---
name: sdlc-migrate
description: >
  Migrate a project's z-sdlc framework to the latest version — content-aware updates that preserve
  project-specific customizations (parking lots, agent names, build commands, maturity tracker) while
  updating framework sections (skills, knowledge, process docs, agents) to match the current z-sdlc.
  Triggers on "migrate my SDLC", "update the SDLC", "migrate SDLC framework", "update SDLC framework",
  "upgrade SDLC", "sync SDLC with upstream".
  Do NOT use for first-time installation — use sdlc-initialize.
  Do NOT use when neither ops/sdlc/ nor .claude/sdlc/ exists — use sdlc-initialize.
---

# SDLC Migrate

Apply z-sdlc upstream updates to a project while preserving project-specific customizations. Unlike the initial installation (which copies files and skips modified ones), this skill is **content-aware** — it understands which sections are framework-level vs project-customized and updates them independently.

**Argument:** `$ARGUMENTS` (optional — local path to a z-sdlc clone. If omitted, resolve via `.sdlc-manifest.json` → `source_repo`, or ask user.)

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## Source Repo Access Rule

**All reads from z-sdlc MUST use git commands** (`git -C [z-sdlc-path] show [target_tag]:<path>`), never filesystem reads. **Never use shell redirection** (`git show > file`) — it silently destroys targets on failure. Full rules and safe extraction patterns: see `[sdlc-root]/process/source-repo-safety.md`.

**`[target_tag]`** is the latest semver release tag in the z-sdlc source repo (e.g., `v1.4.0`). Resolved once during Pre-Flight and used as the git ref for every source read. Never use bare `HEAD` — it may point past the latest release if the source repo has unreleased commits.

## Transaction Log

Every phase start/end, gate decision, mutation, and failure writes an append-only JSONL entry to `.sdlc-transaction-log` in the project root. Schema and event types: see `[sdlc-root]/process/transaction-log-schema.md`.

**Run ID convention for migrate:** `migrate-{6-char-random-hex}` (e.g., `migrate-def456`).

**Migrate-specific events to log:**
- `drift_detected` — when §1.2a finds a drifted file (one entry per file)
- `drift_decision` — CD's choice at the drift gate (`overwrite`/`keep`/`extract_markers`)
- `deviation_detected` — when §2.1c finds non-marker project customizations
- `marker_preserved` — when a PROJECT-SECTION block is re-injected during §2.1d
- `phase_skip` — when an entire phase is skipped (e.g., no skills changed in §1.3)

**Recovery from migrate crash:**
```bash
tail -n 100 .sdlc-transaction-log | jq 'select(.run_id | startswith("migrate-"))'
# Last mutation event = what was last committed
# Last phase_start without phase_end = crash point
# checkpoint: point_of_no_return event tells you whether mutations started
```

## Pre-Flight Check

Before starting, verify this is a migration (not initialization):

If neither `ops/sdlc/` nor `.claude/sdlc/` exists → tell user to run `sdlc-initialize` instead and stop.

**Step 1 — Resolve z-sdlc source and target release:**

**1a. Resolve source to a local path** (in priority order):
1. `$ARGUMENTS` — if the user passed a local clone path, verify with `git -C [path] rev-parse HEAD`
2. `.sdlc-manifest.json` → `source_repo` field (git remote URL) — **clone it immediately:**
   ```bash
   git clone --depth=1 [source_repo] /tmp/z-sdlc-migrate
   ```
   This is safe and expected — it's a shallow clone of the user's own repo. Use `/tmp/z-sdlc-migrate` as `[z-sdlc-path]` for all subsequent phases. Clean up with `rm -rf /tmp/z-sdlc-migrate` after migration completes.
3. If neither is available, ask the user.

**1b. Resolve `[target_tag]`** — the latest semver release tag in the z-sdlc source repo:

```bash
# Fetch tags if shallow clone
git -C [z-sdlc-path] fetch --tags 2>/dev/null

# Get the latest semver tag (vN.N.N), sorted by version
TARGET_TAG=$(git -C [z-sdlc-path] tag -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -1)
TARGET_SHA=$(git -C [z-sdlc-path] rev-parse "$TARGET_TAG")

if [ -z "$TARGET_TAG" ]; then
  echo "WARNING: No release tags found in z-sdlc source — falling back to HEAD"
  TARGET_TAG="HEAD"
  TARGET_SHA=$(git -C [z-sdlc-path] rev-parse HEAD)
fi
```

Use `[target_tag]` (the resolved tag, e.g., `v1.4.0`) as the git ref for **every** source read in subsequent phases. This ensures the migration targets a stable release, not unreleased commits.

**Step 2 — Detect project structure:**

The z-sdlc source uses canonical paths (`knowledge/`, `disciplines/`, `process/`). Projects install these to different locations. Detect the project's structure before applying any changes.

| Signal | Detection | Result |
|--------|-----------|--------|
| **SDLC directory** | `[ -d ops/sdlc ]` vs `[ -d .claude/sdlc ]` | Set `[sdlc-root]` to whichever exists (if both exist, prefer `ops/sdlc` and warn user) |

```bash
# Detect SDLC root
if [ -d ops/sdlc ] && [ -d .claude/sdlc ]; then
  SDLC_ROOT="ops/sdlc"
  echo "WARNING: Both ops/sdlc and .claude/sdlc exist. Using ops/sdlc. Consider consolidating."
elif [ -d ops/sdlc ]; then
  SDLC_ROOT="ops/sdlc"
elif [ -d .claude/sdlc ]; then
  SDLC_ROOT=".claude/sdlc"
else
  echo "No SDLC directory found — use sdlc-initialize"
  exit 1
fi
```

**Adapter lifecycle detection:** After reading `.sdlc-manifest.json`, check for the `adapter` block:

```
If manifest.adapter exists and is not null:
  Resolve handler doc: {project_root}/{adapter.plugin_root}/{adapter.phase_handlers}
  If handler doc missing or unreadable → halt with error
  Parse which H2 sections exist → these are the adapter's declared phases
  Refresh supported_zsdlc_version from live adapter.json (adapter may have been updated; an adapter written
  before the rename declares supported_ccsdlc_version). Write it under the new key and remove a
  supported_ccsdlc_version key from the project's adapter entry
  Log: adapter_detected event with plugin name and declared phases
```

When an adapter is detected, this skill delegates specific phases (knowledge-update, post-file-write, post-operation) to the adapter's handler doc instructions. Non-delegated phases run identically to the non-adapter path. See `[sdlc-root]/process/adapter-lifecycle-protocol.md` for the full protocol.

**Adapter version gate:** During §1.2 (Changelog Review Gate), if an adapter is detected, compare each `[contract-change]` entry's z-sdlc version against `adapter.supported_zsdlc_version`. If any entry's version exceeds the adapter's declared support → halt with a message identifying the uncovered entries and the adapter's current version. The adapter maintainer must update their `adapter.json` before migration can proceed.

When `manifest.adapter` is `null` or absent, behavior is identical to before this protocol existed.

**Step 3 — Report assessment:**

```
MIGRATION ASSESSMENT
SDLC root: [sdlc-root] (ops/sdlc or .claude/sdlc)
Has .sdlc-manifest.json: [yes/no]
Has .claude/agents/: [yes/no]
Has .claude/skills/: [yes/no]
z-sdlc source: [local path or "cloned from [URL] to /tmp/z-sdlc-migrate"]
z-sdlc target release: [target_tag] ([TARGET_SHA short])
Project installed version: [source_version] (from .sdlc-manifest.json)
```

---

## Path Transformation Rules

Source-to-project path mappings (e.g., `knowledge/` → `[sdlc-root]/knowledge/`, `agents/` → `.claude/agents/`) and the list of project-specific files that must never be overwritten (`agent-selection.yaml`, `agent-context-map.yaml`, `provenance_log.md`): see `[sdlc-root]/process/path-mappings.md`.

## Phase 1: Detect What Changed

### 1.1 Identify Source Version

Read the project's `.sdlc-manifest.json` to get:
- `source_repo` — the git remote URL for the z-sdlc repo (used to clone if no local path given)
- `source_version` — the release tag (e.g., `v1.2.0`) from the last install/migration

**Resolve `source_version` to a git ref:**

| `source_version` value | Interpretation | Diff base |
|------------------------|----------------|-----------|
| Semver tag (e.g., `v1.2.0`) | Normal — project tracks releases | `v1.2.0` |
| 40-char hex SHA (legacy) | Pre-tag manifest — resolve to nearest tag | `git -C [z-sdlc-path] describe --tags --abbrev=0 [SHA]` (falls back to SHA if no tag contains it) |
| `"unknown"` or missing | First migration after legacy install | Full migration — compare all files |

**Already up to date?** If `source_version` equals `[target_tag]`, the project is already on the latest release. Report "Already on [target_tag] — nothing to migrate" and stop.

Then check what changed in z-sdlc between the project's version and the target release:

```bash
git -C [z-sdlc-path] log --oneline [source_version]..[target_tag]
git -C [z-sdlc-path] diff --name-only [source_version]..[target_tag]
```

If `source_version` is `"unknown"` or missing, treat this as a **full migration** — compare all framework files against the project. Do not stop or ask the user — a full migration is the correct fallback.

### 1.2 Changelog Review Gate

**Before categorizing or applying anything**, read the changelog entries since the project's source version.

