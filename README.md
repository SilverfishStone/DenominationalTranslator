# DenomBridge

Pick your own Christian tradition, then find a belief from another tradition and read it explained in your own tradition's terms: an Orthodox reader learns what Evangelicals mean by "born again", an Evangelical learns what "saved" means to a Catholic.

Everything on the site is a **lang file**. Adding a translation means adding a file, never editing one.

> All sample entries are `[PLACEHOLDER]` text, not doctrine. The build reports how many placeholders remain per audience.

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
| `registry/sects.json` | `id`, `name`, optional `parent`, optional `blurb`. Add a sect here and its `.suffix` becomes valid immediately. |
| `registry/subjects.json` | Subject ids with a display `name` and per-sect search `terms`. |

`terms` is what makes search work: a reader types "born again" without knowing your subject id. The **first** term listed for a sect is also used as the entry title, since it's how that sect names the idea (`evangelical: ["born again", …]`). Search matches every sect's terms, so searching "theosis" also finds the other traditions' takes on salvation. The sample terms are illustrative; you own the real ones.

## Validation (fails the build)

Unknown sect suffix or unknown source sect, unknown subject, malformed key, non-string or empty value, invalid JSON, duplicate or cyclic sect definitions, `terms` for an unknown sect.

## Deploying to GitHub Pages

1. Push to a GitHub repo with the default branch `main`.
2. Settings → Pages → Source: **GitHub Actions**.
3. `.github/workflows/pages.yml` runs the tests and the build on every push and PR (a bad pack fails the check), and deploys `dist/` on `main`.

The site uses relative URLs and hash routing, so it works under a project subpath (`user.github.io/repo/`) with no config.

## Layout

```
lang/        translation packs (the content)
registry/    sects.json, subjects.json
site/        static front end (index.html, app.js, style.css)
scripts/     build_site.py, serve.py, langlib.py (pure logic)
tests/       unit tests for langlib
dist/        generated, git-ignored
```

## Not built yet

- Human-language locales (`core.ortho.ru.json`). The file-name parser would need one extra optional segment.
- Per-article static pages for search engines (the site is a single page with hash routes for now).
- Markdown in entry text (entries render as escaped plain text with paragraph breaks, deliberately, since contributors' text is untrusted).
