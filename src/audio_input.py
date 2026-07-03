"""Reusable microphone stream wrapper for Hey Jarvis."""

from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import Any


DEFAULT_BLOCK_FRAMES = 1024
MICROPHONE_RECOVERY_GUIDANCE = (
    "Install requirements.txt, connect a microphone, and grant macOS microphone "
    "permission to the terminal or agent surface running Hey Jarvis."
)


class AudioInputError(RuntimeError):
    """Raised when microphone input cannot be opened or read."""


class MicrophoneStream:
    """Open and reuse one 16 kHz mono int16 PCM microphone stream."""

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        block_frames: int = DEFAULT_BLOCK_FRAMES,
        device: int | str | None = None,
        sounddevice_module: ModuleType | Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if block_frames <= 0:
            raise ValueError("block_frames must be positive")

        self.sample_rate = sample_rate
        self.block_frames = block_frames
        self.device = device
        self._sounddevice_module = sounddevice_module
        self._stream: Any | None = None
        self._logger = logger or logging.getLogger(__name__)

    def open(self) -> "MicrophoneStream":
        """Open the underlying sounddevice RawInputStream if needed."""

        if self._stream is not None:
            return self

        try:
            sounddevice = self._sounddevice_module or importlib.import_module("sounddevice")
            stream = sounddevice.RawInputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.block_frames,
                device=self.device,
            )
            stream.start()
        except Exception as exc:  # pragma: no cover - exact sounddevice errors vary by host.
            self._logger.error("Unable to open microphone stream. %s", MICROPHONE_RECOVERY_GUIDANCE)
            raise AudioInputError(f"Unable to open microphone stream: {exc}") from exc

        self._stream = stream
        return self

    def read_chunk(self) -> bytes:
        """Read one PCM chunk from the reusable microphone stream."""

        self.open()
        assert self._stream is not None

        try:
            data, overflowed = self._stream.read(self.block_frames)
        except Exception as exc:  # pragma: no cover - exact sounddevice errors vary by host.
            self._logger.error("Unable to read microphone audio. %s", MICROPHONE_RECOVERY_GUIDANCE)
            raise AudioInputError(f"Unable to read microphone audio: {exc}") from exc

        if overflowed:
            self._logger.warning("Microphone input overflowed; the current audio chunk may be incomplete")

        return bytes(data)

    def close(self) -> None:
        """Close the underlying microphone stream if it is open."""

        if self._stream is None:
            return

        stream = self._stream
        self._stream = None
        close = getattr(stream, "close", None)
        if close is not None:
            close()

    def __enter__(self) -> "MicrophoneStream":
        return self.open()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def open_microphone_stream(
    *,
    sample_rate: int = 16000,
    block_frames: int = DEFAULT_BLOCK_FRAMES,
    device: int | str | None = None,
    logger: logging.Logger | None = None,
) -> MicrophoneStream:
    """Create and open a reusable 16 kHz mono int16 PCM microphone stream."""

    return MicrophoneStream(
        sample_rate=sample_rate,
        block_frames=block_frames,
        device=device,
        logger=logger,
    ).open()
