# Shared Providers

Pluggable `TTSProvider` and `ImageProvider` adapters shared by `scripts/`.

## Structure
- `base.py` — Abstract `TTSProvider` & `ImageProvider` interfaces plus text chunking helper
- `registry.py` — Resolves providers via `--provider` CLI flags or `.env` (`VF_TTS_PROVIDER`, `VF_IMAGE_PROVIDER`)
- `tts/`
  - `gemini.py` — Google GenAI native TTS (`gemini-2.5-flash-preview-tts`, uses `GEMINI_API_KEY`)
  - `mock.py` — Offline synthetic WAV generator for zero-cost testing
- `image/`
  - `gemini.py` — Google GenAI Imagen (`imagen-3.0-generate-002`, uses `GEMINI_API_KEY`)
  - `mock.py` — Offline 16:9 PNG generator via Pillow for zero-cost testing
