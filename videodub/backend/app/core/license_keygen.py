"""Keygen (keygen.sh cloud or self-hosted Keygen CE) license provider.

Only public, key-scoped endpoints are used; no admin/product token ships in
the app:

* ``licenses/actions/validate-key`` (no auth) with a fingerprint scope,
* ``machines`` (``Authorization: License <key>``) to activate this device,
* ``machines/<id>/actions/check-out`` to get a machine file: a certificate
  signed with the account's Ed25519 key. The app verifies it with the public
  key only, so cached offline access cannot be forged or copied to another
  device.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import timedelta
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.core.licensing import (
    OFFLINE_GRACE,
    Certificate,
    LicenseError,
    LicenseRejected,
    ProviderUnavailable,
    parse_time,
)

logger = logging.getLogger(__name__)

JSONAPI = "application/vnd.api+json"
CERT_HEADER = "-----BEGIN MACHINE FILE-----"
CERT_FOOTER = "-----END MACHINE FILE-----"

# Transport signature: (method, url, headers, body) -> (status, response bytes)
Transport = Callable[[str, str, dict, Optional[bytes]], tuple[int, bytes]]

_ACTIVATABLE = {"NO_MACHINE", "NO_MACHINES", "FINGERPRINT_SCOPE_MISMATCH"}
_OTHER_DEVICE = "Mã license đã được kích hoạt trên thiết bị khác. Liên hệ người bán nếu cần đổi máy."
_MESSAGES = {
    "NOT_FOUND": "Mã license không tồn tại. Kiểm tra lại mã đã nhận.",
    "LICENSE_INVALID": "Mã license không đúng. Kiểm tra lại mã đã nhận.",
    "SUSPENDED": "License đã bị khóa.",
    "BANNED": "License đã bị khóa.",
    "EXPIRED": "License đã hết hạn.",
    "OVERDUE": "License đã quá hạn kiểm tra.",
    "TOO_MANY_MACHINES": _OTHER_DEVICE,
    "MACHINE_LIMIT_EXCEEDED": _OTHER_DEVICE,
    "FINGERPRINT_TAKEN": _OTHER_DEVICE,
    "FINGERPRINT_SCOPE_MISMATCH": "Thiết bị này không còn được liên kết với license.",
    "NO_MACHINE": "Thiết bị này không còn được liên kết với license.",
    "NO_MACHINES": "Thiết bị này không còn được liên kết với license.",
}


def message_for(code: str, detail: str = "") -> str:
    return _MESSAGES.get(code or "", f"License không hợp lệ ({code or detail or 'không rõ lỗi'}).")


def _urllib_transport(timeout: float) -> Transport:
    def send(method: str, url: str, headers: dict, body: Optional[bytes]) -> tuple[int, bytes]:
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.status, response.read()
        except HTTPError as exc:
            return exc.code, exc.read() or b""

    return send


class KeygenProvider:
    def __init__(
        self,
        account: str,
        public_key_hex: str,
        api_url: str = "https://api.keygen.sh",
        *,
        ttl: timedelta = OFFLINE_GRACE,
        timeout: float = 15.0,
        transport: Optional[Transport] = None,
    ):
        if not account or not public_key_hex:
            raise ValueError("Keygen account and public key are required")
        self.account = account
        self.public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex.strip()))
        self.base = f"{api_url.rstrip('/')}/v1/accounts/{quote(account, safe='')}"
        self.ttl_seconds = int(ttl.total_seconds())
        self._send = transport or _urllib_transport(timeout)

    # -- HTTP --------------------------------------------------------------
    def _request(self, method: str, path: str, *, body: Optional[dict] = None,
                 key: Optional[str] = None, query: Optional[dict] = None) -> dict:
        url = self.base + path + (f"?{urlencode(query)}" if query else "")
        headers = {"Accept": JSONAPI, "User-Agent": "VideoDub Desktop"}
        if body is not None:
            headers["Content-Type"] = JSONAPI
        if key:
            headers["Authorization"] = f"License {key}"
        payload = json.dumps(body).encode() if body is not None else None
        try:
            status, raw = self._send(method, url, headers, payload)
        except (URLError, OSError, TimeoutError) as exc:
            raise ProviderUnavailable("Không kết nối được máy chủ license. Kiểm tra mạng rồi thử lại.") from exc
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            data = {}
        if status >= 500 or status in (408, 429) or status == 0:
            raise ProviderUnavailable("Máy chủ license tạm thời không phản hồi. Hãy thử lại sau.")
        if status >= 400:
            error = (data.get("errors") or [None])[0] or data.get("meta") or {}
            code = str(error.get("code") or "")
            raise LicenseRejected(message_for(code, str(error.get("detail") or "")), code)
        return data

    def _validate(self, key: str, fingerprint: str) -> dict:
        return self._request("POST", "/licenses/actions/validate-key", body={
            "meta": {"key": key, "scope": {"fingerprint": fingerprint}},
        })

    def _machine_id(self, key: str, fingerprint: str) -> str:
        try:
            data = self._request("GET", f"/machines/{quote(fingerprint, safe='')}", key=key)
        except LicenseRejected as exc:
            if exc.code == "NOT_FOUND":
                raise LicenseRejected(message_for("NO_MACHINE"), "NO_MACHINE") from exc
            raise
        machine_id = (data.get("data") or {}).get("id")
        if not machine_id:
            raise LicenseRejected(message_for("NO_MACHINE"), "NO_MACHINE")
        return machine_id

    def _checkout(self, key: str, machine_id: str, fingerprint: str) -> Certificate:
        data = self._request(
            "POST", f"/machines/{quote(machine_id, safe='')}/actions/check-out", key=key,
            query={"ttl": self.ttl_seconds, "include": "license"},
        )
        raw = ((data.get("data") or {}).get("attributes") or {}).get("certificate")
        if not raw:
            raise ProviderUnavailable("Máy chủ license trả về chứng nhận rỗng. Hãy thử lại sau.")
        certificate = self.verify(raw)
        if certificate.fingerprint != fingerprint:
            raise LicenseRejected("Chứng nhận license không khớp thiết bị này.", "FINGERPRINT_MISMATCH")
        return certificate

    # -- adapter interface ---------------------------------------------------
    def activate(self, key: str, fingerprint: str, device_name: str, platform_name: str) -> Certificate:
        result = self._validate(key, fingerprint)
        meta = result.get("meta") or {}
        code = str(meta.get("code") or "")
        if meta.get("valid"):
            machine_id = self._machine_id(key, fingerprint)  # idempotent re-activation
        elif code in _ACTIVATABLE:
            license_id = (result.get("data") or {}).get("id")
            if not license_id:
                raise LicenseRejected(message_for("NOT_FOUND"), "NOT_FOUND")
            created = self._request("POST", "/machines", key=key, body={"data": {
                "type": "machines",
                "attributes": {"fingerprint": fingerprint, "name": device_name, "platform": platform_name},
                "relationships": {"license": {"data": {"type": "licenses", "id": license_id}}},
            }})
            machine_id = (created.get("data") or {}).get("id")
            if not machine_id:
                raise ProviderUnavailable("Máy chủ license không trả về thiết bị. Hãy thử lại sau.")
        else:
            raise LicenseRejected(message_for(code, str(meta.get("detail") or "")), code)
        return self._checkout(key, machine_id, fingerprint)

    def refresh(self, key: str, fingerprint: str) -> Certificate:
        result = self._validate(key, fingerprint)
        meta = result.get("meta") or {}
        if not meta.get("valid"):
            code = str(meta.get("code") or "")
            raise LicenseRejected(message_for(code, str(meta.get("detail") or "")), code)
        return self._checkout(key, self._machine_id(key, fingerprint), fingerprint)

    def verify(self, raw: str) -> Certificate:
        try:
            text = raw.strip()
            if not text.startswith(CERT_HEADER) or not text.endswith(CERT_FOOTER):
                raise ValueError("not a machine file")
            body = text[len(CERT_HEADER):-len(CERT_FOOTER)]
            envelope = json.loads(base64.b64decode("".join(body.split())))
            if envelope.get("alg") != "base64+ed25519":
                raise ValueError(f"unsupported algorithm {envelope.get('alg')}")
            enc, sig = envelope["enc"], envelope["sig"]
            self.public_key.verify(base64.b64decode(sig), f"machine/{enc}".encode())
            payload = json.loads(base64.b64decode(enc))
            meta = payload["meta"]
            issued = parse_time(meta["issued"])
            expiry = parse_time(meta["expiry"])
            fingerprint = payload["data"]["attributes"]["fingerprint"]
            license_expiry = None
            for item in payload.get("included") or []:
                if item.get("type") == "licenses":
                    license_expiry = parse_time((item.get("attributes") or {}).get("expiry"))
            if issued is None or expiry is None or not fingerprint:
                raise ValueError("incomplete certificate")
        except (InvalidSignature, ValueError, KeyError, TypeError) as exc:
            raise LicenseError("Chứng nhận license không hợp lệ.") from exc
        if license_expiry and license_expiry < expiry:
            expiry = license_expiry
        return Certificate(raw=raw, fingerprint=fingerprint, issued=issued,
                           expiry=expiry, license_expiry=license_expiry)
