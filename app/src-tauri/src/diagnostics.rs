use serde::Serialize;
use serde_json::{json, Value};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

const LOG_LIMIT: u64 = 512 * 1024;
const LOG_GENERATIONS: usize = 3;
const EXPORT_LIMIT: usize = 2 * 1024 * 1024;
const FORBIDDEN: &[&str] = &[
    "sk-",
    "api_key",
    "authorization",
    "sdp",
    "candidate",
    "transcript",
    "answer",
    "tool_arguments",
    "provider_body",
    "audio/",
];

#[derive(Clone)]
pub struct Diagnostics {
    root: PathBuf,
    lock: Arc<Mutex<()>>,
}

#[derive(Debug, Serialize)]
pub struct SupportExport {
    pub path: String,
    pub bytes: usize,
    pub records: usize,
}

impl Diagnostics {
    pub fn new(app_support: &Path) -> Self {
        Self {
            root: app_support.join("diagnostics"),
            lock: Arc::new(Mutex::new(())),
        }
    }

    pub fn record(&self, component: &str, event: &str, session: Option<&str>, state: Option<&str>) {
        if !safe_identifier(component) || !safe_identifier(event) {
            return;
        }
        let session = session.filter(|value| safe_session(value));
        let state = state.filter(|value| safe_identifier(value));
        let record = json!({
            "schema": 1,
            "at_ms": now_ms(),
            "component": component,
            "event": event,
            "session": session,
            "state": state,
        });
        let Ok(encoded) = serde_json::to_string(&record) else {
            return;
        };
        if forbidden(&encoded) {
            return;
        }
        let Ok(_guard) = self.lock.lock() else { return };
        if fs::create_dir_all(&self.root).is_err() {
            return;
        }
        let path = self.root.join("native.jsonl");
        rotate(&path);
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(file, "{encoded}");
        }
    }

    pub fn clear(&self) -> Result<(), String> {
        let _guard = self.lock.lock().map_err(|_| "diagnostics_unavailable")?;
        if self.root.exists() {
            for entry in fs::read_dir(&self.root).map_err(|_| "diagnostics_unavailable")? {
                let path = entry.map_err(|_| "diagnostics_unavailable")?.path();
                if path.is_file() {
                    fs::remove_file(path).map_err(|_| "diagnostics_unavailable")?;
                }
            }
        }
        Ok(())
    }

    pub fn export(&self, app_support: &Path) -> Result<SupportExport, String> {
        let _guard = self.lock.lock().map_err(|_| "diagnostics_unavailable")?;
        let mut records: Vec<Value> = Vec::new();
        if self.root.exists() {
            let mut paths: Vec<_> = fs::read_dir(&self.root)
                .map_err(|_| "diagnostics_unavailable")?
                .filter_map(Result::ok)
                .map(|entry| entry.path())
                .filter(|path| path.is_file())
                .collect();
            paths.sort();
            for path in paths {
                let text = fs::read_to_string(path).map_err(|_| "diagnostics_unavailable")?;
                for line in text.lines() {
                    if let Ok(value) = serde_json::from_str::<Value>(line) {
                        if forbidden(line) && !safe_realtime_summary(&value) {
                            continue;
                        }
                        records.push(value);
                    }
                }
            }
        }
        let bundle = json!({
            "schema": "hey-jarvis-support-v1",
            "created_at_ms": now_ms(),
            "privacy": "lifecycle-only redacted allowlist",
            "records": records,
        });
        let encoded = serde_json::to_vec_pretty(&bundle).map_err(|_| "support_export_failed")?;
        // Every source record was already filtered above. Re-scanning the
        // assembled bundle as an unstructured string would incorrectly reject
        // safe structured codes such as `invalid_api_key`.
        if encoded.len() > EXPORT_LIMIT {
            return Err("support_export_rejected".into());
        }
        let exports = app_support.join("support-exports");
        fs::create_dir_all(&exports).map_err(|_| "support_export_failed")?;
        let path = exports.join(format!("hey-jarvis-support-{}.json", now_ms()));
        fs::write(&path, &encoded).map_err(|_| "support_export_failed")?;
        Ok(SupportExport {
            path: path.display().to_string(),
            bytes: encoded.len(),
            records: records.len(),
        })
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

fn safe_identifier(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 64
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'-' | b'.'))
}

