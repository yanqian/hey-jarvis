# F023 Manual Coding Evidence

## Feature

F023 - Add shared network tool provider infrastructure.

## Manual Fallback

This Coding Agent prompt was run interactively for selected feature `F023`, so this run is recorded as manual fallback rather than an orchestrator-dispatched role adapter run. F023 remains `passes=false` and `status="in_progress"` pending Evaluator Agent review.

## Implemented

- Added shared provider configuration for `WEATHER_PROVIDER`, `FX_PROVIDER`, `STOCK_PROVIDER`, `TOOL_HTTP_TIMEOUT_SECONDS`, `DEFAULT_LOCATION`, `DEFAULT_BASE_CURRENCY`, and optional `FINNHUB_API_KEY`.
- Added `src/tools/providers.py` with `ProviderConfig`, `JsonHttpClient`, structured `ProviderError`, provider error to `ToolResult` mapping, safe public summaries, query parameter handling, timeout propagation, HTTP status mapping, network/timeout error mapping, malformed JSON mapping, and HTTP error resource cleanup.
- Wired provider configuration into diagnostics, `python -m src.main --text ...`, and the state-machine tool boundary without invoking live provider network calls.
- Kept weather, FX, and stock provider behavior unimplemented for F024-F026 while making planned-tool `not_configured` results provider-aware and surfacing missing Finnhub credentials clearly.
- Updated `.env.example`, README, DEPLOYMENT, and documentation tests to cover provider settings, no-live-network automated tests, and future manual real-provider smoke expectations.
- Added focused mocked tests for provider config defaults/overrides, invalid timeout values, missing credential messaging, text-debug provider output, JSON success, HTTP errors, status errors, timeout errors, network errors, malformed JSON, and recoverable provider error results.

## Verification

```bash
./init.sh
python3 -m unittest tests.test_config tests.test_tools tests.test_tool_providers tests.test_documentation
python3 -m unittest discover -s tests
python3 -m src.main --text "AAPL stock price"
./init.sh
```

All verification passed. Automated tests use mocked provider responses and do not call live weather, FX, or stock services.

## Failure Domain

none

No implementation failure or blocked condition occurred.

## Harness Improvement Assessment

No harness improvement is required. The manual fallback was explicitly requested by the interactive selected-feature Coding Agent prompt and has been recorded here. Evaluator gating is preserved by leaving F023 incomplete in `feature_list.json` until evaluator review.

## Capability Gaps

No capability gap was introduced. Live weather, FX, and stock provider behavior remains intentionally deferred to F024, F025, and F026; F023 provides the durable shared config and mocked HTTP boundary needed for those follow-up features.

## Example Boundary

No `examples/` files were changed.

CODING_PASS: F023
