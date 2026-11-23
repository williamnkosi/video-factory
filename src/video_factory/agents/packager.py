"""Stage 6: Packaging agent producing YouTube thumbnail, description, chapters, and export bundle."""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from pydantic import BaseModel

from video_factory.agents.prompts import PACKAGER_SYSTEM_PROMPT
from video_factory.models import (
    AudioTimeline,
    OutlineArtifact,
    PackagingBundle,
    ProjectManifest,
    RenderArtifact,
    VisualPlan,
)
from video_factory.providers.base import LLMProvider
from video_factory.storage import ProjectStore


class _PackagingLLMResponse(BaseModel):
    title_options: list[str]
    selected_title: str
    description_intro: str
    tags: list[str]


def format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS for YouTube chapter markers."""
    total = max(0, round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_chapter_timestamps(audio_timeline: AudioTimeline) -> list[str]:
    """Generate YouTube-compliant chapter timestamps starting at 00:00."""
    lines: list[str] = []
    for idx, ch in enumerate(audio_timeline.chapters):
        ts = "00:00" if idx == 0 else format_timestamp(ch.start_seconds)
        lines.append(f"{ts} — {ch.title}")
    return lines


def _load_serif_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def render_thumbnail(
    base_image_path: Path,
    output_png_path: Path,
    *,
    title: str,
    subtitle: str,
) -> Path:
    """Compose a calm, high-contrast 1280x720 dark painterly YouTube thumbnail."""
    thumb_w, thumb_h = 1280, 720
    with Image.open(base_image_path) as raw:
        img = raw.convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)

    # Darken slightly and add a bottom gradient scrim for legible serif typography
    img = ImageEnhance.Brightness(img).enhance(0.78)
    overlay = Image.new("RGBA", (thumb_w, thumb_h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for y in range(int(thumb_h * 0.35), thumb_h):
        alpha = int(205 * ((y - thumb_h * 0.35) / (thumb_h * 0.65)))
        odraw.line([(0, y), (thumb_w, y)], fill=(8, 7, 10, alpha))

    composed = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(composed)

    title_font = _load_serif_font(62)
    sub_font = _load_serif_font(28)

    # Strip trailing "| ..." suffix from thumbnail display text to keep it clean and punchy
    clean_display_title = title.split("|")[0].split("—")[0].strip()
    wrapped = textwrap.wrap(clean_display_title, width=26)[:3]

    y_cursor = thumb_h - 115 - (len(wrapped) * 74)
    for line in wrapped:
        # Subtle drop shadow
        draw.text((74, y_cursor + 3), line, font=title_font, fill=(0, 0, 0, 220))
        draw.text((70, y_cursor), line, font=title_font, fill=(244, 228, 198, 255))
        y_cursor += 74

    draw.text((72, thumb_h - 86), subtitle[:72].upper(), font=sub_font, fill=(208, 174, 120, 235))

    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    composed.convert("RGB").save(output_png_path, format="PNG")
    return output_png_path


def run_packager_agent(
    manifest: ProjectManifest,
    outline: OutlineArtifact,
    audio_timeline: AudioTimeline,
    visual_plan: VisualPlan,
    render_artifact: RenderArtifact,
    store: ProjectStore,
    llm: LLMProvider,
) -> PackagingBundle:
    """Assemble final local upload bundle in 06_export/ (video, thumbnail, metadata, chapters)."""
    store.export_dir.mkdir(parents=True, exist_ok=True)
    chapters = build_chapter_timestamps(audio_timeline)

    user_prompt = (
        f"Working Title: {outline.working_title}\n"
        f"Editorial Angle: {outline.editorial_angle}\n"
        f"Historical Era: {outline.historical_era}\n"
        f"Actual Runtime: {round(render_artifact.duration_seconds / 60.0, 1)} minutes\n"
        f"Chapters:\n" + "\n".join(chapters)
    )
    meta = llm.generate_structured(
        system_prompt=PACKAGER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=_PackagingLLMResponse,
        temperature=0.6,
        max_tokens=1536,
    )

    # Copy rendered MP4 to 06_export/video.mp4
    src_video = store.root / render_artifact.video_file
    export_video = store.export_dir / "video.mp4"
    shutil.copy2(src_video, export_video)

    # Render 1280x720 thumbnail from the opening scene artwork
    first_scene_img = store.root / (visual_plan.scenes[0].image_file or "")
    thumb_path = store.export_dir / "thumbnail.png"
    render_thumbnail(
        first_scene_img,
        thumb_path,
        title=meta.selected_title,
        subtitle="Sleepy History Documentary • Calm Narration",
    )

    sources_block = (
        "\n\nSources & Further Reading:\n" + "\n".join(f"- {s}" for s in outline.research_sources)
        if outline.research_sources
        else ""
    )
    full_description = (
        f"{meta.description_intro.strip()}\n\n"
        "Chapters:\n"
        + "\n".join(chapters)
        + sources_block
        + "\n\n---\n"
        "Crafted for quiet evenings, deep focus, and restful sleep.\n"
    )

    (store.export_dir / "youtube_description.txt").write_text(full_description, encoding="utf-8")

    ai_guidance = (
        "YouTube AI Disclosure Checklist: If you used stylized painterly artwork and AI-assisted scripting/TTS "
        "without depicting realistic fabricated real-world footage or cloning a real person's voice, "
        "standard stylized illustrations generally do not require the photorealistic synthetic-media label. "
        "However, review your generated scenes before upload—if any image looks photorealistic of a real event/place, "
        "enable 'Altered or synthetic content' in YouTube Studio."
    )

    return PackagingBundle(
        export_video_file=store.relative_str(export_video),
        thumbnail_file=store.relative_str(thumb_path),
        title_options=meta.title_options,
        selected_title=meta.selected_title,
        description=full_description,
        tags=meta.tags,
        chapter_timestamps=chapters,
        ai_disclosure_guidance=ai_guidance,
    )
