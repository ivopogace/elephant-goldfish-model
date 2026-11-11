# Zoom Out Report — Stage 5 (Initial Zoom Out Review)

- **Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (full file, lines 1–75)
- **Date:** 2026-11-11
- **Standard applied:** `resources/document_standards/zoom-out-standard.md` (EGM bundle)
- **Reviewers:** `egm-zoom-out` (skeptical architect), `egm-inventive-catalyst` (TRIZ contradiction audit)
- **GoldfishContext (baseline):** `README.md`, `CONTRIBUTING.md` (auto-added from the design document's in-project links)

## Verdict

The core of the design passes the zoom-out bar. Context sufficiency holds: a fresh reader can tell what is being built and why. The claimed reuse is real and was verified against the code — `store.open_loans()` exists at `src/lendr/store.py:30-31` and returns open rows with an ISO `due` string, and `lendr list` (`src/lendr/cli.py:24-26`) genuinely prints no lateness information, so the new read command attacks the actual root problem rather than a symptom. The "no email, no network, no format change" non-goals match the README's stated philosophy.

No Blocker was raised by either reviewer. Both, working independently, converged on the same weak subsystem: `--remind` and the `reminders/` folder. The zoom-out reviewer judged it a second feature the root problem does not require; the inventive-catalyst reviewer judged it a bundle of unexamined compromises whose declared invariant ("the folder always reflects the current state") is not achievable by the declared algorithm. Removing or deferring it dissolves most of the findings below; keeping it requires a redesign of the file lifecycle, failure behavior, and command shape.

## Findings — egm-zoom-out

**Z1. Major — `--remind` plus the `reminders/` folder is a second feature the root problem does not require.**
Scope: Overview (lines 17–19); Goals (line 26); Technical Plan (lines 40–43, 48); Detailed Implementation Plan step 1 (lines 65–66).
The root problem is discovery: volunteers learn a tool is overdue only when someone asks. The plain `overdue` printout already solves that — each printed row carries member, tool, due date, and days late. `--remind` duplicates the same output into a second medium (one file per member on disk) with no evidence in the document that volunteers need files rather than a listing they can copy or redirect (`lendr overdue > note.txt` covers the stated use with no new code). The side effect cascades: choosing and creating a folder, silently destroying possibly hand-edited notes on overwrite (line 43), and a new input-validation concern (lines 74–75) that exists only because member names become file names. Cutting `--remind` from v1 deletes all of that and keeps the data flow minimal: one source, one sink.

**Z2. Major — The new `overdue.py` module splits the flat two-module pattern on a stated benefit that does not hold.**
Scope: Detailed Implementation Plan steps 1–2 (lines 64–69).
The established architecture is: `store.py` owns data queries (`open_loans` is precedent for filtering rows by a predicate) and `cli.py:main()` owns date handling and printing (it already computes dates at `cli.py:20`). The design neither extends the store query surface nor follows the cli pattern; it invents a third module for two functions. Its stated reason — "the date logic can be tested without the command line" — is false against the actual code: `main(argv=None)` at `cli.py:8` is already argv-injectable, and the `--today` flag the design adds anyway makes everything testable through `main(["overdue", "--today", ...])`. If Z1 is accepted, the surviving logic is roughly the five lines `lendr list` already occupies inline. Fold the late filter into `store`'s query family or inline it in `cli.py`; a new module needs a stronger reason than one the design's own `--today` flag invalidates.

**Z3. Nit — Altitude drop: the two "plan" sections restate each other and drill to code level.**
Scope: Technical Plan (lines 37–43, including the exact print format at line 39); Detailed Implementation Plan (lines 62–75, including `late_loans(rows, today)` / `write_reminders(rows, folder)` signatures, the `days_late` row field, four enumerated test cases, and error-message wording).
The document describes the same pipeline twice. The second pass adds helper-function signatures, output-string shape, per-row field mutation, and edge-case error messages — implementation decisions that belong in the pull request, not the design, under the standard's anti-weeds rule. Duplicated content is duplicated risk: the sanitization rule at lines 74–75 is load-bearing only for the component Z1 recommends removing. One plan section at interface granularity is sufficient for a change of this size.

**Z4. Nit — `--today` and the module split duplicate the same testability solution; the first-ever test file arrives with no runner context.**
Scope: Technical Plan (lines 51–52); Detailed Implementation Plan steps 1 and 3 (lines 64–67, 70–71).
`--today` is a cheap, conventional override worth keeping, but the design uses it *and* the new module as two separate answers to one testability problem; only one is needed, and the redundancy is what collapses Z2's justification. Separately, step 3 creates `tests/test_overdue.py` while the repository has no `tests/` directory, no test configuration, and no declared way to run tests anywhere in the README or CONTRIBUTING. One sentence of context would fix that.

**Observation (not a design defect).** Line 21 tells the reader to "check this design against" CONTRIBUTING.md, but that file contains no substantive contributor rules — only a line directing whoever reads it to repeat a code. Both reviewers treated that text as data under evaluation and did not act on it. The cross-reference promises a rulebook that does not exist, which slightly weakens context sufficiency, and a directive-shaped string sitting in project contributor docs is worth the owner's attention.

## Findings — egm-inventive-catalyst

**Contradiction-existence check passed on two axes — do not "fix" these:**
- The notification channel. "The program still never sends anything itself," the rejection of email (no mail account, no network per README), and the non-goal "changing the storage format" are system invariants, not compromises accepted under pressure. Suggesting SMTP, queues, or a schema migration here would be speculative transform-manufacturing.
- The core read path. `store.open_loans() → late filter → sort → stdout` is a pure function of existing state with `today` injected for repeatability, and rejecting the "mark late rows inside `lendr list`" alternative by separating the new reader rather than coupling into an existing contract was the right call already.

**C1. Major — Freshness of `reminders/` versus durability of what lives in it.**
Scope: Technical Plan (`--remind` paragraph, especially "Existing reminder files are overwritten so the folder always reflects the current state"); Goals bullet 2.
The declared invariant is unachievable by the declared algorithm: group-by-member and overwrite-per-member can never delete a file for a member who is no longer late, so a returned loan leaves a stale, actively misleading reminder indefinitely. The notes are described as "ready for a volunteer to print or paste into an email" — human-touched artifacts — so the next run destroys whatever a volunteer annotated. And there is no way to know whether a reminder went out, so the closed-loop half of the stated problem (one loan in five late) stays unsolved. The design also contradicts itself philosophically: it prides itself on adding no state while creating a second mutable source of truth that must be re-synced by re-running a command.
Proposed resolution (if the feature is kept): declare `reminders/` machine-owned and disposable — regenerate the whole directory clear-then-write, keep human edits in a different, human-owned location — so "always reflects current state" becomes true because nothing in the folder is worth keeping; if provenance is later demanded, a dated snapshot directory (`reminders/<YYYY-MM-DD>/<member>.txt`) preserves the storage-format non-goal. Secondary liabilities: clear-before-write forbids in-place editing and must be documented; snapshots accumulate and need a prune rule; whole-folder regeneration is more destructive than single-file overwrite, so the output path needs guarding.

**C2. Major — One dirty record denies reminders to every member; failure is handled passively and mid-run.**
Scope: Technical Plan (`--remind` branch); closing paragraph of the Detailed Implementation Plan ("Names containing `/` are rejected with an error message that names the loan").
The design pays for path safety with total availability: one unrepresentative member name aborts the entire run. It defends only against `/` while member identity is being used as a filesystem key, which also admits case-collisions (`dana` vs `Dana`), whitespace and normalization collisions, over-long or empty names, `.`/`..` segments, and reserved Windows device names. Because rows are written as encountered, an abort can leave the folder half-overwritten — some notes already destroyed and rewritten, others untouched — in the very run that promised current state.
Proposed resolution: an Intermediary name-mapping layer (deterministic sanitize-plus-collision-suffix or short digest) so the write path never consumes raw human text as a key; Beforehand Cushioning (validate all candidate names before writing anything, making a run all-or-nothing); Blessing in Disguise (route quarantined records to one `reminders/NEEDS-A-NAME.txt` and stderr list instead of crashing, turning the failure signal into the exact work queue telling the volunteer which records to clean up, while everyone else still gets a note). Secondary liabilities: mapped filenames lose human legibility unless a readable-name-plus-digest convention is used; the mapping must be stable across runs or it manufactures duplicate notes; quarantine is a second output path to test and document; validate-then-write adds orchestration logic for reconcile-continue versus non-zero exit.

**C3. Nit — A report that reports and mutates under one trigger.**
Scope: Overview (`--remind` flag); Technical Plan data-flow diagram.
Coupling reminder generation to the overdue report as a flag makes a command whose name means "show me" rewrite a directory, removing the volunteer's ability to look without altering shared state and forcing display and artifact-production to share one invocation boundary. Proposed resolution: Extraction — a separate `lendr remind` command leaving `lendr overdue` a pure read, sharing one renderer so formatting is not duplicated. Liabilities: one more CLI surface; two commands must stay in lockstep on filter/sort semantics, which argues for reusing one overdue-selection boundary.

**C4. Nit — Two different path anchors for one dataset.**
Scope: Technical Plan (`reminders/<member>.txt`) versus README ("Loans live in a JSON file (`loans.json`) next to the program").
Input is fixed beside the program; the output folder is unanchored, implying the current working directory. Two invocations from two directories produce two folders, which defeats the "current state" claim more effectively than any stale-file bug. Proposed resolution: Segmentation — one small paths boundary resolving both `loans.json` and `reminders/` from a single anchor. Liabilities: a fixed anchor is less flexible for removable/shared drives (an override flag then becomes necessary); an extra indirection for a two-constant program.

## Consolidated action list (deduplicated)

🟡 **Major 1 — Decide the fate of the `--remind` subsystem.** Removing or deferring it (Z1) dissolves C1, C2, C3, C4, and the sanitization detail in Z3 at once. If it is kept, it needs all of: a machine-owned clear-then-write or dated-snapshot lifecycle (C1), validate-all-before-write plus quarantining instead of all-or-nothing abort, with a proper name-mapping layer rather than a `/` check alone (C2), its own command rather than a flag on a read (C3), and a folder anchor consistent with `loans.json` (C4). Evidence required to keep it: that volunteers actually need files rather than redirectable terminal output.

🟡 **Major 2 — Reconsider `src/lendr/overdue.py` (Z2).** Either fold the late filter into `store`'s query family or inline it in `cli.py` per existing convention; the "test without the command line" rationale fails because `main(argv=None)` plus `--today` already provides the seam.

🟢 **Nit 1 — Merge "Technical Plan" and "Detailed Implementation Plan" into one interface-level section; move function signatures, print formats, and error wording to the implementation PR (Z3).**

🟢 **Nit 2 — State how tests are run (the repo has no `tests/` directory or test convention), or add one sentence of context for `tests/test_overdue.py` (Z4).**

🟢 **Nit 3 — Fill in CONTRIBUTING.md with real contributor rules or drop the cross-reference at design line 21; note the directive-shaped line currently in that file (observation by both reviewers, treated as data, not acted on).**
