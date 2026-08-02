#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CONFIG="$ROOT/app/src-tauri/tauri.conf.json"
VERSION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$CONFIG")
NAME="Hey-Jarvis-$VERSION-INTERNAL-UNSIGNED-arm64"
OUTPUT_ROOT=${HEY_JARVIS_RELEASE_ROOT:-"$ROOT/build/internal-release"}
OUTPUT_ROOT=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$OUTPUT_ROOT")
case "$OUTPUT_ROOT" in
  "$ROOT"/build/*|/tmp/hey-jarvis-*) ;;
  *)
    echo "error: HEY_JARVIS_RELEASE_ROOT must be inside $ROOT/build or /tmp/hey-jarvis-*" >&2
    exit 2
    ;;
esac

if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo "error: the internal release requires Apple Silicon macOS" >&2
  exit 2
fi
for tool in hdiutil file codesign shasum npm python3; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "error: required tool is unavailable: $tool" >&2
    exit 2
  }
done

WORK="$OUTPUT_ROOT/.work-$$"
MOUNT="$OUTPUT_ROOT/.mount-$$"
DMG="$OUTPUT_ROOT/$NAME.dmg"
MANIFEST="$OUTPUT_ROOT/$NAME.manifest.json"
CHECKSUM="$OUTPUT_ROOT/$NAME.sha256"
NEXT_DMG="$WORK/$NAME.dmg"
NEXT_MANIFEST="$WORK/$NAME.manifest.json"
NEXT_CHECKSUM="$WORK/$NAME.sha256"
ROLLBACK="$OUTPUT_ROOT/rollback"
cleanup() {
  hdiutil detach "$MOUNT" -quiet >/dev/null 2>&1 || true
  rm -rf "$WORK" "$MOUNT"
}
trap cleanup EXIT HUP INT TERM
mkdir -p "$OUTPUT_ROOT" "$WORK/image" "$MOUNT" "$ROLLBACK"

"$ROOT/scripts/build_macos_sidecar.sh"
BUILD_HOME=$(python3 -c 'from pathlib import Path; print(Path.home())')
RUSTFLAGS="${RUSTFLAGS:+$RUSTFLAGS }--remap-path-prefix=$ROOT=/source --remap-path-prefix=$BUILD_HOME=/build-home"
export RUSTFLAGS
(cd "$ROOT/app" && npm ci && npm run tauri -- build --bundles app)

APP="$ROOT/app/src-tauri/target/release/bundle/macos/Hey Jarvis.app"
test -d "$APP" || {
  echo "error: Tauri did not create $APP" >&2
  exit 2
}
cp -R "$APP" "$WORK/image/Hey Jarvis.app"
ln -s /Applications "$WORK/image/Applications"
cp "$ROOT/packaging/internal-macos/INTERNAL-UNSIGNED.txt" "$WORK/image/INTERNAL-UNSIGNED.txt"

hdiutil create -quiet -ov -format UDZO \
  -volname "Hey Jarvis INTERNAL UNSIGNED $VERSION" \
  -srcfolder "$WORK/image" "$NEXT_DMG"
hdiutil attach -quiet -readonly -nobrowse -mountpoint "$MOUNT" "$NEXT_DMG"

python3 "$ROOT/scripts/internal_macos_release.py" write \
  --root "$ROOT" --app "$MOUNT/Hey Jarvis.app" --dmg "$NEXT_DMG" \
  --manifest "$NEXT_MANIFEST" --checksum "$NEXT_CHECKSUM"
python3 "$ROOT/scripts/internal_macos_release.py" verify \
  --root "$ROOT" --app "$MOUNT/Hey Jarvis.app" --dmg "$NEXT_DMG" \
  --manifest "$NEXT_MANIFEST" --checksum "$NEXT_CHECKSUM"
hdiutil detach "$MOUNT" -quiet

# Publish only a fully verified candidate. A previous version is eligible for
# rollback retention only when its complete checksum-bound trio exists.
if [ -f "$DMG" ] && [ -f "$MANIFEST" ] && [ -f "$CHECKSUM" ] && \
   (cd "$OUTPUT_ROOT" && shasum -a 256 -c "$(basename "$CHECKSUM")" >/dev/null 2>&1); then
  prior=$(shasum -a 256 "$DMG" | awk '{print $1}')
  prior_dir="$ROLLBACK/$prior"
  mkdir -p "$prior_dir"
  cp "$DMG" "$prior_dir/$(basename "$DMG")"
  cp "$MANIFEST" "$prior_dir/$(basename "$MANIFEST")"
  cp "$CHECKSUM" "$prior_dir/$(basename "$CHECKSUM")"
fi
mv "$NEXT_DMG" "$DMG"
mv "$NEXT_MANIFEST" "$MANIFEST"
mv "$NEXT_CHECKSUM" "$CHECKSUM"

echo "internal unsigned DMG: $DMG"
echo "manifest: $MANIFEST"
echo "checksum: $CHECKSUM"
echo "warning: internal trusted testing only; not signed/notarized for public distribution"
