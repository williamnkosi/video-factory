"""End-to-end test invoking all 4 media scripts sequentially with mock providers and real FFmpeg."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_four_scripts_end_to_end(tmp_path: Path):
    run_dir = tmp_path / "demo-run"
    (run_dir / "02_script").mkdir(parents=True)
    (run_dir / "04_visuals").mkdir(parents=True)
    (run_dir / "06_export").mkdir(parents=True)

    # Minimal artifacts mimicking Agent 1, Agent 2, and Agent 3 outputs
    (run_dir / "01_outline.json").write_text(
        json.dumps({"working_title": "Demo Video", "sources": ["https://example.com/source"]}),
        encoding="utf-8",
    )
    (run_dir / "02_script" / "chapter_01.md").write_text(
        "# Chapter 1: Opening Beat\n\n" + ("A steady narration sentence flows calmly. " * 25),
        encoding="utf-8",
    )
    (run_dir / "02_script" / "chapter_02.md").write_text(
        "# Chapter 2: Closing Beat\n\n" + ("The second chapter continues cleanly without hurry. " * 25),
        encoding="utf-8",
    )

    # Script 1: TTS & audio mastering
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "tts_and_master.py"),
            str(run_dir),
            "--provider",
            "mock",
            "--ambience",
            "brown_noise",
            "--intro-silence",
            "0.5",
            "--chapter-pause",
            "0.5",
            "--outro-silence",
            "0.5",
        ],
        check=True,
    )
    timeline = json.loads((run_dir / "03_audio" / "audio_timeline.json").read_text(encoding="utf-8"))
    assert len(timeline["chapters"]) == 2
    assert timeline["total_duration_seconds"] > 4.0

    # Agent 3 hybrid visual_plan.json (video hero + animated map + image plate + overlays)
    third = timeline["total_duration_seconds"] / 3.0
    (run_dir / "04_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "style_bible": "Minimalist muted vintage editorial illustration, no text",
                "scenes": [
                    {
                        "scene_id": "scene_001",
                        "chapter_number": 1,
                        "media_type": "video",
                        "video_duration_seconds": 2,
                        "start_seconds": 0.0,
                        "duration_seconds": third,
                        "motion": "zoom_in",
                        "chapter_card": {
                            "chapter_number": 1,
                            "title": "Opening Beat",
                            "subtitle": "Southern Plateau · c. 1300 CE",
                        },
                        "callout": {
                            "location": "Great Zimbabwe",
                            "era": "c. 1250 – 1450 CE",
                        },
                        "image_prompt": "Wide 16:9 sunrise over hills, no text",
                        "motion_prompt": "Warm morning light drifting across stone ridges",
                    },
                    {
                        "scene_id": "scene_002",
                        "chapter_number": 1,
                        "media_type": "map",
                        "start_seconds": third,
                        "duration_seconds": third,
                        "motion": "static",
                        "map": {
                            "title": "Gold Trade Corridor",
                            "subtitle": "c. 1250 – 1450 CE",
                            "stops": [
                                {"name": "Great Zimbabwe", "lon": 30.93, "lat": -20.27},
                                {"name": "Sofala", "lon": 34.73, "lat": -20.15},
                                {"name": "Kilwa Kisiwani", "lon": 39.51, "lat": -8.96},
                            ],
                        },
                    },
                    {
                        "scene_id": "scene_003",
                        "chapter_number": 2,
                        "media_type": "image",
                        "start_seconds": third * 2.0,
                        "duration_seconds": third,
                        "motion": "pan_right",
                        "callout": {
                            "location": "Kilwa Kisiwani",
                            "era": "14th Century",
                            "caption": "Swahili Maritime Hub",
                        },
                        "image_prompt": "Wide 16:9 dusk over harbor, no text",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "06_export" / "metadata.json").write_text(
        json.dumps(
            {
                "selected_title": "Demo Video Title",
                "thumbnail_text": "DEMO VIDEO",
                "thumbnail_scene": "scene_001",
                "description_intro": "A clean end-to-end test description.",
                "tags": ["demo", "video"],
            }
        ),
        encoding="utf-8",
    )

    # Script 2: Image + Hero Video generation (+ verify single-scene regeneration works)
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "generate_images.py"),
            str(run_dir),
            "--provider",
            "mock",
            "--video-provider",
            "mock",
            "--width",
            "640",
            "--height",
            "360",
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "generate_images.py"),
            str(run_dir),
            "--provider",
            "mock",
            "--scene",
            "scene_003",
            "--width",
            "640",
            "--height",
            "360",
        ],
        check=True,
    )
    assert (run_dir / "04_visuals" / "scene_001.png").is_file()
    assert (run_dir / "04_visuals" / "scene_001.mp4").is_file()
    assert (run_dir / "04_visuals" / "scene_003.png").is_file()

    # Script 3: Render MP4
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "render_video.py"),
            str(run_dir),
            "--width",
            "640",
            "--height",
            "360",
            "--fps",
            "12",
            "--crossfade",
            "0.5",
        ],
        check=True,
    )
    assert (run_dir / "05_render" / "final_video.mp4").is_file()

    # Script 4: Package export bundle
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "package_export.py"),
            str(run_dir),
        ],
        check=True,
    )

    export_mp4 = run_dir / "06_export" / "video.mp4"
    thumb_png = run_dir / "06_export" / "thumbnail.png"
    desc_txt = run_dir / "06_export" / "description.txt"
    assert export_mp4.is_file() and export_mp4.stat().st_size > 5_000
    assert thumb_png.is_file()
    assert "00:00 — Opening Beat" in desc_txt.read_text(encoding="utf-8")

    with Image.open(thumb_png) as img:
        assert img.size == (1280, 720)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(export_mp4)],
        check=True,
        capture_output=True,
        text=True,
    )
    streams = {s["codec_type"] for s in json.loads(probe.stdout)["streams"]}
    assert streams == {"video", "audio"}
