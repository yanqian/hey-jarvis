# F042 Fast Coding Evidence

Date: 2026-07-13

The normal and approved-escalated `make -C .agent-harness work-fast` attempts both failed before handoff because the configured Codex Evaluator provider runtime check exited with code 1 while reading its startup prompt. Interactive manual fallback was used without bypassing evaluator gating.

Implemented the normalized personal US watchlist name-routing requirement in the existing deterministic stock router. Added English and common Simplified/Traditional Chinese aliases for the user's screenshot symbols, including `SpaceX -> SPCX`; retained `Google`/`Alphabet`/`谷歌 -> GOOGL`; and verified that explicit uppercase `GOOG` and `GOOGL` take precedence. Existing conservative stock-intent gating and Finnhub provider behavior are unchanged. README coverage and table-driven router, ambiguity, ticker-precedence, and mocked text-debug regressions were added.

Verification:

- `python3 -m unittest tests.test_tools` — 38 tests passed.
- `python3 -m unittest discover -s tests` — 207 tests passed.
- `git diff --check` — passed.
- `./init.sh` — harness checks, 207 project tests, dry-run, fake-backend, and recovery verification passed.

Untracked user-owned `tmp/debug.log` and `tmp/pr1-real.log` were left untouched.

Evaluator retry: the first cold-start evaluation found that `iShares Core S&P 500 股价` was parsed as ticker `S` before alias resolution. Ticker extraction now excludes uppercase tokens immediately adjacent to `&`, preserving explicit ticker precedence while allowing the IVV English alias to resolve. The focused and full verification commands were rerun after this correction.

FAST_CODING_EVIDENCE: F042
CODING_PASS: F042
