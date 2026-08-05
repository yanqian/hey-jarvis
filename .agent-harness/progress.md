# Progress

## Current System Status

Project minspec has been accepted for a simple macOS voice assistant MVP named Hey Jarvis.

F120 provider-native coding and owner-led bilingual target-Mac acceptance pass.
Each wake now captures one bounded `en` or `zh-CN` preference and carries it as
an explicit cue locale; the browser preloads all four validated canonical
assets before arming, uses the snapshot for both ACK and farewell, and never
uses UI state, GPT output, transcription, or conversation language to choose a
fixed cue. Switching Settings affects the UI immediately but fixed cues only on
the next wake. Existing ACK input gating, cached-farewell no-response behavior,
exactly-once cleanup, and per-turn Realtime discussion language remain intact.
The owner confirmed complete English and Chinese wake/discussion/farewell/
rewake flows on the refreshed Debug app. Focused tests, 470 project tests, 12
sidecar tests, 30 Rust tests, JavaScript syntax, Realtime fake smoke, and the
bundled app pass. Coding and live evidence are in
`.agent-harness/runs/F120-fast-coding.md` and
`.agent-harness/runs/F120-live-acceptance.md`; separate cold-start approval is
recorded as `EVAL_PASS: F120` in
`.agent-harness/runs/20260805T170500Z-F120-evaluation-pass.md`.

F119 provider-native coding, bounded paid generation, and owner selection are
complete. The owner authorized at most three English ACK and three English
farewell generations; exactly six successful `gpt-4o-mini-tts` / `alloy`
calls produced validated candidates, with no retry or extra call. After
auditioning all candidates on the target Mac, the owner selected warm
`candidate-02` for both `I'm here. Yes?` (1,416 ms) and `See you.` (738 ms).
Locale-explicit canonical WAVs and privacy-safe manifests validate at 24 kHz
mono PCM, gain 0.5, 40 ms leading/trailing silence, and exact SHA-256 digests.
They prepare byte-identically and are declared beside the unchanged Mandarin
assets in Tauri and sidecar packaging. Eighteen focused tests and a current
Debug build pass. Final recovery passes 465 project tests, 11 Mac
frontend/fake-sidecar tests, 30 Rust tests, and all smoke paths. Separate
cold-start evaluation passed; evidence is in
`.agent-harness/runs/F119-fast-coding.md` and
`.agent-harness/runs/20260805T164338Z-F119-evaluation-pass.md`.

F121 provider-native coding and native visual acceptance are complete. The
Language setting now presents one heading, one combined timing explanation,
and the unchanged selector; it aligns as one row at regular widths and stacks
at compact widths. English and Chinese same-source previews and the rebuilt
native Debug app pass at 560x600 and full-screen sizes. Accessibility exposes
one localized heading, one localized description, and one named popup. Seventeen
focused tests pass, the current-source Debug build succeeds, and final recovery
passes 460 project tests, 11 Mac frontend/fake-sidecar tests, 30 Rust tests, and
all smoke paths. Separate cold-start evaluation passed. Evidence is in
`.agent-harness/runs/F121-fast-coding.md`,
`.agent-harness/runs/F121-visual-acceptance.md`, and
`.agent-harness/runs/20260805T160500Z-F121-evaluation-pass.md`.

The owner requested a focused follow-up to F118: collapse the Language setting
from two visible labels and two explanations into one `Language` heading, one
sentence preserving both timing facts, and the existing right-aligned selector.
F121 owns only that bilingual semantic/responsive presentation refinement;
F119-F120 were temporarily lowered so interactive work selected F121 without
starting the separately authorized paid English-audio workflow. Their P0
priority is restored after F121 approval; no paid generation was started.

F118 provider-native coding and local visual acceptance pass. Preferences now
store one bounded `en` or `zh-CN` choice, migrate the existing Smart Speaker
setting, and initialize an absent choice from macOS preferred languages.
Exactly two General choices localize all app-owned WebView, native-menu,
window, accessibility, dynamic status/error, and secure-prompt text. The
loopback page observes changes through its existing local poll, so language
switching does not stop or restart the sidecar, release media, alter the Smart
Speaker assertion, or disturb an active session. The current-source Debug app
passed English and Chinese ordinary/compact and fullscreen inspection, with
every Settings panel checked in Chinese. Final recovery passed 460 project
tests, 11 Mac frontend/fake-sidecar tests, 30 Rust tests, and all smoke paths.
Coding and visual evidence are in `.agent-harness/runs/F118-fast-coding.md` and
`.agent-harness/runs/F118-visual-acceptance.md`; separate cold-start approval is
recorded as `EVAL_PASS: F118` in
`.agent-harness/runs/20260805T155003Z-F118-evaluation-pass.md`.

The owner-approved bilingual requirement is normalized in `SPEC.md` and
decomposed into F118-F120. The app will offer exactly English and Simplified
Chinese, resolve an absent first-run preference from the macOS preferred
language, localize all app-owned UI while leaving internal codes stable, and
apply a language change immediately to UI without restarting the sidecar or
disturbing an active voice session. Fixed cached cues follow one app-language
snapshot per wake rather than GPT or transcription language: English says
`I'm here. Yes?` and `See you.`, while Chinese retains the accepted assets.
Ordinary Realtime discussion continues to follow each current user turn. F118
owns preference migration and UI localization, F119 owns explicitly authorized
paid English asset generation plus owner selection, and F120 owns cross-process
cue selection, input gating, teardown, and target-Mac overall-flow acceptance.

F117 provider-native coding and owner asset selection are complete. The owner
rejected 827 ms candidate-01 as too heavy, then selected the light/casual
candidate-03 over the 784 ms soft candidate-02. After silence analysis and owner
approval, its front was trimmed by 20 ms to 580 ms while the natural trailing
decay was preserved. Candidate-03 is promoted as a checked 24 kHz mono PCM
`gpt-4o-mini-tts` / `alloy` asset. Realtime now defaults
to preloading and playing that local Mandarin `再见` through the shared browser
audio element, without a farewell `response.create`; `realtime` remains the
validated rollback. Input mute, bounded failure, exactly-once teardown, and
wake recovery retain F107 semantics. English and language selection remain
deferred. Focused tests, 458 project tests, 11 sidecar tests, 27 Rust tests,
JavaScript syntax, and Realtime fake smoke pass. The owner-led target-Mac flow
also passes: the owner heard the cached farewell, judged its ending natural,
and successfully woke the assistant a second time after cleanup; bounded
lifecycle diagnostics confirm two `busy -> wake_listening` cycles in the same
sidecar session. Independent approval is recorded as `EVAL_PASS: F117` in
`.agent-harness/runs/20260805T103500Z-F117-evaluation-pass.md`.

F116 is evaluator-approved. It removes two redundant General micro-labels and
two misplaced internal dividers while preserving one clear boundary between
Setup and Smart Speaker Mode, then places the second boundary above the
independent local-before-wake privacy note. Settings and Done remain fully
visible in native fullscreen. Runtime behavior and other panels are unchanged.
Focused contracts, Debug and release builds, native fullscreen inspection, 456
project tests, 11 Mac app tests, 27 Rust tests, and all smoke paths pass.
Independent approval is recorded as `EVAL_PASS: F116` in
`.agent-harness/runs/20260805T092826Z-F116-evaluation-pass.md`. F112 is restored
to P0 after the temporary interactive selection override.

F115 provider-native coding and local visual acceptance pass. Settings now has
one compact live Voice status component instead of duplicate availability
sentences. General separates Assistant setup from Smart Speaker Mode while
keeping each action beside the state it affects. Per owner visual feedback,
the two section containers are unboxed: headings, whitespace, and one quiet
divider provide hierarchy, and only the actionable readiness and Smart Speaker
surfaces retain card borders. The complete sleep/wake safety explanation is an
accessible native disclosure, and the local-before-wake privacy boundary stays
separate. Regular and compact Debug-app inspection, 33 focused tests, 456
project tests, 11 Mac app tests, 27 Rust tests, and all smoke paths pass.
Coding and visual evidence are in `.agent-harness/runs/F115-fast-coding.md` and
`.agent-harness/runs/F115-visual-acceptance.md`. Independent approval is
recorded as `EVAL_PASS: F115` in
`.agent-harness/runs/20260805T090405Z-F115-evaluation-pass.md`.

F114 provider-native coding and target-Mac Settings acceptance pass. Settings
is now a singleton native window that leaves the main loopback runtime,
sidecar PID/session, wake availability, retained media, and Smart Speaker
assertion unchanged during ordinary inspection. Done closes only Settings.
Credential changes and explicit microphone checks use F113 safe shutdown and
keep a focused Resume action visible until real `wake_listening`; microphone
probing is bounded and retains no late stream. The live neutral trial kept PID
87782 and session `session-b63348070cf583adb541bed08a9a40b1` at Wake listening,
and the runtime-affecting trial stopped in about 220 ms with no new Python crash
report or exit dialog. Final `./init.sh` passed 456 project tests, 11 Mac app
tests, 27 Rust tests, and all smoke paths. Coding and live evidence are in
`.agent-harness/runs/F114-fast-coding.md` and
`.agent-harness/runs/F114-live-acceptance.md`. Independent approval is recorded
as `EVAL_PASS: F114` in
`.agent-harness/runs/20260805T153238Z-F114-evaluation-pass.md`.

F113 provider-native coding and target-Mac acceptance pass. Shutdown is now an
idempotent boundary shared by ProductRuntime, the controller, and the handoff
coordinator: cancellation is published before teardown, shutdown-time stream
failures cannot invoke wake recovery, late host cleanup cannot reopen the
microphone, and the non-daemon controller is joined before server, PortAudio,
detector, or interpreter finalization. Python has a four-second join bound and
the native supervisor a five-second grace period. Focused concurrency tests,
456 project tests, 11 Mac frontend/sidecar tests, 27 Rust tests, all smoke paths,
and a fresh Debug build pass. In the live `open_settings` shutdown trial,
`shutdown_requested -> process_stopped` took about 406 ms, the Python process
exited, and the six-report crash baseline remained unchanged with no new
`OpenAndSetupOneAudioUnit` report or Python-exit dialog. Coding and live evidence
are in `.agent-harness/runs/F113-fast-coding.md` and
`.agent-harness/runs/F113-live-acceptance.md`. Independent approval is recorded
as `EVAL_PASS: F113` in
`.agent-harness/runs/20260805T065031Z-F113-evaluation-pass.md`.

F106 is evaluator-approved after provider-native coding and owner-led target-Mac
acceptance. The explicit-sleep trial released the active
assertion, stopped the old sidecar, made one automatic wake attempt, and
returned to truthful `wake_listening` about 5.9 seconds after wake without a
Resume click. The recovered declarative Settings link opened on the first
click, and the owner heard the requested time answer, ended the conversation
with the farewell phrase, and woke the assistant again. Durable external
evidence is recorded in `.agent-harness/runs/F106-live-acceptance.md`.

