from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.normalize_zip import normalize


ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging" / "macos-sidecar"


class MacOSSidecarPackagingTests(unittest.TestCase):
    def test_dependency_locks_are_exact_and_have_no_optional_heavy_stack(self) -> None:
        combined = "\n".join(
            (PACKAGING / name).read_text(encoding="utf-8")
            for name in ("requirements.lock", "build-requirements.lock")
        )
        entries = [line for line in combined.splitlines() if line and not line.startswith("#")]
        self.assertTrue(entries)
        self.assertTrue(all(line.count("==") == 1 for line in entries))
        self.assertNotIn("onnxruntime", combined)
        self.assertNotIn("scikit-learn", combined)
        self.assertNotIn("scipy==", combined)
        self.assertIn("openwakeword==0.6.0", combined)
        self.assertIn("pyinstaller==6.16.0", combined)

    def test_model_lock_names_only_three_tflite_assets_with_sha256(self) -> None:
        entries = []
        for line in (PACKAGING / "models.lock").read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                name, digest, url = line.split("|")
                entries.append(name)
                self.assertEqual(len(digest), 64)
                int(digest, 16)
                self.assertTrue(url.startswith("https://github.com/dscripka/openWakeWord/releases/"))
        self.assertEqual(
            set(entries),
            {
                "melspectrogram.tflite",
                "embedding_model.tflite",
                "hey_jarvis_v0.1.tflite",
            },
        )

    def test_runtime_init_is_tflite_only_and_has_no_download_url(self) -> None:
        source = (PACKAGING / "openwakeword-runtime-init.py").read_text(encoding="utf-8")
        self.assertIn('inference_framework != "tflite"', source)
        self.assertNotIn("onnxruntime", source)
        self.assertIn('"download_url": ""', source)

    def test_spec_has_arm64_onedir_and_explicit_exclusions(self) -> None:
        source = (PACKAGING / "hey_jarvis_sidecar.spec").read_text(encoding="utf-8")
        self.assertIn('target_arch="arm64"', source)
        self.assertIn("COLLECT(", source)
        self.assertIn('ROOT / "src" / "realtime_host" / "static"', source)
        for asset in ("index.html", "app.js", "i18n.js", "styles.css"):
            self.assertIn(f'REALTIME_STATIC / "{asset}"', source)
        self.assertIn('"src/realtime_host/static"', source)
        for package in ("onnxruntime", "openai", "scipy", "sklearn", "webrtcvad"):
            self.assertIn(f'"{package}"', source)

    def test_tauri_bundles_the_complete_onedir_at_supervisor_path(self) -> None:
        config = json.loads((ROOT / "app" / "src-tauri" / "tauri.conf.json").read_text())
        resources = config["bundle"]["resources"]
        self.assertEqual(
            resources["../../build/macos-sidecar/hey-jarvis-sidecar"],
            "sidecar",
        )
        self.assertEqual(
            resources["../../build/macos-sidecar/manifests"],
            "packaging-manifests",
        )
        supervisor = (ROOT / "app" / "src-tauri" / "src" / "supervisor.rs").read_text()
        self.assertIn('resource_dir.join("sidecar/hey-jarvis-sidecar")', supervisor)

    def test_tauri_bundles_selected_english_cues_with_matching_digests(self) -> None:
        config = json.loads((ROOT / "app" / "src-tauri" / "tauri.conf.json").read_text())
        resources = config["bundle"]["resources"]
        for stem in ("realtime_acknowledgement_alloy_en", "realtime_farewell_alloy_en"):
            audio_source = ROOT / "assets" / f"{stem}.wav"
            manifest_source = ROOT / "assets" / f"{stem}.json"
            self.assertEqual(resources[f"../../assets/{stem}.wav"], f"assets/{stem}.wav")
            self.assertEqual(resources[f"../../assets/{stem}.json"], f"assets/{stem}.json")
            manifest = json.loads(manifest_source.read_text())
            self.assertTrue(manifest["selected_by_owner"])
            self.assertEqual(manifest["locale"], "en")
            self.assertEqual(hashlib.sha256(audio_source.read_bytes()).hexdigest(), manifest["sha256"])

    def test_zip_normalization_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            with zipfile.ZipFile(first, "w") as archive:
                archive.writestr("b.pyc", b"b")
                archive.writestr("a.pyc", b"a")
            with zipfile.ZipFile(second, "w") as archive:
                archive.writestr("a.pyc", b"a")
                archive.writestr("b.pyc", b"b")
            normalize(first)
            normalize(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(
                hashlib.sha256(first.read_bytes()).hexdigest(),
                hashlib.sha256(second.read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
