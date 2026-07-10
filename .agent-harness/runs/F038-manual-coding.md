# Run Record: F038 - manual coding fallback

## Context

- Feature: F038 - Require a safe post-ACK boundary
- Target: follow-up update to existing PR1 branch `fix/armed-baseline-ack-guard`
- Evidence: real ACK-enabled logs ended suppression with `quiet=0.00s`, clipped peaks, then triggered ARMED with `noise_floor=0.0`; ACK-disabled A/B path recorded correctly.
- Workflow: evaluator-gated fast work attempted normally and with approved escalation; both failed the configured Codex Evaluator Agent runtime preflight before coding handoff.
- Failure domain: agent_workflow_gap
- Harness improvement: none in this product follow-up; the provider runtime issue is already known and the manual fallback retains separate evaluator gating.

## Implementation

- Replaced the active guard return tuple with an explicit post-ACK boundary result containing quiet, suppression, seed, RMS/peak, overflow/clipped, and timeout context.
- Guarded ACK flows now wait up to the hard buffer limit for contiguous safe quiet; no quiet means local `no_speech_after_wake` without ARMED, recording, or OpenAI.
- Quiet chunks seed ARMED noise-floor state but do not enter recording pre-roll.
- Guarded post-ACK ARMED requires quiet plus useful noise samples, logs baseline-ready timing/counts, and clears pre-roll on clipped or overflowed chunks.
- ACK-disabled and guard-disabled compatibility paths remain available.
- Updated defaults to 0.80s initial guard, 0.16s quiet, RMS 900, and 1.50s maximum suppression, with clipped-echo volume/short-ack guidance.
- Preserved untracked user logs `tmp/debug.log` and `tmp/pr1-real.log` without reading them into the commit or modifying them.

## Verification

- `python3 -m unittest tests.test_state_machine tests.test_config tests.test_documentation` -> 51 tests passed.
- `python3 -m unittest discover -s tests` -> 172 tests passed.
- `./init.sh` -> harness, compilation, 172 project tests, dry-run, and fake-backend smoke passed.
- Fake-backend trigger logs `post_ack_quiet_observed=true` and `noise_floor_has_samples=true` before recording.
- `git diff --check` -> passed.

FAST_CODING_EVIDENCE: F038
CODING_PASS: F038
