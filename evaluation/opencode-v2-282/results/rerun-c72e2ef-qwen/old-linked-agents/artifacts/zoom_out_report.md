# Stage 5 — Initial Zoom Out Review: Overdue Reminders for lendr

* **Target:** `docs/designs/overdue_reminders.md` (full file, lines 1–75)
* **Standard applied:** `/opt/egm-v2/bundle/resources/document_standards/zoom-out-standard.md`
* **Reviewers (fresh Goldfish sessions, no conversation history):** `egm-zoom-out`, `egm-inventive-catalyst`
* **GoldfishContext passed:** `README.md`, `AGENTS.md` (the two in-project links found in the design doc; no other links, no URLs, no external paths)
* **Date:** 2026-11-10
* **Run scope requested by author:** Stage 5 only

---

## Verdict

The listing half of this design is sound and passes the zoom-out standard: `lendr overdue` reads through the existing
`store.open_loans()`, solves the stated discovery problem directly, adds no schema change, no network access, no cache,
no queue, and no new abstraction.

The reminder half does not pass. `--remind` introduces a new on-disk artifact whose central promise — that the
`reminders/` folder "always reflects the current state" — cannot be delivered by the mechanism chosen (overwrite
existing files, never delete). It also invents a second, unmanaged write path outside the module that owns persistence,
uses raw free-text member names as filesystem keys, and leaves the folder's location undefined. One blocker and five
major findings sit on this one flag. The clearest path forward is to cut `--remind` from v1 and ship the listing, or
re-specify the note subsystem completely before any code is written.

---

## Consolidated findings

### 🔴 Blocker B1 — `--remind` cannot deliver the freshness invariant it claims, and the folder's location is undefined
**Scope:** Overview (16–19), Technical Plan (40–43), Detailed Plan step 1 (64–67), line 75.
**Sources:** zoom-out F1; catalyst F1; catalyst F4.

The design states existing reminder files are overwritten "so the folder always reflects the current state." Overwriting
is only half of mirroring. A member whose loans have all been returned no longer appears in the grouped rows, so their
`reminders/<member>.txt` is never rewritten and never removed. Stale notes persist and still look current to a volunteer
printing the folder. The failure is social, not cosmetic: volunteers nag members who already returned the tool, which is
the exact symptom "The Problem" says the feature exists to end.

Two gaps make it worse:

1. **Where is `reminders/`?** The design never says. `store.py` resolves `loans.json` against the current working
   directory while the README says the file lives "next to the program" — an existing ambiguity the design inherits
   silently. Running the command from another directory creates a second, unrelated folder.
2. **`--today` combined with `--remind`** lets a test-only clock override rewrite live artifacts against a fabricated
   date. No guard is specified.

**Resolutions offered by the reviewers.** (a) Cut the flag (see M1). (b) Make each run produce a fresh immutable batch
directory, e.g. `reminders/<run-date>/`, so stale notes are simply not part of the newest batch instead of being
deleted. (c) Pin the folder to one data directory anchored on the loans file path, created with
`mkdir(parents=True, exist_ok=True)`, and refuse `--today` with `--remind` unless a batch directory is named.

**Trade-offs of (b)/(c):** batch directories grow without bound, so a retention rule is new cleanup logic plus a policy
decision about who may delete volunteer data; a "latest" pointer is needed and is unreliable on Windows, USB, and synced
folders; interrupted runs leave half-created batches unless a temp-then-rename convention is added; anchoring the path
changes behavior for anyone relying on CWD-relative placement.

### 🟡 Major M1 — `--remind` is scope the document does not evidence a need for (YAGNI)
**Scope:** Overview (17–19), Goals (26), Technical Plan (40–43), Alternatives Considered (56–60), lines 74–75.
**Sources:** zoom-out F2.

