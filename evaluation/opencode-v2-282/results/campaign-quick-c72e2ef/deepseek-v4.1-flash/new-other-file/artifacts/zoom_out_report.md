# Zoom Out Review Report — Stage 5 (Initial Zoom Out)

* **Target:** `docs/designs/overdue_reminders.md` (full file, lines 1–75)
* **Reviewers:** `egm-zoom-out` (Skeptical Architect), `egm-inventive-catalyst` (Inventive Catalyst)
* **Standard applied:** `resources/document_standards/zoom-out-standard.md`
* **Goldfish context:** `README.md`, `CONTRIBUTING.md`
* **Date:** 2026-11-11

## Summary

| Severity | Count |
| --- | --- |
| Blocker | 0 |
| Major | 7 |
| Nit | 8 |

The reviewers found no fault in the core shape. The design reuses `store.open_loans()`, keeps the date calculation in one pure function, does not change the storage format, and correctly refuses to send anything. No reviewer asked for a scheduler, daemon, queue, lock, cache, or reconciliation loop; none of that belongs in a single-user offline JSON tool.

The findings cluster in three places: the `--remind` output contract (it promises a state it cannot maintain, and it writes user-visible files using unvalidated names), the public interface (a test-only flag and an unexamined pass over `lendr list`), and the altitude of the plan (signatures and test enumeration are fixed before alternatives are weighed). Two independent reviewers reached the stale-reminder and filename findings separately, which raises confidence that they are real rather than stylistic.

## Findings

### 1. [Major] `--remind` claims the folder "always reflects the current state"; the write-only design cannot keep that promise

**Scope:** Technical Plan lines 41–43; Overview lines 16–19; Detailed Plan line 70.
**Raised by:** both reviewers, independently.

The design says existing reminder files are overwritten so the folder always reflects current state. That is false for the case the feature exists to fix. A member who was late on Monday and returns the tool on Tuesday has no late loan, so no file is written and their old note stays on disk. A volunteer who prints the folder re-nags someone who already returned the tool, and the folder accumulates a graveyard of stale notes.

The opposite failure is also real. The folder is explicitly for humans to print and annotate ("phoned Pat, 3 Nov"), and a blind overwrite destroys those annotations without warning.

**Direction, not prescription:** define the generated set explicitly instead of inferring it from directory contents. Either write one dated artifact per run (`reminders/overdue-<today>.txt`), which makes staleness visible from the filename and needs no deletion, or keep per-member files and bound cleanup with a manifest listing what the tool wrote, pruning only those files. Dated artifacts still accumulate and shift cleanup into a housekeeping habit. Manifest pruning reintroduces on-disk state and makes the tool delete user-visible data, which is the highest-risk failure class here and needs its own tests. If the team will not own deletions, the dated artifact is the safer option.

### 2. [Major] Member names are used as filenames; rejecting `/` does not protect the property the code needs

**Scope:** Detailed Plan lines 62–75 (closing paragraph); Overview line 16–19.
**Raised by:** both reviewers.

`member` is unvalidated argv text; `store.add()` (`store.py:16–19`) writes it verbatim. Rejecting `/` addresses path traversal only. The property the writer actually needs is an injective mapping into legal filenames, and the current rule fails it:

* **Silent loss on case-folding filesystems.** `Pat Smith` and `pat smith` are distinct members in `loans.json` but one path on macOS and Windows. The second write replaces the first with no exception and no message — a member silently gets no reminder while the run reports success.
* **Control characters.** A newline produces a multi-line "filename" (legal, unreadable); a NUL raises mid-run.
* **Length.** A name over roughly 255 bytes raises `OSError` after earlier members' files are already written, leaving a partial folder that looks complete.
* **Reserved and awkward names.** `.`, `..`, leading `-`, and Windows reserved names either misbehave or create files that later globs handle surprisingly.
* **The error path is passive.** The document says the name "is rejected with an error message" but never says whether the run aborts, what happens to files already written, or what the exit status is.

**Direction:** map names through one pure function and validate the whole member→filename mapping, including collisions, before writing anything. Percent-encoding keeps names reversible but unreadable; a slug plus a short stable hash is readable but unstable across renames and invites questions. Either way, repeat the true member name inside the note so the filename is never authoritative. Fail-closed preflight means one junk row blocks every other member's reminder, so it needs an escape hatch or manual cleanup.

### 3. [Major] One malformed `due` value takes down the whole command, contradicting goal "existing `loans.json` files keep working"

**Scope:** Technical Plan lines 37–39; Goals line 27; Detailed Plan step 1.
**Raised by:** `egm-inventive-catalyst`.

