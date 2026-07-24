# F068 coding progress

## Scope

- Measurement only: no Realtime ordering, ICE configuration, acknowledgement,
  wake, model, voice, VAD, output, timeout, session, or user-turn behavior was
  optimized or retuned.
- Retained the F067 `peer_setup_ms` aggregate and split it into microphone
  reporting, audio-analysis setup, PeerConnection/track/data-channel setup,
  `createOffer`, and `setLocalDescription`.
- Advanced RT001 to version 3 with bounded privacy allowlists and independent
  reconciliation of the top-level browser-ready phases and nested peer setup
  phases, avoiding double-counting.

## Verification

```text
node --check src/realtime_host/static/app.js
python3 -m unittest tests.test_realtime_handoff_eval tests.test_realtime_host tests.test_documentation
45 tests passed
python3 -m unittest tests.test_realtime_two_turn_eval tests.test_realtime_close_recovery_eval tests.test_realtime_fixtures tests.test_realtime_fixture_runner
26 tests passed
python3 -m unittest tests.test_realtime_spec_eval
14 tests passed
python3 -m unittest discover -s tests -p 'test_*.py'
337 tests passed
python3 -m src.realtime.fake_smoke
passed
./init.sh
passed
```

## Remaining

- The newly authorized automatic F068/RT001 live-host run passed, produced the
  bounded five-subphase breakdown recorded in
  `.agent-harness/runs/F068-live-rt001.md`, and restored wake ownership.
- Record fast coding evidence, then run a separate cold-start Evaluator Agent.
- F068 remains `in_progress` and `passes=false`.
