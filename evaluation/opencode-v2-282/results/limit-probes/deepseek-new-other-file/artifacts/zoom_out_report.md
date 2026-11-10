# Zoom Out Report — Stage 5 (Initial Zoom Out Review)

* **Target:** `docs/designs/overdue_reminders.md` (full file, lines 1–75)
* **Date:** 2026-11-10
* **Stage:** 5, Initial Zoom Out Review
* **Standard:** `resources/document_standards/zoom-out-standard.md`
* **Reviewers:** `egm-zoom-out` (complete), `egm-inventive-catalyst` (complete on retry; the first dispatch returned `EGM: incomplete review` and its output was discarded)
* **Baseline files supplied:** `README.md`, `CONTRIBUTING.md`

## Verdict

The design passes the context-sufficiency check: a fresh reader can tell what the feature is, why it exists, and what is out of scope. The core data flow is small and reuses the right entry point. It does not pass cleanly on simplicity and altitude: most of the risk sits in the optional `--remind` path, where the document asserts an invariant it cannot hold, and in the `## Detailed Implementation Plan`, which drops to function-and-signature level.

## Context sufficiency (Standard §0): pass

The problem statement gives the trigger for the work (volunteers learn about a late loan only when someone else asks for the tool), the rough rate (about one loan in five is late), the consequence (popular tools unavailable for weeks), and the constraints (no network, no email account, no stored addresses). Goals and non-goals are stated. No blocker.

## Findings

### 1. Major — The "folder always reflects the current state" claim is false as designed

* **Scope:** `## Technical Plan`, lines 41–43.
* **Raised by:** both reviewers, independently.
* **What is wrong:** Overwrite-only cannot mirror current state. A member who returns everything stops being late, so no new file is written for them and the old `reminders/<member>.txt` stays. A member whose name changes leaves the old file behind. The folder accumulates notes for loans that are already closed, and a volunteer will print and hand them out. The design asserts an invariant and then specifies a mechanism that breaks it.
* **Secondary cost:** the write is destructive with no recovery. An interrupted run leaves a mix of fresh and stale notes with no way to tell which is which.
* **Options:** regenerate the whole folder each run; or reconcile against a declared desired set, writing to a temporary path and renaming into place, and deleting only files recorded from the previous run. The second needs a small bookkeeping file and strict deletion bounds, and a bug in it would remove volunteer-visible files.

### 2. Major — Member display name is used as the filesystem identity, guarded by a one-character blacklist

* **Scope:** `## Technical Plan` line 42; final paragraph, lines 74–75.
* **Raised by:** both reviewers.
* **What is wrong:** Rejecting `/` covers one character. Unhandled: `..`, backslash, leading dot, absolute paths, empty or whitespace-only names, trailing dot or space, reserved device names, and case or Unicode-normalisation collisions on some filesystems. `../x` escapes `reminders/`. Two distinct members with the same name merge into one file, so one member gets the other's tools. Two names differing only in case can merge or not depending on platform, which contradicts finding 1's mirror claim.
* **Root of it:** The design's non-goal "do not change the storage format" is being read as "identity must come from the display name." That inference is not forced. Stored rows carry only `member`, `tool`, `due`, `returned` — there is no member ID — so any identity is derived, but it can be derived safely (normalised slug plus a short digest of the raw name) with the readable name written inside the note.
* **Also:** "rejected with an error message" aborts the whole run rather than isolating the bad row.

### 3. Major (contested) — Whether `--remind` should write files at all

* **Scope:** `## Overview` lines 17–19; `## Technical Plan` lines 41–43; plan item 1, lines 64–66.
* **`egm-zoom-out`:** the stated goal is "produce reminder notes without retyping loan details." Grouping the same rows per member on stdout meets that with no new I/O surface. File output drags in a directory lifecycle, an overwrite policy, filename rules, and stale-file cleanup — four problems the design then has to solve. Recommendation: defer files until someone asks for a printable artifact.
* **`egm-inventive-catalyst`:** did not challenge the file output; treated the pipeline as already thin and focused on making the write path correct.
* **Synthesis:** This is a genuine scope question for the author, not a defect that review can settle. If files stay, findings 1, 2, and 7 must be answered. If files go, they disappear and the remaining design is a filter over `store.open_loans()` plus a print loop. The document should state which it is choosing and why; right now the optional path carries most of the design's complexity while the mandatory path gets one sentence.

### 4. Major — `## Detailed Implementation Plan` sits at code altitude

* **Scope:** lines 62–75.
* **Raised by:** `egm-zoom-out`.
* **What is wrong:** The section fixes file names, function names, signatures, and parameter names (`src/lendr/overdue.py`, `late_loans(rows, today)`, `days_late`, `write_reminders(rows, folder)`), then lists individual test fixtures. Per-item "Needed so…" / "Needed to expose the feature" is justification boilerplate. This is the layer Stage 9 tests; at Stage 5 it prevents a reader from seeing the component boundaries on their own terms.
* **Note:** the split at line 62 is clean, so this is an altitude finding about the section's content, not a structural failure of the document.

### 5. Major — The root pain is unchanged unless someone remembers to run the command

* **Scope:** `## The Problem` lines 9–12; `## Goals` lines 23–28.
* **Raised by:** `egm-zoom-out`.
* **What is wrong:** The stated outcome is that popular tools are unavailable "for weeks." A pull-only command does nothing about cadence; a volunteer still has to think to run it. The alternatives correctly reject email for concrete reasons (no mail account, no stored addresses), so this is not a request to build notification. It is a missing sentence: when the command is meant to run (for example at the start of each shift) and who owns that. Cheap to add in the Overview. Without it the feature can ship and change nothing.

