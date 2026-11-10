# Overdue Reminders for lendr

* **Author:** Robin Fixture
* **Date:** 2026-11-09

## Overview

lendr is a small command-line loan tracker for the fictional Maple Hollow Tool Library. Three volunteers share one library laptop and run it by hand once a day. Today a volunteer runs `lendr list` and compares due dates by eye, which misses loans; about one loan in five comes back late. This feature adds an overdue view and a reminder-note output so a volunteer can find every late loan with one command in under ten seconds. It must stay offline, use only the Python standard library, keep the existing `loans.json` format working, and never send anything itself.

## Analysis

The concept is feasible and correctly constrained: it is a read-only filter over data lendr already has, needs no new dependency, and changes no persisted format. The reviewers found no blockers in the idea itself, but egm-codebase-details raised two Blockers against the existing store that the feature depends on: the working-directory-relative data path and the lack of error handling around malformed data. The rest of the risks are details the concept leaves open.

**1. The success measure and the two-command split disagree.** The concept says a volunteer finds every late loan "with one command", but it defines two commands. egm-zoom-out and egm-inventive-catalyst both flag this: the reminder command does not help find late loans, and with sending out of scope it is a manual-copy artifact for a workflow nobody has described. The Catalyst frames this as a contradiction between time-to-complete (one command) and output actionability (a ready-to-use note), and suggests Preliminary Action plus Inversion: precompute days late while listing and let the listing carry the note's full content, with the note as an optional formatting mode rather than a second required command. Secondary trade-off: a combined output is noisier for volunteers who only want the list, and a `--notes` flag couples the query and formatting paths. The Ideal Final Result is one invocation that prints every late loan with member, tool, due date, and days late in a form a volunteer can read or copy verbatim. This stays an open decision for the author.

**2. The data path is working-directory-relative, and the new commands will inherit it.** `store.py` resolves `loans.json` against the process working directory, while the README says the file lives next to the program. A volunteer who runs the new command from another directory gets a silent empty list, which fails the success measure with no error. egm-codebase-details rates this a Blocker; egm-design rates it Major and egm-structural rates it Nit. The Catalyst suggests Extraction: resolve the path once, anchored to the package or an explicit environment variable, and report a missing store loudly. The counter-argument (egm-implementation-readiness, egm-structural) is that the new commands must read exactly what the existing commands read, so the feature should reuse the store's path resolution and flag the README/code mismatch as a separate decision rather than silently changing where loans are found. Secondary trade-off: fixing the path changes where existing loans are found, so current users must migrate or be told.

**3. One malformed row can hide every late loan.** The store never validates dates, and the new commands must parse the `due` string. A hand-edited or truncated `loans.json` with a missing or non-ISO due date would raise inside `date.fromisoformat` and abort the whole command, so the volunteer sees zero late loans instead of every late loan. The reviewers converge on Beforehand Cushioning: validate each row, skip malformed rows with a warning on stderr, and never show a traceback. The parse rule and failure policy must be pinned in the brief. A related pre-existing risk: `_load` raises on malformed JSON, and `_save` truncates the file before writing, so a crash mid-write can destroy the only copy of the data. The feature does not introduce this, but its promise depends on the store surviving.

**4. The lateness rule is unpinned.** "Due date has passed" needs a boundary rule and a days-late formula. The reviewers recommend: a loan is late when `due < today` (a loan due today is not late), `days_late = (today - due).days`, using a single shared date helper so the `loan` and overdue paths cannot drift. The command should also expose an `--as-of`/`--today` override so results are reproducible and testable, and the printed note should carry the as-of date.

**5. The output contract is undefined.** The concept lists the note's fields but not their order, format, or the empty case. Blank output is indistinguishable from a broken command, an empty database, or a wrong directory. The reviewers recommend a concrete contract: one plain-text block per late loan, stable field order, sorted by days late descending then member name, a summary line such as "N open loans, M overdue", a friendly empty-state message ("No overdue loans."), and documented exit codes. The reminder note should be a complete, deliverable message (greeting, member, tool, due date, days late, closing) that a volunteer can read aloud or paste, with the volunteer as the delivery intermediary. Command names should match the existing verb style: `lendr overdue` and `lendr remind`. The README must be updated.

**6. Keep the lateness rule in one place.** Both commands must answer the same question. If each carries its own filter and date math, the outputs can drift and every future change to "late" must be made twice. The reviewers recommend a single shared pure function set (`overdue_loans(rows, today)` and `days_late(row, today)`) owned by a domain module, with the clock passed in as a parameter and defaulted only at the CLI boundary. Both commands should be thin dispatchers over it. The existing dispatch is also a trap: `cli.py` handles `list` with a catch-all `else`, so a forgotten branch would silently print all open loans for `lendr overdue`. The change should make the dispatch explicit.

