# F051 Real-device Acceptance

## Result

PASS for protocol-level speakerphone barge-in.

This acceptance supplements the earlier coding evidence and the independent evaluator pass. It does not change the evaluated implementation.

## Environment

- Chrome 150 on the project Mac
- Built-in MacBook Pro microphone and built-in speakers
- No headphones
- OpenAI Realtime WebRTC session
- Model `gpt-realtime-2.1`
- Voice `marin`

## Capture and connection evidence

- Requested and active settings both reported `echoCancellation=true`, `noiseSuppression=true`, `autoGainControl=true`, and one channel.
- Active sample rate was 48000 Hz.
- The peer connection reached `connected`, the data channel opened, and the remote audio track arrived.
- The report contained zero Realtime errors.

## Deliberate long-answer interruption

- Fixed long answer requested at 7783 ms.
- Response created at 7983 ms and its output item arrived at 8442 ms.
- User speech was detected at 12171 ms.
- The old output audio finished at 12198 ms.
- The old response reported `status=cancelled` at 12199 ms.

The protocol therefore stopped/cancelled the old response about 27-28 ms after speech-start detection, then created a response for the user turn. A later response completed normally.

## Interpretation boundary

The report's `speechDuringAssistant=0` is a probe-observability limitation, not contrary evidence. Browser WebRTC carries output audio on the remote media track, while this run did not receive continuous `response.output_audio.delta` events on the data channel. The probe's delta-based boolean therefore did not model actual remote-track playout duration. The response cancellation event and timing are the authoritative protocol evidence.

Two response cancellations were observed. The first is the deliberate long-answer interruption. The second followed a new response by 86 ms and could be a split VAD utterance, continued user speech, residual speaker audio, or another intentional utterance; the sanitized event report alone cannot distinguish these. Consequently:

- user barge-in and prompt protocol cancellation: accepted;
- browser capture processing activation: accepted;
- absence of speaker self-echo false interruptions under all conditions: not claimed;
- production session/wake gating and longer repeated real-device trials: follow-up architecture and acceptance work.

No raw audio, transcript, API key, ephemeral token, or base64 audio delta is stored in this record.
