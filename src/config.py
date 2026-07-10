"""Configuration loading and diagnostics for Hey Jarvis."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .wake_word import (
    MACOS_ARM64_ONNX_ERROR,
    OPENWAKEWORD_BACKEND,
    OPENWAKEWORD_INFERENCE_FRAMEWORK,
    OPENWAKEWORD_MODEL_NAME,
    SUPPORTED_OPENWAKEWORD_INFERENCE_FRAMEWORKS,
    SUPPORTED_WAKE_BACKENDS,
    is_macos_arm64,
    normalize_inference_framework,
    normalize_wake_backend,
    normalize_wake_model,
)
from .tools.providers import (
    DEFAULT_BASE_CURRENCY as PROVIDER_DEFAULT_BASE_CURRENCY,
    DEFAULT_FX_PROVIDER as PROVIDER_DEFAULT_FX_PROVIDER,
    DEFAULT_LOCATION as PROVIDER_DEFAULT_LOCATION,
    DEFAULT_STOCK_PROVIDER as PROVIDER_DEFAULT_STOCK_PROVIDER,
    DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS as PROVIDER_DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS,
    DEFAULT_WEATHER_PROVIDER as PROVIDER_DEFAULT_WEATHER_PROVIDER,
    ProviderConfig,
)

DEFAULT_WAKE_BACKEND = OPENWAKEWORD_BACKEND
DEFAULT_WAKE_MODEL = OPENWAKEWORD_MODEL_NAME
DEFAULT_WAKE_INFERENCE_FRAMEWORK = OPENWAKEWORD_INFERENCE_FRAMEWORK
DEFAULT_WAKE_PHRASE = "hey jarvis"
DEFAULT_WAKE_THRESHOLD = 0.5
DEFAULT_SILENCE_SECONDS = 1.5
DEFAULT_MAX_RECORD_SECONDS = 20.0
DEFAULT_RECORDING_SILENCE_RMS = 750.0
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_TRANSCRIBE_MODEL = "gpt-4o-mini-transcribe"
DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "alloy"
DEFAULT_TTS_INSTRUCTIONS: str | None = None
DEFAULT_TTS_SPEED = 1.0
DEFAULT_ENABLE_TOOLS = True
DEFAULT_TOOL_ROUTER_DEBUG = False
DEFAULT_TOOL_ANSWER_NATURALIZATION = True
DEFAULT_WEATHER_PROVIDER = PROVIDER_DEFAULT_WEATHER_PROVIDER
DEFAULT_FX_PROVIDER = PROVIDER_DEFAULT_FX_PROVIDER
DEFAULT_STOCK_PROVIDER = PROVIDER_DEFAULT_STOCK_PROVIDER
DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS = PROVIDER_DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS
DEFAULT_LOCATION = PROVIDER_DEFAULT_LOCATION
DEFAULT_BASE_CURRENCY = PROVIDER_DEFAULT_BASE_CURRENCY
DEFAULT_WAKE_ACKNOWLEDGEMENT_ENABLED = True
DEFAULT_WAKE_ACKNOWLEDGEMENT_TEXT = "在呢"
DEFAULT_WAKE_ACKNOWLEDGEMENT_AUDIO_PATH = Path("var/ack.mp3")
DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS = 0.35
DEFAULT_WAKE_DEBUG = False
DEFAULT_POST_PLAYBACK_WAKE_COOLDOWN_SECONDS = 1.0
DEFAULT_POST_PLAYBACK_QUIET_SECONDS = 0.5
DEFAULT_POST_PLAYBACK_QUIET_RMS = 500.0
DEFAULT_POST_PLAYBACK_MAX_SUPPRESSION_SECONDS = 6.0
DEFAULT_WAKE_CONFIRMATION_FRAMES = 2
DEFAULT_ARMED_NO_SPEECH_TIMEOUT_SECONDS = 2.0
DEFAULT_ARMED_MIN_RMS = 750.0
DEFAULT_ARMED_VOICE_RMS = DEFAULT_ARMED_MIN_RMS
DEFAULT_ARMED_SNR_MULTIPLIER = 2.5
DEFAULT_ARMED_VOICE_WINDOW_SECONDS = 0.30
DEFAULT_ARMED_VOICE_REQUIRED_RATIO = 0.75
DEFAULT_ARMED_CLIP_REJECT_PEAK = 32000
DEFAULT_ARMED_PRE_ROLL_SECONDS = 0.50
DEFAULT_MIN_VALID_SPEECH_SECONDS = 0.50
DEFAULT_MIN_TRANSCRIPT_LENGTH = 2
DEFAULT_CANCEL_PHRASES = ("取消", "没事", "不用了", "算了", "stop", "cancel", "never mind")

SUPPORTED_PYTHON_VERSIONS = {(3, 11), (3, 12)}
PLACEHOLDER_API_KEYS = {"", "your_api_key_here", "replace_me", "changeme"}

DEPENDENCY_MODULES: Mapping[str, str] = {
    "sounddevice": "sounddevice",
    "numpy": "numpy",
    "scipy": "scipy",
    "openai": "openai",
    "openwakeword": "openwakeword",
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
    wake_backend: str
    wake_model: str
    wake_inference_framework: str
    wake_phrase: str
    wake_threshold: float
    silence_seconds: float
    max_record_seconds: float
    sample_rate: int
    transcribe_model: str
    chat_model: str
    tts_model: str
    tts_voice: str
    tts_instructions: str | None = DEFAULT_TTS_INSTRUCTIONS
    tts_speed: float = DEFAULT_TTS_SPEED
    enable_tools: bool = DEFAULT_ENABLE_TOOLS
    tool_router_debug: bool = DEFAULT_TOOL_ROUTER_DEBUG
    tool_answer_naturalization: bool = DEFAULT_TOOL_ANSWER_NATURALIZATION
    weather_provider: str = DEFAULT_WEATHER_PROVIDER
    fx_provider: str = DEFAULT_FX_PROVIDER
    stock_provider: str = DEFAULT_STOCK_PROVIDER
    tool_http_timeout_seconds: float = DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS
    default_location: str = DEFAULT_LOCATION
    default_base_currency: str = DEFAULT_BASE_CURRENCY
    finnhub_api_key: str | None = None
    wake_acknowledgement_enabled: bool = DEFAULT_WAKE_ACKNOWLEDGEMENT_ENABLED
    wake_acknowledgement_text: str = DEFAULT_WAKE_ACKNOWLEDGEMENT_TEXT
    wake_acknowledgement_audio_path: Path = DEFAULT_WAKE_ACKNOWLEDGEMENT_AUDIO_PATH
    wake_acknowledgement_drain_seconds: float = DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS
    wake_debug: bool = DEFAULT_WAKE_DEBUG
    post_playback_wake_cooldown_seconds: float = DEFAULT_POST_PLAYBACK_WAKE_COOLDOWN_SECONDS
    post_playback_quiet_seconds: float = DEFAULT_POST_PLAYBACK_QUIET_SECONDS
    post_playback_quiet_rms: float = DEFAULT_POST_PLAYBACK_QUIET_RMS
    post_playback_max_suppression_seconds: float = DEFAULT_POST_PLAYBACK_MAX_SUPPRESSION_SECONDS
    wake_confirmation_frames: int = DEFAULT_WAKE_CONFIRMATION_FRAMES
    armed_no_speech_timeout_seconds: float = DEFAULT_ARMED_NO_SPEECH_TIMEOUT_SECONDS
    armed_voice_rms: float = DEFAULT_ARMED_VOICE_RMS
    armed_min_rms: float = DEFAULT_ARMED_MIN_RMS
    armed_snr_multiplier: float = DEFAULT_ARMED_SNR_MULTIPLIER
    armed_voice_window_seconds: float = DEFAULT_ARMED_VOICE_WINDOW_SECONDS
    armed_voice_required_ratio: float = DEFAULT_ARMED_VOICE_REQUIRED_RATIO
    armed_clip_reject_peak: int = DEFAULT_ARMED_CLIP_REJECT_PEAK
    armed_pre_roll_seconds: float = DEFAULT_ARMED_PRE_ROLL_SECONDS
    min_valid_speech_seconds: float = DEFAULT_MIN_VALID_SPEECH_SECONDS
    min_transcript_length: int = DEFAULT_MIN_TRANSCRIPT_LENGTH
    cancel_phrases: tuple[str, ...] = DEFAULT_CANCEL_PHRASES
    recording_silence_rms: float = DEFAULT_RECORDING_SILENCE_RMS


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

    wake_backend = _choice_value(
        raw_env,
        "WAKE_BACKEND",
        DEFAULT_WAKE_BACKEND,
        SUPPORTED_WAKE_BACKENDS,
        errors,
        normalizer=normalize_wake_backend,
    )
    wake_model = _text_value(raw_env, "WAKE_MODEL", DEFAULT_WAKE_MODEL, errors, normalizer=normalize_wake_model)
    wake_inference_framework = _choice_value(
        raw_env,
        "WAKE_INFERENCE_FRAMEWORK",
        DEFAULT_WAKE_INFERENCE_FRAMEWORK,
        SUPPORTED_OPENWAKEWORD_INFERENCE_FRAMEWORKS,
        errors,
        normalizer=normalize_inference_framework,
    )
    if wake_inference_framework == "onnx" and is_macos_arm64():
        errors.append(MACOS_ARM64_ONNX_ERROR)

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
    recording_silence_rms = _float_value(
        raw_env,
        "RECORDING_SILENCE_RMS",
        DEFAULT_RECORDING_SILENCE_RMS,
        errors,
        minimum=0.0,
    )
    sample_rate = _int_value(raw_env, "SAMPLE_RATE", DEFAULT_SAMPLE_RATE, errors, minimum=1)
    transcribe_model = _text_value(raw_env, "TRANSCRIBE_MODEL", DEFAULT_TRANSCRIBE_MODEL, errors)
    chat_model = _text_value(raw_env, "CHAT_MODEL", DEFAULT_CHAT_MODEL, errors)
    tts_model = _text_value(raw_env, "TTS_MODEL", DEFAULT_TTS_MODEL, errors)
    tts_voice = _text_value(raw_env, "TTS_VOICE", DEFAULT_TTS_VOICE, errors)
    tts_instructions = _optional_text_value(raw_env, "TTS_INSTRUCTIONS")
    tts_speed = _float_value(
        raw_env,
        "TTS_SPEED",
        DEFAULT_TTS_SPEED,
        errors,
        minimum=0.25,
        maximum=4.0,
    )
    enable_tools = _bool_value(raw_env, "ENABLE_TOOLS", DEFAULT_ENABLE_TOOLS, errors)
    tool_router_debug = _bool_value(raw_env, "TOOL_ROUTER_DEBUG", DEFAULT_TOOL_ROUTER_DEBUG, errors)
    tool_answer_naturalization = _bool_value(
        raw_env,
        "TOOL_ANSWER_NATURALIZATION",
        DEFAULT_TOOL_ANSWER_NATURALIZATION,
        errors,
    )
    weather_provider = _text_value(raw_env, "WEATHER_PROVIDER", DEFAULT_WEATHER_PROVIDER, errors)
    fx_provider = _text_value(raw_env, "FX_PROVIDER", DEFAULT_FX_PROVIDER, errors)
    stock_provider = _text_value(raw_env, "STOCK_PROVIDER", DEFAULT_STOCK_PROVIDER, errors)
    tool_http_timeout_seconds = _float_value(
        raw_env,
        "TOOL_HTTP_TIMEOUT_SECONDS",
        DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS,
        errors,
        minimum=0.1,
    )
    default_location = _text_value(raw_env, "DEFAULT_LOCATION", DEFAULT_LOCATION, errors)
    default_base_currency = _text_value(
        raw_env,
        "DEFAULT_BASE_CURRENCY",
        DEFAULT_BASE_CURRENCY,
        errors,
        normalizer=lambda value: value.upper(),
    )
    finnhub_api_key = _optional_secret(raw_env.get("FINNHUB_API_KEY"))
    wake_acknowledgement_enabled = _bool_value(
        raw_env,
        "WAKE_ACKNOWLEDGEMENT_ENABLED",
        DEFAULT_WAKE_ACKNOWLEDGEMENT_ENABLED,
        errors,
    )
    wake_acknowledgement_text = _text_value(
        raw_env,
        "WAKE_ACKNOWLEDGEMENT_TEXT",
        DEFAULT_WAKE_ACKNOWLEDGEMENT_TEXT,
        errors,
    )
    wake_acknowledgement_audio_path = _path_value(
        raw_env,
        "WAKE_ACKNOWLEDGEMENT_AUDIO_PATH",
        DEFAULT_WAKE_ACKNOWLEDGEMENT_AUDIO_PATH,
        errors,
    )
    wake_acknowledgement_drain_seconds = _float_value(
        raw_env,
        "WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS",
        DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS,
        errors,
        minimum=0.0,
    )
    wake_debug = _bool_value(raw_env, "WAKE_DEBUG", DEFAULT_WAKE_DEBUG, errors)
    post_playback_wake_cooldown_seconds = _float_value(
        raw_env,
        "POST_PLAYBACK_WAKE_COOLDOWN_SECONDS",
        DEFAULT_POST_PLAYBACK_WAKE_COOLDOWN_SECONDS,
        errors,
        minimum=0.0,
    )
    post_playback_quiet_seconds = _float_value(
        raw_env,
        "POST_PLAYBACK_QUIET_SECONDS",
        DEFAULT_POST_PLAYBACK_QUIET_SECONDS,
        errors,
        minimum=0.0,
    )
    post_playback_quiet_rms = _float_value(
        raw_env,
        "POST_PLAYBACK_QUIET_RMS",
        DEFAULT_POST_PLAYBACK_QUIET_RMS,
        errors,
        minimum=0.0,
    )
    post_playback_max_suppression_seconds = _float_value(
        raw_env,
        "POST_PLAYBACK_MAX_SUPPRESSION_SECONDS",
        DEFAULT_POST_PLAYBACK_MAX_SUPPRESSION_SECONDS,
        errors,
        minimum=0.0,
    )
    wake_confirmation_frames = _int_value(
        raw_env,
        "WAKE_CONFIRMATION_FRAMES",
        DEFAULT_WAKE_CONFIRMATION_FRAMES,
        errors,
        minimum=1,
    )
    armed_no_speech_timeout_seconds = _float_value(
        raw_env,
        "ARMED_NO_SPEECH_TIMEOUT_SECONDS",
        DEFAULT_ARMED_NO_SPEECH_TIMEOUT_SECONDS,
        errors,
        minimum=0.0,
    )
    armed_voice_rms = _float_value(
        raw_env,
        "ARMED_VOICE_RMS",
        DEFAULT_ARMED_VOICE_RMS,
        errors,
        minimum=0.0,
    )
    armed_min_rms = _float_value(
        raw_env,
        "ARMED_MIN_RMS",
        armed_voice_rms,
        errors,
        minimum=0.0,
    )
    armed_snr_multiplier = _float_value(
        raw_env,
        "ARMED_SNR_MULTIPLIER",
        DEFAULT_ARMED_SNR_MULTIPLIER,
        errors,
        minimum=0.0,
    )
    armed_voice_window_seconds = _float_value(
        raw_env,
        "ARMED_VOICE_WINDOW_SECONDS",
        DEFAULT_ARMED_VOICE_WINDOW_SECONDS,
        errors,
        minimum=0.0,
    )
    armed_voice_required_ratio = _float_value(
        raw_env,
        "ARMED_VOICE_REQUIRED_RATIO",
        DEFAULT_ARMED_VOICE_REQUIRED_RATIO,
        errors,
        minimum=0.0,
        maximum=1.0,
    )
    armed_clip_reject_peak = _int_value(
        raw_env,
        "ARMED_CLIP_REJECT_PEAK",
        DEFAULT_ARMED_CLIP_REJECT_PEAK,
        errors,
        minimum=1,
    )
    if armed_clip_reject_peak > 32768:
        errors.append("ARMED_CLIP_REJECT_PEAK must be at most 32768")
    armed_pre_roll_seconds = _float_value(
        raw_env,
        "ARMED_PRE_ROLL_SECONDS",
        DEFAULT_ARMED_PRE_ROLL_SECONDS,
        errors,
        minimum=0.0,
    )
    min_valid_speech_seconds = _float_value(
        raw_env,
        "MIN_VALID_SPEECH_SECONDS",
        DEFAULT_MIN_VALID_SPEECH_SECONDS,
        errors,
        minimum=0.0,
    )
    min_transcript_length = _int_value(
        raw_env,
        "MIN_TRANSCRIPT_LENGTH",
        DEFAULT_MIN_TRANSCRIPT_LENGTH,
        errors,
        minimum=1,
    )
    cancel_phrases = _text_list_value(raw_env, "CANCEL_PHRASES", DEFAULT_CANCEL_PHRASES, errors)

    if max_record_seconds <= silence_seconds:
        errors.append("MAX_RECORD_SECONDS must be greater than SILENCE_SECONDS")
    if post_playback_max_suppression_seconds < post_playback_wake_cooldown_seconds:
        errors.append(
            "POST_PLAYBACK_MAX_SUPPRESSION_SECONDS must be greater than or equal to "
            "POST_PLAYBACK_WAKE_COOLDOWN_SECONDS"
        )

    if errors:
        raise ConfigError(errors)

    return Settings(
        openai_api_key=openai_api_key,
        wake_backend=wake_backend,
        wake_model=wake_model,
        wake_inference_framework=wake_inference_framework,
        wake_phrase=wake_phrase,
        wake_threshold=wake_threshold,
        silence_seconds=silence_seconds,
        max_record_seconds=max_record_seconds,
        recording_silence_rms=recording_silence_rms,
        sample_rate=sample_rate,
        transcribe_model=transcribe_model,
        chat_model=chat_model,
        tts_model=tts_model,
        tts_voice=tts_voice,
        tts_instructions=tts_instructions,
        tts_speed=tts_speed,
        enable_tools=enable_tools,
        tool_router_debug=tool_router_debug,
        tool_answer_naturalization=tool_answer_naturalization,
        weather_provider=weather_provider,
        fx_provider=fx_provider,
        stock_provider=stock_provider,
        tool_http_timeout_seconds=tool_http_timeout_seconds,
        default_location=default_location,
        default_base_currency=default_base_currency,
        finnhub_api_key=finnhub_api_key,
        wake_acknowledgement_enabled=wake_acknowledgement_enabled,
        wake_acknowledgement_text=wake_acknowledgement_text,
        wake_acknowledgement_audio_path=wake_acknowledgement_audio_path,
        wake_acknowledgement_drain_seconds=wake_acknowledgement_drain_seconds,
        wake_debug=wake_debug,
        post_playback_wake_cooldown_seconds=post_playback_wake_cooldown_seconds,
        post_playback_quiet_seconds=post_playback_quiet_seconds,
        post_playback_quiet_rms=post_playback_quiet_rms,
        post_playback_max_suppression_seconds=post_playback_max_suppression_seconds,
        wake_confirmation_frames=wake_confirmation_frames,
        armed_no_speech_timeout_seconds=armed_no_speech_timeout_seconds,
        armed_voice_rms=armed_voice_rms,
        armed_min_rms=armed_min_rms,
        armed_snr_multiplier=armed_snr_multiplier,
        armed_voice_window_seconds=armed_voice_window_seconds,
        armed_voice_required_ratio=armed_voice_required_ratio,
        armed_clip_reject_peak=armed_clip_reject_peak,
        armed_pre_roll_seconds=armed_pre_roll_seconds,
        min_valid_speech_seconds=min_valid_speech_seconds,
        min_transcript_length=min_transcript_length,
        cancel_phrases=cancel_phrases,
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

    checks.extend(_provider_configuration_checks(settings))

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

    if settings is not None and dependency_modules is None:
        checks.extend(_wake_runtime_dependency_checks(settings))

    checks.extend(_wake_word_model_checks(wake_word_model_paths, modules_to_check, settings))
    checks.extend(_wake_acknowledgement_audio_checks(settings))
    checks.append(
        DiagnosticCheck(
            "microphone_permission",
            "info",
            "Grant macOS microphone permission to the terminal or agent surface that launches Hey Jarvis",
        )
    )

    return DiagnosticReport(tuple(checks))


def wake_acknowledgement_missing_message(settings: Settings) -> str | None:
    """Return actionable guidance when the prepared acknowledgement audio is missing."""

    if not settings.wake_acknowledgement_enabled:
        return None
    if settings.wake_acknowledgement_audio_path.is_file():
        return None
    return (
        f"Wake acknowledgement audio file is missing at {settings.wake_acknowledgement_audio_path}; "
        "run python -m src.main --prepare-acknowledgement before starting the assistant"
    )


def _wake_acknowledgement_audio_checks(settings: Settings | None) -> list[DiagnosticCheck]:
    if settings is None:
        return []
    if not settings.wake_acknowledgement_enabled:
        return [
            DiagnosticCheck(
                "wake_acknowledgement_audio",
                "info",
                "Wake acknowledgement playback is disabled",
            )
        ]
    missing_message = wake_acknowledgement_missing_message(settings)
    if missing_message is not None:
        return [DiagnosticCheck("wake_acknowledgement_audio", "error", missing_message)]
    return [
        DiagnosticCheck(
            "wake_acknowledgement_audio",
            "ok",
            f"Wake acknowledgement audio file is present at {settings.wake_acknowledgement_audio_path}",
        )
    ]


def _provider_configuration_checks(settings: Settings | None) -> list[DiagnosticCheck]:
    if settings is None:
        return []

    provider_config = ProviderConfig(
        weather_provider=settings.weather_provider,
        fx_provider=settings.fx_provider,
        stock_provider=settings.stock_provider,
        http_timeout_seconds=settings.tool_http_timeout_seconds,
        default_location=settings.default_location,
        default_base_currency=settings.default_base_currency,
        finnhub_api_key=settings.finnhub_api_key,
    )
    summary = provider_config.public_summary()
    checks = [
        DiagnosticCheck(
            "tool_providers",
            "ok",
            (
                f"weather={summary['weather_provider']}; fx={summary['fx_provider']}; "
                f"stock={summary['stock_provider']}; timeout={summary['http_timeout_seconds']}s; "
                f"default_location={summary['default_location']}; "
                f"default_base_currency={summary['default_base_currency']}"
            ),
        )
    ]
    if settings.stock_provider.strip().lower() == "finnhub" and settings.finnhub_api_key is None:
        checks.append(
            DiagnosticCheck(
                "FINNHUB_API_KEY",
                "warning",
                "FINNHUB_API_KEY is missing; stock quote requests will report missing credentials",
            )
        )
    elif settings.finnhub_api_key is not None:
        checks.append(DiagnosticCheck("FINNHUB_API_KEY", "ok", "Finnhub API key is configured"))
    return checks


def _wake_word_model_checks(
    wake_word_model_paths: Mapping[str, str | Path] | None,
    dependency_modules: Mapping[str, str],
    settings: Settings | None,
) -> list[DiagnosticCheck]:
    if settings is not None and settings.wake_backend != OPENWAKEWORD_BACKEND:
        return []

    if wake_word_model_paths is None and "openwakeword" in dependency_modules:
        if importlib.util.find_spec("openwakeword") is None:
            return []
        try:
            from .wake_word import required_wake_word_model_paths

            wake_word_model_paths = required_wake_word_model_paths(
                model_name=settings.wake_model if settings is not None else DEFAULT_WAKE_MODEL,
                inference_framework=(
                    settings.wake_inference_framework if settings is not None else DEFAULT_WAKE_INFERENCE_FRAMEWORK
                ),
            )
        except Exception as exc:
            framework = settings.wake_inference_framework if settings is not None else DEFAULT_WAKE_INFERENCE_FRAMEWORK
            return [
                DiagnosticCheck(
                    "wake_word_models",
                    "error",
                    f"Unable to inspect openWakeWord {framework} model files: {exc}",
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
        framework = settings.wake_inference_framework if settings is not None else DEFAULT_WAKE_INFERENCE_FRAMEWORK
        return [
            DiagnosticCheck(
                "wake_word_models",
                "error",
                f"Missing openWakeWord {framework} model files for "
                f"{missing_names}; run python -m src.main --prepare-wake-word",
            )
        ]

    framework = settings.wake_inference_framework if settings is not None else DEFAULT_WAKE_INFERENCE_FRAMEWORK
    return [
        DiagnosticCheck(
            "wake_word_models",
            "ok",
            f"Required openWakeWord {framework} model files are present",
        )
    ]


def _wake_runtime_dependency_checks(settings: Settings) -> list[DiagnosticCheck]:
    if settings.wake_backend != OPENWAKEWORD_BACKEND:
        return []
    if settings.wake_inference_framework == "onnx":
        if importlib.util.find_spec("onnxruntime") is None:
            return [
                DiagnosticCheck(
                    "dependency:onnxruntime",
                    "error",
                    "onnxruntime is required only when WAKE_INFERENCE_FRAMEWORK=onnx; install it explicitly",
                )
            ]
        return [DiagnosticCheck("dependency:onnxruntime", "ok", "onnxruntime is importable")]

    if _has_any_module("ai_edge_litert", "tflite_runtime"):
        return [DiagnosticCheck("dependency:litert", "ok", "LiteRT/TFLite runtime is importable")]
    return [
        DiagnosticCheck(
            "dependency:litert",
            "error",
            "LiteRT/TFLite runtime is required for WAKE_INFERENCE_FRAMEWORK=tflite; install ai-edge-litert",
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


def _bool_value(raw_env: Mapping[str, str], key: str, default: bool, errors: list[str]) -> bool:
    raw = raw_env.get(key)
    if raw is None or raw.strip() == "":
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    errors.append(f"{key} must be a boolean value such as 1, true, 0, or false")
    return default


def _has_any_module(*module_names: str) -> bool:
    return any(importlib.util.find_spec(module_name) is not None for module_name in module_names)


def _choice_value(
    env: Mapping[str, str],
    name: str,
    default: str,
    supported_values: Sequence[str],
    errors: list[str],
    *,
    normalizer,
) -> str:
    raw_value = env.get(name, default)
    try:
        return normalizer(raw_value)
    except ValueError:
        errors.append(f"{name} must be one of {', '.join(supported_values)}")
        return default


def _text_value(env: Mapping[str, str], name: str, default: str, errors: list[str], *, normalizer=None) -> str:
    value = env.get(name, default).strip()
    if not value:
        errors.append(f"{name} must not be empty")
        return default
    if normalizer is not None:
        try:
            return normalizer(value)
        except ValueError as exc:
            errors.append(str(exc))
            return default
    return value


def _optional_text_value(env: Mapping[str, str], name: str) -> str | None:
    raw_value = env.get(name)
    if raw_value is None:
        return None
    value = raw_value.strip()
    return value or None


def _text_list_value(
    env: Mapping[str, str],
    name: str,
    default: Sequence[str],
    errors: list[str],
) -> tuple[str, ...]:
    raw_value = env.get(name)
    if raw_value is None or raw_value.strip() == "":
        return tuple(default)
    values = tuple(part.strip() for part in raw_value.split(",") if part.strip())
    if not values:
        errors.append(f"{name} must include at least one comma-separated phrase")
        return tuple(default)
    return values


def _path_value(env: Mapping[str, str], name: str, default: Path, errors: list[str]) -> Path:
    value = env.get(name, str(default)).strip()
    if not value:
        errors.append(f"{name} must not be empty")
        return default
    return Path(value)


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
