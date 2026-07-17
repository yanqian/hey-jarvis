from __future__ import annotations

import unittest

from src.realtime.fake_smoke import run_fake_smoke


class RealtimeFakeSmokeTests(unittest.TestCase):
    def test_full_mvp_lifecycle_is_deterministic_and_dependency_free(self):
        result = run_fake_smoke()
        self.assertTrue(result.passed)
        self.assertEqual(result.user_turns, 2)
        self.assertEqual(result.assistant_completions, 2)


if __name__ == "__main__":
    unittest.main()
