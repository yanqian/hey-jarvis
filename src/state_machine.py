"""Voice-assistant state machine for one Hey Jarvis loop."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, MutableSequence, Protocol

from .config import Settings
from .recorder import DEFAULT_INPUT_WAV, RecordingResult, record_to_wav
from .wake_word import pcm_rms_and_peak


DEFAULT_OUTPUT_MP3 = Path("tmp/output.mp3")


class AssistantState(Enum):
    WAIT_WAKE = "WAIT_WAKE"
    RECORDING = "RECORDING"
    TRANSCRIBE = "TRANSCRIBE"
    ASK_OPENAI = "ASK_OPENAI"
    TTS = "TTS"
    PLAYING = "PLAYING"


class ChunkSource(Protocol):
    def read_chunk(self) -> bytes:
        """Read one int16 PCM chunk."""


class WakeDetector(Protocol):
    def detect(self, pcm_chunk: bytes) -> bool:
        """Return true when the wake word is detected."""

    def score(self, pcm_chunk: bytes) -> float:
        """Return a wake-word score for debug logging."""


class AssistantClient(Protocol):
    def transcribe_audio(self, path: str) -> str:
        """Transcribe a recorded WAV file."""

    def ask_chatgpt(self, text: str, history: MutableSequence[dict[str, str]]) -> str:
        """Ask the assistant model and update history."""

    def text_to_speech(self, text: str, output_path: str) -> None:
        """Write synthesized speech to output_path."""


class AudioPlayer(Protocol):
    def play(self, path: str | Path) -> None:
        """Play an audio file."""


@dataclass(frozen=True)
class AssistantLoopResult:
    recording_path: Path
    output_path: Path
    transcription: str
    answer: str
    final_state: AssistantState


class VoiceAssistantStateMachine:
    """Run the WAIT_WAKE to PLAYING flow and return to wake listening."""

    def __init__(
        self,
        *,
        settings: Settings,
        audio_source: ChunkSource,
        wake_detector: WakeDetector,
        openai_client: AssistantClient,
        player: AudioPlayer,
        history: MutableSequence[dict[str, str]] | None = None,
        record_audio: Any = record_to_wav,
        input_path: str | Path = DEFAULT_INPUT_WAV,
        output_path: str | Path = DEFAULT_OUTPUT_MP3,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = settings
        self.audio_source = audio_source
        self.wake_detector = wake_detector
        self.openai_client = openai_client
        self.player = player
        self.history = [] if history is None else history
        self.record_audio = record_audio
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.state = AssistantState.WAIT_WAKE
        self._logger = logger or logging.getLogger(__name__)

    def run_once(self) -> AssistantLoopResult:
        """Complete one question-answer loop and return to WAIT_WAKE."""

        self._set_state(AssistantState.WAIT_WAKE)
        self._logger.info("State WAIT_WAKE: listening for the %s wake word", self.settings.wake_phrase)
        self._wait_for_wake_word()

        self._set_state(AssistantState.RECORDING)
        recording = self._record_question()
        self._logger.info(
            "State RECORDING: wrote %s chunks to %s; stopped_by=%s",
            recording.chunks_recorded,
            recording.path,
            recording.stopped_by,
        )

        self._set_state(AssistantState.TRANSCRIBE)
        transcription = self.openai_client.transcribe_audio(str(recording.path))
        self._logger.info("State TRANSCRIBE: received transcription")

        self._set_state(AssistantState.ASK_OPENAI)
        answer = self.openai_client.ask_chatgpt(transcription, self.history)
        self._logger.info("State ASK_OPENAI: received assistant answer")

        self._set_state(AssistantState.TTS)
        self.openai_client.text_to_speech(answer, str(self.output_path))
        self._logger.info("State TTS: wrote synthesized speech to %s", self.output_path)

        self._set_state(AssistantState.PLAYING)
        self.player.play(self.output_path)
        self._logger.info("State PLAYING: playback finished")

        self._set_state(AssistantState.WAIT_WAKE)
        self._logger.info("State WAIT_WAKE: ready for the next wake word")
        return AssistantLoopResult(
            recording_path=recording.path,
            output_path=self.output_path,
            transcription=transcription,
            answer=answer,
            final_state=self.state,
        )

    def _wait_for_wake_word(self) -> None:
        while True:
            chunk = self.audio_source.read_chunk()
            if self._debug_or_detect_wake_word(chunk):
                self._logger.info("State WAIT_WAKE: wake word detected")
                return

    def _debug_or_detect_wake_word(self, chunk: bytes) -> bool:
        if not self.settings.wake_debug:
            return self.wake_detector.detect(chunk)

        score_method = getattr(self.wake_detector, "score", None)
        if score_method is None:
            detected = self.wake_detector.detect(chunk)
            self._logger.info(
                "Wake debug: rms=unavailable peak=unavailable overflow=%s score=unavailable threshold=%.3f detected=%s",
                _overflow_value(self.audio_source),
                self.settings.wake_threshold,
                _bool_text(detected),
            )
            return detected

        score = float(score_method(chunk))
        rms, peak = pcm_rms_and_peak(chunk)
        detected = score >= self.settings.wake_threshold
        self._logger.info(
            "Wake debug: rms=%.1f peak=%s overflow=%s score=%.9f threshold=%.9f detected=%s",
            rms,
            peak,
            _overflow_value(self.audio_source),
            score,
            self.settings.wake_threshold,
            _bool_text(detected),
        )
        return detected

    def _record_question(self) -> RecordingResult:
        return self.record_audio(
            self.audio_source,
            sample_rate=self.settings.sample_rate,
            silence_seconds=self.settings.silence_seconds,
            max_record_seconds=self.settings.max_record_seconds,
            output_path=self.input_path,
            logger=self._logger,
        )

    def _set_state(self, next_state: AssistantState) -> None:
        if self.state == next_state:
            return
        self._logger.info("Transition %s -> %s", self.state.value, next_state.value)
        self.state = next_state


def _overflow_value(audio_source: object) -> str:
    return _bool_text(bool(getattr(audio_source, "last_overflowed", False)))


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
