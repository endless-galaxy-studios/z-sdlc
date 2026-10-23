# Compliance Audit Methodology

Full methodology for SDLC compliance auditing. Covers all 9 audit dimensions, report format, severity levels, and guiding principles. Migrated from the `sdlc-compliance-auditor` agent.

## Audit Methodology Sequence

1. **Catalog Scan**: Read `docs/_index.md` — build complete inventory of claimed deliverables and statuses
2. **Artifact Verification**: For each deliverable, verify expected files exist and naming follows conventions
3. **Orphan Detection**: List files in `docs/current_work/` and `docs/chronicle/` not accounted for in catalog
4. **Git Cross-Reference**: Check recent commits for untracked substantial work
5. **Freshness Check**: Assess CLAUDE.md files and memory files for accuracy
6. **Knowledge Layer Scan**: Audit disciplines, knowledge stores, triage status, wiring, context map, playbooks, usage, staleness by age, cross-file contradictions, coverage gaps, review pattern recurrence
7. **Migration Integrity**: Verify manifest version, file completeness, content-merge, stale references
8. **Agent Memory Mining**: Scan agent memories for recurring patterns worth promoting
9. **Recommendation Follow-Through**: Check whether previous audit recommendations were acted on
10. **Report Generation**: Produce structured audit report at `docs/current_work/audits/sdlc_audit_YYYY-MM-DD.md`
11. **Interactive Triage**: Present promotion candidates to CD for triage decisions and apply approved promotions

Deep Verify (§6m) is NOT part of this sequence — it is an opt-in, orchestrator-run mode that only executes when explicitly invoked by name. Its findings, when it runs, join step 11.

## Dimension 1: Deliverable Catalog Integrity

- Read `docs/_index.md` for the full deliverable catalog
- Verify every listed deliverable has corresponding artifacts at expected locations
- Check for orphaned artifacts (files in `docs/current_work/` or `docs/chronicle/` not referenced in catalog)
- Validate deliverable ID sequencing (no gaps, no duplicates, sub-deliverables properly suffixed)
- Confirm status labels match actual artifact state (e.g., "complete" should have `_COMPLETE.md`)
- **Dependencies** (the `Depends on` column; `[sdlc-root]/process/deliverable_lifecycle.md` § Dependencies). Flag:
  - a dependency on an ID that isn't in the catalog;
  - a cycle;
  - a Draft prerequisite of a Ready or In Progress deliverable (the D11a pattern: the prerequisite dropped out of sight);
  - a plan whose Phase Dependencies table names a deliverable missing from its catalog row's `Depends on`.

  A catalog without the column predates it: one minor finding to add it (`sdlc-migrate` back-fills `—`), not one per row.

## Dimension 2: Artifact Traceability

For each active deliverable, verify the expected artifact chain:
- Spec at `docs/current_work/specs/dNN_name_spec.md`
- Plan at `docs/current_work/planning/dNN_name_plan.md`
- Result at `docs/current_work/results/dNN_name_result.md`
- Completed deliverables archived to `docs/chronicle/` with `_COMPLETE.md` suffix
- Flag deliverables with missing intermediate artifacts (e.g., has result but no spec)
- A split parent has a split record (`docs/current_work/planning/dNN_name_split.md`) instead of a plan, and its parts carry their own chains. A parent with parts in the catalog but no split record is a finding.

## Dimension 3: Untracked Work Detection

- Scan recent git history for commits touching multiple files without deliverable ID prefixes (`d<N>:`)
- Identify patterns suggesting substantial work done ad hoc when it should have been tracked
- Look for new components, modules, stores, routes, or types introduced without corresponding deliverables
- Cross-reference commit messages against the deliverable catalog

## Dimension 4: Knowledge Freshness

- Check `CLAUDE.md` files (root and per-package) for staleness indicators
- Verify agent memory files in `.claude/agent-memory/` reflect current codebase state
- Flag documented patterns or files that no longer exist
- Check that recent architectural decisions are captured somewhere persistent
- Verify `docs/_index.md` reflects current state of all deliverables

## Dimension 5: Process Health Indicators

- Ratio of tracked vs untracked multi-file changes
- Average artifact completeness per deliverable
- Chronicle freshness (how long completed work sits in `current_work/` before archiving)
- Spec approval coverage (deliverables that went through proper CD approval)
- **Changelog freshness** — compare `[sdlc-root]/process/sdlc_changelog.md` against recent commits modifying SDLC process files. Flag process changes without changelog entries.

## Dimension 6: Knowledge Layer Health

### 6a. Discipline Parking Lots (`[sdlc-root]/disciplines/`)

Check each discipline:

| File | Discipline |
|------|-----------|
| `architecture.md` | System design, component boundaries, integration patterns |
| `business-analysis.md` | Requirements, domain modeling, stakeholder needs |
| `coding.md` | Implementation patterns, conventions, tech debt |
| `data-modeling.md` | Data architecture, schema design |
| `deployment.md` | CI/CD, infrastructure, release management |
| `design.md` | UI/UX, visual design, interaction patterns |
| `process-improvement.md` | Meta-discipline: improving the SDLC itself |
| `product-research.md` | Market, users, competitive landscape |
| `testing.md` | Test strategy, automation, knowledge layers |

**What to check:**
- Are parking lots being written to between audits? (git blame / last-modified)
- Do insights reference recent deliverables?
- Are entries added by execution/planning skills? (If only during audits, capture integration is broken)
- Are cross-discipline insights flowing?
- Do entries have triage markers (`[READY TO PROMOTE]`, `[NEEDS VALIDATION]`, `[DEFERRED]`)?

**Maturity level verification:**
- Read Process Maturity Tracker in `process-improvement.md`
- Level 1 claim: discipline parking lot entries exist
- Level 2 claim: knowledge stores populated with YAML files + agent-context-map wired + at least one triage pass
- Flag claims lacking supporting evidence

### 6b. Knowledge Stores (`[sdlc-root]/knowledge/`)

| Directory | Purpose |
|-----------|---------|
| `architecture/` | System design, debugging, security, payments, ML, deployment |
| `business-analysis/` | Requirements feedback loops |
| `coding/` | Code quality, TypeScript patterns, testability |
| `data-modeling/` | UDM patterns, anti-patterns, assessment |
| `design/` | UX modeling, ASCII conventions, accessibility |
| `product-research/` | Competitive analysis, methodology, risk |
| `testing/` | Paradigm, gotchas, tool patterns, timing |

**Check:** staleness, relevance to current stack, consumption by skills/agents, growth since seeding, cross-project vs project-specific content.

### 6c. Discipline Triage Status

**Triage authority matrix:**

| Transition | Authority | When |
|-----------|-----------|------|
| unmarked → `[NEEDS VALIDATION]` | Auto-apply (step 6) | Unmarked for ≥2 audit cycles |
| `[NEEDS VALIDATION]` → `[DEFERRED]` | Auto-apply (step 6) | Unvalidated ≥3 cycles AND no agent feedback references it AND discipline dormant |
| Any → `[READY TO PROMOTE]` | CD decision (step 11) | Proposed with evidence during interactive triage |
| `[READY TO PROMOTE]` → Promoted | CD decision (step 11) | Actual knowledge file creation during interactive triage |
| Promoted / `[READY TO PROMOTE]` → `[NEEDS VALIDATION]` (demotion) | CD decision (step 11) | Proposed with multi-judge DEMOTE verdicts from Deep Verify (§6m); batch-level approval per discipline is acceptable — factual-error dissents and splits listed individually |

**Step 6 auto-triage:** Scan entries, apply qualifying low-risk transitions, log actions in report. Collect promotion candidates for step 11.

**Step 11 interactive triage:** Present all promotion candidates (from §6c and Dimension 8) to CD for decision. See step 11 below for the full workflow.

**Evidence production:** For candidate batches of 3+ entries, or any candidate lacking direct deliverable evidence, the evidence column of this matrix is produced by the Promotion Verification Gate — two independent non-orchestrator judges reviewing a neutral payload at the screening tier, splits resolved by a frontier-tier tie-break judge, a final frontier-tier once-over of the promote-bound slate, and factual-error dissents flagged to CD. See `[sdlc-root]/process/discipline_capture.md` § Promotion Verification Gate. A single well-evidenced candidate may skip the screening panel and present its evidence directly, but still goes through the gate's frontier once-over before reaching CD; the orchestrator's own judgment alone is never sufficient evidence.

### 6d. Knowledge-to-Skill Wiring

Two ownership tiers:
1. **Agent-owned (domain):** Agent definitions include Knowledge Context section instructing them to consult `[sdlc-root]/knowledge/agent-context-map.yaml`
2. **Skill-owned (cross-domain):** Skills inject knowledge from other agents' mappings when dispatching into cross-domain contexts

**Check:** agent definitions have self-lookup sections, skills don't redundantly inject same-agent knowledge, cross-domain injection exists where needed.

### 6e. Agent Context Map Integrity

Consult `[sdlc-root]/knowledge/agent-context-map.yaml`:
- All mapped file paths resolve to actual files
- Knowledge YAML files not referenced by any agent (gaps)
- Agents in skill tables without knowledge mapping
- Skills that should consult the map actually do

### 6f. Playbook Freshness

Check `[sdlc-root]/playbooks/`:
- Each playbook has `last_validated` and `validation_triggers`
- Validation triggers fired since `last_validated`?
- All referenced file paths resolve
- README index consistent with actual files

### 6g. Discipline Usage Audit

Five usage signals per discipline:

| Signal | Active | Warning | Dead |
|--------|--------|---------|------|
| Parking lot activity | Entries added between audits from skills | Only during audits | No entries since last audit |
| Knowledge consumption | Mapped agents dispatched recently | Mapped but agents unused | No mapping |
| Promotion flow | Entries triaged and promoted | Added but not triaged | Static |
| Cross-discipline feed | Receives insights from other domains | Isolated | N/A |
| Agent feedback | Agents reporting on knowledge quality | Silent (gradual adoption ok) | N/A |

Report as table with interpretation (healthy / formalized-but-dead / alive-but-unformalized / dead).

### 6h. Knowledge Staleness by Age

Read `[sdlc-root]/knowledge/provenance_log.md` for each knowledge file's last ingestion or refresh date.

**Thresholds** (projects can override via `[sdlc-root]/knowledge/provenance_log.md` header):
- **>180 days** since last ingestion/refresh in an **active discipline** (discipline usage = healthy or alive-but-unformalized): **Warning**
- **>90 days** since last ingestion/refresh (early warning): **Info**
- **No provenance entry** for a knowledge file (pre-dates the log): **Info** — note as "no provenance record, age unknown"

**How to check:**
1. List all knowledge YAML files across `[sdlc-root]/knowledge/`
2. For each, read `[sdlc-root]/knowledge/provenance_log.md` and find entries with matching `files-created` or `files-updated` paths
3. Use the most recent matching entry's date as "last refreshed"
4. If no entry exists, check git blame for the file's last substantive modification date as a fallback
5. Compare against thresholds; only flag active disciplines at Warning level

### 6i. Cross-File Contradiction Detection

Heuristic scan for conflicting guidance across knowledge files within the same discipline and across disciplines.

**Contradiction patterns to detect:**
- **Direct negation** — one file says "always X" while another says "never X" or "avoid X"
- **Conflicting defaults** — two files recommend different default values for the same setting or threshold
- **Overlapping scope with divergent advice** — two files cover the same topic area but give incompatible guidance (e.g., testing knowledge says "mock external services" while coding knowledge says "never mock — use real integrations")

**Contradiction-prone areas** (check these first):
- Testing vs coding on mocking strategy and test isolation
- Architecture vs deployment on service boundaries and coupling
- Design vs coding on component structure and abstraction levels
- Security rules vs convenience patterns (strict validation vs developer ergonomics)

**All findings are "potential"** — the audit flags them for human confirmation. Severity: **Warning** for all detected contradictions.

**Output format per finding:**
```
POTENTIAL CONTRADICTION
  File A: [path] — "[quoted guidance]"
  File B: [path] — "[quoted guidance]"
  Conflict: [brief description of why these may conflict]
```

### 6j. Coverage Gap Detection

Identify areas where the knowledge layer has structural gaps.

**What to check:**

1. **Disciplines with promotable entries but no knowledge store** — discipline parking lot has `[READY TO PROMOTE]` entries but no corresponding `[sdlc-root]/knowledge/<discipline>/` directory. Severity: **Warning** (actionable — promotion is blocked).

2. **Knowledge files not referenced by any agent** — extends 6e (agent context map integrity). Any YAML file in `[sdlc-root]/knowledge/` not listed in any agent's mapping in `[sdlc-root]/knowledge/agent-context-map.yaml`. Severity: **Warning** (the knowledge exists but no agent consumes it).

3. **Agents with empty knowledge mappings** — agents listed in `[sdlc-root]/knowledge/agent-context-map.yaml` with an empty file list, or agents in `.claude/agents/` not present in the context map at all. Severity: **Info** (possibly intentional for simple utility agents).

4. **Discipline-to-knowledge store alignment** — disciplines at Level 2+ in the Process Maturity Tracker should have corresponding knowledge stores. Flag Level 2+ disciplines without stores. Severity: **Warning**.

### 6k. Orphaned Knowledge Pruning

Identify knowledge files that exist but are not wired to any agent, then assess whether they should be pruned, wired, or kept.

**Step 6k.1 — Identify orphans:**

List all YAML files under `[sdlc-root]/knowledge/` domain directories. For each file, consult `[sdlc-root]/knowledge/agent-context-map.yaml` to check if it appears in any agent's mapping. Files with no agent references are orphan candidates.

Exclude from orphan detection:
- `[sdlc-root]/knowledge/agent-context-map.yaml` itself
- `README.md` files
- `provenance_log.md`

**Step 6k.2 — Assess orphan severity:**

For each orphan, gather signals:

| Signal | Indicates | Severity |
|--------|-----------|----------|
| No provenance entry + no git activity in 90 days | Likely stale, safe to prune | High |
| Has provenance entry but no agent wiring | Created but forgot to wire | Medium |
| Recently modified (< 30 days) but unwired | Active work, wiring oversight | Medium |
| Part of a discipline with no agents yet | Discipline maturity gap, not a prune candidate | Info |

**Step 6k.3 — Build prune candidate list:**

