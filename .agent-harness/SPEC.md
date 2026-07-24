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

### Hey Jarvis Post-Playback Wake Suppression

Goal: prevent the real assistant from immediately re-triggering wake detection
after answer playback when the user has not spoken.

Included scope: consume post-playback microphone audio without wake detection,
require configurable consecutive wake-positive frames before entering
`RECORDING`, expose configuration defaults in `.env.example`, document the
manual acceptance failure, and add deterministic tests that simulate playback
residue and microphone overflow without real audio hardware.

Excluded scope: changing the accepted wake phrase, replacing openWakeWord,
implementing full acoustic echo cancellation, pausing or interrupting playback,
fixing long-question recording cutoff behavior, or making live OpenAI,
microphone, and speaker calls in automated tests.

Core flows: after `PLAYING` finishes, the state machine transitions back to
`WAIT_WAKE`, drains a short configured amount of microphone audio, logs that
post-playback wake audio is being suppressed, and only the next real wake
attempt can begin recording. During normal wake listening, a single
wake-positive residual frame is treated as a candidate and does not trigger
recording until the configured consecutive frame count is met.

Constraints: the MVP remains macOS-focused, keeps one reusable microphone
stream, avoids real microphone/OpenAI/speaker requirements in automated tests,
and keeps fake-backend recovery deterministic. Configuration defaults must be
safe enough to reduce self-triggering but adjustable for wake sensitivity.

Ambiguities or assumptions: the user-observed log shows a wake event
immediately after playback plus microphone overflow, so the likely root cause
is residual playback audio or stale microphone chunks rather than intentional
speech. A short drain window and consecutive-frame confirmation are acceptable
MVP defenses short of full echo cancellation.

Required capabilities: deterministic fake microphone chunks, configurable
cooldown and confirmation settings, state-machine tests for residual audio,
documentation for manual retesting, and standard recovery verification.

Implementation paths: `src/config.py`, `src/state_machine.py`, `src/main.py`,
`.env.example`, `README.md`, `DEPLOYMENT.md`, `MANUAL_TESTING.md`, `tests/`,
`.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and
`.agent-harness/runs/`.

Verification surface: focused unit tests for config and state-machine behavior,
documentation tests for the new settings and manual acceptance note, full
`./init.sh`, and manual retest of the user-observed playback-then-immediate-wake
scenario.

### Hey Jarvis Post-Playback Quiet Gate

Goal: make post-playback wake suppression depend on observed microphone quiet,
not only a fixed timer, so speaker echo or TTS tail audio cannot immediately
trigger a new wake after the cooldown expires.

Included scope: add configurable post-playback quiet seconds, quiet RMS
threshold, and maximum suppression duration; during suppression, feed ignored
audio into the wake detector so its internal state advances; keep detections
discarded until the quiet gate passes; document the second manual failure; and
add deterministic tests for residual post-playback wake-positive chunks after
the fixed cooldown.

Excluded scope: full acoustic echo cancellation, changing the wake phrase,
replacing openWakeWord, interrupting playback, live OpenAI/microphone/speaker
automation, or fixing long-question recording cutoff behavior.

Core flows: playback finishes; the assistant performs the configured fixed
post-playback cooldown; then it continues suppressing wake decisions while
checking microphone RMS; wake model calls during suppression are ignored but
advance model state; the assistant declares `WAIT_WAKE` ready only after a
configured amount of quiet audio or after a configurable maximum suppression
window with an explicit warning.

Constraints: suppression must be bounded by configuration, deterministic in
fake-backend tests, and should not make normal wake detection require live
hardware. Quiet detection uses project-owned PCM RMS logic rather than external
audio APIs.

Ambiguities or assumptions: the second observed failure showed two wake-positive
frames immediately after the 1.0s drain, so residual echo lasted beyond the
fixed cooldown or the detector state needed suppressed audio frames to settle.
The MVP should prefer a slightly delayed return to `WAIT_WAKE` over recording a
silent max-duration false wake.

Required capabilities: configurable quiet gate settings, fake PCM fixtures for
quiet and residual chunks, deterministic state-machine tests, documentation,
and recovery verification.

Implementation paths: `src/config.py`, `src/state_machine.py`, `.env.example`,
`README.md`, `DEPLOYMENT.md`, `MANUAL_TESTING.md`, `tests/`,
`.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and
`.agent-harness/runs/`.

Verification surface: config tests, state-machine tests for residual chunks
after cooldown, documentation tests, `./init.sh`, and manual M022 retest.

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

### Validate Speakerphone Realtime WebRTC Full Duplex

Goal: determine with real evidence whether OpenAI Realtime over a client WebRTC media path can provide acceptable full-duplex conversation, echo suppression, and barge-in on this Mac's built-in microphone and speakers before the project commits to a Realtime backend architecture.

Included scope: a project-owned local validation server; an API-key-protected endpoint that mints an ephemeral Realtime client secret without exposing the standard key to the browser; a minimal browser page that opens a WebRTC Realtime session, requests echo cancellation, noise suppression, and automatic gain control, plays the remote audio track directly, exposes actual microphone track settings, logs bounded session/VAD/response/interruption events, and provides start/stop plus a downloadable or copyable sanitized validation report; deterministic offline tests for server routing, credential handling, static assets, report formatting, and session configuration; concise operator instructions; and one real built-in-microphone/speaker acceptance run when browser permission and network access are available.

Excluded scope: wake-word integration, changes to the existing pipeline or assistant state machine, production backend selection, tools, local PCM forwarding, custom streaming playback, acoustic echo cancellation implementation, WebSocket fallback, UI packaging, deployment, automatic product claims from one device trial, or evaluator dependence on a live paid API call.

Core flows: the operator starts the local probe with the existing configured `OPENAI_API_KEY`; the browser loads only from localhost; pressing Start obtains an ephemeral client secret, requests a processed microphone track, creates a WebRTC peer connection, attaches the microphone track, renders the Realtime remote audio track, and shows both requested and actual capture settings. The operator asks the model to speak, then talks over the answer using the Mac speakers and microphone. The page records whether user speech started during model output, whether the response was cancelled/interrupted, whether remote speech stopped, and any errors. Stop closes data channels, peer connection, media tracks, and audio elements. If the API key, permission, network, model, or browser capability is unavailable, the probe fails clearly without changing the existing assistant.

Constraints: the standard API key stays server-side and is never returned, logged, embedded in HTML/JavaScript, or written into reports; the browser receives only an ephemeral client secret; the local server binds to loopback by default; microphone capture explicitly requests `echoCancellation`, `noiseSuppression`, and `autoGainControl`, while the page reports actual settings instead of assuming they were honored; event logs exclude raw/base64 audio, credentials, and unbounded payloads; automated verification remains offline and hardware-free; the real trial uses the built-in speaker and microphone without headphones and records device/browser/model context plus subjective echo and barge-in observations.

Ambiguities or assumptions: OpenAI does not publicly document ChatGPT App's internal audio processing, so this probe evaluates the supported WebRTC path rather than claiming to reproduce the private app implementation. Browser and macOS audio processing may differ from a future packaged WebView. One successful run establishes feasibility on this machine, not universal acoustic performance. The current official WebRTC session shape and model are external behavior and must be pinned from official docs or a captured successful session before product work depends on them.

Required capabilities: configured `OPENAI_API_KEY`; OpenAI Realtime access and network connectivity for the manual run; a browser with WebRTC, localhost microphone permission, and audio output; Mac built-in microphone and speakers; a project-owned local server using only declared or standard-library dependencies; fake HTTP responses and browser-independent fixtures for automated verification; and the existing harness evaluator/recovery workflow.

Implementation paths: `spikes/realtime_webrtc/` for the local server, HTML, JavaScript, CSS, and usage notes; `tests/test_realtime_webrtc_probe.py` for offline contracts; `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/` for durable state and evidence. Existing `src/`, pipeline behavior, `.env`, and tracked runtime defaults remain unchanged.

Verification surface: official Realtime WebRTC/client-secret documentation captured in run evidence; offline unit/contract tests for loopback defaults, token request shape, secret redaction, static routing, browser capture constraints, cleanup behavior, bounded event/report fields, and missing-key errors; a local static smoke load; full project tests and final `./init.sh`; plus a manual built-in-speaker/microphone run that records actual track settings and pass/fail observations for self-echo, user barge-in, old-response stopping, and cleanup. Live results inform the later architecture decision but are not required for deterministic evaluator completion when external permission or service access is unavailable.

Decomposition decision: this is one intentionally bounded feasibility feature because the token server, WebRTC page, diagnostics, and real-device checklist jointly answer one architectural question and share one verification surface. Wake integration and production Realtime backend implementation remain separate future requirements whose design depends on this result.

### Realtime WebRTC Voice MVP

Goal: add an opt-in macOS development MVP in which the existing local Hey Jarvis wake detector starts a continuous OpenAI Realtime WebRTC voice session, users can speak and interrupt through the built-in microphone and speakers without headphones, follow up without repeating the wake phrase, and reliably return to local wake listening when the session ends, while the existing pipeline remains the default and unchanged fallback.

Included scope: a hands-free-capable WebRTC host selected by an explicit capability gate; exclusive microphone ownership handoff between the existing Python wake listener and that host; a loopback-only Python/host control bridge; server-side creation of ephemeral Realtime credentials or an equivalent official server-authenticated WebRTC call; direct WebRTC microphone and remote-audio tracks with requested and reported echo cancellation, noise suppression, and automatic gain control; opt-in backend configuration and diagnostics; `WAIT_WAKE -> CONNECTING -> ACTIVE_SESSION -> CLOSING -> WAIT_WAKE` lifecycle; Realtime server VAD with automatic response creation and interruption; continuous multi-turn speech; local idle and maximum-duration closure; deterministic bilingual end phrases based on completed input-transcription turns; one existing deterministic calculator exposed through Realtime function calling; bounded redacted observability; fake-host/offline tests; and repeated no-headphones real-device acceptance.

Excluded scope: replacing or changing the default pipeline backend; a Realtime WebSocket fallback; Python-side PCM upload, output streaming queues, `afplay` Realtime playback, client-computed playback duration, manual response cancellation or assistant-item truncation for WebRTC; keeping a Realtime session open while waiting for the wake word; uploading ambient pre-wake audio; running the wake detector and WebRTC capture concurrently; migrating every weather, FX, stock, or future tool; ChatGPT App control, UI automation, virtual audio devices, custom echo cancellation, general-purpose browser UI, distributable `.app` packaging, login-item installation, automatic updates, production deployment, or universal acoustic claims from one Mac.

