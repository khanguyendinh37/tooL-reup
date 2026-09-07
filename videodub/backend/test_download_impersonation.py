import sys
import types
import unittest
from unittest.mock import patch

from app.core.downloader import _build_impersonate_target


class Target:
    def __init__(self, client, label):
        self.client, self.label = client, label

    def __str__(self):
        return self.label


class ImpersonationTests(unittest.TestCase):
    def test_returns_supported_target_object(self):
        target = Target('chrome', 'chrome-120:windows-10')
        module = types.SimpleNamespace(CurlCFFIRH=types.SimpleNamespace(supported_targets=[target]))
        with patch.dict(sys.modules, {'yt_dlp.networking._curlcffi': module}):
            self.assertIs(_build_impersonate_target('facebook'), target)

    def test_new_browser_versions_are_supported(self):
        target = Target('chrome', 'chrome-999:windows-11')
        module = types.SimpleNamespace(CurlCFFIRH=types.SimpleNamespace(supported_targets=[target]))
        with patch.dict(sys.modules, {'yt_dlp.networking._curlcffi': module}):
            self.assertIs(_build_impersonate_target('facebook'), target)

    def test_missing_handler_leaves_other_downloads_available(self):
        with patch.dict(sys.modules, {'yt_dlp.networking._curlcffi': None}):
            self.assertIsNone(_build_impersonate_target('facebook'))
            self.assertIsNone(_build_impersonate_target('youtube'))