The stated root problem is discovery: volunteers do not know which loans are late. `lendr overdue` solves that. Writing
one file per member solves a different problem — transporting loan details into an email or printout — for which the
document offers no evidence. The user-need quote the author cites ("volunteers asked for a short list of only the late
loans") supports the listing only. The design also concedes the delivery path is dead: the program "still never sends
anything itself" and the library laptop has no mail account, so the generated files still have to be carried to a human
who prints or pastes them. The flag therefore buys the elimination of retyping, and pays for it with B1, M2, and M5 in
full.

A minimal alternative that gets the same benefit: print late loans, and additionally print a member-grouped block
(`member: tool, tool, ...`) a volunteer can copy per person, reusing the rows already fetched. Note also that lines
74–75 exist only because files-per-member exists; orphan rules at the top of a design are a reliable YAGNI tell.

### 🟡 Major M2 — Member names used as filesystem keys; failure ordering unspecified
**Scope:** lines 74–75; the `overdue.write_reminders(rows, folder)` boundary.
**Sources:** catalyst F2; zoom-out F1.

Member names are raw free text from `lendr loan <member> ...`. Rejecting `/` treats one character as if it closed the
problem. Unspecified: `..` traversal; `\`, `:`, `*`, `?`, `"`, leading dots, control characters on other platforms (the
library laptop's OS is never stated); two members with the same, case-differing, or diacritic-equivalent names silently
colliding into one note that exposes both people's tools; and whether an abort happens before or after any file is
written, which can leave a half-updated folder — a failure sitting directly on top of B1's mirror claim.

**Resolution offered:** a naming boundary owned by the reminders writer — Unicode-normalize, allow-list
`[A-Za-z0-9._-]`, append a short hash on collision, keep the human-readable name inside the note body, validate every
row before writing a byte, write to temp files then rename.
**Trade-offs:** filenames stop mapping one-to-one to people, so a slug-to-member manifest is one more artifact that can
go stale; sanitization, collision handling, and atomic rename are new code and new tests in a project whose whole
selling point is being small; temp-then-rename is not atomic across FAT/USB or network shares.

### 🟡 Major M3 — New side-effecting file I/O is placed outside the layer that owns persistence
**Scope:** Detailed Plan step 1 (64–67); data-flow diagram (46–48).
**Sources:** zoom-out F3.

Verified by reading the code: `store.py` is the only module that touches disk (private `_load`/`_save`, one `PATH`), and
`cli.py` imports only `store`. Putting `write_reminders(rows, folder)` in a new `overdue.py` creates a second, parallel
write path outside the store, with its own implicit directory-creation and overwrite semantics, breaking the one
convention the codebase actually has. `overdue.py` would also be internally incoherent: `late_loans` is a pure query,
`write_reminders` is an effectful writer, so one module becomes both repository and reporter.

**Resolution offered:** keep only the pure selection next to `open_loans()` in the store and let the CLI print; or, if
notes are genuinely needed later, give `reminders/` its own small store module that owns its path and lifecycle.

### 🟡 Major M4 — The simpler alternative is rejected on an unverified premise, leaving two overlapping output commands
**Scope:** Alternatives Considered (56–58); Goals (25); Overview (16).
**Sources:** zoom-out F4; catalyst F3.

Marking late loans inside `lendr list` is rejected because changing `list` output "would break a script one volunteer
uses to count loans." That premise has no owner, no verification, and no trace in the README; `cli.py` prints
space-separated rows with no documented format, so the script is a phantom contract. If it does exist, the real problem
is that `lendr list`'s stdout is an undocumented public interface, and the fix is to pin that contract in the README. As
specified, `list` and `overdue` print the same rows in two slightly different formats that will drift, and step 3
contains no test pinning any stdout shape — the contract nobody documented is also the contract nobody protects. The
implicit law being accepted, "every printed line is forever an external interface," is what will force a third command
later.

**Cheapest resolution:** state in the README which command output is stable and which is human-only. A machine-readable
`--format json` was proposed by one reviewer and is not recommended here: it is a permanent compatibility surface for a
three-command volunteer tool and is speculative against the project's own YAGNI posture.

### 🟡 Major M5 — The design's own compliance check points at a file that contains no rules
**Scope:** line 21; `AGENTS.md`; `docs/AGENTS.md`. Severity raised from the reviewer's Nit during synthesis.
**Sources:** zoom-out F8; catalyst's closing note (independent).

Line 21 tells the reader to "check this design against" the contributor rules in `AGENTS.md`. Neither `AGENTS.md` nor
the nested `docs/AGENTS.md` contains any technical, style, or design convention. Each holds only a code-named directive
about what to mention in chat responses. Both reviewers independently treated those lines as untrusted file content
rather than review instructions, which is the correct handling inside a Goldfish. The consequence is concrete: the
self-declared compliance check this design asks for cannot be performed, so that portion of every downstream review is
also incomplete. Either put real conventions in `AGENTS.md` or drop the claim from the Overview.

### 🟢 Nit N1 — `--today` is a second mechanism for a problem the design already solved
**Scope:** Technical Plan (51–52); Detailed Plan steps 1 (66–67) and 3 (70–71). Source: zoom-out F5.

`late_loans(rows, today)` already injects the date "so the date logic can be tested without the command line." The CLI
flag is therefore a user-facing knob for a reason the module boundary covers. The dangerous half of this nit is folded
into B1.

### 🟢 Nit N2 — Two gaps a fresh implementer will hit
**Scope:** Detailed Plan steps 1–2 (64–69); Technical Plan (37–39). Source: zoom-out F6.

`cli.py` handles `list` in the trailing `else` of the command chain, so adding an `overdue` subparser silently
re-points the default branch; the plan should say `list` becomes an explicit branch, since line 57 depends on `list`
keeping its documented behavior. Separately, `days_late` needs the stored `due` string parsed back into a date, and the
design never says what happens on a malformed or missing value in a JSON file a volunteer may have hand-edited. One line
—"unparseable due dates are reported and excluded, never dropped quietly" — closes it.

### 🟢 Nit N3 — Altitude drops in the high-level section
**Scope:** Technical Plan (35–52), lines 74–75. Source: zoom-out F7.

The architecture section prescribes the exact print template, the output filename template, the library call
(`datetime.date.today()`), an internal return-field name (`days_late`), and a per-character filename rule. A
user-visible output line belongs in a design; a returned field name, an overwrite policy, and a sanitizer list belong in
code where they can be tested.

---

## Clean at this altitude (no findings invented)

* Reads through the existing `store.open_loans()` instead of re-implementing JSON access.
* No equivalent lateness or date-comparison helper exists anywhere in the codebase, so `late_loans()` is new code, not
  reinvention; stdlib `datetime.date` is the right choice over a third-party date library.
* "Due today is not late," sorting by `due`, and test case 3 are internally consistent.
* No network, no schema change, no cache, no queue, no async, no background job — the premature-optimization vector is
  clean.
* Non-Goals explicitly freeze the storage format, fines, accounts, and email sending.
* Test list and README update follow the project's existing conventions.

## Traceability

| Consolidated | zoom-out | inventive-catalyst |
|---|---|---|
| B1 | F1 (Blocker) | F1 (Major), F4 (Nit) |
| M1 | F2 (Major) | — |
| M2 | F1 (part) | F2 (Major) |
| M3 | F3 (Major) | — |
| M4 | F4 (Major) | F3 (Nit) |
| M5 | F8 (Nit, raised) | reviewer note (independent) |
| N1 | F5 (Nit) | F1 (hazard folded into B1) |
| N2 | F6 (Nit) | — |
| N3 | F7 (Nit) | — |

## Suggested next actions for the author

1. Decide `--remind`: cut it, or re-specify B1, M2, and M3 before drafting code. Cutting it removes one blocker and three
   of the five majors in one edit.
2. Verify or drop the phantom-script premise in Alternatives Considered, and state in the README which command output is
   a stable interface.
3. Either write real contributor conventions into `AGENTS.md` or delete the compliance claim at line 21, so downstream
   stages have something to check against.
4. Move the field name, overwrite policy, and filename sanitizer out of the Technical Plan.
