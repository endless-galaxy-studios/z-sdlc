---
name: sdlc-initialize
description: >
  Bootstrap a new project with the z-sdlc framework — determines whether this is a greenfield or retrofit
  initialization, then walks through the full setup: ideation, spec drafting, skeleton installation, CLAUDE.md
  authoring, deliverable catalog, domain agent creation, knowledge seeding, discipline initialization, and
  verification. This is the single entry point for any project adopting z-sdlc.
  Triggers on "initialize sdlc", "bootstrap sdlc", "set up sdlc", "sdlc init", "initialize this project",
  "bootstrap this project", "set up the SDLC", "I want to use z-sdlc", "integrate sdlc",
  "I'd like to bootstrap the SDLC process in this project".
  Do NOT use for resuming existing SDLC work — use sdlc-status to find active deliverables.
  Do NOT use for creating a single deliverable — use sdlc-plan.
  Do NOT use when SDLC is already initialized (ops/sdlc/ exists and is populated) — use sdlc-status instead.
---

# SDLC Initialize

Orchestrate the full initialization of z-sdlc in a project. This skill detects the project state, selects the right initialization mode, and walks through each phase with CD approval at key gates.

**This skill sets up the framework. It does NOT create deliverables beyond the founding spec.** After initialization, hand off to `sdlc-plan` or `sdlc-lite-plan` for the first piece of implementation work.

**Argument:** `$ARGUMENTS` (optional — z-sdlc source path, or project description for greenfield)

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## Pre-Agent Reality

In greenfield mode, **no domain agents exist until Phase 4.** This means:

- Phases 0–3 are a direct conversation between CD and CC. There is no one to dispatch.
- The Manager Rule does not apply until agents exist. CC writes the spec, CLAUDE.md, and catalog entries directly.
- The Manager Rule activates at Phase 4 and applies for the remainder of the skill and the full session.

This is the only SDLC skill where CC does domain work directly. The justification is structural: you cannot dispatch agents that haven't been created yet.

## Transaction Log

Every phase writes append-only JSONL entries to `.sdlc-transaction-log` for recovery diagnostics. Log events include `run_start`, `phase_start`/`phase_end`, `gate`, `mutation`, `checkpoint`, `warning`, `failure`, and `run_end`.

See `[sdlc-root]/process/transaction-log-schema.md` for the full schema, entry types, run ID conventions, and recovery reading guide.

## Mode Detection

Before starting, determine which mode applies:

```
INITIALIZATION ASSESSMENT
Project directory: [path]
Has existing code: [yes/no — check for src/, lib/, app/, or language-specific indicators]
Has existing docs: [yes/no — check for docs/, README.md beyond boilerplate, specs, design docs]
Has ops/sdlc/: [yes/no]
Has ops/sdlc-lite/: [yes/no — lite install present; triggers Lite Graduation mode]
Has .claude/skills/: [yes/no]
Has .claude/skills/sdlc-lite-plan/ or sdlc-lite-execute/: [yes/no]
Has .sdlc-manifest.json: [yes/no]
Has spec in docs/current_work/specs/: [yes/no — check for d*_spec.md files]
Has agents in .claude/agents/ (beyond template): [yes/no]
```

| State | Mode | Entry Point |
|-------|------|-------------|
| `ops/sdlc/` exists and populated, agents exist | **Already initialized** | Report status, suggest `sdlc-status` |
| `ops/sdlc-lite/` exists, `ops/sdlc/` does not | **Lite Graduation** | Phase 0-L (merge lite → full), then Phase 1 |
| No code, no docs (or only boilerplate), no spec | **Greenfield — fresh** | Phase 0 (ideation + spec) |
| Spec exists in `docs/current_work/specs/`, but no agents | **Greenfield — resume** | Phase 1 (skeleton, then agents) |
| `ops/sdlc/` exists, spec exists, but no agents | **Greenfield — resume (post-skeleton)** | Phase 4 (agents) |
| Has code and/or docs, no `ops/sdlc/` | **Retrofit** | Phase R1 (discovery) |
| `.sdlc-manifest.json` exists but `ops/sdlc/` is incomplete | **Repair** | Phase 1 (reinstall from source) |

Present the assessment and mode selection to CD via `AskUserQuestion`:

> Based on what I see, this is a **[mode]** initialization. Does that match your intent, or should I adjust?

**Resume detection:** If the skill was previously invoked and interrupted (e.g., CD ideated in a prior session), the mode detection picks up from wherever it left off. A spec without agents means "ideation is done, continue from scaffolding." A skeleton without agents means "scaffolding is done, continue from agent creation." This makes re-invocation seamless.

---

## Lite Graduation Mode

For projects that installed `BOOTSTRAP-LITE.md` (minimal 3-agent / 2-skill starter) and now want the full framework. Runs Phase 0-L to merge the lite install into the full `ops/sdlc/` layout, preserving all lite agents, skills, discipline entries, knowledge customizations, and changelog history. After graduation, falls through to Phase 1 so the standard install proceeds with lite assets already in place.

See `references/lite-graduation.md` for the full Phase 0-L procedure (inventory, content migration, path rewriting, changelog entry, and per-phase behavior notes for graduated installs).

---

## Greenfield Mode

For new projects with no existing code. CD and CC define the project together before the scaffold is installed.

### Phase 0: Ideation and Spec

This is a direct conversation between CD and CC. No agents exist yet — CC does the work.

The goal is to produce a D1 spec that establishes the project's identity, tech stack, and structure. Without this, agents, knowledge, and disciplines are impossible to meaningfully create.

#### 0a. If a spec already exists

Read it. Verify it establishes at minimum:
- Problem statement — what you're building and why
- Technology stack — languages, frameworks, databases, infrastructure
- Repository structure — monorepo packages or directory layout

If all three are present, summarize and ask CD: "This spec covers the foundations. Ready to proceed with SDLC scaffolding, or do you want to refine it first?"

If critical sections are missing, note what's missing and ask CD whether to flesh it out now or proceed as-is.

Skip to Phase 1.

#### 0b. If no spec exists — Ideation

Tell CD:

> This is a greenfield project. Before I set up the SDLC framework, we need to define what we're building. Tell me about your project — what problem are you solving, who is it for, and what's your initial vision?

Then enter the ideation loop. The principles here are borrowed from `sdlc-idea` but streamlined for initialization:

**Ground in what you can observe.** Before asking follow-up questions, check:
- Does the repo have any files that hint at direction (package.json, requirements.txt, Cargo.toml)?
- Is there a README with any project description?
- Are there any prior art references in the repo?

**Ask one question at a time.** Do not batch questions. Let each answer inform the next. Use AskUserQuestion for each question — this ensures clear consent gates and structured feedback.

**Question priorities for initialization** (these establish what the spec needs):

| Priority | Question Area | Why It Matters |
|----------|--------------|----------------|
| 1 | **Problem + audience** | What are we building and who is it for? |
| 2 | **Technology stack** | Languages, frameworks, databases — determines agents and knowledge |
| 3 | **Repository structure** | Monorepo vs single package, directory layout — determines agent scope |
| 4 | **Deployment target** | Where it runs — determines infrastructure agents and knowledge |
| 5 | **Data model** (if applicable) | Key entities — determines data-modeling knowledge |
| 6 | **Business model** (if applicable) | Monetization, auth model — determines business-analysis discipline |
| 7 | **Non-functional requirements** | Performance bar, security model, compliance needs |

**You do NOT need to ask all of these.** CD may cover several in their initial description. Ask only what's missing. If CD gives a comprehensive description, you may only need 1–2 follow-up questions.

**When CD describes a problem without a solution:** Help them think through the solution space. Sketch 2–3 high-level approaches (not implementations — directional shapes) and let CD pick. This is exploratory, not prescriptive.

**When CD knows exactly what they want:** Don't over-question. If the problem, stack, and structure are clear, move to spec drafting.

**There is no minimum question count.** The goal is a spec with enough content to create agents and seed knowledge. Some projects need 10 minutes of conversation; others need an hour.

#### 0c. Draft the Spec

When enough is understood, draft a D1 spec. CC writes this directly (no agents exist yet).

Use the spec template from z-sdlc source (`templates/spec_template.md`) as the structural guide. For initialization, the spec must cover at minimum:

```markdown
# D1: [Project Name] — Spec

**Deliverable:** D1
**Name:** [Project Name]
**Status:** Draft
**Date:** [today]

---

## Problem Statement
[What this project solves and why it matters — from ideation conversation]

## Technology Stack
[Languages, frameworks, databases, infrastructure — specific versions where known]

## Repository Structure
[Directory layout with purpose annotations]

## Requirements
### Functional Requirements
[Key features — numbered FR-1, FR-2, etc.]

### Non-Functional Requirements
[Performance, deployment, security — numbered NFR-1, NFR-2, etc.]

## Data Model (if applicable)
[Key entities and relationships]

## Dependencies
[External services, libraries, infrastructure]

## Success Criteria
[What "done" looks like for D1]

## Open Questions
[Unknowns to resolve during planning]
```

**The spec does not need to be exhaustive.** It needs to be sufficient to:
1. Create domain agents with meaningful stack-specific system prompts
2. Seed knowledge stores with relevant technology patterns
3. Seed disciplines with project context
4. Write a CLAUDE.md with accurate project instructions

More detail is better, but don't block on completeness. Open questions are expected.

#### 0d. CD Approves the Spec

Present the full spec to CD. Use `AskUserQuestion`:

> Here's the D1 spec. Review it and let me know:
> 1. Approved as-is — proceed to scaffolding
> 2. Changes needed — tell me what to adjust
> 3. Need more exploration — let's keep ideating

If CD requests changes, make them directly (no agents to dispatch) and re-present.

**Gate:** CD must approve (option 1) before Phase 1.

> ## ⚠ POINT OF NO RETURN
>
> **Phase 0 was read-only or preparatory** (ideation, spec drafting, approval gate). Cancellation left no trace.
>
> **Phase 1 is the first phase that commits mutations.** The first `cp` / file write in Phase 1a writes to disk. Once that has run, **cancellation leaves partial state** that requires re-running `/sdlc-initialize` in repair mode or manual cleanup to resolve.
>
> Before proceeding, verify:
> - Phase 0 spec-approval gate returned `approved`
> - Transaction log has a `gate` event for Phase 0 with `result: approved`
>
> Log a `checkpoint: point_of_no_return` event to the transaction log immediately before the first file write.

### Phase 1: Install the Skeleton

**1a. Locate z-sdlc source.**

Determine where the z-sdlc source is. Check in order:

1. `$ARGUMENTS` for an explicit path (e.g., `/tmp/z-sdlc-bootstrap` from BOOTSTRAP.md)
2. Check if `.claude/BOOTSTRAP.md` or `BOOTSTRAP.md` exists — if so, follow its instructions to clone to `/tmp/z-sdlc-bootstrap`
3. Check `/tmp/z-sdlc-bootstrap` (bootstrap flow already cloned it), or `/tmp/cc-sdlc-bootstrap` from a BOOTSTRAP.md copied before the rename
4. Common local locations: `~/Projects/z-sdlc`, `~/z-sdlc`, `../z-sdlc`, then the pre-rename names `~/Projects/cc-sdlc`, `~/cc-sdlc`, `../cc-sdlc`, and `~/src/ops/sdlc`
5. Clone from GitHub to temp: `git clone --depth 1 https://github.com/endless-galaxy-studios/z-sdlc.git /tmp/z-sdlc-bootstrap`

Verify the source by checking for `skeleton/manifest.json`.

**If already installed** (`.sdlc-manifest.json` exists and `ops/sdlc/` is populated): Skip to Phase 1c (verify). Do not reinstall.

**1b. Install files from z-sdlc source.**

Read `skeleton/manifest.json` from the z-sdlc source. This manifest defines the canonical directory structure and file list.

**Optional bundles.** Before copying, read `manifest.bundles`. For each bundle, ask CD whether to install it using `AskUserQuestion`:

> Optional bundle available: **`[bundle-name]`** — [bundle.description]
>
> Skills it adds: [list bundle.skills]
> Process docs it adds: [list bundle.process — omit line if none]
> Framework files it hooks into: [list distinct bundle.fragments targets — omit line if none]
> Project files it installs: [bundle.tree.to and bundle.seed.to, with a count of each — omit line if neither]
> Requires: [bundle.requires — omit line if none]
>
> Install it?
>
> - Yes — include in this installation
> - No — skip (you can add it later via `/sdlc-migrate`)

