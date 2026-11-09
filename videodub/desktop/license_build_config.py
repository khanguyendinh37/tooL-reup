"""Write the license_config.json bundled into commercial desktop builds.

Values are public (license server URL, account id, Ed25519 *public* key) and
come from environment variables at build time. A build without them fails, so
a customer build can never ship without licensing.

  VIDEODUB_LICENSE_ACCOUNT     Keygen account id (UUID) or slug
  VIDEODUB_LICENSE_PUBLIC_KEY  Keygen Ed25519 public verify key (64 hex chars)
  VIDEODUB_LICENSE_API_URL     optional, default https://api.keygen.sh
                               (set to your self-hosted Keygen CE URL)
  VIDEODUB_LICENSE_CONTACT     optional, shown to customers on license errors
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


def license_config_from_env(env=None) -> dict:
    env = os.environ if env is None else env
    account = (env.get("VIDEODUB_LICENSE_ACCOUNT") or "").strip()
    public_key = (env.get("VIDEODUB_LICENSE_PUBLIC_KEY") or "").strip().lower()
    api_url = (env.get("VIDEODUB_LICENSE_API_URL") or "https://api.keygen.sh").strip().rstrip("/")
    contact = (env.get("VIDEODUB_LICENSE_CONTACT") or "").strip()
    problems = []
    if not account:
        problems.append("VIDEODUB_LICENSE_ACCOUNT is missing")
    if not re.fullmatch(r"[0-9a-f]{64}", public_key):
        problems.append("VIDEODUB_LICENSE_PUBLIC_KEY must be the 64-hex-char Ed25519 public key")
    if not api_url.startswith("https://"):
        problems.append("VIDEODUB_LICENSE_API_URL must use https://")
    if problems:
        raise SystemExit("License configuration required for desktop builds: " + "; ".join(problems))
    return {
        "provider": "keygen",
        "api_url": api_url,
        "account": account,
        "public_key": public_key,
        "contact": contact,
    }


def license_data_file(build_dir: Path) -> Path:
    """Validate env, write license_config.json into ``build_dir``, return it."""
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    path = build_dir / "license_config.json"
    path.write_text(json.dumps(license_config_from_env(), indent=2), encoding="utf-8")
    return path
