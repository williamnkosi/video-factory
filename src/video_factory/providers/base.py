"""Abstract provider interfaces and shared text/JSON parsing helpers."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Interface for text and structured JSON generation."""

    @abstractmethod
    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Return plain prose text."""

    @abstractmethod
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.5,
        max_tokens: int = 4096,
    ) -> T:
        """Return a validated Pydantic model parsed from JSON output."""


class TTSProvider(ABC):
    """Interface for text-to-speech narration synthesis."""

    @abstractmethod
    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav_path: Path,
        voice_instructions: str | None = None,
    ) -> Path:
        """Synthesize narration text into a WAV audio file."""


class ImageProvider(ABC):
    """Interface for 16:9 image generation."""

    @abstractmethod
    def generate_image(
        self,
        *,
        prompt: str,
        output_png_path: Path,
        width: int = 1920,
        height: int = 1080,
    ) -> Path:
        """Generate an image and save it as PNG at output_png_path."""


def extract_json_payload(raw_text: str) -> dict | list:
    """Robustly extract JSON from an LLM response (handles markdown code fences)."""
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Attempt to find the outermost JSON object/array
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            return json.loads(cleaned[first_brace : last_brace + 1])
        raise


def chunk_text_for_tts(text: str, max_chars: int = 3200) -> list[str]:
    """Split narration text cleanly on paragraph/sentence boundaries for TTS APIs."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        if len(para) > max_chars:
            # Flush existing buffer first
            if current:
                chunks.append("\n\n".join(current))
                current, current_len = [], 0
            # Split long paragraph by sentences
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