Target-Mac diagnostics originally reproduced the reported screen as the
existing `system_will_sleep -> sidecar_stopped -> system_did_wake` path: this
was not a 30-minute application expiry, and the old wake callback deliberately
did not restart voice listening. The correction records only whether Smart
Speaker Mode was genuinely active, releases media and the power assertion,
runs one off-callback-thread recovery attempt, accepts success only at real
`wake_listening`, and falls back after 15 seconds to a focused Resume screen.
The Home gear is now a declarative custom-scheme link, so native Settings
navigation remains available even if asynchronous cleanup fails. Stale timeout,
mode-off, one-attempt, Resume UI, JavaScript, 454 project tests, 10 app tests,
27 Rust tests, release build, and final recovery verification pass. Fast coding
evidence is recorded in `.agent-harness/runs/F106-fast-coding.md`, and separate
cold-start approval is recorded as `EVAL_PASS: F106` in
`.agent-harness/runs/20260805T042628Z-F106-evaluation-pass.md`. The owner
separately identified the pre-existing
Settings stop policy as too coarse after it exposed a repeatable Python/
PortAudio shutdown race. Per owner direction, F106 will be committed separately
and a new normalized feature will keep the sidecar alive for ordinary Settings
use, rebuild audio only when required, and make genuine shutdown race-free.

F110 is evaluator-approved. Three digitally captured `gpt-realtime-2.1` /
`alloy` candidates passed bounded validation and wake recovery; the owner
selected the 2,429 ms `candidate-02`. The canonical asset and manifest are
under `assets/`, its prepared runtime copy has the same SHA-256, and unselected
candidates remain Git-ignored. Fast coding evidence is recorded in
`.agent-harness/runs/F110-fast-coding.md`, and independent approval is recorded
as `EVAL_PASS: F110` in
`.agent-harness/runs/20260804T101500Z-F110-evaluation-pass.md`.

F111 is evaluator-approved after coding and an owner-authorized target-Mac
overall-flow run.
The default cached mode prevalidates and preloads the selected WAV, starts it
through the browser's shared Realtime output element while the unified WebRTC
session connects, and keeps the input track disabled until both cached playback
and configured-session barriers finish. Explicit `realtime` and `local`
rollback modes remain available. The target-Mac run began cached playback 411
ms after wake and reached input readiness at 3,416 ms; the owner heard the
cached ACK, normal answer, and native farewell, and wake ownership recovered 83
ms after farewell playback. Fast coding evidence is recorded in
`.agent-harness/runs/F111-fast-coding.md`, and independent approval is recorded
as `EVAL_PASS: F111` in
`.agent-harness/runs/20260804T141335Z-F111-evaluation-pass.md`.

F105 is evaluator-approved after its owner-led target-Mac lock acceptance. The first two trials
isolated two independent boundaries: the native assertion was initially
released on `wake_listening -> busy`, and a corrected run then showed locked
WKWebView microphone acquisition taking 13,443 ms. An unchanged Chrome A/B
completed the same locked media lifecycle, narrowing the second issue to
WKWebView's cold media startup rather than the shared coordinator or Realtime
path.

The product correction keeps the one-time Enable gesture and, only in Smart
Speaker Mode, retains its disabled WKWebView microphone track and primes the
existing `<audio>` element with that live stream at zero volume. Wake then
reuses the live input track and swaps the already-playing element to the remote
Realtime stream. The final locked trial acquired the microphone in 5 ms,
reached browser readiness in 2,019 ms, played ACK and the time answer audibly
while locked, recognized the semantic end phrase, stopped cleanly, and reopened
local wake ownership. The native assertion stayed process-owned with no display
sleep assertion or product `caffeinate`. Full evidence is in
`.agent-harness/runs/F105-fast-coding.md`; independent approval
is recorded as `EVAL_PASS: F105` in
`.agent-harness/runs/20260804T060635Z-F105-evaluation-pass.md`.

F086 is complete at commit `cd8e4d7`. Its isolated Tauri 2, WKWebView, and
Python-sidecar spike passed offline, packaged-app, Apple Silicon live-device,
audible playback, natural interruption, media-release, bounded Python
microphone-reacquisition, parent-loss cleanup, and separate evaluator gates.
The spike remains isolated under `spikes/tauri_realtime/` and is feasibility
evidence only.

The productization requirement has been normalized in `SPEC.md` and,
after user confirmation, decomposed into F087-F093. The portfolio-grade,
local-first architecture makes Rust/Tauri the native security and supervision
boundary, WKWebView the Realtime media endpoint, and the packaged Python
sidecar the owner of reusable wake, coordination, tool, and OpenAI behavior.
The CLI remains the simplest personal-use and recovery path. The current beta
scope uses user-provided Keychain credentials and a manually updated Apple
Silicon macOS 14+ DMG that is explicitly unsigned and restricted to owner-led
or trusted internal testing. Public binary distribution, Developer ID signing,
notarization, a hosted backend, accounts, billing, telemetry, and automatic
updates are excluded from the current plan.
F087 is complete at commit `95524d7`. F088 is evaluator-approved after
provider-native coding and an authorized Apple Silicon live run recorded in
`.agent-harness/runs/F088-fast-coding.md` and
`.agent-harness/runs/F088-live-acceptance.md`; independent approval is recorded
as `EVAL_PASS: F088` in
`.agent-harness/runs/20260731T101439Z-F088-evaluation-pass.md`.
F089 is evaluator-approved and committed as `12a0874`; its BYOK Keychain,
private bootstrap, first-run disclosure, TCC denial/re-enable, and non-listening
recovery evidence is durable in the F089 run records. F090 is
evaluator-approved after reproducible Python 3.12/TFLite onedir packaging,
dependency/license/model/native-code inventories, offline packaged smokes,
byte-identical normalized rebuilds, and measured sidecar/app/DMG-candidate
footprints. Independent approval is recorded as `EVAL_PASS: F090` in
`.agent-harness/runs/20260801T180500Z-F090-evaluation-pass.md`.
F091 is evaluator-approved after lifecycle-only rotating diagnostics across
Rust/WebView/Python, redacted versioned support export and clear controls,
deterministic media/process cleanup, native sleep/wake handling, and bounded
non-paid sidecar crash recovery. The authorized release-App trial also found
and fixed omitted frozen Realtime static assets. Independent approval is
recorded as `EVAL_PASS: F091` in
`.agent-harness/runs/20260802T064406Z-F091-evaluation-pass.md`.

F085 has been completed through evaluator-gated fast work after a user-observed
Realtime session closed 15.024 seconds after its last completed response. The
default idle window is now 60 seconds, the local `.env` test profile is aligned,
and coordinator playback state prevents idle closure between
`host_playback_started` and `host_playback_stopped`; the existing 600-second
maximum duration remains authoritative if playback-stop evidence never
arrives. Playback stop restarts the full idle window, and playback state resets
across cleanup and fresh handoff. Focused configuration, coordinator,
controller, and documentation coverage passes with 64 tests; final recovery
passes with 380 project tests plus pipeline and Realtime fake smokes. Coding
evidence is recorded in `.agent-harness/runs/F085-fast-coding.md`, and separate
cold-start approval is recorded as `EVAL_PASS: F085` in
`.agent-harness/runs/20260730T071947Z-F085-evaluation-pass.md`.

F075 has been completed through evaluator-gated fast work, three user-led
built-in-device sessions, and separate cold-start evaluator approval. The
browser now sends SDP only to the loopback host; Python combines it with the
complete validated session configuration in one unified Realtime call. The
ephemeral-token request and post-connect `session.update` are removed while
F074's disabled-track, audible acknowledgement, and explicit input-enable
boundary remain intact. All three removed token phases were zero, no speech
occurred before input readiness, and final wake ownership recovered. Median
wake-to-configured latency fell from F074's 5,066 ms to 2,081 ms in the bounded
same-device comparison. Approval is recorded as `EVAL_PASS: F075` in
`.agent-harness/runs/20260727T083331Z-F075-evaluation-pass.md`.

F074 has been completed through provider-native fast coding, user-led
built-in-device acceptance, and separate cold-start evaluator approval.
Confirmed wake now queues Realtime immediately; the browser sends silence
through a disabled outgoing track until configuration readiness; Python then
plays “在呢” and explicitly enables input. `host_connected` is the input-ready
boundary. JavaScript syntax, 346 project tests, Realtime fake smoke, and final
recovery pass. Three live sessions showed no speech event before input
readiness; the normal interactive session completed multiple playback turns
and semantic ending, and every session restored wake ownership. Approval is
recorded as `EVAL_PASS: F074` in
`.agent-harness/runs/20260727T090000Z-F074-evaluation-pass.md`.

F073 has been completed through evaluator-gated fast work, a user-led Mac
built-in-microphone/speaker run, and separate cold-start evaluator approval.
The Realtime host now prefers the strongest browser-advertised standardized
echo-cancellation mode with a required fallback, enables validated far-field
input noise reduction, and records playback-buffer lifecycle separately from
response generation. At local output volume 0.3, one normal answer played
continuously for 5,557 ms without false speech, deliberate near-end speech
cancelled an active reply and received a continuation, and the intentional
ending restored wake ownership. The checked-in volume default remains 0.1
pending broader device evidence. Approval is recorded as `EVAL_PASS: F073` in
`.agent-harness/runs/20260727T070000Z-F073-evaluation-pass.md`.

F072 has been completed through evaluator-gated fast work and separate
cold-start evaluator approval. Active recovery state now agrees on the latest
completed feature and empty next-feature queue; the README points directly to
`.agent-harness/runs/`; and the Realtime barge-in Known Issue incorporates
F061's accepted synchronized RT003 result instead of the superseded F060
follow-up. Focused documentation regressions cover both active completion
sections, Current/Next Feature state, the run-evidence path, and the F061
wording. The final evaluator approval is recorded as `EVAL_PASS: F072` in
`.agent-harness/runs/20260727T000000Z-F072-evaluation-pass.md`.

F071 has been completed through evaluator-gated fast work and separate
cold-start evaluator approval. The 909-line
`README.md` is now a 151-line project landing page with backend choice, quick
start, common commands, privacy/safety boundaries, and a task-oriented
documentation map. `DEPLOYMENT.md` is focused on install/prepare/verify/run and
update operations; complete configuration, pipeline behavior, Realtime
operation/evaluations, and troubleshooting now have clear owners under
`docs/`. Documentation contracts enforce the README size boundary, every
`.env.example` key, CLI discoverability, Realtime/privacy/eval contracts,
developer-reference boundaries, and local Markdown links. `MANUAL_TESTING.md`,
root `SPEC.md`, runtime source, spikes, and internal project history were not
rewritten. Focused documentation tests and final recovery verification pass
with 341 project tests. Coding evidence is recorded in
`.agent-harness/runs/F071-fast-coding.md`, and approval is recorded as
`EVAL_PASS: F071` in
`.agent-harness/runs/20260724T095252Z-F071-evaluation-pass.md`.

F001 created the project-owned Python skeleton and updated root `./init.sh` into a project recovery contract. The recovery check now verifies the harness, required project files, Python compilation, unit tests, and a dependency-free dry-run smoke path.

F002 has been implemented and evaluator-approved. The code now includes dependency-free configuration loading, typed validation, runtime diagnostics, CLI diagnostics output, documented `.env.example` settings, and focused unit tests.

F003 has been implemented by manual Coding Agent fallback and evaluator-approved. The code now includes a reusable `sounddevice` microphone stream wrapper, deterministic int16 PCM RMS silence detection, WAV recording to `tmp/input.wav`, synthetic-PCM tests that do not require real microphone access, and durable evaluator evidence in `runs/F003-evaluation.md`.

F004 has been implemented by manual Coding Agent fallback and evaluator-approved. The code now includes a lazy-loading openWakeWord `WakeWordDetector` boundary for the built-in Hey Jarvis model, threshold-based detection from PCM chunks, clear load and inference error logging, fake-model tests that do not require microphone input or installed ML dependencies, and durable evaluator evidence in `runs/F004-evaluation.md`.

