# CLAUDE-SDLC.md

This file is a **drop-in addition** for your project's `CLAUDE.md`. Copy the relevant sections into your existing CLAUDE.md — do not replace it.

---

## SDLC Process

This project follows a lightweight SDLC framework. Reference material lives in the SDLC directory (`ops/sdlc/` by default, or `.claude/sdlc/` for projects using Neuroloom integration).

The SDLC defines what artifacts a deliverable requires; two skills define how CC produces them:
- `sdlc-plan` — spec + plan (domain agents write and review)
- `sdlc-execute` — implement + review + commit (domain agents execute and review)

### Roles
- **CD (Claude Director):** Human — sets direction, approves specs, makes product decisions
- **CC (Claude Code):** The entire agent system — specs, plans, implements, reviews via domain-agent-driven skills

### Deliverable Workflow
Idea → (optional: `sdlc-idea` for exploration) → Spec (CD approves) → Plan (reviewed) → Execute → Review → Result → Chronicle

CC produces SDLC artifacts across two skills:
- **Spec** → `docs/current_work/specs/dNN_name_spec.md` (planning skill, CD must approve)
- **Plan** → `docs/current_work/planning/dNN_name_plan.md` (planning skill, agents review)
- **Result** → `docs/current_work/results/dNN_name_result.md` (execution skill, domain agents review)
- **Complete** → renamed to `dNN_name_COMPLETE.md`, archived to `docs/chronicle/`

### Deliverable Tracking
- **IDs:** Sequential: D1, D2, ... Dnn (never reused). Sub-deliverables use letter suffixes: D1a, D1b.
- **Assign an ID** when work is expected to touch more than one file or take more than 30 minutes.
- **Catalog:** `docs/_index.md`
- **Active work:** `docs/current_work/`
- **Archived work:** `docs/chronicle/`

### Three Tiers of Work

| Tier | When | What Happens |
|------|------|-------------|
| **Idea Exploration** (`sdlc-idea`) | The user has a thought or direction but isn't ready to commit to requirements | Idea brief (optional), saved to `docs/current_work/ideas/` |
| **Full SDLC** (`sdlc-plan` → `sdlc-execute`) | New features, architectural changes, new integrations, new subsystems | Deliverable ID, spec, plan, result doc, chronicle |
| **SDLC-Lite** (`sdlc-lite-plan` → `sdlc-lite-execute`) | Work complex enough to benefit from a reviewed plan up front, but doesn't need a spec | Deliverable ID (tier: lite), plan file, result doc, agent review, catalog entry |
| **Direct dispatch** (no skill) | CD is steering in real-time — describing goals, testing results, giving feedback | Agents do the work, CC orchestrates, CD drives iteration |

**Choosing a tier:** If the user isn't sure what they want yet → `sdlc-idea`. If the work benefits from a **plan artifact that survives context clears** → SDLC or SDLC-Lite. If the user is actively steering and iterating in conversation → direct dispatch.

**Before touching any file:** If you identify non-trivial complexity (cross-domain, non-obvious approach, new subsystems), surface the scope and ask CD which tier to use. The user should never be in the position of catching a missed planning gate.

### Estimation
**Do not estimate in cardinal time.** AI-assisted development compresses implementation so dramatically that calendar-time estimates are misleading. Estimate deliverables on three dimensions instead:

| Dimension | What It Measures |
|-----------|-----------------|
| **Validity** | Are the requirements right and complete? (Low / Medium / High) |
| **Correctness** | Will the implementation be correct on the first pass? (Low / Medium / High) |
| **Effort** | How many human–AI coordination cycles are needed? (Light / Moderate / Heavy) |

Low validity → invest in spec/discovery. Low correctness → invest in testing and iteration. Heavy effort → full SDLC with phased execution. See `[sdlc-root]/process/collaboration_model.md` § Estimation Model for the full rationale.

### Direct Dispatch Rules

