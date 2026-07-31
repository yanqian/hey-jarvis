#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

python3 scripts/check_isolation.py
node --check src/main.js

if [ ! -x .venv/bin/python ]; then
  echo "Run npm run setup before the complete offline check." >&2
  exit 1
fi

.venv/bin/python -m unittest discover -s sidecar/tests -p 'test_*.py'
./scripts/build-sidecar.sh
cargo test --manifest-path src-tauri/Cargo.toml

echo "F086 offline checks passed"
