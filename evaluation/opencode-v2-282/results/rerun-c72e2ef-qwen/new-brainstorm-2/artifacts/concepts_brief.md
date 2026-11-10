# Overdue Reminders for lendr

* **Author:** Robin Fixture
* **Date:** 2026-11-10

## Overview

Maple Hollow Tool Library volunteers currently learn a tool is late only when
another member asks for it. About 1 in 5 loans comes back late, and the daily
fix is to read `lendr list` and compare due dates by eye, which misses loans.
This concept adds an overdue check to `lendr`: one offline command finds every
loan past its due date and produces reminder-note text a volunteer can copy or
hand to a member. The program itself sends nothing.

Hard constraints from the requester: offline only, Python standard library
only, the existing `loans.json` format must keep working, no email/SMS sending,
no fines, no member accounts. Success as stated: a volunteer finds every late
loan with one command in under ten seconds.

## Analysis

Seven brainstorm lenses reviewed the concept against the code
(`src/lendr/cli.py`, `src/lendr/store.py`). The findings converged.

### The dangerous failure is a confident "nothing is late"

Five lenses independently raised the same blocker: `store.py` resolves
`loans.json` relative to the current working directory, while the README and
this concept say it lives "next to the program." On one shared laptop used by
three volunteers by hand, running from the wrong folder reads no file, and the
loader treats a missing file as an empty list. A reminder command inherits
this and prints a clean, wrong "all clear." Automated silence is worse than
today's eye-comparison, because the volunteer will trust it. The lenses' fix
is a precondition, not an option: pin data access to one resolver, print on
every run what was checked (resolved file path, rows read, open count, late
count, the date used), and fail loudly with a non-zero exit when the file is
missing or unreadable.

### The report must be total, row by row

Nothing in the program ever parses the `due` string today. The new command is
the first code that must, and `due` has never been validated — the file is
hand-editable JSON. One bad row must not crash the run (the volunteer sees a
Python traceback and gives up) and must not be silently skipped (a missing
loan is the exact failure this feature exists to prevent). Lenses 4 and 5
agree on the rule: every row in the file appears in exactly one output
section, and unparseable rows are listed under a visible "can't tell — needs
a human" heading with a count.

### The ledger can hide loans before the report ever runs

`lendr return <tool>` closes *every* un-returned row matching the tool name,
so a duplicate checkout or a mistyped return can erase a live loan; a lost
loan can then never appear in a reminder because it no longer exists in the
data. The same command matches nothing silently on a typo, leaving a phantom
open loan that earns a false reminder note every day — the failure most
likely to destroy volunteer trust. Zoom-out and inventive lenses treat this
as out of scope to *fix* in this feature, but in scope to *surface*: the
overdue report should flag data problems (more than one open loan for a tool,
unreadable rows) in its own section rather than pretending the ledger is
clean.

### Two of the three open questions dissolve instead of being decided

* **"Is a loan due today late?"** A single boolean forces either false alarms
  or a lost day of lead time. Several lenses propose replacing the boolean
  with buckets: a `LATE` section sorted most-overdue first with days late
  shown, a `DUE TODAY` section, and the unreadable-rows section. The
  volunteer then decides whom to chase, where that decision lives today.
* **"Terminal text or note files?"** Note files go stale the moment another
  volunteer runs `lendr return` (yesterday's note accuses a member who
  returned the tool), add a second write path to a store with no locking and
  a non-atomic whole-file rewrite, need a naming scheme from unvalidated
  free-text member and tool names (a member recorded as `A/B` becomes a path
  outside the notes directory), and need a deletion story. Printed output is
  self-invalidating: it always reflects the current file. The lenses'
  position: v1 is strictly read-only and writes only to standard output; a
  volunteer who wants paper pipes or copies from the terminal.
