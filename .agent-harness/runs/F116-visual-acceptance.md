# F116 native fullscreen visual acceptance

Date: 2026-08-05

Artifact: `app/src-tauri/target/debug/bundle/macos/Hey Jarvis.app`

Screenshot: `.agent-harness/runs/F116-fullscreen-acceptance.jpeg`

## Observations

- Native fullscreen leaves visible space above both `Settings` and `Done`; neither is clipped.
- `ASSISTANT SETUP` and `POWER & WAKE` are absent from the rendered accessibility tree and screenshot.
- `Setup and start`, readiness, and both setup actions read as one continuous group with no internal divider.
- One quiet rule separates Setup from Smart Speaker Mode.
- `How sleep and wake work` remains directly attached to Smart Speaker Mode with no rule above it.
- A quiet rule immediately above `Local until you wake it.` separates the privacy note from the complete Smart Speaker group.
- No microphone button, credential action, paid session, or runtime mutation was invoked.

VISUAL_ACCEPTANCE_PASS: F116
