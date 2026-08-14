mod credentials;
mod diagnostics;
mod native_i18n;
mod onboarding;
mod power;
mod preferences;
mod protocol;
mod supervisor;

use credentials::{
    delete_and_report, prompt_and_store, status as credential_status_value, CredentialKind,
    CredentialStatus, CredentialStore, MacKeychainStore, RuntimeCredentials,
};
use diagnostics::{Diagnostics, SupportExport};
use onboarding::{load as load_onboarding, save as save_onboarding, OnboardingRecord};
use preferences::{
    load as load_preferences, normalize_language, normalize_theme, save as save_preferences,
    validate_wake_tuning, ENGLISH,
};
use serde::Serialize;
use std::path::PathBuf;
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Arc, Mutex,
};
use std::thread;
use std::time::Duration;
use supervisor::{RuntimeSnapshot, SidecarSupervisor};
use tauri::{
    menu::{Menu, MenuItem, MenuItemKind, PredefinedMenuItem},
    tray::TrayIconBuilder,
    Manager, State, WebviewUrl, WebviewWindowBuilder,
};

struct AppRuntime {
    supervisor: Mutex<SidecarSupervisor>,
    credentials: Arc<dyn CredentialStore>,
    onboarding_path: PathBuf,
    preferences_path: PathBuf,
    power_policy: Mutex<power::PowerPolicy>,
    sleep_recovery: Mutex<power::SleepRecoveryPolicy>,
    app_support_dir: PathBuf,
    diagnostics: Diagnostics,
}

struct NativeMenuItems {
    voice_status: MenuItem<tauri::Wry>,
    application_settings: MenuItem<tauri::Wry>,
    tray_show: MenuItem<tauri::Wry>,
    tray_settings: MenuItem<tauri::Wry>,
    tray_quit: MenuItem<tauri::Wry>,
}

impl NativeMenuItems {
    fn apply(&self, locale: &str, availability: &str) {
        let _ = self
            .voice_status
            .set_text(native_i18n::availability(locale, availability));
        let _ = self
            .application_settings
            .set_text(native_i18n::text(locale, "Settings…", "设置…"));
        let _ = self.tray_show.set_text(native_i18n::text(
            locale,
            "Show Hey Jarvis",
            "显示 Hey Jarvis",
        ));
        let _ = self
            .tray_settings
            .set_text(native_i18n::text(locale, "Settings…", "设置…"));
        let _ = self.tray_quit.set_text(native_i18n::text(
            locale,
            "Quit Hey Jarvis",
            "退出 Hey Jarvis",
        ));
    }
}

static SETTINGS_REQUEST_ID: AtomicU64 = AtomicU64::new(1);

#[tauri::command]
fn record_webview_lifecycle(
    event: String,
    session_id: Option<String>,
    runtime: State<'_, AppRuntime>,
) -> Result<(), String> {
    const ALLOWED: &[&str] = &[
        "loaded",
        "settings_opened",
        "runtime_restart_requested",
        "microphone_check_started",
        "microphone_check_passed",
        "microphone_denied",
        "runtime_navigation",
        "pagehide",
    ];
    if !ALLOWED.contains(&event.as_str()) {
        return Err("diagnostic_event_rejected".into());
    }
    runtime
        .diagnostics
        .record("webview", &event, session_id.as_deref(), None);
    Ok(())
}

#[tauri::command]
fn export_support_bundle(runtime: State<'_, AppRuntime>) -> Result<SupportExport, String> {
    runtime
        .diagnostics
        .record("native", "support_exported", None, None);
    runtime.diagnostics.export(&runtime.app_support_dir)
}

#[tauri::command]
fn clear_diagnostics(runtime: State<'_, AppRuntime>) -> Result<(), String> {
    runtime.diagnostics.clear()
}

