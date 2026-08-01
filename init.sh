#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Harness verification =="
"$ROOT_DIR/.agent-harness/scripts/init.sh" "$@"

cd "$ROOT_DIR"

echo "== Project required files =="
for path in \
  README.md \
  app/package.json \
  app/src/index.html \
  app/src/main.js \
  app/sidecar/fake_sidecar.py \
  app/sidecar/product_sidecar.py \
  app/src-tauri/Cargo.toml \
  app/src-tauri/Info.plist \
  app/src-tauri/src/credentials.rs \
  app/src-tauri/src/lib.rs \
  app/src-tauri/src/onboarding.rs \
  app/src-tauri/src/protocol.rs \
  app/src-tauri/src/supervisor.rs \
  app/src-tauri/tauri.conf.json \
  packaging/macos-sidecar/build-requirements.lock \
  packaging/macos-sidecar/hey_jarvis_sidecar.spec \
  packaging/macos-sidecar/models.lock \
  packaging/macos-sidecar/openwakeword-runtime-init.py \
  packaging/macos-sidecar/requirements.lock \
  .env.example \
  requirements.txt \
  requirements-vad.txt \
  src/__init__.py \
  src/audio_input.py \
  src/config.py \
  src/main.py \
  src/openai_client.py \
  src/player.py \
  src/recorder.py \
  src/silence.py \
  src/state_machine.py \
  src/wake_word.py \
  scripts/build_macos_sidecar.sh \
  scripts/inventory_macos_sidecar.py \
  scripts/normalize_zip.py \
  tests/test_audio_input.py \
  tests/test_config.py \
  tests/test_documentation.py \
  tests/test_mac_app_shell.py \
  tests/test_macos_sidecar_packaging.py \
  tests/test_openai_client.py \
  tests/test_player.py \
  tests/test_recorder.py \
  tests/test_silence.py \
  tests/test_skeleton.py \
  tests/test_state_machine.py \
  tests/test_wake_word.py \
  tmp/.gitkeep \
  var/.gitkeep
do
  test -f "$path"
done

echo "== Project Python compile =="
python3 -m compileall -q src tests

echo "== Project tests =="
python3 -m unittest discover -s tests -p 'test_*.py'

echo "== Mac app frontend and fake sidecar tests =="
node --check app/src/main.js
python3 -m unittest discover -s app/sidecar/tests -p 'test_*.py'

echo "== Mac app Rust tests =="
cargo test --locked --manifest-path app/src-tauri/Cargo.toml

echo "== Project dry-run smoke =="
python3 -m src.main --dry-run

echo "== Project fake-backend smoke =="
python3 -m src.main --fake-backend

echo "== Project Realtime fake smoke =="
python3 -m src.realtime.fake_smoke

echo "project recovery verification passed"
