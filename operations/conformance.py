"""Offline catalog conformance; never executes Goal, migration recipes or a model."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("JSON input exceeds 1 MiB")
    data = json.loads(raw, object_pairs_hook=unique_object)
    canonical(data)  # Reject NaN/Infinity accepted by Python's permissive parser.
    return data, hashlib.sha256(raw).hexdigest()


def check_shape(value, schema, document, location="$", depth=0):
    """Evaluate the closed JSON Schema subset used by catalog.schema.json.

    Unsupported keywords fail closed, rather than silently ignoring a future
    schema requirement. This is not advertised as a general JSON Schema engine.
    """
    supported = {"$schema", "$id", "$defs", "$ref", "title", "description",
                 "type", "const", "enum", "properties", "additionalProperties",
                 "required", "items", "minItems", "maxItems", "uniqueItems",
                 "minLength", "maxLength", "pattern"}
    if depth > 32 or set(schema) - supported:
        raise ValueError(f"unsupported schema at {location}")
    if "$ref" in schema:
        ref = schema["$ref"]
        if not re.fullmatch(r"#/[\$]defs/[A-Za-z0-9_-]+", ref):
            raise ValueError("only local definition references are supported")
        check_shape(value, document["$defs"][ref.rsplit("/", 1)[1]], document,
                    location, depth + 1)
        return
    encoded = canonical(value)
    if "const" in schema and encoded != canonical(schema["const"]):
        raise ValueError(f"constant mismatch at {location}")
    if "enum" in schema and encoded not in [canonical(x) for x in schema["enum"]]:
        raise ValueError(f"unknown vocabulary at {location}")
    types = {"object": dict, "array": list, "string": str, "boolean": bool,
             "integer": int, "null": type(None)}
    expected = schema.get("type")
    if expected:
        expected = [expected] if isinstance(expected, str) else expected
        if not any(type(value) is types[t] for t in expected):
            raise ValueError(f"type mismatch at {location}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if set(schema.get("required", [])) - set(value):
            raise ValueError(f"missing fields at {location}")
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            raise ValueError(f"unknown fields at {location}")
        for key in sorted(set(value) & set(properties)):
            check_shape(value[key], properties[key], document, f"{location}.{key}", depth + 1)
    if isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", MAX_BYTES):
            raise ValueError(f"array bounds at {location}")
        if schema.get("uniqueItems") and len({canonical(x) for x in value}) != len(value):
            raise ValueError(f"duplicate items at {location}")
        for index, item in enumerate(value):
            check_shape(item, schema.get("items", {}), document,
                        f"{location}[{index}]", depth + 1)
    if isinstance(value, str):
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", MAX_BYTES):
            raise ValueError(f"string bounds at {location}")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise ValueError(f"invalid string at {location}")


def validate(data, schema):
    check_shape(data, schema, schema)
    ids, concerns = set(), set()
    for rule in data["rules"]:
        if rule["id"] in ids or rule["concern"] in concerns:
            raise ValueError("duplicate rule identity or competing concern owner")
        ids.add(rule["id"])
        concerns.add(rule["concern"])
        observed = rule["status"] == "observed"
        if rule["extraction"] != ("mapped" if observed else "proposed"):
            raise ValueError("extraction status does not match observation status")
        if observed and not any(x["kind"] == "implementation" for x in rule["evidence"]):
            raise ValueError("observed rule needs implementation evidence")
        if not observed and rule["evidence"]:
            raise ValueError("proposals must not claim implementation evidence")
        if any(x["source"] != "goal" or x["kind"] == "ownership" for x in rule["evidence"]):
            raise ValueError("rule evidence must cite the Goal implementation or tests")
    ownership = data["ownershipEvidence"]
    if {x["source"] for x in ownership} != {"routing", "performance"}:
        raise ValueError("ownership provenance incomplete")
    if any(x["kind"] != "ownership" or x["symbol"] is not None for x in ownership):
        raise ValueError("invalid ownership evidence")
    for evidence in [*ownership, *(x for rule in data["rules"] for x in rule["evidence"])]:
        if any(part in {".", ".."} for part in evidence["path"].split("/")):
            raise ValueError("noncanonical evidence path")


def verify_sources(data, roots):
    """Read immutable Git blobs, verifying hashes and named Python symbols only."""
    cache = {}
    evidence = [*data["ownershipEvidence"],
                *(x for rule in data["rules"] for x in rule["evidence"])]
    for item in evidence:
        source, path = item["source"], item["path"]
        key = source, path
        if key not in cache:
            revision = data["sources"][source]["revision"]
            result = subprocess.run(["git", "-C", str(roots[source]), "show",
                                     f"{revision}:{path}"], check=True,
                                    capture_output=True, timeout=10)
            if len(result.stdout) > MAX_BYTES:
                raise ValueError("source blob exceeds verification bound")
            cache[key] = result.stdout
        raw = cache[key]
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError(f"source digest mismatch: {source}/{path}")
        if item["symbol"]:
            tree = ast.parse(raw)
            symbols = {node.name for node in ast.walk(tree)
                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            symbols |= {node.id for node in ast.walk(tree)
                        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
            if item["symbol"] not in symbols:
                raise ValueError(f"source symbol missing: {source}/{path}")
    return len(cache)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "docs/standard/catalog.json")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--routing-root", type=Path)
    parser.add_argument("--performance-root", type=Path)
    args = parser.parse_args(argv)
    report = {"schema": "wellmanifest.goal/conformance/v1", "valid": False,
              "effectAuthority": False, "runtimeConformanceVerified": False,
              "semanticReviewVerified": False, "sourceEvidenceVerified": False,
              "findings": []}
    code = "WMGOAL-INPUT-001"
    try:
        data, digest = read_json(args.catalog)
        schema, _ = read_json(ROOT / "models/catalog.schema.json")
        report["catalogSha256"] = digest
        code = "WMGOAL-CONTRACT-001"
        validate(data, schema)
        report["ruleCount"] = len(data["rules"])
        roots = {"goal": args.source_root, "routing": args.routing_root,
                 "performance": args.performance_root}
        if any(roots.values()):
            code = "WMGOAL-SOURCE-001"
            if not all(roots.values()):
                raise ValueError("all three source roots are required for source verification")
            report["verifiedBlobs"] = verify_sources(data, roots)
            report["sourceEvidenceVerified"] = True
        report["valid"] = True
    except (ValueError, OSError, KeyError, TypeError, RecursionError, SyntaxError,
            subprocess.SubprocessError) as error:
        report["findings"].append({"code": code, "message": str(error)})
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
