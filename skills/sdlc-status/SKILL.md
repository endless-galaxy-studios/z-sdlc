---
name: sdlc-status
description: >
  Show project SDLC status — active deliverables, blocked items, and recent archives.
  Read-only: scans catalog and current_work/, makes no changes.
  Use when you need a quick read-only overview of active deliverables and project state.
  Triggers on "SDLC status", "show project status", "what are we working on",
  "deliverable dashboard", "show deliverables", "/sdlc-status".
  Do NOT use for compliance or health audits — use sdlc-audit.
---

# SDLC Status Dashboard

Scan the project's SDLC artifacts and present a status summary. This is read-only — take no actions, modify no files.

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Two exceptions stand: the skill's own knowledge-layer updates count as local work, even when an adapter writes them to its memory store (a subagent's own memory-store writes don't), and the External Review Gate may send to a hosted provider the project has durably authorized (`[sdlc-root]/process/external-review-gate.md` § Data egress). Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## Steps

1. **Read `docs/_index.md`** to get the deliverable catalog and next ID.

2. **Scan `docs/current_work/`** subdirectories:
   - `specs/` — list all spec files
   - `planning/` — list all plan files
   - `results/` — list all result files
   - `sdlc-lite/` — lite deliverables: `dNN_*_plan.md` and `dNN_*_result.md`, and in `sdlc-lite/completed/` the ones whose execution committed (`sdlc-lite-execute` moves the plan and result there)
   - `issues/` — list all issue/blocker files

3. **Determine each deliverable's stage** by cross-referencing which artifacts exist:

   | Has Spec | Has Plan | Has Result | Stage |
   |----------|----------|------------|-------|
   | yes | no | no | **Spec written** — needs CD approval, then planning |
   | yes | yes | no | **Plan ready** — awaiting execution |
   | yes | yes | yes | **Complete** — ready to archive |
   | no (lite) | yes, in `sdlc-lite/` | no | **Plan ready** — awaiting `sdlc-lite-execute` |
   | no (lite) | yes, in `sdlc-lite/` | yes, in `sdlc-lite/`, and the catalog doesn't say Complete | **Executing** — result written, not yet committed and moved to `completed/` |
   | no (lite) | yes, in `sdlc-lite/` | yes, in `sdlc-lite/`, and the catalog says Complete | **Complete** — ready to archive; never moved to `completed/`, which `sdlc-archive` accepts |
   | no (lite) | yes, in `sdlc-lite/completed/` | yes, in `sdlc-lite/completed/` | **Complete** — ready to archive |

   A lite result left in `sdlc-lite/` is either still executing or finished and never moved (a project from before the move, or a commit that skipped it), and only the catalog's status tells them apart. When the catalog says In Progress but commits name the ID (`git log --oneline -i --grep=dNN`), show **Executing?** and say the catalog may be stale: `sdlc-archive` step 2 checks it.

   If a matching issue file exists in `issues/`, mark it **Blocked** regardless of other artifacts.

   **Dependencies** (the catalog's `Depends on` column; `[sdlc-root]/process/deliverable_lifecycle.md` § Dependencies):
   - **Waiting on a prerequisite:** a deliverable with a prerequisite that isn't Complete. Mark it `Plan ready — waiting on DNN` (or the stage it's at, plus the wait).
   - **Forgotten prerequisite:** a prerequisite of active work that has no plan and isn't In Progress. Its Next Action is to plan it. These are what drop out of sight.
   - A split parent (its `Depends on` lists its own parts) shows as `Split — waiting on its parts` until they're all Complete.

4. **Scan recent chronicles** — list the 5 most recently modified `_index.md` files under `docs/chronicle/`.

4a. **Find open runbooks** (`[sdlc-root]/process/runbooks.md`): each marker line in `[sdlc-root]/process/*.md` (its full form: `[sdlc-root]/process/runbooks.md` § What makes a doc a runbook) names a runbook and its record. Read the record's **Status** and **Next**. List an `enable` runbook that isn't done ("no record yet" when its record doesn't exist), a `setup` one that isn't done or declined (likewise), and an `on-demand` one that is in progress; leave out the rest.

5. **Present the dashboard:**

```
**{N} active, {N} blocked, {N} ready to execute.** Next ID: D__.

## Active Deliverables

| ID | Name | Stage | Next Action |
|----|------|-------|-------------|
| D1 | ... | Complete | Archive via "Let's organize the chronicles" |
| D2 | ... | Plan ready | Execute via sdlc-execute |

## Forgotten Prerequisites ({N})

- D__ (needed by D__): no plan, not in progress — plan it next

## Blocked Items ({N})

- [issue filename]: brief description from first line

## Open Runbooks ({N})

- factory-enablement: in progress — next § 3.3 (continue with `sdlc-run-runbook factory-enablement`)

## Recent Archives ({N})

- concept-name: brief description
```

Do NOT suggest or take any follow-up actions beyond what appears in the Next Action column. Present the status.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll suggest archiving while showing status" | This skill is read-only. Present the data. Do not take or suggest actions. |
| "I'll fix the catalog while I'm reading it" | Display only. If the catalog has issues, the user decides what to do about them. |

## Integration
- **Depends on:** `docs/_index.md`, `docs/current_work/`, and the runbooks' records (`[sdlc-root]/process/runbooks.md`) (reads current state)
- **Display only:** Do NOT invoke any other skill from here
