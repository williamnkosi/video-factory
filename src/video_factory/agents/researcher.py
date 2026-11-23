"""Stage 1: Historical Researcher & Showrunner agent."""

from __future__ import annotations

import httpx

from video_factory.agents.prompts import RESEARCHER_SYSTEM_PROMPT
from video_factory.models import OutlineArtifact, ProjectManifest
from video_factory.providers.base import LLMProvider


def fetch_wikipedia_context(query: str, max_articles: int = 3) -> tuple[str, list[str]]:
    """Fetch brief grounded historical summaries from Wikipedia's public API (best-effort)."""
    snippets: list[str] = []
    sources: list[str] = []
    headers = {"User-Agent": "VideoFactoryMVP/0.1 (sleepy-history-researcher)"}

    try:
        with httpx.Client(timeout=8.0, headers=headers) as client:
            search_resp = client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": max_articles,
                    "format": "json",
                },
            )
            search_resp.raise_for_status()
            hits = search_resp.json().get("query", {}).get("search", [])

            for hit in hits[:max_articles]:
                title = hit.get("title")
                if not title:
                    continue
                summary_resp = client.get(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
                )
                if summary_resp.status_code != 200:
                    continue
                payload = summary_resp.json()
                extract = (payload.get("extract") or "").strip()
                url = (
                    payload.get("content_urls", {})
                    .get("desktop", {})
                    .get("page", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")
                )
                if extract:
                    snippets.append(f"### {title}\n{extract}")
                    sources.append(url)
    except (httpx.HTTPError, ValueError, KeyError):
        # Offline or rate-limited environments gracefully fall back to LLM knowledge.
        return "", []

    return "\n\n".join(snippets), sources


def run_researcher_agent(
    manifest: ProjectManifest,
    llm: LLMProvider,
    *,
    enable_wikipedia: bool = True,
) -> OutlineArtifact:
    """Expand the user's description into a structured Chapter Bible."""
    target_total_words = max(400, manifest.target_minutes * manifest.words_per_minute)
    # Aim for ~450-650 words per chapter (~3.5-5 min each) for 15-30 min videos
    chapter_count = max(3, min(8, round(target_total_words / 550)))

    wiki_context = ""
    wiki_sources: list[str] = []
    if enable_wikipedia and manifest.providers.llm != "mock":
        wiki_context, wiki_sources = fetch_wikipedia_context(manifest.description)

    grounding_block = (
        f"\n\nGrounded Reference Notes (Wikipedia):\n{wiki_context}\n"
        if wiki_context
        else "\n\n(No external reference notes fetched; rely on accurate historical scholarship.)\n"
    )

    user_prompt = (
        f"Topic Description: {manifest.description}\n"
        f"Target Duration: {manifest.target_minutes} minutes (at ~{manifest.words_per_minute} WPM)\n"
        f"Target total words: {target_total_words}\n"
        f"Recommended Chapter Count: {chapter_count} chapters\n"
        f"{grounding_block}\n"
        "Create a cohesive, deeply relaxing Chapter Bible where the sum of all chapter target_words "
        f"is approximately {target_total_words}. Make Chapter 1 'gentle_opening', middle chapters "
        "'calm_immersion' / 'deep_drifting', and the final chapter 'soft_winding_down'."
    )

    outline = llm.generate_structured(
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=OutlineArtifact,
        temperature=0.5,
        max_tokens=4096,
    )

    if wiki_sources:
        existing = set(outline.research_sources)
        outline.research_sources.extend(src for src in wiki_sources if src not in existing)

    return outline
