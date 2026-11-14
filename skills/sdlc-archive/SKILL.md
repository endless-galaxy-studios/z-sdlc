---
name: sdlc-archive
description: >
  Archive completed deliverables and resolved idea briefs from `docs/current_work/` to
  `docs/chronicle/`. Only deliverables in the Complete state are eligible — verify `**Status:**`
  marker before moving. Idea briefs, bug reports, handoffs, and lite deliverables are also handled,
  and old process-changelog entries move to quarterly archive files once the changelog passes about 150 KB.
  Use when a deliverable is complete or an idea brief is resolved and needs to move from active work to the chronicle.
  Triggers on "let's organize the chronicles", "archive completed deliverables",
  "move to chronicle", "archive deliverable", "reconcile our recent work",
  "let's catalog our ad hoc work", "let's catch up the docs", "let's rejoin the process",
  "archive the changelog", "/sdlc-archive".
  Do NOT use for deliverables still In Progress or Validated — they stay in current_work until Complete.
  Do NOT use for restructuring or deleting chronicle entries — archive is one-way.
---

# Archive Completed Deliverables

Move completed work from `docs/current_work/` to `docs/chronicle/`. Follows the process defined in `[sdlc-root]/process/chronicle_organization.md`. Only deliverables in the **Complete** state (per `[sdlc-root]/process/deliverable_lifecycle.md`) are eligible for archival — verify the `**Status:**` marker before proceeding. Idea briefs, bug reports, handoffs, and lite deliverables are also handled.

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## Steps

### 0. Reconciliation Check

Before archiving, detect untracked ad hoc work that happened outside the SDLC process.

1. Find the last archived deliverable ID from `docs/_index.md`
2. Run `git log --oneline` since the last formal deliverable commit
3. If commits exist that aren't tied to any tracked deliverable, run the reconciliation process in `[sdlc-root]/process/ad_hoc_reconciliation.md`. The process has 5 phases:
   1. **Discovery** — identify the boundary (last formal commit), list ad hoc commits, categorize each
   2. **Reconciliation** — for each commit, pick the resolution: absorb into parent / lightweight record / batch into polish deliverable / skip
   3. **Spec Maintenance** — identify specs that need updating based on what was learned
   4. **Git State** — ensure clean state before resuming
   5. **Path Forward** — ask the user what comes next
   
   Do not skip the categorization step — every commit gets classified before a resolution is chosen.
4. If no untracked work is found, skip to Step 1

This step ensures ad hoc work gets cataloged before archival sweeps completed work into the chronicle.

### 1. Comprehensive Inventory

Perform a single exhaustive scan across ALL artifact types in `docs/current_work/`. Do not split this into multiple passes — scan everything at once.

#### Artifact types to scan:

| Type | Location pattern | What makes it complete |
|------|-----------------|----------------------|
| **Full deliverable** | `docs/current_work/{specs,planning,results}/dNN_*` | Has spec + plan + result files |
| **Lite deliverable** | `docs/current_work/sdlc-lite/completed/dNN_*_result.md` (or `sdlc-lite/dNN_*_result.md` if never moved) | Result file exists |
| **Idea brief** | `docs/current_work/ideas/*_idea-brief.md` | Any state (triage in step 3) |
| **Bug report** | `docs/current_work/ideas/*_bug-report.md` | Any state (triage in step 3) |
| **Handoff** | `docs/current_work/ideas/*_handoff.md` | Any state (triage in step 3) |
| **Ad hoc result** | `docs/current_work/results/adhoc_*` | Result file exists |

For EACH artifact found:
1. Read its content and frontmatter (status field, problem statement, outcome)
2. Check its entry in `docs/_index.md` — record the catalog status for cross-checking in step 2

**The process changelog.** Also run the changelog script in dry-run mode and record what it would move:

```bash
python3 .claude/skills/sdlc-archive/scripts/changelog_archive.py archive [sdlc-root]/process/sdlc_changelog.md --dry-run
```

It proposes a move only when the changelog is over about 150 KB, and then only entries dated before the previous calendar quarter.

If a type yields zero results for a given pattern, also try broader globs (e.g., `docs/current_work/ideas/*bug*`, `docs/current_work/ideas/*handoff*`) to catch naming variations.

### 2. Git History Verification

**Mandatory.** Do not skip this step or defer it to the user.

For every artifact found in step 1:

1. **Verify implementation commits exist:**
   ```bash
   git log --oneline --grep="DNN" --grep="dNN" -i
   ```
   Also search for the artifact's topic keywords if the ID search yields nothing.

2. **Cross-check catalog status against reality:**
   - Catalog says "In Progress" but result file exists → flag as **catalog inconsistency** (fix in step 6)
   - Catalog says "Complete" but no result file → flag as **premature status** (skip archival)
   - No catalog entry but artifact exists → flag as **missing catalog entry**

3. **Graduation detection for idea briefs:**
   - First check frontmatter `status: graduated` / `status: abandoned` / `status: active`
   - If no explicit status, search git log for commits whose messages reference the brief's topic, concept name, or recommended next steps
   - If a deliverable exists whose spec traces to the brief (shared concept, matching problem description), mark as graduated even without frontmatter

Record all findings — they feed directly into step 3 classification.

### 3. Classification

For each artifact, classify using this priority order: **frontmatter status → git history evidence → content analysis**.

| Classification | Criteria | Action |
|---------------|----------|--------|
| **Archive (deliverable)** | Complete full or lite deliverable with implementation commits | Move to concept chronicle |
| **Archive (graduated idea)** | Idea brief that led to a deliverable (linked by topic/ID) | Archive alongside the deliverable's concept |
| **Archive (resolved idea)** | Idea brief whose question was answered without needing a deliverable | Archive into best-fit concept chronicle |
| **Archive (resolved bug)** | Bug report that was fixed (commits exist, issue closed) | Archive into relevant concept chronicle |
| **Delete** | Stale bug reports with no follow-up, duplicate artifacts, resolved handoffs that have been fully acted on | Remove entirely |
| **Skip** | Active, recent, or in-progress work | Leave in place |

### 4. Single Approval Gate

**This is the ONLY AskUserQuestion in the entire flow.** Present one comprehensive table covering all artifact types and all proposed actions:

```
Archive & cleanup plan — {N} items to archive, {M} to delete, {K} skipped (active)

| Item | Type | Status Evidence | Target Concept | Action |
|------|------|----------------|----------------|--------|
| D12 — Auth Tokens | full deliverable | spec+plan+result, 8 commits | auth | Archive |
| D15 — Cache Layer | lite deliverable | result exists, 3 commits | performance | Archive |
| caching_idea-brief | idea (graduated → D15) | topic match to D15 | performance | Archive with D15 |
| notification_idea-brief | idea (resolved) | question answered in D12 result | auth | Archive |
| stale_bug-report | bug report | fixed in commit abc123 | — | Delete |
| api_handoff | handoff | fully acted on | — | Delete |
| D18 — New Feature | full deliverable | no result file yet | — | Skip |
| Process changelog | 2026-Q1, 2026-Q2 (203 entries) | 644 KB, over 150 KB | changelog-archive/ | Archive |
```

If catalog inconsistencies were found in step 2, append a **Catalog Fixes** section:

```
Catalog fixes needed:

| Item | Current Status | Actual Status | Fix |
|------|---------------|---------------|-----|
| D14 | In Progress | Complete (result exists) | Update to Complete |
| D19 | — | Active (spec exists) | Add missing entry |
```

Use AskUserQuestion to confirm. If the user adjusts mappings or actions, apply their changes.

### 5. Archive Deliverables

For each approved deliverable (both full AND lite):

1. **Create concept directory** if it doesn't exist:
   ```
   docs/chronicle/{concept_name}/specs/
   docs/chronicle/{concept_name}/planning/
   docs/chronicle/{concept_name}/results/
   ```

2. **Copy files** to the concept chronicle:
   - Full deliverables: `docs/current_work/{type}/` → `docs/chronicle/{concept_name}/{type}/`
   - Lite deliverables: `docs/current_work/sdlc-lite/completed/dNN_*_result.md` (or `sdlc-lite/dNN_*_result.md`) → `docs/chronicle/{concept_name}/results/`
   - If a lite deliverable has an associated plan or spec in `docs/current_work/sdlc-lite/completed/` (or `sdlc-lite/`), copy those to the matching subdirectory

3. **Update or create `_index.md`** in the concept directory with:
   - Overview of the concept
   - Deliverables table listing all files with purpose and dependencies
   - Key decisions from the spec/result

4. **Remove archived files** from `docs/current_work/`

