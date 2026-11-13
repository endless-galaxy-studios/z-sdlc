---
name: zsdlc-ingest
description: >
  Bulk-import external knowledge into the z-sdlc framework — skills, agent suggestions,
  playbooks, process docs, disciplines, knowledge stores, and templates. Analyzes curated
  content collections (transcripts, articles, documentation, design guides, architecture
  papers, postmortems, workflow recordings, tool documentation) and routes extracted
  insights to the appropriate framework artifact: new/updated skills, agent suggestion
  entries, playbook checklists, process doc amendments, knowledge YAML rules, discipline
  parking lot entries, or template improvements. Changes here propagate to all child
  projects on next migration. Triggers on "ingest these", "analyze these transcripts",
  "import knowledge from", "extract patterns from", "bulk import", "learn from these",
  "what can we adopt from", "process these for the framework", "add to framework from",
  "enrich the framework", "add to z-sdlc from", "distill these into the framework",
  "what should we add from these", "absorb these into z-sdlc".
  Do NOT use for single-file reads or ad-hoc research — use direct reads or WebSearch.
  Do NOT use for exploring ideas.
  Do NOT use for creating specs or plans.
  Do NOT use for enriching a single existing agent.
---

# Framework Ingestion

Structured bulk import of external content into the z-sdlc framework. The goal is to extract actionable insights from curated source material and route them to the correct framework artifact — not just knowledge stores, but skills, agent suggestions, playbooks, process docs, and templates too.

**This skill produces framework artifacts that ship to all child projects on migration. It does NOT produce specs, plans, or implementations.**

**Argument:** `$ARGUMENTS` (path to content directory or file list, plus optional target hint)

## When This Applies

Use this when you have a collection of curated external content to absorb into the framework. The hallmark is bulk external material that could improve how z-sdlc serves child projects.

Signs this skill is appropriate:
- A directory of transcripts, articles, or documentation files
- "What can we adopt from these into our framework?"
- "Analyze these for patterns we should codify"
- Curated content from a known expert, conference, or authoritative source
- The content generalizes across projects (not specific to one codebase)
- Content about workflows, agent patterns, review processes, or development methodology

Signs this skill is NOT appropriate:
- Single file or single insight → add directly to the relevant artifact
- Project-specific patterns that wouldn't generalize → child project's local knowledge
- The user wants to explore an idea → not this skill
- The user wants to enrich one specific agent → not this skill
- Competitive analysis → product research tools

## Artifact Routing Map

Ingested content can land in any of these framework artifacts:

| Artifact Type | Location | What Goes Here | Example |
|---|---|---|---|
| **Knowledge rules** | `knowledge/<discipline>/*.yaml` | Testable, falsifiable rules with rationale | "All animations must use non-linear easing" |
| **Discipline parking lot** | `disciplines/<name>.md` | Promising insights needing validation | "[NEEDS VALIDATION] Consider spring physics for dismissal gestures" |
| **Agent suggestions** | `agents/AGENT_SUGGESTIONS.md` | New agent role definitions or enrichments to existing ones | A new "devops-engineer" agent role with expertise description |
| **Skill candidates** | Noted in report (not auto-created) | Workflow patterns that could become reusable skills | A multi-step review process that could be a `/review-*` skill |
| **Playbook entries** | `playbooks/<name>.md` | Checklists for specific task types | New checklist items for security review playbook |
| **Process doc amendments** | `process/<name>.md` | Workflow or lifecycle improvements | Better handoff protocol between plan and execute phases |
| **Template improvements** | `templates/<name>.md` | Structural additions to document templates | New section in spec template for accessibility considerations |

## Core Principles

**Route to the right artifact.** The most important decision is where each insight lands. A workflow pattern is not a knowledge rule. An agent expertise description is not a playbook. Match the insight to the artifact type that makes it most actionable.

**Extract rules, not summaries.** For knowledge store entries, the output is testable, falsifiable rules with specific values — not prose summaries. "Use non-linear easing" is a summary. "All animations must use non-linear easing (ease-in-out or spring); linear easing is forbidden except for progress bars" is a rule.

**Think cross-project.** Everything entering the framework will be consumed by every child project. Filter for patterns that generalize. Project-specific tips belong in that project's local knowledge, not here.

