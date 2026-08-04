from __future__ import annotations

import json
import unittest
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.config import load_settings
from src.realtime.controller import RealtimeSessionController
from src.realtime_ack_asset import CANONICAL_ACK_ASSET, CANONICAL_ACK_MANIFEST
from src.realtime_host import server
from src.realtime_host.coordinator import HandoffCoordinator, HandoffError, HandoffState


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeLease:
    def __init__(self) -> None:
        self.is_open = False
        self.chunks = [b"wake", b"wake"]

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def read_chunk(self) -> bytes:
        return self.chunks.pop(0)


class FakeDetector:
    def detect(self, chunk: bytes) -> bool:
        return chunk == b"wake"


def cached_coordinator(clock: FakeClock | None = None) -> HandoffCoordinator:
    coordinator = HandoffCoordinator(
        FakeLease(),
        clock=clock or (lambda: 1.0),
        session_ids=lambda: "session-cached",
        acknowledgement_mode="cached",
    )
    coordinator.host_event("armed")
    return coordinator


class CachedAcknowledgementTests(unittest.TestCase):
    def test_cached_playback_can_finish_before_configuration(self):
        coordinator = cached_coordinator()
        session_id = coordinator.begin_handoff()
        self.assertEqual(coordinator.command_after(0)["acknowledgement_mode"], "cached")
        coordinator.host_event("cached_ack_playback_started", session_id)
        coordinator.host_event("cached_ack_playback_stopped", session_id)
        self.assertTrue(coordinator.cached_acknowledgement_complete)
        coordinator.host_event("transport_connected", session_id)
        coordinator.host_event("session_created", session_id)
        coordinator.host_event("session_configured", session_id)
        coordinator.enable_host_input()
        coordinator.host_event("connected", session_id)
        self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_configuration_can_finish_before_cached_playback(self):
        coordinator = cached_coordinator()
        session_id = coordinator.begin_handoff()
        coordinator.host_event("transport_connected", session_id)
        coordinator.host_event("session_created", session_id)
        coordinator.host_event("session_configured", session_id)
        with self.assertRaisesRegex(HandoffError, "before enablement"):
            coordinator.host_event("connected", session_id)
        coordinator.host_event("cached_ack_playback_started", session_id)
        self.assertFalse(coordinator.cached_acknowledgement_complete)
        coordinator.host_event("cached_ack_playback_stopped", session_id)
        coordinator.enable_host_input()
        coordinator.host_event("connected", session_id)
        self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_cached_playback_rejects_duplicates_and_wrong_mode(self):
        coordinator = cached_coordinator()
        session_id = coordinator.begin_handoff()
        with self.assertRaisesRegex(HandoffError, "out of order"):
            coordinator.host_event("cached_ack_playback_stopped", session_id)
        coordinator.host_event("cached_ack_playback_started", session_id)
        with self.assertRaisesRegex(HandoffError, "unexpected"):
            coordinator.host_event("cached_ack_playback_started", session_id)

        realtime = HandoffCoordinator(FakeLease(), session_ids=lambda: "session-live", acknowledgement_mode="realtime")
        realtime.host_event("armed")
        live_session = realtime.begin_handoff()
        with self.assertRaisesRegex(HandoffError, "unexpected"):
            realtime.host_event("cached_ack_playback_started", live_session)

    def test_controller_waits_for_both_barriers_without_local_playback(self):
        for playback_first in (True, False):
            with self.subTest(playback_first=playback_first):
                clock = FakeClock()
                coordinator = cached_coordinator(clock)
                local_calls: list[str] = []
                connected = False

                def sleep(seconds: float) -> None:
                    nonlocal connected
                    clock.advance(max(seconds, 0.1))
                    if coordinator.state == HandoffState.HOST_STARTING:
                        if playback_first:
                            coordinator.host_event("cached_ack_playback_started", coordinator.session_id)
                            coordinator.host_event("cached_ack_playback_stopped", coordinator.session_id)
                        coordinator.host_event("transport_connected", coordinator.session_id)
                        coordinator.host_event("session_created", coordinator.session_id)
                        coordinator.host_event("session_configured", coordinator.session_id)
                    elif coordinator.state == HandoffState.HOST_READY:
                        if not coordinator.cached_acknowledgement_complete:
                            coordinator.host_event("cached_ack_playback_started", coordinator.session_id)
                            coordinator.host_event("cached_ack_playback_stopped", coordinator.session_id)
                        else:
                            connected = True
                            coordinator.host_event("connected", coordinator.session_id)
                    elif coordinator.state == HandoffState.HOST_ACTIVE:
                        coordinator.request_stop("test")
                    elif coordinator.state == HandoffState.HOST_STOPPING:
                        coordinator.host_event("stopped", coordinator.session_id, reason="test")

                result = RealtimeSessionController(
                    coordinator=coordinator,
                    wake_detector=FakeDetector(),
                    play_acknowledgement=lambda: local_calls.append("played"),
                    idle_timeout_seconds=2.0,
                    max_duration_seconds=10.0,
                    clock=clock,
                    sleep=sleep,
                ).run_once()
                self.assertTrue(connected)
                self.assertEqual(local_calls, [])
                self.assertTrue(result.recovered_to_wake)

    def test_cached_playback_timeout_stops_and_restores_wake_ownership(self):
        clock = FakeClock()
        coordinator = cached_coordinator(clock)

        def sleep(seconds: float) -> None:
            clock.advance(max(seconds, 0.1))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event(
                    "stopped",
                    coordinator.session_id,
                    reason="cached_acknowledgement_timeout",
                )

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=FakeDetector(),
            play_acknowledgement=lambda: self.fail("local ACK must not play"),
            idle_timeout_seconds=2.0,
            max_duration_seconds=10.0,
            connect_timeout_seconds=0.3,
            close_timeout_seconds=0.3,
            poll_seconds=0.1,
            clock=clock,
            sleep=sleep,
        ).run_once()
        self.assertEqual(result.reason, "cached_acknowledgement_timeout")
        self.assertTrue(result.recovered_to_wake)

    def test_server_exposes_only_validated_cached_metadata_and_audio(self):
        manifest = json.loads((PROJECT_ROOT / CANONICAL_ACK_MANIFEST).read_text())
        settings = load_settings(env={"BACKEND": "realtime"}, env_file=None)
        responses: list[tuple[HTTPStatus, dict[str, object]]] = []
        handler = object.__new__(server.HostRequestHandler)
        handler.path = "/api/realtime-settings"
        handler.server = SimpleNamespace(
            acknowledgement_mode="cached",
            cached_acknowledgement_manifest=manifest,
        )
        handler._json = lambda status, payload: responses.append((status, dict(payload)))
        with patch.object(server, "load_settings", return_value=settings):
            handler.do_GET()
        acknowledgement = responses[0][1]["acknowledgement"]
        self.assertEqual(acknowledgement["url"], "/acknowledgement.wav")
        self.assertEqual(acknowledgement["duration_ms"], 2429)
        self.assertNotIn("phrase", json.dumps(responses))

        served: list[tuple[HTTPStatus, bytes, str]] = []
        handler.path = "/acknowledgement.wav"
        handler.server.cached_acknowledgement_audio = (PROJECT_ROOT / CANONICAL_ACK_ASSET).read_bytes()
        handler._bytes = lambda status, body, content_type: served.append((status, body, content_type))
        handler.do_GET()
        self.assertEqual(served[0][0], HTTPStatus.OK)
        self.assertEqual(served[0][2], "audio/wav")
        self.assertEqual(len(served[0][1]), (PROJECT_ROOT / CANONICAL_ACK_ASSET).stat().st_size)

    def test_cached_startup_rejects_missing_or_voice_mismatched_assets_before_binding(self):
        with self.assertRaisesRegex(server.HostServerError, "missing"):
            server.build_server(
                acknowledgement_mode="cached",
                cached_acknowledgement_audio_path=Path("missing.wav"),
                cached_acknowledgement_manifest_path=Path("missing.json"),
            )
        mismatched = load_settings(
            env={"BACKEND": "realtime", "REALTIME_VOICE": "marin"},
            env_file=None,
        )
        with self.assertRaisesRegex(server.HostServerError, "does not match"):
            server.build_server(
                acknowledgement_mode="cached",
                settings=mismatched,
                cached_acknowledgement_audio_path=PROJECT_ROOT / CANONICAL_ACK_ASSET,
                cached_acknowledgement_manifest_path=PROJECT_ROOT / CANONICAL_ACK_MANIFEST,
            )

    def test_browser_starts_cached_ack_before_handoff_await_and_defers_remote_swap(self):
        javascript = (PROJECT_ROOT / "src/realtime_host/static/app.js").read_text()
        start = javascript.index('if(command.acknowledgement_mode==="cached")startCachedAcknowledgement(command)')
        microphone = javascript.index('await hostEvent("microphone_requested")', start)
        self.assertLess(start, microphone)
        self.assertIn('cachedAcknowledgementPending)return', javascript)
        self.assertIn('hostEvent("cached_ack_playback_started")', javascript)
        self.assertIn('hostEvent("cached_ack_playback_stopped")', javascript)
        self.assertIn('catch(error){releasePageMedia();sessionConfig=null', javascript)
        cached_function = javascript[javascript.index("async function startCachedAcknowledgement"):javascript.index("function showEndControl")]
        self.assertNotIn("response.create", cached_function)
        self.assertIn("track.enabled=false", javascript)


if __name__ == "__main__":
    unittest.main()
