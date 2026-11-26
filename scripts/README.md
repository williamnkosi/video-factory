# Media Scripts

Deterministic Python CLI scripts invoked after creative stages complete.

1. `tts_and_master.py` — Synthesizes `02_script/chapter_*.md` via `providers.registry.get_tts_provider`, masters to `-16 LUFS`, and writes `03_audio/narration_master.wav` + `audio_timeline.json`.
   ```bash
   python scripts/tts_and_master.py runs/<slug> --provider mock
   ```
2. `generate_images.py` — Generates 16:9 scene PNGs from `04_visuals/visual_plan.json` via `providers.registry.get_image_provider` (supports `--scene scene_004` for single-frame regen).
   ```bash
   python scripts/generate_images.py runs/<slug> --provider mock
   ```
3. `render_video.py` — Deterministic FFmpeg compositor (Ken Burns motion, hierarchical crossfades, optional dimming, H.264 + AAC muxing) writing `05_render/final_video.mp4`.
   ```bash
   python scripts/render_video.py runs/<slug>
   ```
4. `package_export.py` — Composes 1280×720 `thumbnail.png`, builds `00:00` chapter markers, writes `description.txt`, and finalizes `06_export/`.
   ```bash
   python scripts/package_export.py runs/<slug>
   ```
