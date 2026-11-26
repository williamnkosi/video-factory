#!/usr/bin/env python3
"""Script 3: Deterministic FFmpeg hybrid documentary renderer (video clips, images, maps, overlays)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.doc_graphics import (
    render_animated_map_clip,
    render_callout_overlay,
    render_chapter_card_overlay,
)


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(proc.stdout)["format"]["duration"])


def _compute_dim_offset(
    start_s: float,
    dur_s: float,
    total_dur: float,
    *,
    dim_after: float,
    dim_amount: float,
) -> float:
    if dim_amount <= 0.0 or total_dur <= 0.0:
        return 0.0
    midpoint = start_s + (dur_s / 2.0)
    frac = midpoint / total_dur
    if frac <= dim_after:
        return 0.0
    progress = min(1.0, (frac - dim_after) / max(0.01, 1.0 - dim_after))
    return -round(progress * dim_amount, 4)


def _render_image_clip(
    image_path: Path,
    output_mp4: Path,
    *,
    duration: float,
    motion: str,
    width: int,
    height: int,
    fps: int,
    brightness_offset: float,
    film_grain: int,
    preset: str,
) -> Path:
    total_frames = max(2, round(duration * fps))
    up_w = round(width * 1.25)
    up_h = round(height * 1.25)

    if motion == "static":
        vf_parts = [
            f"scale={width}:{height}:force_original_aspect_ratio=increase",
            f"crop={width}:{height}",
        ]
        input_args = ["-loop", "1", "-i", str(image_path)]
    else:
        if motion == "zoom_out":
            zp = (
                f"zoompan=z='1.08-0.08*(on/{total_frames})':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={width}x{height}:fps={fps}"
            )
        elif motion == "pan_left":
            zp = (
                f"zoompan=z='1.08':"
                f"x='(iw-iw/zoom)*(1-on/{total_frames})':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={width}x{height}:fps={fps}"
            )
        elif motion == "pan_right":
            zp = (
                f"zoompan=z='1.08':"
                f"x='(iw-iw/zoom)*(on/{total_frames})':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={width}x{height}:fps={fps}"
            )
        else:  # zoom_in
            zp = (
                f"zoompan=z='1+0.08*(on/{total_frames})':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={width}x{height}:fps={fps}"
            )
        vf_parts = [
            f"scale={up_w}:{up_h}:force_original_aspect_ratio=increase",
            f"crop={up_w}:{up_h}",
            zp,
        ]
        # Single-frame input so zoompan smoothly increments `on` across all frames
        input_args = ["-i", str(image_path)]

    if film_grain > 0:
        vf_parts.append(f"noise=alls={film_grain}:allf=t+u")
    vf_parts.append("vignette=PI/7")
    if brightness_offset < 0.0:
        vf_parts.append(f"eq=brightness={brightness_offset:.4f}")
    vf_parts.append("format=yuv420p")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            *input_args,
            "-vf",
            ",".join(vf_parts),
            "-t",
            f"{duration:.3f}",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            "20",
            "-an",
            str(output_mp4),
        ],
        check=True,
        capture_output=True,
    )
    return output_mp4


def _render_video_clip(
    video_path: Path,
    output_mp4: Path,
    *,
    duration: float,
    width: int,
    height: int,
    fps: int,
    brightness_offset: float,
    preset: str,
) -> Path:
    """Conform a generated hero MP4 clip (looping seamlessly if shorter than scene span)."""
    vf_parts = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        f"fps={fps}",
    ]
    if brightness_offset < 0.0:
        vf_parts.append(f"eq=brightness={brightness_offset:.4f}")
    vf_parts.append("format=yuv420p")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(video_path),
            "-vf",
            ",".join(vf_parts),
            "-t",
            f"{duration:.3f}",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            "20",
            "-an",
            str(output_mp4),
        ],
        check=True,
        capture_output=True,
    )
    return output_mp4


def _apply_documentary_overlays(
    clip_mp4: Path,
    output_mp4: Path,
    *,
    scene: dict,
    clip_duration: float,
    work_dir: Path,
    width: int,
    height: int,
    fps: int,
    preset: str,
) -> Path:
    """Composite optional animated chapter_card and/or lower-third callout overlays onto a clip."""
    chapter_card = scene.get("chapter_card")
    callout = scene.get("callout")
    if not chapter_card and not callout:
        return clip_mp4

    overlays: list[tuple[Path, float, float]] = []
    scene_id = scene["scene_id"]

    if isinstance(chapter_card, dict) and chapter_card.get("title"):
        card_png = work_dir / f"{scene_id}_chapter_card.png"
        render_chapter_card_overlay(
            card_png,
            width=width,
            height=height,
            chapter_number=int(chapter_card.get("chapter_number", scene.get("chapter_number", 1))),
            title=str(chapter_card["title"]),
            subtitle=chapter_card.get("subtitle"),
        )
        start_s = float(chapter_card.get("start", 0.35))
        end_s = min(clip_duration - 0.3, float(chapter_card.get("end", 4.4)))
        if end_s > start_s + 0.6:
            overlays.append((card_png, start_s, end_s))

    if isinstance(callout, dict) and callout.get("location"):
        call_png = work_dir / f"{scene_id}_callout.png"
        render_callout_overlay(
            call_png,
            width=width,
            height=height,
            location=str(callout["location"]),
            era=callout.get("era"),
            caption=callout.get("caption"),
        )
        default_start = 4.8 if overlays else 0.7
        start_s = float(callout.get("start", default_start))
        end_s = min(clip_duration - 0.3, float(callout.get("end", start_s + 5.6)))
        if end_s > start_s + 0.6:
            overlays.append((call_png, start_s, end_s))

    if not overlays:
        return clip_mp4

    cmd = ["ffmpeg", "-y", "-i", str(clip_mp4)]
    for png_path, _, _ in overlays:
        cmd.extend(["-loop", "1", "-t", f"{clip_duration:.3f}", "-i", str(png_path)])

    filter_parts: list[str] = []
    current_label = "[0:v]"
    for idx, (_, start_s, end_s) in enumerate(overlays, start=1):
        fade_in = min(0.45, (end_s - start_s) / 4.0)
        fade_out = min(0.55, (end_s - start_s) / 4.0)
        fade_out_st = max(start_s, end_s - fade_out)
        ov_label = f"[ov{idx}]"
        out_label = f"[v{idx}]"
        filter_parts.append(
            f"[{idx}:v]format=rgba,"
            f"fade=t=in:st={start_s:.3f}:d={fade_in:.3f}:alpha=1,"
            f"fade=t=out:st={fade_out_st:.3f}:d={fade_out:.3f}:alpha=1{ov_label}"
        )
        filter_parts.append(
            f"{current_label}{ov_label}overlay=0:0:shortest=1:format=auto{out_label}"
        )
        current_label = out_label

    filter_parts.append(f"{current_label}format=yuv420p[vfinal]")
    cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[vfinal]",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            "20",
            "-an",
            str(output_mp4),
        ]
    )
    subprocess.run(cmd, check=True, capture_output=True)
    return output_mp4


def _xfade_batch(
    clips: list[Path],
    output_mp4: Path,
    *,
    crossfade: float,
    fps: int,
    preset: str,
) -> Path:
    if len(clips) == 1:
        output_mp4.write_bytes(clips[0].read_bytes())
        return output_mp4

    durations = [probe_duration(c) for c in clips]
    cmd = ["ffmpeg", "-y"]
    for clip in clips:
        cmd.extend(["-i", str(clip)])

    filter_parts: list[str] = []
    for idx in range(len(clips)):
        filter_parts.append(f"[{idx}:v]settb=AVTB,fps={fps},format=yuv420p[v{idx}]")

    acc_dur = durations[0]
    prev_label = "[v0]"
    for idx in range(1, len(clips)):
        eff_xfade = min(crossfade, max(0.2, min(acc_dur, durations[idx]) / 3.0))
        offset = max(0.0, acc_dur - eff_xfade)
        out_label = f"[x{idx}]"
        filter_parts.append(
            f"{prev_label}[v{idx}]xfade=transition=fade:duration={eff_xfade:.3f}:offset={offset:.3f}{out_label}"
        )
        prev_label = out_label
        acc_dur = offset + durations[idx]

    cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            prev_label,
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(output_mp4),
        ]
    )
    subprocess.run(cmd, check=True, capture_output=True)
    return output_mp4


def _merge_hierarchical(
    clips: list[Path],
    work_dir: Path,
    *,
    crossfade: float,
    fps: int,
    preset: str,
    batch_size: int = 8,
) -> Path:
    """Merge arbitrary clip counts via hierarchical crossfade batches to keep FFmpeg memory flat."""
    current = clips
    round_num = 0
    while len(current) > 1:
        round_num += 1
        next_level: list[Path] = []
        for b_idx in range(0, len(current), batch_size):
            batch = current[b_idx : b_idx + batch_size]
            out_path = work_dir / f"_merge_r{round_num}_b{b_idx // batch_size:02d}.mp4"
            next_level.append(
                _xfade_batch(batch, out_path, crossfade=crossfade, fps=fps, preset=preset)
            )
        current = next_level
    return current[0]


def run(
    run_dir: Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    crossfade: float = 1.2,
    dim_after: float = 0.5,
    dim_amount: float = 0.0,
    film_grain: int = 3,
    preset: str = "veryfast",
) -> dict:
    run_root = run_dir.resolve()
    master_audio = run_root / "03_audio" / "narration_master.wav"
    plan_path = run_root / "04_visuals" / "visual_plan.json"
    render_dir = run_root / "05_render"
    clips_dir = render_dir / "_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    if not master_audio.exists():
        raise FileNotFoundError(f"Missing mastered audio: {master_audio}")
    if not plan_path.exists():
        raise FileNotFoundError(f"Missing visual plan: {plan_path}")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    scenes = plan.get("scenes", [])
    if not scenes:
        raise ValueError(f"No scenes found in {plan_path}")

    total_audio_dur = probe_duration(master_audio)

    # Scale scene durations proportionally if audio duration differs from visual_plan's planned total
    planned_total = sum(float(s["duration_seconds"]) for s in scenes)
    scale_factor = (total_audio_dur / planned_total) if planned_total > 0 else 1.0
    effective_durs = [max(1.0, float(s["duration_seconds"]) * scale_factor) for s in scenes]

    safe_xfade = min(crossfade, max(0.2, min(effective_durs) / 3.0))
    rendered_clips: list[Path] = []
    cursor = 0.0

    for idx, (scene, eff_dur) in enumerate(zip(scenes, effective_durs, strict=True)):
        scene_id = scene["scene_id"]
        media_type = (scene.get("media_type") or "image").strip().lower()
        clip_dur = eff_dur + (safe_xfade if idx < len(scenes) - 1 else 0.5)
        raw_clip_path = clips_dir / f"{scene_id}_base.mp4"
        final_clip_path = clips_dir / f"{scene_id}.mp4"
        dim_offset = _compute_dim_offset(
            cursor,
            eff_dur,
            total_audio_dur,
            dim_after=dim_after,
            dim_amount=dim_amount,
        )

        video_rel = scene.get("video_file") or f"04_visuals/{scene_id}.mp4"
        video_path = run_root / video_rel

        if media_type == "map" and isinstance(scene.get("map"), dict):
            print(f"[render] Clip {idx + 1}/{len(scenes)} ({scene_id}, {eff_dur:.1f}s, animated map)")
            render_animated_map_clip(
                scene["map"],
                raw_clip_path,
                duration=clip_dur,
                width=width,
                height=height,
                fps=fps,
                preset=preset,
            )
        elif media_type == "video" and video_path.exists():
            print(f"[render] Clip {idx + 1}/{len(scenes)} ({scene_id}, {eff_dur:.1f}s, hero video)")
            _render_video_clip(
                video_path,
                raw_clip_path,
                duration=clip_dur,
                width=width,
                height=height,
                fps=fps,
                brightness_offset=dim_offset,
                preset=preset,
            )
        else:
            img_rel = scene.get("image_file") or f"04_visuals/{scene_id}.png"
            img_path = run_root / img_rel
            if not img_path.exists():
                raise FileNotFoundError(f"Missing scene image: {img_path}")
            print(
                f"[render] Clip {idx + 1}/{len(scenes)} "
                f"({scene_id}, {eff_dur:.1f}s, {scene.get('motion', 'zoom_in')})"
            )
            _render_image_clip(
                img_path,
                raw_clip_path,
                duration=clip_dur,
                motion=scene.get("motion", "zoom_in"),
                width=width,
                height=height,
                fps=fps,
                brightness_offset=dim_offset,
                film_grain=film_grain,
                preset=preset,
            )

        composited = _apply_documentary_overlays(
            raw_clip_path,
            final_clip_path,
            scene=scene,
            clip_duration=clip_dur,
            work_dir=clips_dir,
            width=width,
            height=height,
            fps=fps,
            preset=preset,
        )
        rendered_clips.append(composited)
        cursor += eff_dur

    print("[render] Crossfading scene clips...")
    merged_video = _merge_hierarchical(
        rendered_clips,
        clips_dir,
        crossfade=safe_xfade,
        fps=fps,
        preset=preset,
    )

    final_mp4 = render_dir / "final_video.mp4"
    fade_in_d = min(1.5, total_audio_dur / 6.0)
    fade_out_d = min(2.5, total_audio_dur / 5.0)
    fade_out_start = max(0.0, total_audio_dur - fade_out_d)

    print("[render] Muxing final H.264 + AAC MP4...")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(merged_video),
            "-i",
            str(master_audio),
            "-vf",
            f"fade=t=in:st=0:d={fade_in_d:.2f},fade=t=out:st={fade_out_start:.3f}:d={fade_out_d:.2f}",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            "19",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(final_mp4),
        ],
        check=True,
        capture_output=True,
    )

    render_info = {
        "video_file": final_mp4.relative_to(run_root).as_posix(),
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": round(probe_duration(final_mp4), 3),
        "file_size_bytes": final_mp4.stat().st_size,
    }
    (render_dir / "render_info.json").write_text(json.dumps(render_info, indent=2) + "\n", encoding="utf-8")
    mb = render_info["file_size_bytes"] / (1024 * 1024)
    print(f"[render] Wrote {render_info['video_file']} ({render_info['duration_seconds']:.2f}s, {mb:.2f} MB)")
    return render_info


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render 1080p hybrid documentary MP4 from scenes, video clips, maps, and mastered audio."
    )
    parser.add_argument("run_dir", type=Path, help="Path to runs/<slug> directory.")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--crossfade", type=float, default=1.2)
    parser.add_argument("--dim-after", type=float, default=0.5, help="Fraction of runtime to start optional dimming.")
    parser.add_argument("--dim-amount", type=float, default=0.0, help="Optional max darken amount (0.0 disables).")
    parser.add_argument("--film-grain", type=int, default=3, help="Subtle archival grain strength on still plates (0 disables).")
    parser.add_argument("--preset", default="veryfast", help="x264 encoding preset.")
    args = parser.parse_args()

    run(
        args.run_dir,
        width=args.width,
        height=args.height,
        fps=args.fps,
        crossfade=args.crossfade,
        dim_after=args.dim_after,
        dim_amount=args.dim_amount,
        film_grain=args.film_grain,
        preset=args.preset,
    )


if __name__ == "__main__":
    main()
