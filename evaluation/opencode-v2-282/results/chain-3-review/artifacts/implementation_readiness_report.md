# Goldfish Review Report — Stage 9 (Implementation Readiness Test)

**Target:** `docs/designs/overdue-reminders.md` (DetailedRange lines 175-243)

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-implementation-readiness` | completed |
| `egm-codebase-details` | completed |
| `egm-style` | completed |

## Prioritized Findings (Blockers -> Major -> Nits)

### 1. `format_list` cannot render the "open-loan count" it is specified to render — Severity: Blocker

* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Lines 85-87, 196, 198 (`format_list` contract, `overdue_loans` contract, CLI branch).
* **Discrepancy Description:** `format_list(loans, today, path)` is required to render "the open-loan count", but the signature receives only the late set, and `overdue_loans()` returns only `list[dict]` (line 188). The open-loan count is not derivable from the late set, and line 87 explicitly forbids a second file read ("the file is read once per run"). The call site is also written as `format_list(...)` with no specified arguments, and `overdue_loans()` does not return `today`. The README item (line 223) and CUJ 1 (line 47) omit the open-loan count entirely, so the plan is internally inconsistent about what the output contains. As written, the specified output cannot be produced without an undocumented design change.
* **Rationale & Recommendation:** Pre-determine one of: (a) `overdue_loans` returns a result object/tuple carrying the items, the open-loan count, and the `today` used; (b) `format_list` gains an explicit `open_count` parameter and the plan states how the CLI obtains it in the same read; or (c) the "open-loan count" field is removed. Also state the exact `today` expression the CLI passes.

### 2. The user-facing output format is not pre-determined — Severity: Major

* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Lines 85-86, 196-197, 211, 223.
* **Discrepancy Description:** The plan enumerates the fields `format_list` must render (as-of date, resolved path, open-loan count, member/tool/due/days-late, total count) and the fields `format_notes` must use, but gives no labels, separators, date format, days-late formatting, header/footer text, or empty-state composition. "Returns 'No overdue loans.' for an empty late set" (line 196) is ambiguous: does the header still print, or is that the entire output? The test plan then requires tests for "the default list output", "the empty state", and "the `--notes` output" without any expected strings. The stderr warning/error wording and the subparser `help=` text are also unspecified. A competent engineer must make independent formatting decisions, which the Zero-Decision Rule forbids.
* **Rationale & Recommendation:** Add exact output templates and at least one complete expected stdout example for a known input, plus the exact empty-state output, the exact notes delimiter, and message/help templates so diagnostics are consistent and testable.

### 3. Notes scope is contradictory and its design is explicitly deferred — Severity: Major

* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`, `egm-style`
* **Affected Scope:** Lines 39, 195-197, 208-211, 223, 228-229, 236-237.
* **Discrepancy Description:** Item 2 unconditionally lists `--notes`/`format_notes` (lines 195, 197) and item 4 unconditionally lists a `--notes` test (line 211), yet Phase 1 staging says "list output only" (line 228) and Phase 2 is conditional on an unspecified external trigger (line 229). Item 6's README documents `lendr overdue [--notes]`, and the verification plan requires `--notes` coverage and E2E. Line 39 admits the per-loan vs. per-member grouping and exact wording are unspecified. The implementer must decide whether notes ship in Phase 1 and invent the format.
* **Rationale & Recommendation:** Split item 2/4/6 into explicit Phase 1 and Phase 2 change lists, and either specify the notes format now (grouping, wording, delimiter, placement) or remove notes from this plan's scope. Define the Phase 2 entry criterion if it remains conditional.

### 4. The exit-code contract has no mechanism in the current CLI — Severity: Major

* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Lines 84, 198, 237; `src/lendr/cli.py:1-26`.
* **Discrepancy Description:** The plan says the `overdue` branch catches `store.DataFileError`, prints to stderr, and "return 1", and CUJ 3 / the data flow promise a non-zero exit. `cli.py` defines `main(argv=None)` but has no `if __name__ == "__main__"` guard, no `sys.exit(main())`, and the repo contains no `setup.py`, `pyproject.toml`, or `__main__.py` that would propagate a return value. A `return 1` from `main()` therefore does not set the process exit status, so the E2E step "Run `lendr overdue` ... confirm the non-zero exit when the file is absent" cannot pass. The plan never mentions adding an entry point or exit propagation; the implementer must decide to add one.
* **Rationale & Recommendation:** Specify the exact invocation (e.g., add a `__main__` guard to `cli.py` and use `PYTHONPATH=src python3 -m lendr.cli`, or a console script) and the success return value, and align the test plan's "exit code 0" assertion with it.

