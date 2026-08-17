from __future__ import annotations

import hashlib
import io
import json
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from src.evals.session_expiry_cues import generate_all_warnings
from src.session_expiry_cues import (
    CANONICAL_ASSETS,
    WARNING_PHRASES,
    SessionExpiryCueError,
    load_candidate,
    load_selected_asset,
    promote_selection,
    store_warning_candidate,
    synthesize_ready_tones,
)


def wav_fixture(*, duration_ms: int = 4_000, rate: int = 24_000, sample: int = 2_400) -> bytes:
    frames = duration_ms * rate // 1000
    edge = rate // 50
    samples = [0] * edge + [sample] * (frames - edge * 2) + [0] * edge
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return output.getvalue()


class SessionExpiryCueTests(unittest.TestCase):
    def test_fixed_scripts_are_bilingual_and_duration_neutral(self):
        self.assertEqual(set(WARNING_PHRASES), {"en", "zh-CN"})
        combined = " ".join(WARNING_PHRASES.values()).lower()
        for forbidden in ("10 minute", "20 minute", "十分钟", "二十分钟", "10 分钟", "20 分钟"):
            self.assertNotIn(forbidden, combined)
        self.assertIn("Hey Jarvis", WARNING_PHRASES["en"])
        self.assertIn("Hey Jarvis", WARNING_PHRASES["zh-CN"])

    def test_paid_batch_requires_authorization_and_is_exactly_six_calls(self):
        with self.assertRaises(SessionExpiryCueError):
            generate_all_warnings(owner_authorized=False, synthesizer=lambda _p, _i: wav_fixture())
        calls: list[tuple[str, str]] = []

        def fake(phrase: str, instructions: str) -> bytes:
            calls.append((phrase, instructions))
            return wav_fixture()

        with tempfile.TemporaryDirectory() as temporary:
            results = generate_all_warnings(
                root=Path(temporary), owner_authorized=True, synthesizer=fake
            )
            self.assertEqual(len(calls), 6)
            self.assertEqual(len(results), 6)
            self.assertEqual(
                [(item["locale"], item["candidate"]) for item in results],
                [
                    ("en", "candidate-01"), ("en", "candidate-02"), ("en", "candidate-03"),
                    ("zh-CN", "candidate-01"), ("zh-CN", "candidate-02"), ("zh-CN", "candidate-03"),
                ],
            )

    def test_live_client_disables_sdk_retries(self):
        from src.evals import session_expiry_cues as evaluator

        created: list[dict[str, object]] = []

        class FakeOpenAI:
            def __init__(self, **kwargs: object):
                created.append(kwargs)

        fake_settings = type("Settings", (), {"openai_api_key": "test-key"})()
        with patch.object(evaluator, "load_settings", return_value=fake_settings), patch.dict(
            "sys.modules", {"openai": type("OpenAIModule", (), {"OpenAI": FakeOpenAI})()}
        ):
            evaluator._openai_synthesizer()
        self.assertEqual(created, [{"api_key": "test-key", "max_retries": 0}])

    def test_warning_validation_rejects_wrong_phrase_rate_and_clipping(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            common = dict(
                root=root, locale="en", label="candidate-01",
                prompt_version="session-expiry-en-warm-v1",
            )
            with self.assertRaises(SessionExpiryCueError):
                store_warning_candidate(wav_data=wav_fixture(), transcript="Ten minutes are up.", **common)
            with self.assertRaises(SessionExpiryCueError):
                store_warning_candidate(
                    wav_data=wav_fixture(rate=16_000), transcript=WARNING_PHRASES["en"], **common
                )
            with self.assertRaises(SessionExpiryCueError):
                store_warning_candidate(
                    wav_data=wav_fixture(sample=32_767), transcript=WARNING_PHRASES["en"], **common
                )

    def test_ready_tones_are_three_deterministic_valid_candidates(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = synthesize_ready_tones(Path(first))
            two = synthesize_ready_tones(Path(second))
            self.assertEqual(len(one), 3)
            self.assertEqual(
                [item["sha256"] for item in one], [item["sha256"] for item in two]
            )
            self.assertEqual(len(set(item["sha256"] for item in one)), 3)
            for item in one:
                data, manifest = load_candidate(Path(item["audio_path"]))
                self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["sha256"])
                self.assertEqual(manifest["source"], "local_synthesis")

    def test_manifest_tampering_and_unconfirmed_promotion_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            warnings = generate_all_warnings(
                root=root / "candidates", owner_authorized=True,
                synthesizer=lambda _p, _i: wav_fixture(),
            )
            tones = synthesize_ready_tones(root / "candidates")
            selection = dict(
                project_root=root,
                english=Path(warnings[0]["audio_path"]),
                chinese=Path(warnings[3]["audio_path"]),
                ready=Path(tones[0]["audio_path"]),
            )
            with self.assertRaises(SessionExpiryCueError):
                promote_selection(confirmed_by_owner=False, **selection)
            promoted = promote_selection(confirmed_by_owner=True, **selection)
            self.assertEqual(set(promoted), {"en", "zh-CN", "ready"})
            for slot, relative in CANONICAL_ASSETS.items():
                self.assertTrue((root / relative).is_file(), slot)
                manifest = json.loads((root / relative.with_suffix(".json")).read_text())
                self.assertTrue(manifest["selected_by_owner"])
                data, selected = load_selected_asset(root / relative, expected_slot=slot)
                self.assertEqual(hashlib.sha256(data).hexdigest(), selected["sha256"])
            manifest_path = Path(warnings[1]["manifest_path"])
            manifest = json.loads(manifest_path.read_text())
            manifest["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(SessionExpiryCueError):
                load_candidate(Path(warnings[1]["audio_path"]))


if __name__ == "__main__":
    unittest.main()
