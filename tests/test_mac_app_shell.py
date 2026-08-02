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

        window = config["app"]["windows"][0]
        self.assertEqual((window["width"], window["height"]), (560, 600))
        self.assertEqual((window["minWidth"], window["minHeight"]), (480, 520))

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
        self.assertIn("Run readiness check", page)
        self.assertIn("Restart sidecar", page)
        script = (APP / "src" / "main.js").read_text(encoding="utf-8")
        self.assertIn('endpoint.protocol !== "http:"', script)
        self.assertIn('endpoint.hostname !== "127.0.0.1"', script)
        self.assertNotIn("OPENAI_API_KEY", script)

    def test_byok_onboarding_keeps_credentials_out_of_webview_and_public_protocol(self):
        page = (APP / "src" / "index.html").read_text(encoding="utf-8")
        script = (APP / "src" / "main.js").read_text(encoding="utf-8")
        credentials = (APP / "src-tauri" / "src" / "credentials.rs").read_text(
            encoding="utf-8"
        )
        supervisor = (APP / "src-tauri" / "src" / "supervisor.rs").read_text(
            encoding="utf-8"
        )
        sidecar = (APP / "sidecar" / "product_sidecar.py").read_text(
            encoding="utf-8"
        )
        cargo = (APP / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")

        for phrase in (
            "Local until you wake it",
            "OpenAI Project budgets and rate limits",
            "macOS Keychain",
            "Conversation audio reaches OpenAI only after wake",
            "Quitting the tray app stops listening",
            "Check microphone &amp; start",
            "Open System Settings",
        ):
            self.assertIn(phrase, page)
        self.assertNotIn('type="password"', page)
        self.assertNotIn("openai_api_key", script.lower())
        self.assertNotIn("finnhub_api_key", script.lower())
        self.assertIn("prompt_save_credential", script)
        self.assertIn("security-framework", cargo)
        self.assertIn("get_generic_password", credentials)
        self.assertIn("set_generic_password", credentials)
        self.assertIn("delete_generic_password", credentials)
        self.assertIn("private_bootstrap", supervisor)
        self.assertIn('"private_credentials"', credentials)
        self.assertIn("parse_private_credentials", sidecar)

    def test_first_run_recovery_guidance_is_non_listening_and_actionable(self):
        script = (APP / "src" / "main.js").read_text(encoding="utf-8")
        for phrase in (
            "Keychain is locked",
            "Microphone access is required, but listening remains off",
            "No microphone was found",
            "Check your internet connection",
            "local wake model is not ready",
            "quit and reopen Hey Jarvis",
            "record_microphone_denied",
            "track.stop()",
            "Microphone access is ready. Starting the local voice runtime",
            "renderRuntime(await invoke(\"complete_onboarding\"))",
        ):
            self.assertIn(phrase, script)

    def test_runtime_page_can_return_to_non_listening_settings(self):
        host_page = (
            ROOT / "src" / "realtime_host" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        host_script = (
            ROOT / "src" / "realtime_host" / "static" / "app.js"
        ).read_text(encoding="utf-8")
        app_script = (APP / "src" / "main.js").read_text(encoding="utf-8")
        native = (APP / "src-tauri" / "src" / "lib.rs").read_text(
            encoding="utf-8"
        )
        app_page = (APP / "src" / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="app-settings"', host_page)
        self.assertIn('aria-label="Open Settings"', host_page)
        self.assertIn("Enable voice assistant", host_page)
        self.assertIn('data-ui-state="ready"', host_page)
        self.assertNotIn('id="events"', host_page)
        self.assertNotIn('id="settings"', host_page)
        self.assertIn('id="runtime-settings"', app_page)
        self.assertIn("window.history.back()", host_script)
        self.assertNotIn("tauri://localhost", host_script)
        self.assertIn('SETTINGS_RETURN_HASH = "#settings-return"', app_script)
        self.assertIn('if (settingsMode) {\n      elements.message.textContent = "Voice listening is stopped while Settings is open."', app_script)
        self.assertIn("window.location.assign(endpoint.href)", app_script)
        self.assertIn("event.persisted && isSettingsReturn()", app_script)
        self.assertIn('window.history.replaceState(null, "", SETTINGS_RETURN_HASH)', app_script)
        self.assertNotIn('window.location.href.split("#", 1)[0]', app_script)
        self.assertIn('invoke(settingsMode ? "enter_settings"', app_script)
        self.assertIn('if (!settingsMode && snapshot.completed', app_script)
        self.assertIn('renderSetup(await invoke("enter_settings"))', app_script)
        self.assertIn("elements.onboarding.hidden = false", app_script)
        self.assertIn("elements.runtime.hidden = true", app_script)
        self.assertIn("fn enter_settings", native)
        self.assertIn('stop_sidecar(&runtime, "open_settings")', native)
        self.assertIn("fn settings_url", native)
        self.assertIn(".build\n        .dev_url", native)
        self.assertIn('url.set_fragment(Some("settings-return"))', native)

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
        self.assertIn('../../.venv/bin/python', supervisor)
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

    def test_diagnostics_recovery_and_support_export_are_privacy_bounded(self):
        native = (APP / "src-tauri" / "src" / "diagnostics.rs").read_text(
            encoding="utf-8"
        )
        supervisor = (APP / "src-tauri" / "src" / "supervisor.rs").read_text(
            encoding="utf-8"
        )
        sidecar = (APP / "sidecar" / "product_sidecar.py").read_text(
            encoding="utf-8"
        )
        frontend = (APP / "src" / "main.js").read_text(encoding="utf-8")
        page = (APP / "src" / "index.html").read_text(encoding="utf-8")
        host = (ROOT / "src" / "realtime_host" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        power = (APP / "src-tauri" / "src" / "power.rs").read_text(
            encoding="utf-8"
        )
        docs = (ROOT / "docs" / "MAC_APP_DIAGNOSTICS.md").read_text(
            encoding="utf-8"
        )

        for marker in (
            "LOG_LIMIT",
            "LOG_GENERATIONS",
            "hey-jarvis-support-v1",
            "support_export_rejected",
            "FORBIDDEN",
        ):
            self.assertIn(marker, native)
        for marker in (
            "MAX_RESTARTS",
            "RESTART_BACKOFF",
            "sidecar_crash_loop",
            "desired_running",
            "recover_if_needed",
        ):
            self.assertIn(marker, supervisor)
        self.assertIn("LifecycleDiagnostics", sidecar)
        self.assertIn("DIAGNOSTIC_LIMIT_BYTES", sidecar)
        self.assertIn('invoke("export_support_bundle")', frontend)
        self.assertIn('invoke("clear_diagnostics")', frontend)
        self.assertIn("Export support bundle", page)
        self.assertIn('window.addEventListener("pagehide",releasePageMedia)', host)
        self.assertIn('document.addEventListener("freeze",releasePageMedia)', host)
        self.assertIn("NSWorkspaceWillSleepNotification", power)
        self.assertIn("NSWorkspaceDidWakeNotification", power)
        self.assertIn('stop_sidecar(&runtime, "system_will_sleep")', power)
        self.assertIn("never creates paid Realtime activity", docs)


if __name__ == "__main__":
    unittest.main()
