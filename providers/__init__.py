"""Pluggable TTS, Image, and Video provider layer shared by media scripts."""

from providers.base import ImageProvider, TTSProvider, VideoProvider
from providers.registry import get_image_provider, get_tts_provider, get_video_provider

__all__ = [
    "ImageProvider",
    "TTSProvider",
    "VideoProvider",
    "get_image_provider",
    "get_tts_provider",
    "get_video_provider",
]
