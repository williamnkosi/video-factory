"""Offline deterministic mock image provider generating clean 16:9 PNG frames."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from providers.base import ImageProvider


class MockImageProvider(ImageProvider):
    """Generates atmospheric 16:9 test frames offline via Pillow."""

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

        palettes = [
            ((16, 20, 28), (52, 74, 98), (168, 134, 88)),
            ((22, 18, 16), (86, 58, 36), (186, 136, 72)),
            ((14, 24, 22), (44, 78, 68), (154, 132, 84)),
            ((20, 16, 26), (66, 52, 88), (162, 122, 92)),
        ]
        bg, mid, accent = palettes[seed % len(palettes)]

        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)

        cx = int(width * rng.uniform(0.3, 0.7))
        cy = int(height * rng.uniform(0.32, 0.62))
        for step in range(16, 0, -1):
            frac = step / 16.0
            rx = int(width * 0.55 * frac)
            ry = int(height * 0.55 * frac)
            color = tuple(
                int(
                    bg[c]
                    + (mid[c] - bg[c]) * (1 - frac) * 0.85
                    + (accent[c] - mid[c]) * max(0.0, 0.45 - frac)
                )
                for c in range(3)
            )
            draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=color)

        horizon_y = int(height * rng.uniform(0.58, 0.72))
        draw.rectangle([0, horizon_y, width, height], fill=bg)
        for _ in range(6):
            bx = rng.randint(0, max(1, width - 120))
            bw = rng.randint(60, 220)
            bh = rng.randint(40, 200)
            draw.rectangle(
                [bx, horizon_y - bh, bx + bw, horizon_y + 10],
                fill=(max(4, bg[0] - 5), max(4, bg[1] - 5), max(4, bg[2] - 5)),
            )

        img = img.filter(ImageFilter.GaussianBlur(radius=14))
        overlay = ImageDraw.Draw(img)
        font = _load_font(max(16, height // 48))
        snippet = prompt[:78] + ("..." if len(prompt) > 78 else "")
        overlay.text((40, height - 54), f"[Mock Frame] {snippet}", fill=(170, 150, 124), font=font)

        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_png_path, format="PNG")
        return output_png_path


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()
