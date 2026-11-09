"""License activation gate tests against an in-process fake Keygen server."""

import base64
import json
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import license as license_api
from app.core import licensing
from app.core.license_keygen import KeygenProvider
from app.core.licensing import LicenseManager, LicenseRejected, ProviderUnavailable

ACCOUNT = "acct-test"
DEVICE_A = "a" * 64
DEVICE_B = "b" * 64
START = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now=START):
        self.now = now

    def __call__(self):
        return self.now


def _iso(value):
    return value.isoformat().replace("+00:00", "Z") if value else None


class FakeKeygen:
    """Minimal model of the Keygen endpoints the provider uses."""

    def __init__(self, clock, signing_key):
        self.clock = clock
        self.signing_key = signing_key
        self.offline = False
        self.licenses = {
            "GOOD-KEY": {"id": "lic-1", "status": "ACTIVE", "expiry": None, "max": 1, "machines": {}},
        }
        self.machine_creates = 0
        self.requests = []

    def _lic_by_key(self, key):
        return self.licenses.get(key)

    def transport(self, method, url, headers, body):
        self.requests.append((method, url, headers, body))
        if self.offline:
            raise URLError("network down")
        parsed = urlparse(url)
        path = parsed.path.split(f"/v1/accounts/{ACCOUNT}", 1)[1]
        payload = json.loads(body) if body else {}
        auth = headers.get("Authorization", "")
        if path == "/licenses/actions/validate-key":
            return self._validate(payload["meta"]["key"], payload["meta"]["scope"]["fingerprint"])
        lic = self._lic_by_key(auth.removeprefix("License "))
        if lic is None or lic["status"] != "ACTIVE":
            return self._error(403, "LICENSE_INVALID")
        if method == "POST" and path == "/machines":
            fingerprint = payload["data"]["attributes"]["fingerprint"]
            if fingerprint not in lic["machines"] and len(lic["machines"]) >= lic["max"]:
                return self._error(422, "MACHINE_LIMIT_EXCEEDED")
            self.machine_creates += 1
            lic["machines"].setdefault(fingerprint, f"mach-{self.machine_creates}")
            return 201, json.dumps({"data": {"id": lic["machines"][fingerprint]}}).encode()
        match = re.fullmatch(r"/machines/([^/]+)", path)
        if method == "GET" and match:
            fingerprint = match.group(1)
            if fingerprint not in lic["machines"]:
                return self._error(404, "NOT_FOUND")
            return 200, json.dumps({"data": {"id": lic["machines"][fingerprint]}}).encode()
        match = re.fullmatch(r"/machines/([^/]+)/actions/check-out", path)
        if method == "POST" and match:
            machine_id = match.group(1)
            fingerprint = next((fp for fp, mid in lic["machines"].items() if mid == machine_id), None)
            if fingerprint is None:
                return self._error(404, "NOT_FOUND")
            ttl = int(parse_qs(parsed.query)["ttl"][0])
            cert = self.machine_file(fingerprint, lic, ttl)
            return 200, json.dumps({"data": {"attributes": {"certificate": cert}}}).encode()
        return self._error(404, "NOT_FOUND")

    def _validate(self, key, fingerprint):
        lic = self._lic_by_key(key)
        if lic is None:
            return 200, json.dumps({"meta": {"valid": False, "code": "NOT_FOUND"}, "data": None}).encode()
        code = "VALID"
        if lic["status"] != "ACTIVE":
            code = lic["status"]
        elif lic["expiry"] and self.clock() >= lic["expiry"]:
            code = "EXPIRED"
        elif not lic["machines"]:
            code = "NO_MACHINE"
        elif fingerprint not in lic["machines"]:
            code = "FINGERPRINT_SCOPE_MISMATCH"
        body = {"meta": {"valid": code == "VALID", "code": code}, "data": {"id": lic["id"]}}
        return 200, json.dumps(body).encode()

    @staticmethod
    def _error(status, code):
        return status, json.dumps({"errors": [{"code": code, "detail": code}]}).encode()

    def machine_file(self, fingerprint, lic, ttl, issued=None):
        issued = issued or self.clock()
        payload = {
            "meta": {"issued": _iso(issued), "expiry": _iso(issued + timedelta(seconds=ttl)), "ttl": ttl},
            "data": {"type": "machines", "attributes": {"fingerprint": fingerprint}},
            "included": [{"type": "licenses", "attributes": {"expiry": _iso(lic["expiry"])}}],
        }
        enc = base64.b64encode(json.dumps(payload).encode()).decode()
        sig = base64.b64encode(self.signing_key.sign(f"machine/{enc}".encode())).decode()
        envelope = base64.b64encode(json.dumps({"enc": enc, "sig": sig, "alg": "base64+ed25519"}).encode()).decode()
        lines = [envelope[i:i + 64] for i in range(0, len(envelope), 64)]
        return "-----BEGIN MACHINE FILE-----\n" + "\n".join(lines) + "\n-----END MACHINE FILE-----\n"


class LicenseTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = Clock()
        self.signing_key = Ed25519PrivateKey.generate()
        public_hex = self.signing_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        self.server = FakeKeygen(self.clock, self.signing_key)
        self.provider = KeygenProvider(ACCOUNT, public_hex, "https://license.test", transport=self.server.transport)
        self.state_path = Path(self.tmp.name) / "license.json"

    def manager(self, fingerprint=DEVICE_A, state_path=None, **kwargs):
        return LicenseManager(
            self.provider,
            state_path=state_path or self.state_path,
            contact="Zalo 0900000000",
            fingerprint_fn=lambda: fingerprint,
            clock=self.clock,
            **kwargs,
        )


class ActivationTests(LicenseTestBase):
    def test_first_activation_stores_signed_certificate(self):
        status = self.manager().activate("GOOD-KEY")
        self.assertEqual(status["state"], "active")
        self.assertTrue(status["allowed"])
        self.assertEqual(status["key_hint"], "••••-KEY")
        stored = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertIn("BEGIN MACHINE FILE", stored["certificate"])
        # No admin token is ever sent; activation uses the customer's own key.
        for _, _, headers, _ in self.server.requests:
            auth = headers.get("Authorization", "")
            self.assertTrue(auth == "" or auth.startswith("License "))

    def test_reactivation_on_same_device_is_idempotent(self):
        self.manager().activate("GOOD-KEY")
        self.state_path.unlink()
        status = self.manager().activate("GOOD-KEY")
        self.assertEqual(status["state"], "active")
        self.assertEqual(self.server.machine_creates, 1)

    def test_second_device_is_refused(self):
        self.manager().activate("GOOD-KEY")
        other = self.manager(DEVICE_B, state_path=Path(self.tmp.name) / "b.json")
        with self.assertRaises(LicenseRejected) as ctx:
            other.activate("GOOD-KEY")
        self.assertIn("thiết bị khác", str(ctx.exception))
        self.assertFalse(other.is_allowed())

    def test_unknown_key_is_refused(self):
        with self.assertRaises(LicenseRejected) as ctx:
            self.manager().activate("WRONG")
        self.assertIn("không tồn tại", str(ctx.exception))
        self.assertFalse(self.state_path.exists())

    def test_activation_offline_reports_unavailable(self):
        self.server.offline = True
        with self.assertRaises(ProviderUnavailable):
            self.manager().activate("GOOD-KEY")

    def test_unlicensed_by_default(self):
        status = self.manager().status()
        self.assertEqual(status["state"], "unlicensed")
        self.assertFalse(status["allowed"])

    def test_not_enforced_allows_everything(self):
        status = self.manager(enforced=False).status()
        self.assertEqual(status["state"], "disabled")
        self.assertTrue(status["allowed"])

    def test_missing_configuration_fails_closed(self):
        manager = LicenseManager(None, state_path=self.state_path, config_error="thiếu cấu hình",
                                 fingerprint_fn=lambda: DEVICE_A, clock=self.clock)
        self.assertEqual(manager.status()["state"], "misconfigured")
        self.assertFalse(manager.is_allowed())


