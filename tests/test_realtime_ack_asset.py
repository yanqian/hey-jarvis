from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace

from src.realtime_ack_asset import (
    ACK_PHRASE,
    RealtimeAckAssetError,
    inspect_wav,
    prepare_selected_asset,
    promote_candidate,
    store_candidate,
)
from src.evals.realtime_ack_capture import RealtimeAckCaptureRunner
from src.realtime_host import server
from src.realtime_host.coordinator import HandoffCoordinator, HandoffError


class FakeLease:
    def __init__(self) -> None:
        self.is_open = False

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False


def wav_fixture(*, seconds: float = 1.0, sample_rate: int = 24_000) -> bytes:
    frames = []
    for index in range(round(seconds * sample_rate)):
        active = sample_rate // 10 <= index < round(seconds * sample_rate) - sample_rate // 10
        value = round(math.sin(index * math.tau * 220 / sample_rate) * 8_000) if active else 0
        frames.append(value)
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(struct.pack(f"<{len(frames)}h", *frames))
    return output.getvalue()


class RealtimeAckAssetTests(unittest.TestCase):
    def test_capture_runner_arms_one_label_and_requires_saved_recovery(self):
        calls: list[tuple[str, str, object]] = []
        reports = iter(
            [
                {"state": "wake_owned", "wake_microphone_open": True, "events": []},
                {
                    "state": "host_active",
                    "wake_microphone_open": False,
                    "events": [
                        {"type": "host_acknowledgement_candidate_saved", "candidate": "candidate-01"},
                        {"type": "host_connected"},
                    ],
                },
                {
                    "state": "wake_owned",
                    "wake_microphone_open": True,
                    "events": [
                        {"type": "host_acknowledgement_candidate_saved", "candidate": "candidate-01"},
                        {"type": "host_connected"},
                    ],
                },
            ]
        )

        def request(url: str, *, method: str = "GET", payload=None):
            calls.append((url, method, payload))
            if url.endswith("/api/report"):
                return next(reports)
            return {"status": "ok"}

        wakes: list[bool] = []
        runner = RealtimeAckCaptureRunner(
            scenario_id="ACK-CAPTURE",
            base_url="http://loopback",
            wake_fixture=None,
            request=request,
            clock=lambda: 0.0,
            sleep=lambda _seconds: None,
        )
        result = runner.run(label="candidate-01", manual_wake_provider=lambda: wakes.append(True))
        self.assertEqual(wakes, [True])
        self.assertTrue(result["saved"] and result["input_ready"] and result["wake_recovered"])
        self.assertIn(
            ("http://loopback/api/acknowledgement-capture/arm", "POST", {"label": "candidate-01"}),
            calls,
        )

    def test_candidate_is_trimmed_validated_and_manifested_without_private_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = store_candidate(
                Path(tmp),
                label="candidate-01",
                wav_data=wav_fixture(),
                transcript="嗯，我在，请说。",
                model="gpt-realtime-2.1",
                voice="alloy",
                output_gain=0.5,
            )
            audio = Path(result["audio_path"]).read_bytes()
            manifest = json.loads(Path(result["manifest_path"]).read_text())
            self.assertLess(inspect_wav(audio).duration_ms, 1_000)
            self.assertEqual(manifest["phrase"], ACK_PHRASE)
            self.assertEqual(manifest["sha256"], hashlib.sha256(audio).hexdigest())
            self.assertFalse({"session_id", "audio", "transcript", "sdp", "ice"} & set(manifest))

    def test_candidate_rejects_wrong_phrase_format_duration_and_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            common = {
                "root": Path(tmp),
                "wav_data": wav_fixture(),
                "model": "gpt-realtime-2.1",
                "voice": "alloy",
                "output_gain": 0.5,
            }
            with self.assertRaises(RealtimeAckAssetError):
                store_candidate(label="answer-01", transcript=ACK_PHRASE, **common)
            with self.assertRaises(RealtimeAckAssetError):
                store_candidate(label="candidate-01", transcript="普通回答", **common)
            with self.assertRaises(RealtimeAckAssetError):
                store_candidate(
                    label="candidate-01",
                    transcript=ACK_PHRASE,
                    wav_data=b"not-wav",
                    root=Path(tmp),
                    model="gpt-realtime-2.1",
                    voice="alloy",
                    output_gain=0.5,
                )

    def test_promotion_requires_owner_confirmation_and_matching_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = store_candidate(
                root / "candidates",
                label="candidate-02",
                wav_data=wav_fixture(),
                transcript=ACK_PHRASE,
                model="gpt-realtime-2.1",
                voice="alloy",
                output_gain=0.5,
            )
            path = Path(candidate["audio_path"])
            with self.assertRaisesRegex(RealtimeAckAssetError, "confirmation"):
                promote_candidate(path, project_root=root, confirmed_by_owner=False)
            promoted = promote_candidate(path, project_root=root, confirmed_by_owner=True)
            self.assertTrue(Path(promoted["audio_path"]).is_file())
            self.assertTrue(json.loads(Path(promoted["manifest_path"]).read_text())["selected_by_owner"])
            prepared = prepare_selected_asset(
                project_root=root,
                destination=root / "var" / "realtime-ack.wav",
            )
            self.assertEqual(
                hashlib.sha256(Path(prepared["audio_path"]).read_bytes()).hexdigest(),
                promoted["sha256"],
            )

    def test_capture_is_one_shot_correlated_and_blocks_completion_until_saved(self):
        coordinator = HandoffCoordinator(FakeLease(), session_ids=lambda: "session-1")
        coordinator.host_event("armed")
        coordinator.request_realtime_acknowledgement_capture("candidate-03")
        session_id = coordinator.begin_handoff()
        command = coordinator.command_after(0)
        self.assertEqual(command["acknowledgement_capture_label"], "candidate-03")
        coordinator.host_event("transport_connected", session_id)
        coordinator.host_event("session_created", session_id)
        coordinator.host_event("session_configured", session_id)
        coordinator.host_event("realtime_ack_response_created", session_id)
        coordinator.host_event("realtime_ack_playback_started", session_id)
        coordinator.host_event("realtime_ack_response_done", session_id, reason="completed")
        coordinator.host_event("realtime_ack_playback_stopped", session_id)
        self.assertFalse(coordinator.realtime_acknowledgement_complete)
        with self.assertRaises(HandoffError):
            coordinator.accept_realtime_acknowledgement_capture("candidate-04")
        coordinator.accept_realtime_acknowledgement_capture("candidate-03")
        self.assertTrue(coordinator.realtime_acknowledgement_complete)
        with self.assertRaises(HandoffError):
            coordinator.accept_realtime_acknowledgement_capture("candidate-03")

    def test_loopback_upload_saves_only_an_armed_correlated_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            coordinator = HandoffCoordinator(FakeLease(), session_ids=lambda: "session-1")
            coordinator.host_event("armed")
            coordinator.request_realtime_acknowledgement_capture("candidate-05")
            session_id = coordinator.begin_handoff()
            for event in ("transport_connected", "session_created", "session_configured", "realtime_ack_response_created", "realtime_ack_playback_started"):
                coordinator.host_event(event, session_id)
            payload = json.dumps(
                {
                    "label": "candidate-05",
                    "transcript": ACK_PHRASE,
                    "audio": base64.b64encode(wav_fixture()).decode(),
                }
            ).encode()
            responses: list[tuple[int, dict[str, object]]] = []
            handler = object.__new__(server.HostRequestHandler)
            handler.path = "/api/acknowledgement-capture/candidate"
            handler.server = SimpleNamespace(
                coordinator=coordinator,
                capability_lease=None,
                acknowledgement_candidate_root=Path(tmp),
                settings=SimpleNamespace(
                    realtime_model="gpt-realtime-2.1",
                    realtime_voice="alloy",
                    realtime_output_volume=0.5,
                ),
            )
            handler.headers = {"Content-Length": str(len(payload)), "Content-Type": "application/json"}
            handler.rfile = io.BytesIO(payload)
            handler._json = lambda status, body: responses.append((int(status), dict(body)))
            handler.do_POST()
            self.assertEqual(responses[-1][0], 201)
            self.assertTrue((Path(tmp) / "candidate-05.wav").is_file())
            handler.rfile = io.BytesIO(payload)
            handler.do_POST()
            self.assertEqual(responses[-1][0], 409)

    def test_browser_capture_is_remote_stream_only_and_bounded_to_ack_metadata(self):
        javascript = Path("src/realtime_host/static/app.js").read_text()
        self.assertIn("createAcknowledgementCapture(remoteStream)", javascript)
        self.assertIn("encodeMonoWav", javascript)
        self.assertIn('metadata:{purpose:"acknowledgement"}', javascript)
        self.assertIn("response.output_audio_transcript.done", javascript)
        self.assertIn("/api/acknowledgement-capture/candidate", javascript)
        capture = javascript.split("function createAcknowledgementCapture", 1)[1].split(
            "function responseTranscript", 1
        )[0]
        self.assertNotIn("getUserMedia", capture)
        self.assertNotIn("warmStream", capture)


if __name__ == "__main__":
    unittest.main()
