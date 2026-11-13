---
name: zsdlc-create-skill
description: >
  Create a new SDLC framework skill in the z-sdlc source repo. Walks through purpose definition,
  skill type selection (orchestration, utility, exploration, domain-specific), frontmatter
  generation with trigger phrases and anti-triggers, type-appropriate body scaffolding,
  Red Flags table, Integration section, and registration in manifest.json and CLAUDE-SDLC.md.
  Enforces single-line YAML descriptions, verb-first naming, manager-rule references for
  agent-dispatching skills, and mandatory sections. Dispatches sdlc-reviewer for quality gate.
  Triggers on "create a new skill", "new skill", "add a skill", "scaffold a skill",
  "I need a skill for", "make a skill", "create a framework skill", "/zsdlc-create-skill".
  Do NOT use for creating agents.
  Do NOT use for modifying existing skills — edit directly.
---

# Skill Creation

Create a new SDLC framework skill in the z-sdlc source repo. Scaffold the complete skill file, validate conventions, register in the manifest, and quality-gate with the reviewer subagent.

**Argument:** `$ARGUMENTS` (what the skill should do)

## Steps

### 1. Purpose Definition

Clarify with the user:
- **What does this skill do?** (one sentence)
- **What skill type?**
  - **Orchestration** — dispatches domain agents, has agent selection criteria, review loops (e.g., sdlc-plan, sdlc-execute, sdlc-review-code)
  - **Utility** — step-by-step procedure, may or may not dispatch agents (e.g., sdlc-archive, sdlc-ingest)
  - **Exploration** — open-ended flow, no hard gates, user-directed iteration (e.g., sdlc-idea, sdlc-design-consult)
  - **Domain-specific** — focused on a specific technical domain (e.g., sdlc-tests-create, sdlc-tests-run)
- **What triggers this skill?** (natural language phrases users would say)
- **What should NOT trigger this skill?** (anti-triggers — which existing skills handle adjacent concerns)

### 2. Name Generation

Generate a name following conventions:
- Format: `lowercase-with-hyphens`, 2-4 words
- Verb-first preferred (e.g., `sdlc-review-code`, not `code-review`)
- Must not conflict with existing skills

Read `skeleton/manifest.json` → `source_files.skills` to list existing skill names. Present the proposed name and confirm.

### 3. Frontmatter Generation

The `description` field uses `>` (folded scalar), the form `sdlc-reviewer` checks for: multi-line quoted strings and `|` block scalars can break Claude Code's frontmatter parser.

The description includes:
- What the skill does (1-2 sentences)
- Explicit trigger phrases (`Triggers on "phrase1", "phrase2", ...`)
- Anti-triggers (`Do NOT use for X — use Y.`)

Template:

```yaml
---
name: {name}
description: >
  {What it does — 1-2 sentences}.
  Triggers on "{phrase1}", "{phrase2}", "{phrase3}", "/{name}".
  Do NOT use for {anti-trigger1} — use {alternative1}.
  Do NOT use for {anti-trigger2} — use {alternative2}.
---
```

### 4. Body Scaffolding

Generate the skill body based on type. All types share common requirements; each type adds specific sections.

#### All Types (required sections)

- **Title** — `# {Skill Title}` with 1-2 sentence summary
- **Argument** — `**Argument:** $ARGUMENTS (description)` if the skill accepts input
- **Steps** — numbered steps with `### N. Step Name` headers
- **Red Flags** — `## Red Flags` table (see step 6)
- **Integration** — `## Integration` section (see step 7)
- **Headless stop rule** — the `headless-stop-rule` block from `process/headless-mode.md` § Mirrored Stop Rule, copied verbatim inside `MIRROR-START`/`MIRROR-END` comment markers whose label joins the source file and block id as `{process-file}#{section-id}`. Place it directly after the skill's `**AskUserQuestion mandate:**` paragraph if it has one, otherwise directly before its first `##` section. Every `sdlc-*` skill carries it; the mirror table already lists them all, so no table row is needed. A gate whose stop needs stating at the gate itself — the status it stops with, what the stop carries, a step it skips, or an outward action it would otherwise take — gets its own **Headless run:** line at the gate, outside the markers, and is added to that doc's § Integration list. A skill whose restart from step 1 would repeat a side effect or lose counted state (a D-number, completed phases, a review round) also gets a **Headless restart** paragraph in its entry step.

#### Orchestration Skills (additional requirements)

