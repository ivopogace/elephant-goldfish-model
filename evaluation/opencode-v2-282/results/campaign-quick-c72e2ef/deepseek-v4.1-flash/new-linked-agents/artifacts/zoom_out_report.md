# Stage 5 — Initial Zoom Out Review

* **Target:** `docs/designs/overdue_reminders.md` (full file, lines 1–75)
* **Date:** 2026-11-11
* **Standard:** Zoom Out Standard (`resources/document_standards/zoom-out-standard.md`)
* **Reviewers:** `egm-zoom-out` (skeptical architect), `egm-inventive-catalyst` (TRIZ / false compromises)
* **Goldfish context supplied:** `README.md` (linked from the design). The design's link to `AGENTS.md` was left out: the review guard denies reviewer reads of `AGENTS.md`, and reviewer instructions are stripped from the project anyway. The design's request to "check this design against" contributor rules therefore could not be honored and is not counted as a defect.

---

## Context sufficiency (prerequisite check)

**Pass.** The Problem section names the actor (volunteers), the current workaround (compare due dates by eye), the observed frequency (about one loan in five), and the cost (popular tools unavailable for weeks). The Overview names a concrete deliverable, and the Non-Goals keep it inside the README's constraints (JSON on disk, no network). A fresh reader can tell what is being built and why. The findings below are refinements, not a request for more context.

## Codebase checks

The zoom-out reviewer read the project source (read-only):

* `store.open_loans()` exists exactly as the design claims (`src/lendr/store.py:30-31`), and rows carry `member`, `tool`, `due`, `returned`. The proposed `late_loans(rows, today)` signature fits that row shape.
* The project has two real modules (`store.py`, `cli.py`) plus an empty `__init__.py`. There is no domain or service layer, and `cli.py` holds command logic inline, including the print loop at `cli.py:24-26` that `lendr overdue` would clone.
* There is **no** `tests/` directory and no pytest configuration. Plan item 3 silently introduces a test harness, not just a test file.
* No existing overdue, late, or reminder logic. Nothing is being reinvented except module placement (finding 7).

---

## Findings

### 1. 🟡 Major — Root problem names a cost the design never addresses
**Scope:** *The Problem* (lines 9–12) vs *Goals* (lines 25–26), *Overview* (line 19).

The Problem states two costs: volunteers cannot see which loans are late, and popular tools are unavailable for weeks. Every Goal maps to the first only. Nothing claims or measures the second. If weeks-long unavailability is the real cost, a printed list is triage, not a fix, and the design cannot be judged against its own motivation. Either narrow the Problem to visibility, or state the causal claim (reminders shorten loans) and the signal a volunteer would check after rollout.

### 2. 🟡 Major — `--remind` carries most of the complexity with no root-problem trail
**Scope:** *Overview* line 17, *Goals* line 26, *Technical Plan* lines 41–43.

The Problem never says volunteers retype loan details, nor that members forget. `--remind` introduces a second workflow — per-member grouping, directory creation, filename policy, overwrite semantics, name rejection — and every hard question in this review comes from it. The minimal version is `lendr overdue` alone: one filtered read over `store.open_loans()`. If the retyping cost is real, put it in the Problem instead of leaving it implicit in a Goal, then keep `--remind`.

### 3. 🟡 Major — Alternatives Considered omits the cheapest option
**Scope:** *Alternatives Considered* (lines 56–58).

The rejected alternative is "mark late loans inside `lendr list`," turned down because it changes output and breaks a volunteer's counting script. That is a strawman: an **additive** `lendr list --overdue` flag leaves default output byte-for-byte identical, gives the short late-only list volunteers asked for, and reuses the existing print loop instead of duplicating it in a second subcommand. The design buys a new command and a new module to avoid a flag. Weigh this option and record why it loses.

### 4. 🟡 Major — The `reminders/` contract contradicts itself
**Scope:** *Technical Plan* lines 41–43; *Detailed Implementation Plan* line 74.

"Existing reminder files are overwritten so the folder always reflects the current state" cannot hold. A member who returns a tool, or who has no late loans this run, keeps an orphan note forever, so the folder accumulates stale reminders while claiming to be a current projection. Overwriting also destroys any record that a note was issued. Meanwhile the note body is unspecified: no due date, no days late, no generation date, so a stale file looks identical to a fresh one and a volunteer can hand a member a weeks-old notice.

Decide one role and write it down:
* **Projection** — build and validate every note in memory, write them, then remove any `*.txt` this run did not produce, and print what was written and removed. Needs an explicit ownership marker so the tool never deletes a user's file.
* **Ledger** — write to a dated folder (`reminders/<YYYY-MM-DD>/<member>.txt`), append-only, with the issue date in the note.

Either way, put the generation date and days late in the note body.

### 5. 🟡 Major — A shipped CLI flag justified only by testing
**Scope:** *Technical Plan* lines 51–52; *Detailed Implementation Plan* lines 64–67, 72.

`--today` is public, user-facing surface, justified as "so tests are repeatable," and the plan also argues `late_loans(rows, today)` exists so the date logic can be tested without the command line — which makes the flag redundant for that purpose. Plan item 4 does not document it in the README, confirming it is not a user feature. (The inventive-catalyst reviewer rated this a Nit; both reviewers agree it is redundant surface, and they differ only on how much an undocumented flag matters.) Either drop it and keep date injection at `late_loans`, or document it as an operator override for back-dating and add a CLI-level test. Do not add timezone handling.