For each orphan, record:
- File path
- Last modified date (git blame)
- Provenance status (has entry / no entry)
- Discipline
- Severity rating from 6k.2
- Candidate agents (agents that already consume from the same discipline)

**Output during report (not triage):**

```
ORPHANED KNOWLEDGE FILES
  High priority (no provenance, inactive):
    - knowledge/architecture/legacy-patterns.yaml (last modified: 2025-10-15)
    
  Medium priority (unwired but active):
    - knowledge/design/interaction-animation.yaml (ingested 2026-04-15, never wired)
    
  Info (discipline gap):
    - knowledge/legal/compliance-rules.yaml (no agents map to legal/ yet)
```

Prune candidates are surfaced in step 11 (triage) alongside promotion candidates. See "Prune Triage" section below.

### 6l. Review Pattern Recurrence Detection

Scan `docs/reviews/recurring-patterns.yaml` for pattern clusters that have crossed the recurrence threshold, indicating they should be promoted to knowledge-store entries.

**If the file does not exist:** skip this sub-dimension with a note: "No review pattern log found — Step 6 of sdlc-review-code has not been exercised yet or the project predates this feature."

**Step 6l.1 — Read and validate the log:**

Read `docs/reviews/recurring-patterns.yaml`. Validate basic structure: top-level `patterns` key is a list, each entry has `slug`, `description`, `lens`, `first_seen`, `occurrences` (list), and `promoted` (boolean). Optional fields set by prior triage decisions: `knowledge_entry` (path, with `promoted: true`), `mechanized_guard` (guard record per `[sdlc-root]/process/guardrail-lifecycle.md` — validated in Dimension 6n), and `mechanization_assessed: excluded` + `mechanization_reason` (deliberately not mechanized — CD decision).

**Step 6l.2 — Scan for threshold breaches:**

For each cluster where `promoted: false`:

1. Count occurrences within the sliding window (default: 30 days from audit date).
2. If count >= 3: flag as a **promotion candidate**.
3. If count >= 2: flag as **watch** (approaching threshold — Info severity).

For each promotion candidate (and for already-promoted clusters that keep accumulating occurrences), additionally assess **guard promotion**: is the pattern mechanizable — detectable by a textual, structural, or behavioral signature per `[sdlc-root]/process/guardrail-lifecycle.md` § "What Qualifies for Guard Promotion"? If yes and the cluster has no `mechanized_guard`, flag it as a **guard-promotion candidate** and name the signature, the proposed guard type, and its fix level per `[sdlc-root]/process/guardrail-lifecycle.md` § "Choosing the Fix for a Repeated Mistake", with why a higher level doesn't apply. A cluster recurring *after* knowledge promotion is the strongest guard-promotion signal.

**Skip clusters marked `mechanization_assessed: excluded`** from guard-candidate output — CD already assessed them and chose not to mechanize (`[sdlc-root]/process/guardrail-lifecycle.md` § "Assessed and Excluded"). List them info-tier with occurrence counts and recorded reasons instead; CD may clear the exclusion at triage if the pattern's signature has changed, but the audit never re-proposes on its own. Exclusion does not affect knowledge-promotion candidacy.

**Step 6l.3 — Cross-reference against existing knowledge:**

For each promotion candidate, check whether a knowledge-store entry already covers the pattern:
- Search `[sdlc-root]/knowledge/` YAML files for the cluster's slug, description keywords, or lens area.
- If a matching entry exists, the cluster should be marked `promoted: true` rather than creating a duplicate. Flag as "already covered — mark as promoted."

**Step 6l.4 — Cross-reference against discipline parking lots:**

Check whether any discipline parking-lot entry (`[sdlc-root]/disciplines/*.md`) already captures the same pattern. If so, note the existing entry — promotion may mean graduating the parking-lot entry rather than creating new knowledge.

**Output format:**

```
REVIEW PATTERN RECURRENCE
  Promotion candidates (3+ occurrences in 30-day window):
    - missing-tenant-filter (4 occurrences, first: 2026-03-15, lens: security)
      Files affected: [list of unique files across occurrences]
      Suggested knowledge area: [sdlc-root]/knowledge/architecture/ or coding/

  Guard-promotion candidates (mechanizable, no guard recorded):
    - missing-tenant-filter — preventable (a query type that can't be built without its tenant)
      Proposed guard type: type-constraint (fix level 2; a lint on the query builder is the fallback if the type change is too wide)
    - manually-synced-parallel-copies-drift — textual signature (KEEP IN SYNC comments) + behavioral (drift test)
      Proposed guard type: ci-check floor now, drift-test as full coverage

  Watch list (2 occurrences, approaching threshold):
    - lazy-relationship-outside-async (2 occurrences, first: 2026-04-15, lens: correctness)

  Already promoted: {N} clusters marked promoted: true
  Guarded: {N} clusters with mechanized_guard (freshness in Dimension 6n)
  Excluded from mechanization (info — CD-assessed, not re-proposed): {N} clusters
    - domain-constants-in-shared-code (4 occurrences; reason: heterogeneous manifestations, would need a semantic allowlist that doesn't exist)
  Total clusters: {N}
```

