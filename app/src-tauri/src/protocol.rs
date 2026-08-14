use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const PROTOCOL_VERSION: u16 = 2;
pub const MAX_MESSAGE_BYTES: usize = 32 * 1024;
pub const MAX_SESSION_ID_LENGTH: usize = 64;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Envelope {
    pub protocol_version: u16,
    pub sequence: u64,
    pub session_id: String,
    pub payload: Payload,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Payload {
    Startup {
        app_version: String,
        app_support_dir: String,
        resource_dir: String,
    },
    StartupTiming {
        stage: String,
        elapsed_ms: u64,
    },
    Ready {
        sidecar_version: String,
        capabilities: Vec<String>,
        control_url: Option<String>,
    },
    Settings {
        revision: u64,
    },
    Session {
        action: String,
        conversation_id: Option<String>,
    },
    Lifecycle {
        event: String,
        detail: Option<String>,
    },
    Error {
        code: String,
        recoverable: bool,
    },
    Shutdown {
        reason: String,
    },
}

pub fn encode(envelope: &Envelope) -> Result<String, String> {
    validate(envelope, None, 0)?;
    let encoded = serde_json::to_string(envelope)
        .map_err(|error| format!("protocol encode failed: {error}"))?;
    if encoded.len() > MAX_MESSAGE_BYTES {
        return Err("protocol message exceeds size limit".into());
    }
    Ok(encoded)
}

pub fn decode(
    line: &str,
    expected_session: Option<&str>,
    last_sequence: u64,
) -> Result<Envelope, String> {
    if line.is_empty() || line.len() > MAX_MESSAGE_BYTES || line.contains('\0') {
        return Err("protocol message size or encoding is invalid".into());
    }
    let value: Value =
        serde_json::from_str(line).map_err(|_| "protocol message is not valid JSON".to_string())?;
    if contains_secret(&value, None) {
        return Err("secret-bearing protocol message rejected".into());
    }
    validate_exact_fields(&value)?;
    let envelope: Envelope = serde_json::from_value(value)
        .map_err(|error| format!("protocol envelope is invalid: {error}"))?;
    validate(&envelope, expected_session, last_sequence)?;
    Ok(envelope)
}

fn validate_exact_fields(value: &Value) -> Result<(), String> {
    let envelope = value
        .as_object()
        .ok_or_else(|| "protocol envelope must be an object".to_string())?;
    let mut envelope_fields = envelope.keys().map(String::as_str).collect::<Vec<_>>();
    envelope_fields.sort_unstable();
    if envelope_fields != ["payload", "protocol_version", "sequence", "session_id"] {
        return Err("protocol envelope fields are invalid".into());
    }

    let payload = envelope
        .get("payload")
        .and_then(Value::as_object)
        .ok_or_else(|| "protocol payload must be an object".to_string())?;
    let kind = payload
        .get("kind")
        .and_then(Value::as_str)
        .ok_or_else(|| "protocol payload kind is invalid".to_string())?;
    let expected: &[&str] = match kind {
        "startup" => &["app_support_dir", "app_version", "kind", "resource_dir"],
        "startup_timing" => &["elapsed_ms", "kind", "stage"],
        "ready" => &["capabilities", "control_url", "kind", "sidecar_version"],
        "settings" => &["kind", "revision"],
        "session" => &["action", "conversation_id", "kind"],
        "lifecycle" => &["detail", "event", "kind"],
        "error" => &["code", "kind", "recoverable"],
        "shutdown" => &["kind", "reason"],
        _ => return Err("protocol payload kind is unsupported".into()),
    };
    let mut actual = payload.keys().map(String::as_str).collect::<Vec<_>>();
    actual.sort_unstable();
    if actual != expected {
        return Err("protocol payload fields are invalid".into());
    }
    Ok(())
}

fn validate(
    envelope: &Envelope,
    expected_session: Option<&str>,
    last_sequence: u64,
) -> Result<(), String> {
    if envelope.protocol_version != PROTOCOL_VERSION {
        return Err("unsupported protocol version".into());
    }
    if envelope.sequence == 0 || envelope.sequence <= last_sequence {
        return Err("protocol sequence is not strictly increasing".into());
    }
    let session = &envelope.session_id;
    if session.is_empty()
        || session.len() > MAX_SESSION_ID_LENGTH
        || !session
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || character == '-')
    {
        return Err("protocol session identity is invalid".into());
    }
    if let Some(expected) = expected_session {
        if session != expected {
            return Err("protocol session identity changed".into());
        }
    }
    if let Payload::StartupTiming { stage, elapsed_ms } = &envelope.payload {
        const STAGES: &[&str] = &[
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
        if !STAGES.contains(&stage.as_str()) || *elapsed_ms > 300_000 {
            return Err("startup timing payload is invalid".into());
        }
    }
    let value = serde_json::to_value(envelope)
        .map_err(|error| format!("protocol validation failed: {error}"))?;
    if contains_secret(&value, None) {
        return Err("secret-bearing protocol message rejected".into());
    }
    Ok(())
}

fn contains_secret(value: &Value, key: Option<&str>) -> bool {
    const FORBIDDEN_KEYS: &[&str] = &[
        "api_key",
        "apikey",
        "authorization",
        "credential",
        "password",
        "secret",
        "token",
    ];

    if key
        .map(|candidate| FORBIDDEN_KEYS.contains(&candidate.to_ascii_lowercase().as_str()))
        .unwrap_or(false)
    {
        return true;
    }
    match value {
        Value::Object(map) => map
            .iter()
            .any(|(name, item)| contains_secret(item, Some(name))),
        Value::Array(items) => items.iter().any(|item| contains_secret(item, None)),
        Value::String(text) => {
            let lowered = text.to_ascii_lowercase();
            lowered.contains("bearer ")
                || lowered.contains("sk-")
                || lowered.contains("api_key")
                || lowered.contains("apikey")
        }
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn envelope(payload: Payload) -> Envelope {
        Envelope {
            protocol_version: PROTOCOL_VERSION,
            sequence: 1,
            session_id: "session-123".into(),
            payload,
        }
    }

    #[test]
    fn all_protocol_payload_kinds_round_trip() {
        let payloads = vec![
            Payload::Startup {
                app_version: "0.1.0".into(),
                app_support_dir: "/tmp/app".into(),
                resource_dir: "/tmp/resources".into(),
            },
            Payload::StartupTiming {
                stage: "imports_ready".into(),
                elapsed_ms: 42,
            },
            Payload::Ready {
                sidecar_version: "fake".into(),
                capabilities: vec!["health".into()],
                control_url: None,
            },
            Payload::Settings { revision: 1 },
            Payload::Session {
                action: "start".into(),
                conversation_id: Some("conversation-1".into()),
            },
            Payload::Lifecycle {
                event: "healthy".into(),
                detail: None,
            },
            Payload::Error {
                code: "fake_error".into(),
                recoverable: true,
            },
            Payload::Shutdown {
                reason: "test".into(),
            },
        ];
        for payload in payloads {
            let original = envelope(payload);
            let encoded = encode(&original).expect("encode");
            assert_eq!(decode(&encoded, Some("session-123"), 0).unwrap(), original);
        }
    }

    #[test]
    fn rejects_unknown_fields_versions_order_and_session_changes() {
        let encoded = encode(&envelope(Payload::Settings { revision: 1 })).unwrap();
        let with_extra = encoded.replacen(
            "\"protocol_version\":2",
            "\"protocol_version\":2,\"extra\":true",
            1,
        );
        let payload_extra =
            encoded.replacen("\"revision\":1", "\"revision\":1,\"unexpected\":true", 1);
        assert!(decode(&with_extra, None, 0).is_err());
        assert!(decode(&payload_extra, None, 0).is_err());
        assert!(decode(
            &encoded.replace("\"protocol_version\":2", "\"protocol_version\":1"),
            None,
            0
        )
        .is_err());
        assert!(decode(&encoded, None, 1).is_err());
        assert!(decode(&encoded, Some("different-session"), 0).is_err());
        assert!(decode(&encoded.replace("session-123", "../bad"), None, 0).is_err());
    }

    #[test]
    fn rejects_secret_bearing_and_oversized_messages() {
        let secret = envelope(Payload::Session {
            action: "start".into(),
            conversation_id: Some("sk-do-not-cross".into()),
        });
        assert!(encode(&secret).is_err());
        assert!(decode(&" ".repeat(MAX_MESSAGE_BYTES + 1), None, 0).is_err());
    }
}
