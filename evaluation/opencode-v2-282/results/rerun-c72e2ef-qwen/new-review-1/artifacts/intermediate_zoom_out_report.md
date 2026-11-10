# Stage 8 — Intermediate Zoom Out Review: `overdue_reminders.md`

- **Target:** <RUN>/project/docs/designs/overdue_reminders.md (full file, lines 1-74)
- **Reviewer:** egm-zoom-out (Skeptical Architect), second pass
- **Standard:** zoom-out-standard.md (plus targeted verification of the two feature-spec-standard compliance citations raised by Stage 7)
- **Prior stage report supplied per the canonical stage:** <RUN>/project/zoom_out_report.md
- **Baseline context:** <RUN>/project/README.md
- **Focus per the stage definition:** the additions and mitigations from the Comprehension (Stage 6) and Critic (Stage 7) stages, which were summarized in the dispatch prompt.
- **Date:** 2026-11-10

Code verification notes from the reviewer (re-checked): `store.open_loans()` already excludes returned rows; rows carry `{member, tool, due (ISO string), returned}`; `close(tool)` flips **every** unreturned row for that tool name; `PATH = pathlib.Path("loans.json")` is CWD-relative; the repo has no `tests/` directory, runner, or dependency. Stage 5's "reuse is correct" verdict still holds.

## 1. Baseline status: nothing was transcribed

The document under review is byte-for-byte the same 74 lines Stage 5 reviewed. No Stage 5 recommendation, and neither intervening stage's additions, were written into the text. What changed is the evidence, not the artifact: Comprehension and Critic independently re-derived the same fault lines from a fresh-reader stance, converting several Stage 5 Majors/Nits into confirmed architecture-level defects — and creating two genuine conflicts between proposed mitigations (§2, IZ1/IZ2).

Stage 5 disposition against the unchanged document: B1 unresolved (worsened); B2 unresolved (now load-bearing on B1's fix); M1 unresolved (worsened — it is the mechanism that hid the `--remind` wiring hole); M2 unresolved (hazard half dissolved by B1's fix, YAGNI half intact); M3 unresolved (worsened — three competing lateness predicates now named); M4 unresolved (worsened — "which folder?" is now an explicit comprehension failure); M5 unresolved (worsened — now also a named feature-spec violation); M6 unchanged, verified in code; N1 becomes moot under B1's fix; N2 and N3 escalated.

## 2. Findings

### IZ1 — Blocker — Two incompatible remediation directions are now stacked (the reminder sink)
- **Location:** cross-cutting; Overview 16-19, Technical Plan 40-49, Detailed Plan 63-66, closing note 73-74.
- **What changed:** Stage 5 offered three options for B1 (stdout, dated digest, harden per-member files). Comprehension then demanded the document *name* the folder location and member-name-uniqueness rule; Critic demanded a *mandatory Risks & Mitigations section* because "per-member, name-derived, overwriting PII files in an unpinned folder" is a hazard class. Those two interventions push toward **harden-and-document the file sink**; Stage 5's preferred option and its N1 push toward **delete the file sink**. The design now carries both directions and chose neither.
- **Why at altitude:** hardening is architectural inflation for zero goal value: it buys sanitization rules, slug+prefix naming, collision handling, folder lifecycle, path pinning, and a Risks section whose only job is licensing a hazard the program created. The standard's minimal-components and workarounds-vs-structural-fix rules reject it. The Overview's promise is "print or paste into an email," which stdout satisfies directly.
- **Committed resolution: cut the persistent per-member file sink.** `--remind` emits one delimited note block per late member to stdout; the volunteer copies, pastes, or redirects. Delete the overwrite sentence (41-42), the file branch of the diagram (47), the folder mention in Overview (17-18), and the `/`-sanitization paragraph (73-74). Add "persistent per-member reminder files — rejected: overwrite cannot express deletion, so the folder cannot reflect current state; it accumulates stale member-identified text on a shared laptop" to Alternatives Considered so no future contributor re-adds it.
- **Collateral resolved by the cut:** staleness + invariant contradiction; filename safety; folder location; PII accumulation; member-name collision as data loss; N1 layering deviation; the `--today` fabricated-date hazard; the hardest item a Risks section would carry; the diagram's false component.

