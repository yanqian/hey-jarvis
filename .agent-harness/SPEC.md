# AI Agent Harness Template SPEC

## 1. Goal

Provide a minimal, copyable repository harness for controlled AI-assisted development with Codex, Claude Code, Cursor Agent, or similar coding agents.

The harness makes project state recoverable by storing requirements, feature state, progress, prompts, and validation scripts in files.

## 2. Scope

### Included

- Durable project instructions in `AGENTS.md`.
- Durable repository knowledge in `docs/`.
- Real-world usage notes that link the harness to projects it was extracted from.
- Evaluator quality criteria in `QUALITY.md`.
- Per-run evidence and handoff records in `runs/`.
- Failure-domain classification and harness improvement checks.
- Capability-gap handling rules that prevent agents from hiding missing tools, permissions, generators, dependencies, or environment setup behind local-only workarounds.
- Example-boundary rules that prevent agents from implementing project-level requirements inside default template examples.
- Proven agent guardrails for state safety, external behavior verification, and anti-patterns in `AGENTS.md`.
- Human-readable requirements in `SPEC.md`.
- Machine-readable feature state in `feature_list.json`.
- Human-readable recovery state in `progress.md`.
- A JSON Schema for feature state.
- Prompt templates for planning, work, continuation, and evaluation.
- Deterministic validation scripts.
- A clean-state command for resetting template project state after copying.
- A `Makefile` with common local and CI verification targets.
- A GitHub Actions workflow that runs harness verification on push and pull request.
- Public-facing README positioning for resumable AI coding projects.
- A new-project flow guide with a visual diagram that shows what the skill does and what humans must provide.
- OSS readiness files for licensing, contribution, security reporting, changelog, and issue triage.
- A distributable AI Agent Harness skill that can initialize projects, guide planning, implementation, evaluation, and commit approved work while preserving the repository protocol as the source of durable state.
- A test plan and dependency-free unit, contract, and smoke tests.
- Contract tests for AI agent obligations and harness boundaries.
- A vendor-neutral lightweight `orchestrator.py`.
- Orchestrator-first work entrypoint guidance so implementation and evaluation normally run through the orchestrator instead of ad hoc manual state edits.
- Configurable orchestrator agent provider selection for Codex, Claude Code, Cursor Agent, or another explicitly configured tool.
- A tiny runnable example proving the harness loop works.
- A dependency-free Go server example for service-style projects.

### Excluded

- Hard-coded vendor-specific automation that assumes one installed CLI for every user.
- Cloud deployment.
- CI provider configuration.
- Automatic commits.
- Implicit agent-provider guessing when multiple provider CLIs are available.

## 3. Core Concepts

### Spec First

New work is first written into `SPEC.md` so agents share a stable requirement source.

### Repository Knowledge Map

`AGENTS.md` acts as an entry point. Durable knowledge belongs in `docs/`, quality criteria belong in `QUALITY.md`, and run evidence belongs in `runs/`.

### Failure Improvement Loop

Failures are classified by domain and assessed for harness improvement. Failed or blocked run records must state the failure domain and whether the harness should be improved through docs, prompts, scripts, schemas, tests, or a follow-up feature.

The orchestrator writes a failed run record when unattended coding or evaluation fails. Unknown failure-domain fields intentionally fail validation until the failure is classified and the harness improvement assessment is recorded.

### Capability Gaps

When a required capability is missing, agents must make that gap explicit and durable instead of bypassing it. Required capabilities include tools, permissions, generators, dependencies, services, credentials, runtime settings, CI resources, and verification fixtures needed to implement or verify a feature.

Agents must verify the missing capability with real evidence, then either add a durable project capability such as setup documentation, scripts, adapters, fixtures, CI configuration, or tests; mark the feature blocked; or append a follow-up feature. Temporary workarounds are acceptable only when recorded as temporary and cannot justify marking a feature complete unless the missing capability is provided or explicitly scoped out.

### Example Boundaries

The default `examples/` tree is a harness demonstration surface, not the default place to implement project requirements. Examples may prove that verification works, show adaptation patterns, or be intentionally removed or replaced during fresh project setup.

Agents must not satisfy a project-level feature by modifying `examples/tiny-cli`, `examples/go-server`, or another default example unless the selected feature explicitly targets that example. New product requirements belong in project-owned source, contract, documentation, and test paths with `./init.sh` updated to verify them.

### Feature Tracked

Every executable unit of work is represented in `feature_list.json` with explicit state and acceptance criteria.

Feature count is determined by independently verifiable behavior and capability boundaries, not by how much text the user wrote. Planning must split broad requirements into multiple features when there are separate user-visible behaviors, required capabilities, implementation boundaries, risk domains, or verification surfaces. If a broad requirement stays as one feature, the planning output must explain why the work remains coherent and independently evaluable.

### Evaluator Gated

A feature is complete only when validation passes and an evaluator can justify the result against the acceptance criteria.

Completed features must have durable evaluator evidence. From the evaluator-evidence baseline onward, `status=done` and `passes=true` are valid only when a run record contains `EVAL_PASS: Fxxx` for that feature. This prevents verification commands alone from being mistaken for evaluator-gated completion.

### Orchestrated When Needed

`orchestrator.py` can preview or run the coding/evaluation loop for one unfinished feature at a time. It is intentionally vendor-neutral: `--dry-run` prints prompts, while `scripts/run-coding-agent.sh` and `scripts/run-evaluator-agent.sh` are the explicit role adapters downstream projects replace to connect Codex, Claude Code, Cursor Agent, or another tool.

### Orchestrator-First Work

Goal: make the orchestrator the default work entrypoint for implementing and evaluating one feature, so feature state transitions, attempts, evaluator gating, failure records, and run evidence are owned by one durable flow.

Included scope: update agent rules, skill workflows, README guidance, Makefile or script entrypoints, and contract tests so the normal "work one feature" path starts with the orchestrator. Manual Coding Agent work remains available only as an explicit fallback when adapters are not configured, unavailable, or the user asks for interactive/manual work.

Excluded scope: replacing the orchestrator with a vendor-specific runner, weakening evaluator evidence, automatically committing orchestrated work, or requiring unattended execution when no provider is configured.

