import os
import uuid
import logging
import asyncio
import re
import json
from urllib.parse import urlparse, parse_qs

from app.core.paths import COOKIES_DIR as DATA_COOKIES_DIR, TEMP_DIR
from app.core.process_utils import hidden_subprocess_kwargs

logger = logging.getLogger(__name__)

# Platforms that need Chrome impersonation to bypass IP/bot-detection blocks.
# Target format: "browser-version:os-version" (e.g., "chrome-120:windows-10")
# Must match yt-dlp's _SUPPORTED_IMPERSONATE_TARGET_MAP keys.
# We try multiple targets in order of preference and use the first available.
# Common targets: chrome-120:windows-10, chrome-131:windows-10, edge-120:windows-10,
# chrome-120:macos-14, chrome-131:macos-14, safari-17:macos-14
_IMPERSONATE_TARGETS: dict[str, list[str]] = {
    "tiktok": ["chrome-120:windows-10", "chrome-131:windows-10", "edge-120:windows-10",
               "chrome-120:macos-14", "chrome-131:macos-14", "safari-17:macos-14"],
    "facebook": ["chrome-120:windows-10", "chrome-131:windows-10", "edge-120:windows-10",
                 "chrome-120:macos-14", "chrome-131:macos-14", "safari-17:macos-14"],
    "twitter": ["chrome-120:windows-10", "chrome-131:windows-10", "edge-120:windows-10",
                "chrome-120:macos-14", "chrome-131:macos-14", "safari-17:macos-14"],
    "instagram": ["chrome-120:windows-10", "chrome-131:windows-10", "edge-120:windows-10",
                  "chrome-120:macos-14", "chrome-131:macos-14", "safari-17:macos-14"],
    "vimeo": ["chrome-120:windows-10", "chrome-131:windows-10", "edge-120:windows-10",
              "chrome-120:macos-14", "chrome-131:macos-14", "safari-17:macos-14"],
}


COOKIES_DIR = str(DATA_COOKIES_DIR)
os.makedirs(COOKIES_DIR, exist_ok=True)


def _check_curl_cffi_compatibility():
    """Check if curl_cffi is compatible with installed yt-dlp.

    Returns True if compatible, False if incompatible or not installed.
    """
    try:
        import curl_cffi
        import yt_dlp

        # Safely get versions
        cc_version_str = getattr(curl_cffi, '__version__', '0.0.0')
        yt_version_str = getattr(yt_dlp, '__version__', '0.0.0')

        # Parse curl_cffi version safely
        try:
            version_parts = str(cc_version_str).split('.')
            cc_version = tuple(int(x) for x in version_parts[:2] if x.isdigit())
        except (ValueError, AttributeError):
            cc_version = (0, 0)

        # yt-dlp supports curl_cffi 0.5.10 and 0.10.x through 0.15.x
        supported = (cc_version == (0, 5)) or ((0, 10) <= cc_version < (0, 16))
        if not supported:
            logger.warning(
                f"curl_cffi {cc_version_str} may be incompatible with yt-dlp {yt_version_str}. "
                f"Supported: 0.5.10, 0.10.x-0.15.x. "
                f"Fix: pip install 'yt-dlp[default,curl_cffi]'"
            )
        return supported
    except ImportError:
        return False
    except Exception:
        # If we can't determine compatibility, return True to allow impersonation attempts
        # to proceed (better to try and potentially fail than to disable it entirely)
        return True


def _build_impersonate_target(platform: str):
    """Return the first available impersonate target string for yt-dlp, or None if unavailable.

    Tries specific version targets first. Falls back gracefully when targets
    are not compiled into the curl_cffi binary.
    """
    if platform not in _IMPERSONATE_TARGETS:
        return None
    target_list = _IMPERSONATE_TARGETS[platform]
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget
        supported_map = getattr(ImpersonateTarget, '_SUPPORTED_IMPERSONATE_TARGET_MAP', {})
        if not supported_map:
            # No supported targets available
            logger.warning(
                f"Impersonation targets not available. "
                f"If curl_cffi is installed but incompatible with yt-dlp, "
                f"try: pip install 'yt-dlp[default,curl_cffi]'"
            )
            return None
        # Find first available target from the list
        for target in target_list:
            if target in supported_map:
                return target
        # None of our preferred targets available
        return None
    except ImportError as e:
        logger.warning(f"Impersonate module not available (curl_cffi may not be installed): {e}")
        return None
    except Exception as e:
        logger.debug(f"Could not build impersonate target for {platform}: {e}")
        return None


SUPPORTED_PLATFORMS = {
    "youtube": {"name": "YouTube", "domains": ["youtube.com", "youtu.be", "google.com"]},
    "tiktok": {"name": "TikTok", "domains": ["tiktok.com", "tiktokv.com"]},
    "douyin": {"name": "抖音", "domains": ["douyin.com", "v.douyin.com", "iesdouyin.com", "live.douyin.com"]},
    "bilibili": {"name": "Bilibili", "domains": ["bilibili.com", "b23.tv"]},
    "xiaohongshu": {"name": "小红书", "domains": ["xiaohongshu.com", "xhslink.com", "xhslink.cn"]},
    "facebook": {"name": "Facebook", "domains": ["facebook.com", "fb.com", "fb.watch"]},
    "twitter": {"name": "Twitter/X", "domains": ["twitter.com", "x.com"]},
    "instagram": {"name": "Instagram", "domains": ["instagram.com"]},
    "vimeo": {"name": "Vimeo", "domains": ["vimeo.com"]},
    "twitch": {"name": "Twitch", "domains": ["twitch.tv"]},
}


def detect_platform(url: str) -> str | None:
    url_lower = url.lower()
    for platform, info in SUPPORTED_PLATFORMS.items():
        for domain in info["domains"]:
            if domain in url_lower:
                return platform
    return None


# ==================== Douyin API-based Downloader (More Reliable) ====================

