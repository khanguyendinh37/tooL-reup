import os
import subprocess
import json


def extract_audio(video_path: str, output_path: str) -> str:
    subprocess.run(
        ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
         "-ar", "16000", "-ac", "1", output_path, "-y"],
        capture_output=True, check=True
    )
    return output_path


def transcribe_with_whisper(audio_path: str, model_size: str = "small",
                             language: str = None, device: str = "auto") -> dict:
    from faster_whisper import WhisperModel

    if device == "auto":
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"

    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    kwargs = {}
    if language:
        kwargs["language"] = language

    segments_iter, info = model.transcribe(audio_path, beam_size=5, **kwargs)

    segments = []
    full_text = ""
    for segment in segments_iter:
        segments.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
        })
        full_text += segment.text.strip() + " "

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
