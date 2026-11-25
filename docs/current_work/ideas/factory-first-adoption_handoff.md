---
type: handoff
slug: factory-first-adoption
created: 2026-10-12
status: partly done: the second-organization run is left (cross-checked 2026-11-25)
trigger: deferred-work
recommended_next_skill: sdlc-lite-plan
source_session_summary: "The factory bundle was made usable by any organization (placeholders, App creation, echo service, host setup for several organizations, Enablement from zero). Its from-zero path hasn't run end to end outside the incubator; CD chose to prove it with the first real adoption, when that organization is ready, not with a throwaway repository"
active_deliverable: null
related_files:
  - process/factory.md
  - bundles/factory/tree/create_app.py
  - bundles/factory/tree/host/setup.sh
  - bundles/factory/tree/bootstrap.py
  - bundles/factory/seed/factory.json
  - bundles/factory/seed/host/host.conf
---

# Handoff: The factory's first adoption outside the incubator proves Enablement

## Progress (cross-checked 2026-11-25)

Two later adoptions, the pilot project and the third project, were in the incubator's own organization. They reused its App, echo service and runner pools, so from-zero Enablement in a second organization, this note's core ask, is still untested. Enablement now has 14 steps.

**Done in the organization:**
- **Stack profiles:** `dotnet-node` (v2.1.0) and `python-uv-node` (v2.3.0).
- **The job image's first publish:** GHCR's `denied` is now re-run (Enablement step 3).
- **Smoke:** it passed on every job in both projects.
- **The open question on a check script:** answered by `bootstrap.py` (steps 2 to 9) and the `factory-enablement` runbook under `sdlc-run-runbook`.
- **The production tier left out of scope:** since built as the `factory-broker` bundle, still a pilot.

**Partly done:** `host/setup.sh` ran for real on the runner and CI hosts, but its `RUNNER_INSTANCE` path for a second organization never ran.

**Left:**
- `create_app.py` against GitHub (its manifest sends no `hook_attributes`);
- a runner group on a Team-plan organization;
- the echo service's `wrangler deploy` command, since the organization's Worker was deployed by hand;
- smoke in a second organization.

## Why this is a handoff

`process/factory.md` § Enablement now takes an organization from nothing to a running factory, with a tool or file in the bundle for each step. The pieces are tested on their own (the import proof installs the bundle with its placeholders into an empty project, and every template renders and every test passes), but nobody has followed Enablement from step 1 to step 11 in an organization other than the incubator's. CD decided (2026-10-12) not to do that in a throwaway repository: the first organization that adopts the factory for a real project does it, and everything it creates stays.

## What needs to happen

When that organization is ready, follow Enablement literally, steps 1 to 11, in its first real repository. Every place the text doesn't carry you is a fix: a documentation gap goes into `process/factory.md`; a bug goes straight into `bundles/factory/tree/` (the pilot rule in `CLAUDE.md`), and `zsdlc-import-factory --to-incubator` copies it to the incubator.

Watch these, which no test has exercised yet:

1. **`create_app.py` against GitHub.** The manifest has no `hook_attributes`; GitHub's documentation marks `hook_attributes.url` as required inside that object, so the form may refuse a manifest without one. If it does, send `hook_attributes: {"url": ..., "active": false}`.
2. **`host/setup.sh`, run for real.** Its settings, names and ownership guard are tested without root; the root run (users, firewall, rootless Docker, the isolation test, registration) has only ever run in its earlier, single-organization form. On a host that already runs another organization's runners, set `RUNNER_INSTANCE` in `host.conf`, and keep the new organization's limits within what the host can spare.
3. **The runner group on GitHub Team.** `bootstrap.py --apply` creates `factory-pool` with selected repositories and selected workflows; GitHub documents extra runner groups on Team, but not clearly the selected-workflows restriction.
4. **The echo service's deploy command** in step 4 (`wrangler deploy ...`) is an example, not a tested command.
5. **The job image's first run.** The install's own push runs `factory-image` against the placeholder repository and fails; step 3 says so. The run after `image.repository` is set must publish, and the image must be pullable by the repository's jobs.
6. **Smoke**, all eight jobs, in an organization that isn't the incubator's.

## Before starting

- **A stack profile that fits the project.** The bundle's one profile, `python-node`, is Django and Vite with npm in one repository (§ Stack Profiles). A project on pnpm, a single-language repository, or another stack needs a profile of its own first, and the interface's first generalization (`agent_job.sh` passes `stack.python` and `stack.node`).
- **The organization's plan:** GitHub Team or above for a private repository; the production tier's required reviewer on a private repository needs Enterprise (step 1). Without it the factory runs with no production gates (D4 rule 16).
- **The bundle as published:** install from z-sdlc's public source, not a local copy, so the proof is of what adopters get.

## Open questions

- Should a small Enablement check script (beyond `bootstrap.py`) report which steps are done, for an adopter working through them over several sessions?

## Out of scope

- The production tier for an adopter (D4 rule 16): a generic broker and host setup is separate work.
