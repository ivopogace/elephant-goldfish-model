# Goldfish Review Report

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (full file, lines 1-2381)

**Stage:** 5 - Initial Zoom Out Review

**Standard:** Zoom-Out Standard (`resources/document_standards/zoom-out-standard.md`)

**Baseline (GoldfishContext):** `<RUN>/project/README.md`

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| egm-zoom-out | completed |
| egm-inventive-catalyst | completed |

## Prioritized Findings (Blockers -> Major -> Nits)

### 1. Appendix A is 2,300 rows of synthetic fixture data - Severity: Blocker

* **Reviewer Lens:** egm-zoom-out
* **Affected Scope:** "Appendix A: Sample Loans Used by the Tests", lines 76-2381
* **Discrepancy Description:** The appendix is 2,300 generated loan rows. The test plan it supports (lines 69-70) needs roughly four to five rows: a loan due yesterday, a loan due today, a returned loan, and two late loans for one member in one reminder file. No stated requirement - scale, performance, pagination, bulk export - justifies the volume. The data is also internally inconsistent: the `late` column does not match any single "today". For example, line 83 (L0002, due 2026-10-03) is marked "no" while line 86 (L0005, due 2026-10-06) is marked "yes"; line 109 (L0028, due 2026-10-01) is "no"; line 2381 (L2300, due 2026-10-05) is "yes". Line 78 claims the last row is the one the "due today" test depends on, which would make line 82 (L0001, due 2026-10-02) late.
* **Rationale & Recommendation:** This is premature detail and YAGNI, and it buries the actual 75-line design under 96.8% synthetic data. Cut the appendix to the rows the tests actually consume, or move it into the test fixture so the design document stays readable.

### 2. The reminder-folder currency invariant is not delivered by the overwrite-only mechanism - Severity: Major

* **Reviewer Lens:** egm-zoom-out and egm-inventive-catalyst (overlapping findings deduplicated)
* **Affected Scope:** Technical Plan, lines 40-42 ("Existing reminder files are overwritten so the folder always reflects the current state")
* **Discrepancy Description:** The stated invariant is false under the described behavior. Overwriting only files for members who are late in the current run leaves stale files in `reminders/` for members who were previously late but have since returned a tool. The plan's own test matrix includes "a returned loan (ignored)" (line 70), so the stale-file case is in scope, yet no deletion or cleanup step is specified. The author treats write-only-overwrite as sufficient for a currency guarantee it cannot provide.
* **Rationale & Recommendation:** Close the loop with a reconciliation step: compute the current late-member set, write their files, and delete `reminders/*.txt` files that are not in the set. Alternatively, generate into a fresh temporary directory and swap it into place so the folder is correct by construction. Either way, scope any deletion strictly to generated `.txt` files inside `reminders/`, and specify the continue-or-abort behavior. As written, the design patches the symptom (refreshing current members) rather than solving the root behavior (folder always current).

### 3. `--today` is a user-facing flag added only for test repeatability - Severity: Nit

* **Reviewer Lens:** egm-zoom-out
* **Affected Scope:** Technical Plan, lines 50-51
* **Discrepancy Description:** The `--today YYYY-MM-DD` flag exists so tests are repeatable, but the design already threads `today` into `late_loans(rows, today)` (line 63), so tests can exercise the date logic directly at the function boundary.
* **Rationale & Recommendation:** Drop the CLI flag and keep the test seam at the function boundary. A volunteer never needs to override today's date, so the flag is speculative surface area.

### 4. Helper function signatures are code-level detail in a high-level plan - Severity: Nit

* **Reviewer Lens:** egm-zoom-out
* **Affected Scope:** Detailed Implementation Plan, lines 63-66
* **Discrepancy Description:** The plan names exact helper signatures (`late_loans(rows, today)`, `write_reminders(rows, folder)`). A high-level plan should stop at component and interface level (new `overdue` module, new CLI subcommand).
* **Rationale & Recommendation:** Defer the signatures to implementation time. Borderline acceptable here because they support the stated testability rationale, but they are still weeds.

### 5. A separate `overdue.py` module is a layering choice worth making consciously - Severity: Nit

* **Reviewer Lens:** egm-zoom-out
* **Affected Scope:** Detailed Implementation Plan, lines 63-66
* **Discrepancy Description:** A separate module for two small pure functions is defensible for testability, but in a codebase this small (`store.py` is 31 lines, `cli.py` is 26) placing the filtering and writing logic beside the existing CLI logic would be simpler.
* **Rationale & Recommendation:** Not a violation. Flagging only so the split is a conscious trade-off rather than an unexamined layering habit.

### 6. Reminder filename safety is only partially mitigated - Severity: Nit

* **Reviewer Lens:** egm-inventive-catalyst
* **Affected Scope:** Detailed Implementation Plan, lines 73-74 (member names used as file names)
* **Discrepancy Description:** Rejecting only `/` is a partial mitigation of the readability-vs.-safety contradiction, not a resolution. Other path separators (for example `\` on Windows), dotted or reserved names, overlong names, and case-insensitive or duplicate-name collisions are unaddressed, and the error path is passive - an error message whose continue-or-abort behavior is unspecified.
* **Rationale & Recommendation:** Validate against a strict allowlist (for example `[A-Za-z0-9][A-Za-z0-9._-]*`, reject `.` and `..`, cap length) with explicit fail-fast behavior, or map members to deterministic safe filenames (slug plus short hash suffix) to guarantee uniqueness. Declare the trade-offs: an allowlist can reject legitimate names and needs an escape hatch; mapped filenames are less readable for a volunteer browsing the folder.

## Reuse Verification

Codebase searched in full: `src/lendr/store.py`, `src/lendr/cli.py`, `src/lendr/__init__.py`.

* `store.open_loans()` exists and is correctly reused; no date or overdue logic exists anywhere in the codebase, so the proposed `overdue.py` is not reinventing an existing utility.
* `datetime.date.today()` and `.isoformat()` match the existing convention in `cli.py`; the argparse subcommand pattern matches the existing CLI structure. Pattern consistency is good.
* No reminder or file-export utility exists, so `write_reminders` is new ground, not duplication.
* No test infrastructure exists; a single test file with four cases is proportionate and not over-specified.
* No premature optimization (no caching, queues, or async) and no architectural dead-ends detected.

## Context Sufficiency

Context sufficiency is satisfied. The objective (volunteers cannot see which loans are late) and the motivation are clear, and the design addresses the root problem with a proportionate command. The review proceeds on substance.

## Inventive Catalyst Note

The catalyst verified a genuine technical contradiction: the reminder-output design asserts a currency invariant its mechanism does not deliver. That finding is consolidated into Finding 2 above. No other false compromise was detected.
