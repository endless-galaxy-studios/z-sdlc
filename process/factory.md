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
| `.claude/skills/sdlc-triage`, `sdlc-reproduce`, `sdlc-implement`, `sdlc-revise` | The stages' skills. Headless only: the workflows run them, so they have no commands | z-sdlc |

Not installed: the production tier, its broker, operations catalog, runner and host setup (D4
rule 16). It is per project and per host (`[sdlc-root]/process/production-gates.md` covers gates in
plans).

**Names.** Runner labels, runner groups and environments are defaults in `factory.json`, shared by
every project in an organization; a project that changes them changes them there, and the workflows,
`workflow_policy.py`, `bootstrap.py` and the host setup follow. The App, the job image and the echo
service are the organization's own: the seed holds placeholders for them, which Enablement fills
(steps 3 to 5).

**Limits of this version.** The project's SDLC root must be `ops/sdlc` (the scripts and the gate
digest name it). The runners need Linux hosts (systemd, nftables, rootless Docker). Three stack
profiles: `python-node` (Django and Vite, npm), `dotnet-node` (.NET 10 and Vite, pnpm) and
`python-uv-node` (uv projects with alembic, Postgres 17 with pgvector, Redis, and a pnpm app); another
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
   - **the env scrub write-protects names in the working directory** (as read from Claude Code 2.1.330, and seen in a run of 2.1.316, the action's pin): `package.json`, `.npmrc`, npm's, Yarn's, pnpm's and Bun's lock and config files, `.env` and its `.local`, `.development`, `.test` and `.production` forms, `scripts/`, `node_modules/.bin`, `.github`, `.claude`, `.gitmodules`, `.git`'s `config`, `hooks` and `info/exclude`, and `HOME`'s shell files. Sandboxed Bash can't create or change them at the root, so a step that writes one there (a script that regenerates `scripts/`, an install that writes `node_modules/.bin` at the root) fails in a stage. A name that doesn't exist becomes an empty placeholder file, listed in `.git/info/exclude`, so it's never committed (the scrub doesn't list the sandbox's own mount points at the root; the job does: rule 4). An empty root `package.json` breaks every Vite and Vitest config load below the root, since esbuild reads each `package.json` up the tree. A project whose `stack.node` is below the root therefore keeps a valid, code-owned root `package.json` (`{"private": true}`): `bootstrap.py` reports one missing, the seeded CODEOWNERS test checks it's owned (with a `package.json` in each folder between, which esbuild reads too), and `verify probe` loads the Vite and Vitest configs inside the sandbox, so `factory-smoke` fails on a config that can't load. Before it did, the pilot project's first real reproduce run was the first to hit this, and came back `blocked`;
   - a sandbox settings file, copied out of the workspace before the agent starts and loaded twice: with `--settings` (which makes the sandbox admin-required, so the repository's own settings can't loosen it) and as the action's `settings` input (user scope, for the user-scope-only keys). It sets `sandbox.enabled`, `failIfUnavailable: true`, `allowUnsandboxedCommands: false`, the weaker-isolation switches off, `network.strictAllowlist: true` with `allowedDomains` limited to the registries that stage needs, `filesystem.denyRead` on the runner's mounts, `credentials.envVars` `deny` for every credential the job holds (the OAuth token, `GH_TOKEN`, `GITHUB_TOKEN`, the action's `OVERRIDE_GITHUB_TOKEN` and `DEFAULT_WORKFLOW_TOKEN`, `CONTEXT7_API_KEY`, the Actions runtime tokens), and `disableAllHooks: true`;
   - `--strict-mcp-config`, because the action forces `enableAllProjectMcpServers` and MCP servers run outside the sandbox. The stage's MCP config holds only Context7, as a server named `context7`, so a project agent whose `tools:` line names Context7 by a plugin install's names reaches it here only by also naming `mcp__context7__resolve-library-id` and `mcp__context7__query-docs` (the project's CLAUDE.md, "Agent tool grants name each tool");
   - an explicit `--setting-sources` that never includes `local`: `user` where the stage needs nothing from the repository, `user,project` where it needs the repository's skills and `CLAUDE.md`. In `-p` mode, project and local settings apply their `env` at startup (`LD_PRELOAD` and `NODE_OPTIONS` aren't filtered), so `project` is loaded only from a ref whose `.claude/`, `CLAUDE.md` and `.mcp.json` CD has reviewed: `main` (CODEOWNERS), or a factory branch whose patch the writer job refused to let touch them;
   - container `options`: the narrow seccomp profile (Docker's default plus `unshare`, `clone`, `setns`, `mount`, `umount2`, `pivot_root`, `mount_setattr`, `open_tree`, `move_mount`) and `--security-opt systempaths=unconfined`;
   - **file tools are outside the sandbox:** Read, Edit and Write run in the Claude Code process, which holds the token. The stage's tool policy denies Read on `/proc`, `/dev`, `/sys` and the runner's mounts, and Edit on system directories, runner state, `HOME`, temp and mount points, `.git`, `.github`, and `.claude/`, `CLAUDE.md` and `.mcp.json` at any depth (deny rules also match a symlink's target). Skill shell execution is off;
   - **a service the job starts outside the sandbox that sandboxed Bash can reach is part of the boundary**. Test databases run outside the sandbox with open network, on the job container's loopback, reached through the sandbox's HTTP proxy with `localhost` as the only local entry in `allowedDomains`. Never `allowAllUnixSockets`: it drops the sandbox's seccomp helper, whose nested PID namespace and clean environment hide bubblewrap's own environment, and a smoke probe showed sandboxed Bash then reads the job's GitHub token from `/proc/1/environ` (the env scrub leaves GitHub tokens in place) and reaches Claude Code's own Unix sockets. Each runs least-privileged (no Postgres superuser, so no `COPY ... TO PROGRAM`; Redis without `MIGRATE`, `REPLICAOF`, `MODULE`, `CONFIG` and the like), starts with an empty environment, and the start script checks all of it on every run;
   - `network.allowedDomains` empty for a stage that installs nothing (implement): a package registry that accepts publishes is a way out. The one exception is the browser host's front end for the project's Playwright, one address and port, when the stage has the browser route (D6).
3. **Writer jobs refuse to post** token-shaped strings, images and embeds. An agent-chosen image URL is a way to send data out. The one kind of link a writer job adds that isn't in agent text is to its own run's artifacts, which it builds itself from the run's URL and an artifact's ID (D6 rule 7).
4. **After an agent step that can write the workspace, the job trusts nothing the agent could have touched.** Later steps in that job run only code copied out beforehand to places the sandbox can't write, call `python3 -I` by absolute path, and run git with hooks and fsmonitor disabled, only after checking that `.git` is a real directory that wasn't redirected (`commondir`, `alternates`), its hooks are unchanged and its config holds only allowlisted keys (read with `git config --file`, which follows no include), and the index holds no submodule; and never into a nested repository (`--ignore-submodules=all`): `git status` runs a staged submodule's own config, filters included, which a planted repository outside `.git/` can define (review round 2, reproduced). The sandbox leaves empty read-only placeholder files behind at protected paths it mounts over (`commondir`, `alternates`, `config.worktree`); the guard removes empty ones and refuses any with content. At the workspace's root, where a name it mounts over (`.bashrc`, `.gitconfig`, `.vscode` and the like) doesn't exist, it makes an empty file to mount on, which sandboxed `git status` lists as untracked while a command runs, and removes it when the command ends, unless the sandbox was killed first. Both were seen in the pilot project's first implement run: its agent saw all nine names in every `git status` and staged none, and its bundle step found none. So `agent_job.sh workspace` lists each of those names that doesn't exist in `.git/info/exclude` before the agent starts, with the tool state the stack profile names (`profiles/<profile>/excludes`: ASP.NET Core's `.aspnet/` for `dotnet-node`, § Stack Profiles), so that the agent's `git status` doesn't show them to stage. The same patterns go in a frozen copy (`$CHECKS/excludes`), which the bundle step's check for uncommitted changes reads, since whether Claude Code keeps the job's lines in `.git/info/exclude` when it writes its own isn't seen yet. That check lists every untracked file by its path, so a failure names what wrote it. The bundle step removes an empty, untracked placeholder before it checks, and fails on any other the excludes hide. It first prints what it finds at the root and the exclude's patterns. The job removes `origin` before the agent step, because the action writes the job token into its URL, and passes the factory's bot identity so the action's git setup commits as the factory. The job removes `.git` at the end, because `actions/checkout`'s post step runs git in the workspace. The commits themselves are judged by a writer job on a clean GitHub-hosted runner.
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
   - CODEOWNERS on `.github/`, `.claude/`, `CLAUDE.md`, `.mcp.json`, other agents' and tools' configuration, `[sdlc-root]/` and the test and build config, enforced by the `main` ruleset. The discipline parking lots (`[sdlc-root]/disciplines/*.md`) and the knowledge YAMLs other than the governing ones are the exception: an owner-less line unowns them so agents can add entries. The writer's guard follows GitHub's last-match-wins rule, and CD still sees each entry in the PR diff. Unlike GitHub, the guard matches an owned line in any case and Unicode normalization, refuses agent configuration by name in any case, and refuses a path that collides with another on a case-insensitive checkout: on CD's Mac, `.Claude/settings.local.json` is `.claude/settings.local.json`;
   - a team of people approving every file, in the `main` ruleset's pull-request rule (its required reviewers: file pattern `*`, at least one approval). GitHub asks no code-owner review of a PR when the PR's author is the only code owner of what it changes, and it counts an App's approval toward the required approvals. Without the team, then, an App that can review PRs (the factory's own, an agent session's, any other the organization installs) can approve a PR CD opened, and with contents write merge it, and the ruleset's history records a pass. A team holds accounts, never an App. With it, every merge into `main` carries a person's approval or is recorded as a bypass. A session acting as CD can still merge with CD's bypass, and only that record shows it (proven on a scratch repository, 2026-11-11);
   - the factory's own GitHub App (Z Software Factory) has no `workflows` permission, so no factory token can push a workflow change. Its key is in the `factory-writer` environment, which only `main` can use, so a factory branch can't mint the token;
   - the sessions App, which Claude Code sessions on CD's machine work as in the product's repositories (Enablement step 13), has none either, and a session's token is narrowed to one repository and to the product's code, its PRs and issues, and reading CI. Infra and setup, workflows included, are CD's own login;
   - the runtime sandbox probe (rule 5).

   CI's `workflow-policy` check catches accidental drift from these rules on every PR. It is not a security control: a workflow is a program (expressions, `$GITHUB_ENV` writes, other actions), so a static check can't be complete against someone editing workflows on purpose. Its known gaps are under Leaves open.

7. **Fixtures a project's tests need from a secret-holding source come from a hosted fixtures job on the default branch, as an artifact; the agent job never holds the secret** (CD, 2026-10-13). `factory.json`'s `fixtures` block names the command, its one repository secret, the directory it fills (gitignored) and the cache key. The implement and revise workflows run it in a `fixtures` job on a GitHub-hosted runner, from the default branch's checkout, so a factory branch an agent wrote never runs with the secret. The job restores the directory from the Actions cache first (the project's CI can fill the same entry), so the source is called only on a miss. It refuses fixtures that contain the secret, then hands the directory over as an artifact, which the agent job puts in the workspace before the agent starts. `workflow_policy.py` holds the job to this shape, and refuses the secret anywhere else in the workflow.
8. **A project may opt in to a service key that can do more than read** (CD, 2026-11-03). Examples: a memory service's project key, which can write and delete; a model provider's key, which can spend. The exposure is accepted, not mitigated: the organization's repositories are private, and the factory does not design against a prompt-injected agent for these keys. What holds:
   - **The project opts in per service,** in its own CODEOWNERS-reviewed settings. The entry says what the key can do (read, write or spend). Nothing is on by default, so a project that doesn't opt in keeps every other rule here unchanged.
   - **The tool list allows only the tools the entry names.** A tool left off it is refused: auto mode can't prompt, so no consent is implied. Writes the project wants kept are staged in the agent's result, shown in the PR, and stored after CD merges, by a writer job holding its own key.
   - **One key per repository,** scoped to that repository's own workspace or account, never an organization-wide secret. A spending key carries a limit set at the provider.
   - **A key the agent can read is removed at the end.** A memory service whose plugin reads its key from a file in the checkout gets the key seeded there before the agent step. The file is deleted before seeding, and again in an always-run step right after the agent step, before any commit, upload or cache save. The file must be git-ignored, and the seed refuses to write otherwise.
   - **Smoke expects a declared key, and nothing else.** It treats the declared key as present by design. Every other credential must still be found nowhere.

   The mechanism is the project tool list. Its read-only form exists: rule 9's `tools`. Opting in to a key that writes or spends isn't built yet (`services.py` still requires `read_only`), so no project can opt in.
9. **The execution stages may use read-only MCP services from the reviewed list** (CD, 2026-11-05; planning-only before, CD 2026-10-10). An entry in `services.json` for implement, execute or revise:
   - is an MCP server (`attach: mcp`), never an env service: Bash runs agent-written code;
   - lists its stages from one tier only, so a planning credential never reaches a strict-tier job;
   - has its own slot, `FACTORY_EXEC_SVC_1` or `_2` (repository secrets), and the workflow policy refuses either outside an implement or revise agent step that builds its settings with `services.py`;
   - names the tools the agent may call (`tools`). `services.py` allows exactly those in the stage's sandbox settings, and auto mode can't prompt for others;
   - declares `read_only`: CD's attestation that the credential itself is read-only at its source. The key can't write on the server, a database login has only `SELECT` (D3 rule 3). A service's own read-only mode or a tools list isn't enough.

   The credential goes in the Authorization header and nowhere else (rule 10). A service's results enter the context of an agent that writes and runs code, and a document or memory service reads as trusted knowledge, so one whose content agents or outside sources can write is a lasting prompt injection. Point an execution entry only at content CD's own reviewed sources write.
10. **An MCP service's credential goes in its Authorization header only.** Node's `fetch` drops `Authorization` on a redirect to another origin but forwards any other header (tested on Node 22, 2026-11-05). The MCP SDK's HTTP client is built on `fetch`, so the same is expected of Claude Code's client: an inference, not an observation, since the stand-in below never redirects. So `services.py` refuses any other header, and the credential reaches no URL but the configured one, which only a code-owned `services.json` and `--strict-mcp-config` set. `factory-smoke`'s `mcp-services` job proves each tier end to end against a stand-in MCP server on the echo host: the credential arrives (the server answers with its digest), sandboxed Bash sees a placeholder, and a tool the entry leaves out is refused. It runs when `services.json` lists an MCP service, or when dispatched with `mcp_probe`. Its summary also says whether each agent tried the left-out tool, since a refusal proves the list only when the agent tried. Its first run (2026-11-05, in a third project) observed the execution entry end to end: the credential arrived, sandboxed Bash saw a placeholder, and the agent tried the left-out tool and was refused under auto mode. The planning entry's verdict that run read the execution probe's transcript (claude-code-action writes every run's output to one path), so the job now keeps a copy of the first probe's transcript. The next run (v2.3.2, the same day) observed the planning entry end to end as well.

### Forbids

1. Giving an agent WebFetch or any unscoped network path. (Context7 covers library and vendor docs; WebFetch was the one channel that let injected text choose the destination.)
2. Agent Bash without the sandbox, or with `failIfUnavailable: false` or `allowUnsandboxedCommands: true`.
3. Granting a stage Bash before smoke carries that stage's sandbox probe.
4. Granting Bash without `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`.
5. `--security-opt seccomp=unconfined`, `apparmor=unconfined`, `--privileged` or `--cap-add` on factory containers.
6. Giving the OAuth token to a non-agent job; giving any write-capable token to an agent job, or putting one in a file the agent can read, except a service key a project opted in to under rule 8.
7. Running an agent step without a tool-policy file, or changing a tool policy without re-running smoke.
8. An execution-stage service that isn't an MCP server with a tools list and a credential read-only at its source, or any service credential outside the Authorization header of an MCP server.

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
- A repository the organization doesn't control runs the factory, or a service an opted-in key belongs to starts offering read-only keys (rule 8).

## D3: Planning Tier (spec and plan stages see real data and services)

### Why

Spec and plan stages make judgment calls that depend on how the system behaves in production: what the data looks like, which errors occur and where, what an external service returns. D2 keeps every agent job away from production and credentials, which is right for the stages that write and run code, but it leaves planning guessing or asking CD for facts it could look up. So planning may use the data and services that make a better plan, the whole database apart from personal and secret data, and only to read.

**Options considered:**
1. **Ask CD for every fact.** Keeps D2 unchanged; slow, and plans are only as good as the questions.
2. **A periodic scrubbed snapshot.** No path to production, but stale data, a table list to maintain, and no route to services such as error trackers.
3. **A separate planning tier with live read-only access (chosen).** Planning jobs run on their own runners as their own user, with a firewall exception for the production database only, a read-only login that can't see personal or secret data, and services wired from a list with their credentials masked.

### Rules

1. **Two runner tiers.** Implement, execute and revise run on the strict tier (D2, unchanged: no production path). Spec and plan run only on the planning tier: runners under a separate Linux user (`factory-planner`), selected by their own runner label and group. A workflow can't move a code-writing stage onto planning runners without a CODEOWNERS-reviewed edit, and the workflow policy check refuses it.
2. **One firewall exception.** The planning user may reach the production database port and nothing else on the host or LAN: on the runner host itself, or, when production runs on another machine, on the one address `host.conf`'s `PLANNING_DB_HOST` names (an address that doesn't change, such as the machine's Tailscale address). When that address is a private or tailnet one, setup's isolation test also probes its other ports (`PROBE_PORTS`), which must be closed. The address and port are set twice, in different repositories, and nothing compares them: the runner host's `host.conf` (`PLANNING_DB_HOST`, `PLANNING_DB_PORT`) builds the firewall, and each project's `planning.json` (`database.host`, `database.port`) is what its planning jobs connect to. They must agree; when they don't, the firewall refuses the connection, and `planning-services.sh`'s error names both settings. The strict user's firewall is unchanged. A database on a public address needs no exception, since the tier reaches the internet, but it is reached only over TLS: `planning-services.sh` requires it there and refuses `prefer` or `disable` (`planning.json`'s `database.sslmode`), where pgbouncer's own default would fall back to plaintext. On a private or tailnet address the network is the boundary, and TLS is used when the server offers it.
3. **The database login is read-only and excludes personal and secret data.** A dedicated role with `SELECT` only, granted per table and per column: everything except fields holding personal data (names, emails, phone numbers, addresses), credentials (password hashes, API keys, tokens, session data) and payment data. The exclusion list is generated from the models, or from the database's own catalog with `planning_reader.py` (any stack: it denies a column no rule knows is safe, and writes the role's SQL and its verify checks), and reviewed by CD; a migration that adds a table or column re-runs the check, and anything new and sensitive-looking stays excluded until CD approves it. The role also has a statement timeout and a connection limit. The agent reaches it through a connection proxy outside the sandbox that holds the password; the agent never sees it.
   - **Read-only is the role's privileges, never a session default.** Any session can open a read-write transaction (`COMMIT; BEGIN READ WRITE`), and what PUBLIC may do the role may do. So the role's SQL also:
     - revokes from PUBLIC `EXECUTE` on the large-object write functions (`lo_create`, `lo_creat`, `lo_from_bytea`, `lo_put`, `lowrite`, `lo_truncate`, `lo_truncate64`) and `TEMPORARY` on the database, granting back to the app's own roles what they use;
     - sets `temp_file_limit` on the role, which only a superuser can change.
   - **`planning-services.sh` checks this through the proxy before the agent starts.** It refuses a role that can write a table (a column-level grant included), a sequence or a large object, create a temporary table, a schema or an object in a schema, own anything, lift `temp_file_limit`, or that has superuser, role-creating or server-file powers. It names each problem.
   - **The deadline the role can't lift is the proxy's.** A role's `statement_timeout` is only a default it can `SET` away, so pgbouncer cancels a query after 60 seconds and drops a transaction left idle, or a client left waiting, after 30.
   - **The connection limit covers the proxy's pool,** 4 connections per planning job, times the planning runners.
   - **The same rules hold for a database read through a service** (`services.json`, an MCP server such as pgEdge): the role's privileges are the boundary, never the service's read-only mode.
