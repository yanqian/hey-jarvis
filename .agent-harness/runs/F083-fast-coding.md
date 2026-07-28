# F083 Fast Coding Evidence

FAST_CODING_EVIDENCE: F083
CODING_PASS: F083

## Scope

- Added one strict `fx` function to the unified Realtime session.
- Validated optional positive amounts up to 1,000,000,000 and optional
  supported uppercase base/quote codes before provider execution.
- Reused the existing `ToolRoute("fx", "fx_provider", ...)`,
  `execute_route`, `ProviderConfig`, Frankfurter client, configured defaults,
  rounding, reference-date, caveat, timeout, and structured error behavior.
- Extended the dependency-free Realtime smoke and operator documentation.

## Offline verification

- `./.venv/bin/python -m unittest tests.test_realtime_host tests.test_documentation -v`
  passed 47 tests.
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
  passed 368 tests.
- `./.venv/bin/python -m src.realtime.fake_smoke` passed with
  `fx_output=true`.
- `node --check src/realtime_host/static/app.js` passed.
- `git diff --check` passed.

The deterministic tests use injected HTTP responses and require no network,
provider credential, browser permission, microphone, or speaker.

## Remaining gate

F083 still requires the user-led built-in-device Realtime acceptance in M083
and a separate cold-start Evaluator Agent pass. This coding note does not
contain evaluator evidence and does not mark the feature complete.
