# Goldfish Review Report

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (`full file, lines 1-74`)

**Stage:** 5 — Initial Zoom Out Review

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-zoom-out` | completed |
| `egm-inventive-catalyst` | completed |

## Prerequisite (Context Sufficiency)

PASS. The document defines the objective (surface overdue loans, optionally generate reminder notes), the motivation (volunteers only discover lateness when another member asks; `lendr list` shows no lateness), and grounds it in the README's constraints (small CLI, JSON file, no network, program never sends anything). A fresh reader can determine what and why. No context failure.

## Prioritized Findings (Blockers -> Major -> Nits)

### `--today` flag adds CLI surface for a test-only need - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Technical Plan, lines 50–51; Detailed Implementation Plan, line 68
* **Discrepancy Description:** The `--today YYYY-MM-DD` CLI flag exists only so tests are repeatable, but the design already makes `late_loans(rows, today)` a pure function that accepts the date as a parameter. Tests can pass a fixed date directly — the design itself says the function is "needed so the date logic can be tested without the command line."
* **Rationale & Recommendation:** A user-facing `--today` flag adds CLI surface area for a non-user requirement. Drop it (or justify it with a real volunteer workflow, e.g. backdating a run) to keep the interface minimal.

### Reminder-folder claim is inaccurate - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Technical Plan, lines 40–42
* **Discrepancy Description:** "Existing reminder files are overwritten so the folder always reflects the current state" is inaccurate. Overwriting only refreshes files for members who are currently late; a member whose loans were returned keeps a stale `reminders/<member>.txt`, so the folder does not reflect current state.
* **Rationale & Recommendation:** Either delete files for members with no late loans, or correct the claim.

### `--remind` may be a second feature layered on the root fix - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Overview, lines 17–19; Goals, line 25; Technical Plan, lines 40–42
* **Discrepancy Description:** `--remind` is a second feature layered on top of the root fix. The root problem — volunteers cannot see what is overdue — is fully solved by `lendr overdue` alone. The Problem section establishes a discovery pain, not a reminder-generation pain; the reminder workflow is asserted in the Goals/Overview without evidence it is needed now.
* **Rationale & Recommendation:** Confirm volunteers actually want printable notes; if not, deferring `--remind` reduces the first iteration to the smallest possible change (one command, stdout only, no file IO).

### Detailed plan sits slightly below architectural altitude - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Detailed Implementation Plan, lines 61–74
* **Discrepancy Description:** The section names concrete helper signatures (`late_loans(rows, today)`, `write_reminders(rows, folder)`) and enumerates individual test cases, which sits slightly below the architectural altitude the standard asks for (components, interfaces, data flow).
* **Rationale & Recommendation:** For a feature this small the architecture is already evident, so this is proportionate — but the plan could stay at the component/data-flow level without losing clarity.

## Inventive Catalyst

No false compromise detected

## Passed Checks
* **Root problem focus:** Directly addresses the underlying visibility gap, not a symptom; consistent with README's "no network / program never sends anything" philosophy.
* **YAGNI / premature optimization:** No caching, async, or speculative abstractions; Non-Goals explicitly exclude email, fines, accounts, catalogue, and storage changes.
* **Reuse:** `store.open_loans()` is reused; `argparse`/`datetime`/`pathlib` follow existing patterns; no duplicate utility found.
* **Minimalist data flow:** `loans.json -> store.open_loans() -> overdue filter -> stdout` (+ optional reminders branch) is the shortest path to the goal.
* **Pattern consistency / placement:** New `overdue.py` module keeps CLI thin and separates domain logic from argument parsing, matching the existing `store.py`/`cli.py` split.
* **Security awareness:** Rejecting `/` in member names before using them as file names is a reasonable path-traversal guard.
