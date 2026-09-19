# In Good Faith

Pick your own Christian tradition, then find a belief from another tradition and read it explained in your own tradition's terms: an Orthodox reader learns what Evangelicals mean by "born again", an Evangelical learns what "saved" means to a Catholic.

Everything on the site is a **lang file**. Adding a translation means adding a file, never editing one.

> Most entries are AI-drafted and tagged *unverified* on the site until members of the tradition they describe have reviewed them.

## Quick start

Needs Python 3.10+ only (standard library, nothing to install).

```
python scripts/serve.py               # build + serve http://localhost:4173, rebuilds on every save
python scripts/build_site.py          # build into dist/
python scripts/build_site.py --check  # validate packs only (this is what CI runs)
python -m unittest discover -s tests  # unit tests
```

Open the site through the server. Opening `site/index.html` directly won't work because browsers block `fetch` on `file://`.

## The model

An entry is one line of a lang file:

```
<source sect>.<subject id>  =  explanation, written for the file's audience
```

The **audience** comes from the file name suffix; the **source sect** and **subject** come from the key.

```
lang/core.ortho.json          audience = ortho
    "evangelical.new_birth": "…the Evangelical idea of 'born again', in Orthodox terms…"
```

A key inside its own audience's file (`evangelical.*` in `*.evangelical.json`) is that tradition describing itself. Those are the ground truth reviewers can check translations against.

### File names: `<pack>.<sect>.json` or `<pack>.<sect>.lang`

- The **last** dot-segment before the extension is the audience and must be an id from `registry/sects.json` (or `common`).
- `<pack>` is free-form. Use as many packs per audience as you like: `core.ortho.json`, `community-2026-10.ortho.json`, `lang/contrib/alice.ortho.lang`. Subfolders are fine.
- `.json`: flat `"key": "text"` object. `.lang`: Minecraft-style `key=value` lines, `#` comments, `\n` for a line break (see `lang/core.catholic.lang`).

### Metadata

A reserved `_meta` object in JSON (or `_meta.x=…` lines in `.lang`):

| field | meaning |
|---|---|
| `author` | shown on the entry page |
| `reviewed_by` | list of sect ids whose adherents reviewed the pack; empty shows "Not yet reviewed by an adherent" |
| `priority` | number, default 0; decides which pack wins on a duplicate key |

For AI-drafted content use `"author": "unverified: auto-generated"` and `"priority": -10`; the site tags such entries *unverified* and any human pack overrides them. Ready-made bulk and single-item prompts (including ones that decide the full list of sects and subjects) are in [`docs/LLM_PROMPTS.md`](docs/LLM_PROMPTS.md).

### Markdown in entries

Entry text is plain text by default (blank line = new paragraph), and a small, safe Markdown subset is also understood. It is rendered without ever using raw HTML, so contributor text can't inject markup.

| write | you get |
|---|---|
| `**bold**`, `*italic*`, `` `code` `` | bold, italic, monospace |
| `- item` / `1. item` | bulleted / numbered list |
| `> quote` | block quote |
| `[text](https://example.org)` | an external link (opens in a new tab) |
| `[text](site:catholic)` | a link to that sect's official site, from its `site` in `registry/sects.json` |
| `[[theosis]]`, `[[theosis\|deification]]` | a word with a pop-up definition from the glossary (optionally shown as different text) |

The build rejects unknown `[[terms]]`, `site:` links to a sect with no `site`, and link targets that aren't `https://`, `mailto:`, `site:` or `#/`.

### Glossary and Dictionary

Unfamiliar words get a pop-up definition. Definitions live in `registry/glossary.json` (and, like the other registries, any `registry/glossary/*.json`):

```json
"theosis": {
  "term": "theosis",
  "aliases": ["deification"],
  "definition": "An Eastern Christian word for the goal of salvation…",
  "familiar_to": ["ortho", "oriental_ortho"],
  "links": [{ "label": "Read more", "url": "https://example.org" }],
  "auto": true
}
```

- **You don't have to mark anything up.** The first occurrence of each term (or alias) in an entry is linked automatically. Set `"auto": false` for common words you'd rather define only where you write `[[term]]`.
- `familiar_to` lists sects whose readers already know the word; they (and the sects beneath them) don't get it defined. Because the general layer has no tradition, it defines every word.
- Every term also appears on the **Dictionary** page (`#/dictionary`), with a page of its own. Definitions can use Markdown, including `[[other_term]]`.
- Two auto-linked terms may not share a name or alias. Definitions may only refer to real terms.

