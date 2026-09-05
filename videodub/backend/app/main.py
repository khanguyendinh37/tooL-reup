import logging
from datetime import datetime
from pathlib import Path
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import update

from app.api import dubbing, history, settings, cookies, tts_preview
from app.core.paths import COOKIES_DIR, DATA_DIR, OUTPUT_DIR, TEMP_DIR
from app.models.database import DubbingJob, async_session, init_db

logger = logging.getLogger(__name__)

# Statuses that mean a background task was actively working. If the process
# exits (crash, reload, shutdown) nothing will ever resume them, so they are
# marked as failed on the next startup. "preview_ready" is intentionally not
# included: it is a resting state waiting for the user to start dubbing.
ACTIVE_STATUSES = (
    "pending", "downloading", "processing", "transcribing",
    "translating", "tts", "removing_vocals", "merging",
)

app = FastAPI(title="VideoDub API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All generated files live outside the installed application. This is the
# backend directory during development and %LOCALAPPDATA%/VideoDub when frozen.
for directory in (DATA_DIR, TEMP_DIR, OUTPUT_DIR, COOKIES_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app.include_router(dubbing.router, prefix="/api/dubbing", tags=["dubbing"])
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(cookies.router, prefix="/api/cookies", tags=["cookies"])
app.include_router(tts_preview.router, prefix="/api/tts", tags=["tts"])


@app.on_event("startup")
async def startup():
    await init_db()
    await _fail_interrupted_jobs()


async def _fail_interrupted_jobs():
    """Mark jobs stranded in an active state by a previous run as failed.

    Without this, jobs whose backend died mid-pipeline stay "downloading"/"tts"
    forever, and the frontend watchdog immediately reports them as timed out
    on the next launch.
    """
    try:
        async with async_session() as session:
            result = await session.execute(
                update(DubbingJob)
                .where(DubbingJob.status.in_(ACTIVE_STATUSES))
                .values(
                    status="error",
                    progress=0,
                    error="Quy trình bị gián đoạn (ứng dụng đã khởi động lại). Hãy thử lại.",
                    updated_at=datetime.utcnow(),
                )
            )
            await session.commit()
        if result.rowcount:
            logger.warning("Marked %d interrupted job(s) as error on startup", result.rowcount)
    except Exception:
        logger.exception("Could not clean up interrupted jobs on startup")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "VideoDub API"}


# In desktop mode the production Vite build is served by this same local API
# process, so the renderer can keep using relative /api URLs. The route is
# registered only when a build directory exists; dev Vite remains unchanged.
_FRONTEND_DIST = Path(
    os.environ.get(
        "VIDEODUB_FRONTEND_DIR",
        str(Path(__file__).resolve().parents[2] / "frontend_dist"),
    )
).resolve()

if _FRONTEND_DIST.is_dir():
    _FRONTEND_ROOT = _FRONTEND_DIST
    _FRONTEND_INDEX = _FRONTEND_ROOT / "index.html"
    _FRONTEND_ASSETS = _FRONTEND_ROOT / "assets"

    if _FRONTEND_ASSETS.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_FRONTEND_ASSETS)),
            name="frontend-assets",
        )

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_frontend(path: str):
        # Never turn an unknown API URL into an HTML response.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")

        requested = (_FRONTEND_ROOT / path).resolve()
        try:
            requested.relative_to(_FRONTEND_ROOT)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")

        if requested.is_file():
            return FileResponse(str(requested))
        if _FRONTEND_INDEX.is_file():
            return FileResponse(str(_FRONTEND_INDEX))
        raise HTTPException(status_code=404, detail="Frontend build not found")
