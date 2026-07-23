# F063 coding progress

- Selected through evaluator-gated `work-fast` handoff.
- Added a versioned RT002 scenario with zero routine human actions, one-time
  private wake/turn fixture setup, offline and fixture-replay evidence tiers,
  same-session continuity oracles, bounded cleanup, and strict content
  exclusions.
- Added an automatic runner that verifies fixture integrity, replays wake,
  waits for one fresh connection, replays turn 1 and waits for its response,
  replays turn 2 and waits for its response under the same session identity,
  then stops and proves fresh wake ownership.
- Added deterministic failures for missing or changed fixtures, duplicate or
  wrong-session connections, early/missing/extra speech, cancelled response,
  intervening close, response timeout, and cleanup timeout.
- Added offline CLI and operator documentation stating that routine runs need
  no fresh speech and judge lifecycle continuity rather than transcript or
  answer semantics.
- Focused RT002/shared-runner/RT003/documentation tests pass with 48 tests.
- Full project discovery passes with 321 tests.
- Python compile, pipeline fake smoke, Realtime fake smoke, and final
  `./init.sh` recovery pass.
- No microphone, browser, network, OpenAI request, or billable live session was
  used during this coding phase.

F063 remains in progress. Its acceptance requires a newly and explicitly
authorized built-in-device `fixture_replay` execution. Do not infer permission
from the earlier F062 authorization. After the live result is recorded, add
the required fast coding markers and invoke the separate cold-start evaluator.