Promotion candidates from 6l are surfaced in step 11 (interactive triage) alongside promotion candidates from 6c and prune candidates from 6k. The triage workflow is the same: CD decides per candidate — promote to knowledge store, promote to a mechanized guard, both, defer, or dismiss. On knowledge promotion, the cluster's `promoted` field is set to `true` and a `knowledge_entry` field is added with the path to the new knowledge file. On guard promotion, a `mechanized_guard` field is added per `[sdlc-root]/process/guardrail-lifecycle.md` — the project implements the guard (the framework never ships project-specific rules), and the field records where it lives so 6n can watch it. When CD declines a guard candidate with "don't re-propose" (as opposed to defer), record `mechanization_assessed: excluded` + `mechanization_reason` on the cluster so future scans skip it.

### 6m. Deep Verify — Retroactive Content Verification (opt-in, never default)

**Not part of the default dimension sweep.** This dimension runs ONLY when the user requests it by name (`/sdlc-audit deep-verify`, "deep audit", "verify the knowledge store", "full content sweep") — never as part of steps 1–10 of a routine audit, and never by the `sdlc-compliance-auditor` subagent (it is orchestrator-run: it needs `AskUserQuestion` gates, judge dispatches, and egress disclosure). The auditor subagent skips this dimension entirely.

Re-judges already-promoted knowledge-store content using the Promotion Verification Gate mechanics (`[sdlc-root]/process/discipline_capture.md` § Promotion Verification Gate) with `KEEP|DEMOTE` verdicts: pre-flight cost/egress confirmation and scope selection, claims-vs-reference content scoping, batched neutral payloads, screening-tier judges with the mandatory fact-checking lens, frontier tie-breaks and once-over. Full specification: `references/deep-verify.md`.

DEMOTE verdicts feed step 11 as a third candidate source — see step 11a. Deep Verify never applies a demotion itself.

### 6n. Mechanized Guard Freshness

For each cluster in `docs/reviews/recurring-patterns.yaml` with a `mechanized_guard` field, verify the guard is alive and effective. Full check definitions in `[sdlc-root]/process/guardrail-lifecycle.md` § "Guard Freshness"; summary:

1. **Guard exists and enforces** — resolve `mechanized_guard.location`: the lint rule is present in the named config, the test file exists, the CI job/step is defined. Then verify **effective enforcement**, not just presence of the rule-name string: parse the rule's effective severity (`off` → CRITICAL, same as missing; `warn`/advisory → WARNING unless `notes` documents advisory as intended); evaluate conditional registration wrappers (e.g., `plugin.rules["x"] ? {...} : {}`) for runtime collapse rather than text-grepping; a skipped test or a disabled/continue-on-error CI step counts as not enforcing. When static reading is inconclusive, run the guard against a known-bad sample (shares mechanics with check 4). Missing → CRITICAL (guard recorded but not wired — the pattern log claims protection that isn't there).
2. **Recurred despite guard** — any occurrence dated after `mechanized_guard.created`, beyond any allowed count recorded in `notes`, → WARNING (guard ineffective: blind spot, wrong scope, or suppressed). Propose modify at triage.
3. **Suppression growth** — count in-code suppressions naming the guard (disable comments, skipped tests); compare against the count recorded at the last audit (note current counts in the audit artifact for next time). Growing → WARNING (the guard is being routed around).
4. **Never fired** (best-effort, only where history is observable; not for `type-constraint` or `other` guards, which work by never firing — try the edit their `notes` says must fail instead) — zero hits since creation → INFO: either the pattern is extinct (retirement candidate) or the guard is miswired (verify against a known-bad sample).

**If no cluster has a `mechanized_guard` field:** report in one line ("No mechanized guards recorded — 6n has nothing to check") and move on. This is normal for projects that haven't promoted a guard yet, not a finding.

Guard findings route into the standard severity-classified findings table. Modify/retire decisions go through step 11 triage; retirement removes the `mechanized_guard` field, notes it in the cluster description, and keeps the occurrence history.

## Dimension 7: Migration Integrity

- **7a. Manifest version:** Read `.sdlc-manifest.json`, compare `source_version` against current z-sdlc. If >10 commits or >30 days behind, recommend migration.
- **7b. File completeness:** Fetch `skeleton/manifest.json` from z-sdlc source (use the repo URL from `.sdlc-manifest.json`), compare installed files against its `source_files` lists.
- **7c. Content-merge:** Verify framework sections current while project customizations preserved (skill gates, discipline entries, agent context map names).
- **7d. Removed features:** Search skills/agents for references to deprecated/removed framework features.

## Dimension 8: Agent Memory Pattern Mining & Hygiene

