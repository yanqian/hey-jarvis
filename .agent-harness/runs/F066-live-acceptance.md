# F066 live-human bilingual acceptance

## Authorization and boundary

- The user explicitly authorized this F066 Realtime bilingual-response test to
  open the microphone, send session audio and optional transcription to OpenAI,
  and incur the associated API cost.
- The run used the built-in microphone and speaker through the existing Chrome
  app-mode host. Chrome reported echo cancellation, noise suppression, and
  automatic gain control enabled with 48 kHz mono capture.
- Durable evidence contains only bounded lifecycle outcomes and the human's
  language verdict. It excludes raw/base64 audio, transcript or answer text,
  tool arguments/results, call identities, credentials, SDP, and provider
  payloads.

## Accepted continuous session

- One fresh wake-triggered session connected and remained the same session for
  three ordered human speech turns.
- The first two turns each recorded one `host_speech_started`, one
  `host_speech_stopped`, one `host_response_created`, and one
  `host_response_done` with `reason=completed`.
- The human explicitly confirmed that the first ordinary answer, following a
  Mandarin Chinese question, was Chinese.
- The human explicitly confirmed that the second ordinary answer, following an
  English question in the same session, was English.
- The third turn produced exactly one `host_end_conversation_tool`, one
  `end_phrase` stop, one browser-confirmed `host_stopped`, and one
  `wake_microphone_reopened`.
- The human explicitly confirmed there was no audible reply after the farewell.
- Final report state was `wake_owned`, with the wake microphone open and no
  active session. The accepted session had no `idle_timeout`, host error,
  duplicate/ignored end call, or alternate cleanup path.

## Separate follow-up observation

- The first ordinary speech turn began about 407 ms before `host_connected`;
  wake-triggered session start to `host_connected` took about 3.15 seconds.
- This is retained only as bounded lifecycle timing for investigation after
  F066. It does not invalidate the bilingual result because the full first turn
  still completed and the human confirmed its Chinese answer.

The language-switching, farewell-regression, lifecycle, and privacy portions of
F066 pass.
