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
        self.assertEqual(window["title"], "Hey Jarvis")
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
        self.assertIn("Privacy &amp; Diagnostics", page)
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
            "navigateToAssistant(await invoke(\"complete_onboarding\"))",
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
        self.assertIn('id="return-assistant"', app_page)
        self.assertNotIn("window.history.back()", host_script)
        self.assertIn('window.location.assign("hey-jarvis://settings/open")', host_script)
        self.assertIn('SETTINGS_RETURN_HASH = "#settings-return"', app_script)
        self.assertIn('recordLifecycle("settings_opened")', app_script)
        self.assertIn("function afterCommittedPaint()", app_script)
        self.assertIn("if (settingsMode) {", app_script)
        self.assertIn("resetSettingsSurface();\n      await afterCommittedPaint();", app_script)
        self.assertIn("window.requestAnimationFrame(() => window.requestAnimationFrame(resolve))", app_script)
        self.assertIn("function resetSettingsSurface()", app_script)
        self.assertIn("elements.returningView.hidden = true", app_script)
        self.assertIn("elements.settingsShell.hidden = false", app_script)
        self.assertIn("if (isSettingsReturn()) resetSettingsSurface()", app_script)
        self.assertIn("window.location.assign(endpoint.href)", app_script)
        self.assertIn("event.persisted && isSettingsReturn()", app_script)
        self.assertIn('window.history.replaceState(null, "", SETTINGS_RETURN_HASH)', app_script)
        self.assertNotIn('window.location.href.split("#", 1)[0]', app_script)
        self.assertIn('invoke(settingsMode ? "enter_settings"', app_script)
        self.assertIn('if (!settingsMode && snapshot.completed', app_script)
        self.assertIn('renderSetup(await invoke("enter_settings"))', app_script)
        self.assertIn('navigateToAssistant(await invoke("restart_sidecar"))', app_script)
        self.assertIn('await recordLifecycle("runtime_restart_requested")', app_script)
        self.assertNotIn("await new Promise(resolve => window.requestAnimationFrame(resolve))", app_script)
        return_start = app_script.index("async function returnToAssistant()")
        return_end = app_script.index("async function runReadinessCheck()", return_start)
        self.assertNotIn("requestAnimationFrame", app_script[return_start:return_end])
        self.assertIn('id="returning-view"', app_page)
        self.assertIn('role="status" aria-live="polite"', app_page)
        self.assertIn("elements.settingsShell.hidden = true", app_script)
        self.assertIn("elements.settingsShell.hidden = false", app_script)
        self.assertIn("fn enter_settings", native)
        self.assertIn('tauri::plugin::Builder::<_, ()>::new("settings-navigation")', native)
        self.assertIn('url.scheme() == "hey-jarvis"', native)
        self.assertIn('url.host_str() == Some("settings")', native)
        self.assertIn('url.path() == "/open"', native)
        self.assertIn("url.query().is_none()", native)
        self.assertIn("url.fragment().is_none()", native)
        self.assertIn("webview.run_on_main_thread(move || open_settings_window(&app))", native)
        self.assertIn("return false", native)
        self.assertIn('"runtime_restart_requested"', native)
        self.assertIn("async fn restart_sidecar(app: tauri::AppHandle)", native)
        self.assertIn("tauri::async_runtime::spawn_blocking", native)
        self.assertIn("restart_sidecar_runtime(&runtime)", native)
        self.assertIn('stop_sidecar(&runtime, "open_settings")', native)
        self.assertIn("fn settings_url", native)
        self.assertIn(".build\n        .dev_url", native)
        self.assertIn("static SETTINGS_REQUEST_ID: AtomicU64", native)
        self.assertIn("SETTINGS_REQUEST_ID.fetch_add(1, Ordering::Relaxed)", native)
        self.assertIn('.append_pair("settings-request", &request_id.to_string())', native)
        self.assertIn('url.set_fragment(Some("settings-return"))', native)

        request_token = native.index('.append_pair("settings-request"')
        settings_fragment = native.index('url.set_fragment(Some("settings-return"))')
        self.assertLess(request_token, settings_fragment)

        enter_settings_start = native.index("fn enter_settings")
        enter_settings_end = native.index("#[tauri::command]", enter_settings_start + 1)
        enter_settings = native[enter_settings_start:enter_settings_end]
        self.assertIn('stop_sidecar(&runtime, "open_settings")', enter_settings)

        open_settings_start = native.index("fn open_settings_window")
        open_settings_end = native.index("#[cfg_attr", open_settings_start)
        open_settings = native[open_settings_start:open_settings_end]
        self.assertIn("window.navigate(url)", open_settings)
        self.assertNotIn("stop_sidecar", open_settings)

    def test_settings_surface_has_unified_entry_points_and_privacy_safe_sections(self):
        page = (APP / "src" / "index.html").read_text(encoding="utf-8")
        script = (APP / "src" / "main.js").read_text(encoding="utf-8")
        styles = (APP / "src" / "styles.css").read_text(encoding="utf-8")
        native = (APP / "src-tauri" / "src" / "lib.rs").read_text(
            encoding="utf-8"
        )

        for section in (
            "General",
            "API Keys",
            "Microphone",
            "Privacy &amp; Diagnostics",
            "About",
        ):
            self.assertIn(section, page)
        for phrase in (
            "Listening is off while Settings is open",
            "the local voice runtime is stopped",
            "never keys, raw audio, transcripts, answers, tool arguments, SDP, ICE, or provider bodies",
            "Unsigned trusted testing only",
        ):
            self.assertIn(phrase, page)
        self.assertNotIn("Protocol", page)
        self.assertNotIn("Session", page)
        self.assertNotIn("App data", page)
        self.assertNotIn('type="password"', page)
        self.assertIn('invoke("record_microphone_granted")', script)
        self.assertIn('window.confirm("Clear all local Hey Jarvis diagnostics?', script)
        self.assertIn("prefers-reduced-motion", styles)
        self.assertIn(":focus-visible", styles)
        self.assertIn("fn open_settings_window", native)
        self.assertIn('"app-settings"', native)
        self.assertIn('Some("CmdOrCtrl+,")', native)
        self.assertIn('"settings" => {\n                    open_settings_window(app);', native)
        self.assertNotIn("Add key…", page)
        self.assertNotIn("Replace key…", script)
        self.assertIn('? "Replace key" : "Add key"', script)
        self.assertIn("font-size: 12px;\n  font-weight: 500;", styles)
        self.assertIn("@media (max-width: 700px)", styles)
        self.assertIn(".row-actions { justify-content: flex-start; width: 100%; }", styles)
        self.assertIn(".row-actions button { flex: 1 1 108px; }", styles)

    def test_home_and_settings_share_one_responsive_desktop_shell(self):
        settings_page = (APP / "src" / "index.html").read_text(encoding="utf-8")
        settings_styles = (APP / "src" / "styles.css").read_text(encoding="utf-8")
        home_page = (
            ROOT / "src" / "realtime_host" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        home_styles = (
            ROOT / "src" / "realtime_host" / "static" / "styles.css"
        ).read_text(encoding="utf-8")
        native = (APP / "src-tauri" / "src" / "lib.rs").read_text(
            encoding="utf-8"
        )

        self.assertIn("<title>Hey Jarvis</title>", settings_page)
        self.assertIn("<title>Hey Jarvis</title>", home_page)
        self.assertNotIn("Hey Jarvis Settings", settings_page)
        self.assertNotIn("Hey Jarvis Settings", native)
        self.assertIn('window.set_title("Hey Jarvis")', native)
        self.assertNotIn('class="eyebrow"', settings_page)
        self.assertIn('id="settings-title" class="context-title">Settings</h1>', settings_page)
        self.assertIn('class="app-header returning-header"', settings_page)
        self.assertIn('class="brand-icon"', home_page)

        for styles in (settings_styles, home_styles):
            self.assertIn("--shell-gutter: clamp(24px, 4vw, 52px);", styles)
            self.assertIn("--shell-top: 24px;", styles)
            self.assertIn("--header-control-size: 38px;", styles)
            self.assertIn("padding: var(--shell-top) var(--shell-gutter)", styles)

        self.assertIn(".settings-shell {\n  width: 100%;", settings_styles)
        self.assertIn("width: min(100%, 1180px);", settings_styles)
        self.assertIn("min-height: max(410px, calc(100vh - 154px));", settings_styles)
        self.assertIn(".settings-panel { width: min(100%, 760px); }", settings_styles)
        self.assertIn("@media (min-width: 1100px)", settings_styles)
        self.assertNotIn("--shell-gutter: 18px", settings_styles)
        self.assertIn(".voice-shell {", home_styles)
        self.assertIn("  width: 100%;", home_styles)
        self.assertIn("width: min(100%, 620px);", home_styles)

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

    def test_voice_availability_is_truthful_bounded_and_visible(self):
        host = (ROOT / "src" / "realtime_host" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        sidecar = (APP / "sidecar" / "product_sidecar.py").read_text(
            encoding="utf-8"
        )
        supervisor = (APP / "src-tauri" / "src" / "supervisor.rs").read_text(
            encoding="utf-8"
        )
        native = (APP / "src-tauri" / "src" / "lib.rs").read_text(
            encoding="utf-8"
        )

        self.assertIn('fetch("/api/availability"', host)
        self.assertIn('"resume-required"', host)
        self.assertIn('event": "voice_availability"', sidecar)
        self.assertIn('diagnostics.record("runtime_ready", "ready")', sidecar)
        self.assertNotIn('diagnostics.record("runtime_ready", "wake_listening")', sidecar)
        for availability in ("ready", "wake_listening", "busy", "resume_required"):
            self.assertIn(f'"{availability}"', supervisor)
        self.assertIn('"voice-status"', native)
        self.assertIn('"Status: Wake listening"', native)

    def test_smart_speaker_mode_is_opt_in_native_and_voice_gated(self):
        page = (APP / "src" / "index.html").read_text(encoding="utf-8")
        frontend = (APP / "src" / "main.js").read_text(encoding="utf-8")
        native = (APP / "src-tauri" / "src" / "lib.rs").read_text(
            encoding="utf-8"
        )
        power = (APP / "src-tauri" / "src" / "power.rs").read_text(
            encoding="utf-8"
        )
        preferences = (APP / "src-tauri" / "src" / "preferences.rs").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="smart-speaker-mode" type="checkbox"', page)
        self.assertIn("This can use more battery", page)
        self.assertIn("explicit Sleep, shutdown, and closing a MacBook lid", page)
        self.assertIn('invoke("set_smart_speaker_mode", { enabled })', frontend)
        self.assertIn('endpoint.hash = "smart-speaker-mode"', frontend)
        self.assertIn("set_smart_speaker_mode", native)
        self.assertIn('availability != "wake_listening"', power)
        self.assertIn('availability == "busy" && self.assertion_id.is_some()', power)
        self.assertIn('CFString::new("PreventUserIdleSystemSleep")', power)
        self.assertIn("IOPMAssertionCreateWithName", power)
        self.assertIn("IOPMAssertionRelease", power)
        self.assertNotIn("caffeinate", power)
        self.assertNotIn("PreventUserIdleDisplaySleep", power)
        self.assertIn("smart_speaker_mode: false", preferences)
        self.assertIn('preferences-v1.json', preferences)

        host = (ROOT / "src" / "realtime_host" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('location.hash==="#smart-speaker-mode"', host)
        self.assertIn('retainedTrack?.readyState==="live"', host)
        self.assertIn('track.enabled=false', host)
        self.assertIn('audio.srcObject=warmStream;audio.volume=0;await audio.play()', host)
        self.assertIn('audio.srcObject=event.streams[0]', host)
        self.assertIn("if(warmStream){warmStream.getTracks().forEach", host)

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