#[derive(Clone, Debug, Serialize)]
struct OnboardingSnapshot {
    first_run: bool,
    completed: bool,
    microphone_permission: String,
    openai_configured: bool,
    finnhub_configured: bool,
    smart_speaker_mode: bool,
    smart_speaker_active: bool,
    app_language: String,
    app_theme: String,
    wake_diagnostics_enabled: bool,
    wake_threshold: f64,
    wake_confirmation_frames: u8,
}

#[tauri::command]
fn sidecar_status(runtime: State<'_, AppRuntime>) -> Result<RuntimeSnapshot, String> {
    runtime
        .supervisor
        .lock()
        .map_err(|_| "sidecar supervisor is unavailable".to_string())
        .map(|supervisor| supervisor.snapshot())
}

#[tauri::command]
fn sidecar_health(runtime: State<'_, AppRuntime>) -> Result<RuntimeSnapshot, String> {
    runtime
        .supervisor
        .lock()
        .map_err(|_| "sidecar supervisor is unavailable".to_string())?
        .health()
}

fn restart_sidecar_runtime(runtime: &AppRuntime) -> Result<RuntimeSnapshot, String> {
    let record = load_onboarding(&runtime.onboarding_path)?;
    if !record.completed || record.microphone_permission != "granted" {
        return Err("onboarding_incomplete".into());
    }
    let credentials = RuntimeCredentials::load(runtime.credentials.as_ref())?;
    runtime
        .supervisor
        .lock()
        .map_err(|_| "sidecar supervisor is unavailable".to_string())?
        .start_with_credentials(Some(&credentials))
}

const WAKE_RECOVERY_TIMEOUT: Duration = Duration::from_secs(15);

fn cancel_sleep_recovery(runtime: &AppRuntime) {
    if let Ok(mut recovery) = runtime.sleep_recovery.lock() {
        recovery.cancel();
    }
}

#[tauri::command]
async fn restart_sidecar(app: tauri::AppHandle) -> Result<RuntimeSnapshot, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let runtime = app.state::<AppRuntime>();
        restart_sidecar_runtime(&runtime)
    })
    .await
    .map_err(|_| "sidecar restart task failed".to_string())?
}

#[tauri::command]
async fn resume_voice_assistant(app: tauri::AppHandle) -> Result<RuntimeSnapshot, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let runtime = app.state::<AppRuntime>();
        if let Ok(mut recovery) = runtime.sleep_recovery.lock() {
            recovery.begin_manual_resume();
        }
        runtime
            .diagnostics
            .record("native", "voice_resume_requested", None, Some("starting"));
        restart_sidecar_runtime(&runtime)
    })
    .await
    .map_err(|_| "voice resume task failed".to_string())?
}

fn stop_sidecar(runtime: &AppRuntime, reason: &str) {
    if reason != "system_will_sleep" {
        cancel_sleep_recovery(runtime);
    }
    release_power_assertion(runtime, reason);
    if let Ok(mut supervisor) = runtime.supervisor.lock() {
        let _ = supervisor.stop(reason);
    }
}

fn release_power_assertion(runtime: &AppRuntime, reason: &str) {
    if let Ok(mut policy) = runtime.power_policy.lock() {
        policy.release(reason, &runtime.diagnostics);
    }
}

fn update_power_availability(runtime: &AppRuntime, availability: &str) {
    if let Ok(mut policy) = runtime.power_policy.lock() {
        policy.update_availability(availability, &runtime.diagnostics);
    }
    if availability == "wake_listening" {
        let completed = runtime
            .sleep_recovery
            .lock()
            .map(|mut recovery| recovery.complete_if_current(None))
            .unwrap_or(false);
        if completed {
            runtime.diagnostics.record(
                "native",
                "voice_resume_completed",
                None,
                Some("wake_listening"),
            );
        }
    }
}

#[tauri::command]
fn onboarding_status(runtime: State<'_, AppRuntime>) -> Result<OnboardingSnapshot, String> {
    let first_run = !runtime.onboarding_path.exists();
    let record = load_onboarding(&runtime.onboarding_path)?;
    let credentials = credential_status_value(runtime.credentials.as_ref())?;
    onboarding_snapshot(&runtime, first_run, record, credentials)
}

