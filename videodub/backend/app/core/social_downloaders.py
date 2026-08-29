"""Isolated Facebook and Instagram downloader module.

This file owns the configuration and entry points for Facebook and Instagram
downloads. It is kept separate from ``downloader.py`` so that:

- changes to Facebook's Tahoe API or Instagram's cookie-based auth do not
  touch TikTok, Douyin, YouTube, Bilibili, XHS, Twitter, Vimeo, Twitch
  configuration;
- the same impersonation/headers logic can be tweaked and tested in one
  place without merge conflicts in a 2000-line file;
- the caller can fall back to the main ``download_with_ytdlp`` path
  transparently by catching :class:`SocialDownloaderError`.

Facebook (2025+) requires BOTH:

1. Login cookies (e.g. ``c_user``, ``xs``) — these authenticate the session.
2. curl_cffi impersonation (browser fingerprint) — Facebook's "Tahoe" API
   fingerprints the TLS/HTTP2/header ordering and rejects requests from
   Python's urllib/requests default fingerprint.

Instagram requires the same two factors (cookies + impersonation), plus the
``sessionid`` and ``csrftoken`` cookies to be present and not expired.
"""

import logging
import os
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class SocialDownloaderError(Exception):
    """Raised when a Facebook/Instagram download cannot be configured or run."""


# ---------------------------------------------------------------------------
# Browser impersonation targets (yt-dlp + curl_cffi)
# ---------------------------------------------------------------------------
# These targets are tried in order. The first one that curl_cffi knows about
# wins. Order matters: chrome-120 is the most widely compiled-in target.
_FACEBOOK_IMPERSONATE_TARGETS: list[str] = [
    "chrome-120:windows-10",
    "chrome-131:windows-10",
    "edge-120:windows-10",
    "chrome-120:macos-14",
    "chrome-131:macos-14",
]

_INSTAGRAM_IMPERSONATE_TARGETS: list[str] = [
    "chrome-120:windows-10",
    "chrome-131:windows-10",
    "edge-120:windows-10",
    "chrome-120:macos-14",
    "chrome-131:macos-14",
]

# User-Agents that match the impersonation targets above (Tahoe API 2025).
_FACEBOOK_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_INSTAGRAM_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Last-resort browser fingerprint for older curl_cffi builds that only ship a
# generic "chrome" target.
_GENERIC_CHROME_FALLBACK = "chrome"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_supported_impersonate_map() -> dict[str, Any]:
    """Return the map of impersonation targets known to the installed yt-dlp.

    Returns an empty dict if yt-dlp is too old, curl_cffi is not installed,
    or anything else goes wrong. Callers should treat an empty dict as
    "impersonation unavailable" and log accordingly.
    """
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget

        return getattr(ImpersonateTarget, "_SUPPORTED_IMPERSONATE_TARGET_MAP", {})
    except Exception:
        return {}


def _build_impersonate_target(target_list: list[str]) -> Optional[str]:
    """Return the first available impersonate target from ``target_list``.

    Falls back to ``"chrome"`` (a generic target that older curl_cffi builds
    still ship) when nothing in the explicit list is available, and finally
    returns ``None`` when even that fails — in which case the caller should
    warn the user to install/update curl_cffi.
    """
    supported = _get_supported_impersonate_map()
    if not supported:
        return None
    for target in target_list:
        if target in supported:
            return target
    if _GENERIC_CHROME_FALLBACK in supported:
        return _GENERIC_CHROME_FALLBACK
    return None


def _curl_cffi_compatible() -> bool:
    """Return True if the installed curl_cffi version is known to work with yt-dlp.

    yt-dlp supports curl_cffi 0.5.10 and 0.10.x through 0.15.x. Anything else
    may load the module but silently break impersonation at runtime. We do
    not refuse to run in that case — we just log a warning — so users with
    unusual Python environments aren't blocked.
    """
    try:
        import curl_cffi
    except Exception:
        return False
    try:
        import yt_dlp  # noqa: F401  (presence confirms compatibility can be checked)
    except Exception:
        return False

    version_str = getattr(curl_cffi, "__version__", "0.0.0")
    try:
        parts = [int(x) for x in str(version_str).split(".")[:2] if x.isdigit()]
        version = tuple(parts)
    except (ValueError, AttributeError):
        version = (0, 0)

    supported = (version == (0, 5)) or ((0, 10) <= version < (0, 16))
    if not supported:
        logger.warning(
            "curl_cffi %s may be incompatible with yt-dlp. "
            "Supported: 0.5.10, 0.10.x-0.15.x. "
            "Fix: pip install 'yt-dlp[default,curl_cffi]'",
            version_str,
        )
    return supported


def _get_cookies_file(platform: str) -> Optional[str]:
    """Resolve the cookie file path for ``platform`` from the main downloader.

    We delegate to ``downloader.get_cookies_file`` instead of duplicating
    path resolution — if cookies storage changes in the future, this stays
    in sync automatically.
    """
    try:
        from app.core.downloader import get_cookies_file

        return get_cookies_file(platform)
    except Exception as exc:
        logger.debug("Could not resolve cookies file for %s: %s", platform, exc)
        return None


