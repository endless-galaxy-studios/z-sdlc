# Headless Mode

How a skill runs when no person is present to answer: in CI, in an issue-driven agent factory, or under `claude -p`. Every skill is written for a session where CD can answer questions and approve work. In a headless run nobody can, so each point that needs CD **stops the run** instead of being guessed past.

The rule lives here. Each skill carries a short verbatim copy of the stop rule (§ Mirrored Stop Rule), so skipping this file does not skip the behavior, and `CLAUDE-SDLC.md` § Use AskUserQuestion for All Questions states it for every session.

## When a Run Is Headless

A run is headless when either of these is true:

1. **The caller declares it.** The caller's prompt or appended system prompt has a line starting `SDLC headless mode:`. This is the primary signal. Anything that runs skills unattended (a workflow, a script, a scheduled job) should declare it, for example with `--append-system-prompt "SDLC headless mode: no person is present."`. The phrase quoted in this rule, in `CLAUDE.md`, or in a skill is not a declaration.
2. **No ask-the-user tool can be used** in the session running the skill: neither `AskUserQuestion` (Claude Code) nor the harness's equivalent (OpenCode's `question`) is available or loadable, or a call to it is denied without an answer (as under `--permission-prompts none` or `--disallowedTools AskUserQuestion`). A deferred tool that can be loaded counts as available.

Otherwise the run is interactive, and the ordinary rules apply.

**Subagents.** A dispatched subagent is never headless itself: it has no ask tool in any session, and it returns questions, DECIDE items and escalations to its orchestrator. In a headless run, the orchestrator says so in every dispatch prompt: the run is headless, outward actions are off limits (§ Outward Actions Go to the Caller), and questions come back to the orchestrator rather than being guessed. The limits bind the subagent through that prompt.

## The Rule

**Every point that needs CD stops the run.** At a question the next step depends on, an approval, or an escalation, the run stops at that point and returns what CD needs to see. It never guesses an answer, never takes a default for a decision CD owns, never approves its own work, and never skips the gate to keep going.

CD-facing points come in these kinds:

| Kind | Examples | Headless behavior |
|---|---|---|
| **Question the next step depends on** | Any `AskUserQuestion` not covered by another row; DECIDE findings; an unresolved INVESTIGATE; phase triage SKIP or REVISE_PLAN (`sdlc-execute`, `sdlc-lite-execute`); a data value that cannot be traced to its source; a request whose premise the code contradicts | Stop with status `needs-input`. |
| **A bounded loop ran out** without meeting its bar | A review loop at its round cap with a critical or major finding open (`[sdlc-root]/process/review-fix-loop.md` § Round Cap); a FIX that failed twice (a headless run stops instead of reclassifying it to INVESTIGATE or PLAN, and CD decides where it goes); the External Review Gate's fix-round limit; `sdlc-debug-incident`'s T6 escalation; `sdlc-tests-run`'s round limit | Stop with status `escalated` and the open-findings table or the loop's own stuck report. |
| **Approval gate** — CD approves a document or an action plan before the next step runs | Spec approval (`sdlc-plan` step 3); plan approval, where the Approval Brief is presented (`sdlc-plan` step 6, `sdlc-lite-plan` step 5); split approval (`sdlc-plan` § Splitting a Deliverable, with the split record as the document); approval of an action plan such as `sdlc-archive`'s archive set or `sdlc-migrate`'s change plan; a production gate in an executing plan, where the gate's steps are the action plan and the next run receives the gate's result (`sdlc-execute`, `sdlc-lite-execute`; `[sdlc-root]/process/production-gates.md`) | Save the document and stop with status `awaiting-approval`. An action plan that would exist only inside the question goes into the result itself, in full. Approval happens outside the run, and the next step starts in a new run that executes **exactly** what was approved; if the state no longer matches it, that run stops again. |
| **Soft gate** — scores CD may act on | The FAR gate (`sdlc-plan` discovery) and the FACTS gate (`sdlc-plan`, `sdlc-lite-plan`) | On a pass, record the scores in `notes` and continue. On a fail, stop with `needs-input` and the scores. |
| **Question the next step does not depend on** | PRE-EXISTING findings; minor PLAN findings; follow-ups for later work | Do not stop. List each under `deferred`, with its severity and options, and continue. A critical or major PLAN finding is not in this row: deferring it needs CD (`[sdlc-root]/process/manager-rule.md` § No Unilateral Finding Demotion), so it stops with `needs-input`. |
| **Optional offer** — CD may say yes or no, and no is safe | The explainer or walkthrough offer (`[sdlc-root]/process/html-rendering.md` § Post-Skill Offer); CP-11b's issue-creation offer; any "want me to also…" | Take the no path and list the offer under `skipped`. Never take the yes path: it does work CD did not ask for. |
| **Confirmation of local, reversible work** | Committing the skill's own output locally, such as `sdlc-handoff` step 7's commit question | Proceed, even where the skill frames the step as optional: local work is allowed (§ Outward Actions Go to the Caller). Say so in `notes`. |

