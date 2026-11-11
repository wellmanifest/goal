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
            with patch.object(c.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "non-symlink directory"):
                    c._read_git_blob(nested_via_symlink, "a" * 40, "goal/delivery.py")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