### IZ2 — Blocker — The trigger gap is now load-bearing, and only appears to conflict with the document's output-stability claim
- **Location:** Problem 9-12 vs Overview 16-20, Goals 24-25; Alternatives 55-57.
- **What changed:** Stage 5 B2 said the design replaces accident-driven discovery with habit-driven discovery and never names who runs the command. That was tolerable while `--remind` wrote a folder someone might stumble over; once IZ1 makes stdout the only artifact, an unrun command leaves nothing behind. The two findings must be resolved as one.
- **Conflict escalated and resolved:** B2's fix (an overdue summary inside an existing command) looks like it collides with Alternatives #1's rejection of changing existing output. It does not: that rejection is scoped to `lendr list`'s **row format**; a one-line summary on `lendr loan`/`lendr return` never touches `list` rows.
- **Committed resolution:** print one line such as "3 loans overdue (run `lendr overdue`)" after `lendr loan` and `lendr return`, sourced from the same predicate; state that output-boundary distinction explicitly in Alternatives; name the trigger in Goals. Residual: the unpinned "one volunteer's script" claim must be verified or demoted to an assumption, with the volunteers' late-only-list ask carrying the argument.

### IZ3 — Major — The interface contract is unstated, so Goal 3 and the data-flow diagram are unverifiable
- **Location:** Technical Plan 36-38 + diagram 44-48; Goals 26; Detailed Plan 63-66, 69-71.
- **What changed:** Comprehension proved a fresh reader cannot tell which component filters returned loans: the text says rows arrive from `store.open_loans()` (verified to exclude returned rows), yet the unit-test list asserts "a returned loan (ignored)" — a second filter the diagram never draws. Goal 3's "keep working without conversion" rests on a row schema the document never states and an ISO-`due` coupling it never names. The design's semantics live in a prose fragment, a diagram with a phantom component, and a test list — an inverted spec where tests define the predicate.
- **Committed resolution:** add one "Contract" block to the Technical Plan stating (a) the row keys and ISO-date coupling as the only schema dependency; (b) the single late predicate in words with worked examples (due yesterday ⇒ 1 day late; due today ⇒ not late; inclusive calendar-day difference, local dates) and secondary sort keys (member, tool); (c) ownership — `store.open_loans()` excludes returned loans, `late_loans` does no return filtering — and delete the returned-loan case from the unit-test list (it belongs to store-level coverage). Redraw the diagram to components that actually exist. Fix one canonical term ("overdue" for the command, "late" for the predicate, defined once).

### IZ4 — Major — Goal 2 has no defined deliverable, and `--remind`'s output mode is undefined
- **Location:** Overview 16-19, Goals 25, Technical Plan 40-42.
- **Committed resolution:** define the note at component level: member line; one line per loan (tool, due date, days late); a single generated-on date; fixed closing sentence. Define `--remind` as notes **instead of** the row listing, with rows unchanged when the flag is absent. (The reviewer flags the either/or question as new at this stage — the document never answers it.)

### IZ5 — Major — The output unit ("per member") has no identity anywhere in the data model
- **Location:** Overview 17-18, Goals 25; Non-Goals 31.
- **Why:** member is a free-text string; there are no member IDs (Non-Goal 31 forbids accounts). "Group by member" groups by an unauthenticated string — two identically named people are indistinguishable in the data, the list, and the note, independent of any filesystem.
- **Committed resolution:** state plainly once — the grouping key is the member name exactly as recorded; members sharing a name share one note; fixing that requires member accounts, a declared Non-Goal. Under IZ1 the consequence drops from silent PII merge to a documented cosmetic limit. Document the limit; do not build machinery against it.

### IZ6 — Major — Two overlapping plan sections are how the un-wired flag survived review
- **Location:** Technical Plan 34-51 vs Detailed Plan 61-74, specifically step 2 (67-68).
- **What changed:** Comprehension showed the cost: step 1 defines `write_reminders`, step 2 never calls it — `--remind` is advertised in Overview, Goals, Technical Plan, and the README step yet has no code path. Each section is locally consistent about a different subset, so no reader sees the hole.
- **Committed resolution:** Technical Plan = components, contract, data flow, `--remind` output mode only. Detailed Plan = file-by-file mechanics. Step 2 must enumerate both call sites for whatever sinks survive (stdout path plus the IZ2 summary line). Move lines 73-74 out (deleted under IZ1); move predicate semantics from the test list into the Contract so the test list stops being the spec.

