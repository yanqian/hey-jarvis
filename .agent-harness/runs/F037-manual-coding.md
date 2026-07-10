# Run Record: F037 - manual coding fallback

## Context

- Feature: F037 - Add optional VAD-gated audio handling
- Base: stacked on F036 / `fix/armed-baseline-ack-guard`
- Workflow: evaluator-gated fast work attempted first
- Failure: both sandboxed and approved escalated `make -C .agent-harness work-fast` runs failed the configured Codex Evaluator Agent provider runtime check before coding handoff.
- Fallback: interactive provider-native coding; separate evaluator approval remains required.
- Failure domain: agent_workflow_gap
- Harness improvement: none in this product PR; the configured provider runtime failure is outside the VAD feature boundary and is durably recorded.

## Implementation

- Added `src/vad.py` with neutral disabled behavior, lazy optional WebRTC loading, 20ms frame classification, voiced ratios/counts, validation, and actionable errors.
- Added validated wake, ARMED, and recording VAD settings with default-disabled compatibility and conditional diagnostics.
- Added ARMED energy-plus-VAD gating and trigger/summary diagnostics without per-chunk log spam.
- Added optional openWakeWord `vad_threshold` forwarding and a clear incompatible-version error.
- Added backward-compatible recorder VAD parameters, hangover, non-voice endpointing, runtime wiring, and preserved legacy RMS behavior when disabled.
- Added README, environment, manual-test, and deterministic fake/synthetic coverage without live audio, OpenAI, playback, or network.

## Verification

- `python3 -m unittest tests.test_config tests.test_vad tests.test_state_machine tests.test_recorder tests.test_wake_word tests.test_main tests.test_documentation` -> 97 tests passed.
- `./init.sh` -> harness checks passed, 187 project tests passed, dry-run passed, and fake-backend passed with `vad_ratio=disabled` and F036 behavior intact.
- `python3 -m src.main --diagnose` executed without a code exception and reported expected host capability errors for Python 3.14 and uninstalled runtime packages; disabled VAD did not create a dependency error.
- `git diff --check` -> passed.

FAST_CODING_EVIDENCE: F037
CODING_PASS: F037
