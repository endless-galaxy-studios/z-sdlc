# DNN: Feature Name — Implementation Instructions

**Spec:** `dNN_feature_name_spec.md`
**Created:** YYYY-MM-DD

---

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

---

## Overview

[Brief summary of what will be implemented]

---

## Component Impact

| Component / Package | Changes |
|--------------------|---------|
| [name] | [What changes] |
| [name] | [What changes] |

## Interface / Adapter Changes

- [New methods, new fields, or "None — no interface changes"]

## Migration Required

- [ ] No migration needed
- [ ] Database migration: [describe]
- [ ] Storage migration: [describe]

---

## Prerequisites

- [ ] Prerequisite 1 is in place
- [ ] Prerequisite 2 is available

---

## Implementation Steps

### Step 1: [Name]

**Files:** `path/to/file.ext`

[Detailed instructions]

```language
// Code example or pattern to follow
```

### Step 2: [Name]

**Files:** `path/to/file.ext`

[Detailed instructions]

### Gate G1: [production work between steps; delete when the plan touches no production]

> Deploys, migrations on a shared database, restarts, backups and live checks happen only in gates, never in a step. Gates don't count toward the 7-phase limit, and the plan's last item is always a step. Rules: `[sdlc-root]/process/production-gates.md`.

**After:** Step 2. **Changes production:** yes | no (read-only).
**Why here:** [why this happens between these steps]
**Preconditions:** [what must be true first]
**Runbook:**
- [ ] [each step, with the exact command or operation, in order]
**Report back:** `field`: [what it is and which step uses it]
**Rollback:** [how to undo it, or "none: read-only"]

[A `gate-ops` block naming catalog operations, only when the project has an operations catalog.]

### Step 3: [Name]

[Continue as needed]

---

## Phase Dependencies

| Phase | Depends On | Agent | Can Parallel With |
|-------|-----------|-------|-------------------|
| 1 | — | [agent] | — |
| 2 | Phase 1 | [agent] | Phase 3 |
| G1 | Phase 2 | CD (or the production runner) | — |
| 3 | G1 | [agent] | — |

Depends On may also name another deliverable (`Phase 5, D11a`): that phase waits until the deliverable is Complete. List the deliverable in the catalog row's `Depends on` too (`[sdlc-root]/process/deliverable_lifecycle.md` § Dependencies). A gate is a row of its own; a phase that needs its results depends on it.

## Approach Comparison (Medium/Complex only)

| Approach | Description | Key Tradeoff | Selected? |
|----------|-------------|-------------|-----------|
| A: [name] | [2 sentences] | [tradeoff] | ✅ / ❌ + why |
| B: [name] | [2 sentences] | [tradeoff] | ✅ / ❌ + why |

## Agent Skill Loading

| Agent | Load These Skills |
|-------|------------------|
| [agent-name] | [skills to load, e.g., WebSearch if researching external patterns] |

---

## Testing Strategy

<!-- Consider tests-first: if acceptance criteria are clear, write tests as an early
     implementation phase so subsequent phases implement code to pass them. This is
     especially valuable when the spec defines precise expected behavior. -->

### Test Phase Ordering
- [ ] **Tests-first** — Tests written as Phase 1 (or early phase), implementation follows to pass them
- [ ] **Tests-after** — Implementation first, tests written after to verify behavior

### Manual Testing
1. [Test step 1]
2. [Test step 2]

### Automated Tests
- [ ] Unit tests in `path/to/tests`
- [ ] Integration tests in `path/to/tests`

---

## Verification Checklist

- [ ] All implementation steps complete
- [ ] Manual testing passes
- [ ] Automated tests pass
- [ ] No regressions introduced

---

## Spec Deviations

[List any intentional divergences from the spec. If the plan implements the spec exactly, write "None — plan matches spec." If the plan drops, adds, or modifies requirements, declare each deviation with a reason.]

- **[Deviation]**: [What changed from spec and why]

---

## Notes

[Any additional context, gotchas, or references]
