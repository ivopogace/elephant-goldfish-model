# Overdue reminders for lendr

* **Author:** Robin Fixture
* **Date:** 2026-11-10

## Overview

Volunteers at the Maple Hollow Tool Library record loans with `lendr loan`, close
them with `lendr return`, and read them with `lendr list`. Three volunteers share
one laptop and run the tool by hand about once a day. Today they find a late loan
by reading `lendr list` and comparing due dates by eye, and they miss some; a late
tool usually surfaces only when another member asks to borrow it. About one loan
in five comes back late.

The concept is a read-only command that lists every open loan whose due date has
passed, showing member, tool, due date and how many days late it is, plus an option
that prints plain-text reminder notes a volunteer delivers by hand. It stays
offline and standard-library only, sends nothing, and leaves `loans.json` in its
current shape. Success means one command finds every late loan in under ten
seconds.

Seven reviewers examined the concept against the actual code (26 lines in
`cli.py`, 31 in `store.py`). The verdict: the feature is cheap to build but its
success criterion is currently unprovable, one existing line of code would make a
new command silently print the wrong thing, and the "reminder note" is the least
defined object in the design. Two reviewers also argued the concept is aimed at
the step that is already nearly free, and that the due-date habit at loan time
deserves attention first.

## Analysis

### The success criterion cannot be met or checked as written

The concept says "find every late loan". Three separate defects make that claim
false or untestable, and reviewers converged on them independently.

**Coverage.** `store.py:5` sets `PATH = pathlib.Path("loans.json")`, resolved
against the current working directory, while `README.md:10` says loans live "next
to the program". `_load()` returns `[]` when the file is missing. A volunteer who
runs the command from a desktop shortcut or their home directory gets a calm,
empty, exit-code-0 answer for a data file that was never opened. Since the whole
point is to find loans that would otherwise be missed, a silent false negative is
worse than today's manual scan: it replaces "we might have missed one" with "the
computer says none". Several reviewers rated this a blocker and asked for the
command to print the resolved file path and the number of open rows it scanned on
every run, and to fail with a non-zero exit and a message when the file is absent
rather than reporting zero.

**Definition.** "Past its due date" is not pinned at the boundary. `due` is a
whole calendar date (`cli.py:20-21`), so a loan due today is the daily edge case,
not an exotic one, and `--days 0` already makes such rows. Reviewers asked for one
predicate: late if and only if `today > due`; `days_late = (today - due).days`,
never below 1; due today does not appear. They also want the as-of date printed in
the output so a wrong laptop clock is visible rather than silently shifting every
number and every note.

**Dispatch.** `cli.py:19-26` dispatches with `if loan / elif return / else: print
list`. Adding an `overdue` subparser without changing that structure routes
`lendr overdue` into the `list` branch: exit code 0, plausible open loans, nothing
about lateness. This is a concrete trap in the existing code, and the same trap
awaits the next command after this one. Reviewers asked for explicit per-command
dispatch with no fallback branch, plus a test that the new command's output differs
from `list` on a fixture that contains late loans.

**Verification.** There is no test suite, no fixture, no packaging file, no
`__main__.py`, and no `if __name__ == "__main__"` in `cli.py`, so nothing in the
project can currently be run as `lendr` without also setting the import path. The
ten-second target is met with enormous margin by a single linear filter over a
small JSON file (order hundreds of rows per year), which makes latency the least
interesting property of the design. The interesting property is completeness, and
completeness needs fixtures with hand-written expected answers: a row due
yesterday, today and tomorrow; returned and open rows; a malformed `due`; duplicate
open rows for the same tool; an absent file; an empty file; a non-ASCII name.

### "Reminder note" is the least defined object, and the data cannot address a borrower

There is no contact information anywhere in the record: only a free-text `member`
string, `tool`, `due`, `returned`. Email, SMS, fines and member accounts are out of
scope by the author's decision, and the program must not send anything itself. So a
note can only contain the member string as typed, the tool, the due date, days late
and a generation date, and it can only be delivered by a volunteer who already
knows how to reach that person. Reviewers asked for a literal sample note in the
design, a stated sink (stdout, with the volunteer choosing to print or copy), and a
decision on the empty case: silence must not be the "nothing is late" answer.

One reviewer pressed the harder question: what carries the note after it is
printed? If the contact route is a paper membership binder or a volunteer's memory,
then the reminder feature's value depends on a system that is not in this
repository, and that assumption should be written down rather than implied.

Note granularity is unresolved and reviewers split on it. One note per loan keeps
every note tied to exactly one row and needs no interpretation of the member
string. One note per member, listing all their late tools, needs less human
carrying and matches how a phone call works, but requires grouping on a free-text
name where "Ana" and "Ana Ruiz" are different keys and two different people can
share one name. Both are defensible; the brief cannot decide it for the author.
Reviewers agreed that whatever is chosen must be stated in one place, and that
`member` must be treated as an opaque display label — printed, never normalised,
joined on, or used to look anything up — or the out-of-scope member-accounts
feature arrives through this door.

