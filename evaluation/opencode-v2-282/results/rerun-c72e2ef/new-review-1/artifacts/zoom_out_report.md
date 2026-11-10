# Goldfish Review Report — Stage 5 (Initial Zoom Out)

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (full file, lines 1–74)

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-zoom-out` | completed |
| `egm-inventive-catalyst` | completed |

## Prioritized Findings (Blockers -> Major -> Nits)

### Test-only date override exposed as a public CLI flag - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** `Technical Plan`, lines 50–51
* **Discrepancy Description**: The design already injects the date at the function boundary (`late_loans(rows, today)`) and says this exists so the date logic can be tested without the command line. The `--today` CLI flag adds a second test seam for the same purpose and a permanent public interface nobody asked for.
* **Rationale & Recommendation**: The stated goals stay testable without the flag. Keep one seam, not two: either drop `--today`, or drop the injection rationale for the module.

### Member names used directly as file paths, patched by one rejection rule - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** `Technical Plan`, line 41; `Detailed Implementation Plan`, lines 73–74
* **Discrepancy Description**: Writing `reminders/<member>.txt` from a volunteer-entered string invites an accumulating validation list: `/`, `\`, `..`, empty names, spaces, case-insensitive collisions on other filesystems, and reserved names. The document already shows this trend by adding a single `/` rejection rule at the end.
* **Rationale & Recommendation**: Stop making filenames carry identity. Write one report file per run, use fixed names with the member name inside the file, or print grouped notes to stdout for the volunteer to redirect. Choosing a structurally safe output shape now avoids a filename-sanitizing subsystem later.

### "Overwritten so the folder always reflects the current state" does not follow - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** `Technical Plan`, lines 40–42
* **Discrepancy Description**: Overwriting does not remove files for members who are no longer late, so stale reminder notes stay in the folder and can still be printed. Overwriting also silently destroys any notes a volunteer wrote on the file. The design does not state where `reminders/` sits relative to `loans.json`.
* **Rationale & Recommendation**: Making the guarantee true means deleting or rebuilding the folder each run, turning a read-only report into durable state that must stay in sync. Either state plainly that the files are per-run scratch output and clear stale ones, or avoid persistent files.

### Same component detail stated twice at two altitudes - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** `Technical Plan` (36–51) versus `Detailed Implementation Plan` (61–74)
* **Discrepancy Description**: The Technical Plan already names `store.open_loans()`, `late_loans(rows, today)`, `write_reminders(rows, folder)`, `datetime.date.today()`, and the per-row output format. The Detailed Plan restates the same module, signatures, and grouping behaviour.
* **Rationale & Recommendation**: Describe components, data flow, and boundaries once in the high-level section; keep helper-level specifics in one place only. Duplicated descriptions on a 74-line document will drift apart on edit, and they push code-level detail into the first section a fresh reader sees.

### Rejected `list` alternative is a straw man - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** `Alternatives Considered`, lines 55–57
* **Discrepancy Description**: The rejection reason (breaking a volunteer's counting script) applies only to changing the default `list` output. A `lendr list --overdue` flag would leave existing output untouched and reuse the existing subcommand, print loop, and `open_loans()` plumbing instead of adding a fourth command.
* **Rationale & Recommendation**: Since this is the closest reuse-based competitor to the proposal, give it an explicit rejection reason that actually covers it.

### Motivation drifts from the goal the design pursues - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** `The Problem`, lines 9–12
* **Discrepancy Description**: "About one loan in five comes back late, and popular tools such as the tile cutter are often unavailable for weeks" are outcome measures this design does not claim to move; it reports lateness that already exists. The real root problem is visibility.
* **Rationale & Recommendation**: Say plainly that the problem is visibility so the frequency figure is not read as a target the command must improve. If reducing lateness were the objective, reminders-before-due would be a different proposal.

### One new module mixes a pure filter with filesystem writes - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** `Detailed Implementation Plan`, lines 63–66
* **Discrepancy Description**: `overdue.py` is justified as a test seam for the date logic but also hosts `write_reminders`, which is unrelated filesystem work. The Technical Plan never says how `due` is compared to today; the current storage makes a string comparison silently correct.
* **Rationale & Recommendation**: Keep the pure filter where it can be tested (the `store` layer already owns the row shape and the ISO `due` string) and put the writing step in `cli.py` where the flag lives. Name the date-comparison assumption so a future storage change does not break it quietly.

## Inventive Catalyst

No false compromise detected. The catalyst found the foundational design balanced at the strategic level and produced no transforms.

## Checks That Pass

* Context is sufficient: problem, overview, goals, non-goals, and data-flow sketch let a fresh reader understand the objective and motivation. No prerequisite failure under the Zoom-Out Standard.
* Reuse verified by code search: `src/lendr/store.py:30` already provides `open_loans()`, and the design consumes it rather than re-reading or re-filtering `loans.json`. Nothing in `src/` already computes lateness, formats reports, or writes per-member files.
* No premature optimization: no caching, indexing, background work, or async plumbing; the data flow is one pass over an in-memory list.
* Non-goals are honest about scope (no email, no fines, no storage change) and align with the README's no-network constraint.
* Apart from member-name file handling, the plan touches existing files only where needed (`cli.py`, `README.md`) and follows the existing flat `argparse` subcommand pattern.
