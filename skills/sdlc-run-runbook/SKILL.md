---
name: sdlc-run-runbook
description: >
  Run a project's runbook ([sdlc-root]/process/runbooks.md): a one-time or occasional procedure, such as
  enabling a bundle, that a process doc lays out step by step. Lists the runbooks and where each stands; runs one
  in a session with CD present, resuming from its record, asking its decisions four at a time, taking each step,
  running each step's check and writing the result to the record, with a committed handoff at each phase's end.
  Triggers on "run the runbook", "continue the runbook", "enable the factory", "continue the factory install",
  "enable github provenance", "set up the external review gate", "set up the verify command",
  "which runbooks are open", "where does the install stand", "/sdlc-run-runbook".
  Do NOT use for installing or updating the framework's or a bundle's files — use sdlc-initialize or sdlc-migrate.
  Do NOT use for planning or building a deliverable — use sdlc-lite-plan or sdlc-plan.
  Do NOT use for a procedure the project repeats as everyday work — that is a skill (sdlc-develop-skill).
---

# Run a Runbook

Drives any runbook: a process doc, or a section of one, whose first line is a `**Runbook:**` marker
(`[sdlc-root]/process/runbooks.md`). The runbook holds the procedure; its record, in the project, holds where the
run stands. This skill keeps the session to both: one step at a time, each check run and written down, so a run
that spans days and many sessions picks up exactly where it stopped.

**Argument:** `$ARGUMENTS`: nothing (list the runbooks), or a runbook's id, optionally with a step ID to resume
at (`factory-enablement 3.3`).

**AskUserQuestion mandate:** every question directed at CD MUST use the `AskUserQuestion` tool, never
conversational text (Tool Rule in `[sdlc-root]/process/collaboration_model.md`). Ask at most four at a time,
grouped by topic, the recommended answer first, each option saying what it forecloses. Text shown next to a
pending question can be lost, so deliver findings and tables as a message of their own first, and make each
question carry its own facts.

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Two exceptions stand: the skill's own knowledge-layer updates count as local work, even when an adapter writes them to its memory store (a subagent's own memory-store writes don't), and the External Review Gate may send to a hosted provider the project has durably authorized (`[sdlc-root]/process/external-review-gate.md` § Data egress). Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

**Headless run:** a runbook is run with CD present. A headless run lists the runbooks (step 1), or for one, reads
where it stands and takes only its read-only steps (an inventory, a check). It returns the next decisions and the
next **[CD]** steps as `needs-input`, and writes nothing but the record.

## Workflow

```
FIND (marker lines in [sdlc-root]/process/) → LOAD (the runbook + its record; add missing record parts)
  → RESUME (first step with no passed check; confirm relayed decisions) → DECIDE (up-front questions, 4 at a time)
  → STEP ⟲ (do it, or hand CD a [CD] step → run its Check → write State) → PHASE END (Status, Next, handoff, commit)
  → DONE (definition of done all true → Status done)
```

## Manager Rule

Read and follow `[sdlc-root]/process/manager-rule.md`. Dispatch prompts must describe WHAT/WHY — implementation
HOW is the agent's domain.

## Agent Selection Criteria

Pick agents from the project's roster with `[sdlc-root]/process/agent-selection.yaml`, and take the runbook's
own word where it names one:

| A step that | Agent |
|---|---|
| Surveys the project before decisions (an inventory) | One research agent, read-only |
| Changes the project's configuration, CI or code | The domain agent for what it changes |
| Touches a security boundary (credentials, access, code ownership, a database role) | That domain agent, with the security agent as reviewer |
| Designs something the runbook has no template for | The architecture agent, then security |

**Dispatch.** Each prompt names the runbook's step the agent works from, the record entry it reports into, and
its limits: an inventory is read-only; no agent reads or writes a secret's value, runs a root step, or pushes.
In a headless run, the prompt also says the run is headless.

**Review lenses.** Every change a step makes goes through a PR CD reviews, with review rounds sized to its risk
(`sdlc-review-code`): the full roster for production code, host setup and security boundaries. An implementation
reviewer checks that the change does what the step says; a security reviewer checks that nothing widens a
credential's reach and that a code-owned file stays code-owned.

## Steps

### 1. Find

