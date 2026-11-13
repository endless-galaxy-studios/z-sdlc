# Installing the Software Factory: Runbook

How to take a project from "the bundle is installed" to "a real issue has gone through the factory".
The rules are `[sdlc-root]/process/factory.md` (D1 to D5); its Enablement section's twelve steps are
what must be true. This runbook is the order to do them in, what to ask before starting, how to tell
each step worked, and what to build when the project brings something the factory hasn't seen.

**Read this first.** On the third project, the twelve Enablement steps took about 2.5 hours. The other
80 went to three things the steps don't cover:
- **a stack no profile fit,** built upstream mid-install;
- **credential debt the factory's threat model surfaced:** secrets in git history, a "read-only" route
  that ran as a superuser, a public database without TLS;
- **a production tier,** which the bundle doesn't install (D4 rule 16) and which had to be designed
  for a host unlike the incubator's.

The first two projects needed none of that, because they were alike: one fit each existing profile,
and the incubator's production was a host its broker could deploy to. So before touching anything,
find out which kind of project this is: § 1 and § 2 do that in about an hour.

---

## 0. How the install runs

- **One session owns the project's install,** in the project's own checkout, with the owner (CD)
  present in that session. Migrations of the project run there too, never from another project's
  session or as a pull request opened elsewhere.
- **Framework gaps go upstream.** A fix the project needs in the bundle goes into z-sdlc's bundle code
  and ships as a release, then migrates in. During an install,
  batch those fixes: one release per phase, not one per fix, and never move a tag a project may already
  have fetched. The third project took five migrations in four days; each one cost a review round.
- **Every decision is written down when it's made,** in the project's `.github/factory/README.md` §
  Enablement record (the seed has its skeleton): the question, the answer in CD's words, the date, and
  the session it was made in. A decision another session relays is confirmed in this session before
  anything acts on it. A decision that is later built or dropped gets a line saying which.
- **Every recommendation names its alternatives and what it forecloses.** A recommendation with no
  alternative is a decision taken for CD.
- **Credentials stay out of the agent's sight.** Two forms, and nothing else:
  - **A credential from somewhere else** (a token or key a dashboard issues, a key a person holds): CD
    writes it, at the store's own masked prompt in CD's own terminal (`gh secret set NAME`), never
    through an agent session (a session's shell has no terminal, so there is no masked prompt, and what
    it prints reaches the model). A credential that arrives as a file, such as an App's private key, is
    fed from the file (`gh secret set NAME < key.pem`), kept out of the repository's tree and deleted
    after.
  - **A random secret the factory itself needs** (an HMAC key, a password for a role it creates): the
    agent may generate it in one pipeline that writes it straight into its store (`openssl rand -hex 32 |
    gh secret set NAME`), so it never appears in output, a file the agent reads, or a screenshot.

  In a dashboard, the agent stays off pages that show secret values and never screenshots one. The
  agent may add a public deploy key the moment CD pastes it.
- **Work on a branch of its own,** in a worktree no other session uses, and agree what may be pushed to
  the default branch while the install runs (a push may deploy, or ship workflows).
- **A committed handoff at the end of each phase.** An install runs for days, across many sessions and
  context compactions: what's done, what's next and what's decided goes in the repository, not in a
  session's memory.

---

## 1. The day-one form: ask it all in one sitting

Ask these together, grouped by topic, before any file changes: four at a time, the recommended answer
first, each with its alternatives. Record the answers (§ 0). "Cost to reverse" is how much work a
changed answer undoes later: ask the high ones carefully, once.

