# Goldfish Review Report — Stage 8 (Intermediate Zoom Out Review)

**Target:** `docs/designs/overdue-reminders.md` (lines 1-243)
**Baseline:** `zoom_out_report.md` (Stage 5 initial zoom out)
**Standard:** `resources/document_standards/zoom-out-standard.md`

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-zoom-out` | completed |

## Baseline Check: Additions and Mitigations Since Stage 5

The target document is unchanged from the version reviewed in the Stage 5 report. Every line reference in that report still resolves to the same content (CUJ 2 at 49-53; `format_notes` at 86 and 197; the staging deferral at 229; `is_open` at 185; the duplicated `overdue_loans` signature at 79 and 188; `format_list` at 85 and 196; `read_rows` at 72 and 184). No additions or mitigations were made. All eight prior findings remain open. One new nit was found (finding 9).

## Standard Re-Check

* **Context sufficiency:** Pass. Overview, Problem, Goals, Non-Goals, CUJs, and Technical Plan stand alone. Minor: "the brief" is still not linked (prior finding 8).
* **Root problem focus:** Pass. The design directly addresses missed late loans with a filtered, sorted, read-only check. Non-Goals explicitly exclude scope creep. Minor: the `open_loans` semantics change touches an existing command (prior finding 6).
* **Simplicity & YAGNI:** One Major issue remains — notes are fully specified despite an explicit Phase 2 deferral (prior finding 1). No premature optimization; DB/cache/cron/grace-period alternatives are correctly rejected with reasons.
* **Anti-weeds (altitude control):** The Detailed Implementation Plan still duplicates function-level detail already in the Technical Plan (prior finding 7). The Technical Plan itself stays at interfaces and data flow.
* **Leverage existing:** Pass, with one nit — `read_rows()` duplicates the existing `_load()` parse path (prior finding 3). No new module, dataclass, or config; stdlib and `store.open_loans()` are reused.

## Prior Findings (Still Open)

### 1. Notes are over-specified despite an explicit Phase 2 deferral — Severity: Major
* **Affected Scope:** Goals line 21; CUJ 2 lines 49-53; Technical Plan lines 83-87 and data flow 106-112; Detailed Implementation Plan lines 197-198; Verification Plan lines 211, 236-237; Staging lines 226-229; Open Questions lines 38-39.
* **Simplicity Rationale:** Unchanged. The document still says Phase 1 ships the listing only and Phase 2 adds `--notes` "only if volunteers act on the list and ask for notes," yet it fully specifies `format_notes(loans)`, writes a CUJ for `--notes`, includes `format_notes` in the Phase 1 data-flow diagram, and mandates `--notes` tests and E2E. That is speculative work for a conditional feature, and it tells the implementer to build and test something the staging says not to build. Simplest fix remains: remove CUJ 2, `format_notes`, and all `--notes` test/E2E requirements; add them in a Phase 2 doc when there is evidence of need.

### 2. `format_list` needs inputs the specified query interface never produces — Severity: Major
* **Affected Scope:** Technical Plan line 85 and lines 89-113; Lateness computation line 79; Detailed Implementation Plan lines 196-198; CUJ 1 line 47.
* **Simplicity Rationale:** Unchanged. `format_list(loans, today, path)` renders the open-loan count and the as-of date, but `overdue_loans()` returns only the late set (`member`, `tool`, `due`, `days_late`) and the CLI branch is specified as calling `store.overdue_loans()` with no `today`. The open-loan count cannot be derived from the late set; obtaining it requires either a second `open_loans()` call (a second file read, contradicting line 87's "the file is read once per run") or a richer return value. Likewise, `today` must be computed once in the CLI and passed to both functions, or returned by the query, to avoid a midnight-rollover mismatch. Additional evidence: CUJ 1 (line 47) still omits the open-loan count that `format_list` and the brief require. Simplest fix remains: have `overdue_loans` return the open count alongside the late set (one integer, no extra read) and have the CLI compute `today` once; also specify whether `path` is `store.PATH` or `store.PATH.resolve()`.

### 3. `read_rows()` duplicates the existing `_load()` parse path — Severity: Nit
* **Affected Scope:** Technical Plan lines 69-74; Detailed Implementation Plan lines 183-186; existing `src/lendr/store.py` lines 8-9.
* **Simplicity Rationale:** Unchanged. `_load()` already reads and parses `PATH`; `read_rows()` is the same parse with strict error semantics. Two functions parsing the same file can drift (encoding, path handling, future schema checks). Simplest fix remains: parameterize `_load(strict=False)` or have `read_rows()` delegate to one shared parse helper.

### 4. `store.overdue_loans` performs stderr I/O, mixing presentation into the storage layer — Severity: Nit
* **Affected Scope:** Technical Plan line 79; Detailed Implementation Plan line 188; Verification Plan lines 205, 211.
* **Simplicity Rationale:** Unchanged. `store.py` currently has no printing. Putting `print(..., file=sys.stderr)` in the query function makes the data layer impure and forces `test_store.py` to assert stderr output, contradicting the stated layering ("CLI branch is wiring only; rendering is separate and testable"). Simplest fix remains: keep `store.py` pure — return the late set plus the skipped rows (or a warnings list) and let `cli.py` own all user-facing diagnostics.

### 5. Two error-contract edge cases can still traceback — Severity: Nit
* **Affected Scope:** Technical Plan lines 72, 79; Detailed Implementation Plan lines 184, 188; CUJ 3 lines 55-59.
* **Simplicity Rationale:** Unchanged. (a) A missing `due` is `None`, and `datetime.date.fromisoformat(None)` raises `TypeError`, not `ValueError`; unless the code catches both (or guards `row.get("due")`), the exact "missing due" case CUJ 3 promises to skip will crash the run. (b) `read_rows()` validates parse success but not that the parsed value is a list; valid JSON such as `{"a": 1}` or `"x"` passes `read_rows` and then raises `AttributeError`/`TypeError` in the open filter, contradicting the "never prints a traceback" contract. The same shape gap extends to a list containing non-dict elements (e.g., `["foo"]`), which would crash `is_open`'s `row.get`. Simplest fix remains: catch `(ValueError, TypeError)` (or check for a missing/non-string `due`) and add one `isinstance(rows, list)` check in `read_rows`.

### 6. `is_open` silently changes `open_loans` semantics, contradicting the "unchanged" non-goal — Severity: Nit
* **Affected Scope:** Technical Plan lines 67, 73; Detailed Implementation Plan line 186; Non-Goals line 34; existing `src/lendr/store.py` line 31.
* **Simplicity Rationale:** Unchanged. The existing filter is `not row["returned"]` (KeyError on a row missing the field); the proposed `is_open` is `not row.get("returned", False)` (treats a missing field as open). Because `lendr list` calls `open_loans()`, this changes existing command behavior for malformed rows, which Non-Goals line 34 says is out of scope. Simplest fix remains: preserve the existing predicate exactly, or explicitly list this behavior change as in-scope.

### 7. Altitude: the Detailed Implementation Plan repeats function-level detail already in the Technical Plan — Severity: Nit
* **Affected Scope:** Lines 175-237, especially 179-200 versus 65-113.
* **Simplicity Rationale:** Unchanged. The same signatures and behaviors are specified twice (`overdue_loans` at lines 79 and 188; `format_list` at lines 85 and 196), and test cases are enumerated. For a feature that adds roughly 40 lines to a 31-line module, this is implementation-level detail; the standard asks high-level sections to stay at interfaces and data flow. Simplest fix remains: keep the Technical Plan's interfaces/data flow and compress the implementation section to file-level changes plus test-case names.

### 8. "The brief" is referenced but not included or linked — Severity: Nit
* **Affected Scope:** Lines 38-39, 63, 206, 224.
* **Simplicity Rationale:** Unchanged. The design cites "the brief" for the command name, test requirements, and README requirement, but the brief is not part of the document and no context was supplied. This is not a context-sufficiency failure (the design stands alone), but linking `concepts_brief.md` (present at the project root) would make the requirements traceable.

## New Finding

### 9. `read_rows()` does not handle I/O errors, despite the "unreadable data" claim — Severity: Nit
* **Affected Scope:** Goals line 22; Technical Plan lines 69-72; Detailed Implementation Plan lines 183-184; CUJ 3 lines 55-59.
* **Simplicity Rationale:** Goals promise "error handling for missing or unreadable data" and CUJ 3 promises a loud diagnostic instead of a traceback, but `read_rows()` is specified to raise `DataFileError` only for a missing file or invalid JSON. A file that exists but cannot be read (permission denied, I/O error) raises an uncaught `OSError`/`PermissionError` and produces a traceback, violating the error contract. Simplest fix: catch `OSError` in `read_rows()` and re-raise as `DataFileError`; this keeps the error contract in the loader rather than scattering guards through the CLI.

## Reuse Check (Codebase Search)

The codebase is still minimal: `src/lendr/store.py` (31 lines), `src/lendr/cli.py` (26 lines), `src/lendr/__init__.py` (empty), `README.md`, and `concepts_brief.md`. There is no `tests/` directory and no existing overdue, reminder, date-parsing, or formatting utilities. The proposed `is_overdue`, `overdue_loans`, `format_list`, `format_notes`, and `DataFileError` remain genuinely new; no equivalent component exists to reuse. `store.open_loans()`, `store.PATH`, and the standard-library modules are correctly reused. The only reuse gap is still prior finding 3 (`read_rows` vs. `_load`).

## Strengths Worth Keeping

Explicit Non-Goals; rejection of cron/DB/cache/grace-period/holiday-calendar/extra-module alternatives with reasons; stated O(total loans ever) growth model with no premature optimization; a pure, injectable-today lateness function; a single read per run; strict-vs-lenient loader split that prevents the false all-clear; and a clean storage/CLI layering (modulo finding 4).
