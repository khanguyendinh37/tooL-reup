# PyInstaller onedir specification for the VideoDub desktop app on macOS.
# Run with: pyinstaller --noconfirm --clean VideoDub_macos.spec
from pathlib import Path

from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ
from PyInstaller.building.osx import BUNDLE
from PyInstaller.utils.hooks import collect_all, copy_metadata


ROOT = Path(SPEC).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
FFMPEG_DIR = ROOT / "desktop" / "vendor" / "ffmpeg"


datas = [
    (str(FRONTEND_DIST), "frontend_dist"),
]
binaries = []
hiddenimports = []

# These libraries use dynamic imports or package data at runtime.
for package in (
    "webview",
    "yt_dlp",
    "curl_cffi",
    "fastapi",
    "starlette",
    "uvicorn",
    "sqlalchemy",
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

# macOS FFmpeg binaries (no .exe extension)
for executable in ("ffmpeg", "ffprobe"):
    executable_path = FFMPEG_DIR / executable
    if executable_path.is_file():
        binaries.append((str(executable_path), "ffmpeg"))

for distribution in ('yt-dlp', 'curl_cffi', 'pytubefix', 'edge-tts',
                     'faster-whisper', 'ctranslate2', 'av', 'demucs', 'torch', 'numpy', 'fastapi'):
    datas.extend(copy_metadata(distribution))

icon_path = ROOT / "desktop" / "VideoDub.icns"

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
    upx=True,
    console=False,
    icon=str(icon_path) if icon_path.is_file() else None,
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VideoDub",
)

app = BUNDLE(
    coll,
    name="VideoDub.app",
    icon=str(icon_path) if icon_path.is_file() else None,
    bundle_identifier="com.videodub.desktop",
)
