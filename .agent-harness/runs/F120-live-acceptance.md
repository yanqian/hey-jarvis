# F120 target-Mac bilingual live acceptance

## Scope

- Date: 2026-08-06 (Asia/Singapore)
- Build: refreshed current-worktree Tauri Debug App bundle
- Runtime: one product sidecar session using the existing Keychain credential,
  local wake detector, microphone, built-in speaker, and OpenAI Realtime
- Authorization: owner-directed bilingual overall-flow acceptance

## English flow

- The preference was English before the wake and the native surface reached
  `WAKE LISTENING`.
- The owner performed wake, ordinary English discussion, exact/semantic ending,
  and a subsequent wake.
- The owner explicitly confirmed that the English flow was entirely normal:
  the selected `I'm here. Yes?` ACK and `See you.` farewell were audible, the
  conversation completed, and the next wake succeeded.

## Simplified Chinese flow

- Computer Use changed the ordinary application preference from English to
  Simplified Chinese while the sidecar stayed alive. The localized UI updated
  immediately and explicitly stated that fixed cues would change from the next
  wake.
- The owner then performed wake, ordinary Mandarin discussion, exact/semantic
  ending, and a subsequent wake.
- The owner explicitly confirmed that the Chinese flow was entirely normal:
  the accepted `嗯，我在，请说。` ACK and `再见` farewell were audible, the
  conversation completed, and the next wake succeeded.

## Recovery and snapshot evidence

- Privacy-bounded lifecycle diagnostics show both owner trials as
  `wake_listening -> busy -> wake_listening`, followed by a second accepted
  `busy -> wake_listening` cycle in the same sidecar session. This confirms
  teardown restored real wake ownership rather than only updating UI text.
- Deterministic coordinator/browser tests independently switch the preference
  during an active handoff: the current ACK/farewell retain the captured
  locale, the language provider is not reread, and the next handoff captures
  the new locale. Cue selection contains no GPT, transcript, current-utterance,
  history, or UI-language inference.

## Privacy boundary and verdict

No audio, transcript, answer text, credentials, SDP, ICE, provider payload, or
tool arguments/results were retained. The bilingual target-Mac overall flows
pass. Separate cold-start Evaluator Agent approval remains required.
