import unittest
from unittest.mock import patch
from app.core.downloader import select_douyin_playback_url, extract_douyin_video_id


class DouyinPlaybackTests(unittest.TestCase):
    def test_short_code_is_not_truncated(self):
        for code in ('4cNUhjZ9_9o', 'abc-def_123', 'Abc123'):
            with self.subTest(code=code), patch('app.core.downloader.resolve_short_url', return_value='123456') as resolve:
                self.assertEqual(extract_douyin_video_id(' https://v.douyin.com/' + code + '/'), '123456')
                resolve.assert_called_once_with(code)

    def test_playback_preferred_to_download(self):
        self.assertEqual(select_douyin_playback_url({
            'download_addr': {'url_list': ['https://cdn.example/download.mp4']},
            'play_addr': {'url_list': ['https://cdn.example/play.mp4?signature=original']},
        }), 'https://cdn.example/play.mp4?signature=original')

    def test_bitrate_fallback(self):
        self.assertEqual(select_douyin_playback_url({
            'play_addr': {'url_list': ['https://example.com/playwm/123']},
            'bit_rate': [{'play_addr': {'url_list': ['https://cdn.example/video.mp4']}}],
        }), 'https://cdn.example/video.mp4')

    def test_download_only_is_not_selected(self):
        with self.assertRaises(RuntimeError):
            select_douyin_playback_url({'download_addr': {'url_list': ['https://cdn.example/watermark.mp4']}})