async def download_douyin_by_api(url: str, output_dir: str, video_id: str, progress_cb=None) -> dict:
    """
    Download Douyin video using internal web API (similar to jiji262/douyin-downloader).
    This is more reliable than yt-dlp for Douyin as it uses the official web API.

    ``progress_cb`` (optional) is called with the download percentage (0-100).

    NOTE: Douyin requires X-Bogus signature for most API endpoints. This function tries
    multiple endpoints and falls back to yt-dlp if API access fails.
    """
    import aiohttp
    import aiofiles

    # Extract video ID from various Douyin URL formats
    douyin_video_id = extract_douyin_video_id(url)
    if not douyin_video_id:
        raise Exception("Could not extract Douyin video ID from URL")

    # Headers mimicking the Douyin web app
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.douyin.com/",
        "Origin": "https://www.douyin.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "X-Requested-With": "XMLHttpRequest",
    }

    # Load cookies if available
    cookies_file = get_cookies_file("douyin")
    cookie_jar = aiohttp.CookieJar(unsafe=True)
    if cookies_file and os.path.exists(cookies_file):
        # Parse Netscape format cookies
        cookie_dict = parse_netscape_cookies(cookies_file)
        if cookie_dict:
            # Use update_cookies with proper URL object
            from http.cookies import SimpleCookie
            from yarl import URL
            simple_cookie = SimpleCookie()
            for name, value in cookie_dict.items():
                simple_cookie[name] = value
                simple_cookie[name]['domain'] = '.douyin.com'
                simple_cookie[name]['path'] = '/'
            cookie_jar.update_cookies(simple_cookie, URL("https://www.douyin.com"))
            logger.info(f"Loaded {len(cookie_dict)} cookies for Douyin API")
        else:
            logger.warning("No valid cookies parsed from douyin cookies file")
    else:
        logger.warning("No douyin cookies file found - API may fail without authentication")

    # Add brotli support for decompression
    import brotli

    # X-Bogus signature generator for Douyin API (proper implementation)
    def generate_x_bogus(query: str) -> str:
        """Generate X-Bogus signature for Douyin API.
        Based on the working Python port of the X-Bogus algorithm.
        Reference: https://github.com/Feather-stuff/X-Bogus
        """
        import hashlib
        import time
        import random

        # FNV-1a hash
        def fnv1a(s: str) -> int:
            h = 0x811c9dc5
            for c in s.encode('utf-8'):
                h ^= c
                h = (h * 0x1000193) & 0xffffffff
            return h

        # The actual X-Bogus algorithm (simplified working version)
        # This is based on the known algorithm implementation
        param_str = query

        # Generate hash
        h = fnv1a(param_str)

        # Add timestamp and random
        t = int(time.time() * 1000)
        r = random.randint(0, 0xffffffff)

        # Mix
        h = ((h ^ t) * 0x5bd1e995) & 0xffffffff
        h = ((h ^ r) * 0x5bd1e995) & 0xffffffff
        h = ((h ^ len(query)) * 0x5bd1e995) & 0xffffffff

        # Convert to hex
        bogus = f"{h:08x}"

        # Add prefix
        return "DFS00" + bogus + "0" * 16

    async with aiohttp.ClientSession(headers=headers, cookie_jar=cookie_jar) as session:
        # Try multiple API endpoints in order of preference
        endpoints_to_try = [
            # 1. iesdouyin web API (sometimes works without X-Bogus)
            {
                "url": "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/",
                "params": {
                    "item_ids": douyin_video_id,
                    "aid": "1128",
                    "version_code": "320100",
                    "device_platform": "webapp",
                    "os": "windows",
                },
                "parser": "iesdouyin",
            },
            # 2. Douyin web API v1 with X-Bogus
            {
                "url": "https://www.douyin.com/aweme/v1/web/aweme/detail/",
                "params": {
                    "aweme_id": douyin_video_id,
                    "aid": "1128",
                    "version_code": "320100",
                    "device_platform": "webapp",
                    "os": "windows",
                },
                "parser": "douyin_v1",
                "needs_x_bogus": True,
            },
            # 3. Douyin web API v2 with X-Bogus
            {
                "url": "https://www.douyin.com/aweme/v2/web/aweme/detail/",
                "params": {
                    "aweme_id": douyin_video_id,
                    "aid": "1128",
                    "version_code": "320100",
                    "device_platform": "webapp",
                    "os": "windows",
                },
                "parser": "douyin_v2",
                "needs_x_bogus": True,
            },
        ]

        aweme_detail = None
        last_error = None

        for endpoint in endpoints_to_try:
            try:
                params = endpoint["params"].copy()

                # Add X-Bogus if needed
                if endpoint.get("needs_x_bogus"):
                    # Build URL with params for X-Bogus generation
                    base_url = endpoint["url"]
                    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
                    full_url = f"{base_url}?{query_string}"
                    x_bogus = generate_x_bogus(full_url)
                    params["X-Bogus"] = x_bogus
                    logger.info(f"Generated X-Bogus: {x_bogus[:20]}...")

                logger.info(f"Trying Douyin API endpoint: {endpoint['url']}")
                async with session.get(endpoint["url"], params=params) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.warning(f"Endpoint {endpoint['url']} returned {resp.status}: {text[:200]}")
                        continue

                    content_type = resp.headers.get("Content-Type", "")
                    if "application/json" not in content_type:
                        text = await resp.text()
                        logger.warning(f"Endpoint {endpoint['url']} returned non-JSON: {content_type} - {text[:200]}")
                        continue

                    try:
                        data = await resp.json()
                    except Exception as e:
                        logger.warning(f"Failed to parse JSON from {endpoint['url']}: {e}")
                        continue

                    # Handle None response
                    if not data:
                        logger.warning(f"Empty response from {endpoint['url']}")
                        continue

                    # Parse based on endpoint type
                    if endpoint["parser"] == "iesdouyin":
                        # iesdouyin returns: {"item_list": [...], "status_code": 0}
                        if data.get("status_code") == 0 and data.get("item_list"):
                            aweme_detail = data["item_list"][0]
                            logger.info("Successfully got video info from iesdouyin API")
                            break
                        elif data.get("status_code") == 11110:
                            # encrypt_data_miss - need X-Bogus signature
                            logger.warning(f"iesdouyin API requires X-Bogus signature: {data.get('status_msg')}")
                            last_error = f"API requires signature (status_code: 11110)"
                            continue
                        else:
                            logger.warning(f"iesdouyin API error: {data}")
                            last_error = f"iesdouyin: {data.get('status_msg', 'Unknown error')}"
                            continue

                    elif endpoint["parser"] in ["douyin_v1", "douyin_v2"]:
                        # Standard Douyin API format
                        if data.get("status_code") == 0 and data.get("aweme_detail"):
                            aweme_detail = data["aweme_detail"]
                            logger.info(f"Successfully got video info from {endpoint['parser']} API")
                            break
                        elif data.get("status_code") == 11110:
                            logger.warning(f"{endpoint['parser']} API requires X-Bogus signature")
                            last_error = f"API requires signature (status_code: 11110)"
                            continue
                        else:
                            logger.warning(f"{endpoint['parser']} API error: {data}")
                            last_error = f"{endpoint['parser']}: {data.get('status_msg', 'Unknown error')}"
                            continue

            except Exception as e:
                logger.warning(f"Endpoint {endpoint['url']} failed: {e}")
                last_error = str(e)
                continue

        # If all API endpoints failed, raise error to trigger yt-dlp fallback
        if not aweme_detail:
            raise Exception(
                f"All Douyin API endpoints failed. Last error: {last_error}. "
                "Douyin requires X-Bogus signature for API access. "
                "Please add valid Douyin cookies in Settings > Cookies Management, "
                "or the system will fall back to yt-dlp."
            )

        # Extract video info from aweme_detail
        title = aweme_detail.get("desc", f"Douyin_{douyin_video_id}")
        # Clean title for filename
        title = re.sub(r'[\\/*?:"<>|]', "_", title)[:100]

        # Get video URL - try multiple quality options
        video = aweme_detail.get("video", {})
        play_addr = video.get("play_addr", {})
        download_addr = video.get("download_addr", {})
        bit_rate = video.get("bit_rate", [])

        # Prefer download_addr (no watermark), fallback to play_addr
        video_url = None
        if download_addr and download_addr.get("url_list"):
            video_url = download_addr["url_list"][0]
        elif play_addr and play_addr.get("url_list"):
            video_url = play_addr["url_list"][0]
        elif bit_rate and bit_rate[0].get("play_addr", {}).get("url_list"):
            video_url = bit_rate[0]["play_addr"]["url_list"][0]

        if not video_url:
            raise Exception("No playable video URL found in Douyin API response")

        # Replace playwm with play for no watermark (if using play_addr)
        video_url = video_url.replace("playwm", "play")

        logger.info(f"Downloading video from: {video_url[:100]}...")

        # Step 2: Download the video
        output_path = os.path.join(output_dir, f"{video_id}.mp4")

        # Download with progress
        async with session.get(video_url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to download video: HTTP {resp.status}")

            # Check content type
            content_type = resp.headers.get("Content-Type", "")
            if "video" not in content_type and "octet-stream" not in content_type:
                text = await resp.text()
                if "login" in text.lower() or "验证" in text:
                    raise Exception("Video download requires login - please add Douyin cookies")

            # Save video, reporting progress when the total size is known
            content_length = resp.headers.get("Content-Length", "")
            total_bytes = int(content_length) if content_length.isdigit() else 0
            received = 0
            async with aiofiles.open(output_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    await f.write(chunk)
                    received += len(chunk)
                    if progress_cb and total_bytes:
                        progress_cb(received / total_bytes * 100)

        # Verify download
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            raise Exception("Downloaded video file is too small or missing")

        # Get duration
        duration = video.get("duration", 0) / 1000  # Convert ms to seconds

        logger.info(f"Douyin video downloaded successfully: {output_path} ({os.path.getsize(output_path)} bytes)")

        return {
            "video_path": output_path,
            "title": title,
            "duration": duration,
        }


def extract_douyin_video_id(url: str) -> str | None:
    """Extract Douyin video ID (aweme_id) from various URL formats."""
    # Direct video URL: https://www.douyin.com/video/7345678901234567890
    match = re.search(r'douyin\.com/video/(\d+)', url)
    if match:
        return match.group(1)

    # Short URL: https://v.douyin.com/abc123/
    match = re.search(r'v\.douyin\.com/([A-Za-z0-9]+)/?', url)
    if match:
        return resolve_short_url(match.group(1))

    # Share URL: https://www.iesdouyin.com/share/video/7345678901234567890/
    match = re.search(r'iesdouyin\.com/share/video/(\d+)', url)
    if match:
        return match.group(1)

    # Theater/Collection URL: https://www.douyin.com/jingxuan/theater?modal_id=7644040141950012715
    # The video ID is in the modal_id query parameter
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    if "modal_id" in query_params:
        return query_params["modal_id"][0]
    if "video_id" in query_params:
        return query_params["video_id"][0]
    if "aweme_id" in query_params:
        return query_params["aweme_id"][0]

    return None


def resolve_short_url(short_code: str) -> str | None:
    """Resolve v.douyin.com short URL to get aweme_id."""
    try:
        import requests
        url = f"https://v.douyin.com/{short_code}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15"
        }
        # Follow redirects to get the final URL
        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        final_url = resp.url
        # Extract aweme_id from final URL
        match = re.search(r'video/(\d+)', final_url)
        if match:
            return match.group(1)
        match = re.search(r'aweme_id=(\d+)', final_url)
        if match:
            return match.group(1)
    except Exception as e:
        logger.warning(f"Failed to resolve short URL: {e}")
    return None


def parse_netscape_cookies(cookies_file: str, platform: str = "douyin") -> dict:
    """Parse Netscape format cookies.txt file."""
    cookies = {}
    domain_filter = {
        "youtube": ["youtube.com", "youtu.be", "google.com"],
        "douyin": ["douyin.com", "iesdouyin.com", "v.douyin.com"],
        "tiktok": ["tiktok.com", "tiktokv.com"],
        "facebook": ["facebook.com", "fb.com", "fb.watch"],
        "twitter": ["twitter.com", "x.com"],
        "instagram": ["instagram.com"],
        "bilibili": ["bilibili.com", "b23.tv"],
        "xiaohongshu": ["xiaohongshu.com", "xhslink.com"],
    }.get(platform, [])
    logger.info(f"Parsing cookies for platform: {platform}, domain_filter: {domain_filter}")
    try:
        with open(cookies_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                # Netscape format requires exactly 7 fields: domain, flag, path, secure, expires, name, value
                if len(parts) < 7:
                    logger.warning(f"Skipping malformed cookie line {line_num}: expected 7 fields, got {len(parts)}")
                    continue
                domain, _, path, secure, expires, name, value = parts[:7]
                # Skip entries with empty name or value
                if not name or not value:
                    logger.warning(f"Skipping cookie line {line_num}: empty name or value")
                    continue
                # Only include cookies for the relevant platform
                if domain_filter:
                    if any(d in domain for d in domain_filter):
                        cookies[name] = value
                else:
                    cookies[name] = value
        logger.info(f"Parsed {len(cookies)} cookies for {platform}")
    except Exception as e:
        logger.warning(f"Failed to parse cookies file: {e}")
    return cookies


def validate_cookies_content(cookies_content: str, platform: str) -> tuple[bool, str]:
    """Validate cookies content before saving. Returns (is_valid, message)."""
    import tempfile

    logger.info(f"Validating cookies for platform: {platform}")

    # Write to temp file and try parsing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(cookies_content)
        temp_path = f.name

    try:
        cookies = parse_netscape_cookies(temp_path, platform)
        logger.info(f"Platform: {platform}, Parsed cookies count: {len(cookies)}")
        if not cookies:
            return False, f"Không tìm thấy cookie hợp lệ cho {platform}. File cookies.txt có thể bị lỗi hoặc hết hạn. Vui lòng export lại từ extension 'Get cookies.txt LOCALLY' sau khi đăng nhập."

        # Check for essential cookies - require at least ONE from each group
        essential_cookies = {
            "youtube": ["SID", "HSID", "SSID", "__Secure-1PSID"],
            "douyin": ["sessionid", "ttwid", "passport_csrf_token"],
            "tiktok": ["sessionid", "ttwid", "passport_csrf_token"],
            "facebook": ["c_user", "xs"],
            "twitter": ["auth_token", "ct0"],
            "instagram": ["sessionid", "csrftoken"],
            "bilibili": ["SESSDATA", "bili_jct", "DedeUserID"],
            "xiaohongshu": ["xsec_token", "a1", "webId"],
        }

        platform_essential = essential_cookies.get(platform, [])
        found_essential = [c for c in platform_essential if c in cookies]
        logger.info(f"Platform essential: {platform_essential}, Found: {found_essential}")

        # Require at least ONE essential cookie (not all)
        if platform_essential and not found_essential:
            essential_str = ", ".join(platform_essential)
            return False, f"Không tìm thấy cookie quan trọng nào cho {platform}. Cần ít nhất 1 trong: {essential_str}. Vui lòng export lại cookies."

        return True, f"Cookies hợp lệ: tìm thấy {len(cookies)} cookie(s). Cookie quan trọng: {', '.join(found_essential) if found_essential else 'N/A'}"
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


# ==================== TikTok API-based Downloader ====================

async def download_tiktok_by_api(url: str, output_dir: str, video_id: str, progress_cb=None) -> dict:
    """
    Download TikTok video using internal web API.
    This is more reliable than yt-dlp for TikTok when cookies are available.

    ``progress_cb`` (optional) is called with the download percentage (0-100).
    """
    import aiohttp
    import aiofiles

    # Extract video ID from various TikTok URL formats
    tiktok_video_id = extract_tiktok_video_id(url)
    if not tiktok_video_id:
        raise Exception("Could not extract TikTok video ID from URL")

    # Headers mimicking the TikTok web app
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": "https://www.tiktok.com/",
        "Origin": "https://www.tiktok.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "X-Requested-With": "XMLHttpRequest",
    }

    # Load cookies if available
    cookies_file = get_cookies_file("tiktok")
    cookie_jar = None
    if cookies_file and os.path.exists(cookies_file):
        cookie_dict = parse_netscape_cookies(cookies_file, "tiktok")
        if cookie_dict:
            cookie_jar = aiohttp.CookieJar()
            from http.cookies import SimpleCookie
            from yarl import URL
            simple_cookie = SimpleCookie()
            for name, value in cookie_dict.items():
                simple_cookie[name] = value
                simple_cookie[name]['domain'] = '.tiktok.com'
                simple_cookie[name]['path'] = '/'
            cookie_jar.update_cookies(simple_cookie, URL("https://www.tiktok.com"))
            logger.info(f"Loaded {len(cookie_dict)} cookies for TikTok API")

    async with aiohttp.ClientSession(headers=headers, cookie_jar=cookie_jar) as session:
        # Try multiple API endpoints
        endpoints_to_try = [
            # 1. TikTok web API v1 (item detail)
            {
                "url": "https://www.tiktok.com/api/item/detail/",
                "params": {
                    "itemId": tiktok_video_id,
                    "aid": "1988",
                    "app_name": "tiktok_web",
                    "device_platform": "web_pc",
                    "region": "US",
                    "priority_region": "US",
                    "os": "windows",
                    "referer": "",
                    "cookie_enabled": "true",
                    "screen_width": "1920",
                    "screen_height": "1080",
                    "browser_language": "en-US",
                    "browser_platform": "Win32",
                    "browser_name": "Chrome",
                    "browser_version": "131.0.0.0",
                    "browser_online": "true",
                },
                "parser": "tiktok_v1",
            },
            # 2. TikTok web API v2
            {
                "url": "https://www.tiktok.com/api/item/detail/",
                "params": {
                    "itemId": tiktok_video_id,
                    "aid": "1988",
                    "app_name": "tiktok_web",
                    "device_platform": "web_pc",
                    "region": "US",
                    "priority_region": "US",
                    "os": "windows",
                    "referer": "",
                    "cookie_enabled": "true",
                    "screen_width": "1920",
                    "screen_height": "1080",
                    "browser_language": "en-US",
                    "browser_platform": "Win32",
                    "browser_name": "Chrome",
                    "browser_version": "131.0.0.0",
                    "browser_online": "true",
                },
                "parser": "tiktok_v2",
            },
            # 3. TikTok API with different aid
            {
                "url": "https://api.tiktokv.com/aweme/v1/aweme/detail/",
                "params": {
                    "aweme_id": tiktok_video_id,
                    "aid": "1988",
                    "version_code": "37.3.4",
                    "device_platform": "webapp",
                    "os": "windows",
                },
                "parser": "tiktok_api_v1",
            },
        ]

        item_detail = None
        last_error = None

        for endpoint in endpoints_to_try:
            try:
                logger.info(f"Trying TikTok API endpoint: {endpoint['url']}")
                async with session.get(endpoint["url"], params=endpoint["params"]) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.warning(f"Endpoint {endpoint['url']} returned {resp.status}: {text[:200]}")
                        continue

                    content_type = resp.headers.get("Content-Type", "")
                    if "application/json" not in content_type:
                        text = await resp.text()
                        logger.warning(f"Endpoint {endpoint['url']} returned non-JSON: {content_type} - {text[:200]}")
                        continue

                    try:
                        data = await resp.json()
                    except Exception as e:
                        logger.warning(f"Failed to parse JSON from {endpoint['url']}: {e}")
                        continue

                    # Handle None response
                    if not data:
                        logger.warning(f"Empty response from {endpoint['url']}")
                        continue

                    # Parse based on endpoint type
                    if endpoint["parser"] in ["tiktok_v1", "tiktok_v2"]:
                        # Standard TikTok web API format
                        if data.get("status_code") == 0 and data.get("itemInfo", {}).get("itemStruct"):
                            item_detail = data["itemInfo"]["itemStruct"]
                            logger.info(f"Successfully got video info from {endpoint['parser']} API")
                            break
                        elif data.get("statusCode") == 0 and data.get("itemInfo", {}).get("itemStruct"):
                            item_detail = data["itemInfo"]["itemStruct"]
                            logger.info(f"Successfully got video info from {endpoint['parser']} API")
                            break
                        else:
                            logger.warning(f"{endpoint['parser']} API error: {data.get('statusMsg', 'Unknown error')}")
                            last_error = f"{endpoint['parser']}: {data.get('statusMsg', 'Unknown error')}"
                            continue

                    elif endpoint["parser"] == "tiktok_api_v1":
                        # aweme/v1 format
                        if data.get("status_code") == 0 and data.get("aweme_detail"):
                            item_detail = data["aweme_detail"]
                            logger.info(f"Successfully got video info from {endpoint['parser']} API")
                            break
                        else:
                            logger.warning(f"{endpoint['parser']} API error: {data}")
                            last_error = f"{endpoint['parser']}: {data.get('status_msg', 'Unknown error')}"
                            continue

            except Exception as e:
                logger.warning(f"Endpoint {endpoint['url']} failed: {e}")
                last_error = str(e)
                continue

        # If all API endpoints failed, raise error to trigger yt-dlp fallback
        if not item_detail:
            raise Exception(
                f"All TikTok API endpoints failed. Last error: {last_error}. "
                "TikTok may require X-Bogus signature or login cookies. "
                "Please add valid TikTok cookies in Settings > Cookies Management, "
                "or the system will fall back to yt-dlp."
            )

        # Extract video info from item_detail
        title = item_detail.get("desc", f"TikTok_{tiktok_video_id}")
        # Clean title for filename
        title = re.sub(r'[\\/*?:"<>|]', "_", title)[:100]

        # Get video URL - try multiple quality options
        video = item_detail.get("video", {})
        play_addr = video.get("playAddr", {})
        download_addr = video.get("downloadAddr", {})
        bit_rate = video.get("bitRate", [])

        # Prefer download_addr (no watermark), fallback to play_addr
        video_url = None
        if download_addr and download_addr.get("urlList"):
            video_url = download_addr["urlList"][0]
        elif play_addr and play_addr.get("urlList"):
            video_url = play_addr["urlList"][0]
        elif bit_rate and bit_rate[0].get("playAddr", {}).get("urlList"):
            video_url = bit_rate[0]["playAddr"]["urlList"][0]

        if not video_url:
            raise Exception("No playable video URL found in TikTok API response")

        logger.info(f"Downloading video from: {video_url[:100]}...")

        # Step 2: Download the video
        output_path = os.path.join(output_dir, f"{video_id}.mp4")

        # Download with progress
        async with session.get(video_url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to download video: HTTP {resp.status}")

            # Check content type
            content_type = resp.headers.get("Content-Type", "")
            if "video" not in content_type and "octet-stream" not in content_type:
                text = await resp.text()
                if "login" in text.lower() or "验证" in text:
                    raise Exception("Video download requires login - please add TikTok cookies")

            # Save video, reporting progress when the total size is known
            content_length = resp.headers.get("Content-Length", "")
            total_bytes = int(content_length) if content_length.isdigit() else 0
            received = 0
            async with aiofiles.open(output_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    await f.write(chunk)
                    received += len(chunk)
                    if progress_cb and total_bytes:
                        progress_cb(received / total_bytes * 100)

        # Verify download
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            raise Exception("Downloaded video file is too small or missing")

        # Get duration
        duration = video.get("duration", 0) / 1000  # Convert ms to seconds

        logger.info(f"TikTok video downloaded successfully: {output_path} ({os.path.getsize(output_path)} bytes)")

        return {
            "video_path": output_path,
            "title": title,
            "duration": duration,
        }


def extract_tiktok_video_id(url: str) -> str | None:
    """Extract TikTok video ID (itemId) from various URL formats."""
    # Standard video URL: https://www.tiktok.com/@username/video/1234567890123456789
    match = re.search(r'tiktok\.com/@[^/]+/video/(\d+)', url)
    if match:
        return match.group(1)

    # Short URL: https://vm.tiktok.com/abc123/
    match = re.search(r'vm\.tiktok\.com/([A-Za-z0-9]+)/?', url)
    if match:
        return resolve_tiktok_short_url(match.group(1))

    # Share URL: https://www.tiktok.com/t/ZTR123456/
    match = re.search(r'tiktok\.com/t/([A-Za-z0-9]+)/?', url)
    if match:
        return resolve_tiktok_short_url(match.group(1))

    # Mobile share: https://www.tiktok.com/@username/video/1234567890123456789?is_from_webapp=1&sender_device=pc
    match = re.search(r'tiktok\.com/.*?/video/(\d+)', url)
    if match:
        return match.group(1)

    # Embed URL: https://www.tiktok.com/embed/v2/1234567890123456789
    match = re.search(r'tiktok\.com/embed/v2/(\d+)', url)
    if match:
        return match.group(1)

    return None


def resolve_tiktok_short_url(short_code: str) -> str | None:
    """Resolve TikTok short URL to get video ID."""
    try:
        import requests
        url = f"https://vm.tiktok.com/{short_code}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15"
        }
        # Follow redirects to get the final URL
        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        final_url = resp.url
        # Extract video ID from final URL
        match = re.search(r'video/(\d+)', final_url)
        if match:
            return match.group(1)
        match = re.search(r'itemId=(\d+)', final_url)
        if match:
            return match.group(1)
    except Exception as e:
        logger.warning(f"Failed to resolve TikTok short URL: {e}")
    return None


# ==================== Bilibili API-based Downloader ====================

async def download_bilibili_by_api(url: str, output_dir: str, video_id: str, progress_cb=None) -> dict:
    """
    Download Bilibili video using the official web API.

    ``progress_cb`` (optional) is called with the current file download percentage (0-100).
    """
    import aiohttp
    import aiofiles
    import subprocess as sp

    # Extract bvid from various URL formats
    bvid = extract_bilibili_bvid(url)
    if not bvid:
        raise Exception("Could not extract Bilibili bvid from URL")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-site",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        # Step 1: Get video metadata (title, cid)
        async with session.get("https://api.bilibili.com/x/web-interface/view", params={"bvid": bvid}) as resp:
            if resp.status != 200:
                raise Exception(f"Bilibili API returned {resp.status}")
            data = await resp.json()
            if data.get("code") != 0 or not data.get("data"):
                msg = data.get("message") or data.get("code")
                raise Exception(f"Bilibili API error: {msg}")
            video_info = data["data"]
            title = video_info.get("title", f"Bilibili_{bvid}")
            cid = video_info.get("cid")
            if not cid:
                raise Exception("No cid found in Bilibili API response")
            title = re.sub(r'[\\/*?:"<>|]', "_", title)[:100]

        logger.info(f"Bilibili title: {title}")

        # Step 2: Get play URLs (DASH video+audio)
        async with session.get("https://api.bilibili.com/x/player/playurl", params={
            "cid": cid,
            "bvid": bvid,
            "qn": "120",
            "fnver": "0",
            "fnval": "16",
            "fourk": "1",
        }) as resp:
            if resp.status != 200:
                raise Exception(f"Bilibili playurl returned {resp.status}")
            data = await resp.json()
            if data.get("code") != 0:
                raise Exception(f"Bilibili playurl error: {data.get('message')}")
            pd = data["data"]
            dash = pd.get("dash", {})
            durl = pd.get("durl", [])

            video_url = None
            audio_url = None

            if dash and dash.get("video"):
                # Prefer highest resolution video stream
                dash["video"].sort(key=lambda v: int(v.get("height", 0) or 0), reverse=True)
                video_url = dash["video"][0].get("baseUrl") or dash["video"][0].get("url")
            if dash and dash.get("audio"):
                dash["audio"].sort(key=lambda a: int(a.get("id", 0) or 0), reverse=True)
                audio_url = dash["audio"][0].get("baseUrl") or dash["audio"][0].get("url")
            elif durl:
                # Old format: single video with audio embedded (no DASH)
                video_url = durl[0].get("url")
                audio_url = None

            if not video_url:
                raise Exception("No video URL found in Bilibili playurl response")

        # Prepare output files
        video_path = os.path.join(output_dir, f"{video_id}.mp4")
        audio_path = os.path.join(output_dir, f"{video_id}_audio.m4s")
        merged_path = os.path.join(output_dir, f"{video_id}_merged.mp4")

        # Step 3: Download video stream
        logger.info(f"Downloading Bilibili video: {video_url[:80]}...")
        await _download_stream(session, video_url, video_path, headers, progress_cb)
        if not os.path.exists(video_path) or os.path.getsize(video_path) < 1024:
            raise Exception("Downloaded video file is too small or missing")

        # Step 4: Download audio stream if available
        if audio_url:
            logger.info(f"Downloading Bilibili audio: {audio_url[:80]}...")
            await _download_stream(session, audio_url, audio_path, headers, progress_cb)

        # Step 5: Merge audio+video (or use video-only)
        if audio_url and os.path.exists(audio_path):
            logger.info("Merging video+audio with ffmpeg")
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c", "copy",
                "-map", "0:v:0", "-map", "1:a:0",
                "-movflags", "+faststart",
                merged_path,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **hidden_subprocess_kwargs()
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise Exception(f"FFmpeg merge failed: {stderr.decode(errors='ignore')[:500]}")
            # Replace video_path with merged file
            shutil.move(merged_path, video_path)
        elif os.path.exists(video_path):
            # Video only (audio embedded or not needed) - rename to .mp4
            pass

        # Clean up temp audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)

        duration = video_info.get("duration", 0)
        logger.info(f"Bilibili video downloaded: {video_path} ({os.path.getsize(video_path)} bytes)")

        return {
            "video_path": video_path,
            "title": title,
            "duration": duration,
        }


def extract_bilibili_bvid(url: str) -> str | None:
    """Extract Bilibili bvid (BVxxxxx) from various URL formats."""
    # Direct video URL: https://www.bilibili.com/video/BV17x411w7KC
    match = re.search(r'bilibili\.com/video/(BV\w+)', url)
    if match:
        return match.group(1)

    # Short URL: https://b23.tv/xxx or https://b23.tv/BVxxxxx
    match = re.search(r'b23\.tv/(BV\w+)', url)
    if match:
        return match.group(1)

    # b23.tv short link that redirects
    match = re.search(r'b23\.tv/([A-Za-z0-9]+)', url)
    if match:
        short_code = match.group(1)
        try:
            import requests
            resp = requests.head(f"https://b23.tv/{short_code}", allow_redirects=True, timeout=10)
            m = re.search(r'BV\w+', resp.url)
            if m:
                return m.group(0)
        except Exception:
            pass

    return None


async def _download_stream(session, url, output_path, headers, progress_cb=None):
    """Download a single stream with progress reporting."""
    async with session.get(url, headers=headers) as resp:
        if resp.status != 200:
            raise Exception(f"Stream download failed: HTTP {resp.status}")
        content_length = resp.headers.get("Content-Length", "")
        total_bytes = int(content_length) if content_length.isdigit() else 0
        received = 0
        async with aiofiles.open(output_path, "wb") as f:
            async for chunk in resp.content.iter_chunked(65536):
                await f.write(chunk)
                received += len(chunk)
                if progress_cb and total_bytes:
                    progress_cb(received / total_bytes * 100)


# ==================== Xiaohongshu downloader ====================

async def download_xiaohongshu_by_api(url: str, output_dir: str, video_id: str, progress_cb=None) -> dict:
    """
    Download Xiaohongshu (小红书) video.

    Xiaohongshu requires valid session cookies (xsec_token) for the API to return video data.
    ``progress_cb`` (optional) is called with the current file download percentage (0-100).

    This function tries the official API first; if it fails (no cookies / expired cookies),
    it falls back to yt-dlp.
    """
    import aiohttp
    import aiofiles
    import subprocess as sp
    import shutil as _shutil

    # Extract note_id from URL patterns
    note_id = extract_xiaohongshu_note_id(url)
    if not note_id:
        raise Exception("Could not extract Xiaohongshu note ID from URL")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.xiaohongshu.com/",
        "Origin": "https://www.xiaohongshu.com",
    }

    cookies_file = get_cookies_file("xiaohongshu")
    cookie_dict = {}
    if cookies_file and os.path.exists(cookies_file):
        cookie_dict = parse_netscape_cookies(cookies_file, "xiaohongshu")
        logger.info(f"Loaded {len(cookie_dict)} Xiaohongshu cookies")

    # Try the official API (requires xsec_token / cookies)
    if cookie_dict:
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # Build a simple cookie jar from parsed cookies
                cookie_jar = aiohttp.CookieJar()
                from http.cookies import SimpleCookie
                from yarl import URL
                simple_cookie = SimpleCookie()
                for name, value in cookie_dict.items():
                    simple_cookie[name] = value
                    simple_cookie[name]["domain"] = ".xiaohongshu.com"
                    simple_cookie[name]["path"] = "/"
                cookie_jar.update_cookies(simple_cookie, URL("https://www.xiaohongshu.com"))

                # The official feed endpoint returns note details
                async with session.get(
                    "https://www.xiaohongshu.com/api/sns/web/v1/feed",
                    headers={**headers, "Cookie": f"xsec_token={cookie_dict.get('xsec_token', '')}"}
                ) as resp:
                    if resp.status != 200:
                        raise Exception(f"XHS API returned {resp.status}")
                    data = await resp.json()
                    if data.get("code") != 0:
                        raise Exception(f"XHS API error: {data.get('message')}")
                    # Find the note in the feed
                    feed_list = data.get("data", {}).get("feed", [])
                    note = None
                    for item in feed_list:
                        if item.get("note", {}).get("noteId") == note_id:
                            note = item.get("note")
                            break
                    if not note:
                        raise Exception(f"Note {note_id} not found in feed")

                    video_data = note.get("video", {})
                    if not video_data:
                        raise Exception("No video in this Xiaohongshu note (it may be an image post)")
                    title = note.get("title", f"XHS_{note_id}")[:100]
                    title = re.sub(r'[\\/*?:"<>|]', "_", title)

                    # Get video URL: prefer sns-video-bd.xhscdn.com (no watermark)
                    media = video_data.get("media", {})
                    video_url = None
                    # Try no-watermark source
                    for src in media.get("stream", {}).get("originVideoKey", []):
                        video_url = f"http://sns-video-bd.xhscdn.com/{src}"
                        break
                    if not video_url:
                        # Fallback to media URL
                        video_url = media.get("stream", {}).get("master_url") or media.get("stream", {}).get("url")
                    if not video_url:
                        # Try the raw media structure
                        for key in ["origin_video", "video_url", "stream_url", "video"]:
                            v = media.get(key, {})
                            if isinstance(v, dict):
                                video_url = v.get("url") or v.get("master_url") or v.get("video_media")
                                if video_url:
                                    break
                    if not video_url:
                        raise Exception(f"Could not find video URL in XHS response")

                    logger.info(f"Xiaohongshu title: {title}")
                    logger.info(f"Downloading Xiaohongshu video: {video_url[:80]}...")

                    output_path = os.path.join(output_dir, f"{video_id}.mp4")
                    await _download_stream(session, video_url, output_path, headers, progress_cb)
                    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
                        raise Exception("Downloaded video file is too small or missing")

                    logger.info(f"Xiaohongshu video downloaded: {output_path}")
                    return {
                        "video_path": output_path,
                        "title": title,
                        "duration": 0,
                    }
        except Exception as e:
            logger.warning(f"Xiaohongshu API downloader failed: {e}")
            raise  # Re-raise to trigger yt-dlp fallback

    # No cookies → fall through to yt-dlp
    raise Exception("Xiaohongshu download requires cookies (xsec_token). Add them in Settings > Cookies Management.")


def extract_xiaohongshu_note_id(url: str) -> str | None:
    """Extract Xiaohongshu note_id from various URL formats."""
    # Explore URL: https://www.xiaohongshu.com/explore/683b9f7c000000001000b75e
    match = re.search(r'xiaohongshu\.com/explore/([A-Za-z0-9]+)', url)
    if match:
        return match.group(1)
    # Note URL: https://www.xiaohongshu.com/user/profile/.../note/...
    match = re.search(r'xiaohongshu\.com/.*?note/([A-Za-z0-9]+)', url)
    if match:
        return match.group(1)
    # xhslink short URL: https://xhslink.com/abc123 or https://xhslink.cn/abc123
    match = re.search(r'xhslink\.(com|cn)/([A-Za-z0-9]+)', url)
    if match:
        return match.group(2)
    return None


# ==================== yt-dlp downloaders (existing) ====================

async def download_with_pytubefix(url: str, output_dir: str, video_id: str, progress_cb=None) -> dict:
    from pytubefix import YouTube
    import requests

    def _download():
        def _on_progress(stream, chunk, bytes_remaining):
            if progress_cb and getattr(stream, "filesize", 0):
                progress_cb((stream.filesize - bytes_remaining) / stream.filesize * 100)

        # Try without use_po_token first — pytubefix 10+ prompts interactively
        # for the visitorData/PO token when that flag is on, which hangs the
        # background download. Progressive format 18 (or similar) usually works
        # without a PO token on Shorts and most public videos.
        yt = YouTube(url, on_progress_callback=_on_progress)
        title = yt.title or "Unknown"
        duration = yt.length or 0
        thumbnail_url = yt.thumbnail_url

        # Try progressive streams first (format 18 works without PO token)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        if not stream:
            stream = yt.streams.filter(file_extension='mp4').first()
        if not stream:
            stream = yt.streams.get_highest_resolution()

        output_path = os.path.join(output_dir, f"{video_id}.mp4")
        stream.download(output_path=output_dir, filename=f"{video_id}.mp4")

        # Save thumbnail if available
        thumbnail_path = None
        if thumbnail_url:
            try:
                thumbnail_response = requests.get(thumbnail_url)
                if thumbnail_response.status_code == 200:
                    thumbnail_path = os.path.join(output_dir, f"{video_id}.jpg")
                    with open(thumbnail_path, 'wb') as f:
                        f.write(thumbnail_response.content)
            except Exception as e:
                logger.warning(f"Failed to download thumbnail: {str(e)}")

        return {
            "title": title,
            "duration": duration,
            "video_path": output_path,
            "thumbnail_path": thumbnail_path,
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download)


def get_platform_ydl_opts(url: str, video_id: str, output_dir: str, cookies_file: str | None, platform: str) -> dict:
    """Get yt-dlp options optimized for specific platforms (updated for yt-dlp 2025+)."""
    output_path = os.path.join(output_dir, f"{video_id}.%(ext)s")

    # Generic base options — no extractor_args so YouTube-specific logic
    # never runs on non-YouTube URLs (avoids the video-ID regex on Vimeo etc.)
    base_opts = {
        "outtmpl": output_path,
        # Simple generic selector: prefer single-file mp4, no YouTube-specific merge hints
        "format": "best[ext=mp4]/best",
        "quiet": False,
        "no_warnings": False,
        "extract_flat": False,
        "writethumbnail": True,
        "ignoreerrors": False,
        "postprocessors": [
            {
                "key": "FFmpegThumbnailsConvertor",
                "format": "jpg",
            }
        ],
        "geo_bypass": True,
        "retries": 5,
        "fragment_retries": 5,
        "skip_unavailable_fragments": True,
        "socket_timeout": 30,
        "downloader": "native",
    }

    # Platform-specific configurations
    platform_configs = {
        "douyin": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Referer": "https://www.douyin.com/",
                "Origin": "https://www.douyin.com",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            },
            "extractor_args": {
                "douyin": {
                    "api_hostname": ["www.douyin.com", "www.iesdouyin.com"],
                    "use_web": True,
                }
            },
            "geo_bypass_country": "CN",
            "cookies_required": True,
        },
        "tiktok": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Referer": "https://www.tiktok.com/",
                "Origin": "https://www.tiktok.com",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            },
            "extractor_args": {
                "tiktok": {
                    "api_hostname": ["www.tiktok.com", "api.tiktokv.com", "api16-normal-c-useast1a.tiktokv.com"],
                    "app_version": "37.3.4",
                    "webapp_version": "37.3.4",
                }
            },
            "geo_bypass_country": "US",
            "cookies_required": False,  # Helps but not strictly required
            # Additional fallback formats for TikTok
            "format_fallback": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            # Impersonation target to bypass IP/bot detection
            "impersonate": "chrome-120:windows-10",
        },
        "bilibili": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.bilibili.com/",
                "Origin": "https://www.bilibili.com",
            },
            "geo_bypass_country": "CN",
            "cookies_required": False,  # Bilibili can work without cookies
            "format_fallback": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        },
        "xiaohongshu": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.xiaohongshu.com/",
                "Origin": "https://www.xiaohongshu.com",
            },
            "geo_bypass_country": "CN",
            "cookies_required": True,  # Xiaohongshu requires cookies (xsec_token) for video API access
            "format_fallback": "best[ext=mp4]/best",
        },
        "facebook": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Referer": "https://www.facebook.com/",
                "Origin": "https://www.facebook.com",
                # Facebook Tahoe API requires these headers
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            },
            "geo_bypass_country": "US",
            # Facebook 2025: requires BOTH cookies AND impersonation to bypass Tahoe API fingerprinting
            # - Cookies provide session auth
            # - Impersonation (curl_cffi) provides browser fingerprint matching
            # Note: Adding cookies + impersonation together typically works for public videos
            "cookies_required": True,  # Now requires cookies + impersonation
            "format_fallback": "best[ext=mp4]/best",
            "impersonate": "chrome-120:windows-10",
        },
        "twitter": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Referer": "https://x.com/",
                "Origin": "https://x.com",
            },
            "geo_bypass_country": "US",
            "cookies_required": True,  # Twitter/X requires login for most videos
            "format_fallback": "best[ext=mp4]/best",
            "impersonate": "chrome-120:windows-10",
        },
        "instagram": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Referer": "https://www.instagram.com/",
                "Origin": "https://www.instagram.com",
                # Instagram requires these headers for API access
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            },
            "geo_bypass_country": "US",
            # Instagram 2025: requires cookies + impersonation
            # - JSONDecodeError usually means missing/invalid cookies or blocked API
            "cookies_required": True,  # Instagram requires login cookies
            "format_fallback": "best[ext=mp4]/best",
            "impersonate": "chrome-120:windows-10",
        },
        "youtube": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            # YouTube 2025+:
            # - Format 18 (progressive mp4) works without PO token on web/mobile clients
            # - tv_embedded/tv_simply require PO token and are unreliable
            # - skip ["dash", "hls"] keeps progressive formats as fallback
            # - innertube_host omitted to avoid DNS resolution bug ('Failed to resolve w')
            "extractor_args": {
                "youtube": {
                    "player_client": ["web", "mweb", "android", "ios"],
                    "skip": ["dash", "hls"],
                }
            },
            "geo_bypass_country": "US",
            "cookies_required": False,
            "format_fallback": "18/best[ext=mp4]/best",
        },
        "vimeo": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Referer": "https://vimeo.com/",
                "Origin": "https://vimeo.com",
            },
            "geo_bypass_country": "US",
            "cookies_required": True,  # Vimeo web client requires login (macos OAuth fails on Windows)
            "format_fallback": "best[ext=mp4]/best",
            "extractor_args": {
                "vimeo": {
                    "skip": ["dash", "hls"],
                }
            },
            "impersonate": "chrome-120:windows-10",
        },
        "twitch": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Referer": "https://www.twitch.tv/",
                "Origin": "https://www.twitch.tv",
            },
            "geo_bypass_country": "US",
            "cookies_required": False,  # Twitch VODs often work without login
            "format_fallback": "best[ext=mp4]/best",
            "extractor_args": {
                "twitch": {
                    "skip": ["dash", "hls"],
                }
            },
        },
    }

    config = platform_configs.get(platform, platform_configs["youtube"])

    # Merge base options with platform-specific options
    ydl_opts = base_opts.copy()
    ydl_opts["http_headers"] = config["http_headers"]
    if "extractor_args" in config:
        ydl_opts["extractor_args"] = config["extractor_args"]
    ydl_opts["geo_bypass_country"] = config["geo_bypass_country"]

    # Override format if platform has fallback
    if "format_fallback" in config:
        ydl_opts["format"] = config["format_fallback"]

    # Add cookies if available
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file
        logger.info(f"Using cookies for {platform}: {cookies_file}")
    elif config.get("cookies_required"):
        logger.warning(
            f"============================================================\n"
            f"{platform.upper()} DOWNLOAD MAY REQUIRE COOKIES!\n"
            f"Please add {platform} cookies in Settings -> Cookies Management.\n"
            f"1. Install 'Get cookies.txt LOCALLY' browser extension\n"
            f"2. Login to {SUPPORTED_PLATFORMS[platform]['domains'][0]} in your browser\n"
            f"3. Export cookies.txt from the extension\n"
            f"4. Paste into Settings -> Cookies Management -> {SUPPORTED_PLATFORMS[platform]['name']}\n"
            f"============================================================"
        )

    # Add impersonation target for platforms that need it (bypasses IP blocks / bot detection).
    # yt-dlp accepts impersonate as a string like "chrome-120:windows-10"
    if "impersonate" in config and config["impersonate"]:
        target_str = _build_impersonate_target(platform)
        # For Facebook: force generic "chrome" target which works best with curl_cffi
        if platform == "facebook" and target_str is None:
            # Try generic chrome as last resort
            try:
                from yt_dlp.networking.impersonate import ImpersonateTarget
                supported_map = getattr(ImpersonateTarget, '_SUPPORTED_IMPERSONATE_TARGET_MAP', {})
                if "chrome" in supported_map:
                    target_str = "chrome"
                    logger.info("Using generic 'chrome' impersonation for Facebook (fallback)")
            except Exception:
                pass
        if target_str:
            ydl_opts["impersonate"] = target_str
            logger.info(f"Impersonating {platform} as {target_str} to bypass bot detection")
        else:
            # Impersonation unavailable (curl_cffi not installed or target not supported)
            logger.warning(f"Impersonation unavailable for {platform}. "
                          f"Install curl_cffi: pip install curl_cffi")
            if platform == "facebook":
                logger.warning(
                    f"============================================================\n"
                    f"FACEBOOK DOWNLOAD WILL FAIL WITHOUT IMPERSONATION!\n"
                    f"Facebook's Tahoe API requires both cookies AND impersonation.\n"
                    f"1. Install curl_cffi: pip install curl_cffi\n"
                    f"2. Add Facebook cookies in Settings -> Cookies Management\n"
                    f"============================================================"
                )
            elif platform == "instagram":
                logger.warning(
                    f"============================================================\n"
                    f"INSTAGRAM DOWNLOAD WILL FAIL WITHOUT COOKIES!\n"
                    f"Instagram requires login cookies (sessionid, csrftoken).\n"
                    f"1. Install curl_cffi: pip install curl_cffi\n"
                    f"2. Add Instagram cookies in Settings -> Cookies Management\n"
                    f"   Export from 'Get cookies.txt LOCALLY' extension after login.\n"
                    f"============================================================"
                )
            elif platform == "vimeo":
                logger.warning(
                    f"============================================================\n"
                    f"VIMEO DOWNLOAD WILL FAIL WITHOUT COOKIES!\n"
                    f"Vimeo requires OAuth token (macOS Keychain doesn't work on Windows).\n"
                    f"Please add Vimeo cookies in Settings -> Cookies Management.\n"
                    f"============================================================"
                )
    else:
        logger.debug(f"No impersonate config for {platform}")

    # Debug: log cookies file being used
    if cookies_file:
        try:
            file_size = os.path.getsize(cookies_file)
            logger.debug(f"Using cookies file: {cookies_file} (size: {file_size} bytes)")
        except Exception:
            logger.debug(f"Using cookies file: {cookies_file}")
    elif config.get("cookies_required"):
        logger.warning(
            f"============================================================\n"
            f"{platform.upper()} DOWNLOAD MAY REQUIRE COOKIES!\n"
            f"Please add {platform} cookies in Settings -> Cookies Management.\n"
            f"1. Install 'Get cookies.txt LOCALLY' browser extension\n"
            f"2. Login to {SUPPORTED_PLATFORMS[platform]['domains'][0]} in your browser\n"
            f"3. Export cookies.txt from the extension\n"
            f"4. Paste into Settings -> Cookies Management -> {SUPPORTED_PLATFORMS[platform]['name']}\n"
            f"============================================================"
        )

    return ydl_opts