Core flows: on process start, the selected WebRTC host performs any one-time per-install or per-launch permission/arming step and then waits without owning the microphone. Python opens the existing 16 kHz wake stream and listens locally without a Realtime connection. After a confirmed Hey Jarvis detection, Python closes the wake input, plays a very short local acknowledgement before WebRTC capture starts, and commands the host to connect. The host obtains a server-minted short-lived credential, requests a processed microphone track, creates the WebRTC peer connection and event data channel, and reports `session.created`/connected readiness. In `ACTIVE_SESSION`, WebRTC transports microphone and model audio directly, Realtime VAD creates turns and interrupts responses, and Python observes bounded lifecycle events without forwarding PCM. Follow-up speech remains in the same session. Idle timeout, maximum duration, an exact normalized end phrase, explicit shutdown, connection failure, or host failure enters `CLOSING`; the host stops tracks/audio and closes the peer/data channel before Python reopens a fresh wake stream and resets the detector. A calculator function call crosses the loopback bridge to the existing safe calculator, returns a `function_call_output` to the same conversation, and lets the model continue speaking.

Constraints: the standard API key remains in trusted Python/server code and never reaches host JavaScript, reports, logs, fixtures, or committed files; the loopback bridge rejects non-loopback binding and validates command/session identity; no ordinary room audio leaves the Mac before wake; at most one component owns microphone capture at a time; WebRTC output must remain on the remote media track so server-managed interruption and automatic truncation remain authoritative; requested browser capture processing must be compared with actual track settings; the host must start a session programmatically after wake without a new click once its documented initial arming/permission step has completed; the feature must fail closed if the candidate host cannot provide that behavior. Realtime input transcription is asynchronous, separately billed, and only a rough guide to the model's native audio understanding, so end-phrase matching uses completed full-turn transcripts and conservative normalization rather than substring matching. The project supports Python 3.11/3.12 on macOS, keeps `BACKEND=pipeline` as the default, and must preserve all existing CLI, fake-backend, wake, ACK, routing, and pipeline tests.

Ambiguities or assumptions: the distributable app shell is intentionally deferred; MVP means runnable from this repository on the user's Mac. F051 proves Chrome WebRTC feasibility but does not prove that an embedded WKWebView, app-mode browser, or other hands-free host can reacquire the microphone and autoplay remote audio after a Python wake event without a fresh user gesture. F052 must select and prove the smallest acceptable host before downstream implementation; candidate details are not predetermined by this plan. One initial permission/arming interaction is acceptable, but every wake after that must be hands-free for the lifetime documented by the chosen host. If no acceptable host passes, the MVP blocks instead of substituting WebSocket/local playback. The official current examples use `gpt-realtime-2.1` and voice `marin`; these remain validated configuration defaults, not assumptions embedded across modules. The local acknowledgement is assumed to finish before the WebRTC microphone track opens, avoiding upload/drain complexity. Self-echo immunity is an acceptance distribution measured across repeated trials, not an absolute guarantee.

Required capabilities: OpenAI Realtime access and a configured standard API key; server-side access to `/v1/realtime/client_secrets` or `/v1/realtime/calls`; a macOS WebRTC host with microphone permission, remote-audio autoplay after documented arming, data-channel access, and actual capture-setting inspection; a loopback control channel between Python and the host; exclusive release/reopen support in the existing `sounddevice` input wrapper; existing openWakeWord models; existing safe calculator routing/execution; fake host, fake clock, fake token response, fake data-channel events, and deterministic lifecycle fixtures; Mac built-in microphone/speakers for manual acceptance; and cold-start evaluator plus root recovery verification.

Implementation paths: keep `spikes/realtime_webrtc/` as F051 evidence rather than the production runtime. Add project-owned Realtime backend/configuration and lifecycle code under a focused `src/realtime/` or equivalently cohesive package; keep WebRTC host assets under a production-owned web/host path rather than `spikes/`; reuse `src/audio_input.py`, wake detector construction, acknowledgement playback, `src/tools/router.py`, and provider-independent calculator execution through explicit adapters rather than rewriting them; extend `src/main.py`, `src/config.py`, `.env.example`, diagnostics, README, DEPLOYMENT, and MANUAL_TESTING only as each feature requires; and add focused `tests/test_realtime_*.py` plus existing regression suites.

Verification surface: offline tests must cover backend selection/default compatibility, bridge validation, exclusive microphone handoff ordering, session state transitions, fake host connect/close, server-VAD session configuration, `response.done` not ending the session, idle/max/end-phrase closure, error recovery, task/track cleanup, function-call arguments/results, secret redaction, and unchanged pipeline behavior without live audio or network. Capability and final acceptance require real built-in-speaker/microphone trials that report actual capture settings, start after wake without a new click, perform at least five wake/session/close/wake cycles, complete multi-turn follow-up, deliberately interrupt long answers, exercise the calculator and an end phrase, verify the microphone indicator and wake stream recover after each close, and record false self-echo interruptions and errors. Final `./init.sh`, fake-backend smoke, Realtime fake smoke, diagnostics, and evaluator evidence must pass.

Official contract: OpenAI recommends WebRTC rather than WebSockets for client devices and states that WebRTC carries microphone/remote audio without granular client audio-event handling. With VAD enabled, Realtime detects speech and can create responses and interrupt an in-progress response; WebRTC/SIP sessions have server-managed output buffering and automatic truncation of unplayed audio. Callable functions are configured through session or response tools and return application results as function-call output items. Completed input transcription is asynchronous, separately billed ASR output and may diverge from the Realtime model's native interpretation. A Realtime session can last up to 60 minutes, while this MVP applies the shorter local maximum. Sources: https://developers.openai.com/api/docs/guides/realtime-webrtc, https://developers.openai.com/api/docs/guides/realtime-vad, https://developers.openai.com/api/docs/guides/realtime-conversations#interruption-and-truncation, https://developers.openai.com/api/docs/guides/realtime-conversations#configure-callable-functions, and https://developers.openai.com/api/reference/resources/realtime/server-events#conversation.item.input_audio_transcription.completed.

Decomposition decision: the MVP is split into six features because host viability, configuration/contracts, lifecycle/media integration, deterministic end phrases, function-tool bridging, and final recovery/acceptance have independent failure and verification boundaries. F052 is a capability gate and blocks all product work if hands-free WebRTC hosting or exclusive microphone handoff is not viable. F053 establishes opt-in contracts without live behavior. F054 delivers the core wake-to-continuous-session product path. F055 and F056 are independently valuable conversation-exit and tool behaviors. F057 reconciles diagnostics/documentation and requires repeated end-to-end hardware acceptance after all earlier pieces are evaluator-approved.

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

### Finnhub Stock Quote Tool

Goal: replace the structured stock route's placeholder result with a
Finnhub-backed quote tool that can answer explicit stock-price requests through
the local tool router without falling back to general chat speculation.

Included scope: conservative stock intent detection, uppercase ticker extraction,
a small explicit company-alias map, optional `FINNHUB_API_KEY` loading,
provider diagnostics, Finnhub quote endpoint integration, concise stock quote
answers, structured tool result data, market-data delay caveats, documentation,
manual smoke guidance, and deterministic mocked tests.

Excluded scope: live trading, portfolio management, investment advice, order
placement, full company search, broad news/web search, streaming market data,
historical charts, analyst ratings, watchlists, automatic live-network tests, or
guessing ambiguous ordinary phrases as stock quote requests.

Core flows: a user asks `AAPL stock price`, the router selects the `stock`
route, extracts symbol `AAPL`, calls the configured Finnhub quote provider with
the API token kept secret, maps Finnhub fields `c`, `d`, `dp`, `h`, `l`, `o`,
`pc`, and `t` into `ToolResult` data, and returns a short answer naming the
symbol, current price, change, percent change, previous close, source, and
freshness caveat. A user asks an explicit Chinese stock phrase such as
`苹果股价多少`, the alias map resolves Apple to `AAPL`. A user asks an ambiguous
ordinary phrase such as `苹果怎么样`, the router does not treat it as a stock
request. Missing credentials, unknown symbols, zero or missing current price,
HTTP failures, timeouts, network failures, and malformed provider data return
structured stock failures and do not fall back to chat-generated prices.

Constraints: `FINNHUB_API_KEY` is optional configuration and must never be
printed, logged, committed, or exposed in diagnostics. Automated verification
must not require live network access or a real Finnhub key; tests use real-shaped
Finnhub quote fixtures through the shared HTTP JSON boundary. Stock answers must
include market-data delay or freshness wording and must not present themselves as
financial advice or executable trade quotes. The assistant remains a local macOS
MVP and should keep text-debug behavior deterministic.

Ambiguities or assumptions: the first stock implementation supports explicit
ticker symbols and a deliberately small alias map for common companies instead
of general company-name search. Finnhub free-tier data freshness may vary by
market and account; the tool should describe data as market data that may be
delayed unless a future requirement adds provider-specific entitlement handling.
Currency selection and exchange-specific disambiguation are out of scope for
this feature.

Required capabilities: shared provider configuration from F023, shared HTTP JSON
fetching with timeout/error mapping, optional Finnhub API key in environment or
`.env`, deterministic provider fakes, router text-debug coverage, documentation
tests, and manual live-smoke instructions for users who provide a key.

