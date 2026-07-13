# F040 Coding Retry

Date: 2026-07-13

The retry addresses the first evaluator's implementation-gap findings without expanding beyond F040:

- ACK drain now emits the same bounded metrics for success and failure, with explicit `completed=true|false` and `failure_stage=start|drain|wait|none` fields.
- A microphone read or handle poll failure joins the playback handle exactly once before propagating the original failure; a secondary join error is logged without hiding the original drain failure.
- A playback wait failure records `failure_stage=wait` before propagation.
- State-machine regressions verify microphone-read failure joins the handle, wait failure is attempted once, both paths log failure metrics, and the success path still joins once.
- Focused player/state-machine verification passes with 46 tests.
- Final `./init.sh` passes with 198 project tests, dry-run, and fake-backend smoke.

FAST_CODING_EVIDENCE: F040
CODING_PASS: F040
