#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${HEY_JARVIS_BUILD_PYTHON:-"$ROOT/.venv/bin/python"}
BUILD_ROOT=${HEY_JARVIS_BUILD_ROOT:-"$ROOT/build/macos-sidecar"}
BUILD_ROOT=$(
  "$PYTHON" -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$BUILD_ROOT"
)
case "$BUILD_ROOT" in
  "$ROOT"/build/*|/tmp/hey-jarvis-*) ;;
  *)
    echo "error: HEY_JARVIS_BUILD_ROOT must be inside $ROOT/build or /tmp/hey-jarvis-*" >&2
    exit 2
    ;;
esac
ENV_DIR="$BUILD_ROOT/build-env"
DIST_DIR="$BUILD_ROOT/dist"
WORK_DIR="$BUILD_ROOT/work"
SPEC="$ROOT/packaging/macos-sidecar/hey_jarvis_sidecar.spec"

if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo "error: the F090 sidecar build requires Apple Silicon macOS" >&2
  exit 2
fi
if [ ! -x "$PYTHON" ]; then
  echo "error: set HEY_JARVIS_BUILD_PYTHON to a Python 3.12 executable" >&2
  exit 2
fi
if [ "$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != 3.12 ]; then
  echo "error: the F090 sidecar build requires Python 3.12" >&2
  exit 2
fi

mkdir -p "$BUILD_ROOT"
rm -rf "$ENV_DIR" "$DIST_DIR" "$WORK_DIR"
"$PYTHON" -m venv "$ENV_DIR"
"$ENV_DIR/bin/python" -m pip install --disable-pip-version-check --no-deps \
  -r "$ROOT/packaging/macos-sidecar/build-requirements.lock" \
  -r "$ROOT/packaging/macos-sidecar/requirements.lock"

OWW_DIR=$(
  "$ENV_DIR/bin/python" -c 'import site; print(site.getsitepackages()[0] + "/openwakeword")'
)
cp "$ROOT/packaging/macos-sidecar/openwakeword-runtime-init.py" "$OWW_DIR/__init__.py"
MODELS_DIR="$OWW_DIR/resources/models"
mkdir -p "$MODELS_DIR"
while IFS='|' read -r name expected url; do
  case "$name" in
    ''|'#'*) continue ;;
  esac
  target="$MODELS_DIR/$name"
  curl --fail --location --silent --show-error "$url" --output "$target"
  actual=$(shasum -a 256 "$target" | awk '{print $1}')
  if [ "$actual" != "$expected" ]; then
    echo "error: wake model hash mismatch for $name" >&2
    exit 2
  fi
done < "$ROOT/packaging/macos-sidecar/models.lock"

SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-1735689600}
export SOURCE_DATE_EPOCH
"$ENV_DIR/bin/pyinstaller" --noconfirm --clean \
  --distpath "$DIST_DIR" --workpath "$WORK_DIR" "$SPEC"

RUNTIME="$DIST_DIR/hey-jarvis-sidecar"
"$ENV_DIR/bin/python" "$ROOT/scripts/normalize_zip.py" "$RUNTIME/_internal/base_library.zip"
"$ENV_DIR/bin/python" "$ROOT/scripts/inventory_macos_sidecar.py" \
  --runtime "$RUNTIME" --build-env "$ENV_DIR" --output "$BUILD_ROOT/manifests"

rm -rf "$BUILD_ROOT/hey-jarvis-sidecar"
mv "$RUNTIME" "$BUILD_ROOT/hey-jarvis-sidecar"
echo "sidecar runtime: $BUILD_ROOT/hey-jarvis-sidecar"
echo "manifests: $BUILD_ROOT/manifests"