Implementation paths: `src/tools/router.py`, `src/tools/providers.py`,
`src/config.py` only if the existing provider config cannot already load the
key, `.env.example` if key documentation is not already present, `README.md`,
`DEPLOYMENT.md`, `MANUAL_TESTING.md`, `tests/`,
`.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `runs/`.

Verification surface: focused router tests for ticker extraction, aliases, and
ambiguous non-stock phrases; provider tests for success, missing key, unknown
symbol, zero/missing price, HTTP errors, network errors, and malformed data;
documentation tests for configuration and manual smoke examples; CLI text-debug
checks for `AAPL stock price`, `苹果怎么样`, and `苹果股价多少`; full
`python3 -m unittest discover -s tests`; final root `./init.sh`; and optional
manual live smoke with a real `FINNHUB_API_KEY`.

Decomposition decision: this is one independently verifiable provider feature
because routing, credential handling, provider parsing, stock-specific caveats,
and tests share one external capability boundary. It depends on the shared
provider infrastructure from F023 but remains independent from the weather and
FX tools.

### Naturalized Structured Tool Answers

Goal: keep provider-backed tools as stable structured fact providers while
adding a separate OpenAI language pass that can turn successful weather, FX, and
stock tool results into more natural spoken answers without changing the facts.

Included scope: an explicit tool-answer naturalization boundary, documented
configuration for enabling or disabling naturalization, a constrained OpenAI
request shape for successful provider-backed tool results, fallback to the raw
deterministic tool answer when naturalization is disabled or fails, text-debug
visibility into raw tool answers and naturalization status, documentation, and
deterministic tests with fake OpenAI clients and mocked providers.

Excluded scope: changing provider fetching or parsing, adding new providers,
letting the LLM select tools, using chat memory to reinterpret tool facts,
naturalizing provider failures, weakening realtime refusal behavior, making
`python -m src.main --text ...` require OpenAI credentials, or adding live
OpenAI/network calls to automated tests.

Core flows: a user asks a weather, FX, or stock question; the deterministic
router selects the tool; the provider returns a `ToolResult` with stable
`status`, `summary`, `answer`, and `data`; if the result is `success` and
naturalization is enabled, the assistant sends the original user question,
route metadata, raw answer, summary, and structured data to a dedicated OpenAI
naturalization method; the model returns one or two short spoken sentences that
preserve numbers, units, timestamps, sources, and caveats; the assistant sends
that naturalized answer to TTS. If naturalization is disabled, unavailable, or
raises a recoverable OpenAI error, the assistant uses the raw deterministic
tool answer. Provider errors, missing credentials, not-configured results, and
realtime refusals bypass naturalization and never fall back to chat speculation.

Constraints: structured `ToolResult.data` remains the source of truth and must
be inspectable in tests and debug output. The naturalization prompt must instruct
the model not to add facts, advice, forecasts, prices, rates, sources, or
timing details absent from the tool result. Secret values such as
`FINNHUB_API_KEY` must never be included in naturalization input or debug output.
Automated verification uses fakes and real-shaped tool fixtures, not live
OpenAI, live Finnhub, live Open-Meteo, or live Frankfurter calls. Spoken answers
must stay concise enough for TTS.

Ambiguities or assumptions: "more natural" means improving phrasing for spoken
delivery, not changing the routing decision, provider data model, or factual
content. The initial naturalization pass applies only to successful
provider-backed realtime tools because local calculator and time answers are
already short and deterministic. If the LLM returns an empty answer or fails,
raw deterministic output is preferable to dropping the response.

Required capabilities: existing F023-F026 provider-backed tool results,
OpenAI chat capability from F005, a dedicated prompt/request boundary that can
be tested without live API access, settings for the naturalization toggle,
fake clients that record naturalization calls, and documentation/manual testing
paths for comparing raw versus naturalized answers.

Implementation paths: `src/config.py`, `.env.example`, `src/openai_client.py`,
`src/tools/router.py`, `src/state_machine.py` if answer-path wiring needs to
carry the naturalized response, `src/main.py` if text debug output changes,
`README.md`, `DEPLOYMENT.md`, `MANUAL_TESTING.md`, `tests/`,
`.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `runs/`.

Verification surface: configuration tests for the naturalization toggle;
OpenAI-client tests for the dedicated naturalization request shape and empty or
failed responses; router/answer-path tests proving successful weather, FX, and
stock results can be naturalized while failures bypass the LLM; tests proving
history is not polluted by naturalization; text-debug tests showing raw answer
and naturalization status without OpenAI; documentation tests; full
`python3 -m unittest discover -s tests`; final root `./init.sh`; and optional
manual comparison with real providers plus `OPENAI_API_KEY`.

Decomposition decision: this is one feature because it is a single presentation
layer capability over the already completed provider tools. Provider-specific
fetching and parsing remain separate completed features; splitting by weather,
FX, and stock would duplicate the same naturalization boundary without adding
independent project value.

### ARMED Baseline Gate And Acknowledgement Guard

Goal: prevent cold-start ARMED false triggers before a useful noise baseline exists, while conservatively preserving immediate post-acknowledgement user speech so the first syllable is less likely to be lost.

Included scope: configurable ARMED baseline duration and minimum valid-chunk gate, optional latest-chunk-voiced trigger requirement, baseline-aware diagnostics, a bounded acknowledgement guard that observes quiet and may preserve a small non-quiet tail, passing preserved guard audio into ARMED pre-roll, environment examples, README configuration guidance, manual tests, and deterministic state-machine/configuration tests.

Excluded scope: voice activity detection, new runtime dependencies, recorder endpointing changes, wake-word model changes, streaming transcription, additional spoken prompts, or broad audio-pipeline redesign.

Core flows: after wake acknowledgement playback, the assistant guards microphone residue for a bounded interval, discards obvious acknowledgement residue and quiet audio, preserves only a conservative late non-quiet tail, enters ARMED with that tail available as pre-roll, waits until both configured baseline time and valid-chunk count are satisfied, and triggers recording only when the voiced-window rule and optional latest-chunk rule pass. A wake followed by silence times out locally and returns to WAIT_WAKE without recording or any OpenAI, tool, TTS, or answer-playback call.

Constraints: preserve `ARMED_VOICE_RMS` as the legacy fallback for `ARMED_MIN_RMS`; existing environment variables and CLI modes must keep working; overflowed and clipped chunks cannot contribute voice decisions; only valid non-voiced chunks update the noise sample set; acknowledgement-only residue must not be enough to trigger recording; preserving too little guard audio is preferable to recording the acknowledgement; automated tests use fakes and synthetic PCM with no live microphone, OpenAI, speaker, or network access.

Ambiguities or assumptions: `ACK_GUARD_SECONDS` replaces the active fixed acknowledgement drain behavior when the guard is enabled, while the existing drain setting remains backward-compatible when the guard is disabled. Guard-tail preservation uses the configured quiet RMS as the conservative residue boundary and keeps only contiguous non-quiet chunks at the end of the bounded buffer. Initial guard chunks seed eventual pre-roll but do not count toward ARMED baseline readiness or directly force a trigger.

Required capabilities: existing PCM RMS/peak helpers, fake audio source overflow signaling, deterministic logging capture, configuration parsing/validation, temporary WAV fixtures, and root recovery verification. No additional package or external service is required.

Implementation paths: `src/config.py`, `src/state_machine.py`, `.env.example`, `README.md`, `MANUAL_TESTING.md`, `tests/test_config.py`, `tests/test_state_machine.py`, `tests/test_documentation.py`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: focused tests for baseline gating, cold-noise-floor silence timeout, latest-chunk voice requirement, acknowledgement-only guard cancellation, boundary-speech preservation, configuration defaults/overrides/validation, and documentation; then `python -m src.main --dry-run`, `python -m src.main --fake-backend`, `python -m src.main --diagnose`, `python -m unittest`, and final `./init.sh`.

Decomposition decision: this remains one feature because the baseline gate and acknowledgement-boundary guard jointly address the same ARMED entry boundary and share one state-machine, logging, documentation, and synthetic-audio verification surface. Splitting them would leave either the false-trigger or first-syllable failure active at the same transition.

### Require A Safe Post-ACK Boundary

Goal: prevent acknowledgement speaker residue, clipping, and microphone overflow from entering triggerable ARMED detection or recording pre-roll, while preserving the working ACK-disabled path and allowing complete user speech after a verified quiet boundary.

Included scope: an explicit post-ACK boundary result/helper, mandatory quiet observation for guarded ACK-enabled flows, bounded suppression and local no-speech cancellation, safe noise seeding, clipped/overflow pre-roll clearing, post-ACK-aware baseline semantics and diagnostics, less destructive ACK guard defaults, documentation/manual-test updates, deterministic state-machine/configuration tests, and updating the existing PR1 branch.

Excluded scope: VAD or PR2 behavior, wake-word model changes, recorder endpointing changes, echo cancellation/DSP, volume automation, streaming transcription, extra spoken prompts, or preserving immediate speech that begins before a safe quiet boundary when it cannot be distinguished from acknowledgement residue without VAD.

Core flows: with acknowledgement disabled, immediate speech enters ordinary F036 ARMED detection unchanged. With acknowledgement and guard enabled, the assistant suppresses clipped, overflowed, loud, or otherwise unsafe residue until the configured quiet duration is observed or the bounded maximum is reached. A verified quiet boundary supplies quiet noise seeds and permits ARMED; clipped/overflowed residue never enters pre-roll. If no quiet boundary is reached, the loop cancels locally as `no_speech_after_wake` without recording or OpenAI. After quiet, the first user speech chunks are retained by normal ARMED pre-roll and can trigger recording.

Constraints: guarded ACK-enabled flow must never log `post_ack_quiet_observed=false` together with `armed_trigger ... result=recording_started`; a guarded ACK flow must not treat elapsed time alone as a useful baseline while noise floor has no samples; overflowed and clipped chunks clear post-ACK candidate pre-roll; max suppression is bounded by `ACK_GUARD_MAX_BUFFER_SECONDS`; automated tests use fake audio and do not require a microphone, speaker, OpenAI, or network. Local user `.env` tuning and untracked real-test logs are not committed.

Ambiguities or assumptions: without VAD or acoustic echo cancellation, loud non-clipped audio before observed quiet cannot be safely distinguished as user speech versus acknowledgement residue, so PR1 follow-up prefers suppression/cancellation over recording it. `ACK_GUARD_SECONDS` is the initial suppression target while `ACK_GUARD_MAX_BUFFER_SECONDS` is the hard maximum boundary wait. Quiet chunks used as noise seeds are not recorded as user pre-roll. Existing guard-disabled behavior retains the legacy fixed drain and ordinary ARMED semantics.

Required capabilities: current ACK/ARMED state machine, PCM RMS/peak and overflow metadata, deterministic fake chunks including clipping/overflow, bounded timing from detector frame duration, logging capture, configuration validation, and root recovery verification.

Implementation paths: `src/config.py`, `src/state_machine.py`, `.env.example`, `README.md`, `MANUAL_TESTING.md`, `tests/test_config.py`, `tests/test_state_machine.py`, `tests/test_documentation.py`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: ACK-without-quiet cancellation, clipped/overflow residue clearing, quiet-then-user-speech pre-roll, no ACK-enabled zero-noise-floor trigger, ACK-disabled immediate speech, post-ACK diagnostics, default configuration/docs assertions, full `python3 -m unittest discover -s tests`, dry-run, fake-backend, diagnose execution, and final `./init.sh`.

Decomposition decision: this is one focused PR1 follow-up because boundary suppression, baseline eligibility, pre-roll safety, diagnostics, and regression tests are one state transition contract. VAD remains isolated in the already reserved stacked PR2 feature F037, so this follow-up uses F038.

### Preserve Clipped User Speech After The ACK Boundary

Goal: stop ARMED from deleting the beginning of a legitimate post-ACK question when real user speech contains clipped chunks, and remove the misleading unused `ACK_GUARD_SECONDS` setting.

Included scope: delete `ACK_GUARD_SECONDS` from defaults, Settings, loading, examples, docs, tests, logs, and local `.env`; keep `ACK_GUARD_MAX_BUFFER_SECONDS` as the only bounded post-ACK wait; change post-boundary ARMED pre-roll handling so overflowed chunks are omitted individually while clipped chunks are preserved as potentially intelligible user audio but remain ineligible for voice/noise decisions; retain previously collected safe pre-roll across invalid chunks; add clipped-user-speech regression coverage and diagnostics/documentation updates; update existing PR1.