Core flows: a user asks to work on the next feature; the documented default command runs one orchestrator round; the orchestrator selects one unfinished feature, invokes Coding Agent and Evaluator Agent adapters, and marks the feature done only after `EVAL_PASS: Fxxx`; if adapters are unavailable, the flow fails closed with clear recovery guidance instead of silently falling back to manual state edits.

Constraints: the startup protocol must still run before work, one feature is handled per round, evaluator evidence remains mandatory for done features after the baseline, manual fallback must be recorded as fallback rather than the default path, and project verification still ends with `./init.sh`.

Ambiguities or assumptions: "default" means default documented entrypoint and convenience target, not that every agent surface must be able to run unattended without adapter configuration.

Required capabilities: deterministic orchestrator command, role adapters, clear adapter-unavailable errors, docs and prompts that route work through the orchestrator first, and tests that lock the default path.

Implementation paths: `AGENTS.md`, `README.md`, `Makefile`, `docs/agent-workflow.md`, `skills/ai-agent-harness/`, bundled template files, `prompts/`, and contract tests.

Verification surface: `./init.sh`, contract tests for orchestrator-first language and targets, orchestrator dry-run checks, and feature validation for the new feature.

### Agent Provider Configuration

Goal: let downstream projects explicitly configure which agent provider the orchestrator adapters use, so Codex users can use Codex, Claude Code users can use Claude Code, Cursor users can use Cursor Agent, and no provider is chosen by unsafe guessing.

Included scope: define a durable provider configuration format, adapter behavior, provider validation, documentation, and tests for Codex, Claude Code, Cursor Agent, and custom providers. Configuration may support detection or recommendations, but execution must use an explicit configured provider.

Excluded scope: inventing unverified external CLI schemas, requiring every provider CLI to be installed on all machines, parsing assistant prose as structured output, or auto-selecting one provider when multiple candidates exist.

Core flows: a user configures a provider; the Coding Agent and Evaluator Agent adapters read the provider config; each adapter validates that the configured command is available and suitable; the orchestrator sends the role prompt on stdin; adapter failure exits non-zero with a capability-gap message; unconfigured provider state fails closed with setup guidance.

Constraints: external CLI flags, stdin behavior, output format, and exit-code semantics must be verified from real help output, official documentation, or captured logs before being trusted. Provider-specific parsing must use real-shaped fixtures, and unknown provider schemas must fail closed.

Ambiguities or assumptions: exact Claude Code and Cursor Agent command shapes are provider-specific external behavior and must be verified during implementation before being documented as executable defaults.

Required capabilities: provider config file or environment contract, adapter dispatch logic, provider validation command, setup documentation, failure messages, and regression tests for configured, unconfigured, missing-command, and ambiguous-provider cases.

Implementation paths: `scripts/run-coding-agent.sh`, `scripts/run-evaluator-agent.sh`, provider config docs or templates, `README.md`, `SPEC.md`, `docs/capability-gaps.md`, `docs/external-behavior.md`, `skills/ai-agent-harness/`, bundled template files, and tests.

Verification surface: `./init.sh`, unit or contract tests for provider configuration semantics, adapter failure-mode tests, and captured evidence or documented uncertainty for each trusted provider command shape.

### Final Role Verdict Normalization

Goal: make orchestrated role execution resistant to contradictory provider output where an agent echoes historical run evidence before returning a final verdict, or where a provider exits non-zero after producing a structured final pass verdict.

Included scope: parse Evaluator Agent output by the last matching `EVAL_PASS: Fxxx` or `EVAL_FAIL: Fxxx: <reason>` line for the selected feature; add optional Coding Agent structured verdict lines, `CODING_PASS: Fxxx` and `CODING_FAIL: Fxxx: <reason>`; allow the orchestrator to continue from a non-zero provider process exit only when the corresponding final structured role verdict is a pass for the selected feature; document provider responsibilities for preserving final role verdict lines; and keep the bundled skill template synchronized.

Excluded scope: inferring success from free-form assistant prose, old run records, source diffs, or test log tails; changing provider-specific CLI commands; guessing undocumented Codex, Claude Code, Cursor Agent, or custom provider schemas; automatically marking product features done without evaluator evidence; or implementing concurrent orchestration.

Core flows: an Evaluator Agent reads prior run records that include an old `EVAL_FAIL: Fxxx`, then emits a final `EVAL_PASS: Fxxx`, and the orchestrator accepts the final pass; an Evaluator Agent emits a final `EVAL_FAIL: Fxxx: <reason>` after earlier pass evidence, and the orchestrator rejects the feature; a Coding Agent emits `CODING_PASS: Fxxx` after intermediate failure output and the provider exits non-zero, and the orchestrator logs the contradiction and proceeds to evaluation; a provider exits non-zero without a matching structured pass verdict, and the orchestrator fails closed.

Constraints: verdict matching must be scoped to the selected feature ID; the orchestrator must not infer verdicts from assistant summaries or run-record prose; existing providers that return zero without `CODING_PASS` remain compatible; downstream hidden-layout installs must be able to receive the same file-level fix from the skill template.

Ambiguities or assumptions: some provider CLIs may return non-zero because an intermediate tool command failed even when the final agent message is successful; structured final verdicts are the durable boundary for normalization. Provider-specific task-complete event schemas are intentionally not parsed until verified and modeled as fixtures.

Required capabilities: unit tests that import orchestrator helpers directly and exercise real-shaped role output strings, documentation updates for provider wrapper behavior and final verdict preservation, and skill-template synchronization for `orchestrator.py`, `prompts/work.md`, provider docs, and unit tests.

Implementation paths: `orchestrator.py`, `prompts/work.md`, `docs/agent-provider-configuration.md`, `test/unit/test_scripts.py`, `skills/ai-agent-harness/assets/template/`, `feature_list.json`, `progress.md`, and `runs/`.

Verification surface: `python3 -m unittest discover -s test/unit -p 'test_*.py'`, `./init.sh`, and `scripts/validate-feature.sh F033`.

### Provider Runtime Preflight

Goal: verify that the configured Coding Agent or Evaluator Agent provider can actually start and access its required runtime resources before the orchestrator mutates feature state.

Included scope: add optional provider-agnostic `runtime_check_command`, `coding_runtime_check_command`, and `evaluator_runtime_check_command` configuration fields; run the selected runtime check during adapter preflight; classify permission failures with a machine-readable `PROVIDER_RUNTIME_PERMISSION_REQUIRED` marker; document that the outer agent or user must explicitly approve escalated provider runtime execution; and keep Codex, Claude Code, Cursor Agent, and custom provider configuration entry points available without guessing unverified commands.

