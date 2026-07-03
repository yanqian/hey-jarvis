"""WAV recording from PCM microphone chunks."""

from __future__ import annotations

import logging
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from .silence import SAMPLE_WIDTH_BYTES, is_silence


DEFAULT_INPUT_WAV = Path("tmp/input.wav")
CHANNELS = 1


class ChunkReader(Protocol):
    def read_chunk(self) -> bytes:
        """Read one int16 PCM audio chunk."""


@dataclass(frozen=True)
class RecordingResult:
    path: Path
    duration_seconds: float
    chunks_recorded: int
    stopped_by: str


class Recorder:
    """Collect int16 PCM chunks and write a mono WAV recording."""

    def __init__(
        self,
        source: ChunkReader | Iterable[bytes],
        *,
        sample_rate: int = 16000,
        silence_seconds: float = 1.5,
        max_record_seconds: float = 20.0,
        silence_threshold: float = 500.0,
        output_path: str | Path = DEFAULT_INPUT_WAV,
        logger: logging.Logger | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if silence_seconds <= 0:
            raise ValueError("silence_seconds must be positive")
        if max_record_seconds <= 0:
            raise ValueError("max_record_seconds must be positive")
        if max_record_seconds <= silence_seconds:
            raise ValueError("max_record_seconds must be greater than silence_seconds")

        self.source = source
        self.sample_rate = sample_rate
        self.silence_seconds = silence_seconds
        self.max_record_seconds = max_record_seconds
        self.silence_threshold = silence_threshold
        self.output_path = Path(output_path)
        self._logger = logger or logging.getLogger(__name__)
        self._source_iter: Iterable[bytes] | None = None

    def record(self) -> RecordingResult:
        """Record until consecutive silence, max duration, or source exhaustion."""

        chunks: list[bytes] = []
        duration_seconds = 0.0
        silent_seconds = 0.0
        stopped_by = "source_exhausted"

        while duration_seconds < self.max_record_seconds:
            try:
                chunk = self._read_next_chunk()
            except StopIteration:
                break
            except Exception:
                self._logger.error(
                    "Audio recording failed. Check microphone availability and macOS microphone permission."
                )
                raise

            _validate_pcm_chunk(chunk)
            if not chunk:
                continue

            chunk_seconds = len(chunk) / (self.sample_rate * CHANNELS * SAMPLE_WIDTH_BYTES)
            chunks.append(chunk)
            duration_seconds += chunk_seconds

            if is_silence(chunk, self.silence_threshold):
                silent_seconds += chunk_seconds
            else:
                silent_seconds = 0.0

            if duration_seconds >= self.max_record_seconds:
                stopped_by = "max_duration"
                break
            if silent_seconds >= self.silence_seconds:
                stopped_by = "silence"
                break

        self._write_wav(chunks)
        return RecordingResult(
            path=self.output_path,
            duration_seconds=duration_seconds,
            chunks_recorded=len(chunks),
            stopped_by=stopped_by,
        )

    def _read_next_chunk(self) -> bytes:
        read_chunk = getattr(self.source, "read_chunk", None)
        if read_chunk is not None:
            return read_chunk()

        if self._source_iter is None:
            self._source_iter = iter(self.source)
        return next(self._source_iter)

    def _write_wav(self, chunks: list[bytes]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(self.output_path), "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(SAMPLE_WIDTH_BYTES)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(b"".join(chunks))


def record_to_wav(
    source: ChunkReader | Iterable[bytes],
    *,
    sample_rate: int = 16000,
    silence_seconds: float = 1.5,
    max_record_seconds: float = 20.0,
    silence_threshold: float = 500.0,
    output_path: str | Path = DEFAULT_INPUT_WAV,
    logger: logging.Logger | None = None,
) -> RecordingResult:
    """Record PCM chunks from a source and write a mono int16 WAV file."""

    return Recorder(
        source,
        sample_rate=sample_rate,
        silence_seconds=silence_seconds,
        max_record_seconds=max_record_seconds,
        silence_threshold=silence_threshold,
        output_path=output_path,
        logger=logger,
    ).record()


def _validate_pcm_chunk(chunk: bytes) -> None:
    if len(chunk) % SAMPLE_WIDTH_BYTES != 0:
        raise ValueError("PCM chunks must contain complete int16 samples")