Excluded scope: changing the pre-boundary rule that clipped/overflowed acknowledgement residue resets quiet/noise candidates, changing ARMED RMS thresholds, VAD/PR2 behavior, automatic gain control, echo cancellation, audio repair, recorder endpointing, wake detection, or extra prompts.

Core flows: ACK residue is suppressed until the F038 quiet boundary. After that boundary, ARMED begins user-speech collection. A microphone overflow chunk is skipped without erasing earlier user chunks. A clipped chunk is kept in pre-roll/WAV because clipped speech may still be intelligible, but it is marked non-voiced and does not update the noise floor. Later valid voiced chunks satisfy the rolling trigger, and recording begins with the full bounded pre-roll including the initial `1+1` audio instead of only the final `等于几` tail.

Constraints: the safe quiet boundary remains mandatory and ACK residue before it never enters recording. Clipped post-boundary audio is accepted only into pre-roll, not as trigger evidence. Overflowed audio remains excluded because it may be incomplete. Default-disabled ACK compatibility and guarded no-quiet cancellation remain unchanged. `ACK_GUARD_MAX_BUFFER_SECONDS` must stay positive and is the sole post-ACK suppression timeout. Automated tests use synthetic PCM and fakes; user log files remain untracked and uncommitted.

Ambiguities or assumptions: real evidence showed `max_peak=32768`, 18 checked versus 12 valid chunks, and only 240ms of an 800ms configured pre-roll before transcription became `等于几`. This is treated as legitimate clipped user speech after an already verified quiet boundary. Preserving clipped PCM may retain distortion, but it is preferable to deleting the utterance prefix; future VAD/DSP work can classify or repair it more precisely.

Required capabilities: existing post-ACK boundary result, `_ArmedChunk` metadata, bounded pre-roll, synthetic clipped/overflow PCM fixtures, captureable recorder source, configuration/documentation tests, and root recovery verification.

Implementation paths: `src/config.py`, `src/state_machine.py`, `.env`, `.env.example`, `README.md`, `MANUAL_TESTING.md`, `tests/test_config.py`, `tests/test_state_machine.py`, `tests/test_documentation.py`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: absence of `ACK_GUARD_SECONDS` across tracked runtime/docs/tests, configuration tolerance for existing unknown local keys only after local cleanup, clipped user chunks retained in captured recording pre-roll, overflow omitted without clearing earlier safe chunks, clipped chunks excluded from trigger/noise decisions, original no-quiet and ACK-disabled regressions, full unittest discovery, dry-run, fake-backend, diagnose execution, and final `./init.sh`.

Decomposition decision: this is one focused PR1 correction because the unused setting removal and pre-roll behavior change directly resolve one observed `1+1` prefix-loss path. It uses F039 because F037 is reserved for stacked PR2 and F038 is already evaluator-approved.

### Synchronize Microphone Consumption During Wake Acknowledgement Playback

Goal: prevent acknowledgement playback from leaving stale speaker-echo audio and overflowed microphone buffers for the post-ACK guard by continuously consuming and discarding microphone chunks while the acknowledgement is actually playing.

Included scope: a non-blocking or observable playback handle for macOS `afplay`; a state-machine ACK playback path that starts playback, drains microphone chunks until playback completion, waits for and propagates playback errors, records safe drain metrics, and then begins post-playback processing from current audio; backward-compatible synchronous answer playback; fake playback handles and microphone sources; documentation, manual testing, and deterministic unit/smoke coverage.

Excluded scope: changing the post-ACK quiet-boundary policy itself, preserving speech spoken over the acknowledgement, acoustic echo cancellation, DSP, microphone gain control, system-volume automation, wake-word changes, VAD/recording endpoint fixes, or changing the acknowledgement wording/audio asset.

Core flows: after confirmed wake, the assistant starts the acknowledgement without blocking microphone consumption. While playback is running, every available microphone chunk is read and deliberately discarded as acknowledgement-contaminated audio; overflow/clipping/RMS/peak metrics are accumulated without entering ARMED or wake detection. The final chunk that overlaps playback completion is discarded. Playback completion or failure is joined deterministically. Only then does post-ACK processing read the next current microphone chunk. Normal answer playback remains synchronous and retains existing post-playback suppression.

Constraints: no raw audio or secrets are logged; no unbounded worker thread or orphaned `afplay` process is allowed; playback failures retain actionable `PlaybackError` behavior; a blocking microphone read may extend at most one configured audio chunk beyond playback completion; ACK-disabled behavior and fake-backend behavior remain compatible; automated tests require no real microphone, speaker, process, OpenAI, or network.

Ambiguities or assumptions: sounddevice's blocking `RawInputStream.read()` is the observed source of backlog when it is not called during synchronous playback. Reading one chunk at a time while polling an `afplay` handle is sufficient to keep the stream near real time. Speech that overlaps the audible acknowledgement is intentionally discarded in this feature because it cannot be separated from speaker echo without AEC; preserving speech that begins after playback belongs to the dependent handoff feature.

Required capabilities: a testable playback process/handle boundary with poll/wait/error semantics, fake handles with deterministic completion, fake microphone chunks and overflow metadata, PCM RMS/peak helpers, state-transition logging capture, macOS `afplay`, and root recovery verification.

Implementation paths: `src/player.py`, `src/state_machine.py`, `src/main.py` if protocol wiring changes, `tests/test_player.py`, `tests/test_state_machine.py`, fake-backend fixtures, `README.md`, `MANUAL_TESTING.md`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: player handle success/failure tests; ACK playback that drains multiple echo/overflow chunks without entering ARMED; proof that the first post-playback read is not a queued ACK chunk; synchronous answer-playback regression; ACK-disabled regression; fake-backend state sequence; focused unit tests; full unittest discovery; dry-run, fake-backend, diagnose, and final `./init.sh`.

### Preserve Immediate Post-ACK Speech After A Synchronized Drain

Goal: allow a user to begin a question immediately after the acknowledgement ends without requiring a preceding quiet interval that suppresses the utterance, while still preventing acknowledgement tail audio, overflow, or clipping from directly triggering ARMED.

Included scope: a synchronized post-ACK handoff contract that is used only after successful playback-time microphone draining; quarantine of the single chunk that can overlap playback completion; routing subsequent live chunks into ARMED pre-roll immediately; safe quiet chunks as optional noise seeds rather than a prerequisite for retaining speech; baseline/energy/VAD gating that prevents quarantined or invalid chunks from triggering; bounded fallback cancellation when drain synchronization or useful post-ACK evidence is unavailable; diagnostics, documentation, manual tests, and deterministic regressions.

Excluded scope: speech spoken during the audible acknowledgement, full acoustic echo cancellation, speaker identification, audio repair, automatic volume control, VAD dependency/diagnostic repair, Recording VAD endpointing, wake-model changes, streaming transcription, or removing local no-speech/transcript safety gates.

Core flows: after F040 confirms that microphone consumption stayed synchronized through playback and discards the overlap chunk, the next non-overflow post-playback chunks enter ARMED pre-roll instead of being blindly suppressed until quiet. Quiet chunks may seed the noise floor; non-quiet or clipped live chunks are retained according to existing F039 rules but remain subject to ARMED baseline, energy, rolling-voice, last-chunk, and optional VAD gates. Immediate `一加一等于几` can therefore trigger and record with its prefix intact. Silence still times out locally. If playback-time synchronization failed or overflow indicates stale state, the assistant falls back to the conservative bounded quiet boundary and cannot trigger from unsafe residue.

Constraints: no path may treat the quarantined overlap chunk, overflowed audio, or clipped audio as voice/noise evidence; clipped live PCM may be retained only as recording pre-roll under F039 semantics; ACK residue alone must not reach recording or OpenAI; ACK-disabled and guard-disabled compatibility remain explicit; the safe fallback remains bounded; tests use synthetic audio and fake handles without hardware or network.

Ambiguities or assumptions: once F040 has continuously consumed the microphone and discarded the chunk overlapping playback completion, subsequent chunks are considered live post-playback input rather than stale queued acknowledgement audio. A small amount of physical speaker tail may remain, so it is preserved only as bounded pre-roll and cannot trigger without later valid rolling speech evidence. VAD remains optional; correctness cannot depend solely on WebRTC classification. The current mandatory `ACK_GUARD_MIN_QUIET_SECONDS` behavior remains available as a fallback rather than the normal synchronized path.

Required capabilities: F040 playback/drain result metadata, current `_PostAckBoundaryResult` and `_ArmedChunk` boundaries, overflow/clipping metadata, bounded pre-roll, optional VAD fakes, captureable recorder input, deterministic timing/chunk fixtures, and root recovery verification.

Implementation paths: `src/state_machine.py`, `src/player.py` result types if needed, `src/config.py` only if a compatibility/fallback switch is required, `.env.example`, `README.md`, `MANUAL_TESTING.md`, `tests/test_state_machine.py`, `tests/test_config.py` and `tests/test_documentation.py` when configuration changes, fake-backend fixtures, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: immediate speech after playback is fully present in captured pre-roll/WAV and transcript fixture; no required 0.20-second quiet pause on the synchronized path; ACK-only echo/tail cannot trigger recording; overlap/overflow/clipped chunks cannot drive voice/noise decisions; silence cancels before OpenAI; failed synchronization uses conservative fallback; ACK-disabled and VAD-disabled regressions; optional-VAD compatibility; five-cycle fake stability; focused tests, full discovery, dry-run, fake-backend, diagnose, and final `./init.sh`; final real-device acceptance repeats immediate `一加一等于几` and five wake-to-answer loops without ACK-boundary timeout or prefix loss.

Decomposition decision: the work is split into F040 and F041 because eliminating playback-time microphone backlog is an independently verifiable player/audio-lifecycle capability, while preserving immediate live speech changes the higher-risk post-ACK safety contract. F041 depends on F040 so it can relax mandatory quiet suppression only when the stream is proven synchronized; combining both would make it difficult to distinguish stale-buffer defects from boundary-policy regressions during evaluation.

## 5. Verification Plan

### Optional VAD Gating And Recording Endpointing

Goal: reduce false ARMED triggers from high-energy non-speech noise and make recording stop more naturally through an optional local WebRTC VAD boundary, while preserving all merged PR1 post-ACK safety behavior when VAD is disabled.

Included scope: disabled and lazily loaded WebRTC VAD implementations; validated VAD, ARMED, recording, hangover, end-silence, and wake-threshold settings; ARMED energy-plus-VAD gating and diagnostics; optional openWakeWord `vad_threshold`; backward-compatible recorder VAD endpointing; runtime wiring, diagnostics, docs, manual tests, and deterministic coverage.

Excluded scope: mandatory or cloud VAD, streaming STT, wake-model replacement, acknowledgement wording changes, resampling, echo cancellation, or removing RMS and maximum-duration safety gates.

