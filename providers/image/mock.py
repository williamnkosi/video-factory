"""Offline deterministic mock image provider generating vintage editorial 16:9 PNG frames."""

from __future__ import annotations

import hashlib
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

from providers.base import ImageProvider


class MockImageProvider(ImageProvider):
    """Generates clean minimalist vintage editorial 16:9 plates offline via Pillow."""

    def generate_image(
        self,
        *,
        prompt: str,
        output_png_path: Path,
        width: int = 1920,
        height: int = 1080,
    ) -> Path:
        seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed)

        # Warm vintage editorial print palettes (parchment, ochre, terracotta, slate, sage, charcoal)
        palettes = [
            ((239, 230, 213), (197, 139, 67), (168, 90, 68), (77, 100, 117), (31, 36, 40)),
            ((235, 224, 204), (109, 123, 99), (197, 139, 67), (64, 82, 96), (34, 36, 38)),
            ((242, 233, 217), (168, 90, 68), (197, 139, 67), (98, 109, 92), (31, 36, 40)),
            ((232, 224, 212), (77, 100, 117), (197, 139, 67), (138, 92, 68), (28, 33, 38)),
        ]
        sky, sun_c, mid_c, far_c, ink_c = palettes[seed % len(palettes)]

        img = Image.new("RGB", (width, height), sky)
        draw = ImageDraw.Draw(img)

        # Soft parchment vertical sky tint
        for y in range(0, int(height * 0.68), 4):
            t = y / max(1, height * 0.68)
            col = tuple(int(sky[c] * (1 - 0.08 * t) + sun_c[c] * (0.08 * t)) for c in range(3))
            draw.rectangle([0, y, width, y + 4], fill=col)

        # Sun / celestial disc
        sun_x = int(width * rng.uniform(0.24, 0.76))
        sun_y = int(height * rng.uniform(0.22, 0.40))
        sun_r = int(min(width, height) * rng.uniform(0.08, 0.13))
        draw.ellipse(
            [sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r],
            fill=sun_c,
        )

        # Subtle archival horizon bands / rolling highland ridges
        ridge_specs = [
            (0.56, far_c, 0.045, 2.2),
            (0.67, mid_c, 0.035, 3.1),
            (0.78, ink_c, 0.022, 1.8),
        ]
        for idx, (y_frac, col, amp_frac, freq) in enumerate(ridge_specs):
            pts = [(0, height)]
            base_y = int(height * y_frac)
            amp = int(height * amp_frac)
            phase = rng.uniform(0, math.tau)
            for x in range(0, width + 24, 24):
                nx = x / max(1, width)
                y = base_y + int(
                    amp * math.sin(nx * math.pi * freq + phase)
                    + (amp * 0.35) * math.cos(nx * math.pi * (freq * 2.1) - idx)
                )
                pts.append((x, y))
            pts.append((width, height))
            draw.polygon(pts, fill=col)

        # Minimalist geometric architectural silhouettes (monoliths / stone walls / arches)
        horizon_y = int(height * 0.76)
        motif = seed % 3
        if motif == 0:
            # Curved stone wall + conical tower silhouette
            wall_y = int(height * 0.66)
            draw.rounded_rectangle(
                [int(width * 0.14), wall_y, int(width * 0.86), horizon_y + 40],
                radius=28,
                fill=(48, 52, 56),
                outline=ink_c,
                width=3,
            )
            tx = int(width * 0.62)
            tw_base = int(width * 0.055)
            tw_top = int(width * 0.034)
            draw.polygon(
                [
                    (tx - tw_base, wall_y + 20),
                    (tx - tw_top, int(height * 0.42)),
                    (tx + tw_top, int(height * 0.42)),
                    (tx + tw_base, wall_y + 20),
                ],
                fill=ink_c,
            )
        elif motif == 1:
            # Terraced stone steps + geometric chevron frieze linework
            for step in range(4):
                pad = int(width * (0.10 + step * 0.08))
                sy = int(height * (0.72 - step * 0.055))
                draw.rectangle([pad, sy, width - pad, sy + int(height * 0.06)], fill=ink_c)
            chev_y = int(height * 0.69)
            step_w = max(24, width // 42)
            pts = []
            for i, x in enumerate(range(int(width * 0.14), int(width * 0.86), step_w)):
                pts.append((x, chev_y - (10 if i % 2 == 0 else -10)))
            if len(pts) >= 2:
                draw.line(pts, fill=sun_c, width=max(2, width // 480))
        else:
            # Coastal lateen sails / archival harbor silhouette
            for sx_frac, scale in ((0.30, 1.0), (0.52, 1.25), (0.70, 0.85)):
                sx = int(width * sx_frac)
                sy = int(height * 0.75)
                sh = int(height * 0.18 * scale)
                sw = int(width * 0.08 * scale)
                draw.polygon([(sx, sy - sh), (sx + sw, sy - 10), (sx - sw // 4, sy - 10)], fill=sky)
                draw.line([(sx, sy - sh), (sx, sy)], fill=ink_c, width=3)
                draw.polygon(
                    [(sx - sw // 2, sy), (sx + sw, sy), (sx + int(sw * 0.7), sy + 18), (sx - sw // 3, sy + 18)],
                    fill=ink_c,
                )

        # Delicate parchment print hairline border inset
        margin = max(18, min(width, height) // 40)
        draw.rectangle(
            [margin, margin, width - margin, height - margin],
            outline=(ink_c[0], ink_c[1], ink_c[2]),
            width=1,
        )

        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_png_path, format="PNG")
        return output_png_path