Record the accepted bundles. The effective install set adds every accepted bundle's `skills` and `process` files to the corresponding `source_files` lists. After all Phase 1 file copies complete, inject each accepted bundle's `fragments` into their target files per `[sdlc-root]/process/project-section-markers.md` § BUNDLE-SECTION Markers: strip any block with the same label, append the fragment content at end of file wrapped in `BUNDLE-SECTION-START/END: [bundle]/[fragment]` markers. Fragment injection counts as a file write — if an adapter declares `post-file-write`, run it on the target after injection.

**Bundles with files outside `.claude/` and `[sdlc-root]/`** (`tree`, `seed`, `render`, `requires`; contract 0019), after the fragment step:

1. **Requires.** If the bundle declares `requires.sdlc_root` and this project's SDLC root differs, don't install it: tell CD why and record it as declined.
2. **Tree.** Copy every file under the z-sdlc directory `tree.from` to the same relative path under the project's `tree.to`, keeping executable bits (`git ls-files -s` mode `100755`). These are framework files: hash them in `installed_files`.
3. **Seed.** For every file under `seed.from`, write it to the same relative path under `seed.to` only if nothing is there. Seeded files are the project's from then on: never hash them, never overwrite them.
4. **Render.** Run the bundle's `render` command from the project root (for the factory, `python3 .github/factory/render.py`, which writes `.github/workflows/factory-*.yml` from the templates and `factory.json`). If it fails, report the error and leave the bundle installed but unrendered: rendering again after fixing the settings is the bundle's Enablement, not a reinstall.

Record accepted bundles in `.sdlc-manifest.json` under an `installed_bundles: []` field, and every injected fragment under `bundle_fragments` (label → target path), so `sdlc-migrate` can tell them apart from legacy installs that pre-date the bundles manifest. **Ordering:** a bundle's entries are written to `installed_bundles`/`bundle_fragments` only after its files are copied and its fragments injected — a crashed install then under-claims rather than over-claims, and a re-run repairs it idempotently.

If an accepted bundle's process doc carries an **Enablement** section (per-project configuration the bundle needs before it activates), tell CD it exists and offer to run it at the end of initialization. Installing without configuring is valid — the bundle stays inert until its Enablement completes.

**Create directories:**
```
For each directory in manifest.directories:
  mkdir -p <target>/<directory>
```

**Copy files by category** using the source → target path mappings in `[sdlc-root]/process/path-mappings.md`. The key transforms: `knowledge/` → `[sdlc-root]/knowledge/`, `agents/` → `.claude/agents/`, `skills/` → `.claude/skills/`, and process/templates/disciplines/playbooks → `[sdlc-root]/` subdirectories.

**Safe file extraction:** See `[sdlc-root]/process/source-repo-safety.md` for verified-content extraction patterns. The core rule: never use shell redirection (`git show > file`) — it truncates the target before git show runs, leaving empty files on failure.

**Not installed to child projects:**
- `templates/optional/` — Conditional CLAUDE.md appendices (e.g., `data-pipeline-integrity.md`). Read from z-sdlc source during Phase 2 when needed, not installed.
- `CLAUDE-SDLC.md` — Content is merged directly into the project's `CLAUDE.md` during Phase 2. No separate file is created.
- `process/changelog-archive/` — z-sdlc's own archived changelog entries. History, not framework content.

**The process changelog starts as the project's own.** Don't copy `process/sdlc_changelog.md`: z-sdlc's entries are the framework's history and stay in z-sdlc, where `sdlc-migrate` reads them. After the skills are copied, write the header and one install entry:

```bash
git -C [z-sdlc-path] show HEAD:process/sdlc_changelog.md \
  | python3 .claude/skills/sdlc-archive/scripts/changelog_archive.py init - [sdlc-root]/process/sdlc_changelog.md --version [source_version]
```

Skip it if the file exists (lite graduation moves the lite changelog there first). If an adapter declares `post-file-write`, don't run it on this file (`[sdlc-root]/process/adapter-lifecycle-protocol.md` hard exclusions).

**Adapter post-file-write:** If an adapter is present and declares `post-file-write`, execute the adapter's transformation instructions on each file after it is written (same per-file callout as in `sdlc-migrate` §2.1-post). The adapter's handler doc declares which file patterns to transform and which to skip.

**Skip existing files** — do not overwrite files that already exist. Track counts:
- Files installed (new)
- Files skipped (already exist)

**Seed the deliverable catalog** if `docs/_index.md` doesn't exist:
```markdown
# Project Deliverable Catalog

This is the single source of truth for all deliverable IDs and their statuses.

## Active Deliverables

| ID | Name | Status | Depends on | Spec | Plan | Result |
|----|------|--------|------------|------|------|--------|

## Completed Deliverables

| ID | Name | Chronicle Location |
|----|------|-------------------|

## Notes

- IDs are sequential and never reused (D1, D2, ... Dnn)
- Sub-deliverables use letter suffixes: D1a, D1b
- Status: Draft | Ready | In Progress | Validated | Deployed | Complete | Archived
- Depends on: the deliverables that must be Complete first, comma-separated (`D11a, D12`); `—` when none. Which phases each one gates is in the plan's Phase Dependencies table; one no phase names gates the whole deliverable. A split parent depends on its parts. See [sdlc-root]/process/deliverable_lifecycle.md § Dependencies
```

**Detect project structure before writing manifest:**

```bash
# Determine SDLC root — default to ops/sdlc unless .claude/sdlc already exists
# (only relevant for repair mode or custom installations)
if [ -d .claude/sdlc ]; then
  SDLC_ROOT=".claude/sdlc"
else
  SDLC_ROOT="ops/sdlc"
fi
```

**Adapter discovery:** Before writing the manifest, scan for adapter plugins:

```
For each directory in .claude/plugins/:
  If {plugin_dir}/adapter.json exists and contains "zsdlc_adapter": true (or the pre-rename "ccsdlc_adapter": true):
    Record as active adapter
```

If an adapter is found, read its `adapter.json` and populate the manifest's `adapter` block (see schema below). If multiple adapters are found, halt with an error. If none found, set `"adapter": null`.

When an adapter is present, this skill delegates specific phases per `[sdlc-root]/process/adapter-lifecycle-protocol.md`:
- Phase 1 (skeleton install) proceeds normally — operational files are written by upstream
- After each file write, if the adapter declares `post-file-write`, upstream executes the adapter's transformation instructions on that file
- Phase 6 (knowledge seeding) is delegated to the adapter's `knowledge-seed` handler instead of writing flat YAML files
- Phase 10 (verification) includes the adapter's `post-operation` handler if declared