**7. The read-only, stateless boundary must be explicit.** The feature's safety comes from never writing. The brief should state that both commands perform no writes of any kind: no new fields, no re-serialization, no schema version, no reminder history, no background jobs, no transport code, no new dependencies. If reminder history or sending is ever wanted, it is a separate feature with its own storage. The reviewers also say explicitly reject caching, indexing, async, and background processes: the ten-second measure is met by the simplest possible implementation, and an optimization layer would add state and failure modes to a tool whose virtue is being stateless and offline.

**8. Auditing and the late-rate metric are undecided.** The store records nothing beyond a `returned` flag, so after this feature ships there is still no way to verify the daily check happened, no way to know whether a reminder was already printed, and no way to track the "one loan in five" rate over time. egm-codebase-details asks the brief to decide between a minimal append-only local run log (timestamp, command, result count, resolved data path) and an explicit non-goal for usage and reminder auditing. Any audit trail must live outside `loans.json` and be local-only.

**9. Pre-existing store risks to note, not necessarily fix.** Non-atomic writes, no backup, no file locking, no input validation (`--days` accepts negative or zero), and no tests. These predate the feature. The brief should record them and decide whether they are in scope for this change or a separate hardening task.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * A command that lists every open loan whose due date has passed, showing member, tool, due date, and days late.
  * A command that prints a ready-to-use reminder note for each late loan.
  * A single shared lateness rule and date helper, with the clock injected for testing.
  * A defined output contract: fields, order, sort order, empty state, and exit codes.
  * Graceful handling of missing or malformed data, with no tracebacks.
  * Updated README and `--help` text.
  * Unit tests for the overdue filter and days-late arithmetic using fixed dates.
* **Out-of-Scope Non-Goals:**
  * Email or SMS sending, fines, and member accounts.
  * Changing the `loans.json` schema or adding fields such as `reminded_at`.
  * Caching, indexing, async, and background processes.
  * Fixing pre-existing store durability and locking, unless the author decides to include it.
  * Historical late-rate tracking and reminder auditing, unless the author chooses the run-log option.

## Alternatives Weighed

No alternative has been rejected by the author yet. The Goldfish review raised the following options; each is carried forward for the author's decision before drafting:

* **One command instead of two** (egm-zoom-out, egm-inventive-catalyst): collapse listing and reminder output into a single command, or add the note as a formatting mode on the listing command. Reason: the success measure says "one command", and a second command may be speculative scope.
* **Enhance `lendr list` instead of adding a subcommand** (egm-zoom-out): show lateness in the command volunteers already run. Reason: smaller surface area and no new habit for the volunteers.
* **Fix the working-directory-relative data path now, or keep it consistent and document it** (egm-design, egm-codebase-details, egm-structural, egm-inventive-catalyst): reason for fixing is silent empty results; reason for keeping is that the new commands must read the same file as the existing commands.
* **Skip malformed rows with a warning, or fail the command** (egm-comprehension, egm-implementation-readiness, egm-structural, egm-inventive-catalyst): reason for skipping is that one bad row should not hide every late loan; reason for failing is that silent skips can hide data corruption.
* **Minimal local run log, or an explicit non-goal for usage and reminder auditing** (egm-codebase-details): reason for the log is verification and dispute evidence; reason against is added state and scope.

## Key Decisions & Staging for Next Steps

Resolved by the author during clarification:

* Offline only; Python standard library only.
* The existing `loans.json` format must keep working.
* The program must not send anything itself.
* Email/SMS sending, fines, and member accounts are out of scope.
* Success measure: a volunteer finds every late loan with one command in under ten seconds.

Proposed for the author's confirmation before drafting:

* Lateness rule: a loan is late when `due < today`; `days_late = (today - due).days`; a loan due today is not late.
* Both new commands are strictly read-only: no writes, no new fields, no new files.
* One shared pure function set owns the lateness filter and date math; the clock is a parameter.
* Command names: `lendr overdue` and `lendr remind`, matching the existing verb style.
* Output: one plain-text block per late loan, sorted by days late descending then member name, with a summary line and a friendly empty-state message.

Open decisions the author still needs to make:

* One command or two (see Alternatives Weighed).
* Whether to fix the working-directory-relative data path in this change or defer it.
* Whether malformed rows are skipped with a warning or fail the command.
* Whether to add a minimal local run log or declare auditing a non-goal.
* Whether to harden the existing store (atomic writes, backup, locking, input validation) in this change or separately.

Next step: author review of this brief, then `egm-draft` for the formal design.
