use serde::Serialize;
use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::Path;
use std::sync::mpsc::{self, SyncSender};
use std::sync::{Arc, Mutex};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

const STARTUP_SCHEMA: &str = "hey-jarvis-startup-v1";
const LOG_LIMIT: u64 = 256 * 1024;
const LOG_GENERATIONS: usize = 5;
const MAX_ELAPSED_MS: u64 = 300_000;

const NATIVE_STAGES: &[&str] = &[
    "process_entry",
    "setup_started",
    "paths_ready",
    "preferences_loaded",
    "sidecar_starting",
    "sidecar_ready",
    "window_shown",
    "setup_completed",
    "voice_ready",
];
const WEBVIEW_STAGES: &[&str] = &[
    "script_started",
    "dom_ready",
    "first_paint",
    "shell_interactive",
    "home_script_started",
    "home_first_paint",
    "home_interactive",
];
const SIDECAR_STAGES: &[&str] = &[
    "process_started",
    "imports_ready",
    "runtime_starting",
    "settings_loaded",
    "credential_validated",
    "wake_model_ready",
    "server_bound",
    "controller_started",
    "runtime_ready",
];

#[derive(Clone)]
pub struct StartupTrace {
    launch_id: String,
    origin: Instant,
    build_profile: &'static str,
    sample_kind: String,
    sender: SyncSender<StartupRecord>,
    seen: Arc<Mutex<HashSet<(String, String)>>>,
}

#[derive(Debug, Serialize)]
struct StartupRecord {
    schema: &'static str,
    launch_id: String,
    build_profile: &'static str,
    sample_kind: String,
    component: String,
    stage: String,
    receipt_elapsed_ms: u64,
    process_elapsed_ms: Option<u64>,
}

impl StartupTrace {
    pub fn new(app_support: &Path, origin: Instant) -> Self {
        let launch_id = format!(
            "launch-{}-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis(),
            std::process::id()
        );
        let build_profile = if cfg!(debug_assertions) {
            "debug"
        } else {
            "release"
        };
        let sample_kind = match std::env::var("HEY_JARVIS_STARTUP_SAMPLE_KIND").as_deref() {
            Ok("cold") => "cold",
            Ok("warm") => "warm",
            _ => "unspecified",
        }
        .to_string();
        let (sender, receiver) = mpsc::sync_channel::<StartupRecord>(128);
        let root = app_support.join("diagnostics");
        std::thread::spawn(move || {
            while let Ok(record) = receiver.recv() {
                write_record(&root, &record);
            }
        });
        let trace = Self {
            launch_id,
            origin,
            build_profile,
            sample_kind,
            sender,
            seen: Arc::new(Mutex::new(HashSet::new())),
        };
        trace.record_at("native", "process_entry", None, 0);
        trace
    }

    pub fn launch_id(&self) -> &str {
        &self.launch_id
    }
    pub fn record_native(&self, stage: &str) {
        self.record("native", stage, None);
    }
    pub fn record_webview(&self, stage: &str, elapsed_ms: u64) {
        self.record("webview", stage, Some(elapsed_ms));
    }
    pub fn record_sidecar(&self, stage: &str, elapsed_ms: u64) {
        self.record("sidecar", stage, Some(elapsed_ms));
    }

    fn record(&self, component: &str, stage: &str, process_elapsed_ms: Option<u64>) {
        let receipt_elapsed_ms = self
            .origin
            .elapsed()
            .as_millis()
            .min(MAX_ELAPSED_MS as u128) as u64;
        self.record_at(component, stage, process_elapsed_ms, receipt_elapsed_ms);
    }

    fn record_at(
        &self,
        component: &str,
        stage: &str,
        process_elapsed_ms: Option<u64>,
        receipt_elapsed_ms: u64,
    ) {
        if !allowed(component, stage) || process_elapsed_ms.is_some_and(|v| v > MAX_ELAPSED_MS) {
            return;
        }
        let Ok(mut seen) = self.seen.lock() else {
            return;
        };
        if !seen.insert((component.into(), stage.into())) {
            return;
        }
        drop(seen);
        let _ = self.sender.try_send(StartupRecord {
            schema: STARTUP_SCHEMA,
            launch_id: self.launch_id.clone(),
            build_profile: self.build_profile,
            sample_kind: self.sample_kind.clone(),
            component: component.into(),
            stage: stage.into(),
            receipt_elapsed_ms,
            process_elapsed_ms,
        });
    }
}

fn allowed(component: &str, stage: &str) -> bool {
    match component {
        "native" => NATIVE_STAGES.contains(&stage),
        "webview" => WEBVIEW_STAGES.contains(&stage),
        "sidecar" => SIDECAR_STAGES.contains(&stage),
        _ => false,
    }
}

fn write_record(root: &Path, record: &StartupRecord) {
    let Ok(encoded) = serde_json::to_string(record) else {
        return;
    };
    if encoded.len() > 512 || fs::create_dir_all(root).is_err() {
        return;
    }
    let path = root.join("startup.jsonl");
    rotate(&path);
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "{encoded}");
    }
}

fn rotate(path: &Path) {
    if path.metadata().map(|meta| meta.len()).unwrap_or(0) < LOG_LIMIT {
        return;
    }
    for generation in (1..LOG_GENERATIONS).rev() {
        let from = path.with_extension(format!("jsonl.{generation}"));
        let to = path.with_extension(format!("jsonl.{}", generation + 1));
        if from.exists() {
            let _ = fs::rename(from, to);
        }
    }
    let _ = fs::rename(path, path.with_extension("jsonl.1"));
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::Duration;

    static NEXT_TEMP: AtomicU64 = AtomicU64::new(1);
    fn temp_root() -> std::path::PathBuf {
        std::env::temp_dir().join(format!(
            "hey-jarvis-startup-{}-{}",
            std::process::id(),
            NEXT_TEMP.fetch_add(1, Ordering::Relaxed)
        ))
    }

    #[test]
    fn records_only_allowlisted_correlated_milestones() {
        let root = temp_root();
        let trace = StartupTrace::new(&root, Instant::now());
        trace.record_native("setup_started");
        trace.record_webview("first_paint", 12);
        trace.record_sidecar("wake_model_ready", 34);
        trace.record_webview("transcript", 50);
        std::thread::sleep(Duration::from_millis(40));
        let text = fs::read_to_string(root.join("diagnostics/startup.jsonl")).expect("startup log");
        assert!(text.contains(STARTUP_SCHEMA));
        assert!(text.contains(trace.launch_id()));
        assert!(text.contains("first_paint"));
        assert!(text.contains("wake_model_ready"));
        assert!(!text.contains("transcript"));
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn rejects_unbounded_child_elapsed_values() {
        let root = temp_root();
        let trace = StartupTrace::new(&root, Instant::now());
        trace.record_sidecar("runtime_ready", MAX_ELAPSED_MS + 1);
        std::thread::sleep(Duration::from_millis(40));
        let text = fs::read_to_string(root.join("diagnostics/startup.jsonl")).expect("startup log");
        assert!(!text.contains("runtime_ready"));
        let _ = fs::remove_dir_all(root);
    }
}
