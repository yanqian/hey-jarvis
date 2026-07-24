# F070 Fast Coding Evidence

Feature: F070 - Keep Realtime input-level diagnostics off the normal critical path

FAST_CODING_EVIDENCE: F070

## Implementation

- Ordinary browser start commands omit input-level diagnostics and skip
  `AudioContext`, analyser, media-stream-source, sampling, and level events.
- A loopback control endpoint arms input-level monitoring for exactly the next
  wake-owned handoff. The coordinator atomically consumes the flag and includes
  only literal `input_level_diagnostics=true` on that start command.
- F060 requests the one-shot capability before playing its private wake fixture;
  its existing bounded level monitoring and cleanup path are unchanged.
- RT001 is version 5 and rejects any normal-path run whose audio-analysis
  aggregate or six nested subphases are non-zero.

## Offline Verification

- `python3 -m unittest tests.test_realtime_host tests.test_realtime_input_diagnosis tests.test_realtime_handoff_eval tests.test_realtime_close_recovery_eval tests.test_documentation`
  - PASS: 65 tests.
- `python3 -m unittest discover -s tests -p 'test_*.py'`
  - PASS: 341 tests.
- `node --check src/realtime_host/static/app.js`
  - PASS.
- `python3 -m src.realtime.fake_smoke`
  - PASS: exclusive handoff, connection, two turns, barge-in, tool output,
    farewell close, and wake recovery.
- `git diff --check`
  - PASS.

## Remaining Acceptance

One freshly authorized RT001 live-host run is still required to prove that the
real normal browser path reports zero audio-analysis timings, connects, cleans
up, and restores wake ownership. No microphone or OpenAI live call was made
during this coding run.

CODING_PASS: F070
