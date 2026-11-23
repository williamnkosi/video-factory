# Media Scripts (Skeleton)

Deterministic Python scripts invoked by Antigravity after creative stages complete.
*(To be implemented once the agent skeleton is finalized.)*

Planned scripts (4 total):
1. `tts_and_master.py` — Synthesizes chapter narration via `providers/`, normalizes/masters audio, and writes `03_audio/audio_timeline.json`.
2. `generate_images.py` — Generates 16:9 scene PNGs from `04_visuals/visual_plan.json` (with single-scene regeneration support).
3. `render_video.py` — Deterministic FFmpeg video assembly from scene images + mastered audio (`05_render/final_video.mp4`).
4. `package_export.py` — Renders thumbnail, builds chapter timestamps, and assembles the final upload bundle (`06_export/`).
