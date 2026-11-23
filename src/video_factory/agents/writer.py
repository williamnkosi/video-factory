"""Stage 2: Chapter-by-chapter literary writer + Sleep Continuity Critic."""

from __future__ import annotations

import re

from video_factory.agents.prompts import (
    BANNED_CLICHES,
    EDITOR_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
)
from video_factory.models import (
    ChapterOutline,
    ChapterScript,
    OutlineArtifact,
    ProjectManifest,
    ScriptBundle,
)
from video_factory.providers.base import LLMProvider
from video_factory.storage import ProjectStore


def detect_sleep_script_issues(text: str) -> list[str]:
    """Deterministic lint pass catching jarring punctuation and AI clichés."""
    issues: list[str] = []
    lowered = text.lower()
    if "!" in text:
        issues.append("Contains exclamation mark(s) which break calm bedtime pacing.")
    for cliche in BANNED_CLICHES:
        if cliche in lowered:
            issues.append(f"Contains banned cliché: '{cliche}'.")
    if re.search(r"^\s*#{1,6}\s+", text, re.MULTILINE):
        issues.append("Contains markdown headings inside spoken narration.")
    if re.search(r"^\s*[-*]\s+", text, re.MULTILINE):
        issues.append("Contains bullet lists inside spoken narration.")
    return issues


def sanitize_spoken_prose(text: str) -> str:
    """Final safety cleanup ensuring clean narration prose without markdown artifacts."""
    cleaned = re.sub(r"^\s*#{1,6}\s+.*$", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"\[(?:pause|silence|music|fade)[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("*", "")
    cleaned = cleaned.replace("!", ".")
    # Normalize blank lines
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned.strip()) if p.strip()]
    return "\n\n".join(paragraphs)


def _write_single_chapter(
    *,
    chapter: ChapterOutline,
    outline: OutlineArtifact,
    continuity_memory: list[str],
    llm: LLMProvider,
) -> tuple[str, str, list[str]]:
    memory_block = (
        "\n".join(f"- {item}" for item in continuity_memory)
        if continuity_memory
        else "- (This is the opening chapter.)"
    )
    facts_block = "\n".join(f"- {f}" for f in chapter.key_historical_facts)
    sensory_block = "\n".join(f"- {s}" for s in chapter.sensory_details)

    draft_prompt = (
        f"Documentary Title: {outline.working_title}\n"
        f"Historical Era: {outline.historical_era}\n"
        f"Setting: {outline.geographic_setting}\n"
        f"Editorial Angle: {outline.editorial_angle}\n"
        f"Narrator Tone: {outline.narrator_tone_notes}\n\n"
        f"Chapter {chapter.chapter_number} of {len(outline.chapters)}\n"
        f"Chapter Title: {chapter.title}\n"
        f"Energy Level: {chapter.energy_level}\n"
        f"Target Word Count: {chapter.target_words}\n"
        f"Chapter Focus: {chapter.summary}\n\n"
        f"Historical Facts to Weave Naturally:\n{facts_block}\n\n"
        f"Sensory Details to Evoke:\n{sensory_block}\n\n"
        f"Already Covered in Earlier Chapters (DO NOT REPEAT):\n{memory_block}\n\n"
        f"Write approximately {chapter.target_words} words of uninterrupted, soothing spoken narration."
    )

    raw_text = llm.generate_text(
        system_prompt=WRITER_SYSTEM_PROMPT,
        user_prompt=draft_prompt,
        temperature=0.72,
        max_tokens=max(2048, int(chapter.target_words * 2.2)),
    )

    lint_notes = detect_sleep_script_issues(raw_text)
    issue_hint = (
        "\nFlagged issues to fix:\n" + "\n".join(f"- {i}" for i in lint_notes)
        if lint_notes
        else "\nNo lint flags triggered; focus on literary rhythm, warmth, and natural spoken flow."
    )

    polish_prompt = (
        f"REVIEW THIS CHAPTER ({chapter.title}, energy: {chapter.energy_level})."
        f"{issue_hint}\n\n"
        f"CHAPTER TEXT:\n{raw_text}"
    )
    edited_raw = llm.generate_text(
        system_prompt=EDITOR_SYSTEM_PROMPT,
        user_prompt=polish_prompt,
        temperature=0.4,
        max_tokens=max(2048, int(chapter.target_words * 2.2)),
    )
    edited_text = sanitize_spoken_prose(edited_raw or raw_text)
    remaining_notes = detect_sleep_script_issues(edited_text)
    critic_notes = lint_notes if lint_notes else ["Passed sleep continuity & anti-slop polish."]
    if remaining_notes:
        critic_notes.extend(f"Remaining note: {n}" for n in remaining_notes)
    return raw_text, edited_text, critic_notes


def run_writer_agent(
    manifest: ProjectManifest,
    outline: OutlineArtifact,
    store: ProjectStore,
    llm: LLMProvider,
    *,
    only_chapter: int | None = None,
) -> ScriptBundle:
    """Draft and polish each chapter with rolling continuity memory and save human-editable Markdown."""
    existing_by_num: dict[int, ChapterScript] = {}
    if store.script_bundle_path.exists():
        prev_bundle = store.load_script_bundle()
        existing_by_num = {c.chapter_number: c for c in prev_bundle.chapters}

    continuity_memory: list[str] = []
    chapters: list[ChapterScript] = []

    for ch in outline.chapters:
        md_path = store.script_dir / f"chapter_{ch.chapter_number:02d}.md"
        md_rel = store.relative_str(md_path)

        if only_chapter is not None and ch.chapter_number != only_chapter and ch.chapter_number in existing_by_num:
            kept = existing_by_num[ch.chapter_number]
            chapters.append(kept)
            continuity_memory.append(f"Chapter {ch.chapter_number} ({ch.title}): {ch.summary}")
            continue

        raw_text, edited_text, critic_notes = _write_single_chapter(
            chapter=ch,
            outline=outline,
            continuity_memory=continuity_memory,
            llm=llm,
        )

        # Save human-editable Markdown so users can tweak prose before Stage 3 Audio
        md_content = f"# Chapter {ch.chapter_number}: {ch.title}\n\n{edited_text}\n"
        md_path.write_text(md_content, encoding="utf-8")

        chapters.append(
            ChapterScript(
                chapter_number=ch.chapter_number,
                title=ch.title,
                raw_text=raw_text,
                edited_text=edited_text,
                word_count=len(edited_text.split()),
                critic_notes=critic_notes,
                markdown_file=md_rel,
            )
        )
        continuity_memory.append(f"Chapter {ch.chapter_number} ({ch.title}): {ch.summary}")

    total_words = sum(c.word_count for c in chapters)
    estimated_minutes = round(total_words / max(1, manifest.words_per_minute), 2)
    return ScriptBundle(
        total_words=total_words,
        estimated_minutes=estimated_minutes,
        chapters=chapters,
    )
