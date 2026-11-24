"""Abstract interfaces for pluggable TTS and Image providers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    """Interface for text-to-speech narration synthesis."""

    @abstractmethod
    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav_path: Path,
        voice: str | None = None,
        style_instructions: str | None = None,
    ) -> Path:
        """Synthesize spoken narration text into a WAV file at output_wav_path."""


class ImageProvider(ABC):
    """Interface for 16:9 scene image generation."""

    @abstractmethod
    def generate_image(
        self,
        *,
        prompt: str,
        output_png_path: Path,
        width: int = 1920,
        height: int = 1080,
    ) -> Path:
        """Generate a 16:9 image and save it as PNG at output_png_path."""


def chunk_text_for_tts(text: str, max_chars: int = 2400) -> list[str]:
    """Split narration text cleanly on paragraph and sentence boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        if len(para) > max_chars:
            if current:
                chunks.append("\n\n".join(current))
                current, current_len = [], 0
            sentences = re.split(r"(?<=[.!?])\s+", para)
            sent_buf: list[str] = []
            sent_len = 0
            for sentence in sentences:
                if sent_len + len(sentence) + 1 > max_chars and sent_buf:
                    chunks.append(" ".join(sent_buf))
                    sent_buf, sent_len = [sentence], len(sentence)
                else:
                    sent_buf.append(sentence)
                    sent_len += len(sentence) + 1
            if sent_buf:
                chunks.append(" ".join(sent_buf))
            continue

        if current_len + len(para) + 2 > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para) + 2

    if current:
        chunks.append("\n\n".join(current))

    return chunks or [text.strip()]
