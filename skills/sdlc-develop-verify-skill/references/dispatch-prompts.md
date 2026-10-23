# Dispatch Prompts

The three prompts `sdlc-develop-verify-skill` sends: the helper script prompt (CREATE step 3, and MAINTAIN step 5 for a harness gap), to the agent that owns test and environment tooling; the source reader prompt (MAINTAIN step 2), to the domain agent that owns a group of features' code; and the review prompt (step 6 in both modes), to a fresh `code-reviewer`. All three follow the full dispatch template in `[sdlc-root]/knowledge/architecture/agent-orchestration-patterns.yaml` § dispatch_prompt_templates. Fill in the braces, and drop a line in braces that doesn't apply.

## Helper Script Prompt

```markdown
**Objective:** Write the helper script the project's verify skill needs to {the job, such as "check the app is healthy before a drive"}, so an agent can run that step with one command.

**Owned files:** `.claude/skills/verify/scripts/{name}`. Nothing else.

**Constraints:**
- The verify skill's Safety Rules bind the script: read .claude/skills/sdlc-develop-verify-skill/references/safety-rules.md.
- Read {the agent's mapped knowledge files} for this codebase's patterns.
- {Headless run only: this run is headless. Ask nothing; put questions in your report. Cause no side effect outside the working tree: no push, post, comment or external send.}
- Use the tools the repo already has. Say so in your report if the script needs anything new.
- Record what the script starts (process IDs, container or session names) so cleanup can stop exactly that.
- Make it executable, start it with a usage line, and exit non-zero with a message that names the failing step.
- Don't stage or commit.

**Acceptance criteria:**
- `{the invocation the skill will show}` does {the observable result} and exits 0.
- On failure it exits non-zero and says which step failed.
- You return: the path, the exact invocation, what it does, its exit codes, and anything it couldn't do.

**Out of scope:**
- Product code. If the app itself is wrong, report it.
- The skill's SKILL.md and feature map: the orchestrator writes those.
- CI and test suites.
```

## Source Reader Prompt

```markdown
**Objective:** Explain from the source how a user uses {feature}, and say where the verify skill's description of it no longer matches the code.

**Owned files:** Read-only. Do not modify files.

**Constraints:**
- The features: {for each, its file in `.claude/skills/verify/features/` and its `Source:` paths}.
- Read {the agent's mapped knowledge files} for this codebase's patterns.
- {Headless run only: this run is headless. Ask nothing; put questions in your report.}
- Don't start the app, drive it, or run anything that changes state. Reading code and git history is fine.
- Cite `path:line` for every claim about what the code does.

**Acceptance criteria:** Return, per feature:
    feature: {name}
    summary: {how a user uses it, in two to four sentences}
    entry_points: [{the user's route or command} → {path:line}]
    drift: [{map_says: "...", code_does: "...", source: "path:line"}]   # or: none
    missing_from_map: [{sub-feature or entry point, its path:line, and a recipe as below}]   # or: none
    recipe: {one live recipe: preconditions, each action with its exact handle, and the end state that proves it}

**Out of scope:** Fixing drift (report it), reviewing code quality, and features outside your list.
```

## Review Prompt

```markdown
**Objective:** Review the project's verify skill before it is handed over: would a cold reader follow it safely, and does it keep its Safety Rules?

**Owned files:** Read-only. Do not modify files.

**Constraints:**
- Review {every file in `.claude/skills/verify/` except `.evidence/`; for MAINTAIN, the files this run changed; for a re-check, only whether these findings are closed: {the rows}}. The run already drove every step and feature in them; the results: {each feature's result}.
- The Safety Rules to compare against, word for word: .claude/skills/sdlc-develop-verify-skill/references/safety-rules.md § The Rules.
- {Headless run only: this run is headless. Ask nothing; put questions in your report.}
- Don't start or drive the app.

**Acceptance criteria:** One row per finding, with `path:line`, severity (major / minor), what is wrong, and the fix. Check:
- Every Safety Rule is copied word for word and nothing in the files breaks one: a target not overridden to a local copy, an integration not confirmed sandboxed, a stop by process name, a secret's value, cleanup that can reach `.evidence/` or an instance the run didn't start.
- The frontmatter has `name: verify` and a description naming the app, its surface and when to use it.
- No placeholder, TODO or invented handle; every helper script's invocation is shown and the script exits non-zero with a message on failure.
- An agent that has never seen the app could follow each step without guessing.
- A clean review is an acceptable result; say so.

**Out of scope:** Product code, and suggestions beyond the verify skill.
```