Core flows: disabled VAD preserves the merged PR1 wake, safe post-ACK boundary, ARMED, clipped-pre-roll, and recording behavior. With WebRTC enabled, ARMED additionally requires configured VAD evidence and high-RMS non-voice times out locally. Recording VAD keeps speech through short gaps and stops only after configured RMS-low/VAD-low audio; max duration remains a cap. Optional `WAKE_VAD_THRESHOLD` is forwarded to openWakeWord with explicit compatibility errors.

Constraints and assumptions: WebRTC is optional and lazily imported; it accepts supported mono 16-bit PCM sample rates and 20ms frames. `RECORDING_VAD_ENABLED=true` requires an enabled backend. Existing silence, RMS, max-duration, post-ACK quiet-boundary, overflow omission, and clipped-pre-roll rules remain valid. Automated tests use fakes and synthetic PCM without live services.

Required capabilities and implementation paths: existing PCM helpers, fake VAD/model factories, configuration diagnostics, and recovery verification across `src/vad.py`, `src/config.py`, `src/state_machine.py`, `src/recorder.py`, `src/wake_word.py`, `src/main.py`, environment/docs files, tests, and harness evidence.

Verification surface: VAD unit tests; ARMED speech/non-speech and merged post-ACK regressions; wake constructor compatibility; recorder pause/endpoint/max-duration tests; config/diagnostic/docs checks; dry-run, fake-backend, diagnose, full unittest, and final `./init.sh`.

Decomposition decision: this is one optional audio-classification capability with shared configuration and runtime wiring. The default-disabled boundary keeps it independently releasable while F038/F039 remain merged prerequisites.

### Personal US Watchlist Stock Name Routing

Goal: let the assistant resolve the English and common Simplified/Traditional Chinese names from the user's supplied US watchlist to the intended ticker before reusing the existing Finnhub quote flow.

Included scope: deterministic aliases for the watchlist symbols BABA, COST, BIDU, FUTU, SAP, AMD, INTC, NVDA, TSLA, BULL, HOOD, AXP, NFLX, WMT, ORCL, GRAB, IBKR, MSFT, BRK.B, KO, QQQ, SE, GOOG, AAPL, IVV, PDD, ASML, TSM, MU, and SPCX; preservation of the existing AMZN and META aliases; `Google`, `Alphabet`, and `谷歌` resolving to GOOGL while explicit GOOG still resolves to GOOG; SpaceX resolving to SPCX; company/ETF name requests remaining conservative and requiring explicit stock intent; documentation and deterministic routing/answer-path tests.

Excluded scope: Singapore/SGX symbols or providers, dynamic Top 100 membership, watchlist persistence or UI, portfolio positions, bulk quote requests, ranking, recommendations, live-network automated tests, provider replacement, and changing Finnhub freshness or subscription behavior.

Core flows: a user asks `SpaceX 股价`, `阿里巴巴股票`, `Costco stock price`, `台积电股价`, or `纳斯达克100 ETF 股价`; the router selects the stock tool and emits SPCX, BABA, COST, TSM, or QQQ respectively; the existing Finnhub provider supplies the quote. `Google 股价`, `Alphabet stock price`, and `谷歌股价` resolve to GOOGL, while explicit uppercase `GOOG 股价` and `GOOGL 股价` retain their exact ticker. A bare ambiguous company word without a stock marker remains ordinary chat rather than triggering a realtime quote.

Constraints: aliases are project-owned deterministic data and must not make network calls; explicit uppercase ticker extraction takes precedence over aliases; aliases must use word boundaries for Latin text, avoid overly broad Chinese nicknames, preserve existing ambiguity behavior such as bare `苹果怎么样`, and never expose the Finnhub key. Automated verification uses mocked provider results only.

Ambiguities or assumptions: the screenshots are the authoritative personal US watchlist even when an issuer is foreign or an entry is an ETF. SPCX is Space Exploration Technologies Corp. for this current watchlist. GOOG remains queryable explicitly, but natural Google/Alphabet names intentionally choose GOOGL per the user's final decision. English issuer names and common unambiguous Chinese names are included; conversational descriptions such as `马斯克的公司` are excluded because they are not stable identifiers.

Required capabilities: the existing stock router, ticker-first extraction, Finnhub provider boundary and mocked quote fixture, Unicode alias matching, text-debug path, documentation tests, and root recovery verification. No new credential, dependency, service, or network capability is required.

Implementation paths: `src/tools/router.py`, `tests/test_tools.py`, `README.md`, `MANUAL_TESTING.md` when useful, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: table-driven alias tests for every watchlist ticker and representative English/Simplified/Traditional names; explicit GOOG/GOOGL precedence tests; SpaceX/SPCX regression; bare-name ambiguity tests; mocked stock answer-path/text-debug checks; full unittest discovery and final `./init.sh`.

Decomposition decision: this is one focused feature because every alias shares the same deterministic routing boundary and mocked verification surface, while the existing Finnhub provider and quote response behavior remain unchanged. SGX support is intentionally excluded after live verification showed the configured Finnhub account returns HTTP 403 for those symbols.

Run:

```bash
./init.sh
scripts/validate-feature.sh F001
scripts/summarize-progress.sh
python3 orchestrator.py --dry-run
make ci
```

Run `python3 orchestrator.py --dry-run` and `scripts/validate-feature.sh F001` outside `./init.sh`; both commands call `./init.sh` and should not be nested inside tests run by `./init.sh`.

### Best-Effort Answers For Stable Knowledge Questions

Goal: make Hey Jarvis answer non-realtime, non-high-stakes knowledge questions from the chat model's available knowledge instead of incorrectly claiming that comparison, ambiguity, or scholarly uncertainty requires internet access.

Included scope: a stronger general-chat system prompt that distinguishes stable knowledge from freshness-dependent facts; best-effort answers with concise qualifications for broad, comparative, or disputed questions; language matching; explicit guidance that lack of browsing is not by itself a reason to refuse stable questions; deterministic request-shape and prompt-contract tests; documentation and manual examples covering historical linguistics and realtime contrasts.

Excluded scope: adding web search or browsing, source retrieval or citations, changing the configured OpenAI model or API surface, guaranteeing factual correctness from prompt text alone, changing structured provider tools, weakening realtime refusals for news/live data, medical/legal/financial decision support, or making automated tests call OpenAI or the network.

Core flows: a user asks a stable question such as `中国古代人的语言交流跟现在中国哪个省份的方言类似`; the deterministic router leaves it on the ordinary chat route; the OpenAI request includes policy to identify the question's broad time/place premise, give the most useful qualified answer from available knowledge, and avoid a bare internet-required refusal. A user asks for current news, live prices, scores, weather, or another freshness-dependent fact; the existing structured route/provider or unsupported-realtime refusal remains authoritative. If a stable answer is genuinely uncertain, the assistant states the uncertainty briefly and still provides useful known context unless the request is high stakes or impossible to interpret safely.

Constraints: spoken replies remain concise, normally one or two short sentences; the assistant answers in the user's language when clear; prompt wording must not imply that the model has browsed or verified sources; existing chat history behavior and structured tool routing remain unchanged; automated verification inspects exact request shape and uses fake SDK responses with no live OpenAI or network access.

Ambiguities or assumptions: stable-versus-realtime enforcement remains split between deterministic routing and the general-chat prompt. Prompt tests can prove the policy is sent to the model but cannot prove every future model response follows it, so a documented manual live evaluation set is required. Historical comparison questions may have no single exact answer; the desired behavior is to explain the missing period/region qualifier and give a defensible best-effort comparison, not to guess one province as certain.

Required capabilities: the existing F005 OpenAI chat boundary and fake SDK request capture, F022 realtime-sensitive router/refusal behavior, documentation tests, a manual live-test path with an optional configured `OPENAI_API_KEY`, and final recovery verification. No new dependency, provider, credential, or network capability is required for implementation or automated evaluation.

Implementation paths: `src/openai_client.py`, `tests/test_openai_client.py`, `tests/test_tools.py` only if realtime regression coverage is missing, `README.md`, `MANUAL_TESTING.md`, `tests/test_documentation.py`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: prompt/request-shape tests proving stable-knowledge best effort, ambiguity qualification, language matching, no false browsing claim, and realtime boundary language are present; router regressions proving the example historical-linguistics question remains ordinary chat while current news remains refused; documentation/manual examples for stable versus realtime questions; focused unit tests; full `python3 -m unittest discover -s tests`; dry-run, fake-backend, diagnose, and final `./init.sh`; optional real OpenAI voice/text evaluation recorded as manual evidence but not required for deterministic completion.

Decomposition decision: this is one focused feature because prompt policy, chat request shape, realtime-boundary regressions, and user documentation jointly define one general-chat answer contract. Adding an actual browsing capability is independently valuable and has different dependencies, security/freshness risks, and verification surfaces, so it is explicitly deferred rather than bundled here.

### Observe Pipeline Latency And Enforce Chinese Replies

Goal: make the pipeline assistant's perceived response delay diagnosable from one runtime log and reliably answer Chinese questions in Chinese unless the user explicitly requests English wording, translation, or pronunciation.

Included scope: monotonic elapsed-time logging for recording completion, transcription, answer generation or local-tool routing, TTS generation, playback startup/completion, and the overall post-recording answer path; a stronger general-chat and tool-naturalization language contract for CJK input; explicit exceptions for requests that ask for English translation, terminology, spelling, or pronunciation; bounded timing diagnostics that do not log answer text, raw audio, credentials, or provider secrets; documentation/manual-test guidance; and deterministic tests.

Excluded scope: streaming STT, streaming TTS, changing OpenAI models, parallelizing dependent API requests, changing recorder silence or ARMED thresholds, adding automatic language detection dependencies, translating deterministic provider data before naturalization, logging complete transcripts or assistant answers, Realtime WebRTC behavior, or promising a specific live-network latency target.

Core flows: after recording stops, the assistant logs cumulative and per-stage monotonic durations for STT, answer generation, TTS, and playback so a user can distinguish audio endpointing from network/model/playback delay. A Chinese stable-knowledge question such as `中国为什么参与朝鲜战争` is sent with an explicit Simplified-Chinese response requirement. A request such as `人脸识别的英文怎么读` may include the requested English term but keeps its explanation in Chinese. English-only input remains answered in English. Local deterministic tools keep their existing answers while the state-machine timing log still covers their shorter path.

Constraints: timing uses `time.monotonic()` and does not depend on wall-clock timestamps; logs remain useful with fake clients and players; language policy is deterministic from the current user text and must not be overridden by prior chat history; prompt tests can prove the instruction is sent but cannot guarantee every live model response; existing concise one-or-two-sentence, stable-knowledge, realtime-freshness, safety, history, provider, and recovery behavior remains intact; no live OpenAI or network call is required for automated verification.

