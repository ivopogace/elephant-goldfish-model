# Stage 7 — Critic Review (Feature Spec): `overdue_reminders.md`

- **Target:** <RUN>/project/docs/designs/overdue_reminders.md
- **Scope:** FeatureRange = lines 1-60 (The Problem, Overview, Goals, Non-Goals, Technical Plan, Alternatives Considered)
- **Reviewers:** egm-design (D), egm-structural (S, structure-map mode), egm-style (Y)
- **Standards:** feature-spec-standard.md (D, S); persona judgment (Y)
- **Baseline context:** <RUN>/project/README.md
- **Date:** 2026-11-10

Reviewers D and S verified the spec's claims against the codebase: `store.open_loans()` exists and filters on `returned`, so the reuse assumption checks out; the spec's output format introduces a second undocumented stdout contract next to `list`'s.

## Consolidated findings (deduplicated, by priority)

### 🔴 Blocker C1 — No Risks & Mitigations section; the standard makes it mandatory and this feature needs it
- **Location:** entire scope (no heading anywhere in lines 1-60); hazards originate at Technical Plan 40-42.
- **Problem:** The feature-spec standard requires explicit failure modes, security implications, and scalability limits with mitigations. The document has no such section, while the in-scope mechanism generates exactly those hazards: file names derived from hand-entered member strings (only a `/` denylist exists, and that guard itself sits out of scope at line 73); silent destruction of previously written notes; and a `reminders/` folder whose location is never pinned — created relative to the current working directory, it can drop member borrowing data into random directories, and a `git add .` from the project root would commit every member's overdue list. Nothing states the folder's gitignore/permission posture, or that `overdue` without `--remind` is guaranteed read-only.
- **Cost:** The document fails the standard on its face, and a fresh implementer ships path-handling and data-loss hazards because no section told them they were hazards.
- **Fix:** Insert `## Risks & Mitigations` after line 51 covering: (a) filename derivation as sanitize + collision-suffix + length-cap, not a denylist; (b) overwrite/loss of already-processed notes with a stated mitigation; (c) pinned `reminders/` location (beside `loans.json`) plus version-control exclusion; (d) explicit statement of no network I/O and no mutation of `loans.json`.
- **Sources:** D1, S-B1, S-M6 (placement half).

### 🔴 Blocker C2 — Alternatives Considered violates the standard's Alternatives Rule
- **Location:** lines 53-59.
- **Problem:** Both rejections are attributed to people ("Rejected by author") with no issue/discussion/PR link — the exact construction the standard bans. The `list` rejection rests on an unverified anecdote ("would break a script one volunteer uses"): the chosen design prints the same fields with extra tokens, so it does not remove that supposed hazard, it adds a second unowned output contract. And the only two alternatives are a UI variant plus the out-of-scope email option — no genuinely different architecture was compared on complexity, cost, performance, or scalability (single dated digest vs per-member files; stdout notes; an additive overdue banner; a separate `remind` command). The highest-risk half of the design (writing files keyed by member name) has zero evaluated alternatives.
- **Fix:** Rewrite with 3-4 real alternatives, each rejected on a concrete trade-off, with decision evidence linked or the rationale restated as pure trade-off. Replace the "breaks a script" claim with either a located script + stated output-format contract + regression test, or drop it. Add one alternative about the reminder-write strategy.
- **Sources:** D2, S-M4, Y12.

### 🔴 Blocker C3 — The feature's only user-visible artifact, the reminder note, is undefined, so Goal 2 cannot be met or verified
- **Location:** Overview 17-19, Goals 25, Technical Plan 40-42.
- **Problem:** Overview promises notes "ready for a volunteer to print or paste into an email"; Goal 2 promises "without retyping loan details"; the mechanism commits only to "listing that member's late tools" — tool names. An implementer following the Plan writes bare tool lines; the volunteer then reopens `lendr list` for due dates and days late — the exact retyping the goal forbids. The stdout format is fully specified; the file body is not.
- **Fix:** Add a content contract: header line, one row per late loan in the same `<tool> due <date> (<n> days late)` form as line 38, closing line. Restate Goal 2 as "a note containing each late tool, its due date, and its days late, produced without opening `lendr list`".
- **Sources:** Y1 (Blocker), S-M1 (Major), Stage-6 finding 6 (same gap).

### 🔴 Blocker C4 — "the folder always reflects the current state" is contradicted by its own mechanism and by `--today`
- **Location:** lines 41-42 vs 50-51; diagram 44-48.
- **Problem:** Overwrite only touches files for members late *now*; a member who returned their tool keeps a stale demand note forever. And `lendr overdue --remind --today 2026-01-01` overwrites the live folder with back-dated content — the flag the document itself adds breaks the "always" claim in the same section. The promised invariant is false as designed, and `write_reminders(rows, folder)` (out of scope, line 64) structurally cannot reconcile prior state from current rows alone.
- **Fix:** Pick one semantics and state it: dated never-mutated snapshot per run, or full reconciliation ("any `reminders/*.txt` whose member has no late loans is removed") with the volunteer-edit loss acknowledged. Add a `generated: <date>` header so a printed note cannot silently misreport. Tie `--today` behavior into the statement (or drop the flag — see Stage 5 M2).
- **Sources:** D5, S-M2, Y9; converges with Stage 5 B1.

