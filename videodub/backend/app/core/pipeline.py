import asyncio
import os
import subprocess
import json
import base64
import tempfile
from datetime import datetime
from sqlalchemy import update

from app.core.downloader import download_video, get_video_duration
from app.core.transcriber import extract_audio, transcribe_with_whisper, segments_to_srt
from app.core.translator import translate_srt_deep_translator, srt_to_segments
from app.core.tts_engine import generate_dubbing_audio, merge_tts_segments
from app.core.vocal_remover import separate_vocals

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import DubbingJob


def speed_to_rate(speed: float) -> str:
    """Convert speed multiplier (0.5-2.0) to rate string for TTS engine."""
    if speed == 1.0:
        return "+0%"
    # Convert to percentage: 1.5 -> +50%, 0.8 -> -20%
    pct = (speed - 1.0) * 100
    return f"{pct:+.0f}%"


def hex_to_ass(hex_color: str) -> str:
    """Convert #RRGGBB to BBGGRR hex (ASS format for force_style)"""
    if not hex_color or not hex_color.startswith('#'):
        return 'FFFFFF'  # Default white
    hex_clean = hex_color.lstrip('#')
    if len(hex_clean) == 6:
        r, g, b = hex_clean[0:2], hex_clean[2:4], hex_clean[4:6]
        return f'{b}{g}{r}'
    return 'FFFFFF'


def get_video_dimensions(aspect_ratio: str, base_width: int = 1920) -> tuple[int, int]:
    """Get video dimensions based on aspect ratio."""
    ratios = {
        "16:9": (1920, 1080),
        "9:16": (1080, 1920),
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
        "4:3": (1440, 1080),
        "21:9": (2560, 1080),
    }
    return ratios.get(aspect_ratio, (1920, 1080))


def build_subtitle_filter(subtitle_config: dict) -> str:
    """
    Build FFmpeg subtitles filter with customizable styling.

    subtitle_config keys (API format):
    - font_family: Font name (e.g., 'Arial', 'DejaVu Sans')
    - font_size: Font size in points
    - font_color: Hex color (e.g., '#FFFFFF' for white)
    - outline_color: Hex color for outline (e.g., '#000000' for black)
    - outline_width: Outline width in pixels
    - shadow_enabled: Whether shadow is enabled
    - shadow_color: Hex color for shadow
    - shadow_offset_x: Shadow X offset
    - shadow_offset_y: Shadow Y offset
    """
    srt_path = subtitle_config.get('srt_path', '')
    if not srt_path:
        return ''

    # Escape path for FFmpeg subtitles filter - Windows needs special handling
    # Use forward slashes and escape colons
    escaped_path = srt_path.replace('\\', '/').replace(':', '\\:')

    # Default values - API format
    font = subtitle_config.get('font_family', 'DejaVu Sans')
    font_size = subtitle_config.get('font_size', 24)
    font_color = hex_to_ass(subtitle_config.get('font_color', '#FFFFFF'))
    outline_color = hex_to_ass(subtitle_config.get('outline_color', '#000000'))
    outline_width = subtitle_config.get('outline_width', 2)

    # Shadow
    shadow_enabled = subtitle_config.get('shadow_enabled', True)
    if shadow_enabled:
        shadow_color = hex_to_ass(subtitle_config.get('shadow_color', '#000000'))
        shadow_offset = subtitle_config.get('shadow_offset_x', 2)  # Use single offset value
    else:
        shadow_color = '000000'
        shadow_offset = 0

    # Build force_style for ASS subtitles - MUST be a single string, not a tuple!
    # Valid force_style options for libass: FontName, FontSize, PrimaryColour, OutlineColour,
    # Outline, Shadow, Alignment, MarginV, MarginL, MarginR, Bold, Italic, Underline, StrikeOut
    force_style_parts = [
        f"FontName={font}",
        f"FontSize={font_size}",
        f"PrimaryColour={font_color}",
        f"OutlineColour={outline_color}",
        f"Outline={outline_width}",
    ]

    if shadow_enabled and shadow_offset > 0:
        force_style_parts.append(f"Shadow={shadow_offset}")
        force_style_parts.append(f"ShadowColour={shadow_color}")

    # Add alignment and margins if provided
    alignment = subtitle_config.get('alignment', 2)
    margin_v = subtitle_config.get('margin_v', 40)
    margin_l = subtitle_config.get('margin_l', 20)
    margin_r = subtitle_config.get('margin_r', 20)

    force_style_parts.extend([
        f"Alignment={alignment}",
        f"MarginV={margin_v}",
        f"MarginL={margin_l}",
        f"MarginR={margin_r}",
    ])

    force_style = ",".join(force_style_parts)

    # Return filter string with force_style wrapped in single quotes for proper parsing
    return f"subtitles={escaped_path}:force_style='{force_style}'"


