"""Positive and adversarial vectors for the catalog boundary, not Goal runtime."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch

import conformance as c


class CatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog, _ = c.read_json(c.ROOT / "docs/standard/catalog.json")
        self.schema, _ = c.read_json(c.ROOT / "models/catalog.schema.json")

    def reject(self, mutate: Any) -> None:
        candidate = deepcopy(self.catalog)
        mutate(candidate)
        with self.assertRaises(ValueError):
            c.validate(candidate, self.schema)

    def test_current_catalog(self) -> None:
        c.validate(self.catalog, self.schema)
        self.assertEqual(len(self.catalog["rules"]), 13)
        self.assertEqual(sum(r["status"] == "observed" for r in self.catalog["rules"]), 12)

    def test_authority_cannot_be_granted(self) -> None:
        self.reject(lambda d: d.update(effectAuthority=True))

    def test_numeric_false_is_not_boolean_false(self) -> None:
        self.reject(lambda d: d.update(effectAuthority=0))

    def test_rule_cannot_grant_authority(self) -> None:
        self.reject(lambda d: d["rules"][0].update(effectAuthority=True))

    def test_unknown_schema(self) -> None:
        self.reject(lambda d: d.update(schema="wellmanifest.goal/catalog/v2"))

    def test_unknown_field(self) -> None:
        self.reject(lambda d: d.update(command="execute arbitrary code"))

    def test_runtime_cannot_move_to_standard(self) -> None:
        self.reject(lambda d: d.update(runtimeOwner="wellmanifest/goal"))

    def test_duplicate_rule_identity(self) -> None:
        self.reject(lambda d: d["rules"][1].update(id=d["rules"][0]["id"]))

    def test_duplicate_concern_owner(self) -> None:
        self.reject(lambda d: d["rules"][1].update(concern=d["rules"][0]["concern"]))

    def test_unknown_destination(self) -> None:
        self.reject(lambda d: d["rules"][0].update(destination="wellmanifest/another-goal"))

    def test_extraction_is_not_claimed_from_mapping(self) -> None:
        self.reject(lambda d: d["rules"][0].update(extraction="extracted"))

    def test_proposed_cannot_claim_observed_status(self) -> None:
        self.reject(lambda d: d["rules"][-1].update(status="observed", extraction="mapped"))

    def test_proposed_cannot_claim_implementation_evidence(self) -> None:
        self.reject(lambda d: d["rules"][-1].update(evidence=d["rules"][0]["evidence"]))

    def test_mapping_requires_observation(self) -> None:
        self.reject(lambda d: d["rules"][-1].update(extraction="mapped"))

    def test_observed_requires_implementation(self) -> None:
        self.reject(lambda d: d["rules"][0].update(evidence=[]))

    def test_ownership_is_not_implementation_evidence(self) -> None:
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(source="routing"))

    def test_relative_path_traversal_and_dash_prefix(self) -> None:
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(path="../secret"))
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(path="-flag/path.py"))

    def test_absolute_path(self) -> None:
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(path="/secret"))

    def test_missing_ownership_provenance(self) -> None:
        self.reject(lambda d: d.update(ownershipEvidence=[]))

    def test_mutable_source_revision(self) -> None:
        self.reject(lambda d: d["sources"]["goal"].update(revision="main"))

    def test_invalid_digest(self) -> None:
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(sha256="latest"))

    def test_trailing_newlines_rejected_across_all_patterned_fields(self) -> None:
        self.reject(
            lambda d: d["sources"]["goal"].update(revision=d["sources"]["goal"]["revision"] + "\n")
        )
        self.reject(
            lambda d: d["rules"][0]["evidence"][0].update(
                sha256=d["rules"][0]["evidence"][0]["sha256"] + "\n"
            )
        )
        self.reject(lambda d: d["rules"][0].update(id="WMGOAL-001\n"))
        self.reject(lambda d: d["rules"][0].update(concern="delivery-modes\n"))
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(path="goal/delivery.py\n"))
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(symbol="resolve_policy\n"))

    def test_rule_evidence_requires_valid_python_symbol_identifier(self) -> None:
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(symbol=None))
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(symbol=""))
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(symbol="9invalid"))

    def test_inline_secret_material_rejected(self) -> None:
        canary = "gh" + "p_" + ("A" * 26)
        self.reject(lambda d: d["rules"][0].update(statement=f"leaked {canary}"))

    def test_rules_are_bounded(self) -> None:
        self.reject(lambda d: d.update(rules=d["rules"] * 10))

    def test_unknown_schema_keyword_is_not_ignored(self) -> None:
        self.schema["unknownConstraint"] = True
        with self.assertRaises(ValueError):
            c.validate(self.catalog, self.schema)

    def test_external_schema_reference_not_fetched(self) -> None:
        self.schema["$ref"] = "https://example.invalid/schema"
        with self.assertRaises(ValueError):
            c.validate(self.catalog, self.schema)

    def test_json_and_symlink_boundaries(self) -> None:
        payloads = (
            b'{"x":1,"x":2}',
            b"{",
            b"NaN",
            b"Infinity",
            b"\xff",
            b" " * (c.MAX_BYTES + 1),
        )
        for raw in payloads:
            with self.subTest(raw=raw[:30]), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "input.json"
                path.write_bytes(raw)
                with self.assertRaises((ValueError, UnicodeError)):
                    c.read_json(path)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real.json"
            real.write_text('{"ok": true}', encoding="utf-8")
            link = root / "link.json"
            link.symlink_to(real)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                c.read_json(link)

    def test_report_does_not_claim_source_or_runtime_verification(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), patch.object(c.subprocess, "run") as run:
            status = c.main([])
        report = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertFalse(report["sourceEvidenceVerified"])
        self.assertFalse(report["runtimeConformanceVerified"])
        self.assertFalse(report["semanticReviewVerified"])
        self.assertFalse(report["effectAuthority"])
        run.assert_not_called()

    def test_partial_source_input_fails_before_git(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), patch.object(c.subprocess, "run") as run:
            status = c.main(["--source-root", "."])
        self.assertEqual(status, 2)
        self.assertEqual(
            json.loads(output.getvalue())["findings"][0]["code"], "WMGOAL-SOURCE-001"
        )
        run.assert_not_called()

    def test_git_blob_rejects_symlink_root_and_flag_injection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_dir = root / "repo"
            real_dir.mkdir()
            link_dir = root / "repo-link"
            link_dir.symlink_to(real_dir)
            with patch.object(c.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "non-symlink directory"):
                    c._read_git_blob(link_dir, "a" * 40, "goal/delivery.py")
                with self.assertRaisesRegex(ValueError, "40-hex"):
                    c._read_git_blob(real_dir, "--output=/tmp/x", "goal/delivery.py")
                with self.assertRaisesRegex(ValueError, "noncanonical"):
                    c._read_git_blob(real_dir, "a" * 40, "-flag.py")
            run.assert_not_called()

    def test_source_digest_mismatch_fails(self) -> None:
        fake = subprocess.CompletedProcess([], 0, stdout=b"different blob")
        with patch.object(c.subprocess, "run", return_value=fake):
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                c.verify_sources(self.catalog, {key: "." for key in self.catalog["sources"]})

    def test_source_symbol_checked_at_module_or_class_scope_without_execution(self) -> None:
        raw = (
            b"raise RuntimeError('must not execute')\n"
            b"CONST_LIMIT: int = 5\n"
            b"class Policy:\n"
            b"    def method_sym(self): pass\n"
            b"def present():\n"
            b"    local_only = 42\n"
            b"    return local_only\n"
        )
        evidence = {
            "source": "goal",
            "path": "example.py",
            "symbol": "missing",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "kind": "implementation",
        }
        data = {
            "sources": self.catalog["sources"],
            "ownershipEvidence": [],
            "rules": [{"evidence": [evidence]}],
        }
        fake = subprocess.CompletedProcess([], 0, stdout=raw)
        with patch.object(c.subprocess, "run", return_value=fake) as run:
            with self.assertRaisesRegex(ValueError, "symbol missing"):
                c.verify_sources(data, {"goal": "."})
            evidence["symbol"] = "local_only"
            with self.assertRaisesRegex(ValueError, "symbol missing"):
                c.verify_sources(data, {"goal": "."})
            for valid_symbol in ("present", "CONST_LIMIT", "Policy", "method_sym"):
                evidence["symbol"] = valid_symbol
                self.assertEqual(c.verify_sources(data, {"goal": "."}), 1)
        self.assertTrue(all(call.args[0][0] == "git" for call in run.call_args_list))
        self.assertTrue(all("shell" not in call.kwargs for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
