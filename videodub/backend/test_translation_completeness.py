import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.core.translator import translate_srt_deep_translator


class TranslationCompletenessTests(unittest.TestCase):
    def test_provider_failure_is_not_sent_to_tts_as_source_language(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.srt'
            output = Path(directory) / 'translated.srt'
            source.write_text('1\n00:00:00,000 --> 00:00:01,000\nHello\n', encoding='utf-8')
            with patch('app.core.translator._translate_marked_group', return_value={}), \
                 patch('app.core.translator._google_circuit_is_open', return_value=True):
                with self.assertRaisesRegex(RuntimeError, '1/1'):
                    translate_srt_deep_translator(str(source), 'vi', str(output), 'en')
            self.assertFalse(output.exists())