Ambiguities or assumptions: "回答我是英文的" refers to an unintended English response to a clearly Chinese question, not to the requested English term in an explicit translation/pronunciation question. CJK detection is intentionally conservative and prompt-based; mixed Chinese/English questions default to Chinese explanation unless their intent explicitly asks for English output. Playback-start timing is measured immediately before the synchronous player call, while playback duration is measured after it returns; first audible byte cannot be proven without a new observable player capability and is excluded.

Required capabilities: the existing OpenAI chat and tool-naturalization prompt boundaries, state-machine logger, injectable or patchable monotonic clock, fake OpenAI clients and players, log capture, documentation tests, and root recovery verification. No new credential, package, service, network permission, or hardware capability is required.

Implementation paths: `src/openai_client.py`, `src/state_machine.py`, focused OpenAI-client/state-machine tests, `README.md`, `MANUAL_TESTING.md`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: request-shape tests for Chinese, English, mixed explicit-English, and chat-history language precedence; tool-naturalization prompt coverage; deterministic state-machine timing tests for chat and local-tool paths with ordered non-negative stage/total metrics; tests that diagnostics omit answer content and secrets; documentation tests; full unittest discovery; dry-run, fake-backend, behavior-compatible diagnose output, final `./init.sh`; and optional real voice comparison using the user's debug-log workflow. A Codex-managed worktree without copied `.env`, `.venv`, or acknowledgement audio may report those pre-existing capability gaps rather than claiming live readiness.

Decomposition decision: this is one feature because the user reported latency and wrong-language output from the same serial post-recording answer path, and both changes share the OpenAI/state-machine observability and manual voice-test surface. The feature diagnoses rather than redesigns latency; streaming or endpoint-threshold optimization remains separately verifiable future work.

### Automatic RT004 Close And Next-Wake Recovery Evaluation

Goal: prove automatically that an explicit Realtime close tears down browser
media, restores Python wake-microphone ownership, and permits the same saved
wake fixture to establish a distinct second Realtime session before a final
clean shutdown.

Included scope: a versioned RT004 contract; offline and live-host evidence
tiers; automatic saved-wake connection for session A; explicit stop;
`host_stopped` before `wake_microphone_reopened`; an intermediate
`wake_owned` snapshot; automatic replay of the same wake fixture without
another Arm action; a distinct session B connection; a second explicit stop;
final wake recovery; sanitized evidence; CLI, documentation, deterministic
tests, full recovery verification, and evaluator-gated harness evidence.

Excluded scope: user questions, assistant responses, transcript or answer
semantics, end-phrase/idle/error close variants, changing production
close/media behavior, changing Arm policy, fresh human speech, CI hardware
automation, audio-content retention, or modifying RT001-RT003 semantics.

Core flows: from an already armed `wake_owned` host, the runner verifies the
private wake fixture exists, records the current event boundary, and replays
the fixture. Session A must become `host_active` while the Python wake
microphone is closed. The runner calls the existing stop control and observes
one `host_stopped` before one `wake_microphone_reopened`, with an intermediate
`wake_owned`/wake-microphone-open snapshot. It replays the same fixture without
another Arm click, requires session B to become active under a non-empty
identity different from session A, explicitly stops again, and requires the
same ordered cleanup plus final wake ownership. Any partial run performs
best-effort bounded cleanup and persists sanitized failure evidence.

Constraints: each active snapshot must show exclusive browser microphone
ownership; session-scoped request, acquisition, connection, stop, and reopen
events must use the correct session identity; exactly two ordered lifecycle
cycles are accepted; session identities must be distinct; stop must precede
wake reopen in both cycles; timeout and cleanup paths fail closed; the wake
fixture and all live evidence remain Git-ignored; committed evidence excludes
raw/base64 audio, transcripts, answers, credentials, ephemeral secrets, SDP,
provider bodies, tool content, and fixture bytes. Automated tests use injected
request/play/clock/sleep boundaries and no hardware, network, OpenAI, or
wall-clock waits.

Ambiguities or assumptions: RT004 uses deterministic explicit stop because it
isolates media teardown and next-wake recovery from transcription and response
semantics. “Media cleanup” is proven through the browser-confirmed
`host_stopped` lifecycle event followed by Python wake-microphone reopen and
exclusive active snapshots; committed evidence does not retain browser track
objects. The same already recorded wake fixture is reused for both cycles.
One Arm action per host launch remains a precondition, but no second Arm action
is allowed between sessions. A live-host run still requires fresh explicit
microphone/OpenAI/cost authorization even though no user utterance is needed.

Required capabilities: the F062 generic Realtime scenario schema, sanitizer
and injected live-runner boundary; the existing loopback `/api/report` and
`/api/stop` controls; the existing browser-confirmed lifecycle events; one
private saved wake fixture; an armed built-in-device Realtime host with a
usable OpenAI credential and network; temporary sanitized evidence storage;
deterministic fake hosts; full project recovery; and a separate cold-start
Evaluator Agent.

Implementation paths: `evals/realtime/scenario.schema.json`,
`evals/realtime/scenarios/RT004.json`, a project-owned RT004 runner under
`src/evals/`, focused tests under `tests/`, `README.md`,
`MANUAL_TESTING.md`, `.agent-harness/feature_list.json`,
`.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: schema/contract validation; offline pass for two
distinct ordered lifecycles; deterministic rejection of missing, duplicated,
misordered, stale, or wrong-session lifecycle events, reused identities,
concurrent microphone ownership, failed second connection, first/final cleanup
defects, and timeouts; offline CLI; RT001-RT003 regression tests; documentation
assertions; Realtime fake smoke; full unittest discovery; final root
`./init.sh`; one newly authorized built-in-device live-host pass with two
connections and no human speech; fast coding evidence; and separate evaluator
approval.

Decomposition decision: RT004 is one focused lifecycle evaluation feature. It
reuses existing production stop and wake behavior without modifying them.
RT001 separately proves one wake-to-connect handoff, RT002 proves two turns
inside one session, and RT003 proves live human barge-in; combining those
independently verifiable semantics would weaken failure attribution.

### Robust Realtime Farewell Closure

Goal: make a clearly spoken Realtime farewell such as `再见` close the active
session promptly through the existing bounded media-cleanup path instead of
being answered as an ordinary turn and eventually closing only by idle timeout.

Included scope: root-cause evidence for the two observed failures; a narrowly
scoped `end_conversation` Realtime function tool; session instructions that
require the model to call that tool for an unambiguous user request to end the
conversation and not continue with a substantive answer; Python-side
validation, de-duplication, sanitized lifecycle evidence, and stop request;
browser handling of the stopping result; preservation of the existing exact
completed-transcription end-phrase fallback; deterministic coordinator,
browser-contract, fake-smoke, documentation, and real-device verification.

Excluded scope: fuzzy substring matching, retaining transcript text, treating
mentions such as `please say goodbye` as commands, changing the configured
Realtime model/voice/VAD/output volume, replacing idle/maximum/error/explicit
stop paths, general semantic command routing, adding arbitrary Realtime tools,
or changing wake, barge-in, calculator, and RT001-RT004 evaluation semantics.

Core flows: after wake and connection, a user clearly says `再见`, `goodbye`,
`结束对话`, or otherwise unambiguously asks to end the current conversation.
The Realtime model calls only `end_conversation`; the browser forwards the
bounded function-call identity/name/arguments to Python; the coordinator
validates the active session and empty argument object, records a sanitized
`host_end_conversation_tool` event, enters `HOST_STOPPING`, and requests the
existing stop command with `end_phrase`. The browser observes the stopping
result, tears down the data channel, peer, tracks, and remote audio, reports
`stopped`, and Python reopens the wake microphone. If the official completed
input transcription exactly matches a configured end phrase first, the
existing fallback closes through the same path. Ordinary conversation,
quoted/mentioned farewell words, malformed calls, unknown tools, duplicate
events, and stale-session events must not close incorrectly.

Constraints: the API key remains in Python; no transcript, utterance, raw or
base64 audio, tool arguments, credentials, SDP, provider body, or ephemeral
secret may enter committed evidence; tool name, bounded call identity, outcome,
session identity, and close reason may be retained; the end tool must not
execute arbitrary code or return conversational output; stop remains
idempotent and session-scoped; exact transcription matching remains available
when input transcription is enabled; disabling optional transcription must not
disable semantic farewell closure; automated verification uses fakes and no
network, microphone, OpenAI, cost, or wall-clock sleeps.

Ambiguities or assumptions: the two real reports prove that microphone capture,
server speech detection, completed transcription delivery, GPT turn handling,
idle cleanup, and wake recovery worked, while `host_end_phrase_matched` did not.
Existing tests prove exact normalized `再见。` would match, so the narrow root
cause is divergence between the separate ASR rough-guide transcript and the
configured exact control phrase; privacy controls intentionally prevent
reconstructing the precise transcript. The Realtime model demonstrably
understood the utterance as a farewell because it replied conversationally, so
an explicitly advertised semantic end tool is the preferred robust control
instead of weakening exact matching with unsafe fuzzy rules. A fresh authorized
real-device run is still required to prove tool selection in the selected live
model.

Required capabilities: the existing Realtime session tool configuration and
function-call event flow, coordinator tool-call validation/de-duplication,
existing stop/media cleanup path, built-in microphone/speaker host, usable
OpenAI credential and network for final live verification, fresh explicit
microphone/OpenAI/cost authorization, deterministic fake coordinator/browser
tests, Realtime fake smoke, final project recovery, and a separate cold-start
Evaluator Agent.

Implementation paths: `src/realtime_host/static/app.js`,
`src/realtime_host/coordinator.py`, focused Realtime host/controller/fake-smoke
tests under `tests/`, `README.md`, `MANUAL_TESTING.md`,
`.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and
`.agent-harness/runs/`.

Verification surface: deterministic exact-transcription fallback tests; valid
end-tool pass with one stop request and no calculator output; malformed,
unknown, duplicate, mentioned-word, stale-session, and ordinary-conversation
non-close regressions; static browser contract assertions for advertised tool,
instructions, stopping-result handling, and cleanup; calculator regression;
Realtime fake smoke; full unittest discovery; final `./init.sh`; one newly
authorized built-in-device run where a human says a clear farewell and evidence
shows `host_end_conversation_tool -> host_stopped ->
wake_microphone_reopened` without idle timeout or substantive assistant reply;
fast coding evidence; and separate evaluator approval.

Decomposition decision: this is one focused product correction because semantic
farewell recognition, coordinator stop authorization, browser cleanup, and its
tests jointly implement one independently verifiable close behavior. General
semantic intent routing, fuzzy ASR matching, and broader tool expansion have
different false-positive and security boundaries and remain excluded.