- **Workflow diagram** — `STEP → STEP → STEP` showing the flow
- **Manager Rule** — `## Manager Rule` section: "Read and follow `process/manager-rule.md`."
- **Agent Dispatch Protocol** — "Dispatch prompts must describe WHAT/WHY — implementation HOW is the agent's domain."
- **Agent Selection Criteria** — table or tiered list showing which agents to dispatch and when
- **Review lenses** — what each reviewing agent checks for
- **Review-Fix Loop** — if the skill has iterative review, carry the matching mirrored critical-steps block verbatim (code review or plan review) per `process/review-fix-loop.md` § Mirrored Critical-Steps Blocks, wrapped in its `MIRROR-START`/`MIRROR-END` markers, and add the skill to that section's table. Never reduce loop steps to a bare pointer (changelog 2026-05-19).

#### Utility Skills (additional requirements)

- **Preconditions** — what must exist before the skill runs
- **Output format** — what artifacts the skill produces and where they go
- **Validation criteria** — how to verify each step succeeded

#### Exploration Skills (additional requirements)

- **Workflow diagram** — non-linear, with iteration loops
- **Core Principles** — what guides the exploration
- **Iterate section** — user controls the loop, with soft prompts after N rounds
- **Optional output format** — exploration may or may not produce artifacts

### 5. Bundled Resources

Determine if the skill needs reference files:
- **references/** — detailed methodology, checklists, or domain-specific content that would bloat SKILL.md (target SKILL.md body at 1,500-3,000 words; overflow goes to references)
- **scripts/** — executable utilities the skill runs repeatedly

If references are needed, create a `## Additional Resources` section at the end of SKILL.md listing each file with a description.

### 6. Red Flags Table

Generate 6-10 red flags specific to this skill. Format:

```markdown
## Red Flags

| Thought | Reality |
|---------|---------|
| "[Common mistake]" | [Why it's wrong and what to do instead] |
```

Include universal red flags relevant to the skill type:
- Orchestration: "I'll implement this myself instead of dispatching" / "The agent has context from earlier"
- All types: "I'll skip the changelog update" / "This skill doesn't need anti-triggers"

### 7. Integration Section

Generate:

```markdown
## Integration

- **Depends on:** [what must exist before this skill runs]
- **Feeds into:** [what skills consume this skill's output]
- **Uses:** [tools, agents, knowledge files this skill uses]
- **Complements:** [sibling skills]
- **Does NOT replace:** [similar-sounding skills that handle different concerns]
- **DRY notes:** [if this skill overlaps with existing skills, document the boundary]
```

### 8. Write and Register

1. Write the skill file to `skills/{name}/SKILL.md`
2. Add `"skills/{name}/SKILL.md"` to `skeleton/manifest.json` → `source_files.skills`
3. Add a command row to `CLAUDE-SDLC.md` if the skill is user-invokable
4. Add a changelog entry to `process/sdlc_changelog.md`

### 9. Quality Gate

Dispatch the `sdlc-reviewer` subagent on the created skill file. Its brief is written for an installed project, so the dispatch prompt says this is the z-sdlc source repo: `skills/{name}/SKILL.md` is a skill, and `[sdlc-root]` is the repo root (not the `ops/sdlc` that the root `.sdlc-manifest.json` template names). Present its findings. Fix any convention violations before finalizing.

## Red Flags

| Thought | Reality |
|---------|---------|
| "The description can span multiple YAML lines with quotes" | Use `>` folded scalar. Other multi-line formats can break Claude Code's frontmatter parser. |
| "This skill doesn't need anti-triggers" | Every skill needs anti-triggers to prevent overlap with siblings. |
| "Red flags are optional for utility skills" | Every skill type needs a Red Flags table. No exceptions. |
| "I'll skip the Integration section — this skill is standalone" | No skill is standalone. Every skill feeds into or complements others. |
| "The name should describe the noun first" | Verb-first naming: `sdlc-review-code`, not `code-review`. |
| "I'll register it later" | Registration (manifest, CLAUDE-SDLC.md, changelog) happens in the same step as creation. |
| "This orchestration skill doesn't need the Manager Rule" | If it dispatches agents, it MUST reference manager-rule.md. |
| "I'll write the skill directly without this scaffolding" | Hand-written skills skip convention validation. Use this skill. |
| "SKILL.md can be as long as needed" | Target 1,500-3,000 words for SKILL.md body. Move detailed content to references/. |

## Integration

- **Feeds into:** The created skill becomes part of the z-sdlc framework skill library (installed to child projects by `sdlc-initialize` and `sdlc-migrate`)
- **Uses:** `skeleton/manifest.json` (registration), `CLAUDE-SDLC.md` (command table), `sdlc-reviewer` (quality gate), existing skills (as reference patterns)
- **Complements:** `sdlc-develop-agent` (agents vs skills), `sdlc-reviewer` (review an existing skill file)
- **Does NOT replace:** Direct editing of existing skills (this creates new ones only)