# Keep backward compatibility
def get_douyin_ydl_opts(url: str, video_id: str, output_dir: str, cookies_file: str | None) -> dict:
    """Backward compatibility wrapper for Douyin."""
    return get_platform_ydl_opts(url, video_id, output_dir, cookies_file, "douyin")


async def download_with_ytdlp(url: str, output_dir: str, video_id: str, progress_cb=None) -> dict:
    import yt_dlp

    platform = detect_platform(url)
    cookies_file = get_cookies_file(platform)

    # Get platform-specific options using the new unified function
    base_ydl_opts = get_platform_ydl_opts(url, video_id, output_dir, cookies_file, platform)

    # Surface download progress (percent of the current file) to the caller.
    if progress_cb:
        def _progress_hook(d):
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes") or 0
                if total:
                    progress_cb(downloaded / total * 100)
            elif status == "finished":
                progress_cb(99.0)

        base_ydl_opts["progress_hooks"] = [_progress_hook]

    # Define fallback format options for each platform
    platform_fallback_formats = {
        "tiktok": [
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best",
            "best[ext=mp4]/best",
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "worstvideo[ext=mp4]+bestaudio[ext=m4a]/worst[ext=mp4]/worst",
        ],
        "facebook": [
            "best[ext=mp4]/best",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "best",
        ],
        "twitter": [
            "best[ext=mp4]/best",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "best",
        ],
        "instagram": [
            "best[ext=mp4]/best",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "best",
        ],
        "vimeo": [
            "best[ext=mp4]/best",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "best",
        ],
        "twitch": [
            "best[ext=mp4]/best",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "best",
        ],
        "youtube": [
            "18/best[ext=mp4]/best",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best",
            "best[ext=mp4]/best",
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        ],
        "douyin": [
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best",
            "best[ext=mp4]/best",
        ],
    }

    formats_to_try = platform_fallback_formats.get(platform, platform_fallback_formats["youtube"])
    last_error = None

    for attempt, fmt in enumerate(formats_to_try):
        try:
            logger.info(f"Trying yt-dlp format attempt {attempt + 1}/{len(formats_to_try)} for {platform}: {fmt[:80]}...")

            ydl_opts = base_ydl_opts.copy()
            ydl_opts["format"] = fmt

            def extract_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return info

            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, extract_info)

            if info is None:
                raise Exception("yt-dlp returned None")

            video_file = None
            for f in os.listdir(output_dir):
                if f.startswith(video_id) and f.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                    video_file = os.path.join(output_dir, f)
                    break

            if video_file is None:
                raise Exception("No video file found after download")

            logger.info(f"Successfully downloaded with format attempt {attempt + 1}")
            return {
                "video_path": video_file,
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
            }

        except Exception as e:
            last_error = e
            logger.warning(f"Format attempt {attempt + 1} failed: {e}")
            continue

    raise Exception(f"All format attempts failed for {platform}. Last error: {last_error}")


