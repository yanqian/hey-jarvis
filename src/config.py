"""Configuration loading and diagnostics for Hey Jarvis."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

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
DEFAULT_WAKE_VAD_THRESHOLD: float | None = None
DEFAULT_SILENCE_SECONDS = 1.5
DEFAULT_MAX_RECORD_SECONDS = 20.0
DEFAULT_RECORDING_SILENCE_RMS = 750.0
DEFAULT_VAD_BACKEND = "disabled"
DEFAULT_VAD_MODE = 2
DEFAULT_ARMED_VAD_REQUIRED_RATIO = 0.50
DEFAULT_ARMED_VAD_MIN_FRAMES = 2
DEFAULT_RECORDING_VAD_ENABLED = False
DEFAULT_RECORDING_VAD_END_RATIO = 0.25
DEFAULT_RECORDING_VAD_SPEECH_RATIO = 0.50
DEFAULT_RECORDING_HANGOVER_SECONDS = 0.30
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
DEFAULT_WAKE_ACKNOWLEDGEMENT_TEXT = "嗯"
DEFAULT_WAKE_ACKNOWLEDGEMENT_AUDIO_PATH = Path("var/ack.mp3")
DEFAULT_WAKE_ACKNOWLEDGEMENT_MAX_DURATION_SECONDS = 0.8
DEFAULT_WAKE_ACKNOWLEDGEMENT_SHA256 = (
    "7a2729046e2b0acdbec345d3d825768ac0e30f9228994092382a885f82109b0c"
)
DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS = 0.35
DEFAULT_ACK_GUARD_ENABLED = True
DEFAULT_ACK_GUARD_MIN_QUIET_SECONDS = 0.16
DEFAULT_ACK_GUARD_QUIET_RMS = 900.0
DEFAULT_ACK_GUARD_MAX_BUFFER_SECONDS = 1.50
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
DEFAULT_ARMED_BASELINE_SECONDS = 0.30
DEFAULT_ARMED_BASELINE_MIN_CHUNKS = 3
DEFAULT_ARMED_REQUIRE_BASELINE = True
DEFAULT_ARMED_LAST_CHUNK_MUST_BE_VOICED = True
DEFAULT_MIN_VALID_SPEECH_SECONDS = 0.50
DEFAULT_MIN_TRANSCRIPT_LENGTH = 2
DEFAULT_CANCEL_PHRASES = ("取消", "没事", "不用了", "算了", "stop", "cancel", "never mind")
DEFAULT_BACKEND = "pipeline"
SUPPORTED_BACKENDS = ("pipeline", "realtime")
DEFAULT_REALTIME_MODEL = "gpt-realtime-2.1"
DEFAULT_REALTIME_VOICE = "alloy"
DEFAULT_REALTIME_OUTPUT_VOLUME = 0.5
DEFAULT_REALTIME_IDLE_TIMEOUT_SECONDS = 60.0
DEFAULT_REALTIME_MAX_DURATION_SECONDS = 600.0
DEFAULT_REALTIME_SERVER_VAD_ENABLED = True
DEFAULT_REALTIME_SERVER_VAD_THRESHOLD = 0.8
DEFAULT_REALTIME_INPUT_NOISE_REDUCTION = "far_field"
SUPPORTED_REALTIME_INPUT_NOISE_REDUCTIONS = ("none", "near_field", "far_field")
DEFAULT_REALTIME_INPUT_TRANSCRIPTION_ENABLED = True
DEFAULT_REALTIME_ACKNOWLEDGEMENT_MODE = "local"
SUPPORTED_REALTIME_ACKNOWLEDGEMENT_MODES = ("local", "none")
DEFAULT_REALTIME_DEBUG = False
DEFAULT_REALTIME_END_PHRASES = ("结束对话", "再见", "goodbye", "end conversation")
DEFAULT_REALTIME_BRIDGE_HOST = "127.0.0.1"
DEFAULT_REALTIME_BRIDGE_PORT = 8770


def normalize_realtime_acknowledgement_mode(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_REALTIME_ACKNOWLEDGEMENT_MODES:
        raise ValueError(value)
    return normalized


def normalize_realtime_input_noise_reduction(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_REALTIME_INPUT_NOISE_REDUCTIONS:
        raise ValueError(value)
    return normalized


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
    wake_vad_threshold: float | None = DEFAULT_WAKE_VAD_THRESHOLD
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
    wake_acknowledgement_max_duration_seconds: float = (
        DEFAULT_WAKE_ACKNOWLEDGEMENT_MAX_DURATION_SECONDS
    )
    wake_acknowledgement_drain_seconds: float = DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS
    ack_guard_enabled: bool = DEFAULT_ACK_GUARD_ENABLED
    ack_guard_min_quiet_seconds: float = DEFAULT_ACK_GUARD_MIN_QUIET_SECONDS
    ack_guard_quiet_rms: float = DEFAULT_ACK_GUARD_QUIET_RMS
    ack_guard_max_buffer_seconds: float = DEFAULT_ACK_GUARD_MAX_BUFFER_SECONDS
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
    armed_baseline_seconds: float = DEFAULT_ARMED_BASELINE_SECONDS
    armed_baseline_min_chunks: int = DEFAULT_ARMED_BASELINE_MIN_CHUNKS
    armed_require_baseline: bool = DEFAULT_ARMED_REQUIRE_BASELINE
    armed_last_chunk_must_be_voiced: bool = DEFAULT_ARMED_LAST_CHUNK_MUST_BE_VOICED
    min_valid_speech_seconds: float = DEFAULT_MIN_VALID_SPEECH_SECONDS
    min_transcript_length: int = DEFAULT_MIN_TRANSCRIPT_LENGTH
    cancel_phrases: tuple[str, ...] = DEFAULT_CANCEL_PHRASES
    recording_silence_rms: float = DEFAULT_RECORDING_SILENCE_RMS
    vad_backend: str = DEFAULT_VAD_BACKEND
    vad_mode: int = DEFAULT_VAD_MODE
    armed_vad_required_ratio: float = DEFAULT_ARMED_VAD_REQUIRED_RATIO
    armed_vad_min_frames: int = DEFAULT_ARMED_VAD_MIN_FRAMES
    recording_vad_enabled: bool = DEFAULT_RECORDING_VAD_ENABLED
    recording_vad_end_ratio: float = DEFAULT_RECORDING_VAD_END_RATIO
    recording_vad_speech_ratio: float = DEFAULT_RECORDING_VAD_SPEECH_RATIO
    recording_hangover_seconds: float = DEFAULT_RECORDING_HANGOVER_SECONDS
    recording_end_silence_seconds: float = DEFAULT_SILENCE_SECONDS
    backend: str = DEFAULT_BACKEND
    realtime_model: str = DEFAULT_REALTIME_MODEL
    realtime_voice: str = DEFAULT_REALTIME_VOICE
    realtime_output_volume: float = DEFAULT_REALTIME_OUTPUT_VOLUME
    realtime_idle_timeout_seconds: float = DEFAULT_REALTIME_IDLE_TIMEOUT_SECONDS
    realtime_max_duration_seconds: float = DEFAULT_REALTIME_MAX_DURATION_SECONDS
    realtime_server_vad_enabled: bool = DEFAULT_REALTIME_SERVER_VAD_ENABLED
    realtime_server_vad_threshold: float = DEFAULT_REALTIME_SERVER_VAD_THRESHOLD
    realtime_input_noise_reduction: str = DEFAULT_REALTIME_INPUT_NOISE_REDUCTION
    realtime_input_transcription_enabled: bool = DEFAULT_REALTIME_INPUT_TRANSCRIPTION_ENABLED
    realtime_acknowledgement_mode: str = DEFAULT_REALTIME_ACKNOWLEDGEMENT_MODE
    realtime_debug: bool = DEFAULT_REALTIME_DEBUG
    realtime_end_phrases: tuple[str, ...] = DEFAULT_REALTIME_END_PHRASES
    realtime_bridge_host: str = DEFAULT_REALTIME_BRIDGE_HOST
    realtime_bridge_port: int = DEFAULT_REALTIME_BRIDGE_PORT


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
    backend: str | None = None,
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

    backend_value = (backend or raw_env.get("BACKEND", DEFAULT_BACKEND)).strip().lower()
    if backend_value not in SUPPORTED_BACKENDS:
        errors.append(f"BACKEND must be one of: {', '.join(SUPPORTED_BACKENDS)}")
        backend_value = DEFAULT_BACKEND

    realtime_model = DEFAULT_REALTIME_MODEL
    realtime_voice = DEFAULT_REALTIME_VOICE
    realtime_output_volume = DEFAULT_REALTIME_OUTPUT_VOLUME
    realtime_idle_timeout_seconds = DEFAULT_REALTIME_IDLE_TIMEOUT_SECONDS
    realtime_max_duration_seconds = DEFAULT_REALTIME_MAX_DURATION_SECONDS
    realtime_server_vad_enabled = DEFAULT_REALTIME_SERVER_VAD_ENABLED
    realtime_server_vad_threshold = DEFAULT_REALTIME_SERVER_VAD_THRESHOLD
    realtime_input_noise_reduction = DEFAULT_REALTIME_INPUT_NOISE_REDUCTION
    realtime_input_transcription_enabled = DEFAULT_REALTIME_INPUT_TRANSCRIPTION_ENABLED
    realtime_acknowledgement_mode = DEFAULT_REALTIME_ACKNOWLEDGEMENT_MODE
    realtime_debug = DEFAULT_REALTIME_DEBUG
    realtime_end_phrases = DEFAULT_REALTIME_END_PHRASES
    realtime_bridge_host = DEFAULT_REALTIME_BRIDGE_HOST
    realtime_bridge_port = DEFAULT_REALTIME_BRIDGE_PORT
    if backend_value == "realtime":
        realtime_model = _text_value(raw_env, "REALTIME_MODEL", DEFAULT_REALTIME_MODEL, errors)
        realtime_voice = _text_value(raw_env, "REALTIME_VOICE", DEFAULT_REALTIME_VOICE, errors)
        realtime_output_volume = _float_value(
            raw_env,
            "REALTIME_OUTPUT_VOLUME",
            DEFAULT_REALTIME_OUTPUT_VOLUME,
            errors,
            minimum=0.1,
            maximum=1.0,
        )
        realtime_idle_timeout_seconds = _float_value(
            raw_env,
            "REALTIME_IDLE_TIMEOUT_SECONDS",
            DEFAULT_REALTIME_IDLE_TIMEOUT_SECONDS,
            errors,
            minimum=1.0,
        )
        realtime_max_duration_seconds = _float_value(
            raw_env,
            "REALTIME_MAX_DURATION_SECONDS",
            DEFAULT_REALTIME_MAX_DURATION_SECONDS,
            errors,
            minimum=1.0,
            maximum=3600.0,
        )
        realtime_server_vad_enabled = _bool_value(
            raw_env, "REALTIME_SERVER_VAD_ENABLED", DEFAULT_REALTIME_SERVER_VAD_ENABLED, errors
        )
        realtime_server_vad_threshold = _float_value(
            raw_env,
            "REALTIME_SERVER_VAD_THRESHOLD",
            DEFAULT_REALTIME_SERVER_VAD_THRESHOLD,
            errors,
            minimum=0.0,
            maximum=1.0,
        )
        realtime_input_noise_reduction = _choice_value(
            raw_env,
            "REALTIME_INPUT_NOISE_REDUCTION",
            DEFAULT_REALTIME_INPUT_NOISE_REDUCTION,
            SUPPORTED_REALTIME_INPUT_NOISE_REDUCTIONS,
            errors,
            normalizer=normalize_realtime_input_noise_reduction,
        )
        realtime_input_transcription_enabled = _bool_value(
            raw_env,
            "REALTIME_INPUT_TRANSCRIPTION_ENABLED",
            DEFAULT_REALTIME_INPUT_TRANSCRIPTION_ENABLED,
            errors,
        )
        realtime_acknowledgement_mode = _choice_value(
            raw_env,
            "REALTIME_ACKNOWLEDGEMENT_MODE",
            DEFAULT_REALTIME_ACKNOWLEDGEMENT_MODE,
            SUPPORTED_REALTIME_ACKNOWLEDGEMENT_MODES,
            errors,
            normalizer=normalize_realtime_acknowledgement_mode,
        )
        realtime_debug = _bool_value(raw_env, "REALTIME_DEBUG", DEFAULT_REALTIME_DEBUG, errors)
        realtime_end_phrases = _text_list_value(
            raw_env, "REALTIME_END_PHRASES", DEFAULT_REALTIME_END_PHRASES, errors
        )
        realtime_bridge_host = _text_value(
            raw_env, "REALTIME_BRIDGE_HOST", DEFAULT_REALTIME_BRIDGE_HOST, errors
        )
        realtime_bridge_port = _int_value(
            raw_env, "REALTIME_BRIDGE_PORT", DEFAULT_REALTIME_BRIDGE_PORT, errors, minimum=1, maximum=65535
        )
        if realtime_max_duration_seconds <= realtime_idle_timeout_seconds:
            errors.append("REALTIME_MAX_DURATION_SECONDS must be greater than REALTIME_IDLE_TIMEOUT_SECONDS")
        if realtime_bridge_host not in {"127.0.0.1", "localhost", "::1"}:
            errors.append("REALTIME_BRIDGE_HOST must be loopback-only")

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
    wake_vad_threshold = _optional_float_value(
        raw_env, "WAKE_VAD_THRESHOLD", errors, minimum=0.0, maximum=1.0
    )
    silence_seconds = _float_value(
        raw_env,
        "SILENCE_SECONDS",
        DEFAULT_SILENCE_SECONDS,
        errors,
        minimum=0.1,
    )
    vad_backend = _choice_value(
        raw_env,
        "VAD_BACKEND",
        DEFAULT_VAD_BACKEND,
        ("disabled", "webrtc"),
        errors,
        normalizer=lambda value: value.strip().lower(),
    )
    vad_mode = _int_value(raw_env, "VAD_MODE", DEFAULT_VAD_MODE, errors, minimum=0, maximum=3)
    armed_vad_required_ratio = _float_value(
        raw_env,
        "ARMED_VAD_REQUIRED_RATIO",
        DEFAULT_ARMED_VAD_REQUIRED_RATIO,
        errors,
        minimum=0.0,
        maximum=1.0,
    )
    armed_vad_min_frames = _int_value(
        raw_env, "ARMED_VAD_MIN_FRAMES", DEFAULT_ARMED_VAD_MIN_FRAMES, errors, minimum=1
    )
    recording_vad_enabled = _bool_value(
        raw_env, "RECORDING_VAD_ENABLED", DEFAULT_RECORDING_VAD_ENABLED, errors
    )
    recording_vad_end_ratio = _float_value(
        raw_env,
        "RECORDING_VAD_END_RATIO",
        DEFAULT_RECORDING_VAD_END_RATIO,
        errors,
        minimum=0.0,
        maximum=1.0,
    )
    recording_vad_speech_ratio = _float_value(
        raw_env,
        "RECORDING_VAD_SPEECH_RATIO",
        DEFAULT_RECORDING_VAD_SPEECH_RATIO,
        errors,
        minimum=0.0,
        maximum=1.0,
    )
    recording_hangover_seconds = _float_value(
        raw_env,
        "RECORDING_HANGOVER_SECONDS",
        DEFAULT_RECORDING_HANGOVER_SECONDS,
        errors,
        minimum=0.0,
    )
    recording_end_silence_seconds = _float_value(
        raw_env,
        "RECORDING_END_SILENCE_SECONDS",
        silence_seconds,
        errors,
        minimum=0.1,
    )
    if recording_vad_enabled and vad_backend == "disabled":
        errors.append("RECORDING_VAD_ENABLED requires VAD_BACKEND=webrtc")
    if recording_vad_speech_ratio < recording_vad_end_ratio:
        errors.append(
            "RECORDING_VAD_SPEECH_RATIO must be greater than or equal to RECORDING_VAD_END_RATIO"
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
    wake_acknowledgement_max_duration_seconds = _float_value(
        raw_env,
        "WAKE_ACKNOWLEDGEMENT_MAX_DURATION_SECONDS",
        DEFAULT_WAKE_ACKNOWLEDGEMENT_MAX_DURATION_SECONDS,
        errors,
        minimum=0.1,
        maximum=5.0,
    )
    wake_acknowledgement_drain_seconds = _float_value(
        raw_env,
        "WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS",
        DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS,
        errors,
        minimum=0.0,
    )
    ack_guard_enabled = _bool_value(raw_env, "ACK_GUARD_ENABLED", DEFAULT_ACK_GUARD_ENABLED, errors)
    ack_guard_min_quiet_seconds = _float_value(
        raw_env,
        "ACK_GUARD_MIN_QUIET_SECONDS",
        DEFAULT_ACK_GUARD_MIN_QUIET_SECONDS,
        errors,
        minimum=0.0,
    )
    if ack_guard_enabled and ack_guard_min_quiet_seconds <= 0:
        errors.append("ACK_GUARD_MIN_QUIET_SECONDS must be greater than 0 when ACK_GUARD_ENABLED is true")
    ack_guard_quiet_rms = _float_value(
        raw_env, "ACK_GUARD_QUIET_RMS", DEFAULT_ACK_GUARD_QUIET_RMS, errors, minimum=0.0
    )
    ack_guard_max_buffer_seconds = _float_value(
        raw_env,
        "ACK_GUARD_MAX_BUFFER_SECONDS",
        DEFAULT_ACK_GUARD_MAX_BUFFER_SECONDS,
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
    armed_baseline_seconds = _float_value(
        raw_env, "ARMED_BASELINE_SECONDS", DEFAULT_ARMED_BASELINE_SECONDS, errors, minimum=0.0
    )
    armed_baseline_min_chunks = _int_value(
        raw_env, "ARMED_BASELINE_MIN_CHUNKS", DEFAULT_ARMED_BASELINE_MIN_CHUNKS, errors, minimum=0
    )
    armed_require_baseline = _bool_value(
        raw_env, "ARMED_REQUIRE_BASELINE", DEFAULT_ARMED_REQUIRE_BASELINE, errors
    )
    armed_last_chunk_must_be_voiced = _bool_value(
        raw_env,
        "ARMED_LAST_CHUNK_MUST_BE_VOICED",
        DEFAULT_ARMED_LAST_CHUNK_MUST_BE_VOICED,
        errors,
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
    if max_record_seconds <= recording_end_silence_seconds:
        errors.append("MAX_RECORD_SECONDS must be greater than RECORDING_END_SILENCE_SECONDS")
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
        wake_vad_threshold=wake_vad_threshold,
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
        wake_acknowledgement_max_duration_seconds=wake_acknowledgement_max_duration_seconds,
        wake_acknowledgement_drain_seconds=wake_acknowledgement_drain_seconds,
        ack_guard_enabled=ack_guard_enabled,
        ack_guard_min_quiet_seconds=ack_guard_min_quiet_seconds,
        ack_guard_quiet_rms=ack_guard_quiet_rms,
        ack_guard_max_buffer_seconds=ack_guard_max_buffer_seconds,
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
        armed_baseline_seconds=armed_baseline_seconds,
        armed_baseline_min_chunks=armed_baseline_min_chunks,
        armed_require_baseline=armed_require_baseline,
        armed_last_chunk_must_be_voiced=armed_last_chunk_must_be_voiced,
        min_valid_speech_seconds=min_valid_speech_seconds,
        min_transcript_length=min_transcript_length,
        cancel_phrases=cancel_phrases,
        vad_backend=vad_backend,
        vad_mode=vad_mode,
        armed_vad_required_ratio=armed_vad_required_ratio,
        armed_vad_min_frames=armed_vad_min_frames,
        recording_vad_enabled=recording_vad_enabled,
        recording_vad_end_ratio=recording_vad_end_ratio,
        recording_vad_speech_ratio=recording_vad_speech_ratio,
        recording_hangover_seconds=recording_hangover_seconds,
        recording_end_silence_seconds=recording_end_silence_seconds,
        backend=backend_value,
        realtime_model=realtime_model,
        realtime_voice=realtime_voice,
        realtime_output_volume=realtime_output_volume,
        realtime_idle_timeout_seconds=realtime_idle_timeout_seconds,
        realtime_max_duration_seconds=realtime_max_duration_seconds,
        realtime_server_vad_enabled=realtime_server_vad_enabled,
        realtime_server_vad_threshold=realtime_server_vad_threshold,
        realtime_input_noise_reduction=realtime_input_noise_reduction,
        realtime_input_transcription_enabled=realtime_input_transcription_enabled,
        realtime_acknowledgement_mode=realtime_acknowledgement_mode,
        realtime_debug=realtime_debug,
        realtime_end_phrases=realtime_end_phrases,
        realtime_bridge_host=realtime_bridge_host,
        realtime_bridge_port=realtime_bridge_port,
    )


def collect_diagnostics(
    env: Mapping[str, str] | None = None,
    env_file: str | Path | None = ".env",
    *,
    python_version: tuple[int, int] | None = None,
    afplay_path: str | None = None,
    dependency_modules: Mapping[str, str] | None = None,
    wake_word_model_paths: Mapping[str, str | Path] | None = None,
    acknowledgement_duration_reader: Callable[[Path], int] | None = None,
    acknowledgement_hash_reader: Callable[[Path], str] | None = None,
    backend: str | None = None,
) -> DiagnosticReport:
    """Collect diagnostics, probing an optional runtime only when configured."""

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
        settings = load_settings(env=env, env_file=env_file, backend=backend)
    except ConfigError as exc:
        checks.append(DiagnosticCheck("configuration", "error", "; ".join(exc.errors)))
        settings = None
    else:
        checks.append(DiagnosticCheck("configuration", "ok", "Environment values loaded"))

    if settings is not None:
        checks.extend(_backend_readiness_checks(settings))

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
        if settings.vad_backend == "webrtc":
            try:
                from .vad import build_vad_detector

                detector = build_vad_detector("webrtc", mode=settings.vad_mode)
                frame_samples = settings.sample_rate * 20 // 1000
                detector.analyze(b"\x00\x00" * frame_samples, settings.sample_rate)
            except Exception as exc:
                failure = f"WebRTC VAD runtime probe failed: {type(exc).__name__}: {exc}"
                if "requirements-vad.txt" not in failure:
                    failure += (
                        ". Install compatible optional dependencies with "
                        "`python -m pip install -r requirements-vad.txt`"
                    )
                checks.append(
                    DiagnosticCheck(
                        "dependency:webrtcvad",
                        "error",
                        failure,
                    )
                )
            else:
                checks.append(
                    DiagnosticCheck(
                        "dependency:webrtcvad",
                        "ok",
                        "WebRTC VAD imported, constructed, and classified a 20ms frame",
                    )
                )

    checks.extend(_wake_word_model_checks(wake_word_model_paths, modules_to_check, settings))
    checks.extend(
        _wake_acknowledgement_audio_checks(
            settings,
            duration_reader=acknowledgement_duration_reader,
            hash_reader=acknowledgement_hash_reader,
        )
    )
    checks.append(
        DiagnosticCheck(
            "microphone_permission",
            "info",
            "Grant macOS microphone permission to the terminal or agent surface that launches Hey Jarvis",
        )
    )

    return DiagnosticReport(tuple(checks))


def _backend_readiness_checks(settings: Settings) -> list[DiagnosticCheck]:
    if settings.backend == "pipeline":
        return [
            DiagnosticCheck("backend:pipeline", "ok", "Pipeline backend selected and Realtime-only settings are inactive"),
            DiagnosticCheck("backend:realtime", "skip", "Realtime backend is not selected"),
        ]

    static_root = Path(__file__).resolve().parent / "realtime_host" / "static"
    required_assets = ("index.html", "app.js", "styles.css")
    assets_ready = all((static_root / name).is_file() for name in required_assets)
    loopback_ready = settings.realtime_bridge_host in {"127.0.0.1", "localhost", "::1"}
    checks = [
        DiagnosticCheck("backend:pipeline", "skip", "Pipeline backend is available but not selected"),
        DiagnosticCheck(
            "realtime:host-assets",
            "ok" if assets_ready else "error",
            "Realtime Chrome app-mode host assets are present"
            if assets_ready
            else "Realtime host assets are missing; restore src/realtime_host/static",
        ),
        DiagnosticCheck(
            "realtime:model-voice",
            "ok",
            f"Realtime model={settings.realtime_model} voice={settings.realtime_voice} "
            f"output_volume={settings.realtime_output_volume} "
            f"server_vad_threshold={settings.realtime_server_vad_threshold} "
            f"input_noise_reduction={settings.realtime_input_noise_reduction}",
        ),
        DiagnosticCheck(
            "realtime:credential",
            "ok" if settings.openai_api_key else "error",
            "Standard API key is configured for server-side ephemeral credential minting"
            if settings.openai_api_key
            else "OPENAI_API_KEY is required by the selected Realtime backend",
        ),
        DiagnosticCheck(
            "realtime:loopback",
            "ok" if loopback_ready else "error",
            f"Realtime bridge is loopback-only at {settings.realtime_bridge_host}:{settings.realtime_bridge_port}"
            if loopback_ready
            else "Realtime bridge host is not loopback-only",
        ),
        DiagnosticCheck(
            "realtime:audio-handoff",
            "ok",
            "Exclusive wake/host microphone handoff contract is available",
        ),
        DiagnosticCheck(
            "realtime:arming",
            "info",
            "Arm Chrome once per launched host; Chrome microphone permission lasts for that host/profile lifetime",
        ),
        DiagnosticCheck(
            "realtime:privacy-cost",
            "info",
            "Pre-wake audio stays local; active WebRTC audio/transcription is uploaded and billable; reports are bounded and content-redacted",
        ),
        DiagnosticCheck(
            "realtime:mvp-scope",
            "info",
            "Calculator is the only Realtime tool; signing, notarization, bundled hosting, and app packaging are deferred",
        ),
    ]
    return checks


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


def _wake_acknowledgement_audio_checks(
    settings: Settings | None,
    *,
    duration_reader: Callable[[Path], int] | None = None,
    hash_reader: Callable[[Path], str] | None = None,
) -> list[DiagnosticCheck]:
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
    if duration_reader is None:
        from .player import audio_duration_ms

        duration_reader = audio_duration_ms
    if hash_reader is None:
        from .player import audio_sha256

        hash_reader = audio_sha256
    try:
        duration_ms = duration_reader(settings.wake_acknowledgement_audio_path)
    except Exception:
        return [
            DiagnosticCheck(
                "wake_acknowledgement_audio",
                "error",
                "Wake acknowledgement duration could not be read; "
                "run python -m src.main --prepare-acknowledgement to restore the accepted asset",
            )
        ]
    maximum_ms = round(settings.wake_acknowledgement_max_duration_seconds * 1000)
    if (
        isinstance(duration_ms, bool)
        or not isinstance(duration_ms, int)
        or not 1 <= duration_ms <= maximum_ms
    ):
        return [
            DiagnosticCheck(
                "wake_acknowledgement_audio",
                "error",
                f"Wake acknowledgement duration is outside the configured 1–{maximum_ms} ms range; "
                "run python -m src.main --prepare-acknowledgement to restore the accepted asset",
            )
        ]
    try:
        asset_hash = hash_reader(settings.wake_acknowledgement_audio_path)
    except Exception:
        return [
            DiagnosticCheck(
                "wake_acknowledgement_audio",
                "error",
                "Wake acknowledgement integrity could not be read; "
                "run python -m src.main --prepare-acknowledgement to restore the accepted asset",
            )
        ]
    if asset_hash != DEFAULT_WAKE_ACKNOWLEDGEMENT_SHA256:
        return [
            DiagnosticCheck(
                "wake_acknowledgement_audio",
                "error",
                "Wake acknowledgement does not match the accepted clear audible asset; "
                "run python -m src.main --prepare-acknowledgement to restore the accepted asset",
            )
        ]
    return [
        DiagnosticCheck(
            "wake_acknowledgement_audio",
            "ok",
            f"Wake acknowledgement duration is {duration_ms} ms "
            f"(configured maximum {maximum_ms} ms) and its SHA-256 matches "
            "the accepted clear audible asset",
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


def _optional_float_value(
    env: Mapping[str, str],
    name: str,
    errors: list[str],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    raw_value = env.get(name)
    if raw_value is None or raw_value.strip() == "":
        return None
    return _float_value(env, name, 0.0, errors, minimum=minimum, maximum=maximum)


def _int_value(
    env: Mapping[str, str],
    name: str,
    default: int,
    errors: list[str],
    *,
    minimum: int | None = None,
    maximum: int | None = None,
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
    if maximum is not None and value > maximum:
        errors.append(f"{name} must be at most {maximum}")
    return value
