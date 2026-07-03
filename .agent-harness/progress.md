# Progress

## Current System Status

Project minspec has been accepted for a simple macOS voice assistant MVP named Hey Jarvis.

F001 created the project-owned Python skeleton and updated root `./init.sh` into a project recovery contract. The recovery check now verifies the harness, required project files, Python compilation, unit tests, and a dependency-free dry-run smoke path.

F002 has been implemented and evaluator-approved. The code now includes dependency-free configuration loading, typed validation, runtime diagnostics, CLI diagnostics output, documented `.env.example` settings, and focused unit tests.

F003 has been implemented by manual Coding Agent fallback and evaluator-approved. The code now includes a reusable `sounddevice` microphone stream wrapper, deterministic int16 PCM RMS silence detection, WAV recording to `tmp/input.wav`, synthetic-PCM tests that do not require real microphone access, and durable evaluator evidence in `runs/F003-evaluation.md`.

F004 has been implemented by manual Coding Agent fallback and evaluator-approved. The code now includes a lazy-loading openWakeWord `WakeWordDetector` boundary for the built-in Hey Jarvis model, threshold-based detection from PCM chunks, clear load and inference error logging, fake-model tests that do not require microphone input or installed ML dependencies, and durable evaluator evidence in `runs/F004-evaluation.md`.

F005 has been implemented by manual Coding Agent fallback and evaluator-approved. The code now includes a lazy-loading OpenAI client boundary for transcription, chat completions with bounded in-memory history, and text-to-speech MP3 output; tests verify request shape, response handling, output file writing, and actionable missing-credential errors without live API access, with durable evaluator evidence in `runs/F005-evaluation.md`.

F006 has been implemented by manual Coding Agent fallback and evaluator-approved. The code now includes macOS `afplay` playback, a WAIT_WAKE -> RECORDING -> TRANSCRIBE -> ASK_OPENAI -> TTS -> PLAYING -> WAIT_WAKE state machine, `python -m src.main` real runtime wiring, a dependency-free `--fake-backend` full-loop smoke path, focused unit tests, README real-demo instructions, and durable evaluator evidence in `runs/F006-evaluation.md`.

F007 has been implemented by manual Coding Agent fallback and evaluator-approved. The README now documents setup, virtualenv dependency installation, `.env` creation, `OPENAI_API_KEY`, macOS microphone permission, `afplay`, real-demo operation, troubleshooting, and post-MVP iterations; `tests/test_documentation.py` verifies documented CLI modes, `.env.example` keys, runtime requirements, and post-MVP TODOs stay in sync, with durable evaluator evidence in `runs/F007-evaluation.md`.

F008 has been implemented by manual Coding Agent fallback and evaluator-approved. The real wake-word path now explicitly uses openWakeWord ONNX models through `onnxruntime`, includes `python -m src.main --prepare-wake-word` to download the required ONNX model files, reports missing `onnxruntime` or model files through `--diagnose`, documents the preparation step, and includes regression tests plus durable evidence in `runs/F008-manual-coding.md`.

F009 has been implemented through orchestrator Coding Agent and evaluator-approved. The real assistant now constructs, loads, and warms the `WakeWordDetector` before opening the microphone stream; the default microphone chunk size is 1280 frames; preload logs are visible before listening begins; troubleshooting documents `WAIT_WAKE` microphone overflow; focused tests cover startup ordering, chunk sizing, documentation, and warmup without real microphone access; and durable evaluator evidence is recorded in `runs/F009-evaluation.md`.

## Last Completed Feature

F009 - Prevent wake-listening microphone overflow during model startup.

## Next Feature

None - all planned features are complete.

## Known Issues

- F001 was completed by manual fallback before the initial commit because the orchestrator startup protocol treated empty `git log` as fatal; that fallback is recorded in `runs/F001-manual-fallback.md`.
- F002 implementation was completed by Coding Agent through the orchestrator provider. A later Evaluator Agent re-evaluation was run through `scripts/run-evaluator-agent.sh` and recorded `EVAL_PASS: F002` in `runs/F002-evaluation.md`.
- Runtime implementation should prefer Python 3.11 or 3.12; Python 3.14 may not be compatible with all audio and ML dependencies.
- Real microphone, speaker, and OpenAI integration cannot be fully verified by default automated checks; use fakes for recovery tests and document manual integration steps.
- macOS microphone permission must be granted to the launching terminal or agent surface before the real demo can run.
- F003 implementation was completed by manual Coding Agent fallback because this prompt was run interactively for a selected feature. Evaluator Agent review recorded `EVAL_PASS: F003` in `runs/F003-evaluation.md`.
- F004 implementation was completed by manual Coding Agent fallback because this prompt was run interactively for a selected feature. Evaluator Agent review recorded `EVAL_PASS: F004` in `runs/F004-evaluation.md`.
- F005 implementation was completed by manual Coding Agent fallback because this prompt was run interactively for a selected feature. Evaluator Agent review recorded `EVAL_PASS: F005` in `runs/F005-evaluation.md`.
- F006 implementation was completed by manual Coding Agent fallback because this prompt was run interactively for a selected feature. Evaluator Agent review recorded `EVAL_PASS: F006` in `runs/F006-evaluation.md`.
- F007 implementation was completed by manual Coding Agent fallback because this prompt was run interactively for a selected feature. Evaluator Agent review recorded `EVAL_PASS: F007` in `runs/F007-evaluation.md`.
- F008 fixed a real-demo capability gap discovered by manual testing: the wake-word path had relied on openWakeWord defaults that were not recoverable on macOS Python 3.12 without extra model/runtime setup. Evaluator review recorded `EVAL_PASS: F008` in `runs/F008-manual-coding.md`.
- F009 was completed through orchestrator-first work after approving the Codex provider runtime permission gap. Evaluator Agent review recorded `EVAL_PASS: F009` in `runs/F009-evaluation.md`.
