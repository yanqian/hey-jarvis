# F083 Live User Acceptance

## Verdict

The user confirmed the built-in-device Realtime FX behavior was acceptable.

## Sanitized lifecycle evidence

- One armed Chrome host accepted one wake and created one Realtime session.
- Input was enabled only after configured-session readiness and local
  acknowledgement completion.
- The first user turn produced one completed, correlated tool-result command.
- A duplicate tool-call event was detected and de-duplicated without a second
  result.
- A later user speech turn remained usable in the same session.
- The final user turn invoked the semantic end-conversation control.
- Browser media stopped before the wake microphone reopened.
- The terminal reported `reason=end_phrase recovered_to_wake=true`.
- The final host report was `state=wake_owned`,
  `wake_microphone_open=true`, and `active_session=false`.

The report contained no transcript, answer, FX amount, currency pair, rate,
tool arguments, call ID, provider response body, credential, audio, or SDP.
The user's audible verdict is the evidence for concise Chinese conversion,
provider-backed reference-date/caveat semantics, and follow-up usability; those
contents are intentionally not persisted.
