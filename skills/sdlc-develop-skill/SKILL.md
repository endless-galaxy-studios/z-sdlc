---
name: sdlc-develop-skill
description: >
  Create or modify project skills following z-sdlc conventions. Two modes: CREATE mode walks
  through purpose definition, skill type selection (orchestration, utility, exploration,
  domain-specific), frontmatter generation with trigger phrases and anti-triggers, type-appropriate
  body scaffolding, Red Flags table, and Integration section. MODIFY mode reads an existing skill,
  identifies changes, auto-wraps custom content in PROJECT-SECTION markers, and warns if changes
  target framework sections that will be overwritten on next migration. Both modes run a DRY audit:
  scans sibling skills for content overlap and proposes extraction (shared reference, knowledge
  store, or process doc with one-line pointers) instead of duplicating prose. When the user
  modifies multiple skills in one invocation, detects shared changes and centralizes them.
  Enforces single-line YAML descriptions, verb-first naming, manager-rule references for
  agent-dispatching skills, and mandatory sections. Dispatches sdlc-reviewer for quality gate.
  Use when creating a new skill or modifying an existing one in the SDLC framework.
  Triggers on "create a new skill", "new skill", "add a skill", "scaffold a skill",
  "I need a skill for", "make a skill", "modify a skill", "update a skill", "customize a skill",
  "/sdlc-develop-skill", "/sdlc-create-skill".
  Do NOT use for creating agents — use sdlc-develop-agent.
  Do NOT use for the project's verify skill (.claude/skills/verify/) — use sdlc-develop-verify-skill.
---

# Skill Development

Create or modify SDLC skills following z-sdlc conventions. Scaffold new skills with convention enforcement, or safely modify existing skills with migration-aware wrapping.

**Argument:** `$ARGUMENTS` (what the skill should do, or which existing skill to modify)

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## Mode Selection

| User Intent | Mode | Entry Point |
|-------------|------|-------------|
| "Create a new skill", "scaffold a skill", "I need a skill for X" | **CREATE** | Step 1 (full creation workflow) |
| "Modify a skill", "update a skill", "customize a skill", "add a phase to X" | **MODIFY** | Modify Workflow below |
| Unclear | Ask: "Are you creating a new skill or modifying an existing one?" | — |

---

## CREATE Mode

### Steps

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

### 1.5. DRY Audit (overlap with existing skills)

Before scaffolding, scan for content overlap with sibling skills. Skipping this step is the most common source of long-term drift — the same framing sentence, principle, or warning ends up duplicated across two or three skills, then evolves independently.

1. **Scan triggers** — grep `.claude/skills/*/SKILL.md` for the proposed trigger phrases and adjacent concepts. If another skill claims overlapping triggers, refine anti-triggers or merge.
2. **Scan body content** — for each existing skill in the same family (sibling orchestrators, sibling utilities, etc.), identify any section the new skill would also need. Candidates for sharing:
   - Universal principles (e.g., "ADRs are immutable", "agents see only their dispatch context")
   - Cross-skill protocols (manager rule, review-fix loop, phrasing contract)
   - Shared methodology that applies to a tier (e.g., both `sdlc-plan` and `sdlc-lite-plan` need ADR immutability rules)
3. **Choose the extraction target:**

| Shared content type | Extract to | Reference from skill via |
|---------------------|-----------|--------------------------|
| Universal SDLC principle, cross-skill protocol | `[sdlc-root]/process/{topic}.md` | One-line pointer: "Read and follow `[sdlc-root]/process/{topic}.md`." |
| Domain knowledge consumed by multiple skills | `[sdlc-root]/knowledge/{domain}/{topic}.yaml` | Phrasing-contract lookup |
| Detailed methodology used by 2+ skills in same family | New shared doc under `[sdlc-root]/process/` (NOT `references/` — those are per-skill) | One-line pointer |
| Single-skill detail that bloats SKILL.md | The skill's own `references/` | `## Additional Resources` link |

4. **Default to extraction** when content would appear verbatim (or near-verbatim) in 2+ skills. Inline duplication is acceptable only when (a) the content is short (≤2 sentences), (b) the framings genuinely differ between tiers, AND (c) you can articulate why divergence is desirable. Document the "why" in the Integration section's `DRY notes`. **`MIRROR` blocks are exempt:** they are deliberate, drift-checked copies (`[sdlc-root]/process/project-section-markers.md` § MIRROR Markers), so overlap scans skip them and never recommend extracting one to a pointer.

