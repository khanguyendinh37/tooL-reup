"""Cookie parsing regressions; fixtures contain no real credentials."""
import tempfile
import unittest
from pathlib import Path

from app.core.downloader import parse_netscape_cookies, validate_cookies_content


class CookieParserTests(unittest.TestCase):
    def test_httponly_bom_and_domain_boundary(self):
        content = (
            '\ufeff# Netscape HTTP Cookie File\n'
            '#HttpOnly_.douyin.com\tTRUE\t/\tTRUE\t0\tsessionid\ttest-only\n'
            '.evil-douyin.com\tTRUE\t/\tFALSE\t0\tttwid\twrong-domain\n'
            '.douyin.com.evil.test\tTRUE\t/\tFALSE\t0\tttwid\twrong-domain\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cookies.txt'
            path.write_text(content, encoding='utf-8')
            self.assertEqual(parse_netscape_cookies(str(path)), {'sessionid': 'test-only'})
        self.assertTrue(validate_cookies_content(content, 'douyin')[0])

    def test_other_platform_httponly(self):
        content = '#HttpOnly_.facebook.com\tTRUE\t/\tTRUE\t0\tc_user\ttest-only\n'
        self.assertTrue(validate_cookies_content(content, 'facebook')[0])
        self.assertFalse(validate_cookies_content(content, 'douyin')[0])


if __name__ == '__main__':
    unittest.main()
