# F052 real-device acceptance

Date: 2026-07-17 (Asia/Singapore)

## Environment

- macOS built-in microphone and built-in speakers; no headphones.
- Google Chrome app mode launched by `python -m src.realtime_host.server --launch --real-microphone`.
- Model `gpt-realtime-2.1`, voice `marin`.
- The standard API key stayed in the Python process. The browser received only a server-minted ephemeral client secret.
- Chrome was armed once per host launch. Every session after that was started through `POST /api/simulate-wake`, with no further browser click.

## Repeated exclusive handoff

Five consecutive start/stop cycles completed. Each sanitized report showed this order:

1. `wake_microphone_closed`
2. `host_microphone_requested`
3. `host_microphone_acquired`
4. `host_connected`
5. `host_command: stop`
6. `host_stopped`
7. `wake_microphone_reopened`

All five host acquisitions reported `echoCancellation=true`, `noiseSuppression=true`, `autoGainControl=true`, `sampleRate=48000`, and `channelCount=1`. After every stop the coordinator returned to `wake_owned`, with `wake_microphone_open=true` and `active_session=false`. No cycle showed concurrent microphone ownership.

## Final no-autoplay-bypass trial

The final Chrome launch did not use `--autoplay-policy=no-user-gesture-required`. One Arm click unlocked capture/playback, then a simulated Python wake started WebRTC without another click. The remote track played through the built-in speakers.

Sanitized monotonic event times from the final trial:

- `4300403512`: wake microphone closed and start queued.
- `4300403517`: host microphone requested.
- `4300404017`: host microphone acquired with AEC/NS/AGC enabled, 48 kHz mono.
- `4300404570`: WebRTC connected.
- `4300409017`: long answer requested.
- `4300411857`: real user speech started during the long answer.
- `4300412011`: the old response completed with status `cancelled` (154 ms after speech detection); audible old output stopped promptly.
- `4300433261`: the response to the interrupting user turn completed.
- `4300443927`: stop queued.
- `4300444200`: browser host stopped tracks, peer, data channel, and remote audio.
- `4300444278`: Python wake microphone reopened.

The final state was `wake_owned`, `wake_microphone_open=true`, `active_session=false`. The result proves the tested device/session only; it does not claim universal immunity to speaker self-echo. A macOS `say` attempt was deliberately excluded as interruption evidence because active AEC removed it as system-playback echo.
