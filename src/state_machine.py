"""Voice-assistant state machine for one Hey Jarvis loop."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, MutableSequence, Protocol

from .config import Settings
from .openai_client import OpenAIClientError
from .recorder import DEFAULT_INPUT_WAV, RecordingResult, record_to_wav
from .tools import answer_with_tools
from .wake_word import pcm_rms_and_peak


DEFAULT_OUTPUT_MP3 = Path("tmp/output.mp3")


class AssistantState(Enum):
    WAIT_WAKE = "WAIT_WAKE"
    ACK_PLAYING = "ACK_PLAYING"
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
    error: str | None = None


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

        if self.settings.wake_acknowledgement_enabled:
            self._set_state(AssistantState.ACK_PLAYING)
            self.player.play(self.settings.wake_acknowledgement_audio_path)
            self._logger.info(
                "State ACK_PLAYING: played wake acknowledgement from %s",
                self.settings.wake_acknowledgement_audio_path,
            )
            self._drain_wake_acknowledgement_audio()

        self._set_state(AssistantState.RECORDING)
        recording = self._record_question()
        self._logger.info(
            "State RECORDING: wrote %s chunks to %s; stopped_by=%s",
            recording.chunks_recorded,
            recording.path,
            recording.stopped_by,
        )

        self._set_state(AssistantState.TRANSCRIBE)
        try:
            transcription = self.openai_client.transcribe_audio(str(recording.path))
        except OpenAIClientError as exc:
            return self._recover_from_openai_error(recording, exc)
        self._logger.info("State TRANSCRIBE: received transcription")

        self._set_state(AssistantState.ASK_OPENAI)
        try:
            answer, tool_route, tool_result = answer_with_tools(
                transcription,
                chat_client=self.openai_client,
                history=self.history,
                tools_enabled=self.settings.enable_tools,
            )
        except OpenAIClientError as exc:
            return self._recover_from_openai_error(recording, exc, transcription=transcription)
        if self.settings.tool_router_debug:
            self._logger.info(
                "Tool router debug: route=%s tool=%s params=%s reason=%s",
                tool_route.category,
                tool_route.tool_name,
                dict(tool_route.params),
                tool_route.reason,
            )
        if tool_result is None:
            self._logger.info("State ASK_OPENAI: received assistant answer")
        else:
            self._logger.info(
                "State ASK_OPENAI: tool route=%s status=%s summary=%s",
                tool_route.category,
                tool_result.status,
                tool_result.summary,
            )

        self._set_state(AssistantState.TTS)
        try:
            self.openai_client.text_to_speech(answer, str(self.output_path))
        except OpenAIClientError as exc:
            return self._recover_from_openai_error(
                recording,
                exc,
                transcription=transcription,
                answer=answer,
            )
        self._logger.info("State TTS: wrote synthesized speech to %s", self.output_path)

        self._set_state(AssistantState.PLAYING)
        self.player.play(self.output_path)
        self._logger.info("State PLAYING: playback finished")

        self._set_state(AssistantState.WAIT_WAKE)
        self._drain_post_playback_audio()
        self._logger.info("State WAIT_WAKE: ready for the next wake word")
        return AssistantLoopResult(
            recording_path=recording.path,
            output_path=self.output_path,
            transcription=transcription,
            answer=answer,
            final_state=self.state,
        )

    def _recover_from_openai_error(
        self,
        recording: RecordingResult,
        exc: OpenAIClientError,
        *,
        transcription: str = "",
        answer: str = "",
    ) -> AssistantLoopResult:
        self._logger.error("Recoverable OpenAI error in state %s: %s", self.state.value, exc)
        self._set_state(AssistantState.WAIT_WAKE)
        self._logger.info("State WAIT_WAKE: ready for the next wake word")
        return AssistantLoopResult(
            recording_path=recording.path,
            output_path=self.output_path,
            transcription=transcription,
            answer=answer,
            final_state=self.state,
            error=str(exc),
        )

    def _wait_for_wake_word(self) -> None:
        consecutive_detections = 0
        required_detections = max(1, self.settings.wake_confirmation_frames)
        while True:
            chunk = self.audio_source.read_chunk()
            if getattr(self.audio_source, "last_overflowed", False):
                consecutive_detections = 0
                self._logger.info("State WAIT_WAKE: ignoring overflowed microphone chunk for wake detection")
                continue
            if self._debug_or_detect_wake_word(chunk):
                consecutive_detections += 1
                if consecutive_detections >= required_detections:
                    self._logger.info("State WAIT_WAKE: wake word detected")
                    return
                self._logger.info(
                    "State WAIT_WAKE: wake word candidate %s/%s",
                    consecutive_detections,
                    required_detections,
                )
            else:
                consecutive_detections = 0

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

    def _drain_wake_acknowledgement_audio(self) -> None:
        drain_seconds = self.settings.wake_acknowledgement_drain_seconds
        if drain_seconds <= 0:
            return

        minimum_chunk_seconds = 1.0 / self.settings.sample_rate
        expected_frame_seconds = _detector_frame_seconds(self.wake_detector, self.settings.sample_rate)
        max_chunks = max(1, math.ceil(drain_seconds / expected_frame_seconds))
        drained_seconds = 0.0
        drained_chunks = 0

        self._logger.info(
            "State ACK_PLAYING: draining acknowledgement microphone residue for %.2fs",
            drain_seconds,
        )
        while drained_chunks < max_chunks and drained_seconds < drain_seconds:
            chunk = self.audio_source.read_chunk()
            drained_chunks += 1
            drained_seconds += max(_chunk_duration_seconds(chunk, self.settings.sample_rate), minimum_chunk_seconds)

        self._logger.info(
            "State ACK_PLAYING: discarded %s acknowledgement microphone chunks",
            drained_chunks,
        )

    def _drain_post_playback_audio(self) -> None:
        cooldown_seconds = self.settings.post_playback_wake_cooldown_seconds
        quiet_seconds_required = self.settings.post_playback_quiet_seconds
        max_suppression_seconds = self.settings.post_playback_max_suppression_seconds
        if cooldown_seconds <= 0 and quiet_seconds_required <= 0:
            return

        minimum_chunk_seconds = 1.0 / self.settings.sample_rate
        expected_frame_seconds = _detector_frame_seconds(self.wake_detector, self.settings.sample_rate)
        max_chunks = max(1, math.ceil(cooldown_seconds / expected_frame_seconds))
        drained_seconds = 0.0
        drained_chunks = 0

        self._logger.info(
            "State WAIT_WAKE: suppressing post-playback wake detection for %.2fs",
            cooldown_seconds,
        )
        while drained_chunks < max_chunks and drained_seconds < cooldown_seconds:
            chunk = self.audio_source.read_chunk()
            drained_chunks += 1
            drained_seconds += max(_chunk_duration_seconds(chunk, self.settings.sample_rate), minimum_chunk_seconds)

        self._logger.info(
            "State WAIT_WAKE: discarded %s post-playback microphone chunks",
            drained_chunks,
        )
        self._wait_for_post_playback_quiet(
            drained_seconds=drained_seconds,
            minimum_chunk_seconds=minimum_chunk_seconds,
        )

    def _wait_for_post_playback_quiet(self, *, drained_seconds: float, minimum_chunk_seconds: float) -> None:
        quiet_seconds_required = self.settings.post_playback_quiet_seconds
        if quiet_seconds_required <= 0:
            return

        max_suppression_seconds = self.settings.post_playback_max_suppression_seconds
        quiet_seconds = 0.0
        suppressed_chunks = 0
        max_scores: list[float] = []
        self._logger.info(
            "State WAIT_WAKE: waiting for %.2fs of post-playback quiet audio",
            quiet_seconds_required,
        )

        while quiet_seconds < quiet_seconds_required:
            if max_suppression_seconds > 0 and drained_seconds >= max_suppression_seconds:
                self._logger.warning(
                    "State WAIT_WAKE: post-playback quiet gate reached %.2fs maximum suppression before quiet",
                    max_suppression_seconds,
                )
                break

            chunk = self.audio_source.read_chunk()
            chunk_seconds = max(_chunk_duration_seconds(chunk, self.settings.sample_rate), minimum_chunk_seconds)
            drained_seconds += chunk_seconds
            suppressed_chunks += 1

            overflowed = bool(getattr(self.audio_source, "last_overflowed", False))
            score = self._suppressed_wake_score(chunk, overflowed=overflowed)
            if score is not None:
                max_scores.append(score)
            rms, _ = pcm_rms_and_peak(chunk)
            wake_score_is_quiet = score is None or score < self.settings.wake_threshold
            if not overflowed and rms <= self.settings.post_playback_quiet_rms and wake_score_is_quiet:
                quiet_seconds += chunk_seconds
            else:
                quiet_seconds = 0.0

        max_score = max(max_scores, default=0.0)
        self._logger.info(
            "State WAIT_WAKE: post-playback quiet gate consumed %s chunks; quiet=%.2fs max_suppressed_score=%.9f",
            suppressed_chunks,
            quiet_seconds,
            max_score,
        )

    def _suppressed_wake_score(self, chunk: bytes, *, overflowed: bool) -> float | None:
        if overflowed:
            self._logger.info("State WAIT_WAKE: suppressing overflowed post-playback microphone chunk")
            return None

        score_method = getattr(self.wake_detector, "score", None)
        if score_method is not None:
            score = float(score_method(chunk))
        else:
            score = 1.0 if self.wake_detector.detect(chunk) else 0.0
        return score

    def _set_state(self, next_state: AssistantState) -> None:
        if self.state == next_state:
            return
        self._logger.info("Transition %s -> %s", self.state.value, next_state.value)
        self.state = next_state


def _overflow_value(audio_source: object) -> str:
    return _bool_text(bool(getattr(audio_source, "last_overflowed", False)))


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _chunk_duration_seconds(pcm_chunk: bytes, sample_rate: int) -> float:
    if sample_rate <= 0 or not pcm_chunk:
        return 0.0
    return len(pcm_chunk) / (sample_rate * 2)


def _detector_frame_seconds(wake_detector: object, sample_rate: int) -> float:
    frame_length = int(getattr(wake_detector, "frame_length", 0) or 0)
    if sample_rate <= 0 or frame_length <= 0:
        return 0.08
    return frame_length / sample_rate
