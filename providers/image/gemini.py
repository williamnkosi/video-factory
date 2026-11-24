"""Google Gemini Imagen provider (16:9 PNG)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from providers.base import ImageProvider


class GeminiImageProvider(ImageProvider):
    """Generates 16:9 scene frames using Google GenAI Imagen."""

    def __init__(
        self,
        api_key: str,
        model: str = "imagen-3.0-generate-002",
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
            raise RuntimeError("Gemini Imagen returned no generated images.")

        image_bytes = result.generated_images[0].image.image_bytes
        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(image_bytes)) as img:
            resized = img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
            resized.save(output_png_path, format="PNG")
        return output_png_path
