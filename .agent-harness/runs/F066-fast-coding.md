# F066 Fast Coding Evidence

FAST_CODING_EVIDENCE: F066

## Root cause

- F058's current-turn language policy was implemented only in the pipeline
  prompt boundary.
- The Realtime session instructions contained the F065 farewell policy but no
  response-language contract, so English developer/tool wording could coincide
  with the observed English-only replies.

## Implementation

- Added structured Realtime role, language, and conversation-ending instruction
  sections using the existing `session.update.instructions` surface.
- Required Mandarin Chinese current-turn input to receive concise natural
  Simplified Chinese and English current-turn input to receive English.
- Made the current user audio turn override prior conversation, English
  developer/tool wording, and English tool output.
- Added bounded mixed-language and explicit translation, spelling,
  pronunciation, language-practice, and whole-response target-language rules.
- Kept language selection inside the Realtime model's current audio
  understanding rather than using optional rough-guide transcription.
- Preserved both existing tools, F065 end/no-reply rules, model, voice, VAD,
  output volume, wake, barge-in, pipeline F058, and RT001-RT004 behavior.
- Documented the language contract and M066 live-human acceptance.
- Verified the approach against current official OpenAI Realtime prompting
  guidance for language constraints and instruction-driven code switching.

## Verification

- JavaScript syntax check passed.
- Focused Realtime/config/documentation suite: 43 tests passed.
- Full project discovery: 335 tests passed.
- Final `./init.sh` passed with 335 project tests, dry-run, pipeline
  fake-backend smoke, and Realtime fake smoke.

## Authorized live-human acceptance

- One authorized built-in-device continuous session produced two ordered
  completed ordinary turns followed by clean semantic farewell closure.
- The human confirmed the first answer to the Mandarin Chinese turn was Chinese
  and the second answer to the English turn in the same session was English.
- The human confirmed the farewell produced no audible reply.
- Lifecycle evidence showed one session identity throughout, clean
  `end_conversation` stop, media teardown, wake-microphone reopen, final
  `wake_owned`, and no accepted-session idle timeout or host error.
- Durable evidence in `F066-live-acceptance.md` excludes transcript, answer,
  audio, credential, provider, and tool content.

CODING_PASS: F066
