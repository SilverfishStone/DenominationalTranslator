import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import langlib as L  # noqa: E402


def pack(file, sect, entries, priority=0):
    return L.Pack(file=file, sect=sect, meta=L.normalize_meta({"priority": priority}), entries=entries)


SECTS = [
    {"id": "protestant", "name": "Protestant"},
    {"id": "evangelical", "name": "Evangelical", "parent": "protestant"},
    {"id": "baptist", "name": "Baptist", "parent": "evangelical"},
    {"id": "ortho", "name": "Orthodox"},
]


class ParseFileName(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(L.parse_file_name("core.ortho.json", {"ortho"}), ("core", "ortho"))

    def test_dotted_pack_name_and_lang_ext(self):
        self.assertEqual(L.parse_file_name("a.b.ortho.lang", {"ortho"}), ("a.b", "ortho"))

    def test_common(self):
        self.assertEqual(L.parse_file_name("core.common.json", set()), ("core", "common"))

    def test_rejects_unknown_sect_missing_sect_and_bad_extension(self):
        for name in ("core.nope.json", "ortho.json", ".ortho.json", "core.ortho.txt"):
            with self.subTest(name), self.assertRaises(L.LangError):
                L.parse_file_name(name, {"ortho"})


class ParseContents(unittest.TestCase):
    def test_lang_text(self):
        text = "# comment\r\n\r\nevangelical.saved = One\\nTwo \\\\ end\r\na.b=x=y\r\n_meta.author=Me\r\n_meta.reviewed_by=ortho, catholic\r\n_meta.priority=5\r\n"
        meta, entries = L.parse_lang_text(text)
        self.assertEqual(entries["evangelical.saved"], "One\nTwo \\ end")
        self.assertEqual(entries["a.b"], "x=y")
        self.assertEqual(meta, {"author": "Me", "reviewed_by": ["ortho", "catholic"], "priority": 5.0})

    def test_lang_text_bad_line(self):
        with self.assertRaises(L.LangError):
            L.parse_lang_text("just some words")

    def test_json_splits_meta_from_entries(self):
        meta, entries = L.parse_json_lang('{"_meta": {"author": "A"}, "x.y": "text"}')
        self.assertEqual(entries, {"x.y": "text"})
        self.assertEqual(meta["author"], "A")

    def test_json_rejects_non_string_values(self):
        with self.assertRaises(L.LangError):
            L.parse_json_lang('{"x.y": 3}')

    def test_entry_problems(self):
        sects, subjects = {"ortho": {}}, {"salvation": {}}
        problems = L.entry_problems(
            {"nope.salvation": "x", "ortho.nope": "x", "bad": "x", "ortho.salvation": " "},
            sects, subjects)
        self.assertEqual(len(problems), 4)  # unknown sect, unknown subject, bad key shape, empty text

    def test_entry_problems_reports_each_issue_once_per_cause(self):
        sects, subjects = {"ortho": {}}, {"salvation": {}}
        problems = L.entry_problems({"ortho.unknown": " "}, sects, subjects)
        self.assertEqual(len(problems), 2)  # unknown subject AND empty text


class Registries(unittest.TestCase):
    def test_valid(self):
        _, errors = L.validate_sects(SECTS)
        self.assertEqual(errors, [])

    def test_cycle_unknown_parent_and_reserved_id(self):
        _, errors = L.validate_sects([
            {"id": "a", "name": "A", "parent": "b"},
            {"id": "b", "name": "B", "parent": "a"},
            {"id": "c", "name": "C", "parent": "zzz"},
            {"id": "common", "name": "Common"},
        ])
        text = "\n".join(errors)
        self.assertIn("cycle", text)
        self.assertIn("unknown parent", text)
        self.assertIn("reserved", text)

    def test_subject_terms_must_name_known_sects(self):
        errors = L.validate_subjects({"s": {"name": "S", "terms": {"nope": ["x"]}}}, {"ortho"})
        self.assertEqual(len(errors), 1)


class MergeSubjects(unittest.TestCase):
    def test_terms_combine_across_files_and_later_name_is_optional(self):
        merged, errors = L.merge_subjects([
            ("a.json", {"salvation": {"name": "Salvation", "terms": {"evangelical": ["saved"]}}}),
            ("b.json", {"salvation": {"terms": {"ortho": ["theosis"]}}, "baptism": {"name": "Baptism"}}),
        ])
        self.assertEqual(errors, [])
        self.assertEqual(merged["salvation"], {"name": "Salvation", "terms": {"evangelical": ["saved"], "ortho": ["theosis"]}})
        self.assertEqual(merged["baptism"], {"name": "Baptism", "terms": {}})

    def test_conflicting_name_and_repeated_sect_terms_are_errors(self):
        _, errors = L.merge_subjects([
            ("a.json", {"s": {"name": "One", "terms": {"x": ["a"]}}}),
            ("b.json", {"s": {"name": "Two", "terms": {"x": ["b"]}}}),
        ])
        self.assertEqual(len(errors), 2)

    def test_bad_shapes(self):
        _, errors = L.merge_subjects([("a.json", []), ("b.json", {"s": "nope"})])
        self.assertEqual(len(errors), 2)


class Merge(unittest.TestCase):
    def test_priority_beats_file_order_and_overrides_are_reported(self):
        packs = [
            pack("b.ortho.json", "ortho", {"x.y": "from b"}),
            pack("a.ortho.json", "ortho", {"x.y": "from a"}),
            pack("z.ortho.json", "ortho", {"x.y": "from z"}, priority=-1),
        ]
        merged, overrides = L.merge_packs(packs)
        self.assertEqual(merged["ortho"]["x.y"]["text"], "from b")  # z (-1) < a < b
        self.assertEqual([o["winner"] for o in overrides], ["a.ortho.json", "b.ortho.json"])


class Resolve(unittest.TestCase):
    def setUp(self):
        self.sects, _ = L.validate_sects(SECTS)

    def test_chain(self):
        self.assertEqual(L.chain_for("baptist", self.sects), ["baptist", "evangelical", "protestant", "common"])
        self.assertEqual(L.chain_for("common", self.sects), ["common"])

    def test_own_then_inherited_then_common_then_missing(self):
        merged, _ = L.merge_packs([
            pack("c.baptist.json", "baptist", {"ortho.a": "baptist wrote this"}),
            pack("c.evangelical.json", "evangelical", {"ortho.a": "evangelical", "ortho.b": "evangelical b"}),
            pack("c.common.json", "common", {"ortho.a": "common", "ortho.b": "common b", "ortho.c": "common c"}),
        ])
        entries, missing = L.resolve_audience("baptist", ["ortho.a", "ortho.b", "ortho.c", "ortho.d"], merged, self.sects)
        got = {e["key"]: (e["level"], e["from"]) for e in entries}
        self.assertEqual(got["ortho.a"], ("own", "baptist"))
        self.assertEqual(got["ortho.b"], ("inherited", "evangelical"))
        self.assertEqual(got["ortho.c"], ("common", "common"))
        self.assertEqual(missing, ["ortho.d"])

    def test_placeholder_flag(self):
        merged, _ = L.merge_packs([pack("c.common.json", "common", {"ortho.a": "[PLACEHOLDER] x"})])
        entries, _ = L.resolve_audience("common", ["ortho.a"], merged, self.sects)
        self.assertTrue(entries[0]["placeholder"])


class Glossary(unittest.TestCase):
    def test_merge_rejects_duplicate_ids(self):
        merged, errors = L.merge_glossary([("a.json", {"theosis": {}}), ("b.json", {"theosis": {}, "pascha": {}})])
        self.assertEqual(sorted(merged), ["pascha", "theosis"])
        self.assertEqual(len(errors), 1)

    def test_valid_entry(self):
        good = {"theosis": {"term": "theosis", "definition": "Sharing in God's life.", "aliases": ["deification"],
                            "familiar_to": ["ortho"], "links": [{"label": "More", "url": "https://example.org"}]}}
        self.assertEqual(L.validate_glossary(good, {"ortho"}), [])

    def test_shape_errors(self):
        bad = {
            "Bad Id": {"term": "x", "definition": "y"},
            "no_def": {"term": "x"},
            "unknown_sect": {"term": "u", "definition": "d", "familiar_to": ["nope"]},
            "bad_link": {"term": "b", "definition": "d", "links": [{"label": "x", "url": "javascript:alert(1)"}]},
        }
        text = "\n".join(L.validate_glossary(bad, {"ortho"}))
        for expected in ("invalid term id", "needs a definition", 'unknown sect "nope"', "http(s)"):
            self.assertIn(expected, text)

    def test_auto_link_name_collisions_are_caught_but_manual_terms_may_overlap(self):
        clash = {"a": {"term": "Grace", "definition": "d"}, "b": {"term": "grace", "definition": "d"}}
        self.assertEqual(len(L.validate_glossary(clash, set())), 1)
        manual = {"a": {"term": "Grace", "definition": "d"}, "b": {"term": "grace", "definition": "d", "auto": False}}
        self.assertEqual(L.validate_glossary(manual, set()), [])

    def test_definitions_may_only_refer_to_real_terms(self):
        errors = L.validate_glossary({"a": {"term": "a", "definition": "See [[ghost]]."}}, set())
        self.assertEqual(len(errors), 1)


class Markup(unittest.TestCase):
    sects = {"catholic": {"site": "https://www.vatican.va"}, "ortho": {}}
    glossary = {"theosis": {}}

    def problems(self, text):
        return L.markup_problems(text, self.glossary, self.sects)

    def test_good_markup_has_no_problems(self):
        text = "**Bold**, [[theosis]], [[theosis|deification]], [site](site:catholic), [x](https://a.org), [y](#/dictionary/theosis)."
        self.assertEqual(self.problems(text), [])

    def test_plain_text_and_placeholders_are_untouched(self):
        self.assertEqual(self.problems("[PLACEHOLDER] Nothing special (really) here."), [])

    def test_unknown_term_unknown_sect_missing_site_and_unsafe_targets(self):
        for text in ("[[ghost]]", "[x](site:nope)", "[x](site:ortho)", "[x](javascript:alert(1))", "[x](ftp://a.org)"):
            with self.subTest(text):
                self.assertEqual(len(self.problems(text)), 1)

    def test_entry_problems_reports_markup_only_when_a_glossary_is_given(self):
        entries = {"ortho.salvation": "See [[ghost]]."}
        self.assertEqual(L.entry_problems(entries, {"ortho": {}}, {"salvation": {}}), [])
        self.assertEqual(len(L.entry_problems(entries, {"ortho": {}}, {"salvation": {}}, {})), 1)

    def test_sect_site_must_be_http(self):
        _, errors = L.validate_sects([{"id": "a", "name": "A", "site": "ftp://x"}, {"id": "b", "name": "B", "site": "https://b.org"}])
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
