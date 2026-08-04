# F108 fast coding evidence

## Scope

- Added a privacy-safe local-versus-Realtime acknowledgement evaluator with a
  one-shot experimental handoff; the local 480 ms asset remains production.
- Realtime ACK uses the active session's model, `alloy` voice, WebRTC output,
  and host gain, disables tools, and gates input until response and playback
  lifecycle completion.
- Added deterministic timeout, cancellation, failure, cleanup, and wake
  recovery behavior plus sanitized saved-local-trial reuse for retry safety.
- Added the fixed short Mandarin bridge `嗯，我在，请说。`. It is a perceived
  wait cue after session configuration, not a claim that negotiation is faster.
- Removed low numeric `max_output_tokens` caps from ACK and farewell audio.
  Current OpenAI reference defines the setting as a total response-output cap
  and defaults it to `inf`; exact-content prompts, disabled tools, and existing
  bounded lifecycle timeouts remain the guards.

## Verification

- Focused ACK evaluator, controller, host, and documentation suite: 78 passed.
- `node --check src/realtime_host/static/app.js`: passed.
- `git diff --check`: passed.
- Final `./init.sh`: passed with 437 project tests, 10 Mac frontend/fake
  sidecar tests, 25 Rust tests, dry-run, fake-backend, and Realtime fake smoke.

## Authorized live evidence

- Owner authorization covered microphone, speaker, network, and paid API use.
- Complete sanitized local baseline: configured-session ready 1,952 ms,
  observable playback start 1,985 ms, playback completion 3,107 ms,
  input-ready 3,192 ms, and cleanup 46 ms after wake/stop boundaries.
- The first Realtime attempt ended `incomplete` under a low numeric audio-token
  cap and recovered wake ownership safely; the failure remains recorded in
  `20260804T075709Z-F108-live-incomplete.md`.
- A separately authorized retry used the fixed Mandarin short bridge and the
  active `gpt-realtime-2.1` / `alloy` / `0.5` profile. It completed response and
  WebRTC playback lifecycle, restored wake ownership, and received the owner's
  explicit `realtime` perceptual verdict: correct Chinese cue and natural
  length.
- Realtime timing after wake: configured-session ready 2,587 ms, response
  creation 2,770 ms, first observable playback 3,159 ms, playback completion
  6,344 ms, input-ready 6,628 ms, and cleanup 77 ms.
- Realtime input-ready was 3,436 ms slower than the saved local baseline. The
  284 ms playback-completion-to-input-ready tail supports the short bridge as a
  perceived-wait cue, not a faster-negotiation or acoustic-onset claim.
- Recommendation: consider Realtime for voice consistency; production remains
  local until a separate owner decision.
- Sanitized evidence is in `tmp/realtime-evals/ACK-AB-evidence.json`; no audio,
  transcript, response text, credentials, SDP, ICE, provider payloads, private
  tool data, or session identifiers are retained.

FAST_CODING_EVIDENCE: F108
CODING_PASS: F108
