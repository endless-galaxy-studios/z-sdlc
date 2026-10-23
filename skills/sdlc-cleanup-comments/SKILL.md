---
name: sdlc-cleanup-comments
description: >
  Trim code comments down to the ones that say what the code can't show at a glance: why a decision
  was made, how a piece connects to code elsewhere, an outside constraint, a public contract.
  Domain agents cut comments that repeat or narrate the code, a fresh reviewer checks every cut, the
  verify command checks that nothing it covers broke, and a report lists what needs CD's call: unclear comments
  (kept), comments that contradict the code, and complex code with no explanation. Edits only
  comments, plus the blank line or padding a cut leaves behind, and writes no new comments. Use when comments have piled up across a codebase, before opening
  a large pull request, or when a module is hard to read for the noise. Scope: the whole repo, paths,
  or a commit range.
  Triggers on "clean up comments", "cleanup comments", "trim comments", "cut comment bloat",
  "remove unnecessary comments", "too many comments", "comment cleanup", "/sdlc-cleanup-comments".
  Do NOT use for reviewing a diff for bugs or quality — use sdlc-review-code.
  Do NOT use for writing developer documentation — use sdlc-create-reference-doc.
  Do NOT use for refactoring code so it needs fewer comments — the report lists those spots; plan them with sdlc-lite-plan.
---

# Cleanup Comments

Cut the comments that repeat the code and keep the ones that carry what it can't show. The rule for which is which lives in `[sdlc-root]/knowledge/coding/comment-discipline.yaml`. This skill applies it to code that already exists. It changes nothing but comments, plus the blank line or padding a cut leaves behind, and writes no new comments.

**Argument:** `$ARGUMENTS` (optional) — one or more paths, a commit range ending at `HEAD` (e.g. `main..HEAD`), or empty for the whole repo.

**AskUserQuestion mandate:** every question directed at the user MUST use the `AskUserQuestion` tool — do not type questions as conversational text (Tool Rule in `[sdlc-root]/process/collaboration_model.md`). Status updates and completion reports that need no response use normal text. Text shown next to a pending question can be lost, so each question carries its own facts: the counts, the paths and what each option does.

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## Workflow

```text
SCOPE → BASELINE → SLICE → TRIM (domain agents, in parallel) → CHECK (fresh reviewer) → VERIFY → REPORT → DECIDE → COMMIT
```

## Manager Rule

Read and follow `[sdlc-root]/process/manager-rule.md`. Trimming edits code files, so the domain agent that owns each slice does it. The same agent fixes what a cut broke (step 6), because finding the cause means reading code.

You apply only three kinds of code change yourself. Each is mechanical under the Delegation Economics Exception:

| Change | Step | Its review |
|--------|------|------------|
| Put back the exact `HEAD` text of a hunk the floor or the check flagged | 5 | `git diff -U0 HEAD -- <path>` no longer shows the hunk |
| Restore a whole slice, once CD authorizes it | 6 (also reached from 4, 5 and 8) | `git diff HEAD -- <slice files>` is empty |
| Cut a comment CD picked | 8 | The numstat differs from the one saved just before the cut by exactly the picked lines |

One departure from the Manager Rule is deliberate: a diff check stands in for § Mandatory Review's domain-agent review of these three. Each puts back `HEAD`'s own bytes or removes a line CD named, so nothing is left for a reviewer to judge. A whole-slice restore discards edits in files this run didn't create, so it always asks CD first (§ No Revert Without Authorization).

**Agent Dispatch Protocol:** Dispatch prompts describe WHAT and WHY: the slice, the rule, the report to return. Which comments to cut in a file is the agent's call under the rule.

## Inputs and Output

- **Input:** the argument above, a clean working tree for the files in scope, and the project's verify command (`[sdlc-root]/process/verify-command.md`).
- **Output:** comment-only edits in the working tree (counts everywhere are net of put-backs), a report at `docs/reviews/comment-cleanup-{YYYY-MM-DD}.md` (step 7; a second run on the same day adds `-2`, and so on), and, once CD says yes, one local commit per area. Nothing is pushed.

## Steps

### 1. Resolve the Scope

| Argument | Scope | How to gather |
|----------|-------|---------------|
| None | Every tracked source and config file | `git ls-files` |
| Path(s) | Tracked files under those paths | `git ls-files -- <paths>` |
| Commit range ending at `HEAD` | Only comments the range added or changed, in the files it touched | `git diff --name-only <range>`, then `git diff -U0 <range>` |

