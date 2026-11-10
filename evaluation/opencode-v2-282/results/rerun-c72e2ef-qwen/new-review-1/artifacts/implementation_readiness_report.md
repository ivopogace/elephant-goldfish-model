# Stage 9 — Implementation Readiness Test: `overdue_reminders.md`

- **Target:** <RUN>/project/docs/designs/overdue_reminders.md
- **Scope:** DetailedRange = lines 61-74 (Detailed Implementation Plan steps 1-4 + closing note)
- **Reviewers:** egm-implementation-readiness (R), egm-codebase-details (C), egm-style (Y)
- **Standards:** implementation-readiness-standard.md (R, C); persona judgment (Y)
- **Baseline context:** <RUN>/project/README.md; C additionally verified `src/lendr/store.py`, `src/lendr/cli.py`, `src/lendr/__init__.py`, and a full repo listing
- **Date:** 2026-11-10

Verified clean by C: `store.open_loans()` exists exactly as assumed (`store.py:30-31`); `src/lendr/` layout is real; every plan file is marked `(new)`/`(changed)`; Step 4's README edit is compatible with the README's structure. R additionally notes the plan's explicit paths are allowlist-friendly except the missing entries in I-9/I-11.

**Question answered by this stage: could a competent engineer, working only from this document, build it correctly on the first attempt?** As written: no. Three of the four steps and the closing note force invented behavior; the most literal build ships a feature that does nothing.

## Consolidated findings (deduplicated; original severities in parentheses where they diverged)

### 🔴 I-1 Blocker — Step 2 parses `--remind` but never calls `write_reminders`: the flagship flag builds as a silent no-op
- **Location:** Step 2, lines 67-68 vs Step 1, lines 63-66; contradicts Overview/Technical Plan promises at 17-19 and 40-42.
- **The build failure:** the step's only assigned actions are "call `overdue.late_loans` and print the rows." `write_reminders` has no caller anywhere in the plan. A literal implementer ships `lendr overdue --remind`: exit 0, no files, no change — while Step 4's README documents the flag as working. "The rows" also reads back onto Step 1's *unfiltered* input, so the printed set can plausibly be every open loan.
- **Fix:** rewrite Step 2 with every call site: "`rows = store.open_loans()`; `late = overdue.late_loans(rows, today)`; print each `late` row in the line-38 format whether or not `--remind` is set; only if `--remind` is set, call `overdue.write_reminders(late, folder)`." Never pass unfiltered rows to printing or reminders.
- **Sources:** R-B2, C-F1, Y-Blocker1 (this was the stated most-important issue by R and Y).

### 🔴 I-2 Blocker — The row contract is undefined, and one wrong guess passes silently
- **Location:** Step 1, lines 63-65 (depends on line 36).
- **The build failure:** nothing states that a "row" is a dict with keys `member`, `tool`, `due`, `returned`; that `due` is an **ISO string** in storage (`store.py:18`, written via `due.isoformat()` at `cli.py:21`); that `today` is a `datetime.date`; who parses the string; whether `days_late` is added by mutating the caller's rows, in a copy, or as a pair. C names the dangerous case: lexicographic `row["due"] < today` "works" for ISO strings, so a wrong-type build passes most tests and fails only the due-today boundary. Mutating caller rows also poisons any other consumer of the store's list.
- **Fix (verbatim from R, corrected by C):** "`late_loans(rows, today)` takes `rows` exactly as returned by `store.open_loans()` and `today: datetime.date`; it parses `row['due']` with `datetime.date.fromisoformat()`, keeps rows where `due < today` (due today is **not** late), and returns a new list of shallow dict copies with added integer key `days_late = (today - due).days`; input rows are never mutated." Add an entry for `store.py (unchanged)` listing its row keys, so the dependency is recorded (Y-18).
- **Sources:** R-B1, C-F2, Y-4, Y-6, Y-18.

### 🔴 I-3 Blocker — Step 3 is not executable as written: one test case contradicts the pipeline, and the repo has no test setup at all
- **Location:** Step 3, lines 69-70; Step 1's boundary promise at 65-66; line 36.
- **Two independent causes, both fatal to first-attempt builds:**
  1. *"A returned loan (ignored)"* cannot be tested through `late_loans(rows, today)`: `store.open_loans()` already excludes returned rows (verified, `store.py:31`), so the function never legitimately sees one. The only ways to satisfy the case — inventing a `returned` filter Step 1 never mentions (duplicating store logic), or testing through the CLI (contradicting "without the command line") — both build against the spec's own diagram (line 45 shows one filter).
  2. The repository has **no** `tests/` directory, no runner (`pytest.ini`/`pyproject.toml`/`conftest.py`), no packaging to make `src/`-layout imports resolve, and no way to redirect the CWD-relative `store.PATH` global (`store.py:5`). The plan presupposes all of it. This was C's stated most-important issue.
