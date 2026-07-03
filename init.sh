#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Harness verification =="
"$ROOT_DIR/.agent-harness/scripts/init.sh" "$@"

cd "$ROOT_DIR"

echo "== Project required files =="
for path in \
  README.md \
  .env.example \
  requirements.txt \
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
  tests/test_audio_input.py \
  tests/test_config.py \
  tests/test_openai_client.py \
  tests/test_player.py \
  tests/test_recorder.py \
  tests/test_silence.py \
  tests/test_skeleton.py \
  tests/test_state_machine.py \
  tests/test_wake_word.py \
  tmp/.gitkeep
do
  test -f "$path"
done

echo "== Project Python compile =="
python3 -m compileall -q src tests

echo "== Project tests =="
python3 -m unittest discover -s tests -p 'test_*.py'

echo "== Project dry-run smoke =="
python3 -m src.main --dry-run

echo "== Project fake-backend smoke =="
python3 -m src.main --fake-backend

echo "project recovery verification passed"
