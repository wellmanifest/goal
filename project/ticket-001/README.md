# Ticket 001: Formalize Goal contracts and extraction ownership

- **ID**: ticket-001
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-09-14

## Goal and scope

Formalize existing semcod/goal contracts as a local, transitional Wellmanifest
standard with stable rule IDs, source evidence, conformance vectors and explicit
extraction destinations. Do not copy runtime code or redefine existing pack
authority. The user explicitly approved the local governance baseline on
2026-09-14; no remote creation or publication is authorized.

## Acceptance criteria

- [x] AC-01: Catalog distinguishes observed Goal behavior, referenced pack ownership
  and proposed improvements; every extracted rule retains a stable ID and source.
- [x] AC-02: Closed-schema data and deterministic offline conformance reject
  authority escalation, owner duplication and unsupported extraction claims.
- [x] AC-03: Standard, catalog and extraction process are indexed, tested and
  governed locally without changing semcod/goal or creating a remote.

Deliverable: [Goal standard and extraction process](../../docs/information/goal-standard.md).
Local checks: 30 conformance tests passed; 14 exact Git blobs and named symbols
verified; JSON Schema Draft 2020-12 model/catalog validation passed; managed gate
passed with zero errors/warnings. No semantic or runtime certification claimed.
The managed continuity capture cannot resolve a repository without origin
(GOV-CONTINUITY-003); no remote is invented to satisfy it. Preserve local history
and a secret-scanned external snapshot, not a fabricated v2 checkpoint.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
