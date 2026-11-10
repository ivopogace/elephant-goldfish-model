# Stage 5 — Initial Zoom Out Review — `overdue_reminders.md`

- **Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (full file, lines 1–75)
- **Standard applied:** `resources/document_standards/zoom-out-standard.md` (bundle root `/home/user/egm-runs/egm-c72e2ef/bundle`)
- **Reviewers:** `egm-zoom-out` and `egm-inventive-catalyst`, dispatched in parallel as fresh isolated sessions (2026-11-10). Results consolidated by the primary agent.
- **Baseline context (GoldfishContext):** user supplied none; linked-file discovery added `README.md` (inside the project). The design's link to `../../AGENTS.md` was **excluded**: this harness forbids reviewers from reading `AGENTS.md`. The contributor-rules cross-check the design asks for (line 21) was therefore **not performed** and remains an open item for a stage or process that is allowed to read those rules.
- **Fact-check note:** the primary agent independently confirmed the code claims used below — `store.open_loans()` exists and matches the design (store.py L30–31), `due` is stored as an ISO string (cli.py L21), there is no member id and no member-name validation in `store.add` (store.py L16–19), no `tests/` directory exists, and output paths follow the module-level `store.PATH` pathlib convention (store.py L5).

## Verdict

No blockers. Context sufficiency passes: the problem, goals, and non-goals are clear, and the read half of the feature (`lendr overdue` printing late loans via `store.open_loans()`) is the right minimal, convention-consistent extension. The design's real risk sits entirely in the `--remind` write path: it is an added mechanism that brings most of the design's complexity with it, one stated guarantee it cannot actually deliver, and a security-shaped workaround that does not close the hole it targets. The inventive pass adds one strategic challenge: the feature is built as something volunteers must remember to run, while the stated problem is that overdue information never arrives unrequested.

## Consolidated findings

### 🟡 Major 1 — The reminder folder's stated guarantee is false under the stated mechanism
**Scope:** Technical Plan, lines 41–43 ("Existing reminder files are overwritten so the folder always reflects the current state").
The design only writes files for members who are late *today*. A member who was late on Monday and returned everything on Tuesday has no rows on Tuesday, so nothing overwrites Monday's file — the folder keeps holding an outdated accusation, and the "always reflects the current state" claim fails by construction. Making the claim true requires a delete/reconcile step the design never mentions. As written, the invariant and the mechanism do not match.
*Sources: catalyst F2; zoom-out F1(c).*

### 🟡 Major 2 — The `--remind` per-member file branch is self-inflicted complexity
**Scope:** Overview L17–19; Technical Plan L41–49; Detailed Plan L66–67; L74–75.
The goal is "produce reminder notes without retyping loan details" (L26), and the notes are meant to be copied into an email (L18–19). Printing member-grouped blocks to stdout — which a volunteer can copy or redirect — meets that goal without a persistent folder. Choosing one saved file per member is what forces everything downstream: the filename sanitization (L74–75), the overwrite semantics problem (Major 1), and a folder volunteers must remember to walk through, which repeats one layer down the very failure mode in the Problem section. The cheapest version of the feature deletes lines 41–43, 66–67, and 74–75 outright.
*Sources: zoom-out F1; catalyst F2 (scaling of N opens/N prints against the no-retyping goal).*

### 🟡 Major 3 — Human display names used as file identity; the one-character filter is a band-aid
**Scope:** Detailed Implementation Plan, final paragraph (L74–75).
`reminders/<member>.txt` couples identity to a path component. Rejecting names containing `/` blocks one failure mode but not the class: two members with the same or case-variant name silently merge into one file (verified: `store.add` has no member id or name checks, store.py L16–19); `..` segments and other unsafe forms remain; renames orphan old notes. Per the standard's "workarounds vs. structural fixes," this should be flagged as an unexamined defect class, not a settled detail. Note it inherits an existing repo habit (loans are keyed on tool-name strings, store.py L22–27), so the design is building on an acknowledged weakness rather than fixing the placement of identity handling.
*Sources: zoom-out F1(b); catalyst F3. Catalyst's stronger resolution: if output becomes a single regenerated digest (Major 1/2 fix), filename derivation disappears entirely.*

### 🟡 Major 4 — Success depends on the habit that is the stated problem
**Scope:** The Problem L9–12; Overview L16–19.
The problem is that overdue information never reaches a volunteer unless someone asks. The design answers with two pull surfaces: a command someone must remember to run, and a folder someone must remember to open, print, and paste. "The program never sends anything" is a fixed system bound, so sending is off the table — but that bound does not foreclose placing the signal where volunteers already are. The catalyst proposes one concrete option: print a short overdue count at the end of `lendr loan`/`lendr return` output (or stderr), which sends nothing, keeps `lendr list` byte-identical so the volunteer's counting script survives, and needs no new habit. Liabilities the reviewer declared: an extra read of `loans.json` on write paths, habituation if volume grows, and possible breakage of unknown scripts parsing `loan` stdout (mitigate via stderr). Minimum acceptable alternative: state in Goals who runs `lendr overdue`, how often, and what adoption would look like — the current text leaves success unassigned.
*Sources: catalyst F1.*

