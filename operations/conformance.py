"""Offline catalog conformance; never executes Goal, migration recipes or a model."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_OPS_DIR = str(Path(__file__).resolve().parent)
if _OPS_DIR not in sys.path:
    sys.path.insert(0, _OPS_DIR)

from goal_io import (  # noqa: E402
    _SENSITIVE_RE,
    MAX_BYTES,
    MAX_JSON_DEPTH,
    _check_utf8_str,
    _enforce_json_depth_and_keys,
    _json_schema_regex,
    _parse_finite_float,
    _parse_finite_int,
    _reject_constant,
    _validate_non_symlink_dir,
    canonical,
    read_json,
    read_regular_bytes,
    reject_sensitive,
    unique_object,
)

ROOT = Path(__file__).resolve().parents[1]
_HEX40_RE = re.compile(r"\A[0-9a-f]{40}\Z")
_REL_PATH_RE = re.compile(r"\A[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")
_LOCAL_REF_RE = re.compile(r"\A#/[\$]defs/[A-Za-z0-9_-]+\Z")

__all__ = [
    "MAX_BYTES",
    "MAX_JSON_DEPTH",
    "ROOT",
    "_HEX40_RE",
    "_LOCAL_REF_RE",
    "_REL_PATH_RE",
    "_SENSITIVE_RE",
    "_check_utf8_str",
    "_enforce_json_depth_and_keys",
    "_extract_python_symbols",
    "_json_schema_regex",
    "_parse_finite_float",
    "_parse_finite_int",
    "_read_git_blob",
    "_reject_constant",
    "_validate_non_symlink_dir",
    "canonical",
    "check_shape",
    "main",
    "read_json",
    "read_regular_bytes",
    "reject_sensitive",
    "unique_object",
    "validate",
    "verify_sources",
]


def _non_neg_int_kw(schema: dict[str, Any], key: str, default: int, location: str) -> int:
    if key not in schema:
        return default
    val = schema[key]
    if type(val) is not int or val < 0:
        raise ValueError(f"unsupported schema at {location}")
    return val


def check_shape(
    value: Any,
    schema: dict[str, Any],
    document: dict[str, Any],
    location: str = "$",
    depth: int = 0,
) -> None:
    """Evaluate the closed JSON Schema subset used by catalog.schema.json.

    Unsupported keywords fail closed, rather than silently ignoring a future
    schema requirement. This is not advertised as a general JSON Schema engine.
    """
    if depth == 0:
        _enforce_json_depth_and_keys(value)
        if not isinstance(document, dict):
            raise ValueError("schema document must be a JSON object")
    if not isinstance(schema, dict) or any(not isinstance(k, str) for k in schema):
        raise ValueError(f"unsupported schema at {location}")
    supported = {
        "$schema",
        "$id",
        "$defs",
        "$ref",
        "title",
        "description",
        "type",
        "const",
        "enum",
        "properties",
        "additionalProperties",
        "required",
        "items",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minLength",
        "maxLength",
        "pattern",
    }
    if depth > 32 or set(schema) - supported:
        raise ValueError(f"unsupported schema at {location}")
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or _LOCAL_REF_RE.fullmatch(ref) is None:
            raise ValueError("only local definition references are supported")
        defs = document.get("$defs")
        ref_name = ref.rsplit("/", 1)[1]
        if not isinstance(defs, dict) or ref_name not in defs:
            raise ValueError(f"unknown schema definition at {location}")
        check_shape(value, defs[ref_name], document, location, depth + 1)
        return
    if "const" in schema or "enum" in schema:
        encoded = canonical(value)
        if "const" in schema and encoded != canonical(schema["const"]):
            raise ValueError(f"constant mismatch at {location}")
        if "enum" in schema:
            enum_vals = schema["enum"]
            if not isinstance(enum_vals, list) or not enum_vals:
                raise ValueError(f"unsupported schema at {location}")
            if encoded not in [canonical(x) for x in enum_vals]:
                raise ValueError(f"unknown vocabulary at {location}")
    types = {
        "object": dict,
        "array": list,
        "string": str,
        "boolean": bool,
        "integer": int,
        "null": type(None),
    }
    expected = schema.get("type")
    if expected is not None:
        expected_list = [expected] if isinstance(expected, str) else expected
        if (
            not isinstance(expected_list, list)
            or not expected_list
            or any(not isinstance(t, str) or t not in types for t in expected_list)
        ):
            raise ValueError(f"unsupported schema at {location}")
        if not any(type(value) is types[t] for t in expected_list):
            raise ValueError(f"type mismatch at {location}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        req = schema.get("required", [])
        if (
            not isinstance(properties, dict)
            or any(not isinstance(k, str) for k in properties)
            or not isinstance(req, list)
            or any(not isinstance(k, str) for k in req)
        ):
            raise ValueError(f"unsupported schema at {location}")
        if "additionalProperties" in schema and type(schema["additionalProperties"]) is not bool:
            raise ValueError(f"unsupported schema at {location}")
        if set(req) - set(value):
            raise ValueError(f"missing fields at {location}")
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            raise ValueError(f"unknown fields at {location}")
        for key in sorted(set(value) & set(properties)):
            check_shape(value[key], properties[key], document, f"{location}.{key}", depth + 1)
    if isinstance(value, list):
        min_i = _non_neg_int_kw(schema, "minItems", 0, location)
        max_i = _non_neg_int_kw(schema, "maxItems", MAX_BYTES, location)
        if "uniqueItems" in schema and type(schema["uniqueItems"]) is not bool:
            raise ValueError(f"unsupported schema at {location}")
        if not min_i <= len(value) <= max_i:
            raise ValueError(f"array bounds at {location}")
        if schema.get("uniqueItems") and len({canonical(x) for x in value}) != len(value):
            raise ValueError(f"duplicate items at {location}")
        for index, item in enumerate(value):
            check_shape(item, schema.get("items", {}), document, f"{location}[{index}]", depth + 1)
    if isinstance(value, str):
        min_l = _non_neg_int_kw(schema, "minLength", 0, location)
        max_l = _non_neg_int_kw(schema, "maxLength", MAX_BYTES, location)
        if not min_l <= len(value) <= max_l:
            raise ValueError(f"string bounds at {location}")
        if "pattern" in schema:
            pat = schema["pattern"]
            if not isinstance(pat, str):
                raise ValueError(f"unsupported schema at {location}")
            if _json_schema_regex(pat).search(value) is None:
                raise ValueError(f"invalid string at {location}")


def validate(data: dict[str, Any], schema: dict[str, Any]) -> None:
    check_shape(data, schema, schema)
    reject_sensitive(data)
    ids: set[str] = set()
    concerns: set[str] = set()
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
        if any(
            not isinstance(x["symbol"], str) or not x["symbol"].isidentifier()
            for x in rule["evidence"]
        ):
            raise ValueError("rule evidence requires a valid Python symbol identifier")
    ownership = data["ownershipEvidence"]
    if {x["source"] for x in ownership} != {"routing", "performance"}:
        raise ValueError("ownership provenance incomplete")
    if any(x["kind"] != "ownership" or x["symbol"] is not None for x in ownership):
        raise ValueError("invalid ownership evidence")
    for evidence in [*ownership, *(x for rule in data["rules"] for x in rule["evidence"])]:
        if evidence["path"].startswith("-") or any(
            part in {"", ".", ".."} for part in evidence["path"].split("/")
        ):
            raise ValueError("noncanonical evidence path")


def _read_git_blob(root: str | Path, revision: str, path: str) -> bytes:
    root_path = _validate_non_symlink_dir(root)
    if not isinstance(revision, str) or _HEX40_RE.fullmatch(revision) is None:
        raise ValueError("source revision must be an immutable 40-hex commit SHA")
    if (
        not isinstance(path, str)
        or path.startswith("-")
        or _REL_PATH_RE.fullmatch(path) is None
        or any(part in {".", ".."} for part in path.split("/"))
    ):
        raise ValueError("noncanonical evidence path")
    result = subprocess.run(
        ["git", "-C", str(root_path), "show", f"{revision}:{path}"],
        check=True,
        capture_output=True,
        timeout=10,
    )
    if len(result.stdout) > MAX_BYTES:
        raise ValueError("source blob exceeds verification bound")
    return result.stdout


def _extract_python_symbols(raw: bytes) -> set[str]:
    if len(raw) > MAX_BYTES or b"\x00" in raw:
        raise ValueError("invalid Python source blob")
    tree = ast.parse(raw)
    symbols: set[str] = set()
    stmt_stack: list[list[ast.stmt]] = [tree.body]
    while stmt_stack:
        body = stmt_stack.pop()
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.add(stmt.name)
            elif isinstance(stmt, ast.ClassDef):
                symbols.add(stmt.name)
                stmt_stack.append(stmt.body)
            elif isinstance(stmt, ast.Assign) or (
                isinstance(stmt, ast.AnnAssign) and stmt.value is not None
            ):
                target_stack = list(stmt.targets) if isinstance(stmt, ast.Assign) else [stmt.target]
                while target_stack:
                    tgt = target_stack.pop()
                    if isinstance(tgt, ast.Name):
                        symbols.add(tgt.id)
                    elif isinstance(tgt, (ast.Tuple, ast.List)):
                        target_stack.extend(tgt.elts)
    return symbols


def verify_sources(data: dict[str, Any], roots: dict[str, str | Path]) -> int:
    """Read immutable Git blobs, verifying hashes and named Python symbols only."""
    cache: dict[tuple[str, str], bytes] = {}
    symbol_cache: dict[tuple[str, str], set[str]] = {}
    evidence = [
        *data["ownershipEvidence"],
        *(x for rule in data["rules"] for x in rule["evidence"]),
    ]
    for item in evidence:
        source, path = item["source"], item["path"]
        key = (source, path)
        if key not in cache:
            revision = data["sources"][source]["revision"]
            cache[key] = _read_git_blob(roots[source], revision, path)
        raw = cache[key]
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError(f"source digest mismatch: {source}/{path}")
        symbol = item["symbol"]
        if item["kind"] != "ownership":
            if not isinstance(symbol, str) or not symbol.isidentifier():
                raise ValueError(f"invalid source symbol: {source}/{path}")
        if symbol is not None:
            if key not in symbol_cache:
                symbol_cache[key] = _extract_python_symbols(raw)
            if symbol not in symbol_cache[key]:
                raise ValueError(f"source symbol missing: {source}/{path}")
    return len(cache)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "docs/standard/catalog.json")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--routing-root", type=Path)
    parser.add_argument("--performance-root", type=Path)
    args = parser.parse_args(argv)
    report: dict[str, Any] = {
        "schema": "wellmanifest.goal/conformance/v1",
        "valid": False,
        "effectAuthority": False,
        "runtimeConformanceVerified": False,
        "semanticReviewVerified": False,
        "sourceEvidenceVerified": False,
        "findings": [],
    }
    code = "WMGOAL-INPUT-001"
    try:
        data, digest = read_json(args.catalog)
        schema, _ = read_json(ROOT / "models/catalog.schema.json")
        report["catalogSha256"] = digest
        code = "WMGOAL-CONTRACT-001"
        validate(data, schema)
        report["ruleCount"] = len(data["rules"])
        roots = {
            "goal": args.source_root,
            "routing": args.routing_root,
            "performance": args.performance_root,
        }
        if any(roots.values()):
            code = "WMGOAL-SOURCE-001"
            if not all(roots.values()):
                raise ValueError("all three source roots are required for source verification")
            report["verifiedBlobs"] = verify_sources(data, roots)
            report["sourceEvidenceVerified"] = True
        report["valid"] = True
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        RecursionError,
        SyntaxError,
        subprocess.SubprocessError,
    ) as error:
        report["findings"].append({"code": code, "message": str(error)})
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
