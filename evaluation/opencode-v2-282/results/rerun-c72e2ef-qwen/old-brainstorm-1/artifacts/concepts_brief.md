# Overdue reminders for lendr

* **Author:** Robin Fixture
* **Date:** 2026-11-10
* **Ticket:** EGMEVAL_PARENT_e45f65cb7019

## Overview

Volunteers at the Maple Hollow Tool Library find out a tool is late only when
another member asks for it; about one loan in five comes back late. Today the
workaround is running `lendr list` and comparing due dates by eye, which misses
loans. This concept adds one command that prints every open loan whose due date
is before today, sorted most-late first and grouped by member, with the days
overdue shown on each line, and turns that same output into plain-text reminder
notes a volunteer carries to members by hand. The program sends nothing itself.

Success measure: a volunteer finds every late loan with one command in under
ten seconds. Every review lens read this correctly: ten seconds is human scan
time, not computer run time. The command must produce output a person can trust
at a glance, or the measure fails no matter how fast the code is.

Seven independent review lenses examined the concept against the existing code
(`src/lendr/cli.py`, `src/lendr/store.py`, `README.md`). The combined verdict:
the date filter is trivial; the real work is not lying when the tool says
"nothing is late." The findings cluster into two pre-existing defects that cap
the accuracy of the feature, one piece of state to refuse, one output contract
to pin down, and a small set of prerequisite fixes in the CLI itself.

## Analysis

### The dangerous failure is a confident all-clear

Two defects in the current code can make the new command report "no late
loans" when late loans exist, and both were found by most lenses.

**Wrong file, silent zero.** `store.py` resolves `loans.json` relative to the
current working directory, while `README.md` tells people the file lives "next
to the program." Three volunteers on one shared laptop will run from different
directories. From the wrong directory, the file simply does not exist, the
loader returns an empty list, and the overdue command prints a clean "nothing
is late" from a ledger that is not the ledger. The brief requires: resolve the
data path from one anchored location (with a `--file` or environment override),
make a missing file a distinct loud outcome that is never confused with
"nothing overdue," and print on every run which file was read, how many rows it
contained, and which date was used for the comparison.

**No loan identity, bulk close.** `lendr return <tool>` marks *every* open row
with that tool name as returned, and nothing prevents two open rows for the
same tool. One return can erase another member's still-out loan from the
overdue list with no trace. Three lenses called this a blocker for the stated
measure ("finds *every* late loan"), because the data source can lose late
loans undetectably and a reminder note for a wrongly closed loan is a false
promise to a member. Nothing in the current record identifies a single loan.
The resolution options raised: give `return` the member argument so the pair
resolves one row, or refuse and list candidates when more than one open row
matches, and key notes on the `(member, tool, due)` triple or a small
per-row handle rather than on the tool name. Adding a loan id inside
`loans.json` is also possible and is a schema decision deferred to the design
stage. Whichever route is chosen, the overdue output must label
duplicate-open-tool groups explicitly, and the concept must record the
bulk-close behavior as a known pre-existing defect rather than silently
design on top of it.

### The command must not inherit the eye-comparison problem

`lendr list` prints three unlabelled fields in insertion order. That is the
mechanism by which the current workaround misses loans: a volunteer doing date
arithmetic over an unordered list. A new command that only filters, and still
prints unordered rows with raw dates, does not meet the ten-second measure.
Required output contract: one line per late loan, sorted most-overdue first,
days-late computed and printed, member and tool and due date labelled, a
summary line ("3 of 11 open loans are overdue"), and the source path and
as-of date printed so a wrong read is visible at a glance.

Data hygiene belongs in the same contract, because the overdue command is the
first command whose entire purpose is completeness, and hand edits are expected
in a human-visible JSON file:

* Pin the boundary in words and code: **due today is not late** (`due < today`).
  A loan due today can still come back tonight; the report becomes untrustworthy
  if it cries wolf daily. Print the resolved "today" so the human sees the cut.
* Three buckets on screen: **Late**, **Due today**, and **Can't tell** (missing
  or unparseable `due`, rows missing keys). A bad row is printed as a named
  problem row, never silently dropped, never a traceback. One lens verified a
  specific hazard: `"returned": "false"` as a string is truthy in the current
  code, so such a loan disappears from the list entirely; the read path needs
  an explicit rule.
* New loans should validate `--days` (reject zero and negatives), which
  otherwise manufacture already-overdue rows.

### Reminder memory: the proposal is to refuse it

