"""Google GenAI Veo video generation provider (Image-to-Video / Text-to-Video)."""

from __future__ import annotations

import time
from pathlib import Path

from providers.base import VideoProvider


class VeoVideoProvider(VideoProvider):
    """Animates hero documentary scenes using Google GenAI Veo."""

    def __init__(
        self,
        api_key: str,
        model: str = "veo-3.0-generate-001",
        poll_interval_seconds: float = 5.0,
        timeout_seconds: float = 360.0,
    ) -> None:
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Add it to your local .env or use '--video-provider mock'."
            )
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds

    def generate_video(
        self,
        *,
        prompt: str,
        output_mp4_path: Path,
        image_path: Path | None = None,
        duration_seconds: int = 8,
        width: int = 1920,
        height: int = 1080,
        fps: int = 24,
    ) -> Path:
        from google.genai import types

        clamped_duration = max(4, min(8, int(duration_seconds)))
        image_arg = (
            types.Image.from_file(location=str(image_path))
            if image_path is not None and image_path.exists()
            else None
        )

        operation = self.client.models.generate_videos(
            model=self.model,
            prompt=prompt,
            image=image_arg,
            config=types.GenerateVideosConfig(
                aspect_ratio="16:9",
                duration_seconds=clamped_duration,
                negative_prompt="text, letters, watermark, borders, modern logos, shaky camera",
            ),
        )

        deadline = time.monotonic() + self.timeout_seconds
        while not getattr(operation, "done", False):
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"Veo video generation timed out after {self.timeout_seconds:.0f}s."
                )
            time.sleep(self.poll_interval_seconds)
            operation = self.client.operations.get(operation)

        video_bytes = _extract_video_bytes(self.client, operation)
        output_mp4_path.parent.mkdir(parents=True, exist_ok=True)
        output_mp4_path.write_bytes(video_bytes)
        return output_mp4_path


def _extract_video_bytes(client, operation) -> bytes:
    """Extract raw MP4 bytes from a completed Veo GenerateVideosOperation."""
    error = getattr(operation, "error", None)
    if error:
        raise RuntimeError(f"Veo video generation failed: {error}")

    response = getattr(operation, "response", None)
    generated = getattr(response, "generated_videos", None) or []
    if not generated:
        raise RuntimeError("Veo operation completed with no generated videos.")

    video_obj = getattr(generated[0], "video", None)
    if video_obj is None:
        raise RuntimeError("Veo generated video entry contained no video payload.")

    raw_bytes = getattr(video_obj, "video_bytes", None)
    if raw_bytes:
        return raw_bytes

    downloaded = client.files.download(file=video_obj)
    if isinstance(downloaded, (bytes, bytearray)):
        return bytes(downloaded)
    if hasattr(downloaded, "read"):
        return downloaded.read()
    raise RuntimeError("Unable to read MP4 bytes from Veo video download response.")
