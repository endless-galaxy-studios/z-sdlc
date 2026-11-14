# Lite Graduation Mode

For projects that installed `BOOTSTRAP-LITE.md` (minimal 3-agent / 2-skill starter) and now want the full framework. Runs Phase 0-L to merge the lite install into the full layout, then falls through to Phase 1 so the standard install proceeds with the lite assets already in place and preserved by the skip-existing logic.

## Phase 0-L: Merge Lite Install Into Full Layout

**Entry condition:** `ops/sdlc-lite/` exists and `ops/sdlc/` does not (or is empty). If both exist and `ops/sdlc/` is populated, treat as Already Initialized and report.

**0-L.a. Inventory and confirm.**

Scan and report what will be preserved:

```
LITE GRADUATION INVENTORY
Lite agents (preserved as-is):
  - .claude/agents/software-architect.md
  - .claude/agents/fullstack-developer.md
  - .claude/agents/code-reviewer.md
Lite skills (preserved as-is):
  - .claude/skills/sdlc-lite-plan/
  - .claude/skills/sdlc-lite-execute/
Lite content (moved into ops/sdlc/):
  - ops/sdlc-lite/process/*.md       → ops/sdlc/process/
  - ops/sdlc-lite/disciplines/*.md   → ops/sdlc/disciplines/
  - ops/sdlc-lite/knowledge/**       → ops/sdlc/knowledge/
  - ops/sdlc-lite/templates/*.md     → ops/sdlc/templates/
  - ops/sdlc-lite/sdlc_changelog.md  → ops/sdlc/process/sdlc_changelog.md
Deliverable catalog: docs/_index.md (stays in place; format upgraded in Phase 3)
Lite work history: docs/current_work/sdlc-lite/ (stays as historical record)
```

Confirm via `AskUserQuestion`:

> I've detected an SDLC-Lite install. Graduation will move lite assets into the full SDLC layout (`ops/sdlc/`), preserve your 3 agents and 2 lite skills, and run the full bootstrap to add specs, full agent roster, chronicle, playbooks, and the remaining knowledge stores. Proceed?

Log `phase_start` event with `phase: 0-L`.

**0-L.b. Create full layout skeleton.**

```bash
mkdir -p ops/sdlc/{process,knowledge,disciplines,templates,playbooks,plugins}
mkdir -p ops/sdlc/knowledge/{architecture,coding,data-modeling,design,product-research,testing}
```

**0-L.c. Move lite content into full layout.**

For each source path, move the file (not copy — we want `ops/sdlc-lite/` empty at the end so it can be removed):

| Source | Target |
|--------|--------|
| `ops/sdlc-lite/process/manager-rule.md` | `ops/sdlc/process/manager-rule.md` |
| `ops/sdlc-lite/process/finding-classification.md` | `ops/sdlc/process/finding-classification.md` |
| `ops/sdlc-lite/process/review-fix-loop.md` | `ops/sdlc/process/review-fix-loop.md` |
| `ops/sdlc-lite/disciplines/*.md` | `ops/sdlc/disciplines/` |
| `ops/sdlc-lite/knowledge/agent-context-map.yaml` | `ops/sdlc/knowledge/agent-context-map.yaml` |
| `ops/sdlc-lite/knowledge/architecture/*.yaml` | `ops/sdlc/knowledge/architecture/` |
| `ops/sdlc-lite/knowledge/coding/*.yaml` | `ops/sdlc/knowledge/coding/` |
| `ops/sdlc-lite/knowledge/testing/*.yaml` | `ops/sdlc/knowledge/testing/` |
| `ops/sdlc-lite/templates/sdlc_lite_plan_template.md` | `ops/sdlc/templates/` |
| `ops/sdlc-lite/templates/sdlc_lite_result_template.md` | `ops/sdlc/templates/` |
| `ops/sdlc-lite/sdlc_changelog.md` | `ops/sdlc/process/sdlc_changelog.md` |

Log each move as a `mutation` event.

**After the moves, Phase 1's skip-existing logic preserves every lite customization.** Full-install versions of the same files (e.g., `manager-rule.md`, `finding-classification.md`) will not overwrite. Lite discipline parking lot entries with real insights will not be replaced by empty full-install seeds. Lite knowledge file customizations persist.

**0-L.d. Rewrite `ops/sdlc-lite/` path references.**

Every lite skill, lite agent, and the lite CLAUDE.md block references `ops/sdlc-lite/` directly. Rewrite all references to `ops/sdlc/`:

```bash
# Skills
for f in .claude/skills/sdlc-lite-plan/SKILL.md .claude/skills/sdlc-lite-execute/SKILL.md; do
  [ -f "$f" ] && sed -i.bak 's|ops/sdlc-lite/|ops/sdlc/|g' "$f" && rm -f "$f.bak"
done

# Agents
for f in .claude/agents/software-architect.md .claude/agents/fullstack-developer.md .claude/agents/code-reviewer.md; do
  [ -f "$f" ] && sed -i.bak 's|ops/sdlc-lite/|ops/sdlc/|g' "$f" && rm -f "$f.bak"
done

# Verify no lite paths remain in rewritten files
! grep -l 'ops/sdlc-lite/' .claude/skills/sdlc-lite-*/SKILL.md .claude/agents/*.md
```

**0-L.e. Remove the SDLC-Lite block from CLAUDE.md.**

The lite bootstrap appended a `# SDLC-Lite` section to `CLAUDE.md`. Phase 2 will add the full SDLC-equivalent content. Remove the lite section now so Phase 2 doesn't duplicate it.

1. Read `CLAUDE.md`
2. Find the line `# SDLC-Lite` (must appear with a preceding `---` separator — that's the marker the bootstrap uses)
3. Delete from the preceding `---` through the end of the file (the block is always last — the lite bootstrap appends it, and nothing should follow)
4. If multiple `# SDLC-Lite` occurrences exist, stop and report to CD (manual intervention needed — the file has been customized beyond the bootstrap template)
5. Write the trimmed `CLAUDE.md`

Log as `mutation` with `type: claude_md_lite_block_removed`.

**0-L.f. Remove the empty `ops/sdlc-lite/` directory.**

```bash
# After all moves, ops/sdlc-lite/ should contain no files
if [ -z "$(find ops/sdlc-lite -type f 2>/dev/null)" ]; then
  rm -rf ops/sdlc-lite/
else
  # Something wasn't moved — report and leave the directory in place
  find ops/sdlc-lite -type f
  # Log a warning event; do not delete
fi
```

**0-L.g. Prepend graduation entry to the migrated changelog.**

Edit `ops/sdlc/process/sdlc_changelog.md` — prepend an entry above existing content documenting the graduation:

```markdown
## <ISO-date>: Graduated from SDLC-Lite to full SDLC

**Origin:** `sdlc-initialize` Lite Graduation mode.

**What happened:** Moved lite install from `ops/sdlc-lite/` into `ops/sdlc/`; preserved 3 lite agents, 2 lite skills, lite discipline parking lot entries, and lite knowledge files. Removed the SDLC-Lite block from `CLAUDE.md` (Phase 2 will add the full SDLC block). Proceeded to Phase 1 to install the remaining framework (full agent roster, specs, chronicle, playbooks, remaining knowledge stores).

**Changes made:**

1. **`ops/sdlc-lite/*`** → `ops/sdlc/*` — directory migration
2. **Path references** in lite skills, lite agents, and `CLAUDE.md` rewritten from `ops/sdlc-lite/` to `ops/sdlc/`
3. **`ops/sdlc-lite/`** removed after successful merge

**Rationale:** The lite install is designed as an on-ramp to the full framework. Graduation preserves everything the team built on lite (agents with project-specific scope, discipline entries with real insights, changelog history, deliverable catalog) and layers the full framework on top.
```

**0-L.h. Proceed to Phase 1.**

Log `phase_end` with `result: pass`. Fall through to Phase 1 (Install the Skeleton). Phase 1's skip-existing logic preserves everything the graduation just moved into place.

The remaining phases behave as follows for a graduated install:

- **Phase 1 (Skeleton install):** Adds full framework files that don't already exist. Lite agents, lite skills, lite process docs (manager-rule, finding-classification, review-fix-loop), lite disciplines, lite knowledge, lite templates, and the changelog are all preserved. Full-framework additions: `sdlc-plan` / `sdlc-execute` / `sdlc-audit` / remaining skills, full process docs (deliverable_lifecycle, collaboration_model, knowledge-routing, etc.), chronicle directory, playbooks, remaining knowledge YAML files, remaining discipline files.
- **Phase 2 (CLAUDE.md):** Adds the full CLAUDE-SDLC.md content block (no duplication — the lite block was removed in 0-L.e).
- **Phase 3 (D1 catalog registration):** Upgrades `docs/_index.md` format if needed; preserves existing entries.
- **Phase 4 (Domain agents):** Detects the 3 existing lite agents and does not recreate them. Asks CD whether to add additional full-roster agents (sdet, accessibility-auditor, security-engineer, etc.).
- **Phase 5 (Agent-Context Map):** Preserves lite mappings for the 3 agents; adds entries for new agents created in Phase 4.
- **Phase 7 (Discipline parking lots):** Preserves lite discipline entries; creates additional discipline files (business-analysis, deployment, process-improvement, etc.) that weren't in the lite install.