def build_overlay_filters(subtitle_config: dict, video_width: int, video_height: int) -> list[str]:
    """
    Build FFmpeg overlay filters for text and image overlays.
    Returns list of filter strings.
    """
    filters = []
    overlay_idx = 0

    # Text overlays
    for text_overlay in subtitle_config.get('text_overlays', []):
        if not text_overlay.get('text', '').strip():
            continue

        text = text_overlay['text'].replace("'", "\\'").replace(":", "\\:")
        font = text_overlay.get('font_family', 'Arial')
        font_size = text_overlay.get('font_size', 24)
        font_color = text_overlay.get('font_color', '#FFFFFF')
        outline_color = text_overlay.get('outline_color', '#000000')
        outline_width = text_overlay.get('outline_width', 2)
        shadow_enabled = text_overlay.get('shadow_enabled', True)
        shadow_color = text_overlay.get('shadow_color', '#000000')
        shadow_offset_x = text_overlay.get('shadow_offset_x', 2)
        shadow_offset_y = text_overlay.get('shadow_offset_y', 2)

        # Calculate position in pixels
        x = text_overlay.get('x', 0.5)
        y = text_overlay.get('y', 0.1)
        x_px = int(x * video_width)
        y_px = int(y * video_height)

        # Build drawtext filter
        # Convert colors to ASS format (BBGGRR)
        font_color_ass = hex_to_ass(font_color)
        outline_color_ass = hex_to_ass(outline_color)
        shadow_color_ass = hex_to_ass(shadow_color)

        # drawtext with box for background-like effect
        drawtext = (
            f"drawtext="
            f"text='{text}':"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"fontcolor={font_color_ass}:"
            f"fontsize={font_size}:"
            f"x={x_px}:"
            f"y={y_px}:"
        )

        if outline_width > 0:
            drawtext += f"borderw={outline_width}:bordercolor={outline_color_ass}:"

        if shadow_enabled:
            drawtext += f"shadowx={shadow_offset_x}:shadowy={shadow_offset_y}:shadowcolor={shadow_color_ass}:"

        drawtext += "font='Arial'"

        filters.append(f"[v{overlay_idx}]{drawtext}[v{overlay_idx + 1}]")
        overlay_idx += 1

    # Image overlays (logos, watermarks)
    for img_overlay in subtitle_config.get('image_overlays', []):
        image_data = img_overlay.get('image_data')
        image_url = img_overlay.get('image_url')

        if not image_data and not image_url:
            continue

        # Save base64 image to temp file if needed
        if image_data:
            # Remove data URL prefix if present
            if image_data.startswith('data:'):
                image_data = image_data.split(',', 1)[1]
            try:
                img_bytes = base64.b64decode(image_data)
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                    f.write(img_bytes)
                    img_path = f.name
            except Exception:
                continue
        else:
            img_path = image_url

        # Calculate position and size
        x = img_overlay.get('x', 0.9)
        y = img_overlay.get('y', 0.1)
        scale = img_overlay.get('scale', 0.15)
        opacity = img_overlay.get('opacity', 1.0)
        rotation = img_overlay.get('rotation', 0.0)

        x_px = int(x * video_width)
        y_px = int(y * video_height)

        # Build overlay filter
        # Use scale relative to video width
        overlay_filter = (
            f"movie={img_path}:loop=0,"
            f"scale={int(video_width * scale)}:-1,"
            f"rotate={rotation}*PI/180,"
            f"format=rgba,"
            f"colorchannelmixer=aa={opacity}"
            f"[logo{overlay_idx}];"
        )
        filters.append(overlay_filter)

        # Overlay onto video
        filters.append(
            f"[v{overlay_idx}][logo{overlay_idx}]overlay={x_px}:{y_px}[v{overlay_idx + 1}]"
        )
        overlay_idx += 1

    return filters


