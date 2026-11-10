# lendr Overdue Reminders

* **Author:** Robin Fixture
* **Date:** 2026-11-10
* **Ticket:** EGMEVAL_PARENT_eda264da822c

## Overview

Volunteers at the Maple Hollow Tool Library find out a tool is late only when another member asks for it. Roughly one loan in five comes back late. The current workaround is for a volunteer to run `lendr list` and compare due dates by eye, which misses loans.

This change adds a read-only report over the existing `loans.json`: one command that prints every loan still recorded as open whose due date has passed, plus an optional plain-text reminder note per member that a volunteer can read aloud or copy. Three volunteers share one laptop and run lendr by hand about once a day. The program stays offline, uses only the Python standard library, changes no part of the `loans.json` format, and never sends anything itself. Success is a volunteer finding every late loan with one command in under ten seconds.

The reviews below change the shape of that promise more than its size. Two claims in the original concept do not survive contact with the code: the list cannot "work around" the return path's loss of loan identity, and a wrong working directory can produce a confident "nothing is late". Both must be written down and handled in output before this is built.

## Analysis

### 1. "Work around `close(tool)`" is not possible, and the claim must shrink

`store.close(tool)` (`store.py:22-27`) marks every open row with that tool name as returned. If a tool went out twice, the first return destroys the record that the second borrower still has it. The late list reads `returned`, so the still-missing loan is invisible. No read-only query can recover a fact that has been overwritten.

Therefore the success criterion must read "every loan **still recorded as open** and overdue", not "every late loan". That is testable; the original wording is not. Fixing loan identity stays out of scope, but the limitation belongs in the README and in the report.

Two read-side cushions cost nothing and were proposed independently by four reviewers:

* Print `N days late` per loan. It is derived from `due` and today, needs no stored state, and gives volunteers a way to prioritise.
* Detect duplicate open loans for the same tool and print a clearly separated warning naming the members and due dates: one `return` will close both, so record the returns separately. This prevents the *next* lost loan without repairing past ones.

Deduplicating by tool or member must not happen. One row per recorded loan; grouping is presentation only.

### 2. `loans.json` lives in the working directory, not next to the program

`store.PATH = pathlib.Path("loans.json")` (`store.py:5`) resolves against the current working directory. The README says the file lives "next to the program". On a shared laptop with three volunteers, starting from a home directory or a different shell makes `_load()` return `[]` and the new command print nothing — indistinguishable from "no late loans". This is the worst failure for a once-a-day manual check because it looks like a clean answer.

Requirements:

* `late` must always print the resolved absolute path it read and the number of open loans scanned, so a wrong directory shows up as a suspicious denominator, not silence.
* Missing file, no open loans, and no late loans must be three different messages.
* The README's "next to the program" wording must be corrected, and one canonical working directory and command line named. The repo has no `pyproject.toml`, no `__main__.py`, and no console entry point, so today no `lendr` executable exists; that gap must be stated rather than assumed.

### 3. A new subcommand will be swallowed by the existing dispatch

`cli.py:19-26` is `if loan / elif return / else print open loans`. Adding a `late` subparser without an explicit branch means `lendr late` prints the unfiltered open-loan list and exits 0. The volunteer sees plausible output and cannot tell the feature failed. This is the most likely way the change ships broken.

Requirement: explicit dispatch per subcommand (for example `set_defaults(handler=fn)` or an explicit `elif`), with a terminal error instead of a fallback branch. The report must include a test where one loan is overdue and one is not, asserting `late` excludes the not-yet-due loan.

### 4. The reminder output was the weakest part of the concept

A reminder note carries no contact data and is not sent, so at first reading it is the same three fields in a different layout. The YAGNI review recommended dropping it; the other reviews kept it but rejected a second subcommand. The reconciled position: reminder output is a display mode of the same query, selected by one flag (`lendr late --notes`, name to be confirmed), never a separate `remind` verb. It replaces the table rather than appending to it so copied text is clean. A note must be self-contained — library name, as-of date, member, each tool with due date and days late, one closing instruction — because a single block is what gets copied or handed over. If the note cannot be made self-contained, drop the mode and sort the table by member.

Nothing is stored about reminders sent, so re-running produces identical notes, and duplicate or skipped reminders are a human process. All three volunteers running the command each day will produce overlapping notes; that is an accepted cost, stated rather than engineered around.

### 5. Output contract, error behaviour, and the boundary rule

Undefined ordering makes the result depend on JSON append order and turns a ten-second scan into luck. The brief must pin, before implementation:

* Sort order: due date ascending, then member, then tool.
* One "as of <date>" line with counts, for example `3 late of 41 open loans in /path/loans.json`.
* A `DAYS LATE` figure and plain ASCII columns; member names may contain spaces, so space-joined fields are unsafe.
* Reminder text and the table on stdout; warnings, counts, and errors on stderr, so `lendr late --notes > notes.txt` does not capture diagnostics.
* A due-today footnote, since due-today absence otherwise looks like a bug.
* Exit codes: 0 when the command ran, 1 when the file could not be read, 2 for usage errors.