### 6. 🟡 Major — Member names used raw as filesystem keys from unvalidated input
**Scope:** *Detailed Implementation Plan* lines 74–75.

Rejecting only names containing `/` closes one case of a whole class. Member names arrive as free-form `lendr loan <member> ...` arguments with no validation in `store.add`. Unhandled: `\` (traversal on Windows), case-folding collisions ("Bob" and "bob" collapse to one file on default macOS/Windows filesystems, silently replacing one member's list with another's), reserved device names (`CON`, `NUL`, `COM1`), trailing dots or spaces, empty or whitespace-only names, over-long names, Unicode normalization, and distinct names that sanitize to the same file. Rejection also aborts mid-run, leaving notes already written and no signal of which members were skipped.

Insert a key between the member string and the filesystem: `slugify(member) + "-" + short_hash(member)`, with the verbatim name as the first line of the note so the file explains itself. Validate and render all notes before writing any, so a bad name fails the run cleanly with no partial output.

*Cost of this fix:* filenames stop being literally the member name, so print the name→file mapping; hash suffixes look opaque; the slug rules become a tested surface with platform differences; buffering all notes means one bad row blocks every note instead of degrading per member.

### 7. 🟢 Nit — Undeclared output contract that the design just surrendered to
**Scope:** *Alternatives Considered* (lines 56–58), *Technical Plan* line 39.

An ad-hoc stdout parse by one volunteer is treated as an immutable external API, but that contract lives nowhere and no test pins it. It is folklore, so it will not survive the next change to `list` even though it blocked this one. The design then introduces a new human-prose format that will attract the same kind of parser. Keep `overdue` as its own subcommand, and make the constraint enforceable: pin `list` stdout with a golden-output test, or state in the README that `list` output is human-facing and may change.

### 8. 🟢 Nit — Silent empty result and unspecified output location
**Scope:** *Overview* line 18, *Technical Plan* lines 37–43.

`reminders/` resolves against the process working directory, the same latent assumption as `store.PATH = pathlib.Path("loans.json")` even though the README says loans live "next to the program." Run from another directory and a volunteer sees no late loans, no error, and a new empty folder — a silent false negative that reads exactly like "everything is on time." Print the resolved folder path under `--remind`, and emit an explicit "no overdue loans" line on stderr so stdout stays parseable. Anchor one data root rather than creating two competing conventions.

### 9. 🟢 Nit — Altitude drop into the high-level sections
**Scope:** *Technical Plan* lines 37 and 51.

Naming the stdlib call (`datetime.date.today()`) and the test-repeatability rationale belongs in the Detailed Implementation Plan. The Technical Plan should state the boundary — "today is an injected input; the command supplies the system date" — and leave the data-flow diagram (lines 45–49), which is the strongest part of that section, to carry the structure. The output format at line 39 is an acceptable interface contract, but say plainly that it near-copies the `list` format, since divergence between the two shapes is a support cost.

### 10. 🟢 Nit — New module justified by test convenience only
**Scope:** *Detailed Implementation Plan* item 1 (lines 64–67).

`late_loans()` is a query over loan rows, and the only existing loan query, `open_loans()`, lives in `store.py`. There is no service layer for a fourth file to slot into. Putting `late_loans(rows, today)` beside `open_loans()` and keeping the write loop in `cli.py` preserves the two-module shape and gives the same testability. A new module is defensible, but the plan justifies it by test convenience rather than an architectural boundary, so state it as a choice.

### 11. 🟢 Nit — The "open" predicate has two possible owners
**Scope:** *Detailed Implementation Plan* lines 64–71.

The plan feeds `late_loans` from `store.open_loans()` (already returned-filtered), yet requires a test proving "a returned loan (ignored)." That test only passes if `late_loans` re-implements the open predicate, creating a second source of truth that can drift from `store.open_loans()` and `store.close()`. State the contract: `late_loans` assumes open rows and the returned case is tested at the store seam, or `late_loans` is the single filter and the CLI stops calling `open_loans()`. Do not filter in both.

### 12. 🟢 Nit — No test harness exists for plan item 3
**Scope:** *Detailed Implementation Plan* item 3 (lines 70–71).

`tests/test_overdue.py` implies a `tests/` directory, a runner, and a convention the project does not have yet. Either add "create the test layout" to the plan or note the tooling assumption.

---

## Checked and **not** false compromises

To avoid manufacturing transforms, both reviewers flagged these as sound:

* **Manual print-and-deliver step.** A real boundary, not a concession: the README states there is no network access, and storing member email addresses is an explicit non-goal. A `mailto:` or `.eml` export was considered and rejected — it does not remove the manual recipient choice, so it removes none of the bottleneck while adding MIME handling.
* **A separate `overdue` subcommand instead of a storage or model change.** Correct YAGNI cuts given date-only stored data and a frozen storage format.
* **Reusing `store.open_loans()` and injecting `today` at a pure function.** Right layer, right testability seam, no new abstraction.

## Priority for the next stage

1. Settle the `reminders/` role and note body (finding 4) — this decides half the remaining design.
2. Settle whether `--remind` belongs in v1 at all (finding 2), which also disposes of findings 5, 6, and 12.
3. Record the `list --overdue` alternative with a reason (finding 3).
4. Decide the member-name-to-file key and the validate-before-write rule (finding 6).
5. State the "open" predicate owner (finding 11) and move stdlib naming out of the Technical Plan (finding 9).
