"""End-to-end integration test exercising all 6 stages with real FFmpeg rendering."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from video_factory.config import Settings
from video_factory.models import ProviderConfig, StageName, StageStatus
from video_factory.pipeline import regenerate_item, run_pipeline
from video_factory.storage import create_project


def test_full_stage_gated_pipeline_e2e(tmp_path: Path):
    settings = Settings(
        VF_RUNS_DIR=tmp_path,
        VF_VIDEO_WIDTH=640,
        VF_VIDEO_HEIGHT=360,
        VF_VIDEO_FPS=12,
        VF_CROSSFADE_SECONDS=0.5,
        VF_INTRO_SILENCE_SECONDS=0.5,
        VF_CHAPTER_PAUSE_SECONDS=0.5,
        VF_OUTRO_SILENCE_SECONDS=0.5,
        VF_ENABLE_WIKIPEDIA=False,
    )

    store, _manifest = create_project(
        tmp_path,
        "The quiet craft of ancient candle makers",
        target_minutes=2,
        seconds_per_scene=10,
        ambience_mode="brown_noise",
        enable_sleep_dimming=True,
        providers=ProviderConfig(llm="mock", tts="mock", image="mock"),
    )

    # 1) Run stage-gated through script and pause for human review
    m = run_pipeline(store, settings, until=StageName.SCRIPT)
    assert m.stages[StageName.OUTLINE].status == StageStatus.COMPLETED
    assert m.stages[StageName.SCRIPT].status == StageStatus.COMPLETED
    assert m.stages[StageName.AUDIO].status == StageStatus.PENDING

    # 2) Simulate human editing Chapter 1 markdown on disk before Stage 3 Audio
    ch1_md = store.script_dir / "chapter_01.md"
    original = ch1_md.read_text(encoding="utf-8")
    custom_sentence = "Beeswax glowed softly across the old oak workbench."
    ch1_md.write_text(original + f"\n{custom_sentence}\n", encoding="utf-8")

    reloaded_script = store.load_script_bundle()
    assert custom_sentence in reloaded_script.chapters[0].edited_text

    # 3) Continue through visuals
    m = run_pipeline(store, settings, until=StageName.VISUALS)
    assert m.stages[StageName.AUDIO].status == StageStatus.COMPLETED
    assert m.stages[StageName.VISUALS].status == StageStatus.COMPLETED

    # 4) Surgically regenerate a single scene image
    plan_before = store.load_visual_plan()
    first_scene_id = plan_before.scenes[0].scene_id
    m = regenerate_item(store, settings, stage=StageName.VISUALS, item_id=first_scene_id)
    assert m.stages[StageName.RENDER].status == StageStatus.PENDING

    # 5) Finish render & package
    m = run_pipeline(store, settings, until=StageName.PACKAGE)
    assert m.stages[StageName.RENDER].status == StageStatus.COMPLETED
    assert m.stages[StageName.PACKAGE].status == StageStatus.COMPLETED

    # Verify export bundle
    export_mp4 = store.export_dir / "video.mp4"
    thumb_png = store.export_dir / "thumbnail.png"
    desc_txt = store.export_dir / "youtube_description.txt"
    meta_json = store.export_dir / "youtube_metadata.json"

    assert export_mp4.is_file() and export_mp4.stat().st_size > 10_000
    assert thumb_png.is_file()
    assert desc_txt.is_file()
    assert meta_json.is_file()

    # Verify thumbnail dimensions
    with Image.open(thumb_png) as img:
        assert img.size == (1280, 720)

    # Verify chapter timestamps start at 00:00
    desc_content = desc_txt.read_text(encoding="utf-8")
    assert "00:00 —" in desc_content

    # Verify MP4 has valid video & audio streams via ffprobe
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(export_mp4),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    info = json.loads(probe.stdout)
    codec_types = {s["codec_type"] for s in info["streams"]}
    assert codec_types == {"video", "audio"}
    assert float(info["format"]["duration"]) > 4.0
