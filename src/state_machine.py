"""Voice-assistant state machine for one Hey Jarvis loop."""

from __future__ import annotations

import logging
import math
import re
import wave
from collections import deque
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import monotonic
from typing import Any, Callable, MutableSequence, Protocol, Sequence

from .config import Settings
from .openai_client import OpenAIClientError
from .recorder import DEFAULT_INPUT_WAV, RecordingResult, record_to_wav
from .tools import answer_with_tools
from .tools.providers import provider_config_from_settings
from .wake_word import pcm_rms_and_peak
from .vad import DisabledVad, VoiceActivityDetector


DEFAULT_OUTPUT_MP3 = Path("tmp/output.mp3")


class AssistantState(Enum):
    WAIT_WAKE = "WAIT_WAKE"
    ACK_PLAYING = "ACK_PLAYING"
    ARMED = "ARMED"
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
    cancelled: bool = False
    cancellation_reason: str | None = None


@dataclass(frozen=True)
class _TranscriptCancellationMatch:
    reason: str
    normalized_transcript: str
    match_mode: str


@dataclass(frozen=True)
class _ArmedChunk:
    pcm: bytes
    seconds: float
    rms: float
    peak: int
    overflowed: bool
    voiced: bool
    dynamic_threshold: float
    noise_floor: float
    energy_ok: bool
    vad_ratio: float | None
    vad_ok: bool
    baseline_ready: bool


@dataclass(frozen=True)
class _PostAckBoundaryResult:
    quiet_observed: bool
    suppressed_chunks: int
    preserved_chunks: tuple[bytes, ...]
    noise_seed_chunks: tuple[bytes, ...]
    max_rms: float
    max_peak: int
    overflow_chunks: int
    clipped_chunks: int
    timed_out: bool
    synchronized: bool = False


