# Run Record: F115 - local Settings visual acceptance

## Summary

- Date: 2026-08-05 (Asia/Singapore)
- Build: current-source Debug `.app`
- Result: PASS

## Inspection

The rebuilt Settings window was inspected at its regular 820 × 640 size and
at the compact supported window boundary. The final screen contained one Voice
status component. General presented Assistant setup and Smart Speaker Mode as
unboxed titled sections separated by whitespace and one quiet divider. Only
the readiness surface and Smart Speaker toggle row retained card borders, so
the previous nested-card effect was absent.

The setup actions stayed with setup readiness and wrapped safely at compact
width. Smart Speaker status stayed with its toggle. `How sleep and wake work`
could be expanded and collapsed, exposed its state in the accessibility tree,
and revealed the complete battery, explicit Sleep, lid-close, wake-recovery,
and shutdown disclosure. The separate local-before-wake privacy note remained
visible.

The inspection did not trigger a microphone check, mutate credentials or
preferences, start a paid conversation, or retain private conversation data.
