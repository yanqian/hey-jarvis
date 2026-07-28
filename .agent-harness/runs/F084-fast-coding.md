# F084 Fast Coding Evidence

FAST_CODING_EVIDENCE: F084
CODING_PASS: F084

## Scope

- Added one strict `stock` function to the unified Realtime session.
- Required one conservative uppercase ticker matching the existing bounded
  ticker shape before provider execution.
- Reused the existing `ToolRoute("stock", "stock_provider", ...)`,
  `execute_route`, `ProviderConfig`, Finnhub credential, timeout, quote fields,
  timestamp, delayed-data warning, non-trading-advice caveat, and structured
  provider-error behavior.
- Extended dependency-free Realtime smoke and operator documentation.

## Offline verification

- `./.venv/bin/python -m unittest tests.test_realtime_host tests.test_documentation -v`
  passed 50 tests.
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
  passed 371 tests.
- `./.venv/bin/python -m src.realtime.fake_smoke` passed with
  `stock_output=true`.
- `node --check src/realtime_host/static/app.js` passed.
- `git diff --check` passed.

The deterministic tests use injected HTTP responses and fake credentials. They
require no live network, browser permission, microphone, or speaker, and verify
missing-key, malformed-ticker, unknown-symbol, timeout, and privacy behavior.

## Remaining gate

F084 still requires the user-led built-in-device Realtime acceptance in M084
and a separate cold-start Evaluator Agent pass. This coding note contains no
evaluator evidence and does not mark the feature complete.

## Evaluator Retry Repair

The first cold-start evaluation rejected F084 with `requirement_gap` because
the normalized parent requirement did not explicitly name its feature IDs.
The existing `Complete Realtime Integration for Existing Structured Tools`
section already defines the required goal, included and excluded scope, core
flows, constraints, assumptions, capabilities, implementation paths,
verification surface, and decomposition decision for local time, FX, and stock.
It now explicitly maps that parent requirement to F082, F083, and F084 so the
durable SPEC-to-feature relationship is unambiguous. No runtime scope or
acceptance behavior changed.
