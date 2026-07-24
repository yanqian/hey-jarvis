# F067 live RT001 wake-to-ready timing

## Authorization and boundary

- The user explicitly authorized this F067/RT001 run to open the microphone,
  send session audio and optional transcription to OpenAI, and incur the
  associated API cost.
- The existing private wake fixture supplied the only acoustic input. No fresh
  human speech or assistant response was required.
- The Chrome app-mode host reported 48 kHz mono capture with echo cancellation,
  noise suppression, and automatic gain control enabled.
- Durable evidence contains only rounded allowlisted lifecycle durations and
  the RT001 verdict. It excludes audio, transcripts, answers, credentials,
  tokens, request identities, provider payloads, SDP, and tool content.

## Result

- RT001 passed exclusive microphone handoff, one configured Realtime
  connection, explicit media cleanup, and restoration to `wake_owned` with the
  wake microphone open.
- Confirmed wake to configured ready: `8711 ms`.
- Confirmed wake to acknowledgement start: `119 ms`.
- Local acknowledgement: `1375 ms`.
- Acknowledgement completion to handoff queue: `0 ms`.
- Handoff queue to configured ready: `7217 ms`.
- Handoff dispatch outside the browser breakdown: `49 ms`.
- Browser command receipt to configured ready: `7168 ms`.
- Command receipt to token start: `5 ms`.
- Ephemeral-token acquisition: `1034 ms`.
- Browser microphone acquisition: `115 ms`.
- Peer/SDP setup: `3053 ms`.
- OpenAI WebRTC negotiation: `1905 ms`.
- Realtime session configuration: `1056 ms`.

## Interpretation boundary

- The dominant measured phase in this single run was peer/SDP setup, followed
  by WebRTC negotiation. Token acquisition, session configuration, and local
  acknowledgement were each about one second or more.
- This is one diagnostic sample, not a stable percentile baseline and not a
  latency SLO.
- F067 changes no runtime ordering or tuning. Any optimization must be planned
  separately from these measurements.

The sanitized local evidence is stored under
`tmp/realtime-evals/RT001-evidence.json` and remains untracked.
