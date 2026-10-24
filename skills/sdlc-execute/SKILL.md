---
name: sdlc-execute
description: >
  Execute an approved implementation plan. The plan must already exist at
  docs/current_work/planning/dNN_name_plan.md — written and reviewed by worker domain agents via
  sdlc-plan. Loads the plan, executes phases using worker domain agents, reviews all completed work
  with worker domain agents, fixes critical and major findings (minors listed for CD), and commits.
  Use when an approved plan exists and the user confirms execution.
  Triggers on "execute the plan", "implement the plan", or references to an existing plan file.
  Do NOT use without a plan — if no plan exists, use sdlc-plan first.
  Do NOT use for lite deliverables — those use sdlc-lite-execute.
  Do NOT use for auditing completed work against a plan — use CHECKER mode (this skill supports both).
---

# SDLC Execution

## Overview

This skill executes an approved plan that was produced by `sdlc-plan`. Worker domain agents implement the phases, review the result, and fix findings. You are the manager — you dispatch worker agents, track phase completion, and ensure reviews pass before the task is done.

**Precondition:** A reviewed and approved plan must exist before this skill runs. If no plan exists, stop and use `sdlc-plan` first.

## Mode Selection

| User Intent | Mode | Entry Point |
|-------------|------|-------------|
| "Execute the plan", "implement the plan" | **APPLIER** | Step 0 (full execution workflow) |
| "Audit implementation", "review against plan", "check completed work" | **CHECKER** | Audit Workflow below |
| Unclear | Ask: "Are you executing new work, or auditing completed work?" | — |

### CHECKER Mode: Audit Completed Work Against Plan

When auditing already-implemented work (not executing new work):

1. Load the plan from `docs/current_work/planning/dNN_name_plan.md`
2. Scan changed files (git diff or file list from result doc)
3. Dispatch ALL relevant worker domain agents to audit:
   - Completeness: did all plan phases get implemented?
   - Correctness: does the implementation match the plan's intent?
   - Deviation: are there changes NOT in the plan? Are they justified?
4. Present structured findings to CD
5. If fixes needed: dispatch agents to fix, then re-audit under the Review-Fix Loop rules (`[sdlc-root]/process/review-fix-loop.md` — fresh subagents, mechanical re-review roster, same exit bar, at most 3 rounds; the initial audit is round 1)

**CHECKER mode ends after step 5. APPLIER mode below governs all execution work.**

## Step 0: Load the Plan

Load the plan from `docs/current_work/planning/dNN_name_plan.md` — this plan has been reviewed and approved.

**Read the plan file only.** Do not pre-read implementation files, existing components, or codebase patterns before dispatch. The plan file is sufficient context for the manager. Worker domain agents read the files relevant to their own phases when they execute. Pre-reading implementation files and accumulating context is not management — it is the first step toward self-implementation.

Extract:
1. **Phases and their dependencies** — what runs in parallel vs. what sequences
2. **Agent assignments** — which worker domain agent owns each phase/task
3. **Relevant worker domain agents** — the full list for post-execution review

If the plan file doesn't exist or can't be found, **stop immediately** and tell the user:

> No approved plan found. Run `sdlc-plan` first to create and review the plan.

Do NOT write a plan yourself. Do NOT proceed without one. **Headless run:** end with status `failed`, reason: no approved plan at the expected path; run `sdlc-plan` first.

**Prerequisites.** Before Phase 1, read the deliverable's `Depends on` in `docs/_index.md`. A phase is gated when its row in the plan's Phase Dependencies table names a deliverable that isn't Complete; a catalog prerequisite no phase names gates Phase 1. Run the phases nothing gates, in order, and stop before the first gated phase. Tell CD which prerequisite blocks it and its status, and ask whether to continue anyway; CD may override. **Headless run:** stop there with status `needs-input`, naming the prerequisite and the phases left. Work done before the stop stays (`[sdlc-root]/process/deliverable_lifecycle.md` § Dependencies).

