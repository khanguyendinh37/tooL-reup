from __future__ import annotations

import os
import asyncio
import logging
import shutil
import subprocess

from app.core.process_utils import hidden_subprocess_kwargs

logger = logging.getLogger(__name__)

# Keep a small bounded pool so Edge TTS requests can run concurrently without
# overwhelming the service or the local machine.
TTS_CONCURRENCY = 4
TTS_SEGMENT_TIMEOUT_SECONDS = 90

# Edge TTS voices mapping - frontend voice IDs match these
EDGE_TTS_VOICES = {
    "vi-VN-HoaiMyNeural": "vi-VN-HoaiMyNeural",
    "vi-VN-NamMinhNeural": "vi-VN-NamMinhNeural",
    "en-US-JennyNeural": "en-US-JennyNeural",
    "en-US-GuyNeural": "en-US-GuyNeural",
    "ja-JP-NanamiNeural": "ja-JP-NanamiNeural",
    "ja-JP-KeitaNeural": "ja-JP-KeitaNeural",
    "ko-KR-SunHiNeural": "ko-KR-SunHiNeural",
    "ko-KR-InJoonNeural": "ko-KR-InJoonNeural",
    "zh-CN-XiaoxiaoNeural": "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural": "zh-CN-YunxiNeural",
    "th-TH-PremwadeeNeural": "th-TH-PremwadeeNeural",
    "fr-FR-DeniseNeural": "fr-FR-DeniseNeural",
    "de-DE-KatjaNeural": "de-DE-KatjaNeural",
    "es-ES-ElviraNeural": "es-ES-ElviraNeural",
    "pt-BR-FranciscaNeural": "pt-BR-FranciscaNeural",
    "ru-RU-SvetlanaNeural": "ru-RU-SvetlanaNeural",
    "ar-SA-ZariyahNeural": "ar-SA-ZariyahNeural",
    "hi-IN-SwaraNeural": "hi-IN-SwaraNeural",
    # Default fallbacks by language prefix
    "vi": "vi-VN-HoaiMyNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "th": "th-TH-PremwadeeNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "ar": "ar-SA-ZariyahNeural",
    "hi": "hi-IN-SwaraNeural",
    "id": "id-ID-GadisNeural",
    "ms": "ms-MY-YasminNeural",
}

# Canonical gender for every supported Edge TTS voice. This is the single
# source of truth so a male selection never silently swaps in a female
# voice when the primary provider is temporarily down.
VOICE_GENDERS = {
    "vi-VN-HoaiMyNeural": "female",
    "vi-VN-NamMinhNeural": "male",
    "en-US-JennyNeural": "female",
    "en-US-GuyNeural": "male",
    "ja-JP-NanamiNeural": "female",
    "ja-JP-KeitaNeural": "male",
    "ko-KR-SunHiNeural": "female",
    "ko-KR-InJoonNeural": "male",
    "zh-CN-XiaoxiaoNeural": "female",
    "zh-CN-YunxiNeural": "male",
    "th-TH-PremwadeeNeural": "female",
    "fr-FR-DeniseNeural": "female",
    "de-DE-KatjaNeural": "female",
    "es-ES-ElviraNeural": "female",
    "pt-BR-FranciscaNeural": "female",
    "ru-RU-SvetlanaNeural": "female",
    "ar-SA-ZariyahNeural": "female",
    "hi-IN-SwaraNeural": "female",
    "id-ID-GadisNeural": "female",
    "ms-MY-YasminNeural": "female",
}