A range must end at `HEAD`, so its line numbers match the working tree. Any other range ends the run as invalid input: tell CD and stop. **Headless run:** end with status `failed`.

Then drop the files listed in `references/machine-read-comments.md` § Files to Skip: generated and vendored code, lockfiles and built output, applied migrations, test fixtures and snapshots, `[sdlc-root]/` and `.claude/`, and prose files. Config files (YAML, TOML, Dockerfiles, shell, SQL) stay in scope: their comments follow the same rule.

**Precondition — no uncommitted changes in scope.** Run `git status --porcelain --untracked-files=no -- <scope>`. If any file in scope has uncommitted changes, stop and ask CD to commit them or set them aside first; the question lists the files. Never stash, reset or restore them yourself (Manager Rule § No Revert Without Authorization). The trims must be the only changes in those files, so a later restore can't touch anyone's work. **Headless run:** end with status `failed`, naming the files.

Record `git rev-parse HEAD`. Every diff below compares the files with `HEAD` (`git diff HEAD`), so an edit someone stages still shows.

**Validation:** state the scope back in one line: files in scope, areas, and files skipped and why.

### 2. Record the Baseline

Run the verify command on the untouched tree and save its result. If the project has none, run the lint, type-check and test commands its CLAUDE.md names. Failures here are not the trim's fault: step 6 compares against this list.

If the project has no way to verify at all, ask CD whether to go ahead unverified or stop. The question says that no verify, lint, type-check or test command was found, and that unverified, a cut a tool needed would go unnoticed. **Headless run:** end with status `failed` and the reason: a commit nobody can verify is not local, reversible work the run may do on its own.

### 3. Plan the Slices

Split the scope into **slices**: disjoint file sets, each owned by one domain agent. Pick the agent for each area by the file-scope rules in `[sdlc-root]/process/agent-selection.yaml` (components to the frontend agent, services to the backend agent, and so on). Keep a slice small enough for one agent to read every file in full, about 40 files or 4,000 lines; split a larger area by directory. An area no domain agent owns goes to the project's refactoring or general implementation agent. If it has neither, ask CD which agent takes it, naming the area and its file count. **Headless run:** stop with `needs-input`, naming the unowned areas.

Output the plan:

```text
Comment cleanup: whole repo
Files in scope: 412 in 6 areas (38 skipped: 21 generated, 9 vendored, 8 applied migrations)
Baseline: verify passes

Slices:
- [ ] web/src/components — frontend-developer, 37 files
- [ ] web/src/lib — frontend-developer, 22 files
- [ ] api/app/billing — backend-developer, 31 files
```

With more than one slice, ask CD whether to proceed, narrow the scope, or stop. The question states the slice count, the file count and that each slice is one agent dispatch. **Headless run:** proceed. The edits are local and reversible. Say so in `notes`.

### 4. Trim

Dispatch every slice's agent in parallel, following `[sdlc-root]/process/parallel-dispatch-monitoring.md`. Consult `[sdlc-root]/knowledge/agent-context-map.yaml` for each slice agent's entry and include relevant knowledge files in the dispatch prompt. Read `[sdlc-root]/knowledge/coding/comment-discipline.yaml` and include it in every dispatch, whatever the map says. Build each prompt from `references/dispatch-prompts.md` § Trimmer Prompt, with the slice's file list and, for a commit-range scope, the range.

An agent may delete a comment, shorten one by cutting the part that repeats the code, and delete the one blank line a cut leaves redundant. Nothing else. It returns the report in the prompt: counts, plus the lists step 7 needs, each entry with a location and an anchor.

**Validation:** as each agent returns, confirm `git rev-parse HEAD` still prints the commit step 1 recorded. An agent that committed would hide its trims from every check: stop and tell CD. **Headless run:** end with status `failed`. Then record the slice's state: `git diff HEAD -- <slice files> | git hash-object --stdin`. Record it again after a re-dispatch and after every put-back in steps 5 and 6. A whole-slice restore compares against the last value (step 6). It catches changes made after it was recorded, not changes someone made while an agent was working.

