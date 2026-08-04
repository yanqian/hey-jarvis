use crate::diagnostics::Diagnostics;

pub trait PowerAssertionBackend: Send {
    fn acquire(&mut self) -> Result<u32, String>;
    fn release(&mut self, assertion_id: u32) -> Result<(), String>;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PowerSnapshot {
    pub enabled: bool,
    pub active: bool,
}

pub struct PowerPolicy {
    enabled: bool,
    assertion_id: Option<u32>,
    acquisition_blocked: bool,
    backend: Box<dyn PowerAssertionBackend>,
}

impl PowerPolicy {
    pub fn system(enabled: bool) -> Self {
        Self::with_backend(enabled, Box::new(SystemPowerAssertionBackend))
    }

    fn with_backend(enabled: bool, backend: Box<dyn PowerAssertionBackend>) -> Self {
        Self {
            enabled,
            assertion_id: None,
            acquisition_blocked: false,
            backend,
        }
    }

    pub fn snapshot(&self) -> PowerSnapshot {
        PowerSnapshot {
            enabled: self.enabled,
            active: self.assertion_id.is_some(),
        }
    }

    pub fn set_enabled(&mut self, enabled: bool, availability: &str, diagnostics: &Diagnostics) {
        if self.enabled != enabled {
            self.acquisition_blocked = false;
        }
        self.enabled = enabled;
        diagnostics.record(
            "native",
            "smart_speaker_mode_changed",
            None,
            Some(if enabled { "enabled" } else { "disabled" }),
        );
        self.reconcile(availability, "mode_changed", diagnostics);
    }

    pub fn update_availability(&mut self, availability: &str, diagnostics: &Diagnostics) {
        self.reconcile(availability, "voice_availability", diagnostics);
    }

    pub fn release(&mut self, reason: &str, diagnostics: &Diagnostics) {
        self.acquisition_blocked = false;
        let Some(assertion_id) = self.assertion_id.take() else {
            return;
        };
        let result = self.backend.release(assertion_id);
        diagnostics.record(
            "native",
            if result.is_ok() {
                "smart_speaker_assertion_released"
            } else {
                "smart_speaker_assertion_release_failed"
            },
            None,
            Some(reason),
        );
    }

    fn reconcile(&mut self, availability: &str, reason: &str, diagnostics: &Diagnostics) {
        if !self.enabled {
            self.release(reason, diagnostics);
            return;
        }

        // A real wake-listening state is the only state allowed to acquire an
        // assertion. Once acquired, keep it through the ensuing Busy handoff
        // so an already-expired idle timer cannot sleep the Mac between wake
        // detection and acknowledgement playback.
        if availability == "busy" && self.assertion_id.is_some() {
            return;
        }
        if availability != "wake_listening" {
            self.release(reason, diagnostics);
            return;
        }
        if self.assertion_id.is_some() || self.acquisition_blocked {
            return;
        }
        match self.backend.acquire() {
            Ok(assertion_id) => {
                self.assertion_id = Some(assertion_id);
                diagnostics.record(
                    "native",
                    "smart_speaker_assertion_acquired",
                    None,
                    Some("active"),
                );
            }
            Err(_) => {
                self.acquisition_blocked = true;
                diagnostics.record(
                    "native",
                    "smart_speaker_assertion_failed",
                    None,
                    Some("inactive"),
                );
            }
        }
    }
}

impl Drop for PowerPolicy {
    fn drop(&mut self) {
        if let Some(assertion_id) = self.assertion_id.take() {
            let _ = self.backend.release(assertion_id);
        }
    }
}

struct SystemPowerAssertionBackend;

#[cfg(target_os = "macos")]
impl PowerAssertionBackend for SystemPowerAssertionBackend {
    fn acquire(&mut self) -> Result<u32, String> {
        use core_foundation::base::TCFType;
        use core_foundation::string::{CFString, CFStringRef};

        #[link(name = "IOKit", kind = "framework")]
        extern "C" {
            fn IOPMAssertionCreateWithName(
                assertion_type: CFStringRef,
                assertion_level: u32,
                assertion_name: CFStringRef,
                assertion_id: *mut u32,
            ) -> i32;
        }

        let assertion_type = CFString::new("PreventUserIdleSystemSleep");
        let assertion_name = CFString::new("Hey Jarvis Smart Speaker Mode");
        let mut assertion_id = 0;
        let result = unsafe {
            IOPMAssertionCreateWithName(
                assertion_type.as_concrete_TypeRef(),
                255,
                assertion_name.as_concrete_TypeRef(),
                &mut assertion_id,
            )
        };
        if result == 0 {
            Ok(assertion_id)
        } else {
            Err("power_assertion_unavailable".into())
        }
    }

    fn release(&mut self, assertion_id: u32) -> Result<(), String> {
        #[link(name = "IOKit", kind = "framework")]
        extern "C" {
            fn IOPMAssertionRelease(assertion_id: u32) -> i32;
        }

        if unsafe { IOPMAssertionRelease(assertion_id) } == 0 {
            Ok(())
        } else {
            Err("power_assertion_release_failed".into())
        }
    }
}

#[cfg(not(target_os = "macos"))]
impl PowerAssertionBackend for SystemPowerAssertionBackend {
    fn acquire(&mut self) -> Result<u32, String> {
        Err("power_assertion_unsupported".into())
    }

