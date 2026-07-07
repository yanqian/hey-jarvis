# F028 Manual Coding Evidence

Date: 2026-07-06

## Fallback

Manual Coding Agent fallback was used because the selected-feature Coding Agent
prompt was invoked interactively for F028. This does not bypass evaluator
gating; `feature_list.json` remains `passes=false` and `status=in_progress`
until evaluator evidence records `EVAL_PASS: F028`.

## Implementation

- Treated relative English and Chinese weather locations such as `here`,
  `current location`, `nearby`, `这里`, `这边`, `本地`, and `附近` as omitted
  locations so the existing weather provider path uses configured
  `DEFAULT_LOCATION`.
- Preserved concrete weather locations such as Tokyo and `东京`.
- Added provider-error context for safe route fields, including query, intent,
  location, attempted location, location source, provider error, and status
  code where available.
- Added default-location attempted-location context when a weather request has
  no concrete route location and Open-Meteo geocoding fails.
- Logged state-machine provider-error route params and result data without
  requiring `TOOL_ROUTER_DEBUG`.
- Added focused mocked tests for relative-location fallback, concrete-location
  preservation, default-location provider calls, provider-error context, weather
  answer-path behavior, and state-machine provider-error logs.

## Verification

```bash
./init.sh
python3 -m unittest tests.test_tools tests.test_tool_providers tests.test_state_machine
./init.sh
```

Focused tests passed 76 tests. Final `./init.sh` passed harness verification,
146 project tests, dry-run smoke, and fake-backend smoke.

## Failure Domain

Primary failure domain: none

No implementation failure or blocked condition occurred. Harness improvement is
not required.

## Capability Gaps

None. Automated verification uses mocked Open-Meteo responses and state-machine
fakes. No GPS, OS location access, live network access, new credentials, or new
dependencies are required.

## Example Boundary

No `examples/` files were changed.

## Evaluator Result

```text
EVAL_PENDING: F028
```
