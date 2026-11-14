# Finding Classification

The canonical taxonomy for classifying review findings. Every skill that triages findings references this file.

---

## Classification Table

Classify each finding individually in a table before acting — no narrative paragraphs, no blanket dismissals. Before the table, one plain sentence tells CD what it means: how many findings, how many get fixed now, and which need CD's decision (`[sdlc-root]/process/writing-for-cd.md` § Status Blocks). For example: "Five findings: three get fixed now, one is already in the code, and one needs your decision (the retry limit)."

```
| # | Finding | Agent | Classification | Severity | Rationale |
|---|---------|-------|---------------|----------|-----------|
| 1 | specific finding | agent-name | FIX / PLAN / INVESTIGATE / DECIDE / PRE-EXISTING | critical/major/minor | why |
```

Severity applies only to FIX findings. Other classifications leave Severity blank. Deduplicate (§ Finding Deduplication) and calibrate severity (§ Severity Levels) **before** filling the table.

**Planning context adds a `Scope change` column** (plan review only — see § Scope-Change Marker):

```
| # | Finding | Agent | Classification | Severity | Scope change | Rationale |
|---|---------|-------|---------------|----------|--------------|-----------|
| 1 | specific finding | agent-name | FIX / DECIDE / PRE-EXISTING | critical/major/minor | yes/no | why |
```

## The Six Classifications

| Classification | When | Action |
|---------------|------|--------|
| **FIX** | Confident in diagnosis AND fix, AND the correct resolution is clear without user input | Dispatch the most relevant domain agent to fix it. In planning skills: include in revision dispatch. Once classified as FIX, the finding cannot be reclassified or closed without CD approval (see `[sdlc-root]/process/manager-rule.md` § No Unilateral Finding Demotion). |
| **PLAN** | Systemic issue (many files, architecture change) that exceeds a single fix | Needs a sub-plan. Flag to CD. |
| **INVESTIGATE** | Need more information before classifying | Dispatch relevant agent to diagnose, then reclassify |
| **DECIDE** | Trade-off, product decision, or resolution requires choosing between alternatives the user should weigh in on | Invoke `AskUserQuestion` with the finding description and options. Do not type the question as conversational text. Block until CD answers. |
| **PRE-EXISTING** | Finding exists in code this work did not touch | Present to CD via `AskUserQuestion` with options: fix now, create a handoff for a future session, or skip. Do not silently dismiss. |
| **PRE-DELIVERABLE-SPLIT** | Real finding requiring action, but scope is too large or decision-heavy for the current cycle | File as a future-deliverable candidate (D-suffix) with all options preserved. In-cycle work may include foundational pieces; the heavy lift is deferred. |

**Use only these six classifications.** If a finding doesn't fit, use DECIDE.

## Which Classifications Apply Where

Not every skill uses all six. The superset is defined here; each skill uses the subset appropriate to its context.

| Skill Context | Available Classifications | Notes |
|--------------|-------------------------|-------|
| Execution (sdlc-execute, sdlc-lite-execute) | FIX, PLAN, INVESTIGATE, DECIDE, PRE-EXISTING, PRE-DELIVERABLE-SPLIT | Full set — execution can surface systemic issues |
| Code review fix (sdlc-review-code, direct-dispatch review before committing) | FIX, INVESTIGATE, DECIDE, PRE-EXISTING | No PLAN or PRE-DELIVERABLE-SPLIT — commit fixes are scoped to the current diff |
| Planning review (sdlc-plan, sdlc-lite-plan) | FIX, DECIDE, PRE-EXISTING | No PLAN, INVESTIGATE, or PRE-DELIVERABLE-SPLIT — planning triage is simpler. Adds the `Scope change` column. |
| Reference-doc review (sdlc-create-reference-doc) | FIX, INVESTIGATE, DECIDE | No PLAN, PRE-EXISTING, or PRE-DELIVERABLE-SPLIT — the doc under review is the whole scope |

## Rules

### Misclassification Guard
Before dispatching FIX findings, scan each one. If you are about to type a question to the user about a FIX finding, STOP — that finding is DECIDE, not FIX. Reclassify it and invoke `AskUserQuestion`. A FIX finding must have a clear corrective action that does not require choosing between alternatives.

### PRE-EXISTING Qualification
A finding qualifies as PRE-EXISTING **only if** the finding's file is not in the plan's Files list AND was not created or modified by an agent during this work. If the file appears in the Files list, or if an agent touched it during this execution, any finding about that file is in scope — regardless of whether the finding is about the specific function that was modified.

### PRE-EXISTING Escalation
A PRE-EXISTING finding is still a real finding — it just wasn't introduced by this work. The decision to skip it belongs to CD, not the reviewer. When classifying a finding as PRE-EXISTING, invoke `AskUserQuestion` with the finding description and these options: (1) fix it now, (2) create a handoff for a future session, (3) skip it. Do not silently dismiss PRE-EXISTING findings or assume CD wants them deferred.

### No Invented Classifications
Do not invent new classification types (STALE, DUPLICATE, INTENTIONAL, WONTFIX, or any other). If a finding doesn't fit the six canonical classifications, it's DECIDE.

