#!/usr/bin/env python3
"""Script 2: Generate 16:9 scene PNGs (and optional hero MP4 clips) from 04_visuals/visual_plan.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from providers.registry import (
    IMAGE_PROVIDERS,
    VIDEO_PROVIDERS,
    get_image_provider,
    get_video_provider,
)


def run(
    run_dir: Path,
    *,
    provider_name: str | None = None,
    video_provider_name: str | None = "none",
    only_scene: str | None = None,
    force: bool = False,
    width: int = 1920,
    height: int = 1080,
) -> dict:
    run_root = run_dir.resolve()
    visuals_dir = run_root / "04_visuals"
    plan_path = visuals_dir / "visual_plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Missing visual plan: {plan_path}")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    scenes = plan.get("scenes", [])
    if not scenes:
        raise ValueError(f"No scenes found in {plan_path}")

    if only_scene and not any(s.get("scene_id") == only_scene for s in scenes):
        raise ValueError(f"Scene '{only_scene}' not found in {plan_path}")

    image_provider = None
    video_provider = None
    generated_images = 0
    generated_videos = 0

    use_video = video_provider_name is not None and video_provider_name.strip().lower() != "none"

    for scene in scenes:
        scene_id = scene["scene_id"]
        media_type = (scene.get("media_type") or "image").strip().lower()

        if only_scene is not None and scene_id != only_scene:
            continue

        # Animated map scenes are rendered programmatically during Stage 5 unless an image_prompt exists
        if media_type == "map" and not scene.get("image_prompt"):
            continue

        out_png = visuals_dir / f"{scene_id}.png"
        should_gen_img = force or not out_png.exists() or (only_scene == scene_id)
        if should_gen_img and scene.get("image_prompt"):
            if image_provider is None:
                image_provider = get_image_provider(provider_name)
            print(f"[images] Generating {scene_id} -> {out_png.relative_to(run_root)}")
            image_provider.generate_image(
                prompt=scene["image_prompt"],
                output_png_path=out_png,
                width=width,
                height=height,
            )
            generated_images += 1
        if out_png.exists():
            scene["image_file"] = out_png.relative_to(run_root).as_posix()

        # Optional Image-to-Video animation for hero scenes tagged media_type="video"
        if media_type == "video" and use_video:
            out_mp4 = visuals_dir / f"{scene_id}.mp4"
            should_gen_vid = force or not out_mp4.exists() or (only_scene == scene_id)
            if should_gen_vid:
                if video_provider is None:
                    video_provider = get_video_provider(video_provider_name)
                motion_prompt = (
                    scene.get("motion_prompt")
                    or scene.get("image_prompt")
                    or "Subtle cinematic documentary motion, slow camera drift, gentle atmospheric light."
                )
                clip_len = int(scene.get("video_duration_seconds", 8))
                print(
                    f"[video] Animating hero {scene_id} ({clip_len}s) -> {out_mp4.relative_to(run_root)}"
                )
                video_provider.generate_video(
                    prompt=motion_prompt,
                    output_mp4_path=out_mp4,
                    image_path=out_png if out_png.exists() else None,
                    duration_seconds=clip_len,
                    width=width,
                    height=height,
                )
                generated_videos += 1
            if out_mp4.exists():
                scene["video_file"] = out_mp4.relative_to(run_root).as_posix()

    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(
        f"[images] Done ({generated_images} images, {generated_videos} hero videos generated; "
        f"{len(scenes)} total scenes in visual_plan.json)"
    )
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate 16:9 scene images (and optional hero video clips) from visual_plan.json."
    )
    parser.add_argument("run_dir", type=Path, help="Path to runs/<slug> directory.")
    parser.add_argument(
        "--provider",
        choices=IMAGE_PROVIDERS,
        default=None,
        help="Image provider override.",
    )
    parser.add_argument(
        "--video-provider",
        choices=(*VIDEO_PROVIDERS, "none"),
        default="none",
        help="Optional video provider for scenes with media_type='video' (default: none).",
    )
    parser.add_argument(
        "--scene",
        default=None,
        help="Regenerate only this scene_id (e.g. scene_004).",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate all scene media.")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()

    run(
        args.run_dir,
        provider_name=args.provider,
        video_provider_name=args.video_provider,
        only_scene=args.scene,
        force=args.force,
        width=args.width,
        height=args.height,
    )


if __name__ == "__main__":
    main()