### Realtime Current-Turn Response Language

Goal: make Realtime answer each turn in the language primarily used by the
user's current utterance, so Mandarin Chinese receives concise natural
Simplified Chinese, English receives English, and language can switch correctly
between consecutive turns in one continuous session.

Included scope: a structured Realtime session language policy; current-turn
language precedence over prior conversation, English system/tool wording, and
English tool output; concise Simplified Chinese for Mandarin Chinese input;
English for English input; mixed-language and explicit
translation/spelling/pronunciation exceptions; preservation of the F065
farewell policy; deterministic browser-contract and documentation tests; one
newly authorized bilingual live-human acceptance session; full recovery and
evaluator-gated evidence.

Excluded scope: changing the Realtime model or voice; using optional input
transcription as the language router; retaining user or assistant transcript
text; language identification in Python; supporting a configurable fixed
language mode; translating every answer; changing pipeline F058 behavior;
changing calculator semantics, farewell semantics, VAD, output volume, wake,
barge-in, RT001-RT004, or adding new tools.

Core flows: after wake and Realtime connection, a user asks a normal question
primarily in Mandarin Chinese and receives a concise spoken Simplified Chinese
answer. In the same continuous session, the user asks a normal English question
and receives an English answer despite the prior Chinese turn. A later Chinese
turn switches back to Chinese. If the current request explicitly asks for an
English translation, spelling, pronunciation, or language-learning content,
the requested English may appear while surrounding explanation follows the
current request language unless the user explicitly asks for the whole response
in another language. A clear farewell still calls `end_conversation` without a
substantive reply.

Constraints: language selection must be based on the Realtime model's
understanding of the current audio turn, not the asynchronous rough-guide
transcription; prior turns, English developer instructions, English function
descriptions, and English calculator output must not force the next reply into
English; ambiguous mixed-language input follows the language of the main
request; Chinese output uses natural Simplified Chinese; the API key stays in
Python; committed evidence excludes raw/base64 audio, transcript or answer text,
tool arguments/results, credentials, SDP, provider payloads, and ephemeral
secrets; automated tests use no network, microphone, OpenAI, cost, or wall-clock
sleep.

Ambiguities or assumptions: “Chinese input” means a current utterance whose
main conversational request is Mandarin Chinese, even if it contains English
names or terms. An explicit target-language request overrides same-language
answering only for the requested content or for the whole answer when the user
clearly asks for that. The existing `marin` voice is retained and assumed
capable of the accepted Chinese and English speech. Audible language correctness
cannot be proven from privacy-preserving lifecycle logs alone, so final external
behavior requires human confirmation; durable evidence records only turn order,
response completion, session continuity, cleanup, and the human's bounded
Chinese/English verdict.

Required capabilities: the current Realtime `session.update.instructions`
surface; official Realtime prompting guidance for structured language
constraints and code-switching; the existing WebRTC session, tools, F065 close
path, built-in microphone/speaker, usable OpenAI credential and network; fresh
explicit microphone/OpenAI/cost authorization; deterministic static host and
documentation tests; final project recovery; and a separate cold-start
Evaluator Agent.

Implementation paths: `src/realtime_host/static/app.js`, focused Realtime host
and documentation tests under `tests/`, `README.md`, `MANUAL_TESTING.md`,
`.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and
`.agent-harness/runs/`.

Verification surface: static assertions for a structured current-turn language
policy, Simplified Chinese, English, prior-turn independence, tool-output
independence, mixed/translation exceptions, and preserved farewell rules;
calculator, F065, controller, RT001-RT004, and Realtime fake-smoke regressions;
JavaScript syntax; full unittest discovery; final `./init.sh`; one newly
authorized built-in-device continuous session where a human confirms a Chinese
answer followed by an English answer and clean farewell recovery without
transcript/answer retention; fast coding evidence; and separate evaluator
approval.

Decomposition decision: F066 is one focused prompt-policy correction with one
shared implementation and verification surface. Fixed-language configuration,
automatic language telemetry, transcript retention, translation mode, and
additional language-specific product policies would be independently
verifiable features and remain excluded.

### Realtime Wake-to-Ready Latency Attribution

Goal: determine where time is spent between a confirmed local wake and a fully
configured Realtime session, so later optimization targets measured bottlenecks
instead of guessing or conflating connection readiness with wake recognition.

Included scope: privacy-bounded monotonic timing markers for confirmed wake,
local acknowledgement start/end, handoff command queueing, browser command
receipt, ephemeral-token acquisition, browser microphone acquisition, peer/SDP
setup, OpenAI WebRTC negotiation, and Realtime session configuration; a
per-session timing summary; RT001 scenario/evidence evolution that validates and
reports the phase breakdown; deterministic sanitizer/oracle/browser/controller
tests; documentation; and one newly authorized automatic RT001 live-host run.

Excluded scope: changing operation ordering; parallelizing token and microphone
work; prewarming credentials or WebRTC; changing acknowledgement playback;
adding a ready sound; changing wake thresholds, confirmation frames, model,
voice, VAD, output volume, API timeouts, or user-turn handling; imposing a
latency pass/fail threshold before a representative baseline exists; retaining
audio, transcript, response text, provider bodies, SDP, credentials, or
high-frequency timing samples.

Core flows: after two-frame local wake confirmation, Python records a bounded
`wake_confirmed` marker, records acknowledgement start and completion, and
queues the existing handoff. The browser timestamps its existing sequential
start path locally and, once `session.updated` proves readiness, emits one
bounded timing summary covering command receipt, token fetch, microphone
acquisition, peer setup, SDP negotiation, and session configuration. RT001
combines those values with coordinator timestamps, validates non-negative
bounded durations and required phase completeness, then saves a sanitized
breakdown alongside its existing exclusive-ownership and recovery verdict.

Constraints: timing uses monotonic clocks and rounded integer milliseconds;
browser durations are reported as one bounded allowlisted summary to minimize
measurement perturbation; no wall-clock correlation, request identity,
provider payload, token, transcript, raw/base64 audio, or SDP is retained;
exactly one timing summary is accepted for the active session; malformed,
negative, non-finite, oversized, duplicate, stale-session, or incomplete
timings fail closed; existing RT001 ownership/cleanup oracles remain mandatory;
the feature observes but does not optimize or establish a performance SLO.

Ambiguities or assumptions: “wake-to-ready” begins when the configured
consecutive wake detections are satisfied, not when the human begins speaking
the wake phrase, because the latter would require retaining or inferring private
audio. “Ready” means the browser has received `session.updated` for the active
Realtime session, matching the current `host_connected` transition. Browser
phase measurements share one `performance.now()` clock, while end-to-end Python
markers use the coordinator monotonic clock; only durations, not absolute
cross-clock timestamps, are combined. One live run identifies the current
dominant phase but is not treated as a stable percentile baseline.

Required capabilities: existing controller/coordinator lifecycle evidence,
browser `performance.now()`, RT001 automatic saved-wake live-host runner,
private wake fixture, armed Chrome host, usable OpenAI credential and network,
fresh explicit microphone/OpenAI/cost authorization for live verification,
deterministic offline tests, final project recovery, fast coding evidence, and
a separate cold-start Evaluator Agent.

Implementation paths: `src/realtime/controller.py`,
`src/realtime_host/coordinator.py`, `src/realtime_host/static/app.js`,
`src/evals/realtime_common.py`, `src/evals/realtime_handoff.py`,
`evals/realtime/scenarios/RT001.json`, focused tests under `tests/`,
`README.md`, `MANUAL_TESTING.md`, `.agent-harness/feature_list.json`,
`.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: deterministic controller ordering and duration tests;
coordinator timing allowlist, bounds, duplicate, stale-session, and privacy
tests; static browser-contract assertions for one batched timing report and all
required phase boundaries; RT001 scenario/oracle pass plus precise failure for
missing, negative, excessive, malformed, duplicate, or inconsistent timings;
existing RT001 ownership/recovery and RT002-RT004 regressions; JavaScript
syntax; Realtime fake smoke; full unittest discovery; final `./init.sh`; one
newly authorized automatic RT001 run whose sanitized evidence produces a phase
breakdown; fast coding evidence; and separate evaluator approval.

Decomposition decision: F067 is one measurement-only capability with one
shared purpose and verification surface. Any latency optimization, readiness
cue, acknowledgement semantic change, or numerical SLO depends on the measured
result and must be planned as a later independently verifiable feature.

### Realtime Peer/SDP Latency Decomposition

Goal: split F067's largest measured `peer_setup_ms` bucket into actionable
browser subphases, so a later optimization can distinguish local reporting and
audio-analysis overhead from RTCPeerConnection construction, offer creation,
and local-description/ICE work.

Included scope: five rounded monotonic browser subphase durations for
microphone settings/reporting, input-level analysis setup, PeerConnection plus
track/data-channel setup, `createOffer`, and `setLocalDescription`; retention of
the F067 aggregate `peer_setup_ms`; nested aggregate consistency validation;
RT001 version/evidence evolution; focused privacy, browser-contract,
coordinator, oracle, documentation, and regression tests; and one newly
authorized automatic RT001 live-host run.

Excluded scope: changing WebRTC operation ordering; parallelizing token,
microphone, acknowledgement, offer, or negotiation work; prewarming or reusing
PeerConnections; changing ICE configuration or trickle behavior; removing
input-level diagnostics; changing acknowledgement, wake, model, voice, VAD,
output volume, timeout, session, or user-turn behavior; adding a performance
threshold; or retaining browser traces, SDP, candidates, network addresses,
credentials, provider bodies, audio, transcripts, or answers.

Core flows: the browser preserves F067's existing start sequence and records
local boundaries immediately after microphone acquisition, settings/reporting,
input analyzer setup, PeerConnection/track/data-channel construction,
`createOffer`, and `setLocalDescription`. At `session.updated`, the same single
batched timing report includes the five subphase durations plus the existing
aggregate. Python validates that the subphases are bounded and sum to
`peer_setup_ms` within rounding tolerance. RT001 returns both the backward-
compatible aggregate and the finer breakdown while retaining all ownership,
connection, cleanup, and total-timing consistency checks.

Constraints: use `performance.now()` and rounded non-negative integer
milliseconds; preserve exactly one batched active-session timing report;
subphase values are allowlisted and bounded by the existing conservative
maximum; their sum must match `peer_setup_ms` within rounding tolerance;
top-level total validation must not double-count nested subphases; committed
evidence excludes SDP, ICE candidates, IP/network details, request identity,
provider payload, token, transcript, raw/base64 audio, and answer content; the
feature observes only and establishes neither an SLO nor an optimization claim.

