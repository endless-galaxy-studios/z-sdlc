# Review-Fix Loop

The core validation pattern that determines when work is done. Every execution skill references this file for the post-completion review cycle.

---

## Overview

After all implementation work completes, verify that evidence exists (tests pass, linters clean), then dispatch the review roster — one reviewer per touched domain plus the standing reviewers — in isolated contexts. Collect findings, deduplicate and calibrate them, classify them, fix them, and re-review under a mechanical roster rule until the exit bar is met: no `critical` or `major` findings remain and no INVESTIGATE or DECIDE finding is unresolved. The loop is capped at three review rounds. It is mandatory and has no shortcuts.

This file owns the loop for **every review context** — code review (execution, `sdlc-review-code`, direct dispatch), plan review (§ Plan Review), and reference-doc review. Severity, deduplication, the scope-change marker, and Open Minor Findings are defined once in `[sdlc-root]/process/finding-classification.md`. Each skill that runs a loop carries a verbatim copy of one of the two mirrored critical-steps blocks in § Mirrored Critical-Steps Blocks.

## Step 0: Verification Gate (before agent review)

<!-- Source: Claude Code Best Practices (code.claude.com/docs/en/best-practices) — "Give Claude a way to verify its work."
     CS146S Wk 6: AI Testing and Security — SAST/DAST integration, Isaac Evans (CEO Semgrep).
     Semgrep blog: Agent-based vuln detection has ~85% false positive rate — tool verification first.
     Google AutoCommenter paper (AIware '24): AI review comments on unchanged code waste attention — scope to changed files.
     Reddit "How we vibe code at a FAANG": "Always write tests first" — tests before implementation, agent builds to pass. -->

Before dispatching any review agent, confirm that machine-verifiable evidence exists and passes. Agent review without verification is opinion — it catches style and design issues but cannot reliably catch functional bugs (agent-based vulnerability detection has a measured ~85% false positive rate). Verification catches functional bugs but cannot catch design issues. Both are required; verification comes first because it's cheaper and objective.

**Required checks (run all that apply):**

1. **Tests exist and pass** — If the plan or spec defines acceptance criteria, corresponding tests must exist. Run the test suite. If tests fail, fix them before entering the review loop — do not ask reviewers to evaluate broken code.
2. **Type checking passes** — If the project has a type system (TypeScript, mypy, etc.), run the type checker. Type errors are not review findings; they are build failures.
3. **Linter passes** — If the project has linting configured, run it. Lint violations are not review findings; they are automated checks that should pass before human review.
4. **Security scanning passes** — If SAST tooling is configured (Semgrep, ESLint security plugins), run it. Tool-detected vulnerabilities are machine-verified findings with higher confidence than agent opinions.

**Output the verification summary before proceeding:**

```
Verification gate:
- Tests: ✓ passed (47/47) | ✗ 3 failures — fix before review
- Types: ✓ clean | ✗ 2 errors — fix before review
- Lint: ✓ clean | ✗ warnings only (proceeding)
- SAST: ✓ clean | ○ not configured
```

**If any required check fails, fix it before proceeding to Step A.** Do not enter the review loop with known failures — this wastes agent context on problems that tooling already identified.

**If no tests exist for the implemented functionality:** This is itself a finding. Note it in the verification summary and flag it to CD before proceeding. The absence of tests means the review loop has no objective ground truth — agent opinions will be the only quality signal, which is insufficient for production code.

## Step 0.5: Experiential Verification (user-facing changes only)

**Applies when:** The implementation touches user-facing code — components, pages, styles, templates, layouts, navigation, or any change that alters what a user sees or interacts with. Skip for backend-only, infrastructure, or purely logic changes.

Machine verification (Step 0) confirms the code is correct. Experiential verification confirms the *experience* is correct. A feature can pass all tests, type checks, and linting while being unusable — duplicated controls, missing scroll behavior, invisible buttons, broken interaction flows. These are not bugs that automated tooling catches; they require using the app.

**Tooling:** If Playwright MCP (`@playwright/mcp` or equivalent) is configured in the project's `.mcp.json`, use it to automate the checks below — navigate, screenshot, inspect the DOM, read console errors. This replaces manual browser inspection with programmatic verification that produces artifacts (screenshots, console logs) the review agents can reference. If no browser automation MCP is available, perform the checks manually or flag to CD that automated experiential verification was not possible.

**Required checks:**

1. **Start the dev server** — the app must be running and reachable. If it cannot be started (missing env, broken deps), flag to CD and skip to Step A with a note that experiential verification was not performed.
2. **Walk the golden path** — navigate to the affected page and perform the primary user action the implementation enables. Does it work end-to-end as specified? With Playwright MCP: navigate to the page, interact with the primary flow, screenshot at each key state.
3. **Check adjacent features** — interact with features that share screen space or state with the change. Did anything regress?
4. **Verify scroll and resize** — scroll the page. Resize the viewport. Do controls remain accessible? Do sticky elements stick? Does content overflow correctly?
5. **Check state transitions** — trigger loading, error, and empty states where applicable. Does the UI communicate each state?
6. **Check console errors** — read the browser console for runtime errors (TypeError, failed imports, 404s, unhandled promise rejections). Console errors that appeared after the implementation are defects even if the page renders correctly.

**Output the experiential summary before proceeding:**

```
Experiential verification:
- Dev server: ✓ running | ✗ cannot start (reason) — skipping
- Golden path: ✓ works | ✗ broken (describe)
- Adjacent features: ✓ no regressions | ✗ regression in (describe)
- Scroll/resize: ✓ controls accessible | ✗ (describe what breaks)
- State transitions: ✓ all states handled | ✗ (describe missing states)
- Console: ✓ no errors | ✗ [error count] errors (describe)
- Tooling: Playwright MCP | manual | not available (reason)
```

**If any check fails, fix it before proceeding to Step A.** Experiential failures are functional bugs — they are not "suggestions" or "nice-to-haves." A sidebar that scrolls away, a button that's invisible, or a duplicated control section is a defect with the same severity as a failing test.

**Subagent browser verification (review dispatch):** When dispatching review agents in Step A for UI-heavy deliverables, include this in the dispatch prompt for `sdet`, `frontend-developer`, and `accessibility-auditor`: "If Playwright MCP tools are available, use them to verify your findings in the running app — navigate, interact, screenshot. Report what you observed alongside your code-level findings." This gives review subagents the ability to catch interaction bugs (broken drag-drop, missing focus management, keyboard trap) that code review alone cannot detect.

## Step A: Dispatch the Review Roster

**First-round roster (coverage, not headcount).** The roster is `code-reviewer` and `software-architect` (always dispatched) plus one reviewer for each domain whose files or concerns the change touches. Start from the plan's agent assignment table (or the original review's agent list) and add agents if new domains surfaced during implementation. "When in doubt" resolves toward covering a touched domain, never toward adding a second reviewer for a domain already covered. Beyond five reviewers, each additional agent needs a one-sentence statement of what it uniquely adds (AOP5). High-risk domains (MTS4) always get their specialist regardless of diff size. Review **lenses** are prompt content, not headcount — every dispatched reviewer gets every applicable lens, however small the diff. Read `[sdlc-root]/knowledge/architecture/agent-orchestration-patterns.yaml` for AOP5. Read `[sdlc-root]/knowledge/architecture/model-tier-strategy.yaml` for MTS4. Re-review rosters come from Step D, not from this rule.