def _warn_missing_cookies(platform: str) -> None:
    """Print a single, well-formatted warning when cookies are missing."""
    domain = {"facebook": "facebook.com", "instagram": "instagram.com"}.get(
        platform, platform
    )
    logger.warning(
        "============================================================\n"
        "%s DOWNLOAD MAY REQUIRE COOKIES!\n"
        "Please add %s cookies in Settings -> Cookies Management.\n"
        "1. Install 'Get cookies.txt LOCALLY' browser extension\n"
        "2. Login to %s in your browser\n"
        "3. Export cookies.txt from the extension\n"
        "4. Paste into Settings -> Cookies Management\n"
        "============================================================",
        platform.upper(),
        platform,
        domain,
    )


def _warn_no_impersonation(platform: str) -> None:
    """Print a single warning that impersonation is unavailable."""
    logger.warning(
        "============================================================\n"
        "%s DOWNLOAD WILL LIKELY FAIL: curl_cffi impersonation is not "
        "available. Install or upgrade it with: "
        "pip install -U 'yt-dlp[default,curl_cffi]'\n"
        "============================================================",
        platform.upper(),
    )


# ---------------------------------------------------------------------------
# HTTP headers
# ---------------------------------------------------------------------------
def _facebook_http_headers() -> dict[str, str]:
    """Headers required by Facebook's Tahoe API (2025).

    Sec-Fetch-* and Sec-Ch-Ua-* are matched against the impersonation
    target; changing them while keeping the impersonation target is fine,
    but changing only the headers (or only the target) will leak.
    """
    return {
        "User-Agent": _FACEBOOK_USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": "https://www.facebook.com/",
        "Origin": "https://www.facebook.com",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    }


def _instagram_http_headers() -> dict[str, str]:
    """Headers required by Instagram's API."""
    return {
        "User-Agent": _INSTAGRAM_USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": "https://www.instagram.com/",
        "Origin": "https://www.instagram.com",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    }


# ---------------------------------------------------------------------------
# yt-dlp option builders
# ---------------------------------------------------------------------------
def _base_ydl_options(output_dir: str, video_id: str) -> dict[str, Any]:
    """Shared yt-dlp options that do not depend on the platform."""
    output_path = os.path.join(output_dir, f"{video_id}.%(ext)s")
    return {
        "outtmpl": output_path,
        # Single-file mp4 first; merge fallback is handled by yt-dlp itself.
        "format": "best[ext=mp4]/best",
        "quiet": False,
        "no_warnings": False,
        "extract_flat": False,
        "writethumbnail": True,
        "ignoreerrors": False,
        "postprocessors": [
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
        ],
        "geo_bypass": True,
        "retries": 5,
        "fragment_retries": 5,
        "skip_unavailable_fragments": True,
        "socket_timeout": 30,
        "downloader": "native",
    }


def build_facebook_ydl_options(
    url: str, video_id: str, output_dir: str, cookies_file: Optional[str]
) -> dict[str, Any]:
    """Build yt-dlp options for a Facebook URL.

    Always injects cookies and impersonation. If either is unavailable
    the function still returns a valid options dict, but the caller should
    expect a downstream error — we log a warning so the failure mode is
    obvious in the user's log.
    """
    del url  # URL is not needed to build the options dict itself
    opts = _base_ydl_options(output_dir, video_id)
    opts["http_headers"] = _facebook_http_headers()
    opts["geo_bypass_country"] = "US"
    opts["cookies_required"] = True

    if cookies_file:
        opts["cookiefile"] = cookies_file
        try:
            size = os.path.getsize(cookies_file)
            logger.info(
                "Using Facebook cookies: %s (size: %d bytes)", cookies_file, size
            )
        except OSError:
            logger.info("Using Facebook cookies: %s", cookies_file)
    else:
        _warn_missing_cookies("facebook")

    if not _curl_cffi_compatible():
        _warn_no_impersonation("facebook")

    target = _build_impersonate_target(_FACEBOOK_IMPERSONATE_TARGETS)
    if target:
        opts["impersonate"] = target
        logger.info("Impersonating Facebook as %s", target)
    else:
        _warn_no_impersonation("facebook")

    return opts


def build_instagram_ydl_options(
    url: str, video_id: str, output_dir: str, cookies_file: Optional[str]
) -> dict[str, Any]:
    """Build yt-dlp options for an Instagram URL.

    Same contract as :func:`build_facebook_ydl_options` — always returns a
    usable options dict, logs warnings when prerequisites are missing.
    """
    del url
    opts = _base_ydl_options(output_dir, video_id)
    opts["http_headers"] = _instagram_http_headers()
    opts["geo_bypass_country"] = "US"
    opts["cookies_required"] = True

    if cookies_file:
        opts["cookiefile"] = cookies_file
        try:
            size = os.path.getsize(cookies_file)
            logger.info(
                "Using Instagram cookies: %s (size: %d bytes)", cookies_file, size
            )
        except OSError:
            logger.info("Using Instagram cookies: %s", cookies_file)
    else:
        _warn_missing_cookies("instagram")

    if not _curl_cffi_compatible():
        _warn_no_impersonation("instagram")

    target = _build_impersonate_target(_INSTAGRAM_IMPERSONATE_TARGETS)
    if target:
        opts["impersonate"] = target
        logger.info("Impersonating Instagram as %s", target)
    else:
        _warn_no_impersonation("instagram")

    return opts


