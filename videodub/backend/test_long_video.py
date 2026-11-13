"""Regression tests for multi-hour dubbing: merge speed, chunking, resume, cancel."""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.core import tts_engine as tts
from app.core import vocal_remover
from app.core.tts_engine import _probe_duration_seconds, merge_tts_segments, prepare_tts_directory
from app.core.translation_config import TranslationConfig
from app.core.translator import translate_srt_deep_translator

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _tone(path: Path, seconds: float, extra: list[str] | None = None) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         *(extra or []), "-y", str(path)],
        check=True,
    )


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg required")
class MergeTimelineTests(unittest.TestCase):
    def test_many_cues_land_on_their_start_times(self):
        with tempfile.TemporaryDirectory() as directory:
            tone = Path(directory) / "tone.mp3"
            _tone(tone, 0.5)
            cues = [{"index": i, "start": i * 2.0, "audio_path": str(tone)} for i in range(60)]
            output = Path(directory) / "merged.wav"
            _, timings = merge_tts_segments(cues, 125.0, str(output))
            self.assertEqual(len(timings), 60)
            for i, (index, start, end) in enumerate(timings):
                self.assertEqual(index, i)
                self.assertAlmostEqual(start, i * 2.0, places=3)
                self.assertGreater(end, start)
            self.assertAlmostEqual(_probe_duration_seconds(str(output)), timings[-1][2], places=2)

    def test_output_is_clipped_to_video_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            tone = Path(directory) / "tone.mp3"
            _tone(tone, 2.0)
            output = Path(directory) / "merged.wav"
            _, timings = merge_tts_segments([
                {"index": 0, "start": 0.0, "audio_path": str(tone)},
                {"index": 1, "start": 2.5, "audio_path": str(tone)},
                {"index": 2, "start": 9.0, "audio_path": str(tone)},
            ], 3.0, str(output))
            self.assertEqual([t[0] for t in timings], [0, 1])
            self.assertAlmostEqual(timings[-1][2], 3.0, places=3)
            self.assertLessEqual(_probe_duration_seconds(str(output)), 3.01)


FAKE_DEMUCS = r'''
import os, shutil, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
source = args[-1]
name = os.path.splitext(os.path.basename(source))[0]
target = os.path.join(out, "htdemucs", name)
os.makedirs(target, exist_ok=True)
shutil.copy(source, os.path.join(target, "vocals.wav"))
shutil.copy(source, os.path.join(target, "no_vocals.wav"))
with open(os.path.join(out, "calls.log"), "a") as log:
    log.write(name + "\n")
'''


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg required")
class ChunkedSeparationTests(unittest.TestCase):
    def test_long_audio_is_split_joined_and_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake_demucs.py"
            script.write_text(FAKE_DEMUCS, encoding="utf-8")
            video = Path(directory) / "video.m4a"
            _tone(video, 25.0, ["-ac", "2"])
            job_dir = Path(directory) / "job"
            job_dir.mkdir()
            progress = []
            with patch.object(vocal_remover, "DEMUCS_CHUNK_SECONDS", 10.0), \
                 patch.object(vocal_remover, "demucs_command",
                              side_effect=lambda args: [sys.executable, str(script), *args]):
                result = vocal_remover.separate_vocals(
                    str(video), str(job_dir), progress_cb=lambda d, t: progress.append((d, t)),
                )
                self.assertEqual(progress[-1], (3, 3))
                for stem in ("vocals", "no_vocals"):
                    self.assertAlmostEqual(_probe_duration_seconds(result[stem]), 25.0, delta=0.05)
                calls = (job_dir / "separated" / "calls.log").read_text().split()
                self.assertEqual(len(calls), 3)

                again = vocal_remover.separate_vocals(str(video), str(job_dir))
                self.assertEqual(again, result)
                calls = (job_dir / "separated" / "calls.log").read_text().split()
                self.assertEqual(len(calls), 3, "cached separation must not rerun Demucs")


def _long_srt(count: int) -> str:
    blocks = []
    for i in range(count):
        start, end = i * 3, i * 3 + 2
        blocks.append(
            f"{i + 1}\n00:{start // 60:02d}:{start % 60:02d},000 --> "
            f"00:{end // 60:02d}:{end % 60:02d},000\nLine number {i}\n"
        )
    return "\n".join(blocks)


