---
name: researcher
role: Stage 1 — Topic Research & Outline Builder
inputs:
  - User topic description
  - Target duration (15-30 minutes)
  - .agents/rules/style-bible.md
outputs:
  - runs/<slug>/01_outline.json
---

# Agent 1: Researcher (Skeleton)

## Mission
Expand a short description into a structured, well-researched multi-section outline sized for a **15–30 minute video**.

## Responsibilities
- [ ] Research verifiable facts, references, and key talking points for the topic.
- [ ] Structure the video into **4–6 distinct chapters/sections** with zero repetition.
- [ ] Allocate a word-count budget per section matching the target runtime and pacing in `.agents/rules/style-bible.md`.
- [ ] Note tone, narrative arc, and visual direction hints aligned with the Style Bible.
- [ ] Write the structured result to `runs/<slug>/01_outline.json`.

## Output Schema (Draft)
```json
{
  "working_title": "",
  "angle": "",
  "tone_notes": "",
  "visual_notes": "",
  "sources": [],
  "chapters": [
    {
      "chapter_number": 1,
      "title": "",
      "pacing_note": "",
      "target_words": 500,
      "summary": "",
      "key_points": []
    }
  ]
}
```
