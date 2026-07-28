# F077 Fast Coding and Target-Mac Playback Evidence

Feature: F077 - Measure acknowledgement playback lifecycle

Date: 2026-07-28
Result: Coding complete; separate evaluator approval required

FAST_CODING_EVIDENCE: F077

## Implementation

- Added a bounded `--benchmark-acknowledgement` CLI mode with independently
  validated `--benchmark-iterations` from 1 through 20.
- The benchmark measures the acknowledgement metadata duration once, then
  records monotonic `afplay` process-start call time, process lifetime, total
  wall time, and the derived wall-minus-asset difference for every trial.
- The first trial is labelled only as a cold candidate and later trials as
  warm candidates. Output explicitly records `acoustic_onset=unmeasured`.
- Output retains no asset path, audio content, transcript, answer, credential,
  SDP, ICE, or provider payload.
- Active Realtime acknowledgement order, configured-session readiness, input
  gate, microphone ownership, and cleanup are unchanged.

## Offline verification

- Focused player tests use fake clocks and processes to prove exact phase
  attribution, medians, iteration bounds, backwards-clock rejection, and
  rejection when wall time is inconsistent with asset metadata.
- CLI tests prove dispatch, bounded privacy-safe output, and explicit unknown
  acoustic onset.
- Documentation describes the command and prevents derived overhead from being
  described as playback-start latency.

## Target-Mac evidence

The first sandboxed attempt was excluded because macOS rejected audio-device
creation with `AudioQueueNew failed ('fmt?')`. The same command was rerun with
authorized local audio-output access and completed normally. No Realtime
session, microphone, network, or OpenAI call was used.

Command:

```bash
python3 -m src.main --benchmark-acknowledgement --benchmark-iterations 5
```

Current asset metadata duration: 480 ms.

### Sample A

| Trial | Process-start call | Process lifetime | Total wall | Derived overhead |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 1 ms | 1,369 ms | 1,370 ms | 890 ms |
| 2 | 5 ms | 1,362 ms | 1,367 ms | 887 ms |
| 3 | 2 ms | 1,351 ms | 1,353 ms | 873 ms |
| 4 | 3 ms | 857 ms | 860 ms | 380 ms |
| 5 | 5 ms | 1,373 ms | 1,378 ms | 898 ms |

Median: process-start call 3 ms, process lifetime 1,362 ms, total wall
1,367 ms, derived overhead 887 ms.

### Sample B

| Trial | Process-start call | Process lifetime | Total wall | Derived overhead |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 1 ms | 1,358 ms | 1,359 ms | 879 ms |
| 2 | 5 ms | 1,373 ms | 1,378 ms | 898 ms |
| 3 | 5 ms | 1,363 ms | 1,368 ms | 888 ms |
| 4 | 4 ms | 1,365 ms | 1,369 ms | 889 ms |
| 5 | 5 ms | 855 ms | 860 ms | 380 ms |

Median: process-start call 5 ms, process lifetime 1,363 ms, total wall
1,368 ms, derived overhead 888 ms.

Across all ten trials, the process-start call was 1–5 ms. Eight trials had
873–898 ms derived overhead and two had 380 ms. This rules out Python
subprocess creation as the material source of the approximately 0.88-second
difference. The difference occurs while `afplay` remains alive, but these
measurements cannot divide that lifetime among decode, output-device setup,
buffering, audible playback, drain, or process shutdown. Acoustic onset remains
unmeasured.

CODING_PASS: F077
