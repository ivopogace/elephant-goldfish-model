# Overdue reminders for lendr

* **Author:** Robin Fixture
* **Date:** 2026-11-09

## Overview

lendr is a small offline command-line loan tracker for the fictional Maple Hollow Tool Library. Volunteers record loans by hand, and today they find late loans by reading `lendr list` and comparing due dates by eye, which misses loans. This feature adds a single command that lists every overdue loan and can print hand-deliverable reminder notes. It runs offline, uses only the Python standard library, reads the existing `loans.json` without changing it, and never sends anything itself.

## Analysis

The concept fits the codebase. `loans.json` already stores every loan with a `due` date, and `store.open_loans()` already filters out returned loans. The overdue check is a small, read-only addition. The reviewers' concerns are not about whether to build it; they are about three unspecified decisions and one piece of scope creep.

### 1. "Reminder notes" is the underspecified half

The success criterion is "a volunteer finds every late loan with one command in under ten seconds." A filtered, sorted list satisfies that. The note half adds decisions nobody has made: wording, per-loan versus per-member grouping, output destination, and whether the library actually chases late members. The data model has no contact information, so a note can only restate what the list prints. The reviewers recommend shipping the list first and treating notes as an optional, explicitly specified addition.

### 2. One data path, one output shape

`store.open_loans()` is the single source of truth for open loans. The overdue command must reuse it, or add a thin `store.overdue_loans(today)` built on it. It must not re-parse `loans.json` or re-implement the returned filter. `datetime.date` is already imported in `cli.py`. No new module, dataclass, config file, database, index, or cache is needed. At one run per day on one shared laptop, the ten-second budget is a human-attention budget, not a compute budget.

### 3. Define "late" and the boundary

The concept never says whether a loan due today is late. Pin it: a loan is overdue when its due date is before today. Use calendar-day math (`date.today() - due`). No grace period, no business-day calendar, no timezone handling. Cover the boundary with unit tests for due yesterday, due today, and due tomorrow.

### 4. Output contract

* Default: a compact list of overdue loans, sorted by due date ascending (most overdue first), with days late and a total count.
* Optional: a `--notes` flag for hand-deliverable reminder notes, or a summary block followed by clearly delimited notes.
* Empty state: print "No overdue loans." explicitly.
* Exit codes: 0 when the check runs (even with zero overdue loans), non-zero only for unreadable data. Diagnostics on stderr, normal output on stdout.
* The command is read-only: it never writes `loans.json` or any other file.
* Print the as-of date and the resolved data-file path so a wrong clock or wrong working directory is visible.

### 5. Missing file and malformed rows must not fake an all-clear

`store.PATH` is relative to the current working directory, while the README says loans live "next to the program." Running from another directory can read a missing file, and `_load()` returns an empty list, which would print "no overdue loans" while loans are actually late. The new command must distinguish "no data file" from "no late loans" and print a loud, actionable error. A row with a missing or malformed due date must be skipped with a stderr warning, never crash the whole run. Corrupt JSON should produce a one-line error and a non-zero exit, not a traceback. Fixing `PATH` for all commands is a separate rollout change and is not required for this feature, but the new command must not silently inherit the false-negative behavior.

### 6. No new state, no schema change

Do not add `reminded_at`, contact fields, a `reminders.json`, or any reminder history. The feature is a pure function over existing fields. Rollback is a code revert with no data migration. If reminder history is ever needed later, it requires a separate additive, versioned schema with defaults for old rows.

### 7. Cost and quota

The product has no network, database, or LLM. Token cost is $0 by design. Forbid non-standard-library imports and any sending library in the new code path. No cron job, daemon, background thread, or scheduler. The file grows with every loan ever recorded because returned rows are kept, so the command is O(total loans ever). At a plausible library scale this is still sub-second, but the design should state the growth model rather than assume a tiny file.

### 8. Maintainability and testability

