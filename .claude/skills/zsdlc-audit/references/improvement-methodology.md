# Framework Improvement Audit Methodology

Detailed patterns for extracting z-sdlc framework improvements from sessions and commits. The goal is to identify how the framework itself should evolve — not whether conventions were followed (that's compliance), but whether the framework is good enough.

## The Self-Improvement Loop

```
Framework development session → Improvement audit → Framework changes → Better framework
```

Every session working on this repo is data. Friction, corrections, missing knowledge, and convention bypasses are signals that the framework has gaps. The improvement audit reads those signals and proposes targeted changes.

## Extraction from Sessions

### Skill Deficiency Signals

Scan the conversation for moments where framework skills either helped or hindered:

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

**Agent dispatch issues:**
- Were agents dispatched that weren't useful? (Wrong agent for the task)
- Were agents missing from dispatch that should have been included?
- Did agent dispatches lack necessary context? (Agent had to re-discover what the skill should have provided)
- Were agents re-dispatched with corrected prompts? (Context quality issue)

### Knowledge Gap Signals

**Missing knowledge in stores:**
- Patterns discovered during framework development that aren't codified in any knowledge YAML
- Gotchas encountered that no knowledge file warned about
- Agent context map missing relevant knowledge file mappings
- External docs consulted that should be distilled into knowledge YAML

**Agent context deficiencies:**
- Agent produced incorrect output due to missing domain knowledge
- Agent had to be told something that a knowledge file should have provided
- Agent re-discovered a pattern that was already in a parking lot but not promoted
- Agent's work contradicted an existing knowledge rule (rule not loaded or not applicable)

**Discipline parking lot candidates:**
- Insights that emerged during the session that are reusable
- Patterns that were discovered by reading code that should be formalized
- Cross-discipline observations (testing session reveals coding pattern)

### Process Friction Signals

**Convention enforcement gaps:**
- Consistency checks that miss important validations
- `sdlc-initialize` or `sdlc-migrate` not handling an install edge case
- CLAUDE-SDLC.md guidance that doesn't match actual skill behavior
- Manifest not updated when files are added/removed

**Workflow mismatch:**
- Did the skill's phase structure match the actual work? (Steps skipped, steps added, steps reordered)
- Were there phases in the work that no skill covers?
- Did the user have to interrupt the skill workflow to handle something unexpected?

**Decision point gaps:**
- Were there decisions where the user had to make a call with no guidance from the process?
- Were there decisions where the framework gave guidance but it was wrong or outdated?
- Were there decisions that come up every time for this task type? (Playbook candidate)

### Structural Gap Signals

- Task types repeated without playbooks
- Disciplines being exercised without parking lots
- Agent roles not in the context map
- Process docs that contradict each other
- CLAUDE-SDLC.md out of sync with actual skill behavior
- Skills or agents that exist on disk but aren't in the manifest
- Knowledge directories without README files

## Extraction from Commits

When working from commits without a session:

### Commit Pattern Analysis

| Pattern | Signal | Improvement Target |
|---------|--------|--------------------|
| Fix commit after feature commit on same files | Correction — something was missed | Skill phase ordering or knowledge gap |
| Manifest update long after file addition | Consistency check gap | Strengthen consistency checks or skill instructions |
| Changelog update in separate commit from change | Process compliance gap | Reinforce "same step" changelog rule |
| Same file edited 3+ times in sequence | Iterative correction | Knowledge gap — pattern not codified |
| Revert commits | Approach was wrong | Decision point needs better guidance |
| Large batches of file additions without manifest | Convention awareness gap | Skill instructions should reference manifest |
| Commits touching multiple skill/agent files | Cross-cutting change | Check if CLAUDE-SDLC.md and manifest were also updated |

### Diff Analysis

For significant commits, read the full diff:
- **New skill files created:** Do they follow frontmatter conventions? Are they in manifest?
- **New knowledge YAML files:** Do they follow store conventions? Are they wired in context map?
- **Agent modifications:** Were corresponding skills updated if agent behavior changed?
- **Process doc changes:** Is there a changelog entry?
- **Installer changes:** Do `sdlc-initialize` and `sdlc-migrate` still handle all manifest files?

### Cross-referencing with Playbooks

If the commits match an existing playbook's task type:
1. Read the playbook
2. Map the commit sequence to the playbook's phases
3. Identify: were all playbook phases represented in commits? Were there commits for work NOT in the playbook?
4. If gaps exist, propose playbook updates

## Categorization Framework

Every finding gets categorized for actionability:

### Category: Skill Deficiency

**Improvement types:**
- Skill workflow modification (add/remove/reorder phases)
- Skill trigger refinement (broader or narrower matching)
- New skill proposal (task type has no skill)
- Skill frontmatter update (better description, anti-triggers)

**Severity:**
- **High:** Skill produced wrong output or missed critical steps
- **Medium:** Skill workflow needed manual adjustment to fit the task
- **Low:** Skill worked but could be smoother

### Category: Knowledge Gap

**Improvement types:**
- Knowledge YAML addition (new file or new rules in existing file)
- Discipline parking lot entry (insight not yet validated)
- Agent context map update (wire knowledge to the right agents)
- Knowledge store README update

**Severity:**
- **High:** Missing knowledge caused incorrect output or significant rework
- **Medium:** Missing knowledge required manual lookup but work completed correctly
- **Low:** Knowledge exists elsewhere but isn't surfaced at the right time

### Category: Process Friction

**Improvement types:**
- Process doc update (guidance missing or wrong)
- Consistency check addition (validation that should happen automatically)
- CLAUDE-SDLC.md update (command documentation drift)
- Installer fix in `sdlc-initialize` or `sdlc-migrate` (installation gap)

**Severity:**
- **High:** Friction that caused errors, wasted significant time, or forced convention bypass
- **Medium:** Friction that slowed work noticeably but didn't cause errors
- **Low:** Minor friction, opportunity for smoother workflow

### Category: Structural Gap

**Improvement types:**
- New playbook proposal
- New discipline proposal
- Context map addition
- Manifest update
- New agent proposal

**Severity:**
- **High:** Missing structure caused framework inconsistency or significant confusion
- **Medium:** Missing structure required workaround
- **Low:** Missing structure is a nice-to-have for future work

## Proposing Changes

Each proposal must include:

1. **Target:** Specific file and section to modify
2. **Change type:** Add / Modify / Remove
3. **Description:** What to change and why
4. **Evidence:** Where in the session/commits this gap was observed
5. **Severity:** High / Medium / Low
6. **Draft change:** For skill/process modifications, include the actual text to add or modify. For knowledge additions, include a YAML skeleton.

### Proposal Quality Bar

- **Specific:** "Add manifest update reminder to zsdlc-create-skill after file creation step" not "improve the skill creation process"
- **Evidenced:** "In session X, a new skill was created but not added to manifest, so child projects never received it" not "manifest should be kept in sync"
- **Proportional:** Don't propose skill rewrites for single-session friction. Don't propose parking lot entries for established patterns.
- **Non-duplicative:** Check existing knowledge stores and parking lots before proposing additions

## Applying Changes

When the user approves proposals:

1. **Skills:** Edit SKILL.md in `skills/` directly. For phase additions, place in the workflow where the analysis showed it was needed. Update the workflow diagram if present.
2. **Knowledge stores:** Create or update YAML files in `knowledge/`. Follow existing conventions in the target store. Set `spec_relevant: false` for new files (safe default).
3. **Discipline parking lots:** Add entries to files in `disciplines/` with `[NEEDS VALIDATION]` marker, dated, with source reference.
4. **Process docs:** Edit files in `process/` directly. Ensure changelog entry is written in the same step.
5. **Playbooks:** For updates to existing playbooks in `playbooks/`, edit directly and update `last_validated`. For new playbook proposals, note for `sdlc-playbook-generate` — don't auto-create.
6. **Context map:** Update `knowledge/agent-context-map.yaml`. Verify the mapped files exist.
7. **Agents:** Edit files in `agents/` directly. Update manifest if adding new agents.
8. **CLAUDE-SDLC.md:** Update command documentation if skills were added or renamed.
9. **Manifest:** Update `skeleton/manifest.json` if files were added or removed.

**Always update `process/sdlc_changelog.md`** for every process change. This is a hard rule — changelog entries are written in the same step as the change, not deferred.
