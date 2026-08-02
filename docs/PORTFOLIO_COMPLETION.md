# Portfolio completion record

## Current decision: HOLD

The engineering narrative and 210-second demo plan are ready. One owner-led
Apple Silicon trial is recorded. F093 still requires a recorded demo and two
more explicitly trusted tester or distinct clean-profile trials. Run
`python3 scripts/verify_portfolio_completion.py --require-complete`; until it
returns `GO_INTERNAL`, the portfolio completion gate has not passed.

Public binary distribution is unconditionally **HOLD**. `GO_INTERNAL` means
only that the portfolio/demo and trusted-test evidence are complete; it never
authorizes posting the unsigned DMG for anonymous download.

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

## Feedback summary

The owner trial found real friction around Keychain authorization, microphone
permission recovery, settings navigation, stale duplicate Chrome audio, asset
routing, and diagnostics-clear semantics. Root causes were corrected and the
final internal artifact passed the bounded flow. Aggregate conclusions remain
on hold until two additional privacy-safe trials are recorded.

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
