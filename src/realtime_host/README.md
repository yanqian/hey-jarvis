# Realtime Chrome app-mode host

This is the production-path capability prototype for F052, not the F051 architecture spike. Chrome app mode is the smallest current macOS host because F051 already proved its WebRTC capture processing and server-managed interruption behavior. A packaged `.app` remains deferred.

Run the integrated assistant with `python -m src.main --backend realtime`. Click **Enable voice assistant** once per host launch to grant/unlock microphone and autoplay. The warm-up track is stopped before Python opens its wake microphone. Afterwards say the configured local wake phrase; each confirmed wake closes Python capture, plays the local acknowledgement, and starts one continuous WebRTC session without another browser click.

For host-only diagnostics, run `python -m src.realtime_host.server --launch --real-microphone`, then trigger a synthetic handoff from Python control:

`curl -X POST http://127.0.0.1:8770/api/simulate-wake`

The coordinator closes the Python `sounddevice` wake lease before issuing `start`. Stop with `curl -X POST http://127.0.0.1:8770/api/stop`; only after the host reports that tracks, peer, data channel, and audio are stopped does Python reopen the wake lease. Inspect bounded sanitized ordering evidence at `/api/report`.

Request the deterministic interruption prompt without refocusing the host window with `curl -X POST http://127.0.0.1:8770/api/long-answer`.

Manual acceptance uses the built-in microphone and speakers without headphones: run five start/stop cycles without clicking Arm again, confirm actual `echoCancellation`, `noiseSuppression`, and `autoGainControl`, request a long answer, interrupt it, and verify audible stopping plus no stuck microphone indicator. Permission denial, autoplay blocking, Chrome absence, API/network failure, and microphone reacquisition failure are capability failures; do not substitute WebSocket or local PCM playback.
