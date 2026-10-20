# Software Factory

The `factory` bundle's rules: issue-driven agent stages that run unattended on self-hosted runners,
from triage to a draft PR, with CD approving every plan, every merge and every production step. These
are framework rules (F22): every project that installs the bundle inherits them, and project
decisions never override them. A project keeps only its settings and operating notes
(`.github/factory/factory.json`, `.github/factory/README.md`).

**What the bundle installs.**

| Where | What | Owner |
|---|---|---|
| `.github/factory/` | The scripts, guards, schemas, tool policies, sandbox settings, workflow templates, the renderer (`render.py`), the workflow policy check, the stack profiles, the setup tools (`bootstrap.py`, `create_app.py`, `host/setup.sh`), the echo service's source (`echo/`) and their tests | z-sdlc: refreshed by every migration |
| `.github/factory/factory.json`, `planning.json`, `services.json`, `triage-policy.md`, `README.md`, `host/host.conf`, and the tests of the project's CODEOWNERS | The project's settings, its runner host's settings, triage policy and notes | The project: seeded once, never overwritten |
| `.github/workflows/factory-*.yml` | The workflows, rendered from the templates with `factory.json` | Generated: re-rendered on every migration; CI refuses a hand edit |
| `.claude/skills/sdlc-triage`, `sdlc-implement`, `sdlc-revise` | The stages' skills. Headless only: the workflows run them, so they have no commands | z-sdlc |

Not installed: the production tier, its broker, operations catalog, runner and host setup (D4
rule 16). It is per project and per host (`[sdlc-root]/process/production-gates.md` covers gates in
plans).

**Names.** Runner labels, runner groups and environments are defaults in `factory.json`, shared by
every project in an organization; a project that changes them changes them there, and the workflows,
`workflow_policy.py`, `bootstrap.py` and the host setup follow. The App, the job image and the echo
service are the organization's own: the seed holds placeholders for them, which Enablement fills
(steps 3 to 5).

**Limits of this version.** The project's SDLC root must be `ops/sdlc` (the scripts and the gate
digest name it). The runners need Linux hosts (systemd, nftables, rootless Docker). Two stack
profiles: `python-node` (Django and Vite, npm) and `dotnet-node` (.NET 10 and Vite, pnpm); another
stack needs a profile of its own (§ Stack Profiles). The plan and spec stages run with or without a
database (`planning.json`, D3).

---

## D1: Stage Contract (labels hold state, dispatch advances, writer jobs write)

### Why

Agent stages connect through GitHub, and three platform facts shape how:
- A label or comment written with a workflow's default `GITHUB_TOKEN` starts no new workflow run. `workflow_dispatch` and `repository_dispatch` are the exceptions.
- `claude-code-action` acts as the Claude GitHub App when `github_token` is unset, and that token can comment, label and push.
- The resume workflow restarts the stage a hidden comment marker names, so whoever can write that marker can steer the factory.

Posting under several identities would silently break resume, and an agent holding a write token makes "the agent can't write" a matter of prompt wording instead of permissions.

**Options considered:**
1. **Label events chain the stages,** applied by a bot with an App token or a PAT. A write token is needed wherever labels are applied, and markers come from several identities.
2. **Agents write directly** as the App. Simplest to wire, but write access rests on instructions, and a prompt injection gets a write channel.
3. **Labels hold state, dispatch advances, writer jobs write (chosen).** The only option where every requirement holds by construction.

### Rules