Excluded scope: automatically escalating permissions, silently granting access to user-level provider state, parsing private provider task-complete schemas, or requiring Claude Code and Cursor Agent users to adopt Codex command shapes.

Core flows: a configured provider has no runtime check and existing command validation behaves as before; a configured runtime check passes and the orchestrator may mark one feature `in_progress`; a runtime check fails with `Operation not permitted`, state-file, or app-server permission output and the adapter exits before feature attempts are incremented; an outer agent sees `PROVIDER_RUNTIME_PERMISSION_REQUIRED` and asks the user to approve escalated provider runtime execution before retrying.

Constraints: runtime checks run without a shell, just like provider commands; selected provider commands must remain explicit string arrays; failed runtime checks must not be confused with business-code failure or evaluator rejection; provider-specific runtime behavior must be verified before being documented as executable defaults.

Ambiguities or assumptions: Codex documents `--ephemeral` and `$CODEX_HOME` behavior, but deeper state database and app-server schemas remain private and should not be parsed. Claude Code and Cursor Agent runtime checks are configuration entry points until their local CLI behavior is verified.

Required capabilities: adapter runtime-check dispatch, permission-error classification, regression tests for pass and permission-required paths, provider docs and example configuration, and bundled skill template synchronization.

Implementation paths: `scripts/run-agent-provider.py`, `agent-provider.example.json`, `docs/agent-provider-configuration.md`, `test/unit/test_scripts.py`, `skills/ai-agent-harness/assets/template/`, `feature_list.json`, `progress.md`, and `runs/`.

Verification surface: `python3 -m unittest discover -s test/unit -p 'test_*.py'`, `./init.sh`, and `scripts/validate-feature.sh F034`.

### Recoverable

Any session can resume by reading repository files and git history. Chat history is not required.

### Verified External Assumptions

When implementation relies on behavior outside repository code, agents verify that behavior through primary sources, real commands, official documentation, captured logs, or real-shaped fixtures before depending on it.

### Skill Assisted Workflow

The harness can also be used through a distributable skill. The skill is a convenience layer for humans and agents: it initializes or repairs harness files, routes new requirements through planning, routes implementation through one-feature Coding Agent work, routes verification through Evaluator Agent rules, and commits approved work only after explicit user satisfaction.

The skill must not become a hidden state store. `AGENTS.md`, `SPEC.md`, `feature_list.json`, `progress.md`, `docs/`, `QUALITY.md`, `runs/`, and git history remain the durable sources of truth.

### New Project Flow

New users need a single visual map for the first project run. The durable flow guide must show the path from skill invocation, harness initialization, minspec input, SPEC normalization, feature decomposition, runnable skeleton, provider configuration, `make work`, evaluator pass, `./init.sh`, and approved commit.

The flow guide must distinguish what the skill does from what the human must provide. Required human inputs include project location or install mode, minspec content, clarification for ambiguous requirements, provider choice, approval to run real agent work, and explicit approval before commit.

The guide must link to the detailed recovery, spec normalization, feature decomposition, provider configuration, evaluator evidence, and commit rules instead of duplicating the whole manual.

### Project Recovery Init

Installed user projects need a clear distinction between harness verification and project recovery. `.agent-harness/scripts/init.sh` verifies that the harness itself is installed, semantically valid, and runnable. The root `./init.sh` is the project recovery entry point.

Immediately after harness initialization, before a project minspec exists, root `./init.sh` may verify only the harness and must not claim that business code, services, dependencies, or smoke tests exist. Once a minspec is accepted, Planning Agent work must create a runnable-skeleton feature that turns root `./init.sh` into the project recovery contract: install dependencies, start required services, run at least one real smoke test for an endpoint or core function, emit clear logs, and fail with a non-zero exit code when recovery or verification fails.

Project recovery requirements belong in project-owned source, test, contract, and setup paths. Default harness examples can illustrate patterns but cannot satisfy project recovery for downstream projects.

### Spec Normalization

Planning Agent work must normalize vague user input into a concrete SPEC addition before appending feature entries. The normalized requirement must state the goal, included scope, excluded scope, core flows, constraints, ambiguities or assumptions, required capabilities, project-owned implementation paths, and verification surface.

The planner must not convert unclear phrases into executable features by guessing. If the requirement lacks enough detail to define core flows, constraints, or verification, the planner must ask for clarification, record explicit assumptions, mark the ambiguity as a planning risk, or create a capability, blocker, or follow-up feature instead of hiding the gap.

### Feature-Linked Commits

Approved feature commits must include their feature ID first in the commit subject using the format `Fxxx <Action> <concise summary>`. Batch commits may include multiple feature IDs only after explicit user approval. Non-feature commits must use a `No-feature:` subject so later analysis can distinguish repository maintenance from feature work.

The skill must also preserve the template's vendor-neutral boundary. Codex can load the skill through `SKILL.md`, but the bundled scripts, references, and workflow rules should remain usable by other agent tools.

Skill initialization and repair must be tested against realistic project states. Tests should cover `new`, `adopt`, `repair`, and `check` modes; default non-overwrite behavior for existing project files; repair completeness for missing harness files; complete diagnostic output from `check`; and version drift handling through template and installation manifests. A newly initialized project is considered a harness only when it can run the verification entry point and its state, scripts, prompts, docs, run templates, and workflow invariants are semantically valid, not merely when files exist.

Skill initialization supports installation layouts. The default `hidden` layout keeps root `AGENTS.md` and `init.sh` as thin entry points and stores harness state, prompts, docs, scripts, tests, runs, schemas, and examples under `.agent-harness/`. The `visible` layout keeps the current template-maintenance shape with harness files at the repository root. `check` and `repair` must preserve or infer the installed layout from `.agent-harness/manifest.json`.

Skill documentation must distinguish installed skill usage from manual script usage. Users should understand that installing the skill places `skills/ai-agent-harness/` under their skill directory, requires restarting the agent surface when applicable, and allows prompts such as `Use $ai-agent-harness to initialize this project.` Manual `python3 skills/.../init_harness.py` commands are repository-checkout or vendor-neutral fallback usage, not the primary installed-skill experience.

