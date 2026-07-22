# F056 Fast Coding Evidence

FAST_CODING_EVIDENCE: F056
CODING_PASS: F056

## Scope implemented

- Advertises exactly one strict Realtime function named `calculator` with automatic tool choice.
- Accepts complete call arguments from both the dedicated completion event and canonical `response.done.output`, correlates by active session/call identity, and de-duplicates before execution.
- Parses bounded JSON with exactly one string `expression` property and executes it through the existing `execute_route(ToolRoute("calculator", "safe_calculator", ...))` boundary.
- Enqueues one bounded `tool_result`; the browser sends one correlated `function_call_output` followed by one `response.create` continuation in the same data channel and conversation.
- Returns safe bounded error outputs for malformed arguments, unknown tools, and unsafe expressions without arbitrary routing, provider tools, shell access, `eval`, or pipeline history mutation.

## Verification

- 66 focused Realtime/tool/documentation/controller tests passed.
- JavaScript syntax and `git diff --check` passed.
- Current official OpenAI Realtime function-calling documentation was checked for session tool configuration, call-id correlation, `function_call_output`, and continuation response flow.
- Real-device evidence is recorded separately in `F056-real-device-acceptance.md`.

This is Coding Agent evidence only. It does not contain evaluator approval and does not mark F056 done.
