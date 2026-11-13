# Framework Compliance Audit Methodology

Full methodology for z-sdlc framework source repo compliance auditing. Covers all 10 audit dimensions, report format, severity levels, and guiding principles.

## Audit Methodology Sequence

1. **Manifest Scan**: Read `skeleton/manifest.json` — build complete inventory of declared source files
2. **Disk Scan**: Glob all tracked directories and compare against manifest entries
3. **Cross-Reference Check**: Verify skills have CLAUDE-SDLC.md commands, agents are in manifest, knowledge files are wired
4. **Stale Reference Scan**: Grep for old/removed names across the codebase
5. **Changelog Freshness**: Compare `process/sdlc_changelog.md` against recent commits modifying process files
6. **Knowledge Store Scan**: Audit YAML structure, README files, `spec_relevant` fields, conventions
7. **Discipline Health Scan**: Check parking lot entries, triage markers, active validation of `[NEEDS VALIDATION]` entries, cross-discipline flow
8. **Skill/Agent Convention Scan**: Verify frontmatter format, required sections, anti-triggers, tools lists
9. **Installer Verification**: Verify `sdlc-initialize` and `sdlc-migrate` handle all manifest files correctly
10. **Cross-Skill DRY Scan**: Detect substantive prose duplicated verbatim or near-verbatim across sibling skills
11. **Report Generation**: Produce structured inline report
12. **Interactive Triage**: Present promotion candidates from disciplines for triage decisions

## Dimension 1: Manifest Completeness

Compare every file on disk against `skeleton/manifest.json` and vice versa.

**Tracked directories:**
- `skills/` — Skill definitions (each skill is a directory with `SKILL.md` and optional `references/`)
- `agents/` — Agent definition files (`.md`)
- `knowledge/` — Knowledge store YAML files organized by discipline
- `process/` — Workflow and process documentation
- `templates/` — Document templates
- `disciplines/` — Discipline parking lot files
- `plugins/` — Plugin setup guides
- `playbooks/` — Playbook files

