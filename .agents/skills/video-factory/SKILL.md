---
name: video-factory
description: Orchestrates the 3-agent, 4-script stage-gated pipeline that turns a short topic description into a 15-30 minute video export bundle.
---

# Video Factory Orchestrator

Follow this stage-gated sequence whenever the user asks to produce a new 15–30 minute video from a description (or resume an existing run in `runs/<slug>/`).

Always read `.agents/rules/style-bible.md` before starting any creative stage, and never silently overwrite manual user edits in `runs/<slug>/`.

## Python Runner
Use the project virtual environment when invoking scripts:
- `.venv/bin/python` (or `python` when `.venv` is activated)

## Running the 3 Creative Agents
Each creative stage is specified in `agents/`:
- **Researcher:** `agents/01-researcher.md`
- **Scriptwriter:** `agents/02-scriptwriter.md`
- **Art Director:** `agents/03-art-director.md`

When executing a stage, read the corresponding spec file and `.agents/rules/style-bible.md`. You may either delegate the stage to a dedicated subagent defined from that spec (`define_subagent` + `invoke_subagent`) or execute the spec directly while honoring every output schema and self-check.

---

## Pipeline Flow

### 0. Initialize Workspace
- Derive a clean kebab-case `<slug>` from the topic description and create `runs/<slug>/`.
- Confirm **target duration** (15–30 minutes, default 20 minutes) and **media providers** (`--provider gemini` vs `--provider mock` for TTS and images; note TTS and images can use different providers).

### 1. Stage 1 — Research & Outline (`agents/01-researcher.md`)
- Run the Researcher to produce `runs/<slug>/01_outline.json`.
- **Checkpoint 1:** Present the working title, angle, chapter breakdown, word budgets, and sources to the user for approval (or edits) before drafting. Skip pausing only if the user explicitly asked for an unattended run.

### 2. Stage 2 — Scriptwriting & Continuity Edit (`agents/02-scriptwriter.md`)
- Re-read `runs/<slug>/01_outline.json` in case the user edited it manually.
- Run the Scriptwriter (Pass 1 drafting + Pass 2 continuity/style/TTS edit) to produce `runs/<slug>/02_script/chapter_01..XX.md`.
- **Checkpoint 2:** Report per-chapter and total word counts (plus estimated runtime at ~140 WPM) and let the user review or edit any `chapter_XX.md` file directly before audio synthesis.

### 3. Stage 3 — Audio Synthesis & Mastering (`scripts/tts_and_master.py`)
- Run with the Style Bible's delivery and ambience settings:
  ```bash
  .venv/bin/python scripts/tts_and_master.py runs/<slug> \
    --provider <gemini|mock> \
    --ambience brown_noise \
    --ambience-db -30 \
    --voice-style "Narrate like an engaging, thoughtful documentary host: warm, clear, curious, measured pacing, crisp diction, and natural pauses between ideas."
  ```
  *(Swap `--ambience soft_rain` when thematically fitting, or `--ambience none` if the user wants narration only; use `--chapter N` for single-chapter regeneration.)*
- Produces `03_audio/narration_master.wav` and `03_audio/audio_timeline.json`.

### 4. Stage 4 — Visual Planning & Media Generation (`agents/03-art-director.md` + `scripts/generate_images.py`)
- Run the Art Director (Stage 4 procedure) using `03_audio/audio_timeline.json` to write a hybrid `runs/<slug>/04_visuals/visual_plan.json` (mixing `video` hero shots, animated `map` routes, `image` editorial plates, `chapter_card` intros, and `callout` lower-thirds).
- Generate all 16:9 scene PNGs and hero MP4 clips:
  ```bash
  .venv/bin/python scripts/generate_images.py runs/<slug> \
    --provider <gemini|mock> \
    --video-provider <veo|mock|none>
  ```
- **Checkpoint 3:** Present the scene list and let the user inspect frames/clips or surgically regenerate individual scenes (`--scene scene_XXX`) after tweaking prompts in `visual_plan.json`.

### 5. Stage 5 — Video Render (`scripts/render_video.py`)
- Assemble Ken Burns clips, hierarchical crossfades, and H.264/AAC muxing:
  ```bash
  .venv/bin/python scripts/render_video.py runs/<slug> --dim-amount 0.0
  ```
- Produces `05_render/final_video.mp4` and `05_render/render_info.json`.

### 6. Stage 6 — Export Metadata & Packaging (`agents/03-art-director.md` + `scripts/package_export.py`)
- Run the Art Director (Stage 6 procedure) to write `runs/<slug>/06_export/metadata.json` (`selected_title`, `title_options`, `thumbnail_text`, `thumbnail_scene`, `thumbnail_concept`, `description_intro`, `tags`).
- Finalize the export bundle using the Art Director's chosen `thumbnail_scene`:
  ```bash
  .venv/bin/python scripts/package_export.py runs/<slug> --thumbnail-scene <scene_id>
  ```
- Produces `06_export/video.mp4`, `06_export/thumbnail.png`, `06_export/description.txt`, and finalized `06_export/metadata.json`.
- Summarize the finished bundle (duration, file sizes, selected title, chapter markers, and paths) for the user.
