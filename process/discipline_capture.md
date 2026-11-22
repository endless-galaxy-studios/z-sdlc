# Discipline Capture Protocol

A lightweight step for capturing cross-discipline insights during active work. Skills reference this file instead of duplicating the protocol.

## When This Runs

After substantive work completes — post-execution, post-planning, post-exploration, post-design. Each skill specifies its own trigger point.

## Structured Gap Detection

Before the freeform scan, run these comparisons using data already in context. These detect systematic gaps that are invisible to a vibes-based scan.

### Comparison 1: Knowledge loaded vs. needed

For each agent dispatched in this session, compare what knowledge was available against the FIX findings the agent produced. Ask: could a knowledge file have prevented this finding?

- **If `knowledge_feedback.loaded` is present** in the agent's handoff, use it — this is the most accurate source of what the agent actually read. Read `[sdlc-root]/knowledge/architecture/agent-communication-protocol.yaml` for the handoff schema.
- **Otherwise**, look up the agent's mapped files from `[sdlc-root]/knowledge/agent-context-map.yaml`. If the lookup for multiple agents would exceed the time budget, skip this comparison and note "deferred to auditor."

**What to detect:**

| Signal | GAP Type | Example |
|--------|----------|---------|
| Finding could have been prevented by knowledge that doesn't exist | `MISSING_KNOWLEDGE` | Agent hit a React StrictMode gotcha not in any knowledge file |
| Knowledge exists but wasn't mapped to this agent | `UNMAPPED_KNOWLEDGE` | Agent needed testing patterns but only had architecture files mapped |
| Knowledge was mapped but agent still got it wrong | `STALE_KNOWLEDGE` | Gotcha file says "use X" but X no longer works in current version |
| A library, API, or framework behaved unexpectedly | `GOTCHA_DISCOVERED` | Pagination API silently returns empty pages instead of 404 past the last page |
| Refactored away from a pattern that was causing problems | `ANTI_PATTERN_HIT` | Nested ternaries in render logic caused stale-closure bugs; extracted to named functions |

### Comparison 2: Cross-domain friction

When agents were dispatched into cross-domain contexts (e.g., a backend agent fixing a frontend issue), did they produce FIX findings in the foreign domain?

- **For skills with a review-fix loop** (sdlc-execute, sdlc-lite-execute, sdlc-plan, sdlc-lite-plan): check the triage table for FIX findings where the fixing agent worked outside its primary domain.
- **For sdlc-idea and sdlc-design-consult** (no triage table): this is a judgment call — did the agent's output reveal it struggled with something outside its domain?

If yes → write a `CROSS_DOMAIN_FRICTION` GAP entry in the relevant discipline's parking lot.

### Comparison 3: Iteration cost

If the review-fix loop ran >2 rounds, did you observe a finding recurring across rounds?

**This is a judgment call**, not a mechanical count. The review-fix loop doesn't assign finding IDs across rounds. The orchestrator assesses "did this look like the same issue?" based on finding descriptions. Resurfacing findings suggest a pattern that isn't captured in any knowledge store.

If yes → write a `RESURFACING_PATTERN` GAP entry.

**Not applicable** to sdlc-idea and sdlc-design-consult (no review-fix loop).

### Skill applicability

| Skill | Comparison #1 | Comparison #2 | Comparison #3 |
|-------|--------------|--------------|--------------|
| sdlc-execute, sdlc-lite-execute | Yes (full triage data) | Yes | Yes |
| sdlc-plan, sdlc-lite-plan | Yes (planning findings) | Yes | Yes (if >2 rounds) |
| sdlc-idea | Conditional (no triage table) | Yes (judgment-based) | No |
| sdlc-design-consult | Conditional (no triage table) | Yes (judgment-based) | No |
| sdlc-review-code (fix loop) | Not applicable — commit-scoped findings are too narrow for discipline-level gap detection |

### GAP entry format

Auto-detected gaps use a distinct format and are always marked `[NEEDS VALIDATION]`:

