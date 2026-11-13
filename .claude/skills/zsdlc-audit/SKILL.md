---
name: zsdlc-audit
description: >
  Unified auditing skill for the z-sdlc framework source repo with two modes: compliance and
  improvement. Compliance mode audits manifest completeness, cross-reference consistency, stale
  references, changelog freshness, knowledge store conventions, discipline health, skill/agent
  convention compliance, installer correctness, and cross-skill DRY (verbatim or near-verbatim
  prose duplicated across sibling skills that should be extracted to a shared location).
  Improvement mode analyzes sessions and/or
  commits to identify framework gaps — skill deficiencies, knowledge store gaps, process doc
  issues, and structural problems. Both modes can run against the current session or be fed a
  previous session or commit range. Triggers on "sdlc audit", "audit the framework", "run a
  framework audit", "compliance audit", "audit this session", "audit for improvements",
  "what can we improve about the framework", "framework health check", "check framework health",
  "validate the framework", "check sdlc compliance", "audit these commits",
  "process improvement audit", "triage parking lot", "triage disciplines",
  "validate parking lot entries".
  Do NOT use for generating playbooks from sessions.
  Do NOT use for bulk knowledge import — use zsdlc-ingest.
---

# Framework Audit

Unified auditing for both structural compliance and process improvement of the z-sdlc source repo. Two modes, flexible inputs.

**Argument:** `$ARGUMENTS` (mode + optional source — see Input Resolution below)

## Modes

| Mode | Purpose | Output |
|------|---------|--------|
| **Compliance** | Verify framework structure, manifest completeness, cross-references, conventions | Findings table + inline report |
| **Improve** | Identify framework gaps — skill deficiencies, knowledge store gaps, process doc issues | Improvement proposals targeting skills, process docs, knowledge stores, disciplines |

## Input Resolution

Parse `$ARGUMENTS` to determine mode and source:

| Invocation | Mode | Source |
|-----------|------|--------|
| `/zsdlc-audit` (no args) | Compliance | Current framework state |
| `/zsdlc-audit compliance` | Compliance | Current framework state |
| `/zsdlc-audit compliance --skip-validation` | Compliance | Current state, skip active validation (6e) — fast structural health check only |
| `/zsdlc-audit compliance <session>` | Compliance | Specific session — did it follow framework conventions? |
| `/zsdlc-audit compliance <commit(s)>` | Compliance | Specific commits — do they maintain framework consistency? |
| `/zsdlc-audit improve` | Improve | Current session |
| `/zsdlc-audit improve <session>` | Improve | Past session |
| `/zsdlc-audit improve <commit(s)>` | Improve | Specific commits |
| `/zsdlc-audit improve <session> <commit(s)>` | Improve | Session + commits combined |

**Identifying sessions vs commits in arguments:**
- Session identifiers: UUIDs, quoted names, or search terms (resolved against JSONL files)
- Commit identifiers: 7+ char hex strings, commit ranges (`abc123..def456`), or branch names
- When ambiguous, ask the user

**Session location:** Session JSONL files live in `~/.claude/projects/<project-dir-hash>/`. Locate by scanning for matching content or session ID. See `references/session-reading.md` for JSONL structure.

## Compliance Mode

Verify the framework's health across 10 audit dimensions. Full methodology in `references/compliance-methodology.md`. Pass `--skip-validation` to skip the active evidence-gathering pass in Dimension 6e — useful when parking lots are large and a full validation pass would be slow.

### Workflow

```
DISPATCH AUDITOR → REPORT → TRIAGE → FIX
```

**Dispatch the `sdlc-compliance-auditor` subagent** to perform the 10-dimension scan. Its own brief is the installed-project audit (`.claude/skills/sdlc-audit/references/compliance-methodology.md`, `docs/_index.md`, 9 project dimensions), none of which exists in this repo, so the dispatch prompt names this skill's methodology (`.claude/skills/zsdlc-audit/references/compliance-methodology.md`) and its 10 dimensions as the ones to use, and says `[sdlc-root]` is the repo root. The subagent returns structured findings with a score. This skill then handles the interactive triage and fix phases.

### Audit Dimensions (summary)

1. **Manifest completeness** — Every file on disk in tracked directories is in `skeleton/manifest.json` and vice versa
2. **Cross-reference consistency** — Skills in manifest have CLAUDE-SDLC.md commands; agents in manifest; knowledge files wired in context map
3. **Stale reference scan** — Grep for old/removed skill/agent/concept names across the codebase
4. **Changelog freshness** — Process changes have corresponding entries in `process/sdlc_changelog.md`
5. **Knowledge store conventions** — YAML structure, README completeness, `spec_relevant` fields
6. **Discipline health** — Parking lot entries have triage markers, active validation of `[NEEDS VALIDATION]` entries against codebase evidence, cross-discipline flow
7. **Skill convention compliance** — Frontmatter format (folded scalar descriptions), required sections, anti-triggers
8. **Agent convention compliance** — Proper frontmatter, tools lists, when-to-use descriptions
9. **Installer correctness** — `sdlc-initialize` (which `BOOTSTRAP.md` copies) and `sdlc-migrate` install every manifest file; agent paths go to `.claude/agents/`
10. **Cross-skill DRY** — Substantive prose blocks (paragraphs, framing sentences, principles) duplicated verbatim or near-verbatim across sibling skills. Findings recommend extraction targets (`process/`, `knowledge/`) so both skills can reference one source.

### Compliance with Session/Commit Input

When fed a session or commits (not just current state):
- **Session input:** Read the conversation and verify framework conventions were followed — were consistency checks run? Were changelogs updated? Were manifest entries added for new files?
- **Commit input:** Check whether commits maintain framework consistency. Cross-reference changes against manifest, CLAUDE-SDLC.md, and changelog. Flag process file changes without changelog entries.

