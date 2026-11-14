# Z-SDLC Lite Bootstrap

A **minimal SDLC starter kit** for teams new to the framework. Installs 3 agents, 2 skills, a small knowledge/discipline store, and the core manager-rule discipline — enough to feel the benefit, nothing that requires ceremony.

Say **"Bootstrap SDLC Lite"** or **"Initialize SDLC Lite"** in Claude Code.

## What this installs

| Piece | What it gives you |
|-------|-------------------|
| 3 agents | `software-architect`, `fullstack-developer`, `code-reviewer` |
| 2 skills | `/sdlc-lite-plan` (plan-then-approve), `/sdlc-lite-execute` (dispatch + review loop) |
| Knowledge store | 3 starter files under `ops/sdlc-lite/knowledge/` — architecture, coding, testing — wired to the 3 agents |
| Disciplines | 3 parking lots under `ops/sdlc-lite/disciplines/` — architecture, coding, testing |
| Templates | Lite plan + lite result templates |
| Changelog | `ops/sdlc-lite/sdlc_changelog.md` — the memory spine |
| Deliverable catalog | `docs/_index.md` — D-001, D-002… IDs for plans and results |
| Process docs | `manager-rule.md`, `finding-classification.md`, `review-fix-loop.md` — the review/triage spine, kept intact |
| CLAUDE.md merge | A "SDLC-Lite" section appended to `CLAUDE.md` with commit format, invocation rules, and manager rule reference |

## What this does NOT install

Everything else. If you later want chronicles, playbooks, full spec/plan/execute with specs, test skills, audit skills, research/ingest, the `sdlc-review-code` review loop, accessibility/security/performance agents, or the full agent-context-map — run the full `Bootstrap SDLC` afterwards. See **Graduation Path** at the bottom.

## Source

```
repo: https://github.com/endless-galaxy-studios/z-sdlc
branch: master
```

---

## Bootstrap Instructions

When the user asks to bootstrap SDLC Lite, follow these steps in order. **Use `AskUserQuestion` for every prompt to the user.** Run the mechanical steps without stopping to ask for confirmation; pause only for the explicit user-input steps below (Steps 2, 3 and 9).

### Step 1: Fetch the framework (temp clone)

```bash
git clone --depth 1 https://github.com/endless-galaxy-studios/z-sdlc.git /tmp/z-sdlc-lite-bootstrap
```

Verify `/tmp/z-sdlc-lite-bootstrap/templates/sdlc_lite_plan_template.md` exists. If the clone fails, stop and report the error — do not delete `BOOTSTRAP-LITE.md`, the user will retry.

Create the lite install root in the project:

```bash
mkdir -p ops/sdlc-lite/{process,knowledge,disciplines,templates}
mkdir -p .claude/{agents,skills}
mkdir -p docs/current_work/sdlc-lite
```

### Step 2: Stack scan + user input

Before creating agents, scan the project to infer the stack. Read whichever of these exist:

- `package.json` (root `dependencies`, `devDependencies`, `engines`)
- `pyproject.toml`, `requirements.txt`, `Pipfile`
- `pom.xml`, `build.gradle`, `build.gradle.kts`
- `Gemfile`, `go.mod`, `Cargo.toml`
- `tsconfig.json` (for TypeScript confirmation)
- `docker-compose.yml`, `Dockerfile`
- `.nvmrc`, `.ruby-version`, `.python-version`

Synthesize a stack summary (≤8 bullets) covering: language(s), primary framework(s), database(s), test runner(s), build tool, deploy target if inferable. Example:

```
Detected stack:
- TypeScript 5.4 + Node 20
- Next.js 14 (App Router)
- Postgres via Prisma 5
- Vitest + Playwright
- Docker / docker-compose
- Deploy: unclear (no CI config found)
```

Present the summary, then ask **once** using `AskUserQuestion`:

> **Anything to add or correct about your stack, conventions, or agent scope?**
> Examples: specific frameworks the agents should know, code style rules, domain boundaries (e.g. "fullstack also owns infra/Terraform"), deploy target, libraries worth flagging.

Record the user's answer verbatim — it feeds every agent's scope, tool list, and core principles.

### Step 3: Create the 3 agents (lite orchestration of `/sdlc-develop-agent`)

Read `/tmp/z-sdlc-lite-bootstrap/templates/agent-template.md` as the structural reference. For each of the 3 agents below, generate the frontmatter + body using the detected stack + user input from Step 2, then write to `.claude/agents/{name}.md`.

