# F053 fast coding evidence

FAST_CODING_EVIDENCE: F053
CODING_PASS: F053

## Implemented scope

- Added `BACKEND=pipeline|realtime` settings and CLI override while preserving pipeline as the default.
- Added conditionally validated Realtime model, voice, timeout, server-VAD, input-transcription, acknowledgement, debug, end-phrase, and loopback bridge settings. Inactive invalid Realtime values do not break pipeline loading.
- Added typed `WAIT_WAKE -> CONNECTING -> ACTIVE_SESSION -> CLOSING` contracts, bounded host command/event enums, and a loopback-only single-session bridge.
- Added raw-PCM, secret, stale identity, malformed value, event ordering, nesting, item-count, and 4KB payload rejection.
- Added deterministic fake clock/host boundaries and backend-specific diagnostics without live microphone, browser, WebRTC, speaker, or OpenAI activity.
- Documented all opt-in defaults and the fail-closed F053/F054 boundary.

## Verification

- Focused config/CLI/contract/documentation tests passed (13 tests in the final focused run).
- `.venv/bin/python -m src.main --backend realtime --diagnose` reported distinct host-assets, model/voice, credential, loopback, and audio-handoff checks without printing secret values or opening live media.
- Final `./init.sh` passed with 243 project tests, dry-run smoke, fake pipeline smoke, and project recovery verification.

The coding phase does not set `EVAL_PASS`, `passes=true`, or `status=done`; those remain evaluator-owned.
