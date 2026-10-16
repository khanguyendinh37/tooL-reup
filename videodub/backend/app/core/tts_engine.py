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
TTS_RECOVERY_ROUNDS = 2
TTS_RECOVERY_DELAY_SECONDS = 10

# Retry resilience for a single Edge TTS call. ``EDGE_TTS_RETRY_BASE_SECONDS``
# doubles per attempt, capped at 10s, so up to 3 attempts takes ~17s worst
# case without switching speakers.
EDGE_TTS_MAX_ATTEMPTS = 3
EDGE_TTS_RETRY_BASE_SECONDS = 1.0


class TTSAccessError(RuntimeError):
    """Provider rejected access; retrying every cue cannot fix authorization."""

# Edge TTS voices mapping - frontend voice IDs match these
EDGE_TTS_VOICES = {
    # Vietnamese
    "vi-VN-HoaiMyNeural": "vi-VN-HoaiMyNeural",
    "vi-VN-NamMinhNeural": "vi-VN-NamMinhNeural",
    # English
    "en-US-JennyNeural": "en-US-JennyNeural",
    "en-US-GuyNeural": "en-US-GuyNeural",
    "en-US-AriaNeural": "en-US-AriaNeural",
    "en-US-AndrewNeural": "en-US-AndrewNeural",
    "en-US-AvaNeural": "en-US-AvaNeural",
    "en-US-BrianNeural": "en-US-BrianNeural",
    "en-US-EmmaNeural": "en-US-EmmaNeural",
    "en-US-MichelleNeural": "en-US-MichelleNeural",
    "en-US-RogerNeural": "en-US-RogerNeural",
    "en-US-AnaNeural": "en-US-AnaNeural",
    "en-GB-SoniaNeural": "en-GB-SoniaNeural",
    "en-GB-RyanNeural": "en-GB-RyanNeural",
    "en-AU-NatashaNeural": "en-AU-NatashaNeural",
    "en-AU-WilliamMultilingualNeural": "en-AU-WilliamMultilingualNeural",
    "en-IN-NeerjaNeural": "en-IN-NeerjaNeural",
    "en-IN-PrabhatNeural": "en-IN-PrabhatNeural",
    # Japanese
    "ja-JP-NanamiNeural": "ja-JP-NanamiNeural",
    "ja-JP-KeitaNeural": "ja-JP-KeitaNeural",
    # Korean
    "ko-KR-SunHiNeural": "ko-KR-SunHiNeural",
    "ko-KR-InJoonNeural": "ko-KR-InJoonNeural",
    "ko-KR-HyunsuMultilingualNeural": "ko-KR-HyunsuMultilingualNeural",
    # Chinese
    "zh-CN-XiaoxiaoNeural": "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural": "zh-CN-YunxiNeural",
    "zh-CN-YunjianNeural": "zh-CN-YunjianNeural",
    "zh-CN-XiaoyiNeural": "zh-CN-XiaoyiNeural",
    "zh-CN-YunyangNeural": "zh-CN-YunyangNeural",
    "zh-HK-HiuMaanNeural": "zh-HK-HiuMaanNeural",
    "zh-HK-WanLungNeural": "zh-HK-WanLungNeural",
    "zh-TW-HsiaoChenNeural": "zh-TW-HsiaoChenNeural",
    "zh-TW-YunJheNeural": "zh-TW-YunJheNeural",
    # Thai
    "th-TH-PremwadeeNeural": "th-TH-PremwadeeNeural",
    "th-TH-NiwatNeural": "th-TH-NiwatNeural",
    # French
    "fr-FR-DeniseNeural": "fr-FR-DeniseNeural",
    "fr-FR-HenriNeural": "fr-FR-HenriNeural",
    "fr-FR-EloiseNeural": "fr-FR-EloiseNeural",
    "fr-CA-SylvieNeural": "fr-CA-SylvieNeural",
    "fr-CA-ThierryNeural": "fr-CA-ThierryNeural",
    # German
    "de-DE-KatjaNeural": "de-DE-KatjaNeural",
    "de-DE-ConradNeural": "de-DE-ConradNeural",
    "de-DE-AmalaNeural": "de-DE-AmalaNeural",
    "de-AT-IngridNeural": "de-AT-IngridNeural",
    "de-AT-JonasNeural": "de-AT-JonasNeural",
    # Spanish
    "es-ES-ElviraNeural": "es-ES-ElviraNeural",
    "es-ES-AlvaroNeural": "es-ES-AlvaroNeural",
    "es-MX-DaliaNeural": "es-MX-DaliaNeural",
    "es-MX-JorgeNeural": "es-MX-JorgeNeural",
    "es-AR-ElenaNeural": "es-AR-ElenaNeural",
    "es-AR-TomasNeural": "es-AR-TomasNeural",
    # Portuguese
    "pt-BR-FranciscaNeural": "pt-BR-FranciscaNeural",
    "pt-BR-AntonioNeural": "pt-BR-AntonioNeural",
    "pt-PT-RaquelNeural": "pt-PT-RaquelNeural",
    "pt-PT-DuarteNeural": "pt-PT-DuarteNeural",
    # Russian
    "ru-RU-SvetlanaNeural": "ru-RU-SvetlanaNeural",
    "ru-RU-DmitryNeural": "ru-RU-DmitryNeural",
    # Arabic
    "ar-SA-ZariyahNeural": "ar-SA-ZariyahNeural",
    "ar-SA-HamedNeural": "ar-SA-HamedNeural",
    "ar-EG-SalmaNeural": "ar-EG-SalmaNeural",
    "ar-EG-ShakirNeural": "ar-EG-ShakirNeural",
    "ar-AE-FatimaNeural": "ar-AE-FatimaNeural",
    "ar-AE-HamdanNeural": "ar-AE-HamdanNeural",
    # Hindi
    "hi-IN-SwaraNeural": "hi-IN-SwaraNeural",
    "hi-IN-MadhurNeural": "hi-IN-MadhurNeural",
    # Indonesian
    "id-ID-GadisNeural": "id-ID-GadisNeural",
    "id-ID-ArdiNeural": "id-ID-ArdiNeural",
    # Malay
    "ms-MY-YasminNeural": "ms-MY-YasminNeural",
    "ms-MY-OsmanNeural": "ms-MY-OsmanNeural",
    # Italian
    "it-IT-IsabellaNeural": "it-IT-IsabellaNeural",
    "it-IT-GiuseppeMultilingualNeural": "it-IT-GiuseppeMultilingualNeural",
    # Dutch
    "nl-NL-ColetteNeural": "nl-NL-ColetteNeural",
    "nl-NL-MaartenNeural": "nl-NL-MaartenNeural",
    # Polish
    "pl-PL-AgnieszkaNeural": "pl-PL-AgnieszkaNeural",
    "pl-PL-MarekNeural": "pl-PL-MarekNeural",
    # Turkish
    "tr-TR-EmelNeural": "tr-TR-EmelNeural",
    "tr-TR-AhmetNeural": "tr-TR-AhmetNeural",
    # Ukrainian
    "uk-UA-PolinaNeural": "uk-UA-PolinaNeural",
    "uk-UA-OstapNeural": "uk-UA-OstapNeural",
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
    "it": "it-IT-IsabellaNeural",
    "nl": "nl-NL-ColetteNeural",
    "pl": "pl-PL-AgnieszkaNeural",
    "tr": "tr-TR-EmelNeural",
    "uk": "uk-UA-PolinaNeural",
}

