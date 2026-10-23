# Guardrail Lifecycle

How recurring review findings graduate into **mechanized guards** — lint rules, drift tests, CI checks — and how those guards are kept honest afterward. This is a cross-skill contract: `sdlc-review-code` logs patterns, `sdlc-reflect` and `sdlc-audit` propose promotions, CD approves at triage, and every review-fix loop treats guard modification as in-scope work. A guard is never set once and forgotten — each audit cycle re-evaluates whether it still fires, still matches its pattern, and still earns its place.

## The Loop

```
LOG → THRESHOLD → PROMOTE → ENFORCE → RE-EVALUATE → MODIFY or RETIRE
```

1. **Log** — `sdlc-review-code` Step 6 clusters review findings into `docs/reviews/recurring-patterns.yaml`.
2. **Threshold** — `sdlc-audit` Dimension 6l scans clusters for 3+ occurrences in the sliding window; `sdlc-reflect` runs the same scan session-scoped between audits. Neither redefines the threshold — 6l's numbers are canonical.
3. **Promote** — at audit triage (compliance methodology step 11), CD decides per candidate: promote to knowledge store, promote to a mechanized guard, both, defer, or dismiss. Knowledge promotion teaches agents; guard promotion makes the machine catch the next occurrence. A pattern that keeps recurring *after* knowledge promotion is the strongest guard-promotion signal — the agents were told and it still happened.
4. **Enforce** — the project implements the guard and the cluster records it in its `mechanized_guard` field (schema below).
5. **Re-evaluate** — `sdlc-audit` Dimension 6n checks every recorded guard's freshness on each audit cycle.
6. **Modify or retire** — review-fix loops treat guard updates as in-scope fixes; guards flagged ineffective by 6n are fixed or retired through triage, never silently ignored.

## Division of Labor

The framework defines the loop, the schema, and the audit checks. **The project supplies the guards themselves** — the actual lint rules, drift tests, and CI wiring. z-sdlc never ships project-specific rules; it ships the contract that makes their absence, staleness, or ineffectiveness visible.

## The `mechanized_guard` Field

When CD approves guard promotion, add this field to the cluster in `docs/reviews/recurring-patterns.yaml` (schema owner: `sdlc-review-code` Step 6):

```yaml
    mechanized_guard:
      type: {lint-rule|drift-test|ci-check|pre-commit-hook|type-constraint|other}
      location: "{where the guard lives — rule ID, test file path, CI job/step name, hook script}"
      created: YYYY-MM-DD
      notes: "{optional — suppression mechanism, known blind spots}"
```

`location` must be specific enough for Dimension 6n to verify the guard still exists *and still enforces*: an ESLint rule name in a named config file, a test file path, a CI job and step. "We added a lint rule" without a locator fails the freshness check by construction.

A cluster can carry both `knowledge_entry` (knowledge promotion) and `mechanized_guard` (guard promotion) — the two paths are complementary, not exclusive. `promoted: true` continues to mean knowledge promotion only; a guard-only cluster keeps `promoted: false` with a `mechanized_guard` field.

## Assessed and Excluded — "Do Not Re-Propose"

Some patterns clear the occurrence threshold but should not be mechanized — the manifestations are heterogeneous, the guard would need semantics that don't exist, or the noise cost outweighs the catch rate. Dismissing such a candidate at triage is not enough: without a durable record, 6l and reflect re-propose it every cycle and CD re-dismisses forever. Record the decision on the cluster:

```yaml
    mechanization_assessed: excluded
    mechanization_reason: "{why the pattern resists mechanization or isn't worth it — recorded at triage}"
```

Semantics:

- **Set only by CD decision at triage.** Exclude is distinct from defer: defer means "re-propose next cycle"; exclude means "assessed, deliberately not mechanized, stop proposing."
- **6l and reflect skip excluded clusters** in guard-candidate output. They still report the excluded count (with reasons available) so the decision stays audit-visible — skipped is not hidden.
- **Guards only.** Exclusion says nothing about knowledge promotion — an excluded cluster can still be (or become) a knowledge-promotion candidate.
- **Reversible at triage.** If the pattern's manifestations later converge on a mechanizable signature, CD clears the fields at triage and the cluster re-enters normal candidate flow. New occurrences alone do not reopen the question — they accumulate on the cluster as usual and appear in the info-tier excluded listing, where CD can choose to revisit.

## What Qualifies for Guard Promotion

A pattern is **mechanizable** when its next occurrence could be detected without human judgment:

| Signature | Guard type | Example |
|-----------|-----------|---------|
| Textual — a string or regex marks the defect | lint-rule, pre-commit-hook, ci-check | `KEEP IN SYNC` comments; banned APIs; hardcoded env names |
| Structural — an AST or type-level shape marks it | lint-rule, type-constraint | missing `useShallow` on a zustand selector; untyped catch clauses |
| Behavioral — a test can fail when it happens | drift-test, ci-check | parallel copies diverging; schema/client drift; broken invariants |
| Preventable — a design or type change makes the next occurrence impossible | type-constraint, other | the wrong import fails to resolve; a query type that can't be built without its tenant |

Patterns requiring judgment — naming quality, over-abstraction — are **not** mechanizable unless the Preventable row applies; they take the knowledge-promotion path only. When proposing candidates, say which signature applies; "we could probably lint this" without naming the signature is not a proposal.

## Choosing the Fix for a Repeated Mistake

When a guard is proposed (audit Dimension 6l, `sdlc-reflect`) and when CD promotes one, fix the pattern at the highest level that works. The proposal names its level and why a higher one doesn't apply:

1. **Remove it by design.** Give each piece of state one owner and each task one supported way, hide internals so the wrong import fails, derive copies from one source instead of syncing them by hand, and delete the old way an agent would copy.
2. **Make the bad state unwritable with types,** so it doesn't compile.
3. **Add a lint or CI check whose error names the fix:** the file, type or function to use instead. When the pattern is already common, fail only when a change adds an instance: record the allowed count in `notes`, and lower it as instances are fixed.
4. **Test the behavior,** with a drift test or a check that fails when the pattern happens.
5. **Write a knowledge entry,** for what needs judgment. Nothing fails when an agent skips it.

This is an order of preference, not a demand to mechanize everything; the knowledge and guard paths still combine. Levels 1 and 2 prevent the pattern rather than detect it, so they qualify through the Preventable row of § What Qualifies for Guard Promotion. Record them with `type: other` or `type-constraint`, a `location` naming what now makes the mistake impossible, and `notes` naming the edit that must now fail ("importing `db/internal` doesn't compile"). Prove any new guard fails on a real past occurrence before relying on it, and run the same command locally and in CI. An exception sits on the offending line with its reason.

**Inside a review-fix loop** (§ Guard Modification Is In-Scope in Review Loops), a guard edit stays at levels 3 and 4, or a level 1 or 2 change confined to the finding's own diff. A wider design or type change is raised as a PLAN or DECIDE finding, not made in a fix dispatch.

## Guard Freshness (audit Dimension 6n)

For each cluster with a `mechanized_guard` field, `sdlc-audit` checks:

| Check | Signal | Finding |
|-------|--------|---------|
| **Guard exists and enforces** | `location` resolves AND enforcement is effective — presence of the rule-name string in config is not enough. Lint rules: parse the *effective* severity (`off` = not wired; `warn` = advisory unless `notes` documents that as intended); conditional registration (e.g., `plugin.rules["x"] ? {...} : {}`) must be evaluated for runtime collapse, not text-grepped. Tests: a skipped test enforces nothing. CI: a disabled or continue-on-error step enforces nothing. When static reading is inconclusive, run the guard against a known-bad sample | Missing or set to `off` → CRITICAL: guard recorded but not enforcing; the pattern log claims protection that isn't there. `warn`/advisory without documented intent → WARNING |
| **Recurred despite guard** | Cluster has occurrences dated after `mechanized_guard.created`, beyond any allowed count recorded in `notes` | WARNING: guard ineffective — blind spot, wrong scope, or suppressed; propose modify at triage |
| **Suppression growth** | Count in-code suppressions of the guard (e.g., disable comments naming the rule, skipped tests) and compare against the count noted at the last audit | WARNING when growing: the guard is being routed around, not obeyed |
| **Never fired** (best-effort) | For guards with observable history (CI logs, test runs): zero hits since creation. Not checked for `type-constraint` or `other`, which work by never firing; for those, try the edit `notes` says must fail | INFO: either the pattern is extinct (candidate for retirement) or the guard is miswired (verify against a known-bad sample) |

Findings route into the standard audit findings table; modify/retire decisions go through triage like any promotion decision. Retirement removes the `mechanized_guard` field and notes the retirement in the cluster's description — the occurrence history stays.

## Guard Modification Is In-Scope in Review Loops

When a review finding matches a cluster in `docs/reviews/recurring-patterns.yaml` that has (or plainly warrants) a mechanized guard, the fix is **two-part**: fix the instance, and update or create the guard so the next instance is caught mechanically. Fixing only the instance of a guarded pattern means the guard failed and is being left broken. This rule is consumed by `[sdlc-root]/process/review-fix-loop.md` Step C and `sdlc-review-code` Step 5a — guard edits (lint config, drift tests, CI wiring, or a design or type change confined to the finding's diff; § Choosing the Fix) are in-scope for fix dispatches without a separate approval cycle, subject to the same review loop as any other fix.

## Enforcement Floors

A guard does not need to be airtight to be worth having. A grep-based CI check is a legitimate floor when the full structural guard is expensive — e.g., failing CI on `KEEP IN SYNC` / `kept in sync manually` comments (see the Contract Safety Lens in `[sdlc-root]/process/review-lenses.md`: such a comment is itself a defect) enforces the single-source-of-truth rule even before a real drift test exists. Record floors with `type: ci-check` and note the limitation in `notes` so 6n doesn't mistake the floor for full coverage.

## Red Flags

| Thought | Reality |
|---------|---------|
| "The pattern is documented in the knowledge store, we're covered" | Agents forget; machines don't. 3+ recurrences after knowledge promotion is the signal to mechanize. |
| "I'll add the guard but skip the yaml field" | An unrecorded guard is invisible to Dimension 6n — it will rot unwatched. The field IS the registration. |
| "The guard exists, so the pattern is handled" | 6n exists because guards go stale: rules get disabled, tests get skipped, patterns mutate past the regex. |
| "Fixing the lint config is out of scope for this review" | If the finding matches a guarded cluster, the guard update is part of the fix, not an extra. |
| "A lint rule is the obvious guard" | Check structure and types first. A mistake the code can't express needs no rule to catch it, and a rule an agent can suppress is weaker than a module it can't reach. |
| "This pattern is judgment-heavy but I'll propose a lint rule anyway" | Name the machine-checkable signature or take the knowledge path. A noisy guard trains people to suppress guards. |
| "CD dismissed this candidate last cycle, but it's still at threshold — re-propose" | Dismissed ≠ excluded. If CD said "don't re-propose," record `mechanization_assessed: excluded` with the reason; if the fields are already set, skip it. Re-proposing an excluded cluster every cycle is the nag this field exists to end. |
| "The rule name is in the config — the guard is wired" | Presence ≠ enforcement. A rule at `off`/`warn`, a skipped test, a continue-on-error CI step, or a conditional registration that collapses at runtime all read as wired to a text grep. Parse the effective severity, or run the guard against a known-bad sample. |