The concept asked whether lendr should remember that a reminder was produced,
"given the loans.json format constraint limits where that state can live." Two
lenses corrected the premise: the constraint does **not** forbid it. An added
optional key keeps old code working (existing readers ignore unknown keys), and
a sidecar file leaves `loans.json` bytes untouched. What actually argues
against reminder state is behavior, not schema:

* A "reminded" flag suppresses a loan from the very list that is the success
  measure. If the volunteer prints the note and never walks to the member, the
  loan vanishes from every future run. This converts a visible failure into an
  invisible one.
* Rows are never deleted and `close()` only flips a bool, so the flag's
  lifecycle is undefined: a re-loaned tool can inherit "already reminded" and
  its genuinely late loan is dropped. Repeat offenders are exactly the cases
  that matter.
* It makes the daily command non-idempotent. Re-running to double-check is the
  expected behavior for three volunteers on one laptop, and re-running must
  give the same answer.
* Any state write turns the most-run command into a whole-file rewriter, and
  `_save` today is a non-atomic truncate-and-write. A crash or a second
  volunteer mid-write can destroy the one file the constraints say must keep
  working.

Days-overdue, recomputed from the due date on every run, delivers the same
"this one is a real problem" signal (a loan at 30 days is visibly worse than
one at 2) with zero new state, and the paper note a volunteer carries is
itself the only delivery record the system needs. Proposed decision: v1 is a
pure read. If reminder accountability is later proven necessary, the shapes on
the table are an append-only log outside `loans.json` or one dated file per run
whose existence is the record — never a mutable flag that gates the list, and
never state that can suppress a loan.

### Notes: the screen is the note

Writing per-loan note files creates a second pile nobody owns: a directory, a
filename scheme that must survive member names with spaces and slashes,
collision and overwrite rules, and no deletion path. On one laptop, three
volunteers, once a day, per-loan files accumulate over a thousand notes a year,
and last week's stale notes look like undone work — recreating the false
all-clear in paper form. Proposed decision: the reminder note is the command's
standard output, grouped per member (one walk is one door, not one tool) with
per-loan lines, carrying the generation date and the closing instruction
(`lendr return <tool> ...`) so the paper stays connected to the ledger. When a
volunteer wants a file, the shell already provides one:
`lendr overdue > notes.txt`. If file output is ever built in, the weighed shape
is one dated file per run, wholesale regenerated, never incremental.

### Prerequisite fix in the CLI itself

`cli.py` dispatches with `if loan / elif return / else`, and the bare `else`
*is* the `list` printer. Add a fourth subparser without a matching branch and
`lendr overdue` silently prints all open loans — on-time loans presented as
late, exit code clean. Four lenses required the same fix as part of this
feature, not as later cleanup: explicit branches (or `set_defaults(func=...)`)
so an unhandled command fails loudly instead of falling through. The overdue
predicate itself should live once, in `store.py`, shared by `list` and the new
command, taking "today" as a parameter so the two outputs can never disagree
and the boundary is testable.

### Non-problems, recorded so drafting does not invent them

* Ledger size: whole-file read and scan is fine for years (an illustrative
  estimate: five years at twenty loans a week is a few thousand rows, a few
  hundred kilobytes, milliseconds to parse). No index, cache, or database.
* No external quota, API, token budget, or telemetry exists, and "the program
  sends nothing" removes the only channel that would need one. The durability
  story is a single laptop copy of `loans.json`; reviewers suggest one manual
  backup before the first release that writes, and atomic replace if any write
  is ever added.
* The "one in five late" statistic is not computable from stored data — there
  is no returned-on date. The command reports "late now," not "came back late."
  Measuring success means a manual tally or explicit acceptance test, not a
  query.
* Operational signals available instead of monitoring: print counts, print the
  path, and pin exit codes (one lens proposed 0 = ran and nothing overdue,
  1 = overdue loans exist, 2 = data or usage problem). The code choice is the
  author's; the brief requires *some* pinned contract.
* Packaging reality: the repo has no tests, no `pyproject.toml` or entry point,
  and `README.md` shows `lendr <cmd>` though that command does not currently
  exist as an installed program. The brief requires stating the real invocation
  form, adding `help=` text to every subcommand, updating `README.md` lines 6-8
  in the same change, and adding a small stdlib `unittest` fixture covering the
  boundaries: due yesterday / due today / due tomorrow / unparseable due /
  duplicate open tool / missing file.

