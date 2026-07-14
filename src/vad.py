"""Optional local voice-activity detection boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


SUPPORTED_WEBRTC_SAMPLE_RATES = (8000, 16000, 32000, 48000)
WEBRTC_FRAME_MILLISECONDS = 20
SAMPLE_WIDTH_BYTES = 2


class VadError(RuntimeError):
    """Raised when an explicitly configured VAD backend cannot operate."""


@dataclass(frozen=True)
class VadResult:
    voiced_ratio: float
    voiced_frames: int
    total_frames: int


class VoiceActivityDetector(Protocol):
    @property
    def is_enabled(self) -> bool:
        """Whether VAD should gate speech decisions."""

    def analyze(self, pcm_chunk: bytes, sample_rate: int) -> VadResult | None:
        """Classify complete frames in a mono int16 PCM chunk."""

    def voiced_ratio(self, pcm_chunk: bytes, sample_rate: int) -> float | None:
        """Return the voiced-frame ratio, or None when disabled/unavailable."""


class DisabledVad:
    @property
    def is_enabled(self) -> bool:
        return False

    def analyze(self, pcm_chunk: bytes, sample_rate: int) -> VadResult | None:
        return None

    def voiced_ratio(self, pcm_chunk: bytes, sample_rate: int) -> float | None:
        return None


class WebRtcVadDetector:
    def __init__(self, mode: int = 2, *, vad: Any | None = None) -> None:
        if mode < 0 or mode > 3:
            raise ValueError("WebRTC VAD mode must be between 0 and 3")
        if vad is None:
            try:
                import webrtcvad
            except ImportError as exc:
                raise VadError(
                    "VAD_BACKEND=webrtc could not import its optional runtime "
                    f"({exc}); install it with "
                    "`python -m pip install -r requirements-vad.txt`"
                ) from exc
            try:
                vad = webrtcvad.Vad(mode)
            except Exception as exc:
                raise VadError(f"WebRTC VAD detector construction failed: {exc}") from exc
        self._vad = vad

    @property
    def is_enabled(self) -> bool:
        return True

    def analyze(self, pcm_chunk: bytes, sample_rate: int) -> VadResult:
        if sample_rate not in SUPPORTED_WEBRTC_SAMPLE_RATES:
            supported = ", ".join(str(value) for value in SUPPORTED_WEBRTC_SAMPLE_RATES)
            raise VadError(f"WebRTC VAD sample rate must be one of {supported}; got {sample_rate}")
        if len(pcm_chunk) % SAMPLE_WIDTH_BYTES != 0:
            raise ValueError("PCM chunks must contain complete int16 samples")

        frame_bytes = sample_rate * WEBRTC_FRAME_MILLISECONDS // 1000 * SAMPLE_WIDTH_BYTES
        total_frames = len(pcm_chunk) // frame_bytes
        if total_frames == 0:
            return VadResult(0.0, 0, 0)
        voiced_frames = 0
        for offset in range(0, total_frames * frame_bytes, frame_bytes):
            frame = pcm_chunk[offset : offset + frame_bytes]
            try:
                voiced_frames += bool(self._vad.is_speech(frame, sample_rate))
            except Exception as exc:
                raise VadError(f"WebRTC VAD failed to classify a 20ms PCM frame: {exc}") from exc
        return VadResult(voiced_frames / total_frames, voiced_frames, total_frames)

    def voiced_ratio(self, pcm_chunk: bytes, sample_rate: int) -> float:
        return self.analyze(pcm_chunk, sample_rate).voiced_ratio


def build_vad_detector(backend: str, *, mode: int = 2) -> VoiceActivityDetector:
    normalized = backend.strip().lower()
    if normalized == "disabled":
        return DisabledVad()
    if normalized == "webrtc":
        return WebRtcVadDetector(mode)
    raise ValueError("VAD_BACKEND must be one of: disabled, webrtc")
