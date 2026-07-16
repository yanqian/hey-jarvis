from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from spikes.realtime_webrtc import server


class _FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class RealtimeWebRTCProbeTests(unittest.TestCase):
    def test_load_config_requires_key_and_allows_probe_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / ".env"
            empty.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(server.ProbeError, "OPENAI_API_KEY"):
                server.load_probe_config({}, env_file=empty)

            key, model, voice = server.load_probe_config(
                {
                    "OPENAI_API_KEY": "sk-test-secret",
                    "REALTIME_PROBE_MODEL": "model-test",
                    "REALTIME_PROBE_VOICE": "voice-test",
                },
                env_file=empty,
            )
        self.assertEqual((key, model, voice), ("sk-test-secret", "model-test", "voice-test"))

    def test_mint_client_secret_uses_official_session_shape_and_returns_only_ephemeral_fields(self):
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _FakeResponse(
                {"value": "ek_ephemeral", "expires_at": 12345, "ignored": "do-not-return"}
            )

        result = server.mint_client_secret(
            api_key="sk-standard-secret",
            model="gpt-realtime-test",
            voice="marin",
            urlopen=fake_urlopen,
        )
        request = captured["request"]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, server.CLIENT_SECRET_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer sk-standard-secret")
        self.assertEqual(
            body,
            {
                "session": {
                    "type": "realtime",
                    "model": "gpt-realtime-test",
                    "audio": {"output": {"voice": "marin"}},
                }
            },
        )
        self.assertEqual(
            result,
            {
                "value": "ek_ephemeral",
                "expires_at": 12345,
                "model": "gpt-realtime-test",
                "voice": "marin",
            },
        )
        self.assertNotIn("sk-standard-secret", json.dumps(result))

    def test_server_rejects_non_loopback_binding(self):
        with self.assertRaisesRegex(server.ProbeError, "loopback"):
            server.build_server("0.0.0.0", 0)

    def test_static_routes_resolve_without_network_or_api_call(self):
        html_asset = server.resolve_static_asset("/?cache=no")
        javascript_asset = server.resolve_static_asset("/app.js")
        self.assertIsNotNone(html_asset)
        self.assertIsNotNone(javascript_asset)
        html = html_asset[0].decode("utf-8")
        javascript = javascript_asset[0].decode("utf-8")
        self.assertEqual(html_asset[1], "text/html; charset=utf-8")
        self.assertEqual(javascript_asset[1], "text/javascript; charset=utf-8")
        self.assertIsNone(server.resolve_static_asset("/../.env"))
        self.assertIn("Speakerphone Realtime WebRTC Probe", html)
        self.assertIn("RTCPeerConnection", javascript)

    def test_browser_probe_requests_processing_tracks_events_and_cleans_up(self):
        javascript = (server.STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        for requirement in (
            "echoCancellation: true",
            "noiseSuppression: true",
            "autoGainControl: true",
            "microphoneTrack.getSettings()",
            'fetch("https://api.openai.com/v1/realtime/calls"',
            'type === "response.output_audio.delta"',
            'type === "input_audio_buffer.speech_started"',
            "during_assistant_audio",
            "playLongTestAnswer",
            'type: "conversation.item.create"',
            'dataChannel.send(JSON.stringify({ type: "response.create" }))',
            "MAX_EVENTS = 200",
            "localStream.getTracks().forEach((track) => track.stop())",
            "peerConnection.close()",
            "audio.srcObject = null",
        ):
            self.assertIn(requirement, javascript)
        self.assertNotIn("OPENAI_API_KEY", javascript)
        self.assertNotIn("event.delta", javascript)

    def test_usage_guidance_defines_no_headphones_acceptance(self):
        guidance = (server.STATIC_ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "without headphones",
            "built-in microphone",
            "built-in speakers",
            "speaker echo caused a false interruption",
            "old answer stopped promptly",
            "microphone indicator turns off",
        ):
            self.assertIn(phrase, guidance)


if __name__ == "__main__":
    unittest.main()
