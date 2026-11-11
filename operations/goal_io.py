"""Bounded regular-file I/O, strict JSON loading, symlink guards, and secret scanning for Goal."""

from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path
from typing import Any

MAX_BYTES = 1024 * 1024
MAX_JSON_DEPTH = 64
_SENSITIVE_RE = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9_]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"
    r"|AK"
    r"IA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z0-9 ]*PRI"
    r"VATE KEY-----"
    r"|(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{16,})"
)


def _check_utf8_str(value: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as err:
        raise ValueError("lone UTF-16 surrogate in JSON string is forbidden") from err


def _enforce_json_depth_and_keys(root: Any, *, max_depth: int = MAX_JSON_DEPTH) -> None:
    if type(max_depth) is not int or max_depth < 1:
        raise ValueError("max_depth must be a positive integer")
    stack: list[tuple[Any, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            raise ValueError(f"JSON nesting depth exceeds maximum of {max_depth}")
        if isinstance(current, str):
            _check_utf8_str(current)
        elif type(current) is int:
            try:
                ok = math.isfinite(float(current))
            except OverflowError:
                ok = False
            if not ok:
                raise ValueError("JSON integer magnitude exceeds finite range")
        elif isinstance(current, float) and not math.isfinite(current):
            raise ValueError("non-finite JSON float is forbidden")
        elif isinstance(current, dict):
            next_depth = depth + 1
            if next_depth > max_depth and current:
                raise ValueError(f"JSON nesting depth exceeds maximum of {max_depth}")
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object keys must be strings")
                _check_utf8_str(key)
                if isinstance(item, (dict, list, str, int, float)):
                    stack.append((item, next_depth))
        elif isinstance(current, list):
            next_depth = depth + 1
            if next_depth > max_depth and current:
                raise ValueError(f"JSON nesting depth exceeds maximum of {max_depth}")
            for item in current:
                if isinstance(item, (dict, list, str, int, float)):
                    stack.append((item, next_depth))


def canonical(value: Any) -> str:
    _enforce_json_depth_and_keys(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False
    )


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


def _parse_finite_int(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > 309:
        raise ValueError("JSON integer magnitude exceeds finite range")
    parsed = int(token)
    try:
        ok = math.isfinite(float(parsed))
    except OverflowError:
        ok = False
    if not ok:
        raise ValueError("JSON integer magnitude exceeds finite range")
    return parsed


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
        elif ch == "^" and not in_class:
            out.append(r"\A")
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
            _check_utf8_str(current)
            if _SENSITIVE_RE.search(current):
                raise ValueError("inline secret material is forbidden")
        elif isinstance(current, list):
            for item in current:
                stack.append((item, depth + 1))
        elif isinstance(current, dict):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object keys must be strings")
                _check_utf8_str(key)
                if _SENSITIVE_RE.search(key):
                    raise ValueError("inline secret material is forbidden")
                stack.append((item, depth + 1))


def _check_no_symlink_ancestors(
    path: str | Path, *, include_self: bool, error_message: str
) -> Path:
    raw_path = os.fspath(path)
    path_obj = Path(raw_path)
    if not path_obj.is_absolute():
        cur = Path()
        parts = path_obj.parts if include_self else path_obj.parts[:-1]
        for part in parts:
            cur = cur / part
            if part not in {".", ".."} and cur.is_symlink():
                raise ValueError(error_message)
    abs_path = Path(os.path.abspath(raw_path))
    if include_self and abs_path.is_symlink():
        raise ValueError(error_message)
    for anc in abs_path.parents:
        if len(anc.parts) > 2 and anc.is_symlink():
            raise ValueError(error_message)
    return abs_path


def read_regular_bytes(path: str | Path, *, max_bytes: int = MAX_BYTES) -> bytes:
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    raw_path = os.fspath(path)
    _check_no_symlink_ancestors(
        raw_path, include_self=False, error_message="symbolic link JSON input is forbidden"
    )
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
            parse_int=_parse_finite_int,
        )
    except RecursionError as err:
        raise ValueError(f"JSON nesting depth exceeds maximum of {MAX_JSON_DEPTH}") from err
    _enforce_json_depth_and_keys(data)
    return data, hashlib.sha256(raw).hexdigest()


def _validate_non_symlink_dir(root: str | Path) -> Path:
    abs_root = _check_no_symlink_ancestors(
        root, include_self=True, error_message="source root must be a non-symlink directory"
    )
    if not abs_root.is_dir():
        raise ValueError("source root must be a non-symlink directory")
    return abs_root
