"""Provider registry resolving concrete TTS, Image, and Video adapters by name."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from providers.base import ImageProvider, TTSProvider, VideoProvider
from providers.image.gemini import GeminiImageProvider
from providers.image.mock import MockImageProvider
from providers.tts.gemini import GeminiTTSProvider
from providers.tts.mock import MockTTSProvider
from providers.video.mock import MockVideoProvider
from providers.video.veo import VeoVideoProvider

TTS_PROVIDERS: tuple[str, ...] = ("gemini", "mock")
IMAGE_PROVIDERS: tuple[str, ...] = ("gemini", "mock")
VIDEO_PROVIDERS: tuple[str, ...] = ("veo", "mock")


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


def get_video_provider(
    name: str | None = None,
    *,
    model: str | None = None,
) -> VideoProvider:
    """Resolve a concrete VideoProvider by name (or VF_VIDEO_PROVIDER env var)."""
    load_dotenv()
    provider_name = (name or os.getenv("VF_VIDEO_PROVIDER") or "veo").strip().lower()

    if provider_name == "veo":
        return VeoVideoProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=model or os.getenv("VF_GEMINI_VIDEO_MODEL", "veo-3.0-generate-001"),
        )
    if provider_name == "mock":
        return MockVideoProvider()

    raise ValueError(
        f"Unknown video provider '{provider_name}'. Supported providers: {', '.join(VIDEO_PROVIDERS)}"
    )