**Review agents report findings only. They do NOT fix anything.** Fixes are dispatched in Step C after the manager classifies each finding. An agent that fixes inline during review has bypassed the triage gate — that is a process failure, not a shortcut.

<!-- Source: Claude Code Best Practices (code.claude.com/docs/en/best-practices) — Writer/Reviewer pattern with separate sessions.
     CS146S Wk 4: Human-agent collaboration patterns.
     Medium/OutsightAI, "Peeking Under the Hood of Claude Code": Sub-agents spawn with narrower context
       and no todo-list reminders — separate context prevents cognitive drift in specialized sub-tasks. -->

**Context separation rule:** Review agents MUST be dispatched as subagents (separate context windows), not inline in the orchestrator's context. This is not optional — it exists to prevent confirmation bias. An agent reviewing code in the same context that wrote it has access to the implementation rationale, the failed approaches, and the conversation history. This biases it toward approving the code because it "understands why" decisions were made. A reviewer in a fresh context sees only the code and the spec — it evaluates what was built, not why it was built that way. This mirrors the principle that code review should evaluate the artifact, not the author's intent.

**Fresh reviewers every round — no reuse.** Every review round dispatches **new** subagents. Never resume or continue a reviewer from an earlier round to save tokens: a resumed reviewer judges from memory of its own findings instead of re-reading the artifact (the failure Retraction Discipline in `[sdlc-root]/process/debate-protocol.md` exists to prevent), and its growing context makes each later round more expensive, not less. Re-review dispatch prompts carry:
- the previous round's findings table (after deduplication and classification),
- the fix diff,
- an instruction to read the current code (or plan, or doc) rather than rely on memory or the prior table,
- an instruction to look for regressions beyond the prior findings, not only to confirm them,
- the statement that a clean report is an expected, acceptable outcome.