4. **Services come from a reviewed list.** `.github/factory/services.json` (CODEOWNERS) names each service: its domains, the GitHub secret with its credential, and how the credential attaches. The planning job turns the list into sandbox settings (`credentials.envVars` with `mode: mask`, `injectHosts` set to the service's domains, `network.tlsTerminate`), or into an MCP server entry with its credential in the Authorization header, its slot masked in the sandbox and its allowed tools (`tools`, or all of the server's) in the settings (D2 rules 9 and 10). Sandboxed commands see a placeholder; the proxy substitutes the real value only on requests to that service. Adding a service is one entry plus one secret, with no workflow edit.
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
- A read-only role can still load the primary: `work_mem`, parallel queries and session advisory locks stay the role's to use within the proxy's deadline. A read replica removes that; until there is one, it's CD's to accept.

## D4: Production Tier (gates CD approves, run by a broker no agent can reach)

### Why

Some plans need production: deploys, migrations, restarts, backups, checks against a live system. D2 keeps agents away from production, and D3 lets planning read it, never change it. The factory needs a way to do production steps without CD's hands, with approval per step and without a new PR for each approval. Cross-checks rejected the first design, which trusted labels and App comments: any repository writer can edit or race those.

**Options considered:**
1. **Plans mark production steps for CD to run.** Safe, but every gate needs CD's hands and a PR for each segment.
2. **An agent with production access, approved per step.** An agent's judgment in production is what D2 exists to prevent, and a prompt injection would reach production.
3. **A deterministic broker runs reviewed operations after CD approves each gate (chosen).** No agent touches production, and the approval is GitHub's own deployment review, which nobody can edit or forge.

### Rules

