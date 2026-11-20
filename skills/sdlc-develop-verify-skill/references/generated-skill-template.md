# Generated Skill Template

The `SKILL.md` that `sdlc-develop-verify-skill` writes at `.claude/skills/verify/` (CREATE step 3). Fill every brace with what the repo actually has. A section with nothing real to say says why (for example, "no sign-in: the app has no accounts"), never a placeholder.

The reader is an agent that opens this file cold, mid-task, and has never seen the app. Give it exact commands and the signal that each one worked.

Commands run in the agent's shell, which is zsh on macOS and usually bash elsewhere, so write each one to run alike in both. zsh doesn't split an unquoted variable into words (`set -- $x` or `cmd $files` passes one argument), and it stops on a glob that matches nothing (`no matches found`) where bash passes the pattern on. Quote every variable, pass several values as separate arguments or loop over lines, and put anything that needs word splitting or loose globs in a `scripts/` helper that starts `#!/usr/bin/env bash`.

## Template

````markdown
---
name: verify
description: >
  Launch, health-check, drive and clean up {app} ({surface}) to prove a change works in the running
  app. Use before saying a user-facing change works, to reproduce a bug a user would see, or when
  the UI smoke check needs the app running. Features to drive are in features/README.md.
  Do NOT use for lint, type checks or tests — use the project's verify command.
---

# Verify {app}

How to run {app} locally and drive it the way a user does. {One sentence on the surface and, for a repo with several apps, which component each section covers.}

## Safety Rules