Run `git diff --stat HEAD` and check each slice's `files_changed` list against its own files. A changed file that's in no slice may hold someone else's work: ask CD what to do with it, naming the file and the agent that touched it. **Headless run:** leave it as it is, keep it out of every commit, and list it under `deferred`. A file one agent changed in another agent's slice is a file conflict: handle it as `[sdlc-root]/process/parallel-dispatch-monitoring.md` says. An agent that returns no report is re-dispatched once with a revised prompt (Manager Rule § Failed Agent Dispatch). If that fails too, its slice goes to the whole-slice restore (step 6). This stops short of the 3-strike rule in `parallel-dispatch-monitoring.md` on purpose: nothing waits on the slice, and leaving it for the next run costs less than a third dispatch.

### 5. Check Every Cut

First, a mechanical floor. For each slice, `git diff --numstat HEAD -- <slice files>` shows added lines. A trim only deletes and changes lines in place, so a slice's added lines can't exceed its agent's `lines_modified`. If they do, the hunks at fault in `git diff -U0 HEAD` are the ones whose added count exceeds their removed count. For a commit-range scope, every removed line must also appear as a `+` line in `git diff -U0 <range>`; a hunk that removes anything else cut a comment the range didn't add.

Then dispatch a **fresh** `code-reviewer`, never the trimmer, with `references/dispatch-prompts.md` § Check Prompt. Give each reviewer up to about four slices or 2,000 diff lines, and run the reviewers in parallel. The dispatch passes only the rule and `references/machine-read-comments.md`: the check judges cuts against one rule, and wider context would only widen it.

A reviewer's answer counts only if it states `problems`, and its `hunks_reviewed` equals the hunk count of its slices, `git diff -U0 HEAD -- <its slice files> | grep -c '^@@'`, taken from the diff the reviewer saw, before any put-back. A clean report says so with its count. Any other answer is a failed dispatch. Re-dispatch once with a revised prompt, stopping short of the 3-strike rule for the reason step 4 gives. If that fails too, its slices go to the whole-slice restore (step 6).

For every flagged hunk, and every hunk the floor found, put back the exact original lines from `git show HEAD:<path>`. Check that `git diff -U0 HEAD -- <path>` no longer shows that hunk, and record the slice's state. When the reviewer flags a cut that should have been listed, it names the list and fills in that list's fields; copy its row into that list. Count every put-back under "Restored after check".

This check runs once and is not a review-fix loop (`[sdlc-root]/process/review-fix-loop.md`). Every correction puts back text from `HEAD`, so a second round would only compare `HEAD` to `HEAD`. Step 6 then machine-checks the corrected tree.

### 6. Verify

Run the step 2 command again and compare with the baseline. A failure the baseline didn't have is the trim's. Give the failure output to the agent that owns the file it names, with `references/dispatch-prompts.md` § Fix Prompt. A cut breaks a tool in one of two ways: the tool needed the comment, and the agent puts back that hunk's exact `HEAD` text; or the cut left a blank line the tool rejects, and the agent deletes it and the cut stands.

Before dispatching the fix, save `git diff --numstat HEAD -- <slice files>`. Check the result against it: only the file the agent names has changed; a put-back is gone from `git diff -U0 HEAD -- <that file>`; a stray blank line shows as exactly one more removed line there, with added lines unchanged. Then record the slice's state and run again. If that agent finds no cause in its slice, give the failure to the agents of the other slices the failing check covers, one at a time. List each comment put back for a tool in the report, so CD can record it where the rule's Machine-read kind says and the next run won't cut it.

**Whole-slice restore.** After that one round of fixes, a new failure that remains means restoring the slices it names, or every slice the failing check covers when it names none. Steps 4 and 5 end here too, for a slice whose dispatch failed twice, and so does a failure after step 8's cuts. Compute the slice's hash again, then ask CD before restoring. The question names the slice, the reason (the failure, or the failed dispatch), and whether the hash matches the last recorded value: a mismatch means someone else has changed those files, and restoring would discard their changes too. The options are restore the slice (`git restore --source=HEAD --staged --worktree -- <slice files>`) and go on, or stop: every trim stays uncommitted for CD to look at, and the run ends with the report. A restored slice is reported under Not Trimmed. After a restore, run the step 2 command again; the report's Verification line comes from that run. **Headless run:** restore nothing. Leave the slice out of every commit and list it under `deferred` with the reason. While a failure remains, step 9 commits nothing.

