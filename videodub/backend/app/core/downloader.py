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

COOKIES_DIR = str(DATA_COOKIES_DIR)
os.makedirs(COOKIES_DIR, exist_ok=True)

SUPPORTED_PLATFORMS = {
    "youtube": {"name": "YouTube", "domains": ["youtube.com", "youtu.be", "google.com"]},
    "tiktok": {"name": "TikTok", "domains": ["tiktok.com", "tiktokv.com"]},
    "douyin": {"name": "抖音", "domains": ["douyin.com", "v.douyin.com", "iesdouyin.com", "live.douyin.com"]},
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
    import os

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
        except:
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
            simple_cookie = SimpleCookie()
            for name, value in cookie_dict.items():
                simple_cookie[name] = value
                simple_cookie[name]['domain'] = '.tiktok.com'
                simple_cookie[name]['path'] = '/'
            cookie_jar.update_cookies(simple_cookie, "https://www.tiktok.com")
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

                    data = await resp.json()

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


# ==================== yt-dlp downloaders (existing) ====================

async def download_with_pytubefix(url: str, output_dir: str, video_id: str, progress_cb=None) -> dict:
    from pytubefix import YouTube
    import requests

    def _download():
        def _on_progress(stream, chunk, bytes_remaining):
            if progress_cb and getattr(stream, "filesize", 0):
                progress_cb((stream.filesize - bytes_remaining) / stream.filesize * 100)

        yt = YouTube(url, on_progress_callback=_on_progress)
        title = yt.title or "Unknown"
        duration = yt.length or 0
        thumbnail_url = yt.thumbnail_url

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

    # Base options common to all platforms
    base_opts = {
        "outtmpl": output_path,
        # Use more flexible format selection - try multiple combinations
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best",
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
        "retries": 5,  # Increased retries
        "fragment_retries": 5,
        "skip_unavailable_fragments": True,
        # Add socket timeout
        "socket_timeout": 30,
        # Prefer native downloader when possible
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
            },
            "extractor_args": {
                "facebook": {
                    "api_version": "v21.0",
                }
            },
            "geo_bypass_country": "US",
            "cookies_required": True,  # Most Facebook videos require login
            "format_fallback": "best[ext=mp4]/best",
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
            "extractor_args": {
                "twitter": {
                    "api_version": "2",
                }
            },
            "geo_bypass_country": "US",
            "cookies_required": True,  # Twitter/X requires login for most videos
            "format_fallback": "best[ext=mp4]/best",
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
            },
            "extractor_args": {
                "instagram": {
                    "api_version": "v1",
                }
            },
            "geo_bypass_country": "US",
            "cookies_required": True,  # Instagram requires login for most content
            "format_fallback": "best[ext=mp4]/best",
        },
        "youtube": {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["web", "mweb", "android", "tv_embedded"],
                    "skip": ["dash", "hls"],
                    "innertube_host": "www.youtube.com",
                }
            },
            "geo_bypass_country": "US",
            "cookies_required": False,
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
            "extractor_args": {
                "vimeo": {
                    "api_version": "3",
                }
            },
            "geo_bypass_country": "US",
            "cookies_required": False,
            "format_fallback": "best[ext=mp4]/best",
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
            "extractor_args": {
                "twitch": {
                    "api_version": "5",
                }
            },
            "geo_bypass_country": "US",
            "cookies_required": False,  # Twitch VODs often work without login
            "format_fallback": "best[ext=mp4]/best",
        },
    }

    config = platform_configs.get(platform, platform_configs["youtube"])

    # Merge base options with platform-specific options
    ydl_opts = base_opts.copy()
    ydl_opts["http_headers"] = config["http_headers"]
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

        # For platforms that typically require cookies, warn if not available
        cookies_required_platforms = ["douyin", "tiktok", "facebook", "twitter", "instagram"]
        if platform in cookies_required_platforms:
            cookies_file = get_cookies_file(platform)
            if not cookies_file:
                platform_name = SUPPORTED_PLATFORMS[platform]["name"]
                domain = SUPPORTED_PLATFORMS[platform]["domains"][0]
                logger.warning(
                    f"============================================================\n"
                    f"{platform_name.upper()} DOWNLOAD MAY REQUIRE COOKIES!\n"
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

    # Final fallback: try pytubefix for non-YouTube, non-Douyin (some sites may work)
    if platform not in ["youtube", "douyin"]:
        try:
            logger.info("Trying pytubefix as fallback...")
            result = await download_with_pytubefix(url, output_dir, video_id, progress_cb=progress_cb)

            video_file = None
            for f in os.listdir(output_dir):
                if f.startswith(video_id) and f.endswith(('.mp4', '.webm', '.mkv')):
                    video_file = os.path.join(output_dir, f)
                    break

            if video_file:
                return {
                    "video_path": video_file,
                    "thumbnail_path": None,
                    "title": result.get("title", "Unknown"),
                    "duration": result.get("duration", 0),
                }
        except Exception as e:
            logger.error(f"pytubefix fallback failed: {e}")
            last_error = e

    raise Exception(f"Không thể tải video: {last_error}")


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