| # | Question | Options | Usual answer | Cost to reverse | Who decides |
|---|---|---|---|---|---|
| A1 | How is the install tracked? | An SDLC deliverable; direct dispatch | Direct dispatch, with the Enablement record | Low | CD |
| A2 | What may the agent do without asking? | Everything but credentials and host root; ask per step | Everything but credentials, root and dashboards | Low | CD |
| A3 | Whose GitHub identity do agent sessions use? | The sessions App for the product's code, CD's login for infra and setup (factory.md step 13: no seat; its key on CD's machine mints a token for one repository; CD reviews and approves the App's PRs and merges CD's own with the bypass); CD's login for everything (every agent PR is CD's, so CD merges with the ruleset bypass and can't approve); a second account's fine-grained token (a paid seat; CD reviews and approves). An identity of their own names who acted; it contains nothing while a session can still reach CD's login | The sessions App, with infra and setup on CD's login (CD, 2026-11-12). Whichever is chosen, step 9's team of required reviewers is needed: without it, an App's approval merges CD's own PRs | Medium | CD |
| A4 | Who runs root steps on hosts, and who writes host tokens? | CD; the agent with temporary sudo, removed after | CD writes every token; root steps by CD, or by the agent under temporary sudo CD grants and removes | Low | CD |
| A5 | What may be pushed to the default branch during the install, and when may a push that deploys go out? | Hold; allow; a window | Name what may ship, and the project's deploy windows | Low | CD |
| B1 | Does an existing stack profile fit? (§ 2's stack-fit table answers it) | Existing; a new profile upstream (§ 4.1) | Whatever § 2 shows | Medium once workflows render | Agent proposes, CD confirms |
| B2 | What does a job's `verify` have to pass? | CI's checks; plus integration; plus the migration round trip | CI's checks plus integration, plus the migration round trip if the project migrates | Low | CD |
| B3 | Where do non-secret test settings live? | The project's test setup (conftest, fixtures); CI's environment | The project's test setup: the suite must run with no CI-only variables | Low | CD |
| C1 | Release model (D4 rule 13)? | Release branch (the default); the fallback, execution-PR gates | Release branch, unless production's host can't follow a branch | **High** | CD |
| C2 | Must plans be able to deploy partway through? | Yes: release gates (the broker must take them); no: only at the end, through a Release section | Ask once, write it down, don't revisit | **High** | CD |
| C3 | Production tier? | None (rule 16: no gates, CD merges releases); checks only (the host deploys the release branch; the broker backs up and checks); deploying (the fallback host) | Follows C1 and the host (§ 2) | **High** | CD |
| C4 | Built with the install, or after? | With; after (the factory runs without gates meanwhile) | After, unless the first plans need gates | Low | CD |
| C5 | Which hosts serve production, and do all of them follow the release branch? | Each host listed (§ 2) | All of them, previews of `factory/**` off | Medium | CD |
| C6 | Is the production host's configuration set in its dashboard or in config-as-code files, and does the production tier's first `baseline` wait for a move between them? | Dashboard; config-as-code; a move first | Settle it before the broker's design: a move changes the code owners, the broker's settings check and the baseline, and a platform may have a cutoff date for one form | **High** | CD |
| C7 | If services deploy concurrently from one merge and a contract check is built (§ 4.3), how is a background job retired? | Never through the check; a reviewed exception path | Decide with the check: an add-only check alone makes a dead job undeletable | Medium | CD |
| D1 | How does planning read data (D3)? | None; a database through the planning tier's firewall exception; a read-only MCP service; an env service | The route the host allows; § 4.2 | **High** (a role, a service, a host setting) | CD |
| D2 | Which outside services may planning read, and who mints their read tokens? | Each service | List them; CD mints each token | Low | CD |
| D3 | The planning login's column policy? | Generated list, CD classifies the held columns; deny unknown names by default | Deny by default | Low | CD |
| D4 | Do the execution stages get read-only MCP services (D2 rule 9)? | Context7 only; a reviewed read-only service | Context7 only | Low | CD |
| E1 | Credentials the inventory finds in git history, or reachable through a planning route: rotate, or accept? | Rotate; accept, recorded | Rotate anything a planning route reaches | Medium | CD |
| E2 | The project's code owners (step 9): the standard layout? | The standard (factory files and agent configuration owned; knowledge files agent-writable except the governing ones) | Standard: it is decided org-wide and isn't asked again | Low | Decided |
| E3 | Review rounds per change? | The full roster; sized to risk | Sized to risk: the full roster for production code, host setup and security boundaries | Low | CD |
| E4 | Who watches scheduled alarms, on which service, and in whose account? | An outside heartbeat service; none | An outside heartbeat for every scheduled alarm (§ 4.6); each check is CD's to create and arm | Low | CD |

---

## 2. Inventory: read-only, before any decision

One research agent, about 30 minutes. It answers § 1's B, C and D rows and finds the debt.

1. **Stack fit,** against every profile in factory.md § Stack Profiles: dependency managers and
   lockfiles; runtime versions; how many source directories, and which hold the database and its
   migrations; the database's version and every extension the tests create (a superuser-only one, such
   as pgvector, needs § 4.1's recipe); how the tests get their database and settings; the migration tool
   and a probe command; the lint and type-check commands.
2. **Do the bare tools match CI?** A job runs `pytest`, `mypy`, the linter and so on bare, so their
   paths and options belong in the project's config files (`pyproject.toml`, `package.json`), not in
   CI's command lines. List the moves: those files are code-owned, so CD reviews them.
3. **The project's own guard tests,** for anything they'd refuse in factory files: the toolchain's name,
   another stack's Dockerfile.
4. **A CI audit:** every workflow's triggers, every secret it references and whether that secret
   exists (by name, `gh secret list` at each level), each checkout's `persist-credentials`, and its
   runners. A job that runs agent-written code holds to an agent job's rules (step 10). For each
   scheduled workflow, how often it actually ran (`gh run list --workflow <file> --event schedule`,
   the gaps against its cron): GitHub starts scheduled runs late or not at all, and an alarm designed
   on the nominal period won't hold.
5. **Every host that deploys from git, and from which branch:** platform services, static-site hosts,
   side services such as auth proxies, and their preview deployments.
6. **The production host's profile,** if production runs on a platform: what "deployed" means there;
   whether its health check can say which deployment is serving; whether services restart concurrently
   or in order; what its tokens can do (a read-only API spike); config-as-code deadlines; whether a
   dashboard change redeploys.
7. **Credential reach:** a secret scan of the full git history (planning jobs check out all of it and
   have the internet); for every credential near the repository or a planning route, which database
   role it really runs as (`select current_user, rolsuper from pg_roles where rolname = current_user`);
   TLS on any public database address.
8. **Shared-tree hazards:** other sessions committing to the default branch, unpushed commits, what a
   push deploys.
9. **An architecture map:** one picture of this project against the factory's reference project,
   before asking CD anything.

The result is one table per area: what the project has, the profile or route it maps to, and the
"New" items § 4 will build. Then ask § 1.

---

## 3. The critical path

Each step names the Enablement step it does, and the check that shows it's done. Steps marked **[CD]**
are CD's; batch them into the three sittings, since each one is an interruption: secrets and GitHub
settings, hosts, and dashboards. Where the organization already has a piece (the App, the job image
for this profile, the echo service, the runner host and its repository, the runner audit), copy its
values from the organization's own records instead of creating it.

### 3.1 Upstream first, only for "New"

A new profile, a new attach mode, new rule text: build it in z-sdlc, release it, migrate it in (§ 0's
batching). Check: the migration's tests pass in the project, and `render.py --check` is clean.

### 3.2 Repo settings (the agent; CD reviews)

- **Step 2, `factory.json`:**
  - `stack`: profile, directories, `env_file`, `database`, which must be the name the tests bootstrap
    from;
  - `image.repository`: one package per profile (`factory-image` pushes `:latest`, so two profiles
    sharing a package overwrite each other);
  - `smoke.echo_host`;
  - `smoke.host_probes`: the runner host's own addresses only, never another project's database
    exception;
  - `release.branch` (§ 1 C1);
  - `review.focus` rules for this stack (§ Where to look).
- **`.gitignore`:** the env file, `.factory/`, `.github/factory/host/reg-token`.
- **A self-sufficient test suite:** fixed non-secret test values in the project's test setup (§ 1 B3).
- **`triage-policy.md`.**
- **CODEOWNERS (step 9):** the standard ordering, every casing a tool accepts, the profile's list (§
  Stack Profiles), plus every file that decides what deploys: the host's config-as-code, migrations'
  environment files, infrastructure-as-code and `.sdlc-manifest.json`. The seeded CODEOWNERS tests pass.
- **CI (step 10):** the audit's findings fixed, the factory checks job added, one aggregate check
  required.

**Check:** `python3 .github/factory/render.py --check` is clean,
`python3 .github/factory/workflow_policy.py .github/workflows` reports 0 violations, and
`python3 -m unittest discover -s .github/factory/tests` passes.

### 3.3 Sitting 1: GitHub and secrets [CD, the agent driving]

1. **[CD]** Give the agent's `gh` the scopes the checks need (`gh auth refresh -s
   read:packages,write:packages,admin:org`).
2. **Step 3, the image:** run `factory-image`. A first publish can fail on the tag push with `denied`:
   re-run it once. Pin the printed digest in `image.digest`, render, commit. For an existing profile's
   package, grant this repository read access instead.
3. **Step 6:** `python3 .github/factory/bootstrap.py --apply`, with an organization owner's login.
4. **Step 7, [CD] secrets:** the App's key and client ID, `CLAUDE_CODE_OAUTH_TOKEN` (`claude
   setup-token`, in CD's own terminal), and the planning secrets. A new App key for an existing App is
   generated in its settings page and fed from the file.
5. **Step 12, the runner audit,** if the organization has one: the agent regenerates the expected
   state; **[CD]** commits it, since agents don't commit there. A new project's workflows are drift
   until then. With § 1 A3 answered "CD's login", CD can't approve that PR either, and merges it with
   the ruleset bypass.
6. **Step 9, the rulesets:** the default branch's (code-owner review, a team of people as required
   reviewers of every file, one approving review, stale approvals dismissed on push, no last-push
   approval, merge commits only in the ruleset and the repository's settings and so no linear-history
   rule, the aggregate check, bypass mode `pull_request`: every factory project's the same, CD
   2026-11-12), the release branch's (merge
   commits only, which provenance reads), and the pinned branches' (`factory/release/**`, no bypass
   actor at all). Of the project's branches, restricted updates belong
   on the release branch and the pinned branches only. On its default branch they let only bypass
   actors merge, so every merge there, approved and green, needs the bypass. (The runner host's
   repository keeps them on its default branch, factory.md step 8: a merge there is root on the host.)
   Prove a bypass mode on a scratch branch before trusting it: mode "always" skips every rule.
   The team holds only people CD trusts as reviewers (CD alone, usually) and has write access to the
   repository; the rule's file pattern is `*`, with one approval. Code-owner review alone lets an App
   approve and merge a PR CD opened, because GitHub asks no code-owner review of a PR whose author is
   the only code owner of what it changes (D2 rule 6).
   A CODEOWNERS file must exist for code-owner review to ask anything: a repository without one (a
   small one of the organization's own, such as the runner audit's) gets `* @<CD>`.
7. **Environments before the workflows that name them:** a run naming an environment that doesn't
   exist creates it unprotected. `bootstrap.py --apply` creates the factory's own environments,
   deployable from the default branch only, and reports one that already exists without that policy,
   which is then CD's to fix. Any other environment the project adds (an alarm's, say) is created with
   its branch policy before the workflow that names it lands: a custom policy naming the default
   branch only, since "protected branches" also admits a ruleset-protected release branch.
8. **Step 13, sessions' identity,** with § 1 A3's usual answer: **[CD]** adds the repository to the
   sessions App's installation (selected repositories), then runs `session_identity.py install` on
   CD's machine with every repository whose sessions work as the App, this one included. Check with
   `session_identity.py status <the clone>`, then in a new session: its first commit is the App's bot's
   and unsigned, and `gh api user` fails (an App's token has no user).

**Check:** `bootstrap.py` (read-only) reports nothing missing, and the audit's next run passes.

### 3.4 Planning data, if § 1 D1 chose a route

See § 4.2. **Check:** `planning-services.sh`'s reader check refuses nothing when run as the planning
role, through the real route; an MCP token bound to the reader's connection fails against any other.

### 3.5 Smoke, then one real issue

1. **Step 11:** `factory-smoke`. Every job passes; `mcp-services` runs when `services.json` lists an
   MCP service.
2. **One trivial real issue** through triage, plan, implement and the PR. Smoke proves the plumbing,
   not `verify` on the project's code, nor planning's data access.

### 3.6 Sitting 2: hosts [CD]

- **The shared runner tiers** (step 8) belong to the shared host's own repository, never a project's.
  Usually nothing to run for a new project. When a run is due (a runner version bump, a host setting),
  by a login no agent session uses:

  ```bash
  gh repo clone <organization>/<host repository> && cd <host repository>
  sudo TIER=<tier> bash .github/factory/host/setup.sh
  ```

  The first run for a repository prints a deploy key and stops: the agent adds it read-only once CD
  pastes it, then CD runs setup again. Look at every tier's state while there, the CI tier's
  included.
- **The production tier,** if § 1 C3 chose one (§ 4.3):
  - a host preflight: the SSH login name, `openssl version` (OpenSSL 3, which receipt signing needs),
    `nft --version`, free disk, and any other tier's `check` before and after;
  - a fresh copy of the default branch on the host (`git archive` over SSH when the host has no
    GitHub credential);
  - setup's two runs, with the deploy key;
  - **[CD]** creates the host token and writes it (`read -s`, root-only); the agent never sees it;
  - `verify-token`, then `check`.

  Re-run setup after any change to a file in the operations digest (`gates.py`, `ed25519.py`, the
  broker, `ops.json`).

**Check:** the runner shows online in its own group; `check` returns ok.

### 3.7 Sitting 3: dashboards [CD, with the browser connected and signed in]

Batch every dashboard-only change into one sitting:
- every host that serves production follows the release branch (a platform service's trigger, a
  static-site project's production branch, a side service's source branch), with auto-deploy off where
  a service is deployed by hand;
- previews of `factory/**` off: a preview builds agent code with the preview's variables;
- failure notifications on;
- a staged change found on the way is reported, never deployed unasked.

**Check:** for each host, the latest production deployment's commit is on the release branch, not
only the default branch.

### 3.8 Close: the definition of done

- **The first release:** a PR from the default branch into the release branch, merged by CD, and each
  host serving it.
- **A production tier's first `baseline`,** and its drills before the first real release: a restore,
  a rollback, a fix-forward, a hung pre-deploy step. The rollback drill also proves the revert's path:
  a revert PR can fail a required check (a contract check, for one), and whether a ruleset's
  pull-request bypass covers a failing required check is to be shown in the drill, not assumed. The
  fallback is removing the check from the ruleset for that one merge, then restoring it.
- **Every scheduled alarm has an outside heartbeat** (§ 4.6).
- **The Enablement record** says done, deferred, or dropped for every decision; the organization's
  records are updated in the same work.
- **One real issue has gone through** (§ 3.5).

---

## 4. When no template exists

### 4.1 A new stack profile

1. Start from a copy of the nearest profile (§ Stack Profiles), keeping its security properties.
2. The six files. The profile also publishes its **environment contract:** the variables
   `test-services.sh` prints for the env file, and the ones `with-test-services` exports. A settings
   loader that refuses unknown keys takes only the keys it knows.
3. **Directories:** discover lockfile directories rather than hard-coding two, with `stack.python` (or
   its equivalent) naming the one that holds the database.
4. **Extensions the tests create:** a superuser-only extension is pre-installed in `template1`, in a
   schema of its own that the tests' teardown doesn't drop, with `USAGE` granted to `PUBLIC` and the
   test role's `search_path` including it.
5. **Prove it on the project's real setup and teardown sequence,** not only a probe. Note the
   production database's major version beside the profile's.
6. Its CODEOWNERS list (§ Stack Profiles) and the tests for it.
7. Release, migrate, publish its image to a package of its own, pin the digest, render, run smoke.

### 4.2 A new planning data route

- **Pick the route the host allows.** A database on a private address takes the planning tier's
  firewall exception (D3 rule 2). A database on a public address needs TLS, which `planning-services.sh`
  requires. A database only a service can reach takes a read-only MCP service (`services.json`,
  `attach: mcp`). An outside API takes an env service.
- **The login is read-only by its privileges** (D3 rule 3), whatever the route: a service's own
  read-only mode is no boundary. Generate the column list from the schema, deny any column not on an
  allow rule (an unknown short text column or a name ending `_id` is not safe by default), and have CD
  classify the held ones. Revoke the large-object write functions and `TEMPORARY` from `PUBLIC`, and
  set the role's `temp_file_limit` and timeouts.
- **Verify as the role it really runs as,** through the real route: `current_user` and `rolsuper`, then
  `planning-services.sh`'s check.
- **An MCP service:** bind its token to the reader's connection and prove it fails switching to any
  other; list its tools (D2 rule 9); put the credential in the Authorization header only (D2 rule 10);
  check that the host's CDN or WAF lets the client's requests through.

### 4.3 A production tier for a new kind of host

1. **The host profile and a read-only API spike** (§ 2 item 6), before any design.
2. **The model** follows from it: a host that deploys a branch makes a checks-only broker (the release
   branch is the deploy); a host that can't makes a deploying one (the fallback), or, once built, one
   that follows the branch (D4 rule 13).
3. **The broker's shape:** start from an existing broker's design, not its code, since the host API
   is most of it. Every broker keeps the rule 7 check (provenance on a release branch), signed receipts,
   the ledger, sandboxed steps, an instance suffix on every name when a host runs several tiers, and a
   per-user request client.
4. **The catalog** (`production/ops.json`): typed read operations, and backups; `release_gates: true`
   only once the broker runs a release gate's gate run.
5. **Health that names the deployment** (rule 15): the serving deployment's id on health and a
   heartbeat. If services deploy concurrently from one merge, a newer process can meet an older schema
   or job contract: give it a startup wait and keep contracts add-only for one release. A CI check of
   the contracts compares a PR with the release branch's tip, so while production holds a change the
   default branch lacks (after a release gate), every PR fails it until the default branch catches up:
   a known false failure. Such a check covers the consuming side only; the producing side (never enqueue
   a job before the release that accepts it is live) stays review unless a check makes every new job
   take two releases. Ask § 1 C7 with it.
6. **Setup:** the root-owned fetch with a per-repository deploy key, firewall rules checked by the
   real tool (`nft -c`) in its tests, acceptance checks.
7. **Drills** (§ 3.8) before the first real release.

### 4.4 A new host that serves production

It follows the release branch by its own branch setting; nothing else deploys it to production. Its
previews of `factory/**` are off. List it in the Enablement record, and in the release branch's
"every host" check (§ 3.7).

### 4.5 The first project in an organization

Before § 3, the organization's own pieces: an organization on Team or above (step 1); the App
(`create_app.py`, step 5); the echo service (step 4); the shared runner host and its own repository
(step 8); the runner audit and its App (step 12); the job image's package for the profile (step 3);
the sessions App (`create_app.py --sessions`, step 13), installed on selected repositories only.
Record each one's values where the next project's install will look.


### 4.6 A scheduled alarm or check

- **Pair it with an outside heartbeat** that alarms when its runs stop. GitHub starts scheduled runs
  late or not at all, so size the heartbeat's grace from the workflow's measured gaps, and recalibrate
  from the heartbeat's own log after a week: a quiet repository's schedule runs less often than a busy
  one's.
- **Prefer an event that runs the default branch's copy of the workflow:** `status` and `workflow_run`
  do. `push` and `deployment_status` run the pushed or deployed commit's copy, and
  `pull_request_target` the base branch's, which on a release branch is whoever pushed there.
- **The heartbeat's secret** goes in an environment whose custom branch policy names the default
  branch only (§ 3.3 item 7). A job with `deployment: false` is still held to that policy, as the third
  project's experiment showed.
- **Accept a heartbeat ping only on its success body** (for healthchecks.io, exactly `OK`): a deleted
  check can still answer `200`.
- **Who hears a failure:** a failed scheduled run emails whoever last edited its cron line, so an edit
  by someone else moves the alarm's recipient.
- **Don't let comments quiet an issue-based alarm:** any branch's workflow can comment as
  `github-actions[bot]`, so throttling or deduplication that trusts its comments can be forged.
---

## 5. Pitfalls

| Pitfall | What to do | Where it's handled |
|---|---|---|
| A stack no profile fits | § 4.1, upstream first | This runbook |
| Two profiles sharing an image package overwrite each other's `:latest` | One package per profile | § 3.2 |
| Bare tools don't match CI's options | Move paths and options into the config files | § 2 item 2 |
| A superuser-only test extension, dropped by the tests' teardown | The extensions-schema recipe | § 4.1 |
| Tests that only pass with CI's environment | Fixed values in test setup | § 1 B3 |
| CODEOWNERS on a case-insensitive checkout | Every casing; the guard matches any case | factory.md step 9 |
| A first image publish `denied` | Re-run once | factory.md step 3 |
| A workflow naming a missing environment creates it unprotected | Environments first | § 3.3 |
| Ruleset bypass mode "always" skips every rule | `pull_request` mode, proven on a scratch branch | § 3.3; `bootstrap.py` checks the default and release branches |
| Restricted updates on the project's default branch: every merge, approved and green, needs the bypass | Restricted updates on the release branch and the pinned branches only | § 3.3 |
| An App's approval merging a PR CD opened, recorded as a pass: code-owner review isn't asked of a PR whose author is the only code owner of what it changes | A team of people as required reviewers of every file on the default branch | § 3.3; `bootstrap.py` checks it |
| Last-push approval: CD's push to an App's PR stops CD approving it, so it needs the bypass | Off; stale approvals dismissed on push make every push need a fresh approval | § 3.3; `bootstrap.py` checks both |
| Merge commits only, with a linear-history rule: no PR can merge | Drop the linear-history rule; allow merge commits in the repository's settings too | § 3.3 |
| Code-owner review required, but no CODEOWNERS file: it asks nothing | `* @<CD>` in a repository with no owners of its own | § 3.3 |
| An App installed on all of the organization's repositories (a sessions App, a coding assistant's) can write the infra repositories and the runner audit's | Selected repositories: the product's only | step 12; step 13 |
| A session working as an App signs its commits with CD's key, and GitHub shows them unverified | `session_identity.py` turns signing off for the App's commits | step 13 |
| A renamed sessions App: new sessions still commit under its old login | Run `session_identity.py install` again with the same repositories | step 13 |
| Squash or rebase merges where provenance is checked | Merge commits only | D4 rule 13 |
| A service's "read-only" mode running as a superuser | Verify as the role | § 4.2; D3 rule 3 |
| A public database without TLS | TLS, or another route | § 4.2; `planning-services.sh` |
| Credentials in git history, reachable by planning | Scan and decide | § 2 item 7; § 1 E1 |
| A host still deploying the default branch | Every host on the release branch | § 3.7 |
| Previews building agent code with real variables | Previews of `factory/**` off | factory.md step 10 |
| A host's health that can't say which deployment serves | A deployment id on health | § 4.3; D4 rule 15 |
| Services deployed concurrently meeting an older schema | A startup wait; add-only contracts | § 4.3 |
| A dashboard change that redeploys, or re-enables auto-deploy | Report, read back, never deploy unasked | § 3.7 |
| A shared runner tier owned by a project | The shared host's own repository | factory.md step 8 |
| Setup's first run printing a deploy key and stopping | Add the key, run again | § 3.6 |
| Firewall rules the host's `nft` refuses | Test with `nft -c` | § 4.3 |
| Scheduled alarms that don't run on schedule | An outside heartbeat | § 3.8 |
| A decision relayed between sessions, or reversed, or never built | The Enablement record | § 0 |
| Release churn mid-install | Batch fixes; never move a tag | § 0 |
| A long install losing state across context compactions | A committed handoff at each phase's end | § 0 |
| A revert PR failing a required check during a rollback | Prove the bypass in the rollback drill | § 3.8 |
| An alarm designed on its cron's nominal period | Measure the runs; an outside heartbeat | § 2 item 4; § 4.6 |

---

## 6. What varies between projects

The first two projects shared a shape on every row below. When a project brings a new value, the
right-hand column says what to do.

| Dimension | The first two projects | What the third brought | The rule now | A new value means |
|---|---|---|---|---|
| Toolchain and layout | One Python or .NET directory and one Node directory; pip and npm, or dotnet and pnpm | uv with several projects, pnpm, alembic | Profiles discover lockfile directories | § 4.1 |
| Test services | Postgres without extensions; Django-style settings | Postgres 17 with pgvector; settings read from the process environment | A profile publishes its environment contract and the extensions recipe | § 4.1 |
| Planning data route | A private database through a firewall exception | A managed database reachable only through an MCP service | The route the host allows; the role is the boundary | § 4.2 |
| Production host | One the broker deploys to | A platform that deploys a branch itself | The release branch is the model; the host decides the broker's shape | § 4.3 |
| Hosts per project | One | A platform plus static-site hosts | Every host follows the release branch | § 4.4 |
| Who presses deploy | The broker, in a gate | CD's merge into the release branch | D4 rule 13 | § 1 C1 |
| Mid-plan deploys | Deploy gates | Release gates, which the broker declares | D4 rule 13; `release_gates` | § 1 C2 |
| Production tiers per host | One | A second tier on the same host | Instance-suffixed names, a per-user client | § 4.3 |
| Shared runner host's owner | The incubator's checkout | A repository of its own | factory.md step 8 | — |
| Ruleset bypass | "Always", harmless while the broker deployed | `pull_request` mode, merge commits only | factory.md step 9 | § 3.3 |
| Review rules (`review.focus`) | Django, ASP.NET Core | FastAPI and SQLAlchemy | Per-stack rule packs | § 3.2 |
| Pre-existing credentials | Purpose-made logins | A superuser-backed route, secrets in history, no TLS | Audit credential reach first | § 2 item 7 |
| Scheduled checks | Assumed to run on time | Measured: most hourly slots never ran | An outside heartbeat | § 3.8 |
| What "copy work" covers | Almost everything | 2.5 of about 83 hours | § 2 finds the rest first | § 2 |

---

## 7. Keeping it working

- **Runner versions:** GitHub stops sending jobs to a runner more than 30 days behind its latest
  release. A z-sdlc release bumps `setup.sh`'s `RUNNER_VERSION`; re-run each tier's setup after it,
  well inside the 30 days.
- **Digest files:** a production host re-runs its setup after any change to `gates.py`, `ed25519.py`,
  the broker or `ops.json`, or every gate is refused.
- **The runner audit** is regenerated after any intended change to runner groups or their runners, a
  new project's workflows included.
- **Dependabot's actions updates:** on each PR, `render.py --adopt-pins`, `CLAUDE_CODE_VERSION`
  moved with the agent action, and `factory-smoke` after the merge (factory.md step 10).
- **Tokens** a production tier holds are rotated on a schedule CD sets, and at once on any suspicion.
- **Migrations** run in the project's own session (§ 0), one release at a time.
