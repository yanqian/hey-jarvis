# F041 Coding Retry

Date: 2026-07-13

The retry addresses the first evaluator's synchronization-trust finding without expanding beyond F041:

- A completed asynchronous ACK drain is synchronized only when its drain metrics contain zero microphone overflow chunks.
- Every success/failure drain summary now includes `synchronized=true|false`.
- Completed drains with overflow return `synchronized=false`, so the state machine runs the existing bounded quiet-boundary fallback instead of live handoff.
- A regression drives wake, asynchronous ACK drain with overflow, quiet fallback, ARMED speech, and the answer loop; it verifies fallback suppression and `post_ack_synchronized=false`.
- Immediate-prefix, tail-only cancellation, optional-VAD, and five-loop synchronized tests remain passing on zero-overflow drains.
- Final `./init.sh` passes with 203 project tests, dry-run, and fake-backend smoke.

FAST_CODING_EVIDENCE: F041
CODING_PASS: F041
