# F076 Fast Coding and Live Evidence

Feature: F076 - Attribute post-answer Realtime and acknowledgement latency

Date: 2026-07-28

FAST_CODING_EVIDENCE: F076
CODING_PASS: F076

## Offline implementation and verification

- Browser timing now splits `session_configuration_ms` into
  `data_channel_open_ms` and
  `session_created_after_data_channel_open_ms`.
- Both the coordinator sanitizer and evaluation oracle require the two
  readiness subphases to reconcile exactly to the aggregate.
- RT001 version 8 records the prepared acknowledgement asset duration,
  acknowledgement wall time, and derived player/device overhead separately.
- `afinfo` behavior was verified on the target Mac. The current `var/ack.mp3`
  reports 480 ms. Independent decoded inspection found about 413 ms of audio
  with about 82 ms total leading and trailing silence; this inspection is
  diagnostic and no audio is committed.
- Focused tests, JavaScript syntax, full discovery with 351 project tests,
  pipeline fake smoke, Realtime fake smoke, and final `./init.sh` pass.

## Live target-Mac evidence

Environment:

- Mac built-in microphone and speakers
- Chrome app-mode host armed once
- Existing unified WebRTC call
- Current local `嗯` acknowledgement
- Far-field input noise reduction and local output volume 0.3
- Bounded sanitized lifecycle report only

Three manually wake-triggered sessions were observed. No audio, transcript
text, answer text, credentials, SDP, ICE, provider bodies, or private raw logs
are retained here.

| Session | DataChannel open | After-open `session.created` | Readiness total | ACK asset | ACK wall | Derived ACK overhead | Wake to configured | Wake to input ready | Outcome |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A | 1,053 ms | 176 ms | 1,229 ms | 480 ms | 900 ms | 420 ms | 3,880 ms | 4,935 ms | Idle close |
| B | 2,702 ms | 0 ms | 2,702 ms | 480 ms | 1,400 ms | 920 ms | 4,730 ms | 6,321 ms | Normal turns, interruption, semantic end |
| C | 3,124 ms | 0 ms | 3,124 ms | 480 ms | 1,366 ms | 886 ms | 5,212 ms | 7,561 ms | Idle close |

All three sessions:

- used zero command-to-token and token phases;
- reconciled both readiness subphases exactly;
- recorded the 480 ms asset separately from playback wall time;
- emitted no user-turn activity before `host_connected`;
- stopped browser media before reopening the wake microphone; and
- ended with `state=wake_owned`, `wake_microphone_open=true`, and no active
  session.

The first automatic saved-wake attempt was excluded because the wake fixture
did not produce `wake_confirmed`, matching the previously observed fixture
recognition limitation. It never entered `/session`, was not a Realtime
readiness failure, and left wake ownership intact.

## Finding and F077 implication

The earlier aggregate label “session-created wait” was misleading. In these
three sessions, 1,053–3,124 ms elapsed before DataChannel open, while the
subsequent `session.created` delivery took only 0–176 ms.

Starting the ready acknowledgement immediately after SDP/transport would
therefore be unsafe under the selected two-stage contract. In sessions B and
C, the 900–1,400 ms acknowledgement could finish more than one second before
configured readiness. A user speaking after the audible cue would still find
the outgoing track disabled. F077 must not implement that ordering unless the
product contract changes or pre-ready speech buffering is added; both are
currently excluded.

This is bounded target-Mac evidence, not a production percentile or SLO.
