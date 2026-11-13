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
# Multi-hour videos have thousands of cues, so a burst of Edge TTS throttling
# is likely somewhere in the run. They get more, longer-spaced recovery rounds
# before the job is failed (the finished cues are kept on disk for a retry).
TTS_LONG_JOB_SEGMENTS = 300
TTS_LONG_RECOVERY_ROUNDS = 5
TTS_RECOVERY_MAX_DELAY_SECONDS = 120
TTS_MANIFEST_NAME = "manifest.json"

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
    result = {
        "index": index,
        "start": segment["start"],
        "end": segment["end"],
        "text": text,
        "audio_path": segment_path,
    }
    # A finished cue from an interrupted run is reused. Files are only ever
    # moved into place once complete, so an existing file is never partial.
    if os.path.isfile(segment_path) and os.path.getsize(segment_path) > 0:
        return result
    partial_path = segment_path + ".part.mp3"
    async with semaphore:
        try:
            # Retry the selected voice with a bounded timeout.
            await asyncio.wait_for(
                text_to_speech_with_fallback(text, voice, partial_path, rate, target_lang),
                timeout=TTS_SEGMENT_TIMEOUT_SECONDS,
            )
            if os.path.exists(partial_path):
                os.replace(partial_path, segment_path)
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


def prepare_tts_directory(output_dir: str, cache_key: dict) -> None:
    """Keep cached cue audio only when it was made from the same inputs.

    ``cache_key`` should identify the translated text, voice and rate. If any
    of them changed since the files were written, the stale cues are removed
    so a retry never mixes two voices or two translations.
    """
    import json

    manifest_path = os.path.join(output_dir, TTS_MANIFEST_NAME)
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            previous = json.load(handle)
    except (OSError, ValueError):
        previous = None
    if previous != cache_key and os.path.isdir(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(cache_key, handle)


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
    recovery_rounds = (
        TTS_LONG_RECOVERY_ROUNDS if len(indexed_segments) >= TTS_LONG_JOB_SEGMENTS
        else TTS_RECOVERY_ROUNDS
    )
    for recovery_round in range(recovery_rounds):
        pending = [position for position, result in enumerate(results) if result is None]
        if not pending:
            break
        delay = min(
            TTS_RECOVERY_DELAY_SECONDS * (2 ** recovery_round if recovery_rounds > TTS_RECOVERY_ROUNDS
                                          else recovery_round + 1),
            TTS_RECOVERY_MAX_DELAY_SECONDS,
        )
        logger.warning(
            "Retrying %d failed TTS cues with voice %s concurrently after %ss (round %d/%d)",
            len(pending), voice, delay, recovery_round + 1, recovery_rounds,
        )
        await asyncio.sleep(delay)
        await run_batch(pending)
    failed = sum(result is None for result in results)
    if failed:
        raise RuntimeError(
            f"Không tạo được {failed}/{len(indexed_segments)} đoạn lồng tiếng bằng giọng {voice}. "
            "Hệ thống giữ nguyên giọng đã chọn. Các đoạn đã tạo được giữ lại; "
            "bấm Thử lại để chỉ tạo tiếp các đoạn còn thiếu."
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


MERGE_SAMPLE_RATE = 44100
MERGE_CHANNELS = 2
MERGE_BYTES_PER_FRAME = MERGE_CHANNELS * 2  # s16le
MERGE_DECODE_WORKERS = 6
MERGE_DECODE_WINDOW = 48
MERGE_MAX_SPEEDUP = 4.0


def _decode_segment_pcm(audio_path: str, speed: float = 1.0) -> bytes:
    """Decode one TTS file to raw s16le PCM, optionally time-stretched."""
    cmd = ["ffmpeg", "-v", "error", "-i", audio_path]
    if speed > 1.001:
        cmd.extend(["-af", _atempo_chain(speed)])
    cmd.extend([
        "-f", "s16le", "-acodec", "pcm_s16le",
        "-ar", str(MERGE_SAMPLE_RATE), "-ac", str(MERGE_CHANNELS), "pipe:1",
    ])
    result = subprocess.run(cmd, capture_output=True, check=True, **hidden_subprocess_kwargs())
    data = result.stdout
    return data[:len(data) - len(data) % MERGE_BYTES_PER_FRAME]


def merge_tts_segments(audio_files: list, total_duration: float,
                        output_path: str) -> tuple[str, list[tuple[int, float, float]]]:
    """Place per-segment TTS audio on the video timeline as one WAV track.

    Each segment is decoded straight to PCM (one ffmpeg call, run in a small
    thread pool) and written into a single raw stream with exact sample-count
    silence between cues. The old implementation spawned four or five
    ffmpeg/ffprobe processes per cue sequentially, which took close to an hour
    for a multi-hour video with thousands of cues.

    Overlap handling: when a translated segment runs longer than the gap until
    the next cue, it is sped up with ``atempo`` (capped at 4x) so it ends on
    the next cue's start. If even 4x does not fit, the next cue starts right
    after it. Segments that fit keep their natural speed.

    Returns ``(output_path, actual_segments)`` where each entry is
    ``(cue_index, actual_start, actual_end)``: the absolute time the segment's
    audio occupies in the merged track, used to rebuild the on-screen SRT.
    """
    if not audio_files:
        logger.warning("No audio files to merge")
        return "", []
    if total_duration <= 0:
        raise ValueError("Video duration must be greater than zero before merging TTS")

    sorted_files = sorted(
        (af for af in audio_files if af and af.get("audio_path")
         and os.path.exists(af["audio_path"])),
        key=lambda af: float(af.get("start", 0.0) or 0.0),
    )
    if not sorted_files:
        logger.warning("No TTS audio files available to merge")
        return "", []

    frame_seconds = 1.0 / MERGE_SAMPLE_RATE
    total_frames = int(round(total_duration * MERGE_SAMPLE_RATE))
    starts = [max(float(af.get("start", 0.0) or 0.0), 0.0) for af in sorted_files]
    raw_path = output_path + ".pcm"
    actual_segments: list[tuple[int, float, float]] = []
    written_frames = 0

    from concurrent.futures import ThreadPoolExecutor

    try:
        with open(raw_path, "wb") as raw, ThreadPoolExecutor(MERGE_DECODE_WORKERS) as pool:
            for window_start in range(0, len(sorted_files), MERGE_DECODE_WINDOW):
                window = sorted_files[window_start:window_start + MERGE_DECODE_WINDOW]
                decoded = list(pool.map(lambda af: _decode_segment_pcm(af["audio_path"]), window))
                for offset, (af, pcm) in enumerate(zip(window, decoded)):
                    i = window_start + offset
                    if written_frames >= total_frames:
                        break
                    try:
                        cue_index = int(af.get("index", i))
                    except (TypeError, ValueError):
                        cue_index = i
                    start_frame = max(int(round(starts[i] * MERGE_SAMPLE_RATE)), written_frames)
                    required_end = starts[i + 1] if i + 1 < len(sorted_files) else total_duration
                    required_frames = int(round(required_end * MERGE_SAMPLE_RATE)) - start_frame
                    natural_frames = len(pcm) // MERGE_BYTES_PER_FRAME
                    if natural_frames > required_frames and natural_frames > 0:
                        speed = (natural_frames / required_frames) if required_frames > 0 else MERGE_MAX_SPEEDUP
                        if speed > MERGE_MAX_SPEEDUP:
                            logger.warning(
                                "Cue %s needs %.2fx to fit before the next cue; capping at %.0fx "
                                "(the next cue will start slightly late)",
                                cue_index, speed, MERGE_MAX_SPEEDUP,
                            )
                            speed = MERGE_MAX_SPEEDUP
                        if speed > 1.001:
                            pcm = _decode_segment_pcm(af["audio_path"], speed)
                    frames = len(pcm) // MERGE_BYTES_PER_FRAME
                    # Silence up to the cue start, then the speech, both clipped
                    # to the video length.
                    silence = start_frame - written_frames
                    if silence > 0:
                        raw.write(bytes(silence * MERGE_BYTES_PER_FRAME))
                        written_frames += silence
                    frames = min(frames, total_frames - written_frames)
                    if frames <= 0:
                        break
                    raw.write(pcm[:frames * MERGE_BYTES_PER_FRAME])
                    actual_segments.append((
                        cue_index,
                        written_frames * frame_seconds,
                        (written_frames + frames) * frame_seconds,
                    ))
                    written_frames += frames
                else:
                    continue
                break

        # rf64 keeps the WAV valid beyond 4 GB (about 6.7 hours of stereo).
        subprocess.run([
            "ffmpeg", "-v", "error",
            "-f", "s16le", "-ar", str(MERGE_SAMPLE_RATE), "-ac", str(MERGE_CHANNELS),
            "-i", raw_path, "-c:a", "pcm_s16le", "-rf64", "auto",
            "-y", output_path,
        ], capture_output=True, check=True, **hidden_subprocess_kwargs())
    finally:
        if os.path.exists(raw_path):
            os.remove(raw_path)

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
