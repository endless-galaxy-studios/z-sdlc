# The Checks-Only Production Broker (`factory-broker` bundle)

The `factory-broker` bundle gives a factory project a production broker (`[sdlc-root]/process/factory.md` § D4)
without writing one. It is for a project on the release branch model (D4 rule 13) whose host deploys the release
branch by itself, so the broker only checks: provenance, the release's evidence, the recorded state, typed reads
and the host's own operations, such as a backup. It deploys nothing and rolls nothing back.

**Status: pilot.** The bundle is being proved in one project before any is offered it: `sdlc-initialize` doesn't
offer a bundle marked `pilot`, and it has no `bundle_debut` entry yet. § Adopting it by hand says how the pilot
project installs it.

**It requires the `factory` bundle,** whose `gates.py`, `ed25519.py` and request client it uses.

**It's not for a broker that deploys** (the fallback's execution-PR gates, or a broker that follows the release
branch on a host that can't, D4 rule 13). The factory's incubator keeps its own deploying broker at the same path,
`production/factory_op.py`: never install this bundle there.

## What it installs

| Path (under `.github/factory/`) | Whose | What |
|---|---|---|
| `production/factory_op.py` | the bundle's (migration updates it) | The broker: root commands, the socket server, provenance (D4 rule 7), release gates, the ledger and signed receipts, the sandbox, the egress proxy, and the generic operations (`release-wait`, `health`, `http-check`, `capture-state`, `drift-scan`, `host-check`) |
| `production/tests/` | the bundle's | The broker's tests, on a fake host. The project's CI runs them (`python3 -I -m unittest discover -s .github/factory/production/tests`) |
| `host/setup-production.sh` | the bundle's | The host's setup, run by CD as root: users, firewall, the broker, its units, the runner, acceptance checks |
| `production/factory_op_host.py` | the project's (a seed) | The host module: the project's code for its host, run only inside the broker's sandboxed steps. Seeded as a stub where every primitive fails closed |
| `production/ops.example.json` | the project's (a seed) | The catalog to start from: the generic operations and the `broker` block. A project has a production tier once `production/ops.json` exists (D4 rule 16), so the install stays inert until the enable runbook writes it |
| `production/config.json` | the project's (a seed) | The repository, branches, approvers, the App's id, and the host's ids block, which only the host module reads |
| `host/production.conf` | the project's (a seed) | The instance, the agent login, the runner's name and group, LAN DNS, probe ports |

The request client (`host/factory-op-request`) is the factory bundle's: one per host serves every tier.

## How it works

**Root runs no project code.** Root's commands read `config.json`'s generic keys, `ops.json` (the catalog and its
`broker` block) and the ledger, and never import the host module. Only a sandboxed step loads it, as the operator
user, with no IP network and only the egress allowlist, by explicit path. Every check root makes about the host is
generic code over the typed outputs a step returns, or data the `broker` block declares. A hostile or broken host
module can read from inside the sandbox, reach the declared egress hosts, and return typed outputs that root checks
against the catalog's patterns; nothing more.

