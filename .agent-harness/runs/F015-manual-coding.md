# Run Record: F015 - Switch Alexa openWakeWord runtime to TFLite

## Summary

- Date: 2026-07-04
- Agent role: Manual Coding Agent fallback
- Feature: F015 - Switch Alexa openWakeWord runtime to TFLite
- Result: Implementation completed by manual fallback; awaiting Evaluator Agent review.

## Repository State

- Starting commit: `ed8404e F012-F014 Restore Alexa wake runtime`
- Ending commit: not committed
- Working tree status: pre-existing uncommitted harness planning edits, local debug artifacts, `.DS_Store`, and audio files were present before implementation and preserved.

## Commands Run

```bash
git log --oneline -20
./init.sh
.venv/bin/python - <<'PY'
import importlib.util
for name in ['openwakeword','tflite_runtime','tensorflow','onnxruntime']:
    spec=importlib.util.find_spec(name)
    print(f'{name}: {spec.origin if spec else None}')
PY
.venv/bin/python - <<'PY'
import importlib.metadata as md
for dist in ['openwakeword','tflite-runtime','tensorflow','onnxruntime']:
    try:
        meta=md.metadata(dist)
        print(f'## {dist} {md.version(dist)}')
        print('Requires-Dist:', meta.get_all('Requires-Dist'))
    except md.PackageNotFoundError:
        print(f'## {dist} not installed')
PY
rg -n "tflite|litert|Interpreter|inference_framework|onnx" .venv/lib/python3.12/site-packages/openwakeword -S
sed -n '1,260p' .venv/lib/python3.12/site-packages/openwakeword/model.py
test -d /Users/armstrong/Project/openWakeWord && rg -n "ai-edge|tflite_runtime|tflite-runtime|litert" /Users/armstrong/Project/openWakeWord -S || true
test -x /Users/armstrong/Project/openWakeWord/.venv/bin/python && /Users/armstrong/Project/openWakeWord/.venv/bin/python - <<'PY'
import importlib.util
for name in ['tflite_runtime','tflite_runtime.interpreter','ai_edge_litert','ai_edge_litert.interpreter']:
    try:
        spec=importlib.util.find_spec(name)
    except Exception as exc:
        print(f'{name}: ERROR {type(exc).__name__}: {exc}')
    else:
        print(f'{name}: {spec.origin if spec else None}')
import importlib.metadata as md
for dist in ['ai-edge-litert','tflite-runtime','openwakeword']:
    try:
        print(f'{dist}: {md.version(dist)}')
        print(md.files(dist)[:5] if md.files(dist) else [])
    except Exception as exc:
        print(f'{dist}: {type(exc).__name__}: {exc}')
PY
python3 -m unittest tests.test_config tests.test_wake_word tests.test_main tests.test_documentation tests.test_state_machine tests.test_openai_client
python3 -m unittest discover -s tests -p 'test_*.py'
.agent-harness/scripts/validate-feature.sh F015
./init.sh
```

## Evidence

- Tests: focused F015-adjacent unittest command passed 42 tests covering configuration defaults and validation, macOS ARM64 ONNX guard, detector loader arguments, TFLite and explicit ONNX preparation paths, debug metadata and per-key maximum scores, documentation sync, and dependent settings fixtures without real microphone access or live model downloads.
- Tests: full project test discovery passed 59 tests, including a fake-model fixture for `scripts/debug_oww_file.py` metadata and per-key max-score output.
- Feature validation: `.agent-harness/scripts/validate-feature.sh F015` passed while correctly leaving F015 `in_progress` and `passes=false` pending evaluator review.
- Recovery: final `./init.sh` passed harness verification, project compile, full project tests, dry-run smoke, and fake-backend smoke.
- External behavior verification: installed openWakeWord 0.6.0 source in the project `.venv` imports `tflite_runtime.interpreter` for TFLite and falls back to ONNX when TFLite runtime is missing; the adjacent upstream checkout imports `ai_edge_litert.interpreter` and declares `ai-edge-litert>=2.0.2,<3` for Darwin/Linux. The implementation adds a compatibility alias so `ai-edge-litert` can satisfy the PyPI openWakeWord TFLite import shape.
- External behavior verification: existing `debug/openwakeword-alexa-debug.md` records local macOS ARM64 evidence where ONNX produced near-zero Alexa scores while TFLite produced usable scores on live microphone and official positive-sample checks.
- Capability handling: the TFLite runtime capability is now durable through `requirements.txt`, diagnostics, README setup/troubleshooting, and tests. ONNX remains an explicit non-default path and fails fast on macOS ARM64.

## Failure Analysis

- Failure domain: none
- Failure summary: No implementation failure or blocked capability was encountered during this manual coding pass.
- Harness improvement: Not required; this was product/runtime implementation work with the missing TFLite runtime capability made durable in project requirements, diagnostics, documentation, and tests.
- Follow-up feature: None

## Files Changed

- `.agent-harness/progress.md`
- `.agent-harness/runs/F015-manual-coding.md`
- `.env.example`
- `README.md`
- `requirements.txt`
- `scripts/debug_oww_file.py`
- `src/config.py`
- `src/main.py`
- `src/wake_word.py`
- `tests/test_config.py`
- `tests/test_debug_oww_file.py`
- `tests/test_documentation.py`
- `tests/test_main.py`
- `tests/test_openai_client.py`
- `tests/test_state_machine.py`
- `tests/test_wake_word.py`

## Evaluator Result

Awaiting Evaluator Agent review. Do not mark F015 done until a durable evaluator run records the exact `EVAL_PASS: F015` line.

## Follow-Up

- Run Evaluator Agent for F015.
