# Goldfish Review Report

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (`DetailedRange lines 61-74`)

**Stage:** 9 — Implementation Readiness Test

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-implementation-readiness` | completed |
| `egm-codebase-details` | completed |
| `egm-style` | completed |

## Codebase Accuracy Check

`egm-codebase-details` verified every existing symbol the document cites: `store.open_loans()` exists (`src/lendr/store.py:30-31`), `due` is persisted as an ISO string via `due.isoformat()` (`src/lendr/cli.py:21`), `datetime.date.today()` is the existing date source (`src/lendr/cli.py:20`), `loans.json` is the CWD-relative store (`src/lendr/store.py:5`), the argparse subparser layout is as described (`src/lendr/cli.py:9-18`), and the `../../README.md` link resolves. No Non-Existent References and no "Contradicts the Code" findings were found in the range. The DetailedRange is accurate against the current codebase but not exhaustive.

## Prioritized Findings (Blockers -> Major -> Nits)

### Reminder note content is never specified - Severity: Blocker
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Detailed Implementation Plan item 1 (`write_reminders`, lines 63-66); Technical Plan lines 40-42; Overview lines 17-19
* **Discrepancy Description**: The content of the reminder notes is never specified. `write_reminders(rows, folder)` is described only as "groups rows by member and writes one text file per member," and the Technical Plan says the file lists "that member's late tools." There is no template: no addressee/greeting, no header, no per-tool line format, no ordering rule, no closing, no encoding/trailing-newline statement, and no statement of which fields appear (tool, due date, days late). The reminder note is the primary deliverable of `--remind` — a volunteer prints or pastes it — so the implementer must invent the user-facing format. It is also unstated whether `write_reminders` receives the output of `late_loans` (required to have `days_late`) or raw rows.
* **Rationale & Recommendation**: This is precisely the independent design choice the Zero-Decision Rule forbids. Specify the exact file content (e.g., `Dear <member>, the following tools are overdue:\n- <tool> due <date> (<n> days late)\n...`) and add a test asserting the exact lines.

### `--remind` is never wired to `write_reminders` - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Detailed Implementation Plan item 2, lines 67-68 (with 64-65)
* **Discrepancy Description**: Step 2 says only "add the `overdue` subcommand with `--remind` and `--today`, call `overdue.late_loans` and print the rows." It never states that `--remind` invokes `overdue.write_reminders`, never gives the arguments to `late_loans` (row source and `today` value), and never supplies the `folder` argument. `write_reminders` is defined in step 1 but no step calls it, so the entire `--remind` code path — the feature's reason for existing — is left for the implementer to invent.
* **Rationale & Recommendation**: State it explicitly, e.g., "when `--remind` is set, call `overdue.write_reminders(late_rows, 'reminders')` after printing."

### `late_loans(rows, today)` has an unstated date-type and return contract - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Detailed Implementation Plan item 1, lines 63-64 (with line 50)
* **Discrepancy Description**: `store.add()` persists `due` as an ISO string via `due.isoformat()` (`src/lendr/cli.py:21`) and `store.open_loans()` returns those raw dicts, but the plan says `today` comes from `datetime.date.today()` — a `datetime.date`. `late_loans` must therefore convert one side (`datetime.date.fromisoformat(row["due"])` or `today.isoformat()`); the plan never says which, and a direct `str` vs `date` comparison raises `TypeError`. The plan also does not state whether `late_loans` returns new dicts or mutates its input rows, or how `days_late` is attached, nor the lateness comparison (`due < today`), nor tie-breaking for equal due dates.
* **Rationale & Recommendation**: Pin down the exact contract: input row schema, comparison, date parsing, `today` type, and output shape (e.g., "return a new list of dicts, each a copy of the input row with an added integer `days_late` key, sorted ascending by `due`").

### Filename validation rule is unassigned and incomplete - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Detailed Implementation Plan lines 73-74
* **Discrepancy Description**: The rule "Names containing `/` are rejected with an error message that names the loan" appears after the numbered steps with no home. The implementer must decide whether the check lives in `late_loans`, `write_reminders`, or the CLI; whether it raises or prints; and the exact message text. "names the loan" is ambiguous (tool? member? due date?). The validation is also incomplete — only `/` is rejected, while other unsafe names (`..`, empty string, leading `.`, backslash, reserved names) are unaddressed. The failure/continuation behavior (abort vs. continue with remaining members) and exit code are undefined.
* **Rationale & Recommendation**: Enumerate the validation rule, the exact message format, the owning function, and the failure/continuation behavior.

### Stale reminder files contradict the "always reflects the current state" invariant - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Detailed Implementation Plan item 1, lines 63-66 (contradicts Technical Plan lines 41-42)
* **Discrepancy Description**: Lines 41-42 claim "Existing reminder files are overwritten so the folder always reflects the current state." Overwriting only rewrites files for currently-overdue members; a member whose loan was returned keeps a stale `reminders/<member>.txt`. `write_reminders` as specified never deletes stale files, so the stated invariant is false. The implementer must decide whether to delete stale files (and how to distinguish them) or whether the claim only means "overwrite, don't append." The plan also never says to create `reminders/` if it does not exist; the first run would raise `FileNotFoundError`.
* **Rationale & Recommendation**: State the cleanup behavior explicitly (clear the folder first, or delete files for members absent from the current late set) and specify folder creation (`mkdir(parents=True, exist_ok=True)`).

### Test plan is incomplete and ambiguous - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Detailed Implementation Plan item 3, lines 69-70 (with lines 36, 50-51, 63, 73-74)
* **Discrepancy Description**: The test plan omits cases for behaviors the plan itself introduces: the `--today` override (lines 50-51, added "so tests are repeatable" but never exercised) and the `/` rejection (lines 73-74, added after the test plan). It also omits sorting order ("oldest first"), the empty/no-late-loans case, and any assertion on reminder-file content. The "returned loan (ignored)" case is ambiguous: `store.open_loans()` already filters returned rows (`src/lendr/store.py:31`), so a unit test at the `late_loans` level that passes a returned row would not ignore it. Finally, no test framework is named and the repo has no existing tests or config, so the implementer must choose pytest vs unittest — a dependency/design choice the standard says must be pre-decided.
* **Rationale & Recommendation**: Add the missing cases, state the test level (unit vs CLI) and how a returned row is represented, and name the framework and runner.

### `--today` parsing and invalid-input handling unspecified - Severity: Nit
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Detailed Implementation Plan item 2, line 67 (with lines 50-51)
* **Discrepancy Description**: `--today YYYY-MM-DD` is specified as a flag but not how the string is converted (`datetime.date.fromisoformat`) or how malformed input is handled (argparse `type=` error vs. a custom message).
* **Rationale & Recommendation**: Specify the conversion and the error behavior.

### Existing library reuse is unstated - Severity: Nit
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Detailed Implementation Plan lines 63-68
* **Discrepancy Description**: The codebase already imports `pathlib` (`src/lendr/store.py:3`) and `datetime` (`src/lendr/cli.py:3`). `write_reminders` should reuse `pathlib.Path` for `folder / f"{member}.txt"` and `write_text`, and `late_loans` should reuse `datetime.date.fromisoformat`. The plan should state that no new third-party dependency is needed; silence invites an implementer to add one (e.g., `python-dateutil`) or hand-roll parsing. Relatedly, `store.PATH` is CWD-relative (`pathlib.Path("loans.json")`), so `reminders/` is CWD-relative too — consistent with the Overview but never stated.
* **Rationale & Recommendation**: State the reuse and the CWD-relative folder convention explicitly.

### README documentation content is unspecified - Severity: Nit
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Detailed Implementation Plan item 4, line 71
* **Discrepancy Description**: "document `lendr overdue` and the `--remind` flag" does not say what to document — usage syntax, output format, the `reminders/` folder location, or `--today`. The implementer must choose the README content.
* **Rationale & Recommendation**: Specify the exact additions (e.g., a bullet mirroring the existing command list plus a short example).

### No phase boundaries or verification checkpoints - Severity: Nit
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Detailed Implementation Plan lines 61-74 (phasing)
* **Discrepancy Description**: The four items are sequential but there are no phase boundaries or verification checkpoints (e.g., "run the test suite after step 3"), and tests are written after the CLI, so steps 1-2 are unverified until step 3. The standard requires each phase to leave the codebase stable, buildable, and testable.
* **Rationale & Recommendation**: Mark the phase boundaries and add an explicit verification step.

### Defensive "Needed to..." rationale clauses - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Detailed Implementation Plan items 1 and 2, lines 65-66 and 68
* **Style Rationale**: The trailing clause "Needed so the date logic can be tested without the command line" restates the design rather than specifying behavior, and the testability rationale is already implied by the `overdue.py`/`cli.py` separation and the test plan. "Needed to expose the feature" is tautological — adding the subcommand to the CLI is by definition how the feature is exposed. Both items close with a "Needed to..." rationale; the repeated justification pattern is noise.
* **Style Rationale**: Trim or drop both clauses.

### Member-name caveat floats outside the step it constrains - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Detailed Implementation Plan, closing paragraph, lines 73-74
* **Style Rationale**: "Member names are used as file names. Names containing `/` are rejected with an error message that names the loan." is an operational caveat about file naming and error handling, but it floats after the numbered plan instead of living with the step it constrains (`write_reminders`, item 1). It reads as a defensive edge-case disclaimer appended to cover a failure mode (invalid member names) without naming a concrete operator decision.
* **Style Rationale**: RELOCATE into item 1, alongside the `write_reminders` specification.