1. **No agent in the production tier.** Agents plan gates and write code; a deterministic broker runs the gates. D2 and D3 hold unchanged.
2. **Production work happens only through the release branch, or in gates** (`[sdlc-root]/process/production-gates.md`). A deploy is a release PR CD merges (rule 13): a release gate's, partway through a plan, or the one that follows a plan's execution PR. Gates between phases hold what isn't a deploy (a backup, a live check), and, on the fallback without a release branch, the deploys too. The plan's last item is a phase; the factory also needs a phase before the first gate.
3. **Operations come from a reviewed catalog** (`.github/factory/production/ops.json`, code-owned): kind, parameters and outputs with an anchored pattern each, timeout, required earlier operations, rollback-only operations, and `release_gates`, the broker's own word that it runs release gates' gate runs (rule 13). Outputs are typed values, never free text. Scripts are installed root-owned by CD's setup run, never loaded from a workspace. The catalog also gives the broker's own time, for the plan guard's budget: `gate_overhead_s` (the worst case of what it does around a gate's steps: its lock wait, fetches, state captures, a release gate's checks), `step_margin_s` (what stopping a step past its timeout takes) and `release_wait` (the read operation it runs itself before a release gate's steps, unless the block starts with it). Each is optional, and none or 0 without. The guard refuses a gate whose worst case (that time, then every step it may run to its timeout and stop, the rollback included) is over the gate run's job limit (`factory-gate.yml`'s `execute`, 300 minutes), rather than let the job's limit kill it partway: for a release gate, that would come after the deploy.
4. **Two approvals.** Merging the plan approves what each gate may do; the plan guard refuses an unknown operation or a broken parameter. Approving the gate run approves doing it now, with the values filled in.
5. **Approval is GitHub's deployment review.** Each gate gets a run of `factory-gate.yml` whose title carries the request's digest; its job waits on environment `factory-production` (CD the required reviewer, `main` only). Labels and comments authorize nothing: `factory:gate-retry` only asks for a fresh run.
6. **The digest binds everything:** repository, issue, PR, gate, attempt, plan path and blob, PR head, the resolved steps and rollback, and a hash of the installed operations; for a release gate (rule 13), its release PR and merge commit too.
7. **The broker checks for itself** (root, socket-activated, one instance per request, reachable only by the runner user): the run is `factory-gate.yml` dispatched on `main`; an approver approved its deployment; the request it rebuilds from the plan blob on `main`, the PR head, its own ledger and its installed operations has the title's digest; the run is in progress; every earlier gate is done in its ledger, as the plan defines it now; production's deployed commit is the one it last recorded (after any gate, or a `baseline` CD records after changing production by hand); nothing is unfinished; the digest never started.
8. **Signed receipts, for every gate.** A CD gate goes through the broker too: it runs nothing and records CD's approval. The broker signs every result, bound to its PR, gate and digest, with a root-only ed25519 key. The hosted report job verifies it with the committed public key before posting it or continuing execution; an unverified result changes nothing, and nothing the factory acts on comes from an editable comment.
9. **Never twice, and never unknown.** The ledger records each step. A finished digest returns its stored receipt; an interrupted run blocks every gate until CD resolves it on the host.
10. **Keys.** The runner user has no sudo, no Docker group and the strict firewall, and holds only the job's read-only token. The broker runs operations as the operator user, with the host's credentials in place. The runner group takes only `factory-gate.yml` (and, with a broker following the release branch, rule 13, `factory-follow.yml`) from `refs/heads/main`.
11. **Rollback is approved with the gate,** runs automatically when a step fails, and only for steps that got far enough to need it. Schema changes are expand-only, and a rollback never reverts a migration. Where the host runs migrations itself before the new release starts (Railway's pre-deploy command), the broker never runs the commit's code: it bounds that step with its own deadline and cancels the deployment when the deadline passes (Railway sets none). Restoring from a backup is CD's runbook, never an operation: on Railway a restore stages a change, which rule 14 refuses anyway.
12. **One gate at a time on the host,** never during the nightly backup (the broker holds its lock).
13. **Release model: production deploys from a release branch** (`factory.json`'s `release.branch`, `release/production` by default; CD, 2026-11-06, after each project chose its own from 2026-11-05). A project whose production host can't follow a branch yet uses the fallback, execution-PR gates, with `release.branch` empty. A `factory.json` with no `release` block, written before the release branch existed, is on the fallback, and migrating changes nothing for it: a seed is never rewritten.
    - **The release branch, the model.** Every host that serves production deploys that branch: by itself (a Railway service's trigger, a Vercel project's production branch), or, on a host that can't, through its broker following it (below, not built yet). Nothing deploys any other branch to production. CD's merge of a PR into it is the deploy and its approval: its ruleset requires a PR with code-owner review and merge commits only (provenance, below, reads them), blocks force pushes and deletion, and restricts updates to its bypass actors. They are only organization or repository admins, in pull-request mode: no App, team or deploy key, and none in always or exempt mode. Their merge may skip the review and the merge method; a squash or rebase one still fails provenance. No `exclude` condition of it matches the branch. Without the update restriction, anything with contents write, the App included, could merge a reviewed release PR. With it, the factory App can open a release PR but never merge one, and an admin credential can't push to it (`bootstrap.py` checks all of it).
      - **A plan can deploy partway through, in a release gate** (CD, 2026-11-05: every project must be able to deploy mid-plan, release branch or not). A gate with a `**Release:**` line is one (`[sdlc-root]/process/production-gates.md` § With a Release Branch); it needs the production tier, as every gate does (rule 16), and a broker that takes release gates: its catalog says `"release_gates": true`. Without that, the plan guard and the gate request refuse a release gate before anything is pinned, since merging its release PR would deploy and only then would the broker refuse the gate run.
        1. **Pin.** When execution stops before it, `factory-gate-request.yml` pins the stopped commit, the PR's head it checked, as `factory/release/<pr>-<gate>-<first 12 of the commit>`. It pins only where GitHub lists the pinned branches' ruleset covering that name (updates restricted, no force push, no deletion): without it the branch could move after CD reviewed it. The contents token that creates the pin is minted only for a release gate, and held only by the step that pins, never by a step that reads the PR, its comments or the plan. As the App, it opens a release PR from that branch into the release branch, saying what merging deploys: the execution PR's commits up to the gate, and the default branch's commits behind them that the release branch doesn't have yet. It closes the gate's older release PR at another commit.
        2. **Deploy.** CD's merge of the release PR is the deploy.
        3. **Check.** `factory-advance` then asks for the gate run, of kind `release`, whose digest also binds the release PR and its merge commit. CD approves it as for any gate. The broker checks for itself that the release PR is the App's, from the gate's pinned branch at the request's head (the execution PR's head, which the broker reads itself), merged by an approver into the release branch, and that its merge commit, whose second parent is that head, is on the release branch's first-parent history at or before its head (another release may have followed it). The head must still have the gate's content: for every path the execution PR's commits up to the gate changed, the same blob as the gate's commit. So a revert since, or a later release that changed one of those paths, fails the gate closed, and CD decides. It waits, within its own deadline for rule 15, for evidence that production serves the release branch's head, runs the gate's read operations, records the branch's head and signs the receipt. The gate run's job allows 300 minutes for all of it. Execution then continues from the gate's commit, as after any gate.
        - **The pinned branch can't move:** a ruleset on `factory/release/**` restricts updates and deletions and blocks force pushes, with no bypass actor, the App included, so the commit CD reviews is the commit CD merges (`bootstrap.py` checks it). It allows creation, so a pinned name that already exists at another commit is refused, never used. Nothing deletes pinned branches, the repository's delete-on-merge included: CD deletes old ones by hand, with that ruleset off, or leaves them.
        - **Someone else's PR from a pinned branch** blocks the App's (GitHub allows one open PR per branch pair), so the factory refuses and says so; CD closes it unmerged. A release PR merged at an older commit than the execution PR's head (a stale one, reopened) is reported as what it is: production runs that commit.
        - **A release gate can't roll back by itself:** its release is live from the merge. A failed one is CD's. Without a migration, roll back through the host, then revert the release in the release branch and record a `baseline` (the revert's merge isn't on the default branch, so provenance blocks the next gate until then), and close the execution PR or fix it. With one, fix forward (rule 11): a host rollback would run the older release against the newer schema, and a revert never reverts a migration file. To try again after a revert, CD first reverts that revert in the release branch, again never touching a migration file, and records a `baseline` for it: git counts the gate's commits as merged already, so neither `factory:gate-retry` nor a new release PR brings them back, and the gate's content check refuses until they are.
      - **A plan whose finished work must reach production** has a `### Release` section (`[sdlc-root]/process/production-gates.md`). The plan's PR shows it, the execution PR carries it, and when CD merges that execution PR into the default branch, `factory-release-pr.yml` opens a release PR from the default branch into the release branch, or comments on the one already open. That PR carries only what the plan's release gates haven't. Nothing else opens a release PR; CD opens their own by hand.
      - **The broker,** if the project has one, runs only non-deploy operations: backups, typed checks, capture-state. The exception is a broker following the branch on a host that can't (below), which deploys the branch's head and nothing else. A rollback is CD's, through the host, followed by a revert PR into the release branch so the branch matches production again. Rule 7's expected deployed commit is the release branch's head, read from GitHub at gate time, rather than the broker's own record. The broker also checks provenance: every first-parent commit added to the release branch since its last record must be the merge commit of a PR an approver merged, whose second parent is on the default branch or is a release gate's pinned commit: the head of a merged release PR the App opened from a `factory/release/` branch whose name ends in that commit's first 12 characters. Who merged proves who clicked, not what came in, and a pinned branch can't move, so all of it can be read from GitHub at any later gate. A commit that reached the branch any other way, a hotfix included, blocks the next gate until CD records a `baseline`.
      - **No infrastructure refusal** on a host that rebuilds from the merged commit: the guard keeps agents off what builds production, and CD reviews every release PR. A broker following the branch on a Compose host keeps the fallback's refusal (below), since a restart there doesn't rebuild.
      - **The default branch's merge method doesn't matter for deploys:** they follow the release branch's history.
    - **Execution-PR gates, the fallback** (`release.branch` empty, or no `release` block), for a production host that can't follow a branch yet: a Compose host until its broker follows the branch (below). A deploy gate deploys the execution PR's head; production may run ahead of `main` until CD merges it with a merge commit. Deploys only move forward from the commit the broker last recorded, which it checks in a clone of its own, and only the broker deploys: a host that deploys a branch by itself (Railway's auto-deploy from GitHub) has that turned off for production. A deploy refuses a change to what the host builds or runs production from, which stays CD's. The project's tier configuration lists it, and it is code-owned. On a compose host, a restart doesn't rebuild, so that is compose files, Dockerfiles, `docker/`, dependencies, env files, the Makefile and units. On a host that builds every deploy from the commit (Railway), dependency changes simply rebuild, and what stays CD's is the host's config-as-code (`railway.json` or `railway.toml`: the build, start and pre-deploy commands, the health check), Dockerfiles and the builder's configuration. `.github/` deploys like docs: no container reads it and the broker runs its installed copy, so factory commits don't force a hand catch-up before the next deploy. No infrastructure pattern applies under it, whatever a file there is called (a stack profile's job-image `Dockerfile` included).
    - **A host that can't deploy a branch by itself follows it through its broker** (designed 2026-11-06, not built yet: until it is, such a host's project uses the fallback, and the incubator keeps execution-PR gates). A Compose host has nothing that watches a branch, so its broker does:
      1. **Trigger.** The release branch changes only through merged PRs, so `factory-advance`, on the `pull_request` event of a PR merged into it, asks for a run of `factory-follow.yml` on `main`; its job only dispatches. A `push` trigger would run the release branch's own copy of the workflow instead. CD can dispatch the run by hand, and it is idempotent: the broker deploys the branch's head when that isn't the commit it last recorded, and otherwise does nothing. The project's production runner group takes `factory-follow.yml` and `factory-gate.yml`, from `refs/heads/main` only.
      2. **Approval.** The run has no environment approval. CD's merge is the approval, as it is when a host deploys the branch by itself, and the broker reads that merge from GitHub for itself. Forbids 3 still holds for every gate run.
      3. **Checks.** The broker checks, for itself:
         - the run is `factory-follow.yml` dispatched on `main`;
         - provenance, as above, for every first-parent commit added to the branch since its last record;
         - the branch's head descends from the commit it last deployed, in a clone of its own;
         - nothing in its ledger is unfinished, and the nightly backup isn't running (rule 12).

         It deploys the branch's head and nothing else.
      4. **What stays CD's.** A Compose restart doesn't rebuild, so the fallback's infrastructure refusal holds. A release whose diff from the deployed commit touches the tier's list (compose files, Dockerfiles, `docker/`, dependencies, env files, the Makefile, units) is refused, and CD deploys it by hand and records a `baseline`.
      5. **Deploy.** Rule 14's settings check comes first, then the deploy operation and rule 15's evidence. A failure rolls back to the commit the broker last recorded: this rule approves that rollback in advance, it runs by itself, and it never goes past a migration (rule 11: fix forward). After a rollback the branch's head isn't what production runs, so the broker refuses every follow run and gate until CD reverts the release in the branch or records a `baseline`.
      6. **Record and report.** The ledger records the deployed commit, the PR and merge commit it came from, the outcome and the timing. The broker signs a receipt of its own kind, bound to that head and that PR, and a hosted report job verifies it and posts it on the merged PR.
      7. **Release gates.** A release gate's merge starts both the follow run and the gate run's request. The gate's check waits for the follow deploy, under the broker's lock, then checks as on any host.
      - **A missed dispatch** shows at the next gate, which expects the branch's head in production (rule 7), and in the broker's drift check where it has one. CD then dispatches `factory-follow.yml` by hand.
14. **A deploy never changes production's settings.** Before changing anything, the broker shows that the new release will run with the settings production has now, and refuses otherwise. (With a release branch the host deploys, not the broker: CD's merge of the release PR covers it, and rule 15's evidence applies to anything that waits on a release. A broker following the branch on a host that can't, rule 13, runs this check before each deploy.) CD's own change to production is recorded on the host with `baseline`.
    - **Compose:** a dry run in the broker's own environment shows every restarted service would stay running as it is. A recreate re-reads the environment, `.env`, ports and mounts, so production could come back with settings it wasn't started with. (Comparing `docker compose config --hash` with the containers' config-hash label doesn't work: they differ even right after `up` in the same environment.)
    - **Railway:** the environment has no staged change with a non-empty patch (an empty staged row isn't a change), and each service's variables and configuration hash the same as when the broker last recorded them. Railway exposes no version of a variable, so the broker reads the values and hashes them in its own process, never printing or storing them. A rollback that restores settings (Railway's restores the variables with the image) is followed by a fresh record.
15. **Healthy after a deploy means the new release.** The health wait needs evidence newer than the change and specific to it, not just a passing health check: an old process's last word outlives it. One sign of the new release isn't enough either: a new process can report once and then crash.
    - **A heartbeat kept with a time-to-live** counts only when it shows the new release on two reads more than one time-to-live apart. A worker that writes once and crashes, or crash-loops under restart-on-failure as the same release, leaves its mark there for a whole time-to-live.
    - **During the overlap,** old and new processes write the same last-writer-wins key, so its value alternates until the old one stops. The wait looks for the new release's mark on those two reads, never for a value that stops changing. The old process can't write the new release's mark, so the alternation can't produce a false pass.
    - **Compose:** a worker heartbeat newer than the restarted worker's start. A stopped worker's last heartbeat outlives it, and both the container health check and the API's endpoint accept it.
    - **Railway:** the deployment the deploy call returned reaches SUCCESS, and the API's health endpoint and the worker's heartbeat report that deployment's id (`RAILWAY_DEPLOYMENT_ID`; the commit variable may be empty after an API deploy).
      - Railway keeps the old deployment serving until the new one passes its check, so an answer without the new id is the old release.
      - SUCCESS can turn into CRASHED, so the broker reads the deployment's status again at the end of the wait.
      - A service with no platform health check reports SUCCESS as soon as its container starts. For it, SUCCESS is no evidence of health at all: its heartbeat is.
      - What's serving is the newest successful deployment, not the latest, which may have been skipped or failed.
16. **No production tier, no gates.** The tier (the broker, its operations catalog `production/ops.json`, its runner) is the project's own, and this bundle doesn't install it. For a project whose host deploys the release branch by itself, the opt-in `factory-broker` bundle supplies a checks-only broker and its setup, leaving the project its host module and catalog (`[sdlc-root]/process/factory-broker.md`); a broker that deploys stays the project's own. Without it a plan can have no gates, CD's included, since every gate runs through the broker: the publish guards refuse such a plan and say why. Production steps then stay outside the factory, as CD's. A release-branch project without a tier still releases: its plans have no gates, release gates included, since their check runs through the broker, and finished work reaches production through a Release section's release PR. CD's merge is the deploy, and nothing in the factory checks it afterward. A host may run several projects' tiers. Each one after the first has names of its own: its user, configuration, library, state and log directories, socket, systemd units, firewall table and runner name. The request client finds the broker's socket from the calling user (`/run/<user>/op.sock`), so one client serves every tier on the host.
17. **A revision reaches a gate the way execution does.** An execution that stops with a decision open for CD returns `escalated`, so nothing asks for the gate. CD answers with a Request-changes review. On a PR that executes a plan, a revision can then stop before that plan's next gate. The plan is the one its gate tracker names. With no tracker yet, it's the sibling of the one result doc the PR adds, when that plan is on `main` and is for the issue's own deliverable (the ID the plan stage reserved on the issue, as the App): a result doc's name alone can't point the gate at another plan. The next gate is the plan's first one this PR hasn't passed, by the broker's signed results. The gate job gives the agent the plan and that gate, and the publish job refuses any other gate. The revision must leave no critical or major finding and no question for CD, with the work before that gate done. It returns `awaiting-approval` naming the gate. A writer job then does what execute's report job does at a gate stop: it posts or updates the tracker, sets `factory:gate` on the issue and asks for the gate run, which replaces a stale run still waiting on an older request. Execution and a revision both ask for the gate on the commit they pushed: if the branch has moved since, no request is built, and CD adds `factory:gate-retry` to ask for one on the new commits after reviewing them. If that writer job doesn't run, CD dispatches a workflow that does its work from GitHub's own records: the App's last revision comment must say it stopped before that gate, and the branch's last push must be the App's push of the PR's head, from before that comment. It runs no agent and counts no revision, so it works after the last revision too. A revision never continues execution: if work before a gate is unfinished, CD pushes it, then requests changes.

### Forbids

1. An agent on the production runner, or a production path, credential or runner reachable from an agent job.
2. An operation outside the installed catalog, or a parameter that breaks its pattern.
3. A gate run without an approver's environment approval, or a digest run twice.
4. A production runner job from any workflow but `factory-gate.yml` (and, with a broker following the release branch, `factory-follow.yml`) on `main`, with a container, a `uses:` step, a secret, or any permission beyond read.
5. Operation scripts loaded from a workspace; agent commits to the files rule 13 keeps for CD (compose files, Dockerfiles, `docker/`, a host's config-as-code).
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

## D6: Browser Host (stages drive a real browser, with no way out)

### Why

The code-writing stages can't see a web app run. Triage confirms UI bugs from code alone, plans hand every browser check to CD or CI, and a bug CI stayed green on was found only when CD drove the app at a gate. CLAUDE-SDLC's "prove the bug before fixing it" needs a browser for a UI bug. A browser is also the widest way out a sandbox can have: it fetches whatever a page names. So the browser has to run where it can't reach anything, and drive only the app the stage starts. WebGL needs a GPU, which renders a frame for about 7 CPUs' software rendering.

**Options considered:**
1. **Playwright MCP in the stage's config.** MCP servers run outside the sandbox, next to the job's credentials, so the agent would get an open browser: the channel D2 Forbid 1 removed.
2. **Chromium inside the sandbox.** Unproven under the sandbox's seccomp filter, browsers have crashed in sandboxes before, and WebGL would render in software. A GPU passed into agent jobs puts its driver within reach of agent code on a host that does more than CI (§ Stack Profiles).
3. **A dedicated browser host the sandbox reaches through one port (chosen, CD 2026-11-19/20).** The app and its servers stay in the sandbox, as tests do today. A Playwright client in the same sandboxed command connects to the browser host, and every request the browser makes comes back through that connection and is made from the sandbox's side, so the browser can load the sandbox's own `localhost` and nothing else.

### Rules

1. **The browser runs on the browser host, never in a stage's job.** A Playwright client in a sandboxed command connects to the host's front end for the project's own Playwright version: a client's major.minor must match its server's, so the host serves each version on its own port (`port_base` + minor, 3100 by default). The front end forces `exposeNetwork: "*"`, so all of the browser's traffic goes back through the client and is made inside the sandbox. The job image needs no browser, and `playwright install` never runs in a job. A GPU renders WebGL wherever the host has one (CD, 2026-11-19).
2. **The strict tier's one network opening** (CD, 2026-11-20). The strict runner users may reach the browser host's front-end ports and nothing else on the host or LAN: the one address `host.conf`'s `STRICT_BROWSER_HOST` names, on `STRICT_BROWSER_PORTS` (3100–3199 by default). It is the same shape as the planning tier's database exception (D3 rule 2):
   - setup's firewall accepts that address and range before it rejects the private and tailnet ranges;
   - setup's isolation test finds every other probe port there closed, and the ports just past each end of the range;
   - setup reads the loaded rule back, and refuses an address that isn't private or tailnet, or that is the runner host's own;
   - the address is set twice, in different repositories, and nothing compares them: the runner host's `host.conf` builds the firewall, and each project's `factory.json` (`browser.host`) is what its stages connect to. They must agree; when they don't, the connection is refused. That holds only because both must be private or tailnet addresses, which the firewall otherwise rejects: `browser.py` refuses any other, since a public one would be reached as the internet is.

   A stage's sandbox narrows the opening to one port. `browser.py`, run outside the sandbox before the agent starts, adds `<address>:<port>` for the project's installed Playwright to the stage's `allowedDomains`, and the sandbox's proxy refuses every other port and host. D2 holds otherwise: no other host, no direct connection, no DNS.
3. **The browser host is part of the boundary.** The client is agent-written code, so nothing it chooses is trusted. The host must hold all of these:
   - **A front end is the only thing the network reaches.** It replaces whatever the client sends with:
     - the browser `chromium`;
     - `exposeNetwork: "*"`;
     - fixed launch options: new headless (which uses the GPU), `--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1` and `--force-webrtc-ip-handling-policy=disable_non_proxied_udp`.

     No launch option of the client's takes effect. `run-server` has no authentication, so the network's access policy (the runner host only, on those ports) is the lock.
   - **Each `run-server` listens on loopback, at `port_base` + 100 + minor, on a secret path,** random per start, known only to the front end and never logged. A page can reach the host's loopback (a context proxy whose bypass names `127.0.0.1` makes Chrome connect there directly). With launch options taken from the request, a page that opened a `run-server` WebSocket could launch any program as the browser's account (found 2026-11-20, before the secret path; nothing was launched). Plain HTTP on the host's loopback stays reachable, so every service there must require credentials.
   - **An outbound block keeps the browser's account to loopback,** passing only the replies to the runner host's connections. A client can give a browser context its own proxy (`newContext({proxy})`), which skips the forced tunnel: before the block, a client in a sandbox with no network fetched an outside page that way.
   - **The browser looks up no name itself.** The outbound block doesn't cover the operating system's resolver, which runs as root. A context proxy's hostname and a WebRTC STUN server's both leaked a lookup from the host until the resolver rule above closed them. Page traffic is unaffected: its names resolve on the client's side.
   - **A session cap** (two browsers on an 8 GB host), with a first-come queue that answers 503 after 10 minutes.
   - **Its code is root-owned,** versioned and reviewed like the runner host's setup, and started only in the browser account's own session. The browser account is a standard one.
4. **What proves it.** Two checks prove the route, because neither can see everything:
   - **`factory-smoke`'s `browser-host` job,** from inside the implement stage's own sandbox with the route added. The probe (`browser_probe.mjs`, judged by `browser_check.py`) must find:
     - the app it starts on its own loopback loaded by the browser host, its WebSocket included, with WebGL on the GPU (unless `browser.gpu` is false);
     - a screenshot, the trace and the video come back;
     - the forced flags on the browser's own command line, the resolver rule exactly once;
     - a second client that asks for another browser, its own launch options (a program, headed, a proxy, its own resolver rule, a debugging port) and loopback only, in its headers and its query, gets the forced Chromium and flags and none of its own;
     - the outside world refused, by name and by address;
     - a context proxy refused, by address and by name;
     - a page that reaches the host's loopback (plain HTTP answers on the run-servers' ports, at `port_base` + 100 + minor) opens no WebSocket to a `run-server` there;
     - the sandbox's proxy refuses the browser host's next port, since the stage's sandbox allows one;
     - Node's `fetch` reaches the project's first allowed outside host (`browser.allow`) through the sandbox's proxy: the path a spec's `context.route` helper depends on. With the entry's `probe` path, a `GET` of it must answer 2xx, so the host serves what the specs fetch. Without one, a `HEAD` of the root passes with any HTTP status, which proves only the path (a CDN with nothing at its root answers 522), and the log line says so. With none allowed, the probe says so;
     - no credential, by name or by value;
     - the filmed pass's overlay (`evidence_film.mjs`, rule 7), on a page with a canvas under a button: the same stepped move, filmed and not, hits the same elements, sends the same pointer coordinates, and shows an observer of the body nothing; the filmed pass draws the pointer and its steps reach the page at least 40 ms apart (half the 80 ms hold, for the timers' slack). Timing is checked only from below. Its pace checks run on a page with a button, an input, a frame with an input of its own, and a second frame inside an open shadow root. Each is judged by count and by the reason the module logs, or mustn't log. Without a frame (`film-claims`):
       - a gesture made with `page.mouse` and `page.keyboard`, a double-click and a bare down included, counts as paced;
       - a locator click where the pointer already is, also after a double-click, counts as unpaced.

       With a frame (`film-frames`):
       - a click just inside the frame counts as not checked;
       - a click back out of it counts as sent, with no "didn't send" logged;
       - a locator click in the frame then a move, and a move across the frame, count as unpaced;
       - a key into the frame, a click into it, or a bare down over it, then a locator key or click in the page, counts as unpaced: what the frame took was left out of the sent counts;
       - a move across the frame inside the shadow root counts as unpaced, and so do keys into that frame followed by a locator key;
       - a click far into the frame counts as a jump;
       - a move across a frame inside a closed shadow root, which no lookup finds, counts as unpaced, by the jump the page saw.

       And the gesture's typed keys arrive at least 40 ms apart, half the 80 ms hold, as for moves (`film-typed`), and its "Watch" caption is gone after it, by the strip's pixels (`film-caption`).

     An unsandboxed control in the same job must first reach the outside world through the same tunnel and find a canary credential in its environment, so the agent's refusals and clean environment are the sandbox's doing, not a broken check. The control holds the canary, never a real token: it runs the project's own Playwright with network.
   - **The browser host's own check,** on a timer, as the browser's account, reporting to a dead-man's switch so a check that stops running also alerts. It checks that outside addresses and the LAN are blocked, loopback is reached, the front ends are up and the browser's account holds the session. The smoke job can't see the outbound block: the resolver rule refuses outside hosts, bare addresses included, before the block is ever reached. Nor can it see a DNS lookup leave the host: a changed launch flag is proven on the host with a canary resolver before it ships.

   **Nothing relies on the route until smoke passes.** A stage gets it only when CD lists the stage in `browser.stages`, after the `browser-host` job has passed. Run smoke again after any change to the browser host (its code, its Chrome, its flags, a new Playwright version), and after the project upgrades Playwright.
5. **Absence is reported, never guessed.** With no route for the stage, or no answer from the host, `with-browser` prints `UNAVAILABLE: browser host (<why>)` and exits 75. A stage that gets it reports `blocked`. It never claims a bug was reproduced or ruled out.
6. **Offline by default, at the network.** The sandbox blocks the app's server and the browser alike, since most outside calls in the projects swept are server-side (server rendering, back-end calls to maps, media or partner APIs). Every outside connection falls into one of five kinds:

   | Kind | Handled by |
   |---|---|
   | The project's own services | the profile's test services, or emulators |
   | Static files (CDNs, fonts, images) | a local copy from the fixtures job (D2 rule 7), or a recording replayed with `routeFromHAR` |
   | Live services with effects (payments, auth providers, analytics, telemetry, streaming) | the app's own offline mode, or a stub; a feature that needs one can't be driven here |
   | Links out to partners | caught and checked, never followed |
   | The partner's own side | outside the factory (below) |

   - **Anything not sorted is blocked, and listed in the stage's result.** Tests that tolerate a missing service can pass while the app is broken: one project's suite went 21 of 21 green with its content service returning nothing.
   - **The project's verify skill is the one list** of its outside connections (its Targets, outbound integrations and Recorded Exceptions; CD, 2026-11-20). The factory reads the same list and enforces it more strictly.
   - **No approved outside host to start** (CD, 2026-11-20). An exception recorded for interactive verify (a CDN, say) doesn't carry over: the fixtures job supplies the files instead.
   - **Partner sites stay outside the factory, except by exception** (CD, 2026-11-20). Checking a partner's side, such as an affiliate link's destination, is a scheduled script or a supervised session, not an agent with open internet. An exception names one host, and CD records it in the project's verify skill (Recorded Exceptions) and in the factory's reviewed allowlist. Each exception weighs what the visit does on the partner's side, such as an affiliate click it records, and that a reachable host is a way out: `browser.py` opens the whole of `<host>:443` to every sandboxed command, with any method, headers and body, not only the browser's requests. `factory-smoke` also sends the first allowed host two requests per run, one from the control and one from the agent probe: a `GET` of the entry's `probe` path, or a `HEAD` of its root (rule 4).
   - **A project rule that must bind the agent goes where that agent reads it.** A stage passes its blocks, such as this rule's browser block, to the agent doing the work word for word, while a project's own rule may reach that agent only through the orchestrator's summary of it. So a rule the working agent must follow, such as "every e2e context opens through our helper", goes in a file the project keeps beside the code it governs and the agent reads for itself (a `CLAUDE.md` there, say), not only in the orchestrator's prompt.
   - **Enforce such a rule where its effect happens, not only by reading the specs.** A check that scans spec code for every way to break the rule keeps growing and still misses forms: in the pilot project, a static guard that every e2e context opens through its helper grew to about 1,500 lines over three review rounds, and the outside reviewer still found ways past it. Put the invariant in the module that owns the effect, at run time: a helper that refuses a context it didn't open, say, or an evidence writer that refuses a file outside its folder. Keep a static check for early feedback, never as the boundary.
   - **The reviewed allowlist is `factory.json`'s `browser.allow`** (code-owned): one plain hostname per entry, with `why` and `decided` (who, and when), and optionally `probe`, a path on the host that answers 2xx to a `GET` (a file the specs fetch), which `factory-smoke` fetches from the first entry (rule 4). `browser.py` adds each as `<host>:443` to the stage's `allowedDomains`, and nothing else. The browser can't fetch it by itself: Playwright's tunnel connects from the client directly, and the sandbox has no network but its proxy. So the project's spec, or a helper its specs use, serves those requests: `context.route` for the host, fulfilled from Node's `fetch`, which `with-browser` points at the sandbox's proxy (`NODE_USE_ENV_PROXY`, with the hosts in `FACTORY_BROWSER_ALLOW`). The same exception goes in the verify skill's Recorded Exceptions, in the same PR, so CD reviews the boundary change once.

7. **Evidence goes from the agent's files to the PR only through frozen code** (CD, 2026-11-20). CD sees it through links, as the writer job builds them:
   - **The agent writes only `.factory/evidence/`:** screenshots (PNG), at most one video (WebM) and one Playwright trace, with a `manifest.json` that says, for each file, its step, what it shows and whether it shows the bug. That's the verify skill's own layout (`[sdlc-root]/process/verify-command.md` § Companion). Reproduce and verify runs record video; other browser runs take screenshots and the trace only. The project's evidence helper empties the folder when each Playwright invocation starts, so the last invocation's files are the ones that ship, unless the stage puts the proof's back after a filmed pass (below). The viewport is fixed, and the video short. `with-browser` exports `FACTORY_EVIDENCE_VIDEO=1` in the stages and `0` in smoke, from `browser.conf`, so the helper knows when to record. The trace is taken without screenshots when the run records video (rule 5): measured on Playwright 1.61, a 90-second run's trace was 61 MB with them, past the 50 MB trace limit `evidence.py` keeps, and 4 MB without. It marks each action, but it isn't what CD watches: on a canvas app its snapshots don't show the board, and it doesn't open on a phone or reach the archive. A reproduce run that kept no video says so in its report (`reproduce_report.py`).
   - **The proof runs as CI runs it, and a filmed pass runs last** (CD, 2026-11-23: "i want to be able to read this report, watch the video and understand what's happening"). The proof is plain `recordVideo`, never annotated: Playwright's annotated video (`showActions`, in 1.61) waits before every input on its context, 500 ms by default, which can hide a race or break a short UI window, so a factory run would disagree with CI's run of the same spec; and its cursor goes to a move's end point before the move's steps run. But an unpaced stepped move goes as fast as the browser takes input (measured, 5 to 18 ms a step on a light page and about 50 ms on the pilot project's canvas board), so a state that lasts one step shows for a frame or two of a 25 fps video at most, and the pointer isn't drawn: CD can't follow it. So, where the project's evidence helper loads the film module, the stage runs the same spec once more, last, alone, with `with-browser --film` (`FACTORY_EVIDENCE_PACE=1`), and that pass's evidence ships, unless it didn't run cleanly or the bug shows only in the proof (below). Since the helper empties the folder when the filmed pass starts, `with-browser --film` first keeps the proof's folder as `.factory/proof-evidence/`, and `with-browser --ship-proof` puts it back as `.factory/evidence/`. A copy already kept stays, so a filmed pass run again keeps the proof's, not the first film's; a run without `--film` is a proof and drops it, even one that writes no evidence, so nothing else runs through `with-browser` between the filmed pass and `--ship-proof`; a run whose front end doesn't answer keeps and drops nothing. With nothing kept, `--ship-proof` changes nothing and fails, since it can't tell whose files the folder holds: run the proof again, and its files ship. In it, the helper loads `evidence_film.mjs` (`$FACTORY_EVIDENCE_FILM`, installed read-only beside `with-browser`):
     - `filmContext` on the recorded context, before its first page opens, draws the pointer from the page's own pointer events, a ring on each press, and a caption strip at the bottom edge (or the top, for a layout whose bottom holds what CD needs);
     - `caption` puts each step's words on the picture when the helper records the step;
     - the spec makes the moves and presses that show the bug with `page.mouse` (moves in steps, presses where a move ended) and `page.keyboard`, and wraps them in `gesture(page, label, fn)`. It shows "Watch: <label>", holds each step of a `page.mouse` move 80 ms after the browser takes it (two frames at 25 fps), so the page sees the steps at least that far apart, and waits 400 ms before a press, click or key. A typed string then goes a character every 80 ms (Playwright's own `delay`; at most 1.5 s added in all, as for a move, and a longer delay from the spec kept), so it's seen typed, not appearing at once. So in the filmed pass a key is held about 80 ms and the app's handlers run between characters: a debounced search or a keyup handler can behave differently from the proof. `insertText` puts its whole string in at once, as one action, like a paste. The module adds at most 1.5 s to a move; a slow browser's own time per step comes on top (each paced step is a call of its own, and a trace that snapshots each call makes it slower: about 210 ms a step on the pilot's board). Holding only what a step's round trip didn't take would be faster there, but on the browser host it let two steps reach the page 7 ms apart: part of a round trip's delay can come after the page already has the event. Setup outside a gesture runs at full speed, so the video stays short.

     Nothing outside a gesture waits, and a paced move sends the points Playwright's own interpolation would, one at a time; where a locator action has moved the pointer since `page.mouse` last did, the start isn't known and the move runs unpaced. Inside a gesture the module also counts what can't be called paced, and each logs "[film] a move ran unpaced: ...":
       - a move, press or click after something other than `page.mouse` moved the pointer, which it checks before each of them and once when the gesture ends;
       - a press or key the page received that `page.mouse` and `page.keyboard` didn't send, such as a locator click where the pointer already was, or a locator key. The overlay counts the page's trusted `pointerdown` and `keydown` events. The gesture's end compares them with the most the module's calls could have caused, counted as Playwright sends them: a chord's keys as Playwright splits it, and only typed characters on its US layout, since it inserts the rest with no key. A foreign press or key that fits inside that slack isn't seen;
       - a jump: a move with a step longer than 40 px (`MAX_STEP_PX`), or a click that far from the pointer. It's held, but the pointer is drawn at points, not travelling;
       - a move whose start can't be checked, because the page hasn't seen the pointer since it loaded, or it's over a frame. It runs unpaced, so the film sends the proof's points;
       - a move with a step point on a frame, where the top page can't see the pointer, so the drawn pointer would stall and then jump. It runs unpaced. Only the step points are checked; a frame narrower than a step can fall between two of them, and the drawn pointer steps over it as over anything else;
       - a paced move in which the page itself saw the pointer jump more than 40 px. The overlay records the longest jump between the positions it receives during the move, and the last leg to its end point. It catches where the page got no pointer events, such as a frame inside a closed shadow root, which no lookup finds;
       - a move whose `steps` isn't a whole number.

     A press, a click or the gesture's end that can't be checked (the page hasn't seen the pointer since it loaded, loaded during the gesture, has the pointer over a frame, or couldn't be asked), and a key sent while the focus is in a frame, log "[film] not checked: ..." and make no claim either way. A press or key that goes into a frame (a click by where it lands, a bare press by where the pointer is, a key by where the focus is) is left out of the counts, since the top page never receives it, so it leaves no slack for a foreign one. The counts are per page, so one such press or key leaves the whole video with no claim about pace, and a move from inside the frame then runs unpaced and makes it "full speed". So keep the bug's gesture out of frames where the app allows. Frames are found through open shadow roots too. A move can't be left unchecked: it runs unpaced and counts as such, and that outweighs anything unchecked. So a spec places the pointer with `page.mouse` outside any gesture before it starts, uses only `page.mouse` and `page.keyboard` inside it, with moves in steps of at most 40 px, and ends it before the input that loads a new page. The gesture's end clears its "Watch" caption, so nothing after it sits under one. During a native drag (`draggable`), which stops the page's pointer events until the drop, the overlay follows `drag` and `dragover`, between them at every step, so the drawn pointer keeps moving and the checks keep the drop point. It skips the boundary events right after a `pointercancel`, which report (0, 0). It also follows `pointerover` and `pointerout`, which still say where the pointer went when it enters a frame, so a locator action into a frame reads as a move outside `page.mouse`. What the module can't see at all:
       - a locator hover that ends within 1 px of where `page.mouse` left the pointer, wherever it went in between;
       - a locator action that makes no press, key or pointer move: `fill` (an `input` event only), `selectOption`, `focus`, `setInputFiles`, `dispatchEvent`;
       - anything inside a frame, since the overlay runs in the top document only. A move whose start is over a frame runs unpaced, so the film still sends the proof's points;
       - a frame inside a closed shadow root, which can't be looked into: it reads as its host. A move across it is caught by the jump the page saw, but a press or key into it counts as sent, which leaves room for one nobody sent.

     The overlay sits in a closed shadow root on an element under `<html>`, outside `<body>`, with `pointer-events: none`, and draws in the event handler, with no page timer (which `page.clock` replaces): it changes no hit test, no pointer coordinate and nothing an observer of the body sees. `factory-smoke`'s probe proves those on the browser host, and that it draws and paces (rule 4). A top-layer element (an open `<dialog>`, a popover) paints over it. Under a paused `page.clock`, an app that paints in `requestAnimationFrame` (a canvas) doesn't repaint during a gesture: measured 2026-11-23, the drawn pointer swept across four squares while the canvas still showed the first one highlighted, until the spec advanced the clock. So a spec on a paused clock says so in its gesture's label. A helper that films ends the video's `shows` with the module's `paceClaim(page)` for the recorded page, shortening the rest to keep within 300 characters. It speaks for the gestures only, which the video captions "Watch: ...":
       - `; filmed at a person's pace where captioned "Watch"` when they paced an input and every check passed;
       - `; filmed, but a move captioned "Watch" ran at full speed` when one ran unpaced;
       - nothing when a check couldn't be made or nothing was paced.

     The rule lives in the module, so a helper doesn't restate it (`paceCounts(page)` gives the counts behind it). `caption` cuts a longer caption itself. The module measures text as `evidence.py` measures `shows`: in characters (code points), printable as Python's `isprintable` means it. The module may be loaded from the helper or from a fixture that hands it to the helper (the pilot's import guard allows only the fixture). A test outside the project's `import()` reach (vitest's) can load it with `createRequire`, which needs Node 22.12 or later. Where neither reads `$FACTORY_EVIDENCE_FILM`, the stage runs no filmed pass: the proof's evidence ships, and the stage's report says the video isn't paced.
   - **When the two passes disagree on the bug's own check** (one fails the check of the mechanism and the other passes it), the behaviour depends on speed: that's a finding, never noise. A timeout, a failed precondition, or a pixel comparison under the overlay isn't a disagreement: run the filmed pass again, or put the proof's evidence back (`with-browser --ship-proof`) and say the filmed pass didn't run cleanly. Reproduce: the bug only in the filmed pass is `partially-reproduced`, "only at a person's pace", and the film's evidence ships; the bug only in the proof is `reproduced`, the proof's evidence ships (`--ship-proof`), and the report says the film doesn't show it. Implement, execute and revise: a fix that holds in the proof and fails in the filmed pass isn't done; fix it, or escalate with the finding. They run the spec failing and then fixed, and film the fixed code; the failure shows in the reproduce step's own video when that ran. So the film's evidence ships when it ran cleanly and shows what the proof showed, or shows a failure the proof missed; the proof's ships when the film didn't run cleanly, or misses the bug the proof shows.
   - **`evidence.py` packs it, after the agent and quiesce,** from the frozen copy. It reads only regular files directly in that directory, without following a link, and only those the manifest lists. It writes each screenshot again from its image data alone, which drops every text and metadata chunk. It checks the video's header and writes the trace again entry by entry, refusing a name that isn't plain. It enforces the caps (20 screenshots, 5 MB each; 50 MB of video; a 50 MB trace; 150 MB in all), and it writes a report with the screenshots and the manifest inline that runs no script and loads nothing. What it drops, it says why.
   - **The report is the one link CD needs, on a phone too** (CD, 2026-11-22, over a hosted viewer: "maintaining no code is a plus, and we can just archive the report"). A video of at most 20 MB goes inside it, as a `<video>` element whose source is the WebM as a `data:` URL, and its content policy allows media from `data:` alone. The page sets a phone's viewport. Measured on CD's iPhone, in Safari over HTTPS: Playwright's WebM played that way, unconverted, under that policy, at 4.2, 12.7, 21.2 and 33.9 MB ("they certainly did take some time to load"), while a video handed to the player through a script didn't play, so the page has no script. The video comes after the manifest's table, which shows while it loads: a page shows nothing past a `data:` URL until all of it has arrived. GitHub serves the report's artifact inline, as a page, and the video and trace as downloads. The video's bytes are only header-checked, as before, and a browser now reads them when the page opens rather than when CD downloads the file. A bigger video goes beside the report as its own artifact, and the report says so. `evidence.json`'s `video_in_report` says which.
   - **Each file goes up as its own unzipped artifact** (`actions/upload-artifact`, `archive: false`): the report, the trace, and the video when it isn't inside the report, kept 90 days. They open in the browser. `workflow_policy.py` holds an agent job's uploads to the runner's temp directory or an execution file, never the workspace, and allows only the packed evidence unzipped.
   - **The writer job adds the links** (D2 rule 3): to the report ("report, with the video" when it holds it), a separate video and the trace, each built from the run's URL and the artifact's ID, never from agent text. It also adds the archive path, `<factory.json evidence.archive>/<repository>/<issue>/<run id>/`, known in advance, and the manifest as text, every caption escaped like the rest of the agent's text. A record that doesn't check turns the section into one line saying so; the run isn't lost.
   - **After 90 days, the archive keeps it** (CD, 2026-11-20: "so it's never gone"). `host/evidence_archive.py`, on a timer on the host that keeps it, as its own user with a read-only Actions token, pulls each run's report under that path, with the video when it's a separate file (CD, 2026-11-22: the report, and a video too big to go inside it, "keep the big videos too"; the trace, a desktop debugging tool, lasts GitHub's 90 days). It takes only the factory's implement and revise runs on the default branch, since any workflow can upload a file by those names. It learns the issue from the run's `evidence.json`, which `evidence.py` writes from the job's own environment, and it never overwrites. `host/setup-archive.sh` installs it with root, on storage the host already has: redundant, with a quota and daily snapshots. Creating that storage is the host's own business.

8. **A bug the code can't confirm is reproduced before it's planned** (CD, 2026-11-20). Planned work was otherwise never reproduced before its plan was written: in the pilot project, triage left 4 of 16 issues unreproduced, and half of its plan PRs were UI work built on unconfirmed causes. The plan stage can't do it itself, since the planning tier reads production data and must not run app code.
   - **Triage stays code-only.** When it returns `ready-to-plan` for a web-app bug whose cause the code didn't confirm, it sets `needs_repro` (`sdlc-triage` step 7b). Its apply job decides the route from the default branch's `factory.json`, never from the agent: with a browser host and `reproduce` in `browser.stages`, it adds `factory:needs-repro` and dispatches the implement workflow with `reproduce`, instead of the plan stage. Without them it says the cause is unconfirmed and starts the plan, as before. A direct-tier fix skips the step, since implement reproduces first anyway.
   - **The reproduce job** runs on the strict tier in the implement stage's sandbox, with the route for `reproduce` (`sdlc-reproduce`). It writes the failing spec through the route, records the evidence (rule 7) and commits nothing. It returns one of four outcomes with the spec, what was tried and the failed requests (`reproduce.schema.json`).
   - **Its report job** (`reproduce_report.py`, as the App) posts the outcome on the issue. The summary, what was tried and the failed requests go in as escaped text, the spec in a fenced block whose fence the writer picks, and the evidence as links the writer builds. Then:
     - `reproduced` or `partially reproduced`: the plan starts, and reads the spec from the comment;
     - `not reproduced`: `factory:needs-input`, with a `reproduce` stage marker, so CD's reply runs the step again with what it adds, and nothing is planned first;
     - `blocked`: the plan starts, its comment saying the cause is unconfirmed.

     It starts the plan only for an issue still open and labelled `factory:ready-to-plan`, since CD may have re-triaged it meanwhile. The spec is agent text in an App comment, so every reader of a marker takes it only from the comment's leading marker block (D1 rule 5): the tier readers in the plan stage and `factory:go` were anchored to it with this rule. A spec with bidirectional or invisible control characters is refused, and one too long to post with the rest is left in the run's transcript.
   - **It's a mode of the implement workflow, not a workflow of its own,** so it needs no change to the runner group's selected workflows. Resume restarts it (`reproduce` → the implement workflow with `reproduce`), and `factory:go` starts it for a held issue that carries `factory:needs-repro`.

### Forbids

1. A browser in a stage's job or sandbox, or a browser MCP server in a stage's config.
2. Giving a stage the route before `factory-smoke`'s `browser-host` job has passed, or keeping it while a property of rule 3 is missing.
3. A strict-tier opening beyond the browser host's front-end ports, or a sandbox entry for the browser host beyond the project's one port.
4. A browser, launch option or proxy the client chooses taking effect on the browser host.
5. Reporting a bug reproduced or ruled out when the browser host was unavailable.

### Costs

- A machine, its upkeep and its own reviewed setup. Each Playwright version a project uses needs a front end there, and a project's upgrade needs one before its stages can use the browser.
- A remote browser is slower. Each request makes extra round trips through the tunnel, and timing-sensitive specs flake: one passed 2 of 4 runs on the browser host that passes on the CI host. Specs drive the app's timers with `page.clock` rather than wall time, and a timeout on its own never counts as reproduced.
- Two browsers at once across every project, since an 8 GB host holds about two. A run that waits past the queue is `blocked`.
- The browser renders with the host's own fonts, not the CI image's, so pixel comparisons differ from CI.
- The filmed pass runs each reproducing and verifying spec a second time, holds about 80 ms for each step of a gesture's moves and each character it types, and keeps a copy of the proof's evidence on the runner until the stage ends (rule 7).

### Leaves open

- **Which Playwright versions the host serves,** and who adds one when a project upgrades.
- **Whether a timing-sensitive spec failing on the browser host counts as reproduced.** Only a failing check of the mechanism does; a timeout alone doesn't.
- **The archive** (rule 7): until a host runs `setup-archive.sh`, evidence lasts GitHub's 90 days, and `evidence.archive` stays empty so no PR names a path that doesn't exist. How the API serves an unzipped artifact for download isn't documented; the puller takes the file either bare or in a zip of its own, and its first live pull is the proof.

### Revisit when

- Playwright changes how `connect` works, `run-server`'s launch-option filter, or `exposeNetwork`.
- The browser host leaves macOS (Asahi Linux is the fallback if its lockdown can't hold) or gains a second browser host.
- GPU passthrough to a job's container becomes safe on a host that does nothing else, which would make option 2 worth another look.

---

## Tiers in the factory

The factory routes by `CLAUDE.md` § Three Tiers of Work, with one rule of its own for API and schema
changes, which an unattended run can't negotiate with CD:

- **Additive** changes are **lite**: a new field on a response, a new nullable column, a new endpoint
  that changes nothing existing. Never direct: implement hands them back (`rescope`).
- **Breaking or reshaping** changes are **full**: renaming, removing or retyping fields, changing an
  endpoint's or message's shape, migrating existing data.

A project's `CLAUDE.md` can be stricter; it can't move either kind to direct.

## Where to look

CD approves every merge, and a PR's Risk line and Review focus are the agent's own judgment. So a project
names the files CD should always look at, and the factory finds them in each code PR itself (CD,
2026-10-24):

- **The rules** are `factory.json`'s `review.focus`, which the publish guard (`implement_guard.py`)
  reads from the default branch, never from the factory branch. Each has a `name` and a `why` (both
  shown) and an optional `tier` (`medium` or `high`). It picks files with `paths` and leaves some out
  with `except` (CODEOWNERS patterns; a directory covers everything beneath it). It can also require a
  line the file's diff adds (`added`), removes (`removed`) or either (`changed`) to match a regex. A rule
  with both paths and a line regex needs both to match, and it needs at least one of them. A rule with
  no `paths` reads every changed file, docs and tests included, so leave those out with `except`.
  `except` belongs on rules that read lines: on a rule with only paths it reopens what the paths close.
  An `except` pattern covers what's beneath it only when it ends in `/` or `/**`. Leave tests out by
  their directories, not by name: a production file can be named like a test.
- **What CD sees.** A code PR's Review focus opens with Where to look: each flagging rule, its tier, why
  it matters and every file it flags. The description lists them over the whole PR, from where it leaves
  the default branch, when it's written: when the PR opens and when a continued execution finishes.
  Each later stop short of done (before a gate, or escalated) lists that segment's own in its comment on
  the issue, or says nothing matched, so CD sees them before approving the gate or deciding the findings. A revision's comment lists the flagged files that revision changes. A file one
  commit changed and a later one changed back is still listed by the rules that need no line, marked as
  such. A move counts as one only for a rule whose scope holds both names, which then reads only what the
  move changed; a file moved into or out of a rule's scope is read in full. When a rule flagging the
  final diff has a tier above the agent's rating, the Risk line leads with it and still names the
  agent's: "**High** by the project's review rules (Migration); the agent rated it **Low**".
- **What it holds against.** The agent can read the rules but not change them, and only the writer job
  writes these lines. A path can't be hidden: a migration has to sit where the framework runs
  migrations from. Paths protect places the framework enforces, though, not logic: code copied to a new
  file outside a rule's `paths` isn't followed, so a path rule can be dodged by moving the logic. A line regex catches an honest mistake, but a hostile
  agent that reads it can write around it, so put what matters most under `paths`. A name that isn't
  plain renders as escaped text, with every character outside printable ASCII shown as its code point
  (an invisible or lookalike one would make it read as another file), and a long one is cut in the middle.
  A description or comment over 60,000 bytes, or a segment's list over 30,000, is refused before anything
  is pushed (GitHub's cap is 65,536 characters), and so is a file name that isn't UTF-8.
- **Not a gate.** It says where to look, and CD still approves every merge. Plan and spec PRs get none:
  they change documents only.
- **Deterministic only.** No model judges the diff: the writer job that renders the PR runs no agent.
  Line regexes read whole lines and have no timeout, so keep them simple. Rules that don't load turn
  Where to look off, and Review focus says so; the PR still publishes, so the agent's run isn't lost.
  The bundle's tests load the project's rules, so CI catches a broken one on the PR that adds it, and
  run each line regex on long lines in a process they can stop: one that takes over 2 s, or never
  finishes, fails CI with its rule's name.
- **The project's always-high areas** (the PR template's Risk Tiers) are checked as `high` rules, and
  the template's project block says so; a change to one changes the other.
- **The seed** starts a project with rules for migrations (the `migrations/`, `Migrations/` and
  `alembic/` directories), bulk writes and raw SQL, access checks, auth code and configuration reads,
  scoped to source files and leaving out test directories (and Django's `tests.py`). The line rules
  come in packs by framework: the first ones know Django's and ASP.NET Core's names, and the ones
  marked (SQLAlchemy) and (FastAPI) know `text()`, a driver's own connection (asyncpg, psycopg), SQL in a
  string (a line opening with `UPDATE`, `INSERT` or `DELETE`, or a quoted one), Core's `delete(Model)`
  and `update(Model)`, upserts and bulk mappings, and FastAPI's security dependencies, CORS and
  middleware. A project keeps the packs its stack uses, and one on another framework adds its own.
  Auth code is a paths rule (`auth/`, `auth.py`, `security.py`, `permissions.py`, `deps.py`): check it
  names where the project's auth lives. `QuerySet.update(` isn't in it: no regex tells it from
  `dict.update(`. A project adds its own always-high areas as rules with
  paths, such as the code that computes money. Migrations never touch seeds: a project installed before
  this has no `review` block, and its PRs list nothing until it copies the seed's in.

## The stages' sandbox

What every code-writing stage's agent works inside (D2), stated once and mirrored into the skills
that run there:

<!-- MIRROR-SOURCE-START: factory-sandbox -->
- **Bash is sandboxed:** it can write only the workspace and the temp directory, and has no network. Dependencies are already installed; nothing can be installed. The one exception is the browser route, when this stage has it: `/opt/factory/with-browser <command>` reaches the browser host's front end for the project's Playwright, and the browser loads only what the command serves on its own `localhost` (`[sdlc-root]/process/factory.md` D6). Without the route it prints `UNAVAILABLE: browser host`. Empty files the sandbox mounts at the repository's root while a command runs (`.bashrc`, `.gitconfig`, `.vscode` and the like) aren't the run's: never stage, remove or ignore them; the job excludes and removes them.
- **No GitHub access:** no `gh`, no push. The issue is in the context file.
- **Off-limits paths:** edits to `.github/`, `.claude/`, `CLAUDE.md`, `.mcp.json` and `.git/` are denied, and the publish job rejects any commit touching a path in `.github/CODEOWNERS` (the project's test and build config, dependency manifests, `[sdlc-root]/` and the like). The SDLC hygiene files are the exception, and you may write them: the discipline parking lots (`[sdlc-root]/disciplines/*.md`) and the knowledge YAMLs (`[sdlc-root]/knowledge/`), except the eight that route or govern agents (`[sdlc-root]/knowledge/agent-context-map.yaml` and seven in `[sdlc-root]/knowledge/architecture/`), which the publish guard refuses by name. It also refuses other agents' and editors' configuration (`AGENTS.md`, `GEMINI.md`, `.codex/`, `.gemini/`, `.cursor/`, `.vscode/`, `.devcontainer/`), all of these in any letter case, and a path that differs from another only in case. A knowledge entry the fix makes wrong is corrected in this PR, and an existing entry it corrects or removes is marked as that doc's grammar says (`[sdlc-root]/process/project-section-markers.md`), or the next migration may take it back; one this run added needs no mark. If the change needs one of them, stop (Edge Cases).
<!-- MIRROR-SOURCE-END: factory-sandbox -->

| Mirror | Copies |
|---|---|
| `factory-sandbox` | `sdlc-implement`, `sdlc-revise`, `sdlc-reproduce` |

## Reproducing in a browser

How a code-writing stage proves and verifies a bug a user sees in a web app, when the stage has the browser route
(D6), stated once and mirrored into the skills that run there. `sdlc-execute`'s UI smoke check and
`[sdlc-root]/process/review-fix-loop.md` Step 0.5 point here for a factory run.

<!-- MIRROR-SOURCE-START: factory-browser -->
**A bug a user sees in the web app is reproduced in a real browser when this stage has the browser route** (`[sdlc-root]/process/factory.md` D6). `/opt/factory/with-browser <command>` runs a command with the browser host reached, and the browser loads only what that command serves on its own `localhost`. Without the route, it prints `UNAVAILABLE: browser host (<why>)` and exits 75.
1. **Before the fix,** an agent writes the smallest Playwright spec that follows the reported steps (the issue's, or CD's request's) and runs it alone, at one worker, through `/opt/factory/with-test-services /opt/factory/with-browser`, with the project's own Playwright command, so the project's config starts the app's servers in the same command. The run must fail for the reason the issue gives. Build the spec on the project's own end-to-end fixtures (its test sign-in, its seeded state), not on clicking through the whole UI. Drive the app's timers with `page.clock`, never wall time: a remote browser adds round trips. The spec stays in the PR (CLAUDE.md § Bug-Fix Rule), named `repro-<issue>-<slug>.spec.ts` where the project's Playwright config runs it (its CLAUDE.md or verify skill says where), so one pattern there picks up every kept spec.
2. **Follow the report's steps first,** then make at most two targeted variations. Find the UI's elements by searching the code for their strings, not by clicking around.
3. **Report one of four outcomes** in the result:
   - `reproduced`: a check of the mechanism fails as the report says. A timeout alone is not one.
   - `partially reproduced`: part of what the report describes, said which.
   - `not reproduced`: with what was tried. It is a valid result.
   - `blocked`: the browser host was unavailable, or an outside service the feature needs is offline. It never counts as reproduced or ruled out.
4. **List every request the page made that failed** (Playwright's `requestfailed`, and responses of 400 or more), not the servers' own output: a dev server stopped at the end of a run prints a failure of its own. An outside host is blocked by design, and is listed, except one CD allowed for the project (`$FACTORY_BROWSER_ALLOW`), which the spec, or the project's helper its specs use, serves with `context.route`, fetched through the sandbox's proxy with Node's `fetch`. A skipped test counts as not passing.
5. **A helper agent drives the browser and reports in text.** Screenshots, video and traces stay in its files, never in the orchestrator's context (the manager rule): under `.factory/evidence/` and nowhere else, with a `manifest.json` that lists each file as `{"file", "step", "shows", "bug"}`. A file's `bug` is true only when that file itself shows the bug, never because its test failed, and its `shows` opens with what the file shows: one printable line of at most 300 characters, since a longer one drops the whole manifest. A measurement the picture can't show (a hit test, an observer's record) never stands in for what it shows; it may follow, marked: "pointer resting on a card, its popup open; checked: the path crossed the Undo button". The factory keeps the first video and the first trace the manifest lists and drops any other, so they record one page of one test: when the spec has more than one test, or drives more than one page (two users, say), record the page, and order the tests, so the kept recording is the one where the bug happens. Where the project has an evidence helper, it writes those files and the manifest: never write a manifest by hand beside it. The reproducing and verifying runs record plain video (Playwright's `recordVideo`, never annotated: D6 rule 7) at a fixed viewport, which `$FACTORY_EVIDENCE_VIDEO` (1) asks for. Each is a proof, run as CI runs it. Where the project's evidence helper loads the film module (its helper or a fixture reads `$FACTORY_EVIDENCE_FILM`), a filmed pass follows: the same spec once more, last, alone, through `/opt/factory/with-browser --film`, at a person's pace, and its evidence ships, unless it didn't run cleanly or the bug shows only in the proof: then `/opt/factory/with-browser --ship-proof` puts the proof's back, which `--film` kept, provided nothing else ran through `with-browser` since the filmed pass; when it fails, run the proof again (D6 rule 7). For it, the spec wraps the moves and presses that show the bug in the helper's `gesture(page, label, fn)`, using only `page.mouse` and `page.keyboard` there: moves in steps of at most 40 px, and presses where a move ended. Place the pointer with `page.mouse` outside any gesture before it starts: until the page has seen the pointer, the first move's start is unknown. End a gesture before the input that loads a new page, place the pointer again, then start another. The helper puts each step's `shows` on the picture. A run that logs "[film] a move ran unpaced" did one of these: moved the pointer or pressed some other way (a locator action, say), jumped, started where the page hadn't seen the pointer, or gave a move a `steps` that isn't a whole number. Its video says a move ran at full speed: fix the gesture as the log says and film again. "[film] not checked" (a click that loaded a new page, a frame) needs no fix: that video makes no claim about pace. A spec on a paused `page.clock` says in the label that the app repaints only when the clock advances. When the two passes disagree on the bug's own check, report it as D6 rule 7 says. Where the helper doesn't load the module, run no filmed pass: the proof's evidence ships, and the result says the video isn't paced. A run that repeats the spec (`--repeat-each`, or a retry) keeps evidence from its first repeat only (`testInfo.repeatEachIndex` 0), and the result says how many repeats passed. A run that records video takes its trace without screenshots (`tracing.start({ screenshots: false })`): the video is the visual timeline, and with video on Playwright captures the trace's frames at the video's size, which pushes a long run's trace past the 50 MB the factory keeps. A stage that runs its spec failing and then fixed films the fixed code: its filmed pass is the last run. The folder holds whatever the last run to write it left: when the latest run was refused (by the project's guard, say) or never started, the files are an earlier run's, so treat the latest as not run (reproduce reports `blocked`) and cite none of them. After `--ship-proof` they're the proof's, which is the run to cite. The factory checks and packs that folder for the PR, and drops anything else.
6. **After the fix,** the same spec runs again and passes.
7. **Run only the reproducing spec, never a whole suite:** the browser host holds two browsers across every project.
8. **CI may not run the kept spec.** Where the project's end-to-end suite doesn't run in CI, or doesn't pick up the spec's file, the result says so: the spec is the stage's own evidence.
<!-- MIRROR-SOURCE-END: factory-browser -->

| Mirror | Copies |
|---|---|
| `factory-browser` | `sdlc-implement`, `sdlc-revise`, `sdlc-reproduce` |

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
| `factory:review-capped` | implement or execute | The review cap was hit. A draft PR is parked with an open-findings table. |
| `factory:advisor` | triage or CD | A property, not a state: planning gets an advisor. Triage sets it when the plan turns on judgment and clears it otherwise; a label CD added always stands. State sweeps leave it alone. |
| `factory:follow-up` | follow-up filer | A property: filed from a merged plan's checklist. Triage runs, then holds; the App's provenance marker, not the label, decides the hold. |
| `factory:go` | CD | Releases a held issue (a follow-up or a split part): starts its triaged stage once, then removes itself. Needs write access. |
| `factory:needs-repro` | triage | A property: the code alone didn't confirm this web-app bug, so the reproduce step (D6 rule 8) runs before the plan, and `factory:go` starts it for a held issue. Set only where the project has that step. Triage clears it when it no longer flags the issue, and the step removes it once the bug reproduced or it was blocked; CD removes it to plan without reproducing. |
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
| `verify [<area> ...\|probe]` | The stages and smoke | The project's checks (tests, lint, type check, build), in the profile's own areas, which `--print` lists; `probe` proves the toolchain and the test database work, and loads the Vite and Vitest configs as those tools do. Reads its directories from `verify.conf`. |

The interface is the first profile's shape: `agent_job.sh` passes `stack.python` and `stack.node` as
the project's two directories (`verify.conf`'s `python=` and `node=`, beside `database=`,
`stack.database`), whatever the stack. A profile for another stack uses them for its own directories,
and may find more itself: `python-uv-node` checks every top-level uv project, with `stack.python`
naming the one that holds the database. Renaming them is a change to every project's `factory.json`,
left until a stack doesn't fit that. Start from a copy of the nearest
profile, keep its security properties (no superuser test login, services started with an empty
environment, nothing installed inside the sandbox), and prove it with `factory-smoke`.

| Profile | `stack.python`, `stack.node` | `verify` areas | Test services | What the project must meet |
|---|---|---|---|---|
| `python-node` | The Django project; the Vite app (npm) | `python` (pytest), `node` (eslint, `tsc -b`, Vite build) | Postgres 16 and Redis 7 | Django reads the env file; `probe` runs `manage.py migrate --plan` |
| `dotnet-node` | The directory of the solution (or project) `dotnet` builds; the Vite app (pnpm) | `dotnet` (`dotnet test`, Release), `node` (eslint, `tsc -b`, vitest, Vite build) | Postgres 16 | Tests in the categories `Nightly` (long suites on their own schedule) and `External` (they need the network or a secret, which no job has) are left out; `eslint .` must pass, not only the paths the project's lint script names; the default connection string names `stack.database` as database and user (ASP.NET Core reads no env file) |
| `python-uv-node` | The uv project holding the database and its alembic migrations; the Node app (pnpm). Every top-level directory with a `uv.lock` beside its `pyproject.toml` is a uv project, installed and checked | `python` (in each uv project: `ruff check`, `ruff format --check`, `mypy`, the tests outside `tests/integration`), `migrations` (alembic `upgrade head`, `downgrade -1`, `upgrade head` on a fresh database each run), `integration` (`tests/integration` without `slow`), `node` (`eslint .` with no warnings, `tsc -b`, `vitest run`) | Postgres 17 with pgvector (in template1's `extensions` schema, on the role's `search_path`) and Redis 7 | Each uv project's mypy targets in its own configuration (`files`), and a bare `pytest --ignore=tests/integration` collecting what CI's unit run does; `ruff` and `mypy` in each project's locked dev group; `ruff format --check .` passing everywhere; `eslint .` passing; `alembic.ini` beside `stack.python`'s project, its `env.py` reading `DATABASE_URL`; the settings reading only `DATABASE_URL` and `REDIS_URL` from the env file (it holds nothing else, so settings that refuse unknown keys load) and the tests reading `TEST_DATABASE_URL` and `TEST_REDIS_URL` from the environment, which `with-test-services` exports; integration tests in `stack.python`'s `tests/integration`, the long ones marked `slow`; `.venv/` ignored |

`verify` calls the tools, never a Makefile or package.json script, so a check a project's build
script chains in (a bundle-size gate, a generated file) is left to CI on the PR. The Node tools find their
configs by name, the first name in each tool's order winning, so an added `vite.config.js` would replace a
project's `vite.config.ts`, and an added `vitest.config.ts` the test settings it keeps in `vite.config.ts`.
`agent_job.sh workspace` records, before the agent starts, the config file eslint, Vite and Vitest each load
in the checkout (`node_configs.py`, into `verify.conf`). `verify` passes those files to the tools
(`--config`; eslint's only when it's in `stack.node` itself), and its node area fails, naming the file, when
a tool would now load another, or Vitest another workspace file. CI runs the tools without the pin, so such a
file is refused at publish too, since CODEOWNERS covers each of these names (below). The Python profiles run
pytest without the project's directory first on `sys.path`, as CI's `pytest` script does: `python -m` would
put it there, where a module named like pytest or anything it imports replaces it (`python-node` sets
`PYTHONSAFEPATH=1`; `python-uv-node` runs `.venv/bin/pytest`). A project's own `pythonpath` setting still
applies. In the sandbox, Unix
sockets are blocked, and MSBuild's worker nodes use them: `dotnet-node` builds in one process
(`-m:1`), and `verify --print` tells the agent to do the same (`dotnet run` and `dotnet ef` ignore
the switch, so they run with `--no-build` after a `dotnet build -m:1`). In the pilot project's first implement
run, a `.aspnet/` appeared beside the server project once the end-to-end specs had started the server, and
stopped the publish as an uncommitted change. Outside Windows, ASP.NET Core keeps its data protection keys
under `$LOCALAPPDATA/ASP.NET/` when that variable is set, else under the user's home's `.aspnet/`
(`DefaultKeyStorageDirectories`, read in its source). Reproduced with the server in .NET's runtime image, as a user with no
passwd entry: an empty or unset HOME gave in-memory keys and no folder, while `HOME=.` wrote the run's exact
path. So the sandboxed command's HOME was likely relative, though the agent step's own was `/github/home`.
`dotnet-node` sets
`LOCALAPPDATA` into `.factory/`, names `.aspnet/` in its `excludes` (D2 rule 4) for anything else that writes
there, and its `verify probe` prints what HOME a sandboxed command has, absolute or not, and whether its user
has a passwd entry, so `factory-smoke` shows it. End-to-end suites
(Playwright) are not in `verify`: they need browsers and live servers, and CI runs them. A stage with the
browser route (D6) runs the project's own Playwright through `/opt/factory/with-browser`, which composes with
`with-test-services`: the app's servers start in the sandbox and the browsers run on the browser host. A
project whose end-to-end setup needs steps before its servers start (a build, migrations, a production bundle)
keeps them in one code-owned script, so a stage doesn't rediscover them each run.

**What CODEOWNERS must cover, per profile** (Enablement step 9). A revise or continued run installs a
factory branch's dependencies outside the sandbox, and the project's CI builds a factory PR's code.
Both rely on no factory commit having changed a file a tool loads just because it exists. The
publish guard and the branch check refuse only what CODEOWNERS covers, so it must cover each of
these at any depth, whether or not the project has one yet. GitHub's CODEOWNERS matching is
case-sensitive, so cover every casing a tool accepts (the guard itself matches an owned line in any
case). The guard keeps a sample of every name below for each profile (`implement_guard.PROFILE_BUILD_FILES`),
which the project's seeded CODEOWNERS test reads: a change to this list changes those samples with it, and a
new profile adds its own.
- **`python-node`:** `requirements*.txt`, `pyproject.toml`, `setup.py`, `setup.cfg`, `pytest.ini`,
  `.pytest.ini`, `pytest.toml` and `.pytest.toml` (pytest 9 reads them before `pyproject.toml`),
  `tox.ini`, `conftest.py`, `sitecustomize.py`, `hatch.toml` and `hatch_build.py` (a hatchling build
  hook runs when the project installs, outside the sandbox), any in-tree build backend a
  `pyproject.toml`'s `backend-path` names, and the Node files below.
- **`python-uv-node`:** `python-node`'s list, in every uv project, plus `uv.lock`, `uv.toml`,
  `.python-version` and `.python-versions` (uv picks the interpreter from them), `ruff.toml`,
  `.ruff.toml`, `mypy.ini`, `.mypy.ini`, `.coveragerc` (its `plugins` import modules) and
  `alembic.ini`, and the Node files below with pnpm's.
- **`dotnet-node`:** `*.csproj` (and `*.fsproj`, `*.vbproj`), their `.user` files (MSBuild imports
  `<project>.user` when it exists), `*.props`, `*.targets`, `*.rsp` (`Directory.Build.*`,
  `Directory.Packages.props` and `Directory.Solution.*` among them), `*.sln`, `*.slnx`, `*.slnf`,
  `global.json`, `nuget.config`, `NuGet.config` and `NuGet.Config`, NuGet's lock files
  (`packages.lock.json`, and `packages.*.lock.json` where projects share a folder: restore uses one just
  because it exists and fetches exactly its versions, transitive ones included, while the project's
  dependencies are unchanged), and any lock file a `NuGetLockFilePath` names,
  `.config/dotnet-tools.json` and a root `dotnet-tools.json`, `*.runsettings`, `xunit.runner.json`,
  `.editorconfig`, `.globalconfig`, and the Node files below. A project file can run code during
  `dotnet restore`, so owning `*.csproj` makes a new project or package CD's change; the implement
  sandbox can't fetch a package anyway.
- **Node, in both:** `package.json` (`install` runs its lifecycle scripts), `.npmrc`, the eslint
  (`eslint.config.*`, `.eslintrc*`), TypeScript (`tsconfig*.json`), Vite and Vitest
  (`vite.config.*`, `vitest.config.*`, and `vitest.workspace.*` or `vitest.projects.*`, which choose the
  tests Vitest runs) configs, the PostCSS and Babel ones Vite loads when they exist (`postcss.config.*`,
  `.postcssrc*`, `babel.config.*`, `.babelrc*`), and the env files it loads into the build (`.env*`: `.env`,
  `.env.local`, `.env.<mode>`; a template nothing loads, such as `.env.example`, may be un-owned again after
  that line); for
  npm (`python-node`) `package-lock.json`, and for pnpm (`dotnet-node`, `python-uv-node`)
  `pnpm-lock.yaml`, `pnpm-workspace.yaml` and `.pnpmfile.cjs`.

---

## Enablement

**The order to do these in, what to ask CD before starting, how to tell each step worked, and what to
build when a project brings a stack, data route or production host the factory hasn't seen:**
`[sdlc-root]/process/factory-runbook.md`. Read its opening and its § 0 before starting: these steps are a
small part of an install whose project doesn't fit an existing profile or host. `sdlc-run-runbook`
runs it in the project's session (`factory-enablement`).

The bundle installs inert: nothing runs until a person adds `factory:triage` to an issue, and the
first run fails without the setup below, done in order. Steps 3 to 5 replace the seed's placeholders
in `factory.json`; after each settings change, run `python3 .github/factory/render.py` and merge the
settings and the workflows into `main` through a PR. `python3 .github/factory/bootstrap.py` checks steps 2 to 9 and
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
   reads. When `stack.node` is below the root, the repository keeps a code-owned root `package.json`
   (`{"private": true}` will do; D2 rule 2). The profile is rendered into `factory-image` (it builds that profile's `Dockerfile`), so
   render after choosing it, or CI's render check fails. `.gitignore` must cover the env file and
   `.factory/` (the jobs' working files and the profile's caches): a run that leaves an untracked file
   isn't published. It must also cover `.github/factory/host/reg-token`, the runner registration
   token step 8 puts there. Tests that need fixtures from a secret-holding source get them through the
   `fixtures` block (D2 rule 7); leave its `path` empty for none. Write `triage-policy.md` (its
   direction, rules, containers, plan triggers and external sources). Set the files CD should always
   look at in `factory.json`'s `review.focus` (§ Where to look), starting from the seed's rules. The planning tier (D3) is
   required; its database is optional. To give the plan and spec stages one, fill `planning.json` and
   create the read-only role it names (D3 rule 3); list services in `services.json` (D3 rule 4). Leave
   both empty for none.

   **The release model** (D4 rule 13): `factory.json`'s `release.branch` is `release/production` by
   default, and the workflows render with it from the install on. So, before the first plan that
   releases:
   - create the branch at `main`'s tip;
   - add its two rulesets (step 9);
   - point every host that serves production at it, with the host's own branch deploy (a Railway
     service's trigger, a Vercel project's production branch), and turn off deploys from any other
     branch.

   `bootstrap.py` reports what's missing. Which case a project is in:
   - **A host that deploys a branch by itself:** keep the default.
   - **Nothing in production yet:** keep it too. The branch records what's released until a host follows it.
   - **A host that can't follow a branch yet** (a Compose host, until its broker follows the branch):
     set `release.branch` to `""`. Deploys are then gates' operations, the fallback.
3. **The job image.** Set `image.repository` to where the organization publishes it (for example
   `ghcr.io/<org>/factory-job`), render, and merge it into `main`: `factory-image` builds the profile's
   `Dockerfile` on a GitHub-hosted runner and publishes it (or run it by hand). Its run on the
   install's own merge fails, publishing to the placeholder; this one is the first that counts. On
   a package's first publish, GHCR can refuse the tag (`error from registry: denied`) in the
   same second it creates the package and takes every layer: re-run the job, and it publishes. Copy the digest from
   its run summary into `image.digest` and render again. Every factory job runs in this image, pinned
   by its digest. Projects on the same profile can share one image: give each repository read
   access to the package.
4. **The echo service.** Smoke proves the sandbox's credential masking against a host that echoes
   each request's headers back. Deploy `.github/factory/echo/worker.js` as a Cloudflare Worker on a
   `workers.dev` address (for example `npx wrangler deploy .github/factory/echo/worker.js --name
   factory-echo --compatibility-date 2025-01-01`), or run `echo/server.py` on any host behind HTTPS,
   and set `smoke.echo_host` to its host name. It stores nothing, and receives only smoke's
   throwaway values; one serves the whole organization. Its `/mcp` route is the stand-in MCP server
   smoke's `mcp-services` job calls. A deployment from before that route serves the other jobs, but
   an organization whose projects list an MCP service redeploys it once.
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
   (`docker-ce-rootless-extras`) and room for the runners' work and images. Commit the host's own
   settings in `.github/factory/host/host.conf` to `main`: setup uses the default branch's, never a
   checkout's. Then, from a checkout of `main`, for each tier, write a runner
   registration token (`gh api -X POST orgs/<org>/actions/runners/registration-token --jq .token`) to
   `.github/factory/host/reg-token` (mode 600) and run `sudo bash .github/factory/host/setup.sh` (the
   strict tier) or `sudo TIER=planning bash .github/factory/host/setup.sh` (the planning tier), and
   `sudo TIER=ci bash .github/factory/host/setup.sh` for the CI tier if the project needs one (step
   10). It creates each tier's user, rootless Docker, firewall and runners, and registers no runner
   whose jobs can reach the host or the LAN. **Root never runs the checkout's files.** The checkout's
   owner, and any agent session running as that login, can change its files, its git metadata and its
   config (a replace ref makes `git show` and `git status` lie), so setup's bootstrap fetches the
   tier's repository's default branch into a root-owned clone, with root's own read-only deploy key and
   a git that reads no config and no replace refs; stages every file it reads from that clone, each
   checked against the blob id its tree names; and re-executes the staged copy. The repository is the
   tier's record's, or `TIER_OWNER`'s on its first run, never the checkout's remote. The first run for
   a repository prints the key and stops: add it to the repository as a deploy key with write access
   off (one key per repository and host, at `/etc/factory-runner/deploy-keys/<owner>/<repository>`),
   then run setup again. Setup refuses a checkout whose `setup.sh` or `host.conf` isn't the default
   branch's. What remains is the bootstrap itself, the checkout's script: whoever can change it
   before you run it gets root, so run setup from a checkout no agent session can write, such as a
   fresh clone made just before by a login no agent session uses. Put the host's own LAN and VPN addresses in
   `factory.json`'s `smoke.host_probes`, so smoke checks them too: the runner host's own, never another
   project's planning database exception. One host serves the whole
   organization, and can serve other organizations too: each one after the first sets `RUNNER_INSTANCE`
   in its `host.conf` and gets its own users, firewall tables and services, isolated from the others'
   as from the host. Setup refuses runners registered to another organization, and a planning database
   port is only ever the organization's own. Each tier has one designated repository, recorded in
   `/etc/factory-runner/tiers/<unit>`: setup refuses a run for another repository, whose `host.conf`
   would re-cap or re-label a tier it doesn't own. The record is made only when the operator names
   the repository and the tier, so the first checkout to run doesn't claim a tier by default: the
   first run for a tier is `sudo TIER=<tier> TIER_OWNER=<owner>/<repository> bash
   .github/factory/host/setup.sh`, from that repository's checkout.

   **The shared host's own repository** (CD, 2026-11-06). The strict and planning tiers serve every
   project in the organization, so their setup and settings live in a repository of their own, never
   a project's, and that repository owns them. It holds:
   - `.github/factory/host/`;
   - a minimal `.github/factory/factory.json` with only the runner labels and groups setup reads
     (`runners.strict`, `runners.planning`, `runners.ci` and `runners.groups`);
   - the host's committed `host.conf`.

   A tier's owner is only the source of the host's settings. But setup runs the owner's own default
   branch, so a project that owned a shared tier would hold back the host's upgrades for every project
   until it migrated. The CI tier is the exception: the project whose CI it runs owns it, because its
   job image is built from that project's toolchain (`factory.json`'s `ci` block). The host repository:
   - **runs nothing:** it's in no runner group and runs no workflows, with Actions off;
   - **has the organization's strongest protection on its default branch,** since whoever can merge
     there gets root on the runner host at the next setup run: a PR with code-owner review, updates
     restricted to admins in pull-request bypass mode, and no force push or deletion;
   - **takes each z-sdlc release** by copying the bundle's `host/` files at the release's tag, never
     `host.conf`. Its tiers' setup then runs again from a fresh clone of it.

   A new project in an organization that already has a host needs nothing here. To move a tier to
   another owner, remove its record (`/etc/factory-runner/tiers/<unit>`), then claim it again with
   `TIER_OWNER`, from a fresh clone of the new owner.

   Each tier's firewall table is loaded again whenever
   `nftables.service` starts or reloads, since its stock ruleset begins with `flush ruleset`, and after it stops,
   since its stock `ExecStop` flushes it. On a host running Tailscale, each runner user is denied
   `/run/tailscale` by an ACL that `tailscaled` reapplies on every start: its local API dials tailnet peers as
   root for any local user, past a firewall that matches the user. The firewall rejects all IPv6 for the runner users (a host's global addresses and its
   LAN's global prefix would otherwise be reachable), and the isolation test probes IPv6 too. Runners
   never update themselves (`--disableupdate`): they stay at `setup.sh`'s `RUNNER_VERSION`, whose
   checksum it verifies. z-sdlc bumps it within 30 days of each actions/runner release, because GitHub
   stops sending jobs to older runners. After the release that brings a bump reaches each tier's owner
   (the host repository's copy of `host/` for the shared tiers, a migration for the CI tier's
   project), run that tier's setup again from a fresh clone of the owner. On the strict and planning
   tiers it upgrades each idle runner in place: it downloads and checks the new version once, before
   it stops any runner, so a failed download leaves every runner as it was, running. The CI tier's
   runner version is an input of its job image, which setup rebuilds.

   **Runner labels.** GitHub gives every self-hosted runner its own default labels (`self-hosted`,
   `linux`, `windows`, `macos`, `x64`, `x86`, `arm`, `arm64`): `self-hosted`, its OS and its
   architecture. A just-in-time runner gets only the labels it's registered with. The factory treats
   those as GitHub's: setup and the CI launcher refuse a tier with no label beyond them, the workflow
   policy never takes one for a hosted label, and the runner audit (step 12) leaves them out of what
   it compares. So a runner's other labels in GitHub's runner list are the factory's, its tier's label
   from `factory.json`'s `runners` block. Each script keeps its own copy of the list, since each runs
   where no shared file reaches it, and the bundle's tests hold the copies to one set.

   Put `RUNNER_HOME_BASE` where root
   owns every directory from it up to `/`, writable by no one else: whoever owns or can write a
   directory above a runner's home can move the home aside and put another in its place. Setup warns
   when that isn't so (a base under a person's own directory works, but trusts that person).
9. **CODEOWNERS and the `main` ruleset** (D2 rule 6): code owners on `.github/`, `.claude/`,
   `CLAUDE.md` at any depth, `.mcp.json`, `[sdlc-root]/` and the test and build configuration,
   including every file the profile's tools load just because it exists (§ Stack Profiles, What
   CODEOWNERS must cover); code-owner review required on `main`.
   - **A team of people approves every file on `main`** (D2 rule 6): in the `main` ruleset's
     pull-request rule, required reviewers of a team only people CD trusts as reviewers are on (CD's own,
     with write access to the repository), file pattern `*`, one approval. Without it, an App's approval
     merges a PR CD opens. `bootstrap.py` reports it, and reports anything but `*` or any `!` line as
     missing: `*` is the pattern proven to cover every path, dot-directories at any depth included.
     Branch protection has no equivalent, so it must be a ruleset.
   - **Every bypass of `main`'s rulesets in pull-request mode** (CD, 2026-11-12, for every project the
     factory runs in): a bypass then only merges a PR, and is recorded. Always (a missing mode is always)
     and exempt let the actor push to `main` with no PR, every rule skipped. So nothing reaches `main`
     but a PR, CD's own changes included. `bootstrap.py` reports any other mode. A tag ruleset (release
     tags, which are pushed, not merged) is outside this.
   - **The same review on every project's `main`** (CD, 2026-11-12): one approving review, which a
     push dismisses (dismiss stale approvals on push); no last-push approval; and merge commits only,
     in the repository's settings and the ruleset's allowed merge methods. Without the dismissal, a push
     after CD approves keeps the approval, so an App could merge commits CD never saw. With it, every
     push needs a fresh approval already, and last-push approval would only stop CD approving a PR CD
     last pushed to, an App's included. Merge commits keep a PR's commits, and who made each, as they
     were reviewed: a PR that should be one commit is squashed in the session that drives it, before
     review. A ruleset's linear-history rule refuses merge commits, so it goes. `bootstrap.py` reports
     each.
   - **What other agents and tools load on CD's machine:** `AGENTS.md`, `GEMINI.md`, `.codex/`,
     `.gemini/`, `.cursor/`, `.vscode/` (its tasks can run when the folder opens), `.devcontainer/`,
     `.envrc`, `.gitattributes` (`linguist-generated` collapses a file's diff in review),
     `mise.toml` and `.tool-versions`.
   - **Owner-less lines, after the owned ones,** for what agents may write: the discipline parking
     lots (`[sdlc-root]/disciplines/*.md`), every knowledge YAML (`[sdlc-root]/knowledge/**/*.yaml`)
     and the SDLC changelog.
   - **Then owned again, after the owner-less lines** (the last matching line wins):
     - the eight knowledge files that route agents or govern how they work, talk, are tiered,
       prompted and budgeted, and how their work is security-reviewed: `agent-context-map.yaml`,
       and in `architecture/`, `agent-communication-protocol`, `agent-orchestration-patterns`,
       `knowledge-management-methodology`, `model-tier-strategy`, `prompt-engineering-patterns`,
       `token-economics` and `security-review-taxonomy`. The guard keeps the list
       (`implement_guard.GOVERNING_KNOWLEDGE`) and refuses them by name too;
     - `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md` and `GEMINI.md`. Otherwise the parking lots' line unowns a
       nested `[sdlc-root]/disciplines/CLAUDE.md` on GitHub, which Claude Code loads.
   - **Every casing a tool loads, listed explicitly,** early and again after the owner-less lines:
     `CLAUDE.md`, `claude.md` and `Claude.md`, the same for `CLAUDE.local.md` and `AGENTS.md`, and any
     your own tools accept. GitHub matches CODEOWNERS case-sensitively, so an unlisted casing gets no
     code owner on a person's PR. The guard refuses every casing in a factory commit either way.
   - **The other knowledge YAMLs are agent-writable on purpose** (SDLC hygiene, CD 2026-10-09),
     and CD's PR review is the control. Agents can therefore shape knowledge that later agents and
     reviewers read. CD accepted that, organization-wide, so a project doesn't ask again.
   - **The release branch's two rulesets** (D4 rule 13; every project but one on the fallback, with
     `release.branch` empty), which `bootstrap.py` reports and never sets:
     - **The release branch's:** a PR with code-owner review, merge commits only, no force push, no
       deletion, and updates restricted to bypass actors who are organization or repository admins only,
       in pull-request mode. No `exclude` of it may match the branch.
     - **Release gates' pinned branches** (`refs/heads/factory/release/**`): updates, deletion and force
       pushes restricted, creation allowed, and no bypass actor at all.
   - **On the fallback with a production tier, merge commits matter for deploys too.** An execution PR
     merges with a merge commit (D4 rule 13): a squash or rebase leaves production on a commit `main`
     doesn't contain, and the broker refuses the next gate. With a release branch, deploys follow the
     release branch's history instead.
   - The seeded `tests/test_codeowners.py` checks the file against the guard, the governing list
     and the order included, and against GitHub's case-sensitive matching for the agent files' casings
     (`implement_guard.owner_on_github`). Until CODEOWNERS exists it fails. The profile's list it reads
     from the guard (`implement_guard.profile_build_files`), so a release that changes it reaches the test
     on migration: a seed never updates, and a copied list drifted at the first release that changed it.
     Its other path lists are the project's to extend: its test and build configuration, its other
     directories' build files (a second uv project, a second Node app), its source paths. A test
     seeded before the guard kept the lists has its own copy of them (`PROFILE_FILES`, `NODE_FILES`,
     `PACKAGE_MANAGER_FILES`): replace them with `guard.profile_build_files(stack)`.
10. **CI**, required on `main`: `python .github/factory/render.py --check`, then
    `python .github/factory/workflow_policy.py .github/workflows`, then
    `python -m unittest discover -s .github/factory/tests` (with PyYAML; with a CI tier, on a
    GitHub-hosted runner, and `FACTORY_DOCKER_SMOKE=1`, so the tier's job flags are tried on a real
    Docker daemon, which the tests' fakes can't stand in for; the test makes its own image and pulls
    none). The policy reads every
    workflow, the project's own included, and scans the local composite actions they use: run it
    before making it required. A CI job on the organization's own GitHub-hosted (larger) runners
    needs its label in `factory.json`'s `policy.hosted_labels`. A job that must stay on a
    self-hosted runner outside the factory container needs an entry in
    `policy.self_hosted_exemptions` (its workflow, job and reason). An exemption lifts only the
    container rule, the last of the rules below, so its reason says how that runner is isolated
    instead. The other rules below still apply to the job.

    **Dependabot's actions updates** edit `.github/workflows/` only, so a bump of an action a factory
    workflow uses fails `render.py --check` until the templates have it. On the update's PR, run
    `python3 .github/factory/render.py --adopt-pins`: it copies the changed commit pins into the
    templates and refuses any other change, so `--check` passes again and CD still reviews the
    templates under CODEOWNERS (D2 rule 6). A bump of `anthropics/claude-code-action` also moves
    `CLAUDE_CODE_VERSION` in `templates/factory-smoke.yml` to the Claude Code version the action
    installs at its new commit (its `base-action/action.yml`). Run `factory-smoke` once the PR merges
    (D2 rule 5). `sdlc-migrate` then reports those templates as changed by the project, even once a
    release carries the same pins; take the release's copy when it equals the project's or has newer
    pins. After a migration that changes the factory's action pins, run `factory-smoke` too.

    **The project's existing CI runs agent-written code.** Factory branches live in the repository,
    so a factory PR's `pull_request` runs get the repository's secrets. Before the first run, hold
    every job that builds, tests or lints a PR's code to an agent job's rules. `python3 -I
    .github/factory/ci_audit.py --repo <owner>/<repo> --runs 20` reads every workflow against them:
    its triggers and which branch's copy each runs, each job's runners, token and checkouts, every
    secret it references and whether that secret exists (by name), and how often each scheduled
    workflow really ran. It changes nothing, and exits 1 while it has findings:
    - no secret in that job, whether before or after the PR's code runs. A build step can write
      `$GITHUB_ENV` or `$GITHUB_PATH` and redirect every later step;
    - `persist-credentials: false` on its checkout, and a read-only token;
    - a GitHub-hosted runner, or a self-hosted one only inside a container, as the factory's own
      jobs are: the CI tier below.

    A job that needs a secret (a fixture fetch) runs the default branch's code, as the fixtures job
    does (D2 rule 7).

    **Preview deploys run agent-written code too.** A host that builds a preview of every pushed
    branch (Vercel, Netlify, Cloudflare Pages, Railway's PR environments) builds `factory/**` with
    its preview variables. Turn previews off for those branches (on Vercel,
    `git.deploymentEnabled` set false for `factory/**`), or keep every secret out of the preview
    environment.

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
         (a reboot, a trip) cleans up first, and a registration it couldn't remove is
         removed by its next cycle: the slot keeps it in `/var/lib/factory-runner/<unit>`, which
         outlives a reboot. The runner's name is kept there before GitHub is asked for it, so a
         registration made while the slot stopped, whose ID the cycle never heard, is found by its
         name and removed too; a name GitHub refused (a 4xx but 409) isn't kept. A 404 on a
         registration left over, or during setup's `retire`, counts as gone only once the
         organization's runner list has answered: GitHub answers 404 for an organization the App
         can't see, too.

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
      for the base image's and packages' updates. Earlier job images are removed only once the
      check (below) has passed on the new one. Lowering `CI_RUNNERS` disables the slots above it:
      one running a job keeps it, and stops when its job ends. At the start of each of its
      cycles, slot 1 removes any registration such a slot left behind, except one GitHub calls busy,
      and leaves the slot alone while its own process still runs.
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

      The check fingerprints the table as `nft -j` lists it, and an `nftables` upgrade can list
      the same table differently. That trips the tier like a changed table does: fail-safe, but it
      looks like tampering. After upgrading `nftables`, check the table
      (`sudo nft list table inet factory_ci`, or `factory_ci_<instance>` for a host's second
      organization), then run setup again, which records the new
      fingerprint.
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
    - **GPU (`CI_JOB_GPUS`, optional).** For a CI-only host with an NVIDIA card, whose browser suites
      render WebGL: one CDI device name per slot (an index like `0`, or a UUID from `nvidia-smi -L`,
      never `all`), at least as many as `CI_RUNNERS`. Empty, the default, changes nothing: no flag, no
      layer, the same job image. Setup refuses without the NVIDIA driver, the container toolkit and its
      CDI spec (`nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`, root's to write, which setup
      never installs), and a slot's job sees exactly one GPU: setup's isolation test compares the
      UUIDs the slots report. A layer on the job image adds the EGL/GL/Vulkan libraries Chromium
      needs; without them it falls back to SwiftShader without a word. The project's Playwright
      config still has to ask for the GPU (`--use-gl=angle --use-angle=gl-egl
      --ignore-gpu-blocklist`). A pull request's code can use the GPU, so the host should do nothing
      else. Measured on a mobile-class card: the GPU shortens a browser suite and needs fewer CPUs
      per job, and it exposed test races software rendering hid; a second, integrated GPU gave no
      gain from running more jobs at once.
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

    A renamed group is one drift, a rename (its ID is the same), with its settings compared with what
    it had. An answer from GitHub that isn't what it documents is a run that can't read (exit 2), never
    drift. Anything different, or a run that can't read all of it or runs out of time, fails the run and
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
       regenerate it the same way, and after a release that changes `runner_audit.py`, since the
       workflow carries its own copy of the script. The schedule is hourly; `--cron` tightens it. GitHub starts scheduled
       runs late or not at all (an hourly schedule was measured starting in about one slot in five,
       with gaps of up to eleven hours), so a quiet audit is no all-clear: pair it with an outside
       heartbeat that alarms when runs stop, with its grace sized from measured gaps.
13. **Sessions' identity** (CD, 2026-11-12, for every project the factory runs in): a Claude Code
    session CD starts in a clone of the product's repository works as the sessions App, so what it
    writes is the App's, and CD reviews and approves it like any PR. Infra and setup stay CD's own
    login. What's which:
    - **The App's: the product's code.** The session's git commits, pushes and `gh` calls go out as
      the App's bot, with a token for that one repository that lasts an hour, narrowed to contents,
      pull requests and issues (write) and Actions, checks and statuses (read), whatever else the App
      holds. Its commits aren't signed: CD's key would sign them otherwise.
    - **CD's own login: infra and setup.** A change to a path CODEOWNERS gives an owner (step 9's
      list: `.github/`, `.claude/`, `CLAUDE.md`, `[sdlc-root]/`'s owned files, the test and build
      configuration), and anything outside the repository's files: settings, rulesets, secrets,
      environments, Apps, hosts. The session makes those in a branch and PR of their own and runs each
      `git` or `gh` command for them through `session_identity.py as-owner -- <command>`. GitHub refuses
      the App a push that changes `.github/workflows/` anyway. CD can't approve a PR CD opened, so CD
      merges those with the bypass (step 9).

    `session_identity.py`'s SessionStart hook does it, from CD's own Claude Code settings, never a
    project's: a project's settings would also load in the factory's runner jobs. It puts the App's
    identity in the session's environment (`CLAUDE_ENV_FILE`: `GH_TOKEN`, the commit author, and git's
    credential helper, HTTPS for SSH remotes and signing off, as `GIT_CONFIG_*`), never in the clone's
    git config, so CD's own terminal in the same clone is CD's. It tells the session which identity is
    which. A session in any other repository is CD's, as before. When the App's token can't be had, the
    session's GitHub and git commands fail rather than use CD's login, and the session is told why.
    An identity of its own shows who acted, but contains nothing: the session can still reach CD's
    login (its keychain, its SSH keys, `as-owner`). Setup, once per organization and once per project:
    1. **Once per organization:** `create_app.py <org> --sessions` creates the App with exactly those
       permissions; its key stays on CD's machine (`~/.config/agent-sessions/<org>.pem`, mode 600).
       It's `<org>-agent-sessions` unless `--name` says otherwise (App names are unique across
       GitHub). In its settings, give it a one-line description of whose sessions it is and a logo
       that pairs with the factory App's: they're what a reviewer sees on every PR it opens. Renaming it
       changes the bot's login, not its ID, key or installation, so run step 3's `install` again with
       the same repositories, or new sessions keep committing under the old name. Commits made under
       the old name still show as the bot, since GitHub matches its address by the ID.
    2. **Install it on the product's repositories only** (Only select repositories): never one that
       holds infra or setup, such as the runner host's or the runner audit's (step 12: no App that can
       write contents or issues may be installed there).
    3. **On CD's machine:** `session_identity.py install <org> --client-id <id> --key <key> --repo
       <repository>`, naming every repository whose sessions work as the App, this project's
       included. It copies itself to `~/.config/agent-sessions/`, records the App there, and adds the
       hook to Claude Code's user settings once. New sessions pick it up; `session_identity.py status
       <a clone>` says which identity a session there gets.
14. **The browser route** (optional, D6), for a project with a web app and Playwright. Once per organization, a
    browser host: a machine with a GPU, set up from the organization's own reviewed host repository so that it
    holds every property of D6 rule 3, with a front end for each Playwright version its projects use and a
    self-check reporting to a dead-man's switch. Its network's access policy lets only the runner host reach the
    front-end ports. Then:
    1. **The runner host:** set `STRICT_BROWSER_HOST` (and `STRICT_BROWSER_PORTS`, if not 3100–3199) in the shared
       tiers' `host.conf`, and re-run the strict tier's setup. Its isolation test probes the browser host's other
       ports.
    2. **The project:** before a stage uses the browser, the project's verify skill lists its outside connections
       (D6 rule 6), fixtures cover its static files, it has a test sign-in that works offline, and a code-owned
       script prepares what its end-to-end servers need. Set `factory.json`'s `browser.host` to the same address,
       with `browser.client` if its Playwright isn't installed in `stack.node`. Leave `browser.stages` empty.
    3. **Smoke:** merge step 2's settings (`browser.host`, `browser.allow` and the rest), then run `factory-smoke`.
       Its `browser-host` job must pass (D6 rule 4). Every smoke job checks out the default branch on purpose (a
       branch could otherwise change what proves the boundary), so a branch's browser settings can't be smoked
       before they merge.
    4. **The stages:** list them in `browser.stages` (implement, execute, revise, and `reproduce` for the step before
       planning, D6 rule 8), through a second PR, after smoke passed on step 2's merge. So enabling the route
       takes two PRs, the settings and then the stages (D6, Forbids 2). Smoke a later change to the browser
       settings (an allowed host, its probe path) as soon as it merges. An implement run asks for the route as `execute` when it's given a
       plan and as `implement` when it isn't, so list both, or a plan-driven run gets no browser; `bootstrap.py`
       reports one listed without the other.
    5. **The archive** (optional, D6 rule 7): on the host that keeps it, with storage already in place,
       `sudo bash .github/factory/host/setup-archive.sh <root> <owner/repository> ...` from the shared tiers'
       repository, then set each project's `factory.json` `evidence.archive` to `<root>`.

---

## After migrating

What a release of the bundle can make due. `sdlc-migrate` follows this after it copies the bundle's files and
renders (`[sdlc-root]/process/runbooks.md` § After migrating), and puts each item that applies in the migration
report. The items name CD's steps; the migration does none of them. Compare the bundle's files at the
project's previous version with the release's.

- **The operations digest:** `gates.py`, `ed25519.py` or a broker file changed → a project with a production tier
  re-runs that tier's setup on its host before the next gate, or every gate is refused (D4 rule 6). CD's root
  step.
- **Action pins:** the templates' action pins changed → run `factory-smoke` once the migration's PR merges
  (D2 rule 5).
- **The runner's version:** `host/setup.sh`'s `RUNNER_VERSION` changed → re-run each runner tier's setup within
  30 days: GitHub stops sending jobs to a runner more than 30 days behind its latest release. The shared host's
  own repository copies the bundle's `host/` at the release's tag first (Enablement step 8).
- **The CI tier:** `host/ci_launcher.py`, `host/setup-ci.sh` or the CI tier's image changed → re-run the CI
  tier's setup (`TIER=ci`).
- **A seed change:** the release's changelog entry names a seed change (a setting, a test's list, a review rule)
  → the migration doesn't apply it, since seeds are the project's: list it for CD, with what to copy.
- **The runner audit:** a template's runner labels or groups changed → regenerate the audit's expected state
  (Enablement step 12).
- **Labels, environments and checks:** `bootstrap.py` changed → once the migration's PR merges, run
  `python3 .github/factory/bootstrap.py`, and with `--apply` when it reports a label or environment missing: a
  release's new label (`factory:needs-repro`, say) doesn't exist until then, and the step that adds it fails
  (Enablement step 6). A problem it reports in the repository (a missing root `package.json`, say) is fixed
  through a PR. CD's step, with an organization owner's `gh` login.
- **What CODEOWNERS must cover:** `implement_guard.py`'s build-file lists changed → the project's seeded test
  of its CODEOWNERS (`.github/factory/tests/test_codeowners.py`) checks the new names, and fails until
  CODEOWNERS covers them (§ Stack Profiles, What CODEOWNERS must cover). Run it; a name it reports goes into
  CODEOWNERS through a PR. A test that keeps its own copied lists instead of reading `profile_build_files`
  (one written before the seed, as the incubator's was) checks none of the new names: compare CODEOWNERS with
  that list by hand.
- **The filmed pass:** `evidence_film.mjs` is new or changed → the project's evidence helper loads it in the filmed pass
  (D6 rule 7): `filmContext` on the recorded context, `caption` at each step, a `gesture` for its specs to wrap the
  bug's moves and presses in, and the video's `shows` ending with `paceClaim(page)` for the recorded page (the rest
  shortened by its length to fit 300 characters). A helper that worked the suffix out itself (from `paceCounts`, or
  from whether it filmed) moves to `paceClaim`, and one that types the module adds it. A helper that appends
  `paceClaim` as given needs nothing when its words change; one that accepts only the words it knows, so it can't
  claim more than the module checked, adds the new ones. A spec's gestures use only `page.mouse` and `page.keyboard`, with
  moves in steps of at most 40 px and presses where a move ended, and the pointer placed with `page.mouse` before each
  gesture: a locator action, a jump or an unplaced start inside one keeps its video from saying it was filmed at a
  person's pace. Check each gesture's step lengths when the module changes. The module counts text in code points,
  as `evidence.py` does. It may be loaded in a fixture that hands it to the helper. The helper also
  empties `.factory/evidence/` when each invocation starts; `with-browser` keeps the proof's folder for the filmed
  pass itself, so that needs nothing from the project. The helper is the project's code, so the migration lists
  this for CD; until the helper loads the module the stages run no filmed pass. Smoke's `browser-host` job checks
  the overlay itself.
- **The browser route:** `browser.py`, `with-browser`, `browser_probe.mjs` or `browser_check.py` changed → a
  project with `browser.host` set runs `factory-smoke` once the migration's PR merges, and its `browser-host`
  job must pass before its stages keep the route (D6 rule 4). `host/setup.sh`'s browser opening changed → re-run
  the strict tier's setup.
- **The evidence archive:** `host/evidence_archive.py` or `host/setup-archive.sh` changed → on the host that keeps
  the archive, re-run `setup-archive.sh` from the shared tiers' repository once it has the release's `host/`: the
  installed puller is a copy, and the migration doesn't reach it (Enablement, the browser route's step 5).

The rest of the factory's upkeep isn't release-triggered (token rotation, a runner more than 30 days behind
without a release, Dependabot's pin updates): `[sdlc-root]/process/factory-runbook.md` § 7.
