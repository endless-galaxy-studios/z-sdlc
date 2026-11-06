# Production Gates

How a plan handles work that touches production: deploys, migrations on a shared database, restarts, backups, and checks against a live system. That work happens only in **gates**, stops between phases that CD approves. Phases never touch production.

The rule exists so that production work is always visible, approved and reversible. In one project, a plan mixed a deploy into a phase ("Phase 3: code + Deploy step 1"), and nothing that runs plans unattended could tell which steps needed production.

## What a Gate Is

A gate sits between two phases. It holds the production steps the plan needs at that point, and nothing else: no code changes, no reviews. Each gate is done by CD, or by the project's production runner after CD approves it (§ Operations Catalog). An agent never does a gate's steps.

**Gates aren't phases.** They don't count toward a plan's phase limit (7 for `sdlc-plan`, 4 for `sdlc-lite-plan`).

**The last item in a plan is always a phase.** It reads the last gate's results, writes the records and sets the catalog to Complete. A plan that ends in a live check still has a closing phase.

**No phase after a gate starts before the gate is done,** whether or not its Depends On names the gate.

**Status:** approving a deploy gate is CD's authorization to deploy before the deliverable is Validated (`[sdlc-root]/process/deliverable_lifecycle.md` § Deployed). The deliverable stays In Progress until the closing phase.

**Gates aren't prerequisites.** A wait on another deliverable is a `Depends on` entry (`[sdlc-root]/process/deliverable_lifecycle.md` § Dependencies), not a gate.

## The Gate Section

A gate is its own section in the plan, between the phases it separates, and its own row in the Phase Dependencies table (`G1 | Phase 3 | CD | —`). A phase that needs the gate's results depends on it (`Phase 4 | G1`).

````markdown
### Gate G1: [what happens in production, in plain words]

**After:** Phase 3. **Changes production:** yes | no (read-only).
**Why here:** [why this happens between these phases and not later]
**Preconditions:** [what must be true first: a backup within 24 hours, no deploy in flight]
**Runbook:**
- [ ] [each step, with the exact command or operation, in order]
**Report back:** `field`: [what it is and which phase uses it]; ...
**Rollback:** [how to undo it, or "none: read-only"]

```gate-ops
{"steps": [{"op": "backup-now"}, {"id": "deploy", "op": "deploy", "with": {"sha": "${head}"}}],
 "rollback": [{"op": "deploy", "with": {"sha": "${steps.deploy.previous_sha}"}}]}
```
````

- **Runbook:** what CD would do by hand. Exact commands, never "deploy as usual".
- **Report back:** the values later phases need from the gate: snapshot identities, hashes, timestamps, versions. A later phase cites them as `G1.field`. A gate whose results nothing reads still reports its outcome.
- **Rollback:** required when the gate changes production. Schema changes are expand-only, so a rollback can redeploy the previous code and keep the schema.
- **`gate-ops` block:** only when the project has an operations catalog (§ Operations Catalog). Otherwise leave it out: the runbook is the gate.

## Before a Gate: Review, Then Commit

**A gate never ships unreviewed work.** When execution reaches a gate, it runs the review loop (`[sdlc-root]/process/review-fix-loop.md`) over the work since the previous gate, or since the start, with the same exit bar and round cap as the completion review. Then it commits that work. A loop that ends with a critical or major finding open escalates instead of reaching the gate. The completion review at the end covers only the work after the last gate.

## At a Gate

**Interactive run:** present the gate (runbook, report-back fields, rollback) as a completed message, then ask with `AskUserQuestion` whether CD will do it or approve the runner to. Once it's done, ask for the report-back values or the runner's result. If a step uses `${head}`, push the branch first so the runner can reach that commit. Record them in the result doc's Gates section, then continue with the next phase. If the gate fails, CD decides: roll back, retry, or stop. A failed gate is never worked around inside a phase.

**Headless run:** stop before the gate with status `awaiting-approval` (the caller publishes the commits before it asks for the gate). The gate is the action plan awaiting approval: name it in `stage` (`sdlc-execute — after gate G1`), and in a `gate` field if the caller's schema has one. List its steps under `outbound`. The run never does a gate's steps itself: they are live-system changes (`[sdlc-root]/process/headless-mode.md` § Outward Actions Go to the Caller).

**Headless restart after a gate:** the caller passes the gate's result. If the gate succeeded and every report-back field is present, record the result in the result doc's Gates section and continue with the next phase. Otherwise stop with `needs-input`, saying what's missing or what failed.

## Operations Catalog

