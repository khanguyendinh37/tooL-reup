"""Standalone Facebook downloader test.

This script runs a Facebook download outside the FastAPI app so you can see
which strategies work on your machine. Run it from the ``backend/`` folder
after activating the venv:

    .venv/Scripts/python.exe -m scripts.test_facebook_download <URL> [cookies_file]

It tries the following strategies in order, prints the result of each, and
stops at the first one that returns a non-empty file:

1. yt-dlp with curl_cffi impersonation + cookies (the path the app uses)
2. yt-dlp with only cookies (no impersonation)
3. yt-dlp with no cookies and no impersonation (works for some public Reels)
4. yt-dlp using the m.facebook.com web client (sometimes succeeds when the
   desktop client is fingerprinted)
5. yt-dlp with ``tv`` extractor (web client bypass)

The output is intentionally verbose: the goal is to find out which strategy
works on the user's network and machine, not to be a quiet, production
downloader.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path


async def try_strategy(label, opts, url, output_dir, video_id):
    """Run a single yt-dlp attempt and return the result."""
    import yt_dlp

    print(f"\n{'=' * 60}\n[{label}]\n{'=' * 60}")
    print(f"opts: {json.dumps({k: v for k, v in opts.items() if k != 'http_headers'}, default=str)}")
    try:
        loop = asyncio.get_event_loop()

        def _run():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=True)

        info = await loop.run_in_executor(None, _run)
        if info:
            print(f"[{label}] SUCCESS — title: {info.get('title')!r}")
            # Find downloaded file
            for f in os.listdir(output_dir):
                if f.startswith(video_id) and f.endswith(('.mp4', '.webm', '.mkv')):
                    full = os.path.join(output_dir, f)
                    size = os.path.getsize(full)
                    print(f"[{label}] file: {full} ({size} bytes)")
                    if size > 1024:
                        return full
        return None
    except Exception as exc:
        print(f"[{label}] FAILED: {exc}")
        return None


def common_opts(output_dir, video_id):
    output_path = os.path.join(output_dir, f"{video_id}.%(ext)s")
    return {
        "outtmpl": output_path,
        "format": "best[ext=mp4]/best",
        "quiet": False,
        "no_warnings": False,
        "writethumbnail": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
    }


async def main():
    if len(sys.argv) < 2:
        print("usage: test_facebook_download <URL> [cookies_file]")
        sys.exit(1)
    url = sys.argv[1]
    cookies_file = sys.argv[2] if len(sys.argv) > 2 else None
    output_dir = tempfile.mkdtemp(prefix="fbtest_")
    video_id = "test"
    print(f"Output dir: {output_dir}")
    print(f"URL: {url}")
    print(f"Cookies: {cookies_file or '(none)'}")

    # Resolve impersonation target
    target = None
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget
        supported = getattr(ImpersonateTarget, '_SUPPORTED_IMPERSONATE_TARGET_MAP', {})
        for t in (
            "chrome-120:windows-10",
            "chrome-131:windows-10",
            "edge-120:windows-10",
            "chrome",
        ):
            if t in supported:
                target = t
                break
    except Exception as exc:
        print(f"Impersonation module not available: {exc}")
    print(f"Impersonation target: {target or '(unavailable)'}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        "Referer": "https://www.facebook.com/",
    }

    strategies = []

    # 1. impersonate + cookies
    if target and cookies_file:
        opts = common_opts(output_dir, video_id)
        opts["http_headers"] = headers
        opts["impersonate"] = target
        opts["cookiefile"] = cookies_file
        strategies.append(("1-impersonate+cookies", opts))

    # 2. cookies only
    if cookies_file:
        opts = common_opts(output_dir, video_id)
        opts["http_headers"] = headers
        opts["cookiefile"] = cookies_file
        strategies.append(("2-cookies-only", opts))

    # 3. impersonate only (no cookies)
    if target:
        opts = common_opts(output_dir, video_id)
        opts["http_headers"] = headers
        opts["impersonate"] = target
        strategies.append(("3-impersonate-only", opts))

    # 4. no auth — public Reels sometimes work
    opts = common_opts(output_dir, video_id)
    opts["http_headers"] = headers
    strategies.append(("4-no-auth", opts))

    # 5. m.facebook.com web client
    opts = common_opts(output_dir, video_id)
    opts["http_headers"] = headers
    if cookies_file:
        opts["cookiefile"] = cookies_file
    opts["extractor_args"] = {"generic": {"force_generic_extractor": False}}
    strategies.append(("5-web-client", opts))

    for label, opts in strategies:
        result = await try_strategy(label, opts, url, output_dir, video_id)
        if result:
            print(f"\n>>> Strategy '{label}' worked: {result}")
            return 0

    print("\n>>> All strategies failed.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
