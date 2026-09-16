# Ticket 002: Adopt wellmanifest/new-project 0.20.32

- **ID**: ticket-002
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-16

## Goal and scope

To be completed from human-owned input.

## Acceptance criteria



## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
## Validation evidence

- `goal governance adopt --latest --check` — adopted 0.20.32 @ b6ba9c21
- `./project/governance-check.sh` — GOV-PASS (0 errors, 0 warnings)
- json.tool lock OK; bash -n on new-ticket.sh + install-agent-hosts.sh OK
- Local `manifest.json` integration extension aligned with 0.20.32 base (stale
  0.20.25-era `.governance/*`/AGENTS.md entries removed; extendable target).