5. **Update `docs/_index.md`**:
   - Move the deliverable row from "Active Work" to "Completed & Archived"
   - Update its status to "Archived"
   - Add a link to the concept chronicle

### 6. Fix Catalog Inconsistencies

Apply all approved catalog fixes from the table in step 4:
- Update status markers in `docs/_index.md` to match reality
- Add missing catalog entries
- Correct any stale status fields

### 7. Archive Idea Briefs & Resolved Artifacts

For each approved idea brief, bug report, or handoff marked for archival:

1. **Create `ideas/` subdirectory** in the target concept chronicle if it doesn't exist:
   ```
   docs/chronicle/{concept_name}/ideas/
   ```

2. **Copy the file** from `docs/current_work/ideas/` to `docs/chronicle/{concept_name}/ideas/`

3. **Update `_index.md`** in the concept directory — add an "Exploration History" section (if not already present):
   ```markdown
   ## Exploration History

   | Brief | Seed | Outcome | Date |
   |-------|------|---------|------|
   | [filename.md] | [original seed from brief] | Graduated → DNN / Resolved / Abandoned | [explored date] |
   ```

4. **Remove the file** from `docs/current_work/ideas/`

### 8. Delete Approved Artifacts

Remove all artifacts marked for deletion in step 4. This includes stale bug reports, resolved handoffs, and duplicates.

### 8a. Archive Old Changelog Entries

If CD approved the changelog row, run the script without `--dry-run`:

```bash
python3 .claude/skills/sdlc-archive/scripts/changelog_archive.py archive [sdlc-root]/process/sdlc_changelog.md
```

It moves each whole quarter older than the previous one to `[sdlc-root]/process/changelog-archive/YYYY-Qn.md`, unedited and in its order, adds one pointer line to the changelog, and writes nothing unless every entry is still present exactly once across the files. Exit 2 means it refused: report its message and leave the files as they are. Never move entries by hand.

### 9. Knowledge Hygiene

Archival is a natural triage checkpoint for parking lot entries generated during the work being archived. This is NOT discipline capture (no new insights are generated) — it closes the loop on entries that were captured during the original work sessions.

#### 9a. Scan Related Parking Lot Entries

For each deliverable being archived, read `[sdlc-root]/disciplines/*.md` and find parking lot entries whose bold header contains the deliverable's context tag. The discipline capture protocol requires context tags at the start of each entry in the format `**[date] [context]**:`. Scan for entries matching the deliverable's ID pattern (e.g., `[D05 — phase 2]`, `[D05 — planning]`).

For each idea brief being archived, scan for entries whose bold header contains the idea's context tag (e.g., `[idea: caching]`).

**Legacy tolerance:** Older entries may use non-standard context formats (e.g., `[session: D05-execution]` instead of `[D05 — phase N]`). When scanning, also match the deliverable number as a bare substring (e.g., `D05`) to catch these. Flag non-standard entries in the triage table so the user can decide whether to normalize them.

Collect all entries that are still marked `[NEEDS VALIDATION]`.

#### 9b. Check Idea Brief Insight Coverage

For each idea brief being archived, read its "Key Insights from Exploration" section. For each insight listed, check whether a corresponding parking lot entry exists.

Flag any insight that appears significant and reusable but has no parking lot entry.

#### 9c. Present Triage Table (only if needed)

**Skip this entire sub-step if no `[NEEDS VALIDATION]` entries exist AND all idea brief insights have coverage.** Do not use AskUserQuestion — apply reasonable defaults instead:

- Entries clearly validated by the archived work → **flag as promotion candidates in the triage table** so CD decides. The `[READY TO PROMOTE]` transition is CD-only per the triage authority matrix (compliance methodology §6c) — never apply it as a silent default. If the table is being skipped (nothing else needs judgment), append `(promotion candidate — [date])` after the entry's `[NEEDS VALIDATION]` marker instead, leaving the transition for the next audit's step 11 triage.
- Entries not yet proven → mark `[DEFERRED]`
- Missing insight entries → capture with `[NEEDS VALIDATION]`

If more than 3 entries require judgment calls, present a brief summary and use AskUserQuestion. Otherwise, apply defaults and report what was done.

Archival-time triage is deliberately lighter than audit-time promotion: it identifies candidates and flags uncertainty, it does not adjudicate. The multi-judge Promotion Verification Gate (`[sdlc-root]/process/discipline_capture.md` § Promotion Verification Gate) runs when entries are actually promoted — during sdlc-audit step 11 or a dedicated promotion pass — not during archival.

