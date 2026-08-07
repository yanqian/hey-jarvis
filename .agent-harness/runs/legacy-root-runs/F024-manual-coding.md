# F024 Manual Coding Evidence

## Feature

F024 - Implement Open-Meteo weather tool.

## Manual Fallback

This Coding Agent prompt was run interactively for selected feature `F024`, so this run is recorded as manual fallback rather than an orchestrator-dispatched role adapter run. F024 remains `passes=false` and `status="in_progress"` pending Evaluator Agent review.

## Implemented

- Added weather route parameter extraction for `current`, `today`, and `tomorrow` intents plus practical English and Chinese location extraction.
- Wired `execute_route`, `answer_with_tools`, and `format_text_debug` to run the Open-Meteo weather provider when `WEATHER_PROVIDER=open-meteo`, while leaving FX and stock provider behavior deferred.
- Added Open-Meteo geocoding and forecast provider behavior behind the existing JSON HTTP boundary, including `DEFAULT_LOCATION` fallback, current weather answers, today/tomorrow daily forecast answers, normalized location, source, freshness, temperature, apparent-temperature, weather-code, precipitation, and rain/probability data.
- Mapped no geocoding match, missing/malformed provider fields, HTTP status, timeout, network, and malformed JSON errors into structured weather `ToolResult` errors without falling back to chat speculation.
- Updated README, DEPLOYMENT, MANUAL_TESTING, documentation tests, routing tests, and provider tests for Open-Meteo weather behavior and no-live-network automated verification.

## External Behavior Evidence

Open-Meteo API behavior was checked against official Open-Meteo documentation during implementation:

- Geocoding endpoint: `https://geocoding-api.open-meteo.com/v1/search` accepts `name`, `count`, `format`, `language`, and returns `results` with `name`, `latitude`, `longitude`, `country`, and `timezone` fields.
- Forecast endpoint: `https://api.open-meteo.com/v1/forecast` accepts `latitude`, `longitude`, `current`, `hourly`, `daily`, `timezone`, and `forecast_days`; current, hourly, and daily weather variables include temperature, apparent temperature, weather code, precipitation, rain, and precipitation probability fields.

Automated tests use real-shaped mocked Open-Meteo responses and do not call live provider services.

## Verification

```bash
./init.sh
python3 -m unittest tests.test_tools tests.test_tool_providers
python3 -m unittest tests.test_config tests.test_tools tests.test_tool_providers tests.test_documentation tests.test_main tests.test_state_machine
```

All verification listed above passed before this run note was written. Final `./init.sh` verification is still required after state-file updates.

## Failure Domain

none

No implementation failure or blocked condition occurred.

## Harness Improvement Assessment

No harness improvement is required. The manual fallback was explicitly requested by the interactive selected-feature Coding Agent prompt and has been recorded here. Evaluator gating is preserved by leaving F024 incomplete in `feature_list.json` until evaluator review.

## Capability Gaps

No unresolved capability gap was introduced. Live Open-Meteo provider behavior is implemented through durable configuration, documentation, mocked fixtures, and the shared HTTP boundary. Automated verification intentionally avoids live network calls; manual live-provider smoke commands are documented.

## Example Boundary

No `examples/` files were changed.

CODING_PASS: F024