**A question the inputs already answer is not a gate.** Before stopping, read the prompt and any thread or earlier answers the caller passed. Stop only on what they leave open. A deliverable name the caller supplied, a tier set by an earlier triage, or an answer CD already gave in the thread does not stop the run.

**Ask what blocks the next step, and no more.** Where a skill has its own pacing rule, it still holds: `sdlc-plan` discovery asks one question at a time, so a headless discovery stop carries one question.

**Discovery check-in: the one exception, and only when the caller asks for it.** A caller that wants CD to confirm the basis of a spec before it is written asks for a **discovery check-in** in its prompt, in those words. `sdlc-plan` then stops once with status `needs-input`, after the DISCOVERY-GATE and the FAR gate pass and before any agent writes the spec. The stop carries one question, "is this the right basis for the spec?", in about 300 words (`[sdlc-root]/process/writing-for-cd.md`):
- one line naming what the spec carries over from what CD already approved (an earlier spec, a split record, CD's answers), not restated item by item;
- each assumption CD hasn't decided (the run's or an agent's own judgment), in one line with its source;
- each open choice in one line: the choice, the recommendation, and what the main alternative would cost.

Facts and detail go in `notes`.

It is not a batch. Blocking questions still stop the run one at a time, and the check-in comes after the gates pass, when none is left. It happens once per deliverable, and CD's reply confirms or corrects the basis. *Why:* a headless run can settle discovery from records alone and never stop, and then a wrong assumption costs a whole spec run before CD sees it. Without the request, an answered question is still not a gate.

**Work done before the stop stays.** Documents written to disk, local commits and a partial result doc are kept. Stopping is not a rollback.

## Outward Actions Go to the Caller

A headless run has no one to confirm an outward-facing action, so it **causes no side effect outside the working tree.** That means it does not:

- push, or open or update pull requests;
- post comments, change labels or issues, publish artifacts, or send messages;
- send code or documents to an external service. The External Review Gate runs headless only against a local model or a hosted provider the project has durably authorized; otherwise it is skipped and listed under `skipped`;
- change a live system: deploy, roll back, restart, scale, or run a migration against a shared database;
- write github-provenance checkpoints to GitHub. A checkpoint's local half still happens (issue links in frontmatter and the catalog when the issue is known, the local artifact commit), and its GitHub half goes under `outbound` as a rendered entry the caller can apply (`[sdlc-root]/process/github-checkpoints.md` § Headless Runs).

It lists each action it would have taken under `outbound`, and the caller decides.

Local work is fine: writing files in the working tree, running tests and builds, and committing locally. Reads are fine from anywhere: the codebase, Context7, web search, `gh` reads, fetching an upstream repo. Writes to the project's configured knowledge backend (an adapter's memory store) count as local work, because they are how the framework records what it learned.

**Exception:** the caller's prompt may hand a named outward action to the run ("you may push to `<branch>`"). Only that action, and only as named.

## Ending a Headless Run

**A stop is a result, not an error.** End the turn normally with the result; never abort to signal a stop. The run cannot choose its own exit code, so the status is what tells the caller what happened. A stop and a finished run both end normally.

