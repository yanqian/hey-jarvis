# Portfolio demo

DEMO_DURATION_SECONDS: 213

This is the final Chinese feature-demo recording, not an installation tutorial
or a general consumer binary release. The current 3 minute 33 second recording focuses on
the user-visible value: normal conversation, tool-backed information, a locked
Mac wake flow, acknowledgement, semantic ending, and recovery to wake listening.
The English and Chinese recordings are both published feature demonstrations.

Installation, BYOK, microphone permission, Settings, diagnostics, update,
rollback, and uninstall are documented in [the English user guide](USER_GUIDE.md)
and [the Chinese user guide](USER_GUIDE_ZH.md). They do not need to be forced
into the feature-demo recording. The unsigned internal distribution boundary
and trusted install procedure remain documented in
[INTERNAL_MAC_APP_TESTING.md](INTERNAL_MAC_APP_TESTING.md).

Published demos:

- English: https://www.youtube.com/watch?v=Cpv3dhFmS3M
- Chinese: https://www.youtube.com/watch?v=PDHQiYzFAXQ

## Privacy setup

- Use a clean desktop and notifications-off mode.
- Configure Keychain before recording. Never show a key entry dialog, Keychain
  password, API dashboard, support-bundle contents, raw logs, transcripts, or
  Finder paths containing a personal account name.
- Keep the macOS microphone indicator visible when useful, but do not record
  unrelated applications or private audio.
- State on screen that the build is Apple Silicon/macOS 14+, BYOK,
  `INTERNAL-UNSIGNED`, not notarized, and intended for internal evaluation.

## Final recording coverage

| Time | Visual and action | Proof point |
| --- | --- | --- |
| Normal Mode | Wake, acknowledgement, ordinary conversation, follow-up, provider-backed PDD quote, and semantic stop | Everyday assistant flow |
| Smart Speaker Mode | Locked-Mac wake and response flow | Hands-free wake after the screen is locked |
| Closing | Return to the next wake-ready state | Session ending and media release |

## Closing card

Show: “Local-first wake detection · OpenAI after wake · BYOK · Apple Silicon
macOS 14+ · unsigned internal evaluation build.” Link to the repository case
study and the GitHub Release notes.

The recording is accepted as the feature demo when it is 120–240 seconds, uses
the production app, shows no sensitive value or transcript, and accurately keeps
publicly trusted binary distribution on hold. The user-facing operational
details belong to the linked documentation.
