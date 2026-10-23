# Writing for CD

How an SDLC session writes anything CD reads. CD owns the project but doesn't watch the work. Long, dense output gets skimmed or skipped, and an approval CD couldn't follow isn't a real approval.

## Where It Applies

Everything addressed to CD:
- status updates and end-of-turn summaries;
- questions, including the text of an `AskUserQuestion` call;
- approval briefs for specs and plans (§ Approval Briefs);
- completion reports (`sdlc-execute` and `sdlc-lite-execute` step 5);
- PR descriptions (`[sdlc-root]/templates/pr_description_template.md`);
- findings CD must act on, and improvement proposals (`sdlc-audit` improvement mode, including an agent factory's weekly report);
- the parts of a headless run's result that a caller shows CD: the questions, the reason for a stop, findings and deferred items (`[sdlc-root]/process/headless-mode.md` § Ending a Headless Run). The result's `notes` are for the next run and keep their detail.

It doesn't apply to what agents work from: the body of a spec, plan or result doc, and dispatch prompts. Those keep their detail.

A personal output style can sit on top, for example to set how deeply terms get taught. This standard sets what is said and how long it runs. A style can't override it, and the framework doesn't ship one: only one style can be active, and styles don't reach dispatched agents.

## The Rules

1. **Lead with what CD needs:** the decision, the outcome or the action. Background comes after, if at all.
2. **Plain language.** Write for someone who knows the product but not this change. Define a term the first time you use it, or leave it out. Internal labels (gate names, finding classes such as DECIDE, phase and deliverable numbers) can tag a line, but the sentence must make sense without them.
3. **Say each thing once.** Don't restate what CD just saw, and don't summarize your own summary.
4. **Evidence over claims.** Show what ran and what came out. "All tests pass" on its own is a claim.
5. **Say where you're unsure:** the part you're least confident in, and what CD may not have thought of.
6. **Don't invent.** A section with nothing true to say is left out.
7. **Keep to the budget.** If it won't fit, cut what CD needs neither to decide nor to learn, and point to the document that has the rest.
8. **No stock phrasing.** Rewrite words and patterns that read as machine-written, because they say less than they sound like they do:
   - inflated words: crucial, pivotal, delve, robust, seamless, leverage, utilize, showcase, underscore, landscape, testament;
   - "serves as" or "stands as" where "is" will do, and "not just X, but Y";
   - a trailing "-ing" clause that adds nothing ("…, ensuring reliability");
   - unnamed authorities ("experts say", "industry reports suggest");
   - chat openers and closers ("Great question", "I hope this helps");
   - filler ("in order to", "it's important to note that") and stacked hedges ("could potentially").

   These are prompts to rewrite, not banned words: the test is whether the sentence names a mechanism, a fact or a number.

## Length Budgets

| What | Budget |
|---|---|
| A status update while working | 1–2 sentences |
| A question | The decision, why it matters, and each option's consequence in a line |
| The reason a headless run stopped | 1–2 sentences |
| A discovery check-in (`sdlc-plan`, headless) | About 300 words: only what CD hasn't already decided, one line per assumption and per choice |
| An end-of-turn summary | About 150 words |
| An approval brief (spec or plan) | About 450 words |
| A completion report or code PR description | About 500 words (a report's What you need to do and Commits come on top) |
| An improvement proposal | About 100 words: the change, why (with its evidence) and the expected effect, a line or two each |

## Status Blocks

Skills print status blocks (gates, review checklists, scores) as proof that a step ran. **On the happy path a block is one line. The full block appears only when a check fails or CD must act.** Each skill defines both forms; print one, never both.

A soft gate (FAR, FACTS) that passes prints its line and the run continues; CD can still stop it. When it fails, show the scores and wait for CD.

Before a findings table, one plain sentence says what it means for CD: how many findings, how many get fixed now, and which need CD's decision.

## Approval Briefs

CD approves a spec or a plan from its **Approval Brief**, a section at the top of the document. It is written for CD in the shape of the plan variant of `[sdlc-root]/templates/pr_description_template.md`. The rest of the document stays the agents' contract, so approving the brief must never approve something CD didn't see.

**CD sees the brief verbatim, then the document's path, in a message that ends the turn.** The manager never summarizes the document in its place. CD's reply is the approval or the change request. This is the one approval asked for without `AskUserQuestion`: a pending question can lose text shown in the same turn.

When the approval happens through a pull request, the brief is the PR description. In a headless run, the caller's PR-description fields are filled from it.

<!-- MIRROR-SOURCE-START: approval-brief -->
**Approval Brief procedure.** The document's writing agent writes the brief once the document is final (after review, for a plan). The manager never writes it, except a WORDING fix CD asked for during spec approval.

1. **Dispatch the writing agent** to fill the document's `## Approval Brief` section with `Edit`, changing nothing else in the file. It fills the template's `###` headings, keeping them at level 3 and adding no agent-record `<details>`, as the plan variant of `[sdlc-root]/templates/pr_description_template.md` describes each section: plain language, about 450 words, from the document as it now stands. Every decision the document leaves to CD goes under What you're approving: a table CD approves, a `USER DECISION NEEDED`, or scope beyond what was asked for or approved. For a plan, pass it the review round count and the number of open minor findings for the brief's Review line.
2. **Dispatch a fresh reader** in the foreground: a new subagent given only the document's path, told to read the brief first and then the rest. It reports whether someone who didn't watch the work could explain the problem, the change, the choices, the risks and the evidence from the brief alone; any statement the document doesn't support; and any decision left to CD that the brief leaves out. Send its findings to the writing agent to fix. One pass, not a loop.
3. **Count the words:** `awk '/^## Approval Brief/{f=1;next} /^## /{f=0} f' <document path> | wc -w`. If the brief runs well past 450 words (over about 600), send it back to the writing agent once to cut.
<!-- MIRROR-SOURCE-END: approval-brief -->

## Completion Reports

The execution skills end with a Completion Report, shaped by the block below.

<!-- MIRROR-SOURCE-START: completion-report -->
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
<!-- MIRROR-SOURCE-END: completion-report -->

## Mirrored Blocks

The skills carry verbatim copies of this doc's two procedures, so skipping this file doesn't skip them.

| Block | Source section id | Mirrored in |
|-------|-------------------|-------------|
| Approval Brief procedure | `approval-brief` | `sdlc-plan` (steps 2a, 5b), `sdlc-lite-plan` (step 4a) |
| Completion Report | `completion-report` | `sdlc-execute`, `sdlc-lite-execute` (step 5) |

**Markers.** Each source block is wrapped in `MIRROR-SOURCE-START` / `MIRROR-SOURCE-END` markers carrying its id. Each copy in a skill is wrapped in `MIRROR-START` / `MIRROR-END` markers naming this file and the id. The lines between the markers must be identical; any difference is a drift finding. Edit a block here, then re-copy it into every skill that carries it. Site-specific lines (which document, headless, step references) go outside the markers. Marker conventions: `[sdlc-root]/process/project-section-markers.md` § MIRROR Markers.

## Integration

- **Stated for every session:** `CLAUDE-SDLC.md` § Writing for CD, and the approval-by-reply exception in § Use AskUserQuestion for All Questions
- **Approval briefs:** § Approval Briefs, mirrored into `sdlc-plan` steps 2a and 5b and `sdlc-lite-plan` step 4a, and presented in `sdlc-plan` steps 3 and 6 and `sdlc-lite-plan` step 5; the Approval Brief section of `[sdlc-root]/templates/spec_template.md`, `planning_template.md` and `sdlc_lite_plan_template.md`
- **Completion reports:** § Completion Reports, mirrored into `sdlc-execute` and `sdlc-lite-execute` step 5
- **Discovery check-in:** `sdlc-plan`, before step 2; `[sdlc-root]/process/headless-mode.md` § The Rule
- **PR descriptions:** `[sdlc-root]/templates/pr_description_template.md`
- **Status blocks with a one-line form:** VERIFICATION-GATE and the FACTS gate (`sdlc-plan`, `sdlc-lite-plan`; also `[sdlc-root]/process/input-quality-gates.md`); DISCOVERY-GATE and the FAR gate (`sdlc-plan`); PRE-GATE and POST-GATE (`sdlc-execute`, `sdlc-lite-execute`, which print REVIEW-GATE as one line); the review-round line (`[sdlc-root]/process/review-fix-loop.md` Step A)
- **Findings tables:** `[sdlc-root]/process/finding-classification.md` § Classification Table
- **Headless runs:** `[sdlc-root]/process/headless-mode.md` § Ending a Headless Run
