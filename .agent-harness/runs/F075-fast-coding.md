# F075 Fast Coding Evidence

Feature: F075 - Create configured Realtime sessions through one unified WebRTC call

## Implemented

- Added a loopback-only, content-type-checked, 128 KB-bounded `/session` SDP
  endpoint.
- Moved the complete validated model, language, audio input, transcription,
  server VAD, output voice, calculator, and semantic-ending configuration to
  Python.
- Added dependency-free multipart `sdp` plus `session` call creation using the
  standard server-side API key and the official Realtime calls endpoint.
- Removed the production browser's `/token` request, ephemeral credential,
  direct authenticated OpenAI request, and `session.update`.
- Made `session.created` from the already-configured call the readiness event
  while preserving transport ordering, disabled-track acknowledgement gating,
  explicit session-scoped input enablement, interruption, and cleanup.
- Kept arm-time browser playback metadata on a bounded non-secret loopback
  endpoint, outside the wake critical path.
- Retained the timing schema for compatibility while requiring both removed
  token phases to be exactly zero in coordinator and evaluator validation.
- Evolved RT001 to version 7 and documented unified negotiation semantics.

## Verification

- Focused Realtime host/controller/evaluator/documentation tests pass.
- JavaScript syntax validation passes.
- Full recovery passes with 348 project tests and Realtime fake smoke.
- Three user-led built-in-device sessions pass; durable sanitized observations
  are recorded in `.agent-harness/runs/F075-live-acceptance.md`.
- The live wake-to-configured median improved from F074's 5,066 ms to 2,081 ms
  in the bounded comparison, with zero token phases and preserved input gating.

This coding evidence does not mark the feature done, does not write evaluator
approval, and does not substitute local or live testing for an independent
Evaluator Agent.

FAST_CODING_EVIDENCE: F075
CODING_PASS: F075