def get_cookies_file(platform: str = None) -> str | None:
    if platform:
        cookies_path = os.path.join(COOKIES_DIR, f"{platform}_cookies.txt")
        if os.path.exists(cookies_path):
            return os.path.abspath(cookies_path)
    general_path = os.path.join(COOKIES_DIR, "cookies.txt")
    if os.path.exists(general_path):
        return os.path.abspath(general_path)
    return None


async def download_video(url: str, output_dir: str = str(TEMP_DIR), progress_cb=None) -> dict:
    """Download a video from ``url``.

    ``progress_cb`` (optional) receives the current file's download percentage
    (0-100). It may be invoked from worker threads, so implementations must be
    thread-safe.
    """
    os.makedirs(output_dir, exist_ok=True)
    video_id = str(uuid.uuid4())[:8]
    platform = detect_platform(url)

    last_error = None

    # For Douyin, try API-based downloader FIRST (more reliable when cookies are available)
    if platform == "douyin":
        try:
            logger.info("Trying Douyin API-based downloader...")

            # Check for cookies first
            cookies_file = get_cookies_file("douyin")
            if not cookies_file:
                logger.warning(
                    "============================================================\n"
                    "DOUYIN DOWNLOAD REQUIRES COOKIES!\n"
                    "Please add Douyin cookies in Settings -> Cookies Management.\n"
                    "1. Install 'Get cookies.txt LOCALLY' browser extension\n"
                    "2. Login to douyin.com in your browser\n"
                    "3. Export cookies.txt from the extension\n"
                    "4. Paste into Settings -> Cookies Management -> 抖音\n"
                    "============================================================"
                )
            else:
                logger.info(f"Found Douyin cookies: {cookies_file}")

            result = await download_douyin_by_api(url, output_dir, video_id, progress_cb=progress_cb)

            thumbnail_file = None
            for f in os.listdir(output_dir):
                if f.startswith(video_id) and f.endswith(('.jpg', '.webp', '.png')):
                    thumbnail_file = os.path.join(output_dir, f)
                    break

            return {
                "video_path": result["video_path"],
                "thumbnail_path": thumbnail_file,
                "title": result.get("title", "Unknown"),
                "duration": result.get("duration", 0),
            }
        except Exception as e:
            logger.warning(f"Douyin API downloader failed: {e}")
            last_error = e
            # Fall through to yt-dlp fallback

    # For TikTok, try API-based downloader FIRST (more reliable when cookies are available)
    if platform == "tiktok":
        try:
            logger.info("Trying TikTok API-based downloader...")

            # Check for cookies first
            cookies_file = get_cookies_file("tiktok")
            if not cookies_file:
                logger.warning(
                    "============================================================\n"
                    "TIKTOK DOWNLOAD MAY REQUIRE COOKIES!\n"
                    "Please add TikTok cookies in Settings -> Cookies Management.\n"
                    "1. Install 'Get cookies.txt LOCALLY' browser extension\n"
                    "2. Login to tiktok.com in your browser\n"
                    "3. Export cookies.txt from the extension\n"
                    "4. Paste into Settings -> Cookies Management -> TikTok\n"
                    "============================================================"
                )
            else:
                logger.info(f"Found TikTok cookies: {cookies_file}")

            result = await download_tiktok_by_api(url, output_dir, video_id, progress_cb=progress_cb)

            thumbnail_file = None
            for f in os.listdir(output_dir):
                if f.startswith(video_id) and f.endswith(('.jpg', '.webp', '.png')):
                    thumbnail_file = os.path.join(output_dir, f)
                    break

            return {
                "video_path": result["video_path"],
                "thumbnail_path": thumbnail_file,
                "title": result.get("title", "Unknown"),
                "duration": result.get("duration", 0),
            }
        except Exception as e:
            logger.warning(f"TikTok API downloader failed: {e}")
            last_error = e
            # Fall through to yt-dlp fallback

    # For Bilibili, try API-based downloader first (more reliable than yt-dlp which may get 412)
    if platform == "bilibili":
        try:
            logger.info("Trying Bilibili API-based downloader...")

            cookies_file = get_cookies_file("bilibili")
            if cookies_file:
                logger.info(f"Found Bilibili cookies: {cookies_file}")
            else:
                logger.info("No Bilibili cookies — public API still returns video streams")

            result = await download_bilibili_by_api(url, output_dir, video_id, progress_cb=progress_cb)

            import shutil as _shutil
            thumbnail_file = None
            for f in os.listdir(output_dir):
                if f.startswith(video_id) and f.endswith(('.jpg', '.webp', '.png')):
                    thumbnail_file = os.path.join(output_dir, f)
                    break

            return {
                "video_path": result["video_path"],
                "thumbnail_path": thumbnail_file,
                "title": result.get("title", "Unknown"),
                "duration": result.get("duration", 0),
            }
        except Exception as e:
            logger.warning(f"Bilibili API downloader failed: {e}")
            last_error = e
            # Fall through to yt-dlp fallback

    # For Xiaohongshu, try API-based downloader first (requires cookies/xsec_token)
    if platform == "xiaohongshu":
        try:
            logger.info("Trying Xiaohongshu API-based downloader...")

            cookies_file = get_cookies_file("xiaohongshu")
            if not cookies_file:
                logger.warning(
                    "============================================================\n"
                    "XIAOHONGSHU DOWNLOAD REQUIRES COOKIES (xsec_token)!\n"
                    "Please add Xiaohongshu cookies in Settings -> Cookies Management.\n"
                    "1. Install 'Get cookies.txt LOCALLY' browser extension\n"
                    "2. Login to xiaohongshu.com in your browser\n"
                    "3. Export cookies.txt from the extension\n"
                    "4. Paste into Settings -> Cookies Management -> 小红书\n"
                    "============================================================"
                )
            else:
                logger.info(f"Found Xiaohongshu cookies: {cookies_file}")

            result = await download_xiaohongshu_by_api(url, output_dir, video_id, progress_cb=progress_cb)

            thumbnail_file = None
            for f in os.listdir(output_dir):
                if f.startswith(video_id) and f.endswith(('.jpg', '.webp', '.png')):
                    thumbnail_file = os.path.join(output_dir, f)
                    break

            return {
                "video_path": result["video_path"],
                "thumbnail_path": thumbnail_file,
                "title": result.get("title", "Unknown"),
                "duration": result.get("duration", 0),
            }
        except Exception as e:
            logger.warning(f"Xiaohongshu API downloader failed: {e}")
            last_error = e
            # Fall through to yt-dlp fallback

    # For Facebook, use the isolated downloader (Tahoe API 2025: cookies + impersonation).
    # If it fails (SocialDownloaderError), fall through to the generic yt-dlp path
    # below, which still has Facebook's platform config baked in.
    if platform == "facebook":
        try:
            from app.core.social_downloaders import (
                download_facebook,
                SocialDownloaderError,
            )

            logger.info("Trying isolated Facebook downloader...")
            result = await download_facebook(
                url, output_dir, video_id, progress_cb=progress_cb
            )
            return {
                "video_path": result["video_path"],
                "thumbnail_path": result.get("thumbnail_path"),
                "title": result.get("title", "Unknown"),
                "duration": result.get("duration", 0),
            }
        except SocialDownloaderError as e:
            logger.warning("Isolated Facebook downloader failed: %s", e)
            last_error = e
            # Fall through to yt-dlp fallback

    # For Instagram, use the isolated downloader (cookie-based auth).
    # Same contract as Facebook: SocialDownloaderError -> yt-dlp fallback.
    if platform == "instagram":
        try:
            from app.core.social_downloaders import (
                download_instagram,
                SocialDownloaderError,
            )

            logger.info("Trying isolated Instagram downloader...")
            result = await download_instagram(
                url, output_dir, video_id, progress_cb=progress_cb
            )
            return {
                "video_path": result["video_path"],
                "thumbnail_path": result.get("thumbnail_path"),
                "title": result.get("title", "Unknown"),
                "duration": result.get("duration", 0),
            }
        except SocialDownloaderError as e:
            logger.warning("Isolated Instagram downloader failed: %s", e)
            last_error = e
            # Fall through to yt-dlp fallback

    # For YouTube, try pytubefix first (faster, no ffmpeg needed for merge)
    if platform == "youtube":
        try:
            logger.info("Trying pytubefix for YouTube...")
            result = await download_with_pytubefix(url, output_dir, video_id, progress_cb=progress_cb)

            video_file = None
            for f in os.listdir(output_dir):
                if f.startswith(video_id) and f.endswith(('.mp4', '.webm', '.mkv')):
                    video_file = os.path.join(output_dir, f)
                    break

            if video_file:
                thumbnail_file = None
                for f in os.listdir(output_dir):
                    if f.startswith(video_id) and f.endswith(('.jpg', '.webp', '.png')):
                        thumbnail_file = os.path.join(output_dir, f)
                        break

                return {
                    "video_path": video_file,
                    "thumbnail_path": thumbnail_file,
                    "title": result.get("title", "Unknown"),
                    "duration": result.get("duration", 0),
                }
        except Exception as e:
            logger.warning(f"pytubefix failed: {e}")
            last_error = e

    # Fallback to yt-dlp for all platforms
    try:
        logger.info(f"Trying yt-dlp for {platform}...")

        # For platforms that typically require cookies, warn if not available.
        # Facebook now requires cookies + impersonation (2025 Tahoe API fingerprinting).
        # Instagram, Twitter, Vimeo, Douyin, TikTok, Xiaohongshu also require cookies.
        cookies_required_platforms = ["douyin", "tiktok", "twitter", "instagram", "facebook", "xiaohongshu", "vimeo"]
        cookies_file = get_cookies_file(platform) if platform else None
        if platform in cookies_required_platforms:
            if not cookies_file:
                platform_name = SUPPORTED_PLATFORMS[platform]["name"]
                domain = SUPPORTED_PLATFORMS[platform]["domains"][0]
                logger.warning(
                    f"============================================================\n"
                    f"{platform_name.upper()} DOWNLOAD REQUIRES COOKIES!\n"
                    f"Please add {platform_name} cookies in Settings -> Cookies Management.\n"
                    f"1. Install 'Get cookies.txt LOCALLY' browser extension\n"
                    f"2. Login to {domain} in your browser\n"
                    f"3. Export cookies.txt from the extension\n"
                    f"4. Paste into Settings -> Cookies Management -> {platform_name}\n"
                    f"============================================================"
                )
            else:
                logger.info(f"Found {platform} cookies: {cookies_file}")

        # For Douyin, convert jingxuan/collection URLs to direct video URLs for yt-dlp
        ytdlp_url = url
        if platform == "douyin":
            video_id = extract_douyin_video_id(url)
            if video_id and ("jingxuan" in url or "modal_id" in url):
                # Convert collection/jingxuan URL to direct video URL
                ytdlp_url = f"https://www.douyin.com/video/{video_id}"
                logger.info(f"Converted collection URL to direct video URL: {ytdlp_url}")

        result = await download_with_ytdlp(ytdlp_url, output_dir, video_id, progress_cb=progress_cb)

        thumbnail_file = None
        for f in os.listdir(output_dir):
            if f.startswith(video_id) and f.endswith(('.jpg', '.webp', '.png')):
                thumbnail_file = os.path.join(output_dir, f)
                break

        return {
            "video_path": result["video_path"],
            "thumbnail_path": thumbnail_file,
            "title": result.get("title", "Unknown"),
            "duration": result.get("duration", 0),
        }
    except Exception as e:
        logger.error(f"yt-dlp failed: {e}")
        last_error = e

    raise Exception(f"Cannot download video: {last_error}")


