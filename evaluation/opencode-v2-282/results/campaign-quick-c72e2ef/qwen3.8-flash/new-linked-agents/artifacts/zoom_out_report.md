# Stage 5 — Initial Zoom Out Review: `overdue_reminders.md`

- **Target:** <RUN>/project/docs/designs/overdue_reminders.md
- **Scope:** full file, lines 1–75
- **Standard:** resources/document_standards/zoom-out-standard.md
- **Reviewers:** egm-zoom-out (Skeptical Architect), egm-inventive-catalyst (TRIZ)
- **Goldfish baseline given to reviewers:** project README.md. The design also links `../../AGENTS.md`; it was deliberately left out of the reviewers' reading list because reviewer dispatches may not require AGENTS.md files. The author should still check the design against it.
- **Date:** 2026-11-11

## Summary verdict

Context sufficiency passes: the document states what is being built (`lendr overdue`, optional reminder notes) and why (volunteers only learn about late loans when someone asks), so the review proceeds rather than failing at the prerequisite check. The strategic direction — read-only command plus plain-text notes, with no sending — is sound and its rejected alternatives were properly examined. The problems are concentrated in scope, failure handling, and layering, not in the core idea.

Total: **1 Blocker, 4 Major, 3 Nit**.

## Codebase facts the reviewers verified (basis for several findings)

Source: egm-zoom-out reuse audit of `src/lendr/cli.py`, `src/lendr/store.py`, package root.

- The package is exactly three files. `store.py` owns every disk touch (`PATH = pathlib.Path("loans.json")`, `_load`, `_save`) and already owns row filtering (`open_loans()`).
- `cli.py` holds all command logic; its `list` branch is the loop the design reuses conceptually.
- `due` is persisted as an ISO string; there is no date helper anywhere.
- There is **no `tests/` directory** and no test runner configuration of any kind (no `pyproject.toml`, `setup.cfg`, or `requirements.txt`).

## Findings

### 🔴 Blocker 1 — `--remind` solves a problem the document never states (egm-zoom-out)

**Scope:** Overview (16–21), Goals (26), Technical Plan (41–49), Detailed Implementation Plan step 1 (64–67).

The root problem (9–12) is a *read* gap: late loans are invisible. `lendr overdue` on stdout closes it completely. The reminder-file writer addresses a different need — that volunteers "retype loan details" (26) — for which no evidence appears in The Problem, and line 19 itself says the program never sends anything, so the produced artifact is still a file a human opens and pastes by hand. The feature is not cheap: it brings in an output folder, overwrite semantics, group-by-member, a name-to-filename mapping, a sanitization error path (74–75), and half of the proposed new code. Cutting `--remind` removes roughly half the design's footprint and its entire side-effect surface while still satisfying the stated goals.

**Note on the other reviewer's view:** egm-inventive-catalyst examined the manual-delivery trade-off and judged it a project invariant (README: "no network access"), not a false compromise — the ideal outcome under that constraint. The two results are compatible: *if* the feature ships, its delivery model is right; the blocker is that the need for it is not yet evidenced.

**Recommendation:** ship the read-only command now; split reminder generation into its own design when a volunteer asks for it. If `--remind` stays, add the missing evidence to The Problem.

### 🟡 Major 2 — Member-name filenames: weak sanitizer, unbounded failure blast radius, undefined partial state (merged: egm-zoom-out F3 + egm-inventive-catalyst F1)

**Scope:** 41–43, 64–67, 74–75.

The design manufactures filesystem identifiers from unvalidated free text typed at loan time, rejects only `/`, and calls it solved. Unhandled: backslash, `..`, `.`, empty names, leading/trailing spaces, case-insensitive collisions, unicode lookalikes — and the overwrite rule (43) means a collision silently replaces one member's note with another's. Worse, one bad row aborts `--remind` for *every* member, defeating the command's stated purpose via a passive report-and-stop error; and because the check sits inside the write loop, the partial-state question (were earlier files already written before the abort?) is unaddressed, contradicting the "folder always reflects the current state" claim.

**Resolutions offered (egm-inventive-catalyst, TRIZ):**
- *Segmentation + Blessing in Disguise:* per-row quarantine — an unsafe name is excluded from file emission, its loan listed on stderr, and the remaining reminders and the full stdout report still complete. Secondary liabilities: a warning channel that needs its own tests; volunteers must learn "succeeded with warnings"; exit-code policy must be chosen deliberately or scripts ignore problems.
- *Intermediary:* stop embedding raw names — stable key filenames like `reminders/NN-<slug>.txt` with the human name inside the file. Secondary liabilities: loses the by-name greppability the design chose names for; slug transliteration can collide two members into one file, a new defect class.

The structurally simpler option (egm-zoom-out): one combined `reminders.txt` in due-date order, grouped by member headings, needs no sanitizer and no error path at all.