```
- **[date] [context]**: [GAP:{type}] {description}. Source: {agent} finding. [NEEDS VALIDATION]
```

Types: `MISSING_KNOWLEDGE`, `UNMAPPED_KNOWLEDGE`, `STALE_KNOWLEDGE`, `CROSS_DOMAIN_FRICTION`, `RESURFACING_PATTERN`, `GOTCHA_DISCOVERED`, `ANTI_PATTERN_HIT`

## Freeform Insight Scan

After structured gap detection, scan the work just completed for insights that are:

- **Reusable** — applies beyond this specific deliverable
- **Non-obvious** — not something an agent would derive from reading the codebase
- **Cross-discipline** — belongs to a discipline other than the primary work (e.g., a testing gotcha discovered during implementation, an architecture boundary issue surfaced during planning)

Common signals:

| Source | Example |
|--------|---------|
| Agent review finding | "Agent flagged a pattern that applies to all API endpoints, not just this one" |
| Discovery during research | "Context7 revealed a library gotcha not in our knowledge store" |
| Execution friction | "This approach required 3 re-dispatches because the data flow wasn't documented" |
| Cross-domain surprise | "Backend agent needed design knowledge to implement this correctly" |
| Agent knowledge feedback | Agent's `knowledge_feedback.missing` describes a gap worth capturing |

## How to Capture

Append each insight or GAP entry to the relevant `[sdlc-root]/disciplines/*.md` parking lot under the `## Parking Lot` heading.

**Entry format:**

```
- **[date] [context]**: [Insight title] — [description]. [triage marker]
```

The `[context]` tag MUST appear in the bold header at the start of the entry. This is what `sdlc-archive` uses to correlate parking lot entries with the deliverable being archived. Entries without a context tag in the header are invisible to archival hygiene.

**Context formats by skill:**
- Execution: `[DNN — phase N]`
- Planning: `[DNN — planning]`
- Idea exploration: `[idea: {slug}]`
- Design consultation: `[sdlc-design-consult: {slug}]`

These are the ONLY valid context formats. Do not invent variants like `[session: DNN-execution]`, `[DNN execution]`, or bare `[DNN]`. The `sdlc-archive` skill scans for these exact patterns — non-standard formats are invisible to archival hygiene.

**Concrete examples:**

```markdown
- **[2026-05-28] [D12 — phase 2]**: Async session factories — pass a factory, never a shared session, to avoid cross-request state leaks. [NEEDS VALIDATION]
- **[2026-05-28] [D12 — planning]**: [GAP:MISSING_KNOWLEDGE] No knowledge file covers WebSocket reconnection patterns. Source: realtime-systems-engineer finding. [NEEDS VALIDATION]
- **[2026-05-28] [idea: caching]**: Cache invalidation via TTL is simpler but stale reads are acceptable for this use case. [NEEDS VALIDATION]
```

**Adapter-backed installations:** When storing via `memory_store`, include the deliverable context as a structured tag alongside the discipline and parking-lot tags. This enables `sdlc-archive` step 9a to filter by tag rather than scanning entry content. Derive the tag from the context format: `[DNN — phase N]` or `[DNN — planning]` → `sdlc:deliverable:DNN`; `[idea: {slug}]` → `sdlc:context:idea:{slug}`; `[sdlc-design-consult: {slug}]` → `sdlc:context:design-consult:{slug}`.

**Triage markers:**
- `[NEEDS VALIDATION]` — default for newly captured insights and all auto-detected GAP entries
- `[READY TO PROMOTE]` — use only if you're confident the insight is validated, reusable, and stable
- `[DEFERRED]` — acknowledged but not a priority (include reason)

## Promotion Verification Gate

Promotion to a knowledge store is where a single agent's self-assessment is weakest and where a bad entry does the most compounding damage — once promoted, it becomes precedent every future agent reads. Before proposing either high-risk transition (any → `[READY TO PROMOTE]`, `[READY TO PROMOTE]` → `Promoted →`), the orchestrator must produce independent evidence rather than substitute its own judgment. CD remains the deciding authority for both transitions (see the triage authority matrix in the sdlc-audit compliance methodology §6c); this gate is how CD's decision gets evidence.

