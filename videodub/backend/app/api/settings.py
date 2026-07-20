from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.models.database import get_session, AppSettings

router = APIRouter()

DEFAULT_SETTINGS = {
    "whisper_model": "small",
    "default_target_lang": "vi",
    "default_voice": "vi-VN-HoaiMyNeural",
    "tts_speed": "1.0",
}


class SettingsUpdate(BaseModel):
    whisper_model: Optional[str] = None
    default_target_lang: Optional[str] = None
    default_voice: Optional[str] = None
    tts_speed: Optional[float] = None


@router.get("")
async def get_settings(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AppSettings))
    rows = result.scalars().all()

    settings = {row.key: row.value for row in rows}

    for key, default_val in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = default_val

    return settings


@router.put("")
async def update_settings(update: SettingsUpdate, session: AsyncSession = Depends(get_session)):
    updates = update.model_dump(exclude_none=True)

    for key, value in updates.items():
        result = await session.execute(
            select(AppSettings).where(AppSettings.key == key)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = str(value)
        else:
            session.add(AppSettings(key=key, value=str(value)))

    await session.commit()
    return {"status": "updated"}
