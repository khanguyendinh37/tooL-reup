import uuid
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import os

from app.models.database import get_session, DubbingJob
from app.schemas.dubbing import DubbingRequest, DubbingResponse
from app.core.pipeline import run_pipeline

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/start", response_model=DubbingResponse)
async def start_dubbing(req: DubbingRequest, session: AsyncSession = Depends(get_session)):
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
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Run pipeline in background task
    asyncio.create_task(
        run_pipeline_background(job_id, req.url, req.source_lang, req.target_lang,
                                req.voice, req.whisper_model, req.tts_speed, req.subtitle_config)
    )

    return DubbingResponse.from_orm(job)


async def run_pipeline_background(job_id: str, url: str, source_lang: str,
                                   target_lang: str, voice: str, whisper_model: str,
                                   tts_speed: float = 1.0, subtitle_config: dict = None):
    """Run pipeline in background with a new database session."""
    from app.models.database import async_session
    from app.core.pipeline import run_pipeline

    logger.info(f"Starting background pipeline for job {job_id}")
    async with async_session() as session:
        try:
            await run_pipeline(job_id, url, source_lang, target_lang,
                               voice, whisper_model, tts_speed, session, subtitle_config)
            logger.info(f"Pipeline completed for job {job_id}")
        except Exception as e:
            logger.error(f"Pipeline failed for job {job_id}: {e}", exc_info=True)
            # Error is already handled in run_pipeline
            pass


@router.get("/{job_id}/status", response_model=DubbingResponse)
async def get_status(job_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return DubbingResponse.from_orm(job)


@router.get("/{job_id}/download")
async def download_result(job_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed" or not job.result_path:
        raise HTTPException(status_code=400, detail="Job not completed")
    if not os.path.exists(job.result_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        job.result_path,
        filename=f"{job.title or job_id}_dubbed.mp4",
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
    thumb_path = job.thumbnail_path

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