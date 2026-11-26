"""Documentary typography, overlays (chapter cards, lower-thirds), and animated vintage maps."""

from __future__ import annotations

import math
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Style Bible vintage editorial palette
PARCHMENT = (239, 230, 213)
PARCHMENT_DARK = (224, 211, 188)
SEA_MUTE = (212, 221, 223)
SEA_GRID = (192, 203, 206)
CHARCOAL = (31, 36, 40)
INK_SOFT = (74, 82, 88)
OCHRE_GOLD = (197, 139, 67)
TERRACOTTA = (168, 90, 68)
SLATE_BLUE = (77, 100, 117)
SAVANNA_SAGE = (109, 123, 99)

# Simplified real-world (lon, lat) coastline polygons for vintage cartographic plates
AFRICA_MAINLAND_COAST: list[tuple[float, float]] = [
    (-5.6, 35.8), (10.5, 37.0), (11.2, 33.2), (20.0, 32.1), (25.2, 31.6),
    (32.5, 31.2), (34.8, 28.0), (37.2, 21.5), (43.3, 12.6), (51.2, 11.8),
    (49.0, 5.2), (41.0, -2.0), (39.5, -6.8), (40.6, -10.8), (40.5, -15.2),
    (35.0, -19.8), (35.5, -24.0), (32.9, -26.0), (31.0, -29.8), (27.9, -33.0),
    (20.0, -34.8), (18.4, -34.2), (17.9, -31.5), (14.5, -23.0), (12.0, -17.2),
    (13.2, -9.0), (12.2, -5.8), (9.4, 0.5), (9.0, 4.0), (5.5, 4.3),
    (1.2, 6.1), (-4.0, 5.2), (-7.8, 4.5), (-13.3, 8.5), (-16.8, 12.2),
    (-17.4, 14.7), (-16.2, 19.5), (-17.0, 21.2), (-13.2, 27.6), (-9.6, 30.4),
    (-6.8, 34.0), (-5.6, 35.8),
]

MADAGASCAR_COAST: list[tuple[float, float]] = [
    (49.3, -12.0), (50.4, -15.4), (49.4, -18.2), (47.5, -24.8), (45.2, -25.6),
    (43.6, -23.3), (44.3, -20.2), (46.3, -15.8), (48.5, -13.4), (49.3, -12.0),
]

ARABIA_COAST: list[tuple[float, float]] = [
    (34.8, 29.5), (40.0, 21.0), (43.5, 12.7), (54.0, 17.0), (59.8, 22.5),
    (56.3, 26.2), (50.0, 26.8), (48.0, 30.0), (36.0, 32.0), (34.8, 29.5),
]

INDIA_WEST_COAST: list[tuple[float, float]] = [
    (68.0, 24.0), (72.8, 19.0), (74.8, 13.0), (77.5, 8.1), (80.3, 13.0),
    (86.0, 20.5), (86.0, 28.0), (68.0, 28.0), (68.0, 24.0),
]

_ROMAN_NUMERALS = [
    "", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"
]


