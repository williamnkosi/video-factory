"""Core Pydantic data models for pipeline state and stage artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class StageName(StrEnum):
    """Ordered pipeline stages from prompt to ready-to-upload bundle."""

    OUTLINE = "outline"
    SCRIPT = "script"
    AUDIO = "audio"
    VISUALS = "visuals"
    RENDER = "render"
    PACKAGE = "package"


STAGE_ORDER: list[StageName] = [
    StageName.OUTLINE,
    StageName.SCRIPT,
    StageName.AUDIO,
    StageName.VISUALS,
    StageName.RENDER,
    StageName.PACKAGE,
]


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StageRecord(BaseModel):
    status: StageStatus = StageStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    notes: str | None = None


class ProviderConfig(BaseModel):
    llm: Literal["gemini", "openai", "mock"] = "gemini"
    tts: Literal["gemini", "openai", "mock"] = "openai"
    image: Literal["gemini", "openai", "mock"] = "gemini"


class ProjectManifest(BaseModel):
    """Master project state saved at runs/<slug>/manifest.json."""

    project_id: str
    slug: str
    description: str
    target_minutes: int = 20
    words_per_minute: int = 130
    seconds_per_scene: int = 40
    channel_style: str = "sleepy_history"
    ambience_mode: Literal["brown_noise", "soft_rain", "none"] = "brown_noise"
    enable_sleep_dimming: bool = True
    providers: ProviderConfig = Field(default_factory=ProviderConfig)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stages: dict[StageName, StageRecord] = Field(
        default_factory=lambda: {stage: StageRecord() for stage in STAGE_ORDER}
    )

    def mark_stage(
        self,
        stage: StageName,
        status: StageStatus,
        *,
        error: str | None = None,
        notes: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        rec = self.stages[stage]
        rec.status = status
        if status == StageStatus.RUNNING:
            rec.started_at = now
            rec.error = None
        elif status == StageStatus.COMPLETED:
            rec.completed_at = now
            rec.error = None
        elif status == StageStatus.FAILED:
            rec.error = error
        if notes is not None:
            rec.notes = notes
        self.updated_at = now


# --- Stage 1: Outline & Research Bible ---


class ChapterOutline(BaseModel):
    chapter_number: int
    title: str
    summary: str
    key_historical_facts: list[str]
    sensory_details: list[str]
    energy_level: Literal["gentle_opening", "calm_immersion", "deep_drifting", "soft_winding_down"]
    target_words: int


class OutlineArtifact(BaseModel):
    working_title: str
    subtitle_hook: str
    historical_era: str
    geographic_setting: str
    editorial_angle: str
    narrator_tone_notes: str
    visual_palette_notes: str
    research_sources: list[str] = Field(default_factory=list)
    chapters: list[ChapterOutline]


# --- Stage 2: Scripts ---


class ChapterScript(BaseModel):
    chapter_number: int
    title: str
    raw_text: str
    edited_text: str
    word_count: int
    critic_notes: list[str] = Field(default_factory=list)
    markdown_file: str


class ScriptBundle(BaseModel):
    total_words: int
    estimated_minutes: float
    chapters: list[ChapterScript]


# --- Stage 3: Audio & Timeline ---


class ChapterAudioTiming(BaseModel):
    chapter_number: int
    title: str
    raw_audio_file: str
    master_audio_file: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float


class AudioTimeline(BaseModel):
    master_audio_file: str
    ambient_bed_file: str | None = None
    total_duration_seconds: float
    chapters: list[ChapterAudioTiming]


# --- Stage 4: Visual Plan & Scenes ---


class SceneSpec(BaseModel):
    scene_id: str
    index: int
    chapter_number: int
    start_seconds: float
    duration_seconds: float
    narration_excerpt: str
    image_prompt: str
    motion: Literal["zoom_in", "zoom_out", "pan_left", "pan_right"] = "zoom_in"
    image_file: str | None = None


class VisualPlan(BaseModel):
    style_bible: str
    scenes: list[SceneSpec]


# --- Stage 5: Render ---


class RenderArtifact(BaseModel):
    video_file: str
    width: int
    height: int
    fps: int
    duration_seconds: float
    file_size_bytes: int


# --- Stage 6: Packaging ---


class PackagingBundle(BaseModel):
    export_video_file: str
    thumbnail_file: str
    title_options: list[str]
    selected_title: str
    description: str
    tags: list[str]
    chapter_timestamps: list[str]
    ai_disclosure_guidance: str
