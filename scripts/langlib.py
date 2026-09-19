"""Pure logic for the lang pipeline: parsing, validation, merging, fallback resolution.

No file-system access here, so everything is easy to unit-test.
"""
import json
import re
from dataclasses import dataclass

COMMON = "common"  # reserved neutral audience; the root every fallback chain ends in
ID_RE = re.compile(r"^[a-z0-9_]+$")
KEY_RE = re.compile(r"^([a-z0-9_]+)\.([a-z0-9_]+)$")  # <source sect>.<subject>
LANG_EXTS = (".json", ".lang")
PLACEHOLDER = "[PLACEHOLDER]"


class LangError(ValueError):
    pass


@dataclass
class Pack:
    file: str  # path relative to lang/, forward slashes
    sect: str  # audience this pack is written for
    meta: dict
    entries: dict


# --- file names ---------------------------------------------------------------

def parse_file_name(file_name, sect_ids):
    """'core.ortho.json' -> ('core', 'ortho'). The last dot-segment is the audience."""
    ext = next((e for e in LANG_EXTS if file_name.endswith(e)), None)
    if ext is None:
        raise LangError(f"unsupported extension (expected {' or '.join(LANG_EXTS)})")
    pack, dot, sect = file_name[: -len(ext)].rpartition(".")
    if not dot or not pack:
        raise LangError(f"file name must look like <pack>.<sect>{ext}")
    if sect != COMMON and sect not in sect_ids:
        raise LangError(f'unknown sect suffix ".{sect}" (add it to registry/sects.json?)')
    return pack, sect


# --- file contents ------------------------------------------------------------

def normalize_meta(raw):
    raw = raw or {}
    if not isinstance(raw, dict):
        raise LangError("_meta must be an object")
    reviewed = raw.get("reviewed_by", [])
    if isinstance(reviewed, str):
        reviewed = [s.strip() for s in reviewed.split(",") if s.strip()]
    try:
        priority = float(raw.get("priority", 0))
    except (TypeError, ValueError):
        raise LangError("_meta.priority must be a number") from None
    author = raw.get("author")
    return {
        "author": author if isinstance(author, str) and author else None,
        "reviewed_by": [str(x) for x in reviewed],
        "priority": priority,
    }


def parse_json_lang(text):
    data = json.loads(text)
    if not isinstance(data, dict):
        raise LangError("top level must be an object")
    meta = normalize_meta(data.pop("_meta", None))
    for key, value in data.items():
        if not isinstance(value, str):
            raise LangError(f'value for "{key}" must be a string')
    return meta, data


def _unescape(value):
    return re.sub(r"\\(n|\\)", lambda m: "\n" if m.group(1) == "n" else "\\", value)


