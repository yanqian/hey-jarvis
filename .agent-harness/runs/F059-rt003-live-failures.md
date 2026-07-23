# F059 RT003 Live Attempt Failures

## Summary

Three authorized real-device RT003 attempts ran on the built-in Mac microphone and
speakers with Chrome reporting echo cancellation, noise suppression, automatic
gain control, 48 kHz mono capture, output gain `0.1`, and server-VAD threshold
`0.8`. Each attempt entered a fresh Realtime session, created the deterministic
long response, reached the 15-second idle timeout without any
`host_speech_started`, stopped cleanly, and restored `wake_owned` with the local
wake microphone open.

The first two attempts ran with noticeable room noise. The third attempt was an
explicit quiet-room retest on 2026-07-23 after reopening and arming a fresh Chrome
app-mode host. The user confirmed that the counting response was intelligible and
that they spoke a deliberate near-end interruption. The third run created the
long response, emitted no `host_speech_started`, stopped at the 15-second idle
timeout, and reopened the wake microphone. No transcript text, utterance content,
raw/base64 audio, credential, tool payload, or full session identity is recorded
here.

## Result

- Scenario: RT003 version 1
- Evidence tier: live-near-end
- Result: failed
- Failure stage: near-end speech detection
- Old response cancellation latency: unavailable because no server speech-start
  event was emitted
- Cleanup: passed on all three attempts

## Failure Analysis

- Failure domain: implementation_gap
- Failure summary: Natural live near-end speech produced no server
  `host_speech_started` in three authorized RT003 attempts, including one
  quiet-room retest, and the initial eval
  runner did not persist structured evidence for that failed outcome.
- Harness improvement: Improve the project-owned F059 evaluator, not the
  generic harness runtime. Failed live scenarios now emit sanitized versioned
  evidence, detect early session closure, request bounded cleanup, and have
  focused regression coverage.
- Follow-up feature: None yet. Product sensitivity tuning or numeric microphone
  level observability must be separately normalized if the user chooses to
  pursue the failed RT003 behavior.
- Product observation: the previously accepted saved fixtures can cross the
  `0.8` server-VAD threshold, but natural live near-end speech did not cross it
  in these three attempts. The quiet-room retest weakens ambient room noise as
  the primary explanation. This is a real fixture-versus-human generalization
  gap, not acceptable passing RT003 evidence.
- Eval implementation observation: the first runner version printed a generic
  timeout and did not persist failure evidence after the session had already
  returned to wake ownership.
- Harness improvement assessment: no generic harness runtime change is needed.
  F059 should make failed live scenarios first-class sanitized evidence and
  fail immediately when the active session closes before the required event.
- Follow-up boundary: do not lower the scenario threshold, change product VAD,
  or substitute same-Mac replay merely to obtain a pass. Product sensitivity
  tuning and numeric microphone-level observability require separately
  normalized follow-up work if RT003 continues to fail.
