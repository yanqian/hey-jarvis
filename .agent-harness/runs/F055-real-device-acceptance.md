# F055 Real-Device Acceptance

Date: 2026-07-17

## Environment

- macOS built-in microphone and speakers; no headphones.
- Project-selected Chrome app-mode WebRTC host on loopback.
- Actual capture settings reported `echoCancellation=true`, `noiseSuppression=true`, `autoGainControl=true`, 48 kHz mono.
- Realtime backend used the configured model, voice, server VAD, and input transcription.
- The temporary acceptance process used a 60-second idle window only to accommodate task-UI response latency; tracked defaults were unchanged.

## Procedure

1. Start a fresh Python Realtime controller and fresh armed Chrome host identity.
2. Trigger the existing local wake path with the private saved wake fixture.
3. Confirm exclusive handoff reaches `host_active` with the Python wake microphone closed.
4. Speak one configured English end phrase as one complete utterance.
5. Inspect only the bounded sanitized coordinator report; do not retain transcript text or item/session identifiers.

## Result

PASS.

The sanitized ordering was:

```text
host_connected
host_speech_started
host_speech_stopped
host_response_created
host_transcription
host_end_phrase_matched
host_command(reason=end_phrase)
host_stopped(reason=end_phrase)
wake_microphone_reopened
```

Final state was `wake_owned`, `wake_microphone_open=true`, and `active_session=false`. The report contained one end-phrase match and no transcript text, raw/base64 audio, standard API key, or ephemeral credential.

Earlier attempts were intentionally rejected as evidence when the service was no longer alive, the Codex in-app browser rather than the selected Chrome host owned the track, or no `speech_started` event arrived. This final run used the production-path Chrome host and received real user speech.