Ambiguities or assumptions: “microphone reporting” includes rendering capture
settings and the awaited loopback `host_microphone_acquired` event; “audio
analysis setup” covers synchronous analyzer construction while asynchronous
AudioContext resume may continue outside that boundary; “PeerConnection setup”
covers constructor, event handlers, track addition, and data-channel creation;
`setLocalDescription` may include browser-controlled ICE work. These names
describe code boundaries rather than claiming an underlying browser/network
root cause. One live run is diagnostic, not a stable percentile baseline.

Required capabilities: F067 timing contract and RT001 v2 runner, browser
`performance.now()`, deterministic static and Python tests, private wake
fixture, armed Chrome host, built-in microphone, usable OpenAI credential and
network, fresh explicit microphone/OpenAI/cost authorization for final live
verification, final project recovery, fast coding evidence, and a separate
cold-start Evaluator Agent.

Implementation paths: `src/realtime_host/static/app.js`,
`src/realtime_host/coordinator.py`, `src/evals/realtime_common.py`,
`src/evals/realtime_handoff.py`, `evals/realtime/scenarios/RT001.json`, focused
tests under `tests/`, `README.md`, `MANUAL_TESTING.md`,
`.agent-harness/feature_list.json`, `.agent-harness/progress.md`, and
`.agent-harness/runs/`.

Verification surface: static browser assertions for all five boundaries and
unchanged ordering; coordinator allowlist, integer/range, incomplete,
aggregate-mismatch, duplicate, stale-session, and privacy tests; RT001 valid
breakdown plus missing, negative, excessive, malformed, or inconsistent
subphase failures; preservation of F067 top-level total validation and RT001
ownership/recovery; RT002-RT004 and Realtime fake-smoke regressions; JavaScript
syntax; full unittest discovery; final `./init.sh`; one newly authorized
automatic RT001 run with sanitized subphase evidence and final wake recovery;
fast coding evidence; and separate evaluator approval.

Decomposition decision: F068 is one deeper measurement-only capability with a
single browser implementation and RT001 verification surface. Token/ACK
parallelization, PeerConnection optimization, readiness cues, and latency SLOs
remain separate future features because they change runtime behavior or product
semantics.

### Realtime Web Audio Cold-Start Attribution

Goal: determine which synchronous operation inside `startInputLevels(stream)`
accounts for F068's observed `4379 ms` audio-analysis setup time, and compare
the first and second Realtime sessions in one armed Chrome page to assess
whether the delay is consistent with a page/audio-stack cold start or recurs
whenever the analysis graph is rebuilt.

Included scope: rounded monotonic browser subphase durations for prior
input-level cleanup, `AudioContext` construction, analyser construction and
configuration, `createMediaStreamSource`, source-to-analyser connection, and
remaining monitor startup; retention of the F068
`audio_analysis_setup_ms` aggregate; nested consistency validation; RT001
timing/evidence evolution; RT004 two-session timing comparison in one armed
page; focused privacy, browser-contract, coordinator, oracle, documentation,
and regression tests; and one freshly authorized automatic RT004 live-host run.

Excluded scope: moving, deferring, prewarming, reusing, or removing the Web
Audio graph; keeping an `AudioContext` open across sessions; changing the
Realtime/WebRTC operation order; changing ICE, token, microphone,
acknowledgement, wake, model, voice, VAD, output volume, timeouts, media
cleanup, session, or user-turn behavior; declaring a stable latency SLO or
universal browser root cause; or retaining audio, transcripts, answers,
credentials, SDP, ICE details, network addresses, provider payloads, request
identities, high-frequency samples, or raw performance traces.

Core flows: during each unchanged Realtime start, the browser records
contiguous boundaries around every synchronous operation in
`startInputLevels(stream)` and includes the resulting nested values in the
existing single active-session timing report. Python validates that these
values are complete, bounded, and reconcile to `audio_analysis_setup_ms`
without double-counting them in `peer_setup_ms` or the top-level browser-ready
total. RT001 exposes the finer breakdown. RT004 automatically creates session
A, stops and restores wake ownership, then creates session B in the same armed
Chrome page and returns both sanitized timing breakdowns for comparison before
final cleanup.

Constraints: use `performance.now()` and rounded non-negative integer
milliseconds; preserve exactly one batched timing report per active session;
all new fields are allowlisted and bounded by the existing timing limit; nested
values reconcile within rounding tolerance; the first/second-session
comparison is diagnostic evidence rather than a pass/fail performance
threshold; the implementation must not change when audio analysis,
PeerConnection creation, offer creation, negotiation, or readiness occurs;
committed evidence remains lifecycle/timing metadata only.

Ambiguities or assumptions: “cold start” is treated as a hypothesis, not an
implementation fact. A much slower first session than second session in the
same page supports page/audio-stack warm-up; comparable delays weaken that
hypothesis and suggest per-construction cost. One two-session run is still not
a stable percentile baseline. `AudioContext.resume()` is invoked without
awaiting its returned promise today, so this feature measures only the
synchronous cost of initiating resume plus the remaining buffer/timer setup;
asynchronous resume completion is not claimed. Cleanup includes any
synchronous work performed by the existing `stopInputLevels()` call.

Required capabilities: F068 timing contract, RT001 and RT004 automatic runners,
browser `performance.now()`, deterministic static and Python tests, private
wake fixture, armed Chrome host, built-in microphone, usable OpenAI credential
and network, fresh explicit microphone/OpenAI/cost authorization for a
two-session live verification, final project recovery, fast coding evidence,
and a separate cold-start Evaluator Agent.

Implementation paths: `src/realtime_host/static/app.js`,
`src/realtime_host/coordinator.py`, `src/evals/realtime_common.py`,
`src/evals/realtime_handoff.py`, `src/evals/realtime_close_recovery.py`,
`evals/realtime/scenarios/RT001.json`,
`evals/realtime/scenarios/RT004.json`, focused tests under `tests/`,
`README.md`, `MANUAL_TESTING.md`, `.agent-harness/feature_list.json`,
`.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: static browser assertions for every internal Web Audio
boundary and unchanged operation order; coordinator and shared sanitizer
allowlist, integer/range, incomplete, aggregate-mismatch, duplicate,
stale-session, and privacy tests; RT001 valid fine-grained breakdown plus
precise malformed failures; RT004 exactly two distinct same-page sessions with
one valid timing report each and preserved cleanup/recovery oracles; RT002 and
RT003 regressions; JavaScript syntax; Realtime fake smoke; full unittest
discovery; final `./init.sh`; one freshly authorized automatic RT004 live run
whose sanitized evidence compares session A and B; fast coding evidence; and
separate evaluator approval.

Decomposition decision: F069 is one measurement-only capability because the
internal timing fields and two-session comparison answer the same cold-start
hypothesis through one browser/eval verification surface. Any change that
moves, reuses, prewarms, or conditionally disables input-level analysis will be
a later independently verifiable optimization feature based on F069 evidence.

### Realtime On-Demand Input-Level Diagnostics

Goal: remove the optional browser input-level analyser from the normal
Realtime connection-critical path while preserving F060's explicitly requested
near-end diagnostic capability.

Included scope: make input-level monitoring disabled for ordinary Realtime
handoffs; add a bounded host API that arms monitoring for exactly the next
handoff; have the F060 live runner request that one-shot mode before playing its
wake fixture; carry the boolean only on the resulting start command; preserve
the complete F069 timing schema with zero-valued audio-analysis subphases when
monitoring is skipped; and update focused tests and operator documentation.

Excluded scope: prewarming or reusing `AudioContext`, changing WebRTC,
PeerConnection, token, microphone, acknowledgement, wake, ICE, AEC, noise
suppression, automatic gain control, VAD, output volume, model, voice, session,
timeout, interruption, cleanup, or user-turn behavior; changing F060's
classifier or privacy contract; adding a latency SLO; or enabling diagnostics
through an ambient global setting that can silently affect later sessions.

Core flows: an ordinary wake creates a start command without input-level
diagnostics, the browser records all analysis timing boundaries at one instant
without creating an `AudioContext`, and the remaining WebRTC setup proceeds
unchanged. Before an F060 live run, the runner requests one-shot diagnostics
while the host is armed and wake-owned; the next start command carries the
explicit flag, the browser runs the existing bounded analyser, and cleanup
closes it as before. The one-shot request is consumed by that handoff, including
when startup later fails, so subsequent sessions return to the normal path.

Constraints: the enable request is accepted only while the armed coordinator
is `wake_owned`; the browser treats only the literal boolean `true` as enabled;
default and malformed or absent command detail fail safe to disabled; no
diagnostic mode or high-frequency level sample is retained beyond existing
bounded lifecycle evidence; F069 aggregate and nested timing validation remains
strict; zero values mean a deliberately skipped optional phase rather than
missing evidence; and committed evidence excludes audio, transcripts, answers,
credentials, SDP, ICE details, addresses, request identities, provider bodies,
or raw performance traces.

Ambiguities or assumptions: F060 is the only current workflow that requires
continuous input-level summaries. RT003 uses server VAD events and does not
need the analyser. A fresh RT001 live result can demonstrate removal from the
normal critical path, while deterministic browser/coordinator/F060 tests are
sufficient to preserve the opt-in diagnostic branch without spending another
live diagnostic session unless a later regression requires it. One RT001 run is
diagnostic evidence and does not establish a stable latency percentile.

Required capabilities: F069 timing contracts, the existing loopback host API
and F060 runner, deterministic browser/coordinator/runner tests, JavaScript
syntax verification, private wake fixture, armed Chrome host, built-in
microphone, usable OpenAI credential and network, fresh explicit
microphone/OpenAI/cost authorization for final RT001 live verification, final
project recovery, fast coding evidence, and a separate cold-start Evaluator
Agent.

Implementation paths: `src/realtime_host/coordinator.py`,
`src/realtime_host/server.py`, `src/realtime_host/static/app.js`,
`src/evals/realtime_input_diagnosis.py`, focused tests under `tests/`,
`README.md`, `MANUAL_TESTING.md`, `.agent-harness/feature_list.json`,
`.agent-harness/progress.md`, and `.agent-harness/runs/`.

Verification surface: coordinator state, one-shot consumption, command
allowlist, and cross-session reset tests; server endpoint tests; browser static
and JavaScript syntax checks proving ordinary starts skip `AudioContext` while
explicit starts retain the existing analyser; F060 runner ordering and cleanup
tests; F069 timing consistency plus RT001-RT004 and privacy regressions;
Realtime fake smoke; full unittest discovery; final `./init.sh`; one freshly
authorized automatic RT001 normal-path live run with zero audio-analysis
timings and final wake recovery; fast coding evidence; and separate evaluator
approval.

Decomposition decision: F070 is one coherent optimization because the
normal-path removal and one-shot F060 preservation are two sides of the same
conditional diagnostic boundary and share the same host-command, browser, and
regression surface. Prewarming/reuse, numerical latency gates, and unrelated
WebRTC optimizations remain separate features.
