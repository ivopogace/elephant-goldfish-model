# Overdue Reminders for lendr

* **Author:** Robin Fixture
* **Date:** 2026-11-10

## Overview

`lendr` is a small offline command-line loan tracker for the Maple Hollow Tool
Library, used by three volunteers on one shared laptop. About one loan in five
comes back late, and volunteers only learn a tool is late when another member
asks for it. Today a volunteer runs `lendr list` and compares due dates by eye,
which misses loans.

This feature adds one command that lists every open loan whose due date is
before today, read from the existing `loans.json`, and prints plain-text
reminder notes grouped by member that a volunteer carries to members by hand.
The tool sends nothing, runs offline, uses only the Python standard library, and
keeps existing data files working without changes.

The requester's success measure — find every late loan with one command in under
ten seconds — was challenged by several review lenses as measuring retrieval
speed that even today's `lendr list` already meets, while the actual problem is
a late loan first being discovered by the next borrower. See Analysis and Key
Decisions.

## Analysis

Seven review lenses (contrarian/YAGNI, resource economics, UX, migration and
compatibility, debuggability, maintenance/debt, inventive transforms) examined
the anchored concept. Their findings converge strongly on one point and diverge
usefully on scope.

### The feature's core is tiny; its trustworthiness is the work

The mechanics are about fifteen lines over the current code: read the JSON
list, keep rows that are open and have `due` before today, group by member,
print. At this scale — three volunteers typing a few times a day, roughly 1,800
loan rows per year, about 200 KB of file growth per year — parse, filter, and
sort take milliseconds. Performance work (caching, indexing, SQLite,
pagination, archiving) is noise here and was rejected outright.

What the lenses actually flagged, in severity order:

**1. False "all clear" is the blocker, and it already exists in the code.**
`store.PATH` is `pathlib.Path("loans.json")`, resolved from the *current
working directory*, and `_load()` returns an empty list when the file is
absent. So `lendr late` run from any other folder prints "nothing overdue" and
exits successfully without having looked at anything. Worse, `lendr loan` run
from the wrong folder *creates a second loans.json there*, silently splitting
the library's records. The README says the file lives "next to the program";
the code says otherwise, and three different people will discover that
difference three different ways. Every lens independently required the same
fix: the command must print the resolved absolute file path, the number of rows
read, and the number open, on every run; a missing file must be a loud error
with a non-zero exit; "nothing is late", "there are no loans", and "I could not
check" must be three different messages. Silence is never a valid result.

**2. The command turns a display field into load-bearing data.**
Nothing in today's code parses `due`; `list` prints it whatever it is. The new
command will be the first code in the project that interprets it, so it is also
the first that can crash or silently drop hand-edited rows: `"2026-11-5"`
(unpadded), `"March 4"`, `null`, a missing key. A traceback makes a volunteer
shrug and go back to eyeballing; silently skipping a row is exactly the missed
late loan this feature exists to prevent. The rule the lenses converged on:
parse defensively with `datetime.date.fromisoformat`, and list any row that
cannot be understood in a visible "could not check — inspect by hand" block.
Never abort, never drop. Two related facts must be decided, not inherited:
`fromisoformat` accepts more formats on Python 3.11+ than on 3.10 and earlier,
and the repo pins no version; and string-sorting `YYYY-MM-DD` is only correct
for well-formed dates, so validation comes before any sorting shortcut. The
same trap exists for `returned`: `open_loans()` uses truthiness, so a hand-typed
`"returned": "no"` marks the loan as returned and hides it forever — validate
that the value is a real boolean and surface anything that is not.

**3. The clock is a silent input.** An offline laptop has no time sync, and a
drifted or reset clock makes every answer wrong in either direction with
plausible-looking output. The command must print the date it used as today,
accept a `--today YYYY-MM-DD` override (which doubles as the test seam), and
optionally warn when the data file's modification timestamp is in the future,
which proves the clock is wrong.

