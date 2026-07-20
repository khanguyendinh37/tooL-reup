from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class FontPreset(BaseModel):
    """Font preset for CapCut-style animated subtitles"""
    id: str
    name: str
    description: str
    font_family: str
    font_size: int
    font_color: str
    outline_color: str
    outline_width: int
    shadow_enabled: bool
    shadow_color: str
    shadow_offset_x: int
    shadow_offset_y: int
    # Animation style
    animation: Optional[str] = None  # 'karaoke', 'typewriter', 'fade', 'pop', 'shake', 'wave'
    animation_speed: float = 1.0
    # Preview image (base64 or URL)
    preview_url: Optional[str] = None


# Default CapCut-style font presets
DEFAULT_FONT_PRESETS: List[FontPreset] = [
    FontPreset(
        id='default',
        name='Mặc định',
        description='Phụ đề tiêu chuẩn',
        font_family='Arial',
        font_size=24,
        font_color='#FFFFFF',
        outline_color='#000000',
        outline_width=2,
        shadow_enabled=True,
        shadow_color='#000000',
        shadow_offset_x=2,
        shadow_offset_y=2,
    ),
    FontPreset(
        id='karaoke',
        name='Karaoke',
        description='Màu vàng viền đỏ, kiểu karaoke',
        font_family='Arial',
        font_size=32,
        font_color='#FFFF00',
        outline_color='#FF0000',
        outline_width=3,
        shadow_enabled=True,
        shadow_color='#000000',
        shadow_offset_x=3,
        shadow_offset_y=3,
        animation='karaoke',
    ),
    FontPreset(
        id='tiktok_viral',
        name='TikTok Viral',
        description='Font to, bo tròn, màu trắng viền đen',
        font_family='Montserrat',
        font_size=40,
        font_color='#FFFFFF',
        outline_color='#000000',
        outline_width=4,
        shadow_enabled=False,
        shadow_color='#000000',
        shadow_offset_x=0,
        shadow_offset_y=0,
        animation='pop',
    ),
    FontPreset(
        id='cinematic',
        name='Sinematic',
        description='Font mỏng, chữ trắng, viền đen mịn',
        font_family='Cinzel',
        font_size=28,
        font_color='#FFFFFF',
        outline_color='#000000',
        outline_width=1,
        shadow_enabled=True,
        shadow_color='#000000',
        shadow_offset_x=2,
        shadow_offset_y=2,
        animation='fade',
    ),
    FontPreset(
        id='neon',
        name='Neon',
        description='Màu neon sáng, viền phát sáng',
        font_family='Orbitron',
        font_size=30,
        font_color='#00FFFF',
        outline_color='#FF00FF',
        outline_width=2,
        shadow_enabled=True,
        shadow_color='#FF00FF',
        shadow_offset_x=0,
        shadow_offset_y=0,
        animation='wave',
    ),
    FontPreset(
        id='typewriter',
        name='Máy đánh chữ',
        description='Font monospace, hiệu ứng gõ chữ',
        font_family='Courier New',
        font_size=26,
        font_color='#00FF00',
        outline_color='#000000',
        outline_width=1,
        shadow_enabled=True,
        shadow_color='#003300',
        shadow_offset_x=1,
        shadow_offset_y=1,
        animation='typewriter',
    ),
    FontPreset(
        id='bold_impact',
        name='Impact Bold',
        description='Font đậm, to, dùng cho meme/video ngắn',
        font_family='Impact',
        font_size=48,
        font_color='#FFFFFF',
        outline_color='#000000',
        outline_width=5,
        shadow_enabled=False,
        shadow_color='#000000',
        shadow_offset_x=0,
        shadow_offset_y=0,
        animation='pop',
    ),
    FontPreset(
        id='elegant',
        name='Sang trọng',
        description='Font serif, vàng nhạt, viền nâu',
        font_family='Georgia',
        font_size=30,
        font_color='#FFD700',
        outline_color='#8B4513',
        outline_width=2,
        shadow_enabled=True,
        shadow_color='#4A2C00',
        shadow_offset_x=2,
        shadow_offset_y=2,
        animation='fade',
    ),
]


class TextOverlay(BaseModel):
    """Custom text overlay"""
    id: str
    text: str
    font_family: str = "Arial"
    font_size: int = 24
    font_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: int = 2
    shadow_enabled: bool = True
    shadow_color: str = "#000000"
    shadow_offset_x: int = 2
    shadow_offset_y: int = 2
    # Position (0-1 relative to video)
    x: float = 0.5
    y: float = 0.1
    # Animation
    animation: Optional[str] = None
    animation_speed: float = 1.0
    # Timing (optional - for timed overlays)
    start_time: Optional[float] = None  # seconds
    end_time: Optional[float] = None    # seconds


class ImageOverlay(BaseModel):
    """Image/logo overlay"""
    id: str
    # Image data (base64) or URL
    image_data: Optional[str] = None
    image_url: Optional[str] = None
    # Position (0-1 relative to video)
    x: float = 0.9
    y: float = 0.1
    # Size (0-1 relative to video width)
    scale: float = 0.15
    # Opacity (0-1)
    opacity: float = 1.0
    # Rotation (degrees)
    rotation: float = 0.0
    # Timing
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class SubtitleConfig(BaseModel):
    enabled: bool = True
    # Font settings
    font_family: str = "Arial"
    font_size: int = 24
    font_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: int = 2
    shadow_enabled: bool = True
    shadow_color: str = "#000000"
    shadow_offset_x: int = 2
    shadow_offset_y: int = 2
    position: str = "bottom"  # top, center, bottom
    margin_v: int = 40
    margin_l: int = 20
    margin_r: int = 20
    alignment: int = 2
    custom_x: Optional[float] = None
    custom_y: Optional[float] = None
    use_custom_position: bool = False
    # Animation
    animation: Optional[str] = None
    animation_speed: float = 1.0
    # Font preset
    font_preset_id: Optional[str] = None
    # Text overlays
    text_overlays: List[TextOverlay] = []
    # Image overlays (logos, watermarks)
    image_overlays: List[ImageOverlay] = []
    # Video aspect ratio
    aspect_ratio: str = "16:9"  # "16:9", "9:16", "1:1", "4:5", "4:3"


class DubbingRequest(BaseModel):
    url: str
    source_lang: str
    target_lang: str
    voice: str
    whisper_model: str = "small"
    tts_speed: float = 1.0
    subtitle_config: Optional[SubtitleConfig] = None


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
    # Default subtitle config
    default_subtitle_config: Optional[SubtitleConfig] = None