# Comprehension Report — Stage 6

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (FeatureRange 1–60; DetailedRange 61–74)
**Reviewer:** `egm-comprehension`

## What this proposes

Add a new `lendr overdue` subcommand to lendr, the command-line tool used by volunteers at the Maple Hollow Tool Library. It prints every open loan whose due date has passed, oldest first, showing the member, tool, due date, and number of days late. An optional `--remind` flag writes one plain-text reminder file per late member into a `reminders/` folder, overwriting existing files, while the program itself sends nothing. A `--today YYYY-MM-DD` override supplies a fixed date so tests are repeatable. The detailed plan adds `src/lendr/overdue.py` with `late_loans` and `write_reminders`, wires the subcommand into `src/lendr/cli.py`, adds `tests/test_overdue.py`, and updates the README.

## How the existing system works, per this document

lendr is the tool library's command-line program, and `lendr list` prints open loans from `loans.json` without indicating which are late, so a volunteer must compare each due date with today's date by eye. Open loans are retrieved through `store.open_loans()`, and today's date comes from `datetime.date.today()`. The document does not otherwise describe the `store` module, the shape of a loan record, or where loan data is found. Existing `loans.json` files are expected to remain usable without conversion.

## Findings

### Undefined loan record schema and undefined `store.open_loans()` - Severity: Major
* **Affected Scope:** `store.open_loans()` and loan rows; Technical Plan lines 36–38 and 45; Detailed Implementation Plan lines 63–65
* **Discrepancy Description & Rationale**: `store.open_loans()` is a project-specific API named without any definition, module path, or link. The document never states which fields a loan row contains, even though the printed format and `late_loans(rows, today)` depend on `member`, `tool`, and `due` fields, and the plan adds a `days_late` field. The schema of `loans.json` is likewise never described, and the plural "Existing `loans.json` files" hints at more than one file without explanation. A fresh reader cannot tell what data reaches the filter or whether the proposed helpers operate on the right records without reading the existing codebase.

### `reminders/` location and lifecycle unspecified - Severity: Major
* **Affected Scope:** `reminders/` folder; Overview lines 17–19; Technical Plan lines 40–42 and 47
* **Discrepancy Description & Rationale**: The document does not say where `reminders/` is created, whether it is relative to the current working directory or the project root, or whether the command creates the folder when it does not already exist. It also claims that overwriting existing reminder files means "the folder always reflects the current state," which is misleading: a member who no longer has a late loan would keep their old reminder file because nothing is overwritten or removed for them. A volunteer cannot predict where the notes appear or trust that the folder contains only current reminders.

### `write_reminders` is never wired into the CLI - Severity: Major
* **Affected Scope:** Detailed Implementation Plan steps 1–2, lines 63–68; `write_reminders`
* **Discrepancy Description & Rationale**: The plan defines `write_reminders(rows, folder)` but never connects it to the CLI: step 2 says only that the `overdue` subcommand calls `overdue.late_loans` and prints the rows. Nothing states that the CLI calls `write_reminders`, which folder value it passes, or that this happens when `--remind` is set. An implementer following the numbered steps literally would produce no reminder files, so the `--remind` feature described in the Overview is not actually accounted for.

### Returned-loan filtering ownership unstated - Severity: Nit
* **Affected Scope:** `late_loans`, returned-loan handling; Detailed Implementation Plan lines 63–70
* **Discrepancy Description & Rationale**: The plan says `late_loans(rows, today)` receives rows and that a "returned loan (ignored)" is a test case, but it does not say whether `store.open_loans()` already excludes returned loans or whether `late_loans` must filter them. If `open_loans()` already excludes them, the test case exercises a state that cannot reach `late_loans` through the proposed call path. The term "open loan" is also never defined inline; a reader can only infer it from "returned loan ... ignored."

### Output behavior with `--remind` ambiguous - Severity: Nit
* **Affected Scope:** `--remind` output behavior; Technical Plan lines 40–48
* **Discrepancy Description & Rationale**: It is not explicit whether the command still prints the overdue list to stdout when `--remind` is supplied. The prose says rows are grouped by member and files are written, while the diagram shows both a stdout branch and a reminder-file branch. A user cannot tell what output to expect from the command in that mode.

### Member-name rejection behavior underspecified - Severity: Nit
* **Affected Scope:** member-name validation; Detailed Implementation Plan lines 73–74
* **Discrepancy Description & Rationale**: The statement that names containing `/` are "rejected with an error message that names the loan" leaves unclear which layer performs the validation, whether the whole command aborts or only that member's file is skipped, and what "names the loan" means concretely since a loan has no identifier described in the document. Behavior on problematic member names is therefore unpredictable from the plan alone.
