"""Google Gemini adapter (LLM, Imagen 3 image generation, and Gemini TTS)."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import TypeVar

from PIL import Image
from pydantic import BaseModel

from video_factory.providers.base import (
    ImageProvider,
    LLMProvider,
    TTSProvider,
    chunk_text_for_tts,
    extract_json_payload,
)

T = TypeVar("T", bound=BaseModel)


def _get_genai_client(api_key: str):
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Add it to .env or switch provider to 'openai' or 'mock'."
        )
    from google import genai

    return genai.Client(api_key=api_key)


class GeminiLLMProvider(LLMProvider):
    """Google Gemini text & structured JSON provider via google-genai SDK."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self.client = _get_genai_client(api_key)
        self.model = model

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return (response.text or "").strip()

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> T:
        from google.genai import types

        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        augmented_prompt = (
            f"{user_prompt}\n\n"
            "Return ONLY valid JSON conforming strictly to this JSON Schema:\n"
            f"```json\n{schema_json}\n```"
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=augmented_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
        )
        data = extract_json_payload(response.text or "{}")
        return response_model.model_validate(data)


class GeminiImageProvider(ImageProvider):
    """Google Imagen provider via google-genai SDK."""

    def __init__(self, api_key: str, model: str = "imagen-3.0-generate-002") -> None:
        self.client = _get_genai_client(api_key)
        self.model = model

    def generate_image(
        self,
        *,
        prompt: str,
        output_png_path: Path,
        width: int = 1920,
        height: int = 1080,
    ) -> Path:
        from google.genai import types

        result = self.client.models.generate_images(
            model=self.model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                output_mime_type="image/png",
            ),
        )
        if not result.generated_images:
            raise RuntimeError("Gemini Imagen returned no images.")

        image_bytes = result.generated_images[0].image.image_bytes
        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(image_bytes)) as img:
            resized = img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
            resized.save(output_png_path, format="PNG")
        return output_png_path


class GeminiTTSProvider(TTSProvider):
    """Google Gemini native TTS preview provider (24kHz 16-bit PCM -> WAV)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-preview-tts",
        voice_name: str = "Enceladus",
    ) -> None:
        self.client = _get_genai_client(api_key)
        self.model = model
        self.voice_name = voice_name

    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav_path: Path,
        voice_instructions: str | None = None,
    ) -> Path:
        from google.genai import types

        chunks = chunk_text_for_tts(text, max_chars=2400)
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        style_prefix = (
            voice_instructions
            or "Read aloud in a warm, calm, unhurried, soothing late-night documentary voice:"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            part_files: list[Path] = []
            for idx, chunk in enumerate(chunks, start=1):
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=f"{style_prefix}\n\n{chunk}",
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=self.voice_name
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
    """Pull raw PCM bytes from a Gemini AUDIO response candidate."""
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return inline.data
    raise RuntimeError("Gemini TTS response contained no inline audio data.")
