"""Helpers for running media tools without flashing console windows on Windows."""

from __future__ import annotations

import subprocess
from typing import Any


def hidden_subprocess_kwargs() -> dict[str, Any]:
    """Return subprocess flags that keep child consoles hidden on Windows."""
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if create_no_window:
        return {"creationflags": create_no_window}
    return {}
