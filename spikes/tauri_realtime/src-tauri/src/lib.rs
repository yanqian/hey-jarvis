use serde::Serialize;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, State,
};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

const PROBE_PORT: u16 = 8871;

struct ProbeRuntime {
    token: String,
    child: Mutex<Option<CommandChild>>,
}

#[derive(Serialize)]
struct ProbeConfig {
    base_url: String,
    token: String,
}

fn capability_token() -> Result<String, String> {
    let mut bytes = [0_u8; 32];
    getrandom::fill(&mut bytes).map_err(|error| format!("random token generation failed: {error}"))?;
    Ok(bytes.iter().map(|value| format!("{value:02x}")).collect())
}

fn stop_sidecar(runtime: &ProbeRuntime) {
    if let Ok(mut guard) = runtime.child.lock() {
        if let Some(child) = guard.take() {
            let _ = child.kill();
        }
    }
}

#[tauri::command]
fn probe_config(runtime: State<'_, ProbeRuntime>) -> ProbeConfig {
    ProbeConfig {
        base_url: format!("http://127.0.0.1:{PROBE_PORT}"),
        token: runtime.token.clone(),
    }
}

#[tauri::command]
fn stop_probe(runtime: State<'_, ProbeRuntime>) {
    stop_sidecar(&runtime);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let token = capability_token().map_err(std::io::Error::other)?;
            let env_file = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.env");
            let sidecar = app
                .shell()
                .sidecar("tauri-realtime-probe")
                .map_err(std::io::Error::other)?
                .env("TAURI_SPIKE_TOKEN", &token)
                .env("TAURI_SPIKE_PORT", PROBE_PORT.to_string())
                .env("TAURI_SPIKE_ENV_FILE", env_file);
            let (mut events, child) = sidecar.spawn().map_err(std::io::Error::other)?;
            tauri::async_runtime::spawn(async move {
                while let Some(event) = events.recv().await {
                    match event {
                        tauri_plugin_shell::process::CommandEvent::Terminated(payload) => {
                            eprintln!("Tauri spike sidecar terminated: {:?}", payload.code);
                        }
                        tauri_plugin_shell::process::CommandEvent::Error(_) => {
                            eprintln!("Tauri spike sidecar reported a bounded process error");
                        }
                        _ => {}
                    }
                }
            });
            app.manage(ProbeRuntime {
                token,
                child: Mutex::new(Some(child)),
            });

            let show = MenuItem::with_id(app, "show", "Show Tauri Realtime Spike", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            let mut tray = TrayIconBuilder::with_id("tauri-realtime-spike").menu(&menu);
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
                    if let Some(runtime) = app.try_state::<ProbeRuntime>() {
                        stop_sidecar(&runtime);
                    }
                    app.exit(0);
                }
                _ => {}
            })
            .build(app)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![probe_config, stop_probe])
        .build(tauri::generate_context!())
        .expect("Tauri Realtime spike failed to build");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Some(runtime) = app_handle.try_state::<ProbeRuntime>() {
                stop_sidecar(&runtime);
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn capability_tokens_are_bounded_and_distinct() {
        let first = capability_token().expect("token");
        let second = capability_token().expect("token");
        assert_eq!(first.len(), 64);
        assert!(first.chars().all(|value| value.is_ascii_hexdigit()));
        assert_ne!(first, second);
    }

    #[test]
    fn probe_port_is_loopback_only_by_contract() {
        let config = ProbeConfig {
            base_url: format!("http://127.0.0.1:{PROBE_PORT}"),
            token: "a".repeat(64),
        };
        assert_eq!(config.base_url, "http://127.0.0.1:8871");
    }
}