def load_font(
    size: int,
    *,
    style: str = "serif_bold",
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a crisp cross-platform editorial font on macOS or Linux."""
    candidates: dict[str, tuple[str, ...]] = {
        "serif_bold": (
            "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
            "/System/Library/Fonts/Supplemental/Baskerville.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        ),
        "serif": (
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
            "/System/Library/Fonts/Supplemental/Baskerville.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        ),
        "sans_bold": (
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/System/Library/Fonts/Supplemental/GillSans.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ),
        "sans": (
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/System/Library/Fonts/Supplemental/GillSans.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ),
    }
    for path_str in candidates.get(style, candidates["serif_bold"]):
        if Path(path_str).exists():
            try:
                return ImageFont.truetype(path_str, size=size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _roman(num: int) -> str:
    return _ROMAN_NUMERALS[num] if 0 < num < len(_ROMAN_NUMERALS) else str(num)


def render_chapter_card_overlay(
    output_png: Path,
    *,
    width: int,
    height: int,
    chapter_number: int,
    title: str,
    subtitle: str | None = None,
) -> Path:
    """Create a transparent RGBA editorial chapter-title plate for FFmpeg overlay."""
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    scale = height / 1080.0
    band_h = int(230 * scale) if not subtitle else int(270 * scale)
    y0 = int(height * 0.37)
    y1 = y0 + band_h

    # Subtle translucent warm charcoal editorial band
    draw.rectangle([0, y0, width, y1], fill=(24, 28, 32, 208))
    rule_w = int(width * 0.16)
    cx = width // 2
    draw.rectangle(
        [cx - rule_w // 2, y0 + int(28 * scale), cx + rule_w // 2, y0 + int(31 * scale)],
        fill=(*OCHRE_GOLD, 240),
    )

    label_font = load_font(max(14, int(24 * scale)), style="sans_bold")
    title_font = load_font(max(24, int(58 * scale)), style="serif_bold")
    sub_font = load_font(max(14, int(26 * scale)), style="serif")

    chapter_label = f"CHAPTER {_roman(chapter_number)}"
    lb = draw.textbbox((0, 0), chapter_label, font=label_font)
    draw.text(
        (cx - (lb[2] - lb[0]) // 2, y0 + int(48 * scale)),
        chapter_label,
        font=label_font,
        fill=(*OCHRE_GOLD, 255),
    )

    wrapped = textwrap.wrap(title.strip(), width=34)[:2]
    ty = y0 + int(94 * scale)
    for line in wrapped:
        tb = draw.textbbox((0, 0), line, font=title_font)
        draw.text(
            (cx - (tb[2] - tb[0]) // 2, ty),
            line,
            font=title_font,
            fill=(*PARCHMENT, 255),
        )
        ty += int(66 * scale)

    if subtitle:
        sb = draw.textbbox((0, 0), subtitle.strip(), font=sub_font)
        draw.text(
            (cx - (sb[2] - sb[0]) // 2, ty + int(6 * scale)),
            subtitle.strip(),
            font=sub_font,
            fill=(206, 198, 184, 235),
        )

    output_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_png, format="PNG")
    return output_png


def render_callout_overlay(
    output_png: Path,
    *,
    width: int,
    height: int,
    location: str,
    era: str | None = None,
    caption: str | None = None,
) -> Path:
    """Create a crisp documentary lower-third badge (location / era / caption) RGBA PNG."""
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    scale = height / 1080.0

    loc_font = load_font(max(16, int(30 * scale)), style="serif_bold")
    era_font = load_font(max(12, int(20 * scale)), style="sans_bold")
    cap_font = load_font(max(12, int(21 * scale)), style="serif")

    loc_text = location.strip()
    era_text = (era or "").strip().upper()
    cap_text = (caption or "").strip()

    pad_x = int(28 * scale)
    pad_y = int(18 * scale)
    bar_w = max(5, int(7 * scale))

    widths = [draw.textbbox((0, 0), loc_text, font=loc_font)[2]]
    total_h = int(38 * scale)
    if era_text:
        widths.append(draw.textbbox((0, 0), era_text, font=era_font)[2])
        total_h += int(28 * scale)
    if cap_text:
        widths.append(draw.textbbox((0, 0), cap_text, font=cap_font)[2])
        total_h += int(28 * scale)

    box_w = min(int(width * 0.56), max(widths) + pad_x * 2 + bar_w)
    box_h = total_h + pad_y * 2
    x0 = int(width * 0.05)
    y0 = int(height * 0.80) - (box_h // 2)

    draw.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=(24, 28, 32, 215))
    draw.rectangle([x0, y0, x0 + bar_w, y0 + box_h], fill=(*OCHRE_GOLD, 255))

    tx = x0 + bar_w + pad_x
    ty = y0 + pad_y
    if era_text:
        draw.text((tx, ty), era_text, font=era_font, fill=(*OCHRE_GOLD, 255))
        ty += int(27 * scale)
    draw.text((tx, ty), loc_text, font=loc_font, fill=(*PARCHMENT, 255))
    ty += int(38 * scale)
    if cap_text:
        draw.text((tx, ty), cap_text, font=cap_font, fill=(210, 202, 188, 240))

    output_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_png, format="PNG")
    return output_png


def _project_lonlat(
    lon: float,
    lat: float,
    bbox: tuple[float, float, float, float],
    width: int,
    height: int,
) -> tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = bbox
    x = ((lon - min_lon) / max(0.001, max_lon - min_lon)) * width
    y = ((max_lat - lat) / max(0.001, max_lat - min_lat)) * height
    return x, y


def _auto_bbox(stops: list[dict], width: int, height: int) -> tuple[float, float, float, float]:
    lons = [float(s["lon"]) for s in stops]
    lats = [float(s["lat"]) for s in stops]
    cx = (min(lons) + max(lons)) / 2.0
    cy = (min(lats) + max(lats)) / 2.0
    span_lon = max(14.0, (max(lons) - min(lons)) * 2.1)
    span_lat = max(10.0, (max(lats) - min(lats)) * 2.1)
    aspect = width / max(1, height)
    if span_lon / span_lat < aspect:
        span_lon = span_lat * aspect
    else:
        span_lat = span_lon / aspect
    return (cx - span_lon / 2.0, cy - span_lat / 2.0, cx + span_lon / 2.0, cy + span_lat / 2.0)


def _sample_route_polyline(
    points: list[tuple[float, float]],
    stops: list[dict] | None = None,
    steps_per_seg: int = 36,
) -> list[tuple[float, float]]:
    """Interpolate smooth curved arcs between map stops for vintage cartographic routes."""
    if len(points) < 2:
        return points
    sampled: list[tuple[float, float]] = []
    for idx in range(len(points) - 1):
        x0, y0 = points[idx]
        x1, y1 = points[idx + 1]
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy)
        # Optional explicit curve_dir (-1, 0, +1) on destination stop for sea vs. inland arcs
        stop_dir = None
        if stops and idx + 1 < len(stops):
            stop_dir = stops[idx + 1].get("curve_dir")
        direction = float(stop_dir) if stop_dir is not None else (1.0 if idx % 2 == 0 else -1.0)
        curve = min(56.0, dist * 0.16) * direction
        nx, ny = (-dy / max(1.0, dist), dx / max(1.0, dist))
        mx, my = (x0 + x1) / 2.0 + nx * curve, (y0 + y1) / 2.0 + ny * curve
        for s in range(steps_per_seg):
            t = s / steps_per_seg
            inv = 1.0 - t
            px = inv * inv * x0 + 2 * inv * t * mx + t * t * x1
            py = inv * inv * y0 + 2 * inv * t * my + t * t * y1
            sampled.append((px, py))
    sampled.append(points[-1])
    return sampled


def _draw_compass_rose(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int, scale: float) -> None:
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=INK_SOFT, width=max(1, int(2 * scale)))
    inner = int(radius * 0.24)
    # Four cardinal spikes
    draw.polygon([(cx, cy - radius), (cx + inner, cy), (cx, cy)], fill=CHARCOAL)
    draw.polygon([(cx, cy - radius), (cx - inner, cy), (cx, cy)], fill=OCHRE_GOLD)
    draw.polygon([(cx, cy + radius), (cx + inner, cy), (cx, cy)], fill=INK_SOFT)
    draw.polygon([(cx, cy + radius), (cx - inner, cy), (cx, cy)], fill=PARCHMENT_DARK)
    draw.polygon([(cx + radius, cy), (cx, cy - inner), (cx, cy + inner)], fill=INK_SOFT)
    draw.polygon([(cx - radius, cy), (cx, cy - inner), (cx, cy + inner)], fill=INK_SOFT)
    n_font = load_font(max(11, int(18 * scale)), style="serif_bold")
    nb = draw.textbbox((0, 0), "N", font=n_font)
    draw.text((cx - (nb[2] - nb[0]) // 2, cy - radius - int(24 * scale)), "N", font=n_font, fill=CHARCOAL)


def render_animated_map_clip(
    map_spec: dict,
    output_mp4: Path,
    *,
    duration: float,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    preset: str = "veryfast",
) -> Path:
    """Render a smoothly animated vintage parchment trade/route map MP4 via Pillow + FFmpeg."""
    stops = map_spec.get("stops") or []
    if not stops:
        raise ValueError("Animated map scene requires at least one stop in map.stops.")

    total_frames = max(4, round(duration * fps))
    scale = height / 1080.0
    raw_bbox = map_spec.get("bbox")
    if raw_bbox and len(raw_bbox) == 4:
        bbox = (float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3]))
    else:
        bbox = _auto_bbox(stops, width, height)

    # 1) Pre-render crisp static vintage map baseplate once
    base = Image.new("RGB", (width, height), SEA_MUTE)
    bdraw = ImageDraw.Draw(base)

    # Subtle latitude/longitude graticule
    min_lon, min_lat, max_lon, max_lat = bbox
    for lon_line in range(int(min_lon // 5) * 5, int(max_lon) + 6, 5):
        x, _ = _project_lonlat(lon_line, min_lat, bbox, width, height)
        bdraw.line([(x, 0), (x, height)], fill=SEA_GRID, width=1)
    for lat_line in range(int(min_lat // 5) * 5, int(max_lat) + 6, 5):
        _, y = _project_lonlat(min_lon, lat_line, bbox, width, height)
        bdraw.line([(0, y), (width, y)], fill=SEA_GRID, width=1)

    # Landmasses in warm parchment with crisp charcoal coastline
    for coast in (AFRICA_MAINLAND_COAST, MADAGASCAR_COAST, ARABIA_COAST, INDIA_WEST_COAST):
        poly = [_project_lonlat(lon, lat, bbox, width, height) for lon, lat in coast]
        bdraw.polygon(poly, fill=PARCHMENT, outline=CHARCOAL)
        bdraw.line(poly, fill=CHARCOAL, width=max(2, int(2.5 * scale)))

    # Editorial inset frame & compass rose
    margin = int(28 * scale)
    bdraw.rectangle([margin, margin, width - margin, height - margin], outline=INK_SOFT, width=max(1, int(2 * scale)))
    _draw_compass_rose(
        bdraw,
        cx=width - int(110 * scale),
        cy=height - int(115 * scale),
        radius=int(42 * scale),
        scale=scale,
    )

    # Cartographic title cartouche top-left
    map_title = (map_spec.get("title") or "").strip()
    map_subtitle = (map_spec.get("subtitle") or "").strip()
    if map_title:
        tf = load_font(max(16, int(34 * scale)), style="serif_bold")
        sf = load_font(max(12, int(20 * scale)), style="sans_bold")
        tw = bdraw.textbbox((0, 0), map_title, font=tf)[2]
        sw = bdraw.textbbox((0, 0), map_subtitle.upper(), font=sf)[2] if map_subtitle else 0
        cw = max(tw, sw) + int(48 * scale)
        ch = int((96 if map_subtitle else 64) * scale)
        cx0, cy0 = margin + int(24 * scale), margin + int(24 * scale)
        bdraw.rectangle([cx0, cy0, cx0 + cw, cy0 + ch], fill=PARCHMENT, outline=CHARCOAL, width=max(1, int(2 * scale)))
        bdraw.rectangle([cx0, cy0, cx0 + int(7 * scale), cy0 + ch], fill=TERRACOTTA)
        bdraw.text((cx0 + int(24 * scale), cy0 + int(14 * scale)), map_title, font=tf, fill=CHARCOAL)
        if map_subtitle:
            bdraw.text(
                (cx0 + int(24 * scale), cy0 + int(56 * scale)),
                map_subtitle.upper(),
                font=sf,
                fill=TERRACOTTA,
            )

    # Project stops and precompute smooth route polyline
    stop_pts = [_project_lonlat(float(s["lon"]), float(s["lat"]), bbox, width, height) for s in stops]
    route_pts = _sample_route_polyline(stop_pts, stops=stops, steps_per_seg=42)
    label_font = load_font(max(13, int(23 * scale)), style="serif_bold")
    note_font = load_font(max(11, int(17 * scale)), style="sans")

    # 2) Pipe animated frames directly into FFmpeg H.264 encoder
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
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
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None

    n_stops = len(stops)
    route_color = TERRACOTTA
    line_w = max(3, int(6 * scale))

    try:
        for frame_idx in range(total_frames):
            # Draw route smoothly over first 78% of clip, hold cleanly for the rest
            progress = min(1.0, frame_idx / max(1, int(total_frames * 0.78)))
            frame = base.copy()
            fdraw = ImageDraw.Draw(frame)

            # Animated curved trade route
            if len(route_pts) >= 2 and progress > 0.0:
                max_idx = max(1, int(progress * (len(route_pts) - 1)))
                active_pts = route_pts[: max_idx + 1]
                # Soft gold casing + rich terracotta ink line
                fdraw.line(active_pts, fill=OCHRE_GOLD, width=line_w + max(2, int(4 * scale)))
                fdraw.line(active_pts, fill=route_color, width=line_w)
                hx, hy = active_pts[-1]
                hr = max(5, int(9 * scale))
                fdraw.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=OCHRE_GOLD, outline=CHARCOAL, width=2)

            # Reveal stops + ripple rings + editorial labels as the route reaches them
            for s_idx, (stop, (sx, sy)) in enumerate(zip(stops, stop_pts, strict=True)):
                threshold = 0.0 if n_stops == 1 else (s_idx / (n_stops - 1)) * 0.96
                if progress + 0.01 < threshold:
                    continue
                age = min(1.0, (progress - threshold) / 0.14) if progress >= threshold else 1.0
                if age < 1.0:
                    rip_r = int((12 + 28 * age) * scale)
                    fdraw.ellipse(
                        [sx - rip_r, sy - rip_r, sx + rip_r, sy + rip_r],
                        outline=OCHRE_GOLD,
                        width=max(1, int(2 * scale)),
                    )

                pin_r = max(6, int(10 * scale))
                fdraw.ellipse(
                    [sx - pin_r, sy - pin_r, sx + pin_r, sy + pin_r],
                    fill=TERRACOTTA if s_idx in (0, n_stops - 1) else CHARCOAL,
                    outline=PARCHMENT,
                    width=max(2, int(3 * scale)),
                )

                # Label box offset cleanly (configurable per stop via label_offset: [dx, dy])
                off = stop.get("label_offset") or [16, -24]
                lx = sx + int(off[0] * scale)
                ly = sy + int(off[1] * scale)
                name = str(stop["name"])
                note = str(stop.get("note") or "")
                nb = fdraw.textbbox((0, 0), name, font=label_font)
                nw = nb[2] - nb[0]
                nh = nb[3] - nb[1]
                sub_box = fdraw.textbbox((0, 0), note, font=note_font) if note else (0, 0, 0, 0)
                sub_w = sub_box[2] - sub_box[0]
                sub_h = (sub_box[3] - sub_box[1]) if note else 0
                pad_x = int(12 * scale)
                pad_y = int(8 * scale)
                gap_y = int(6 * scale) if note else 0
                bw = max(nw, sub_w) + pad_x * 2
                bh = nh + gap_y + sub_h + pad_y * 2
                lx = max(margin + 8, min(width - margin - bw - 8, lx))
                ly = max(margin + 8, min(height - margin - bh - 8, ly))
                fdraw.rectangle([lx, ly, lx + bw, ly + bh], fill=PARCHMENT, outline=INK_SOFT, width=1)
                fdraw.text((lx + pad_x, ly + pad_y - nb[1]), name, font=label_font, fill=CHARCOAL)
                if note:
                    fdraw.text(
                        (lx + pad_x, ly + pad_y + nh + gap_y - sub_box[1]),
                        note,
                        font=note_font,
                        fill=INK_SOFT,
                    )

            # Subtle slow documentary camera zoom across the clip (1.00 -> 1.04)
            zoom = 1.0 + 0.04 * (frame_idx / max(1, total_frames - 1))
            if zoom > 1.001:
                crop_w = int(width / zoom)
                crop_h = int(height / zoom)
                x0 = (width - crop_w) // 2
                y0 = (height - crop_h) // 2
                frame = frame.crop((x0, y0, x0 + crop_w, y0 + crop_h)).resize(
                    (width, height), Image.Resampling.BILINEAR
                )

            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()

    stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"FFmpeg failed while rendering animated map {output_mp4}: {stderr}")

    return output_mp4
