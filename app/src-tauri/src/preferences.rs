use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::Command;

const PREFERENCES_VERSION: u8 = 4;
pub const ENGLISH: &str = "en";
pub const SIMPLIFIED_CHINESE: &str = "zh-CN";
pub const NIGHT_THEME: &str = "night";
pub const DAY_THEME: &str = "day";

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Preferences {
    pub version: u8,
    pub smart_speaker_mode: bool,
    pub app_language: String,
    pub app_theme: String,
    pub wake_diagnostics_enabled: bool,
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            version: PREFERENCES_VERSION,
            smart_speaker_mode: false,
            app_language: ENGLISH.into(),
            app_theme: NIGHT_THEME.into(),
            wake_diagnostics_enabled: false,
        }
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct PreferencesV1 {
    version: u8,
    smart_speaker_mode: bool,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct PreferencesV2 {
    version: u8,
    smart_speaker_mode: bool,
    app_language: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct PreferencesV3 {
    version: u8,
    smart_speaker_mode: bool,
    app_language: String,
    app_theme: String,
}

pub fn normalize_language(value: &str) -> Result<&'static str, String> {
    match value {
        ENGLISH => Ok(ENGLISH),
        SIMPLIFIED_CHINESE => Ok(SIMPLIFIED_CHINESE),
        _ => Err("unsupported_app_language".into()),
    }
}

pub fn normalize_theme(value: &str) -> Result<&'static str, String> {
    match value {
        NIGHT_THEME => Ok(NIGHT_THEME),
        DAY_THEME => Ok(DAY_THEME),
        _ => Err("unsupported_app_theme".into()),
    }
}

pub fn language_from_macos_output(output: &str) -> &'static str {
    let first = output
        .lines()
        .map(str::trim)
        .find(|line| line.starts_with('"'))
        .unwrap_or("")
        .trim_matches(|character| matches!(character, '"' | ','));
    let normalized = first.to_ascii_lowercase();
    if normalized == "zh" || normalized.starts_with("zh-") || normalized.starts_with("zh_") {
        SIMPLIFIED_CHINESE
    } else {
        ENGLISH
    }
}

pub fn preferred_macos_language() -> &'static str {
    Command::new("/usr/bin/defaults")
        .args(["read", "-g", "AppleLanguages"])
        .output()
        .ok()
        .filter(|output| output.status.success())
        .and_then(|output| String::from_utf8(output.stdout).ok())
        .map(|output| language_from_macos_output(&output))
        .unwrap_or(ENGLISH)
}

pub fn path(app_support_dir: &Path) -> PathBuf {
    // Keep the stable filename while versioning the schema inside the record.
    app_support_dir.join("preferences-v1.json")
}

pub fn load(path: &Path) -> Result<Preferences, String> {
    if !path.exists() {
        return Ok(Preferences {
            app_language: preferred_macos_language().into(),
            ..Preferences::default()
        });
    }
    let contents = std::fs::read(path).map_err(|_| "preferences_unavailable".to_string())?;
    let value: serde_json::Value =
        serde_json::from_slice(&contents).map_err(|_| "preferences_corrupt".to_string())?;
    if value.get("version").and_then(serde_json::Value::as_u64) == Some(1) {
        let legacy: PreferencesV1 =
            serde_json::from_value(value).map_err(|_| "preferences_corrupt".to_string())?;
        if legacy.version != 1 {
            return Err("preferences_corrupt".into());
        }
        let migrated = Preferences {
            smart_speaker_mode: legacy.smart_speaker_mode,
            app_language: preferred_macos_language().into(),
            ..Preferences::default()
        };
        save(path, &migrated)?;
        return Ok(migrated);
    }
    if value.get("version").and_then(serde_json::Value::as_u64) == Some(2) {
        let legacy: PreferencesV2 =
            serde_json::from_value(value).map_err(|_| "preferences_corrupt".to_string())?;
        if legacy.version != 2 || normalize_language(&legacy.app_language).is_err() {
            return Err("preferences_corrupt".into());
        }
        let migrated = Preferences {
            smart_speaker_mode: legacy.smart_speaker_mode,
            app_language: legacy.app_language,
            ..Preferences::default()
        };
        save(path, &migrated)?;
        return Ok(migrated);
    }
    if value.get("version").and_then(serde_json::Value::as_u64) == Some(3) {
        let legacy: PreferencesV3 =
            serde_json::from_value(value).map_err(|_| "preferences_corrupt".to_string())?;
        if legacy.version != 3
            || normalize_language(&legacy.app_language).is_err()
            || normalize_theme(&legacy.app_theme).is_err()
        {
            return Err("preferences_corrupt".into());
        }
        let migrated = Preferences {
            smart_speaker_mode: legacy.smart_speaker_mode,
            app_language: legacy.app_language,
            app_theme: legacy.app_theme,
            ..Preferences::default()
        };
        save(path, &migrated)?;
        return Ok(migrated);
    }
    let preferences: Preferences =
        serde_json::from_value(value).map_err(|_| "preferences_corrupt".to_string())?;
    if preferences.version != PREFERENCES_VERSION
        || normalize_language(&preferences.app_language).is_err()
        || normalize_theme(&preferences.app_theme).is_err()
    {
        return Err("preferences_corrupt".into());
    }
    Ok(preferences)
}

