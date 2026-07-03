# Progress

## Current System Status

Project minspec has been accepted for a simple macOS voice assistant MVP named Hey Jarvis.

F001 created the project-owned Python skeleton and updated root `./init.sh` into a project recovery contract. The recovery check now verifies the harness, required project files, Python compilation, unit tests, and a dependency-free dry-run smoke path.

## Last Completed Feature

F001 - Create Python project skeleton and recovery init.

## Next Feature

F002 - Implement configuration loading and runtime diagnostics.

## Known Issues

- There are no commits yet in this repository, so `git log --oneline -20` reports that `main` has no commits.
- Orchestrator-first `make work` is blocked until the repository has at least one commit because its startup protocol treats empty `git log` as fatal; F001 was completed by manual fallback and recorded in `runs/F001-manual-fallback.md`.
- Runtime implementation should prefer Python 3.11 or 3.12; Python 3.14 may not be compatible with all audio and ML dependencies.
- Real microphone, speaker, and OpenAI integration cannot be fully verified by default automated checks; use fakes for recovery tests and document manual integration steps.
- macOS microphone permission must be granted to the launching terminal or agent surface before the real demo can run.
