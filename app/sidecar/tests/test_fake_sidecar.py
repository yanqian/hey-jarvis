import io
import json
import subprocess
import sys
import unittest
from pathlib import Path


SIDECAR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIDECAR_DIR))

from fake_sidecar import ProtocolError, parse_message, run  # noqa: E402


def message(sequence=1, session_id="session-1", payload=None):
    return json.dumps(
        {
            "protocol_version": 1,
            "sequence": sequence,
            "session_id": session_id,
            "payload": payload
            or {
                "kind": "startup",
                "app_version": "0.1.0",
                "app_support_dir": "/tmp/hey-jarvis-test",
            },
        }
    )


class FakeSidecarTests(unittest.TestCase):
    def test_startup_health_and_shutdown(self):
        incoming = "\n".join(
            [
                message(),
                message(
                    2,
                    payload={"kind": "lifecycle", "event": "health_check", "detail": None},
                ),
                message(3, payload={"kind": "shutdown", "reason": "test"}),
            ]
        )
        output = io.StringIO()

        self.assertEqual(run(io.StringIO(incoming), output), 0)
        payloads = [json.loads(line)["payload"] for line in output.getvalue().splitlines()]
        self.assertEqual([item["kind"] for item in payloads], ["ready", "lifecycle", "lifecycle"])
        self.assertEqual(payloads[1]["event"], "healthy")
        self.assertEqual(payloads[2]["event"], "stopping")

    def test_rejects_unknown_version_order_session_and_fields(self):
        cases = [
            message().replace('"protocol_version": 1', '"protocol_version": 2'),
            message(sequence=1),
            message(session_id="../bad"),
            message(payload={"kind": "startup", "app_version": "0.1.0", "extra": True}),
            message(payload={"kind": "unknown"}),
        ]
        parse_message(cases[0].replace('"protocol_version": 2', '"protocol_version": 1'), expected_session=None, last_sequence=0)
        with self.assertRaises(ProtocolError):
            parse_message(cases[0], expected_session=None, last_sequence=0)
        with self.assertRaises(ProtocolError):
            parse_message(cases[1], expected_session="session-1", last_sequence=1)
        for value in cases[2:]:
            with self.assertRaises(ProtocolError):
                parse_message(value, expected_session=None, last_sequence=0)

    def test_rejects_secret_bearing_payloads_and_oversized_messages(self):
        secret = message(
            payload={
                "kind": "session",
                "action": "start",
                "conversation_id": "sk-do-not-pass-secrets",
            }
        )
        with self.assertRaises(ProtocolError):
            parse_message(secret, expected_session=None, last_sequence=0)
        with self.assertRaises(ProtocolError):
            parse_message(" " * (32 * 1024 + 1), expected_session=None, last_sequence=0)

    def test_parent_pipe_eof_stops_process(self):
        process = subprocess.Popen(
            [sys.executable, str(SIDECAR_DIR / "fake_sidecar.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(message() + "\n")
        process.stdin.flush()
        ready = json.loads(process.stdout.readline())
        self.assertEqual(ready["payload"]["kind"], "ready")

        process.stdin.close()
        self.assertEqual(process.wait(timeout=2), 0)
        process.stdout.close()
        assert process.stderr is not None
        process.stderr.close()


if __name__ == "__main__":
    unittest.main()
