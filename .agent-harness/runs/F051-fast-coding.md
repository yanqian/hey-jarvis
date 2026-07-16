# F051 Fast Coding Evidence

FAST_CODING_EVIDENCE: F051

CODING_PASS: F051

## Scope delivered

- Added a project-owned, loopback-only Python validation server under `spikes/realtime_webrtc/`.
- The standard `OPENAI_API_KEY` stays on the server. The browser receives only a short-lived Realtime client secret minted through the official client-secrets endpoint.
- Added a browser WebRTC probe that requests `echoCancellation`, `noiseSuppression`, and `autoGainControl`, publishes the local microphone track, plays the remote WebRTC audio track directly, and reports the browser's actual microphone track settings.
- Added deterministic Start/Stop resource cleanup, bounded sanitized event evidence, a copyable report, and a fixed long-answer action for repeatable barge-in timing.
- Kept the existing assistant runtime, wake flow, tools, routing, playback, and tracked defaults unchanged.

## Official external contract

- OpenAI's Realtime WebRTC guide recommends WebRTC for client devices, documents the server-minted ephemeral client-secret flow, and shows microphone/remote-audio transport over `RTCPeerConnection`: https://developers.openai.com/api/docs/guides/realtime-webrtc
- OpenAI's Realtime conversations guide documents that WebRTC/SIP sessions have server-managed output buffering and automatic truncation during interruption, unlike WebSocket clients that must manage playback position and truncation themselves: https://developers.openai.com/api/docs/guides/realtime-conversations#interruption-and-truncation

This evidence supports the public API contract only. It does not claim knowledge of the private implementation of the ChatGPT desktop or mobile applications.

## Automated verification

- `node --check spikes/realtime_webrtc/app.js`: pass.
- `.venv/bin/python -m unittest tests.test_realtime_webrtc_probe -v`: 6/6 pass.
- `.venv/bin/python -m unittest discover -s tests`: 229 tests pass before the final recovery run.
- `.venv/bin/python -m spikes.realtime_webrtc.server --check`: ready with credentials configured; no credential value printed.
- Final `./init.sh`: pass with all 229 project tests plus harness, compile, dry-run, and fake-backend recovery checks.

The focused tests cover credential requirements, official token request shape, returned-field redaction, loopback enforcement, static routing, capture-processing constraints, event bounds, deterministic cleanup, report guidance, and the fixed long-answer action.

## Real-device observations

Environment: Chrome on the project Mac, built-in MacBook Pro microphone, built-in speakers, no headphones, live OpenAI Realtime WebRTC session using `gpt-realtime-2.1` and voice `marin`.

Observed:

- WebRTC negotiation completed and a remote audio track arrived.
- Browser-reported active microphone settings were `echoCancellation=true`, `noiseSuppression=true`, `autoGainControl=true`, sample rate 48000 Hz, and one channel.
- Remote model audio played through the speaker path without local PCM forwarding or application-side output processing.
- Two normal user speech turns and completed assistant responses were observed with zero reported Realtime errors.
- The bounded report showed `speechStarted=2`, `speechDuringAssistant=0`, `cancelled=0`, and `errors=0` for that run.
- Stop was exercised and the Chrome microphone-recording indicator cleared.

Not proven:

- Those two turns did not overlap assistant playback, so they do not prove barge-in, prompt old-response stopping, or immunity from speaker self-echo under deliberate overlap.
- Chrome UI automation could not reliably reload the subsequently added fixed long-answer control. This is recorded as an inconclusive manual acceptance item, not as a pass.

The spike therefore validates the direct WebRTC transport and browser capture-processing premise, while leaving deliberate speakerphone barge-in as the remaining production decision gate.

## Safety and repository state

- Evidence contains no API key, ephemeral secret, raw audio, base64 audio delta, or transcript content.
- Existing untracked real-test logs under `tmp/` were not modified.
- No production dependency or runtime default was changed.
