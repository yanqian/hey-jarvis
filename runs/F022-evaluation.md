# F022 Evaluation

EVAL_PASS: F022

## Re-Evaluation

- Date: 2026-07-06
- Agent role: Evaluator Agent
- Feature: F022 - Add structured tool routing foundation
- Result: pass
- Failure domain: none
- Harness improvement: none required; the orchestrator-first failure and manual fallback are already recorded with evaluator gating preserved.

## Acceptance Review

- `src/tools` defines `ToolRoute`, `ToolResult`, deterministic routing, local time, safe calculator, and not-configured planned provider results without network calls.
- Router tests cover calculator, time, weather, stock, FX, none, ambiguous `苹果怎么样`, unsupported realtime `今天有什么新闻`, and supported planned-provider routing for latest stock requests.
- The post-transcription state-machine path uses structured tools when enabled, avoids chat for local calculator answers, and refuses unsupported realtime requests without chat fallback.
- `python -m src.main --text ...` prints input, route, params, tool result summary, and final answer without microphone, wake-word detection, TTS, playback, OpenAI, or network access.
- `.env.example`, README, DEPLOYMENT, and focused tests cover `ENABLE_TOOLS`, `TOOL_ROUTER_DEBUG`, safe calculator, local time, supported planned-provider categories, unsupported realtime behavior, and recovery through `./init.sh`.
- SPEC normalization includes goal, included scope, excluded scope, core flows, constraints, ambiguities or assumptions, required capabilities, implementation paths, and verification surface.
- Feature decomposition is acceptable because F022 is one local routing and answer-safety foundation; network-backed providers are explicitly deferred.
- Implementation is in project-owned `src/`, tests, docs, and config paths, not default examples.

## Commands

```bash
git log --oneline -20
./init.sh
python3 -m unittest tests.test_tools tests.test_main tests.test_state_machine tests.test_config tests.test_documentation
python3 .agent-harness/scripts/validate-feature.py F022 || .agent-harness/scripts/validate-feature.sh F022
python3 -m src.main --text "现在几点"
python3 -m src.main --text "今天有什么新闻"
python3 -m src.main --text "苹果怎么样"
python3 -m src.main --text "100加20是多少"
python3 -m src.main --text "苹果股价多少"
python3 -m unittest discover tests
python3 -m src.main --fake-backend
./init.sh
```

Result: all passed.
