# Overdue reminders for lendr

*   **Author:** Robin Fixture
*   **Status:** Draft
*   **Date:** 2026-11-09

--------------------------------------------------------------------------------

## Overview

`lendr` is a small offline command-line loan tracker for the fictional Maple Hollow Tool Library. Volunteers record which member borrowed which tool and when it is due back. Today they find late loans by reading `lendr list` and comparing due dates by eye, which misses loans. This design adds a single command, `lendr overdue`, that lists every open loan whose due date is before today and can print hand-deliverable reminder notes. The command runs offline, uses only the Python standard library, reads the existing `loans.json` without changing it, and never sends anything itself.

## The Problem

Volunteers detect late loans by scanning the open-loan list and mentally comparing each due date with today. The scan is slow and error-prone: a loan missed once stays missed, and there is no printable note to hand to a member. The data model has no contact information, so a reminder can only restate what the list already shows. The library needs one fast, read-only check that produces the late set and, when asked, a note a volunteer can deliver by hand.

## Goals

*   A single command that lists every open loan with a due date before today.
*   Sorted output (most overdue first) with days late and a total count.
*   Optional hand-deliverable reminder notes derived only from existing loan fields.
*   Explicit empty state, error handling for missing or unreadable data, and a non-zero exit on error.
*   Read-only behavior: no writes to `loans.json` or any new file.
*   Unit tests for the lateness boundary and data-error cases.
*   Command help and README documentation.

## Non-Goals

*   Email, SMS, or any other sending.
*   Fines, member accounts, contact information, or reminder history.
*   Schema changes to `loans.json` or a second data store.
*   Scheduling, daemons, background jobs, caching, indexing, or a database.
*   Business-day or holiday-calendar lateness, grace periods, or timezone handling.
*   Changes to the existing `loan`, `return`, and `list` command behavior or output.

## Open Questions

*   **Command name:** the brief recommends `lendr overdue` with a `--notes` flag. This draft uses that name; confirm it at the section gate or request a change.
*   **Notes format:** per-loan versus per-member grouping and the exact wording are unspecified. Phase 1 ships the listing only, so this is deferred to Phase 2.

## Critical User Journeys (CUJs)

### CUJ 1: Daily overdue check

*   **Given**: `loans.json` exists in the working directory and contains open and returned loans.
*   **When**: A volunteer runs `lendr overdue`.
*   **Then**: The command prints every open loan with a due date before today, sorted most overdue first, with days late and a total count, plus the as-of date and the resolved data-file path. Exit code is 0.

### CUJ 2: Hand-deliverable notes

*   **Given**: The same data file and at least one overdue loan.
*   **When**: A volunteer runs `lendr overdue --notes`.
*   **Then**: The command prints the compact list followed by clearly delimited reminder notes derived only from existing loan fields. No file is written and nothing is sent.

### CUJ 3: Missing or unreadable data

*   **Given**: `loans.json` is missing, corrupt, or contains a row with a missing or malformed due date.
*   **When**: A volunteer runs `lendr overdue`.
*   **Then**: The command never prints "No overdue loans." A missing file or corrupt JSON produces a loud, actionable stderr diagnostic and a non-zero exit. A malformed due date skips that row with a stderr warning and still reports the remaining loans.

## Technical Plan (Architecture)

The feature is a pure, read-only addition to the existing `lendr` package. It adds one query function and two small helpers to `store.py`, one CLI subcommand with its renderers to `cli.py`, and tests. No new module, dataclass, configuration file, database, index, or cache is introduced. The only imports are Python standard-library modules already in use (`json`, `pathlib`, `datetime`) plus `sys` for stderr warnings.

### Data path

`store.open_loans()` remains the single source of truth for open loans. The new `store.overdue_loans(today=None)` reuses that same open-loan filter and adds the lateness check. The existing `loan`, `return`, and `list` commands keep the current lenient loader and are unchanged.

To keep the new command from silently printing "No overdue loans." when the data file is missing, `store.py` gains a strict loader:

*   `store.DataFileError` is a new exception with a user-facing message.
*   `store.read_rows()` reads `PATH` and returns the parsed list. It raises `DataFileError` when the file is missing or contains invalid JSON. An existing file containing `[]` is the empty state and returns `[]`.
*   `store.is_open(row)` extracts the open-loan predicate so `open_loans()` and `overdue_loans()` share one filter.
*   `store.open_loans(rows=None)` keeps its current behavior and accepts an optional preloaded row list so the overdue path can reuse the same filter without re-parsing the file.

### Lateness computation

*   `store.is_overdue(due, today)` is a pure calendar-day comparison: a loan is overdue when `due < today`. A loan due today is not overdue. There is no grace period, business-day calendar, or timezone handling.
*   `store.overdue_loans(today=None)` uses `datetime.date.today()` when `today` is not supplied. It strictly loads the rows, applies the shared open filter, parses each `due` value with `datetime.date.fromisoformat`, and keeps the rows where `is_overdue(due, today)` is true. Each returned item carries `member`, `tool`, `due` (a `date`), and `days_late` (`today - due` in days). The result is sorted by `due` ascending, so the most overdue loan comes first. A row with a missing or malformed `due` is skipped with a one-line stderr warning and does not stop the run.

