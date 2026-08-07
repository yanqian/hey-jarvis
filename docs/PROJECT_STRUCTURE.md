# Project structure

This repository keeps product code, verification code, evaluation data, and
local runtime output separate. The main directories are:

| Path | Purpose |
| --- | --- |
| `app/` | Tauri desktop app, native Rust shell, and packaged Sidecar. |
| `src/` | Python product runtime and reusable evaluation executors under `src/evals/`. |
| `tests/` | Main automated regression, contract, integration, packaging, and evaluator-oracle tests. |
| `app/sidecar/tests/` | Tests for the fake and product Sidecar boundary. |
| `evals/realtime/` | Realtime evaluation scenario definitions and schemas. |
| `artifacts/` | Curated audio fixtures and privacy-bounded evaluation evidence. |
| `assets/` | Canonical runtime audio assets packaged with the application. |
| `feedback/` | Trusted tester trial templates and approved feedback evidence. |
| `docs/` | Operator, architecture, testing, packaging, and troubleshooting guides. |
| `scripts/` | Build, packaging, verification, and maintenance commands. |
| `packaging/` | Sidecar build locks, PyInstaller configuration, and release metadata. |
| `spikes/` | Historical feasibility experiments; not part of the product runtime. |
| `.agent-harness/` | Harness state, prompts, evaluator records, and resumable agent history. |
| `tmp/` | Disposable runtime recordings and logs; never treat as source evidence. |
| `var/` | Disposable prepared runtime audio and local state. |
| `build/` | Ignored build output, sidecar environments, bundles, and internal releases. |

## Where tests and evaluations belong

Keep normal automated tests in `tests/`. Keep Sidecar-specific tests beside the
Sidecar because they run against a separate packaging and process boundary.

The Realtime evaluator implementation lives in `src/evals/` so it can be run
with commands such as `python -m src.evals.realtime_handoff`. The corresponding
scenario data stays in `evals/realtime/scenarios/`, while sanitized outputs go
under `artifacts/evaluations/realtime/`.

Harness run records belong only under `.agent-harness/runs/`. Historical records
from the former root-level `runs/` directory are retained under
`.agent-harness/runs/legacy-root-runs/`.
