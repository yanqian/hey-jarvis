"""Command-line entrypoint for the Hey Jarvis MVP."""

from __future__ import annotations

import argparse


def run_dry_run() -> int:
    """Exercise the skeleton path without microphone, OpenAI, or playback."""
    print("Assistant started")
    print("Dry run: microphone, wake word, OpenAI, and playback are not invoked")
    print("Returned to WAIT_WAKE")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.main")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run a dependency-free smoke path for recovery verification",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.dry_run:
        return run_dry_run()

    print("Hey Jarvis runtime is not implemented yet. Run with --dry-run for the skeleton smoke check.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
