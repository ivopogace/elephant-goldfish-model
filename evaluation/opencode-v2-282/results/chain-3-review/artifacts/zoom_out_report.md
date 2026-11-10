# Goldfish Review Report — Stage 5 (Initial Zoom Out Review)

**Target:** `docs/designs/overdue-reminders.md` (lines 1-243)

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-zoom-out` | completed |
| `egm-inventive-catalyst` | completed |

## Prioritized Findings (Blockers -> Major -> Nits)

### 1. Notes are over-specified despite an explicit Phase 2 deferral — Severity: Major

* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Goals line 21; CUJ 2 lines 49-53; Technical Plan lines 83-87 and data flow lines 106-112; Detailed Implementation Plan lines 197-198; Verification Plan lines 211, 236-237; Staging lines 226-229; Open Questions lines 38-39.
* **Discrepancy Description:** The document says Phase 1 ships the listing only and Phase 2 adds `--notes` "only if volunteers act on the list and ask for notes," yet it fully specifies `format_notes(loans)`, writes a CUJ for `--notes`, includes `format_notes` in the Phase 1 data-flow diagram, and mandates `--notes` tests and E2E in the verification plan. That is speculative work for a conditional feature, and it tells the implementer to build and test something the staging says not to build.
* **Rationale & Recommendation:** Simplest fix: remove CUJ 2, `format_notes`, and all `--notes` test/E2E requirements from this document; add them in a Phase 2 doc when there is evidence of need. If notes are actually in scope, drop the deferral language and resolve the explicitly "unspecified" wording/grouping question first.

### 2. `format_list` needs inputs the specified query interface never produces — Severity: Major

* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Technical Plan line 85 (`format_list` spec) and lines 89-113 (data flow); Lateness computation line 79 (`overdue_loans` return shape); Detailed Implementation Plan lines 196-198.
* **Discrepancy Description:** `format_list(loans, today, path)` renders "the open-loan count" and the as-of date, but `overdue_loans()` returns only the late set (`member`, `tool`, `due`, `days_late`) and the CLI branch is specified as calling `store.overdue_loans()` with no `today`. The open-loan count cannot be derived from the late set; obtaining it requires either a second `open_loans()` call (a second file read, contradicting line 87's "the file is read once per run") or a richer return value. Likewise, `today` must be computed once in the CLI and passed to both `overdue_loans(today)` and `format_list(...)`, or returned by the query, to avoid a midnight-rollover mismatch.
* **Rationale & Recommendation:** Simplest fix: have `overdue_loans` return the open count alongside the late set (one integer, no extra read) and have the CLI compute `today` once. Also specify whether `path` is passed as `store.PATH` or `store.PATH.resolve()` ("resolved" is otherwise ambiguous).

### 3. `read_rows()` duplicates the existing `_load()` parse path — Severity: Nit

* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Technical Plan lines 69-74; Detailed Implementation Plan lines 183-186; existing `src/lendr/store.py` lines 8-9.
* **Discrepancy Description:** `_load()` already reads and parses `PATH`; `read_rows()` is the same parse with strict error semantics. Two functions parsing the same file can drift (encoding, path handling, future schema checks).
* **Rationale & Recommendation:** Simplest fix: parameterize `_load(strict=False)` or have `read_rows()` delegate to one shared parse helper, preserving the strict/lenient distinction without a second reader.

### 4. `store.overdue_loans` performs stderr I/O, mixing presentation into the storage layer — Severity: Nit

* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Technical Plan line 79; Detailed Implementation Plan line 188; Verification Plan lines 205, 211.
* **Discrepancy Description:** `store.py` currently has no printing. Putting `print(..., file=sys.stderr)` in the query function makes the data layer impure and forces `test_store.py` to assert stderr output, which contradicts the stated layering ("CLI branch is wiring only; rendering is separate and testable").
* **Rationale & Recommendation:** Simplest fix: keep `store.py` pure — return the late set plus the skipped rows (or a warnings list) and let `cli.py` own all user-facing diagnostics.

### 5. Two error-contract edge cases can still traceback — Severity: Nit

* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Technical Plan lines 72, 79; Detailed Implementation Plan lines 184, 188; CUJ 3 lines 55-59.
* **Discrepancy Description:** (a) A missing `due` is `None`, and `datetime.date.fromisoformat(None)` raises `TypeError`, not `ValueError`; unless the code catches both (or guards `row.get("due")`), the exact "missing due" case CUJ 3 promises to skip will crash the run. (b) `read_rows()` validates parse success but not that the parsed value is a list; valid JSON such as `{"a": 1}` or `"x"` passes `read_rows` and then raises `AttributeError`/`TypeError` in the open filter, contradicting the "never prints a traceback" contract.
* **Rationale & Recommendation:** Simplest fix: catch `(ValueError, TypeError)` (or check for a missing/non-string `due`) and add one `isinstance(rows, list)` check in `read_rows`.

### 6. `is_open` silently changes `open_loans` semantics, contradicting the "unchanged" non-goal — Severity: Nit

* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Technical Plan lines 67, 73; Detailed Implementation Plan line 186; Non-Goals line 34; existing `src/lendr/store.py` line 31.
* **Discrepancy Description:** The existing filter is `not row["returned"]` (KeyError on a row missing the field); the proposed `is_open` is `not row.get("returned", False)` (treats a missing field as open). Because `lendr list` calls `open_loans()`, this changes existing command behavior for malformed rows, which Non-Goals line 34 says is out of scope.
* **Rationale & Recommendation:** Simplest fix: preserve the existing predicate exactly, or explicitly list this behavior change as in-scope.

### 7. Altitude: the Detailed Implementation Plan repeats function-level detail already in the Technical Plan — Severity: Nit

* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Lines 175-237, especially 179-200 versus 65-113.
* **Discrepancy Description:** The same signatures and behaviors are specified twice (`overdue_loans` at lines 79 and 188; `format_list` at lines 85 and 196), and test cases are enumerated. For a feature that adds roughly 40 lines to a 31-line module, this is implementation-level detail; the standard asks high-level sections to stay at interfaces and data flow.
* **Rationale & Recommendation:** Simplest fix: keep the Technical Plan's interfaces/data flow and compress the implementation section to file-level changes plus test-case names.

### 8. "The brief" is referenced but not included or linked — Severity: Nit

* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Lines 38-39, 63, 206, 224.
* **Discrepancy Description:** The design cites "the brief" for the command name, test requirements, and README requirement, but the brief is not part of the document and no context was supplied. This is not a context-sufficiency failure (the design stands alone), but linking `concepts_brief.md` (present at the project root) would make the requirements traceable.

## Inventive Catalyst Result

**No false compromise detected.**

The foundational architecture is balanced, and the apparent tensions are explicitly examined rather than accepted as inevitable laws.

- **Scan cost vs. simplicity:** The O(total loans ever) scan (line 117) is not presented as an unavoidable bottleneck. Alternative D (database/index/cache, lines 139-143) is considered and rejected on a scale rationale, and the Non-Goals explicitly exclude those mechanisms.
- **Strict vs. lenient loading:** The dual-loader split (lines 67-74) is a deliberate Extraction, not a false compromise.
- **Partial data on malformed due dates:** The warn-skip-exit-0 policy (lines 79, 84) is an explicit, justified error contract, not passive logging.
- **Read-only, offline, no-send, no-schema-change constraints** are treated as system boundaries, not as trade-offs being surrendered.

## Reuse Check (Codebase Search)

The codebase is minimal: `src/lendr/store.py` (31 lines), `src/lendr/cli.py` (26 lines), `src/lendr/__init__.py` (empty), and `README.md`. There is no `tests/` directory and no existing overdue, reminder, date-parsing, or formatting utilities. The proposed `is_overdue`, `overdue_loans`, `format_list`, `format_notes`, and `DataFileError` are genuinely new; no equivalent component exists to reuse. `store.open_loans()`, `store.PATH`, and the standard-library modules are correctly reused. The only reuse gap is finding 3 (`read_rows` vs. `_load`).

## Strengths Worth Keeping

Explicit Non-Goals; rejection of cron/DB/cache/grace-period/holiday-calendar/extra-module alternatives with reasons; stated O(total loans ever) growth model with no premature optimization; a pure, injectable-today lateness function; a single read per run; strict-vs-lenient loader split that prevents the false all-clear; and a clean storage/CLI layering (modulo finding 4).
