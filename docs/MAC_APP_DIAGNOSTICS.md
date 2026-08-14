# Mac App Diagnostics and Recovery

F091 keeps failures diagnosable without turning diagnostics into conversation
history. Rust/Tauri and the packaged Python sidecar write JSONL lifecycle
records under `~/Library/Application Support/com.heyjarvis.desktop/diagnostics/`.
Each writer rotates at 512 KiB and retains three prior generations. WebView
events cross a native allowlist; arbitrary JavaScript strings cannot be logged.

Wake-word tuning diagnostics are a separate, explicitly opt-in JSONL stream at
`~/Library/Application Support/com.heyjarvis.desktop/diagnostics/wake.jsonl`.
The Settings toggle defaults off. The same card exposes two bounded experiments:
score threshold `0.50` or `0.60`, and confirmation count `2` or `3` consecutive
frames. New and migrated installs retain the existing `0.50` / `2` behavior,
and Settings always displays the effective pair. Changing the toggle or either
tuning value safely pauses the sidecar. The
top-right action is always **Apply & Done**. If wake listening was active when
Settings opened, it restarts local listening with the new value and closes only
after `wake_listening` is confirmed. If the sidecar was ready but not listening,
it restores that ready state without arming the assistant. If the assistant was
already inactive, it closes Settings without starting it. When enabled, the stream
records only bounded numeric evidence for near-threshold frames, positive runs,
run resets, overflows, and confirmed wakes: score, configured threshold,
consecutive/required frame counts, RMS, and peak. It uses the same 512 KiB and
three-generation retention boundary. Each record includes the effective
threshold and required-frame count, so exported evidence identifies the exact
experiment. Low-score background frames are omitted,
and write failures never interrupt wake listening.

Records contain only schema version, timestamp, component, event, bounded
session correlation, and state. Credentials, authorization values, raw audio,
SDP/ICE, transcripts, answers, tool arguments, and provider request/response
bodies are excluded. The dedicated Privacy & Diagnostics Settings section can
export a versioned, size-bounded `hey-jarvis-support-v1` JSON bundle or clear
all local diagnostic generations after an explicit confirmation.
Exports are written under the app-owned `support-exports/` directory and must
pass the same forbidden-content scanner.

For tuning, enable the setting, collect a labeled conversational session and a
separate set of intentional wakes at normal distances, then export the support
bundle. Count conversational confirmed events as false accepts and intentional
attempts as recall trials. Compare candidate thresholds or confirmation-frame
counts offline before changing defaults. The diagnostic stream does not retain
audio, so label observation times while testing; it does not by itself prove an
accuracy improvement.

The conversation gear, tray **Settings…** item, and standard `⌘,` shortcut all
open or focus one local Settings window without navigating the conversation
window, releasing the Smart Speaker assertion, or stopping the sidecar. The
Settings banner reads live bounded availability and remains display-only. The
stable **Apply & Done** action closes only that window for runtime-neutral
inspection. A successful credential change or an explicit microphone check is
runtime-affecting: it uses the safe sidecar shutdown path, restores the prior
ready/listening intent when prerequisites remain available, and closes only
after that state is confirmed.

The native supervisor distinguishes intentional stops from unexpected exits.
An intentional permission, credential, sleep, or quit stop never restarts.
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
