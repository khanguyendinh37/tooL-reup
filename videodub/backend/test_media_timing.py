import tempfile
import shutil
import subprocess
import unittest
from pathlib import Path

from app.core.translator import build_subtitle_srt_from_actual_timing, parse_srt
from app.core.video_response import video_response
from app.core.tts_engine import merge_tts_segments, _probe_duration_seconds
from starlette.requests import Request


class SubtitleTimingTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_merged_timing_tracks_real_audio_when_speed_cap_is_exceeded(self):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / 'tone.wav'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'sine=frequency=440:duration=2', '-y', str(audio)], check=True)
            output = Path(directory) / 'merged.wav'
            _, timings = merge_tts_segments([
                {'index': 0, 'start': 0, 'audio_path': str(audio)},
                {'index': 1, 'start': 0.1, 'audio_path': str(audio)},
            ], 5, str(output))
            self.assertGreater(timings[1][1], 0.4)
            self.assertAlmostEqual(timings[0][2], timings[1][1], places=3)
            self.assertAlmostEqual(timings[-1][2], _probe_duration_seconds(str(output)), places=3)

    def test_audio_positions_match_cues_regardless_of_srt_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'translated.srt'
            output = Path(directory) / 'subtitle.srt'
            source.write_text('7\n00:00:01,000 --> 00:00:02,000\nFirst\n\n42\n00:00:03,000 --> 00:00:04,000\nSecond\n', encoding='utf-8')
            build_subtitle_srt_from_actual_timing(str(source), [(0, 1.2, 2.8), (1, 3.1, 4.6)], str(output))
            entries = parse_srt(str(output))
            self.assertEqual([e['start'] for e in entries], ['00:00:01,200', '00:00:03,100'])
            self.assertEqual([e['end'] for e in entries], ['00:00:02,800', '00:00:04,600'])
            self.assertEqual([e['original_text'] for e in entries], ['First', 'Second'])


class VideoRangeTests(unittest.IsolatedAsyncioTestCase):
    async def test_ranges_return_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'video.mp4'
            path.write_bytes(b'0123456789')
            for value, expected in [('bytes=3-5', b'345'), ('bytes=7-', b'789'), ('bytes=-2', b'89'), ('bytes=8-99', b'89')]:
                request = Request({'type': 'http', 'headers': [(b'range', value.encode())]})
                response = video_response(str(path), request)
                self.assertEqual(response.status_code, 206)
                body = b''.join([chunk async for chunk in response.body_iterator])
                self.assertEqual(body, expected)
                self.assertEqual(int(response.headers['content-length']), len(expected))
            for value in ['bytes=10-', 'bytes=7-3', 'bytes=-0', 'bytes=-']:
                request = Request({'type': 'http', 'headers': [(b'range', value.encode())]})
                self.assertEqual(video_response(str(path), request).status_code, 416)
            response = video_response(str(path), Request({'type': 'http', 'headers': []}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['accept-ranges'], 'bytes')
