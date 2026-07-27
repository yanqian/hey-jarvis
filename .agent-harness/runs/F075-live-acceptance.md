# F075 Unified Realtime Live Acceptance

Feature: F075 - Create configured Realtime sessions through one unified WebRTC call

Date: 2026-07-27
Result: PASS for the unified control plane and preserved F074 input gate

## Environment and privacy

- Mac built-in microphone and speakers
- One Chrome app-mode page, armed once
- `REALTIME_INPUT_NOISE_REDUCTION=far_field`
- Local `REALTIME_OUTPUT_VOLUME=0.3`
- User waited for “在呢” before speaking
- Evidence source: bounded sanitized loopback report
- No audio, transcript text, answer text, credential, SDP, ICE, request body,
  provider body, or private debug log is retained here

## Three real wake sessions

Every accepted session used exactly one local `POST /session`; the browser did
not request a client secret, send a direct authenticated OpenAI request, or
send `session.update`.

| Session | Wake to configured | Browser ready | Unified negotiation | Session-created wait | ACK | ACK end to input ready | First speech after input ready | Outcome |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A | 2,665 ms | 2,279 ms | 1,313 ms | 858 ms | 1,357 ms | 85 ms | 260 ms | Multiple turns, one cancelled response followed by completed continuation, semantic end |
| B | 2,081 ms | 1,379 ms | 405 ms | 864 ms | 1,351 ms | 245 ms | 390 ms | Completed answer, semantic end |
| C | 1,686 ms | 1,416 ms | 465 ms | 847 ms | 1,360 ms | 89 ms | 310 ms | Completed answer, bounded idle close |

For all three sessions:

- `command_to_token_ms=0`
- `token_ms=0`
- `audio_analysis_setup_ms=0`
- no `host_speech_started` occurred before `host_connected`
- the outgoing browser track remained closed until acknowledgement completion
- a post-acknowledgement user turn produced a completed answer
- browser media stopped before the Python wake microphone reopened

The final state was:

```text
state=wake_owned
wake_microphone_open=true
active_session=false
```

## Comparison with F074

F074 wake-to-configured values were 5,958 ms, 5,066 ms, and 2,494 ms
(median 5,066 ms). F075 values were 2,665 ms, 2,081 ms, and 1,686 ms
(median 2,081 ms), a 58.9% median reduction in this bounded same-device
comparison.

F075 browser-ready values had a 1,416 ms median. The removed token phases were
zero in every run, and the remaining post-answer `session.created` wait was
stable at 847-864 ms. These samples support the intended structural latency
reduction but do not establish a production percentile or SLO.

## Excluded diagnostic attempts

An automatic RT004 attempt never produced `wake_confirmed` from the saved wake
fixture and therefore never entered `/session`; it is not a unified-call
failure or an accepted latency sample. Two later direct `/api/simulate-wake`
diagnostic attempts were also excluded because that coordinator-only seam does
not invoke the Python acknowledgement controller and correctly failed closed.
Both paths restored wake ownership.

## Verdict

PASS. The unified interface removes the two token phases and the separate
post-connect session update without weakening F074's audible input-ready
contract, interaction behavior, privacy boundary, or cleanup.
