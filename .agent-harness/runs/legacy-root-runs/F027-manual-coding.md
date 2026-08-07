# F027 Manual Coding Evidence

Date: 2026-07-06

## Fallback

Manual Coding Agent fallback was used because the selected-feature Coding Agent
prompt was invoked interactively for F027. This does not bypass evaluator
gating; `feature_list.json` remains `passes=false` and `status=in_progress`
until evaluator evidence records `EVAL_PASS: F027`.

## Implementation

- Added `TOOL_ANSWER_NATURALIZATION`, default enabled, to settings loading,
  validation, `.env.example`, README, and deployment docs.
- Added `OpenAIClient.naturalize_tool_answer(...)` as a separate chat
  completions boundary that receives the user question, route metadata, raw
  answer, summary, and sanitized non-secret structured data without mutating
  chat history.
- Routed naturalization only for successful weather, FX, and stock
  provider-backed `ToolResult` values.
- Preserved deterministic raw answers for provider failures, missing
  credentials, not-configured results, realtime refusals, calculator/local-time
  answers, disabled naturalization, empty LLM output, and recoverable OpenAI
  errors.
- Added text-debug `raw_answer` and `naturalization_status` fields without
  requiring OpenAI credentials.
- Added focused tests for request shape, fallback behavior, no chat-history
  pollution, no secret leakage, text-debug output, config loading, and
  documentation coverage.

## Verification

```bash
./init.sh
python3 -m unittest tests.test_config tests.test_openai_client tests.test_tools tests.test_state_machine tests.test_main tests.test_documentation
python3 -m src.main --text "2 + 2"
python3 -m src.main --text "今天有什么新闻"
python3 -m unittest discover -s tests
```

Focused and full project unit tests passed before final recovery verification.

## Failure Domain

Primary failure domain: none.

No implementation failure or blocked condition occurred. Harness improvement is
not required.

## Capability Gaps

None. Automated verification uses fake OpenAI clients and mocked provider
results. No live OpenAI or provider network access is required for completion
evidence.

## Example Boundary

No `examples/` files were changed.
