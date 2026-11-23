"""Deterministic offline mock providers for zero-cost pipeline testing and demos."""

from __future__ import annotations

import hashlib
import math
import random
import struct
import wave
from pathlib import Path
from typing import TypeVar

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel

from video_factory.models import ChapterOutline, OutlineArtifact
from video_factory.providers.base import ImageProvider, LLMProvider, TTSProvider

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(LLMProvider):
    """Offline mock LLM that returns well-formed sleep history outlines, prose, and metadata."""

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        # Handle critic / editor passes cleanly by returning lightly polished text
        if "REVIEW THIS CHAPTER" in user_prompt or "POLISH" in system_prompt.upper():
            marker = "CHAPTER TEXT:\n"
            if marker in user_prompt:
                raw = user_prompt.split(marker, 1)[1].strip()
                cleaned = raw.replace("!", ".").replace("delve", "drift").replace("tapestry", "weave")
                return cleaned
        # Generate calm, soothing historical paragraphs proportional to requested word count
        target_words = _extract_target_words(user_prompt, default=350)
        topic = _extract_line(user_prompt, "Chapter Title:") or "The Quiet Turning of the Centuries"
        base_paragraphs = [
            (
                f"In the hush of evening, the story of {topic.lower()} unfolds not with trumpets or sudden shocks, "
                "but with the slow rhythm of ordinary hands at work. Along stone lanes dampened by twilight dew, "
                "merchants folded linen awnings while oil lamps flickered behind leaded glass. History, when viewed "
                "at a gentler distance, rarely rushes; it settles like dust upon carved timber and ledger paper."
            ),
            (
                "Records kept by patient clerks tell of weights and measures, seasonal harvests, and boats waiting "
                "for the tide to turn. A single sack of grain or jar of resin might pass through seven pairs of hands "
                "between the river quay and the cellar where it would rest through winter. Each journey left small, "
                "quiet marks in account books, letters, and the worn steps of municipal halls."
            ),
            (
                "As lamps dimmed across the old quarter, watchmen paced slowly beside shuttered workshops. "
                "The smell of cedar shavings, beeswax, and woodsmoke lingered in the cool air, carrying the memory "
                "of a day's careful labor. Nothing demanded haste anymore; the work that could be finished was done, "
                "and whatever remained would wait patiently for morning light."
            ),
            (
                "Over decades, customs shifted almost imperceptibly, much as a river reshapes a pebble over many "
                "winters. Guild apprentices grew into elders, tools were mended rather than discarded, and songs "
                "hummed during long afternoons passed quietly from one generation to the next."
            ),
        ]
        paragraphs: list[str] = []
        words_so_far = 0
        idx = 0
        while words_so_far < target_words:
            p = base_paragraphs[idx % len(base_paragraphs)]
            paragraphs.append(p)
            words_so_far += len(p.split())
            idx += 1
        return "\n\n".join(paragraphs)

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> T:
        name = response_model.__name__
        if name == "OutlineArtifact":
            return self._mock_outline(user_prompt)  # type: ignore[return-value]
        if name == "_SceneBatchResponse":
            return self._mock_scenes(user_prompt, response_model)
        if name == "_PackagingLLMResponse":
            return self._mock_packaging(user_prompt, response_model)
        raise NotImplementedError(f"MockLLMProvider does not support {name}")

    def _mock_outline(self, user_prompt: str) -> OutlineArtifact:
        topic = _extract_line(user_prompt, "Topic Description:") or "Forgotten Trade Routes of Antiquity"
        target_words = _extract_target_words(user_prompt, default=1800)
        num_chapters = max(3, min(7, round(target_words / 500)))
        words_per_chapter = max(120, target_words // num_chapters)

        templates = [
            ("Dusk Over the Old Harbor", "gentle_opening"),
            ("The Craft of Patient Hands", "calm_immersion"),
            ("Ledgers, Roads, and Quiet Exchanges", "calm_immersion"),
            ("Winter Stores and Candlelit Workshops", "deep_drifting"),
            ("Distant Ports and Slow Tides", "deep_drifting"),
            ("Echoes Left in Stone and Ink", "soft_winding_down"),
            ("When the Lanterns Finally Fade", "soft_winding_down"),
        ]
        chapters: list[ChapterOutline] = []
        for i in range(num_chapters):
            title, energy = templates[i % len(templates)]
            if i == num_chapters - 1:
                energy = "soft_winding_down"
            chapters.append(
                ChapterOutline(
                    chapter_number=i + 1,
                    title=title,
                    summary=f"A calm exploration of {topic.lower()}, focusing on {title.lower()} and everyday historical texture.",
                    key_historical_facts=[
                        f"Archival trade and household practices connected to {topic.lower()}.",
                        "Seasonal rhythms governed travel, craft, and daily survival.",
                    ],
                    sensory_details=[
                        "Warm amber candlelight across rough plaster walls",
                        "Distant rainfall tapping softly against clay roof tiles",
                    ],
                    energy_level=energy,  # type: ignore[arg-type]
                    target_words=words_per_chapter,
                )
            )

        clean_title = topic.strip().rstrip(".")
        return OutlineArtifact(
            working_title=f"The Sleepy History of {clean_title[:60]}",
            subtitle_hook="A calm, candlelit documentary to drift asleep to.",
            historical_era="Pre-industrial & Classical Era",
            geographic_setting="Old harbors, quiet countryside, and candlelit study halls",
            editorial_angle="Everyday lived texture, craft, and unhurried historical continuity rather than dramatic battles.",
            narrator_tone_notes="Unhurried British documentary cadence, warm and steady, gentle pauses.",
            visual_palette_notes="Low-luminance Dutch golden-age chiaroscuro, warm ochre, deep umber, muted indigo.",
            research_sources=["Mock Archival Compendium (offline dry-run mode)"],
            chapters=chapters,
        )

    def _mock_scenes(self, user_prompt: str, response_model: type[T]) -> T:
        import re

        count_match = re.search(r"Create exactly (\d+) distinct visual scenes", user_prompt)
        count = int(count_match.group(1)) if count_match else 4
        scenes = []
        motifs = [
            "Candlelit medieval scriptorium with weathered parchment and brass astrolabe",
            "Misty ancient harbor at twilight with wooden merchant vessels moored in still water",
            "Quiet apothecary workshop with glass vials, dried herbs, and warm hearth glow",
            "Rain-slicked cobblestone lane under soft lantern light in an old European town",
            "Old stone library with leather-bound folios and gentle moonlight through arched windows",
            "Moonlit valley and winding dirt trade road beside terraced hills",
        ]
        for idx in range(count):
            motif = motifs[idx % len(motifs)]
            scenes.append(
                {
                    "scene_prompt": (
                        f"Oil painting in dark Dutch Golden Age chiaroscuro style, {motif}, "
                        "muted warm amber and deep umber shadows, low brightness, serene nocturnal atmosphere, no text"
                    ),
                    "narration_excerpt": f"Scene {idx + 1}: {motif[:70]}...",
                }
            )
        return response_model.model_validate({"scenes": scenes})

    def _mock_packaging(self, user_prompt: str, response_model: type[T]) -> T:
        title = _extract_line(user_prompt, "Working Title:") or "The Sleepy History of Quiet Worlds"
        return response_model.model_validate(
            {
                "title_options": [
                    f"{title} | Relaxing History to Fall Asleep To",
                    f"Fall Asleep to History: {title} (No Loud Sounds)",
                    f"{title} — A Calm Bedtime Documentary",
                ],
                "selected_title": f"{title} | Relaxing History to Fall Asleep To",
                "description_intro": (
                    f"Settle in, dim the lights, and drift through {title.lower()}. "
                    "Designed with gentle, unhurried narration, warm low-volume audio, and dark painterly scenes "
                    "so you can relax or fall asleep without sudden sounds."
                ),
                "tags": [
                    "sleepy history",
                    "history to fall asleep to",
                    "relaxing documentary",
                    "bedtime history",
                    "calm narration",
                    "sleep documentary",
                ],
            }
        )


class MockTTSProvider(TTSProvider):
    """Generates soft, gentle synthetic WAV narration placeholders for offline testing."""

    def __init__(self, seconds_per_100_words: float = 2.0, sample_rate: int = 24000) -> None:
        # Shortened by default in mock mode so e2e tests render in seconds while exercising real FFmpeg!
        self.seconds_per_100_words = seconds_per_100_words
        self.sample_rate = sample_rate

    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav_path: Path,
        voice_instructions: str | None = None,
    ) -> Path:
        words = max(1, len(text.split()))
        duration = max(2.5, min(12.0, (words / 100.0) * self.seconds_per_100_words))
        total_samples = int(duration * self.sample_rate)

        seed = int(hashlib.sha256(text[:120].encode("utf-8")).hexdigest()[:8], 16)
        base_freq = 145.0 + (seed % 35)  # Warm baritone hum simulating narration envelope

        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)

            frames = bytearray()
            for i in range(total_samples):
                t = i / self.sample_rate
                # Soft speech-like syllable amplitude modulation + fade in/out
                syllable_env = 0.55 + 0.45 * math.sin(2.0 * math.pi * 2.4 * t)
                fade = min(1.0, t / 0.3, (duration - t) / 0.3)
                sample_val = (
                    0.18 * math.sin(2.0 * math.pi * base_freq * t)
                    + 0.08 * math.sin(2.0 * math.pi * (base_freq * 1.5) * t)
                ) * syllable_env * max(0.0, fade)
                pcm = max(-32767, min(32767, int(sample_val * 32767)))
                frames.extend(struct.pack("<h", pcm))
            wf.writeframes(frames)
        return output_wav_path


