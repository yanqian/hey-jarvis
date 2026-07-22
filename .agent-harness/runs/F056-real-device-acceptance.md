# F056 Real-Device Acceptance

Date: 2026-07-17

## Environment and procedure

- macOS built-in microphone/speakers, no headphones, project-selected Chrome app-mode host.
- Fresh armed host and wake-triggered Realtime session with a temporary 60-second idle window for task-UI latency; tracked defaults were unchanged.
- User spoke the existing Chinese calculator regression request for 100 times 1000 and confirmed the spoken answer completed.
- Evidence was inspected only through bounded sanitized events; no transcript text, raw/base64 audio, API key, ephemeral credential, or pipeline chat history was retained.

## Result

PASS.

- One `host_tool_call` executed the advertised calculator.
- One `host_command(command=tool_result)` returned `status=success` and `The answer is 100000.`.
- The dedicated arguments-completed event and canonical response-done item both reported the same call; the second became one `host_tool_call_duplicate`, proving execution was not repeated.
- A following `host_response_created` and completed response occurred in the same active session, and the user heard the spoken continuation.
- Explicit cleanup returned the controller to `wake_owned` with its wake microphone reopened.