### 7. Report

Write the report from `references/report-template.md`, creating `docs/reviews/` if it's missing. Follow `[sdlc-root]/process/writing-for-cd.md`: the first line tells CD what happened and what waits on them. Leave out any section with nothing in it. Counts are net of put-backs. Locations reported in step 4 can move when later steps put lines back, so find each entry's anchor in the final file and use the line it's on now.

A comment that contradicts the code may point to a bug. Lead your chat summary with that section, and don't change the code or the comment.

In chat, give a summary of about 150 words and the report's path.

### 8. Decide the Kept Comments

If "Kept for Your Call" has entries, ask CD what to do with them: keep them all (recommended), go through them, or cut them all. The question states how many there are and the report's path. To go through them, ask in batches of up to four comments per multi-select question, each option showing the location and the comment. The ones CD selects get cut.

Cut CD's picks yourself: each is a listed line CD chose, with no judgment left. Save `git diff --numstat HEAD -- <touched files>` first. Afterwards, each file's removed count must have grown by exactly its picked lines. Its added count must be unchanged, or have grown by one for each picked trailing comment, with the code on that line unchanged. Run the verify command again; a new failure goes to step 6. Record the slice's state. Remove the cut comments' rows from the report, renumber the `#` column, find every remaining row in the touched files again by its anchor, as step 7 does, and update the counts. **Headless run:** don't stop. The comments stay, and the count and the report path go under `deferred`.

Then offer to turn the follow-up lists (contradictions, gaps, reshape candidates, constraints, suppressions) into a handoff with `sdlc-handoff`. **Headless run:** take the no path and list the offer under `skipped`.

### 9. Commit

Commit only if the last verify run matched the baseline, or CD chose in step 2 to go on unverified. Otherwise a failing slice is still in the tree and no run verified the commits without it: commit nothing, and say why in the summary. **Headless run:** list it under `deferred`.

Ask CD whether to commit. The question states the number of areas and that each becomes one local commit, with nothing pushed. On a yes, make one commit per area, so a reviewer can read the cleanup area by area. Before each commit, compute each of the area's slice hashes again: on a mismatch, someone changed those files during the run, so ask CD before committing that slice. **Headless run:** leave a mismatched slice uncommitted, under `deferred`. Stage the area's slice files by name, plus the report in the first commit, since it covers every area (`git add -- <paths>`). Then commit only those paths (`git commit -m "<message>" -- <paths>`), so nothing else in the index or the tree comes along:

```text
refactor(billing): cut comments that repeat the code

31 files, 214 comment lines cut, 12 shortened. Unclear comments were kept and are
listed in docs/reviews/comment-cleanup-2026-10-23.md with the follow-ups.
```

Slices under Not Trimmed and files outside every slice stay out. Don't push and don't open a pull request. A whole-repo cleanup reads best as one pull request per area; say so in the summary. **Headless run:** commit locally without asking (local, reversible work), push nothing, and say so in `notes`.

## Examples

**One module.** `/sdlc-cleanup-comments api/app/billing` gives one slice, so there's no plan question. `backend-developer` cuts 214 lines in 31 files. The check restores 3 hunks: one `# noqa`, and two comments that explained an order another module relies on. Verify matches the baseline. The report lists 4 kept comments, 1 contradiction (`# retries 3 times` above a loop that retries 5) and 6 gaps. CD keeps all 4 and commits.

**Before a pull request.** `/sdlc-cleanup-comments main..HEAD` trims only the comments the branch added or changed. Comments the branch didn't touch are left alone, even in the same files.

## Troubleshooting

