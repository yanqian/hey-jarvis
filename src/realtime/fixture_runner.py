"""Event-driven acoustic replay of private Realtime acceptance fixtures."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Callable

from src.realtime.fixtures import DEFAULT_FIXTURE_ROOT, FIXTURE_NAMES, load_manifest


class FixtureRunError(RuntimeError):
    """Raised when an expected Realtime acceptance transition is absent."""


def _json_request(url: str, *, method: str = "GET") -> dict[str, object]:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=3.0) as response:
        return json.loads(response.read())


class FixtureAcceptanceRunner:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8770",
        root: Path = DEFAULT_FIXTURE_ROOT,
        play: Callable[[Path], None] | None = None,
        request: Callable[..., dict[str, object]] = _json_request,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        transition_timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.root = root
        self.play = play or self._afplay
        self.request = request
        self.clock = clock
        self.sleep = sleep
        self.transition_timeout = transition_timeout
        self.session_id: str | None = None

    def run(self) -> dict[str, object]:
        missing = [name for name in FIXTURE_NAMES if name not in load_manifest(self.root)]
        if missing:
            raise FixtureRunError(f"missing private fixtures: {', '.join(missing)}")
        initial = self._report()
        if initial.get("state") != "wake_owned" or not initial.get("wake_microphone_open"):
            raise FixtureRunError("host must be armed and waiting with the wake microphone open")

        try:
            self.play(self._fixture_path("wake"))
            active = self._wait(lambda report: report.get("state") == "host_active", "ACTIVE_SESSION")
            connected = self._latest_event(active, "host_connected")
            self.session_id = str(connected.get("session_id")) if connected else None
            if not self.session_id:
                raise FixtureRunError("ACTIVE_SESSION did not expose a sanitized session identity")

            created = self._count("host_response_created")
            self.play(self._fixture_path("turn-1"))
            first_created = self._wait_count("host_response_created", created + 1, "turn-1 response.created")
            first = self._wait_event_after(
                "host_response_done",
                int(self._latest_event(first_created, "host_response_created")["at_ms"]),
                "turn-1 response.done",
            )
            self._require_event_reason(first, "completed", "turn-1")

            created += 1
            self.play(self._fixture_path("turn-2"))
            second_created = self._wait_count("host_response_created", created + 1, "turn-2 response.created")
            second = self._wait_event_after(
                "host_response_done",
                int(self._latest_event(second_created, "host_response_created")["at_ms"]),
                "turn-2 response.done",
            )
            self._require_event_reason(second, "completed", "turn-2")

            created += 1
            tool_calls = self._count("host_tool_call")
            self.play(self._fixture_path("calculator"))
            self._wait_count("host_tool_call", tool_calls + 1, "calculator tool call")
            # The first response closes the function call; the second is the
            # spoken continuation created after the local tool result.
            continuation_created = self._wait_count(
                "host_response_created",
                created + 2,
                "calculator continuation response.created",
            )
            continuation = self._latest_event(continuation_created, "host_response_created")
            calculator = self._wait_event_after(
                "host_response_done",
                int(continuation["at_ms"]),
                "calculator continuation response.done",
            )
            self._require_event_reason(calculator, "completed", "calculator continuation")

            created = self._count("host_response_created")
            self.request(f"{self.base_url}/api/long-answer", method="POST")
            long_report = self._wait_count("host_response_created", created + 1, "long answer response.created")
            long_created = self._latest_event(long_report, "host_response_created")
            self.sleep(1.0)
            self.play(self._fixture_path("barge-in"))
            long_created_ms = int(long_created["at_ms"])
            interrupted = self._wait(
                lambda report: self._first_event(
                    report,
                    "host_response_done",
                    after_ms=long_created_ms,
                )
                is not None,
                "barge-in response.done",
            )
            done = self._first_event(interrupted, "host_response_done", after_ms=long_created_ms)
            if done is None or done.get("reason") != "cancelled":
                actual = None if done is None else done.get("reason")
                raise FixtureRunError(f"barge-in response.done was {actual!r}, expected 'cancelled'")
            speech = self._latest_event(interrupted, "host_speech_started", after_ms=long_created_ms)
            if speech is None:
                raise FixtureRunError("barge-in cancellation had no speech_started after the long answer began")
            interruption_ms = int(done["at_ms"]) - int(speech["at_ms"])
            if interruption_ms < 0 or interruption_ms > 1_000:
                raise FixtureRunError(f"barge-in cancellation latency was not prompt: {interruption_ms}ms")
            barge_created = self._wait_count(
                "host_response_created",
                created + 2,
                "barge-in continuation response.created",
            )
            barge_continuation = self._latest_event(barge_created, "host_response_created")
            barge_answer = self._wait_event_after(
                "host_response_done",
                int(barge_continuation["at_ms"]),
                "barge-in continuation response.done",
            )
            self._require_event_reason(barge_answer, "completed", "barge-in continuation")

            self.play(self._fixture_path("end-phrase"))
            final = self._wait(
                lambda report: report.get("state") == "wake_owned"
                and report.get("wake_microphone_open") is True
                and any(
                    isinstance(event, dict)
                    and event.get("type") == "host_end_phrase_matched"
                    and event.get("session_id") == self.session_id
                    for event in report.get("events", [])
                ),
                "end phrase and fresh wake ownership",
            )
            summary = self._summary(final, interruption_ms=interruption_ms)
            if summary["speech_started"] != 5:
                raise FixtureRunError(
                    f"unexpected speech_started count: {summary['speech_started']!r}, expected 5 fixture utterances"
                )
            return summary
        except Exception:
            try:
                self.request(f"{self.base_url}/api/stop", method="POST")
            except Exception:
                pass
            raise

    def _report(self) -> dict[str, object]:
        return self.request(f"{self.base_url}/api/report")

    def _fixture_path(self, name: str) -> Path:
        replay = self.root / "replay" / f"{name}.wav"
        return replay if replay.exists() else self.root / f"{name}.wav"

    def _events(self) -> list[dict[str, object]]:
        events = self._report().get("events", [])
        return events if isinstance(events, list) else []

    def _count(self, event_type: str) -> int:
        return sum(self._matches(event, event_type) for event in self._events())

    def _wait_count(self, event_type: str, target: int, label: str) -> dict[str, object]:
        return self._wait(
            lambda report: sum(
                self._matches(event, event_type) for event in report.get("events", []) if isinstance(event, dict)
            )
            >= target,
            label,
        )

    def _wait_event_after(self, event_type: str, after_ms: int, label: str) -> dict[str, object]:
        report = self._wait(
            lambda candidate: self._first_event(candidate, event_type, after_ms=after_ms) is not None,
            label,
        )
        event = self._first_event(report, event_type, after_ms=after_ms)
        if event is None:  # Predicate and extraction deliberately share the same condition.
            raise FixtureRunError(f"timed out waiting for {label}")
        return event

    def _wait(self, predicate: Callable[[dict[str, object]], bool], label: str) -> dict[str, object]:
        deadline = self.clock() + self.transition_timeout
        while self.clock() < deadline:
            report = self._report()
            if predicate(report):
                return report
            self.sleep(0.1)
        raise FixtureRunError(f"timed out waiting for {label}")

    def _matches(self, event: dict[str, object], event_type: str) -> bool:
        return event.get("type") == event_type and (
            self.session_id is None or event.get("session_id") == self.session_id
        )

    def _latest_event(
        self,
        report: dict[str, object],
        event_type: str,
        *,
        after_ms: int | None = None,
    ) -> dict[str, object] | None:
        events = report.get("events", [])
        for event in reversed(events if isinstance(events, list) else []):
            if not isinstance(event, dict) or not self._matches(event, event_type):
                continue
            if after_ms is None or int(event.get("at_ms", -1)) >= after_ms:
                return event
        return None

    def _first_event(
        self,
        report: dict[str, object],
        event_type: str,
        *,
        after_ms: int,
    ) -> dict[str, object] | None:
        events = report.get("events", [])
        for event in events if isinstance(events, list) else []:
            if (
                isinstance(event, dict)
                and self._matches(event, event_type)
                and int(event.get("at_ms", -1)) >= after_ms
            ):
                return event
        return None

    def _require_event_reason(
        self,
        event: dict[str, object],
        expected: str,
        label: str,
    ) -> dict[str, object]:
        actual = event.get("reason")
        if actual != expected:
            raise FixtureRunError(f"{label} response.done was {actual!r}, expected {expected!r}")
        return event

    @staticmethod
    def _afplay(path: Path) -> None:
        subprocess.run(["afplay", str(path)], check=True)

    def _summary(self, report: dict[str, object], *, interruption_ms: int) -> dict[str, object]:
        events = report.get("events", [])
        session_events = [event for event in events if isinstance(event, dict) and event.get("session_id") == self.session_id]
        event_types = [event.get("type") for event in session_events]
        return {
            "result": "passed",
            "turns_completed": event_types.count("host_response_done"),
            "speech_started": event_types.count("host_speech_started"),
            "barge_in_cancel_latency_ms": interruption_ms,
            "calculator_calls": event_types.count("host_tool_call"),
            "end_phrase_matches": event_types.count("host_end_phrase_matched"),
            "recovered_to_wake": report.get("state") == "wake_owned" and report.get("wake_microphone_open") is True,
            "note": "acoustic replay may be suppressed by same-device echo cancellation",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.realtime.fixture_runner")
    parser.add_argument("--base-url", default="http://127.0.0.1:8770")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        summary = FixtureAcceptanceRunner(base_url=args.base_url, transition_timeout=args.timeout).run()
    except (FixtureRunError, OSError, subprocess.SubprocessError) as exc:
        print(f"Realtime fixture acceptance failed: {exc}")
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