### Command wiring and rendering

*   `cli.py` adds an `overdue` subparser with a `--notes` flag and `help=` text. The CLI branch is wiring only: it calls `store.overdue_loans()`, catches `store.DataFileError`, and prints the rendered output.
*   A missing file or corrupt JSON is reported as a single stderr line and exits non-zero. A malformed due date is a stderr warning and still exits 0, because the check itself ran.
*   `format_list(loans, today, path)` renders the default compact output: the as-of date, the resolved data-file path, the open-loan count, then one line per overdue loan with member, tool, due date, and days late, followed by the total count. An empty late set renders the explicit line "No overdue loans."
*   `format_notes(loans)` renders hand-deliverable reminder notes from the same late set, using only the existing `member`, `tool`, and `due` fields. Notes are appended behind the `--notes` flag and are clearly delimited from the list.
*   The two renderers share one late set, so the file is read once per run.

### Data flow

```text
loans.json
    │
    ▼
store.read_rows()  ──raises DataFileError──► CLI: one stderr line + exit 1
    │
    ▼
store.open_loans(rows)          (shared open-loan filter)
    │
    ▼
due parse + store.is_overdue(due, today)  ──malformed due──► stderr warning, skip row
    │
    ▼
late set, sorted by due ascending (most overdue first)
    │
    ├─────────────────────────────┐
    ▼                             ▼
format_list(...)            format_notes(...)
    │                             │
    └──────────────┬──────────────┘
                   ▼
                stdout
```

### Growth and cost

The command is O(total loans ever) because returned rows are kept in `loans.json`. At a plausible library scale this is sub-second; the ten-second budget is a human-attention budget, not a compute budget. There is no network, database, or LLM, so token cost is zero by design. The new code path forbids non-standard-library imports and any sending library.

## Alternatives Considered

### Alternative A: Email or SMS reminders

*   **Pros**: reaches members directly without a volunteer delivering anything.
*   **Cons**: requires contact information the data model does not have, adds a sending dependency, and violates the offline, no-send constraint.
*   **Reason for Rejection**: Rejected by author: out of scope; the program must not send anything.

### Alternative B: Fines and member accounts

*   **Pros**: could automate late-fee tracking.
*   **Cons**: adds accounts, balances, and policy rules the library does not use.
*   **Reason for Rejection**: Rejected by author: out of scope.

### Alternative C: Cron job or background daemon

*   **Pros**: could scan automatically without a volunteer running a command.
*   **Cons**: one run per day needs no scheduler, and a background writer would add concurrency on a store with no locking.
*   **Reason for Rejection**: Rejected during ideation: no scheduling need, and the concurrency risk is unnecessary.

### Alternative D: Database, index, or cache

*   **Pros**: faster queries at large scale.
*   **Cons**: there is no query load; a full-file JSON scan is the entire query, and a database adds a running service and a schema.
*   **Reason for Rejection**: Rejected during ideation: the data set is small and the JSON file is the store.

### Alternative E: Persist reminder notes or a `reminded_at` field

*   **Pros**: could avoid printing the same note twice.
*   **Cons**: changes the file format the feature promises to keep, and a stale note is worse than none.
*   **Reason for Rejection**: Rejected during ideation: schema churn and stale-state risk outweigh the benefit.

### Alternative F: Business-day or holiday-calendar lateness

*   **Pros**: could match a formal lending policy.
*   **Cons**: there is no SLA, and a calendar is a data dependency with maintenance cost.
*   **Reason for Rejection**: Rejected during ideation: no business rule requires it.

### Alternative G: `--grace-days` flag

*   **Pros**: could tolerate a few days of lateness.
*   **Cons**: no business rule requires it, and it adds a decision volunteers must understand.
*   **Reason for Rejection**: Rejected during ideation: extra configuration without a rule behind it.

### Alternative H: A separate `reminders.py` or `formatters.py` module

*   **Pros**: isolates rendering from storage.
*   **Cons**: one query function in `store.py` and one render function are enough for a feature this size.
*   **Reason for Rejection**: Rejected during ideation: a new module adds indirection without a second consumer.

### Alternative I: Add an overdue footer to `lendr list`

*   **Pros**: makes the overdue set visible inside the existing command.
*   **Cons**: changes the output of an existing command, which this feature keeps unchanged.
*   **Reason for Rejection**: Not chosen: the existing command's output should stay unchanged, so discovery happens through `--help` and the README instead.

## Detailed Implementation Plan

### Target Files to Create/Modify

#### 1. `./src/lendr/store.py` (Modify)