pub fn save(path: &Path, preferences: &Preferences) -> Result<(), String> {
    normalize_language(&preferences.app_language).map_err(|_| "preferences_corrupt")?;
    normalize_theme(&preferences.app_theme).map_err(|_| "preferences_corrupt")?;
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
        std::env::temp_dir().join(format!("hey-jarvis-f118-{name}-{}", std::process::id()))
    }

    #[test]
    fn defaults_to_a_supported_language_and_round_trips_without_secrets() {
        let directory = fixture("round-trip");
        let state_path = path(&directory);
        let _ = std::fs::remove_dir_all(&directory);
        let initial = load(&state_path).unwrap();
        assert!(matches!(
            initial.app_language.as_str(),
            ENGLISH | SIMPLIFIED_CHINESE
        ));
        assert!(!initial.smart_speaker_mode);
        assert!(!initial.wake_diagnostics_enabled);

        let preferences = Preferences {
            smart_speaker_mode: true,
            app_language: SIMPLIFIED_CHINESE.into(),
            app_theme: DAY_THEME.into(),
            wake_diagnostics_enabled: true,
            ..Preferences::default()
        };
        save(&state_path, &preferences).unwrap();
        assert_eq!(load(&state_path).unwrap(), preferences);
        let contents = std::fs::read_to_string(&state_path).unwrap();
        assert!(!contents.contains("api_key"));
        assert!(contents.contains("zh-CN"));
        let _ = std::fs::remove_dir_all(&directory);
    }

    #[test]
    fn macos_language_mapping_is_bounded_to_two_supported_locales() {
        assert_eq!(
            language_from_macos_output("(\n    \"zh-Hans-SG\"\n)"),
            SIMPLIFIED_CHINESE
        );
        assert_eq!(
            language_from_macos_output("(\n    \"zh_TW\"\n)"),
            SIMPLIFIED_CHINESE
        );
        assert_eq!(language_from_macos_output("(\n    \"en-US\"\n)"), ENGLISH);
        assert_eq!(language_from_macos_output("garbage"), ENGLISH);
        assert!(normalize_language("fr").is_err());
    }

    #[test]
    fn version_one_migrates_without_losing_smart_speaker_mode() {
        let directory = fixture("migration");
        let state_path = path(&directory);
        let _ = std::fs::remove_dir_all(&directory);
        std::fs::create_dir_all(&directory).unwrap();
        std::fs::write(&state_path, br#"{"version":1,"smart_speaker_mode":true}"#).unwrap();
        let migrated = load(&state_path).unwrap();
        assert_eq!(migrated.version, 4);
        assert!(migrated.smart_speaker_mode);
        assert!(matches!(
            migrated.app_language.as_str(),
            ENGLISH | SIMPLIFIED_CHINESE
        ));
        let persisted = std::fs::read_to_string(&state_path).unwrap();
        assert!(persisted.contains("\"version\":4"));
        assert!(persisted.contains("\"wake_diagnostics_enabled\":false"));
        let _ = std::fs::remove_dir_all(&directory);
    }

    #[test]
    fn version_three_migrates_theme_and_defaults_wake_diagnostics_off() {
        let directory = fixture("v3-migration");
        let state_path = path(&directory);
        let _ = std::fs::remove_dir_all(&directory);
        std::fs::create_dir_all(&directory).unwrap();
        std::fs::write(&state_path, b"{\"version\":3,\"smart_speaker_mode\":true,\"app_language\":\"zh-CN\",\"app_theme\":\"day\"}").unwrap();
        let migrated = load(&state_path).unwrap();
        assert_eq!(migrated.version, 4);
        assert!(migrated.smart_speaker_mode);
        assert_eq!(migrated.app_language, SIMPLIFIED_CHINESE);
        assert_eq!(migrated.app_theme, DAY_THEME);
        assert!(!migrated.wake_diagnostics_enabled);
        let _ = std::fs::remove_dir_all(&directory);
    }

    #[test]
    fn corrupt_unknown_or_unsupported_preferences_fail_closed() {
        let directory = fixture("corrupt");
        let state_path = path(&directory);
        let _ = std::fs::remove_dir_all(&directory);
        std::fs::create_dir_all(&directory).unwrap();
        std::fs::write(&state_path, b"{\"version\":4,\"smart_speaker_mode\":true,\"app_language\":\"en\",\"app_theme\":\"night\",\"wake_diagnostics_enabled\":false,\"unknown\":true}").unwrap();
        assert_eq!(load(&state_path).unwrap_err(), "preferences_corrupt");
        std::fs::write(&state_path, b"{\"version\":4,\"smart_speaker_mode\":false,\"app_language\":\"fr\",\"app_theme\":\"night\",\"wake_diagnostics_enabled\":false}").unwrap();
        assert_eq!(load(&state_path).unwrap_err(), "preferences_corrupt");
        std::fs::write(&state_path, b"{\"version\":4,\"smart_speaker_mode\":false,\"app_language\":\"en\",\"app_theme\":\"blue\",\"wake_diagnostics_enabled\":false}").unwrap();
        assert_eq!(load(&state_path).unwrap_err(), "preferences_corrupt");
        std::fs::write(&state_path, b"{\"version\":4,\"smart_speaker_mode\":false,\"app_language\":\"en\",\"app_theme\":\"night\",\"wake_diagnostics_enabled\":\"yes\"}").unwrap();
        assert_eq!(load(&state_path).unwrap_err(), "preferences_corrupt");
        let _ = std::fs::remove_dir_all(&directory);
    }
}
