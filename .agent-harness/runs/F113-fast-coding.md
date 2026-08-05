# F113 Fast Coding Evidence

FAST_CODING_EVIDENCE: F113

## Implementation

- Added one cancellation signal shared by `ProductRuntime` and
  `RealtimeSessionController`; all controller waits now observe shutdown and a
  shutdown-time stream exception returns `reason=shutdown` without invoking the
  generic microphone-recovery path.
- Added an idempotent `HandoffCoordinator.begin_shutdown()` boundary. It is
  published before teardown, disarms the host, requests an active-session stop,
  makes availability truthfully non-listening, and prevents arm, handoff,
  restore, or late handoff completion from reopening the wake microphone.
- Made the controller thread non-daemon and changed runtime teardown ordering to
  signal shutdown, publish coordinator shutdown, join the controller, then
  destroy the server, microphone lease, and detector. Repeated close is a no-op.
- Gave Python four seconds for the bounded join and extended the native
  supervisor grace period from two to five seconds so a normal safe shutdown is
  not killed while PortAudio cleanup is completing.

## Automated verification

- Focused controller, sidecar, coordinator, and native supervisor tests passed.
- New tests cover a shutdown/read-error race with no reopen, late host cleanup
  with no reopen, idempotent coordinator close, and dependency teardown only
  after controller join.
- `./init.sh` passed with 456 project tests, 11 Mac frontend/sidecar tests, 27
  Rust tests, and all dry-run, fake-backend, and Realtime smoke paths.
- `npm run tauri -- build --debug --bundles app` produced the target-Mac Debug
  app used for live acceptance.

## Target-Mac result

- The Debug app reached `wake_listening` with Python PID 78972, then the current
  Settings path issued a genuine `open_settings` sidecar shutdown.
- Python recorded `shutdown_requested` at 1785912413863 and
  `process_stopped/non_listening` at 1785912414269; native recorded
  `sidecar_stopped/non_listening` at 1785912414366. The process exited and no
  Python process remained.
- The pre-run crash-report baseline ended at
  `Python-2026-08-05-121108.ips`; after shutdown it was unchanged. No new
  `OpenAndSetupOneAudioUnit`/PortAudio crash report or system Python-exit dialog
  appeared.

CODING_PASS: F113
