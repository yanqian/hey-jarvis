# F044 Evaluation Pass

Date: 2026-07-13

The cold-start evaluator reconstructed repository context from `AGENTS.md`, `.agent-harness/progress.md`, `.agent-harness/feature_list.json`, recent git history, and `./init.sh`, then inspected the normalized `SPEC.md` entry, fast-coding evidence, implementation diff, focused router and state-machine regressions, documentation updates, and workflow evidence for F044.

Evaluation confirmed that the calculator router now converts common Simplified and Traditional Chinese positional integers through thousands into safe numeric expressions, preserves the existing Chinese operator path, rejects ambiguous consecutive digit readings instead of guessing, and routes spoken requests such as `一加一等于几` and `一加一等於幾` to the local calculator without calling chat or mutating chat history. `./init.sh` passed end to end, and focused verification with `.venv/bin/python -m unittest tests.test_tools tests.test_state_machine tests.test_main` passed with 98 tests. Fast-work evidence correctly contains `FAST_CODING_EVIDENCE: F044` and `CODING_PASS: F044` without spoofing evaluator evidence.

EVAL_PASS: F044