#[tauri::command]
fn set_smart_speaker_mode(
    enabled: bool,
    runtime: State<'_, AppRuntime>,
) -> Result<OnboardingSnapshot, String> {
    let mut preferences = load_preferences(&runtime.preferences_path)?;
    preferences.smart_speaker_mode = enabled;
    save_preferences(&runtime.preferences_path, &preferences)?;
    let availability = runtime
        .supervisor
        .lock()
        .map_err(|_| "sidecar supervisor is unavailable".to_string())?
        .snapshot()
        .availability;
    runtime
        .power_policy
        .lock()
        .map_err(|_| "power policy is unavailable".to_string())?
        .set_enabled(enabled, &availability, &runtime.diagnostics);
    onboarding_status(runtime)
}

#[tauri::command]
fn set_app_language(
    locale: String,
    app: tauri::AppHandle,
    runtime: State<'_, AppRuntime>,
    menus: State<'_, NativeMenuItems>,
) -> Result<OnboardingSnapshot, String> {
    let locale = normalize_language(&locale)?;
    let mut preferences = load_preferences(&runtime.preferences_path)?;
    preferences.app_language = locale.into();
    save_preferences(&runtime.preferences_path, &preferences)?;
    let availability = runtime
        .supervisor
        .lock()
        .map_err(|_| "sidecar supervisor is unavailable".to_string())?
        .snapshot()
        .availability;
    menus.apply(locale, &availability);
    if let Some(window) = app.get_webview_window("settings") {
        let _ = window.set_title(native_i18n::text(
            locale,
            "Hey Jarvis Settings",
            "Hey Jarvis 设置",
        ));
    }
    onboarding_status(runtime)
}

#[tauri::command]
fn set_app_theme(
    theme: String,
    runtime: State<'_, AppRuntime>,
) -> Result<OnboardingSnapshot, String> {
    let theme = normalize_theme(&theme)?;
    let mut preferences = load_preferences(&runtime.preferences_path)?;
    preferences.app_theme = theme.into();
    save_preferences(&runtime.preferences_path, &preferences)?;
    onboarding_status(runtime)
}

#[tauri::command]
fn set_wake_diagnostics(
    enabled: bool,
    runtime: State<'_, AppRuntime>,
) -> Result<OnboardingSnapshot, String> {
    let mut preferences = load_preferences(&runtime.preferences_path)?;
    if preferences.wake_diagnostics_enabled != enabled {
        preferences.wake_diagnostics_enabled = enabled;
        save_preferences(&runtime.preferences_path, &preferences)?;
        stop_sidecar(&runtime, "wake_diagnostics_changed");
    }
    onboarding_status(runtime)
}

#[tauri::command]
fn set_wake_tuning(
    wake_threshold: f64,
    wake_confirmation_frames: u8,
    runtime: State<'_, AppRuntime>,
) -> Result<OnboardingSnapshot, String> {
    validate_wake_tuning(wake_threshold, wake_confirmation_frames)?;
    let mut preferences = load_preferences(&runtime.preferences_path)?;
    if preferences.wake_threshold != wake_threshold
        || preferences.wake_confirmation_frames != wake_confirmation_frames
    {
        preferences.wake_threshold = wake_threshold;
        preferences.wake_confirmation_frames = wake_confirmation_frames;
        save_preferences(&runtime.preferences_path, &preferences)?;
        stop_sidecar(&runtime, "wake_tuning_changed");
    }
    onboarding_status(runtime)
}

#[tauri::command]
fn enter_settings(runtime: State<'_, AppRuntime>) -> Result<OnboardingSnapshot, String> {
    onboarding_status(runtime)
}

#[tauri::command]
fn open_settings(app: tauri::AppHandle) -> Result<(), String> {
    request_open_settings(app);
    Ok(())
}

