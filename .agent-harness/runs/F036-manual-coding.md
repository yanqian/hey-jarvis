# Run Record: F036 - manual coding fallback

## Context

- Feature: F036 - Guard ARMED startup and acknowledgement boundary
- Workflow: evaluator-gated fast work attempted first
- Failure: both sandboxed and approved escalated `make -C .agent-harness work-fast` runs failed the configured Codex Evaluator Agent provider runtime check before handoff.
- Fallback: interactive provider-native coding, with separate evaluator approval still required.
- Failure domain: agent_workflow_gap
- Harness improvement: none in this product PR; the installed provider contract is configured but its runtime check fails outside the product implementation boundary.

## Implementation

- Added validated ARMED baseline, latest-chunk, and acknowledgement-guard settings with documented defaults.
- Gated ARMED triggers on baseline readiness while preserving baseline-period and initial guard-tail audio in pre-roll.
- Added baseline fields to `armed_trigger` and `armed_summary` without removing existing result markers.
- Replaced active blind acknowledgement draining with a bounded quiet-aware guard and retained the fixed drain as the disabled-guard compatibility path.
- Added focused baseline, cold-noise-floor, latest-chunk, acknowledgement-only, boundary-preservation, configuration, and documentation coverage.
- Did not add VAD, runtime dependencies, recorder endpointing changes, wake-word changes, or extra spoken prompts.

## Verification

- `python3 -m unittest tests.test_config tests.test_state_machine tests.test_documentation` -> 49 tests passed.
- `./init.sh` -> harness checks passed, 170 project tests passed, dry-run passed, fake-backend passed, and fake-backend `armed_trigger` reported `baseline_ready=true`.
- `python3 -m src.main --diagnose` executed and reported the expected host-environment capability errors (Python 3.14 and missing optional runtime packages) without a code exception; diagnostics behavior remains intact.
- `git diff --check` -> passed.

FAST_CODING_EVIDENCE: F036
CODING_PASS: F036
