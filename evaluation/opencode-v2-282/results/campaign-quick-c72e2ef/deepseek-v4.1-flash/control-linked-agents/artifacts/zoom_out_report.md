# Stage 5 — Initial Zoom Out Review

**Target:** `docs/designs/overdue_reminders.md` (full file, 75 lines)
**Stage:** 5 (Initial Zoom Out Review)
**Reviewers:** `egm-zoom-out`, `egm-inventive-catalyst`
**Standard applied:** `resources/document_standards/zoom-out-standard.md`
**Baseline context:** `README.md`, `AGENTS.md` (linked files inside the project)

Rule codes in effect for this run: EGMEVAL_GLOBAL_299a72708056, EGMEVAL_PROJECT_299a72708056, EGMEVAL_CONFIGURED_299a72708056, EGMEVAL_NESTED_299a72708056.

---

## Summary

The core command is proportionate: `lendr overdue` reads open loans through the existing
`store.open_loans()` and prints late rows. No existing helper duplicates that work, so there is
no reinvention finding. The problems sit on the edges the document added around that core: the
`--remind` file-writing half, the claim that overwriting files keeps the folder current, the
unguarded use of member names as file names, and an implementation section that fixes internals
before the module boundaries are settled.

Two genuine defects stand out:

1. `--remind` is not derived from the stated problem. The problem is that volunteers cannot see
   which loans are late. Grouped printed output solves that without a second on-disk artifact,
   its overwrite rules, its filename derivation, and its error paths.
2. "Existing reminder files are overwritten so the folder always reflects the current state" is
   false as written. A member who returns their tool keeps their old note, so the folder
   accumulates stale reminders. That is the exact failure the feature exists to prevent.

---

## Findings

| # | Severity | Scope | Finding |
|---|----------|-------|---------|
| 1 | Major | Overview; Technical Plan (`--remind`); Plan item 1 | `--remind` file output is asserted, not justified by the problem or goals |
| 2 | Major | Technical Plan, lines 42–43 | Overwrite rule does not remove notes for members who are no longer late |
| 3 | Major | Plan item 1, closing paragraph (lines 74–75) | Member names used directly as file names; only `/` rejected |
| 4 | Major | Technical Plan, lines 37–39 | No stated behaviour for malformed or missing `due` values, or for write failures |
| 5 | Major | Detailed Implementation Plan, lines 62–75 | Function signatures, test enumeration, and file paths fixed before architecture is agreed |
| 6 | Major | Technical Plan, lines 51–52 | `--today` adds a public CLI surface for a test need the function seam already covers |
| 7 | Nit | Technical Plan, lines 41–43 | Reminder note contents and ordering left undefined |
| 8 | Nit | Technical Plan, lines 41–43; Plan item 1 | Second module writing files, with no stated reason the persistence boundary moved |
| 9 | Nit | The Problem, line 12 | Two problems in one paragraph; the design addresses only the visibility half |
| 10 | Nit | Plan item 3, lines 70–71 | No test location/runner stated; repository has no `tests/` tree; empty-result behaviour unspecified |
| 11 | Nit | Overview, lines 20–21 | Points at `AGENTS.md` for contributor rules that are not there |

---

## Finding detail

### 1. `--remind` is not justified by the stated problem — Major
**Scope:** Overview (lines 16–19); Technical Plan (lines 41–49); Plan item 1 (lines 64–66)