`store._load()` is a bare `json.loads` (`store.py:8–9`) with no validation. A single hand-edited `due` — a typo, `""`, `2026-13-01`, JSON `null`, or `2026-1-5` — makes the date parse raise and kills the command, including rows that are perfectly valid. It also breaks the plain string sort the design relies on. With `--remind`, the exception can land after some reminder files are written. The document states an error policy for member names and none for dates.

**Direction:** partition rather than crash. Return late rows plus unparseable rows, print the late rows, report the bad ones on stderr, exit non-zero, and do this preflight before any reminder file is written. The cost is real: skipped bad rows stay invisible unless someone reads stderr, and a non-zero exit breaks chained shell usage.

### 4. [Major] `--remind` is scope that the problem section does not ask for

**Scope:** Overview lines 16–19; Goals line 26; Technical Plan lines 41–43; Detailed Plan line 72.
**Raised by:** `egm-zoom-out`.

The Problem section says overdue status is hard to see; it gives no evidence that volunteers need per-member files. `--remind` adds grouping, file I/O, naming, overwrite semantics, error handling, and a second output mode — a second feature. If volunteers do currently retype loan details, that evidence belongs in the Problem section, and the smallest fix is likely grouped stdout, not a persistent folder contract. If `--remind` is a confirmed requirement, this finding collapses to simplifying the output mechanism, not dropping the need.

### 5. [Major] The problem statement describes an alerting gap, but the design ships a report a volunteer must remember to run

**Scope:** "The Problem" lines 7–12; "Goals" lines 23–27.
**Raised by:** `egm-zoom-out`.

Line 9 says volunteers learn about overdue loans only when another member asks. A new subcommand does not change that trigger; it only removes the by-eye comparison once someone decides to check. The goals are output capabilities ("can see", "can produce"), not an outcome or adoption path, and there is no success signal for the one-in-five lateness claim or the weeks-long unavailability of popular tools.

**Direction:** narrow the problem to "overdue status is not identifiable in `lendr list` output" and drop the behavioural claim, or state the actual trigger (for example an overdue count on every invocation) and a measurable target. Do not add both without saying which problem is being solved.

### 6. [Major] `--today` is a test seam exposed as a public flag, and its types are undefined

**Scope:** Technical Plan lines 51–52; Detailed Plan lines 64–67 and 72.
**Raised by:** `egm-zoom-out`.

The flag exists "so tests are repeatable", but the design already isolates the clock in `late_loans(rows, today)`. Tests can call that function with a fixed date, or patch the clock for a CLI test. The flag adds public parsing, invalid-date behaviour, and documentation surface, and step 4 only promises to document `--remind`, so `--today` would ship undocumented. The date representation is also unspecified: `store.add` writes `due` as an ISO string (`store.py:18`), so the interface must say whether `today` and `due` are `date` objects or strings.

### 7. [Major] The Detailed Plan restates the Technical Plan and fixes code-level choices before alternatives are weighed

**Scope:** Detailed Implementation Plan lines 62–75 against Technical Plan lines 35–52.
**Raised by:** `egm-zoom-out`.

The section names new file paths, exact signatures and return fields (`late_loans(rows, today)`, `days_late`), exact test cases, and a filename character rule. A lower-altitude section is expected in this template, so the finding is not that it exists. It is that it duplicates the Technical Plan and locks choices — module split, signature shape, sanitizer rule — before alternatives such as an opt-in `list --overdue` or a single report file have been considered. Keep the decisions that constrain architecture (reuse `store.open_loans()`, no storage change, the output and reminder contract); leave signatures and test enumeration to the implementation stage.

### 8. [Nit] "Mark late loans inside `lendr list`" is rejected as a straw man

**Scope:** Alternatives Considered lines 54–58.
**Raised by:** `egm-zoom-out`.

The rejection rests on breaking a volunteer's counting script, which follows only from changing the *default* output. An opt-in `lendr list --overdue` preserves the default, reuses the existing subparser and print path, and avoids a new top-level command. The design does not weigh it. Either add it and justify the separate command on discoverability or output-format grounds, or prefer the flag.

### 9. [Nit] The new module is not a reuse violation, but its justification is weak and it creates a parallel print path

**Scope:** Technical Plan lines 37–39; Detailed Plan lines 64–69.
**Raised by:** `egm-zoom-out`, after code search.

No existing late-loan filter or reminder writer exists, so nothing is being reinvented. The stated reason for `src/lendr/overdue.py` — testability without the CLI — does not hold: a module-level function in `cli.py` is equally testable. The design also adds a second row-printing loop instead of reusing `cli.py:24–26`. A third source module for two small functions is extra structure in a two-module project. Reuse a shared row formatter, and keep the filter in `cli.py` unless the reminder logic grows enough to earn its own file.