    fn release(&mut self, _assertion_id: u32) -> Result<(), String> {
        Ok(())
    }
}

#[cfg(target_os = "macos")]
pub fn install(app: tauri::AppHandle) {
    use block2::RcBlock;
    use objc2_app_kit::{
        NSWorkspace, NSWorkspaceDidWakeNotification, NSWorkspaceWillSleepNotification,
    };
    use objc2_foundation::NSNotification;
    use std::ptr::NonNull;
    use tauri::Manager;

    let center = NSWorkspace::sharedWorkspace().notificationCenter();
    let sleep_app = app.clone();
    let sleep: RcBlock<dyn Fn(NonNull<NSNotification>)> = RcBlock::new(move |_| {
        if let Some(runtime) = sleep_app.try_state::<crate::AppRuntime>() {
            runtime
                .diagnostics
                .record("native", "system_will_sleep", None, Some("non_listening"));
            crate::release_power_assertion(&runtime, "system_sleep");
            crate::stop_sidecar(&runtime, "system_will_sleep");
        }
    });
    let wake: RcBlock<dyn Fn(NonNull<NSNotification>)> = RcBlock::new(move |_| {
        if let Some(runtime) = app.try_state::<crate::AppRuntime>() {
            runtime
                .diagnostics
                .record("native", "system_did_wake", None, Some("non_listening"));
        }
    });
    unsafe {
        let sleep_observer = center.addObserverForName_object_queue_usingBlock(
            Some(NSWorkspaceWillSleepNotification),
            None,
            None,
            &sleep,
        );
        let wake_observer = center.addObserverForName_object_queue_usingBlock(
            Some(NSWorkspaceDidWakeNotification),
            None,
            None,
            &wake,
        );
        std::mem::forget(sleep_observer);
        std::mem::forget(wake_observer);
    }
}

#[cfg(not(target_os = "macos"))]
pub fn install(_app: tauri::AppHandle) {}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;
    use std::sync::{Arc, Mutex};

    #[derive(Default)]
    struct BackendState {
        acquire_calls: usize,
        released: Vec<u32>,
        fail_acquire: bool,
    }

    struct FakeBackend(Arc<Mutex<BackendState>>);

    impl PowerAssertionBackend for FakeBackend {
        fn acquire(&mut self) -> Result<u32, String> {
            let mut state = self.0.lock().unwrap();
            state.acquire_calls += 1;
            if state.fail_acquire {
                Err("test_failure".into())
            } else {
                Ok(41)
            }
        }

        fn release(&mut self, assertion_id: u32) -> Result<(), String> {
            self.0.lock().unwrap().released.push(assertion_id);
            Ok(())
        }
    }

    fn fixture(state: Arc<Mutex<BackendState>>) -> (PowerPolicy, Diagnostics) {
        (
            PowerPolicy::with_backend(false, Box::new(FakeBackend(state))),
            Diagnostics::new(Path::new("/tmp/hey-jarvis-f105-power-tests")),
        )
    }

    #[test]
    fn assertion_requires_both_opt_in_and_real_wake_listening() {
        let state = Arc::new(Mutex::new(BackendState::default()));
        let (mut policy, diagnostics) = fixture(Arc::clone(&state));

        policy.update_availability("wake_listening", &diagnostics);
        policy.set_enabled(true, "ready", &diagnostics);
        assert_eq!(state.lock().unwrap().acquire_calls, 0);
        assert_eq!(
            policy.snapshot(),
            PowerSnapshot {
                enabled: true,
                active: false
            }
        );

        policy.update_availability("wake_listening", &diagnostics);
        policy.update_availability("wake_listening", &diagnostics);
        assert_eq!(state.lock().unwrap().acquire_calls, 1);
        assert!(policy.snapshot().active);
    }

    #[test]
    fn active_conversation_keeps_an_existing_assertion() {
        let state = Arc::new(Mutex::new(BackendState::default()));
        let (mut policy, diagnostics) = fixture(Arc::clone(&state));
        policy.set_enabled(true, "wake_listening", &diagnostics);
        policy.update_availability("busy", &diagnostics);
        assert!(policy.snapshot().active);
        assert!(state.lock().unwrap().released.is_empty());

        policy.update_availability("wake_listening", &diagnostics);
        assert_eq!(state.lock().unwrap().acquire_calls, 1);
    }

    #[test]
    fn busy_cannot_acquire_before_real_wake_listening() {
        let state = Arc::new(Mutex::new(BackendState::default()));
        let (mut policy, diagnostics) = fixture(Arc::clone(&state));
        policy.set_enabled(true, "busy", &diagnostics);
        assert_eq!(state.lock().unwrap().acquire_calls, 0);
        assert!(!policy.snapshot().active);
    }

    #[test]
    fn stop_settings_and_disable_release_idempotently() {
        for availability in ["ready", "resume_required"] {
            let state = Arc::new(Mutex::new(BackendState::default()));
            let (mut policy, diagnostics) = fixture(Arc::clone(&state));
            policy.set_enabled(true, "wake_listening", &diagnostics);
            policy.update_availability(availability, &diagnostics);
            policy.release("settings_opened", &diagnostics);
            policy.set_enabled(false, availability, &diagnostics);
            assert_eq!(state.lock().unwrap().released, vec![41]);
            assert!(!policy.snapshot().active);
        }
    }

    #[test]
    fn acquisition_failure_stays_inactive_without_retry_loop() {
        let state = Arc::new(Mutex::new(BackendState {
            fail_acquire: true,
            ..BackendState::default()
        }));
        let (mut policy, diagnostics) = fixture(Arc::clone(&state));
        policy.set_enabled(true, "wake_listening", &diagnostics);
        policy.update_availability("wake_listening", &diagnostics);
        assert_eq!(state.lock().unwrap().acquire_calls, 1);
        assert!(!policy.snapshot().active);
    }
}
