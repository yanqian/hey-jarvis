"""macOS audio playback for Hey Jarvis."""

from __future__ import annotations

import logging
import math
import re
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, Sequence


DEFAULT_AFPLAY = "afplay"
DEFAULT_AFINFO = "afinfo"
PLAYBACK_RECOVERY_GUIDANCE = "Run Hey Jarvis on macOS with afplay available on PATH."
_AFINFO_DURATION = re.compile(r"estimated duration:\s*([0-9]+(?:\.[0-9]+)?)\s*sec")
MAX_BENCHMARK_ITERATIONS = 20
MAX_BENCHMARK_TIMING_MS = 60_000


class PlaybackError(RuntimeError):
    """Raised when synthesized speech cannot be played."""


@dataclass(frozen=True)
class PlaybackBenchmarkTrial:
    """One directly observed local playback-process lifecycle."""

    index: int
    process_start_call_ms: int
    process_lifetime_ms: int
    total_wall_ms: int
    derived_overhead_ms: int


@dataclass(frozen=True)
class PlaybackBenchmark:
    """Privacy-safe repeated playback timings for one prepared asset."""

    asset_duration_ms: int
    trials: tuple[PlaybackBenchmarkTrial, ...]
    median_process_start_call_ms: int
    median_process_lifetime_ms: int
    median_total_wall_ms: int
    median_derived_overhead_ms: int


Runner = Callable[..., Any]
ProcessFactory = Callable[..., Any]


class PlaybackHandle(Protocol):
    """Observe and join one running playback process."""

    def poll(self) -> int | None:
        """Return None while playback is running, otherwise its exit status."""

    def wait(self) -> None:
        """Wait for playback and raise PlaybackError on failure."""


class _ProcessPlaybackHandle:
    def __init__(self, process: Any, command: Sequence[str], logger: logging.Logger) -> None:
        self._process = process
        self._command = tuple(command)
        self._logger = logger

    def poll(self) -> int | None:
        return self._process.poll()

    def wait(self) -> None:
        try:
            stdout, stderr = self._process.communicate()
        except Exception as exc:
            self._logger.error("Playback failed while waiting for afplay: %s", exc)
            raise PlaybackError(f"Playback failed while waiting for afplay: {exc}") from exc
        returncode = getattr(self._process, "returncode", 0)
        if returncode:
            detail = _failure_detail(
                self._command,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            )
            self._logger.error("Playback failed: %s", detail)
            raise PlaybackError(detail)


