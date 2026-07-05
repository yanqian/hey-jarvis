# SPEC

## F019 - Configure TTS vibe and speed

- Goal: Let Hey Jarvis users configure OpenAI text-to-speech voice style and playback speed through documented environment settings, matching the practical "vibe" controls exposed by OpenAI.fm through API-supported parameters.
- Scope included: `TTS_INSTRUCTIONS` for tone/style guidance, `TTS_SPEED` for generated audio speed, OpenAI speech request wiring, configuration validation, documentation, and focused tests.
- Scope excluded: A UI for selecting presets, custom voice creation or consent flows, Realtime API voice settings, post-processing generated audio with local DSP tools, and changing chat response content style.
- Core flows: A user sets `TTS_VOICE`, optional `TTS_INSTRUCTIONS`, and optional `TTS_SPEED` in `.env`; the assistant sends those values to the OpenAI speech endpoint when generating `tmp/output.mp3`; invalid speed values fail configuration before runtime.
- Constraints: Keep the existing `gpt-4o-mini-tts` default, keep `TTS_INSTRUCTIONS` optional because older TTS models do not support it, validate `TTS_SPEED` within the OpenAI speech API range of 0.25 to 4.0, and preserve dependency-free tests without live API calls.
- Ambiguities or assumptions: OpenAI.fm "vibe" is treated as an API `instructions` prompt rather than a distinct `vibe` parameter. Default instructions remain unset to preserve existing assistant behavior until the user opts in.
- Required capabilities: Existing OpenAI Python SDK boundary, local unit tests with fake SDK calls, and documentation updates; no new external services, credentials, or dependencies are required.
- Implementation paths: `src/config.py`, `src/openai_client.py`, `.env.example`, `README.md`, `DEPLOYMENT.md`, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `runs/`.
- Verification surface: Config tests for defaults, overrides, and invalid speed; OpenAI client tests for speech request shape with optional instructions and speed; documentation tests for new env keys; `./init.sh` recovery verification.

Decomposition: This is intentionally one feature because it is one coherent TTS request-shaping capability with one implementation boundary and one verification surface.
