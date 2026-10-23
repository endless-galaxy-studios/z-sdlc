---
name: sdlc-reflect
description: >
  Surface learnings from the current work session into SDLC discipline parking lots. Reviews
  recent work (commits, changes, conversation context), identifies reusable insights and
  cross-discipline patterns, categorizes them by discipline, and writes them as triage-ready
  parking lot entries. Also attempts a session-scoped prune of agent memories — removing
  entries this session's changes invalidated, splitting MEMORY.md files nearing the size
  cap, and routing memory entries that carry generalizable insight into the parking lots
  before they're pruned. This is the standalone version of the discipline capture protocol —
  use it after any work session where formal SDLC skills without built-in discipline capture
  were invoked, or after sessions where no formal SDLC skills ran at all.
  Several skills suggest running sdlc-reflect at completion: sdlc-debug-incident (after closeout),
  sdlc-review-code, sdlc-tests-run, sdlc-tests-create, sdlc-create-reference-doc, and
  sdlc-playbook-generate.
  Triggers on "/sdlc-reflect", "capture learnings", "what did I learn", "surface insights",
  "session retrospective", "reflect on this session", "feed back to SDLC".
  Do NOT use for bulk external knowledge import — use sdlc-ingest.
  Do NOT use for exploring ideas — use sdlc-idea.
  Do NOT use for formal post-mortems — use sdlc-debug-incident closeout.
  Do NOT use for a project-wide agent memory hygiene sweep — sdlc-audit Dimension 8 covers that.
  Do NOT use during or after sdlc-execute, sdlc-lite-execute, sdlc-plan, sdlc-lite-plan,
  sdlc-idea, or sdlc-design-consult — those skills run discipline capture automatically.
---

# SDLC Reflect — Session Learning Capture

Surface learnings from a work session into discipline parking lots. The goal is to capture reusable, non-obvious insights that emerged during work — especially sessions where formal SDLC skills were not invoked and discipline capture didn't run automatically. As a closing pass, the skill also attempts to prune agent memories the session touched or invalidated, so stale memories don't accumulate between audit cycles.

**Argument:** `$ARGUMENTS` (optional — description of what to focus the reflection on, or "all" for a full session scan)

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## When This Applies

Use after any work session where you did substantive work but discipline capture didn't run automatically. Two main scenarios:

**A. Sessions without formal SDLC skills:**
- Direct dispatch sessions — CD was steering, agents were doing work, no plan artifact
- Bug fix sessions — diagnosed and fixed an issue without a deliverable
- Exploratory coding — prototyped something, learned things, didn't use `sdlc-idea`
- Refactoring sessions — restructured code, discovered patterns or anti-patterns
- Integration work — wired up external services, hit gotchas worth recording

**B. After SDLC skills that lack built-in discipline capture:**
- After `sdlc-debug-incident` closeout — cross-discipline insights beyond the postmortem's Lessons Learned
- After `sdlc-review-code` — gotchas, cross-domain friction, or anti-patterns surfaced during review
- After `sdlc-tests-run` — testability issues, architecture gaps, or testing patterns discovered during the fix loop
- After `sdlc-tests-create` — coverage gaps that reveal missing knowledge or discipline-level blind spots
- After `sdlc-create-reference-doc` — knowledge gaps and cross-domain friction surfaced during documentation
- After `sdlc-playbook-generate` — discipline-level insights beyond what the playbook itself captures

These skills suggest running `/sdlc-reflect` at completion when non-obvious learnings surfaced.

Signs this skill is NOT appropriate:
- You just finished `sdlc-execute`, `sdlc-lite-execute`, `sdlc-plan`, `sdlc-lite-plan`, `sdlc-idea`, or `sdlc-design-consult` — those already ran discipline capture
- You want to import external articles/transcripts — use `sdlc-ingest`
- You want to explore an idea — use `sdlc-idea`
- Nothing non-obvious happened — skip it, don't fabricate entries

## Preconditions

- At least one substantive work action in the current session (commits, file edits, agent dispatches, research)
- Discipline parking lots exist at `[sdlc-root]/disciplines/`
- Agent memory pruning (Step 5) additionally requires `.claude/agent-memory/` to exist — skip that step silently if it doesn't

## Steps

### 1. Survey the Session

Review what happened in this session to build a picture of the work done:

1. **Recent commits** — run `git log --oneline -20` and `git diff HEAD~5 --stat` (adjust range to cover the session's work)
2. **Uncommitted changes** — run `git status` and `git diff --stat` for work in progress
3. **Conversation context** — what agents were dispatched, what problems were solved, what friction was encountered

Present a brief session summary:

```
SESSION SUMMARY
Work: [1-2 sentence description of what was done]
Files touched: [count] ([key areas])
Agents dispatched: [list] | none (manual work)
Duration signal: [commit count and time span]
```

### 2. Identify Learnings

Scan the session for insights across two dimensions.

**Structured detection** — signals from `[sdlc-root]/process/discipline_capture.md` applicable in standalone mode. The full protocol defines seven signal types; two (`UNMAPPED_KNOWLEDGE`, `STALE_KNOWLEDGE`) require agent handoff data (`knowledge_feedback.loaded`) that isn't available in standalone sessions. The five session-inferrable signals:

| Signal | What to look for |
|--------|-----------------|
| `MISSING_KNOWLEDGE` | A problem was solved that no knowledge file covers — would a future agent benefit from having this documented? |
| `CROSS_DOMAIN_FRICTION` | Work required expertise outside the primary domain — did a backend change need design knowledge, or vice versa? |
| `RESURFACING_PATTERN` | Did you fix something you've fixed before, or see the same issue in multiple places? |
| `GOTCHA_DISCOVERED` | Did a library, API, or framework behave unexpectedly? |
| `ANTI_PATTERN_HIT` | Did you refactor away from a pattern that was causing problems? |

**Freeform scan** — beyond the structured signals, ask:

- What would I tell a colleague starting similar work tomorrow?
- What assumption turned out to be wrong?
- What took longer than expected, and why?
- What pattern emerged that applies beyond this specific task?

**Filtering criteria — include if:**
- Reusable beyond this specific task
- Non-obvious — an agent wouldn't derive it from reading the codebase
- Actionable — it changes how future work should be done

**Filtering criteria — exclude if:**
- Obvious to any competent practitioner
- Specific to this exact task with no generalizable lesson
- Already captured in an existing knowledge file or discipline entry

### 3. Categorize by Discipline

Map each identified learning to its target discipline. Read `[sdlc-root]/disciplines/README.md` for the full discipline list if needed.

| Discipline | Typical learnings |
|-----------|-------------------|
| `coding` | Implementation patterns, refactoring insights, language gotchas, testability lessons |
| `architecture` | System design discoveries, integration patterns, boundary issues, performance insights |
| `testing` | Test strategy insights, coverage gaps, flaky test patterns, tool gotchas |
| `design` | UI/UX patterns, accessibility discoveries, component interaction issues |
| `data-modeling` | Schema insights, migration patterns, query optimization discoveries |
| `deployment` | CI/CD friction, infrastructure gotchas, release process learnings |
| `observability` | Monitoring gaps, debugging workflow improvements, logging patterns |
| `business-analysis` | Requirements clarifications, domain model insights, stakeholder feedback patterns |
| `product-research` | User behavior observations, competitive insights, feature viability signals |
| `process-improvement` | SDLC friction, workflow improvements, tool integration insights |
| `dx` | Developer experience friction, documentation gaps, onboarding obstacles |

Present the categorized learnings for confirmation:

```
LEARNINGS
─────────────────────────────────────────────
[N] learnings identified across [N] disciplines

  coding (2):
    1. [Brief description of learning]
    2. [Brief description of learning]

  architecture (1):
    1. [Brief description of learning]

Write to parking lots? (y / adjust / skip)
```

Wait for confirmation. The user may adjust categorization, remove entries, or add ones you missed.

### 4. Write to Parking Lots

For each confirmed learning, Append to `[sdlc-root]/disciplines/*.md` under `## Parking Lot`.

**Entry format:**

```
- **[date] [context]**: [insight]. [NEEDS VALIDATION]
```

**Context format:** `[session: {brief-slug}]` — e.g., `[session: fix-auth-race-condition]`, `[session: refactor-payment-flow]`.

For auto-detected structured gaps, use the GAP format adapted from `[sdlc-root]/process/discipline_capture.md`:

```
- **[date] [session: {slug}]**: [GAP:{type}] {description}. [NEEDS VALIDATION]
```

The canonical GAP format includes `Source: {agent} finding` — omitted here because sdlc-reflect infers gaps from git history and conversation context, not from agent handoffs.

**Rules:**
- Default triage marker is `[NEEDS VALIDATION]` — do not mark as `[READY TO PROMOTE]` unless the learning has been validated through repeated use
- One insight per bullet — keep entries atomic for independent triage
- Include enough context that the entry is useful without the conversation history
- Write directly — the Manager Rule does not apply to parking lot entries (per `[sdlc-root]/process/discipline_capture.md`)

### 4b. Recurring-Pattern Guard Scan

If `docs/reviews/recurring-patterns.yaml` exists, run a session-scoped version of `sdlc-audit` Dimension 6l's threshold scan — same thresholds, same criteria, no redefinition (canonical logic in the compliance methodology; guard contract in `[sdlc-root]/process/guardrail-lifecycle.md`). Skip silently if the file doesn't exist.

1. For each cluster with 3+ occurrences in the 30-day window and no `mechanized_guard`: if the pattern is mechanizable (textual, structural, or behavioral signature), flag it as a **guard-promotion proposal** with the signature and its fix level named (`[sdlc-root]/process/guardrail-lifecycle.md` § Choosing the Fix for a Repeated Mistake). Skip clusters marked `mechanization_assessed: excluded` — CD already assessed those and chose not to mechanize; never re-propose them.
2. For each cluster that gained an occurrence this session *despite* having a `mechanized_guard`: flag it as **guard ineffective**.

Present flags in the Step 6 report. Do NOT write `mechanized_guard` fields or implement guards here — proposals route to the next `sdlc-audit` triage (or CD can invoke it now). This step exists so a threshold crossed mid-cycle surfaces within the session instead of waiting for the next audit.

### 5. Prune Agent Memories

Attempt a session-scoped prune of agent memories. This is a lighter-weight complement to sdlc-audit's project-wide memory hygiene sweep — scoped to memories this session plausibly touched or invalidated, not a full scan of every agent. Skip silently if `.claude/agent-memory/` doesn't exist.

**Scope — check only:**
- Memories of agents dispatched during this session
- Any agent's `MEMORY.md` whose claims cover code changed this session (compare memory claims against the session's diff from Step 1)

