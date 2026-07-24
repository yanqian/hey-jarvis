# F066 coding progress

- Selected through evaluator-gated `work-fast` handoff after normalizing the
  current-turn language requirement and its bilingual live verification.
- Confirmed the defect boundary: F058 applies only to the pipeline, while the
  Realtime session instructions previously contained only the F065 farewell
  policy and no response-language contract.
- Verified current official OpenAI Realtime prompting guidance recommends
  explicit language constraints for multilingual/noisy conditions and supports
  custom instruction-driven code switching.
- Replaced the single-purpose Realtime instruction with structured role,
  language, and conversation-ending sections.
- Required every ordinary response to follow the language primarily used in the
  current user audio turn; Mandarin Chinese maps to concise natural Simplified
  Chinese and English maps to English.
- Made the current turn override prior conversation, English developer/tool
  wording, and English tool output. Added mixed-language and explicit
  translation, spelling, pronunciation, language-practice, and whole-response
  target-language rules.
- Preserved the F065 `end_conversation` selection/no-reply contract, both
  existing tools, and all model, voice, VAD, output-volume, wake, barge-in,
  pipeline, and RT001-RT004 settings.
- Added README and M066 manual acceptance documentation plus static contract
  regressions.
- JavaScript syntax and 43 focused Realtime/config/documentation tests pass.
- Full project discovery and final `./init.sh` recovery pass with 335 project
  tests, dry-run, pipeline fake-backend smoke, and Realtime fake smoke.
- No microphone, browser, network, OpenAI request, or billable live session was
  used during this coding phase.

F066 remains in progress. Its acceptance requires one newly and explicitly
authorized built-in-device continuous live session with human confirmation of
Chinese then English replies and clean farewell recovery. Do not infer
permission from F065. After live evidence is recorded, add fast coding markers
and invoke the separate cold-start evaluator.
