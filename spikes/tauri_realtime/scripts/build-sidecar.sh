#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

if [ ! -x .venv/bin/pyinstaller ]; then
  echo "Run npm run setup before building the Python sidecar." >&2
  exit 1
fi

mkdir -p src-tauri/binaries src-tauri/resources .build/pyinstaller .build/spec
export PYINSTALLER_CONFIG_DIR="$ROOT/.build/pyinstaller-config"
.venv/bin/pyinstaller \
  --clean \
  --noconfirm \
  --onedir \
  --collect-all sounddevice \
  --name tauri-realtime-probe-runtime \
  --distpath src-tauri/resources \
  --workpath .build/pyinstaller \
  --specpath .build/spec \
  sidecar/probe_service.py

test -x src-tauri/binaries/tauri-realtime-probe-aarch64-apple-darwin
test -x src-tauri/resources/tauri-realtime-probe-runtime/tauri-realtime-probe-runtime
echo "Built isolated Python sidecar runtime for aarch64-apple-darwin."