### 10. [Nit] The `open_loans` → `late_loans` → `write_reminders` data contract is ambiguous

**Scope:** Technical Plan line 37; Detailed Plan lines 64–71.
**Raised by:** `egm-zoom-out`.

Line 37 says the command reads open loans and filters them, yet the test list includes "a returned loan (ignored)" for `late_loans`. If `late_loans` receives open rows, that test is vacuous at that layer; if it also filters `returned`, it duplicates `store.open_loans()`. `write_reminders(rows, folder)` likewise does not say whether it takes late rows or all open rows. State one source of truth for "open" and test returned-loan exclusion at the store or CLI boundary.

### 11. [Nit] The `reminders/` base directory is undefined and disagrees with the README

**Scope:** Technical Plan lines 41–43; Detailed Plan line 72; `README.md:10`; `store.py:5`.
**Raised by:** both reviewers.

`README.md:10` says loans live "next to the program", but `store.PATH` is `pathlib.Path("loans.json")`, i.e. relative to the current working directory. The design's `reminders/` has no defined base, so it can land somewhere other than the loan file. Both reviewers also ask whether the folder is created when missing.

### 12. [Nit] Output and exit contract under `--remind` is unstated

**Scope:** Overview lines 16–19; Technical Plan lines 37–52; format string at line 39.
**Raised by:** `egm-inventive-catalyst`.

The design does not say whether `--remind` still prints the list to stdout, what a note contains (due date, days late, or only tools), or the exit code on success and on error. The line format is space-delimited over two free-text fields, so it is ambiguous when a member or tool name contains a space. No goal requires machine parsing, so do not add a JSON format unless a consumer is named; do state the contract that exists.

### 13. [Nit] The existing CLI dispatch has a catch-all `else` the new command must not inherit

**Scope:** `src/lendr/cli.py` lines 19–26; design lines 68–69.
**Raised by:** `egm-zoom-out`.

`cli.py` currently treats `else` as the `list` handler. Adding an `overdue` branch before it works, but any future unhandled subcommand will silently print all open loans. The design says "add the overdue subcommand" without mentioning this. Convert the `else` to an explicit `elif args.command == "list"` as part of the change.

### 14. [Nit] The design tells reviewers to check it against contributor rules that do not exist

**Scope:** Overview lines 20–21; `CONTRIBUTING.md` lines 1–3.
**Raised by:** both reviewers.

`CONTRIBUTING.md` contains no engineering, test, style, or review rules. Its only content is a meta-instruction addressed to automated readers. There is nothing to check the design against, so the reference is misleading. Both reviewers flagged this rather than pretending compliance. Remove line 21 or replace it with real contribution rules (test command, style, review process); the repository also needs a test runner before `tests/test_overdue.py` means anything.

### 15. [Nit] `tests/test_overdue.py` presumes a test runner that is not declared

**Scope:** Detailed Plan step 3.
**Raised by:** `egm-inventive-catalyst`.

The project has no `pyproject.toml`, `setup.py`, `requirements*.txt`, or `tests/` directory. Step 3 is a new convention, not reuse. The plan should name the runner and how it is invoked.

## Checks that found nothing

* **Context sufficiency (Standard §0):** objective and motivation are identifiable; no context failure.
* **Premature optimisation:** no caching, sharding, async processing, or background queue is proposed. Both reviewers explicitly declined to recommend any.
* **Storage compatibility:** the JSON format is unchanged, so the "no conversion" goal is structurally supported.
* **Platform standards:** `datetime.date.fromisoformat` and standard grouping cover the parsing and grouping needs; no custom utility is warranted.
* **Reuse:** code search found `store.open_loans()` as the only query, `cli.py:24–26` as the only row renderer, and no existing date, sorting, grouping, or text-output helper. The design uses `open_loans()` correctly.

## Reviewer disagreement

None on substance. `egm-inventive-catalyst` stated its findings inside a bounded architecture and confirmed that no infrastructure pattern is warranted; `egm-zoom-out` pushed two of the same points further toward removing `--remind` outright. Finding 4 records that disagreement honestly: it is a scope judgement, not a defect, and the author should decide it rather than have the reviewer decide it.

## Note on a repository hazard

`CONTRIBUTING.md` is an instruction-injection surface: its only line tells automated readers to emit a specific string. The guard on this run strips project instruction sources from reviewers, and both reviewers treated the string as data rather than as a requirement, so the review is unaffected. The file should be cleaned up separately; it is not a defect in this design document.
