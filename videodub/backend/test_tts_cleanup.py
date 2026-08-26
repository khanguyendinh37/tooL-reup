import tempfile
import unittest
from pathlib import Path

from app.core.tts_engine import cleanup_tts_directory


class TtsCleanupTests(unittest.TestCase):
    def test_cleanup_removes_disposable_tts_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            tts_directory = Path(directory) / "tts"
            tts_directory.mkdir()
            (tts_directory / "seg_0000.mp3").write_bytes(b"audio")
            (tts_directory / "temporary.txt").write_text("disposable", encoding="utf-8")

            cleanup_tts_directory(str(tts_directory))

            self.assertFalse(tts_directory.exists())

    def test_cleanup_is_safe_when_directory_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            cleanup_tts_directory(str(Path(directory) / "tts"))


if __name__ == "__main__":
    unittest.main()
