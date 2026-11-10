# Goldfish Review Report — Stage 7 (Critic Review)

**Target:** `<RUN>/project/docs/designs/overdue_reminders.md` (FeatureRange, lines 1–60)

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-design` | completed |
| `egm-structural` | completed |
| `egm-style` | completed |

## Prioritized Findings (Blockers -> Major -> Nits)

### No Risks & Limits section - Severity: Blocker
* **Reviewer Lens:** `egm-design`, `egm-structural`
* **Affected Scope:** whole audited scope, lines 1–60 (absent; also absent through line 74)
* **Discrepancy Description**: The standard makes a risks section mandatory: the spec "must explicitly call out its own constraints" and identify failure modes, security implications, scalability limits, and their mitigations. No such H2 exists, and none appears later in the document. The gap is substantive here: the design overwrites files, derives filenames from member names, and writes plaintext personal data — all unrecorded.
* **Rationale & Recommendation**: Add an H2 `Risks & Mitigations` between `Alternatives Considered` and `Detailed Implementation Plan`, covering path/filename safety, stale reminder files, overwrite and data loss, personal-data exposure, write failures (permissions, disk full, partial runs), timezone/date boundaries, the dependency on `store.open_loans()`, and expected volumes. Each entry needs a mitigation or an explicitly accepted risk.

### Alternatives Rule not met: person-attributed rejections with no linked evidence - Severity: Blocker
* **Reviewer Lens:** `egm-design`, `egm-structural`, `egm-style`
* **Affected Scope:** `Alternatives Considered`, lines 53–59
* **Discrepancy Description**: Both rejections are attributed to people ("Rejected by author:", "volunteers asked for") with no linked issue, discussion, or PR, which the standard forbids. The rationales are one-line anecdotes — "a script one volunteer uses to count loans" — not concrete trade-offs. The `list` rejection is also technically weak: an opt-in `list --late` flag would leave the existing default output untouched, so the stated breakage reason does not survive scrutiny.
* **Rationale & Recommendation**: Link the volunteer feedback and the affected script or PR, or mark them as author assumptions with a date. Replace preference-based reasons with concrete trade-offs (output-contract breakage vs. new surface area, discovery cost, maintenance duplication). Add the alternatives actually available — `list --late`, a machine-readable output mode, one combined reminder file vs. one per member, CSV for mail merge — and state why each loses on complexity, cost, or scope.

### `store.open_loans()` contract and loan record schema assumed - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Technical Plan`, lines 36–37
* **Discrepancy Description**: The design assumes `open_loans()` already excludes returned loans, returns a `due` value directly comparable to a date, and carries member/tool names in the expected shape. None of this is stated or cited. If `due` is a string or returned loans are included, the filter is silently wrong or crashes. Behaviour for a missing or malformed `due` value is unspecified, so one bad record could abort the run or silently drop a late loan.
* **Rationale & Recommendation**: Cite the function's return contract and the `loans.json` field format, including whether `due` is an ISO date or a timestamp, and state the policy for malformed records.

### Date semantics, timezone, and `--today` validation undefined - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Technical Plan`, lines 36–37, 50
* **Discrepancy Description**: The timezone behind `datetime.date.today()` is unstated (library-local vs. UTC vs. laptop clock skew), as is whether `due` can carry a time component and how `--today` is validated. Invalid input (a typo, `2026-13-01`, an empty string) has no specified behaviour.
* **Rationale & Recommendation**: State the timezone contract, define the accepted `due` format, require strict parsing of `--today` with a clear error and non-zero exit, and either justify the flag as shipped interface or scope it as a documented override.

### Unstructured stdout line is ambiguous and injectable - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Technical Plan`, line 38
* **Discrepancy Description**: `<member> <tool> due <date> (<n> days late)` joins free-text fields with spaces and no quoting. Names containing spaces make the line ambiguous; names with newlines, tabs, or control characters can fabricate rows in any script or terminal that consumes the output — including the counting script the spec cites as a reason to protect `list` output.
* **Rationale & Recommendation**: Define the output contract: escaping plus a rule rejecting or stripping control characters, or a machine-readable mode (`--format tsv|json`) with the human layout declared non-parseable.