@dataclass(frozen=True)
class _AckPlaybackDrainResult:
    synchronized: bool
    preserved_chunks: tuple[bytes, ...] = ()
    noise_seed_chunks: tuple[bytes, ...] = ()
    drained_chunks: int = 0
    quarantined_overlap_chunks: int = 0


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
        vad_detector: VoiceActivityDetector | None = None,
        clock: Callable[[], float] | None = None,
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
        self.vad_detector = vad_detector or DisabledVad()
        self._clock = clock or monotonic

    def run_once(self) -> AssistantLoopResult:
        """Complete one question-answer loop and return to WAIT_WAKE."""

        self._set_state(AssistantState.WAIT_WAKE)
        self._logger.info("State WAIT_WAKE: listening for the %s wake word", self.settings.wake_phrase)
        self._wait_for_wake_word()

        if self.settings.wake_acknowledgement_enabled:
            self._set_state(AssistantState.ACK_PLAYING)
            ack_playback_drain = self._play_wake_acknowledgement()
            self._logger.info(
                "State ACK_PLAYING: played wake acknowledgement from %s",
                self.settings.wake_acknowledgement_audio_path,
            )
            post_ack_boundary = self._wait_for_post_ack_boundary(
                playback_drain=ack_playback_drain
            )
            if post_ack_boundary.timed_out and not post_ack_boundary.preserved_chunks:
                return self._cancel_to_wait_wake("no_speech_after_wake")
        else:
            post_ack_boundary = None

        self._set_state(AssistantState.ARMED)
        speech_start_chunks = self._wait_for_armed_speech(
            initial_pre_roll=() if post_ack_boundary is None else post_ack_boundary.preserved_chunks,
            initial_noise_seed=() if post_ack_boundary is None else post_ack_boundary.noise_seed_chunks,
            post_ack_boundary=post_ack_boundary,
        )
        if speech_start_chunks is None:
            return self._cancel_to_wait_wake("no_speech_after_wake")

        self._set_state(AssistantState.RECORDING)
        recording = self._record_question(initial_chunks=speech_start_chunks)
        self._logger.info(
            "State RECORDING: wrote %s chunks to %s; stopped_by=%s",
            recording.chunks_recorded,
            recording.path,
            recording.stopped_by,
        )
        recording_cancel_reason = self._recording_cancellation_reason(recording)
        if recording_cancel_reason is not None:
            return self._cancel_to_wait_wake(recording_cancel_reason, recording=recording)

        response_started_at = self._clock()
        self._set_state(AssistantState.TRANSCRIBE)
        stage_started_at = response_started_at
        try:
            transcription = self.openai_client.transcribe_audio(str(recording.path))
        except OpenAIClientError as exc:
            self._log_pipeline_stage("transcription", stage_started_at, response_started_at, status="error")
            if _is_empty_transcription_error(exc):
                return self._cancel_to_wait_wake("empty_transcript", recording=recording)
            return self._recover_from_openai_error(recording, exc)
        transcription_seconds = self._log_pipeline_stage(
            "transcription", stage_started_at, response_started_at
        )
        self._logger.info("State TRANSCRIBE: received transcription")
        transcription, acknowledgement_prefix_removed = self._remove_acknowledgement_prefix(transcription)
        if acknowledgement_prefix_removed:
            self._logger.info(
                "State TRANSCRIBE: removed configured acknowledgement prefix from mixed recording"
            )
        transcript_cancel_match = self._transcript_cancellation_match(transcription)
        if transcript_cancel_match is not None:
            self._logger.info(
                "State TRANSCRIBE: transcript cancellation normalized_transcript=%r match_mode=%s",
                transcript_cancel_match.normalized_transcript,
                transcript_cancel_match.match_mode,
            )
            return self._cancel_to_wait_wake(
                transcript_cancel_match.reason,
                recording=recording,
                transcription=transcription,
            )

        self._set_state(AssistantState.ASK_OPENAI)
        stage_started_at = self._clock()
        try:
            answer, tool_route, tool_result = answer_with_tools(
                transcription,
                chat_client=self.openai_client,
                history=self.history,
                tools_enabled=self.settings.enable_tools,
                naturalize_tool_answers=self.settings.tool_answer_naturalization,
                provider_config=provider_config_from_settings(self.settings),
            )
        except OpenAIClientError as exc:
            self._log_pipeline_stage("answer", stage_started_at, response_started_at, status="error")
            return self._recover_from_openai_error(recording, exc, transcription=transcription)
        response_route = "chat" if tool_result is None else tool_route.category
        answer_seconds = self._log_pipeline_stage(
            "answer",
            stage_started_at,
            response_started_at,
            route=response_route,
        )
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
            if tool_result.status == "error":
                self._logger.info(
                    "State ASK_OPENAI: tool route=%s status=%s summary=%s params=%s data=%s",
                    tool_route.category,
                    tool_result.status,
                    tool_result.summary,
                    dict(tool_route.params),
                    dict(tool_result.data),
                )
            else:
                self._logger.info(
                    "State ASK_OPENAI: tool route=%s status=%s summary=%s",
                    tool_route.category,
                    tool_result.status,
                    tool_result.summary,
                )

        self._set_state(AssistantState.TTS)
        stage_started_at = self._clock()
        try:
            self.openai_client.text_to_speech(answer, str(self.output_path))
        except OpenAIClientError as exc:
            self._log_pipeline_stage("tts", stage_started_at, response_started_at, status="error")
            return self._recover_from_openai_error(
                recording,
                exc,
                transcription=transcription,
                answer=answer,
            )
        tts_seconds = self._log_pipeline_stage("tts", stage_started_at, response_started_at)
        self._logger.info("State TTS: wrote synthesized speech to %s", self.output_path)

        self._set_state(AssistantState.PLAYING)
        stage_started_at = self._clock()
        ready_to_play_seconds = max(0.0, stage_started_at - response_started_at)
        self.player.play(self.output_path)
        playback_seconds = self._log_pipeline_stage("playback", stage_started_at, response_started_at)
        post_recording_total = max(0.0, self._clock() - response_started_at)
        self._logger.info(
            "response_timing recording=%.3fs transcription=%.3fs answer=%.3fs tts=%.3fs "
            "ready_to_play=%.3fs playback=%.3fs post_recording_total=%.3fs route=%s",
            recording.duration_seconds,
            transcription_seconds,
            answer_seconds,
            tts_seconds,
            ready_to_play_seconds,
            playback_seconds,
            post_recording_total,
            response_route,
        )
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

    def _log_pipeline_stage(
        self,
        stage: str,
        started_at: float,
        response_started_at: float,
        *,
        status: str = "success",
        route: str | None = None,
    ) -> float:
        finished_at = self._clock()
        duration = max(0.0, finished_at - started_at)
        elapsed = max(0.0, finished_at - response_started_at)
        route_text = "" if route is None else f" route={route}"
        self._logger.info(
            "pipeline_timing stage=%s status=%s duration=%.3fs post_recording_elapsed=%.3fs%s",
            stage,
            status,
            duration,
            elapsed,
            route_text,
        )
        return duration

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

    def _cancel_to_wait_wake(
        self,
        reason: str,
        *,
        recording: RecordingResult | None = None,
        transcription: str = "",
    ) -> AssistantLoopResult:
        self._logger.info("State %s: local cancellation reason=%s", self.state.value, reason)
        self._set_state(AssistantState.WAIT_WAKE)
        self._drain_post_cancellation_audio(reason=reason)
        self._logger.info("State WAIT_WAKE: ready for the next wake word")
        return AssistantLoopResult(
            recording_path=recording.path if recording is not None else self.input_path,
            output_path=self.output_path,
            transcription=transcription,
            answer="",
            final_state=self.state,
            cancelled=True,
            cancellation_reason=reason,
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

    def _wait_for_armed_speech(
        self,
        *,
        initial_pre_roll: Sequence[bytes] | None = None,
        initial_noise_seed: Sequence[bytes] | None = None,
        post_ack_boundary: _PostAckBoundaryResult | None = None,
    ) -> tuple[bytes, ...] | None:
        timeout_seconds = self.settings.armed_no_speech_timeout_seconds
        minimum_chunk_seconds = 1.0 / self.settings.sample_rate
        expected_frame_seconds = _detector_frame_seconds(self.wake_detector, self.settings.sample_rate)
        window_chunks_required = max(1, math.ceil(self.settings.armed_voice_window_seconds / expected_frame_seconds))
        voiced_chunks_required = max(1, math.ceil(window_chunks_required * self.settings.armed_voice_required_ratio))
        elapsed_seconds = 0.0
        chunks_checked = 0
        valid_chunks = 0
        overflow_chunks = 0
        voiced_chunks = 0
        vad_voiced_chunks = 0
        max_vad_ratio = 0.0
        last_vad_ok = not self.vad_detector.is_enabled
        max_rms = 0.0
        max_peak = 0
        noise_samples = [pcm_rms_and_peak(chunk)[0] for chunk in (initial_noise_seed or ())]
        noise_seed_count = len(noise_samples)
        post_ack_synchronized = bool(post_ack_boundary is not None and post_ack_boundary.synchronized)
        post_ack_quiet_observed = post_ack_boundary is None or post_ack_boundary.quiet_observed
        post_ack_boundary_ready = post_ack_quiet_observed or post_ack_synchronized
        protected_post_ack = (
            post_ack_boundary is not None
            and self.settings.ack_guard_enabled
            and not post_ack_synchronized
        )
        baseline_ready_after: float | None = None
        baseline_ready_at_chunks: int | None = None
        voiced_window: deque[bool] = deque(maxlen=window_chunks_required)
        pre_roll: deque[_ArmedChunk] = deque()
        pre_roll_seconds = 0.0
        for initial_chunk in initial_pre_roll or ():
            initial_seconds = max(
                _chunk_duration_seconds(initial_chunk, self.settings.sample_rate),
                minimum_chunk_seconds,
            )
            initial_rms, initial_peak = pcm_rms_and_peak(initial_chunk)
            pre_roll.append(
                _ArmedChunk(
                    pcm=initial_chunk,
                    seconds=initial_seconds,
                    rms=initial_rms,
                    peak=initial_peak,
                    overflowed=False,
                    voiced=False,
                    dynamic_threshold=self.settings.armed_min_rms,
                    noise_floor=0.0,
                    energy_ok=False,
                    vad_ratio=None,
                    vad_ok=not self.vad_detector.is_enabled,
                    baseline_ready=False,
                )
            )
            pre_roll_seconds += initial_seconds
        pre_roll_seconds = _trim_pre_roll(
            pre_roll,
            pre_roll_seconds=pre_roll_seconds,
            max_seconds=self.settings.armed_pre_roll_seconds,
        )
        self._logger.info(
            (
                "State ARMED: waiting up to %.2fs for speech; min_rms=%.1f "
                "snr_multiplier=%.2f voiced_window=%s/%s pre_roll=%.2fs"
            ),
            timeout_seconds,
            self.settings.armed_min_rms,
            self.settings.armed_snr_multiplier,
            voiced_chunks_required,
            window_chunks_required,
            self.settings.armed_pre_roll_seconds,
        )

        while elapsed_seconds < timeout_seconds:
            chunk = self.audio_source.read_chunk()
            chunks_checked += 1
            chunk_seconds = max(_chunk_duration_seconds(chunk, self.settings.sample_rate), minimum_chunk_seconds)
            elapsed_seconds += chunk_seconds
            rms, peak = pcm_rms_and_peak(chunk)
            max_rms = max(max_rms, rms)
            max_peak = max(max_peak, peak)
            overflowed = bool(getattr(self.audio_source, "last_overflowed", False))
            clipped = peak >= self.settings.armed_clip_reject_peak
            noise_floor = _noise_floor(noise_samples)
            dynamic_threshold = max(
                self.settings.armed_min_rms,
                noise_floor * self.settings.armed_snr_multiplier,
            )
            energy_ok = rms >= dynamic_threshold
            vad_result = self.vad_detector.analyze(chunk, self.settings.sample_rate)
            vad_ratio = None if vad_result is None else vad_result.voiced_ratio
            if vad_ratio is not None:
                max_vad_ratio = max(max_vad_ratio, vad_ratio)
            vad_ok = (
                not self.vad_detector.is_enabled
                or (
                    vad_result is not None
                    and vad_ratio is not None
                    and vad_ratio >= self.settings.armed_vad_required_ratio
                    and vad_result.voiced_frames >= self.settings.armed_vad_min_frames
                )
            )
            last_vad_ok = vad_ok
            baseline_ready = (
                elapsed_seconds >= self.settings.armed_baseline_seconds
                and valid_chunks + (0 if overflowed or clipped else 1)
                >= self.settings.armed_baseline_min_chunks
            )
            baseline_gate_open = baseline_ready or not self.settings.armed_require_baseline
            candidate_voice = not overflowed and not clipped and energy_ok and vad_ok
            voiced = candidate_voice and (
                baseline_gate_open or not self.vad_detector.is_enabled
            )
            armed_chunk = _ArmedChunk(
                pcm=chunk,
                seconds=chunk_seconds,
                rms=rms,
                peak=peak,
                overflowed=overflowed,
                voiced=voiced,
                dynamic_threshold=dynamic_threshold,
                noise_floor=noise_floor,
                energy_ok=energy_ok,
                vad_ratio=vad_ratio,
                vad_ok=vad_ok,
                baseline_ready=baseline_ready,
            )
            if not (protected_post_ack and overflowed):
                pre_roll.append(armed_chunk)
                pre_roll_seconds += chunk_seconds
                pre_roll_seconds = _trim_pre_roll(
                    pre_roll,
                    pre_roll_seconds=pre_roll_seconds,
                    max_seconds=self.settings.armed_pre_roll_seconds,
                )

            if overflowed:
                overflow_chunks += 1
                self._logger.info("State ARMED: ignoring overflowed microphone chunk")
                voiced_window.append(False)
                continue
            if not clipped:
                valid_chunks += 1
            voiced_window.append(voiced)
            if voiced:
                voiced_chunks += 1
                if vad_ratio is not None:
                    vad_voiced_chunks += 1
            elif not clipped and not candidate_voice:
                noise_samples.append(rms)

            window_voiced_chunks = sum(1 for item in voiced_window if item)
            baseline_ready = (
                elapsed_seconds >= self.settings.armed_baseline_seconds
                and valid_chunks >= self.settings.armed_baseline_min_chunks
                and post_ack_boundary_ready
                and (
                    post_ack_boundary is None
                    or not self.settings.ack_guard_enabled
                    or bool(noise_samples)
                )
            )
            if baseline_ready and baseline_ready_after is None:
                baseline_ready_after = elapsed_seconds
                baseline_ready_at_chunks = valid_chunks
            baseline_gate_open = baseline_ready or not self.settings.armed_require_baseline
            latest_chunk_ready = voiced or not self.settings.armed_last_chunk_must_be_voiced
            if (
                baseline_gate_open
                and latest_chunk_ready
                and len(voiced_window) >= window_chunks_required
                and window_voiced_chunks >= voiced_chunks_required
            ):
                pre_roll_chunks = tuple(item.pcm for item in pre_roll if item.pcm)
                pre_roll_overflow_chunks = sum(1 for item in pre_roll if item.overflowed)
                pre_roll_ms = int(round(sum(item.seconds for item in pre_roll) * 1000))
                self._logger.info(
                    (
                        "armed_trigger after=%.2fs duration_pcm=%.2fs chunks=%s valid_chunks=%s "
                        "rms=%.1f peak=%s overflow=%s max_rms=%.1f max_peak=%s "
                        "overflow_chunks=%s voiced_chunks=%s threshold=%.1f "
                        "dynamic_threshold=%.1f noise_floor=%.1f noise_floor_has_samples=%s "
                        "energy_ok=%s vad_ratio=%s vad_ok=%s "
                        "noise_seed_count=%s baseline_ready=%s baseline_ready_after=%.2f "
                        "baseline_ready_at_chunks=%s baseline_chunks=%s baseline_seconds=%.2f "
                        "post_ack_quiet_observed=%s post_ack_synchronized=%s post_ack_boundary_ready=%s "
                        "post_ack_suppressed_chunks=%s "
                        "post_ack_max_rms=%.1f post_ack_max_peak=%s post_ack_overflow_chunks=%s "
                        "post_ack_clipped_chunks=%s voiced_window=%s/%s "
                        "pre_roll_ms=%s pre_roll_chunks=%s pre_roll_overflow_chunks=%s "
                        "result=recording_started"
                    ),
                    elapsed_seconds,
                    elapsed_seconds,
                    chunks_checked,
                    valid_chunks,
                    rms,
                    peak,
                    _bool_text(overflowed),
                    max_rms,
                    max_peak,
                    overflow_chunks,
                    voiced_chunks,
                    self.settings.armed_min_rms,
                    dynamic_threshold,
                    noise_floor,
                    _bool_text(bool(noise_samples)),
                    _bool_text(energy_ok),
                    _format_vad_ratio(vad_ratio),
                    _bool_text(vad_ok),
                    noise_seed_count,
                    _bool_text(baseline_ready),
                    baseline_ready_after or elapsed_seconds,
                    baseline_ready_at_chunks or valid_chunks,
                    valid_chunks,
                    elapsed_seconds,
                    _bool_text(post_ack_quiet_observed),
                    _bool_text(post_ack_synchronized),
                    _bool_text(post_ack_boundary_ready),
                    0 if post_ack_boundary is None else post_ack_boundary.suppressed_chunks,
                    0.0 if post_ack_boundary is None else post_ack_boundary.max_rms,
                    0 if post_ack_boundary is None else post_ack_boundary.max_peak,
                    0 if post_ack_boundary is None else post_ack_boundary.overflow_chunks,
                    0 if post_ack_boundary is None else post_ack_boundary.clipped_chunks,
                    window_voiced_chunks,
                    len(voiced_window),
                    pre_roll_ms,
                    len(pre_roll_chunks),
                    pre_roll_overflow_chunks,
                )
                return pre_roll_chunks or (chunk,)

        final_noise_floor = _noise_floor(noise_samples)
        final_dynamic_threshold = max(
            self.settings.armed_min_rms,
            final_noise_floor * self.settings.armed_snr_multiplier,
        )
        final_baseline_ready = (
            elapsed_seconds >= self.settings.armed_baseline_seconds
            and valid_chunks >= self.settings.armed_baseline_min_chunks
            and post_ack_boundary_ready
            and (
                post_ack_boundary is None
                or not self.settings.ack_guard_enabled
                or bool(noise_samples)
            )
        )
        self._logger.info(
            (
                "armed_summary duration_pcm=%.2fs chunks=%s valid_chunks=%s max_rms=%.1f max_peak=%s "
                "overflow_chunks=%s voiced_chunks=%s threshold=%.1f dynamic_threshold=%.1f "
                "noise_floor=%.1f noise_floor_has_samples=%s noise_seed_count=%s "
                "vad_ok=%s max_vad_ratio=%s vad_voiced_chunks=%s "
                "baseline_ready=%s baseline_ready_after=%s baseline_ready_at_chunks=%s "
                "baseline_chunks=%s baseline_seconds=%.2f post_ack_quiet_observed=%s "
                "post_ack_synchronized=%s post_ack_boundary_ready=%s "
                "post_ack_suppressed_chunks=%s post_ack_max_rms=%.1f post_ack_max_peak=%s "
                "post_ack_overflow_chunks=%s post_ack_clipped_chunks=%s "
                "pre_roll_ms=%s pre_roll_chunks=%s pre_roll_overflow_chunks=%s "
                "result=no_speech_timeout"
            ),
            elapsed_seconds,
            chunks_checked,
            valid_chunks,
            max_rms,
            max_peak,
            overflow_chunks,
            voiced_chunks,
            self.settings.armed_min_rms,
            final_dynamic_threshold,
            final_noise_floor,
            _bool_text(bool(noise_samples)),
            noise_seed_count,
            _bool_text(last_vad_ok),
            _format_vad_ratio(max_vad_ratio if self.vad_detector.is_enabled else None),
            vad_voiced_chunks,
            _bool_text(final_baseline_ready),
            "unset" if baseline_ready_after is None else f"{baseline_ready_after:.2f}",
            "unset" if baseline_ready_at_chunks is None else str(baseline_ready_at_chunks),
            valid_chunks,
            elapsed_seconds,
            _bool_text(post_ack_quiet_observed),
            _bool_text(post_ack_synchronized),
            _bool_text(post_ack_boundary_ready),
            0 if post_ack_boundary is None else post_ack_boundary.suppressed_chunks,
            0.0 if post_ack_boundary is None else post_ack_boundary.max_rms,
            0 if post_ack_boundary is None else post_ack_boundary.max_peak,
            0 if post_ack_boundary is None else post_ack_boundary.overflow_chunks,
            0 if post_ack_boundary is None else post_ack_boundary.clipped_chunks,
            int(round(sum(item.seconds for item in pre_roll) * 1000)),
            sum(1 for item in pre_roll if item.pcm),
            sum(1 for item in pre_roll if item.overflowed),
        )
        return None

    def _play_wake_acknowledgement(self) -> _AckPlaybackDrainResult:
        start_playback = getattr(self.player, "start_acknowledgement", None)
        if not callable(start_playback):
            start_playback = getattr(self.player, "start", None)
        if not callable(start_playback):
            self.player.play(self.settings.wake_acknowledgement_audio_path)
            self._logger.info(
                "State ACK_PLAYING: synchronous playback fallback; microphone drain unavailable"
            )
            return _AckPlaybackDrainResult(synchronized=False)

        drained_chunks = 0
        overflow_chunks = 0
        clipped_chunks = 0
        max_rms = 0.0
        max_peak = 0
        retained_chunks: deque[tuple[bytes, float, float, int, bool]] = deque()
        retained_seconds = 0.0
        failure_stage = "start"
        try:
            handle = start_playback(self.settings.wake_acknowledgement_audio_path)
        except Exception:
            self._log_ack_playback_drain(
                drained_chunks,
                overflow_chunks,
                clipped_chunks,
                max_rms,
                max_peak,
                completed=False,
                failure_stage=failure_stage,
                synchronized=False,
            )
            raise

        try:
            failure_stage = "drain"
            while handle.poll() is None:
                chunk = self.audio_source.read_chunk()
                drained_chunks += 1
                rms, peak = pcm_rms_and_peak(chunk)
                max_rms = max(max_rms, rms)
                max_peak = max(max_peak, peak)
                overflowed = bool(getattr(self.audio_source, "last_overflowed", False))
                overflow_chunks += int(overflowed)
                clipped_chunks += int(peak >= self.settings.armed_clip_reject_peak)
                chunk_seconds = max(
                    _chunk_duration_seconds(chunk, self.settings.sample_rate),
                    1.0 / self.settings.sample_rate,
                )
                if not overflowed:
                    retained_chunks.append(
                        (
                            chunk,
                            chunk_seconds,
                            rms,
                            peak,
                            peak >= self.settings.armed_clip_reject_peak,
                        )
                    )
                    retained_seconds += chunk_seconds
                    while retained_chunks and retained_seconds > self.settings.armed_pre_roll_seconds:
                        retained_seconds -= retained_chunks.popleft()[1]
        except Exception:
            try:
                handle.wait()
            except Exception as join_exc:
                self._logger.error(
                    "State ACK_PLAYING: playback join also failed after drain error: %s",
                    join_exc,
                )
            self._log_ack_playback_drain(
                drained_chunks,
                overflow_chunks,
                clipped_chunks,
                max_rms,
                max_peak,
                completed=False,
                failure_stage=failure_stage,
                synchronized=False,
            )
            raise

        failure_stage = "wait"
        try:
            handle.wait()
        except Exception:
            self._log_ack_playback_drain(
                drained_chunks,
                overflow_chunks,
                clipped_chunks,
                max_rms,
                max_peak,
                completed=False,
                failure_stage=failure_stage,
                synchronized=False,
            )
            raise

        synchronized = overflow_chunks == 0
        quarantined_overlap_chunks = 0
        if retained_chunks:
            retained_seconds -= retained_chunks[-1][1]
            retained_chunks.pop()
            quarantined_overlap_chunks = 1
        preserved_chunks = tuple(item[0] for item in retained_chunks)
        noise_seed_chunks = tuple(
            item[0]
            for item in retained_chunks
            if not item[4] and item[2] <= self.settings.ack_guard_quiet_rms
        )
        self._log_ack_playback_drain(
            drained_chunks,
            overflow_chunks,
            clipped_chunks,
            max_rms,
            max_peak,
            completed=True,
            failure_stage="none",
            synchronized=synchronized,
        )
        self._logger.info(
            "State ACK_PLAYING: playback handoff preserved_chunks=%s preserved_ms=%s "
            "noise_seed_count=%s quarantined_overlap_chunks=%s",
            len(preserved_chunks),
            int(round(retained_seconds * 1000)),
            len(noise_seed_chunks),
            quarantined_overlap_chunks,
        )
        return _AckPlaybackDrainResult(
            synchronized=synchronized,
            preserved_chunks=preserved_chunks if synchronized else (),
            noise_seed_chunks=noise_seed_chunks if synchronized else (),
            drained_chunks=drained_chunks,
            quarantined_overlap_chunks=quarantined_overlap_chunks,
        )

    def _log_ack_playback_drain(
        self,
        drained_chunks: int,
        overflow_chunks: int,
        clipped_chunks: int,
        max_rms: float,
        max_peak: int,
        *,
        completed: bool,
        failure_stage: str,
        synchronized: bool,
    ) -> None:
        self._logger.info(
            (
                "State ACK_PLAYING: playback microphone drain drained_chunks=%s "
                "overflow_chunks=%s clipped_chunks=%s max_rms=%.1f max_peak=%s "
                "completed=%s failure_stage=%s synchronized=%s"
            ),
            drained_chunks,
            overflow_chunks,
            clipped_chunks,
            max_rms,
            max_peak,
            _bool_text(completed),
            failure_stage,
            _bool_text(synchronized),
        )

    def _record_question(self, *, initial_chunks: Sequence[bytes] | None = None) -> RecordingResult:
        source = self.audio_source
        if initial_chunks:
            source = _PreloadedChunkSource(initial_chunks, self.audio_source)
        return self.record_audio(
            source,
            sample_rate=self.settings.sample_rate,
            silence_seconds=self.settings.silence_seconds,
            max_record_seconds=self.settings.max_record_seconds,
            silence_threshold=self.settings.recording_silence_rms,
            output_path=self.input_path,
            logger=self._logger,
            vad_detector=self.vad_detector if self.settings.recording_vad_enabled else None,
            vad_enabled=self.settings.recording_vad_enabled,
            vad_speech_ratio=self.settings.recording_vad_speech_ratio,
            vad_end_ratio=self.settings.recording_vad_end_ratio,
            hangover_seconds=self.settings.recording_hangover_seconds,
            end_silence_seconds=self.settings.recording_end_silence_seconds,
        )

    def _recording_cancellation_reason(self, recording: RecordingResult) -> str | None:
        if recording.chunks_recorded <= 0:
            return "empty_recording"
        if recording.duration_seconds < self.settings.min_valid_speech_seconds:
            return "too_short_recording"

        voice_duration = _wav_voice_duration_seconds(
            recording.path,
            sample_rate=self.settings.sample_rate,
            voice_rms=self.settings.armed_min_rms,
        )
        if voice_duration < self.settings.min_valid_speech_seconds:
            return "silent_recording"
        return None

    def _remove_acknowledgement_prefix(self, transcription: str) -> tuple[str, bool]:
        """Remove only an exact leading configured ACK when useful text follows it."""

        text = transcription.strip()
        acknowledgement = self.settings.wake_acknowledgement_text.strip()
        if not text or not acknowledgement:
            return transcription, False
        if text.startswith(acknowledgement):
            remainder = text[len(acknowledgement) :]
        elif acknowledgement == "嗯" and re.match(r"^[nN](?=[\u3400-\u9fff])", text):
            remainder = text[1:]
        else:
            return transcription, False
        remainder = re.sub(r"^[\s,，。.!！?？:：;；、]+", "", remainder).strip()
        if len(_normalize_transcript(remainder).replace(" ", "")) < self.settings.min_transcript_length:
            return transcription, False
        return remainder, True

    def _transcript_cancellation_match(self, transcription: str) -> _TranscriptCancellationMatch | None:
        normalized = _normalize_transcript(transcription)
        compact = normalized.replace(" ", "")
        if not compact:
            return _TranscriptCancellationMatch("empty_transcript", normalized, "empty")
        if compact in _FILLER_TRANSCRIPTS:
            return _TranscriptCancellationMatch("filler_transcript", normalized, "filler")

        for phrase in self.settings.cancel_phrases:
            normalized_phrase = _normalize_transcript(phrase)
            phrase_compact = normalized_phrase.replace(" ", "")
            if not phrase_compact:
                continue
            if normalized == normalized_phrase or compact == phrase_compact:
                return _TranscriptCancellationMatch("cancel_phrase", normalized, "exact")
            if _is_noisy_cancel_variant(
                compact,
                phrase_compact,
                self.settings.cancel_phrases,
            ):
                return _TranscriptCancellationMatch("cancel_phrase", normalized, "noisy_suffix")
        if _is_colloquial_chinese_cancel_variant(compact):
            return _TranscriptCancellationMatch("cancel_phrase", normalized, "colloquial_variant")
        if len(compact) < self.settings.min_transcript_length:
            return _TranscriptCancellationMatch("short_transcript", normalized, "short")
        if len(compact) <= _SHORT_TRANSCRIPT_DIAGNOSTIC_MAX_COMPACT_LENGTH:
            self._logger.info(
                "State TRANSCRIBE: transcript cancellation check normalized_transcript=%r compact_transcript=%r match_decision=not_cancelled",
                normalized,
                compact,
            )
        return None

    def _wait_for_post_ack_boundary(
        self,
        *,
        playback_drain: _AckPlaybackDrainResult | None = None,
    ) -> _PostAckBoundaryResult:
        if not self.settings.ack_guard_enabled:
            self._drain_wake_acknowledgement_audio()
            return _PostAckBoundaryResult(True, 0, (), (), 0.0, 0, 0, 0, False)

        if playback_drain is not None and playback_drain.synchronized:
            self._logger.info(
                "State ACK_PLAYING: synchronized live handoff; buffered playback tail enters protected "
                "ARMED pre-roll and requires post-playback voice plus useful noise-floor evidence"
            )
            return _PostAckBoundaryResult(
                quiet_observed=False,
                suppressed_chunks=0,
                preserved_chunks=playback_drain.preserved_chunks,
                noise_seed_chunks=playback_drain.noise_seed_chunks,
                max_rms=0.0,
                max_peak=0,
                overflow_chunks=0,
                clipped_chunks=0,
                timed_out=False,
                synchronized=True,
            )

        quiet_required = self.settings.ack_guard_min_quiet_seconds
        max_suppression_seconds = self.settings.ack_guard_max_buffer_seconds
        if quiet_required <= 0 or max_suppression_seconds <= 0:
            return _PostAckBoundaryResult(False, 0, (), (), 0.0, 0, 0, 0, True)

        minimum_chunk_seconds = 1.0 / self.settings.sample_rate
        expected_frame_seconds = _detector_frame_seconds(self.wake_detector, self.settings.sample_rate)
        max_chunks = max(1, math.ceil(max_suppression_seconds / expected_frame_seconds))
        noise_seed_chunks: deque[bytes] = deque()
        elapsed_seconds = 0.0
        quiet_seconds = 0.0
        chunks_read = 0
        max_rms = 0.0
        max_peak = 0
        overflow_chunks = 0
        clipped_chunks = 0

        self._logger.info(
            (
                "State ACK_PLAYING: waiting for safe post-ACK boundary; "
                "quiet_required=%.2fs max_suppression=%.2fs"
            ),
            quiet_required,
            max_suppression_seconds,
        )
        while chunks_read < max_chunks and elapsed_seconds < max_suppression_seconds:
            chunk = self.audio_source.read_chunk()
            chunk_seconds = max(_chunk_duration_seconds(chunk, self.settings.sample_rate), minimum_chunk_seconds)
            elapsed_seconds += chunk_seconds
            chunks_read += 1
            rms, peak = pcm_rms_and_peak(chunk)
            max_rms = max(max_rms, rms)
            max_peak = max(max_peak, peak)
            overflowed = bool(getattr(self.audio_source, "last_overflowed", False))
            clipped = peak >= self.settings.armed_clip_reject_peak
            overflow_chunks += int(overflowed)
            clipped_chunks += int(clipped)
            quiet = not overflowed and not clipped and rms <= self.settings.ack_guard_quiet_rms
            if quiet:
                quiet_seconds += chunk_seconds
                noise_seed_chunks.append(chunk)
            else:
                quiet_seconds = 0.0
                noise_seed_chunks.clear()
            if quiet_seconds >= quiet_required:
                break

        quiet_observed = quiet_seconds >= quiet_required
        timed_out = not quiet_observed
        self._logger.info(
            (
                "State ACK_PLAYING: post-ACK boundary post_ack_quiet_observed=%s "
                "post_ack_suppressed_chunks=%s preserved_chunks=0 noise_seed_count=%s "
                "quiet=%.2fs post_ack_max_rms=%.1f post_ack_max_peak=%s "
                "post_ack_overflow_chunks=%s post_ack_clipped_chunks=%s timed_out=%s"
            ),
            _bool_text(quiet_observed),
            chunks_read,
            len(noise_seed_chunks),
            quiet_seconds,
            max_rms,
            max_peak,
            overflow_chunks,
            clipped_chunks,
            _bool_text(timed_out),
        )
        return _PostAckBoundaryResult(
            quiet_observed=quiet_observed,
            suppressed_chunks=chunks_read,
            preserved_chunks=(),
            noise_seed_chunks=tuple(noise_seed_chunks) if quiet_observed else (),
            max_rms=max_rms,
            max_peak=max_peak,
            overflow_chunks=overflow_chunks,
            clipped_chunks=clipped_chunks,
            timed_out=timed_out,
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

    def _drain_post_cancellation_audio(self, *, reason: str) -> None:
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
        max_scores: list[float] = []

        self._logger.info(
            "State WAIT_WAKE: suppressing post-cancellation wake detection reason=%s for %.2fs",
            reason,
            cooldown_seconds,
        )
        while drained_chunks < max_chunks and drained_seconds < cooldown_seconds:
            chunk = self.audio_source.read_chunk()
            drained_chunks += 1
            drained_seconds += max(_chunk_duration_seconds(chunk, self.settings.sample_rate), minimum_chunk_seconds)
            score = self._suppressed_wake_score(
                chunk,
                overflowed=bool(getattr(self.audio_source, "last_overflowed", False)),
                context="post-cancellation",
            )
            if score is not None:
                max_scores.append(score)

        self._logger.info(
            "State WAIT_WAKE: discarded %s post-cancellation microphone chunks reason=%s max_suppressed_score=%.9f",
            drained_chunks,
            reason,
            max(max_scores, default=0.0),
        )
        self._wait_for_post_cancellation_quiet(
            reason=reason,
            drained_seconds=drained_seconds,
            minimum_chunk_seconds=minimum_chunk_seconds,
            max_scores=max_scores,
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

    def _wait_for_post_cancellation_quiet(
        self,
        *,
        reason: str,
        drained_seconds: float,
        minimum_chunk_seconds: float,
        max_scores: list[float],
    ) -> None:
        quiet_seconds_required = self.settings.post_playback_quiet_seconds
        if quiet_seconds_required <= 0:
            return

        max_suppression_seconds = self.settings.post_playback_max_suppression_seconds
        quiet_seconds = 0.0
        suppressed_chunks = 0
        self._logger.info(
            "State WAIT_WAKE: waiting for %.2fs of post-cancellation quiet audio reason=%s",
            quiet_seconds_required,
            reason,
        )

        while quiet_seconds < quiet_seconds_required:
            if max_suppression_seconds > 0 and drained_seconds >= max_suppression_seconds:
                self._logger.warning(
                    "State WAIT_WAKE: post-cancellation quiet gate reached %.2fs maximum suppression before quiet reason=%s",
                    max_suppression_seconds,
                    reason,
                )
                break

            chunk = self.audio_source.read_chunk()
            chunk_seconds = max(_chunk_duration_seconds(chunk, self.settings.sample_rate), minimum_chunk_seconds)
            drained_seconds += chunk_seconds
            suppressed_chunks += 1

            overflowed = bool(getattr(self.audio_source, "last_overflowed", False))
            score = self._suppressed_wake_score(chunk, overflowed=overflowed, context="post-cancellation")
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
            "State WAIT_WAKE: post-cancellation quiet gate consumed %s chunks reason=%s quiet=%.2fs max_suppressed_score=%.9f",
            suppressed_chunks,
            reason,
            quiet_seconds,
            max_score,
        )

    def _suppressed_wake_score(self, chunk: bytes, *, overflowed: bool, context: str = "post-playback") -> float | None:
        if overflowed:
            self._logger.info("State WAIT_WAKE: suppressing overflowed %s microphone chunk", context)
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


def _format_vad_ratio(value: float | None) -> str:
    return "disabled" if value is None else f"{value:.3f}"


def _chunk_duration_seconds(pcm_chunk: bytes, sample_rate: int) -> float:
    if sample_rate <= 0 or not pcm_chunk:
        return 0.0
    return len(pcm_chunk) / (sample_rate * 2)


def _detector_frame_seconds(wake_detector: object, sample_rate: int) -> float:
    frame_length = int(getattr(wake_detector, "frame_length", 0) or 0)
    if sample_rate <= 0 or frame_length <= 0:
        return 0.08
    return frame_length / sample_rate


class _PreloadedChunkSource:
    def __init__(self, preloaded_chunks: Sequence[bytes], source: ChunkSource) -> None:
        self._preloaded_chunks = deque(preloaded_chunks)
        self._source = source

    @property
    def last_overflowed(self) -> bool:
        if self._preloaded_chunks:
            return False
        return bool(getattr(self._source, "last_overflowed", False))

    def read_chunk(self) -> bytes:
        if self._preloaded_chunks:
            return self._preloaded_chunks.popleft()
        return self._source.read_chunk()


def _noise_floor(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    sorted_samples = sorted(samples)
    midpoint = len(sorted_samples) // 2
    if len(sorted_samples) % 2:
        return sorted_samples[midpoint]
    return (sorted_samples[midpoint - 1] + sorted_samples[midpoint]) / 2


def _trim_pre_roll(
    pre_roll: deque[_ArmedChunk],
    *,
    pre_roll_seconds: float,
    max_seconds: float,
) -> float:
    target_seconds = max(0.0, max_seconds)
    while len(pre_roll) > 1 and pre_roll_seconds > target_seconds:
        removed = pre_roll.popleft()
        pre_roll_seconds -= removed.seconds
    return max(0.0, pre_roll_seconds)


_FILLER_TRANSCRIPTS = {"um", "uh", "umm", "hmm", "hm", "嗯", "啊", "呃", "额", "在呢"}
_NOISY_CANCEL_SUFFIXES = {
    "了",
    "啦",
    "吧",
    "呀",
    "啊",
    "儿",
    "哈",
    "谢谢",
    "多谢",
    "不用",
    "不用了",
    "不用啦",
    "不用吧",
    "没事",
    "没事了",
    "取消",
    "取消吧",
    "算了",
    "算了吧",
    "please",
    "thanks",
    "thankyou",
    "thx",
    "now",
    "it",
    "that",
    "有声音",
    "有噪音",
    "有杂音",
    "后面有声音",
    "背景有声音",
    "背景噪音",
}
_COLLOQUIAL_CHINESE_CANCEL_SEGMENTS = {
    "不用",
    "不用了",
    "不用啦",
    "不用吧",
    "不要",
    "不要了",
    "不要啦",
    "不要吧",
    "没事",
    "没事了",
    "没事儿",
    "没事啦",
    "没事吧",
}
_SHORT_TRANSCRIPT_DIAGNOSTIC_MAX_COMPACT_LENGTH = 12


def _normalize_transcript(text: str) -> str:
    lowered = text.strip().lower()
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", lowered)
    return re.sub(r"\s+", " ", normalized).strip()


def _is_noisy_cancel_variant(transcript_compact: str, phrase_compact: str, cancel_phrases: tuple[str, ...]) -> bool:
    if not transcript_compact.startswith(phrase_compact):
        return False
    suffix = transcript_compact[len(phrase_compact) :]
    if not suffix:
        return True
    if suffix in _NOISY_CANCEL_SUFFIXES:
        return True

    compact_cancel_phrases = {
        _normalize_transcript(phrase).replace(" ", "")
        for phrase in cancel_phrases
        if _normalize_transcript(phrase).replace(" ", "")
    }
    return _is_made_of_cancel_segments(suffix, compact_cancel_phrases)


def _is_colloquial_chinese_cancel_variant(transcript_compact: str) -> bool:
    if not transcript_compact:
        return False
    return _is_made_of_exact_segments(transcript_compact, _COLLOQUIAL_CHINESE_CANCEL_SEGMENTS)


def _is_made_of_cancel_segments(text: str, segments: set[str]) -> bool:
    if not text:
        return True
    for segment in sorted(segments | _NOISY_CANCEL_SUFFIXES, key=len, reverse=True):
        if text.startswith(segment) and _is_made_of_cancel_segments(text[len(segment) :], segments):
            return True
    return False


def _is_made_of_exact_segments(text: str, segments: set[str]) -> bool:
    if not text:
        return True
    for segment in sorted(segments, key=len, reverse=True):
        if text.startswith(segment) and _is_made_of_exact_segments(text[len(segment) :], segments):
            return True
    return False


def _is_empty_transcription_error(exc: OpenAIClientError) -> bool:
    message = str(exc).lower()
    return "transcription" in message and "empty" in message


def _wav_voice_duration_seconds(path: Path, *, sample_rate: int, voice_rms: float) -> float:
    if not path.is_file():
        return 0.0

    try:
        with wave.open(str(path), "rb") as wav_file:
            channels = max(1, wav_file.getnchannels())
            sample_width = wav_file.getsampwidth()
            frame_rate = wav_file.getframerate() or sample_rate
            window_frames = max(1, min(1280, frame_rate))
            voice_seconds = 0.0
            while True:
                pcm = wav_file.readframes(window_frames)
                if not pcm:
                    break
                if sample_width != 2:
                    continue
                rms, _ = pcm_rms_and_peak(pcm)
                if rms >= voice_rms:
                    frame_count = len(pcm) / (sample_width * channels)
                    voice_seconds += frame_count / frame_rate
            return voice_seconds
    except wave.Error:
        return 0.0
