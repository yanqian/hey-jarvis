import unittest
from contextlib import redirect_stdout
from io import StringIO

from src.main import run_dry_run


class SkeletonSmokeTests(unittest.TestCase):
    def test_dry_run_succeeds(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(run_dry_run(), 0)

        self.assertIn("Assistant started", output.getvalue())


if __name__ == "__main__":
    unittest.main()
