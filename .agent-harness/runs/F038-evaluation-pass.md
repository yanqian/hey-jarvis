# Run Record: F038 evaluation pass after retry

## Scope

- Re-evaluated F038 after the recorded coding retry against its normalized SPEC entry, feature acceptance criteria, `QUALITY.md`, and evaluator-evidence rules.
- Preserved the prior evaluator failure record in `F038-evaluation.md`.
- Inspected the configuration boundary, defensive runtime boundary, post-ACK result and ARMED gating, pre-roll safety, diagnostics, documentation, and regression coverage.
- Preserved unrelated untracked files `tmp/debug.log` and `tmp/pr1-real.log` without reading or modifying them.
- Did not modify product code.

## Verification

- `./init.sh` -> passed: harness verification, 174 project tests, dry-run smoke, and fake-backend smoke.
- `python3 -m unittest tests.test_state_machine tests.test_config tests.test_documentation` -> 53 tests passed.
- `python3 -m unittest discover -s tests` -> 174 tests passed.
- Independent configuration probe with enabled guard and `ACK_GUARD_MIN_QUIET_SECONDS=0` -> rejected with the documented `ConfigError`.
- Independent runtime probe bypassing configuration with zero quiet duration and loud audio -> fail-closed boundary with `quiet_observed=false`, no noise seeds, and `timed_out=true`.
- `python3 -m src.main --dry-run` -> passed.
- `python3 -m src.main --fake-backend` -> passed with `post_ack_quiet_observed=true`, two quiet noise seeds, `noise_floor_has_samples=true`, and baseline-ready diagnostics before recording.
- `python3 -m src.main --diagnose` -> diagnostics executed correctly and reported expected host capability errors for unsupported Python 3.14 and absent runtime packages.
- `git diff --check` -> passed.

## Result

F038 now satisfies its acceptance criteria. Guarded ACK flow exposes the required explicit boundary metrics, waits for contiguous safe quiet within the bounded maximum, cancels locally when no boundary is available, supplies useful quiet noise seeds before protected ARMED can trigger, and keeps clipped or overflowed residue out of recording pre-roll. ACK-disabled immediate speech and guard-disabled legacy drain compatibility remain intact. Defaults, documentation, diagnostics, focused regressions, full discovery, and recovery verification are consistent. The prior zero-duration gap is closed at configuration load and independently fails closed at runtime.

EVAL_PASS: F038
