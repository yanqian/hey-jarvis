# Hey Jarvis

Hey Jarvis is a developer-run macOS voice assistant. It listens locally for
“Hey Jarvis”, answers through OpenAI, speaks through the Mac, and can handle
safe local or provider-backed tools such as arithmetic, time, weather, exchange
rates, and stock quotes.

The project has two voice backends:

| Backend | Best for | Conversation model |
| --- | --- | --- |
| **Pipeline** (default) | Stable local development and debugging | Wake → record → transcribe → answer → speak |
| **Realtime** (opt-in) | Continuous, lower-latency conversation and barge-in | Wake → WebRTC session with follow-up turns |

Both are working MVP paths. A product-owned Tauri app and an unsigned Apple
Silicon DMG can now be built for explicitly trusted internal testing. Developer
ID signing, notarization, launch-at-login, automatic updates, and public binary
distribution of a distributable `.app` remain deferred.

## Project goals

This project solves a personal hands-free need while preserving the CLI as the
simplest interface. It is also an exercise in disciplined AI-assisted
engineering, a job-portfolio case study, and a way to collect feedback from a
small trusted group. Commercial defensibility is not a success criterion; the
engineering decisions and evidence remain useful even if a platform later
ships equivalent wake-word behavior.

## Requirements

- macOS with microphone permission for the launching terminal
- Python 3.11 or Python 3.12
- macOS `afplay` and `afinfo` on `PATH`
- an OpenAI API key
- network access for installation and real OpenAI/provider calls

Realtime additionally launches a local Chrome app-mode host and needs one
**Enable voice assistant** click per host launch.

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
test -f .env || cp .env.example .env
```

Set your key in `.env`:

```text
OPENAI_API_KEY=sk-...
```

Prepare local audio assets and verify the machine:

```bash
python -m src.main --prepare-wake-word
python -m src.main --prepare-acknowledgement
python -m src.main --diagnose
```

Start the default pipeline:

```bash
python -m src.main
```

Say “Hey Jarvis”, wait for the acknowledgement, then ask a question.

To use Realtime instead:

```bash
python -m src.main --backend realtime
```

Click **Enable voice assistant** once in the Chrome window, then use the same wake
phrase. Realtime audio and optional transcription are billable API usage.
Before wake, audio remains local to the Python wake detector.

## Useful commands

| Command | Purpose |
| --- | --- |
| `./init.sh` | Compile, test, and run dependency-free recovery smoke paths |
| `./scripts/build_internal_macos_release.sh` | Build and verify the Apple Silicon `INTERNAL-UNSIGNED` DMG |
| `python -m src.main --dry-run` | Verify the entry point without devices or APIs |
| `python -m src.main --fake-backend` | Exercise the full pipeline state machine with fakes |
| `python -m src.realtime.fake_smoke` | Exercise the Realtime lifecycle without browser, audio, or network |
| `python -m src.main --diagnose` | Check local runtime readiness |
| `python -m src.main --benchmark-acknowledgement` | Compare legacy and duration-bounded ACK player timing |
| `python -m src.main --text "2 + 2"` | Inspect routing without microphone or OpenAI |
| `python -m src.main --wake-debug` | Inspect live microphone levels and wake scores |
| `python -m src.main --wake-file tmp/wake-debug.wav` | Replay a saved wake WAV |

The CLI also supports `--wake-debug-output`, `--prepare-wake-word`,
`--prepare-acknowledgement`, and bounded `--benchmark-iterations`. See the
focused guides below before changing audio, VAD, Realtime, or provider
settings.

## What it can do

The pipeline supports:

- general knowledge answers from the configured chat model;
- deterministic local time and safe arithmetic;
- Open-Meteo weather;
- Frankfurter reference-rate currency conversion;
- Finnhub stock quotes when `FINNHUB_API_KEY` is configured;
- Chinese or English replies based on the current request.

Realtime supports a continuous voice session, interruption, and the same six
allowlisted functions: calculator, weather, local time, foreign exchange,
stock quote, and spoken conversation ending.

Current/live facts are never guessed from model memory when a suitable provider
is unavailable. General knowledge answers do not browse the web or claim that
sources were checked.

## Privacy and safety

- Pre-wake microphone audio stays local.
- `.env`, private voice fixtures, recordings, and local eval evidence are not
  intended for Git.
- Default Realtime reports keep bounded lifecycle metadata and exclude API
  keys, SDP, raw audio, transcript text, and tool content.
- The calculator uses a bounded parser, never `eval`.
- Live Realtime and provider checks may use paid services. Run them only when
  you intend to use the microphone, network, and API quota.

## Documentation

Start with the document matching your task:

- [Deployment](DEPLOYMENT.md) — install, prepare, verify, run, and update.
- [Configuration reference](docs/CONFIGURATION.md) — every `.env` setting and
  its ownership.
- [Pipeline guide](docs/PIPELINE.md) — wake/record flow, tools, response policy,
  and diagnostics.
- [Realtime guide](docs/REALTIME.md) — browser handoff, privacy, controls, and
  evaluation commands.
- [Mac App architecture](docs/MAC_APP_ARCHITECTURE.md) — native ownership,
  sidecar protocol, lifecycle, identity, and release freeze points.
- [Unsigned internal Mac testing](docs/INTERNAL_MAC_APP_TESTING.md) — trusted
  install, privacy/cost, feedback, update, rollback, and uninstall workflow.
- [Portfolio case study](docs/PORTFOLIO_CASE_STUDY.md) — goals, architecture,
  failures, measured tradeoffs, and completion boundary.
- [Portfolio demo](docs/PORTFOLIO_DEMO.md) — privacy-safe 3:30 recording plan.
- [Completion record](docs/PORTFOLIO_COMPLETION.md) — measured readiness,
  unresolved limits, feedback, and explicit go/hold status.
- [Trusted trial evidence](feedback/README.md) — structured feedback and
  release-blocker gate; it never publishes the unsigned DMG.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — common failures and audio debug.

Developer references:

- [Manual testing](MANUAL_TESTING.md) — detailed device acceptance cases.
- [Project specification](SPEC.md) — durable feature requirements.
- [Agent instructions](AGENTS.md) — repository workflow for coding agents.

Development history, evaluator evidence, and orchestration state live under
`.agent-harness/`, with run records in `.agent-harness/runs/`; they are
intentionally not part of this landing page.

## Recovery

From the repository root:

```bash
./init.sh
```

This verifies the harness, compiles Python, runs the full unit suite, and
executes the pipeline and Realtime fake smoke paths without live devices,
credentials, or provider calls.
