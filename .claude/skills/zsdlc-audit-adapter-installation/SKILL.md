---
name: zsdlc-audit-adapter-installation
description: >
  Audit a z-sdlc adapter-produced installation (currently Neuroloom) against z-sdlc source
  to detect and categorize deviations. Verifies (a) the installation functions — MCP integration
  healthy, transaction log complete, no botched transformations — and (b) content doesn't deviate
  from z-sdlc except where the adapter's phrasing contract explicitly permits. Produces a
  classified report: which defects need fixing in z-sdlc upstream, which need fixing in the
  plugin, which need both, which are correct as-is.
  Triggers on "audit the adapter installation", "audit the neuroloom install",
  "check the plugin transformations", "verify the migration output", "audit a neuroloom migration",
  "check adapter compliance", "did the migration deviate", "post-migration audit",
  "did the plugin handle this correctly". Use AFTER a user reports a migration completed or
  reports unexpected post-migration state in a target project — the skill runs from z-sdlc
  source against the target.
  Do NOT use to audit z-sdlc source itself — use the `audit` skill for that.
  Do NOT use as a replacement for the plugin's own internal §4.2-gate / post-operation-audit — this
  is the OUTSIDE check that runs after, with diff access to z-sdlc source, and catches what those
  inside-the-run gates miss.
---

# Audit Adapter Installation

This skill runs from the z-sdlc source repo and audits an adapter-produced installation (e.g., a Neuroloom-adapted project) for deviations from what z-sdlc intended. It complements — does not replace — the adapter plugin's own internal gates.

## Why this exists

An adapter plugin (like `neuroloom-sdlc-plugin`) ships its own `/sdlc-initialize` and `/sdlc-migrate` skills that transform z-sdlc content into adapter-native form (for Neuroloom: MCP calls via `memory_search` / `memory_store`). The plugin runs its own internal gates (§4.2.0 preservation, §4.2-gate MCP retention audit, post-operation audit). Those gates run inside the plugin's own skill, without the ability to diff against z-sdlc source.

This skill is the **outside** check. It runs from z-sdlc with full diff access to source and asks three questions:

1. **Does the installation function?** MCP calls present where they should be, transaction log complete, no malformed output, no exempt-file corruption.
2. **Does it deviate from z-sdlc only where the phrasing contract permits?** Every differing hunk against source must be either (a) a legitimate transformation per the plugin's Pattern Mapping, (b) a legitimate project customization inside PROJECT-SECTION markers or preserved MCP sections, or (c) a defect.
3. **Where does each defect get fixed?** Categorize as upstream (z-sdlc source bug), plugin (transformer / Pattern Mapping defect), both, or neither.

The output is a structured report designed to feed directly into fix planning — one pass of this skill produces the list of commits needed across z-sdlc and the plugin.

## Invocation

```
/zsdlc-audit-adapter-installation <target-path> [adapter-name]
```

- `<target-path>` — absolute or `~`-relative path to the target project (e.g., `~/Projects/my-app`)
- `[adapter-name]` — optional; defaults to `neuroloom`. Currently the only supported adapter; future adapters register their own exempt lists and Pattern Mapping sources here.

If the user invokes the skill without specifying a target, ask which project to audit. Don't guess.

## The audit flow

### Step 1: Establish adapter + version context

Read `<target-path>/.sdlc-manifest.json`:
- `source_version` — the z-sdlc version the target is at. If this doesn't match current z-sdlc's version, the audit may surface "deviations" that are just version drift. Surface this up front so findings are interpreted in context.
- `neuroloom_backend` — confirms the adapter identity. If not present, this is a bare z-sdlc install and this skill is the wrong tool; redirect to the `audit` skill.
- `last_migration` or `install_date` — timestamp of the last adapter operation

Check the plugin repo for its version:
- Look for `~/Projects/neuroloom/neuroloom-sdlc-plugin/.claude-plugin/plugin.json` (default local path)
- If the user specified a different plugin path, use that
- Record `plugin_version`

