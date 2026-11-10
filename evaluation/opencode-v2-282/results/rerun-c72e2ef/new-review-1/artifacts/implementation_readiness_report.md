# Goldfish Review Report — Stage 9 (Implementation Readiness Test)

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (DetailedRange, lines 61–74)

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-implementation-readiness` | completed |
| `egm-codebase-details` | completed |
| `egm-style` | completed |

## Verdict

The plan does not pass the implementation-readiness standard. The Zero-Decision Rule fails at three points: the two new function contracts and the member-name validation path. An implementer would have to invent argument types, return shapes, file contents, folder creation, error handling, and the CLI branch for `--remind`.

Verified against code: `src/lendr/store.py` exposes `open_loans()`, `src/lendr/cli.py` has no `overdue` subcommand, and `due` is stored as an ISO string (`cli.py:20-21`, `store.py:16-19`). The plan's claims about existing code are accurate.

## Prioritized Findings (Blockers -> Major -> Nits)

### `late_loans` contract undefined - Severity: Blocker
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** item 1, lines 63–64
* **Discrepancy Description**: The signature `late_loans(rows, today)` is named, but nothing states the argument and return types. It is unclear whether `today` is a `datetime.date` or the raw `--today` string; whether `rows` are raw dicts from `store.open_loans()` (whose `due` is an ISO string) or already-parsed rows; whether `days_late` is added by mutating the caller's dicts or by returning copies; and whether the result is a dict, tuple, or named structure. A literal implementation of `today - row["due"]` raises `TypeError`.
* **Rationale & Recommendation**: Specify the full signature with types, the parse step (`datetime.date.fromisoformat`), whether input is mutated, the exact returned structure, and the `days_late` formula (`(today - due).days`). This is a public data shape, not an implementer choice.

### `write_reminders` contract undefined - Severity: Blocker
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** item 1, lines 64–66; Technical Plan lines 40–42
* **Discrepancy Description**: "Groups rows by member and writes one text file per member" leaves nearly every decision open: whether it takes raw open-loan rows or `late_loans` output; whether `folder` is a `str` or `pathlib.Path` (the codebase already uses `pathlib` in `store.py:3,5`); whether it creates the folder when absent; the exact reminder file content (header, one tool per line, due dates, `days_late`, trailing newline, encoding); what it returns for tests to assert on; and what happens when `folder` exists as a file or is not writable. Line 64 says "one text file" while the Technical Plan says `reminders/<member>.txt`, and "overwrites existing files" appears only in the Technical Plan.
* **Rationale & Recommendation**: Write the file template verbatim. Define argument types, `mkdir(parents=True, exist_ok=True)` behaviour, the return value, and the exception and message for I/O failure.

### Member-name rejection has no defined enforcement point or error path - Severity: Blocker
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`, `egm-style`
* **Affected Scope:** lines 73–74
* **Discrepancy Description**: "Names containing `/` are rejected with an error message that names the loan" defines neither the enforcement point nor the error strategy. Undecided: check in `write_reminders`, in the CLI before any output, or both; exception, `sys.exit`, or `argparse` error; what exit code; whether validation runs before any files are written (otherwise earlier members' files are written before the failure, leaving a half-updated folder); and whether the rejection applies only under `--remind` or also to plain stdout. "Names the loan" is ambiguous for a member with several late loans. Other path-unsafe names (`\`, `..`, empty string, leading dot, names that are `.` or `..`) are unaddressed; `store.add` accepts any string, so these are reachable input.
* **Rationale & Recommendation**: Specify the validation location, predicate, message template, exit code, and a pre-pass over all rows before any write. The style reviewer's CALIBRATE note is folded in here: name the exact identifying fields the message must contain.

### Returned-loan filter ownership contradicts the test plan - Severity: Blocker
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** item 1, lines 63–66; item 3, line 70
* **Discrepancy Description**: `store.open_loans()` already excludes returned rows (`store.py:30-31`), but the test plan expects "a returned loan (ignored)" to be handled by `late_loans`. If `late_loans` receives raw rows it must re-check `row["returned"]`; if it receives `open_loans()` output, that test case must call `open_loans` first. The plan leaves both the input contract and the filter responsibility undecided, so the same test can be implemented two contradictory ways.
* **Rationale & Recommendation**: State that `late_loans` filters `row["returned"] is False` and is called with raw rows, or the reverse, and state the `due < today` predicate explicitly rather than relying on the Technical Plan section.

### No phasing or checkpoints - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** whole plan, lines 61–74
* **Discrepancy Description**: The plan is a flat four-item list with no phases and no verification checkpoints, so it leaves sequencing and the point at which the suite should pass to the implementer.
* **Rationale & Recommendation**: Split into phases that each leave the codebase buildable: (a) `overdue.py` with `late_loans` plus unit tests, checkpoint `python -m pytest tests/test_overdue.py` passing; (b) CLI wiring plus CLI-level tests; (c) `write_reminders` plus tests; (d) README. Name the exact command and expected result at each checkpoint.

### `--remind` is never wired to `write_reminders` - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** item 2, lines 67–68
* **Discrepancy Description**: Item 2 says only to add the subcommand, "call `overdue.late_loans` and print the rows". Following the plan literally makes `--remind` a no-op. Nothing states when `write_reminders` is invoked, what is passed (late rows, not the full `open_loans()` result), whether stdout still prints when `--remind` is set, whether writing happens before or after printing, or where `reminders/` resolves from (working directory, or beside `loans.json` as `store.PATH` suggests).
* **Rationale & Recommendation**: Spell out the branch: `open_loans()` → `late_loans(rows, today)` → print → if `args.remind`: `write_reminders(..., pathlib.Path("reminders"))`, plus the success exit code. Anchor the print format to the existing `cli.py:24-26` style.

### `--today` parsing and failure behaviour undefined - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** item 2, line 67; context line 50
* **Discrepancy Description**: The flag override mechanism is unstated. It is unclear whether it uses `type=datetime.date.fromisoformat` (so `argparse` produces the usage error) or manual parsing with a custom message, what the user sees for `--today 2026-13-01`, and what the default is when the flag is omitted.
* **Rationale & Recommendation**: Pin the `argparse` declaration and the invalid-input path, including message and exit code.

### Stale reminder files contradict the stated guarantee - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Technical Plan lines 41–42 versus item 1 line 65
* **Discrepancy Description**: Line 42 promises "the folder always reflects the current state", but line 41 and item 1 only overwrite files for currently late members. A member who is no longer late keeps an old `<member>.txt`, contradicting the guarantee.
* **Rationale & Recommendation**: Delete stale files or restate the guarantee. Either choice changes both `write_reminders` and its tests, so state which one.

### Test plan has no assertions or expected values - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** item 3, lines 69–70
* **Discrepancy Description**: The four scenarios have no expected outputs, so the implementer must invent the exact printed line for a loan due yesterday (including the `days_late` value), the exact reminder file contents and filename, and the exclusion expectations for a due-today and a returned loan.
* **Rationale & Recommendation**: Add concrete arrange/act/assert descriptions per test: input rows, expected `late_loans` return, expected stdout string, expected file contents.

### Test plan misses behaviours the plan introduces - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** item 3, lines 69–70
* **Discrepancy Description**: No test covers sort order with three or more late loans across different due dates, the `--today` override and invalid input, the `--remind` end-to-end path (files land in `reminders/`, folder is created), overwriting an existing reminder file and the stale-file rule, the `/`-in-name rejection message and exit code, or the empty case (no late loans, exit 0, no unexpected side effects). `store.PATH` is a module-level constant (`store.py:5`) with no injection point, so any CLI-level test needs monkeypatching — the plan must state that approach or scope the tests to the pure functions.
* **Rationale & Recommendation**: Add these cases, or explicitly scope the suite to pure functions and say how CLI behaviour is verified instead.

### Test tooling is an unstated dependency choice - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** item 3, line 69
* **Discrepancy Description**: The repository has no `tests/` directory, no `pyproject.toml`, no `setup.py`, and no test runner configuration. Naming `tests/test_overdue.py` implies pytest, so the implementer chooses and adds a dependency, a discovery layout, and possibly `tests/__init__.py` or `conftest.py` — all outside the stated file boundary.
* **Rationale & Recommendation**: State the framework, how it is installed or invoked (`python -m pytest`), and whether any dependency or config file is in scope. If none is, say the tests must run on the standard library only.

### File actions are not labelled Create/Modify/Delete - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** whole plan, lines 63–71
* **Discrepancy Description**: Paths carry prose annotations "(new)" and "(changed)" rather than explicit `Create` / `Modify` / `Delete` markers, so the list is not suitable for a write allowlist. Reported once, as instructed: `src/lendr/overdue.py`, `src/lendr/cli.py`, `tests/test_overdue.py`, `README.md`.
* **Rationale & Recommendation**: Mark each of the four paths explicitly.

### "Needed to expose the feature" is tautological filler - Severity: Major
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** item 2, lines 67–68
* **Discrepancy Description**: Adding the `overdue` subcommand is itself the exposure, so the sentence records no decision, constraint, or testable requirement, and "expose the feature" is product jargon.
* **Rationale & Recommendation**: DROP. By contrast, the "Needed so the date logic can be tested without the command line" rationale at lines 65–66 records a concrete design decision and should stay.

### Sort tie-break unspecified - Severity: Nit
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** item 1, line 63
* **Discrepancy Description**: "Sorted by due date" leaves ties undecided, and ties are realistic when all loans are created on the same day with the default `--days 7`. The plan also never says to sort on the parsed date rather than the ISO string.
* **Rationale & Recommendation**: State the key and a secondary sort (member, then tool) so stdout order and the order of tools inside each reminder file are deterministic.

### README step is under-specified - Severity: Nit
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** item 4, line 71
* **Discrepancy Description**: It says to document `lendr overdue` and `--remind` but omits the `--today` flag that item 2 adds, and gives no target text.
* **Rationale & Recommendation**: Add `--today` to the documented surface and state whether the existing bullet list is extended with a new bullet, a short example invocation, or both.

### Reminder output paths absent from the file boundary - Severity: Nit
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** items 1–4 versus lines 64–65
* **Discrepancy Description**: The plan lists four source and doc paths, but the feature also creates a `reminders/` directory with `<member>.txt` files at runtime. The file-boundary requirement does not cover that output location, and `.gitignore` is not mentioned.
* **Rationale & Recommendation**: Name the output location and whether a generated `reminders/*.txt` glob is the allowlist entry, and state whether `.gitignore` must change.
