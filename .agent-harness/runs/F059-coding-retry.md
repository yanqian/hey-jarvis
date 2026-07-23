# F059 Coding Retry

FAST_CODING_EVIDENCE: F059

CODING_PASS: F059

## Trigger

Two authorized real-device assisted runs reached the long-answer response, but
natural near-end speech did not emit `host_speech_started` before the configured
idle timeout. Both sessions cleaned up successfully. The user confirmed hearing
the quiet response and speaking a deliberate interruption.

## Correction

- Made failed live scenarios first-class versioned sanitized evidence.
- Added precise failure stages and bounded safe failure messages.
- Detects an active session returning to `wake_owned` before a required event
  instead of waiting for a longer generic runner timeout.
- Requests stop on every failed path and captures the final sanitized host state.
- Keeps the RT003 product verdict failed; no VAD, output gain, Realtime product
  behavior, or oracle threshold was changed.
- Clarified the feature contract: F059 validates the evaluation capability's
  ability to preserve an honest PASS or FAIL. It does not require a pre-existing
  product behavior to pass and never relabels RT003 failure as success.

## Verification

- Focused RT003, existing fixture-runner, and Realtime fake-smoke tests pass.
- Added real-shaped regressions for early session close and persisted sanitized
  failure evidence.
- The two live failures and cleanup result are recorded separately in
  `F059-rt003-live-failures.md`.

This coding retry does not contain or claim evaluator approval.
