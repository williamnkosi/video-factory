"""Stage 5: Deterministic FFmpeg video assembly with Ken Burns motion, crossfades, and sleep dimming."""

from __future__ import annotations

import subprocess
from pathlib import Path

from video_factory.agents.narrator import probe_media_duration
from video_factory.config import Settings
from video_factory.models import (
    AudioTimeline,
    ProjectManifest,
    RenderArtifact,
    SceneSpec,
    VisualPlan,
)
from video_factory.storage import ProjectStore


def _compute_dim_brightness(
    scene: SceneSpec,
    total_duration: float,
    *,
    enabled: bool,
    start_fraction: float,
    max_darken: float,
) -> float:
    """Return FFmpeg eq brightness offset (0.0 -> -max_darken) for progressive sleep dimming."""
    if not enabled or total_duration <= 0:
        return 0.0
    midpoint = scene.start_seconds + (scene.duration_seconds / 2.0)
    frac = midpoint / total_duration
    if frac <= start_fraction:
        return 0.0
    progress = min(1.0, (frac - start_fraction) / max(0.01, 1.0 - start_fraction))
    return -round(progress * max_darken, 4)


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
) -> Path:
    """Render a single smooth Ken Burns clip from a static 16:9 image."""
    total_frames = max(2, round(duration * fps))
    # Slight overscale keeps zoompan smooth without blowing up CPU render times
    up_w = round(width * 1.25)
    up_h = round(height * 1.25)

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
        "vignette=angle=PI/5",
    ]
    if brightness_offset < 0:
        vf_parts.append(f"eq=brightness={brightness_offset:.4f}")
    vf_parts.append("format=yuv420p")
    vf = ",".join(vf_parts)

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(image_path),
            "-vf",
            vf,
            "-t",
            f"{duration:.3f}",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
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


def _xfade_clip_group(
    clips: list[Path],
    output_mp4: Path,
    *,
    crossfade: float,
    fps: int,
) -> Path:
    """Join a small batch of video clips with smooth crossfade transitions."""
    if len(clips) == 1:
        output_mp4.write_bytes(clips[0].read_bytes())
        return output_mp4

    durations = [probe_media_duration(c) for c in clips]
    cmd = ["ffmpeg", "-y"]
    for clip in clips:
        cmd.extend(["-i", str(clip)])

    filter_parts: list[str] = []
    # Normalize timebase across inputs for reliable xfade
    for i in range(len(clips)):
        filter_parts.append(f"[{i}:v]fps={fps},settb=AVTB,format=yuv420p[v{i}]")

    offset = max(0.1, durations[0] - crossfade)
    prev_label = "v0"
    for i in range(1, len(clips)):
        out_label = "vout" if i == len(clips) - 1 else f"xf{i}"
        filter_parts.append(
            f"[{prev_label}][v{i}]xfade=transition=fade:duration={crossfade:.3f}:offset={offset:.3f}[{out_label}]"
        )
        prev_label = out_label
        offset = max(0.1, offset + durations[i] - crossfade)

    cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[vout]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
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


def _merge_clips_hierarchical(
    clips: list[Path],
    work_dir: Path,
    *,
    crossfade: float,
    fps: int,
    batch_size: int = 8,
) -> Path:
    """Hierarchically xfade clips in bounded batches so 30-min videos never exceed RAM limits."""
    current = list(clips)
    round_num = 0
    while len(current) > 1:
        round_num += 1
        next_level: list[Path] = []
        for idx in range(0, len(current), batch_size):
            group = current[idx : idx + batch_size]
            out_path = work_dir / f"merge_r{round_num}_g{idx // batch_size:02d}.mp4"
            _xfade_clip_group(group, out_path, crossfade=crossfade, fps=fps)
            next_level.append(out_path)
        current = next_level
    return current[0]


def run_assembler_agent(
    manifest: ProjectManifest,
    audio_timeline: AudioTimeline,
    visual_plan: VisualPlan,
    store: ProjectStore,
    settings: Settings,
) -> RenderArtifact:
    """Deterministically assemble all scene PNGs and mastered audio into a YouTube-ready MP4."""
    store.render_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = store.render_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    if not visual_plan.scenes:
        raise ValueError("VisualPlan contains no scenes to render.")

    min_scene_dur = min(s.duration_seconds for s in visual_plan.scenes)
    crossfade = min(settings.crossfade_seconds, max(0.25, min_scene_dur / 3.0))

    total_audio_dur = audio_timeline.total_duration_seconds
    rendered_clips: list[Path] = []

    for idx, scene in enumerate(visual_plan.scenes):
        if not scene.image_file:
            raise FileNotFoundError(f"Scene {scene.scene_id} has no image_file assigned.")
        img_path = store.root / scene.image_file
        if not img_path.exists():
            raise FileNotFoundError(f"Scene image missing on disk: {img_path}")

        # Extend all clips except the last by `crossfade` so overlapped xfade matches audio length
        clip_dur = scene.duration_seconds + (crossfade if idx < len(visual_plan.scenes) - 1 else 0.5)
        clip_path = clips_dir / f"{scene.scene_id}.mp4"
        dim_offset = _compute_dim_brightness(
            scene,
            total_audio_dur,
            enabled=manifest.enable_sleep_dimming,
            start_fraction=settings.dim_start_fraction,
            max_darken=settings.dim_max_darken,
        )
        _render_scene_clip(
            img_path,
            clip_path,
            duration=clip_dur,
            motion=scene.motion,
            width=settings.video_width,
            height=settings.video_height,
            fps=settings.video_fps,
            brightness_offset=dim_offset,
        )
        rendered_clips.append(clip_path)

    merged_video = _merge_clips_hierarchical(
        rendered_clips,
        work_dir=clips_dir,
        crossfade=crossfade,
        fps=settings.video_fps,
    )

    master_audio_path = store.root / audio_timeline.master_audio_file
    final_mp4 = store.render_dir / "final_video.mp4"
    fade_out_start = max(0.0, total_audio_dur - 3.5)

    # Final mux: gentle fade from/to black, sync to mastered audio, faststart for YouTube streaming
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(merged_video),
            "-i",
            str(master_audio_path),
            "-vf",
            f"fade=t=in:st=0:d=2.0,fade=t=out:st={fade_out_start:.3f}:d=3.5",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
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

    final_dur = probe_media_duration(final_mp4)
    return RenderArtifact(
        video_file=store.relative_str(final_mp4),
        width=settings.video_width,
        height=settings.video_height,
        fps=settings.video_fps,
        duration_seconds=round(final_dur, 3),
        file_size_bytes=final_mp4.stat().st_size,
    )
