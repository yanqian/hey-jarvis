#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "F086 currently requires Apple Silicon macOS." >&2
  exit 1
fi

for command in cargo rustc node npm python3; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required command: $command" >&2
    exit 1
  fi
done

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
npm install
./scripts/build-sidecar.sh

echo "Tauri spike setup complete."
rustc --version
cargo --version
node --version
npm --version
.venv/bin/python --version