Direct dispatch is not "no process" — it's process without a plan file. These rules apply whenever you're doing work without invoking a planning or execution skill:

**Agent-first, always.** Domain agents do the implementation and review work. You orchestrate. This is not optional just because there's no plan. If a domain agent exists for the work, dispatch them.

**State scope before dispatching.** Before your first agent dispatch, output a brief scope statement:
```
Scope: [what we're doing and why]
Agents: [who's doing the work]
```
This takes 10 seconds and prevents scope drift. It's not a plan — it's a one-time orientation.

**Pass full context to agents.** The dispatch prompt must include everything the agent needs: what to build/fix, which files are involved, relevant constraints, library versions (verify via Context7 when external APIs are involved), and any context from the user's feedback. Agents start fresh — they don't see the conversation.

**Iterate on CD feedback.** When the user tests and reports issues ("that didn't work", "why is this magenta?", screenshots), dispatch the relevant agent to fix — self-apply only when the fix passes the Manager Rule's economics test, and route it through review either way. Each round of feedback is a new dispatch with the user's observations as context.

**Review before committing.** When the user signals they're satisfied (or when you've completed a coherent unit of work), review the full set of changes before committing with the same review-fix loop the execution skills use (`[sdlc-root]/process/review-fix-loop.md`). Roster: `code-reviewer` and `software-architect` plus one reviewer per touched domain, as fresh subagents every round. In one line: **re-run the verification gate after every fix round; re-review with the full roster if any fix was critical or major or touched files beyond the findings, otherwise only the raising reviewers plus `code-reviewer` and `software-architect`; exit when no critical or major findings remain (open minors are listed for CD, never silently closed); at most three review rounds — escalate to CD if critical or major findings are still open at the cap.**

**External review gate — first-class when configured.** Projects that provide an executable `[sdlc-root]/external-review.sh` get a cross-vendor reviewer (Codex or a local LLM) as a standing SDLC participant — deliberation between models is strongest when they come from different families. It participates at planning time (approach deliberation consult in `sdlc-plan` step 3d; ensemble member of the plan review roster in `sdlc-plan` step 5 and `sdlc-lite-plan` step 3) and at execution time (second opinion on the diff after the internal review loop is clean, before commit). Its findings re-enter the same triage; the external model never edits files and never decides. Standard wrapper templates ship at `[sdlc-root]/templates/external-review.sh.template` and `[sdlc-root]/templates/external-review-knowledge.sh.template` — enable one by copying it to `[sdlc-root]/external-review.sh` (or `external-review-knowledge.sh`), making it executable, and adjusting the defaults to the project's egress policy. Sending code to a hosted model is data egress — state where the code goes and never send secrets; prefer a local model for sensitive code. See `[sdlc-root]/process/external-review-gate.md`. A parallel optional wrapper, `[sdlc-root]/external-review-knowledge.sh`, serves as the external judge in the knowledge Promotion Verification Gate (`[sdlc-root]/process/discipline_capture.md` § Promotion Verification Gate) — same egress rules, different output contract. For Codex-backed wrappers, match model and reasoning effort to the task via the `CODEX_MODEL` / `CODEX_REASONING_EFFORT` env vars, resolving current model names at runtime from OpenAI's model docs rather than from memory (see the gate doc § Task-Based Model Selection).

**Dispatch-first, with an economics exception.** The manager rule applies in direct dispatch exactly as it does in plan-based execution. "There's no plan so I'll just do it myself" is not valid. You may self-apply a change only under the Manager Rule's Delegation Economics Exception — delegation would cost more than the change itself (in tokens or main-context growth), the change is small and mechanical, and it needs no new context — and every self-applied change is still reviewed by the relevant domain agent(s) before commit. See `[sdlc-root]/process/manager-rule.md`.

### When to Escalate to a Plan

If you're in direct dispatch and ANY of these become true, stop and ask CD about escalating to SDLC-Lite or full SDLC:

- The scope has grown beyond what was originally stated
- You're on your third dispatch round and the work isn't converging
- The changes would benefit from surviving a context clear (long-running, will continue next session)
- You're introducing new abstractions (components, hooks, stores, routes, types, events)

### Workflow Rules

**STOP and invoke `sdlc-idea` when:**

- The user has a vague idea, question, or direction they want to explore ("what if we...", "I'm thinking about...", "could we...")
- The user describes a problem without proposing a solution and wants to think it through
- Multiple viable approaches exist and the user hasn't chosen — exploration before commitment

**STOP and invoke `sdlc-plan` when ANY of the following is true:**

- The user asks to build a new feature, new integration, or new subsystem
- The work introduces new architectural patterns
- You are unsure whether something needs full tracking — default to asking, not implementing

**STOP and invoke `sdlc-lite-plan` when:**

- The work is complex enough to benefit from agent review of a plan before execution
- The work will likely span a context clear
- Multiple interacting changes where getting the approach wrong is costly

**Invoke `sdlc-execute` / `sdlc-lite-execute` only when:**
- An approved plan exists at the expected path
- The user explicitly says "execute the plan" or references a specific plan file

**STOP and invoke `sdlc-handoff` when:**

- A bug, idea, or out-of-scope work is discovered mid-session and addressing it now would derail the current task
- The user wants to "park this" or "pick this up in a new session"
- A new session needs a self-contained starting point that doesn't depend on the current conversation

**After a direct-dispatch or ad-hoc session**, consider invoking `sdlc-reflect` to surface learnings into discipline parking lots — especially if the work involved gotchas, cross-domain friction, or patterns worth recording. It also attempts a session-scoped prune of agent memories the session touched or invalidated. This is optional; skip it if nothing non-obvious surfaced.

**After any skill writes a deliverable MD file to `docs/current_work/`,** ask CD whether they want an HTML explainer (`sdlc-explain` — big pictures, few words, verified) or a guided walkthrough (`sdlc-walkthru` — paced, comprehensive, conversational) — never unprompted. The markdown is the deliverable; both are optional ways for a human to absorb it. If CD accepts the explainer, build it with the document type's storyboard defaults and no further Q&A. When the deliverable feeds an approval gate, resolve the offer first — offer, and if accepted deliver, *before* asking for approval; never bundle the offer into the approval question, and never deliver after approval. Conventions: `[sdlc-root]/process/html-rendering.md`.

**All HTML the framework produces follows one visual doctrine — big pictures, few words.** Anything with a shape is drawn as inline SVG before it is described; words are rationed with hard limits; real names and real values, never placeholders. `/eli5 <subject>` (`sdlc-explain`) answers "how does this work", "why did we choose this", and "what caused this" the same way. An explainer informs a gate but is never approved against — the markdown is.

**When starting any session:** Check `docs/current_work/` for in-progress deliverables before accepting new work.

### Process Changelog
When you make changes to SDLC process files (skills, agents, process docs, CLAUDE-SDLC.md, disciplines, knowledge), update the process changelog (`[sdlc-root]/process/sdlc_changelog.md`) **immediately after the change, in the same step**. Do not defer changelog updates to a later step, a separate commit, or a future session. Every process decision change — new rules, classification changes, workflow adjustments, guard additions — must have a changelog entry written before moving on to other work. The changelog captures *why* process changes were made — context that git log alone doesn't preserve. Don't backdate entries for changes made in prior sessions.

### Key References
- `[sdlc-root]/process/overview.md` — Full workflow
- `[sdlc-root]/process/commands.md` — All SDLC commands and skills
- `[sdlc-root]/process/writing-for-cd.md` — How anything CD reads is written: plain language, length budgets, approval briefs
- `[sdlc-root]/templates/` — Document templates (spec, plan, result, concept index, PR description)
- `[sdlc-root]/templates/html-design-system.html` — HTML design system for explainers and exploration artifacts
- `[sdlc-root]/process/html-rendering.md` — HTML conventions, visual doctrine, and document-type storyboards
- `docs/_index.md` — Deliverable catalog