**Dispatch every agent in the foreground and wait for its result.** Never use `run_in_background`, in any step, reviewers included. A headless run ends when the orchestrator's turn ends, so ending the turn to wait for a background agent ends the run, and the agent's work is lost. Run independent agents in parallel as several foreground calls in one message. Callers should also switch background launches off in the runtime (`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` for Claude Code), because some runtimes launch agents in the background by default.

**Stop before a time limit, not at it.** A caller that kills the run at a time limit gives it a **time budget** in its prompt: how long the run has, and how much of it to keep for stopping. Note the time when the run starts (`date`) and check it between steps; a dispatched agent's work counts against the budget too. Once only the margin is left, start nothing new: finish or set aside the step in progress, commit what is done locally, and stop with the status the caller names for running out of time, putting what is done and what is left in `notes`. A run killed at the limit returns nothing, so stopping early with a result always beats running to the kill.

**`failed` is for a precondition the caller must fix:** no deliverable catalog, no plan to execute, a broken environment. Give the `reason`. Crashes and exhausted turn or time limits reach the caller through its own failure path.

Every headless run ends with a result, whether it stopped at a gate, failed a precondition, or finished. A skill's own closing output (a completion report, a summary) comes first; the result is always last.

**Write the result for CD where CD will read it.** A caller posts the questions, the reason for a stop, findings and deferred items where CD reads them, so they follow `[sdlc-root]/process/writing-for-cd.md`: lead with the decision, use plain language, one line per option or item, and keep a stop's reason to 1–2 sentences. `notes` is for the next run and keeps its detail.

- **If the caller passed an output schema** (`--json-schema`), that schema is the contract. Map the result onto its fields — its state or status field, its questions field — and return nothing else. The skill's own closing output still goes where the skill saves it (a result doc, for instance). Anything the schema has no field for — `notes`, `deferred`, `skipped`, `outbound` — goes into the stage's saved document under a `## Headless Result` heading, if the stage saves one. Callers running stages that can stop should give their schema those fields. When the schema has fields for a pull request's description (a `brief` object, or one field per section), fill them per `[sdlc-root]/templates/pr_description_template.md`. For a spec or plan, take them from its Approval Brief (`[sdlc-root]/process/writing-for-cd.md` § Approval Briefs) rather than writing a second brief. Never paste them from the plan body, which stays the agent's contract.
- **Otherwise** end with this block as the final message:

```markdown
## Headless Result
- **status:** done | needs-input | awaiting-approval | escalated | failed
- **stage:** <skill> — <step to restart from>
- **reason:** (failed) the missing precondition and what the caller must fix
- **questions:** (needs-input) each question with why it blocks and its options, recommended first, as AskUserQuestion would present them
- **findings:** (escalated) the open-findings table: finding, agent, severity, what each fix attempt returned, hypothesis
- **documents:** paths written or updated this run, marking the one awaiting approval; an action plan awaiting approval goes here in full
- **deferred:** questions CD should see that did not block the run, each with its options
- **notes:** what the next run needs so it does not redo work: decisions made, research results, what was checked and ruled out
- **skipped:** optional offers taken as no, and gates skipped for lack of authorization
- **outbound:** outward actions handed to the caller. A github-provenance checkpoint is a rendered entry: issue, comment body, Status target and write condition, commits to push. A `ranks` item rides along for the Status writes (`[sdlc-root]/process/github-checkpoints.md` § Headless Runs)
```

`notes` matters most. The next run starts cold, and anything not in the documents or the notes gets redone at full cost.

## Resuming

A headless run is **restarted, not resumed.** The caller starts a new run at the `stage` the result named and passes CD's answer along with the earlier thread. The new run reads the saved documents, the earlier result's notes and CD's answers, then continues from the gate. A skill whose restart from step 1 would repeat a side effect or lose counted state (a D-number, completed phases, a review round) carries a **Headless restart** paragraph in its entry step: `sdlc-plan`, `sdlc-lite-plan`, `sdlc-execute`, `sdlc-lite-execute`. It skips work already done, never registers the deliverable a second time, and carries on counting where the earlier run stopped: completed phases, the review round, the frozen round-1 roster. Other skills restart from step 1, where questions the thread has answered are not gates and an approved action plan from the earlier result is what runs. It does not re-ask an answered question, and it does not redo work the notes record as done.