{The rules in sdlc-develop-verify-skill's `references/safety-rules.md` § The Rules, copied word for word.}

## Recorded Exceptions

{Each exception CD made to a Safety Rule for this app, one bullet each: the rule, exactly what it allows, why, and who decided it and when. For example: "**Point every target at this run's own copy:** the browser loads map tiles read-only from the public tile server at tiles.example.org, since no local server can stand in for it (CD, 2026-11-18)." Or "None."}

An exception allows only what its entry says. Stop only what this run started, Secrets by name only and Evidence survives cleanup take none. This section is kept apart from Safety Rules, which `/sdlc-develop-verify-skill maintain` replaces word for word.

Launch's Targets, the outbound integrations Health Check confirms, and these exceptions are this app's one list of outside connections. The factory reads the same list and holds it more strictly: an exception recorded here for interactive verify doesn't carry over to its runs. One that covers the factory too says so in its entry, and CD records it in the factory's allowlist as well (`[sdlc-root]/process/factory.md` D6 rule 6).

## Launch

Do these in order. Nothing writes to a target before step 4 confirms it.

1. **Run ID:** `{how a run picks its ID, such as a timestamp}`. It names the run's containers, sessions, data and evidence folder, and the run records under it every process ID it starts, with that process's start time (`ps -o lstart= -p "$pid"`), and whether it started each container.
2. **Secrets:** {the variables that hold secrets}. Name them; never write their values.
3. **Targets:** {each database, queue, cache, bucket and service URL the app reads, and the variable that points it at this run's own copy}. Never launch on a `.env` default that points at a shared service. A target a Recorded Exceptions entry covers points exactly where the entry says.
4. **Confirm targets:** `{the command or log line that shows where each target resolved}`. Each resolves to this run's own copy, or to exactly what its Recorded Exceptions entry allows.
5. **Fresh data:** {how to create the disposable data folder or database this run uses, then migrations and seed data}.
6. **Start:** `{exact command}` from `{directory}`.
7. **Ready when:** {the signal that a user could start working: a log line, a page that renders signed in, a prompt}. A process that answers is not enough.

A prerequisite outside the repo that is missing ({the container runtime, images, tools this launch needs}) prints `UNAVAILABLE: <what>` and stops, never a plain failure: the execute skills' smoke check skips on that line.

- **Isolation:** {whether two instances can run side by side, and on which ports and folders}. If they can't, refuse to drive an instance this run didn't start. A port this run picks is one browsers allow: Chrome refuses some, such as 5060 and 5061 (`net::ERR_UNSAFE_PORT`).
- **Short-lived CLI:** {build or install once, then run each drive in its own terminal session} (or "not applicable").

## Health Check

`{one read-only command or short sequence}`: the process is up, it is the build you expect, the port belongs to this run, each target resolves to this run's own copy (or, under a recorded exception, exactly where its entry allows), sign-in works, and {each outbound integration} is sandboxed or stubbed, confirmed by {what is observed: a local mail catcher, a sandbox host in the logs}. For a browser-driven surface it also loads one page through the browser: a port the browser refuses passes curl and fails every drive. Run it before the first drive and after anything surprising.

## Drive

- **Harness:** {Playwright MCP, the repo's e2e helpers, a terminal session, HTTP}.
- **Sign in:** {how, with which test account, by environment variable name}.
- **Handles:** {stable ones from this repo: accessible names, data attributes, routes, prompt strings}. Prefer them to coordinates and tab order.
- **Recipes:** one per feature, in `features/`. Start from `features/README.md`.

## Evidence

- **Where:** `.claude/skills/verify/.evidence/<run>/`, which the skill's `.gitignore` excludes.
- **What:** {screenshots and accessibility snapshots for UI; command, output and exit code for a CLI; request and response for an API}, plus a second, read-only view of anything a drive changed.
- **Manifest:** `manifest.json` in the run's folder, one entry per file, named by its path there: `{"file": "expense-add/02-list.png", "step": 2, "shows": "the list with the new expense, rounded to cents", "bug": false}`, `bug` saying whether it shows the bug. Screenshots are PNG; a run keeps at most one video (WebM) and one Playwright trace. The factory's stages write the same manifest to `.factory/evidence/`, kept flat there.
- **Name each artifact** with the feature and the entry point it proves.
- **Strip** auth headers, cookies and tokens from captured requests and logs.

## Cleanup

`{exact command}`: stops what this run started, by the IDs recorded under its run ID, and only a process whose start time still matches the recorded one, since a process ID is reused once its process ends. It removes the run's scratch data and never touches the evidence folder.

## Helpers

{Each script in `scripts/`: what it does and its exact invocation.} (Or "none: the commands above cover every step.")

## Unproven

{Steps proven only on a stand-in for the real target, if any.}

## Out of Reach

{What no local run of this skill can show, so a verify run is never cited as proof of it: the production build and its headers, sign-in that only production settings enable, a proxy the local run bypasses, a development-only hook being absent in production. Or "nothing known".} Unproven lists this skill's own steps proven only on a stand-in, and a feature marked `unreachable` lacks a precondition; this lists what the app does only outside a local run.

## Smoke Trigger Paths

{Optional; leave the section out unless CD lists paths. The paths whose change should trigger the execute skills' UI smoke check, beyond its default patterns: a plain-TypeScript client, the server endpoints a page calls. They take precedence over the backend-only skip (`[sdlc-root]/process/verify-command.md` § Companion).}
````

## Example

A filled Launch and Health Check for a fictional expense tracker, Tally: a web UI and API in one repo, with Postgres in Docker.

```markdown
## Launch

1. **Run ID:** `export RUN_ID=$(date +%Y%m%d-%H%M%S)`. Every ID below is recorded in `/tmp/tally-verify-$RUN_ID/`.
2. **Secrets:** `TALLY_SESSION_SECRET` and `TALLY_TEST_PASSWORD`.
3. **Targets:** `TALLY_DB_URL=postgres://127.0.0.1:5432/tally_verify_$RUN_ID`, never the `.env` default;
   `TALLY_MAIL_URL=smtp://127.0.0.1:1025`, the local mail catcher.
4. **Confirm targets:** `npm run config:print` shows `db host 127.0.0.1, db tally_verify_<run ID>` and
   `mail host 127.0.0.1`. Stop if either names another host.
5. **Fresh data:** if `docker info` fails, print `UNAVAILABLE: container runtime` and stop. If
   `docker compose ps -q db` is empty, run `docker compose up -d db` and write
   `started` to `/tmp/tally-verify-$RUN_ID/db-container`. Then `npm run db:create`,
   `npm run db:migrate` and `npm run db:seed`.
6. **Start:** `npm run dev -- --port 5180 & echo $! > /tmp/tally-verify-$RUN_ID/dev.pid` from the repo root, then
   `ps -o lstart= -p "$(cat /tmp/tally-verify-$RUN_ID/dev.pid)" > /tmp/tally-verify-$RUN_ID/dev.start`.
7. **Ready when:** `curl -sf http://127.0.0.1:5180/api/health` returns `"db":"ready"` and the sign-in
   page shows the "Sign in to Tally" heading. The database passes its own check before seeding
   finishes, so wait for the API's.

- **Isolation:** two runs can share the database container, each with its own database, but not
  port 5180. If 5180 is taken, refuse to drive it.
- **Short-lived CLI:** not applicable.

## Health Check

`scripts/doctor.sh 5180`: checks the API health endpoint, that the build hash in `/api/version` matches
`git rev-parse --short HEAD`, that port 5180 belongs to the process in `dev.pid`, that `config:print`
still names this run's database, that the test account in `TALLY_TEST_EMAIL` can sign in, that the
sign-in page loads in the browser on 5180, and that a test message reaches the local mail catcher.

## Cleanup

`pid=$(cat /tmp/tally-verify-$RUN_ID/dev.pid)`; if `ps -o lstart= -p "$pid"` still matches
`dev.start`, `kill "$pid"` (otherwise the process already ended and the ID may be another's). Then
`npm run db:drop -- tally_verify_$RUN_ID`. If
`/tmp/tally-verify-$RUN_ID/db-container` says `started`, run `docker compose stop db`; otherwise leave
the container, which another run may be using.
```
