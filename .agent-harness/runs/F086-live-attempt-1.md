# F086 Live Attempt 1

LIVE_USER_AUTHORIZED: F086
LIVE_RESULT: INCOMPLETE

## Scope

The user explicitly authorized one Apple Silicon built-in-microphone/speaker
Realtime trial on 2026-07-31. The run used the isolated
`spikes/tauri_realtime` app and spike-local ignored `.env`. No credential,
audio, transcript, SDP, provider body, or answer content was retained.

## Accepted evidence

- The isolated Python sidecar was ready on attempt 0 at 36 ms and reported
  OpenAI configured.
- WKWebView acquired a 48 kHz microphone track with
  `echoCancellation=true`. The strongest advertised `all` mode was unavailable,
  so the required `true` fallback was used. WKWebView did not report
  `noiseSuppression`, `autoGainControl`, or `channelCount`.
- The WebRTC peer reached `connected`, the remote audio track was attached,
  the transport opened, and `session_created` was recorded.
- A normal human turn produced bounded `speech_started` and `speech_stopped`
  evidence, followed by response and playback-start lifecycle evidence.
- During the requested long answer, the previous response completed with
  `status=cancelled` at 124060 ms. Human speech was then recorded at 124064 ms
  with `during_playback=true`, stopped at 125475 ms, and a new response entered
  `in_progress` at 125484 ms. This is accepted transport-level evidence that
  deliberate natural interruption worked.

## Incomplete boundary

The Mac automatically locked before the user could confirm the interrupted
answer audibly and before the UI `Stop and reacquire` action could run.
Computer Use correctly refused to unlock the Mac. To avoid leaving a
microphone or billable Realtime session active, the test app was terminated.
The external termination left the Python runtime orphaned, so that isolated
process was also explicitly terminated. A final process-table check found no
remaining Tauri or sidecar process.

This attempt does not establish audible-playback acceptance, normal UI media
release, or Python microphone reacquisition and therefore is not a live PASS.

## Corrective action

The sidecar now monitors its original supervising parent and shuts its server
down if the Tauri process disappears. A deterministic parent-loss regression
raises the Python test total from 8 to 9. `npm test` and
`npm run build:app` pass with the corrected app bundle.

## Remaining live gate

After the user unlocks the Mac, rerun the corrected bundle and require:

1. user confirmation that the normal and interrupted answers are audible;
2. `Stop and reacquire`;
3. `media_released=true`;
4. `reacquire_result ok=true`; and
5. no residual Tauri or Python process after normal app quit.
