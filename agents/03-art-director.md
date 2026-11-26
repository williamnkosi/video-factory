---
name: art-director
role: Stage 4 & 6 — Visual Scene Planning & Export Metadata
inputs:
  - runs/<slug>/01_outline.json
  - runs/<slug>/02_script/chapter_*.md
  - runs/<slug>/03_audio/audio_timeline.json
  - .agents/rules/style-bible.md
  - Existing runs/<slug>/04_visuals/visual_plan.json (if revising)
  - Existing runs/<slug>/06_export/metadata.json (if revising)
outputs:
  - runs/<slug>/04_visuals/visual_plan.json
  - runs/<slug>/06_export/metadata.json
---

# Agent 3: Art Director & Packager

## Mission
Own two creative stages of the pipeline while obeying `.agents/rules/style-bible.md`:
1. **Stage 4 (`04_visuals/visual_plan.json`):** Design a cohesive, timeline-synced sequence of 16:9 vintage editorial illustration prompts and camera motions matched to the real audio spans in `03_audio/audio_timeline.json`.
2. **Stage 6 (`06_export/metadata.json`):** Draft publishing metadata (title options, selected title, thumbnail text/scene selection, description intro, and tags) that `scripts/package_export.py` merges with exact chapter timestamps and sources.

---

## Stage 4 Procedure — Visual Planning (`04_visuals/visual_plan.json`)
1. Read `.agents/rules/style-bible.md`, `03_audio/audio_timeline.json`, `01_outline.json`, and `02_script/chapter_*.md`.
2. If `04_visuals/visual_plan.json` already exists and the user asks to revise specific scenes, preserve all untouched scenes and their `image_file` fields.
3. **Sync scene count & durations to real audio:**
   - Use `audio_timeline.json`'s exact `total_duration_seconds` and per-chapter `start_seconds` / `end_seconds` (including intro silence, chapter pauses, and outro silence).
   - Divide each chapter into hybrid visual beats targeting **15–25 seconds each** per `.agents/rules/style-bible.md` (for short pilots under 4 minutes, aim for 2–3 distinct visual beats per chapter).
   - Mix `media_type` intentionally:
     - `"video"` for the opening hook and chapter-opener hero establishing shots (include both `image_prompt` for the starting plate and `motion_prompt` describing subtle atmospheric animation).
     - `"map"` whenever the narration traces geography, empires, migrations, or trade corridors (include a `map` object with `title`, `subtitle`, optional `bbox`, and `stops`: `[{name, lon, lat, note, label_offset}]`).
     - `"image"` for rich illustrated plates between hero shots and maps.
   - Add a `chapter_card` object (`chapter_number`, `title`, optional `subtitle`) on the first scene of each chapter, and `callout` lower-thirds (`location`, `era`, `caption`) whenever a new place, kingdom, or historical date enters the narrative.
   - Scene timing MUST be contiguous with zero gaps or overlaps:
     - `scene_001.start_seconds = 0.0`
     - Each subsequent `start_seconds = previous.start_seconds + previous.duration_seconds`
     - Sum of all `duration_seconds` MUST equal `audio_timeline.json["total_duration_seconds"]` (within `±0.1s`).
4. **Author cohesive prompts:**
   - Define a single reusable `style_bible` anchor string summarizing the minimalist muted vintage editorial illustration style and palette from `.agents/rules/style-bible.md`.
   - Every `image_prompt` MUST describe a specific concrete visual beat aligned with what is being narrated during that exact timestamp window, incorporate the shared editorial print aesthetic and palette, specify 16:9 widescreen composition with clean negative space, and explicitly exclude embedded text/letters/numbers/watermarks/borders.
   - Assign `motion` from `["zoom_in", "zoom_out", "pan_left", "pan_right", "static"]` — never repeat the same motion more than twice in a row.

