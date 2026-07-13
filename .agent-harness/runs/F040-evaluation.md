# F040 Evaluation

Date: 2026-07-13

The first cold-start evaluation rejected F040 in the `implementation_gap` domain. Successful ACK drain metrics and focused tests passed, but failure paths did not emit the required drain metrics/failure state, and state-machine tests did not prove that microphone-read or playback-wait failures still join the playback handle without leaving an orphan.

Evaluator result:

```text
EVAL_FAIL: F040: ACK drain failure handling does not log the required drain metrics/failure state, and tests cover only successful state-machine drain; playback/read/wait failure and no-orphan behavior are not verified. Focused 44 tests and ./init.sh (196 tests) pass.
```

- Failure domain: implementation_gap
- Harness improvement: no harness runtime change is required; future audio-lifecycle evaluator checklists should probe start, active-drain read, poll/wait, and cleanup failures in addition to the success path.