This dimension has two jobs: mine memories for content worth **promoting** to shared stores, and flag memories that need **hygiene fixes**. Keep the two streams separate — promotion candidates route to the interactive triage (step 11), hygiene findings route to the standard severity-classified findings table (they are fixes, not promotions).

### 8a. Pattern mining (promotion signal)

- Read each agent's `MEMORY.md` in `.claude/agent-memory/*/`
- Identify recurring themes across multiple agents or cycles
- Flag patterns that should be in `[sdlc-root]/knowledge/` or `[sdlc-root]/disciplines/` but aren't

Promotion criteria: appears in 2+ agent memories independently, reusable pattern, saves future agents from rediscovery.

### 8b. Hygiene (fix signal)

Check each `MEMORY.md` — **not** its linked topic files, which are uncapped by design — against the following. Report each as a finding in the standard table with file path and line evidence; the read-only auditor never edits, so the sdlc-audit orchestrator (which has Write) applies approved fixes in skill Step 4.

- **Size cap — Major, not cosmetic.** Claude Code loads only the first **200 lines or 25KB, whichever comes first** of `MEMORY.md` into the agent's system prompt; the remainder is silently truncated, so the agent's newest notes are invisible to it. Flag any `MEMORY.md` over 200 lines or 25KB. Fix: split the largest topics into `{topic}.md` files beside MEMORY.md and replace them with one-line pointers (see the agent template's memory protocol).
- **Contradicts current code.** A memory asserting something the codebase no longer does (e.g. "no version field / no locking" after a later change added them). Verify against source before flagging — this is a correctness risk, not just staleness.
- **Internal contradiction / duplication.** The same fact or tuned value stated more than once within one `MEMORY.md`, sometimes with drifted numbers. Fix: keep the value matching current code, delete the rest.
- **Orphaned directory — Major.** An `.claude/agent-memory/{name}/` whose `{name}` no longer matches any agent in `.claude/agents/` (e.g. a predecessor role retired in a rules-version migration). Recommend deletion.

Note: `sdlc-reflect` Step 5 applies these same hygiene checks session-scoped (agents dispatched that session, memories invalidated by that session's changes), and opportunistically routes memory entries with generalizable insight to discipline parking lots as `[NEEDS VALIDATION]` — a lower bar than 8a's 2+-agent recurrence, feeding the same triage cycle. This dimension remains the project-wide sweep — projects that reflect regularly accumulate less between audits, but don't skip the sweep on that assumption.

## Dimension 9: Recommendation Follow-Through

- Read previous audit artifacts in `docs/current_work/audits/`
- For each past recommendation: implemented, deferred with rationale, or ignored?
- Calculate follow-through rate: (acted-on + explicitly-deferred) / total
- Flag ignored recommendations without explanation

## Compliance with Session Input

When auditing a specific session for compliance:

1. Read the session JSONL (see `references/session-reading.md`)
2. Check whether SDLC skills were invoked when they should have been
3. Verify deliverable IDs were assigned for substantial work
4. Check whether specs were written before execution
5. Verify agent dispatch patterns match process requirements
6. Flag process bypasses with context (why was it bypassed?)

## Compliance with Commit Input

When auditing specific commits:

1. Read commit messages and diffs
2. Cross-reference against `docs/_index.md` — do commits map to tracked deliverables?
3. Flag multi-file changes without deliverable tracking
4. Check whether new components/modules/routes have corresponding specs
5. Verify commit message conventions — must follow `{type}[{deliverable_id}]({scope}): {description}` format with valid type (`feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`, `perf`, `ci`, `sdlc`) and a deliverable ID that maps to `docs/_index.md`

## Step 11: Interactive Triage

After presenting the audit report, run an interactive triage session for all promotion candidates identified during the audit. This surfaces candidates from three sources:

- **§6c parking lot entries** marked `[NEEDS VALIDATION]` or `[READY TO PROMOTE]` that have supporting evidence
- **Dimension 8 agent memory patterns** flagged as promotion-worthy (recurring across agents, reusable)
- **§6m Deep Verify DEMOTE verdicts** (only when a Deep Verify sweep ran this invocation) — demotion candidates carrying the entry text, source location (`file.yaml::key`), each judge's verdict and reasoning, and tie-break reasoning if split

### Triage Workflow

**11a. Collect candidates.** During steps 6 and 8, build a candidate list. Each candidate needs:
- The entry text (verbatim from parking lot or agent memory)
- Source location (discipline file + line, or agent memory file)
- Evidence (why it's promotion-worthy: recurrence count, agent feedback, deliverable references)
- Suggested target (which knowledge store it would go into — existing or new)

**How the evidence gets produced:** if the candidate batch has 3+ entries, or any candidate lacks direct deliverable evidence, run the Promotion Verification Gate (`[sdlc-root]/process/discipline_capture.md` § Promotion Verification Gate) before 11b: two independent non-orchestrator judges review a neutral payload at the screening tier; unanimous-PROMOTE entries are presented to CD as verified candidates, unanimous-DEMOTE entries are dropped from the candidate list (their dissent reasoning appended to the parking-lot entry), and splits are resolved by a frontier-tier tie-break judge — the 2–1 majority applies, with any dissent alleging a specific factual error flagged prominently in the CD presentation. The full promote-bound slate then gets a final frontier-tier once-over (single batch dispatch, blind to earlier verdicts) before 11b; its DEMOTEs are flagged to CD, never silently applied or discarded. The once-over is unconditional for every promotion candidate: a single well-evidenced entry may skip the screening panel, but it still goes through the frontier once-over before 11b — deliverable evidence alone never carries a candidate to CD without an independent frontier-tier fact-check. Do not substitute the orchestrator's own assessment for the Evidence field.

**11b. Present candidates grouped by discipline.** Use `AskUserQuestion` to present candidates in batches (one discipline at a time):

```
TRIAGE: [Discipline Name] — N candidates

1. "[entry text]"
   Source: disciplines/coding.md
   Evidence: Referenced in D3, D5, D7 execution. 2 agents flagged independently.
   Suggested target: knowledge/coding/typescript-patterns.yaml → new item under "Error Handling"

2. "[entry text]"
   Source: .claude/agent-memory/backend-developer/patterns.md
   Evidence: Appears in 3 agent memories. Consistent pattern across all API routes.
   Suggested target: knowledge/architecture/api-design-methodology.yaml → new item

For each: (P)romote, (D)efer, (S)kip
```

**11c. Apply CD decisions.**

- **Promote:** Create or update the target knowledge YAML file with the new entry. Mark the parking lot entry as `Promoted → [target file path] ([date])`. If the source was an agent memory, add the entry to the relevant discipline parking lot as `Promoted → [target file path] ([date])` for traceability.
- **Defer:** Update the parking lot entry marker to `[DEFERRED]` with CD's reason appended.
- **Skip:** Leave the entry unchanged — it stays at its current marker for next audit cycle.
- **Demote** (Deep Verify candidates only): Remove the entry from the knowledge YAML using the comment-preserving removal script (`references/deep-verify.md` § Reusable Scripts — never a `yaml.safe_dump()` round-trip). Restore a parking-lot entry in the relevant discipline file marked `[NEEDS VALIDATION]` with the demoting judges' reasoning appended inline. Grep the entry's key across `[sdlc-root]/disciplines/*.md` and fix any `Promoted →` ledger lines that point at the removed entry. Bump the knowledge file's `last_updated` if present. Log the sweep in `[sdlc-root]/knowledge/provenance_log.md` with `source-type: audit-sweep` (one entry for the whole sweep, not per demotion).

**11d. Report triage results.** Append triage outcomes to the audit artifact:

```markdown
### Triage Results
| # | Entry | Decision | Target |
|---|-------|----------|--------|
| 1 | [summary] | Promoted | knowledge/coding/typescript-patterns.yaml |
| 2 | [summary] | Deferred — not validated yet | — |
| 3 | [summary] | Skipped | — |

Promoted: N | Deferred: N | Skipped: N
```

### Prune Triage (Orphaned Knowledge)

After promotion triage, present orphaned knowledge files identified in §6k for pruning decisions.

**11e. Present prune candidates grouped by severity.** Use `AskUserQuestion`:

```
PRUNE TRIAGE: Orphaned Knowledge Files — N candidates

HIGH PRIORITY (no provenance, inactive >90 days):

1. knowledge/architecture/legacy-patterns.yaml
   Last modified: 2025-10-15 (182 days ago)
   Provenance: none
   Discipline: architecture (5 agents mapped)
   → (P)rune | (W)ire to agents | (K)eep

MEDIUM PRIORITY (unwired but active):

2. knowledge/design/interaction-animation.yaml
   Last modified: 2026-04-15 (today)
   Provenance: prov-2026-04-15-001 (ingest)
   Discipline: design (3 agents mapped)
   Candidate agents: ui-ux-designer, frontend-developer, accessibility-auditor
   → (P)rune | (W)ire to agents | (K)eep

For each: (P)rune, (W)ire, (K)eep
```

**11f. Apply prune decisions.**

- **Prune:** Delete the knowledge file. Remove any provenance entry that references it. Log the deletion in the audit artifact.
- **Wire:** Run the wiring flow from sdlc-ingest step 6 — present candidate agents, let CD select, update `[sdlc-root]/knowledge/agent-context-map.yaml`.
- **Keep:** Leave unchanged. Optionally add a note in provenance log explaining why the file is intentionally unwired (e.g., "reference only, not for agent consumption").

**11g. Report prune results.** Append to the audit artifact:

```markdown
### Prune Results
| # | File | Decision | Action Taken |
|---|------|----------|--------------|
| 1 | knowledge/architecture/legacy-patterns.yaml | Pruned | Deleted |
| 2 | knowledge/design/interaction-animation.yaml | Wired | Added to ui-ux-designer, frontend-developer |
| 3 | knowledge/legal/compliance-rules.yaml | Kept | No agents map to legal/ yet |

Pruned: N | Wired: N | Kept: N
```

### When to Skip Triage

- **No candidates:** If steps 6 and 8 found no promotion candidates AND §6k found no prune candidates, skip step 11 entirely. Do not force a triage session.
- **User declines:** If CD says "skip triage" or "not now," respect that. Note "Triage deferred by CD" in the audit artifact.
- **Prune-only:** If there are prune candidates but no promotion candidates, still run the prune triage portion of step 11.

## Report Format

```markdown
## SDLC Compliance Audit — [Date]

### Summary
- Total deliverables: N
- Complete: N | Active: N | Blocked: N
- Knowledge layer wiring: connected | partially connected | disconnected
- Compliance score: X/10
- Top issues: [brief list]

### Catalog Integrity
[findings]

### Artifact Traceability
[per-deliverable status]

### Untracked Work
[commits/changes that should have been tracked]

### Knowledge Freshness
[stale docs, outdated memories]

### Knowledge Layer Health
#### Discipline Parking Lots
[per-file status, cross-discipline flow, maturity verification]

#### Discipline Usage Audit
| Discipline | Level | Parking Lot | Knowledge | Promotion | Cross-Feed |
|-----------|-------|-------------|-----------|-----------|------------|

#### Knowledge Stores
[per-directory status]

#### Discipline Triage Status
[markers, promotion recommendations]

#### Knowledge-to-Skill Wiring
[wiring status, gaps]

#### Agent Context Map
[path resolution, unmapped files]

#### Playbook Freshness
[per-playbook status]

#### Knowledge Staleness (6h)
[per-file staleness status — last refreshed date, threshold comparison]

#### Cross-File Contradictions (6i)
[potential contradictions found, or "No contradictions detected"]

#### Coverage Gaps (6j)
[promotable entries without stores, unreferenced knowledge files, empty agent mappings]

#### Orphaned Knowledge (6k)
[files not wired to any agent — high/medium/info priority, prune candidates for triage]

### Migration Integrity
- Manifest version: [hash] ([age] behind)
- Framework completeness: N/N files
- Content-merge: [pass/issues]
- Stale references: [list or none]

### Agent Memory Patterns
[recurring findings worth promoting]

### Changelog Freshness
[entries vs process commits]

### Recommendation Follow-Through
[previous recommendations status]
- Follow-through rate: X%

### Triage Results
| # | Entry | Decision | Target |
|---|-------|----------|--------|
[triage outcomes — omit section if no candidates or triage skipped]

Promoted: N | Deferred: N | Skipped: N

### Prune Results
| # | File | Decision | Action Taken |
|---|------|----------|--------------|
[prune outcomes — omit section if no orphans or prune triage skipped]

Pruned: N | Wired: N | Kept: N

### Recommendations
[prioritized action items]
```

## Severity Levels

- **Critical**: Missing specs for completed features, deliverable ID conflicts, catalog entries pointing to nonexistent files
- **Warning**: Incomplete artifact chains, stale docs, unarchived completed work, disconnected knowledge stores, dormant disciplines
- **Info**: Minor naming inconsistencies, optional improvements, unmarked parking lot entries. Note: promotion candidates are no longer reported as INFO findings — they are handled interactively in step 11 (triage)

## Guiding Principles

- **Read before asserting.** Never claim a file exists or doesn't without checking.
- **Substance over ceremony.** Flag missing artifacts only when the gap creates real risk.
- **Proportional recommendations.** Small gaps get small fixes.
- **Honor the ad hoc exception.** Single-file fixes, config changes, typo corrections legitimately skip tracking.
- **Context-aware.** The SDLC is lightweight by design — small team or solo dev + AI.
- **Toolbox, not recipe.** Empty parking lots aren't failures if the discipline hasn't been needed. Only flag staleness when the discipline IS being exercised but knowledge layer isn't participating.

## Audit Artifact Lifecycle

- Output: `docs/current_work/audits/sdlc_audit_YYYY-MM-DD.md`
- Keep the last 5 audits; recommend deleting older ones
- Not deliverables — don't archive to chronicles
- Consumed by: this skill on subsequent runs (follow-through), planning skills (knowledge wiring gaps), the user (periodic health check)

## File Naming Conventions to Validate

| Type | Pattern | Example |
|------|---------|---------|
| Spec | `dNN_name_spec.md` | `d1_auth_spec.md` |
| Plan | `dNN_name_plan.md` | `d1_auth_plan.md` |
| Result | `dNN_name_result.md` | `d1_auth_result.md` |
| Complete | `dNN_name_COMPLETE.md` | `d1_auth_COMPLETE.md` |
| Blocked | `dNN_name_BLOCKED.md` | `d1_auth_BLOCKED.md` |
