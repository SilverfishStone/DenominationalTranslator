# Writing content with an LLM

Everything an LLM writes for DenomBridge is a **draft**. Three habits keep that honest:

1. **Label it.** Every AI-written lang pack has `"author": "unverified: auto-generated"` and `"reviewed_by": []`. The site shows an *unverified* tag on those entries.
2. **Give it low priority.** AI packs use `"priority": -10`, so any human-written pack (priority 0 or higher) automatically wins for the same key. A draft can never shadow something a person wrote.
3. **Keep it in one place.** AI lang packs live in `lang/auto/`; AI registry additions live in `registry/sects/` and `registry/subjects/`. Create these folders the first time you need them.

There are two lanes:

- **Bulk prompts (Bulk 1 to 5):** the LLM decides what's needed and produces it all. Use these to stand the site up.
- **Single-item prompts (A to D):** one subject, one sect, one entry at a time. Use these for later additions and fixes.

## Recommended order for a full bulk run

1. **Bulk 1** decides the sects. Save the output as `registry/sects/bulk-01.json`.
2. **Bulk 2** decides the subjects. Save each block it gives you as `registry/subjects/bulk-NN.json`.
3. Run `python scripts/build_site.py --check` and fix anything it reports (paste the errors back to the LLM).
4. **Bulk 4** once per sect: that tradition describing itself. Start with the major ones.
5. **Bulk 5** with audience `common` first: a neutral explanation of every belief, which gives *every* reader a complete baseline through fallback. Then Bulk 5 for individual audiences (major families first; their branches inherit from them).
6. Later, when you add a sect, run **Bulk 3** to give it terms on existing subjects.

Scale warning: the full matrix is (audiences) x (subject and source-sect pairs) entries at roughly 150 words each, which is enormous. Steps 4 and 5-with-`common` already give complete coverage. Per-audience translations are an upgrade you can add gradually, most valuable audience first.

How the registry files combine: `registry/sects.json` plus every file under `registry/sects/` form one list. `registry/subjects.json` plus every file under `registry/subjects/` are merged, and a subject id may appear in several files (their `terms` combine; `name` may be left out after the first file). Duplicate sect ids, conflicting names, or the same sect's terms given twice for one subject fail the build.

## Workflow for any prompt