class MacOSPlayer:
    """Play synthesized audio files with macOS afplay."""

    def __init__(
        self,
        *,
        afplay_path: str = DEFAULT_AFPLAY,
        runner: Runner | None = None,
        process_factory: ProcessFactory | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.afplay_path = afplay_path
        self._runner = runner or subprocess.run
        self._process_factory = process_factory or subprocess.Popen
        self._logger = logger or logging.getLogger(__name__)

    def play(self, path: str | Path) -> None:
        play_audio(path, afplay_path=self.afplay_path, runner=self._runner, logger=self._logger)

    def start(self, path: str | Path) -> PlaybackHandle:
        """Start playback without blocking so callers can service microphone input."""

        audio_path = _require_audio_file(path)
        command = [self.afplay_path, str(audio_path)]
        try:
            process = self._process_factory(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            self._logger.error("Playback failed because afplay was not found. %s", PLAYBACK_RECOVERY_GUIDANCE)
            raise PlaybackError(f"afplay was not found: {exc}") from exc
        except Exception as exc:
            self._logger.error("Playback failed while starting afplay: %s", exc)
            raise PlaybackError(f"Playback failed while starting afplay: {exc}") from exc
        return _ProcessPlaybackHandle(process, command, self._logger)

    def duration_ms(self, path: str | Path, *, afinfo_path: str = DEFAULT_AFINFO) -> int:
        """Read bounded audio duration metadata without playing the asset."""

        return audio_duration_ms(
            path,
            afinfo_path=afinfo_path,
            runner=self._runner,
            logger=self._logger,
        )


def benchmark_audio_playback(
    player: MacOSPlayer,
    path: str | Path,
    *,
    iterations: int = 5,
    clock: Callable[[], float] = time.monotonic,
) -> PlaybackBenchmark:
    """Measure observable afplay process phases without inferring audible onset."""

    if isinstance(iterations, bool) or not isinstance(iterations, int):
        raise PlaybackError("Acknowledgement benchmark iterations must be an integer")
    if not 1 <= iterations <= MAX_BENCHMARK_ITERATIONS:
        raise PlaybackError(
            f"Acknowledgement benchmark iterations must be between 1 and {MAX_BENCHMARK_ITERATIONS}"
        )
    audio_path = Path(path)
    if not audio_path.is_file():
        raise PlaybackError("Acknowledgement benchmark asset was unavailable")
    try:
        asset_duration_ms = player.duration_ms(audio_path)
    except PlaybackError as exc:
        raise PlaybackError("Acknowledgement benchmark could not inspect the asset duration") from exc
    if (
        isinstance(asset_duration_ms, bool)
        or not isinstance(asset_duration_ms, int)
        or not 1 <= asset_duration_ms <= MAX_BENCHMARK_TIMING_MS
    ):
        raise PlaybackError("Acknowledgement benchmark asset duration was outside the supported range")

    trials: list[PlaybackBenchmarkTrial] = []
    for index in range(1, iterations + 1):
        before_start = _benchmark_clock_value(clock)
        try:
            handle = player.start(audio_path)
        except PlaybackError as exc:
            raise PlaybackError(f"Acknowledgement benchmark trial {index} could not start") from exc
        after_start = _benchmark_clock_value(clock)
        try:
            handle.wait()
        except PlaybackError as exc:
            raise PlaybackError(f"Acknowledgement benchmark trial {index} did not complete") from exc
        after_wait = _benchmark_clock_value(clock)

        process_start_call_ms = _bounded_elapsed_ms(before_start, after_start)
        process_lifetime_ms = _bounded_elapsed_ms(after_start, after_wait)
        total_wall_ms = process_start_call_ms + process_lifetime_ms
        if total_wall_ms > MAX_BENCHMARK_TIMING_MS:
            raise PlaybackError("Acknowledgement benchmark total timing exceeded the supported range")
        derived_overhead_ms = total_wall_ms - asset_duration_ms
        if derived_overhead_ms < 0:
            raise PlaybackError(
                "Acknowledgement benchmark wall time was shorter than the asset metadata duration"
            )
        trials.append(
            PlaybackBenchmarkTrial(
                index=index,
                process_start_call_ms=process_start_call_ms,
                process_lifetime_ms=process_lifetime_ms,
                total_wall_ms=total_wall_ms,
                derived_overhead_ms=derived_overhead_ms,
            )
        )

    return PlaybackBenchmark(
        asset_duration_ms=asset_duration_ms,
        trials=tuple(trials),
        median_process_start_call_ms=_median_ms(
            trial.process_start_call_ms for trial in trials
        ),
        median_process_lifetime_ms=_median_ms(trial.process_lifetime_ms for trial in trials),
        median_total_wall_ms=_median_ms(trial.total_wall_ms for trial in trials),
        median_derived_overhead_ms=_median_ms(trial.derived_overhead_ms for trial in trials),
    )


def play_audio(
    path: str | Path,
    *,
    afplay_path: str = DEFAULT_AFPLAY,
    runner: Runner | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Play one audio file through afplay and surface clear failures."""

    audio_path = _require_audio_file(path)
    active_logger = logger or logging.getLogger(__name__)

    command = [afplay_path, str(audio_path)]
    run = runner or subprocess.run
    try:
        result = run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        active_logger.error("Playback failed because afplay was not found. %s", PLAYBACK_RECOVERY_GUIDANCE)
        raise PlaybackError(f"afplay was not found: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        detail = _failure_detail(command, returncode=exc.returncode, stdout=exc.stdout, stderr=exc.stderr)
        active_logger.error("Playback failed: %s", detail)
        raise PlaybackError(detail) from exc
    except Exception as exc:
        active_logger.error("Playback failed while running afplay: %s", exc)
        raise PlaybackError(f"Playback failed while running afplay: {exc}") from exc

    returncode = getattr(result, "returncode", 0)
    if returncode:
        detail = _failure_detail(
            command,
            returncode=returncode,
            stdout=getattr(result, "stdout", ""),
            stderr=getattr(result, "stderr", ""),
        )
        active_logger.error("Playback failed: %s", detail)
        raise PlaybackError(detail)


def audio_duration_ms(
    path: str | Path,
    *,
    afinfo_path: str = DEFAULT_AFINFO,
    runner: Runner | None = None,
    logger: logging.Logger | None = None,
) -> int:
    """Return rounded macOS audio metadata duration in milliseconds."""

    audio_path = _require_audio_file(path)
    active_logger = logger or logging.getLogger(__name__)
    run = runner or subprocess.run
    command = [afinfo_path, str(audio_path)]
    try:
        result = run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        active_logger.error("Audio duration inspection failed because afinfo was not found")
        raise PlaybackError(f"afinfo was not found: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        detail = _failure_detail(
            command,
            returncode=exc.returncode,
            stdout=exc.stdout,
            stderr=exc.stderr,
        )
        active_logger.error("Audio duration inspection failed: %s", detail)
        raise PlaybackError(detail) from exc
    except Exception as exc:
        active_logger.error("Audio duration inspection failed: %s", exc)
        raise PlaybackError(f"Audio duration inspection failed: {exc}") from exc
    output = f"{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}"
    match = _AFINFO_DURATION.search(output)
    if match is None:
        raise PlaybackError("afinfo did not report an estimated audio duration")
    duration_ms = round(float(match.group(1)) * 1000)
    if not 1 <= duration_ms <= 60_000:
        raise PlaybackError("Audio duration was outside the supported range")
    return duration_ms


def _require_audio_file(path: str | Path) -> Path:
    audio_path = Path(path)
    if not audio_path.is_file():
        raise PlaybackError(f"Audio file not found for playback: {audio_path}")
    return audio_path


def _failure_detail(
    command: Sequence[str],
    *,
    returncode: int,
    stdout: str | bytes | None,
    stderr: str | bytes | None,
) -> str:
    detail = _first_output(stderr) or _first_output(stdout) or "no error output"
    executable = Path(command[0]).name if command else "audio player"
    return f"{executable} exited with status {returncode}: {detail}"


def _benchmark_clock_value(clock: Callable[[], float]) -> float:
    try:
        value = float(clock())
    except Exception as exc:
        raise PlaybackError("Acknowledgement benchmark clock failed") from exc
    if not math.isfinite(value):
        raise PlaybackError("Acknowledgement benchmark clock returned a non-finite value")
    return value


def _bounded_elapsed_ms(start: float, end: float) -> int:
    elapsed = end - start
    if elapsed < 0:
        raise PlaybackError("Acknowledgement benchmark clock moved backwards")
    elapsed_ms = round(elapsed * 1000)
    if not 0 <= elapsed_ms <= MAX_BENCHMARK_TIMING_MS:
        raise PlaybackError("Acknowledgement benchmark timing exceeded the supported range")
    return elapsed_ms


def _median_ms(values: Iterable[int]) -> int:
    materialized = tuple(values)
    if not materialized:
        raise PlaybackError("Acknowledgement benchmark produced no trials")
    return round(statistics.median(materialized))


def _first_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value.strip().splitlines()[0] if value.strip() else ""
