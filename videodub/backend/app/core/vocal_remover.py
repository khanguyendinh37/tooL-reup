import json
import subprocess
import os
import shutil
import logging
import sys
import tempfile
import threading
import time
from typing import Callable, Optional

from app.core.process_utils import hidden_subprocess_kwargs

logger = logging.getLogger(__name__)

# Demucs keeps the whole separated track in memory (4 sources x stereo x
# float32), so a multi-hour input needs 10+ GB of RAM and is killed by the OS.
# Long inputs are separated in fixed windows instead. Each window is extended
# by ``DEMUCS_CHUNK_OVERLAP_SECONDS`` on both sides and the overlap is trimmed
# away afterwards, so every kept sample sits in the interior of a Demucs run
# and the joins do not click.
DEMUCS_CHUNK_SECONDS = float(os.getenv("VIDEODUB_DEMUCS_CHUNK_SECONDS", "600"))
DEMUCS_CHUNK_OVERLAP_SECONDS = 2.0
# Demucs on CPU runs at roughly 0.3-1x realtime. The timeout only exists to
# catch a hung worker, so it is generous and scales with the chunk length.
DEMUCS_TIMEOUT_FACTOR = 8.0
DEMUCS_MIN_TIMEOUT_SECONDS = 600
SAMPLE_RATE = 44100
STEMS = ("vocals", "no_vocals")
DONE_MARKER = "done.json"


class VocalSeparationCancelled(Exception):
    """Raised when the caller asked to stop between or during Demucs runs."""


def demucs_command(arguments: list[str]) -> list[str]:
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--demucs-worker', *arguments]
    return [sys.executable, '-m', 'demucs.separate', *arguments]


def _probe_duration(path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=60, **hidden_subprocess_kwargs(),
        )
        return float(result.stdout.strip() or 0.0)
    except (ValueError, subprocess.SubprocessError, OSError):
        return 0.0


def _source_fingerprint(video_path: str) -> dict:
    stat = os.stat(video_path)
    return {"size": stat.st_size, "mtime": int(stat.st_mtime)}


def _run_cancellable(cmd: list[str], timeout: float,
                     cancel_event: Optional[threading.Event]) -> tuple[int, str]:
    """Run a subprocess that can be killed by ``cancel_event``.

    Demucs prints tqdm progress bars to stderr; piping that without draining
    it can fill the pipe and deadlock, so stderr goes to a temporary file.
    """
    with tempfile.TemporaryFile(mode="w+b") as log:
        process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=log, **hidden_subprocess_kwargs(),
        )
        deadline = time.monotonic() + timeout
        try:
            while True:
                try:
                    returncode = process.wait(timeout=1.0)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if cancel_event is not None and cancel_event.is_set():
                    raise VocalSeparationCancelled()
                if time.monotonic() > deadline:
                    raise subprocess.TimeoutExpired(cmd, timeout)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        log.seek(0)
        output = log.read()[-4000:].decode("utf-8", errors="replace")
    return returncode, output


def _ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", *args],
                   capture_output=True, check=True, **hidden_subprocess_kwargs())


def _run_demucs(audio_path: str, separated_dir: str, duration: float,
                cancel_event: Optional[threading.Event]) -> dict:
    """Separate one file and return its vocals/no_vocals paths."""
    timeout = max(DEMUCS_MIN_TIMEOUT_SECONDS, duration * DEMUCS_TIMEOUT_FACTOR)
    returncode, stderr = _run_cancellable(
        demucs_command(["--two-stems", "vocals", "-o", separated_dir, audio_path]),
        timeout, cancel_event,
    )
    if returncode != 0:
        raise RuntimeError(f"Demucs failed: {stderr}")
    track_dir = os.path.join(
        separated_dir, "htdemucs", os.path.splitext(os.path.basename(audio_path))[0],
    )
    paths = {stem: os.path.join(track_dir, f"{stem}.wav") for stem in STEMS}
    if not os.path.exists(paths["vocals"]):
        raise RuntimeError("Demucs did not produce a vocals stem")
    if not os.path.exists(paths["no_vocals"]):
        _rebuild_no_vocals(track_dir, paths["no_vocals"])
    return paths


