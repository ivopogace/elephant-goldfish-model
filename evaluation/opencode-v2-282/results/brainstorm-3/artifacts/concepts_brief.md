# Overdue Reminders for lendr

* **Author:** Robin Fixture
* **Date:** 2026-11-09

## Overview

lendr is a small offline command-line loan tracker for the fictional Maple Hollow Tool Library. Volunteers currently find out a tool is late only when another member asks for it, by comparing the dates in `lendr list` with today by eye. About one loan in five comes back late, so the manual check misses loans.

This feature adds a `lendr overdue` command that lists every open loan whose due date has passed, oldest first, with the number of days late. An optional `--remind` flag writes one plain-text reminder note per late member into a `reminders/` folder, ready to print or paste into an email. The program still never sends anything itself.

The target users are three volunteers who share one library laptop and run lendr by hand about once a day. There is no SLA. The feature must run offline, use only the Python standard library, and keep the existing `loans.json` format working.

## Analysis

Seven Goldfish reviewers examined the concept and the existing draft at `docs/designs/overdue_reminders.md`. The listing half of the feature is sound and cheap. The risks cluster in the `--remind` half and in unspecified edge behavior. The findings below are deduplicated.

**The `--remind` freshness claim is false as written.** The draft says existing reminder files are overwritten "so the folder always reflects the current state." Overwriting only updates files for members who are late right now. A member who returned a tool keeps the old `reminders/<member>.txt`, so a volunteer who prints the folder can send a reminder for a loan that is already closed. That is the exact failure the feature exists to prevent, reintroduced as stored derived state. The folder must be reconciled: rebuild it each run, delete files for members with no current late loan, or build into a temp folder and swap it into place. The claim must be made true or removed. A test must cover the returned-member case.

