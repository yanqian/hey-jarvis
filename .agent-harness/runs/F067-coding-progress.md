# F067 coding progress

## Scope

- Measurement only: no Realtime ordering, acknowledgement, wake, model, VAD,
  output, timeout, or user-turn behavior was optimized or retuned.
- Added coordinator-clock markers for confirmed wake, acknowledgement start and
  completion, and handoff queueing.
- Added one browser-monotonic, rounded, batched timing report for command
  dispatch, ephemeral-token acquisition, microphone acquisition, peer/SDP
  setup, WebRTC negotiation, session configuration, and total browser ready.
- Extended RT001 version 2 to validate, sanitize, and report end-to-end and
  phase timings while preserving exclusive ownership and cleanup oracles.

## Verification

```text
node --check src/realtime_host/static/app.js
python3 -m unittest tests.test_realtime_handoff_eval tests.test_realtime_controller tests.test_realtime_host tests.test_documentation
51 tests passed
python3 -m unittest discover -s tests -p 'test_*.py'
337 tests passed
python3 -m src.realtime.fake_smoke
passed
```

## Remaining

- The newly authorized automatic RT001 live-host run passed and produced the
  bounded breakdown recorded in `.agent-harness/runs/F067-live-rt001.md`.
- Final recovery verification and fast coding evidence are complete.
- Separate cold-start evaluator approval remains pending.
- F067 remains `in_progress` and `passes=false`.