Put the lateness computation in a pure function with an injectable today, for example `store.overdue_loans(today=None)` and `is_overdue(due, today)`. Keep note rendering in a separate function. The CLI branch is wiring only. Add `help=` text to the subparser and a README entry so volunteers discover the command. Add standard-library `unittest` coverage for the boundary dates, the missing-file case, and the malformed-row case.

### 9. Inventive contradictions and Ideal Final Result

* **Reuse existing helpers versus no false negatives.** Resolution: extract file loading so "no file" and "empty file" are distinct, and fail loudly on missing data. Secondary trade-off: a wrong-directory run now errors instead of silently passing.
* **Fast scan versus complete notes.** Resolution: compute the late set once, then render it two ways (compact list by default, notes behind a flag). Secondary trade-off: two output modes to document and test; they must share one lateness computation.
* **Offline operation with no authoritative time source versus correct overdue determination.** Resolution: print the as-of date and open-loan count on every run so a wrong clock is visible. Secondary trade-off: the system still cannot detect a clock jump by itself.
* **Ideal Final Result:** `lendr overdue` never confuses "no data" with "no late loans"; it computes the late set once, renders it compactly by default, and produces notes on demand without re-reading the file.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * A single command that lists every open loan with a due date before today.
  * Sorted output (most overdue first) with days late and a total count.
  * Optional hand-deliverable reminder notes derived only from existing loan fields.
  * Explicit empty state, error handling for missing or unreadable data, and non-zero exit on error.
  * Read-only behavior: no writes to `loans.json` or any new file.
  * Unit tests for the lateness boundary and data-error cases.
  * Command help and README documentation.
* **Out-of-Scope Non-Goals:**
  * Email, SMS, or any other sending.
  * Fines, member accounts, contact information, or reminder history.
  * Schema changes to `loans.json` or a second data store.
  * Scheduling, daemons, background jobs, caching, indexing, or a database.
  * Business-day or holiday-calendar lateness, grace periods, or timezone handling.
  * Changes to the existing `loan`, `return`, and `list` command behavior or output.

## Alternatives Weighed

* **Email or SMS reminders:** rejected by the author (out of scope; the program must not send anything).
* **Fines and member accounts:** rejected by the author (out of scope).
* **Cron job or background daemon:** rejected during ideation; one run per day needs no scheduler, and a background writer would add concurrency on a store with no locking.
* **Database, index, or cache:** rejected during ideation; there is no query load, and a full-file JSON scan is the entire query.
* **Persisting reminder notes or a `reminded_at` field:** rejected during ideation; it changes the file format the feature promises to keep, and a stale note is worse than none.
* **Business-day or holiday-calendar lateness:** rejected during ideation; there is no SLA, and a calendar is a data dependency with maintenance cost.
* **`--grace-days` flag:** rejected during ideation; no business rule requires it, and it adds a decision volunteers must understand.
* **A separate `reminders.py` or `formatters.py` module:** rejected during ideation; one query function in `store.py` and one render function are enough.
* **Adding an overdue footer to `lendr list`:** not chosen; the existing command's output should stay unchanged, so discovery happens through `--help` and the README instead.

## Key Decisions & Staging for Next Steps

* **Lateness definition:** a loan is overdue when `due < today`, using calendar days. A loan due today is not overdue.
* **Data path:** reuse `store.open_loans()`; add `store.overdue_loans(today=None)` and `is_overdue(due, today)` in `store.py`.
* **Output:** compact sorted list by default; `--notes` for reminder notes. Empty state and error behavior are part of the contract.
* **State:** the command is a pure, stateless read over existing fields. No new files, no schema changes, no reminder history.
* **Error handling:** missing file, corrupt JSON, and malformed due dates produce stderr diagnostics and a non-zero exit; the command never prints a traceback and never silently reports "no overdue loans" when it could not read the data.
* **Command name:** recommend `lendr overdue` with `--notes`; confirm the name during drafting.
* **Staging:** Phase 1 delivers the overdue listing with tests and documentation. Phase 2 adds `--notes` only if volunteers act on the list and ask for notes.