**4. Pre-existing storage defects cap the feature's accuracy.** `close(tool)`
marks *every* open row with that tool name returned, so a duplicate tool name
can silently close a live loan (a missed late loan), and a typo'd
`lendr return` closes zero rows, exits 0, and leaves a ghost loan that prints
in every reminder note forever with an ever-older date. These are not caused by
this feature, but they break its promise. The lenses' position: do not rewrite
history in this change; make `return` report how many rows it closed and make
zero a loud error; flag "2 open rows for this tool — record looks wrong" in
output; and optionally separate implausibly old rows (for example due more than
about 180 days ago) into a "possibly stale, check by hand" section so the
actionable list stays honest.

**5. Statelessness survived attack and should be defended on purpose.** The
contrarian and inventive lenses pushed hardest here and the verdict held: no
per-loan reminder records, no sidecar file, no version marker. The technical
reasons: there is no loan id, so any sidecar key ((member, tool, due)) collides
on re-loans and breaks the moment a volunteer hand-edits a due date; a stale
sidecar entry silently suppresses a reminder, which is the dangerous direction
of error; writing state turns a read-only daily poke into a mutation of the one
shared file; and output that changes depending on whether you ran the command
already is maddening for the volunteer. Rollback cost of a stateless, read-only
command is zero: delete the code, the file is unchanged. The one cheap
compromise kept as a future option is a single "last swept on <date>" marker —
one calendar value, delete-it-and-everything-is-noisier safe — to be revisited
only if duplicate nagging actually bothers members. A related decision costs
one sentence: old files already load with zero changes because unknown keys are
ignored and preserved, so the only rule to write down is *readers must never
require a new key*.

