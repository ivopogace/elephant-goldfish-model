# Overdue reminders for lendr

* **Author:** Robin Fixture
* **Date:** 2026-11-10
* **Source ticket:** EGMEVAL_PARENT_446a7be15c08

## Overview

`lendr` is a small command-line loan tracker for the Maple Hollow Tool Library. Volunteers record a loan, close it on return, and print open loans. Nothing tells them a loan has passed its due date, so they find out only when another member asks for the tool. About one loan in five comes back late.

This feature adds one read-only command that reports every open loan whose due date has passed, how many days late it is, and on request prints a plain-text reminder note for each such loan. The volunteer still does the contacting. The program sends nothing, stores nothing new, and leaves `loans.json` exactly as it is.

The success measure: a volunteer finds every late loan with one command in under ten seconds.

## Analysis

All seven review lenses ran: design critic, codebase details, zoom out, comprehension, implementation readiness, structural, and inventive catalyst. Their findings collapse into five problems and a set of smaller output decisions.

### 1. A silent all-clear is the worst failure

Three lenses independently found the same trap. `store.PATH` is `pathlib.Path("loans.json")` (store.py:5), which resolves against the directory the command is run from, not "next to the program" as README.md:10 says. `_load()` returns an empty list when the file is absent (store.py:8-9). So a volunteer who starts `lendr` from the wrong folder, or whose file was moved, gets an empty overdue list and exit status 0. That is indistinguishable from "nothing is late" and is worse than the eyeballing it replaces.

The same silence covers three other cases: a laptop clock set to the wrong date, a due date that cannot be parsed, and a row missing `returned`. Each currently either shifts every verdict or kills the command with a traceback and no output.

The fix the lenses converge on is to make the run self-describing. The output states the reference date and the file it read; a missing file is a distinct message, not an empty result; a due date that cannot be parsed is reported as "cannot judge" rather than dropped. Detection reliability has to be visible in the output, not assumed.

### 2. "Late" has no boundary in the concept

No answer said whether a loan due today is late. The readiness and comprehension lenses both flag this as the off-by-one that decides whether a volunteer chases someone who is not yet at fault, or misses a loan. The boundary is fixed below: late means the due date is strictly before the reference date.

Dates are stored as ISO strings produced by `date.isoformat()` (cli.py:20-21), so `date.fromisoformat` parses them without new code. Hand-edited or older files may contain something else, which is why unparseable rows need their own handling.

### 3. Loans have no identity, and `return` does not match one loan

`add` appends `member`, `tool`, `due`, `returned` and nothing else (store.py:16-19). `close(tool)` loops every row and marks every open row with that tool returned, with no `break` (store.py:22-27). Two open loans of the same tool therefore collapse on the first return, and no stable loan key exists.

This settles the note-granularity question for now: one note per late row, not one per member. A per-member note needs a member identity that does not exist, and grouping by the free-text `member` string splits "Ana" from "ana" and merges unrelated people. Per-loan notes use only fields that exist. The `close` behaviour is a pre-existing bug; this feature reads the same rows and does not fix it.

### 4. A new subcommand would silently print the wrong thing

`cli.py` dispatches with `if loan`, `elif return`, `else: print open loans` (cli.py:19-26). `list` works by falling through to that `else`, not by matching its own name. A parser entry for `overdue` added without an explicit branch would fall into the same `else` and print the ordinary open list, with exit status 0. That failure looks like a plausible answer, which makes it the hardest kind to notice.

Dispatch must become exhaustive: an explicit branch for `list`, an explicit branch for `overdue`, and an error for anything unmatched. That is a small refactor, but it is a precondition, not a detail.

### 5. Reminder notes conflict with the tool's output contract

`list` prints an unlabelled, space-separated row per loan. Prose notes and row data in one stream make the output's shape depend on the data, so neither a volunteer nor a script can tell which lines are records. The structural lens recommends one output shape per invocation.

The concept also cannot address a note: there is no contact data anywhere in the store, and member accounts are out of scope. The inventive lens resolves this by inverting the delivery model. The volunteer is the only channel. The note is addressed with the stored member string and written to be read aloud or handed over. No contact field, no delivery record, no send hook, not even a stub.

The zoom-out lens argues for cutting notes entirely and using `lendr overdue > notes.txt`. That is a fair challenge to a second output path, but it does not satisfy the request to produce reminder notes, and shell redirection still leaves the note text undefined. Notes survive as a rendering of the same rows, not as a new subsystem.

### 6. Smaller findings that still need decisions

* The empty result needs its own sentence; a blank screen cannot be told from a crash.
* Rows need a header and a days-late column, because the existing bare `member tool due` line is already misread as borrow date by a first-time user. This is safe only because `overdue` is a new command; `list` output stays byte-identical.
* Ordering is currently insertion order. Overdue rows should sort by due date, then member, then tool, so the oldest problem is first and ties are stable.
* Note grammar needs singular and plural forms for days, and tool names need quotes so `saw (small)` reads as one object.
* There are no tests and no console entry point in this checkout, although the README documents `lendr loan ...`. Any claim of "one command" is unverified until one of the two exists.
* `store._save` rewrites the whole file with no locking or atomic replace. This feature is read-only and does not make that worse, but three volunteers share one laptop and the existing write path can lose a row if two invocations overlap.

### Contradictions and what resolves them

