"""Filesystem-backed checkpoint storage and project directory management."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from video_factory.models import (
    AudioTimeline,
    OutlineArtifact,
    PackagingBundle,
    ProjectManifest,
    ProviderConfig,
    RenderArtifact,
    ScriptBundle,
    VisualPlan,
)

T = TypeVar("T", bound=BaseModel)


def slugify(text: str, max_len: int = 48) -> str:
    """Create a clean filesystem-safe slug from a description."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower()).strip()
    slug = re.sub(r"[\s_-]+", "-", cleaned)[:max_len].strip("-")
    return slug or "sleepy-history"


class ProjectStore:
    """Manages stage artifacts and atomic manifest persistence for a single run."""

    def __init__(self, project_dir: Path) -> None:
        self.root = project_dir.resolve()

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def outline_path(self) -> Path:
        return self.root / "01_outline.json"

    @property
    def script_dir(self) -> Path:
        return self.root / "02_script"

    @property
    def script_bundle_path(self) -> Path:
        return self.script_dir / "script_bundle.json"

    @property
    def audio_dir(self) -> Path:
        return self.root / "03_audio"

    @property
    def audio_timeline_path(self) -> Path:
        return self.audio_dir / "audio_timeline.json"

    @property
    def visuals_dir(self) -> Path:
        return self.root / "04_visuals"

    @property
    def visual_plan_path(self) -> Path:
        return self.visuals_dir / "visual_plan.json"

    @property
    def render_dir(self) -> Path:
        return self.root / "05_render"

    @property
    def render_artifact_path(self) -> Path:
        return self.render_dir / "render_artifact.json"

    @property
    def export_dir(self) -> Path:
        return self.root / "06_export"

    @property
    def packaging_path(self) -> Path:
        return self.export_dir / "youtube_metadata.json"

    def ensure_dirs(self) -> None:
        for path in [
            self.root,
            self.script_dir,
            self.audio_dir,
            self.visuals_dir,
            self.render_dir,
            self.export_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _write_json(path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)

    def save_model(self, path: Path, model: BaseModel) -> None:
        self._write_json(path, model.model_dump_json(indent=2))

    def load_model(self, path: Path, model_cls: type[T]) -> T:
        raw = path.read_text(encoding="utf-8")
        return model_cls.model_validate_json(raw)

    # Convenience typed accessors
    def save_manifest(self, manifest: ProjectManifest) -> None:
        self.save_model(self.manifest_path, manifest)

    def load_manifest(self) -> ProjectManifest:
        return self.load_model(self.manifest_path, ProjectManifest)

    def save_outline(self, outline: OutlineArtifact) -> None:
        self.save_model(self.outline_path, outline)

    def load_outline(self) -> OutlineArtifact:
        return self.load_model(self.outline_path, OutlineArtifact)

    def save_script_bundle(self, bundle: ScriptBundle) -> None:
        self.save_model(self.script_bundle_path, bundle)

    def load_script_bundle(self) -> ScriptBundle:
        """Load script bundle, automatically incorporating manual edits to chapter markdown files."""
        bundle = self.load_model(self.script_bundle_path, ScriptBundle)
        total_words = 0
        for chapter in bundle.chapters:
            md_path = self.root / chapter.markdown_file
            if md_path.exists():
                text = _strip_markdown_header(md_path.read_text(encoding="utf-8"))
                if text.strip():
                    chapter.edited_text = text.strip()
                    chapter.word_count = len(chapter.edited_text.split())
            total_words += chapter.word_count
        bundle.total_words = total_words
        return bundle

    def save_audio_timeline(self, timeline: AudioTimeline) -> None:
        self.save_model(self.audio_timeline_path, timeline)

    def load_audio_timeline(self) -> AudioTimeline:
        return self.load_model(self.audio_timeline_path, AudioTimeline)

    def save_visual_plan(self, plan: VisualPlan) -> None:
        self.save_model(self.visual_plan_path, plan)

    def load_visual_plan(self) -> VisualPlan:
        return self.load_model(self.visual_plan_path, VisualPlan)

    def save_render_artifact(self, artifact: RenderArtifact) -> None:
        self.save_model(self.render_artifact_path, artifact)

    def load_render_artifact(self) -> RenderArtifact:
        return self.load_model(self.render_artifact_path, RenderArtifact)

    def save_packaging(self, bundle: PackagingBundle) -> None:
        self.save_model(self.packaging_path, bundle)

    def load_packaging(self) -> PackagingBundle:
        return self.load_model(self.packaging_path, PackagingBundle)

    def relative_str(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()


def _strip_markdown_header(content: str) -> str:
    """Strip leading '# Chapter N: Title' header when reading human-edited chapter markdown."""
    lines = content.splitlines()
    idx = 0
    while idx < len(lines) and (lines[idx].startswith("#") or not lines[idx].strip()):
        idx += 1
    return "\n".join(lines[idx:]).strip()


def create_project(
    runs_dir: Path,
    description: str,
    *,
    slug: str | None = None,
    target_minutes: int = 20,
    words_per_minute: int = 130,
    seconds_per_scene: int = 40,
    ambience_mode: str = "brown_noise",
    enable_sleep_dimming: bool = True,
    providers: ProviderConfig | None = None,
) -> tuple[ProjectStore, ProjectManifest]:
    """Initialize a new run directory and save its initial manifest."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    base_slug = slugify(slug or description)
    candidate = base_slug
    suffix = 2
    while (runs_dir / candidate).exists():
        candidate = f"{base_slug}-{suffix}"
        suffix += 1

    store = ProjectStore(runs_dir / candidate)
    store.ensure_dirs()
    manifest = ProjectManifest(
        project_id=uuid.uuid4().hex[:12],
        slug=candidate,
        description=description.strip(),
        target_minutes=target_minutes,
        words_per_minute=words_per_minute,
        seconds_per_scene=seconds_per_scene,
        ambience_mode=ambience_mode,  # type: ignore[arg-type]
        enable_sleep_dimming=enable_sleep_dimming,
        providers=providers or ProviderConfig(),
    )
    store.save_manifest(manifest)
    return store, manifest


def list_projects(runs_dir: Path) -> list[ProjectManifest]:
    """Return all saved project manifests sorted newest-first."""
    if not runs_dir.exists():
        return []
    manifests: list[ProjectManifest] = []
    for entry in sorted(runs_dir.iterdir()):
        manifest_file = entry / "manifest.json"
        if manifest_file.is_file():
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
                manifests.append(ProjectManifest.model_validate(data))
            except (OSError, ValueError):
                # Skip malformed or unreadable project directories
                pass
    manifests.sort(key=lambda m: m.updated_at, reverse=True)
    return manifests