Read `process/sdlc_changelog.md` from the z-sdlc source repo (via `git -C [z-sdlc-path] show [target_tag]:process/sdlc_changelog.md`), stopping when you reach entries older than the project's `source_version` date. When the project's version is older than the file's oldest entry, keep reading in `process/changelog-archive/` at the same tag, newest quarter first (`git -C [z-sdlc-path] ls-tree --name-only [target_tag] process/changelog-archive/`, then `git show` each `YYYY-Qn.md`). A tag from before archiving has no archive; its changelog holds everything. This is the migration's release notes — it surfaces:

- **Breaking changes** — renamed concepts, moved files, added structural markers, changed conventions
- **New capabilities** — new knowledge files, new disciplines, new agent roles the project may want
- **Human-judgment items** — changes where the project team should decide (e.g., "do you want the new BA discipline wired to an agent?")

**Gate rule:** If any changelog entry describes a breaking change or convention rename, note it for the CLAUDE-SDLC.md compatibility check in §4.3a. If any entry describes a new capability that requires project-team input (new agent roles, new discipline areas), flag it for user review before applying.

Present a brief migration summary to the user via `AskUserQuestion`:

```
Migration summary: [source_version] → [target_tag]
- N commits, M changelog entries
- Breaking changes: [list or "none"]
- New capabilities: [list or "none"]
- Items needing your input: [list or "none"]
Proceed with migration?
```

**Gate:** Wait for user confirmation before continuing to Phase 2.

### 1.2a Operational Drift Detection

Before computing upstream-vs-project diffs, detect **drift** — files where the hash recorded at install time (`installed_files[path].sha256` in `.sdlc-manifest.json`) no longer matches the current on-disk hash. Drift indicates the file was edited post-install without going through PROJECT-SECTION markers.

For each path in `manifest.installed_files`:

```
current_hash = sha256(file contents on disk)
installed_hash = manifest.installed_files[path].sha256

if current_hash != installed_hash:
  categorize based on upstream comparison:
    - DRIFTED-CLEAN:    project edited, upstream unchanged since install
    - DRIFTED-CONFLICT: project edited AND upstream changed
    - DRIFTED-ORPHAN:   project edited, file removed/moved in upstream
```

**Project-owned files are not drift.** Skip every file on the never-overwrite list (`[sdlc-root]/process/path-mappings.md` § Project-Specific Files): the project edits them by design, and migration never overwrites them, so a changed hash there needs no decision.

**Drift categories and defaults:**

| Category | Meaning | Gate Action |
|----------|---------|-------------|
| `DRIFTED-CLEAN` | Project edited, upstream unchanged | Prompt: overwrite with upstream / keep project version / extract project edits into PROJECT-SECTION markers |
| `DRIFTED-CONFLICT` | Project edited AND upstream changed | Hard prompt: show both diffs, require three-way decision |
| `DRIFTED-ORPHAN` | Project edited, file removed upstream | Prompt: keep as project-owned / move to legacy / delete |

Surface drifted files in the §1.3 change manifest with a `⚠ DRIFT` marker so CD sees them before any mutation. Phase 2's direct-copy operations (§2.1) and content-merges (§2.2+) must consult drift status before acting — if a file is drifted, the Phase 2 default action is overridden by the drift gate decision.

**Why this matters:** Without drift detection, migration silently overwrites manual edits to framework files. With it, every unexpected edit gets surfaced and consented before being touched.

**Back-fill path (projects initialized before `installed_files` was introduced):**

If `.sdlc-manifest.json` lacks an `installed_files` field:
1. Log: "Drift detection unavailable — manifest predates installed_files field"
2. Back-fill: hash each file listed in `skeleton/manifest.json` source_files at its installed path, except the never-overwrite files (`[sdlc-root]/process/path-mappings.md` § Project-Specific Files), record to `installed_files` with `installed_at: "backfilled-{CURRENT_VERSION}"`
3. Proceed without drift analysis for this migration — it becomes available starting with the next migration

### 1.3 Categorize Changes

Group the changed z-sdlc files by migration strategy:

| File Type | Location | Strategy |
|-----------|----------|----------|
| **Skills** | `skills/*/SKILL.md` | Content-merge: update framework sections, preserve project customizations |
| **Skill scripts** | `skills/*/scripts/*` (manifest-listed) | Direct copy to `.claude/skills/*/scripts/`; never content-merged |
| **Skill references** | `skills/*/references/*` (manifest-listed) | Direct copy to `.claude/skills/*/references/`, except a dual-audience skill's (§2.2 Step 0), which merge additively; `sdlc-audit`'s follow §2.4 |
| **Agent template** | `templates/agent-template.md` | Direct copy to `[sdlc-root]/templates/` (no project customizations) |
| **Audit skill** | `skills/sdlc-audit/SKILL.md` + `references/` | Content-merge: update audit methodology, preserve project-specific additions |
| **Knowledge YAMLs** | `knowledge/**/*.yaml` | Key-level merge: add new upstream keys, preserve project additions (§2.1b). Check for moved/deleted files (§2.1a) |
| **Process docs** | `process/*.md` | Direct copy (framework-level), except the changelog (next row) |
| **Process changelog** | `process/sdlc_changelog.md` | Never overwrite — the project's record of its own process changes. Migration prepends one entry for itself (§4.5b) |
| **Changelog archive** | `process/changelog-archive/` | Not installed: z-sdlc's archive is its own history (§1.2 reads it). The project's archive is never overwritten; §4.5c adds to it |
| **Disciplines** | `disciplines/*.md` | Content-merge: update framework guidance, preserve project parking lot entries |
| **Context map** | `knowledge/agent-context-map.yaml` | Never overwrite — project has its own agent names. Update paths for moved/deleted files (§3.3) |
| **Provenance log** | `knowledge/provenance_log.md` | Never overwrite — project's append-only ingestion/research records |
| **Project agents** | Project `.claude/agents/*.md` | Targeted section updates (see Phase 3) |
| **CLAUDE-SDLC.md** | `CLAUDE-SDLC.md` | Content-merge into project's `CLAUDE.md` (§2.1e). No separate file. |
| **Templates** | `templates/*` (all manifest-listed files, incl. `.html` and `.sh.template`) | Direct copy (framework-level). Skip `templates/optional/` (source-only). Never copy a `*.sh.template` to the executable wrapper path — projects enable wrappers themselves. |

---

## PROJECT-SECTION Marker Convention

Read and follow `[sdlc-root]/process/project-section-markers.md` — the canonical definition of the marker convention. It defines the syntax (Markdown and YAML), label format, rules, and validation. Producing skills that add markers to process/skill files (`sdlc-develop-agent`, `sdlc-develop-skill`, `sdlc-audit` improvement mode) reference that document. Note: markers are only for process docs and skill files — knowledge files, discipline files, and agent-context-map are project-specific and don't need markers.

This migration skill is responsible for **consuming** markers: extracting, preserving, and re-injecting marked blocks during framework updates. Existing project content that lacks markers is detected by the deviation detection step (§2.1c).

---

## Phase 2: Apply Framework Updates

> ## ⚠ POINT OF NO RETURN
>
> **Phase 1 was read-only** — source version identification, changelog review, and change categorization. All three completed without touching workspace state. Cancellation at any Phase 1 point left no trace.
>
> **Phase 2 is the first phase that commits mutations.** The first file write in §2.1 overwrites on disk. Once that has run, **cancellation leaves partial state**. The good news: migrations are designed to be resumable — re-running `/sdlc-migrate` from a crash point will complete via PROJECT-SECTION marker re-extraction and idempotent copy. The bad news: the workspace `source_version` will be in an intermediate state until the re-run completes.
>
> Before proceeding, verify:
> - §1.2 changelog review gate returned `approved`
> - If drift was detected in §1.2a, every drifted file has a `drift_decision` logged
> - Transaction log has the corresponding `gate` events with `approved` results
>
> Log a `checkpoint: point_of_no_return` event to the transaction log immediately before the first file write.

### 2.0 Load Contract Changes

Read `skeleton/contract_changes.yaml` from the z-sdlc source (via `git -C [z-sdlc-path] show [target_tag]:skeleton/contract_changes.yaml`).

**If the file is absent** (the upstream z-sdlc predates the contract-changes system): skip this step entirely. `pending_changes` is empty. §4.3a falls back to its inherent path-integrity and convention checks with no rename set. §4.5 does not update `last_applied_contract_id`. §4.7 is skipped. Log `CONTRACT CHANGES: not present in upstream — skipping contract-driven steps`.

Otherwise, read `.sdlc-manifest.json` → `last_applied_contract_id` (treat as `"0000"` if absent — this covers projects installed before contract_changes.yaml existed).

Select entries with `id` > `last_applied_contract_id`. Call this set **pending_changes**. It drives:

- §2.0a bundle detection (entries with `type: bundle_debut`)
- §2.1a upstream-deletion exemptions (bundle skill paths are exempt regardless of contract entry; see below)
- §4.3a CLAUDE.md compatibility check (entries with `type: rename_skill`)
- §4.5 manifest update (entries with `type: manifest_field_added`; also persists `last_applied_contract_id`)
- §4.5a catalog columns (entries with `type: catalog_column_added`)
- §4.7 bundle offer (entries with `type: bundle_debut` not yet installed)

Log the selection so CD can see what's being applied:

```
CONTRACT CHANGES SINCE 0005:
  0006 rename_skill          Merge review-commit + review-diff into sdlc-review-code
  0007 manifest_field_added  Introduce optional skill bundles (installed_bundles)
  0008 bundle_debut          Debut design bundle
```

If pending_changes is empty, log `CONTRACT CHANGES: up to date` and skip the §4.3a contract-driven rename step (it has nothing to do). The rest of §4.3a (path integrity, convention checks) still runs.

**Unknown entry types:** If an entry's `type` isn't one of the defined values, log a warning and skip it. Do not fail the migration — schema-forward compatibility lets adapter plugins extend the set.

### 2.0a Bundle Detection

Before any file copying, compute the **effective install set** for this project — the default `source_files` list plus any opt-in bundles the project has already adopted.

**Process:**

1. Read `skeleton/manifest.json` from the z-sdlc source.
2. Read `.sdlc-manifest.json` from the project. If it has an `installed_bundles` array, treat that as the authoritative list of installed bundles.
3. **Fallback for pre-bundles installs:** If `installed_bundles` is missing (projects installed before the bundles manifest existed), for each bundle in `manifest.bundles` check whether **any** of its listed **skill** paths exist as installed skills in the project. If yes, mark the bundle as **installed** and append it to `installed_bundles` — the migrate's §4.5 manifest update will persist this. **Bundle `process` paths are deliberately excluded from this detection:** a project can hand-roll a process doc at the same path before the bundle ever debuts (that is exactly the predecessor case §4.7 exists for), and auto-marking such a project as bundle-installed would blind-overwrite its hand-rolled version and skip the adopt/preserve-config flow.
4. Build the effective skills list: `source_files.skills` ∪ (bundle.skills for every installed bundle). Likewise the effective process list: `source_files.process` ∪ (bundle.process for every installed bundle that declares any).
5. Log the detection result to the migration report:
   ```
   BUNDLE DETECTION
   - design: installed (source: installed_bundles | file-existence fallback)
   - testing: not installed
   ```

**Rules:**

- **Never remove** installed bundle skills, even when a bundle is detected as only partially installed. The project chose its subset; migration preserves that choice.
- Bundle skill paths are **exempt from §2.1a "Remove Deleted and Moved Files"** — they are not considered upstream-deleted even though they live outside `source_files.skills`. Bundle `process` paths get the same exemption.
- Bundle skills are **eligible for §2.1 direct-copy updates**: if the bundle is installed, its skill files propagate upstream changes the same way `source_files` skills do. Bundle `process` files likewise.
- Bundle `fragments` are **refreshed, not preserved**: §2.1's marker step discards any existing `BUNDLE-SECTION` blocks in a target file and injects the current fragment content from the z-sdlc source (step 7 of the marker-preservation flow below). Hand-edits inside `BUNDLE-SECTION` markers are lost by design — see `[sdlc-root]/process/project-section-markers.md` § BUNDLE-SECTION Markers.
- Bundle `tree` files (contract 0019) are **eligible for §2.1 direct-copy updates** like `source_files`: copy every file under `tree.from` at `[target_tag]` to the same path under `tree.to`, keeping executable bits, with the usual drift check against `installed_files`. When upstream deletes one, §2.1a removes it from the project. Files under `tree.to` that the bundle doesn't list (a project's own additions, such as a production tier) are never touched.
- Bundle `seed` files are **never touched by migration**: written once at install, they are the project's. A seed file upstream adds later is written only where the project has nothing at that path.
- **Render after the copy.** When §2.1 is done, run each installed bundle's `render` command from the project root (for the factory, `python3 .github/factory/render.py`), so its generated files follow the new templates. A render failure is a migration finding (usually a setting the project must add), not a reason to stop: report it with the command's output.
- Bundles not installed in the project are **not** copied during §2.1 — they are offered at the end of migration (§4.7).

### 2.1 Direct Copy Files

**Step 0 — Load exclusion list before any writes.** Read `[sdlc-root]/process/path-mappings.md` § "Project-Specific Files (Never Overwrite)". For every file about to be written in this phase, confirm it does NOT appear on that list. If it does, skip it — no exceptions, no "I'll just update the header" rationalizations. Current exclusions: `agent-selection.yaml`, `agent-context-map.yaml`, `provenance_log.md`, `sdlc_changelog.md`, `process/changelog-archive/`, and the project's `.claude/skills/verify/`.

For files with no project customizations, copy directly from z-sdlc to the project's `[sdlc-root]/` directory:

- `process/*.md`, top level only (excluding `agent-selection.yaml` and `sdlc_changelog.md` — project-specific, protected by Step 0). Never copy `process/changelog-archive/`: it's z-sdlc's history
- `skills/*/scripts/*` (manifest-listed) → `.claude/skills/*/scripts/`
- `skills/*/references/*` (manifest-listed) → `.claude/skills/*/references/`, except a dual-audience skill's (§2.2 Step 0), which merge additively; `sdlc-audit`'s follow §2.4
- `knowledge/**/*.yaml` (but NOT `agent-context-map.yaml`)
- `knowledge/README.md` (to `[sdlc-root]/knowledge/`) — NOT `knowledge/provenance_log.md`; that's project-specific (see "Project-Specific Files")
- `README.md` (to `[sdlc-root]/`)
- `templates/agent-template.md` → `[sdlc-root]/templates/` (agent template moved from agents/ to templates/)
- `agents/sdlc-reviewer.md`, `agents/sdlc-compliance-auditor.md` → `.claude/agents/` (framework subagents must be in `.claude/agents/` for Claude Code to dispatch them, not just `[sdlc-root]/agents/`)
- `playbooks/*.md` (unless the project has written its own playbooks — check git blame)
- `examples/*.md`
- `templates/*` (to `[sdlc-root]/templates/` — all manifest-listed files, including `.html` and `.sh.template`; never overwrite a project's enabled `[sdlc-root]/external-review*.sh` wrappers, which are project-authored)

**Not direct-copied:**
- `templates/optional/` — Conditional CLAUDE.md appendices. Read from z-sdlc source during initialization when needed, not installed.
- `CLAUDE-SDLC.md` — See §2.1e for CLAUDE-SDLC.md handling (merge into CLAUDE.md, not a separate file).

**All reads from the z-sdlc source repo must use git commands** (e.g., `git -C [z-sdlc-path] show [target_tag]:path/to/file`), not filesystem reads. This ensures you're reading the target release, not unreleased working tree state.

**PROJECT-SECTION preservation with content review (mandatory for all direct-copy files):**

Before overwriting any file:
1. Scan the project's current version for `PROJECT-SECTION-START` / `PROJECT-SECTION-END` marker pairs
2. Extract each marked block along with its label and the heading it appears under (nearest `#`/`##`/`###` above)
3. **Review each marked block against upstream changes** (see §2.1d below)
4. After copying the upstream file, re-inject each block at its original heading position (unless user chose to update/remove during review)
5. If the heading no longer exists in the upstream file, append the block at the end of the file with a warning comment: `<!-- MIGRATION WARNING: heading "[heading]" no longer exists in upstream — block preserved at end of file -->`
6. Log all re-injected blocks and review decisions in the migration report
7. **Inject bundle fragments (`BUNDLE-SECTION`).** After PROJECT-SECTION re-injection: strip any `BUNDLE-SECTION` blocks remaining in the file, then for each installed bundle whose `fragments` map targets this file (alphabetical bundle order), append the fragment content **read from the z-sdlc source at `[target_tag]`** wrapped in `BUNDLE-SECTION-START/END: [bundle]/[fragment]` markers. No content review — these blocks are upstream-owned; hand-edits inside them are discarded by design. Injection counts as a file write for the adapter `post-file-write` callout. Log each injected fragment in the migration report.

### 2.1d PROJECT-SECTION Content Review

Markers preserve project content, but that content can become stale, conflicting, or improvable as upstream evolves. Before blindly re-injecting, review each marked block against upstream changes.

**For each extracted `PROJECT-SECTION` block:**

1. **Identify the surrounding context:**
   - Which section heading is it under?
   - What was the upstream content in that section at `source_version`?
   - What is the upstream content in that section at `[target_tag]`?

2. **Detect upstream changes to the same area:**
   ```bash
   # Get the section content at old version
   git -C [z-sdlc-path] show [source_version]:<path> | ... extract section ...
   
   # Get the section content at target release
   git -C [z-sdlc-path] show [target_tag]:<path> | ... extract section ...
   
   # Compare
   diff <(old_section) <(new_section)
   ```

3. **Classify the marker review finding** — types: `OK`, `REVIEW`, `ORPHAN`, `OPPORTUNITY`, `CONFLICT`. Full classification table, detection thresholds, and user prompt format: see `references/marker-review-findings.md`.

4. **Build the review findings list** — collect all non-`OK` findings across all files

5. **Present findings to user via `AskUserQuestion`** — use the prompt format in `references/marker-review-findings.md`. User chooses per-finding: keep, update, remove, or merge. Apply decisions and log per that reference.

   <!-- Prompt format, decision application, and logging format extracted to references/marker-review-findings.md -->
   <!-- Finding type detection rules (REVIEW, ORPHAN, OPPORTUNITY, CONFLICT thresholds) also in that reference -->

**When to skip review:**

- If `source_version` is unknown (first migration after legacy install), skip review — no baseline to compare against
- If the block label starts with `deviation-` (wrapped by previous migration), always flag for review — these are temporary preservations that should be re-evaluated
- If the block is < 7 days old (parse date from label), skip review — too recent to be stale

**Why this matters:** Markers protect project content from being overwritten, but they don't protect it from becoming stale. A discipline capture from 6 months ago may reference patterns that upstream has since improved. An agent wiring entry may use outdated dispatcher logic. Blind re-injection preserves content but also preserves technical debt. This review step ensures markers serve their purpose (preserving project work) without becoming a mechanism for accumulating outdated customizations.

**Ensure `.claude/agent-memory/` is gitignored.** Agent memories are not source-controlled — check the project's `.gitignore` for the entry. If missing, append:

```
# Agent memory — private scratchpad, not source-controlled
# Reusable learnings flow through knowledge_feedback → discipline capture → knowledge stores
.claude/agent-memory/
```

If the project was previously committing agent memory files, note this in the migration report. The files can remain in the working tree but should not be committed going forward. If agent memory files are currently tracked by git, unstage them:

```bash
git rm -r --cached .claude/agent-memory/ 2>/dev/null
```

### 2.1-post: Adapter Post-File-Write

**Adapter delegation:** After each file is written or merged (§2.1 direct copies, §2.1e CLAUDE-SDLC.md merge, §2.2–§2.4 content merges), if the adapter declares a `post-file-write` phase:

1. Check whether the file matches the adapter's declared filter (from the handler doc's `**Applies to:**` and `**Skip:**` lines)
2. If it matches, execute the adapter's `post-file-write` instructions on that file
3. If the adapter's handler specifies `halt` on failure, stop the migration on transformation error

