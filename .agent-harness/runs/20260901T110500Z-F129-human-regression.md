# Run Record: Initial F129 Regression Classification (Superseded)

## Summary

- Date: 2026-09-01
- Classification: `current_feature`
- Feature: F129 - Shorten the measured Home startup critical path
- Result: superseded by F131 root-cause classification

## Observed External Behavior

A fresh current Release installed over `/Applications/Hey Jarvis.app` remained
indefinitely on the visible `Preparing local voice...` startup shell.

Correlated launch `launch-1788230961884-49362` recorded:

- native window shown at 181 ms and WebView shell interactive at 390 ms;
- background sidecar start at 12,746 ms after the Keychain phase;
- packaged-sidecar runtime ready and native sidecar ready at 13,826 ms;
- continuing loopback health checks in the same sidecar session;
- no WebView `runtime_navigation`, no Home milestone, and no bounded slow-start
  notice after readiness.

Read-only process and two-second thread samples showed the native startup thread
had exited, the sidecar reader remained healthy, and neither the main process nor
the WebContent process was spinning or crashed.

## Failure Analysis

- Failure domain: `external_behavior_gap`
- Original promise unmet: F129 requires truthful asynchronous readiness and Home
  navigation from a real ready snapshot.
- Implementation gap: the WebView owns the only ordinary startup navigation and
  checks its 30-second deadline only after an awaited IPC call settles. A rejected
  call is rendered into a Settings-only message that is hidden by the startup
  shell; a never-settling call prevents the deadline check entirely.
- Verification gap: existing Mac shell tests assert source-string presence rather
  than executing the async handoff. The original live Release evidence explicitly
  lacked after-run `sidecar_ready`/`voice_ready` because the unsigned development
  bundle did not complete Keychain authorization, so it verified preparing,
  timeout copy, and Settings but not the successful ready-to-Home transition.
- Harness improvement: acceptance for cross-process startup handoffs
  must require executable state-transition tests and a successful real ready-to-
  navigation trace; source inspection and visible-shell timing are insufficient.

## Required Correction

Keep F129 reopened until native ready navigation, a truly bounded and visible
WebView fallback, deterministic slow/rejected/never-settling behavioral tests,
full recovery verification, fresh fast coding evidence, and an independent
cold-start evaluator verdict are complete.

## Superseding Evidence

Executable source-path inspection subsequently identified the deterministic
F131 out-of-scope `route` access recorded in
`20260901T111000Z-F131-human-regression.md`. F129's completion state is restored;
this record remains as historical evidence of the observed launch and the
orchestrator's fail-closed rejection of premature F129 evaluation.