**Plan contract injection (when available):** When the review-fix loop is invoked from an execution skill (`sdlc-execute`, `sdlc-lite-execute`), the plan document is available. Each reviewer's dispatch prompt must include the plan's specification for the work they are reviewing — expected behavior, acceptance criteria, and implementation approach. This enables **plan compliance review**: reviewers check "does the implementation match what was specified?" alongside standard code quality checks. Without the plan contract, a well-structured stub that builds clean will pass review — the reviewer has no way to know the plan required a real implementation.

Before dispatching, output the roster as one line (`[sdlc-root]/process/writing-for-cd.md` § Status Blocks):

```
Review round N of 3 — dispatching (full roster | narrow: raisers + standing reviewers): agent-name-1, agent-name-2, agent-name-3
```

Every name must have a corresponding agent dispatch. If the number of dispatched agents doesn't match the number of names, **stop and fix before proceeding**.

## Step B: Collect Findings

Wait for ALL dispatched agents to return. For each agent, record:
- Agent name
- Findings (or "no issues")

Output a findings table:

```
Review round N results:
| Agent | Findings | Severity |
|-------|----------|----------|
| agent-1 | specific finding | critical/major/minor |
| agent-2 | no issues | — |
```

**If any agent has findings → go to Step C.** If no agent has findings, apply § Exit Bar — minors accumulated from earlier rounds still get their batched pass (Step C); otherwise a clean round with no unresolved INVESTIGATE or DECIDE finding exits the loop.

## Step C: Triage + Fix

**Order: deduplicate → calibrate → classify.**

1. **Deduplicate** per `[sdlc-root]/process/finding-classification.md` § Finding Deduplication — same location and same issue merge into one finding (credit every agent, keep the highest reported severity); different issues at the same location stay separate.
2. **Calibrate** each finding's severity per `[sdlc-root]/process/finding-classification.md` § Severity Calibration — impact × likelihood, not the reviewer's alarm level. Record the rationale for any change. Never downgrade a severity to reach the exit bar.
3. **Classify** each finding in the Classification Table per `[sdlc-root]/process/finding-classification.md`.

**Security finding calibration:** Agent-based security review has a measured ~85% false positive rate (Semgrep 2025 study). Security agent findings that are not corroborated by tool output (Step 0 SAST results) should be scrutinized more carefully than findings from code-reviewer or architect agents. If a security finding seems plausible but uncertain, classify it as INVESTIGATE rather than FIX — verify it with a targeted tool scan or manual inspection before committing a fix that may be unnecessary.

**What gets fixed this round.** Fix every `critical` and `major` FIX finding. Resolve every INVESTIGATE (diagnose, then reclassify) and DECIDE (CD answers via `AskUserQuestion`). Minor FIX findings accumulate: once no `critical` or `major` findings remain, all accumulated minors get **one batched fix pass**, re-reviewed under Step D like any other fix round. Minors still open after that pass — or open when the round cap is reached — go into the Open Minor Findings table (§ Exit Bar).

**Pre-fix snapshot (before dispatching any fix).** Record the pre-fix state so Step D can compute the touched files without judgment:

```bash
# Prints a tree hash of the whole working tree — tracked changes AND untracked (non-ignored) files —
# built through a throwaway copy of the index. The real index and the working tree are never touched.
t=$(mktemp); cp "$(git rev-parse --git-dir)/index" "$t"; GIT_INDEX_FILE="$t" git add -A; GIT_INDEX_FILE="$t" git write-tree; rm -f "$t"
```

Record the printed hash in your round notes as the pre-fix snapshot (shell variables do not survive between tool calls). Run the same command after the fixes for the post-fix snapshot. Never use `git stash` (push), `git checkout`, a plain `git add`, or anything else that changes the working tree or the real index to take a snapshot — the working tree may hold the user's concurrent work. (`git stash create` is not a substitute: it omits untracked files, so edits to a newly created file — the usual case for new code and new docs — would be invisible.)

Dispatch the most relevant domain agent to fix each finding being fixed this round — this is often the agent who found it, but may be a different agent with deeper expertise in the affected file. If multiple findings need fixes, dispatch all of them before re-reviewing.

**Fix-intent constraint:** Per the No Semantic Revert rule (`[sdlc-root]/process/manager-rule.md`), fix dispatch prompts must include this constraint: "Fix this issue while preserving the existing behavior. Do not remove, simplify, or replace the feature to avoid the bug — address the root cause. If the behavior is fundamentally incompatible with the fix, report back instead of changing it." A fix agent that returns a "solution" that removes the feature it was asked to fix has not completed the task.

