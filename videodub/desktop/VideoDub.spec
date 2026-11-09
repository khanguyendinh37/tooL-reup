# PyInstaller onedir specification for the VideoDub desktop app.
import os
import re
from pathlib import Path

from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ
from PyInstaller.utils.hooks import collect_all, copy_metadata


ROOT = Path(SPEC).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
FFMPEG_DIR = ROOT / "desktop" / "vendor" / "ffmpeg"

# Release version, e.g. "1.2.3". CI passes it from the git tag (v1.2.3).
APP_VERSION = (os.environ.get("VIDEODUB_VERSION") or "1.0.0").lstrip("vV")
_numbers = [int(part) for part in re.findall(r"\d+", APP_VERSION)[:4]]
VERSION_TUPLE = tuple((_numbers + [0, 0, 0, 0])[:4])


datas = [
    (str(FRONTEND_DIST), "frontend_dist"),
]
binaries = []
hiddenimports = []

# These libraries use dynamic imports or package data at runtime. Collecting
# them here is more reliable than relying on PyInstaller's static analysis,
# especially for webview, Whisper and Demucs.
for package in (
    "webview",
    "yt_dlp",
    "curl_cffi",
    "fastapi",
    "starlette",
    "uvicorn",
    "sqlalchemy",
    "greenlet",
    "aiosqlite",
    "faster_whisper",
    "ctranslate2",
    "edge_tts",
    "demucs",
    "torch",
):
    try:
        package_datas, package_binaries, package_hiddenimports = collect_all(package)
    except Exception as exc:
        raise RuntimeError(f"Cannot package required dependency {package}") from exc
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

for executable in ("ffmpeg.exe", "ffprobe.exe"):
    executable_path = FFMPEG_DIR / executable
    if executable_path.is_file():
        binaries.append((str(executable_path), "ffmpeg"))

for distribution in ('yt-dlp', 'curl_cffi', 'pytubefix', 'edge-tts',
                     'faster-whisper', 'ctranslate2', 'av', 'demucs', 'torch', 'numpy', 'fastapi'):
    datas.extend(copy_metadata(distribution))

icon_path = ROOT / "desktop" / "VideoDub.ico"

# Windows "Details" tab metadata. Signed installers and SmartScreen reputation
# are tied to consistent product/company names, so keep these stable.
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

_version_text = ".".join(str(part) for part in VERSION_TUPLE)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=VERSION_TUPLE, prodvers=VERSION_TUPLE),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", os.environ.get("VIDEODUB_PUBLISHER", "VideoDub")),
            StringStruct("FileDescription", "VideoDub - AI video dubbing"),
            StringStruct("FileVersion", _version_text),
            StringStruct("InternalName", "VideoDub"),
            StringStruct("OriginalFilename", "VideoDub.exe"),
            StringStruct("ProductName", "VideoDub"),
            StringStruct("ProductVersion", APP_VERSION),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

import sys

sys.path.insert(0, str(ROOT / "desktop"))
from packaging_utils import shorten_metadata_paths  # noqa: E402

datas = shorten_metadata_paths(datas, workpath)

analysis = Analysis(
    [str(ROOT / "desktop" / "desktop_main.py")],
    pathex=[str(BACKEND_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="VideoDub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(icon_path) if icon_path.is_file() else None,
    version=version_info,
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VideoDub",
)
