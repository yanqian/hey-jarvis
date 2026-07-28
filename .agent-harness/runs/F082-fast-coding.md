# F082 Fast Coding Evidence

## Result

FAST_CODING_EVIDENCE: F082

CODING_PASS: F082

F082 implementation and offline verification are complete. User-led live
acceptance and separate evaluator approval remain pending.

## Implementation

- Added one strict argument-free Realtime `local_time` function.
- Reused the existing time `ToolRoute`, `execute_route`, host-local timezone
  conversion, and injectable clock boundary.
- Kept calculator, weather, and semantic end-conversation behavior unchanged.
- Rejected model-controlled timezone/location fields and malformed or oversized
  arguments through the existing bounded tool-output path.
- Preserved session-scoped de-duplication, late/stale result rejection, and
  content-redacted lifecycle evidence.
- Extended the dependency-free Realtime fake smoke with deterministic `+08`
  local-time output.
- Added M082 operator guidance and updated the Realtime tool inventory.

## Verification

```bash
python3 -m unittest tests.test_realtime_host tests.test_documentation tests.test_tools
python3 -m src.realtime.fake_smoke
node --check src/realtime_host/static/app.js
python3 -m unittest discover -s tests
./init.sh
```

Results:

- 88 focused tests passed.
- 365 full project tests passed.
- Realtime fake smoke passed with `local_time_output=true`.
- JavaScript syntax passed.
- Final project recovery verification passed.

## Live Gate

M082 passed one fresh user-authorized built-in-device Realtime session. The
user accepted the host-local answer and ordinary follow-up, and the runtime
ended with `reason=end_phrase` plus `recovered_to_wake=true`. Live evidence is
recorded in `F082-live-acceptance.md`. No evaluator pass is claimed in this
coding record.
