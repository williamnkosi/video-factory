# Channel Style Bible

Shared creative guardrails obeyed by all agents and scripts in this repository.
Every creative choice (outline, script, TTS delivery, visual prompts, and export metadata) must conform to this document unless the user overrides a rule for a specific run.

## 1. Channel Vision, Format & Runtime
- **Subject Focus:** **Historical documentaries centered around Africa** — exploring the continent's empires, kingdoms, cities, trade networks, scholarship, architecture, diplomacy, engineering, art, resistance movements, and overlooked turning points across all regions and eras.
- **Channel Format:** Narrative historical documentary / deep-dive explainer (curious, cinematic, rigorous, engaging).
- **Target Duration:** **15–30 minutes** (default: **20 minutes**).
- **Target Spoken Pace:** **~135–150 words per minute** (~2,200–4,500 words total across **4–6 chapters**; aim for **~2,800–3,000 words** for a 20-minute default).
- **Visual Cadence:** **1 scene every 40–50 seconds** (~24–30 scenes for a 20-minute video).

## 2. Editorial Lens & Historical Rigor
- **Inside-Out Perspective:** Tell African history on its own terms — centering African agency, institutions, trade, politics, and voices rather than framing eras solely around European arrival or outside "discovery."
- **Specificity Over Generalization:** Treat Africa as a vast, diverse continent of distinct regions, polities, languages, and eras. Name specific peoples, kingdoms, and cities (e.g., Aksum, Kush, Mali, Songhai, Kanem-Bornu, Benin, Great Zimbabwe, Kilwa, Kongo, Ashanti, Zulu, Ethiopia) rather than flattening them into vague labels.
- **Source Standards:** Ground outlines in verifiable scholarship, archaeology, primary chronicles (e.g., Timbuktu manuscripts, *Kilwa Chronicle*, *Kebra Nagast*, Ibn Battuta, archaeological surveys, UNESCO *General History of Africa*, and modern African historians). Clearly distinguish established historical evidence from oral tradition or active scholarly debate — never fabricate dates, figures, or quotes.

## 3. Voice & Writing Guardrails
- **Format:** Clean spoken narration prose only. Each `02_script/chapter_XX.md` starts with a single `# Chapter N: <Title>` heading on line 1 followed by uninterrupted paragraphs. **No** subheadings, bullet lists, bold/italic markup, footnotes, or `[stage directions]` inside narration text.
- **Tone & Persona:** Curious, lucid, cinematic historian-storyteller — authoritative without sounding like a textbook lecture. Ground grand history in tangible objects, architecture, trade goods, landscapes, and human decisions.
- **Narrative & Energy Arc:**
  - **Opening chapter (Hook & Question):** Open in-scene with a vivid historical moment, artifact, city, or paradox within the first 30 seconds. Earn attention through real stakes rather than meta-intros.
  - **Middle chapters (Escalation & Mechanism):** Advance by cause-and-effect — show *how* economies, armies, treaties, trade routes, or innovations actually worked. End each chapter with a natural narrative handoff into the next.
  - **Closing chapter (Synthesis & Resonance):** Pull back to illuminate the long legacy and human echo of the story, landing on a memorable closing image rather than a YouTube outro pitch.
- **TTS-Ready Prose & Pronunciation:**
  - Vary sentence length deliberately (pair crisp short beats with measured explanatory sentences).
  - Introduce unfamiliar titles, regions, and historical names clearly in context (e.g., *Mansa*, *Askia*, *Oba*, *Kilwa Kisiwani*, *Mapungubwe*, *Sankore*).
  - Avoid parenthetical asides, slashes (`/`), raw URLs, or awkward symbols (`&`, `%` → write `"percent"`).
- **Forbidden Phrases & Clichés:**
  - **No YouTube meta-filler:** *"In this video"*, *"Welcome back"*, *"Let's dive in"*, *"Without further ado"*, *"Buckle up"*, *"Smash that like button"*, *"Before we begin"*.
  - **No exoticizing or reductive tropes:** *"Dark continent"*, *"mysterious Africa"*, *"lost civilization"* (when descendant peoples and history are known), lazy *"tribal"* generalizations where a specific kingdom/polity/people name applies, or framing sites as *"discovered"* by outsiders.
  - **No overused essay clichés:** *"Fast forward to"*, *"Little did they know"*, *"Needless to say"*, *"At the end of the day"*, *"It's worth noting"*, *"Delve into"*, *"Tapestry"*, *"Testament to"*, *"Game-changer"*.

## 4. Visual Guardrails
- **Aesthetic & Style:** **Minimalist muted editorial illustration / warm vintage prints** — subtle archival paper grain, crisp ink linework, flat-to-lightly-shaded editorial shapes, museum-plate and mid-century printmaking sensibility.
- **Color Palette:** Warm parchment/sandstone (`#EFE6D5`), charcoal ink (`#1F2428`), muted ochre/gold (`#C58B43`), laterite terracotta (`#A85A44`), indigo slate (`#4D6475`), and savanna sage (`#6D7B63`). Avoid neon colors, glossy 3D/CGI renders, hyper-saturated HDR, or stock-photo realism.
- **Regional & Historical Accuracy:** Depict authentic regional architecture, environments, trade goods, and period dress matched to the exact place and century — e.g., Sudano-Sahelian earthen mosques and libraries, Great Zimbabwe dry-stone enclosures, Swahili coral-stone harbors and dhows, Nubian granite pyramids, Ethiopian rock-hewn stone, Benin cast-bronze court scenes, Saharan salt caravans. Never default to generic savanna clichés when a scene belongs in a walled city, university courtyard, highland fortress, or coastal port.
- **Framing & Composition:** **16:9 widescreen**, clean focal hierarchy, generous negative space, and balanced margins so slow Ken Burns camera moves feel deliberate and uncluttered.
- **Cross-Scene Continuity:** Every prompt in `04_visuals/visual_plan.json` must share one cohesive editorial print style anchor so the entire documentary reads like plates from one curated historical atlas/monograph.
- **Camera Motion:** Alternate slow `zoom_in`, `zoom_out`, `pan_left`, `pan_right`, and occasional `static` (for stark architectural elevations or map-like geometric compositions). Never use the same motion more than twice in a row. Keep progressive dimming disabled (`--dim-amount 0.0`).
- **Forbidden Visual Elements:** **No text, letters, numbers, map labels, captions, logos, UI elements, picture frames/borders, or watermarks** inside generated scene images.

## 5. Audio Guardrails
- **Loudness:** Consistent broadcast narration mastering (`-16 LUFS`, true peak limited, zero clipping via `scripts/tts_and_master.py`).
- **Voice Delivery (`--voice-style`):**
  > Narrate like an engaging, thoughtful historical documentary host: warm, clear, curious, measured pacing, crisp diction, and natural pauses between ideas — respectful and vivid, never rushed or overly theatrical.
- **Background Audio / Ambience:** Subtle low-level procedural bed (`--ambience brown_noise --ambience-db -30`, or `--ambience soft_rain --ambience-db -30` when thematically fitting), always tucked cleanly beneath the narration with gentle fade-in and fade-out.