> **Note:** `[sdlc-root]` is `ops/sdlc/` by default, or `.claude/sdlc/` for projects using Neuroloom integration. The actual path is recorded in `.sdlc-manifest.json` under `sdlc_root`.

---

## Verification Policy (Zero-Assumption Rule)

**Assumptions are forbidden.** Every claim about external behavior, API shape, library usage, or service configuration must be verified before acting on it. "I'm pretty sure" is not good enough — verify or disclose.

### External Libraries & Frameworks
- Before using any external library API, **verify it via Context7** (`mcp__context7__resolve-library-id` → `mcp__context7__query-docs`). Do not rely on training data for API signatures, parameter names, default behaviors, or version-specific features.
- Check the project's actual dependency version (package.json, lock files, etc.) before querying docs — version matters.
- If Context7 does not have docs for the library, say so and ask the user for a documentation source.

### Codebase Knowledge
- Before making claims about how this codebase works, **read the actual code**. Do not infer file structure, function signatures, or module behavior from naming conventions alone.
- When modifying code, always read the target file and its immediate dependencies first.

### External Services & APIs
- Do not assume endpoint shapes, authentication methods, rate limits, or response formats. Look up documentation via Context7 or web search, or ask the user.
- If an external API has changed between versions, verify the version in use before giving guidance.

### When You Don't Know
- **Say "I don't know" or "Let me verify that."** Do not fabricate an answer.
- If verification tools are unavailable or inconclusive, explicitly flag the uncertainty: "I wasn't able to verify this — here's my best understanding, but please confirm."
- Never present unverified information with confidence.

### Agent Dispatch Integration
When dispatching domain agents for phases that involve external library integration, include in the dispatch prompt:
1. The specific libraries involved and their versions (from the project's dependency files)
2. Instructions to use Context7 for API verification before writing integration code
3. A reminder that training-data knowledge of library APIs is not sufficient — live docs are required

---

## Writing for CD

Everything addressed to CD follows `[sdlc-root]/process/writing-for-cd.md`: status updates, questions, summaries, approval briefs, completion reports, PR descriptions, and what a headless run's caller posts for CD.
- **Lead with what CD needs** to decide, know or do. Background comes after, if at all.
- **Plain language.** Define a term or leave it out. Internal labels (gate names, DECIDE, deliverable numbers) never carry a sentence on their own.
- **Say each thing once.** Show evidence, not claims. Say where you're unsure. Don't invent.
- **Budgets:** a status update in 1–2 sentences, an end-of-turn summary in about 150 words, an improvement proposal in about 100, a discovery check-in in about 300, an approval brief in about 450, a completion report in about 500.
- **Status blocks are one line on the happy path.** The full block appears only when a check fails or CD must act.
- **CD approves a spec or plan from its Approval Brief,** shown verbatim with the document's path.

The documents agents work from keep their detail: the bodies of specs, plans and result docs, and dispatch prompts.

---

## Use AskUserQuestion for All Questions

**Always use the `AskUserQuestion` tool when you need user input.** Do not type questions as conversational text. This includes:

- Design decisions and trade-offs
- Scope confirmation ("should we plan this, use SDLC-Lite, or direct dispatch?")
- Data accuracy questions ("should this be X or Y?")
- Clarification of ambiguous requirements
- Escalation when stuck (review-loop round cap, 3-strike rule, blocked work)

**Why:** Conversational questions create pause points where the user has to type free-text responses like "do it", "yes", "continue", "go" to unblock execution. `AskUserQuestion` presents structured options, reduces friction, and makes the decision point explicit.

**Exception:** Status updates, findings tables, and informational output are not questions — those are plain text. Spec and plan approval is asked by the Approval Brief message, which ends the turn; CD's reply is the answer (`[sdlc-root]/process/writing-for-cd.md` § Approval Briefs).

**Headless runs (no person present).** A run is headless when the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or when no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent) can be used in the session running the skill — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself, but in a headless run the orchestrator tells each subagent so, and the same limits bind it. Nobody can answer, so every question the next step depends on, every approval gate, and every escalation **stops the run** at that point. Save the work so far, then end the turn normally with the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one). A stop is a result, not an error; a missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. Questions the next step does not depend on are listed in the result, not stopped on. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it, and list those actions in the result; reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.

