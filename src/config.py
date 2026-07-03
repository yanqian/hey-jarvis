"""Configuration loading and diagnostics for Hey Jarvis."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


DEFAULT_WAKE_PHRASE = "hey jarvis"
DEFAULT_WAKE_THRESHOLD = 0.8
DEFAULT_SILENCE_SECONDS = 1.5
DEFAULT_MAX_RECORD_SECONDS = 20.0
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_TRANSCRIBE_MODEL = "gpt-4o-mini-transcribe"
DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "alloy"

SUPPORTED_PYTHON_VERSIONS = {(3, 11), (3, 12)}
PLACEHOLDER_API_KEYS = {"", "your_api_key_here", "replace_me", "changeme"}

DEPENDENCY_MODULES: Mapping[str, str] = {
    "sounddevice": "sounddevice",
    "numpy": "numpy",
    "scipy": "scipy",
    "openai": "openai",
    "openwakeword": "openwakeword",
    "onnxruntime": "onnxruntime",
    "python-dotenv": "dotenv",
}


class ConfigError(ValueError):
    """Raised when environment configuration is invalid."""

    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__("Invalid configuration: " + "; ".join(self.errors))


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    wake_phrase: str
    wake_threshold: float
    silence_seconds: float
    max_record_seconds: float
    sample_rate: int
    transcribe_model: str
    chat_model: str
    tts_model: str
    tts_voice: str


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    status: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.status == "error"


@dataclass(frozen=True)
class DiagnosticReport:
    checks: tuple[DiagnosticCheck, ...]

    @property
    def has_errors(self) -> bool:
        return any(check.is_error for check in self.checks)


def load_settings(
    env: Mapping[str, str] | None = None,
    env_file: str | Path | None = ".env",
    *,
    require_openai_api_key: bool = False,
) -> Settings:
    """Load settings from .env and environment mappings.

    Values from the process environment, or an explicit ``env`` mapping in tests,
    override values loaded from the optional .env file.
    """

    raw_env: dict[str, str] = {}
    if env_file is not None:
        raw_env.update(_read_env_file(Path(env_file)))
    raw_env.update(os.environ if env is None else env)

    errors: list[str] = []

    openai_api_key = _optional_secret(raw_env.get("OPENAI_API_KEY"))
    if require_openai_api_key and openai_api_key is None:
        errors.append("OPENAI_API_KEY is required; set it in .env or the environment")

    wake_phrase = _text_value(raw_env, "WAKE_PHRASE", DEFAULT_WAKE_PHRASE, errors)
    wake_threshold = _float_value(
        raw_env,
        "WAKE_THRESHOLD",
        DEFAULT_WAKE_THRESHOLD,
        errors,
        minimum=0.0,
        maximum=1.0,
    )
    silence_seconds = _float_value(
        raw_env,
        "SILENCE_SECONDS",
        DEFAULT_SILENCE_SECONDS,
        errors,
        minimum=0.1,
    )
    max_record_seconds = _float_value(
        raw_env,
        "MAX_RECORD_SECONDS",
        DEFAULT_MAX_RECORD_SECONDS,
        errors,
        minimum=0.1,
    )
    sample_rate = _int_value(raw_env, "SAMPLE_RATE", DEFAULT_SAMPLE_RATE, errors, minimum=1)
    transcribe_model = _text_value(raw_env, "TRANSCRIBE_MODEL", DEFAULT_TRANSCRIBE_MODEL, errors)
    chat_model = _text_value(raw_env, "CHAT_MODEL", DEFAULT_CHAT_MODEL, errors)
    tts_model = _text_value(raw_env, "TTS_MODEL", DEFAULT_TTS_MODEL, errors)
    tts_voice = _text_value(raw_env, "TTS_VOICE", DEFAULT_TTS_VOICE, errors)

    if max_record_seconds <= silence_seconds:
        errors.append("MAX_RECORD_SECONDS must be greater than SILENCE_SECONDS")

    if errors:
        raise ConfigError(errors)

    return Settings(
        openai_api_key=openai_api_key,
        wake_phrase=wake_phrase,
        wake_threshold=wake_threshold,
        silence_seconds=silence_seconds,
        max_record_seconds=max_record_seconds,
        sample_rate=sample_rate,
        transcribe_model=transcribe_model,
        chat_model=chat_model,
        tts_model=tts_model,
        tts_voice=tts_voice,
    )


def collect_diagnostics(
    env: Mapping[str, str] | None = None,
    env_file: str | Path | None = ".env",
    *,
    python_version: tuple[int, int] | None = None,
    afplay_path: str | None = None,
    dependency_modules: Mapping[str, str] | None = None,
    wake_word_model_paths: Mapping[str, str | Path] | None = None,
) -> DiagnosticReport:
    """Collect runtime diagnostics without requiring optional imports."""

    checks: list[DiagnosticCheck] = []
    version = python_version or sys.version_info[:2]
    if version in SUPPORTED_PYTHON_VERSIONS:
        checks.append(DiagnosticCheck("python", "ok", f"Python {version[0]}.{version[1]} is supported"))
    else:
        checks.append(
            DiagnosticCheck(
                "python",
                "error",
                f"Python {version[0]}.{version[1]} is unsupported; use Python 3.11 or 3.12",
            )
        )

    resolved_afplay = afplay_path if afplay_path is not None else shutil.which("afplay")
    if resolved_afplay:
        checks.append(DiagnosticCheck("afplay", "ok", f"afplay found at {resolved_afplay}"))
    else:
        checks.append(
            DiagnosticCheck(
                "afplay",
                "error",
                "afplay was not found on PATH; run on macOS or install an equivalent playback path",
            )
        )

    try:
        settings = load_settings(env=env, env_file=env_file)
    except ConfigError as exc:
        checks.append(DiagnosticCheck("configuration", "error", "; ".join(exc.errors)))
        settings = None
    else:
        checks.append(DiagnosticCheck("configuration", "ok", "Environment values loaded"))

    if settings is None or settings.openai_api_key is None:
        checks.append(
            DiagnosticCheck(
                "OPENAI_API_KEY",
                "error",
                "OPENAI_API_KEY is missing; add it to .env or export it before running the assistant",
            )
        )
    else:
        checks.append(DiagnosticCheck("OPENAI_API_KEY", "ok", "OpenAI API key is configured"))

    modules_to_check = DEPENDENCY_MODULES if dependency_modules is None else dependency_modules
    for package_name, module_name in modules_to_check.items():
        if importlib.util.find_spec(module_name) is None:
            checks.append(
                DiagnosticCheck(
                    f"dependency:{package_name}",
                    "error",
                    f"{package_name} is not importable; install requirements.txt in the active environment",
                )
            )
        else:
            checks.append(DiagnosticCheck(f"dependency:{package_name}", "ok", f"{package_name} is importable"))

    checks.extend(_wake_word_model_checks(wake_word_model_paths, modules_to_check))

    checks.append(
        DiagnosticCheck(
            "microphone_permission",
            "info",
            "Grant macOS microphone permission to the terminal or agent surface that launches Hey Jarvis",
        )
    )

    return DiagnosticReport(tuple(checks))


def _wake_word_model_checks(
    wake_word_model_paths: Mapping[str, str | Path] | None,
    dependency_modules: Mapping[str, str],
) -> list[DiagnosticCheck]:
    if wake_word_model_paths is None and "openwakeword" in dependency_modules:
        if importlib.util.find_spec("openwakeword") is None:
            return []
        try:
            from .wake_word import required_wake_word_model_paths

            wake_word_model_paths = required_wake_word_model_paths()
        except Exception as exc:
            return [
                DiagnosticCheck(
                    "wake_word_models",
                    "error",
                    f"Unable to inspect openWakeWord ONNX model files: {exc}",
                )
            ]

    if wake_word_model_paths is None:
        return []

    missing = {
        name: Path(path)
        for name, path in wake_word_model_paths.items()
        if not Path(path).is_file()
    }
    if missing:
        missing_names = ", ".join(sorted(missing))
        return [
            DiagnosticCheck(
                "wake_word_models",
                "error",
                "Missing openWakeWord ONNX model files for "
                f"{missing_names}; run python -m src.main --prepare-wake-word",
            )
        ]

    return [
        DiagnosticCheck(
            "wake_word_models",
            "ok",
            "Required openWakeWord ONNX model files are present",
        )
    ]


def format_diagnostics(report: DiagnosticReport) -> str:
    labels = {"ok": "OK", "error": "ERROR", "info": "INFO", "warning": "WARN"}
    lines = ["Runtime diagnostics:"]
    for check in report.checks:
        label = labels.get(check.status, check.status.upper())
        lines.append(f"[{label}] {check.name}: {check.message}")
    return "\n".join(lines)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _strip_quotes(raw_value.strip())
    return values


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _optional_secret(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped.lower() in PLACEHOLDER_API_KEYS:
        return None
    return stripped


def _text_value(env: Mapping[str, str], name: str, default: str, errors: list[str]) -> str:
    value = env.get(name, default).strip()
    if not value:
        errors.append(f"{name} must not be empty")
        return default
    return value


def _float_value(
    env: Mapping[str, str],
    name: str,
    default: float,
    errors: list[str],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    raw_value = env.get(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        value = float(raw_value)
    except ValueError:
        errors.append(f"{name} must be a number")
        return default
    if minimum is not None and value < minimum:
        errors.append(f"{name} must be at least {minimum}")
    if maximum is not None and value > maximum:
        errors.append(f"{name} must be at most {maximum}")
    return value


def _int_value(
    env: Mapping[str, str],
    name: str,
    default: int,
    errors: list[str],
    *,
    minimum: int | None = None,
) -> int:
    raw_value = env.get(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        value = int(raw_value)
    except ValueError:
        errors.append(f"{name} must be an integer")
        return default
    if minimum is not None and value < minimum:
        errors.append(f"{name} must be at least {minimum}")
    return value
