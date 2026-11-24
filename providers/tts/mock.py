"""Offline deterministic mock TTS provider for zero-cost pipeline testing."""

from __future__ import annotations

import hashlib
import math
import struct
import wave
from pathlib import Path

from providers.base import TTSProvider


class MockTTSProvider(TTSProvider):
    """Generates clean synthetic WAV placeholders sized proportionally to chapter length."""

    def __init__(self, seconds_per_100_words: float = 1.6, sample_rate: int = 24000) -> None:
        self.seconds_per_100_words = seconds_per_100_words
        self.sample_rate = sample_rate

    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav_path: Path,
        voice: str | None = None,
        style_instructions: str | None = None,
    ) -> Path:
        words = max(1, len(text.split()))
        duration = max(2.5, min(10.0, (words / 100.0) * self.seconds_per_100_words))
        total_samples = int(duration * self.sample_rate)

        seed = int(hashlib.sha256(text[:120].encode("utf-8")).hexdigest()[:8], 16)
        base_freq = 150.0 + (seed % 40)

        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)

            frames = bytearray()
            for i in range(total_samples):
                t = i / self.sample_rate
                envelope = 0.55 + 0.45 * math.sin(2.0 * math.pi * 2.2 * t)
                fade = min(1.0, t / 0.25, (duration - t) / 0.25)
                sample = (
                    0.18 * math.sin(2.0 * math.pi * base_freq * t)
                    + 0.08 * math.sin(2.0 * math.pi * (base_freq * 1.5) * t)
                ) * envelope * max(0.0, fade)
                pcm = max(-32767, min(32767, int(sample * 32767)))
                frames.extend(struct.pack("<h", pcm))
            wf.writeframes(frames)

        return output_wav_path
