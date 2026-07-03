# F001 Manual Fallback Run

Feature: F001 - Create Python project skeleton and recovery init

## Reason

The default orchestrator-first path was attempted with `make work`, but the repository has no commits yet. The orchestrator startup protocol runs `git log --oneline -20` with `check=True`, so it exited before selecting a feature.

No initial commit was created because commits require explicit user approval. Work continued as a manual fallback and was limited to F001.

## Changes

- Added project-owned skeleton files: `README.md`, `.env.example`, `requirements.txt`, `src/`, `tests/`, and `tmp/.gitkeep`.
- Added a dependency-free dry-run entrypoint with `python3 -m src.main --dry-run`.
- Updated root `./init.sh` to run harness verification plus project required-file checks, Python compilation, unit tests, and dry-run smoke verification.
- Expanded `.gitignore` for local environment files, Python caches, and generated audio artifacts.

## Verification

Command:

```bash
./init.sh
```

Result:

```text
init verification passed
project recovery verification passed
```

## Evaluation

The implementation satisfies all F001 acceptance criteria:

- Project-owned paths exist for `src/`, `tests/`, `README.md`, `.env.example`, `requirements.txt`, and `tmp/.gitkeep`.
- Root `./init.sh` still runs `.agent-harness/scripts/init.sh` and verifies project compile, tests, and dry-run smoke.
- The recovery check is idempotent, logs each phase, and uses `set -euo pipefail` to exit non-zero on failure.
- The dry-run smoke path exercises the current core entrypoint without microphone, speaker, or OpenAI access.
- README documents Python 3.11 or 3.12 as the supported MVP runtime.

EVAL_PASS: F001
