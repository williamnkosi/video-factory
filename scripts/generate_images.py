#!/usr/bin/env python3
"""Script 2: Generate 16:9 scene PNGs from 04_visuals/visual_plan.json via ImageProvider."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from providers.registry import IMAGE_PROVIDERS, get_image_provider


def run(
    run_dir: Path,
    *,
    provider_name: str | None = None,
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

    image_provider = get_image_provider(provider_name)
    generated = 0

    for scene in scenes:
        scene_id = scene["scene_id"]
        out_png = visuals_dir / f"{scene_id}.png"
        should_gen = (
            (only_scene is not None and scene_id == only_scene)
            or (only_scene is None and (force or not out_png.exists()))
        )
        if should_gen:
            print(f"[images] Generating {scene_id} -> {out_png.relative_to(run_root)}")
            image_provider.generate_image(
                prompt=scene["image_prompt"],
                output_png_path=out_png,
                width=width,
                height=height,
            )
            generated += 1
        if out_png.exists():
            scene["image_file"] = out_png.relative_to(run_root).as_posix()

    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(f"[images] Done ({generated} generated, {len(scenes)} total scenes in visual_plan.json)")
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate 16:9 scene images from visual_plan.json.")
    parser.add_argument("run_dir", type=Path, help="Path to runs/<slug> directory.")
    parser.add_argument("--provider", choices=IMAGE_PROVIDERS, default=None, help="Image provider override.")
    parser.add_argument("--scene", default=None, help="Regenerate only this scene_id (e.g. scene_004).")
    parser.add_argument("--force", action="store_true", help="Regenerate all scene PNGs.")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()

    run(
        args.run_dir,
        provider_name=args.provider,
        only_scene=args.scene,
        force=args.force,
        width=args.width,
        height=args.height,
    )


if __name__ == "__main__":
    main()
