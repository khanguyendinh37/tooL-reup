import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from startup_check import check_window


class StartupCheckTests(unittest.TestCase):
    def check(self, loaded, page):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.json'
            window = Mock()
            window.events = SimpleNamespace(loaded=Mock())
            window.events.loaded.wait.return_value = loaded
            window.evaluate_js.return_value = page
            check_window(window, report, timeout=0.01)
            window.destroy.assert_called_once()
            return json.loads(report.read_text())

    def test_rendered_frontend_passes(self):
        self.assertTrue(self.check(True, {'ready': True, 'title': 'VideoDub'})['ok'])

    def test_no_native_page_fails(self):
        self.assertFalse(self.check(False, None)['ok'])

    def test_blank_page_fails(self):
        self.assertFalse(self.check(True, {'ready': False})['ok'])


if __name__ == '__main__':
    unittest.main()
