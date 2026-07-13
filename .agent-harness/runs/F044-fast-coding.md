# F044 Fast Coding Evidence

FAST_CODING_EVIDENCE: F044
CODING_PASS: F044

## Trigger

Real voice logs showed cleaned transcripts `一加一等于几` and `一加一等於幾` fell through to `route=none/tool=chat`, making a deterministic arithmetic request depend on ChatGPT.

## Implementation

- Added dependency-free conservative Chinese positional integer parsing for 零/〇, 一 through 九, 两/兩, 十, 百, and 千.
- Reused the existing Chinese operator normalization and safe calculator evaluator.
- Rejected ambiguous consecutive Chinese digit readings instead of guessing.
- Added Simplified/Traditional, positional integer, local answer-path, text-debug, safety, and documentation coverage.

## Verification

- `.venv/bin/python -m unittest tests.test_tools tests.test_state_machine`: 88 passed before the final zero-placeholder regression.
- `.venv/bin/python -m unittest discover -s tests`: 211 passed.
- `python -m src.main --text '一加一等于几'`: calculator / `1+1` / answer 2.
- `python -m src.main --text '一加一等於幾'`: calculator / `1+1` / answer 2.
- `.venv/bin/python -m src.main --fake-backend`: passed.
- `git diff --check`: passed.

No live microphone, OpenAI chat, speaker, or network was required.
