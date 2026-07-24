# F069 live RT004 Web Audio cold-start comparison

## Authorization and boundary

- The user explicitly authorized this F069/RT004 run to open the microphone,
  establish two consecutive OpenAI Realtime sessions, send session audio and
  optional transcription, and incur the associated API cost.
- The existing private wake fixture supplied the only acoustic input twice. No
  fresh human speech or assistant response was required.
- Both sessions ran in one armed Chrome app-mode page. The host reported 48 kHz
  mono capture with echo cancellation, noise suppression, and automatic gain
  control enabled.
- Durable evidence contains only rounded allowlisted lifecycle durations and
  the RT004 verdict. It excludes audio, transcripts, answers, credentials,
  tokens, request identities, provider payloads, SDP, ICE details, addresses,
  and high-frequency input samples.

## Result

- RT004 version 2 passed two distinct connections, two explicit media cleanup
  cycles, and final restoration to `wake_owned` with the wake microphone open.
- Session A browser-ready total: `7773 ms`.
- Session B browser-ready total: `4940 ms`.
- Session A peer setup: `4498 ms`.
- Session B peer setup: `2837 ms`.
- Session A audio-analysis setup: `4491 ms`.
- Session B audio-analysis setup: `2831 ms`.
- First-minus-second audio-analysis difference: `1660 ms`.

### Internal Web Audio breakdown

| Synchronous operation | Session A | Session B |
| --- | ---: | ---: |
| Prior monitor cleanup | `0 ms` | `0 ms` |
| `new AudioContext()` | `4490 ms` | `2831 ms` |
| Analyser construction/configuration | `1 ms` | `0 ms` |
| `createMediaStreamSource()` | `0 ms` | `0 ms` |
| Source-to-analyser connection | `0 ms` | `0 ms` |
| Resume initiation, buffer, and timer setup | `0 ms` | `0 ms` |

## Interpretation boundary

- The synchronous `AudioContext` constructor accounted for effectively the
  entire audio-analysis delay in both sessions.
- The second constructor was `1660 ms` faster, so a same-page warm-up effect is
  present in this sample. However, it still blocked for `2831 ms`; a one-time
  page cold start does not explain the majority of the recurring cost.
- The current stop path closes the analysis `AudioContext`, and the next
  session constructs a new one. This measurement therefore supports evaluating
  reuse/prewarming or moving optional input-level diagnostics outside the
  connection-critical path in a separate optimization feature.
- This is one two-session diagnostic sample, not a stable percentile baseline,
  universal Chrome/macOS claim, or latency SLO. F069 changed no runtime
  ordering or tuning.

The sanitized local evidence is stored under
`tmp/realtime-evals/RT004-evidence.json` and remains untracked.
