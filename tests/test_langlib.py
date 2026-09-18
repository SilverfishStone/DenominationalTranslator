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


if __name__ == "__main__":
    unittest.main()