### Suggesting edits

The **✎ Suggest edits** button (bottom-right corner, on every page) opens edit mode. From an entry it jumps straight to that entry; from elsewhere it asks for a starting view (an audience). Then:

1. Scroll through every topic for that audience (grouped by the tradition being explained), filter by word, or show *Edited only*. Topics with no entry yet are listed too.
2. Rewrite any text in the box. **Preview** shows the formatted result. Drafts save in the browser as you type.
3. **Export…** gives a lang file you can download or copy: `suggested-edits.<audience>.json`, with `_meta.author` set to `unverified: suggested by <name>` and `priority` 10. Send it in, or drop it into `lang/`. Run `python scripts/build_site.py --check` to validate it first.

### Duplicate keys: later wins

Packs load in order of `priority`, then file path. If two packs define the same key for the same audience, the later one wins and the build prints an `override:` note. So a community fix is a new file with a higher `priority`; the original is untouched. (Without `priority`, `community-x` sorts *before* `core-` alphabetically and would lose.)

### Fallback: family tree

`registry/sects.json` gives each sect an optional `parent`. For a reader of sect S and a key K the site takes the first hit in:

1. S's own packs, then
2. S's parent, its grandparent, and so on, then
3. `*.common.json` (the neutral layer).

The entry page says which level answered, and the list marks it (`via Evangelical`, `general`). If nothing answers, the topic isn't shown, and the audience page counts it as missing. `baptist` in the sample data has no pack at all and inherits everything from `evangelical`.

## Registries

| file | purpose |
|---|---|
| `registry/sects.json` | `id`, `name`, optional `parent`, `blurb` and `site` (the tradition's official website, used by `[text](site:<id>)` links and shown on its entries). Add a sect here and its `.suffix` becomes valid immediately. |
| `registry/subjects.json` | Subject ids with a display `name` and per-sect search `terms`. |
| `registry/glossary.json` | Words with pop-up definitions (see above). |

Both registries are also read from folders, so additions can be new files instead of edits: every `registry/sects/*.json` (a list) is appended to the sects, and every `registry/subjects/*.json` (an object) is merged into the subjects. A subject id may appear in several files: their `terms` combine, and `name` can be omitted after the first file. Duplicate sect ids, a conflicting name, or the same sect's terms given twice for one subject fail the build.

`terms` is what makes search work: a reader types "born again" without knowing your subject id. The **first** term listed for a sect is also used as the entry title, since it's how that sect names the idea (`evangelical: ["born again", …]`). A sect with no terms of its own uses its nearest ancestor's, so list a term at the broadest sect that shares it. Search matches every sect's terms, so searching "theosis" also finds the other traditions' takes on salvation. The sample terms are illustrative; you own the real ones.

## Validation (fails the build)

Unknown sect suffix or unknown source sect, unknown subject, malformed key, non-string or empty value, invalid JSON, duplicate or cyclic sect definitions, `terms` for an unknown sect, an unknown `[[glossary term]]`, a `site:` link to a sect without a `site`, a disallowed link target, and malformed glossary entries.

## Deploying to GitHub Pages

1. Push to a GitHub repo with the default branch `main`.
2. Settings → Pages → Source: **GitHub Actions**.
3. `.github/workflows/pages.yml` runs the tests and the build on every push and PR (a bad pack fails the check), and deploys `dist/` on `main`.

The site uses relative URLs and hash routing, so it works under a project subpath (`user.github.io/repo/`) with no config.

## Layout

```
lang/        translation packs (the content)
registry/    sects.json, subjects.json, glossary.json
site/        static front end (index.html, app.js, markdown.js, editor.js, style.css)
scripts/     build_site.py, serve.py, langlib.py (pure logic)
tests/       unit tests for langlib
dist/        generated, git-ignored
```

## Not built yet

- Human-language locales (`core.ortho.ru.json`). The file-name parser would need one extra optional segment.
- Per-article static pages for search engines (the site is a single page with hash routes for now).
- Submitting suggestions from inside the site. Edit mode exports a file for now; sending it in is manual.
