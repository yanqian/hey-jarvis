"""One-shot owner-led capture and promotion of a Realtime ACK candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from src.evals.realtime_common import PROJECT_ROOT, RealtimeRunnerBase, RealtimeScenarioError
from src.realtime_ack_asset import CANDIDATE_LABEL, prepare_selected_asset, promote_candidate


DEFAULT_CANDIDATE_ROOT = PROJECT_ROOT / "tmp" / "realtime-ack-candidates"


class RealtimeAckCaptureRunner(RealtimeRunnerBase):
    def run(self, *, label: str, manual_wake_provider: Callable[[], None]) -> dict[str, object]:
        if not CANDIDATE_LABEL.fullmatch(label):
            raise RealtimeScenarioError("ACK candidate label must look like candidate-01")
        initial = self.report()
        if initial.get("state") != "wake_owned" or initial.get("wake_microphone_open") is not True:
            raise RealtimeScenarioError("ACK capture requires wake_owned before arming")
        self.request(
            f"{self.base_url}/api/acknowledgement-capture/arm",
            method="POST",
            payload={"label": label},
        )
        manual_wake_provider()
        active = self.wait(
            lambda report: report.get("state") == "host_active"
            and any(
                isinstance(event, dict)
                and event.get("type") == "host_acknowledgement_candidate_saved"
                and event.get("candidate") == label
                for event in report.get("events", [])
            ),
            "digitally saved ACK candidate and input readiness",
        )
        self.stop()
        final = self.wait(
            lambda report: report.get("state") == "wake_owned"
            and report.get("wake_microphone_open") is True,
            "wake recovery after ACK capture",
        )
        events = final.get("events", [])
        return {
            "candidate": label,
            "saved": any(
                isinstance(event, dict)
                and event.get("type") == "host_acknowledgement_candidate_saved"
                and event.get("candidate") == label
                for event in events
            ),
            "input_ready": any(
                isinstance(event, dict) and event.get("type") == "host_connected"
                for event in events
            ),
            "wake_recovered": final.get("wake_microphone_open") is True,
            "audio_path": str(DEFAULT_CANDIDATE_ROOT / f"{label}.wav"),
            "manifest_path": str(DEFAULT_CANDIDATE_ROOT / f"{label}.json"),
        }


def main(argv: list[str] | None = None, *, input_fn: Callable[[str], str] = input) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.evals.realtime_ack_capture")
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture", help="capture one paid Realtime ACK candidate")
    capture.add_argument("label")
    capture.add_argument("--base-url", default="http://127.0.0.1:8770")
    capture.add_argument("--timeout", type=float, default=30.0)
    promote = commands.add_parser("promote", help="promote one explicitly selected candidate")
    promote.add_argument("candidate", type=Path)
    promote.add_argument(
        "--owner-confirmed",
        action="store_true",
        help="confirm that the owner auditioned and selected this exact candidate",
    )
    prepare = commands.add_parser("prepare", help="install the selected canonical asset locally")
    prepare.add_argument(
        "--destination",
        type=Path,
        default=PROJECT_ROOT / "var" / "realtime-ack.wav",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "promote":
            result = promote_candidate(
                args.candidate,
                project_root=PROJECT_ROOT,
                confirmed_by_owner=args.owner_confirmed,
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "prepare":
            result = prepare_selected_asset(
                project_root=PROJECT_ROOT,
                destination=args.destination,
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        runner = RealtimeAckCaptureRunner(
            scenario_id="ACK-CAPTURE",
            base_url=args.base_url,
            wake_fixture=None,
            transition_timeout=args.timeout,
        )
        result = runner.run(
            label=args.label,
            manual_wake_provider=lambda: input_fn(
                f"Press Enter, then say Hey Jarvis to capture {args.label}: "
            ),
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, RealtimeScenarioError) as exc:
        print(f"Realtime ACK capture failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