def parse_lang_text(text):
    """Minecraft-style: key=value per line, '#' comments, \\n for a newline, _meta.x=... for metadata."""
    meta, entries = {}, {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, eq, value = line.partition("=")
        key = key.strip()
        if not eq or not key:
            raise LangError(f"line {number}: expected key=value")
        value = _unescape(value.strip())
        if key.startswith("_meta."):
            meta[key[len("_meta."):]] = value
        else:
            entries[key] = value
    return normalize_meta(meta), entries


MD_TERM_RE = re.compile(r"\[\[([A-Za-z0-9_]+)(?:\|[^\]]+)?\]\]")   # [[term]] or [[term|shown text]]
MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")                  # [text](target)


def markup_problems(text, glossary, sects_by_id):
    """Problems with Markdown-style markup in one entry: unknown [[terms]] and unusable link targets."""
    problems = []
    for term_id in MD_TERM_RE.findall(text):
        if term_id not in glossary:
            problems.append(f'unknown glossary term "[[{term_id}]]" (add it under registry/glossary?)')
    for target in MD_LINK_RE.findall(text):
        if target.startswith("site:"):
            sect = sects_by_id.get(target[len("site:"):])
            if sect is None:
                problems.append(f'link "{target}" names an unknown sect')
            elif not sect.get("site"):
                problems.append(f'link "{target}": that sect has no "site" in registry/sects.json')
        elif not target.startswith(("http://", "https://", "mailto:", "#/")):
            problems.append(f'link target "{target}" is not allowed (use https://..., site:<sect_id> or #/...)')
    return problems


def entry_problems(entries, sects_by_id, subjects, glossary=None):
    problems = []
    for key, text in entries.items():
        match = KEY_RE.match(key)
        if not match:
            problems.append(f'key "{key}" must look like <source_sect>.<subject_id>')
            continue
        source, subject = match.groups()
        if source not in sects_by_id:
            problems.append(f'key "{key}": unknown source sect "{source}"')
        if subject not in subjects:
            problems.append(f'key "{key}": unknown subject "{subject}" (add it to registry/subjects.json?)')
        if not text.strip():
            problems.append(f'key "{key}": empty text')
        if glossary is not None:
            problems.extend(f'key "{key}": {p}' for p in markup_problems(text, glossary, sects_by_id))
    return problems


# --- registries ---------------------------------------------------------------

def validate_sects(sects):
    """Returns ({id: sect}, [errors])."""
    if not isinstance(sects, list):
        return {}, ["registry/sects.json: top level must be a list"]
    errors, by_id = [], {}
    for sect in sects:
        sid = sect.get("id") if isinstance(sect, dict) else None
        if not isinstance(sid, str) or not ID_RE.match(sid):
            errors.append(f"registry/sects.json: invalid sect id {sid!r}")
        elif sid == COMMON:
            errors.append(f'registry/sects.json: "{COMMON}" is reserved for the neutral fallback')
        elif sid in by_id:
            errors.append(f'registry/sects.json: duplicate id "{sid}"')
        else:
            by_id[sid] = sect
            if not isinstance(sect.get("name"), str) or not sect["name"]:
                errors.append(f'registry/sects.json: "{sid}" needs a name')
            site = sect.get("site")
            if site is not None and not (isinstance(site, str) and site.startswith(("http://", "https://"))):
                errors.append(f'registry/sects.json: "{sid}".site must be an http(s) URL')
    for sid, sect in by_id.items():
        parent = sect.get("parent")
        if parent is not None and parent not in by_id:
            errors.append(f'registry/sects.json: "{sid}" has unknown parent "{parent}"')
    for sid in by_id:
        seen, parent = {sid}, by_id[sid].get("parent")
        while parent in by_id:
            if parent in seen:
                errors.append(f'registry/sects.json: parent cycle involving "{sid}"')
                break
            seen.add(parent)
            parent = by_id[parent].get("parent")
    return by_id, errors


def merge_subjects(parts):
    """Combine subject registries from several files: [(label, dict), ...] -> (merged, errors).

    The same subject id may appear in more than one file. Its `terms` are combined (a sect's terms may
    appear in only one file), and `name` may be omitted after the first file that gives it.
    """
    merged, errors = {}, []
    for label, data in parts:
        if not isinstance(data, dict):
            errors.append(f"{label}: top level must be an object")
            continue
        for sid, subject in data.items():
            if not isinstance(subject, dict):
                errors.append(f'{label}: "{sid}" must be an object')
                continue
            slot = merged.setdefault(sid, {"terms": {}})
            name = subject.get("name")
            if name is not None:
                if "name" in slot and slot["name"] != name:
                    errors.append(f'{label}: "{sid}" is named "{name}" but an earlier file calls it "{slot["name"]}"')
                else:
                    slot["name"] = name
            terms = subject.get("terms") or {}
            if not isinstance(terms, dict):
                errors.append(f'{label}: "{sid}".terms must be an object')
                continue
            for sect, phrases in terms.items():
                if sect in slot["terms"]:
                    errors.append(f'{label}: "{sid}" already has terms for "{sect}" from an earlier file')
                else:
                    slot["terms"][sect] = phrases
    return merged, errors


def validate_subjects(subjects, sect_ids):
    if not isinstance(subjects, dict):
        return ["registry/subjects.json: top level must be an object"]
    errors = []
    for sid, subject in subjects.items():
        if not ID_RE.match(sid):
            errors.append(f'registry/subjects.json: invalid subject id "{sid}"')
        if not isinstance(subject, dict) or not isinstance(subject.get("name"), str):
            errors.append(f'registry/subjects.json: "{sid}" needs a name')
            continue
        for sect, terms in (subject.get("terms") or {}).items():
            if sect not in sect_ids:
                errors.append(f'registry/subjects.json: "{sid}" has terms for unknown sect "{sect}"')
            elif not isinstance(terms, list) or not all(isinstance(t, str) for t in terms):
                errors.append(f'registry/subjects.json: "{sid}".terms.{sect} must be a list of strings')
    return errors


def merge_glossary(parts):
    """Combine glossary files: [(label, dict), ...] -> (merged, errors). A term id may be defined once."""
    merged, errors = {}, []
    for label, data in parts:
        if not isinstance(data, dict):
            errors.append(f"{label}: top level must be an object")
            continue
        for term_id, term in data.items():
            if term_id in merged:
                errors.append(f'{label}: glossary term "{term_id}" is defined more than once')
            else:
                merged[term_id] = term
    return merged, errors


def validate_glossary(glossary, sect_ids):
    """Glossary shape: {id: {term, definition, aliases?, links?, familiar_to?, auto?}}."""
    errors, names = [], {}
    for term_id, term in glossary.items():
        where = f'registry/glossary: "{term_id}"'
        if not ID_RE.match(term_id):
            errors.append(f'registry/glossary: invalid term id "{term_id}" (lowercase letters, digits, underscores)')
        if not isinstance(term, dict):
            errors.append(f"{where} must be an object")
            continue
        for field in ("term", "definition"):
            if not isinstance(term.get(field), str) or not term[field].strip():
                errors.append(f"{where} needs a {field}")
        aliases = term.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(a, str) and a.strip() for a in aliases):
            errors.append(f"{where}.aliases must be a list of non-empty strings")
            aliases = []
        familiar = term.get("familiar_to", [])
        if not isinstance(familiar, list):
            errors.append(f"{where}.familiar_to must be a list of sect ids")
        else:
            errors.extend(f'{where}.familiar_to names unknown sect "{s}"' for s in familiar if s not in sect_ids)
        if "auto" in term and not isinstance(term["auto"], bool):
            errors.append(f"{where}.auto must be true or false")
        for link in term.get("links", []) or []:
            url = link.get("url") if isinstance(link, dict) else None
            if not (isinstance(link, dict) and isinstance(link.get("label"), str) and isinstance(url, str)
                    and url.startswith(("http://", "https://"))):
                errors.append(f'{where}.links entries need a "label" and an http(s) "url"')
        if term.get("auto") is not False:    # only auto-linked words can collide with each other
            for name in [term.get("term"), *aliases]:
                if isinstance(name, str):
                    owner = names.setdefault(name.lower(), term_id)
                    if owner != term_id:
                        errors.append(f'registry/glossary: "{name}" is used by both "{owner}" and "{term_id}"')
    for term_id, term in glossary.items():
        if isinstance(term, dict) and isinstance(term.get("definition"), str):
            errors.extend(f'registry/glossary: "{term_id}" refers to unknown term "[[{ref}]]"'
                          for ref in MD_TERM_RE.findall(term["definition"]) if ref not in glossary)
    return errors


