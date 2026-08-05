from __future__ import annotations

import json
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

from src.config import load_settings
from src.realtime_ack_asset import CANONICAL_ACK_ASSET, CANONICAL_ACK_MANIFEST
from src.realtime_farewell_asset import CANONICAL_FAREWELL_ASSET, CANONICAL_FAREWELL_MANIFEST
from src.realtime_host import server
from src.realtime_host.coordinator import HandoffCoordinator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGLISH_ACK = PROJECT_ROOT / "assets/realtime_acknowledgement_alloy_en.wav"
ENGLISH_ACK_MANIFEST = ENGLISH_ACK.with_suffix(".json")
ENGLISH_FAREWELL = PROJECT_ROOT / "assets/realtime_farewell_alloy_en.wav"
ENGLISH_FAREWELL_MANIFEST = ENGLISH_FAREWELL.with_suffix(".json")


class FakeLease:
    def __init__(self) -> None:
        self.is_open = False

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False


class FakeHTTPServer:
    def __init__(self, address, handler) -> None:
        self.server_address = address
        self.handler = handler


class RealtimeLanguageCueTests(unittest.TestCase):
    def test_language_is_snapshotted_once_per_wake_and_defaults_safely(self):
        selected = ["zh-CN"]
        reads = []

        def language_provider():
            reads.append(selected[0])
            return selected[0]

        ids = iter(("session-one", "session-two", "session-three"))
        coordinator = HandoffCoordinator(
            FakeLease(),
            session_ids=lambda: next(ids),
            app_language_provider=language_provider,
        )
        coordinator.host_event("armed")

        first_session = coordinator.begin_handoff()
        first = coordinator.command_after(0)
        self.assertEqual(first["cue_locale"], "zh-CN")
        self.assertEqual(reads, ["zh-CN"])

        selected[0] = "en"
        self.assertEqual(first["cue_locale"], "zh-CN")
        self.assertEqual(reads, ["zh-CN"])
        coordinator.request_stop("test")
        stop = coordinator.command_after(first["command_id"])
        coordinator.host_event("stopped", first_session, reason="test")

        second_session = coordinator.begin_handoff()
        second = coordinator.command_after(stop["command_id"])
        self.assertEqual(second["cue_locale"], "en")
        self.assertEqual(reads, ["zh-CN", "en"])
        coordinator.request_stop("test")
        second_stop = coordinator.command_after(second["command_id"])
        coordinator.host_event("stopped", second_session, reason="test")

        selected[0] = "unsupported"
        coordinator.begin_handoff()
        third = coordinator.command_after(second_stop["command_id"])
        self.assertEqual(third["cue_locale"], "en")

    def test_preferences_reader_is_bounded_and_supports_only_two_locales(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences-v1.json"
            self.assertEqual(server.read_app_language(path), "en")
            path.write_text(json.dumps({"app_language": "zh-CN"}))
            self.assertEqual(server.read_app_language(path), "zh-CN")
            path.write_text(json.dumps({"app_language": "fr"}))
            self.assertEqual(server.read_app_language(path), "en")
            path.write_bytes(b"{" + b"x" * 5000)
            self.assertEqual(server.read_app_language(path), "en")

    def build_bilingual_server(self, preferences: Path):
        settings = load_settings(env={"BACKEND": "realtime"}, env_file=None)
        with patch.object(server, "HostHTTPServer", FakeHTTPServer):
            return server.build_server(
                acknowledgement_mode="cached",
                farewell_mode="cached",
                settings=settings,
                cached_acknowledgement_audio_path=PROJECT_ROOT / CANONICAL_ACK_ASSET,
                cached_acknowledgement_manifest_path=PROJECT_ROOT / CANONICAL_ACK_MANIFEST,
                cached_farewell_audio_path=PROJECT_ROOT / CANONICAL_FAREWELL_ASSET,
                cached_farewell_manifest_path=PROJECT_ROOT / CANONICAL_FAREWELL_MANIFEST,
                english_cached_acknowledgement_audio_path=ENGLISH_ACK,
                english_cached_acknowledgement_manifest_path=ENGLISH_ACK_MANIFEST,
                english_cached_farewell_audio_path=ENGLISH_FAREWELL,
                english_cached_farewell_manifest_path=ENGLISH_FAREWELL_MANIFEST,
                app_language_path=preferences,
            )

    def test_server_publishes_and_serves_all_four_validated_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            preferences = Path(directory) / "preferences-v1.json"
            preferences.write_text(json.dumps({"app_language": "en"}))
            host = self.build_bilingual_server(preferences)
            responses = []
            handler = object.__new__(server.HostRequestHandler)
            handler.server = host
            handler._json = lambda status, payload: responses.append((status, payload))
            handler.path = "/api/realtime-settings"
            handler.do_GET()

            self.assertEqual(responses[0][0], HTTPStatus.OK)
            cues = responses[0][1]["voice_cues"]
            self.assertEqual(set(cues), {"en", "zh-CN"})
            self.assertEqual(cues["en"]["acknowledgement"]["url"], "/acknowledgement.wav?locale=en")
            self.assertEqual(cues["en"]["farewell"]["url"], "/farewell.wav?locale=en")
            self.assertEqual(cues["zh-CN"]["acknowledgement"]["url"], "/acknowledgement.wav?locale=zh-CN")
            self.assertEqual(cues["zh-CN"]["farewell"]["url"], "/farewell.wav?locale=zh-CN")

            served = []
            handler._bytes = lambda status, body, kind: served.append((status, body, kind))
            for locale, expected in (("en", ENGLISH_ACK), ("zh-CN", PROJECT_ROOT / CANONICAL_ACK_ASSET)):
                handler.path = f"/acknowledgement.wav?locale={locale}"
                handler.do_GET()
                self.assertEqual(served[-1], (HTTPStatus.OK, expected.read_bytes(), "audio/wav"))
            for locale, expected in (("en", ENGLISH_FAREWELL), ("zh-CN", PROJECT_ROOT / CANONICAL_FAREWELL_ASSET)):
                handler.path = f"/farewell.wav?locale={locale}"
                handler.do_GET()
                self.assertEqual(served[-1], (HTTPStatus.OK, expected.read_bytes(), "audio/wav"))

            responses.clear()
            handler.path = "/farewell.wav?locale=fr"
            handler.do_GET()
            self.assertEqual(responses[-1][0], HTTPStatus.NOT_FOUND)

    def test_bilingual_startup_fails_closed_on_incomplete_or_stale_manifest_paths(self):
        with patch.object(server, "HostHTTPServer", FakeHTTPServer):
            with self.assertRaisesRegex(server.HostServerError, "configured together"):
                server.build_server(english_cached_acknowledgement_audio_path=ENGLISH_ACK)
            with self.assertRaisesRegex(server.HostServerError, "did not match"):
                server.build_server(
                    english_cached_acknowledgement_audio_path=ENGLISH_ACK,
                    english_cached_acknowledgement_manifest_path=ENGLISH_FAREWELL_MANIFEST,
                    english_cached_farewell_audio_path=ENGLISH_FAREWELL,
                    english_cached_farewell_manifest_path=ENGLISH_FAREWELL_MANIFEST,
                )

    def test_browser_preloads_both_languages_and_keeps_the_wake_snapshot(self):
        javascript = (PROJECT_ROOT / "src/realtime_host/static/app.js").read_text()
        acknowledgement = javascript[
            javascript.index("async function prepareCachedAcknowledgement"):
            javascript.index("async function prepareCachedFarewell")
        ]
        farewell = javascript[
            javascript.index("async function prepareCachedFarewell"):
            javascript.index("function resetCachedAcknowledgementPlayback")
        ]
        playback = javascript[
            javascript.index("async function startCachedAcknowledgement"):
            javascript.index("function showEndControl")
        ]
        self.assertIn('locales.join(",")!=="en,zh-CN"', acknowledgement)
        self.assertIn('locales.join(",")!=="en,zh-CN"', farewell)
        self.assertIn("cachedAcknowledgementUrls[command.cue_locale]", playback)
        self.assertIn("cachedFarewellUrls[activeCueLocale]", playback)
        self.assertNotIn("appLanguage", playback)
        self.assertIn("activeCueLocale=command.cue_locale", javascript)
        self.assertIn('if(!["en","zh-CN"].includes(command.cue_locale))', javascript)


if __name__ == "__main__":
    unittest.main()
