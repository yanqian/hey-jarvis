#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ICON_DIR="$ROOT_DIR/app/src-tauri/icons"
MASTER="$ICON_DIR/icon.svg"
TRAY_MASTER="$ICON_DIR/tray-template.svg"
ICONSET="$ICON_DIR/AppIcon.iconset"
TAURI_ICON="$ROOT_DIR/app/node_modules/.bin/tauri"

test -x "$TAURI_ICON" || {
  echo "Run 'npm install' in app/ before generating icons." >&2
  exit 1
}

mkdir -p "$ICONSET"
TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/hey-jarvis-icons.XXXXXX")
trap 'rm -rf "$TEMP_DIR"' EXIT HUP INT TERM

DEFAULT_DIR="$TEMP_DIR/default"
SIZES_DIR="$TEMP_DIR/sizes"
mkdir -p "$DEFAULT_DIR" "$SIZES_DIR"
"$TAURI_ICON" icon "$MASTER" -o "$DEFAULT_DIR" >/dev/null
"$TAURI_ICON" icon "$MASTER" -o "$SIZES_DIR" \
  --png 16 --png 32 --png 64 --png 128 --png 256 --png 512 --png 1024 >/dev/null

cp "$SIZES_DIR/16x16.png" "$ICONSET/icon_16x16.png"
cp "$SIZES_DIR/32x32.png" "$ICONSET/icon_16x16@2x.png"
cp "$SIZES_DIR/32x32.png" "$ICONSET/icon_32x32.png"
cp "$SIZES_DIR/64x64.png" "$ICONSET/icon_32x32@2x.png"
cp "$SIZES_DIR/128x128.png" "$ICONSET/icon_128x128.png"
cp "$SIZES_DIR/256x256.png" "$ICONSET/icon_128x128@2x.png"
cp "$SIZES_DIR/256x256.png" "$ICONSET/icon_256x256.png"
cp "$SIZES_DIR/512x512.png" "$ICONSET/icon_256x256@2x.png"
cp "$SIZES_DIR/512x512.png" "$ICONSET/icon_512x512.png"
cp "$SIZES_DIR/1024x1024.png" "$ICONSET/icon_512x512@2x.png"

cp "$DEFAULT_DIR/32x32.png" "$ICON_DIR/32x32.png"
cp "$DEFAULT_DIR/128x128.png" "$ICON_DIR/128x128.png"
cp "$DEFAULT_DIR/128x128@2x.png" "$ICON_DIR/128x128@2x.png"
cp "$DEFAULT_DIR/icon.png" "$ICON_DIR/icon.png"
cp "$DEFAULT_DIR/icon.icns" "$ICON_DIR/icon.icns"

# Cocoa displays status-item images at 18 logical points. The 36-pixel source
# provides a 2x backing image; the 18-pixel sibling is retained for inspection.
mkdir -p "$TEMP_DIR/tray"
"$TAURI_ICON" icon "$TRAY_MASTER" -o "$TEMP_DIR/tray" --png 18 --png 36 >/dev/null
cp "$TEMP_DIR/tray/18x18.png" "$ICON_DIR/trayTemplate.png"
cp "$TEMP_DIR/tray/36x36.png" "$ICON_DIR/trayTemplate@2x.png"

echo "Generated macOS app and menu-bar icons in $ICON_DIR"