#[tauri::command]
fn close_settings_window(window: tauri::WebviewWindow) -> Result<(), String> {
    if window.label() != "settings" {
        return Err("settings_window_required".into());
    }
    window.close().map_err(|_| "settings_unavailable".into())
}

#[tauri::command]
fn prompt_save_credential(
    kind: String,
    runtime: State<'_, AppRuntime>,
) -> Result<CredentialStatus, String> {
    let kind = CredentialKind::parse(&kind)?;
    let locale = load_preferences(&runtime.preferences_path)?.app_language;
    let result = prompt_and_store(runtime.credentials.as_ref(), kind, &locale)?;
    stop_sidecar(&runtime, "credential_replaced");
    Ok(result)
}

#[tauri::command]
fn delete_credential(
    kind: String,
    runtime: State<'_, AppRuntime>,
) -> Result<CredentialStatus, String> {
    let kind = CredentialKind::parse(&kind)?;
    let result = delete_and_report(runtime.credentials.as_ref(), kind)?;
    stop_sidecar(&runtime, "credential_deleted");
    Ok(result)
}

#[tauri::command]
fn prepare_microphone_check(runtime: State<'_, AppRuntime>) {
    stop_sidecar(&runtime, "microphone_settings_check");
}

#[tauri::command]
fn record_microphone_denied(runtime: State<'_, AppRuntime>) -> Result<OnboardingSnapshot, String> {
    stop_sidecar(&runtime, "microphone_denied");
    let mut record = load_onboarding(&runtime.onboarding_path).unwrap_or_default();
    record.completed = false;
    record.microphone_permission = "denied".into();
    save_onboarding(&runtime.onboarding_path, &record)?;
    let credentials = credential_status_value(runtime.credentials.as_ref())?;
    onboarding_snapshot(&runtime, false, record, credentials)
}

#[tauri::command]
fn record_microphone_granted(runtime: State<'_, AppRuntime>) -> Result<OnboardingSnapshot, String> {
    let first_run = !runtime.onboarding_path.exists();
    let mut record = load_onboarding(&runtime.onboarding_path).unwrap_or_default();
    record.microphone_permission = "granted".into();
    save_onboarding(&runtime.onboarding_path, &record)?;
    let credentials = credential_status_value(runtime.credentials.as_ref())?;
    onboarding_snapshot(&runtime, first_run, record, credentials)
}

#[tauri::command]
async fn restart_voice_from_settings(
    app: tauri::AppHandle,
    resume_listening: bool,
) -> Result<RuntimeSnapshot, String> {
    let worker_app = app.clone();
    let snapshot = tauri::async_runtime::spawn_blocking(move || {
        let runtime = worker_app.state::<AppRuntime>();
        restart_sidecar_runtime(&runtime)
    })
    .await
    .map_err(|_| "sidecar restart task failed".to_string())??;
    navigate_main_to_runtime(&app, &snapshot, resume_listening)?;
    Ok(snapshot)
}

#[tauri::command]
fn complete_onboarding(runtime: State<'_, AppRuntime>) -> Result<RuntimeSnapshot, String> {
    let credentials = RuntimeCredentials::load(runtime.credentials.as_ref())?;
    let record = OnboardingRecord {
        completed: true,
        microphone_permission: "granted".into(),
        ..OnboardingRecord::default()
    };
    save_onboarding(&runtime.onboarding_path, &record)?;
    runtime
        .supervisor
        .lock()
        .map_err(|_| "sidecar supervisor is unavailable".to_string())?
        .start_with_credentials(Some(&credentials))
}

#[tauri::command]
fn open_microphone_settings() -> Result<(), String> {
    std::process::Command::new("/usr/bin/open")
        .arg("x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone")
        .status()
        .map_err(|_| "system_settings_unavailable".to_string())?
        .success()
        .then_some(())
        .ok_or_else(|| "system_settings_unavailable".to_string())
}

