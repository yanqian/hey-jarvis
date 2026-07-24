# F068 live RT001 peer/SDP timing

## Authorization and boundary

- The user explicitly authorized this F068/RT001 run to open the microphone,
  send session audio and optional transcription to OpenAI, and incur the
  associated API cost.
- The existing private wake fixture supplied the only acoustic input. No fresh
  human speech or assistant response was required.
- The Chrome app-mode host reported 48 kHz mono capture with echo cancellation,
  noise suppression, and automatic gain control enabled.
- Durable evidence contains only rounded allowlisted lifecycle durations and
  the RT001 verdict. It excludes audio, transcripts, answers, credentials,
  tokens, request identities, provider payloads, SDP, ICE details, addresses,
  and tool content.

## Result

- RT001 version 3 passed exclusive microphone handoff, one configured Realtime
  connection, explicit media cleanup, and restoration to `wake_owned` with the
  wake microphone open.
- Confirmed wake to configured ready: `8535 ms`.
- Confirmed wake to acknowledgement start: `115 ms`.
- Local acknowledgement: `1354 ms`.
- Acknowledgement completion to handoff queue: `0 ms`.
- Handoff queue to configured ready: `7066 ms`.
- Handoff dispatch outside the browser breakdown: `181 ms`.
- Browser command receipt to configured ready: `6885 ms`.
- Command receipt to token start: `4 ms`.
- Ephemeral-token acquisition: `443 ms`.
- Browser microphone acquisition: `95 ms`.
- Peer/SDP setup aggregate: `4389 ms`.
  - Microphone settings/reporting: `2 ms`.
  - Input-level audio-analysis setup: `4379 ms`.
  - PeerConnection, track, and data-channel setup: `5 ms`.
  - Offer creation: `1 ms`.
  - Local-description setup: `2 ms`.
- OpenAI WebRTC negotiation: `776 ms`.
- Realtime session configuration: `1178 ms`.

## Interpretation boundary

- In this single run, `4379 ms` of the `4389 ms` peer/SDP aggregate occurred
  synchronously inside `startInputLevels(stream)`, which creates and wires a
  Web Audio `AudioContext`, analyser, media-stream source, sample buffer, and
  timer. PeerConnection construction and local SDP operations together took
  only `8 ms`.
- The timing boundaries are contiguous browser-monotonic measurements. The
  five nested values reconcile exactly to the retained aggregate and are not
  counted again in the browser-ready total.
- This is one diagnostic sample, not a stable percentile baseline and not a
  latency SLO. F068 changes no runtime ordering or tuning. Deferring or
  reworking input-level diagnostics is a candidate for a separately planned
  optimization, not part of F068.

The sanitized local evidence is stored under
`tmp/realtime-evals/RT001-evidence.json` and remains untracked.