class MockImageProvider(ImageProvider):
    """Generates atmospheric dark chiaroscuro PNGs offline via Pillow."""

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

        # Dark warm candlelit canvas (low luminance for sleep-friendly viewing)
        palettes = [
            ((14, 12, 16), (78, 52, 28), (156, 108, 54)),
            ((11, 16, 22), (38, 54, 68), (132, 104, 68)),
            ((18, 12, 10), (74, 42, 26), (146, 96, 48)),
            ((12, 15, 14), (44, 58, 46), (126, 102, 62)),
        ]
        bg, mid, glow = palettes[seed % len(palettes)]

        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)

        # Soft painterly overlapping ellipses to simulate chiaroscuro lighting
        cx = int(width * rng.uniform(0.32, 0.68))
        cy = int(height * rng.uniform(0.35, 0.62))
        for step in range(18, 0, -1):
            frac = step / 18.0
            rx = int(width * 0.52 * frac)
            ry = int(height * 0.55 * frac)
            color = tuple(
                int(bg[c] + (mid[c] - bg[c]) * (1 - frac) * 0.8 + (glow[c] - mid[c]) * max(0.0, 0.45 - frac))
                for c in range(3)
            )
            draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=color)

        # Subtle horizon / architectural silhouette
        horizon_y = int(height * rng.uniform(0.58, 0.72))
        draw.rectangle([0, horizon_y, width, height], fill=(bg[0], bg[1], bg[2]))
        for _ in range(7):
            bx = rng.randint(0, width - 120)
            bw = rng.randint(60, 220)
            bh = rng.randint(40, 210)
            draw.rectangle(
                [bx, horizon_y - bh, bx + bw, horizon_y + 10],
                fill=(max(4, bg[0] - 4), max(4, bg[1] - 4), max(4, bg[2] - 4)),
            )

        img = img.filter(ImageFilter.GaussianBlur(radius=18))

        # Subtle warm golden vignette border
        overlay = ImageDraw.Draw(img)
        font = _load_font(22)
        snippet = prompt[:76] + ("..." if len(prompt) > 76 else "")
        overlay.text((54, height - 64), f"[Mock Scene] {snippet}", fill=(120, 98, 72), font=font)

        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_png_path, format="PNG")
        return output_png_path


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _extract_target_words(prompt: str, default: int) -> int:
    import re

    match = re.search(r"(?:Target Word Count|target_words|Target total words)[:\s~]+(\d+)", prompt, re.IGNORECASE)
    return int(match.group(1)) if match else default


def _extract_line(prompt: str, prefix: str) -> str | None:
    for line in prompt.splitlines():
        if line.strip().startswith(prefix):
            return line.strip()[len(prefix) :].strip()
    return None