#### 9d. Agent Memory Path Fixups (mechanical only)

This archive operation just moved deliverable docs from `docs/current_work/...` to `docs/chronicle/...`. Any agent-memory note that cited the old path is now broken — a mechanical breakage caused by *this* operation, so fix it here rather than leaving it for an audit.

**Scope: only the dNN deliverable(s) in this archive batch, and only path rewrites.** Do NOT prune, dedup, or curate memory content — deeper agent-memory hygiene (oversized `MEMORY.md`, contradictions, orphaned dirs) is `sdlc-audit` Dimension 8b's job, a periodic sweep, not the archive's.

1. If `.claude/agent-memory/` doesn't exist (project doesn't use agent memory), skip this step silently.
2. For each deliverable being archived, grep `.claude/agent-memory/*/` for the old `docs/current_work/...` paths this operation moved.
3. Rewrite each hit to the new `docs/chronicle/...` location.
4. If a note's entire subject deliverable is now archived and the note is a pure task-log with no forward-reusable insight, offer it for deletion **in the Step 9c triage table** (per the "ONE AskUserQuestion" rule — do not open a second gate). If Step 9c was skipped (no table produced), apply the default: keep the note unless it is unambiguously a pure task-log with nothing reusable, in which case delete it and report what was removed.

### 10. Clean Up Issues

If a deliverable had an associated issue file in `docs/current_work/issues/` and the deliverable is now archived, remove the issue file too.

### 11. Verify

List the archived files in their new locations and confirm nothing was left behind in `docs/current_work/` that should have been moved.

### 12. Commit

Commit with message format: `docs: archive DXX-DYY into chronicles`

Include artifact types in the message when relevant:
- `docs: archive DXX-DYY + idea briefs into chronicles`
- `docs: archive DXX-DYY + lite deliverables + idea briefs, fix catalog`
- `docs: archive DXX-DYY + changelog 2026-Q1..Q2`

Ask for confirmation before committing.

## Red Flags

| Thought | Reality |
|---------|---------|
| "Archive everything, skip categorization" | Each deliverable needs correct concept mapping. Wrong categorization breaks chronicle discoverability. |
| "This deliverable is obviously complete, skip the check" | Run git log verification. Catalog status lies — commits don't. |
| "I'll pick the concept category myself" | Present the table and use AskUserQuestion. The user decides categorization. |
| "This idea brief is old, just delete it" | Old briefs still contain exploration context. Archive them — don't discard. The thinking is valuable even if the idea was abandoned. |
| "I should run full discipline capture during archival" | Archival is housekeeping, not creative work. Knowledge hygiene triages existing entries — it does not generate new ones. |
| "No parking lot entries to triage, skip step 9" | Still check idea brief insights for missing coverage (step 9b). But if both 9a and 9b are clean, skip the triage table — don't fabricate work. |
| "I'll ask the user at each step" | ONE AskUserQuestion in step 4. After approval, execute autonomously. Knowledge hygiene gets a second gate only if >3 ambiguous entries exist. |
| "Lite deliverables go through the same path as full" | Lite deliverables may only have a result file — don't fail on missing spec/plan. Archive what exists. |
| "I'll move the old changelog entries by hand" | Run the script. It moves entries unedited and checks none is lost or doubled; a hand move can drop or alter one. |
| "Bug reports should always be archived" | Stale, duplicate, or fully-resolved bug reports can be deleted. Only archive bugs with valuable diagnostic context. |

## Integration
- **Feeds into:** `sdlc-status` (chronicle is the source of truth for completed work), `sdlc-reflect` (archived deliverables inform retrospectives)
- **Uses:** `[sdlc-root]/process/chronicle_organization.md`, `[sdlc-root]/process/ad_hoc_reconciliation.md` (Step 0), `[sdlc-root]/process/deliverable_lifecycle.md`, `docs/current_work/`, `docs/_index.md`, `[sdlc-root]/disciplines/*.md`, `scripts/changelog_archive.py` (Steps 1 and 8a; `sdlc-migrate` §4.5c runs it too)
- **Complements:** `sdlc-status` (identifies archivable work), `sdlc-idea` (produces idea briefs that archive triages)
- **Does NOT replace:** `sdlc-ingest` (knowledge capture — archive only triages existing parking lot entries, does not create new ones)