fn safe_session(value: &str) -> bool {
    value.starts_with("session-") && value.len() <= 64 && safe_identifier(value)
}

fn safe_realtime_identifier(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 100
        && !value.to_ascii_lowercase().starts_with("sk-")
        && !value.to_ascii_lowercase().starts_with("ek_")
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'-' | b'.' | b':'))
}

fn safe_realtime_summary(value: &Value) -> bool {
    let Some(record) = value.as_object() else {
        return false;
    };
    const ALLOWED: &[&str] = &[
        "schema",
        "at_ms",
        "component",
        "event",
        "session",
        "local_http_status",
        "upstream_http_status",
        "error_type",
        "error_code",
    ];
    if record.keys().any(|key| !ALLOWED.contains(&key.as_str()))
        || record.get("schema").and_then(Value::as_str) != Some("hey-jarvis-realtime-v1")
        || record.get("component").and_then(Value::as_str) != Some("python")
        || record.get("event").and_then(Value::as_str) != Some("realtime_negotiation_failed")
        || record.get("at_ms").and_then(Value::as_u64).is_none()
    {
        return false;
    }
    if let Some(session) = record.get("session") {
        if !session.is_null() && !session.as_str().map(safe_session).unwrap_or(false) {
            return false;
        }
    }
    for field in ["local_http_status", "upstream_http_status"] {
        if field == "local_http_status" || record.contains_key(field) {
            let Some(status) = record.get(field).and_then(Value::as_u64) else {
                return false;
            };
            if !(400..=599).contains(&status) {
                return false;
            }
        }
    }
    for field in ["error_type", "error_code"] {
        if let Some(identifier) = record.get(field) {
            if !identifier
                .as_str()
                .map(safe_realtime_identifier)
                .unwrap_or(false)
            {
                return false;
            }
        }
    }
    true
}

fn forbidden(value: &str) -> bool {
    let lower = value.to_ascii_lowercase();
    FORBIDDEN.iter().any(|marker| lower.contains(marker))
}

