# Realtime WebRTC speakerphone probe

This architecture spike tests whether the official OpenAI Realtime WebRTC media path is usable with the Mac built-in microphone and speakers without headphones. It does not integrate the wake word or change the existing pipeline.

## Run

From the repository root with the existing `.env`:

```bash
.venv/bin/python -m spikes.realtime_webrtc.server --check
.venv/bin/python -m spikes.realtime_webrtc.server
```

Open <http://127.0.0.1:8765>, press **Start Realtime session**, and grant microphone access. The standard `OPENAI_API_KEY` stays in the local Python process; the page receives only an ephemeral Realtime client secret.

Optional probe-only overrides:

```text
REALTIME_PROBE_MODEL=gpt-realtime-2.1
REALTIME_PROBE_VOICE=marin
```

## No-headphones trial

1. Select the Mac built-in microphone and built-in speakers in macOS.
2. Use a normal comfortable speaker volume and sit at a normal working distance.
3. Start the session and confirm that the page reports actual values for `echoCancellation`, `noiseSuppression`, and `autoGainControl`.
4. Press **Play long test answer** so the model counts slowly from one to twenty.
5. While the model is speaking, say “Stop. What is two plus two?”
6. Mark whether speaker echo caused a false interruption, whether the real interruption was detected, and whether the old answer stopped promptly.
7. Repeat at a lower and higher speaker volume if the first result is ambiguous.
8. Press Stop and confirm the browser microphone indicator turns off, then copy the sanitized report.

One successful run proves feasibility only for the tested browser, device, room, distance, and volume. It does not establish how the private ChatGPT App audio stack is implemented or guarantee a packaged WebView will behave identically.
