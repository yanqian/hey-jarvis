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
        // NSNotificationCenter owns these process-lifetime callbacks. Keeping
        // the opaque tokens alive avoids a callback-after-drop teardown race.
        std::mem::forget(sleep_observer);
        std::mem::forget(wake_observer);
    }
}

#[cfg(not(target_os = "macos"))]
pub fn install(_app: tauri::AppHandle) {}
