use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

const ONBOARDING_VERSION: u8 = 1;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct OnboardingRecord {
    pub version: u8,
    pub completed: bool,
    pub microphone_permission: String,
}

impl Default for OnboardingRecord {
    fn default() -> Self {
        Self {
            version: ONBOARDING_VERSION,
            completed: false,
            microphone_permission: "not_checked".into(),
        }
    }
}

pub fn path(app_support_dir: &Path) -> PathBuf {
    app_support_dir.join("onboarding-v1.json")
}

pub fn load(path: &Path) -> Result<OnboardingRecord, String> {
    if !path.exists() {
        return Ok(OnboardingRecord::default());
    }
    let contents = std::fs::read(path).map_err(|_| "onboarding_state_unavailable".to_string())?;
    let record: OnboardingRecord =
        serde_json::from_slice(&contents).map_err(|_| "onboarding_state_corrupt".to_string())?;
    if record.version != ONBOARDING_VERSION
        || !matches!(
            record.microphone_permission.as_str(),
            "not_checked" | "granted" | "denied"
        )
    {
        return Err("onboarding_state_corrupt".into());
    }
    Ok(record)
}

pub fn save(path: &Path, record: &OnboardingRecord) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "onboarding_state_unavailable".to_string())?;
    std::fs::create_dir_all(parent).map_err(|_| "onboarding_state_unavailable".to_string())?;
    let temporary = path.with_extension("json.tmp");
    let encoded = serde_json::to_vec(record).map_err(|_| "onboarding_state_corrupt".to_string())?;
    std::fs::write(&temporary, encoded)
        .and_then(|_| std::fs::rename(&temporary, path))
        .map_err(|_| "onboarding_state_unavailable".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("hey-jarvis-f089-{name}-{}", std::process::id()))
    }

    #[test]
    fn missing_state_is_first_run_and_completed_state_round_trips_without_secrets() {
        let directory = fixture("round-trip");
        let state_path = path(&directory);
        let _ = std::fs::remove_dir_all(&directory);
        assert_eq!(load(&state_path).unwrap(), OnboardingRecord::default());
        let record = OnboardingRecord {
            completed: true,
            microphone_permission: "granted".into(),
            ..OnboardingRecord::default()
        };
        save(&state_path, &record).unwrap();
        assert_eq!(load(&state_path).unwrap(), record);
        let contents = std::fs::read_to_string(&state_path).unwrap();
        assert!(!contents.contains("api_key"));
        let _ = std::fs::remove_dir_all(&directory);
    }

    #[test]
    fn corrupt_or_unknown_state_fails_closed() {
        let directory = fixture("corrupt");
        let state_path = path(&directory);
        let _ = std::fs::remove_dir_all(&directory);
        std::fs::create_dir_all(&directory).unwrap();
        std::fs::write(&state_path, b"{}").unwrap();
        assert_eq!(load(&state_path).unwrap_err(), "onboarding_state_corrupt");
        let _ = std::fs::remove_dir_all(&directory);
    }
}