### Output

Present findings to user in a structured format (score/10, verdict, findings table). No separate audit artifact file — this is the source repo, not a child project.

### Interactive Triage Phase

After presenting the audit report, if any discipline parking lot entries are promotion candidates (from Dimension 6), run an interactive triage session. See `references/compliance-methodology.md` step 11 for the full workflow.

Candidates come from two sources: entries marked `[VALIDATED]` by the active validation pass (§6e — these have codebase evidence already gathered), and entries with existing `[READY TO PROMOTE]` markers. The triage phase presents candidates grouped by discipline and asks the user to decide on each: promote to knowledge store, defer (with reason), or leave as-is. Promotions are applied immediately — the audit creates or updates the target knowledge store file, removes the full entry from the parking lot, and adds a one-liner to the `### Promoted` section at the bottom of the discipline file (`- **[source]** short title → target path`).

## Improvement Mode

Analyze sessions and/or commits to identify how the z-sdlc framework itself should evolve. Full methodology in `references/improvement-methodology.md`.

### Workflow

```
LOCATE → EXTRACT → CATEGORIZE → PROPOSE → (optional) APPLY → CHANGELOG
```

### What to Look For

**Skill deficiencies** — specific skill behaviors that produced suboptimal results in child projects or this repo:
- Steps in a skill workflow that were skipped or done out of order
- Missing phases that the work required
- Agent recommendations in skills that were wrong for the task
- Template sections that didn't fit the actual output needed
- Trigger phrases that are too broad or too narrow

**Knowledge gaps** — information that was needed but didn't exist in the knowledge layer:
- Patterns discovered during framework development that should be codified
- Gotchas encountered that no knowledge file warned about
- Agent context map missing relevant knowledge file mappings
- Knowledge store YAML files missing important rules or patterns

**Process friction** — moments where the framework's own process slowed work down:
- Consistency checks that miss important validations
- `sdlc-initialize` or `sdlc-migrate` not handling an install edge case
- CLAUDE-SDLC.md guidance that doesn't match actual skill behavior
- Process docs that contradict each other or are outdated

**Structural gaps** — missing infrastructure in the framework:
- Task types that have no playbook but should
- Disciplines being exercised without a parking lot
- Agent roles that aren't mapped in the context map
- Missing skill types for common development workflows

### Improvement with Commit Input

When fed commits (without a session):
- Read commit messages and diffs for process signals
- Look for patterns: commits that fix previous commits (correction signal), multiple small commits to the same file (iteration signal)
- Check whether commits updated the changelog, manifest, and CLAUDE-SDLC.md when they should have
- Cross-reference against existing playbooks — does the commit pattern match a playbook?

### Output

Present categorized improvement proposals:

```
IMPROVEMENT AUDIT REPORT
═══════════════════════════════════════════════════════════════

Source: [session ID / commit range / current session]
Analyzed: [message count] messages, [commit count] commits

SKILL DEFICIENCIES
  [numbered list with target skill and proposed change]

KNOWLEDGE GAPS
  [numbered list with target discipline/store]

PROCESS FRICTION
  [numbered list of friction points with severity]

STRUCTURAL GAPS
  [numbered list with proposed addition]

PROPOSED CHANGES
| # | Target | Change Type | Description | Severity |
|---|--------|-------------|-------------|----------|
| 1 | skills/sdlc-execute/SKILL.md | Modify | Add env-var checklist phase | High |
| 2 | knowledge/architecture/ | Add | New deployment patterns file | Medium |
| 3 | disciplines/deployment.md | Add entry | Service dependency ordering | Low |
```

### Applying Improvements

When the user approves proposals, apply changes directly:
- Skill modifications → edit the SKILL.md in `skills/`
- Knowledge additions → create/update YAML files in `knowledge/`
- Discipline entries → add to parking lot in `disciplines/` with `[NEEDS VALIDATION]`
- Process doc updates → edit the relevant file in `process/`
- Agent modifications → edit the agent file in `agents/`
- New playbook proposals → note them in the report (don't auto-create)

Update `process/sdlc_changelog.md` for every process change applied.

## Red Flags

| Thought | Reality |
|---------|---------|
| "The framework looks fine, no improvements needed" | Check the correction signals and mid-stream discoveries before concluding. If they show nothing, report the session as clean rather than proposing changes. |
| "I'll fix everything without asking" | Present proposals first. The user decides what to change. |
| "This is just a compliance audit with extra steps" | Compliance checks structure. Improvement analyzes behavior. Different inputs, different outputs. |
| "I'll propose sweeping framework changes" | Proportional recommendations. Small friction gets small fixes. |
| "The session didn't follow conventions, that's a compliance failure" | For improvement mode, convention bypass is a signal, not a failure. Ask: why was it bypassed? That's the improvement. |

## Integration

- **Feeds into:** skill modifications, knowledge store updates, discipline parking lots, process doc changes, manifest updates, CLAUDE-SDLC.md updates
- **Uses:** `sdlc-compliance-auditor` subagent (compliance mode 10-dimension scan), session JSONL, git history, all framework source files
- **Complements:** `sdlc-playbook-generate` (playbooks capture "how to repeat"; this captures "how to improve")
- **Does NOT replace:** `zsdlc-ingest` (bulk knowledge import — audit triages existing entries, does not ingest new ones)

## Additional Resources

### Reference Files

- **`references/compliance-methodology.md`** — Full 10-dimension framework compliance audit methodology, report format, severity levels, guiding principles
- **`references/improvement-methodology.md`** — Detailed patterns for extracting framework improvements from sessions and commits
- **`references/session-reading.md`** — JSONL message type reference and extraction patterns for reading Claude Code session files
