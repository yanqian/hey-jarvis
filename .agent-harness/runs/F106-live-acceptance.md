# Run Record: F106 - target Mac sleep recovery acceptance

## Summary

- Date: 2026-08-05 (Asia/Singapore)
- Agent role: owner-led target-Mac acceptance with provider-native observation
- Feature: F106
- Result: explicit sleep/wake recovery and post-recovery voice loop passed
- Build: current source Debug `.app`, bundled immediately before the trial

## Preconditions

- Smart Speaker Mode was enabled.
- The current Debug app showed `WAKE LISTENING`.
- Native diagnostics recorded `smart_speaker_assertion_acquired` with state
  `active` before the owner selected Apple menu -> Sleep.
- The owner performed the privacy- and system-sensitive sleep, wake, unlock,
  microphone-permission, and spoken-audio steps directly.

## Explicit Sleep And Automatic Recovery

The app-owned lifecycle diagnostics recorded this ordered sequence:

```text
1785901861120 system_will_sleep state=recovery_pending
1785901861121 smart_speaker_assertion_released state=system_sleep
1785901863148 sidecar_stopped state=non_listening
1785901872962 system_did_wake state=non_listening
1785901873041 sidecar_starting session=session-e9ead6bef6cc27f9becfb098e719a53b
1785901876857 sidecar_ready state=ready
1785901876857 voice_resume_arming state=bounded
1785901878867 smart_speaker_assertion_acquired state=active
1785901878868 voice_resume_completed state=wake_listening
```

Automatic recovery completed about 5.9 seconds after `system_did_wake`, within
the 15-second bound. No Resume click was used. The recovered loopback page was
the focused `#smart-speaker-resume` route and its accessible UI reported
`WAKE LISTENING` / `Waiting for “Hey Jarvis”`. Python health checks for the new
session continuously reported `wake_listening` after recovery.

## Settings And Voice Loop

- The recovered Home gear was the declarative
  `hey-jarvis://settings/open` link and opened the bundled Settings surface on
  the first click.
- Settings truthfully reported non-listening under the existing F095-F100
  lifecycle, and Done returned to Home. A fresh Enable action restored
  `WAKE LISTENING`.
- The owner then said the wake phrase, asked for the current time, heard the
  audible time answer, said the farewell phrase, observed the conversation end,
  and successfully woke the assistant again.
- No audio, transcript, answer text, credential, SDP, ICE, or provider body is
  retained in this evidence.

## Separately Tracked Existing Defect

Opening Settings exposed an existing sidecar-shutdown race: macOS generated a
Python `SIGSEGV` report in PortAudio's `OpenAndSetupOneAudioUnit` while the
intentional Settings stop was finalizing the interpreter. Matching crash
reports predate F106, and the F106 sleep teardown itself completed and recovered
as specified. The owner explicitly accepted committing F106 separately and
requested a new requirement that keeps the sidecar alive for ordinary Settings
use, pauses/rebuilds audio only for affected settings, and makes genuine
shutdown race-free. This defect is not hidden as completed F106 work.

## Acceptance Result

The required target-Mac explicit-sleep/wake trial, automatic recovery,
clickable Settings control, audible post-recovery answer, semantic farewell,
and subsequent wake all passed. F106 remains pending the required separate
cold-start Evaluator Agent.
