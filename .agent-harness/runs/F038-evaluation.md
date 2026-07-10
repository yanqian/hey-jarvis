# Run Record: F038 evaluation

## Scope

- Evaluated F038 against its normalized SPEC entry, feature acceptance criteria, `QUALITY.md`, and evaluator-evidence rules.
- Inspected configuration, the explicit post-ACK boundary result, ARMED gating, pre-roll handling, diagnostics, documentation, and focused synthetic-audio coverage.
- Preserved the unrelated untracked files `tmp/debug.log` and `tmp/pr1-real.log` without reading or modifying them.
- Did not modify product code.

## Verification

- `./init.sh` -> passed: harness verification, 172 project tests, dry-run smoke, and fake-backend smoke.
- `python3 -m unittest tests.test_state_machine tests.test_config tests.test_documentation` -> 51 tests passed.
- `python3 -m src.main --dry-run` -> passed.
- `python3 -m src.main --fake-backend` -> passed with `post_ack_quiet_observed=true`, two quiet noise seeds, and `noise_floor_has_samples=true` before recording.
- `python3 -m src.main --diagnose` -> diagnostics executed and reported the expected host capability errors for unsupported Python 3.14 and absent runtime packages.
- `git diff --check` -> passed.
- Direct supported-configuration probe with `ACK_GUARD_MIN_QUIET_SECONDS=0` and a loud first post-ACK chunk -> `_PostAckBoundaryResult(quiet_observed=True, noise_seed_chunks=(), timed_out=False)`.

## Failure

F038 does not yet enforce its mandatory safe post-ACK quiet/noise boundary for all accepted configurations. `src/config.py` accepts `ACK_GUARD_MIN_QUIET_SECONDS=0`, and `_wait_for_post_ack_boundary()` then evaluates `quiet_seconds >= quiet_required` as true even when the first chunk is loud. It returns `quiet_observed=true` with no noise seed and does not time out, contradicting the normalized requirement that guarded ACK-enabled flow require observed quiet and useful noise seeds before entering ARMED. Focused tests cover the defaults but not this accepted zero-value edge case.

- Failure domain: implementation_gap
- Harness improvement: add an evaluator/checklist probe for validation-boundary values whenever a feature strengthens an existing configurable safety gate; no harness runtime change is required.

EVAL_FAIL: F038: ACK_GUARD_MIN_QUIET_SECONDS=0 is accepted but marks a loud post-ACK chunk quiet with no noise seed, bypassing the mandatory safe boundary
