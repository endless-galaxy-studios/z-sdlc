# SDLC-Lite Plan: [Title]

**Execute this plan using the `sdlc-lite-execute` skill.**

**Scope:** [1-2 sentences — what's changing and why]
**Files:** [List all files that will be created or modified]
**Agents:** [List assigned worker domain agents]

## Approval Brief

**[deliverable ID] plan, for your approval:** [what it will build, in plain words]

> For CD, who approves the plan from this section: the report CD reads when planning ends. Written last, after review, by the plan's author, as `[sdlc-root]/process/writing-for-cd.md` § Approval Briefs describes a plan's brief: about 550 words, or the plan variant of `[sdlc-root]/templates/pr_description_template.md` alone, in about 450, in a headless run. Every decision this plan leaves to CD appears under What you're approving. Execution follows the sections below, not this one. Delete this note when you fill the section.

### What you need to do
### The problem
### What changes for users
### What you're approving
### The phases
### Scope
### Risk
### Review focus
### How it will be verified
### How it works
### Learn the change

**Review:** [N] rounds; [what review changed in the plan, or: no changes]; [K] open minor findings, listed at the end of this plan.

## Phase Dependencies

| Phase | Depends On | Agent | Can Parallel With |
|-------|-----------|-------|-------------------|
| 1     | —         | agent | —                 |
| 2     | Phase 1   | agent | Phase 3           |

Depends On may also name another deliverable (`Phase 5, D11a`): that phase waits until the deliverable is Complete. List the deliverable in the catalog row's `Depends on` too (`[sdlc-root]/process/deliverable_lifecycle.md` § Dependencies). A production gate is a row of its own (`G1 | Phase 1 | CD | —`); a phase that needs its results depends on it.

## Phases

### Phase 1: [Name]
**Agent:** [assigned agent]
**Outcome:** [What must be true when this phase is done]
**Why:** [Why it matters]
**Guidance:** [Optional — approach hints, key files/functions, non-obvious context that helps the executing agent]

### Gate G1: [production work between phases; delete when the plan touches no production]
> Deploys, migrations on a shared database, restarts, backups and live checks happen only in gates, never in a phase. Gates don't count toward the 4-phase limit, and the last item is always a phase. Rules: `[sdlc-root]/process/production-gates.md`.

**After:** Phase 1. **Changes production:** yes | no (read-only).
**Why here:** [why this happens between these phases]
**Preconditions:** [what must be true first]
**Runbook:**
- [ ] [each step, with the exact command or operation, in order]
**Report back:** `field`: [what it is and which phase uses it]
**Rollback:** [how to undo it, or "none: read-only"]

### Phase 2: [Name]
...

## Spec Deviations

[List any intentional divergences from the spec. If the plan implements the spec exactly, write "None — plan matches spec." If the plan drops, adds, or modifies requirements, declare each deviation with a reason.]

- **[Deviation]**: [What changed from spec and why]

## Post-Execution Review
All completed work must be reviewed by all relevant worker domain agents.
All findings must be fixed by the most relevant domain agent.
Build must pass before work is considered done.