**Respect existing conventions.** Each artifact type has established conventions. Read existing examples before writing new entries. Agent suggestions follow the format in `AGENT_SUGGESTIONS.md`. Knowledge YAML follows the patterns in existing stores. Skills follow the structure in `.claude/skills/zsdlc-create-skill/SKILL.md`.

**Source attribution is mandatory.** Every extracted insight must trace back to its source file.

**Filter aggressively.** Not everything in external content belongs in the framework. The test: would this make z-sdlc measurably more useful to child projects?

**Deduplicate against existing artifacts.** Before creating new entries, read existing artifacts in the target area. If an insight already exists, skip it or merge source attribution.

## Workflow

```
SURVEY → SCOPE → EXTRACT → CLASSIFY → STRUCTURE → PLACE → REPORT → CHANGELOG → MANIFEST
```

The flow is sequential. Each step must complete before the next begins. The user confirms scope (step 2) before extraction begins.

## Steps

### 1. Survey the Content

Read the content source to understand what's there:

1. **Inventory** — list all files, formats, sizes. Count the total.
2. **Sample** — read 2-3 representative files to assess content quality and domain focus.
3. **Characterize** — describe the content in one sentence: who created it, what domain it covers, what type of knowledge it contains.

Present the survey to the user:

```
SURVEY
Files: [count] [format] files in [path]
Domain: [what the content covers]
Character: [principles / tutorials / case studies / reference / workflow docs / mixed]
Sample: [1-sentence summary of 2-3 sampled files]
Quality signal: [high — expert with rationale / medium — practical tips / low — opinions without backing]
```

### 2. Scope the Ingestion

Before extracting anything, align with the user on:

1. **Likely artifact targets** — based on the survey, which artifact types will likely receive content. A set of transcripts about testing methodology might target knowledge rules + playbook entries + possibly an agent suggestion. Workflow documentation might target process docs + skill candidates.

2. **Existing artifact audit** — read the current state of likely targets:
   - Knowledge stores (`knowledge/<discipline>/`) — existing YAML files and rule IDs
   - Discipline files (`disciplines/<name>.md`) — existing parking lot entries
   - Agent suggestions (`agents/AGENT_SUGGESTIONS.md`) — existing agent roles
   - Playbooks (`playbooks/`) — existing playbooks and their checklists
   - Process docs (`process/`) — relevant existing process documentation
   - Skills (`skills/`) — existing skills that might overlap with extracted workflows
   - Templates (`templates/`) — existing template structures

3. **Extraction depth** — based on file count and user preference:
   - **Shallow** (>20 files): read all files but extract only high-confidence, broadly-applicable insights
   - **Deep** (<20 files): thorough extraction with nuance, including edge cases and conditional insights

4. **Cross-project generalizability** — assess whether the content is universal enough for the framework

Present the scope for confirmation:

```
SCOPE
Likely targets: [artifact types]
Existing state:
  Knowledge: [count] YAML files in [disciplines], [count] total rules
  Agent suggestions: [count] agent roles
  Playbooks: [count] playbooks
  Skills: [count] skills (potential overlap with: [list])
Extraction depth: shallow | deep
Generalizability: [universal / conditional — note limitations]
```

Wait for user confirmation before proceeding.

### 3. Extract

Read all source files and extract insights, casting a wide net across artifact types.

**For each source file, capture:**
- Actionable rules with specific, testable criteria → knowledge candidates
- Workflow patterns with repeatable steps → skill or process doc candidates
- Agent role descriptions or expertise areas → agent suggestion candidates
- Task-specific checklists → playbook candidates
- Anti-patterns with "why it's wrong" rationale → knowledge or playbook candidates
- Structural patterns for documents → template candidates
- Insights that need validation before codifying → parking lot candidates

**Filtering criteria — include if:**
- An agent acting on it would produce measurably better work across projects
- It generalizes beyond the specific example in the source
- It includes rationale (not just "do this" but "do this because...")
- It fills a gap in the current framework artifacts

**Filtering criteria — exclude if:**
- It's tool-specific workflow advice (IDE shortcuts, specific SaaS UI steps)
- It's an opinion without rationale or evidence
- It's obvious to any competent practitioner
- It duplicates an existing artifact
- It's too project-specific to generalize

**For large collections (shallow mode):** Process files in batches. After each batch, check for theme saturation.

### 4. Classify

Route each extracted insight to its target artifact type. This is the step that distinguishes this skill from the child-project version — here we're thinking about the full framework.

