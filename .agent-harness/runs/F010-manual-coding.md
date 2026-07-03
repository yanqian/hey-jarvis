# Run Record: F010 - Add wake-word debug probes

## Summary

- Date: 2026-07-03
- Agent role: Manual Coding Agent fallback
- Feature: F010 - Add wake-word debug probes
- Result: Implementation completed by manual fallback; awaiting Evaluator Agent review.

## Repository State

- Starting commit: `309e024 F009 Prevent wake-listening microphone overflow`
- Ending commit: not committed
- Working tree status: modified project and harness files, with pre-existing F010 planning state preserved.

## Commands Run

```bash
git log --oneline -20
./init.sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall -q src tests
./init.sh
```

## Evidence

- Tests: full project unittest discovery passed 49 tests covering debug output shape, generated WAV-file scoring, CLI parser flags, `WAKE_DEBUG` configuration, normal `WAIT_WAKE` score logging, PCM RMS/peak metrics, and microphone overflow surfacing.
- Recovery: final `./init.sh` passed harness verification, project compile, project tests, dry-run smoke, and fake-backend smoke.
- Logs: `WAKE_DEBUG=1` logs `Wake debug:` lines with `rms`, `peak`, `overflow`, `score`, `threshold`, and `detected` fields during normal `WAIT_WAKE` listening.
- External behavior verification: F010 uses Python standard-library `argparse` and `wave` behavior plus project fake detectors and generated WAV fixtures. Real microphone and openWakeWord model execution remain manual runtime checks because automated recovery tests intentionally avoid microphone permissions and physical audio devices.
- Capability gaps: none for automated F010 verification. Real live microphone probing requires local macOS microphone permission and installed runtime dependencies, which are documented setup requirements rather than bypassed test dependencies.

## Failure Analysis

- Failure domain: none
- Failure summary: No implementation failure or blocked capability was encountered during this manual coding pass.
- Harness improvement: Not required; manual fallback was explicitly requested by the interactive Coding Agent prompt, run evidence was recorded, and evaluator gating remains in place.
- Follow-up feature: None

## Files Changed

- `.agent-harness/progress.md`
- `.agent-harness/runs/F010-manual-coding.md`
- `.env.example`
- `README.md`
- `src/audio_input.py`
- `src/config.py`
- `src/main.py`
- `src/state_machine.py`
- `src/wake_word.py`
- `tests/test_audio_input.py`
- `tests/test_config.py`
- `tests/test_documentation.py`
- `tests/test_main.py`
- `tests/test_state_machine.py`
- `tests/test_wake_word.py`

## Evaluator Result

Awaiting Evaluator Agent review. Do not mark F010 done until a durable evaluator run records the exact `EVAL_PASS: F010` line.

## Follow-Up

- Run Evaluator Agent for F010.
