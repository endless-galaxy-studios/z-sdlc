---
name: sdlc-playbook-generate
description: >
  Generate structured playbooks from the current conversation context or from previous session files
  and their associated git commits. Reads the current session directly when invoked mid-conversation
  or with no argument — no session ID or description required. Can also analyze past sessions via
  JSONL lookup when a session identifier is provided. Analyzes both what worked (the process to
  formalize) and what was missed (corrections, setup gotchas, environment gaps, service configuration
  that surfaced mid-execution). Produces playbooks following the project's existing playbook template
  format. Triggers on "make a playbook from", "analyze session", "generate playbook",
  "create playbook from session", "playbook from that session", "let's make a playbook for",
  "formalize that into a playbook", "turn that session into a playbook",
  "what did we learn from that session", "extract a playbook", "make a playbook from this",
  "playbook from what we just did", "turn this into a playbook", "playbook from this session",
  "make a playbook", "create a playbook".
  Use when a completed session or set of commits should be formalized into a reusable playbook.
  Do NOT use for creating playbooks from scratch without session data — write those directly.
  Do NOT use for bulk knowledge import — use sdlc-ingest.
  Do NOT use for session resumption — use sdlc-status to find active deliverables.
---

# Playbook Generation from Session Analysis

Extract structured, reusable playbooks from completed session conversations and their git history. The goal is to capture both the **process that worked** (steps to formalize and repeat) and the **gap that didn't** (corrections, missed setup, environment surprises, configuration gotchas that only surfaced during execution).

**This skill produces a playbook artifact in `[sdlc-root]/playbooks/`. It does NOT produce specs, plans, or implementations.**

**Argument:** `$ARGUMENTS` (optional — playbook scope hint, session name/ID, or search term. When empty or referencing the current session, the skill reads the current conversation context directly.)

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Two exceptions stand: writes to the project's knowledge backend count as local work, and the External Review Gate may send to a hosted provider the project has durably authorized (`[sdlc-root]/process/external-review-gate.md` § Data egress). Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## When This Applies

Use this when the user has completed work and wants to formalize the process into a repeatable playbook. The hallmark is retrospective analysis — the work is done, and now the user wants to capture what they learned.

Signs this skill is appropriate:
- "Make a playbook from this" / "Turn this into a playbook" (current session — no argument needed)
- "Let's make a playbook from the Slack bot session" (past session — name as argument)
- "Analyze that session and create a playbook for integrations" (past session with scope hint)
- The user just finished a non-trivial task and wants to prevent the same friction next time
- A session involved corrections mid-stream that indicate missing process knowledge

Signs this skill is NOT appropriate:
- Writing a playbook from scratch without session data → write directly using `[sdlc-root]/playbooks/example-playbook.md` as template
- Importing knowledge from external content → `sdlc-ingest`
- Resuming an incomplete session → use `sdlc-status` to find active deliverables

## Core Principles

**Context-first, arguments-second.** When invoked without a session ID, read the current conversation directly — you already have full access to everything that happened. Don't require the user to summarize or describe what they want a playbook for when you can see the work yourself. Arguments are for scoping, not for explaining.

**Two sources of truth, not one.** The conversation reveals what happened (intent, friction, corrections, discoveries). The git log reveals what was produced (code, config, migrations). Neither alone tells the full story. Cross-reference both.

**Friction is the signal.** The most valuable parts of a playbook are the steps that weren't obvious — the env var that was missing, the database migration that was forgotten, the service that needed restarting, the config that was wrong on first attempt. Scan for user corrections, re-dos, "oh wait" moments, and error-fix cycles.

**Formalize the happy path too.** The process that got you 90% there is the backbone of the playbook. Capture the step sequence, agent selection, and knowledge context that worked — the gap analysis layers on top of that foundation.

**Concrete over abstract.** Playbook steps reference specific files, specific env vars, specific service names. "Configure the database" is useless. "Add DATABASE_URL to Railway service env vars, run prisma migrate deploy, verify connection with prisma db pull" is a playbook.

**One playbook per task type.** A session might touch multiple concerns. The playbook covers the repeatable task pattern, not the specific session. Generalize the steps while preserving the specific gotchas.

## Workflow

```
RESOLVE SOURCE → CORRELATE → ANALYZE → DRAFT → PLACE → REPORT
```

Sequential. Each step must complete before the next. The user confirms scope (step 2) before deep analysis begins.

## Steps

### 1. Resolve Source

Determine where to read the session data from. Two paths — current context or past session file.

**Path A — Current session context (default when no session ID is provided):**

