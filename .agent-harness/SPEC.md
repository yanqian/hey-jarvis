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
