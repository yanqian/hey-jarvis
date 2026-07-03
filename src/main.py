"""Command-line entrypoint for the Hey Jarvis MVP."""

from __future__ import annotations

import argparse
import logging
import wave
from pathlib import Path

from .audio_input import open_microphone_stream
from .config import collect_diagnostics, format_diagnostics, load_settings
from .openai_client import build_openai_client
from .player import MacOSPlayer
from .recorder import RecordingResult
from .state_machine import AssistantState, VoiceAssistantStateMachine
from .wake_word import WakeWordDetector, prepare_wake_word_models


LOGGER_NAME = "hey_jarvis"


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


def run_assistant_forever() -> int:
    """Run the real assistant until interrupted."""

    logger = logging.getLogger(LOGGER_NAME)
    settings = load_settings(require_openai_api_key=True)
    history: list[dict[str, str]] = []

    logger.info("Assistant started")
    logger.info("Say Hey Jarvis, ask a question, and wait for playback")
    try:
        wake_detector = WakeWordDetector(settings.wake_threshold, logger=logger)
        logger.info("Preparing Hey Jarvis wake-word detector")
        wake_detector.preload()
        logger.info("Hey Jarvis wake-word detector ready")
        with open_microphone_stream(sample_rate=settings.sample_rate, logger=logger) as microphone:
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
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)
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


if __name__ == "__main__":
    raise SystemExit(main())
