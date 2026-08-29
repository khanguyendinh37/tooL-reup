#!/usr/bin/env bash
# Launch the VideoDub macOS .app from the command line.
# Usage: ./desktop/run_macos.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/desktop/dist/VideoDub.app"

if [ ! -d "$APP" ]; then
    echo "[ERROR] $APP not found."
    echo "        Run ./desktop/build_macos.sh first."
    exit 1
fi

open "$APP"
