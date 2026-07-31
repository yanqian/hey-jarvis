import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from sidecar.probe_service import (
    ProbeError,
    ProbeState,
    build_session_config,
    create_realtime_call,
    load_env_file,
    load_probe_config,
    monitor_parent,
    multipart_call_body,
    reacquire_microphone,
    sanitize_event,
)


class FakeStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.closed = False

    def start(self):
        self.started = True
        callback = self.kwargs.get("callback")
        if callback:
            callback(b"\0\0" * 1_280, 1_280, None, False)

    def read(self, frames):
        return b"\0\0" * frames, False

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


class FakeSoundDevice:
    RawInputStream = FakeStream


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body


class ProbeServiceTests(unittest.TestCase):
    def test_env_file_and_config_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "OPENAI_API_KEY=secret-test\nREALTIME_MODEL=model-test\n",
                encoding="utf-8",
            )
            self.assertEqual(load_env_file(path)["OPENAI_API_KEY"], "secret-test")
            config = load_probe_config(
                {
                    "TAURI_SPIKE_TOKEN": "a" * 64,
                    "TAURI_SPIKE_PORT": "8871",
                    "TAURI_SPIKE_ENV_FILE": str(path),
                }
            )
        self.assertEqual(config["api_key"], "secret-test")
        self.assertEqual(config["model"], "model-test")

    def test_config_rejects_missing_token(self):
        with self.assertRaisesRegex(ProbeError, "TOKEN"):
            load_probe_config({})

    def test_session_config_keeps_realtime_audio_contract(self):
        session = build_session_config({"model": "m", "voice": "v"})
        self.assertEqual(session["model"], "m")
        self.assertEqual(session["audio"]["output"]["voice"], "v")
        turn = session["audio"]["input"]["turn_detection"]
        self.assertTrue(turn["create_response"])
        self.assertTrue(turn["interrupt_response"])
        self.assertEqual(turn["threshold"], 0.8)

    def test_multipart_contains_sdp_and_session(self):
        body = multipart_call_body(
            "v=0\r\n",
            {"type": "realtime"},
            boundary="fixed",
        )
        self.assertIn(b'name="sdp"', body)
        self.assertIn(b"application/sdp", body)
        self.assertIn(b'name="session"', body)
        self.assertIn(b'"type":"realtime"', body)

    def test_realtime_call_keeps_key_in_authorization_header(self):
        captured = {}

        def urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(b"v=0\r\nanswer")

        answer = create_realtime_call(
            api_key="secret-key",
            sdp="v=0\r\noffer",
            session={"type": "realtime"},
            urlopen=urlopen,
        )
        self.assertTrue(answer.startswith("v=0"))
        self.assertEqual(captured["timeout"], 20)
        self.assertEqual(captured["request"].headers["Authorization"], "Bearer secret-key")
        self.assertNotIn(b"secret-key", captured["request"].data)

    def test_events_are_allowlisted_and_content_redacted(self):
        event = sanitize_event(
            {
                "type": "microphone_acquired",
                "echoCancellation": True,
                "sampleRate": 48_000,
                "transcript": "private words",
                "api_key": "secret",
            }
        )
        self.assertEqual(event["sampleRate"], 48_000)
        self.assertNotIn("transcript", event)
        self.assertNotIn("api_key", event)
        with self.assertRaisesRegex(ProbeError, "allowlisted"):
            sanitize_event({"type": "transcription"})

    def test_report_requires_release_before_reacquisition_evidence(self):
        state = ProbeState({"token": "a" * 64})
        state.record({"type": "media_released", "reason": "user_stop"})
        state.record({"type": "reacquire_result", "ok": True, "reason": "reacquired"})
        report = state.report()
        self.assertTrue(report["media_released"])
        self.assertTrue(report["reacquired"])
        self.assertNotIn("token", json.dumps(report))

    def test_microphone_reacquisition_uses_one_bounded_read(self):
        result = reacquire_microphone(FakeSoundDevice)
        self.assertTrue(result["ok"])
        self.assertEqual(result["frames"], 1_280)

    def test_microphone_reacquisition_times_out_without_frames(self):
        class SilentStream(FakeStream):
            def start(self):
                self.started = True

        class SilentSoundDevice:
            RawInputStream = SilentStream

        result = reacquire_microphone(SilentSoundDevice, timeout=0.001)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "microphone_timeout")

    def test_parent_monitor_stops_orphaned_sidecar(self):
        class FakeServer:
            stopped = False

            def shutdown(self):
                self.stopped = True

        server = FakeServer()
        parents = iter((42, 42, 1))
        monitor_parent(
            server,
            42,
            getppid=lambda: next(parents),
            wait=lambda _interval: None,
        )
        self.assertTrue(server.stopped)


if __name__ == "__main__":
    unittest.main()
