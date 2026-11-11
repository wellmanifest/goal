"""Adversarial regression tests for Goal regular-file I/O, JSON bounds, and symlink guards."""

from __future__ import annotations

import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import conformance as c


class GoalHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog, _ = c.read_json(c.ROOT / "docs/standard/catalog.json")
        self.schema, _ = c.read_json(c.ROOT / "models/catalog.schema.json")

    def test_read_json_rejects_fifo_and_directory_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "regular file"):
                c.read_json(root)
            if hasattr(os, "mkfifo"):
                fifo = root / "catalog.fifo"
                os.mkfifo(fifo)
                with self.assertRaisesRegex(ValueError, "regular file"):
                    c.read_json(fifo)

    def test_read_json_rejects_overflow_floats_and_excessive_nesting(self) -> None:
        deep = ("[" * (c.MAX_JSON_DEPTH + 2)) + "1" + ("]" * (c.MAX_JSON_DEPTH + 2))
        extreme = ("[" * 1500) + "1" + ("]" * 1500)
        for payload in ("1e999", "-1e999", "-Infinity", deep, extreme):
            with self.subTest(payload=payload[:20]), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "bad.json"
                target.write_text(payload, encoding="utf-8")
                with self.assertRaises(ValueError):
                    c.read_json(target)

    def test_validate_rejects_non_string_keys_non_finite_floats_and_deep_objects(self) -> None:
        candidate = deepcopy(self.catalog)
        candidate[123] = "bad"  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "strings"):
            c.validate(candidate, self.schema)

        candidate2 = deepcopy(self.catalog)
        candidate2["extraFloat"] = float("inf")
        with self.assertRaisesRegex(ValueError, "non-finite"):
            c.validate(candidate2, self.schema)

        nested: object = "leaf"
        for _ in range(c.MAX_JSON_DEPTH + 5):
            nested = {"child": nested}
        with self.assertRaisesRegex(ValueError, "nesting depth"):
            c.reject_sensitive(nested)

    def test_check_shape_rejects_unknown_local_definition_and_malformed_schema(self) -> None:
        bad_schema = deepcopy(self.schema)
        bad_schema["$ref"] = "#/$defs/nonexistentDef"
        with self.assertRaisesRegex(ValueError, "unknown schema definition"):
            c.validate(self.catalog, bad_schema)

        with self.assertRaisesRegex(ValueError, "unsupported schema"):
            c.check_shape(self.catalog, {1: "bad"}, self.schema)  # type: ignore[arg-type]

    def test_git_blob_rejects_ancestor_symlink_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_parent = root / "real_parent"
            real_repo = real_parent / "repo"
            real_repo.mkdir(parents=True)
            link_parent = root / "link_parent"
            link_parent.symlink_to(real_parent)
            nested_via_symlink = link_parent / "repo"
            with patch.object(c.subprocess, "run") as run, self.assertRaisesRegex(
                ValueError, "non-symlink directory"
            ):
                c._read_git_blob(nested_via_symlink, "a" * 40, "goal/delivery.py")
            run.assert_not_called()

    def test_huge_int_lone_surrogates_symlink_ancestors_and_iterative_ast_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for idx, payload in enumerate((
                b'{"count": ' + (b"9" * 400) + b"}",
                b'{"text": "\\ud800"}',
                b'{"\\udfff": 1}',
            )):
                bad_file = root / f"bad-{idx}.json"
                bad_file.write_bytes(payload)
                with self.assertRaises(ValueError):
                    c.read_json(bad_file)

            real_dir = root / "real_catalog"
            real_dir.mkdir()
            cat_file = real_dir / "catalog.json"
            cat_file.write_bytes((c.ROOT / "docs/standard/catalog.json").read_bytes())
            sym_dir = root / "sym_catalog"
            sym_dir.symlink_to(real_dir)

            with self.assertRaisesRegex(ValueError, "symbolic link"):
                c.read_json(sym_dir / "catalog.json")

            old_cwd = Path.cwd()
            try:
                os.chdir(root)
                with self.assertRaisesRegex(ValueError, "symbolic link"):
                    c.read_regular_bytes(Path("sym_catalog/catalog.json"))
            finally:
                os.chdir(old_cwd)

            for bad_max in (True, False, 0, -1):
                with self.subTest(max_bytes=bad_max), self.assertRaises(ValueError):
                    c.read_regular_bytes(cat_file, max_bytes=bad_max)  # type: ignore[arg-type]

        bad_type_schema = deepcopy(self.schema)
        bad_type_schema["type"] = "bogusType"
        with self.assertRaisesRegex(ValueError, "unsupported schema"):
            c.check_shape(self.catalog, bad_type_schema, bad_type_schema)

        src = (
            b"class Outer:\n"
            b"    class Inner:\n"
            b"        X, Y = 1, 2\n"
            b"        def run(self):\n"
            b"            pass\n"
        )
        self.assertEqual(c._extract_python_symbols(src), {"Outer", "Inner", "X", "Y", "run"})
        with self.assertRaises(ValueError):
            c._extract_python_symbols(b"x = 1\x00")
        self.assertIsNone(c._HEX40_RE.match("a" * 40 + "\n"))


if __name__ == "__main__":
    unittest.main()
