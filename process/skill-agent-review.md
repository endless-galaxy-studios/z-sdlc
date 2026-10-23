# Skill & Agent Review Methodology

Convention review checklist for SDLC skills and agents. Referenced by creation and enrichment skills during their quality gate steps. The `sdlc-reviewer` subagent performs the actual review — this doc defines what it checks.

## Skill Conventions

### Frontmatter
- `description` uses folded scalar (`>`) — not quoted strings or block scalar (`|`)
- Includes trigger phrases (`Triggers on "..."`)
- Includes anti-triggers (`Do NOT use for X — use Y.`)
- `name` matches the skill directory name

### Required Sections
- Title heading with 1-2 sentence summary
- Steps with numbered `### N. Step Name` headers
- `## Red Flags` table (5+ entries, `| Thought | Reality |` format)
- `## Integration` section (Feeds into, Uses, Complements, Does NOT replace)
- Mirrored blocks, verbatim inside their `MIRROR` markers: the headless stop rule in every skill (`[sdlc-root]/process/headless-mode.md` § Mirrored Stop Rule), and the matching review-loop block in every skill that runs a review loop (`[sdlc-root]/process/review-fix-loop.md` § Mirrored Critical-Steps Blocks)

A project's own verify skill (`.claude/skills/verify/`, written by `sdlc-develop-verify-skill`) is a lean recipe and is exempt from the frontmatter trigger phrases and the section requirements above; that skill's step 6 review checks it instead.

### Skill Type-Specific
- **Orchestration** skills reference `[sdlc-root]/process/manager-rule.md` and include agent selection criteria
- **Utility** skills define preconditions/inputs and output format
- **Exploration** skills include a user-controlled iteration mechanism and no hard gates

### Content Quality
- References correct agent names (not stale/renamed)
- File paths use `[sdlc-root]/...` (not bare `knowledge/`, `disciplines/`, etc.)
- SKILL.md body targets 1,500-3,000 words; overflow goes to `references/`

## Agent Conventions

### Frontmatter
- `description` is double-quoted single-line with `\\n` escapes (single `\n` in YAML double-quoted strings is a real newline — breaks the parser)
- Includes 1-2 `<example>` blocks as trigger mechanism, tiered by confusability: 1 if no confusable sibling agent exists, 2 (typical-use + seam) if one does. Never 3-4 — that was the previous default and is where most of the per-session description-token cost sat.
- NO `<commentary>` blocks inside examples — they restate the scope sentence or Do-NOT-use boundary already present in the same description; pure redundancy, not routing signal
- Includes a mandatory "Do NOT use for: X — use Y instead" boundary sentence — with examples capped at 2, this is the primary mechanism resolving overlap with adjacent agents, not optional prose
- `model`, `tools`, `color` fields present
- `name` field present

### Required Sections
- Scope statement (what the agent owns AND does not touch)
- Knowledge Context section referencing `[sdlc-root]/knowledge/agent-context-map.yaml`
- Communication Protocol (inter-agent handoff format)
- Core Principles (domain-specific, not generic)
- Workflow (3+ numbered steps)
- Anti-Rationalization Table (mandatory)
- Self-Verification Checklist (4-8 items covering distinct failure modes)

### Content Quality
- Principles are specific and actionable, not platitudes
- Anti-rationalization entries cover domain-specific shortcuts
- Agent doesn't reference child-project-only concepts from the source repo

## Review Severity Levels

- **Critical** — will break dispatching or violates a hard convention (missing frontmatter fields, wrong description format)
- **Major** — convention gap that degrades quality (missing anti-triggers, no Red Flags table, no Integration section)
- **Minor** — style or completeness improvement (generic principles, thin anti-rationalization table)