### 🟡 Major 5 — `--today` is a permanent public flag justified by a reason the design already satisfies itself
**Scope:** Technical Plan L51–52 vs. Detailed Plan L64–67, L70–71.
The flag's stated purpose is repeatable tests, but item 1 already injects the clock as a parameter (`late_loans(rows, today)`), explicitly "so the date logic can be tested without the command line," and the listed tests are data-level cases that need no CLI flag. So the flag adds user-facing parsing and validation surface for a rationale that exists elsewhere in the same document. If it is kept, the real justification (volunteer what-if queries, e.g. "what will be late next Friday") should be written down; also warn that a future `--today` produces misleading "days late" wording. Either drop the flag or state its user-facing purpose.
*Sources: zoom-out F3; catalyst F5.*

### 🟡 Major 6 — The most consequential decision was never put through Alternatives Considered
**Scope:** Alternatives Considered L54–60.
Both recorded alternatives concern the read path (extend `list`, send email). Neither the "overdue list only, no `--remind`" option nor the single-file/stdout shape was examined, so the file-writing branch entered the design unchallenged. Both rejections are also "by author" with no stakeholder attribution for the requirement that generated files persist on disk.
*Sources: zoom-out F2.*

### 🟢 Nit 7 — Altitude drops in the Detailed Implementation Plan
**Scope:** L64–72; also the exact output string at L38–39.
Helper identifiers, the `days_late` integer, the literal print format, and a four-case test list at function granularity are implementer-level detail. Freezing a new output string at design time also creates the same breakage hazard the document cites to protect `lendr list` (L56–58), with no stated consumer of the new format yet.

### 🟢 Nit 8 — Undefined seams: who parses the date, and where `reminders/` lives
**Scope:** L37, L41–43, L51–52 vs. code.
`due` is an ISO *string* in storage (cli.py L21), `--today` is a date, and `days_late` is an integer — nothing says which component parses, so the one new module's interface is ambiguous, and ISO strings happen to sort correctly by luck (lexicographic = chronological), which hides the missing contract until someone changes the format. Separately, `reminders/` is a hard-coded location while the repo's convention for file paths is the module-level `store.PATH` pathlib constant; reusing that pattern keeps state redirection in one place (and inherits the working-directory dependence, which deserves one acknowledging sentence). Also state the boundary rule: store owns row schema, `overdue` owns lateness policy.

### 🟢 Nit 9 — Item 3 quietly scopes in the repo's first test harness
**Scope:** L70–71; L52.
Verified: there is no `tests/` directory, no test files, and no packaging or runner configuration. Adding `tests/test_overdue.py` implies choosing a runner and solving imports from a `src/` layout with no install metadata — a project-wide decision compressed into one plan line. Either keep tests harness-free (plain assert script, consistent with a repo with no test culture) or name the tooling choice as separate work. This also weakens Major 5 further: with no harness, the `--today` testability argument has no host.

### 🟢 Nit 10 — Failure behavior is only ever "abort and name the loan"
**Scope:** L74–75; absence of any failure policy in Technical Plan.
Nothing covers malformed `due` values, missing fields, or an unwritable/absent `reminders/` folder. Since "existing `loans.json` files keep working without conversion" is a goal (L27), hand-maintained heterogeneous rows are expected input, so all-or-nothing failure means one bad row withholds every member's reminder. Suggested shape: skip bad rows, report a count and the offenders prominently, exit non-zero, and check folder writability before producing output — degrading to hard failure if every row is unreadable.
*Sources: catalyst F4.*

### 🟢 Observation 11 — The "one in five" baseline is anecdotal
**Scope:** L11. No measurable baseline or success metric is defined anywhere; tied to Major 4's adoption question. Noted, not blocking.

## What the reviewers verified as sound
- Reuse is correct, not reinvented: `store.open_loans()` matches the design; no existing lateness/date utility or text-file helper was skipped; `datetime.date.today()` matches existing style.
- No migration needed: the design adds no fields and `due` is already ISO-8601, so Goal L27 holds.
- Root-problem alignment with README holds: read-only, sends nothing, consistent with "no network access" (README L10) and the Non-Goals.
- The rejected `lendr list` alternative is technically accurate: `list` prints raw fields (cli.py L24–26), so changing it could break a parser.
- No premature optimization: no caching, async, queues, or speculative plugin layers; the "no sending / no network" bound was correctly treated as an invariant, not a compromise.

## Open items carried out of Stage 5
1. Contributor-rules cross-check against `AGENTS.md` (requested at design L21) — reviewers could not read it; needs an approved path outside the Goldfish protocol.
2. Whether `--remind` persists at all (Majors 1, 2, 6) is the single decision to settle before implementation; Majors 3–5 follow from keeping it.

## Reviewer traceability
| Consolidated | Zoom-out | Catalyst |
|---|---|---|
| Major 1 | F1(c) | F2 |
| Major 2 | F1 | F2 |
| Major 3 | F1(b) | F3 |
| Major 4 | — | F1 |
| Major 5 | F3 | F5 |
| Major 6 | F2 | — |
| Nit 7 | F4 | — |
| Nit 8 | F5 | — |
| Nit 9 | F6 | — |
| Nit 10 | — | F4 |
| Obs 11 | caveat | — |
| No blockers; core read path sound | verdict, verification | step 0 (balanced elements) |