### Identity and the inherited `return` defect

`store.add` appends an anonymous row and `store.close` loops over every row,
setting `returned = True` on each open row whose tool matches, with no `break`
(`store.py:22-27`). One `lendr return hammer` can therefore close two members'
loans, and a genuinely late loan disappears from `open_loans()` and from the new
report. Tool names are not unique, there is no loan identifier, and matching is
exact string equality, so case differences leave rows open that were returned.
Reviewers were consistent that fixing this is a separate change: it touches the
only mutation path all three volunteers use, and it could surface previously
mis-closed loans as newly late. The concept must state its dependency instead of
inheriting the defect silently. Adding identifiers or a `reminded` field to
`loans.json` was rejected: it breaks the format constraint, `_save` rewrites the
whole file non-atomically, and derived lateness goes stale the way `returned`
already demonstrates.

### The concept may be aimed at the wrong step

Detection is already nearly free: `lendr list` prints every open loan and a late
one is a due date in the past. One reviewer noted that a success criterion defined
as a latency bound on a non-bottleneck is a sign of a mis-framed problem, and
proposed the smallest alternative: sort `list` by due date and mark past-due rows,
about three lines, with no new subcommand. The counter-argument is real — a mixed
list is noisy at the desk — but that is the volunteers' call after using the sorted
list once.

Two further levers were raised and are worth a decision before drafting:

* **Due dates chosen at loan time.** `--days` defaults to 7 for every tool, and a
  volunteer under time pressure takes the default. A 20 percent late rate is at
  least as consistent with unrealistic due dates as with forgetful members. One
  reviewer suggested one sentence at the desk ("due back 17 Nov") using a value the
  code already computes and currently discards; another suggested watching three
  real loans being recorded before building any report.
* **A "due soon" bucket.** The same one-pass filter can print loans due within N
  days alongside overdue ones. It is socially cheaper and may move the rate more
  than a post-hoc list, at the cost of a second comparison and a second decision.

One reviewer also proposed a sanity check before any code: run the existing `list`
once and compare it against the shelves. If the bookkeeping is already stale, a new
report will burn volunteer trust on phone calls about tools that are on the shelf,
and the higher-leverage fix is at the check-in desk.

### Where the structure should go

Reviewers converged on a seam: one I/O-free module (for example
`lendr/overdue.py`) exporting a pure function that takes open rows and an as-of
date and returns records carrying `days_late`. `store.py` stays the persistence
boundary and never reads a clock; `cli.py` reads the clock once, calls the view,
picks a renderer, prints. Lateness must be defined once — otherwise the listing and
the note text will disagree on the boundary case within one iteration — and the
overdue set must be a view over `open_loans()`, not a second query over the raw
file that re-tests `returned`. No output mode should reload `loans.json`, since a
return recorded between two reads produces notes for loans the listing calls closed.
The display fields should be declared once so `list` and `overdue` differ only in
row set and the extra column.

Robustness of the read path matters more than usual because three people hand-edit
one file. `open_loans()` indexes `row["returned"]` directly and `json.loads` errors
are uncaught; a single malformed row or a truncated file aborts the whole run with
a traceback. Reviewers asked for per-row isolation: unreadable rows reported on
stderr with their position in the file, the remaining late loans still listed, a
non-zero exit and a one-line summary, with notes on stdout kept clean. They also
asked for UTF-8 on read, a locale-independent sort key, and a check that `returned`
is a JSON boolean rather than a truthy string.

### Contradictions and the ideal result

The inventive lens named three contradictions and resolved them without new
machinery. First, "must not send" versus "the borrower is not told": the
resolution is to extract transport from the program entirely — it authors a
sentence, a person who is already present carries it — and to issue the cheapest
reminder at the desk, when the due date is set. Second, "a short list" versus
"confidence that the list is complete": never print silence; every run states the
resolved path, the file's modification time, how many open rows were scanned, how
many are late, and today's date, so "nothing late" is a positive claim with a
denominator. Third, "fast answers" versus "the format cannot change": lateness is a
projection computed at read time from the stored ISO date, never stored.

The ideal result: the volunteer types one command, sees one dated and self-checking
report, and carries away a note that needed no authoring effort — while the
upstream reminder, the spoken due date at the desk, quietly reduces how many notes
are needed at all.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * One command that lists every open loan past its due date, with member, tool,
    due date and days late, given an as-of date supplied once per run.
  * A plain-text note output that a volunteer prints or copies and delivers by
    hand, with a stated template, sink (stdout) and empty-case behaviour.
  * Deterministic ordering, so the same data always prints the same sequence.
  * A coverage line on every run: resolved `loans.json` path, open rows scanned,
    late rows found, as-of date.
  * Explicit per-command dispatch, replacing the current `else` fallback.
  * A read-only change: no new fields, no writes to `loans.json`, no migration.
  * Standard-library tests with checked-in fixtures and expected output, including
    the boundary cases above.
  * A documented way to run the tool, so "one command" is a real command.

