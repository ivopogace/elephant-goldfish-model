# Stage 5 — Initial Zoom Out Review: `overdue_reminders.md`

- **Target:** <RUN>/project/docs/designs/overdue_reminders.md (full file, lines 1-74)
- **Standard applied:** zoom-out-standard.md (egm-zoom-out reviewer)
- **Reviewers:** egm-zoom-out (Z1-Z6), egm-inventive-catalyst (F1-F8)
- **Baseline context given to reviewers:** <RUN>/project/README.md
- **Date:** 2026-11-10

Both reviewers verified against the actual codebase: `store.open_loans()` exists and returns the row shape the design assumes, and reuse of it is correct. The repo currently has **no** `tests/` directory, test runner, or dependency.

## Consolidated findings (deduplicated, by priority)

### Blocker B1 — The `reminders/` output mechanism contradicts its own claim and produces stale notes
- **Location:** Overview (16-19), Technical Plan (40-42), Detailed Implementation Plan step 1 (63-66), closing note (73-74).
- **Problem:** The design says the folder "always reflects the current state," but overwriting per-member files never removes a file for a member who returned their tool. A returned loan simply stops appearing in `open_loans()`, so its old reminder note survives on the shared library laptop and can be printed and sent for a tool that is already back. The design also silently overwrites files a volunteer may have edited, and leaves the folder lifecycle undefined: who creates it, what happens when nothing is late, whether anything is ever deleted, and whether a note was already sent.
- **Aggravating:** Member names become filenames, and only `/` is defended (73-74). Absolute paths (in `pathlib`, `Path("reminders") / "/x"` escapes the folder), `.`/`..`, empty names, name-length limits, case collisions, and two members sharing one name are unhandled. Erroring on a bad name aborts the whole run for every member.
- **Why it matters:** Goal 2 (trustworthy reminder notes) fails by the chosen mechanism itself, and three implementers would produce three different "compliant" behaviors.
- **Fix options (pick one and delete the contradicting claim):**
  - E (both reviewers' preference): `--remind` prints one delimited per-member note to stdout; the volunteer copies, pastes, or redirects. No folder, no staleness, no filename sanitization.
  - Or: a single dated, never-overwritten digest (e.g. `reminders/2026-11-10.txt`), plus an explicit statement under Goals/Non-Goals that the program does not know whether a note was sent.
  - Or, if per-member files stay: slug + numeric prefix filenames, reject-and-skip bad names with a warning naming the loan, plus a "N members skipped" summary.
- **Sources:** Z1, F2, F4, C2, C4.

### Blocker B2 — The fix depends on the same accident-driven discovery it was written to solve
- **Location:** The Problem (9-12) vs. Overview (16-20), Goals (24-25).
- **Problem:** The problem is that lateness surfaces only when another member asks. The solution is a command that works only when a volunteer remembers to run it. The document never states the trigger: who runs `lendr overdue`, how often, and what surfaces the count at the moment a volunteer already acts.
- **Unexamined alternatives:** printing a one-line overdue summary inside `lendr loan` / `lendr return` (reuses the same `late_loans` logic, no new habit); a scheduled or login-time local run that writes notes (the mail ban does not forbid local automation); reminding *before* the due date instead of after.
- **Fix:** name the trigger in Goals, or adopt a banner in an existing command; state in Alternatives Considered that rejecting email does not reject local generation.
- **Sources:** F1 (C1), F6 (partly), F2 (delivery-state half).

### Major M1 — Technical Plan leaks code-level detail into the architecture section
- **Location:** Technical Plan (34-51): exact format string (38), stdlib call and flag plumbing (50-51); Detailed Plan goes further (73).
- **Problem:** Format strings and function signatures belong in the Detailed Implementation Plan. Freezing them in two sections makes incidental choices look load-bearing and forces the two sections to stay in agreement.
- **Fix:** keep the Technical Plan at component level; move the format string, signatures, and `--today` mechanics into the Detailed Plan only.
- **Sources:** Z2.

### Major M2 — `--today` is speculative user-facing surface justified only by tests
- **Location:** Technical Plan (50-51), Detailed Plan step 2 (67-68).
- **Problem:** The stated reason is test repeatability, but `late_loans(rows, today)` already takes the date as a parameter — the test seam exists at the right level. `--today` with `--remind` can write notes computed from a fabricated date, and notes carry no generation date to reveal it.
- **Fix:** drop the flag; tests call the module function directly (which step 1 already commits to). If kept for "what was late last week," always print the effective date in output and inside each note.
- **Sources:** Z3, F7 (C3).

### Major M3 — "days late" and "late" are underdefined; sort has no tie-break
- **Location:** Overview (16-17), Technical Plan (36-38), Detailed Plan (63-64, 69-71).
- **Problem:** The predicate (`due < today`) is fixed by the test list, but the value is not: `days_late` for a loan due yesterday is 1 or 2 depending on an unstated rounding rule. Sorting by `due` alone gives unstable order for equal dates and flaky tests.
- **Fix:** state "inclusive calendar-day difference, local dates only, no time component"; add a secondary sort key (member, tool); add both cases to the test list.
- **Sources:** F3.

### Major M4 — Input failure handling is absent; the only error in the design protects the output
- **Location:** Technical Plan (36-51), Detailed Plan (63-74).
- **Problem:** Unspecified: missing/corrupt `loans.json` (the store raises on empty or malformed JSON), rows without a `due` key, unparseable dates, missing or unwritable `reminders/`, partway write failure, exit status. Both `loans.json` and `reminders/` resolve against the current working directory, so running elsewhere can silently create a fresh empty state instead of failing.
- **Fix:** add an "Errors and edge cases" subsection (warn-and-skip bad rows naming the loan; create the folder on demand; resolve paths relative to the data file), and state the exit status.
- **Sources:** F5, Z4 (path ambiguity half).

### Major M5 — Alternatives Considered offers no real alternative to the chosen mechanism
- **Location:** Alternatives Considered (53-59).
- **Problem:** Both rejected options are sibling output choices. Neither touches the two decisions that matter: post-hoc detection vs. pre-due prevention, and files vs. stdout. The `list` rejection leans on an unpinned claim ("would break a script one volunteer uses") that most plausible line-counting scripts survive; the load-bearing reason is the volunteers' explicit ask for a late-only list. The email rejection is sound but has been used to close the wider question "what can be automated offline?", which it does not close.
- **Fix:** reorder the `list` argument (ask first, script second, or verify the script exists); add pre-due window, in-command banner, and stdout-only reminders as entries with real reasons; state whether "don't break existing output" also bars the banner idea.
- **Sources:** F6, Z6.

### Major M6 — Goals are unfalsifiable, and the ledger has correctness bugs the design is silent about
- **Location:** Problem (11-12), Goals (24-26), Non-Goals (30-32).
- **Problem:** The one-in-five late rate cannot be measured after launch because the store records no return date, and Non-Goal 32 guarantees that stays true. Also, `return <tool>` closes *every* unreturned row for that tool: with two copies of the tile cutter, returning one hides the other borrower from `overdue` and from reminders entirely.
- **Fix:** add a "Known limits" paragraph (no delivery tracking, no outcome measurement, return-closes-all-copies) and record the two follow-ups (optional `returned_on`; per-item identity) as explicitly deferred.
- **Sources:** F8.

### Nit N1 — Layering deviation: new file persistence placed in the compute module
- **Location:** Detailed Plan step 1 (63-66).
- **Problem:** The repo's convention is store = disk, cli = output. `write_reminders` puts disk writes in `overdue.py` without acknowledging the deviation. Taking B1's stdout option makes this disappear.
- **Sources:** Z4.

### Nit N2 — Unstated ISO date coupling; test framework introduced by accident
- **Location:** Technical Plan (36), Detailed Plan step 3 (69-71).
- **Problem:** The design compares `due` values but never says they are ISO strings parsed with `date.fromisoformat` — the one data-format coupling Goal 3 rests on. Separately, the repo has no test runner at all; `tests/test_overdue.py` silently establishes a pytest-style convention as a plan line item instead of a decision.
- **Sources:** Z5.

### Nit N3 — Reminder note content is undefined
- **Location:** Technical Plan (40-42).
- **Problem:** The note body is "that member's late tools" — no due dates, no days late, no date of the note, no reply instructions. A note a volunteer can hand over verbatim is what would actually shorten weeks of unavailability.
- **Sources:** F-list idea "note content".

## Strongest counter-argument to the design as a whole
The minimal fix might be sorting `lendr list` by due date and marking late rows, giving the overdue view with zero new commands, flags, or file writes. Both reviewers judged the design survives this — volunteers independently asked for a late-only list — but the design should lead with that reason, not the brittle-script claim (see M5).

## What the design gets right (verified, not flattering)
Root-problem framing is honest and quantified. Non-Goals correctly fence off email, fines, and format migration. Reuse of `store.open_loans()` is verified correct against `src/lendr/store.py`. The no-network philosophy of the README is respected.

## Single most important issue (per both reviewers)
The output mechanism defeats the goal: per-member overwrite leaves stale reminder notes that carry the program's authority, and nothing triggers the command in the first place — fix B1's mechanism and B2's trigger before approval.

## Traceability matrix
| Consolidated | Sources |
|---|---|
| B1 stale reminders + filename safety | Z1, F2, F4, C2, C4 |
| B2 trigger gap | F1, C1, F6 (part) |
| M1 altitude leak | Z2, §3 |
| M2 `--today` | Z3, F7, C3 |
| M3 days-late/sort undefined | F3 |
| M4 input failures | F5, Z4 (part) |
| M5 alternatives | F6, Z6 |
| M6 unfalsifiable goals, store bugs | F8 |
| N1 layering | Z4 |
| N2 ISO + test runner | Z5 |
| N3 note content | F-notes |