**6. Notes are text to act from, not letters.** There is no member contact data
and the tool must not send anything, so the artifact is a screen a volunteer
transcribes or prints. The lenses demand that it survive that: member-grouped
(one block per person, because the name is copied once), groups ordered by
their most overdue loan and worst-first within the group, ties broken so two
runs on the same day produce byte-identical text (the volunteer ticks off paper
against it), days-late counts next to the date instead of forcing mental
arithmetic, a one-line count summary at the top ("3 overdue across 2 members,
checked 11 open loans in /path/to/loans.json"), and one self-contained,
paste-safe line per loan with no color and no padding that shatters in a text
editor. Never truncate the list — a summary that hides rows is the same lie as
the missing file. A labelled "Due today — not overdue yet" section sits below,
because "strictly before today" otherwise leaves an invisible hole: three tools
due today print nothing under a name that promises everything late. Do not
write a `REMINDERS.txt` for the volunteer; a saved note goes stale silently,
and the dated header plus shell redirection already covers carrying it.

**7. Naming and shape: `lendr late`, a subcommand, not a flag.** Flags are not
discoverable by people who don't know flags exist; a second subcommand matches
the existing structure and keeps `lendr list` byte-for-byte unchanged for
volunteers with muscle memory. `remind` was rejected outright: it is a verb
that implies the tool sent something, which the hard constraint forbids —
a volunteer must never be unsure whether a note went out by itself. Use
`late` with `overdue` as an alias. The drift risk of a second code path (the
contrarian's argument for a flag) is resolved structurally: one predicate
module that both `list`'s late marker (if added later) and `late` call.

**8. Where the logic lives, so it does not rot.** A small `rules` (or
`policy`) module holding `parse_due`, `is_overdue(row, today)`, and the grouping
function, with `today` passed in as a parameter and captured once per run, not
called per row. `store` stays persistence and does not start owning semantics.
The if/elif/else dispatch in `cli.py` where `else` means `list` should become
explicit per-branch handling, so a typo cannot render the wrong view. Exit
convention defined now: 0 means the check ran (even with overdue rows found),
non-zero means it could not check, 2 is usage.

**9. Tests are the anti-rot mechanism.** Today there are none, and "the old
format keeps working" is currently an untested assertion. Minimum standard
library `unittest` set: the boundary trio (due yesterday is late, due today is
not, due tomorrow is not) with an injected date; a committed golden fixture of
the current row format that loads unchanged; three distinct asserted outputs
for missing file, empty file, and nothing-late; one malformed-due row reported
by position while other rows are still evaluated; byte-deterministic output.
Keep the current detail that `_load`/`_save` read the module-global `PATH` at
call time — it is the seam that lets tests point at a temp file.

**10. Invocation does not actually exist yet.** There is no `lendr` executable,
no entry point, no `pyproject.toml`, and no `__main__.py`, yet the README tells
volunteers to type `lendr loan ...`. Until how the program is started is
decided, the data file lands wherever the shell happened to be, which feeds
finding 1. Fixing the README (or adding a trivial entry point) is part of
making the "one command" measure mean anything.

**11. One safety fix worth bundling.** `_save` truncates and rewrites the whole
file in one step; an interrupted write (Ctrl-C, disk full) destroys the entire
loan history, and there are no backups. Writing to a temp file and renaming
over it (`os.replace`) is about three lines, keeps the format identical, and is
taken for crash-safety — not for concurrency, which at three people on one
laptop was calculated at roughly one collision per millennium and had locking
explicitly rejected.

### The inventive layer

The true contradictions the concept accepted as inevitable: lateness must reach
the volunteer without being sought, yet the program has no delivery path; and
avoiding double-nagging needs memory, yet the file must not change. The
resolved forms of these, kept as post-v1 options rather than scope creep:
*inversion* — piggyback one line after `lendr loan` / `lendr return` ("3 loans
are overdue. Run: lendr late"), so the report attaches to the transaction that
already happens daily instead of needing a habit that failed; *self-service* —
the dated stdout listing is already a redirectable artifact; *cheap
dispensable* — the single last-swept date marker; *dynamics* — urgency bands
(due today / 1–6 late / 7+ late) as pure derived views, never stored, since a
stored band goes stale while a computed one can't; and reframing the report as
availability ("what can I lend tonight") rather than delinquency, which changes
the social tone of the notes without changing the data.

**Ideal Final Result:** a late loan reports itself at the moment the volunteer
is already at the keyboard, on a sheet that dates itself, needs no memory and
no records to run honestly — the entire state being at most one calendar date —
while `loans.json` is never touched and the program never speaks.

## Goals vs. Non-Goals

* **In-scope goals:**
  * `lendr late` (alias `overdue`): a read-only subcommand listing every open
    loan with due date strictly before today, from the existing `loans.json`.
  * Member-grouped, ordered, deterministic reminder notes on stdout with days
    late, a due-today section, a could-not-check section for bad rows, and a
    summary header naming the file it read, the date used as today, and counts.
  * Distinct loud output and non-zero exit for: missing file, unreadable file,
    nothing open, nothing late. Never silence.
  * `--today` override; shared rules module with the overdue predicate.
  * Stdlib `unittest` suite: boundary trio, golden old-format fixture,
    distinct error-state outputs, determinism.
  * Bundled safety fixes: atomic save (temp + `os.replace`); `lendr return`
    reports how many rows it closed and treats zero as a loud error; README
    corrected for file location and invocation.
  * Documented manual-edit recipe for hand-fixing ghost or duplicate rows.
* **Out-of-scope non-goals (intentional):**
  * Sending anything: no email, SMS, or network of any kind.
  * Reminders state: no per-loan reminded flags, no sidecar history, no
    suppression of repeat listings — "asked already" lives on paper.
  * No scheduler, daemon, or automatic runs.
  * No member accounts, contact data, fines, or escalation tiers.
  * No stored note files, print layouts, or templates.
  * No SQLite, indexes, caching, locking, or data archiving/compaction.
  * No fuzzy matching of member names; no rewriting or normalizing stored data.
  * No pre-due prediction beyond the labelled due-today section.
  * No change to the `loans.json` format, required or optional, in this round.

## Alternatives Weighed

* **Do only this: sort `lendr list` by due date.** Rejected by review as the
  whole answer, but kept as a real fallback with a kill criterion: count the
  open loans first (under about twenty, sorting may already deliver "no late
  loan first discovered by the next borrower"); if a trial of sorted `list`
  meets that outcome, the filter command should not be built. The requester
  should decide whether to trial this before drafting.
* **`lendr list --late` flag instead of a subcommand.** Rejected by review:
  not discoverable for non-programmers, and it changes the byte-for-byte output
  of a command volunteers navigate by habit; the drift concern it was meant to
  avoid is instead handled by one shared predicate module.
* **Naming it `lendr remind`.** Rejected by review: the name claims an action
  (sending reminders) that the hard constraints forbid, and would leave
  volunteers unsure whether anything was actually sent.
* **Per-loan reminder state in `loans.json` (`last_reminded` key).** Rejected
  by review: old readers tolerate extra keys, but writing it turns a read-only
  command into a writer of the shared file, makes output depend on past runs,
  needs clearing rules on return, and retains contact-attempt records about
  named people on an unadministered laptop. Kept trigger: revisit only if
  duplicate reminders start bothering members.
* **A separate reminders sidecar (JSONL or sqlite3).** Rejected by review: no
  stable loan id exists to key on; (member, tool, due) collides on re-loans and
  breaks on hand-edited dates; a stale entry silently suppresses a reminder —
  the worst failure direction. The discounted version (single last-swept date
  marker) is kept as a post-v1 option.
* **Version marker or `{"version": 1, "loans": [...]}` wrapper.** Rejected by
  review: the top level is a bare list, so there is no non-breaking place for a
  marker; the wrapper breaks old lendr reads and buys nothing, since lateness
  is derivable from existing fields.
* **File locking or concurrency design.** Rejected by review as premature
  (collision odds about once per millennium at this usage). Atomic temp+rename
  writing is taken instead, for crash safety, not concurrency.
* **SQLite, indexes, caching, pagination, compaction/rotation of
  loans.json.** Rejected by review with arithmetic: the design stays
  comfortably fast for decades; none of these address any real failure mode.
* **Writing a `REMINDERS.txt` as the deliverable.** Rejected by review: a
  second source of truth that goes stale invisibly; the dated stdout listing,
  redirectable if a paper copy is wanted, replaces it.
* **Fuzzy member-name matching for grouping.** Rejected by review: can accuse
  one member of another member's tools. Casefold/strip grouping that displays
  the recorded spellings and flags "possible duplicate names" is taken instead.
* **Truncating or summarizing away long overdue lists.** Rejected by review:
  the promise is *every* late loan; the header count and member grouping manage
  the scanning time.
* **Urgency bands with pre-due notices (due in ≤ 3 days).** Held as a future
  option, not v1: predicted by review to be offered as the obvious next step
  and refused until a volunteer asks for it; social cost of early nagging in a
  member co-op noted.

## Key Decisions & Staging for Next Steps

1. **Late means due date strictly before today**, with a clearly labelled
   due-today section printed below so the strict boundary never creates an
   invisible hole. (Requester default confirmed; lenses attacked the invisibility, not the rule.)
2. **v1 is stateless and read-only.** "No reminder state" is recorded as a
   deliberate permanent non-goal with a revisit trigger (duplicate nagging
   bothers members), so a later contributor does not add a flag as a favor.
3. **Output contract over machine speed.** The ten-second measure is restated:
   the machine will respond in milliseconds; the ten-second budget is spent on
   the header line answering "how bad, who first, did it actually look." The
   outcome measure for keeping the feature is: no late loan is first discovered
   by the next borrower.
4. **Structure:** new `lendr late` subcommand sharing one rules module with an
   injected `today`; `list` output unchanged this round; per-branch CLI
   dispatch; exit 0 = checked, non-zero = could not check.
5. **Validation rules:** `due` must parse as strict ISO via `fromisoformat`,
   `returned` must be a real boolean; anything else is printed in a
   could-not-check block, never dropped or fatal. A minimum Python version is
   declared and the accepted date format documented.
6. **Grouping:** casefold-and-strip grouping by member name, worst-loan-first
   group order, deterministic ties, alternate spellings shown, blank member
   bucketed as "unknown member".
7. **Bundled safety fixes:** atomic save; `return` reports rows closed and
   errors on zero; README corrected for the real file location and actual
   invocation. If the requester wants an even smaller first cut, this is the
   list to trim, and the false-all-clear mitigations are not.
8. **Pre-draft action:** count typical open loans; if very small, consider the
   sorted-`list` trial (Alternative 1) before committing to the new command.
9. **Carried to draft as options, not scope:** the piggyback "N loans are
   overdue — run lendr late" line after `loan`/`return` (watch piped-stdout
   pollution); the last-swept-date marker; the loan-time paper slip; the
   availability ("lendr free") reframing; urgency bands.
10. **Open question for draft:** the long-term home of `loans.json` (fixed data
    directory vs. current working directory with loud-path mitigation). v1
    mitigates and documents; it does not move anyone's file.