F005 has been implemented by manual Coding Agent fallback and evaluator-approved. The code now includes a lazy-loading OpenAI client boundary for transcription, chat completions with bounded in-memory history, and text-to-speech MP3 output; tests verify request shape, response handling, output file writing, and actionable missing-credential errors without live API access, with durable evaluator evidence in `runs/F005-evaluation.md`.

F006 has been implemented by manual Coding Agent fallback and evaluator-approved. The code now includes macOS `afplay` playback, a WAIT_WAKE -> RECORDING -> TRANSCRIBE -> ASK_OPENAI -> TTS -> PLAYING -> WAIT_WAKE state machine, `python -m src.main` real runtime wiring, a dependency-free `--fake-backend` full-loop smoke path, focused unit tests, README real-demo instructions, and durable evaluator evidence in `runs/F006-evaluation.md`.

F007 has been implemented by manual Coding Agent fallback and evaluator-approved. The README now documents setup, virtualenv dependency installation, `.env` creation, `OPENAI_API_KEY`, macOS microphone permission, `afplay`, real-demo operation, troubleshooting, and post-MVP iterations; `tests/test_documentation.py` verifies documented CLI modes, `.env.example` keys, runtime requirements, and post-MVP TODOs stay in sync, with durable evaluator evidence in `runs/F007-evaluation.md`.

F008 has been implemented by manual Coding Agent fallback and evaluator-approved. The real wake-word path now explicitly uses openWakeWord ONNX models through `onnxruntime`, includes `python -m src.main --prepare-wake-word` to download the required ONNX model files, reports missing `onnxruntime` or model files through `--diagnose`, documents the preparation step, and includes regression tests plus durable evidence in `runs/F008-manual-coding.md`.

F009 has been implemented through orchestrator Coding Agent and evaluator-approved. The real assistant now constructs, loads, and warms the `WakeWordDetector` before opening the microphone stream; the default microphone chunk size is 1280 frames; preload logs are visible before listening begins; troubleshooting documents `WAIT_WAKE` microphone overflow; focused tests cover startup ordering, chunk sizing, documentation, and warmup without real microphone access; and durable evaluator evidence is recorded in `runs/F009-evaluation.md`.

F010 has been completed through the orchestrator entrypoint, with the Coding Agent run recorded as an interactive manual fallback and the Evaluator Agent approving it. The code now includes live microphone wake debug output, WAV-file wake scoring, `WAKE_DEBUG=1` WAIT_WAKE score logging, PCM RMS/peak metrics, overflow surfacing from the microphone wrapper, README troubleshooting guidance, deterministic tests that do not require physical microphone access, and durable evaluator evidence in `runs/F010-evaluation.md`.

F011 has been implemented by manual fallback after the orchestrator Coding Agent adapter hung waiting for a child process, and evaluator-approved. The wake debug workflow now supports explicit live PCM capture to a mono 16 kHz 16-bit WAV file, high-precision score and threshold output, live and file replay summary metrics, deterministic short final chunk replay, README record-and-replay guidance, focused tests using generated fixtures and fakes without physical microphone access, and durable evaluator evidence in `runs/F011-evaluation.md`.

F012 has been completed through the orchestrator entrypoint, with Coding Agent implementation and Evaluator Agent approval recorded. The default wake phrase and openWakeWord model are now Alexa, wake model preparation and diagnostics target the Alexa ONNX asset plus feature models, runtime logs and README examples use Alexa as the accepted wake phrase, and focused tests cover Alexa loader arguments, score-key extraction, preparation paths, diagnostics, documentation, and recovery checks without physical microphone access. Durable evaluator evidence is recorded in `runs/F012-evaluation.md`.

Manual wake-word debugging after F012 showed the openWakeWord path is blocking the MVP: both the original Hey Jarvis model and the Alexa model failed to wake reliably in live use, and captured/TTS replay produced tiny scores far below useful thresholds despite valid 16 kHz mono int16 chunking. The next recovery direction is to stop tuning openWakeWord for the MVP and switch the active wake-word runtime to Picovoice Porcupine with a user-provided Picovoice AccessKey.

F013 has been completed through the orchestrator entrypoint, with Coding Agent implementation and Evaluator Agent approval recorded. The active wake-word path now uses Picovoice Porcupine with `PICOVOICE_ACCESS_KEY`, built-in keyword `jarvis`, configurable `PORCUPINE_SENSITIVITY`, engine `frame_length`, and engine `sample_rate`; openWakeWord, ONNX model preparation, and `onnxruntime` are no longer active-path requirements. Wake debug and WAV replay remain available with deterministic 0/1 Porcupine detection output and final short-frame padding. Durable evaluator evidence is recorded in `runs/F013-evaluation.md`.

F014 has been completed through the orchestrator entrypoint, with Coding Agent implementation and Evaluator Agent approval recorded. The active wake-word runtime has been restored to the previously accepted F012 Alexa/openWakeWord ONNX path after the user reported they cannot obtain a Picovoice AccessKey. The restored path includes ONNX model preparation, diagnostics, documentation, 1280-frame wake debug/replay behavior, and focused regression tests. This is a usability rollback that removes the Picovoice account capability gap from the active path; it does not fix the known Alexa low-score recognition behavior. Durable evaluator evidence is recorded in `runs/F014-evaluation.md`.

F015 has been completed through the orchestrator entrypoint, with Coding Agent implementation and Evaluator Agent approval recorded. The active Alexa/openWakeWord path now defaults to configurable TFLite inference with `WAKE_BACKEND=openwakeword`, `WAKE_MODEL=alexa`, `WAKE_INFERENCE_FRAMEWORK=tflite`, and `WAKE_THRESHOLD=0.5`; detector construction, model preparation, diagnostics, live/file wake debug output, `scripts/debug_oww_file.py`, README, `.env.example`, requirements, and focused tests are framework-aware. The implementation adds a macOS ARM64 guard that rejects explicit ONNX selection with guidance to use TFLite, and records durable TFLite runtime capability through `ai-edge-litert` requirements and diagnostics. Durable evaluator evidence is recorded in `runs/F015-evaluation.md`.

F016 has been implemented by manual Coding Agent fallback and evaluator-approved. The real assistant loop now treats `OpenAIClientError` from transcription, chat, or text-to-speech as recoverable: it logs the failure, returns to `WAIT_WAKE`, skips downstream stages that depend on the failed stage, and keeps the long-running process alive. Focused tests cover the user-observed empty transcription traceback, chat/TTS recovery, unexpected exception propagation, and the successful loop. README and deployment troubleshooting now document empty transcription recovery. Durable evaluator evidence is recorded in `runs/F016-evaluation.md`.

F017 has been implemented by manual Coding Agent fallback after root `make work` was unavailable in this hidden-layout project. The user-observed failure was an immediate false wake after answer playback, preceded by microphone overflow, followed by a max-duration silent recording and empty transcription recovery. The assistant now suppresses wake detection for a configurable post-playback microphone drain window, ignores overflowed chunks during normal wake listening, and requires configurable consecutive wake-positive frames before entering `RECORDING`. `.env.example`, README, DEPLOYMENT, and MANUAL_TESTING document `POST_PLAYBACK_WAKE_COOLDOWN_SECONDS`, `WAKE_CONFIRMATION_FRAMES`, and manual retesting. Focused tests simulate playback residue and overflow without real hardware, and `./init.sh` verifies the fake-backend smoke path remains deterministic. Durable evaluator evidence is recorded in `runs/F017-evaluation.md`.

F018 has been implemented by manual Coding Agent fallback after the user reported F017 was still insufficient: after the fixed 1.0s drain, two residual wake-positive frames still triggered `RECORDING` without speech. The post-playback suppression now also waits for configurable observed quiet before returning to active wake listening, feeds suppressed audio through the wake detector to advance its internal state while discarding detections, and treats wake-positive suppressed scores as not quiet even if PCM RMS is low. `.env.example`, README, DEPLOYMENT, and MANUAL_TESTING document `POST_PLAYBACK_QUIET_SECONDS`, `POST_PLAYBACK_QUIET_RMS`, and `POST_PLAYBACK_MAX_SUPPRESSION_SECONDS`. Focused tests simulate residual wake-positive chunks after cooldown followed by quiet audio, and `./init.sh` verifies 67 project tests plus smoke paths. Durable evaluator evidence is recorded in `runs/F018-evaluation.md`.

F019 has been implemented through the orchestrator entrypoint and evaluator-approved. The OpenAI TTS path now loads optional `TTS_INSTRUCTIONS` and validated `TTS_SPEED`, passes speed plus optional instructions to `audio.speech.with_streaming_response.create`, documents OpenAI.fm-style vibe mapping through `TTS_INSTRUCTIONS`, and adds focused config, OpenAI request-shape, and documentation tests. Coding evidence is recorded in `runs/F019-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F019` in `runs/F019-evaluation.md`.

F020 has been implemented by manual Coding Agent fallback after the user validated the local Hey Jarvis TFLite wake path. The active wake-word default is now openWakeWord `hey_jarvis` with TFLite, `WAKE_PHRASE=hey jarvis`, configuration-aware preload logs, Hey Jarvis documentation and manual-test flows, focused regression tests, and recovery smoke output that listens for the hey jarvis wake word. Coding evidence is recorded in `runs/F020-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F020` in `runs/F020-evaluation.md`.

F021 has been completed through the orchestrator entrypoint, with Coding Agent implementation and Evaluator Agent approval recorded. The assistant now supports configurable wake acknowledgement settings, `python -m src.main --prepare-acknowledgement` one-time audio generation through the existing OpenAI TTS boundary, startup/diagnostic missing-file guidance, an explicit `ACK_PLAYING` state after confirmed wake detection, acknowledgement microphone-residue draining before the existing recorder starts, fake-backend smoke coverage for `WAIT_WAKE -> ACK_PLAYING -> RECORDING`, and documentation/manual-test updates. Coding evidence is recorded in `runs/F021-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F021` in `runs/F021-evaluation.md`.

F022 has been implemented by manual Coding Agent fallback after the orchestrator-first run hit the known Codex provider behavior of hanging in `subprocess.communicate()` while waiting for the Coding Agent child process. The code now includes a structured local tool routing foundation before network-backed realtime providers: route/result schemas, deterministic router rules, realtime-sensitive refusal behavior, local time and safe calculator tools, not-configured results for planned weather/FX/stock tools, `ENABLE_TOOLS`, `TOOL_ROUTER_DEBUG`, state-machine post-transcription routing, and `python -m src.main --text ...` for dependency-free inspection. Focused tests and `./init.sh` pass, and durable evidence is recorded in `runs/F022-manual-coding.md` and `runs/F022-evaluation.md`.

Network-backed structured tools have been planned as four follow-up features. F023 adds the shared provider configuration, HTTP JSON boundary, diagnostics, and mocked failure handling required by all remote tools. F024 adds Open-Meteo weather using geocoding plus forecast data. F025 adds Frankfurter FX reference-rate conversion. F026 adds Finnhub stock quotes behind a user-provided API key. This decomposition keeps provider-specific parsing, credentials, freshness semantics, and caveats independently implementable and evaluatable.

