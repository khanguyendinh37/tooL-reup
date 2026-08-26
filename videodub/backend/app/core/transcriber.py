import os
import subprocess
import json

from app.core.process_utils import hidden_subprocess_kwargs


def extract_audio(video_path: str, output_path: str) -> str:
    subprocess.run(
        ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
         "-ar", "16000", "-ac", "1", output_path, "-y"],
        capture_output=True, check=True, **hidden_subprocess_kwargs()
    )
    return output_path


def _normalize_whisper_language(language: str | None) -> str | None:
    """Normalize UI language codes to the codes accepted by faster-whisper."""
    if not language:
        return None

    normalized = language.strip().lower()
    aliases = {
        "zh-cn": "zh",
        "zh-tw": "zh",
        "zh-hans": "zh",
        "zh-hant": "zh",
        "chinese": "zh",
    }
    return aliases.get(normalized, normalized) or None


def transcribe_with_whisper(audio_path: str, model_size: str = "small",
                             language: str = None, device: str = "auto") -> dict:
    from faster_whisper import WhisperModel

    if device == "auto":
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"

    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    requested_language = _normalize_whisper_language(language)
    transcribe_options = {
        "beam_size": 5,
        "temperature": 0.0,
        # VAD prevents music/noise-only intervals from becoming invented words.
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 500},
        # Independent windows are less likely to carry a previous hallucination
        # into the next subtitle segment.
        "condition_on_previous_text": False,
    }
    if requested_language:
        transcribe_options["language"] = requested_language

    segments_iter, info = model.transcribe(audio_path, **transcribe_options)

    segments = []
    full_text = ""
    for segment in segments_iter:
        text = segment.text.strip()
        if not text:
            continue
        segments.append({
            "start": segment.start,
            "end": segment.end,
            "text": text,
        })
        full_text += text + " "

    return {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "segments": segments,
        "text": full_text.strip(),
    }


def segments_to_srt(segments: list, output_path: str) -> str:
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = format_timestamp(seg["start"])
            end = format_timestamp(seg["end"])
            f.write(f"{i}\n{start} --> {end}\n{seg['text']}\n\n")
    return output_path


def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