class OfflineAndRevocationTests(LicenseTestBase):
    def setUp(self):
        super().setUp()
        self.manager().activate("GOOD-KEY")

    def test_offline_grace_then_expiry(self):
        self.server.offline = True
        self.clock.now = START + timedelta(hours=48)
        status = self.manager().refresh_if_due()
        self.assertEqual(status["state"], "active")
        self.assertTrue(status["offline"])
        self.clock.now = START + timedelta(hours=73)
        status = self.manager().refresh_if_due()
        self.assertEqual(status["state"], "offline_expired")
        self.assertFalse(status["allowed"])
        # Back online: access returns with a fresh certificate.
        self.server.offline = False
        self.clock.now += timedelta(minutes=10)
        self.assertEqual(self.manager().refresh_if_due()["state"], "active")

    def test_periodic_revalidation_extends_offline_window(self):
        self.clock.now = START + timedelta(hours=60)
        self.assertEqual(self.manager().refresh_if_due()["state"], "active")
        self.server.offline = True
        self.clock.now = START + timedelta(hours=100)
        self.assertEqual(self.manager().status()["state"], "active")

    def test_suspension_revokes_immediately(self):
        self.server.licenses["GOOD-KEY"]["status"] = "SUSPENDED"
        status = self.manager().refresh()
        self.assertEqual(status["state"], "revoked")
        self.assertFalse(status["allowed"])
        self.assertIn("khóa", status["message"])

    def test_released_device_is_revoked(self):
        self.server.licenses["GOOD-KEY"]["machines"].clear()
        status = self.manager().refresh()
        self.assertEqual(status["state"], "revoked")

    def test_license_expiry_caps_offline_use(self):
        lic = self.server.licenses["GOOD-KEY"]
        lic["expiry"] = START + timedelta(hours=10)
        self.manager().refresh()
        self.server.offline = True
        self.clock.now = START + timedelta(hours=11)
        status = self.manager().status()
        self.assertEqual(status["state"], "expired")
        self.assertFalse(status["allowed"])

    def test_tampered_certificate_is_rejected(self):
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        lic = self.server.licenses["GOOD-KEY"]
        forged_key = Ed25519PrivateKey.generate()
        forger = FakeKeygen(self.clock, forged_key)
        data["certificate"] = forger.machine_file(DEVICE_A, lic, 10 ** 8)
        self.state_path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.manager().status()["state"], "unlicensed")

    def test_state_copied_to_another_device_is_rejected(self):
        copied = Path(self.tmp.name) / "copied.json"
        copied.write_text(self.state_path.read_text(encoding="utf-8"), encoding="utf-8")
        status = self.manager(DEVICE_B, state_path=copied).status()
        self.assertEqual(status["state"], "unlicensed")
        self.assertIn("thiết bị khác", status["message"])

    def test_clock_rollback_requires_online_check(self):
        self.clock.now = START + timedelta(hours=5)
        self.manager().status()
        self.clock.now = START + timedelta(hours=1)
        status = self.manager().status()
        self.assertEqual(status["state"], "clock_rollback")
        self.assertFalse(status["allowed"])


class GateTests(LicenseTestBase):
    def setUp(self):
        super().setUp()
        app = FastAPI()
        app.include_router(license_api.router, prefix="/api/license")
        app.middleware("http")(license_api.license_gate_middleware)

        @app.post("/api/dubbing/start")
        @app.post("/api/dubbing/preview")
        @app.post("/api/dubbing/{job_id}/retry")
        @app.post("/api/dubbing/{job_id}/cancel")
        async def ok():
            return {"ok": True}

        @app.get("/api/history/")
        async def history():
            return []

        licensing.set_manager(self.manager())
        self.addCleanup(licensing.set_manager, None)
        self.client = TestClient(app)

    def test_processing_routes_refused_without_license(self):
        for path in ("/api/dubbing/start", "/api/dubbing/preview", "/api/dubbing/job-1/retry"):
            response = self.client.post(path, json={})
            self.assertEqual(response.status_code, 403, path)
            body = response.json()
            self.assertEqual(body["code"], "license_required")
            self.assertIn("Cần license hợp lệ", body["detail"])
            self.assertIn("Zalo 0900000000", body["detail"])

    def test_other_routes_stay_available(self):
        self.assertEqual(self.client.get("/api/history/").status_code, 200)
        self.assertEqual(self.client.post("/api/dubbing/job-1/cancel").status_code, 200)

    def test_activation_api_unlocks_processing(self):
        self.assertFalse(self.client.get("/api/license/status").json()["allowed"])
        bad = self.client.post("/api/license/activate", json={"key": "WRONG"})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("không tồn tại", bad.json()["detail"])
        good = self.client.post("/api/license/activate", json={"key": "GOOD-KEY"})
        self.assertEqual(good.status_code, 200)
        self.assertTrue(good.json()["allowed"])
        self.assertEqual(self.client.post("/api/dubbing/start", json={}).status_code, 200)

    def test_activation_offline_returns_503(self):
        self.server.offline = True
        response = self.client.post("/api/license/activate", json={"key": "GOOD-KEY"})
        self.assertEqual(response.status_code, 503)


class EnforcementTests(unittest.TestCase):
    def test_source_runs_are_not_enforced_by_default(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VIDEODUB_LICENSE_REQUIRED", None)
            self.assertFalse(licensing.is_enforced())
            os.environ["VIDEODUB_LICENSE_REQUIRED"] = "1"
            self.assertTrue(licensing.is_enforced())

    def test_frozen_builds_always_enforce(self):
        import os
        import sys
        from unittest import mock

        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.dict(os.environ, {"VIDEODUB_LICENSE_REQUIRED": "0"}):
            self.assertTrue(licensing.is_enforced())

    def test_real_device_fingerprint_is_stable_hash(self):
        fingerprint = licensing.machine_fingerprint()
        self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")
        self.assertEqual(fingerprint, licensing.machine_fingerprint())


if __name__ == "__main__":
    unittest.main()