Skill installation documentation must avoid machine-specific absolute paths. It should use portable paths such as `~/.codex/skills`, `~/.claude/skills`, project `.claude/skills`, and Cursor project rules under `.cursor/rules`, and explain which entry point applies to Codex, Claude Code, Cursor, and manual fallback use.

### Layered Verification

The template keeps automated checks in explicit layers:

- Unit tests cover small deterministic helper behavior.
- Contract tests lock repository rules, schema shape, prompt requirements, and orchestrator command guarantees.
- Harness tests are reserved for project-level workflow behavior and are optional in the minimal template.
- Smoke tests run the template's main user-facing verification commands end to end.

### Hey Jarvis Wake-Word Runtime Recovery

Goal: make the real Hey Jarvis wake-word path recoverable on supported macOS Python 3.11/3.12 environments by using openWakeWord's ONNX runtime path and explicit ONNX model preparation before microphone capture starts.

Included scope: project-owned wake-word model loading, explicit wake-word model preparation, diagnostics, setup documentation, troubleshooting, unit tests, and harness state for the bugfix.

Excluded scope: changing the accepted wake phrase, adding custom wake-word models, replacing openWakeWord, making live OpenAI calls in automated tests, or automatically granting microphone permissions.

Core flows: a user installs requirements, runs a preparation command to download the required openWakeWord ONNX model assets, runs `python -m src.main --diagnose` and sees wake-word readiness, starts `python -m src.main`, says `Hey Jarvis`, and the assistant can proceed past wake-word model loading.

Constraints: the MVP remains macOS-focused, supports Python 3.11 or 3.12, uses dependency-free fake-backend tests for recovery, avoids real microphone/OpenAI/speaker use in automated tests, and does not hide network/model download requirements behind local-only setup.

Ambiguities or assumptions: openWakeWord 0.6.0 exposes official ONNX assets corresponding to the built-in `hey_jarvis` model, and `onnxruntime` is the portable runtime for this macOS MVP. If model download is blocked by network policy, diagnostics must report the missing files and the preparation command rather than treating the app as ready.

Required capabilities: installed `openwakeword` and `onnxruntime`, network access during explicit model preparation, write access to the active virtualenv package model directory, an OpenAI API key for the later real assistant stages, and macOS microphone permission for live capture.

Implementation paths: `src/wake_word.py`, `src/config.py`, `src/main.py`, `README.md`, `requirements.txt` if needed, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: unit tests for wake-word ONNX loading and diagnostics, parser/documentation tests for the preparation command, dependency-free `./init.sh`, and optional manual `python -m src.main --prepare-wake-word` followed by `python -m src.main --diagnose` in a real venv.

### Hey Jarvis Wake-Listening Overflow Recovery

Goal: reduce real wake-listening failures where the assistant logs microphone input overflow during `WAIT_WAKE` and misses the user's wake phrase.

Included scope: wake-word model preload order, microphone chunk sizing, runtime logs, troubleshooting documentation, tests, and harness state for the bugfix.

Excluded scope: changing the wake-word model, adding custom wake words, tuning OpenAI request behavior, implementing a full audio latency profiler, or guaranteeing reliable recognition across every microphone and room condition.

Core flows: a user starts `python -m src.main`; the assistant prepares the wake-word detector before opening the microphone stream; microphone capture starts only after the model is ready; WAIT_WAKE reads 1280-frame chunks aligned with openWakeWord's prediction frame; if overflow still occurs, documentation points the user toward processing-lag and microphone/device recovery steps.

Constraints: automated tests must not require a real microphone, live OpenAI calls, or speaker playback; the project remains Python 3.11/3.12 and macOS-focused; fake-backend recovery must stay dependency-free.

Ambiguities or assumptions: the observed overflow is most likely caused by doing ONNX model initialization/warmup while the microphone stream is already active, and aligning chunks to openWakeWord's 1280-sample frame is a safer default than the previous 1024-frame block. Some host-specific device overflows may still need future tuning.

Required capabilities: prepared ONNX wake-word model files, installed `onnxruntime`, a microphone with macOS permission, deterministic tests that can verify operation ordering through fakes, and root recovery tests.

Implementation paths: `src/audio_input.py`, `src/wake_word.py`, `src/main.py`, `README.md`, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: unit tests for microphone defaults and preload ordering, full `./init.sh`, and optional manual real-demo observation that the model-preload log appears before WAIT_WAKE listening.

### Hey Jarvis Wake Debug Probes

Goal: make wake-word failures observable so a user can tell whether the assistant is blocked by microphone input, PCM levels, openWakeWord scores, threshold selection, or a state-machine path.

Included scope: CLI debug commands for live microphone wake-word scoring and WAV-file wake-word scoring, environment-backed wake debug logging, documented output fields, and tests that verify output shape without requiring a real microphone or live model.

Excluded scope: changing the wake-word model, adding a custom wake phrase, automatically tuning thresholds, making OpenAI calls, recording long-term audio logs, or requiring automated tests to access a physical microphone.

Core flows: a user runs `python -m src.main --wake-debug` and sees repeated `rms`, `peak`, `overflow`, `score`, and `threshold` values while speaking; a user runs `python -m src.main --wake-file path.wav` and sees per-frame or summary wake scores for a saved clip; a user sets `WAKE_DEBUG=1` and sees wake-score logs during normal `WAIT_WAKE` listening.

Constraints: debug output must avoid printing audio samples or transcriptions, tests must use fakes or generated WAV fixtures, normal assistant behavior must remain unchanged unless debug mode is requested, and the existing fake-backend recovery path must remain dependency-free.

Ambiguities or assumptions: live microphone debugging is inherently manual because physical devices and macOS permissions vary. The project can still provide deterministic tests for formatting, score extraction, and CLI routing.

Required capabilities: existing microphone stream, openWakeWord ONNX detector, WAV fixture handling, CLI parser support, and deterministic fake detector/model tests.

Implementation paths: `src/config.py`, `src/main.py`, `src/wake_word.py`, `README.md`, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: focused unit tests for debug CLI modes and output fields, generated WAV fixture tests, full `./init.sh`, and manual execution of `python -m src.main --wake-debug` when microphone access is available.

### Hey Jarvis Wake Debug Capture Replay

