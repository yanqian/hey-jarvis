# F088 Mac App Live Acceptance

LIVE_USER_AUTHORIZED: F088
LIVE_TECHNICAL_RESULT: PASS
LIVE_USER_AUDIBLE_CONFIRMATION: PASS
LIVE_PASS: F088

## Scope

The user explicitly authorized a billable Apple Silicon built-in-microphone
and built-in-speaker run. The run used the production-owned Tauri/WKWebView
shell and product sidecar, with the ignored local OpenAI key injected only into
the controlled launch environment. No credential, transcript, answer, SDP,
provider payload, audio, or capability URL was retained as evidence.

## Startup corrections

The first Finder launch did not inherit the controlled development credential
and correctly failed closed before exposing the media page. It also showed
that the three-second fake-sidecar readiness window was too short for real
wake-model warmup and microphone acquisition. F088 was corrected to:

- allow a bounded 30-second product startup window;
- surface the sidecar's redacted startup error code instead of the misleading
  `sidecar did not send readiness` fallback;
- explicitly show and focus the native window after setup.

Full offline recovery passed after the correction. The controlled relaunch
then reached the product Realtime page with the Arm control, while the API key
remained outside JavaScript and the sidecar protocol.

## Live behavior

After one Arm gesture, the user confirmed:

- local wake detection and one audible acknowledgement;
- a normal, continuous spoken answer;
- a follow-up turn in the same Realtime session;
- a provider-backed weather tool turn;
- deliberate natural interruption stopped the old answer and produced the
  replacement answer;
- semantic farewell closed the session and restored the waiting-for-wake
  state;
- a fresh wake after recovery completed another answer and semantic close.

An early trial sounded duplicated and produced an unrelated response. Process
inspection showed exactly one product App and one product sidecar, and the
sanitized browser events showed one remote track per session with
non-overlapping playback intervals. A separately played acknowledgement asset
was single-channel and played exactly once. The user found and closed a
residual Chrome `Hey Jarvis Realtime Host` from the pre-product workflow. The
clean product-only retry then had one acknowledgement, no self-monitoring, and
the correct answer. This was an external test-environment conflict, not
accepted as product behavior.

## Cleanup and relaunch

The user ended the recovered session and selected tray Quit. An external
process-table and listener check found no Hey Jarvis native process, product
sidecar, or product loopback listener. The only remaining Python loopback
listener belonged to an unrelated named local application.

A fresh controlled relaunch started a new native process and product sidecar,
and the user confirmed that the WKWebView again displayed the Arm control. The
relaunch was then terminated and a second process check found no Hey Jarvis or
product-sidecar residue.

F088 still requires separate cold-start evaluator approval.