**Guard modification is in-scope:** If a FIX finding matches a cluster in `docs/reviews/recurring-patterns.yaml` that has (or plainly warrants) a mechanized guard, the fix is two-part — fix the instance AND update or create the guard (lint rule, drift test, CI check, or a design or type change confined to the finding's diff) so the next instance is caught mechanically, and show it failing on a pre-fix occurrence, per `[sdlc-root]/process/guardrail-lifecycle.md`. A wider design or type change is a PLAN or DECIDE finding, not a fix. Include the guard requirement in the fix dispatch prompt; guard edits go through the same re-review (Step D) as any other change. Skip silently if the pattern log doesn't exist.

**FIX failure escalation:** If a FIX fails twice (agent dispatched, finding persists), reclassify it as INVESTIGATE or PLAN per `[sdlc-root]/process/finding-classification.md` § FIX Failure Escalation. A headless run stops with `escalated` instead (§ Round Cap).

For anything that isn't a FIX, state what you don't know:
```
**Unknown**: [specific thing you haven't verified]
```

## Step D: Re-Review (Mandatory, Mechanical Roster)

After ALL fixes from Step C are applied — including the minor batch pass:

1. **Re-run the verification gate (Step 0)** — tests, type checks, lint, configured static analysis. Fix failures before dispatching reviewers.
2. **Compute the touched files:** take the post-fix snapshot (Step C command), then `git diff --name-only <pre-fix> <post-fix>`, plus any file a fixer reports touching. `git diff <pre-fix> <post-fix>` is the fix diff re-reviewers receive.
3. **Pick the roster mechanically:**
   - **Full roster** if (a) any applied fix was `critical` or `major`, or (b) the touched files go beyond the files named in the fixed findings.
   - **Otherwise, narrow:** only the reviewers who raised the fixed findings, plus the standing reviewers (`code-reviewer` and `software-architect`; for reference docs, see § Skill-Specific Variations), scoped to the fix diff.
   - In either case, a fix that touches a domain not covered by the roster adds that domain's reviewer.

   **This test is mechanical: read the Severity column and compare file sets; do not reason about relevance.**
4. **Return to Step A** with that roster and the re-review prompt contents from Step A.

Re-review is never skipped. "The fixes were small" decides only *which* roster re-reviews (via the test above), never *whether* re-review happens. Do not claim the loop is closed without a round that meets § Exit Bar.

## Step E: External Review Gate (optional, opt-in)

After the internal loop meets § Exit Bar — and before commit — run the
**External Review Gate** if the project has enabled it. This sends the converged
diff to a non-Claude model (Codex or a local LLM) for a maximally-independent
second opinion. The full protocol, wrapper contract, and data-egress rules are in
`[sdlc-root]/process/external-review-gate.md`.

Mechanics:

1. If `[sdlc-root]/external-review.sh` is absent or not executable, **skip
   silently** — the gate is optional. Otherwise continue.
2. State where the code is going (which model/endpoint) so CD sees any egress.
   For hosted providers not durably authorized, confirm with CD first. Never send
   secrets or `.env` content.
3. Run the wrapper with the payload (rubric + spec/plan context + diff). If it
   exits non-zero, record "external gate errored — skipped" and proceed to
   commit. **Never block a commit on external availability.**
4. Feed any returned findings into **Step C** triage exactly like agent findings —
   deduplicated against and calibrated alongside the internal findings, on the
   same severity scale. The external model does not fix — domain agents fix.
   External findings uncorroborated by tests or internal reviewers lean
   INVESTIGATE, not FIX.
5. If a FIX is applied, **return to Step D** (the internal loop re-opens; fixes
   can introduce new problems), then re-run the gate once the internal loop meets
   the exit bar again. **Every internal round the gate re-opens counts toward the
   three-round cap** (§ Round Cap).
6. The gate also keeps its own limit of 2 fix rounds. Both limits apply —
   whichever is reached first stops the loop, and the remaining findings go to CD
   via `AskUserQuestion` rather than looping.

The gate does not replace the internal loop and never runs before it. It is one
more ensemble member (`[sdlc-root]/process/debate-protocol.md` § Cross-Vendor
External Reviewer), deliberately chosen for independence.

## Exit Bar

The loop exits when **all three** are true:

1. No `critical` or `major` FIX finding remains open.
2. No INVESTIGATE or DECIDE finding is unresolved — INVESTIGATE has been diagnosed and reclassified; DECIDE has CD's answer.
3. The accumulated minor FIX findings have had their one batched fix pass and its re-review — or the round cap leaves no round to re-review it (§ Round Cap).

A clean round with no minors awaiting their batch pass meets the bar. So does a round whose only open findings are minors that already had their batched pass. Minor FIX findings still open at exit go into an **Open Minor Findings** table (shape and location per context in `[sdlc-root]/process/finding-classification.md` § Open Minor Findings). They are never silently closed — only CD closes them. Listing them is not demotion (`[sdlc-root]/process/manager-rule.md` § No Unilateral Finding Demotion); downgrading a severity to meet this bar is.

When the loop exits, announce it with the count of open minors: "Review loop complete — no critical or major findings open (N open minor findings listed)."

## Round Cap

**At most 3 review rounds per loop** — the first round plus up to 2 re-reviews. Every round counts: the re-review after the minor batch pass, and rounds started because External Review Gate findings re-opened the loop.

- **At the cap with any `critical` or `major` finding open:** stop. Output the open-findings table (finding, agent, severity, what each fix attempt returned, your hypothesis for why it persists), then escalate to CD via `AskUserQuestion` — do not type the escalation as conversational text. Save progress in a partial result doc if applicable. **Never claim the loop is clean.**
- **If CD directs you to proceed anyway:** do not announce "Review loop complete" — the exit bar was not met. List the still-open critical and major findings, with their severity and CD's direction, in the context's Open Minor Findings table (`[sdlc-root]/process/finding-classification.md` § Open Minor Findings), then continue.
- **At the cap with only minors open:** exit under § Exit Bar with the Open Minor Findings table. The batched minor pass is skipped if the cap has no round left to re-review it.
- **In a headless run** (no person present), the escalation is a stop: save the partial result doc, then end the run with status `escalated` and the open-findings table as its result. The run never claims the loop is clean and never continues past the cap on its own. DECIDE findings and unresolved INVESTIGATE findings mid-loop stop the run the same way, with status `needs-input`. A FIX that fails twice is not reclassified; it stops the run with `escalated`. PRE-EXISTING findings and minor PLAN findings do not stop it: they are listed under the result's `deferred`. A critical or major PLAN finding stops it with `needs-input`, because deferring it needs CD. Rule and result format: `[sdlc-root]/process/headless-mode.md`.

The cap replaces the former 3-strike rule. FIX failure escalation (a FIX that fails twice is reclassified) still applies within the cap in interactive runs; a headless run stops with `escalated` instead (the bullet above).

## Plan Review

Plan review (`sdlc-plan`, `sdlc-lite-plan`) uses this loop's definitions — fresh reviewers every round (Step A), dedup → calibrate → classify (Step C), § Exit Bar (its condition 3 does not apply — plans have no separate minor pass), § Round Cap, and the first-round roster rule in Step A — with these differences:

- **No verification gate.** There is nothing to build or test.
- **Severity is read as impact on the implementation if the plan is executed as written**, and every FIX finding also carries the `Scope change` marker (`[sdlc-root]/process/finding-classification.md` § Scope-Change Marker).
- **One revision dispatch per round.** All FIX findings go to the writing agent together; there is no separate minor batch pass. Minor FIX findings the revision does not incorporate go into the Open Minor Findings table in the plan file.
- **Re-review fires on scope change, not severity.** Re-review is mandatory if ANY of: (1) any FIX finding has `Scope change` = yes, (2) the revised plan's Files list differs from the pre-revision Files list, or (3) a phase was added, removed, or its assigned agent changed. Otherwise there is no re-review. These are exactly the cases the pre-2026-10 trigger fired on (trigger (1) used to read "Severity = `critical`", when critical *meant* scope change).
- **When re-review fires, it dispatches the full roster** — the round-1 roster line. Step D's narrow re-review does not apply to plans.
- **At the cap, an unreviewable revision escalates.** If round 3's revision would fire a re-review trigger, there is no round left to review it — escalate to CD under § Round Cap rather than exiting.

## Mirrored Critical-Steps Blocks

Skills that run a review loop must not reduce their loop steps to a bare "read and follow this file" pointer — the 2026-05-19 changelog entry ("Inline Critical Guardrails Lost in Skill Consolidation") records `sdlc-review-code` skipping the loop and falsely claiming it clean after exactly that consolidation. Instead, the critical steps are defined **once** here and each skill carries a **verbatim copy** of the relevant block:

| Block | Source section id | Mirrored in |
|-------|-------------------|-------------|
| Code-review mechanics | `code-review-mechanics` | `sdlc-execute`, `sdlc-lite-execute`, `sdlc-review-code`, `sdlc-create-reference-doc`, `sdlc-implement` and `sdlc-revise` (the `factory` bundle) |
| Plan-review mechanics | `plan-review-mechanics` | `sdlc-plan`, `sdlc-lite-plan` |

**Markers.** The source block below is wrapped in `<!-- MIRROR-SOURCE-START: {id} -->` / `<!-- MIRROR-SOURCE-END: {id} -->`. Each copy in a skill is wrapped in `<!-- MIRROR-START: review-fix-loop.md#{id} -->` / `<!-- MIRROR-END: review-fix-loop.md#{id} -->`. The lines between the markers must be **identical** — any difference is a drift finding (`sdlc-reviewer` § Cross-skill DRY; the framework audit's cross-skill DRY dimension). To change a block, edit it here and re-copy it into every skill that mirrors it. Context-specific behavior goes in the skill text outside the markers or in § Skill-Specific Variations, never inside a copy. Marker conventions: `[sdlc-root]/process/project-section-markers.md` § MIRROR Markers.

### Code-review mechanics

<!-- MIRROR-SOURCE-START: code-review-mechanics -->
**Review-fix loop — critical mechanics.** Canonical protocol: `[sdlc-root]/process/review-fix-loop.md`. Shared definitions (severity, deduplication, Open Minor Findings): `[sdlc-root]/process/finding-classification.md`. These steps are inlined so that skipping the read does not skip the behavior.

1. **Verification gate before every round.** Run tests, type checks, lint, and configured static analysis before the first review round and again after every fix round. Fix failures before dispatching reviewers. (Reference docs have no build gate; they skip this step.)
2. **Fresh reviewer subagents, every round.** Dispatch each reviewer as a new subagent in its own context window — never inline, never a resumed reviewer from an earlier round. Re-review prompts include the previous round's findings table and the fix diff, require reading the current artifact rather than recalling it, ask for regressions beyond the prior findings, and state that a clean report is an expected, acceptable outcome. Reviewers report findings only; they never fix.
3. **Deduplicate, calibrate, then classify.** Merge duplicates first: the same issue at the same location becomes one finding that keeps the highest reported severity. Then calibrate every severity by impact × likelihood before labelling it. Then classify each finding in the Classification Table. Never downgrade a severity to reach the exit bar.
4. **Fix critical and major findings each round.** Resolve every INVESTIGATE and DECIDE finding. Minor FIX findings wait: once no critical or major findings remain, they get one batched fix pass. Before dispatching any fix, record the pre-fix snapshot — the tree hash printed by `t=$(mktemp); cp "$(git rev-parse --git-dir)/index" "$t"; GIT_INDEX_FILE="$t" git add -A; GIT_INDEX_FILE="$t" git write-tree; rm -f "$t"` (it includes untracked files and never touches the working tree or the real index) — and run the same command after the fixes for the post-fix snapshot.
5. **Re-review roster is mechanical.** After every fix round, including the minor batch pass: if any applied fix was `critical` or `major`, or the touched files (`git diff --name-only` between the pre-fix and post-fix snapshots) go beyond the files named in the fixed findings, dispatch the **full roster**. Otherwise dispatch **only the reviewers who raised the fixed findings, plus the standing reviewers** (code-reviewer and software-architect; for reference docs, the skill's standing reviewer, code-reviewer), scoped to the fix diff. A fix that touches a new domain adds that domain's reviewer. Read the Severity column and compare file sets; do not reason about relevance.
6. **Exit bar.** The loop exits when no `critical` or `major` FIX finding remains open, no INVESTIGATE or DECIDE finding is unresolved, and the accumulated minors have had their one batched fix pass (or the cap leaves no round to re-review it). Minor FIX findings still open go in an **Open Minor Findings** table. They are never silently closed; only CD closes them.
7. **Three-round cap.** At most 3 review rounds per loop: the first round plus up to 2 re-reviews. Every round counts, including the re-review after the minor batch pass and rounds re-opened by External Review Gate findings. At the cap with any `critical` or `major` finding open: stop, escalate to CD via `AskUserQuestion` with the open-findings table, and never claim the loop is clean. At the cap with only minors open: exit with the Open Minor Findings table.
<!-- MIRROR-SOURCE-END: code-review-mechanics -->

### Plan-review mechanics

<!-- MIRROR-SOURCE-START: plan-review-mechanics -->
**Plan review loop — critical mechanics.** Canonical protocol: `[sdlc-root]/process/review-fix-loop.md` § Plan Review. Shared definitions (severity, deduplication, scope-change marker, Open Minor Findings): `[sdlc-root]/process/finding-classification.md`. These steps are inlined so that skipping the read does not skip the behavior.

1. **Fresh reviewer subagents, every round.** Dispatch each reviewer as a new subagent in its own context window — never a resumed reviewer from an earlier round. Re-review prompts include the previous round's findings table and what the revision changed, require reading the current plan file rather than recalling it, ask for regressions beyond the prior findings, and state that a clean report is an expected, acceptable outcome.
2. **Deduplicate, calibrate, then classify.** Merge duplicates first, then calibrate every severity by impact × likelihood (the impact on the implementation if the plan is executed as written), then classify each finding in the Classification Table. Fill the `Scope change` column for every FIX finding: `yes` if the fix changes the approach, adds or removes files, or changes a phase or agent assignment. Never downgrade a severity to reach the exit bar.
3. **One revision dispatch per round.** All FIX findings go to the writing agent in a single revision dispatch. DECIDE findings go to CD via `AskUserQuestion`. PRE-EXISTING findings appear in the table and need no action.
4. **Re-review trigger is mechanical.** Before the revision dispatch, record the plan's Files list and phase/agent assignments from your last Read of the plan file; after the writer returns, Read it again and compare. Re-review is mandatory if ANY of these is true: (1) any FIX finding has `Scope change` = yes, (2) the revised plan's Files list differs from the pre-revision Files list, or (3) a phase was added, removed, or its assigned agent changed. Otherwise there is no re-review. Read the `Scope change` column and compare the before/after Files list; do not reason about whether the revision "changed the approach."
5. **Re-review dispatches the full roster.** The roster is the round-1 roster line (plus the external reviewer, inside its own 2-round cap). When re-review fires, dispatch every reviewer on it — not a subset chosen by what the revision changed. Plans have no narrow re-review.
6. **Exit bar.** Review ends when no `critical` or `major` FIX finding remains unaddressed and no DECIDE finding is unresolved. Minor FIX findings the revision did not incorporate go in an **Open Minor Findings** table in the plan file. They are never silently closed; only CD closes them.
7. **Three-round cap.** At most 3 review rounds: the first round plus up to 2 re-reviews, and every round counts. If any `critical` or `major` finding is open at the cap, or round 3's revision fires a re-review trigger: stop, escalate to CD via `AskUserQuestion` with the open-findings table, and never claim the review is clean. At the cap with only minors open: exit with the Open Minor Findings table.
<!-- MIRROR-SOURCE-END: plan-review-mechanics -->

## What This Loop Does NOT Replace

An exit from this loop means: code quality is verified, machine checks pass, experiential verification confirms basic functionality, no critical or major finding is open, and any open minors are listed for CD. It does **not** mean the UX is final.

**CD iteration is a distinct, expected phase — not a failure of this loop.** The review loop catches:
- Code quality (overengineering, DRY, type safety, security, performance)
- Functional correctness (tests pass, types check, lint clean)
- UX bugs (Step 0.5 — things visibly broken when you use the app)

CD iteration catches:
- Interaction model choices ("should this be a slider or a dropdown?")
- Control placement ("does this belong in the toolbar or the sidebar?")
- Breakpoint strategy ("are these breakpoints right for this content?")
- Flow and feel ("this works but feels wrong — the rhythm is off")

These are judgment calls that require product context, taste, and sustained hands-on use. No agent review — however thorough — substitutes for a human using the feature and deciding "this isn't right." When CD iteration surfaces issues after a clean review loop, that is the process working correctly: formal review and CD iteration are complementary layers, not redundant ones.

## Skill-Specific Variations

| Context | Skills | Round-1 roster source | Verification gate | Narrow re-review standing reviewers | Re-review rule | Open Minor Findings live in |
|---------|--------|----------------------|-------------------|-------------------------------------|----------------|----------------------------|
| Code review — execution | `sdlc-execute`, `sdlc-lite-execute` | Plan's agent assignment table (+ domains surfaced during implementation) | Step 0 + Step 0.5 | `code-reviewer`, `software-architect` | Step D (mechanical full/narrow) | Result doc |
| Code review — on demand | `sdlc-review-code` | Step 3's dispatch checklist — **that dispatch is round 1**, so Step 5b's re-reviews are rounds 2 and 3 | Step 0 (tests, types, lint) after every fix round; not before round 1, which reviews the diff as submitted (possibly a historical commit) | `code-reviewer`, `software-architect` | Step D | Fix Summary (final report) |
| Code review — direct dispatch | "Review before committing" in `CLAUDE-SDLC.md` | Touched domains + standing reviewers (Step A) | Step 0 | `code-reviewer`, `software-architect` | Step D | Final report to CD |
| Plan review | `sdlc-plan`, `sdlc-lite-plan` | The skill's step-1 agent list, reconfirmed (AGENT-RECONFIRM, round 1 only), as dispatched — the round-1 roster line | None | n/a — no narrow re-review | § Plan Review (scope-change triggers; full round-1 roster) | The plan file |
| Reference-doc review | `sdlc-create-reference-doc` | The skill's review quorum | None (no build gate) | The skill's standing reviewer: `code-reviewer` (on every quorum) | Step D | The commit message |

Lite and full tiers run the identical loop — there are no lite-specific review rules. Lite work gets lighter naturally: smaller rosters under the Step A roster rule and fewer rounds under § Exit Bar and § Round Cap.
