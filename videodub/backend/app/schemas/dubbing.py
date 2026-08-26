from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PreviewRequest(BaseModel):
    url: str
    source_lang: Optional[str] = "en"
    target_lang: Optional[str] = "vi"
    voice: Optional[str] = "vi-VN-HoaiMyNeural"
    whisper_model: Optional[str] = "small"


class DubbingRequest(BaseModel):
    url: str
    source_lang: str
    target_lang: str
    voice: str
    whisper_model: str = "small"
    tts_speed: float = 1.0
    job_id: Optional[str] = None  # Resume from preview phase
    subtitle_config: Optional[dict] = None  # Subtitle burning config
    dubbing_volume: Optional[float] = None  # TTS dubbing volume
    background_volume: Optional[float] = None  # Background audio volume
    original_vocals_volume: Optional[float] = None  # Original vocals volume


class DubbingResponse(BaseModel):
    id: str
    url: str
    title: Optional[str] = None
    source_lang: str
    target_lang: str
    voice: str
    whisper_model: str
    status: str
    progress: int
    error: Optional[str] = None
    result_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    processing_config: Optional[str] = None
    duration: Optional[str] = None
    file_size: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    whisper_model: Optional[str] = None
    default_target_lang: Optional[str] = None
    default_voice: Optional[str] = None
    tts_speed: Optional[float] = None