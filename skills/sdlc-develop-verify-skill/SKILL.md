---
name: sdlc-develop-verify-skill
description: >
  Create or maintain the project's verify skill at .claude/skills/verify/: the launch recipe that tells
  an agent how to start the app, check it is healthy, drive it the way a user does, capture evidence
  and clean up, with a feature map of what to drive. CREATE reads the repo, writes the skill and a
  seed feature map, and drives every seeded feature once before handing it over. MAINTAIN checks every
  mapped feature against the source, drives each one live, and fixes the skill's own drift; it never
  edits product code and reports app bugs instead. Use when agents keep rediscovering how to launch
  the app, before relying on a UI smoke check, or after the app's features have changed.
  Triggers on "create a verify skill", "set up a launch recipe", "make a skill that drives the app",
  "maintain the verify skill", "the verify skill is out of date", "audit the verify skill",
  "/sdlc-develop-verify-skill".
  Do NOT use for running lint, type checks and tests — use the project's verify command or sdlc-tests-run.
  Do NOT use for writing test suites — use sdlc-tests-create.
  Do NOT use for creating any other skill — use sdlc-develop-skill.
  Do NOT use for an app that won't start or misbehaves — use sdlc-lite-plan, or sdlc-debug-incident for production.
---

# Develop the Verify Skill

A project's verify skill answers "does the change work in the running app?" (`[sdlc-root]/process/verify-command.md` § Companion). This skill writes one and keeps it true. Write it for the agent that will read it: one that opens it cold, mid-task, and has never seen the app. It is a recipe, deliberately lean: no Red Flags, Integration section or headless block of its own.

The generated skill belongs to the project. It is not in the framework's manifest, and `sdlc-migrate` never writes, overwrites or removes it (`[sdlc-root]/process/path-mappings.md` § Project-Specific Files).

**Argument:** `$ARGUMENTS` — empty for CREATE, or `maintain` for MAINTAIN.

**AskUserQuestion mandate:** every question directed at the user MUST use the `AskUserQuestion` tool — do not type questions as conversational text (Tool Rule in `[sdlc-root]/process/collaboration_model.md`). Status updates and completion reports that need no response use normal text. Text shown next to a pending question can be lost, so each question carries its own facts: what was found, the paths, and what each option does.

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## Mode Resolution

Check the precondition under Inputs and Output first. Then, where "present" means `.claude/skills/verify/SKILL.md` exists:

| `.claude/skills/verify/` | Request | Mode |
|--------------------------|---------|------|
| absent | anything but a maintain request | CREATE |
| absent | `maintain`, or a request to maintain, audit or update it | Stop and point at CREATE. **Headless run:** end with status `failed`. |
| present, with `features/README.md` | `maintain`, or a request to maintain, audit or update it | MAINTAIN |
| present, with `features/README.md` | anything else | Ask CD: maintain it, or replace it. **Headless run:** stop with `needs-input`. |
| present, written by hand (no `features/README.md`) | any | Ask CD: adopt it, or replace it. **Headless run:** stop with `needs-input`. |

- **Replace:** run CREATE. Once step 2 has shown the app starts, step 3 removes the old files with `git rm -r -q -- .claude/skills/verify/` before writing the new ones. They stay in git history, since the precondition requires them committed.
- **Adopt:** keep the file and its commands and gotchas, but the Safety Rules win: rewrite a kept command that breaks one so it keeps its intent, or ask CD (**Headless run:** `needs-input`). Before anything runs, apply CREATE step 6's mechanical check to its files and CREATE step 1 to what it doesn't cover; then run step 2 against its Launch. Then add the Safety Rules section, the `.gitignore` and the template's missing sections, and run CREATE steps 4 to 7.

## Workflow

```text
CREATE:   READ THE REPO → CHECK IT STARTS → WRITE → SEED THE MAP → PROVE → REVIEW → HAND OVER
MAINTAIN: LOCATE → READ THE SOURCE (agents, in parallel) → RECONCILE → DRIVE EVERY FEATURE → TRIAGE → REVIEW → HAND OVER
```

## Manager Rule

Read and follow `[sdlc-root]/process/manager-rule.md`. The work splits like this:

| Work | Who | Why |
|------|-----|-----|
| The generated `SKILL.md` and feature map | You | They are a project skill, which the orchestrator writes, as in `sdlc-develop-skill`. A fresh reviewer checks them before handover (step 6) |
| A helper script the skill ships | The agent that owns test and environment tooling by the file-scope rules in `[sdlc-root]/process/agent-selection.yaml`: `sdet` for drive helpers, `devops-engineer` for health and environment scripts, or the nearest equivalent | A script is code |
| Every live drive of the app | You | It is verification, as in the execute skills' UI smoke check, and one owner keeps instances from colliding. Keep screenshots and snapshots on disk and hold one line per feature in context |
| MAINTAIN's source reading | The domain agent that owns each feature's code, read-only | Explaining how a feature works means reading its code |

This skill never edits product code. An app that is broken is reported to CD, not fixed here.

**Agent Dispatch Protocol:** dispatch prompts describe WHAT and WHY: the helper's job and the rules it must keep, the feature to explain, or the skill to review. How is the agent's call. Build each prompt from `references/dispatch-prompts.md`, and for each agent consult `[sdlc-root]/knowledge/agent-context-map.yaml` for its entry and include relevant knowledge files in the dispatch prompt.

## Safety Rules

Read `references/safety-rules.md` before step 1. Its seven rules (instances, targets, outside effects, stopping, secrets, evidence, the real user path) bind every drive in both modes, and the generated skill carries a word-for-word copy. Where a step below names a rule, the reference's wording is the rule.

## Inputs and Output

- **Input:** a checkout whose app starts locally. If `.claude/skills/verify/` exists, it must be committed and clean, leaving out its evidence: `git ls-files -- .claude/skills/verify/` lists its files, and `git status --porcelain -- .claude/skills/verify/ ':!.claude/skills/verify/.evidence'` shows nothing. Otherwise ask CD to commit it or set it aside first, naming the files. For CREATE, the folder must not be git-ignored: `git check-ignore -q .claude/skills/verify/SKILL.md` must fail; if it succeeds, ask CD. **Headless run:** end with status `failed`, naming the files or the ignore rule.
- **Output:** `.claude/skills/verify/` with `SKILL.md`, `.gitignore`, `features/` and, if needed, `scripts/`; and, once CD says yes, one local commit of that folder only. Nothing is pushed.

## CREATE

### 1. Read the Repo

Answer these from the code, and ask CD only what the code can't tell you:

- **Surface:** what a user touches: a web UI, CLI, desktop app or API. A repo with several apps gets one verify skill with a section per component, the primary one first. A library with no app to run has nothing to drive: stop and say so. **Headless run:** end with status `failed` and that reason.
- **Launch:** the repo's own dev command (package scripts, Makefile, README), its ports, environment variables (and which hold secrets), migrations, seed data and sign-in.
- **Targets:** every database, queue, cache, bucket and service URL the launch reads, the override that makes each one local or disposable, and how to see where each resolved.
- **Outbound integrations:** mail, payments, messages, webhooks and third-party APIs, and how each is sandboxed or stubbed.
- **Drive:** an existing harness first (Playwright specs, Playwright MCP, CLI scripts, HTTP endpoints), otherwise a browser for web, a terminal session for a CLI, plain HTTP for a service. Check the tool is available in this session.
- **Evidence:** what can be captured: screenshots, accessibility snapshots, terminal output and exit codes, response bodies, logs, stored state.
- **Isolation:** whether two instances can run side by side (ports, data folders, profiles).

Ask CD about the gaps in one question that lists what was found: a fact the code doesn't show (which test account), a target that can't be made local, a target that can't be seen resolving before the app's first write (an app that migrates as it boots), an integration the app can't start without and can't sandbox, or a missing driving tool. An integration only some features need is not a gap: those features are `unreachable`. **Headless run:** stop with `needs-input`, listing the gaps.

### 2. Check It Starts

Set every target to this run's own copy, then confirm each one resolved there by something observed, before the first write of any kind (create, migrate, seed or reset). Then run the launch on fresh data. If the app doesn't reach a usable state, stop and report the command and the exact failure. When the cause is the environment (a stopped container runtime, a missing tool, a port another process holds), say what to fix. Otherwise point CD at the bug route (`sdlc-lite-plan`, or `sdlc-debug-incident` for a production incident): a recipe written against an app that doesn't start teaches the wrong steps. **Headless run:** end with status `failed` and the failure.