---

## Unbuilt-Capability Rule: Ask, Don't Silently Cut

**"I couldn't find this exposed in the codebase" is a reason to ask, never a reason to unilaterally cut, soften, or "correct" a stakeholder's request** — especially when the request originates from leadership/CD. A codebase-only investigation proves a capability isn't *currently exposed through an API or UI*; it does not prove the capability is unbuildable, and it never sees a requester's own context (a roadmap commitment, an intended feature, a known-but-underdocumented data source).

**The trap:** treating "not found via grep across the exposed application layer" as equivalent to "the underlying data doesn't support this." Products routinely collect data that already supports a described capability even when no current API or view exposes it — such requests can be real, buildable features, not just copy to soften into vagueness or cut.

**Correct procedure when a stakeholder's description doesn't match a currently-exposed capability:**
1. Check whether the *underlying data* (not just the application layer) already supports it — models, raw tables, survey/event logs. "Not exposed via any current endpoint" and "the data doesn't exist" are different findings; report which one is actually true.
2. **Ask the requester** — via `AskUserQuestion` — rather than deciding unilaterally. Lay out what's confirmed to exist and what would need to be built, and let them choose: build it for real, ship the language as explicitly forward-looking/illustrative, or hold it. Do not present "I cut/softened it" as a fait accompli in a summary after the fact.
3. This applies doubly to requests from leadership. Their language may be intentionally illustrative (an example of the *kind* of capability the product can offer, not a literal existing feature) rather than a factual claim needing "correction" — don't assume factual intent from marketing-style phrasing without asking which it is.

## Code Verification Rule

**Never assert how specific code behaves without reading it first.**

This applies to: flag names, function signatures, sync logic, config values, pipeline flow — anything implementation-specific.

The correct workflow is:

```
Read/Search → Reason → Assert
```

Not:

```
Assert (plausible) → Search to confirm → Correct when challenged
```

If you haven't read the relevant file, say so: *"Let me check"* — then check.

**Use LSP when available.** For type-system and call-graph questions, prefer LSP over Grep:

| Task | Use | Not |
|------|-----|-----|
| Find where a symbol is defined | LSP `goToDefinition` | Grep for the name |
| Find all call sites of a function | LSP `findReferences` | Grep for the name (misses renames and aliased imports) |
| Get the type signature of a function/variable | LSP `hover` | Read the file and infer |
| Find implementations of an interface method | LSP `goToImplementation` | Grep for method name |
| Trace what a function calls / who calls it | LSP `outgoingCalls` / `incomingCalls` | Manually following imports |
| List all symbols in a file | LSP `documentSymbol` | Reading the entire file |
| Search for a string literal or comment | Grep | LSP |
| Search non-code files (JSON, YAML, md) | Grep | LSP |
| Find a file by name pattern | Glob | LSP |

**If LSP returns an error or empty result:** Fall back to Grep + Read. Do not retry LSP in a loop.

See `[sdlc-root]/plugins/lsp-setup.md` for setup.

### UI Verification via Playwright MCP
When executing phases that modify user-facing code, the execution skills run inline UI smoke checks — navigate to the affected page, screenshot, check console errors. This requires Playwright MCP (`@playwright/mcp`). Without it, UI verification falls back to manual browser inspection. For projects with UI, install Playwright MCP to enable automated visual verification during execution. When the project has a verify skill (`.claude/skills/verify/`, written by `/sdlc-develop-verify-skill`), the smoke check launches, health-checks and drives the app through it.

See `[sdlc-root]/plugins/playwright-mcp-setup.md` for setup.

