# Run Record: F008 - Fix recoverable wake-word model setup

## Summary

- Date: 2026-07-03
- Agent role: Manual Coding Agent fallback plus Evaluator review
- Feature: F008 - Fix recoverable wake-word model setup
- Result: Implemented and evaluator-approved

## Repository State

- Starting commit: 202ac70
- Ending commit: not committed
- Working tree status: modified project and harness files, with pre-existing F007-related uncommitted changes left intact

## Commands Run

```bash
./init.sh
python3 -m unittest discover tests
python3 -m src.main --dry-run
python3 -m src.main --fake-backend
python3 -m src.main --diagnose
.venv/bin/python -m src.main --diagnose
.venv/bin/python -m src.main --prepare-wake-word
.venv/bin/python -c "from src.wake_word import _load_openwakeword_model; model = _load_openwakeword_model(); print(sorted(model.models.keys()))"
.venv/bin/python -c "from src.wake_word import WakeWordDetector; d=WakeWordDetector(0.8); print(d.detect(b'\x00\x00'*1024))"
```

## Evidence

- Tests: `python3 -m unittest discover tests` passed 40 tests.
- Recovery: `./init.sh` passed harness verification, project compile, 40 project tests, dry-run smoke, and fake-backend smoke.
- Runtime diagnostics: `.venv/bin/python -m src.main --diagnose` reported Python 3.12, dependencies, `onnxruntime`, and wake-word ONNX model files as OK after preparation.
- External behavior verification: openWakeWord 0.6.0 was inspected locally; its `Model` supports `inference_framework="onnx"`, and the actual ONNX model load returned `['hey jarvis']`.
- Capability gaps: the first model preparation attempt failed under sandbox network restrictions, then succeeded with approved network access and downloaded only the ONNX assets needed by this project.

## Failure Analysis

- Failure domain: capability_gap
- Failure summary: The real demo crashed in `WAIT_WAKE` because the project used openWakeWord defaults without declaring or preparing the required wake-word runtime/model capability.
- Harness improvement: No harness-level rule change required; the product capability is now durable through explicit dependencies, CLI preparation, diagnostics, documentation, and tests.
- Follow-up feature: None

## Files Changed

- `.agent-harness/SPEC.md`
- `.agent-harness/feature_list.json`
- `.agent-harness/progress.md`
- `.agent-harness/runs/F008-manual-coding.md`
- `README.md`
- `requirements.txt`
- `src/config.py`
- `src/main.py`
- `src/wake_word.py`
- `tests/test_config.py`
- `tests/test_documentation.py`
- `tests/test_wake_word.py`

## Evaluator Result

```text
EVAL_PASS: F008
```

## Follow-Up

- After pulling this change into a fresh venv, run `python -m src.main --prepare-wake-word` once before the real demo.
