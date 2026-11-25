# Knowledge Routing

## Purpose

Domain agents start each session without accumulated context. They don't know which patterns apply to their domain, which pitfalls to avoid, or which methodology the project has converged on. If knowledge files exist but aren't wired into the dispatch path, agents will either rediscover that knowledge the hard way or make decisions inconsistent with prior work. Knowledge routing solves this by giving the framework a systematic way to ensure agents receive the right files at the right time — not through ad-hoc prompt construction, but through a maintained map that skills consult before dispatching.

---

## How It Works

### The context map

All routing is governed by a single file: `[sdlc-root]/knowledge/agent-context-map.yaml`. It contains one top-level key, `mappings:`, whose value is an object. Each key in that object is an agent name. Each value is a list of file paths — the knowledge files that agent should read before starting domain work.

```yaml
mappings:
  architect:
    - "[sdlc-root]/knowledge/architecture/backend-capability-assessment.yaml"
    - "[sdlc-root]/knowledge/architecture/technology-patterns.yaml"
    ...
  backend-developer:
    - "[sdlc-root]/knowledge/coding/code-quality-principles.yaml"
    ...
```

The files in each list are project knowledge stores: YAML files containing reusable patterns, known anti-patterns, methodology entries, and domain gotchas. A `technology-patterns.yaml` file might contain decisions about which libraries the project uses and why. A `domain-boundary-gotchas.yaml` might list known pitfalls at the seams between subsystems. A `testing-paradigm.yaml` might define what constitutes an acceptable test in this project. These files are not documentation for humans to browse — they are context payloads that agents consume.

### The agent-side contract

Every agent built on this framework carries a `## Knowledge Context` section in its system prompt. The canonical instruction, taken verbatim from `templates/agent-template.md`, is:

> Before starting substantive work, consult `[sdlc-root]/knowledge/agent-context-map.yaml` and find your entry. Read the mapped knowledge files — they contain reusable patterns, anti-patterns, and domain-specific guidance relevant to your work.

This means every agent is responsible for finding its own name in the map and reading the listed files before proceeding. No special tooling or injection is required — the agent reads the map, reads the files, and then starts its domain work with that context in scope.

### The dispatch-time contract

Skills that dispatch agents carry a parallel responsibility. Before dispatching, the skill consults the map and includes the agent's mapped file paths in the dispatch prompt, typically as a prefixed instruction:

> Before implementing, read [paths] for relevant patterns.

This covers cases where an agent's access to the map file cannot be assumed — for example, when an agent is invoked in a restricted tool environment or when the dispatch prompt is the primary vehicle for context. Including the paths directly in the dispatch is a belt-and-suspenders measure: the agent would find them via the map anyway, but the skill makes them explicit.

**Cross-domain injection:** When an agent works in a context outside its primary domain, skills may inject knowledge files from *other* agents' mappings. For example, when dispatching an SDET to write tests for a feature, `sdlc-tests-create` looks up the agents who built that feature and includes their domain knowledge in the SDET's dispatch prompt. This ensures the tester understands the implementation's patterns and constraints without having to rediscover them. Skills use judgment here — cross-domain injection applies when genuinely crossing boundaries, not for routine single-domain work.

### Concrete example

The `architect` agent has one of the larger mappings in the current map. A three-entry excerpt:

```yaml
architect:
  - "[sdlc-root]/knowledge/architecture/backend-capability-assessment.yaml"
  - "[sdlc-root]/knowledge/architecture/technology-patterns.yaml"
  - "[sdlc-root]/knowledge/architecture/pipeline-design-patterns.yaml"
```

`backend-capability-assessment.yaml` gives the architect a current-state read on what the backend can and cannot do, so design proposals stay grounded. `technology-patterns.yaml` captures which libraries and patterns the project has converged on, preventing re-litigation of settled decisions. `pipeline-design-patterns.yaml` documents how data pipelines are structured in this project. All three files narrow the solution space before the architect writes a line of design prose.

---

## Map Structure Reference

| Field | Type | Description |
|-------|------|-------------|
| `mappings` | object | Top-level key. Contains one entry per registered agent. |
| Agent name key | string | Matches the agent's `.md` filename without the extension (e.g., `architect` for `architect.md`). |
| File path list | array of strings | Ordered list of paths to knowledge files. Paths are relative to the project root. Files are read in list order. |

Minimal valid structure:

```yaml
mappings:
  my-agent:
    - "[sdlc-root]/knowledge/architecture/agent-communication-protocol.yaml"
```

---

## Adding a New Agent

1. **Create the agent definition file** at `.claude/agents/[agent-name].md`. The agent name must use lowercase letters and hyphens only (e.g., `data-pipeline-engineer`).

