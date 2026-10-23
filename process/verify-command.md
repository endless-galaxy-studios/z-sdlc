# The Verify Command Convention

Every project should expose **one discoverable one-shot command** that runs the full pre-commit verification chain — lint, typecheck, format check, tests — so that neither agents nor humans have to reconstruct the gate from scattered package scripts.

## The Convention

- **One entry point at the repo root**, named `verify`, in the project's native runner: `npm run verify` / `pnpm verify`, `make verify`, `just verify`, `./scripts/verify.sh`, `uv run poe verify` — whatever the stack already uses. Don't introduce a new task runner just for this.
- **It chains every gate that CI runs** (or a documented subset, with the difference stated where the command is defined). A verify command that passes while CI fails is a broken promise — keep the two in sync, ideally by having CI call the same command.
- **Monorepos:** the root `verify` fans out to every package. A package without lint/typecheck/test scripts is a gap the root command makes visible rather than papers over.
- **It is documented in CLAUDE.md** (root instructions) so agents find it without spelunking. The review-fix loop's Verification Gate (`[sdlc-root]/process/review-fix-loop.md` Step 0) and any pre-commit checks should invoke it rather than re-listing individual tools.

## Why It's Framework-Level

Agents run verification constantly — before review loops, after fixes, before commits. When the gate is a single command, it gets run; when it's four commands scattered across packages, steps get skipped and the review loop enters with known-red checks. `sdlc-initialize` checks for this command during setup (Phase 9b) and offers to scaffold it; the codebase-health audit (`sdlc-audit` health mode, Sweep 1) flags its absence as a gap.

## Companion: the Project Launch-Recipe Skill

The verify command answers "do the checks pass"; a separate question — "does the change work in the *running* app" — deserves its own durable home. Mature projects grow a **project-local launch-recipe skill** (conventionally `.claude/skills/verify/`): the concrete build/launch commands per component, ports, how to drive the app end-to-end (including how to get authenticated), and the accumulated environment gotchas that otherwise burn a rediscovery session each time (stale containers, port-forward failures, techniques for capturing racy UI states). It is project-specific by nature — the framework defines the convention, not the content. Seed one the first time a session has to rediscover how to launch the app; grow it every time a new gotcha costs real time. Claude Code's built-in `run` behavior looks for exactly such a skill before falling back to guessing. `/sdlc-develop-verify-skill` writes one from the repo, with a feature map of what to drive, and runs it end to end before handing it over; its `maintain` mode re-checks every mapped feature after the app changes. The skill belongs to the project, and migration never touches it (`[sdlc-root]/process/path-mappings.md` § Project-Specific Files). The UI smoke check in `sdlc-execute` and `sdlc-lite-execute` launches and drives the app through it when it exists.

## Scaffolding Guidance

When creating a verify command in a project that lacks one:

1. Inventory what exists: which of lint / typecheck / format / test are configured, per package.
2. Chain what exists — do not invent new tooling as a side effect. Missing gates are reported as gaps, not silently added.
3. Fail fast and loudly: the command exits non-zero on the first failing gate and names it.
4. Add the one-line usage to root CLAUDE.md.