# Fallback voices per language (if primary fails)
VOICE_FALLBACKS = {
    "vi": ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural", "en-US-GuyNeural"],
    "en": ["en-US-JennyNeural", "en-US-GuyNeural"],
    "ja": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
    "ko": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural"],
    "zh": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"],
    "th": ["th-TH-PremwadeeNeural"],
    "fr": ["fr-FR-DeniseNeural"],
    "de": ["de-DE-KatjaNeural"],
    "es": ["es-ES-ElviraNeural"],
    "pt": ["pt-BR-FranciscaNeural"],
    "ru": ["ru-RU-SvetlanaNeural"],
    "ar": ["ar-SA-ZariyahNeural"],
    "hi": ["hi-IN-SwaraNeural"],
    "id": ["id-ID-GadisNeural"],
    "ms": ["ms-MY-YasminNeural"],
}


def get_edge_voice(voice: str) -> str:
    """Map frontend voice ID to Edge TTS voice."""
    if voice in EDGE_TTS_VOICES:
        return EDGE_TTS_VOICES[voice]
    # Fallback: extract language prefix and use default
    lang = voice.split("-")[0] if voice else "en"
    return EDGE_TTS_VOICES.get(lang, "en-US-JennyNeural")


def _voice_gender(voice_id: str) -> str:
    """Return 'male' or 'female' for an Edge TTS voice id.

    Uses the canonical ``VOICE_GENDERS`` table as the single source of truth.
    Unknown voices default to 'female' so a male selection never silently
    swaps in a female voice when the primary provider is temporarily down.
    """
    return VOICE_GENDERS.get(voice_id, "female")


def get_fallback_voices(voice: str) -> list:
    """Get list of fallback voices for a given voice.

    Same-gender fallbacks are tried first so a male selection never silently
    swaps in a female voice when the primary provider is temporarily down.
    Returns an empty list when no same-gender fallback exists; the caller
    should then fall back to the primary voice rather than a different gender.
    """
    lang = voice.split("-")[0] if voice else "en"
    fallbacks = VOICE_FALLBACKS.get(lang, ["en-US-JennyNeural"])
    primary = get_edge_voice(voice)
    primary_gender = _voice_gender(primary)

    same_gender = [v for v in fallbacks if v != primary and _voice_gender(v) == primary_gender]
    if same_gender:
        return same_gender
    return []


def speed_to_rate(speed: float) -> str:
    """Convert speed multiplier (0.5-2.0) to Edge TTS rate format (+0%, +50%, -20%, etc.)."""
    if speed == 1.0:
        return "+0%"
    pct = (speed - 1.0) * 100
    return f"{pct:+.0f}%"


def _detect_text_language(text: str) -> str:
    """Detect the language of text using Unicode character ranges.

    Returns a 2-letter language code (e.g., 'vi', 'ja', 'zh', 'ko', 'th')
    or '' if the language cannot be determined. This is used to validate that
    an Edge TTS voice can actually pronounce the text correctly - an English
    voice reading Vietnamese produces garbled output.
    """
    if not text:
        return ""
    sample = text[:200]
    if any("一" <= char <= "鿿" for char in sample):
        return "zh"
    if any("぀" <= char <= "ゟ" or "゠" <= char <= "ヿ" for char in sample):
        return "ja"
    if any("가" <= char <= "힯" for char in sample):
        return "ko"
    if any("฀" <= char <= "๿" for char in sample):
        return "th"
    if any("Ѐ" <= char <= "ӿ" for char in sample):
        return "ru"
    if any("؀" <= char <= "ۿ" for char in sample):
        return "ar"
    if any("ऀ" <= char <= "ॿ" for char in sample):
        return "hi"
    if any("เ" <= char <= "๿" for char in sample):
        return "th"
    # Latin-based: check for Vietnamese diacritics first
    if any(char in "àáảãạâầấẩẫậăằằằẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụỳýỷỹỵđ" for char in sample.lower()):
        return "vi"
    return ""


