# Bundles

The z-sdlc core is deliberately small. Bundles are opt-in capabilities layered on top of it: each one is installed only if you accept it, and each is **inert until configured**, so installing one without setting it up is a valid resting state.

| Bundle | What it is for | Needs |
|---|---|---|
| [`design`](#design) | Design options before UI work | Nothing |
| [`github-provenance`](#github-provenance) | GitHub issues and a board that mirror your deliverables | `gh` CLI, a GitHub repo |
| [`factory`](#factory) | Unattended, issue-driven agent stages with human gates | A GitHub organization, self-hosted Linux runners |

The authoritative list, with every file each bundle installs, is `bundles` in [`skeleton/manifest.json`](../skeleton/manifest.json).

## design

A single skill, `sdlc-design-consult`. Hand it screenshots, references and codebase context and it returns 2 to 3 distinct design options grounded in design theory, with iterative refinement until you settle on a direction. It produces direction only, and implementation then goes through the normal planning and execution skills. Use it when a component, layout or interaction flow needs visual exploration before anyone writes code.

## github-provenance

The catalog in `docs/_index.md` stays the source of truth. This bundle projects it into GitHub so people who never open the repo's markdown can follow along.

- A GitHub issue is created when a deliverable ID is minted.
- Lifecycle checkpoints (planned, executing, reviewed, archived) are commented on the issue, with SHA-pinned links.
- Cards move across a Projects v2 board, if you configure one.
- `sdlc-audit` reconciles the issues against the catalog and flags drift. If they disagree, the catalog wins.
- A failure to reach GitHub never blocks the SDLC.

The policy lives in [`process/github-checkpoints.md`](../process/github-checkpoints.md); the mechanics live in the `sdlc-manage-github` skill. The bundle also carries *fragments*: short checkpoint sections injected into eight framework files (the plan, execute, handoff, archive and audit skills and the compliance auditor). It is switched on by setting `enabled: true` in the policy doc's config block as the last step of its Enablement section.

## factory

A software factory built on the same skills, agents, review lenses and knowledge layer as the rest of z-sdlc. An issue goes in, and a draft PR comes out the other side, with a human approving every plan, every merge and every production step.

**The stages:**

- **triage** reads an issue, decides what it is and which tier it needs, and asks questions when it can't tell.
- **plan and spec** produce a reviewed spec and plan as a PR, against real data and services where configured.
- **implement** executes an approved plan through the normal review loop and opens a draft PR.
- **revise** applies review feedback, with a cap on rounds before it escalates to a person.
- **execute with production gates** runs reviewed production operations, each one approved by a person.
- **improve** is a weekly loop that reads what the human did to the factory's output (change requests, closed PRs, answers, label overrides) and proposes improvements to the factory.

**Design decisions** ([`process/factory.md`](../process/factory.md) holds the rules and the options that were rejected):

- **Labels hold state, and dispatch advances it.** Stages are chained by workflow dispatch from a writer job, not by labels a bot sets.
- **Agents hold no write credential.** The agent job is read-only and returns structured output. A separate job with no agent validates that output and does the writing. A prompt injection therefore has no write channel to hijack.
- **Production is run by a deterministic broker, not an agent.** A person approves each gate through GitHub's own deployment review, which nobody can edit or forge.
- **Anything that needs a person stops the run.** An unattended run never guesses past a decision ([`process/headless-mode.md`](../process/headless-mode.md)).
- **The factory learns from correction.** The improve loop is a deterministic harvest, a read-only analysis and a deterministic report, so no agent can rewrite the factory's own skills unreviewed.

**What it installs:** three headless skills (`sdlc-triage`, `sdlc-implement`, `sdlc-revise`), the process doc, and the factory's scripts, guards, schemas, sandbox settings and workflow templates under `.github/factory/`. The workflows in `.github/workflows/factory-*.yml` are *rendered* from the templates and the project's `factory.json`, and CI refuses a hand edit.

**Requirements and limits of this version:** a GitHub organization (and GitHub Team or above for a private repository), Linux runner hosts with systemd, nftables and rootless Docker, the project's SDLC root at `ops/sdlc`, and one of the shipped stack profiles (`python-node` or `dotnet-node`) or one you write. The production tier is per project and is not part of the bundle. Setup is the ordered Enablement section of the process doc, and `bootstrap.py` checks each step and changes nothing unless told to.

The factory is incubated in a separate private project and imported here, so improvements to the factory itself start there. Fixes found in a project that installed the bundle are made here and then handed back.

## How bundles work

**Installing.** `sdlc-initialize` offers the bundles during setup. `sdlc-migrate` offers a newly debuted bundle once and never removes files a project already has. Accepted bundles are recorded in the project's `.sdlc-manifest.json`.

**What a bundle can contain**, as declared in the manifest:

| Part | Meaning | Ownership after install |
|---|---|---|
| `skills`, `process` | Installed to `.claude/skills/` and `[sdlc-root]/process/` | z-sdlc: refreshed on every migration |
| `fragments` | Short sections injected into framework files inside `BUNDLE-SECTION` markers | z-sdlc: re-injected on every migration; hand edits are discarded |
| `tree` | A directory copied to the project (the factory's `.github/factory/`) | z-sdlc: refreshed on every migration |
| `seed` | Files written only where absent (settings, policy, notes) | The project: never overwritten |
| `render` | A command run after the files are in place | Run on install and on every migration |
| `requires` | A precondition (for example the SDLC root's location) | Install refuses if it isn't met |

**Bundles share a project.** A bundle that touches something a project's GitHub or configuration holds (labels, workflows, environments, settings) is checked against every other bundle's rules over the same thing, and each side's doc says how they meet. Before adding one, grep the other bundles' fragments and process docs.

## Adding or changing a bundle

Bundle skills and process docs live in the normal `skills/` and `process/` locations and are listed under `bundles` in the manifest. What belongs under `bundles/<name>/` is limited to `fragments/`, `tree/` and `seed/`. Changes follow the repo's usual rules: update the manifest, log the change in `process/sdlc_changelog.md`, and add a `skeleton/contract_changes.yaml` entry when a bundle debuts or its manifest fields change. The consistency checks in the repo's `CLAUDE.md` apply.