### 🟡 Major C5 — The problem chain is cut: visibility is the half the design fixes, delivery is the half that frees the tool, and delivery is undefined
- **Location:** Problem 7-12 vs Overview/Non-Goals 28-32.
- **Problem:** The stated harm is tools "unavailable for weeks", which depends on the member acting, not the volunteer discovering. The spec never says who sends the notes, when, or through what channel — while members have no stored contact data at all (README), making the notes undeliverable by the system. Also the "about one loan in five comes back late" figure is unsourced, describes *returned* loans (which the system cannot even count — no return date is recorded), and cannot be compared with the feature's output.
- **Fix:** Restate the problem as the full chain and scope this feature to the visibility half explicitly ("follow-up delivery remains a manual process owned by <role>"); cite a source for the statistic or reframe it as volunteer observation; tie one goal to a measurable detection-latency statement.
- **Sources:** D3, Y4, S-M8, Stage-5 F1/B2 (adjacent).

### 🟡 Major C6 — Goals are capability statements with no thresholds; the design is unfalsifiable
- **Location:** Goals 22-26.
- **Problem:** "can see all late loans", "can produce notes without retyping" are satisfied by any working command. Only line 26 is objectively testable, without a fixture. Nothing states expected usage, library size, or what counts as failure.
- **Fix:** Convert goals to measurable statements with baseline and target (example given in report: detection latency to ≤ 7 days measured by the note date header; overdue returns all late rows of a 200-loan fixture with zero re-typed fields; a named non-adoption threshold).
- **Sources:** D4, part of D3.

### 🟡 Major C7 — Data-model and input assumptions the promised behavior rests on are unstated
- **Location:** Problem 10-12, Technical Plan 34-38, Goals 26.
- **Problem:** (a) Goal 3's "keep working without conversion" cannot be checked because the `loans.json` row shape (`due` field, returned marker, ISO dates) is described nowhere and the README link is scoped to commands only — a reader can only assume `due` exists. (b) One malformed hand-edited row aborts the whole list; no skip-vs-error rule. (c) `return <tool>` closes every open loan of that tool name and output has no loan id, so two copies of the tile cutter produce indistinguishable rows. (d) Sort tie-breaks and member ordering are unspecified, making output non-deterministic.
- **Fix:** Add an "Assumptions" or "Compatibility and failure behavior" paragraph: name the fields read and their format (extend the line-20 README link to cover the data format), state tool-uniqueness among open loans (or add a disambiguating field), give the skip-and-warn rule for bad rows, and fix the sort key (`due`, then `member`, then `tool`).
- **Sources:** D6, S-M5, Y8; converges with Stage-6 findings 1 and 4.

### 🟡 Major C8 — CLI contract gaps: the spec owns decisions an implementer would have to guess
- **Location:** Overview 17-19, Technical Plan 34-51, diagram.
- **Problem:** Exit codes for "no late loans" vs error are undefined (a volunteer cannot tell "all clear" from "it failed"); zero-result stdout is unspecified; `--today` combined with `--remind` is a footgun (wrong-dated notes) with no rule; whether `--remind` also prints the rows is unstated; the CWD-relative path dependency is unmentioned.
- **Fix:** Specify: exit 0 with an explicit "no overdue loans" message, nonzero on load/parse failure; reminders path resolution; refuse `--today`+`--remind` or embed the supplied date as the note's "as of" date; stdout parity with and without `--remind`.
- **Sources:** D7, Y9 (flag-interaction half).

### 🟡 Major C9 — `--today` is spec-level surface the Overview never admits; its status is unresolved
- **Location:** Overview 14-20 vs Technical Plan 50-51; README step (line 71, out of scope) drops it.
- **Problem:** The user-visible surface is enumerated as `overdue` + `--remind`; `--today` appears first in the Technical Plan with a purely test rationale. Nothing says whether it is a supported flag or a test-only hook — the document contradicts itself about what the command promises.
- **Fix:** Either list it in Overview with "test/debug override, not for normal use", or drop it (see Stage 5 M2) and keep the injection seam in `late_loans`.
- **Sources:** S-M7, D9.