2. **Add an entry to `agent-context-map.yaml`** under `mappings:`. The key must match the filename without the `.md` extension exactly — a mismatch means the agent's `## Knowledge Context` lookup fails silently.

3. **List knowledge file paths** that are relevant to the agent's domain. Consider including `[sdlc-root]/knowledge/architecture/agent-communication-protocol.yaml` for agents that emit structured handoffs (see Shared Knowledge below). Add domain-specific files as they exist or are created.

4. **Verify the entry** by reading the agent's system prompt instructions and confirming that the file paths in the map actually exist on disk. An agent that tries to read a non-existent path will waste context window on an error.

   ```bash
   # Quick check: confirm each path exists ([sdlc-root] is ops/sdlc)
   sdlc_root="ops/sdlc"
   for f in $(grep -A 20 'my-new-agent:' "$sdlc_root/knowledge/agent-context-map.yaml" | grep '^\s*-' | sed 's/.*"\[sdlc-root\]//' | sed 's/".*//' ); do
     resolved="$sdlc_root$f"
     [ -f "$resolved" ] && echo "OK: $resolved" || echo "MISSING: $resolved"
   done
   ```

5. **Add the `## Knowledge Context` section** to the agent's system prompt if using the template — it is already present in `agent-template.md`. Confirm the wording matches the canonical text.

---

## Adding Knowledge to an Existing Agent

Open `agent-context-map.yaml`, find the agent's entry under `mappings:`, and append the new file path to its list. No other changes are required — the agent will read the file on its next dispatch.

**Order matters.** Files are read in list order. Place broadly applicable files (shared patterns, communication protocol) earlier in the list and narrowly applicable files (domain-specific gotchas, subsystem-specific patterns) later. This way, if context limits force an agent to stop reading early, the most general knowledge survives.

Do not add files that belong to another domain without considering the signal-to-noise ratio. An agent loaded with marginally relevant context takes longer to orient and may draw on patterns that don't apply. Prefer focused lists over exhaustive ones.

---

## Shared Knowledge

`[sdlc-root]/knowledge/architecture/agent-communication-protocol.yaml` appears in most domain agents' mappings. The communication protocol defines how agents structure their output, send progress updates, and format handoffs. Agents that emit structured handoffs should include this file; utility agents with simpler output patterns may omit it.

This reflects a general principle: cross-cutting knowledge goes in each relevant agent's list explicitly. There is no "include all" directive, no wildcard, and no inheritance. Explicit lists are load-bearing — they make the knowledge contract for each agent visible and auditable at a glance.

If you add a new knowledge file that should apply to multiple agents (e.g., a project-wide conventions file), you must add it to each agent's list manually. That friction is a feature: it forces a decision about whether the file genuinely applies to each agent, rather than defaulting to broad injection.

---

## Adapter Plugins and the Phrasing Contract

Some projects use an adapter plugin (e.g., `neuroloom-sdlc-plugin`) that swaps z-sdlc's file-based knowledge routing for a different backend (e.g., a memory graph accessed via `memory_search`). The adapter plugin transforms skills and agents at install time — replacing file-path references with backend-native calls — and preserves those transformations during migrations via content-aware merging.

This pattern (core stays pure, adapter transforms at boundaries) follows the Terraform/Prisma provider model. The key constraint: **z-sdlc must use consistent phrasing** so the adapter's pattern-matching transformer can find and replace references reliably.

### Standard Phrases (the contract)

Skills and agents that reference the knowledge layer MUST use these exact phrases so adapter plugins can transform them reliably. Deviations break the transformer and cause silent routing failures in adapter-based projects.

| Use Case | Required Phrasing | Notes |
|----------|-------------------|-------|
| Looking up an agent's mapped knowledge files | `consult [sdlc-root]/knowledge/agent-context-map.yaml` | Lowercase unless at sentence start (`Consult ...`) |
| Cross-domain knowledge injection during dispatch | `Consult [sdlc-root]/knowledge/agent-context-map.yaml for the [agent-name] entry and include relevant knowledge files in the dispatch prompt` | Standard dispatch-time form |
| Agent's Knowledge Context section (canonical, from `templates/agent-template.md`) | `Before starting substantive work, consult [sdlc-root]/knowledge/agent-context-map.yaml and find your entry. Read the mapped knowledge files...` | Full template |
| Referencing the communication protocol | `Read [sdlc-root]/knowledge/architecture/agent-communication-protocol.yaml` | — |
| Reading domain knowledge stores | `Read [sdlc-root]/knowledge/<domain>/<file>.yaml` | Use literal domain and file names |
| Wiring new files to agent mappings | `update [sdlc-root]/knowledge/agent-context-map.yaml` | Use `update`, not "Read and add" or "Connect via" |
| Appending to discipline parking lots | `Append to [sdlc-root]/disciplines/*.md` | For discipline capture instructions |