# Canonical gender for every supported Edge TTS voice. This is the single
# source of truth so a male selection never silently swaps in a female
# voice when the primary provider is temporarily down.
VOICE_GENDERS = {
    # Vietnamese
    "vi-VN-HoaiMyNeural": "female",
    "vi-VN-NamMinhNeural": "male",
    # English
    "en-US-JennyNeural": "female",
    "en-US-GuyNeural": "male",
    "en-US-AriaNeural": "female",
    "en-US-AndrewNeural": "male",
    "en-US-AvaNeural": "female",
    "en-US-BrianNeural": "male",
    "en-US-EmmaNeural": "female",
    "en-US-MichelleNeural": "female",
    "en-US-RogerNeural": "male",
    "en-US-AnaNeural": "female",
    "en-GB-SoniaNeural": "female",
    "en-GB-RyanNeural": "male",
    "en-AU-NatashaNeural": "female",
    "en-AU-WilliamMultilingualNeural": "male",
    "en-IN-NeerjaNeural": "female",
    "en-IN-PrabhatNeural": "male",
    # Japanese
    "ja-JP-NanamiNeural": "female",
    "ja-JP-KeitaNeural": "male",
    # Korean
    "ko-KR-SunHiNeural": "female",
    "ko-KR-InJoonNeural": "male",
    "ko-KR-HyunsuMultilingualNeural": "male",
    # Chinese
    "zh-CN-XiaoxiaoNeural": "female",
    "zh-CN-YunxiNeural": "male",
    "zh-CN-YunjianNeural": "male",
    "zh-CN-XiaoyiNeural": "female",
    "zh-CN-YunyangNeural": "male",
    "zh-HK-HiuMaanNeural": "female",
    "zh-HK-WanLungNeural": "male",
    "zh-TW-HsiaoChenNeural": "female",
    "zh-TW-YunJheNeural": "male",
    # Thai
    "th-TH-PremwadeeNeural": "female",
    "th-TH-NiwatNeural": "male",
    # French
    "fr-FR-DeniseNeural": "female",
    "fr-FR-HenriNeural": "male",
    "fr-FR-EloiseNeural": "female",
    "fr-CA-SylvieNeural": "female",
    "fr-CA-ThierryNeural": "male",
    # German
    "de-DE-KatjaNeural": "female",
    "de-DE-ConradNeural": "male",
    "de-DE-AmalaNeural": "female",
    "de-AT-IngridNeural": "female",
    "de-AT-JonasNeural": "male",
    # Spanish
    "es-ES-ElviraNeural": "female",
    "es-ES-AlvaroNeural": "male",
    "es-MX-DaliaNeural": "female",
    "es-MX-JorgeNeural": "male",
    "es-AR-ElenaNeural": "female",
    "es-AR-TomasNeural": "male",
    # Portuguese
    "pt-BR-FranciscaNeural": "female",
    "pt-BR-AntonioNeural": "male",
    "pt-PT-RaquelNeural": "female",
    "pt-PT-DuarteNeural": "male",
    # Russian
    "ru-RU-SvetlanaNeural": "female",
    "ru-RU-DmitryNeural": "male",
    # Arabic
    "ar-SA-ZariyahNeural": "female",
    "ar-SA-HamedNeural": "male",
    "ar-EG-SalmaNeural": "female",
    "ar-EG-ShakirNeural": "male",
    "ar-AE-FatimaNeural": "female",
    "ar-AE-HamdanNeural": "male",
    # Hindi
    "hi-IN-SwaraNeural": "female",
    "hi-IN-MadhurNeural": "male",
    # Indonesian
    "id-ID-GadisNeural": "female",
    "id-ID-ArdiNeural": "male",
    # Malay
    "ms-MY-YasminNeural": "female",
    "ms-MY-OsmanNeural": "male",
    # Italian
    "it-IT-IsabellaNeural": "female",
    "it-IT-GiuseppeMultilingualNeural": "male",
    # Dutch
    "nl-NL-ColetteNeural": "female",
    "nl-NL-MaartenNeural": "male",
    # Polish
    "pl-PL-AgnieszkaNeural": "female",
    "pl-PL-MarekNeural": "male",
    # Turkish
    "tr-TR-EmelNeural": "female",
    "tr-TR-AhmetNeural": "male",
    # Ukrainian
    "uk-UA-PolinaNeural": "female",
    "uk-UA-OstapNeural": "male",
}

