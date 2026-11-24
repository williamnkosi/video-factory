# Video Factory

An **Antigravity-native AI video factory** (**3 agents + 4 scripts**) for producing **15–30 minute videos** from a short description.

## Architecture

- **Creative stages (Antigravity agents in `agents/`):** Research & outline (`01-researcher.md`), long-form scriptwriting & edit (`02-scriptwriter.md`), visual scene planning & export metadata (`03-art-director.md`).
- **Media stages (Python scripts in `scripts/`):**
  1. `scripts/tts_and_master.py` — TTS synthesis + FFmpeg `-16 LUFS` mastering + chapter timeline
  2. `scripts/generate_images.py` — 16:9 scene PNG generation (with single-scene `--scene` regen)
  3. `scripts/render_video.py` — Deterministic FFmpeg Ken Burns, crossfades, and H.264/AAC muxing
  4. `scripts/package_export.py` — 1280×720 thumbnail, `00:00` chapter markers, and `06_export/` bundle
- **Shared providers (`providers/`):** Pluggable `TTSProvider` & `ImageProvider` interfaces (`gemini` + offline `mock`).

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # Add GEMINI_API_KEY locally (or use --provider mock offline)

# Run the 4 media scripts on any runs/<slug>/ created by the Antigravity agents:
python scripts/tts_and_master.py runs/<slug> --provider mock
python scripts/generate_images.py runs/<slug> --provider mock
python scripts/render_video.py runs/<slug>
python scripts/package_export.py runs/<slug>
```
