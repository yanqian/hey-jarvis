# Building Hey Jarvis: a local-first Mac voice assistant

## Why this project exists

Hey Jarvis has four practical goals: solve the owner's hands-free assistant
need, remain usable from the command line, build fluency with AI-assisted
engineering, become a concrete job-portfolio project, and gather feedback from
a small trusted group. It is deliberately not presented as a defensible SaaS
business. A platform-provided wake-word feature could reduce its product value;
the durable result is the architecture, testing discipline, and evidence.

## What was built

The accepted product is local-first and BYOK. Rust/Tauri owns native identity,
Keychain access, first-run state, app paths, diagnostics, and supervision.
WKWebView owns OpenAI Realtime microphone capture and playback. A packaged
Python 3.12 sidecar owns local wake inference, session coordination, language
behavior, and six allowlisted tools: calculator, weather, local time, foreign
exchange, stock quote, and conversation ending. The original Python CLI stays
independent as the simplest personal-use and recovery path.

Before wake, microphone audio is processed by the local wake detector. After a
wake, one unified WebRTC session provides conversation audio, follow-up turns,
and interruption. Saying goodbye tears down browser media before Python
reacquires the wake microphone. Credentials remain in macOS Keychain and are
passed to the sidecar over a bounded per-launch private bootstrap; the WebView
never receives the standard OpenAI key.

## From feasibility spike to product boundary

F086 was intentionally isolated under `spikes/tauri_realtime/`. It proved on an
Apple Silicon Mac that WKWebView could request and release microphone access,
play Realtime output, support natural interruption, and return microphone
ownership to Python. The production app did not import that code. F087–F091
then rebuilt the capability behind a typed protocol, product-owned UI, BYOK
onboarding, a pinned PyInstaller runtime, rotating redacted diagnostics, and a
bounded sidecar supervisor.

This separation was a deliberate engineering tradeoff: the spike answered
“can WKWebView do this?”, while the product work answered “can it fail closed,
recover, protect secrets, and be reproduced without a checkout or system
Python?”

## Failures that shaped the design

- A stale Chrome Realtime host produced doubled acknowledgement and playback.
  Closing the duplicate host proved that only one media owner may exist; the
  product app now supervises a single sidecar and owns the WebView lifecycle.
- Settings navigation initially raced sidecar startup and later exposed asset
  404 and capability-cookie `forbidden` failures. Durable native frontend
  history, a settings-return marker, and a one-time loopback capability fixed
  the actual causes rather than masking the symptoms.
- Keychain access prompted after installation because macOS had to authorize
  the stable service identity. The onboarding and internal-test guide now make
  that recovery explicit without exposing key values.
- Clearing diagnostics appeared not to work because the running app immediately
  created new lifecycle events. The UI semantics now distinguish deleting
  existing history from disabling future diagnostics; exported bundles remain
  intentionally separate.
- Packaging initially leaked repository build paths into the release binary.
  Release-only path selection and Rust source-path remapping turned the artifact
  scan into an enforced privacy/reproducibility boundary.

## Measured result and tradeoffs

The F092 internal artifact is version `0.1.0`, Apple Silicon only, macOS 14+,
45,439,075 bytes as a DMG, and about 104 MiB installed. Its 83 nested Mach-O
entries are arm64. It bundles Python, the TFLite wake runtime, required wake
models, audio dependencies, and the app in one atomic version. That footprint
is larger than a fully native implementation, but preserves the tested Python
assistant and avoids a separately installed runtime or model download.

The DMG is explicitly `INTERNAL-UNSIGNED`. It has no Developer ID distribution
identity, notarization ticket, Gatekeeper-readiness claim, automatic update, or
public download. Trusted testers receive the artifact and SHA-256 directly and
may use macOS **Open Anyway** after reviewing the source. Public binary
distribution stays on hold unless a future, separate signing/notarization
feature is planned and accepted.

## AI Agent Harness workflow

Repository files, not chat history, are the durable source of truth. Each
feature begins with a normalized SPEC and independently verifiable acceptance
criteria in `.agent-harness/feature_list.json`. Coding produces durable run
evidence but cannot mark itself complete. A separate cold-start Evaluator Agent
checks the feature, and `./init.sh` verifies the complete recovery contract.
This forced microphone, browser, provider, packaging, and human-device claims
to remain distinct from deterministic test evidence.

## What completion means

The portfolio is ready when the bounded demo and three privacy-safe trusted
trials pass without credential exposure, repeatable microphone ownership loss,
residual sidecars, crash loops, or unrecoverable onboarding. “Ready” means the
engineering narrative is public and the internal artifact is reproducible; it
does not mean the unsigned DMG is publicly distributed. The retained CLI is the
recovery path. Possible future work includes a signed/notarized channel or a
thin-client/cloud control plane, but neither is implemented or implied here.