1. Open a chat with an LLM and paste **the rules block** below.
2. Paste the task prompt, fill in the `{{blanks}}`, and paste the registries where it asks (the current files, all of them merged if you've split them).
3. Save each file it outputs at the path it gives.
4. Run `python scripts/build_site.py --check`. If it reports errors, paste them back and ask for a corrected file.
5. Preview with `python scripts/serve.py`, skim for anything that reads as polemic, then commit.

---

## The rules block (paste first, every time)

````text
You are helping build DenomBridge, a static website where a reader from one Christian tradition can look up a belief of another tradition and read it explained in their own tradition's vocabulary. All content is stored in small data files. Follow these rules exactly.

WHAT YOU WRITE
- Explain, don't argue. Describe each belief the way its own adherents would recognise and accept as fair. Never advocate for or against a tradition, and never claim to know what a tradition "really" believes beneath what it says.
- Write for the reader's tradition (the "audience"). Anchor explanations in words and ideas the audience already uses, and say plainly where a term or idea does NOT map cleanly, rather than pretending two things are the same.
- Where a topic is genuinely contested between traditions, describe each side in its own terms and stop. Do not adjudicate.
- Use neutral, respectful vocabulary. Avoid loaded labels (for example "cult"). If a disputed label matters to the topic, say who uses it and why, as a description.
- Only state what you are confident is true of that tradition's official or widely held teaching. If belief varies within a tradition, say so briefly. If you are unsure, say less. Never invent quotations, citations, section numbers, dates or statistics. Name a primary source (a catechism, confession, creed, scripture passage) only if you are certain it exists and says what you claim.
- Length: about 80 to 200 words per entry, in 1 to 3 short paragraphs.
- Plain text only. No Markdown, no bullet lists, no headings, no HTML. Separate paragraphs with a blank line (in JSON, the two characters \n\n). Use single quotes, not double quotes, inside the text so the JSON stays valid.
- Never begin an entry with [PLACEHOLDER].

FILE FORMAT
- A lang file is one JSON object. Keys look like "<source_sect_id>.<subject_id>": the sect whose belief is being explained, then the subject. The value is the explanation, written FOR the audience named in the file name.
- If the source sect and the audience are the same, the entry is that tradition describing its own belief in its own terms.
- The audience is a sect id, or the special id "common": a neutral explanation for a reader with no tradition-specific vocabulary, defining every term in plain language.
- Sect ids and subject ids must come from the registry files I paste. Existing ids are permanent because content files refer to them: never rename or remove one, and never invent an id inside a lang file. If you need a new one, tell me instead.
- Ids use lowercase letters, digits and underscores only. Never put a dot inside an id.
- Every lang file starts with this exact "_meta" object (unless a task says otherwise):
  "_meta": { "author": "unverified: auto-generated", "reviewed_by": [], "priority": -10 }
- Output valid JSON only: no comments, no trailing commas.
- Lang file names are <pack>.<audience_id>.json and go in lang/auto/.

OUTPUT
- For each file, print its path on its own line, then the complete file in a fenced code block. Nothing else before or after, except the short notes sections a task asks for, and a short "Uncertain" list at the end naming any claim you were less than fully confident about.
````

---

# Bulk prompts

## Bulk 1: decide and add every sect

````text
[Rules block pasted above.]

Current sect registry (registry/sects.json plus any files in registry/sects/; it may hold only a few sample entries):
{{paste}}

TASK: Decide which Christian traditions the site needs, and add every missing one.

Scope: {{default: every tradition worldwide that describes itself as Christian, or that Christians commonly discuss in conversation with each other. Include groups whose Christian status other traditions dispute, listed under their own self-description with no editorial comment. Cover the major families (for example Catholic, Eastern Orthodox, Oriental Orthodox, Anglican, Lutheran, Reformed, Baptist, Methodist, Pentecostal, Anabaptist, Adventist, Restorationist, nontrinitarian groups, and any others you judge necessary) and their significant branches.}}
Target size: {{about 50 to 100 entries in total, including those already present}}

How to decide:
1. Think in a family tree. A tradition gets its own entry only if a reader from it would use noticeably different vocabulary or hold noticeably different beliefs from readers of its parent. Do not add entries for bodies that differ only in governance or history unless that changes how they speak about beliefs.
2. "parent" is chosen for FALLBACK, not history: a reader of this tradition sees the parent's explanations whenever nothing has been written for them specifically. Pick the single broader entry whose vocabulary they would most readily understand, or null for a top-level family. Each entry has at most one parent.
3. Keep every id that already exists. Never rename or remove one. Do not repeat existing entries in your output.
4. Ids: lowercase snake_case, short, no dots, usable as a file suffix (methodist, oriental_ortho). Names: what members would call themselves.
5. Order siblings alphabetically by name, and put each parent before its children.
6. Before answering, check: every parent id exists (in the existing registry or in your output), no cycles, no duplicate ids, no id containing a dot or a capital letter.

Output:
- The file registry/sects/bulk-01.json as ONE JSON list of only the NEW entries, each { "id": "...", "name": "...", "parent": "..." or null }. Add "blurb" only if you have one neutral, factual sentence.
- "Suggested changes to existing entries": any existing entry whose name or parent you think should change, one line each with the reason. Do not apply them in the JSON.
- "Judgement calls": traditions you left out or placed uncertainly, and why.
(This task does not produce a lang file: ignore the FILE FORMAT and _meta rules.)
````

## Bulk 2: decide and add every subject

Run this after the sects are final, since `terms` refer to sect ids.

````text
[Rules block pasted above.]

Sect registry (registry/sects.json plus any files in registry/sects/):
{{paste}}

Current subject registry (registry/subjects.json plus any files in registry/subjects/; it may hold only a few sample entries):
{{paste}}

TASK: Decide which subjects the site needs, and add every missing one.

Scope: {{default: every belief, practice, term or question on which Christian traditions commonly misunderstand one another. Cover at least: God and the Trinity; Christ and the incarnation; the Holy Spirit; salvation and grace; sin and human nature; Scripture and its authority; tradition and authority in the church; the church and its structure; ministry and ordination; baptism and the other sacraments or ordinances; worship, liturgy and prayer; saints, Mary and the dead; the afterlife and last things; ethics and life in the world; the roles of women and men; the labels traditions use for themselves and for each other; and any others you judge necessary.}}
Target size: {{about 100 to 200 subjects in total, including those already present}}

How to decide:
1. A subject is a topic where at least two traditions hold different beliefs, OR use the same words differently, OR use different words for the same idea. Skip topics where every tradition agrees and speaks alike.
2. Subjects are neutral topics, not one tradition's claims. Name each one in plain English a curious outsider would recognise ('baptism', not 'believer's baptism').
3. Keep every existing subject id. Never rename or remove one. Do not repeat existing subjects.
4. Ids: lowercase snake_case, no dots, unique.
5. "terms" maps sect ids (only ids in the sect registry) to lists of search phrases:
   - Include a sect only if it has its own word or view for this subject.
   - The FIRST phrase for a sect is that tradition's own natural name for the idea; the site shows it as the entry title.
   - A sect with no terms of its own automatically uses its nearest ancestor's (following "parent"), so list a term at the broadest sect that shares it and add a child sect only where the child differs.
   - Give each listed sect 1 to 4 further phrases: alternative wordings, and phrases outsiders use for the idea (these are what readers type into the search box).