# Fallback voices per language (if primary fails). Each list contains
# voices ordered by the order the original (likely-still-most-common) one
# appears first, then the same-gender alternatives. Callers filter by
# gender so a male selection never silently swaps in a female voice.
VOICE_FALLBACKS = {
    "vi": ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural", "en-US-GuyNeural"],
    "en": [
        "en-US-JennyNeural", "en-US-AriaNeural", "en-US-AvaNeural", "en-US-EmmaNeural",
        "en-US-MichelleNeural", "en-US-AnaNeural", "en-GB-SoniaNeural", "en-AU-NatashaNeural",
        "en-IN-NeerjaNeural", "en-US-GuyNeural", "en-US-AndrewNeural", "en-US-BrianNeural",
        "en-US-RogerNeural", "en-GB-RyanNeural", "en-AU-WilliamMultilingualNeural", "en-IN-PrabhatNeural",
    ],
    "ja": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
    "ko": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural", "ko-KR-HyunsuMultilingualNeural"],
    "zh": [
        "zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural",
        "zh-HK-HiuMaanNeural", "zh-TW-HsiaoChenNeural",
        "zh-CN-YunxiNeural", "zh-CN-YunjianNeural", "zh-CN-YunyangNeural",
        "zh-HK-WanLungNeural", "zh-TW-YunJheNeural",
    ],
    "th": ["th-TH-PremwadeeNeural", "th-TH-NiwatNeural"],
    "fr": [
        "fr-FR-DeniseNeural", "fr-FR-EloiseNeural", "fr-CA-SylvieNeural",
        "fr-FR-HenriNeural", "fr-CA-ThierryNeural",
    ],
    "de": [
        "de-DE-KatjaNeural", "de-DE-AmalaNeural", "de-AT-IngridNeural",
        "de-DE-ConradNeural", "de-AT-JonasNeural",
    ],
    "es": [
        "es-ES-ElviraNeural", "es-MX-DaliaNeural", "es-AR-ElenaNeural",
        "es-ES-AlvaroNeural", "es-MX-JorgeNeural", "es-AR-TomasNeural",
    ],
    "pt": [
        "pt-BR-FranciscaNeural", "pt-PT-RaquelNeural",
        "pt-BR-AntonioNeural", "pt-PT-DuarteNeural",
    ],
    "ru": ["ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"],
    "ar": [
        "ar-SA-ZariyahNeural", "ar-EG-SalmaNeural", "ar-AE-FatimaNeural",
        "ar-SA-HamedNeural", "ar-EG-ShakirNeural", "ar-AE-HamdanNeural",
    ],
    "hi": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"],
    "id": ["id-ID-GadisNeural", "id-ID-ArdiNeural"],
    "ms": ["ms-MY-YasminNeural", "ms-MY-OsmanNeural"],
    "it": ["it-IT-IsabellaNeural", "it-IT-GiuseppeMultilingualNeural"],
    "nl": ["nl-NL-ColetteNeural", "nl-NL-MaartenNeural"],
    "pl": ["pl-PL-AgnieszkaNeural", "pl-PL-MarekNeural"],
    "tr": ["tr-TR-EmelNeural", "tr-TR-AhmetNeural"],
    "uk": ["uk-UA-PolinaNeural", "uk-UA-OstapNeural"],
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
    """Generate TTS audio using Edge TTS (Microsoft Edge voices).

    Performs up to ``EDGE_TTS_MAX_ATTEMPTS`` attempts per call with bounded
    exponential backoff so transient Edge TTS failures (rate-limit, network
    blip, "No audio was received") recover without the caller falling back to
    a different voice or gTTS.
    """
    edge_voice = get_edge_voice(voice)
    # Warn about language mismatches without changing speaker identity.
    text_lang = _detect_text_language(text)
    voice_lang = edge_voice.split("-")[0] if edge_voice else ""
    if text_lang and voice_lang and text_lang != voice_lang and text_lang != "auto":
        logger.warning(
            "Voice '%s' (%s) may not pronounce text in '%s' correctly; "
            "keeping the selected voice to preserve speaker identity",
            edge_voice, voice_lang, text_lang,
        )
    try:
        import edge_tts
    except ImportError:
        logger.error("edge-tts not installed. Please install: pip install edge-tts")
        raise

    last_error: Exception | None = None
    for attempt in range(EDGE_TTS_MAX_ATTEMPTS):
        try:
            communicate = edge_tts.Communicate(text, edge_voice, rate=rate)
            await communicate.save(output_path)
            return output_path
        except Exception as e:
            if getattr(e, "status", None) in (401, 403):
                raise TTSAccessError(
                    "Dịch vụ giọng đọc từ chối truy cập (401/403). "
                    "Đã dừng tạo giọng để tránh thử lại kéo dài. "
                    "Hãy cập nhật ứng dụng hoặc thử lại sau; giọng đã chọn được giữ nguyên."
                ) from e
            last_error = e
            if attempt < EDGE_TTS_MAX_ATTEMPTS - 1:
                wait = min(10.0, EDGE_TTS_RETRY_BASE_SECONDS * (2 ** attempt))
                logger.warning(
                    "Edge TTS attempt %d/%d failed for voice '%s': %s; retrying in %.1fs",
                    attempt + 1, EDGE_TTS_MAX_ATTEMPTS, edge_voice, e, wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.error(
                    "Edge TTS failed for voice '%s' after %d attempts: %s",
                    edge_voice, EDGE_TTS_MAX_ATTEMPTS, e,
                )
    assert last_error is not None
    raise last_error


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
    """Retry the selected voice only; never substitute a different speaker.

    The function name and target_lang argument remain for caller compatibility.
    """
    return await text_to_speech_edge(text, voice, output_path, rate)


async def _generate_segment_audio(index: int, segment: dict, voice: str,
                                  output_dir: str, rate: str, target_lang: str,
                                  semaphore: asyncio.Semaphore) -> dict | None:
    """Generate one segment while respecting the global TTS concurrency limit.

    Each segment keeps the selected voice, including retries.
    """
    text = segment.get("text", "").strip()
    if not text:
        return None

    segment_path = os.path.join(output_dir, f"seg_{index:04d}.mp3")
    async with semaphore:
        try:
            # Retry the selected voice with a bounded timeout.
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
        except TTSAccessError:
            raise
        except Exception as exc:
            logger.error(
                f"Failed to generate TTS for segment {index} with selected voice {voice}: {exc}"
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
                                 target_lang: str = "vi", progress_cb=None) -> list:
    """Generate all TTS segments concurrently while preserving timeline order.

    Reject incomplete batches instead of publishing missing speech.
    """
    os.makedirs(output_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(TTS_CONCURRENCY)
    indexed_segments = [
        (index, segment) for index, segment in enumerate(segments)
        if segment.get("text", "").strip()
    ]
    if not indexed_segments:
        logger.warning("No transcribed text segments to synthesize")
        return []

    logger.info(
        f"Generating {len(indexed_segments)} TTS segments concurrently (limit={TTS_CONCURRENCY})"
    )
    results = [None] * len(indexed_segments)
    completed = 0

    async def generate(position):
        index, segment = indexed_segments[position]
        result = await _generate_segment_audio(
            index, segment, voice, output_dir, rate, target_lang, semaphore,
        )
        return position, result

    async def run_batch(positions):
        nonlocal completed
        tasks = [asyncio.create_task(generate(position)) for position in positions]
        try:
            for task in asyncio.as_completed(tasks):
                position, result = await task
                results[position] = result
                if result is not None:
                    completed += 1
                    if progress_cb is not None:
                        await progress_cb(completed, len(indexed_segments))
        finally:
            # An access failure or cancellation must stop pending provider calls.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    await run_batch(range(len(indexed_segments)))
    # Retry only failed cues with the same bounded parallel pool and voice.
    for recovery_round in range(TTS_RECOVERY_ROUNDS):
        pending = [position for position, result in enumerate(results) if result is None]
        if not pending:
            break
        delay = TTS_RECOVERY_DELAY_SECONDS * (recovery_round + 1)
        logger.warning(
            "Retrying %d failed TTS cues with voice %s concurrently after %ss (round %d/%d)",
            len(pending), voice, delay, recovery_round + 1, TTS_RECOVERY_ROUNDS,
        )
        await asyncio.sleep(delay)
        await run_batch(pending)
    failed = sum(result is None for result in results)
    if failed:
        raise RuntimeError(
            f"Không tạo được {failed}/{len(indexed_segments)} đoạn lồng tiếng bằng giọng {voice}. "
            "Hệ thống giữ nguyên giọng đã chọn. Vui lòng thử lại."
        )
    return results


def _atempo_chain(speed: float) -> str:
    """Build an ffmpeg atempo filter chain that achieves the requested speed.

    The atempo filter accepts values in [0.5, 2.0] only, so a larger speed-up
    is split into chained atempo nodes. ``atempo=2.0,atempo=2.0`` reproduces
    4x speed, for example. Very high speeds degrade audio quality, but the
    pipeline only uses this when the dubbed voice would otherwise overlap
    the next cue; the alternative (silent drop or hard cut) is worse.
    """
    if speed <= 0:
        return "anull"
    chain = []
    remaining = speed
    while remaining > 2.0:
        chain.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        chain.append("atempo=0.5")
        remaining *= 2.0
    chain.append(f"atempo={remaining:.4f}")
    return ",".join(chain)


def merge_tts_segments(audio_files: list, total_duration: float,
                        output_path: str) -> tuple[str, list[tuple[int, float, float]]]:
    """Concatenate per-segment TTS audio into one dubbed track.

    The previous implementation passed every input file inline as
    ``-i /path/to/seg_NNNN.mp3`` arguments to a single ``ffmpeg`` invocation.
    On Windows the command line is capped at 32,768 characters, so a video
    with ~300+ subtitles (each input path ~100 chars) trips WinError 206 and
    the job aborts. This implementation stages each segment into a padded
    WAV (silence prefix matching the cue start) and then concatenates them
    so the segment timings match the original SRT cues. The ffmpeg command
    is one short ``-f concat -i list.txt`` call regardless of segment count.

    Overlap handling: when a translated segment runs longer than the source
    cue, its natural audio would push past the next cue's start and the
    previous behaviour stacked segments end-to-end (gap dropped to 0), which
    compressed every following cue, made the voice unnaturally fast, and
    left the on-screen subtitle drifting later and later than the audio.
    The current version applies ``atempo`` to the *next* segment so it
    fits inside the time window the previous one left: each segment that
    would otherwise start mid-sentence is sped up enough to land on its
    nominal SRT start time. Segments that already fit keep their natural
    speed, so the voice still sounds normal in the easy stretches and only
    speeds up where the translation genuinely overflows.

    Returns a tuple of ``(output_path, actual_segments)`` where each entry in
    ``actual_segments`` is ``(cue_index, actual_start, actual_end)`` giving
    the absolute time the segment's audio occupies in the merged track.
    Translations are usually longer than the source phrase, so the actual
    audio length commonly exceeds the original SRT window; callers that
    build the on-screen subtitle SRT should use this timing so the burn-in
    text stays in sync with the dubbed voice.
    """
    if not audio_files:
        logger.warning("No audio files to merge")
        return "", []
    if total_duration <= 0:
        raise ValueError("Video duration must be greater than zero before merging TTS")

    concat_list_path = output_path + ".concat.txt"
    padded_dir = output_path + ".padded"
    os.makedirs(padded_dir, exist_ok=True)
    actual_segments: list[tuple[int, float, float]] = []
    try:
        sorted_files = sorted(
            (af for af in audio_files if af.get("audio_path")
             and os.path.exists(af["audio_path"])),
            key=lambda af: af.get("start", 0.0),
        )
        if not sorted_files:
            logger.warning("No TTS audio files available to merge")
            return "", []

        # Pass 1: emit each segment at its natural pace. We use
        # ``previous_end`` (the actual end of the previous segment in the
        # merged track) as the running anchor. The silence prefix is
        # always the difference between the previous segment's end and
        # this cue's nominal start, capped at 0 (no negative silence -
        # that would mean the audio of this segment has to start before
        # the previous one ends, which the concat demuxer cannot do).
        # When the previous segment is still playing at this cue's start,
        # the silence prefix is 0 and this segment is queued right after
        # the previous one. Pass 2 will speed the previous segment up
        # later so this segment can begin at its SRT start time without
        # the 50ms safety gap that the previous implementation used.
        #
        # The previous 50ms guard was the source of the subtitle drift
        # the user reported: every segment's ``actual_start`` was padded
        # 50ms past the SRT ``start``, and that error compounded through
        # the cue list, so the on-screen subtitle appeared noticeably
        # later than the dubbed voice.
        #
        # We keep two files per segment: ``audio_path`` (the TTS MP3 we
        # downloaded, never modified) and a working file that holds the
        # atempo-adjusted audio after pass 2. The padded file is built
        # last in pass 3 from the working audio + the final silence
        # prefix, so re-pad never duplicates the audio.
        build_specs: list[dict] = []  # one entry per segment, post-pass-1 state
        previous_end = 0.0
        for i, af in enumerate(sorted_files):
            audio_path = af["audio_path"]
            working_path = os.path.join(padded_dir, f"audio_{i:04d}.wav")
            padded_path = os.path.join(padded_dir, f"padded_{i:04d}.wav")
            start_seconds = max(float(af.get("start", 0.0)), 0.0)
            # Normalize the TTS MP3 into a 44.1kHz stereo WAV the rest
            # of the pipeline can probe and re-encode cheaply. Without
            # this the concat demuxer would still work, but ``ffprobe``
            # round-trips on MP3 metadata add a few hundred milliseconds
            # per cue on long videos.
            subprocess.run([
                "ffmpeg", "-i", audio_path,
                "-ar", "44100", "-ac", "2",
                "-y", working_path,
            ], capture_output=True, check=True, **hidden_subprocess_kwargs())
            segment_duration = _probe_duration_seconds(working_path)
            # ``silence_prefix`` is exactly the gap between the previous
            # segment's end and this cue's nominal start. ``max(..., 0)``
            # drops any negative gap (overlap) to zero so the concat
            # demuxer can still join the files; the overlap is fixed in
            # pass 2 by atempo on the offending segment.
            silence_prefix = max(start_seconds - previous_end, 0.0)
            try:
                cue_index = int(af.get("index", i))
            except (TypeError, ValueError):
                cue_index = i
            actual_start = previous_end + silence_prefix
            actual_end = actual_start + segment_duration
            build_specs.append({
                "working_path": working_path,
                "padded_path": padded_path,
                "cue_index": cue_index,
                "start_seconds": start_seconds,
                "natural_duration": segment_duration,
                "silence_prefix": silence_prefix,
                "actual_start": actual_start,
                "actual_end": actual_end,
            })
            previous_end = actual_end

        # Pass 2: detect overlaps and speed up the offending segment.
        # ``actual_end`` of segment N can land after ``start_seconds`` of
        # segment N+1; that means segment N is still playing when the next
        # cue is supposed to start. We re-emit segment N with atempo so it
        # ends exactly at ``start_seconds`` (the next cue's nominal start)
        # rather than its natural ``actual_end``, then anchor every later
        # segment that has slack back to its SRT ``start_seconds`` so the
        # rebuilt subtitle SRT lines up with the on-disk audio.
        for i, spec in enumerate(build_specs):
            # Where does this segment have to end? Either the next cue's
            # nominal start (most cases) or the video's end (last cue).
            # Capping at ``total_duration`` matters for the final cue: if
            # it overruns the video, we want atempo to land it on the
            # actual end of the track rather than the trimmed cut point.
            if i + 1 < len(build_specs):
                required_end = build_specs[i + 1]["start_seconds"]
            else:
                required_end = total_duration
            overlap_window = spec["actual_end"] - required_end
            if overlap_window <= 0.0:
                # The next cue (or the end of the file) starts after this
                # segment finishes naturally, so no atempo is needed.
                continue
            # Available time: how much of the segment we can keep before
            # the required end. ``actual_start`` is where the audio really
            # begins (after the silence prefix), and we want it to end at
            # ``required_end`` (the next cue's start or the video end).
            available = required_end - spec["actual_start"]
            natural = spec["natural_duration"]
            if available <= 0.0 or natural <= 0.0:
                # Not enough room to even start the audio before the next
                # cue. Truncate to a short click; better than total overlap.
                available = 0.0
            speed = natural / available if available > 0 else 4.0
            # Cap at 4x; above that the voice becomes unintelligible and
            # the alignment is barely better than the previous drop-gap
            # behavior. We do still apply the cap so the audio has a
            # chance of fitting, even if imperfectly.
            if speed > 4.0:
                logger.warning(
                    "Cue %s is %.2fs but only %.2fs of headroom remains; "
                    "capping speed-up at 4x (audio will still slightly "
                    "overlap the next cue)",
                    spec["cue_index"], natural, available,
                )
                speed = 4.0
            if speed <= 1.001:
                # Within 0.1% of 1x: leave the segment as is. The overlap
                # is small enough that the small drift is inaudible.
                continue
            logger.info(
                "Cue %s overruns the required end %.2fs by %.2fs; applying "
                "atempo %.2fx to fit it inside the cue window",
                spec["cue_index"], required_end, overlap_window, speed,
            )
            atempo_filter = _atempo_chain(speed)
            new_actual_end = spec["actual_start"] + (natural / speed)
            # Re-encode the working audio with atempo. The working file
            # only holds the audio (no silence prefix), so re-running
            # atempo here just changes its duration; pass 3 will wrap
            # the new silence around it. ffmpeg refuses to write to the
            # same file it reads, so we stage the output in a sibling
            # WAV temp file and atomically swap it in. The temp file
            # must keep the ``.wav`` extension so ffmpeg picks the WAV
            # muxer - naming it ``audio_0002.wav.tmp`` (or anything
            # without a known container extension) makes the muxer
            # refuse to open it.
            working_dir = os.path.dirname(spec["working_path"])
            temp_out = os.path.join(working_dir, f"{spec['cue_index']:04d}_atempo.tmp.wav")
            subprocess.run([
                "ffmpeg",
                "-i", spec["working_path"],
                "-af", atempo_filter,
                "-ar", "44100", "-ac", "2",
                "-y", temp_out,
            ], capture_output=True, check=True, **hidden_subprocess_kwargs())
            os.replace(temp_out, spec["working_path"])
            spec["actual_end"] = new_actual_end
            # Anchor the next cue to its SRT start: atempo just pulled
            # this segment's end back to ``required_end`` (== the next
            # cue's SRT start), so the next segment's silence prefix is
            # now exactly zero and ``actual_start`` snaps to the SRT
            # start. The duration of the next segment is preserved by
            # shifting its end by the same delta.
            if i + 1 < len(build_specs):
                next_spec = build_specs[i + 1]
                delta = next_spec["actual_start"] - next_spec["start_seconds"]
                if delta != 0.0:
                    next_spec["actual_start"] = next_spec["start_seconds"]
                    next_spec["actual_end"] -= delta
            # Pull every later cue back to its SRT start as well. Each
            # one had its ``actual_start`` pushed forward by the
            # overlap; once the overlap is gone, the slack can be
            # absorbed. We cap at the SRT start to avoid overshooting.
            for j in range(i + 2, len(build_specs)):
                later = build_specs[j]
                delta = later["actual_start"] - later["start_seconds"]
                if delta > 0.0:
                    later["actual_start"] = later["start_seconds"]
                    later["actual_end"] -= delta

        # Pass 3: build each padded file from the (possibly atempo'd)
        # working audio + the final silence prefix. We never re-pad an
        # already-padded file because doing so would double-count the
        # audio inside it. ``actual_start`` and ``actual_end`` are
        # already in their final positions thanks to pass 2, so the
        # silence prefix is simply ``actual_start - previous_end`` (>= 0).
        list_lines: list[str] = []
        previous_end = 0.0
        for spec in build_specs:
            silence_prefix = max(spec["actual_start"] - previous_end, 0.0)
            # Match the millisecond precision used by the silence generator.
            silence_prefix = round(silence_prefix, 3)
            actual_start = previous_end + silence_prefix
            speech_duration = _probe_duration_seconds(spec["working_path"])
            if silence_prefix > 0.0:
                subprocess.run([
                    "ffmpeg",
                    "-f", "lavfi", "-i", f"aevalsrc=0:d={silence_prefix:.3f}:s=44100:c=mono",
                    "-i", spec["working_path"],
                    "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                    "-map", "[out]",
                    "-ar", "44100", "-ac", "2",
                    "-y", spec["padded_path"],
                ], capture_output=True, check=True, **hidden_subprocess_kwargs())
            else:
                # No silence prefix; the working audio *is* the padded
                # file (a direct copy is enough since the format
                # already matches).
                subprocess.run([
                    "ffmpeg",
                    "-i", spec["working_path"],
                    "-ar", "44100", "-ac", "2",
                    "-y", spec["padded_path"],
                ], capture_output=True, check=True, **hidden_subprocess_kwargs())
            spec["silence_prefix"] = silence_prefix
            list_lines.append(f"file '{_escape_ffmpeg_path(spec['padded_path'])}'")
            spec["actual_start"] = actual_start
            spec["actual_end"] = min(actual_start + speech_duration, total_duration)
            previous_end += _probe_duration_seconds(spec["padded_path"])

        # Snapshot the final positions for the caller. ``actual_segments``
        # must reflect what the on-disk audio actually contains so the
        # rebuilt subtitle SRT lines up with the voice.
        actual_segments = [
            (spec["cue_index"], spec["actual_start"], spec["actual_end"])
            for spec in build_specs
            if spec["actual_start"] < total_duration
        ]

        with open(concat_list_path, "w", encoding="utf-8") as f:
            f.write("\n".join(list_lines) + "\n")

        # Trim the concatenated stream to the video duration so we do not
        # leak audio past the last cue.
        subprocess.run([
            "ffmpeg",
            "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-af", f"atrim=0:{total_duration:.3f},asetpts=PTS-STARTPTS",
            "-ar", "44100", "-ac", "2",
            "-y", output_path,
        ], capture_output=True, check=True, **hidden_subprocess_kwargs())
    finally:
        if os.path.isdir(padded_dir):
            shutil.rmtree(padded_dir, ignore_errors=True)
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)

    return output_path, actual_segments


def _escape_ffmpeg_path(path: str) -> str:
    """Escape a path for use inside an ffmpeg concat list entry.

    The concat demuxer treats single quotes as the only safe string delimiter,
    so any embedded single quote has to be escaped. The resulting string is
    wrapped in single quotes by the caller.
    """
    return path.replace("'", "'\\''")


def _probe_duration_seconds(audio_path: str) -> float:
    """Return the duration of an audio file in seconds, falling back to 0.

    Used by ``merge_tts_segments`` to know how much real audio time each
    padded segment contributes so the gap calculation for the next segment
    stays correct. A failure here only means we use a slightly larger
    inter-segment gap than ideal, which sounds as silence rather than as
    a glitch.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ],
            capture_output=True, text=True, timeout=10,
            **hidden_subprocess_kwargs(),
        )
        return float(result.stdout.strip() or 0.0)
    except (ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        return 0.0
