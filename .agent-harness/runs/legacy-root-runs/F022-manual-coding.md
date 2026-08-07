# F022 Manual Coding Evidence

## Feature

F022 - Add structured tool routing foundation.

## Orchestrator Attempt

The orchestrator-first path was attempted with:

```bash
make -C .agent-harness work
```

The first unprivileged run failed with `PROVIDER_RUNTIME_PERMISSION_REQUIRED` because the Codex provider could not access its state/app-server runtime from the sandbox. The command was retried with approved escalated execution. The escalated orchestrator entered `Round 1: F022` and wrote partial F022 changes, but then hung waiting for the Coding Agent child process in `subprocess.communicate()`. The run was interrupted and completed by manual fallback, preserving the partial work and evaluator gating.

## Implemented

- Added `src/tools/` with route/result schemas, deterministic routing, realtime-sensitive detection, local time execution, safe calculator execution, text debug formatting, and not-configured/refusal results.
- Added `ENABLE_TOOLS` and `TOOL_ROUTER_DEBUG` configuration.
- Wired the state machine answer path through the structured tool boundary after transcription.
- Added `python -m src.main --text ...` for dependency-free route/result/answer inspection.
- Documented structured local tools, supported local behavior, planned provider categories, unsupported realtime refusal, and debug settings.
- Added focused tests for router behavior, safe calculator, local time, unsupported realtime refusal, text debug output, state-machine tool routing, config validation, documentation coverage, and smoke output.

## Verification

```bash
python3 -m unittest tests.test_tools tests.test_config tests.test_main tests.test_state_machine tests.test_documentation
python3 -m src.main --text "现在几点"
python3 -m src.main --text "苹果怎么样"
python3 -m src.main --text "今天有什么新闻"
python3 -m src.main --text "100加20是多少"
python3 -m src.main --text "苹果股价多少"
python3 -m src.main --text "latest AAPL stock price"
python3 -m unittest discover tests
python3 -m src.main --fake-backend
./init.sh
```

All verification passed.
