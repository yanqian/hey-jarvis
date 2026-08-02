# F091 Automated Verification

## Scope

Provider-native coding for F091 adds lifecycle-only rotating diagnostics,
redacted support export/clear, bounded unexpected-exit recovery, deterministic
page media release, and native macOS sleep/wake cleanup. This is coding-phase
evidence only; packaged-app user acceptance and the separate Evaluator remain.

## Root-cause record

The first release launch exited normally because an older debug app with the
same bundle identifier was still running and the single-instance plugin
rejected the second instance. Process inspection identified debug app PID 3943
and Python sidecar PID 3951. A normal termination of the old app removed both;
the release app then stayed running and wrote its first lifecycle record. No
implementation method was changed in response to that expected single-instance
behavior.

During sleep/wake implementation, compilation proved that desktop Tauri has no
`RunEvent::Suspended`. Treating a generic initial `Resumed` as wake would have
stopped a healthy startup. The rejected approach was removed and replaced with
the explicit macOS `NSWorkspaceWillSleepNotification` and
`NSWorkspaceDidWakeNotification` boundary.

## Verification

- `./init.sh`: PASS
  - project tests: 398
  - Mac app/Python tests: 10
  - Rust tests: 17
  - dry-run, fake-backend, and Realtime fake smoke: PASS
- JavaScript syntax for both app shell and Realtime host: PASS
- Rust fault injection: three bounded restarts, fourth-exit crash loop, five
  repeated launch/stop cycles with no retained child/stdin/reader: PASS
- Diagnostics: 512 KiB rotation, three generations, forbidden-content
  rejection, 2 MiB export bound, versioned export, and clear: PASS
- Final Apple Silicon `.app` bundle build: PASS

## Authorized packaged-app verification

The first unlocked release trial exposed a packaging defect rather than a
Tauri asset defect. The embedded app page loaded and the frozen sidecar became
ready, but an authenticated request to the loopback host returned an empty
reply. Inspection proved that the PyInstaller spec omitted
`src/realtime_host/static/{index.html,app.js,styles.css}`. The spec now requires
and bundles those three files, and a focused packaging contract prevents the
omission from recurring. After rebuilding the frozen runtime and `.app`, the
WebView loaded the loopback UI at `127.0.0.1`, showing `Runtime ready · click
Arm hands-free audio`; the earlier blank/403 page did not recur.

- The UI exported a 4,024-byte `hey-jarvis-support-v1` bundle containing 20
  correlated Rust, WebView, and Python records. Every record had only the
  allowlisted lifecycle fields, and the forbidden-content scan passed.
- The UI clear action reported success and removed all local diagnostic files.
- Killing the exact supervised sidecar PID caused three bounded restarts with
  new PIDs and `wake_listening` state. The fourth exit recorded
  `sidecar_crash_loop` and remained `non_listening`, with no sidecar process.
- Normal termination of the exact app PID left no app or sidecar process in
  the process table.
- The rebuilt frozen runtime passed its empty-environment packaging smoke, and
  the complete release `.app` bundle rebuilt successfully.

Three consecutive packaged-app launch/quit rounds each produced a distinct App
and sidecar PID; after every exact App termination, the process table contained
neither process. During the third round, a physical Apple-menu sleep followed
by unlock produced the ordered lifecycle evidence
`system_will_sleep -> sidecar_stopped(non_listening) -> system_did_wake`.
After wake, the App remained alive, the sidecar remained absent, and no
automatic Realtime activity occurred. Terminating the App after that trial
again left no residual App or sidecar process.
