use crate::credentials::RuntimeCredentials;
use crate::diagnostics::Diagnostics;
use crate::protocol::{decode, encode, Envelope, Payload, PROTOCOL_VERSION};
use serde::Serialize;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

// Real startup includes loading and warming the wake model plus acquiring the
// built-in microphone. Keep this bounded, but do not apply the fake fixture's
// sub-second expectation to the product runtime.
const START_TIMEOUT: Duration = Duration::from_secs(30);
// The Python runtime joins its microphone controller for up to four seconds
// before finalizing PortAudio. Keep the native grace period longer so normal
// shutdown is never converted into a forced kill mid-cleanup.
const STOP_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_RESTARTS: u8 = 3;
const RESTART_BACKOFF: Duration = Duration::from_millis(250);

#[derive(Clone, Debug, Serialize)]
pub struct RuntimeSnapshot {
    pub state: String,
    pub availability: String,
    pub detail: String,
    pub protocol_version: u16,
    pub session_id: String,
    pub app_support_dir: String,
    pub control_url: Option<String>,
}

impl RuntimeSnapshot {
    fn stopped(app_support_dir: &Path) -> Self {
        Self {
            state: "stopped".into(),
            availability: "resume_required".into(),
            detail: "Sidecar is not running.".into(),
            protocol_version: PROTOCOL_VERSION,
            session_id: String::new(),
            app_support_dir: app_support_dir.display().to_string(),
            control_url: None,
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
    resource_dir: PathBuf,
    launch: SidecarLaunch,
    snapshot: Arc<Mutex<RuntimeSnapshot>>,
    diagnostics: Diagnostics,
    desired_running: bool,
    restart_attempts: u8,
}

enum SidecarLaunch {
    Executable(PathBuf),
    PythonDevelopment {
        interpreter: String,
        script: PathBuf,
    },
}

impl SidecarSupervisor {
    pub fn new(app_support_dir: PathBuf, resource_dir: PathBuf, script_path: PathBuf) -> Self {
        let snapshot = Arc::new(Mutex::new(RuntimeSnapshot::stopped(&app_support_dir)));
        let diagnostics = Diagnostics::new(&app_support_dir);
        let launch = if let Some(path) = std::env::var_os("HEY_JARVIS_SIDECAR_EXECUTABLE") {
            SidecarLaunch::Executable(PathBuf::from(path))
        } else if cfg!(debug_assertions) {
            SidecarLaunch::PythonDevelopment {
                interpreter: development_python_interpreter(),
                script: script_path,
            }
        } else {
            SidecarLaunch::Executable(resource_dir.join("sidecar/hey-jarvis-sidecar"))
        };
        Self {
            child: None,
            stdin: None,
            reader: None,
            next_sequence: 1,
            session_id: String::new(),
            app_support_dir,
            resource_dir,
            launch,
            snapshot,
            diagnostics,
            desired_running: false,
            restart_attempts: 0,
        }
    }

    #[cfg(test)]
    fn with_python(
        app_support_dir: PathBuf,
        resource_dir: PathBuf,
        script_path: PathBuf,
        python_command: String,
    ) -> Self {
        let mut supervisor = Self::new(app_support_dir, resource_dir, script_path);
        supervisor.launch = SidecarLaunch::PythonDevelopment {
            interpreter: python_command,
            script: match &supervisor.launch {
                SidecarLaunch::PythonDevelopment { script, .. } => script.clone(),
                SidecarLaunch::Executable(path) => path.clone(),
            },
        };
        supervisor
    }

    #[cfg(test)]
    pub fn start(&mut self) -> Result<RuntimeSnapshot, String> {
        self.start_with_credentials(None)
    }

    pub fn start_with_credentials(
        &mut self,
        credentials: Option<&RuntimeCredentials>,
    ) -> Result<RuntimeSnapshot, String> {
        self.stop("restart")?;
        self.desired_running = true;
        self.restart_attempts = 0;
        std::fs::create_dir_all(&self.app_support_dir)
            .map_err(|error| format!("cannot create app support directory: {error}"))?;
        let sidecar_path = match &self.launch {
            SidecarLaunch::Executable(path) => path,
            SidecarLaunch::PythonDevelopment { script, .. } => script,
        };
        if !sidecar_path.is_file() {
            return self.fail(format!("sidecar is missing: {}", sidecar_path.display()));
        }

        self.session_id = new_session_id()?;
        self.diagnostics.record(
            "native",
            "sidecar_starting",
            Some(&self.session_id),
            Some("starting"),
        );
        self.next_sequence = 1;
        if let Ok(mut snapshot) = self.snapshot.lock() {
            snapshot.state = "starting".into();
            snapshot.availability = "resume_required".into();
            snapshot.detail = "Starting the sidecar.".into();
            snapshot.session_id = self.session_id.clone();
            snapshot.app_support_dir = self.app_support_dir.display().to_string();
            snapshot.control_url = None;
        }
        let mut command = match &self.launch {
            SidecarLaunch::Executable(path) => Command::new(path),
            SidecarLaunch::PythonDevelopment {
                interpreter,
                script,
            } => {
                let mut command = Command::new(interpreter);
                command.arg("-I").arg(script);
                command
            }
        };
        let mut child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| format!("cannot start sidecar: {error}"))?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(|| "sidecar stdin is unavailable".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "sidecar stdout is unavailable".to_string())?;

        if let Some(credentials) = credentials {
            let mut bootstrap = credentials.private_bootstrap()?;
            let result = stdin
                .write_all(&bootstrap)
                .and_then(|_| stdin.flush())
                .map_err(|_| "credential bootstrap write failed".to_string());
            bootstrap.fill(0);
            if let Err(error) = result {
                let _ = child.kill();
                let _ = child.wait();
                return self.fail(error);
            }
        }

        let startup = self.outbound(Payload::Startup {
            app_version: env!("CARGO_PKG_VERSION").into(),
            app_support_dir: self.app_support_dir.display().to_string(),
            resource_dir: self.resource_dir.display().to_string(),
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
                        set_availability(&snapshot, "resume_required");
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
            .map_err(|_| "sidecar readiness timed out".to_string())
            .and_then(|result| {
                result.map_err(|error| format!("sidecar readiness read failed: {error}"))
            })
            .and_then(|line| line.ok_or_else(|| "sidecar exited before readiness".to_string()));
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
        match ready.payload {
            Payload::Ready { control_url, .. } => {
                if let Ok(mut snapshot) = self.snapshot.lock() {
                    snapshot.control_url = control_url;
                }
            }
            Payload::Error { code, .. } => {
                let _ = self.stop("startup_failure");
                return self.fail(format!("Sidecar startup failed: {code}"));
            }
            _ => {
                let _ = self.stop("startup_failure");
                return self.fail("sidecar did not send readiness".into());
            }
        }

        set_snapshot(&self.snapshot, "ready", "Sidecar is healthy.");
        set_availability(&self.snapshot, "ready");
        self.diagnostics.record(
            "native",
            "sidecar_ready",
            Some(&self.session_id),
            Some("ready"),
        );
        Ok(self.snapshot())
    }

    pub fn needs_recovery(&mut self) -> bool {
        if !self.desired_running {
            return false;
        }
        match self.child.as_mut() {
            Some(child) => child.try_wait().ok().flatten().is_some(),
            None => true,
        }
    }

    pub fn recover_if_needed(
        &mut self,
        credentials: &RuntimeCredentials,
    ) -> Result<RuntimeSnapshot, String> {
        self.recover_with_credentials(Some(credentials))
    }

    fn recover_with_credentials(
        &mut self,
        credentials: Option<&RuntimeCredentials>,
    ) -> Result<RuntimeSnapshot, String> {
        if !self.needs_recovery() {
            return Ok(self.snapshot());
        }
        self.stdin.take();
        self.child.take();
        if let Some(reader) = self.reader.take() {
            let _ = reader.join();
        }
        self.diagnostics.record(
            "native",
            "sidecar_unexpected_exit",
            Some(&self.session_id),
            Some("non_listening"),
        );
        set_availability(&self.snapshot, "resume_required");
        if self.restart_attempts >= MAX_RESTARTS {
            self.desired_running = false;
            set_snapshot(
                &self.snapshot,
                "crash_loop",
                "Sidecar crash loop; listening remains off.",
            );
            set_availability(&self.snapshot, "resume_required");
            self.diagnostics.record(
                "native",
                "sidecar_crash_loop",
                Some(&self.session_id),
                Some("non_listening"),
            );
            return Err("sidecar_crash_loop".into());
        }
        let attempt = self.restart_attempts + 1;
        thread::sleep(RESTART_BACKOFF * u32::from(attempt));
        let result = self.start_with_credentials(credentials);
        self.restart_attempts = attempt;
        if result.is_err() {
            self.desired_running = true;
            set_snapshot(
                &self.snapshot,
                "degraded",
                format!("Sidecar recovery attempt {attempt} failed; listening remains off."),
            );
            set_availability(&self.snapshot, "resume_required");
            self.diagnostics.record(
                "native",
                "sidecar_restart_failed",
                Some(&self.session_id),
                Some("non_listening"),
            );
        } else {
            self.diagnostics.record(
                "native",
                "sidecar_restarted",
                Some(&self.session_id),
                Some("ready"),
            );
        }
        result
    }

    pub fn health(&mut self) -> Result<RuntimeSnapshot, String> {
        if let Err(error) = self.send(Payload::Lifecycle {
            event: "health_check".into(),
            detail: None,
        }) {
            set_availability(&self.snapshot, "resume_required");
            return Err(error);
        }
        Ok(self.snapshot())
    }

    pub fn stop(&mut self, reason: &str) -> Result<(), String> {
        self.desired_running = false;
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
        set_availability(&self.snapshot, "resume_required");
        self.diagnostics.record(
            "native",
            "sidecar_stopped",
            Some(&self.session_id),
            Some("non_listening"),
        );
        Ok(())
    }

    pub fn snapshot(&self) -> RuntimeSnapshot {
        self.snapshot
            .lock()
            .map(|snapshot| snapshot.clone())
            .unwrap_or_else(|_| RuntimeSnapshot {
                state: "error".into(),
                availability: "resume_required".into(),
                detail: "Sidecar status lock is unavailable.".into(),
                protocol_version: PROTOCOL_VERSION,
                session_id: self.session_id.clone(),
                app_support_dir: self.app_support_dir.display().to_string(),
                control_url: None,
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
        set_availability(&self.snapshot, "resume_required");
        self.diagnostics.record(
            "native",
            "sidecar_failed",
            Some(&self.session_id),
            Some("non_listening"),
        );
        Err(detail)
    }
}

#[cfg(debug_assertions)]
fn development_python_interpreter() -> String {
    if let Ok(configured) = std::env::var("HEY_JARVIS_SIDECAR_PYTHON") {
        return configured;
    }
    let project_venv = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../.venv/bin/python");
    if project_venv.is_file() {
        return project_venv.display().to_string();
    }
    "python3".into()
}

#[cfg(not(debug_assertions))]
fn development_python_interpreter() -> String {
    // This branch is never selected by a release SidecarSupervisor. Avoid
    // compiling the repository-local virtualenv path into release artifacts.
    "python3".into()
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

fn set_availability(snapshot: &Arc<Mutex<RuntimeSnapshot>>, availability: &str) {
    if let Ok(mut current) = snapshot.lock() {
        current.availability = availability.into();
    }
}

fn update_from_payload(snapshot: &Arc<Mutex<RuntimeSnapshot>>, payload: Payload) {
    match payload {
        Payload::Lifecycle { event, detail } => {
            if event == "voice_availability" {
                let availability = detail.unwrap_or_default();
                if matches!(
                    availability.as_str(),
                    "ready" | "wake_listening" | "busy" | "resume_required"
                ) {
                    set_snapshot(
                        snapshot,
                        "ready",
                        format!("Voice availability: {availability}"),
                    );
                    set_availability(snapshot, &availability);
                } else {
                    set_snapshot(
                        snapshot,
                        "error",
                        "Sidecar sent invalid voice availability.",
                    );
                    set_availability(snapshot, "resume_required");
                }
                return;
            }
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
            set_availability(snapshot, "resume_required");
        }
        _ => {
            set_snapshot(
                snapshot,
                "error",
                "Sidecar sent a message that is invalid in this lifecycle state.",
            );
            set_availability(snapshot, "resume_required");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> (PathBuf, PathBuf, PathBuf, String) {
        let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let script = manifest.join("../sidecar/fake_sidecar.py");
        let support = std::env::temp_dir().join(format!(
            "hey-jarvis-f087-{}",
            new_session_id().expect("session")
        ));
        let python = std::env::var("PYTHON").unwrap_or_else(|_| "python3".into());
        let resources = manifest.join("../../");
        (support, resources, script, python)
    }

    #[test]
    fn starts_health_checks_and_stops_fake_sidecar() {
        let (support, resources, script, python) = fixture();
        let mut supervisor = SidecarSupervisor::with_python(support, resources, script, python);
        let started = supervisor.start().expect("sidecar starts");
        assert_eq!(started.state, "ready");
        assert_eq!(started.availability, "ready");
        assert!(started.session_id.starts_with("session-"));

        let health = supervisor.health().expect("health request");
        assert_eq!(health.state, "ready");
        for _ in 0..20 {
            if supervisor.snapshot().detail == "Voice availability: ready" {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        assert_eq!(supervisor.snapshot().availability, "ready");
        supervisor.stop("test").expect("sidecar stops");
        assert_eq!(supervisor.snapshot().state, "stopped");
        assert_eq!(supervisor.snapshot().availability, "resume_required");
    }

    #[test]
    fn missing_sidecar_fails_closed() {
        let (support, resources, _, python) = fixture();
        let mut supervisor = SidecarSupervisor::with_python(
            support,
            resources,
            PathBuf::from("/missing/fake.py"),
            python,
        );
        assert!(supervisor.start().is_err());
        assert_eq!(supervisor.snapshot().state, "error");
        assert_eq!(supervisor.snapshot().availability, "resume_required");
    }

    #[test]
    fn invalid_voice_availability_fails_closed() {
        let (support, _, _, _) = fixture();
        let snapshot = Arc::new(Mutex::new(RuntimeSnapshot::stopped(&support)));
        update_from_payload(
            &snapshot,
            Payload::Lifecycle {
                event: "voice_availability".into(),
                detail: Some("invented_state".into()),
            },
        );
        let current = snapshot.lock().expect("snapshot").clone();
        assert_eq!(current.state, "error");
        assert_eq!(current.availability, "resume_required");
    }

    #[test]
    fn session_ids_are_bounded_and_distinct() {
        let first = new_session_id().expect("session");
        let second = new_session_id().expect("session");
        assert_ne!(first, second);
        assert!(first.len() <= crate::protocol::MAX_SESSION_ID_LENGTH);
    }

    #[test]
    fn intentional_stop_never_requests_recovery() {
        let (support, resources, script, python) = fixture();
        let mut supervisor = SidecarSupervisor::with_python(support, resources, script, python);
        supervisor.start().expect("start");
        supervisor.stop("test").expect("stop");
        assert!(!supervisor.needs_recovery());
        assert_eq!(supervisor.snapshot().state, "stopped");
    }

    #[test]
    fn unexpected_exit_restarts_with_a_bounded_crash_loop() {
        let (support, resources, script, python) = fixture();
        let mut supervisor = SidecarSupervisor::with_python(support, resources, script, python);
        supervisor.start().expect("start");
        for expected_attempt in 1..=MAX_RESTARTS {
            supervisor
                .child
                .as_mut()
                .expect("child")
                .kill()
                .expect("kill");
            supervisor
                .child
                .as_mut()
                .expect("child")
                .wait()
                .expect("wait");
            assert!(supervisor.needs_recovery());
            supervisor
                .recover_with_credentials(None)
                .expect("bounded restart");
            assert_eq!(supervisor.restart_attempts, expected_attempt);
        }
        supervisor
            .child
            .as_mut()
            .expect("child")
            .kill()
            .expect("kill");
        supervisor
            .child
            .as_mut()
            .expect("child")
            .wait()
            .expect("wait");
        assert_eq!(
            supervisor.recover_with_credentials(None).unwrap_err(),
            "sidecar_crash_loop"
        );
        assert_eq!(supervisor.snapshot().state, "crash_loop");
        assert!(!supervisor.desired_running);
        assert!(supervisor.child.is_none());
    }

    #[test]
    fn repeated_launch_and_quit_leave_no_child_handle() {
        let (support, resources, script, python) = fixture();
        let mut supervisor = SidecarSupervisor::with_python(support, resources, script, python);
        for _ in 0..5 {
            supervisor.start().expect("start");
            supervisor.stop("repeated_quit").expect("stop");
            assert!(supervisor.child.is_none());
            assert!(supervisor.stdin.is_none());
            assert!(supervisor.reader.is_none());
        }
    }
}