Either way, stop what this step started, by the IDs it recorded, before going on.

"Usable" means a user could start working, not that a process answers: a database can pass its health check while its setup scripts are still running.

### 3. Write the Skill

For a replace, remove the old files first, as Mode Resolution says. Write `.claude/skills/verify/SKILL.md` from `references/generated-skill-template.md`, and `.claude/skills/verify/.gitignore` containing `.evidence/`. The frontmatter is required: Claude Code registers the skill, and its built-in `run` behavior finds it, only through `name` and `description`. Fill every section with what step 1 found, with real commands and handles from this repo and no placeholders, and copy the Safety Rules in word for word.

Prefer the repo's own commands and harnesses. Add a helper script only when no existing command does the job, such as a health check that combines several probes. For each, dispatch the agent the Manager Rule names with `references/dispatch-prompts.md` § Helper Script Prompt.

### 4. Seed the Feature Map

Write `features/README.md` and one file for each of the 3 to 5 most-used user-facing features, found from routes, commands, menus or docs. Follow `references/feature-map-format.md`, including each feature's `Source:` paths in the index. A journey whose precondition the seed data lacks is `unreachable`, with the missing precondition in the feature's Gotchas. Never weaken a journey to make it pass.

### 5. Prove It

In one launch, run the generated skill exactly as written: launch, health check, drive every seeded feature, capture each one's evidence, clean up. Then confirm the evidence is still in `.evidence/`: a cleanup that deletes the proof fails this step. Fix what fails in the skill or map; a failing helper goes back to its agent. Run the skill's cleanup after every failed attempt, so nothing is left running.

After three attempts, mark each feature that still fails as `unproven` in the index and go on, naming them at handover. If launch or the health check itself still fails, stop and report the failing step. **Headless run:** stop with status `escalated` and the failing step.

If you proved it somewhere other than the real target (a container standing in for a fresh machine), list in the skill's Unproven section each step the stand-in did that the target won't.

**Validation:** the commands run, each feature's result, and the evidence path.

### 6. Review

Check the skill's files, excluding `.evidence/`. First, mechanically: no value of a secret-holding variable appears in them or in `.evidence/`, no process is stopped by name (`pkill`, `killall`) or by port, and no template brace or TODO is left. Then dispatch a fresh `code-reviewer`, never an agent that wrote any of it, with `references/dispatch-prompts.md` § Review Prompt. Step 5's drives prove the steps work; the reviewer checks what driving can't show: the Safety Rules, cleanup scope, secrets, and whether a cold reader could follow it.

Fix each finding: in `SKILL.md` or the map yourself, in a helper through its agent. Then run the mechanical check again, drive the features the fixes touched, and send the major findings back to the same reviewer, scoped to those rows, to confirm each is closed. That re-check confirms the named findings only and gathers no new ones. Give each finding two tries. A major finding still open after that stops the handover: report it to CD. A minor one still open is named at handover, and marks its feature `unproven` when it has one. **Headless run:** an open major finding stops with status `escalated` and the findings table.

This is a quality gate, as in `sdlc-develop-skill`, not a review-fix loop: step 5 already ran everything the reviewer read. Finish with a teardown check: nothing this run started still runs, and the evidence is in place.

### 7. Hand Over

Report in chat: the surface, each feature's result (proven, `unproven` or `unreachable`, with the reason), the evidence path, and the stand-in steps left unproven. Ask CD whether to commit, stating that it is one local commit of `.claude/skills/verify/` with nothing pushed. Commit only that folder (`git add -- .claude/skills/verify/`, then `git commit -m "<message>" -- .claude/skills/verify/`). **Headless run:** commit locally (local, reversible work), and say so in `notes`.

Say that `/sdlc-develop-verify-skill maintain` keeps the skill true after the app changes, and, for a UI surface, that the execute skills' UI smoke check now launches and drives the app through it.

## MAINTAIN

### 1. Locate

Read `.claude/skills/verify/SKILL.md` and `features/README.md`, and list the feature files. Then:

- Fix index drift: entries with no file, files with no entry, duplicates, dead links, and entries with no `Source:`.
- If the skill's Safety Rules section differs from `references/safety-rules.md`, replace it with the reference's text.
- If `.gitignore` lacks `.evidence/`, restore it. If `git ls-files -- .claude/skills/verify/.evidence` lists anything, evidence was committed: stop and tell CD. **Headless run:** end with status `failed`.

