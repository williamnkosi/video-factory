"""Stage 4: Visual Art Director planning scenes and generating cohesive dark painterly images."""

from __future__ import annotations

import math

from pydantic import BaseModel

from video_factory.agents.prompts import ART_DIRECTOR_SYSTEM_PROMPT, SLEEPY_STYLE_BIBLE
from video_factory.config import Settings
from video_factory.models import (
    AudioTimeline,
    OutlineArtifact,
    ProjectManifest,
    SceneSpec,
    ScriptBundle,
    VisualPlan,
)
from video_factory.providers.base import ImageProvider, LLMProvider
from video_factory.storage import ProjectStore

_MOTION_CYCLE: tuple[str, ...] = ("zoom_in", "pan_right", "zoom_out", "pan_left")


class _ScenePromptItem(BaseModel):
    scene_prompt: str
    narration_excerpt: str


class _SceneBatchResponse(BaseModel):
    scenes: list[_ScenePromptItem]


def build_visual_plan(
    manifest: ProjectManifest,
    outline: OutlineArtifact,
    script_bundle: ScriptBundle,
    audio_timeline: AudioTimeline,
    llm: LLMProvider,
) -> VisualPlan:
    """Plan evenly-paced visual scenes synchronized to actual chapter audio timings."""
    script_by_num = {c.chapter_number: c for c in script_bundle.chapters}
    scenes: list[SceneSpec] = []
    global_idx = 0

    total_audio = audio_timeline.total_duration_seconds
    for ch_idx, ch_timing in enumerate(audio_timeline.chapters):
        ch_script = script_by_num[ch_timing.chapter_number]
        # Allocate gap up to next chapter (or end of audio) so visuals seamlessly cover pauses
        if ch_idx < len(audio_timeline.chapters) - 1:
            next_start = audio_timeline.chapters[ch_idx + 1].start_seconds
            span_start = 0.0 if ch_idx == 0 else ch_timing.start_seconds
            span_end = next_start
        else:
            span_start = 0.0 if ch_idx == 0 else ch_timing.start_seconds
            span_end = total_audio

        span_duration = max(2.0, span_end - span_start)
        scene_count = max(1, round(span_duration / max(8, manifest.seconds_per_scene)))
        # Ensure we don't generate an absurd number of scenes if seconds_per_scene is tiny
        scene_count = min(scene_count, max(1, math.ceil(span_duration / 4.0)))

        user_prompt = (
            f"Documentary Title: {outline.working_title}\n"
            f"Historical Era: {outline.historical_era}\n"
            f"Visual Palette Notes: {outline.visual_palette_notes}\n"
            f"Chapter {ch_timing.chapter_number}: {ch_timing.title}\n\n"
            f"Create exactly {scene_count} distinct visual scenes in chronological order matching this narration.\n"
            "Every scene_prompt MUST incorporate dark chiaroscuro oil-painting lighting, low luminance, "
            "warm candlelit or nocturnal atmosphere, and zero text.\n\n"
            f"CHAPTER NARRATION:\n{ch_script.edited_text[:5500]}"
        )
        batch = llm.generate_structured(
            system_prompt=ART_DIRECTOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=_SceneBatchResponse,
            temperature=0.55,
            max_tokens=3072,
        )

        # Normalize returned count to match exact planned scene_count
        items = list(batch.scenes)
        if not items:
            items = [
                _ScenePromptItem(
                    scene_prompt=f"{ch_timing.title}, {SLEEPY_STYLE_BIBLE}",
                    narration_excerpt=ch_script.edited_text[:90],
                )
            ]
        while len(items) < scene_count:
            items.append(items[-1])
        items = items[:scene_count]

        per_scene_dur = span_duration / scene_count
        for local_idx, item in enumerate(items):
            global_idx += 1
            start_s = span_start + local_idx * per_scene_dur
            # Guarantee channel style bible is present even if LLM shortened it
            prompt_text = item.scene_prompt.strip()
            if "chiaroscuro" not in prompt_text.lower() and "oil painting" not in prompt_text.lower():
                prompt_text = f"{prompt_text}. {SLEEPY_STYLE_BIBLE}"

            scenes.append(
                SceneSpec(
                    scene_id=f"scene_{global_idx:03d}",
                    index=global_idx,
                    chapter_number=ch_timing.chapter_number,
                    start_seconds=round(start_s, 3),
                    duration_seconds=round(per_scene_dur, 3),
                    narration_excerpt=item.narration_excerpt[:140],
                    image_prompt=prompt_text,
                    motion=_MOTION_CYCLE[(global_idx - 1) % len(_MOTION_CYCLE)],  # type: ignore[arg-type]
                )
            )

    return VisualPlan(style_bible=SLEEPY_STYLE_BIBLE, scenes=scenes)


def run_art_director_agent(
    manifest: ProjectManifest,
    outline: OutlineArtifact,
    script_bundle: ScriptBundle,
    audio_timeline: AudioTimeline,
    store: ProjectStore,
    llm: LLMProvider,
    image_provider: ImageProvider,
    settings: Settings,
    *,
    only_scene_id: str | None = None,
    replan: bool = False,
) -> VisualPlan:
    """Create or load editable visual_plan.json and generate any missing/requested scene PNGs."""
    store.visuals_dir.mkdir(parents=True, exist_ok=True)

    if store.visual_plan_path.exists() and not replan:
        plan = store.load_visual_plan()
    else:
        plan = build_visual_plan(manifest, outline, script_bundle, audio_timeline, llm)
        store.save_visual_plan(plan)

    for scene in plan.scenes:
        img_path = store.visuals_dir / f"{scene.scene_id}.png"
        should_generate = (
            (only_scene_id is not None and scene.scene_id == only_scene_id)
            or (only_scene_id is None and (replan or not img_path.exists()))
        )
        if should_generate:
            image_provider.generate_image(
                prompt=scene.image_prompt,
                output_png_path=img_path,
                width=settings.video_width,
                height=settings.video_height,
            )
        if img_path.exists():
            scene.image_file = store.relative_str(img_path)

    store.save_visual_plan(plan)
    return plan