### 🟡 Major C10 — Terminology drift makes the spec's core predicate ambiguous
- **Location:** lines 1, 10, 16-17, 24-25, 30, 36-38, 40-41, 45, 55.
- **Problem:** "overdue" and "late" are never declared identical. Lateness is stated three ways: "due date has passed" (reads time-of-day), "before today" (calendar-day), and "n days late" with no formula (yesterday = 1 or 2?). "Oldest first" plausibly means borrow date, not due date. Goal 1 says "all late loans" while the mechanism reads only *open* ones. The artifact is a "note", then a "file", then an unnamed diagram box; "row" replaces "loan" mid-document. "Sending email" is Non-Goal *will not* in line 30 but *cannot* in line 58 — the reader cannot tell if the decision is reversible — and "storing member email addresses is out of scope" (59) points at a Non-Goal that does not exist.
- **Fix:** Define once: "A loan is late when `due < today`; days late = whole days between." Use one word throughout, one artifact name, "the command" as the sentence subject, reword Goal 1 to "every currently open loan that is past its due date", and align the email statements (Non-Goal: delivery is out of scope; Alternative: rejected on trade-off, not hardware accident).
- **Sources:** Y2, Y3, Y6, Y7, Y10, Y11, Y13, Y14, Y16.

### 🟡 Major C11 — The data-flow diagram misrepresents the mechanism
- **Location:** lines 44-48 vs 40-42, 50-51.
- **Problem:** The branch to `reminders/<member>.txt` hangs directly off the filter, depicting a row-at-a-time write and omitting the mandatory "group by member" stage; `--today` has no input arrow; the conditional nature of the file sink is invisible. Followed literally, an implementer writes inside the row loop and a member's second late loan clobbers their first.
- **Fix:** Redraw: `loans.json --> store.open_loans() --> late-loan filter (today from --today) --> stdout`, and `filter --> group by member --> reminders/<member>.txt (--remind only)`.
- **Sources:** S-M3, Y14 (box name half).

### 🟢 Nit C12 — Non-Goals boundary is blurry where the mechanism contradicts it
- **Location:** lines 28-32 vs 41-42.
- **Problem:** "Changing the storage format" does not obviously exclude writing a new set of files beside `loans.json`, so the Non-Goal reads as contradicting the Overview; and the two obvious follow-on asks (scheduling, sent-state tracking) are not fenced.
- **Fix:** Reword to "Changing the on-disk format or location of `loans.json`", add non-goals for automated delivery/scheduling and reminder-history tracking, and note that `reminders/` holds generated output, not loan state.
- **Sources:** S-M12.

### 🟢 Nit C13 — Scale envelope and read-only guarantee unrecorded
- **Location:** Technical Plan 34-43.
- **Problem:** Full-file load and in-memory filtering are fine at library size, but the assumption is never stated, nor whether `reminders/` grows unbounded; the "overdue with no flag mutates nothing" property that lets a volunteer run it casually is never promised.
- **Fix:** One sentence on assumed scale and folder retention; one sentence guaranteeing read-only behavior without `--remind`.
- **Sources:** D8.

### 🟢 Nit C14 — Code identifiers used as if known; implementation language never stated
- **Location:** lines 36, 50.
- **Problem:** A reader cannot tell whether `store.open_loans()` is existing, new, or convention; `datetime.date.today()` hides that the machine clock and local-midnight flip are decisions.
- **Fix:** One parenthetical: existing helper, file, row fields; one clause on local calendar date semantics.
- **Sources:** Y15; converges with Stage 5 N2.

### 🟢 Nit C15 — Technical Plan granularity overlaps the Detailed Plan with no stated authority
- **Location:** lines 34-51 vs 61-68.
- **Problem:** Both restate sorting and grouping at function-name level; the reader must diff the sections to find which wins when they diverge (they already do on note content).
- **Fix:** Keep Technical Plan to flow + interfaces, add one line naming the Detailed Plan authoritative for helper-level detail.
- **Sources:** S-M10; converges with Stage 5 M1.

### 🟢 Nit C16 — No rollout/adoption statement in contract sections
- **Location:** scope-wide; exists only as out-of-scope README step 4.
- **Problem:** Nothing in Goals promises volunteers learn the command exists, though adoption is the entire point of The Problem.
- **Fix:** One Goal bullet or line: the README documents the command and the launch habit ("run at each check-in").
- **Sources:** S-M9, Stage-5-adjacent (F-notes).

### 🟢 Nit C17 — Grammar/plurality of printed output undefined
- **Location:** line 38.
- **Problem:** "(1 days late)" — singular/plural never decided; minor but it is volunteer-visible text.
- **Sources:** D6 (embedded).

## Cross-reviewer agreement
All three critics independently hit the same three load-bearing spots: the reminder-file semantics (C1/C4/C3 from different lenses), the Alternatives rule violation (C2), and the undefined note contents (C3). The design's reuse of `store.open_loans()` is verified correct.

## Single most important issue in this scope
The spec mandates no risk section while its core mechanism — per-member, name-derived, silently-overwriting PII files in an undefined folder — is exactly the hazard class the standard requires documented and mitigated; no amount of rewording elsewhere makes lines 40-48 safe until that is fixed.
