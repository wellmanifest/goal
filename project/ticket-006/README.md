# Ticket 006: Harden Goal JSON overflow/surrogates, symlink ancestors, and iterative AST symbol bounds

- **ID**: ticket-006
- **Owner**: tom
- **Status**: DONE
- **Workflow state**: MERGED
- **Created**: 2026-11-11

## Goal and scope

Harden `wellmanifest/goal` offline catalog conformance (`operations/conformance.py`):
anchor `_HEX40_RE`, `_REL_PATH_RE`, `_LOCAL_REF_RE`, and JSON Schema `^` patterns with
`\A...\Z`; reject `10**400` JSON integer overflow and lone UTF-16 surrogates across
`read_json` and `check_shape`; enforce positive integer `max_bytes` and symlink-ancestor
checks in `read_regular_bytes`; fail closed on unknown JSON Schema `type` names; convert
AST symbol extraction in `_extract_python_symbols` to a bounded iterative stack; expand
`operations/test_goal_hardening.py`; and mark merged `ticket-005` `DONE`.

## Acceptance criteria

- [x] AC-01: `operations/conformance.py` passes offline conformance (`python3 operations/conformance.py`)
      and stays strictly `< 500` lines.
- [x] AC-02: `ruff check --no-cache operations` and `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`
      pass all unit and hardening tests.
- [x] AC-03: Mark merged `ticket-005` `DONE` and pass `./project/governance-check.sh --base origin/main`
      and `wellman check`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