When no adapter is declared, this step is skipped entirely — no overhead for non-adapter projects.

### 2.1a Remove Deleted and Moved Files

Check the z-sdlc changelog for files that were **deleted, moved, or renamed** since the project's `source_version`. These require explicit cleanup in the downstream project — direct copy only adds files, it doesn't remove stale ones.

**Process:**

1. From the diff in Phase 1.1, identify any files that were deleted or moved:
   ```bash
   git -C [z-sdlc-path] diff --name-status [source_version]..[target_tag] | grep -E '^[DR]'
   ```

   Ignore paths under `process/changelog-archive/`: z-sdlc's archive is never installed, so nothing of it is in the project to remove or move.

2. For each deleted file: remove it from the downstream project's `[sdlc-root]/` directory.

3. For each moved/renamed file: the new location was already copied in §2.1. Remove the old location. Then check whether the project's `agent-context-map.yaml` references the old path — if so, update the path (see §3.3).

4. **Scan agent memory files for stale paths (if they exist locally).** Agent memory files (`.claude/agent-memory/*.md`) are not git-tracked but may exist locally and contain hardcoded knowledge file paths that bypass the context map. For each deleted or moved file path, grep agent memories:
   ```bash
   grep -rl "old/path/to/file.yaml" .claude/agent-memory/ 2>/dev/null
   ```
   Update any matches to the new path, or remove references to deleted files.

5. Log all removals and path fixes so the migration report (Phase 4.6) includes them.

6. **Clean up legacy files no longer installed to child projects:**
   
   - **Standalone CLAUDE-SDLC.md:** If `[sdlc-root]/CLAUDE-SDLC.md` exists as a separate file, verify its content is already in `CLAUDE.md` (via §2.1e), then remove it:
     ```bash
     rm [sdlc-root]/CLAUDE-SDLC.md
     ```
   - **Contract-driven cleanups:** Check `pending_changes` (from §1.2b) for entries that describe file relocations or removals. Apply them here — delete old-path files after verifying the new-path copy landed.
   
   Log any removals in the migration report.

**Why this matters:** Without cleanup, downstream projects accumulate orphan files. Worse, if a file was moved (e.g., `knowledge/architecture/foo.yaml` → `knowledge/coding/foo.yaml`), agents mapped to the old path load a stale copy while the updated version sits unwired at the new path. Agent memories are a second source of path references that §3.3 (context map) doesn't cover — they must be scanned separately.

### 2.1b Knowledge YAML Key-Level Merge

**Adapter delegation:** If the adapter declares a `knowledge-update` phase (H2 section exists in handler doc), skip this entire subsection. Execute the adapter's `knowledge-update` instructions instead — the adapter handles knowledge updates via its backend's native diff/upsert semantics. Resume at §2.1c after the adapter's phase completes (or halts on failure).

---

Knowledge YAML files contain domain patterns that projects naturally extend with project-specific additions. Unlike framework logic files, knowledge is additive — projects add their own patterns alongside upstream patterns. Direct-copy would destroy these additions.

**Merge strategy:**

- **New upstream keys** → add to project file
- **Existing project keys** → preserve project version (may be intentionally customized)
- **Project-only keys** → preserved automatically (no markers needed)
- **`spec_relevant` field** → special handling (see below)

**Process for each knowledge YAML:**

