"""Unit tests for the shared provider layer and script helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from providers.base import chunk_text_for_tts
from providers.registry import get_image_provider, get_tts_provider
from scripts.package_export import format_timestamp
from scripts.tts_and_master import normalize_text_for_speech, parse_chapter_markdown


def test_registry_resolves_mock_providers(tmp_path: Path):
    tts = get_tts_provider("mock")
    wav_out = tts.synthesize_to_wav(text="Hello world. " * 40, output_wav_path=tmp_path / "test.wav")
    assert wav_out.is_file() and wav_out.stat().st_size > 1000

    img = get_image_provider("mock")
    png_out = img.generate_image(
        prompt="Wide 16:9 evening valley over stone arches",
        output_png_path=tmp_path / "scene.png",
        width=640,
        height=360,
    )
    assert png_out.is_file()
    with Image.open(png_out) as pil_img:
        assert pil_img.size == (640, 360)


def test_registry_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown TTS provider"):
        get_tts_provider("nonexistent")
    with pytest.raises(ValueError, match="Unknown image provider"):
        get_image_provider("nonexistent")


def test_gemini_requires_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        get_tts_provider("gemini")
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        get_image_provider("gemini")


def test_chunk_text_for_tts_respects_limit():
    text = "\n\n".join([f"Paragraph {i}. " + ("A clear sentence about clocks. " * 25) for i in range(5)])
    chunks = chunk_text_for_tts(text, max_chars=900)
    assert len(chunks) >= 3
    assert all(len(c) <= 950 for c in chunks)


def test_speech_normalization_and_chapter_parsing(tmp_path: Path):
    sample = "In c. 1660, Louis XIV visited St. Denis and recalled 44 BCE."
    norm = normalize_text_for_speech(sample)
    assert "circa 1660" in norm
    assert "Louis the Fourteenth" in norm
    assert "Saint Denis" in norm
    assert "44 B.C.E." in norm

    md = tmp_path / "chapter_02.md"
    md.write_text("# Chapter 2: Iron Gears\n\nFirst paragraph.\n\nSecond paragraph.\n", encoding="utf-8")
    ch_num, title, body = parse_chapter_markdown(md, fallback_num=1)
    assert ch_num == 2
    assert title == "Iron Gears"
    assert "First paragraph." in body and "# Chapter" not in body


def test_format_timestamp():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(125) == "02:05"
    assert format_timestamp(3661) == "1:01:01"