Goal: make live wake-word debug sessions reproducible by saving the exact microphone PCM chunks that were scored, reporting enough score precision to distinguish tiny non-zero outputs from true zeros, and summarizing the maximum observed score.

Included scope: a live wake-debug save flag that writes a mono 16 kHz 16-bit WAV file, higher-precision wake score output, summary metrics for live and file debug modes, graceful interruption handling for live debug capture, README guidance for record-and-replay debugging, and deterministic tests.

Excluded scope: changing the wake-word model, replacing openWakeWord, adding custom wake phrases, automatically tuning `WAKE_THRESHOLD`, storing long-term audio logs, transcribing debug audio, or requiring automated tests to use a physical microphone.

Core flows: a user runs `python -m src.main --wake-debug --wake-debug-output tmp/wake-debug.wav`, says `Hey Jarvis`, stops the command, and receives a saved WAV plus a max-score summary; the user then runs `python -m src.main --wake-file tmp/wake-debug.wav` to replay the exact captured audio and compare scores; short or final partial WAV chunks are handled without being silently ignored.

Constraints: saved debug audio is an explicit user-requested artifact only, uses the configured sample rate and mono int16 PCM, keeps OpenAI and playback disabled, remains dependency-light, and preserves the existing fake-backend recovery path.

Ambiguities or assumptions: local microphone behavior cannot be fully automated; tests will verify capture/replay mechanics using fake chunk sources and generated WAV files. Very low openWakeWord scores may still indicate model mismatch, pronunciation mismatch, input-device quality issues, or a need for a future custom wake model.

Required capabilities: existing microphone stream abstraction, wake detector scoring, WAV writing and reading, CLI parser support, README documentation, and fake audio fixtures for automated verification.

Implementation paths: `src/main.py`, `src/wake_word.py`, `README.md`, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: unit tests for saved live debug WAV output, precise score formatting, summary metrics, file replay of short chunks, parser flags, full `./init.sh`, and optional manual execution of live capture followed by wake-file replay.

### Alexa Wake-Word Model Switch

Goal: replace the unreliable built-in `hey_jarvis` wake-word path with openWakeWord's built-in `alexa` model so the assistant has a more practical default wake phrase for local demos.

Included scope: default wake phrase, openWakeWord model name and model key, score-key handling, ONNX model preparation paths, diagnostics for missing model assets, README setup/debug instructions, `.env.example`, and tests that prove the project loads and prepares the Alexa model without requiring a physical microphone.

Excluded scope: training a custom wake-word model, supporting multiple simultaneous wake models, adding runtime model selection UI, changing OpenAI transcription/chat/TTS behavior, or guaranteeing recognition in every room and microphone setup.

Core flows: a user runs `python -m src.main --prepare-wake-word` to prepare the Alexa ONNX model assets, runs `python -m src.main --diagnose` and sees wake-word readiness, runs `python -m src.main --wake-debug --wake-debug-output tmp/alexa-debug.wav`, says `Alexa`, sees score/debug output for the Alexa model, then starts `python -m src.main` and uses `Alexa` as the wake phrase.

Constraints: the project remains macOS-focused, Python 3.11/3.12-compatible, ONNX-runtime based, and dependency-free for automated recovery tests; tests must use fakes or metadata stubs instead of live microphone input; existing F010/F011 debug tools must keep working with the new score key.

Ambiguities or assumptions: openWakeWord 0.6.0 includes a built-in `alexa` model and corresponding ONNX asset URL. Alexa is chosen as the single MVP default because empirical debugging showed the built-in `hey_jarvis` model returned extremely low scores for both user and synthetic recordings.

Required capabilities: installed `openwakeword` and `onnxruntime`, explicit model preparation with network access when assets are missing, deterministic tests for model-name arguments and model-path diagnostics, and manual microphone permission for real runtime testing.

Implementation paths: `src/wake_word.py`, `src/config.py`, `README.md`, `.env.example`, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: focused unit tests for Alexa model constants, loader arguments, preparation paths, diagnostics, documentation, and debug score-key extraction; full `./init.sh`; optional manual `python -m src.main --prepare-wake-word`, `--diagnose`, and `--wake-debug` with the Alexa phrase.

## 4. Acceptance Criteria

- `./init.sh` validates harness state and runs the tiny example tests.
- `scripts/validate-feature.sh F001` validates a feature by ID and runs the default verification entry point.
- `scripts/summarize-progress.sh` prints a concise status summary.
- Contract tests statically verify the orchestrator CLI and startup contract.
- The documented default one-feature work entrypoint runs through the orchestrator before manual fallback.
- Orchestrator agent providers are explicitly configurable and fail closed when unconfigured, missing, or ambiguous.
- Contract tests verify AI-facing obligations for state safety, external behavior verification, prompt restrictions, and evaluator gating.
- `feature_list.json` conforms to `schemas/feature_list.schema.json`.
- `prompts/plan.md`, `prompts/work.md`, `prompts/continue.md`, and `prompts/evaluate.md` define the standard agent roles.
- The tiny example can be tested without installing third-party dependencies.
- The Go server example can be tested with `go test ./...` when Go is installed.
- `AGENTS.md` includes external behavior verification and external tool schema guardrails.
- `docs/capability-gaps.md`, prompts, and contract tests require missing capabilities to become durable setup, tests, docs, adapters, CI configuration, blocked state, or follow-up features instead of local-only bypasses.
- `docs/example-boundaries.md`, prompts, and contract tests require project-level requirements to land outside default examples unless the feature explicitly targets example maintenance.
- Root `./init.sh` behavior for installed projects distinguishes harness verification from project recovery and requires a runnable skeleton after minspec acceptance.
- Planning governance requires minspec-to-SPEC normalization with explicit goal, included scope, excluded scope, core flows, constraints, ambiguities, capabilities, implementation paths, and verification surface before feature entries are appended.
- `./init.sh` runs unit, contract, smoke, and optional harness tests.
- `docs/README.md`, `QUALITY.md`, and `runs/RUN_TEMPLATE.md` are present and validated.
- `scripts/check-failure-domains.sh` verifies failed run records include failure-domain and harness-improvement fields.
- Evaluator-evidence checks prevent done features after the enforcement baseline from lacking an `EVAL_PASS: Fxxx` run record.
- `make ci` runs the CI verification path.
- `.github/workflows/ci.yml` runs `make ci` on GitHub Actions.
- `make clean` resets `feature_list.json`, `progress.md`, and recorded run artifacts for a fresh project.
- README explains the project as a repository-level harness for resumable AI coding, not a prompt collection.
- README links to the new-project flow guide and the guide includes a visual diagram of the skill-assisted path.

