# F081 Fast Coding Evidence

## Result

FAST_CODING_EVIDENCE: F081

CODING_PASS: F081

F081 implementation and offline verification are complete. Live user
acceptance and evaluator approval remain separate gates.

## Implementation

- Added one strict Realtime `weather` function with optional explicit location
  and required `current`, `today`, or `tomorrow` intent.
- Reused the existing `ToolRoute`, `execute_route`, `ProviderConfig`,
  Open-Meteo, configured default location, timeout, parsing, and structured
  provider-error boundaries.
- Added a conservative provider-query alias for explicit Chinese references to
  Japan's Tokyo (`东京`, `東京`, and unambiguous variants). This avoids the
  observed `no_location_match` failure without globally enabling Chinese
  geocoding, which can resolve `东京` to unrelated same-name places in China.
- Preserved calculator and semantic end-conversation behavior; stock, FX, time,
  news, shell, arbitrary browsing, and MCP remain unadvertised.
- Split tool handling into a lock-bounded claim, lock-free provider execution,
  and lock-bounded correlated completion. Stopped or replaced sessions cannot
  receive late output.
- Kept tool arguments, call IDs, locations, answers, and provider bodies out of
  sanitized lifecycle evidence.
- Extended the dependency-free Realtime fake smoke with mocked
  default-Singapore weather.
- Documented the Realtime weather boundary and M081 user-led acceptance.

## External Contract Evidence

The official OpenAI Realtime function-calling guide confirms that applications
return custom tool results with a `conversation.item.create` event whose item
type is `function_call_output`, reusing the original `call_id`, then emit
`response.create` to continue the model response:

https://developers.openai.com/api/docs/guides/realtime-conversations#provide-the-results-of-a-function-call-to-the-model

The existing browser implementation already follows that contract, so F081 did
not alter its data-channel protocol.

## Verification

```bash
python3 -m unittest tests.test_realtime_host tests.test_documentation tests.test_tool_providers tests.test_tools
python3 -m src.realtime.fake_smoke
node --check src/realtime_host/static/app.js
python3 -m unittest discover -s tests
./init.sh
```

Results:

- Focused Realtime, provider, tool, privacy, and documentation tests passed.
- 364 full project tests passed.
- Realtime fake smoke passed with `weather_output=true`.
- JavaScript syntax passed.
- Harness verification, dry-run, pipeline fake smoke, Realtime fake smoke, and
  final project recovery verification passed.

## Live Gate

Live attempts are recorded separately in `F081-live-attempts.md`. Default
Singapore weather eventually played successfully. The first explicit Tokyo
attempt exposed the Chinese geocoding defect above; after correction, a real
provider query returned Tokyo, Japan and a fresh Realtime session completed the
weather tool lifecycle and restored wake ownership. The user confirmed that
the post-fix Chinese audio named Japan's Tokyo. No evaluator pass is claimed in
this coding record.
