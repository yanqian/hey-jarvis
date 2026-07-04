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

F010 has been completed through the orchestrator entrypoint, with the Coding Agent run recorded as an interactive manual fallback and the Evaluator Agent approving it. The code now includes live microphone wake debug output, WAV-file wake scoring, `WAKE_DEBUG=1` WAIT_WAKE score logging, PCM RMS/peak metrics, overflow surfacing from the microphone wrapper, README troubleshooting guidance, deterministic tests that do not require physical microphone access, and durable evaluator evidence in `runs/F010-evaluation.md`.

F011 has been implemented by manual fallback after the orchestrator Coding Agent adapter hung waiting for a child process, and evaluator-approved. The wake debug workflow now supports explicit live PCM capture to a mono 16 kHz 16-bit WAV file, high-precision score and threshold output, live and file replay summary metrics, deterministic short final chunk replay, README record-and-replay guidance, focused tests using generated fixtures and fakes without physical microphone access, and durable evaluator evidence in `runs/F011-evaluation.md`.

F012 has been completed through the orchestrator entrypoint, with Coding Agent implementation and Evaluator Agent approval recorded. The default wake phrase and openWakeWord model are now Alexa, wake model preparation and diagnostics target the Alexa ONNX asset plus feature models, runtime logs and README examples use Alexa as the accepted wake phrase, and focused tests cover Alexa loader arguments, score-key extraction, preparation paths, diagnostics, documentation, and recovery checks without physical microphone access. Durable evaluator evidence is recorded in `runs/F012-evaluation.md`.

Manual wake-word debugging after F012 showed the openWakeWord path is blocking the MVP: both the original Hey Jarvis model and the Alexa model failed to wake reliably in live use, and captured/TTS replay produced tiny scores far below useful thresholds despite valid 16 kHz mono int16 chunking. The next recovery direction is to stop tuning openWakeWord for the MVP and switch the active wake-word runtime to Picovoice Porcupine with a user-provided Picovoice AccessKey.

F013 has been completed through the orchestrator entrypoint, with Coding Agent implementation and Evaluator Agent approval recorded. The active wake-word path now uses Picovoice Porcupine with `PICOVOICE_ACCESS_KEY`, built-in keyword `jarvis`, configurable `PORCUPINE_SENSITIVITY`, engine `frame_length`, and engine `sample_rate`; openWakeWord, ONNX model preparation, and `onnxruntime` are no longer active-path requirements. Wake debug and WAV replay remain available with deterministic 0/1 Porcupine detection output and final short-frame padding. Durable evaluator evidence is recorded in `runs/F013-evaluation.md`.

F014 has been completed through the orchestrator entrypoint, with Coding Agent implementation and Evaluator Agent approval recorded. The active wake-word runtime has been restored to the previously accepted F012 Alexa/openWakeWord ONNX path after the user reported they cannot obtain a Picovoice AccessKey. The restored path includes ONNX model preparation, diagnostics, documentation, 1280-frame wake debug/replay behavior, and focused regression tests. This is a usability rollback that removes the Picovoice account capability gap from the active path; it does not fix the known Alexa low-score recognition behavior. Durable evaluator evidence is recorded in `runs/F014-evaluation.md`.

## Last Completed Feature

F014 - Restore Alexa wake-word runtime.

## Next Feature

None currently selected.

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
- F010 was completed through the orchestrator entrypoint after F009; implementation evidence is in `runs/F010-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F010` in `runs/F010-evaluation.md`.
- F011 orchestrator execution was attempted through `make work`, but the Coding Agent adapter hung inside `subprocess.communicate()` and was interrupted. Manual fallback preserved evaluator gating; implementation evidence is in `runs/F011-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F011` in `runs/F011-evaluation.md`.
- F012 was completed through the orchestrator entrypoint after waiting for the Coding Agent adapter to return. Implementation evidence is in `runs/F012-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F012` in `runs/F012-evaluation.md`.
- F013 replaced openWakeWord with Picovoice Porcupine because manual tests of both Hey Jarvis and Alexa did not produce a usable wake event. Porcupine introduces a new required user capability: `PICOVOICE_ACCESS_KEY` from Picovoice Console. Implementation evidence is in `runs/F013-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F013` in `runs/F013-evaluation.md`.
- F014 was completed through the orchestrator entrypoint because `PICOVOICE_ACCESS_KEY` is not currently obtainable by the user. The Porcupine account requirement is recorded as a capability gap in the abandoned Porcupine direction; F014 resolves it for the active MVP path by restoring Alexa/openWakeWord setup through durable requirements, diagnostics, documentation, and tests. Implementation evidence is in `runs/F014-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F014` in `runs/F014-evaluation.md`.
