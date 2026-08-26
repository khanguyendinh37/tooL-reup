import asyncio
import os
import subprocess
import logging
import time
from datetime import datetime
from sqlalchemy import update
from typing import Optional

logger = logging.getLogger(__name__)

# The old SRT path depended on libass's default 384x288 script canvas. New
# ASS files use the actual video frame as their canvas; this reference height
# only keeps the existing compact subtitle size consistent across resolutions.
ASS_REFERENCE_PLAYRES_HEIGHT = 288

from app.core.downloader import download_video, get_video_duration
from app.core.paths import OUTPUT_DIR, TEMP_DIR
from app.core.process_utils import hidden_subprocess_kwargs
from app.core.transcriber import extract_audio, transcribe_with_whisper, segments_to_srt
from app.core.translation_config import TranslationConfig, load_translation_config
from app.core.translator import translate_srt_deep_translator, srt_to_segments
from app.core.tts_engine import cleanup_tts_directory, generate_dubbing_audio, merge_tts_segments
from app.core.vocal_remover import separate_vocals

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import DubbingJob, async_session


def hex_to_ass(color: str, default: str = "FFFFFF") -> str:
    """Convert a CSS hex color to the BGR hex format expected by libass."""
    if not isinstance(color, str):
        return default

    value = color.strip()
    if value.startswith("#"):
        value = value[1:]
    elif value.upper().startswith("&H"):
        value = value[2:]
        # Accept ASS AARRGGBB input and discard the alpha component here.
        if len(value) == 8:
            value = value[2:]

    if len(value) == 3:
        value = "".join(char * 2 for char in value)

    if len(value) != 6 or any(char not in "0123456789abcdefABCDEF" for char in value):
        return default

    red, green, blue = value[0:2], value[2:4], value[4:6]
    return f"{blue}{green}{red}".upper()


def _escape_ffmpeg_filter_path(path: str) -> str:
    """Make a local path safe for FFmpeg's subtitle filter syntax."""
    normalized = os.path.abspath(path).replace("\\", "/")
    return normalized.replace("'", "\\'").replace(":", "\\:")