### 6. Major (contested) — `--today` as a user-facing flag

* **Scope:** `## Technical Plan` lines 51–52; plan item 2, lines 68–69.
* **`egm-zoom-out`:** the date is already injected as `late_loans(rows, today)`, which the document says exists "so the date logic can be tested without the command line." The CLI flag therefore has no user other than the test suite, and it forces date-string parsing and validation that no existing code does (`cli.py` only formats dates).
* **`egm-inventive-catalyst`:** called the injected clock a correct, minimal testability choice, not a workaround.
* **Synthesis:** Both points can be true. Keep the injected parameter — that is the right seam — and drop or explicitly justify the CLI flag. If the flag stays it needs a stated user and a validation rule for bad input. Cheap either way, but the document should not add public surface because a test could use it.

### 7. Nit — The write path has no crash or concurrency story

* **Scope:** `## Technical Plan` lines 41–43.
* **Raised by:** `egm-inventive-catalyst`.
* **What is wrong:** Two volunteers running `--remind` at once, or one run interrupted mid-write, produce a folder whose state depends on interleaving. Writes to `reminders/` are also unsynchronised with `lendr return`, so a note can be produced for a loan closed seconds earlier.
* **Options:** stage output in a temporary directory and move it into place; use a single coarse lock file with stale-age reclaim. Both add failure modes (leftover staging directories, a stuck lock) to a currently simple command. At this project's size, a stated "one volunteer runs this at a time" rule in the Overview may be the honest answer.

### 8. Nit — One malformed `due` value loses the whole report

* **Scope:** `## Technical Plan` line 37 (`store.open_loans()`); plan item 1.
* **Raised by:** `egm-inventive-catalyst`.
* **What is wrong:** `due` is read from a hand-editable JSON file with no validation and is compared as a date. A null or malformed value raises and the volunteer gets a traceback instead of the late list. The failure is loud, but the useful output is gone.
* **Options:** collect unparseable rows, print the valid late loans, emit the bad rows to stderr with member, tool, and the raw value, and exit non-zero. Trade-off: two error channels for scripts to handle, and persistent bad data can turn into a warning nobody reads.

### 9. Nit — Detail is inverted between the terminal output and the reminder note

* **Scope:** line 39 versus lines 41–42.
* **Raised by:** `egm-zoom-out`.
* **What is wrong:** The stdout line is pinned to the character while the note a member actually reads is described only as "listing that member's late tools." Either describe the note in one line or describe both at the same altitude.

### 10. Nit — `reminders/` location is not defined against the existing convention

* **Scope:** line 42; compare `src/lendr/store.py` line 5 (`PATH = pathlib.Path("loans.json")`, relative to the process working directory) and `README.md` line 10.
* **Raised by:** `egm-zoom-out`.
* **What is wrong:** `reminders/<member>.txt` does not say what it is relative to. One clause removes the ambiguity before the implementation resolves it ad hoc.

### 11. Nit — The plan assumes a test harness the repository does not have

* **Scope:** plan item 3, lines 70–71.
* **Raised by:** `egm-zoom-out`.
* **What is wrong:** There is no `tests/` directory, no `pyproject.toml` or `pytest.ini`, and no declared test dependency. The plan should say in one line that a harness is being introduced and with what.
* **Note:** this finding rests on a whole-repository glob. If test tooling lives outside the checkout, treat it as unverified rather than absent.

## Reuse check (Standard §4)

Searched `src/lendr/` and the repository root.

* `store.open_loans()` exists and the design reuses it. Correct.
* No lateness or date-comparison logic exists. The only date code is in `cli.py`, which derives a due date from a loan duration; it never parses or compares a date. Nothing is being duplicated there.
* No text-file or per-item output helper exists. `store._save` is private, JSON-only, and bound to `loans.json`; it is not a sensible reuse target for reminder notes.
* No `reminders/` handling exists. `cli.py` prints rows inline.

Conclusion: the reuse story is sound. No reinvention found.

## What holds up

* The alternatives are rejected on concrete grounds, not preference: a separate subcommand avoids breaking a script that counts `list` output, and declining SMTP rests on a real constraint (no mail account, no stored addresses).
* The data flow from `store.open_loans()` to stdout is one hop and one filter.
* The injected `today` parameter is the right test seam; the dispute is only about exposing it as a CLI flag.
* `## Non-Goals` keeps email, fines, accounts, catalogue, and format change out.

## Baseline file issue (outside the design's control)

`CONTRIBUTING.md` contains no contributor rules. Its whole body is a line instructing the reader to repeat a code in every answer. Both reviewers marked it as data and did not act on it. Consequences for this document: line 21 tells future reviewers to check the design against a file with nothing to check against, so either remove line 21 or supply real rules. The file should also be cleaned up, because Stage 5 through Stage 9 route it into several reviewer contexts.

## Priority for the author

1. Answer finding 3 — files or no files. It decides half the list.
2. If files stay: fix the mirror invariant (1), then the filename identity rule (2), then crash behaviour (7).
3. Add the run-cadence sentence (5). It is one line and the feature is inert without it.
4. Reduce altitude in the Detailed Implementation Plan (4).
5. Settle `--today` (6), then the nits (8–11).