* **Out-of-Scope Non-Goals:**
  * Sending email, SMS, or any outbound message; any network or send-capable
    import. (Author decision.)
  * Fines and member accounts. (Author decision.)
  * Storing borrower contact details or looking up members.
  * Recording that a reminder was produced, or any reminder history: the feature
    is stateless and re-emits notes while a loan stays late.
  * Loan identifiers or any change to the `loans.json` schema.
  * Changing `return`, `list`, `open_loans()` or path resolution semantics in the
    same change; the `return`-closes-multiple defect is recorded as a dependency.
  * A scheduler, daemon, cache, index, database, template file or note directory.
  * Per-member grouping by any stored or normalised key.

## Alternatives Weighed

* **Send reminders directly (email/SMS).** Rejected by author: the program must
  not send anything, and the setting is offline.
* **Fines and member accounts.** Rejected by author: out of scope.
* **Persist "reminder already sent" on the loan row.** Rejected in brainstorm: no
  loan identity to key it on, `_save` rewrites the whole file without atomic
  replace, and stored lateness or reminder state goes stale — the existing
  `returned` flag already shows that failure mode. It also breaks the constraint
  that existing `loans.json` files keep working.
* **A separate `overdue_loans()` query in `store.py`.** Rejected in brainstorm: it
  creates a second definition of "open" beside `open_loans()`, and the two drift
  as soon as row shape changes.
* **A second reload of `loans.json` for the note path.** Rejected in brainstorm: a
  return recorded between the two reads yields notes for loans the listing reports
  as closed.
* **Write notes to files beside the program.** Rejected in brainstorm: unrequested
  side-effect state on a shared laptop, with unspecified naming, overwrite and
  stale-content rules, and member names left on disk in whatever directory the
  volunteer happened to use.
* **Add a schema version key or normalise `due` on load.** Rejected in
  brainstorm: violates the format constraint, creates an irreversible migration
  with no backup, and turns a read-only feature into a writer.
* **Cache or index the data.** Rejected in brainstorm: latency is already met by
  three orders of magnitude, and the cache would recreate the staleness problem.
* **Sort `list` and mark past-due rows instead of adding a command.** Not rejected;
  recorded as the smallest alternative if the volunteers find a mixed list
  sufficient. Awaiting the author's decision.
* **A "due soon" bucket and a spoken due date at the desk.** Not rejected; recorded
  as upstream levers that may matter more than the report itself. Awaiting the
  author's decision.

## Key Decisions & Staging for Next Steps

1. **Read-only, format-frozen.** The change adds no fields and performs no writes.
   Reminder history is out of scope with the reasons above recorded, not left open.
2. **One definition of late.** `today > due`; `days_late` at least 1; due today is
   not late; the as-of date is one injectable value used by filtering, output and
   tests; production default is the laptop's local date.
3. **Coverage over silence.** Missing or unreadable `loans.json` is an error with a
   non-zero exit; the normal case prints path, open count, late count and as-of
   date; the empty case prints a sentence, not nothing.
4. **Explicit dispatch.** Every subcommand gets its own branch or handler; the
   `else` fallback is removed before the new command is added.
5. **One seam.** A new I/O-free module owns lateness and `days_late`; the overdue
   set is a view over `open_loans()`; display fields are declared once.
6. **Note template and granularity.** A literal sample note belongs in the draft.
   The author still has to choose one note per loan (simplest, no member
   interpretation) or one note per member (fewer slips, grouping on a free-text
   name). This is the one decision the brainstorm could not make for the author.
7. **Verification.** Standard-library `unittest` with fixtures, golden output, a
   reconciliation invariant against `list`, and a documented single command to run
   it. The ten-second target is recorded as already met, not as a design goal.
8. **Run contract.** A documented invocation (`python -m lendr` with a
   `__main__.py`, or an equivalent console script) must exist, because today
   nothing in the project can be run as `lendr`.
9. **Open for the author:** whether to ship the report at all before checking the
   shelves against `list`; whether to add the "due soon" bucket; whether to change
   the `--days` default or surface the due date at the desk.
10. **Author position recorded 2026-11-10:** the author read this brief, accepted
    the findings above as documented risks, and kept the scope unchanged. No
    finding was withdrawn. The note-granularity choice in item 6 and the open
    alternatives in item 9 carry forward to drafting as decisions, not as defects.
