# Run Record: F014 - Restore Alexa wake-word runtime

## Summary

- Date: 2026-07-04
- Agent role: Manual Coding Agent fallback
- Feature: F014 - Restore Alexa wake-word runtime
- Result: Implementation completed by manual fallback; awaiting Evaluator Agent review.

## Repository State

- Starting commit: `414fa12 F010-F011 Add wake debug probes`
- Ending commit: not committed
- Working tree status: modified project and harness files, with pre-existing uncommitted F012/F013 state and local audio artifacts preserved.

## Commands Run

```bash
git log --oneline -20
./init.sh
.venv/bin/python - <<'PY'
import openwakeword
print(sorted(openwakeword.MODELS.keys()))
print(openwakeword.MODELS.get("alexa"))
print(openwakeword.FEATURE_MODELS)
PY
python3 -m compileall -q src tests
python3 -m unittest tests.test_wake_word tests.test_config tests.test_main tests.test_audio_input tests.test_documentation tests.test_openai_client tests.test_state_machine
python3 -m unittest discover -s tests -p 'test_*.py'
.agent-harness/scripts/validate-feature.sh F014
./init.sh
```

## Evidence

- Tests: focused F014-adjacent unittest command passed 40 tests covering Alexa loader arguments, score-key extraction, ONNX preparation paths, diagnostics, documentation, 1280-frame microphone and replay sizing, wake-debug output, and dependent settings fixtures without real microphone access or live model download.
- Tests: full project unittest discovery passed 53 tests.
- Feature validation: `.agent-harness/scripts/validate-feature.sh F014` passed while correctly leaving F014 `in_progress` and `passes=false` pending evaluator review.
- Recovery: pre-change and final `./init.sh` passed harness verification, project compile, full project tests, dry-run smoke, and fake-backend smoke. The final fake-backend smoke logged `State WAIT_WAKE: listening for the alexa wake word`.
- External behavior verification: local installed `openwakeword` metadata includes the built-in `alexa` key, `alexa_v0.1.tflite` metadata, and feature model metadata. Project code converts those metadata paths and URLs to ONNX assets for preparation and diagnostics.
- Capability gaps: `PICOVOICE_ACCESS_KEY` was required by the F013 Porcupine active path and the user cannot currently obtain one. F014 removes that credential requirement from the active MVP path by restoring durable openWakeWord/ONNX requirements, `--prepare-wake-word`, diagnostics, README setup/troubleshooting, and regression tests. The restored path still requires network access only when the user explicitly prepares openWakeWord model assets.

## Failure Analysis

- Failure domain: none
- Failure summary: No implementation failure or blocked capability was encountered during this manual coding pass.
- Harness improvement: Not required; this was a product runtime rollback driven by an external account capability gap, and the durable project capability is now represented by requirements, diagnostics, documentation, and tests.
- Follow-up feature: None

## Files Changed

- `.agent-harness/progress.md`
- `.agent-harness/runs/F014-manual-coding.md`
- `.env.example`
- `README.md`
- `requirements.txt`
- `src/audio_input.py`
- `src/config.py`
- `src/main.py`
- `src/wake_word.py`
- `tests/test_audio_input.py`
- `tests/test_config.py`
- `tests/test_documentation.py`
- `tests/test_main.py`
- `tests/test_openai_client.py`
- `tests/test_state_machine.py`
- `tests/test_wake_word.py`

## Evaluator Result

Awaiting Evaluator Agent review. Do not mark F014 done until a durable evaluator run records the exact `EVAL_PASS: F014` line.

## Follow-Up

- Run Evaluator Agent for F014.
