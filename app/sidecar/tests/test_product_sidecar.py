import io
import json
import sys
import unittest
from pathlib import Path


SIDECAR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIDECAR_DIR))

from product_sidecar import ACKNOWLEDGEMENT_RESOURCE, run  # noqa: E402


def message(sequence, payload):
    return json.dumps(
        {
            "protocol_version": 2,
            "sequence": sequence,
            "session_id": "session-product-1",
            "payload": payload,
        }
    )


class FakeRuntime:
    control_url = "http://127.0.0.1:54321/?lease=session-product-1"

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class ProductSidecarTests(unittest.TestCase):
    def test_product_protocol_starts_health_checks_and_closes_runtime(self):
        runtime = FakeRuntime()
        calls = []

        def factory(**kwargs):
            calls.append(kwargs)
            return runtime

        incoming = "\n".join(
            [
                message(
                    1,
                    {
                        "kind": "startup",
                        "app_version": "0.1.0",
                        "app_support_dir": "/tmp/hey-jarvis-support",
                        "resource_dir": "/tmp/hey-jarvis-resources",
                    },
                ),
                message(
                    2,
                    {"kind": "lifecycle", "event": "health_check", "detail": None},
                ),
                message(3, {"kind": "shutdown", "reason": "test"}),
            ]
        )
        output = io.StringIO()

        self.assertEqual(
            run(
                io.StringIO(incoming),
                output,
                runtime_factory=factory,
                env={"OPENAI_API_KEY": "test-only"},
            ),
            0,
        )
        payloads = [
            json.loads(line)["payload"] for line in output.getvalue().splitlines()
        ]
        self.assertEqual(payloads[0]["kind"], "ready")
        self.assertEqual(payloads[0]["control_url"], runtime.control_url)
        self.assertEqual(payloads[1]["event"], "healthy")
        self.assertEqual(payloads[2]["event"], "stopping")
        self.assertTrue(runtime.closed)
        self.assertEqual(calls[0]["resource_dir"], Path("/tmp/hey-jarvis-resources"))
        self.assertEqual(calls[0]["app_support_dir"], Path("/tmp/hey-jarvis-support"))

    def test_startup_failure_is_redacted_and_nonzero(self):
        def factory(**_kwargs):
            raise RuntimeError("OPENAI_API_KEY=sk-private")

        incoming = message(
            1,
            {
                "kind": "startup",
                "app_version": "0.1.0",
                "app_support_dir": "/tmp/support",
                "resource_dir": "/tmp/resources",
            },
        )
        output = io.StringIO()

        self.assertEqual(
            run(io.StringIO(incoming), output, runtime_factory=factory),
            1,
        )
        result = output.getvalue()
        self.assertIn("startup_RuntimeError", result)
        self.assertNotIn("sk-private", result)
        self.assertNotIn("OPENAI_API_KEY", result)

    def test_acknowledgement_resource_is_relative_to_bundle_resources(self):
        self.assertFalse(ACKNOWLEDGEMENT_RESOURCE.is_absolute())
        self.assertEqual(
            ACKNOWLEDGEMENT_RESOURCE.as_posix(),
            "assets/wake_acknowledgement_alloy.mp3",
        )


if __name__ == "__main__":
    unittest.main()
