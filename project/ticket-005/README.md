# Ticket 005: Harden Goal regular-file I/O, strict JSON bounds, and ancestor symlink guards

- **ID**: ticket-005
- **Owner**: tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-11

## Goal and scope

Harden `wellmanifest/goal` offline catalog conformance (`operations/conformance.py`):
enforce `O_NOFOLLOW | O_NONBLOCK` regular-file verification and inode stability in
`read_regular_bytes` / `read_json`; reject non-standard JSON constants, overflow IEEE-754
floats (`1e999`/`-1e999`), `RecursionError`, non-string object keys, and nesting deeper than
`MAX_JSON_DEPTH = 64` iteratively across `read_json`, `check_shape`, and `reject_sensitive`;
avoid redundant recursive `canonical()` serialization unless `const`/`enum` is present;
reject ancestor symlinks in `_read_git_blob`; add adversarial regression tests in
`operations/test_goal_hardening.py`; and mark merged `ticket-004` `DONE`.

## Acceptance criteria

- [x] AC-01: `operations/conformance.py` enforces `O_NOFOLLOW | O_NONBLOCK` regular-file
      reads, finite float / `MAX_JSON_DEPTH = 64` / `RecursionError` / string-key bounds,
      iterative `reject_sensitive`, and ancestor symlink checks in `_read_git_blob` while
      keeping all modules `< 500` lines.
- [x] AC-02: `operations/test_conformance.py` and `operations/test_goal_hardening.py` pass
      `ruff check --no-cache operations`, `python3 operations/conformance.py`, and
      `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`.
- [x] AC-03: Close merged `ticket-004`, and pass `./project/governance-check.sh --base origin/main`
      and `wellman check`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