When no adapter is found, behavior is identical to before this protocol existed.

**Write `.sdlc-manifest.json`** at project root. Includes an `installed_files` map of SHA-256 hashes for every framework file written in Phase 1 — **including accepted bundles' `skills` and `process` files, hashed after fragment injection, and their `tree` files** (never their seeds, which are the project's). This enables `sdlc-migrate` to detect post-install manual edits (drift) before overwriting.

```json
{
  "_comment": "Generated by sdlc-initialize. Used by sdlc-migrate skill for version tracking.",
  "version": "1.0.0",
  "source_repo": "<git remote origin from z-sdlc source, or 'local'>",
  "source_version": "<latest semver release tag from z-sdlc source (e.g., 'v1.4.0'), or 'unknown'>",
  "source_version_sha": "<commit SHA of the release tag, for precise diff resolution>",
  "install_date": "<ISO 8601 timestamp>",
  "file_count": <number of files installed>,
  "sdlc_root": "<SDLC_ROOT value from detection above>",
  "installed_bundles": ["design"],
  "bundle_fragments": {},
  "last_applied_contract_id": "<newest id in skeleton/contract_changes.yaml at install time>",
  "adapter": null,
  "installed_files": {
    "ops/sdlc/process/overview.md":      { "sha256": "<hash>", "size": <bytes>, "installed_at": "<ISO timestamp>" },
    "ops/sdlc/knowledge/architecture/agent-communication-protocol.yaml": { "sha256": "<hash>", "size": <bytes>, "installed_at": "<ISO timestamp>" },
    ".claude/skills/sdlc-plan/SKILL.md": { "sha256": "<hash>", "size": <bytes>, "installed_at": "<ISO timestamp>" },
    ".claude/agents/sdlc-reviewer.md":   { "sha256": "<hash>", "size": <bytes>, "installed_at": "<ISO timestamp>" }
  }
}
```

**`installed_bundles`:** List of opt-in bundle names the project accepted during initialization. Empty array if none accepted. `sdlc-migrate` uses this field as the authoritative signal for which bundles are installed; for projects installed before bundles existed, migrate falls back to file-existence detection.

**`bundle_fragments`:** Map of injected `BUNDLE-SECTION` fragment labels (`bundle/fragment`) to their target file paths, written when a bundle with `fragments` is installed. Empty object if no installed bundle carries fragments. The compliance auditor validates block presence against this map without needing the z-sdlc source.

**`source_version` and `source_version_sha`:** `source_version` stores the release tag (e.g., `v1.4.0`) — resolve via `git -C [z-sdlc-path] tag -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -1`. `source_version_sha` stores the tag's commit hash for precise diffs. If no tags exist (pre-release source), fall back to `"unknown"` for the tag and store the HEAD SHA. `sdlc-migrate` uses these fields to determine what changed between the installed version and the latest release.

**`last_applied_contract_id`:** The id of the newest entry in `skeleton/contract_changes.yaml` at the time of this install. New projects start already caught up — `sdlc-migrate` will not re-apply historical renames and other one-shot migrations meant for older projects. Read this value from the z-sdlc source when writing the manifest: parse `contract_changes.yaml`, take the last entry's `id`.

**`adapter`:** `null` when no adapter plugin is found. When an adapter is discovered (via `adapter.json` in `.claude/plugins/`), this block is populated automatically during Phase 1:

```json
"adapter": {
  "plugin": "<plugin name from plugin.json>",
  "plugin_root": "<path to adapter plugin root, relative to project root>",
  "supported_zsdlc_version": "<from adapter.json: supported_zsdlc_version, or the pre-rename supported_ccsdlc_version>",
  "phase_handlers": "<from adapter.json>"
}
```

See `[sdlc-root]/process/adapter-lifecycle-protocol.md` for field semantics, discovery logic, and the `adapter.json` schema.

**Hash generation:** SHA-256 of the file's content as written to disk.

```bash
sha256sum "{path}" | awk '{print $1}'
# or Python: hashlib.sha256(open(path, "rb").read()).hexdigest()
```

**Scope of `installed_files`:**
- **Include:** every file installed from `skeleton/manifest.json` source_files — skills, agents, process docs, templates, knowledge YAMLs, disciplines, plugins
- **Exclude:** project-generated files (`docs/_index.md`, anything under `docs/current_work/`, `[sdlc-root]/process/sdlc_changelog.md`), user-owned files (`CLAUDE.md` project root), `.sdlc-manifest.json` itself

Project-specific files (e.g., `knowledge/agent-context-map.yaml` after wiring) are expected to drift — those are handled by migrate via merge logic, not by hash comparison. `installed_files` tracks unexpected drift in files CD never intended to modify.

The `sdlc_root` field enables `sdlc-migrate` to resolve the project's SDLC root path (`ops/sdlc/` vs `.claude/sdlc/`) during migration. The `installed_files` map enables drift detection during migration (see sdlc-migrate §1.2a).

Report progress to CD:
```
INSTALLATION PROGRESS
Source: [z-sdlc path]
Files installed: [count]
Files skipped: [count] (already exist)
```

**1c. Verify installation.**

Validate against `skeleton/manifest.json` source_files — every file listed must exist at its target path. Report any missing files.

```
SKELETON CHECK
Directories created: [count]
Files installed: [count]
Files skipped: [count]
.sdlc-manifest.json: [exists/missing]

Required directories:
[ ] docs/current_work/audits/
[ ] ops/sdlc/playbooks/
[ ] ops/sdlc/plugins/
[ ] ops/sdlc/examples/

Required files (commonly missed):
[ ] ops/sdlc/knowledge/README.md
[ ] ops/sdlc/knowledge/architecture/README.md
[ ] ops/sdlc/knowledge/data-modeling/README.md
[ ] ops/sdlc/knowledge/design/README.md
[ ] ops/sdlc/knowledge/product-research/README.md
[ ] ops/sdlc/knowledge/testing/README.md
[ ] .claude/skills/sdlc-migrate/SKILL.md
[ ] [sdlc-root]/templates/agent-template.md
[ ] [sdlc-root]/templates/external-review.sh.template (non-.md — do NOT chmod +x; inert until the project enables the gate)
[ ] [sdlc-root]/templates/external-review-knowledge.sh.template (non-.md — same rule)
[ ] .claude/agents/AGENT_SUGGESTIONS.md (ephemeral — deleted in Phase 12)
[ ] .claude/skills/sdlc-audit/SKILL.md
[ ] ops/sdlc/plugins/README.md
[ ] ops/sdlc/plugins/context7-setup.md
[ ] ops/sdlc/plugins/lsp-setup.md
```

