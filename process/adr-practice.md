# ADR Practice

Shared reference for Architecture Decision Record (ADR) conventions. Linked from planning, execution, and review skills so the language stays in sync. Edit here once; all skills pick up the changes on their next invocation.

## What an ADR is

An ADR captures a single significant architectural decision: the context that forced the choice, the options considered, the option taken, and the rationale. ADRs are durable constraints that agents must respect.

- **Home:** `docs/architecture/decisions/adr-NN_{slug}.md`
- **Template:** `[sdlc-root]/templates/decision_record_template.md`
- **Catalog:** `docs/architecture/decisions/_index.md`
- **Owner:** The architect role drafts; affected domain agents review; CD approves. Other agents read and respect active ADRs.

## Immutability

ADRs are append-only facts. Once Active, you do **not** edit a prior ADR to reflect a newer choice — you write a new ADR that `Supersedes` the prior one and link both directions via frontmatter. This preserves the reasoning chain: someone later can reconstruct *why* the old decision was made and what changed. The only in-place edits are the three in § Amendments vs. Supersessions, plus the Status line and frontmatter a supersession sets on the ADR it replaces; none changes what the ADR requires or forbids.

## Crystallization Signals

An ADR is warranted when work introduces any of:

- A new service boundary (new container in the C4 sense, or a new arrow between existing containers)
- A new external library or framework (or replaces an existing one)
- A new data-model shape (new table, relationship type, or invariant)
- A new dependency edge (A now calls B where it didn't before), or an existing edge reversed
- A new protocol surface (new API endpoint family, new event stream, new MCP tool signature)
- A new fitness function (CI check, lint rule, import-boundary enforcement)
- A configuration safety default that encodes a decision (flipping a lenient default to strict for durability)
- A codified defensive pattern (new base class, middleware, guard, or invariant enforcement that encodes a learned failure-mode response)

If none of these apply, the work is conformance to existing ADRs — note that explicitly in the result doc (`Architectural decisions: none — conforms to existing ADRs`) rather than producing a new ADR.

## Contradiction Handling

If proposed or in-flight work appears to contradict an active ADR, surface the conflict rather than silently resolving it. Contradictions are CD's to resolve, with three paths:

1. **Supersede** — write a new ADR with `Supersedes: ADR-N` in frontmatter; the old ADR's status becomes `Superseded by ADR-M`. Ship the supersession ADR in the same commit as the code that relies on the new decision.
2. **Conform** — revise the approach to match the active ADR.
3. **Reject** — if neither supersession nor conformance is acceptable, the deliverable itself needs to change.

Never edit the prior ADR in place to reflect the new choice (§ Amendments vs. Supersessions lists the only in-place edits, plus the Status line and frontmatter a supersession sets on the ADR it replaces, and none changes what the ADR requires or forbids). Never merge work that contradicts an active ADR without also merging the supersession ADR in the same commit.

## Three Functions

ADRs integrate into SDLC skills via three functions. All three are skip-if-absent: if `docs/architecture/decisions/` does not exist in the project, the step is a no-op.

### READ — discovered as constraints

Planning skills (`sdlc-plan`, `sdlc-lite-plan`) scan `docs/architecture/decisions/_index.md` during discovery, list active ADRs relevant to the work's domain, and include them in agent dispatch prompts as technical constraints. This prevents agents from re-litigating decided questions.

### PRODUCE — drafted when crystallized

Execution skills (`sdlc-execute`, `sdlc-lite-execute`) run an architecture-decision check at the result-doc step. If the work crystallized a new architectural choice (see signals above), they dispatch the architect agent to draft the ADR before marking the deliverable complete. The ADR is committed with the code that crystallized it — same commit.

Incident skills (`sdlc-debug-incident`) run the same check at postmortem closeout — remediations that changed architecture produce an ADR with the postmortem cited as `triggered_by`.

### RESPECT — enforced at review

Review skills (`sdlc-review-code`) apply an ADR-drift lens: for each active ADR relevant to the changed files, verify the change does not violate the ADR's decision. Drift gets flagged as `major` with category `adr-drift`. Intentional supersessions require a matching supersession ADR staged in the same diff; missing supersession is itself an `adr-drift` finding.

## Lightweight Variants

For decisions that warrant a record but do not need the full template structure:

**Y-Statement format** — single paragraph:
> In the context of *<problem>*, facing *<constraint>*, we decided for *<option>* and against *<alternatives>*, to achieve *<benefit>*, accepting that *<cost>*.

**Lightweight ADR** — Status, Date, Context (1-3 sentences), Decision, Consequences (Good/Bad/Mitigations).

Both variants live in the same `docs/architecture/decisions/` directory with the same numbering.

## Negative Constraints: "What This ADR Forbids / Does NOT Decide"

Any ADR that decides "X uses pattern Y" should also explicitly document "X must NOT do Z" — the negative constraints prevent future agents from drifting toward the wrong shape. This applies especially to ADRs drafted alongside specs/plans, where the decision is partially implemented and partially deferred.

An ADR without negative constraints is aspirational — it describes what was chosen but not what was excluded. Future agents reading the ADR may reasonably implement approaches that the original decision intended to prevent, because the prevention was implicit rather than stated.

Add a subsection titled **"What This ADR Does NOT Decide"** or **"What This ADR Forbids"** (or both) covering:

1. **Deferred scope** — aspects the ADR intentionally leaves open for future decisions. Name them explicitly so future work knows where the seam is, rather than assuming the ADR covers everything.
2. **Architectural prohibitions** — patterns or access paths that the decision structurally prevents. These are candidates for fitness functions (CI assertions, lint rules, import boundary tests) that enforce the prohibition automatically.
3. **Phase boundaries** — if the ADR covers a multi-phase implementation, state what is NOT in Phase 1 and where the seam is. This prevents Phase 2 work from choosing an incompatible shape.

## Amendments vs. Supersessions

ADR immutability has three narrow exceptions that do not require a superseding ADR. All three require an `## Amendment` trailer at the bottom of the ADR (a dated `## Amendment log` section of entries is the same trailer) documenting what changed and why it is not a supersession. Each trailer entry names the exception it uses (`Exception: placeholder correction`, `rendering update`, `status fact` or `answer to an open question`), stands on its own, and never declares that it wins over the ADR's body.

**Placeholder corrections** — a fact written into the Decision section turned out wrong before any consumer depended on it (e.g., a URL placeholder for an unbuilt repo, a version number for an unreleased dependency). The decision itself is unchanged; a detail that was always intended to have a specific value is corrected to that value. The amendment trailer cites the correction and confirms no consumer depended on the placeholder.

**Rendering updates** — diagram syntax, formatting, or rendering directives that change how the ADR displays without changing what it decides (e.g., updating Mermaid syntax for a new renderer version). The amendment trailer cites the rendering change.

**Status facts and answers to open questions** — one of the two edits below, each with the trailer the last item describes:

- **Status fact:** a proposal (an item the ADR itself marks undecided: Proposed, pending CD) was dropped; something the ADR already required has landed (the PR a Status line awaited has merged); or a proposal was adopted without adding, removing or changing a requirement or prohibition (e.g., a proposed fitness function was built and enforces a constraint already in the ADR). Adding a proposal (any item or section marked Proposed) to an Active (or Accepted) ADR is never a status fact: a proposed change, or an adopted proposal that adds a requirement or prohibition, is drafted as a superseding ADR. Retiring the ADR (Expired, or removing its constraints) is outside this exception; until the framework defines retirement, supersede.
- **Answer to an open question:** CD's answer to a question the ADR left open, written where the question was. It qualifies only when it defers the item, declines a proposal or keeps the current state; one that picks a new requirement or prohibition is a supersession. It is written as a dated fact with its reopening trigger ("CD declined X on YYYY-MM-DD; revisit when …"), never as an instruction ("X is not allowed"). Neither the recorded decline or keep nor its revisit trigger is a requirement or prohibition: work that wants X goes back to CD, as it would have while the question was open.
- **Trailer:** says what happened, quotes the text it replaced (if any), says where the decision or event is recorded, and confirms no constraint changed.

Everything else — including rewording the Decision section to say something substantively different, adding new constraints, removing existing constraints, or tightening or loosening one — is a narrative edit and requires a superseding ADR. The test: does the edit add, remove or change (loosen or tighten) anything the ADR requires or forbids, in any section (e.g., Decision, Consequences, What This ADR Forbids, Revisit)? Then supersede. It decides only whether a status-fact or answer edit qualifies (placeholder corrections and rendering updates have their own conditions above), and an edit that is none of the three exceptions is a supersession whatever the test says. When in doubt, supersede. The cost of an unnecessary supersession ADR is one extra file; the cost of a misclassified in-place edit is a broken reasoning chain.

## Template Section Discipline

The decision-record template (`[sdlc-root]/templates/decision_record_template.md`) is loosely MADR-style. The following sections are mandatory; sections may be omitted only when explicitly N/A:

- **Status** — Proposed | Accepted | Deprecated | Superseded by ADR-N | Rejected
- **Context** — what forced the decision (problem statement, constraints, scope). Future readers cannot reconstruct rationale without this.
- **Decision Drivers** — the specific criteria the decision was scored against (must-haves vs nice-to-haves)
- **Considered Options** — at least two; "do nothing" is a valid option when reversibility is asymmetric
- **Decision** — the option taken, named explicitly
- **Rationale** — why the chosen option won against the alternatives; trade-offs explicit
- **Consequences** — Positive, Negative, Risks (mitigations noted). Honest negatives required — ADRs that read as press releases lose their value as future reference.
- **Implementation Notes** — links to migrations, fitness functions, observed metrics
- **Related Decisions** — backlinks to ADRs this complements, supersedes, or depends on

ADRs should target 1-2 pages. Longer than that means either the decision contains multiple sub-decisions (split into separate ADRs) or the Context is doing the work of a research doc (move analysis to a research deliverable, link from ADR).

## Review Checklist

Before merging an ADR:

- [ ] Context clearly explains the problem and the constraints
- [ ] At least two viable options considered (or "do nothing" justified)
- [ ] Pros / Cons / Risks are balanced and honest — not a single-option promotion
- [ ] Consequences (positive, negative, risks) documented with mitigations
- [ ] Related ADRs linked (Supersedes, Complements, Depends on)
- [ ] Implementation notes link to migrations, fitness functions, observed metrics
- [ ] Reversibility assessed — one-way door vs two-way door explicitly stated
- [ ] Affected agents (per `[sdlc-root]/knowledge/agent-context-map.yaml`) consume the ADR or are notified that they should

## Directory Conventions

- **Numbering:** ADR-1, ADR-2, ... sequential, never reused
- **File naming:** `adr-NN_short_name.md` (lowercase, zero-padded two-digit number, underscores)
- **Statuses:** Active | Superseded by ADR-XX | Expired
- **Catalog:** `docs/architecture/decisions/_index.md` — live index with status, revisit schedule, cross-references
- **Template:** shared with business DRs — `[sdlc-root]/templates/decision_record_template.md`
