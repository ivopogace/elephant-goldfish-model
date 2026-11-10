# Stage 5 — Initial Zoom Out Review

* **Target:** `docs/designs/overdue_reminders.md`
* **Date:** 2026-11-10
* **Reviewers:** egm-zoom-out (Skeptical Architect), egm-inventive-catalyst (TRIZ)
* **Standard:** `resources/document_standards/zoom-out-standard.md`
* **Scope:** Full file
* **Ticket:** EGMEVAL_PARENT_7e0672ab3b11
* **Run markers:** EGMEVAL_GLOBAL_7e0672ab3b11, EGMEVAL_PROJECT_7e0672ab3b11, EGMEVAL_CONFIGURED_7e0672ab3b11, EGMEVAL_NESTED_7e0672ab3b11, EGMEVAL_OTHER_7e0672ab3b11

Context sufficiency (Standard §0): **passes**. The objective, motivation, non-goals, and success criteria are all stated. The findings below concern scope discipline, altitude, reuse, and interface definition.

## Summary of judgement

The design solves a real, narrow problem: volunteers cannot see which open loans are late. The core command (`lendr overdue`, filter open loans by due date, sort oldest first) is small, reuses `store.open_loans()`, and fits the existing CLI. That part survives review.

The `--remind` half does not. It roughly doubles the design surface, introduces a filesystem-as-output-channel design with two hard-to-reverse decisions (member name as filename, overwrite-as-reconciliation), and its note format — the feature's actual deliverable — is unspecified while the stdout line is pinned to the character. Separately, the design claims alignment with `CONTRIBUTING.md`, which contains no contributor rules to check against.

## Findings

### F1. `--remind` folder is speculative scope (Major)

**Scope:** Overview (lines 17–19), Goals (line 26), Detailed Implementation Plan steps 1 and 3.

The Problem section and the only quoted volunteer feedback (Alternatives, lines 56–58) ask for *visibility* of late loans; nothing in the document shows anyone asked for pre-written files. `--remind` adds a second output channel, directory creation, per-member grouping, filename derivation, an overwrite policy, a new module, and new tests. The Overview concedes the program still sends nothing, so the volunteer still prints or pastes by hand — the saving over copying a line of stdout is small.

Simpler path meeting the stated goals: `lendr overdue` alone; if grouping is wanted, a `--by-member` formatting option on stdout rather than a filesystem artifact. `cli.py` already owns printing (`src/lendr/cli.py:24-26`).

### F2. Overwrite does not make the folder reflect current state (Major)

**Scope:** Technical Plan (lines 41–43), Detailed Implementation Plan step 1 (line 65).

A member who returns their tools disappears from `store.open_loans()` (`src/lendr/store.py:30-31`), so `write_reminders` never rewrites — and never removes — their old `reminders/<member>.txt`. The folder therefore keeps notes for loans that are no longer late, contradicting the stated guarantee. Closing the gap needs either deleting files in a user-facing folder the program did not create, or a manifest of files written last run. Also unaddressed: a crash between per-member writes leaves a mixed old/new set, and volunteer-edited notes are destroyed with no ownership rule.

Options: (a) one file per run (`reminders/<date>.txt`) containing all members — no cleanup logic, no staleness; (b) stage the full set in a temp directory and publish by replacing the directory — not atomic on every platform, changes ownership/permissions, manual edits still lost; (c) a manifest of tool-owned files deleted after successful writes — new state that can drift. Option (a) is the only one that removes the problem instead of managing it.

### F3. Member name is used as a filename and as identity (Major)

**Scope:** Technical Plan (lines 41–43, 74–75).

