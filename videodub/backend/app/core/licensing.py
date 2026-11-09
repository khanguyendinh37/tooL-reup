"""Single-device license gate for the packaged VideoDub app.

Design (see docs/superpowers/specs/2026-09-12-device-license-design.md):

* A license provider (see ``license_keygen.py``) activates the key for this
  device online and issues a certificate signed with the provider's private
  key. The app only ships the matching public key, so the certificate cannot
  be forged or moved to another machine without detection.
* The certificate is cached under the app data directory and allows offline
  use until it expires (72 hours after the last successful online check, never
  past the license's own expiry).
* The license is re-validated online periodically. Only temporary network or
  server failures fall back to the cached certificate; an explicit rejection
  (suspended, expired, device released) revokes local access immediately.
* Packaged (frozen) builds always enforce the license and ignore any runtime
  override. Source runs (run.bat) only enforce it when
  ``VIDEODUB_LICENSE_REQUIRED=1``, so internal development is never locked.

This deters casual sharing; it cannot stop someone who modifies the program.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from app.core.paths import BACKEND_DIR, DATA_DIR

logger = logging.getLogger(__name__)

OFFLINE_GRACE = timedelta(hours=72)
REVALIDATE_AFTER = timedelta(hours=6)
CLOCK_TOLERANCE = timedelta(minutes=10)
STATE_FILENAME = "license.json"
CONFIG_FILENAME = "license_config.json"
DEFAULT_CONTACT = "Liên hệ người bán VideoDub để được hỗ trợ."
MAX_KEY_LENGTH = 256


class LicenseError(Exception):
    """Base error; ``str(error)`` is a user-facing Vietnamese message."""


class LicenseRejected(LicenseError):
    """The provider explicitly refused the key or this device."""

    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


class ProviderUnavailable(LicenseError):
    """Temporary network/server failure; cached certificate stays usable."""


class DeviceIdError(LicenseError):
    """The OS device identifier could not be read."""


@dataclass(frozen=True)
class Certificate:
    raw: str
    fingerprint: str
    issued: datetime
    expiry: datetime
    license_expiry: Optional[datetime] = None


class LicenseProvider(Protocol):
    """Adapter interface; swap providers by implementing these three calls."""

    def activate(self, key: str, fingerprint: str, device_name: str, platform_name: str) -> Certificate: ...

    def refresh(self, key: str, fingerprint: str) -> Certificate: ...

    def verify(self, raw: str) -> Certificate: ...


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.astimezone(timezone.utc).isoformat() if value else None


# ---------------------------------------------------------------------------
# Device identity
# ---------------------------------------------------------------------------

def _machine_identifier() -> str:
    """Return the OS installation identifier. MAC addresses are never used."""
    value = ""
    try:
        if sys.platform == "win32":
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as handle:
                value, _ = winreg.QueryValueEx(handle, "MachineGuid")
        elif sys.platform == "darwin":
            output = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=10, check=True,
            ).stdout
            match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', output)
            value = match.group(1) if match else ""
        else:
            for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                if os.path.isfile(candidate):
                    value = Path(candidate).read_text().strip()
                    break
    except Exception as exc:
        logger.warning("Could not read device identifier: %s", exc)
        value = ""
    value = str(value or "").strip()
    if len(value) < 8:
        raise DeviceIdError(
            "Không đọc được mã định danh thiết bị từ hệ điều hành nên không thể kích hoạt license."
        )
    return value


@lru_cache(maxsize=1)
def machine_fingerprint() -> str:
    """Hashed device id; the raw OS identifier never leaves this machine."""
    identifier = _machine_identifier().lower()
    return hashlib.sha256(f"videodub-device-v1:{identifier}".encode()).hexdigest()


def device_name() -> str:
    return (socket.gethostname() or platform.node() or "VideoDub device")[:100]


def platform_name() -> str:
    return f"{platform.system()} {platform.release()}".strip()[:100]


def mask_key(key: str) -> str:
    key = key or ""
    return f"••••{key[-4:]}" if len(key) > 4 else "••••"


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class LicenseManager:
    """Owns the local license state file and decides whether work is allowed."""

    def __init__(
        self,
        provider: Optional[LicenseProvider],
        *,
        state_path: Path,
        enforced: bool = True,
        contact: str = DEFAULT_CONTACT,
        config_error: Optional[str] = None,
        fingerprint_fn: Callable[[], str] = machine_fingerprint,
        clock: Callable[[], datetime] = utcnow,
    ):
        self.provider = provider
        self.state_path = Path(state_path)
        self.enforced = enforced
        self.contact = contact or DEFAULT_CONTACT
        self.config_error = config_error
        self._fingerprint_fn = fingerprint_fn
        self._clock = clock
        self._lock = threading.RLock()

    # -- storage -----------------------------------------------------------
    def _load(self) -> dict:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception:
            logger.warning("License state file is unreadable; treating as unlicensed")
            return {}

    def _save(self, data: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_path)

    # -- public API --------------------------------------------------------
    def status(self) -> dict:
        with self._lock:
            return self._evaluate(self._load(), touch=True)

    def is_allowed(self) -> bool:
        return bool(self.status()["allowed"])

    def activate(self, key: str) -> dict:
        """Activate ``key`` on this device. Raises LicenseError on failure."""
        key = (key or "").strip()
        if not key or len(key) > MAX_KEY_LENGTH:
            raise LicenseRejected("Vui lòng nhập mã license hợp lệ.", "INVALID_INPUT")
        if not self.enforced:
            raise LicenseRejected("Bản chạy nội bộ không yêu cầu license.", "NOT_ENFORCED")
        self._require_ready()
        fingerprint = self._fingerprint_fn()
        certificate = self.provider.activate(key, fingerprint, device_name(), platform_name())
        if certificate.fingerprint != fingerprint:
            raise LicenseRejected("Chứng nhận license không khớp thiết bị này.", "FINGERPRINT_MISMATCH")
        now = self._clock()
        with self._lock:
            self._save({
                "key": key,
                "certificate": certificate.raw,
                "last_validated_at": _iso(now),
                "last_seen_at": _iso(now),
            })
            logger.info("License activated (%s)", mask_key(key))
            return self._evaluate(self._load(), touch=False)

    def refresh(self) -> dict:
        """Validate online now. Network failures keep the cached certificate."""
        with self._lock:
            data = self._load()
        key = data.get("key")
        if not self.enforced or not key or self.config_error or self.provider is None:
            return self.status()
        try:
            fingerprint = self._fingerprint_fn()
            certificate = self.provider.refresh(key, fingerprint)
            if certificate.fingerprint != fingerprint:
                raise LicenseRejected("Chứng nhận license không khớp thiết bị này.", "FINGERPRINT_MISMATCH")
        except LicenseRejected as exc:
            logger.warning("License rejected by provider: %s", getattr(exc, "code", ""))
            with self._lock:
                data = self._load()
                data.pop("certificate", None)
                data["rejected"] = {"message": str(exc), "code": exc.code, "at": _iso(self._clock())}
                self._save(data)
                return self._evaluate(data, touch=False)
        except (ProviderUnavailable, DeviceIdError) as exc:
            logger.info("License online check unavailable: %s", exc)
            with self._lock:
                data = self._load()
                data["last_error"] = str(exc)
                data["last_attempt_at"] = _iso(self._clock())
                self._save(data)
                return self._evaluate(data, touch=True)
        now = self._clock()
        with self._lock:
            data = self._load()
            data.update({
                "certificate": certificate.raw,
                "last_validated_at": _iso(now),
                "last_seen_at": _iso(now),
            })
            for stale in ("rejected", "last_error", "last_attempt_at"):
                data.pop(stale, None)
            self._save(data)
            return self._evaluate(data, touch=False)

    def refresh_if_due(self) -> dict:
        """Re-validate online when the last successful check is stale."""
        with self._lock:
            data = self._load()
        if not self.enforced or not data.get("key") or data.get("rejected"):
            return self.status()
        last = _safe_time(data.get("last_validated_at"))
        attempt = _safe_time(data.get("last_attempt_at"))
        now = self._clock()
        # Back off a little after a failed attempt so the gate stays responsive offline.
        if attempt and timedelta(0) <= now - attempt < timedelta(minutes=5):
            return self.status()
        if last is None or now - last >= REVALIDATE_AFTER or now < last:
            return self.refresh()
        return self.status()

    # -- evaluation --------------------------------------------------------
    def _require_ready(self) -> None:
        if self.config_error or self.provider is None:
            raise LicenseError(self.config_error or "Bản cài thiếu cấu hình license.")

    def _result(self, state: str, message: str, data: dict, **extra) -> dict:
        allowed = state in ("disabled", "active")
        result = {
            "enforced": self.enforced,
            "state": state,
            "allowed": allowed,
            "message": message,
            "contact": self.contact,
            "device_name": device_name(),
            "key_hint": mask_key(data["key"]) if data.get("key") else None,
            "last_validated_at": data.get("last_validated_at"),
            "license_expiry": None,
            "offline_until": None,
            "offline": False,
        }
        result.update(extra)
        return result

    def _evaluate(self, data: dict, *, touch: bool) -> dict:
        if not self.enforced:
            return self._result("disabled", "Bản chạy nội bộ: không yêu cầu license.", {})
        if self.config_error or self.provider is None:
            return self._result("misconfigured", self.config_error or "Bản cài thiếu cấu hình license.", data)
        try:
            fingerprint = self._fingerprint_fn()
        except DeviceIdError as exc:
            return self._result("device_error", str(exc), data)
        if not data.get("key"):
            return self._result("unlicensed", "Chưa kích hoạt license trên thiết bị này.", data)
        if data.get("rejected"):
            return self._result("revoked", data["rejected"].get("message") or "License không còn hiệu lực.", data)
        raw = data.get("certificate")
        if not raw:
            return self._result("unlicensed", "Chưa kích hoạt license trên thiết bị này.", data)
        try:
            certificate = self.provider.verify(raw)
        except LicenseError:
            return self._result("unlicensed", "Chứng nhận license đã lưu không hợp lệ. Hãy kích hoạt lại.", data)
        if certificate.fingerprint != fingerprint:
            return self._result("unlicensed", "License đã lưu thuộc về thiết bị khác. Hãy kích hoạt lại.", data)

        now = self._clock()
        expiry_info = {
            "license_expiry": _iso(certificate.license_expiry),
            "offline_until": _iso(min(filter(None, (certificate.expiry, certificate.license_expiry)))),
        }
        last_seen = _safe_time(data.get("last_seen_at"))
        if (last_seen and now < last_seen - CLOCK_TOLERANCE) or now < certificate.issued - CLOCK_TOLERANCE:
            return self._result(
                "clock_rollback",
                "Đồng hồ máy tính có vẻ bị chỉnh lùi. Hãy chỉnh đúng giờ và kết nối mạng để xác thực lại license.",
                data, **expiry_info,
            )
        if certificate.license_expiry and now >= certificate.license_expiry:
            return self._result(
                "expired",
                f"License đã hết hạn ngày {certificate.license_expiry.astimezone().strftime('%d/%m/%Y')}.",
                data, **expiry_info,
            )
        if now >= certificate.expiry:
            hours = int(OFFLINE_GRACE.total_seconds() // 3600)
            return self._result(
                "offline_expired",
                f"Đã quá {hours} giờ chưa xác thực được license. Hãy kết nối mạng để tiếp tục.",
                data, **expiry_info,
            )

        if touch and (last_seen is None or now - last_seen > timedelta(minutes=1)):
            data["last_seen_at"] = _iso(now)
            try:
                self._save(data)
            except OSError:
                logger.warning("Could not update license state timestamp")
        last_validated = _safe_time(data.get("last_validated_at"))
        offline = bool(data.get("last_error")) or last_validated is None or now - last_validated > REVALIDATE_AFTER
        return self._result("active", "License đang hoạt động.", data, offline=offline, **expiry_info)

    def denial_message(self, status: Optional[dict] = None) -> str:
        status = status or self.status()
        return f"{status['message']} Cần license hợp lệ để xử lý video mới. {self.contact}".strip()


def _safe_time(value: Any) -> Optional[datetime]:
    try:
        return parse_time(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Configuration / singleton
# ---------------------------------------------------------------------------

def is_enforced() -> bool:
    if getattr(sys, "frozen", False):
        return True  # packaged builds: no runtime switch to disable licensing
    return os.environ.get("VIDEODUB_LICENSE_REQUIRED") == "1"


def _config_path() -> Path:
    override = os.environ.get("VIDEODUB_LICENSE_CONFIG")
    if override and not getattr(sys, "frozen", False):
        return Path(override)
    return BACKEND_DIR / CONFIG_FILENAME


def _license_dir() -> Path:
    # The --pipeline-check CLI uses an isolated data dir but must still read the
    # user's real license; a pointed-elsewhere dir only holds certificates that
    # must verify for this device anyway.
    return Path(os.environ.get("VIDEODUB_LICENSE_DIR") or DATA_DIR)


def build_manager() -> LicenseManager:
    enforced = is_enforced()
    state_path = _license_dir() / STATE_FILENAME
    provider: Optional[LicenseProvider] = None
    config_error: Optional[str] = None
    contact = DEFAULT_CONTACT
    if enforced:
        try:
            config = json.loads(_config_path().read_text(encoding="utf-8"))
            contact = config.get("contact") or DEFAULT_CONTACT
            name = config.get("provider", "keygen")
            if name != "keygen":
                raise ValueError(f"unsupported provider {name}")
            from app.core.license_keygen import KeygenProvider

            provider = KeygenProvider(
                account=config["account"],
                public_key_hex=config["public_key"],
                api_url=config.get("api_url") or "https://api.keygen.sh",
            )
        except Exception as exc:
            logger.error("License configuration invalid: %s", exc)
            config_error = "Bản cài thiếu hoặc sai cấu hình license. Liên hệ người bán để nhận bản cài đúng."
    return LicenseManager(
        provider, state_path=state_path, enforced=enforced, contact=contact, config_error=config_error,
    )


_manager: Optional[LicenseManager] = None
_manager_lock = threading.Lock()


def get_manager() -> LicenseManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = build_manager()
        return _manager


def set_manager(manager: Optional[LicenseManager]) -> None:
    """Testing hook."""
    global _manager
    with _manager_lock:
        _manager = manager
