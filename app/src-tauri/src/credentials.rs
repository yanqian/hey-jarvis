use serde::Serialize;
use std::process::Command;

pub const KEYCHAIN_SERVICE: &str = "com.heyjarvis.desktop";
pub const PRIVATE_BOOTSTRAP_MAX_BYTES: usize = 4096;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CredentialKind {
    OpenAi,
    Finnhub,
}

impl CredentialKind {
    pub fn parse(value: &str) -> Result<Self, String> {
        match value {
            "openai" => Ok(Self::OpenAi),
            "finnhub" => Ok(Self::Finnhub),
            _ => Err("unsupported_credential_kind".into()),
        }
    }

    fn account(self) -> &'static str {
        match self {
            Self::OpenAi => "openai-api-key",
            Self::Finnhub => "finnhub-api-key",
        }
    }

    fn prompt_script(self) -> &'static str {
        match self {
            Self::OpenAi => {
                r#"text returned of (display dialog "Enter your OpenAI API key. It will be stored in macOS Keychain and will not be shown in the app." default answer "" with hidden answer buttons {"Cancel", "Save"} default button "Save" cancel button "Cancel" with title "Hey Jarvis")"#
            }
            Self::Finnhub => {
                r#"text returned of (display dialog "Enter an optional Finnhub API key for stock quotes. It will be stored in macOS Keychain." default answer "" with hidden answer buttons {"Cancel", "Save"} default button "Save" cancel button "Cancel" with title "Hey Jarvis")"#
            }
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CredentialStoreError {
    pub code: &'static str,
}

pub trait CredentialStore: Send + Sync {
    fn get(&self, kind: CredentialKind) -> Result<Option<Vec<u8>>, CredentialStoreError>;
    fn set(&self, kind: CredentialKind, value: &[u8]) -> Result<(), CredentialStoreError>;
    fn delete(&self, kind: CredentialKind) -> Result<(), CredentialStoreError>;
}

pub struct MacKeychainStore;

impl CredentialStore for MacKeychainStore {
    fn get(&self, kind: CredentialKind) -> Result<Option<Vec<u8>>, CredentialStoreError> {
        match security_framework::passwords::get_generic_password(KEYCHAIN_SERVICE, kind.account())
        {
            Ok(value) => Ok(Some(value)),
            Err(error) if error.code() == -25300 => Ok(None),
            Err(error) => Err(classify_keychain_error(error.code())),
        }
    }

    fn set(&self, kind: CredentialKind, value: &[u8]) -> Result<(), CredentialStoreError> {
        security_framework::passwords::set_generic_password(KEYCHAIN_SERVICE, kind.account(), value)
            .map_err(|error| classify_keychain_error(error.code()))
    }

    fn delete(&self, kind: CredentialKind) -> Result<(), CredentialStoreError> {
        match security_framework::passwords::delete_generic_password(
            KEYCHAIN_SERVICE,
            kind.account(),
        ) {
            Ok(()) => Ok(()),
            Err(error) if error.code() == -25300 => Ok(()),
            Err(error) => Err(classify_keychain_error(error.code())),
        }
    }
}

fn classify_keychain_error(code: i32) -> CredentialStoreError {
    let code = match code {
        -25293 => "keychain_auth_failed",
        -25308 => "keychain_interaction_not_allowed",
        -128 => "keychain_user_cancelled",
        _ => "keychain_unavailable",
    };
    CredentialStoreError { code }
}

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct CredentialStatus {
    pub openai_configured: bool,
    pub finnhub_configured: bool,
}

pub fn status(store: &dyn CredentialStore) -> Result<CredentialStatus, String> {
    Ok(CredentialStatus {
        openai_configured: store
            .get(CredentialKind::OpenAi)
            .map_err(public_store_error)?
            .is_some(),
        finnhub_configured: store
            .get(CredentialKind::Finnhub)
            .map_err(public_store_error)?
            .is_some(),
    })
}

pub fn prompt_and_store(
    store: &dyn CredentialStore,
    kind: CredentialKind,
) -> Result<CredentialStatus, String> {
    let mut output = Command::new("/usr/bin/osascript")
        .arg("-e")
        .arg(kind.prompt_script())
        .output()
        .map_err(|_| "credential_prompt_unavailable".to_string())?;
    if !output.status.success() {
        output.stdout.fill(0);
        output.stderr.fill(0);
        return Err("credential_prompt_cancelled".into());
    }
    while matches!(output.stdout.last(), Some(b'\n' | b'\r')) {
        output.stdout.pop();
    }
    validate(kind, &output.stdout)?;
    let result = store.set(kind, &output.stdout).map_err(public_store_error);
    output.stdout.fill(0);
    output.stderr.fill(0);
    result?;
    status(store)
}

pub fn delete_and_report(
    store: &dyn CredentialStore,
    kind: CredentialKind,
) -> Result<CredentialStatus, String> {
    store.delete(kind).map_err(public_store_error)?;
    status(store)
}

fn validate(kind: CredentialKind, value: &[u8]) -> Result<(), String> {
    if value.is_empty()
        || value.len() > 512
        || std::str::from_utf8(value).is_err()
        || value
            .iter()
            .any(|byte| byte.is_ascii_whitespace() || byte.is_ascii_control())
    {
        return Err("credential_format_invalid".into());
    }
    if kind == CredentialKind::OpenAi && !value.starts_with(b"sk-") {
        return Err("credential_format_invalid".into());
    }
    Ok(())
}

fn public_store_error(error: CredentialStoreError) -> String {
    error.code.into()
}

pub struct RuntimeCredentials {
    openai: Vec<u8>,
    finnhub: Option<Vec<u8>>,
}

impl RuntimeCredentials {
    pub fn load(store: &dyn CredentialStore) -> Result<Self, String> {
        let openai = store
            .get(CredentialKind::OpenAi)
            .map_err(public_store_error)?
            .ok_or_else(|| "openai_credential_missing".to_string())?;
        validate(CredentialKind::OpenAi, &openai)?;
        let finnhub = store
            .get(CredentialKind::Finnhub)
            .map_err(public_store_error)?;
        if let Some(value) = finnhub.as_deref() {
            validate(CredentialKind::Finnhub, value)?;
        }
        Ok(Self { openai, finnhub })
    }

    pub fn private_bootstrap(&self) -> Result<Vec<u8>, String> {
        #[derive(Serialize)]
        struct Bootstrap<'a> {
            kind: &'static str,
            openai_api_key: &'a str,
            finnhub_api_key: Option<&'a str>,
        }

        let message = Bootstrap {
            kind: "private_credentials",
            openai_api_key: std::str::from_utf8(&self.openai)
                .map_err(|_| "credential_format_invalid".to_string())?,
            finnhub_api_key: self
                .finnhub
                .as_deref()
                .map(std::str::from_utf8)
                .transpose()
                .map_err(|_| "credential_format_invalid".to_string())?,
        };
        let mut encoded =
            serde_json::to_vec(&message).map_err(|_| "credential_bootstrap_failed".to_string())?;
        if encoded.len() > PRIVATE_BOOTSTRAP_MAX_BYTES {
            encoded.fill(0);
            return Err("credential_bootstrap_too_large".into());
        }
        encoded.push(b'\n');
        Ok(encoded)
    }
}

