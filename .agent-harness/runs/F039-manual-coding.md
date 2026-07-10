# Run Record: F039 - manual coding fallback

## Context

- Feature: F039 - Preserve clipped post-ACK user speech
- Target: follow-up update to existing PR1 branch `fix/armed-baseline-ack-guard`
- Real evidence: 18 checked/12 valid ARMED chunks, `max_peak=32768`, configured 800ms pre-roll collapsed to 240ms, and transcription lost `1+1`.
- Workflow: normal and approved escalated `make -C .agent-harness work-fast` both failed the configured Codex Evaluator Agent runtime preflight before coding handoff.
- Failure domain: agent_workflow_gap
- Harness improvement: none in this product correction; the known provider runtime issue remains outside feature scope and separate evaluator gating is retained.

## Implementation

- Removed unused `ACK_GUARD_SECONDS` / `ack_guard_seconds` from defaults, Settings, parsing, construction, environment examples, docs, tests, logs, and local `.env`.
- Kept `ACK_GUARD_MAX_BUFFER_SECONDS` as the sole post-ACK timeout.
- Preserved pre-boundary clipped/overflow residue rejection and quiet/noise candidate reset.
- Changed post-boundary ARMED handling so overflow is omitted individually, clipped PCM is retained in bounded pre-roll, and neither counts as voiced or noise evidence.
- Added regressions proving clipped user PCM and earlier safe speech survive to recording, while overflow is omitted without clearing earlier safe pre-roll.
- Preserved untracked user logs without staging or modifying them.

## Verification

- `python3 -m unittest tests.test_state_machine tests.test_config tests.test_documentation` -> 54 tests passed.
- `./init.sh` -> harness, compilation, 175 project tests, dry-run, and fake-backend smoke passed.
- Fake-backend post-ACK log no longer contains the misleading `initial_guard` field.
- Repository search finds no tracked runtime/config/docs occurrence of `ACK_GUARD_SECONDS`; the sole occurrence is a negative documentation assertion.
- `git diff --check` -> passed.

FAST_CODING_EVIDENCE: F039
CODING_PASS: F039
