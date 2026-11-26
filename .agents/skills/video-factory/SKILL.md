---
name: video-factory
description: Orchestrates the 3-agent, 4-script stage-gated pipeline that turns a short topic description into a 15-30 minute video export bundle.
---

# Video Factory Orchestrator

Follow this stage-gated sequence whenever the user asks to produce a new 15–30 minute video from a description.

## Pipeline Flow

1. **Initialize Workspace**
   - Create `runs/<slug>/` from the topic description and confirm target duration (15–30 min, default 20 min).

2. **Stage 1 — Research & Outline (`agents/01-researcher.md`)**
   - Invoke the Researcher agent to produce `runs/<slug>/01_outline.json`.
   - **Checkpoint:** Present the outline to the user for approval before drafting.

3. **Stage 2 — Scriptwriting & Edit (`agents/02-scriptwriter.md`)**
   - Invoke the Scriptwriter agent to draft and edit `runs/<slug>/02_script/chapter_01..XX.md`.
   - **Checkpoint:** Let the user review or edit chapter Markdown files directly.

4. **Stage 3 — Audio & Mastering (`scripts/tts_and_master.py`)**
   - Run: `python scripts/tts_and_master.py runs/<slug> [--provider gemini|mock]`
   - Produces `03_audio/narration_master.wav` and `03_audio/audio_timeline.json`.

5. **Stage 4 — Visual Planning & Image Generation (`agents/03-art-director.md` + `scripts/generate_images.py`)**
   - Invoke the Art Director agent to write `04_visuals/visual_plan.json` synced to `audio_timeline.json`.
   - Run: `python scripts/generate_images.py runs/<slug> [--provider gemini|mock]`
   - **Checkpoint:** Allow surgical regeneration of any individual scene (`--scene scene_XXX`).

6. **Stage 5 & 6 — Render & Export (`scripts/render_video.py` + `scripts/package_export.py`)**
   - Run: `python scripts/render_video.py runs/<slug>`
   - Draft title/description/tags via Art Director agent (`06_export/metadata.json`).
   - Run: `python scripts/package_export.py runs/<slug>` to finalize `06_export/` (`video.mp4`, `thumbnail.png`, `description.txt`, `metadata.json`).
