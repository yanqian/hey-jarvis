# F079 Fast Coding and Live Evidence

Feature: F079 - Reduce acknowledgement playback overhead

Date: 2026-07-28 to 2026-07-29
Result: Coding, target-Mac A/B, and user-led Realtime acceptance complete

## Implementation

- Added an acknowledgement-only `MacOSPlayer` path that reads the positive
  bounded `afinfo` duration and invokes `afplay -t` with that exact value.
- Pipeline acknowledgement drain prefers the bounded start method. Realtime
  local acknowledgement playback waits for the same bounded process to finish
  before recording `ack_completed` and enabling browser input.
- Normal answer playback still uses the original unbounded `afplay` command.
- The benchmark now runs legacy and bounded modes on the same asset and reports
  per-mode observable phases plus the bounded-minus-legacy median wall
  difference. Acoustic onset remains unmeasured and `slo=unset`.

## Target-Mac A/B

Command:

```bash
python -m src.main --benchmark-acknowledgement --benchmark-iterations 3
```

Asset duration: 480 ms.

| Mode | Median start call | Median process lifetime | Median total wall | Median derived overhead |
| --- | ---: | ---: | ---: | ---: |
| legacy | 3 ms | 1,375 ms | 1,378 ms | 898 ms |
| bounded | 24 ms | 611 ms | 635 ms | 155 ms |

The bounded-minus-legacy median total-wall difference was -743 ms on this
sample. This establishes only the observed target-Mac process-lifecycle
difference; it does not measure acoustic onset or create an SLO.

## Offline verification

- Focused player, main, state-machine, Realtime controller/host, and
  documentation tests passed.
- Tests prove exact `-t 0.480` construction, bounded-path selection for
  acknowledgement, unchanged legacy path for normal playback, comparison
  output, process failures, input-ready ordering, and cleanup recovery.
- Final `./init.sh` passed: harness verification, 378 project tests, dry-run,
  pipeline fake smoke, and Realtime fake smoke.
- `git diff --check` passed.

## Human and Realtime acceptance

- The user confirmed the final three bounded A/B plays were complete, clear,
  and not truncated.
- On 2026-07-29 the user explicitly authorized Mac microphone audio
  transmission to OpenAI for the F079 Realtime check.
- Chrome reported 48 kHz mono input with echo cancellation, noise suppression,
  and automatic gain control all active.
- The session reached configured readiness before the bounded acknowledgement
  completed, and browser input became ready only after completion.
- One post-cue user utterance produced one normal audible answer.
- The user's semantic ending produced `reason=end_phrase`; browser media
  stopped, the UI reported `Python wake microphone restored`, and Python
  recorded `recovered_to_wake=true`.
- Evidence retains only bounded lifecycle and human verdicts; no audio,
  transcript, answer, credential, provider body, or tool arguments are stored.

FAST_CODING_EVIDENCE: F079
CODING_PASS: F079

Separate cold-start evaluator approval remains required.
