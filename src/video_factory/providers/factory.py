"""Provider factory resolving LLM, TTS, and Image adapters from config."""

from __future__ import annotations

from dataclasses import dataclass

from video_factory.config import Settings
from video_factory.models import ProviderConfig
from video_factory.providers.base import ImageProvider, LLMProvider, TTSProvider
from video_factory.providers.gemini import (
    GeminiImageProvider,
    GeminiLLMProvider,
    GeminiTTSProvider,
)
from video_factory.providers.mock import (
    MockImageProvider,
    MockLLMProvider,
    MockTTSProvider,
)
from video_factory.providers.openai_provider import (
    OpenAIImageProvider,
    OpenAILLMProvider,
    OpenAITTSProvider,
)


@dataclass
class ProviderBundle:
    llm: LLMProvider
    tts: TTSProvider
    image: ImageProvider


def build_providers(
    settings: Settings,
    provider_config: ProviderConfig | None = None,
) -> ProviderBundle:
    """Instantiate configured LLM, TTS, and Image providers."""
    cfg = provider_config or ProviderConfig(
        llm=settings.llm_provider,
        tts=settings.tts_provider,
        image=settings.image_provider,
    )

    if cfg.llm == "gemini":
        llm: LLMProvider = GeminiLLMProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_llm_model,
        )
    elif cfg.llm == "openai":
        llm = OpenAILLMProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_llm_model,
        )
    else:
        llm = MockLLMProvider()

    if cfg.tts == "gemini":
        tts: TTSProvider = GeminiTTSProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_tts_model,
            voice_name=settings.gemini_tts_voice,
        )
    elif cfg.tts == "openai":
        tts = OpenAITTSProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_tts_model,
            voice=settings.openai_tts_voice,
        )
    else:
        tts = MockTTSProvider()

    if cfg.image == "gemini":
        image: ImageProvider = GeminiImageProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_image_model,
        )
    elif cfg.image == "openai":
        image = OpenAIImageProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_image_model,
        )
    else:
        image = MockImageProvider()

    return ProviderBundle(llm=llm, tts=tts, image=image)