impl Drop for RuntimeCredentials {
    fn drop(&mut self) {
        self.openai.fill(0);
        if let Some(value) = self.finnhub.as_mut() {
            value.fill(0);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::sync::Mutex;

    #[derive(Default)]
    struct MemoryStore(Mutex<HashMap<&'static str, Vec<u8>>>);

    impl CredentialStore for MemoryStore {
        fn get(&self, kind: CredentialKind) -> Result<Option<Vec<u8>>, CredentialStoreError> {
            Ok(self.0.lock().unwrap().get(kind.account()).cloned())
        }

        fn set(&self, kind: CredentialKind, value: &[u8]) -> Result<(), CredentialStoreError> {
            self.0
                .lock()
                .unwrap()
                .insert(kind.account(), value.to_vec());
            Ok(())
        }

        fn delete(&self, kind: CredentialKind) -> Result<(), CredentialStoreError> {
            self.0.lock().unwrap().remove(kind.account());
            Ok(())
        }
    }

    #[test]
    fn keychain_fixture_supports_add_replace_read_and_delete_without_public_values() {
        let store = MemoryStore::default();
        store
            .set(CredentialKind::OpenAi, b"sk-first-value")
            .unwrap();
        assert!(status(&store).unwrap().openai_configured);
        store
            .set(CredentialKind::OpenAi, b"sk-replaced-value")
            .unwrap();
        let credentials = RuntimeCredentials::load(&store).unwrap();
        let encoded = credentials.private_bootstrap().unwrap();
        assert!(encoded.starts_with(b"{\"kind\":\"private_credentials\""));
        assert!(!format!("{:?}", status(&store).unwrap()).contains("sk-"));
        drop(credentials);
        store.delete(CredentialKind::OpenAi).unwrap();
        assert!(!status(&store).unwrap().openai_configured);
    }

    #[test]
    fn validation_rejects_missing_malformed_whitespace_and_oversized_values() {
        for value in [b"".as_slice(), b"not-an-openai-key", b"sk-with space"] {
            assert_eq!(
                validate(CredentialKind::OpenAi, value).unwrap_err(),
                "credential_format_invalid"
            );
        }
        assert!(validate(CredentialKind::OpenAi, &vec![b'x'; 513]).is_err());
        assert!(validate(CredentialKind::Finnhub, b"optional-token").is_ok());
    }

    #[test]
    fn bootstrap_is_bounded_and_is_not_part_of_the_public_protocol() {
        let store = MemoryStore::default();
        store
            .set(CredentialKind::OpenAi, b"sk-private-value")
            .unwrap();
        let credentials = RuntimeCredentials::load(&store).unwrap();
        let encoded = credentials.private_bootstrap().unwrap();
        assert!(encoded.len() <= PRIVATE_BOOTSTRAP_MAX_BYTES + 1);
        assert!(crate::protocol::decode(
            std::str::from_utf8(&encoded[..encoded.len() - 1]).unwrap(),
            None,
            0
        )
        .is_err());
    }
}