**Production gates.** A plan may have gates between phases (`### Gate G<n>`): production work, approved by CD and done by CD or the project's production runner, never by you or an agent (`[sdlc-root]/process/production-gates.md`). When the next item is a gate:
1. Run the Review-Fix Loop (step 2's rules, exit bar and round cap) over the work since the previous gate, or since Phase 1. A gate never ships unreviewed work. Emit `REVIEW-GATE: phases [list] done — entering pre-gate review (G<n>)`; when the loop exits, announce "Review loop complete — proceeding to gate G<n>" and go to the gate, not to step 3. If the loop escalates, the escalation comes first; if CD directs you past the cap, record the open findings in the result doc and go to the gate. Every loop's open minor findings and key feedback go in the result doc.
2. Commit that work (step 3c's per-phase commits already cover it; commit anything left).
3. Present the gate (runbook, report-back fields, rollback) as a completed message, then ask with `AskUserQuestion` whether CD will do it or approve the project's runner to. Once it's done, ask for the outcome and the report-back values, record them in the result doc's Gates section, and continue with the next phase.

A failed gate stops execution; CD decides whether to roll back, retry or stop. The completion review (step 2) then covers only the work after the last gate. A phase whose steps include production work (a plan written before gates existed, or one a review missed) is triaged REVISE_PLAN at its PRE-GATE and never dispatched. A gate row in the Phase plan is never dispatched either. **Headless run:** after steps 1 and 2, stop with status `awaiting-approval`: name the gate in `stage` (`sdlc-execute — after gate G<n>`) and in a `gate` field if the caller's schema has one, list its steps under `outbound`, and record in `notes` the completed phases and their commits and that the review before the gate passed.

**Headless restart.** When the prompt restarts this deliverable at a named stage (an answer to a phase triage, a DECIDE finding, an escalated review, or a production gate's result), read the plan, the partial result doc and the earlier result's `notes`. Skip phases already complete, and continue from the stopped phase, or from the review loop at the recorded round with the frozen round-1 roster. Never redo a completed phase or restart the round count. After a gate, the prompt carries the gate's result: if the gate succeeded and every report-back field is present, record it in the result doc's Gates section and continue with the phase after the gate; otherwise stop with `needs-input`, saying what failed or is missing. The review loop after a gate starts at round 1. Each headless stop's `notes` carry what a restart needs: completed phases and their commits, the current phase, and during review the round number, frozen roster and open-findings table (`[sdlc-root]/process/headless-mode.md` § Resuming).

## The Process

```dot
digraph execution {
    rankdir=TB;

    "0. Load approved plan" [shape=box];
    "Plan exists?" [shape=diamond];
    "STOP — run planning skill first" [shape=doublecircle, color=red];

    subgraph cluster_phase_loop {
        label="1. Per-Phase Loop (repeat for each phase/wave)";
        style=dashed;

        "1a. PRE-GATE\n- Pattern Reuse Gate\n- Phase triage: BUILD / SKIP / REVISE_PLAN\n- Verify dependencies complete" [shape=box, style=bold, color=blue];
        "1b. DISPATCH worker domain agent(s)\nper plan assignment\n(you do NOT implement)" [shape=box];
        "1c. POST-GATE\n- [build command]\n- Files match plan?\n- Flag deviations to CD" [shape=box, style=bold, color=blue];
    }

    "All phases complete?" [shape=diamond];
    "2a. Dispatch fresh reviewers\n(round N of 3; roster from plan,\nthen mechanical re-review roster)" [shape=box];
    "2b. Collect findings\ndedup → calibrate → classify" [shape=box];
    "Anything left to fix?\n(critical/major, unresolved INVESTIGATE/DECIDE,\nor minors awaiting their one batch pass)" [shape=diamond];
    "Round 3 done?" [shape=diamond];
    "Critical or major\nstill open?" [shape=diamond];
    "ESCALATE to CD\n(AskUserQuestion +\nopen-findings table)" [shape=box, color=red];
    "2c. Fix critical + major\n(or the minor batch pass)" [shape=box];
    "2d. Re-run verification gate\nPick roster mechanically\n(full or raisers + standing)" [shape=box, style=bold];
    "3. Write Worker Agent Reviews\n-> results doc" [shape=box];
    "4. Verify + commit" [shape=box];
    "Task complete" [shape=doublecircle];

    "0. Load approved plan" -> "Plan exists?";
    "Plan exists?" -> "STOP — run planning skill first" [label="no"];
    "Plan exists?" -> "1a. PRE-GATE\n- Pattern Reuse Gate\n- Phase triage: BUILD / SKIP / REVISE_PLAN\n- Verify dependencies complete" [label="yes"];
    "1a. PRE-GATE\n- Pattern Reuse Gate\n- Phase triage: BUILD / SKIP / REVISE_PLAN\n- Verify dependencies complete" -> "1b. DISPATCH worker domain agent(s)\nper plan assignment\n(you do NOT implement)";
    "1b. DISPATCH worker domain agent(s)\nper plan assignment\n(you do NOT implement)" -> "1c. POST-GATE\n- [build command]\n- Files match plan?\n- Flag deviations to CD";
    "1c. POST-GATE\n- [build command]\n- Files match plan?\n- Flag deviations to CD" -> "All phases complete?";
    "All phases complete?" -> "1a. PRE-GATE\n- Pattern Reuse Gate\n- Phase triage: BUILD / SKIP / REVISE_PLAN\n- Verify dependencies complete" [label="no — next phase/wave"];
    "All phases complete?" -> "REVIEW-GATE\n(mandatory — no pause)" [label="yes"];
    "REVIEW-GATE\n(mandatory — no pause)" [shape=box, style=bold, color=red];
    "REVIEW-GATE\n(mandatory — no pause)" -> "2a. Dispatch fresh reviewers\n(round N of 3; roster from plan,\nthen mechanical re-review roster)";
    "2a. Dispatch fresh reviewers\n(round N of 3; roster from plan,\nthen mechanical re-review roster)" -> "2b. Collect findings\ndedup → calibrate → classify";
    "2b. Collect findings\ndedup → calibrate → classify" -> "Anything left to fix?\n(critical/major, unresolved INVESTIGATE/DECIDE,\nor minors awaiting their one batch pass)";
    "Anything left to fix?\n(critical/major, unresolved INVESTIGATE/DECIDE,\nor minors awaiting their one batch pass)" -> "Round 3 done?" [label="yes"];
    "Round 3 done?" -> "2c. Fix critical + major\n(or the minor batch pass)" [label="no"];
    "2c. Fix critical + major\n(or the minor batch pass)" -> "2d. Re-run verification gate\nPick roster mechanically\n(full or raisers + standing)";
    "2d. Re-run verification gate\nPick roster mechanically\n(full or raisers + standing)" -> "2a. Dispatch fresh reviewers\n(round N of 3; roster from plan,\nthen mechanical re-review roster)";
    "Round 3 done?" -> "Critical or major\nstill open?" [label="yes — cap"];
    "Critical or major\nstill open?" -> "ESCALATE to CD\n(AskUserQuestion +\nopen-findings table)" [label="yes"];
    "Critical or major\nstill open?" -> "3. Write Worker Agent Reviews\n-> results doc" [label="no — list Open Minor Findings"];
    "Anything left to fix?\n(critical/major, unresolved INVESTIGATE/DECIDE,\nor minors awaiting their one batch pass)" -> "3. Write Worker Agent Reviews\n-> results doc" [label="no — exit bar met"];
    "3. Write Worker Agent Reviews\n-> results doc" -> "4. Verify + commit";
    "4. Verify + commit" -> "Task complete";
}
```

## Collaboration Model

The full model is in `[sdlc-root]/process/collaboration_model.md` (role definitions, decision authority table, autonomy spectrum). The critical directives:

**AskUserQuestion mandate:** every question directed at the user MUST use the `AskUserQuestion` tool — do not type questions as conversational text. Status updates and completion reports that need no response use normal text.

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

**Anti-patterns to avoid:** (1) code assertion without verification — never answer "how does X work" from memory; grep/read the code first; (2) trajectory poisoning — if the agent is off track after 2-3 corrections, clear context and start fresh rather than continuing to correct in a poisoned trajectory.

## Deliverable Lifecycle

Follow the state machine in `[sdlc-root]/process/deliverable_lifecycle.md`. Update the `**Status:**` marker in the spec file as the deliverable transitions through states: In Progress (at phase start), Validated (after review loop passes), Deployed (after deployment verification, if applicable), Complete (after final commit). Use the defined status markers — do not invent custom states.

## Manager Rule

**You are the manager — you orchestrate, you do not implement.** The canonical rule is in `[sdlc-root]/process/manager-rule.md`. The critical constraints:

- **Default: dispatch domain agents** for all code and domain content changes. You never write code yourself.
- **Delegation economics exception:** you may self-apply a change when delegation would cost more than the change itself (in tokens or main-context growth) AND the change is small and bounded, requires no design judgment, and needs no new context beyond what you already hold. Every self-applied change still goes through domain agent review — self-applied is never self-approved.
- **Failed dispatch:** if an agent returns without applying its work, re-dispatch with a revised prompt; only a remaining gap that passes the economics test may be closed directly (with review).
- **No semantic revert:** fixing a bug by removing the feature is not a fix — preserve the user's requested behavior.
- **Session scope:** this rule stays active for the entire session. There is no post-commit wind-down mode.

**No pre-dispatch narration.** Status comes from the gates (PRE-GATE, POST-GATE, REVIEW-GATE) — not from sentences around them. Do not type filler describing what you are about to do: "Plan loaded.", "Let me check the catalog.", "Proceeding to Phase N.", "Now updating the catalog and committing.", "Staged set looks correct. Committing." The gates ARE the protocol; commentary around them is noise the user has to scroll past. The two acceptable exceptions are: (1) a one-line note conveying genuinely new information — a deviation observed, a phase-bleeding decision, a serialization choice forced by mid-stream discovery, a triage rationale; (2) the explicit announcements other rules require ("Review loop complete — …", REVIEW-GATE block, etc.). When in doubt, prefer the gate over a sentence.

## Phase Details

### 1. Execute Phases

Follow the plan's phase structure.

**Phase plan (emit once, before any dispatch):**

Reprint the plan's phase structure as a single table. This is the reference every subsequent PRE-GATE points back to — file-conflict and dependency information live here, not in each per-phase block.

```
**Phase plan**

| # | Agent       | Files                                 | Depends | Parallel with |
|---|-------------|---------------------------------------|---------|---------------|
| 1 | <agent>     | <path>, <path>                        | —       | <# or —>      |
| 2 | <agent>     | <path>, <path>                        | 1       | —             |
```

If any file appears in more than one phase's row, those phases MUST run sequentially regardless of the plan's `Parallel with` column — mark the conflict in the table and explain in one line below. The Phase plan emission IS the file-conflict check; don't repeat it per phase unless a conflict was missed.

After emitting the Phase plan, proceed directly to the first wave's PRE-GATE in the same response. Do not ask the user to confirm execution scope — plan size (many phases, many agents, long estimated arc) is not a confirmation trigger. The plan was approved in `sdlc-plan`; a scope question re-litigates that approval and stalls an autonomous run.

For each phase:

**PRE-GATE** — you cannot dispatch the phase agent until this block appears in your response. Use the compact form by default; fall back to verbose when a trigger fires.

Compact form (happy path — Triage = BUILD):

```
### Phase [N] — [phase name]  (agent: [agent-name])

Design decisions:
- [decision 1 — one per bullet, not semicolon-chained]
- [decision 2]

Expected: [counts from plan, or "none"]
Triage: BUILD
```

Verbose form (use when any of these triggers fires):
- **Triage ≠ BUILD** — SKIP or REVISE_PLAN (stop and wait for CD confirmation; document SKIPs in the result doc under 'Skipped Phases'; do not self-modify the approved plan). **Headless run:** stop with status `needs-input`, giving the phase, SKIP or REVISE_PLAN, and the reason; completed phases stay, and the phase is neither skipped nor rewritten until CD answers (`[sdlc-root]/process/headless-mode.md`).
- **Pattern found** — LSP `goToImplementation`/`findReferences` or Grep surfaced a precedent that's actively shaping the implementation (cite the path)
- **External data** — the phase reads from any source other than the codebase (URL, repo, API, document)
- **Dependency re-check** — the Phase plan table needs amending (mid-execution re-sequencing, late-discovered conflict)
- **Re-dispatch** — partial completion or stub fix within this same phase

Verbose form — single phase. Emit as a table; the labeled-field block format is deprecated:

```
**PRE-GATE Phase [N] — [phase name]**

| Field          | Value |
|----------------|-------|
| Agent          | [agent-name] |
| Triage         | BUILD | SKIP | REVISE_PLAN |
| If not BUILD   | [reason — stop and wait for CD confirmation; omit row if Triage = BUILD] |
| Dependencies   | [phase N complete | none required] |
| Pattern search | [what you searched for] → [found / not found / following pattern at path/to/file.ts] (use LSP goToImplementation/findReferences for interfaces and call sites; Grep for text patterns) |
| Data sources   | [ALL external sources — URLs, repos, APIs, documents | "codebase only"] |
| Expected       | [counts from plan | none] |

Design Decisions:
- [decision 1 — one per bullet, never semicolon-chained]
- [decision 2]
```

Verbose form — parallel dispatch (two or more phases in the same wave). Emit a single comparison table instead of repeating the per-phase block:

```
**PRE-GATE — parallel dispatch (Phases [N], [M])**

| Field          | Phase [N]: [name]      | Phase [M]: [name]      |
|----------------|------------------------|------------------------|
| Agent          | [agent-name]           | [agent-name]           |
| Triage         | BUILD                  | BUILD                  |
| Dependencies   | [...]                  | [...]                  |
| File overlap   | none with Phase [M]    | none with Phase [N]    |
| Pattern search | [...]                  | [...]                  |
| Data sources   | [...]                  | [...]                  |
| Expected       | [...]                  | [...]                  |

Design Decisions — Phase [N]:
- ...

Design Decisions — Phase [M]:
- ...
```

**File-Conflict Gate (parallel phases only):** Before dispatching two or more phases simultaneously, verify file overlap (same rule as the Phase plan table above, applied at dispatch time). If any file appears in more than one phase, sequence those phases. Do not rely on the plan's dependency table alone; verify file overlap yourself.

**Parallel Phase Ownership Decomposition.** When the plan specifies two or more phases that can run in parallel, the File-Conflict Gate above is necessary but not sufficient — also verify each phase has a coherent ownership cluster. Use this decomposition lens before dispatching parallel phases:

| Ownership model | When to use | Typical agent assignment |
|-----------------|-------------|--------------------------|
| **By package** (monorepo boundary) | Default for full-stack features — each phase owns one package or top-level directory | One domain agent per package |
| **By layer within a package** | When a single-package feature has clean vertical layers and one agent per layer makes sense | db-architect (models/migrations), backend-developer (routes/services), sdet (tests/) |
| **By module/feature** | When touching multiple independent features within one package | One domain agent per feature subdirectory |
| **Vertical slice** | One agent owns end-to-end for a narrow user-facing capability (UI + API + tests) | Single domain agent (rare — prefer horizontal layer) |
| **Horizontal layer** | One agent owns their layer across all features in the phase | One domain agent per layer |

The project's agent split typically implies the right ownership model. When unsure, default to horizontal-layer — it matches most domain-agent configurations.

**Barrel-file / index-file rule.** Files that aggregate exports or imports for many siblings (`__init__.py`, `index.ts`, barrel files, router registration files, config aggregators) are implicit conflict hotspots — multiple phases may each want to add an entry. For any parallel-phase set, list every barrel file each phase would modify. If two phases touch the same barrel file, designate one phase as the owner and have the other phase's agent request the entry via the dispatch prompt — not by editing. Alternative: collapse the barrel edits into a small, sequenced coda phase the manager runs after both parallel phases pass their POST-GATE.

**Interface-contract boundary.** When parallel phases consume each other's output (frontend consumes backend's API schema; workers consume a table shape; one service consumes another's contract), the contract must be frozen before the downstream phase dispatches. Contract surfaces include: request/response schemas (the authoritative source for downstream types), data models + migrations (the canonical data shape), and generated types (if the plan specifies generated types, the producing phase must complete before the consuming phase dispatches). File overlap is not the same as logical dependency — two phases can touch entirely different files yet still have a semantic dependency through a contract surface.

When the plan has a parallel phase set where one phase defines a contract and another consumes it, split the work: dispatch the contract-producing phase first, verify the contract file exists and is coherent, then dispatch the consumers in parallel.

**Plan parallelization signals.** Before dispatching a parallel phase set from the plan, verify these signals are all true. If any is false, dispatch sequentially and note why in the PRE-GATE:

1. No file appears in more than one phase (File-Conflict Gate above).
2. No barrel/index file is modified by more than one phase, or the barrel-file coda pattern above applies.
3. No phase consumes a contract artifact produced by another phase in the same wave (contract-producing phases go first).
4. Phases have distinct agent owners — two phases assigned to the same agent cannot run in parallel regardless of file non-overlap, because a single agent session cannot be dispatched twice concurrently.
5. No phase produces a side effect (migration run, seed execution, cache prime) that another phase in the same wave depends on implicitly.

**Decomposition-wrong-mid-stream.** If during execution you discover the plan's parallel decomposition was unsafe (agents are blocking on each other, unexpected file overlap surfaces, a contract boundary was missed), stop new dispatch. Output a `REVISE_PLAN` triage for the remaining phases per the PRE-GATE protocol and wait for CD confirmation. Do not silently serialize a planned-parallel set — that hides the planning defect from the discipline capture and lets the same mistake recur.

**Data Source Extraction (mandatory):** Read the plan's phase description and extract EVERY data source mentioned — external repos, APIs, URLs, documents, AND codebase files. List them all in the PRE-GATE block. If the plan says data comes from an external source, the dispatch prompt MUST tell the agent to fetch from that source. Omitting an external data source from the dispatch prompt causes agents to hallucinate values instead of reading from the defined source.

**EXECUTE**: Dispatch assigned agent(s) per plan. Never narrate readiness ("Ready to dispatch") and pause for confirmation; the plan is already approved. The dispatch prompt must include:
1. **The phase's full context from the plan** — outcome, constraints, acceptance criteria, AND any implementation guidance the planning agent included (approach hints, key functions, file relationships, migration notes, data flow context). The plan is the agent's primary briefing document — pass through everything relevant to this phase. Do not summarize or omit plan details; the executing agent benefits from the planning agent's full reasoning.
2. **All data sources** from the PRE-GATE extraction — external sources get explicit fetch instructions. For data extraction tasks, tell the agent to read ALL relevant pages from the source, extract ALL entries exhaustively, and cross-check the final count.
3. **Expected counts** from the plan — the agent can self-check its output
4. **Binding Design Decisions** that constrain this phase's implementation
5. **Prior phase artifacts** — when this phase depends on a completed phase that produced data artifacts (seed scripts, config files, type definitions), the dispatch prompt must tell the agent to read those files as the canonical reference. Agents that produce coupled artifacts will fabricate their own values if not told where the canonical data lives.
6. **Library verification instructions** — when the phase involves external library/framework APIs, tell the agent to verify API usage via Context7 (`mcp__context7__resolve-library-id` → `mcp__context7__query-docs`) before writing integration code. Include the library names and versions from the project's dependency files. Agents must not rely on training data for API signatures, parameter names, or default behaviors.
Consult `[sdlc-root]/knowledge/architecture/agent-orchestration-patterns.yaml` for dispatch discipline — especially AOP1 (decompose by file ownership for parallel work), AOP8 (wide-shallow dependency graphs), AOP9 (dispatch prompts must include acceptance criteria, owned files, and out-of-scope), and AOP10 (detect workload imbalance between agents).

Read `[sdlc-root]/knowledge/architecture/model-tier-strategy.yaml` for model/effort tier matching — especially MTS4 (reviewer tier at or above implementer tier for high-risk domains) and MTS5 (escalate a thrashing worker's tier instead of re-dispatching a third time).

Dispatch independent phases in parallel using multiple Agent tool calls in a single message. If you find yourself editing files directly instead of dispatching an agent, stop — that violates the Manager Rule. When dispatching 2+ agents in parallel, follow `[sdlc-root]/process/parallel-dispatch-monitoring.md`. The critical rules: (1) read EVERY agent's output before deciding next steps — do not act on the first agent's result while others are still pending; (2) check for file conflicts via `git diff --stat` after parallel agents return; (3) apply the 3-strike rule for stuck agents; (4) on retry, revise the prompt — do not re-send the same prompt verbatim.

**Cross-domain knowledge injection:** When a phase requires an agent to work in a context outside its primary domain, consult `[sdlc-root]/knowledge/agent-context-map.yaml` for the other domain's agent and include those knowledge files in the dispatch prompt. Use judgment — only inject when the agent is genuinely crossing into unfamiliar territory (e.g., a backend agent implementing a feature that depends on real-time patterns, a frontend agent touching data layer code). Do not inject for routine single-domain work.

**POST-GATE** — a phase is NOT complete until this block appears in your response. Use the compact form by default; fall back to verbose when a trigger fires.

Compact form (happy path — all checks clean):

```
✓ Phase [N] — [X/Y tests pass] · [0 regressions] · [0 stubs] · build: pass
```

If something is not clean but doesn't warrant the full verbose form, indent caveats under the status line with `⚠`:

```
✓ Phase [N] — 6/6 new tests pass · 0 regressions · 0 stubs · build: pass
  ⚠ 36 pre-existing failures in test_session_start.py (baseline — will be fixed by Phase 2 patch-target rename)
```

Verbose form (use when any of these triggers fires):
- **Build fails** — any command from the project's CLAUDE.md returns non-zero
- **File deviation** — agent modified files not listed in the plan for this phase
- **Stubs found on final phase** — stub audit caught placeholder code that won't be filled by a later phase
- **Phase bleeding** — agent covered scope belonging to a subsequent phase
- **Re-dispatch needed** — partial completion requires a re-dispatch within this phase
- **Data audit mismatch** — phase produced data artifacts and the count doesn't match the plan

```
POST-GATE Phase [N] — [phase name]
Build: pass | fail (command: [build command] — see project CLAUDE.md)
Planned files: [list from plan]
Actual files: [list from git diff / agent report]
Deviations: [none | list of extra files with reason — logged, included in result doc]
Stubs: [none | list with file:line and disposition: deferred-to-phase-N | defect — re-dispatch pending]
```

- **Stale diagnostic dismissal (anti-pattern):** Do not dismiss build warnings or diagnostics as "stale" or "LSP catching intermediate state." Every warning is potentially real. If a build tool reports an unused variable, type error, or import issue, dispatch the phase agent to verify and fix — do not reason the warning away yourself. Warnings dismissed as stale in one round reliably resurface as real findings in the next review round.

- **UI smoke check (auto-detected):** If this phase modified UI-affecting files (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.cshtml`, `.css`, `components/`, `pages/`, `views/`, `templates/`) AND a dev server command is known (from the project's verify skill at `.claude/skills/verify/`, or its CLAUDE.md), run an inline visual smoke check before marking the phase complete. When the verify skill exists, launch, sign in, health-check, drive the affected page with its handles and clean up through it, keeping its Safety Rules. A launch or health-check failure is a smoke failure: re-dispatch the phase agent with the command and its output. The only exception is a cause the phase's changes can't have made, as the verify skill reports it: an instance it didn't start holds the port, or the driving tool is missing. Then output `UI smoke: skipped — [reason]` and `Console: skipped`, and go on. Using Playwright MCP (if available) or manual inspection: navigate to the affected page, verify it renders without a blank screen, take a screenshot, and check the browser console for runtime errors. Output in the POST-GATE block:
  ```
  UI smoke: ✓ renders clean | ✗ [describe failure] | skipped — [reason]
  Console: ✓ no errors | ✗ [error count and summary] | skipped
  ```
  If the smoke check fails, re-dispatch the phase agent with the screenshot and console errors. Do not proceed to the next phase with a broken render — downstream UI phases build on a broken foundation and compound the debugging effort. Skip this check for backend-only phases (controllers, models, migrations, services) and for projects with no runnable dev server. Consult `[sdlc-root]/knowledge/testing/advanced-test-patterns.yaml` § `playwright_mcp_verification` for tool patterns and the auto-detect heuristic.

**File deviation check (mandatory):**
1. List every file the plan specifies for this phase (created or modified)
2. List every file the agent actually created or modified (from the git diff or agent report)
3. Compare the two lists. Any file in list 2 that is NOT in list 1 is a deviation — regardless of whether the agent describes it as "related", "fixing the same pattern", or "obviously necessary"
4. If any deviation exists: log the deviation (file name and reason) and continue execution. Include all deviations in the result doc's Deviations section. Do not stop for approval — but do not silently absorb them either; they must be visible in the final report.

**Add-ons and follow-ups.** A small follow-up the work turns up is finished in this deliverable as an **add-on**: no decision CD hasn't made, inside the files or area the plan touched, dispatched to the domain agent like any change, verified like planned work, and listed in the result doc's Add-ons section. A knowledge entry or parking-lot note the change makes wrong is corrected in the same deliverable (SDLC hygiene), not deferred. Anything bigger is a **Follow-Up Item**: an id (`F1`, `F2`, ...), an issue-ready title, and why it isn't done now, including the plan's own deferrals. Never drop one silently. Where the project files follow-ups as issues (the software factory files checked items when CD merges an executed plan), they become issues; otherwise the completion report proposes them to CD.
5. **NEVER revert a deviated file.** Do not run `git checkout --`, `git restore`, or any command that discards changes in the deviated file. The file may contain the user's concurrent uncommitted work that predates this session. If you believe the deviation is harmful, ask the user via `AskUserQuestion` — but the default is to keep and log, never to revert.

- **Phase bleeding check:** If an agent returns work that covers scope belonging to a subsequent phase (within plan-listed files): (1) output a one-line note to CD identifying which phase was anticipated, (2) in the subsequent phase's dispatch prompt, include a summary of what the earlier agent already implemented and instruct the agent to verify completeness and implement only what remains. If the bleeding substantially changes a subsequent phase (e.g., makes it a verify-only pass), flag to CD rather than silently absorbing. Document any skipped or substantially reduced phases in the result doc under 'Skipped Phases'.

- **Re-dispatch within the same phase (partial completion):** If an agent returns work that is incomplete (missed a component, left TODOs, partially implemented scope), re-dispatch that agent with a PRE-GATE block labeled `Phase [N] re-dispatch — [brief reason]`. The PRE-GATE documents what was missed and why the re-dispatch occurred. Omitting the PRE-GATE for re-dispatches creates untracked sub-phases that can cause drift between the plan and the implementation.

- **Stub audit (mandatory):** After each phase completes, grep the plan-specified files for stub indicators: `TODO`, `FIXME`, `NotImplementedError`, `not yet implemented`, `placeholder`, `raise NotImplementedError`, `pass` as a lone function body, hardcoded return values on functions the plan specified as real implementations (e.g., `return True`, `return []`, `return None` where the plan requires actual logic).
  - **Intermediate phases:** Log any stubs found as tracked items. Include them in the next phase's dispatch prompt so the implementing agent knows they exist and must be filled. This is expected — phased execution legitimately stubs things in early phases that get filled later.
  - **Final phase (or single-phase plans):** Stubs are defects. Re-dispatch the phase agent with a PRE-GATE block listing every stub found, requiring real implementation. Do not proceed to the review-fix loop with known stubs — they will pass code review because they are syntactically valid code. A stub that builds clean is the hardest defect to catch in review; catch it here instead.

- **Data audit (mandatory for phases that produce data artifacts):** If this phase created or modified a seed script, scraper, allowlist, or any file containing data values (not just code logic), verify the data against its authoritative source before marking the phase complete. For each data category: check the count matches the plan's expected count, confirm no fabricated entries exist, and confirm no entries are missing. If any value cannot be traced to a source, flag it via `AskUserQuestion`. Code review catches code quality — the data audit catches data accuracy. These are separate concerns.

Do not start dependent phases until the dependency's POST-GATE clears.

```
Phase 1: Data schema + shared types (independent)
Phase 2: Backend endpoints (depends on Phase 1)
Phase 3: UI components (depends on Phase 1, NOT Phase 2)

-> Phase 1 runs first (PRE-GATE → EXECUTE → POST-GATE)
-> Phase 2 and Phase 3 run in parallel (both only depend on Phase 1)
```

### 2. Completion Review

**MANDATORY — NO PAUSE.** When the last phase's POST-GATE clears, proceed directly to the review loop. A brief phase summary is fine, but do not stop and wait for user input — no "what's next?", no "ready to review?", no waiting for confirmation. The plan already defines the review agents — emit the REVIEW-GATE line and dispatch them in the same response. Phase completion is a waypoint, not a stopping point.

You must emit this line before dispatching review agents:

```
REVIEW-GATE: phases [list] done — entering completion review
```

The Step A roster line that follows names the reviewers (plan agents + `code-reviewer` + `software-architect`).

After ALL phases are done, run the **Review-Fix Loop** (over the work after the last production gate, when the plan has gates) per `[sdlc-root]/process/review-fix-loop.md`. Agent source for round 1: the plan's agent assignment table, plus `code-reviewer` and `software-architect` if the plan omits them, plus any domain surfaced during implementation. Every round — not just round 1 — emits the `review-fix-loop.md` Step A roster line (`Review round N of 3 — dispatching (full roster | narrow: raisers + standing reviewers): …`) before dispatch. For user-facing changes, also run experiential verification (`review-fix-loop.md` Step 0.5) before the first round: start the dev server and walk the golden path, check adjacent features, verify scroll/resize, and check state transitions. Fix experiential failures before entering agent review.

<!-- MIRROR-START: review-fix-loop.md#code-review-mechanics -->
**Review-fix loop — critical mechanics.** Canonical protocol: `[sdlc-root]/process/review-fix-loop.md`. Shared definitions (severity, deduplication, Open Minor Findings): `[sdlc-root]/process/finding-classification.md`. These steps are inlined so that skipping the read does not skip the behavior.

1. **Verification gate before every round.** Run tests, type checks, lint, and configured static analysis before the first review round and again after every fix round. Fix failures before dispatching reviewers. (Reference docs have no build gate; they skip this step.)
2. **Fresh reviewer subagents, every round.** Dispatch each reviewer as a new subagent in its own context window — never inline, never a resumed reviewer from an earlier round. Re-review prompts include the previous round's findings table and the fix diff, require reading the current artifact rather than recalling it, ask for regressions beyond the prior findings, and state that a clean report is an expected, acceptable outcome. Reviewers report findings only; they never fix.
3. **Deduplicate, calibrate, then classify.** Merge duplicates first: the same issue at the same location becomes one finding that keeps the highest reported severity. Then calibrate every severity by impact × likelihood before labelling it. Then classify each finding in the Classification Table. Never downgrade a severity to reach the exit bar.
4. **Fix critical and major findings each round.** Resolve every INVESTIGATE and DECIDE finding. Minor FIX findings wait: once no critical or major findings remain, they get one batched fix pass. Before dispatching any fix, record the pre-fix snapshot — the tree hash printed by `t=$(mktemp); cp "$(git rev-parse --git-dir)/index" "$t"; GIT_INDEX_FILE="$t" git add -A; GIT_INDEX_FILE="$t" git write-tree; rm -f "$t"` (it includes untracked files and never touches the working tree or the real index) — and run the same command after the fixes for the post-fix snapshot.
5. **Re-review roster is mechanical.** After every fix round, including the minor batch pass: if any applied fix was `critical` or `major`, or the touched files (`git diff --name-only` between the pre-fix and post-fix snapshots) go beyond the files named in the fixed findings, dispatch the **full roster**. Otherwise dispatch **only the reviewers who raised the fixed findings, plus the standing reviewers** (code-reviewer and software-architect; for reference docs, the skill's standing reviewer, code-reviewer), scoped to the fix diff. A fix that touches a new domain adds that domain's reviewer. Read the Severity column and compare file sets; do not reason about relevance.
6. **Exit bar.** The loop exits when no `critical` or `major` FIX finding remains open, no INVESTIGATE or DECIDE finding is unresolved, and the accumulated minors have had their one batched fix pass (or the cap leaves no round to re-review it). Minor FIX findings still open go in an **Open Minor Findings** table. They are never silently closed; only CD closes them.
7. **Three-round cap.** At most 3 review rounds per loop: the first round plus up to 2 re-reviews. Every round counts, including the re-review after the minor batch pass and rounds re-opened by External Review Gate findings. At the cap with any `critical` or `major` finding open: stop, escalate to CD via `AskUserQuestion` with the open-findings table, and never claim the loop is clean. At the cap with only minors open: exit with the Open Minor Findings table.
<!-- MIRROR-END: review-fix-loop.md#code-review-mechanics -->

**Self-applied fixes:** fixes passing the Manager Rule's delegation-economics test may be self-applied — they re-enter the next review round like any other fix; the rest are dispatched to domain agents.

**Triage output format (mandatory).** When you collect findings and classify them, emit the canonical Classification Table from `[sdlc-root]/process/finding-classification.md` — one row per finding with columns `# | Finding | Agent | Classification | Severity | Rationale`. Do NOT emit two free-form bullet lists ("Will fix:" / "Out of scope:") with agent names in brackets. The canonical table puts every finding on the same scannable axis; the bullet-list shape forces the reader to re-parse classification from prose ("logged in result doc", "pre-existing systemic", "accepted trade-off"). After the table, dispatch the FIX rows being fixed this round (critical and major, or the minor batch pass) in a single batch — no narration between table and dispatch.

**Plan contract briefing (mandatory):** When dispatching review agents in the loop, each agent's prompt must include the plan's specification for the phases they are reviewing — specifically: the expected behavior, acceptance criteria, and implementation approach from the plan. Reviewers check "does the implementation match what was specified?" in addition to "is the code well-written?" A well-structured stub passes code quality review but fails plan compliance review. Without the plan contract, reviewers can only assess code quality — they cannot detect whether the agent delivered what was actually asked for.

**Review lenses (mandatory):** each reviewer's prompt also names `[sdlc-root]/process/review-lenses.md` and tells the reviewer to apply the lenses that fit the diff, per its § Lens Applicability: every lens, with the frontend- and API-conditional ones only when the diff touches those files. The plan contract says what was asked for; the lenses say what to check the code for.

**External Review Gate (Step E, optional):** If `[sdlc-root]/external-review.sh` exists and is executable, run the cross-vendor gate after the internal loop meets its exit bar — its findings re-enter triage, deduplicated and calibrated alongside internal findings, the external model never fixes, and any data egress is stated to CD first. Every internal round its findings re-open counts toward the three-round cap; the gate also keeps its own limit of 2 fix rounds, whichever is reached first, with leftovers going to CD via `AskUserQuestion`. A wrapper error is recorded as "external gate errored — skipped" and never blocks the commit. Skip silently if absent. See `[sdlc-root]/process/external-review-gate.md`.

**Round-cap escalation outcome:** if the loop stops at the cap with critical or major findings open, CD's answer to the escalation decides what happens next. Do not proceed to step 3 until the exit bar is met or CD explicitly directs you to. If CD directs you to proceed with critical or major findings still open, do not output the "Review loop complete" announcement below — list the still-open findings, with their severity and CD's direction, in the result doc's Open Minor Findings section (`[sdlc-root]/process/review-fix-loop.md` § Round Cap), then go to step 3.

When the loop finally exits — including Step E when enabled — output "Review loop complete — no critical or major findings open (N open minor findings listed). Proceeding to Worker Agent Reviews." then go to step 3. Carry any open minors into the result doc's Open Minor Findings section.

### 3. Worker Agent Reviews Output

Every execution MUST end with a Worker Agent Reviews section. This step is only reached when the review loop has exited under its exit bar — no critical or major findings open, no INVESTIGATE or DECIDE unresolved — or when CD has directed you to proceed at the round cap (see Round-cap escalation outcome). Save as: `docs/current_work/results/dNN_name_result.md`

```markdown
## Worker Agent Reviews

Key feedback incorporated:

- [agent-name] specific, concrete feedback that was incorporated or addressed
- [agent-name] another specific feedback point with actionable detail
- [agent-name] what they caught during review and how it was resolved
```

**Rules:**
- Bracket the agent's exact name: `[frontend-developer]`, `[software-architect]`, etc.
- Each bullet is specific and concrete — not generic praise
- Include feedback from the completion review (step 2)
- Open minor findings go in the result doc's **Open Minor Findings** section (`[sdlc-root]/templates/result_template.md`), not in this list
- Omit agents that found no issues (don't write "[agent] no issues found")
- This section is **mandatory** — the task cannot be marked complete without it

**Post-write: offer an explainer or a walkthrough.** Ask CD whether they want an HTML explainer (`sdlc-explain`, **result** storyboard) or a guided walkthrough (`sdlc-walkthru`) of the result doc — never unprompted. Mechanics and the precedes-approval rule: `[sdlc-root]/process/html-rendering.md` § Post-Skill Offer.

### 3a. Architecture Decision Crystallization Check (skip-if-absent)

If `docs/architecture/decisions/` does not exist, emit `Architecture decisions: directory not present — skipped` and proceed to 3b.

If the directory exists, scan the completed work for crystallization signals (see `[sdlc-root]/process/adr-practice.md` § Crystallization Signals). If any signal fired:

1. Dispatch the architect agent to draft an ADR using `[sdlc-root]/templates/decision_record_template.md`
2. The ADR is saved to `docs/architecture/decisions/adr-NN_{slug}.md` with the next sequential number
3. Update `docs/architecture/decisions/_index.md` with the new entry
4. The ADR is committed with the code that crystallized it — same commit (step 3c or step 4)

If no crystallization signal fired, emit `Architecture decisions: none — conforms to existing ADRs` in the result doc and proceed.

### 3b. Discipline Capture

Run the discipline capture protocol from `[sdlc-root]/process/discipline_capture.md`. Context format: `[DNN — phase N]`. The procedure:

1. **Structured gap detection** — 3 comparisons using session data:
   - Knowledge loaded vs. needed: could a knowledge file have prevented any FIX finding?
   - Cross-domain friction: did agents struggle outside their primary domain?
   - Iteration cost: did the review-fix loop run >2 rounds with recurring findings?
2. **Freeform insight scan** — look for insights that are reusable, non-obvious, and cross-discipline
3. **Write to parking lots** — append to `[sdlc-root]/disciplines/*.md` under `## Parking Lot`, one bullet per insight, marked `[NEEDS VALIDATION]`

Skip if nothing surfaced — do not fabricate entries. Budget: <3 minutes total. The manager writes these directly (process documentation, not domain content).

Entry format (context tag in bold header — required for `sdlc-archive` traceability):
```markdown
- **[YYYY-MM-DD] [DNN — phase N]**: [Insight title] — [description]. [NEEDS VALIDATION]
```

No PROJECT-SECTION markers needed — discipline files are project-specific and not overwritten during framework migrations.

### 3c. Per-Phase Commits (Mandatory)

After each phase's POST-GATE clears, commit the phase's work before starting the next phase. **Documentation artifacts ship with their work** — discipline entries, knowledge updates, and any other SDLC artifacts produced during the phase go in the same commit as the code, not in a separate doc commit.

1. Stage **all** files created or modified by the phase's agent(s) — this includes:
   - Application code and test files
   - Discipline parking lot entries (`[sdlc-root]/disciplines/*.md`) if discipline capture added entries
   - Any other SDLC artifacts produced during the phase
2. Commit with the z-sdlc format: `feat[DNN](phase-N): [phase name] — [brief description]`
3. Do NOT wait until all phases are complete to commit

This ensures each phase is independently reviewable, bisectable, and revertable. A single monolithic commit at the end defeats the purpose of phased execution.

**Exception:** If two phases run in parallel and both pass their POST-GATEs, they may share a single commit if the files don't overlap. Document which phases are included.

### 3d. CLAUDE.md Refresh

After discipline capture and per-phase commits, scan the deliverable for changes that invalidate or extend the project's CLAUDE.md. The work just shipped — this is the moment to update project memory before context fades. Refresh updates ship in the step 4 final commit alongside the work that motivated them; do not commit CLAUDE.md separately.

**Trigger scan.** Compare the deliverable's diff against the existing CLAUDE.md files (project root and any module-/package-level CLAUDE.md the work touched). Update CLAUDE.md only when one of these triggers fired during execution:

| Trigger | What changes in CLAUDE.md |
|---------|---------------------------|
| New convention introduced (naming, error handling, state pattern, testing approach) | Add to conventions section |
| Build / test / lint / dev command added, removed, or renamed | Update commands section |
| Architecture shift (new layer, package boundary, contract surface, deployment model) | Update structure / architecture section |
| Files or directories moved, renamed, or deleted that CLAUDE.md references by path | Fix path references |
| New dependency with non-obvious usage (config, gotchas, version pin, opt-in flag) | Add to dependencies / gotchas section |
| Feature, path, or module that CLAUDE.md still describes was removed or deprecated | Remove or mark deprecated |

If no triggers fired, emit `CLAUDE.md refresh: no changes needed` and proceed. Do not pad CLAUDE.md with session-specific narration — only persistent project knowledge belongs there.

**Update rules:**
1. Identify which CLAUDE.md file(s) need updates — root, package-level, or both.
2. Make surgical edits to the affected sections only. Do not rewrite untouched sections.
3. Do not paste deliverable summaries ("D-042 added session refresh"). CLAUDE.md describes *how the codebase works*, not deliverable history — that lives in the result doc and the chronicle.
4. Do not document conventions that the next deliverable will touch again. Wait until the convention stabilizes.
5. Do not log review-fix findings as CLAUDE.md content. Findings belong in disciplines.

### 4. Final Verify, Commit, and Mark Complete

**Principle: documentation artifacts ship with their work.** Result docs, catalog updates, discipline entries, and archive moves are part of the deliverable — not afterthoughts. They go in the same commit as the work they describe. Never create separate doc-only or `sdlc`-type commits for artifacts that belong to a work commit.

Before claiming the work is done:

1. Run the full build (`[build command]` — see project CLAUDE.md)
2. Confirm build passes with zero errors
3. Review the git diff for unintended changes (should be minimal — most work committed per-phase)
4. Update `docs/_index.md` — change the deliverable's status from "In Progress" to "Complete" in the Active Work table
5. Stage any remaining modified files — **all categories, not just application code:**
   - Result doc (`docs/current_work/results/dNN_*_result.md`)
   - Spec file (`docs/current_work/specs/dNN_*_spec.md`) — status marker updated to Complete
   - Plan file (`docs/current_work/planning/dNN_*_plan.md`)
   - Idea brief (`docs/current_work/ideas/dNN_*_idea.md`) if associated with this deliverable
   - Catalog updates (`docs/_index.md`)
   - Discipline parking lot entries (`[sdlc-root]/disciplines/*.md`)
   - Knowledge store updates (`[sdlc-root]/knowledge/*.md`)
   - CLAUDE.md updates from step 3d (root and any module-level files)
   - Process changelog (`[sdlc-root]/process/sdlc_changelog.md`) if updated
   - Review fixes from the review loop
6. Commit using the z-sdlc commit format:
   ```
   {type}[{deliverable_id}]({scope}): {description}

   {optional body — brief summary of what was changed and why}

   Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
   ```
   **Types:** `feat` (new feature), `fix` (bug fix), `refactor` (restructure, no behavior change), `docs` (documentation only), `test` (adding/updating tests), `chore` (build, config, tooling, dependencies), `style` (formatting, no logic change), `perf` (performance improvement), `ci` (CI/CD changes), `sdlc` (SDLC process, skills, agents, or framework changes)
   **Example:** `feat[D-042](auth): add session refresh endpoint`
7. If on a feature branch, push and create a PR. Write step 5's report sections first, then open the PR from them in the template's PR form, after the template's fresh-reader check (`[sdlc-root]/process/writing-for-cd.md` § Completion Reports); step 5 then emits the report. **Headless run:** do neither; list both under the result's `outbound`, and fill the caller's PR-description schema fields from the report's sections.
8. Emit the **Completion Report** (step 5). It names the commits; the full message stays in git.

### 5. Completion Report

Every execution MUST end with a Completion Report presented to the user, emitted after all commits are made. It is what CD reads to understand the change. Its shape is shared with the other execution skill and defined in `[sdlc-root]/process/writing-for-cd.md` § Completion Reports. (**Headless run:** the Headless Result follows the report as the very last output — `[sdlc-root]/process/headless-mode.md`. With a caller schema, the block's last rule applies.)

Commits lists every commit made during execution (per phase and the final commit from step 4).

<!-- MIRROR-START: writing-for-cd.md#completion-report -->
**Completion Report.** The report is the code variant of `[sdlc-root]/templates/pr_description_template.md`: the same sections in the same order, with bold labels instead of headings (they read better in a terminal), What was built in place of What you're approving, What you need to do first and Commits last. About 500 words, not counting What you need to do and Commits. Read the template's section rules and its Risk Tiers, with the project's always-high areas, before writing it. The result doc keeps the full record of every file, test and finding.

```
# [deliverable ID] done: [what was built, in plain words]

**What you need to do**
- [a step outside the code: deploy, migration, environment variable, account, API key]
- [ ] [a smoke test: what to do in the app, and what to check]

**The problem**
[What prompted this, and the symptom a user saw, in 1–2 sentences.]

**What changes for users**
- [each visible change, in the user's terms] — or: Nothing visible.

**What was built**
1. **[the behavior now in the code]** [the alternative it rejects, only where one was weighed]

**Deviations from the approved plan**
- [what changed from the plan, and why] — or: None.

**Scope**
- Tackled: [what this did]
- Not tackled: [what was deliberately skipped or left incomplete, and why]
- Add-ons: [each small fix beyond the plan, its files, and how it was verified]
- Follow-ups: [each Follow-Up Item as `F1: title`; checked ones are filed as issues where the project does that]

**Scope integrity:** No tests or CI checks weakened; touched only the planned files. — or each exception with its reason.

**Risk:** [Low | Medium | High], [why]. [The top 1–3 risks.] Undo: [how].

**Review focus**
- [where CD should look first, and why]
- [each critical or major finding CD directed past the review cap: severity, finding, CD's direction]
- [N] open minor findings, listed in the result doc

**How it was verified**
- `[command]`: [the result, with counts]
- [a UI check and what it showed]
- Not run: [the check, and why]

**How it works**
[The approach and how the pieces fit, in a short paragraph.]

**Learn the change**
- Files, in reading order: `path`: [its role in this change]; `path`: [role]
- Concepts: **[term]**: [plain definition]

**Commits**
- `{short-sha}` {commit title}
- Full record: `[the result doc's final path]`
```

- **Always present:** The problem, What changes for users, What was built, Deviations (`None.` when there were none), Scope's Tackled line, Scope integrity, Risk, Review focus, How it was verified, How it works, Learn the change's Files line, and Commits. **Left out when empty:** What you need to do, Not tackled, Deferred, a Review focus finding line with nothing to list, and Concepts.
- **What you need to do comes first,** because it is what CD acts on. It holds the deployment guide (manual deploy steps, environment variables, migrations, database changes, account setup) as bullets, and smoke tests as checkboxes. A change users can see always gets at least one smoke test. Smoke tests are user-facing actions: "Open the app and navigate to X", "Try creating a Y", "Check that Z appears on the dashboard". They are things you do in the running application, not CLI commands, unless the deliverable is CLI or terminal tooling.
- **A skipped phase** goes under Deviations, with its reason.
- **Evidence, not claims.** How it was verified shows this session's commands and results. Scope integrity comes from the POST-GATE file-deviation log and `git diff --stat` of the work over test and CI paths: a deleted, skipped or loosened test or check is an exception, with its reason.
- **Commits:** one line per commit made during execution.
- **A pull request** carrying the work uses these sections in the template's PR form (headings, What you're approving, the agent record collapsed, no What you need to do or Commits), and passes the template's fresh-reader check before it opens.
- **Headless run with a caller schema:** the sections fill the schema's PR-description fields instead of being printed.
<!-- MIRROR-END: writing-for-cd.md#completion-report -->

### Session Handoff

The Manager Rule remains in effect per `[sdlc-root]/process/manager-rule.md` — see the Session Scope section.

## Agent Selection Reference

The plan identifies which agents are relevant. If you need to add agents not listed in the plan (e.g., a security concern surfaces during implementation), refer to the full agent tables in the `sdlc-plan` skill's Agent Selection section.

- **Project-level agents**: `.claude/agents/` (project root)
- **Personal-level agents**: `~/.claude/agents/`

## SDLC Integration

This skill produces the third SDLC artifact:

| Artifact | Saved To | Step |
|----------|----------|------|
| Result | `docs/current_work/results/dNN_name_result.md` | 3 |

The spec and plan were produced by `sdlc-plan`.

When the deliverable is complete, the "Let's organize the chronicles" command moves artifacts from `current_work/` to `docs/chronicle/{concept}/` and updates `docs/_index.md`.

## Red Flags

| Thought | Reality |
|---------|---------|
| "This file wasn't in the plan — I'll revert it" | NEVER revert files you didn't create. The file may contain the user's concurrent work. Log the deviation; ask via `AskUserQuestion` if concerned. `git checkout --` on someone else's work is destructive and irreversible. |
| "The gate is just a deploy; I'll run it so execution keeps moving" | You never do a gate's steps, and neither does an agent. CD does them, or the project's runner after CD approves (`[sdlc-root]/process/production-gates.md`). |
| "The phases passed their POST-GATEs; the code is ready for the gate" | A gate never ships unreviewed work. Run the review loop over the work since the last gate, commit, then stop at the gate. |
| "The gate failed, but the next phase can work around it" | A failed gate stops execution. CD decides: roll back, retry or stop. |
| "There's no plan, I'll wing it" | Stop. Use `sdlc-plan` first. |
| "This plan is very large — I should confirm scope before starting" | Size is not a confirmation trigger. The plan was approved in `sdlc-plan`; a scope question re-litigates that approval. Emit the Phase plan and dispatch wave 1 in the same response. |
| "I'll implement this part myself" | Only if it passes the delegation-economics test (small, mechanical, no new context, cheaper than dispatch) — and it still gets reviewed. Otherwise dispatch the worker domain agent. See Manager Rule. |
| "This phase is small and well-defined, I'll do it directly" | Size is not an exception. Dispatch the agent. |
| "I'll implement directly to avoid context gaps from dispatching" | Complexity increases the need for agents, not decreases it. Pass the context you have to the agent in the dispatch prompt. |
| "I pre-read 8 files so now I have complete context and can implement" | Pre-reading is the first step toward self-implementation. Read the plan file; let agents read the implementation files they need. |
| "I'll just merge the conflict / fix the loose ends myself" | Parallel conflict or partial completion is still an agent task. Re-dispatch the affected agent. |
| "Findings are minor, ship it" | Minors get one batched fix pass once no critical or major findings remain. Any still open go in the result doc's Open Minor Findings table — never silently dropped, and only CD closes them. |
| "I dispatched most of the agents" / "Re-review is overkill" | Re-review is mandatory; its roster comes from the mechanical trigger, never judgment. Small, file-local minor fixes get the narrow roster (raisers + standing reviewers) — they never get no roster. Count the names on the roster line. Count the dispatches. They must match. |
| "I'll skip the PRE-GATE / POST-GATE" | The mandatory output blocks exist because these were skipped in 100% of early executions. Emit the block. |
| "One more iteration and I'll get it" | The loop is capped at three review rounds. At the cap with critical or major findings open, escalate to CD with the open-findings table and documented attempts. |
| "This only touches the frontend" | Check. Features rarely affect one layer. If it changes data shape or API contract, backend must review too. |
| "I know a better way to do this" | Search first. If a pattern exists, follow it. Consistency beats cleverness. |
| "I'll fix it without triaging first" | Classify the problem in the Classification Table (2b) before attempting a fix. Wrong classification wastes iterations. |
| "This finding is about code I didn't modify in that file" | If the file is in the plan's Files list, the finding is in scope. File presence is the test, not function-level diff. |
| "The review loop finished cleanly" | Output the exit announcement before proceeding. Silent state transitions cause drift. |
| "Build passes, fixes are done — moving on" | Build-pass is not the review loop exit. After ANY fix round, re-run the verification gate and re-review with the roster the mechanical trigger picks. Only exit at the exit bar. Two audits caught this same skip. |
| "This is really a minor — I'll label it minor so the loop can exit" | Calibration applies impact × likelihood; it is never a lever for exiting. Downgrading severity to meet the exit bar is unilateral demotion. |
| "We're at the cap — close enough, call it clean" | At the cap with critical or major findings open, stop and escalate via `AskUserQuestion` with the open-findings table. Never claim the loop is clean. |
| "I'll resume last round's reviewer — it already has the context" | Every round uses fresh subagents. A resumed reviewer judges from memory of its own findings, and its growing context makes each round cost more. Pass the prior findings table and fix diff instead. |
| "The fix was tiny — skip the verification re-run" | The verification gate re-runs after every fix round, before any reviewer is dispatched. Reviewers are not a substitute for tests, types, and lint. |
| "All phases complete — here's a summary" *(then waits for user input)* | Summaries are fine — stopping is not. Emit the summary, then REVIEW-GATE and dispatch review agents in the same response. The plan defines the review agents; no user input is needed to proceed. |
| "I noted the file deviation but didn't log it" | Deviations don't require approval, but they MUST be logged in the POST-GATE output and included in the result doc's Deviations section. Silent absorption defeats traceability. |
| "This is a fix dispatch, not a phase dispatch" | Fix dispatches follow the same protocol as phase dispatches. |
| "Phase 2's agent did Phase 3's work — I'll skip Phase 3" | Note the overlap to CD. Dispatch Phase 3 to verify completeness and implement what remains. |
| "Data sources: read from these codebase files" (plan also mentions external source) | If the plan says data comes from an external source AND codebase files, the dispatch prompt must include BOTH. Listing only codebase files causes agents to hallucinate values for the external-source categories. |
| "This phase produces a scraper/consumer that should align with the seed/config from Phase N" | Tell the agent to READ the Phase N output file for canonical values. Agents will fabricate their own allowlists if not pointed at the canonical source. |
| "The plan is committed, this is just a small follow-up" | Manager Rule applies for the full session. Dispatch the domain agent. |
| "The user asked about the server code — I'll just fix it while I'm here" | Domain crossing. Dispatch the relevant domain agent for that scope. Read domain boundaries in agent definitions. |
| "I'll commit the code now and the docs separately" | Documentation artifacts (result docs, catalog updates, discipline entries, archive moves) ship in the same commit as the work they describe. Separate doc commits fragment the history and break bisectability. |
| "CLAUDE.md is fine, no need to refresh" *(without scanning)* | Step 3d is a scan, not a judgement call. Walk the trigger table against the diff before deciding. If no triggers fired, emit `CLAUDE.md refresh: no changes needed` — the explicit no-op is the protocol. |
| "Pasting the deliverable summary into CLAUDE.md" | CLAUDE.md describes how the codebase works, not deliverable history. Result docs and the chronicle hold "what shipped"; CLAUDE.md holds "what future agents need to know to navigate the code." |
| "I know how this library works" | Verify external library APIs via Context7 before writing integration code. |
| "These parallel phases don't overlap on files, dispatch them both" | File non-overlap is necessary, not sufficient. Also check: barrel/index files, contract artifacts (schemas, generated types), shared agent ownership, implicit side-effect ordering. See Parallel Phase Ownership Decomposition. |
| "Both phases need to add an entry to the barrel/index file — they can each edit it" | Barrel files are single-owner. Designate one phase as owner and pass the other's required entry via the dispatch prompt, or collapse the barrel edits into a sequenced coda phase. |
| "Frontend phase and backend phase touch different files, so they can run in parallel" | Logical dependency ≠ file overlap. If frontend consumes backend's schemas or generated types, backend produces the contract first. Dispatch the contract-producing phase, verify the artifact, then dispatch consumers. |
| "The parallel decomposition isn't working — I'll just serialize what's left and keep going" | Silent serialization hides the planning defect. Emit `REVISE_PLAN` triage and wait for CD. The discipline entry protects the next deliverable. |
| "Two phases are both assigned to the same agent but touch different files — run them in parallel" | A single agent session cannot be dispatched twice concurrently. Two phases sharing an agent owner must sequence, regardless of file non-overlap. |
| "Plan loaded. Let me check the catalog. Proceeding to Phase 1." | Pre-dispatch narration is noise. Read the plan, then emit the PRE-GATE — no filler sentences between tool calls and gates. |
| Two phases dispatched in parallel, two long PRE-GATE blocks emitted | Use the parallel comparison table form. One table with phase columns is faster to read than two stacked blocks. |
| Triage emitted as "Will fix:" + "Out of scope:" bullet lists with `[agent-name]` brackets | Use the canonical Classification Table from finding-classification.md. Bullet lists force the reader to re-parse classification from prose. |

## Integration

- **Feeds into:** `sdlc-tests-run` (post-commit test verification), `sdlc-archive` (when deliverable is complete)
- **Uses:** worker domain agents (implementation + review), `sdlc-plan` output (the plan file), `[sdlc-root]/process/manager-rule.md`, `[sdlc-root]/process/collaboration_model.md`, `[sdlc-root]/process/review-fix-loop.md`, `[sdlc-root]/process/finding-classification.md`, `[sdlc-root]/process/production-gates.md` (review, commit and stop at each production gate; step 0), `[sdlc-root]/templates/pr_description_template.md` (code variant, steps 4–5), `[sdlc-root]/process/writing-for-cd.md` (§ Completion Reports, step 5)
- **Complements:** `sdlc-lite-execute` (handles lite deliverables), `sdlc-audit` (can audit execution quality post-hoc)
- **Does NOT replace:** `sdlc-plan` (plan must exist before execution), `sdlc-tests-run` (separate test verification step)