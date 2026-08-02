from __future__ import annotations

import json
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import internal_macos_release as release


ROOT = Path(__file__).resolve().parents[1]


def fake_app(base: Path, *, version: str = "0.1.0") -> Path:
    app = base / "Hey Jarvis.app"
    executable = app / "Contents/MacOS/hey-jarvis-mac"
    sidecar = app / "Contents/Resources/sidecar/hey-jarvis-sidecar"
    manifest = app / "Contents/Resources/packaging-manifests/build-manifest.json"
    icon = app / "Contents/Resources/Hey Jarvis.icns"
    for path in (executable, sidecar, manifest, icon):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    executable.chmod(0o755)
    sidecar.chmod(0o755)
    info = {
        "CFBundleDisplayName": "Hey Jarvis",
        "CFBundleIdentifier": "com.heyjarvis.desktop",
        "CFBundleExecutable": "hey-jarvis-mac",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSMinimumSystemVersion": "14.0",
        "NSMicrophoneUsageDescription": "Use the microphone to detect the wake phrase.",
        "CFBundleIconFile": "Hey Jarvis.icns",
    }
    (app / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
    return app


class InternalMacOSReleaseTests(unittest.TestCase):
    def test_identity_version_icon_and_usage_text_have_one_checked_contract(self):
        config = json.loads((ROOT / "app/src-tauri/tauri.conf.json").read_text())
        package = json.loads((ROOT / "app/package.json").read_text())
        cargo = (ROOT / "app/src-tauri/Cargo.toml").read_text()
        self.assertEqual(config["version"], package["version"])
        self.assertIn(f'version = "{config["version"]}"', cargo)
        self.assertEqual(config["identifier"], release.BUNDLE_ID)
        self.assertEqual(config["bundle"]["icon"], ["icons/icon.png"])
        self.assertEqual(config["bundle"]["macOS"]["minimumSystemVersion"], "14.0")

    def test_inspection_inventories_arm64_code_and_rejects_private_material(self):
        with tempfile.TemporaryDirectory() as directory:
            app = fake_app(Path(directory))
            with mock.patch.object(release, "_run_file", return_value="Mach-O 64-bit executable arm64"), mock.patch.object(
                release, "_signature_status", return_value="adhoc-no-distribution-trust"
            ):
                inspected = release.inspect_app(app, ROOT)
                self.assertEqual(inspected["version"], "0.1.0")
                self.assertEqual(inspected["architecture"], "arm64")
                self.assertEqual(len(inspected["nested_code"]), 2)

                (app / "Contents/Resources/leak.txt").write_text(
                    "/Users/example/Projects/hey-jarvis"
                )
                with self.assertRaisesRegex(release.ReleaseError, "developer filesystem path"):
                    release.inspect_app(app, ROOT)

                (app / "Contents/Resources/leak.txt").write_text(
                    "OPENAI_API_KEY=not-a-real-key"
                )
                with self.assertRaisesRegex(release.ReleaseError, "credential-shaped"):
                    release.inspect_app(app, ROOT)

                (app / "Contents/Resources/leak.txt").write_text(
                    "sk-proj-ABCDEF0123456789abcdef0123456789"
                )
                with self.assertRaisesRegex(release.ReleaseError, "credential-shaped"):
                    release.inspect_app(app, ROOT)

    def test_manifest_is_explicitly_internal_unsigned_and_checksum_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            app = fake_app(base)
            (base / release.REQUIRED_WARNING).write_text("internal")
            dmg = base / "Hey-Jarvis-0.1.0-INTERNAL-UNSIGNED-arm64.dmg"
            dmg.write_bytes(b"fake dmg")
            manifest = base / "release.manifest.json"
            checksum = base / "release.sha256"
            with mock.patch.object(release, "_run_file", return_value="Mach-O 64-bit executable arm64"), mock.patch.object(
                release, "_signature_status", return_value="none"
            ):
                written = release.write_release_files(ROOT, app, dmg, manifest, checksum)
                release.verify_release_files(ROOT, app, dmg, manifest, checksum)
                self.assertEqual(written["channel"], "internal-unsigned")
                self.assertTrue(written["distribution"]["trusted_source_required"])
                for key in (
                    "developer_id_signed",
                    "notarized",
                    "stapled",
                    "gatekeeper_ready",
                    "public_distribution",
                ):
                    self.assertFalse(written["distribution"][key])

                tampered = json.loads(manifest.read_text())
                tampered["distribution"]["notarized"] = True
                manifest.write_text(json.dumps(tampered))
                with self.assertRaisesRegex(release.ReleaseError, "forbidden distribution trust"):
                    release.verify_release_files(ROOT, app, dmg, manifest, checksum)

    def test_build_command_never_invokes_distribution_credentials(self):
        script = (ROOT / "scripts/build_internal_macos_release.sh").read_text()
        for marker in (
            "build_macos_sidecar.sh",
            "tauri -- build --bundles app",
            "INTERNAL-UNSIGNED",
            "hdiutil create",
            "internal_macos_release.py",
            "rollback",
            "Publish only a fully verified candidate",
        ):
            self.assertIn(marker, script)
        for forbidden in ("notarytool", "stapler", "security find-identity", "Developer ID Application"):
            self.assertNotIn(forbidden, script)

    def test_release_rust_excludes_compile_time_checkout_paths(self):
        native = (ROOT / "app/src-tauri/src/lib.rs").read_text()
        supervisor = (ROOT / "app/src-tauri/src/supervisor.rs").read_text()
        self.assertIn("#[cfg(not(debug_assertions))]\nfn development_sidecar_path", native)
        self.assertIn("#[cfg(not(debug_assertions))]\nfn development_python_interpreter", supervisor)


if __name__ == "__main__":
    unittest.main()
