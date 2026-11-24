"""Pluggable TTS and Image provider layer shared by media scripts."""

from providers.base import ImageProvider, TTSProvider
from providers.registry import get_image_provider, get_tts_provider

__all__ = [
    "ImageProvider",
    "TTSProvider",
    "get_image_provider",
    "get_tts_provider",
]
