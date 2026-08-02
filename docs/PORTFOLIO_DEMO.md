# Portfolio demo runbook

DEMO_DURATION_SECONDS: 210

This is a 3 minute 30 second recording plan, not a public binary release. Use
the unsigned internal build only on the owner Mac or with an explicitly trusted
tester. Record a fresh bounded run and do not splice older Chrome/spike footage
into the product demo.

## Privacy setup

- Use a clean desktop and notifications-off mode.
- Configure Keychain before recording. Never show a key entry dialog, Keychain
  password, API dashboard, support-bundle contents, raw logs, transcripts, or
  Finder paths containing a personal account name.
- Keep the macOS microphone indicator visible when useful, but do not record
  unrelated applications or private audio.
- State on screen that the build is Apple Silicon/macOS 14+, BYOK,
  `INTERNAL-UNSIGNED`, not notarized, and not available as a public download.

## Shot list

| Time | Visual and action | Proof point |
| --- | --- | --- |
| 0:00–0:20 | Title card, four project goals, unsigned-internal warning | Honest project and distribution scope |
| 0:20–0:45 | Open the installed app and briefly show Settings with both keys shown only as configured/not configured | BYOK, Keychain boundary, privacy/API-cost disclosure |
| 0:45–1:05 | Run **Check microphone & start**, reach the runtime page, then select **Arm hands-free audio** | Deliberate TCC check and explicit media arming |
| 1:05–1:30 | Say the wake phrase, hear one acknowledgement, and ask one ordinary question | Local wake followed by Realtime handoff |
| 1:30–1:55 | Ask a follow-up without repeating the wake phrase | Continuous session |
| 1:55–2:20 | Ask one provider-backed tool question; show the answer without exposing transcript/log content | Bounded tool integration |
| 2:20–2:45 | Interrupt a longer answer with a clearly different question | Natural barge-in and switch to the new turn |
| 2:45–3:05 | Say “再见” and show `Armed · Python wake microphone restored` | Semantic ending, media release, wake recovery |
| 3:05–3:25 | Open Settings, show **Export support bundle** and **Clear diagnostics** controls without opening their output | Privacy-safe support path |
| 3:25–3:30 | Quit from the tray and show the closing card | Clean lifecycle and explicit limitations |

## Closing card

Show: “Local-first wake detection · OpenAI after wake · BYOK · Apple Silicon
macOS 14+ · unsigned trusted testing only · public binary distribution on
hold.” Link to the repository case study, not to the DMG.

The recording passes only if it is 120–240 seconds, contains every shot above,
shows no sensitive value or transcript, uses the production app, and accurately
keeps public binary distribution on hold.
