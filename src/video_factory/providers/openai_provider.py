"""OpenAI adapter (GPT LLM, OpenAI TTS with chunking, and GPT Image / DALL-E)."""

from __future__ import annotations

import base64
import io
import json
import subprocess
import tempfile
from pathlib import Path
from typing import TypeVar

import httpx
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


def _get_openai_client(api_key: str):
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Add it to .env or switch provider to 'gemini' or 'mock'."
        )
    from openai import OpenAI

    return OpenAI(api_key=api_key)


class OpenAILLMProvider(LLMProvider):
    """OpenAI chat completions provider for prose and structured JSON."""

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        self.client = _get_openai_client(api_key)
        self.model = model

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return (completion.choices[0].message.content or "").strip()

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> T:
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        augmented_prompt = (
            f"{user_prompt}\n\n"
            "Return ONLY valid JSON conforming strictly to this JSON Schema:\n"
            f"```json\n{schema_json}\n```"
        )
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": augmented_prompt},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        data = extract_json_payload(content)
        return response_model.model_validate(data)


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS provider supporting gpt-4o-mini-tts instructions and safe chunking."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini-tts",
        voice: str = "onyx",
    ) -> None:
        self.client = _get_openai_client(api_key)
        self.model = model
        self.voice = voice

    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav_path: Path,
        voice_instructions: str | None = None,
    ) -> Path:
        chunks = chunk_text_for_tts(text, max_chars=3400)
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        instructions = (
            voice_instructions
            or "Speak in a calm, warm, soft, unhurried late-night documentary voice. "
            "Maintain an even, gentle volume with unhurried pauses between sentences so listeners can drift to sleep."
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            part_files: list[Path] = []
            for idx, chunk in enumerate(chunks, start=1):
                part_path = Path(tmp_dir) / f"part_{idx:03d}.wav"
                kwargs: dict = {
                    "model": self.model,
                    "voice": self.voice,
                    "input": chunk,
                    "response_format": "wav",
                }
                if "gpt-4o" in self.model:
                    kwargs["instructions"] = instructions

                with self.client.audio.speech.with_streaming_response.create(**kwargs) as resp:
                    resp.stream_to_file(part_path)
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


class OpenAIImageProvider(ImageProvider):
    """OpenAI Image API adapter (gpt-image-1 or dall-e-3)."""

    def __init__(self, api_key: str, model: str = "gpt-image-1") -> None:
        self.client = _get_openai_client(api_key)
        self.model = model

    def generate_image(
        self,
        *,
        prompt: str,
        output_png_path: Path,
        width: int = 1920,
        height: int = 1080,
    ) -> Path:
        size = "1536x1024" if self.model.startswith("gpt-image") else "1792x1024"
        result = self.client.images.generate(
            model=self.model,
            prompt=prompt,
            size=size,
            n=1,
        )
        item = result.data[0]
        if getattr(item, "b64_json", None):
            image_bytes = base64.b64decode(item.b64_json)
        elif getattr(item, "url", None):
            resp = httpx.get(item.url, timeout=60.0)
            resp.raise_for_status()
            image_bytes = resp.content
        else:
            raise RuntimeError("OpenAI image generation returned neither b64_json nor url.")

        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(image_bytes)) as img:
            resized = img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
            resized.save(output_png_path, format="PNG")
        return output_png_path
