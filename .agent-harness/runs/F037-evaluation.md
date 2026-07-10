# Evaluation: F037 - Add optional VAD-gated audio handling

## Result

F037 does not satisfy its normalized recorder endpointing contract.

The normalized SPEC says that only audio which is both RMS-low and VAD-low may accumulate the final quiet window, and the feature acceptance criterion likewise requires sustained RMS-low/VAD-low non-voice before stopping. In `src/recorder.py`, however, the VAD-enabled path computes `quiet` solely from `vad_ratio <= vad_end_ratio` and ignores RMS. Consequently, sustained high-RMS audio classified as non-voice is accumulated as quiet and stops the recording; `test_recorder_vad_stops_on_non_voice_noise` explicitly locks in this contradictory behavior with RMS 1800 input.

Recovery verification otherwise passed: `./init.sh` completed successfully with 187 project tests, dry-run, and fake-backend smoke coverage, and `git diff --check` passed.

- Failure domain: implementation_gap
- Harness improvement: no harness change required; the normalized requirement and evaluator gate correctly identified a product endpointing mismatch for coding retry.

EVAL_FAIL: F037: VAD-enabled recorder endpointing ignores the required RMS-low condition and stops on sustained high-RMS/VAD-low noise, contrary to the normalized SPEC and acceptance criterion.
