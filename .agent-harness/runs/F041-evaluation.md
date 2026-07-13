# F041 Evaluation

Date: 2026-07-13

The first cold-start evaluation rejected F041 in the `implementation_gap` domain. `_play_wake_acknowledgement()` returned only `True` after every completed asynchronous drain, even when its own metrics recorded microphone overflow. That allowed the synchronized path to skip conservative quiet suppression despite the normalized requirement that overflow/stale synchronization fall back safely. Existing tests did not cover the required overflow fallback.

- Failure domain: implementation_gap
- Harness improvement: no harness runtime change is required; evaluator checklists for trusted handoff signals should inject contradictory telemetry such as a nominally completed operation that also reports overflow or data loss.

EVAL_FAIL: F041: completed asynchronous ACK drain with overflow was treated as synchronized and bypassed the required conservative fallback
