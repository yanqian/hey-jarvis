"""Command-line entrypoint for the Hey Jarvis MVP."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import logging
import tempfile
import threading
import wave
from pathlib import Path
from typing import TextIO

from .audio_input import open_microphone_stream
from .config import SUPPORTED_BACKENDS, Settings
from .config import collect_diagnostics, format_diagnostics, load_settings, wake_acknowledgement_missing_message
from .openai_client import build_openai_client
from .player import MacOSPlayer
from .recorder import RecordingResult
from .realtime.controller import RealtimeSessionController
from .state_machine import AssistantState, VoiceAssistantStateMachine
from .tools.providers import provider_config_from_settings
from .tools.router import format_text_debug
from .wake_word import (
    OPENWAKEWORD_FRAME_SAMPLES,
    WakeWordDetector,
    pad_pcm_chunk,
    pcm_rms_and_peak,
    prepare_wake_word_models,
)
from .vad import build_vad_detector


LOGGER_NAME = "hey_jarvis"
WAKE_SCORE_PRECISION = 9


@dataclass
class WakeDebugSummary:
    frame_count: int = 0
    max_score: float = 0.0
    detected_frame_count: int = 0
    interrupted: bool = False
    max_scores_by_key: dict[str, float] | None = None

    def add(self, score: float, threshold: float, scores_by_key: dict[str, float] | None = None) -> None:
        self.frame_count += 1
        self.max_score = max(self.max_score, score)
        if score >= threshold:
            self.detected_frame_count += 1
        if scores_by_key:
            if self.max_scores_by_key is None:
                self.max_scores_by_key = {}
            for key, value in scores_by_key.items():
                self.max_scores_by_key[key] = max(self.max_scores_by_key.get(key, 0.0), value)


def run_dry_run() -> int:
    """Exercise the skeleton path without microphone, OpenAI, or playback."""
    print("Assistant started")
    print("Dry run: microphone, wake word, OpenAI, and playback are not invoked")
    print("Returned to WAIT_WAKE")
    return 0


def run_fake_backend_smoke() -> int:
    """Exercise the full state machine with deterministic fakes."""

    logger = logging.getLogger(LOGGER_NAME)
    base_settings = load_settings(env={}, env_file=None)
    with tempfile.TemporaryDirectory() as tmp_dir:
        acknowledgement_path = Path(tmp_dir) / "ack.mp3"
        acknowledgement_path.write_bytes(b"fake-ack")
        settings = replace(base_settings, wake_acknowledgement_audio_path=acknowledgement_path)
        microphone = _FakeMicrophone(
            [
                _FAKE_SILENCE_CHUNK,
                _FAKE_WAKE_CHUNK,
                _FAKE_WAKE_CHUNK,
                _FAKE_SILENCE_CHUNK,
                _FAKE_SILENCE_CHUNK,
                _FAKE_SILENCE_CHUNK,
                _FAKE_SILENCE_CHUNK,
                _FAKE_SILENCE_CHUNK,
                _FAKE_SPEECH_CHUNK,
                _FAKE_SPEECH_CHUNK,
                _FAKE_SPEECH_CHUNK,
                _FAKE_SPEECH_CHUNK,
            ]
        )
        machine = VoiceAssistantStateMachine(
            settings=settings,
            audio_source=microphone,
            wake_detector=_FakeWakeDetector(),
            openai_client=_FakeOpenAIClient(),
            player=_FakePlayer(),
            record_audio=_fake_record_audio,
            logger=logger,
        )
        result = machine.run_once()
    print("Assistant started")
    print(f"Fake backend answered: {result.answer}")
    print(f"Returned to {result.final_state.value}")
    return 0 if result.final_state == AssistantState.WAIT_WAKE else 1


def run_prepare_wake_word() -> int:
    """Download the model files required for real wake-word detection."""

    logger = logging.getLogger(LOGGER_NAME)
    settings = load_settings()
    prepared = prepare_wake_word_models(
        model_name=settings.wake_model,
        inference_framework=settings.wake_inference_framework,
        logger=logger,
    )
    print(f"Prepared wake-word {settings.wake_inference_framework} models:")
    for name, path in sorted(prepared.items()):
        print(f"- {name}: {path}")
    return 0


def run_prepare_acknowledgement(
    *,
    settings: Settings | None = None,
    openai_client: object | None = None,
) -> int:
    """Generate the configured wake acknowledgement audio once."""

    resolved_settings = settings or load_settings(require_openai_api_key=True)
    client = openai_client or build_openai_client(settings=resolved_settings)
    client.text_to_speech(
        resolved_settings.wake_acknowledgement_text,
        str(resolved_settings.wake_acknowledgement_audio_path),
    )
    print(f"Prepared wake acknowledgement audio: {resolved_settings.wake_acknowledgement_audio_path}")
    return 0


def run_text_debug(text: str) -> int:
    """Print deterministic structured-tool routing for text input."""

    settings = load_settings()
    print(format_text_debug(text, provider_config=provider_config_from_settings(settings)))
    return 0


def run_wake_debug(
    *,
    max_frames: int | None = None,
    debug_output_path: str | Path | None = None,
    settings: Settings | None = None,
    audio_source: object | None = None,
    wake_detector: object | None = None,
    output: TextIO | None = None,
) -> int:
    """Print live wake-word debug frames without OpenAI or playback."""

    logger = logging.getLogger(LOGGER_NAME)
    resolved_settings = settings or load_settings()
    detector = wake_detector or _build_wake_detector(resolved_settings, logger=logger)
    if hasattr(detector, "preload"):
        logger.info("Preparing %s wake-word detector", resolved_settings.wake_phrase)
        detector.preload()
        logger.info("%s wake-word detector ready", resolved_settings.wake_phrase.title())

    if audio_source is not None:
        summary = _print_live_wake_debug(
            audio_source,
            detector,
            settings=resolved_settings,
            max_frames=max_frames,
            debug_output_path=debug_output_path,
            output=output,
        )
        return 130 if summary.interrupted else 0

    with open_microphone_stream(
        sample_rate=resolved_settings.sample_rate,
        block_frames=_detector_frame_length(detector),
        logger=logger,
    ) as microphone:
        summary = _print_live_wake_debug(
            microphone,
            detector,
            settings=resolved_settings,
            max_frames=max_frames,
            debug_output_path=debug_output_path,
            output=output,
        )
    return 130 if summary.interrupted else 0


def run_wake_file_debug(
    wav_path: str | Path,
    *,
    settings: Settings | None = None,
    wake_detector: object | None = None,
    output: TextIO | None = None,
) -> int:
    """Print wake-word debug scores for a saved WAV file."""

    logger = logging.getLogger(LOGGER_NAME)
    resolved_settings = settings or load_settings()
    detector = wake_detector or _build_wake_detector(resolved_settings, logger=logger)
    if hasattr(detector, "preload"):
        logger.info("Preparing %s wake-word detector", resolved_settings.wake_phrase)
        detector.preload()
        logger.info("%s wake-word detector ready", resolved_settings.wake_phrase.title())

    summary = WakeDebugSummary()
    target = output or None
    print(
        _format_wake_debug_metadata("wake_file", resolved_settings, detector),
        file=target,
    )
    with wave.open(str(wav_path), "rb") as wav_file:
        if wav_file.getnchannels() != 1:
            raise ValueError("wake-file debug requires a mono WAV file")
        if wav_file.getsampwidth() != 2:
            raise ValueError("wake-file debug requires 16-bit PCM WAV samples")

        while True:
            chunk = wav_file.readframes(_detector_frame_length(detector))
            if not chunk:
                break
            scores_by_key = _wake_scores(detector, pad_pcm_chunk(chunk, frame_length=_detector_frame_length(detector)))
            score = _selected_wake_score(detector, scores_by_key)
            summary.add(score, resolved_settings.wake_threshold, scores_by_key)
            print(
                _format_wake_debug_line(
                    mode="wake_file",
                    frame_index=summary.frame_count,
                    pcm_chunk=chunk,
                    score=score,
                    threshold=resolved_settings.wake_threshold,
                    overflow=False,
                ),
                file=target,
            )

    print(_format_wake_debug_summary("wake_file", summary, resolved_settings.wake_threshold), file=target)
    return 0


def run_assistant_forever(*, backend: str | None = None) -> int:
    """Run the real assistant until interrupted."""

    logger = logging.getLogger(LOGGER_NAME)
    settings = load_settings(require_openai_api_key=True, backend=backend)
    if settings.backend == "realtime":
        return run_realtime_forever(settings)
    history: list[dict[str, str]] = []

    logger.info("Assistant started")
    logger.info("Say %s, ask a question, and wait for playback", settings.wake_phrase)
    missing_acknowledgement = wake_acknowledgement_missing_message(settings)
    if missing_acknowledgement is not None:
        logger.error(missing_acknowledgement)
        return 1
    wake_detector: object | None = None
    try:
        wake_detector = _build_wake_detector(settings, logger=logger)
        vad_detector = build_vad_detector(settings.vad_backend, mode=settings.vad_mode)
        logger.info("Preparing %s wake-word detector", settings.wake_phrase)
        wake_detector.preload()
        logger.info("%s wake-word detector ready", settings.wake_phrase.title())
        with open_microphone_stream(
            sample_rate=settings.sample_rate,
            block_frames=_detector_frame_length(wake_detector),
            logger=logger,
        ) as microphone:
            machine = VoiceAssistantStateMachine(
                settings=settings,
                audio_source=microphone,
                wake_detector=wake_detector,
                openai_client=build_openai_client(settings=settings),
                player=MacOSPlayer(logger=logger),
                history=history,
                logger=logger,
                vad_detector=vad_detector,
            )
            while True:
                machine.run_once()
    except KeyboardInterrupt:
        logger.info("Assistant stopped")
        return 130
    finally:
        if wake_detector is not None:
            close = getattr(wake_detector, "close", None)
            if close is not None:
                close()


def run_realtime_forever(settings: Settings) -> int:
    """Run local wake listening and continuous WebRTC sessions until interrupted."""

    from .realtime_host.server import build_server, launch_chrome_app

    logger = logging.getLogger(LOGGER_NAME)
    missing_acknowledgement = wake_acknowledgement_missing_message(settings)
    if settings.realtime_acknowledgement_mode == "local" and missing_acknowledgement is not None:
        logger.error(missing_acknowledgement)
        return 1

    detector = _build_wake_detector(settings, logger=logger)
    if hasattr(detector, "preload"):
        logger.info("Preparing %s wake-word detector", settings.wake_phrase)
        detector.preload()
    server = build_server(
        settings.realtime_bridge_host,
        settings.realtime_bridge_port,
        real_microphone=True,
        wake_after_arm=True,
        end_phrases=settings.realtime_end_phrases,
    )
    url = f"http://{settings.realtime_bridge_host}:{server.server_port}/"
    launch_chrome_app(url)
    server_thread = threading.Thread(target=server.serve_forever, name="realtime-host", daemon=True)
    server_thread.start()
    player = MacOSPlayer(logger=logger)

    def play_acknowledgement() -> None:
        if settings.realtime_acknowledgement_mode == "local":
            player.play(settings.wake_acknowledgement_audio_path)

    controller = RealtimeSessionController(
        coordinator=server.coordinator,
        wake_detector=detector,
        play_acknowledgement=play_acknowledgement,
        idle_timeout_seconds=settings.realtime_idle_timeout_seconds,
        max_duration_seconds=settings.realtime_max_duration_seconds,
        wake_confirmation_frames=settings.wake_confirmation_frames,
    )
    logger.info("Realtime host launched at %s; arm it once, then say %s", url, settings.wake_phrase)
    try:
        while True:
            result = controller.run_once()
            logger.info(
                "Realtime session ended reason=%s recovered_to_wake=%s",
                result.reason,
                str(result.recovered_to_wake).lower(),
            )
            if not result.recovered_to_wake:
                logger.error("Realtime host did not confirm media teardown; wake capture remains fail-closed")
                return 1
    except KeyboardInterrupt:
        logger.info("Assistant stopped")
        return 130
    finally:
        server.shutdown()
        server.server_close()
        server.coordinator.close()
        close = getattr(detector, "close", None)
        if close is not None:
            close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.main")
    parser.add_argument(
        "--backend",
        choices=SUPPORTED_BACKENDS,
        help="select pipeline (default) or opt-in billable Realtime WebRTC (arm Chrome once per launch)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="run a dependency-free smoke path for recovery verification",
    )
    mode.add_argument(
        "--diagnose",
        action="store_true",
        help="report selected-backend configuration, permission, privacy, and macOS readiness checks",
    )
    mode.add_argument(
        "--fake-backend",
        action="store_true",
        help="run the full state-machine smoke path with deterministic fakes",
    )
    mode.add_argument(
        "--prepare-wake-word",
        action="store_true",
        help="download the configured wake-word models required by the real assistant",
    )
    mode.add_argument(
        "--prepare-acknowledgement",
        action="store_true",
        help="generate the configured wake acknowledgement audio file once",
    )
    mode.add_argument(
        "--wake-debug",
        action="store_true",
        help="print live microphone wake-word scores without OpenAI or playback",
    )
    mode.add_argument(
        "--wake-file",
        metavar="PATH",
        help="print wake-word scores for a 16-bit mono WAV file without microphone access",
    )
    mode.add_argument(
        "--text",
        metavar="TEXT",
        help="print structured tool routing for text input without audio, OpenAI, or playback",
    )
    parser.add_argument(
        "--wake-debug-frames",
        type=int,
        default=0,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--wake-debug-output",
        metavar="PATH",
        help="write live wake-debug microphone PCM to a 16 kHz mono WAV file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.wake_debug_output and not args.wake_debug:
        parser.error("--wake-debug-output requires --wake-debug")
    if args.dry_run:
        return run_dry_run()
    if args.diagnose:
        report = collect_diagnostics(backend=args.backend)
        print(format_diagnostics(report))
        return 1 if report.has_errors else 0
    if args.fake_backend:
        return run_fake_backend_smoke()
    if args.prepare_wake_word:
        return run_prepare_wake_word()
    if args.prepare_acknowledgement:
        return run_prepare_acknowledgement()
    if args.text is not None:
        return run_text_debug(args.text)
    if args.wake_debug:
        return run_wake_debug(
            max_frames=args.wake_debug_frames or None,
            debug_output_path=args.wake_debug_output,
        )
    if args.wake_file:
        return run_wake_file_debug(args.wake_file)

    return run_assistant_forever(backend=args.backend)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


_FAKE_SILENCE_CHUNK = b"\x00\x00" * OPENWAKEWORD_FRAME_SAMPLES
_FAKE_WAKE_CHUNK = b"\x01\x00" * OPENWAKEWORD_FRAME_SAMPLES
_FAKE_SPEECH_CHUNK = (2000).to_bytes(2, byteorder="little", signed=True) * OPENWAKEWORD_FRAME_SAMPLES


class _FakeMicrophone:
    def __init__(self, chunks: list[bytes], *, fallback_chunk: bytes = _FAKE_SILENCE_CHUNK) -> None:
        self._chunks = list(chunks)
        self._fallback_chunk = fallback_chunk

    def read_chunk(self) -> bytes:
        if not self._chunks:
            return self._fallback_chunk
        return self._chunks.pop(0)


class _FakeWakeDetector:
    def detect(self, pcm_chunk: bytes) -> bool:
        return pcm_chunk.startswith(b"\x01\x00")

    def score(self, pcm_chunk: bytes) -> float:
        return 1.0 if self.detect(pcm_chunk) else 0.0


class _FakeOpenAIClient:
    def transcribe_audio(self, path: str) -> str:
        if not Path(path).is_file():
            raise RuntimeError(f"fake transcription input missing: {path}")
        return "what is two plus two?"

    def ask_chatgpt(self, text: str, history: list[dict[str, str]]) -> str:
        history.append({"role": "user", "content": text})
        answer = "Two plus two is four."
        history.append({"role": "assistant", "content": answer})
        return answer

    def text_to_speech(self, text: str, output_path: str) -> None:
        if not text.strip():
            raise RuntimeError("fake TTS input was empty")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake-mp3")


class _FakePlayer:
    def play(self, path: str | Path) -> None:
        if not Path(path).is_file():
            raise RuntimeError(f"fake playback input missing: {path}")


def _fake_record_audio(
    source: object,
    *,
    sample_rate: int,
    output_path: str | Path,
    **_: object,
) -> RecordingResult:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(_FAKE_SPEECH_CHUNK * 8)
    return RecordingResult(path=path, duration_seconds=0.64, chunks_recorded=8, stopped_by="fake_backend")


def _print_live_wake_debug(
    audio_source: object,
    detector: object,
    *,
    settings: Settings,
    max_frames: int | None,
    debug_output_path: str | Path | None,
    output: TextIO | None,
) -> WakeDebugSummary:
    summary = WakeDebugSummary()
    wav_file: wave.Wave_write | None = None
    try:
        print(_format_wake_debug_metadata("wake_debug", settings, detector), file=output)
        if debug_output_path is not None:
            wav_file = _open_debug_output_wav(debug_output_path, settings.sample_rate)
        while max_frames is None or summary.frame_count < max_frames:
            chunk = audio_source.read_chunk()
            scores_by_key = _wake_scores(detector, chunk)
            score = _selected_wake_score(detector, scores_by_key)
            summary.add(score, settings.wake_threshold, scores_by_key)
            print(
                _format_wake_debug_line(
                    mode="wake_debug",
                    frame_index=summary.frame_count,
                    pcm_chunk=chunk,
                    score=score,
                    threshold=settings.wake_threshold,
                    overflow=bool(getattr(audio_source, "last_overflowed", False)),
                ),
                file=output,
            )
            if wav_file is not None:
                wav_file.writeframes(chunk)
    except KeyboardInterrupt:
        summary.interrupted = True
    finally:
        if wav_file is not None:
            wav_file.close()
        print(_format_wake_debug_summary("wake_debug", summary, settings.wake_threshold), file=output)
    return summary


def _open_debug_output_wav(path: str | Path, sample_rate: int) -> wave.Wave_write:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wav_file = wave.open(str(output_path), "wb")
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(sample_rate)
    return wav_file


def _format_wake_debug_line(
    *,
    mode: str,
    frame_index: int,
    pcm_chunk: bytes,
    score: float,
    threshold: float,
    overflow: bool,
) -> str:
    rms, peak = pcm_rms_and_peak(pcm_chunk)
    detected = score >= threshold
    return (
        f"{mode} frame={frame_index} rms={rms:.1f} peak={peak} "
        f"overflow={_bool_text(overflow)} score={score:.{WAKE_SCORE_PRECISION}f} "
        f"threshold={threshold:.{WAKE_SCORE_PRECISION}f} detected={_bool_text(detected)}"
    )


def _format_wake_debug_summary(mode: str, summary: WakeDebugSummary, threshold: float) -> str:
    max_scores = _format_score_map(summary.max_scores_by_key or {})
    return (
        f"{mode} summary frames={summary.frame_count} "
        f"max_score={summary.max_score:.{WAKE_SCORE_PRECISION}f} "
        f"max_scores={max_scores} "
        f"threshold={threshold:.{WAKE_SCORE_PRECISION}f} "
        f"detected_frames={summary.detected_frame_count}"
    )


def _format_wake_debug_metadata(mode: str, settings: Settings, detector: object) -> str:
    loaded_model_keys = _loaded_model_keys(detector)
    return (
        f"{mode} metadata model={settings.wake_model} "
        f"framework={settings.wake_inference_framework} "
        f"loaded_models={','.join(loaded_model_keys) if loaded_model_keys else 'unknown'}"
    )


def _wake_score(detector: object, pcm_chunk: bytes) -> float:
    return _selected_wake_score(detector, _wake_scores(detector, pcm_chunk))


def _wake_scores(detector: object, pcm_chunk: bytes) -> dict[str, float]:
    score_details = getattr(detector, "score_details", None)
    if score_details is not None:
        return {str(key): float(value) for key, value in score_details(pcm_chunk).items()}

    score_method = getattr(detector, "score", None)
    if score_method is not None:
        model_key = str(getattr(detector, "model_key", getattr(detector, "model_name", "score")))
        return {model_key: float(score_method(pcm_chunk))}
    model_key = str(getattr(detector, "model_key", getattr(detector, "model_name", "detected")))
    return {model_key: 1.0 if detector.detect(pcm_chunk) else 0.0}


def _selected_wake_score(detector: object, scores: dict[str, float]) -> float:
    for key in (
        str(getattr(detector, "model_key", "")),
        str(getattr(detector, "model_name", "")),
    ):
        if key and key in scores:
            return scores[key]
    if len(scores) == 1:
        return next(iter(scores.values()))
    return max(scores.values(), default=0.0)


def _format_score_map(scores: dict[str, float]) -> str:
    if not scores:
        return "{}"
    return "{" + ",".join(f"{key}:{value:.{WAKE_SCORE_PRECISION}f}" for key, value in sorted(scores.items())) + "}"


def _loaded_model_keys(detector: object) -> tuple[str, ...]:
    loaded_model_keys = getattr(detector, "loaded_model_keys", None)
    if loaded_model_keys is not None:
        return tuple(str(key) for key in loaded_model_keys())
    return ()


def _detector_frame_length(detector: object) -> int:
    return int(getattr(detector, "frame_length", OPENWAKEWORD_FRAME_SAMPLES))


def _build_wake_detector(settings: Settings, *, logger: logging.Logger) -> WakeWordDetector:
    return WakeWordDetector(
        settings.wake_threshold,
        model_name=settings.wake_model,
        inference_framework=settings.wake_inference_framework,
        vad_threshold=settings.wake_vad_threshold,
        logger=logger,
    )


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


if __name__ == "__main__":
    raise SystemExit(main())