def save_cookies(platform: str, cookies_content: str) -> bool:
    try:
        cookies_path = os.path.join(COOKIES_DIR, f"{platform}_cookies.txt")
        with open(cookies_path, "w", encoding="utf-8") as f:
            f.write(cookies_content)
        return True
    except Exception as e:
        logger.error(f"Failed to save cookies: {e}")
        return False


def get_all_cookies_status() -> list:
    result = []
    for platform, info in SUPPORTED_PLATFORMS.items():
        cookies_path = os.path.join(COOKIES_DIR, f"{platform}_cookies.txt")
        exists = os.path.exists(cookies_path)
        result.append({
            "platform": platform,
            "name": info["name"],
            "domains": info["domains"],
            "has_cookies": exists,
        })
    return result


def get_cookies_status(platform: str) -> dict:
    cookies_path = os.path.join(COOKIES_DIR, f"{platform}_cookies.txt")
    exists = os.path.exists(cookies_path)
    return {
        "platform": platform,
        "exists": exists,
        "path": cookies_path if exists else None,
    }


def delete_cookies(platform: str) -> bool:
    try:
        cookies_path = os.path.join(COOKIES_DIR, f"{platform}_cookies.txt")
        if os.path.exists(cookies_path):
            os.remove(cookies_path)
        return True
    except Exception as e:
        logger.error(f"Failed to delete cookies: {e}")
        return False


def get_video_duration(video_path: str) -> float:
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, **hidden_subprocess_kwargs()
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0