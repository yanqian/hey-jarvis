# Run Record: F037 - coding retry after evaluator failure

## Evaluator feedback

The first evaluation rejected recorder endpointing because VAD-low audio accumulated silence even when RMS remained above the configured silence threshold. That contradicted the normalized requirement that final endpoint silence must be both RMS-low and VAD-low.

## Retry

- VAD-enabled endpoint quiet now requires `rms <= silence_threshold` and `vad_ratio <= vad_end_ratio`.
- The non-voice stop regression uses moderate sub-threshold noise with VAD ratio 0.0.
- A new high-RMS/VAD-low regression proves high energy is not mislabeled as silence and reaches the max-duration safety outcome.
- Focused retry coverage passed with 98 tests; final `./init.sh` passed with 188 project tests, dry-run, and fake-backend smoke.
- Failure domain: implementation_gap
- Harness improvement: none required; the normalized SPEC and evaluator gate caught the product logic mismatch.

FAST_CODING_EVIDENCE: F037
CODING_PASS: F037
