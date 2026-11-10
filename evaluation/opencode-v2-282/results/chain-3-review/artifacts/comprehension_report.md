# Comprehension Report — Stage 6

**Target:** `docs/designs/overdue-reminders.md` (FeatureRange lines 1-174, DetailedRange lines 175-243)

## What this proposes

This document proposes adding a `lendr overdue` command to the existing `lendr` loan tracker. The command lists every open loan whose due date is before today, sorted most overdue first, with days late and a total count, and can optionally print hand-deliverable reminder notes via `--notes`. It is designed to be read-only, offline, and standard-library-only, with explicit empty and error states; the staging plan defers the notes feature to a conditional Phase 2.

## How the existing system works, per this document

`lendr` is a small offline Python CLI used by the fictional Maple Hollow Tool Library to record which member borrowed which tool and when it is due back. Loans live in `loans.json`, and the existing `loan`, `return`, and `list` commands manage and display them; volunteers currently find late loans by eyeballing `lendr list`. The data model has no contact information. Per the design, `store.py` already provides `open_loans()` backed by a lenient loader, and `cli.py` holds the existing subcommands.

## Findings

1. **Severity**: Major
   **Affected Scope**: Goals (line 21), Open Questions (line 39), CUJ 2 (lines 49-53), Command wiring and rendering (line 86), Detailed Implementation item 2 (lines 197-198), item 4 (line 211), Staging (lines 228-229).
   **Discrepancy Description & Rationale**: The Overview, Goals, CUJ 2, Technical Plan, and Implementation items 2 and 4 all present `--notes`/`format_notes` as part of this design — item 4 even requires a test for "`--notes` output". But Open Questions (line 39) and Staging (line 229) defer the `--notes` flag and `format_notes` to a conditional Phase 2, and Phase 1 (line 228) includes item 4 without carving out its `--notes` test. A naive reader cannot tell whether notes are in scope now or a possible future addition, and the Phase 1 test plan cannot be satisfied as written. The document should state clearly that Phase 1 excludes notes and adjust item 4 and the Phase 1 test plan accordingly.

2. **Severity**: Major
   **Affected Scope**: Open Questions (line 38), item 3 Rationale (line 206), item 6 Rationale (line 224).
   **Discrepancy Description & Rationale**: The document cites "the brief" three times as the source of the command name, the boundary-date/data-error test requirement, and the README requirement, but never identifies it, links it, or says where it lives. A naive reader cannot verify the requirements or separate brief requirements from the author's own choices. The brief should be named and linked (for example, the Concepts Brief/PRD).

3. **Severity**: Major
   **Affected Scope**: Data path (line 72), CUJ 1 (line 47), Command wiring and rendering (line 85), item 1 (line 188), item 2 (line 196), item 6 (line 223), E2E/Integration (line 237).
   **Discrepancy Description & Rationale**: `PATH` is referenced as the thing `read_rows()` reads, but the document never defines it: its value, whether it is a constant or configurable, how it is resolved, or how a user points the command at a different directory. The output contract requires printing "the resolved data-file path", but "resolved" is never explained. The E2E step ("against a sample `loans.json` in a scratch directory") depends on this mechanism and cannot be followed without it. The data-file location is load-bearing for both the output contract and the verification steps.

4. **Severity**: Major
   **Affected Scope**: CUJ 1 (line 47), Command wiring and rendering (line 85), item 2 (line 196).
   **Discrepancy Description & Rationale**: The output contract names both "the open-loan count" and "the total count" without defining either; CUJ 1 mentions only "a total count". The renderer signature `format_list(loans, today, path)` receives only the late set, so it has no data source for a total open-loan count; if both counts are meant to be `len(loans)`, the output is redundant and the naming is misleading. A naive reader cannot tell what numbers are printed or where they come from, which invites implementation drift.

5. **Severity**: Nit
   **Affected Scope**: Overview (line 11), The Problem (line 15), Data path (line 74), Lateness computation (line 79), item 1 (line 185).
   **Discrepancy Description & Rationale**: The document relies on row fields `member`, `tool`, `due`, and `returned`, but never documents the schema of `loans.json` or the type and semantics of `returned` (boolean flag versus return date). `is_open` is defined as `not row.get("returned", False)`, which behaves differently depending on that type. A new reader cannot visualize the data or verify the open-loan filter without reading `store.py`.

6. **Severity**: Nit
   **Affected Scope**: Data path (lines 67, 186).
   **Discrepancy Description & Rationale**: The design contrasts the new strict loader with "the current lenient loader" and names `_load()`, but never says what the lenient loader does — for example, whether a missing file yields `[]`, warns, or raises. The rationale ("so a missing file cannot look like an all-clear") implies behavior, but a naive reader must infer it. This is a vague description of existing behavior on which the error-handling story depends.

7. **Severity**: Nit
   **Affected Scope**: Open Questions (line 38).
   **Discrepancy Description & Rationale**: The document tells the reader to "confirm it at the section gate or request a change", but "section gate" is never defined or linked. A naive reader does not know what this gate is, when it occurs, or who runs it. This is team/process jargon used as an instruction.

8. **Severity**: Nit
   **Affected Scope**: Growth and cost (line 117).
   **Discrepancy Description & Rationale**: The document refers to "the ten-second budget" as if it were an established requirement, but it is not defined anywhere in the document or linked. A naive reader cannot tell whether this is a hard requirement, who imposed it, or how it was derived.

9. **Severity**: Nit
   **Affected Scope**: Growth and cost (line 117).
   **Discrepancy Description & Rationale**: The document says "token cost is zero by design" in a standard-library-only offline CLI that explicitly has no LLM. "Token cost" is not defined and has no apparent meaning in this context; a naive reader may wonder whether an LLM or API is involved. The term is undefined and appears to contradict the stated no-LLM design.

10. **Severity**: Nit
    **Affected Scope**: Provenance footer (lines 241, 243).
    **Discrepancy Description & Rationale**: The footer says "Drafted with EGM" and "initial structural drafting via EGM", but EGM is never defined or linked. A naive reader does not know what EGM is.

11. **Severity**: Nit
    **Affected Scope**: Verification Plan, E2E/Integration (line 237).
    **Discrepancy Description & Rationale**: The E2E step says "Run `lendr overdue` ... against a sample `loans.json` in a scratch directory", but the document never states how the `lendr` command is invoked (console script, `python -m`, etc.) or how the data path is pointed at the scratch directory. A naive reader following the verification plan cannot complete it without external knowledge.

12. **Severity**: Nit
    **Affected Scope**: CUJ 3 (line 59), Data path (line 71), item 1 (line 183), item 2 (line 198).
    **Discrepancy Description & Rationale**: The document requires "a loud, actionable stderr diagnostic" and a "user-facing message" but never specifies what the message says or what action it directs the user to take. "Actionable" is therefore unverifiable, and a test cannot assert the diagnostic without a defined message.
