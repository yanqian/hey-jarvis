# F071 Fast Coding Evidence

FAST_CODING_EVIDENCE: F071

CODING_PASS: F071

## Scope

Restructured project-facing documentation without changing runtime source,
configuration defaults, CLI behavior, manual acceptance history, or live
integration behavior.

## Changes

- Reduced `README.md` from 909 lines to a 151-line landing page.
- Focused `DEPLOYMENT.md` on supported target, install, prepare, verify, run,
  update, and local artifact flows.
- Added `docs/CONFIGURATION.md` as the complete `.env.example` setting owner.
- Added `docs/PIPELINE.md` for pipeline lifecycle, routing, language, knowledge,
  and timing behavior.
- Added `docs/REALTIME.md` for WebRTC lifecycle, privacy, tools, controls,
  fixtures, and RT001-RT004/F060 evaluation operation.
- Added `docs/TROUBLESHOOTING.md` for dependency, wake, recording, provider, and
  Realtime recovery.
- Replaced README-centric assertions with ownership, line-limit, CLI,
  configuration-inventory, Realtime-contract, local-link, and developer-boundary
  documentation tests.
- Left `MANUAL_TESTING.md`, root `SPEC.md`, runtime source, spikes, internal host
  notes, and historical run material materially unchanged.

## Verification

Focused documentation suite:

```text
python3 -m unittest tests.test_documentation -v
Ran 13 tests in 0.002s
OK
```

Final recovery:

```text
./init.sh
validated 71 features
Ran 341 project tests
project recovery verification passed
```

The recovery path remained dependency-free for audio/OpenAI/provider behavior
and made no live network, credential, microphone, speaker, or browser calls.