### Inventive reframing

The catalyst lens named the two contradictions the design inherits and the
transforms that dissolve them instead of compromising. First: per-loan
truthfulness versus one-keystroke simplicity — resolved by deriving a loan
handle at render time (inversion: identity exists where it is used, not in the
schema) and by having `return` refuse on ambiguity instead of guessing
(cushioning). Second: reminder accountability versus an untouched ledger —
resolved by extraction (state, if any, lives outside `loans.json`) and by
making the disposable note its own audit trail (cheap-dispensables). The
ideal final result as the lens stated it: one keystroke yields the complete
late set, already laid out as the note; producing paper is an afterthought that
cannot change what the volunteer saw; and no loan is ever named by tool alone.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * One command (`lendr overdue`) that prints every open loan with
    `due < today`, sorted most-overdue first, grouped by member, with
    days-late, counts, the file read, and the as-of date on screen.
  * The printed output doubles as the hand-carried reminder note.
  * Distinguish loud outcomes: no data file vs nothing overdue vs rows that
    can't be judged (reported, never dropped silently).
  * Prerequisite fixes: explicit command dispatch, anchored data path, single
    shared late-predicate in `store.py`, `--days` validation.
  * A stated mitigation for the bulk-close defect so notes never key on tool
    name alone.
  * README and `--help` updates; stdlib tests for the boundary cases.
* **Out-of-Scope Non-Goals:**
  * Email, SMS, or any sending by the program.
  * Fines and member accounts.
  * Persisted "already reminded" state in v1.
  * A built-in note-file subsystem (shell redirection covers it for now).
  * Databases, indexes, caches, scheduling/daemons.
  * Historical "returned late" statistics.

## Alternatives Weighed

* **Sort and annotate `list` only; no new command.** The diagnosed cause of
  misses is unordered eye-comparison, which sorting alone fixes, with no new
  surface. Rejected during brainstorm because the success measure asks for one
  command that yields exactly the late set in ten seconds, and `list` prints
  everything; carried as the documented fallback if the team balks at a fourth
  command.
* **`lendr list --overdue` flag.** Rejected: it puts a read-only report and a
  changed human interface into one command, keeps the ambiguous dispatch, and
  changes `list`'s existing output contract, which the volunteers' current
  habit depends on.
* **Reminder state as an optional key inside `loans.json`.** Rejected — not
  because the format constraint forbids it (it does not; verified by two
  lenses), but because a suppression flag loses late loans when a walk is
  skipped, has undefined lifecycle on an append-only ledger, breaks idempotent
  re-runs, and turns the daily read into a non-atomic whole-file write.
* **Sidecar `reminders.json` / append-only reminder log.** Weighed and set
  aside: two files that can disagree with no shared transaction, and a second
  writer on a store with no locking. On the table only if accountability is
  later demanded.
* **Per-loan note files.** Rejected: unbounded accumulation, filename escaping
  of member names, stale paper that looks like undone work. One dated file per
  run is the shape retained if file output is ever required.
* **Naming the command `lendr remind`.** Rejected on comprehension grounds: it
  reads as "a message goes out," which the hard constraints forbid. The name
  should say what it shows: `lendr overdue`.

## Key Decisions & Staging for Next Steps

Decisions carried to `/egm-draft`. The author confirmed this direction in the
Step 3 iteration on 2026-11-10: stateless read-only design, notes as terminal
output, and prerequisite fixes accepted:

1. **Read-only by construction.** `lendr overdue` writes nothing. Overdue-ness
   is derived on every run from `due` and today.
2. **One boundary rule.** `due < today`; due-today is a separate printed
   bucket; the as-of date is on screen.
3. **Fix the ground first.** Explicit dispatch, anchored data path with a
   visible resolved file, and a chosen `return` disambiguation (member
   argument vs refuse-on-ambiguity) are part of this change.
4. **The screen is the note.** Per-member grouping, per-loan lines, days-late,
   generation date, closing instruction; file output via shell redirection
   only.
5. **No reminder state in v1**, for the suppression and lifecycle reasons
   above, with the sidecar and dated-file shapes recorded for later.
6. **Verify it.** Stdlib tests over a fixture ledger for the named boundary
   cases; README and `--help` updated in the same change; exit-code contract
   pinned.
7. **Open question for drafting:** loan identity — render-time
   `(member, tool, due)` handle vs an additive stored `id` key — decides how
   `return` disambiguates and how any future reminder annotation would key.
