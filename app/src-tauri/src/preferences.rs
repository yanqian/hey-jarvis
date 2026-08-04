use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

const PREFERENCES_VERSION: u8 = 1;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Preferences {
    pub version: u8,
    pub smart_speaker_mode: bool,
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            version: PREFERENCES_VERSION,
            smart_speaker_mode: false,
        }
    }
}

pub fn path(app_support_dir: &Path) -> PathBuf {
    app_support_dir.join("preferences-v1.json")
}

pub fn load(path: &Path) -> Result<Preferences, String> {
    if !path.exists() {
        return Ok(Preferences::default());
    }
    let contents = std::fs::read(path).map_err(|_| "preferences_unavailable".to_string())?;
    let preferences: Preferences =
        serde_json::from_slice(&contents).map_err(|_| "preferences_corrupt".to_string())?;
    if preferences.version != PREFERENCES_VERSION {
        return Err("preferences_corrupt".into());
    }
    Ok(preferences)
}

pub fn save(path: &Path, preferences: &Preferences) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "preferences_unavailable".to_string())?;
    std::fs::create_dir_all(parent).map_err(|_| "preferences_unavailable".to_string())?;
    let temporary = path.with_extension("json.tmp");
    let encoded = serde_json::to_vec(preferences).map_err(|_| "preferences_corrupt".to_string())?;
    std::fs::write(&temporary, encoded)
        .and_then(|_| std::fs::rename(&temporary, path))
        .map_err(|_| "preferences_unavailable".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("hey-jarvis-f105-{name}-{}", std::process::id()))
    }

    #[test]
    fn defaults_off_and_round_trips_without_secrets() {
        let directory = fixture("round-trip");
        let state_path = path(&directory);
        let _ = std::fs::remove_dir_all(&directory);
        assert_eq!(load(&state_path).unwrap(), Preferences::default());

        let preferences = Preferences {
            smart_speaker_mode: true,
            ..Preferences::default()
        };
        save(&state_path, &preferences).unwrap();
        assert_eq!(load(&state_path).unwrap(), preferences);
        let contents = std::fs::read_to_string(&state_path).unwrap();
        assert!(!contents.contains("api_key"));
        let _ = std::fs::remove_dir_all(&directory);
    }

    #[test]
    fn corrupt_or_unknown_preferences_fail_closed() {
        let directory = fixture("corrupt");
        let state_path = path(&directory);
        let _ = std::fs::remove_dir_all(&directory);
        std::fs::create_dir_all(&directory).unwrap();
        std::fs::write(&state_path, b"{\"version\":2,\"smart_speaker_mode\":true}").unwrap();
        assert_eq!(load(&state_path).unwrap_err(), "preferences_corrupt");
        let _ = std::fs::remove_dir_all(&directory);
    }
}
