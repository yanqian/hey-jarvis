# Progress

## Current System Status

Project minspec has been accepted for a simple macOS voice assistant MVP named Hey Jarvis.

F001 created the project-owned Python skeleton and updated root `./init.sh` into a project recovery contract. The recovery check now verifies the harness, required project files, Python compilation, unit tests, and a dependency-free dry-run smoke path.

F002 has been implemented and evaluator-approved. The code now includes dependency-free configuration loading, typed validation, runtime diagnostics, CLI diagnostics output, documented `.env.example` settings, and focused unit tests.

F003 has been implemented by manual Coding Agent fallback and evaluator-approved. The code now includes a reusable `sounddevice` microphone stream wrapper, deterministic int16 PCM RMS silence detection, WAV recording to `tmp/input.wav`, synthetic-PCM tests that do not require real microphone access, and durable evaluator evidence in `runs/F003-evaluation.md`.

## Last Completed Feature

F003 - Implement audio stream, silence detection, and WAV recording.

## Next Feature

F004 - Implement Hey Jarvis wake-word detector.

## Known Issues

- F001 was completed by manual fallback before the initial commit because the orchestrator startup protocol treated empty `git log` as fatal; that fallback is recorded in `runs/F001-manual-fallback.md`.
- F002 implementation was completed by Coding Agent through the orchestrator provider. A later Evaluator Agent re-evaluation was run through `scripts/run-evaluator-agent.sh` and recorded `EVAL_PASS: F002` in `runs/F002-evaluation.md`.
- Runtime implementation should prefer Python 3.11 or 3.12; Python 3.14 may not be compatible with all audio and ML dependencies.
- Real microphone, speaker, and OpenAI integration cannot be fully verified by default automated checks; use fakes for recovery tests and document manual integration steps.
- macOS microphone permission must be granted to the launching terminal or agent surface before the real demo can run.
- F003 implementation was completed by manual Coding Agent fallback because this prompt was run interactively for a selected feature. Evaluator Agent review recorded `EVAL_PASS: F003` in `runs/F003-evaluation.md`.