### 5. Malformed-data handling is underspecified and a naive implementation crashes — Severity: Major

* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Lines 72, 79, 184-188, 196, 205.
* **Discrepancy Description:** The plan says `read_rows()` "returns the parsed JSON" and raises `DataFileError` only when the file is missing or the JSON is invalid. A file containing `null`, `{}`, `"x"`, or `123` is valid JSON, so `read_rows()` returns it; `overdue_loans()` then passes it to `open_loans(rows)`, where iteration raises `TypeError`. A `null` file is additionally ambiguous with the `rows=None` sentinel. The plan also does not say whether to read `row["due"]` or `row.get("due")`, nor which exceptions to catch: `date.fromisoformat` raises `KeyError` if the key is absent, `TypeError` for `None` or a non-string, and `ValueError` for a malformed string. A naive `except ValueError` will crash on the explicitly promised "missing" case. Rows missing `member`/`tool`, and non-dict rows, are likewise unhandled and will raise `KeyError`/`AttributeError` during rendering. The result is a raw traceback, not the promised stderr diagnostic.
* **Rationale & Recommendation:** Define the validation contract: what `read_rows` accepts (list of objects), which fields are required, the behavior when `member`/`tool` are missing, and the exact exception(s) caught for `due`. Add matching tests.

### 6. `open_loans(rows=None)` does not "keep its current behavior" for rows missing `returned` — Severity: Major

* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Lines 74, 185-186, 199; Non-Goals line 34; `src/lendr/store.py:31`.
* **Discrepancy Description:** The plan says `open_loans(rows=None)` "keeps its current behavior" and that the existing `list` command is unchanged. The current filter is `not row["returned"]` (`src/lendr/store.py:31`), which raises `KeyError` for a row with no `returned` key. The specified `is_open(row)` is `not row.get("returned", False)`, which silently treats such a row as open. That is a behavior change for malformed rows, contradicting both the "keeps its current behavior" claim and the Non-Goal of not changing `list` behavior. The plan does not document the change or an intent to handle missing `returned`; CUJ 3 covers malformed `due` but not missing `returned`.
* **Rationale & Recommendation:** Either preserve the old failure mode in `is_open` or explicitly document the intended behavior change and add a test. Add a direct test case for `is_open`/`open_loans(rows=...)`.

### 7. Message and help text are left to the implementer — Severity: Nit

* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Lines 183-184, 195, 198 (`DataFileError`, `help=` text, stderr diagnostics).
* **Discrepancy Description:** The `DataFileError` message, the one-line stderr diagnostic, the malformed-`due` warning, and the `overdue`/`--notes` `help=` strings are unspecified. The strategy (stderr, non-zero) is documented, but "actionable" implies content decisions (path, parse error, offending row).
* **Rationale & Recommendation:** Specify message templates so diagnostics are consistent and testable.

### 8. The CLI branch does not say how `today` and `path` are obtained — Severity: Nit

* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Lines 85, 196, 198.
* **Discrepancy Description:** `format_list(loans, today, path)` requires `today` and `path`, but the specified `overdue` branch only calls `store.overdue_loans()` (which computes `today` internally and does not return it) and never defines `path`. The plan says "the resolved data-file path", which implies `store.PATH.resolve()`, but `PATH` is a relative `pathlib.Path("loans.json")` (`src/lendr/store.py:5`) and the plan never says to resolve it or how to pass it. The existing `else` catch-all in `cli.py` currently serves `list`; adding `overdue` requires converting it to an explicit `list` branch or inserting an `elif`, which the plan does not mention while claiming the existing branches stay unchanged.
* **Rationale & Recommendation:** State the dispatch shape and the exact argument expressions, including whether the CLI calls `datetime.date.today()` separately (risking a midnight inconsistency) and whether to resolve the path.

### 9. The empty-state output is ambiguous — Severity: Nit

* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Lines 85, 196.
* **Discrepancy Description:** Line 85 says `format_list` renders the as-of date, resolved path, and open-loan count, and that "an empty late set renders the explicit line 'No overdue loans.'" Line 196 says `format_list` "returns 'No overdue loans.' for an empty late set", which reads as if the entire return value is that line and the header is omitted. The plan does not say whether the header is printed when there are no overdue loans, so the test plan's empty-state expectation is undefined.
* **Rationale & Recommendation:** Specify whether the header prints in the empty state.