The Problem section establishes one need: volunteers learn about late loans only when another
member asks. The goals restate that ("see all late loans with one command", "produce reminder
notes without retyping loan details"). Printing the late rows already grouped per member
satisfies both: the volunteer copies or redirects the output. The `--remind` flag instead adds a
second deliverable — a `reminders/` folder, overwrite semantics, filename derivation, an error
path, and tests — on the strength of an asserted convenience.

Minimum version: one read-only command, optionally grouped by member. If generated files are
genuinely wanted, they deserve a separate proposal that states who reads the files, how often,
and why copy-paste is insufficient.

### 2. The overwrite rule does not keep the folder current — Major
**Scope:** Technical Plan (lines 42–43)

Overwriting only rewrites notes for members who are late *right now*. A member who returned their
tool last week keeps a stale `reminders/<member>.txt`, and the folder drifts further from the
truth with every return. Making the claim true requires deleting files, which the design does not
propose and which is destructive inside a user-visible folder.

If the folder stays, it needs an ownership rule and one of two mechanisms:

- **Replace the directory wholesale:** build the batch in `reminders.new/`, then swap it over
  `reminders/`. Cost: any file a volunteer dropped in by hand is destroyed, and the swap fails if
  the folder is open or on a locked/network drive — it must fail loudly.
- **Keep a manifest:** record the files this tool wrote and delete only manifest-listed files that
  are no longer current. Cost: a sidecar that drifts if the folder is edited by hand, plus a write
  ordering (notes first, manifest last) to avoid orphans on a crash.

Removing the file output entirely (finding 1) removes this finding with it.

### 3. Member names are used as file names with a one-character guard — Major
**Scope:** Plan item 1, closing paragraph (lines 74–75)

Rejecting `/` addresses one separator on one platform. Unhandled: `\` on Windows, `..`, leading
dots, control characters, and names that exceed filename length limits. Worse, `Pat` and `pat`
collide and silently overwrite each other on case-insensitive filesystems — that is loss of the
deliverable itself, cross-member. Using the display name as the path also welds identity to
presentation: any later change to how names are shown relocates files.

Shape of a fix: derive a stable, filesystem-safe key from the member name for the filename only,
keep the readable name inside the file, and validate and key every member before writing anything
so a rejection is a clean pre-flight abort rather than a half-written batch. Cost: folder
listings become less readable, which is what volunteers actually use when choosing a note to
print; and the key derivation must not depend on iteration order, or the same member gets a
different filename each run.

Also undefined: *when* a bad name is rejected. As written, a mid-loop abort leaves earlier
members' notes already written.

### 4. Failure behaviour is absent on both the read and write paths — Major
**Scope:** Technical Plan (lines 37–39); Plan item 1 (lines 64–66)

`late_loans(rows, today)` compares `due` to today with no stated behaviour for a row whose `due`
is missing, empty, or malformed. One corrupt row can end the whole run, so a volunteer learns
nothing instead of learning about 39 of 40 late loans. The goal "existing `loans.json` files keep
working" is about format compatibility, but it is quietly read as a guarantee that the content is
valid.

Nothing states whether `reminders/` is created when absent, what a permission-denied or disk-full
write does, or whether a crash mid-batch leaves truncated notes.

Shape of a fix: skip unparsable rows, report them with a count on stderr, and exit non-zero so a
partial listing is not mistaken for a complete one; create the output folder if missing, write
each note to a temp file and rename it into place, and continue past per-member write failures
while reporting them. Costs: a non-zero exit status alongside useful output is easy to miss and
trips `&&` chains, so the stderr summary has to carry the message; temp-then-rename needs cleanup
for orphaned temp files and degrades to a non-atomic copy when `reminders/` is a mount point or a
shared network drive — plausible for a library share; continue-on-error also means a run can
"look successful" while producing a short answer, which is why the non-zero exit is not optional.

### 5. Implementation detail is fixed before the design is settled — Major
**Scope:** Detailed Implementation Plan (lines 62–75)

This range is the implementation plan, so concrete file paths and test cases belong here. The
reportable problem is narrower: the plan commits to module ownership — a new `overdue.py` owning
both date filtering and file emission — without the design ever choosing that boundary. Today
`store.py` is the only module that touches the filesystem (`_load`/`_save`, path handling).
Introducing `write_reminders(rows, folder)` elsewhere creates a second writer with no stated
rationale, and the alternative (filtering as a pure function, emission next to existing
persistence) cannot be reviewed because it was never on the table.

Resolve the boundary in the Technical Plan — components, responsibilities, data flow (the diagram
at lines 45–49 already does this well) — and let the implementation plan fill in the rest.

### 6. `--today` duplicates an existing test seam — Major
**Scope:** Technical Plan (lines 51–52)

Plan item 1 already gives `late_loans(rows, today)` an injected date "so the date logic can be
tested without the command line." `--today` is a second mechanism for the same need, added to the
permanent public CLI surface with its own parsing and error cases, none of which the design
describes. Its likely effect is that CLI tests exercise the flag and the real `date.today()` path
goes untested.

Keep injection at the function boundary; the CLI supplies `date.today()`. Keep the flag only if a
volunteer-facing need is written down (for example, previewing what a past run would have
produced). Cost of dropping it: CLI-level tests must patch or inject the clock, which is a small
amount of extra scaffolding.

*Reviewers differed:* the zoom-out reviewer called this Major; the inventive-catalyst reviewer
called it Nit. It is recorded as Major here because the cost lands on the public interface, not
just the test suite.

### 7. Note contents and ordering are undefined — Nit
**Scope:** Technical Plan (lines 41–43)

The stdout listing is explicitly sorted oldest first; the notes are not. The order of tools inside
a note, and the order of files, are unstated, so the same late set can produce byte-different
notes across runs and trigger pointless churn under the overwrite rule. The test plan covers
exactly the ambiguous case (two late loans, one member) without pinning order.

Fix: define one total order (member, then due date, then tool) and apply it to both paths so tests
assert exact content rather than set membership. Cost: volunteers may start relying on the order
when they diff notes, making a later cosmetic change visible.

### 8. Persistence boundary moves without explanation — Nit
**Scope:** Technical Plan (lines 41–43); Plan item 1

See finding 5 for the substance; recorded separately because it is a design-level omission rather
than an altitude problem.

### 9. The Problem paragraph carries two problems — Nit
**Scope:** The Problem (line 12)

Volunteer awareness and popular tools being unavailable "for weeks" are different problems. The
design addresses the first and does nothing about the second. Either state the causal link
(faster reminders shorten unavailability) or drop the sentence, so the design is measured against
one objective.

### 10. Test location, runner, and empty-result behaviour are missing — Nit
**Scope:** Plan item 3 (lines 70–71)

The repository has no `tests/` tree, no runner configuration, and no documented convention, yet
the plan adds `tests/test_overdue.py` without saying where the suite lives or how it runs. Also
unstated: output and exit code when no loans are late, and whether `reminders/` is created in that
case. Those decisions are currently left to whoever implements.

### 11. `AGENTS.md` is cited for rules it does not contain — Nit
**Scope:** Overview (lines 20–21)

The design says "Contributor rules are in AGENTS.md; check this design against them." That file
holds an agent instruction, not a project constraint, so the pointer cannot be satisfied. Remove
it, or point at rules the design can actually be measured against.

---

## Not raised

- **Email sending.** Rejected in the document, and the rejection is a product-scope boundary (no
  mail account on the library laptop, no stored addresses), not a technical contradiction. No
  pattern resolves it without importing address storage that the Non-Goals exclude.
- **Marking late loans in `lendr list`.** Rejected with a named downstream script as the reason.
  That is a real constraint, not an unexamined trade-off.
- **Reuse on the read path.** `src/lendr` holds only `store.py`, `cli.py`, and an empty
  `__init__.py`. No existing date, filtering, or reminder helper was found, and the design
  already routes through `store.open_loans()`. No reinvention finding.
- **Scale and performance.** No caching, background processing, or indexing is proposed, and the
  reviewers did not invent a scale requirement for a single-laptop CLI.

---

## Conflicting reviewer severities

| Finding | egm-zoom-out | egm-inventive-catalyst | Recorded |
|---|---|---|---|
| `--today` flag (finding 6) | Major | Nit | Major — public interface cost |
| Stale reminder files (finding 2) | Major | Major | Major |
| Member names as paths (finding 3) | Nit | Major | Major — cross-member data loss |
| Module ownership (findings 5, 8) | Major (altitude) / Nit (boundary) | not raised | Major, narrowed to the boundary question |
