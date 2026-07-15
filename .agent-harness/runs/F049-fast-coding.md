# F049 Fast Coding Evidence

Date: 2026-07-15

FAST_CODING_EVIDENCE: F049
CODING_PASS: F049

## Implementation

- Normalizes the multi-character `乘以` operator before bare `乘`, preventing the leftover `以` that previously truncated extraction to `100*`.
- Extends conservative Chinese positional integers through one `万/萬` section, bounded to 99,999,999.
- Rejects ambiguous digit sequences, repeated `万`, unsupported `亿/億`, and expressions ending in a binary operator instead of routing an incomplete calculator expression.
- Adds router, execution, text-debug, answer-path, state-machine, safety, and documentation coverage without changing audio or provider behavior.

## Verification

- Focused tool/state-machine/main/documentation suite: 106 tests passed.
- Full unittest discovery: 223 tests passed.
- `python3 -m src.main --text '一百乘以一千等于多少'`: expression `100*1000`, answer 100000.
- `python3 -m src.main --text '一百乘以一萬等於多少'`: expression `100*10000`, answer 1000000.
- `git diff --check`: passed.
- `./init.sh`: passed with harness checks, 223 project tests, dry-run, and fake-backend smoke.
