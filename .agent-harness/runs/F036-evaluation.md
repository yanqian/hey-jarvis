# Run Record: F036 evaluation

## Scope

- Evaluated F036 against its normalized SPEC entry, feature acceptance criteria, `QUALITY.md`, and evaluator-evidence rules.
- Inspected configuration, ARMED baseline gating, acknowledgement guard behavior, logging, documentation, and focused synthetic-audio coverage.
- Did not modify product code.

## Verification

- `./init.sh` -> passed: harness verification, 170 project tests, dry-run smoke, and fake-backend smoke.
- `python3 -m unittest tests.test_config tests.test_state_machine tests.test_documentation` -> 49 tests passed.
- `python3 -m src.main --dry-run` -> passed.
- `python3 -m src.main --fake-backend` -> passed with acknowledgement guard output and `armed_trigger ... baseline_ready=true`.
- `python3 -m src.main --diagnose` -> diagnostics executed correctly and reported expected host capability errors for unsupported Python 3.14 and absent optional runtime packages.
- `git diff --check` -> passed.

## Result

F036 satisfies its acceptance criteria: validated documented defaults and overrides are present; ARMED gates on elapsed baseline time and valid chunks, excludes overflowed/clipped chunks from voice decisions, updates noise samples only from valid non-voiced chunks, can require the latest chunk to be voiced, preserves baseline/guard-tail pre-roll, and emits the required diagnostics. The bounded acknowledgement guard prevents acknowledgement-only residue from entering recording while preserving a conservative late non-quiet tail for eventual recording. Deterministic tests verify local no-speech cancellation skips recording and all downstream OpenAI/tool/TTS/answer-playback work.

EVAL_PASS: F036
