use crate::protocol::{decode, encode, Envelope, Payload, PROTOCOL_VERSION};
use serde::Serialize;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

const START_TIMEOUT: Duration = Duration::from_secs(3);
const STOP_TIMEOUT: Duration = Duration::from_secs(2);

#[derive(Clone, Debug, Serialize)]
pub struct RuntimeSnapshot {
    pub state: String,
    pub detail: String,
    pub protocol_version: u16,
    pub session_id: String,
    pub app_support_dir: String,
}

impl RuntimeSnapshot {
    fn stopped(app_support_dir: &Path) -> Self {
        Self {
            state: "stopped".into(),
            detail: "Sidecar is not running.".into(),
            protocol_version: PROTOCOL_VERSION,
            session_id: String::new(),
            app_support_dir: app_support_dir.display().to_string(),
        }
    }
}

pub struct SidecarSupervisor {
    child: Option<Child>,
    stdin: Option<ChildStdin>,
    reader: Option<JoinHandle<()>>,
    next_sequence: u64,
    session_id: String,
    app_support_dir: PathBuf,
    script_path: PathBuf,
    python_command: String,
    snapshot: Arc<Mutex<RuntimeSnapshot>>,
}

impl SidecarSupervisor {
    pub fn new(app_support_dir: PathBuf, script_path: PathBuf) -> Self {
        let snapshot = Arc::new(Mutex::new(RuntimeSnapshot::stopped(&app_support_dir)));
        Self {
            child: None,
            stdin: None,
            reader: None,
            next_sequence: 1,
            session_id: String::new(),
            app_support_dir,
            script_path,
            python_command: std::env::var("HEY_JARVIS_FAKE_SIDECAR_PYTHON")
                .unwrap_or_else(|_| "python3".into()),
            snapshot,
        }
    }

    #[cfg(test)]
    fn with_python(app_support_dir: PathBuf, script_path: PathBuf, python_command: String) -> Self {
        let mut supervisor = Self::new(app_support_dir, script_path);
        supervisor.python_command = python_command;
        supervisor
    }

    pub fn start(&mut self) -> Result<RuntimeSnapshot, String> {
        self.stop("restart")?;
        std::fs::create_dir_all(&self.app_support_dir)
            .map_err(|error| format!("cannot create app support directory: {error}"))?;
        if !self.script_path.is_file() {
            return self.fail(format!(
                "fake sidecar is missing: {}",
                self.script_path.display()
            ));
        }

        self.session_id = new_session_id()?;
        self.next_sequence = 1;
        if let Ok(mut snapshot) = self.snapshot.lock() {
            snapshot.state = "starting".into();
            snapshot.detail = "Starting the fake sidecar.".into();
            snapshot.session_id = self.session_id.clone();
            snapshot.app_support_dir = self.app_support_dir.display().to_string();
        }
        let mut child = Command::new(&self.python_command)
            .arg("-I")
            .arg(&self.script_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| format!("cannot start fake sidecar: {error}"))?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(|| "fake sidecar stdin is unavailable".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "fake sidecar stdout is unavailable".to_string())?;

        let startup = self.outbound(Payload::Startup {
            app_version: env!("CARGO_PKG_VERSION").into(),
            app_support_dir: self.app_support_dir.display().to_string(),
        });
        write_message(&mut stdin, &startup)?;

        let (sender, receiver) = mpsc::sync_channel(1);
        let session = self.session_id.clone();
        let snapshot = Arc::clone(&self.snapshot);
        let reader = thread::spawn(move || {
            let mut lines = BufReader::new(stdout).lines();
            let ready = lines.next().transpose();
            let _ = sender.send(ready);

            let mut last_sequence = 1;
            for line in lines {
                let result = line
                    .map_err(|error| format!("sidecar output read failed: {error}"))
                    .and_then(|value| decode(&value, Some(&session), last_sequence));
                match result {
                    Ok(envelope) => {
                        last_sequence = envelope.sequence;
                        update_from_payload(&snapshot, envelope.payload);
                    }
                    Err(error) => {
                        set_snapshot(&snapshot, "error", error);
                        break;
                    }
                }
            }
        });

        self.child = Some(child);
        self.stdin = Some(stdin);
        self.reader = Some(reader);

        let ready_result = receiver
            .recv_timeout(START_TIMEOUT)
            .map_err(|_| "fake sidecar readiness timed out".to_string())
            .and_then(|result| {
                result.map_err(|error| format!("fake sidecar readiness read failed: {error}"))
            })
            .and_then(|line| {
                line.ok_or_else(|| "fake sidecar exited before readiness".to_string())
            });
        let ready_line = match ready_result {
            Ok(line) => line,
            Err(error) => {
                let _ = self.stop("startup_failure");
                return self.fail(error);
            }
        };
        let ready = match decode(&ready_line, Some(&self.session_id), 0) {
            Ok(message) => message,
            Err(error) => {
                let _ = self.stop("startup_failure");
                return self.fail(error);
            }
        };
        if !matches!(ready.payload, Payload::Ready { .. }) {
            let _ = self.stop("startup_failure");
            return self.fail("fake sidecar did not send readiness".into());
        }

        set_snapshot(&self.snapshot, "ready", "Fake sidecar is healthy.");
        Ok(self.snapshot())
    }

    pub fn health(&mut self) -> Result<RuntimeSnapshot, String> {
        self.send(Payload::Lifecycle {
            event: "health_check".into(),
            detail: None,
        })?;
        set_snapshot(
            &self.snapshot,
            "ready",
            "Health check requested from the fake sidecar.",
        );
        Ok(self.snapshot())
    }