1. **Labels hold state.** An issue carries at most one `factory:*` state label, set by CD or by writer jobs.
2. **Dispatch advances.** A stage starts by `workflow_dispatch` of `factory-<stage>.yml` with an `issue_number` input, sent from a writer job (`GITHUB_TOKEN`, `actions: write`). A stage workflow may also accept its label event, so CD can start it by hand.
3. **Agents hold no write credential.** An agent job's `github_token` is the job's read-only `GITHUB_TOKEN`, never unset. The agent returns structured output (from phase 2, also a patch or bundle artifact). A writer job on a GitHub-hosted runner validates it and acts on it.
4. **One identity for comments and markers.** Comments, labels and markers are posted only as the factory App (its bot user is `factory.json`'s `app.login`), with an issues-only App token each writer job mints in the writer environment. Pushes and PR creation use a separate contents and pull-requests App token, in a writer job that posts no markers. Dispatch alone uses `GITHUB_TOKEN`. Exceptions that show as `github-actions[bot]`: failure reports when the App token can't be made (they fall back so a broken key still gets reported) and `factory-advance`'s "plan approved" comment (a `pull_request` event can't use the `main`-only environment). One visible identity also makes markers harder to forge: only default-branch jobs in `factory-writer` can mint the App's token, where any workflow with `issues: write` can post as `github-actions[bot]`. App-set labels start workflows, so rule 2's label events count only from a person (`sender.type != 'Bot'`, in the job condition and the concurrency group).
5. **Marker grammar.** Markers form a block of consecutive lines at the top of a factory comment (D4's gate markers on execution PRs are display only, never trusted for anything):
   - **stage marker,** first when present: `<!-- factory-stage: <stage> [k=v ...] -->`, meaning "waiting on CD; a reply restarts `<stage>`";
   - **decision record:** `<!-- factory-triage: {...} -->`;
   - **deliverable reservation:** `<!-- factory-id: Dnn -->`, posted by the plan stage's claim job before planning starts (F11 without a push to `main`): the next ID is the highest of the catalog's Next ID, its rows and every earlier reservation, plus one, claimed one at a time across the repository;
   - **revision count:** `<!-- factory-revise: N -->`, one per revise run (F16: 3 per code PR, 5 per spec or plan PR, then `factory:escalated`).

   Writer jobs escape `<!--` in agent text and validate every value they write into a marker. Resume reads the leading marker only from comments by the App's bot user, matched by ID (REST has returned its login in different case), and maps stages to workflows through an explicit allowlist. The claim job's reservation scan also counts `github-actions[bot]` reservations from before the switch.
6. **Resumable questions go on the issue.** A stage that pauses about a PR puts its question on the issue with `pr=<n>` in the marker. Non-resumable notices on a PR (such as F16's escalation) are allowed.

### Forbids

1. An agent job with `issues: write`, `pull-requests: write` or `contents: write`, or with `github_token` unset.
2. Chaining stages by label events applied with a bot token or PAT (a stage ignores labels a bot sets).
3. Posting a comment, label or marker with a PAT, with `GITHUB_TOKEN` (except the fallbacks in rule 4), or with the App's push token.
4. Reading a marker from anything but the leading block of a comment by the App's bot user, or dispatching a stage not on resume's allowlist.
5. Posting a stage marker or resumable question on a PR.
6. Using the App key outside `create-github-app-token`'s private-key input in a hosted `factory-writer` job with no agent (`workflow_policy.py` checks this).

### Costs

- Every stage costs a second job on GitHub-hosted minutes.
- Adding a stage takes three touches: its workflow, a `case` line in resume (the stage's workflow and in-flight label), and the runner group's selected-workflows list.
- Phase 2 pushes need artifact plumbing between agent and writer jobs.
- A reply posted while a stage runs restarts nothing (the label is already swapped); CD replies again after the stage comments.

### Revisit when

- A stage genuinely needs agent-side GitHub writes.
- GitHub changes which events `GITHUB_TOKEN` may trigger (resume would fail loudly: it restores `factory:needs-input` and comments).
- The factory runs across more than one repository.
- Phase 2's patch-artifact handoff proves too brittle.

## D2: Credential Boundary for Agent Jobs

### Why

Agent jobs run on self-hosted runners, and a runner host may also run production. `claude-code-action` passes its whole environment to Claude Code, including `CLAUDE_CODE_OAUTH_TOKEN`, a long-lived credential for the owner's Claude plan. Agents read untrusted text (issues, search results, documentation), so a prompt injection needs only a tool that reads the environment and a way to send it out. Triage needs no shell; implement needs Bash to install dependencies and run tests.

**Options considered:**
1. **Never give agents Bash.** Safe, but rules out a stage that runs tests.
2. **Bash with default isolation, relying on auto mode's classifier.** It declined token-reading commands when tested, but a model's judgment is not a boundary.
3. **A tool policy, a credential scrub, a bubblewrap PID namespace and a network sandbox (chosen).**
4. **No agent-side credentials** (an API proxy, a VM per job). More infrastructure than a self-hosted factory needs to start; § Revisit when says when it would be worth it.

### Rules

1. **Every agent step runs under a versioned tool-policy file,** loaded by the stage workflow and probed by `factory-smoke`. Triage (and smoke's agent steps) use `triage-tools.args`: Read, Grep, Glob, WebSearch and Context7; no Bash, write tools or WebFetch; Read denies on `/proc`, `/dev`, `.git` and the runner's mounts (which also bind Grep and Glob).
2. **A stage that grants Bash runs it sandboxed:**
   - `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, with `bubblewrap` and `socat` in the job image;
   - a sandbox settings file, copied out of the workspace before the agent starts and loaded twice: with `--settings` (which makes the sandbox admin-required, so the repository's own settings can't loosen it) and as the action's `settings` input (user scope, for the user-scope-only keys). It sets `sandbox.enabled`, `failIfUnavailable: true`, `allowUnsandboxedCommands: false`, the weaker-isolation switches off, `network.strictAllowlist: true` with `allowedDomains` limited to the registries that stage needs, `filesystem.denyRead` on the runner's mounts, `credentials.envVars` `deny` for every credential the job holds (the OAuth token, `GH_TOKEN`, `GITHUB_TOKEN`, the action's `OVERRIDE_GITHUB_TOKEN` and `DEFAULT_WORKFLOW_TOKEN`, `CONTEXT7_API_KEY`, the Actions runtime tokens), and `disableAllHooks: true`;
   - `--strict-mcp-config`, because the action forces `enableAllProjectMcpServers` and MCP servers run outside the sandbox;
   - an explicit `--setting-sources` that never includes `local`: `user` where the stage needs nothing from the repository, `user,project` where it needs the repository's skills and `CLAUDE.md`. In `-p` mode, project and local settings apply their `env` at startup (`LD_PRELOAD` and `NODE_OPTIONS` aren't filtered), so `project` is loaded only from a ref whose `.claude/`, `CLAUDE.md` and `.mcp.json` CD has reviewed: `main` (CODEOWNERS), or a factory branch whose patch the writer job refused to let touch them;
   - container `options`: the narrow seccomp profile (Docker's default plus `unshare`, `clone`, `setns`, `mount`, `umount2`, `pivot_root`, `mount_setattr`, `open_tree`, `move_mount`) and `--security-opt systempaths=unconfined`;
   - **file tools are outside the sandbox:** Read, Edit and Write run in the Claude Code process, which holds the token. The stage's tool policy denies Read on `/proc`, `/dev`, `/sys` and the runner's mounts, and Edit on system directories, runner state, `HOME`, temp and mount points, `.git`, `.github`, and `.claude/`, `CLAUDE.md` and `.mcp.json` at any depth (deny rules also match a symlink's target). Skill shell execution is off;
   - **a service the job starts outside the sandbox that sandboxed Bash can reach is part of the boundary**. Test databases run outside the sandbox with open network, on the job container's loopback, reached through the sandbox's HTTP proxy with `localhost` as the only local entry in `allowedDomains`. Never `allowAllUnixSockets`: it drops the sandbox's seccomp helper, whose nested PID namespace and clean environment hide bubblewrap's own environment, and a smoke probe showed sandboxed Bash then reads the job's GitHub token from `/proc/1/environ` (the env scrub leaves GitHub tokens in place) and reaches Claude Code's own Unix sockets. Each runs least-privileged (no Postgres superuser, so no `COPY ... TO PROGRAM`; Redis without `MIGRATE`, `REPLICAOF`, `MODULE`, `CONFIG` and the like), starts with an empty environment, and the start script checks all of it on every run;
   - `network.allowedDomains` empty for a stage that installs nothing (implement): a package registry that accepts publishes is a way out.
3. **Writer jobs refuse to post** token-shaped strings, images and embeds.
4. **After an agent step that can write the workspace, the job trusts nothing the agent could have touched.** Later steps in that job run only code copied out beforehand to places the sandbox can't write, call `python3 -I` by absolute path, and run git with hooks and fsmonitor disabled, only after checking that `.git` is a real directory that wasn't redirected (`commondir`, `alternates`), its hooks are unchanged and its config holds only allowlisted keys (read with `git config --file`, which follows no include), and the index holds no submodule; and never into a nested repository (`--ignore-submodules=all`): `git status` runs a staged submodule's own config, filters included, which a planted repository outside `.git/` can define (review round 2, reproduced). The sandbox leaves empty read-only placeholder files behind at protected paths it mounts over (`commondir`, `alternates`, `config.worktree`); the guard removes empty ones and refuses any with content. The job removes `origin` before the agent step, because the action writes the job token into its URL, and passes the factory's bot identity so the action's git setup commits as the factory. The job removes `.git` at the end, because `actions/checkout`'s post step runs git in the workspace. The commits themselves are judged by a writer job on a clean GitHub-hosted runner.
5. **The boundary is tested before it is relied on.** Every smoke run probes the tool policy and does an exact-value credential scan. Before any stage gets Bash, smoke carries that stage's sandbox probe (`factory-smoke` job `bash-sandbox`):
   - **An unsandboxed control** must find the tokens in its environment and in `/proc`, and a planted canary in plain and base64 files, which proves each detection path.
   - **From inside the sandbox,** the probe, frozen read-only before the agent runs, must find no credential by value (environment, every process's environment, token-like strings in readable files, raw or base64) and none by name. It must also find:
     - a PID namespace other than the control's;
     - unlistable runner mounts;
     - unwritable protected paths;
     - no Unix socket it can find that accepts a connection (the Docker socket, the job's own services' sockets, the runtime's): the test services answer only through the proxy;
     - the allowed registries reachable through the proxy, every other host refused, and no route around the proxy.
   - **The assertion judges** only the output of the one expected command.
   - **On the planning tier** (job `planning-sandbox`), before the plan, spec and revise-doc stages get Bash: the same probe, in the job those stages run. That means their runners and firewall exception, the read-only database password pgbouncer holds, their service credential slots, and the sandbox settings `services.py` builds for them. Sandboxed Bash must find none of those secrets, and must reach the planning database through the proxy. Its network is D3 rule 5's open internet: `WebFetch(domain:*)` opens the sandbox's proxy to every host, so any host may answer, but nothing may get around the proxy (no direct connection, no DNS). Only this job's verdict may use the open internet (`sandbox_check.py`'s `open`); the workflow policy refuses it anywhere else. The job's isolation probes run from that tier too, with the planning database as their one exception (D3 rule 2), so `planning.json`'s database host must be written as in `smoke.host_probes`. The probe recognises the reader password in a file only when it's token-like (20 or more letters, digits, `-` or `_`), as a generated one is.
   - **Tool policies:** smoke probes triage's and implement's. `plan-tools.args` is implement's plus WebFetch (D3 rule 5), and `improve-tools.args` is no wider than triage's: unit tests pin both, so neither has a probe of its own.

   Re-run smoke on every action, image or tool-policy change.
6. **Workflow edits are trusted only through review.** The boundary against a malicious workflow change is:
   - CODEOWNERS on `.github/`, `.claude/`, `CLAUDE.md`, `.mcp.json`, `[sdlc-root]/` and the test and build config, enforced by the `main` ruleset. The discipline parking lots (`[sdlc-root]/disciplines/*.md`) are the exception: an owner-less line unowns them so agents can add entries. The writer's guard follows GitHub's last-match-wins rule, and CD still sees each entry in the PR diff;
   - the factory's own GitHub App (Z Software Factory) has no `workflows` permission, so no factory token can push a workflow change. Its key is in the `factory-writer` environment, which only `main` can use, so a factory branch can't mint the token;
   - the runtime sandbox probe (rule 5).

   CI's `workflow-policy` check catches accidental drift from these rules on every PR. It is not a security control: a workflow is a program (expressions, `$GITHUB_ENV` writes, other actions), so a static check can't be complete against someone editing workflows on purpose. Its known gaps are under Leaves open.

7. **Fixtures a project's tests need from a secret-holding source come from a hosted fixtures job on the default branch, as an artifact; the agent job never holds the secret** (CD, 2026-10-13). `factory.json`'s `fixtures` block names the command, its one repository secret, the directory it fills (gitignored) and the cache key. The implement and revise workflows run it in a `fixtures` job on a GitHub-hosted runner, from the default branch's checkout, so a factory branch an agent wrote never runs with the secret. The job restores the directory from the Actions cache first (the project's CI can fill the same entry), so the source is called only on a miss. It refuses fixtures that contain the secret, then hands the directory over as an artifact, which the agent job puts in the workspace before the agent starts. `workflow_policy.py` holds the job to this shape, and refuses the secret anywhere else in the workflow.

### Forbids

1. Giving an agent WebFetch or any unscoped network path. (Context7 covers library and vendor docs; WebFetch was the one channel that let injected text choose the destination.)
2. Agent Bash without the sandbox, or with `failIfUnavailable: false` or `allowUnsandboxedCommands: true`.
3. Granting a stage Bash before smoke carries that stage's sandbox probe.
4. Granting Bash without `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`.
5. `--security-opt seccomp=unconfined`, `apparmor=unconfined`, `--privileged` or `--cap-add` on factory containers.
6. Giving the OAuth token to a non-agent job; giving any write-capable token to an agent job, or putting one in a file the agent can read.
7. Running an agent step without a tool-policy file, or changing a tool policy without re-running smoke.

### Costs

- `systempaths=unconfined` is required (bubblewrap mounts its own `/proc`).
- Sandboxed Bash gets no credential at all, so tools inside it can't authenticate (no `gh`, no private registries). A stage that needs one would use a `mask` entry, which needs TLS termination; not decided.
- Denying `/github` hides the job's `HOME` from Bash; Bash stages point pip and npm caches at the temp directory.
- WebSearch and Context7 queries still leave the job, to fixed services.
- The seccomp profile tracks Docker's default; re-check on Docker or bubblewrap upgrades.

### Leaves open

- **`CONTEXT7_API_KEY`:** whether it reaches sandboxed Bash is exercised only in a project that sets the key. It's denied by name either way.
- **Hooks and settings in a checkout of another branch** (the revise stages check out pull requests' branches): `disableAllHooks` and admin-required sandboxing cover hooks and sandbox loosening. A branch's project skills and `CLAUDE.md` are still agent instructions from that branch.
- **Ephemeral runners for the strict and planning tiers.** The CI tier's are just-in-time; these tiers' runners keep a workspace between jobs, which every job cleans first.
- **Gaps in the static workflow check** (rule 6). Each needs a workflow edit CD reviews under CODEOWNERS:
  - `--json-schema` and `--mcp-config` values aren't shape-checked, and an `env.*` value written at runtime can carry extra flags;
  - lines a step writes to `$GITHUB_ENV` or `$GITHUB_PATH` aren't checked, and `FACTORY_TOOL_ARGS` can be set by a heredoc, extended after the `tr`, or read from a rewritten `.args` file;
  - environment keys are blocklisted, not allowlisted, and `secrets['X']` or `toJSON(secrets)` aren't caught;
  - actions in agent jobs aren't allowlisted;
  - a `git checkout` in a `run:` step after the pinned checkout isn't caught;
  - the direct-Claude pattern misses `import claude_agent_sdk` and `$(which claude)`;
  - the guard that keeps a sandbox verdict's `open` to the planning probe matches the word as written, so a quoted, split, variable or continued `open`, or the checker run through a variable, gets past it (the pilot project's review of v2.1.5). An allowlist of the strict verdict's whole line would fall to a renamed step or a shell function in the same way.

  The structural answer is a design item: every agent run going through one reusable workflow, with a frozen step right before the agent that checks the actual environment, arguments and tool policy at runtime.

### Revisit when

- Claude Code or the action changes credential handling or sandbox keys.
- A stage needs a non-HTTP network path (the sandbox proxy covers HTTP(S) only).
- The factory moves off a production host.

## D3: Planning Tier (spec and plan stages see real data and services)

### Why

Spec and plan stages make judgment calls that depend on how the system behaves in production: what the data looks like, which errors occur and where, what an external service returns. D2 keeps every agent job away from production and credentials, which is right for the stages that write and run code, but it leaves planning guessing or asking CD for facts it could look up. So planning may use the data and services that make a better plan, the whole database apart from personal and secret data, and only to read.

**Options considered:**
1. **Ask CD for every fact.** Keeps D2 unchanged; slow, and plans are only as good as the questions.
2. **A periodic scrubbed snapshot.** No path to production, but stale data, a table list to maintain, and no route to services such as error trackers.
3. **A separate planning tier with live read-only access (chosen).** Planning jobs run on their own runners as their own user, with a firewall exception for the production database only, a read-only login that can't see personal or secret data, and services wired from a list with their credentials masked.

### Rules

1. **Two runner tiers.** Implement, execute and revise run on the strict tier (D2, unchanged: no production path). Spec and plan run only on the planning tier: runners under a separate Linux user (`factory-planner`), selected by their own runner label and group. A workflow can't move a code-writing stage onto planning runners without a CODEOWNERS-reviewed edit, and the workflow policy check refuses it.
2. **One firewall exception.** The planning user may reach the production database port and nothing else on the host or LAN: on the runner host itself, or, when production runs on another machine, on the one address `host.conf`'s `PLANNING_DB_HOST` names (an address that doesn't change, such as the machine's Tailscale address). The strict user's firewall is unchanged.
3. **The database login is read-only and excludes personal and secret data.** A dedicated role with `SELECT` only, granted per table and per column: everything except fields holding personal data (names, emails, phone numbers, addresses), credentials (password hashes, API keys, tokens, session data) and payment data. The exclusion list is generated from the models and reviewed by CD; a migration that adds a table or column re-runs the check, and anything new and sensitive-looking stays excluded until CD approves it. The role also has a statement timeout and a connection limit. The agent reaches it through a connection proxy outside the sandbox that holds the password; the agent never sees it.
4. **Services come from a reviewed list.** `.github/factory/services.json` (CODEOWNERS) names each service: its domains, the GitHub secret with its credential, and how the credential attaches. The planning job turns the list into sandbox settings (`credentials.envVars` with `mode: mask`, `injectHosts` set to the service's domains, `network.tlsTerminate`) or into an MCP server entry. Sandboxed commands see a placeholder; the proxy substitutes the real value only on requests to that service. Adding a service is one entry plus one secret, with no workflow edit.
5. **Open internet for planning.** Planning's sandbox allows general web access for research. What leaks is bounded by what the tier can read: credentials are masked and go only to their own hosts, and the database login can't see personal or secret data.
6. **Planning never copies raw data into its documents.** Specs and plans state facts and aggregates (counts, ranges, distributions, examples with identifiers removed), not row dumps. The skill says so; the writer job's checks apply as for every stage.
7. **Planning still writes only documents.** Its output is a spec or plan PR; it never pushes code to run. Rules D1 and D2 otherwise hold unchanged (read-only GitHub token, writer jobs post, frozen code after the agent).

### Forbids

1. A code-writing stage (implement, execute, revise) on planning runners, or any planning runner, secret or exception reachable from the strict tier.
2. A database login with write rights, or one that can read an excluded table or column.
3. A service credential in the agent's environment unmasked, or masked without `injectHosts`.
4. Raw rows of production data in a spec, plan, PR or comment.

### Costs

- A second runner user, its own rootless Docker, firewall and runners on the host.
- The exclusion list must be maintained as models change (mechanical, but it needs CD's review for new sensitive fields).
- Planning can exfiltrate what it can read through the open web; the bound is the data's sensitivity, not the network.

## D4: Production Tier (gates CD approves, run by a broker no agent can reach)

### Why

Some plans need production: deploys, migrations, restarts, backups, checks against a live system. D2 keeps agents away from production, and D3 lets planning read it, never change it. The factory needs a way to do production steps without CD's hands, with approval per step and without a new PR for each approval. Cross-checks rejected the first design, which trusted labels and App comments: any repository writer can edit or race those.

**Options considered:**
1. **Plans mark production steps for CD to run.** Safe, but every gate needs CD's hands and a PR for each segment.
2. **An agent with production access, approved per step.** An agent's judgment in production is what D2 exists to prevent, and a prompt injection would reach production.
3. **A deterministic broker runs reviewed operations after CD approves each gate (chosen).** No agent touches production, and the approval is GitHub's own deployment review, which nobody can edit or forge.

### Rules

1. **No agent in the production tier.** Agents plan gates and write code; a deterministic broker runs the gates. D2 and D3 hold unchanged.
2. **Production work happens only in gates** between phases (`[sdlc-root]/process/production-gates.md`). The plan's last item is a phase; the factory also needs a phase before the first gate.
3. **Operations come from a reviewed catalog** (`.github/factory/production/ops.json`, code-owned): kind, parameters and outputs with an anchored pattern each, timeout, required earlier operations, rollback-only operations. Outputs are typed values, never free text. Scripts are installed root-owned by CD's setup run, never loaded from a workspace.
4. **Two approvals.** Merging the plan approves what each gate may do; the plan guard refuses an unknown operation or a broken parameter. Approving the gate run approves doing it now, with the values filled in.
5. **Approval is GitHub's deployment review.** Each gate gets a run of `factory-gate.yml` whose title carries the request's digest; its job waits on environment `factory-production` (CD the required reviewer, `main` only). Labels and comments authorize nothing: `factory:gate-retry` only asks for a fresh run.
6. **The digest binds everything:** repository, issue, PR, gate, attempt, plan path and blob, PR head, the resolved steps and rollback, and a hash of the installed operations.
7. **The broker checks for itself** (root, socket-activated, one instance per request, reachable only by the runner user): the run is `factory-gate.yml` dispatched on `main`; an approver approved its deployment; the request it rebuilds from the plan blob on `main`, the PR head, its own ledger and its installed operations has the title's digest; the run is in progress; every earlier gate is done in its ledger, as the plan defines it now; production's deployed commit is the one it last recorded (after any gate, or a `baseline` CD records after changing production by hand); nothing is unfinished; the digest never started.
8. **Signed receipts, for every gate.** A CD gate goes through the broker too: it runs nothing and records CD's approval. The broker signs every result, bound to its PR, gate and digest, with a root-only ed25519 key. The hosted report job verifies it with the committed public key before posting it or continuing execution; an unverified result changes nothing, and nothing the factory acts on comes from an editable comment.
9. **Never twice, and never unknown.** The ledger records each step. A finished digest returns its stored receipt; an interrupted run blocks every gate until CD resolves it on the host.
10. **Keys.** The runner user has no sudo, no Docker group and the strict firewall, and holds only the job's read-only token. The broker runs operations as the operator user, with the host's credentials in place. The runner group takes only `factory-gate.yml` from `refs/heads/main`.
11. **Rollback is approved with the gate,** runs automatically when a step fails, and only for steps that got far enough to need it. Schema changes are expand-only.
12. **One gate at a time on the host,** never during the nightly backup (the broker holds its lock).
13. **Release model:** a deploy gate deploys the execution PR's head; production may run ahead of `main` until CD merges it with a merge commit. Deploys only fast-forward, and refuse infrastructure files (compose, Dockerfiles, `docker/`, dependencies, env files, the Makefile, units), which need a rebuild by hand; compose files and `docker/` are code-owned. `.github/` deploys like docs: no container reads it and the broker runs its installed copy, so factory commits don't force a hand catch-up before the next deploy. No infrastructure pattern applies under it, whatever a file there is called (a stack profile's job-image `Dockerfile` included).
14. **A restart never changes production's settings.** Before stopping anything, a deploy asks Compose, with a dry run in the broker's own environment, what restarting would do, and refuses unless every restarted service would stay running as it is. A recreate re-reads the environment, `.env`, ports and mounts, so production could come back with settings it wasn't started with. (Comparing `docker compose config --hash` with the containers' config-hash label doesn't work: they differ even right after `up` in the same environment.)
15. **Healthy after a restart means the restarted process.** The health wait needs evidence newer than the restart (for example, a worker heartbeat newer than the running worker's start), not just a passing health check: a stopped worker's last heartbeat outlives it, and both the container health check and the API's endpoint accept it.
16. **No production tier, no gates.** The tier (the broker, its operations catalog `production/ops.json`, its runner) is the project's own, and the bundle doesn't install it. Without it a plan can have no gates, CD's included, since every gate runs through the broker: the publish guards refuse such a plan and say why. Production steps then stay outside the factory, as CD's.
17. **A revision reaches a gate the way execution does.** An execution that stops with a decision open for CD returns `escalated`, so nothing asks for the gate. CD answers with a Request-changes review. On a PR that executes a plan, a revision can then stop before that plan's next gate. The plan is the one its gate tracker names. With no tracker yet, it's the sibling of the one result doc the PR adds, when that plan is on `main` and is for the issue's own deliverable (the ID the plan stage reserved on the issue, as the App): a result doc's name alone can't point the gate at another plan. The next gate is the plan's first one this PR hasn't passed, by the broker's signed results. The gate job gives the agent the plan and that gate, and the publish job refuses any other gate. The revision must leave no critical or major finding and no question for CD, with the work before that gate done. It returns `awaiting-approval` naming the gate. A writer job then does what execute's report job does at a gate stop: it posts or updates the tracker, sets `factory:gate` on the issue and asks for the gate run, which replaces a stale run still waiting on an older request. Execution and a revision both ask for the gate on the commit they pushed: if the branch has moved since, no request is built, and CD adds `factory:gate-retry` to ask for one on the new commits after reviewing them. A revision never continues execution: if work before a gate is unfinished, CD pushes it, then requests changes.

### Forbids

1. An agent on the production runner, or a production path, credential or runner reachable from an agent job.
2. An operation outside the installed catalog, or a parameter that breaks its pattern.
3. A gate run without an approver's environment approval, or a digest run twice.
4. A production runner job from any workflow but `factory-gate.yml` on `main`, with a container, a `uses:` step, a secret, or any permission beyond read.
5. Operation scripts loaded from a workspace; agent commits to compose files, Dockerfiles or `docker/`.
6. Posting or continuing on a gate result whose signature doesn't verify.

### Costs

- CD sets up an environment, a runner group, labels, the host (`setup-production.sh`) and commits the public key, once; and re-runs setup after any change to the operations.
- The operator user's credentials are in reach of the operation scripts: they are the boundary's weakest part, so they stay few, typed and reviewed.
- Production can run code that isn't on `main` while a deliverable is mid-gate, which blocks unrelated deploys until it merges.
- Unknown outcomes need CD on the host.

## D5: Improve Loop (the factory learns from what CD did to its output)

### Why

The factory repeats mistakes nobody tells it about, while CD's corrections already sit on GitHub: request-changes reviews, revisions, PRs closed unmerged, answers to questions, label overrides, follow-ups left unchecked at merge. Agent transcripts don't outlive their artifacts' retention.

**Options considered:**
1. **Read transcripts weekly.** Races their expiry, and keeps agent text around for the loop to read as text.
2. **An agent with write access files its own improvements.** The loop would change skills and workflows without review, and a prompt injection in a review comment would get a write channel.
3. **A deterministic harvest, a read-only analysis, a deterministic report (chosen).** Only the analysis is an agent, and it returns data that a writer renders.

### Rules

1. **Report only.** The loop posts one report issue a week and changes nothing. Hygiene PRs wait for a dedicated `improve` guard stage (exact allowlist, its own schema, evidence validated). Skills, agents, process docs and anything code-owned stay CD-applied.
2. **Metrics at the source.** Every agent job uploads an allowlisted record (stage, status, cost, turns, models, dispatch inputs, how a lost run ended) for at least 30 days. Never agent text. A missing value is unknown, not zero.
3. **The harvest is code, not an agent.** It runs on a hosted runner with a read-only token, gives every signal a stable id, and caps quoted text, which stays untrusted data.
4. **Trust.** CD is a person the repository lets push (a permission check), never `author_association`. Factory content counts only from the App's bot user, by ID, in the marker grammar. A failed permission check fails the harvest; it never silently drops CD's signals.
5. **The analysis holds no write credential and no shell.** It runs `sdlc-audit` improvement mode headless on the strict tier with Read, Grep and Glob only, and returns proposals in a schema: section, route, severity, target, change, why, effect, evidence ids, and the earlier proposal it matches.
6. **The writer owns the report's structure.** It renders from the schema, escapes every agent string, builds links from the digest only, removes evidence ids the harvest didn't produce, and drops a proposal left with none, saying so. It never drops one silently.
7. **Fingerprints are the writer's.** A new proposal's fingerprint is a hash of its section, target and title. The agent may only point at a fingerprint the ledger already holds. A renamed section keeps its fingerprints: the framework section is `z-sdlc` (formerly `cc-sdlc`), its fingerprints are still hashed under the old name, and readers accept both values.
8. **Durable decisions.** The ledger lives in the report issues (the App's marker) and CD's replies on them (`accept 1 3`, `reject 2: why`, `defer 4`). A proposal matching a decided or open one is shown as one line with its new evidence, never re-proposed.
9. **One report a week, and an empty week posts nothing.** A re-run never posts a second report for the same week. Catch-up starts from the last report's window, so a missed run loses nothing. A report's week is the ISO week its window's midpoint falls in, so a run that ends past midnight into Monday (a delayed schedule, or a run by hand) reports on the week it covers and doesn't take the next Sunday's.

### Forbids

1. A write credential, Bash or network tool in the analysis job.
2. Agent text in the report's structure (headings, links, numbering, the marker), or a link not built from the digest.
3. A fingerprint or evidence id the writer didn't produce or validate.
4. Transcripts as a data source, or agent text in a metrics record.

### Costs

- A weekly Opus run on the Max plan.
- The window's commits are harvested so the analysis can drop already-fixed problems; a busy week means a large digest.
- The analysis can't run code, so it can't measure; numbers come only from the harvest.

---

## Tiers in the factory

The factory routes by `CLAUDE.md` § Three Tiers of Work, with one rule of its own for API and schema
changes, which an unattended run can't negotiate with CD:

- **Additive** changes are **lite**: a new field on a response, a new nullable column, a new endpoint
  that changes nothing existing. Never direct: implement hands them back (`rescope`).
- **Breaking or reshaping** changes are **full**: renaming, removing or retyping fields, changing an
  endpoint's or message's shape, migrating existing data.

A project's `CLAUDE.md` can be stricter; it can't move either kind to direct.

## The stages' sandbox

What every code-writing stage's agent works inside (D2), stated once and mirrored into the skills
that run there:

<!-- MIRROR-SOURCE-START: factory-sandbox -->
- **Bash is sandboxed:** it can write only the workspace and the temp directory, and has no network. Dependencies are already installed; nothing can be installed.
- **No GitHub access:** no `gh`, no push. The issue is in the context file.
- **Off-limits paths:** edits to `.github/`, `.claude/`, `CLAUDE.md`, `.mcp.json` and `.git/` are denied, and the publish job rejects any commit touching a path in `.github/CODEOWNERS` (the project's test and build config, dependency manifests, `[sdlc-root]/` and the like). The SDLC hygiene files are the exception, and you may write them: the discipline parking lots (`[sdlc-root]/disciplines/*.md`) and the knowledge YAMLs (`[sdlc-root]/knowledge/`), except `[sdlc-root]/knowledge/agent-context-map.yaml` and the agent-governing files CODEOWNERS still lists. A knowledge entry the fix makes wrong is corrected in this PR. If the change needs one of them, stop (Edge Cases).
<!-- MIRROR-SOURCE-END: factory-sandbox -->

| Mirror | Copies |
|---|---|
| `factory-sandbox` | `sdlc-implement`, `sdlc-revise` |

---

## Labels

Every factory label. D1 rule 1: an issue carries at most one state label.

The factory owns every label starting `factory:`. `bootstrap.py` creates these and reports one in that namespace it doesn't define, which it never removes (removing a label strips it from every issue that has it). A project with the github-provenance bundle keeps them out of its checkpoint label config, and its audit checks them against this table (`[sdlc-root]/process/github-checkpoints.md` § Labels). A new factory label goes in this table and in `bootstrap.py`'s `LABELS` together.

| Label | Set by | Meaning |
|---|---|---|
| `factory:triage` | CD | Opt-in: run triage on this issue. The apply step removes it. |
| `factory:ready-for-dispatch` | triage | Small and clear. Implement, review, then open a draft PR. |
| `factory:ready-to-plan` | triage | Needs a plan. The triage comment names the tier (lite or full). The run stops at a plan or spec PR. |
| `factory:needs-input` | any stage | Waiting on CD. The question comment carries `<!-- factory-stage: <stage> -->`. CD's reply comment restarts that stage. |
| `factory:wait` | triage | Doesn't fit now. The comment says what would change that. |
| `factory:review-capped` | execute | The review cap was hit. A draft PR is parked with an open-findings table. |
| `factory:advisor` | triage or CD | A property, not a state: planning gets an advisor. Triage sets it when the plan turns on judgment and clears it otherwise; a label CD added always stands. State sweeps leave it alone. |
| `factory:follow-up` | follow-up filer | A property: filed from a merged plan's checklist. Triage runs, then holds; the App's provenance marker, not the label, decides the hold. |
| `factory:go` | CD | Releases a held issue (a follow-up or a split part): starts its triaged stage once, then removes itself. Needs write access. |
| `factory:revise` | CD | On a factory PR: revise it from the review comments since the last revision. A Request-changes review does the same. |
| `factory:escalated` | revise workflows | The PR had its revise runs (3 for code, 5 for a spec or plan) and CD requested changes again. No more automatic runs; CD decides. |
| `factory:gate` | execute or revise | The execution is stopped before a production gate (D4). Its PR's gate run waits for CD's approval in the production environment. |
| `factory:gate-retry` | CD | On an execution PR: build a fresh gate request and start its gate run, after a failed, rejected or refused gate or a stale request. |

---

## Stack Profiles

A stack profile is how the factory builds, installs and checks one kind of project:
`.github/factory/profiles/<name>/`, chosen by `factory.json`'s `stack.profile`. Every job runs in the
profile's image, and the stages run the profile's commands, never the project's own scripts, which an
agent could have edited. A profile has six files:

| File | Run by | Does |
|---|---|---|
| `Dockerfile` | `factory-image`, on a GitHub-hosted runner | The job image: the stack's toolchain and test services, plus what the factory's own steps use (the Bash sandbox's `bubblewrap` and `socat`, `jq`, `git`, `curl`, `unzip`, and `pgbouncer` for the planning tier). No project dependencies. |
| `install.sh <stack.python> <stack.node>` | The job, outside the sandbox, after secrets are out of the environment | Installs the project's dependencies: the implement sandbox has no network. |
| `test-services.sh <socket-dir> <database>` | The job, as root, before the agent | Starts throwaway test services on the job container's loopback, with logins that can't run code, and prints their settings for the project's env file. |
| `with-test-services <command>` | Commands inside the sandbox | Runs a command with the test services' ports reachable through the sandbox's proxy. |
| `services` | `factory-smoke`'s `bash-sandbox` job | The test services `test-services.sh` starts and `with-test-services` forwards, `<label> <port>` a line: the sandbox probe requires each to answer from sandboxed Bash. A missing or malformed file fails the job. |
| `verify [<area> ...\|probe]` | The stages and smoke | The project's checks (tests, lint, type check, build), in the profile's own areas, which `--print` lists; `probe` proves the toolchain and the test database work. Reads its directories from `verify.conf`. |

The interface is the first profile's shape: `agent_job.sh` passes `stack.python` and `stack.node` as
the project's two directories (`verify.conf`'s `python=` and `node=`), whatever the stack. A profile
for another stack uses them for its own directories; renaming them is a change to every project's
`factory.json`, left until a stack doesn't fit two directories. Start from a copy of the nearest
profile, keep its security properties (no superuser test login, services started with an empty
environment, nothing installed inside the sandbox), and prove it with `factory-smoke`.

| Profile | `stack.python`, `stack.node` | `verify` areas | Test services | What the project must meet |
|---|---|---|---|---|
| `python-node` | The Django project; the Vite app (npm) | `python` (pytest), `node` (eslint, `tsc -b`, Vite build) | Postgres 16 and Redis 7 | Django reads the env file; `probe` runs `manage.py migrate --plan` |
| `dotnet-node` | The directory of the solution (or project) `dotnet` builds; the Vite app (pnpm) | `dotnet` (`dotnet test`, Release), `node` (eslint, `tsc -b`, vitest, Vite build) | Postgres 16 | Tests in the categories `Nightly` (long suites on their own schedule) and `External` (they need the network or a secret, which no job has) are left out; `eslint .` must pass, not only the paths the project's lint script names; the default connection string names `stack.database` as database and user (ASP.NET Core reads no env file) |

`verify` calls the tools, never a Makefile or package.json script, so a check a project's build
script chains in (a bundle-size gate, a generated file) is left to CI on the PR. In the sandbox, Unix
sockets are blocked, and MSBuild's worker nodes use them: `dotnet-node` builds in one process
(`-m:1`), and `verify --print` tells the agent to do the same (`dotnet run` and `dotnet ef` ignore
the switch, so they run with `--no-build` after a `dotnet build -m:1`). End-to-end suites
(Playwright) are not in any profile: they need browsers and live servers, and CI runs them.

**What CODEOWNERS must cover, per profile** (Enablement step 9). A revise or continued run installs a
factory branch's dependencies outside the sandbox, and the project's CI builds a factory PR's code.
Both rely on no factory commit having changed a file a tool loads just because it exists. The
publish guard and the branch check refuse only what CODEOWNERS covers, so it must cover each of
these at any depth, whether or not the project has one yet. CODEOWNERS matching is case-sensitive,
so cover every casing a tool accepts.
- **`python-node`:** `requirements*.txt`, `pyproject.toml`, `setup.py`, `setup.cfg`, `pytest.ini`,
  `tox.ini`, `conftest.py`, `sitecustomize.py`, and the Node files below.
- **`dotnet-node`:** `*.csproj` (and `*.fsproj`, `*.vbproj`), their `.user` files (MSBuild imports
  `<project>.user` when it exists), `*.props`, `*.targets`, `*.rsp` (`Directory.Build.*`,
  `Directory.Packages.props` and `Directory.Solution.*` among them), `*.sln`, `*.slnx`, `*.slnf`,
  `global.json`, `nuget.config`, `NuGet.config` and `NuGet.Config`, `.config/dotnet-tools.json` and a
  root `dotnet-tools.json`, `*.runsettings`, `xunit.runner.json`, `.editorconfig`, `.globalconfig`,
  and the Node files below. A project file can run code during `dotnet restore`, so owning `*.csproj`
  makes a new project or package CD's change; the implement sandbox can't fetch a package anyway.
- **Node, in both:** `package.json` (`install` runs its lifecycle scripts), `.npmrc`, and the eslint,
  TypeScript, Vite and Vitest configs; for npm (`python-node`) `package-lock.json`, and for pnpm
  (`dotnet-node`) `pnpm-lock.yaml`, `pnpm-workspace.yaml` and `.pnpmfile.cjs`.

---

## Enablement

The bundle installs inert: nothing runs until a person adds `factory:triage` to an issue, and the
first run fails without the setup below, done in order. Steps 3 to 5 replace the seed's placeholders
in `factory.json`; after each settings change, run `python3 .github/factory/render.py` and commit the
settings and the workflows to `main`. `python3 .github/factory/bootstrap.py` checks steps 2 to 9 and
changes nothing; with `--apply` it does step 6, and only once the placeholders are gone. It reports,
and never sets, the secrets, the App's install, CODEOWNERS and the `main` ruleset, which stay CD's. It
needs an organization owner's `gh` login (`admin:org`) for the runner groups and the App.

1. **An organization; for a private repository, on GitHub Team or above.** The runners register to
   an organization runner group, which a personal account doesn't have. The credential boundary
   (D2) rests on environment secrets, environments deployable from `main` only and a ruleset
   requiring code-owner review, which a private repository has from Team up; the production tier's
   required reviewer (D4 rule 5) on a private repository needs GitHub Enterprise. Why an
   organization, not a repository's own runners: one pool of hardened runners serves every project,
   and the group's selected-workflows list keeps a project's other workflows off them.
2. **Settings.** In `.github/factory/factory.json`, the `stack` block: the profile, the project's two
   directories (§ Stack Profiles), its env file, its test database name, and workspace paths its code
   reads. The profile is rendered into `factory-image` (it builds that profile's `Dockerfile`), so
   render after choosing it, or CI's render check fails. `.gitignore` must cover the env file and
   `.factory/` (the jobs' working files and the profile's caches): a run that leaves an untracked file
   isn't published. It must also cover `.github/factory/host/reg-token`, the runner registration
   token step 8 puts there. Tests that need fixtures from a secret-holding source get them through the
   `fixtures` block (D2 rule 7); leave its `path` empty for none. Write `triage-policy.md` (its
   direction, rules, containers, plan triggers and external sources). The planning tier (D3) is
   required; its database is optional. To give the plan and spec stages one, fill `planning.json` and
   create the read-only role it names (D3 rule 3); list services in `services.json` (D3 rule 4). Leave
   both empty for none.
3. **The job image.** Set `image.repository` to where the organization publishes it (for example
   `ghcr.io/<org>/factory-job`), render, and push to `main`: `factory-image` builds the profile's
   `Dockerfile` on a GitHub-hosted runner and publishes it (or run it by hand). Its run on the
   install's own push fails, publishing to the placeholder; this one is the first that counts. Copy the digest from
   its run summary into `image.digest` and render again. Every factory job runs in this image, pinned
   by its digest. Projects on the same profile can share one image: give each repository read
   access to the package.
4. **The echo service.** Smoke proves the sandbox's credential masking against a host that echoes
   each request's headers back. Deploy `.github/factory/echo/worker.js` as a Cloudflare Worker on a
   `workers.dev` address (for example `npx wrangler deploy .github/factory/echo/worker.js --name
   factory-echo --compatibility-date 2025-01-01`), or run `echo/server.py` on any host behind HTTPS,
   and set `smoke.echo_host` to its host name. It stores nothing, and receives only smoke's
   throwaway values; one serves the whole organization.
5. **The App.** `python3 .github/factory/create_app.py <organization>` creates the factory's GitHub
   App from its manifest (Contents, Issues and Pull requests read and write, Metadata read; no
   webhook, no `workflows` or `actions` permission), writes its bot user into `factory.json` and its
   private key to a new file only you can read. Install it on the repository from the link it
   prints. One App serves the whole organization: another project installs the same App and copies
   `app` into its own `factory.json`.
6. **`bootstrap.py --apply`.** Creates the labels (§ Labels); the environments, each deployable
   from `main` only: writer (`factory-writer`), planning (`factory-planning`) and, with the production
   tier, production (`factory-production`, CD the required reviewer); and the runner group
   (`factory-pool`) with this repository and its agent workflows, or adds them to it. With the
   production tier, `factory-gate.yml` goes to the project's own group instead
   (`factory-pool-<repository>-prod`, on the host that runs its production). Through the API, an
   update to a group replaces its selected-workflows list with the list it sends (an omitted list
   empties it), and one that sends `visibility` empties its repository list: send the whole workflow
   list and never `visibility` (`bootstrap.py` does).
7. **Secrets.** In `factory-writer`: secret `FACTORY_APP_PRIVATE_KEY` and variable
   `FACTORY_APP_CLIENT_ID` (the commands `create_app.py` printed; then delete the key file). In
   `factory-planning`: `FACTORY_DB_READER_PASSWORD` with a planning database, and `FACTORY_SVC_1`..`4`
   for services. Repository secrets: `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`; never an
   organization secret), optionally `CONTEXT7_API_KEY`, and the one `fixtures.secret` names, if any
   (read-only; only the fixtures job references it).
8. **The runner host.** A Linux host with systemd, nftables, `python3`, rootless Docker's extras
   (`docker-ce-rootless-extras`) and room for the runners' work and images. From a checkout of `main`,
   set the host's own settings in `.github/factory/host/host.conf`; then, for each tier, write a runner
   registration token (`gh api -X POST orgs/<org>/actions/runners/registration-token --jq .token`) to
   `.github/factory/host/reg-token` (mode 600) and run `sudo bash .github/factory/host/setup.sh` (the
   strict tier) or `sudo TIER=planning bash .github/factory/host/setup.sh` (the planning tier), and
   `sudo TIER=ci bash .github/factory/host/setup.sh` for the CI tier if the project needs one (step
   10). It creates each tier's user, rootless Docker, firewall and runners, and registers no runner
   whose jobs can reach the host or the LAN. Put the host's own LAN and VPN addresses in
   `factory.json`'s `smoke.host_probes`, so smoke checks them too. One host serves the whole
   organization, and can serve other organizations too: each one after the first sets `RUNNER_INSTANCE`
   in its `host.conf` and gets its own users, firewall tables and services, isolated from the others'
   as from the host. Setup refuses runners registered to another organization, and a planning database
   port is only ever the organization's own. Each tier has one designated checkout, recorded in
   `/etc/factory-runner/tiers/<unit>`: setup refuses a run from another repository's, whose `host.conf`
   would re-cap or re-label a tier it doesn't own. The record is made only when the operator names
   the repository and the tier, so the first checkout to run doesn't claim a tier by default: the
   first run for a tier is `sudo TIER=<tier> TIER_OWNER=<owner>/<repository> bash
   .github/factory/host/setup.sh`, from that repository's checkout. Each tier's firewall table is loaded again whenever
   `nftables.service` starts or reloads, since its stock ruleset begins with `flush ruleset`, and after it stops,
   since its stock `ExecStop` flushes it. On a host running Tailscale, each runner user is denied
   `/run/tailscale` by an ACL that `tailscaled` reapplies on every start: its local API dials tailnet peers as
   root for any local user, past a firewall that matches the user. The firewall rejects all IPv6 for the runner users (a host's global addresses and its
   LAN's global prefix would otherwise be reachable), and the isolation test probes IPv6 too. Runners
   never update themselves (`--disableupdate`): they stay at `setup.sh`'s `RUNNER_VERSION`, whose
   checksum it verifies. z-sdlc bumps it within 30 days of each actions/runner release, because GitHub
   stops sending jobs to older runners. After the migration that brings a bump, run each tier's setup
   again from its checkout: it upgrades each idle runner in place. Put `RUNNER_HOME_BASE` where root
   owns every directory from it up to `/`, writable by no one else: whoever owns or can write a
   directory above a runner's home can move the home aside and put another in its place. Setup warns
   when that isn't so (a base under a person's own directory works, but trusts that person).
9. **CODEOWNERS and the `main` ruleset** (D2 rule 6): code owners on `.github/`, `.claude/`,
   `CLAUDE.md` at any depth, `.mcp.json`, `[sdlc-root]/` and the test and build configuration,
   including every file the profile's tools load just because it exists (§ Stack Profiles, What
   CODEOWNERS must cover), with owner-less lines last for the discipline parking lots, the knowledge
   YAMLs (except the agent-governing ones) and the SDLC changelog; code-owner review required on
   `main`. The seeded `tests/test_codeowners.py` checks the file against the guard; until it exists
   it fails, and its path lists are the project's to extend (its test and build configuration, the
   profile's list, its source paths).
10. **CI**, required on `main`: `python .github/factory/render.py --check`, then
    `python .github/factory/workflow_policy.py .github/workflows`, then
    `python -m unittest discover -s .github/factory/tests` (with PyYAML; with a CI tier, on a
    GitHub-hosted runner, and `FACTORY_DOCKER_SMOKE=1`, so the tier's job flags are tried on a real
    Docker daemon, which the tests' fakes can't stand in for). The policy reads every
    workflow, the project's own included, and scans the local composite actions they use: run it
    before making it required. A CI job on the organization's own GitHub-hosted (larger) runners
    needs its label in `factory.json`'s `policy.hosted_labels`. A job that must stay on a
    self-hosted runner outside the factory container needs an entry in
    `policy.self_hosted_exemptions` (its workflow, job and reason). An exemption lifts only the
    container rule, the last of the rules below, so its reason says how that runner is isolated
    instead. The other rules below still apply to the job.

    **The project's existing CI runs agent-written code.** Factory branches live in the repository,
    so a factory PR's `pull_request` runs get the repository's secrets. Before the first run, hold
    every job that builds, tests or lints a PR's code to an agent job's rules:
    - no secret in that job, whether before or after the PR's code runs. A build step can write
      `$GITHUB_ENV` or `$GITHUB_PATH` and redirect every later step;
    - `persist-credentials: false` on its checkout, and a read-only token;
    - a GitHub-hosted runner, or a self-hosted one only inside a container, as the factory's own
      jobs are: the CI tier below.

    A job that needs a secret (a fixture fetch) runs the default branch's code, as the fixtures job
    does (D2 rule 7).

    **The CI tier.** A project CI job that outgrows GitHub-hosted runners, such as an end-to-end
    suite, runs on the CI tier: one disposable runner per job, on the runner host. The label is
    `runners.ci` (`factory-ci`) and the runner group `runners.groups.ci` (`factory-ci`), as with
    CD's decision (2026-10-13).
    - **How it works.** Each of `CI_RUNNERS` systemd slots runs `host/ci_launcher.py`, one job per
      cycle:
      1. It mints a just-in-time runner registration with the runner-registration App, labelled
         `self-hosted` and the tier's label: a just-in-time runner gets only the labels it's given,
         never the ones `config.sh` adds.
      2. It starts a fresh container from the tier's job image, as the runner user. The container
         has that job's CPU, memory, process and log caps, `NET_RAW` and `MKNOD` dropped, and a
         network of its own.
      3. It watches the container until its one job ends. GitHub, never the container, says
         whether the runner is online and busy. The container is killed when:
         - its job has run `CI_JOB_HOURS` (the job's own `timeout-minutes` is the first limit);
         - its runner has idled `CI_IDLE_HOURS` (recycled);
         - GitHub has removed its runner (the job is over) while the container still runs;
         - its runner went offline after being online, or never came online;
         - it is older than `CI_IDLE_HOURS` + `CI_JOB_HOURS`, whatever GitHub says;
         - free space under the runner's home falls below `CI_MIN_FREE_GB` (no cycle starts below
           it either).
      4. It removes the container and the runner's registration. A slot that stops mid-job
         (setup, a reboot, a trip) cleans up first, and a registration it couldn't remove is
         removed by its next cycle: the slot keeps it in `/var/lib/factory-runner/<unit>`, which
         outlives a reboot.

      While GitHub can't be read (an outage, a revoked key), every limit that needs its answer
      waits: the lifetime cap and the disk floor are what bound a container then. A token GitHub
      refuses (401) is minted again at once; a 403, which is also its rate limit, isn't.

      The job runs inside the container, runner and all, so whatever a pull request's code does
      there, to the runner's own processes included, ends with the container.

      Recycling an idle runner relies on GitHub refusing to remove a busy one (it answers 422): a
      job assigned between the last poll and the removal then keeps its runner. To see that on a
      new tier without risking a real job, dispatch a job on the label that only sleeps (no
      checkout, no secret), and while it runs, `gh api -X DELETE orgs/<org>/actions/runners/<id>`
      its runner: expect 422, then let it finish. If GitHub ever removed it instead, that one job
      would lose its runner and fail, and the launcher's handling would hold the rest. Setup's
      restart of an idle slot asks GitHub first and leaves a busy runner alone, so only that
      window between a poll and the removal depends on the 422.
    - **The threat model.** A pull request's run executes the pull request's own workflow, and
      the group can't be restricted to workflows (next point). So the policy is a merge gate,
      not an execution gate, and the boundary is what holds a hostile job:
      - each job's disposable container;
      - the runner user's own uid, firewall (no host, no LAN, no IPv6) and caps;
      - root never running or parsing anything that comes out of a container, beyond its exit
        status.

      A container escape is a compromise of the runner user, held by that outer boundary as on
      the strict tier, and it lasts until setup rebuilds the image.
    - **The group is restricted to repositories, not workflows.** A pull request's run comes from
      its merge ref, which a group's branch-pinned workflow list never matches. Its jobs would
      wait forever.
    - **The runner-registration App** is a second GitHub App. Create it with
      `create_app.py <org> --runners` and install it on the organization (it needs no
      repository). Its one permission is the organization's self-hosted runners (write), and
      GitHub has no narrower credential that can register runners. That permission reaches every
      runner group in the organization. A holder of the App's key can:
      - register a runner into any group with any labels, and so take that group's jobs and
        their secrets, the strict tier's agent jobs among them;
      - move runners between groups;
      - change a group's repository and workflow restrictions;
      - delete runners.

      The launcher narrows each token it mints to that permission, but nothing narrows the key.
      Before the CI tier, no long-lived credential that can register runners lived on any host
      (the other tiers register with an hour-long token CD makes), so the key is the most
      sensitive thing on the runner host:
      - It goes straight to `/etc/factory-runner/factory-ci/app.pem`, root-only, never into a
        checkout: `sudo install -D -m 600 -o root -g root <key> /etc/factory-runner/factory-ci/app.pem`.
        Setup refuses to run while a key sits in the checkout's `host/` directory.
      - Root on the host already holds every local runner's credentials, so the key adds the
        groups' settings and other hosts' groups to what root there can reach.
      - Delete the copy `create_app.py` writes, and every other, once the key is installed. Keep
        `/etc/factory-runner` out of the host's backups.
      - On any doubt, revoke the key in the App's settings (Private keys) and install a new one.
        Revoking it, or uninstalling the App, stops the CI tier and nothing else.
      - `bootstrap.py` reports a factory group whose visibility, public-repository or workflow
        restrictions drifted, each time it runs. The CI tier's check re-reads its own group's.
        The runner audit (step 12) compares every group, every hour, off the host (exactly, but
        the CI tier's by its runners' name pattern, most-at-once and labels): set
        it up before the CI tier takes jobs.
    - **The job image** is built on the runner host, as the runner user, from a root-owned copy of
      the build context. The copy keeps links as links, and setup refuses a Dockerfile or context
      that resolves outside the checkout. The image is the project's toolchain (`factory.json`'s
      `ci` block: a Dockerfile, its context and static build arguments, on a Debian or Ubuntu base
      pinned by digest) with `host/ci-runner.Dockerfile`'s runner on top, at `setup.sh`'s
      `RUNNER_VERSION`. The image is chosen before a job is assigned, so a pull request can't
      bring its own. Keep versions that pull requests bump (a browser for a test framework, say)
      out of the image and install them in the job, or run setup again for each change.
    - **Setup order:**
      1. `create_app.py <org> --runners`, and install the App on the organization.
      2. On the runner host: the key installed root-only (above), and `CI_APP_CLIENT_ID` in the
         owning checkout's `host.conf`.
      3. The `ci` block in `factory.json`, a workflow on the label, and a commit.
      4. `bootstrap.py --apply`, which creates the group once a workflow uses the label.
      5. From the owning checkout, the first time:
         `sudo TIER=ci TIER_OWNER=<owner>/<repository> bash .github/factory/host/setup.sh` (step 8).
      6. A job moved onto the tier from another runner leaves its earlier runs queued for the old
         label, for up to a day: cancel them.

      Setup checks the settings and the key before it changes anything on the host, and the App's
      installation and the group before it builds anything. Run it again after a toolchain
      change or a launcher update. A slot whose runner isn't running a job restarts at once; one
      that is keeps its job, and takes the new image and launcher at its next cycle. Setup keeps
      the job image while its inputs are unchanged (the toolchain's Dockerfile and context, the
      build arguments, the runner's version): a rebuild of the same inputs still makes a new
      image. `sudo CI_REBUILD=1 TIER=ci bash .github/factory/host/setup.sh` rebuilds it anyway,
      for the base image's and packages' updates.
    - **The checks.** `ci_launcher.py check` runs before any slot starts (at boot too) and every
      6 hours. It checks:
      - the firewall table (loaded, and as setup loaded it, by fingerprint: flushing a chain or a
        set leaves the table there, changed), the slice's caps and the delegated controllers that
        make a container's caps hold;
      - free space (logged, not tripped: below the floor no cycle starts, and a running job is
        killed);
      - the group's settings;
      - a probe on the host, as the runner user with no Docker: the host, the LAN gateway and
        IPv6 closed;
      - a probe from a container of the job image with a job's own flags: the host and LAN
        closed, the job's exact caps in force, and a listener on another network unreachable,
        so concurrent jobs can't reach each other.

      At boot the check waits up to ten minutes for the runner user's Docker daemon. A timer
      checks the firewall table every minute, and looks again a few seconds on before it trips,
      since `nftables.service`'s own restart flushes the table for a moment. A failure, or a check
      that doesn't finish, writes a marker no slot starts past. It stops the slots, the timers and
      the runner user's whole session, a job mid-run included, and disables the slots, the gate,
      the timers and the runner user's linger, so a reboot brings none of it back. The tier stays
      stopped until someone fixes the cause and runs setup again, which enables them all. The
      internet or GitHub out of reach is liveness, not isolation, and is only logged.
    - **Writing the job:** `runs-on: [self-hosted, factory-ci]` (the form bootstrap reads); no
      `container:` and no `services:`, since the job runs in its runner's container and a database
      starts in the job; no `docker://` step; explicit read-only permissions;
      `persist-credentials: false`; no secret and no job token. The policy holds every job on the
      label to all of that.
    - **Capacity.** The `CI_JOB_*` settings cap each job. The slice caps them together:
      `CI_MEMORY_HIGH` must cover `CI_RUNNERS` × `CI_JOB_MEMORY` + 2G, `CI_CPU_QUOTA` is what
      leaves the host's own work its cores, and the slice's process cap is `CI_RUNNERS` ×
      `CI_JOB_PIDS` + 4096 (the runner user's manager and daemon live there too). Every tier's
      ceilings are limits, not reservations: together they can come to more than the host has.
      Jobs don't swap (`--memory-swap` equals `--memory`), so memory pressure ends in OOM kills (exit
      137 in a slot's journal). Compare the tiers' ceilings together with the host's memory and its
      other tenants; `CI_RUNNERS=1` is the lever.
    - **Browser suites need more than their test count suggests.** Chromium in a container renders
      WebGL in software (SwiftShader), at about 7 CPUs a browser before it stops being latency-bound.
      The pilot project's 32 two-browser tests, which pass in 10 minutes uncapped, timed out at 8 and
      16 CPUs and passed at 24 (2026-10-15). Size `CI_JOB_CPUS` from a measured run, and expect one
      such job at a time (`CI_RUNNERS=1`).
      - **CPU:** a CPU quota a CPU-bound job outgrows stalls it, and pinning it to as many CPUs
        removes the stalls but not the shortage (the same run, pinned to 8, used 4), so measure
        rather than pin.
      - **Shared memory:** give Chromium a real `/dev/shm` (`CI_JOB_SHM`, 4g for that suite) and turn
        off Playwright's default `--disable-dev-shm-usage` (`ignoreDefaultArgs`). Otherwise
        Chromium's shared memory lands in the container's `/tmp`, inside its memory cap, and every
        round of a test slows tenfold.
      - **Fonts:** put the project's fonts in its toolchain image: a bare image's fallback font
        changes layouts that tests hover over. No container's writable layer
      has a size cap, so put `RUNNER_HOME_BASE` on a filesystem of its own: a full disk then stops
      only the factory. Check the jobs' `timeout-minutes` against the first capped runs.
    - **Runner versions.** A just-in-time runner takes its settings from GitHub, so it may update
      itself when GitHub asks, inside its throwaway container. Bumping `RUNNER_VERSION` (and
      running setup) keeps that from costing every job a download.
11. **Smoke.** Run `factory-smoke`; every job must pass before the first issue (D2 rule 5).
12. **The runner audit,** required with a CI tier, from before its App's key goes on the runner host
    (step 10), and worth having without one. That key can change any runner group. `runner_audit.py`
    compares the organization's runner groups, every hour, with an expected state:
    - the set of groups, each by its name and ID (`<name>#<id>`: an enterprise's shared groups
      can have the same name as the organization's own, such as two `Default` groups), and each
      group's visibility, public-repository setting, whether it's the enterprise's
      (`inherited`), repositories, workflow restriction and workflows;
    - each group's runners, with their IDs and labels. The CI tier's group is a name pattern, a
      most-at-once and labels, since its runners come and go;
    - the factory's labels on any runner outside the groups that carry them.

    Anything different, or a run that can't read all of it or runs out of time, fails the run and
    opens or updates an issue (mentioning the logins in the repository's `RUNNER_AUDIT_NOTIFY`
    variable). A failed scheduled run also emails whoever last changed the schedule: the one
    channel no App can touch. It runs from one private repository per organization, on GitHub-hosted
    runners only, with its own App: read access to the organization's self-hosted runners and
    nothing else. The expected state and the audit itself are written into the workflow file, since
    neither of the factory's Apps can change a workflow. That holds only while no other App that
    can is installed on the audit's repository (setup step 2). Choose a repository the factory's App
    isn't installed on if you can: a factory token can close or bury issues where it is. Not seen:
    - anything done and undone between two runs: a runner registered into a group that takes one
      job and goes, or a group opened to another repository or workflow for one job and restored.
      The organization's audit log would see both: its REST API (`GET orgs/<org>/audit-log`, on
      GitHub Enterprise Cloud) records each runner's registration. The audit doesn't read it yet;
    - a runner in the CI tier's group that fits its pattern and most-at-once (its jobs hold
      read-only tokens);
    - repository-level runners;
    - a run that never happens: silence isn't an all-clear, so look at the workflow's runs now and
      then;
    - the audit's own job, taken by a runner the key's holder registers with a GitHub-hosted label
      (`ubuntu-latest`) just before a run and removes after it: that runner answers for the audit.
      A runner left with such a label is drift, and so is a group open beyond the repositories it
      lists (visibility `all`, or `private`: every private repository) or one the audit's own
      repository may use (setup step 2). Each run's job record names the runner that took it.

    Setup:
    1. `create_app.py <org> --auditor`, installed on the organization for the audit's repository.
    2. In that repository, the variable `RUNNER_AUDIT_APP_CLIENT_ID`, the secret
       `RUNNER_AUDIT_APP_KEY` and, optionally, `RUNNER_AUDIT_NOTIFY`; then delete the key file.
       Keep that repository out of every runner group, the default one included, and make every
       group's visibility `selected` (the default group's is `all` until changed; `private`, every
       private repository, is as open): the audit reports either as drift whatever the expected
       state says, since a runner there could take the audit's own job and answer for it.
       Check the repository's installed Apps too (its settings → GitHub Apps): none may write
       workflows, contents, issues or actions, and an App installed on all of the organization's
       repositories counts (a coding assistant's App, say). Narrow such an installation to
       selected repositories, without this one. An App that can write there can rewrite the
       expected state or the audit, close its alarm issues, or disable the workflow.
    3. From your own machine (it reads with your `gh` login, an organization owner's; never on a
       runner host): `runner_audit.py snapshot <org> > expected.json`, reviewed, so that every
       group and runner in it is one the organization means to have. Turn the CI tier's group's
       runners into `{"pattern": "^<prefix>-ci-[0-9]+-[0-9a-f]{6}$", "max": <CI_RUNNERS>,
       "labels": ["factory-ci"]}`, with the host's runner name prefix.
    4. `runner_audit.py workflow expected.json > .github/workflows/factory-runner-audit.yml` in the
       audit's repository, committed; run it once by hand. After any intended change to the
       groups or their runners (a new runner, a re-registration, a new project's workflows),
       regenerate it the same way. The schedule is hourly; `--cron` tightens it.