fn onboarding_snapshot(
    runtime: &AppRuntime,
    first_run: bool,
    record: OnboardingRecord,
    credentials: CredentialStatus,
) -> Result<OnboardingSnapshot, String> {
    let preferences = load_preferences(&runtime.preferences_path)?;
    let power = runtime
        .power_policy
        .lock()
        .map_err(|_| "power policy is unavailable".to_string())?
        .snapshot();
    Ok(OnboardingSnapshot {
        first_run,
        completed: record.completed,
        microphone_permission: record.microphone_permission,
        openai_configured: credentials.openai_configured,
        finnhub_configured: credentials.finnhub_configured,
        smart_speaker_mode: preferences.smart_speaker_mode,
        smart_speaker_active: power.active,
        app_language: preferences.app_language,
        app_theme: preferences.app_theme,
        wake_diagnostics_enabled: preferences.wake_diagnostics_enabled,
        wake_threshold: preferences.wake_threshold,
        wake_confirmation_frames: preferences.wake_confirmation_frames,
    })
}

#[cfg(debug_assertions)]
fn development_sidecar_path() -> PathBuf {
    std::env::var_os("HEY_JARVIS_SIDECAR_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../sidecar/product_sidecar.py")
        })
}

#[cfg(not(debug_assertions))]
fn development_sidecar_path() -> PathBuf {
    // The release supervisor always resolves the frozen sidecar from the app's
    // resource directory. Keeping the development source path out of this
    // build also prevents a developer checkout path leaking into the binary.
    PathBuf::new()
}

fn settings_url(app: &tauri::AppHandle) -> Result<WebviewUrl, String> {
    local_shell_url(app, "settings").map(WebviewUrl::External)
}

fn local_shell_url(app: &tauri::AppHandle, fragment: &str) -> Result<tauri::Url, String> {
    let mut url = app
        .config()
        .build
        .dev_url
        .clone()
        .unwrap_or(tauri::Url::parse("tauri://localhost").map_err(|_| "settings_unavailable")?);
    let request_id = SETTINGS_REQUEST_ID.fetch_add(1, Ordering::Relaxed);
    url.query_pairs_mut()
        .append_pair("settings-request", &request_id.to_string());
    url.set_fragment(Some(fragment));
    Ok(url)
}

pub(crate) fn show_resume_required_window(app: &tauri::AppHandle) {
    let ui_app = app.clone();
    let _ = app.run_on_main_thread(move || {
        if let Some(window) = ui_app.get_webview_window("main") {
            if let Ok(url) = local_shell_url(&ui_app, "resume-required") {
                let _ = window.navigate(url);
            }
            let _ = window.show();
            let _ = window.set_focus();
        }
    });
}

fn navigate_to_recovery_runtime(
    app: &tauri::AppHandle,
    snapshot: &RuntimeSnapshot,
) -> Result<(), String> {
    let control_url = snapshot
        .control_url
        .as_deref()
        .ok_or("sidecar_readiness_timed_out")?;
    let mut url = tauri::Url::parse(control_url).map_err(|_| "invalid_control_url")?;
    if url.scheme() != "http" || url.host_str() != Some("127.0.0.1") {
        return Err("invalid_control_url".into());
    }
    url.set_fragment(Some("smart-speaker-resume"));
    let ui_app = app.clone();
    app.run_on_main_thread(move || {
        if let Some(window) = ui_app.get_webview_window("main") {
            let _ = window.navigate(url);
            let _ = window.show();
            let _ = window.set_focus();
        }
    })
    .map_err(|_| "runtime_navigation_failed".to_string())
}

