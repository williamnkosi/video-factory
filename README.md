# Video Factory — Sleepy History AI Pipeline (MVP)

A stage-gated, checkpointable AI agent factory that transforms a short topic description into a ready-to-upload **15–30 minute calm history documentary** modeled on channels like `@TheSleepyHistoryChannel`.

## What It Builds (Local Export Bundle)

Given a topic prompt, the pipeline runs 6 resumable stages and produces a complete upload bundle in `runs/<slug>/06_export/`:

- `video.mp4` — 1080p H.264/AAC documentary with slow Ken Burns motion, 2s crossfades, dark chiaroscuro scenes, progressive sleep dimming, mastered narration (`-16 LUFS`, warm EQ, peak limiter), and procedural brown-noise/rain ambience.
- `thumbnail.png` — 1280×720 dark painterly thumbnail with warm serif typography.
- `youtube_description.txt` — Copy-paste ready description with exact `00:00` chapter timestamps and research sources.
- `youtube_metadata.json` — Title options, tags, chapter markers, and YouTube AI disclosure guidance.

## Architecture (6 Checkpointable Stages)

1. **`outline`** — Historical Researcher & Showrunner agent (with best-effort Wikipedia grounding) creates an editable `01_outline.json` Chapter Bible with a sleep energy curve (`gentle_opening` → `calm_immersion` → `deep_drifting` → `soft_winding_down`).
2. **`script`** — Chapter-by-chapter literary writer with rolling continuity memory + Anti-AI-Slop & Sleep Editor critic pass. Writes human-editable Markdown chapters in `02_script/chapter_XX.md`.
3. **`audio`** — Speech normalizer (dates, regnal numerals) + chunked TTS + FFmpeg sleep mastering (`-16 LUFS`, warm treble roll-off, limiter) + procedural ambient soundscape (`brown_noise` / `soft_rain` / `none`).
4. **`visuals`** — Visual Art Director plans evenly paced scenes locked to the dark Dutch Golden Age chiaroscuro Style Bible (`04_visuals/visual_plan.json`) and generates 16:9 PNG frames.
5. **`render`** — Deterministic FFmpeg compositor: smooth Ken Burns pans/zooms, vignette, progressive brightness dimming in the second half, hierarchical crossfades, and audio muxing.
6. **`package`** — Composes thumbnail, titles, SEO description, chapter timestamps, and export bundle in `06_export/`.

## Quick Start

### 1. Prerequisites
- Python 3.11+
- `ffmpeg` and `ffprobe` on `PATH`

### 2. Install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

### 3. Dry-Run Offline Test (Zero API Cost)
Test the entire pipeline end-to-end—including real FFmpeg audio mastering and 1080p MP4 rendering—using the built-in `mock` providers:

```bash
vfactory create "How ancient spice merchants navigated monsoon winds" \
  --minutes 2 --llm mock --tts mock --image mock --auto
```

### 4. Real 15–30 Minute Production Run (Stage-Gated)
Add `GEMINI_API_KEY` and/or `OPENAI_API_KEY` to `.env` (providers can be mixed & matched independently).

```bash
# Estimate API spend first
vfactory estimate --minutes 20 --llm gemini --tts openai --image gemini

# Step 1: Create project and pause after outline
vfactory create "The quiet history of medieval clockmakers and candlelit guilds" --minutes 20

# Inspect/edit runs/<slug>/01_outline.json, then write the script & pause
vfactory run <slug> --until script

# Optionally tweak prose in runs/<slug>/02_script/chapter_01.md (edits are picked up automatically!)
# Then finish audio -> visuals -> render -> package
vfactory run <slug>
```

### 5. Surgical Regeneration (No Wasted Credits)
Fix one chapter or one scene image without rebuilding the rest:

```bash
vfactory regenerate <slug> --stage visuals --item scene_004
vfactory regenerate <slug> --stage script --item chapter_02
vfactory run <slug>   # Re-runs only invalidated downstream stages
```

## Provider Matrix

Set in `.env` or via CLI flags (`--llm`, `--tts`, `--image`):

| Role | `gemini` (Google GenAI) | `openai` (OpenAI) | `mock` (Offline) |
| :--- | :--- | :--- | :--- |
| **LLM** | `gemini-2.5-flash` (configurable) | `gpt-4.1-mini` (configurable) | Deterministic sleep prose |
| **TTS** | `gemini-2.5-flash-preview-tts` | `gpt-4o-mini-tts` / `tts-1-hd` | Soft synthetic WAV |
| **Image** | `imagen-3.0-generate-002` | `gpt-image-1` / `dall-e-3` | Dark chiaroscuro PNG |
