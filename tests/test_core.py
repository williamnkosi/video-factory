"""Unit tests for core helpers, speech normalization, anti-slop lint, and storage."""

from __future__ import annotations

from pathlib import Path

from video_factory.agents.narrator import normalize_text_for_speech
from video_factory.agents.packager import format_timestamp
from video_factory.agents.writer import detect_sleep_script_issues, sanitize_spoken_prose
from video_factory.models import ProviderConfig, StageName
from video_factory.pipeline import estimate_project_cost
from video_factory.providers.base import chunk_text_for_tts, extract_json_payload
from video_factory.storage import create_project, slugify


def test_slugify_handles_punctuation():
    assert slugify("The Sleepy History of Rome's Aqueducts!") == "the-sleepy-history-of-romes-aqueducts"
    assert slugify("   ") == "sleepy-history"


def test_extract_json_payload_handles_fences():
    raw = 'Here is your output:\n```json\n{"title": "Quiet Rome", "count": 3}\n```'
    parsed = extract_json_payload(raw)
    assert parsed == {"title": "Quiet Rome", "count": 3}


def test_chunk_text_for_tts_respects_limit():
    text = "\n\n".join([f"Paragraph {i}. " + ("Soft rain fell over stone roofs. " * 20) for i in range(6)])
    chunks = chunk_text_for_tts(text, max_chars=900)
    assert len(chunks) >= 3
    assert all(len(c) <= 950 for c in chunks)


def test_speech_normalization_regnal_and_dates():
    sample = "In c. 1660, King Louis XIV walked past St. Denis, recalling 44 BCE."
    normalized = normalize_text_for_speech(sample)
    assert "circa 1660" in normalized
    assert "Louis the Fourteenth" in normalized
    assert "Saint Denis" in normalized
    assert "44 B.C.E." in normalized


def test_sleep_script_lint_and_sanitize():
    bad = "# Heading\nLet's dive in! We will delve into a rich tapestry [pause 2s] of stone."
    issues = detect_sleep_script_issues(bad)
    assert len(issues) >= 3

    cleaned = sanitize_spoken_prose(bad)
    assert "!" not in cleaned
    assert "# Heading" not in cleaned
    assert "[pause" not in cleaned


def test_format_timestamp():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(65) == "01:05"
    assert format_timestamp(3661) == "1:01:01"


def test_cost_estimate_and_project_creation(tmp_path: Path):
    store, manifest = create_project(
        tmp_path,
        "How medieval bells kept time",
        target_minutes=20,
        providers=ProviderConfig(llm="gemini", tts="openai", image="gemini"),
    )
    assert store.manifest_path.exists()
    assert manifest.stages[StageName.OUTLINE].status == "pending"

    est = estimate_project_cost(manifest)
    assert est.estimated_words == 2600
    assert est.estimated_images == 30
    assert est.total_usd > 0
