"""Offline catalog conformance; never executes Goal, migration recipes or a model."""

from __future__ import annotations

import argparse
import ast
import errno
import hashlib
import json
import math
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 1024 * 1024
MAX_JSON_DEPTH = 64
_HEX40_RE = re.compile(r"[0-9a-f]{40}\Z")
_REL_PATH_RE = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")
_SENSITIVE_RE = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9_]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"
    r"|(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{16,})"
)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if not isinstance(key, str):
            raise ValueError("JSON object keys must be strings")
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(token: str) -> Any:
    raise ValueError(f"non-standard JSON constant {token!r} is forbidden")


def _parse_finite_float(token: str) -> float:
    parsed = float(token)
    if not math.isfinite(parsed):
        raise ValueError(f"JSON float out of finite IEEE-754 range: {token!r}")
    return parsed


def _enforce_json_depth_and_keys(root: Any, *, max_depth: int = MAX_JSON_DEPTH) -> None:
    stack: list[tuple[Any, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            raise ValueError(f"JSON nesting depth exceeds maximum of {max_depth}")
        if isinstance(current, float) and not math.isfinite(current):
            raise ValueError("non-finite JSON float is forbidden")
        if isinstance(current, dict):
            next_depth = depth + 1
            if next_depth > max_depth and current:
                raise ValueError(f"JSON nesting depth exceeds maximum of {max_depth}")
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object keys must be strings")
                if isinstance(item, (dict, list, float)):
                    stack.append((item, next_depth))
        elif isinstance(current, list):
            next_depth = depth + 1
            if next_depth > max_depth and current:
                raise ValueError(f"JSON nesting depth exceeds maximum of {max_depth}")
            for item in current:
                if isinstance(item, (dict, list, float)):
                    stack.append((item, next_depth))


def _json_schema_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    in_class = False
    escaped = False
    for ch in pattern:
        if escaped:
            out.append(ch)
            escaped = False
        elif ch == "\\":
            out.append(ch)
            escaped = True
        elif ch == "[" and not in_class:
            in_class = True
            out.append(ch)
        elif ch == "]" and in_class:
            in_class = False
            out.append(ch)
        elif ch == "$" and not in_class:
            out.append(r"\Z")
        else:
            out.append(ch)
    return re.compile("".join(out))


def reject_sensitive(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f"JSON nesting depth exceeds maximum of {MAX_JSON_DEPTH}")
        if isinstance(current, str):
            if _SENSITIVE_RE.search(current):
                raise ValueError("inline secret material is forbidden")
        elif isinstance(current, list):
            for item in current:
                stack.append((item, depth + 1))
        elif isinstance(current, dict):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object keys must be strings")
                if _SENSITIVE_RE.search(key):
                    raise ValueError("inline secret material is forbidden")
                stack.append((item, depth + 1))


def read_regular_bytes(path: str | Path, *, max_bytes: int = MAX_BYTES) -> bytes:
    raw_path = os.fspath(path)
    st = os.lstat(raw_path)
    if stat.S_ISLNK(st.st_mode):
        raise ValueError("symbolic link JSON input is forbidden")
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"JSON input must be a regular file: {raw_path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(raw_path, flags)
    except OSError as err:
        if err.errno == errno.ELOOP:
            raise ValueError("symbolic link JSON input is forbidden") from err
        raise
    try:
        fst = os.fstat(fd)
        if not stat.S_ISREG(fst.st_mode):
            raise ValueError(f"JSON input must be a regular file: {raw_path}")
        if (st.st_dev, st.st_ino) != (fst.st_dev, fst.st_ino):
            raise ValueError(f"JSON input changed during open: {raw_path}")
        if fst.st_size > max_bytes:
            raise ValueError("JSON input exceeds 1 MiB")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(65536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("JSON input exceeds 1 MiB")
        return b"".join(chunks)
    finally:
        os.close(fd)


def read_json(path: str | Path) -> tuple[Any, str]:
    raw = read_regular_bytes(path, max_bytes=MAX_BYTES)
    text = raw.decode("utf-8")
    try:
        data = json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=_reject_constant,
            parse_float=_parse_finite_float,
        )
    except RecursionError as err:
        raise ValueError(f"JSON nesting depth exceeds maximum of {MAX_JSON_DEPTH}") from err
    _enforce_json_depth_and_keys(data)
    return data, hashlib.sha256(raw).hexdigest()


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
        if not isinstance(ref, str) or not re.fullmatch(r"#/[\$]defs/[A-Za-z0-9_-]+\Z", ref):
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
        if "enum" in schema and encoded not in [canonical(x) for x in schema["enum"]]:
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
    if expected:
        expected_list = [expected] if isinstance(expected, str) else expected
        if not any(type(value) is types[t] for t in expected_list):
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
            check_shape(item, schema.get("items", {}), document, f"{location}[{index}]", depth + 1)
    if isinstance(value, str):
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", MAX_BYTES):
            raise ValueError(f"string bounds at {location}")
        if "pattern" in schema and _json_schema_regex(schema["pattern"]).search(value) is None:
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


def _validate_non_symlink_dir(root: str | Path) -> Path:
    root_path = Path(os.path.abspath(os.fspath(root)))
    for candidate in (root_path, *root_path.parents):
        if candidate.is_symlink():
            raise ValueError("source root must be a non-symlink directory")
    if not root_path.is_dir():
        raise ValueError("source root must be a non-symlink directory")
    return Path(root)


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


def _collect_scope_targets(target: ast.expr, symbols: set[str]) -> None:
    if isinstance(target, ast.Name):
        symbols.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            _collect_scope_targets(elt, symbols)


def _collect_scope_symbols(body: list[ast.stmt], symbols: set[str]) -> None:
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.add(stmt.name)
        elif isinstance(stmt, ast.ClassDef):
            symbols.add(stmt.name)
            _collect_scope_symbols(stmt.body, symbols)
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                _collect_scope_targets(target, symbols)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            _collect_scope_targets(stmt.target, symbols)


def _extract_python_symbols(raw: bytes) -> set[str]:
    tree = ast.parse(raw)
    symbols: set[str] = set()
    _collect_scope_symbols(tree.body, symbols)
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
        catalog_path = Path(os.path.abspath(os.fspath(args.catalog)))
        data, digest = read_json(catalog_path)
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
