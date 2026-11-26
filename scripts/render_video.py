#!/usr/bin/env python3
"""Script 3: Deterministic FFmpeg video assembly from scene PNGs and mastered narration audio."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


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


def _render_scene_clip(
    image_path: Path,
    output_mp4: Path,
    *,
    duration: float,
    motion: str,
    width: int,
    height: int,
    fps: int,
    brightness_offset: float,
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
                f"zoompan=z='1.06-0.06*(on/{total_frames})':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={width}x{height}:fps={fps}"
            )
        elif motion == "pan_left":
            zp = (
                f"zoompan=z='1.06':"
                f"x='(iw-iw/zoom)*(1-on/{total_frames})':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={width}x{height}:fps={fps}"
            )
        elif motion == "pan_right":
            zp = (
                f"zoompan=z='1.06':"
                f"x='(iw-iw/zoom)*(on/{total_frames})':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={width}x{height}:fps={fps}"
            )
        else:  # zoom_in
            zp = (
                f"zoompan=z='1+0.06*(on/{total_frames})':"
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
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(output_mp4),
        ],
        check=True,
        capture_output=True,
    )
    return output_mp4


def _xfade_group(clips: list[Path], output_mp4: Path, *, crossfade: float, fps: int, preset: str) -> Path:
    if len(clips) == 1:
        output_mp4.write_bytes(clips[0].read_bytes())
        return output_mp4

    durations = [probe_duration(c) for c in clips]
    cmd = ["ffmpeg", "-y"]
    for clip in clips:
        cmd.extend(["-i", str(clip)])

    filters = [f"[{i}:v]fps={fps},settb=AVTB,format=yuv420p[v{i}]" for i in range(len(clips))]
    offset = max(0.1, durations[0] - crossfade)
    prev = "v0"
    for i in range(1, len(clips)):
        out = "vout" if i == len(clips) - 1 else f"xf{i}"
        filters.append(
            f"[{prev}][v{i}]xfade=transition=fade:duration={crossfade:.3f}:offset={offset:.3f}[{out}]"
        )
        prev = out
        offset = max(0.1, offset + durations[i] - crossfade)

    cmd.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
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
    current = list(clips)
    level = 0
    while len(current) > 1:
        level += 1
        next_level: list[Path] = []
        for idx in range(0, len(current), batch_size):
            group = current[idx : idx + batch_size]
            out = work_dir / f"merge_r{level}_g{idx // batch_size:02d}.mp4"
            _xfade_group(group, out, crossfade=crossfade, fps=fps, preset=preset)
            next_level.append(out)
        current = next_level
    return current[0]


def run(
    run_dir: Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    crossfade: float = 1.5,
    dim_after: float = 0.5,
    dim_amount: float = 0.0,
    preset: str = "veryfast",
) -> dict:
    run_root = run_dir.resolve()
    timeline_path = run_root / "03_audio" / "audio_timeline.json"
    plan_path = run_root / "04_visuals" / "visual_plan.json"
    render_dir = run_root / "05_render"
    clips_dir = render_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    scenes = plan.get("scenes", [])
    if not scenes:
        raise ValueError(f"No scenes found in {plan_path}")

    master_audio = run_root / timeline["master_audio_file"]
    if not master_audio.exists():
        raise FileNotFoundError(f"Master audio missing: {master_audio}")
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
        img_rel = scene.get("image_file") or f"04_visuals/{scene_id}.png"
        img_path = run_root / img_rel
        if not img_path.exists():
            raise FileNotFoundError(f"Missing scene image: {img_path}")

        clip_dur = eff_dur + (safe_xfade if idx < len(scenes) - 1 else 0.5)
        clip_path = clips_dir / f"{scene_id}.mp4"
        dim_offset = _compute_dim_offset(
            cursor,
            eff_dur,
            total_audio_dur,
            dim_after=dim_after,
            dim_amount=dim_amount,
        )
        print(f"[render] Clip {idx + 1}/{len(scenes)} ({scene_id}, {eff_dur:.1f}s, {scene.get('motion', 'zoom_in')})")
        _render_scene_clip(
            img_path,
            clip_path,
            duration=clip_dur,
            motion=scene.get("motion", "zoom_in"),
            width=width,
            height=height,
            fps=fps,
            brightness_offset=dim_offset,
            preset=preset,
        )
        rendered_clips.append(clip_path)
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
    parser = argparse.ArgumentParser(description="Render 1080p MP4 from scene images and mastered audio.")
    parser.add_argument("run_dir", type=Path, help="Path to runs/<slug> directory.")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--crossfade", type=float, default=1.5)
    parser.add_argument("--dim-after", type=float, default=0.5, help="Fraction of runtime to start optional dimming.")
    parser.add_argument("--dim-amount", type=float, default=0.0, help="Optional max darken amount (0.0 disables).")
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
        preset=args.preset,
    )


if __name__ == "__main__":
    main()
