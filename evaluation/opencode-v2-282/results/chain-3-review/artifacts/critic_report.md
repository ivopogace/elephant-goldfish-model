# Goldfish Review Report — Stage 7 (Critic Review)

**Target:** `docs/designs/overdue-reminders.md` (FeatureRange lines 1-174)

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-design` | completed |
| `egm-structural` | completed |
| `egm-style` | completed |

## Prioritized Findings (Blockers -> Major -> Nits)

### 1. Missing mandatory "Risks & Mitigations" section — Severity: Major

* **Reviewer Lens:** `egm-design`, `egm-structural`
* **Affected Scope:** Document-level structure; nearest anchors "Growth and cost" (115-117) and "Alternatives Considered" (119).
* **Discrepancy Description:** The Feature Specification Standard requires the specification to "explicitly call out its own constraints" and "identify potential failure modes, security implications, scalability limits, and how they will be mitigated," and lists "Risks & Mitigations" as a mandatory area. The document has no risks section. Failure modes appear only inline in CUJ 3 and the Technical Plan, scalability appears only in "Growth and cost," and security implications are absent entirely.
* **Rationale & Recommendation:** Add a dedicated "Risks & Limits" section covering at minimum: non-ISO `due` values, the all-malformed false all-clear, non-array JSON roots and OS-level read errors, the scalability ceiling and archival strategy, output injection from untrusted `member`/`tool` values, and an explicit security note (offline, read-only, no network, path handling), each with likelihood, impact, and mitigation.

### 2. The all-malformed case still produces the false all-clear — Severity: Major

* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 59, 69, 79, 84-85, 188.
* **Discrepancy Description:** CUJ 3 promises "The command never prints 'No overdue loans.'" when the data contains a malformed due date, and the strict loader's stated purpose (line 69) is to prevent exactly that false all-clear. But the specified behavior for a malformed `due` is skip-with-warning and exit 0 (lines 79, 84), and an empty late set renders "No overdue loans." (line 85). If every open row has a missing or malformed `due`, the command prints "No overdue loans." — the precise false all-clear the design claims to prevent. The CUJ and the rendering/error specs contradict each other.
* **Rationale & Recommendation:** Track skipped rows; if any row is skipped, either exit non-zero, print a summary line (e.g., "N rows skipped: malformed due date"), or suppress "No overdue loans." when skips > 0. Add a CUJ and test for the all-malformed case.

### 3. The on-disk `loans.json` schema and `due` format are undefined, and `fromisoformat` is version-dependent — Severity: Major

* **Reviewer Lens:** `egm-design`, `egm-comprehension` (cross-stage), `egm-zoom-out` (cross-stage)
* **Affected Scope:** Lines 67, 72, 74, 78-79, 186, 188; data-flow diagram.
* **Discrepancy Description:** The lateness rule depends on `datetime.date.fromisoformat(row["due"])`, which requires a strict ISO 8601 date string, and its accepted syntax varies by Python version (3.11+ accepts basic and week formats; earlier versions accept only `YYYY-MM-DD`). The document never states the on-disk `loans.json` schema, the type/semantics of `returned` (boolean flag versus return date), or the format of `due`. It also references `store.PATH` and the existing lenient `_load()` without defining the path-resolution rule or the current loader's error behavior. If existing rows use another format, every row is treated as malformed and the feature silently degrades to zero overdue loans.
* **Rationale & Recommendation:** Add a short "Current state" paragraph describing the on-disk schema, `PATH` resolution, and the existing lenient loader's behavior. Document the actual `due` format; add a test fixture taken from a real `loans.json`; pin the minimum Python version and the exact `fromisoformat` semantics; if legacy formats exist, specify a parser or migration.

### 4. `format_list` needs the open-loan count, which the specified query interface never produces — Severity: Major

* **Reviewer Lens:** `egm-design`, `egm-zoom-out` (cross-stage), `egm-comprehension` (cross-stage)
* **Affected Scope:** Lines 85, 87, 196; data-flow diagram lines 91-113.
* **Discrepancy Description:** The output contract requires "the open-loan count" (lines 85, 196), and the architecture claims the renderers "share one late set, so the file is read once per run" (line 87). But `format_list(loans, today, path)` receives only the late set, `today`, and `path`; the open-loan count is not derivable from those arguments, and `len(loans)` is the overdue count, not the open count. Either `overdue_loans()` must also return the open count, or the CLI must read/count separately, contradicting the read-once claim. The document also never defines "the open-loan count" versus "the total count," and `today` must be computed once to avoid a midnight-rollover mismatch.
* **Rationale & Recommendation:** Change `overdue_loans()` to return a result object (late set, open count, skipped count) or add an `open_count` parameter to `format_list`, and update the data-flow diagram and CLI wiring accordingly. Define both counts explicitly and compute `today` once in the CLI. Specify whether `path` is `store.PATH` or `store.PATH.resolve()`.

### 5. `--notes` scope contradicts the Phase 2 deferral — Severity: Major

* **Reviewer Lens:** `egm-design`, `egm-zoom-out` (cross-stage), `egm-comprehension` (cross-stage)
* **Affected Scope:** Lines 21, 39, 49-53, 86, 197-198, 211, 226-229.
* **Discrepancy Description:** Goals (line 21) and CUJ 2 (lines 49-53) list `--notes`/`format_notes` as deliverables, and the Technical Plan specifies `format_notes` and the `--notes` flag in detail (lines 86, 197). But Open Questions says "Phase 1 ships the listing only, so this is deferred to Phase 2" (line 39), and Staging (lines 228-229) repeats the conflict: item 2 includes `format_notes`, while Phase 1 is described as "list output only." A reader cannot determine whether notes are in the first release, and the Phase 1 test plan cannot be satisfied as written.
* **Rationale & Recommendation:** Reconcile the scope: either mark notes as a Phase 2 deliverable consistently across Goals, CUJs, Technical Plan, and Staging (and remove the `--notes` test/E2E from Phase 1), or state explicitly that Phase 1 ships `--notes` and remove the deferral.

### 6. Unquantified performance and scale claims; no scalability ceiling — Severity: Major

* **Reviewer Lens:** `egm-design`, `egm-style`, `egm-comprehension` (cross-stage)
* **Affected Scope:** Lines 115-117.
* **Discrepancy Description:** "Growth and cost" asserts the command is "sub-second" at "a plausible library scale" and references "the ten-second budget," but neither the scale (row count, file size) nor the budget is defined, measured, or sourced. The design also acknowledges unbounded growth (returned rows are kept forever) with no ceiling, compaction, or archival strategy. The standard requires scalability limits and mitigations; an unquantified "sub-second" claim is an unbacked performance assertion.
* **Rationale & Recommendation:** Quantify expected data (loans/year, maximum file size), state where the ten-second budget comes from and how it will be measured, define a documented ceiling (e.g., X rows / Y MB), and specify a mitigation if the file outgrows it (archive returned loans, or an explicit unsupported-size limit).

### 7. Non-array JSON roots and OS-level read errors escape the promised error contract — Severity: Nit

* **Reviewer Lens:** `egm-design`, `egm-zoom-out` (cross-stage)
* **Affected Scope:** Lines 22, 59, 72, 84, 184, 188.
* **Discrepancy Description:** The design promises "error handling for missing or unreadable data" (line 22) and a "loud, actionable stderr diagnostic and a non-zero exit" for missing/corrupt data (line 59). But `read_rows()` is specified to raise `DataFileError` only for a missing file or invalid JSON (lines 72, 184). Valid JSON that is not an array (`null`, `{}`, `"x"`) would pass `read_rows()` and likely crash later with an unhandled `TypeError`/iteration error; a permission-denied file, a directory, or a non-UTF-8 file raises `OSError`/`UnicodeDecodeError`, which are not wrapped. A missing `due` is `None`, and `datetime.date.fromisoformat(None)` raises `TypeError`, not `ValueError`.
* **Rationale & Recommendation:** Validate that the parsed root is a `list` and raise `DataFileError` otherwise; catch `OSError`/`UnicodeDecodeError` and re-raise as `DataFileError` with an actionable message; catch `(ValueError, TypeError)` or guard a missing/non-string `due`; add tests for these cases.

### 8. Rendering trusts untrusted `member`/`tool` values — Severity: Nit

* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 85-86, 196-197.
* **Discrepancy Description:** The renderers print `member` and `tool` values directly, one line per loan. A value containing newline or control characters can break the one-line-per-loan contract, forge extra entries, or inject text into the hand-deliverable notes. No escaping or sanitization is specified.
* **Rationale & Recommendation:** Define a rendering contract (strip/reject control characters, truncate long fields, or explicitly document that values are trusted) and add a test with a newline in a field.

### 9. Concurrency and torn reads are unaddressed — Severity: Nit

* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 63-67, 117, 136.
* **Discrepancy Description:** Concurrency is mentioned only to reject a cron daemon (line 136). But the existing `loan`/`return` commands write `loans.json`; a concurrent write during `lendr overdue` can produce a torn read that either raises `DataFileError` or, if the torn content is still valid JSON, silently yields a wrong late set. No locking, atomic-write, or retry strategy is specified, and the single-user assumption is not stated.
* **Rationale & Recommendation:** State the concurrency assumption explicitly (single-user CLI, serialized runs) and/or specify that `DataFileError` is the intended behavior for a torn read; if concurrent use is plausible, recommend atomic writes (temp file + rename) or a retry.

### 10. "Rejected by author" attribution without a linked issue/discussion/PR — Severity: Nit

* **Reviewer Lens:** `egm-design`, `egm-structural`, `egm-style`
* **Affected Scope:** Lines 125 (Alternative A) and 131 (Alternative B).
* **Discrepancy Description:** The Alternatives Rule states rejection rationales "must not attribute a rejection to a maintainer without linking their issue, discussion, or PR." Alternatives A and B read "Rejected by author: out of scope" with no link. The trade-offs themselves are documented in the Cons, so the substance is present; the attribution is the violation. The rejection provenance labels are also internally inconsistent ("by author" vs. "during ideation" vs. "Not chosen").
* **Rationale & Recommendation:** Replace "Rejected by author" with a rationale grounded in the documented constraints (e.g., "Rejected: the data model has no contact information and the offline/no-send constraint rules it out"), or link the issue/discussion/PR. Standardize the rejection labels or define the stages.

### 11. Uncalibrated claims carry the problem statement — Severity: Nit

* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Overview (line 11), The Problem (line 15).
* **Discrepancy Description:** "which misses loans" (line 11) asserts a failure mode with no evidence; "The scan is slow and error-prone" (line 15) mixes an unmeasured performance claim ("slow") with a subjective quality judgment ("error-prone"); "one fast, read-only check" (line 15) repeats the unmeasured performance claim for the proposed solution. These claims carry the feature's justification.
* **Rationale & Recommendation:** CALIBRATE — replace with observable facts or cite evidence (e.g., "the manual scan depends on a volunteer noticing each due date; no record is kept of missed loans").

### 12. Alternative C's con is factually inaccurate — Severity: Nit

* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Alternative C (line 136).
* **Discrepancy Description:** "a background writer would add concurrency on a store with no locking" mischaracterizes the alternative. A cron job or daemon running the read-only `lendr overdue` command is not a writer; the feature performs no writes. The con is factually inaccurate.
* **Rationale & Recommendation:** CALIBRATE — restate the con in terms of the actual risk (e.g., a long-running process competing with CLI writes, if that is the concern).

### 13. Alternatives D and F rest on uncalibrated claims — Severity: Nit

* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Alternatives D and F (lines 142-143, 154).
* **Discrepancy Description:** "there is no query load", "the data set is small", and "there is no SLA" are uncalibrated claims about existing conditions. No evidence is provided, yet they justify rejecting alternatives.
* **Rationale & Recommendation:** CALIBRATE — cite the data size/usage or reframe as explicit assumptions.

### 14. "Token cost is zero by design" is irrelevant to an offline CLI — Severity: Nit

* **Reviewer Lens:** `egm-style`, `egm-comprehension` (cross-stage)
* **Affected Scope:** Growth and cost (line 117).
* **Discrepancy Description:** "There is no network, database, or LLM, so token cost is zero by design" introduces LLM/token-cost concepts irrelevant to an offline standard-library CLI. The claim supports no reader decision and may suggest an LLM or API is involved.
* **Rationale & Recommendation:** DROP.

### 15. "Loud, actionable" diagnostic is a subjective, unverifiable requirement — Severity: Nit

* **Reviewer Lens:** `egm-style`, `egm-comprehension` (cross-stage)
* **Affected Scope:** CUJ 3 (line 59), Data path (line 71), item 1 (line 183), item 2 (line 198).
* **Discrepancy Description:** The document requires "a loud, actionable stderr diagnostic" and a "user-facing message" but never specifies what the message says or what action it directs the user to take. "Loud" is editorializing; "actionable" is unverifiable, and a test cannot assert the diagnostic without a defined message.
* **Rationale & Recommendation:** CALIBRATE — describe the diagnostic's content (e.g., "a one-line stderr message naming the file and error").

### 16. "A stale note is worse than none" is a subjective judgment — Severity: Nit

* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Alternative E (line 148).
* **Discrepancy Description:** "a stale note is worse than none" is a subjective quality judgment presented as fact.
* **Rationale & Recommendation:** CALIBRATE — state the concrete failure (e.g., "a stale note could misinform a volunteer about which loans were already reminded").

### 17. "Two small helpers" and "the current lenient loader" are subjective — Severity: Nit

* **Reviewer Lens:** `egm-style`, `egm-comprehension` (cross-stage)
* **Affected Scope:** Technical Plan (line 63), Data path (line 67).
* **Discrepancy Description:** "two small helpers" and "the current lenient loader" are subjective characterizations; "small" is unmeasured and "lenient" is a quality judgment about existing code.
* **Rationale & Recommendation:** CALIBRATE — describe size/behavior concretely (e.g., "two helper functions", "the existing loader, which ignores a missing file").

### 18. "Clearly delimited" relies on a subjective adverb — Severity: Nit

* **Reviewer Lens:** `egm-style`
* **Affected Scope:** CUJ 2 (line 53), Command wiring (line 86).
* **Discrepancy Description:** "clearly delimited" is repeated and relies on a subjective adverb. The requirement is better stated as a concrete delimiter.
* **Rationale & Recommendation:** CALIBRATE — specify the delimiter (e.g., a heading or separator line).

### 19. Inconsistent bold-label colon placement in the metadata block — Severity: Nit

* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** Lines 3-5 vs. all other labeled bullets (e.g., 45-47, 51-53, 57-59, 123-125).
* **Discrepancy Description:** The header metadata uses `**Author:**`, `**Status:**`, `**Date:**` (colon inside the bold span), while every other labeled bullet in the document uses `**Given**:`, `**When**:`, `**Then**:`, `**Pros**:`, `**Cons**:`, `**Reason for Rejection**:` (colon outside the bold span).
* **Rationale & Recommendation:** Pick one convention.

### 20. "Reason for Rejection" restates the Cons in most alternatives — Severity: Nit

* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Alternatives A-I (lines 123-173).
* **Discrepancy Description:** The "Reason for Rejection" field restates the Cons in most alternatives (A-H), adding no new information.
* **Rationale & Recommendation:** DROP or consolidate — keep the field only where it records a decision (who rejected it and when).

## Strengths Worth Keeping

* Strict H1 → H2 → H3 heading hierarchy with no skipped levels; clean section boundaries.
* Mandatory Feature Spec sections present: Problem Statement, Goals & Non-Goals, Proposed Architecture (with a data-flow diagram), and a substantive Alternatives Considered section (nine alternatives with Pros/Cons and reasons).
* Explicit Non-Goals and consistent rejection of cron/DB/cache/grace-period/holiday-calendar/extra-module alternatives.
* A pure, injectable-today lateness function; a single read per run; a strict-vs-lenient loader split that prevents the false all-clear.
* Defensive caveats reviewed and classified KEEP (no action): "never sends anything itself," "No file is written and nothing is sent," "The command never prints 'No overdue loans.'", "There is no grace period, business-day calendar, or timezone handling," "forbids non-standard-library imports and any sending library."