- **Fix:** drop the returned-loan case and state "returned exclusion is guaranteed by `store.open_loans()`; noted as a store-level invariant, not tested here." Add a Step 0 or expand Step 3: "Establish pytest via `pyproject.toml` with `[tool.pytest.ini_options] pythonpath = ['src']` (or editable install); tests import `from lendr import overdue` and call `late_loans`/`write_reminders` directly with hand-built rows, injecting `today`; store-touching tests monkeypatch `lendr.store.PATH` to a tmp file. Pin assertions: due `2026-01-09` with `today=2026-01-10` ⇒ one row, `days_late == 1`; due `2026-01-10` ⇒ `[]`; two late rows for `ada` ⇒ exactly one file named `reminders/ada.txt` containing both lines; plus cases for I-4 and I-6."
- **Sources:** R-M6 (case half), C-F3, C-F4, Y-Blocker3, Y-16.

### 🔴 I-4 Blocker — The closing note is an orphan requirement: no owner, no mechanism, no test, and a denylist that misses the worst case
- **Location:** lines 73-74 (unnumbered, outside the step list).
- **The build failure:** nothing says whether the `/`-check lives in `write_reminders` or `cli.py`; whether it raises (which exception — raw traceback in front of a volunteer?) or prints-and-exits (which stream, which code); whether one bad member aborts the run or is skipped while others are written; whether files already written are rolled back (an in-loop raise leaves a half-updated folder); whether it applies at all without `--remind` (the sentence reads as an unconditional rule for the command); and what "names the loan" means when the member has two late loans — the plan's own test case. `/`-only rejection still lets `../x` write outside `reminders/` (both filesystem and git exposure), plus `\`, empty, `.`, `..`, case-colliding names, and Windows-reserved basenames. Step 3 lists no test for it, so the design's one guardrail ships unverified.
- **Fix (committed from R/Y wording):** make it Step 5, scoped to `--remind`: "`write_reminders` validates all member names before writing any file: invalid if containing `/` or `\`, equal to `.`/`..`, empty/whitespace-only, or colliding after case-folding. On any invalid name: write no files, print `cannot write reminder for '<member>' (late loans: <tool> due <date>, …)` to stderr, exit 2. Add a Step 3 case asserting no file exists after rejection."
- **Sources:** R-B4, C-F5, Y-Blocker2, Y-15.

### 🔴 I-5 Blocker — Reminder file contents are specified nowhere, so the fourth test case has nothing to assert
- **Location:** Step 1 lines 64-65; line 41 ("late tools"); Step 3 line 70.
- **The build failure:** tool-only vs tool+due+days-late, one per line vs comma-separated, header or greeting line, order within the file, per-loan vs per-tool lines (a member with two late loans of the same tool), trailing newline — all open. The implementer invents a format, writes a test against their own invention, and the test proves nothing. Step 4 cannot document the artifact's shape. This repeats Stage 6 finding 6 and Stage 7 C3 — here it is a build blocker.
- **Fix:** one template line plus an example: "Each reminder file contains header `Overdue tools for <member>:`, then one line per late loan in the line-38 row format, `due`-ascending, single trailing newline, UTF-8 `\n`. Example: `tile cutter due 2026-11-07 (3 days late)`."
- **Sources:** R-B3, Y-8 (unit half), Stage-6 F6, Stage-7 C3.

