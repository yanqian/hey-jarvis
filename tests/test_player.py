import logging
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.player import (
    MacOSPlayer,
    PlaybackError,
    audio_duration_ms,
    benchmark_audio_playback,
    play_audio,
)


class PlayerTests(unittest.TestCase):
    def test_benchmark_separates_observable_process_phases(self):
        class FakeHandle:
            def wait(self):
                return None

        class FakePlayer:
            def __init__(self):
                self.start_calls = 0
                self.duration_calls = 0

            def duration_ms(self, path):
                self.duration_calls += 1
                return 480

            def start(self, path):
                self.start_calls += 1
                return FakeHandle()

        times = iter((0.000, 0.003, 0.500, 1.000, 1.002, 1.480))
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "private-name.mp3"
            audio_path.write_bytes(b"fake-mp3")
            player = FakePlayer()
            result = benchmark_audio_playback(
                player,
                audio_path,
                iterations=2,
                clock=lambda: next(times),
            )

        self.assertEqual(player.duration_calls, 1)
        self.assertEqual(player.start_calls, 2)
        self.assertEqual(result.asset_duration_ms, 480)
        self.assertEqual(
            result.trials[0],
            result.trials[0].__class__(
                index=1,
                process_start_call_ms=3,
                process_lifetime_ms=497,
                total_wall_ms=500,
                derived_overhead_ms=20,
            ),
        )
        self.assertEqual(result.trials[1].process_start_call_ms, 2)
        self.assertEqual(result.trials[1].process_lifetime_ms, 478)
        self.assertEqual(result.median_total_wall_ms, 490)
        self.assertEqual(result.median_derived_overhead_ms, 10)

    def test_benchmark_rejects_invalid_iterations_and_unsafe_timings(self):
        class FakeHandle:
            def wait(self):
                return None

        class FakePlayer:
            def duration_ms(self, path):
                return 480

            def start(self, path):
                return FakeHandle()

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "ack.mp3"
            audio_path.write_bytes(b"fake-mp3")
            for iterations in (0, 21, True):
                with self.subTest(iterations=iterations):
                    with self.assertRaises(PlaybackError):
                        benchmark_audio_playback(
                            FakePlayer(),
                            audio_path,
                            iterations=iterations,
                        )
            with self.assertRaisesRegex(PlaybackError, "moved backwards"):
                benchmark_audio_playback(
                    FakePlayer(),
                    audio_path,
                    iterations=1,
                    clock=iter((1.0, 0.9, 1.5)).__next__,
                )
            with self.assertRaisesRegex(PlaybackError, "shorter than"):
                benchmark_audio_playback(
                    FakePlayer(),
                    audio_path,
                    iterations=1,
                    clock=iter((0.0, 0.001, 0.100)).__next__,
                )

    def test_audio_duration_reads_bounded_afinfo_metadata(self):
        calls = []

        def fake_runner(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(
                returncode=0,
                stdout="estimated duration: 0.480000 sec\n",
                stderr="",
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "ack.mp3"
            audio_path.write_bytes(b"fake-mp3")
            duration = audio_duration_ms(
                audio_path,
                afinfo_path="/usr/bin/afinfo",
                runner=fake_runner,
            )

        self.assertEqual(duration, 480)
        self.assertEqual(calls[0][0], ["/usr/bin/afinfo", str(audio_path)])

    def test_audio_duration_rejects_missing_or_unbounded_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "ack.mp3"
            audio_path.write_bytes(b"fake-mp3")
            for output in ("no duration", "estimated duration: 0.000000 sec"):
                with self.subTest(output=output):
                    runner = lambda *args, **kwargs: SimpleNamespace(
                        returncode=0,
                        stdout=output,
                        stderr="",
                    )
                    with self.assertRaises(PlaybackError):
                        audio_duration_ms(audio_path, runner=runner)

    def test_start_returns_observable_handle_and_waits_for_success(self):
        calls = []

        class FakeProcess:
            returncode = 0

            def poll(self):
                return None

            def communicate(self):
                return ("", "")

        def fake_process_factory(command, **kwargs):
            calls.append((command, kwargs))
            return FakeProcess()

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "ack.mp3"
            audio_path.write_bytes(b"fake-mp3")
            handle = MacOSPlayer(
                afplay_path="/usr/bin/afplay",
                process_factory=fake_process_factory,
            ).start(audio_path)
            self.assertIsNone(handle.poll())
            handle.wait()

        self.assertEqual(calls[0][0], ["/usr/bin/afplay", str(audio_path)])
        self.assertEqual(calls[0][1]["stdout"], subprocess.PIPE)
        self.assertEqual(calls[0][1]["stderr"], subprocess.PIPE)
        self.assertTrue(calls[0][1]["text"])

    def test_started_playback_failure_reports_stderr(self):
        class FakeProcess:
            returncode = 42

            def poll(self):
                return 42

            def communicate(self):
                return ("", "unsupported audio format\nmore detail")

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "ack.mp3"
            audio_path.write_bytes(b"fake-mp3")
            logger = logging.getLogger("tests.player.started_failure")
            player = MacOSPlayer(
                process_factory=lambda *args, **kwargs: FakeProcess(),
                logger=logger,
            )
            with self.assertLogs(logger, level="ERROR"):
                with self.assertRaisesRegex(PlaybackError, "unsupported audio format"):
                    player.start(audio_path).wait()

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
