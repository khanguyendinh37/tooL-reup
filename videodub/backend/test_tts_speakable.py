import asyncio
import tempfile
import unittest
from unittest import mock

from app.core import tts_engine
from app.core.tts_engine import generate_dubbing_audio, speakable_text


class SpeakableTextTests(unittest.TestCase):
    def test_unspeakable_cues_are_empty(self):
        for text in ("...", "♪♪", "😂😂", "—", "哈哈哈", "  "):
            self.assertEqual(speakable_text(text, "vi-VN-HoaiMyNeural"), "", text)

    def test_readable_text_is_kept(self):
        self.assertEqual(speakable_text("Xin chào 你好!", "vi-VN-HoaiMyNeural"), "Xin chào !")
        self.assertEqual(speakable_text("Giá 100% (rẻ) 😂", "vi-VN-NamMinhNeural"), "Giá 100% (rẻ)")
        # Voices for non-Latin languages keep their own script.
        self.assertEqual(speakable_text("你好", "zh-CN-XiaoxiaoNeural"), "你好")


class SilentCueTests(unittest.TestCase):
    def test_unspeakable_cue_becomes_silence_instead_of_failing_job(self):
        calls = []

        async def fake_tts(text, voice, path, rate, lang):
            calls.append(text)
            with open(path, "wb") as handle:
                handle.write(b"audio")
            return path

        segments = [
            {"start": 0.0, "end": 1.0, "text": "Xin chào"},
            {"start": 1.0, "end": 2.0, "text": "哈哈哈"},
        ]
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(tts_engine, "text_to_speech_with_fallback", fake_tts):
            results = asyncio.run(generate_dubbing_audio(segments, "vi-VN-HoaiMyNeural", directory))
        self.assertEqual(calls, ["Xin chào"])
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]["audio_path"])
        self.assertIsNone(results[1]["audio_path"])
        self.assertTrue(results[1]["silent"])


if __name__ == "__main__":
    unittest.main()