# --- merging and fallback -----------------------------------------------------

def merge_packs(packs):
    """Later packs win. Order: meta.priority, then file path. Returns (by_audience, overrides)."""
    by_audience, overrides = {}, []
    for pack in sorted(packs, key=lambda p: (p.meta["priority"], p.file)):
        bucket = by_audience.setdefault(pack.sect, {})
        for key, text in pack.entries.items():
            if key in bucket:
                overrides.append({"audience": pack.sect, "key": key, "winner": pack.file, "loser": bucket[key]["file"]})
            bucket[key] = {
                "text": text,
                "file": pack.file,
                "author": pack.meta["author"],
                "reviewed_by": pack.meta["reviewed_by"],
            }
    return by_audience, overrides


def chain_for(audience, sects_by_id):
    """Fallback order: the sect itself, its parents, then the neutral 'common' layer."""
    chain, current = [], audience
    while current and current != COMMON and current not in chain:
        chain.append(current)
        current = sects_by_id.get(current, {}).get("parent")
    chain.append(COMMON)
    return chain


def resolve_audience(audience, all_keys, by_audience, sects_by_id):
    """Returns (entries, missing_keys) for one audience."""
    chain = chain_for(audience, sects_by_id)
    entries, missing = [], []
    for key in all_keys:
        found_at = next((lvl for lvl in chain if key in by_audience.get(lvl, {})), None)
        if found_at is None:
            missing.append(key)
            continue
        hit = by_audience[found_at][key]
        source, subject = KEY_RE.match(key).groups()
        if found_at == COMMON:
            level = "common"
        elif found_at == audience:
            level = "own"
        else:
            level = "inherited"
        entries.append({
            "key": key,
            "source": source,
            "subject": subject,
            "text": hit["text"],
            "level": level,
            "from": found_at,
            "pack": hit["file"],
            "author": hit["author"],
            "reviewed_by": hit["reviewed_by"],
            "placeholder": hit["text"].startswith(PLACEHOLDER),
        })
    return entries, missing
