# PyInstaller onedir specification for the VideoDub macOS .app bundle.
from pathlib import Path

from PyInstaller.building.build_main import Analysis, BUNDLE, COLLECT, EXE, PYZ
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

for package in (
    "webview",
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

# FFmpeg/ffprobe on macOS have no .exe extension
for executable in ("ffmpeg", "ffprobe"):
    executable_path = FFMPEG_DIR / executable
    if executable_path.is_file():
        binaries.append((str(executable_path), "ffmpeg"))

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
    upx=False,
    console=False,
    icon=str(icon_path) if icon_path.is_file() else None,
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

# Build .app bundle structure for macOS
app = BUNDLE(
    coll,
    name="VideoDub.app",
    icon=str(icon_path) if icon_path.is_file() else None,
    bundle_identifier="com.videodub.app",
    info_plist={
        "CFBundleName": "VideoDub",
        "CFBundleDisplayName": "VideoDub",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
    },
)
