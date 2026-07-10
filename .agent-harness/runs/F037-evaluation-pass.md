# Evaluation Pass: F037 - Add optional VAD-gated audio handling

## Result

Cold-start re-evaluation verified the normalized SPEC, acceptance criteria, implementation, quality rubric, prior failure evidence, and coding retry evidence.

- `src/recorder.py` now accumulates final VAD-enabled silence only when both RMS is at or below `silence_threshold` and VAD ratio is at or below `vad_end_ratio`.
- The RMS-low/VAD-low regression stops with `stopped_by="silence"`.
- The new high-RMS/VAD-low safety regression does not classify the input as silence and reaches `stopped_by="max_duration"`.
- `python3 -m unittest tests.test_config tests.test_vad tests.test_state_machine tests.test_recorder tests.test_wake_word tests.test_main tests.test_documentation` passed 98 tests.
- Final `./init.sh` passed harness verification, 188 project tests, dry-run, and fake-backend smoke coverage.
- `git diff --check` passed.

EVAL_PASS: F037