**Simplifications vs. full `/sdlc-develop-agent`:**
- No domain-conflict check across existing agents (lite roster is fixed)
- No `agent-context-map` round-trip (handled in Step 5 as one shot)
- No `sdlc-reviewer` quality gate (not installed in lite)
- No `sdlc-plan` / `agent-selection.yaml` wiring (those files don't exist in lite)

**Frontmatter rules (same as full):**
- `description` MUST be a double-quoted single-line string using `\\n` for newlines — single `\n` breaks the parser
- Include 1 `<example>` block (Context/user/assistant, no `<commentary>`), or 2 when another lite agent's domain could be confused with this one
- Include the boundary sentence ("Do NOT use for: X — use Y instead")

#### 3a. `software-architect`

| Field | Value |
|-------|-------|
| `name` | `software-architect` |
| `model` | `opus` |
| `tools` | `Read, Glob, Grep, WebFetch` |
| `color` | `cyan` |
| `memory` | (omit — stateless) |

**Scope statement:**
> You own system-level design: component boundaries, data flow between services/modules, integration patterns, non-functional concerns (performance, scalability, observability). You do not write application code — that is `fullstack-developer`'s domain. You do not review line-level code quality — that is `code-reviewer`'s domain. Your output is decisions, diagrams-in-prose, and tradeoff analyses the builder can execute against.

**Core principles (generate 3, adapting to detected stack):**
1. Consistency over preference — follow existing patterns unless there's a concrete reason to diverge
2. Boundaries before implementations — name what belongs where before anyone writes code
3. Cite precedent — when a pattern exists in the codebase, reference it explicitly

**Anti-rationalization table (6 entries, standard set):**
- "I'll sketch the implementation too" → Stop at boundaries. Handoff to fullstack.
- "This is just a small architectural nudge" → No size exception. Still a decision that needs rationale.
- "Everyone knows this pattern" → Cite it anyway. New contributors don't.
- "I'll pick the modern option" → Pick the option that fits the codebase. Modern is not an argument.
- "The tradeoff is obvious" → Write it down. Obvious to you is not obvious to the executing agent.
- "I don't need to read the existing code" → Architecture without code reading is hallucination.

#### 3b. `fullstack-developer`

| Field | Value |
|-------|-------|
| `name` | `fullstack-developer` |
| `model` | `sonnet` |
| `tools` | `Read, Write, Edit, Bash, Glob, Grep` |
| `color` | `green` |
| `memory` | (omit — stateless) |

**Scope statement:**
> You own application code across the web stack: backend services/APIs, frontend components, UI/UX implementation, database schema + queries. You do not make system-level architectural decisions (component boundaries, integration patterns) — defer to `software-architect`. You do not review your own code for quality — `code-reviewer` handles that. Your domain expertise covers **[inject the detected frontend framework, backend framework, database, and test runner from Step 2]**, plus any additional tech the user mentioned.

**Core principles (generate 4, adapting to detected stack):**
1. Read before you write — find the existing pattern in the codebase; follow it
2. Types first — derive implementations from types, not the other way around (if TypeScript/typed language detected)
3. Tests co-located with the change — new behavior ships with new tests
4. No silent scope drift — if you touch a file the plan didn't specify, log it in your handoff

**Anti-rationalization table (6 entries):**
- "I'll refactor this while I'm here" → Out of scope. Log it as a follow-up.
- "This is a quick one-liner, no test needed" → Every behavioral change ships with a test.
- "The plan said X but Y is better" → Raise it, don't silently substitute.
- "Stubs are fine for now" → Stubs that build clean are the hardest defects to catch. No stubs in the final phase.
- "I'll handle the migration myself" → DB schema changes get flagged, not buried.
- "Library version doesn't matter" → Verify APIs via Context7 before writing integration code.

#### 3c. `code-reviewer`

| Field | Value |
|-------|-------|
| `name` | `code-reviewer` |
| `model` | `sonnet` |
| `tools` | `Read, Glob, Grep, Bash` |
| `color` | `red` |
| `memory` | (omit — stateless) |

**Scope statement:**
> You review code changes for quality, correctness, security, and maintainability. You do not write or fix code — findings go back to the agent that wrote the code. You do not make architectural decisions — flag architectural concerns to `software-architect`. Your output is a **findings list** with severity (critical / major / minor) and specific file:line references.

**Core principles (generate 4):**
1. Every finding cites a file and line — vague findings are not actionable
2. Severity is evidence-based — "critical" means "this breaks in production" or "this is exploitable"
3. Separate code quality from plan compliance — reviewers check both: is the code well-written AND did the agent deliver what was specified
4. Pre-existing issues are flagged as `PRE-EXISTING`, not demanded as fixes

**Anti-rationalization table (6 entries):**
- "I'll fix this myself instead of flagging it" → You don't write code. Flag it.
- "This is ugly but it works" → Then it's a minor finding, not no finding.
- "I'll skip security — nothing obvious" → Run the OWASP-top-10 mental pass anyway.
- "The agent obviously meant X" → If the code says Y, the finding is Y.
- "Build passes, I'm done" → Build passing is a precondition, not a conclusion.
- "I'll bundle all findings as critical" → Severity inflation trains future agents to ignore you.

Write all 3 files. Confirm each exists before moving on.

### Step 4: Install the two lite skills (strip dead references in place)

The framework's `skills/sdlc-lite-plan/` and `skills/sdlc-lite-execute/` are already "lite" relative to the full SDLC, but they reference a handful of files this bootstrap doesn't install (chronicle, playbooks, `agent-selection.yaml`). Copy them in, then edit out the dead references directly — this is mechanical text manipulation during installation, not an SDLC work session, so no agent dispatch.

```bash
cp -r /tmp/z-sdlc-lite-bootstrap/skills/sdlc-lite-plan .claude/skills/
cp -r /tmp/z-sdlc-lite-bootstrap/skills/sdlc-lite-execute .claude/skills/
```

**Edits to apply to both `.claude/skills/sdlc-lite-plan/SKILL.md` and `.claude/skills/sdlc-lite-execute/SKILL.md`:**

1. **Remove entirely** — sections, paragraphs, or bullets that only exist to reference files not installed in lite:
   - Any paragraph or bullet mentioning `[sdlc-root]/playbooks/` or `playbooks/` lookups
   - The `Infrastructure domain trigger conditions` paragraph referencing `[sdlc-root]/process/agent-selection.yaml`
   - The `CHRONICLE-CONTEXT scan` paragraph and the corresponding verbose `CHRONICLE-CONTEXT` block
   - Any reference to `[sdlc-root]/process/knowledge-routing.md` or the phrasing contract (lite has no adapters)

2. **Simplify in place** — replace the reference with a one-line inline equivalent:
   - `[sdlc-root]/process/deliverable_lifecycle.md` → "update the deliverable's Status in `docs/_index.md` (`In Progress` at start, `Complete` at final commit)"
   - `[sdlc-root]/process/collaboration_model.md` → "all user questions use `AskUserQuestion`"
   - `[sdlc-root]/process/discipline_capture.md` structured gap detection → "scan the work for cross-discipline insights; append any you find to the relevant `ops/sdlc-lite/disciplines/*.md` parking lot using the format `- **[YYYY-MM-DD] [context]**: [insight]. [NEEDS VALIDATION]`. Skip if nothing surfaced." (The full structured-gap-detection protocol — comparing agent knowledge loads against findings to detect `MISSING_KNOWLEDGE` / `UNMAPPED_KNOWLEDGE` / `STALE_KNOWLEDGE` / `CROSS_DOMAIN_FRICTION` / `RESURFACING_PATTERN` gaps — needs the full knowledge store + handoff protocol to produce meaningful signal. Lite keeps only the freeform scan.)

3. **Keep as-is, with path rewrites** — these references point at files that ARE installed in Step 7:
   - `[sdlc-root]/process/manager-rule.md` → `ops/sdlc-lite/process/manager-rule.md`
   - `[sdlc-root]/process/finding-classification.md` → `ops/sdlc-lite/process/finding-classification.md`
   - `[sdlc-root]/process/review-fix-loop.md` → `ops/sdlc-lite/process/review-fix-loop.md`
   - `[sdlc-root]/templates/sdlc_lite_plan_template.md` → `ops/sdlc-lite/templates/sdlc_lite_plan_template.md`
   - `[sdlc-root]/templates/sdlc_lite_result_template.md` → `ops/sdlc-lite/templates/sdlc_lite_result_template.md`
   - `[sdlc-root]/knowledge/agent-context-map.yaml` → `ops/sdlc-lite/knowledge/agent-context-map.yaml`

4. **Keep verbatim** — core workflow the lite install depends on:
   - Writer-writes-saves pattern (Manager Rule consequence — never editorialize this)
   - PRE-GATE / POST-GATE compact forms and their verbose fall-through triggers
   - Review-Fix loop (cites `ops/sdlc-lite/process/review-fix-loop.md`)
   - Finding classification (cites `ops/sdlc-lite/process/finding-classification.md`)
   - Worker Agent Reviews section + append procedure
   - Plan + result file paths (`docs/current_work/sdlc-lite/dNN_{slug}_plan.md`, `_result.md`)
   - Deliverable ID claim from `docs/_index.md`
   - Completion Report structure at the end of execution
   - Context7 library verification instructions

5. **Global path rewrite** — after the targeted edits, grep both files for any remaining `[sdlc-root]` and replace with `ops/sdlc-lite`. No `[sdlc-root]` placeholders should remain in lite skill bodies.

Verification:

```bash
! grep -n '\[sdlc-root\]\|chronicle\|playbooks\|agent-selection\.yaml\|knowledge-routing\.md\|collaboration_model\.md\|deliverable_lifecycle\.md' .claude/skills/sdlc-lite-plan/SKILL.md .claude/skills/sdlc-lite-execute/SKILL.md && echo "Strip OK"
```

### Step 5: Install knowledge store + disciplines + agent-context-map

**Knowledge store** — copy a minimum viable set:

```bash
# Architecture (system design patterns the architect will read)
mkdir -p ops/sdlc-lite/knowledge/architecture
cp /tmp/z-sdlc-lite-bootstrap/knowledge/architecture/technology-patterns.yaml ops/sdlc-lite/knowledge/architecture/
cp /tmp/z-sdlc-lite-bootstrap/knowledge/architecture/domain-boundary-gotchas.yaml ops/sdlc-lite/knowledge/architecture/
cp /tmp/z-sdlc-lite-bootstrap/knowledge/architecture/api-design-methodology.yaml ops/sdlc-lite/knowledge/architecture/

# Coding (quality principles + language patterns for fullstack)
mkdir -p ops/sdlc-lite/knowledge/coding
cp /tmp/z-sdlc-lite-bootstrap/knowledge/coding/code-quality-principles.yaml ops/sdlc-lite/knowledge/coding/
# Copy typescript-patterns.yaml ONLY if TypeScript detected in Step 2
# Otherwise skip — the store stays TypeScript-free rather than misleading

# Testing (gotchas + tool patterns for code-reviewer)
mkdir -p ops/sdlc-lite/knowledge/testing
cp /tmp/z-sdlc-lite-bootstrap/knowledge/testing/gotchas.yaml ops/sdlc-lite/knowledge/testing/
cp /tmp/z-sdlc-lite-bootstrap/knowledge/testing/testing-paradigm.yaml ops/sdlc-lite/knowledge/testing/
```

**Rewrite paths inside copied YAML** — each copied file may reference `[sdlc-root]/...` internally. Grep each file and replace `[sdlc-root]` → `ops/sdlc-lite`. Verify:

```bash
grep -l '\[sdlc-root\]' ops/sdlc-lite/knowledge/**/*.yaml
# Should return nothing after the rewrite
```

**Disciplines** — create 3 parking lots:

Write each of these 3 files with content derived from `/tmp/z-sdlc-lite-bootstrap/disciplines/README.md` § "How to Use" (the parking-lot pattern, triage markers, freeform entry format). Do not copy the full README — synthesize a 30-40 line parking lot file per discipline:

- `ops/sdlc-lite/disciplines/architecture.md`
- `ops/sdlc-lite/disciplines/coding.md`
- `ops/sdlc-lite/disciplines/testing.md`

Each file has:
1. A one-sentence scope statement
2. A triage-marker table (`[NEEDS VALIDATION]`, `[READY TO PROMOTE]`, `[DEFERRED]`)
3. A `## Parking Lot` heading with one seeded example entry showing the format
4. Entry format: `- **[YYYY-MM-DD] [context]**: [insight]. [triage marker]`

**Agent-context-map** — write `ops/sdlc-lite/knowledge/agent-context-map.yaml`:

```yaml
# Maps each of the 3 lite agents to the knowledge files they should consult
# before starting substantive work. Skills read this file before dispatch
# and inject the mapped files into the agent's prompt.

mappings:
  software-architect:
    - "ops/sdlc-lite/knowledge/architecture/technology-patterns.yaml"
    - "ops/sdlc-lite/knowledge/architecture/domain-boundary-gotchas.yaml"
    - "ops/sdlc-lite/knowledge/architecture/api-design-methodology.yaml"

  fullstack-developer:
    - "ops/sdlc-lite/knowledge/coding/code-quality-principles.yaml"
    - "ops/sdlc-lite/knowledge/architecture/technology-patterns.yaml"
    # Add typescript-patterns.yaml here if TypeScript was detected and copied

  code-reviewer:
    - "ops/sdlc-lite/knowledge/coding/code-quality-principles.yaml"
    - "ops/sdlc-lite/knowledge/testing/gotchas.yaml"
    - "ops/sdlc-lite/knowledge/testing/testing-paradigm.yaml"
    - "ops/sdlc-lite/knowledge/architecture/domain-boundary-gotchas.yaml"
```

Add a `## Knowledge Context` section to each of the 3 agent files (written in Step 3) pointing them at this map:

```markdown
## Knowledge Context

Before starting substantive work, consult `ops/sdlc-lite/knowledge/agent-context-map.yaml` and find your entry. Read the mapped knowledge files — they contain reusable patterns and gotchas relevant to your domain.
```

### Step 6: Install templates

```bash
cp /tmp/z-sdlc-lite-bootstrap/templates/sdlc_lite_plan_template.md ops/sdlc-lite/templates/
cp /tmp/z-sdlc-lite-bootstrap/templates/sdlc_lite_result_template.md ops/sdlc-lite/templates/
```

### Step 7: Install core process + memory files

**Core process docs** — copy verbatim, then rewrite `[sdlc-root]` → `ops/sdlc-lite` inside each file:

```bash
cp /tmp/z-sdlc-lite-bootstrap/process/manager-rule.md ops/sdlc-lite/process/manager-rule.md
cp /tmp/z-sdlc-lite-bootstrap/process/finding-classification.md ops/sdlc-lite/process/finding-classification.md
cp /tmp/z-sdlc-lite-bootstrap/process/review-fix-loop.md ops/sdlc-lite/process/review-fix-loop.md
```

These are the spine of the review/triage half of the SDLC — kept intact in lite (not summarized inline in the skills). After copying, grep each file for `[sdlc-root]` and replace with `ops/sdlc-lite`. Verify:

```bash
! grep -l '\[sdlc-root\]' ops/sdlc-lite/process/*.md && echo "Process doc path rewrites OK"
```

**Changelog** — create `ops/sdlc-lite/sdlc_changelog.md`:

```markdown
# SDLC-Lite Changelog

Append-only log of process + deliverable changes. **One entry per change**, same commit as the work.

## Format

```
## [YYYY-MM-DD] [type]: [short title]

[1-2 sentences on what changed and why]

- Files: `path/one`, `path/two`
- Deliverable: D-NNN (if applicable)
```

**Types:** `bootstrap`, `deliverable`, `skill`, `agent`, `knowledge`, `discipline`, `process`, `fix`

---

## [TODAY'S-DATE] bootstrap: SDLC-Lite installed

Initial lite bootstrap. 3 agents (software-architect, fullstack-developer, code-reviewer), 2 skills (/sdlc-lite-plan, /sdlc-lite-execute), starter knowledge store, 3 discipline parking lots, manager-rule, deliverable catalog.

- Files: `.claude/agents/*`, `.claude/skills/sdlc-lite-*`, `ops/sdlc-lite/**`, `docs/_index.md`
- Deliverable: n/a (bootstrap)
```

Fill in today's date.

**Deliverable catalog** — create `docs/_index.md`:

```markdown
# Deliverable Catalog

Next ID: **D-001**

| ID | Title | Status | Tier | Plan | Result |
|----|-------|--------|------|------|--------|
| —  | —     | —      | —    | —    | —      |

## States

`In Progress` → `Complete` (or `Abandoned`)

## Tiers

- `lite` — plan + result, no spec
- (full SDLC tiers appear here if you later upgrade via `Bootstrap SDLC`)

## How to use

1. `/sdlc-lite-plan` claims the next ID, increments the counter, appends a row with status `In Progress`
2. Plan file: `docs/current_work/sdlc-lite/dNNN_{slug}_plan.md`
3. Result file: `docs/current_work/sdlc-lite/dNNN_{slug}_result.md` (produced by `/sdlc-lite-execute`)
4. On completion: update Status to `Complete`, move both files to `docs/current_work/sdlc-lite/completed/`
```

### Step 8: Merge SDLC-Lite into CLAUDE.md

The single most important file. Without this block, the agent doesn't know when to invoke lite skills, what the commit format is, or that the Manager Rule applies.

**Preserve existing `CLAUDE.md`.** Append (do not overwrite):

```markdown

---

# SDLC-Lite

This project uses the z-sdlc **lite** toolkit — a minimal planning/execution/review loop. See `ops/sdlc-lite/` for the installed content.

## When to invoke

| Situation | Action |
|-----------|--------|
| Trivial change (typo, config bump, single-line fix) | Just do it |
| Moderate complexity (2-5 files, cross-domain, non-obvious approach) | `/sdlc-lite-plan` → approve → `/sdlc-lite-execute` |
| New feature, new integration, architectural change | Consider upgrading to full SDLC — see `ops/sdlc-lite/GRADUATION.md` |
| Just need a second opinion on a design | Dispatch `software-architect` directly |
| Code review before commit | Dispatch `code-reviewer` directly |

Complexity is the trigger, not file count. A 2-file change that touches DB + API warrants a plan. A 10-file rename might not.

## The Manager Rule

When any skill that dispatches agents is active, **you (the assistant) dispatch domain agents by default**. You may self-apply a change only when delegation would cost more than the change itself (in tokens or main-context growth) and the change is small, mechanical, and needs no new context — and every self-applied change is still reviewed by the relevant agent before commit. No complexity exception. See `ops/sdlc-lite/process/manager-rule.md` for the canonical definition.

## The 3 agents

| Agent | Owns | Does not touch |
|-------|------|----------------|
| `software-architect` | System design, boundaries, integration patterns, non-functional concerns | Application code, line-level review |
| `fullstack-developer` | All application code — backend, frontend, UI/UX, DB | System-level decisions, reviewing own code |
| `code-reviewer` | Quality / correctness / security / maintainability findings | Writing or fixing code |

All 3 consult `ops/sdlc-lite/knowledge/agent-context-map.yaml` before starting substantive work.

## Commit format

```
{type}[{deliverable_id}]({scope}): {description}

{optional body}

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`, `perf`, `ci`, `sdlc`

**Examples:**
- `feat[D-001](auth): add session refresh endpoint`
- `fix[D-002](ui): correct modal focus trap`
- `sdlc: add error-handling insight to coding discipline`

Work commits include all related artifacts — code, tests, plan/result docs, discipline entries, changelog update — in **one commit**. Never a separate "docs" commit for artifacts that belong with the work.

## Changelog rule

Every process-file change (skill edit, agent edit, knowledge addition, discipline entry promoted) updates `ops/sdlc-lite/sdlc_changelog.md` **in the same commit**. If the user has to ask for the changelog update, it was already too late.

## Discipline capture (freeform)

During any work session, if you encounter an insight that belongs to a discipline other than your current focus (a testing gotcha surfaced during implementation, a design issue surfaced during architecture):

1. Append a line to the relevant `ops/sdlc-lite/disciplines/*.md` parking lot under `## Parking Lot`
2. Format: `- **[YYYY-MM-DD] [context]**: [insight]. [NEEDS VALIDATION]`
3. Keep working

At planning boundaries, triage unmarked entries → `[NEEDS VALIDATION]`, `[READY TO PROMOTE]`, or `[DEFERRED]`.
```

Append this block to `CLAUDE.md`. If `CLAUDE.md` doesn't exist, create it with just this block (prefixed with `# <Project Name>` — infer from the repo root directory name).

### Step 9: Ask about a custom skill (optional orchestration)

Use `AskUserQuestion`:

> **Do you want to create a custom skill now?**
> Examples: a project-specific review checklist, a bug-report-to-plan converter, a release-notes generator, a domain-specific refactor flow.
>
> Options: (1) Yes — walk me through it, (2) No — maybe later.

If the user answers **Yes**, run the following lite orchestration (a stripped-down `/sdlc-develop-skill`):

1. **Purpose** — `AskUserQuestion`: "In one sentence, what does this skill do? What triggers should activate it (natural language phrases)? What should NOT trigger it?"

2. **Name** — propose `{verb}-{noun}` (e.g., `review-release-notes`, not `release-notes-reviewer`). Confirm with the user.

3. **Type** — infer from purpose:
   - Dispatches agents with a review loop → **orchestration**
   - Step-by-step procedure → **utility**
   - Open-ended iterative flow → **exploration**
   - If unclear, ask.

4. **Scaffold** — write `.claude/skills/{name}/SKILL.md` with:
   - Single-line `description` using `>` folded scalar, with explicit trigger phrases and anti-triggers
   - Numbered `### N. Step Name` headers (3-6 steps)
   - If orchestration: a `## Manager Rule` section pointing at `ops/sdlc-lite/process/manager-rule.md`
   - A `## Red Flags` table with 4-6 skill-specific entries (pair every "don't do X" with the correct replacement inline — never show an anti-pattern without its replacement)
   - A `## Integration` section (`Feeds into`, `Uses`, `Complements`, `Does NOT replace`)
   - Target 800-1,500 words. Lite skills are readable.

5. **Skip these from full `/sdlc-develop-skill`:** DRY audit across sibling skills (too heavy for 2 skills), phrasing-contract compliance (no adapters), `sdlc-reviewer` quality gate (not installed), PROJECT-SECTION markers (no migration coming — direct edits are safe in lite).

6. **Changelog entry** — append to `ops/sdlc-lite/sdlc_changelog.md`:
   ```
   ## [YYYY-MM-DD] skill: add /{name}

   [One sentence on what it does.]

   - Files: `.claude/skills/{name}/SKILL.md`
   ```

7. **Offer another** — `AskUserQuestion`: "Create another skill, or done?"

If the user answers **No**, skip to Step 10.

### Step 10: Verification

Run these checks. Any failure: stop, report to user, **do not delete `BOOTSTRAP-LITE.md`**.

```bash
# Agents present
ls .claude/agents/software-architect.md .claude/agents/fullstack-developer.md .claude/agents/code-reviewer.md

# Skills present
ls .claude/skills/sdlc-lite-plan/SKILL.md .claude/skills/sdlc-lite-execute/SKILL.md

# Knowledge + disciplines + context map
ls ops/sdlc-lite/knowledge/agent-context-map.yaml
ls ops/sdlc-lite/disciplines/architecture.md ops/sdlc-lite/disciplines/coding.md ops/sdlc-lite/disciplines/testing.md

# Templates + process docs + changelog + catalog
ls ops/sdlc-lite/templates/sdlc_lite_plan_template.md ops/sdlc-lite/templates/sdlc_lite_result_template.md
ls ops/sdlc-lite/process/manager-rule.md ops/sdlc-lite/process/finding-classification.md ops/sdlc-lite/process/review-fix-loop.md
ls ops/sdlc-lite/sdlc_changelog.md
ls docs/_index.md

# CLAUDE.md has the SDLC-Lite section
grep -q "^# SDLC-Lite$" CLAUDE.md && echo "CLAUDE.md merge OK"

# No stale [sdlc-root] references leaked in
! grep -rn '\[sdlc-root\]' ops/sdlc-lite/ .claude/skills/sdlc-lite-*/ .claude/agents/ && echo "Path rewrites OK"
```

Present a one-page summary to the user: files created, next-step suggestion ("try `/sdlc-lite-plan` on your next 2-5 file change").

### Step 11: Graduation note

Write `ops/sdlc-lite/GRADUATION.md`:

```markdown
# Graduating from SDLC-Lite to Full SDLC

Lite gives you: 3 agents, plan/execute loop, starter knowledge store, 3 discipline parking lots, manager rule, changelog, deliverable catalog.

Full SDLC adds:
- **Specs** — `sdlc-plan` writes a spec before the plan; lite skips specs entirely
- **More agents** — sdet, accessibility-auditor, security-engineer, performance-engineer, debug-specialist, db-engineer, etc. (see full `knowledge/agent-context-map.yaml`)
- **Review skill** — `/sdlc-review-code` — review-and-fix loops over git ranges or uncommitted changes
- **Test skills** — `/sdlc-tests-create`, `/sdlc-tests-run` — structured test authoring and verification
- **Audit skill** — `/sdlc-audit` — compliance + improvement audits of the framework and your sessions
- **Research/ingest** — `/sdlc-research`, `/sdlc-ingest` — pull external knowledge into the store
- **Chronicle** — `docs/chronicle/` — concept-level memory that persists across deliverables
- **Playbooks** — `ops/sdlc/playbooks/` — reusable agent-selection recipes for recurring task types
- **Discipline capture protocol** — structured gap detection (knowledge-loaded-vs-needed, cross-domain friction, resurfacing patterns)
- **Process docs** — deliverable lifecycle state machine, collaboration model, knowledge routing contract, review-fix loop, finding classification, agent-selection YAML
- **Full knowledge store** — ~60 YAML files across architecture, business-analysis, coding, data-modeling, design, dx, product-research, search, testing

**When to graduate:**
- You've shipped 3+ lite deliverables and want to retain more context between them (→ chronicle)
- Your team has grown and you need more specialist agents (→ full agent roster)
- You're starting to hit the same problems repeatedly (→ playbooks, discipline capture)
- Compliance / audit requirements make you want traceability (→ audit skill)

**How to graduate:**

Say **"Bootstrap SDLC"** or **"Initialize SDLC"** in Claude Code. `sdlc-initialize` detects the existing lite install via its Mode Detection step (looks for `ops/sdlc-lite/`) and runs **Phase 0-L (Lite Graduation)** before the normal install. Phase 0-L will:

1. Inventory the lite install and confirm via `AskUserQuestion`
2. Move `ops/sdlc-lite/*` content into the full layout at `ops/sdlc/*`
3. Rewrite `ops/sdlc-lite/` path references in your 3 lite agents, 2 lite skills, and `CLAUDE.md`
4. Remove the SDLC-Lite block from `CLAUDE.md` (Phase 2 adds the full SDLC-Lite-equivalent content)
5. Delete the now-empty `ops/sdlc-lite/` directory
6. Prepend a graduation entry to the migrated changelog
7. Fall through to Phase 1, which installs the full framework while skip-existing-files logic preserves every lite customization

**What's preserved:** your 3 agents (as-is), both lite skills (as-is, with paths rewritten), all discipline parking lot entries, the full changelog history, the deliverable catalog with every D-NNN entry, lite knowledge file customizations, and `docs/current_work/sdlc-lite/` as a historical record.

**What's added:** full agent roster (sdet, accessibility-auditor, security-engineer, etc. — CD chooses which), specs via `sdlc-plan`, the full skill library, chronicle, playbooks, remaining process docs, remaining knowledge stores, remaining discipline parking lots.
```

### Step 12: Cleanup (mandatory on success)

```bash
rm -rf /tmp/z-sdlc-lite-bootstrap
rm -f BOOTSTRAP-LITE.md .claude/BOOTSTRAP-LITE.md
```

Also add an entry to the changelog for the cleanup:

```markdown
## [YYYY-MM-DD] bootstrap: cleanup

Removed temp clone and BOOTSTRAP-LITE.md. Framework is self-contained.

- Files: (deletions)
```

---

## Notes for Claude Code

1. **`AskUserQuestion` for all prompts** — stack confirmation (Step 2), custom skill (Step 9), skill purpose (Step 9.1).
2. **No confirmation gates between mechanical steps** — Steps 1, 4, 5, 6, 7, 8, 10, 11, 12 run without pausing. Only the explicit user-input steps (2, 3 briefing, 9) prompt.
3. **Preserve existing files** — Never overwrite `CLAUDE.md`; always append. If `docs/_index.md` exists, merge carefully.
4. **If the user already has full z-sdlc installed** — stop at Step 1. Say: "Full SDLC is already installed at `ops/sdlc/`. SDLC-Lite is a subset of what you have — no action needed. Use `/sdlc-lite-plan` / `/sdlc-lite-execute` which are already available."
5. **Clean up on success** — remove `/tmp/z-sdlc-lite-bootstrap` AND `BOOTSTRAP-LITE.md`.
6. **Clean up on failure** — remove `/tmp/z-sdlc-lite-bootstrap` but **leave** `BOOTSTRAP-LITE.md` so the user can retry.
7. **The Manager Rule does not apply during the bootstrap itself.** Bootstrap is framework installation, not an SDLC work session. All steps here — including the skill-file strip in Step 4 and the YAML path rewrites in Step 5 — are mechanical text manipulation performed directly by Claude Code. The Manager Rule activates for the user's first real work session after the install is complete, at which point the lite skills enforce it.

---

## One-liner install

```bash
curl -fsSL https://raw.githubusercontent.com/endless-galaxy-studios/z-sdlc/master/BOOTSTRAP-LITE.md -o .claude/BOOTSTRAP-LITE.md
```

Then in Claude Code: **"Bootstrap SDLC Lite"**