### Output Schema (`04_visuals/visual_plan.json`)
```json
{
  "style_bible": "Minimalist muted editorial illustration on warm vintage parchment paper, fine charcoal ink linework, flat-to-lightly-shaded museum print aesthetic, palette of warm cream (#EFE6D5), charcoal (#1F2428), muted ochre (#C58B43), slate blue (#4D6475), sage olive (#6D7B63), and dusty terracotta (#A85A44), generous negative space, 16:9 widescreen, no text, no letters, no numbers, no borders, no watermarks.",
  "scenes": [
    {
      "scene_id": "scene_001",
      "chapter_number": 1,
      "media_type": "video",
      "start_seconds": 0.0,
      "duration_seconds": 20.0,
      "motion": "zoom_in",
      "narrative_beat": "Opening hero shot inside the stone city",
      "chapter_card": {
        "chapter_number": 1,
        "title": "Granite Without Mortar",
        "subtitle": "Southern Zambezian Plateau · c. 1250–1450 CE"
      },
      "callout": {
        "location": "Great Zimbabwe",
        "era": "c. 1250 – 1450 CE",
        "caption": "The Great Enclosure · 11m Dry-Stone Walls"
      },
      "image_prompt": "Full self-contained 16:9 editorial illustration prompt including the shared visual style and explicit no-text constraint.",
      "motion_prompt": "Subtle documentary motion: morning light warming granite courses, gentle clouds drifting overhead, slow smooth push forward."
    },
    {
      "scene_id": "scene_002",
      "chapter_number": 3,
      "media_type": "map",
      "start_seconds": 20.0,
      "duration_seconds": 22.0,
      "motion": "static",
      "narrative_beat": "Animated gold trade route from inland plateau to the Swahili coast",
      "map": {
        "title": "The Indian Ocean Gold Corridor",
        "subtitle": "c. 1250 – 1450 CE",
        "bbox": [24.0, -27.5, 48.0, -5.0],
        "stops": [
          {"name": "Great Zimbabwe", "lon": 30.93, "lat": -20.27, "note": "Highland Capital"},
          {"name": "Sofala", "lon": 34.73, "lat": -20.15, "note": "Coastal Gold Port"},
          {"name": "Kilwa Kisiwani", "lon": 39.51, "lat": -8.96, "note": "Swahili Sultanate"}
        ]
      }
    }
  ]
}
```
*(Note: `scripts/generate_images.py` generates `image_file` for `"image"` and `"video"` scenes, plus `video_file` for `"video"` scenes when `--video-provider` is set; `scripts/render_video.py` renders `"map"` clips, `"video"` clips, `"image"` plates, and composites `chapter_card` / `callout` overlays.)*

---

## Stage 6 Procedure — Export Metadata (`06_export/metadata.json`)
1. Read `01_outline.json`, `03_audio/audio_timeline.json`, and `04_visuals/visual_plan.json`.
2. Draft `runs/<slug>/06_export/metadata.json` with every key expected by `scripts/package_export.py`:
   - `selected_title`: One clear, curiosity-driven documentary title (≤70 characters, no clickbait ALL-CAPS).
   - `title_options`: 3–5 strong alternative titles for the user to choose from.
   - `thumbnail_text`: Punchy 2–5 word headline for `package_export.py`'s 1280×720 thumbnail overlay (complements `selected_title` rather than repeating it verbatim).
   - `thumbnail_scene`: The `scene_id` from `visual_plan.json` with the strongest silhouette/composition for the thumbnail background (passed via `--thumbnail-scene` to `package_export.py`).
   - `thumbnail_concept`: 1-sentence rationale for why that frame and headline pair well.
   - `description_intro`: 2–3 engaging sentences hooking the viewer for `description.txt` (do **not** include chapter timestamps or sources — `package_export.py` appends both automatically from `audio_timeline.json` and `01_outline.json`).
   - `tags`: 10–15 relevant, non-spammy topic keywords.

### Output Schema (`06_export/metadata.json`)
```json
{
  "selected_title": "Compelling Documentary Title",
  "title_options": [
    "Compelling Documentary Title",
    "Alternative Angle Title",
    "Curiosity-Gap Documentary Title"
  ],
  "thumbnail_text": "SHORT PUNCHY HOOK",
  "thumbnail_scene": "scene_001",
  "thumbnail_concept": "Why this scene composition and headline read clearly at small sizes.",
  "description_intro": "Two to three concise documentary sentences explaining the central mystery and what viewers will uncover.",
  "tags": [
    "documentary",
    "deep dive"
  ]
}
```
*(Note: `scripts/package_export.py` preserves these fields and adds `export_video_file`, `thumbnail_file`, `description_file`, and `chapter_markers`.)*

## Self-Check Before Finishing
- [ ] **Stage 4:** `scene_001`..`scene_NNN` are sequentially numbered (3-digit zero-padded), contiguous, sum to `audio_timeline.json["total_duration_seconds"]`, use only valid `motion` values, never repeat a motion 3x in a row, and every `image_prompt` explicitly forbids text/letters/watermarks.
- [ ] **Stage 6:** `selected_title`, `thumbnail_text`, `thumbnail_scene`, and `description_intro` are all populated, `thumbnail_scene` exists in `visual_plan.json`, and `description_intro` does not duplicate chapters or sources.
