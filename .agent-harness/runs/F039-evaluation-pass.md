# Evaluation: F039 - Preserve clipped post-ACK user speech

Date: 2026-07-10
Role: cold-start Evaluator Agent

## Verdict

EVAL_PASS: F039

## Acceptance evidence

- `ACK_GUARD_SECONDS` and `ack_guard_seconds` are absent from tracked runtime configuration, examples, documentation, tests, and post-ACK logs. The local ignored `.env` also has no active `ACK_GUARD_SECONDS` entry. `ACK_GUARD_MAX_BUFFER_SECONDS` remains the bounded post-ACK suppression timeout.
- `_wait_for_post_ack_boundary()` retains the F038 fail-closed boundary: clipped, overflowed, or loud residue resets contiguous quiet/noise candidates; only verified quiet seeds ARMED; timeout returns `quiet_observed=false` and locally cancels before recording or OpenAI.
- Protected post-boundary ARMED handling skips each overflowed chunk without clearing earlier pre-roll. Clipped PCM is retained in the bounded pre-roll while `voiced=false`, excluded from `valid_chunks`, and excluded from noise-floor sampling.
- The synthetic ACK-boundary regression records `[LOUD_CHUNK, USER_CLIPPED_CHUNK, LOUD_CHUNK, LOUD_CHUNK]`, excludes the pre-boundary clipped ACK residue, and triggers only after later valid voiced chunks. A separate overflow regression proves earlier safe speech survives while the incomplete overflow chunk is omitted.
- ACK-disabled immediate-speech and F038 no-quiet/clipped-trigger rejection regressions pass. Trigger diagnostics continue to expose pre-roll duration/counts and post-ACK boundary metrics.
- `tmp/debug.log` and `tmp/pr1-real.log` remained untracked and were not included in evaluator-owned changes.

## Verification

- Required startup `./init.sh`: passed; 175 project tests plus harness, compile, dry-run, and fake-backend checks passed.
- Focused config/documentation/state-machine evaluation: 23 tests passed.
- `python3 -m src.main --dry-run`: passed.
- `python3 -m src.main --fake-backend`: passed.
- `python3 -m src.main --diagnose`: executed and loaded configuration; host-system Python/dependency readiness errors were reported actionably and are unrelated to this dependency-free feature verification.
- `git diff --check`: passed.

Failure domain: none
Harness improvement: none required.