| Problem | What the skill does |
|---------|---------------------|
| Files in scope have uncommitted changes | Stops before any edit and names the files. Headless: `failed` |
| A commit range that doesn't end at `HEAD` | Stops as invalid input. Headless: `failed` |
| No way to verify | Asks CD whether to go ahead unverified or stop. Headless: `failed` |
| A trimmer changed code, not just comments | The check flags it, and the hunk goes back to its `HEAD` text |
| A reviewer's `hunks_reviewed` is missing or doesn't match the diff | Re-dispatches once, then takes those slices to the restore question |
| A cut leaves two blank lines and the formatter fails | The slice's agent deletes the stray blank line; the cut stands |
| Verify still fails after one round of fixes | Asks CD whether to restore the slice or stop with every trim uncommitted. Headless: restores nothing and commits nothing, under `deferred` |
| An agent staged or committed its edits | Staging changes nothing, since every check compares with `HEAD`. A commit moves `HEAD`, so the run stops. Headless: `failed` |
| Someone changed a slice's files during the run | The restore question says so, since restoring would discard their changes too |
| Nothing in scope to cut | Writes a short report saying so. No commit |

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'm not sure this comment carries a reason, so I'll cut it" | CD chose keep-and-list. Unclear comments stay and go on the Kept for Your Call list. |
| "This code needs a why, I'll write one" | The skill writes no comments. List the gap with any reason the history gives, and its source. |
| "The comment contradicts the code, I'll fix whichever is wrong" | Either one may be wrong. Keep the comment, list it with what the code does, and leave the call to CD. |
| "Docstrings are just comments" | Some are strings a program reads: CLI help, API docs, doctests. Check `references/machine-read-comments.md` first. |
| "That pragma reads like prose" | If a tool reads it, it's code. Never cut a suppression, directive or doc tag. |
| "Their uncommitted changes are in the way, I'll stash them" | Never. Stop and ask CD. The no-revert rule protects work you didn't make. |
| "Tests went red, so the trim broke them" | Compare with the step 2 baseline. Only a new failure is the trim's. |
| "I'll trim `[sdlc-root]/` and `.claude/` too" | Framework files are skipped: `sdlc-migrate` overwrites them. |
| "Whole repo, one commit is simpler" | One commit per area. A single huge diff is the PR bulk this skill exists to cut. |
| "The trimmer is careful, skip the check" | Self-reported trims are never self-approved. A fresh reviewer checks every cut. |
| "The reviewer came back empty, so the cuts are clean" | An empty answer isn't a clean report. A clean report states how many hunks it reviewed; anything else is a failed dispatch. |
| "I can see which cut broke the build, I'll put it back myself" | Finding it means reading code. Give the failure to the slice's agent. |
| "The formatter failed on a double blank line, so put the comment back" | Delete the stray blank line and keep the cut. A comment goes back only when a tool needed the comment itself. |
| "This slice won't pass, I'll `git restore` it" | Ask CD first. A restore discards edits in files this run didn't create. |

## Integration

- **Depends on:** a clean working tree for the files in scope; the verify command (`[sdlc-root]/process/verify-command.md`); domain agents per `[sdlc-root]/process/agent-selection.yaml`
- **Feeds into:** `sdlc-handoff` (follow-up lists, on CD's yes); `sdlc-lite-plan` (reshape candidates and constraints worth enforcing); `[sdlc-root]/process/guardrail-lifecycle.md` (a constraint worth a mechanized guard)
- **Uses:** `[sdlc-root]/knowledge/coding/comment-discipline.yaml` (the rule), `[sdlc-root]/process/headless-mode.md` (the skill's gate sites are listed in its § Integration), `[sdlc-root]/knowledge/agent-context-map.yaml`, `[sdlc-root]/knowledge/architecture/agent-orchestration-patterns.yaml` (dispatch template), `[sdlc-root]/process/manager-rule.md`, `[sdlc-root]/process/parallel-dispatch-monitoring.md`, `[sdlc-root]/process/writing-for-cd.md`, `[sdlc-root]/process/collaboration_model.md` (Tool Rule), `references/dispatch-prompts.md`, `references/machine-read-comments.md`, `references/report-template.md`
- **Complements:** `sdlc-review-code` (its reviewers apply the same rule to new diffs, so the comments trimmed here don't grow back)
- **Does NOT replace:** `sdlc-review-code` (reviews a diff for bugs and quality and fixes nothing without the fix gate), `sdlc-create-reference-doc` (writes developer docs)
- **DRY notes:** the keep and cut lists live only in `[sdlc-root]/knowledge/coding/comment-discipline.yaml`. This skill and its prompts point at that file and never restate the lists. `references/machine-read-comments.md` extends the rule's Machine-read kind with tool-specific examples.

## Additional Resources

- `references/dispatch-prompts.md` — the trimmer prompt (step 4) with its report format, the check prompt (step 5), and the fix prompt (step 6)
- `references/machine-read-comments.md` — comments a tool reads, docstrings a program reads, and the files to skip
- `references/report-template.md` — the step 7 report