Use this path when:
- `$ARGUMENTS` is empty
- `$ARGUMENTS` references the current session ("this", "what we just did", "this session", etc.)
- `$ARGUMENTS` describes a playbook topic without referencing a specific past session

The current conversation IS the source data. You already have full access to it — every user message, assistant response, tool call, correction, and error is visible in the conversation context. No JSONL file lookup needed.

**Extract from current context:**
- The sequence of work performed (tool calls, agent dispatches, files read/written/edited)
- User corrections, feedback, "oh wait" moments, and error-fix cycles
- Decision points and the choices made
- The overall task type and scope of work completed

If `$ARGUMENTS` is empty and the conversation contains substantial work, infer the playbook topic from the work performed. If the conversation is too short or ambiguous to infer a playbook topic, ask the user: "What aspect of this session should the playbook cover?"

**Path B — Past session lookup (when a session name/ID is provided):**

Use this path when `$ARGUMENTS` contains a session name, search term, or session ID that refers to a different session.

Sessions are stored as JSONL files in the project's Claude directory:

```
~/.claude/projects/<project-dir-hash>/<session-id>.jsonl
```

**Resolution strategy:**
1. If the user provides a session name or search term, scan JSONL files for matching content (first user messages, topic keywords)
2. If the user provides a session ID, locate the file directly
3. If ambiguous, present candidates with timestamps and first user message for the user to pick

**Extract session metadata:**
- Session ID and timestamp range (first to last message)
- Project directory (from the JSONL path)
- Message count and approximate conversation length

Present the located session for confirmation before proceeding.

### 2. Correlate with Git History

Identify git commits associated with the session's work.

**For current session (Path A):** Use the commits made during this conversation. Check `git log` for recent commits, cross-referencing with files you observed being created or modified during the session.

**For past session (Path B):** Use the session's timestamp range:

```bash
git log --after="<session_start>" --before="<session_end>" --format="%H %ai %s" --reverse
```

**Build the correlation map (both paths):**
- List all commits with their messages and timestamps
- For significant commits, read the diff summary (`git diff --stat <hash>~1 <hash>`)
- Identify files created, modified, and deleted during the session
- Note any commits that were amended or reverted (signals of correction)

**Present scope for confirmation:**

```
SESSION SOURCE: [current conversation | session file <id>]
Time span: [start] → [end] ([duration])
Commits: [count] commits touching [count] files
Key files: [top 5-8 files by change frequency]
Playbook target: [user's stated purpose, or inferred task type]
```

Wait for user confirmation. If the user adjusts the playbook scope or target, re-present.

### 3. Analyze

Extract structured insights from the session data. For current session context (Path A), analyze the conversation directly — you already have it. For past session files (Path B), read the session JSONL. See `references/analysis-methodology.md` for the detailed extraction patterns (the same patterns apply to both paths — the difference is only where the data comes from).

**Two-track analysis:**

**Track A — The Process (what worked):**
- Ordered sequence of steps taken (what was done and in what order)
- Agent selection and dispatch patterns
- Knowledge files and references consulted
- Decision points and the choices made
- Codebase patterns leveraged (existing code that informed the approach)

**Track B — The Gap (what was missed or corrected):**
- User corrections ("no, not that", "we also need to", "that's wrong")
- Error-fix cycles (something failed, had to debug and retry)
- Mid-stream discoveries ("oh, we also need to set up X")
- Environment/infrastructure setup that wasn't anticipated
- Configuration values that required trial and error
- Service dependencies that weren't obvious upfront
- Steps that were done out of order and had to be redone

**Cross-reference tracks:** For each gap item, identify where in the process sequence it should have appeared. This produces the corrected, complete process that the playbook will capture.

### 4. Draft the Playbook

Generate the playbook following the project's template format (`[sdlc-root]/playbooks/example-playbook.md`). Read the template first to match the exact structure.

**Key sections to populate from analysis:**

| Template Section | Source |
|-----------------|--------|
| When to use | Generalized from the session's task type |
| Recommended Agents | From Track A agent dispatch patterns |
| Knowledge Context | From Track A knowledge files consulted |
| Typical Phases | From Track A process sequence, corrected by Track B ordering |
| Reference Implementations | From git history — key files created/modified |
| Key Decisions to Surface | From Track A decision points |
| Common Gotchas | From Track B — the core value of the analysis |
| Checklist Before Complete | From both tracks — the full corrected process |

**Gotchas section is critical.** Each gotcha must include:
- What went wrong or was missed
- Why it wasn't obvious (what assumption led to the gap)
- The concrete fix (specific env var, specific command, specific config)

