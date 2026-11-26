"""Google Gemini native image generation provider (16:9 PNG)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from providers.base import ImageProvider


class GeminiImageProvider(ImageProvider):
    """Generates 16:9 scene frames using Google GenAI native image generation."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-image",
    ) -> None:
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Add it to your local .env or use '--provider mock'."
            )
        from google import genai

        self.client = genai.Client(api_key=api_key)
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

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="16:9"),
            ),
        )
        image_bytes = _extract_image_bytes(response)
        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(image_bytes)) as img:
            resized = img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
            resized.save(output_png_path, format="PNG")
        return output_png_path


def _extract_image_bytes(response) -> bytes:
    """Extract inline image bytes from a Gemini IMAGE generate_content response."""
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                mime = (getattr(inline, "mime_type", "") or "").lower()
                if not mime or mime.startswith("image/"):
                    return inline.data
    raise RuntimeError("Gemini image response contained no inline image data.")
