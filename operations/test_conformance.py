"""Positive and adversarial vectors for the catalog boundary, not Goal runtime."""

from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import conformance as c


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog, _ = c.read_json(c.ROOT / "docs/standard/catalog.json")
        self.schema, _ = c.read_json(c.ROOT / "models/catalog.schema.json")

    def reject(self, mutate):
        candidate = deepcopy(self.catalog)
        mutate(candidate)
        with self.assertRaises(ValueError):
            c.validate(candidate, self.schema)

    def test_current_catalog(self):
        c.validate(self.catalog, self.schema)
        self.assertEqual(len(self.catalog["rules"]), 13)
        self.assertEqual(sum(r["status"] == "observed" for r in self.catalog["rules"]), 12)

    def test_authority_cannot_be_granted(self):
        self.reject(lambda d: d.update(effectAuthority=True))

    def test_numeric_false_is_not_boolean_false(self):
        self.reject(lambda d: d.update(effectAuthority=0))

    def test_rule_cannot_grant_authority(self):
        self.reject(lambda d: d["rules"][0].update(effectAuthority=True))

    def test_unknown_schema(self):
        self.reject(lambda d: d.update(schema="wellmanifest.goal/catalog/v2"))

    def test_unknown_field(self):
        self.reject(lambda d: d.update(command="execute arbitrary code"))

    def test_runtime_cannot_move_to_standard(self):
        self.reject(lambda d: d.update(runtimeOwner="wellmanifest/goal"))

    def test_duplicate_rule_identity(self):
        self.reject(lambda d: d["rules"][1].update(id=d["rules"][0]["id"]))

    def test_duplicate_concern_owner(self):
        self.reject(lambda d: d["rules"][1].update(concern=d["rules"][0]["concern"]))

    def test_unknown_destination(self):
        self.reject(lambda d: d["rules"][0].update(destination="wellmanifest/another-goal"))

    def test_extraction_is_not_claimed_from_mapping(self):
        self.reject(lambda d: d["rules"][0].update(extraction="extracted"))

    def test_proposed_cannot_claim_observed_status(self):
        self.reject(lambda d: d["rules"][-1].update(status="observed", extraction="mapped"))

    def test_proposed_cannot_claim_implementation_evidence(self):
        self.reject(lambda d: d["rules"][-1].update(evidence=d["rules"][0]["evidence"]))

    def test_mapping_requires_observation(self):
        self.reject(lambda d: d["rules"][-1].update(extraction="mapped"))

    def test_observed_requires_implementation(self):
        self.reject(lambda d: d["rules"][0].update(evidence=[]))

    def test_ownership_is_not_implementation_evidence(self):
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(source="routing"))

    def test_relative_path_traversal(self):
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(path="../secret"))

    def test_absolute_path(self):
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(path="/secret"))

    def test_missing_ownership_provenance(self):
        self.reject(lambda d: d.update(ownershipEvidence=[]))

    def test_mutable_source_revision(self):
        self.reject(lambda d: d["sources"]["goal"].update(revision="main"))

    def test_invalid_digest(self):
        self.reject(lambda d: d["rules"][0]["evidence"][0].update(sha256="latest"))

    def test_rules_are_bounded(self):
        self.reject(lambda d: d.update(rules=d["rules"] * 10))

    def test_unknown_schema_keyword_is_not_ignored(self):
        self.schema["unknownConstraint"] = True
        with self.assertRaises(ValueError):
            c.validate(self.catalog, self.schema)

    def test_external_schema_reference_not_fetched(self):
        self.schema["$ref"] = "https://example.invalid/schema"
        with self.assertRaises(ValueError):
            c.validate(self.catalog, self.schema)

    def test_json_boundaries(self):
        for raw in (b'{"x":1,"x":2}', b'{', b'NaN', b'Infinity', b'\xff',
                    b' ' * (c.MAX_BYTES + 1)):
            with self.subTest(raw=raw[:30]), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "input.json"
                path.write_bytes(raw)
                with self.assertRaises((ValueError, UnicodeError)):
                    c.read_json(path)

    def test_report_does_not_claim_source_or_runtime_verification(self):
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

    def test_partial_source_input_fails_before_git(self):
        output = io.StringIO()
        with redirect_stdout(output), patch.object(c.subprocess, "run") as run:
            status = c.main(["--source-root", "."])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(output.getvalue())["findings"][0]["code"],
                         "WMGOAL-SOURCE-001")
        run.assert_not_called()

    def test_source_digest_mismatch_fails(self):
        with patch.object(c.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, stdout=b"different blob")):
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                c.verify_sources(self.catalog, {key: "." for key in self.catalog["sources"]})

    def test_source_symbol_checked_without_execution(self):
        raw = b"raise RuntimeError('must not execute')\ndef present(): pass\n"
        evidence = {"source": "goal", "path": "example.py", "symbol": "missing",
                    "sha256": hashlib.sha256(raw).hexdigest(), "kind": "implementation"}
        data = {"sources": self.catalog["sources"], "ownershipEvidence": [],
                "rules": [{"evidence": [evidence]}]}
        with patch.object(c.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, stdout=raw)) as run:
            with self.assertRaisesRegex(ValueError, "symbol missing"):
                c.verify_sources(data, {"goal": "."})
            evidence["symbol"] = "present"
            self.assertEqual(c.verify_sources(data, {"goal": "."}), 1)
        self.assertTrue(all(call.args[0][0] == "git" for call in run.call_args_list))
        self.assertTrue(all("shell" not in call.kwargs for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
