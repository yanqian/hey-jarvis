# F076 Fresh-Restart Five-Session Follow-up

Feature: F076 - Attribute post-answer Realtime and acknowledgement latency

Date: 2026-07-28
Result: Follow-up live evidence after `EVAL_PASS: F076`

## Purpose

The original three-session sample came from a service and Chrome page that had
been running for a long time. This follow-up fully stopped the Python
Realtime service, verified no old Realtime or evaluator process remained,
started a new service process, loaded a fresh host page, armed it once, and
collected five consecutive manual wake sessions. The goal was to test whether
the earlier 1,053–3,124 ms DataChannel-open range reproduced after restart.

## Environment and privacy

- Mac built-in microphone and speakers
- New Python service process
- Freshly loaded Chrome app-mode host page, armed once
- Existing unified WebRTC call
- Current local `嗯` acknowledgement
- Far-field input noise reduction and local output volume 0.3
- Each session ended through the semantic end-conversation tool
- Bounded sanitized lifecycle report only
- No audio, transcript text, answer text, credentials, SDP, ICE, provider
  bodies, or private raw logs are retained

## Five sessions

| Session | Negotiation | DataChannel open | After-open `session.created` | Readiness total | ACK asset | ACK wall | Derived ACK overhead | Wake to configured | Wake to input ready |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 419 ms | 696 ms | 169 ms | 865 ms | 480 ms | 1,362 ms | 882 ms | 1,660 ms | 3,121 ms |
| B | 509 ms | 690 ms | 170 ms | 860 ms | 480 ms | 1,362 ms | 882 ms | 1,865 ms | 3,346 ms |
| C | 796 ms | 685 ms | 167 ms | 852 ms | 480 ms | 1,375 ms | 895 ms | 1,948 ms | 3,423 ms |
| D | 828 ms | 680 ms | 169 ms | 849 ms | 480 ms | 1,359 ms | 879 ms | 2,166 ms | 3,645 ms |
| E | 823 ms | 760 ms | 170 ms | 930 ms | 480 ms | 852 ms | 372 ms | 2,131 ms | 3,011 ms |
| Median | 796 ms | 690 ms | 169 ms | 860 ms | 480 ms | 1,362 ms | 882 ms | 1,948 ms | 3,346 ms |

All five sessions:

- used zero command-to-token and token phases;
- reconciled DataChannel-open plus post-open `session.created` exactly to the
  readiness aggregate;
- emitted no user-turn event before `host_connected`;
- completed the semantic end flow;
- stopped browser media before reopening the wake microphone; and
- restored `wake_owned` with the wake microphone open.

## Comparison with the earlier long-running process

| Sample | Sessions | Median DataChannel open | Median post-open `session.created` | Median readiness total | Median ACK wall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Earlier long-running process/page | 3 | 2,702 ms | 0 ms | 2,702 ms | 1,366 ms |
| Freshly restarted service/page | 5 | 690 ms | 169 ms | 860 ms | 1,362 ms |

The fresh sample returned to the same approximately 850–860 ms readiness range
seen in F075 and stayed tight across all five sessions. The difference is
almost entirely DataChannel establishment; ACK median wall time is effectively
unchanged.

This supports treating the earlier 2.7–3.1 second DataChannel values as a
state- or network-dependent slowdown rather than the normal steady value. It
does not prove that service age alone caused the slowdown because restart time,
browser page state, network conditions, and provider conditions changed
together.

## Product implication

The new sample strengthens the attribution but does not make transport-time
ACK overlap fail-safe. A restart produced a stable 849–930 ms readiness
interval and the median ACK lasted longer, but the earlier accepted sample
still proves that DataChannel establishment can exceed ACK playback by more
than one second. Under the selected contract, hearing `嗯` must continue to
mean input is ready. F077 therefore still requires product-contract
reconciliation or a different architecture; the safe next optimization is
F078's reproducible low-overhead ACK path without opening input early.
