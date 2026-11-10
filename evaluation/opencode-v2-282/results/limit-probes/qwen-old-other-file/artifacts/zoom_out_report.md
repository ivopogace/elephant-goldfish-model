# Stage 5 — Initial Zoom Out Review Report

- **Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (full file, lines 1-75)
- **Standard applied:** `/opt/egm-v2/bundle/resources/document_standards/zoom-out-standard.md`
- **Reviewers:** `egm-zoom-out` (Skeptical Architect) and `egm-inventive-catalyst` (TRIZ), dispatched in parallel as fresh Goldfish sessions
- **GoldfishContext used:** `README.md`, `CONTRIBUTING.md` (linked from the design; no user-supplied additions)
- **Date:** 2026-11-10

## Verdict

Context sufficiency passes: the document states what is being built and why, with a quantified symptom ("About one loan in five comes back late", line 12). No blockers. The `lendr overdue` read-only half of the design is sound and reuses existing infrastructure correctly. The problems are concentrated in the `--remind` half: its stated correctness property does not hold as designed, its file-naming rule is a partial band-aid, and its new module placement conflicts with the codebase's existing structure. Seven consolidated findings below (0 blockers, 4 major, 3 nits).

## Consolidated Findings

### 🟡 M1. The `reminders/` folder does not "always reflect the current state" (stale-file contradiction)
- **Source:** zoom-out finding 1; catalyst finding 1 (same defect, converged)
- **Scope:** Overview lines 17-19; Technical Plan lines 41-43
- The design says existing reminder files are overwritten "so the folder always reflects the current state" (line 43), but only writes per member. A member who has since returned everything keeps a reminder file forever. The failure mode is the worst one available: a volunteer prints a stale folder and nags a member who is no longer late. No cleanup rule, no error, and none of the four listed tests (lines 70-71) covers it. The asserted invariant is false as designed.
- **Recommendation:** If `--remind` stays, declare `reminders/` derived state that each run reconciles: write today's late-member files and delete `reminders/*.txt` files for members no longer late (scoped strictly to that folder and glob, with a test). Simpler alternative: one wholly-rewritten `reminders/overdue.txt`. Either way, document that the folder is machine-owned so volunteers do not annotate notes in place. Note the trade-off: a filter bug plus a delete step turns a display bug into a data-loss bug, so the delete scope must be narrow and tested.

### 🟡 M2. Member name used as filename: rejected `/` is a local patch, not a structural fix; identity coupling is unexamined
- **Source:** zoom-out findings 1 and 7; catalyst finding 2
- **Scope:** lines 42-43, 74-75
- Lines 74-75 reject only names containing `/`. Remaining holes: `..`, empty/whitespace names, and case-insensitive collisions ("Jo Smith" vs "jo smith" on a typical single-laptop filesystem), where one member's note silently replaces another's — a wrong reminder to the wrong person. Worse, one awkward name aborts the whole `--remind` run for all members, and the failure surfaces at reminder time instead of at `lendr loan`, where it could have been caught. With member accounts a declared non-goal (line 32), the name string has silently become the system's identity, and name-as-filename makes that identity load-bearing.
- **Recommendation:** Do not make the filename the identifier. Use a deterministic, injective mapping (readable slug plus short hash suffix) so no valid name collides or is rejected, keep the exact member name inside the file body, and move name-sanity validation to loan-recording time. Trade-offs: uglier filenames to print and browse; validating in `lendr loan` changes an existing command's accepted inputs, the same conservatism the author applied to `list` (lines 56-58), so it needs explicit README coverage. The mapping must disambiguate, not merge names — merging would reinvent member accounts, which line 32 rules out.

### 🟡 M3. Data-type contract with the reused store is undefined — the stated filter does not run against the actual schema
- **Source:** zoom-out finding 3
- **Scope:** Technical Plan lines 37-39; Detailed Implementation Plan lines 64-66
- The plan filters "rows whose `due` date is before today" and computes a `days_late` integer, but `store.add` persists `due` as an ISO **string** (`src/lendr/store.py` lines 18, 21) and `store.open_loans()` returns rows untouched (lines 30-31). Comparing that string to a `datetime.date` is invalid; a parse step and a `timedelta` are needed, and the design never says where parsing happens or whether `late_loans` takes raw store rows or normalized ones. This is the interface between the reused component and the new component — exactly what a high-level design must pin down. It also makes Goal line 27 ("existing `loans.json` files keep working") unverifiable as written.

