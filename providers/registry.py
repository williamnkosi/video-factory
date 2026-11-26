"""Provider registry resolving concrete TTS and Image adapters by name."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from providers.base import ImageProvider, TTSProvider
from providers.image.gemini import GeminiImageProvider
from providers.image.mock import MockImageProvider
from providers.tts.gemini import GeminiTTSProvider
from providers.tts.mock import MockTTSProvider

TTS_PROVIDERS: tuple[str, ...] = ("gemini", "mock")
IMAGE_PROVIDERS: tuple[str, ...] = ("gemini", "mock")


def get_tts_provider(
    name: str | None = None,
    *,
    voice: str | None = None,
    model: str | None = None,
) -> TTSProvider:
    """Resolve a concrete TTSProvider by name (or VF_TTS_PROVIDER env var)."""
    load_dotenv()
    provider_name = (name or os.getenv("VF_TTS_PROVIDER") or "gemini").strip().lower()

    if provider_name == "gemini":
        return GeminiTTSProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=model or os.getenv("VF_GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
            default_voice=voice or os.getenv("VF_GEMINI_TTS_VOICE", "Charon"),
        )
    if provider_name == "mock":
        return MockTTSProvider()

    raise ValueError(
        f"Unknown TTS provider '{provider_name}'. Supported providers: {', '.join(TTS_PROVIDERS)}"
    )


def get_image_provider(
    name: str | None = None,
    *,
    model: str | None = None,
) -> ImageProvider:
    """Resolve a concrete ImageProvider by name (or VF_IMAGE_PROVIDER env var)."""
    load_dotenv()
    provider_name = (name or os.getenv("VF_IMAGE_PROVIDER") or "gemini").strip().lower()

    if provider_name == "gemini":
        return GeminiImageProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=model or os.getenv("VF_GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
        )
    if provider_name == "mock":
        return MockImageProvider()

    raise ValueError(
        f"Unknown image provider '{provider_name}'. Supported providers: {', '.join(IMAGE_PROVIDERS)}"
    )
