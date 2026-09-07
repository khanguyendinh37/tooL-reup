# PyInstaller onedir specification for the VideoDub desktop app.
from pathlib import Path

from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ
from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPEC).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
FFMPEG_DIR = ROOT / "desktop" / "vendor" / "ffmpeg"


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
    "aiosqlite",
    "faster_whisper",
    "ctranslate2",
    "edge_tts",
    "demucs",
    "torch",
):
    try:
        package_datas, package_binaries, package_hiddenimports = collect_all(package)
    except Exception:
        continue
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

for executable in ("ffmpeg.exe", "ffprobe.exe"):
    executable_path = FFMPEG_DIR / executable
    if executable_path.is_file():
        binaries.append((str(executable_path), "ffmpeg"))

icon_path = ROOT / "desktop" / "VideoDub.ico"

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