class ChunkedTranslationTests(unittest.TestCase):
    def test_long_file_is_sent_in_chunks_and_failed_chunk_falls_back(self):
        config = TranslationConfig(
            provider="gemini", model="gemini-2.0-flash",
            endpoint="https://example.test/v1beta", api_key="test-key", verified=True,
        )
        calls = []

        def fake_ai(_config, block, source, target, timeout_seconds=20):
            markers = [line.split(">>>")[0] + ">>>" for line in block.splitlines()]
            calls.append(len(markers))
            if "<<<0>>>" in block and len(markers) > 10:
                return ""  # first chunk fails
            return "\n".join(f"{m} Dòng {m.strip('<>')}" for m in markers)

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.srt"
            output = Path(directory) / "translated.srt"
            source.write_text(_long_srt(400), encoding="utf-8")
            with patch("app.core.translator.translate_marked_block", side_effect=fake_ai), \
                 patch("app.core.translator._translate_with_retry") as google:
                translate_srt_deep_translator(str(source), "vi", str(output), "en", config)
            self.assertTrue(all(count <= 150 for count in calls[:3]))
            self.assertGreaterEqual(len(calls), 3)
            google.assert_not_called()
            text = output.read_text(encoding="utf-8")
            self.assertIn("Dòng 0", text)
            self.assertIn("Dòng 399", text)


class TtsResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_cue_files_are_reused(self):
        segments = [{"start": i, "end": i + 1, "text": f"cue {i}"} for i in range(3)]
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "seg_0001.mp3").write_bytes(b"done")
            with patch.object(tts, "text_to_speech_edge", new_callable=AsyncMock) as edge:
                result = await tts.generate_dubbing_audio(segments, "vi-VN-NamMinhNeural", directory)
            self.assertEqual([r["index"] for r in result], [0, 1, 2])
            self.assertEqual([call.args[0] for call in edge.await_args_list], ["cue 0", "cue 2"])

    async def test_partial_files_are_written_then_moved(self):
        async def synth(text, voice, path, rate):
            Path(path).write_bytes(b"audio")

        segments = [{"start": 0, "end": 1, "text": "hello"}]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(tts, "text_to_speech_edge", side_effect=synth):
                await tts.generate_dubbing_audio(segments, "vi-VN-NamMinhNeural", directory)
            self.assertEqual(sorted(os.listdir(directory)), ["seg_0000.mp3"])

    def test_cache_is_wiped_when_voice_or_text_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            tts_dir = Path(directory) / "tts"
            prepare_tts_directory(str(tts_dir), {"voice": "a"})
            (tts_dir / "seg_0000.mp3").write_bytes(b"x")
            prepare_tts_directory(str(tts_dir), {"voice": "a"})
            self.assertTrue((tts_dir / "seg_0000.mp3").exists())
            prepare_tts_directory(str(tts_dir), {"voice": "b"})
            self.assertFalse((tts_dir / "seg_0000.mp3").exists())
            self.assertEqual(json.loads((tts_dir / "manifest.json").read_text()), {"voice": "b"})


class CancellationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.models.database import Base, DubbingJob

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        async with self.Session() as session:
            session.add(DubbingJob(id="job1", url="u", source_lang="en", target_lang="vi",
                                   voice="v", whisper_model="small", status="tts"))
            await session.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_cancel_is_seen_and_not_overwritten(self):
        from sqlalchemy import select, update
        from app.core.pipeline import _check_cancelled, update_job
        from app.models.database import DubbingJob

        async with self.Session() as pipeline_session, self.Session() as api_session:
            # The pipeline session has the job loaded in its identity map.
            (await pipeline_session.execute(select(DubbingJob))).scalar_one()
            await api_session.execute(
                update(DubbingJob).where(DubbingJob.id == "job1").values(status="cancelled")
            )
            await api_session.commit()

            await update_job(pipeline_session, "job1", "tts", 40)
            status = (await api_session.execute(select(DubbingJob.status))).scalar_one()
            self.assertEqual(status, "cancelled")
            with self.assertRaises(asyncio.CancelledError):
                await _check_cancelled(pipeline_session, "job1")


if __name__ == "__main__":
    unittest.main()