fn navigate_main_to_runtime(
    app: &tauri::AppHandle,
    snapshot: &RuntimeSnapshot,
    resume_listening: bool,
) -> Result<(), String> {
    let control_url = snapshot
        .control_url
        .as_deref()
        .ok_or("sidecar_readiness_timed_out")?;
    let mut url = tauri::Url::parse(control_url).map_err(|_| "invalid_control_url")?;
    if url.scheme() != "http" || url.host_str() != Some("127.0.0.1") {
        return Err("invalid_control_url".into());
    }
    if resume_listening {
        url.set_fragment(Some("smart-speaker-resume"));
    } else {
        let smart_speaker_mode = app
            .try_state::<AppRuntime>()
            .and_then(|runtime| load_preferences(&runtime.preferences_path).ok())
            .map(|preferences| preferences.smart_speaker_mode)
            .unwrap_or(false);
        url.set_fragment(smart_speaker_mode.then_some("smart-speaker-mode"));
    }
    let main = app
        .get_webview_window("main")
        .ok_or_else(|| "runtime_navigation_failed".to_string())?;
    main.navigate(url)
        .map_err(|_| "runtime_navigation_failed".to_string())
}

pub(crate) fn recover_after_system_wake(app: tauri::AppHandle, generation: u64) {
    let result = app
        .try_state::<AppRuntime>()
        .ok_or_else(|| "runtime_unavailable".to_string())
        .and_then(|runtime| restart_sidecar_runtime(&runtime));
    match result {
        Ok(snapshot) if navigate_to_recovery_runtime(&app, &snapshot).is_ok() => {
            if let Some(runtime) = app.try_state::<AppRuntime>() {
                runtime.diagnostics.record(
                    "native",
                    "voice_resume_arming",
                    Some(&snapshot.session_id),
                    Some("bounded"),
                );
            }
            let timeout_app = app.clone();
            thread::spawn(move || {
                thread::sleep(WAKE_RECOVERY_TIMEOUT);
                let timed_out = timeout_app
                    .try_state::<AppRuntime>()
                    .and_then(|runtime| {
                        runtime
                            .sleep_recovery
                            .lock()
                            .ok()
                            .map(|mut recovery| recovery.timeout_if_current(generation))
                    })
                    .unwrap_or(false);
                if timed_out {
                    if let Some(runtime) = timeout_app.try_state::<AppRuntime>() {
                        runtime.diagnostics.record(
                            "native",
                            "voice_resume_timed_out",
                            None,
                            Some("non_listening"),
                        );
                        stop_sidecar(&runtime, "wake_recovery_timeout");
                    }
                    show_resume_required_window(&timeout_app);
                }
            });
        }
        _ => {
            if let Some(runtime) = app.try_state::<AppRuntime>() {
                let _ = runtime
                    .sleep_recovery
                    .lock()
                    .map(|mut recovery| recovery.timeout_if_current(generation));
                runtime.diagnostics.record(
                    "native",
                    "voice_resume_failed",
                    None,
                    Some("non_listening"),
                );
            }
            show_resume_required_window(&app);
        }
    }
}

fn open_settings_window(app: &tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("settings") {
        let _ = window.show();
        let _ = window.set_focus();
        return Ok(());
    }
    let locale = app
        .try_state::<AppRuntime>()
        .and_then(|runtime| load_preferences(&runtime.preferences_path).ok())
        .map(|preferences| preferences.app_language)
        .unwrap_or_else(|| ENGLISH.into());
    let window = WebviewWindowBuilder::new(app, "settings", settings_url(app)?)
        .title(native_i18n::text(
            &locale,
            "Hey Jarvis Settings",
            "Hey Jarvis 设置",
        ))
        .inner_size(820.0, 640.0)
        .min_inner_size(700.0, 520.0)
        .build()
        .map_err(|_| "settings_unavailable".to_string())?;
    let _ = window.show();
    let _ = window.set_focus();
    Ok(())
}

