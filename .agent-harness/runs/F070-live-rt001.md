# F070 Authorized RT001 Live Evidence

Feature: F070 - Keep Realtime input-level diagnostics off the normal critical path

Scenario: RT001 version 5, normal path without optional input-level analysis

Authorization: the user explicitly authorized this F070/RT001 run to use the
microphone, send session audio and optional transcription to OpenAI, and incur
API charges. The authorization was consumed by this single run.

## Environment

- Built-in microphone and speaker through the armed Chrome Realtime host.
- Browser capture reported echo cancellation, noise suppression, and automatic
  gain control enabled, at 48 kHz mono.
- Existing private saved wake fixture; no fresh human speech was required.
- Evidence timestamp: `2026-07-24T08:50:18.135480+00:00`.

## Result

The automatic RT001 runner returned `result=passed` with:

- `connected=true`
- `exclusive_handoff=true`
- `recovered_to_wake=true`
- `audio_analysis_setup_ms=0`
- `input_level_cleanup_ms=0`
- `audio_context_creation_ms=0`
- `analyser_setup_ms=0`
- `media_stream_source_creation_ms=0`
- `source_connection_ms=0`
- `monitor_startup_ms=0`
- `peer_setup_ms=5`
- `total_browser_ready_ms=3105`
- `handoff_to_ready_ms=4055`
- `wake_to_ready_ms=5525`

The live loopback report independently showed final `state=wake_owned`,
`wake_microphone_open=true`, and ordered `host_stopped` followed by
`wake_microphone_reopened`. The test process was then stopped.

F069 measured `new AudioContext()`-dominated analysis setup of 4490 ms and
2831 ms in two same-page sessions. This F070 run removes that optional analysis
work from the normal path and measured only 5 ms for the remaining peer setup
subphases. This single run demonstrates the intended branch and is not a stable
latency percentile or SLO.

The saved machine-local evidence remains under `tmp/realtime-evals/` and is not
committed. This durable summary contains only allowlisted lifecycle verdicts and
rounded timing metadata; it contains no audio, transcript, utterance, answer,
credential, token, SDP, provider body, or private fixture content.

LIVE_PASS: F070 RT001