| Contradiction | Compromise the concept was drifting toward | Resolution |
| --- | --- | --- |
| Late loans must be found reliably, but the only environment is a laptop clock and a relative data path | Trust `date.today()` and an empty list | Print the reference date and resolved file path; treat a missing file and unparseable dates as separate, visible states; allow the reference date to be set explicitly |
| A note must reach a member, but no contact data exists and accounts are out of scope | Quietly assume an address, or add a member registry | Invert delivery: the volunteer is the channel, the note is addressed by the stored name, and no contact field is added |
| The program must produce notes but must not send anything | Add a disabled send path "for later" | Notes are stdout text only. No network import, no send function, no delivery ledger |
| One command must both list loans and print notes | Append prose after the rows | One output shape per invocation: rows by default, note blocks only under `--notes`, never both |
| Notes should batch per member, but member is free text | Group by string and hope spellings match | Per-loan notes; member-level batching is deferred until a member key exists |

The Ideal Final Result: one read-only command that states the date and file it used, prints every open loan past due with days late, and on request prints one note per such loan. No new stored fields, no writes, no sending, and no way for a wrong folder or a wrong clock to look like good news.

## Goals vs. Non-Goals

**In-scope goals**

* `lendr overdue` lists every open loan with `due < reference date`, with a header, days late, sorted by due date, then member, then tool.
* `lendr overdue --notes` prints one reminder note per late loan, in the same order, and prints no table.
* `--today YYYY-MM-DD` overrides the reference date; the default is the laptop's local date, read once per run.
* The output states the reference date and the absolute path of the file read.
* A loan due today is not late. Returned loans never appear.
* Missing file, unreadable JSON, and unparseable due dates each produce a distinct, visible result rather than an empty list.
* `lendr list` output remains byte-identical. `loans.json` keeps its current shape and is never written by this command.
* `unittest` tests with a fixture `loans.json` cover the boundary, returned loans, sort order, note count, empty state, bad due date, and missing file.
* One README line documents the command, and the false "next to the program" sentence is corrected.

**Out-of-scope non-goals**

* Sending email, SMS, or notifications, and any record of what was handed to a member.
* Fines, member accounts, contact details, or a member registry.
* Writing note files, `--out` directories, templates, HTML, or printable layouts.
* A `reminded` field, reminder history, or any schema change or migration.
* JSON, CSV, or other machine-readable output; the consumers are three volunteers reading a terminal.
* Fixing `close()` closing every matching loan, and making `_save` atomic. Both are real pre-existing defects, recorded here so the draft does not silently inherit them as solved.
* Case-folding or normalising member names, and batching notes per member.
* Localisation, configuration files, and colour output.

## Alternatives Weighed

* **`lendr list --overdue` flag.** Offered as the smallest change: one argument and a filter in the existing print branch, about three lines. Rejected in brainstorm because it changes the meaning of a command that currently takes no arguments, inherits the `else` fall-through, and cannot host a second output shape without a second flag. It would also make `list` output conditional, breaking the byte-identical guarantee.
* **One command that prints the table and then the notes.** Rejected in brainstorm because mixed prose and rows make the output shape depend on the data. Notes are a separate rendering selected by `--notes`.
* **A separate `remind` verb.** Rejected: two commands to remember, two definitions of "late", and a note is only a rendering of the row set the overdue command already selects.
* **Cut notes and tell volunteers to redirect `lendr overdue` to a file.** Rejected by the request itself, which asks for reminder notes; the note text and its grammar still have to be defined somewhere.
* **One note per member.** Rejected for this version: no member key exists, and free-text grouping both splits and merges real people.
* **Store a `reminded` flag in `loans.json`.** Rejected: a schema change against the compatibility constraint, a write on a shared file with no locking, and state that goes stale overnight. Notes are derived on every run.
* **Write notes as files under `--out DIR`.** Rejected for this version: member names are free text, so file naming needs sanitising, collision rules, and an overwrite policy, all to replace what a volunteer can already see on screen.
* **A shell one-liner (`lendr list | awk ...`).** It works today because ISO dates sort lexicographically. Recorded as the baseline the feature must beat: the feature's value is removing date syntax from a volunteer's day, not adding a capability the shell lacks.
* **Add contact fields or a member registry.** Rejected: member accounts are explicitly out of scope, and a note addressed by name is enough for a volunteer standing in front of the member.

## Key Decisions & Staging for Next Steps

**Decisions to carry into the draft**

1. Command surface is `lendr overdue`, with `--notes` and `--today YYYY-MM-DD`. No positional arguments.
2. Late is `due < reference date`. Due today is not late. Returned loans are excluded. The boundary is stated in the command's help text.
3. Reference date defaults to the local date, read once. `--today` exists because the clock is the only time source and a wrong clock must be correctable without changing system settings.
4. `overdue` prints a header row and `member`, `tool`, `due`, `days late`, sorted by due date, then member, then tool. `list` is untouched.
5. One note per late loan. Note text names the library, the member as stored, the quoted tool, the due date, the days late, and the return instruction. Days are singular at 1.
6. Notes print to stdout only, with no table, under `--notes`. No files, no send path, no delivery record.
7. The run prints the reference date and resolved absolute `loans.json` path. A missing file is its own message with a non-zero exit; corrupt JSON is an error; a row with an unparseable `due` is skipped with a one-line stderr warning and does not hide the other rows.
8. The command is read-only: no schema change, no `reminded` field, no migration. Existing `loans.json` files are valid input as they are.
9. Dispatch in `cli.py` becomes exhaustive, with explicit branches for `loan`, `return`, `list`, and `overdue`, so no command can fall through to another command's output.
10. Tests use `unittest` and a fixture file, and one test invokes `main(["overdue"])` to prove the one-command success measure on disk.

**Staging**

The dispatch refactor and the row selector land first, because a new verb is unsafe until `else` no longer means `list`. The table rendering and note rendering follow as two functions over the same selected rows. Tests and the README line land with them. Nothing in this feature writes to `loans.json`.

**Open question for the draft**

The checkout has no console entry point or packaging metadata, so the documented `lendr` command cannot be run here as written. The draft must either add the entry point or state that the tests call `main()` directly and packaging is handled outside this change.
