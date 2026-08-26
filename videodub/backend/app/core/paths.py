"""Runtime paths shared by development and the packaged desktop app."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Union

PathLike = Union[str, os.PathLike[str]]

# In source runs this is the backend directory. In a PyInstaller build the
# bundled ``app`` package is copied to the runtime root, so the same lookup
# resolves to the extracted application root.
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
    configured = os.environ.get("VIDEODUB_DATA_DIR")
    if configured:
        return Path(configured).expanduser()

    # A frozen app must never write beside its executable (often Program
    # Files, which is not user-writable). Keep source development behaviour
    # unchanged by using the backend directory when not frozen.
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            if base:
                return Path(base) / "VideoDub"
        base = os.environ.get("XDG_DATA_HOME")
        if base:
            return Path(base) / "VideoDub"
        return Path.home() / ".local" / "share" / "VideoDub"

    return BACKEND_DIR


DATA_DIR = _default_data_dir()
TEMP_DIR = DATA_DIR / "temp"
OUTPUT_DIR = DATA_DIR / "output"
COOKIES_DIR = DATA_DIR / "cookies"
DATABASE_PATH = DATA_DIR / "videodub.db"


def ensure_data_dirs() -> None:
    """Create all user-writable runtime directories if needed."""
    for directory in (DATA_DIR, TEMP_DIR, OUTPUT_DIR, COOKIES_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def resolve_data_path(path: PathLike | None) -> str | None:
    """Resolve a stored relative path against the app data directory.

    Existing database rows may contain absolute paths, so those are preserved.
    Relative paths continue to work for local development and are now safely
    rooted in the persistent desktop data directory.
    """
    if path is None:
        return None

    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return str(DATA_DIR / candidate)


ensure_data_dirs()