Each runbook opens with one marker line (`[sdlc-root]/process/runbooks.md` § What makes a doc a runbook):

```
**Runbook:** `<id>` · **When:** <enable | setup | on-demand> · **Record:** `<project path>` § <section>
```

Search `[sdlc-root]/process/*.md` for marker lines in that full form (`[sdlc-root]/process/runbooks.md` § What
makes a doc a runbook says what isn't one). With no argument, show each runbook's id,
when it runs, its doc, and its record's **Status** and **Next**: "no record yet" when there's none, and "in
progress (no Status yet)" when the record holds decisions or results but no Status line. Show it as a table in a
message of its own, and stop. An unknown id: say so, show the list, and stop.

### 2. Load

1. **Read the runbook in full:** the whole doc, or for a section, from its marker to the next heading of the same
   level. Read anything it says to read first.
2. **Read its record.** The record's file and section come from the marker. Add whatever of the record's parts
   are missing (Status, Next, Decisions, State, Deferred: `[sdlc-root]/process/runbooks.md` § The record), in the runbook's own words
   and table shapes when it gives them, without rewriting anything already there. A record written before this
   convention, or kept elsewhere (a transaction log, a handoff), is read for what it records, and the facts it
   holds are carried into the record's parts with their source named. Where an older State line doesn't say
   whether its check passed, write the outcome it shows and cite the line; when it can't be told, re-run the
   check. Then set **Status** to `in progress` with today's date, since a run has started: a prior `done` or
   `declined` moves to Decisions first, with its date, as reopened. **Next** is set by step 6.

### 3. Resume

1. **Where it stands.** The run starts at the step the argument names, or else at **Next**, or else at the first
   step **State** doesn't record as passed, done or skipped (`[sdlc-root]/process/runbooks.md` § The record), in
   the order the runbook says to take its steps. A step a recorded decision makes inapplicable is recorded
   skipped, with the decision, rather than started. Show CD where it stands, as a message of its own: done,
   next, and anything deferred.
2. **Decisions relayed from elsewhere are confirmed here.** A decision that reached this session from another
   (a handoff, a note, a message) and isn't in the record with its date and session is confirmed with CD before
   anything acts on it. One the record already holds stands, unless CD reopens it or a step shows it wrong; one
   the runbook itself records isn't asked (`[sdlc-root]/process/runbooks.md` § What makes a doc a runbook).
   A decision reopened changes the steps built on it: record each of them `failed`, citing the decision, and
   redo it.
3. **The runbook's ground rules,** when it has them (who owns the run, which branch it works on, what may be pushed
   while it runs), are agreed once per session and written to Decisions with this session. Ground rules are not a
   step: a section that only holds them is never where a run resumes.

### 4. Decide

On the run's first session (its record holds no decisions yet), ask the runbook's up-front questions, four at a time, in its order, the recommended answer
first, each with its alternatives and its cost to reverse. Ask a decision the runbook marks hard to reverse
carefully, once. A survey step that answers some questions (an inventory) runs first when the runbook says so,
and its findings are shown to CD before the questions. A survey recorded as done whose findings are gone runs
again, read-only, before anything relies on them, and before the decisions it informs are confirmed. On a later session, ask only the open questions the next step
depends on; the rest wait for the step that needs them. Write each answer to **Decisions** as it's given: the
question, the answer in CD's words, the date, this session.

### 5. Step, check, record

Take the steps in the order the runbook says (its numbering, unless it says otherwise), from where the run stands:

- **An agent's step:** do it, or dispatch it (§ Agent Selection Criteria). A step that needs the framework itself
  changed (a missing profile, a bundle bug, rule text the runbook lacks) isn't done in the project: the
  framework's files come from z-sdlc and the next migration overwrites them. Write it as a handoff for a z-sdlc
  session (`sdlc-handoff`), record it under **Deferred**, and go on with the steps that don't depend on it.
- **A [CD] step:** tell CD exactly what to do and where, and wait. When the runbook groups CD's steps (a sitting
  for secrets, one for hosts), batch them: each is an interruption.
- **Credentials never pass through the session.** A credential from elsewhere, CD writes at the store's own
  masked prompt in CD's own terminal. A random secret the project itself needs may be generated in one pipeline
  that writes it straight into its store (`openssl rand -hex 32 | gh secret set NAME`), never printed, written
  to a file the session reads, or shown in a screenshot.
