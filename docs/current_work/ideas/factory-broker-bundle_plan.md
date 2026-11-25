---
type: plan
slug: factory-broker-bundle
created: 2026-11-16
status: built and released (v2.7.0); the pilot and the debut are left (cross-checked 2026-11-25)
active_deliverable: null
related_files:
  - process/factory.md
  - process/production-gates.md
  - bundles/factory/tree/gates.py
  - skeleton/manifest.json
  - skills/sdlc-initialize/SKILL.md
  - skills/sdlc-migrate/SKILL.md
---

# Plan: the checks-only broker as an opt-in bundle (`factory-broker`)

## Progress (cross-checked 2026-11-25)

**Done:**
- P0 to P9, in 52f6b75 and 9788c03, which are on `origin/master` and first released in v2.7.0. The status line's "not pushed" was out of date.
- P10's client PR in the incubator (c9da4f5).
- Every plan default:
  - a non-empty rollback is refused;
  - a release service with no evidence is refused;
  - `"rollbacks": false` makes the plan guard refuse a rollback;
  - drift-scan, host-check and the diagnostics are generic;
  - the legacy ledger has a reader.

**Left:**
- **P10's pilot in the third project:** it's still on z-sdlc v2.4.1, with no adoption branch. It needs a migration, a PR with the host module and the `broker` block, the adoption, setup on the production machine, and one gate end to end.
- **The debut:** drop `pilot`, add a `bundle_debut` entry, and settle the name.

Until the third project adopts, the "rollback approved but never run" bug stays live in its own broker.

**Status:** pilot-ready (2026-11-17), committed (`52f6b75`, the outside review's fixes in `9788c03`), not pushed.
Built and reviewed: P0 to P9. The broker, its setup, seeds, tests (681 in an installed layout, also with every seed
filled in), `process/factory-broker.md` and its runbook, the manifest's pilot entry and the installers' `pilot` and
`requires.bundles`. Reviewed in three rounds (security, and correctness against D4 and the doc), then by Codex on
the bundle alone: no open critical or major finding, every fix with a test that fails without it. Codex's critical,
setup running the checkout's code as root, is the limit both setups document; the runbook says to run setup from a
fresh clone. Nothing has run under real systemd. The incubator's setup installs the shared client (CD merged its PR,
2026-11-17). **Next:** P10, the pilot in the third project, then the debut.

**This session ends at pilot-ready, not debuted.** The pilot needs the production machine and a PR in the third
project, and the bundle is offered to projects only after it passes (CD's answer 3).

## Decided (CD, 2026-11-16)

1. **The bundle-tree contract.** The bundle owns `production/factory_op.py`; migration updates it with the drift
   check. A project's host code is `production/factory_op_host.py`, a seed it owns. The generic file is the same in
   every project, so the bundle's tests prove it once.
2. **Root runs no project code.** Root's checks are data, a `broker` block in `ops.json` (under the digest). The host
   module loads only inside the sandboxed step: no IP network, only the egress allowlist.
3. **The whole bundle, piloted before it debuts.** The manifest lists it as a pilot (below); the `bundle_debut`
   entry comes after the third project's pilot passes.
4. **The request client moves into the factory bundle** (`host/factory-op-request`, the per-user client), one per
   host. **Correction to how that reaches the incubator:** `import.json` excludes `production/*` and
   `host/setup-production.sh`, so `--to-incubator` can't change how the incubator installs the client. Its
   `setup-production.sh` is the incubator's own file, so the change is a PR in the incubator, on CD's say, and a
   setup re-run on its host (CD's).

**Name:** `factory-broker` (chosen in the session; CD can rename it before the debut).

**Defaults the plan takes** (from the broker's map; CD can reverse any):
- Fail closed: the broker refuses a non-empty rollback up front, and the catalog's check refuses a release service
  declared with no evidence kind (D4 rule 15).
- The catalog can say `"rollbacks": false`, and the plan guard then refuses a rollback step (D4 rule 11's promise,
  kept at plan time). It lands in `gates.py` with this release's other change, so hosts re-run setup once.
- In v1 after all (changed at P1): the drift check (`drift-scan` became generic code over the host's deployments),
  host diagnostics (`verify-token` becomes a host module `DIAGNOSTICS` entry), and the passwordless `health` and
  `check` lines. P1 found them generic, so the third project keeps what it has.
- In v1: the legacy ledger reader, so the third project adopts without a re-baseline.

## The source

The third project's broker, exported to this session's scratchpad with `git archive` of its default branch as of
2026-11-11 (`production/factory_op.py` 3,102 lines, sha256 `ddac80b347627a23…`; `host/setup-production.sh` 1,211
lines), and the incubator's deploying broker for comparison. A reboot cleared the scratchpad once: the export was
taken again from the same commit (the hash matched), and the map and P1's files were rebuilt from the agents'
transcripts. The work itself lives in the repository's working tree, never only in the scratchpad. Nothing from either is committed here: no project name, host, id, UUID, client
hash, service name or design-decision id (the map's never-port list; P9's scan).

## The design

**Layout** (the factory bundle's `tree` and `seed` both go to `.github/factory`; this bundle's share no path with
them):

| Path | Owner | What |
|---|---|---|
| `production/factory_op.py` | bundle tree, digest | The generic checks-only broker: root commands, serve, rule 7 provenance, release gates, ledger and receipts, the sandbox, the egress proxy, the instance from its install path, the generic sandbox ops (`release-wait`, `health`, `http-check`, the `capture-state` frame), the legacy ledger reader |
| `production/tests/` | bundle tree | The bundle's tests on a fake host, including the fitness tests |
| `host/setup-production.sh` | bundle tree | Generic, instance-aware setup: the repository from a root-owned tier record, staged and re-executed |
| `host/factory-op-request` | **factory** bundle tree | The per-user request client, one per host for every tier |
| `production/factory_op_host.py` | seed, digest | The project's host module, seeded as a stub where every primitive fails closed |
| `production/ops.example.json` | seed | The catalog to start from: the bundle's operations and the `broker` block. **Not `ops.json`:** a project has a production tier when `production/ops.json` exists (the plan and publish guards, `bootstrap.py`), so the install stays inert until the enable runbook writes it |
| `production/config.json` | seed | Repository, branches, approvers, the App's id, content patterns; the host's ids block, read only by the host module |
| `host/production.conf` | seed | The instance, the agent login, the runner's name and group, LAN DNS, probe ports |

**The host contract** (`factory_op_host.py`, loaded only by `op_main` after its not-root check, by explicit path,
never through `sys.path`; it gets the broker's own classes through `ctx`):

```
client(ctx)                                the host API client from the step's token, read-only
preflight(ctx)                             the credential is for the configured project; the config's host block is valid
deployments(ctx, svc) -> [Deployment]      newest first; status waiting|success|skipped|failed|crashed
serving(ctx, svc) -> Deployment | None     the newest successful deployment
reports(ctx, svc, deployment_id) -> bool   the running service says it is this deployment (Unavailable: no usable answer)
heartbeat(ctx, svc, deployment_id, patient) -> (started, written) | None   (StepFailed when definitive)
capture(ctx) -> {output: value}            <svc>_commit and <svc>_settled per checked service, plus every recorded
                                           and invariant output
OPS = {name: fn}                           host-only catalog operations (a backup, say)
```

**The `broker` block** (in `ops.json`, digest-covered, read by root, the egress proxy and setup without running
project code): `egress`, `http_targets`, `secrets`, `op_secrets`, `services` (release, checked, evidence),
`heartbeat_ttl_s`, `release_wait_phases`, `recorded`, `invariants`, `python`, `host_locks`, and, from P1,
`host_ops` and `internal_ops`. P1 froze it (with `latest(ctx)` added to the contract, a `branch` on each
deployment, and content patterns moved into `services`); `process/factory-broker.md` carries the reference.
`release_gates` may be false while the project enables the broker, which then refuses release-kind requests;
`rollbacks` must be false.

**The digest** (`gates.py`): `BROKER_MODULES = ("factory_op_host.py",)`, hashed by exact name when present, in the
repository and on the host. The set of names the incubator's host hashes doesn't change; its digest moves once,
because `gates.py`'s own bytes are in it, as every `gates.py` change does.

**The instance** comes from the install path (`/usr/local/lib/factory-prod[-<instance>]`), never rendered into the
file, so the repository's copy and the host's hash the same. Other tiers on the host are discovered
(`/etc/factory-prod*/config.json`), never named.

**Setup's trust root:** the repository comes from a root-owned tier record written on the first run, as the factory
bundle's `host/setup.sh` does, never from the checkout.

**The pilot path.** The manifest lists the bundle with `"pilot": true`: `sdlc-initialize` doesn't offer a pilot
bundle, and `sdlc-migrate` offers bundles only through `bundle_debut` entries, which it has none of yet. The
third project adopts by hand, following the bundle's enable runbook: it writes its host module and `broker` block
first, in its own PR; then copies the bundle's tree files at this release, adds the bundle to `installed_bundles`
and records the files' hashes in `installed_files`, so its next migration refreshes them normally; then re-runs
setup. The debut drops `pilot` and adds the `bundle_debut` entry; a project that adopted by hand then shows no
difference in § 4.7's adopt.

**Never offered to the incubator,** whose own deploying broker sits at `production/factory_op.py`. After the debut,
§ 4.7's tree-predecessor adopt would show the difference and only CD's skip would protect it, so the offer's text
says it's for a checks-only broker and not a broker that deploys.

## Phases

Every agent is told: the working tree holds uncommitted work; no stash, checkout or reset, and edit only the files
its brief names.

- **P0. Commit what's there** (CD's call), so the broker's changes to `gates.py`, `factory.md`, the manifest and the
  install skills don't mix with this session's other work.
- **P1. Freeze the contract against the real case.** In the scratchpad, never this repository: a scratch host module
  for the third project implementing the contract from its broker (capture, the release-wait and health primitives,
  its invariants and recorded outputs), its `broker` block, and one legacy ledger record read. Report every root
  check of its broker the declared data can't express. **Check:** that list is empty, or each item has a decided
  way in; the contract and block schema are written here, frozen.
- **P2. The tightest tests first.** A poisoned host module that raises on import: every root command still runs.
  The repository's and the installed digest match, with and without `factory_op_host.py`. `BROKER_MODULES` equals
  setup's stage and install lists. A non-empty rollback is refused; so is a release service with no evidence kind.
  **Check:** they exist and fail for the right reason before P3 and P4.
- **P3. `gates.py` and the client.** `BROKER_MODULES` in both digest functions; the catalog's optional `rollbacks`
  key and the plan guard's refusal; `host/factory-op-request` in the factory bundle's tree. **Check:** the factory's
  tests pass, and `zsdlc-import-factory --prove` still passes.
- **P4. The generic broker** (`factory_op.py`), one owner, sequential: from the third project's, its host parts moved
  to declared data or the host module's contract, the instance from the install path, the host module loaded only
  in `op_main`, the legacy reader, the rollback refusal. **Check:** P2's tests pass, and no line of it names a
  project, host or host vendor.
- **P5. Generic setup** (`setup-production.sh`), in parallel with P4: names from the instance, the tier record,
  other tiers discovered, the client from the factory bundle's path, the host module staged and installed, egress
  and secrets from the `broker` block. **Check:** its rendering and staging tests pass with two instances.
- **P6. The tests on a fake host:** `fake_host.py` in place of the third project's platform mock, and the generic
  tests carried over (release gates, provenance, execute and records, baseline, the sandbox, egress, health,
  release-wait, http-check, serve). **Check:** they pass; each carried-over test still fails when the code it
  guards is broken (spot-checked by mutation).
- **P7. Seeds:** the stub host module, `ops.example.json`, `config.json`, `production.conf`, and a catalog test the
  project's CI runs (required operations present, their parameters exact, timeouts at or above the phases' sum,
  `gate_overhead_s` and `step_margin_s` at or above the broker's own). **Check:** an empty project with both
  bundles installs inert (no `ops.json`, so no tier), and the catalog test fails on the example until it's filled.
- **P8. Docs and the framework.** `process/factory-broker.md`: the design, its `enable` runbook (host module,
  `broker` block, `ops.json`, setup on the host, a first `baseline`, release gates on last), and `## After
  migrating`. `factory.md` D4 rule 16 (the factory bundle installs no tier; this bundle does, for a checks-only
  host), the manifest entry (`requires` the factory bundle, `pilot`), `sdlc-initialize` skipping a pilot bundle
  and checking `requires.bundles`, the changelog. Checked against the other bundles: the factory's CODEOWNERS
  guard and seeded test, `bootstrap.py`, `ci_audit.py`, and the project's CI running `production/tests`.
  **Check:** the repository's tests and consistency checks pass.
- **P9. Proof and review.** An empty project with `factory` and `factory-broker` installed runs both test sets;
  `--prove` passes; a deny-list scan built from the map's never-port table finds nothing in the bundle. Review:
  security and implementation reviewers on the bundle's code, and Codex on the bundle's code alone (never the third
  project's source or the map). **Check:** no open critical or major finding.
- **P10. Outside this session (CD):** the incubator's PR for the client (merged 2026-11-17); the pilot in the third project (its host
  module and `broker` block PR, the hand adoption, setup on the production machine, a gate end to end); then the
  debut.

## Findings to carry

**An ops gate's rollback is approved, then never run (the third project's live broker).** The plan guard accepts a
read operation as an ops gate's rollback step, and the gate request tells CD those steps run; the broker signs
`rollback: []`, which `check_receipt` accepts as a prefix. Only read operations can be rollback steps in its
catalog, so nothing went unundone, but D4 rule 11's promise breaks. The generic broker refuses a non-empty rollback
(P4), and `"rollbacks": false` lets the plan guard refuse it first (P3).

**The ledger.** Without the legacy reader, the third project's old records stop counting: `baseline` falls back to
the release branch's start, and CD re-accepts every hotfix accepted before. The reader maps an old signed record's
fields to the new shape with no host code.