## Project Requirement: Simple Mac Voice AI Assistant MVP

### Goal

Build a simple macOS-based voice assistant named Hey Jarvis that runs continuously, listens locally for a wake word, records a spoken question, transcribes it with OpenAI speech-to-text, asks an OpenAI text model for a short answer, converts the answer to speech, plays it through the Mac speakers, and returns to wake-word listening.

The first working demo should support:

```text
User: "Hey Jarvis, what is two plus two?"
Assistant: "Two plus two is four."
```

### Scope Included

- Python application launched with `python -m src.main`.
- macOS local runtime with continuous microphone input and speaker playback.
- One microphone stream opened at startup and reused while the process runs.
- 16 kHz mono int16 PCM audio handling.
- Built-in openWakeWord wake-word detection for `hey jarvis`.
- Simple RMS silence detection for the MVP.
- Recording user speech to `tmp/input.wav`.
- OpenAI speech-to-text, chat response generation, and text-to-speech.
- Short in-memory conversation history for the current process.
- Blocking playback through macOS `afplay` for the MVP.
- Clear logging of state transitions and major events.
- README setup, run, permissions, and iteration notes.

### Scope Excluded

- MCP, agent frameworks, tool calling, browser automation, computer control, calendar, Gmail, HomeKit, long-term memory, user login, and web UI.
- Custom wake words such as `Hey Armstrong` or Chinese wake words in the MVP.
- Interrupting assistant playback in the MVP.
- Follow-up conversation window without wake word in the MVP.
- Packaging as a launch daemon, menu bar app, signed app, or installer.
- Cloud deployment or hosted service runtime.

### Core Flows

1. Startup loads configuration, opens the microphone once, initializes wake-word detection, and enters `WAIT_WAKE`.
2. In `WAIT_WAKE`, incoming PCM chunks are checked locally by openWakeWord until `hey jarvis` crosses the configured threshold.
3. On wake detection, the assistant transitions to `RECORDING`, collects PCM chunks, stops on configured silence duration or maximum record duration, and writes `tmp/input.wav`.
4. The assistant transcribes the WAV file, sends the transcript plus short history to OpenAI, receives text, generates `tmp/output.mp3`, plays it with `afplay`, and returns to `WAIT_WAKE`.
5. Errors from audio, missing credentials, OpenAI calls, TTS, or playback are logged clearly and do not leave the state machine in an ambiguous state.

### Constraints

- The MVP should prefer Python 3.11 or Python 3.12 because audio and ML dependencies may lag the newest Python release.
- The runtime target is macOS with microphone permission granted to the launching terminal or agent surface.
- Audio chunks must remain compatible with openWakeWord expectations: 16-bit, 16 kHz, mono PCM.
- OpenAI API usage requires `OPENAI_API_KEY` in environment or `.env`.
- The first wake-word implementation uses an openWakeWord built-in `hey jarvis` model; custom model loading is deferred.
- Playback may be blocking in the MVP.
- Automated verification should not require a real microphone, real speaker, or live OpenAI API unless an explicit integration command is run.
- Project implementation belongs in project-owned paths such as `src/`, `tests/`, `README.md`, `.env.example`, and root `./init.sh`, not in default harness examples.

### Ambiguities Or Assumptions

- Assumption: the accepted MVP wake phrase is `Hey Jarvis`, replacing the original example wake word `Computer`.
- Assumption: Chat should use a small OpenAI text model configured by environment, with `gpt-4o-mini` as the initial default unless implementation-time documentation indicates a better current choice.
- Assumption: speech-to-text and TTS model names should be configurable, with documented defaults and fallbacks based on current OpenAI SDK support.
- Assumption: first-party OpenAI APIs are the only remote service in scope.
- Planning risk: local dependency installation can fail on unsupported Python versions or missing native audio libraries; this must be surfaced as a capability gap, not hidden behind manual local workarounds.
- Planning risk: macOS microphone permission cannot be fully granted by automated tests and must be documented with a diagnostic path.

### Required Capabilities

- Python 3.11 or 3.12 local runtime and virtual environment support.
- Installable Python packages for audio capture, numeric processing, OpenAI SDK, wake-word inference, and dotenv loading.
- macOS microphone permission for the launching process.
- macOS `afplay` for playback.
- `OPENAI_API_KEY` with access to configured speech-to-text, text, and TTS models.
- Offline unit-test fixtures or fakes for audio chunks, silence detection, recorder output, OpenAI client boundaries, playback subprocess calls, and state transitions.
- Optional manual integration path for microphone, wake word, OpenAI, TTS, and speaker playback.

### Implementation Paths

- `README.md`
- `.env.example`
- `requirements.txt`
- `src/main.py`
- `src/config.py`
- `src/audio_input.py`
- `src/wake_word.py`
- `src/recorder.py`
- `src/silence.py`
- `src/openai_client.py`
- `src/player.py`
- `src/state_machine.py`
- `tests/`
- `tmp/.gitkeep`
- root `./init.sh`

### Verification Surface

- `./init.sh` runs harness verification plus project recovery checks after the runnable skeleton feature is implemented.
- Unit tests cover configuration loading, silence detection, WAV saving with synthetic PCM, wake-word wrapper behavior with fakes, OpenAI client call boundaries with mocks, playback subprocess invocation, and state transitions.
- Static import and compile checks verify the Python package can start without syntax errors.
- A dry-run or fake-backend smoke path verifies the state machine without requiring a microphone or OpenAI credentials.
- README documents a manual integration command for the real microphone and OpenAI demo.

### Decomposition Decision