### 10. `_load()` is described as "lenient" but only tolerates a missing file — Severity: Nit

* **Reviewer Lens:** `egm-codebase-details`, `egm-style`
* **Affected Scope:** Lines 67, 74, 186, 235.
* **Discrepancy Description:** The plan calls the existing `_load()` "lenient". It is lenient only about a missing file (`PATH.exists()` check); it raises `json.JSONDecodeError` on invalid JSON, `UnicodeDecodeError` on non-UTF-8 content, and `OSError` on permission/read errors. The plan does not qualify the term, so a reader may assume the existing commands never fail on bad data. Line 235 also makes a negative existential claim ("the project has no linter configuration") without evidence.
* **Rationale & Recommendation:** Confirm `_load()` exists and describe its actual behavior without overclaiming, and verify the absence of linter configuration or cite the check.

### 11. Sort tie-break order is unspecified — Severity: Nit

* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Line 188.
* **Discrepancy Description:** The plan says the result is "sorted by `due` ascending". For two loans with the same due date, the plan does not specify the secondary order. Python's sort is stable, so file order would be preserved, but the plan does not state this, and the test plan's "sort order" case cannot assert a unique expectation for ties.
* **Rationale & Recommendation:** State the tie-break rule (for example, stable file order, or a secondary key).

### 12. Uncalibrated claims and rationale restatement in the detailed plan — Severity: Nit

* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Lines 186, 200, 206.
* **Discrepancy Description:** (a) "the pure functions make these cases deterministic" (line 206) misattributes the mechanism; determinism in the boundary tests comes from the injected `today` parameter, not from the absence of side effects. (b) The `cli.py` rationale (line 200) largely restates the technical plan and the bullets immediately above it ("wiring only" repeats line 83; the stderr/stdout error contract repeats lines 84 and 198) and adds no new information.
* **Rationale & Recommendation:** CALIBRATE the determinism claim to "the injected `today` parameter makes the boundary cases deterministic." Trim the rationale to the one non-obvious point (rendering is separate and testable) or delete it.

### 13. "Clearly delimited" relies on a subjective qualifier — Severity: Nit

* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Line 197 (`cli.py` item, `format_notes`).
* **Discrepancy Description:** "clearly delimited from the list" is a subjective qualifier with no specified delimiter; the exact notes format is already flagged as unspecified in Open Questions (line 39). As written, it states a requirement without a testable criterion.
* **Rationale & Recommendation:** Specify the delimiter, or drop the phrase and defer the detail to Phase 2.

### 14. The Phase 2 trigger is not measurable — Severity: Nit

* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Line 229 (Staging, Phase 2).
* **Discrepancy Description:** The conditional itself is a legitimate scope gate with a reachable operator decision (KEEP), but the trigger "volunteers act on the list and ask for notes" is not a measurable or observable criterion.
* **Rationale & Recommendation:** Define a concrete gate (for example, a documented request from volunteers) so the phase boundary is actionable.

### 15. Duplicate EGM attribution in the footer — Severity: Nit

* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Lines 241 and 243 (document footer).
* **Discrepancy Description:** The hidden provenance comment ("Indicates initial structural drafting via EGM") and the visible "*Drafted with EGM*" both attribute EGM drafting; the comment's "initial structural drafting" is vague.
* **Rationale & Recommendation:** Keep one attribution. (If this footer is template boilerplate, no action is needed.)

## Accurate Claims (Codebase Verification)

The following scope claims match the code: `store.PATH` is a module-level `pathlib.Path("loans.json")`; `_load()` is the current loader used by `open_loans()`; `open_loans()` currently filters with `not row["returned"]`; the `loan`, `return`, and `list` branches exist and are as described; `README.md` exists at the repo root; `src/lendr/store.py` and `src/lendr/cli.py` exist at the stated paths. The lateness rule (`due < today`), the `days_late` definition, and the ascending-`due` sort are internally consistent with the described data model. Every current-state reference in the scope exists; the proposed files/functions are consistently marked Create/Modify, and no proposed-only item is cited as existing today. No Non-Existent References were found.

## Reviewer Note on Project Instruction Files

`AGENTS.md` and `docs/AGENTS.md` in the project root contain embedded reader-directed instructions. They are outside the design document's scope, but the implementing engineer will read them; they should be reviewed before implementation.
