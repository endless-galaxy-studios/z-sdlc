# Improvement Audit Methodology

Detailed patterns for extracting SDLC process improvements from sessions and commits. The goal is to identify how the SDLC itself should evolve — not whether it was followed (that's compliance), but whether it's good enough.

## The Self-Improvement Loop

```
Session work → Improvement audit → Process changes → Better session work
```

Every session is data. Friction, corrections, missing knowledge, and process bypasses are signals that the SDLC has gaps. The improvement audit reads those signals and proposes targeted changes.

## Extraction from Sessions

### Process Friction Signals

Scan the conversation for moments where the SDLC process either helped or hindered:

**Skill invocation patterns:**
- Was a skill invoked? Which one? Did it fit the task?
- Was a skill NOT invoked when it should have been? (User did work that matches a skill's trigger but didn't use it)
- Was a skill invoked but abandoned mid-workflow? (Skill didn't fit)
- Were multiple skills considered before choosing one? (Ambiguous trigger conditions)

**Workflow mismatch:**
- Did the skill's phase structure match the actual work? (Steps skipped, steps added, steps reordered)
- Were there phases in the work that no skill covers?
- Did the user have to interrupt the skill workflow to handle something unexpected?

**Agent dispatch issues:**
- Were agents dispatched that weren't useful? (Wrong agent for the task)
- Were agents missing from dispatch that should have been included?
- Did agent dispatches lack necessary context? (Agent had to re-discover what the skill should have provided)
- Were agents re-dispatched with corrected prompts? (Context quality issue)

**Decision point gaps:**
- Were there decisions where the user had to make a call with no guidance from the process?
- Were there decisions where the SDLC gave guidance but it was wrong or outdated?
- Were there decisions that come up every time for this task type? (Playbook candidate)

### Knowledge Gap Signals

**External lookups that should be internal:**
- Context7 queries for information that should be in knowledge stores
- Web searches for patterns the project uses regularly
- User providing information that should be documented ("The Railway config needs X")
- Assistant reading external docs that could be distilled into knowledge YAML

**Agent context deficiencies:**
- Agent produced incorrect output due to missing domain knowledge
- Agent had to be told something that a knowledge file should have provided
- Agent re-discovered a pattern that was already in a parking lot but not promoted
- Agent's work contradicted an existing knowledge rule (rule not loaded or not applicable)

**Discipline parking lot candidates:**
- Insights that emerged during the session that are reusable
- Patterns that were discovered by reading code that should be formalized
- Cross-discipline observations (testing session reveals coding pattern)

### Skill Deficiency Signals

**Phase-level issues:**
- A skill's workflow has a phase that consistently produces incomplete results
- A skill's workflow is missing a phase that the work always requires
- A skill's phase ordering doesn't match the natural order of the work

**Template/output issues:**
- Skill produces an artifact that doesn't match what's actually needed
- Artifact sections are consistently skipped or marked N/A
- Artifact is missing sections that the work always requires

**Trigger issues:**
- Skill triggers on queries it shouldn't handle
- Skill doesn't trigger on queries it should handle
- Multiple skills could trigger — ambiguous boundaries

### Structural Gap Signals

- Task types repeated without playbooks
- Disciplines exercised without parking lots
- Agent roles not in the context map
- Process docs that contradict each other
- CLAUDE-SDLC.md out of sync with actual skill behavior

## Extraction from Commits

When working from commits without a session:

### Commit Pattern Analysis

| Pattern | Signal | Improvement Target |
|---------|--------|--------------------|
| `fix:` after `feat:` on same files | Correction — feature had a gap | Playbook gotcha, or skill phase ordering |
| Config-only commits after implementation | Infrastructure setup missed initially | Skill should include setup phase earlier |
| Same file edited 3+ times in sequence | Iterative correction | Knowledge gap — pattern not codified |
| Revert commits | Approach was wrong | Decision point needs better guidance |
| Migration commits after implementation | Database setup out of order | Playbook ordering, or skill phase ordering |
| Large commits without `d<N>:` prefix | Untracked substantial work | Process awareness gap |
| Commits touching knowledge/discipline files | Process learning happened | Check if the learning was also captured in changelog |

### Diff Analysis

For significant commits, read the full diff:
- **New files created:** Do they represent new patterns that should be in knowledge stores?
- **Config files modified:** Are these configurations documented anywhere? Should they be?
- **Test files added/modified:** Do they reveal testing patterns not in the testing knowledge store?
- **Dependency changes:** Were version bumps or new packages added mid-stream? (Setup gap)

### Cross-referencing with Playbooks

If the commits match an existing playbook's task type:
1. Read the playbook
2. Map the commit sequence to the playbook's phases
3. Identify: were all playbook phases represented in commits? Were there commits for work NOT in the playbook?
4. If gaps exist, propose playbook updates

## Extraction from a Factory Digest

A factory digest (SKILL.md § Improvement with a Factory Digest) is the record of what CD did to an agent factory's output. Each correction CD had to make is a signal that some stage, skill or check let the problem through.

### Reading the Signals

| Signal | What it says | Where the fix usually goes |
|--------|--------------|----------------------------|
| Revision requests (CD's request-changes reviews and inline comments) | What the agents got wrong the first time | The stage's skill or prompt, its review loop's checklist, or knowledge for the code area |
| A revision's answers: declined, or needs CD's call | What the agents refused or couldn't decide | The skill's scope rules, or a decision CD should record once |
| Revision limits hit, escalations, review caps | Where a loop doesn't converge | The loop's bar, the stage's tier, or triage's tier for that kind of issue |
| PRs closed without merging (rejections only, not a replan or a comparison run) | Work CD didn't want; CD's reason, if given, says why | Triage calibration, plan scope rules, the issue template |
| Questions and CD's answers | Gaps in the issue or the skills; a question the thread already answered means a skill re-asks | The skill's gate rules, triage's needs-input bar, the issue template |
| Triage overrides (an advisor label added or removed by CD, a re-triage, a manual tier) | Where triage's judgment is off | The triage rubric |
| Follow-ups CD unchecked at merge | What the agents over-propose | The execute skills' follow-up rules |
| Failed runs and their failing step | Brittle steps and recurring environment problems | The workflow, guard, image or runner setup |
| Run metrics by stage | Cost and turn outliers, stages that struggle | Prompts, model and effort choices, caps |
| CD's reactions on factory comments | A light quality signal | Supporting evidence only |
| Commits in the window to the factory or SDLC | What was already fixed | Nothing: drop proposals a later commit settled |

### Patterns Over Events

- **Recurrence decides weight.** The same correction on two issues outweighs a long comment on one. A one-off is a low-severity proposal at most, unless it caused a failure CD had to clean up.
- **Look for the stage that let it through,** not only the file that was wrong. A missing test the review loop didn't flag is a review-checklist gap as much as a code gap.
- **Separate the factory from the framework.** A problem in a project's own workflows or guards stays with the project. A problem any project running the same skill would hit goes to the framework (route `z-sdlc`).
- **Cost is a fact, not a verdict.** Flag a stage whose cost or turns jump against its own earlier runs, and say what changed. Don't propose cutting cost where the run did what it should.

### What CD Needs from Each Proposal

Each proposal is something CD can act on without reading the digest: what to change, where, why (the evidence, by signal id), and the expected effect. The proposal quality bar below applies. A proposal that only observes is not a proposal. When nothing in a section needs action, leave the section empty: an empty section reads as "nothing to action", and that is a valid result.

## Categorization Framework

Every finding gets categorized for actionability:

### Category: Process Friction

**Improvement types:**
- Skill workflow modification (add/remove/reorder phases)
- Skill trigger refinement (broader or narrower matching)
- New skill proposal (task type has no skill)
- Process doc update (guidance missing or wrong)

**Severity:**
- **High:** Friction that caused errors, wasted significant time, or forced process bypass
- **Medium:** Friction that slowed work noticeably but didn't cause errors
- **Low:** Minor friction, opportunity for smoother workflow

### Category: Knowledge Gap

**Improvement types:**
- Knowledge YAML addition (new file or new rules in existing file)
- Discipline parking lot entry (insight not yet validated)
- Agent context map update (wire knowledge to the right agents)
- Playbook knowledge context update (add files to playbook's context list)

**Severity:**
- **High:** Missing knowledge caused incorrect output or significant rework
- **Medium:** Missing knowledge required manual lookup but work completed correctly
- **Low:** Knowledge exists elsewhere but isn't surfaced at the right time

### Category: Skill Deficiency

**Improvement types:**
- Phase addition/modification/removal
- Agent recommendation update
- Template section update
- Gate condition change

**Severity:**
- **High:** Skill produced wrong output or missed critical steps
- **Medium:** Skill workflow needed manual adjustment to fit the task
- **Low:** Skill worked but could be smoother

### Category: Structural Gap

**Improvement types:**
- New playbook proposal
- New discipline proposal
- Context map addition
- Process doc creation/update

**Severity:**
- **High:** Missing structure caused process failure or significant confusion
- **Medium:** Missing structure required workaround
- **Low:** Missing structure is a nice-to-have for future work

## Proposing Changes

Each proposal must include:

1. **Target:** Specific file and section to modify
2. **Change type:** Add / Modify / Remove
3. **Description:** What to change and why
4. **Evidence:** Where in the session/commits this gap was observed (for a factory digest, the signal ids)
5. **Severity:** High / Medium / Low
6. **Draft change:** For skill/process modifications, include the actual text to add or modify. For knowledge additions, include a YAML skeleton.

### Proposal Quality Bar

- **Specific:** "Add env-var verification phase to sdlc-execute after PRE-GATE" not "improve the execution skill"
- **Evidenced:** "In session X, the Railway SIGNING_SECRET was missing because the skill doesn't check env vars before deploy" not "env vars are important"
- **Proportional:** Don't propose skill rewrites for single-session friction. Don't propose parking lot entries for established patterns.
- **Non-duplicative:** Check existing knowledge stores and parking lots before proposing additions

## Applying Changes

A headless run never applies: it returns the proposals with status `awaiting-approval` (SKILL.md § Applying Improvements).

When the user approves proposals:

1. **Skills:** Edit SKILL.md directly. For phase additions, place in the workflow where the analysis showed it was needed. Update the workflow diagram if present.
2. **Knowledge stores:** Create or update YAML files. Follow existing conventions in the target store. Set `spec_relevant: false` for new files (safe default).
3. **Discipline parking lots:** Add entries with `[NEEDS VALIDATION]` marker, dated, with source reference.
4. **Process docs:** Edit directly. Ensure changelog entry is written in the same step.
5. **Playbooks:** For updates to existing playbooks, edit directly and update `last_validated`. For new playbook proposals, note for `sdlc-playbook-generate` — don't auto-create.
6. **Context map:** Add agent-to-knowledge mappings. Verify the mapped files exist.

**Migration protection:** When applying fixes to framework files (process docs and skills), determine whether the fix is project-specific or a framework correction (see `[sdlc-root]/process/project-section-markers.md` for the full convention):

- **Framework correction** (e.g., fixing a typo in a framework-defined phase, correcting a gate condition) — these should flow back upstream: list them for z-sdlc. Until a release carries it, mark the corrected section as a replacement, or the next migration asks about it and may take upstream's back. An edit in frontmatter can't be marked (`[sdlc-root]/process/project-section-markers.md` § What Markers Can't Hold): it is re-applied after each migration until upstream has it.
- **Project-specific fix to process/skill files** (e.g., adding a project-specific phase to a skill) — wrap in `PROJECT-SECTION` markers, as an addition, a replacement or a removal:

```html
<!-- PROJECT-SECTION-START: audit-improve-YYYY-MM-DD-description -->
... project-specific fix content ...
<!-- PROJECT-SECTION-END: audit-improve-YYYY-MM-DD-description -->

<!-- PROJECT-SECTION-START: audit-improve-YYYY-MM-DD-description replaces `### The upstream heading` -->
### The upstream heading
... the corrected section ...
<!-- PROJECT-SECTION-END: audit-improve-YYYY-MM-DD-description -->

<!-- PROJECT-SECTION-REMOVED: audit-improve-YYYY-MM-DD-description `### The upstream heading` — why; CD, YYYY-MM-DD -->
```

**No markers needed for project data:** discipline parking-lot entries (with a discipline's `## Project Context` and `## Active Questions`) and agent-context-map.yaml — migration keeps them whole. A discipline file's framework sections are framework text: a change to one is marked. A knowledge YAML entry the project added needs none either, but a fix that rewrites or removes an entry the framework shipped is marked as a replacement or removal (`[sdlc-root]/process/project-section-markers.md` § The Three Kinds of Change), or the next migration takes upstream's back.

**Always update `[sdlc-root]/process/sdlc_changelog.md`** for every process change. This is a hard rule — changelog entries are written in the same step as the change, not deferred.
