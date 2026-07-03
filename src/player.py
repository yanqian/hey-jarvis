"""macOS audio playback for Hey Jarvis."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Callable, Sequence


DEFAULT_AFPLAY = "afplay"
PLAYBACK_RECOVERY_GUIDANCE = "Run Hey Jarvis on macOS with afplay available on PATH."


class PlaybackError(RuntimeError):
    """Raised when synthesized speech cannot be played."""


Runner = Callable[..., Any]


class MacOSPlayer:
    """Play synthesized audio files with macOS afplay."""

    def __init__(
        self,
        *,
        afplay_path: str = DEFAULT_AFPLAY,
        runner: Runner | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.afplay_path = afplay_path
        self._runner = runner or subprocess.run
        self._logger = logger or logging.getLogger(__name__)

    def play(self, path: str | Path) -> None:
        play_audio(path, afplay_path=self.afplay_path, runner=self._runner, logger=self._logger)


def play_audio(
    path: str | Path,
    *,
    afplay_path: str = DEFAULT_AFPLAY,
    runner: Runner | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Play one audio file through afplay and surface clear failures."""

    audio_path = Path(path)
    active_logger = logger or logging.getLogger(__name__)
    if not audio_path.is_file():
        raise PlaybackError(f"Audio file not found for playback: {audio_path}")

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
