# Retrofit Mode

For existing projects with code and documentation that need z-sdlc integrated.

## Phase R1: Discovery

1. Scan the project for existing documentation (markdown files, docs/, design/, specs/)
2. Categorize each document:

| Category | Indicators |
|----------|------------|
| **Spec** | "Specification", "Design", requirements, API definitions |
| **Planning** | "Instructions", "How to", implementation steps |
| **Result** | "COMPLETE", "DONE", completion records |
| **Roadmap** | Future plans, phases, milestones |
| **Reference** | API docs, architecture overview, README |
| **Issue** | "BLOCKED", problems, open questions |

3. Group related documents into logical concepts (domains/features)
4. Check for existing agents in `.claude/agents/`

## Phase R2: Proposal

1. Present categorization table to CD (files found, proposed type, proposed concept)
2. Propose concept groupings for the chronicle
3. Propose which existing docs map to which SDLC artifact types
4. Get CD approval via `AskUserQuestion` before acting

**Gate:** CD must approve the proposal before Phase R3.

## Phase R3: Implementation

1. Install files from z-sdlc source (same as Greenfield Phase 1)
2. Augment existing CLAUDE.md with SDLC process section (do NOT overwrite)
3. Create concept directories in `docs/chronicle/` based on approved proposal
4. Move/copy existing docs to appropriate locations
5. Backfill `docs/_index.md` with entries for substantial completed work
6. Create domain agents (same as Greenfield Phase 4 — via `/sdlc-develop-agent`)
7. Wire agent-context map (same as Greenfield Phase 5)
8. Seed knowledge and disciplines (same as Greenfield Phases 6–8, informed by existing codebase patterns)
9. Verify plugin readiness, assess initial maturity levels, and offer the verify command's runbook (same as Greenfield Phases 9, 9a and 9b)

## Phase R4: Verification

Same as Greenfield Phases 10–11 (verification checklist + compliance audit), with these added to the checklist, then Phase 12 (cleanup, and the runbook offers):

```
[ ] Existing documents categorized and moved to SDLC locations
[ ] Chronicle concept directories created with _index.md files
[ ] Deliverable catalog backfilled with completed work
[ ] Existing CLAUDE.md augmented (not replaced)
```
