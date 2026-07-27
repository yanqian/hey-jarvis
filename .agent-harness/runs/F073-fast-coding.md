# F073 Fast Coding Evidence

Feature: F073 - Stabilize Realtime playback on Mac built-in speakers

FAST_CODING_EVIDENCE: F073

## Implementation

- Added validated `REALTIME_INPUT_NOISE_REDUCTION` with `far_field` as the
  built-in speaker/microphone default, `near_field` for headset-style capture,
  and `none` for explicit diagnostic disablement.
- The browser now requires ordinary echo cancellation, inspects the active
  microphone track capabilities, and requests standardized `all` echo
  cancellation when advertised with a safe required-boolean fallback.
- Realtime session updates send input noise reduction before server VAD and
  retain `create_response=true` plus `interrupt_response=true`.
- Sanitized microphone evidence now includes requested and actual echo
  cancellation, whether `all` was advertised, input noise reduction, and
  output volume.
- WebRTC `output_audio_buffer.started` and `.stopped` events now define remote
  playback state independently of response-generation completion and are
  retained as bounded content-free host lifecycle events.
- Configuration and manual-test guidance distinguish built-in speaker and
  headset profiles. The checked-in playback default remains 0.1 pending live
  acceptance; the ignored local `.env` is prepared for the authorized test at
  volume 0.3 with far-field reduction.

## Offline Verification

- `node --check src/realtime_host/static/app.js`
  - PASS.
- `python3 -m unittest tests.test_realtime_config tests.test_realtime_host tests.test_documentation`
  - PASS: 42 tests.
- `./init.sh`
  - PASS: 73 features validated, 344 project tests, pipeline smoke, and
    Realtime fake smoke.
- `git diff --check`
  - PASS.

No live network, credential, microphone, speaker, or browser call was made
during offline coding verification. Existing untracked `tmp/` logs and private
Realtime eval artifacts were not modified or staged.

## Remaining Acceptance

Run one user-led built-in-microphone/speaker session at local output volume 0.3.
A normal answer must remain continuous without a playback-correlated false
speech/cancellation chain; one deliberate interruption must still cancel the
active answer and receive a continuation; cleanup must restore wake ownership.

CODING_PASS: F073