F023 has been completed through the orchestrator entrypoint after approving the Codex provider runtime permission gap, with Coding Agent implementation and Evaluator Agent approval recorded. The code now includes shared provider configuration fields, optional Finnhub credential loading without secret disclosure, provider diagnostics/text-debug surfacing, a standard-library JSON GET boundary with structured recoverable provider errors, provider-aware planned-tool `not_configured` results, offline mocked tests, and documentation for provider settings plus no-live-network automated verification. Coding evidence is recorded in `runs/F023-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F023` in `runs/F023-evaluation.md`.

F024 has been completed through the orchestrator entrypoint after approving the Codex provider runtime permission gap, with Coding Agent implementation and Evaluator Agent approval recorded. The structured weather route now extracts current/today/tomorrow intent and practical locations, falls back to `DEFAULT_LOCATION` when omitted, resolves places through Open-Meteo geocoding, fetches current and daily Open-Meteo forecast fields, returns source/freshness/temperature/apparent-temperature/weather-code/precipitation context in `ToolResult` data, and maps no-match, missing-field, HTTP, timeout, network, and malformed-data failures to structured tool errors without chat speculation. Focused mocked tests cover weather routing, text debug, success and failure paths, default location behavior, and non-Open-Meteo provider fallback. Coding evidence is recorded in `runs/F024-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F024` in `runs/F024-evaluation.md`.

F025 has been completed through the orchestrator entrypoint after approving the Codex provider runtime permission gap, with Coding Agent implementation and Evaluator Agent approval recorded. The structured FX route now extracts amount/base/quote from English and Chinese aliases for USD, SGD, CNY, EUR, JPY, HKD, GBP, and AUD, applies documented defaults for omitted currencies, calls Frankfurter's v2 single-pair rate endpoint through the shared JSON HTTP boundary, calculates converted amounts locally, and returns short reference-rate answers with rate date, source, freshness, and bank/trade-quote caveats. Unsupported currencies, same-currency requests, missing rate fields, provider HTTP failures, and malformed provider data map to structured FX errors without chat fallback. Focused mocked tests and CLI text-debug checks pass, coding evidence is recorded in `runs/F025-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F025` in `runs/F025-evaluation.md`.

F026 has been completed through the orchestrator entrypoint after approving the Codex provider runtime permission gap, with Coding Agent implementation and Evaluator Agent approval recorded. The structured stock route now extracts uppercase ticker symbols and conservative company aliases such as Apple/AAPL while preserving ambiguous ordinary phrases like `苹果怎么样` as non-stock routes. The Finnhub provider uses `FINNHUB_API_KEY` only as the request token, returns current price, change, percent change, high, low, open, previous close, timestamp, source, freshness, and market-data caveats, and maps missing keys, unknown symbols, zero or missing current prices, provider failures, and malformed data to structured tool errors without chat speculation. After an initial evaluator requirement-gap failure, the durable normalized SPEC entry for F026 was restored with goal, scope, flows, constraints, assumptions, capabilities, implementation paths, verification surface, and decomposition rationale. Focused mocked tests, documentation tests, CLI text-debug checks, full project tests, and `./init.sh` pass, coding evidence is recorded in `runs/F026-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F026` in `runs/F026-evaluation.md`.

F027 has been completed through the orchestrator entrypoint after approving the Codex provider runtime permission gap, with Coding Agent implementation and Evaluator Agent approval recorded. The code now includes a default-enabled `TOOL_ANSWER_NATURALIZATION` setting, a dedicated OpenAI naturalization boundary for successful provider-backed weather, FX, and stock `ToolResult` answers, raw-answer fallback for disabled naturalization, failures, realtime refusals, local tools, empty LLM output, and recoverable OpenAI errors, text-debug `raw_answer` and `naturalization_status` output without OpenAI calls, and focused tests for request shape, no chat-history pollution, no secret leakage, fallback behavior, and documentation coverage. Coding evidence is recorded in `runs/F027-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F027` in `runs/F027-evaluation.md`.

F028 has been completed through the orchestrator entrypoint with Coding Agent implementation and Evaluator Agent approval recorded. The user-reported real voice weather request returned `weather provider error: no_location_match` even though the weather provider itself can fetch data. The observed input/output audio files were overwritten by required recovery verification before they could be inspected, so the implementation addresses the likely root cause from durable logs and parser behavior: relative weather locations such as `这里`, `这边`, `本地`, `here`, `nearby`, or `current location` are now treated as omitted locations and fall back to configured `DEFAULT_LOCATION`. Provider-error results now retain safe query, intent, attempted-location, location-source, provider-error, and status-code context where available, and state-machine provider-error logs include route params plus result data without requiring `TOOL_ROUTER_DEBUG`. Focused tests, final `./init.sh` recovery verification, coding evidence in `.agent-harness/runs/F028-manual-coding.md`, and evaluator approval as `EVAL_PASS: F028` in `.agent-harness/runs/F028-evaluation.md` are recorded.

F029 has been planned after review of the user-observed false-wake interaction: wake acknowledgement can currently lead directly into recording, transcription, AI response generation, and TTS playback even when the user does not intend to speak. The planned work adds a post-wake `ARMED` intent-confirmation state plus local minimum-speech, invalid-transcript, and cancel-phrase gates so false or accidental wakes quietly return to `WAIT_WAKE` before any AI response cycle begins.

F029 has been completed through the orchestrator entrypoint after approving the Codex provider runtime permission gap, with Coding Agent implementation and Evaluator Agent approval recorded. The assistant now enters `ARMED` after wake acknowledgement/drain, waits for local speech before recording, preserves the first speech chunk for the recorder, cancels no-speech wakes before recording or OpenAI calls, cancels silent/too-short recordings before transcription, and cancels empty/filler/configured cancel transcripts before chat/tool routing, answer TTS, playback, or chat-history mutation. Configuration, README, deployment, manual testing, fake-backend smoke behavior, and focused tests now cover the ARMED timeout, RMS threshold, minimum speech/transcript gates, and English/Chinese cancel phrases. Coding evidence is recorded in `.agent-harness/runs/F029-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F029` in `.agent-harness/runs/F029-evaluation.md`.

F030 has been planned after manual F029 acceptance testing found that saying `没事` in a noisy environment could still lead to an AI reply. The observed real-world failure was: ARMED correctly detected speech, recording continued to `MAX_RECORD_SECONDS` because construction/background noise prevented silence stop, transcription returned text that did not exactly match the configured cancel phrase, and the state machine proceeded to chat/TTS. The planned fix keeps F029's local cancellation model but makes transcript-level cancel intent matching robust to short trailing STT noise while guarding against legitimate requests that merely begin with a cancel word.

F030 has been completed through the orchestrator entrypoint after approving the Codex provider runtime permission gap, with Coding Agent implementation and Evaluator Agent approval recorded. After an initial evaluator failure found that the SPEC core-flow transcript `没事 后面有声音` still reached chat, the retry broadened the deterministic safe noisy suffix set and added a focused regression fixture. Transcript-level cancellation now accepts exact configured cancel phrases and conservative short noisy suffix variants such as `没事了`, `没事不用了`, `没事 谢谢`, `没事 后面有声音`, `取消吧`, `算了算了`, `stop please`, and `cancel that` before chat/tool routing, answer TTS, playback, or chat-history mutation. Command-like continuations such as `没事的话帮我查天气`, `取消我明天的闹钟`, and `cancel my alarm tomorrow` are not locally cancelled. Cancellation logs include normalized transcript context plus `match_mode`; direct evaluator-style probing, focused state-machine/documentation tests, full project tests, and final `./init.sh` pass. Coding evidence is recorded in `.agent-harness/runs/F030-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F030` in `.agent-harness/runs/F030-evaluation.md`.

F031 has been planned after manual F030 acceptance testing found a new loop: the transcript `算了算了` is correctly classified as local cancellation, but the assistant immediately returns to active `WAIT_WAKE`, accepts residual wake-positive chunks or wake-detector state, replays the acknowledgement `在呢`, times out in `ARMED`, and can repeat the wake/acknowledgement loop without a fresh user wake. The planned fix keeps F030's cancel matching intact and adds post-cancellation wake suppression plus observed quiet before the assistant becomes wake-ready again.

F031 has been completed through the orchestrator entrypoint after approving the Codex provider runtime permission gap, with Coding Agent implementation and Evaluator Agent approval recorded. Local cancellation now enters the existing wake-suppression model before becoming wake-ready: transcript cancellations such as `算了算了`, ARMED no-speech timeouts, silent/short recordings, empty transcripts, and filler transcripts suppress wake detection, discard residual chunks, wait for observed quiet, and log cancellation reason plus maximum suppressed wake score. Focused fake-audio tests cover the reported acknowledgement/cancel loop, ARMED no-speech residual wake suppression, and later intentional wake after quiet without live microphone, OpenAI, speaker, or network access. Coding evidence is recorded in `.agent-harness/runs/F031-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F031` in `.agent-harness/runs/F031-evaluation.md`.

F032 has been planned after manual F030/F031 acceptance testing found that spoken cancellation still reaches OpenAI for common Chinese variants. Exact `不用了` is configured as a cancel phrase, but real speech can transcribe to nearby forms such as `不用啦`, `不用不用了`, `不要了`, `没事儿`, or `没事没事儿`; those were outside F030's conservative suffix set. The planned fix expands deterministic local transcript cancellation for short colloquial Chinese cancel variants, keeps command-like continuations protected, and adds safe diagnostic logging for short non-cancel transcripts so future misses reveal the normalized STT text.

F032 has been completed through the orchestrator entrypoint after approving the Codex provider runtime permission gap, with Coding Agent implementation and Evaluator Agent approval recorded. The transcript cancellation matcher now handles common short Chinese spoken cancel variants such as `不用啦`, `不用不用`, `不用不用了`, `不用了谢谢`, `不要了`, `没事儿`, `没事没事儿`, and `没事儿没事儿` without chat/tool routing, answer TTS, playback, or chat-history mutation. Command-like continuations such as `不用了帮我查天气`, `没事的话帮我查天气`, `取消我明天的闹钟`, and `不要取消我明天的闹钟` remain non-cancel requests, and short non-cancel transcripts now log normalized/compact transcript context with `match_decision=not_cancelled`. Focused tests and final recovery verification pass. Coding evidence is recorded in `.agent-harness/runs/F032-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F032` in `.agent-harness/runs/F032-evaluation.md`.

F033 has been planned after the user reported that normal 4-5 second utterances often record until the 20 second maximum instead of stopping after 1.5 seconds of silence. Code review found the likely root cause: recorder silence detection still uses a hard-coded RMS 500 threshold, while ARMED speech detection uses RMS 750, so steady background noise can be too quiet to count as speech but still too loud to count as recorder silence. The planned fix keeps the existing local RMS model but adds a configurable recording silence threshold plus window-tolerant end-of-speech detection so low or moderate background noise does not reset the silence timer indefinitely.

F033 has been completed through the orchestrator entrypoint after approving the Codex provider runtime permission gap, with Coding Agent implementation and Evaluator Agent approval recorded. The recorder now uses configurable `RECORDING_SILENCE_RMS` with a default of 750, the state machine passes that setting only into question recording, and recorder end-of-speech detection uses a recent-window rule that tolerates steady below-threshold background plus occasional moderate noisy chunks while speech-like chunks still extend recording. Focused config, recorder, state-machine wiring, documentation tests, synthetic PCM fixtures, final recovery verification, and evaluator approval pass. Coding evidence is recorded in `.agent-harness/runs/F033-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F033` in `.agent-harness/runs/F033-evaluation.md`.