Rejecting only `/` treats "member name is a safe, unique, case- and normalization-stable key" as an invariant. It is not: `..` and other path components, absolute paths, leading `-`, `\` on Windows, reserved names (`CON`, `NUL`), trailing dots/spaces, control characters, over-long names, `Alex`/`alex` collisions on case-insensitive filesystems, and NFC/NFD variants are all unhandled. Because writes overwrite unconditionally, a collision silently drops one member's note or attributes it to the wrong member. Rejecting those names also denies the reminder feature to those members.

The design also never says where `reminders/` is rooted (CWD or next to `loans.json`), while `store.PATH` is CWD-relative (`src/lendr/store.py:5`) and the README says loans live "next to the program." Using the filesystem as the identity key means any later change (stable member IDs, renames) forces this feature to be rewritten.

If files are kept, define one sanitization rule (slug plus a short stable digest, e.g. `alex-3f9c2a.txt`), validate the whole target set for collisions before writing, and state one root. Filenames become less readable, the digest must stay stable across platforms, and existing files need migration.

### F4. Contributor alignment claim cannot be verified (Major)

**Scope:** Overview (lines 20–21).

Line 21 says to check the design against `CONTRIBUTING.md`. That file contains no contribution rules, conventions, module layout, or test policy. There is nothing to check against, so the claimed alignment is unsupported. Either the reference is wrong or the file is a placeholder. Related: the repository has `src/lendr/{__init__,cli,store}.py` only — no `tests/`, no `pyproject.toml`, no dependency manifest — so step 3 presumes a test harness that does not exist and should say how tests are run.

### F5. Altitude is misallocated in the Detailed Implementation Plan (Major)

**Scope:** Detailed Implementation Plan (lines 62–75).

The section spends its budget on helper names and signatures (`late_loans(rows, today)`, `write_reminders(rows, folder)`) and an enumerated test-case list, while leaving the real interface decisions unstated:

* The return shape of `late_loans` (rows mutated with a `days_late` key, tuples, or a dataclass) is a coupling decision between `overdue.py` and `cli.py` printing, presented as boilerplate.
* The reminder note content and format — the actual deliverable of `--remind` — is described only as "listing that member's late tools," while the stdout line is specified to the character (line 39). Does the note include due date, days late, a greeting, a return address? Unstated.
* `days_late` boundary semantics are undefined for a `due` value carrying a time component, and for the local-date/timezone boundary implied by `datetime.date.today()`.

The test-case enumeration belongs in the test file. State the return contract and the note format; drop the case list.

### F6. New module splits ownership of one projection (Major)

**Scope:** Technical Plan (lines 37–39), Detailed Implementation Plan step 1 (lines 64–67).

`store.py` already owns the row schema and the "open" projection in `open_loans()`. `late_loans` is the same projection with one more predicate plus arithmetic, so placing it in `store.py` keeps one module authoritative over loan state and lets `cli.py` stay a thin printer. A separate `overdue.py` leaves "what is an open loan" and "what is a late loan" in different files that must agree on the schema. The stated justification — testable date logic without the command line — is already satisfied by the `today` parameter wherever the function lives; it argues for dependency injection, not a new module. If a separate module is chosen, say why (for example, it will also own note rendering).

### F7. Due-date parsing is assumed, not specified (Major)

**Scope:** Technical Plan (line 37), Goal line 27.

"Keeps the rows whose `due` date is before today" never states whether `due` is compared as an ISO string or parsed to a date. `cli.py` writes `due.isoformat()` (`src/lendr/cli.py:20-21`), so string ordering works for new data, but `store._load()` reads arbitrary JSON (`src/lendr/store.py:8-9`) and the design promises legacy files keep working. A legacy `due` in another format yields silently wrong ordering, or a `ValueError` that `list` does not raise. A malformed row can also crash after stdout was printed and midway through reminder writes.

Choose and state one policy: parse with `datetime.date.fromisoformat`; on failure, either fail fast before any output with the offending loan named on stderr and a non-zero exit, or skip-and-warn with a separate diagnostic section. Never generate reminders from an invalid set. Note the costs: a new exit-code and stderr contract, one corrupt row blocking all reminders, and strict parsing possibly rejecting historical formats.

### F8. `--today` is public CLI surface added for tests (Nit)

**Scope:** Technical Plan (line 51).

The testability seam already exists as the `today` argument to `late_loans`. Every CLI flag must be documented, validated (bad dates), and maintained, and its only stated consumer is the test suite. Pass a date into the function from tests; drop the flag — unless it is intended as a user-facing feature (reconstructing a report as of a past date), in which case say so and give it a user story.

### F9. Rejected alternative conflates two different changes (Nit)

**Scope:** Alternatives Considered (lines 56–58), Technical Plan (line 39).

"Mark late loans inside `lendr list`" (mutates existing output, breaks a volunteer's counting script — a fair rejection) is not the same as an additive `list --late` filter or a shared row formatter. The additive option is the cheapest reuse path and was never evaluated. The cost of skipping it is already visible: `cli.py:25` prints `member tool due`, and the new command introduces a second, divergent format, so the codebase now has two print paths over the same rows. At minimum, explain why a second subcommand beats a flag on the existing one.

### F10. Two symptoms bundled, one addressed (Nit)

**Scope:** The Problem (lines 9–12), Goals (lines 25–28).

Volunteers cannot tell what is late, and popular tools are unavailable "for weeks." Only the first is addressed; a report changes neither the return rate nor the availability of the tile cutter. That is defensible, but the design should say explicitly that reducing late returns is out of scope and why visibility is expected to help, or drop the second symptom.

## Reuse verification

Source tree searched: `src/lendr/` (`__init__.py`, `cli.py`, `store.py`); no `tests/`, no dependency manifest, no helper or utility modules.

* `store.open_loans()` (`src/lendr/store.py:30-31`) exists and is correctly reused.
* No existing late/overdue, date-arithmetic, grouping, or file-writing helper exists, so `late_loans` / `write_reminders` do not reinvent a project utility.
* The reusable assets the design bypasses are structural: the module boundary in `store.py` (F6) and the print path in `cli.py:24-26` (F9).
* Date handling already appears in `cli.py:20`; the new command should not add a third date idiom.

## Architectural dead-ends

F2 and F3 are the hard-to-reverse decisions, and both come from using the filesystem as the output channel. Replacing that with a single stream, or a single per-run file, removes both and most of the design's complexity at once. A `--remind` flag that must coexist with `--today` and future filters invites flag-combination growth on a command whose job is a read-only report.

## Contradiction check (inventive catalyst)

A genuine contradiction exists — snapshot correctness versus treating `reminders/` as a durable folder the program does not own — and is covered by F2. No other false compromise was found: the small offline CLI with a JSON file has no throughput, durability, or scaling trade-off to eliminate. Proposals that would add staging directories or manifests are recorded in F2 only as alternatives, with their costs, and are not recommended.

## Recommended direction

1. Keep `lendr overdue` as a stdout-only report; make `--remind` justify itself or cut it to a single per-run file.
2. Move the late predicate next to `open_loans()` in `store.py`; keep `cli.py` a thin printer and one date idiom.
3. Replace the helper-function and test-case enumeration with a return contract, a note format (if reminders stay), and a stated due-date parsing policy.
4. Fix the contributor-rules reference and say how tests are run in a repository with no test harness.
