# F052 fast coding evidence

FAST_CODING_EVIDENCE: F052
CODING_PASS: F052

## Implemented scope

- Added a production-path Chrome app-mode WebRTC host separate from the F051 spike.
- Added one-time host arming, loopback polling commands, ephemeral client-secret minting, and programmatic session start after a Python wake signal.
- Added an exclusive microphone handoff coordinator that closes the Python wake stream before browser capture and reopens it only after browser media teardown.
- Added sanitized bounded ordering/capability reports, a deterministic long-answer control, fail-closed error handling, and no WebSocket fallback.
- Documented the host choice, one-arm-per-launch lifetime, real-microphone command, dependency rationale, five-cycle procedure, known capability failures, and packaging deferral.

## Verification

- `node --check src/realtime_host/static/app.js`
- `.venv/bin/python -m unittest tests.test_realtime_host -v` (5 tests)
- `.venv/bin/python -m src.realtime_host.server --check`
- Real-device five-cycle exclusive-handoff run plus final no-autoplay-bypass built-in speaker/microphone interruption trial: `.agent-harness/runs/F052-real-device-acceptance.md`
- Final `./init.sh` project recovery verification passed with 234 project tests.

The coding phase does not set `EVAL_PASS`, `passes=true`, or `status=done`; those remain evaluator-owned.
