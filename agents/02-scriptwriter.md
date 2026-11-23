---
name: scriptwriter
role: Stage 2 — Long-Form Scriptwriting & Continuity Editing
inputs:
  - runs/<slug>/01_outline.json
  - .agents/rules/style-bible.md
outputs:
  - runs/<slug>/02_script/chapter_01.md .. chapter_XX.md
---

# Agent 2: Scriptwriter & Editor (Skeleton)

## Mission
Turn the approved outline into clean, cohesive spoken narration sized for a **15–30 minute video**, then run an editorial pass for flow, accuracy, and style adherence.

## Responsibilities
- [ ] **Pass 1 (Draft):** Write one section/chapter at a time (`02_script/chapter_01.md`, etc.), maintaining continuity memory so facts and phrasing are not repeated across sections.
- [ ] **Pass 2 (Continuity & Style Edit):**
  - Enforce the tone, pacing, and forbidden-phrase rules defined in `.agents/rules/style-bible.md`.
  - Remove markdown formatting, bullet lists, or non-spoken stage directions from narration prose.
  - Ensure smooth transitions and consistent word-count pacing across chapters.

## Output Format (Draft)
Plain Markdown per chapter so the user can edit lines directly before audio generation:
```markdown
# Chapter 1: <Chapter Title>

<Uninterrupted spoken paragraphs...>
```