### 🟡 I-6 Major — Folder path, creation, and the stale-file promise are all unresolved in the plan
- **Location:** Step 1 line 65 (`folder` param), Step 2, line 41-42 (spec promise).
- **Problem:** nobody says what the CLI passes as `folder`; CWD-relative vs "next to `loans.json`" differ the moment anyone runs from elsewhere (README's "next to the program" is itself already inaccurate against `store.py:5`'s CWD behavior — a pre-existing error Step 4 inherits silently); nothing says `write_reminders` creates the folder (first run: `FileNotFoundError` coin flip); and the Detailed Plan silently drops line 42's "always reflects the current state" — per-member overwrite never deletes files for members no longer late. Note: Stage 5/7/8 recommend *cutting* the file mechanism entirely (stdout notes); if the author follows that, this finding and its stale-file sub-issue disappear. If files stay, the plan must state: `folder.mkdir(parents=True, exist_ok=True)`; default path resolved beside the data file or explicitly CWD-relative; deletion rule ("remove `*.txt` directly in folder whose member is not in the current rows") plus a Step 3 case for the leftover file.
- **Sources:** R-M3, R-M4, C-F7, Y-7, Y-8; converges with Stage 8 IZ1.

### 🟡 I-7 Major — `--today` has no default, parse location, validation, or error text
- **Location:** Step 2 lines 67-68; line 50-51.
- **Problem:** where `YYYY-MM-DD` → `date` conversion lives is unassigned; unparseable input (`2026-13-45`, `yesterday`) tracebacks; `--remind` reads as value-taking next to a value flag; interaction with `--remind` unspecified. (Stage 5 M2 / Stage 8 IZ9 recommend deleting the flag and testing through the parameter — if kept, specify:) "parse with `date.fromisoformat`; default `date.today()`; parse failure prints `--today must be YYYY-MM-DD, got '<value>'` and exits 2."
- **Sources:** R-M1, Y-10, Stage-5 M2.

### 🟡 I-8 Major — `days_late` arithmetic, sort direction, and tie-break are not pinned
- **Location:** Step 1 lines 63-64; Overview line 16.
- **Problem:** off-by-one `days_late` passes all four listed cases unless the test spells the number; "sorted by due" reads either direction (Overview says "oldest first" — the two can be implemented against); equal-`due` loans order arbitrarily, making any order assertion nondeterministic. Also line 38's row template lives only in the Technical Plan; Step 2 alludes to it ("print the rows" — a literal `print(row_dict)` satisfies the sentence).
- **Fix:** "`days_late = (today - due).days` (due yesterday ⇒ 1); sort by `(due, member, tool)` ascending; print using the line-38 template with `%Y-%m-%d` dates and `1 day late` singular — duplicate the template inside Step 2 to remove the cross-reference."
- **Sources:** R-M2, C-F8, Y-5, Y-9.

### 🟡 I-9 Major — Module boundaries and integration points are assumed, and needed files are missing from the plan's own list
- **Location:** Steps 1-3, lines 63-70.
- **Problem:** nobody assigns the caller of `store.open_loans()`; nothing forbids `overdue.py` from importing `store`/`argparse` or calling `date.today()` itself — the "Needed so…" rationales (65-66, 68) state benefits, not constraints, so they can never fail; the `src/`-layout import form is unstated (`from . import overdue` vs path hacks), and making Step 3 runnable may require `pyproject.toml`/`conftest.py` — files the plan's explicit path list never mentions, i.e. unapproved adjacent changes. `cli.py` dispatch reality compounds it: `list` has no explicit branch (`cli.py:24-26` uses `else`), so adding `overdue` sloppily reroutes `list`.
- **Fix:** convert rationales into constraints ("`overdue.py` must not import `argparse`, `store`, or call `date.today()`; `cli.py` is the only caller of `store.open_loans()` and holds all I/O wiring"); state import forms; convert the `else` list branch to `elif args.command == "list"` before adding `elif … == "overdue"`; list any packaging/config file as `(changed)` in the plan.
- **Sources:** R-M7, R-N1, C-F6, Y-4, Y-11.

### 🟡 I-10 Major — Step 4's "document" names no section, wording, or completeness bar — and omits user-visible surface
- **Location:** line 71; README lines 6-8.
- **Problem:** the literal reading is a one-line mention; `--today`, the reminder-file format, the rejection error, the overwrite/stale rule, the folder location, and the "it never sends anything" guarantee are all operator-visible and all unlisted. Nothing ignores `reminders/` either: a run inside the repo drops per-member PII files into version-control territory.
- **Fix:** "Add bullets to the README command list matching its style, covering `lendr overdue [--remind] [--today YYYY-MM-DD]`, each flag's behavior, the note format, the error case, and the never-sends guarantee; acceptance: every flag in Step 2 appears in the README." Add `reminders/` to `.gitignore` (listed as `(changed)` in the plan) or place the folder outside the repo per I-6.
- **Sources:** R-M8, Y-12.

