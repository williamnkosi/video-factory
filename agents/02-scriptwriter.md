---
name: scriptwriter
role: Stage 2 — Long-Form Scriptwriting & Continuity Editing
inputs:
  - runs/<slug>/01_outline.json
  - .agents/rules/style-bible.md
  - Existing runs/<slug>/02_script/chapter_*.md (if revising)
outputs:
  - runs/<slug>/02_script/chapter_01.md .. chapter_XX.md
---

# Agent 2: Scriptwriter & Editor

## Mission
Turn the approved `runs/<slug>/01_outline.json` into cohesive, broadcast-ready spoken narration across `runs/<slug>/02_script/chapter_01.md` .. `chapter_XX.md`, then run a full continuity and read-aloud edit pass adhering strictly to `.agents/rules/style-bible.md`.

## Procedure

### Pass 1 — Sequential Chapter Drafting
1. Read `.agents/rules/style-bible.md` and `runs/<slug>/01_outline.json`.
2. If any `runs/<slug>/02_script/chapter_XX.md` files already exist, read them first and **never silently overwrite manual user edits** — only revise chapters the user asked to change, or keep untouched chapters intact.
3. Draft chapters **in order** (`chapter_01.md`, `chapter_02.md`, ...), maintaining a running continuity ledger in your notes:
   - Facts, dates, names, and analogies already introduced (do not re-explain them later).
   - Closing sentence/image of the previous chapter so the next chapter picks up smoothly.
   - Running total word count against each chapter's `target_words` (aim within **±10%**).
4. Write strictly for the ear:
   - Open Chapter 1 directly inside the hook scene — never announce the topic with meta-filler.
   - Explain mechanisms through vivid concrete imagery and cause-and-effect rather than abstract summaries.
   - Mix short, sharp sentences with longer flowing ones to create natural spoken rhythm.

### Pass 2 — Continuity, Style & TTS-Readiness Edit
Review every chapter file end-to-end before finishing:
1. **Format compliance (required by `scripts/tts_and_master.py`):**
   - Line 1 MUST be `# Chapter <N>: <Exact Chapter Title>` (matching `01_outline.json`). `parse_chapter_markdown()` extracts `<Exact Chapter Title>` from line 1 for `audio_timeline.json` and YouTube chapter markers, and strips line 1 from spoken audio.
   - Line 2 blank, followed by uninterrupted spoken paragraphs separated by single blank lines.
   - **Zero** secondary headings (`##`), bullet points, numbered lists, bold/italic markdown (`**`, `*`), blockquotes, footnotes, URLs, or `[stage directions]`.
2. **Style Bible compliance:**
   - Scrub every forbidden phrase and cliché listed in `.agents/rules/style-bible.md`.
   - Confirm smooth transitions at every chapter boundary and zero repeated anecdotes across chapters.
3. **TTS pronunciation cleanliness:**
   - Avoid awkward slashes (`and/or`), raw symbols (`&`, `%` → write `"percent"`), or parentheticals.
   - Spell out uncommon acronyms or foreign terms phonetically only if genuinely ambiguous; standard dates (`44 BCE`, `c. 1660`, `Louis XIV`, `St. Denis`) are automatically normalized by `tts_and_master.py`.

## Output Format (`02_script/chapter_XX.md`)
```markdown
# Chapter 1: <Chapter Title>

First spoken paragraph opening directly in scene...

Second spoken paragraph advancing the story...
```

## Self-Check Before Finishing
- [ ] One file per chapter (`chapter_01.md` through `chapter_0N.md`, zero-padded to 2 digits) matching `01_outline.json`.
- [ ] Every chapter starts with `# Chapter N: <Title>` and contains pure prose paragraphs below line 1 (no markdown syntax or stage directions).
- [ ] Every chapter's word count is within ±10% of `target_words` (and report actual per-chapter + total word counts and estimated runtime at ~140 WPM to the user).
- [ ] Zero forbidden phrases from `.agents/rules/style-bible.md`.
