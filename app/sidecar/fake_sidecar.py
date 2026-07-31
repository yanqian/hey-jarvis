#!/usr/bin/env python3
"""Protocol-only fake sidecar for the F087 native shell."""

from __future__ import annotations

import json
import re
import sys
from typing import Any, TextIO


PROTOCOL_VERSION = 2
MAX_MESSAGE_BYTES = 32 * 1024
MAX_SESSION_ID_LENGTH = 64
SESSION_RE = re.compile(r"^[A-Za-z0-9-]+$")
FORBIDDEN_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}
PAYLOAD_FIELDS = {
    "startup": {"app_version", "app_support_dir", "resource_dir"},
    "settings": {"revision"},
    "session": {"action", "conversation_id"},
    "lifecycle": {"event", "detail"},
    "shutdown": {"reason"},
}


class ProtocolError(ValueError):
    pass


def _contains_secret(value: Any, key: str = "") -> bool:
    if key.lower() in FORBIDDEN_KEYS:
        return True
    if isinstance(value, dict):
        return any(_contains_secret(item, str(name)) for name, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return (
            "bearer " in lowered
            or "sk-" in lowered
            or "api_key" in lowered
            or "apikey" in lowered
        )
    return False


def parse_message(line: str, *, expected_session: str | None, last_sequence: int) -> dict[str, Any]:
    if not line or len(line.encode("utf-8")) > MAX_MESSAGE_BYTES or "\x00" in line:
        raise ProtocolError("message size or encoding is invalid")
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError("message is not valid JSON") from exc
    if not isinstance(message, dict) or set(message) != {
        "protocol_version",
        "sequence",
        "session_id",
        "payload",
    }:
        raise ProtocolError("envelope fields are invalid")
    if message["protocol_version"] != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    sequence = message["sequence"]
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence <= last_sequence:
        raise ProtocolError("message sequence is not strictly increasing")
    session_id = message["session_id"]
    if (
        not isinstance(session_id, str)
        or not session_id
        or len(session_id) > MAX_SESSION_ID_LENGTH
        or SESSION_RE.fullmatch(session_id) is None
    ):
        raise ProtocolError("session identity is invalid")
    if expected_session is not None and session_id != expected_session:
        raise ProtocolError("session identity changed")
    payload = message["payload"]
    if not isinstance(payload, dict) or not isinstance(payload.get("kind"), str):
        raise ProtocolError("payload is invalid")
    kind = payload["kind"]
    allowed = PAYLOAD_FIELDS.get(kind)
    if allowed is None or set(payload) != allowed | {"kind"}:
        raise ProtocolError("payload kind or fields are invalid")
    if _contains_secret(message):
        raise ProtocolError("secret-bearing payload rejected")
    return message


def _write(output: TextIO, session_id: str, sequence: int, payload: dict[str, Any]) -> None:
    message = {
        "protocol_version": PROTOCOL_VERSION,
        "sequence": sequence,
        "session_id": session_id,
        "payload": payload,
    }
    output.write(json.dumps(message, separators=(",", ":")) + "\n")
    output.flush()


def run(input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout) -> int:
    session_id: str | None = None
    inbound_sequence = 0
    outbound_sequence = 1

    for line in input_stream:
        try:
            message = parse_message(
                line.rstrip("\n"),
                expected_session=session_id,
                last_sequence=inbound_sequence,
            )
        except ProtocolError:
            return 2

        inbound_sequence = message["sequence"]
        if session_id is None:
            if message["payload"]["kind"] != "startup":
                return 2
            session_id = message["session_id"]
            _write(
                output_stream,
                session_id,
                outbound_sequence,
                {
                    "kind": "ready",
                    "sidecar_version": "0.1.0-fake",
                    "capabilities": ["health", "settings", "session", "shutdown"],
                    "control_url": None,
                },
            )
            outbound_sequence += 1
            continue

        payload = message["payload"]
        kind = payload["kind"]
        if kind == "lifecycle" and payload["event"] == "health_check":
            _write(
                output_stream,
                session_id,
                outbound_sequence,
                {"kind": "lifecycle", "event": "healthy", "detail": "fake sidecar"},
            )
            outbound_sequence += 1
        elif kind == "settings":
            _write(
                output_stream,
                session_id,
                outbound_sequence,
                {"kind": "lifecycle", "event": "settings_applied", "detail": None},
            )
            outbound_sequence += 1
        elif kind == "session":
            _write(
                output_stream,
                session_id,
                outbound_sequence,
                {"kind": "lifecycle", "event": "session_updated", "detail": payload["action"]},
            )
            outbound_sequence += 1
        elif kind == "shutdown":
            _write(
                output_stream,
                session_id,
                outbound_sequence,
                {"kind": "lifecycle", "event": "stopping", "detail": payload["reason"]},
            )
            return 0
        else:
            return 2

    # EOF is the parent-loss contract: exit instead of becoming an orphan.
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
