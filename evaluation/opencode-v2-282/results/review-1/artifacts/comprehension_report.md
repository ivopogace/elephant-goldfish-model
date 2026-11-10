# Comprehension Test Report

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md`
**Stage:** 6 — Comprehension Test
**Scope:** FeatureRange lines 1-60; DetailedRange lines 61-74
**Reviewer:** `egm-comprehension` (no document standard; self-containment test)

**What this proposes**

The document proposes adding a `lendr overdue` command that prints every open loan whose due date has passed, oldest first, with the number of days late. An optional `--remind` flag writes one plain-text reminder file per late member into a `reminders/` folder for volunteers to print or paste into an email; the program itself never sends anything. A `--today YYYY-MM-DD` flag overrides the current date so tests are repeatable. The implementation adds `src/lendr/overdue.py`, modifies `src/lendr/cli.py`, adds `tests/test_overdue.py`, and updates the README.

**How the existing system works, per this document**

`lendr` is a command-line loan tracker for the Maple Hollow Tool Library; volunteers record loans and the program stores them in `loans.json`. `lendr list` prints open loans but does not indicate which are late, so a volunteer must compare each due date with today's date by eye. The document says open loans are read through `store.open_loans()` and links to the project README for the existing commands. Existing `loans.json` files must keep working without conversion.

**Findings**

1. **Severity**: Major
   **Affected Scope**: Technical Plan (lines 36, 45); Detailed Implementation Plan (lines 63-68)
   **Discrepancy Description & Rationale**: The document's central data path is `store.open_loans()`, but `store` is never defined, described, or linked. A naive reader cannot tell whether `store` is an existing module, a new module to be created, or something else; the Detailed Implementation Plan lists new and changed files but omits it, so its status is ambiguous. The only link in the document points to the README for commands, which does not mention `store`. The document should state inline that `store` is the existing storage module (or link to it).

2. **Severity**: Nit
   **Affected Scope**: Technical Plan (lines 41-42)
   **Discrepancy Description & Rationale**: The document says existing reminder files are overwritten "so the folder always reflects the current state," but overwriting only replaces files for members who currently have late loans. If a member's loans are returned, their old reminder file is not deleted, so the folder can retain stale reminders. A naive reader is left to assume a cleanup that the described mechanism does not perform; the claim should be softened or the plan should state that stale files are removed.

3. **Severity**: Nit
   **Affected Scope**: Overview (lines 17-19); Technical Plan (lines 40-42)
   **Discrepancy Description & Rationale**: The document says reminders are written into "a `reminders/` folder" but never says where that folder is created (current working directory, program directory, or elsewhere). A naive reader cannot tell where to look for the output. The README's note that `loans.json` lives "next to the program" suggests a convention, but the design doc does not state where `reminders/` lives.