---

## Comment Rule

**A code comment says what the code can't show at a glance:** why a decision was made, how a piece connects to code elsewhere, a constraint from outside the code, or a public API's contract. It doesn't repeat what the code, a name or a type already says, narrate the steps, or record the change. The change's story belongs in the commit message and the pull request, and comments that repeat the code add bulk to every PR.

Two readers depend on comments: an agent that opens one file mid-task, and a developer new to the codebase. Both lose when a reason is missing, and both lose when it's buried among comments that repeat the code. Aim for that balance, not for a density.

- Write the why when the reason isn't obvious. Before explaining a surprise in our own code, try to remove it with a rename, an extraction or a type.
- When you change code, update or delete the comments about it in the same change.
- Never edit a comment a tool reads (a lint suppression, a build tag, a directive) as if it were prose.

Read `[sdlc-root]/knowledge/coding/comment-discipline.yaml` for the full rule and examples. To trim an existing codebase, run `/sdlc-cleanup-comments`.

---

## Debugging Escalation Rule

If you have spent 3 or more rounds of read/search/grep investigating a bug without identifying the root cause, stop self-investigating and dispatch `debug-specialist` with your findings so far. Pass what you've ruled out, the open hypotheses, and the relevant file paths. Do not continue accumulating context yourself — that context belongs in the agent's dispatch prompt.

---

## Session Model & Effort (your orchestrator seat)

This is *your* session dial (what you launch / `/model` + `/effort`), separate from the per-agent frontmatter tiers below. Both dials track how judgment-dense the session is (MTS6 in `[sdlc-root]/knowledge/architecture/model-tier-strategy.yaml`):

