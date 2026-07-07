# F031 Manual Coding Evidence

## Context

Manual Coding Agent fallback for selected feature `F031` because this prompt was
run interactively rather than by the orchestrator adapter.

F031 addresses the loop observed after F030: transcript-level cancellation such
as `算了算了` correctly skips chat/TTS/playback, but the assistant immediately
returns to wake listening and can consume residual wake-positive audio or wake
detector state, replay acknowledgement, time out in `ARMED`, and repeat.

## Implementation

- Added post-cancellation wake suppression to local cancellation paths before
  logging wake readiness.
- Reused the existing post-playback cooldown, observed quiet, quiet RMS, and max
  suppression settings so no new runtime capability or configuration surface is
  required.
- Logged cancellation reason, discarded chunks, quiet-gate status, and maximum
  suppressed wake score for post-cancellation suppression.
- Preserved F029/F030 cancellation behavior: local cancellation still skips
  chat/tool routing, answer TTS, answer playback, and chat-history mutation.
- Added fake-audio regression tests for transcript cancellation with residual
  wake chunks followed by later intentional wake, and for ARMED no-speech
  cancellation with residual wake chunks.
- Updated README, DEPLOYMENT, MANUAL_TESTING, and documentation sync tests.

## Verification

```text
./init.sh
python3 -m py_compile src/state_machine.py
python3 -m unittest tests.test_state_machine tests.test_documentation
python3 -m unittest discover -s tests
```

Focused and full project unit tests passed before final recovery verification.
Final `./init.sh` passed after the evidence and progress updates.

## Evaluator Handoff

F031 is implemented but not marked complete by the Coding Agent. Evaluator
evidence with `EVAL_PASS: F031` is still required before `feature_list.json`
should be marked done.
