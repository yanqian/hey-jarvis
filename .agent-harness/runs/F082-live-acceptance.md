# F082 Live Realtime Local-Time Acceptance

## Scope

This was a user-authorized, billable Realtime session on the target Mac using
its built-in microphone and speaker. The user followed M082: ask for current
local time, make an ordinary follow-up, and end semantically.

## Result

- The user confirmed the test was successful.
- The local-time response was accepted as correct and usable.
- The ordinary follow-up remained usable in the same session.
- The runtime ended with `reason=end_phrase` and
  `recovered_to_wake=true`.
- The test host was then stopped normally.

No transcript, answer, call identity, tool arguments, audio, credential, or
provider payload is retained in this evidence.

## Verdict

LIVE_USER_PASS: F082

Separate cold-start evaluator approval remains required. No evaluator verdict
is claimed here.
