import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from src.main import main, run_dry_run, run_fake_backend_smoke


class SkeletonSmokeTests(unittest.TestCase):
    def test_dry_run_succeeds(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(run_dry_run(), 0)

        self.assertIn("Assistant started", output.getvalue())

    def test_fake_backend_smoke_completes_full_loop(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(run_fake_backend_smoke(), 0)

        text = output.getvalue()
        self.assertIn("Fake backend answered: The answer is 4.", text)
        self.assertIn("Returned to WAIT_WAKE", text)

    def test_main_fake_backend_mode_succeeds(self):
        output = StringIO()
        logs = StringIO()
        with redirect_stdout(output), redirect_stderr(logs):
            self.assertEqual(main(["--fake-backend"]), 0)

        self.assertIn("Returned to WAIT_WAKE", output.getvalue())


if __name__ == "__main__":
    unittest.main()