**Classification rules:**

| If the insight is... | Route to... |
|---|---|
| A testable rule with specific criteria and rationale | Knowledge YAML |
| A promising pattern that needs validation | Discipline parking lot |
| A description of a specialized agent role not in AGENT_SUGGESTIONS.md | Agent suggestion |
| An enrichment to an existing agent's expertise description | Agent suggestion (merge) |
| A multi-step workflow that could be automated/guided | Skill candidate (noted in report) |
| A checklist for a specific task type | Playbook entry |
| A workflow or lifecycle improvement | Process doc amendment |
| A structural addition to document formats | Template improvement |
| Cross-discipline but useful | Adjacent artifact's parking lot |

**Do NOT auto-create skills.** Skill candidates are noted in the report with a proposed structure. The user decides whether to invoke `/zsdlc-create-skill` for them. Skills are complex artifacts that need intentional design.

**Do NOT auto-create new agent files.** Agent suggestions go into `AGENT_SUGGESTIONS.md`. Creating actual agent `.md` files is a separate, deliberate step.

### 5. Structure

Organize extracted insights into the format required by each target artifact.

**Knowledge rules** — follow existing YAML conventions in the target knowledge store:
- Group by theme/category into files
- Continue existing rule ID sequences
- Include: ID, name, rule statement, rationale, checklist item, source
- Set `spec_relevant: false` for new files (safe default)

**Agent suggestions** — follow the format in `AGENT_SUGGESTIONS.md`:
- Role name as H3 heading
- "When to use" line
- Expertise description in code block
- Suggested tools list
- Place in the correct category section (Engineering, Quality, Architecture & Design, etc.)

**Playbook entries** — follow existing playbook format:
- Checklist items with clear pass/fail criteria
- Grouped by phase or category within the playbook

**Process doc amendments** — draft the specific text changes:
- Reference the exact section being amended
- Show before/after or new section content

**Template improvements** — draft the structural addition:
- Reference the exact template and section
- Show the new structure with placeholder guidance

**Parking lot entries** — standard format:
```
### [Category Name] ([date], source: [source description])

*Bulk import from [source characterization].*

- **[Insight title].** [NEEDS VALIDATION] [Description]. (Source: `[source-file-id]`)
```

**Skill candidates** — structured proposal (not implementation):
```
SKILL CANDIDATE: [name]
Trigger: [when a user would invoke this]
Steps: [high-level workflow]
Inputs: [what it needs]
Outputs: [what it produces]
Similar to: [existing skills it's related to]
Justification: [why this warrants a dedicated skill vs. ad-hoc work]
```

### 6. Place

Write each output to its correct destination:

| Output Type | Destination | Action |
|---|---|---|
| Knowledge rules | `knowledge/<discipline>/<file>.yaml` | Create or append |
| Parking lot entries | `disciplines/<name>.md` | Append to parking lot section |
| Agent suggestions | `agents/AGENT_SUGGESTIONS.md` | Add new roles or merge into existing |
| Playbook entries | `playbooks/<name>.md` | Create or append checklist items |
| Process doc amendments | `process/<name>.md` | Edit existing docs |
| Template improvements | `templates/<name>.md` | Edit existing templates |
| Skill candidates | Report only | Do not write — present for user decision |

**Knowledge file placement:**
- Write new YAML files or append to existing ones
- Update the knowledge store's `README.md` to list new files
- If new files are created, add them to the README's structure listing

