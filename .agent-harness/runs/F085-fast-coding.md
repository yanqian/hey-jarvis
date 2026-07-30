# F085 Fast Coding Evidence

FAST_CODING_EVIDENCE: F085
CODING_PASS: F085

## User-observed failure

The live sanitized report showed the final `host_response_done` at
`5436899234 ms` and the local `stop` command with `reason=idle_timeout` at
`5436914258 ms`, a 15.024-second gap matching the active
`REALTIME_IDLE_TIMEOUT_SECONDS=15` profile. The session was not a transport
failure and recovered wake ownership successfully. The report contained
playback-start evidence but no matching playback-stop evidence before the idle
close.

## Implementation

- Changed the checked-in and local Realtime idle profile from 15 to 60 seconds.
- Added coordinator playback-active state driven by the existing sanitized
  playback start/stop events.
- Kept maximum duration authoritative before the playback idle guard.
- Restarted the full idle window from playback-stop activity.
- Reset playback state at handoff start and cleanup.
- Updated configuration and Realtime lifecycle documentation.

## Verification

- `python3 -m unittest tests.test_realtime_config tests.test_realtime_host tests.test_realtime_controller tests.test_documentation`
  passed 64 tests.
- New deterministic coverage proves repeated playback starts are safe, idle
  timeout is suppressed during playback, playback stop grants a complete
  60-second window, fresh sessions do not inherit playback state, and a missing
  playback stop still reaches the 600-second maximum duration.
- `git diff --check` passed.
- `./init.sh` passed with 380 project tests, pipeline dry/fake smoke, and
  Realtime fake smoke.

## Boundaries

No live OpenAI call, browser permission, microphone, speaker, or billable
Realtime session was required for coding verification. F085 remains
`in_progress`; this coding record does not claim evaluator approval.
