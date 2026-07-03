"""Command-line entrypoint for the Hey Jarvis MVP."""

from __future__ import annotations

import argparse

from .config import collect_diagnostics, format_diagnostics


def run_dry_run() -> int:
    """Exercise the skeleton path without microphone, OpenAI, or playback."""
    print("Assistant started")
    print("Dry run: microphone, wake word, OpenAI, and playback are not invoked")
    print("Returned to WAIT_WAKE")
    return 0


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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.dry_run:
        return run_dry_run()
    if args.diagnose:
        report = collect_diagnostics()
        print(format_diagnostics(report))
        return 1 if report.has_errors else 0

    print("Hey Jarvis runtime is not implemented yet. Run with --dry-run for the skeleton smoke check.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