* **"One command or two?"** One lens found a structural trap that makes this
  concrete: `cli.py` dispatches `list` in the catch-all `else` branch, so any
  new subcommand silently prints the ordinary open-loans list and looks like
  it works. Explicit per-command handlers are a precondition for adding a
  command at all. Beyond that, "one command" and "one code path" are
  different decisions: the lenses want exactly one lateness predicate and one
  renderer shared by `list` and any late view, because duplicated logic is
  how `list` and the new view start to disagree.

### The success metric measures the wrong thing

"Under ten seconds" is trivially met by any local script and says nothing
about the real defect, which is *omission*. One lens notes the baseline
"1 in 5 late" is not computable from the current schema at all (there is no
`loaned_on` or `returned_on`), so no version of this feature can show it
moved the number without a schema addition — which the compatibility
constraint blocks. The proposed honest metric: every open row is either
listed as late, listed as due today, or listed as unreadable, and the run
prints the path and date it checked. Whether the note text helps members
return tools is a human-workflow question the tool cannot measure.

### The daily habit the feature assumes is the habit that is missing

Comprehension and inventive lenses raise the same contradiction: the concept
assumes volunteers will run a check once a day, but the evidence ("late only
when someone asks") shows nobody checks systematically. A command that must
be remembered is a reminder whose activation depends on not needing one. The
cheapest resolution is preliminary action — attach the late count to the
transactions volunteers already perform, so any `lendr loan` or
`lendr return` prints "2 loans late — run `lendr late`" as a footer (kept in
a guard so a rendering bug can never break recording a loan). The related
prevention point: `lendr loan` prints nothing today, so the member never
hears the due date; echoing `member, tool, due <date>` at checkout is one
line and consistent with "the program sends nothing."

### Notes have no defined recipient or grouping

There is no member contact data by design, so a note can only be paper, a
spoken prompt, or text the volunteer pastes into a channel humans already
use — the concept does not say which, and lenses ask that it must. Grouping
by member is socially right (one late member with three tools deserves one
conversation) but `member` is unnormalized free text, so "Dana", "dana", and
"Dana R." split into competing notes; member accounts are out of scope, so
grouping must be an exact-string rule stated in the spec, or one line per
loan with the volunteer doing the grouping. An inventive detail worth
keeping: end each note entry with the literal `lendr return <tool>` line so
the note closes the loop at the moment the tool comes back, and include due
date and days late so the volunteer can point at facts if a member disputes
it. Also raised: a printed list of *people* who are late, left on a shared
counter, is a mild privacy event; a list of late *tools* is not.

### Naming and clock risks

A verb like `remind` reads as "a reminder was sent," which contradicts the
hard constraint and the existing grammar (`loan`, `return`, `list` are things
the operator does to the ledger); `late` or `overdue`, or a mode of `list`,
describes reading. Separately, lateness is now a function of the shared
laptop's clock, which on an offline machine never self-corrects: lenses
require the evaluation date printed on every run and an `--as-of` override
as the single time source, which also makes the boundary testable without a
test harness (the repo has none). Finally, backdating is unasked-about:
`lendr loan` can only express a future due date (`today + N`), so the moment
the report succeeds it creates pressure to record yesterday's loan as due in
the future, writing false "not late" rows. An optional `--due YYYY-MM-DD`
would fix the expressiveness gap but is arguably a second feature.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * Find every loan past its due date with one command, with a verification
    header (file read, rows, open/late counts, as-of date) that makes a
    clean empty result an evidenced claim.
  * Total row accounting: late / due today / needs-a-human sections; no
    silent skips, no tracebacks.
  * One shared lateness predicate and one renderer used by the late view and
    `lendr list` (or a `list` mode), so the two views cannot disagree.
  * Copyable reminder-note text on stdout, read-only, including days late
    and the literal `lendr return <tool>` line.
  * Data-problem flags (duplicate open loans for a tool, unreadable rows)
    surfaced in the report.
* **Out-of-Scope Non-Goals:**
  * Sending anything (email/SMS/push) — hard constraint.
  * Fines, member accounts, member normalization, contact data.
  * Note files with a lifecycle; program-side printing.
  * Reminder/"already chased" state in `loans.json` (a schema change the
    compatibility constraint forbids; the human is the log).
  * Fixing the pre-existing ledger hazards (close-all-matching return, no
    write locking, no loan id) beyond surfacing them; those are separate,
    larger changes.
  * Measuring the 1-in-5 rate (not computable from the current schema).
  * Performance machinery: a full scan and sort is sub-millisecond at this
    scale; SQLite, indexes, and caches are rejected.

## Alternatives Weighed

* **Note files written by the program** (`notes/` per loan or per member) —
  rejected by zoom-out, implementation-readiness, structural, inventive, and
  comprehension lenses on state grounds: stale after returns, second unguarded
  write path, unsafe filenames from free-text fields, undefined cleanup.
  `lendr late > notes.txt` (shell redirect) keeps the benefit with no new
  semantics; recorded as the rejected default so the choice is explicit.
* **`remind`/`reminder` as the command name** — rejected by the comprehension
  lens: promises delivery the program does not perform, breaks the
  operator-verb grammar of `loan`/`return`/`list`.
* **A brand-new subcommand bolted onto the current dispatcher** — blocked
  until dispatch is made explicit (zoom-out, structural): the catch-all
  `else` would make it print the unfiltered open list and look like it works.
* **Zero new commands: sort and annotate `lendr list` (or `list --late`)** —
  strongest competitor, raised by most lenses; reuses the daily habit, one
  code path, meets the detection goal outright. Held against only if the
  note-text requirement survives the open questions below.
* **SQLite / an overdue index / caching** — rejected: read path is three
  orders of magnitude inside any budget; unneeded complexity.
* **Tracking `reminded_on`/`returned_on` in `loans.json`** — rejected for v1
  (format-change risk, needs loan identity, the program must send nothing);
  optional `returned_on` is the only way to ever measure the 1-in-5 baseline,
  so it is deferred with that consequence stated, not forgotten.
* **Per-member note grouping with fuzzy name matching** — rejected: identity
  subsystem, explicitly out of scope; exact-string grouping or one-line-per-
  loan are the allowed options.

## Key Decisions & Staging for Next Steps

1. **Preconditions before any feature code (all carried into `/egm-draft`):**
   single data-path resolver with the resolved path echoed every run; loud
   failure (non-zero) on missing/corrupt file instead of an empty list;
   explicit per-command dispatch (no catch-all `else`).
2. **Core invariant:** the overdue view is a pure function of `loans.json`
   plus an as-of date. Read-only, stdout-only, no new state, no schema change,
   nothing sent. `--as-of` overrides the clock and is also the recovery path
   for a drifted laptop date.
3. **Buckets replace the boolean:** LATE (worst-first, days late shown),
   DUE TODAY (count; whether it earns note text is an open question), and an
   UNREADABLE/needs-a-human section. The due-today dispute is resolved by
   decomposition, not by picking an operator.
4. **One predicate, one renderer** shared by whatever forms the late view and
   `list` take; lateness is defined in exactly one place.
5. **Open for the requester to answer (blocking `/egm-draft` shape):**
   (a) what a volunteer concretely does with a note — paper at the counter,
   pasted into a group chat, or read aloud — and the grouping unit (per
   member with an exact-string rule, or per loan); (b) whether the discovery
   mechanism is a remembered command, the piggyback nudge on `loan`/`return`,
   or both; (c) whether prevention items (`loan` echoes the due date;
   due-tomorrow bucket; optional `--due` for backdating) ship together or are
   deferred; (d) whether the success metric is restated to "no manual date
   comparison, no missed loan" (recommended) and whether "under ten seconds"
   is kept only as a trivially-met floor; (e) is `loans.json` hand-edited
   today, and roughly how many rows does it hold?
6. **Documented known dependencies, not silently expanded:** close-all-rows-
   for-a-tool, silent no-match return, no loan identity, no locking, unbounded
   growth of returned rows. The feature surfaces their symptoms; fixing the
   causes is a separate proposal.
