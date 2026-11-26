"""Google Gemini native TTS provider (24kHz 16-bit PCM -> WAV)."""

from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path

from providers.base import TTSProvider, chunk_text_for_tts


class GeminiTTSProvider(TTSProvider):
    """Synthesizes long-form chapter narration using Google GenAI native TTS."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-preview-tts",
        default_voice: str = "Charon",
    ) -> None:
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Add it to your local .env or use '--provider mock'."
            )
        from google import genai
        from google.genai import types

        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1beta"),
        )
        self.model = model
        self.default_voice = default_voice

    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav_path: Path,
        voice: str | None = None,
        style_instructions: str | None = None,
    ) -> Path:
        from google.genai import types

        voice_name = voice or self.default_voice
        chunks = chunk_text_for_tts(text, max_chars=2400)
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)

        prefix = (
            f"{style_instructions.strip()}\n\n"
            if style_instructions and style_instructions.strip()
            else "Read aloud clearly with natural, steady pacing:\n\n"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            part_files: list[Path] = []
            for idx, chunk in enumerate(chunks, start=1):
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=f"{prefix}{chunk}",
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name
                                )
                            )
                        ),
                    ),
                )
                pcm_bytes = _extract_pcm_audio(response)
                part_path = Path(tmp_dir) / f"part_{idx:03d}.wav"
                with wave.open(str(part_path), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(pcm_bytes)
                part_files.append(part_path)

            if len(part_files) == 1:
                output_wav_path.write_bytes(part_files[0].read_bytes())
            else:
                concat_list = Path(tmp_dir) / "concat.txt"
                concat_list.write_text(
                    "\n".join(f"file '{p.as_posix()}'" for p in part_files),
                    encoding="utf-8",
                )
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat_list),
                        "-c:a",
                        "pcm_s16le",
                        str(output_wav_path),
                    ],
                    check=True,
                    capture_output=True,
                )

        return output_wav_path


def _extract_pcm_audio(response) -> bytes:
    """Extract raw inline PCM bytes from a Gemini AUDIO response."""
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return inline.data
    raise RuntimeError("Gemini TTS response contained no inline audio data.")
