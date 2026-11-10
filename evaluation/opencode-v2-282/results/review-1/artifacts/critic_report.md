# Goldfish Review Report

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (`FeatureRange lines 1-60`)

**Stage:** 7 — Critic Review

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-design` | completed |
| `egm-structural` | completed |
| `egm-style` | completed |

## Prioritized Findings (Blockers -> Major -> Nits)

### Missing Risks & Limits / Risks & Mitigations section - Severity: Blocker
* **Reviewer Lens:** `egm-design`, `egm-structural`
* **Affected Scope:** Entire FeatureRange, lines 1-60 (most acute in Technical Plan, lines 34-51)
* **Discrepancy Description**: The Feature Specification Standard's "Risks & Limits" requirement states the specification must "explicitly call out its own constraints" and identify failure modes, security implications, scalability limits, and their mitigations, and lists "Risks & Mitigations" as a required area. The document has no Risks & Mitigations (or equivalent) section anywhere in scope — the mandatory-area sequence runs Problem -> Goals/Non-Goals -> Architecture (Technical Plan) -> Alternatives, then stops. Risks plainly apply to this feature (unvalidated member names used as filenames, silent overwrite of existing reminder files, date-boundary and `--today` determinism, unbounded file creation), so the section cannot be dismissed as inapplicable. The only constraint note, the `/`-in-name rejection at lines 73-74, sits outside the review scope and is an implementation detail, not a risks section.
* **Rationale & Recommendation**: Add a Risks & Mitigations section that enumerates each failure mode, security implication, and scalability limit and states its mitigation, so a fresh reader can confirm the risks were addressed.

### Alternatives rejection attributed to "author" without a link - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-structural`, `egm-style`
* **Affected Scope:** `## Alternatives Considered`, lines 55-59
* **Discrepancy Description**: Both rejection rationales open with "Rejected by author:" and provide no issue, discussion, or PR link. The standard's Alternatives Rule states that rejection rationales "must not attribute a rejection to a maintainer without linking their issue, discussion, or PR." The underlying rationales are otherwise concrete (breaking an existing volunteer script; no mail account and email storage out of scope), but the attribution form violates an explicit prohibition and, per `egm-style`, is redundant in the author's own design record.
* **Rationale & Recommendation**: Drop the "Rejected by author" attribution and lead with the technical/scope trade-off; if the decision originated from a maintainer, link the specific issue/discussion/PR.

### Stale reminder invariant is logically false - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Technical Plan, lines 40-42
* **Discrepancy Description**: The design asserts "Existing reminder files are overwritten so the folder always reflects the current state." This invariant is false: overwriting only applies to members who currently have late loans. A member who returns a tool keeps a stale `<member>.txt`, so the folder can retain reminders for loans that are no longer late and does not reflect current state. This is an unbacked assertion about system behavior.
* **Rationale & Recommendation**: Either delete/clean reminder files for members with no late loans before writing, or correct the claim to "reminder files for members with late loans are overwritten" and document that stale files require manual removal. Add a test for the member-returns-tool case (the current test plan at lines 69-70 does not cover it).

### Member names used as file paths create a path-traversal risk - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Technical Plan, lines 40-42 (introduces `reminders/<member>.txt`); the partial mitigation at line 73 is outside the reviewed range and incomplete
* **Discrepancy Description**: Member names are used directly as file paths, creating a path-traversal / arbitrary-file-write risk. A name such as `../../<something>` or an absolute path could write outside `reminders/`. Line 73 rejects names containing `/`, but the reviewed range specifies no validation, and even that mitigation is incomplete (`..` components, reserved names, trailing dots/spaces on Windows, and other separator forms are unaddressed).
* **Rationale & Recommendation**: Within the reviewed range, specify a strict allowlist/sanitization rule (safe characters only; reject `.`/`..`, path separators, and reserved names) or map members to safe slug/ID-based filenames, and document the rejection behavior.

### Uncalibrated statistics in the Problem Statement - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-style`
* **Affected Scope:** `## The Problem`, lines 11-12
* **Discrepancy Description**: "About one loan in five comes back late" and "popular tools such as the tile cutter are often unavailable for weeks" are stated as facts with no source, sample size, or time window. Both are claims about existing behavior that outrun the evidence in the document; "about," "popular," and "often" are unquantified hedges.
* **Rationale & Recommendation**: Cite the source (e.g., `loans.json` history over a stated period) or soften to qualitative language ("a significant share of loans come back late"). `egm-style` classifies this as CALIBRATE.

### `reminders/` folder creation is unspecified - Severity: Nit
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Technical Plan, lines 40-42
* **Discrepancy Description**: The plan says the command writes into a `reminders/` folder but never states whether the folder is created when absent. If it does not exist, `--remind` fails at runtime — an unaddressed failure mode.
* **Rationale & Recommendation**: Specify `mkdir -p`-style creation, or document the precondition and the error behavior.

### Goals lack measurable success criteria - Severity: Nit
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `## Goals` and `## Non-Goals`, lines 22-32
* **Discrepancy Description**: Goals are stated as capabilities with no measurable success criterion (e.g., reminders produced per run, reduction in manual date-checking, time saved).
* **Rationale & Recommendation**: Add one or two measurable success metrics, or explicitly state that success is qualitative.

### Redundant defensive scope reassurance - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `## Overview`, line 19
* **Discrepancy Description**: "The program still never sends anything itself" duplicates the Non-Goals entry "Sending email or text messages" (line 30) and the README's "There is no network access." It names no concrete reader or operator decision, and "still" and "itself" are filler emphasis.
* **Rationale & Recommendation**: DROP — the constraint is already carried by the Non-Goals list and the README.

## Passed Checks
* **Structure:** Heading hierarchy is sound (single H1, all sections at H2, no skipped or out-of-order levels). Formatting is clean — bullet lists, numbered list, and the fenced code block are well-formed. The single link `[project README](../../README.md)` (line 20) resolves correctly from `docs/designs/` to the project-root README.
* **Standard substance:** Problem Statement, Goals/Non-Goals, Proposed Architecture, and Alternatives Considered are present and substantive.