### Forbidden Phrasings (rewrite to canonical)

These phrasings are NOT canonical. Rewrite them to use one of the forms above. The adapter plugin's Pattern Mapping does not match these variants, so they leak file-based references into Neuroloom projects.

| Forbidden | Canonical Replacement |
|-----------|----------------------|
| `Read [sdlc-root]/knowledge/agent-context-map.yaml` (as instruction, not as file-read metadata) | `consult [sdlc-root]/knowledge/agent-context-map.yaml` |
| `Look up ... in [sdlc-root]/knowledge/agent-context-map.yaml` | `Consult [sdlc-root]/knowledge/agent-context-map.yaml for ...` |
| `via [sdlc-root]/knowledge/agent-context-map.yaml` (as instruction) | `update [sdlc-root]/knowledge/agent-context-map.yaml` |
| `directing them to [sdlc-root]/knowledge/agent-context-map.yaml` | `instructing them to consult [sdlc-root]/knowledge/agent-context-map.yaml` |
| `Connect ... via [sdlc-root]/knowledge/agent-context-map.yaml` | `Update [sdlc-root]/knowledge/agent-context-map.yaml to wire ...` |
| `Read and follow the full methodology at [sdlc-root]/knowledge/<file>` | `Read [sdlc-root]/knowledge/<file> for the full methodology` |
| `Apply the [X] paradigm from [sdlc-root]/knowledge/<file>` | `Read [sdlc-root]/knowledge/<file> and apply the [X] paradigm` |
| `go to your SDLC knowledge store ([sdlc-root]/knowledge/<domain>/)` | `append to [sdlc-root]/knowledge/<domain>/` |
| `(see [sdlc-root]/knowledge/<file>)` parenthetical asides | Extract into its own sentence using canonical `Read [sdlc-root]/knowledge/<file>` |

**Parenthetical rule:** Never put knowledge-file references inside parentheses when they're instructions. Parentheticals read as asides even when the content is load-bearing, and the adapter's pattern matching skips parenthetical references. If the reference is instructional, pull it out of parentheses into its own sentence.

### Metadata Contexts

References that are **not runtime instructions to an agent** are exempt from the instruction-phrase contract rules. These include:

- Integration sections in skill/agent frontmatter (`**Uses:** [path]`, `**Depends on:** [path]`)
- Tables listing file paths as data (file category tables, migration strategy tables)
- Changelog entries describing what changed
- Phrasing contract documentation itself (this doc, `sdlc-reviewer.md` checklist, `sdlc-compliance-auditor.md` validation criteria)
- Audit dimension descriptions
- Path examples in bulleted feature lists
- Parenthetical path labels in category descriptions (`Discipline parking lot entries ([sdlc-root]/disciplines/*.md)`)

In these contexts, use inline-backticked paths (e.g., `` `[sdlc-root]/knowledge/agent-context-map.yaml` ``). The distinguishing rule: if removing the reference would prevent an agent from completing its task at runtime, it's an instruction (contract-covered); if removing it only affects documentation readability, it's metadata.

#### Adapter metadata transformation (Neuroloom and similar)

Metadata references point at filesystem locations that exist in file-based z-sdlc installations but **don't exist in adapter-backend projects** (e.g., `[sdlc-root]/disciplines/*.md` paths are invalid in Neuroloom where disciplines live in the memory graph). To avoid misleading Neuroloom users with dead file paths, adapter plugins MAY transform metadata references in parenthetical/table-cell contexts to their backend-native equivalent.

For example, the Neuroloom plugin transforms:
- `Discipline parking lot entries ([sdlc-root]/disciplines/*.md)` → `Discipline parking lot entries (memory graph, entries tagged sdlc:discipline:*)`
- Table cells `| ... | [sdlc-root]/knowledge/**/*.yaml | ... |` → `| ... | memory graph (sdlc:knowledge tags) | ... |`

Not all adapters need to do this — it's an adapter design choice. The contract doesn't require it; it just doesn't forbid it. If your adapter implements metadata transformation, document the rules in its Pattern Mapping table.

**Metadata transformation is never applied to:**
- `[sdlc-root]/process/` (process files exist on disk in all modes)
- `[sdlc-root]/templates/` (templates exist on disk)
- `[sdlc-root]/playbooks/` (playbooks exist on disk)
- `[sdlc-root]/agents/` (agents are installed to `.claude/agents/`)
- Fenced code blocks or backticked paths used as examples

