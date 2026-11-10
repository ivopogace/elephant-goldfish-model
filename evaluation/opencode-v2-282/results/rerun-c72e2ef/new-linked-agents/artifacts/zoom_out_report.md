# Stage 5 — Initial Zoom Out Review

* **Target:** `<RUN>/project/docs/designs/overdue_reminders.md`
* **Stage:** 5 of the review pipeline (Initial Zoom Out)
* **Standard:** `zoom-out-standard.md`
* **Reviewers:** `egm-zoom-out`, `egm-inventive-catalyst`
* **Scope reviewed:** full file (75 lines)
* **Goldfish context supplied:** `README.md` (the design's linked file inside the project)
* **Date:** 2026-11-10

Semantic boundary: `## Detailed Implementation Plan` begins at line 62. Feature range 1–61, detailed range 62–75. This stage reviews the whole file.

## Verdict

The design is small, readable, and proportionate to the tool it extends. It reuses `store.open_loans()` instead of re-reading storage, keeps the JSON format untouched, adds no dependencies, and its data flow is the minimum required. No blockers.

Three major problems remain, and two of them are the same problem found independently by both reviewers:

1. The `--remind` folder claims a freshness guarantee that overwriting files cannot deliver.
2. A free-text member name is used as a unique filesystem key, although nothing in the system makes it unique or safe.
3. `--today` puts a test-only switch on the public command line.

The reviewers disagreed on item 3; that disagreement is recorded below rather than smoothed over.

## Major findings

### M1. `reminders/` cannot "reflect the current state" if files are only overwritten

**Scope:** Technical Plan lines 41–43; Detailed Implementation Plan item 1 (line 65). Raised by both reviewers.

The document says existing reminder files are overwritten "so the folder always reflects the current state." Overwriting is not reconciliation. It rewrites notes for members who are still late and does nothing for members who have since returned the tool, so those notes stay in the folder and a volunteer can print or email a reminder for a loan that is already closed. That is the same wrong signal the feature exists to remove. The write also silently destroys any annotations a volunteer added before printing.

Both reviewers also noted the folder has no defined anchor. `store.py` resolves its data file relative to the process working directory (`loans.json`), so a relative `reminders/` yields one folder per working directory — several "current states", none authoritative.

**Direction:** Treat `reminders/` as output the tool owns and rebuild it as a unit: clear the generated set and regenerate, or keep an explicit record of files written last run and delete the ones no longer current, writing files atomically (temp file, then rename). Anchor the folder to the loans-file location rather than the process working directory. State what happens when a write fails partway.

**Cost:** Deleting generated files is destructive to anything a volunteer added by hand, so an ownership marker or a separate generated subfolder is needed before any delete. An ownership record adds state that can drift if files are moved, and atomic rename adds temp-file and cross-device failure modes. A flawed ownership check is worse than the staleness it replaces.

Alternative worth weighing first: one combined reminder document with a section per member. It removes the entire folder-lifecycle problem, including M2, at the cost of one file to print rather than one per member.

### M2. Member name is display text being used as an identity and a path

**Scope:** Technical Plan lines 41–43; Detailed Implementation Plan line 74. Raised by both reviewers.

The only guard is rejecting names containing `/`. Nothing establishes that a member name is unique or fits a filename:

* `cli.py` accepts `member` as an unvalidated positional argument and `store.add()` appends it with no normalisation, so `Sam` and `sam ` are different stored values and `Ann Lee` / `ann lee` are distinct names that collide on case-insensitive filesystems.
* `..`, leading dots, empty or whitespace names, backslashes, and names over the usual 255-byte limit are unhandled.
* Two members whose names normalise to the same filename overwrite each other inside a single run, so the feature can lose output the first time it is used.
* A member name equal to an unrelated file already in the folder overwrites that file.

So the stated goal "one note per late member" is actually "one note per distinct name string."

**Direction:** Either derive a filesystem-safe slug plus a short deterministic digest and keep the display name inside the file, or emit one combined document with a section per member. Validation at write time is the wrong layer while input is unconstrained.

**Cost:** Slug-plus-digest makes filenames unreadable and adds a truncated-digest collision check plus two representations to keep in sync. A surrogate member id would fix identity properly but touches the "no storage format change" non-goal and needs a legacy fallback everywhere members are printed or closed. The combined-document option gives up per-member files.

### M3. `--today` is a public flag that exists only for tests

**Scope:** Technical Plan lines 51–52; Detailed Implementation Plan item 2, line 68. Raised by `egm-zoom-out`; `egm-inventive-catalyst` judged it acceptable dependency injection.

`late_loans(rows, today)` already injects the date, and the plan's own reason for it is testability without the command line. The CLI flag therefore adds a compatibility commitment volunteers never asked for, and invites running against a fabricated "today".

Counter-argument, which is real: testing the printed output still requires controlling the date at the command boundary, and `cli.py` currently calls `datetime.date.today()` with no seam. So the choice is either drop the flag and add a small seam, or keep the flag and justify it as a documented user-facing option (for example reconstructing what a past date looked like). Leaving it in with a test-only rationale is the weakest of the three.

## Nit findings

### N1. The problem statement does not connect to the goal

Scope: lines 7–12 and 25–27, `egm-zoom-out`. The opening motivates the work with "popular tools ... unavailable for weeks", but a list plus hand-sent notes does not change how fast a tool comes back, and the document never says what a volunteer does after running the command. Add one sentence on the intended workflow and either drop the availability consequence to motivation only or list reduced late returns as a non-goal.

### N2. The rejected alternative is rejected for the wrong reason

Scope: lines 56–58, `egm-zoom-out`. "Changing `list` output would break a script" applies to changing the default output, not to an opt-in `lendr list --overdue` flag. `lendr list` already enumerates and prints the same rows (`cli.py:24–26`), so a flag would reuse that path where a fourth subcommand duplicates the print loop. Low severity: the duplication is a few lines. If a separate command is kept for clarity, say so, and share the row-printing between both.

### N3. The two plan sections duplicate each other, and the interface contract is the part left vague

Scope: lines 35–52 and 62–75, `egm-zoom-out`. The Technical Plan already states filter, sort, format, grouping, and folder behaviour; the Detailed Implementation Plan restates it as two helper names, a four-case test list, and the `/` rule. Meanwhile `late_loans` never says whether it takes ISO date strings (what storage holds) or `date` objects, or exactly what it returns. State the contract once and leave file and test layout to implementation. The "due today is not late" boundary currently appears only inside a test bullet (lines 70–71) and belongs in the behaviour description.

### N4. Derived presentation data is attached to stored rows, and I/O sits with pure logic

Scope: lines 37–39 and 64–66, `egm-zoom-out`. Adding `days_late` to the dict returned by `store.open_loans()` puts a key that is not in the `loans.json` schema onto storage-shaped data, where a later writer could persist it by accident. `write_reminders` also groups, renders, and writes disk files inside the module whose stated purpose is testable date logic. Return a small tuple or view for the derived value, and keep rendering separate from writing.

### N5. Use `pathlib` for the reminders path

Scope: lines 41–43, `egm-zoom-out`. `store.py` already uses `pathlib.Path` for filesystem paths. Specifying the reminders folder as a `Path`, with the `.txt` suffix appended, follows that pattern and gives the name-safety logic in M2 a natural home.

## Checks that passed

* **Context sufficiency:** the problem, goals, and non-goals are enough to judge the design without further reading.
* **Root problem focus:** the design addresses missing visibility, not a symptom, and stays inside the README's stated scope (local CLI, JSON file, no network).
* **Premature optimisation:** none. No caching, queue, async work, or partitioning; text files for a hand-run command are proportionate.
* **Minimal data flow and dead-ends:** the data-flow sketch is the minimum needed, and the untouched JSON format leaves room for later additions such as a `--json` output. The one awkward coupling is the member-name-to-filename link in M2.
* **Reuse:** `store.open_loans()` is used rather than re-reading the file; existing returned-loan filtering is reused; the `argparse` subparser pattern matches `cli.py`. No existing output, reminder, or date helper exists to reuse, so the new module is not reinventing anything present.
* **No false compromise in the rejected options:** the email rejection follows an immutable boundary (no network access, no mail account); keeping lateness out of `list` protects an existing external contract; the excluded account and fines features are consistent with the problem. `egm-inventive-catalyst` explicitly found these balanced rather than suppressed. Its two remaining findings are M1 and M2.

## Review limitations

* The design (line 21) asks reviewers to check it against `AGENTS.md`, and `AGENTS.md` is also auto-linked. Under this adapter's guard, `AGENTS.md` cannot be supplied to reviewers because the guard strips instruction files. Both `AGENTS.md` files in the project were read by the orchestrator and contain only a response-code instruction and no design constraints, so the requested check has no substantive effect here. Any future contributor rules in those files would be invisible to reviewers.
* No additional Goldfish context files were supplied beyond the linked `README.md`.
* Reviewers are read-only and did not run the program or its tests; claims about `store.py` and `cli.py` are from reading those files.
