"""Offline deterministic mock video provider producing animated documentary hero clips."""

from __future__ import annotations

import hashlib
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from providers.base import VideoProvider


class MockVideoProvider(VideoProvider):
    """Generates smooth, subtly animated vintage editorial hero MP4 clips offline."""

    def generate_video(
        self,
        *,
        prompt: str,
        output_mp4_path: Path,
        image_path: Path | None = None,
        duration_seconds: int = 8,
        width: int = 1920,
        height: int = 1080,
        fps: int = 24,
    ) -> Path:
        dur = max(2, int(duration_seconds))
        total_frames = max(4, dur * fps)
        seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)

        output_mp4_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            if image_path is not None and image_path.exists():
                base_png = image_path
            else:
                base_png = tmp_root / "base.png"
                _render_vintage_backdrop(base_png, width=width, height=height, seed=seed)

            # Create a subtle atmospheric motion clip: gentle camera push + warm sunlight drift
            # + light archival film grain so hero shots feel alive rather than static.
            up_w = round(width * 1.2)
            up_h = round(height * 1.2)
            dx_sign = 1 if (seed % 2 == 0) else -1
            drift_expr = (
                f"iw/2-(iw/zoom/2)+{dx_sign}*28*sin(PI*on/{total_frames})"
            )
            vf = ",".join(
                [
                    f"scale={up_w}:{up_h}:force_original_aspect_ratio=increase",
                    f"crop={up_w}:{up_h}",
                    (
                        f"zoompan=z='1.02+0.07*(on/{total_frames})':"
                        f"x='{drift_expr}':"
                        f"y='ih/2-(ih/zoom/2)-12*(on/{total_frames})':"
                        f"d={total_frames}:s={width}x{height}:fps={fps}"
                    ),
                    "noise=alls=4:allf=t+u",
                    "vignette=PI/6",
                    "format=yuv420p",
                ]
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(base_png),
                    "-vf",
                    vf,
                    "-t",
                    f"{dur:.3f}",
                    "-r",
                    str(fps),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "21",
                    "-an",
                    str(output_mp4_path),
                ],
                check=True,
                capture_output=True,
            )

        return output_mp4_path


def _render_vintage_backdrop(path: Path, *, width: int, height: int, seed: int) -> None:
    """Create a minimalist warm vintage parchment landscape plate if no base image exists."""
    img = Image.new("RGB", (width, height), (239, 230, 213))
    draw = ImageDraw.Draw(img)

    # Subtle layered horizon ridges in Style Bible palette
    layers = [
        (0.56, (197, 139, 67), 0.04),
        (0.66, (168, 90, 68), 0.03),
        (0.76, (77, 100, 117), 0.025),
        (0.84, (31, 36, 40), 0.02),
    ]
    for idx, (y_frac, color, amp_frac) in enumerate(layers):
        pts = [(0, height)]
        base_y = int(height * y_frac)
        amp = int(height * amp_frac)
        phase = (seed % 17) * 0.4 + idx * 1.3
        for x in range(0, width + 32, 32):
            y = base_y + int(amp * math.sin((x / max(1, width)) * math.pi * (2 + idx) + phase))
            pts.append((x, y))
        pts.append((width, height))
        draw.polygon(pts, fill=color)

    img.save(path, format="PNG")