**What to check:**
- Every file in these directories on disk has a corresponding entry in `skeleton/manifest.json` `source_files`
- Every entry in `skeleton/manifest.json` `source_files` resolves to an actual file on disk
- No phantom entries (manifest references files that don't exist)
- No untracked files (files on disk not in manifest)

**How to validate:**
```bash
# Validate JSON syntax
python3 -c "import json; json.load(open('skeleton/manifest.json'))"
```
Then glob `skills/*/SKILL.md`, `skills/*/references/*.md`, `agents/*.md`, `knowledge/**/*.yaml`, `knowledge/**/*.d2`, `process/*.md`, `templates/*.md`, `disciplines/*.md`, `plugins/*.md`, `playbooks/*.md` and cross-reference against manifest `source_files` entries.

## Dimension 2: Cross-Reference Consistency

Verify that framework components are properly cross-referenced across key files.

**Skills → CLAUDE-SDLC.md:**
- Every user-invokable skill in `skeleton/manifest.json` → `source_files.skills` should have a corresponding command entry in `CLAUDE-SDLC.md`
- The command name in CLAUDE-SDLC.md should match the skill directory name
- Skills that are internal-only (not user-invokable) are exempt

**Agents → Manifest:**
- Every agent file in `agents/` should be listed in `skeleton/manifest.json` → `source_files.agents`

**Knowledge → Agent Context Map:**
- New knowledge files should be wired in `knowledge/agent-context-map.yaml` to relevant agent roles
- Check `knowledge/agent-context-map.yaml` for:
  - All mapped file paths resolve to actual files
  - Knowledge YAML files not referenced by any agent (potential gaps)
  - Agents referenced in mappings that don't have corresponding agent files

**Skills/Agents → sdlc-initialize:**
- New skills and agents should be referenced in `skills/sdlc-initialize/` where relevant

**Skills/Agents → sdlc-migrate:**
- New files should be handled in `skills/sdlc-migrate/` migration strategy (direct copy in section 2.1, context-map wiring in section 3.3)

## Dimension 3: Stale Reference Scan

Grep across the entire codebase for references to old, removed, or renamed concepts.

**Known stale references to check:**
- Any recently renamed or removed skill names
- Any recently renamed or removed agent names
- References to old directory structures or file paths

**Scope:** All `.md` and `.yaml` files in tracked directories. Exclude `process/sdlc_changelog.md` and `process/changelog-archive/` (changelog entries legitimately reference old names).

**Method:** Maintain a list of known renames/removals (check recent changelog entries for renames). Grep for each old name. Report any hits outside the changelog.

## Dimension 4: Changelog Freshness

Compare `process/sdlc_changelog.md` against recent git history to verify process changes are documented.

**What to check:**
- Recent commits that modify files in `skills/`, `agents/`, `process/`, `disciplines/`, `knowledge/`, `CLAUDE-SDLC.md` — do they have corresponding changelog entries?
- Changelog entries reference actual changes (not phantom entries)
- Entries are dated and describe the change meaningfully

**Method:**
```bash
git log --oneline --since="30 days ago" -- skills/ agents/ process/ disciplines/ knowledge/ CLAUDE-SDLC.md templates/ plugins/ playbooks/
```
Cross-reference commit subjects against changelog entries. Flag process-modifying commits without changelog coverage.

## Dimension 5: Knowledge Store Conventions

Audit knowledge store YAML files for structural consistency and convention adherence.

**Directory structure:** `knowledge/<discipline>/` with YAML files and optional `README.md`

**YAML conventions to check:**
- Files have proper YAML frontmatter/structure
- Required metadata fields present (varies by knowledge type)
- `spec_relevant` field present where applicable
- Consistent key naming across files in the same discipline
- No orphaned YAML files (not wired in context map — overlaps with Dimension 2)

**README completeness:**
- Each knowledge discipline directory should have a `README.md` explaining scope and contents
- README should list all YAML files in the directory with brief descriptions
- README should indicate which agents consume this knowledge

**Diagram files:** Check `.d2` files for syntax validity if present.

## Dimension 6: Discipline Health

### 6a. Discipline Parking Lots (`disciplines/`)

Check each discipline file:

| File | Discipline |
|------|-----------|
| `architecture.md` | System design, component boundaries, integration patterns |
| `business-analysis.md` | Requirements, domain modeling, stakeholder needs |
| `coding.md` | Implementation patterns, conventions, tech debt |
| `data-modeling.md` | Data architecture, schema design |
| `deployment.md` | CI/CD, infrastructure, release management |
| `design.md` | UI/UX, visual design, interaction patterns |
| `process-improvement.md` | Meta-discipline: improving the SDLC itself |
| `product-research.md` | Market, users, competitive landscape |
| `testing.md` | Test strategy, automation, knowledge layers |

**What to check:**
- Are parking lots being written to between audits? (git blame / last-modified)
- Do entries have triage markers (`[READY TO PROMOTE]`, `[NEEDS VALIDATION]`, `[DEFERRED]`)?
- Are cross-discipline insights flowing? (entry in one discipline references another)
- Is there a healthy pipeline from parking lot to knowledge store?

### 6b. Triage Status

**Triage authority matrix:**

| Transition | Authority | When |
|-----------|-----------|------|
| unmarked → `[NEEDS VALIDATION]` | Auto-apply (step 7) | Unmarked for >=2 audit cycles |
| `[NEEDS VALIDATION]` → `[VALIDATED]` | Auto-apply (step 7, confirmed by 6e) | Evidence found during active validation |
| `[NEEDS VALIDATION]` → `[REDUNDANT → file]` | Auto-apply (step 7, confirmed by 6e) | Existing knowledge rule covers same concept |
| `[NEEDS VALIDATION]` → `[DEFERRED]` | Auto-apply (step 7) | Unvalidated >=3 cycles AND discipline dormant |
| Any → `[READY TO PROMOTE]` | User decision (step 11) | Proposed with evidence during interactive triage |
| `[READY TO PROMOTE]` → Promoted | User decision (step 11) | Actual knowledge file creation during interactive triage |

**Step 7 auto-triage:** Scan entries, apply qualifying low-risk transitions, log actions in report. Then run active validation (6e) on remaining `[NEEDS VALIDATION]` entries — unless `--skip-validation` was passed, in which case skip 6e entirely. Collect promotion candidates for step 11.

### 6c. Knowledge-to-Skill Wiring

Two ownership tiers:
1. **Agent-owned (domain):** Agent definitions include Knowledge Context section directing them to `knowledge/agent-context-map.yaml`
2. **Skill-owned (cross-domain):** Skills inject knowledge from other agents' mappings when dispatching into cross-domain contexts

**Check:** Agent definitions have self-lookup sections, skills don't redundantly inject same-agent knowledge, cross-domain injection exists where needed.

### 6d. Discipline Usage Audit

Five usage signals per discipline:

| Signal | Active | Warning | Dead |
|--------|--------|---------|------|
| Parking lot activity | Entries added between audits | Only during audits | No entries since last audit |
| Knowledge consumption | Mapped agents reference knowledge files | Mapped but unused | No mapping |
| Promotion flow | Entries triaged and promoted | Added but not triaged | Static |
| Cross-discipline feed | Receives insights from other domains | Isolated | N/A |
| Growth since seeding | Knowledge files added or expanded | Unchanged since initial seed | N/A |

Report as table with interpretation (healthy / formalized-but-dead / alive-but-unformalized / dead).

### 6e. Active Validation

After auto-triage markers (6b), run an evidence-based validation pass on remaining `[NEEDS VALIDATION]` entries. This closes the gap between passive marker aging and interactive promotion — it checks whether unvalidated insights have been confirmed by actual work.

**For each `[NEEDS VALIDATION]` entry:**

1. **Extract search terms** — pull 2-3 distinctive keywords or phrases from the entry
2. **Search for evidence:**
   - `git log --all -S "keyword"` — commits that added/removed the concept
   - `git log --all --grep="keyword"` — commit messages referencing it
   - `grep -r "pattern" skills/ knowledge/ process/` — framework references
   - Session history — was the pattern encountered in documented work?
3. **Check for independent recurrence** — was a similar insight added from a different source or date? Look for related entries in other discipline files or other ingestion batches.
4. **Check knowledge store coverage** — does an existing rule in `knowledge/` already encode the same concept? If so, the entry is redundant, not unvalidated.

**Evidence strength:**

| Level | Signal | Action |
|-------|--------|--------|
| **Strong** | 2+ independent occurrences, OR implemented in framework code, OR referenced in multiple sessions | Mark `[VALIDATED]` — promotion candidate for step 11 |
| **Moderate** | Single occurrence since seeding, OR related knowledge rule exists but doesn't fully cover it | Leave `[NEEDS VALIDATION]` — note evidence for next cycle |
| **Redundant** | Existing knowledge store rule covers the same concept | Mark `[REDUNDANT → knowledge/path/file.yaml]` — prune candidate |
| **None** | No evidence after searching | Leave `[NEEDS VALIDATION]` |

**Scope control:** If a discipline has >10 `[NEEDS VALIDATION]` entries, validate the 5 oldest first. Report remaining count for next cycle. Skip this entire section if `--skip-validation` was passed — report "Active validation: skipped (--skip-validation)" in the Dimension 6 output.

**Output:** Collect `[VALIDATED]` entries as promotion candidates for step 11. Report all validation actions in the Dimension 6 section of the audit report:

```
Active Validation Results:
  Validated: N (promotion candidates)
  Redundant: N (prune candidates)
  Inconclusive: N (remain [NEEDS VALIDATION])
  Skipped (scope limit): N
```

## Dimension 7: Skill Convention Compliance

Audit every skill in `skills/` for convention adherence.

**Frontmatter format:**
- Uses YAML frontmatter with `---` delimiters
- `name:` field present and matches directory name
- `description:` uses folded scalar (`>`) for multi-line
- Description includes trigger phrases ("Triggers on...")
- Description includes anti-triggers ("Do NOT use for...")

**Required sections:**
- Title heading matching skill purpose
- Workflow or methodology section
- Red Flags table (common mistakes to avoid)
- Integration section (dispatches, complements, feeds into, uses)

**Content quality:**
- Skill references correct agent names (not stale)
- File paths in skill match source repo structure (not child project paths)
- Skill workflow steps are actionable and clear

## Dimension 8: Agent Convention Compliance

Audit every agent in `agents/` for convention adherence.

**Frontmatter format:**
- Uses YAML frontmatter with `---` delimiters
- `name:` field present
- `description:` includes when-to-use guidance with examples
- `model:` field present (e.g., `sonnet`, `opus`)
- `tools:` field lists required tools
- `color:` field present

**Content quality:**
- Agent has clear role description
- Methodology or approach section present
- Agent references correct file paths for the source repo
- Agent doesn't reference child-project-only concepts (deliverables, catalog, chronicle)

## Dimension 9: Installer Correctness

Verify the installer skills handle all framework files correctly. `sdlc-initialize` installs (`BOOTSTRAP.md` copies it into the target first); `sdlc-migrate` updates existing installs.

**What to check:**
- Every `source_files` category in `skeleton/manifest.json` has a source → target mapping in `process/path-mappings.md` (`sdlc-initialize` Phase 1 copies files by those mappings)
- Skills install to target's `.claude/skills/` (not `ops/sdlc/skills/`)
- Agents install to target's `.claude/agents/` (not `ops/sdlc/agents/`)
- Knowledge, process, templates, disciplines, plugins, playbooks install to target's `ops/sdlc/<type>/`
- Every category new files were added to has a migration strategy in `sdlc-migrate` (§2.1 direct copy, or its merge rules)
- `sdlc-initialize` Phase 1 creates every directory in the manifest's `directories` array

**Method:** Read `process/path-mappings.md`, `sdlc-initialize` Phase 1 and `sdlc-migrate` §2.1. Compare against manifest entries. Flag any manifest file that neither installer would place. `sdlc-initialize` itself is deliberately not in the manifest; don't flag it.

## Dimension 10: Cross-Skill DRY

Detect substantive prose duplicated verbatim or near-verbatim across sibling skills. This is the dimension that catches drift like the historical `sdlc-plan` / `sdlc-lite-plan` divergence (same framing sentences, ADR immutability rules, and reinforcement paragraphs that only appeared in one of the two skills despite applying universally).

**Scope:**
- `skills/*/SKILL.md`
- `skills/*/references/*.md`

**What to detect:**

1. **Verbatim paragraph duplication** — a paragraph (≥2 sentences or ≥100 chars) appears in 2+ SKILL.md files. Use shingle-style grep: pick the longest distinctive substring (8-12 words, no boilerplate punctuation) from each candidate paragraph and grep across the corpus.
2. **Near-verbatim conceptual duplication** — the same load-bearing concept appears with slightly different wording in 2+ skills (e.g., one says "ADRs are immutable", another says "Do not edit prior ADRs"). Detect by grepping for distinctive concept anchors ("immutable", "ensures that", "is to X what", "must not edit") and reporting clusters where the same anchor produces multiple-but-non-identical hits.
3. **Reinforcement-paragraph drift** — same framing/reinforcement paragraph appears in only one of two sibling skills where both apply (e.g., a tier-pair like `sdlc-plan` and `sdlc-lite-plan`, or any pair sharing the same prefix-family).
4. **Trigger phrase overlap** — frontmatter trigger phrases overlap between skills without explicit anti-trigger acknowledgement.
5. **Mirrored-block drift** — skills carry verbatim copies of process-doc sections wrapped in `<!-- MIRROR-START: {doc}.md#{id} -->` / `<!-- MIRROR-END: {doc}.md#{id} -->`; the source lives in `process/{doc}.md` between `<!-- MIRROR-SOURCE-START: {id} -->` / `<!-- MIRROR-SOURCE-END: {id} -->` (convention: `process/project-section-markers.md` § MIRROR Markers; users: `process/review-fix-loop.md` § Mirrored Critical-Steps Blocks and `process/headless-mode.md` § Mirrored Stop Rule). Any difference between a copy and its source is a finding (severity **major** — a drifted copy silently changes a skill's behavior). Run:

   ```bash
   for f in skills/*/SKILL.md; do
     grep -o 'MIRROR-START: [a-z0-9-]*\.md#[a-z0-9-]*' "$f" | sed 's/MIRROR-START: //' | sort -u | while IFS='#' read -r doc id; do
       src=$(sed -n "/MIRROR-SOURCE-START: $id -->/,/MIRROR-SOURCE-END: $id -->/p" "process/$doc" | sed '1d;$d')
       cpy=$(sed -n "/MIRROR-START: $doc#$id -->/,/MIRROR-END: $doc#$id -->/p" "$f" | sed '1d;$d')
       { [ -n "$src" ] && [ "$src" = "$cpy" ]; } || echo "DRIFT: $f <- $doc#$id"
     done
   done
   ```

   Empty output = no drift. Also confirm every skill listed in the source doc's mirror table (e.g. `review-fix-loop.md` § Mirrored Critical-Steps Blocks) carries its block — a listed skill with no `MIRROR-START` for its id is a **major** finding (the skill lost its inline steps), as is a skill with a copy that the table does not list (minor — update the table). `headless-mode.md`'s table lists every skill: `grep -L 'MIRROR-START: headless-mode.md#headless-stop-rule' skills/*/SKILL.md` must print nothing.

**Scoping rules (avoid noise):**
- Ignore matches inside fenced code blocks (` ``` `)
- Ignore canonical phrasing-contract lines (`consult [sdlc-root]/...`, `update [sdlc-root]/...`, `Read [sdlc-root]/knowledge/architecture/agent-communication-protocol.yaml`) — those ARE the shared form and are validated separately by the phrasing contract
- Ignore single-line pointers (`Read [sdlc-root]/process/...`, `Consult [sdlc-root]/...`) — those are the correct extraction pattern
- Ignore `## Red Flags` table cells (red flags often share boilerplate wording legitimately) unless the entire row is identical
- Ignore matches in process/changelog/knowledge files cited as quotation
- **Exempt `MIRROR` blocks from extraction recommendations.** Content between `MIRROR-START`/`MIRROR-END` markers is deliberate, checked duplication (check 5) — never recommend extracting it to a pointer; that is the failure the 2026-05-19 changelog entry records.
- Skip pairs where one skill is the canonical source and the other is a documented adapter or variant (look for explicit `tier:` or `variant_of:` markers in frontmatter, or comments noting the relationship)

**Recommendation format (for each finding):**

```
DUPLICATION: {short summary}
  Files: skills/skill-A/SKILL.md:42, skills/skill-B/SKILL.md:88
  Block: "{first 60 chars}..."
  Recommended target: [sdlc-root]/{process|knowledge}/{topic}.{md|yaml}
  Action: extract once; replace both call sites with one-line pointer
```

**Severity:**
- **Major** — verbatim duplication of ≥3 sentences, OR a load-bearing principle worded differently across siblings (the kind of drift that becomes load-bearing if not unified)
- **Minor** — single-paragraph overlap, near-verbatim conceptual cluster
- **Info** — trigger phrase overlap when anti-triggers exist but could be tightened

**Method (lightweight):**
1. Build a list of distinctive 8-12-word phrases from each `skills/*/SKILL.md` (skip code blocks, frontmatter, pointer lines)
2. Grep each phrase across `skills/*/SKILL.md` and `skills/*/references/*.md`
3. For phrases hitting ≥2 files, read each hit's surrounding paragraph and classify (verbatim vs near-verbatim vs scoping-rule false positive)
4. Group findings by likely extraction target

## Step 11: Interactive Triage

After presenting the audit report, run an interactive triage session for all promotion candidates identified during the audit (from Dimension 6 parking lot entries).

### Triage Workflow

**11a. Collect candidates.** During step 7, build a candidate list from two sources: (1) entries marked `[VALIDATED]` by active validation (6e) — these are primary candidates with evidence already gathered, and (2) entries with existing `[READY TO PROMOTE]` markers from previous cycles. Each candidate needs:
- The entry text (verbatim from parking lot)
- Source location (discipline file + line)
- Evidence (why it's promotion-worthy: validation evidence from 6e, recurrence, deliverable references)
- Suggested target (which knowledge store file it would go into — existing or new)

**11b. Present candidates grouped by discipline.** Use interactive prompts to present candidates in batches (one discipline at a time):

```
TRIAGE: [Discipline Name] — N candidates

1. "[entry text]"
   Source: disciplines/coding.md
   Evidence: Referenced in multiple sessions. Consistent pattern.
   Suggested target: knowledge/coding/typescript-patterns.yaml → new item under "Error Handling"

For each: (P)romote, (D)efer, (S)kip
```

**11c. Apply decisions.**

- **Promote:** Create or update the target knowledge store YAML file with the new entry. Remove the full entry from its current location in the parking lot and add a one-liner to the `### Promoted` section at the bottom of the file (create the section if it doesn't exist). Format: `- **[source tag]** short title → `target file path``. The promoted section is a breadcrumb trail — full content lives in the knowledge store.
- **Defer:** Update the parking lot entry marker to `[DEFERRED]` with reason appended.
- **Skip:** Leave the entry unchanged — it stays at its current marker for next audit cycle.

**11d. Report triage results.** Include triage outcomes in the report:

```markdown
### Triage Results
| # | Entry | Decision | Target |
|---|-------|----------|--------|
| 1 | [summary] | Promoted | knowledge/coding/typescript-patterns.yaml |
| 2 | [summary] | Deferred — not validated yet | — |
| 3 | [summary] | Skipped | — |

Promoted: N | Deferred: N | Skipped: N
```

### When to Skip Triage

- **No candidates:** If no promotion candidates found, skip step 11 entirely.
- **User declines:** If user says "skip triage" or "not now," respect that. Note "Triage deferred by user" in the report.

## Report Format

```markdown
## Framework Compliance Audit — [Date]

### Summary
- Compliance score: X/10
- Verdict: [HEALTHY / NEEDS ATTENTION / CRITICAL]
- Top issues: [brief list]

### Dimension 1: Manifest Completeness
- Files on disk not in manifest: [list or none]
- Manifest entries without files: [list or none]

### Dimension 2: Cross-Reference Consistency
- Skills without CLAUDE-SDLC.md commands: [list or none]
- Agents not in manifest: [list or none]
- Knowledge files not in context map: [list or none]
- Missing sdlc-initialize references: [list or none]
- Missing sdlc-migrate handling: [list or none]

### Dimension 3: Stale References
- [list of stale reference findings or "None found"]

### Dimension 4: Changelog Freshness
- Process commits without changelog entries: [list or none]
- Changelog coverage: X/Y recent process commits documented

### Dimension 5: Knowledge Store Conventions
- YAML structure issues: [list or none]
- Missing READMEs: [list or none]
- Missing spec_relevant fields: [list or none]

### Dimension 6: Discipline Health
#### Parking Lot Status
[per-file status, triage markers, cross-discipline flow]

#### Discipline Usage Audit
| Discipline | Parking Lot | Knowledge | Promotion | Cross-Feed | Status |
|-----------|-------------|-----------|-----------|------------|--------|

#### Knowledge-to-Skill Wiring
[wiring status, gaps]

#### Active Validation Results
- Validated: N (promotion candidates)
- Redundant: N (prune candidates)
- Inconclusive: N (remain [NEEDS VALIDATION])
- Skipped (scope limit / --skip-validation): N

### Dimension 7: Skill Convention Compliance
[per-skill findings — frontmatter, sections, content quality]

### Dimension 8: Agent Convention Compliance
[per-agent findings — frontmatter, content, paths]

### Dimension 9: Installer Correctness
- Unhandled manifest files: [list or none]
- Path mapping issues: [list or none]
- Missing directory creation: [list or none]

### Dimension 10: Cross-Skill DRY
- Verbatim paragraph duplications: [count and locations, or none]
- Near-verbatim conceptual clusters: [count and locations, or none]
- Reinforcement-paragraph drift (one of N siblings has it, others don't): [list or none]
- Trigger phrase overlaps without anti-trigger acknowledgement: [list or none]

For each finding, include the recommended extraction target (`process/`, `knowledge/`, or new shared doc).

### Triage Results
| # | Entry | Decision | Target |
|---|-------|----------|--------|
[triage outcomes — omit section if no candidates or triage skipped]

Promoted: N | Deferred: N | Skipped: N

### Recommendations
[prioritized action items]
```

## Severity Levels

- **Critical**: Manifest entries pointing to nonexistent files, an installer not placing required files, skills referencing deleted agents, CLAUDE-SDLC.md missing commands for active skills
- **Warning**: Stale references outside changelog, process commits without changelog entries, knowledge files not wired in context map, skills missing required sections, agents with incorrect paths
- **Info**: Minor naming inconsistencies, optional improvements, unmarked parking lot entries. Note: promotion candidates are handled interactively in step 11 (triage), not reported as INFO findings.

## Guiding Principles

- **Read before asserting.** Never claim a file exists or doesn't without checking.
- **Substance over ceremony.** Flag missing conventions only when the gap creates real risk.
- **Proportional recommendations.** Small gaps get small fixes.
- **Context-aware.** This is a framework source repo — audit the framework's own health, not child project concepts.
- **Toolbox, not recipe.** Empty parking lots aren't failures if the discipline hasn't been needed. Only flag staleness when the discipline IS being exercised but the knowledge layer isn't participating.
- **Source of truth mindset.** Changes here propagate to all child projects — accuracy matters more than speed.
