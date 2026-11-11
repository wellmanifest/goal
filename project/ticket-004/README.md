# Ticket 004: Harden Goal catalog conformance validation and wire pytest

- **ID**: ticket-004
- **Owner**: tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-11

## Goal and scope

Harden `wellmanifest/goal` offline catalog conformance (`operations/conformance.py`
and `models/catalog.schema.json`): translate JSON Schema unescaped `$` anchors to
`\Z` so trailing newlines cannot bypass `pattern` checks on `id`, `concern`, `path`,
or `symbol`; require valid Python identifier `symbol` strings on `implementation` and
`test` rule evidence; restrict `_extract_python_symbols` to module and class-body
scopes so function-local variables cannot satisfy symbol checks; reject symlink inputs
and git flag-prefixed revisions/paths in `read_json` and `_read_git_blob`; reject
inline credential material; wire `pyproject.toml` (`pytest` and `ruff`); and close
merged `ticket-001`, `ticket-002`, and `ticket-003`.

## Acceptance criteria

- [x] AC-01: `models/catalog.schema.json` and `operations/conformance.py` reject
      trailing newlines on patterned strings, invalid/empty rule evidence symbols,
      function-local AST symbol false positives, symlink inputs, git flag-prefixed
      revisions/paths, and inline credentials while keeping all modules `< 500` lines.
- [x] AC-02: `pyproject.toml` and `operations/test_conformance.py` pass
      `ruff check --no-cache operations`, `python3 operations/conformance.py`, and
      `python3 -m pytest -q`.
- [x] AC-03: Close merged `ticket-001`, `ticket-002`, and `ticket-003`, and pass
      `./project/governance-check.sh --base origin/main` and `wellman check`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
