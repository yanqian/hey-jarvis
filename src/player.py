"""macOS audio playback for Hey Jarvis."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence


DEFAULT_AFPLAY = "afplay"
PLAYBACK_RECOVERY_GUIDANCE = "Run Hey Jarvis on macOS with afplay available on PATH."


class PlaybackError(RuntimeError):
    """Raised when synthesized speech cannot be played."""


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
    return f"{' '.join(command)} exited with status {returncode}: {detail}"


def _first_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value.strip().splitlines()[0] if value.strip() else ""