async def text_to_speech_edge(text: str, voice: str, output_path: str, rate: str = "+0%") -> str:
    """Generate TTS audio using Edge TTS (Microsoft Edge voices)."""
    edge_voice = get_edge_voice(voice)
    try:
        import edge_tts
        # Validate the voice matches the language of the text. If the voice
        # belongs to a different language family than the text, fall back to
        # gTTS which actually pronounces the target language correctly.
        text_lang = _detect_text_language(text)
        voice_lang = edge_voice.split("-")[0] if edge_voice else ""
        if text_lang and voice_lang and text_lang != voice_lang and text_lang != "auto":
            # The voice may not pronounce this language correctly. gTTS
            # fallback will speak the target language accurately.
            logger.warning(
                "Voice '%s' (%s) may not pronounce text in '%s' correctly; "
                "gTTS fallback will speak the target language accurately",
                edge_voice, voice_lang, text_lang,
            )
        communicate = edge_tts.Communicate(text, edge_voice, rate=rate)
        await communicate.save(output_path)
        return output_path
    except ImportError:
        logger.error("edge-tts not installed. Please install: pip install edge-tts")
        raise
    except Exception as e:
        logger.error(f"Edge TTS failed for voice '{edge_voice}': {e}")
        raise


async def text_to_speech_gtts(text: str, lang: str, output_path: str, slow: bool = False) -> str:
    """Generate TTS audio using gTTS (Google Translate TTS) - fallback."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang, slow=slow)
        await asyncio.to_thread(tts.save, output_path)
        return output_path
    except ImportError:
        logger.error("gTTS not installed. Please install: pip install gTTS")
        raise
    except Exception as e:
        logger.error(f"gTTS failed for lang '{lang}': {e}")
        raise


async def text_to_speech_with_fallback(text: str, voice: str, output_path: str, rate: str = "+0%", target_lang: str = "vi") -> str:
    """Try Edge TTS with fallbacks, then fall back to gTTS.

    Args:
        text: Text to synthesize
        voice: Voice ID (e.g., 'vi-VN-HoaiMyNeural', 'en-US-GuyNeural')
        output_path: Output audio file path
        rate: Speech rate (e.g., '+0%', '+20%')
        target_lang: Target language code (e.g., 'vi', 'en', 'ja') - used for gTTS
                     fallback to ensure correct language is spoken regardless of
                     the voice parameter.
    """
    # Try primary voice
    primary_voice = get_edge_voice(voice)
    try:
        return await text_to_speech_edge(text, voice, output_path, rate)
    except Exception as e:
        logger.warning(f"Primary voice '{primary_voice}' failed: {e}")

    # Try fallback voices
    fallback_voices = get_fallback_voices(voice)
    for fb_voice in fallback_voices:
        try:
            logger.info(f"Trying fallback voice: {fb_voice}")
            return await text_to_speech_edge(text, fb_voice, output_path, rate)
        except Exception as e:
            logger.warning(f"Fallback voice '{fb_voice}' failed: {e}")

    # Try gTTS as last resort - USE target_lang, not voice prefix
    # Map language codes for gTTS (Google Translate TTS language codes)
    gtts_lang_map = {
        "vi": "vi", "en": "en", "ja": "ja", "ko": "ko", "zh": "zh-cn",
        "th": "th", "fr": "fr", "de": "de", "es": "es", "pt": "pt",
        "ru": "ru", "ar": "ar", "hi": "hi", "id": "id", "ms": "ms"
    }
    gtts_lang = gtts_lang_map.get(target_lang.lower(), "en")
    try:
        logger.info(f"Falling back to gTTS with target_lang: {target_lang} -> gTTS lang: {gtts_lang}")
        return await text_to_speech_gtts(text, gtts_lang, output_path)
    except Exception as e:
        logger.error(f"All TTS methods failed: {e}")
        raise


async def _generate_segment_audio(index: int, segment: dict, voice: str,
                                  output_dir: str, rate: str, target_lang: str,
                                  semaphore: asyncio.Semaphore) -> dict | None:
    """Generate one segment while respecting the global TTS concurrency limit.

    target_lang is passed through so the gTTS fallback speaks the destination
    language even if the user picked a voice whose prefix differs.
    """
    text = segment.get("text", "").strip()
    if not text:
        return None

    segment_path = os.path.join(output_dir, f"seg_{index:04d}.mp3")
    async with semaphore:
        try:
            # Use fallback chain: Edge TTS -> fallback voices -> gTTS. A
            # provider that hangs must not hold a job in TTS forever.
            await asyncio.wait_for(
                text_to_speech_with_fallback(text, voice, segment_path, rate, target_lang),
                timeout=TTS_SEGMENT_TIMEOUT_SECONDS,
            )
            return {
                "index": index,
                "start": segment["start"],
                "end": segment["end"],
                "text": text,
                "audio_path": segment_path,
            }
        except Exception as exc:
            logger.error(
                f"Failed to generate TTS for segment {index} after all fallbacks: {exc}"
            )
            return None


def cleanup_tts_directory(output_dir: str) -> None:
    """Remove disposable per-segment TTS files after a successful merge.

    The merged WAV and final video live outside this directory, so retrying a
    failed job can safely regenerate the segments from ``translated.srt``.
    Cleanup failures are logged but deliberately do not invalidate a completed
    video.
    """
    if not os.path.isdir(output_dir):
        return
    try:
        shutil.rmtree(output_dir)
        logger.info("Removed disposable TTS directory: %s", output_dir)
    except OSError as exc:
        logger.warning("Could not remove disposable TTS directory %s: %s", output_dir, exc)


async def generate_dubbing_audio(segments: list, voice: str,
                                 output_dir: str, rate: str = "+0%",
                                 target_lang: str = "vi") -> list:
    """Generate all TTS segments concurrently while preserving timeline order.

    target_lang is used for the gTTS fallback so the fallback voice speaks the
    destination language instead of the voice's language prefix.
    """
    os.makedirs(output_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(TTS_CONCURRENCY)
    tasks = [
        _generate_segment_audio(index, segment, voice, output_dir, rate, target_lang, semaphore)
        for index, segment in enumerate(segments)
        if segment.get("text", "").strip()
    ]

    if not tasks:
        logger.warning("No transcribed text segments to synthesize")
        return []

    logger.info(
        f"Generating {len(tasks)} TTS segments concurrently (limit={TTS_CONCURRENCY})"
    )
    results = await asyncio.gather(*tasks)
    return [result for result in results if result is not None]


def merge_tts_segments(audio_files: list, total_duration: float,
                        output_path: str) -> str:
    if not audio_files:
        logger.warning("No audio files to merge")
        return ""
    if total_duration <= 0:
        raise ValueError("Video duration must be greater than zero before merging TTS")

    silence_path = output_path + ".silence.wav"
    subprocess.run(
        ["ffmpeg", "-f", "lavfi", "-i",
         f"anullsrc=r=44100:cl=mono:d={total_duration}",
         "-y", silence_path],
        capture_output=True, check=True, **hidden_subprocess_kwargs()
    )

    filter_parts = []
    delay_parts = []

    for i, af in enumerate(audio_files):
        input_idx = i + 1
        delay_ms = int(af["start"] * 1000)
        filter_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
        delay_parts.append(f"[a{i}]")

    if not delay_parts:
        logger.warning("No audio segments to merge")
        return ""

    filter_str = ";".join(filter_parts)
    mix_inputs = "".join(delay_parts)
    filter_str += f";{mix_inputs}amix=inputs={len(delay_parts)}:duration=longest:dropout_transition=0[out]"

    cmd = ["ffmpeg", "-i", silence_path]
    for af in audio_files:
        cmd.extend(["-i", af["audio_path"]])
    cmd.extend([
        "-filter_complex", filter_str,
        "-map", "[out]",
        "-ar", "44100",
        "-y", output_path
    ])

    subprocess.run(cmd, capture_output=True, check=True, **hidden_subprocess_kwargs())

    if os.path.exists(silence_path):
        os.remove(silence_path)

    return output_path