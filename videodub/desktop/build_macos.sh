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

# 1. Python — pin to 3.11 because pydantic-core (PyO3) and av fail to
#    build against Python 3.14+ on recent GitHub Actions runners.
echo "[1/6] Checking Python..."
PYTHON_BIN=""
for candidate in python3.11 python3.12 python3.13 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        CAND_VERSION=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if [ "$CAND_VERSION" = "3.11" ] || [ "$CAND_VERSION" = "3.12" ] || [ "$CAND_VERSION" = "3.13" ]; then
            PYTHON_BIN="$candidate"
            PYTHON_VERSION="$CAND_VERSION"
            break
        fi
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] No compatible Python (3.11-3.13) found."
    echo "        Install: brew install python@3.11"
    exit 1
fi
echo "       Python $PYTHON_VERSION found at $(command -v "$PYTHON_BIN")"

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
    "$PYTHON_BIN" -m venv "$VENV_DIR"
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