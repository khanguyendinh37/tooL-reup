import os
import asyncio
import logging
import subprocess

logger = logging.getLogger(__name__)

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


def get_edge_voice(voice: str) -> str:
    """Map frontend voice ID to Edge TTS voice."""
    if voice in EDGE_TTS_VOICES:
        return EDGE_TTS_VOICES[voice]
    # Fallback: extract language prefix and use default
    lang = voice.split("-")[0] if voice else "en"
    return EDGE_TTS_VOICES.get(lang, "en-US-JennyNeural")


def speed_to_rate(speed: float) -> str:
    """Convert speed multiplier (0.5-2.0) to Edge TTS rate format (+0%, +50%, -20%, etc.)."""
    if speed == 1.0:
        return "+0%"
    pct = (speed - 1.0) * 100
    return f"{pct:+.0f}%"


async def text_to_speech(text: str, voice: str, output_path: str, rate: str = "+0%") -> str:
    """Generate TTS audio using Edge TTS (Microsoft Edge voices).

    Args:
        text: Text to synthesize
        voice: Voice ID (e.g., 'vi-VN-NamMinhNeural', 'vi-VN-HoaiMyNeural')
        output_path: Output file path (will be .mp3)
        rate: Speech rate adjustment (e.g., '+0%', '+50%', '-20%')
    """
    edge_voice = get_edge_voice(voice)

    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, edge_voice, rate=rate)
        await communicate.save(output_path)
        return output_path
    except ImportError:
        logger.error("edge-tts not installed. Please install: pip install edge-tts")
        raise
    except Exception as e:
        logger.error(f"Edge TTS failed for voice '{edge_voice}': {e}")
        raise


async def generate_dubbing_audio(segments: list, voice: str,
                                  output_dir: str, rate: str = "+0%") -> list:
    os.makedirs(output_dir, exist_ok=True)
    audio_files = []

    for i, seg in enumerate(segments):
        if not seg["text"].strip():
            continue

        seg_path = os.path.join(output_dir, f"seg_{i:04d}.mp3")
        try:
            await text_to_speech(seg["text"], voice, seg_path, rate)
            audio_files.append({
                "index": i,
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
                "audio_path": seg_path,
            })
        except Exception as e:
            logger.error(f"Failed to generate TTS for segment {i}: {e}")

    return audio_files


def merge_tts_segments(audio_files: list, total_duration: float,
                        output_path: str) -> str:
    if not audio_files:
        logger.warning("No audio files to merge")
        return ""

    silence_path = output_path + ".silence.wav"
    subprocess.run(
        ["ffmpeg", "-f", "lavfi", "-i",
         f"anullsrc=r=44100:cl=mono:d={total_duration}",
         "-y", silence_path],
        capture_output=True, check=True
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

    subprocess.run(cmd, capture_output=True, check=True)

    if os.path.exists(silence_path):
        os.remove(silence_path)

    return output_path