If any are missing, copy them from the z-sdlc source. Do not proceed to Phase 2 with missing files.

### Phase 1d: Ensure private state files are gitignored

Several files are per-session or per-agent scratchpads that must not be git-tracked. Check the project's `.gitignore` and append missing entries.

| Entry | Purpose |
|-------|---------|
| `.claude/agent-memory/` | Per-agent scratchpad. Reusable learnings flow through `knowledge_feedback` → discipline capture → knowledge stores instead. |
| `.sdlc-transaction-log` | Per-run JSONL log of init/migrate phase events. Diagnostic-only; regenerated on each run. |

If any entry is missing, append:

```
# Agent memory — private scratchpad, not source-controlled
# Reusable learnings flow through knowledge_feedback → discipline capture → knowledge stores
.claude/agent-memory/

# SDLC session diagnostic logs
.sdlc-transaction-log
```

If `.gitignore` doesn't exist, create it with these entries (plus any standard entries for the project's language/framework).

### Phase 2: Write CLAUDE.md

CC writes CLAUDE.md directly (agents don't exist yet). Use the spec as the source of truth.

**If CLAUDE.md already exists:** Read it. Preserve all existing content. Add the SDLC process section if not present.

**If CLAUDE.md does not exist:** Author it from scratch.

**Required sections for greenfield CLAUDE.md:**

1. **Project header** — name, one-paragraph description
2. **Repository layout** — directory tree with purpose annotations (from spec)
3. **Technology stack** — per-package if monorepo (from spec)
4. **Coding standards** — per-language conventions
   - If multi-language: document the boundary conventions (e.g., snake_case API, camelCase frontend)
5. **SDLC process section** — read `CLAUDE-SDLC.md` from z-sdlc source and merge the full content into this section, adapted for this project
6. **Verification policy** — zero-assumption rule, Context7 for external libs, read code before asserting
7. **Agent dispatch conventions** — agent-first, never self-implement, manager rule

**Optional sections (detect and include if applicable):**

8. **Data Pipeline Integrity** — include if the project has data pipelines, seed scripts, scrapers, ETL, or allowlists. Detection signals:
   - Directories: `seeds/`, `scrapers/`, `etl/`, `pipelines/`, `data/`
   - Files: `*seed*.{ts,js,py}`, `*scrape*.{ts,js,py}`, `*allowlist*`, `*blocklist*`
   - Spec mentions: "seed", "scrape", "ETL", "pipeline", "ingest", "allowlist"
   
   If detected, read `templates/optional/data-pipeline-integrity.md` from z-sdlc source and append to CLAUDE.md. If uncertain, ask CD.

**Gate:** Present the drafted CLAUDE.md to CD. Use `AskUserQuestion`: "CLAUDE.md is ready for review. Any changes before I save it?"

### Phase 3: Register D1 in the Catalog

1. Read `docs/_index.md` (installed by Phase 1 with the template)
2. Register the project's founding deliverable as D1
3. Set status to `Draft` with a link to the spec
4. Increment "Next ID" to D2
5. Save the spec to `docs/current_work/specs/d1_name_spec.md` if it isn't there already

This is mechanical — CC does this directly.

### Phase 4: Create Domain Agents

This is the highest-effort phase. Agents must be customized for the project's actual stack.

**From this phase forward, the Manager Rule activates.** Agents created in this phase will be dispatched for work in subsequent phases.

**4a. Determine agent roster.**

Based on the spec's technology stack, propose a set of domain agents:

| Project Type | Typical Count | Core Roles |
|-------------|--------------|------------|
| Single-framework web app | 4–6 | frontend, backend, code-reviewer, sdet |
| Full-stack with separate API | 6–8 | + db-engineer, devops, debug-specialist |
| Multi-package monorepo | 8–12 | + per-package specialists, architect, security |
| CLI / library | 3–5 | core-engineer, code-reviewer, sdet |

Present the proposed roster to CD via `AskUserQuestion`:

> Based on the spec, I recommend these domain agents: [list with one-line domain descriptions]. Add, remove, or adjust?

**4b. Create each agent.**

**MANDATORY: Invoke `/sdlc-develop-agent` for each agent.** Do NOT write agent files directly. The skill handles:
- Frontmatter validation (name format, description with `<example>` blocks)
- System prompt scaffolding (Knowledge Context, Communication Protocol, Anti-Rationalization Table)
- Template compliance (agent-template.md structure)

**Mandatory agents (create these regardless of project size):**
1. **`software-architect`** — dispatched by both review and planning skills, seeds disciplines and knowledge in later initialization phases, and reviews every other agent's plan output. Create first so it's available for dispatch throughout initialization.
2. **`code-reviewer`** — always dispatched in every review skill (Tier 1, unconditional). Without it, no review skill produces findings. This is the one agent that reviews every diff regardless of what changed.

If CD's proposed roster omits either of these, add them and explain why. These are not optional.

**Creation order (after mandatory agents):**
3. Core implementation roles (backend, frontend)
4. Specialized roles (db-engineer, security, performance)
5. Testing and infrastructure (sdet, build-engineer)

**Framework agents (pre-installed by Phase 1 — do NOT create as domain agents):**
- `sdlc-reviewer` — reviews skill/agent files against z-sdlc conventions (dispatched by `sdlc-develop-skill`, `sdlc-develop-agent`)
- `sdlc-compliance-auditor` — performs 10-dimension compliance scan (dispatched by `sdlc-audit`)

The `sdlc-audit` skill is already installed by Phase 1 — do not recreate it as an agent.

**Pass stack context to the agent creation skill.** Each agent's system prompt must reference the project's actual technologies, not generic placeholders. Include in the creation prompt:
- Which packages/directories the agent owns
- Which frameworks/libraries the agent should know
- Key file paths and conventions from the spec

**4c. Report progress.**

After each agent is created, report to CD: "Created [agent-name] — [domain coverage]." After all agents are created, list the full roster.

**4d. Spec-vs-roster reconciliation.**

Before moving to Phase 5, compare the created agent roster against any agent roles mentioned in the spec (e.g., FR requirements that reference "domain agents" or list specific roles). If the spec lists agents that were not created, or agents were created that the spec doesn't mention:

```
ROSTER RECONCILIATION
Spec-listed roles:    [list from spec FRs/NFRs]
Created agents:       [list from .claude/agents/]
Match:                [yes / deviations listed below]
Deviations:
  - [role] — [not created / created but not in spec] — [reason]
```

Present deviations to CD. This prevents the neuroloom-bootstrap gap where spec-listed agents were silently dropped without a deviation record.

**4e. Verify dispatcher wiring.**

`/sdlc-develop-agent` Step 6 wires each agent into the dispatching tables during creation. After all agents are created, verify that nothing was missed:

```
DISPATCHER WIRING CHECK
Agent                    | agent-selection.yaml | sdlc-plan agent table | sdlc-plan infra triggers
-------------------------|--------------------------|----------------------|------------------------
software-architect       | Tier 1 (always)          | yes                  | n/a
frontend-developer       | Tier 1                   | yes                  | yes
backend-developer        | Tier 1                   | yes                  | yes
code-reviewer            | Tier 1 (always)          | yes                  | n/a
sdet                     | Tier 1                   | yes                  | n/a
...
```

For each created agent, confirm:
1. A tier1 or tier2 entry exists in `ops/sdlc/process/agent-selection.yaml` (if the agent reviews code)
2. A row exists in the `sdlc-plan` agent table
3. An infra trigger row exists in `sdlc-plan` / `sdlc-lite-plan` (if the agent owns an infrastructure domain)

If any agent is missing from a table it belongs in, add the entry now. These dispatcher table entries must be wrapped in `PROJECT-SECTION` markers per `ops/sdlc/process/project-section-markers.md` (they live in framework files that get overwritten on migration).

### Phase 5: Wire the Agent-Context Map

1. Read `ops/sdlc/knowledge/agent-context-map.yaml`
2. List the agents just created: `ls .claude/agents/*.md`
3. For each mapping entry:
   - Rename generic roles to match the project's actual agent filenames
   - Remove mappings for roles that have no corresponding agent
   - Add mappings for project-specific agents not in the generic list
4. Save the updated map

No PROJECT-SECTION markers needed — `agent-context-map.yaml` is a project-specific file that is preserved entirely during migration.

This is mechanical — the orchestrator does this directly. The agent filenames must match exactly for self-discovery to work.

### Phase 6: Seed Knowledge Stores

**Adapter delegation:** If the adapter declares a `knowledge-seed` phase (detected during Phase 1's manifest write), delegate knowledge seeding entirely to the adapter's handler instructions. The adapter ingests knowledge into its backend rather than writing flat YAML files. Skip §6a–6d and resume at Phase 7.

When no adapter is declared, proceed with flat-file knowledge seeding below.

---

**Now that agents exist, dispatch them for knowledge work.**

**6a. Assess knowledge store relevance.**

Read every YAML file in `ops/sdlc/knowledge/` (installed by Phase 1). Each file has a `project_applicability` block:

```yaml
project_applicability:
  relevant_when: "condition describing when this store applies"
  action_if_irrelevant: keep | customize | remove
```

For each file, compare its `relevant_when` condition against the D1 spec (tech stack, domain, architecture). Classify each as:

- **Keep** — condition matches the project, or `action_if_irrelevant: keep` (always relevant)
- **Customize** — condition doesn't match but the file has a useful structure; replace content with project-appropriate equivalents (e.g., swap MUI DataGrid patterns for your component library)
- **Remove** — condition doesn't match and the content isn't adaptable

Present the assessment to CD:

```
KNOWLEDGE RELEVANCE ASSESSMENT
Based on the D1 spec, here is how each knowledge store maps to this project:

Keep (always relevant or matches spec):
  [x] debugging-methodology — Always relevant
  [x] security-review-taxonomy — Always relevant
  [x] agent-communication-protocol — Governs z-sdlc agents
  [x] typescript-patterns — Project uses TypeScript
  [x] design/component-patterns — UI component rules (any project with a UI)
  [x] design/interaction-animation — Interactive states, micro-interactions
  [x] design/visual-design-rules — Color theory, dark mode, shadows
  [x] design/layout-principles — Spacing, grid, structural layout
  ...

Customize (useful structure, replace content for your stack):
  [~] testing/tool-patterns — Currently Playwright CLI; replace with [your test tool]
  [~] testing/timing-defaults — Currently React/MUI; replace with [your components]
  [~] testing/component-catalog — Currently MUI DataGrid; replace with [your components]
  ...

Remove (not applicable to this project):
  [ ] payment-state-machine — No payment features in spec
  [ ] ml-system-design — No ML/AI model training in spec
  [ ] pipeline-design-patterns — No ETL/batch pipelines in spec
  ...
```

Use `AskUserQuestion` to let CD confirm. CD may override any classification (e.g., "keep payments — we'll add Stripe in Q2").

**Actions after CD confirms:**
- **Keep** files: no changes needed
- **Customize** files: note them for Phase 6c (agent will rewrite content for the project's stack)
- **Remove** files: delete them from `ops/sdlc/knowledge/` and remove their entries from `agent-context-map.yaml`

**6b. Identify stack-specific knowledge gaps.**

For each major technology in the spec's stack, ask: "What would an agent need to know that isn't obvious from the documentation?" Categories:

- **Gotchas** — things that look right but break
- **Patterns** — the project's preferred way of doing common things
- **Boundaries** — where one technology meets another

**6c. Create stack-specific knowledge files.**

Dispatch the `software-architect` agent (or nearest equivalent) to draft knowledge YAML files for the project's stack-specific technologies. Each file follows the z-sdlc knowledge format:

```yaml
id: technology-patterns
name: Technology Patterns
description: One-line description
last_updated: YYYY-MM-DD
content:
  - category: Category Name
    items:
      - name: Pattern Name
        description: What this is
        details: Why it matters and how to apply it
```

**Verify via Context7** before writing knowledge files that reference external library APIs. Do not seed knowledge with training-data assumptions about library behavior.

Present the list of knowledge files to CD. This is informational, not a gate — CD can adjust later.

**6d. Tag spec-relevant knowledge stores.**

Walk through all installed knowledge YAML files and identify which should inform spec writing for this project. Present the list grouped by discipline:

```
SPEC-RELEVANCE TAGGING
Which knowledge stores should inform spec writing for this project?
(Stores marked with * are commonly spec-relevant)

Architecture:
  [ ] api-design-methodology — API design patterns
  [ ] backend-capability-assessment — Backend assessment rubric
  [*] security-review-taxonomy — Security posture is a spec-level concern
  ...
Data Modeling:
  [*] people-and-organizations — Party/role data model patterns
  [*] meta-framework — Universal data modeling framework
  ...
Design:
  [*] ux-modeling-methodology — UX interaction modeling
  [*] accessibility-testability-principles — Accessibility rules
  ...
Product Research:
  [*] product-methodology — Product methodology shapes feature scoping
  ...
Testing:
  [*] testing-paradigm — Test type selection (always loaded at spec time by sdlc-plan)
  ...
```

CD selects which stores to mark as `spec_relevant: true`. Update the selected files' `spec_relevant` field from `false` to `true`.

**Guidance:** Tag at least 2-3 files, or leave all as `false` for full loading. Tagging only one file may produce under-informed specs. See `knowledge/README.md` § "spec_relevant Field" for semantics.

**If CD skips this step:** All files stay `false` and `sdlc-plan` spec-time filtering remains dormant — all mapped files load at spec time (backward-compatible behavior). CD can tag stores later by asking the orchestrator to "review spec-relevance tags."

### Phase 7: Seed Discipline Parking Lots

Read each of the 9 discipline files in `ops/sdlc/disciplines/`. For each, add a "## Project Context" section with 3–5 bullets specific to this project's stack and domain.

Dispatch the `software-architect` agent to produce the seed content for all 9 disciplines in one pass, given the spec as input. The agent returns the seed content; the orchestrator appends it to each file.

| Discipline | Seed Focus |
|-----------|-----------|
| architecture | Repo layout, service boundaries, API-first vs monolith |
| coding | Per-language conventions, cross-language boundaries |
| testing | Test suites per package, isolation challenges, mocking stance |
| design | Theme direction, component library, brand constraints |
| data-modeling | ORM/query patterns, migration safety, special column types |
| deployment | Target platform, service topology, local dev stack |
| business-analysis | Revenue model, multi-tenancy, auth strategy |
| product-research | Market context, competitive landscape, ecosystem position |
| process-improvement | Note: "First project from z-sdlc — capture friction for upstream" |

### Phase 8: Seed Testing Knowledge

Dispatch the `sdet` agent (or nearest equivalent) to produce `ops/sdlc/knowledge/testing/gotchas.yaml` entries specific to the project's technology stack. For each major technology, the agent should identify:

- Test isolation challenges
- Mocking pitfalls
- Async/timing issues
- Environment-specific gotchas (dev vs CI vs prod)

**Verify gotchas via Context7** for any claims about library-specific test behavior.

If `gotchas.yaml` already has upstream content, append project-specific entries — do not overwrite.

### Phase 9: Verify Plugin Readiness

Check whether required plugins are installed:

**context7 (required):**
```bash
grep -r "context7" ~/.claude/settings.json ~/.claude/settings.local.json .claude/settings.json .claude/settings.local.json .mcp.json 2>/dev/null
```

If not found, tell CD:
> context7 is required for library verification. Install via `/plugin install context7` or see `ops/sdlc/plugins/context7-setup.md`.

**LSP (highly recommended):**
Check for language-appropriate LSP plugin based on the spec's technology stack.

If not found, tell CD:
> LSP is recommended for type-aware code navigation. Install via `/plugin install <language>-lsp` (e.g., `/plugin install typescript-lsp`). See `ops/sdlc/plugins/lsp-setup.md` for the full language list.

**Playwright MCP (recommended for projects with UI):**
If the project has user-facing UI (frontend components, web pages, templates), check for Playwright MCP:
```bash
grep -r "playwright" ~/.claude/settings.json ~/.claude/settings.local.json .claude/settings.json .claude/settings.local.json .mcp.json 2>/dev/null
```

If not found and the project has UI, tell CD:
> Playwright MCP is recommended for automated UI verification during execution. Install via `/plugin install playwright-mcp` or see `ops/sdlc/plugins/playwright-mcp-setup.md`.


### Phase 9a: Assess Initial Maturity Levels

Read the maturity level definitions in `ops/sdlc/disciplines/process-improvement.md` (§ Process Maturity Levels). For each of the 9 disciplines, assess the initial level based on what was just set up:

**Level 1 (Initial)** — discipline parking lot entries exist but no knowledge store for this discipline.

**Level 2 (Managed)** — knowledge store exists with at least one validated YAML file AND the agent-context-map wires those files to relevant agents AND parking lot has been seeded.

For most fresh installations, the assessment is straightforward:
- Disciplines that received knowledge seeding in Phases 6-8 AND have entries in `agent-context-map.yaml` → Level 2
- Disciplines with only parking lot seeding from Phase 7 → Level 1

Update the Process Maturity Tracker table in `ops/sdlc/disciplines/process-improvement.md` with the assessed levels and evidence. The tracker was copied from the z-sdlc source with source-repo levels — it must be adjusted to reflect this project's actual state.

This is a quick assessment (2-3 minutes total), not a gate. Present the tracker to CD as informational.

### Phase 9b: Verify Command Check

Check whether the project exposes a one-shot verification command per the convention in `ops/sdlc/process/verify-command.md` — a single root entry point (`npm run verify`, `make verify`, `./scripts/verify.sh`, or the stack's equivalent) that chains lint, typecheck, format check, and tests.

```bash
# Examples — adapt to the stack detected in Phase 0
grep -n '"verify"' package.json 2>/dev/null
grep -n '^verify:' Makefile justfile 2>/dev/null
ls scripts/verify.sh 2>/dev/null
```

**If present:** confirm it actually chains the gates CI runs (read the script/target), and ensure it is documented in the project's CLAUDE.md.

**If absent:** tell CD:

> No one-shot verify command found. Agents run verification before every review loop and commit — a single root command keeps that gate from being skipped. Want me to scaffold one? I'll chain the gates that already exist (found: {list}) and report the packages missing lint/typecheck/test scripts as gaps.

If CD accepts, scaffold per `ops/sdlc/process/verify-command.md` § Scaffolding Guidance: chain only what exists, fail fast, document the command in CLAUDE.md. Report (don't silently fix) packages lacking gate scripts — those are findings for CD, not setup work.

**Companion skill:** if the project has an app a user runs and no `.claude/skills/verify/`, tell CD that `/sdlc-develop-verify-skill` can write one: how to launch, health-check, drive and clean up the app, proven end to end. Offer it; don't run it as part of setup.

**Retrofit note:** for retrofit installations this check frequently finds partial coverage (some packages have scripts, some don't). Scaffold the root command over what exists and list the gaps — the codebase-health audit (`/sdlc-audit health`) tracks them afterward.

### Phase 10: Final Verification

**Adapter post-operation:** If the adapter declares a `post-operation` phase, execute the adapter's verification instructions before the standard checklist below. This lets the adapter confirm its backend is consistent (e.g., all knowledge ingested, no untransformed phrasing-contract references remain). If the adapter's handler specifies `warn-continue` on failure, log the warning and proceed. If `halt`, stop and report.

Run through the verification checklist:

```
INITIALIZATION COMPLETE — VERIFICATION

Skeleton & Infrastructure:
[ ] Spec: D1 spec exists in docs/current_work/specs/
[ ] Skeleton: Phase 1 completed, .sdlc-manifest.json present
[ ] All upstream READMEs copied (knowledge/README.md, knowledge/*/README.md)
[ ] All scaffold directories exist: playbooks/, plugins/, examples/, docs/current_work/audits/
[ ] .gitignore: `.claude/agent-memory/` entry present
[ ] CLAUDE.md: exists with all required sections
[ ] Catalog: docs/_index.md has D1 registered
[ ] Verify command: root one-shot verify present and documented, or gaps reported to CD (Phase 9b)

Agents:
[ ] All agents created via /sdlc-develop-agent — confirmed
    Created: [list all agents]
[ ] Mandatory agents created: software-architect, code-reviewer
[ ] Spec-vs-roster reconciliation complete — all spec-listed roles created or deviation logged
[ ] agent-template.md present in [sdlc-root]/templates/
[ ] Framework subagents present in .claude/agents/: sdlc-reviewer.md, sdlc-compliance-auditor.md
[ ] Dispatcher wiring: all agents in agent-selection.yaml, sdlc-plan agent table, infra triggers
[ ] Context map: agent-context-map.yaml wired to actual agent filenames
[ ] All knowledge files mapped in agent-context-map.yaml (no unmapped YAMLs)

Knowledge & Disciplines:
[ ] Knowledge: upstream carried + stack-specific seeded
    Stack-specific files: [list]
[ ] Disciplines: all 9 initialized with project context
[ ] Testing: gotchas.yaml seeded with stack-specific entries
[ ] Maturity tracker: updated with project-assessed levels (not source-repo levels)

Plugins:
[ ] context7: [installed / NOT INSTALLED]
[ ] LSP: [installed / not applicable / NOT INSTALLED]
[ ] Playwright MCP: [installed / not applicable (no UI) / NOT INSTALLED]
```

Present the checklist to CD. If any items failed, note them and suggest remediation.

### Phase 11: Post-Initialization Compliance Audit

Run the compliance audit before declaring initialization complete — this catches structural gaps early. Dispatch the `sdlc-compliance-auditor` subagent directly to verify initialization integrity. Do not ask CD to invoke `/sdlc-audit` separately — dispatch the subagent yourself as part of this skill's execution.

**Dispatch prompt for the subagent:**

> Run a compliance audit on this freshly initialized project. Check all 9 dimensions: catalog integrity, artifact traceability, knowledge layer health, agent-context-map wiring, and file completeness. Note: this is a new project — Dimensions 3 (untracked work), 8 (agent memory mining), and 9 (recommendation follow-through) will have no data, which is expected.

Present the subagent's findings to CD before the final summary.

If the audit returns findings:
- **Critical/Major:** Fix before continuing. These indicate initialization gaps.
- **Minor/Info:** Log and continue — expected for a fresh project (e.g., no chronicle entries yet, no prior audit to follow through on).

After the audit passes (or only minor/info findings remain):

> SDLC initialization complete. Compliance audit: {score}/10.
>
> To start your first piece of implementation work:
> - **New feature or major work:** invoke `sdlc-plan`
> - **Quick task with a plan:** invoke `sdlc-lite-plan`

### Phase 12: Cleanup (Mandatory)

**Run cleanup after successful initialization.**

Remove the temp clone if it exists:

```bash
rm -rf /tmp/z-sdlc-bootstrap
```

Remove the bootstrap file — it served its purpose:

```bash
rm -f .claude/BOOTSTRAP.md BOOTSTRAP.md
```

Remove ephemeral files — these were used during initialization and are no longer needed:

```bash
rm -f .claude/agents/AGENT_SUGGESTIONS.md
rm -rf .claude/skills/sdlc-initialize/
```

**On failure:** If initialization fails partway, still remove `/tmp/z-sdlc-bootstrap` but leave the bootstrap file, AGENT_SUGGESTIONS.md, and sdlc-initialize so the user can retry.

---

## Retrofit Mode

For existing projects with code and documentation that need z-sdlc integrated. Discovers and categorizes existing docs, proposes a migration plan, then runs the standard install while augmenting (not replacing) existing content.

See `references/retrofit-mode.md` for Phases R1–R4.

---

## Recovery / Emergency Restore

If initialization fails, see `references/recovery-emergency.md` for diagnostics and recovery steps.

---

## Red Flags

Common anti-patterns: see `references/red-flags.md`.

## Integration

- **Feeds into:** `sdlc-plan` (first deliverable), `sdlc-lite-plan` (first lightweight task), `sdlc-status` (health check), `sdlc-migrate` (consumes `.sdlc-manifest.json` for version tracking and path detection)
- **Uses:** `/sdlc-develop-agent` (agent creation), Context7 (knowledge verification), `AskUserQuestion` (CD gates), `.claude/skills/sdlc-archive/scripts/changelog_archive.py init` (the project's first changelog, Phase 1b)
- **Produces:** Fully initialized SDLC framework with project-specific agents, knowledge, and disciplines; `.sdlc-manifest.json` with `sdlc_root`, `source_version`, and `installed_files` fields
- **Borrows from:** `sdlc-idea` (ideation principles for Phase 0), spec template (Phase 0c structure)
- **Adapter-aware:** when `manifest.adapter` is declared, delegates knowledge-seed, post-file-write, and post-operation phases per `[sdlc-root]/process/adapter-lifecycle-protocol.md`