**What to prune** (hygiene rules per the agent template's memory protocol; canonical check definitions in sdlc-audit's compliance methodology, Dimension 8b):

| Check | Action |
|-------|--------|
| Entry contradicts current code — especially claims this session's changes invalidated | Remove or correct the entry. Verify against source before touching it — a memory that merely *looks* stale may still be right. |
| Same fact or tuned value stated twice with drifted numbers | Keep the value matching current code, delete the rest |
| `MEMORY.md` at or approaching the load cap (~180 lines or nearing 25KB) | Split the largest topics into `{topic}.md` files beside it, leave one-line pointers |
| Memory directory for an agent that no longer exists in `.claude/agents/` | Flag for deletion — never delete without explicit confirmation |

Size checks apply only to `MEMORY.md` (topic files are uncapped by design), but correctness pruning applies to topic files too when a MEMORY.md pointer leads to one with invalidated claims.

**Promotion check — do this before deleting anything.** While scanning, evaluate each memory entry you touch against the Step 2 filtering criteria (reusable beyond the task, non-obvious, actionable). An entry can warrant a parking lot entry whether it's being pruned or kept:

- **Pruned entries:** the entry may be stale as stated but carry a generalizable lesson — e.g., a memory invalidated by this session's change often documents *why* the old approach failed, which is exactly a `GOTCHA_DISCOVERED` or `ANTI_PATTERN_HIT` signal. Capture the lesson before deleting the entry.
- **Kept entries:** a correct memory that's transferable domain knowledge rather than codebase-specific scratchpad belongs to everyone, not one agent (per the agent template: "your memory is for you; knowledge stores are for everyone"). Route a copy to the parking lot; leave the memory in place.

Most memory entries are codebase-specific shortcuts and will not qualify — apply the same exclusion filters as Step 2 and don't promote for the sake of promoting.

Present proposed prunes and promotions together before applying:

```
MEMORY PRUNES
─────────────────────────────────────────────
  [agent-name]: [N] entries stale (invalidated by [change]), [N] duplicates
  [agent-name]: MEMORY.md at [N] lines — split [topic] to topic file

PROMOTION CANDIDATES (memory → parking lot)
  [discipline]: [insight, one line] (from [agent-name], pruned|kept)

Apply prunes and write promotions? (y / adjust / skip)
```

Confirmed promotion candidates are written using the Step 4 entry format with context `[memory: {agent-name}]` instead of `[session: {slug}]`, still marked `[NEEDS VALIDATION]`.

If nothing needs pruning or promoting, say so in one line and move on — don't manufacture entries to have something to show.

### 6. Report

Present what was captured:

```
REFLECT REPORT
═══════════════════════════════════════════════════════════════

Session: [brief description]

ENTRIES WRITTEN
  [discipline]: [count] entries
  [discipline]: [count] entries
  Total: [count] entries across [count] disciplines

SAMPLE ENTRIES
  - [discipline]: [first entry text, truncated]
  - [discipline]: [first entry text, truncated]

SKIPPED
  [count] potential insights filtered (obvious: N, task-specific: N, already-captured: N)

MEMORY PRUNES
  [agent-name]: [what was pruned/split] | none needed | no agent-memory directory
  Promoted to parking lots: [count] entries ([disciplines]) | none qualified

GUARD SIGNALS (from recurring-patterns scan)
  Guard-promotion proposals: [slug — signature — proposed guard type] | none at threshold | no pattern log
  Guards recurred-despite: [slug — guard location] | none

NEXT STEPS
  - Entries are marked [NEEDS VALIDATION] — they'll be triaged during the next sdlc-audit cycle
  - [If any entry looks ready to promote]: Consider promoting [entry] to [target knowledge file] after further validation
```

