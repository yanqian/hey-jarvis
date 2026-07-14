# F046 Fast Coding Evidence

Date: 2026-07-13

FAST_CODING_EVIDENCE: F046
CODING_PASS: F046

## Implementation

- Added `requirements-vad.txt` with `webrtcvad==2.0.10` and `setuptools<81`, matching the captured F037 compatibility evidence.
- Replaced WebRTC module-discovery diagnostics with the production `build_vad_detector` boundary, configured `VAD_MODE`, and a real 20ms mono int16 silence-frame classification.
- Preserved lazy optional behavior when `VAD_BACKEND=disabled` and added actionable, root-cause-preserving failures for import, construction, and classification errors.
- Updated setup/troubleshooting documentation and recovery required-file checks.

## Verification

- `python3 -m unittest tests.test_vad tests.test_config tests.test_documentation`: 31 tests passed.
- `python3 -m unittest discover -s tests`: 215 tests passed.
- `./init.sh`: passed with 215 project tests, dry-run, and fake-backend smoke.
- Real optional-runtime probe under `.venv/bin/python` (Python 3.12, setuptools 80.10.2): detector constructed and classified one frame with `voiced=0`.
- `VAD_BACKEND=webrtc .venv/bin/python -m src.main --diagnose`: exited 0 and reported `dependency:webrtcvad` OK after import, construction, and 20ms classification.
- System Python without the optional package failed closed with the `requirements-vad.txt` installation command.

The real classifier probe proves installation/runtime compatibility only. It does not resolve the separate Recording VAD real-audio accuracy issue.
