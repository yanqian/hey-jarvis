# Portfolio completion record

## Current decision: GO_INTERNAL

The English and Chinese feature demos are published and viewable. One owner-led
Apple Silicon internal trial is recorded. Installation and usage details are
available in both `docs/USER_GUIDE.md` and `docs/USER_GUIDE_ZH.md`; additional
trusted trials remain optional follow-up evidence, not blockers for this pass.

- English demo: https://www.youtube.com/watch?v=Cpv3dhFmS3M
- 中文 Demo: https://www.youtube.com/watch?v=PDHQiYzFAXQ

The unsigned DMG is approved for a public GitHub Release as an internal
evaluation artifact. It is not presented as signed, notarized, Gatekeeper-ready,
or suitable for general consumer distribution. Public binary distribution means
trusted/general-consumer distribution remains deferred.

## Artifact and readiness baseline

- App version: `0.1.0`
- Target: Apple Silicon, macOS 14+
- DMG: 45,439,075 bytes; installed app approximately 104 MiB
- Nested code: 83 arm64 Mach-O entries
- Trust: ad-hoc/unsigned internal build; not Developer ID signed, notarized,
  stapled, Gatekeeper-ready, or automatically updated
- Runtime evidence: correct answer, continuous follow-up, successful
  interruption, semantic ending, wake-microphone restoration, support export,
  clean quit/relaunch, and manual rollback passed in the owner-led F092 trial
- Local Chinese feature artifact: `artifacts/video/hey-jarvis-f093-flow-in-one-cn-v2.mp4`,
  approximately 183 seconds, 1280×720
- Local English feature artifact: `artifacts/video/hey-jarvis-f093-flow-in-one-v5.mp4`,
  approximately 187 seconds, 1280×720

## Feedback summary

The owner trial found real friction around Keychain authorization, microphone
permission recovery, settings navigation, stale duplicate Chrome audio, asset
routing, and diagnostics-clear semantics. Root causes were corrected and the
final internal artifact passed the bounded flow. Additional trusted trials may
be collected later for broader feedback, but are not required by the current
portfolio completion boundary.

Any credential exposure, presentation of the unsigned binary as publicly
trusted, repeatable microphone ownership loss, residual sidecar, crash loop,
or unrecoverable onboarding is a blocker. Record it in the trial JSON and open
a follow-up Harness feature; do not hide it in a feedback average.

## Retained limits and evolution

The Python CLI remains the personal-use and recovery path. Current limitations
are BYOK, Apple Silicon/macOS 14+ only, manual install/update/rollback, no launch
at login, and explicitly trusted internal distribution. Possible future work
is either a separately planned Developer ID/notarization channel or a hosted
control plane with short-lived client credentials. Neither is implemented,
required for this portfolio, or implied by the current artifact.
