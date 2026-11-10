# Stage 5 — Initial Zoom Out Review

* **Target:** `docs/designs/overdue_reminders.md` (full file, lines 1–75)
* **Reviewers:** `egm-zoom-out` (Skeptical Architect), `egm-inventive-catalyst` (TRIZ contradiction analysis)
* **Standard applied:** `resources/document_standards/zoom-out-standard.md` (to `egm-zoom-out`)
* **Context read:** `README.md`, `AGENTS.md`, and the existing `src/lendr/` sources
* **Date:** 2026-11-10

## Prerequisite check — context sufficiency: PASS

The document states what is being built and why: volunteers learn about overdue tools only when another member asks, about one loan in five is late, so add `lendr overdue` plus an opt-in `--remind` note generator. Goals, non-goals, and two rejected alternatives are present. A fresh reader can determine the objective and motivation without extra context, so the review proceeds on its substance.

## Findings

Findings from both reviewers are merged and de-duplicated. Severity follows the Zoom-Out Standard scale.

### 1. Major — `--today` is a production flag that exists only to make tests repeatable

**Affected scope:** Technical Plan (lines 51–52); Detailed Implementation Plan item 2 and item 3 (lines 68, 70); README step (line 72).

The design already gives testability through a `today` parameter on the new function ("so the date logic can be tested without the command line", lines 66–67), then adds a second, public seam. `--today` appears in no Goal, and the README change lists only `--remind`, so the flag would ship undocumented. Once a volunteer or a script uses it, it becomes permanent surface that must be supported. The CLI already accepts an injected `argv` (`cli.py:8`), so end-to-end date coverage does not need a user-facing flag. Either drop `--today` or state a concrete user need for it.

### 2. Major — the `reminders/` folder adds a file-management subsystem, and its "always current" claim is false

**Affected scope:** Overview (lines 17–19); Technical Plan (lines 41–43, diagram lines 45–49); closing paragraph (lines 74–75).

Two problems are combined here.

*Necessity:* the goal is "produce reminder notes without retyping loan details" (line 26). Per-member files force the design to own filename derivation, collision handling, overwrite semantics, stale-file cleanup, folder creation, and permissions — none of which serves that goal. Printing the same text to stdout, or letting the volunteer redirect it, reaches the goal with no storage contract and no chance of destroying a note a volunteer annotated.

*Correctness:* line 43 says overwriting means "the folder always reflects the current state". Overwriting rewrites only members who are late now. A member written on Friday and returned on Monday keeps a stale note; a re-borrow with a later due date keeps the old date and the old lateness count. The invariant holds only for members who are still late — the case where it matters least. The folder is treated as both a generated view and a volunteer workspace without separating the two roles. If the folder stays, the design must say whether the program owns it (delete files from a previous run that are no longer produced) or refuses to overwrite files it did not write.

### 3. Major — member names as filenames is a local workaround, and the guard is incomplete

**Affected scope:** Technical Plan (line 42); Detailed Implementation Plan item 1 (line 65); closing paragraph (lines 74–75).