- **Root steps** are CD's, or the agent's only under temporary access CD grants and removes. **Nothing that may
  deploy** (a push to a branch a host deploys from, a workflow change) goes out without CD's say for that push.
- **Run the step's Check** and write its outcome to **State** (`[sdlc-root]/process/runbooks.md` § The record). A
  step whose section lists numbered items records each item (`3.3 item 6`), so a run can resume at the one that
  stopped. A failed check stops that
  step: fix it, or record it under **Deferred** with CD's say. A step is never recorded as passed on anything but
  its check.

### 6. Phase end

When a phase of the runbook ends, or the session does: set **Status** and **Next** (the step to start at, and
what it does first), commit the record with the phase's changes (inside `sdlc-initialize` or `sdlc-migrate`, with
theirs), and write a handoff (`sdlc-handoff`) saying what's done, what's next and what's decided. A run that spans
sessions and context compactions loses what isn't committed. A run that reaches step 7 in this session needs no
handoff: its report says the same (`[sdlc-root]/process/runbooks.md` § The record).

### 7. Done

The run is done when every line of the runbook's definition of done is true and recorded, or recorded skipped
with the decision that made it inapplicable. Set **Status** to
`done` with the date, mark every decision built, deferred or dropped, and report what was done, what's deferred
and who owns it. Update anything the runbook says the organization keeps (its shared records) in the same work.

## Red Flags

| Thought | Reality |
|---------|---------|
| "CD can paste the token here and I'll set it" | A secret through this session reaches the model. CD writes it at the store's masked prompt in CD's own terminal. |
| "The check is obviously fine, I'll mark the step passed" | State records only what a check showed. Run it. |
| "The bundle's script is wrong; I'll patch it in the project" | The framework's files come from z-sdlc and migrations overwrite them. Hand the fix to z-sdlc and record it as deferred. |
| "Another session already decided this" | A relayed decision is confirmed in this session before anything acts on it. |
| "I'll ask the questions one at a time as they come up" | Ask them up front, four at a time: the hard-to-reverse ones change everything after them. |
| "I'll renumber the steps to tidy the runbook" | Records, handoffs and other docs cite the step IDs. Add a number, or mark a step dropped. |
| "I'll write the handoff when the whole run is done" | Each phase ends with one. A long run loses what isn't committed. |
| "This procedure deserves its own skill" | A one-time or rare procedure is a runbook (`[sdlc-root]/process/runbooks.md` § A skill or a runbook). |
| "I'll do the step myself instead of dispatching" | The manager rule holds: dispatch what the delegation exception doesn't cover. |
| "This step is wrong for this project; I'll quietly do it differently" | Record what differed and why under Decisions, and hand the fix to the runbook's owner: z-sdlc for a bundle's runbook, the project's own changelog for its own. |

## Integration

- **Depends on:** a runbook installed in `[sdlc-root]/process/` with its marker line; the convention in
  `[sdlc-root]/process/runbooks.md`; the core process docs it cites (`collaboration_model.md`, `manager-rule.md`,
  `agent-selection.yaml`, `headless-mode.md`); a git checkout to commit the record in; CD present
- **Feeds into:** the runbook's record in the project; handoffs (`sdlc-handoff`); z-sdlc, through handoffs for
  framework gaps a run finds
- **Uses:** `sdlc-handoff`, `sdlc-review-code`, `[sdlc-root]/process/agent-selection.yaml`,
  `[sdlc-root]/process/manager-rule.md`
- **Complements:** `sdlc-initialize` and `sdlc-migrate`, which offer a bundle's `enable` runbook when it's
  installed and each `setup` runbook a project has no record of; `sdlc-status`, which lists runbooks still open
- **Does NOT replace:** `sdlc-initialize` or `sdlc-migrate` (they install files; a runbook configures what they
  installed), the planning and execution skills (a deliverable's work), or a bundle's `## After migrating`
  section, which `sdlc-migrate` follows itself
- **DRY notes:** the procedure lives in each runbook and the convention in `runbooks.md`; this skill holds only
  how to drive them, so a runbook's change needs no change here