fn now_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT_TEMP: AtomicU64 = AtomicU64::new(1);

    fn temp_root() -> PathBuf {
        std::env::temp_dir().join(format!(
            "hey-jarvis-diagnostics-{}-{}-{}",
            std::process::id(),
            now_ms(),
            NEXT_TEMP.fetch_add(1, Ordering::Relaxed)
        ))
    }

    #[test]
    fn export_is_versioned_and_rejects_sensitive_events() {
        let root = temp_root();
        let diagnostics = Diagnostics::new(&root);
        diagnostics.record(
            "native",
            "sidecar_started",
            Some("session-safe"),
            Some("ready"),
        );
        diagnostics.record("native", "sk-secret", None, None);
        let export = diagnostics.export(&root).expect("export");
        let text = fs::read_to_string(export.path).expect("bundle");
        assert!(text.contains("hey-jarvis-support-v1"));
        assert!(text.contains("sidecar_started"));
        assert!(!text.contains("sk-secret"));
        assert_eq!(export.records, 1);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn clear_removes_rotated_diagnostics() {
        let root = temp_root();
        let diagnostics = Diagnostics::new(&root);
        diagnostics.record("webview", "loaded", None, None);
        diagnostics.clear().expect("clear");
        assert_eq!(
            fs::read_dir(root.join("diagnostics"))
                .expect("directory")
                .count(),
            0
        );
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn export_includes_content_free_wake_diagnostics() {
        let root = temp_root();
        let diagnostics = Diagnostics::new(&root);
        fs::create_dir_all(root.join("diagnostics")).expect("directory");
        let wake = json!({
            "schema": "hey-jarvis-wake-v1",
            "at_ms": 1234,
            "event": "confirmed",
            "score": 0.7,
            "threshold": 0.5,
            "consecutive": 2,
            "required": 2,
            "rms": 412.0,
            "peak": 800,
            "overflow": false
        });
        fs::write(
            root.join("diagnostics/wake.jsonl"),
            format!("{}\n", serde_json::to_string(&wake).expect("wake record")),
        )
        .expect("wake log");
        let export = diagnostics.export(&root).expect("export");
        let text = fs::read_to_string(export.path).expect("bundle");
        assert!(text.contains("hey-jarvis-wake-v1"));
        assert!(text.contains("confirmed"));
        assert!(!text.contains("transcript"));
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn export_includes_safe_realtime_negotiation_summary() {
        let root = temp_root();
        let diagnostics = Diagnostics::new(&root);
        fs::create_dir_all(root.join("diagnostics")).expect("directory");
        let realtime = json!({
            "schema": "hey-jarvis-realtime-v1",
            "at_ms": 1234,
            "component": "python",
            "event": "realtime_negotiation_failed",
            "session": "session-safe",
            "local_http_status": 409,
            "upstream_http_status": 429,
            "error_type": "insufficient_quota",
            "error_code": "invalid_api_key"
        });
        fs::write(
            root.join("diagnostics/realtime.jsonl"),
            format!(
                "{}\n",
                serde_json::to_string(&realtime).expect("realtime record")
            ),
        )
        .expect("realtime log");
        let export = diagnostics.export(&root).expect("export");
        let text = fs::read_to_string(export.path).expect("bundle");
        assert!(text.contains("hey-jarvis-realtime-v1"));
        assert!(text.contains("invalid_api_key"));
        assert!(!text.contains("provider_body"));
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn export_rejects_secret_shaped_or_extra_realtime_summary_fields() {
        let root = temp_root();
        let diagnostics = Diagnostics::new(&root);
        fs::create_dir_all(root.join("diagnostics")).expect("directory");
        let unsafe_records = [
            json!({
                "schema": "hey-jarvis-realtime-v1",
                "at_ms": 1234,
                "component": "python",
                "event": "realtime_negotiation_failed",
                "session": "session-safe",
                "local_http_status": 409,
                "error_code": "sk-secret"
            }),
            json!({
                "schema": "hey-jarvis-realtime-v1",
                "at_ms": 1234,
                "component": "python",
                "event": "realtime_negotiation_failed",
                "session": "session-safe",
                "local_http_status": 409,
                "message": "api_key"
            }),
        ];
        fs::write(
            root.join("diagnostics/realtime.jsonl"),
            unsafe_records
                .iter()
                .map(|record| serde_json::to_string(record).expect("record"))
                .collect::<Vec<_>>()
                .join("\n"),
        )
        .expect("realtime log");
        let export = diagnostics.export(&root).expect("export");
        let text = fs::read_to_string(export.path).expect("bundle");
        assert!(!text.contains("sk-secret"));
        assert!(!text.contains("\"message\""));
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn rotation_and_export_size_limit_are_enforced() {
        let root = temp_root();
        let diagnostics = Diagnostics::new(&root);
        fs::create_dir_all(root.join("diagnostics")).expect("directory");
        let log = root.join("diagnostics/native.jsonl");
        fs::write(&log, vec![b' '; LOG_LIMIT as usize]).expect("large log");
        diagnostics.record("native", "rotated", None, Some("safe"));
        assert!(root.join("diagnostics/native.jsonl.1").is_file());

        let event = serde_json::to_string(&json!({
            "schema": 1, "component": "native", "event": "safe", "state": "safe"
        }))
        .expect("record");
        fs::write(&log, format!("{}\n", event).repeat(40_000)).expect("oversized records");
        assert_eq!(
            diagnostics.export(&root).unwrap_err(),
            "support_export_rejected"
        );
        let _ = fs::remove_dir_all(root);
    }
}
