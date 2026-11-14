---
name: sdlc-handoff
description: >
  Capture the current session as a self-contained handoff document for another session to pick up.
  Writes a structured handoff at `docs/current_work/ideas/{slug}_handoff.md` that another session
  can crystallize via `sdlc-idea`, `sdlc-lite-plan`, `sdlc-plan`, or `sdlc-debug-incident`.
  Use when an issue, idea, or out-of-scope work is discovered mid-session that shouldn't be
  addressed in the current context.
  Triggers on "create a handoff", "hand this off", "save this for a new session",
  "write up a handoff", "this is out of scope here", "let's not handle this now",
  "park this for later", "another session should pick this up", "/sdlc-handoff".
  Do NOT use for resuming an existing deliverable — use `sdlc-status` to find it, then pick up from there.
  Do NOT use for archiving completed or resolved work — use `sdlc-archive`.
  Do NOT use for active production incidents — use `sdlc-debug-incident` directly.
  Do NOT use to write a spec or plan — use `sdlc-plan` or `sdlc-lite-plan`.
  Do NOT use for project-wide status snapshots — use `sdlc-status`.
  Do NOT use for open-ended exploration of a new concept where the idea hasn't been examined yet — use `sdlc-idea` directly. A handoff captures session context that's already concrete; an idea explores something that isn't.
---

# SDLC Handoff

Capture context from the current session into a self-contained handoff document so another session can pick the work up cleanly. The handoff names what was found, where the evidence is, and which skill should open the receiving session.

