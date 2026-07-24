# F065 live-human acceptance

## Authorization and boundary

- The user explicitly authorized this F065 Realtime farewell-closure test to
  open the microphone, send session audio and optional transcription to
  OpenAI, and incur the associated API cost.
- The run used the built-in microphone and speaker through the existing Chrome
  app-mode host. Chrome reported echo cancellation, noise suppression, and
  automatic gain control enabled with 48 kHz mono capture.
- Durable evidence contains only bounded lifecycle outcomes. It excludes raw or
  encoded audio, transcript text, tool arguments, call ids, credentials, and
  provider payloads.

## Attempts

- Attempt 1 was invalid for F065 semantics: wake connected, but no
  `host_speech_started` followed connection; the likely-too-early farewell was
  not captured and the session later closed through `idle_timeout`.
- Attempt 2 was also invalid: the operator correctly waited for an agent signal
  after wake, but that coordination exceeded the configured 15-second idle
  window. It closed through `idle_timeout` before the farewell phase.
- Attempt 3 used one continuous operator sequence: human wake, a roughly
  four-second connection allowance, then a clear standalone farewell.

## Accepted lifecycle evidence

- One fresh session connected and then recorded exactly one
  `host_speech_started`, one `host_speech_stopped`, and one sanitized completed
  transcription outcome.
- The model emitted exactly one valid `end_conversation` call, recorded as
  `host_end_conversation_tool`, about 632 ms after the completed-transcription
  outcome.
- The coordinator emitted exactly one stop command with `reason=end_phrase` at
  the same monotonic timestamp as the accepted tool call. No tool result or
  continuation response was requested.
- Browser media teardown recorded `host_stopped` about 19 ms later, followed by
  `wake_microphone_reopened` about 97 ms after teardown.
- Final report state was `wake_owned`, with the wake microphone open and no
  active session.
- The accepted session had no `idle_timeout`, host error, ignored end call,
  duplicate tool call, or alternate stop path.
- The human explicitly confirmed that the accepted third attempt produced no
  audible GPT reply after the farewell.

The lifecycle, experience, and privacy portions of F065 pass.
