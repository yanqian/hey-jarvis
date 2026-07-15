"""WAV recording from PCM microphone chunks."""

from __future__ import annotations

import logging
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

from .silence import SAMPLE_WIDTH_BYTES, rms_level


DEFAULT_INPUT_WAV = Path("tmp/input.wav")
CHANNELS = 1
SILENCE_WINDOW_QUIET_RATIO = 0.8
SPEECH_LIKE_RMS_MULTIPLIER = 1.25
SECONDS_EPSILON = 1e-9


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
        vad_detector: Any | None = None,
        vad_enabled: bool = False,
        vad_speech_ratio: float = 0.50,
        vad_end_ratio: float = 0.25,
        hangover_seconds: float = 0.30,
        end_silence_seconds: float | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if silence_seconds <= 0:
            raise ValueError("silence_seconds must be positive")
        if max_record_seconds <= 0:
            raise ValueError("max_record_seconds must be positive")
        if max_record_seconds <= silence_seconds:
            raise ValueError("max_record_seconds must be greater than silence_seconds")
        if silence_threshold < 0:
            raise ValueError("silence_threshold must be non-negative")
        if not 0.0 <= vad_end_ratio <= 1.0 or not 0.0 <= vad_speech_ratio <= 1.0:
            raise ValueError("VAD ratios must be between 0.0 and 1.0")
        if vad_speech_ratio < vad_end_ratio:
            raise ValueError("vad_speech_ratio must be greater than or equal to vad_end_ratio")
        if hangover_seconds < 0:
            raise ValueError("hangover_seconds must be non-negative")
        resolved_end_silence = silence_seconds if end_silence_seconds is None else end_silence_seconds
        if resolved_end_silence <= 0:
            raise ValueError("end_silence_seconds must be positive")
        if max_record_seconds <= resolved_end_silence:
            raise ValueError("max_record_seconds must be greater than end_silence_seconds")
        if vad_enabled and vad_detector is None:
            raise ValueError("vad_detector is required when vad_enabled is true")

        self.source = source
        self.sample_rate = sample_rate
        self.silence_seconds = silence_seconds
        self.max_record_seconds = max_record_seconds
        self.silence_threshold = silence_threshold
        self.output_path = Path(output_path)
        self._logger = logger or logging.getLogger(__name__)
        self._source_iter: Iterable[bytes] | None = None
        self.vad_detector = vad_detector
        self.vad_enabled = vad_enabled
        self.vad_speech_ratio = vad_speech_ratio
        self.vad_end_ratio = vad_end_ratio
        self.hangover_seconds = hangover_seconds
        self.end_silence_seconds = resolved_end_silence

    def record(self) -> RecordingResult:
        """Record until consecutive silence, max duration, or source exhaustion."""

        chunks: list[bytes] = []
        duration_seconds = 0.0
        silence_window = _SilenceWindow(self.end_silence_seconds)
        speech_like_threshold = self.silence_threshold * SPEECH_LIKE_RMS_MULTIPLIER
        hangover_remaining = 0.0
        low_energy_high_vad_chunks = 0
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

            rms = rms_level(chunk)
            vad_ratio = None
            if self.vad_enabled:
                vad_result = self.vad_detector.analyze(chunk, self.sample_rate)
                vad_ratio = None if vad_result is None else vad_result.voiced_ratio
            energy_speech = rms > speech_like_threshold
            vad_speech = vad_ratio is not None and vad_ratio >= self.vad_speech_ratio
            # WebRTC can remain falsely voiced on post-speech room tone. VAD may
            # confirm energetic speech, but it cannot extend low-energy audio by
            # itself or the end-silence window may never complete.
            speech_like = energy_speech and (vad_ratio is None or vad_speech)
            if (
                vad_ratio is not None
                and vad_ratio > self.vad_end_ratio
                and rms <= self.silence_threshold
            ):
                low_energy_high_vad_chunks += 1
            if speech_like:
                silence_window.clear()
                hangover_remaining = self.hangover_seconds if self.vad_enabled else 0.0
            else:
                if hangover_remaining > 0:
                    hangover_remaining = max(0.0, hangover_remaining - chunk_seconds)
                    silence_window.clear()
                else:
                    # Low energy is authoritative for endpointing. A low VAD
                    # ratio cannot make high-energy noise quiet, while a false
                    # high VAD ratio cannot veto sustained RMS silence.
                    quiet = rms <= self.silence_threshold
                    silence_window.add(chunk_seconds, quiet=quiet)

            if duration_seconds >= self.max_record_seconds:
                stopped_by = "max_duration"
                break
            if silence_window.is_complete:
                stopped_by = "silence"
                break

        if self.vad_enabled:
            self._logger.info(
                "recording_endpoint stopped_by=%s duration=%.2fs chunks=%s "
                "low_energy_high_vad_chunks=%s",
                stopped_by,
                duration_seconds,
                len(chunks),
                low_energy_high_vad_chunks,
            )
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
    vad_detector: Any | None = None,
    vad_enabled: bool = False,
    vad_speech_ratio: float = 0.50,
    vad_end_ratio: float = 0.25,
    hangover_seconds: float = 0.30,
    end_silence_seconds: float | None = None,
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
        vad_detector=vad_detector,
        vad_enabled=vad_enabled,
        vad_speech_ratio=vad_speech_ratio,
        vad_end_ratio=vad_end_ratio,
        hangover_seconds=hangover_seconds,
        end_silence_seconds=end_silence_seconds,
    ).record()


def _validate_pcm_chunk(chunk: bytes) -> None:
    if len(chunk) % SAMPLE_WIDTH_BYTES != 0:
        raise ValueError("PCM chunks must contain complete int16 samples")


class _SilenceWindow:
    def __init__(self, target_seconds: float, quiet_ratio: float = SILENCE_WINDOW_QUIET_RATIO) -> None:
        self.target_seconds = target_seconds
        self.quiet_ratio = quiet_ratio
        self._chunks: deque[tuple[float, bool]] = deque()
        self._total_seconds = 0.0
        self._quiet_seconds = 0.0

    def clear(self) -> None:
        self._chunks.clear()
        self._total_seconds = 0.0
        self._quiet_seconds = 0.0

    def add(self, seconds: float, *, quiet: bool) -> None:
        if seconds <= 0:
            return
        self._chunks.append((seconds, quiet))
        self._total_seconds += seconds
        if quiet:
            self._quiet_seconds += seconds
        self._trim()

    @property
    def is_complete(self) -> bool:
        return (
            self._total_seconds + SECONDS_EPSILON >= self.target_seconds
            and self._quiet_seconds + SECONDS_EPSILON >= self.target_seconds * self.quiet_ratio
        )

    def _trim(self) -> None:
        excess_seconds = self._total_seconds - self.target_seconds
        while excess_seconds > 0 and self._chunks:
            seconds, quiet = self._chunks[0]
            if seconds <= excess_seconds:
                self._chunks.popleft()
                self._total_seconds -= seconds
                if quiet:
                    self._quiet_seconds -= seconds
                excess_seconds -= seconds
                continue

            self._chunks[0] = (seconds - excess_seconds, quiet)
            self._total_seconds -= excess_seconds
            if quiet:
                self._quiet_seconds -= excess_seconds
            break