1. **New file (doesn't exist in project):** Copy from upstream as-is.

2. **Existing file:** Perform key-level merge:
   ```
   For each top-level key in upstream:
     If key doesn't exist in project → add it
     If key exists in project → keep project version, flag if upstream differs
   Project-only keys → keep (these are project additions)
   ```

3. **`spec_relevant` handling:**
   - Project `true` + upstream `false` → keep project's `true` (project override)
   - Project `false` + upstream `true` → keep project's `false`, flag for review:
     ```
     Knowledge spec_relevant upstream upgrade: [file] — upstream now marks as spec-relevant. Review whether to adopt.
     ```
   - Missing in project → copy from upstream

4. **Flag merge conflicts** in migration report when upstream updated a key the project also has:
   ```
   Knowledge merge conflicts (review recommended):
   - [file]: upstream updated `[key]`, project version kept
   ```
   This ensures projects are aware of upstream improvements without silently overwriting their customizations.

**First migration introducing `spec_relevant`:** If no knowledge file in the project has `spec_relevant` at all (the field didn't exist before this migration), all files will receive `spec_relevant: false` from upstream. After Phase 4 completes, prompt CD to review which stores should be tagged `true` for this project — same walkthrough as `sdlc-initialize` Phase 6d:

1. List all knowledge YAMLs grouped by discipline with their `name` and `description`
2. Mark commonly spec-relevant stores with `*` (see `knowledge/README.md` § "spec_relevant Field" for examples)
3. CD selects which to tag `true`; update the files
4. If CD skips, all files stay `false` and `sdlc-plan` filtering remains dormant (backward compatible)

**Why merge-only:** Knowledge YAMLs capture domain patterns — both framework patterns (upstream) and project-specific patterns (local additions like custom enum mappings, project conventions, incident learnings). Direct-copy destroys project knowledge; key-level merge preserves both sources.

### 2.1c Deviation Detection

Before direct-copying any file, detect whether the project has made custom changes outside existing `PROJECT-SECTION` markers:

**Process:**

1. Read the project's current version of the file
2. Read the previous upstream version (at `source_version` commit): `git -C [z-sdlc-path] show [source_version]:<path>`
3. Diff the project's version against the previous upstream version
4. Identify changes that are:
   - **Inside markers** — already protected, will be preserved automatically (§2.1 marker preservation)
   - **Outside markers** — project customizations that will be lost on overwrite

5. If the project modified content outside existing markers, present the customizations via `AskUserQuestion`:

```
DEVIATION DETECTED: [file path]

The project has customized this framework file outside of any PROJECT-SECTION markers.
These changes will be lost when the upstream version is copied.

Customized sections:
  [heading or line range]: [brief description of what changed]
  [heading or line range]: [brief description of what changed]

Options:
1. Wrap customizations in markers — preserve this and future migrations
2. Overwrite — accept upstream version, discard customizations
3. Skip — don't update this file
```

6. If the user chooses option 1: wrap each customized section in `<!-- PROJECT-SECTION-START: deviation-YYYY-MM-DD-label -->` markers before applying the upstream copy, then proceed with marker-preserving copy
7. If option 2: direct copy as normal
8. If option 3: skip this file, log in migration report

**Why this matters:** Without deviation detection, `sdlc-migrate` silently destroys intentional project-specific changes. Users invest time customizing business suite content, discipline captures, and agent wiring — a migration that discards that work without warning erodes trust in the framework.

### 2.1e CLAUDE-SDLC.md Merge

**CLAUDE-SDLC.md is not maintained as a separate file in child projects.** Its content lives directly in the project's `CLAUDE.md`. During migration, update the SDLC sections in `CLAUDE.md` rather than copying a separate file.

**Process:**

1. **Read the upstream CLAUDE-SDLC.md** content via git:
   ```bash
   git -C [z-sdlc-path] show [target_tag]:CLAUDE-SDLC.md
   ```

2. **Identify the SDLC section boundaries** in the project's `CLAUDE.md`:
   - Look for markers like `# Z-SDLC` or the characteristic SDLC headings (`## SDLC Skills`, `## Knowledge Stores`, etc.)
   - If the project uses `<!-- SDLC-START -->` / `<!-- SDLC-END -->` markers, use those as boundaries

3. **Compare and update:**
   - Diff the project's SDLC sections against the upstream CLAUDE-SDLC.md
   - Apply framework updates (new skills, changed workflow rules, updated paths)
   - Preserve project-specific customizations within the SDLC sections (custom agent names, project-specific instructions)

4. **Clean up stale separate file:** If `[sdlc-root]/CLAUDE-SDLC.md` exists as a separate file (legacy from older installations), delete it after verifying its content is already in `CLAUDE.md`:
   ```bash
   rm [sdlc-root]/CLAUDE-SDLC.md
   ```

**Why this matters:** Maintaining CLAUDE-SDLC.md as a separate file creates confusion — users must remember to read two files, and updates to the separate file don't automatically propagate to what Claude Code actually sees. Merging into CLAUDE.md keeps everything in one place.

### 2.2 Content-Merge: Skills

**Step 0 — Dual-audience skill detection.** Before content-merging any skill, check whether z-sdlc source has a framework-dev counterpart at `.claude/skills/zsdlc-{name}/` (e.g., `zsdlc-ingest` exists alongside `skills/sdlc-ingest/`). If a `zsdlc-*` counterpart exists, the installed skill is **dual-audience** — its source version is a generic template that projects customize heavily after installation. Dual-audience skills use **additive-only merge**: propagate genuinely new framework sections (sections that exist in upstream but not in the project at all) but never overwrite or content-merge existing sections. This prevents replacing a project's customized methodology with the generic template version.

Current dual-audience skills: `sdlc-audit`, `sdlc-ingest`, `sdlc-develop-skill`, `sdlc-research`.

Skills have two layers:
1. **Framework structure** — dispatch patterns, gate logic, manager rules, cross-domain injection
2. **Project customizations** — build commands, agent names, project-specific examples, tech stack references

**Migration process for each non-dual-audience skill:**

1. Read the z-sdlc source version of the skill
2. Read the project's version of the skill
3. Identify framework-level changes (new sections, updated dispatch logic, added/removed gates)
4. Apply those changes while preserving:
   - Project-specific build commands (e.g., `pnpm build` vs `[build command]`)
   - Project-specific agent names in tables and examples
   - Project-specific examples and terminology
   - Project-specific health check URLs and test commands
   - `[PLUGIN: ...]` guards that have been resolved to direct invocations

**Verbatim rule:** Framework content must be copied verbatim from the z-sdlc source — do not summarize, rephrase, condense, or rewrite in your own words. The source text is the canonical version. When merging, replace the project's framework sections with the exact z-sdlc text, then re-apply project-specific values (build commands, agent names, etc.) into the appropriate placeholders. If a framework section contains `[build command]` or similar placeholders, substitute the project's actual values — but do not rephrase the surrounding framework text.

**Key rule:** If a section exists in z-sdlc but not in the project, add it. If a section was removed from z-sdlc, remove it from the project. If a section was modified in z-sdlc, update the framework logic while keeping project-specific values.

**PROJECT-SECTION preservation with review:** If `PROJECT-SECTION` blocks exist within a skill being content-merged, apply the §2.1d content review process. Present findings to user before re-injection. These blocks contain project-specific content (e.g., dispatcher table entries added by `sdlc-develop-agent`, custom modifications from `sdlc-develop-skill`) that survive migration — but may need updating if upstream changed the surrounding framework patterns.

**BUNDLE-SECTION fragment injection (applies to every content-merged framework file, §2.2–§2.4 alike):** after the merge (and any PROJECT-SECTION re-injection) completes for a file, run the same fragment pass as §2.1 step 7 — strip any remaining `BUNDLE-SECTION` blocks, then for each installed bundle whose `fragments` map targets this file, append the current fragment from the z-sdlc source at `[target_tag]`. Most fragment targets are content-merged skills, so skipping this pass here would leave their bundle hooks stale or stripped while only direct-copied targets refresh.

### 2.3 Content-Merge: Disciplines

Discipline files have:
1. **Framework structure** — status line, knowledge store reference, summary, mutation verification rules, level definitions (in process-improvement.md only)
2. **Project additions** — parking lot entries (with triage markers), active questions, project context sections
3. **Project-assessed data** — the Process Maturity Tracker in `process-improvement.md` (levels reflect the downstream project's state, not the source repo's)

**Migration process:**
1. Update framework sections to match z-sdlc — **verbatim, not rephrased**
2. Preserve all parking lot entries with their triage markers (these are project-specific knowledge)
3. Preserve active questions
4. Preserve project context sections (added by `sdlc-initialize` Phase 7)
5. Add any new seeded insights from z-sdlc that the project doesn't have — but do NOT overwrite triage markers on existing entries (the project may have triaged differently than the source repo)
6. **Preserve project parking lot entries.** Discipline parking lot entries are project-specific — they don't have PROJECT-SECTION markers because discipline files are not overwritten during migration. Simply preserve all entries with their triage markers.
7. **Preserve the Process Maturity Tracker table as-is.** The tracker is delimited by `<!-- PROJECT-TRACKER-START -->` and `<!-- PROJECT-TRACKER-END -->` markers. Everything between these markers (including the table and last-updated note) reflects the project's assessed levels — never overwrite it. Update the framework sections *outside* the markers (level definitions, assessment procedure) to match z-sdlc. If the downstream file lacks these markers, treat the entire `### Process Maturity Tracker` section through the next heading as project data and preserve it.

### 2.4 Content-Merge: Audit Skill

`sdlc-audit` is a **dual-audience skill** (see §2.2 Step 0). Its reference docs (`compliance-methodology.md`, `improvement-methodology.md`) are heavily customized by projects to match their audit scope (deliverable catalogs, artifact chains, project-specific dimensions). The z-sdlc source version audits the framework source repo itself — a fundamentally different audience.

**Additive-only merge for dual-audience reference docs:**

1. Read the z-sdlc source versions of all audit skill files
2. Read the project's versions
3. For `SKILL.md`: update only the skill's frontmatter (description, triggers) and add any genuinely new sections not present in the project. Do NOT overwrite existing workflow, modes, or dispatch logic that the project has customized.
4. For `references/*.md`: add new reference files that don't exist in the project. For existing reference files, add only new sections (identified by H2/H3 headings not present in the project version). Never overwrite existing sections — the project's audit dimensions and methodology reflect its own structure.
5. Preserve all project-specific audit dimensions, improvement categories, and report formats.

**Migration note:** The `sdlc-compliance-auditor` agent has been restored as a subagent dispatched by `sdlc-audit`. If the project has an old version, update it to the current version. If the project removed it during a prior migration, re-install it.

### 2.5 Content-Merge Verification Gate

**Before proceeding to agent updates**, verify the content-merge results from §2.2–2.4 didn't corrupt project data. This catches merge errors before they propagate into agent wiring.

**Quick checks (< 2 minutes):**

1. **Tracker integrity** — read `[sdlc-root]/disciplines/process-improvement.md` and verify:
   - `<!-- PROJECT-TRACKER-START -->` / `<!-- PROJECT-TRACKER-END -->` markers are present
   - The table between markers contains the project's levels (not the z-sdlc source repo's levels)
   - Level definitions outside the markers were updated to match z-sdlc

2. **Parking lot preservation** — spot-check 2 discipline files:
   - Project-specific entries (dates, deliverable references) are still present
   - Triage markers (`[NEEDS VALIDATION]`, `[DEFERRED]`, `Promoted →`) were not overwritten
   - New seeded insights from z-sdlc were added without disturbing existing entries

3. **Skill customization preservation** — spot-check 1 skill:
   - Project-specific build commands, agent names, and examples are intact
   - Framework sections were updated (compare against z-sdlc source)

4. **Audit skill** — verify all reference files were updated and any project-specific audit dimensions preserved

**Gate rule:** If any check fails, fix the merge before continuing. Do not proceed to Phase 3 with corrupted content — agent wiring decisions depend on accurate discipline and knowledge state.

---

## Phase 3: Update Project Agents

Project agents are NOT framework files — they're project-specific. But some sections come from the framework template and should be updated when the template changes.

### 3.1 Identify Template-Derived Sections

These sections originate from the framework and should be updated across all project agents:

| Section | Source | Update Rule |
|---------|--------|-------------|
| `## Knowledge Context` | agent-template | Must exist in every agent. If missing, add it. If present, update to match template wording. |
| `## Communication Protocol` | agent-template | Update the canonical protocol reference. Preserve domain-specific handoff fields. |
| Memory section header/guidelines | agent-template | Update generic guidelines and "Surfacing Learnings to the SDLC" section. Preserve domain-specific "what to save" content. |

**NOT template-derived:** the frontmatter `description` field is author/project-owned and is never auto-updated here, even when `agent-template.md`'s description convention changes (e.g., example-count tiering). Overwriting a project's hand-tuned trigger examples with framework defaults would be a regression, not an update. §3.4 offers an advisory-only trim suggestion instead — the project team decides.

### 3.2 Apply Template Updates

For each agent in `.claude/agents/`:
1. Check if `## Knowledge Context` section exists — add if missing
2. Verify Communication Protocol references `[sdlc-root]/knowledge/architecture/agent-communication-protocol.yaml`
3. Verify memory section guidelines match the latest template
4. Do NOT touch: scope ownership, core principles, workflow, anti-rationalization tables, self-verification checklists, domain-specific content

### 3.3 Update Agent-Context-Map (if needed)

The agent-context-map is **never overwritten** because projects have their own agent names. But it must be updated for four scenarios:

**New knowledge files added to existing roles:** If z-sdlc added new YAML files that are relevant to existing agents:
1. Read the project's `agent-context-map.yaml`
2. Read the z-sdlc source's `agent-context-map.yaml` for the new mappings
3. Add new file paths to the project's existing agent entries (matching by role, not by exact name)

**New role entries:** If z-sdlc added an entirely new role section to the agent-context-map (e.g., `business-analyst`):
1. Read the project's `agent-context-map.yaml`
2. Check if the project has an agent that matches the new role (by role name or responsibility — e.g., the project may use `ba-agent` instead of `business-analyst`)
3. If a matching agent exists: add the new role section using the project's agent name, with the z-sdlc knowledge file paths
4. If no matching agent exists: add the role section as-is (the project can customize or remove it later)
5. Note the addition in the migration report so the project team can review the wiring

**Moved/renamed knowledge files:** If z-sdlc moved a file from one directory to another (identified in §2.1a):
1. Search the project's `agent-context-map.yaml` for the old path
2. Replace with the new path
3. Verify the new path exists on disk

**Removed knowledge files:** If z-sdlc deleted a knowledge file:
1. Search the project's `agent-context-map.yaml` for references to the deleted file
2. Remove those references
3. Note the removal in the migration report

Never remove project-specific mappings that aren't in the z-sdlc source — those were added during initialization or by the project team.

### 3.4 Downstream Impact Analysis

New or updated knowledge files and process docs may conflict with or improve the child project's existing artifacts — skills, agents, discipline entries, and knowledge overrides. This step identifies those impacts so the project team can decide what to act on.

**When to run:** Only when the migration includes new or substantively changed knowledge files, discipline insights, or process docs (identified in §1.2/§1.3). Skip if the migration is purely structural (file moves, template updates, manifest changes).

**What to scan in the child project:**

| Child Artifact | Where | What to Check Against New Knowledge |
|----------------|-------|-------------------------------------|
| Skill descriptions | `.claude/skills/*/SKILL.md` frontmatter | Activation framing rules — flag advisory descriptions ("best practices", "guidance for") that should use mandatory framing |
| Skill bodies | `.claude/skills/*/SKILL.md` content | AVOID example safety — flag unguarded anti-pattern examples missing the correct-pattern pairing |
| Skill bodies | `.claude/skills/*/SKILL.md` content | Deterministic-first — flag procedural instructions (file scanning, API calls, pattern matching) that could be scripts |
| Agent definitions | `.claude/agents/*.md` | New knowledge wiring — do any agents work in domains covered by newly added knowledge files but aren't wired to them? |
| Agent descriptions | `.claude/agents/*.md` frontmatter | Description-economy convention — flag `<commentary>` blocks, 3+ `<example>` blocks, or a missing "Do NOT use for" boundary sentence; suggest a trim (advisory only, see §3.1) |
| Discipline parking lots | `[sdlc-root]/disciplines/*.md` | Stale entries — do any `[NEEDS VALIDATION]` entries now have evidence from newly landed knowledge? |
| Project knowledge | `[sdlc-root]/knowledge/**/*.yaml` | Contradictions — do any project-specific knowledge rules conflict with newly landed upstream rules? |

**Process:**

1. **Read the changelog entries being applied** (from §1.2) to identify which new knowledge files and process changes are landing. Extract the key principles, rules, and patterns from each.

2. **Scan child skills:**
   - Glob `.claude/skills/*/SKILL.md`
   - For each skill, read the frontmatter `description` field and check activation framing
   - For each skill, grep for AVOID/DON'T/NEVER patterns without an adjacent correct-pattern ("Instead do", "DO this")
   - For each skill, grep for procedural instructions that describe step-by-step API calls, file reads, or pattern matching that could be a script
   - **Do not modify skills.** Collect findings.

3. **Scan child agents:**
   - Glob `.claude/agents/*.md` (excluding framework agents: `sdlc-reviewer.md`, `sdlc-compliance-auditor.md`)
   - For each agent, read its domain expertise description
   - Cross-reference against newly added knowledge files — if a new knowledge file covers a domain the agent works in but isn't in the agent's `## Knowledge Context` section, flag it
   - For each agent, check the frontmatter `description` field for `<commentary>` blocks, 3+ `<example>` blocks, or a missing "Do NOT use for" boundary sentence — flag against the description-economy convention
   - **Do not modify agents.** Collect findings.

4. **Scan discipline parking lots:**
   - Read each `[sdlc-root]/disciplines/*.md` parking lot
   - For each `[NEEDS VALIDATION]` entry, check if newly landed knowledge provides evidence that would change the triage marker (promote to knowledge, or mark as validated)
   - **Do not modify entries.** Collect findings.

5. **Scan project knowledge:**
   - Read each `[sdlc-root]/knowledge/**/*.yaml` that the project has customized (use `git diff HEAD -- [sdlc-root]/knowledge/` to identify project-modified files)
   - Compare project-added rules against newly landed upstream rules for contradictions
   - **Do not modify files.** Collect findings.

**Present findings via `AskUserQuestion`:**

```
DOWNSTREAM IMPACT ANALYSIS
═══════════════════════════════════════════════════════════════

New knowledge landing this migration:
  [list of new/changed knowledge files and their key principles]

SKILL FINDINGS ([count] skills scanned)
  Activation framing:
    [skill-name] — description uses advisory framing: "[current text]"
      → Suggest: "[mandatory reframing]"
  AVOID examples:
    [skill-name] — line N has unguarded anti-pattern
      → Suggest: pair with correct pattern
  Deterministic candidates:
    [skill-name] — §N describes procedural [API call/file scan] inline
      → Suggest: extract to scripts/ for consistency

AGENT FINDINGS ([count] agents scanned)
  Missing knowledge wiring:
    [agent-name] — works in [domain] but not wired to new [knowledge-file]
      → Suggest: add to agent-context-map.yaml
  Description economy:
    [agent-name] — description has [N] examples with `<commentary>` blocks / missing Do-NOT-use boundary
      → Suggest: trim to 1-2 examples (tiered by confusability), drop `<commentary>`, add boundary sentence

PARKING LOT FINDINGS
  Evidence available:
    [discipline] — "[entry title]" marked [NEEDS VALIDATION], new knowledge
    in [file] provides supporting evidence
      → Suggest: promote or update triage marker

KNOWLEDGE CONFLICTS
  [file] rule [id] conflicts with upstream [file] rule [id]: [description]
    → Suggest: reconcile — project rule may need updating

No findings in a category? Omit that category entirely.
Apply any of these? (list numbers, "all", or "skip")
```

**Gate rule:** User chooses which findings to apply. For each approved finding:
- Skill description reframing → edit the skill's frontmatter
- AVOID example fixes → edit the skill body
- Agent knowledge wiring → edit `agent-context-map.yaml`
- Agent description trim → edit the agent's frontmatter `description` field
- Parking lot triage updates → edit the discipline file
- Knowledge conflict resolution → edit the project knowledge file

Log all applied changes in the migration report (§4.6). Log all skipped findings too — they serve as tech debt awareness.

**Why this matters:** Without this step, new knowledge lands in `[sdlc-root]/knowledge/` but the project's existing skills and agents continue operating with stale assumptions. The knowledge is available but not applied. This step closes the gap between "framework updated" and "project benefits from the update."

---

## Phase 4: Verification

### 4.1 File Path Integrity

```bash
# Verify all agent-context-map paths resolve
for path in $(grep -E '^\s+- ' [sdlc-root]/knowledge/agent-context-map.yaml | sed 's/.*- //'); do
  [ -f "$path" ] || echo "BROKEN: $path"
done
```

### 4.2 Agent Consistency

```bash
# Verify all agents have Knowledge Context section
for agent in .claude/agents/*.md; do
  grep -q '## Knowledge Context' "$agent" || echo "MISSING Knowledge Context: $agent"
done
```

### 4.3 Skill Verification

Spot-check 2-3 skills to confirm:
- Framework sections updated correctly
- Project customizations preserved
- No orphaned references to removed framework features

### 4.3a CLAUDE-SDLC.md Compatibility Check

The project's `CLAUDE.md` contains CLAUDE-SDLC.md content — skill names, process file paths, conventions, and workflow rules. If the migration renamed a skill, changed a convention, or modified a path, the project's CLAUDE.md will have stale references.

**Check for:**

1. **Skill name references (guarded renames)** — driven by `skeleton/contract_changes.yaml` entries with `type: rename_skill`. Only rename references to skills that actually exist in the project. Full guarded rename rules for both skills and agents (inventory check, chained renames, logging): see `references/guarded-renames.md`.

2. **Agent name references in dispatching skills (guarded renames)** — skills that dispatch subagents contain project-specific agent names. Do NOT rename to match upstream unless the target agent exists. Full rules: see `references/guarded-renames.md`.

3. **Process file paths** — verify paths like `[sdlc-root]/process/overview.md`, `[sdlc-root]/process/sdlc_changelog.md`, `[sdlc-root]/process/compliance_audit.md` still exist

4. **Convention changes** — if the changelog (§1.2) flagged breaking convention changes (renamed concepts, changed workflow rules), check whether the project's CLAUDE.md still uses the old terminology

5. **New sections in CLAUDE-SDLC.md** — compare the project's CLAUDE.md SDLC sections against the current `CLAUDE-SDLC.md` source. If new sections were added (e.g., new workflow rules, new verification policies), they should be merged into the project's CLAUDE.md

6. **Optional sections** — some SDLC sections are conditionally included based on project characteristics. Check if the project should have optional sections it doesn't currently have:

   | Optional Section | Detection Signals | Template |
   |-----------------|-------------------|----------|
   | Data Pipeline Integrity | `seeds/`, `scrapers/`, `etl/`, `pipelines/` dirs; `*seed*.{ts,js,py}`, `*scrape*.{ts,js,py}` files; allowlist/blocklist files | `templates/optional/data-pipeline-integrity.md` |
   
   If signals are detected but the section is missing from the project's CLAUDE.md, ask CD whether to add it.

**Gate rule:** If the project's CLAUDE.md references a renamed skill or removed path, fix it. If dispatching skills reference nonexistent agents, keep the project's original agent names. Stale references cause silent process failures — Claude Code follows the instructions but they point nowhere.

### 4.4 Post-Migration Compliance Audit

**MANDATORY — do not skip.** Dispatch the `sdlc-compliance-auditor` subagent directly to verify migration integrity. Do not ask the user to invoke `/sdlc-audit` separately — dispatch the subagent yourself as part of this skill's execution.

**Dispatch prompt for the subagent:**

> Run a compliance audit focused on migration integrity. Check all 9 dimensions, with special attention to:
> - Dimension 7 (Migration Integrity): All framework files match the z-sdlc source at [target_tag]
> - No orphaned files from previous versions remain
> - Agent-context-map paths all resolve
> - Content-merge preserved project data (tracker levels, parking lot entries, skill customizations)
> - CLAUDE-SDLC.md references in CLAUDE.md are valid
> - `agents/sdlc-compliance-auditor.md` is present and current
>
> **Context:** This audit runs immediately after migration applied changes. Uncommitted files in the working tree are expected — the user has not committed yet. Do NOT flag uncommitted migration files as findings.

Present the subagent's findings to the user before proceeding to §4.5.

If the audit returns findings:
- **Critical/Major:** Fix before continuing. Re-dispatch the auditor after fixes.
- **Minor/Info:** Log in the migration report, continue to §4.5.

### 4.4a Adapter Post-Operation

**Adapter delegation:** If the adapter declares a `post-operation` phase, execute the adapter's post-operation instructions after the compliance audit (§4.4) and before the manifest update. This is the adapter's opportunity to run its own integrity verification (e.g., contract residue scan, backend consistency check).

If the adapter's handler specifies `warn-continue` on failure (recommended for this phase), log the warning and proceed to §4.5. If `halt`, stop and report.

When no adapter is declared, skip to §4.4b.

### 4.4b Verify Plugin Readiness

Check whether recommended plugins are installed. This mirrors `sdlc-initialize` Phase 9 and ensures plugin gaps are surfaced on every migration, not just first-time setup.

**context7 (required):**
```bash
grep -r "context7" ~/.claude/settings.json ~/.claude/settings.local.json .claude/settings.json .claude/settings.local.json .mcp.json 2>/dev/null
```

If not found, tell CD:
> context7 is required for library verification. Install via `/plugin install context7` or see `[sdlc-root]/plugins/context7-setup.md`.

**LSP (highly recommended):**
Check for language-appropriate LSP plugin based on the project's technology stack:
```bash
grep -rE "typescript-language-server|pyright|gopls|rust-analyzer|clangd|omnisharp" ~/.claude/settings.json ~/.claude/settings.local.json .claude/settings.json .claude/settings.local.json .mcp.json 2>/dev/null
```

If not found, tell CD:
> LSP is recommended for type-aware code navigation. Install via `/plugin install <language>-lsp` (e.g., `/plugin install typescript-lsp`). See `[sdlc-root]/plugins/lsp-setup.md` for the full language list.

**Playwright MCP (recommended for projects with UI):**
If the project has user-facing UI (frontend components, web pages, templates — check for `*.tsx`, `*.jsx`, `*.vue`, `*.svelte`, `*.cshtml` files in the codebase), check for Playwright MCP:
```bash
grep -r "playwright" ~/.claude/settings.json ~/.claude/settings.local.json .claude/settings.json .claude/settings.local.json .mcp.json 2>/dev/null
```

If not found and the project has UI, tell CD:
> Playwright MCP is recommended for automated UI verification during execution. Install via `/plugin install playwright-mcp` or see `[sdlc-root]/plugins/playwright-mcp-setup.md`.

Log the results for the migration report (§4.6).

### 4.5 Update Manifest

After migration, update `.sdlc-manifest.json`:

1. **Update `source_version`** to the target release tag (e.g., `v1.4.0`). Also set `source_version_sha` to the tag's commit hash for precise diff resolution.
1a. **Point `source_repo` at the framework's current home.** The repository moved from `Inpacchi/cc-sdlc` to `endless-galaxy-studios/z-sdlc` (2026-10-12); GitHub redirects the old URL, but only until something takes the old name. If `source_repo` names `github.com/Inpacchi/cc-sdlc` (HTTPS or SSH, with or without `.git`), rewrite it to the same form at the new home: `https://github.com/endless-galaxy-studios/z-sdlc.git` or `git@github.com:endless-galaxy-studios/z-sdlc.git`. Leave any other value alone (a fork or a local path is deliberate).
2. **Add missing fields** if the manifest predates this migration:
   - `sdlc_root`: set to `[sdlc-root]` detected in pre-flight
   - `installed_files`: back-fill if absent (hash every file in `skeleton/manifest.json` source_files **plus every installed bundle's `skills`, `process` and `tree` files** at its installed path (never its seeds), except the never-overwrite files; mark `installed_at: "backfilled-{CURRENT_VERSION}"`)
   - `installed_bundles`: back-fill from the §2.0a detection result (empty array if no bundles detected)
   - `last_applied_contract_id`: if absent, back-fill to `"0000"` before consuming pending_changes; if already set, leave untouched until step 5 below
   - **Any field added by a `manifest_field_added` contract entry in pending_changes** — apply its `default` value
3. **Refresh `installed_files` hashes.** For every file the migration just touched — direct copies, content-merges, drift resolutions — recompute SHA-256 of the final on-disk content and update the corresponding entry. For drift cases where CD chose "keep mine", record the current hash so the next migration sees a clean baseline. For files CD chose to overwrite with upstream, the new hash reflects the upstream content. This keeps drift detection accurate for the next migration.
4. **Update `installed_bundles`** to include any bundles CD accepted in §4.7.
4a. **Update `bundle_fragments`** to reflect every `BUNDLE-SECTION` fragment injected this run (§2.1 step 7 and §4.7 installs): label `bundle/fragment` → target path. Remove entries for fragments upstream no longer declares (their blocks were stripped by §2.1 step 7's strip pass and not re-added).
5. **Update `last_applied_contract_id`** to the newest `id` in `contract_changes.yaml`. Do this only after §4.3a, §4.7, and every other pending-change consumer has run successfully — if any of them failed, leave the old id so the next migration retries.

```bash
# Read existing manifest
MANIFEST=$(cat .sdlc-manifest.json)

# Update source_version to release tag
MANIFEST=$(echo "$MANIFEST" | jq --arg v "$TARGET_TAG" '.source_version = $v')

# Store the tag's commit SHA for precise diff resolution
MANIFEST=$(echo "$MANIFEST" | jq --arg v "$TARGET_SHA" '.source_version_sha = $v')

# Add sdlc_root if missing
if ! echo "$MANIFEST" | jq -e '.sdlc_root' >/dev/null 2>&1; then
  MANIFEST=$(echo "$MANIFEST" | jq --arg r "$SDLC_ROOT" '.sdlc_root = $r')
fi

echo "$MANIFEST" > .sdlc-manifest.json
```

### 4.5a Catalog Columns

For each `catalog_column_added` entry in pending_changes, update the project's `docs/_index.md` (skip if the file doesn't exist):

1. Find the active deliverables table: the first table whose header row starts `| ID | Name | Status`. If its header already has the entry's `column`, skip the entry (the project added it by hand or a previous run did).
2. Insert the column after the entry's `after` column in the header, a `---` cell in the separator row, and the entry's `default` in every data row of that table. Leave every other table alone.
3. If the entry has a `note` and the file has a `## Notes` section, append the note as a bullet there unless an equivalent bullet already exists.
4. Show CD the diff of `docs/_index.md` with the migration summary. It is project content, so it's never overwritten wholesale. Run this before §4.5 step 5, so a failure leaves `last_applied_contract_id` where it was.

### 4.5b Record the Migration in the Project Changelog

The project's changelog is its own record (§1.3, never overwritten), so the migration records itself there. Prepend one entry above the newest one, in the file's format:

- **Title:** `## YYYY-MM-DD: Migrated to z-sdlc vX.Y.Z (from vA.B.C)`
- **Origin:** the migration, and who ran it.
- **What happened:** one or two sentences: what kind of release it was (fixes, new capabilities, contract changes).
- **Changes made:** the titles of the upstream changelog entries applied (from §1.2), each one line, and what the project decided: drift resolutions, bundles accepted or declined, PROJECT-SECTION reviews, files removed.
- **Rationale:** omit unless the project made a choice worth explaining.

Never copy upstream entries into the project's changelog: the source repo's changelog at the target tag is the full framework history (§1.2 reads it there).

### 4.5c Archive the Project Changelog

After §4.5b's entry is in, run the archive script the migration just installed (§2.1), giving it z-sdlc's changelog and archive files at the target tag:

```bash
{ git -C [z-sdlc-path] show [target_tag]:process/sdlc_changelog.md
  for f in $(git -C [z-sdlc-path] ls-tree --name-only [target_tag] process/changelog-archive/); do
    git -C [z-sdlc-path] show "[target_tag]:$f"
  done
} | python3 .claude/skills/sdlc-archive/scripts/changelog_archive.py archive [sdlc-root]/process/sdlc_changelog.md --upstream -
```

Two kinds of entry move, unedited and in their order, to `[sdlc-root]/process/changelog-archive/YYYY-Qn.md`, and the changelog gets one pointer line:
- **Entries copied from z-sdlc** (older installs and migrations copied them; a `## YYYY-MM-DD: Title` line that matches one upstream), whatever their date and the file's size: the project's changelog holds only its own entries (CD, 2026-10-11).
- **The project's own entries** dated before the previous calendar quarter, once the file is over about 150 KB.

This is automatic (contract 0017): don't ask CD. Exit 2 means the files didn't parse or an entry appears twice, and nothing was written: report it and leave the changelog as it is. Put the counts it prints in §4.6's report. If an adapter declares `post-file-write`, don't run it on the archive files (hard exclusions).

### 4.6 Report to User

```markdown
## SDLC Migration Complete — {N} files updated, all gates passed

[1-2 sentences: what the migration brought (e.g., "Upgraded from v1.2 to v1.3 — added 3 new knowledge files, merged 2 expanded skills, wired 4 agent roles"). State any items needing manual review.]

### Source Version
- Previous: [source_version] ([old SHA short])
- Current: [target_tag] ([TARGET_SHA short])

### Changes Applied
- Agent memory gitignored: yes/already present
- Previously tracked agent memories unstaged: yes/no/not applicable
- Skills updated: N (framework sections merged, project customizations preserved)
- Knowledge files added: N [list new files from upstream]
- Knowledge files merged: N (new upstream keys added, project additions preserved)
- Knowledge merge conflicts: N [list files where upstream updated a key the project also has — review recommended]
- Knowledge spec_relevant overrides preserved: N [list files where project `true` was kept]
- Knowledge spec_relevant upstream upgrades: N [list files where upstream is now `true` — review recommended]
- Knowledge files removed (moved/deleted in source): N [list old paths]
- New agent roles added to context-map: N [list roles]
- Process docs updated: N (direct copy, excluding agent-selection.yaml)
- Templates updated: N (direct copy, excluding templates/optional/)
- Agent template updated: yes/no
- Agents updated: N (Knowledge Context / Communication Protocol sections)
- Agent-context-map paths updated: N (moved/removed file paths corrected)
- Auditor updated: yes/no
- Plugin setup guides added: N [list new plugin setup files — recommend installation to user]
- CLAUDE-SDLC.md merged into CLAUDE.md: yes/no/not needed
- Changelog archived: N entries moved to `changelog-archive/` [list quarter files], changelog now N KB / not needed (under 150 KB or nothing older than the previous quarter)

### Legacy Cleanup
- Standalone CLAUDE-SDLC.md removed: yes/no/not present

### PROJECT-SECTION Content Review (§2.1d)
- Marked blocks found: N
- Reviewed (non-OK findings): N
- Decisions:
  - Kept as-is: N (list labels)
  - Updated by user: N (list labels)
  - Removed: N (list labels)
  - Merged: N (list labels)
- Blocks skipped (too recent or no baseline): N

### Preserved
- Project-specific skill customizations (build commands, agent names, examples)
- Discipline parking lot entries and triage markers
- Process Maturity Tracker (project-assessed levels, not source repo levels)
- Agent-context-map agent names and project-specific mappings
- The project's process changelog (one migration entry prepended, §4.5b; old quarters archived unedited, §4.5c)
- Project agent domain content (scope, principles, workflow, anti-rationalization)
- Knowledge file project additions (project-specific keys preserved via key-level merge)
- Knowledge file `spec_relevant` project overrides (true values preserved)

### Downstream Impact Analysis (§3.4)
- Skills scanned: N
- Agents scanned: N
- Findings: N (applied: N, skipped: N)
- Applied: [list changes made]
- Skipped: [list findings deferred — serves as tech debt awareness]

### Gates Passed
- §1.2 Changelog review: user confirmed migration summary
- §2.5 Content-merge verification: tracker intact, parking lots preserved, skills spot-checked
- §3.4 Downstream impact: user reviewed findings
- §4.3a CLAUDE-SDLC.md compatibility: no stale references / [list fixes]

### Plugins
- context7: [installed / NOT INSTALLED — see [sdlc-root]/plugins/context7-setup.md]
- LSP: [installed / not applicable / NOT INSTALLED — see [sdlc-root]/plugins/lsp-setup.md]
- Playwright MCP: [installed / not applicable (no UI) / NOT INSTALLED — see [sdlc-root]/plugins/playwright-mcp-setup.md]

### Verification
- All agent-context-map paths resolve: yes/no
- All agents have Knowledge Context: yes/no
- Spot-check passed: yes/no
- Post-migration audit: passed/findings fixed (auditor dispatched automatically in §4.4)

### Next Steps
1. Commit the migration with: `sdlc(migrate): upgrade z-sdlc from [source_version] to [target_tag]`
```

### 4.7 Offer Newly Debuted Bundles

After the migration report, surface any `bundle_debut` entry in **pending_changes** whose bundle isn't already installed. Only debut entries pending for this migration trigger the offer — bundles CD previously declined (debut entry is no longer pending because `last_applied_contract_id` has advanced past it) are not re-offered. This prevents nagging every migration about the same bundle.

For each such bundle:

> New bundle available since your last migration: **`[bundle.name]`** — [bundle.description]
>
> Skills it would add: [list bundle.skills]
> Process docs it would add: [list bundle.process — omit line if none]
> Framework files it would hook into: [list distinct bundle.fragments targets — omit line if none]
> Project files it would install: [bundle.tree.to and bundle.seed.to, with a count of each — omit line if neither]
> Requires: [bundle.requires — omit line if none]
>
> Install it now?

**Predecessor detection (before the offer, for bundles carrying `process` files):** check whether any of the bundle's `process` file paths already exist in the project. A hit means the project hand-rolled an equivalent of this bundle before it existed upstream (or received one from another project). Do **not** blind-overwrite. Say what was found and ask CD: **adopt** (preserve the existing file's `PROJECT-SECTION` blocks — including any configuration block — into the bundle's version, replace the body, then flag any project-local `PROJECT-SECTION` blocks in *other* framework files that duplicate what the bundle's fragments now provide, so CD can retire them) or **skip** (leave the hand-rolled version alone; the bundle is not installed and the debut entry is consumed as declined).

**Predecessor detection for bundles carrying a `tree`:** if the project already has files under `tree.to` (it incubated the bundle, or copied it), offer **adopt**: list every tree file whose content differs from the project's copy, with the diff, and on CD's yes replace them; leave the files at seed paths and any files the bundle doesn't list as they are; then render. **Skip** leaves everything alone and declines the bundle. A bundle whose `requires` the project doesn't meet (an `sdlc_root` other than the one required) is not offered; log why.

If CD accepts: copy the bundle's skills and `process` files into the project (same direct-copy flow as §2.1), its `tree` files and any absent `seed` files (§2.0a), run its `render` command, inject its `fragments` into their target files per `[sdlc-root]/process/project-section-markers.md` § BUNDLE-SECTION Markers, **then** append the bundle name to `installed_bundles` and its fragments to `bundle_fragments` (§4.5 steps 4/4a), and log the install in the migration report. If the bundle's process doc carries an **Enablement** section, tell CD it exists and offer to run it now — installing without configuring is valid and leaves the bundle inert.

If CD declines: do nothing. The debut entry will be marked consumed when §4.5 advances `last_applied_contract_id`, so this bundle won't be offered again automatically. CD can still opt in later by editing `.sdlc-manifest.json` → `installed_bundles` manually, which §2.0a will honor on the next migration.

Do **not** auto-install bundles. Do **not** remove installed bundles the project chose to adopt.

---

## Recovery / Emergency Restore

If migration fails, crashes, or leaves the workspace inconsistent, see `references/recovery-procedures.md` for diagnosis commands, state-to-action mapping, and last-resort procedures. Migration is designed to be resumable — most scenarios resolve via re-running `/sdlc-migrate`.

---

## Red Flags

Common anti-patterns and their corrections (20 entries covering direct-copy temptation, agent name assumptions, verbatim rule, guarded renames, marker staleness, and more): see `references/red-flags.md`.

## Integration

- **Feeds into:** `sdlc-audit` skill (post-migration compliance audit)
- **Depends on:** z-sdlc source repo (reads via git), `.sdlc-manifest.json` (version tracking)
- **Uses:** `AskUserQuestion` (changelog review gate, user confirmation), `[sdlc-root]/process/adapter-lifecycle-protocol.md` (when adapter declared), `.claude/skills/sdlc-archive/scripts/changelog_archive.py` (§4.5c)
- **Related:** `sdlc-initialize` (first-time setup — use that, not this, for new projects)

## Migration vs Initialization

| Concern | Initialization (`sdlc-initialize`) | Migration (`sdlc-migrate`) |
|---------|-------------------------------------|----------------------------|
| When | First install | Framework update |
| Agent creation | Creates new agents from scratch | Updates template-derived sections in existing agents |
| Skills | Copies from z-sdlc | Merges framework changes into project-customized skills |
| Context map | Wires generic roles to project agents | Adds new knowledge file mappings only |
| Disciplines | Copies templates | Preserves parking lot entries, updates framework sections |
| Destructive? | No (creates new) | No (merges, never overwrites project content) |
