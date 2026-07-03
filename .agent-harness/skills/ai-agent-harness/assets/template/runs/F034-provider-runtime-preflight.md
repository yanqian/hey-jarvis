# Run Record: F034 - provider runtime preflight

## Summary

- Date: 20260613
- Agent role: Manual Coding Agent fallback and Evaluator Agent fallback
- Feature: F034 Preflight provider runtime permissions
- Result: pass

## Repository State

- Starting commit: 9d5ae3f
- Ending commit: working tree
- Working tree status: F034 changes are unstaged and limited to provider runtime preflight implementation, docs, example config, tests, state, bundled skill template assets, and this run record.

## Commands Run

```bash
python3 -m unittest discover -s test/unit -p 'test_*.py'
./init.sh
```

## Evidence

- Tests: unit tests passed, including successful runtime checks, permission-required runtime check failures, and role-specific runtime check command selection.
- Tests: root `./init.sh` passed, including harness state validation, failure-domain checks, evaluator-evidence checks, syntax checks, examples, unit, contract, harness, and smoke layers.
- Logs: provider runtime permission failures now emit `PROVIDER_RUNTIME_PERMISSION_REQUIRED` with guidance for outer agent or user-approved escalated provider execution.
- Screenshots or traces: not applicable.
- External behavior verification: `codex exec --help` was checked locally on 2026-06-13 and documents stdin prompt handling, `$CODEX_HOME` configuration references, and `--ephemeral`; Claude Code and Cursor Agent runtime checks remain configuration entry points until their local behavior is verified.

## Failure Analysis

- Failure domain: none
- Failure summary: no failure found in this evaluator run.
- Harness improvement: provider runtime permission gaps are now detected during adapter preflight before feature state mutation, with a machine-readable escalation marker.
- Follow-up feature:

## Files Changed

- `scripts/run-agent-provider.py`
- `agent-provider.example.json`
- `docs/agent-provider-configuration.md`
- `docs/capability-gaps.md`
- `test/unit/test_scripts.py`
- `SPEC.md`
- `feature_list.json`
- `progress.md`
- `skills/ai-agent-harness/assets/template/scripts/run-agent-provider.py`
- `skills/ai-agent-harness/assets/template/agent-provider.example.json`
- `skills/ai-agent-harness/assets/template/docs/agent-provider-configuration.md`
- `skills/ai-agent-harness/assets/template/docs/capability-gaps.md`
- `skills/ai-agent-harness/assets/template/test/unit/test_scripts.py`
- `runs/F034-provider-runtime-preflight.md`

## Evaluator Result

```text
EVAL_PASS: F034
```

## Follow-Up

- Downstream installed projects can sync the harness provider runtime preflight files when they need orchestrator-first provider escalation behavior.
