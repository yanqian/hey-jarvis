mod protocol;
mod supervisor;

use std::path::PathBuf;
use std::sync::Mutex;
use supervisor::{RuntimeSnapshot, SidecarSupervisor};
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, State,
};

struct AppRuntime(Mutex<SidecarSupervisor>);

#[tauri::command]
fn sidecar_status(runtime: State<'_, AppRuntime>) -> Result<RuntimeSnapshot, String> {
    runtime
        .0
        .lock()
        .map_err(|_| "sidecar supervisor is unavailable".to_string())
        .map(|supervisor| supervisor.snapshot())
}

#[tauri::command]
fn sidecar_health(runtime: State<'_, AppRuntime>) -> Result<RuntimeSnapshot, String> {
    runtime
        .0
        .lock()
        .map_err(|_| "sidecar supervisor is unavailable".to_string())?
        .health()
}

#[tauri::command]
fn restart_sidecar(runtime: State<'_, AppRuntime>) -> Result<RuntimeSnapshot, String> {
    runtime
        .0
        .lock()
        .map_err(|_| "sidecar supervisor is unavailable".to_string())?
        .start()
}

fn stop_sidecar(runtime: &AppRuntime, reason: &str) {
    if let Ok(mut supervisor) = runtime.0.lock() {
        let _ = supervisor.stop(reason);
    }
}

fn fake_sidecar_path() -> PathBuf {
    std::env::var_os("HEY_JARVIS_FAKE_SIDECAR_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../sidecar/fake_sidecar.py")
        })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .setup(|app| {
            let app_support_dir = app.path().app_data_dir()?;
            let mut supervisor = SidecarSupervisor::new(app_support_dir, fake_sidecar_path());
            let _ = supervisor.start();
            app.manage(AppRuntime(Mutex::new(supervisor)));

            let show = MenuItem::with_id(app, "show", "Show Hey Jarvis", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit Hey Jarvis", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            let mut tray = TrayIconBuilder::with_id("hey-jarvis").menu(&menu);
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            tray.on_menu_event(|app, event| match event.id.as_ref() {
                "show" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
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
            restart_sidecar
        ])
        .build(tauri::generate_context!())
        .expect("Hey Jarvis Mac app failed to build");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Some(runtime) = app_handle.try_state::<AppRuntime>() {
                stop_sidecar(&runtime, "app_exit");
            }
        }
    });
}