*   **Type / Scope**: Python storage module.
*   **Proposed Changes**:
    *   Add `DataFileError(Exception)` with a user-facing message.
    *   Add `read_rows() -> list`: returns the parsed JSON when the file exists and parses; raises `DataFileError` when the file is missing or the JSON is invalid; returns `[]` for an existing empty array.
    *   Add `is_open(row) -> bool`: returns `not row.get("returned", False)`.
    *   Change `open_loans(rows=None) -> list`: when `rows` is `None`, load with the existing lenient `_load()`; otherwise use the supplied rows; filter with `is_open`.
    *   Add `is_overdue(due, today) -> bool`: returns `due < today` for `datetime.date` values.
    *   Add `overdue_loans(today=None) -> list[dict]`: defaults `today` to `datetime.date.today()`; calls `read_rows()`; filters with `open_loans(rows)`; parses each `due` with `datetime.date.fromisoformat`; skips a row with a missing or malformed `due` after printing a one-line warning to stderr; keeps rows where `is_overdue(due, today)`; returns items carrying `member`, `tool`, `due`, and `days_late`, sorted by `due` ascending.
*   **Rationale**: Keeps `open_loans()` as the single source of truth, adds a strict loader so a missing file cannot look like an all-clear, and isolates the lateness rule in a pure function for testing.

#### 2. `./src/lendr/cli.py` (Modify)

*   **Type / Scope**: Python CLI entry point.
*   **Proposed Changes**:
    *   Add an `overdue` subparser with a `--notes` flag and `help=` text.
    *   Add `format_list(loans, today, path) -> str`: renders the as-of date, the resolved data-file path, the open-loan count, one line per overdue loan (member, tool, due, days late), and the total count; returns "No overdue loans." for an empty late set.
    *   Add `format_notes(loans) -> str`: renders hand-deliverable notes from the same late set using only `member`, `tool`, and `due`, clearly delimited from the list.
    *   Add the `overdue` branch: call `store.overdue_loans()`; catch `store.DataFileError`, print one line to stderr, and return 1; otherwise print `format_list(...)` and, when `--notes` is set, append `format_notes(...)`.
    *   Keep the existing `loan`, `return`, and `list` branches unchanged.
*   **Rationale**: The CLI branch is wiring only; rendering is separate and testable; the error contract keeps diagnostics on stderr and normal output on stdout.

#### 3. `./tests/test_store.py` (Create)

*   **Type / Scope**: Unit tests, standard-library `unittest`.
*   **Proposed Changes**: Cover `is_overdue` for due yesterday, due today, and due tomorrow; `overdue_loans` with an injected `today`; a missing file raising `DataFileError`; corrupt JSON raising `DataFileError`; an existing empty array returning no overdue loans; a malformed due date skipped with a stderr warning; and sort order (most overdue first).
*   **Rationale**: The brief requires boundary-date and data-error coverage, and the pure functions make these cases deterministic.

#### 4. `./tests/test_cli.py` (Create)

*   **Type / Scope**: Unit tests, standard-library `unittest`.
*   **Proposed Changes**: Cover the default list output, the sorted order and days-late values, the total count, the explicit "No overdue loans." empty state, the `--notes` output, exit code 0 on a successful run, a non-zero exit on a missing file, and stderr diagnostics on error.
*   **Rationale**: Verifies the output contract and exit codes without spawning the CLI.

#### 5. `./tests/__init__.py` (Create)

*   **Type / Scope**: Python package marker.
*   **Proposed Changes**: Empty file so `unittest discover` imports the test modules consistently.
*   **Rationale**: Keeps the test directory importable under the project root.

#### 6. `./README.md` (Modify)

*   **Type / Scope**: Documentation.
*   **Proposed Changes**: Add `lendr overdue [--notes]` to the command list; describe the sorted output, days late, the total count, the as-of date and resolved path, the empty state, the non-zero exit on unreadable data, and the read-only behavior.
*   **Rationale**: The brief requires README documentation so volunteers discover the command.

### Staging

*   **Phase 1**: Items 1, 2 (list output only), 3, 4, 5, and 6. Ships `lendr overdue` with tests and documentation.
*   **Phase 2**: The `--notes` flag and `format_notes`, added only if volunteers act on the list and ask for notes. Phase 2 reuses the Phase 1 late set and adds no new file reads.

### Verification Plan

*   **Compilation/Build**: `python3 -m py_compile src/lendr/store.py src/lendr/cli.py`
*   **Unit Tests**: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
*   **Static Analysis & Linting**: None required; the project has no linter configuration.
*   **Test Coverage Requirement**: The boundary dates (yesterday, today, tomorrow), missing file, corrupt JSON, malformed due date, empty state, `--notes`, and both exit codes must all have explicit tests.
*   **E2E/Integration**: Run `lendr overdue` and `lendr overdue --notes` against a sample `loans.json` in a scratch directory; confirm the sorted list, the empty state, and the non-zero exit when the file is absent.
