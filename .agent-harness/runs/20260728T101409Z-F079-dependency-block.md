# F079 Dependency Block

Feature: F079 - Reduce acknowledgement playback overhead

Date: 2026-07-28
Result: Blocked before coding

`make -C .agent-harness work-fast` selected F079 even though its declared F080
dependency was incomplete. No F079 implementation or coding-pass evidence was
produced. The feature remains incomplete and may resume only after separate
Evaluator approval for F080.

Failure domain: harness_workflow
Harness improvement: the orchestrator should exclude features whose declared
dependencies do not have both `passes=true` and `status=done`.
