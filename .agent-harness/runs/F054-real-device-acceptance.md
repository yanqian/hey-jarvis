# F054 real-device acceptance

Date: 2026-07-17 (Asia/Singapore)

## Boundary

- Hardware: built-in Mac microphone and speakers, no headphones.
- Host: Chrome app mode on loopback.
- Model/voice: configured Realtime model and voice; credentials and session identifiers omitted.
- Input: private local voice fixtures recorded from the user, stored under the Git-ignored `tmp/realtime-fixtures/` directory. No recording or transcript is included in this evidence.
- Replay derivatives removed leading/trailing capture wait while preserving originals and integrity metadata.

## Result

- Local wake replay scored `0.978938639` against the configured Hey Jarvis detector and crossed the configured threshold.
- Browser arm reported `echoCancellation=true`, `noiseSuppression=true`, `autoGainControl=true`, `sampleRate=48000`, and `channelCount=1`.
- The browser warm-up track stopped before Python opened its wake microphone.
- Confirmed local wake closed Python capture before acknowledgement and before the host requested its microphone.
- One WebRTC session reached transport connected, `session.created`, configured/connected readiness, and ACTIVE_SESSION.
- Turn 1 produced one speech interval and `response.done reason=completed`.
- Turn 2 followed without another wake, produced one speech interval, and ended with `response.done reason=completed`.
- A deterministic long answer was requested. Replay barge-in then produced `speech_started`; the active response ended with `reason=cancelled` 32 ms later. No client `response.cancel`, truncation, playback-duration accounting, Python PCM forwarding, or local response playback was used.
- Explicit stop was followed by host media teardown confirmation in 197 ms and fresh Python wake-microphone ownership 108 ms later.
- Final sanitized state was `wake_owned`, `wake_microphone_open=true`, and no active session.

## Privacy and observability

The durable record contains only configuration booleans, relative event timing, status/reason values, and aggregate outcomes. It contains no API key, ephemeral credential, session identifier, audio bytes, transcript, or user question text.

