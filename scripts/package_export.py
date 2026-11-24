#!/usr/bin/env python3
"""Script 4: Compose 1280x720 thumbnail, finalize chapters/description, and assemble 06_export/."""

from __future__ import annotations

import argparse
import json
import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


def format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS for YouTube chapter markers."""
    total = max(0, round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_chapter_lines(audio_timeline: dict) -> list[str]:
    lines: list[str] = []
    for idx, ch in enumerate(audio_timeline.get("chapters", [])):
        ts = "00:00" if idx == 0 else format_timestamp(float(ch.get("start_seconds", 0.0)))
        lines.append(f"{ts} — {ch.get('title', f'Chapter {idx + 1}')}")
    return lines


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def render_thumbnail(base_image_path: Path, output_png_path: Path, *, headline: str) -> Path:
    """Compose a clean 1280x720 thumbnail with a bottom scrim and high-contrast typography."""
    thumb_w, thumb_h = 1280, 720
    with Image.open(base_image_path) as raw:
        img = raw.convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)

    img = ImageEnhance.Brightness(img).enhance(0.84)
    overlay = Image.new("RGBA", (thumb_w, thumb_h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    scrim_start = int(thumb_h * 0.35)
    for y in range(scrim_start, thumb_h):
        alpha = int(210 * ((y - scrim_start) / (thumb_h - scrim_start)))
        odraw.line([(0, y), (thumb_w, y)], fill=(8, 10, 14, alpha))

    composed = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(composed)

    font = _load_font(66)
    wrapped = textwrap.wrap(headline.strip(), width=24)[:3]
    y_cursor = thumb_h - 80 - (len(wrapped) * 78)
    for line in wrapped:
        draw.text((74, y_cursor + 3), line, font=font, fill=(0, 0, 0, 225))
        draw.text((70, y_cursor), line, font=font, fill=(246, 240, 226, 255))
        y_cursor += 78

    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    composed.convert("RGB").save(output_png_path, format="PNG")
    return output_png_path


def run(run_dir: Path, *, thumbnail_scene: str | None = None) -> dict:
    run_root = run_dir.resolve()
    render_mp4 = run_root / "05_render" / "final_video.mp4"
    timeline_path = run_root / "03_audio" / "audio_timeline.json"
    plan_path = run_root / "04_visuals" / "visual_plan.json"
    export_dir = run_root / "06_export"
    export_dir.mkdir(parents=True, exist_ok=True)

    if not render_mp4.exists():
        raise FileNotFoundError(f"Missing rendered video: {render_mp4}")

    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    meta_path = export_dir / "metadata.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    # 1) Copy final video into 06_export/video.mp4
    export_video = export_dir / "video.mp4"
    shutil.copy2(render_mp4, export_video)

    # 2) Pick scene image and compose 1280x720 thumbnail.png
    scenes = plan.get("scenes", [])
    chosen_scene = None
    if thumbnail_scene:
        chosen_scene = next((s for s in scenes if s.get("scene_id") == thumbnail_scene), None)
    if chosen_scene is None and scenes:
        chosen_scene = scenes[0]
    if chosen_scene is None:
        raise ValueError("Cannot generate thumbnail: no scenes in visual_plan.json")

    base_img = run_root / (chosen_scene.get("image_file") or f"04_visuals/{chosen_scene['scene_id']}.png")
    headline = (
        metadata.get("thumbnail_text")
        or metadata.get("selected_title")
        or run_root.name.replace("-", " ").title()
    )
    thumb_path = export_dir / "thumbnail.png"
    render_thumbnail(base_img, thumb_path, headline=headline)

    # 3) Build exact 00:00 chapters and write description.txt
    chapter_lines = build_chapter_lines(timeline)
    intro = (metadata.get("description_intro") or "").strip()
    parts: list[str] = []
    if intro:
        parts.append(intro)
    if chapter_lines:
        parts.append("Chapters:\n" + "\n".join(chapter_lines))

    outline_path = run_root / "01_outline.json"
    if outline_path.exists():
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
        sources = outline.get("sources") or outline.get("research_sources") or []
        if sources:
            parts.append("Sources:\n" + "\n".join(f"- {s}" for s in sources))

    description_text = "\n\n".join(parts) + "\n"
    desc_path = export_dir / "description.txt"
    desc_path.write_text(description_text, encoding="utf-8")

    # 4) Finalize metadata.json with exact export paths and verified chapters
    metadata["export_video_file"] = export_video.relative_to(run_root).as_posix()
    metadata["thumbnail_file"] = thumb_path.relative_to(run_root).as_posix()
    metadata["description_file"] = desc_path.relative_to(run_root).as_posix()
    metadata["chapter_markers"] = chapter_lines
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(
        f"[package] Export bundle ready in {export_dir.relative_to(run_root)}/: "
        "video.mp4, thumbnail.png, description.txt, metadata.json"
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Package final video, thumbnail, and description into 06_export/.")
    parser.add_argument("run_dir", type=Path, help="Path to runs/<slug> directory.")
    parser.add_argument("--thumbnail-scene", default=None, help="Scene ID to use as thumbnail background.")
    args = parser.parse_args()
    run(args.run_dir, thumbnail_scene=args.thumbnail_scene)


if __name__ == "__main__":
    main()
