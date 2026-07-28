# F084 Live User Acceptance

## Verdict

The user confirmed the built-in-device Realtime stock-quote behavior was
acceptable and explicitly authorized the F084 commit.

## Sanitized lifecycle evidence

- One armed Chrome host accepted one wake and created one Realtime session.
- Input was enabled only after configured-session readiness and local
  acknowledgement completion.
- Three user turns each produced one completed, correlated stock tool-result
  command; the user exercised multiple quote requests in the same session.
- Each duplicate tool-call event was detected and de-duplicated without a
  second result.
- The conversation remained usable across all quote turns.
- The final user turn invoked the semantic end-conversation control.
- Browser media stopped before the wake microphone reopened.
- The terminal reported `reason=end_phrase recovered_to_wake=true`.
- The final host report was `state=wake_owned`,
  `wake_microphone_open=true`, and `active_session=false`.

The report contained no transcript, answer, ticker, price, quote timestamp,
tool arguments, call ID, provider body, Finnhub credential, audio, or SDP. The
user's audible verdict is the evidence for concise Chinese provider-backed
quotes, freshness/delayed-data and non-advice semantics, and follow-up
usability; those contents are intentionally not persisted.
