# Run Record: F114 - target Mac Settings lifecycle

## Summary

- Date: 2026-08-05 (Asia/Singapore)
- Build: current-source Debug `.app`
- Result: PASS

## Runtime-neutral Settings trial

The app reached truthful `wake_listening` with Python PID 87782 and session
`session-b63348070cf583adb541bed08a9a40b1`. Opening Settings from the gear and
repeating Command-, kept one window titled `Hey Jarvis Settings`; repeated
entry focused that window instead of creating another runtime.

While Settings was open, Python PID and session were unchanged, the main
loopback runtime document remained in place, Wake listening remained active,
and the native Smart Speaker assertion stayed acquired. Settings reported the
same bounded availability without exposing conversation content. Done closed
only Settings and returned focus to a main window still showing Wake listening.

## Runtime-affecting trial

The explicit microphone check first invoked the documented safe-stop boundary.
Python recorded `shutdown_requested` followed by `process_stopped` about 220 ms
later, and Settings changed to `Resume required` with a focused
`Resume voice assistant` action. A successful permission check retained no
stream and kept Resume visible; a later automation-stalled permission prompt
motivated the final bounded 15-second timeout and late-stream cleanup.

The pre- and post-trial DiagnosticReports lists both contained the same six
Python reports and ended at `Python-2026-08-05-121108.ips`. No new
`OpenAndSetupOneAudioUnit` report or Python-exit system dialog appeared.

No audio, transcript, answer, credential, SDP, ICE, provider body, or other
conversation content was retained in this evidence.