def _rebuild_no_vocals(track_dir: str, no_vocals_path: str) -> None:
    """Older Demucs builds may emit four stems; mix the non-vocal ones."""
    inputs = [
        os.path.join(track_dir, f"{name}.wav") for name in ("other", "drums", "bass")
        if os.path.exists(os.path.join(track_dir, f"{name}.wav"))
    ]
    if not inputs:
        raise RuntimeError("Demucs did not produce a background stem")
    cmd = []
    for inp in inputs:
        cmd.extend(["-i", inp])
    labels = "".join(f"[{i}:a]" for i in range(len(inputs)))
    cmd.extend([
        "-filter_complex", f"{labels}amix=inputs={len(inputs)}:duration=first:normalize=0[out]",
        "-map", "[out]", "-y", no_vocals_path,
    ])
    _ffmpeg(cmd)


def _separate_in_chunks(audio_path: str, separated_dir: str, duration: float,
                        cancel_event: Optional[threading.Event],
                        progress_cb: Optional[Callable[[int, int], None]]) -> dict:
    """Separate a long file window by window and join the trimmed stems."""
    chunk_dir = os.path.join(separated_dir, "chunks")
    os.makedirs(chunk_dir, exist_ok=True)
    chunk_count = max(int(-(-duration // DEMUCS_CHUNK_SECONDS)), 1)
    stem_parts: dict[str, list[str]] = {stem: [] for stem in STEMS}
    logger.info("Separating %.0fs of audio in %d Demucs chunks", duration, chunk_count)

    for index in range(chunk_count):
        keep_start = index * DEMUCS_CHUNK_SECONDS
        keep_length = min(DEMUCS_CHUNK_SECONDS, duration - keep_start)
        if keep_length <= 0:
            break
        read_start = max(keep_start - DEMUCS_CHUNK_OVERLAP_SECONDS, 0.0)
        read_end = min(keep_start + keep_length + DEMUCS_CHUNK_OVERLAP_SECONDS, duration)
        lead_in = keep_start - read_start

        # Chunks already separated by an interrupted run are reused.
        trimmed = {stem: os.path.join(chunk_dir, f"{stem}_{index:04d}.wav") for stem in STEMS}
        if not all(os.path.isfile(path) and os.path.getsize(path) > 0 for path in trimmed.values()):
            chunk_audio = os.path.join(chunk_dir, f"chunk_{index:04d}.wav")
            _ffmpeg([
                "-ss", f"{read_start:.3f}", "-t", f"{read_end - read_start:.3f}",
                "-i", audio_path, "-acodec", "pcm_s16le",
                "-ar", str(SAMPLE_RATE), "-ac", "2", "-y", chunk_audio,
            ])
            stems = _run_demucs(chunk_audio, separated_dir, read_end - read_start, cancel_event)
            for stem in STEMS:
                partial = trimmed[stem] + ".part.wav"
                _ffmpeg([
                    "-ss", f"{lead_in:.3f}", "-t", f"{keep_length:.3f}",
                    "-i", stems[stem], "-acodec", "pcm_s16le",
                    "-ar", str(SAMPLE_RATE), "-ac", "2", "-y", partial,
                ])
                os.replace(partial, trimmed[stem])
            shutil.rmtree(os.path.dirname(stems["vocals"]), ignore_errors=True)
            os.remove(chunk_audio)
        for stem in STEMS:
            stem_parts[stem].append(trimmed[stem])
        if progress_cb is not None:
            progress_cb(index + 1, chunk_count)

    track_dir = os.path.join(separated_dir, "htdemucs", "full")
    os.makedirs(track_dir, exist_ok=True)
    result = {}
    for stem in STEMS:
        list_path = os.path.join(chunk_dir, f"{stem}_list.txt")
        with open(list_path, "w", encoding="utf-8") as handle:
            for part in stem_parts[stem]:
                escaped = os.path.abspath(part).replace("\\", "/").replace("'", "'\\''")
                handle.write(f"file '{escaped}'\n")
        output = os.path.join(track_dir, f"{stem}.wav")
        # rf64 keeps WAV files above 4 GB (6+ hours of stereo) readable.
        _ffmpeg(["-f", "concat", "-safe", "0", "-i", list_path,
                 "-c", "copy", "-rf64", "auto", "-y", output])
        result[stem] = output
    shutil.rmtree(chunk_dir, ignore_errors=True)
    return result


def _load_cached(separated_dir: str, fingerprint: dict) -> Optional[dict]:
    marker = os.path.join(separated_dir, DONE_MARKER)
    try:
        with open(marker, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if data.get("source") != fingerprint:
        return None
    paths = {stem: data.get(stem) for stem in STEMS}
    if all(path and os.path.isfile(path) for path in paths.values()):
        return paths
    return None


def separate_vocals(video_path: str, output_dir: str,
                    cancel_event: Optional[threading.Event] = None,
                    progress_cb: Optional[Callable[[int, int], None]] = None) -> dict:
    """Separate vocals from video audio using Demucs.

    Returns dict with 'vocals' and 'no_vocals' paths. If Demucs fails, the
    phase-cancellation fallback is used for 'no_vocals' and 'vocals' is None.
    A finished separation is cached next to the job so a retried job does not
    repeat hours of CPU work.
    """
    separated_dir = os.path.join(output_dir, "separated")
    os.makedirs(separated_dir, exist_ok=True)
    fingerprint = _source_fingerprint(video_path)
    cached = _load_cached(separated_dir, fingerprint)
    if cached:
        logger.info("Reusing cached Demucs separation in %s", separated_dir)
        return cached

    audio_path = os.path.join(separated_dir, "source_audio.wav")
    try:
        _ffmpeg(["-i", video_path, "-vn", "-acodec", "pcm_s16le",
                 "-ar", str(SAMPLE_RATE), "-ac", "2", "-rf64", "auto", "-y", audio_path])
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract audio: {e}")
        return {"vocals": None, "no_vocals": None}

    vocals_path = None
    no_vocals_path = None
    try:
        duration = _probe_duration(audio_path)
        if duration > DEMUCS_CHUNK_SECONDS + DEMUCS_CHUNK_OVERLAP_SECONDS:
            stems = _separate_in_chunks(audio_path, separated_dir, duration,
                                        cancel_event, progress_cb)
        else:
            stems = _run_demucs(audio_path, separated_dir, duration, cancel_event)
            if progress_cb is not None:
                progress_cb(1, 1)
        vocals_path, no_vocals_path = stems["vocals"], stems["no_vocals"]
        with open(os.path.join(separated_dir, DONE_MARKER), "w", encoding="utf-8") as handle:
            json.dump({"source": fingerprint, **stems}, handle)
    except VocalSeparationCancelled:
        raise
    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError, OSError) as e:
        logger.warning(f"Demucs not available or failed ({e}), using simple vocal removal fallback")
        # Fallback: simple center channel extraction (works for stereo with center-panned vocals)
        vocals_path = None
        no_vocals_path = os.path.join(separated_dir, "no_vocals.wav")
        try:
            _ffmpeg(["-i", audio_path, "-af", "pan=stereo|c0=c0-c1|c1=c1-c0",
                     "-rf64", "auto", "-y", no_vocals_path])
        except subprocess.CalledProcessError as fallback_error:
            logger.error(f"Fallback vocal removal failed: {fallback_error}")
            no_vocals_path = None
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

    return {
        "vocals": vocals_path if vocals_path and os.path.exists(vocals_path) else None,
        "no_vocals": no_vocals_path if no_vocals_path and os.path.exists(no_vocals_path) else None,
    }
