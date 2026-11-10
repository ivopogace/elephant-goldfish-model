# Stage 6 — Comprehension Test: `overdue_reminders.md`

Target: <RUN>/project/docs/designs/overdue_reminders.md
Reviewer: egm-comprehension (dispatched directly; no document standard, no GoldfishContext — the test measures the document's own self-containment)
Scope: FeatureRange lines 1-60, DetailedRange lines 61-74
Date: 2026-11-10

## Paraphrase — What this proposes (FeatureRange, lines 1-60)

The document proposes a new `lendr overdue` command for the lendr CLI, used by volunteers at the Maple Hollow Tool Library. By default it lists every open loan whose due date is strictly before today — oldest first — as one line per loan showing member, tool, due date, and number of days late. An optional `--remind` flag additionally groups the late loans by member and writes (overwriting) one plain-text reminder note per member into a `reminders/` folder, for a volunteer to print or paste into an email; the program itself never sends anything. A `--today YYYY-MM-DD` flag overrides the default `datetime.date.today()` so tests are repeatable. Explicitly out of scope: sending email/SMS, fines, member accounts, a tool catalogue, and any change to the storage format — existing `loans.json` files must keep working with no conversion.

Guesses/fills my paraphrase needed: I assumed "due date has passed" means strictly before today (the test list's "loan due today (not late)" at lines 69-70 confirms this, but the Overview's phrasing alone is ambiguous). I assumed `store.open_loans()` already exists (never stated; see Finding 5). I assumed the reminder note's contents mirror the stdout fields (never stated; see Finding 6).

## Paraphrase — How the existing system works, per this document

lendr is a command-line loan tracker whose data lives in a `loans.json` file, with existing commands documented in the project README. The existing `lendr list` prints open loans with due dates but never marks which are late, so volunteers compare due dates to today's date by eye and typically learn a tool is overdue only when another member asks for it. An existing module `store` exposes `open_loans()`, which returns loan rows carrying at least `member`, `tool`, and `due` fields. About one loan in five currently comes back late, and the program never sends communications.

Guesses/fills my paraphrase needed: I inferred rows also carry a returned/open status marker, because the test list expects "a returned loan (ignored)" (line 70), yet the document never describes how a loan's returned state is represented. The README link (line 20) covers "existing commands" only, not the data format.

## Paraphrase — What the implementation plan commits to build (DetailedRange, lines 61-74)

The plan commits to four artifacts: (1) a new `src/lendr/overdue.py` with two functions — `late_loans(rows, today)` returning late rows sorted by due date each annotated with a `days_late` integer, and `write_reminders(rows, folder)` grouping rows by member and writing one text file per member — separated from the CLI so date logic is testable without the command line; (2) a changed `src/lendr/cli.py` adding the `overdue` subcommand with `--remind` and `--today`, calling `overdue.late_loans` and printing the rows; (3) a new `tests/test_overdue.py` with four cases: due yesterday (late), due today (not late), returned loan (ignored), and two late loans of one member landing in a single reminder file; (4) a `README.md` update documenting the command and flag. It also commits to a rule: member names are used as reminder file names, and a name containing `/` is rejected with an error message that names the loan.

Divergence flagged: to make step 2 coherent I had to supply two calls the text never assigns to anyone — where `rows` comes from (presumably `store.open_loans()`, named only in the Technical Plan) and who calls `write_reminders` when `--remind` is set. See Finding 2.

## Findings

1. **Blocker — Technical Plan / Detailed Implementation Plan (lines 36, 63-66, 69-70): the returned-loan test contradicts the stated data flow, and the reader must guess which component filters returned loans.**
   Gap: the Technical Plan says rows enter via `store.open_loans()` and `late_loans(rows, today)` "returns late rows" — a contract stated purely in date terms. The test list then requires "a returned loan (ignored)." Under the spec as written, a returned loan with a past due date *is* a late row, so one of the two readings must be false: either `open_loans()` already excludes returned loans (then the unit test for `late_loans` cannot exercise that case at all, and the test's placement in step 1's date-logic suite is wrong), or `open_loans()` includes them (then "open_loans" is a misnomer and `late_loans` has an undocumented status filter). There is no third reading that fits.
   Why a fresh reader gets it wrong: they implement `late_loans` exactly as specified (date-only), write the returned-loan test, watch it fail, and then either bolt an unspecified status filter into `late_loans` or discover too late that `open_loans()`'s real behavior differs from its name — the central contract of the design.
   Suggested wording: after line 64, add — "`store.open_loans()` returns only loans the member has not returned; it does this today and is unchanged. The 'returned loan' test in step 3 runs at the command level against a `loans.json` fixture to verify that exclusion; `late_loans()` itself does no status filtering." (Swap which function owns the filter if that is the author's actual intent — the point is the document must say which.)

2. **Major — Detailed Implementation Plan, step 2 (lines 67-68): the CLI step never wires `--remind` to `write_reminders`, nor says where the rows come from.**
   Gap: step 1 defines `write_reminders(rows, folder)`, and no later sentence names any caller; step 2 says only "call `overdue.late_loans` and print the rows." The data source (`store.open_loans()`) appears only in the Technical Plan, and the diagram (line 45) shows it as a black box.
   Why a fresh reader gets it wrong: an implementer working top-down through the Detailed Plan builds a CLI that accepts `--remind`, then must invent the wiring; the most literal reading of step 2 — `--remind` accepted but doing nothing, or the dead-code `write_reminders` dropped in review — is the reading closest to the text.
   Suggested wording: "call `store.open_loans()` for the rows, pass them with the resolved today to `overdue.late_loans`, print the result, and when `--remind` is set call `overdue.write_reminders(late_rows, Path('reminders'))`."

3. **Major — Technical Plan (lines 41-42): "Existing reminder files are overwritten so the folder always reflects the current state" describes a mechanism that cannot produce the claimed property.**
   Gap: overwrite only touches files for members who are late *now*. A member who was late last week but has since returned the tool generates no row, so their old `reminders/<member>.txt` survives — the folder does not "reflect the current state." The document never says files are deleted or the folder cleared.
   Why a fresh reader gets it wrong: a volunteer following the doc trusts that a printed pile of notes is current and mails a reminder to someone who already returned the tile cutter; an implementer cannot tell whether to add folder-clearing logic the spec does not describe.
   Suggested wording (pick the intended one): "Before writing, the command deletes any `reminders/*.txt` whose member has no late loans" — or — "Files are overwritten only for members who are currently late; a file for a member who has returned their loans is left in place and must be discarded by eye."

4. **Major — Goals / Technical Plan (lines 26, 36-38): the loan-row structure is used as fact but never defined or linked.**
   Gap: the design's filtering, printing, and grouping all hinge on row fields `member`, `tool`, `due` (and an implied returned marker, per Finding 1), and line 26 asserts existing `loans.json` files "keep working without conversion" — a claim a fresh reader cannot check, because the format is described nowhere in the document and the sole README link (line 20) is scoped to "the existing commands." Storage format is a Non-Goal, which defers it but does not point at it.
   Why a fresh reader gets it wrong: they guess the schema from the output template `<member> <tool> due <date>`, and guess wrong on exactly the parts not in the template — how "returned" is encoded and whether `due` is a string or date — which is where the test fixture and name-vs-field handling live.
   Suggested wording: extend the line-20 link to cover "the existing commands and the `loans.json` record format," and add one sentence naming the row fields the command reads.

5. **Major — Detailed Implementation Plan (lines 73-74) / Technical Plan (line 41): member names are silently assumed to be unique, stable identifiers, and the error contract "names the loan" is unexplained.**
   Gap: names are the grouping key and the filename; the document never states names are unique (two members with the same name silently merge into one reminder file) or where canonical names come from. The rejection path says the error "names the loan" — but the offending value is the *member*, so a reader cannot tell which loan is meant when a member has several late loans, or why the loan is the reference at all (presumably so the volunteer can find the bad row in `loans.json` — that rationale is unstated).
   Why a fresh reader gets it wrong: they either treat the duplicate-name merge as a bug to "fix" outside the spec, or implement the error message naming one arbitrary loan row, which may not exist when the member has multiple late loans — behavior the doc gives no way to check against intent.
   Suggested wording: "Member names are unique identifiers in this library (one file per person is safe). When a late loan's `member` contains `/`, the command exits with `Cannot create a reminder file for member '<name>' (loan: <tool>, due <date>)` so the volunteer can find the entry in `loans.json` and fix the name."

6. **Nit — Overview / Technical Plan (lines 17-19, 41): the reminder note's actual contents are never specified.**
   Gap: line 18 promises a note "ready for a volunteer to print or paste into an email"; line 41 only says it is "listing that member's late tools." Whether it includes due dates, days late, or any prose is open — and "ready to paste" implies more than a bare tool list.
   Why a fresh reader gets it wrong: two implementers produce either one-word-per-line files or a full dated message, and test step 3 ("two late loans … in one reminder file") checks file *identity*, not contents, so neither is caught.
   Suggested wording: after line 41 add — "Each file contains one line per late loan in the same format as the command's output."

7. **Nit — Overview / Technical Plan (lines 18, 41): the base location of `reminders/` is undefined.**
   Gap: relative to the current directory, next to `loans.json`, or configurable is not said; `write_reminders(rows, folder)` (line 64) takes a folder parameter but no step says what the CLI passes.
   Why a fresh reader gets it wrong: files land wherever the volunteer happened to `cd`, and a print-me workflow breaks silently. (Low severity: one phrase fixes it.)
   Suggested wording: "writes into a `reminders/` folder beside `loans.json`."

## Terms and references used without definition (beyond findings 1-5 and 7)

- `store.open_loans()` / the `store` module (lines 36, 45) — never located or described; the Detailed Plan's file list implies it is pre-existing, but the document does not say so, and the diagram treats it as a black box.
- "the rows" / row field names `due`, `member`, `tool` as `loans.json` structure (lines 36-38) — output-template placeholders used interchangeably with data fields, never distinguished.
- `datetime.date.today()` (line 50) — general Python stdlib; not flagged per persona rules.
- The returned/open representation of a loan (line 70) — a data concept the document depends on but never introduces.
- `src/lendr/cli.py` (changed) and `README.md` (changed) (lines 67, 71) — cited as existing without any description of their current contents; acceptable at this altitude *only* because the README link exists; noted for completeness.
- `<date>` output format and the arithmetic of "days late" (line 38 vs line 65 `days_late`) — never pinned (ISO? whole days? one day late for yesterday?); a fresh reader guesses, harmlessly but unavoidably.

Sections I could paraphrase: all of them. No section was unparaphrasable as a whole; the Blocker is an internal contradiction between the Technical Plan's row pipeline and the test list, not an unreadable passage.
