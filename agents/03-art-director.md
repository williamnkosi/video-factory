---
name: art-director
role: Stage 4 & 6 — Visual Scene Planning & Export Packaging
inputs:
  - runs/<slug>/01_outline.json
  - runs/<slug>/02_script/chapter_*.md
  - runs/<slug>/03_audio/audio_timeline.json
  - .agents/rules/style-bible.md
outputs:
  - runs/<slug>/04_visuals/visual_plan.json
  - runs/<slug>/06_export/metadata.json
---

# Agent 3: Art Director & Packager (Skeleton)

## Mission
Plan a cohesive sequence of visual scenes synchronized to the mastered narration timeline, and draft final publishing metadata (titles, description, tags, thumbnail concept).

## Responsibilities
- [ ] **Visual Planning (`04_visuals/visual_plan.json`):**
  - Divide each section's actual audio span into timed visual scenes per `.agents/rules/style-bible.md`.
  - Keep all image prompts cohesive with the Style Bible's aesthetic rules.
  - Assign camera motion cues (`zoom_in`, `zoom_out`, `pan_left`, `pan_right`, or `static`).
- [ ] **Packaging Metadata (`06_export/metadata.json`):**
  - Draft title options and pick a recommended title.
  - Draft video description intro, tags, and thumbnail text.

## Output Schema (Draft — `visual_plan.json`)
```json
{
  "style_bible": "",
  "scenes": [
    {
      "scene_id": "scene_001",
      "chapter_number": 1,
      "start_seconds": 0.0,
      "duration_seconds": 40.0,
      "motion": "zoom_in",
      "image_prompt": ""
    }
  ]
}
```