F034 has been planned after real voice testing showed that `现在几点了` can transcribe as traditional Chinese `現在幾點了`; the existing deterministic time router did not match that variant, so the request fell through to general OpenAI chat instead of the local time tool. A follow-up local-tool audit found that digit-based calculator requests such as `100減20是多少` also fall through because the safe calculator maps simplified `减` but not traditional `減`, while provider-backed weather, FX, and stock already cover common traditional markers such as `天氣`, `匯率`, `人民幣`, `蘋果`, and `股價`. The planned fast-work-sized fix adds narrow traditional Chinese local-tool markers/operators, text-debug and answer-path regression coverage, and final recovery verification without changing wake, ARMED, recording, transcription, provider-backed tools, or adding broad Chinese script conversion.

F034 has been completed by manual fast-work fallback because the installed hidden-layout harness does not currently provide the documented `work-fast` Makefile target. The router now recognizes traditional Chinese time requests such as `現在幾點了`, `幾點了`, and `現在時間`, and digit-based calculator requests using `減`, such as `100減20是多少`, while preserving the existing deterministic local time and safe calculator behavior. Focused router/text-debug/answer-path tests pass, text debug confirms the affected inputs now route locally, final `./init.sh` recovery verification passes, coding evidence is recorded in `.agent-harness/runs/F034-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F034` in `.agent-harness/runs/F034-evaluation.md`.

F035 has been completed through evaluator-gated `work-fast` after the hidden-layout harness repair restored the target. ARMED now confirms speech through an adaptive recent voiced window, rejects overflowed or clipped chunks, preserves pre-roll audio when recording starts, logs structured `armed_trigger` and `armed_summary` diagnostics with RMS/peak/overflow/threshold/noise-floor/pre-roll context, and keeps local short/empty/filler/acknowledgement-only cancellation before AI routing. Focused config/state-machine/documentation tests, full project tests, fake-backend smoke, final recovery verification, fast coding evidence, and cold-start evaluator approval pass. Coding evidence is recorded in `.agent-harness/runs/20260709T085604Z-F035-fast-coding-retry.md`, and evaluator approval is recorded as `EVAL_PASS: F035` in `.agent-harness/runs/20260709T090453Z-F035-evaluation-pass.md`.

F036 has been planned from the user-reported post-F035 real-test failures. It adds an explicit ARMED baseline gate so a cold `noise_floor=0.0` cannot immediately satisfy the voiced window, optionally requires the latest chunk to remain voiced, and replaces blind acknowledgement draining with a conservative bounded guard that can preserve a small late speech tail as pre-roll. The feature explicitly excludes VAD, new dependencies, and recorder endpointing changes.

F036 has been completed through interactive manual coding fallback and separate cold-start evaluator approval. ARMED now requires configurable baseline time plus valid chunks before triggering, can require the latest chunk to remain voiced, preserves baseline and guard-tail audio in pre-roll without letting initial guard chunks force a trigger, and logs baseline readiness/chunks/seconds with threshold context. The acknowledgement path now uses a bounded quiet-aware guard by default, retains the legacy fixed drain when disabled, and logs discarded/preserved counts plus quiet/RMS/peak metrics. Focused tests and final `./init.sh` pass with 170 project tests; coding evidence is in `.agent-harness/runs/F036-manual-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F036` in `.agent-harness/runs/F036-evaluation.md`.

F038 has been planned as a PR1 follow-up from real A/B testing and captured logs. ACK-disabled speech records correctly, but guarded ACK-enabled runs can finish suppression with `quiet=0.00s`, clipped peaks, and then enter ARMED with `noise_floor=0.0`, producing false recording or partial transcription. F038 separates post-ACK suppression from ARMED, requires a verified quiet/noise boundary, clears clipped/overflow residue from candidate pre-roll, and cancels locally at a bounded timeout. F037 remains reserved for the already stacked optional-VAD PR2.

F038 coding is complete through interactive manual fallback after both normal and approved escalated `make -C .agent-harness work-fast` attempts failed the configured Codex Evaluator Agent runtime check before handoff. The state machine now returns an explicit post-ACK boundary result, requires contiguous safe quiet/noise seeds before guarded ACK flow can enter ARMED, cancels locally at the bounded suppression limit, excludes clipped/overflow residue from pre-roll, preserves ACK-disabled compatibility, and emits post-ACK/baseline diagnostics. Defaults, README, manual guidance, focused tests, full discovery, and recovery verification pass with 172 project tests. Coding evidence is recorded in `.agent-harness/runs/F038-manual-coding.md`; F038 remains in progress pending cold-start evaluator approval.

F038 cold-start evaluation failed in the `implementation_gap` domain: configuration still accepts `ACK_GUARD_MIN_QUIET_SECONDS=0`, for which a loud first post-ACK chunk is incorrectly returned as `quiet_observed=true` with no noise seed and no timeout. This bypasses the mandatory safe post-ACK boundary for a supported configuration. Evaluator evidence is recorded in `.agent-harness/runs/F038-evaluation.md`. Harness improvement assessment: add validation-boundary evaluator probes for configurable safety gates; no harness runtime change is required.

F038 has been completed after a coding retry and separate cold-start evaluator approval. Enabled ACK guard configuration now rejects a non-positive quiet duration, while the runtime boundary independently fails closed if invalid settings bypass configuration. The original explicit boundary metrics, bounded local cancellation, safe noise seeding, protected ARMED gating, clipped/overflow pre-roll exclusion, compatibility paths, defaults, documentation, and diagnostics remain accepted. Focused tests pass with 53 tests, full discovery and final recovery verification pass with 174 project tests, the original evaluator failure remains in `.agent-harness/runs/F038-evaluation.md`, and approval is recorded as `EVAL_PASS: F038` in `.agent-harness/runs/F038-evaluation-pass.md`.

F039 has been planned from real PR1 testing where an ACK-enabled request transcribed only `等于几`. The decisive log showed 18 ARMED chunks, only 12 valid chunks, `max_peak=32768`, and just 240ms/3 chunks retained despite `ARMED_PRE_ROLL_SECONDS=0.80`. Code review confirmed every clipped post-boundary user chunk cleared the whole pre-roll. F039 removes the unused `ACK_GUARD_SECONDS`, keeps the safe boundary, omits overflow individually, and retains clipped user PCM without using it as trigger or noise evidence.

F039 coding is complete through interactive manual fallback after both normal and approved escalated `make -C .agent-harness work-fast` attempts failed the configured Codex Evaluator Agent runtime check before handoff. `ACK_GUARD_SECONDS` is removed from runtime, tracked configuration/docs/tests, logs, and local `.env`; `ACK_GUARD_MAX_BUFFER_SECONDS` is now the sole post-ACK bound. After quiet, overflowed chunks are skipped without erasing earlier pre-roll, while clipped user PCM is retained but remains excluded from voice and noise-floor decisions. Synthetic regressions preserve the utterance prefix across clipped/overflowed chunks. Focused tests and final recovery verification pass with 175 project tests. Coding evidence is recorded in `.agent-harness/runs/F039-manual-coding.md`; F039 remains in progress pending cold-start evaluator approval.

F039 has been completed after separate cold-start evaluator approval. The evaluator confirmed complete removal of the unused ACK guard duration, preservation of the F038 safe quiet boundary and local no-quiet cancellation, clipped post-boundary PCM retention without voice/noise contribution, individual overflow omission without clearing earlier pre-roll, ACK-disabled compatibility, useful diagnostics, untouched untracked user logs, and passing focused plus recovery verification. Approval is recorded as `EVAL_PASS: F039` in `.agent-harness/runs/F039-evaluation-pass.md`.

F037 was reconciled onto the merged PR1 implementation. The optional WebRTC VAD boundary, energy-plus-VAD ARMED gate, wake-model threshold forwarding, and VAD-aware recorder endpointing are retained while F038/F039's mandatory safe post-ACK quiet boundary and clipped-user pre-roll preservation remain authoritative. A fresh cold-start post-merge evaluation passed and is recorded in `.agent-harness/runs/F037-post-pr1-evaluation.md`.

F047 has been completed through evaluator-gated fast work and separate cold-start evaluator approval. Investigation found that the user-observed historical-linguistics question was refused before chat because `现在` matched the router's broad realtime marker. Stable past-versus-present comparisons now remain on the ordinary chat route unless they ask about fresh news, prices, weather, stocks, rates, or scores. The general chat prompt also requires qualified best-effort stable-knowledge answers, language matching, calibrated uncertainty, and no false browsing claims while preserving current/live-data refusal semantics. Focused tests, 219 project tests, text-debug contrasts, dry-run, fake-backend, diagnose, and final recovery verification pass. Coding evidence is recorded in `.agent-harness/runs/20260715T123826Z-F047-fast-coding.md`, and approval is recorded as `EVAL_PASS: F047` in `.agent-harness/runs/20260715T124324Z-F047-evaluation-pass.md`.

## Last Completed Feature

F100 - Unify the Home and Settings desktop shell.

F100 keeps the native and document title at `Hey Jarvis`, aligns the Home
`Hey Jarvis` and Settings `Settings` context labels at one shared header
origin, and places gear/Done in the same trailing control slot. Settings now
uses a left-anchored desktop workspace at regular and fullscreen widths while
retaining a compact, scrollable layout with visible credential actions.
Default, compact, API-key, and fullscreen Debug app views were inspected; the
real-window pass found and corrected a six-pixel compact gutter drift. Full
recovery verification passed with 412 project tests, seventeen Rust tests, and
all smoke paths. Coding evidence is in
`.agent-harness/runs/F100-fast-coding.md`; independent approval is recorded as
`EVAL_PASS: F100` in
`.agent-harness/runs/20260803T074732Z-F100-evaluation-pass.md`.

F099 - Make Settings return lifecycle deterministic.

F099 removed Done's throttled `requestAnimationFrame` gate, moved blocking
sidecar readiness work off the Tauri UI/IPC path, and replaced the assistant
gear's BFCache-prone `history.back()` with an exact data-free navigation intent
that is cancelled and handled by the native Settings helper. Three consecutive
Debug app cycles opened Settings with request tokens 1, 2, and 3 and returned to
the Ready assistant surface. Request-to-native-start measured 18, 12, and 24 ms;
the remaining 1.7–1.8 seconds was the observed sidecar/model readiness interval.
Full recovery verification passed, coding evidence is in
`.agent-harness/runs/F099-fast-coding.md`, and independent approval is recorded
as `EVAL_PASS: F099` in
`.agent-harness/runs/20260803T070255Z-F099-evaluation-pass.md`.

F098 - Reset Settings state on every native entry.

F098 prevents the bundled `Returning to Jarvis` transition from surviving a
new native Settings request. Each tray, menu, or `⌘,` entry now receives a
unique process-local `settings-request` query token, forcing WKWebView to load
a fresh same-origin Settings document while preserving `#settings-return` and
`enter_settings` as the sole intentional sidecar-stop boundary. The rebuilt
Debug app reproduced the old state, then rendered Settings at request IDs 1
and 2 on successive entries. Final recovery passes with 411 project tests,
ten Mac app/Python tests, seventeen Rust tests, and all smoke paths. Coding
evidence is in `.agent-harness/runs/F098-fast-coding.md`; independent approval
is recorded as `EVAL_PASS: F098` in
`.agent-harness/runs/20260803T033621Z-F098-evaluation-pass.md`.

F097 - Polish Settings interaction and compact layout.

