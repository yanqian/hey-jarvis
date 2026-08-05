# F117 target-Mac live acceptance

## Scope

- Date: 2026-08-05 (Asia/Singapore)
- Agent role: owner-led target-Mac acceptance with provider-native observation
- Build: current-worktree Tauri Debug App
- Profile: cached Mandarin farewell, canonical 580 ms `alloy` WAV, browser gain 0.5
- Authorization: the owner explicitly requested an overall test, authorizing one
  short microphone, speaker, and OpenAI Realtime session.

## Overall flow

- The owner performed the required wake, ordinary question, semantic farewell,
  and subsequent wake on the target Mac.
- The owner explicitly confirmed hearing the selected cached `再见`, judged its
  ending natural, and confirmed the second wake succeeded.
- Privacy-bounded Python lifecycle diagnostics for one unchanged sidecar session
  show `wake_listening -> busy -> wake_listening`, followed about 8.0 seconds
  later by a second `busy -> wake_listening` cycle. The first busy interval was
  about 10.1 seconds and the second about 6.0 seconds.
- The second busy interval proves that wake ownership was not merely displayed
  as recovered: the subsequent spoken wake was accepted and handed off, then
  local wake listening recovered again.
- The canonical asset and manifest passed digest, format, duration, owner
  selection, and 20 ms leading-trim assertions in the same worktree before the
  live run. Cached mode sends no farewell `response.create` by source contract
  and automated coverage.

## Privacy boundary

No audio, transcript, answer text, credentials, SDP, ICE, provider payload,
or tool arguments/results were retained. This record contains only bounded
lifecycle states, relative timing, configuration identifiers, and the owner's
perceptual verdict.

## Verdict

The target-Mac listening and overall-flow acceptance required by F117 passes.
The cached farewell was audible and natural, cleanup restored wake ownership,
and a second wake completed successfully. Separate cold-start Evaluator Agent
approval remains required.