async def run_pipeline(job_id: str, url: str, source_lang: str,
                        target_lang: str, voice: str, whisper_model: str,
                        tts_speed: float, session: AsyncSession,
                        subtitle_config: dict = None):
    job_dir = os.path.join("output", job_id)
    os.makedirs(job_dir, exist_ok=True)
    temp_dir = os.path.join("temp", job_id)
    os.makedirs(temp_dir, exist_ok=True)

    # Convert Pydantic model to dict if needed
    if subtitle_config is not None and hasattr(subtitle_config, 'model_dump'):
        subtitle_config = subtitle_config.model_dump()

    # Default subtitle config
    if subtitle_config is None:
        subtitle_config = {}

    # Enable subtitles by default if translated SRT exists
    subtitle_config.setdefault('enabled', True)
    subtitle_config.setdefault('srt_path', os.path.join(job_dir, "translated.srt"))

    # Get aspect ratio for overlay positioning
    aspect_ratio = subtitle_config.get('aspect_ratio', '16:9')
    video_width, video_height = get_video_dimensions(aspect_ratio)

    try:
        await update_job(session, job_id, "downloading", 0)
        video_info = await download_video(url, temp_dir)
        video_path = video_info["video_path"]
        title = video_info.get("title", "Unknown")
        thumbnail_path = video_info.get("thumbnail_path")
        await update_job_field(session, job_id, "title", title)
        if thumbnail_path and os.path.exists(thumbnail_path):
            # Copy thumbnail to job output dir for persistence
            import shutil
            thumb_dest = os.path.join(job_dir, "thumbnail.jpg")
            shutil.copy2(thumbnail_path, thumb_dest)
            await update_job_field(session, job_id, "thumbnail_path", thumb_dest)
        await update_job(session, job_id, "downloading", 100)

        await update_job(session, job_id, "transcribing", 0)
        audio_path = os.path.join(temp_dir, "audio.wav")
        extract_audio(video_path, audio_path)
        await update_job(session, job_id, "transcribing", 50)

        result = transcribe_with_whisper(audio_path, whisper_model, source_lang)
        original_srt = os.path.join(job_dir, "original.srt")
        segments_to_srt(result["segments"], original_srt)
        await update_job(session, job_id, "transcribing", 100)

        await update_job(session, job_id, "translating", 0)
        translated_srt = os.path.join(job_dir, "translated.srt")
        translate_srt_deep_translator(original_srt, target_lang, translated_srt)
        await update_job(session, job_id, "translating", 100)

        await update_job(session, job_id, "tts", 0)
        translated_segments = srt_to_segments(translated_srt)
        tts_dir = os.path.join(job_dir, "tts")
        rate = speed_to_rate(tts_speed)
        audio_files = await generate_dubbing_audio(
            translated_segments, voice, tts_dir, rate
        )
        await update_job(session, job_id, "tts", 50)

        total_duration = video_info.get("duration", 0)
        if total_duration == 0:
            total_duration = get_video_duration(video_path)

        dubbed_audio = os.path.join(job_dir, "dubbed_audio.wav")
        merge_tts_segments(audio_files, total_duration, dubbed_audio)
        await update_job(session, job_id, "tts", 100)

        await update_job(session, job_id, "removing_vocals", 0)
        vocal_result = separate_vocals(video_path, job_dir)
        no_vocals = vocal_result.get("no_vocals")
        await update_job(session, job_id, "removing_vocals", 100)

        await update_job(session, job_id, "merging", 0)
        final_output = os.path.join(job_dir, f"{job_id}_dubbed.mp4")

        # Build filter complex for audio mixing
        if no_vocals and os.path.exists(no_vocals):
            # Normalize and boost dubbed audio volume before mixing
            boosted_dubbed = os.path.join(job_dir, "dubbed_audio_boosted.wav")
            subprocess.run([
                "ffmpeg", "-i", dubbed_audio,
                "-af", "volume=4.0,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-ar", "44100", "-y", boosted_dubbed
            ], capture_output=True, check=True)

            # Also normalize the background (no_vocals) to consistent level
            normalized_bg = os.path.join(job_dir, "no_vocals_normalized.wav")
            subprocess.run([
                "ffmpeg", "-i", no_vocals,
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-ar", "44100", "-y", normalized_bg
            ], capture_output=True, check=True)

            # Mix: background at normal level, dubbed at boosted level
            merged_audio = os.path.join(job_dir, "final_audio.wav")
            subprocess.run([
                "ffmpeg", "-i", normalized_bg, "-i", boosted_dubbed,
                "-filter_complex",
                "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0,volume=1.2[out]",
                "-map", "[out]", "-ar", "44100", "-y", merged_audio
            ], capture_output=True, check=True)

            # Build complete filter graph with subtitles + overlays
            filter_parts = []
            video_input_idx = 0
            audio_input_idx = 1

            # Start with video
            current_video = f"{video_input_idx}:v"

            # Add subtitles if enabled
            if subtitle_config.get('enabled') and os.path.exists(subtitle_config['srt_path']):
                subtitle_filter = build_subtitle_filter(subtitle_config)
                if subtitle_filter:
                    filter_parts.append(f"[{current_video}]{subtitle_filter}[v_subs]")
                    current_video = "[v_subs]"

            # Add text/image overlays
            overlay_filters = build_overlay_filters(subtitle_config, video_width, video_height)
            for i, of in enumerate(overlay_filters):
                if i == 0:
                    filter_parts.append(f"[{current_video}]{of}")
                else:
                    filter_parts.append(of)
                # Update current_video to the last output
                if 'overlay' in of or 'drawtext' in of:
                    # Extract output label
                    parts = of.split(']')
                    if len(parts) > 1:
                        current_video = parts[-1].strip() + ']'

            # If we have video filters, combine with audio
            if filter_parts:
                # Build the full filter complex
                filter_complex = ";".join(filter_parts)

                # Get final video label
                final_video_label = current_video
                if not final_video_label.startswith('['):
                    final_video_label = "[v_final]"

                cmd = [
                    "ffmpeg", "-i", video_path, "-i", merged_audio,
                    "-filter_complex", filter_complex,
                    "-map", final_video_label, "-map", f"{audio_input_idx}:a",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-shortest", "-y", final_output
                ]
            else:
                # No video filters, just combine
                subprocess.run([
                    "ffmpeg", "-i", video_path, "-i", merged_audio,
                    "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest", "-y", final_output
                ], capture_output=True, check=True)
        else:
            # No vocals removed - just boost and normalize the dubbed audio
            boosted_dubbed = os.path.join(job_dir, "dubbed_audio_boosted.wav")
            subprocess.run([
                "ffmpeg", "-i", dubbed_audio,
                "-af", "volume=4.0,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-ar", "44100", "-y", boosted_dubbed
            ], capture_output=True, check=True)

            # Build filter graph for subtitles + overlays
            filter_parts = []
            current_video = "0:v"

            # Add subtitles if enabled
            if subtitle_config.get('enabled') and os.path.exists(subtitle_config['srt_path']):
                subtitle_filter = build_subtitle_filter(subtitle_config)
                if subtitle_filter:
                    filter_parts.append(f"[{current_video}]{subtitle_filter}[v_subs]")
                    current_video = "[v_subs]"

            # Add text/image overlays
            overlay_filters = build_overlay_filters(subtitle_config, video_width, video_height)
            for i, of in enumerate(overlay_filters):
                if i == 0:
                    filter_parts.append(f"[{current_video}]{of}")
                else:
                    filter_parts.append(of)
                if 'overlay' in of or 'drawtext' in of:
                    parts = of.split(']')
                    if len(parts) > 1:
                        current_video = parts[-1].strip() + ']'

            if filter_parts:
                filter_complex = ";".join(filter_parts)
                final_video_label = current_video
                if not final_video_label.startswith('['):
                    final_video_label = "[v_final]"

                subprocess.run([
                    "ffmpeg", "-i", video_path, "-i", boosted_dubbed,
                    "-filter_complex", filter_complex,
                    "-map", final_video_label, "-map", "1:a",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-shortest", "-y", final_output
                ], capture_output=True, check=True)
            else:
                subprocess.run([
                    "ffmpeg", "-i", video_path, "-i", boosted_dubbed,
                    "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest", "-y", final_output
                ], capture_output=True, check=True)

        await update_job(session, job_id, "merging", 100)

        file_size = os.path.getsize(final_output) if os.path.exists(final_output) else 0
        size_str = f"{file_size / (1024*1024):.1f} MB"

        await update_job_field(session, job_id, "result_path", final_output)
        await update_job_field(session, job_id, "file_size", size_str)
        await update_job(session, job_id, "completed", 100)

    except asyncio.CancelledError:
        await update_job(session, job_id, "cancelled", 0)
        raise
    except Exception as e:
        await update_job(session, job_id, "error", 0)
        await update_job_field(session, job_id, "error", str(e))
        raise
    finally:
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


async def update_job(session: AsyncSession, job_id: str, status: str, progress: int):
    await session.execute(
        update(DubbingJob)
        .where(DubbingJob.id == job_id)
        .values(status=status, progress=progress, updated_at=datetime.utcnow())
    )
    await session.commit()


async def update_job_field(session: AsyncSession, job_id: str, field: str, value):
    await session.execute(
        update(DubbingJob)
        .where(DubbingJob.id == job_id)
        .values(**{field: value, "updated_at": datetime.utcnow()})
    )
    await session.commit()