F097 makes Done acknowledge immediately with a bundled **Returning to Jarvis**
startup state while the local runtime performs its real cold start; failures
restore Settings and focus instead of leaving an inert button. Buttons use
smaller, lighter, quieter styling, Add/Replace key labels omit ellipses, and
responsive API-key rows keep Delete visible through the supported compact
width. A two-frame committed-paint boundary also closes the intermittent
Settings disconnect race. Final recovery passes with 411 project tests, ten
Mac app/Python tests, seventeen Rust tests, and all smoke paths. Coding evidence
is in `.agent-harness/runs/F097-fast-coding.md`; independent approval is
recorded as `EVAL_PASS: F097` in
`.agent-harness/runs/20260803T031331Z-F097-evaluation-pass.md`.

F096 stabilized the runtime-to-Settings transition.

F096 removes the native pre-navigation sidecar stop that could blank WKWebView
before it committed the bundled Settings document. The loaded Settings page
now remains the single intentional shutdown owner through `enter_settings`, so
the gear, tray item, and `⌘,` share one stable non-listening transition without
a timing delay. The rebuilt Debug app remained rendered after the former
failure window, **Done** returned to wake-ready, and the shortcut reopened the
same persistent Settings page. Final recovery passes with 411 project tests,
ten Mac app/Python tests, seventeen Rust tests, and all smoke paths. Coding
evidence is in `.agent-harness/runs/F096-fast-coding.md`; independent approval
is recorded as `EVAL_PASS: F096` in
`.agent-harness/runs/20260803T023742Z-F096-evaluation-pass.md`.

F095 created the secondary Settings and diagnostics surface.

F095 replaces the bootstrap engineering/setup card with a dedicated modern
Settings presentation organized as General, API Keys, Microphone, Privacy &
Diagnostics, and About. The conversation-window gear, tray **Settings…** item,
and standard `⌘,` shortcut share one native helper and route. Entering Settings
stops the sidecar before the visible non-listening state; **Done** explicitly
restarts the local runtime and returns to the minimal conversation surface.
Keychain add/replace/delete, durable microphone permission recovery,
non-starting readiness checks, privacy-bounded support export, confirmed
diagnostics clearing, keyboard focus, reduced motion, media cleanup, and crash
recovery remain accepted without exposing credentials, raw audio, transcripts,
provider bodies, protocol/session fields, or internal endpoints.

The final recovery run passed 411 project tests, ten Mac app/Python tests,
seventeen Rust tests, and all smoke paths. Coding evidence is in
`.agent-harness/runs/F095-fast-coding.md`; independent approval is recorded as
`EVAL_PASS: F095` in
`.agent-harness/runs/20260802T143136Z-F095-evaluation-pass.md`.

## Recent Completed Feature History

F069 - Attribute Realtime Web Audio cold-start latency.

F069 has been completed through evaluator-gated fast work, one newly authorized
automatic RT004 version 2 two-session live-host run, and separate cold-start
evaluator approval. `new AudioContext()` accounted for effectively the entire
input-level analysis delay: `4490 ms` in session A and `2831 ms` in session B.
The `1660 ms` improvement supports a partial same-page warm-up effect, but the
recurring `2831 ms` weakens a one-time cold-start explanation. Both distinct
sessions connected, cleaned up, and restored final wake ownership. This is
diagnostic evidence, not an SLO or stable percentile, and no runtime operation
was moved, deferred, prewarmed, reused, disabled, or retuned. Final recovery
passes with 338 project tests. Coding evidence is in
`.agent-harness/runs/F069-fast-coding.md`, live evidence is in
`.agent-harness/runs/F069-live-rt004.md`, and approval is recorded as
`EVAL_PASS: F069` in
`.agent-harness/runs/20260724T083039Z-F069-evaluation-pass.md`.

F059 - Add a spec-driven assisted Realtime barge-in eval.

F059 has been completed through evaluator-gated fast work, three authorized live-near-end attempts, a coding retry, and separate cold-start evaluator approval. The project now has a versioned RT003 contract, deterministic offline oracle, guided live runner, bounded PASS/FAIL evidence, privacy allowlists, early-close detection, cleanup-safe failure persistence, and 282 passing project tests. The independent evaluator accepted the evaluation capability while preserving the honest product verdict: under the accepted `output_volume=0.1` and `server_vad_threshold=0.8` profile, all three natural human interruption attempts—including a quiet-room retest—produced no `host_speech_started` and ended by idle timeout, even though prior saved fixtures crossed the threshold. Coding evidence is in `.agent-harness/runs/F059-fast-coding.md` and `.agent-harness/runs/F059-coding-retry.md`, live failure evidence is in `.agent-harness/runs/F059-rt003-live-failures.md`, and approval is recorded as `EVAL_PASS: F059` in `.agent-harness/runs/20260723T000000Z-F059-evaluation-pass.md`.

F058 - Log pipeline latency and enforce Chinese replies.

F058 has been completed through evaluator-gated fast work and separate cold-start evaluator approval. Successful pipeline loops now emit ordered `pipeline_timing` stage records and a bounded `response_timing` summary with recording duration, transcription, answer or local-tool routing, TTS, ready-to-play, playback, post-recording total, and route. General chat and structured-tool naturalization receive a current-turn language system instruction: Chinese input requires concise Simplified Chinese, explicit English terminology/translation/pronunciation requests may include requested English content with Chinese explanation, and English input remains English regardless of prior history. Focused tests pass with 66 tests, full supported-runtime discovery and final recovery pass with 233 project tests, coding evidence is recorded in `.agent-harness/runs/F058-fast-coding.md`, and evaluator approval is recorded as `EVAL_PASS: F058` in `.agent-harness/runs/20260717T000000Z-F058-evaluation-pass.md`.

F057 - Accept and document the Realtime WebRTC MVP.

F057 has been completed through evaluator-gated fast work, a corrective retry after the first evaluator rejected incomplete final-cycle coverage, separate cold-start evaluator approval, and five consecutive no-headphones real-device cycles. Every accepted cycle started from a saved real wake without another Arm click, completed two response-bound turns, invoked the calculator and its spoken continuation, cancelled a long answer through deliberate barge-in in 15-118 ms, completed the barge-in continuation, ended through the exact saved end phrase, recorded exactly five intended speech starts and zero host errors, and restored fresh wake ownership. The accepted quiet profile uses direct browser output gain `0.1` and documented server-VAD threshold `0.8` with browser echo cancellation, noise suppression, automatic gain control, and 48 kHz mono capture. Final recovery passes with 266 project tests. Coding evidence is in `.agent-harness/runs/F057-fast-coding.md` and `.agent-harness/runs/F057-coding-retry.md`, live evidence is in `.agent-harness/runs/F057-real-device-acceptance.md`, the preserved rejection is in `.agent-harness/runs/20260717T090000Z-F057-evaluation-fail.md`, and approval is recorded as `EVAL_PASS: F057` in `.agent-harness/runs/20260717T092851Z-F057-evaluation-pass.md`.

F056 - Bridge the safe calculator into Realtime.

F056 has been completed through evaluator-gated fast work, separate cold-start evaluator approval, and real-device Chrome-hosted acceptance. The Realtime session advertises exactly one strict calculator function; Python bounds, correlates, and de-duplicates calls, executes the existing `safe_calculator`, and returns one correlated function output for a same-conversation spoken continuation. Malformed, unsafe, unknown, duplicate, and stale calls remain bounded and do not execute twice or expose other tools. A real Chinese 100-times-1000 request produced one successful execution, the answer 100000, and clean wake-microphone recovery. Final recovery passes with 262 project tests. Coding evidence is in `.agent-harness/runs/F056-fast-coding.md`, live evidence is in `.agent-harness/runs/F056-real-device-acceptance.md`, and approval is recorded as `EVAL_PASS: F056` in `.agent-harness/runs/20260717T000000Z-F056-evaluation-pass.md`.

F055 - End Realtime sessions with deterministic phrases.

F055 has been completed through evaluator-gated fast work, separate cold-start evaluator approval, and real-device Chrome-hosted acceptance. Completed input transcription is treated only as asynchronous item-correlated rough-guide metadata; exact short bilingual end phrases are normalized across Unicode form, case, outer punctuation, and ASR whitespace, while substrings, partial/missing/oversized events, ordinary cancellation language, duplicates, failures, and stale events remain safe. A host-instance lease prevents stale Chrome app windows from consuming commands. A real spoken English end phrase produced `host_end_phrase_matched`, stopped WebRTC media through the shared close path, and returned to `wake_owned` with the microphone open and no transcript text in the report. Final recovery passes with 259 project tests plus pipeline and Realtime fake smoke paths. Coding evidence is in `.agent-harness/runs/F055-fast-coding.md`, real-device evidence is in `.agent-harness/runs/F055-real-device-acceptance.md`, and approval is recorded as `EVAL_PASS: F055` in `.agent-harness/runs/20260717T075325Z-F055-evaluation-pass.md`.

F054 - Run wake-triggered continuous WebRTC voice sessions.

F054 has been completed through evaluator-gated fast work, separate cold-start evaluator approval, and a repeatable real-device acceptance run. The opt-in Realtime runtime now performs confirmed local wake, exclusive pre-capture acknowledgement handoff, connected/session-created readiness, continuous follow-up turns, server-VAD interruption, bounded idle/maximum/error/explicit/Ctrl+C closure, browser-media teardown, and fresh wake recovery without changing the pipeline default. Private local voice fixtures plus event-driven replay remain Git-ignored and transcript-free. A clean no-headphones run completed two turns in one session, cancelled a long answer 32 ms after replay speech detection, and returned microphone ownership. Final recovery passes with 255 project tests plus pipeline and Realtime fake smoke paths. Coding evidence is in `.agent-harness/runs/F054-fast-coding.md`, real-device evidence is in `.agent-harness/runs/F054-real-device-acceptance.md`, and approval is recorded as `EVAL_PASS: F054` in `.agent-harness/runs/20260717T050500Z-F054-evaluation-pass.md`.

F052 - Validate hands-free WebRTC hosting and microphone handoff.

F052 has been completed through evaluator-gated fast work and separate cold-start evaluator approval. The selected Chrome app-mode host now requires one Arm gesture per launch, then accepts programmatic Python wake commands without another click. Its coordinator enforces exclusive Python-wake/browser-WebRTC microphone ownership, uses server-minted ephemeral client secrets, reports bounded sanitized ordering and actual browser capture settings, and fails closed without a WebSocket fallback. Offline handoff tests pass. Five real start/stop cycles returned ownership cleanly, and a final launch without an autoplay-policy bypass passed a built-in-speaker/microphone interruption trial: real user speech cancelled the old response 154 ms after speech detection and the Python wake stream reopened after browser teardown. Coding evidence is in `.agent-harness/runs/F052-fast-coding.md`, real-device evidence is in `.agent-harness/runs/F052-real-device-acceptance.md`, and approval is recorded as `EVAL_PASS: F052` in `.agent-harness/runs/20260717T033400Z-F052-evaluation-pass.md`.

F051 - Validate speakerphone Realtime WebRTC full duplex.

