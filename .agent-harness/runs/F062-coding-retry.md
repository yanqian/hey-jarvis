# F062 Coding Retry

FAST_CODING_EVIDENCE: F062

## Evaluator Finding

The first cold-start evaluator correctly rejected F062 because the offline
oracle strictly validated the final lifecycle but allowed an active snapshot
whose `host_connected` belonged to another session or appeared twice.

## Correction

- The active snapshot now uses the same exact-count, active-session, and
  ordered-lifecycle validation as the final report.
- Active microphone request, acquisition, and connection events must all use
  the observation's one session identity.
- Added direct regressions for active-snapshot wrong-session
  `host_connected` and duplicated `host_connected`.
- The evaluator's two reproduced malformed observations now fail precisely.

## Verification

- Focused RT001/RT003/documentation tests: 36 passed.
- Full project discovery through final `./init.sh`: 309 passed.
- Realtime fake smoke and project recovery: passed.
- The previously recorded authorized RT001 live-host PASS remains valid
  because its active and final reports already contain one correctly ordered
  lifecycle under one fresh session identity.

CODING_PASS: F062
