# Run Record: F004 - manual coding fallback

## Summary

- Date: 2026-07-03 15:54:41 +0800
- Agent role: Coding Agent
- Feature: F004 - Implement Hey Jarvis wake-word detector
- Result: Coding implementation complete; awaiting evaluator gating.

## Repository State

- Starting commit: 4d0abb4 F003 Add audio recording primitives
- Ending commit: not committed
- Working tree status: modified F004 harness state, project recovery check, README, progress, run evidence, plus untracked F004 source and tests.

## Commands Run

```bash
git log --oneline -20
./init.sh
python3 -m compileall -q src tests
python3 -m unittest tests/test_wake_word.py
python3 -m unittest discover -s tests -p 'test_*.py'
./init.sh
git diff --check
```

## Evidence

- Tests: focused F004 wake-word tests passed 6 tests; final project unittest discovery passed 22 tests.
- Logs: pre-change and final `./init.sh` runs passed harness verification, project compile, all project tests, and dry-run smoke.
- Screenshots or traces: none.
- External behavior verification: openWakeWord primary-source README and source were checked for `Model(wakeword_models=[...])`, `predict(frame) -> dict`, 16-bit 16 kHz PCM frame expectations, and the built-in Hey Jarvis model name. Tests use fake models and import shims, so no real microphone input, network access, or installed ML dependency is required for automated verification.
- Capability gaps: no gap blocks F004 automated verification. The local environment does not have `openwakeword` or `numpy` installed, but those dependencies are already declared in `requirements.txt` and the recovery check is intentionally dependency-free until the real runtime feature wires the full assistant.

## Failure Analysis

- Failure domain: none
- Failure summary: none
- Harness improvement: not required; manual fallback was explicitly requested by the interactive Coding Agent prompt and evaluator gating remains pending.
- Follow-up feature: none

## Files Changed

- `.agent-harness/feature_list.json`
- `.agent-harness/progress.md`
- `.agent-harness/runs/F004-manual-coding.md`
- `README.md`
- `init.sh`
- `src/wake_word.py`
- `tests/test_wake_word.py`

## Evaluator Result

```text
Awaiting Evaluator Agent.
```

## Follow-Up

- Run evaluator review for F004 before changing `feature_list.json` to `passes=true` or `status=done`.