### Member names become raw file paths without a validation contract - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Overview`/`Technical Plan`, lines 17–19, 40–42
* **Discrepancy Description**: The audited range has no validation, encoding, or collision rule for `reminders/<member>.txt`, so it inherits path traversal (`../`, absolute paths), OS-reserved names, case-insensitive collisions (`Ann` vs `ann`), Unicode normalization collisions, and 255-byte filename limits. The only mitigation anywhere is the `/` rejection at line 73 — outside the spec and insufficient (misses backslash, `..`, leading dots, control characters, reserved names, length).
* **Rationale & Recommendation**: Specify a canonical filename derivation (slug plus a short hash of the raw name), an allowlist or explicit rejection rule, and a normalization decision, and keep that guard in the specification rather than buried in the implementation plan.

### Unconditional overwrite of existing files risks data loss - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-style`
* **Affected Scope:** `Technical Plan`, lines 40–42
* **Discrepancy Description**: "Existing reminder files are overwritten" is unconditional. A pre-existing, user-owned file that happens to share a member-derived name — a pinned note, a draft, a hand-edited letter — is destroyed without warning. The folder's location and version-control status are unstated, so member names could also be committed to git. The warning lives only in the developer-facing plan, where a volunteer deciding to use `--remind` will not see it.
* **Rationale & Recommendation**: Write only into a tool-owned directory, refuse to overwrite files the tool did not create (or require `--force`), state the location and its `.gitignore` requirement, use temp-file-plus-rename for atomic writes, and carry the overwrite warning into the user-facing README documentation.

### "The folder always reflects the current state" is false - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-style`
* **Affected Scope:** `Technical Plan`, lines 40–42
* **Discrepancy Description**: Only members currently late get a file. A member who returned the tool keeps an old reminder listing tools no longer overdue, and the next volunteer may send it. The absolute "always" is a reassurance the logic does not support.
* **Rationale & Recommendation**: Either add an explicit prune step (remove managed files with no remaining late loans, never touch unmanaged files) and report created/updated/removed counts, or state that the files are per-run scratch output and stale files can remain. Replace "always" with what actually happens.

### No write-failure handling or exit-code contract - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Technical Plan`, lines 40–42
* **Discrepancy Description**: Behaviour is unstated for a `reminders/` directory that cannot be created, a read-only folder, disk full, or a mid-run failure. A partial run leaves some members with reminders and others without, and the missing files falsely imply those members are not late. Exit codes on write errors are unspecified.
* **Rationale & Recommendation**: Specify directory-creation semantics, per-file error handling, non-zero exit on any write failure, atomic per-file writes, and a final summary line ("wrote N, updated N, removed N, failed N").

### Personal data exposure unaddressed - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Overview`/`Technical Plan`, lines 17–19, 40–42
* **Discrepancy Description**: Member names are written to plaintext files under the default umask on a shared library laptop, with no permissions, retention, deletion, or access policy, even though the notes are explicitly meant to be printed or pasted into email.
* **Rationale & Recommendation**: Add a risks entry with mitigations: restrictive directory and file modes (0700/0600), a location outside the repository, a retention and deletion rule, and a note that pasted content leaves the machine.

### Unsupported claims carry the motivation, with no success measure - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-style`
* **Affected Scope:** `The Problem`, lines 9–12; `Goals`, lines 22–26
* **Discrepancy Description**: "About one loan in five comes back late", "popular tools such as the tile cutter", "often unavailable for weeks", and the universal "find out … only when another member asks" are unsourced claims carrying the whole justification. No measurement window, count, or source is given. The spec also never states how producing paperwork shortens overdue periods or how anyone will know the feature worked.
* **Rationale & Recommendation**: Source or drop the statistics (CALIBRATE), narrow the "only" claim to observed practice, state the theory of change (volunteer sends note → member returns tool → shorter overdue period), and add a measurable acceptance target.

