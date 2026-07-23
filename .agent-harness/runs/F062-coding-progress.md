# F062 coding progress

- Selected through evaluator-gated `work-fast` handoff.
- Added the backward-compatible generic Realtime scenario boundary with the
  four agreed evidence tiers.
- Added versioned RT001, shared injected request/clock/play/poll/cleanup
  machinery, automatic saved-wake live runner, offline oracle, bounded
  sanitized PASS/FAIL evidence, and CLI/documentation.
- Deterministic coverage includes missing, stale, wrong-session, duplicated,
  misordered, timeout, stop-failure, and cleanup-defect cases.
- Focused RT001/RT003/documentation tests pass.
- Full project discovery passes with 308 tests.
- Python compile, Realtime fake smoke, and final `./init.sh` recovery pass.
- No microphone, browser, network, OpenAI request, or billable live session was
  used during this coding phase.

F062 remains in progress. Its acceptance requires a newly and explicitly
authorized built-in-device `live_host` execution. Do not infer that permission
from earlier F060/F061 authorizations. After the live result is recorded, add
the required fast coding markers and invoke the separate cold-start evaluator.