**Argument:** `$ARGUMENTS` (optional — a 1-2 sentence description of what's being handed off; if omitted, the skill will ask)

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## When This Applies

Use this skill when the current session has surfaced something that needs work, but addressing it now would derail the work in flight. Common triggers:

- **Issue found mid-implementation** — a bug, defect, or regression in code adjacent to the current task
- **Out-of-scope work discovered** — refactor opportunity, new feature idea, or system gap noticed while doing something else
- **Deferred follow-up** — work the user agreed to do later that's larger than a TODO comment
- **Investigation needed** — an unknown that requires a fresh, focused session to dig into

The handoff is a self-contained capture. The receiving session must NOT need this conversation's context to act on it.

## Preconditions

- A `docs/current_work/ideas/` directory exists (created by `sdlc-initialize`). If absent, create it before writing.
- The session has produced enough context to describe the handoff. Don't capture handoffs based on a single line of conversation — wait until the issue or idea has been examined enough to articulate concretely.

## Workflow

```
CAPTURE INTENT → EXTRACT EVIDENCE → CLASSIFY & RECOMMEND → GENERATE SLUG → WRITE DOC → SURFACE NEXT STEP → (OPTIONAL) COMMIT
```

## Steps

### 1. Capture Intent

If `$ARGUMENTS` is non-empty, use it as the seed. Otherwise prompt the user with `AskUserQuestion`:

> "What's being handed off?" (free-text answer)

Then classify the trigger using `AskUserQuestion`:

| Option | When to choose |
|--------|----------------|
| **Issue / bug** | A defect or regression — code is broken or behaving wrong |
| **Idea / improvement** | A new feature, refactor, or improvement worth exploring |
| **Deferred work** | Already-clear work the user agreed to do later |
| **Investigation needed** | An unknown that needs focused digging in a fresh session |

The trigger type determines which next-skill recommendation is most likely to fit (see step 3).

### 2. Extract Evidence

Pull from the current session — do NOT re-investigate. The handoff doc is a capture of what's already known, not an opportunity to expand the search.

Collect:

- **Files touched or read in this session** — paths to specific files involved
- **Code locations** — `file:line` references for any bug, anomaly, or salient code already encountered
- **Error output** — verbatim stack traces, error messages, log lines from this session
- **Recent agent findings** — any agent reports or review findings that bear on the handoff
- **Observations from the user** — what they noticed, in their own words where possible
- **Active deliverable context** — if a deliverable is in flight, name its ID and state so the receiving session knows what NOT to disturb

LSP (`hover`, `findReferences`) is allowed only to confirm symbol names and line numbers already discussed. The handoff captures; it does not explore. If you find yourself reading new files or running new searches, stop — that's the receiving session's job.

### 3. Classify and Recommend a Next Skill

Pick the lightest skill that won't skip a needed gate. Note the reasoning in the doc — the receiving session may override.

**Route on effort, not artifact size.** Effort here is coordination cycles — review rounds, cross-domain handoffs, verification depth — *not* item count or wall-clock time (see `[sdlc-root]/process/collaboration_model.md` § Estimation Model). A known, repeatable transform over N items — or an isolated single-file fix — is Light effort no matter how many records it touches or writes to production; route it to direct dispatch. Reach for a plan when the *approach* is unclear, the work spans domains, or getting the first move wrong is costly or hard to reverse.

| Handoff trigger + shape | Default next skill | Rationale |
|-------------------------|-------------------|-----------|
| Issue — isolated, Light-effort fix (approach clear) | Direct dispatch (`debug-specialist` or relevant specialist) | Single-agent fix doesn't need a plan |
| Issue — cross-domain or unclear scope | `sdlc-lite-plan` | Worth a reviewed plan before fixing |
| Issue — production incident with user impact | `sdlc-debug-incident` | Live triage and postmortem required |
| Idea — vague or unscoped | `sdlc-idea` | Needs exploration before planning |
| Idea — clear shape | `sdlc-lite-plan` or `sdlc-plan` | Skip exploration if requirements are evident |
| Deferred work — Light effort (known transform, reversible, even if high-volume) | Direct dispatch | Approach is settled; just do it when picked up. Default here and let the receiver escalate only if a real unknown surfaces |
| Deferred work — Moderate/Heavy effort (approach unclear, cross-domain, or costly/irreversible if wrong) | `sdlc-lite-plan` | Plan first — the coordination cycles, not the item count, are what earns the plan |
| Investigation needed | `sdlc-idea` | Open-ended exploration is the point |

If multiple skills could fit equally, list them in the doc and let the receiving session choose.

### 4. Generate a Slug

Two-to-four words, kebab-case, descriptive of the handoff itself (not the source session). Examples:

- `auth-token-refresh-bug`
- `query-cache-investigation`
- `deferred-typescript-strict-mode`

If a collision exists in `docs/current_work/ideas/`, append a date suffix: `{slug}-YYYY-MM-DD`.

### 5. Write the Handoff Doc

Write to `docs/current_work/ideas/{slug}_handoff.md` using this structure:

```markdown
---
type: handoff
slug: {slug}
created: YYYY-MM-DD
status: pending
trigger: {issue | idea | deferred-work | investigation}
recommended_next_skill: {skill-name or "direct-dispatch"}
source_session_summary: "{one line: what the source session was working on}"
active_deliverable: {DNN or null}
related_files:
  - path/to/file.ts
  - path/to/other.py
---

# Handoff: {Title}

## Why this is a handoff
{1-2 paragraphs: what was found in the current session and why it shouldn't be handled here. Name the source session's actual focus so the receiving session knows what NOT to inherit.}

## What needs to happen
{The work being handed off. Be specific where possible; it's fine to leave shape questions open — the receiving skill will sharpen them. Bullets or paragraphs, whichever fits.}

## Evidence
- **Code locations:** `path/to/file.ts:47` — {what's at that line}
- **Error output:** {paste verbatim, or reference a captured log file if long}
- **Observations:** {what the user or agent noticed, ideally with attribution}
- **Related findings:** {agent reports, review notes, prior chronicle entries}

## Recommended next step
Open a new session and run: **`/{recommended-skill}`** with this file as the seed.

Reasoning: {one or two sentences on why this skill fits — the receiving session may choose differently}

## Open questions
- {what the receiving session will need to figure out}
- {ambiguity worth flagging up front}

## Out of scope (do NOT pursue)
{Anything tangentially relevant that could pull the receiving session off track. Optional but useful when the handoff sits adjacent to a larger area.}
```

Validate before saving:

- Every required string field in the frontmatter is populated — no leftover `{placeholder}` markers. (`active_deliverable: null` is a valid sentinel value when no deliverable is in flight; do not treat that as unfilled.)
- Evidence section has at least one concrete reference (file path, line number, or verbatim error). A handoff with no evidence is a TODO, not a handoff.
- Recommended next skill names a real, installed skill (or `direct-dispatch`).

**Post-write: offer an explainer or a walkthrough.** Ask CD whether they want an HTML explainer (`sdlc-explain`, **handoff** storyboard) or a guided walkthrough (`sdlc-walkthru`) of the handoff doc — never unprompted. Mechanics and the precedes-approval rule: `[sdlc-root]/process/html-rendering.md` § Post-Skill Offer.

### 6. Surface the Handoff

Output to the user (plain text, not a question):

```
Handoff written: docs/current_work/ideas/{slug}_handoff.md

To pick this up in a new session:
  /clear
  /{recommended-skill} pick up the handoff at docs/current_work/ideas/{slug}_handoff.md

Or invoke the skill with the file as the seed in any way that matches your workflow.
```

Do NOT auto-clear the current session. The user decides when to context-switch.

### 7. Commit (optional)

If the project commits SDLC docs and the user wants the handoff visible across branches or to teammates, ask via `AskUserQuestion` whether to commit it now. **Headless run:** if the project commits SDLC docs, commit the handoff locally without asking and say so in the result's `notes`; never push it (`[sdlc-root]/process/headless-mode.md`). Suggested message:

```
docs: add {slug} handoff
```

If not committing, point out that the file is on disk but uncommitted — a session on a different branch won't see it.

## Output

- `docs/current_work/ideas/{slug}_handoff.md` — the handoff doc
- (Optional) Git commit adding the doc
- A clear next-step message for the user

## Validation Criteria

Before completing the skill, verify:

- The doc exists at the expected path
- Every required string field in the frontmatter is populated (no `{placeholder}` markers; `active_deliverable: null` is acceptable when no deliverable is active)
- The Evidence section has at least one concrete reference
- The Recommended next step names a real, installed skill or `direct-dispatch`
- The doc reads cold — a reader who hasn't seen this session can act on it

If any check fails, fix the doc before reporting completion.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll just leave a TODO comment in the code instead" | TODOs rot. A handoff is a tracked artifact that `sdlc-archive` inventories and resolves. Use the doc. |
| "The new session will read this conversation, I don't need to capture context" | The receiving session won't have this conversation. Capture every detail the receiver needs — file paths, error text, verbatim observations. |
| "I'll write a one-paragraph handoff and let the receiver figure it out" | Handoffs without evidence are worse than no handoff — they look like work but force the receiver to redo discovery. Either capture real evidence or don't write the handoff. |
| "I'll re-investigate to make the handoff thorough" | The handoff captures what's already known. Don't expand the investigation — that's the receiving session's job. Re-investigation is how this skill ends up duplicating `sdlc-idea`. |
| "I'll handle this in the current session, it's small" | If it would derail the current task, it's a handoff. The cost of context-switching mid-task is real and underestimated. |
| "It touches many records / writes to production, so it's non-trivial → plan it" | Volume and write-surface aren't effort. A known, repeatable transform over N items is Light effort — direct dispatch — regardless of count. Plans earn their keep when the *approach* is unclear, the work is cross-domain, or a wrong move is costly to reverse; not when the item count is high. |
| "I'll skip the recommended-next-skill field, the user can choose" | Always recommend. The receiver may override, but the recommendation forces you to think about which gate the work needs. |
| "I'll auto-clear the session after writing" | The user controls context switches. Surface the next-step command and stop. |
| "Multiple handoffs from one session can share a doc" | One handoff = one doc. Bundling makes the receiver disentangle them. Write separate docs. |
| "I'll write this as an idea brief instead" | Idea briefs are produced by `sdlc-idea` AFTER exploration. Handoffs are pre-exploration session captures. Different artifacts, different filenames (`*_idea-brief.md` vs `*_handoff.md`). |
| "The handoff doc is for me — terse notes are fine" | The handoff is for a future session that has zero shared context. Write for that reader. Telegraphic notes that depend on this conversation are worthless to the receiver. |
| "I'll skip Step 7 (Commit) — the user didn't ask for it" | The commit step is gated by `AskUserQuestion` for a reason: a handoff that lives only on the source-session branch is invisible to a session on `main` or another branch. Always ask in an interactive run. The user decides; you don't decide for them by skipping. A headless run commits locally instead (step 7). |

## Integration

- **Depends on:** Active session context (files touched, agent findings, observations); `docs/current_work/ideas/` directory (auto-created if missing).
- **Feeds into:** `sdlc-idea` (exploration of an unscoped handoff), `sdlc-lite-plan` (lightweight planning), `sdlc-plan` (full planning), `sdlc-debug-incident` (active incidents), direct dispatch (single-agent fixes), `sdlc-archive` (resolves handoffs to chronicle).
- **Uses:** `AskUserQuestion` for trigger classification and commit confirmation; `LSP`/`Grep` for quick reference confirmation only (no expanded investigation); `Write` for the doc.
- **Complements:** `sdlc-status` (shows active deliverables; it does not list handoffs, which sit in `docs/current_work/ideas/` until `sdlc-archive` inventories and resolves them).
- **Does NOT replace:** `sdlc-idea` — handoffs are session captures, not exploration output. `sdlc-debug-incident` — active production incidents need the incident skill directly, not a handoff routed through it. `sdlc-plan` / `sdlc-lite-plan` — handoffs name the work; planning skills scope it.
- **DRY notes:** The `*_handoff.md` filename and `docs/current_work/ideas/` location are already canonical conventions used by `sdlc-archive` (which handles archival of resolved handoffs). This skill produces the artifact; `sdlc-archive` cleans it up. Do not invent a parallel directory.
