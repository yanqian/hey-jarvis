# Run Record: F011 - evaluation

## Summary

- Date: 2026-07-03
- Agent role: Evaluator Agent manual fallback
- Feature: F011 - Add wake debug capture replay
- Result: Passed

## Repository State

- Starting commit: `309e024 F009 Prevent wake-listening microphone overflow`
- Ending commit: not committed
- Working tree status: F010 and F011 implementation, planning state, manual coding evidence, and this evaluator evidence are uncommitted.

## Commands Run

```bash
git log --oneline -20
./init.sh
.venv/bin/python -m unittest tests.test_main tests.test_state_machine tests.test_documentation
.venv/bin/python -m src.main --help
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python -m compileall -q src tests
.agent-harness/scripts/validate-feature.sh F011
./init.sh
```

## Evidence

- Tests: focused F011-adjacent tests passed 12 tests covering parser exposure, live debug output, saved debug WAV shape, high-precision score formatting, summary metrics, parser validation, short final WAV replay, README coverage, and `WAKE_DEBUG` log precision.
- Tests: full project unittest discovery passed 52 tests without requiring physical microphone access, OpenAI credentials, or speaker playback.
- Feature validation: `.agent-harness/scripts/validate-feature.sh F011` passed.
- Recovery: final root `./init.sh` passed harness verification, project compile, full project tests, dry-run smoke, and fake-backend smoke.
- Runtime inspection: `python -m src.main --help` exposes `--wake-debug-output PATH` alongside `--wake-debug` and `--wake-file`.
- External behavior verification: automated checks use Python standard-library `argparse` and `wave` behavior plus generated WAV fixtures and fake detectors. Real live microphone capture remains a documented manual integration path because physical devices and macOS microphone permission cannot be exercised reliably in automated recovery tests.

## Failure Analysis

- Failure domain: none
- Failure summary: none for the feature implementation or verification.
- Harness improvement: not required for this feature. Orchestrator execution was attempted first, but the Coding Agent adapter hung inside `subprocess.communicate()` and was interrupted; manual fallback preserved run evidence, evaluator gating, feature status updates, and final `./init.sh` verification.
- Follow-up feature: none

## Files Changed

- `.agent-harness/runs/F011-evaluation.md`

## Evaluator Result

```text
EVAL_PASS: F011
```

## Follow-Up

- Use `python -m src.main --wake-debug --wake-debug-output tmp/wake-debug.wav` to capture a real live wake attempt, then replay it with `python -m src.main --wake-file tmp/wake-debug.wav`.
