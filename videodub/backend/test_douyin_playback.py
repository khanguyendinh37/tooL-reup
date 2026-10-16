import unittest
from app.core.downloader import select_douyin_playback_url


class DouyinPlaybackTests(unittest.TestCase):
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
