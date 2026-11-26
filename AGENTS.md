# Video Factory — Antigravity Agent Instructions

An **Antigravity-native AI video factory** for producing **15–30 minute videos** from a short description.
*(Channel niche, tone, and visual style are isolated and configured in `.agents/rules/style-bible.md`.)*

## Architecture Overview (3 Agents + 4 Scripts)

Antigravity handles creative and editorial stages via **3 specialized agents** (`agents/`).
Deterministic media work (TTS, image generation, video rendering, packaging) is handled by **4 Python scripts** (`scripts/`) sharing a common adapter layer (`providers/`).

| Layer | Location | Responsibility |
| :--- | :--- | :--- |
| **Orchestrator Skill** | `.agents/skills/video-factory/SKILL.md` | End-to-end stage-gated workflow & human review checkpoints |
| **Channel Style Rules** | `.agents/rules/style-bible.md` | Runtime targets, voice/writing guardrails, visual style, and audio rules |
| **Agent 1: Researcher** | `agents/01-researcher.md` | Topic research & section/chapter outline (`01_outline.json`) |
| **Agent 2: Scriptwriter** | `agents/02-scriptwriter.md` | Long-form script drafting & continuity edit (`02_script/chapter_XX.md`) |
| **Agent 3: Art Director** | `agents/03-art-director.md` | Visual scene planning & export metadata (`04_visuals/`, `06_export/`) |
| **Media Scripts** | `scripts/` | `tts_and_master.py`, `generate_images.py`, `render_video.py`, `package_export.py` |
| **Shared Providers** | `providers/` | Pluggable `TTSProvider` & `ImageProvider` adapters (`gemini`, `mock`) |

## Shared Run Artifact Contract (`runs/<slug>/`)

Every video run lives in `runs/<slug>/` so any stage can pause, be edited manually, or resume cleanly:

```text
runs/<slug>/
├── 01_outline.json            # Owned by Agent 1 (Researcher)
├── 02_script/
│   └── chapter_01..XX.md      # Owned by Agent 2 (Scriptwriter)
├── 03_audio/
│   ├── narration_master.wav   # Owned by Script 1 (tts_and_master.py)
│   └── audio_timeline.json    # Exact section start/end timestamps
├── 04_visuals/
│   ├── visual_plan.json       # Owned by Agent 3 (Art Director)
│   └── scene_001..XXX.png     # Owned by Script 2 (generate_images.py)
├── 05_render/
│   └── final_video.mp4        # Owned by Script 3 (render_video.py)
└── 06_export/
    ├── video.mp4              # Owned by Script 4 (package_export.py)
    ├── thumbnail.png
    ├── description.txt
    └── metadata.json          # Drafted by Agent 3, finalized by Script 4
```

## Core Principles

1. **Stage-gated checkpoints:** Pause for user review after `01_outline.json`, `02_script/`, and `04_visuals/` unless the user requests an unattended run.
2. **Preserve manual edits:** Always read existing files in `runs/<slug>/` rather than silently overwriting user edits.
3. **Niche-agnostic core:** Keep tone, subject matter, and visual aesthetics isolated inside `.agents/rules/style-bible.md` so the factory can adapt to any video format.
