# F064 coding progress

- Selected through evaluator-gated `work-fast` handoff.
- Normalized the previously missing RT004 specification before implementation,
  including goals, scope, flows, constraints, assumptions, capabilities,
  implementation paths, and verification surface.
- Added a versioned RT004 scenario with zero routine human actions, offline and
  live-host evidence tiers, two distinct wake-triggered sessions, ordered
  browser stop/Python microphone reopen oracles, bounded final recovery, and
  strict content exclusions.
- Added an automatic runner that replays the same private wake twice around two
  explicit stops, proves exactly one fresh connection per cycle, rejects reused
  session identity, and evaluates sanitized lifecycle snapshots through the
  same fail-closed oracle used offline.
- Added deterministic failures for missing, duplicated, stale, or misordered
  lifecycle evidence; concurrent microphone ownership; second connection
  failure; either cleanup timeout; and reused identity.
- Added CLI and operator documentation stating that routine RT004 runs need no
  fresh speech and judge media ownership/lifecycle rather than transcript or
  response semantics.
- Focused RT001-RT004/shared-runner/documentation tests pass with 58 tests.
- Full project discovery and final `./init.sh` recovery pass with 332 project
  tests.
- No microphone, browser, network, OpenAI request, or billable live session was
  used during this coding phase.

F064 remains in progress. Its acceptance requires a newly and explicitly
authorized built-in-device `live_host` execution. Do not infer permission from
the earlier F063 authorization. After the live result is recorded, add the
required fast coding markers and invoke the separate cold-start evaluator.