**What a step can reach.** A step's `/run` is an allowlist: an empty read-only filesystem holding only the egress
proxy's socket and the step's own directory, so the machine's usual local sockets there (the journal, name
services, D-Bus and the rest) are out of reach. It has its own IPC namespace, no `/dev/shm` or `/dev/mqueue`, no IP
network, and other tiers' directories (their libraries included) are hidden. The egress proxy reaches only the
declared hosts on port 443, never the production machine itself. A socket elsewhere on the machine (under `/var`,
`/srv` or `/opt`, say a database's) is reachable when its file mode lets the operator user in, so keep other
services' sockets closed to other users; setup's probe checks only `/run`. This needs systemd 248 or newer: setup
refuses an older one (Debian 11 and Ubuntu 20.04 among them).

**The agent login** may run `check` and `health` without a password; `health` runs at most once a minute,
counted from when it starts. Every other command asks for the password each time.

**A step never outlives its broker.** Every command that runs steps, and `resolve`, first asks systemd whether one of
this tier's step units is still running, and refuses, naming it, while one is: a broker killed mid-step leaves its
step running until the step's own time limit, and nothing may start beside it or close its run. Wait for it, or stop
the unit (`systemctl stop <unit>`), then try again. A step that times out returns only once its unit is gone.

**Earlier gates count only as the plan defines them now:** the same title, block and kind, so a gate the plan has
since made a release gate, or stopped making one, runs again (D4 rule 7).

**The digest** (D4 rule 6) covers the host module by name (`gates.BROKER_MODULES`) and, for a broker with a host
module, `config.json`, with `gates.py`, `ed25519.py`, `factory_op.py`, `ops.json` and any `ops/*.sh`. Changing any of
them means re-running setup on the host, or every gate is refused; a gate also stops if the installed package changes
while it runs. Setup installs `config.json` twice from the same fetched copy: in the library, where the broker reads
and the digest hashes it, and in `/etc/<tier>/`, which only other tiers' setups read, never the broker; `check`
reports when the two differ. The library must hold the host module, or every command refuses, and setup refuses a
default branch without one. A command reads the installed package once, from the same bytes it hashes, and refuses,
to be run again, when setup changed the package while it loaded or while it waited for the lock (a gate's refusal is
signed; `factory:gate-retry` asks for it again). A root command stopped by any signal that would end it unwinds
cleanly: it stops its step and releases what it holds.

**The instance comes from the install path.** The first tier on a host is `factory-prod`; each later one has its
own suffix (`factory-prod-<instance>`), in its users, directories, units, firewall table and socket (D4 rule 16).
The broker reads its instance from where setup installed it, never from a file a checkout can change, and finds
other tiers on the host by looking, never by name.

**Setup's trust root** is a root-owned record of the repository, written on the first run, never read from the
checkout: an edit to a project file can't redirect what root fetches and installs. Setup takes the broker's lock
before it changes anything, and refuses while a gate runs.

**The ledger** is append-only, and one damaged line stops every command rather than be guessed at. A last line left
half-written by a crash mid-append is reported by `check` and refuses gates as an interrupted run;
`resolve --torn-line NOTE` moves the torn bytes to a side file beside the ledger, then replaces the ledger, in one
rename, with its whole lines and a signed note of what it moved, who and why. Any other unreadable line is CD's to repair by
hand.

**What it refuses:** a rollback, for every request kind (its catalog says `"rollbacks": false`, so the plan guard
refuses one first); a release service declared without evidence (D4 rule 15); any catalog or block that breaks the
rules below. A refusal is signed, like a receipt. Only an `openssl` that is root's, in a directory only root can
write, ever receives the receipt key; `check` reports any other on the signer's list, though the signer skips it.

**The drift check** (`drift-check`, daily on a timer) compares production with the record and walks the release
branch's history since it. A release gate's merge, mid-plan, is accepted, with the gate's content that the default
branch doesn't have until the execution PR merges, only when its subject is exactly the pin's (`Merge pull request
#N from <owner>/factory/release/<pr>-G<n>-<sha12>`, matching the merged commit) and the ledger holds a verified
release-gate result for that merge, and only for 14 days: after that the drift check names it, since the execution
PR should have merged by then. Anything else raises the alarm.

## The host module

`production/factory_op_host.py` implements these for its host. The broker loads it only in a step, and checks the
interface before using it: a missing primitive fails the step.

| Primitive | Contract |
|---|---|
| `client(ctx)` | The host API client, built from the step's credential (`ctx.secret(label)`), read-only. A client that can change anything is built only inside the one operation that needs it. |
| `preflight(ctx)` | `config.json`'s `host` block is valid and names exactly the declared services; when the step holds the credential, it is for the configured project and environment. Runs before every step but a diagnostic. |
| `latest(ctx)` | Every declared service's newest deployment status, in one read: `{svc: status or None}`. |
| `deployments(ctx, svc)` | The service's recent deployments, at least the newest 20, as `Deployment(id, commit, status, created, branch)`. The broker sorts them itself. |
| `serving(ctx, svc)` | The newest successful deployment, which isn't necessarily the latest. |
| `reports(ctx, svc, deployment_id)` | Whether the running service says it is this deployment, and ready. Raises `Unavailable` for no usable answer. |
| `heartbeat(ctx, svc, deployment_id, patient)` | The service's heartbeat for this deployment, as `(started, written)`, or None for "not yet". Raises `StepFailed` when the answer is definitive, `Unavailable` for no usable answer. The broker's own loop needs two reads more than `heartbeat_ttl_s` apart, written after the deployment began (D4 rule 15). |
| `capture(ctx)` | `capture-state`'s outputs: `<svc>_commit` and `<svc>_settled` for each checked service, and every recorded and invariant output. It must fail when the host builds a release service from patterns other than its declared ones. |
| `OPS` | `{name: fn(ctx) -> outputs}`: the host's own catalog operations (a backup). Exactly the block's `host_ops`. |
| `DIAGNOSTICS` (optional) | `{name: fn(ctx)}`: checks CD runs by hand (`diagnose <name>`), which fail their own step when something is wrong. |

Statuses are `waiting`, `success`, `skipped`, `failed` and `crashed`; the module maps its host's vocabulary onto
them, and anything it can't place is `failed`. It imports only the names in the broker's `HOST_API`
(`StepFailed`, `Unavailable`, `HostError`, `Deployment`, `STATUSES`, `Deadline`, `NETWORK_ERRORS`, `SHA`, `safe`,
`parse_ts`, `canonical`). `ctx` gives it the step's parameters, the config and its `host` block, the `broker`
block, the release branch's head, a read-only git view of the broker's clone, a clock and the step's deadline, its
declared secrets, HTTPS through the egress proxy (`ctx.https`, declared hosts only, no redirects), and
`ctx.note(text)` for display lines, which root prints and never decides on.

## The `broker` block

In `ops.json`, beside the catalog, so the digest covers it. Unknown keys are refused, so a typo can't turn a check
off.

| Key | What it declares |
|---|---|
| `egress` | The only hosts the step's HTTPS and the egress proxy reach (1 to 16 names, no IP literals). Setup opens the firewall for the proxy alone. |
| `http_targets` | `{name: host}` for the generic `http-check`; each host is in `egress`. |
| `secrets` | `{label: {file, by, hex, pattern?}}`: credentials under the tier's `/etc` directory. `by: setup` ones setup generates (32 random bytes, hex, and `hex` must be true); `by: cd` ones CD writes by hand, as root, mode 0600, where setup's `ACTION NEEDED` line says, and `check` fails until they're there. A file can't take a name the tier uses itself. Each step gets only its own, and their bytes are redacted from its log. |
| `op_secrets` | `{op: [label]}`: which secrets each operation gets, `[]` for none. Every operation is listed. |
| `host_ops` | The catalog operations the host module's `OPS` implements. Every catalog operation is a generic one or listed here. |
| `services` | `{svc: {release, checked, evidence, patterns}}`, in order, at least one `release`. A `release` service is one a release waits for: it must be `checked`, and needs `evidence` (`reports`, `heartbeat` or `both`); every other service's `evidence` is `none`. A `checked` one's commit, settledness and content are checked at every gate, baseline and drift check, and it may deploy only from the release branch; it gives `patterns`, the paths that build it (a service the host rebuilds on every merge declares `["**"]`), and an unchecked one gives none. |
| `heartbeat_ttl_s` | The heartbeat's time to live, when a service's evidence is a heartbeat. |
| `release_wait_phases` | `{grace_s, <name>_s}`: how long a release may take, phase by phase. Only `grace_s` changes behavior; the sum sizes `release-wait`'s timeout, which must be at least 1.1 times it. |
| `recorded` | The capture outputs that must not move between a gate's two captures or since the last record (settings fingerprints, say): at least one, none a commit, settled or deployment output. |
| `invariants` | `{output: {is or in, why, show?}}`: values a gate, baseline and drift check require. A failure says what it found, what it needed, and why, with each `show` output's value; `capture` returns the `show` outputs too. |
| `internal_ops` | `{name: {timeout_s}}`: the broker's own steps outside the catalog (`drift-scan`, `host-check`) and the host's diagnostics. |
| `python` | The host's Python floor (`"3.<n>"`). |
| `host_locks` | Optional lock files the broker holds while a gate's steps run (D4 rule 12): each under `/run/` (not `/run/lock`, `/run/user` or `/var/lock`), in a root-owned directory nobody else can write, and itself a regular root-owned file only root can open (mode 0600 or 0700). A lock other users can open could be held to block every gate, so `flock(1)`'s default file (0644) is refused: the job that shares it must create it 0600, after every reboot on a tmpfs. |

**The catalog keys it requires,** outside the block: `"rollbacks": false`; `release_gates`, present (false while
the project enables the broker, then true); `release_wait: "release-wait"`; `gate_overhead_s` at least the broker's
own worst case around a gate's steps; `step_margin_s` at least its kill margin; no `rollback_only` operation; and
the generic operations, each a `read`, with their exact parameters and at least their generic outputs:
`release-wait` gives `head`, `deployed` and `<svc>_deployment` for each release service; `health` gives `healthy`,
`services`, `unhealthy` and `<svc>_deployment`; `capture-state` gives `<svc>_commit` and `<svc>_settled` for each
checked service and every recorded, invariant and `show` output; `http-check`, needed only with `http_targets`,
gives `status`, `latency_ms` and `body_sha256`. Timeouts must cover their worst case: `release-wait`'s at least 1.1
times the phases' sum; `health`'s at least 1.1 × H × (`heartbeat_ttl_s` + 61), for H services with heartbeat
evidence; and the phases after `grace_s` add up to at least H × (`heartbeat_ttl_s` + 65), room for the two reads. The bundle's catalog test, in the project's CI, checks all of
it against `ops.json`; the seeded `ops.example.json` passes it, release gates off.

## Enabling it

**Runbook:** `factory-broker-enablement` · **When:** enable · **Record:** `docs/runbooks/factory-broker-enablement.md` § Record

For a project with the `factory` bundle enabled (`[sdlc-root]/process/factory-runbook.md`) and a release branch
its host deploys by itself. `sdlc-run-runbook factory-broker-enablement` runs it. Read § How it works and § The host
module first.

**Ask first,** after step 1: the instance (none for the first tier on the machine, a short name for a later one;
recommended: none unless another tier is there); the release services and what proves each release (recommended:
`reports` where a service can report its deployment, a heartbeat for a worker); the host's own operations, if any
(a backup); and whether the project already has a broker of its own, which § Adopting it by hand covers instead of
steps 3 and 4. **Done when:** every step passed, and a release gate in a plan passes the plan guard.

The broker's command is `factory-op` on the first tier and `factory-op-<instance>` on a later one; below it is
written `factory-op`.

1. **Inventory.** The host: how it deploys the release branch, its services, which ones a release changes, what
   each can report about the deployment it runs, its API and credential, and any other tier on the production
   machine. **Check:** State lists each service with its proposed `release`, `checked`, evidence and patterns.
2. **[CD] Decide** (asked first). **Check:** Decisions hold each answer.
3. **Write the host module** in `production/factory_op_host.py`, with tests of its own beside the bundle's
   (`production/tests/test_host_*.py`, against recorded answers from the host, never the live API), and add the
   line to the project's CI that runs `production/tests` (`python3 -I -m unittest discover -s
   .github/factory/production/tests`). **Check:** CI runs and passes the host module's tests and the bundle's.
4. **Write the catalog and settings:**
   - `production/ops.json` from `ops.example.json`: the `broker` block from step 2, `release_gates` false.
   - `production/config.json`: `repo`, `default_branch`, `release_branch` (factory.json's `release.branch`), and
     `environment` when the project renamed it (factory.json's `environments.production`; setup refuses either when
     it differs); `release_head_start`, the commit the release branch was created at, which the first `baseline`
     starts provenance from; `app_bot_id` and `approvers` (GitHub user ids); the tier's own paths (the seed's are the
     first tier's; a later tier's are `factory-prod-<instance>`'s, and `clone_dir` is `<clone base>/<name>.git`); and
     the `host` block the host module reads.
   - `host/production.conf`: `AGENT_USER` and `PROD_RUNNER_NAME` (required), the instance, and the rest as needed.
   - CODEOWNERS covering `production/` and `host/`, and the same paths in the seeded `tests/test_codeowners.py`'s
     lists.

   **Check:** the bundle's catalog test passes on `ops.json`, `config.json` and the host module, and the CODEOWNERS
   test passes with the new paths.
5. **Merge** steps 3 and 4 in a PR CD reviews. **Check:** they're on the default branch.
6. **[CD] GitHub's side:** now that `ops.json` exists, run the factory's `bootstrap.py --apply` again
   (`[sdlc-root]/process/factory.md` § Enablement): it creates the `factory-production` environment and the
   production runner group (`factory-pool-<repository>-prod`). **Check:** `bootstrap.py` reports both in place.
7. **[CD] Set up the host** as root, from a checkout no agent session can write, such as a fresh clone made just
   before by a login no agent session uses: setup's first stage is the checkout's own script, so whoever can change
   it before it runs gets root (the factory's runner setup has the same rule). Put a runner registration token in
   `host/reg-token` first (as the factory's runner setup takes one; without it the runner installs but doesn't
   register). The tier's first run names the repository: `sudo TIER_OWNER=<owner>/<repository> bash
   .github/factory/host/setup-production.sh`; later runs don't. Then write each `by: cd` secret where setup's `ACTION NEEDED` lines say. **Check:** setup's acceptance
   checks pass, and `sudo factory-op check` prints `"ok": true`.
8. **[CD] Commit the public key** setup printed (`production/receipt.pub`). **Check:** it's on the default branch.
9. **[CD] Record a first `baseline`:** `sudo factory-op baseline NOTE`. It checks the release branch's provenance
   from the record, or from `release_head_start`; a commit that reached the branch without the review provenance
   needs (a hotfix) is shown, and recorded only when CD types `accept <sha>` for it. When the release branch already
   has commits CD has reviewed another way, `baseline --advance-release-head NOTE` records the branch's head as the
   new start. **Check:** `sudo factory-op drift-check` prints `drift: ok`.
10. **A gate end to end:** a throwaway plan with one read gate (`health`). **Check:** its signed receipt verifies,
    and the factory reports it.
11. **Release gates on:** `release_gates` true in `ops.json`, merged, then setup run again (the digest moved).
    **Check:** `check` passes, and a release gate in a plan passes the plan guard.

## Adopting it by hand (the pilot, or a project with a broker of its own)

A project that already runs a checks-only broker at `production/factory_op.py` adopts the bundle's in place of
steps 3 and 4, and keeps its ledger:

1. **Its host module and block first,** in a PR of its own: move its host code into `factory_op_host.py` and its
   host data into the `broker` block. The broker reads a ledger written before it, with no re-baseline, when the
   host module emits the same recorded outputs from the same hashed inputs, byte for byte; `recorded` names exactly
   the outputs the old records hold (a record of fingerprints `<n>` and a key id reads as `fp_<n>` and
   `fp_key_id`); and the ledger and receipt key stay at the tier's paths. Otherwise the next `baseline` records it
   afresh, keeping the release head.
2. **Its settings, in the generic shape:** `config.json` with the tier's own paths (its ledger in
   `/var/lib/<tier>/`, its clone under `/var/lib/<tier>-clone/`), `release_head_start` and the `host` block; and
   `host/production.conf` with only the keys setup reads (`PROD_INSTANCE`, `AGENT_USER`, `PROD_RUNNER_NAME`,
   `RUNNER_GROUP`, `LAN_DNS`, `PROBE_PORTS`, `PROD_HOME_BASE`): an unknown key is refused.
3. **Then the bundle's files:** copy the bundle's `tree` files at the release it adopts over its own, add
   `factory-broker` to `.sdlc-manifest.json`'s `installed_bundles`, and record each copied file's hash in
   `installed_files`, so its next migration refreshes them like any bundle's.
4. **Then setup** on the host (the digest moved). Its first run under the bundle names the repository with
   `TIER_OWNER`; an installed `/etc/<tier>/config.json` naming the same repository is taken as this repository's
   own tier, not another's. **Check:** `sudo factory-op drift-check` prints `drift: ok` with no new `baseline`.

## After migrating

What a release of the bundle can make due. `sdlc-migrate` follows this after copying the bundle's files
(`[sdlc-root]/process/runbooks.md` § After migrating) and reports each item that applies; CD does them.

- **The broker changed** (`production/factory_op.py`), or the factory bundle's `gates.py` or `ed25519.py` → re-run
  setup on the host before the next gate, or every gate is refused. The same for the project's own `config.json`,
  `ops.json` and host module, whenever they change.
- **Setup changed** (`host/setup-production.sh`) → re-run setup.
- **The request client changed** (the factory bundle's `host/factory-op-request`) → re-run setup, which shows the
  installed client's difference and replaces it only with `REPLACE_CLIENT=1`.
- **The catalog's rules changed:** the bundle's catalog test fails in the project's CI on its `ops.json` → change
  `ops.json` as the failure says (a seed is never rewritten), then re-run setup.

## Integration

- **Requires:** the `factory` bundle (`gates.py`, `ed25519.py`, `host/factory-op-request`)
- **Rules it implements:** `[sdlc-root]/process/factory.md` § D4, `[sdlc-root]/process/production-gates.md`
- **Driven by:** `sdlc-run-runbook` (`factory-broker-enablement`)
- **Followed by:** `sdlc-migrate` (§ After migrating)