An approval arrives the same way. Once CD has approved the document or action plan, by whatever surface the caller uses, the caller starts the next step as a new run.

## Mirrored Stop Rule

Every skill carries a verbatim copy of the block below, so the stop rule is read at the skill itself and never reduced to a skippable pointer (the 2026-05-19 changelog entry, "Inline Critical Guardrails Lost in Skill Consolidation", records what happens to pointer-only rules).

| Block | Source section id | Mirrored in |
|-------|-------------------|-------------|
| Headless stop rule | `headless-stop-rule` | Every `sdlc-*` skill. Project skills may carry it too; `sdlc-develop-skill` adds it to the skills it creates |

**Placement:** directly after the skill's `**AskUserQuestion mandate:**` paragraph when it has one; otherwise directly before the skill's first `##` section.

**Markers.** The source block below is wrapped in `<!-- MIRROR-SOURCE-START: {id} -->` / `<!-- MIRROR-SOURCE-END: {id} -->`; each copy in a skill is wrapped in `<!-- MIRROR-START: headless-mode.md#{id} -->` / `<!-- MIRROR-END: headless-mode.md#{id} -->`. The lines between the markers must be identical — any difference is a drift finding (`sdlc-reviewer` § Cross-skill DRY; the framework audit's cross-skill DRY dimension). To change the block, edit it here and re-copy it into every skill. Some gates need their stop stated at the gate itself: the status it stops with, what the stop carries, a step it skips, or an outward action it would otherwise take. Those get a **Headless run:** line outside the markers, at the gate, and the gate is added to § Integration. Marker conventions: `[sdlc-root]/process/project-section-markers.md` § MIRROR Markers.

<!-- MIRROR-SOURCE-START: headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-SOURCE-END: headless-stop-rule -->

## Red Flags

| Thought | Reality |
|---|---|
| "Nobody's here to ask, so I'll pick the reasonable option" | That is guessing at a decision CD owns. Stop with `needs-input`. |
| "The spec is solid; I'll treat it as approved and start the plan" | Approval happens outside the run. Stop with `awaiting-approval`. |
| "CD will approve the archive set when they see the result, so I'll describe it briefly" | The restarted run executes exactly what CD approved. Put the whole action plan in the result. |
| "I'll ask everything at once to save a round trip" | Ask what blocks the next step, and follow the skill's own pacing rule. |
| "This PRE-EXISTING finding needs CD, so I'll stop" | The next step does not depend on it. List it under `deferred` and continue. |
| "The FIX failed twice, so I'll reclassify it as PLAN, defer it and finish" | A headless run stops instead of reclassifying. Stop with `escalated`, and CD decides where the finding goes. |
| "The restarted run should start from step 1 to be safe" | It skips work already done and never registers the deliverable twice. Follow the skill's **Headless restart** paragraph. |
| "The writer is still running in the background; I'll end my turn and wait for it" | Ending the turn ends the run. Dispatch in the foreground and wait. |
| "Stopping means the run failed" | A stop is a normal result; end the turn normally. `failed` is only for a precondition the caller must fix. |
| "I'll post the question on the issue myself" | Outward actions go to the caller. List the post under `outbound`. |
| "The fix agent can restart the service; the incident is urgent" | A live-system change is an outward action. List it under `outbound`, unless the caller's prompt named it. |
| "The subagent isn't headless, so the outward-action ban doesn't reach it" | The orchestrator tells every subagent the run is headless. The ban binds it through the dispatch prompt. |
| "The next run can work this out again" | It starts cold. Put it in `notes`. |
| "I'm near the time budget, but one more step will finish it" | A killed run returns nothing. At the margin, commit what is done and stop with the status the caller named. |
| "We're at the review cap with a major open, but it's close enough" | Stop with `escalated` and the open-findings table. Never claim the loop is clean. |
| "I'll accept the explainer offer so CD has it later" | Optional offers take the no path. |
| "The thread already answers this, but I'll confirm" | An answered question is not a gate. Continue. The one exception is a discovery check-in the caller asked for, which comes once, after discovery. |

## Integration

- **States it for every session:** `CLAUDE-SDLC.md` § Use AskUserQuestion for All Questions
- **Mirrored in:** every `sdlc-*` skill (§ Mirrored Stop Rule)
- **Gate sites with their own headless line:**
  - `sdlc-plan`: step 0 (headless restart), the DISCOVERY-GATE, the FAR gate, the discovery check-in (when the caller asks for one), step 3 (spec approval), the FACTS gate, step 6 (plan approval), § Splitting a Deliverable (split approval), and the Output section
  - `sdlc-lite-plan`: step 0 (headless restart), the FACTS gate, step 5 (plan approval), and the Output section
  - `sdlc-execute`: step 0 (headless restart; no plan → `failed`; an unfinished prerequisite gating the next phase → `needs-input`; a production gate → `awaiting-approval` after the review and commit before it), phase triage, step 4's push and pull request, and step 5's Completion Report
  - `sdlc-lite-execute`: step 0 (headless restart; no plan → `failed`; an unfinished prerequisite gating the next phase → `needs-input`; a production gate → `awaiting-approval` after the review and commit before it), phase triage, and step 5's Completion Report
  - `sdlc-handoff`: step 7 (local commit) and its red flag
  - `sdlc-cleanup-comments`: step 1 (uncommitted changes in scope, or a range not ending at `HEAD` → `failed`), step 2 (no way to verify → `failed`), step 3 (an area no agent owns → `needs-input`; otherwise the proceed question → proceed), step 4 (`HEAD` moved during the run → `failed`; a changed file outside every slice → left, `deferred`), step 6 (a slice that can't pass, also reached from steps 4, 5 and 8 → nothing restored; while a failure remains, nothing committed; `deferred`), step 8 (kept comments → `deferred`; the handoff offer → `skipped`) and step 9 (local commit, only when the last verify matched the baseline, else nothing committed, `deferred`; a slice changed during the run → uncommitted, `deferred`)
  - `sdlc-develop-verify-skill`: the precondition, checked first (untracked or uncommitted files in `.claude/skills/verify/`, or the folder git-ignored → `failed`), mode resolution (a verify skill already exists, or one written by hand → `needs-input`; a maintain request with none → `failed`; adopting a command that breaks a Safety Rule → `needs-input`), CREATE step 1 (gaps the code can't answer, a target that can't be made local or seen resolving before the first write, an integration the app can't start without and can't sandbox, a missing driving tool → `needs-input`; nothing to drive → `failed`), step 2 (the app doesn't start → `failed`), step 5 (launch or the health check still failing after three attempts → `escalated`), step 6 (a major review finding still open after two tries → `escalated`) and step 7 (local commit), and MAINTAIN step 1 (evidence found committed → `failed`) and step 7 (proven fixes → local commit; `blocked` → `escalated`; product bugs → `deferred`, the bug-route offer → `skipped`)
  - `sdlc-audit`: improvement mode's factory-digest input and § Applying Improvements (proposals returned with `awaiting-approval`; nothing applied)
  - `sdlc-implement` and `sdlc-revise` (the `factory` bundle; always headless): a failure that survives two fix attempts (§ 4 Verify) and the review cap (§ 5), each returning `escalated` after a commit; and `sdlc-revise`'s execution PR at a production gate (§ 7, `awaiting-approval` naming the gate)
  - `[sdlc-root]/process/production-gates.md` § At a Gate (`awaiting-approval` before a gate; the restart after it)
  - `[sdlc-root]/process/review-fix-loop.md` § Round Cap
  - `[sdlc-root]/process/html-rendering.md` § Post-Skill Offer
  - `[sdlc-root]/process/external-review-gate.md` (sanctioned skips; § Data egress)
  - `[sdlc-root]/process/github-checkpoints.md` § Headless Runs, the activation line of each checkpoint-firing `github-provenance` fragment, and `sdlc-archive`'s archive-time checklist executor
- **Manager rule (subagent escalation):** `[sdlc-root]/process/manager-rule.md`
- **PR-description fields in a caller's schema:** `[sdlc-root]/templates/pr_description_template.md`, filled from the Approval Brief for a spec or plan (`[sdlc-root]/process/writing-for-cd.md`)