### 🟡 I-11 Major — No per-step verification or ordering statement; Step 1→2 dependency is hidden
- **Location:** lines 61-71 as a whole.
- **Problem:** the standard wants each phase to leave the repo buildable and testable; nothing says what to run or what passing looks like, and the fact that `write_reminders` consumes `late_loans`'s output (hence the shared row shape and the 1→2 order) is discoverable only mid-build.
- **Fix:** add "After Step 1: import check succeeds; `write_reminders` accepts exactly what `late_loans` returns." "After Step 2: the M5/I-8 output cases print correctly by hand." "After Step 3: `pytest tests/test_overdue.py` passes with the enumerated cases." State "do not reorder 1→2."
- **Sources:** R-M9.

### 🟡 I-12 Major — The plan section inherits the terminology fault: the lateness boundary is pinned only inside a test description
- **Location:** lines 63-70 vs line 36; Overview line 16.
- **Problem:** "late"/"overdue" are never declared identical in the plan; the sole place pinning the due-today boundary is a parenthetical in a test case ("(not late)"), not a requirement — an implementer may treat due-today as overdue in the command, note, or README and satisfy every sentence. The artifact carries four names (note/file/"one text file"/"one reminder file") and the unit three (rows/loans/tools).
- **Fix:** first-use insert: "In this plan 'late' and 'overdue' are one predicate: `due < today`; due today is not late." Then: "reminder file (`reminders/<member>.txt`)" and "late loan row" throughout.
- **Sources:** Y-13, Y-14, C-F2 (boundary half); converges with Stage 7 C10.

### 🟢 Nits
- **I-13** Test wording: "cover a loan due yesterday" pins no assertion and "yesterday" is relative to an unstated injected date (fix: `today=2026-01-10`, assert exact list) — Y-16. *(Merged into I-3's corrected wording.)*
- **I-14** "two late loans … in one reminder file" attaches two ways (fixture vs assertion); also fails to pin the filename, letting a `reminder-<n>.txt` scheme ship untested — Y-17, R-N2.
- **I-15** "names" reads as noun twice then verb; "the loan" singular vs multi-loan members — Y-15. *(Merged into I-4.)*
- **I-16** Sanitization beyond rejection undecided: spaces in names, Windows-reserved basenames (`con`, `aux`) raise `OSError` mid-write with no path — decide reject-and-report vs slugify — R-N3.
- **I-17** No acceptance line for Step 4; suggested "every flag named in Step 2 appears in README, grep-checkable" — R-N1. *(Folded into I-10.)*

## Cross-stage note
This stage re-derives, in build terms, the same core faults the earlier stages found in design terms: unwired `--remind` (= Stage 6 F2), undefined note content (= Stage 6 F6 / Stage 7 C3), stale-file promise (= Stage 5 B1 / Stage 7 C4), returned-loan contradiction (= Stage 6 F1), missing test infrastructure (= Stage 5 N2). The Stage 8 architecture decision — cut the file sink or document it — determines how much of I-4/I-5/I-6 survives; the remaining findings (I-1, I-2, I-3, I-7 through I-12) stand regardless of that choice.

## Most important issue in this scope
Step 2 never gives `write_reminders` a caller or a row set — `--remind` builds as a silent no-op while the README step documents it as working — and Step 3 as written cannot run on a first attempt at all (no test infrastructure exists, and one listed case contradicts the pipeline).

## Traceability
| Consolidated | egm-implementation-readiness | egm-codebase-details | egm-style |
|---|---|---|---|
| I-1 unwired flag | B2 | F1 | Blocker 1 |
| I-2 row contract | B1 | F2 | 4, 6, 18 |
| I-3 unbuildable tests | M6 | F3, F4 | Blocker 3, 16 |
| I-4 orphan constraint | B4 | F5 | Blocker 2, 15 |
| I-5 note contents | B3 | — | 8 |
| I-6 folder/stale semantics | M3, M4 | F7 | 7, 8 |
| I-7 --today | M1 | — | 10 |
| I-8 arithmetic/sort/format | M2, M5 | F8 | 5, 9 |
| I-9 boundaries/imports | M7, N1 | F6 | 4, 11 |
| I-10 README/gitignore | M8 | F7 (inherited note) | 12 |
| I-11 verification steps | M9 | — | — |
| I-12 terminology | — | F2 | 13, 14 |
| I-13..I-17 | N1, N2, N3 | — | 15, 16, 17 |
