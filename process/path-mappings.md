# Path Transformation Rules

Throughout this migration, apply these transformations when copying or merging content.

## Source → Project Path Mapping

| z-sdlc Source Path | Project Path |
|---------------------|--------------|
| `knowledge/` | `[sdlc-root]/knowledge/` |
| `disciplines/` | `[sdlc-root]/disciplines/` |
| `process/` | `[sdlc-root]/process/` |
| `templates/*` (manifest-listed files) | `[sdlc-root]/templates/` |
| `playbooks/` | `[sdlc-root]/playbooks/` |
| `examples/` | `[sdlc-root]/examples/` |
| `agents/` | `.claude/agents/` (always — Claude Code requires this location) |
| `skills/` | `.claude/skills/` (always — Claude Code requires this location), including a skill's `references/` and `scripts/` |
| `bundles/<bundle>/tree/` (an installed bundle's `tree.from`) | the bundle's `tree.to` (the factory: `.github/factory/`), same relative paths, executable bits kept |
| `bundles/<bundle>/seed/` (`seed.from`) | the bundle's `seed.to`, only where nothing is there yet (see below) |

**Not installed to child projects:**
- `templates/optional/` — Conditional CLAUDE.md appendices (e.g., `data-pipeline-integrity.md`). Read from z-sdlc source during initialization when needed, not installed.
- `CLAUDE-SDLC.md` — Content is merged into the project's `CLAUDE.md` during initialization. No separate file is maintained.
- `process/changelog-archive/` — z-sdlc's own archived changelog entries: history, not framework content. Migration reads them from the source (`sdlc-migrate` §1.2); a project's own archive is written in the project.
- `process/sdlc_changelog.md`'s entries — a new project's changelog is the file's header plus one install entry (`sdlc-initialize` Phase 1b), not a copy.

## Project-Specific Files (Never Overwrite)

Some files in the z-sdlc source are **templates** that become project-specific after initialization. These must NOT be direct-copied during migration:

| File | Reason |
|------|--------|
| `process/agent-selection.yaml` | Project's agent roster and dispatch rules — contains project-specific agent names |
| `knowledge/agent-context-map.yaml` | Project's agent-to-knowledge mappings — already protected in §3.3 |
| `knowledge/provenance_log.md` | Project's knowledge provenance records — append-only log of ingestions and research handoffs |
| `process/sdlc_changelog.md` | Project's record of process changes — its own entries and the migrations it applied. Migration prepends an entry for itself (`sdlc-migrate` §4.5b) and never copies z-sdlc's file over it; framework history is read from the source repo (§1.2) |
| `process/changelog-archive/` | The project's archived changelog entries, one file per quarter, moved unedited from its changelog by `changelog_archive.py` (`sdlc-archive`, and `sdlc-migrate` §4.5c). Never copied from z-sdlc, never transformed by an adapter |
| A bundle's `seed` files (the factory: `.github/factory/factory.json`, `planning.json`, `services.json`, `triage-policy.md`, `README.md`, and the tests of the project's CODEOWNERS) | The project's settings, policy and notes. Written once at install where absent, never overwritten, hashed or removed (contract 0019) |
| `.claude/skills/verify/` (written in the project by `sdlc-develop-verify-skill`, not copied from z-sdlc) | The project's verify skill: its launch recipe, feature map and helper scripts. It is not in the manifest, and migration never writes, overwrites or removes it. |

Framework files may contain canonical agent names (e.g., `frontend-developer`) in examples. These are illustrative — they don't affect dispatch behavior. The project's actual agents in `.claude/agents/` and `agent-context-map.yaml` define what gets dispatched.

## Dual-Audience Skills (Additive-Only Merge)

Some skills in z-sdlc `skills/` have a framework-development counterpart in `.claude/skills/zsdlc-*/`. The `skills/` version is a generic template installed to projects; the `.claude/skills/zsdlc-*/` version is for maintaining z-sdlc itself. After installation, projects heavily customize these skills — their methodology, reference docs, and workflow diverge from the generic template.

During migration, these skills use **additive-only merge**: propagate genuinely new sections that don't exist in the project, but never overwrite or content-merge existing sections. Detection: if `.claude/skills/zsdlc-{name}/` exists in z-sdlc source, `skills/sdlc-{name}/` is dual-audience.

| Installed Skill | Framework Counterpart | Why Dual-Audience |
|-----------------|----------------------|-------------------|
| `sdlc-audit` | `zsdlc-audit` | Project audits deliverable catalogs, artifact chains. Framework audits manifest completeness, setup.sh, CLAUDE-SDLC.md commands. |
| `sdlc-ingest` | `zsdlc-ingest` | Project ingests into project knowledge stores. Framework ingests into z-sdlc source artifacts. |
| `sdlc-develop-skill` | `zsdlc-create-skill` | Project creates project skills with PROJECT-SECTION awareness. Framework creates source skills with manifest registration. |
| `sdlc-research` | `zsdlc-research` | Project researches for project knowledge. Framework researches for framework enrichment. |