## Red Flags

| Thought | Reality |
|---------|---------|
| "Nothing happened worth capturing" | If the session involved substantive work, run the structured detection signals before concluding there's nothing. But if genuinely nothing non-obvious surfaced, that's fine — skip it. |
| "I'll mark these as READY TO PROMOTE" | Default is NEEDS VALIDATION. A single session's learning hasn't been validated through repeated use. |
| "I'll dispatch an agent to write the parking lot entries" | The orchestrator writes parking lot entries directly — Manager Rule does not apply to process documentation. |
| "I'll also update the knowledge YAML files" | Reflect captures raw insights to parking lots. Promotion to knowledge stores is a separate triage step (sdlc-audit or manual). |
| "This belongs in the knowledge store, not a parking lot" | Parking lot is the landing zone. Even high-confidence insights start here. The triage cycle promotes what's validated. |
| "I'll skip the user confirmation step" | Always present categorized learnings before writing. The user may disagree with categorization or want to adjust. |
| "I should run this after every session" | Only when substantive work happened AND formal skills didn't already capture. Most direct-dispatch or bug-fix sessions are good candidates. |
| "I'll create a new discipline for this learning" | Route to the closest existing discipline. New disciplines require the criteria in `[sdlc-root]/disciplines/README.md` § "Creating a New Discipline". |
| "I'll do a full sweep of every agent's memory while I'm at it" | Session scope only — agents dispatched this session or memories the session's changes invalidated. The project-wide hygiene sweep is sdlc-audit Dimension 8b. |
| "This pattern hit the threshold — I'll write the mechanized_guard field now" | Step 4b proposes; the audit triage (or CD explicitly) decides. Reflect never writes guard fields or implements guards. |
| "This memory looks outdated, I'll delete it" | Verify against current source first. Deleting a correct memory costs the agent hard-won context; pruning applies only to entries you've confirmed are wrong, duplicated, or over-cap. |
| "It's stale, delete it and move on" | Run the promotion check first. A memory invalidated by a change often documents why the old approach failed — capture that lesson in the parking lot before the entry disappears. |
| "This memory is useful, so it should be promoted" | Useful to *that agent* isn't the bar. Promote only entries that pass the Step 2 filters — reusable beyond the task, non-obvious, actionable. Codebase-specific scratchpad stays in memory. |
| "Memory pruning failed / no memories exist, so the reflect failed" | Pruning is best-effort. Note it in the report and finish — parking lot capture is the primary deliverable. |

## Integration

- **Depends on:** Substantive work in the current session; discipline parking lots at `[sdlc-root]/disciplines/`
- **Feeds into:** Discipline triage cycle (sdlc-audit scans parking lots for threshold breaches and untriaged entries)
- **Uses:** `git log`, `git diff`, `git status` (session survey); `[sdlc-root]/disciplines/*.md` (write targets); `[sdlc-root]/process/discipline_capture.md` (structured gap detection methodology); `docs/reviews/recurring-patterns.yaml` + `[sdlc-root]/process/guardrail-lifecycle.md` (guard scan, Step 4b); `.claude/agent-memory/*/MEMORY.md` (prune targets, Step 5)
- **Complements:** Built-in discipline capture in sdlc-execute, sdlc-plan, sdlc-idea (those run automatically; this is for sessions without those skills)
- **Does NOT replace:** sdlc-ingest (bulk external knowledge import), sdlc-audit improvement mode (systematic process gap analysis), built-in discipline capture steps in execution/planning skills
- **DRY notes:** Structured detection uses five of seven signals from `[sdlc-root]/process/discipline_capture.md` — standalone mode omits `UNMAPPED_KNOWLEDGE` and `STALE_KNOWLEDGE` (require agent handoff data). GAP entry format omits `Source: {agent} finding` (documented in Step 4). The difference: discipline_capture.md runs embedded within other skills with full triage table and agent handoff data; sdlc-reflect runs standalone and infers from git history and conversation context. Memory-prune hygiene checks (Step 5) reuse the definitions in sdlc-audit's compliance methodology Dimension 8b and the agent template's memory protocol — sdlc-reflect applies them session-scoped between audits; sdlc-audit remains the project-wide sweep. The Step 5 promotion check parallels sdlc-audit's Dimension 8a pattern mining but differs in bar and destination: 8a requires recurrence across 2+ agent memories and routes to interactive triage; reflect promotes opportunistically (single entry, Step 2 filters) and routes to parking lots as `[NEEDS VALIDATION]` — the triage cycle still decides what graduates to knowledge stores.
