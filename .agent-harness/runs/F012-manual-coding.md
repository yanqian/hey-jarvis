# Run Record: F012 - Switch wake word to Alexa

## Summary

- Date: 2026-07-03
- Agent role: Manual Coding Agent fallback
- Feature: F012 - Switch wake word to Alexa
- Result: Implementation completed by manual fallback; awaiting Evaluator Agent review.

## Repository State

- Starting commit: `414fa12 F010-F011 Add wake debug probes`
- Ending commit: not committed
- Working tree status: modified project and harness files, with pre-existing F012 planning and partial implementation state preserved.

## Commands Run

```bash
git log --oneline -20
./init.sh
python3 -m unittest tests.test_wake_word tests.test_config tests.test_documentation
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall -q src tests
.agent-harness/scripts/validate-feature.sh F012
./init.sh
```

## Evidence

- Tests: focused F012-adjacent tests passed 21 tests covering Alexa defaults, loader arguments, score-key extraction, ONNX preparation paths, diagnostics, README documentation, and `.env.example` coverage.
- Tests: full project unittest discovery passed 52 tests without requiring physical microphone access, OpenAI credentials, live openWakeWord execution, or speaker playback.
- Feature validation: `.agent-harness/scripts/validate-feature.sh F012` passed while correctly leaving `F012` incomplete pending evaluator review.
- Recovery: final `./init.sh` passed harness verification, project compile, full project tests, dry-run smoke, and fake-backend smoke.
- External behavior verification: F012 relies on the existing openWakeWord metadata shape through real-shaped `FEATURE_MODELS` and `MODELS` fixtures in tests; automated verification intentionally avoids network downloads and physical microphone access. Real model preparation remains a documented runtime command.
- Capability gaps: none for automated F012 implementation verification. Real Alexa model download requires installed runtime dependencies and network access during `python -m src.main --prepare-wake-word`, which is documented as setup behavior rather than bypassed verification.

## Failure Analysis

- Failure domain: none
- Failure summary: No implementation failure or blocked capability was encountered during this manual coding pass.
- Harness improvement: Not required; manual fallback was explicitly requested by the interactive Coding Agent prompt, run evidence was recorded, and evaluator gating remains in place.
- Follow-up feature: None

## Files Changed

- `.agent-harness/progress.md`
- `.agent-harness/runs/F012-manual-coding.md`
- `.env.example`
- `README.md`
- `src/config.py`
- `src/main.py`
- `src/state_machine.py`
- `src/wake_word.py`
- `tests/test_config.py`
- `tests/test_documentation.py`
- `tests/test_wake_word.py`

## Evaluator Result

Awaiting Evaluator Agent review. Do not mark F012 done until a durable evaluator run records the exact `EVAL_PASS: F012` line.

## Follow-Up

- Run Evaluator Agent for F012.
