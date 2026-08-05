# Mac App Diagnostics and Recovery

F091 keeps failures diagnosable without turning diagnostics into conversation
history. Rust/Tauri and the packaged Python sidecar write JSONL lifecycle
records under `~/Library/Application Support/com.heyjarvis.desktop/diagnostics/`.
Each writer rotates at 512 KiB and retains three prior generations. WebView
events cross a native allowlist; arbitrary JavaScript strings cannot be logged.

Records contain only schema version, timestamp, component, event, bounded
session correlation, and state. Credentials, authorization values, raw audio,
SDP/ICE, transcripts, answers, tool arguments, and provider request/response
bodies are excluded. The dedicated Privacy & Diagnostics Settings section can
export a versioned, size-bounded `hey-jarvis-support-v1` JSON bundle or clear
all local diagnostic generations after an explicit confirmation.
Exports are written under the app-owned `support-exports/` directory and must
pass the same forbidden-content scanner.

The conversation gear, tray **Settings…** item, and standard `⌘,` shortcut all
resolve to the same Settings route. Entering that route intentionally stops the
sidecar before the non-listening banner is shown. The **Done** action explicitly
restarts the local runtime before returning to the conversation surface.

The native supervisor distinguishes intentional stops from unexpected exits.
An intentional Settings, permission, credential, or quit stop never restarts.
System sleep records only whether Smart Speaker Mode was genuinely active,
stops local media, and permits one bounded local-runtime recovery attempt after
wake. Browser re-arming must restore real `wake_listening` within 15 seconds;
otherwise the app remains truthfully non-listening and exposes focused Resume
and Settings actions. Neither path starts paid Realtime activity before a new
wake phrase. An unexpected child exit is retried at most three times with bounded
backoff; a fourth exit enters `crash_loop`, remains non-listening, and requires
an explicit user restart. Restarting restores local wake listening only and
never creates paid Realtime activity before a fresh wake phrase.

WebView `beforeunload`, `pagehide`, and freeze paths synchronously stop local
tracks, detach remote playback, and close the data channel and peer. Native app
exit and resume paths stop the sidecar, whose `finally` cleanup closes the
loopback server, coordinator, detector, and microphone ownership.

## Verification

- Rust tests cover redacted export, clear, intentional stop, unexpected exit,
  bounded restart, and crash-loop state.
- Python tests cover lifecycle-only diagnostics and forbidden event rejection.
- JavaScript syntax and contracts cover reload/freeze media release and the
  export/clear UI.
- `./init.sh` runs these checks with the full project and fake smoke paths.
- The F091 target-Mac acceptance record covers physical sleep/wake and three
  consecutive packaged-app launch/quit process-table checks.