A project with a production runner (in the software factory, a runner that runs gates after CD approves them) keeps an **operations catalog**: the only operations the runner can do, each a reviewed script with typed parameters. The project's `CLAUDE.md` names the catalog's path. A plan's gates then carry a `gate-ops` block naming only catalog operations.

- **Parameters** are typed: the catalog gives each one a pattern its value must match. A value is a literal, or a placeholder resolved when CD is asked to approve:
  - `${head}`: the commit the execution branch is at;
  - `${G<n>.<field>}`: an earlier gate's report-back value;
  - in `rollback` only, `${steps.<id>.<field>}`: a value from a step of the same run, resolved when the runner runs it.
- **Two approvals.** Approving the plan approves what each gate may do. Approving the gate, when execution reaches it, approves doing it now with the values filled in. The runner runs exactly what CD approved, once.
- **Rollback steps** in the block run automatically when a step fails, and only those.
- **No agent runs operations.** Agents write the plan and the code; the runner does the gate.
- The factory's catalog format, runner and approval rules are in its design rules (D4).

Without a catalog, the runbook is the whole gate, and CD does it.

## With a Release Branch

A project whose production follows a release branch (`factory.json`'s `release.branch`, `[sdlc-root]/process/factory.md` D4 rule 13) deploys only when CD merges a PR into that branch: every host serving production deploys it by itself. A plan there deploys in either of two ways, or both.

**Partway through, in a release gate.** A gate with a `**Release:**` line deploys the work up to it. When execution reaches it, the factory pins that commit and opens a release PR from it into the release branch, and CD's merge is the deploy. The gate then checks production as any gate does, and the next phase starts once it's done:

````markdown
### Gate G1: [what reaches production, in plain words]

**After:** Phase 2. **Changes production:** yes.
**Release:** [what production needs from the work so far, in one line]
**Why here:** [why production needs it before the next phase]
**Preconditions:** [what must be true first]
**Runbook:**
- [ ] Merge the release PR the factory opens; merging deploys.
- [ ] Approve the gate run that follows; it checks production runs the release.
**Report back:** `field`: [what it is and which phase uses it]; ...
**Rollback:** through the host, then a revert PR into the release branch and a `baseline`; after a migration, fix forward instead (expand-only, never reverted).

```gate-ops
{"steps": [{"op": "health"}]}
```
````

- **Its `gate-ops` block is optional** and holds only read operations, run after the deploy. It has no `rollback`: the broker can't deploy, so a failed release gate is CD's: rolled back through the host and a revert, or, after a migration, fixed forward.
- **Merging deploys everything behind the gate's commit:** the default branch's commits the release branch doesn't have yet go too. The release PR lists them.

**When the work is done, in a Release section,** after its phases:

````markdown
### Release

**Why:** [what production needs from this deliverable, in one line]
````

The plan's PR shows the release. When CD merges the plan's execution PR, the factory opens a release PR from the default branch into the release branch, or comments on the one already open, and merging that PR is the deploy. It carries only what the plan's release gates haven't.

The plan's other gates hold only what isn't a deploy (a backup, a live check). A release gate or a Release section in a project without a release branch is refused: there, a deploy is a gate's operation.

## Red Flags

| Thought | Reality |
|---|---|
| "The deploy is one command; I'll fold it into the phase" | Production work goes in a gate, so it is approved and can be rolled back. |
| "The phase can run the migration on production; it's tested" | Phases never touch production. Put the migration in a gate. |
| "The gate's code passed the phase checks, so it's ready to ship" | A gate needs the review loop over the work since the last gate first. |
| "Headless, but the gate is read-only, so I'll run it" | A headless run never does a gate's steps. Stop with `awaiting-approval`. |
| "The gate failed; the next phase can work around it" | A failed gate stops the run. CD decides. |
| "The plan ends with the post-deploy check" | The last item is a phase that writes the records. |
| "This needs 8 phases plus 2 gates; time to split" | Gates don't count toward the phase limit. Count the phases. |

## Integration

- **Templates:** `[sdlc-root]/templates/planning_template.md`, `[sdlc-root]/templates/sdlc_lite_plan_template.md` (the gate section), and the result templates (the Gates section)
- **Planning:** `sdlc-plan`, `sdlc-lite-plan` put production work in gates
- **Execution:** `sdlc-execute`, `sdlc-lite-execute` review and commit before a gate, then stop at it
- **Headless rules:** `[sdlc-root]/process/headless-mode.md` (approval gates; outward actions)
- **Dependencies:** `[sdlc-root]/process/deliverable_lifecycle.md` § Dependencies
