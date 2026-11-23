"""Stage-gated DAG orchestrator with checkpoint resume and surgical item regeneration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from video_factory.agents.art_director import run_art_director_agent
from video_factory.agents.assembler import run_assembler_agent
from video_factory.agents.narrator import run_narrator_agent
from video_factory.agents.packager import run_packager_agent
from video_factory.agents.researcher import run_researcher_agent
from video_factory.agents.writer import run_writer_agent
from video_factory.config import Settings
from video_factory.models import (
    STAGE_ORDER,
    ProjectManifest,
    StageName,
    StageStatus,
)
from video_factory.providers import ProviderBundle, build_providers
from video_factory.storage import ProjectStore

StageCallback = Callable[[StageName, str], None]


@dataclass
class CostEstimate:
    target_minutes: int
    estimated_words: int
    estimated_tts_chars: int
    estimated_images: int
    llm_usd: float
    tts_usd: float
    image_usd: float

    @property
    def total_usd(self) -> float:
        return round(self.llm_usd + self.tts_usd + self.image_usd, 2)


def estimate_project_cost(manifest: ProjectManifest) -> CostEstimate:
    """Rough pre-flight cost estimate so creators know API spend before running paid stages."""
    words = manifest.target_minutes * manifest.words_per_minute
    tts_chars = int(words * 6.0)
    images = max(3, int((manifest.target_minutes * 60) / max(10, manifest.seconds_per_scene)))

    # Conservative order-of-magnitude API rates
    llm_usd = 0.0 if manifest.providers.llm == "mock" else round(max(0.05, words / 4000 * 0.12), 2)
    if manifest.providers.tts == "mock":
        tts_usd = 0.0
    elif manifest.providers.tts == "openai":
        # OpenAI gpt-4o-mini-tts / tts-1 ballpark (~$0.015/min)
        tts_usd = round(manifest.target_minutes * 0.015, 2)
    else:
        # Gemini TTS preview ballpark
        tts_usd = round(manifest.target_minutes * 0.02, 2)

    if manifest.providers.image == "mock":
        image_usd = 0.0
    elif manifest.providers.image == "gemini":
        # Imagen 3 (~$0.03-$0.04 per image)
        image_usd = round(images * 0.035, 2)
    else:
        # OpenAI gpt-image-1 medium (~$0.04-$0.07 per image)
        image_usd = round(images * 0.05, 2)

    return CostEstimate(
        target_minutes=manifest.target_minutes,
        estimated_words=words,
        estimated_tts_chars=tts_chars,
        estimated_images=images,
        llm_usd=llm_usd,
        tts_usd=tts_usd,
        image_usd=image_usd,
    )


def _invalidate_downstream(manifest: ProjectManifest, start_stage: StageName) -> None:
    """Mark all stages strictly after start_stage as pending so dependent artifacts rebuild."""
    idx = STAGE_ORDER.index(start_stage)
    for stage in STAGE_ORDER[idx + 1 :]:
        if manifest.stages[stage].status == StageStatus.COMPLETED:
            manifest.stages[stage].status = StageStatus.PENDING
            manifest.stages[stage].notes = f"Invalidated after {start_stage.value} changed."


def run_stage(
    stage: StageName,
    store: ProjectStore,
    manifest: ProjectManifest,
    providers: ProviderBundle,
    settings: Settings,
    *,
    force: bool = False,
) -> ProjectManifest:
    """Execute a single pipeline stage, persisting checkpoints before and after."""
    manifest.mark_stage(stage, StageStatus.RUNNING)
    store.save_manifest(manifest)

    try:
        if stage == StageName.OUTLINE:
            outline = run_researcher_agent(
                manifest,
                providers.llm,
                enable_wikipedia=settings.enable_wikipedia_grounding,
            )
            store.save_outline(outline)
            manifest.mark_stage(
                stage,
                StageStatus.COMPLETED,
                notes=f"{len(outline.chapters)} chapters planned ({outline.working_title})",
            )

        elif stage == StageName.SCRIPT:
            outline = store.load_outline()
            bundle = run_writer_agent(manifest, outline, store, providers.llm)
            store.save_script_bundle(bundle)
            manifest.mark_stage(
                stage,
                StageStatus.COMPLETED,
                notes=f"{bundle.total_words} words (~{bundle.estimated_minutes:.1f} min)",
            )

        elif stage == StageName.AUDIO:
            bundle = store.load_script_bundle()
            timeline = run_narrator_agent(manifest, bundle, store, providers.tts, settings)
            store.save_audio_timeline(timeline)
            manifest.mark_stage(
                stage,
                StageStatus.COMPLETED,
                notes=f"{timeline.total_duration_seconds / 60.0:.2f} min mastered ({manifest.ambience_mode})",
            )

        elif stage == StageName.VISUALS:
            outline = store.load_outline()
            bundle = store.load_script_bundle()
            timeline = store.load_audio_timeline()
            plan = run_art_director_agent(
                manifest,
                outline,
                bundle,
                timeline,
                store,
                providers.llm,
                providers.image,
                settings,
                replan=force,
            )
            store.save_visual_plan(plan)
            manifest.mark_stage(
                stage,
                StageStatus.COMPLETED,
                notes=f"{len(plan.scenes)} dark painterly scenes ready",
            )

        elif stage == StageName.RENDER:
            timeline = store.load_audio_timeline()
            plan = store.load_visual_plan()
            render_artifact = run_assembler_agent(manifest, timeline, plan, store, settings)
            store.save_render_artifact(render_artifact)
            mb = render_artifact.file_size_bytes / (1024 * 1024)
            manifest.mark_stage(
                stage,
                StageStatus.COMPLETED,
                notes=f"{render_artifact.duration_seconds / 60.0:.2f} min MP4 ({mb:.1f} MB)",
            )

        elif stage == StageName.PACKAGE:
            outline = store.load_outline()
            timeline = store.load_audio_timeline()
            plan = store.load_visual_plan()
            render_artifact = store.load_render_artifact()
            packaging = run_packager_agent(
                manifest,
                outline,
                timeline,
                plan,
                render_artifact,
                store,
                providers.llm,
            )
            store.save_packaging(packaging)
            manifest.mark_stage(
                stage,
                StageStatus.COMPLETED,
                notes=f"Export bundle ready in 06_export/ ({packaging.selected_title})",
            )

        store.save_manifest(manifest)
        return manifest

    except Exception as exc:
        manifest.mark_stage(stage, StageStatus.FAILED, error=str(exc))
        store.save_manifest(manifest)
        raise


def run_pipeline(
    store: ProjectStore,
    settings: Settings,
    *,
    until: StageName = StageName.PACKAGE,
    from_stage: StageName | None = None,
    force: bool = False,
    providers: ProviderBundle | None = None,
    on_event: StageCallback | None = None,
) -> ProjectManifest:
    """Run stages sequentially from the first incomplete stage (or from_stage) up through `until`."""
    manifest = store.load_manifest()
    bundle = providers or build_providers(settings, manifest.providers)

    start_idx = STAGE_ORDER.index(from_stage) if from_stage else 0
    end_idx = STAGE_ORDER.index(until)
    if start_idx > end_idx:
        raise ValueError(f"--from-stage ({from_stage}) cannot be after --until ({until}).")

    # Verify prerequisites before from_stage are completed
    for prereq in STAGE_ORDER[:start_idx]:
        if manifest.stages[prereq].status != StageStatus.COMPLETED:
            raise RuntimeError(
                f"Cannot start at '{from_stage}': prerequisite stage '{prereq.value}' is not completed."
            )

    for stage in STAGE_ORDER[start_idx : end_idx + 1]:
        already_done = manifest.stages[stage].status == StageStatus.COMPLETED
        should_run = force or (from_stage is not None and stage == from_stage) or not already_done

        if not should_run:
            if on_event:
                on_event(stage, "skipped (already completed)")
            continue

        if on_event:
            on_event(stage, "running")
        manifest = run_stage(stage, store, manifest, bundle, settings, force=force)
        if force or from_stage is not None:
            _invalidate_downstream(manifest, stage)
            store.save_manifest(manifest)
        if on_event:
            on_event(stage, f"completed — {manifest.stages[stage].notes or ''}")

    return manifest


def regenerate_item(
    store: ProjectStore,
    settings: Settings,
    *,
    stage: StageName,
    item_id: str,
    providers: ProviderBundle | None = None,
) -> ProjectManifest:
    """Surgically regenerate a single chapter (script/audio) or single scene image (visuals)."""
    manifest = store.load_manifest()
    bundle = providers or build_providers(settings, manifest.providers)

    if stage == StageName.SCRIPT:
        chapter_num = _parse_chapter_number(item_id)
        outline = store.load_outline()
        script_bundle = run_writer_agent(
            manifest, outline, store, bundle.llm, only_chapter=chapter_num
        )
        store.save_script_bundle(script_bundle)
        manifest.mark_stage(
            StageName.SCRIPT,
            StageStatus.COMPLETED,
            notes=f"Regenerated chapter {chapter_num} ({script_bundle.total_words} total words)",
        )
        _invalidate_downstream(manifest, StageName.SCRIPT)

    elif stage == StageName.AUDIO:
        chapter_num = _parse_chapter_number(item_id)
        script_bundle = store.load_script_bundle()
        timeline = run_narrator_agent(
            manifest, script_bundle, store, bundle.tts, settings, only_chapter=chapter_num
        )
        store.save_audio_timeline(timeline)
        manifest.mark_stage(
            StageName.AUDIO,
            StageStatus.COMPLETED,
            notes=f"Regenerated audio for chapter {chapter_num} ({timeline.total_duration_seconds / 60.0:.2f} min total)",
        )
        _invalidate_downstream(manifest, StageName.AUDIO)

    elif stage == StageName.VISUALS:
        outline = store.load_outline()
        script_bundle = store.load_script_bundle()
        timeline = store.load_audio_timeline()
        plan = run_art_director_agent(
            manifest,
            outline,
            script_bundle,
            timeline,
            store,
            bundle.llm,
            bundle.image,
            settings,
            only_scene_id=item_id,
            replan=False,
        )
        if not any(s.scene_id == item_id for s in plan.scenes):
            raise ValueError(f"Scene '{item_id}' not found in visual_plan.json.")
        store.save_visual_plan(plan)
        manifest.mark_stage(
            StageName.VISUALS,
            StageStatus.COMPLETED,
            notes=f"Regenerated {item_id} ({len(plan.scenes)} scenes)",
        )
        _invalidate_downstream(manifest, StageName.VISUALS)

    else:
        raise ValueError("Item-level regeneration is supported for stages: script, audio, visuals.")

    store.save_manifest(manifest)
    return manifest


def _parse_chapter_number(item_id: str) -> int:
    cleaned = item_id.lower().replace("chapter_", "").replace("chapter", "").strip()
    if not cleaned.isdigit():
        raise ValueError(f"Expected chapter number like '2' or 'chapter_02', got '{item_id}'.")
    return int(cleaned)
