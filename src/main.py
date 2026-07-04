"""Command-line entrypoint for the Hey Jarvis MVP."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
import wave
from pathlib import Path
from typing import TextIO

from .audio_input import open_microphone_stream
from .config import Settings
from .config import collect_diagnostics, format_diagnostics, load_settings
from .openai_client import build_openai_client
from .player import MacOSPlayer
from .recorder import RecordingResult
from .state_machine import AssistantState, VoiceAssistantStateMachine
from .wake_word import (
    OPENWAKEWORD_FRAME_SAMPLES,
    WakeWordDetector,
    pad_pcm_chunk,
    pcm_rms_and_peak,
    prepare_wake_word_models,
)


LOGGER_NAME = "hey_jarvis"
WAKE_SCORE_PRECISION = 9


@dataclass
class WakeDebugSummary:
    frame_count: int = 0
    max_score: float = 0.0
    detected_frame_count: int = 0
    interrupted: bool = False

    def add(self, score: float, threshold: float) -> None:
        self.frame_count += 1
        self.max_score = max(self.max_score, score)
        if score >= threshold:
            self.detected_frame_count += 1


def run_dry_run() -> int:
    """Exercise the skeleton path without microphone, OpenAI, or playback."""
    print("Assistant started")
    print("Dry run: microphone, wake word, OpenAI, and playback are not invoked")
    print("Returned to WAIT_WAKE")
    return 0


def run_fake_backend_smoke() -> int:
    """Exercise the full state machine with deterministic fakes."""

    logger = logging.getLogger(LOGGER_NAME)
    settings = load_settings(env={}, env_file=None)
    microphone = _FakeMicrophone([b"\x00\x00", b"\x01\x00"])
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
    """Download the ONNX model files required for real wake-word detection."""

    logger = logging.getLogger(LOGGER_NAME)
    prepared = prepare_wake_word_models(logger=logger)
    print("Prepared wake-word ONNX models:")
    for name, path in sorted(prepared.items()):
        print(f"- {name}: {path}")
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
    detector = wake_detector or WakeWordDetector(resolved_settings.wake_threshold, logger=logger)
    if hasattr(detector, "preload"):
        logger.info("Preparing Alexa wake-word detector")
        detector.preload()
        logger.info("Alexa wake-word detector ready")

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
    detector = wake_detector or WakeWordDetector(resolved_settings.wake_threshold, logger=logger)
    if hasattr(detector, "preload"):
        logger.info("Preparing Alexa wake-word detector")
        detector.preload()
        logger.info("Alexa wake-word detector ready")

    summary = WakeDebugSummary()
    target = output or None
    with wave.open(str(wav_path), "rb") as wav_file:
        if wav_file.getnchannels() != 1:
            raise ValueError("wake-file debug requires a mono WAV file")
        if wav_file.getsampwidth() != 2:
            raise ValueError("wake-file debug requires 16-bit PCM WAV samples")

        while True:
            chunk = wav_file.readframes(_detector_frame_length(detector))
            if not chunk:
                break
            score = _wake_score(detector, pad_pcm_chunk(chunk, frame_length=_detector_frame_length(detector)))
            summary.add(score, resolved_settings.wake_threshold)
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


def run_assistant_forever() -> int:
    """Run the real assistant until interrupted."""

    logger = logging.getLogger(LOGGER_NAME)
    settings = load_settings(require_openai_api_key=True)
    history: list[dict[str, str]] = []

    logger.info("Assistant started")
    logger.info("Say %s, ask a question, and wait for playback", settings.wake_phrase)
    wake_detector: object | None = None
    try:
        wake_detector = WakeWordDetector(settings.wake_threshold, logger=logger)
        logger.info("Preparing Alexa wake-word detector")
        wake_detector.preload()
        logger.info("Alexa wake-word detector ready")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.main")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="run a dependency-free smoke path for recovery verification",
    )
    mode.add_argument(
        "--diagnose",
        action="store_true",
        help="report runtime configuration, dependency, and macOS readiness checks",
    )
    mode.add_argument(
        "--fake-backend",
        action="store_true",
        help="run the full state-machine smoke path with deterministic fakes",
    )
    mode.add_argument(
        "--prepare-wake-word",
        action="store_true",
        help="download the ONNX wake-word models required by the real assistant",
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
        report = collect_diagnostics()
        print(format_diagnostics(report))
        return 1 if report.has_errors else 0
    if args.fake_backend:
        return run_fake_backend_smoke()
    if args.prepare_wake_word:
        return run_prepare_wake_word()
    if args.wake_debug:
        return run_wake_debug(
            max_frames=args.wake_debug_frames or None,
            debug_output_path=args.wake_debug_output,
        )
    if args.wake_file:
        return run_wake_file_debug(args.wake_file)

    return run_assistant_forever()


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


class _FakeMicrophone:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    def read_chunk(self) -> bytes:
        if not self._chunks:
            return b"\x01\x00"
        return self._chunks.pop(0)


class _FakeWakeDetector:
    def detect(self, pcm_chunk: bytes) -> bool:
        return pcm_chunk == b"\x01\x00"

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
        wav_file.writeframes(b"\x00\x00" * 160)
    return RecordingResult(path=path, duration_seconds=0.01, chunks_recorded=1, stopped_by="fake_backend")


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
        if debug_output_path is not None:
            wav_file = _open_debug_output_wav(debug_output_path, settings.sample_rate)
        while max_frames is None or summary.frame_count < max_frames:
            chunk = audio_source.read_chunk()
            score = _wake_score(detector, chunk)
            summary.add(score, settings.wake_threshold)
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
    return (
        f"{mode} summary frames={summary.frame_count} "
        f"max_score={summary.max_score:.{WAKE_SCORE_PRECISION}f} "
        f"threshold={threshold:.{WAKE_SCORE_PRECISION}f} "
        f"detected_frames={summary.detected_frame_count}"
    )


def _wake_score(detector: object, pcm_chunk: bytes) -> float:
    score_method = getattr(detector, "score", None)
    if score_method is not None:
        return float(score_method(pcm_chunk))
    return 1.0 if detector.detect(pcm_chunk) else 0.0


def _detector_frame_length(detector: object) -> int:
    return int(getattr(detector, "frame_length", OPENWAKEWORD_FRAME_SAMPLES))


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


if __name__ == "__main__":
    raise SystemExit(main())
