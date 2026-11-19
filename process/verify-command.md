# The Verify Command Convention

Every project should expose **one discoverable one-shot command** that runs the full pre-commit verification chain — lint, typecheck, format check, tests — so that neither agents nor humans have to reconstruct the gate from scattered package scripts.

## The Convention

- **One entry point at the repo root**, named `verify`, in the project's native runner: `npm run verify` / `pnpm verify`, `make verify`, `just verify`, `./scripts/verify.sh`, `uv run poe verify` — whatever the stack already uses. Don't introduce a new task runner just for this.
- **It chains every gate that CI runs** (or a documented subset, with the difference stated where the command is defined). A verify command that passes while CI fails is a broken promise — keep the two in sync, ideally by having CI call the same command.
- **Monorepos:** the root `verify` fans out to every package. A package without lint/typecheck/test scripts is a gap the root command makes visible rather than papers over.
- **It is documented in CLAUDE.md** (root instructions) so agents find it without spelunking. The review-fix loop's Verification Gate (`[sdlc-root]/process/review-fix-loop.md` Step 0) and any pre-commit checks should invoke it rather than re-listing individual tools.

## Why It's Framework-Level

Agents run verification constantly — before review loops, after fixes, before commits. When the gate is a single command, it gets run; when it's four commands scattered across packages, steps get skipped and the review loop enters with known-red checks. `sdlc-initialize` offers § Setting it up during the install (Phase 9b), and `sdlc-migrate` offers it to a project with no record of it; the codebase-health audit (`sdlc-audit` health mode, Sweep 1) flags the command's absence as a gap.

## Companion: the Project Launch-Recipe Skill

The verify command answers "do the checks pass"; a separate question — "does the change work in the *running* app" — deserves its own durable home. Mature projects grow a **project-local launch-recipe skill** (conventionally `.claude/skills/verify/`): the concrete build/launch commands per component, ports, how to drive the app end-to-end (including how to get authenticated), and the accumulated environment gotchas that otherwise burn a rediscovery session each time (stale containers, port-forward failures, techniques for capturing racy UI states). It is project-specific by nature — the framework defines the convention, not the content. Seed one the first time a session has to rediscover how to launch the app; grow it every time a new gotcha costs real time. Claude Code's built-in `run` behavior looks for exactly such a skill before falling back to guessing. `/sdlc-develop-verify-skill` writes one from the repo, with a feature map of what to drive, and runs it end to end before handing it over; its `maintain` mode re-checks every mapped feature after the app changes. The skill belongs to the project, and migration never touches it (`[sdlc-root]/process/path-mappings.md` § Project-Specific Files). The UI smoke check in `sdlc-execute` and `sdlc-lite-execute` launches and drives the app through it when it exists.

**What the smoke check reads from it.** Two parts of the verify skill are a contract with that check:

- **`UNAVAILABLE: <what>`.** When a prerequisite outside the repo is missing (a stopped container runtime, an image it can't pull offline, a tool that isn't installed), the launch prints this line and stops, instead of failing. The smoke check skips on it (`UI smoke: skipped — UNAVAILABLE: <what>`) when the app needed that prerequisite before the phase. A prerequisite the phase added (a new tool, image or dependency) is the phase's to provide, so it fails the smoke check.
- **`## Smoke Trigger Paths`** (optional): paths whose change should trigger the smoke check, for UI the default patterns miss (a plain-TypeScript client, the server endpoints a page calls). They add to the defaults and take precedence over the backend-only skip; they never remove a default. Without the section, the defaults apply. CD sets the list. `sdlc-develop-verify-skill` maintain never changes it on its own, and it isn't derived from the feature map's `Source:` lines, which also name backend files that need no launch.

## Scaffolding Guidance

When creating a verify command in a project that lacks one:

1. Inventory what exists: which of lint / typecheck / format / test are configured, per package.
2. Chain what exists — do not invent new tooling as a side effect: every gate CI runs, with CI's own command for it, and any a package configures beyond them. A gate neither CI nor the package has is a gap, reported, not silently added; a gate CI runs that the package doesn't configure (CI's `mypy .` with no mypy settings) is chained as CI runs it, and its missing configuration is a gap.
3. Fail fast and loudly: the command exits non-zero on the first failing gate and names it.
4. Add the one-line usage to root CLAUDE.md.

## Setting it up

**Runbook:** `verify-command` · **When:** setup · **Record:** `docs/runbooks/verify-command.md` § Record

Finds the project's verify command, or scaffolds one over the gates that exist, and records the gaps.
`sdlc-initialize` offers it during the install (Phase 9b); `sdlc-run-runbook verify-command` runs it any time,
again after the project's gates or CI change.

**Ask first,** with step 1's inventory shown: scaffold the command, or extend the one found, over what exists
(§ Scaffolding Guidance; recommended), or leave the project as it is; and, for each gap, whether its package's
owner adds the missing gate (recommended: record it, and the codebase-health audit tracks it). Nothing to ask when
step 1 finds a command that chains what CI runs, documented, with no gaps. **Done when:** every step passed, or
was skipped by a decision.

1. **Inventory.** Find a root verify command (`"verify"` in `package.json`, a `verify:` target in a `Makefile` or
   `justfile`, `scripts/verify.sh`, the stack's equivalent) and read what it runs; for each package, which of
   lint, typecheck, format check and tests it configures; and what CI runs. A package missing a gate is a gap. A
   retrofit project often has some packages covered and some not. **Check:** State lists the command (or none),
   each package's gates and CI's.
2. **[CD] Decide** (asked first). **Check:** Decisions hold the answer, and one for each gap.
3. **Scaffold or extend** the command per § Scaffolding Guidance. Skipped when step 1's command already chains
   what CI runs, or CD chose to leave the project as it is. **Check:** with a failure put in the first gate it runs
   (a lint error in a scratch change, reverted after), the command exits non-zero and names that gate; and State
   records what it gives on the tree as it is (passes, or the gate that already fails).
4. **Document it** in the project's root `CLAUDE.md`, with any difference from CI stated where the command is
   defined. Skipped when CD chose to leave the project as it is and there's no command. **Check:** `CLAUDE.md`
   has the command's one-line usage, and where the command is defined, each gate CI runs that it doesn't is
   named.
5. **Record the gaps** under Deferred, each with CD's decision and its owner. **Check:** every gap step 1 found is
   there.
