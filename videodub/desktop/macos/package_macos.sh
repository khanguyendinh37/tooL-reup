#!/usr/bin/env bash
# Sign, package (DMG) and optionally notarize the macOS app bundle.
#
# Usage (from repo root, after desktop/build_macos.sh):
#   ./videodub/desktop/macos/package_macos.sh 1.2.3
#
# Environment (all optional; without them the app is ad-hoc signed, which runs
# on the build machine but shows a Gatekeeper warning on customers' Macs):
#   MACOS_SIGN_IDENTITY   "Developer ID Application: Your Name (TEAMID)"
#   MACOS_KEYCHAIN        keychain that holds the identity (CI imports one)
#   APPLE_ID              Apple ID email used for notarization
#   APPLE_TEAM_ID         10-character Team ID
#   APPLE_APP_PASSWORD    app-specific password from appleid.apple.com
#
# Output: videodub/desktop/dist/VideoDub-<version>-macos-arm64.dmg

set -euo pipefail

VERSION="${1:-1.0.0}"
VERSION="${VERSION#v}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$HERE/../dist"
APP="$DIST/VideoDub.app"
ENTITLEMENTS="$HERE/entitlements.plist"
ARCH="$(uname -m)"
DMG="$DIST/VideoDub-${VERSION}-macos-${ARCH}.dmg"
IDENTITY="${MACOS_SIGN_IDENTITY:--}"

if [ ! -d "$APP" ]; then
    echo "[ERROR] $APP not found. Run desktop/build_macos.sh first." >&2
    exit 1
fi

KEYCHAIN_ARGS=()
if [ -n "${MACOS_KEYCHAIN:-}" ]; then
    KEYCHAIN_ARGS=(--keychain "$MACOS_KEYCHAIN")
fi

sign() {
    if [ "$IDENTITY" = "-" ]; then
        codesign --force --sign - "$@"
    else
        codesign --force --timestamp --options runtime \
            --entitlements "$ENTITLEMENTS" ${KEYCHAIN_ARGS[@]+"${KEYCHAIN_ARGS[@]}"} \
            --sign "$IDENTITY" "$@"
    fi
}

echo "[1/4] Signing nested binaries (identity: ${IDENTITY})..."
# Apple requires every Mach-O inside the bundle to be signed before the
# bundle itself, innermost first. Symlinks are skipped (find -type f).
count=0
while IFS= read -r file; do
    if file -b "$file" | grep -q "Mach-O"; then
        sign "$file"
        count=$((count + 1))
    fi
done < <(find "$APP/Contents" -type f | awk -F/ '{ print NF "\t" $0 }' | sort -rn | cut -f2-)
echo "       Signed $count binaries."

echo "[2/4] Signing app bundle..."
sign "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

echo "[3/4] Building DMG..."
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
ditto "$APP" "$STAGING/VideoDub.app"
ln -s /Applications "$STAGING/Applications"
rm -f "$DMG"
hdiutil create -volname "VideoDub" -srcfolder "$STAGING" -ov -format UDZO "$DMG"
if [ "$IDENTITY" != "-" ]; then
    codesign --force --timestamp ${KEYCHAIN_ARGS[@]+"${KEYCHAIN_ARGS[@]}"} --sign "$IDENTITY" "$DMG"
fi

echo "[4/4] Notarization..."
if [ "$IDENTITY" != "-" ] && [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ] \
        && [ -n "${APPLE_APP_PASSWORD:-}" ]; then
    xcrun notarytool submit "$DMG" \
        --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_PASSWORD" \
        --wait --timeout 2h
    xcrun stapler staple "$DMG"
    xcrun stapler validate "$DMG"
    spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG"
    echo "       Notarized and stapled."
else
    echo "       Skipped (no Developer ID / Apple credentials). Customers will see a"
    echo "       Gatekeeper warning; see videodub/desktop/RELEASE.md."
fi

echo ""
echo "DMG: $DMG"
