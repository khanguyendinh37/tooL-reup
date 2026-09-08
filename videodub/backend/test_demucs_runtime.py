import sys
import unittest
from unittest.mock import patch
from app.core.vocal_remover import demucs_command


class DemucsRuntimeTests(unittest.TestCase):
    def test_source_uses_its_python_not_global_cli(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(demucs_command(['--help']),
                             [sys.executable, '-m', 'demucs.separate', '--help'])

    def test_frozen_uses_explicit_worker_not_python_m(self):
        with patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(demucs_command(['--two-stems', 'vocals', 'input.wav']),
                             [sys.executable, '--demucs-worker', '--two-stems', 'vocals', 'input.wav'])
