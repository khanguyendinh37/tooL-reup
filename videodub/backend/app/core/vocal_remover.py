import subprocess
import os
import shutil
import logging

logger = logging.getLogger(__name__)


def separate_vocals(video_path: str, output_dir: str) -> dict:
    """Separate vocals from video audio using Demucs.

    Returns dict with 'vocals' and 'no_vocals' paths.
    If Demucs fails, returns None for both and logs the error.
    """
    audio_path = video_path + ".audio.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
             "-ar", "44100", "-ac", "2", audio_path, "-y"],
            capture_output=True, check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract audio: {e}")
        return {"vocals": None, "no_vocals": None}

    separated_dir = os.path.join(output_dir, "separated")
    os.makedirs(separated_dir, exist_ok=True)

    no_vocals_path = None

    try:
        # Run Demucs for vocal separation
        result = subprocess.run(
            ["demucs", "--two-stems", "vocals", "-o", separated_dir, audio_path],
            capture_output=True, text=True, timeout=600
        )

        if result.returncode != 0:
            logger.warning(f"Demucs failed: {result.stderr}")
            raise RuntimeError(f"Demucs failed: {result.stderr}")

        htdemucs_dir = os.path.join(separated_dir, "htdemucs")
        audio_basename = os.path.splitext(os.path.basename(audio_path))[0]
        track_dir = os.path.join(htdemucs_dir, audio_basename)

        vocals_path = os.path.join(track_dir, "vocals.wav")
        no_vocals_path = os.path.join(track_dir, "no_vocals.wav")

        if not os.path.exists(no_vocals_path):
            # Try to reconstruct from other stems
            other_path = os.path.join(track_dir, "other.wav")
            drums_path = os.path.join(track_dir, "drums.wav")
            bass_path = os.path.join(track_dir, "bass.wav")

            mix_cmd = ["ffmpeg"]
            inputs = []
            if os.path.exists(other_path):
                inputs.append(other_path)
            if os.path.exists(drums_path):
                inputs.append(drums_path)
            if os.path.exists(bass_path):
                inputs.append(bass_path)

            if inputs:
                for inp in inputs:
                    mix_cmd.extend(["-i", inp])

                n_inputs = len(inputs)
                filter_str = "".join(f"[{i}:a]" for i in range(n_inputs))
                filter_str += f"amix=inputs={n_inputs}:duration=first[out]"
                mix_cmd.extend(["-filter_complex", filter_str, "-map", "[out]", "-y", no_vocals_path])
                subprocess.run(mix_cmd, capture_output=True, check=True)
            else:
                no_vocals_path = None

    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Demucs not available or failed ({e}), using simple vocal removal fallback")
        # Fallback: simple center channel extraction (works for stereo with center-panned vocals)
        no_vocals_path = os.path.join(separated_dir, "no_vocals.wav")
        try:
            subprocess.run([
                "ffmpeg", "-i", audio_path,
                "-af", "pan=stereo|c0=c0-c1|c1=c1-c0",
                "-y", no_vocals_path
            ], capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Fallback vocal removal failed: {e}")
            no_vocals_path = None

    # Clean up temporary audio file
    if os.path.exists(audio_path):
        os.remove(audio_path)

    return {
        "vocals": None,  # We don't need the vocals track
        "no_vocals": no_vocals_path if no_vocals_path and os.path.exists(no_vocals_path) else None,
    }