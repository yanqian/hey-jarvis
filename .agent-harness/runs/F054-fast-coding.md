# F054 fast coding evidence

FAST_CODING_EVIDENCE: F054
CODING_PASS: F054

## Implemented

- Added the opt-in `RealtimeSessionController` and production `--backend realtime` runtime wiring.
- Required consecutive local wake confirmation, closed Python capture before acknowledgement, and deferred initial wake-microphone opening until Chrome arm warm-up had stopped.
- Entered ACTIVE_SESSION only after WebRTC transport, `session.created`, and configured `session.updated` readiness.
- Kept the browser WebRTC session alive across follow-up turns with direct processed microphone and remote media tracks.
- Configured Realtime server VAD response creation/interruption and input transcription while avoiding client cancellation/truncation and Python PCM/playback paths.
- Unified idle, maximum-duration, explicit stop, peer/data-channel failure, Realtime error, controller error, microphone error, and Ctrl+C through bounded media teardown and wake recovery.
- Added a dependency-free two-turn fake smoke to root recovery.
- Added private Git-ignored voice fixture capture, integrity manifests, replay derivatives, and an event-gated acoustic acceptance runner. The runner requires two `completed` turns, a `cancelled` barge-in response within one second of speech detection, and confirmed fresh wake ownership; it requests safe stop on failure.
- Updated Realtime host and project documentation without changing the pipeline default.

## Verification

- Focused Realtime controller, coordinator, fixture, runner, configuration, host, and JavaScript checks pass.
- `./init.sh` passes with 255 project tests, pipeline dry-run/fake regression, and the two-turn Realtime fake smoke.
- Real built-in-speaker/microphone replay completed two follow-up turns in one session, cancelled the long response 32 ms after barge-in speech detection, stopped browser media, and restored Python wake capture. See `F054-real-device-acceptance.md`.
- Private fixtures remain under ignored `tmp/realtime-fixtures/`; `git status` exposes no audio or transcript artifact.

The coding phase has not written evaluator approval, changed F054 to done, or set `passes=true`.

