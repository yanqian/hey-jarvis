import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path


SIDECAR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIDECAR_DIR))

from product_sidecar import (  # noqa: E402
    ACKNOWLEDGEMENT_RESOURCE,
    LifecycleDiagnostics,
    ProductRuntimeError,
    parse_private_credentials,
    run,
    validate_openai_credential,
)


def message(sequence, payload):
    return json.dumps(
        {
            "protocol_version": 2,
            "sequence": sequence,
            "session_id": "session-product-1",
            "payload": payload,
        }
    )


def credentials(openai="sk-test-private", finnhub=None):
    return json.dumps(
        {
            "kind": "private_credentials",
            "openai_api_key": openai,
            "finnhub_api_key": finnhub,
        }
    )


class FakeRuntime:
    control_url = "http://127.0.0.1:54321/?lease=session-product-1"

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    def availability(self):
        return "wake_listening"


class ProductSidecarTests(unittest.TestCase):
    def test_lifecycle_diagnostics_are_bounded_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            diagnostics = LifecycleDiagnostics(Path(directory), "session-product-1")
            diagnostics.record("runtime_ready", "wake_listening")
            diagnostics.record("transcript_secret", "ready")
            text = diagnostics.path.read_text(encoding="utf-8")
            record = json.loads(text)
            self.assertEqual(record["event"], "runtime_ready")
            self.assertEqual(record["session"], "session-product-1")
            self.assertNotIn("transcript_secret", text)

    def test_openai_credential_validation_distinguishes_valid_invalid_and_offline(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        calls = []

        def succeeds(request, timeout):
            calls.append((request, timeout))
            return Response()

        validate_openai_credential("sk-valid-test", urlopen=succeeds)
        self.assertEqual(calls[0][1], 10)
        self.assertEqual(calls[0][0].get_header("Authorization"), "Bearer sk-valid-test")

        def unauthorized(_request, timeout):
            del timeout
            raise urllib.error.HTTPError("url", 401, "unauthorized", {}, None)

        with self.assertRaisesRegex(ProductRuntimeError, "openai_credential_invalid"):
            validate_openai_credential("sk-invalid-test", urlopen=unauthorized)

        def offline(_request, timeout):
            del timeout
            raise urllib.error.URLError("offline")

        with self.assertRaisesRegex(ProductRuntimeError, "offline"):
            validate_openai_credential("sk-offline-test", urlopen=offline)

    def test_product_protocol_starts_health_checks_and_closes_runtime(self):
        runtime = FakeRuntime()
        calls = []

        def factory(**kwargs):
            calls.append(kwargs)
            return runtime

        incoming = "\n".join(
            [
                credentials(),
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
                env={"OPENAI_API_KEY": "sk-environment-must-not-win"},
            ),
            0,
        )
        payloads = [
            json.loads(line)["payload"] for line in output.getvalue().splitlines()
        ]
        self.assertEqual(payloads[0]["kind"], "ready")
        self.assertEqual(payloads[0]["control_url"], runtime.control_url)
        self.assertEqual(payloads[1]["event"], "voice_availability")
        self.assertEqual(payloads[1]["detail"], "wake_listening")
        self.assertEqual(payloads[2]["event"], "stopping")
        self.assertTrue(runtime.closed)
        self.assertEqual(calls[0]["resource_dir"], Path("/tmp/hey-jarvis-resources"))
        self.assertEqual(calls[0]["app_support_dir"], Path("/tmp/hey-jarvis-support"))
        self.assertEqual(calls[0]["env"]["OPENAI_API_KEY"], "sk-test-private")
        self.assertNotIn("sk-test-private", output.getvalue())

    def test_startup_failure_is_redacted_and_nonzero(self):
        def factory(**_kwargs):
            raise RuntimeError("OPENAI_API_KEY=sk-private")

        incoming = "\n".join(
            [
                credentials(),
                message(
                    1,
                    {
                        "kind": "startup",
                        "app_version": "0.1.0",
                        "app_support_dir": "/tmp/support",
                        "resource_dir": "/tmp/resources",
                    },
                ),
            ]
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

    def test_private_credentials_are_required_and_validated_before_protocol(self):
        self.assertEqual(run(io.StringIO(""), io.StringIO()), 2)
        with self.assertRaises(ProductRuntimeError):
            parse_private_credentials(credentials(openai="not-a-key"))
        with self.assertRaises(ProductRuntimeError):
            parse_private_credentials("{}")

        calls = []

        def factory(**kwargs):
            calls.append(kwargs)
            return FakeRuntime()

        incoming = "\n".join(
            [
                credentials(finnhub="stock-token"),
                message(
                    1,
                    {
                        "kind": "startup",
                        "app_version": "0.1.0",
                        "app_support_dir": "/tmp/support",
                        "resource_dir": "/tmp/resources",
                    },
                ),
            ]
        )
        output = io.StringIO()
        self.assertEqual(run(io.StringIO(incoming), output, runtime_factory=factory), 0)
        self.assertEqual(calls[0]["env"]["FINNHUB_API_KEY"], "stock-token")
        self.assertNotIn("stock-token", output.getvalue())

    def test_acknowledgement_resource_is_relative_to_bundle_resources(self):
        self.assertFalse(ACKNOWLEDGEMENT_RESOURCE.is_absolute())
        self.assertEqual(
            ACKNOWLEDGEMENT_RESOURCE.as_posix(),
            "assets/wake_acknowledgement_alloy.mp3",
        )


if __name__ == "__main__":
    unittest.main()
