"""PCM RMS silence detection."""

from __future__ import annotations

import math
import struct


DEFAULT_SILENCE_THRESHOLD = 500.0
SAMPLE_WIDTH_BYTES = 2


def rms_level(pcm_chunk: bytes) -> float:
    """Return the RMS amplitude for little-endian signed int16 PCM."""

    if len(pcm_chunk) % SAMPLE_WIDTH_BYTES != 0:
        raise ValueError("PCM chunk length must be even for int16 samples")
    if not pcm_chunk:
        return 0.0

    sample_count = len(pcm_chunk) // SAMPLE_WIDTH_BYTES
    square_sum = 0
    for (sample,) in struct.iter_unpack("<h", pcm_chunk):
        square_sum += sample * sample
    return math.sqrt(square_sum / sample_count)


def is_silence(pcm_chunk: bytes, threshold: float = DEFAULT_SILENCE_THRESHOLD) -> bool:
    """Return true when a little-endian signed int16 PCM chunk is below threshold."""

    if threshold < 0:
        raise ValueError("Silence threshold must be non-negative")
    return rms_level(pcm_chunk) <= threshold