### IZ7 — Major — Compliance items are real, but the cheapest path is the cut, not the paperwork
- **Location:** absent Risks & Mitigations section; Alternatives 55, 58.
- **Verified:** the standard's lines 19-21 do forbid "Rejected by author" without an issue/discussion/PR link; lines 23-27/38-39 do make failure modes and security implications mandatory.
- **Committed resolution:** (a) add a Risks & Limits section whose content is honest *after* IZ1: the program never knows whether a note was sent; a volunteer's own redirect creates a PII copy the volunteer owns and must delete; detection is post-hoc, not preventive; store limits from IZ8. (b) rewrite both Alternatives entries as technical trade-offs; state that rejecting email sending does not reject local generation or local scheduling.

### IZ8 — Major — Unfalsifiable goals plus two verified store defects the design is silent about
- **Location:** Problem 11-12, Goals 24-26, Non-Goals 30-32.
- **Verified in code:** no return date is recorded, so "one loan in five" can never be re-measured; `close(tool)` closes all unreturned rows for a tool name, so with two tile cutters, returning one removes the other borrower from `overdue`, the notes, and the IZ2 banner.
- **Committed resolution:** express Goals as observable at the interface (one command yields the full late list, oldest-first, with days; a note per member with zero retyping — countable from the run itself); declare the outcome metric a **Known limit**, not a goal; record two deferred follow-ups explicitly: optional `returned_on`; per-item identity.

### IZ9 — Nit (downgraded from Stage 5 M2) — `--today`
The hazard argument is moot after IZ1/IZ3 (no folder, no invariant). The YAGNI half stands: drop the flag, test through the injected parameter. If "what was late last week" is genuinely wanted, print the effective date in every run header and note (IZ4 already requires it) and keep the override internal.

### IZ10 — Nit (new at this stage) — The new module exists to host the mechanism being cut
`overdue.py` was justified by testability, but that justification only carried weight because the module also held `write_reminders` disk writes. With the sink gone, the module holds one three-line predicate. Fold `late_loans` into the existing two-module shape (test by importing `cli.py`) and delete step 1's new file — or name a second overdue behavior that justifies it. Either way, state the layout as a decision; and state the test-runner choice as a decision too (the repo has no runner today; this feature silently establishes one).

### IZ11 — Cross-cutting process finding — the pipeline's output has not reached the artifact
Every accumulated item across three stages is still absent from the 74-line document. The next author pass must be a **rewrite pass with a checklist**, not another review pass, or Stage 7 will re-derive these findings a third time. Recommended sequencing: resolve IZ1+IZ2 together (one decision about what the artifact is and who sees it), then IZ3-IZ6 as local edits that follow, then IZ7-IZ8 as section additions, then IZ9-IZ10 as deletions.

## 3. The resolved architecture this stage commits to

Keep the diagnosis and the command; change the artifact and the trigger. `lendr overdue` remains the late-only, oldest-first view of open loans reusing `store.open_loans()` (verified). `--remind` stays but changes sink: per-member note blocks to stdout, generation date included; the volunteer pastes or redirects. The overdue count moves to where volunteers already stand: a one-line summary printed by `lendr loan` and `lendr return`, `list` row format untouched, and that boundary stated in Alternatives. No folder, no overwrite, no filename rules, no new module, no speculative flag; the program still sends nothing.

- **Add:** Contract block · `--remind` output mode and note content · trigger named in Goals · member-name-as-identity limit · Risks & Limits · Known limits + two deferred follow-ups · Alternatives entries for pre-due window, in-command banner, stdout-only notes, and per-member files (rejected with reason) · the test-runner decision.
- **Cut:** `reminders/<member>.txt` and the overwrite sentence · "always reflects the current state" · the `/`-sanitization paragraph · `--today` · the returned-loan unit-test case · "Rejected by author" phrasing · `overdue.py` as a new file · the phantom second filter in the diagram.
- **Move:** format strings/signatures/mechanics → Detailed Plan; predicate semantics → Contract; disk writes out of the compute path; step 2 lists all call sites.

## The single decision the author must make first

Does the reminder artifact stay a set of per-member files on the shared library laptop (and therefore require a Risks section, naming rules, folder pinning, and a deletion story), or does it become text on stdout that the volunteer copies or redirects — because this one answer silently settles staleness, filename safety, folder location, the `--today` hazard, member-name collisions, the diagram, and what the Risks section can honestly say.