### Non-Goals

- **Don't scatter conditional branches** across skills. The adapter handles translation at install time — inline conditionals add noise without adding capability.
- **Don't invent new phrasings** for the same operation. If a skill needs to look up an agent's mapped files, use the exact phrase from the canonical table above.
- **Don't directly reference adapter-specific tools** in z-sdlc skills. Those are adapter concerns.

### Relationship to the Adapter Lifecycle Protocol

This document governs the **content contract** — what phrases z-sdlc uses so adapters can transform them. The **adapter lifecycle protocol** (`[sdlc-root]/process/adapter-lifecycle-protocol.md`) governs **execution** — when adapters run during initialize and migrate, and how upstream delegates knowledge and transformation phases. Both are required for adapter integration.

### When z-sdlc Changes

If a change to z-sdlc introduces a new knowledge-access pattern, the adapter plugin's handler doc must be updated in parallel. Document the new phrase in the table above so the adapter maintainer can add a transformation rule. The commit message should tag the change with `[contract-change]` so adapter maintainers can filter for it.

### Adapter Version Declaration (required)

Every adapter plugin MUST declare which z-sdlc version its Pattern Mapping and post-op audit have been verified against. This declaration is the single source of truth used by upstream's `sdlc-migrate` §1.2 contract-change gate to decide whether `[contract-change]` entries in the migration range are safe to auto-resolve or require a deterministic halt.

**Required field in plugin manifest** (`.claude-plugin/plugin.json` or equivalent):

```json
{
  "name": "<adapter-plugin-name>",
  "version": "<plugin-semver>",
  "supported_zsdlc_version": "<highest z-sdlc version covered>"
}
```

Adapters written before 2026-10-12 declare it as `supported_ccsdlc_version` (and mark themselves with `ccsdlc_adapter`); readers accept either name.

**Semantics:** `supported_zsdlc_version` is the highest z-sdlc version whose `[contract-change]` entries have been reviewed and reflected in the plugin's transformation rules and forbidden-phrase detection. The plugin maintainer bumps this field after verifying coverage — never before.

**Upstream migrate gate:** `sdlc-migrate` §1.2 MUST use deterministic semver comparison at its contract-change gate. For each `[contract-change]` entry in the migration range, compare the entry's z-sdlc version against the adapter's declared `supported_zsdlc_version` (from `adapter.json`):
- `entry_version <= supported_zsdlc_version` → the adapter declares support; auto-resolve and continue.
- `entry_version > supported_zsdlc_version` → halt deterministically with a message that identifies the uncovered entries and the current PSV.

Prose-interpreted gates (where the LLM running the skill decides at runtime whether coverage is "probably fine") are explicitly forbidden. The determinism requirement exists because prose-interpreted gates are non-reproducible: the same migration run twice can halt once and silently pass the other. That defeats the purpose of the gate.

**When bumping `supported_zsdlc_version`:** review every `[contract-change]` entry in z-sdlc's changelog between the previous PSV and the new PSV. Verify the adapter's transformation rules have handlers for each newly standardized phrase AND the adapter's post-op audit has detectors for each newly forbidden phrase. Bumping without verification defeats the entire gate — it converts a deterministic safety check into a rubber stamp.

**First-time introduction:** this requirement was added to the contract mid-stream. Existing adapters (e.g., `neuroloom-sdlc-plugin` at 0.4.0+) must add the field on their next release. Adapters without the field MUST halt their own migrate gate — missing declaration is treated as "unsupported at any version."

---

## Limitations

**Linear scaling with knowledge volume.** Each agent reads its full file list on every dispatch. As the number of knowledge files grows, so does the context consumed before an agent starts its actual work. There is no lazy loading, no relevance scoring, and no file-level caching across dispatches. For agents with large mappings (e.g., `architect` has 10+ files), this is a real cost.

**Manual map maintenance.** Adding an agent, renaming a knowledge file, or reorganizing the knowledge directory requires a manual update to `agent-context-map.yaml`. There is no automation to detect drift between the map and the filesystem. A renamed file that isn't updated in the map will cause a silent read failure at dispatch time.

**No conditional routing.** Every file in an agent's list is loaded on every dispatch, regardless of what the task actually requires. A `backend-developer` dispatched to fix a one-line bug still loads all backend knowledge files. Task-aware routing — selecting a subset of files based on task type or involved paths — is not supported by the current flat-list structure.

A tag-based alternative (where knowledge files carry tags and agents declare which tags they need) would address the last two limitations. That approach would allow richer routing logic and make map maintenance more resilient to file reorganization. No such mechanism exists in the current framework; this is a known area for future development.