| Session | Model | Effort | Why |
|---------|-------|--------|-----|
| Planning / idea (`sdlc-plan`, `sdlc-lite-plan`, `sdlc-idea`) | Fable **or** Opus (CD's choice) | **high** (→ xhigh/max only for novel, ambiguous, or high-blast-radius work) | Judgment-dense and short — discovery, approach comparison, arbitration, acceptance. The Manager Rule keeps premium tokens off implementation, so a premium orchestrator is cheap here. |
| Execution (`sdlc-execute`, `sdlc-lite-execute`) | Sonnet | **medium** | Judgment is already in the plan; the seat coordinates + triages. Long sessions, so easing both dials conserves budget. Bump effort ad-hoc for a hard triage or a 3-strike/debug escalation. |

**Planning model is your call — Fable or Opus.** Both are top-tier; the split that matters is *planning-premium vs execution-Sonnet*, not which premium. Pick by task, quota, and preference (e.g. Fable 5 as flagship, or Opus 4.8's 1M-context variant when the planning context is very large). "Highest tier available" is a floor, not a mandate to always max out.

**Lowest-friction switching — launch aliases (set both dials at once):**

```bash
# ~/.zshrc (or ~/.bashrc)
alias ccplan="claude --model fable --effort high"       # planning / idea (Fable)
alias ccplan-opus="claude --model opus --effort high"   # planning / idea (Opus)
alias ccexec="claude --model sonnet --effort medium"    # execution
```

Both `--model` and `--effort` are launch flags. Setting effort at launch also avoids a gotcha: switching model mid-session with `/model` can reset effort to that model's default, so re-check `/effort` after any `/model`. `settings.json` persists `effortLevel` but not `model`, so aliases beat it. There are no named profiles and a SessionStart hook can't drive `/model` — aliases are the ceiling today. The `M4` "don't escalate to be safe" guardrail applies to your own session too: reserve `max` for the genuinely hardest planning.

## Agent Conventions

- **Model and effort tiers are pre-assigned in agent frontmatter** — trust the assignment rather than escalating everything "to be safe." Judgment work (intent, architecture, tradeoffs, arbitration, final acceptance) stays with the orchestrator; evidence-checkable work delegates to cheaper tiers; high-risk work gets a reviewer tier at or above the implementer tier. Planning sessions benefit most from running on the highest-tier model available — the Manager Rule keeps premium tokens off implementation. Read `[sdlc-root]/knowledge/architecture/model-tier-strategy.yaml` for the tier ladder and escalation rules.
- **Agent memories are not git-tracked** — `.claude/agent-memory/` is a private scratchpad for per-agent session continuity. Reusable learnings should flow through `knowledge_feedback` in agent handoffs → discipline capture → knowledge stores. See the "Surfacing Learnings to the SDLC" section in the agent template.
- **`MEMORY.md` is capped at 200 lines / 25KB** — only that much loads into the agent's system prompt; the rest is silently truncated, dropping the *newest* entries first. Keep `MEMORY.md` a lean index and push detail into `{topic}.md` files beside it (uncapped, read on demand). The agent template defines the split protocol; `sdlc-audit` Dimension 8b flags files over the cap.
- **Agent frontmatter: single-line descriptions only** — The `description` field in `.claude/agents/*.md` must be a double-quoted single-line YAML string using `\\n` (double-backslash n) for newlines. A single `\n` in YAML double-quoted strings is interpreted as a real newline character and silently breaks Claude Code's frontmatter parser.

## Commit Completeness Rule

Every commit must include **all** artifacts produced during the work — not just application code. Before staging, scan for modifications in all of these categories:

| Category | Paths | When present |
|----------|-------|--------------|
| Application code & tests | Project-specific | Always |
| Discipline parking lot entries | `[sdlc-root]/disciplines/*.md` | When discipline capture adds entries |
| Knowledge store updates | `[sdlc-root]/knowledge/*.md` | When domain knowledge is added or corrected |
| SDLC process changelog | `[sdlc-root]/process/sdlc_changelog.md` | When process files change |
| Result docs & catalog | `docs/current_work/results/`, `docs/_index.md` | During full SDLC execution |

**Never split SDLC documentation into a separate follow-up commit.** The documentation is part of the work, not a chore after the work. If `git status` shows unstaged SDLC files after staging application code, something was missed.

---

## Commit Message Format

**Subject line:** Keep under ~72 characters. Use the conventional-commits prefix style: `feat(scope): ...`, `fix(scope): ...`, `chore(scope): ...`, `docs(scope): ...`, `refactor(scope): ...`. Scope is the package or domain (`api`, `web`, `auth`, `sdlc`, etc.). Imperative mood — "add feature" not "added feature."

**Body wrapping:** Do **not** hard-wrap body text at 72 characters. Write natural sentences and let the viewer reflow. One blank line between paragraphs. The 50/72 convention existed for 80-column terminals and mailing-list patch workflows; neither governs how this repo's commits are read. Hard-wraps in the middle of a clause create awkward breakpoints in GitHub's commit view (where most reading happens) and don't help `git log` more than natural breaks would.

**Intentional line breaks are fine** when they serve meaning — bullet lists, grouped clauses, or separating a trailing footer like `Co-Authored-By:`. What's out is mechanical wrapping at column 72.

**Structure:** Subject line, blank line, paragraph-form body explaining the *why*. Bullet lists only when the content is genuinely enumerable (a list of behaviors, a list of affected files) — not as a default format. Close with any `Co-Authored-By:` trailer on its own line.

---

## Pull Request Description

A pull request that asks CD to approve agent-written work is written for CD, not for the agent: for code, the PR is usually where CD starts reading. Follow `[sdlc-root]/templates/pr_description_template.md` for every such PR, whether a person or the factory opens it: plain language, a fixed section order, and about one screen above a collapsed agent record. Plan and spec PRs use the plan variant; code PRs use the code variant. Every PR tells CD the original problem, what changes for users, what CD is approving, what's in and out of scope, the risk, and how the change will be (or was) verified. It also teaches the change: how it works, which files to read and in what order, and the key concepts. The plan, spec and result documents don't change. They stay the agent's contract, and only the PR is written for CD.