**Agent suggestion placement:**
- New roles: add under the appropriate category heading in `AGENT_SUGGESTIONS.md`
- Enrichments: merge new expertise into existing role descriptions (don't duplicate)
- Add to the "Choosing Your Agent Team" table if the role serves a common project type

**Playbook placement:**
- If a related playbook exists, add checklist items
- If enough insights cluster around a new task type to warrant a new playbook, propose it for approval

### 7. Report

Present a structured summary of what was ingested:

```
INGESTION REPORT
═══════════════════════════════════════════════════════════════

Source: [count] files from [path]
Extraction depth: shallow | deep

KNOWLEDGE FILES
  Created: [list of new YAML files with rule count]
  Updated: [list of existing files with new rule count]
  Total new rules: [count]

DISCIPLINE PARKING LOT
  New entries: [count] ([count] NEEDS VALIDATION)
  Cross-discipline entries: [count] (in [discipline names])

AGENT SUGGESTIONS
  New roles added: [list with category]
  Existing roles enriched: [list with what was added]

PLAYBOOKS
  Updated: [playbook name — added N checklist items] | none
  Proposed: [new playbook name and reason] | none

PROCESS DOCS
  Updated: [doc name — what changed] | none

TEMPLATES
  Updated: [template name — what changed] | none

SKILL CANDIDATES (requires user approval)
  [name] — [one-line description]
  [name] — [one-line description]

FILTERING
  Insights extracted: [count]
  Insights placed: [count]
  Insights filtered: [count] (tool-specific: N, opinion-only: N, duplicates: N, too-specific: N)

GAPS IDENTIFIED
  [List areas where the source material was thin or where the framework needs more depth]

SOURCE COVERAGE
  [count]/[total] files produced extractable insights
  Top contributors: [files that yielded the most insights]
  No-yield files: [files that produced nothing useful, with brief reason]

SPEC RELEVANCE
  New knowledge files default to spec_relevant: false
  Potentially spec-relevant: [list files that may warrant override to true, with rationale]

DOWNSTREAM IMPACT
  New files need adding to skeleton/manifest.json
  New knowledge files may need wiring in knowledge/agent-context-map.yaml
  Child projects will receive these on next migration via `sdlc-migrate`
```

### 8. Changelog Update

Update `process/sdlc_changelog.md` with the ingestion event:

```markdown
## [date]: Framework Ingestion — [primary domain]

**Origin:** Bulk ingestion from [source description]

**What happened:** [count] [content type] files analyzed for framework enrichment.

**Changes made:**

1. **`knowledge/[discipline]/[file].yaml`** — [created/updated] with [count] new rules ([ID range])
2. **`disciplines/[name].md`** — [count] new parking lot entries added
3. **`agents/AGENT_SUGGESTIONS.md`** — [added/enriched] [count] agent roles
4. **`playbooks/[name].md`** — [updated/proposed] with [count] new items
[5. **`process/[name].md`** — [what changed]]
[6. **`templates/[name].md`** — [what changed]]

**Skill candidates proposed:** [count] (pending user approval)

**Downstream:** Child projects will receive these artifacts on next migration.

**Rationale:** [brief justification for the import]
```

### 9. Manifest Sync

After writing artifacts:

1. Add any new files to `skeleton/manifest.json` in the appropriate section
2. If new knowledge files should be wired to agents, update `knowledge/agent-context-map.yaml`
3. Verify the manifest stays consistent — run the manifest completeness check from CLAUDE.md

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll summarize the content" | Extract actionable artifacts, not summaries. |
| "Everything in here is useful" | Filter aggressively. Most external content doesn't meet the bar. |
| "I'll auto-create a skill from this" | Note skill candidates in the report. Skills need intentional design via `/zsdlc-create-skill`. |
| "I'll create a new agent .md file" | Agent suggestions go to `AGENT_SUGGESTIONS.md`. Creating agent files is a separate, deliberate step. |
| "I'll skip reading existing artifacts" | Deduplication is mandatory. Don't create entries that already exist. |
| "I'll put everything in knowledge YAML" | Route to the right artifact type. A workflow isn't a rule. A checklist isn't a rule. |
| "This content spans 5 artifact types" | That's fine — classify and route each insight independently. |
| "I'll skip the manifest update" | New files must be added to `skeleton/manifest.json` and wired appropriately. |
| "I'll skip source attribution" | Every insight traces to a source. No exceptions. |

## Integration

- **Feeds into:** discipline parking lot triage, knowledge store maturation, playbook creation, agent suggestion adoption, skill creation, child project migrations
- **Uses:** file reading, existing framework artifacts (for deduplication and convention-matching)
- **Complements:** discipline capture protocol (organic, per-session in child projects) — this skill handles bulk external import into the framework
- **Does NOT replace:** organic discipline capture in child projects, or targeted enrichment of individual agents
- **Downstream:** after ingestion, `/zsdlc-audit` can assess freshness and coverage. Child projects receive new artifacts via `sdlc-migrate`.
- **DRY notes:** This is the framework-level ingest skill (`.claude/skills/zsdlc-ingest/`). The child-project version (`skills/sdlc-ingest/`) imports into `ops/sdlc/` paths only. The boundary: this version enriches the framework itself across all artifact types; the child version enriches a specific project's discipline/knowledge layer.