### 2. Read the Source

Dispatch read-only readers in parallel, following `[sdlc-root]/process/parallel-dispatch-monitoring.md`: one domain agent per area, with up to about six of its features, and one reader per domain for a feature whose `Source:` spans several. Build each prompt from `references/dispatch-prompts.md` § Source Reader Prompt, with each feature's file and `Source:` paths. Readers never drive the app and never edit files. A reader whose report leaves out a feature it was given has failed for that feature, and is re-dispatched once with a revised prompt (Manager Rule § Failed Agent Dispatch). If that fails too, the feature is `blocked`. One retry stops short of the 3-strike rule on purpose: nothing waits on a reader, and the next maintain run tries again.

### 3. Reconcile

Check that every feature has a report. Merge the returned recipes into as few app states as practical. Spot-check each drift a reader cited against its source line; don't re-prove clean reports. Then look for features the map is missing: in the readers' `missing_from_map`, and by comparing the app's own lists of user entry points (route tables, command definitions, menus) with the entry points the map names. Call a feature missing only when you can name its source path. Write a feature file for each missing feature from the reader's recipe; step 4 drives it.

### 4. Drive Every Feature

Follow the skill's own launch model: one long-lived instance driven in turn for a server or UI, or a fresh session per drive for a short-lived CLI. Drive every feature at least once, even when the source reading found nothing. Hold three rules the whole pass:

- **Health check before trusting an instance,** including the target and integration checks: before the first drive, on every fresh session, and after any failed drive. Where the health check can't see the problem, such as a stuck UI on a healthy process, reset to a known state or relaunch.
- **Evidence survives every cleanup.** Check it in `.evidence/`.
- **Nothing a drive started outlives the drive.** Clean up after a failed attempt too. With the run's long-lived instance, clean up what the drive created, not the instance.

A health check that fails because the skill has drifted is drift: fix it, with the same two tries as any fix (step 5). If launch or the health check still fails after that, stop driving: the run is `blocked`. A feature you can't reach is `unreachable` only with the missing prerequisite (sign-in, entitlement, operating system, a live integration) and the route you tried. If the map doesn't name that prerequisite, that's drift too.

### 5. Triage

| What you found | What it is | What happens |
|----------------|------------|--------------|
| The map or skill describes it wrong, or leaves it out | Drift | Fix the map or skill |
| The app works, but the skill can't drive it | Harness gap | Fix the skill; a helper goes to its agent |
| The app doesn't do what a user expects | Product bug | Don't touch it. Record it for CD with the steps that show it, and offer the bug route: `sdlc-lite-plan`, `sdlc-debug-incident`, or a handoff with `sdlc-handoff`. The feature is reported with its bug, never as proven |

Make and drive one fix at a time. Before each, save the text it replaces to a scratch file outside the skill folder. A fix that still fails after two tries is undone by putting back exactly that text (not `git checkout`, which would drop the other fixes in the file), and the run is `blocked` on it. A feature file this run created that can't be proven stays in the index as `unproven`, with the reason; it counts as a change, not a block.

### 6. Review

As CREATE step 6, on the files this run changed, then drive again the features those fixes touched. Tear down only after the last drive, and run the teardown check.

### 7. Hand Over