def _format_ass_timestamp(value: object) -> str:
    """Format seconds as an ASS timestamp with centisecond precision."""
    try:
        total_centiseconds = max(int(round(float(value) * 100)), 0)
    except (TypeError, ValueError):
        total_centiseconds = 0

    hours, remainder = divmod(total_centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _escape_ass_text(value: object) -> str:
    """Keep subtitle text from being interpreted as ASS override tags."""
    backslash = chr(92)
    newline = chr(10)
    text = str(value or "").replace(chr(13) + newline, newline).replace(chr(13), newline)
    text = text.replace(backslash, backslash + backslash)
    text = text.replace("{", backslash + "{").replace("}", backslash + "}")
    return text.replace(newline, backslash + "N")


def _write_positioned_ass_subtitles(
    srt_path: str,
    ass_path: str,
    video_width: int,
    video_height: int,
    font_size: int,
    outline_width: int,
    font_color: str,
    outline_color: str,
    position_y: float,
) -> str:
    """Create an ASS file whose coordinate system matches the video frame.

    The preview stores the subtitle's center as a normalized top-down value.
    ASS alignment 5 plus ``\\pos`` uses the same center anchor, so no
    resolution-dependent MarginV conversion is needed.
    """
    width = max(int(video_width), 1)
    height = max(int(video_height), 1)
    x = width // 2
    y = min(max(int(round(height * position_y)), 0), height)
    scale = height / ASS_REFERENCE_PLAYRES_HEIGHT
    ass_font_size = max(int(round(font_size * scale)), 1)
    ass_outline_width = max(int(round(outline_width * scale)), 0)

    segments = srt_to_segments(srt_path)
    dialogue_lines = []
    for segment in segments:
        text = _escape_ass_text(segment.get("text", ""))
        if not text.strip():
            continue
        start = _format_ass_timestamp(segment.get("start", 0))
        end = _format_ass_timestamp(segment.get("end", 0))
        if end == start:
            continue
        dialogue_lines.append(
            f"Dialogue: 0,{start},{end},Default,,0,0,0,,"
            f"{{\\an5\\pos({x},{y})}}{text}"
        )

    ass_content = chr(10).join([
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Arial,{ass_font_size},&H00{font_color},&H00{font_color},"
        f"&H00{outline_color},&H00000000,0,0,0,0,100,100,0,0,1,"
        f"{ass_outline_width},0,5,0,0,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *dialogue_lines,
        "",
    ])
    with open(ass_path, "w", encoding="utf-8") as ass_file:
        ass_file.write(ass_content)
    return ass_path


def _coerce_bool(value: object, default: bool = False) -> bool:
    """Parse booleans safely when configs come from JSON, forms, or the DB."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    if value is None:
        return default
    return bool(value)


def _normalize_audio_track(input_path: str, output_path: str, volume: float) -> str:
    """Normalize a track first, then apply the user's gain multiplier.

    Applying ``volume`` after ``loudnorm`` is important: applying it before
    normalization causes loudnorm to undo the user's selected level.
    """
    gain = max(float(volume), 0.0)
    subprocess.run([
        "ffmpeg", "-i", input_path,
        "-af", f"loudnorm=I=-23:TP=-2:LRA=11,volume={gain:.3f}",
        "-ar", "44100", "-ac", "2", "-y", output_path,
    ], capture_output=True, check=True, **hidden_subprocess_kwargs())
    return output_path


def _mix_audio_tracks(track_paths: list[str], output_path: str) -> str:
    """Mix already-normalized tracks without changing their relative gains."""
    if not track_paths:
        raise ValueError("No audio tracks available for mixing")

    cmd = ["ffmpeg"]
    for track_path in track_paths:
        cmd.extend(["-i", track_path])

    labels = "".join(f"[{index}:a]" for index in range(len(track_paths)))
    filter_complex = (
        f"{labels}amix=inputs={len(track_paths)}:duration=longest:"
        "dropout_transition=0:normalize=0,alimiter=limit=0.95[out]"
    )
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[out]", "-ar", "44100", "-ac", "2", "-y", output_path,
    ])
    subprocess.run(cmd, capture_output=True, check=True, **hidden_subprocess_kwargs())
    return output_path


def speed_to_rate(speed: float) -> str:
    """Convert speed multiplier (0.5-2.0) to rate string for TTS engine."""
    if speed == 1.0:
        return "+0%"
    # Convert to percentage: 1.5 -> +50%, 0.8 -> -20%
    pct = (speed - 1.0) * 100
    return f"{pct:+.0f}%"


def get_actual_video_dimensions(video_path: str) -> tuple[int, int]:
    """Probe the actual video dimensions using ffprobe."""
    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            video_path
        ], capture_output=True, text=True, timeout=30, **hidden_subprocess_kwargs())
        if result.returncode == 0:
            import json as _json
            data = _json.loads(result.stdout)
            streams = data.get("streams", [])
            if streams:
                w = streams[0].get("width", 1920)
                h = streams[0].get("height", 1080)
                logger.info(f"Probed video dimensions: {w}x{h}")
                return (w, h)
    except Exception as e:
        logger.warning(f"Failed to probe video dimensions: {e}")
    return (1920, 1080)


def burn_subtitles_with_blur_mask(
    input_video: str,
    srt_path: str,
    output_video: str,
    video_width: int,
    video_height: int,
    subtitle_config: dict
) -> bool:
    """Burn translated subtitles, optionally covering old burned-in captions."""
    if not isinstance(subtitle_config, dict) or not subtitle_config.get("enabled", False):
        return False

    if not os.path.isfile(srt_path):
        logger.warning(f"SRT file not found: {srt_path}")
        return False

    try:
        width = max(int(video_width), 1)
        height = max(int(video_height), 1)
        font_size = max(int(subtitle_config.get("font_size", 13)), 1)
        outline_width = max(int(subtitle_config.get("outline_width", 1)), 0)
        try:
            position_y = min(max(float(subtitle_config.get("position_y", 0.94)), 0.0), 1.0)
        except (TypeError, ValueError):
            position_y = 0.94
        blur_existing = _coerce_bool(
            subtitle_config.get("blur_existing_subtitles", False)
        )
        # The reference video has a large, full-width burned-caption band. Keep
        # enough vertical padding to cover glyphs above and below the new line.
        blur_height_ratio = min(
            max(float(subtitle_config.get("blur_height_ratio", 0.24)), 0.18), 0.35
        )
        blur_strength = max(float(subtitle_config.get("blur_strength", 34)), 0.0)
        blur_steps = max(int(subtitle_config.get("blur_steps", 2)), 1)

        # libass expects colors as opaque AABBGGRR values, not CSS #RRGGBB.
        font_color = hex_to_ass(subtitle_config.get("font_color", "#FFFFFF"))
        outline_color = hex_to_ass(
            subtitle_config.get("outline_color", "#000000"), "000000"
        )

        blur_region = subtitle_config.get("blur_region")
        has_custom_blur_region = isinstance(blur_region, dict)
        if blur_existing:
            if has_custom_blur_region:
                try:
                    region_width = min(max(float(blur_region.get("width", 1.0)), 0.02), 1.0)
                    region_height = min(max(float(blur_region.get("height", 0.24)), 0.02), 1.0)
                    region_x = min(max(float(blur_region.get("x", 0.0)), 0.0), 1.0 - region_width)
                    region_y = min(max(float(blur_region.get("y", 0.76)), 0.0), 1.0 - region_height)
                    blur_x = min(max(int(round(width * region_x)), 0), max(width - 1, 0))
                    blur_y = min(max(int(round(height * region_y)), 0), max(height - 1, 0))
                    blur_width = max(min(int(round(width * region_width)), width - blur_x), 1)
                    blur_height = max(min(int(round(height * region_height)), height - blur_y), 1)
                except (TypeError, ValueError):
                    has_custom_blur_region = False

            if not has_custom_blur_region:
                blur_height = min(
                    max(int(round(height * blur_height_ratio)), font_size * 6),
                    height,
                )
                blur_x = 0
                blur_y = max(height - blur_height, 0)
                blur_width = width

        else:
            blur_x = 0
            blur_width = 0
            blur_height = 0
            blur_y = height

        # The preview positions the draggable subtitle label by its center in
        # top-down video coordinates. Render an ASS file with the exact frame
        # as its script canvas and use an explicit center anchor so the same
        # normalized point is used by the final video renderer.
        ass_path = os.path.splitext(srt_path)[0] + ".ass"
        _write_positioned_ass_subtitles(
            srt_path=srt_path,
            ass_path=ass_path,
            video_width=width,
            video_height=height,
            font_size=font_size,
            outline_width=outline_width,
            font_color=font_color,
            outline_color=outline_color,
            position_y=position_y,
        )

        # Keep the filename inside quotes. This is required for Windows drive
        # letters and paths containing spaces; only the filter-level colon is escaped.
        ass_escaped = _escape_ffmpeg_filter_path(ass_path)
        subtitle_filter = f"ass=filename='{ass_escaped}'"

        if blur_existing:
            # Only blur when the user confirms the source contains burned-in text.
            # Crop the full-width lower band, blur that crop, put it back over the
            # original frame, and render the new subtitle last so it stays sharp.
            filter_complex = (
                f"[0:v]split=2[v_main][v_blur];"
                f"[v_blur]crop=w={blur_width}:h={blur_height}:x={blur_x}:y={blur_y},"
                f"gblur=sigma={blur_strength}:steps={blur_steps}[blurred];"
                f"[v_main][blurred]overlay=x={blur_x}:y={blur_y}:eof_action=repeat[blurred_video];"
                f"[blurred_video]{subtitle_filter}[v_subtitle]"
            )
        else:
            # Avoid a full-frame blur pass for videos without old captions.
            filter_complex = f"[0:v]{subtitle_filter}[v_subtitle]"

        cmd = [
            "ffmpeg", "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[v_subtitle]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", os.getenv("FFMPEG_PRESET", "veryfast"), "-crf", "23",
            "-c:a", "copy", "-shortest",
            "-y", output_video,
        ]

        logger.info(
            f"Burning subtitles (blur_old={blur_existing}, font_size={font_size}, "
            f"position_y={position_y:.4f}, ass_path={ass_path}, "
            f"blur_x={blur_x}, blur_y={blur_y}, blur_width={blur_width}, blur_height={blur_height}, "
            f"blur_sigma={blur_strength}, blur_steps={blur_steps}): {' '.join(cmd)}"
        )
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=600, **hidden_subprocess_kwargs())
        logger.info(f"Subtitle burn successful: {output_video}")
        return True
    except (ValueError, TypeError) as exc:
        logger.error(f"Invalid subtitle configuration: {exc}")
        return False
    except subprocess.TimeoutExpired as exc:
        logger.error("Subtitle burn timed out after 600s")
        if exc.stderr:
            logger.error(f"ffmpeg stderr:\n{exc.stderr}")
        return False
    except subprocess.CalledProcessError as exc:
        logger.error(f"Subtitle burn failed with return code {exc.returncode}")
        logger.error(f"ffmpeg stderr:\n{exc.stderr or '(empty)'}")
        logger.error(f"Filter complex used: {filter_complex}")
        if os.path.exists(output_video):
            os.remove(output_video)
        return False


def _download_progress_reporter(job_id: str):
    """Build a thread-safe callback that persists download progress.

    yt-dlp and pytubefix fire their callbacks on executor threads while the
    caller's AsyncSession belongs to the event loop, so each write marshals a
    short-lived dedicated session back onto the loop with
    ``run_coroutine_threadsafe`` — never touching the caller's session.
    Updates are throttled and skipped while a previous write is still in
    flight to avoid hammering SQLite.
    """
    loop = asyncio.get_running_loop()
    state = {"last_time": 0.0, "in_flight": None}

    def _report(percent: float) -> None:
        try:
            pending = state["in_flight"]
            if pending is not None and not pending.done():
                return
            now = time.monotonic()
            if now - state["last_time"] < 2.0:
                return
            state["last_time"] = now
            clamped = max(1, min(int(percent), 99))

            async def _write():
                try:
                    async with async_session() as session:
                        await update_job(session, job_id, "downloading", clamped)
                except Exception:
                    logger.debug("Progress write failed for job %s", job_id, exc_info=True)

            state["in_flight"] = asyncio.run_coroutine_threadsafe(_write(), loop)
        except Exception:
            logger.debug("Progress reporting failed for job %s", job_id, exc_info=True)

    return _report


async def run_preview_download(job_id: str, url: str, session: AsyncSession):
    """Phase 1: Download video for preview. Store in output dir for persistence."""
    job_dir = os.path.join(str(OUTPUT_DIR), job_id)
    os.makedirs(job_dir, exist_ok=True)
    temp_dir = os.path.join(str(TEMP_DIR), job_id)
    os.makedirs(temp_dir, exist_ok=True)

    try:
        await update_job(session, job_id, "downloading", 0)
        video_info = await download_video(
            url, temp_dir, progress_cb=_download_progress_reporter(job_id)
        )
        video_path = video_info["video_path"]
        title = video_info.get("title", "Unknown")
        thumbnail_path = video_info.get("thumbnail_path")

        await update_job_field(session, job_id, "title", title)

        # Copy video to output dir for persistence (so it survives temp cleanup)
        import shutil
        video_dest = os.path.join(job_dir, "preview.mp4")
        shutil.copy2(video_path, video_dest)
        await update_job_field(session, job_id, "video_path", video_dest)

        if thumbnail_path and os.path.exists(thumbnail_path):
            thumb_dest = os.path.join(job_dir, "thumbnail.jpg")
            shutil.copy2(thumbnail_path, thumb_dest)
            await update_job_field(session, job_id, "thumbnail_path", thumb_dest)

        await update_job(session, job_id, "preview_ready", 100)
        logger.info(f"Preview ready for job {job_id}: {video_dest}")

    except Exception as e:
        await update_job(session, job_id, "error", 0)
        await update_job_field(session, job_id, "error", str(e))
        raise
    finally:
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


async def run_pipeline(job_id: str, url: str, source_lang: str,
                        target_lang: str, voice: str, whisper_model: str,
                        tts_speed: float, session: AsyncSession,
                        subtitle_config: Optional[dict] = None,
                        audio_config: Optional[dict] = None,
                        translation_config: Optional[TranslationConfig] = None):
    job_dir = os.path.join(str(OUTPUT_DIR), job_id)
    os.makedirs(job_dir, exist_ok=True)
    temp_dir = os.path.join(str(TEMP_DIR), job_id)
    os.makedirs(temp_dir, exist_ok=True)

    # Audio mix volume defaults (overridable via audio_config)
    dubbing_volume = audio_config.get("dubbing_volume", 2.0) if audio_config else 2.0
    background_volume = audio_config.get("background_volume", 1.0) if audio_config else 1.0
    original_vocals_volume = audio_config.get("original_vocals_volume", 0.1) if audio_config else 0.1
    vocal_task = None

    try:
        # Check if video was already downloaded in preview phase
        existing_video = None
        try:
            from sqlalchemy import select as sa_select
            from app.models.database import DubbingJob as _DJ
            result_q = await session.execute(sa_select(_DJ).where(_DJ.id == job_id))
            existing_job = result_q.scalar_one_or_none()
            if existing_job and existing_job.video_path and os.path.exists(existing_job.video_path):
                existing_video = existing_job.video_path
                title = existing_job.title or "Unknown"
                logger.info(f"Reusing preview video: {existing_video}")
        except Exception:
            pass

        if existing_video:
            video_path = existing_video
            video_info = {"duration": 0}
            await update_job(session, job_id, "downloading", 100)
        else:
            await update_job(session, job_id, "downloading", 0)
            video_info = await download_video(
                url, temp_dir, progress_cb=_download_progress_reporter(job_id)
            )
            video_path = video_info["video_path"]
            title = video_info.get("title", "Unknown")
            thumbnail_path = video_info.get("thumbnail_path")
            await update_job_field(session, job_id, "title", title)
            if thumbnail_path and os.path.exists(thumbnail_path):
                import shutil
                thumb_dest = os.path.join(job_dir, "thumbnail.jpg")
                shutil.copy2(thumbnail_path, thumb_dest)
                await update_job_field(session, job_id, "thumbnail_path", thumb_dest)
            await update_job(session, job_id, "downloading", 100)

        # Keep FastAPI's event loop responsive while probing media metadata.
        video_width, video_height = await asyncio.to_thread(
            get_actual_video_dimensions, video_path
        )
        logger.info(f"Video dimensions: {video_width}x{video_height}")

        await update_job(session, job_id, "transcribing", 0)
        audio_path = os.path.join(temp_dir, "audio.wav")
        await asyncio.to_thread(extract_audio, video_path, audio_path)
        await update_job(session, job_id, "transcribing", 50)

        result = await asyncio.to_thread(
            transcribe_with_whisper, audio_path, whisper_model, source_lang
        )
        original_srt = os.path.join(job_dir, "original.srt")
        segments_to_srt(result["segments"], original_srt)
        await update_job(session, job_id, "transcribing", 100)

        await update_job(session, job_id, "translating", 0)
        translated_srt = os.path.join(job_dir, "translated.srt")
        if translation_config is None:
            translation_config = await load_translation_config(session)
        await asyncio.to_thread(
            translate_srt_deep_translator,
            original_srt,
            target_lang,
            translated_srt,
            source_lang=source_lang,
            translation_config=translation_config,
        )
        await update_job(session, job_id, "translating", 100)

        # TTS is network-bound while vocal separation is a separate CPU-bound
        # process, so start both jobs together instead of waiting sequentially.
        vocal_task = asyncio.create_task(
            asyncio.to_thread(separate_vocals, video_path, job_dir)
        )

        await update_job(session, job_id, "tts", 0)
        translated_segments = srt_to_segments(translated_srt)
        logger.info("Using translated SRT as TTS input: %s", translated_srt)
        expected_audio_count = sum(1 for segment in translated_segments if segment.get("text", "").strip())
        if expected_audio_count == 0:
            raise RuntimeError("Không có nội dung phụ đề đã dịch để tạo audio lồng tiếng")
        tts_dir = os.path.join(job_dir, "tts")
        rate = speed_to_rate(tts_speed)
        audio_files = await generate_dubbing_audio(
            translated_segments, voice, tts_dir, rate
        )
        if len(audio_files) != expected_audio_count:
            raise RuntimeError(
                f"Chỉ tạo được {len(audio_files)}/{expected_audio_count} đoạn audio từ phụ đề đã dịch; vui lòng kiểm tra kết nối TTS rồi thử lại."
            )
        await update_job(session, job_id, "tts", 50)

        total_duration = video_info.get("duration", 0)
        if total_duration == 0:
            total_duration = await asyncio.to_thread(get_video_duration, video_path)

        dubbed_audio = os.path.join(job_dir, "dubbed_audio.wav")
        await asyncio.to_thread(merge_tts_segments, audio_files, total_duration, dubbed_audio)
        if not os.path.isfile(dubbed_audio):
            raise RuntimeError("Không tạo được audio lồng tiếng cuối cùng")
        await update_job(session, job_id, "tts", 100)

        await update_job(session, job_id, "removing_vocals", 50)
        vocal_result = await vocal_task
        no_vocals = vocal_result.get("no_vocals")
        original_vocals = vocal_result.get("vocals")
        await update_job(session, job_id, "removing_vocals", 100)

        await update_job(session, job_id, "merging", 0)
        final_output = os.path.join(job_dir, f"{job_id}_dubbed.mp4")

        # Normalize each source first, then apply the configured gain. Applying
        # gain after loudnorm keeps values such as 1.4 and 0.2 meaningful.
        if no_vocals and os.path.exists(no_vocals):
            boosted_dubbed = os.path.join(job_dir, "dubbed_audio_boosted.wav")
            await asyncio.to_thread(
                _normalize_audio_track, dubbed_audio, boosted_dubbed, dubbing_volume
            )

            normalized_bg = os.path.join(job_dir, "no_vocals_normalized.wav")
            await asyncio.to_thread(
                _normalize_audio_track, no_vocals, normalized_bg, background_volume
            )

            audio_tracks = [normalized_bg, boosted_dubbed]
            if original_vocals and os.path.exists(original_vocals) and original_vocals_volume > 0:
                normalized_vocals = os.path.join(job_dir, "vocals_normalized.wav")
                await asyncio.to_thread(
                    _normalize_audio_track,
                    original_vocals,
                    normalized_vocals,
                    original_vocals_volume,
                )
                audio_tracks.append(normalized_vocals)

            logger.info(
                f"Audio volumes - dubbing: {dubbing_volume}, "
                f"background: {background_volume}, original vocals: {original_vocals_volume}"
            )
            merged_audio = os.path.join(job_dir, "final_audio.wav")
            await asyncio.to_thread(_mix_audio_tracks, audio_tracks, merged_audio)

            # Subtitle/overlay rendering has been removed from the pipeline.
            # The dubbed video now contains only the mixed audio + original video.
            current_video_path = video_path

            # PASS 2.5: Burn subtitles with blur mask (if enabled)
            if subtitle_config and subtitle_config.get("enabled", False):
                translated_srt = os.path.join(job_dir, "translated.srt")
                if os.path.exists(translated_srt):
                    subtitle_output = os.path.join(job_dir, "video_with_subs.mp4")
                    success = await asyncio.to_thread(
                        burn_subtitles_with_blur_mask,
                        input_video=current_video_path,
                        srt_path=translated_srt,
                        output_video=subtitle_output,
                        video_width=video_width,
                        video_height=video_height,
                        subtitle_config=subtitle_config,
                    )
                    if success:
                        current_video_path = subtitle_output
                        logger.info("Subtitle burn with blur mask completed")
                    else:
                        logger.warning("Subtitle burn failed, continuing without subtitles")
                else:
                    logger.warning(f"Translated SRT not found: {translated_srt}")

            # PASS 3: Merge video + audio
            try:
                cmd = [
                    "ffmpeg", "-i", current_video_path, "-i", merged_audio,
                    "-c:v", "copy", "-c:a", "aac",
                    "-map", "0:v", "-map", "1:a",
                    "-shortest", "-y", final_output
                ]
                logger.info(f"Pass 3 - Final merge: {' '.join(cmd)}")
                await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    check=True,
                    timeout=300,
                    **hidden_subprocess_kwargs(),
                )
                logger.info("Pass 3 - Final merge successful")
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                logger.error(f"Pass 3 - Final merge failed: {e}")
                raise RuntimeError("Không thể ghép audio lồng tiếng vào video") from e
        else:
            # Demucs may fail on a source; keep the original track as a separate
            # source and apply the requested gain after normalization as above.
            logger.info(
                f"Audio volumes (no vocals removed) - dubbing: {dubbing_volume}, "
                f"background: {background_volume}, original vocals: {original_vocals_volume}"
            )
            boosted_dubbed = os.path.join(job_dir, "dubbed_audio_boosted.wav")
            await asyncio.to_thread(
                _normalize_audio_track, dubbed_audio, boosted_dubbed, dubbing_volume
            )

            original_audio = os.path.join(job_dir, "original_audio.wav")
            await asyncio.to_thread(
                subprocess.run,
                [
                    "ffmpeg", "-i", video_path,
                    "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                    "-y", original_audio,
                ],
                capture_output=True,
                check=True,
                **hidden_subprocess_kwargs(),
            )

            normalized_original = os.path.join(job_dir, "original_audio_normalized.wav")
            await asyncio.to_thread(
                _normalize_audio_track,
                original_audio,
                normalized_original,
                original_vocals_volume,
            )

            merged_audio = os.path.join(job_dir, "final_audio.wav")
            await asyncio.to_thread(
                _mix_audio_tracks, [normalized_original, boosted_dubbed], merged_audio
            )

            # Subtitle/overlay rendering has been removed from the pipeline.
            current_video_path = video_path

            # PASS 2.5: Burn subtitles with blur mask (if enabled)
            if subtitle_config and subtitle_config.get("enabled", False):
                translated_srt = os.path.join(job_dir, "translated.srt")
                if os.path.exists(translated_srt):
                    subtitle_output = os.path.join(job_dir, "video_with_subs.mp4")
                    success = await asyncio.to_thread(
                        burn_subtitles_with_blur_mask,
                        input_video=current_video_path,
                        srt_path=translated_srt,
                        output_video=subtitle_output,
                        video_width=video_width,
                        video_height=video_height,
                        subtitle_config=subtitle_config,
                    )
                    if success:
                        current_video_path = subtitle_output
                        logger.info("Subtitle burn with blur mask completed")
                    else:
                        logger.warning("Subtitle burn failed, continuing without subtitles")
                else:
                    logger.warning(f"Translated SRT not found: {translated_srt}")

            # PASS 3: Merge video + audio
            try:
                cmd = [
                    "ffmpeg", "-i", current_video_path, "-i", merged_audio,
                    "-c:v", "copy", "-c:a", "aac",
                    "-map", "0:v", "-map", "1:a",
                    "-shortest", "-y", final_output
                ]
                logger.info(f"[No-vocals] Pass 3 - Final merge: {' '.join(cmd)}")
                await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    check=True,
                    timeout=300,
                    **hidden_subprocess_kwargs(),
                )
                logger.info("[No-vocals] Pass 3 - Final merge successful")
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                logger.error(f"[No-vocals] Pass 3 - Final merge failed: {e}")
                raise RuntimeError("Không thể ghép audio lồng tiếng vào video") from e

        if not os.path.isfile(final_output) or os.path.getsize(final_output) <= 0:
            raise RuntimeError("Video đầu ra không được tạo thành công")

        await update_job(session, job_id, "merging", 100)

        file_size = os.path.getsize(final_output) if os.path.exists(final_output) else 0
        size_str = f"{file_size / (1024*1024):.1f} MB"

        # Segment MP3 files are disposable once the merged audio and final
        # video exist. Keep translated.srt and merged artifacts for retry/debug.
        await asyncio.to_thread(cleanup_tts_directory, tts_dir)
        await update_job_field(session, job_id, "result_path", final_output)
        await update_job_field(session, job_id, "file_size", size_str)
        await update_job(session, job_id, "completed", 100)

    except asyncio.CancelledError:
        if vocal_task is not None and not vocal_task.done():
            vocal_task.cancel()
        await update_job(session, job_id, "cancelled", 0)
        raise
    except Exception as e:
        if vocal_task is not None and not vocal_task.done():
            vocal_task.cancel()
            try:
                await vocal_task
            except asyncio.CancelledError:
                pass
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