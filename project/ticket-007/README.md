# Ticket 007: Modularize goal_io and harden relative symlink-parent traversal, JSON bounds, and schema keyword checks

- **ID**: ticket-007
- **Owner**: tom
- **Status**: DONE
- **Workflow state**: DONE
- **Created**: 2026-11-11

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: On 2026-11-11 user authorized auditing, fixing bugs, optimizing, and hardening `wellmanifest/*` standard repositories.

Extract bounded regular-file I/O, strict JSON parsing, symlink-ancestor checks, and secret scanning into `operations/goal_io.py` so `operations/conformance.py` drops well below 500 lines; prevent `os.path.abspath` from lexically collapsing `sym_dir/..` relative symlink traversal in `main` and `_validate_non_symlink_dir`; bound JSON integer digit length before `int()` conversion in `read_json`; enforce UTF-8 surrogate and finite integer bounds in `canonical` and `reject_sensitive`; fail closed on malformed JSON Schema keyword types in `check_shape`; expand `operations/test_goal_hardening.py`; and reconcile merged `project/ticket-006/README.md` status to `DONE`.

## Acceptance criteria

- [x] AC-01: Extract `operations/goal_io.py` (< 500L), block `sym_dir/..` relative symlink traversal in `main` and `_validate_non_symlink_dir`, reject 5000+ digit JSON integers and lone UTF-16 surrogates in `read_json`/`canonical`/`reject_sensitive`, fail closed on malformed JSON Schema keyword values in `check_shape`, and mark `project/ticket-006/README.md` `DONE`.
- [x] AC-02: All Python modules in `operations/` remain strictly `< 500` lines and pass `ruff check --no-cache operations`, `python3 operations/conformance.py`, `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider`, `./project/governance-check.sh --base origin/main`, and `wellman check` with 0 errors.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