5. **If extraction is needed but out of scope** for this invocation, surface it: "This skill duplicates {content} from {sibling skills}. Recommend extracting to {target} in a follow-up." Do not silently re-duplicate.

### 2. Name Generation

Generate a name following conventions:
- Format: `lowercase-with-hyphens`, 2-4 words
- Verb-first preferred (e.g., `sdlc-review-code`, not `code-review`)
- Must not conflict with existing skills

Scan `.claude/skills/` to list existing skill names. Present the proposed name and confirm no conflicts.

### 3. Frontmatter Generation

**CRITICAL:** The `description` field MUST use `>` (folded scalar) for readability. Multi-line quoted strings and block scalars (`|`) break Claude Code's frontmatter parser in some contexts.

The description MUST include:
- What the skill does (1-2 sentences)
- Explicit trigger phrases (`Triggers on "phrase1", "phrase2", ...`)
- Anti-triggers (`Do NOT use for X — use Y.`)

**Activation framing rule:** Use imperative/mandatory language in descriptions and trigger phrases. Advisory framing ("Best practices for X", "Guidance on X") causes agents to skip the skill — empirically measured at ~10% activation rate. Mandatory framing ("Rules that MUST be followed when working on X", "Required steps for X") achieves 57-83% activation. The description is the primary signal agents use to decide whether to invoke the skill — treat it as a trigger, not a summary. (Evidence: Tessl controlled experiment, 30 trials per configuration — `[sdlc-root]/knowledge/coding/context-engineering-patterns.yaml`, activation_engineering section.)

**Triggering accuracy validation:** Before finalizing the description, read `[sdlc-root]/knowledge/dx/skill-quality-rubrics.yaml` and apply the SQR-01/SQR-02 mental test: write 5 prompts that should trigger the skill and 5 that should not. If 3+ of either set misfire, rewrite the trigger contexts.

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
- **Headless stop rule** — the `headless-stop-rule` block from `[sdlc-root]/process/headless-mode.md` § Mirrored Stop Rule, copied verbatim inside `MIRROR-START`/`MIRROR-END` comment markers whose label joins the source file and block id as `{process-file}#{section-id}` (per `[sdlc-root]/process/project-section-markers.md` § MIRROR Markers) — never the source doc's `MIRROR-SOURCE` markers. Place it directly after the skill's `**AskUserQuestion mandate:**` paragraph if it has one, otherwise directly before its first `##` section. Every `sdlc-*` skill carries it, including skills that never ask anything, so the rule needs no per-skill judgment; add it to project skills too. The mirror table already covers both, so no table row is needed. A gate whose stop needs stating at the gate itself — the status it stops with, what the stop carries, a step it skips, or an outward action it would otherwise take — gets its own **Headless run:** line at the gate, outside the markers. A skill whose restart from step 1 would repeat a side effect or lose counted state (a D-number, completed phases, a review round) also gets a **Headless restart** paragraph in its entry step. In z-sdlc source, add such gates to the doc's § Integration list; in a target project that list is upstream-owned, so keep the line in the skill and propose the list entry upstream.

#### Orchestration Skills (additional requirements)

- **Workflow diagram** — `STEP → STEP → STEP` showing the flow
- **Manager Rule** — `## Manager Rule` section: "Read and follow `[sdlc-root]/process/manager-rule.md`."
- **Agent Dispatch Protocol** — "Dispatch prompts must describe WHAT/WHY — implementation HOW is the agent's domain."
- **Agent Selection Criteria** — table or tiered list showing which agents to dispatch and when
- **Review lenses** — what each reviewing agent checks for
- **Review-Fix Loop** — if the skill has iterative review, carry the matching mirrored critical-steps block verbatim (code review or plan review) per `[sdlc-root]/process/review-fix-loop.md` § Mirrored Critical-Steps Blocks, wrapped in its `MIRROR-START`/`MIRROR-END` markers, and add the skill to that section's table. Never reduce loop steps to a bare pointer — the 2026-05-19 changelog entry records the loop being skipped after exactly that.
- **Phrasing Contract** — If the skill references the knowledge layer (e.g., `agent-context-map.yaml`, `knowledge/architecture/agent-communication-protocol.yaml`), use the exact standard phrasings from `[sdlc-root]/process/knowledge-routing.md` § "Standard Phrases". Do NOT add inline adapter conditionals — adapter plugins handle translation at install time.

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

