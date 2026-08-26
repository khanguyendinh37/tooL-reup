import uuid
import asyncio
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import os

from app.models.database import get_session, DubbingJob
from app.core.paths import resolve_data_path
from app.schemas.dubbing import DubbingRequest, DubbingResponse, PreviewRequest
from app.core.pipeline import run_pipeline, run_preview_download
from app.core.translation_config import TranslationConfig, load_translation_config

router = APIRouter()

logger = logging.getLogger(__name__)


def _build_processing_config(
    source_lang: str,
    target_lang: str,
    voice: str,
    whisper_model: str,
    tts_speed: float,
    subtitle_config: Optional[dict],
    audio_config: Optional[dict],
) -> str:
    """Persist the inputs required to restart a failed pipeline exactly."""
    return json.dumps({
        "source_lang": source_lang,
        "target_lang": target_lang,
        "voice": voice,
        "whisper_model": whisper_model,
        "tts_speed": tts_speed,
        "subtitle_config": subtitle_config,
        "audio_config": audio_config,
    })


def _clamp_unit(value, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    if numeric != numeric:  # NaN
        numeric = default
    return min(max(numeric, 0.0), 1.0)


def _map_blur_region(frontend_cfg: dict) -> dict:
    """Convert a normalized editor rectangle to a bounded 0..1 region."""
    raw = frontend_cfg.get("blur_region")
    if not isinstance(raw, dict):
        return {"x": 0.0, "y": 0.76, "width": 1.0, "height": 0.24}

    width = min(max(_clamp_unit(raw.get("width"), 1.0), 0.02), 1.0)
    height = min(max(_clamp_unit(raw.get("height"), 0.24), 0.02), 1.0)
    x = min(_clamp_unit(raw.get("x")), 1.0 - width)
    y = min(_clamp_unit(raw.get("y"), 0.76), 1.0 - height)
    return {"x": x, "y": y, "width": width, "height": height}


def _map_subtitle_config(frontend_cfg: Optional[dict]) -> Optional[dict]:
    """Convert frontend subtitle settings to the pipeline format."""
    if not frontend_cfg or not frontend_cfg.get("enabled"):
        return None

    position_map = {"top": 0.1, "center": 0.5, "bottom": 0.94}
    color_map = {
        "white": "#FFFFFF",
        "yellow": "#FFD700",
        "cyan": "#00FFFF",
        "red": "#FF4444",
    }

    position = frontend_cfg.get("position", "bottom")
    color = frontend_cfg.get("color", "white")
    position_y = _clamp_unit(frontend_cfg.get("position_y"), position_map.get(position, position_map["bottom"]))
    blur_existing = frontend_cfg.get("blur_existing_subtitles", False)
    if isinstance(blur_existing, str):
        blur_existing = blur_existing.lower() in {"1", "true", "yes", "on"}

    return {
        "enabled": True,
        # Keep the rendered subtitle deliberately compact as requested.
        "font_size": 13,
        "font_color": color_map.get(color, color_map["white"]),
        "outline_color": "#000000",
        "outline_width": 1,
        "position_y": position_y,
        "blur_existing_subtitles": bool(blur_existing),
        "blur_region": _map_blur_region(frontend_cfg),
        # The source caption band in the reference occupies roughly the lower
        # quarter of the frame; keep this internal so the public API stays simple.
        "blur_height_ratio": 0.24,
        "blur_strength": 34,
        "blur_steps": 2,
    }


@router.post("/preview", response_model=DubbingResponse)
async def preview_video(req: PreviewRequest, session: AsyncSession = Depends(get_session)):
    """Download video and return preview URL. Phase 1 of the new workflow."""
    job_id = str(uuid.uuid4())[:12]

    source_lang = req.source_lang or "en"
    target_lang = req.target_lang or "vi"
    voice = req.voice or "vi-VN-HoaiMyNeural"
    whisper_model = req.whisper_model or "small"
    job = DubbingJob(
        id=job_id,
        url=req.url,
        source_lang=source_lang,
        target_lang=target_lang,
        voice=voice,
        whisper_model=whisper_model,
        status="downloading",
        progress=0,
        processing_config=_build_processing_config(
            source_lang, target_lang, voice, whisper_model, 1.0, None, None,
        ),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    asyncio.create_task(run_preview_background(job_id, req.url))

    return DubbingResponse.from_orm(job)


async def run_preview_background(job_id: str, url: str):
    """Download video in background for preview."""
    from app.models.database import async_session
    async with async_session() as session:
        try:
            await run_preview_download(job_id, url, session)
            logger.info(f"Preview download completed for job {job_id}")
        except Exception as e:
            logger.error(f"Preview download failed for job {job_id}: {e}", exc_info=True)
            try:
                await session.execute(
                    update(DubbingJob)
                    .where(DubbingJob.id == job_id)
                    .values(status="error", progress=0, error=str(e))
                )
                await session.commit()
            except Exception:
                logger.exception("Could not persist preview error state for job %s", job_id)


@router.post("/start", response_model=DubbingResponse)
async def start_dubbing(req: DubbingRequest, session: AsyncSession = Depends(get_session)):
    subtitle_cfg = _map_subtitle_config(req.subtitle_config)

    audio_cfg = {}
    if req.dubbing_volume is not None:
        audio_cfg["dubbing_volume"] = req.dubbing_volume
    if req.background_volume is not None:
        audio_cfg["background_volume"] = req.background_volume
    if req.original_vocals_volume is not None:
        audio_cfg["original_vocals_volume"] = req.original_vocals_volume
    audio_cfg = audio_cfg if audio_cfg else None

    # Resume the preview job when the frontend already downloaded the video.
    if req.job_id:
        result = await session.execute(
            select(DubbingJob).where(DubbingJob.id == req.job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status not in ("preview_ready", "error"):
            raise HTTPException(status_code=400, detail=f"Job cannot be started (status: {job.status})")

        update_values = dict(
            source_lang=req.source_lang,
            target_lang=req.target_lang,
            voice=req.voice,
            whisper_model=req.whisper_model,
            status="processing",
            progress=0,
            subtitle_config=json.dumps(subtitle_cfg) if subtitle_cfg else None,
            processing_config=_build_processing_config(
                req.source_lang, req.target_lang, req.voice, req.whisper_model,
                req.tts_speed, subtitle_cfg, audio_cfg,
            ),
        )
        await session.execute(
            update(DubbingJob)
            .where(DubbingJob.id == req.job_id)
            .values(**update_values)
        )
        await session.commit()
        await session.refresh(job)
        translation_config = await load_translation_config(session)

        asyncio.create_task(
            run_pipeline_background(
                req.job_id, req.url, req.source_lang, req.target_lang,
                req.voice, req.whisper_model, req.tts_speed,
                subtitle_config=subtitle_cfg,
                audio_config=audio_cfg,
                translation_config=translation_config,
            )
        )
        return DubbingResponse.from_orm(job)

    job_id = str(uuid.uuid4())[:12]
    job = DubbingJob(
        id=job_id,
        url=req.url,
        source_lang=req.source_lang,
        target_lang=req.target_lang,
        voice=req.voice,
        whisper_model=req.whisper_model,
        status="pending",
        progress=0,
        subtitle_config=json.dumps(subtitle_cfg) if subtitle_cfg else None,
        processing_config=_build_processing_config(
            req.source_lang, req.target_lang, req.voice, req.whisper_model,
            req.tts_speed, subtitle_cfg, audio_cfg,
        ),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    translation_config = await load_translation_config(session)

    asyncio.create_task(
        run_pipeline_background(
            job_id, req.url, req.source_lang, req.target_lang,
            req.voice, req.whisper_model, req.tts_speed,
            subtitle_config=subtitle_cfg,
            audio_config=audio_cfg,
            translation_config=translation_config,
        )
    )

    return DubbingResponse.from_orm(job)


async def run_pipeline_background(job_id: str, url: str, source_lang: str,
                                   target_lang: str, voice: str, whisper_model: str,
                                   tts_speed: float = 1.0, subtitle_config: Optional[dict] = None,
                                   audio_config: Optional[dict] = None,
                                   translation_config: Optional[TranslationConfig] = None):
    """Run pipeline in background with a new database session."""
    from app.models.database import async_session
    from app.core.pipeline import run_pipeline

    logger.info(f"Starting background pipeline for job {job_id}")
    async with async_session() as session:
        try:
            await run_pipeline(job_id, url, source_lang, target_lang,
                               voice, whisper_model, tts_speed, session,
                               subtitle_config=subtitle_config,
                               audio_config=audio_config,
                               translation_config=translation_config)
            logger.info(f"Pipeline completed for job {job_id}")
        except Exception as e:
            logger.error(f"Pipeline failed for job {job_id}: {e}", exc_info=True)
            # run_pipeline normally persists its own error. Repeat it here so
            # catastrophic failures cannot leave the UI polling forever.
            try:
                await session.execute(
                    update(DubbingJob)
                    .where(DubbingJob.id == job_id)
                    .values(status="error", progress=0, error=str(e))
                )
                await session.commit()
            except Exception:
                logger.exception("Could not persist pipeline error state for job %s", job_id)


@router.post("/{job_id}/retry", response_model=DubbingResponse)
async def retry_dubbing(job_id: str, session: AsyncSession = Depends(get_session)):
    """Restart a failed job with the exact options used by its last run."""
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "error":
        raise HTTPException(status_code=400, detail=f"Job cannot be retried (status: {job.status})")

    processing_config = {}
    if job.processing_config:
        try:
            processing_config = json.loads(job.processing_config)
        except (TypeError, json.JSONDecodeError):
            logger.warning("Invalid processing config for job %s; using stored fields", job_id)

    subtitle_config = processing_config.get("subtitle_config")
    if subtitle_config is None and job.subtitle_config:
        try:
            subtitle_config = json.loads(job.subtitle_config)
        except (TypeError, json.JSONDecodeError):
            subtitle_config = None

    source_lang = processing_config.get("source_lang") or job.source_lang
    target_lang = processing_config.get("target_lang") or job.target_lang
    voice = processing_config.get("voice") or job.voice
    whisper_model = processing_config.get("whisper_model") or job.whisper_model
    try:
        tts_speed = float(processing_config.get("tts_speed", 1.0))
    except (TypeError, ValueError):
        tts_speed = 1.0
    audio_config = processing_config.get("audio_config")

    await session.execute(
        update(DubbingJob)
        .where(DubbingJob.id == job_id)
        .values(
            source_lang=source_lang,
            target_lang=target_lang,
            voice=voice,
            whisper_model=whisper_model,
            status="processing",
            progress=0,
            error=None,
            subtitle_config=json.dumps(subtitle_config) if subtitle_config else None,
            processing_config=_build_processing_config(
                source_lang, target_lang, voice, whisper_model, tts_speed,
                subtitle_config, audio_config,
            ),
        )
    )
    await session.commit()
    await session.refresh(job)
    translation_config = await load_translation_config(session)

    asyncio.create_task(
        run_pipeline_background(
            job_id, job.url, source_lang, target_lang, voice, whisper_model,
            tts_speed, subtitle_config=subtitle_config, audio_config=audio_config,
            translation_config=translation_config,
        )
    )
    return DubbingResponse.from_orm(job)


@router.get("/{job_id}/status", response_model=DubbingResponse)
async def get_status(job_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return DubbingResponse.from_orm(job)


@router.get("/{job_id}/preview-url")
async def get_preview_url(job_id: str, session: AsyncSession = Depends(get_session)):
    """Get the preview video URL for a downloaded video."""
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    file_path = resolve_data_path(job.video_path)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Preview video not ready yet")

    return FileResponse(
        file_path,
        media_type="video/mp4",
    )


@router.get("/{job_id}/download")
async def download_result(job_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed" or not job.result_path:
        raise HTTPException(status_code=400, detail=f"Job not completed (status: {job.status})")

    # Resolve old relative rows against the persistent app data directory.
    file_path = resolve_data_path(job.result_path)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found at: {file_path}")

    return FileResponse(
        file_path,
        filename=f"{job.title or job_id}_dubbed.mp4",
        media_type="video/mp4",
    )


@router.get("/{job_id}/download-original")
async def download_original(job_id: str, session: AsyncSession = Depends(get_session)):
    """Download the original video (preview) for a job."""
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.video_path:
        raise HTTPException(status_code=404, detail="Original video not available")

    # Resolve old relative rows against the persistent app data directory.
    file_path = resolve_data_path(job.video_path)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Original video file not found at: {file_path}")

    return FileResponse(
        file_path,
        filename=f"{job.title or job_id}_original.mp4",
        media_type="video/mp4",
    )


@router.get("/{job_id}/thumbnail")
async def get_thumbnail(job_id: str, session: AsyncSession = Depends(get_session)):
    """Get video thumbnail for a job."""
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Try thumbnail_path first, then result_path for fallback
    thumb_path = resolve_data_path(job.thumbnail_path)

    if not thumb_path or not os.path.exists(thumb_path):
        # Return a placeholder or 404
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    return FileResponse(
        thumb_path,
        media_type="image/jpeg",
    )


@router.post("/{job_id}/cancel")
async def cancel_dubbing(job_id: str, session: AsyncSession = Depends(get_session)):
    # Check if job exists and is still running
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ["completed", "error", "cancelled"]:
        return {"status": "already_finished", "job_status": job.status}

    # Update status to cancelled
    await session.execute(
        update(DubbingJob)
        .where(DubbingJob.id == job_id)
        .values(status="cancelled")
    )
    await session.commit()

    return {"status": "cancelled"}


@router.get("/{job_id}/debug")
async def debug_job(job_id: str, session: AsyncSession = Depends(get_session)):
    """Debug endpoint to check job details and file existence."""
    import os
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    file_path = resolve_data_path(job.result_path)

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "result_path_db": job.result_path,
        "result_path_resolved": file_path,
        "file_exists": os.path.exists(file_path) if file_path else False,
        "cwd": os.getcwd(),
        "error": job.error,
        "file_size": job.file_size,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }