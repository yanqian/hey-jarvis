# F057 real-device acceptance

Date: 2026-07-17 (Asia/Singapore)

## Environment and privacy

- macOS built-in microphone and built-in speakers; no headphones.
- Project-selected Chrome app-mode WebRTC host on loopback, armed once before the five accepted cycles.
- Model `gpt-realtime-2.1`, voice `marin`, direct browser playback gain `0.1`, server-VAD threshold `0.8`.
- Every accepted session began with the private saved wake fixture crossing the real local Hey Jarvis detector, not `/api/simulate-wake`.
- Each session replayed two private user-question fixtures, one calculator fixture, one deliberate barge-in fixture over a requested long answer, and one end-phrase fixture before proving fresh wake ownership. The recordings, transcripts, credentials, full session ids, and raw/base64 audio remain Git-ignored and are not included here.

## Pre-acceptance defect and mitigation

At direct playback gain `1.0`, a fresh-host run reproduced speaker self-echo: a second `speech_started` arrived 1,569 ms after `response.created`, and the normal answer was cancelled 26 ms later even though no next fixture was playing. Gains `0.5`, `0.3`, and `0.1` with the stock `0.5` server-VAD threshold also produced intermittent false starts. Repeated runs were rejected rather than counted.

The accepted quiet profile combines direct browser `<audio>` gain `0.1` with server-VAD threshold `0.8`. The gain does not re-encode audio or route it through Python. The threshold is the documented Realtime activation threshold: increasing it rejects quieter residual echo while the recorded user and barge-in fixtures prove intended speech still activates.

## Five accepted cycles

All cycles used `echoCancellation=true`, `noiseSuppression=true`, `autoGainControl=true`, 48 kHz mono capture, output gain `0.1`, server-VAD threshold `0.8`, and no second Arm click. The runner hard-fails unless each session has exactly five `speech_started` events, matching the five intended fixtures.

| Cycle | Wake-to-connected | Intended speech starts | Calculator calls | Self-echo false starts | Deliberate barge-in | Errors | Exit / wake restored |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1 | 2,070 ms | 5 | 1 | 0 | 118 ms | 0 | end phrase / yes |
| 2 | 2,649 ms | 5 | 1 | 0 | 32 ms | 0 | end phrase / yes |
| 3 | 2,056 ms | 5 | 1 | 0 | 15 ms | 0 | end phrase / yes |
| 4 | 2,590 ms | 5 | 1 | 0 | 30 ms | 0 | end phrase / yes |
| 5 | 2,172 ms | 5 | 1 | 0 | 37 ms | 0 | end phrase / yes |

Every deliberate interruption cancelled the long response and produced a completed continuation. Each cycle recorded one calculator tool call, one end-phrase match, zero host errors, and exactly five intended speech starts. After every teardown the coordinator reported `wake_owned`, `wake_microphone_open=true`, and the following cycle reached ACTIVE_SESSION through a fresh saved wake fixture. The Chrome microphone indicator cleared between sessions.

The runner associates each answer with the `response.created` that owns it instead of relying on a global `response.done` count. This matters because a saved follow-up can begin while the previous browser audio buffer is draining; that intentional overlap may add a cancellation for the old response but cannot be misclassified as the new answer or an unexplained speech start.

## Boundary

This evidence proves the tested Mac, placement, system output setting, `0.1` browser gain, and `0.8` VAD threshold. It does not claim universal acoustic behavior. A deployment that changes speaker volume, device, room, gain, or threshold must repeat M057; a normal answer that cancels itself or any unexplained sixth speech start is a failed cycle, not successful barge-in.
