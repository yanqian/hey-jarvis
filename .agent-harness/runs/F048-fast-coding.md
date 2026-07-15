# F048 Fast Coding Evidence

Date: 2026-07-15

FAST_CODING_EVIDENCE: F048
CODING_PASS: F048

## Implementation

- Recording VAD now requires both speech-level RMS and configured VAD speech evidence before a chunk can reset end silence or refresh hangover.
- Sustained RMS at or below `RECORDING_SILENCE_RMS` advances the existing tolerant end-silence window even when WebRTC remains falsely voiced.
- High-RMS/VAD-low audio remains non-quiet, maximum-duration safety and VAD-disabled behavior are preserved, and `RECORDING_VAD_END_RATIO` remains the disagreement-diagnostic boundary.
- A single `recording_endpoint` summary logs the stop reason and low-energy/high-VAD disagreement count without raw audio or per-chunk spam.
- README and manual testing define the algorithm and the five-question Python 3.12 real-device gate before any future default enablement.

## Verification

- `python3 -m unittest tests.test_recorder tests.test_state_machine tests.test_documentation`: 64 tests passed.
- `python3 -m unittest discover -s tests`: 221 tests passed.
- `git diff --check`: passed.
- `./init.sh`: passed with harness checks, 221 project tests, dry-run, and fake-backend smoke.
- Synthetic regression: normal energetic/VAD-confirmed speech followed by low-RMS `vad_ratio=1.0` stops by silence after hangover plus the configured window and records the disagreement metric.

Real-device acceptance remains intentionally pending; `RECORDING_VAD_ENABLED=0` stays the default until the documented five-question trial passes.