6. Before answering, check: every sect id in "terms" exists in the sect registry, no subject id is duplicated or contains a dot, and every subject has a name.

Output:
- One or more JSON objects, each in its own fenced block and each meant to be saved as its own file: registry/subjects/bulk-01.json, bulk-02.json, and so on. Each object maps NEW subject ids to { "name": "...", "terms": { "<sect_id>": ["...", "..."] } }. Group by theme so each file covers one or two themes, and keep each file under about 40 subjects. If you run out of room, end at a clean subject boundary with the single line CONTINUES; I will reply "continue" and you give the next file, without repeating anything.
- "Judgement calls": subjects you considered and left out, and why.
(This task does not produce a lang file: ignore the FILE FORMAT and _meta rules.)
````

## Bulk 3: give newly added sects terms on existing subjects

Use this whenever you add sects after the subjects already exist.

````text
[Rules block pasted above.]

Sect registry (all files):
{{paste}}

Subject registry (all files merged):
{{paste}}

New sects to cover: {{sect ids, e.g. methodist, oriental_ortho}}

TASK: Add terms for the new sects to the existing subjects.

For each existing subject on which a new sect has its own word or view, output an entry containing ONLY the terms for the new sect(s). Leave out subjects where the new sect has nothing distinct: it inherits from its parent. Follow the same rules for terms as usual: the first phrase is the sect's own name for the idea, followed by 1 to 4 alternative and outsider phrases.

Do not repeat a subject's "name" (if you include it, copy it exactly), and do not repeat terms already present for other sects. Do not add new subjects here; list any you think are missing under "Missing subjects".

Output:
- The file registry/subjects/terms-<label>.json as ONE JSON object: { "<subject_id>": { "terms": { "<new_sect_id>": ["...", "..."] } } }
- "Missing subjects" and "Judgement calls".
(This task does not produce a lang file: ignore the FILE FORMAT and _meta rules.)
````

## Bulk 4: every self-description for one tradition

Run once per sect. Self-descriptions are the ground truth every translation is checked against.

````text
[Rules block pasted above.]

Sect registry (all files):
{{paste}}

Subject registry (all files merged):
{{paste}}

TASK: Write the self-description entries for ONE tradition (source and audience are the same sect).

Tradition: {{sect id, e.g. ortho}}

Work list: every subject in the subject registry whose "terms" contain this sect's OWN entry (not inherited ones). Write one entry for each, keyed "<sect_id>.<subject_id>", as that tradition describing its own belief in its own vocabulary, the way a thoughtful member would endorse. Use the tradition's own term (the first phrase in "terms") naturally in the text. Where the tradition's own teaching is not uniform, say so briefly.

Output the file lang/auto/self.<sect_id>.json. If the work list is longer than about 40 entries, split it into lang/auto/self-01.<sect_id>.json, self-02.<sect_id>.json, and so on, ending every part except the last with the single line CONTINUES; I will reply "continue".
````

## Bulk 5: explain many beliefs for one audience

Run once per audience, starting with `common`. It works through a queue in batches so no response runs out of room.

````text
[Rules block pasted above.]

Sect registry (all files):
{{paste}}

Subject registry (all files merged):
{{paste}}

TASK: Write explanations for ONE audience across many subjects.

Audience: {{a sect id, or common}}
Subjects in scope: {{all, or a list of subject ids, or a theme}}
Start after (leave blank to begin): {{e.g. baptism.lutheran}}
Batch size: {{20}} entries per response.

Work list: for every subject in scope, one pair for each sect that has its OWN entry in that subject's "terms" (not inherited ones), but skip pairs where the source sect equals the audience (the self-description task covers those); for the audience "common", include every source. Order the list by subject id, then source sect id, and work through it in that order, starting just after the pair named above.

For each pair, write an entry keyed "<source_sect_id>.<subject_id>" that explains the source sect's belief FOR the audience: use the audience's vocabulary as anchors, say where words or ideas do not map, and keep to the rules. For the audience "common", define every term in plain language for a reader who knows no tradition's vocabulary.

Output:
- The file lang/auto/bulk-<NN>.<audience_id>.json, where NN is the batch number (01, 02, and so on).
- Then the single line: DONE <k> of <total> | NEXT: <subject_id>.<source_sect_id>
  I will reply "continue" for the next batch, or paste the NEXT value into a new chat as "Start after". Never repeat entries from earlier batches. When the list is finished, end with the single line COMPLETE.
````

---

# Single-item prompts

Use these for one-off additions and corrections. A new subject or sect from these can be saved as its own file in `registry/subjects/` or `registry/sects/` (a JSON object for a subject, a one-element list for a sect), or pasted into the main file.