### 🟡 Major 3 — Undefined write location; persistence boundary bypassed (egm-zoom-out)

**Scope:** 41–43, diagram 45–49, step 1 (65–67).

`reminders/` is a relative path and the design never says relative to what, so the folder lands wherever the volunteer happened to `cd`. Today every byte on disk goes through `store.py` and its single module-level `PATH`; this design adds a second, direct write inside new code, forking the project's only persistence convention. State the base path and route the write through the layer that owns `loans.json`.

### 🟡 Major 4 — New module justified by test infrastructure that does not exist (egm-zoom-out)

**Scope:** steps 1 and 3 (64–67, 70–71).

`late_loans(rows, today)` is a filter-and-sort over the rows `store.open_loans()` already returns. A third module in a three-file package adds a layer boundary with no second consumer, and the stated reason — testability without the command line — assumes infrastructure the repo lacks: no `tests/` tree and no configured runner, so `tests/test_overdue.py` silently presupposes a pytest setup the design never lists as a prerequisite. Note the pure-function signature itself already provides the test seam. Put the late-loan query in `store.py` beside `open_loans()`, keep printing in `cli.py`, drop `overdue.py`; if a test tree is wanted, state adding test tooling as its own step.

### 🟡 Major 5 — Altitude drop: two sections duplicate one design, one down to code level (egm-zoom-out)

**Scope:** Technical Plan (36–52) vs Detailed Implementation Plan (62–75): format string (39), signatures (64–67), enumerated test cases (70–71), error-message wording (74–75).

The design's job is to fix the contract — a volunteer sees late loans oldest-first with days late, optionally with notes — not to choose the literal `(<n> days late)` string or pre-list which four unit tests to write. Duplicated sections at different altitudes drift once either is edited. Collapse to one section at component/data-flow/responsibility level; move formatting, signatures, and the case list to implementation.

### 🟡 Major 6 — Validation placed at the consumer edge instead of the record boundary (egm-inventive-catalyst)

**Scope:** layering between `cli.py` (step 2) and `overdue.py` (step 1).

A data-shape rule about member names is enforced where reminders are written, not where loans are created. Because legacy `loans.json` files keep working without conversion (27, 33), awkward names can pre-exist forever and every future consumer of member names must re-implement its own guard — this overdue command is only the first file-writing consumer, so the coupling will replicate. Move name-shape validation into `lendr loan` and centralize the filesystem-safe representation in one named function. Secondary liabilities (declared): retroactive ineffectiveness forces a read-side fallback anyway (two guards); a new user-facing constraint on `lendr loan` needs README and test coverage and could reject data already entered; filename logic in a library layer coarsens CLI integration tests. Respects the no-storage-change Non-Goal.

### 🟢 Nit 7 — Two clock seams; date parsing left unspecified (egm-zoom-out)

**Scope:** 51–52, 37–39.

`--today` is user-visible CLI surface added "so tests are repeatable", but `late_loans(rows, today)` already provides that seam — tests pass a date directly and never need the flag. Keep one seam. Separately, the design never says how a stored ISO string becomes a computable date; name `datetime.date.fromisoformat` rather than leaving the implementer to pick, since bare string comparison would silently "work" for the filter and fail for the `days_late` arithmetic.

### 🟢 Nit 8 — Two decisions outsourced to unverifiable authority (egm-zoom-out)

**Scope:** 21, 58.

Line 21 makes compliance with contributor rules (`AGENTS.md`) a condition of the design without stating what that compliance constrains, so the design cannot be confirmed against its own rules from the design alone. Line 58's one un-cited anecdote ("would break a script one volunteer uses") is the sole justification for adding a new subcommand instead of marking lateness in `lendr list`, where The Problem says the gap actually is. Respecting an existing output contract is legitimate — but as the hinge of the whole command structure it should be evidenced, not asserted.

## Checked and deliberately not flagged (egm-inventive-catalyst)

- **Manual delivery of reminders** (print/paste by a volunteer): a project invariant, not a false compromise; the email alternative was rejected on concrete grounds.
- **Overwrite semantics of `reminders/`**: for a small all-volunteer operation with a 1-in-5 lateness rate, "always reflects current state" is the simpler correct choice; reconciliation, backups, or generated markers would be premature machinery.
- **No clock abstraction beyond `--today`**: warranted at this scale. (Nit 7 still applies to the redundant flag itself.)

## Suggested resolution order

1. Decide Blocker 1 (drop or justify `--remind`); it shrinks or reframes Majors 2–3 and 6 if dropped.
2. If `--remind` stays: fix filename scheme and failure blast radius (Major 2), define the write path and route it through the store layer (Major 3).
3. Fold `late_loans` into `store.py` or state test tooling as a prerequisite (Major 4).
4. Collapse the duplicated plan sections to one altitude (Major 5), then pick up Nits 7–8.