### 🟡 M4. Wrong placement and a second filesystem owner; `reminders/` location is never anchored
- **Source:** zoom-out finding 4; catalyst finding 3 (partial overlap on path anchoring)
- **Scope:** Detailed Implementation Plan lines 64-67; Technical Plan lines 41-43
- In this codebase only `store.py` touches the filesystem; `cli.py` parses arguments and prints. Putting `write_reminders` inside a new `overdue.py` mixes a pure date function with I/O side effects and creates a second writer of on-disk state. The stated justification ("date logic testable without the command line", line 67) only requires separating `late_loans`, not co-locating the file writer. Separately, the folder's anchor is unspecified: `store.py` uses a current-directory-relative path (line 5) while the README says loans live "next to the program" — running `lendr overdue --remind` from another directory could scatter reminder folders.
- **Recommendation:** If `--remind` survives, file writing belongs in the store layer, and one sentence in the Technical Plan must state where `reminders/` resolves relative to (next to the `loans.json` in use is the option consistent with the store's existing boundary).

### 🟢 N1. `--remind` itself may be a second feature bolted onto the root problem (scope / YAGNI)
- **Source:** zoom-out finding 1 (first half); catalyst finding scope note
- **Scope:** Overview lines 17-19; Goals line 26; and the whole `--remind` machinery
- The root problem is visibility of late loans (lines 9-11). A pure read, zero-side-effect `lendr overdue` solves it. `--remind` adds the design's only new writes, the naming hazard (M2), and the staleness bug (M1), and its goal ("produce reminder notes without retyping loan details", line 26) is reverse-engineered from the feature rather than evidenced in The Problem. Recommendation: consider shipping `lendr overdue` alone and moving `--remind` to a separate proposal with demonstrated volunteer demand. This is a scope call for the author, not a defect in itself; if kept, M1/M2/M4 must be fixed.

### 🟢 N2. Rejected alternatives skip the strictly simpler option: reuse the `lendr list` loop
- **Source:** zoom-out finding 2
- **Scope:** Alternatives Considered lines 56-58 vs. lines 37-39 and 64-69
- `cli.py` (lines 24-26) already iterates `store.open_loans()` and prints `member tool due`. The new command re-implements that loop with a filter, so the same rows are formatted in two places and will drift. The documented rejections argue only against *altering existing output*; they do not rule out the option the document never considers: `lendr list --late`, or a shared row-formatting helper used by both commands. The hearsay justification ("volunteers asked", line 57) is uncited. Either adopt the reuse option or record why it was rejected.

### 🟢 N3. Minor altitude and hygiene issues
- **Source:** zoom-out findings 5, 6, 7; catalyst finding 4
- `--today` as a permanent public CLI flag exists only for test repeatability (line 52), but `late_loans(rows, today)` already provides the test seam; `cli.py` itself hardcodes `date.today()` for `loan` (line 20), so the flag is new public surface for internal convenience.
- The document describes the plan twice at two altitudes (lines 35-49 and 62-75), and the sharpest edges — writes into the working directory, overwrite-only, name rejection — appear only in the low-altitude copy, so summary readers miss them. One plan section would be shorter and safer.
- Line 21 tells the reader to check the design against `CONTRIBUTING.md`, but that file contains no substantive contributor rules — its only "rule" is an embedded instruction-shaped string demanding that a code token be repeated in every answer. Both reviewers evaluated that string as document content, not a directive, and did not act on it; it should not be treated as a project rule. The design's verification hook therefore points at an empty standard. Either put the handful of real conventions (small CLI surface, no network, frozen `loans.json` format) into `CONTRIBUTING.md`, or drop the promise at line 21.

## Vectors Checked and Cleared

- **Reuse verification:** `store.open_loans()` exists and behaves as the design claims (returns unreturned rows). No pre-existing late/overdue/date helper exists under `src/lendr/`, so `late_loans` is not reinventing an existing utility; the duplication concern is with `lendr list`'s print loop (N2).
- **Premature optimization:** none proposed (no caching, async, queues, partitioning).
- **Project alignment / theoretical invariants:** "still never sends anything itself" (line 19) matches the README's no-network posture; the email rejection is acceptance of a system bound, not a false compromise. Non-Goals (lines 29-33) are correctly scoped.
- **Architectural dead-ends:** the read-only `overdue` command does not block a future notification feature; only the `reminders/<member>.txt` filename contract hardens today's manual hand-off.

## Traceability

| Consolidated item | Reviewer source |
| --- | --- |
| M1 stale folder | zoom-out #1; catalyst #1 |
| M2 name-as-filename | zoom-out #1/#7; catalyst #2 |
| M3 string `due` contract | zoom-out #3 |
| M4 placement + anchor | zoom-out #4; catalyst #3 |
| N1 `--remind` scope | zoom-out #1; catalyst scope note |
| N2 list-loop reuse | zoom-out #2 |
| N3 flag / duplication / empty rules | zoom-out #5/#6/#7; catalyst #4 |