F051 has been accepted by a separate cold-start Evaluator and subsequently passed a deliberate real-device speakerphone interruption trial. Chrome reported active echo cancellation, noise suppression, automatic gain control, 48 kHz mono capture, a connected peer, and a remote audio track with no Realtime errors. During the fixed long answer, user speech detection was followed by output completion and `response.done status=cancelled` in about 27-28 ms, then the user turn received a response. The report's `speechDuringAssistant=0` is a known probe-observability limitation because WebRTC playout used the remote media track without continuous output-audio delta events on the data channel. A second rapid cancellation cannot be classified from sanitized events alone, so universal absence of speaker self-echo remains unclaimed. Coding evidence is in `.agent-harness/runs/F051-fast-coding.md`, approval is in `.agent-harness/runs/20260716T151618Z-F051-evaluation-pass.md`, and post-evaluation real-device evidence is in `.agent-harness/runs/F051-real-device-acceptance.md`.

F040 coding is complete through interactive fast-work fallback after `make -C .agent-harness work-fast` failed its configured Codex Evaluator Agent runtime check before handoff. The implementation adds observable non-blocking acknowledgement playback on macOS, drains/discards microphone chunks while `afplay` runs with safe metrics, and preserves synchronous answer playback plus fake/legacy fallback behavior. Focused tests and final recovery verification pass with 196 project tests. Coding evidence is recorded in `.agent-harness/runs/F040-fast-coding.md`; F040 remains in progress pending separate evaluator approval.

F040's first cold-start evaluation failed because drain failures lacked required metrics/failure state and no state-machine regression proved cleanup on microphone-read or playback-wait failure. The retry now logs bounded success/failure metrics with explicit failure stages, joins the playback handle on drain failure, and covers read/wait cleanup paths. Focused tests pass with 46 tests and final recovery verification passes with 198 project tests. Retry evidence is recorded in `.agent-harness/runs/F040-coding-retry.md`; F040 remains in progress pending evaluator approval.

F040 has been completed after separate cold-start evaluator approval. ACK playback on the real macOS path now uses an observable `afplay` handle and continuously consumes/discards microphone chunks through playback completion, including the overlap chunk, with bounded success/failure diagnostics and cleanup regressions. Synchronous answer playback and fake/legacy compatibility remain intact; the conservative post-ACK quiet boundary is intentionally unchanged for F041. Approval is recorded as `EVAL_PASS: F040` in `.agent-harness/runs/F040-evaluation-pass.md`.

F041 coding is complete through interactive fast-work fallback after `make -C .agent-harness work-fast` failed its configured Codex Evaluator Agent runtime check before handoff. Successful F040 drains now bypass mandatory quiet suppression for subsequent current audio, hand it into protected ARMED pre-roll, and expose separate quiet/synchronized/boundary-ready diagnostics; legacy/fake players retain the conservative fallback. Immediate-prefix, tail-only cancellation, optional-VAD, and five-loop fake regressions pass, and final recovery verification passes with 202 project tests. Coding evidence is recorded in `.agent-harness/runs/F041-fast-coding.md`; F041 remains in progress pending separate evaluator approval.

F041's first cold-start evaluation failed because a completed ACK drain was trusted as synchronized even when its metrics recorded overflow. The retry now marks any overflowed drain `synchronized=false`, logs that decision, and proves the full conservative quiet-boundary fallback path. Focused tests and final recovery verification pass with 203 project tests. Retry evidence is recorded in `.agent-harness/runs/F041-coding-retry.md`; F041 remains in progress pending evaluator approval.

F041 has been completed after separate cold-start evaluator approval. Only completed zero-overflow ACK drains now enable synchronized live handoff; overflowed drains fall back to the bounded quiet boundary. Immediate current speech enters protected ARMED pre-roll without mandatory quiet suppression, while overlap, overflow, clipping, tail-only audio, silence, baseline, rolling voice, latest-chunk, and optional VAD protections remain enforced. Approval is recorded as `EVAL_PASS: F041` in `.agent-harness/runs/F041-evaluation-pass.md`.

F043 coding is complete through interactive fast-work fallback after `make -C .agent-harness work-fast` failed its configured Codex Evaluator Agent runtime check before handoff. Real logs proved F041 discarded questions that began during the roughly 18-chunk acknowledgement playback drain. The implementation now retains a bounded safe playback tail, quarantines the completion-overlap chunk, extracts low-energy noise seeds, requires a useful noise floor before synchronized ARMED triggering, and removes only an exact leading configured acknowledgement from STT when useful question text remains. Playback-time audio cannot trigger by itself; the supported no-AEC boundary requires user speech to continue after playback. Focused state-machine tests, full discovery with 209 tests, dry-run, fake-backend, and documentation checks pass. Coding evidence is recorded in `.agent-harness/runs/F043-fast-coding.md`; F043 remains in progress pending separate cold-start evaluator approval and real-device retesting.

F043 real-device retesting confirmed playback-overlap prefix preservation, but OpenAI STT rendered the configured `嗯` acknowledgement residue as ASCII `n` in inputs such as `n一加一等于几`. The coding retry adds a configuration-specific narrow cleanup for a single leading `n` or `N` immediately followed by CJK text when the configured acknowledgement is `嗯`; it does not alter ordinary English text. One run still transcribed `n加一等于几`, showing a separately lost spoken `一` in that trial rather than only an ACK artifact.

F045 has been completed through evaluator-gated fast work and separate cold-start evaluator approval. `progress.md` now limits Known Issues to the unresolved Recording VAD reliability defect and WebRTC VAD dependency/diagnostic false-positive gap. Python support, macOS permission, live-integration verification limits, and untracked real-test logs are separated as operational/verification constraints. Completed-feature, fallback, provider, wake, ACK, and orchestration history was removed from the active issue list while remaining durable in feature summaries, runs, and git history. Coding evidence is recorded in `.agent-harness/runs/F045-fast-coding.md`, and approval is recorded as `EVAL_PASS: F045` in `.agent-harness/runs/20260713T150202Z-F045-evaluation-pass.md`.

F046 has been completed through evaluator-gated fast work and separate cold-start evaluator approval. The optional WebRTC VAD dependency set is now reproducible through `requirements-vad.txt`, and configured diagnostics use the production detector factory plus a real 20ms classification instead of module discovery. Lazy VAD-disabled behavior, focused failure probes, 215 project tests, final recovery verification, system-Python fail-closed diagnostics, and a real Python 3.12/setuptools 80.10.2/WebRTC runtime diagnostic pass are recorded in `.agent-harness/runs/F046-fast-coding.md`, and approval is recorded as `EVAL_PASS: F046` in `.agent-harness/runs/20260713T154700Z-F046-evaluation-pass.md`.

F048 has been completed through evaluator-gated fast work, separate cold-start evaluator approval, and real-device acceptance. Recording VAD endpointing now requires RMS plus VAD to extend speech, lets sustained low RMS advance end silence despite false-high WebRTC ratios, preserves high-energy noise and max-duration safety, and emits a bounded disagreement summary. Focused tests, 221 full project tests, and final recovery verification pass; coding evidence is recorded in `.agent-harness/runs/F048-fast-coding.md`, approval is recorded as `EVAL_PASS: F048` in `.agent-harness/runs/20260715T155043Z-F048-evaluation-pass.md`, and five normal Python 3.12 trials all stopped by silence with no max-duration failures as recorded in `.agent-harness/runs/F048-real-device-acceptance.md`. Default enablement remains a separate product decision.

F049 has been completed through evaluator-gated fast work and separate cold-start evaluator approval. Chinese calculator normalization now consumes `乘以` as one operator, supports one conservative `万/萬` section, and rejects incomplete or malformed expressions instead of routing `100*`. Text debug returns 100000 for `一百乘以一千等于多少` and 1000000 for `一百乘以一萬等於多少`; focused checks, 223 project tests, and final recovery verification pass. Coding evidence is recorded in `.agent-harness/runs/F049-fast-coding.md`, and approval is recorded as `EVAL_PASS: F049` in `.agent-harness/runs/20260715T160231Z-F049-evaluation-pass.md`.

F050 has been completed through evaluator-gated fast work and separate cold-start evaluator approval. Recovery state now reflects F049's approval, README and manual guidance reflect F048's 5/5 real-device endpoint acceptance without implying default enablement, manual testing distinguishes post-RECORDING hangover from unresolved pre-trigger ARMED prefix loss, and the duplicate M012 test ID is removed. Focused documentation assertions guard these boundaries. Coding evidence is recorded in `.agent-harness/runs/F050-fast-coding.md`, and approval is recorded as `EVAL_PASS: F050` in `.agent-harness/runs/20260716T071443Z-F050-evaluation-pass.md`.

## Current Feature

F112 is the next active direction after evaluator-approved F116. It remains a
separate owner-led ACK experiment and does not affect Settings.

F108 is evaluator-approved. The bounded A/B runner,
one-shot same-session Realtime ACK path, privacy oracle, deterministic cleanup,
saved-local-trial recovery, and offline verification are implemented while the
480 ms local acknowledgement remains the production default. After an earlier
authorized `incomplete` response exposed an invalid low audio-token cap, a
second explicitly authorized target-Mac trial completed the fixed Mandarin
short bridge with the active `gpt-realtime-2.1` / `alloy` / `0.5` profile. The
owner heard the intended Chinese cue, judged its length natural, and preferred
Realtime. Realtime first-observable playback was 3,159 ms after wake and input
became ready at 6,628 ms, 3,436 ms slower than the saved local baseline; input
readiness followed playback completion by 284 ms. The evidence therefore
recommends considering Realtime for voice consistency without claiming faster
negotiation, an acoustic-onset SLO, or an automatic production switch.

F109 is evaluator-approved. The normal Realtime backend now uses the accepted
same-session Mandarin acknowledgement on every wake, keeps the classic pipeline
local, and retains `REALTIME_ACKNOWLEDGEMENT_MODE=local` as an environment-level
rollback. Input remains gated through ACK playback completion, and failures
recover silently rather than double-playing a local cue. An authorized run
confirmed the audible ACK and normal answer after correcting a private `.env`
override. It also exposed and fixed an intermittent farewell ordering race by
letting semantic end-tool responses finish naturally instead of sending an
unnecessary cancellation immediately before farewell creation. In the final
authorized retry, the owner heard both the Mandarin ACK and `再见`; sanitized
evidence confirms input enablement only after ACK playback, same-session
answers/tools/follow-up/interruption, `farewell_complete`, and wake recovery 93
ms after media teardown. Independent approval is recorded as `EVAL_PASS: F109`
in `.agent-harness/runs/20260804T084407Z-F109-evaluation-pass.md`.

F103 is evaluator-approved as the completed desktop icon-consistency baseline.

F104 is evaluator-approved as the truthful availability foundation for the
owner-approved Smart Speaker Mode; F105-F106 remain planned. The planning
is grounded in the 2026-08-03 target-Mac experiment: after the old external
`caffeinate` assertion disappeared and the display remained off beyond the
configured one-minute system-sleep deadline, macOS emitted
`system_will_sleep`, the current power callback intentionally stopped the
sidecar, wake only recorded `system_did_wake`, and the still-running native app
could no longer answer `Hey Jarvis`. The plan therefore requires a truthful
voice-availability contract before adding a native idle-sleep assertion and a
separate bounded sleep/wake recovery path.

F093 is pending (`status=todo`) and intentionally deferred behind the
owner-prioritized interaction/settings work. It owns the public engineering narrative
and bounded demo plus privacy-safe feedback from at least three explicitly
trusted trials or clean profiles. It must use the evaluator-approved F092
internal artifact without publishing the unsigned binary or describing it as
signed, notarized, Gatekeeper-ready, or suitable for anonymous download.