**AVOID example warning:** If the skill includes "don't do this" anti-pattern examples, frame them carefully. Tessl found that AVOID examples in skills caused regressions — the agent followed the bad example rather than the instruction. Always pair anti-patterns with the correct pattern immediately after: "DO NOT do this: [bad]. Instead do this: [good]." Never show an anti-pattern without its replacement. (Evidence: Tessl Skill-Optimizer, hooks.md regression in database-plugin-architecture scenario — `[sdlc-root]/knowledge/testing/ai-generated-code-verification.yaml`, eval_contamination section.)

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

### 8. Write

1. Write the skill file to `.claude/skills/{name}/SKILL.md`
2. If the skill needs reference files, create `.claude/skills/{name}/references/` and add them
3. Add a changelog entry to `[sdlc-root]/process/sdlc_changelog.md`

### 9. Quality Gate

Dispatch the `sdlc-reviewer` subagent on the created skill file. The reviewer checks against the conventions in `[sdlc-root]/process/skill-agent-review.md`. Also audit against `[sdlc-root]/knowledge/dx/skill-quality-rubrics.yaml` — SQR-04 (scope calibration line counts), SQR-05 (progressive disclosure to references/), SQR-06 (directive density), and SQR-07 (anti-pattern flags: OVER_CONSTRAINED, EMPTY_DESCRIPTION, MISSING_TRIGGER, BLOATED_SKILL, ORPHAN_REFERENCE). Present findings. Fix any convention violations before finalizing.

---

## MODIFY Mode

Safely modify an existing skill with migration-aware wrapping. This mode reads the skill, identifies what the user wants to change, determines whether the change is framework-level or project-specific, and applies appropriate protection.

### Modify Workflow

### M1. Read and Analyze

1. Read the existing skill's `SKILL.md`
2. If the user names multiple skills (or "all the planning skills", "both X and Y"), read them all in parallel before proposing edits
3. Skills in `.claude/skills/` are framework-installed from z-sdlc, so direct edits to framework sections will be overwritten on next `sdlc-migrate`. The exception is the project's own skills, such as `.claude/skills/verify/`, which `sdlc-develop-verify-skill` maintains and migration never touches
4. Warn the user accordingly before making changes

### M1.5. DRY Audit (cross-skill drift detection)

Before applying any edit, run the same overlap scan as CREATE step 1.5 — but in MODIFY mode the questions are slightly different:

1. **Single-skill modification** — for each section the user wants to change, grep sibling skills for the same concept. If the change adds a sentence/paragraph that already exists elsewhere (or *should* exist elsewhere), flag it: "This addition restates content already in {sibling skill}. Options: (a) extract to shared location and pointer-reference from both, (b) leave divergent and document why in DRY notes, (c) update both in this invocation."
2. **Multi-skill modification** — when the user is changing 2+ skills in one invocation:
   - Detect when the same content is being added/changed in multiple targets. Default action: write it once to a shared location (`[sdlc-root]/process/{topic}.md` or knowledge store) and have each skill reference it.
   - Detect when one skill is being brought into alignment with a sibling that already has the content. Default action: extract from the source skill first, then point both at the extracted location — do not copy-paste forward.
   - When you must edit the same section across N skills, propose the extraction *first* and only inline if the user explicitly declines.
3. **Skip `MIRROR` blocks.** The headless stop rule (in every skill) and the review-loop blocks are deliberate copies; never propose extracting them. A change inside one is a change to its source doc (M2).
4. **Surface unjustified drift** — if grep reveals the same concept worded differently across skills (e.g., one says "ADRs are immutable", another says "Do not edit prior ADRs"), report it. The user may want to unify wording even if it's outside the requested change.

### M2. Classify the Change

Determine whether the user's requested change targets:

| Target | Classification | Action |
|--------|---------------|--------|
| Framework section (gates, workflow, dispatch protocol) | **Framework change** | Warn: "This section is framework-owned and will be overwritten on next migration. Consider proposing this upstream instead." |
| Project-specific addition (new phase, custom agent wiring, domain-specific step) | **Project addition** | Auto-wrap in `PROJECT-SECTION` markers |
| Existing `PROJECT-SECTION` block | **Project update** | Edit within existing markers |
| Inside a `MIRROR` block | **Source-doc change** | Do not edit the copy. A change to the block itself is an upstream change to its process doc: propose it to z-sdlc, where the block is edited once and re-copied into every skill. Project-specific wording goes in a `PROJECT-SECTION` outside the block. |