The MVP is split into separate features because it crosses distinct capability and verification boundaries: project recovery, configuration/runtime diagnostics, audio capture, wake-word inference, OpenAI integration, state-machine integration, and documentation. A runnable-skeleton feature comes first because this project now has an accepted minspec and root `./init.sh` must become the recovery contract before product behavior is treated as complete.
- README and `docs/real-world-usage.md` link real projects that informed the harness design.
- `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, and GitHub issue templates are present.
- `skills/ai-agent-harness/` contains a distributable skill with initialization, planning, one-feature work, evaluation, and explicit finalize-and-commit workflows.

### Porcupine Wake-Word Runtime Switch

Goal: unblock the macOS MVP wake-word path by replacing the openWakeWord runtime with Picovoice Porcupine as the default wake detector.

Included scope: record the openWakeWord blocker discovered during manual testing, remove openWakeWord and ONNX-specific setup from the active runtime, add a Porcupine-based `WakeWordDetector`, configure Picovoice AccessKey and built-in keyword settings, update diagnostics, README, `.env.example`, requirements, wake debug behavior, and deterministic tests.

Excluded scope: training a custom Porcupine `.ppn` model, supporting multiple simultaneous wake-word providers, adding cloud-hosted wake-word detection, changing OpenAI transcription/chat/TTS behavior, committing local debug audio, or requiring automated tests to use a real microphone or a real Picovoice AccessKey.

Core flows: a user installs requirements, adds `PICOVOICE_ACCESS_KEY` to `.env`, runs `python -m src.main --diagnose` and sees Porcupine dependency and AccessKey readiness, starts `python -m src.main`, says the configured built-in keyword, the Porcupine detector returns a detection index, the assistant records the question, and the rest of the existing OpenAI/TTS/playback loop proceeds unchanged. A user can still run wake debug and wake-file replay to inspect RMS, peak, overflow, detection state, and threshold-like sensitivity configuration without invoking OpenAI.

Constraints: Porcupine requires a Picovoice account AccessKey, the `pvporcupine` Python package, 16-bit mono PCM, and input frames sized to the engine's `frame_length` at the engine's `sample_rate`. Secrets must not be committed. Automated tests must use fake Porcupine modules or fake engines. The project remains macOS and Python 3.11/3.12 focused.

Ambiguities or assumptions: use Porcupine's built-in `jarvis` keyword if the installed SDK exposes it; otherwise fall back to the built-in `porcupine` keyword as the documented first test phrase. The wake score debug field may become a detection indicator because Porcupine reports keyword indexes rather than continuous openWakeWord scores. Manual evidence showed both `hey jarvis` and `alexa` openWakeWord paths stayed at tiny scores and did not wake the assistant, so openWakeWord is recorded as a blocker for the MVP rather than tuned further.

Required capabilities: official Picovoice Porcupine Python SDK behavior, `pvporcupine` as an installable dependency, user-provided `PICOVOICE_ACCESS_KEY`, deterministic fake-engine tests, diagnostics that report missing dependency or AccessKey clearly, and README instructions for creating and protecting the AccessKey.

Implementation paths: `src/wake_word.py`, `src/config.py`, `src/main.py`, `src/audio_input.py` if chunk sizing must become engine-driven, `requirements.txt`, `.env.example`, `README.md`, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: focused unit tests for Porcupine loader arguments, PCM conversion, frame length validation, detector preload/delete behavior, diagnostics and configuration, CLI/debug output compatibility, full `./init.sh`, and optional manual `python -m src.main --diagnose` plus live wake debug after a real Picovoice AccessKey is configured.

Decomposition decision: this remains one feature because the cleanup and Porcupine replacement are one coherent wake-detector runtime capability with a shared verification surface; splitting would leave the MVP in a partially migrated wake-word state with no independent user value.

### Alexa Wake-Word Runtime Restore

Goal: restore the active wake-word runtime to the F012 Alexa/openWakeWord ONNX path because the Porcupine path requires a Picovoice AccessKey that the user cannot currently obtain.

Included scope: record the Porcupine AccessKey/account capability gap, remove Picovoice Porcupine as the active runtime, restore Alexa as the default wake phrase and openWakeWord model, restore ONNX wake-word preparation and diagnostics, update requirements, README, `.env.example`, runtime logs, debug/replay frame sizing, and deterministic tests.

Excluded scope: solving Alexa's low-score recognition behavior, returning to the original Hey Jarvis model, training a custom wake word, supporting multiple wake-word providers, requiring a Picovoice AccessKey, changing OpenAI transcription/chat/TTS behavior, or deleting local debug artifacts.

Core flows: a user installs requirements, runs `python -m src.main --prepare-wake-word` to prepare Alexa ONNX assets, runs `python -m src.main --diagnose` and sees openWakeWord/ONNX readiness, starts `python -m src.main`, says `Alexa`, and the existing assistant state machine proceeds when the Alexa score crosses the configured threshold. Wake debug and wake-file replay continue to report RMS, peak, overflow, score, threshold, and summaries using openWakeWord's 1280-sample frame size.

Constraints: the restored runtime is explicitly a rollback to the previously accepted F012 behavior, not a claim that Alexa recognition is fixed. Automated tests must not require a real microphone, live OpenAI call, network model download, or live openWakeWord inference. The project remains macOS and Python 3.11/3.12 focused.

Ambiguities or assumptions: the user prefers a locally usable setup without a Picovoice company-account requirement, even though Alexa/openWakeWord previously produced low scores in manual testing. Picovoice may still be revisited later if a usable AccessKey becomes available.

Required capabilities: installed `openwakeword` and `onnxruntime`, explicit network access only when the user runs ONNX model preparation, deterministic fake-model tests, diagnostics for missing ONNX assets, and documentation that names the known Alexa recognition caveat.

Implementation paths: `src/wake_word.py`, `src/config.py`, `src/main.py`, `src/audio_input.py` if frame sizing was changed by F013, `requirements.txt`, `.env.example`, `README.md`, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: focused unit tests for Alexa loader arguments, ONNX model preparation paths, diagnostics, 1280-sample debug/replay behavior, documentation, full `./init.sh`, and optional manual `python -m src.main --prepare-wake-word`, `--diagnose`, and `--wake-debug`.

Decomposition decision: this is one rollback feature because the runtime, diagnostics, dependencies, docs, and tests must move together to avoid a half-Porcupine half-openWakeWord configuration.

### Alexa openWakeWord TFLite Runtime Switch

Goal: make the active Alexa/openWakeWord wake-word path usable on macOS ARM64 by switching the configured inference framework from ONNX to TFLite and making the selected framework visible across runtime, diagnostics, preparation, and debug output.

Included scope: add environment-backed wake backend, model, inference framework, and threshold settings; pass the configured `WAKE_INFERENCE_FRAMEWORK` into `WakeWordDetector`; prepare and diagnose framework-specific openWakeWord model assets; make live/file wake debug and the standalone openWakeWord debug script print requested model, inference framework, loaded models, and max scores; add a macOS ARM64 guard that rejects ONNX with clear recovery guidance; update requirements, `.env.example`, README, tests, and harness state.

Excluded scope: replacing openWakeWord with another wake-word provider, training custom wake-word models, changing OpenAI transcription/chat/TTS behavior, requiring automated tests to download real models or use a physical microphone, resolving upstream ONNX numeric behavior, or deleting local debug audio artifacts.

Core flows: a user copies `.env.example`, keeps `WAKE_BACKEND=openwakeword`, `WAKE_MODEL=alexa`, and `WAKE_INFERENCE_FRAMEWORK=tflite`, runs `python -m src.main --prepare-wake-word` to prepare TFLite assets, runs `python -m src.main --diagnose` and sees TFLite readiness, starts `python -m src.main`, says `Alexa`, and the assistant proceeds when the TFLite score crosses `WAKE_THRESHOLD`. A user can run wake debug or wake-file replay and see which model and inference framework produced the reported scores, so ONNX and TFLite cannot be confused during troubleshooting.

Constraints: macOS ARM64 must not silently use openWakeWord ONNX because local evidence and upstream issue evidence show near-zero scores there; TFLite support must remain explicit and configurable; automated tests must use fakes and generated fixtures rather than live microphone, OpenAI, network model download, or live openWakeWord inference; the project remains macOS and Python 3.11/3.12 focused.

Ambiguities or assumptions: `ai-edge-litert` is the preferred TFLite runtime dependency for this project because local debug notes showed it working with openWakeWord on the user's machine. If openWakeWord requires a `tflite_runtime` module import path in a given environment, diagnostics should report that runtime capability clearly instead of marking the assistant ready. ONNX may remain configurable on non-macOS-ARM64 platforms for investigation, but it is not the default active path.

Required capabilities: installed `openwakeword`, a working TFLite interpreter path such as `ai-edge-litert` or an openWakeWord-compatible `tflite_runtime`, network access only during explicit model preparation, write access to the active openWakeWord model directory, deterministic fake-model tests, and local debug evidence from `debug/openwakeword-alexa-debug.md` for the ONNX-vs-TFLite decision.

Implementation paths: `src/config.py`, `src/wake_word.py`, `src/main.py`, `scripts/debug_oww_file.py`, `requirements.txt`, `.env.example`, `README.md`, `tests/`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: focused unit tests for configuration defaults and overrides, macOS ARM64 ONNX rejection, framework-specific model loading and preparation paths, diagnostics dependency/model checks, wake debug output metadata, standalone debug script framework output, documentation assertions, full `./init.sh`, and optional manual `python -m src.main --prepare-wake-word`, `--diagnose`, and `--wake-file tmp/alexa-debug.wav` in a real virtualenv.

Decomposition decision: this remains one feature because configuration, detector construction, model preparation, diagnostics, debug observability, documentation, and tests are one coherent runtime switch. Splitting them would leave the wake path in a misleading partial state where the detector might use TFLite but setup or debug still claims ONNX.

### Recover From Empty Transcription And OpenAI Loop Errors

Goal: keep the long-running assistant alive when a wake event leads to an empty
OpenAI transcription or another OpenAI client error during the answer loop.

Included scope: catch project-owned `OpenAIClientError` exceptions from
transcription, chat completion, and text-to-speech inside the state machine;
log the recoverable failure with the current state; return to `WAIT_WAKE`
without calling later stages that depend on the failed stage; document the empty
transcription troubleshooting case; add deterministic tests for the user-observed
empty transcription traceback and adjacent OpenAI error stages.

Excluded scope: changing OpenAI model selection, adding real-time stock/news/web
tools, changing microphone recording thresholds, retrying OpenAI requests,
playing an apology TTS after failures, swallowing unexpected programming errors,
or requiring live OpenAI calls in automated tests.

Core flows: after a valid wake detection, the assistant records
`tmp/input.wav`. If transcription returns empty text and the OpenAI client raises
`OpenAIClientError`, the state machine logs the failure, transitions back to
`WAIT_WAKE`, does not call chat/TTS/playback, and the outer
`run_assistant_forever` loop keeps listening. If chat or TTS raises
`OpenAIClientError`, the same recoverable return-to-wake behavior happens after
preserving the already completed stage outputs in the loop result. Unexpected
non-OpenAI exceptions still surface for debugging.

Constraints: the assistant is a long-running local process, so recoverable API
or empty-audio outcomes must not terminate it. Automated tests must use fake
clients and generated WAV files, not live OpenAI requests or a real microphone.
The existing successful state-machine flow and fake-backend smoke path must keep
working unchanged.

Ambiguities or assumptions: empty transcription is treated as a recoverable
runtime outcome, often caused by silence, background noise, max-duration
recordings, or unusable speech after a wake event. The MVP logs the recovery and
returns to wake listening instead of synthesizing a spoken apology.

Required capabilities: deterministic fake `OpenAIClientError` test doubles,
existing state-machine unit tests, README and deployment troubleshooting updates,
and the recovery check through root `./init.sh`.

Implementation paths: `src/state_machine.py`, `tests/test_state_machine.py`,
`README.md`, `DEPLOYMENT.md`, `.agent-harness/feature_list.json`,
`.agent-harness/progress.md`, `.agent-harness/SPEC.md`, and
`.agent-harness/runs/`.

Verification surface: focused state-machine tests for empty transcription,
chat error, TTS error, unexpected exception propagation, existing successful
loop behavior, OpenAI client tests, documentation tests, feature validation, and
full `./init.sh`.

Decomposition decision: this remains one bug-fix feature because the failures
share one boundary: recoverable OpenAI client errors inside a single
question-answer loop. Splitting by transcription/chat/TTS would duplicate the
same recovery behavior without adding independently useful user value.

## 5. Verification Plan

Run:

```bash
./init.sh
scripts/validate-feature.sh F001
scripts/summarize-progress.sh
python3 orchestrator.py --dry-run
make ci
```

Run `python3 orchestrator.py --dry-run` and `scripts/validate-feature.sh F001` outside `./init.sh`; both commands call `./init.sh` and should not be nested inside tests run by `./init.sh`.