fn request_open_settings(app: tauri::AppHandle) {
    thread::spawn(move || {
        let _ = open_settings_window(&app);
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(
            tauri::plugin::Builder::<_, ()>::new("settings-navigation")
                .on_navigation(|webview, url| {
                    let is_settings_intent = url.scheme() == "hey-jarvis"
                        && url.host_str() == Some("settings")
                        && url.path() == "/open"
                        && url.query().is_none()
                        && url.fragment().is_none();
                    if is_settings_intent {
                        let app = webview.app_handle().clone();
                        request_open_settings(app);
                        return false;
                    }
                    true
                })
                .build(),
        )
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .setup(|app| {
            let app_support_dir = app.path().app_data_dir()?;
            let diagnostics = Diagnostics::new(&app_support_dir);
            diagnostics.record("native", "app_started", None, Some("safe"));
            let resource_dir = std::env::var_os("HEY_JARVIS_RESOURCE_DIR")
                .map(PathBuf::from)
                .unwrap_or(app.path().resource_dir()?);
            let onboarding_path = onboarding::path(&app_support_dir);
            let preferences_path = preferences::path(&app_support_dir);
            let preferences = load_preferences(&preferences_path).unwrap_or_default();
            let _ = save_preferences(&preferences_path, &preferences);
            let credential_store: Arc<dyn CredentialStore> = Arc::new(MacKeychainStore);
            let mut supervisor = SidecarSupervisor::new(
                app_support_dir.clone(),
                resource_dir,
                development_sidecar_path(),
            );
            let onboarding = load_onboarding(&onboarding_path).unwrap_or_default();
            if onboarding.completed && onboarding.microphone_permission == "granted" {
                if let Ok(credentials) = RuntimeCredentials::load(credential_store.as_ref()) {
                    let _ = supervisor.start_with_credentials(Some(&credentials));
                }
            }
            app.manage(AppRuntime {
                supervisor: Mutex::new(supervisor),
                credentials: credential_store,
                onboarding_path,
                preferences_path,
                power_policy: Mutex::new(power::PowerPolicy::system(
                    preferences.smart_speaker_mode,
                )),
                sleep_recovery: Mutex::new(power::SleepRecoveryPolicy::default()),
                app_support_dir,
                diagnostics,
            });
            power::install(app.handle().clone());
            let initial_availability = app
                .state::<AppRuntime>()
                .supervisor
                .lock()
                .map(|supervisor| supervisor.snapshot().availability)
                .unwrap_or_else(|_| "resume_required".into());
            let voice_status = MenuItem::with_id(
                app,
                "voice-status",
                native_i18n::availability(&preferences.app_language, &initial_availability),
                false,
                None::<&str>,
            )?;
            let monitor_voice_status = voice_status.clone();
            let monitor_app = app.handle().clone();
            thread::spawn(move || loop {
                thread::sleep(Duration::from_secs(1));
                let Some(runtime) = monitor_app.try_state::<AppRuntime>() else {
                    break;
                };
                let needs_recovery = runtime
                    .supervisor
                    .lock()
                    .map(|mut supervisor| supervisor.needs_recovery())
                    .unwrap_or(false);
                if !needs_recovery {
                    let availability = runtime
                        .supervisor
                        .lock()
                        .map(|mut supervisor| {
                            let snapshot = supervisor.snapshot();
                            if snapshot.state == "ready" {
                                let _ = supervisor.health();
                            }
                            supervisor.snapshot().availability
                        })
                        .unwrap_or_else(|_| "resume_required".into());
                    let locale = load_preferences(&runtime.preferences_path)
                        .map(|preferences| preferences.app_language)
                        .unwrap_or_else(|_| ENGLISH.into());
                    let _ = monitor_voice_status
                        .set_text(native_i18n::availability(&locale, &availability));
                    update_power_availability(&runtime, &availability);
                    continue;
                }
                release_power_assertion(&runtime, "sidecar_exit");
                let Ok(credentials) = RuntimeCredentials::load(runtime.credentials.as_ref()) else {
                    runtime.diagnostics.record(
                        "native",
                        "recovery_credentials_unavailable",
                        None,
                        Some("non_listening"),
                    );
                    continue;
                };
                if let Ok(mut supervisor) = runtime.supervisor.lock() {
                    let _ = supervisor.recover_if_needed(&credentials);
                    let availability = supervisor.snapshot().availability;
                    let locale = load_preferences(&runtime.preferences_path)
                        .map(|preferences| preferences.app_language)
                        .unwrap_or_else(|_| ENGLISH.into());
                    let _ = monitor_voice_status
                        .set_text(native_i18n::availability(&locale, &availability));
                    update_power_availability(&runtime, &availability);
                };
            });
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }

            let application_menu = Menu::default(app.handle())?;
            let settings_shortcut = MenuItem::with_id(
                app,
                "app-settings",
                native_i18n::text(&preferences.app_language, "Settings…", "设置…"),
                true,
                Some("CmdOrCtrl+,"),
            )?;
            if let Some(MenuItemKind::Submenu(application_submenu)) =
                application_menu.items()?.into_iter().next()
            {
                application_submenu.insert(&settings_shortcut, 1)?;
                application_submenu.insert(&PredefinedMenuItem::separator(app)?, 2)?;
            }
            app.set_menu(application_menu)?;
            app.on_menu_event(|app, event| {
                if event.id.as_ref() == "app-settings" {
                    request_open_settings(app.clone());
                }
            });

            let show = MenuItem::with_id(
                app,
                "show",
                native_i18n::text(
                    &preferences.app_language,
                    "Show Hey Jarvis",
                    "显示 Hey Jarvis",
                ),
                true,
                None::<&str>,
            )?;
            let settings = MenuItem::with_id(
                app,
                "settings",
                native_i18n::text(&preferences.app_language, "Settings…", "设置…"),
                true,
                None::<&str>,
            )?;
            let quit = MenuItem::with_id(
                app,
                "quit",
                native_i18n::text(
                    &preferences.app_language,
                    "Quit Hey Jarvis",
                    "退出 Hey Jarvis",
                ),
                true,
                None::<&str>,
            )?;
            let menu = Menu::with_items(app, &[&voice_status, &show, &settings, &quit])?;
            app.manage(NativeMenuItems {
                voice_status: voice_status.clone(),
                application_settings: settings_shortcut.clone(),
                tray_show: show.clone(),
                tray_settings: settings.clone(),
                tray_quit: quit.clone(),
            });
            let tray = TrayIconBuilder::with_id("hey-jarvis")
                .menu(&menu)
                .icon(tauri::include_image!("icons/trayTemplate@2x.png"))
                .icon_as_template(true);
            tray.on_menu_event(|app, event| match event.id.as_ref() {
                "show" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "settings" => {
                    request_open_settings(app.clone());
                }
                "quit" => {
                    if let Some(runtime) = app.try_state::<AppRuntime>() {
                        stop_sidecar(&runtime, "tray_quit");
                    }
                    app.exit(0);
                }
                _ => {}
            })
            .build(app)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            sidecar_status,
            sidecar_health,
            restart_sidecar,
            resume_voice_assistant,
            onboarding_status,
            set_smart_speaker_mode,
            set_app_language,
            set_app_theme,
            set_wake_diagnostics,
            set_wake_tuning,
            enter_settings,
            open_settings,
            close_settings_window,
            prompt_save_credential,
            delete_credential,
            prepare_microphone_check,
            record_microphone_denied,
            record_microphone_granted,
            complete_onboarding,
            restart_voice_from_settings,
            open_microphone_settings,
            record_webview_lifecycle,
            export_support_bundle,
            clear_diagnostics
        ])
        .build(tauri::generate_context!())
        .expect("Hey Jarvis Mac app failed to build");

    app.run(|app_handle, event| {
        if let Some(runtime) = app_handle.try_state::<AppRuntime>() {
            match event {
                tauri::RunEvent::Exit => {
                    runtime
                        .diagnostics
                        .record("native", "app_exit", None, Some("stopping"));
                    stop_sidecar(&runtime, "app_exit");
                }
                _ => {}
            }
        }
    });
}
