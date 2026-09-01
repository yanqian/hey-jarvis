# Run Record: F131 Human-Acceptance Regression

## Summary

- Date: 2026-09-01
- Classification: `current_feature`
- Feature: F131 - Restore Smart Speaker media retention on fast startup
- Result: reopened

## Root Cause

F131 changed the ready branch in `waitForStartupRuntime()` from
`navigateToAssistant(runtime)` to a call using `route.smart_speaker_mode`.
`route` is declared with `const` inside `load()` and is not in scope inside
`waitForStartupRuntime()`. Once native pending clears and the sidecar is ready,
the WebView deterministically throws `ReferenceError` before recording
`runtime_navigation` or calling `window.location.assign()`.

The top-level catch writes that error to `elements.message`, which belongs to the
hidden Settings shell, so the visible startup status remains `Preparing local
voice...`. This exactly matches correlated launch `launch-1788230961884-49362`:
native sidecar ready at 13,826 ms, continuing health checks, and no navigation.

## Verification Gap

The F131 Node tests execute only `assistantModeFragment()` in isolation. The Mac
shell test asserts that the faulty source text exists, but never executes the
pending-to-ready handoff. The original acceptance criterion explicitly required
behavioral fast-start coverage rather than source-string presence, so the prior
evaluator accepted insufficient evidence.

## Failure Analysis

- Failure domain: `implementation_gap`
- Failure summary: an out-of-scope route lookup strands every returning launch
  that reaches the F131 ready branch.
- Harness improvement: cross-function async route changes require an executable
  state-transition test that reaches the navigation callback with real-shaped
  route and ready snapshots; isolated fragment tests and source assertions are
  insufficient.
- Follow-up feature: none; reopen and correct F131.

## Required Correction

Pass the bounded mode explicitly across the async handoff, render handoff errors
on the visible startup surface, add executable enabled/disabled ready-transition
tests that fail against the old code, pass full recovery and builds, record fresh
fast coding evidence, and require a new independent evaluator verdict.
