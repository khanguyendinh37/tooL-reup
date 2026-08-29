#!/usr/bin/env bash
# VideoDub macOS Desktop Build
# Run from videodub/ directory: ./desktop/build_macos.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP_DIR="$ROOT/desktop"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
FFMPEG_DIR="$DESKTOP_DIR/vendor/ffmpeg"

echo "========================================"
echo "  VideoDub - Desktop Build (macOS)"
echo "========================================"
echo ""

# 1. Python
echo "[1/6] Checking Python..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 not found. Install Xcode Command Line Tools or Homebrew Python."
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "       Python $PYTHON_VERSION found."

# 2. Node.js
echo "[2/6] Checking Node.js..."
if ! command -v node >/dev/null 2>&1; then
    echo "       Installing Node.js via Homebrew..."
    if ! command -v brew >/dev/null 2>&1; then
        echo "[ERROR] Homebrew not found. Install from https://brew.sh first."
        exit 1
    fi
    brew install node
fi
echo "       Node.js $(node -v) found."

# 3. Virtualenv
echo "[3/6] Setting up Python virtualenv..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$DESKTOP_DIR/requirements.txt"

# 4. FFmpeg
echo "[4/6] Preparing FFmpeg..."
mkdir -p "$FFMPEG_DIR"
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "       Installing FFmpeg via Homebrew..."
    brew install ffmpeg
fi
# Copy ffmpeg and ffprobe to vendor directory (no .exe on macOS)
cp "$(which ffmpeg)" "$FFMPEG_DIR/ffmpeg"
cp "$(which ffprobe)" "$FFMPEG_DIR/ffprobe"
chmod +x "$FFMPEG_DIR/ffmpeg" "$FFMPEG_DIR/ffprobe"
echo "       FFmpeg copied to $FFMPEG_DIR"

# 5. Frontend build
echo "[5/6] Building frontend..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    npm ci
fi
npm run build
cd "$ROOT"

# 6. Icon
echo "[6/6] Generating icons..."
"$VENV_DIR/bin/python" "$DESKTOP_DIR/create_icon.py"

# 7. PyInstaller build
echo "[7/7] Building macOS app (onedir)..."
cd "$DESKTOP_DIR"
"$VENV_DIR/bin/pyinstaller" --noconfirm --clean VideoDub_macos.spec

echo ""
echo "========================================"
echo "  macOS Desktop build completed!"
echo "========================================"
echo ""
echo "App bundle:"
echo "  $DESKTOP_DIR/dist/VideoDub.app"
echo ""
echo "Run:"
echo "  open $DESKTOP_DIR/dist/VideoDub.app"
echo "  # or: ./desktop/run_macos.sh"