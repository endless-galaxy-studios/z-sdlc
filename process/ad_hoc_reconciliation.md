# Ad Hoc Work Reconciliation

## The Reality

Not all work fits neatly into the Spec → Planning → Implementation → Result flow. Sometimes you:

- Fix a bug CC introduced
- Move a button 10 pixels
- Add a missed validation
- Iterate on UI feedback
- Handle an edge case the spec didn't anticipate

**This is normal.** The process should accommodate reality, not fight it.

---

## The Principle

> The SDLC process is a **better path for substantial work**, not a gate that blocks quick fixes.

Ad hoc work is legitimate. The goal is to periodically reconcile it so:
- Chronicles remain accurate
- Specs stay current
- Nothing important is lost
- You can resume formal process cleanly

---

## Trigger: "Let's catalog our ad hoc work"

When the user says this (or similar), CC should initiate reconciliation.

**Alternative triggers:**
- "Let's catch up the docs"
- "What have we done since D[last]?"
- "Let's rejoin the process"
- "Reconcile our recent work"

---

## Reconciliation Process

### Phase 1: Discovery

**1.1 Identify the boundary**

Find the last formal checkpoint:
```bash
# Find last deliverable-tagged commit
git log --oneline --grep="d[0-9]" | head -5

# Find last chronicled deliverable
ls docs/current_work/results/*COMPLETE.md | tail -5
```

**1.2 Review ad hoc commits**

List commits since last formal work:
```bash
git log --oneline [last-formal-commit]..HEAD
```

**1.3 Categorize each commit**

| Category | Description | Action |
|----------|-------------|--------|
| **Bug fix** | Correcting CC's mistake | Absorb or skip |
| **UI tweak** | Small visual adjustment | Batch into polish |
| **Missed requirement** | Gap in original spec | Update spec + absorb |
| **Edge case** | Unanticipated scenario | Update spec + absorb |
| **Iteration** | Refinement based on feedback | Absorb into parent |
| **Trivial** | Typos, formatting | Skip |

### Phase 2: Reconciliation Options

Present options to user:

**Option A: Absorb into existing deliverable**

If work is related to a recent deliverable (e.g., d12):
- Update `d12_..._result.md` with additional changes
- Optionally update the spec if requirements changed
- No new deliverable ID needed

**Option B: Create lightweight completion record**

For standalone work that doesn't warrant a full spec:
```markdown
# Ad Hoc: [Brief Description]

**Date:** YYYY-MM-DD
**Commits:** abc123, def456

## Summary
[What was done and why]

## Changes
- [File]: [What changed]

## Related
- Parent deliverable: d12 (if any)
- Spec update needed: Yes/No
```

Save as: `docs/current_work/results/adhoc_YYYYMMDD_brief_description.md`

**Option C: Batch into polish deliverable**

Group related tweaks into a single deliverable:
- Create `dNN_[timeframe]_polish_spec.md` (lightweight)
- List all changes in one completion record
- Good for UI iteration phases

**Option D: Skip tracking**

For truly trivial work:
- Acknowledge it happened
- Don't create documentation
- Move on

### Phase 3: Spec Maintenance

If ad hoc work revealed spec gaps:

```markdown
## Spec Updates Needed

| Spec | Gap Identified | Suggested Update |
|------|----------------|------------------|
| d12_name_spec.md | Didn't handle null values | Add validation requirement |
```

Offer to update specs now or create a task.

### Phase 4: Git State

Ensure clean state before resuming:
```bash
git status
```

Options:
- Commit any pending changes
- Create reconciliation commit: `docs: reconcile ad hoc work [date range]`
- Stash if user wants to continue ad hoc

### Phase 5: Path Forward

Ask the user with `AskUserQuestion`: "Ad hoc work has been reconciled. What would you like to do?" Options:

1. **Resume formal process** — Start d[next] with a spec
2. **Continue ad hoc** — Keep working, reconcile again later
3. **Chronicle and pause** — Archive current work, take a break

---

## Quick Reference

| Situation | Recommended Action |
|-----------|-------------------|
| Fixed CC's bug | Skip or absorb into parent deliverable |
| Moved a button | Batch into polish or skip |
| Added missed validation | Update spec + absorb |
| Major feature creep | Stop, write a spec, formalize |
| UI iteration (many tweaks) | Batch into `dNN_ui_polish` |
| Typo fix | Skip |

---

## Anti-Patterns

### Don't
- Create full spec/planning/prompt for a 2-line fix
- Feel guilty about ad hoc work
- Let ad hoc work accumulate for weeks without reconciliation
- Abandon process entirely because "it's too heavy"

### Do
- Reconcile weekly or at natural breakpoints
- Keep specs updated when requirements change
- Use lightweight tracking for small work
- Return to formal process for substantial features

---

## For CC: Handling Ad Hoc Requests

When user asks for quick changes without a deliverable ID:

1. **Do the work as direct dispatch** — don't block on deliverable tracking. The Manager Rule and the review before committing still apply (`CLAUDE.md` § Direct Dispatch Rules).
2. **Note it** — Remember this is ad hoc
3. **Offer reconciliation** — After a few ad hoc items, suggest: "We've done several small changes. Want to catalog them?"

When user explicitly says "just do X, skip the process":
- Skip the deliverable tracking (no ID, spec or plan); dispatch and review as direct dispatch does
- Don't lecture about process
- Offer to reconcile later

---

## Integration with Chronicles

Ad hoc work can be chronicled:
- **Absorbed work** — Goes with parent deliverable
- **Lightweight records** — Go to relevant concept directory
- **Batched polish** — Gets its own deliverable ID, chronicles normally

The chronicles should reflect what actually happened, not an idealized process.
