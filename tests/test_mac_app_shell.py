import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


class MacAppShellTests(unittest.TestCase):
    def test_product_shell_has_stable_identity_and_minimum_capabilities(self):
        config = json.loads((APP / "src-tauri" / "tauri.conf.json").read_text())
        self.assertEqual(config["productName"], "Hey Jarvis")
        self.assertEqual(config["identifier"], "com.heyjarvis.desktop")
        self.assertEqual(config["bundle"]["macOS"]["minimumSystemVersion"], "14.0")
        self.assertFalse(config["bundle"]["active"])

        capability = json.loads(
            (APP / "src-tauri" / "capabilities" / "default.json").read_text()
        )
        self.assertEqual(capability["windows"], ["main"])
        self.assertEqual(capability["permissions"], ["core:default"])

    def test_product_does_not_import_or_copy_spike_source(self):
        forbidden = ("spikes/tauri_realtime", "tauri-realtime-probe", "PROBE_PORT")
        product_files = [
            path
            for path in APP.rglob("*")
            if path.is_file()
            and "node_modules" not in path.parts
            and "target" not in path.parts
            and path.suffix in {".json", ".rs", ".py", ".js", ".html", ".css", ".toml"}
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in product_files)
        for marker in forbidden:
            self.assertNotIn(marker, combined)

    def test_frontend_discloses_f087_non_media_boundary(self):
        page = (APP / "src" / "index.html").read_text(encoding="utf-8")
        self.assertIn("does not access the microphone or OpenAI", page)
        self.assertIn("Check sidecar", page)
        self.assertIn("Restart sidecar", page)

    def test_architecture_records_three_part_ownership_and_freeze_points(self):
        architecture = (ROOT / "docs" / "MAC_APP_ARCHITECTURE.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "Rust/Tauri owns",
            "WKWebView owns",
            "Python owns",
            "com.heyjarvis.desktop",
            "Application Support and Keychain",
            "Developer ID and notarization",
            "TCC microphone grants",
            "F088",
            "F089",
            "F090",
            "F092",
        ):
            self.assertIn(phrase, architecture)


if __name__ == "__main__":
    unittest.main()
