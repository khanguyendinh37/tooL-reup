import copy
import unittest
from verify_build import compare_reports


class BuildParityTests(unittest.TestCase):
    def setUp(self):
        self.report = {'ok': True, 'python': '3.11.9',
                       'packages': {'yt-dlp': '2026.8.19'},
                       'checks': {'audio_extraction': 'ok', 'ffmpeg': 'same'}}

    def test_matching_reports_pass(self):
        compare_reports(self.report, copy.deepcopy(self.report))

    def test_version_or_binary_drift_fails(self):
        for field in ('python', 'packages', 'checks'):
            other = copy.deepcopy(self.report)
            other[field] = 'different'
            with self.assertRaisesRegex(RuntimeError, field):
                compare_reports(self.report, other)

    def test_failed_smoke_test_cannot_pass(self):
        with self.assertRaises(RuntimeError):
            compare_reports(self.report, {'ok': False})