### The program "never sends anything" duplicates Non-Goals - Severity: Major
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Overview`, line 19
* **Discrepancy Description**: "The program still never sends anything itself" repeats the first Non-Goals bullet in substance, and the absolute "never" adds emphasis without information.
* **Rationale & Recommendation**: DROP; the Non-Goals section already establishes this boundary.

### Section naming drifts from the blueprint vocabulary - Severity: Nit
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `The Problem` (line 7), `Technical Plan` (line 34), `Goals`/`Non-Goals` (lines 22, 28)
* **Discrepancy Description**: "The Problem" vs. "Problem Statement", "Technical Plan" vs. "Proposed Architecture", and Goals/Non-Goals split into two sibling H2s where the standard groups them as one area. Content is present in each case, so this is a labelling and symmetry mismatch.
* **Rationale & Recommendation**: Align names with the standard, or state the mapping, so template conformance is visible to a reviewer diffing against the blueprint.

### Architecture is restated across Overview and Technical Plan - Severity: Nit
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `Overview` (14–20) vs. `Technical Plan` (34–42)
* **Discrepancy Description**: `Overview` already specifies the command, the `--remind` flag, the `reminders/` folder, and the no-sending boundary; `Technical Plan` re-describes the same mechanics. There is no single canonical place for the architecture narrative.
* **Rationale & Recommendation**: Keep the behavioural statement in `Overview` and make `Technical Plan` purely mechanical.

### Data-flow fence has no info string - Severity: Nit
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `Technical Plan`, lines 44–48
* **Discrepancy Description**: The fenced block holds an ASCII data-flow diagram, not code, and the fence carries no language hint. Markdown renders fine and the block is closed.
* **Rationale & Recommendation**: Add a language hint such as `text` for consistency with other technical blocks.

### Empty state and exit status unspecified - Severity: Nit
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Technical Plan`, line 38
* **Discrepancy Description**: What prints when no loan is late, and whether the command exits non-zero when late loans exist or when writes fail, is undefined, so scripts cannot be written against it.
* **Rationale & Recommendation**: State the no-results output and a full exit-code table.

### Sort has no tie-break - Severity: Nit
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Technical Plan`, line 37
* **Discrepancy Description**: "Sorts them by `due`" gives no secondary key, so loans due on the same date order nondeterministically across runs and filesystems; "oldest first" is only well defined once the tie-break is stated.
* **Rationale & Recommendation**: Define a secondary sort (member, then tool) for stable, diffable output.

### Reminder file content under-specified - Severity: Nit
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Technical Plan`, lines 40–41
* **Discrepancy Description**: "listing that member's late tools" does not say whether the file includes due dates, days late, a generation date, return instructions, or contact details, nor its encoding and line endings. A volunteer cannot reliably print or paste it.
* **Rationale & Recommendation**: Include a short sample reminder file and fix its encoding (UTF-8) and structure.

### Diagram omits error and provisioning branches - Severity: Nit
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Technical Plan`, lines 44–48
* **Discrepancy Description**: The diagram shows only the happy path to stdout and `reminders/`, omitting store read errors, invalid dates, write errors, and folder creation.
* **Rationale & Recommendation**: Annotate the failure paths and the directory-provisioning step.

### Scalability limits unstated - Severity: Nit
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** whole audited scope
* **Discrepancy Description**: One file per late member with no bound, no expected loan counts or `loans.json` size, and no note that `open_loans()` likely loads the whole file. The scale is almost certainly trivial, but the standard asks for limits.
* **Rationale & Recommendation**: Add one sentence to Risks & Limits with expected volumes and the point at which the per-file design needs revisiting.

### Redundant purpose clause in Overview - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Overview`, line 18
* **Discrepancy Description**: "ready for a volunteer to print or paste into an email" restates the output medium already implied by "plain-text reminder note".
* **Rationale & Recommendation**: DROP; the sentence is complete without it.

### Repeated meta-attribution "Rejected by author:" - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Alternatives Considered`, lines 55, 58
* **Discrepancy Description**: The document has a single named author and the section is already titled "Alternatives Considered", so "by author" adds no disambiguation.
* **Rationale & Recommendation**: DROP "by author"; write "Rejected:".

### "short list of only the late loans" doubles exclusivity - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Alternatives Considered`, lines 55–56
* **Discrepancy Description**: "short" and "only" both signal exclusivity; "only" does the work.
* **Rationale & Recommendation**: DROP "short".

### Imperative mood in Overview conflicts with declarative prose - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Overview`, lines 16–20
* **Discrepancy Description**: "Add a `lendr overdue` command" and "Add an optional `--remind` flag" read as instructions to an implementer, while the rest of the document describes the design declaratively.
* **Rationale & Recommendation**: CALIBRATE to declarative description ("This design adds…").

## Checks That Pass

* Heading hierarchy is sound: one H1, consistent H2s, no skipped levels, consistent `*` bullets, and a properly closed fenced block.
* The one inline link (`../../README.md`, line 20) resolves from `docs/designs/` to the project README.
* No marketing hyperbole, buzzword vocabulary, or executive-summary filler was found in the audited scope beyond the items above.