Rejecting `/` patches one character instead of removing the cause: untrusted member input used as a filesystem path. Unhandled: case-insensitive collisions (`Ann` and `ann` collapse into one file, silently losing one member's list on macOS and Windows), Unicode normalisation collisions, `..`, backslashes, empty or whitespace-only names, trailing dots or spaces, reserved names (`CON`, `NUL`), and length limits. The error path is also unspecified: abort the whole run, skip the member, or fail after some files are written? "Rejected with an error message that names the loan" implies one bad record can block reminders for every other late member. The note body also carries no member name except in the filename, which is what forces the coupling. A single mapping from member name to safe, collision-free file name, plus the member name written as the note's first line, would contain the problem.

### 4. Major — a new `overdue.py` module duplicates the selection layer that already exists

**Affected scope:** Technical Plan (lines 37–39); Detailed Implementation Plan item 1 (line 64).

The reviewers disagree on this point, and both positions are recorded below under "Reviewer disagreement". The concern: `store.py` already owns row selection (`open_loans()` filters on `returned`), and `cli.py` owns date construction and printing. Putting "which loans are late" in a third module separates it from "which loans are open", so every future filter faces an arbitrary choice of home. The document never argues for the new module over `store.late_loans(today)` or a few lines inside the command. Note also that the module pairs an overdue filter with a file writer: those two functions share no concern.

### 5. Major — detection still depends on a volunteer remembering to run the command

**Affected scope:** The Problem (lines 9–12); Goals (lines 25–27); Overview (lines 19–20, "the program still never sends anything itself").

The Problem section measures harm as time-to-notice ("find out only when another member asks", "unavailable for weeks"), but the Goals ask only that a volunteer *can* run something. The design treats "no network, no mail account, must not send" as also forbidding any active surfacing, so the human-memory dependency the document identifies is relocated from remembering due dates to remembering the command. Reminder notes are also most useful before the volunteer is at the desk. A host-scheduler contract (cron, systemd timer, Task Scheduler) with no daemon and no network, plus an exit-code convention (0 = nothing late, distinct non-zero = late loans found, 2 = usage or data error) and a quiet mode, would remove that dependency without breaking the "never sends" promise. This is an advisory direction, not a blocker; if the scope is deliberately limited to an on-demand command, say so in Non-Goals.

### 6. Nit — the `cli.py` dispatch change is missing from the plan

**Affected scope:** Detailed Implementation Plan item 2 (line 68); existing `cli.py:24–26`.

`list` is the catch-all `else` branch, so adding a subparser is not additive: without converting `else` to `elif args.command == "list"`, `lendr overdue` falls through and prints the open loan list. The plan describes the change as "add the `overdue` subcommand", which points an implementer at a silent-wrong-output trap.

### 7. Nit — the Detailed Implementation Plan restates the Technical Plan at a lower altitude

**Affected scope:** lines 62–75, especially 64–71.

The section names exact file paths, function signatures (`late_loans(rows, today)`, `write_reminders(rows, folder)`), an internal field name (`days_late`), and an enumerated list of test cases. `late_loans` is described in the same words at line 37, so the section adds no architectural information before the detailed-plan stage has been reached. Component boundaries and data flow belong here; function signatures and individual test cases do not.

### 8. Nit — two output sinks, only one format defined

**Affected scope:** Technical Plan (line 39 vs. line 42); `write_reminders` in item 1.

The stdout line is specified to the character, while the note body is only "listing that member's late tools". The plan's test item 3 asserts reminder contents with no contract to assert against, and two sinks that format the same data separately will diverge. Define the note body, and render both from one row formatter if the folder survives Finding 2.

### 9. Nit — artifact root is implicitly the current working directory

**Affected scope:** Technical Plan (lines 41–43); interaction with `store.PATH`.

`reminders/` is a relative path with no stated root. `store.PATH` is already `pathlib.Path("loans.json")` (`store.py:5`), so input and output both depend on where the command is run from. Under the scheduled use in Finding 5, the data file would not be found and the folder would appear in an unexpected place. One place that resolves the artifact root (derived from the loans file, or an explicit option) contains this, with the current behaviour kept as the default.

### 10. Nit — behavioural edges left to the implementer

**Affected scope:** Technical Plan (lines 37–52); tests (lines 70–71).

Each of these has two plausible answers that will be guessed differently: `due` is stored as an ISO string (`store.py:18`, `cli.py:21`) while `late_loans` takes a `today` date, so the string-to-date boundary is undefined; no late loans could mean empty output with success or a message; the project has no test framework declared anywhere, yet the plan adds its first test file.

### 11. Nit — goals are output-shaped, with no link back to the measured problem

**Affected scope:** The Problem (lines 9–12); Goals (lines 25–27).

The problem is quantified (one loan in five late; popular tools unavailable for weeks), but the goals stop at "a volunteer can see all late loans" and "can produce reminder notes". Nothing states an expected effect or how the library would notice the feature is not working, so a successful structural fix cannot be told apart from an unused command.

### 12. Nit — the `list`-compatibility rejection is asserted, not examined

**Affected scope:** Alternatives Considered (lines 56–58).

"Changing the `list` output would break a script one volunteer uses to count loans" is stated as a law without saying what the script parses. If it counts lines, an appended marker changes nothing; if it parses column positions, it does. Keep the default output byte-identical and expose lateness additively if the script tolerates it; otherwise the current decision stands, but it should rest on a check rather than an assumption.

## Contradiction analysis (`egm-inventive-catalyst`)

A genuine contradiction exists, so this is not a "no false compromise detected" result. The design claims the folder "always reflects the current state" while specifying an overwrite-only write path, which cannot deliver that invariant (Finding 2). Member identity is welded to filename identity, so filesystem safety and human-readable note names are treated as mutually exclusive and "safety" is reduced to rejecting `/` (Finding 3). Detection latency, the measured problem, is accepted as unchangeable because the program must not send anything, even though scheduling the existing command needs no network (Finding 5).

Parts the catalyst judged already balanced and did not flag: `due` as ISO-8601 means lexicographic order equals chronological order, so no date transform is needed; `--today` as a parameter is a correct control-flow inversion for testability (the disagreement is about also exposing it as a flag); reusing `store.open_loans()` avoids duplicating the returned-row filter.

## Reviewer disagreement

`egm-zoom-out` rates the new `overdue.py` module a Major finding (duplicate selection layer, split concern). `egm-inventive-catalyst` explicitly accepts the module as a correct extraction for testing. Both agree that `store.open_loans()` should remain the single selection anchor; they differ on whether a separate module is justified. The decision is the author's, but the document should state the reason, because as written it does not argue the point either way.

## Verdict

No blockers. Context is sufficient and the design addresses the root problem rather than a symptom: `lendr list` output is deliberately left intact for a stated reason. The Majors are about avoidable surface area, not wrong intent — a test-only public flag, a file-writing feature whose "always current" claim does not hold, a filename scheme that patches one bad character instead of removing the cause, an unargued new module, and an unchanged manual trigger. Settling Findings 1–3 would let the feature land as one testable function plus one command branch, with no new destructive write path and no new public flag.