### M3. Apply with Protection

For **project additions** to framework skills:

1. Identify the insertion point (which section/heading the new content belongs under)
2. Wrap the new content in markers:

```html
<!-- PROJECT-SECTION-START: modify-YYYY-MM-DD-description -->
... new project-specific content ...
<!-- PROJECT-SECTION-END: modify-YYYY-MM-DD-description -->
```

3. Apply the edit
4. Confirm to the user that the content is migration-protected

For **framework changes**: present the warning and offer alternatives:
- Propose the change upstream (edit the z-sdlc source repo)
- Apply anyway with markers (will be preserved but may conflict with upstream changes)
- Apply without markers (will be overwritten on next migration — user accepts this)

### M4. Quality Gate

Dispatch the `sdlc-reviewer` subagent on the modified skill file. The reviewer checks against `[sdlc-root]/process/skill-agent-review.md`. Present its findings.

---

## Red Flags

| Thought | Reality |
|---------|---------|
| "The description can span multiple YAML lines with quotes" | Use `>` folded scalar. Other multi-line formats can break Claude Code's frontmatter parser. |
| "This skill doesn't need anti-triggers" | Every skill needs anti-triggers to prevent overlap with siblings. |
| "This skill never asks the user anything, so the headless block is noise" | Every skill carries it verbatim, so the rule needs no per-skill judgment. Reword nothing inside the markers; gate-specific wording goes outside them. |
| "Red flags are optional for utility skills" | Every skill type needs a Red Flags table. No exceptions. |
| "I'll skip the Integration section — this skill is standalone" | No skill is standalone. Every skill feeds into or complements others. |
| "The name should describe the noun first" | Verb-first naming: `sdlc-review-code`, not `code-review`. |
| "This orchestration skill doesn't need the Manager Rule" | If it dispatches agents, it MUST reference manager-rule.md. |
| "I'll use custom phrasing like 'check' or 'look at' for knowledge lookups" | Use the exact phrases from the phrasing contract. Custom wording breaks adapter transformers. |
| "I'll add an inline adapter conditional" | Core skills must not know about adapters. The adapter transforms phrases at install time — inline conditionals in core files are redundant and make the phrasing contract harder to maintain. |
| "I'll write the skill directly without this scaffolding" | Hand-written skills skip convention validation. Use this skill. |
| "SKILL.md can be as long as needed" | Target 1,500-3,000 words for SKILL.md body. Move detailed content to references/. |
| "I'll edit a framework skill directly without markers" | Framework sections are overwritten on migration. Use MODIFY mode to auto-wrap project-specific additions. |
| "The user wants to modify a skill, I'll just edit it" | Check if it's a framework skill first. If so, classify the change and apply appropriate protection. |
| "I'll write the same paragraph in both skills — they're related" | Default to extraction. Verbatim or near-verbatim content in 2+ skills drifts independently within weeks. Put it once in `[sdlc-root]/process/` or a knowledge store and reference it. |
| "The user is editing 3 skills, I'll just apply the same change to each" | Multi-skill changes are the strongest signal that content belongs in one shared location. Propose extraction first, then have each skill reference it. |
| "I'll inline this because the wording is *slightly* different in each tier" | Only acceptable if you can articulate why divergence is desirable AND document it in DRY notes. Otherwise the difference is drift, not design. |
| "Skipping the DRY audit — this is a small skill" | Small skills accrete duplicated framing too. The audit is grep-fast; skipping it is how `sdlc-plan` and `sdlc-lite-plan` ended up with three duplicated paragraphs. |

## Integration

- **Feeds into:** The created/modified skill becomes part of the project's skill library
- **Uses:** `sdlc-reviewer` (quality gate), existing skills in `.claude/skills/` (as reference patterns), `[sdlc-root]/process/` and `[sdlc-root]/knowledge/` (as extraction targets for shared content)
- **Complements:** `sdlc-develop-agent` (agents vs skills)
- **Does NOT replace:** Direct editing of project-owned skills (this adds convention enforcement, migration protection, and DRY discipline)
- **DRY discipline:** CREATE step 1.5 and MODIFY step M1.5 enforce overlap scans before any write. Extraction targets, in priority order: `[sdlc-root]/process/{topic}.md` (universal protocols), `[sdlc-root]/knowledge/{domain}/{topic}.yaml` (domain rules), per-skill `references/` (single-skill detail). Inline duplication requires a documented justification in the skill's `DRY notes`.
