import json
import plistlib
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
        info = plistlib.loads((APP / "src-tauri" / "Info.plist").read_bytes())
        self.assertIn("wake phrase", info["NSMicrophoneUsageDescription"])

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

    def test_bootstrap_frontend_redirects_only_to_product_loopback(self):
        page = (APP / "src" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Check sidecar", page)
        self.assertIn("Restart sidecar", page)
        script = (APP / "src" / "main.js").read_text(encoding="utf-8")
        self.assertIn('endpoint.protocol !== "http:"', script)
        self.assertIn('endpoint.hostname !== "127.0.0.1"', script)
        self.assertNotIn("OPENAI_API_KEY", script)

    def test_wkwebview_media_surface_preserves_accepted_realtime_boundary(self):
        script = (ROOT / "src" / "realtime_host" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        for marker in (
            "navigator.mediaDevices.getUserMedia",
            "new RTCPeerConnection()",
            "track.enabled=false",
            "inputTrack.enabled=true",
            'audio.srcObject=null',
            "stream.getTracks().forEach(track=>track.stop())",
            '"tool_call"',
            '"playback_stopped"',
            '"transcription"',
        ):
            self.assertIn(marker, script)
        self.assertNotIn("OPENAI_API_KEY", script)

    def test_product_sidecar_reuses_runtime_without_chrome_or_root_env(self):
        sidecar = (APP / "sidecar" / "product_sidecar.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            "RealtimeSessionController",
            "_build_wake_detector",
            "provider_config_from_settings",
            "env_file=None",
            'real_microphone=True',
            'realtime_bridge_host="127.0.0.1"',
        ):
            self.assertIn(marker, sidecar)
        self.assertNotIn("launch_chrome_app", sidecar)
        self.assertNotIn("subprocess", sidecar)

    def test_release_sidecar_does_not_depend_on_system_python_or_terminal_path(self):
        supervisor = (APP / "src-tauri" / "src" / "supervisor.rs").read_text(
            encoding="utf-8"
        )
        self.assertIn('cfg!(debug_assertions)', supervisor)
        self.assertIn('resource_dir.join("sidecar/hey-jarvis-sidecar")', supervisor)
        self.assertIn("SidecarLaunch::Executable", supervisor)
        self.assertIn("SidecarLaunch::PythonDevelopment", supervisor)
        self.assertIn("HEY_JARVIS_SIDECAR_PYTHON", supervisor)
        self.assertNotIn("HEY_JARVIS_FAKE_SIDECAR_PYTHON", supervisor)
        self.assertIn("Duration::from_secs(30)", supervisor)
        self.assertIn("Sidecar startup failed: {code}", supervisor)

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
