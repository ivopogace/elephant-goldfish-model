# Goldfish Review Report — Stage 8 (Intermediate Zoom Out)

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (full file, lines 1–74)

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-zoom-out` | completed |

## Verdict

The design does not pass the Zoom-Out Standard, and the high-altitude picture is simpler than the three earlier reports imply. The document has not been revised, so every failure condition cited in Stages 5–7 is still present verbatim at the same lines and no prior finding is resolved.

More importantly, those findings are not independent. Almost every Major and Blocker — filename validation, path traversal, overwrite and data loss, stale files, folder creation, write failures, personal-data retention, the `/` rejection rule, the missing risk register — follows from one scope decision: `--remind` writing a persistent file per member. Remove that decision and the design collapses to a small read-only report that is close to passing. The earlier stages treated the symptoms separately; the critic stage's advice to specify a filename-derivation algorithm in the spec would deepen the weeds. The correct response is to delete the output shape that needs them.

What passes, re-verified against the code: context is sufficient; `store.open_loans()` already exists and is correctly reused (`src/lendr/store.py:30`); the read-only path is one pass over an in-memory list with no caching, async, or indexing; the non-goals are honest about email, fines, and storage; and the no-network constraint matches the README. The failure is scope, not context or reuse.

## Resolved

None. The text cited by the earlier reports is unchanged, and no comprehension gap or critic finding has been answered in the document. All three reports stay open as inputs, not history.

## Carried Over (grouped, not re-argued)

* **Test-only `--today` flag — Major, lines 50–51.** Still unresolved, and now also the entry point for the timezone and input-validation questions from Stage 7. The function seam `late_loans(rows, today)` already exists for tests; the flag is a second seam exposed to volunteers who never need it.
* **Per-member filename / overwrite / stale-state cluster — Major, lines 40–42, 73–74.** Still unresolved; subsumed by N1. If N1 is accepted these disappear rather than needing mitigations.
* **Same component detail at two altitudes — Major, lines 36–51 vs. 61–74.** Still unresolved, and it is generating false findings: comprehension's "`write_reminders` is never wired" is only the numbered step omitting what the Technical Plan already states. The fix is deduplication, not more prose.
* **Alternatives analysis — Blocker, lines 53–59.** Still unresolved. The load-bearing omission is the alternative that reuses the existing `list` subcommand, parser, and print loop: an opt-in `list --late` leaves the default output — and the volunteer's counting script — untouched, so the stated rejection reason does not cover it. It is also the alternative that would have exposed the scope problem below.
* **Missing Risks & Limits section — Blocker, absent after line 59.** Still unresolved, but do not answer it with an eight-entry risk register for one optional flag. Most expected entries are consequences of N1; a risks section for the remaining read-only report is short (malformed `due`, invalid `--today` if kept, output contract).
* **Output contract, empty state, exit codes, tie-break — Major/Nits, lines 36–38.** Still unresolved and now more consequential: if the report becomes the only output, its contract is the entire interface, so escaping, no-results text, and a secondary sort key are not cosmetic.
* **Problem statistics and absent success measure — Major, lines 9–12, 22–26.** Still unresolved, and it is the root of N1: the cited overdue rate is an outcome this design does not move, and goal 2 has no basis in the problem statement.
* **Schema / `open_loans()` contract — Major, lines 36–37.** Partly answers itself from the code; see N4.
* **Reminder content, location and lifecycle, returned-loan ownership, validation layer, style nits.** Subsumed by N1 and N2, or cosmetic; no separate action.

## New or Materially Changed Findings

### N1. The feature is two deliverables, and only the first is grounded in the problem - Severity: Blocker
* **Affected Scope:** `The Problem` 9–12; `Overview` 17–19; `Goals` 25; `Non-Goals` 28–32; `Technical Plan` 40–48; `Detailed Implementation Plan` 63–74
* **Simplicity Rationale**: The problem statement establishes one gap: `lendr list` shows open loans without marking lateness, so a volunteer compares dates by eye. Goal 1 and `lendr overdue` answer that in one filter pass over `open_loans()`. Goal 2 and `--remind` introduce a second deliverable — durable files, one per member — that nothing in the problem asks for. The document never says volunteers currently retype loan details, write reminder notes, or need one file per member. That ungrounded half is where essentially all downstream complexity lives: a member-keyed file namespace that must be created, refreshed, pruned, sanitized, secured, and kept in sync. It is a small stateful store disguised as an output flag, and it sits awkwardly against the Non-Goals, which rule out member accounts. The `/` rejection rule at lines 73–74 is the first entry in the validation list this shape will inevitably grow.
* **Recommendation**: Decide first whether reminder notes are in scope now. If they are, state the burden in `The Problem` (volunteers hand-write these notes today) and justify `--remind` against it. Either way, do not make filenames carry identity. The simplest shape that satisfies both goals is one read-only report grouped by member on stdout, which the volunteer prints or copies a block from. If a file is genuinely required, write one file per run with a fixed name, not one per member. That deletes `write_reminders`, the folder lifecycle, the filename contract, and the `/` rule, leaving roughly a 30-line change in `cli.py` plus a pure filter.

### N2. The reminder note — the deliverable goal 2 promises — is the least specified output - Severity: Major
* **Affected Scope:** `Technical Plan` 40–41; `Goals` 25
* **Simplicity Rationale**: The stdout line at 38 fixes member, tool, due date, and days late. The reminder note is described only as "listing that member's late tools." A note with tool names but no due date or lateness forces the volunteer to add those by hand — exactly the retyping goal 2 says the feature removes. Stage 7 filed this as a Nit; at the goal level it is a Major, because the product's content is undefined while the developer-facing output is fully specified.
* **Recommendation**: Define the note's fields once (tool, due date, days late, generation date) and give one sample block — or, if N1 is accepted, fold it into the single report format so there is one contract, not two.

### N3. Member name is treated as identity for grouping, but the data model has none - Severity: Major
* **Affected Scope:** `Technical Plan` 40–42; `Detailed Implementation Plan` 63–66, 73–74; cf. `store.add`/`open_loans`
* **Simplicity Rationale**: `member` is a free-text positional argument stored verbatim (`src/lendr/store.py:16–18`). Grouping by that string merges two distinct members with the same typed name into one note and splits one member across case or spacing variants. Earlier stages flagged filename collisions; the correctness of the grouping itself was not examined. At this library's scale the assumption may be acceptable, but the `--remind` deliverable depends on string equality being identity, so the design must state and explicitly accept that assumption.
* **Recommendation**: If N1 reduces the output to a report, the same assumption is visible to the reader and harmless. Otherwise state it as an accepted limitation and define the normalization rule.

### N4. The `due` contract is now verifiable, and the Stage 5 "string comparison is silently correct" claim is only half right - Severity: Major
* **Affected Scope:** lines 36–37, 50, 63–64
* **Simplicity Rationale**: `store.add` writes `due.isoformat()` (`src/lendr/store.py:18, 21`), and `open_loans()` already excludes returned rows (`:30–31`). Filtering and sorting on the ISO string is therefore correct without parsing, and returned-loan filtering is owned by the store — the comprehension Nit about ownership is settled, and the returned-loan test case at lines 69–70 cannot reach `late_loans` through the documented path. But `days_late` requires `date.fromisoformat`, which can raise on a hand-edited record.
* **Recommendation**: State one contract: `due` is the `YYYY-MM-DD` string written by `store.add`; filter and sort lexicographically; parse only to compute `days_late`; define behaviour for unparseable values. That replaces "name the assumption" with a concrete line and closes the Stage 6 and 7 schema finding.

### N5. Goal 3 restates Non-Goal 3 - Severity: Nit
* **Affected Scope:** line 26 versus line 32
* **Simplicity Rationale**: "Existing `loans.json` files keep working without conversion" asserts the absence of a change the design never proposes, and Non-Goal 3 already commits to not changing storage. Goals should state an outcome the design produces.
* **Recommendation**: Drop it, or replace it with the visibility outcome (a volunteer identifies every late loan without comparing dates by eye).

### N6. The stated testability rationale is unsupported by the test plan and the repository - Severity: Nit
* **Affected Scope:** lines 63–66, 69–70
* **Simplicity Rationale**: `overdue.py` is justified "so the date logic can be tested without the command line," but the repository has no tests directory, runner configuration, or dependency manifest, so `tests/test_overdue.py` also introduces an unstated test framework. The listed cases cover only the pure filter, while the failure-prone half (`write_reminders` and the `/` rule) has no test, and the returned-loan case is unreachable.
* **Recommendation**: If N1 removes file writing, keep the module only if the project is also adopting tests; otherwise put the filter beside `open_loans()` and test it there.

### N7. Existing data-location convention not reused - Severity: Nit
* **Affected Scope:** lines 41, 47
* **Simplicity Rationale**: `store.PATH` is already the project's notion of where loan data lives; the design invents a second, unanchored location for `reminders/`.
* **Recommendation**: Say "beside `loans.json`" and derive it from `store.PATH.parent`, or state the working-directory rule outright. Subsumed by N1 if files are dropped.

## Strategic Recommendation

Revise scope, not wording. In order: (1) decide whether `--remind` exists now, and if so ground it in the problem statement; (2) replace per-member files with a single read-only report, optionally one fixed-name file per run; (3) fix the two contracts that remain (the `due` string and the output format), deduplicate the Technical and Detailed sections to one altitude, and replace the straw-man `list` alternative with the opt-in flag that actually competes; (4) write a three-line Risks & Limits section for what is left. After that, the document describes a 30-line change, which is proportionate. In its current form it describes a 30-line change plus a file-management subsystem, and the subsystem is the only reason the risks section is long.