Provider-native work has added the case study, a 210-second privacy-safe demo
runbook, structured trusted-trial evidence, an explicit completion record, and
a fail-closed completion verifier. The owner-led F092 run is preserved as one
eligible privacy-safe trial. The current machine-readable decision is `HOLD`:
the demo has not yet been recorded and two additional trusted tester or clean
profile trials remain. No demo or external feedback has been fabricated.
The existing F093 worktree is intentionally retained so the feature can resume
without recreating its narrative, demo, feedback, or verification groundwork.

## Next Feature

Implement and evaluate F118, then F119 and F120. F119 paid generation and live
speaker audition require fresh explicit owner authorization immediately before
execution. The older optional F112 Mandarin ACK-shortening experiment and F093
portfolio demo/trusted-trial work remain deferred behind the owner-prioritized
bilingual product flow. Then Resume F093 by recording the bounded production-app
demo and running two additional trusted Apple Silicon tester or distinct
clean-profile trials. Public binary distribution remains on hold.

For the owner-prioritized interactive F118-F120 sequence, F112 is temporarily
set to P1 so the priority-and-order-only orchestrator selects F118 first. Restore
F112 to P0 after F120 evaluation or if the bilingual sequence is abandoned.

F113 was explicitly selected for interactive work ahead of the older F112 todo
item because the owner reported a repeatable P0 native crash and asked to fix
it first. The installed orchestrator has no feature-selection flag, so this
selection state is recorded as an explicit manual priority fallback; the
required `make -C .agent-harness work-fast` handoff and separate evaluator gate
remain authoritative.

## Recently Completed

F109 - Make Realtime acknowledgement the production default.

F109 promotes the accepted same-session Mandarin ACK while preserving local
rollback, fixes the semantic-farewell cancellation race found in live testing,
and passes owner-heard ACK-to-farewell acceptance plus independent evaluation.

F108 - Compare local and Realtime acknowledgement latency.

F108 adds a one-shot, privacy-safe A/B runner while preserving the local
production default. An explicitly authorized target-Mac retry completed the
fixed Mandarin Realtime short bridge with `gpt-realtime-2.1`, `alloy`, and `0.5`
gain. The owner judged its length natural and preferred Realtime; input-ready
was 3,436 ms slower than the saved local baseline, so the recommendation is to
consider Realtime for voice consistency rather than claim a latency win.
Independent approval is recorded as `EVAL_PASS: F108` in
`.agent-harness/runs/20260804T081419Z-F108-evaluation-pass.md`.

F107 - Speak a Realtime-native farewell before closing.

F107 mutes browser input on an unambiguous end intent, generates exactly one
brief audio-only farewell on the active Realtime session with tools disabled,
and waits for both response and playback completion before the existing bounded
teardown restores wake ownership. Full recovery passed with 426 project tests,
ten Mac frontend/sidecar tests, 25 Rust tests, and Realtime fake smoke. Coding
evidence is in `.agent-harness/runs/F107-fast-coding.md`; independent approval
is recorded as `EVAL_PASS: F107` in
`.agent-harness/runs/20260804T071725Z-F107-evaluation-pass.md`.

F105 - Add the native Smart Speaker idle-sleep policy.

F105 adds the opt-in native idle-system-sleep assertion and retains it from
genuine wake listening through the active conversation. Smart Speaker Mode
also uses the existing Enable gesture to retain a disabled WKWebView microphone
track and prime the existing audio element silently, avoiding unreliable cold
media startup after lock. The owner-led locked trial completed audible ACK,
time answer, semantic end, and wake restoration with 5 ms microphone reuse;
final recovery and independent evaluation passed.

F104 - Publish truthful voice availability across the Mac app.

F104 introduces a single fail-closed voice-availability contract across the
Python coordinator, native supervisor, loopback Home page, and menu bar. A real
Debug run verified Ready before Enable, Wake listening only after the local
microphone lease opened, Resume required after sidecar loss, Not listening in
Settings, and Ready after Done starts a fresh runtime. Full recovery passes
with 423 project tests, ten Mac sidecar tests, and eighteen Rust tests. Coding
evidence is in `.agent-harness/runs/F104-fast-coding.md`; independent approval
is recorded as `EVAL_PASS: F104` in
`.agent-harness/runs/20260803T153701Z-F104-evaluation-pass.md`.

F103 - Strengthen the menu-bar icon at native size.

F103 gives only the dedicated tray template more optical weight: the `J`
stroke is 4.4 units, the orb ring is 2.4, and the three listening bars are 1.8.
The platform moved down slightly to preserve a 1.4-unit vector gap while its
orb remains centered at x=17.5. Visible coverage increased to 29.9% at 18px
and 25.8% at 36px, with transparent corners, black-only template pixels, and
unchanged Show, Settings, and Quit behavior. The full-color App Icon remains
unchanged. Coding evidence is in `.agent-harness/runs/F103-fast-coding.md`;
independent approval is recorded as `EVAL_PASS: F103` in
`.agent-harness/runs/20260803T104134Z-F103-evaluation-pass.md`.

F102 - Correct the selected icon geometry.

F102 reduces the color `J` stroke from 104 to 76 SVG units and the menu-bar
template stroke from 4 to 3.2. The listening orb now sits at the exact visual
midpoint of the short platform, including round-cap and stem stroke width,
while preserving the approved gap, palette, and three listening bars. The full
PNG/ICNS family and transparent 18/36 menu-bar assets were regenerated. Six
focused icon tests, final recovery, and the saved multi-size contact sheet pass.
Coding evidence is in `.agent-harness/runs/F102-fast-coding.md`; independent
approval is recorded as `EVAL_PASS: F102` in
`.agent-harness/runs/20260803T094121Z-F102-evaluation-pass.md`.

F101 - Replace the Mac app and menu-bar icon system.

F101 replaced the face-like icon with an editable SVG master containing the
approved mint `J`, original short upper platform, separated listening orb, and
three warm-white bars. Its reproducible generator emits exact 16-through-1024
iconset members, Tauri PNGs, and ICNS. The native tray embeds a dedicated
36-pixel black/transparent image and enables macOS template rendering instead
of shrinking the opaque app icon. Pixel contracts verify transparent corners,
bounded glyph coverage, and black-only RGB on every antialiased template pixel;
the saved contact sheet covers app sizes plus light/dark menu-bar composites.
Final recovery passed with 417 project tests, ten Mac frontend/sidecar tests,
seventeen Rust tests, and all smoke paths. Coding evidence is in
`.agent-harness/runs/F101-fast-coding.md`; independent approval is recorded as
`EVAL_PASS: F101` in
`.agent-harness/runs/20260803T092422Z-F101-evaluation-pass.md`.

F094 - Create the minimal voice interaction surface.

F094 replaced the production WKWebView engineering dashboard with a focused
560x600 Hey Jarvis conversation surface. A CSS-only orb and concise copy map
ready, wake-ready, connecting, listening, thinking, speaking, stopping, and
error states without exposing engineering controls. Independent approval is
recorded as `EVAL_PASS: F094` in
`.agent-harness/runs/20260802T133342Z-F094-evaluation-pass.md`.

F091 - Harden app diagnostics and sidecar recovery.

F091 added bounded rotating lifecycle diagnostics across Rust, WebView, and
the frozen Python runtime; redacted support export and clear UI; deterministic
media release; sleep/wake cleanup; and bounded crash recovery. Its authorized
Apple Silicon trials and independent evaluator approval are recorded in
`.agent-harness/runs/20260802T063008Z-F091-fast-coding.md` and
`.agent-harness/runs/20260802T064406Z-F091-evaluation-pass.md`.

F077 - Measure acknowledgement playback lifecycle.

F077 passed provider-native fast coding, two five-trial target-Mac playback
samples, final recovery verification, and separate cold-start evaluator
approval. The benchmark shows `afplay` process creation at only 1–5 ms; the
approximately 0.88-second median difference occurs while `afplay` remains
alive, although acoustic onset and the split among decode, output setup,
buffering, drain, and shutdown remain unmeasured. Approval is recorded as
`EVAL_PASS: F077` in
`.agent-harness/runs/20260728T120000Z-F077-evaluation-pass.md`.

F074 passed live and evaluator acceptance: speech after “在呢” receives normal
answers, no speech is submitted before input readiness, and cleanup restores
wake ownership.

## Known Issues

### Deferred Recording VAD limitations

- Impact: F048 resolved the normal post-speech `max_duration` failure and passed 5/5 real trials. Two lower-priority behaviors remain. Before RECORDING starts, a deliberately paused short question can lose its prefix if ARMED triggers only on the suffix after the prefix has left pre-roll. Separately, clap-like transients can produce false-positive WebRTC voice evidence and unnecessarily enter RECORDING/transcription.
- Current safe configuration: The default remains `RECORDING_VAD_ENABLED=0`; the tested Python 3.12/WebRTC environment may enable it for normal continuous questions. ARMED sustained-window and pre-roll safeguards remain in effect.
- Evidence: `.agent-harness/runs/F037-real-vad-tuning-results.md` and `.agent-harness/runs/F048-real-device-acceptance.md`.
- Follow-up: Treat paused-prefix preservation and clap/transient rejection as separate lower-priority features if their real impact becomes material. Default enablement is a separate product decision.

### Realtime natural human barge-in repeatability

- Impact: Three F059 live-near-end attempts emitted no `host_speech_started`, while F060 showed strong speech capture and server-VAD cancellation during a controlled comparison. F061 passed the synchronized RT003 run. A later user-observed built-in-speaker regression produced playback-correlated false speech and repeated cancellation until F073 added far-field preprocessing and stronger echo-cancellation negotiation. This sequence still does not establish statistical reliability across speakers, rooms, or devices.
- Current safe interpretation: Preserve the historical failures and use the F073 target-Mac result as evidence for `far_field` plus local output volume 0.3 on that device. The checked-in volume default remains 0.1 until broader evidence supports changing it; server-VAD threshold remains 0.8.
- Evidence: `.agent-harness/runs/F059-rt003-live-failures.md`, `.agent-harness/runs/F060-live-diagnostic-attempt.md`, `.agent-harness/runs/F061-live-attempts.md`, `.agent-harness/runs/20260727T064500Z-F073-live-acceptance.md`, and `.agent-harness/runs/20260727T070000Z-F073-evaluation-pass.md`.
- Follow-up: Repeat synchronized RT003 only when a user-observed regression, environment change, or broader reliability goal makes new live evidence worthwhile. Create a product correction only if that controlled run identifies a reproducible product defect.

## Operational and Verification Constraints

- Supported runtime: Prefer Python 3.11 or 3.12. Python 3.14 compatibility is not established for all audio and ML dependencies.
- Platform permission: macOS microphone permission must be granted to the terminal or agent surface that launches the assistant.
- Verification boundary: Automated recovery uses deterministic fakes and cannot prove live microphone, speaker echo, OpenAI service, or provider-network behavior. Use `MANUAL_TESTING.md`, `--wake-debug`, captured WAV replay, and runtime logs for real-device acceptance.
- Local artifacts: `tmp/debug.log` and similar real-test logs are intentionally untracked and must not be treated as durable repository state.
- Live Mac App trials must close any residual Chrome `Hey Jarvis Realtime Host`
  from the legacy workflow. A residual armed host independently captures and
  plays audio and invalidates product-only acoustic observations.

Resolved feature history, evaluator decisions, fallbacks, and prior failure analysis remain available in the completed feature summaries above, `.agent-harness/runs/`, and git history; they are not active Known Issues.
