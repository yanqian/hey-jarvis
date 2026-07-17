"""Private, local-only voice fixtures for repeatable Realtime acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import wave
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from src.audio_input import DEFAULT_BLOCK_FRAMES, open_microphone_stream


DEFAULT_FIXTURE_ROOT = Path("tmp/realtime-fixtures")
FIXTURE_NAMES = ("wake", "turn-1", "turn-2", "barge-in")
SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2


class FixtureError(RuntimeError):
    """Raised when a private fixture cannot be recorded or validated."""


class ChunkSource(Protocol):
    last_overflowed: bool

    def read_chunk(self) -> bytes: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class FixtureMetadata:
    name: str
    filename: str
    duration_seconds: float
    sample_rate: int
    channels: int
    sample_width_bytes: int
    sha256: str
    overflow_chunks: int
    recorded_at: str


@dataclass(frozen=True)
class ReplayMetadata:
    name: str
    filename: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    sha256: str


def record_fixture(
    source: ChunkSource,
    *,
    name: str,
    duration_seconds: float,
    root: Path = DEFAULT_FIXTURE_ROOT,
) -> FixtureMetadata:
    """Capture a fixed-duration mono 16-bit fixture without storing a transcript."""

    if name not in FIXTURE_NAMES:
        raise FixtureError(f"fixture name must be one of: {', '.join(FIXTURE_NAMES)}")
    if not 0.5 <= duration_seconds <= 30.0:
        raise FixtureError("duration_seconds must be between 0.5 and 30.0")

    target_bytes = round(duration_seconds * SAMPLE_RATE) * SAMPLE_WIDTH_BYTES
    pcm = bytearray()
    overflow_chunks = 0
    try:
        while len(pcm) < target_bytes:
            chunk = source.read_chunk()
            if len(chunk) % SAMPLE_WIDTH_BYTES:
                raise FixtureError("microphone returned an incomplete int16 sample")
            if getattr(source, "last_overflowed", False):
                overflow_chunks += 1
            pcm.extend(chunk)
    finally:
        source.close()

    captured = bytes(pcm[:target_bytes])
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(CHANNELS)
        output.setsampwidth(SAMPLE_WIDTH_BYTES)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(captured)

    metadata = FixtureMetadata(
        name=name,
        filename=path.name,
        duration_seconds=len(captured) / (SAMPLE_RATE * SAMPLE_WIDTH_BYTES),
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
        sample_width_bytes=SAMPLE_WIDTH_BYTES,
        sha256=hashlib.sha256(captured).hexdigest(),
        overflow_chunks=overflow_chunks,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    _update_manifest(root, metadata)
    return metadata


def load_manifest(root: Path = DEFAULT_FIXTURE_ROOT) -> dict[str, FixtureMetadata]:
    path = root / "manifest.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fixtures = payload.get("fixtures", {})
        return {name: FixtureMetadata(**value) for name, value in fixtures.items()}
    except (OSError, ValueError, TypeError) as exc:
        raise FixtureError(f"fixture manifest is invalid: {exc}") from exc


def trim_replay_fixture(
    *,
    name: str,
    start_seconds: float,
    end_seconds: float,
    root: Path = DEFAULT_FIXTURE_ROOT,
) -> ReplayMetadata:
    """Create a local replay derivative while preserving the original fixture."""

    if name not in FIXTURE_NAMES:
        raise FixtureError(f"fixture name must be one of: {', '.join(FIXTURE_NAMES)}")
    if start_seconds < 0 or end_seconds <= start_seconds:
        raise FixtureError("replay window must have a non-negative start before its end")
    source_path = root / f"{name}.wav"
    if not source_path.exists():
        raise FixtureError(f"missing fixture: {source_path}")
    try:
        with wave.open(str(source_path), "rb") as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (
                CHANNELS,
                SAMPLE_WIDTH_BYTES,
                SAMPLE_RATE,
            ):
                raise FixtureError("fixture format must be mono 16 kHz 16-bit WAV")
            total_frames = source.getnframes()
            start_frame = round(start_seconds * SAMPLE_RATE)
            end_frame = round(end_seconds * SAMPLE_RATE)
            if start_frame >= total_frames or end_frame > total_frames:
                raise FixtureError("replay window exceeds the fixture duration")
            source.setpos(start_frame)
            pcm = source.readframes(end_frame - start_frame)
    except wave.Error as exc:
        raise FixtureError(f"fixture WAV is invalid: {exc}") from exc

    replay_root = root / "replay"
    replay_root.mkdir(parents=True, exist_ok=True)
    output_path = replay_root / f"{name}.wav"
    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(CHANNELS)
        output.setsampwidth(SAMPLE_WIDTH_BYTES)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm)
    metadata = ReplayMetadata(
        name=name,
        filename=f"replay/{name}.wav",
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        duration_seconds=len(pcm) / (SAMPLE_RATE * SAMPLE_WIDTH_BYTES),
        sha256=hashlib.sha256(pcm).hexdigest(),
    )
    _update_replay_manifest(root, metadata)
    return metadata


def _update_manifest(root: Path, metadata: FixtureMetadata) -> None:
    fixtures = load_manifest(root)
    fixtures[metadata.name] = metadata
    payload = {
        "schema_version": 1,
        "privacy": "local-only; contains voice recordings; never commit",
        "fixtures": {name: asdict(value) for name, value in sorted(fixtures.items())},
    }
    (root / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _update_replay_manifest(root: Path, metadata: ReplayMetadata) -> None:
    path = root / "replay-manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema_version": 1, "replay": {}}
    payload["privacy"] = "local-only derivatives; never commit"
    payload["replay"][metadata.name] = asdict(metadata)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.realtime.fixtures")
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser("record", help="record one private local voice fixture")
    record.add_argument("name", choices=FIXTURE_NAMES)
    record.add_argument("--seconds", type=float, required=True)
    record.add_argument(
        "--wait-for-enter",
        action="store_true",
        help="open the microphone, then wait for Enter before capture starts",
    )
    trim = subparsers.add_parser("trim", help="create a replay derivative without changing the original")
    trim.add_argument("name", choices=FIXTURE_NAMES)
    trim.add_argument("--start", type=float, required=True)
    trim.add_argument("--end", type=float, required=True)
    subparsers.add_parser("list", help="list metadata without transcribing or playing fixtures")
    args = parser.parse_args(argv)

    if args.command == "list":
        fixtures = load_manifest()
        for name, metadata in sorted(fixtures.items()):
            print(f"{name}: {metadata.duration_seconds:.2f}s overflow_chunks={metadata.overflow_chunks}")
        return 0

    if args.command == "trim":
        metadata = trim_replay_fixture(name=args.name, start_seconds=args.start, end_seconds=args.end)
        print(f"Saved {metadata.filename}: {metadata.duration_seconds:.2f}s sha256={metadata.sha256[:12]}")
        return 0

    source = open_microphone_stream(sample_rate=SAMPLE_RATE, block_frames=DEFAULT_BLOCK_FRAMES)
    if args.wait_for_enter:
        input(f"Microphone ready for {args.name}; press Enter to start. ")
    print(f"Recording {args.name} for {args.seconds:.1f}s; speak now.", flush=True)
    metadata = record_fixture(source, name=args.name, duration_seconds=args.seconds)
    print(
        f"Saved {metadata.filename}: {metadata.duration_seconds:.2f}s "
        f"overflow_chunks={metadata.overflow_chunks} sha256={metadata.sha256[:12]}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