The outcome is the most severe that applies: **blocked** (a reader failed twice, a fix couldn't be proven, or the app stopped launching), then **changed** (fixes to the skill, map or helpers, each driven live), then **clean** (nothing needed changing). An `unreachable` feature with its prerequisite named, and a feature failing on a reported product bug, are covered and reported; neither changes the outcome.

Report the outcome, the coverage per feature, and product bugs first and separately. Commit the proven fixes of a changed or blocked run: ask CD, stating it is one local commit of `.claude/skills/verify/`, and commit as in CREATE step 7. A clean run commits nothing. **Headless run:** commit the proven fixes locally. A blocked run ends with status `escalated` and what blocked it. Take the no path on the bug-route offer, listing it under `skipped`, and list the bugs under `deferred`.

Keep run notes (features covered, unreachable prerequisites, drift found, outcome) out of the commit.

## Troubleshooting

| Problem | What the skill does |
|---------|---------------------|
| `.claude/skills/verify/` has uncommitted or untracked files | Stops before any edit and names them. Headless: `failed` |
| The project's verify skill was written by hand | Asks CD whether to adopt or replace it. Headless: `needs-input` |
| The app doesn't start | Stops with the command and the failure, and points at the bug route. Headless: `failed` |
| A target can't be made local, or the app needs an unsandboxable integration to start | Asks CD; never launches against it. Headless: `needs-input` |
| The proof keeps failing on one feature | Marks it `unproven` after three attempts and names it at handover |
| Another instance holds the port | Refuses to drive it, and says what to free. In CREATE step 2, headless: `failed`. In MAINTAIN, the run is `blocked`; headless: `escalated` |
| A reader leaves out a feature twice | That feature is `blocked`, and so is the run. Headless: `escalated` |

## Red Flags

| Thought | Reality |
|---------|---------|
| "The app won't start, I'll fix it first" | This skill never edits product code. Report the failure and point at the bug route. |
| "I set `DATABASE_URL`, so it's local" | Confirm where each target resolved by observing it, before the first write. An override the app ignores does nothing. |
| "Test mode is on, so nothing goes out" | Confirm each integration is sandboxed by observing it. Some test modes still send. |
| "I'll write the recipe from the README" | A recipe that was never run is a draft. Step 5 drives every seeded feature before anyone relies on it. |
| "The map says it works, so it works" | MAINTAIN drives every feature live, even when the source reading is clean. |
| "Weaken this journey so it passes" | A journey that can't pass is `unreachable` with its reason. Weakening it hides the gap from every later run. |
| "`pkill node` will clean up" | Stop only what this run started, by its recorded ID. Killing by name or port takes down other people's work. |
| "Paste the test password into the recipe" | Name the environment variable. The skill is committed. |
| "I'll write this helper script myself" | A script is code: the tooling agent writes it, and a fresh reviewer checks it. |
| "The app is wrong here, so I'll fix the map to match" | A user-visible behavior that's broken is a product bug. Record it for CD; don't document it as correct. |
| "Their verify skill is stale, I'll replace it" | Replacing discards the project's file. Ask CD; a hand-written one can be adopted instead. |

## Integration

- **Depends on:** an app that starts locally; `[sdlc-root]/process/verify-command.md` § Companion (the convention); domain agents per `[sdlc-root]/process/agent-selection.yaml`
- **Feeds into:** `sdlc-execute` and `sdlc-lite-execute` (their UI smoke check launches and drives the app through `.claude/skills/verify/`); Claude Code's built-in `run`; the bug route (`sdlc-lite-plan`, `sdlc-debug-incident`, `sdlc-handoff`) for product bugs MAINTAIN finds
- **Uses:** `code-reviewer` (step 6), `[sdlc-root]/process/manager-rule.md`, `[sdlc-root]/process/headless-mode.md` (the skill's gate sites are listed in its § Integration), `[sdlc-root]/process/parallel-dispatch-monitoring.md`, `[sdlc-root]/knowledge/agent-context-map.yaml`, `[sdlc-root]/knowledge/architecture/agent-orchestration-patterns.yaml` (dispatch template), `[sdlc-root]/process/collaboration_model.md` (Tool Rule), `references/safety-rules.md`, `references/generated-skill-template.md`, `references/feature-map-format.md`, `references/dispatch-prompts.md`
- **Complements:** the project's verify command (do the checks pass?) and `sdlc-tests-create` (tests that run in CI); this skill covers driving the running app
- **Does NOT replace:** `sdlc-tests-run` (runs the test suite and fixes failures), `sdlc-develop-skill` (any other project skill)
- **DRY notes:** the convention lives in `verify-command.md` § Companion; this skill builds to it. The Safety Rules live only in `references/safety-rules.md`; each generated skill carries a copy that MAINTAIN step 1 refreshes. The execute skills only follow the generated skill; they don't restate it.

## Additional Resources

- `references/safety-rules.md` — the rules that bind every drive, copied into each generated skill
- `references/generated-skill-template.md` — the generated `SKILL.md`: frontmatter, sections and an example
- `references/feature-map-format.md` — the feature map's index and feature files, with an example
- `references/dispatch-prompts.md` — the helper script, source reader and review prompts
