import tempfile
import types
import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from app.core import tts_engine as tts


class VoiceConsistencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_access_failure_stops_without_recovery(self):
        failure = RuntimeError('forbidden')
        failure.status = 403
        save = AsyncMock(side_effect=failure)
        communicate = Mock(return_value=types.SimpleNamespace(save=save))
        with patch.dict('sys.modules', {'edge_tts': types.SimpleNamespace(Communicate=communicate)}), \
             patch.object(tts.asyncio, 'sleep', new_callable=AsyncMock) as sleep:
            with self.assertRaises(tts.TTSAccessError):
                await tts.text_to_speech_edge('Xin chào', 'vi-VN-NamMinhNeural', 'unused.mp3')
            self.assertEqual(save.await_count, 1)
            sleep.assert_not_awaited()

    async def test_parallelism_progress_and_order(self):
        active = peak = 0
        async def synth(*args):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
        segments = [{'start': i, 'end': i + 1, 'text': str(i)} for i in range(12)]
        progress = AsyncMock()
        with tempfile.TemporaryDirectory() as directory, patch.object(tts, 'text_to_speech_edge', side_effect=synth):
            result = await tts.generate_dubbing_audio(segments, 'vi-VN-NamMinhNeural', directory, progress_cb=progress)
        self.assertEqual(peak, tts.TTS_CONCURRENCY)
        self.assertEqual([r['index'] for r in result], list(range(12)))
        self.assertEqual([c.args for c in progress.await_args_list], [(i, 12) for i in range(1, 13)])

    async def test_access_failure_cancels_pending_batch(self):
        calls = 0
        async def synth(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise tts.TTSAccessError('forbidden')
            await asyncio.sleep(10)
        segments = [{'start': i, 'end': i+1, 'text': str(i)} for i in range(100)]
        with tempfile.TemporaryDirectory() as directory, patch.object(tts, 'text_to_speech_edge', side_effect=synth):
            with self.assertRaises(tts.TTSAccessError):
                await asyncio.wait_for(tts.generate_dubbing_audio(segments, 'vi-VN-NamMinhNeural', directory), 1)
        self.assertLessEqual(calls, tts.TTS_CONCURRENCY + 1)

    async def test_transient_failure_retries_exact_voice(self):
        save = AsyncMock(side_effect=[RuntimeError('temporary failure'), None])
        communicate = Mock(return_value=types.SimpleNamespace(save=save))
        with patch.dict('sys.modules', {'edge_tts': types.SimpleNamespace(Communicate=communicate)}), \
             patch.object(tts.asyncio, 'sleep', new_callable=AsyncMock):
            result = await tts.text_to_speech_with_fallback('Xin chào', 'vi-VN-NamMinhNeural', 'unused.mp3', '+20%')
        self.assertEqual(result, 'unused.mp3')
        self.assertEqual(communicate.call_count, 2)
        self.assertTrue(all(call.args[1] == 'vi-VN-NamMinhNeural' and call.kwargs['rate'] == '+20%' for call in communicate.call_args_list))

    async def test_provider_failure_never_substitutes_voice(self):
        with patch.object(tts, 'text_to_speech_edge', new_callable=AsyncMock) as edge, \
             patch.object(tts, 'text_to_speech_gtts', new_callable=AsyncMock) as google:
            edge.side_effect = RuntimeError('temporary service failure')
            with self.assertRaises(RuntimeError):
                await tts.text_to_speech_with_fallback('Xin chào', 'vi-VN-NamMinhNeural', 'unused.mp3')
            edge.assert_awaited_once_with('Xin chào', 'vi-VN-NamMinhNeural', 'unused.mp3', '+0%')
            google.assert_not_awaited()

    async def test_failed_cue_rejects_batch(self):
        segments = [{'start': i, 'end': i + 1, 'text': str(i)} for i in range(3)]
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(tts, 'text_to_speech_edge', new_callable=AsyncMock) as edge, \
             patch.object(tts.asyncio, 'sleep', new_callable=AsyncMock):
            edge.side_effect = ['ok', RuntimeError('unavailable'), 'ok', RuntimeError('unavailable'), RuntimeError('unavailable')]
            with self.assertRaisesRegex(RuntimeError, '1/3'):
                await tts.generate_dubbing_audio(segments, 'vi-VN-NamMinhNeural', directory)
            self.assertEqual(edge.await_count, 5)
            self.assertTrue(all(call.args[1] == 'vi-VN-NamMinhNeural' for call in edge.await_args_list))

    async def test_recovery_retries_only_failed_cue_and_preserves_indices(self):
        segments = [
            {'start': 0, 'end': 1, 'text': 'First'},
            {'start': 1, 'end': 2, 'text': ''},
            {'start': 2, 'end': 3, 'text': 'Second'},
        ]
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(tts, 'text_to_speech_edge', new_callable=AsyncMock) as edge, \
             patch.object(tts.asyncio, 'sleep', new_callable=AsyncMock) as sleep:
            edge.side_effect = ['ok', RuntimeError('No audio was received'), 'ok']
            results = await tts.generate_dubbing_audio(segments, 'vi-VN-NamMinhNeural', directory, '+20%')
            self.assertEqual([result['index'] for result in results], [0, 2])
            self.assertEqual([call.args[0] for call in edge.await_args_list], ['First', 'Second', 'Second'])
            self.assertTrue(all(call.args[1] == 'vi-VN-NamMinhNeural' and call.args[3] == '+20%' for call in edge.await_args_list))
            sleep.assert_awaited_once_with(tts.TTS_RECOVERY_DELAY_SECONDS)

    async def test_success_preserves_voice_order_and_rate(self):
        segments = [{'start': i, 'end': i + 1, 'text': str(i)} for i in range(3)]
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(tts, 'text_to_speech_edge', new_callable=AsyncMock) as edge:
            result = await tts.generate_dubbing_audio(segments, 'vi-VN-NamMinhNeural', directory, '+20%')
            self.assertEqual([item['index'] for item in result], [0, 1, 2])
            self.assertTrue(all(call.args[1] == 'vi-VN-NamMinhNeural' and call.args[3] == '+20%' for call in edge.await_args_list))


if __name__ == '__main__':
    unittest.main()
