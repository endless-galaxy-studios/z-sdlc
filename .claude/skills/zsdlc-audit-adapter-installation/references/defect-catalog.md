# Adapter Defect Catalog

Known defect patterns that appear in adapter-produced installations. Each entry includes:
- The exact grep pattern to detect it
- What causes it
- A concrete example from production audits
- Where the fix lives (plugin / upstream / both)

## Table of contents

1. [Transformer output bugs](#1-transformer-output-bugs) — malformed strings that shouldn't exist in any correct installation
2. [Pattern Mapping coverage gaps](#2-pattern-mapping-coverage-gaps) — canonical phrases that weren't transformed
3. [Exempt-file violations](#3-exempt-file-violations) — files in the allowlist that got transformed anyway
4. [Structural content loss](#4-structural-content-loss) — upstream content dropped during merge
5. [Version-drift false positives](#5-version-drift-false-positives) — hunks that look like defects but aren't

---

## 1. Transformer output bugs

These are malformed outputs — no correct installation should contain them. Each hit is a standalone finding.

### 1.1 Double-paren splice

**Grep:** `((discipline memories\|((memory graph\|((the agent knowledge graph\|((via memory_store`

**Cause:** A bare-path rule (replacement itself contains `(...)`) fired inside an existing `(...)` context, producing `((replacement) original-tail)`.

**Example from `migrate-f01a70`:**
```
Input:  Discipline parking lot entries (`[sdlc-root]/disciplines/*.md`)
Output: Discipline parking lot entries ((discipline memories, tagged sdlc:discipline:*) *.md`)
```

**Fix location:** plugin. The plugin's Pattern Mapping rule ordering (full-parenthetical → label → table-cell → bare-path) prevents this when enforced. If double-parens appear, the matcher is picking bare-path rules when parenthetical-whole rules exist.

### 1.2 Orphan glob debris

**Grep:** `\*\.md\`)\|\) \*\.md)\|\`\*\.md\`\)`

**Cause:** Same as 1.1 — the replacement consumed the opening `(` of the pattern but not the trailing `*.md)`, leaving orphaned suffix.

**Example:** visible inside the double-paren output above (`*.md\`)` trailing).

**Fix location:** plugin. Rule ordering fix resolves both 1.1 and 1.2.

### 1.3 Read of write API

**Grep:** `Read memory_store\|Read memory_search`

**Cause:** A capture-target rule (whose replacement begins with `memory_store with tags [...]`) fired inside a `Read ...` instruction context. Capture-target rules describe WRITE destinations; they should never transform a read.

**Example from `migrate-f01a70`:**
```
Input:  Read `[sdlc-root]/knowledge/architecture/agent-communication-protocol.yaml` for the handoff schema.
Output: Read memory_store with tags ["sdlc:knowledge", "sdlc:domain:architecture"] for the handoff schema.
```

`Read memory_store` is semantically impossible — `memory_store` is the write API. Correct transformation uses `Call memory_search(query="...", tags=[...])`.

**Fix location:** plugin. The plugin's "Capture-target rules must NEVER fire in `Read ...` contexts" guard prevents this when enforced.

### 1.4 Greedy-swallow capture

**Grep:** context-dependent — look for `memory_search(query="...(e\|query="...\| [X]\|query=".*[.;,]`

**Cause:** A wildcard capture (`[X]`, `<name>`, `<purpose>`) consumed past its intended terminator, swallowing a following parenthetical, comma, or sentence boundary.

**Example from `migrate-f01a70`:**
```
Input:  read `[sdlc-root]/disciplines/*.md` and find parking lot entries tagged with that deliverable's ID (e.g., [D05 — phase 2], [D05 — planning]).
Output: memory_search(query="parking lot entries tagged with that deliverable's ID (e", tags=["sdlc:discipline:*"]) g., [D05 — phase 2], [D05 — planning]).
```

The `[X]` capture stopped at arbitrary position `(e` and leaked the rest as orphan text.

**Fix location:** plugin. Match rule #6 (non-greedy with explicit terminators: `(`, `)`, `[`, `]`, `,`, `.`, `;`, `: `, EOL) prevents this.

### 1.5 Fenced-block corruption

**Grep:** find `memory_search(` or `memory_store(` inside `^\`\`\`` blocks that aren't ```bash (MCP calls in `bash`/`jsonl` fences are legitimate transaction log examples).

**Cause:** Transformer didn't honor fenced-block exemption, mangled example YAML/JSON with transformation, breaking syntax.

**Example from `migrate-f01a70`:** `sdlc-ingest.md:271-273` had ```yaml with `[sdlc-root]/knowledge/design/component-patterns.yaml` transformed into nested-quoted `memory_search(...)` producing syntactically invalid YAML.

**Fix location:** plugin. Fenced-block hard exclusion prevents this.

### 1.6 Integration-section corruption

**Grep:** `\*\*(Uses|Depends on|Updates|Feeds into|Complements|Downstream):\*\*.*memory_(search|store)`, then read each hit.

**What counts:** in a Neuroloom-backed project, the adapter's transforms of Integration lines are authoritative (CD, 2026-10-29; see `exempt-file-list.md` § Adapter-owned). A clean `memory_search(...)` on a `**Uses:**` line is **neither**. Only corrupted output is a defect: double-paren, orphan debris, a malformed call, or a greedy swallow (§1.1–1.4) on an Integration line.

**Example of the defect:** `**Uses:** [sdlc-root]/knowledge/agent-context-map.yaml (for wiring)` turned into nonsense with a double paren.

**Fix location:** plugin (the corrupting rule).

---

## 2. Pattern Mapping coverage gaps

Canonical phrases stayed untransformed. The rule either doesn't exist in the plugin's Pattern Mapping or exists but didn't match due to context.

### 2.1 Leak grep (general)

```bash
grep -rn '\[sdlc-root\]/\(knowledge\|disciplines\)/' <target>/.claude/ 2>/dev/null \
  | grep -vE 'sdlc_changelog|changelog-archive/|knowledge-routing|sdlc-reviewer\.md|sdlc-compliance-auditor\.md|CLAUDE-SDLC\.md|provenance_log\.md'
```

Each hit needs per-line classification (see `classification-framework.md`).

### 2.2 Known untransformed idioms (Pattern Mapping gap candidates)

- ``- Knowledge store updates (`[sdlc-root]/knowledge/*.md`)`` — label-parenthetical with backticks
- ``- Files from the same discipline (e.g., `[sdlc-root]/knowledge/<discipline>/`)`` — `(e.g., ...)` variant
- Table cells with `[sdlc-root]/knowledge/...` in non-first column
- ``knowledge stores (`[sdlc-root]/knowledge/`)`` mid-sentence (e.g., `AGENT_TEMPLATE.md:134` pre-fix)
- `Cross-project knowledge updates append to [sdlc-root]/knowledge/testing/` — rule exists, didn't fire

### 2.3 Mid-sentence lowercase verb

**Example:** `For each deliverable being archived, read [sdlc-root]/disciplines/*.md and find parking lot entries...`

Rule pattern `Read [sdlc-root]/disciplines/*.md and find [X]` should match case-insensitively regardless of sentence position (plugin match rule #1). Hits here indicate the matcher anchors on sentence-start capitalization.

**Fix location:** plugin.

### 2.4 Bare concept-terminology residue (Pass 2 misfires)

**Discovered post-`migrate-6f4217` (an adapter install audit, 2026-04-26)** — a defect class the audit's path-based residue grep misses entirely.

Pass 2 of the plugin transformer (added in 0.4.0) translates file-mode concept terminology to memory-graph terminology even when no `[sdlc-root]/` path is present. The rules are documented in `pattern-mapping-rules.md` § "Knowledge-layer concept terminology" — they cover phrases like:

- `knowledge files` (bare plural) → `knowledge memory entries`
- `knowledge file` (bare singular) → `knowledge memory entry`
- `discipline files` (bare plural) → `discipline memory entries`
- `discipline file` (bare singular) → `discipline memory entry`
- `parking lot entries` → `discipline memory entries`
- `parking lot entry` (singular) → `discipline memory entry`
- `discipline parking lots` → `discipline memory entries`
- `knowledge stores` (bare plural concept) → `knowledge memory entries`
- `knowledge store` (bare singular concept) → `knowledge layer`
- `Knowledge YAML files` / `YAML knowledge files` / `Knowledge YAMLs` → `memory entries tagged sdlc:knowledge`
- `agent-context-map` (bare, used as live thing) → `the memory graph's agent index`

**The bug class:** the rules exist but Pass 2 didn't fire on the affected files. When Pass 2 doesn't run (e.g., `migrate-6f4217` emitted zero `concept_terminology_applied` events), upstream's file-mode prose overwrites the project's pre-migration Neuroloom-aware prose in any section that lacked an MCP signal marker for section-level preservation.

**Exemplar from `migrate-6f4217`:** the target's `process/deliverable_lifecycle.md:76` had pre-migration `- Testing knowledge memory entries updated`. Migration overwrote with upstream's `- Testing knowledge files updated`. The rule `knowledge files` → `knowledge memory entries` exists in the plugin's Pass 2 table but didn't fire — Pass 2 was never invoked on the file. The user found this manually after the audit failed to surface it. ~37 sibling hits across the target at the time of detection, mix of regressions and upstream-inherited references.

**Detection grep (Scan 3b in `SKILL.md`):**
```bash
grep -rnE '\bknowledge files\b|\bdiscipline files\b|\bparking lot entr|\bknowledge stores\b|\bDiscipline parking lots\b|\bKnowledge YAMLs?\b|\bYAML knowledge files\b|\bagent-context-map\b' <target>/.claude/ 2>/dev/null \
  | grep -vE 'sdlc_changelog|changelog-archive/|knowledge-routing|sdlc-reviewer\.md|sdlc-compliance-auditor\.md|CLAUDE-SDLC\.md|provenance_log\.md|agent-memory/'
```

**Per-hit classification — context guards matter:** not every match is a regression. Some legitimate retentions:
- `sdlc-ingest` discussion of YAML format ("Existing knowledge: 3 YAML files") — describes the upstream file structure that ingest consumes; legitimate
- `compliance-methodology.md` audit-dimension prose where `agent-context-map.yaml` is named as a config artifact's identity — legitimate
- `sdlc-develop-skill` Integration `**Uses:**` line listing knowledge files as a dependency — legitimate (Integration sections are exempt)
- Project `agent-memory/` content (filtered out by the grep already)

Distinguishing signal: **if the sentence describes a Neuroloom-mode operation and the term refers to the live knowledge layer, it's residue (defect)**. If the sentence describes a YAML-file-based mechanism specifically (a configuration file's structure, an upstream file format), retention is legitimate.

**Co-occurrence with telemetry gap:** if §2 of the audit (transaction log verification) found zero `concept_terminology_applied` events, expect Scan 3b to surface many hits across many files — Pass 2 didn't run at all. Conversely, if Pass 2 events exist but Scan 3b still has hits, the bug is rule-coverage (Pattern Mapping gap) or context-guard miscalibration.

**Fix location:** plugin (the rule already exists; the bug is enforcement). Telemetry hardening from `migrate-6f4217` audit (plugin 0.4.5) addresses the root cause; this scan is the outside-the-run check that catches Pass 2 misfires regardless.

**New-file-install pathway (added post-`migrate-6f4217` second follow-up):** when upstream introduces a new file the project hasn't seen before (`subtype: mcp_new_file`), the migration writes upstream content WITHOUT a project version to merge against. The plugin spec requires Pattern Mapping to run regardless, but in `migrate-6f4217` the executor treated "no merging needed" as "no transformation needed" and silently bypassed Pass 1 entirely on `incident-runbook-template.md` (introduced upstream, no project version) — the file landed with intact `[sdlc-root]/knowledge/architecture/debugging-methodology.yaml` and `error-cascade-methodology.yaml` references. Both Scan 3a (this skill) and the plugin's new Contract Residue Audit (0.4.8+) catch this — the audit hard-halts at write time, this scan catches anything that slips through. Co-occurrence signal: high Scan 3a count concentrated in template files (`*-template.md` under `[sdlc-root]/templates/`) suggests the new-file-install path bypassed Pattern Mapping, since templates are most likely to be new on any given migration.

### 2.5 Stale agent references (framework content names agents the project doesn't have)

**Discovered post-`migrate-6f4217` (an adapter install audit, 2026-04-26)** — a defect class neither Scan 3a (path-bearing residue) nor Scan 3b (concept-terminology residue) catches.

z-sdlc framework content names canonical agents in dispatch maps, message envelopes, and routing tables: `security-engineer`, `data-architect`, `ml-engineer`, `devops-engineer`, `data-pipeline-engineer`, etc. Projects often have a different roster (the target has `infosec-engineer` instead of `security-engineer`, `firebase-architect` instead of `data-architect`, no `ml-engineer` at all). The migration's existing guarded-rename machinery only fires when a `contract_changes.yaml` entry drives a rename for CLAUDE.md — it doesn't proactively walk every framework file looking for agent refs that don't resolve to the project's roster.

**Exemplar from `migrate-6f4217`:** the target's `process/team-communication-protocol.md:16` had pre-migration `from: "reviewer-infosec-engineer"` (project's actual agent). Migration overwrote with upstream's `from: "reviewer-security-engineer"` (z-sdlc canonical name, an agent that doesn't exist in the target). The user discovered it manually weeks later; the audit before this update missed it because no `[sdlc-root]/` path appears and no concept-terminology phrase fired. ~11 sibling stale refs across the target at detection time: `data-architect`, `data-pipeline-engineer`, `database-architect`, `db-engineer`, `devops-engineer`, `frontend-engineer`, `ml-architect`, `ml-engineer`, `security-auditor`, `security-engineer`, `systems-engineer`.

**Detection grep (Scan 3c in `SKILL.md`):** build the project roster from `<target>/.claude/agents/`, then scan framework content for backtick-quoted role names and message-envelope quoted values, strip the `reviewer-`/`fixer-`/`architect-` prefix, and check whether each resolves.

**Per-hit classification:**

- **Halt-class (dispatch-position):** the name appears in a dispatch instruction or message envelope `from:`/`to:` field — runtime dispatch will fail. Plugin halt-class defect; must be fixed before migration completes (or pre-0.4.7, surfaced as a project-cleanup item).
- **Warn-class (descriptive prose):** the name appears in advisory text (e.g., "consult security-engineer for auth issues", "(e.g., ml-engineer)"). Doesn't break runtime; document as a project-roster gap or declare the rename.
- **Project-rename candidate:** project has a likely rename (e.g., project has `infosec-engineer`, content has `security-engineer`). Recommend declaring `agent_renames` in `.sdlc-manifest.json` (plugin 0.4.7+ field) so future migrations apply the substitution.

**Fix location:** plugin §4.2-gate Stale Agent Reference Audit (added 0.4.7) catches this proactively at write time; this scan (Scan 3c) is the outside-the-run check that catches anything that escapes the gate or migrated before 0.4.7 lands.

---

## 3. Exempt-file violations

These files must be copied verbatim from z-sdlc source — zero transformation. A transformation-shaped hunk in any of these files is a defect.

**Exempt files (Neuroloom):**
- `process/sdlc_changelog.md` — historical record
- `process/changelog-archive/*.md` — historical record (the project's archived entries)
- `agents/sdlc-compliance-auditor.md` — auditor's validation criteria
- `CLAUDE-SDLC.md` — framework documentation
- `knowledge/provenance_log.md` — project append-only file (treated like changelog)

**Detection:** diff each exempt file against z-sdlc source. Any hunk = defect. Exception: `agents/sdlc-compliance-auditor.md` has a documented adapter customization around methodology path reference (see specific rules in `classification-framework.md`).

`process/knowledge-routing.md` and `agents/sdlc-reviewer.md` were on this list until 2026-10-29. In a Neuroloom-backed project they are now adapter-owned (`exempt-file-list.md` § Adapter-owned). The `migrate-f01a70` finding that the reviewer's checklist was transformed into Neuroloom forms would be **neither** today.

**Fix location:** plugin. Hard-gate enforcement (post-0.3.6) prevents this by routing exempt files through a verbatim-copy path with zero rule evaluation.

---

## 4. Structural content loss

These don't show in MCP counts or leak greps. They show as heading / table row / numbered step count drops between z-sdlc source and target.

**Detection:**
```bash
# For each file diffed:
comm -23 <(grep -cE '^#{1,6} ' source.md) <(grep -cE '^#{1,6} ' target.md)
# ...similar for tables and numbered steps
```

If target count < source count without a matching project customization, it's a content-merge bug.

**Examples from `migrate-f01a70`:**
- `sdlc-develop-skill.md:224-234` — 12-row Red Flags table replaced with duplicate of an earlier prose section
- `sdlc-plan.md:240-254` — 5-step "Library verification (MANDATORY)" procedure deleted; 4-step "Spec-time knowledge filtering" replaced with 3-step stub
- `sdlc-review.md:49-59` — "Dispatch Reviewer" step body replaced with duplicate of a later section

**Fix location:** plugin. The Structural Content-Loss Audit (plugin §4.2-gate, post-0.3.6) catches this when enforced.

---

## 5. Version-drift false positives

Not defects — but they look like defects at first glance. Rule them out before classifying anything else.

### 5.1 Target z-sdlc version < current z-sdlc version

If `.sdlc-manifest.json` shows `source_version` earlier than the current z-sdlc repo, differences against current source may just be legitimate upstream changes the target hasn't migrated to yet. A v1.1.1 target diffed against current v1.2.3 source will show all v1.2.1-v1.2.3 upstream edits as "deviations."

**What to do:** always surface target version vs current version in the report headline. Interpret diffs in that context. If the user wants a same-version audit, have them re-migrate to current first.

### 5.2 Target customizations inside PROJECT-SECTION markers

Content between `<!-- PROJECT-SECTION-START: label -->` and `<!-- PROJECT-SECTION-END: label -->` is explicitly preserved across migrations and is project-specific by design. Diffs inside these blocks are never defects.

### 5.3 Preserved MCP sections (project-authored MCP)

Sections with `memory_search(query="<domain-specific>", tags=[...])` calls that weren't plugin-generated (i.e., the project added them during `/sdlc-port` or manually) are preserved verbatim by the plugin's §4.2.0 gate. Diffs in these sections are project customizations, not defects.

**Detection heuristic:** a preserved MCP section has query strings referencing project-specific domain terms (e.g., `"debugging methodology investigation root cause"` in a project's debug-specialist agent), not the generic terms the plugin's Pattern Mapping emits.

### 5.4 Target-specific path corrections

In the 2026-04-22 audit, the target's `agents/sdlc-compliance-auditor.md:13` had a MORE CORRECT methodology path than upstream (the target had `.claude/skills/sdlc-audit/references/compliance-methodology.md`; upstream had the broken `[sdlc-root]/knowledge/compliance-methodology.md`). When the target fixes an upstream bug, that's an upstream finding, not a plugin one.