# ---------------------------------------------------------------------------
# Progress hook
# ---------------------------------------------------------------------------
def _make_progress_hook(progress_cb: Callable[[float], None]):
    """Build a yt-dlp ``progress_hooks`` callback that maps to a 0-100 float."""

    def _hook(d: dict[str, Any]) -> None:
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            if total:
                try:
                    progress_cb(downloaded / total * 100)
                except Exception:
                    # Progress callbacks should never break the download.
                    logger.debug("progress_cb raised, ignoring", exc_info=True)
        elif status == "finished":
            try:
                progress_cb(100)
            except Exception:
                logger.debug("progress_cb raised on finished, ignoring", exc_info=True)

    return _hook


# ---------------------------------------------------------------------------
# Async downloaders (the public entry points)
# ---------------------------------------------------------------------------
async def download_facebook(
    url: str,
    output_dir: str,
    video_id: str,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> dict[str, Any]:
    """Download a Facebook video into ``output_dir``.

    Returns a dict with the keys expected by the rest of the pipeline:
    ``title``, ``duration``, ``video_path``, ``thumbnail_path``. Raises
    :class:`SocialDownloaderError` on configuration or download failure
    so the caller can fall back to :func:`app.core.downloader.download_with_ytdlp`.
    """
    import yt_dlp

    cookies_file = _get_cookies_file("facebook")
    opts = build_facebook_ydl_options(url, video_id, output_dir, cookies_file)

    if progress_cb:
        opts["progress_hooks"] = [_make_progress_hook(progress_cb)]

    logger.info("Starting Facebook download: %s", url)

    try:
        # yt-dlp's YoutubeDL blocks; run it in a worker thread to keep the
        # event loop responsive to cancel requests.
        loop_holder: dict[str, Any] = {}

        def _run() -> None:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    loop_holder["info"] = ydl.extract_info(url, download=True)
            except Exception as exc:  # noqa: BLE001
                loop_holder["error"] = exc

        import asyncio

        await asyncio.get_event_loop().run_in_executor(None, _run)
        if loop_holder.get("error"):
            raise SocialDownloaderError(
                f"Facebook yt-dlp run failed: {loop_holder['error']}"
            ) from loop_holder["error"]
        info = loop_holder.get("info") or {}
    except SocialDownloaderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SocialDownloaderError(f"Facebook download failed: {exc}") from exc

    output_path = os.path.join(output_dir, f"{video_id}.mp4")
    thumbnail_path = os.path.join(output_dir, f"{video_id}.jpg")

    return {
        "title": info.get("title") or "Unknown",
        "duration": info.get("duration") or 0,
        "video_path": output_path if os.path.exists(output_path) else None,
        "thumbnail_path": thumbnail_path if os.path.exists(thumbnail_path) else None,
    }


async def download_instagram(
    url: str,
    output_dir: str,
    video_id: str,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> dict[str, Any]:
    """Download an Instagram video into ``output_dir``.

    Same contract as :func:`download_facebook`.
    """
    import asyncio
    import yt_dlp

    cookies_file = _get_cookies_file("instagram")
    opts = build_instagram_ydl_options(url, video_id, output_dir, cookies_file)

    if progress_cb:
        opts["progress_hooks"] = [_make_progress_hook(progress_cb)]

    logger.info("Starting Instagram download: %s", url)

    try:
        loop_holder: dict[str, Any] = {}

        def _run() -> None:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    loop_holder["info"] = ydl.extract_info(url, download=True)
            except Exception as exc:  # noqa: BLE001
                loop_holder["error"] = exc

        await asyncio.get_event_loop().run_in_executor(None, _run)
        if loop_holder.get("error"):
            raise SocialDownloaderError(
                f"Instagram yt-dlp run failed: {loop_holder['error']}"
            ) from loop_holder["error"]
        info = loop_holder.get("info") or {}
    except SocialDownloaderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SocialDownloaderError(f"Instagram download failed: {exc}") from exc

    output_path = os.path.join(output_dir, f"{video_id}.mp4")
    thumbnail_path = os.path.join(output_dir, f"{video_id}.jpg")

    return {
        "title": info.get("title") or "Unknown",
        "duration": info.get("duration") or 0,
        "video_path": output_path if os.path.exists(output_path) else None,
        "thumbnail_path": thumbnail_path if os.path.exists(thumbnail_path) else None,
    }