### When the full gate is required

Run the multi-judge gate when **either** holds:

- The candidate batch has **3 or more entries**, or
- Any entry lacks **direct deliverable evidence** — recurrence across deliverables, independent-reviewer citations already in the entry text, or corroboration from an existing knowledge-store entry making the *same* claim (an adjacent claim is not corroboration).

A single well-evidenced entry may skip the screening panel (steps 2–4), but **not the frontier once-over (step 5)** — deliverable evidence proves the pattern was used, not that the entry's specific claims are true, so no promotion candidate reaches CD without at least one independent frontier-tier fact-check. Run the entry through step 5 (build the neutral payload from step 1 for it first), then present it to CD with its evidence and the once-over verdict attached, in the interactive-triage candidate format (compliance methodology step 11a). The lighter path replaces the screening judges, not the frontier review or the CD decision — never promote on the orchestrator's judgment alone.

### The gate

1. **Build one neutral evidence payload** for the candidate batch: each entry's full text plus corroboration signals — recurrence count across deliverables, independent-reviewer citations already in the text, whether an existing knowledge-store entry makes the same (vs. merely adjacent) claim, and external validity as a known engineering principle. **No verdicts in the payload** — every judge reasons from the same raw evidence independently. Write it as a numbered, self-contained file (session scratchpad is fine; it is working material, not an artifact).
2. **Dispatch two independent non-orchestrator judges at the screening tier.** Screening is the high-volume pass — run it on capable-but-not-frontier configurations and save frontier capacity for tie-breaks (step 4):
   - **External judge, if configured:** if an executable `[sdlc-root]/external-review-knowledge.sh` exists, pipe the payload to it (wrapper contract in `[sdlc-root]/process/external-review-gate.md` § Knowledge-Judgment Wrapper). Set a balanced/mid-tier `CODEX_MODEL` (looked up just before the call, per that doc § Task-Based Model Selection) with `CODEX_REASONING_EFFORT=high`. This is data egress if the wrapper calls a hosted model — the egress rules in that doc apply; state where the payload is going before running.
   - **Subagent judge, always:** dispatch an Agent (`model: "opus"`) pointed at the payload file, instructed to read nothing else and told nothing of any other judge's existence or verdict.
   - **No external wrapper configured (or wrapper errored):** dispatch a **second** independent subagent judge, so there are always two independent judges.
   - **Every judge's instructions must require fact-checking, not just pattern recognition.** Retroactive analysis of 674 promoted entries showed the dominant split cause was lens divergence: one judge asking "is this a recognized general pattern?" (almost always yes) while the other fact-checked the specific claims embedded in the entry (frequently no — stale numeric thresholds, wrong API/protocol semantics, internal contradictions). Instruct judges explicitly: *verify every specific factual claim — numeric thresholds, version-sensitive benchmarks, protocol/API semantics, internal consistency. A recognized general pattern containing a false or unverifiable specific claim is a DEMOTE.*
3. **Collect verdicts** in the format `N | PROMOTE|DEMOTE | one-sentence justification`, one line per entry.
4. **Tally — the orchestrator is not a judge.** It assembled the candidate list, so it does not vote and does not break ties; its own read may be recorded alongside for CD's benefit. The decision rule uses only the independent judges:
   - **Both PROMOTE** → present to CD as a verified candidate (CD still decides; the authority matrix is unchanged).
   - **Both DEMOTE** → the entry is not proposed and keeps its current marker. No CD interaction needed unless the orchestrator disagrees strongly — then escalate it as a split.
   - **Split → escalate model/effort, not CD.** Dispatch one fresh **tie-break judge at the frontier tier** — the external wrapper with a frontier `CODEX_MODEL` at `CODEX_REASONING_EFFORT=xhigh` if configured, otherwise a `model: "fable"` subagent (`"opus"` if unavailable) — blind to the split, given only the neutral payload for the split entries, with the same fact-checking instructions. The resulting 2–1 majority applies; the dissenting justification is recorded with the entry either way. Do not send raw splits to CD one-by-one — at batch scale that doesn't work (the retroactive run produced 122 splits).
   - **Factual-error dissents get flagged.** If a 2–1 PROMOTE overrides a dissent that alleges a specific, checkable factual error (as opposed to a judgment-call disagreement), flag that entry prominently in the CD presentation with the dissent's full reasoning — factual-error dissents were the highest-value signal in the retroactive analysis and should not be buried by a majority.
