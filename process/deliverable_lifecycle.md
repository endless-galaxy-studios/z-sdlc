# Deliverable Lifecycle

## States

```
[Draft] → [Ready] → [In Progress] → [Validated] → [Deployed] → [Complete] → [Archived]
                 ↘ [Blocked] ↗
```

### Draft
Spec exists but is incomplete or under review.
- File: `dNN_name_spec.md`
- Status marker in file: `**Status:** Draft`

### Ready
Spec is approved and has planning/instructions.
- Files: spec + planning + optional prompt
- Status marker: `**Status:** Ready`

### In Progress
Implementation is underway.
- CC is actively working on it
- Status marker: `**Status:** In Progress`

### Blocked
Work cannot proceed.
- File: `dNN_name_BLOCKED.md` in `issues/`
- Contains: what's blocked, why, what's needed

### Validated
Implementation passes all testing gates.
- Phase 1 (exploratory testing): all scenarios pass
- Phases 2-3 (test specs + test generation): test files created
- Phase 4 (test execution): all tests green
- Testing knowledge updated
- Status marker: `**Status:** Validated`

### Deployed
Code is live in staging/production and verified.
- Deployment completed per project deployment docs
- Post-deploy smoke tests pass (health checks, auth, key endpoints)
- Seed data verified if applicable
- Status marker: `**Status:** Deployed`

**Note:** CD may authorize early deployment for human review while tests run in parallel. In this case, the deliverable moves to Deployed before Validated, but cannot move to Complete until both gates pass.

### Complete
Implementation is finished, validated, and deployed.
- File: `dNN_name_result.md` in `results/`
- Includes: test results, deploy verification
- Status marker: `**Status:** Complete`

### Archived
Moved to chronicles for long-term reference.
- Files moved to `chronicle/` under the appropriate concept
- Removed from `current_work/`

---

## Transitions

### Draft → Ready
- Spec is reviewed and approved
- Planning document is written
- Optional: CC prompt is prepared

### Ready → In Progress
- CC begins implementation
- Or: human begins implementation

### In Progress → Validated
- Code compiles clean
- Exploratory testing passes (Phase 1)
- Test specs written (Phase 2)
- Tests generated and passing (Phases 3-4)
- Testing knowledge files updated
- CD iteration complete (for user-facing changes): CD has used the feature hands-on and confirmed that interaction models, control placement, breakpoint strategy, and overall flow meet product expectations. CD iteration may surface issues that formal review cannot — these are addressed before validation, not after.

### Validated → Deployed
- Prerequisite: Validated state reached (all tests green, CD iteration complete for UI work)
- Code deployed to target environment
- Post-deploy smoke tests pass

### Deployed → Complete
- Both Validated and Deployed states confirmed
- Result document created with full test + deploy outcomes

### In Progress → Blocked
- Obstacle encountered
- Issue document created
- Work pauses until resolved

### Blocked → In Progress
- Blocker resolved
- Issue document updated or removed
- Work resumes

### Complete → Archived
- Periodic chronicle organization
- Files moved to appropriate concept/step
- `_index.md` updated

---

## Dependencies

A deliverable that needs another one finished first records it where tools can read it. Prose alone doesn't count: a dependency that lives only in a commit message or a plan's gate text drops out of sight. In one project, a deliverable's second part was planned while its prerequisite, the first part, sat in Draft with no spec or plan.

**Where it's recorded:**
- **The catalog's `Depends on` column** (`docs/_index.md`) lists the deliverables that must be Complete first, comma-separated (`D11a, D12`), or `—`.
- **The plan's Phase Dependencies table** says which phases each one gates: a phase whose Depends On names a deliverable ID can't start until that deliverable is Complete. A catalog dependency that no phase names gates the whole deliverable, from Phase 1.

**Who fills it:**
- the split step (§ Splitting a deliverable);
- any spec or plan that gates on another deliverable;
- CD, by hand, for a dependency found later.

**What reads it:**

| Skill | Check |
|---|---|
| `sdlc-status` | Lists **blocked** deliverables (a prerequisite isn't Complete) and **forgotten prerequisites**: a prerequisite of active work that has no plan and isn't In Progress |
| `sdlc-plan`, `sdlc-lite-plan` | At registration and in the Approval Brief (What you need to do), name any prerequisite that has no plan or isn't Complete, and offer to plan it next. Headless: the result's `notes` and the brief's review focus |
| `sdlc-execute`, `sdlc-lite-execute` | At load, run only the phases no unfinished prerequisite gates, and stop before the first gated phase. Interactive: tell CD and ask whether to continue anyway. Headless: stop with `needs-input` |
| `sdlc-compliance-auditor` | Flags a dependency on an ID that isn't in the catalog, a cycle, and a Draft prerequisite of a Ready or In Progress deliverable |

Planning a deliverable before its prerequisite is fine: a prerequisite blocks execution, not planning.

## Splitting a Deliverable

When a deliverable turns out to be several (the Feasibility Gate shows it, or a plan would need an eighth phase), it splits into parts with letter suffixes: D11 → D11a, D11b, D11c. `sdlc-plan` § Splitting a Deliverable has the procedure. The result:
- **A split record:** `docs/current_work/planning/dNN_name_split.md`, from `[sdlc-root]/templates/split_record_template.md`. It holds each part's name, scope, tier and dependencies, and is what CD approves.
- **Catalog rows for the parts:** Draft, with `Depends on` filled.
- **The parent row:** it stays as the umbrella. Its `Depends on` lists its parts, and it reaches Complete when they all have.
- **No part left without a next action:** each part either gets planned next, or the split record names its next step. A part that "already has a design" still gets a lite plan before execution.
- **One level only:** a part doesn't split again. If a part is still too big, the split itself is wrong, and CD decides.

---

## File Naming

| State | File Pattern |
|-------|--------------|
| Draft/Ready | `dNN_name_spec.md` |
| Planning | `dNN_name_plan.md` |
| Complete | `dNN_name_result.md` |
| Blocked | `dNN_name_BLOCKED.md` |

---

## Status Markers

Every spec should have a status block at the top:

```markdown
# DNN: Feature Name — Specification

**Status:** Draft | Ready | In Progress | Complete
**Created:** YYYY-MM-DD
**Updated:** YYYY-MM-DD
**Depends On:** D1, D5 (if any)
```
