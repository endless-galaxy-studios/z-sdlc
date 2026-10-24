# Z-SDLC — Claude Code SDLC Toolkit

This is the **source repository** for the z-sdlc framework. It contains SDLC skills, agents, knowledge stores, and compliance tooling that get installed into target projects via the `sdlc-initialize` skill.

## Directives Are Framework Changes

When the user gives a directive in this repo — a preference, a behavior change, a "from now on do X," a "stop doing Y" — it almost always means **change the framework**, not just change how you behave for this one session. Find where that behavior is defined in the SDLC (a skill, process doc, knowledge store, agent, `CLAUDE-SDLC.md`, or template), update it there, log it in `process/sdlc_changelog.md` in the same step, and run the consistency checks below. A directive that only changes your in-session behavior and leaves the framework source untouched is almost always a mistake here.

Example: "ask before rendering HTML instead of auto-rendering" is not a session preference — it's an edit to the post-skill render behavior across the rendering skills, `process/html-rendering.md`, and `CLAUDE-SDLC.md`. Treat directives this way by default; only skip the framework edit if the directive is unmistakably about this conversation alone.

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `skills/` | SDLC skill definitions (installed to target's `.claude/skills/`) |
| `agents/` | Agent definitions — suggestions catalog (ephemeral) and framework subagents (installed to target's `.claude/agents/`) |
| `process/` | Workflow documentation (installed to target's `ops/sdlc/process/`) |
| `templates/` | Document templates and agent template (installed to target's `ops/sdlc/templates/`; `optional/` subdirectory is source-only) |
| `knowledge/` | Domain knowledge stores (installed to target's `ops/sdlc/knowledge/`) |
| `disciplines/` | Discipline parking lots (installed to target's `ops/sdlc/disciplines/`) |
| `plugins/` | Required/optional plugin setup guides (installed to target's `ops/sdlc/plugins/`) |
| `bundles/` | Opt-in bundle fragments (`bundles/<bundle>/fragments/*.md`) — injected into target framework files inside `BUNDLE-SECTION` markers when the bundle is installed. A bundle's skills and process docs live in the normal `skills/`/`process/` locations, listed under `manifest.bundles` instead of `source_files`. |
| `skeleton/` | `manifest.json` — canonical directory structure and file list. `contract_changes.yaml` — structured, append-only record of changes requiring active migration behavior (renames, bundle debuts, manifest field additions). Consumed by `sdlc-migrate`; not installed into projects. |
| `CLAUDE-SDLC.md` | SDLC content merged into target project's CLAUDE.md during initialization (not a separate file) |
| `BOOTSTRAP.md` | One-file bootstrap — curl this, say "Bootstrap SDLC", framework installs itself |
| `skills/sdlc-migrate/` | Skill for content-aware framework updates to existing projects |
| `skills/sdlc-initialize/` | Installation skill — handles full framework setup from GitHub source |

## Skill/Agent Location Convention

| Location | Type | Runs in | Purpose |
|----------|------|---------|---------|
| `skills/`, `agents/` | Project skills/agents | Target projects only | Installed to target's `.claude/skills/` and `.claude/agents/` via `sdlc-initialize`. Never run in z-sdlc source. |
| `.claude/skills/`, `.claude/agents/` | Framework development | z-sdlc source only | Used to maintain the framework itself. Not installed to target projects. |

**Key implication:** Skills in `skills/` must not reference z-sdlc source paths like `skeleton/manifest.json` or bare `agents/` — those don't exist in target projects. Use `[sdlc-root]/...` for SDLC content and `.claude/...` for installed skills/agents.

## Plugin Dependencies

| Plugin | Status | Purpose |
|--------|--------|---------|
| **context7** | Required | Live library/framework documentation lookups — prevents stale API knowledge |
| **LSP** (language-specific) | Highly recommended | Type-aware code intelligence — go-to-definition, find-references, hover, diagnostics |

See `plugins/README.md` for details and `plugins/*-setup.md` for installation instructions.

## Adapter Plugins

z-sdlc is the stable core. Adapter plugins live in separate repos and transform z-sdlc's file-based knowledge references into alternate backends (e.g., memory graphs) at install/migration time.

| Plugin | Location | What It Adapts |
|--------|----------|----------------|
| **neuroloom-sdlc-plugin** | `~/Projects/neuroloom/neuroloom-sdlc-plugin` (local); `endless-galaxy-studios/neuroloom-sdlc-plugin` (GitHub) | Swaps file-based knowledge routing (`agent-context-map.yaml`) for Neuroloom's `memory_search` / `memory_store` MCP calls. Declares lifecycle phase handlers via `adapter.json`; upstream delegates knowledge-seed, knowledge-update, post-file-write, and post-operation phases. `/sdlc-port` remains adapter-independent. Transforms z-sdlc skills during install/migration via a phrasing-contract-driven transformation table (`references/pattern-mapping-rules.md`). |

**The phrasing contract** (`process/knowledge-routing.md` § "Adapter Plugins and the Phrasing Contract") is the interface between z-sdlc and adapters. z-sdlc commits to using a fixed set of standard phrases when referencing the knowledge layer; adapters commit to transforming those exact phrases. When you change a knowledge-layer reference pattern in z-sdlc, tag the changelog entry with `[contract-change]` so adapter maintainers catch it on their next upstream pull.

**Working across both repos:** If a change here affects the contract, make the paired change in `neuroloom-sdlc-plugin` (typically in `references/pattern-mapping-rules.md`). Verify: `grep -n "consult\|Read" ~/Projects/neuroloom/neuroloom-sdlc-plugin/references/pattern-mapping-rules.md` shows the transformation table up to date.

## When Editing This Repo

- Changes to skills, agents, and process docs affect all downstream projects on next migration
- Test changes by copying `skills/sdlc-initialize/` to a scratch project and invoking "Initialize SDLC"
- The `skeleton/manifest.json` is the source of truth for what gets installed — keep it in sync
- CLAUDE-SDLC.md is the drop-in that target projects add to their CLAUDE.md — it must be self-contained
- **The `factory` bundle is imported from its incubator** (CD, 2026-10-12): a private project of the organization's, the incubator, incubates the software factory and z-sdlc imports it with `zsdlc-import-factory` (`.claude/skills/zsdlc-import-factory/`). Its own improvements change the incubator's `.github/factory/` first, then get imported, never copied by hand. Edited here instead: the bundle's skills (`skills/sdlc-triage`, `sdlc-implement`, `sdlc-revise`), `process/factory.md`, the generic seeds (`bundles/factory/seed/`), and **a fix found in a project that installed the bundle** (the pilot project first), which goes straight into `bundles/factory/tree/`. The import keeps those changes and `--to-incubator` copies them into the incubator, which keeps exact copies of the skills and process doc too.
- **z-sdlc runs the framework work it starts** (CD, 2026-10-24): z-sdlc is the authority on the SDLC. Framework work that starts here, the factory's included, is scoped, planned and reviewed by z-sdlc's own judgment, even when its code lands in a project first, as the factory's does in the incubator. That project's process rules (its tiers, its "ask CD which tier", its deliverable catalog) don't govern it: ask CD about the work itself, never which process to run it under. The project's protections still hold: its `main` ruleset, CODEOWNERS review and CI.
- **Bundles share a project** (CD, 2026-10-15): a bundle that adds something a project's GitHub or config holds (labels, workflows, environments, issue types, settings) is checked against every other bundle's rules and audits, and each side's doc says how they meet. Grep the other bundles' fragments and process docs for rules over the same thing before shipping. The factory's labels and github-provenance's label audit had never met, so every factory label read as sprawl.
- **z-sdlc is public** (CD, 2026-10-15): commits, their messages and the files they change name no project of the organization's, no host, no absolute home path (it names its user; `~/...` names no one) and no private address. Write "the incubator" (the private project the factory is incubated in), "the pilot project", "the runner host", "the production machine", and use documentation addresses (`203.0.113.x`) in tests. The import's `specific` patterns catch hosts and paths in imported code; check 6 below catches the rest before anything is pushed. A history that's already public stays as it is. Push `master` and tags by name (`git push origin master`, `git push origin v<x.y.z>`), never `--all` or `--mirror`: a local branch can hold history from before a rewrite.
- **Changelog rule:** When you change any process file (skills, agents, process docs, CLAUDE-SDLC.md, disciplines, knowledge), update `process/sdlc_changelog.md` **immediately in the same step** — not as a follow-up. If the user has to ask for the changelog update, it was already too late.
- **Path variable rule:** Skills, agents, and installed docs reference SDLC paths using `[sdlc-root]` — both directories (e.g., `[sdlc-root]/knowledge/`, `[sdlc-root]/disciplines/`) and specific files (e.g., `[sdlc-root]/knowledge/agent-context-map.yaml`, `[sdlc-root]/process/sdlc_changelog.md`). Never use bare paths like `knowledge/`, `disciplines/`, or `agent-context-map.yaml`. The `[sdlc-root]` placeholder resolves to the project's installed location (typically `ops/sdlc/`). Exception: `sdlc-migrate` and `sdlc-initialize` may use bare paths when documenting z-sdlc source structure or in mapping tables showing source → target.
- **Consistency check rule:** After completing any batch of changes to this repo, run the following checks **before presenting the final summary to the user**. Do not wait to be asked.

### Commit Convention

Use conventional commits with scopes matching the content area:

| Type | Scope | Example |
|------|-------|---------|
| `feat` | `skills`, `agents`, `knowledge`, `process` | `feat(skills): add brand-asset skill` |
| `fix` | `skills`, `agents`, `knowledge`, `process` | `fix(agents): correct frontmatter escaping` |
| `refactor` | `skills`, `agents`, `knowledge`, `process` | `refactor(skills): overhaul archive skill` |
| `docs` | omit or specific area | `docs: update plugin setup guide` |
| `ci` | omit | `ci: add auto-release workflow` |
| `chore` | omit | `chore: update manifest` |

The scope tells you *what* changed; the type tells you *how* it changed.

### Versioning (release tags)

Tags are `vMAJOR.MINOR.PATCH`; pushing a `v*` tag triggers the release workflow (notes auto-generated from changelog entries since the previous tag). Bump rules (CD decision, set with v1.7.0/v1.7.1):

- **Minor** — new contract surface: a new cross-skill contract or process convention, new command surface (a new skill or skill mode), or new data schema that downstream projects write into their own files. **Purely additive `contract_changes.yaml` entries — opt-in bundle debuts and manifest field additions with back-fill defaults — are minor, not major** (CD decision, 2026-09-02): they force no behavior change on existing installs that decline them.
- **Patch** — everything else: fixes, doc iterations, and strengthening of checks/steps within existing contracts — even when the commits are `feat`-typed.
- **Major** — breaking changes that force active migration behavior on existing installs (renames, phrasing-contract breaks, non-optional `contract_changes.yaml` entries).

Do not cut or push tags without CD's explicit request.

### Consistency Checks (mandatory after process changes)

**1. Manifest completeness** — Every file on disk must be in `skeleton/manifest.json` and vice versa:
```bash
# Validate JSON
python3 -c "import json; json.load(open('skeleton/manifest.json'))"
```
- Glob `skills/*/SKILL.md`, `skills/*/references/*.md`, `skills/*/scripts/*.py`, `agents/*.md`, `knowledge/**/*.yaml`, `knowledge/**/*.d2`, `process/*.md`, `templates/*.md`, `disciplines/*.md`, `plugins/*.md`, `playbooks/*.md`, `bundles/*/fragments/*.md`
- Compare against manifest `source_files` entries **and `bundles` entries** (bundle skills/process/fragments are listed under `manifest.bundles`, not `source_files`). Report any file on disk not in manifest, or manifest entry without a file.
- A bundle's `tree.from` and `seed.from` directories (`bundles/*/tree/`, `bundles/*/seed/`) are listed as directories, not file by file: check each one named exists and has files, and that nothing under `bundles/<name>/` sits outside `fragments/`, `tree/` and `seed/`. `sdlc-initialize` is the installer (`BOOTSTRAP.md` copies it) and is deliberately not in the manifest.

**2. Stale reference scan** — Grep for old/removed names across the codebase:
- Any recently renamed/removed skills, agents, plugins, or concepts
- Only changelog entries should reference old names

**3. Cross-reference consistency:**
- New skills listed in `skeleton/manifest.json` → `source_files.skills`
- New skills have commands in `CLAUDE-SDLC.md` (if user-invokable)
- New agents listed in `skeleton/manifest.json` → `source_files.agents`
- New knowledge files wired in `knowledge/agent-context-map.yaml` to relevant roles
- `sdlc-initialize` references new skills/agents/knowledge where relevant
- `sdlc-migrate` handles new files in its migration strategy (§2.1 for direct copy, §3.3 for context-map wiring)

**4. Agent installation paths** — Framework subagents in `agents/` install to `.claude/agents/` (not `ops/sdlc/agents/`). Verify `sdlc-initialize` Phase 1 copies them correctly.

**5. Hard-coded path scan** — Grep skills and agents for bare SDLC paths that should use `[sdlc-root]`:
```bash
grep -r '`\(knowledge\|disciplines\|playbooks\|process\|templates\|plugins\)/[^R\[\*]' skills/ agents/
```
Ignore hits in `sdlc-migrate` and `sdlc-initialize` (source path documentation) and example output blocks. All other references to these directories should use `[sdlc-root]/...`.

**6. Public-content scan** — before pushing, nothing unpushed may name a private project, host or path. The names themselves live in `.claude/private-names.txt` (one per line, untracked and git-ignored, since this file is public): create it from the organization's project and host names if it's missing.
```bash
names=.claude/private-names.txt fail=0
test -s "$names" || { echo "FAIL: $names is missing or empty"; fail=1; }
git rev-parse -q --verify origin/master > /dev/null || { echo "FAIL: no origin/master (fetch it first)"; fail=1; }
git log -p origin/master..master | grep '^+' | grep -inFf "$names"; [ $? = 1 ] || fail=1
git log --format=%B origin/master..master | grep -inFf "$names"; [ $? = 1 ] || fail=1
git log -p origin/master..master | grep -nE '^\+.*\b100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.'; [ $? = 1 ] || fail=1
[ "$fail" = 0 ] && echo "check 6: clean"
```
It passes only when it prints `check 6: clean` and nothing else, and its last line then exits 0. A `FAIL` line, a match, or grep's error (exit 2) fails it, and the block exits non-zero, so a push chained after it (`bash check6.sh && git push …`) stops before it runs. (A git failure inside a scan doesn't show in its exit, even under `pipefail`, since grep's 1 comes last: the `origin/master` line is what catches a range that can't be read.) Only added lines count: a diff's context can quote what's already public. An absolute home path names its user, so the names file catches it; the last scan catches tailnet addresses. A hit in a commit not yet pushed is reworded before the push, history included (`git filter-branch` over `origin/master..master`).

If any check fails, fix it before committing. Do not present the summary until all checks pass.
