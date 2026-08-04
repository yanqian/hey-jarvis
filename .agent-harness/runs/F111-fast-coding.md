# Run Record: F111 - cached ACK parallel handoff

## Summary

- Date: 2026-08-04
- Agent role: provider-native fast Coding Agent
- Feature: F111
- Result: coding_pass
- Starting commit: `01d0af6`

## Implementation

- The normal Realtime default is now `cached`; explicit `realtime` and `local`
  acknowledgement modes remain available as rollback paths.
- Startup validates the owner-selected canonical WAV and manifest before the
  loopback host binds. Model and voice must match the active Realtime settings.
- Arm preloads the validated WAV. After the local wake microphone is released,
  the browser starts cached playback through the same audio element and gain
  used for subsequent Realtime output while the unified WebRTC session connects.
- The browser input track stays disabled until both cached playback completion
  and configured-session readiness are accepted for the active session. Either
  completion order works; duplicate, stale, wrong-mode, and early-input events
  fail closed.
- Playback/preload, negotiation, timeout, settings, page lifecycle, transport,
  and media failures converge on bounded cleanup and wake recovery.
- The packaged sidecar includes and validates the canonical WAV plus manifest.

## Offline Verification

- Focused cached/config/controller/asset/host/sidecar/main/Mac-shell tests: 113
  passing after the new timeout/cleanup coverage.
- `node --check src/realtime_host/static/app.js`: passed.
- Realtime fake smoke in `cached` mode: passed with exclusive handoff, two turns,
  interruption, tools, end phrase, close, and wake recovery.
- Final `./init.sh`: passed, including the complete project test suite and both
  pipeline and Realtime recovery smokes.

## Authorized Target-Mac Overall Flow

- The owner explicitly authorized one short microphone/speaker/OpenAI Realtime
  session and manually performed wake, a normal question, semantic end, and
  audible verification on the target Mac.
- Active profile: `gpt-realtime-2.1`, `alloy`, browser gain `0.5`, cached ACK.
- Wake microphone closed 115 ms after wake confirmation, before the handoff.
- Cached ACK playback began 411 ms after wake confirmation and 296 ms after the
  handoff was queued.
- Cached ACK playback lasted 2,620 ms for the validated 2,429 ms asset.
- Configured-session readiness arrived 3,186 ms after wake; in this run it was
  155 ms after cached playback completed.
- Input became ready 3,416 ms after wake and 385 ms after cached playback
  completed. The first user speech event occurred 786 ms after input readiness.
- No live-Realtime ACK response creation or ACK playback event occurred; the
  paid session was the single ordinary unified Realtime call.
- Normal response lifecycle completed. Semantic end entered the native farewell
  lifecycle; farewell playback completed, media stopped 5 ms later, and wake
  ownership reopened 83 ms after farewell playback completion.
- Browser audio settings reported 48 kHz mono, echo cancellation, noise
  suppression, automatic gain control, `far_field` input noise reduction, and
  output gain `0.5`.
- The owner explicitly confirmed hearing the cached ACK, the normal answer, and
  the final `再见`.
- Evidence retains no audio, transcript, answer, tool arguments/results,
  credentials, SDP, ICE, or provider payloads.

## Verdict

FAST_CODING_EVIDENCE: F111

CODING_PASS: F111

Separate cold-start evaluator approval remains required. This record does not
mark the feature complete and contains no evaluator verdict.