One bad row must not kill the report. `late` is the first command to parse `due`; a hand-edited or half-written row would raise and hide every late loan. Parse per row, skip unparseable or incomplete rows into a labelled stderr warning, still print valid late loans, and exit non-zero so "clean" and "skipped some rows" are distinguishable. A truncated file from the non-atomic `_save` must produce one plain sentence naming the file and the parse problem, never a traceback and never an empty list presented as a clean result.

"Late" means `due < today` with today captured once per process. Making `_save` atomic (write temp, `os.replace`) is format-compatible and worth doing separately, but it widens the rollback surface and is not required to ship this.

### 6. Where the logic lives, and the tests that protect it

`store.py` stays a JSON adapter: no `datetime` import, no clock read, no notion of "late", no grouping, no printing, no new write path. `cli.py` owns argparse, one captured `today`, and pure helpers — `late_loans(rows, today)`, grouping, and two renderers. If the helpers push `cli.py` past roughly 120 lines, they move to `lendr/report.py`; do not create that file pre-emptively.

The only real logic is the boundary and it can regress silently. Add stdlib `unittest` coverage: due yesterday is late, due today is not, due tomorrow is not, unparseable `due` is reported and skipped, two loans for one member group into one note. `date.fromisoformat` requires Python 3.7 or later; state a minimum or compare zero-padded ISO strings.

### 7. What this does and does not achieve

The "one in five" figure is a volunteer observation, not something `loans.json` can confirm: with only `due` and a boolean `returned`, there is no return date, so lateness rate is not computable even retrospectively. No telemetry is being added, and none should be claimed. The feature makes lateness visible; it does not change member behaviour. A monthly manual check (count of loans more than seven days late against a shelf walk) is the affordable way to see whether the reminders help.

## Goals vs. Non-Goals

**In-Scope Goals**

* One command lists every loan still recorded as open and past its due date, sorted so a volunteer can scan it in under ten seconds.
* Each row shows member, tool, due date, and days late.
* The output states the resolved file path, the as-of date, the count of late loans, and the count of open loans scanned.
* Missing file, no open loans, and no late loans produce three distinct messages.
* An optional notes mode prints one self-contained reminder block per member, on stdout, with nothing sent or saved.
* A warning lists tools with more than one open loan, because one return will close all of them.
* Malformed rows are reported and skipped; the command never shows a traceback or a falsely clean result.
* README and `--help` describe the new command, the due-today rule, the working-directory assumption, and the reminder limitation.
* Boundary tests exist.

**Out-of-Scope Non-Goals**

* Sending email, SMS, or any network traffic, and contact details for members.
* Fines, member accounts, borrowing limits, or member identity beyond the stored name string.
* Changing the `loans.json` schema, adding a loan id, recording return dates, or storing reminder state.
* Fixing `close(tool)` to close one loan, and repairing loans it already closed.
* Normalising or merging member spellings; grouping is exact string.
* Servers, daemons, schedulers, caches, or logging frameworks.
* Measuring or promising a lower late-return rate.

## Alternatives Weighed

* **Flag on the existing command, `lendr list --late`.** The smallest change: two lines, no dispatch edit, no new command. Set aside because the daily volunteer has to remember a modifier and `list` already prints open loans; a distinct `late` word is easier to find in `--help`. Revisit if review shows the dispatch restructure is riskier than it looks.
* **Separate `lendr remind` subcommand.** Set aside: it duplicates the query and adds a second dispatch branch, and the word implies delivery the program must not perform.
* **Store a "reminder sent" flag or log.** Set aside: it breaks the schema constraint, introduces write contention on a non-atomic save, and needs loan identity that does not exist.
* **Change `close(tool)` to refuse or disambiguate duplicate tools.** A real fix, and the one reviewers most wanted, but it changes return behaviour for volunteers mid-flight and was ruled out of scope by the author. Recorded here so the choice is visible when the identity defect is eventually addressed.
* **Rewrite `loans.json` or backfill return dates.** Set aside: irreversible, no data source for the missing facts, and unnecessary for a read-only report.
* **A `lendr late --member NAME` filter.** Set aside: three volunteers and one laptop do not need filtering; add it only if the notes are too long to scan.
* **Deduplicate rows by tool so the list looks tidier.** Set aside: it hides the exact ambiguity the warning exists to surface.
* **Note per loan instead of per member.** Set aside: one person holding two late tools then gets two slips that are easy to separate in a pocket.

## Key Decisions & Staging for Next Steps

1. The report is read-only and reads only `store.open_loans()`-equivalent data; no new write path anywhere.
2. Success is restated as "every loan still recorded as open and overdue", with the `close(tool)` limitation documented rather than worked around.
3. `late` prints the resolved path and counts; missing file, empty library, and clean result are distinct.
4. Dispatch becomes explicit; no subcommand may be served by the fallback branch.
5. Notes are a flag on `late`, self-contained per member, stdout only, nothing stored.
6. One captured `today` and one pure predicate feed both display modes; `store.py` gains no date logic.
7. Duplicate open loans for one tool produce a visible warning and are never deduplicated away.
8. Open decisions for the author before drafting: the exact flag name (`--notes` versus `--remind`), whether the duplicate-tool warning ships in the first version, whether `lendr list` gains a one-line pointer when anything is late, whether atomic `_save` is pulled in as a separate change, and the minimum Python version to state.