**Member names make unsafe filenames.** The draft only rejects names containing `/`. Unhandled cases include `..` and `.`, empty names, control characters, names longer than the filesystem limit, Windows reserved names, and case-insensitive collisions ("Ann" vs "ann" silently overwrite each other's notes). A collision loses one member's reminder. The fix is a tested filename policy: reject or slugify unsafe characters, cap length, case-fold and detect collisions, and decide whether a bad name aborts the run or skips that member with a reported error. The longer-term fix is a stable member key in the schema, kept separate from the display name.

**Path resolution is ambiguous and contradicts the README.** `store.PATH` is `pathlib.Path("loans.json")`, resolved against the current working directory, while the README says loans live "next to the program." The draft says `reminders/` without saying where. A volunteer running lendr from another directory gets an empty result with exit 0 and creates a reminders folder in the wrong place, or silently operates on a different `loans.json`. The base directory must be pinned and shared by `loans.json` and `reminders/`, the missing-file behavior defined, and the README corrected.

**Data validation and error behavior are unspecified.** `store.open_loans()` returns raw rows and never validates them. `late_loans()` must parse `due`, so a hand-edited or legacy row with `"11/02/2026"`, `null`, or a missing key raises a traceback and aborts the whole command. A legacy `"returned": "false"` string is treated as returned and silently vanishes. The row contract (`member: str`, `tool: str`, `due: ISO YYYY-MM-DD`, `returned: bool`) must be pinned, and the failure behavior chosen: fail fast with an error naming the member and tool, or skip the row with a stderr warning. The same applies to an unwritable or missing `reminders/` folder, a plain file named `reminders`, permission errors, and a full disk.

**The output and exit-code contract is unspecified, and stdout is a de facto API.** A volunteer script already parses `lendr list` output, so stdout stability matters. The draft does not define exit codes, the empty-result message, whether `--remind` still prints the late-loan list, or what a volunteer sees on success. The command should print the reference date and its source once per run, emit a summary with counts, keep stdout stable and machine-readable, and return non-zero on any data or write failure. Ties on the same due date need a deterministic secondary key.

**Scope: the listing alone meets the success criterion.** The stated success is "a volunteer finds every late loan with one command in under ten seconds." `lendr overdue` does that. `--remind` is a second workflow with no evidence of demand, and it imports filesystem state, overwrite semantics, and filename sanitization. One option is to ship `lendr overdue` first and validate whether printed notes are wanted; if they are, print them to stdout grouped by member, or put file output in a separate feature. This brief keeps `--remind` in scope because the author asked for reminder notes, but the staging decision belongs in `/egm-draft`.

**The success metric measures command latency, not discovery latency.** The real pain is that nobody checks proactively. A faster command still depends on a volunteer remembering to run it. One inventive resolution is to invert the trigger: print a one-line "N late loan(s)" notice to stderr on every `lendr` invocation, leaving stdout byte-identical so the counting script keeps working. Discovery then becomes a side effect of the existing daily habit, and `lendr overdue` remains the on-demand detailed view. A scheduled trigger (cron or shell-profile hook) is the alternative, at the cost of one operational artifact that can silently fail.

**Secondary trade-offs.** Writes should be atomic (temp file plus `os.replace`) so a volunteer printing mid-write never sees a partial note, and so two simultaneous runs cannot interleave. Generation should be two-phase: validate every note in memory first, then write, so a failure does not leave a half-built folder. Overwriting destroys volunteer edits, so notes need a backup, a confirmation, or an "auto-generated, edits lost on next run" header. `reminders/` will appear as untracked files containing member names, so `.gitignore` needs a decision. Returned loans are never pruned, so `loans.json` grows forever; an archive or prune strategy should be recorded as a later concern. The ten-second success criterion should become an explicit, testable acceptance criterion.

**Ideal Final Result.** A volunteer learns that late loans exist as a byproduct of their existing daily habit, with no new command to remember. When they want detail, `lendr overdue` lists every late loan in under ten seconds. If they ask for notes, `reminders/` contains exactly the current late members' notes and nothing else after each run, every note shows the member's real name and the reference date, and no note can be mistaken for a current one.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * `lendr overdue` lists every open loan whose due date is strictly before today, oldest first, with days late.
  * `--remind` writes one plain-text reminder note per late member into a `reminders/` folder, reconciled to the current late set.
  * The reminder note template, output line format, exit codes, and error messages are pinned.
  * Works offline, standard library only, no change to `loans.json`, never sends anything.
  * Success is measurable: a volunteer finds every late loan with one command in under ten seconds.
* **Out-of-Scope Non-Goals:**
  * Sending email or text messages.
  * Fines, member accounts, or a tool catalogue.
  * Changing the storage format or pruning `loans.json`.
  * Changing the default output of `lendr list` (a volunteer script counts loans from it).
  * Scheduled or background sending; no network access.

## Alternatives Weighed

* **Mark late loans inside `lendr list`.** Rejected by author: volunteers asked for a short list of only the late loans, and changing the `list` output would break a script one volunteer uses to count loans. Reviewers noted an opt-in `lendr list --late` filter would leave the default output unchanged; this is recorded for `/egm-draft` to decide, not rejected.
* **Send email directly.** Rejected by author: the library laptop has no mail account, and storing member email addresses is out of scope.
* **Print reminder notes to stdout grouped by member.** Weighed during ideation: it removes filesystem state, overwrite rules, and filename sanitization. Not adopted here because the author asked for notes as files; recorded as a fallback if `--remind` is cut.
* **Defer `--remind` and ship `lendr overdue` first.** Weighed during ideation: the listing alone meets the success criterion, and `--remind` adds a class of new problems. Not rejected; staged as a possible second phase.
* **Keep `--today` on the CLI.** Weighed during ideation: tests can pass the date directly to `late_loans(rows, today)`, so the flag is speculative surface. If it stays, it must be documented, validated, and stamped into every note.
* **Use member names directly as filenames.** Rejected during ideation: rejecting `/` alone leaves path traversal, empty names, collisions, and platform-specific characters open. A tested filename policy is required.

## Key Decisions & Staging for Next Steps

* `lendr overdue` is the primary interface. `/egm-draft` should decide whether `lendr list --late` is the primary filter with `overdue` as an alias, or whether the new subcommand stands.
* `--remind` stays in scope, but its folder must be reconciled each run and its filenames must go through a tested safety policy.
* The note template, output format, exit codes, error behavior, and path-resolution rule must be pinned in `/egm-draft`.
* The ten-second success criterion must become an explicit acceptance criterion with a measurement method.
* A possible later phase is a stderr "N late loan(s)" notice on every `lendr` invocation, leaving stdout unchanged.
* Next step: run `/egm-draft` on this brief.