These context facts frame the report — a v1.1.1 installation audited against current v1.2.3 z-sdlc will produce different findings than a v1.2.3-against-v1.2.3 audit. Don't treat version drift as defects.

### Step 2: Functional health check

**2a. MCP integration health.** Count `memory_search(` + `memory_store(` occurrences across `<target-path>/.claude/sdlc/` and `<target-path>/.claude/agents/` and `<target-path>/.claude/skills/`. This gives a floor number — healthy Neuroloom installations have dozens of MCP calls (recent the target runs: 60–120). Zero or very-low counts indicate the adapter didn't transform, or transformation was reverted.

**2b. Known-defect output scan.** Grep for each pattern in `references/defect-catalog.md` — these are exact strings that a correct installation should never contain. Each hit is itself a finding, not just a signal. See `references/defect-catalog.md` for the full list; at minimum scan for:
- Double-paren splices (`((discipline memories`, `((memory graph`, `((the agent knowledge graph`)
- Orphan glob debris (`*.md\`)`, `) *.md)`, `` *.md`)`` )
- Malformed read-of-write-API (`Read memory_store`, `Read memory_search`)

**2c. Transaction log verification.** Read `<target-path>/.sdlc-transaction-log`. For the most recent run_id, assert:
- `file_merged` events exist for each file the change manifest said was modified
- Exactly one `mcp_retention_audit_complete` event with `audit_result: "PASS"`
- Exactly one `structural_audit_complete` event (plugin 0.3.6+) with zero regressions
- No `TRANSFORMATION_WARNING` events without a corresponding resolution
- `run_complete` present

Missing any mandatory event is a finding — the plugin's own gates didn't run. See `references/transaction-log-schema.md` for the full event catalog and expected fields.

### Step 3: Contract-residue scan

Canonical phrases that should have been transformed sometimes stay untouched — a Pattern Mapping gap, a match-rule failure, or a preservation boundary that kept untransformed content. Run **two** scans: a path-bearing residue scan AND a bare concept-terminology residue scan. Both classes have caused production regressions; missing either skips a defect class.

**Scan 3a — path-bearing residue (Pass 1 phrasing-contract miss):**

```bash
grep -rn '\[sdlc-root\]/\(knowledge\|disciplines\)/' <target-path>/.claude/ 2>/dev/null \
  | grep -vE 'sdlc_changelog|changelog-archive/|knowledge-routing|sdlc-reviewer\.md|sdlc-compliance-auditor\.md|CLAUDE-SDLC\.md|provenance_log\.md'
```

**Scan 3b — bare concept-terminology residue (Pass 2 phrasing-contract miss):**

Pass 2 in plugin 0.4.0+ translates file-mode vocabulary to memory-graph vocabulary even when no `[sdlc-root]/` path is present. Phrases like `knowledge files`, `discipline files`, `parking lot entries`, `knowledge stores` (plural), `YAML files` (in knowledge context) all describe the knowledge layer using its file-based shape — they must be transformed in Neuroloom installations even though Scan 3a misses them entirely.

```bash
grep -rinE '\bknowledge files?\b|\bdiscipline files?\b|\bparking[- ]lot entr|\bknowledge stores?\b|\bknowledge-store entr|\bdiscipline parking lots?\b|\bknowledge YAMLs?\b|\bYAML knowledge files?\b|\bagent-context-map\b|\bknowledge area\b|\bsuggested knowledge area\b' <target-path>/.claude/ 2>/dev/null \
  | grep -vE 'sdlc_changelog|changelog-archive/|knowledge-routing|sdlc-reviewer\.md|sdlc-compliance-auditor\.md|CLAUDE-SDLC\.md|provenance_log\.md|path-mappings\.md|agent-memory/'
```

The `agent-memory/` filter excludes project-authored agent-MEMORY.md content (project-specific, not framework-derived).

**Hard-coverage check (added post-`migrate-6f4217` audit, 2026-04-26):** the target's `deliverable_lifecycle.md:76` had upstream `- Testing knowledge files updated` overwrite the project's pre-migration `- Testing knowledge memory entries updated`. Pass 2 should have re-translated `knowledge files` → `knowledge memory entries` (rule exists in plugin pattern-mapping-rules.md ~line 136) but didn't fire. The audit before this update missed it because Scan 3a's grep didn't match — no `[sdlc-root]/` on the line. Scan 3b is the fix.

**For each hit (3a OR 3b), read context and classify per `references/classification-framework.md`:**
- **Correctly exempt** — Integration section, fenced code block, audit-description prose that the contract allows, project-specific agent memory, or content where "knowledge files" / "YAML files" legitimately refers to the file mechanism (e.g., the discussion of YAML format in `sdlc-ingest`'s "Existing knowledge" line). Distinguishing signal: if the sentence describes Neuroloom-mode operation, the term is residue (defect); if it describes a YAML-file-based mechanism specifically (like agent-context-map's structure), it can be legitimately retained
- **Pattern gap** — No rule in plugin Pattern Mapping / Pass 2 covers this phrasing (plugin add needed)
- **Match failure** — Rule exists but didn't fire (plugin matcher bug; usually paired with telemetry gap if Pass 2 didn't emit `concept_terminology_applied`)
- **Preservation boundary** — Section was preserved verbatim and contained the leak (plugin needs to re-transform inside preserved sections, or the user needs to normalize)

**Scan 3c — stale agent reference scan (added post-`migrate-6f4217` audit, 2026-04-26):**

Framework content references agents by name in dispatch maps, message envelopes, and routing tables. When the project's `.claude/agents/` doesn't include those names, those references break runtime dispatch silently. The plugin's §4.2-gate Stale Agent Reference Audit (added 0.4.7) catches this proactively at write time; this scan is the outside-the-run check that catches anything that escaped the gate or migrated before 0.4.7 lands.

```bash
# Build the project agent roster
ROSTER=$(ls <target-path>/.claude/agents/ | sed 's/\.md$//' | sort -u)

# Extract candidate agent references from framework content
grep -rohE '`[a-z][a-z0-9-]+(engineer|developer|architect|designer|auditor|specialist|advisor|strategist|researcher|reviewer|officer)`|"reviewer-[a-z-]+"|"fixer-[a-z-]+"|"architect-[a-z-]+"' \
  <target-path>/.claude/sdlc/ <target-path>/.claude/skills/ 2>/dev/null \
  | sed 's/[`"]//g' | sed 's/^reviewer-//' | sed 's/^fixer-//' | sed 's/^architect-//' \
  | sort -u \
  | while read agent; do
      if ! echo "$ROSTER" | grep -qx "$agent"; then
        echo "STALE: $agent"
      fi
    done
```

**For each STALE hit, classify:**

- **Halt-class (dispatch-position):** name appears in a dispatch instruction (`Dispatch <name>`, `Spawn <name> as a teammate`, `from: "reviewer-<name>"` in a message envelope, a YAML key in a fenced `agent-selection.yaml`-shaped block, a routing-table column header). Runtime dispatch will fail. Plugin defect — the §4.2-gate should have halted; if the migration ran on 0.4.7+, this is a gate-bypass. If pre-0.4.7, expected — surface as a project cleanup item.

- **Warn-class (descriptive prose):** name appears in advisory text — "consult security-engineer for auth issues", "(e.g., ml-engineer)", an example list under a heading like "Common dispatch domains". Doesn't break runtime but documents an unadopted role. Plugin should have emitted `agent_unresolved_warning` for §5.4 surfacing.

- **Project-rename candidate:** project's roster includes a likely rename (e.g., project has `infosec-engineer`, content references `security-engineer`). Recommend declaring `agent_renames: {"security-engineer": "infosec-engineer"}` in `.sdlc-manifest.json` so future migrations apply the substitution consistently.

**The bug this catches:** the target, post-`migrate-6f4217`, had ~11 stale agent references across `team-communication-protocol.md`, `sdlc-debug-incident.md`, `sdlc-plan.md`, `sdlc-execute.md`, `sdlc-tests-run.md`, etc. — names like `security-engineer`, `data-architect`, `ml-engineer`, `db-engineer`, `devops-engineer`, `frontend-engineer`, `data-pipeline-engineer`, `database-architect`, `ml-architect`, `security-auditor`, `systems-engineer`. The user discovered them by manually diffing `team-communication-protocol.md` weeks after migration completed. Both Scan 3a and Scan 3b miss this class — agent names don't contain `[sdlc-root]/` paths and aren't in the concept-terminology table. Scan 3c is the third leg.

### Step 4: File-by-file diff audit

For every file in `<target-path>/.claude/` that corresponds to a z-sdlc source file (per `skeleton/manifest.json`), diff it against its upstream source. Adapter-owned files and lines (`references/exempt-file-list.md` § Adapter-owned) are expected to differ. Classify their hunks only for corrupted output or residue, never for the transformation itself:

```bash
diff -u ~/Projects/z-sdlc/<source-path> <target-path>/<install-path>
```

Install-path mapping:
- `z-sdlc/skills/X/SKILL.md` → `target/.claude/skills/X/SKILL.md`
- `z-sdlc/agents/X.md` → `target/.claude/agents/X.md`
- `z-sdlc/process/X.md` → `target/.claude/sdlc/process/X.md`
- `z-sdlc/templates/X.md` → `target/.claude/sdlc/templates/X.md`
- `z-sdlc/disciplines/X.md` → `target/.claude/sdlc/disciplines/X.md` (Neuroloom: not applicable — disciplines live in memory graph)

For each differing hunk, classify using `references/classification-framework.md`. Record one row per file in the output table. A file can have multiple findings of different verdicts — list each separately.

**Scope limits:** skip files in the "Project-Specific Files (Never Overwrite)" list the plugin documents (`process/agent-selection.yaml`, `knowledge/agent-context-map.yaml`, `knowledge/provenance_log.md`) — those are expected to diverge. Also skip `.gitignore`, `CLAUDE.md`, and `.sdlc-manifest.json` in the target — those are project-install artifacts, not z-sdlc copies. Note their presence but don't diff them.

### Step 5: Structural content-loss check

MCP counts can be preserved while structural content is lost. For each file diffed in Step 4, also count:
- Heading lines (`^#{1,6} `)
- Table body rows (`^\|.*\|.*\|\s*$` excluding header/separator rows)
- Numbered steps with bold lead (`^\s*\d+\.\s+\*\*`)
- Fenced code blocks (`^\s*\`\`\``)

If the target's post-merge count is less than z-sdlc source's count by more than 1 (tolerating small project-specific edits), and the delta doesn't match a `deviation` marker or a documented customization, flag as a **content-loss** defect — the plugin's content-merge dropped upstream content. These are the worst findings because they're invisible to MCP-only audits.

### Step 6: Report

Produce the report artifact at `<target-path>/docs/current_work/audits/adapter_audit_YYYY-MM-DD.md` (create the directory if it doesn't exist) using the template below. Also print a condensed version to the conversation so the user can see headline findings immediately.

## Report structure

ALWAYS use this exact template:

```markdown
# Adapter Installation Audit — <target-name>

**Date:** YYYY-MM-DD
**Target:** <target-path>
**Target z-sdlc version:** <source_version from manifest>
**Current z-sdlc version:** <version from source repo>
**Adapter:** <adapter-name> v<plugin_version>
**Last migration run_id:** <from transaction log>

## Headline metrics

| Metric | Value | Status |
|---|---|---|
| MCP call lines | N | healthy ≥ 40 / concerning < 20 / broken < 5 |
| Contract-residue leaks (Scan 3a — path-bearing) | N | target 0 |
| Concept-terminology residue (Scan 3b — bare forms) | N | target 0 |
| Stale agent references (Scan 3c — non-resolving names) | N | target 0 |
| Double-paren corruptions | N | target 0 |
| Orphan debris sites | N | target 0 |
| Malformed `Read memory_store` / `Update memory_search` | N | target 0 |
| Files with content-loss | N | target 0 |
| Transaction log gaps | N | target 0 |

## Transaction log summary

<events-present vs events-expected, plus any TRANSFORMATION_WARNINGs>

## Classification (per file)

| File | Verdict | Specific issue |
|---|---|---|
| ... | **upstream** / **plugin** / **both** / **neither** | one-line finding with line number |

## Findings detail

### upstream (z-sdlc source bugs)
<list each with file:line evidence>

### plugin (adapter defects)
<grouped by defect class — transformer bug / Pattern Mapping gap / exempt violation / content-loss / regex bug / etc.>

### both
<findings that need changes in both repos>

### neither (correct as-is or no-op)
<summary counts; don't list every file unless useful>

## Recommended fix plan

### z-sdlc upstream
<numbered list of specific edits with file paths>

### neuroloom-sdlc-plugin
<numbered list of specific rule additions or transformer guard additions>

### target project cleanup (if any)
<only list if the user asked for immediate cleanup; otherwise note that re-running migration against fixed plugin is the canonical fix path>
```

## Interactive follow-up

After presenting the report, ask the user: "Which fixes should I apply now?" with three options:
- Apply upstream fixes (z-sdlc)
- Apply plugin fixes (neuroloom-sdlc-plugin)
- Both — apply in parallel

Skip this question if the user has already signalled they just want the report (e.g., they said "just audit" or "don't fix anything").

For the target project itself: **never** offer to cleanup target files manually unless the user explicitly asks. The canonical fix path is to re-run the migration against a fixed plugin — manual cleanup diverges from the adapter's transformation contract and creates cleanup debt. Surface this in the recommended fix plan.

## Red Flags

| Thought | Reality |
|---|---|
| "MCP count is high, installation is healthy" | MCP counts can be preserved while 12-row tables and 5-step procedures vanish. The structural content-loss check at Step 5 catches what MCP-only audits miss. |
| "Leaks are low, the migration worked" | Leak count measures Pattern Mapping coverage. It doesn't measure transformer correctness (double-paren), exempt-file violation, or content loss. Run all six steps. |
| "The exempt list already protects these files" | Informational exempt lists are aspirational. If the plugin's own post-op-audit doesn't hard-gate the allowlist, transformer ran over exempt files anyway. Verify per-file via the transaction log's `subtype: exempt_verbatim` markers. |
| "Just grep for `[sdlc-root]/`" | That catches residue but misses botched transformation output (`Read memory_store`, double-paren, orphan debris). Those forms don't contain `[sdlc-root]` — they've already been mangled past it. |
| "The plugin's internal audit passed, so we're fine" | The plugin audits from inside its own run with no access to z-sdlc source. This skill audits from outside with full diff. Both are necessary; neither replaces the other. |
| "Upstream is always correct" | z-sdlc source itself can have broken references (see 2026-04-22 `sdlc-compliance-auditor.md:13` path bug). When the target's version is MORE correct than upstream because the adapter corrected a broken path, that's an upstream finding, not a plugin one. |
| "Version drift isn't a defect" | It isn't — but surface it in the headline so the user doesn't interpret version-drift hunks as plugin bugs. A v1.1.1→v1.2.3 audit against v1.2.3 source has different expectations than v1.2.3→v1.2.3. |

## Integration

- **Complements:** the plugin's internal §4.2-gate / post-operation-audit — this skill runs from z-sdlc source with outside-the-run diff capability. Both are required; neither replaces the other.
- **Uses:** `references/defect-catalog.md` (known-defect patterns), `references/classification-framework.md` (verdict criteria), `references/exempt-file-list.md` (which files should be untransformed), `references/transaction-log-schema.md` (expected events)
- **Feeds into:** `z-sdlc/process/sdlc_changelog.md` (for upstream fixes), `neuroloom-sdlc-plugin/skills/sdlc-migrate/SKILL.md` (for Pattern Mapping and transformer guard additions)
- **Does NOT replace:** the `audit` skill (which audits z-sdlc source itself, not adapter installations). If the user asks to audit z-sdlc source, redirect to `audit`.
- **Downstream:** once fixes land upstream + in the plugin, the canonical verification is to re-run `/sdlc-migrate` in the target against the fixed plugin and re-run this skill to confirm the findings cleared.
