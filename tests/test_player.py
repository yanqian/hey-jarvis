import logging
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.player import MacOSPlayer, PlaybackError, play_audio


class PlayerTests(unittest.TestCase):
    def test_play_audio_runs_afplay_for_existing_file(self):
        calls = []

        def fake_runner(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "output.mp3"
            audio_path.write_bytes(b"fake-mp3")

            MacOSPlayer(afplay_path="/usr/bin/afplay", runner=fake_runner).play(audio_path)

        self.assertEqual(calls[0][0], ["/usr/bin/afplay", str(audio_path)])
        self.assertTrue(calls[0][1]["check"])
        self.assertTrue(calls[0][1]["capture_output"])

    def test_missing_audio_file_fails_clearly(self):
        with self.assertRaises(PlaybackError) as caught:
            play_audio("missing-output.mp3")

        self.assertIn("Audio file not found", str(caught.exception))

    def test_afplay_command_failure_reports_stderr(self):
        def fake_runner(command, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=42,
                cmd=command,
                stderr="unsupported audio format\nmore detail",
                output="",
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "output.mp3"
            audio_path.write_bytes(b"fake-mp3")

            logger = logging.getLogger("tests.player.failure")
            with self.assertLogs(logger, level="ERROR"):
                with self.assertRaises(PlaybackError) as caught:
                    play_audio(audio_path, afplay_path="afplay", runner=fake_runner, logger=logger)

        message = str(caught.exception)
        self.assertIn("exited with status 42", message)
        self.assertIn("unsupported audio format", message)


if __name__ == "__main__":
    unittest.main()
