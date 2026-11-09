---
type: handoff
slug: factory-enablement-upstream
created: 2026-11-09
status: pending
trigger: idea
recommended_next_skill: sdlc-lite-plan
source_session_summary: "The third project's factory install (a project on a PaaS, planning through an MCP service, a checks-only production tier) was reviewed end to end for CD, who asked for repeatable procedure. The runbook (process/factory-runbook.md) covers the procedure; this lists what it found worth building upstream, none of it built yet."
active_deliverable: null
related_files:
  - process/factory-runbook.md
  - process/factory.md
  - bundles/factory/tree/gates.py
  - bundles/factory/tree/implement_guard.py
  - bundles/factory/tree/host/setup.sh
  - bundles/factory/tree/host/setup-ci.sh
  - bundles/factory/tree/bootstrap.py
  - bundles/factory/seed/factory.json
  - bundles/factory/seed/tests/test_codeowners.py
---

# Handoff: what the third project's install found worth building upstream

## Why this is a handoff

The third project's install took about 83 hours, of which the twelve Enablement steps took 2.5. The
runbook now covers the procedure: the day-one form, the inventory, the critical path with its
checks, and what to build when no template exists. These are the pieces a fourth project would
otherwise build again, or that the install showed missing. Each is generic: the project-specific
parts stay the project's. None is built; CD decides which, and in what order.

## Candidates, roughly by how much a next install saves

1. **A checks-only broker skeleton** for a release-branch project on a host that deploys a branch
   itself. The project built one from the incubator's deploying broker, and most of it carried over
   as design, not code. Generic:
   - the rule 7 provenance check on the release branch;
   - a `release-wait` operation with rule 15's two-read evidence;
   - signed receipts and the ledger;
   - sandboxed steps;
   - an instance-suffixed second tier;
   - the per-user request client;
   - setup's root-owned fetch.

   The host's API client, its documents and its ids stay the project's.
2. **A deny-by-default planning reader generator** that works from the database's catalog, not an
   ORM. The incubator's walks Django models. The project had to write its own for SQLAlchemy, with
   column rules, overrides and a role verifier, and review found its first version allowed unknown
   short text columns and `_id` names by default.
3. **A CI audit script** for Enablement step 10. It should list every workflow's triggers, each secret
   it references and whether that secret exists (by name), its checkouts' `persist-credentials`, and
   its runners. Step 10 states the rule but gives no procedure, and the project's first reading of its
   CI was wrong (a referenced secret that didn't exist).
4. **A release provenance alarm as a bundle workflow** for release-branch projects. It flags a commit
   on the release branch that didn't arrive through an approved PR. It needs an event trigger that
   runs the default branch's copy (a `push` trigger runs the pushed commit's), plus an outside
   heartbeat, since GitHub starts most scheduled runs late or not at all.
5. **A seeded CODEOWNERS test that imports the guard's lists** instead of copying them. Seeds aren't
   updated by migrations, so the project's copy drifted at the first release that changed the lists.
6. **Per-stack `review.focus` rule packs** beside the seed's Django and ASP.NET Core ones, starting
   with FastAPI and SQLAlchemy (auth files, raw SQL including quoted-string SQL, timed regexes).
7. **A drill checklist for any production tier:** restore, rollback, fix-forward, and a hung pre-deploy
   step, run before the first real release.
8. **`bootstrap.py` checks the default branch's ruleset bypass mode too.** It checks the release
   branch's today, and the copied default-branch ruleset had mode "always".
9. **Gate-plan checks the project added locally:**
   - the plan guard sums a plan's gate time budgets against the gate job's limit;
   - the guard refuses a gate with no steps;
   - `check_plan` checks `release_gates` before it skips a release gate with no `gate-ops` block.
     Today such a gate passes the plan guard and is refused only at the gate request, before
     anything is pinned.
10. **Shellcheck warnings in the host setup:** `setup.sh`'s empty `local` assignment (SC1007), and
    `setup-ci.sh`'s variables that `setup.sh` sets before sourcing it (SC2154, and SC2148 for its
    missing shebang).
11. **Knowledge:** "services deployed concurrently from one merge need contracts that stay add-only
    for a release" (schemas and background-job arguments), for the architecture knowledge store.

## Process proposals for CD

Not framework files, so CD decides them directly:
- **Agent identity:** whether agent sessions keep using CD's GitHub login, in which case CD can't
  approve their PRs and merges each with the ruleset bypass, or get a fine-grained token of their own.
- **A skill that walks the runbook** in a project's session: the form, the inventory agent, the
  critical path's checks. Worth it once the runbook has been through a fourth install unchanged.