**Generalize but preserve specifics.** The playbook is for the *task type*, not the specific session. But gotchas reference specific technical details — env var names, service configurations, file paths. These are the details that make the playbook actionable.

Present the draft to the user for review before writing.

### 5. Place

After user approval:

1. Write the playbook to `[sdlc-root]/playbooks/<slug>.md`
2. Update `[sdlc-root]/playbooks/README.md` — add entry to the "Available playbooks" table
3. Check if any existing knowledge stores should cross-reference the new playbook (note in report, don't auto-modify)

### 6. Report

```
PLAYBOOK GENERATION REPORT
═══════════════════════════════════════════════════════════════

Source session: [session-id] ([date range])
Commits analyzed: [count] ([count] files changed)
Playbook: [sdlc-root]/playbooks/[slug].md

PROCESS CAPTURED
  Phases: [count]
  Steps: [count] total
  Agents: [list of agents referenced]
  Knowledge context: [list of knowledge files]

GAP ANALYSIS
  Corrections found: [count]
  Gotchas documented: [count]
  Setup steps added: [count] (not in original session flow)
  Ordering fixes: [count] (steps that should have come earlier)

CROSS-REFERENCES
  Related playbooks: [existing playbooks that overlap] | none
  Knowledge stores to update: [stores that could benefit] | none

SESSION COVERAGE
  Conversation messages analyzed: [count]/[total]
  Commits correlated: [count]/[total in range]
```

### 7. Changelog Update

Update `[sdlc-root]/process/sdlc_changelog.md`:

```markdown
## [date]: Playbook Generated — [playbook name]

**Origin:** Session analysis of [session-id] ([brief description of the work])

**What happened:** Analyzed [duration] session with [N] commits to extract repeatable process and gap analysis for [task type].

**Changes made:**

1. **`playbooks/[slug].md`** — new playbook with [N] phases, [N] steps, [N] gotchas
2. **`playbooks/README.md`** — added to available playbooks index

**Rationale:** Formalizing session learnings into a playbook prevents repeated friction. [N] gotchas documented that would otherwise be rediscovered on the next [task type] integration.
```

### 8. Session Learning Capture

Playbook generation involves deep session analysis that surfaces discipline-level insights — process friction patterns, knowledge gaps that caused mid-stream corrections, cross-domain integration gotchas that transcend the specific playbook topic.

If this session surfaced non-obvious learnings beyond what the playbook itself captures (process-improvement insights, knowledge store gaps, discipline-level patterns), suggest:

> This playbook generation surfaced insights that may be worth capturing to discipline parking lots. Consider running `/sdlc-reflect` to surface them.

Skip the suggestion if the playbook already captures all relevant learnings.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I need the user to describe what this playbook is for" | Read the conversation context — you can see what was done. Only ask if the scope is genuinely ambiguous. |
| "I'll just summarize what happened" | Extract process steps and gotchas, not a narrative summary. |
| "The git log tells the whole story" | Git log shows what was committed. The conversation shows what was tried, failed, and corrected. Both are required. |
| "I'll skip the gap analysis, the process is clear" | The gap analysis IS the primary value. A playbook without gotchas is just a generic checklist. |
| "This gotcha is too specific to include" | Specific is good. "Set SLACK_SIGNING_SECRET in Railway" is more useful than "configure environment variables". |
| "I'll generalize away the details" | Generalize the task type, preserve the technical specifics. The env var names, the service configs, the file paths — those are what save time next run. |
| "I'll create the playbook without showing the draft" | Always present the draft for review. The user knows nuances the conversation didn't capture. |
| "The session was messy, I can't extract a clean process" | Messy sessions produce the best playbooks — the mess IS the gap analysis. |

## Integration

- **Feeds into:** Planning skills (`sdlc-plan`, `sdlc-lite-plan`) — playbooks pre-seed agent selection and knowledge context; `sdlc-reflect` (suggests it when session analysis surfaces discipline-level insights beyond the playbook)
- **Uses:** Current conversation context (preferred) or session JSONL files, git log, existing playbook template, knowledge stores (for cross-referencing)
- **Complements:** `sdlc-ingest` imports external knowledge; this skill imports internal session knowledge
- **Downstream:** `/sdlc-audit` checks playbook freshness as part of knowledge layer health audits

## Additional Resources

### Reference Files

For detailed analysis patterns and extraction methodology:
- **`references/analysis-methodology.md`** — Detailed patterns for extracting process steps and gap signals from session conversations and git history
