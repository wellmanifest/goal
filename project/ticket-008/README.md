# Ticket 008: Harden goal_io symlink-parent traversal, secret-key checks, and catalog prose controls

- **ID**: ticket-008
- **Owner**: tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-11

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: On 2026-11-11 user authorized auditing, fixing bugs, optimizing, and hardening `wellmanifest/*` standard repositories.

Harden `_check_no_symlink_ancestors` in `operations/goal_io.py` against un-normalized absolute (`sym_dir/../real`) and sibling relative (`../sym_dir`) symlink-parent traversal before `os.path.abspath`, declare `__all__`, and reject credential-named dictionary keys in `reject_sensitive`; pass `allow_nan=False` in `conformance.main` JSON serialization and reject blank or C0/DEL/C1 control-character strings in unpatterned catalog prose fields (`coverage.scope`, `coverage.exclusions[*]`, `rules[*].statement`); expand `operations/test_goal_hardening.py`; and reconcile merged `project/ticket-007/README.md` status to `DONE`.

## Acceptance criteria

- [x] AC-01: Reject un-normalized absolute and sibling relative symlink-parent traversal in `_check_no_symlink_ancestors`, reject credential-named dictionary keys in `reject_sensitive`, reject blank or C0/DEL/C1 control-character catalog prose in `validate`, pass `allow_nan=False` in `main`, and mark `project/ticket-007/README.md` `DONE`.
- [x] AC-02: All Python modules in `operations/` remain strictly `< 500` lines and pass `ruff check --no-cache operations`, `python3 operations/conformance.py`, `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider`, `./project/governance-check.sh --base origin/main`, and `wellman check` with 0 errors.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