    pub fn stop(&mut self, reason: &str) -> Result<(), String> {
        if self.child.is_none() {
            return Ok(());
        }
        if self.stdin.is_some() {
            let _ = self.send(Payload::Shutdown {
                reason: reason.into(),
            });
        }
        self.stdin.take();

        if let Some(child) = self.child.as_mut() {
            let deadline = Instant::now() + STOP_TIMEOUT;
            while Instant::now() < deadline {
                if child
                    .try_wait()
                    .map_err(|error| format!("sidecar wait failed: {error}"))?
                    .is_some()
                {
                    break;
                }
                thread::sleep(Duration::from_millis(20));
            }
            if child
                .try_wait()
                .map_err(|error| format!("sidecar wait failed: {error}"))?
                .is_none()
            {
                child
                    .kill()
                    .map_err(|error| format!("sidecar kill failed: {error}"))?;
                let _ = child.wait();
            }
        }
        self.child.take();
        if let Some(reader) = self.reader.take() {
            let _ = reader.join();
        }
        set_snapshot(&self.snapshot, "stopped", "Sidecar stopped.");
        Ok(())
    }

    pub fn snapshot(&self) -> RuntimeSnapshot {
        self.snapshot
            .lock()
            .map(|snapshot| snapshot.clone())
            .unwrap_or_else(|_| RuntimeSnapshot {
                state: "error".into(),
                detail: "Sidecar status lock is unavailable.".into(),
                protocol_version: PROTOCOL_VERSION,
                session_id: self.session_id.clone(),
                app_support_dir: self.app_support_dir.display().to_string(),
            })
    }

    fn outbound(&mut self, payload: Payload) -> Envelope {
        let envelope = Envelope {
            protocol_version: PROTOCOL_VERSION,
            sequence: self.next_sequence,
            session_id: self.session_id.clone(),
            payload,
        };
        self.next_sequence += 1;
        envelope
    }

    fn send(&mut self, payload: Payload) -> Result<(), String> {
        let envelope = self.outbound(payload);
        let stdin = self
            .stdin
            .as_mut()
            .ok_or_else(|| "sidecar is not running".to_string())?;
        write_message(stdin, &envelope)
    }

    fn fail<T>(&self, detail: String) -> Result<T, String> {
        set_snapshot(&self.snapshot, "error", &detail);
        Err(detail)
    }
}

impl Drop for SidecarSupervisor {
    fn drop(&mut self) {
        let _ = self.stop("supervisor_drop");
    }
}

fn write_message(stdin: &mut ChildStdin, envelope: &Envelope) -> Result<(), String> {
    let encoded = encode(envelope)?;
    stdin
        .write_all(format!("{encoded}\n").as_bytes())
        .and_then(|_| stdin.flush())
        .map_err(|error| format!("sidecar input write failed: {error}"))
}

fn new_session_id() -> Result<String, String> {
    let mut bytes = [0_u8; 16];
    getrandom::fill(&mut bytes)
        .map_err(|error| format!("session identity generation failed: {error}"))?;
    Ok(format!(
        "session-{}",
        bytes
            .iter()
            .map(|value| format!("{value:02x}"))
            .collect::<String>()
    ))
}

fn set_snapshot(snapshot: &Arc<Mutex<RuntimeSnapshot>>, state: &str, detail: impl Into<String>) {
    if let Ok(mut current) = snapshot.lock() {
        current.state = state.into();
        current.detail = detail.into();
    }
}

fn update_from_payload(snapshot: &Arc<Mutex<RuntimeSnapshot>>, payload: Payload) {
    match payload {
        Payload::Lifecycle { event, detail } => {
            let message = detail
                .map(|value| format!("{event}: {value}"))
                .unwrap_or(event);
            set_snapshot(snapshot, "ready", message);
        }
        Payload::Error { code, recoverable } => {
            set_snapshot(
                snapshot,
                if recoverable { "degraded" } else { "error" },
                format!("Sidecar error: {code}"),
            );
        }
        _ => set_snapshot(
            snapshot,
            "error",
            "Sidecar sent a message that is invalid in this lifecycle state.",
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> (PathBuf, PathBuf, String) {
        let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let script = manifest.join("../sidecar/fake_sidecar.py");
        let support = std::env::temp_dir().join(format!(
            "hey-jarvis-f087-{}",
            new_session_id().expect("session")
        ));
        let python = std::env::var("PYTHON").unwrap_or_else(|_| "python3".into());
        (support, script, python)
    }

    #[test]
    fn starts_health_checks_and_stops_fake_sidecar() {
        let (support, script, python) = fixture();
        let mut supervisor = SidecarSupervisor::with_python(support, script, python);
        let started = supervisor.start().expect("sidecar starts");
        assert_eq!(started.state, "ready");
        assert!(started.session_id.starts_with("session-"));

        let health = supervisor.health().expect("health request");
        assert_eq!(health.state, "ready");
        supervisor.stop("test").expect("sidecar stops");
        assert_eq!(supervisor.snapshot().state, "stopped");
    }

    #[test]
    fn missing_sidecar_fails_closed() {
        let (support, _, python) = fixture();
        let mut supervisor =
            SidecarSupervisor::with_python(support, PathBuf::from("/missing/fake.py"), python);
        assert!(supervisor.start().is_err());
        assert_eq!(supervisor.snapshot().state, "error");
    }

    #[test]
    fn session_ids_are_bounded_and_distinct() {
        let first = new_session_id().expect("session");
        let second = new_session_id().expect("session");
        assert_ne!(first, second);
        assert!(first.len() <= crate::protocol::MAX_SESSION_ID_LENGTH);
    }
}