### PRE-DELIVERABLE-SPLIT Guidelines
Use when:
- The fix requires a CD UX decision the cycle doesn't have time to gather
- The fix introduces a new abstraction or subsystem (cross-package, schema-changing, service-introducing)
- The fix's scope expanded mid-execution beyond what was originally tasked
- The fix needs full SDLC planning (sdlc-plan or sdlc-lite-plan)

Do NOT use when:
- The fix is fully scoped but large — that's still FIX, just multi-task
- The fix needs CD input on direction but is otherwise scoped — that's DECIDE

Orchestrator responsibilities for PRE-DELIVERABLE-SPLIT:
1. Capture all candidate options (with architect-side preference if applicable)
2. Preserve evidence + context so the follow-up deliverable can resume without re-discovery
3. Note the finder and relevant reviewers with the finding so they can be looped into the follow-up
4. Surface in the final report under "Future Deliverables" with proposed D-number

### Low-Severity In-Scope Findings (Planning Context)
If a finding is in scope but has no actionable correction (e.g., purely informational, already consistent with the plan), classify it as FIX with a rationale of "acknowledged, no revision needed." It still gets a row in the table. Do not create a new classification for it.

### FIX Failure Escalation
If a FIX fails twice (agent dispatched, finding persists), reclassify as INVESTIGATE or PLAN. Do not keep dispatching the same fix. A headless run (no person present) does not reclassify: it stops with status `escalated` (`[sdlc-root]/process/headless-mode.md`).

## Severity Levels (FIX Findings Only)

One severity scale for every review context — code review, plan review, and reference-doc review. Severity is a function of **impact × likelihood**, not reviewer alarm level.

| Severity | Meaning |
|----------|---------|
| **critical** | Certain or very likely data loss, security breach, or complete failure |
| **major** | Significant functionality impact, likely to manifest |
| **minor** | Partial impact, a workaround exists, or cosmetic |

**How each context reads "impact":**

| Context | Impact is measured on |
|---------|----------------------|
| Code review | The running software |
| Plan review | The implementation, if the plan is executed as written |
| Reference-doc review | A reader (agent or human) acting on what the doc says |

Reference docs use this bar as-is — there is no separate HIGH/MEDIUM tier.

### Severity Calibration

Calibrate every finding against the table above **before** assigning its label — reviewers' own labels are input, not the verdict. A finding one reviewer escalated to `critical` that calibrates as `major` is downgraded, and the rationale is recorded in the finding: "Calibrated from agent-reported critical to major: impact is significant but not certain data loss under normal conditions." A report where everything is `critical` is a report that gets ignored.

Calibration applies the criteria; it is never a lever for exiting a review loop. Downgrading a finding so that the loop's exit bar is met is a demotion, governed by `[sdlc-root]/process/manager-rule.md` § No Unilateral Finding Demotion.

### Scope-Change Marker (Planning Context Only)

In plan review, every FIX finding also gets a `Scope change` value in the Classification Table: **yes** if the fix changes the approach, adds or removes files, or changes a phase or agent assignment; **no** otherwise. The marker is independent of severity — a `minor` finding whose fix adds a file is `Scope change: yes`. Plan re-review trigger (1) reads this column (see `[sdlc-root]/process/review-fix-loop.md` § Plan Review). Execution and reference-doc contexts do not use the column.

## Finding Deduplication

Applies **before classification** in every review loop. When multiple reviewers flag issues at the same location, apply these merge rules:

| Situation | Action |
|-----------|--------|
| Same `file:line`, same underlying issue | Merge into one finding. Credit all agents. Keep the more detailed description. Use the highest severity among them (then calibrate). |
| Same `file:line`, different issues | Keep as separate findings. Tag both as `co-located` so the author knows they are distinct concerns at the same spot. |
| Same issue, different locations | Keep separate. Cross-reference: "See also: Finding #N (same pattern at `other/file.py:88`)". |
| Same location, conflicting fix recommendations | Keep merged but include both recommendations with agent attribution: "agent-A recommends X; agent-B recommends Y." Do not silently choose one. |

For plans and reference docs, "location" is the `artifact § section` the finding cites. Merging by location alone erases real findings — merge only when the underlying issue is the same.

## Open Minor Findings

A review loop exits when no `critical` or `major` FIX findings remain (`[sdlc-root]/process/review-fix-loop.md` § Exit Bar). Minor FIX findings still open at exit are **listed, never silently closed**. The same table also carries any critical or major finding CD directed proceeding with at the round cap, with its real severity and CD's direction:

```
### Open Minor Findings

| # | Finding | Agent | Location | Why still open |
|---|---------|-------|----------|----------------|
| 1 | specific finding | agent-name | file:line or artifact § section | batched pass did not resolve it / round cap reached |
```

| Context | Where the table lives |
|---------|----------------------|
| Execution (sdlc-execute, sdlc-lite-execute) | The result doc |
| Code review (sdlc-review-code, direct-dispatch review before committing) | The final report (Fix Summary) |
| Plan review (sdlc-plan, sdlc-lite-plan) | The plan file, alongside the agent-reviews section |
| Reference-doc review (sdlc-create-reference-doc) | The commit message |

Listing a minor finding as open at loop exit, visible to CD, is permitted and is not demotion. **Only CD closes an Open Minor Findings entry** — the orchestrator never marks one resolved, accepted, or won't-fix.
