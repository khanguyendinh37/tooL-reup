from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, desc

from app.models.database import get_session, DubbingJob
from app.schemas.dubbing import DubbingResponse

router = APIRouter()


@router.get("", response_model=list[DubbingResponse])
async def list_history(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DubbingJob).order_by(desc(DubbingJob.created_at))
    )
    jobs = result.scalars().all()
    return [DubbingResponse.from_orm(j) for j in jobs]


@router.get("/{job_id}", response_model=DubbingResponse)
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return DubbingResponse.from_orm(job)


@router.delete("/{job_id}")
async def delete_job(job_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DubbingJob).where(DubbingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    import shutil
    import os
    job_dir = os.path.join("output", job_id)
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir, ignore_errors=True)

    await session.execute(delete(DubbingJob).where(DubbingJob.id == job_id))
    await session.commit()

    return {"status": "deleted"}