## A: add one subject

````text
[Rules block pasted above.]

Here are the current registries.

Sect registry:
{{paste}}

Subject registry:
{{paste}}

TASK: Propose a new subject for the subject registry.

Subject to add: {{one or two sentences, e.g. "how each tradition understands baptism: who is baptised, when, and what it does"}}

Produce a single JSON entry:
- "id": short lowercase snake_case id that is not already used.
- "name": a neutral, plain-English display name a curious reader from any tradition would recognise (not one tradition's jargon).
- "terms": an object mapping sect ids (only ids that exist in the sect registry) to lists of search phrases. The FIRST phrase for each sect must be that tradition's own most natural name for the idea, because it is shown as the entry title (a sect with no terms of its own uses its parent's). Follow it with 1 to 4 other phrases or alternative wordings a reader from ANY tradition might type when they meet this idea, including phrases outsiders use for it. Include a sect only if it has a distinct term or view on the subject.

Output only the JSON entry as { "<id>": { "name": ..., "terms": ... } }, then one line naming any sect that plausibly holds a view here but that you left out, and why. (This task does not produce a lang file, so ignore the FILE FORMAT and _meta rules.)
````

## B: write entries for one subject

````text
[Rules block pasted above.]

Here are the current registries.

Sect registry:
{{paste}}

Subject registry:
{{paste}}

TASK: Write lang files for one subject.

Subject id: {{e.g. new_birth}}
Source sects whose belief is to be explained: {{e.g. evangelical, catholic}}
Audiences to write for: {{e.g. ortho, lds, evangelical, or common}}

For EACH audience, produce one file lang/auto/<subject_id>.<audience_id>.json containing one entry for each source sect, keyed "<source_sect_id>.<subject_id>".
- When the audience differs from the source sect, explain the source sect's belief in the audience's vocabulary, and note where the terms differ.
- When the audience equals the source sect, write that tradition's belief in its own words, as a description a member would endorse.
- Skip any (source, audience) pair where the source sect has no meaningful position on the subject, and list the skipped pairs in the "Uncertain" section at the end.

Follow the OUTPUT rules.
````

## C: add one sect

````text
[Rules block pasted above.]

Sect registry:
{{paste}}

TASK: Propose a new entry for the sect registry.

Tradition to add: {{e.g. Methodist}}

Produce one JSON object:
- "id": lowercase snake_case, not already used, suitable as a file suffix (e.g. methodist).
- "name": the display name members of this tradition would use.
- "parent": the id of the existing sect it most sensibly sits under, or null if none fits. Fallback works like this: readers of this tradition see the parent's explanations (and inherit its search terms) when nothing has been written for them specifically, so choose the parent whose vocabulary these readers would most readily understand.
- "blurb": omit unless you have one factual, neutral sentence.

Output only the JSON object, then two sentences explaining your choice of parent and naming any other plausible parent. (This task does not produce a lang file, so ignore the FILE FORMAT and _meta rules.)
````

## D: revise one entry after feedback

The revision is a separate file that overrides the old text, so nothing is edited in place.

````text
[Rules block pasted above.]

TASK: Revise one entry using feedback.

Audience: {{e.g. ortho}}
Key: {{e.g. evangelical.new_birth}}

Current text:
{{paste the current entry text}}

Feedback:
{{paste the feedback, verbatim}}

Rewrite the entry so it addresses the feedback while still following every rule above. If you believe part of the feedback is mistaken, keep the accurate wording and say so in the "Uncertain" section instead of silently ignoring it.

Output ONE file, lang/auto/revision-{{short-label}}.<audience_id>.json, containing just this one key. Use this _meta instead of the default, so the revision beats the original draft:
  "_meta": { "author": "unverified: auto-generated", "reviewed_by": [], "priority": -9 }
````

---

## Review checklist (before you trust a draft)

- Would a member of the source tradition recognise their own belief in it, and call it fair?
- Does it argue, mock, or slip in "but actually..."? Cut it.
- Any quotation, citation or statistic you can't verify yourself? Cut it.
- Does it say where the audience's vocabulary *doesn't* match, or does it pretend two terms mean the same thing?
- For a contested topic (for example whether a group counts as Christian), are both sides described in their own terms without a verdict?
- For sect and subject registries: does every tradition you care about have a sensible parent, and did the "Judgement calls" list leave out anything you'd want in?

## Promoting a draft to a reviewed entry

Move the text into a normal pack (for example `lang/core.ortho.json`, or a new `lang/community-XXXX.ortho.json`), then set the metadata to what is actually true:

```json
"_meta": { "author": "Your Name", "reviewed_by": ["evangelical"], "priority": 0 }
```

`reviewed_by` lists the sect ids whose members checked the entry. Remove the same key from the `lang/auto/` file so there's a single source of truth.
