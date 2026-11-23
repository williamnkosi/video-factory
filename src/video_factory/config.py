"""Application configuration loaded from environment and .env files."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["gemini", "openai", "mock"]
AmbienceMode = Literal["brown_noise", "soft_rain", "none"]


class Settings(BaseSettings):
    """Runtime settings for the Sleepy History video factory."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider selection (can be mixed & matched independently)
    llm_provider: ProviderName = Field(default="gemini", alias="VF_LLM_PROVIDER")
    tts_provider: ProviderName = Field(default="openai", alias="VF_TTS_PROVIDER")
    image_provider: ProviderName = Field(default="gemini", alias="VF_IMAGE_PROVIDER")

    # API Keys (standard names so existing environment variables work seamlessly)
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # Gemini models
    gemini_llm_model: str = Field(default="gemini-2.5-flash", alias="VF_GEMINI_LLM_MODEL")
    gemini_image_model: str = Field(
        default="imagen-3.0-generate-002", alias="VF_GEMINI_IMAGE_MODEL"
    )
    gemini_tts_model: str = Field(
        default="gemini-2.5-flash-preview-tts", alias="VF_GEMINI_TTS_MODEL"
    )
    gemini_tts_voice: str = Field(default="Enceladus", alias="VF_GEMINI_TTS_VOICE")

    # OpenAI models
    openai_llm_model: str = Field(default="gpt-4.1-mini", alias="VF_OPENAI_LLM_MODEL")
    openai_image_model: str = Field(default="gpt-image-1", alias="VF_OPENAI_IMAGE_MODEL")
    openai_tts_model: str = Field(default="gpt-4o-mini-tts", alias="VF_OPENAI_TTS_MODEL")
    openai_tts_voice: str = Field(default="onyx", alias="VF_OPENAI_TTS_VOICE")

    # Sleep documentary pacing & production defaults (MVP: 15-30 min)
    default_target_minutes: int = Field(default=20, alias="VF_DEFAULT_TARGET_MINUTES")
    words_per_minute: int = Field(default=130, alias="VF_WORDS_PER_MINUTE")
    seconds_per_scene: int = Field(default=40, alias="VF_SECONDS_PER_SCENE")
    chapter_pause_seconds: float = Field(default=3.0, alias="VF_CHAPTER_PAUSE_SECONDS")
    intro_silence_seconds: float = Field(default=2.0, alias="VF_INTRO_SILENCE_SECONDS")
    outro_silence_seconds: float = Field(default=4.0, alias="VF_OUTRO_SILENCE_SECONDS")

    # Video rendering settings
    video_width: int = Field(default=1920, alias="VF_VIDEO_WIDTH")
    video_height: int = Field(default=1080, alias="VF_VIDEO_HEIGHT")
    video_fps: int = Field(default=24, alias="VF_VIDEO_FPS")
    crossfade_seconds: float = Field(default=2.0, alias="VF_CROSSFADE_SECONDS")

    # Audio mastering & sleep ambience
    ambience_mode: AmbienceMode = Field(default="brown_noise", alias="VF_AMBIENCE_MODE")
    ambience_volume_db: float = Field(default=-28.0, alias="VF_AMBIENCE_VOLUME_DB")
    enable_sleep_dimming: bool = Field(default=True, alias="VF_ENABLE_SLEEP_DIMMING")
    dim_start_fraction: float = Field(default=0.5, alias="VF_DIM_START_FRACTION")
    dim_max_darken: float = Field(default=0.35, alias="VF_DIM_MAX_DARKEN")

    # Wikipedia research grounding toggle
    enable_wikipedia_grounding: bool = Field(default=True, alias="VF_ENABLE_WIKIPEDIA")

    # Output workspace
    runs_dir: Path = Field(default=Path("runs"), alias="VF_RUNS_DIR")

    def resolve_runs_dir(self) -> Path:
        return self.runs_dir.resolve()
