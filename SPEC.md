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

## F020 - Restore Hey Jarvis TFLite wake word

- Goal: Make the verified openWakeWord `hey_jarvis` TFLite model the default wake-word contract again so the assistant is invoked as Hey Jarvis rather than Alexa.
- Scope included: Default wake model and wake phrase configuration, wake detector constants and score-key behavior, model preparation and diagnostics expectations, runtime logs, README/deployment/manual-test instructions, `.env.example`, focused tests, and recovery smoke output.
- Scope excluded: Adding a new wake-word engine, changing post-playback suppression behavior, changing OpenAI transcription/chat/TTS behavior, changing microphone device selection, and committing local `.env` secrets or debug audio captures.
- Core flows: A fresh user copies `.env.example`, runs `python -m src.main --prepare-wake-word`, runs `python -m src.main --diagnose`, validates wake scores with `--wake-debug`/`--wake-file`, then says `Hey Jarvis, what is two plus two?` to complete the MVP loop; fake-backend smoke logs the configured Hey Jarvis wake phrase.
- Constraints: Keep `WAKE_BACKEND=openwakeword`, keep `WAKE_INFERENCE_FRAMEWORK=tflite`, keep the macOS ARM64 ONNX guard, keep the configurable `WAKE_MODEL`/`WAKE_PHRASE` override path, avoid requiring live microphone or OpenAI access in automated tests, and treat the user's successful manual Hey Jarvis validation as external behavior evidence.
- Ambiguities or assumptions: The requested "Alexa model" replacement means the wake-word model and phrase, not the OpenAI chat or TTS models. The user has already validated the local `hey_jarvis` TFLite path manually, so the project default can switch without introducing a new engine.
- Required capabilities: Existing openWakeWord TFLite runtime, model preparation download path for `hey_jarvis_v0.1.tflite`, local unit/documentation tests, `./init.sh`, and user-provided manual microphone validation evidence.
- Implementation paths: `src/wake_word.py`, `src/config.py`, `src/main.py`, `.env.example`, `README.md`, `DEPLOYMENT.md`, `MANUAL_TESTING.md`, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `runs/`.
- Verification surface: Focused config/wake-word/main/documentation tests, `python -m src.main --diagnose` with the local `.env`, `python -m src.main --wake-file tmp/input.wav`, and final `./init.sh` recovery verification.

Decomposition: This is intentionally one feature because it is one coherent wake-word default contract with one implementation boundary and one shared verification surface.

## F021 - Add wake acknowledgement before recording

- Goal: Make the Hey Jarvis interaction feel more like a conversational assistant by confirming wake-word detection with a short pre-generated acknowledgement before recording the user's actual question.
- Scope included: Configurable wake acknowledgement settings, a one-time acknowledgement audio preparation command, startup diagnostics for the prepared audio file, state-machine playback of the acknowledgement after wake detection, microphone draining before question recording, documentation, fake-backend smoke coverage, and focused tests.
- Scope excluded: Barge-in while the acknowledgement is playing, dynamic per-wake TTS generation, changing the Hey Jarvis wake model or threshold behavior, changing the recorder's existing silence and maximum-duration stop rules, multi-turn follow-up listening, and committing user-generated audio artifacts to the repository.
- Core flows: A user configures optional wake acknowledgement text and audio path, prepares the acknowledgement audio once, starts the assistant, says "hey jarvis", hears a short response such as "在呢", then asks the actual question; the assistant records the question with the existing silence and max-duration logic, answers, plays the answer, and returns to wake listening with the existing post-playback suppression. If acknowledgement playback is enabled but the prepared audio file is missing, diagnostics and startup guidance explain how to create it instead of silently generating TTS during every wake event.
- Constraints: Keep the acknowledgement short by default, default the acknowledgement text to "在呢", avoid adding a live OpenAI API call to each wake event, keep automated tests dependency-free with fake TTS/playback/microphone boundaries, preserve macOS `afplay` playback behavior, and ensure acknowledgement audio is not transcribed as part of the user's question.
- Ambiguities or assumptions: The default prepared file path is assumed to be `tmp/ack.mp3`; acknowledgement playback is blocking and must finish before recording begins; microphone residue after the acknowledgement should be drained for a small configurable window rather than treated as user speech; users can change the wording later through configuration without requiring a new feature.
- Required capabilities: Existing OpenAI TTS client boundary for one-time audio generation, existing player abstraction for local audio playback, local filesystem access to `tmp/ack.mp3`, deterministic fake backends for tests, and project documentation updates. No new external service beyond the existing OpenAI credential is required.
- Implementation paths: `src/config.py`, `src/main.py`, `src/state_machine.py`, `src/player.py` if needed, `src/openai_client.py` if the preparation command needs a small wrapper, `.env.example`, `README.md`, `DEPLOYMENT.md`, `MANUAL_TESTING.md`, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `runs/`.
- Verification surface: Config validation tests for wake acknowledgement settings, CLI tests for the acknowledgement preparation command using fake TTS, state-machine tests for `WAIT_WAKE -> ACK_PLAYING -> RECORDING`, tests proving acknowledgement playback/drain audio is not transcribed as the user question, documentation tests for the new settings and workflow, fake-backend smoke output, and final `./init.sh` recovery verification.

Decomposition: This is intentionally one feature because the preparation command, configuration, diagnostics, playback transition, microphone drain, tests, and documentation all support one coherent user-visible interaction: wake acknowledgement before question recording.
