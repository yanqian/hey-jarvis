# F107 Fast Coding Evidence

FAST_CODING_EVIDENCE: F107

## Implementation

- Added an explicit `HOST_FAREWELL` coordinator phase for both the semantic
  `end_conversation` tool and exact configured end phrases. Entering it is
  idempotent, ignores new user-turn activity, and does not issue the existing
  stop command until farewell response and playback completion are both seen.
- The browser disables the active input track as soon as farewell is requested,
  cancels a pending or active ordinary response, and creates exactly one
  audio-only Realtime response with per-response tools disabled. A late
  ordinary `response.created` event is also cancelled before farewell starts.
- The farewell remains on the existing Realtime session and remote WebRTC audio
  element, so it inherits the configured session voice and
  `REALTIME_OUTPUT_VOLUME` path instead of introducing local TTS, an audio
  asset, or a second connection.
- Correlated response-created/done and output-buffer-started/stopped events gate
  normal teardown. Non-completed generation, transport failure, explicit stop,
  and an eight-second farewell timeout converge on the existing bounded cleanup
  and wake-microphone recovery path.
- Evidence records bounded event names, reasons, and monotonic timestamps only;
  no farewell text, transcript, provider payload, credential, SDP, or private
  tool data is retained.

## Verification

- `node --check src/realtime_host/static/app.js`: PASS.
- Focused Realtime host, controller, fake-smoke, configuration, and
  documentation tests: PASS (34 tests in the final focused run).
- `python3 -m src.realtime.fake_smoke`: PASS, including farewell closure and
  recovery to wake ownership.
- `python3 .agent-harness/scripts/validate-state.py`: PASS (108 features).
- `git diff --check`: PASS.
- Final `./init.sh`: PASS outside the filesystem sandbox because the existing
  loopback-capability test must bind a temporary `127.0.0.1` port. It includes
  426 project tests, ten Mac frontend/fake-sidecar tests, 25 Rust tests, harness
  verification, and all dry-run/fake-backend/Realtime smoke paths.

## Live Verification Boundary

- No OpenAI credential, network request, microphone, speaker, or paid Realtime
  call was used. A later owner-authorized live voice check may confirm the
  audible voice/volume match, but it is product evidence rather than a required
  automated gate for F107.

CODING_PASS: F107