5. **Frontier once-over of the promote-bound slate.** This step is unconditional for every promotion candidate — including single well-evidenced entries that skipped the screening panel. Before presenting candidates to CD, send every PROMOTE-bound entry — unanimous PROMOTEs, tie-broken 2–1 PROMOTEs, and screening-skip entries alike — through one final frontier-tier judge (external wrapper with a frontier `CODEX_MODEL` at `xhigh` if configured, else a `model: "fable"` subagent) as a **single batch dispatch**: same neutral payload, same fact-checking instructions, blind to the earlier verdicts. This is the backstop that verifies the screening tier got it right, at a fraction of the cost of running the whole gate at the frontier tier. Its PROMOTEs confirm the slate. Any DEMOTE it returns is a frontier dissent against the lower tiers — neither silently apply it nor silently discard it: flag the entry to CD with the once-over's full reasoning, same treatment as a factual-error dissent. Demote-bound entries are not re-reviewed — an entry wrongly held back waits for the next triage cycle; an entry wrongly promoted compounds, so the once-over spends its budget where the risk is asymmetric.
6. **Record the outcome.** Entries that survive and get CD approval move through the Promotion Workflow below. Entries that don't survive stay at their current marker with the dissenting judge's reasoning appended inline, so the next triage pass sees why the entry was held back instead of re-litigating it from scratch.

## Promotion Workflow

When an entry is promoted to a knowledge store, it must be **moved** from the `## Parking Lot` section to a `### Promoted` section at the bottom of the discipline file. Do not leave promoted entries mixed in with active entries — they clutter the working set and make triage harder.

1. Remove the entry from its current position in the parking lot
2. Append it to the `### Promoted` section (create the section if it doesn't exist)
3. Replace the triage marker with `Promoted →` followed by the target location

**Promoted entry format:**
```markdown
### Promoted

- **Entry title.** Promoted → `[sdlc-root]/knowledge/{domain}/{file}.yaml` ({section} section)
```

The promoted section is a ledger — it records what was promoted and where, so triage passes don't re-discover the same insight. Keep the entry text short; the full content now lives in the knowledge store.

An entry can also be promoted to a **fitness function**, a committed test or check that enforces it: ``- **Entry title.** Promoted → `path/to/test` (fitness function)``. CD still approves it. The Promotion Verification Gate's panel judges knowledge entries; a fitness function is checked by running it, so it must fail without the behavior it enforces and pass in CI.

## Rules

- **Skip if nothing surfaced.** Do not fabricate entries. Empty is fine — discipline capture is pulled, not pushed.
- **<3 minutes total.** Structured gap detection: ~30s. Freeform scan: ~2 minutes. If a structured comparison would exceed the time budget, skip it and note "deferred to auditor."
- **One insight per bullet.** Keep entries atomic so they can be triaged independently.
- **The orchestrator writes these directly.** This is process documentation, not domain content — the Manager Rule does not apply. Do not dispatch an agent to write a parking lot entry.
- **Audit triage carve-out.** The `sdlc-audit` skill (compliance mode) may apply low-risk triage markers (unmarked → `[NEEDS VALIDATION]`, `[NEEDS VALIDATION]` → `[DEFERRED]`) directly per its triage authority matrix in the compliance methodology §6c. High-risk transitions (any → `[READY TO PROMOTE]`, any → `Promoted →`) remain CD-only, with evidence produced by the Promotion Verification Gate above — CD decides, the gate is how the decision gets evidence.
