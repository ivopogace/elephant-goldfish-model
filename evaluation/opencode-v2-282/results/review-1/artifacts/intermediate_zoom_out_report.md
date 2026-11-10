# Goldfish Review Report

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (`full file, lines 1-74`)

**Stage:** 8 — Intermediate Zoom Out Review

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-zoom-out` | completed |

## Prerequisite (Context Sufficiency)

PASS. The objective, motivation, and constraints remain clear and grounded in the README (small CLI, JSON file, no network, program never sends anything).

## Stage Delta

The target document is **unchanged since Stage 5**. It is still 74 lines, and every passage the Stage 5 report quoted or cited is byte-for-byte intact (the `--today` text at lines 50-51/68, the reminder-folder claim at lines 40-42, the `--remind` overview/goals text, and the helper-signature/test enumeration at lines 61-74). No additions or mitigations were made in the Comprehension or Critic stages. Consequently, **all four Stage 5 findings remain open at the same severity**, and no new scope was introduced. The high-level architecture still holds: `loans.json -> store.open_loans() -> overdue filter -> stdout` (+ optional reminders branch) is the minimal path, and reuse/placement checks still pass.

## Prioritized Findings (Blockers -> Major -> Nits)

### `--today` flag still adds CLI surface for a test-only need - Severity: Nit (unmitigated)
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Technical Plan, lines 50-51; Detailed Implementation Plan, line 68
* **Simplicity Rationale:** The design already exposes `late_loans(rows, today)` as a pure function precisely so tests can pass a fixed date without the command line. A user-facing `--today` flag therefore adds interface surface for a non-user requirement. Drop it, or justify it with a concrete volunteer workflow.

### Reminder-folder freshness claim is still inaccurate - Severity: Nit (unmitigated)
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Technical Plan, lines 40-42
* **Simplicity Rationale:** Overwriting only refreshes files for currently-late members; a member whose loans were returned keeps a stale `reminders/<member>.txt`. The folder therefore does not "always reflect the current state." Either delete files for members with no late loans, or correct the claim.

### `--remind` remains a second feature not grounded in the stated problem - Severity: Nit (unmitigated)
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Overview, lines 17-19; Goals, line 25; Technical Plan, lines 40-42
* **Simplicity Rationale:** The Problem section establishes a discovery pain (volunteers cannot see what is overdue), which `lendr overdue` alone solves. The reminder-generation workflow is asserted without evidence in the Problem/Overview. Confirm volunteers actually want printable notes; otherwise deferring `--remind` reduces the first iteration to one command, stdout only, no file IO. This is the largest remaining simplicity risk.

### Detailed plan still sits slightly below architectural altitude - Severity: Nit (unmitigated)
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Detailed Implementation Plan, lines 61-74
* **Simplicity Rationale:** The section names concrete helper signatures (`late_loans(rows, today)`, `write_reminders(rows, folder)`) and enumerates individual test cases. For a feature this small the architecture is already evident, so this is proportionate — but the plan could stay at the component/data-flow level without losing clarity.

### `reminders/` folder creation is unspecified - Severity: Nit (new)
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Technical Plan, lines 40-42; Detailed Implementation Plan, lines 63-66
* **Simplicity Rationale:** The design says the command writes into a `reminders/` folder but never states that the folder is created. On a fresh checkout `write_reminders(rows, folder)` will fail. One line ("the command creates `reminders/` if missing") closes the gap; otherwise the optional feature is not usable as described.

## Reuse Verification (code search)
* `store.open_loans()` exists at `src/lendr/store.py:30` and is correctly reused — no duplicate data access.
* No existing overdue, reminder, or date-diff utility exists in the codebase (`src/lendr/` contains only `store.py`, `cli.py`, `__init__.py`); the proposed `overdue.py` is not reinventing anything.
* `argparse`, `datetime`, and `pathlib` are already the established tools in `cli.py`/`store.py`; the plan follows existing patterns.

## Passed Checks
* **Root problem focus:** `lendr overdue` directly closes the visibility gap; no symptom-only patch.
* **Project alignment:** No network, no sending, JSON storage unchanged — consistent with README.
* **Minimalist data flow:** Shortest path from `loans.json` to the goal; no caching, async, or speculative abstraction.
* **Placement:** New `overdue.py` keeps the CLI thin and matches the existing `store.py`/`cli.py` separation.
* **Security awareness:** Rejecting `/` in member names before using them as file names is a reasonable path-traversal guard.

## Verdict
The architecture holds and the document remains simple and well-scoped, but the Stage 5 review had no effect: all four nits are unmitigated and one new completeness gap (folder creation) is present. None are blockers; the only item with real weight is the unconfirmed `--remind` feature, which should be validated or deferred before implementation.
