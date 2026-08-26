"""Desktop entry point for VideoDub.

The packaged executable starts FastAPI on a local loopback port and opens the
production Vite build inside a native pywebview window. The backend remains
unchanged as an HTTP API, which keeps development and desktop behaviour aligned.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import socket
import sys
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

APP_NAME = "VideoDub"


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[1]


def _backend_root(project_root: Path) -> Path:
    return project_root if getattr(sys, "frozen", False) else project_root / "backend"


def _frontend_dist(project_root: Path) -> Path:
    if getattr(sys, "frozen", False):
        return project_root / "frontend_dist"
    return project_root / "frontend" / "dist"


def _user_data_dir() -> Path:
    configured = os.environ.get("VIDEODUB_DATA_DIR")
    if configured:
        return Path(configured).expanduser()

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME

    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def _prepare_runtime() -> tuple[Path, Path]:
    project_root = _project_root()
    backend_root = _backend_root(project_root)
    frontend_dist = _frontend_dist(project_root)

    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    os.environ.setdefault("VIDEODUB_DATA_DIR", str(_user_data_dir()))
    os.environ.setdefault("VIDEODUB_FRONTEND_DIR", str(frontend_dist))

    ffmpeg_candidates = [
        project_root / "ffmpeg" if getattr(sys, "frozen", False) else project_root / "desktop" / "vendor" / "ffmpeg",
    ]
    for ffmpeg_dir in ffmpeg_candidates:
        if ffmpeg_dir.is_dir():
            os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")
            break

    log_dir = Path(os.environ["VIDEODUB_DATA_DIR"]) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "desktop.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return backend_root, frontend_dist


_backend_root_path, _frontend_dist_path = _prepare_runtime()

# Imports intentionally happen after environment and sys.path preparation so
# database/storage constants resolve to the persistent desktop directory.
import uvicorn  # noqa: E402
import webview  # noqa: E402
from app.main import app  # noqa: E402


logger = logging.getLogger(__name__)


class DesktopApi:
    """Native actions exposed to the React renderer through pywebview."""

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = re.sub(r'[\\\\/:*?"<>|]+', "_", filename or "VideoDub.mp4")
        return cleaned.strip(" .") or "VideoDub.mp4"

    def save_file(self, url: str, filename: str = "VideoDub.mp4") -> dict[str, str]:
        """Download a result through a native Save As dialog."""
        if not url.startswith("http://127.0.0.1:"):
            return {"status": "error", "message": "Chỉ cho phép tải file từ API cục bộ"}

        window = webview.windows[0]
        destination = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=self._safe_filename(filename),
            file_types=("Video files (*.mp4)", "All files (*.*)"),
        )
        if not destination:
            return {"status": "cancelled"}
        if isinstance(destination, (tuple, list)):
            destination = destination[0]

        try:
            request = Request(url, headers={"User-Agent": "VideoDub Desktop"})
            with urlopen(request, timeout=600) as response, open(destination, "wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            return {"status": "ok", "path": str(destination)}
        except Exception as exc:
            logger.exception("Native download failed")
            return {"status": "error", "message": str(exc)}


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_api(port: int) -> None:
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )


def _wait_for_api(port: int, timeout: float = 30.0) -> bool:
    health_url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=1.0) as response:
                if response.status == 200:
                    return True
        except (OSError, URLError):
            time.sleep(0.2)
    return False


def main() -> None:
    if not _frontend_dist_path.joinpath("index.html").is_file():
        raise FileNotFoundError(
            f"Không tìm thấy frontend build: {_frontend_dist_path}. "
            "Hãy chạy desktop\\build.bat trước."
        )

    port = _find_free_port()
    api_thread = threading.Thread(target=_run_api, args=(port,), daemon=True)
    api_thread.start()

    if not _wait_for_api(port):
        raise RuntimeError("VideoDub API không khởi động được trong thời gian cho phép")

    logger.info("VideoDub desktop started on http://127.0.0.1:%s", port)
    try:
        webview.create_window(
            APP_NAME,
            f"http://127.0.0.1:{port}/",
            width=1440,
            height=920,
            min_size=(1024, 700),
            resizable=True,
            text_select=True,
            background_color="#020617",
            js_api=DesktopApi(),
        )
        webview.start(debug=False)
        logger.info("VideoDub desktop window closed")
    except Exception:
        logger.exception("VideoDub desktop window failed to start")
        raise


if __name__ == "__main__":
    main()
