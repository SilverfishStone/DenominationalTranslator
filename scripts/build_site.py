"""Build the static site: validate lang packs, merge them, resolve fallbacks, emit dist/.

    python scripts/build_site.py           # build into dist/
    python scripts/build_site.py --check   # validate only, write nothing

Exits non-zero on any validation error, so CI fails before a bad pack is published.
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import langlib as L

ROOT = Path(__file__).resolve().parent.parent
LANG_DIR = ROOT / "lang"
REGISTRY_DIR = ROOT / "registry"
SITE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"


def read_json(path, errors):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        errors.append(f"{path.relative_to(ROOT).as_posix()}: {exc}")
        return None


def registry_parts(name, errors, required=True):
    """registry/<name>.json first, then every registry/<name>/**/*.json in path order."""
    files = [p for p in [REGISTRY_DIR / f"{name}.json"] if p.is_file()]
    folder = REGISTRY_DIR / name
    if folder.is_dir():
        files += sorted(folder.rglob("*.json"))
    if not files and required:
        errors.append(f"registry/{name}.json: not found")
    parts = []
    for path in files:
        data = read_json(path, errors)
        if data is not None:
            parts.append((path.relative_to(ROOT).as_posix(), data))
    return parts


def load_packs(sects_by_id, subjects, glossary, errors, notes):
    packs, sect_ids = [], set(sects_by_id)
    for path in sorted(p for p in LANG_DIR.rglob("*") if p.is_file()):
        rel = path.relative_to(LANG_DIR).as_posix()
        if path.suffix not in L.LANG_EXTS:
            notes.append(f"ignored lang/{rel} (only {' and '.join(L.LANG_EXTS)} files are loaded)")
            continue
        try:
            _, sect = L.parse_file_name(path.name, sect_ids)
            text = path.read_text(encoding="utf-8-sig")
            parse = L.parse_json_lang if path.suffix == ".json" else L.parse_lang_text
            meta, entries = parse(text)
        except (OSError, ValueError) as exc:
            errors.append(f"lang/{rel}: {exc}")
            continue
        problems = L.entry_problems(entries, sects_by_id, subjects, glossary)
        errors.extend(f"lang/{rel}: {p}" for p in problems)
        if not problems:
            packs.append(L.Pack(file=rel, sect=sect, meta=meta, entries=entries))
    return packs


def fail(errors):
    print(f"\nBuild failed with {len(errors)} error(s):")
    for error in errors:
        print(f"  ERROR  {error}")
    return False


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build(write=True):
    errors, notes = [], []
    sect_parts = registry_parts("sects", errors)
    subject_parts = registry_parts("subjects", errors)
    glossary_parts = registry_parts("glossary", errors, required=False)
    if errors:
        return fail(errors)

    sects = []
    for label, data in sect_parts:
        if isinstance(data, list):
            sects.extend(data)
        else:
            errors.append(f"{label}: top level must be a list")
    subjects, merge_errors = L.merge_subjects(subject_parts)
    glossary, glossary_merge_errors = L.merge_glossary(glossary_parts)
    errors += merge_errors + glossary_merge_errors
    if errors:
        return fail(errors)

    sects_by_id, sect_errors = L.validate_sects(sects)
    errors += sect_errors
    errors += L.validate_subjects(subjects, set(sects_by_id))
    errors += L.validate_glossary(glossary, set(sects_by_id))
    if errors:
        return fail(errors)

    packs = load_packs(sects_by_id, subjects, glossary, errors, notes)
    if errors:
        return fail(errors)

    by_audience, overrides = L.merge_packs(packs)
    all_keys = sorted({key for pack in packs for key in pack.entries})
    audiences = [L.COMMON] + [s["id"] for s in sects]

    bundles, stats = {}, {}
    for audience in audiences:
        entries, missing = L.resolve_audience(audience, all_keys, by_audience, sects_by_id)
        bundles[audience] = {"audience": audience, "entries": entries, "missing": missing}
        count = lambda level: sum(e["level"] == level for e in entries)
        stats[audience] = {
            "count": len(entries),
            "own": count("own"),
            "inherited": count("inherited"),
            "common": count("common"),
            "missing": len(missing),
            "placeholders": sum(e["placeholder"] for e in entries),
        }

    print(f"{len(packs)} pack(s), {len(all_keys)} distinct key(s), {len(sects)} sect(s), "
          f"{len(subjects)} subject(s), {len(glossary)} glossary term(s)\n")
    print(f"  {'audience':<13}{'own':>5}{'inherited':>11}{'common':>8}{'missing':>9}{'placeholders':>14}")
    for audience in audiences:
        s = stats[audience]
        print(f"  {audience:<13}{s['own']:>5}{s['inherited']:>11}{s['common']:>8}{s['missing']:>9}{s['placeholders']:>14}")
    for o in overrides:
        notes.append(f"override: [{o['audience']}] {o['key']} - {o['winner']} replaces {o['loser']}")
    for note in notes:
        print(f"  note   {note}")

    if not write:
        print("\nCheck passed (nothing written).")
        return True

    shutil.rmtree(DIST_DIR, ignore_errors=True)
    shutil.copytree(SITE_DIR, DIST_DIR)
    data_dir = DIST_DIR / "data"
    data_dir.mkdir()
    write_json(data_dir / "index.json", {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sects": sects,
        "subjects": subjects,
        "audiences": stats,
    })
    write_json(data_dir / "glossary.json", glossary)
    for audience, bundle in bundles.items():
        write_json(data_dir / f"{audience}.json", bundle)
    print(f"\nBuilt dist/ ({len(bundles)} audience bundles).")
    return True


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(0 if build(write="--check" not in sys.argv) else 1)
