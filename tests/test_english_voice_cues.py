from __future__ import annotations

import hashlib
import io
import json
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from src.english_voice_cues import (
    CUES,
    EnglishVoiceCueError,
    load_candidate,
    prepare_selected_assets,
    promote_candidate,
    store_candidate,
)
from src.evals.english_voice_cues import generate_candidate


def wav_fixture(duration_ms: int = 700, sample_rate: int = 24_000) -> bytes:
    frames = duration_ms * sample_rate // 1000
    samples = [0] * (sample_rate // 50) + [1800] * (frames - sample_rate // 25) + [0] * (sample_rate // 50)
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return output.getvalue()


class EnglishVoiceCueTests(unittest.TestCase):
    def test_paid_generation_requires_explicit_authorization_and_bounded_label(self):
        with self.assertRaises(EnglishVoiceCueError):
            generate_candidate("ack", "candidate-01", style="light", owner_authorized=False)
        with self.assertRaises(EnglishVoiceCueError):
            generate_candidate("ack", "candidate-04", style="light", owner_authorized=True)

    def test_candidate_has_exact_locale_phrase_format_boundaries_and_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = store_candidate(
                Path(temporary), cue="ack", label="candidate-01", wav_data=wav_fixture(),
                transcript="I'm here. Yes?", prompt_version="english-ack-light-v1",
            )
            data, manifest = load_candidate(Path(result["audio_path"]))
            self.assertEqual(manifest["locale"], "en")
            self.assertEqual(manifest["phrase"], "I'm here. Yes?")
            self.assertEqual(manifest["sample_rate"], 24_000)
            self.assertEqual(manifest["format"], "wav_pcm_s16le_mono")
            self.assertLessEqual(manifest["leading_silence_ms"], 80)
            self.assertLessEqual(manifest["trailing_silence_ms"], 80)
            self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["sha256"])

    def test_wrong_phrase_rate_configuration_and_unconfirmed_promotion_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            common = dict(cue="farewell", label="candidate-01", prompt_version="english-farewell-light-v1")
            with self.assertRaises(EnglishVoiceCueError):
                store_candidate(root, wav_data=wav_fixture(), transcript="Goodbye.", **common)
            with self.assertRaises(EnglishVoiceCueError):
                store_candidate(root, wav_data=wav_fixture(sample_rate=16_000), transcript="See you.", **common)
            result = store_candidate(root, wav_data=wav_fixture(500), transcript="See you.", **common)
            with self.assertRaises(EnglishVoiceCueError):
                promote_candidate(Path(result["audio_path"]), project_root=root, confirmed_by_owner=False)

    def test_selected_assets_prepare_with_identical_digests_and_reject_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidates = root / "candidates"
            for cue, phrase in (("ack", "I'm here. Yes?"), ("farewell", "See you.")):
                result = store_candidate(
                    candidates, cue=cue, label="candidate-01", wav_data=wav_fixture(), transcript=phrase,
                    prompt_version=f"english-{cue}-light-v1",
                )
                promote_candidate(Path(result["audio_path"]), project_root=root, confirmed_by_owner=True)
            prepared = prepare_selected_assets(project_root=root, destination=root / "prepared")
            for cue, spec in CUES.items():
                canonical = root / spec.canonical_audio
                copied = Path(prepared[cue]["audio_path"])
                self.assertEqual(canonical.read_bytes(), copied.read_bytes())
                canonical_manifest = root / spec.canonical_manifest
                copied_manifest = Path(prepared[cue]["manifest_path"])
                self.assertEqual(canonical_manifest.read_bytes(), copied_manifest.read_bytes())
            farewell_manifest = root / CUES["farewell"].canonical_manifest
            value = json.loads(farewell_manifest.read_text())
            value["phrase"] = "Goodbye."
            farewell_manifest.write_text(json.dumps(value))
            with self.assertRaises(EnglishVoiceCueError):
                prepare_selected_assets(project_root=root, destination=root / "again")


if __name__ == "__main__":
    unittest.main()
