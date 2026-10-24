# SDLC Process Changelog

A living record of how the process evolves through real use. Each entry captures what changed, why, and where the change originated.

<!-- changelog-archive-pointer -->
> Older entries are in `changelog-archive/`, one file per quarter, moved there unedited once this file passed about 150 KB.

---

## Format

Each entry contains:
- **Date** — when the change was made
- **Origin** — what prompted the change (a session, audit finding, or observed friction)
- **What happened** — context leading to the change
- **Changes made** — numbered list of specific file changes
- **Rationale** — why the change improves the process

---

## Example Entry

```
## YYYY-MM-DD: [Brief Title]

**Origin:** [What prompted this — e.g., D7 planning session compliance audit, upstream sync]

**What happened:** [Context — what was observed, what problem was found]

**Changes made:**

1. **`[file path]`** — [what changed and why]
2. **`[file path]`** — [what changed and why]

**Rationale:** [Why this improves the process — the insight that led to the change]
```

---

## 2026-10-23: Review lenses reach the execution review loop

**Origin:** A `sdlc-reviewer` pass on the review-evidence change found that `process/review-lenses.md` reached only `sdlc-review-code`, `sdlc-tests-create` and `sdlc-create-reference-doc`. The review-fix loop said every reviewer "gets every applicable lens" but never named the file, and neither execution skill mentioned it. So no lens reached execution's reviews: not the overengineering, type-safety and contract lenses, and not the two-edit check, the Suppressions lens or the evidence checks added today. CD chose to close the gap.

**Changes made:**
1. **`process/review-fix-loop.md`** Step A: every code review through the loop names `review-lenses.md` in each reviewer's prompt, with the lenses that apply; plan reviews don't use them. That covers direct dispatch and the factory's `sdlc-implement` and `sdlc-revise`, which run this loop, without changing the factory's skills.
2. **`skills/sdlc-execute/SKILL.md`** and **`skills/sdlc-lite-execute/SKILL.md`**: a "Review lenses (mandatory)" paragraph beside the plan contract briefing, outside the mirrored loop block.
3. **`process/review-lenses.md`** § Lens Applicability: a row for the execution review loop.

**Rationale:** The lenses were written for every code review and reached only one of them. Reviewer prompts get longer and reviews may raise more findings, a cost CD accepted. Step A already promised every applicable lens; this makes the promise hold, strengthening an existing check: a patch.

---

## 2026-10-23: Fixing a repeated mistake structure-first, and no stock phrasing

**Origin:** The last of the pstack (cursor/plugins) items CD agreed to bring in, checked first against z-sdlc with Codex (`gpt-6-luna`, max effort). `guardrail-lifecycle.md` defined when a recurring pattern becomes a guard and how guards are kept fresh, but not which kind of fix to reach for first. `writing-for-cd.md` asked for plain language but named none of the phrasing that reads as machine-written.

**What happened:** pstack's `correct` skill, `principle-encode-lessons-in-structure` and `unslop` were the sources. Its punctuation rules (no em dashes, few colons) were left out: z-sdlc's own files use both.

**Changes made:**
1. **`process/guardrail-lifecycle.md`**: new § Choosing the Fix for a Repeated Mistake: design, then types, then a lint or CI check whose error names the fix (failing only on new instances of a common pattern, with the allowed count in `notes`), then a test, then a knowledge entry for what needs judgment. It is an order of preference, not a demand to mechanize everything. A new Preventable row in § What Qualifies lets a design or type fix be proposed at all; it is recorded with `type: other` or `type-constraint` and the edit that must now fail, which Dimension 6n tries instead of reporting it as never fired, and a recurrence counts only beyond the allowed count. Inside a review-fix loop the guard edit stays a lint, test, or change confined to the finding's diff; anything wider is a PLAN or DECIDE finding. Every new guard is shown failing on a real past occurrence. A red flag for reaching for a lint rule first.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** (6l and 6n), **`skills/sdlc-reflect/SKILL.md`**, **`process/review-fix-loop.md`** and **`skills/sdlc-review-code/SKILL.md`**: guard proposals name their fix level, the worked example proposes a tenant-scoped query type instead of a lint, and the review loops' guard edits follow the in-loop limit and the failing-occurrence proof.
3. **`process/writing-for-cd.md`** § The Rules: rule 8, no stock phrasing: inflated words, "serves as" for "is", "not just X, but Y", empty "-ing" tails, unnamed authorities, chat openers and closers, filler and stacked hedges, as prompts to rewrite rather than banned words. **`CLAUDE-SDLC.md`** § Writing for CD and **`templates/pr_description_template.md`** carry it in one line.
4. **`knowledge/provenance_log.md`**: pstack at 8b3326d, MIT, rewritten rather than copied.

**Rationale:** A rule an agent can skip is the weakest fix for a mistake agents keep making, so the order puts the ones that can't be skipped first. Stock phrasing costs CD reading time and hides whether a sentence says anything. A `sdlc-reviewer` pass caught the fix order meeting the existing guard machinery at four points (review loops, the audit's signature test, 6n's checks, and proposals that couldn't name a level); all are fixed. Both strengthen existing conventions: the fix order is a preference inside the guard contract, using `type` values the schema already has, and rule 8 names what plain language already excluded. A patch, unlike "Check before asking", which added a new action every session takes.

---

## 2026-10-23: Explaining why code is shaped as it is, and checking before asking

**Origin:** The fourth of the pstack (cursor/plugins) items CD agreed to bring in, checked first against z-sdlc with Codex (`gpt-6-luna`, max effort), plus one from the first list that CD chose to include. `sdlc-explain` already answered "why" questions from specs, plans and ADRs, and the investigation report format asked for confidence levels on hypotheses. Nothing said to start from the code's history, or to keep what a source states apart from what the agent infers. And nothing said to try a quick experiment before asking CD about a fact that could be observed.

**What happened:** pstack's `why` skill (with its epistemics and code-archaeology references) and the facts-versus-decisions line in its `poteto-mode` skill were the sources. Its investigators across chat, tickets, observability and analytics tools were left out, and so was its broader rule to proceed on reversible work without asking.

**Changes made:**
1. **`knowledge/architecture/investigation-report-format.yaml`**: new `explaining_why` key: the history commands to start from (blame, the line-range log past the last touch, log through renames, the pickaxe search, finding the pull request and its line comments, its issues, ADRs, tests), five groups for every claim (found, supported, inferred, competing, unknown), words that claim intent only beside a citation, one line per source consulted including the empty ones, a suggested answer treated as one hypothesis, and, before a change, what to keep, change and avoid, with the risks, feeding the plan rather than replacing its approval.
2. **`skills/sdlc-explain/SKILL.md`**: the "why" row points at it for code whose reason the specs, plans and ADRs don't record, and the explainer draws only what a source states. **`knowledge/agent-context-map.yaml`**: `architect` and `refactor-engineer` now load the file, so the method reaches the agents that plan and reshape code; **`disciplines/architecture.md`** lists its readers. **`knowledge/coding/comment-discipline.yaml`** § trimming.when_unsure points at it for the method.
3. **`CLAUDE-SDLC.md`** § Use AskUserQuestion for All Questions: new "Check before asking": a fact that could be observed gets a quick experiment first, one that is local and either read-only or on disposable data, within existing permissions, never against production or a shared environment (that is a gate). The result is reported instead of asked; when no safe experiment settles it, the question is asked. Decisions in the Decision Authority table stay CD's. **`process/collaboration_model.md`** § Tool Rule says the same.
4. **`knowledge/provenance_log.md`**: pstack at 8b3326d, MIT, rewritten rather than copied.

**Rationale:** An explanation that mixes what the record says with what the agent guessed reads as certain either way; separating them lets CD see which is which. Asking CD for a fact a thirty-second experiment would settle costs CD a turn and teaches nothing. A `sdlc-reviewer` pass caught a safety wording that would have let a read-only query run against production, the method not reaching planning agents, the two statements of the question rule disagreeing, and an explainer told to draw inferences; all are fixed. "Check before asking" changes when every session asks CD, a new process convention: a minor version at the next tag. The new knowledge content is a new top-level key, so migration adds it, and `sdlc-migrate` §3.3 adds the new map entries by role.

---

## 2026-10-23: Review asks for evidence: what a change is safe because of, suppressions, performance numbers

**Origin:** The third of the pstack (cursor/plugins) items CD agreed to bring in, checked first against z-sdlc with Codex (`gpt-6-luna`, max effort). Contract Safety asked whether consumers were updated but never for proof that the change is safe. Code review looked at suppressions only in shell scripts. The performance philosophy said to measure before and after but gave no way to check a reported number.

**What happened:** pstack's `blast-radius`, `principle-prove-it-works`, `benchmark-checklist`, `principle-explain-the-number`, and the suppression rule in its `comment-sicko` agent were the sources. Each landed in `process/review-lenses.md`, which reaches the reviewers of `sdlc-review-code`, `sdlc-tests-create` and `sdlc-create-reference-doc`. The execution skills' review loop doesn't name that file, so these checks don't reach it yet; that gap predates this change and is left for CD's decision.

**Changes made:**
1. **`process/review-lenses.md`** § Contract Safety: two bullets. Consumers a symbol search won't find (API JSON, stored formats and columns, wire formats, other languages reading the same bytes, flags and config keys, code several calls downstream). And the fact the change is safe because of, named with how far it is proven, from stated up to reproduced in the app; a shared-contract change that rests on a statement when a short script could settle it is an INVESTIGATE finding asking for the script, closed by its output or a test.
2. **`process/review-lenses.md`**: new § Suppressions Lens. Look up the rule each suppression the diff adds or changes silences; one over a bug-catching or security rule is a finding unless the line says why the rule is wrong here, and the fix is the code or, where the rule is wrong, a written reason. One that could name its rule and doesn't, or covers a whole file, is a finding. Style suppressions are fine; ones already in a touched file are noted, not fixed. Shell keeps its own rules, and a suppression is never reworded as prose. **`skills/sdlc-review-code/SKILL.md`**: `suppression` and `performance` join its finding categories and pattern lenses.
3. **`process/review-lenses.md`** § Performance Lens: a performance number without its evidence is a finding, with a pointer to the new questions.
4. **`knowledge/architecture/performance-optimization-philosophy.yaml`**: new `checking_a_number` key: write the claim first; seven questions (what limits it, both sides tuned alike, the arithmetic against physical limits, errors counted, at least 5 alternating runs with median and range, its share of the end-to-end path, proof the work ran); a labeled one-run ballpark; and how to report the verdict.
5. **`knowledge/provenance_log.md`**: pstack at 8b3326d, MIT, rewritten rather than copied.

**Rationale:** Each of these is evidence a reviewer can ask for instead of trusting a write-up: the one fact a change depends on, the rule a suppression hides, the run behind a number. Putting them in lenses means `sdlc-review-code` applies them without new routing. The new knowledge content is a new top-level key, so migration adds it to existing projects. A `sdlc-reviewer` pass caught the lens reach overstated (here and in the Bug-Fix entry), a suppression rule that would have pulled every old suppression in a touched file into scope, and evidence findings with no category or way to close; all are fixed. These strengthen existing review checks: a patch.

---

## 2026-10-23: The Bug-Fix Rule: bug fixes reach the method z-sdlc already has

**Origin:** The second of the pstack (cursor/plugins) items CD agreed to bring in. A Codex consult (`gpt-6-luna`, max effort) showed the method already existed: `debugging-methodology.yaml` asks for a reproduction first and a regression test that fails on the unfixed code, and `testing-paradigm.yaml` § regression_first asks for red, then green, then one commit. The gap was the path. Those files reach `code-reviewer`, `debug-specialist`, `performance-engineer` and `build-engineer`, not the developers who fix most bugs, and nothing in `sdlc-lite-plan` or the main session's rules sent a bug fix to them.

**What happened:** pstack's bug-fix playbook, `tdd`, `principle-fix-root-causes`, `principle-attack-the-premise` and `principle-test-behavior-not-implementation` were the sources. z-sdlc keeps its own rule to commit the test with the fix, rather than pstack's separate commit for the failing test.

**Changes made:**
1. **`CLAUDE-SDLC.md`**: new § Bug-Fix Rule. Reproduce the bug locally or in a test environment (against production it's a gate), watch the smallest test that would have caught it fail for the bug's reason, or use the closest runnable check with the reason a test isn't practical, fix the first wrong step rather than the symptom, commit the test with the fix, and quote the failing run in the report and the commit message. A dispatch to fix a bug says so, carries the rule, and points the agent at `fix_discipline` and `two_edit_check`, so the cues reach the developer who writes the fix without wiring two large files into every implementation dispatch.
2. **`skills/sdlc-lite-plan/SKILL.md`**: a plan rule that the phase fixing a bug starts by proving it, with the failing-then-passing test or check in its acceptance criteria and the test in the same phase as the fix.
3. **`skills/sdlc-review-code/SKILL.md`** and **`process/review-lenses.md`** § Standard Lens: the two-edit check (break the behavior and the test must fail; change only the internals and it must still pass), and a recorded failing run for a bug-fix test. The Standard Lens carries it to `sdlc-review-code`'s reviewers; the execution skills' review loop doesn't name the lens file (see the entry on review evidence). In `sdlc-review-code` a test that can't fail when the behavior breaks is `major`, and a missing failing run is `minor`.
4. **`knowledge/architecture/debugging-methodology.yaml`**: new `fix_discipline` key: the failing test must fail for the bug's reason, a guard is a fix only when the state it handles is allowed, a failure only after a restart points at saved state, the whole pattern gets fixed, and when two fixes on one assumption have failed, the assumption is written down and tested before a third. That check feeds investigation and never allows a fix past the review loop's FIX failure escalation; a headless run stops with `escalated`. Other instances of the fault outside the task's scope become follow-ups, not part of the fix. A `sdlc-reviewer` pass found those two bounds missing, the cues not reaching the developer, and a failing-run check no reviewer could verify; all are fixed.
5. **`knowledge/testing/testing-paradigm.yaml`**: new `two_edit_check` key, and `regression_first` names its one exception. **`skills/sdlc-tests-run/SKILL.md`**: before a test's third round, the assumption its two failed fixes shared is written down and tested.
6. **`knowledge/provenance_log.md`**: pstack at 8b3326d, MIT, rewritten rather than copied.

**Rationale:** The method was right but reached the wrong agents, so the fix is routing rather than a new skill. The new knowledge content sits in new top-level keys because `sdlc-migrate`'s key-level merge keeps a project's existing keys as they are and adds new ones. A new `CLAUDE-SDLC.md` rule is a new cross-skill convention, so this is a minor version at the next tag.

---

## 2026-10-23: `sdlc-develop-verify-skill`, the skill that builds the project's verify skill

**Origin:** CD agreed to bring in seven items from pstack (cursor/plugins), cross-checked first with Codex (`gpt-6-luna`, max effort) against z-sdlc, and chose to build this one first. `process/verify-command.md` § Companion has described a project-local verify skill at `.claude/skills/verify/` since 2026-09-02, but nothing created or maintained one.

**What happened:** pstack's `create-verification-skill` and `maintain-verification-skill` were the base. CD chose one skill with a maintain mode, like `sdlc-develop-agent`'s enrich mode, rather than two, and chose to wire the result into the execute skills' smoke check. Codex's consult set three limits: leave the Cursor paths and control skills, send a broken app to the bug route instead of fixing it first, and make the generated skill keep z-sdlc's side-effect rules.

**Changes made:**
1. **`skills/sdlc-develop-verify-skill/`** (new skill, with `references/safety-rules.md`, `references/generated-skill-template.md`, `references/feature-map-format.md` and `references/dispatch-prompts.md`). A hand-written verify skill can be adopted, keeping its commands and gotchas, or replaced. CREATE reads the repo, checks the app starts, writes the verify skill and a seed feature map, drives every seeded feature once (the evidence must survive cleanup), has a fresh `code-reviewer` check the whole folder, and commits that folder locally after CD's yes. MAINTAIN fixes the map's index, has the domain agents explain each feature from the source in parallel, drives every feature live, and sorts what it finds into drift, harness gaps and product bugs. It fixes the first two and reports the bugs. The orchestrator writes the generated skill and does every drive; helper scripts are code, so the agent that owns test or environment tooling writes them. Safety rules bind every drive and are copied into the generated skill: only instances the run started, every database and service URL pointed at the run's own copy, every outbound integration confirmed sandboxed, stop only what it started, secrets by name, evidence kept out of cleanup and commits. `sdlc-reviewer`'s quality gate found 8 major issues, among them: no check that the launch pointed at local data rather than a shared database, no check that mail or payments were sandboxed, a proof that drove one of the seeded features while calling the map proven, a review handed to `sdlc-review-code`, which can't review untracked files, and retry limits marked `failed` instead of `escalated`. A second round found 4 more: overrides that were set but never seen to take effect before migrations ran, a smoke check that would have skipped an app the phase itself broke, a word-for-word check with nothing to compare against (the Safety Rules now live in one reference file that the copy, the refresh and the reviewer all use), and no path for a verify skill written by hand. It also moved MAINTAIN's undo to saved text, made the folder's precondition check that it is tracked, and gave each review finding two tries. A third round found 5 more: adopting a hand-written skill would have run its commands before the target check and the mechanical check, the launch order let migrations run before targets were confirmed, a clean maintain run would have left a modified file that failed the next run's precondition (the `Verified at:` line, now dropped: MAINTAIN compares the app's own route, command and menu lists with the map instead), the review gate had no one to confirm a fix, and the undo could drop earlier fixes in the same file. All are fixed.
2. **`skills/sdlc-execute/SKILL.md`** and **`skills/sdlc-lite-execute/SKILL.md`**: the UI smoke check takes the dev server from the verify skill when there is one, and launches, health-checks and cleans up through it. When the verify skill can't launch or refuses (another instance holds the port), the check reports `skipped` with the reason, but only for a cause outside the phase; a launch the phase broke is still a smoke failure.
3. **`process/path-mappings.md`** § Project-Specific Files and **`skills/sdlc-migrate/SKILL.md`** §2.1 Step 0: the project's `.claude/skills/verify/` is never written, overwritten or removed by migration.
4. **`process/verify-command.md`** § Companion points at the skill; **`skills/sdlc-initialize/SKILL.md`** Phase 9b offers it for a project with a runnable app; **`CLAUDE-SDLC.md`** § UI Verification and **`knowledge/testing/advanced-test-patterns.yaml`** (the smoke check's auto-detect rule) name the verify skill as a source of the dev server; **`skills/sdlc-develop-skill/SKILL.md`** no longer says every skill in `.claude/skills/` is framework-installed, and sends the verify skill here; **`process/skill-agent-review.md`** and **`agents/sdlc-reviewer.md`** exempt the lean generated skill from the trigger phrases and the section requirements.
5. **`process/commands.md`** (Testing), **`process/headless-mode.md`** § Integration (the skill's gate sites), **`skeleton/manifest.json`**, **`knowledge/provenance_log.md`** (pstack at 8b3326d, MIT, rewritten rather than copied).

**Rationale:** The verify command says whether the checks pass; nothing gave agents a proven way to see a change work in the running app, so each session rediscovered how to launch it. A recipe is only worth trusting once it has been run, so CREATE runs it before handing it over, and MAINTAIN drives every feature rather than trusting the map. A new skill is a minor version at the next tag.

---

## 2026-10-23: The comment rule, and `sdlc-cleanup-comments`

**Origin:** CD directive, after reviewing what to adopt from pstack (cursor/plugins). Comments should explain what the code can't show at a glance, and comments that only repeat the code add bulk to every pull request. CD asked for a skill that trims an existing codebase, and for the same rule to govern how code gets written.

**What happened:** z-sdlc had one bullet on this ("comments explaining obvious code", in the overengineering lens) and no rule for writing comments. pstack's `no-comments` skill and its `comment-sicko` agent were the base. CD set three behaviors that differ from pstack: an unclear comment is kept and listed rather than cut; complex code with no explanation is listed, with any reason the history gives, and the skill writes no comments; and the skill keeps the `sdlc-` prefix.

**Changes made:**
1. **`knowledge/coding/comment-discipline.yaml`** (new): the single rule. What a comment is for and its two readers (an agent mid-task, a developer new to the code), what to keep, cut and shorten, reshaping our own surprises before commenting them, trimming rules (when unsure, contradictions, constraints, vague TODOs), writing rules, and a review checklist. A project lists its own tool-read comments in a `project_machine_read` key it adds, which migration keeps.
2. **`skills/sdlc-cleanup-comments/`** (new skill, with `references/dispatch-prompts.md`, `references/machine-read-comments.md` and `references/report-template.md`): scope (whole repo, paths, or a commit range), a verify baseline, disjoint slices per domain agent, trimming that only deletes or shortens comments, a single check by a fresh `code-reviewer` whose every correction restores `HEAD` text, verification against the baseline, a report under `docs/reviews/`, CD's call on kept comments, and one local commit per area. Machine-read comments, docstrings a program reads, generated and vendored code, applied migrations and framework files are never touched. Each change the orchestrator makes itself has a mechanical check that stands as its review, against a snapshot saved before the change. A slice hash taken as each agent returns flags files someone else changed later in the run; it can't see changes made while an agent was working. `sdlc-reviewer`'s quality gate took several rounds. Among what it caught: report locations that went stale after put-backs (entries now carry an anchor), a diagnosis the orchestrator would have done itself (the slice's agent does it now), a review check that could never pass, a trimmer barred from removing the blank line its own cut left, and a docstring rule that contradicted the cut list. A whole-slice restore asks CD every time, because it discards edits in files the run didn't create.
3. **`knowledge/agent-context-map.yaml`**: the rule is wired to every code-writing role the map has, and `code-reviewer`. Four code-writing roles in `agent-selection.yaml` (`domain-integration-engineer`, `realtime-systems-engineer`, `devops-engineer`, `systems-engineer`) have no map entry at all, so the Comment Rule in `CLAUDE-SDLC.md` is what reaches them.
4. **`CLAUDE-SDLC.md`**: new § Comment Rule, so every project's main session writes comments by the same rule.
5. **`process/review-lenses.md`**: the overengineering lens's comment bullet now names what to flag and points at the rule.
6. **`process/commands.md`**, **`process/headless-mode.md`** § Integration (the skill's gate sites), **`knowledge/coding/README.md`**, **`skeleton/manifest.json`**, **`knowledge/provenance_log.md`** (pstack at 8b3326d, MIT, rewritten rather than copied).
7. **`skills/sdlc-migrate/SKILL.md`** §1.3 and §2.1: skill reference files (`skills/*/references/*`, manifest-listed) are direct-copied to `.claude/skills/*/references/`, except a dual-audience skill's, which merge additively. Until now only `sdlc-audit`'s references had a rule, so a migration had no stated way to install the references of this skill, `sdlc-migrate`, `sdlc-develop-agent`, `sdlc-playbook-generate` or `sdlc-port-opencode`.
8. **A Codex cross-check** (`gpt-6-luna`, max effort; `gpt-6-astra` and `gpt-6.1-sol` aren't available on the ChatGPT-account login) found what the internal rounds missed, and all of it is fixed but one point. Every diff and slice hash compared the files with the index, so a trimmer that staged its edits would have hidden them from the check, and `git restore` would have put back the staged trims: every check now compares with `HEAD`, the restore is `git restore --source=HEAD --staged --worktree`, agents don't stage or commit, and the run stops if `HEAD` moves. A slice left failing in the tree no longer lets the other slices commit, since no verify run covered them without it: step 9 commits only after a verify that matched the baseline. A commit takes only its own paths (`git commit -- <paths>`), with the report named in the first. Step 6's fix gets its own prompt, which carries the headless notice. The context-map consult and the Comment Rule's pointer to the knowledge file now use the phrasing contract's forms, which the adapter transforms. One point stays as it was, by CD's decision: the skill's three mechanical self-applied changes take a diff check instead of § Mandatory Review's domain-agent review. The skill states that departure in its Manager Rule section, and `manager-rule.md` gets no new exception.

**Rationale:** One rule, used three ways: when agents write code, when reviewers read a diff, and when the skill trims existing code. Keeping it in a single knowledge file means the three can't drift apart. Keeping unclear comments costs a little bulk. Cutting them would lose reasons nobody wrote down anywhere else. A new skill is a minor version at the next tag.

---

## 2026-10-20: A revision's gate stop that didn't run

**Origin:** The first revision to stop at a gate, in the incubator. It stopped before its plan's first gate, and its comment said so. But the writer job that posts the gate tracker and asks for the gate run was skipped. It was the PR's last revision, and a re-run would have run the agent again.

**What happened:** The job's condition had no status function, so GitHub added `success()`. That reads every earlier job, and the fixtures job before the agent's is skipped in every project with no fixtures. The incubator fixed the condition and added a workflow policy rule that would have caught it. It also added a workflow CD dispatches to do that job's work for a PR whose last revision stopped before a gate. The code comes in with the next import.

**Changes made:**
1. **`process/factory.md`:** D4 rule 17 says what that workflow checks: the App's last revision comment stopped before the plan's next gate, and the branch's last push is the App's push of the PR's head, from before that comment. Both are GitHub's own records, and it runs no agent and counts no revision.

**Rationale:** A gate stop that didn't run would otherwise leave a PR stuck once its revisions are used up. The recovery takes nothing a dispatch passes in on trust.

---

## 2026-10-20: The factory imported from the incubator (946ddda..9e56842): a revision's gate stop

**Origin:** The incubator merged the factory code for the entry below.

**What happened:** The import brought in 11 bundle files, one of them new (`gate_stop.sh`). The skill and process doc were already in sync, since `--to-incubator` had copied them in. The incubator's own `README.md` seed changed, in its § Production gates and § Revise. The bundle's generic seed has neither section, so it needs nothing. Both proofs pass: the incubator takes the bundle unchanged, and so does an empty project. The empty-project proof had caught a bug before the merge: without a production runner (no receipt key), the gate job would have failed for every revision of a PR that executes a plan. The incubator fixed it before merging.

**Changes made:**
1. **`bundles/factory/tree/`:** `revise_gate.sh` (the plan, bound to the issue's reserved ID, and its next gate), `gate_stop.sh` (new: the stop-at-gate job), `agent_job.sh`, `implement_guard.py`, `revise.schema.json`, the `factory-revise`, `factory-gate-request` and `factory-implement` templates, and their tests.
2. **`.claude/skills/zsdlc-import-factory/import.json`:** `last_import` is `9e56842`.
3. **`bundles/factory/tree/tests/test_revise_gate.py`:** z-sdlc's own fix. The imported test hard-coded the incubator App's login in its fake comments, which the bundle never names (its seeds and tests use placeholders). The import's patterns didn't catch it. The test now reads the login from `factory.json`, as it reads the App's user ID. The incubator has the same change in review, so the next import should show the two in sync.

**Rationale:** The factory's code comes only from its incubator. This brings in the code the skill change below relies on: without `gate` in the revise context, a revision never stops at a gate.

---

## 2026-10-20: A revision reaches a production gate the way execution does

**Origin:** An execution PR in the incubator. Execution built the phase before the plan's first gate, then stopped with two major findings that were CD's decisions. Its result was `escalated`. CD answered with Request-changes reviews, and two revisions ran. Even after a clean revision, nothing could take the PR to its gate:
- only execute's report job posts the gate tracker and asks for the gate run, and only for `awaiting-approval`;
- the revise workflow had no gate handling at all;
- the gate request reads its plan from the tracker;
- a continued execution needs a done gate at the PR's head;
- and the gate code trusts only the App's comments, so CD can't post a tracker by hand.

**Changes made:**
1. **`skills/sdlc-revise/SKILL.md`:**
   - The context gives the plan an execution PR executes (`plan`) and its next gate (`gate`). § 7 adds the result's `gate` field and status `awaiting-approval`.
   - New: § "An execution PR at a production gate". A revision may stop before the context's `gate`, and no other, when the work before it is done, no critical or major finding is open, and no response is `needs-your-call`. Otherwise `gate` stays empty. A revision never continues execution.
   - Edge cases and red flags for both.
2. **`process/factory.md`:** D4 rule 17 says how a revision reaches a gate: the plan it finds and how that plan is bound to the issue, which gate is next, what the stop requires, and what the writer job does. Execution and a revision ask for the gate on the commit they pushed. `factory:gate` is now set by execute or revise.
3. **`process/headless-mode.md`:** the gate-site list includes the revise skill's gate stop.

**The factory code** changes in the incubator first, and comes into `bundles/factory/tree/` with the next import:
- `revise_gate.sh` finds the plan: the one the PR's gate tracker names, or else the sibling of the one result doc the PR adds, if that plan is on the default branch and its deliverable ID is the one the plan stage reserved on the issue. It also finds that plan's next gate the PR hasn't passed, by the broker's signed results.
- `agent_job.sh` puts the plan and the gate in the revise context.
- `revise.schema.json` gets `gate` and `awaiting-approval`; `implement_guard.py` checks them, and refuses any gate but the next one.
- `factory-revise.yml` gets a `stop-at-gate` job, which runs the new `gate_stop.sh`. It does what execute's report job does at a gate stop: posts the tracker, sets `factory:gate` and asks for the gate run. It's a separate job so that re-running it never posts the revision comment (and its revision marker) twice.
- `factory-gate-request.yml` takes the commit the factory pushed (`head`) and builds no request if the branch has moved since. Implement and revise both pass it.
- `gates.py` is unchanged. It's part of the operations package the broker hashes, so changing it would make every gate refuse until the host's setup re-runs.

A review of the incubator's PR found the first version steerable: with no tracker, a result doc named after another deliverable's plan on `main` would have chosen that plan's gates. It also found that a push after the revision's could have gone under the gate request, and that only the gate ID's shape was checked. The ID binding, the next-gate rule and the head binding fix those.

The skill is safe to deliver before the code: without `gate` in the context, a revision never stops at a gate.

**Left open:**
- Execute's result can't be `escalated` and name the gate it stopped before, so an escalated stop gets no tracker. (An `awaiting-approval` result with a major open is refused too, which lost one run's publish.)
- An execution that escalated part-way through a phase has no route but CD's own push.

---

## 2026-10-16: The `open` guard's limits are on record

**Origin:** The pilot project's review of v2.1.5. The workflow policy's guard against `open` in a sandbox verdict outside the planning probe is a match on the word. A quoted, split, variable or line-continued `open`, or the checker run through a variable, gets past it. A bare ` open` is refused.

**Decision:** Leave the guard as it is, and record the limit. D2 rule 6 already says the static workflow check isn't a security control against a deliberate edit, and that the boundary is code-owner review of workflow changes. The guard is there for the accident, which it catches. The reviewer's suggested allowlist of the strict verdict's whole line would also fall to a deliberate edit, such as a renamed step or a shell function. The structural answer stays the one already listed: every agent run through one reusable workflow, checked at runtime.

**Changes made:**
1. **`process/factory.md`:** D2's Leaves open, "Gaps in the static workflow check", lists it.

---

## 2026-10-16: Only the planning probe may be judged by the open internet; no socket may answer the sandbox

**Origin:** The pilot project's review of v2.1.4. Two findings, neither blocking:
- **Major:** nothing held `bash-sandbox` to the allowlist. Adding `open` to its verdict, in the template and the rendered workflow together, would pass `render.py --check` and the workflow policy, leaving only CODEOWNERS review. The sandbox would still enforce its allowlist, but smoke would stop proving it.
- **Minor, from before v2.1.4:** the probe reports every Unix socket it finds, but the verdict failed only on the Docker socket. Any other socket that answered would pass silently.

**Changes made:**
1. **`workflow_policy.py`:** a sandbox probe's verdict may pass `open` only in `PLANNING_PROBES` (the planning stages' `planning-sandbox`). The check runs in every project's CI over its actual workflows.
2. **`sandbox_check.py`:** from inside the sandbox, any Unix socket the probe finds that accepts a connection fails the verdict, whatever it serves. The sandbox refuses Unix sockets, so no allowlist is needed. The control, outside the sandbox, still reaches the job's own sockets.
3. **Tests:**
   - `test_planning_probe.py`: the rendered `bash-sandbox` verdict passes no `open` and `planning-sandbox`'s does, and the policy refuses `open` in `bash-sandbox`;
   - `test_sandbox_check.py`: a socket that answers fails the agent's verdict and not the control's.
4. **`process/factory.md`:** D2 rule 5 lists the socket rule, and says only the planning probe may use `open`.

**Checked against live runs:** the incubator's passing strict-tier and planning-tier probe output (2026-10-16) both pass under the new rules. Every socket they found from inside the sandbox was blocked: the Docker socket, the runtime's own sockets and the test services' sockets.

---

## 2026-10-15: The planning probe judges the planning tier's open internet

**Origin:** The new `planning-sandbox` smoke job's first live run, in the incubator (2026-10-16, its planning tier, with a production database):
- **What held:** the planning boundary itself. The unsandboxed control found the reader password in `pgbouncer.ini`, which proves the probe looks where the password lives. The sandboxed agent found no secret, reached the test services and the planning database through the proxy, was refused the Docker socket, and had no route around the proxy. The isolation step passed with the database as its one exception.
- **What failed:** the verdict, on "host outside the allowlist reachable" for `example.com` and `api.github.com`.

**What happened:** The check held the planning sandbox to the strict tier's network allowlist. But the planning sandbox's `WebFetch(domain:*)` permission opens its proxy to every host, which is D3 rule 5's open internet for planning, by design. Its sandbox settings' own `allowedDomains` are only `localhost`, which hid that.

**Changes made:**
1. **`sandbox_check.py`:** the agent mode takes the tier's network rule as a last argument: `allowlist` (the default, the strict tier's) or `open` (the planning tier's). Under `open`, any host may answer through the proxy, but nothing may bypass it (no direct connection, no DNS). An unknown rule fails.
2. **`templates/factory-smoke.yml`:** `planning-sandbox` passes `open`.
3. **`tests/test_sandbox_check.py`:** the open internet still goes through the proxy: a host reached without it fails under either rule.
4. **`process/factory.md`:** D2 rule 5's planning bullet says what the planning tier's network is.

**Checked against the live run:** that run's control and agent output, judged again: `allowlist` gives exactly those two failures, `open` passes, and the control passes.

**Rationale:** The probe proves what the design says, D3 rule 5 included. A check stricter than the design fails for the wrong reason, and teaches people to ignore its failures.

---

## 2026-10-15: The public-content scan stops a push

**Origin:** This release's first push. Check 6 found an added line naming the incubator, but its last command was an `echo`, so it exited 0. The push chained after it ran, and the release went out with the line. CD had it re-cut.

**Changes made:**
1. **`CLAUDE.md`** (this repository's), check 6: the scan exits non-zero on a missing names file, a missing `origin/master`, a match or a grep error, and prints `check 6: clean` only when there's none. A push chained after it stops before it runs.
2. **`.claude/skills/zsdlc-import-factory/SKILL.md`:** step 3's line, which this release changed, says "the incubator".

**Rationale:** A check whose exit status always says "pass" depends on someone reading its output, which a chained command never does.

---

## 2026-10-15: Smoke probes the planning stages' sandbox

**Origin:** The pilot project's review after its move to v2.1.2. Its plan and revise-doc stages grant Bash (`plan-tools.args`) under `planning-sandbox.settings.json` on the planning runners, while all of `factory-smoke`'s jobs ran on the strict runners. D2 rule 5 ("Before any stage gets Bash, smoke carries that stage's sandbox probe") would then keep Bash from both stages even after a green smoke. CD asked for the fix, shipped as a patch (v2.1.3).

**What happened:**
- **The planning job differs from the strict one.** The planning sandbox's settings are implement's plus a WebFetch permission, but its job doesn't match the strict job the probe ran in:
  - pgbouncer holds the read-only database login's password on the job container's loopback;
  - the service credential slots are wired in;
  - the runners run as their own user, behind a firewall with the database exception.

  None of that had been probed. The incubator had run both stages that way since the planning tier began.
- **Two doc errors:**
  - D2 rule 6 pointed to a "Leaves open" list that `factory.md` didn't have;
  - the design record said smoke probed every stage's tools but improve's, which plan's and revise-doc's weren't.

**Changes made:**
1. **`templates/factory-smoke.yml`:** a ninth job, `planning-sandbox`, on the planning runners with the planning environment. It runs the planning stages' setup:
   - the profile's test services, and pgbouncer with the reader password when `planning.json` names a database;
   - the sandbox settings `services.py` builds for the plan stage, with their service slots in the agent step's environment.

   It then runs the sandbox probe:
   - the probe looks for the reader password and the service credentials too, besides the tokens and the canary;
   - it must reach the planning database through the proxy (`planning-db`, beside the profile's services);
   - the transcript is checked for each raw value.

   The isolation probes run from that tier as well, with the planning database (`planning.json`'s host and port) as their one exception.
2. **`workflow_policy.py`:**
   - `PLANNING_PROBES` lets that one job, and no other outside the planning workflows, use the planning runners, environment and service slots;
   - the job must run on the planning runners.
3. **`tests/test_planning_probe.py`** (new):
   - the job runs where the planning stages run, and the policy admits it;
   - no other smoke job may use the planning tier, and the probe may not leave it;
   - `plan-tools.args` is `implement-tools.args` (which smoke probes) plus WebFetch, with the same deny rules, so the planning tool policy needs no probe of its own, as with improve's.
4. **`process/factory.md`:**
   - D2 rule 5 names the planning probe and the two pinned tool policies;
   - D2 gains its Leaves open list (the static check's known gaps and the rest), which rule 6 points to.
5. **`.claude/skills/zsdlc-import-factory/`:**
   - `import.json` records the incubator's commit that took v2.1.2 (`--apply`; nothing copied);
   - `SKILL.md` step 3 says to record each hand-back's commit that way. Until then, the next change here to a handed-back file reads as changed on both sides, and the proof installs the incubator's copy without it, which is how this release's proof first failed.

**Upgrading:** take the bundle code, re-render, and run `factory-smoke`. All nine jobs must pass before the plan, spec and revise-doc stages are relied on. The planning job needs the planning environment's secrets as the planning stages have them, and `planning.json`'s database host written as in `smoke.host_probes`.

**Rationale:** A probe proves the boundary in the job it ran in. The planning stages hold a credential and a network path the strict job never had, so their sandbox is proven where they run.

---

## 2026-10-15: The sandbox probe checks the profile's own test services

**Origin:** The pilot project's first `factory-smoke` run on z-sdlc v2.1.0 (2026-10-15): 7 of 8 jobs passed, and `bash-sandbox` failed in its control probe with "test service unreachable: redis". D2 rule 5 lets no stage have Bash until that job passes, so the pilot project's agent workflows stay disabled until it does.

**What happened:** `sandbox_probe.py` probed Postgres (5432) and Redis (6379), and `sandbox_check.py` required both (`SERVICE_SOCKETS`). Those are the `python-node` profile's services. The `dotnet-node` profile starts Postgres alone, so its control could never pass. The probe's docstring already described a services list beside its hash file, which was never built. Unchanged since v2.0.0.

**Changes made:**
1. **`bundles/factory/tree/profiles/*/services`** (new, a profile's sixth file): its test services, `<label> <port>` a line. `python-node`: `db 5432`, `redis 6379`; `dotnet-node`: `db 5432`.
2. **`sandbox_probe.py`:**
   - probes the services listed in the `services` file beside its hash file, so the agent's command (which the job compares word for word) is unchanged;
   - reports `localsvc none` for a profile with none, and `localsvc-list unreadable` for a missing or malformed list, which fails the required-line check.
3. **`sandbox_check.py`:**
   - takes the profile's frozen `services` file as its last argument and requires each listed service to answer;
   - a missing or malformed file is a failure;
   - the Docker socket must still refuse.
4. **`templates/factory-smoke.yml`:**
   - the check reads the copy `agent_job.sh freeze` made of the profile, out of the agent's reach;
   - the probe gets its own copy beside its hash file.
5. **`templates/factory-implement.yml`, `factory-revise.yml`:** a comment no longer says the test services are Postgres and Redis.
6. **`bundles/factory/tree/tests/test_sandbox_check.py`** (new):
   - a profile without Redis passes on its Postgres;
   - a listed service must answer, and the Docker socket must not;
   - a missing or malformed list fails;
   - the probe and the check parse a list alike;
   - every profile's list names only ports its `with-test-services` forwards.

   `test_agent_job.py`'s freeze test lists `services` among the profile files frozen for the check.
7. **`process/factory.md`:** a profile has six files, `services` among them.

**Upgrading:** take the bundle code, re-render (`render.py`), and run `factory-smoke`. A project with its own profile adds a `services` file listing what its `test-services.sh` starts.

**Rationale:** The services a probe requires belong to the profile that starts them. A fixed list is right for one stack and impossible for the next.

---

## 2026-10-15: The factory owns its labels

**Origin:** The incubator's compliance audit after its migration to v2.1.0 flagged all 13 of the factory's `factory:*` labels as label sprawl. CD asked how two z-sdlc bundles could disagree, and for the best fix, shipped as a patch (CD, 2026-10-15: v2.1.1).

**What happened:**
- **The two rules:** github-provenance (2026-09-02) made its config block "the complete allowed label set … a label not listed there is definitionally sprawl", and its audit (§ 10h) requires the repository's labels to equal that set exactly. Then, its checkpoint skills were z-sdlc's only automated label writers. The factory bundle (2026-10-12) brought its own 13 labels, created by `bootstrap.py` and documented in `process/factory.md` § Labels.
- **Nothing reconciled them:** neither bundle's docs named the other, the factory import's proof installs the factory alone, the release reviews were scoped to the factory's code, and this repository's checks don't look at bundles together. Every project running both bundles gets 13 `minor` findings.

**Changes made:**
1. **`bundles/github-provenance/fragments/sdlc-compliance-auditor.md` § 10h:**
   - when the project runs the factory (`.github/factory/factory.json`: the bundle installed, or the factory's incubator), `factory:` labels are the factory's, not the config block's;
   - they're checked against `process/factory.md` § Labels, so a missing one, or a `factory:` label the table doesn't list, is still drift;
   - a config block that lists them is drift too.
2. **`process/github-checkpoints.md` § Labels:** labels another bundle owns are outside the config block's set, and the factory's are the case today.
3. **`process/factory.md` § Labels:** the factory owns the `factory:` namespace. A project with github-provenance keeps the labels out of its checkpoint config, and a new label goes in the table and `LABELS` together.
4. **`bundles/factory/tree/bootstrap.py`:** `LABEL_PREFIX`. A `factory:` label it doesn't define is reported (a typo, or one a removed stage left), never removed, since that would strip it from every issue. This covers projects with the factory but no github-provenance audit. Test: `test_a_label_in_the_factorys_namespace_it_doesnt_define_is_reported_never_removed`.
5. **`tests/test_factory_labels.py`** (new): the factory's table and `bootstrap.py`'s `LABELS` name the same labels, so the audit's reference can't drift from the code.
6. **`CLAUDE.md`** (this repository's): bundles share a project. A bundle that adds something a project's GitHub or config holds is checked against every other bundle's rules and audits.

**Upgrading:** a project running both bundles takes this with its next migration: the auditor's fragment and the process docs refresh, and the 13 findings go. Leave the factory's labels out of the config block, and take out any listed there by hand.

**Rationale:**
- **Ownership by namespace, not a shared list:** a list of the factory's labels in the config would be a second copy that drifts the first time the factory adds one.
- **Why the factory is named directly:** a manifest field declaring the namespace wouldn't reach the incubator, which runs the factory without installing the bundle, and the factory is the only bundle that creates labels. A generic declaration waits for a second one.

---

## 2026-10-15: The import's last commit, after the incubator's history rewrite

**Origin:** The incubator rewrote its own history after its production move. The commit `import.json` recorded as the last import no longer exists there, so the next import would have stopped.

**What happened:** The rewrite changed no file under the incubator's `.github/factory/`. The incubator then committed this release's factory code. Its import report showed all 103 bundle files in sync. Its two own seeds changed, in its database host and a note on its runner host, and the bundle's generic seeds already cover both.

**Changes made:**
1. **`.claude/skills/zsdlc-import-factory/import.json`:** `last_import` is the incubator's commit that took this release's factory code, applied with the import's own `--apply`.

**Rationale:** An import compares three ways against its last commit. A rewritten history has to give it one that exists, with the same files.

---

## 2026-10-15: The factory imported from the incubator (07d9441..3f43e26); optional seed settings

**Origin:** The incubator's migration to v2.1.0. Before z-sdlc's factory changes are copied into the incubator (`--to-incubator`), the import brings the incubator's own since the last import (its production move, 2026-10-14).

**What happened:**
- **One shared file changed:** the incubator's production move changed one shared file, a comment in `templates/factory-smoke.yml`. Its other changes are in its production tier (excluded) and its own seeds: `README.md` and `host/host.conf`, both naming its hosts, so the bundle's generic seeds need nothing.
- **The import refused to apply:** the bundle's `factory.json` seed has the pilot project's optional settings (`ci`, `fixtures`, `policy`, `runners.ci`), and the incubator, which uses none of them, doesn't. The import read each as "removed there?", a fix-first item.

**Changes made:**
1. **`bundles/factory/tree/templates/factory-smoke.yml`:** imported. The host probes also cover the production machine's addresses.
2. **`.claude/skills/zsdlc-import-factory/import.json`:**
   - `optional_settings` names the seed settings the bundle's code reads only when they're there, which the incubator may leave out;
   - one the incubator has is still compared;
   - `last_import` is `3f43e26`.
3. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`, `SKILL.md`, `tests/test_import_factory.py`:** the rule, its documentation, and a test that a listed setting is no finding while an unlisted one still is.

**Rationale:** A seed setting that's optional for a project is optional for the incubator too. Flagging it on every import would hide a real removal among false ones.

---

## 2026-10-15: The factory's tests pass in a project with no CI tier

**Origin:** The incubator's migration to v2.1.0. With v2.1.0's factory code in the incubator's tree, two of the bundle's tests failed there, and the import's proof hadn't caught it.

**What happened:**
- **The tests:** two `test_bootstrap.py` tests, a CI tier's group and one restricted to workflows, read the project's own `factory.json` and assumed it names a CI tier (`runners.ci`). The bundle's seed does, so a new project passes. A project upgrading from v2.0.0 keeps its own `factory.json` (a migration never changes a seed), and the incubator's has no CI tier, so both tests failed. Every project upgrading from v2.0.0 without one would see the same.
- **The proof:** the import's proof ran the tests only in an empty project made from the seeds, never in the incubator with its own settings.

**Changes made:**
1. **`bundles/factory/tree/tests/test_bootstrap.py`:** the CI-tier tests give their test project a CI tier themselves.
2. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`, `SKILL.md`:** the proof's first step, in a clone of the incubator, also runs the factory's tests there. Without the fix above, it fails on those two tests.

**Rationale:** The seed is what a new project starts from, not what an existing one has. A test that reads the project's settings must hold for every settings file a migration leaves in place.

---

## 2026-10-15: The runner audit's repository admits no App that can write

**Origin:** The pilot project, setting up its runner audit after v2.1.0. An AI coding assistant's GitHub App was installed on all of its organization's repositories, with workflows, contents, issues and actions write.

**What happened:** Enablement step 12 and `runner_audit.py` reasoned that no App can change the audit, because neither of the factory's Apps has the workflows permission. Any other App installed on the audit's repository breaks that, an organization-wide installation included. Such an App could rewrite the expected state or the audit, close its alarm issues, or disable the workflow.

**Changes made:**
1. **`process/factory.md`:** Enablement step 12:
   - the premise holds only while no other App that can write is installed on the audit's repository;
   - setup step 2 says to check the repository's installed Apps, counting organization-wide ones, and to narrow any App that can write workflows, contents, issues or actions to selected repositories, without this one.
2. **`bundles/factory/tree/runner_audit.py`:** the docstring and the generated workflow's header say the same.

**Rationale:** The audit's guarantee rests on who can change one file. Every App installed on its repository is someone.

---

## 2026-10-15: The release review's second round

**Origin:** The pilot project's second review of this release (three fresh reviewers: code and tests, architecture, host operations) closed the first round's three blockers and found three more, with cheap hardening around them.

**What happened:**
- **The audit missed a group open to every private repository.** A runner group's visibility is `selected`, `all` or `private`, and the audit flagged only `all`. It records repositories only for a `selected` group, so a `private` group admitted the audit's own (private) repository unseen.
- **Upgrading a pre-release CI tier could kill a job.** Setup moved the old `/run` state's records into the new state before it installed the slots' new settings, minutes earlier, while the image built. A cycle starting in that window wrote its record to the old place, so `retire` found nothing there and answered idle. A re-run after an abort could also delete a live record.
- **The upgrade notes missed what stops a v2.0.0 host's first run:**
  - every tier's claim;
  - the label refusal;
  - IPv6;
  - `TasksMax` at the defaults;
  - a pre-release audit's expected state.

**Changes made:**
1. **`bundles/factory/tree/runner_audit.py`:**
   - any visibility but `selected` is drift, whatever the expected state says;
   - the audit's own repository is matched without case;
   - `check` refuses to run (2) without `GITHUB_REPOSITORY`, which a hand run would otherwise skip;
   - an empty token is a clean 2.
2. **`bundles/factory/tree/host/ci_launcher.py`:**
   - **`retire`:**
     - asks GitHub about each registration the slot holds (its record, its leftovers, and any record on the old `/run` state) before removing an idle one, so it no longer depends on GitHub refusing to remove a busy runner;
     - treats a record that changes meanwhile, or a missing state directory, as not idle;
     - says why it isn't restarting a slot.
   - **A leftover GitHub no longer has** is dropped rather than kept forever.
   - **The tier's group** must be the only one with its name.
3. **`bundles/factory/tree/host/setup-ci.sh`:** the old state's records move in as leftovers, never over a current record, only once the slots' new settings are in place, just before the restarts.
4. **`bundles/factory/tree/host/setup.sh`:** the usage line's first run names the tier too, as the claim requires.
5. **Tests:**
   - `private` visibility;
   - case;
   - no `GITHUB_REPOSITORY`;
   - `retire` asking first, a busy old-state record, a new record meanwhile, a missing state directory;
   - a leftover GitHub no longer has;
   - the old state's default path;
   - two groups with the tier's name;
   - the carry-over's order in `setup-ci.sh`.
6. **`process/factory.md`:**
   - step 12 says `private` is as open as `all`, and lists `inherited` among the compared fields;
   - the audit log is GitHub Enterprise Cloud's, and isn't read yet;
   - step 10 says setup's restart asks GitHub first.
7. **This changelog:**
   - "Upgrading a project from v2.0.0" is rewritten: every tier's claim and label rule, IPv6, self-update, the planning database, and the CI tier and audit framed as a pre-release host's;
   - item 12 no longer names a `setup-ci.sh` label check;
   - Enterprise Cloud is named the same way throughout.
8. **`CLAUDE.md`:**
   - check 6 fails closed when the names file is missing or empty, or a scan errors;
   - pushes name `master` and the tag, never `--all`;
   - "no absolute home path".
9. **`docs/current_work/ideas/factory-ci-tier-follow-ups_handoff.md`** (new): the minors that follow the tag.
10. **The third round** (ship; no critical or major findings), before the tag:
    - **`ci_launcher.py`:** a record on the old `/run` state (tmpfs) that GitHub won't remove yet is written into the state as a leftover, then removed, rather than renamed across filesystems, which failed (`EXDEV`) on a real host. The test now refuses a rename between directories, as a real host does.
    - **The follow-ups:**
      - added: a renamed group read as one gone and one new; a sunset for the pre-release migration code; a loose old-state directory skipped silently; a 404 from the wrong organization read as "gone";
      - corrected: where the label lists live, and that the firewall check already fingerprints `nft -j`'s JSON;
      - dropped: `read < <(python3 …)` failing silently (those sites stop setup).
    - **`CLAUDE.md` check 6:** fails when `origin/master` can't be read, which the scans' exits don't show.
    - **The upgrade notes:** why the release is minor, the apt refusal, and the planning tier's error without `PLANNING_DB_HOST`.

**Rationale:** Both blockers were the same mistake as the first round's: a check that passes when it can't see. An unknown visibility or a record in the wrong place now counts as the unsafe answer.

---

## 2026-10-15: z-sdlc names no private project, host or path

**Origin:** CD (2026-10-15), preparing this release: z-sdlc is public, and its unpushed commits named the pilot project, two of the organization's machines and a tailnet address.

**What happened:** The import's `specific` patterns keep hosts and home paths out of code imported from the incubator, but nothing checked z-sdlc's own changelog, docs, tests and commit messages. The pilot project's name, and the names of the runner host and the production machine, had spread through this release's entries.

**Changes made:**
1. **`CLAUDE.md`** (this repository's):
   - z-sdlc's commits, their messages and the files they change name no project of the organization's, no host, no home path and no private address;
   - consistency check 6 scans what's unpushed before every push, against names kept in an untracked, git-ignored `.claude/private-names.txt`.
2. **This release's commits**, before their first push:
   - reworded: "the pilot project", "the runner host", "the production machine", documentation addresses in tests;
   - the pilot project's intake note is renamed `pilot-v2-migration-upstream-issues_handoff.md`;
   - published history is left as it is.
3. **`CLAUDE.md`, `.claude/skills/zsdlc-import-factory/SKILL.md`:** "the pilot project first" for the pilot rule.

**Rationale:** A public framework's history is permanent. Naming a private project or a machine in it tells anyone how the organization is built, and the only cheap moment to keep it out is before the push.

---

## 2026-10-14: CI tier runners take their jobs (a label hotfix)

**Origin:** The pilot project's second first-run attempt on its runner host, with the log-driver hotfix (the entry below). Setup passed, the check was ok, and both JIT runners came online in the CI group, but neither took a queued job.

**What happened:**
- The runners' labels were only `factory-ci`.
- A `config.sh` registration gets `self-hosted`, plus the OS and architecture, by itself. `generate-jitconfig` gives a runner only the labels it's passed.
- Every job on the tier asks for `[self-hosted, factory-ci]`, and the workflow policy requires exactly that.
- The pilot project confirmed with the tier's App that GitHub accepts `self-hosted` in a JIT label list.

**Changes made:**
1. **`bundles/factory/tree/host/ci_launcher.py`** — `jit_labels()` registers each runner with `self-hosted` first, then the tier's labels (without a second `self-hosted`).
2. **`bundles/factory/tree/tests/test_ci_launcher.py`** — the JIT request's labels are `["self-hosted", "factory-ci"]`, and `self-hosted` appears once however the settings list it.

**Rationale:** The launcher's tests fake GitHub, so a label set GitHub routes differently can only show on a real tier. The label list is now pinned to what the jobs ask for.

---

## 2026-10-14: CI tier job containers start (a log-driver hotfix)

**Origin:** The pilot project's first `TIER=ci` setup on its runner host at `b73589a` (2026-10-14). Steps 1–7 passed, but step 8's check tripped: "the check's listener container didn't start".

**What happened:** On Docker 29.4.0's rootless daemon, `docker run` failed with "failed to initialize logging driver: compression cannot be enabled when max file count is 1". `job_flags()` passes `--log-driver local --log-opt max-size=20m --log-opt max-file=1`, and the `local` driver compresses rotated files by default, which takes at least two. Every job container, and every check container, took those flags. The tests' fake docker can't see a daemon's refusal.

**Changes made:**
1. **`bundles/factory/tree/host/ci_launcher.py`** — `job_flags()` adds `--log-opt compress=false`: one log file, uncompressed.
2. **`bundles/factory/tree/tests/test_ci_launcher.py`** — the job's log options are exactly `max-size=20m`, `max-file=1` and `compress=false`, on the `local` driver.

**Rationale:** A cap on a job's logs that the daemon refuses stops every job. The test pins the one combination the local driver accepts.

---

## 2026-10-14: The CI tier, review round 3; the runner audit

**Origin:** The pilot project's review of the CI tier's round 2 (`8575c31`; 2026-10-14) passed with minor findings, and CD left the calls on them to that project, which asked for all of them before the minor release. The same review found that the runner-registration App's key, now on a runner host that no longer runs production, is the main bridge to production's runner group, and asked for an alarm off that host. Scope from the pilot project (CD's delegate): lean, state-only, hourly.

**What happened:**
- **`ci_launcher.py`:**
  - A token GitHub refused stayed cached until its expiry by the wall clock, so a revoked token or a clock step failed every poll, silently disabling every limit that waits on GitHub's answer.
  - A JSON answer that wasn't an object raised past the cycle's handlers and skipped the backoff counter's write.
  - A network failure on the idle runner's removal counted as "busy".
  - A job that overran `CI_JOB_HOURS` added to the backoff.
  - Low disk and a slow rootless Docker daemon at boot each tripped the whole tier.
  - The firewall check only tested that the table existed, and a tick during `nftables.service`'s own restart could trip.
  - "Nothing may start the runner user's manager again" was false: linger, and the enabled gate and slots' `Requires=user@` (a unit's condition doesn't stop its dependencies from starting), brought it back at boot while tripped.
  - A memory cap that isn't a whole number of pages (`6001k`) never matched `memory.max`, so the check would trip forever.
- **`setup-ci.sh`:**
  - The slots' state was on tmpfs, so a reboot forgot the registrations a killed cycle left.
  - `setpriv` was checked after the host had changed.
  - `TimeoutStopSec=180` was under the launcher's worst-case cleanup (about 210 s).
- **`setup.sh`:** the apt plan ignored removals, and nothing warned about a `RUNNER_HOME_BASE` whose directories someone other than root owns (the pilot project's host condition c3).
- **`create_app.py`:** step 3 for `--runners` left out `TIER_OWNER`.
- **Tests:** nothing covered setup's owner logic, its key refusal, its apt plan or the units.
- **The runner-registration App's key** (organization self-hosted runners: write) can register a runner into any group and change any group's repositories and workflows. Nothing would notice if it did.

**Changes made:**
1. **`bundles/factory/tree/host/ci_launcher.py`**:
   - **Tokens:**
     - their lifetime is counted on the monotonic clock;
     - a 401 drops the cached token and retries once with a new one (`Tokens.call`); a 403 doesn't (item 9).
   - **GitHub's answers:** `api()` returns only JSON objects. A success with anything else is `Failed`, and an error's body is its message. A JIT answer without a runner ID is `Failed`.
   - **Idle runners:** a failed removal of an idle runner asks GitHub again. The runner counts as busy only on GitHub's word, and otherwise the next poll retries the removal.
   - **Backoff:** `job-hours` is neutral, like a recycle.
   - **Memory caps:** they're compared as the kernel keeps them, rounded down to whole pages.
   - **The firewall check:** it compares the table's fingerprint with what setup loaded (`nft -j`, without handles, counters and nft's version; chains, rules and set elements). The minute check looks again three times, 2 s apart, before it trips.
   - **Low disk:** in the check, it's a note, not a trip.
   - **The boot gate:** it waits up to 10 minutes for the runner user's daemon.
   - **A trip:** it also disables the slots, the gate and the timers, and turns off the runner user's linger, so a reboot brings nothing back. Setup enables them all again.
   - **JIT configs:** one a crashed cycle left is removed at the next cycle and at the slot's stop.
   - **The docstring:** it says what bounds a container while GitHub can't be read (the lifetime cap and the disk floor).
2. **`bundles/factory/tree/host/setup-ci.sh`**:
   - The state moves to `/var/lib/factory-runner/<unit>`. Registrations left in the old `/run` state are carried over, and the tmpfiles entry is removed.
   - The settings get `loginctl`'s path and the table's fingerprint (`ci_launcher.py fingerprint`).
   - `TimeoutStopSec=360`.
   - The units' comments say what a trip disables.
3. **`bundles/factory/tree/host/setup.sh`**:
   - `setpriv` and `loginctl` are checked in the CI preflight, before anything changes.
   - The apt plan refuses removals as well as upgrades.
   - **`warn_home_base`** warns when `RUNNER_HOME_BASE`, or any directory above it, isn't root-owned or is writable by group or other.
   - The key check, the tier claim and the warning are functions (`check_ci_key`, `claim_tier`, `warn_home_base`), so they can be tested.
4. **`bundles/factory/tree/runner_audit.py`** (new): the runner audit.
   - `snapshot` takes the organization's runner groups as an expected state.
   - `workflow` writes a self-contained, hourly, GitHub-hosted workflow, with the script and the expected state inside it. Neither factory App can edit a workflow, so neither can change what the audit expects. It refuses content GitHub would read as an expression.
   - `check` compares exactly:
     - the groups, and each group's visibility, public-repository setting, repositories, workflow restriction and workflows;
     - each group's runners, with their IDs and labels. The CI tier's group is a pattern, a most-at-once and labels;
     - factory labels outside their groups.
   - It fails closed: exit 2 when anything can't be read. A failing run opens or updates an issue through the workflow's own `GITHUB_TOKEN`.
   - No audit-log check: a change made and reverted between two runs goes unseen, and the doc names the audit log as the upgrade.
5. **`bundles/factory/tree/create_app.py`**:
   - `--auditor` makes the audit's App: organization self-hosted runners: read, nothing else. Its printed steps put the key in the audit repository's secrets.
   - `--runners`' step 3 names `TIER_OWNER`.
6. **Tests:**
   - **`test_ci_launcher.py`** (13 new):
     - a token minted again after a 401, and a token's life counted on the monotonic clock;
     - answers that aren't objects;
     - GitHub out of reach during an idle removal, and polls failing through the grace window;
     - an overrun counted as neutral, and low disk as a note;
     - memory pages, and a JIT config left behind;
     - SIGTERM during `docker run` and during an API call;
     - the check network's collision;
     - a flushed chain, and the nftables restart window;
     - the trip's disabling steps.
   - **`test_host_setup.py`** (5 new): the apt plan, tier claims, the CI key, the home-base warning, and the CI units as text.
   - **`test_runner_audit.py`** (new, 11): every kind of drift, failing closed, pagination, the expected state's shape, the workflow (YAML, the embedded script byte-identical, its expressions, its refusals), and `check` end to end.
   - **`test_create_app.py`**: the audit App's one read permission.
7. **`process/factory.md`**:
   - **Enablement step 8:** the `RUNNER_HOME_BASE` ownership warning.
   - **Step 10:** the slots' state on disk, what bounds a container during an outage, the firewall rule count and second look, low disk as a note, the boot wait, and what a trip disables.
   - **Step 12 (new), the runner audit:** what it compares, where it runs, what it doesn't see, and its setup.
8. **A fresh architecture review of this batch**, all applied:
   - **The setup self-trip:** `setup.sh` writes the CI table's new rule count into the live settings right after the table loads. Before, the minute check compared a table this run had just changed with the old count until `setup-ci.sh` wrote settings, tripping the tier under setup.
   - **The build context:** it's copied into `/var/lib/factory-runner/ci-build.*`, root's all the way up, not under `RUNNER_HOME_BASE`, whose ancestors' owner could swap it.
   - **A trip inside the gate:** a trip only disables the gate. A trip running inside the gate would otherwise stop itself before turning off linger.
   - **The `/run` state:** registrations carried over from it are removed there.
   - **The alarm:**
     - it comments only on an open issue the workflow opened itself, and opens a new one when there's none or the comment is refused, so a planted or locked decoy can't swallow it;
     - it mentions `RUNNER_AUDIT_NOTIFY`'s logins;
     - it fires on a cancelled run (a timeout) as well as a failed one;
     - the doc names the failed-run email as the channel no App can touch, and asks for a private repository the factory's App isn't installed on.
   - **Patterns:** an expected pattern that matches an empty name is refused, and the doc gives the CI tier's exact one.
   - **"Not seen" says what it is:**
     - a runner that takes one job and goes, and a group opened for one job and restored (the audit log, on GitHub Enterprise Cloud, would see both);
     - a rogue runner within the CI pattern and most-at-once;
     - repository-level runners;
     - a run that never happens.
   - **Snapshot:** it's taken from an operator's machine, never a runner host.
9. **A fresh code review of this batch**, all applied (its two majors were the architect's 1 and 2 above):
   - **401 only:** a 403 is also GitHub's rate limit, so it no longer mints a new token.
   - **The firewall fingerprint:** it replaces the rule count, because `nft flush set … blocked4` keeps the count but opens the LAN.
   - **Stopping:** `TimeoutStopSec=360` covers a cleanup whose refused token is minted again.
   - **The audit:**
     - a runner carrying a GitHub-hosted-style label is drift, and the doc names the limit: a runner registered with `ubuntu-latest` just before a run can answer for the audit;
     - labels must be strings;
     - the expected state is embedded as ASCII-only JSON;
     - `IncompleteRead` exits 2;
     - a failed issue search still opens an issue;
     - the audit step has its own timeout under the job's, so the alarm step runs after it.
   - **The home-base warning:** it walks the resolved path.
   - **Tests:**
     - a trip's steps in order;
     - a 403 that mints nothing, and a token refused twice;
     - a flushed chain and a flushed set, against unchanged counters and handles;
     - setup's fingerprint;
     - hosted-style labels and non-string labels;
     - ASCII embedding;
     - a failed search;
     - a symlinked base.
10. **The pilot project's pre-merge review of the vendored `setup.sh`** (at `b73589a`), all applied to `setup.sh`:
    - **One setup at a time per host:** an `flock` on `/run/factory-runner/setup.lock`, in a directory only root can write.
    - **The tier claim** prints git's own error, naming `safe.directory`, instead of "no origin remote".
    - **`acl`** installs with step 1's packages where Tailscale runs, instead of an un-updated `apt-get install` after the units were written.
    - **An idle runner** is stopped before its new version is unpacked, so no job starts on a half-unpacked runner.
    - **`PLANNING_DB_HOST`** must be a real IPv4 address (no octet above 255).
    - **`host.conf`:** any `TIER` or `TIER_OWNER` assignment in it is refused, even one equal to the command line's, as its seed and setup's message say.
    - **The polkit rule** stays the incubator's: it denies `logind` to its production runner, whose sandbox is its unit's. The bundle's runner users already run user managers by design (rootless Docker), and their Tailscale deny is by user, so it holds there.
11. **The pilot project's two further notes**, applied:
    - **The CI slice's `TasksMax`:** it was a fixed 16384, exactly `CI_RUNNERS` × `CI_JOB_PIDS` at the defaults, leaving no room for the user manager, rootless dockerd and rootlesskit in the same slice. It's now `CI_RUNNERS` × `CI_JOB_PIDS` + 4096 (`SLICE_TASKS` in `--print-settings`); the other tiers stay at 16384.
    - **Enablement step 10's Capacity:**
      - every tier's ceilings are limits, not reservations, and can add up past the host;
      - jobs don't swap, so memory pressure ends in OOM kills (exit 137);
      - compare the tiers' ceilings with the host's memory and other tenants, and use `CI_RUNNERS=1` as the lever.
    - **Step 10, the busy-runner refusal:** a safe way to see GitHub's 422 on removing a busy runner on a new tier (a sleep-only job dispatched on the label), and what happens if it ever didn't.
12. **After the CI tier's first real run** (the pilot project on its runner host, 2026-10-14), beyond its two hotfixes (the log driver, `self-hosted`; their own entries):
    - **Idle slots restart:** a setup run restarts each slot whose runner isn't running a job (`ci_launcher.py busy`; a runner GitHub can't answer for counts as busy). It used to leave a running slot alone, so an idle runner kept the old launcher, and an old label set, until its `CI_IDLE_HOURS` recycle.
    - **The audit:** it leaves out the labels every self-hosted runner has (`self-hosted`, the OS and architecture) by name, whatever type GitHub reports, so a just-in-time runner's own `self-hosted` is neither drift nor a hosted-style label.
    - **A real-Docker test:** `test_a_real_daemon_takes_the_job_flags` runs the job flags on a real Docker daemon when `FACTORY_DOCKER_SMOKE=1` (Enablement step 10's CI says to set it on a GitHub-hosted runner). The fakes passed the log options that stopped every job.
    - **Docs:** step 10 says a JIT runner gets only the labels it's given.
    - **The pilot project's review of the label hotfix** (two lows):
      - `self-hosted` is matched regardless of case;
      - a runner label setting of only commas or spaces (`","`) is refused for every tier, the CI tier's included, as an empty one was (`setup.sh`). Otherwise a runner would register with none of the factory's labels and could take any job asking only for `self-hosted`.
    - **A flaky test:** `test_a_runner_that_never_ran_its_job_backs_off` asserted exactly one `time.sleep`, under a patch of the whole time module that `subprocess`'s own wait loop also calls. It now checks that the first sleep is the backoff.
13. **The first run's report** (the tier live on its runner host: runners registered with `self-hosted,factory-ci`, busy within 40 s, job caps read live from the containers):
    - **The job image:** every setup run built a new one (a new image ID each time, since package steps resolve again), churning the prune. Setup now fingerprints the image's inputs (`ci_launcher.py inputs`: the copied context and Dockerfiles, by path, mode and contents or link target, plus the build arguments and the runner's version). It keeps the image while they're unchanged and it's still there. `CI_REBUILD=1` on setup's command line rebuilds anyway, for upstream updates.
    - **Enablement step 10:** cancel runs still queued for the label a moved job used before (they'd wait a day), and the image reuse.
14. **What the first real e2e runs needed** (the pilot project's experiment, 2026-10-15). No code: per-slot CPU pins were prepared and dropped.
    - **The cause:** the tier's e2e jobs timed out at 8 CPUs where they passed uncapped on the same host. The cause was CPU itself: Chromium's software WebGL (SwiftShader) wants about 7 CPUs a browser.
    - **The experiment**, in a replica of the job container:
      - `--cpus 8`: throttled in 75–80% of periods, failed;
      - pinned to 8 CPUs with no quota: no throttling, but only about 4 CPUs used, failed;
      - `--cpus 16`: failed;
      - `--cpus 24`, with Chromium on a 4 GB `/dev/shm` and fonts added: 32/32 in 10.0 minutes, matching the uncapped runner.
    - **Two container differences mattered too:**
      - Playwright's default `--disable-dev-shm-usage` puts Chromium's shared memory in the container's `/tmp`, which made each round of a test take 4–5 s instead of 0.4 s. A 1 GB `/dev/shm` crashed; 4 GB peaked near 900 MB.
      - The bare image's fallback font broke two hover tests.
    - **The pilot project's fix is its own settings:** `CI_RUNNERS=1`, `CI_JOB_CPUS=24`, `CI_CPU_QUOTA=2600%`, `CI_JOB_SHM=4g`, `CI_MEMORY_HIGH=10G`, `CI_MEMORY_MAX=12G`, plus its Playwright config and fonts in its image.
    - **`process/factory.md`, Enablement step 10's Capacity:**
      - browser suites need far more CPU than their test count suggests, so size `CI_JOB_CPUS` from a measured run and expect one at a time;
      - a quota a CPU-bound job outgrows can't be offset by pinning: measure;
      - give Chromium a real `/dev/shm` and turn off `--disable-dev-shm-usage`;
      - put the fonts in the image.
15. **The pilot project's review of the release** (three reviewers), applied:
    - **Critical, the audit keyed groups by name.** An organization can have two groups of the same name: its own `Default` (visibility `all`, which every repository can target) and one its enterprise shares, which GitHub lists last. So the organization's own dropped out of both the snapshot and the check. Groups are now keyed `<name>#<id>`, whether a group is the enterprise's (`inherited`) is compared, and an expected state keyed otherwise is refused.
    - **Restarting an idle slot could kill a job.** `ci_launcher.py busy` answered "idle" on any local error, and asking then restarting raced a job assigned in between. `retire` replaces it: it deregisters the slot's runner first, which GitHub refuses while it runs a job (422), and answers 10 only when the runner is gone or there was none. `setup-ci.sh` restarts a slot on 10 alone, and says when it doesn't.
    - **A tier labelled only `self-hosted`** (or with the OS and architecture, in any case) passed every guard, so its runners would take any job asking only for `self-hosted`. `setup.sh` refuses a tier without a label of its own, and `jit_labels()` won't register one.
    - **The audit reads every list in full:** it checks GitHub's `total_count`, so a short page isn't taken for the end.
    - **An expected state has every field and list of every group.** One missing used to skip that check silently.
    - **No expected state makes two holes right:** a group every repository may use (visibility `all`), and one the audit's own repository may use. Either lets a runner registered there take the audit's job and answer for it. Enablement step 12's setup now says to close both.
    - **`api()`'s failure paths are tested:** an HTTP error, a network error, a truncated read, and a success that isn't an object.
    - **A registration GitHub won't remove** (a dead runner it still calls busy) no longer stops the cycle. It's kept as `slot-N.leftover-<id>` and retried by later cycles and the slot's stop.
    - **The docs say what the code does:**
      - a 401 drops a token, a 403 doesn't;
      - the CI tier's group is compared by pattern, count and labels;
      - the audit log's REST API is on GitHub Enterprise Cloud;
      - the items here are in order.

**Upgrading a project from v2.0.0.** Migrating copies the bundle; nothing on a host changes until each tier's setup runs again, as root, from the project's checkout. It's a minor release because each change below either needs no action or stops setup with a message that names the fix:
- **Every tier:**
  - **the first run claims the tier,** the strict tier's included: `sudo TIER=<strict|planning|ci> TIER_OWNER=<owner>/<repository> bash setup.sh`, naming the checkout's own repository. Without both, setup stops ("no checkout owns the … tier"). Later runs need neither for strict and `TIER` alone for the others, and another repository's checkout is refused. Remove any `TIER`/`TIER_OWNER` from `host.conf`: it's refused. One setup runs at a time per host;
  - **labels:** a tier whose labels are only defaults GitHub gives every self-hosted runner (`self-hosted`, an OS, an architecture) is refused. The factory's own labels pass;
  - **the firewall** rejects all IPv6 for the runner users, gets its `nftables` stop drop-in, and, where Tailscale runs, denies the runner users `/run/tailscale`;
  - **runners** no longer update themselves (`--disableupdate`; existing ones get it in their settings), and an idle one upgrades to `RUNNER_VERSION`;
  - **the runner's libraries** come from apt, and setup stops rather than upgrade or remove an installed package for them ("would upgrade …", "would remove …"): resolve that by hand, then run setup again;
  - setup warns on every run while `RUNNER_HOME_BASE`'s directories aren't root's alone.
- **The planning tier:** if production's database is on another machine, set `PLANNING_DB_HOST` (its one IPv4 address) with `PLANNING_DB_PORT` in `host.conf`. Unset, the exception stays on this host's own addresses, as before, and setup stops with "the planning tier cannot reach the database at <address>:<port>".
- **A host on a pre-release CI tier** (v2.0.0 has none; a project setting one up now follows Enablement step 10):
  - claim it as above, with `TIER=ci`;
  - the job image rebuilds once, then is kept while its inputs are unchanged (`CI_REBUILD=1` rebuilds);
  - the slice's `TasksMax` becomes `CI_RUNNERS` × `CI_JOB_PIDS` + 4096: 20480 at the defaults (2 × 8192 + 4096);
  - slot state moves from `/run/factory-runner/<unit>` to `/var/lib/factory-runner/<unit>`. The registrations cycles left on the old state move in as leftovers just before the slots restart, to be removed. The backoff counts start again, and the tmpfiles entry is removed;
  - idle slots restart: setup asks GitHub about each slot's registrations and restarts a slot only when they're gone, or idle and removed;
  - a runner audit's `expected.json` made before the release (groups keyed by name alone) is refused: snapshot again, review it, and regenerate the workflow.
- **The project's CI:** with a CI tier, run the bundle's tests on a GitHub-hosted runner with `FACTORY_DOCKER_SMOKE=1`.
- **The runner audit:** set it up before the CI tier takes jobs (Enablement step 12), with every runner group's visibility `selected`.

**Rationale:**
- **The audit:** the runner-registration key is the most powerful credential the factory keeps on a host, and production's runner group is one PATCH away from it. An alarm off the host, with a read-only credential and an expected state that neither factory App can edit, is the least that makes misuse visible.
- **Round 3:** each fix keeps a failure from looking like something else: a dead token like a quiet runner, a slow daemon like an isolation failure, a flushed chain like a loaded firewall.

---

## 2026-10-14: Runner users can't reach Tailscale's local API

**Origin:** The incubator's production move to a machine of its own (2026-10-14). The architecture review of its production runner asked whether Tailscale could get around a firewall that matches the user. A test on the production machine showed it could: a non-root user that isn't Tailscale's operator ran `tailscale nc` and got the runner host's SSH banner. Tailscale's local API socket (`/run/tailscale/tailscaled.sock`) is mode 0666, and its dial endpoint connects to any tailnet peer as `tailscaled`, which is root. The connection comes from root, so the runner users' `meta skuid` rules never see it.

**What happened:**
- The runner tiers' isolation test already proves a job container can't reach the host's Docker socket, so a job probably couldn't mount Tailscale's either.
- But the runner users have processes on the host: the runner itself and, with linger, a user manager. Nothing stopped those from reaching it, and nothing tested it.

**Changes made:**
1. **`bundles/factory/tree/host/setup.sh`** — On a host running Tailscale:
   - Each tier denies its runner user `/run/tailscale` with an ACL (installing `acl` if it's missing).
   - A `tailscaled.service.d/<firewall unit>.conf` drop-in reapplies the ACL whenever `tailscaled` starts, since its `RuntimeDirectory` is recreated each time. It runs before the socket exists (`ExecStartPre`) and again after (`ExecStartPost`).
   - The isolation test fails unless the runner user is refused for permission (`EACCES`). Root connects first, so a missing socket can't pass for a refusal.
   - Matching by user covers the runner, its user manager and its rootless containers alike: inside a container, the user ID is still the runner user's.
2. **`process/factory.md`** — Enablement step 8 says so. It also notes that the firewall table is reloaded after `nftables` stops, and that a setup run upgrades idle runners.

**Rationale:** The tiers' isolation is a firewall that matches the user. Any root daemon that connects on a local user's behalf goes around it, and Tailscale's does by design. The runner hosts that need this most also run Tailscale.

---

## 2026-10-14: Runners take a version bump; tier firewalls survive nftables stopping

**Origin:** An architecture review of the incubator's production move to a machine of its own (2026-10-14) read the same code in the incubator's `setup-production.sh` and in the bundle.

**What happened:**
- **Runner upgrades.** Since "factory runner hosts: no IPv6, no self-update" (2026-10-13), runners register with `--disableupdate` and stay at `setup.sh`'s `RUNNER_VERSION`. The comment and `process/factory.md` (Enablement step 8) said "a run of this setup installs it". But setup downloaded a runner only when its directory had none, so a bump never reached an installed runner. GitHub stops sending jobs to runners more than 30 days behind a release.
- **The firewall after a stop.** Each tier's firewall table was reloaded after `nftables.service` started, restarted or reloaded, but not after it stopped. Its stock `ExecStop` flushes the whole ruleset, so the table was gone while the firewall unit still showed active.

**Changes made:**
1. **`bundles/factory/tree/host/setup.sh`**:
   - **Upgrades.** An installed runner at a different version than `RUNNER_VERSION` gets the new archive unpacked over it. Its registration files aren't in the archive. The existing idle-only restart then starts the new version. A runner running a job is left alone, with a message to re-run setup when it's idle.
   - **Stops.** A drop-in, `nftables.service.d/<firewall unit>.conf`, reloads the tier's table with `ExecStopPost` after nftables stops.
   - A flush by hand (`nft flush ruleset`) is still not covered. The CI tier's minute-by-minute firewall check would see one.

**Rationale:** Runners that never update themselves are only safe if setup is how they update. A firewall that a routine `systemctl stop` can remove, without anything noticing, isn't a boundary.

---

## 2026-10-14: The planning tier's database can live on another machine

**Origin:** The incubator's production is moving off its factory runner host to a production-only machine (CD, 2026-10-14). The planning tier's one firewall exception (D3 rule 2) admitted only a database port on the runner host's own addresses, so a database elsewhere was out of its reach.

**Changes made:**
1. **`bundles/factory/tree/host/setup.sh`:**
   - A new setting, `PLANNING_DB_HOST`: one IPv4 address, refused unless `PLANNING_DB_PORT` is set too.
   - When set, the planning tier's exception admits that address and port instead of the host's own addresses.
   - The isolation test then keeps the database port in the probe of this host, which must now be closed like any other, and the final reachability check connects to the remote address.
   - The setting is empty by default, which keeps today's behavior.
   - `--print-settings` shows it as `DB_HOST`.
2. **`bundles/factory/seed/host/host.conf`:** `PLANNING_DB_HOST`, with a note to use an address that doesn't change, such as the machine's Tailscale address. The comment now cites D3 rule 2, not rule 3.
3. **`bundles/factory/tree/tests/test_host_setup.py`:**
   - the planning tier with a remote database;
   - the strict tier never gets one;
   - a host name, a list, or a host without a port is refused.
4. **`process/factory.md`:** D3 rule 2 names the remote case.

**Rationale:** Moving production off the runner host is what D2's "Revisit when" anticipates. The planning tier's read-only access to production's database must follow the database to its new machine through the same single, address-pinned exception.

---

## 2026-10-13: The tier and its owner come only from setup's command line

**Origin:** The pilot project's review of round 2 ("The factory CI tier, review round 2", below). `setup.sh` recorded whether `TIER` was given after it had sourced `host.conf`, so a `host.conf` that set `TIER` (the pilot project's did) defeated the rule that a new owner claim names its tier. A `TIER_OWNER` there would have defeated the claim itself.

**Changes made:**
1. **`bundles/factory/tree/host/setup.sh`**: whether `TIER` was given is taken before `host.conf` is sourced, and setup refuses a `host.conf` that sets `TIER` or `TIER_OWNER` to anything but what the command line gave.
2. **`bundles/factory/seed/host/host.conf`**: says `TIER` and `TIER_OWNER` never go there. The per-tier defaults line gives the CI tier's new `CI_MEMORY_HIGH` default (14G, not 12G).
3. **`bundles/factory/tree/tests/test_host_setup.py`**: a `host.conf` that sets either is refused; the same value on both is not an override.

**Rationale:** The claim is the operator's statement at the moment of the first run. A checked-in setting that supplies it for them is the trust-on-first-use the claim replaced.

---

## 2026-10-13: The factory CI tier, review round 2

**Origin:** The pilot project's architect and code reviewer reviewed the disposable-runner CI tier ("The factory CI tier runs one disposable runner per job", below). The architect approved it with conditions, both reviewers found the same three launcher defects, and they listed host, configuration and test gaps besides.

**Changes made:**

1. **`bundles/factory/tree/host/ci_launcher.py`**:
   - **Docker no longer orphans.** Every docker call runs through `setpriv`, which execs, so a timeout kills docker itself. `runuser`'s forked parent left docker running after a timeout. Every call has a timeout. A cycle runs one `docker wait`, which is never killed and returns when the container ends.
   - **The job-hours limit can't be dodged.** GitHub's view of the runner decides when to kill. A 404 while the container runs (the job is over) kills it, so does offline on two polls after being online, or never online within a grace period. An idle runner is recycled after `CI_IDLE_HOURS`: it is deregistered first, and if GitHub refuses because a job just arrived, the job runs. The container's lifetime is capped at `CI_IDLE_HOURS` + `CI_JOB_HOURS` whatever the API says.
   - **Backoff.** It counts from GitHub too. A runner still registered after its container ended never ran a job, so it counts as a failure. The installation token is cached in memory until near expiry.
   - **The check fails closed.** Any exception in it, a hang included, trips the tier (the units' `OnFailure=` runs a new `trip` subcommand that keeps the check's marker).
   - **The check covers more:**
     - It re-reads the group's visibility and public-repository setting.
     - It checks free space.
     - It runs a host-side probe as the runner user with no Docker, which is where IPv6 is tested.
     - The default LAN gateway joins the targets, so the blocked set itself is exercised; the host's own addresses all hit the loopback rule.
     - The container probe runs with a job's own flags and checks the exact `cpu.max`, `memory.max` and `pids.max`.
     - A listener at a fixed address on a network of its own must be unreachable from a slot-like network.
   - **Liveness is not isolation.** The internet or GitHub out of reach is logged, not tripped.
   - **`fwcheck`** checks the firewall table every minute.
   - **SIGTERM unwinds the cycle**, so the slot's stop removes its container and registration. The runner's ID is kept in `slot-N.runner` before the container starts, and the slot's `stop` and the next cycle deregister a leftover. Each cleanup step runs on its own.
   - **Transport errors.** `api()` turns every transport and parse error (`http.client.HTTPException`, non-JSON) into one error type, so polling survives them.
   - **Disk.** Below `CI_MIN_FREE_GB` free under the runner's home, no cycle starts and a running job is killed.
   - **Container hardening.** Job containers get capped `local` logs and drop `NET_RAW` and `MKNOD`.
   - **The state directory** must be a directory only root can write.
   - **Logging.** Probe and API output is logged as printable ASCII only.
   - **The header** states the App key's reach, and that the JIT config stays readable inside the container until removal (single-use).
2. **`bundles/factory/tree/host/setup-ci.sh`**:
   - **The key** is no longer moved from the checkout (see `setup.sh`).
   - **The launcher's settings** are written whole to a new file, resolved against GitHub, completed with the image, then renamed into place.
   - **The build context and Dockerfile** must resolve, links included, inside the checkout. They are copied with `cp -RP`, so links stay links.
   - **The job image** is labelled `factory.keep`, and earlier ones are removed by the runner user.
   - **The units:**
     - the gate `Wants=network-online.target`;
     - the gate and check get `TimeoutStartSec` and `OnFailure=` the trip unit, and the check no longer `Requires=user@`, which restarted the runner user's manager while tripped;
     - a new firewall check timer runs every minute;
     - slots run with `KillMode=mixed`.
   - **Extra slots** are found from the enabled and loaded units, not 1–20.
   - **A failed image inspect** now dies with its message.
3. **`bundles/factory/tree/host/setup.sh`** (shared by every tier):
   - **Tier owner, no longer trust-on-first-use.** A missing owner record is made only when `TIER_OWNER` names this checkout's repository and `TIER` is given too, so a dropped `TIER` can't claim strict.
   - **The firewall.** Each tier's firewall unit orders after `nftables.service` and reloads with it, and a new `<firewall>-reapply.service`, wanted by `nftables.service`, loads the table again after its start or restart. Its stock ruleset begins with `flush ruleset`. `PartOf=` would have restarted the firewall unit and, through `user@`'s `Requires=`, killed every job.
   - **The weekly prune** spares `factory.keep` images.
   - **The runner's apt dependencies** are simulated first, and setup stops if installing them would upgrade an installed package (an `Inst` line with the old version in brackets straight after the name). The comment claimed `--no-upgrade` did that.
   - **For TIER=ci:**
     - every setting and the App's key are checked before anything changes;
     - caps must be above 0, which Docker reads as unlimited;
     - `CI_MEMORY_HIGH` must cover `CI_RUNNERS` × `CI_JOB_MEMORY` + 2G (default now 14G);
     - the key must already be at `/etc/factory-runner/<unit>/app.pem`, and a key in the checkout's `host/` directory stops setup;
     - `CI_CPU_WEIGHT` is removed: a weight on the user's slice only ranks it against other users, never against `system.slice`, so `CI_CPU_QUOTA` is the bound;
     - new settings `CI_IDLE_HOURS` (24) and `CI_MIN_FREE_GB` (20).
4. **`bundles/factory/tree/create_app.py`**: `--runners` states the key's reach and prints the root-only install command.
5. **Seeds:** `host/host.conf`'s CI block (the new settings, the key's place, the memory rule, `RUNNER_HOME_BASE` on its own filesystem). `factory.json`'s `ci._doc` (paths resolve inside the repository; base pinned by digest).
6. **Tests:** `test_ci_launcher.py` rewritten (23 tests). It covers:
   - one `docker wait` per cycle, and no docker process left alive;
   - a 404 while running, offline twice, never online, idle recycling and its race, and the lifetime cap with GitHub failing;
   - non-JSON and cut-off answers while polling;
   - low disk;
   - a real SIGTERM mid-job;
   - a slot's stop and a leftover registration;
   - the state directory's owner and mode;
   - the check passing, tripping on each of ten failures (an exception and a timeout among them), and not tripping on liveness;
   - the firewall check;
   - the trip unit keeping a check's marker.

   `test_host_setup.py` follows the settings.
7. **`process/factory.md`**:
   - **Enablement step 2:** `ci-app.pem` is gone from the `.gitignore` list.
   - **Step 8:** `TIER_OWNER` and the reapply unit.
   - **"The CI tier":** the kill conditions, key handling (straight to `/etc`, never a checkout, out of backups), the build-context rule, the setup order with `TIER_OWNER`, the checks, liveness, capacity (`CI_CPU_QUOTA`, the memory rule, `RUNNER_HOME_BASE` on its own filesystem).

**Not done here:**
- **A scheduled audit of every organization runner group's members against expected names.** The architect asked for it as a compensating control for the App key. It is CD's decision. Tripping the CI tier wouldn't touch a rogue runner in another group, and the audit must run where the key isn't.
- **Tests for `setup.sh`'s and `setup-ci.sh`'s heredoc units and the tier-owner logic.** They need root and systemd, so a host run is their first test.

---

## 2026-10-13: The CI tier's App key reaches every runner group

**Origin:** The pilot project's review of the CI tier asked whether a stolen runner-registration key could put runners into the strict tier's group or a production group. GitHub's REST docs for self-hosted runner groups answer it. The App's one permission, `organization_self_hosted_runners`, covers every organization runner endpoint: registering into any group with any labels, moving runners between groups, and changing a group's visibility, public-repository and workflow restrictions.

**What happened:** `process/factory.md` said the key "can register runners and nothing else", which understated its reach.

**Changes made:**
1. **`process/factory.md`** (Enablement step 10, The CI tier): the runner-registration App's paragraph now states what a holder of its key can do. It notes that it is the first long-lived credential on a host that can register runners. It lists how the key is kept: root-only, the downloaded copy deleted, revoked on doubt, and group drift reported by `bootstrap.py`.

**Rationale:** CD chose disposable runners partly on the App's stated reach, so the stated reach has to be right. `create_app.py`'s docstring and `host/ci_launcher.py`'s header say the same and change with the review's findings.

---

## 2026-10-13: The factory CI tier runs one disposable runner per job

**Origin:** CD's decision (2026-10-13): design A for the held CI tier ("The factory CI tier is held", below). The pilot project's review had shown that a persistent runner hands a job's environment and PATH to its own host-side processes.

**What happened:** The runner itself goes inside the boundary. A launcher on the host registers a just-in-time (JIT) runner for each job and runs it in a fresh rootless container. The job runs in that container, runner and all, and the container is removed after its one job. Checked against actions/runner v2.338.0:
- `generate-jitconfig` takes an App installation token with the organization's "Self-hosted runners" (write) permission.
- The runner reads `ACTIONS_RUNNER_INPUT_JITCONFIG` from its environment, masks it, and removes it before any step.
- `run.sh` exits 0 when a JIT runner has run its job.
- A JIT runner's settings come from GitHub, so `--disableupdate` can't apply to it. It updates itself, if at all, only inside its throwaway container.

**Changes made:**

1. **`bundles/factory/tree/host/ci_launcher.py`** (new), root-owned:
   - **`run`, one cycle:** the App's JWT signed by openssl with the root-only key, then an installation token narrowed to the one permission, then a JIT config, then a fresh container started as the runner user with per-job CPU, memory, process and shm caps, `no-new-privileges` and its own network. An idle runner waits as long as it takes. `docker wait` runs in 5-minute rounds, and between rounds GitHub, not the daemon, is asked whether the runner is busy. A job is killed after `CI_JOB_HOURS` of job time, a backstop behind the job's own `timeout-minutes`. Then the cycle removes the container and deregisters the runner with a fresh token. A failing cycle backs off, so `generate-jitconfig` isn't hammered.
   - **`stop`, `resolve` and `check`.** `resolve` returns the App's installation (it must hold the permission) and the group (selected repositories only, no public ones). `check` covers the firewall table, the slice caps, the delegated controllers, and a probe from a container of the job image: host, LAN and IPv6 closed, the internet open, caps in force. A failure writes a marker no slot starts past and stops the runner user's whole session.
   - **The rules root keeps.** Root reads only `docker wait`'s integer from the daemon. The JIT config travels in a 0600 file created without following links, in a root-owned directory, and is deleted once the container starts. Every docker call runs as the runner user with a fixed environment.
2. **`bundles/factory/tree/host/ci-runner.Dockerfile`** (new): the project's toolchain image with the runner on top (pinned version, checked archive, its dependencies installed inside the image), `python3` for the probe, and `RUNNER_ALLOW_RUNASROOT` (container root is an unprivileged host user).
3. **`bundles/factory/tree/host/setup-ci.sh`** (new), sourced by `setup.sh` after step 6 for `TIER=ci`:
   - **The key** moves from the checkout's gitignored `host/ci-app.pem` to `/etc/factory-runner/<unit>/app.pem` (root-only).
   - **Delegation** of the cpu, memory and pids controllers is verified.
   - **The launcher's settings** are written, and resolved against the App and the group before anything is built.
   - **The job image** is built as the runner user from root-owned copies of the build contexts.
   - **The units:** a gate unit runs the check before any slot starts (at boot too), a timer runs it every 6 hours, and `<unit>-slot@N` is started, never restarted, so a job in flight survives a setup run.
4. **`bundles/factory/tree/host/setup.sh`**:
   - **The hold is gone.** `TIER=ci` takes steps 1–6, then `setup-ci.sh`.
   - **The CI tier's settings:** its slice gets a low `CPUWeight` (`CI_CPU_WEIGHT`, 20) and its user's manager delegates cpu, cpuset, io, memory and pids. New settings `CI_APP_CLIENT_ID` and `CI_JOB_*` show in `--print-settings`.
   - **Removed:** the persistent-runner guard, hooks and their check.
5. **Removed:** `host/docker_guard.py`, `host/ci_job_hook.sh` and their tests.
6. **`bundles/factory/tree/workflow_policy.py`**: a job on the CI label runs in its disposable runner. So: no `container:` or `services:` of its own, no `docker://` step, and the container rule doesn't apply to it. The other CI-tier rules stay.
7. **`bundles/factory/tree/create_app.py`**: `--runners` creates the runner-registration App, whose only permission is `organization_self_hosted_runners: write`, and says where its key and client ID go.
8. **`bundles/factory/tree/bootstrap.py`**: a runner group that lets public repositories use it is a problem.
9. **`bundles/factory/tree/render.py`**, **seeds:** `factory.json` gains the `ci` block (`dockerfile`, `context`, `build_args`), which render treats as a run-time setting. `host/host.conf` gains `CI_APP_CLIENT_ID`, `CI_JOB_*` and `CI_CPU_WEIGHT`.
10. **Tests:** `test_ci_launcher.py` (new) covers a cycle against a fake GitHub with recorded docker calls, the JWT verified with real openssl, failure and non-integer exits, an idle runner never killed, a job killed after its job time, no JIT config, backoff, the env file over a planted link, resolve, and the check passing and tripping. Also `test_host_setup.py`, `test_render.py` (the flipped CI-tier rules), `test_create_app.py` and `test_bootstrap.py`.
11. **`process/factory.md`**: "The CI tier" rewritten (how it works, the threat model, the App, the image and its version coupling, the setup order, the check, the job shape, capacity, runner versions). Enablement step 2 adds `ci-app.pem` to what `.gitignore` must cover.

**Rationale:** On a persistent runner, the runner's own processes are the job's way to the host. A disposable runner per job puts them inside the job's container, so nothing a job does outlives it, and the runner user's firewall and caps remain the outer boundary.

---

## 2026-10-13: The factory's verify test runs in its own directory

**Origin:** Handing the pilot's bundle code to the incubator (zsdlc-import-factory --to-incubator).

**What happened:** `test_agent_job.py`'s `Verify` test assumes its profile's directories (`api`, `web`) don't exist, but it ran `verify` in the current directory. Run from a checkout whose `web/` has `node_modules` (the incubator's), the node checks really ran and passed, and the test failed.

**Changes made:**

1. **`bundles/factory/tree/tests/test_agent_job.py`**: `Verify` (and `VerifyDotnetNode`) run `verify` in the test's temp directory.

**Rationale:** A test that depends on where it is run from fails on a developer's machine and passes in CI, which hides real failures.

---

## 2026-10-13: Factory runner hosts: no IPv6, no self-update, one checkout per tier

**Origin:** The pilot project's review of the CI tier raised three findings that hold for every tier. CD approved all three proposals (2026-10-13).

**What happened:**
- **IPv6.** The firewall rejected private IPv4 ranges and a few IPv6 ones (loopback, unique-local, link-local, multicast), and the isolation test probed only IPv4. A host's own global IPv6 addresses and its LAN's global prefix were reachable from jobs.
- **Self-update.** Runners updated themselves, away from the version setup.sh verifies by checksum.
- **Checkouts.** Any checkout's `host.conf` could re-run any tier's setup, re-capping or re-labelling a tier another project set up. A dropped `TIER` falls through to `strict`.

**Changes made:**

1. **`bundles/factory/tree/host/setup.sh`**:
   - **IPv6:** the runner users' chain rejects all IPv6 (everything a job needs answers over IPv4), and the IPv6 blocked set is gone. The isolation test also probes the host's global IPv6 addresses and a public one, and must find them closed.
   - **Self-update:** new registrations pass `--disableupdate`, and runners already registered get `disableUpdate` in their settings file (the runner reports it when its session starts).
   - **Tier ownership:** the first run records the repository whose checkout set the tier up, in `/etc/factory-runner/tiers/<unit>`, and a run from another repository's checkout is refused (remove the file to hand the tier over).
2. **`process/factory.md`** Enablement step 8 says all three. z-sdlc bumps `RUNNER_VERSION` within 30 days of each actions/runner release, since GitHub stops sending jobs to older runners, and each tier's setup runs again from its checkout after the migration that brings the bump.

**Rationale:** The firewall's job is that no factory job reaches the host or the LAN. An address family it didn't cover, a runner binary nobody verified, and a tier any checkout could reconfigure were three ways around it.

---

## 2026-10-13: The factory CI tier is held; host setup never runs a runner-writable file as root

**Origin:** The pilot project's review of the CI tier (software-architect, devops, code-review). The architect rejected running `sudo TIER=ci setup.sh`. Its premise: assume a pull request's code reaches the host as the runner user. Two findings, confirmed against actions/runner v2.338.0, make that premise true:
- **C1, the docker client.** The runner starts the docker client for a step's `docker exec` with the step's whole environment (StepHost.cs), so `LD_PRELOAD` from `$GITHUB_ENV` reaches the host binary first: the guard's `/bin/sh` and python3, or `/usr/bin/docker` itself without a guard. The runner's host-to-container path translation is a prefix match, so a host path to a planted library slips through untranslated.
- **C2, the hooks.** The runner picks a hook's shell with `GetDefaultShellForScript(path, prependPath)` (JobHookProvider.cs), and `$GITHUB_PATH` feeds `prependPath`. So the job-completed hook runs a bash the job chose.

**What happened:** On a persistent runner, job-controlled environment and PATH reach the runner's own host-side processes. That is the runner's design, not a gap in the guard (2026-10-13 entries below). Hardening the guard further would be whack-a-mole, so the tier is held for a design decision.

The review also found a root escalation present in every tier from the start. setup.sh ran `"$dir/bin/installdependencies.sh"` as root whenever `config.sh` wasn't executable, and that directory belongs to the runner user. A compromised runner user could plant the script, and the next setup run would execute it as root. The same script's apt run could upgrade shared libraries on a production host.

**Changes made:**

1. **`bundles/factory/tree/host/setup.sh`**:
   - **Runner libraries:** root installs them from apt, from an explicit list of the runner's Debian dependencies (installdependencies.sh v2.338.0), with `--no-upgrade`, and never runs anything from the runner's directory. This affects every tier, but only does anything on a host missing one of those libraries.
   - **The seccomp profile** is replaced only when it differs, by an atomic rename, so the other tiers' jobs never see it missing.
   - **`TIER=ci` is refused** after `--print-settings` and before any root work, naming this entry.
2. **`bundles/factory/tree/tests/test_host_setup.py`**: the hold.
3. **`process/factory.md`**: "The CI tier" opens with the hold. Enablement step 2 adds `.github/factory/host/reg-token` to what `.gitignore` must cover.

**For CD to decide (the CI tier's design):**
- **A. Disposable per-job runners** (recommended). A root-owned launcher mints a just-in-time (JIT) runner config per job and starts a fresh runner in a throwaway rootless container. Its image is the runner plus the end-to-end toolchain, and the job runs in it (no `container:`). The container is destroyed after one job, so everything C1 and C2 reach is inside it. The runner user, firewall and caps stay the outer boundary. It needs a credential on the host that can register runners: a second GitHub App with only `organization_self_hosted_runners: write`, its key root-only. The container only ever gets the single-use JIT config.
- **B. Untrusted code never reaches the host.** The tier runs only the default branch's code, so its group can be restricted to `ci.yml@refs/heads/main`, a platform-enforced boundary. Pull-request end-to-end tests go to hosted runners, where the per-test CPU need (a server, Postgres, two browsers) starves 2 vCPU. So B means a lighter pre-merge subset plus the full suite after merge, or paid larger runners.
- **C. Harden the persistent runner** (a static first-exec shim, no completed hook, a loader-variable scrub). Residual exposure through the runner's own processes; not recommended.

The guard, hooks and check timer stay in the tree, held, as design inputs. The review's findings on them (service-container start TOCTOU, fail-closed ordering, the check not killing in-flight jobs, the `_PipelineMapping` redundancy, the exec environment allowlist, a stricter network regex, `..` tests) are recorded for whichever design follows.

**For CD, all tiers (proposals, nothing changed):**
- **IPv6.** The firewall and the isolation probe are IPv4-only, so a host's global IPv6 addresses and its LAN's global prefix aren't blocked. The simplest sound fix rejects all IPv6 egress for factory users, since IPv4 reaches everything the jobs need.
- **`--disableupdate`.** It would pin the runner to setup.sh's verified version, at the cost of a bump within 30 days of each runner release.
- **One checkout per tier.** Run each tier's setup from one designated checkout: its host.conf caps that tier (the pilot project now defaults its host.conf to `TIER=ci`).

**Rationale:** A boundary has to hold against what the runner itself does with a job's input. The fix that applies everywhere (root never executing what the runner user can write) goes in now. The CI tier waits for a design that puts the runner's own processes inside the disposable boundary.

---

## 2026-10-13: The factory's seeded CODEOWNERS test works in a repository with Git LFS

**Origin:** The pilot project's first hosted CI run of the factory checks (its fix is c7892b62 there).

**What happened:** The seeded `tests/test_codeowners.py` replays the publish path on a local `git clone --depth 1 --no-local` of the CI checkout (`RealChangelog`). In a repository that tracks files with Git LFS, `actions/checkout` leaves them as pointers, and git-lfs on the runner then tries to fetch their objects from a "remote" that has none. The clone exits 128 ("remote missing object"). The incubator has no LFS, so it never saw this.

**Changes made:**

1. **`bundles/factory/seed/tests/test_codeowners.py`**: the test's git calls (`run()` and `RealChangelog.git()`) set `GIT_LFS_SKIP_SMUDGE=1`; the test never reads LFS content. A seed: new projects get it, and an existing project takes the change by hand (the pilot project has it).

**Rationale:** A project's own files decide whether it uses LFS. A seeded test has to pass in either case.

---

## 2026-10-13: The factory CI tier holds against a hostile job definition

**Origin:** The pilot project's software-architect reviewed the CI tier. A `pull_request` run executes the pull request's own workflow, and the CI group can't be workflow-restricted (pull requests' merge refs). So for a pull request from a branch, the workflow policy is a merge gate, not an execution gate, and a job definition on the tier can be hostile (`container.options: -v …`, a new workflow on the label). The review asked for ephemeral runners or wiping between jobs, runner credentials kept from job containers, daemon defaults, a recurring isolation probe and no shared host caches. It also found `*.csproj.user` and a root `dotnet-tools.json` missing from `dotnet-node`'s CODEOWNERS list.

**What happened:** Read against the runner's source (actions/runner v2.338.0):
- **The runner's docker calls.** `DockerCommandManager` builds one options string and splices the job's `container.options` into it verbatim, and a job's `container.volumes` become `-v` too. docker/cli stops reading options at the image (`SetInterspersed(false)`).
- **What a job can reach.** Job containers get the whole work directory read-write. The runner's credentials sit outside it, reachable only through a mount the job adds.
- **What persists between jobs.** `ActionManager` deletes `_actions` at every job start and `_temp` is recreated, but `_tool` and the workspaces persist. So does `_PipelineMapping`, which `PipelineDirectoryManager` joins to `_work` unchecked when the next job starts, before its hooks run.
- **Steps' secrets.** A step's environment, secrets included, reaches `docker exec` through the CLI's own environment (`-e KEY`).
- **Mid-job containers.** `docker run` (docker:// steps, container actions) mounts runner directories mid-job, after the job's code could have swapped one for a symlink.

**Changes made:**

1. **`bundles/factory/tree/host/docker_guard.py`** (new): the CI tier's runners reach docker only through it.
   - **What passes:** the runner's own commands, exact forms only.
   - **Mounts:** only the runner's own directories, by exact path with no symlink below them, or anonymous volumes.
   - **Refused:** any option it doesn't know (`--env-file`, `--cidfile` and the rest), every privilege and namespace option, other networks, published ports, and other security options. Those must stay a pair with the policy's `ALLOWED_OPTIONS`. It also refuses `docker run` and `docker build`, so no `docker://` step or Dockerfile action runs on the tier.
   - **What it forces:** `no-new-privileges` on every container, and docker always against the instance's own daemon. Every command but `exec` gets a minimal environment.
2. **`bundles/factory/tree/host/ci_job_hook.sh`** (new): the job-started hook deletes `_tool` and empties the workspaces, keeping the directories the runner made for the job. The job-completed hook deletes `_tool`, the workspaces and `_PipelineMapping`. They work in the rootless daemon's user namespace, for files owned by subordinate IDs. `reset` deletes the whole work directory as root.
3. **`bundles/factory/tree/host/setup.sh`** (`TIER=ci`):
   - **Installs:** the guard, the hook and a root-owned probe, under `/usr/local/lib/factory-runner`. Each instance gets root-owned settings (`/etc/factory-runner/factory-ci/N.json`) and wrappers, and its `.env` puts the guard first on PATH with both hooks.
   - **The runner unit:** wipes the work directory as root before every start.
   - **The check timer:** `factory-ci-check.timer` runs every 6 hours. It checks the firewall, the slice caps, the isolation probe from a container (host, LAN and host socket closed, internet open; a failed pull of the probe's image says so), and each instance's PATH, hooks and guard, which must refuse a mount of the runner's own directory. A failure stops `factory-ci@*`, which stays stopped until someone starts it again. Setup's last step is the check's first run, so a misconfigured tier never takes a job.
4. **`bundles/factory/tree/tests/test_docker_guard.py`, `test_ci_job_hook.py`** (new): the runner's own argv (job container, exec, `--config` pull and login, networks) passes; every hostile variant is refused; the guard's environment and host are checked. The hooks' modes are tested on a temp tree, and bad paths and a missing pid file are refused.
5. **`process/factory.md`**: "The CI tier" gains the threat model (merge gate against execution gate), the guard, hooks and check, the docker:// and Dockerfile-action ban, no host paths, and ephemeral runners as CD's call. They need a credential on the host that can register runners, and the factory App lacks that permission. `dotnet-node`'s CODEOWNERS list gains the project files' `.user` files and a root `dotnet-tools.json` (with the seeded test and the proof's CODEOWNERS).

**Rationale:** The factory's own pool keeps hostile workflows out by its workflow restriction. The CI tier can't, so it enforces at the one place every job definition passes through, the runner's docker commands. It also leaves nothing on disk for the next job.

---

## 2026-10-13: A factory CI tier: isolated self-hosted runners for a project's own CI jobs

**Origin:** The pilot project. CD's decision for its pull-request end-to-end jobs (Playwright, against the real server and Postgres) was a dedicated, isolated CI runner tier on the runner host, built the factory's way, with no paid larger runners, and with pre-merge end-to-end tests kept for factory PRs. They had moved off 2-vCPU GitHub-hosted runners because two browsers starved the CPU, and ran on an unisolated self-hosted runner, which the workflow policy refuses.

**What happened:** CD asked for the tier's runner group to be restricted to the project's CI workflow. GitHub's runner groups pin each selected workflow to a branch, with no wildcard ([docs](https://docs.github.com/en/enterprise-cloud@latest/actions/hosting-your-own-runners/managing-self-hosted-runners/managing-access-to-self-hosted-runners-using-groups)). A `pull_request` run comes from the PR's merge ref, so a `ci.yml@refs/heads/main` entry never matches it and its jobs would wait forever. That restriction can't coexist with pre-merge tests, so the CI group is restricted to the repositories that use it. The isolation lives in the runners (their own user, firewall and caps, a job container required) and in the policy's hold on the label. `factory-pool` keeps its workflow restriction: agent workflows run from events on the default branch. This, and the Chromium point in item 4, are decisions for CD to confirm.

**Changes made:**

1. **`bundles/factory/tree/host/setup.sh`**: `TIER=ci`. User `factory-ci`, nft table `factory_ci`, firewall unit and file, runner unit `factory-ci@N`, names `<prefix>-ci-N`, all suffixed for a second organization. Label `runners.ci`; group `runners.groups.ci` (default `factory-ci`), computed per tier now. Caps from host.conf's `CI_RUNNERS` (2), `CI_MEMORY_HIGH` (12G), `CI_MEMORY_MAX` (16G) and `CI_CPU_QUOTA` (800%), for the tier's runners together. Otherwise the strict tier's setup: firewall (internet, no host or LAN), rootless Docker, isolation self-check from inside a container, job container required. A `factory.json` without `runners.ci` is refused with the reason.
2. **`bundles/factory/tree/bootstrap.py`**: once a workflow runs on `runners.ci`, the CI group, created with the repository and without a workflow restriction. An existing CI group restricted to workflows is reported with why it would strand pull requests, and left to CD.
3. **`bundles/factory/tree/workflow_policy.py`**: CI-tier rules for any job on the label. It must be in one of the project's own workflows (never a factory one), run no agent, and run in a container (the existing rule: no service containers). It needs explicit read-only permissions and checkouts with `persist-credentials: false`. It holds no secret and no job token, except the job token as the container's pull credentials. `systempaths=unconfined` comes only with the factory seccomp profile. The label counts as a factory label, so it is never a hosted label or exemptible.
4. **`process/factory.md`**: Enablement step 8 runs `TIER=ci`. Step 10's "The CI tier" covers the setup order (bootstrap creates the group before setup registers into it), why the group isn't workflow-restricted, the job rules, the seccomp profile as allowed but not required, and capacity. Docker's default seccomp is stricter, and enough for a browser run without its own sandbox, which is Playwright's default. Chromium's sandbox under `seccomp-bwrap.json` wasn't tested.
5. **`render.py`** treats `runners.ci` and `runners.groups` as run-time settings. **Seeds:** `factory.json` gains `runners.ci: factory-ci`, and `host/host.conf` the `CI_*` settings. **Tests:** `test_host_setup.py` (the tier's names, caps, group, second organization, an old `factory.json`), `test_bootstrap.py` (the group made only once a workflow uses the label, without a workflow restriction; a restricted one left to CD), `test_render.py` (a compliant CI-tier job, each rule broken, a factory workflow on the label).

**Rationale:** End-to-end suites need more machine than GitHub's standard runners, and pre-merge they run a pull request's code, agent-written for factory PRs. The factory already knows how to run untrusted code on its own hardware: a firewalled user, rootless Docker, a container per job, and nothing in the job worth taking. The CI tier is that, for the project's CI, without the agent machinery.

---

## 2026-10-13: The factory's workflow policy scans local actions, and names its exceptions in factory.json

**Origin:** The pilot project (CD: "fix the checker upstream"). The policy, which Enablement step 10 makes required CI over every workflow in a repository, refused 6 jobs in the project's own `ci.yml`. Two refusals were for a local composite action the policy refused rather than read. Four were for the end-to-end jobs on a self-hosted runner outside a container. CD's runner choice for those jobs (GitHub-hosted, possibly larger runners, or an isolated self-hosted runner) is still open, so the checker had to support either without loosening anything.

**What happened:** A blanket rescoping (checking only the factory's own workflows) would have stopped the policy from catching a newly added self-hosted PR job, so each exception is named instead. The new settings live in a `policy` block in `factory.json`, which CODEOWNERS covers through `/.github/` and only `workflow_policy.py` reads.

**Changes made:**

1. **`bundles/factory/tree/workflow_policy.py`**:
   - **Local actions** (`uses: ./…`) resolve in the repository and are scanned. A composite action's steps join the calling job's, nested ones too, so every step rule reads them: docker, direct Claude Code, the agent jobs' checks, and the OAuth, App-key and fixture-secret confinement. Refused: a docker or JavaScript action, a path with no `action.yml` or outside the repository, a ref, an action that uses itself, nesting deeper than 8, and an agent step inside one. An agent job still runs no local action at all, as before.
   - **`policy.hosted_labels`**: the organization's own GitHub-hosted runner labels count as hosted, wherever the policy asks (the container rule, the App key's job, the fixtures job). Refused, regardless of case: a label GitHub gives every self-hosted runner (`self-hosted`, `linux`, `windows`, `macos`, `x64`, `arm`, `arm64`), a factory runner label, and anything that isn't a label.
   - **`policy.self_hosted_exemptions`**: exact `{workflow, job, reason}` entries. They lift only the container rule, and only for one of the project's own jobs. Never a factory workflow, a job on the factory's runners or an agent job, and never with a reason under 20 characters. An entry that names no job, or a job that runs hosted, is a violation, so the list stays exactly what it lets through. Each use prints a CI notice.
2. **`bundles/factory/tree/render.py`**: the `policy` block, like `stack`, is read at run time, not by a template.
3. **`bundles/factory/seed/factory.json`**: the empty `policy` block, with its `_doc`.
4. **`bundles/factory/tree/tests/test_render.py`**: `ProjectWorkflows`, run in a repository laid out as GitHub's: nested composite actions scanned, each unscannable kind refused, a local action in an agent job refused, the factory's secrets refused inside a local action, the organization's labels, an exemption lifting one named job and not a new one, an exemption never reaching the secret rules, and each exemption that can't hold.
5. **`process/factory.md`**: Enablement step 10 says the policy scans local actions, and when a project's own CI needs `policy.hosted_labels` or an exemption.

**Rationale:** The policy reads every workflow so that a job someone adds later falls under the factory's rules by default. Exceptions now live in a reviewed file with reasons, and the checker refuses any that stop being true. The secret rules have no exceptions at all.

---

## 2026-10-13: Factory Enablement: what CODEOWNERS must cover per profile, and the project's own CI

**Origin:** The pilot project's Enablement review. That project's session found that none of the files .NET and pnpm load just because they exist were code-owned, and that its existing CI would run factory PRs' code next to a secret.

**What happened:** Two of the factory's protections rest on CODEOWNERS covering every file a stack's tools load by existing. A revise or continued run installs a factory branch's dependencies outside the sandbox (`install.sh`: `dotnet restore`, `pnpm install`). The only guard there is `factory_branch.sh check` refusing any change to a CODEOWNERS path. The same files decide what the project's CI does with a factory PR. Enablement step 9 said "the test and build configuration" and nothing more specific. For .NET that set is wide: a project file can hook a target into restore, and any `.props`/`.targets` it imports can too. And factory branches live in the repository, so `pull_request` CI on a factory PR gets the repository's secrets. In the pilot project, the build step (PR code) ran before the step holding `SLEEVED_API_KEY`, and the end-to-end jobs ran on a self-hosted runner outside any container. Running the workflow policy on that repository found 6 violations in its own `ci.yml`, which Enablement step 10's required check would have hit on the first PR.

**Changes made:**

1. **`process/factory.md`** § Stack Profiles: "What CODEOWNERS must cover, per profile", the files each profile's tools load just because they exist, at any depth and in every casing a tool accepts. python-node: requirements, pyproject, setup, pytest and tox config, conftest, sitecustomize. dotnet-node: `*.csproj`, `*.props`, `*.targets`, `*.rsp`, the solution files, `global.json`, `nuget.config` in its three casings, the tool manifest, runsettings, `xunit.runner.json`, `.editorconfig`, `.globalconfig`. Node in both: `package.json`, `.npmrc`, and each package manager's own lockfile and files. Enablement step 9 points at it. Step 10 says to run the policy (which reads every workflow) before making it required, and warns that the project's existing CI runs agent-written code. Every job that builds, tests or lints a PR's code therefore holds no secret before or after it, uses `persist-credentials: false` and a read-only token, and runs on a hosted runner or in a container. A job that needs a secret runs the default branch's code.
2. **`bundles/factory/seed/tests/test_codeowners.py`**: `test_the_profiles_build_files` checks sample paths from the profile's list in the project's two directories (`factory.json`'s stack). New projects get it; existing projects keep their own copy.
3. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`**: the proof's Enablement-shaped CODEOWNERS covers both profiles' lists (and names Enablement step 9, not 7).

**Rationale:** "The test and build configuration" left each project to rediscover which files a toolchain executes by convention. The factory's own install step and the project's CI both depend on that list, so the profile that brings the toolchain now names it, and the seeded test holds a new project to it.

---

## 2026-10-13: Factory fixtures: a hosted job hands secret-sourced test fixtures to the agent job

**Origin:** The pilot project. Four of the pilot project's tests need card-art fixtures that CI fetches with a secret (`SLEEVED_API_KEY`), and the implement sandbox has neither the network nor the secret, so the `dotnet-node` profile left them out (`Category=External`). CD asked whether the factory could fetch the art itself ("can we wire this in as a service?"), chose option 3 of five (CD, 2026-10-13: a hosted fixtures job that hands an artifact to the agent job), and approved D2 rule 7 for it.

**What happened:** A service (`services.json`) was the wrong tool. It would have put a masked credential and two egress hosts into the code-writing stages, against the planning-only services rule (CD 2026-10-10) and D2 rule 2's empty network for implement. The chosen shape keeps the secret off the self-hosted host entirely. It is CI's own three steps (restore the cache, fetch on a miss, upload) in a job on a GitHub-hosted runner, and the agent job only downloads the result. Two GitHub Actions details shaped the templates. A job whose upstream job is skipped may be skipped too unless its condition says otherwise, so `publish` now states its own condition, as `report` already did. And an expression like `secrets.` with an empty name breaks the whole workflow, so the secret is read as `secrets['NAME']`, which stays valid when a project has no fixtures.

**Changes made:**

1. **`bundles/factory/tree/templates/factory-implement.yml`, `factory-revise.yml`**: a `fixtures` job, skipped when `fixtures.path` is empty. It checks out the default branch, restores `path` with `actions/cache` (v6.1.0) under `cache_key-<hashFiles(key_files)>`, and on a miss installs `apt` and runs `run` with the secret exported under its own name. Then it refuses fixtures that contain the secret (plain or base64) and uploads them as `factory-fixtures`. The agent job `needs` it, runs unless it failed, and downloads the artifact into `path` before the agent starts. `publish` states its condition explicitly. `report-failure` names a failed fixtures job.
2. **`bundles/factory/tree/render.py`**: `%{key?}` is an optional setting, which renders empty when `factory.json` doesn't have it. A project installed before the `fixtures` block keeps rendering without editing its settings.
3. **`bundles/factory/tree/workflow_policy.py`**: the fixtures job kind (a factory workflow's job named `fixtures`; a project's own `ci.yml` may use the name). It must be in the implement or revise workflow, on a GitHub-hosted runner, with no agent, container, environment or outputs. Its permissions are exactly `contents: read`, it checks out the default branch once without persisted credentials, and it uses only the checkout, cache and upload-artifact actions. Its one secret appears only as `${{ secrets['NAME'] }}` in a run step's `FIXTURE_SECRET`. No other job, and no workflow env, may reference that secret. `factory.json`'s fixtures values are checked for anything that would change the workflow text they render into: an expression, a quote, `..`, or a path without its command and cache key.
4. **`bundles/factory/seed/factory.json`**: the `fixtures` block, empty (path, run, secret, apt, cache_key, key_files), with its `_doc`.
5. **`bundles/factory/tree/tests/test_render.py`**: optional placeholders; a project without the block renders skipped fixtures jobs; a project with one renders them, names the secret only in the fixtures job, and passes the policy. The policy refuses the secret in an agent job, a factory-branch checkout, a self-hosted runner, outputs, another action, another secret, and settings that would change the workflow.
6. **`process/factory.md`**: D2 rule 7 (CD's sentence, with how the job does it). Enablement step 2 points at the `fixtures` block, and step 7 lists its secret as a read-only repository secret.

**Rationale:** The factory's boundary is that an agent job holds no credential beyond its own read-only token. Test fixtures that need a secret were the first thing that boundary kept out of a factory run, and the answer keeps the boundary: the privileged fetch happens in a trusted job, and only its non-secret result crosses over, as D1 already does for writes.

---

## 2026-10-13: A second factory stack profile, dotnet-node (.NET 10 and pnpm/Vite)

**Origin:** The pilot project (its session, at CD's request), which is .NET 10 with a pnpm/Vite web client, is installing the `factory` bundle, and its only profile was `python-node`. Under the pilot rule (CD, 2026-10-12) the fix goes straight into the bundle code.

**What happened:** A profile was written from `python-node` and proven against a clean archive of the pilot project in a local stand-in for the implement sandbox (the job image with no network, a read-only root, no HOME and a seccomp filter refusing `socket(AF_UNIX)`). That run found what the sandbox does to .NET. MSBuild's worker nodes talk over Unix sockets, so a solution's build fails in under a second with "Build FAILED, 0 errors" and leaves orphaned workers. No environment variable, SDK `MSBuild.rsp` or root `Directory.Build.rsp` overrides the `-maxcpucount` the dotnet CLI passes; only an explicit `-m:1` works, and `dotnet run` and `dotnet ef` ignore it. With `-m:1`, 5,565 of the pilot project's 5,573 tests pass there (4 are skipped, and the 4 that fail are card-art cases that need a secret), and tsc, vitest, the Vite build and both of its bundle gates pass too. `eslint .` fails on `scripts/*.mjs` and `perf/*.mjs` alone, which the pilot project's own lint never covers. With no HOME, `dotnet restore` writes NuGet's data into the working directory (`.local/share/NuGet/`), an untracked file that would stop the run's publish; `XDG_DATA_HOME` moves it. A second run started from a git repository and applied the asks to the pilot project (the card-art cases tagged `External`, eslint without `scripts/` and `perf/`, `.factory/` ignored). In it install, `verify probe` and `verify` all pass, `git status` stays empty, and no process outlives a command. It also showed a gap that predates the profile. Every job writes `.factory/` into the workspace, and the publish step refuses untracked files. The incubator gitignores `.factory/`, but Enablement never said to.

**Changes made:**

1. **`bundles/factory/tree/profiles/dotnet-node/`** (new): `Dockerfile` (python:3.12-slim-bookworm, because the plan and smoke templates call `/usr/local/bin/python3` by path; the .NET 10 SDK copied from `mcr.microsoft.com/dotnet/sdk:10.0` with `libicu72`; Node 22; pnpm 10.33.0 as a package, not corepack; Postgres 16 and pgbouncer). `install.sh` (`dotnet restore`, `dotnet tool restore` when there is a tool manifest, `pnpm install --frozen-lockfile`; .NET's home, the NuGet packages, the data directory (`XDG_DATA_HOME`) and the pnpm store go in `.factory/`; it sets no-node-reuse, no shared compilation, no telemetry or first-run certificate, and NuGet audit off in the sandbox). `test-services.sh` (Postgres only, the same lockdown checks, and a `ConnectionStrings__DefaultConnection` line). `with-test-services` (ports 5432 and 6432). `verify` (areas `dotnet` and `node`, plus `probe`; `-m:1` on every build; tests in the categories `Nightly` and `External` left out; `--print` tells the agent the `-m:1` rule).
2. **`bundles/factory/tree/tests/test_agent_job.py`**: `VerifyDotnetNode` covers the new profile's commands, areas and failures. The `Freeze` test reads the project's profile from `factory.json` instead of naming `python-node`; before this, it failed in any project on another profile, and these tests are required CI (Enablement step 10). All 269 tests pass in a project on `dotnet-node`.
3. **`process/factory.md`**: "Limits of this version" names both profiles. § Stack Profiles gains a table of the two profiles and what each needs of a project, says why `verify` leaves a build script's own gates to CI, and covers the sandbox's `-m:1` rule and end-to-end suites. The `stack.python`/`stack.node` slots stay, renamed only when a stack doesn't fit two directories, because renaming them changes every project's `factory.json`. Enablement step 2 requires `.gitignore` to cover the env file and `.factory/`, and says to render after choosing the profile: `factory-image` builds the chosen profile's `Dockerfile`, so the pilot project's render check failed until it re-rendered.

**Rationale:** The second stack is where the factory learns what "one kind of project" really varies in. The sandbox's Unix-socket block is invisible to Python and npm but breaks MSBuild silently, and only a run that imitates the sandbox finds it before a paid agent run does. Proof on a real runner is still `factory-smoke`, in the pilot project's Enablement.

---

## 2026-10-13: The factory import's patterns name no host

**Origin:** the import tool's rules, public in z-sdlc, listed the incubator's runner host by name as a pattern to flag; CD asked for it to go.

**Changes made:**

1. **`.claude/skills/zsdlc-import-factory/import.json`** — the host name is out of `specific`; private and VPN address ranges and home directories still catch host-specific text an import would add.

**Rationale:** a public file shouldn't name a private machine, even as a pattern. Release type: patch.

---

## 2026-10-12: One factory runner host serves several organizations

**Origin:** a second organization's factory will share an existing runner host rather than need its own machine (CD: "change setup.sh").

**What happened:** `host/setup.sh` used fixed names for its users, firewall tables and services, so a host ran one organization's runners; setting it up for a second would have reused the first's users and runner directories. Imported from quantile 6251b8c..07d9441.

**Changes made:**

1. **`bundles/factory/tree/host/setup.sh`** — `RUNNER_INSTANCE` (in `host.conf`) names a second organization's runners: users `factory-runner-<instance>` and `factory-planner-<instance>`, their own nft tables, firewall units and runner services, each isolated from the others as from the host. Without it the names are as before. Setup refuses, before changing anything, a runner directory registered to another organization; new runner users get subordinate IDs above every range already given out, not a fixed block that could collide on a fresh host; replacing the shared seccomp profile says so.
2. **`bundles/factory/seed/host/host.conf`** — documents `RUNNER_INSTANCE` and that each organization's limits come out of the same host.
3. **`bundles/factory/tree/tests/test_host_setup.py`** — the instance names, refused names, and the ownership guard.
4. **`process/factory.md`** — Enablement step 8: a host can serve several organizations; a planning database port is only ever the organization's own.
5. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`** — a copy of `process/factory.md` or a skill that the incubator committed from z-sdlc (`--to-incubator`) is recognized by z-sdlc's history, not reported as an edit made in the incubator; with a test.

**Rationale:** runner hosts are the costly part of the factory; letting organizations share one, each confined as strictly as from the host itself, removes the need for a machine per organization. Release type: minor (a new host setting).

---

## 2026-10-12: factory.md's Enablement starts from zero, and says what a stack profile is

**Origin:** with the bundle carrying everything an organization needs (the entry below), its Enablement still assumed Endless Galaxy's App, image, echo service and runners already existed (CD: the factory is an abstraction for anyone). Checking GitHub's documentation for the plan the factory needs corrected an earlier answer: a free organization isn't enough.

**Changes made:**

1. **`process/factory.md`** — Enablement starts from an organization (the runners are an organization runner group's), on GitHub Team or above for a private repository (environment secrets, `main`-only environments and rulesets), and says the production tier's required reviewer on a private repository needs Enterprise. New steps for the job image, the echo service, the App (`create_app.py`) and the runner host (`host/setup.sh`, `host.conf`); `bootstrap.py --apply` becomes its own step, after the placeholders are filled. The planning tier's database is optional. A new Stack Profiles section says what a profile's five files do, and that the interface keeps `python-node`'s shape until the first other profile generalizes it. The install table and limits match the bundle.
2. **`bundles/factory/`** — imported from quantile c6520ae..6251b8c: `create_app.py` and the tests cite the new step numbers; `create_app.py` writes the App's private key to the home directory by default, outside any checkout; `bootstrap.py` compares with the seed's exact placeholders, so an organization named like one isn't locked out. The seeded `planning.json` says its database is optional, and the seeded `tests/test_codeowners.py` cites step 9.

**Rationale:** Enablement is the one path a new organization follows, so it has to cover everything that path needs, in an order where each step has what it uses. Release type: patch.

---

## 2026-10-12: The factory bundle sets up from zero: host setup, the App, the echo service, placeholders

**Origin:** the factory is meant to be usable by anyone who installs z-sdlc, not only by CD's organization (CD). The bundle assumed Endless Galaxy's App, job image, echo service and runner host, and the host setup wasn't in it at all.

**What happened:** imported from endless-galaxy-studios/quantile ec4b0d9..c6520ae. Quantile's commits made each piece of the factory read the project's own settings, and the import proof (an empty project with the seed's placeholders) found that the host setup stopped outside a checkout with an `origin`; fixed in quantile and imported.

**Changes made:**

1. **`bundles/factory/seed/factory.json`** — `app`, `image` and `smoke.echo_host` are placeholders (`your-factory-app[bot]`, `ghcr.io/your-org/factory-job`, an all-zero digest, `echo.example.invalid`) instead of Endless Galaxy's values; the runner labels and environment names stay as shared defaults.
2. **`bundles/factory/tree/bootstrap.py`** — checks first that `factory.json` names the project's own App, image and echo service, and applies nothing until it does, naming the Enablement step that fills each.
3. **`bundles/factory/tree/create_app.py`** (new) — creates the factory's GitHub App in an organization through GitHub's manifest flow, with exactly the four permissions `bootstrap.py` checks and no webhook; writes its bot user into `factory.json` and its private key to a new mode-600 file.
4. **`bundles/factory/tree/echo/`** (new) — the echo service smoke calls: `worker.js` for Cloudflare Workers, `server.py` for any container host behind HTTPS.
5. **`bundles/factory/tree/host/setup.sh`**, **`seccomp-bwrap.json`** and **`bundles/factory/seed/host/host.conf`** (new to the bundle) — the runner host setup: runner labels and group from `factory.json`, the host's own settings (organization, home directory, LAN resolver, probe ports, a planning database port, runner counts and limits) from `host.conf`, each with a default; `--print-settings` resolves them without root. The production tier's host scripts stay per project.
6. **`bundles/factory/tree/planning-services.sh`**, **`templates/factory-plan.yml`**, **`templates/factory-revise-doc.yml`** — the planning database is optional (D3): with none in `planning.json`, the plan and revise-doc stages run without one.
7. **`bundles/factory/tree/templates/factory-smoke.yml`**, **`implement_tools_check.py`** — smoke's write probe uses directories it creates, not one project's layout.
8. **`bundles/factory/tree/tests/`** — the tests read the project's own `factory.json` instead of Endless Galaxy's App and values, so every adopter's CI runs them unchanged; new tests for the App creation, the echo server, the host settings and the optional planning database.
9. **`.claude/skills/zsdlc-import-factory/`** — `host/` is bundle code except the production tier's two scripts, and `host/host.conf` is a seed. A file z-sdlc's history never had (excluded at the last import, bundle code under today's rules) is reported as added, not as z-sdlc's removal; with a test. The home-directory pattern no longer matches `api.github.com/users/`.

**Rationale:** an adopter now fills four placeholders with its own App, image and echo service, each made by a script or file in the bundle, and sets up its runner host from the same checkout; nothing in the bundle presumes Endless Galaxy. Release type: minor (new command surface: `create_app.py`, the host setup).

---

## 2026-10-12: Public and generic: project-internal material leaves z-sdlc

**Origin:** z-sdlc is public and for anyone, and the factory is meant to be an abstraction every adopter can use (CD). A review of what z-sdlc publishes found no credentials, but it did find CD's own projects' internals: a runner host's network addresses in the factory's smoke template, the factory's design record (one project's hosts, operations, costs and history), another project's product material, and private projects named as examples in files every project installs.

**Changes made:**

1. **`process/factory.md`** — each of D1-D5 gains a Why section (the context and the options considered), written for any adopter. The factory's design record and rollout plan, which held one project's operations, leave `docs/current_work/ideas/` for CD's private documentation.
2. **`bundles/factory/`** — smoke's isolation probe takes the runner host's own addresses from `factory.json`'s new `smoke.host_probes` (empty in the seed) and always adds the default Docker bridge and rootless gateways; the template no longer carries one host's addresses. Comments and test fixtures that named a host or project are generic, and code cites `process/factory.md` instead of the design record.
3. **Installed files** — `knowledge/architecture/model-tier-strategy.yaml`'s survey, two design knowledge files' sources, the examples in `process/production-gates.md` and `process/deliverable_lifecycle.md`, `skills/sdlc-migrate`, `skills/sdlc-audit/references/session-reading.md`, and `templates/pr_description_template.md` (its worked example is now an orders API) no longer name private projects or people.
4. **`docs/current_work/ideas/`** — the two pending handoffs (an ADR supersession gate, and option previews for `sdlc-explain`) keep their proposals without the source projects' details; the 155 KB reference page from another project is removed. `changelog-archiving_design.md` cites its numbers without naming projects.
5. **Framework-development tooling** — the adapter-installation audit says "the target" for the project it audits; the import tool flags private and VPN address ranges and home directories instead of names.
6. **`skeleton/contract_changes.yaml`** — 0019 and 0020's `changelog_ref` match the factory debut's heading; descriptions don't name projects.

**Rationale:** what a public framework ships, and what its examples teach, should hold for any project; CD's own projects belong in CD's private records. Release type: patch.

---

## 2026-10-12: zsdlc-import-factory: importing the factory from quantile is a command

**Origin:** CD decided (2026-10-12) that quantile incubates the software factory and z-sdlc imports it, and asked for the import tool proposed then.

**What happened:** the session that built the `factory` bundle imported it from quantile by hand five times. Each time, new files had to be remembered and new seed settings added by hand. Quantile's copy of `process/factory.md` fell a clause behind z-sdlc's, and the guard tests carried quantile's own CODEOWNERS into the bundle. The proof that an import installs and works lived in a throwaway script.

**Changes made:**

1. **`.claude/skills/zsdlc-import-factory/`** (new, source-only) — `SKILL.md` (report, apply, prove, record), `import.json` (which of quantile's `.github/factory/` files are seeds, which are excluded, settings whose keys are project data, patterns of quantile-specific text, the last imported commit), and `scripts/import_factory.py`. The script reads quantile at a commit, never its working tree. It reports bundle code added, changed and removed; JSON seed settings the bundle's seeds lack; text seeds quantile changed; quantile-specific text an import would add; and whether quantile's copies of the bundle's skills and process doc still match. `--apply` writes the bundle code and records the commit. Since later reports compare against that commit, it refuses while a [fix first] item is open (a missing seed setting, a quantile edit to z-sdlc's text). An added or removed file, quantile-specific text or a changed text seed needs `--accept`. `--prove` installs into a clone of quantile and into an empty project, then renders every template, checks the policy and runs the tests. `sdlc-reviewer` found that applying could hide open items. That's fixed in the script, and its other findings are fixed in the skill.
2. **`tests/test_import_factory.py`** (new) — 19 tests against fixture repositories, including a z-sdlc fix kept and handed to quantile, a file z-sdlc added, a conflict merged in quantile, and a file quantile deleted.
3. **`CLAUDE.md`** — the `factory` bundle is imported from quantile. Edited here instead: the skills, `process/factory.md`, the seeds, and a fix found in a project that installed the bundle, which goes straight into the bundle code (CD, 2026-10-12, for the ChronoCore pilot).

Because of that last rule, the script compares each bundle code file three ways: quantile now, the bundle now, and quantile at the last import. Quantile's changes are imported. z-sdlc's own changes are kept, listed as `ahead`, and `--to-incubator` writes them (and newer skills and process docs) into quantile's working tree to commit there. A file changed on both sides is a conflict: merge in quantile, then `--apply --accept`. The proof installs the bundle with z-sdlc's own changes kept.

**Proof:** against quantile `3b1ba7d` the report finds the bundle in sync and the proof passes (17 workflows, policy, every test). `import.json` records `3b1ba7d` as the last import.

**Rationale:** the pilot will bring changes from two directions; every import now sorts, checks and proves the same way. Release type: patch (framework-development tooling; nothing installs into projects).

---

## 2026-10-12: Debut the factory bundle: the software factory, promoted from quantile

**Origin:** the factory's rollout (`docs/current_work/ideas/software-factory_rollout-design.md`). The software factory incubated in quantile (F13): issue-driven agent stages from triage to a draft PR, on self-hosted runners, with CD approving every plan, merge and production step. Steps 1-3 made it installable: shared scripts, workflows rendered from a per-repository `factory.json`, and the `python-node` stack profile. Step 4 moves it into z-sdlc as an opt-in bundle, with its design rules promoted to a process doc (F22); step 5 adds the GitHub setup. CD decided (2026-10-12) that quantile keeps incubating it and z-sdlc imports it, and that a fix found in a project that installed the bundle goes straight into z-sdlc.

**What happened:** before the release, the bundle met quantile's live runs. D17, the first live rollback gate, found that the deploy check refused the factory's own job image under `.github/`. Moving the guard tests upstream found that a project without a production tier could publish no plan. Renaming the org's runner groups showed that a runner-group API update can empty a group's repository list. Smoke's stand-in service, httpbin.org, failed it for an afternoon. Each is fixed here.

**Changes made:**

1. **`bundles/factory/tree/`** — the factory's code as quantile has it (83 files): the scripts, guards, schemas, tool policies, sandbox settings, workflow templates, `render.py`, `workflow_policy.py`, the `python-node` profile, `bootstrap.py` and the tests. Installed at `.github/factory/` and refreshed on every migration. The guard tests use a sample CODEOWNERS and operations catalog, so they ship upstream; the publish guards treat a missing catalog as no production tier. `bootstrap.py` checks a repository's GitHub setup against Enablement and, with `--apply`, creates the labels, environments and runner-group entries (secrets, the App, CODEOWNERS and the ruleset stay report-only). Smoke's injection probes call `factory.json`'s `smoke.echo_host` instead of httpbin.org.
2. **`bundles/factory/seed/`** — what becomes the project's, written once where absent: `factory.json` (Endless Galaxy's shared defaults, including `smoke.echo_host`; the `stack` block is set per project), `planning.json`, `services.json`, `triage-policy.md`, a short `README.md`, and `tests/test_codeowners.py` (the project's CODEOWNERS against the guard). Not in the bundle: quantile's production tier (the broker, its operations and their tests), its host setup and its Django-specific database access list.
3. **`skills/sdlc-triage`, `skills/sdlc-implement`, `skills/sdlc-revise`** — the stage skills, made generic. Project specifics moved to the project's `.github/factory/triage-policy.md`; the App's login comes from `factory.json`, and commands and test services from the stack profile. An `sdlc-reviewer` pass found 7 major and 15 minor findings; two minors are left as follow-ups (the thread-reading rules repeated across the three skills, and where the sandbox paragraphs sit).
4. **`process/factory.md`** — D1-D5's rules, forbids, costs and revisit-when, the label set and Enablement. D4 rule 13: no infrastructure pattern applies under `.github/`, whatever a file there is called. D4 rule 16: without a production tier a plan has no gates, CD's included. Enablement names the shared runner group `factory-pool` and the per-project `factory-pool-<project>-prod`, gives the runner-group API's rule, and points steps 2 to 8 at `bootstrap.py`.
5. **`skeleton/manifest.json`** — `bundles.factory`; bundles may now carry `tree`, `seed`, `render` and `requires` (`skeleton/contract_changes.yaml` 0019; the debut is 0020). `sdlc-initialize` and `sdlc-migrate` install trees and absent seeds, run the render, hash tree files (never seeds) and offer an adopt path to a project that already has the tree. `process/path-mappings.md`, `process/commands.md`, `review-fix-loop.md`'s mirror table and `headless-mode.md`'s gate sites cover them.

**Proof:** installed into quantile, the bundle changes nothing and the workflow policy passes. Installed into an empty project with an Enablement-shaped CODEOWNERS, all 17 workflows render, the policy passes and every test passes (`zsdlc-import-factory --prove`). Quantile's live runs exercised the rest: smoke (all eight jobs, on the new echo host), a rollback gate that ended `rolled-back` as designed, and the generic triage and implement skills on a throwaway issue.

**Adapter action:** none; the bundle's files are code and settings, not knowledge-layer references (treat `bundles/factory/` like scripts).

**Rationale:** the factory is meant for every project (F22). Steps 1-3 left its project-specific values in a settings file and a stack profile, so the rest ships as one upstream copy. Release type: minor on its own (an opt-in bundle debut and additive manifest fields).

---

## 2026-10-12: Adapter fields and the improve route take the z-sdlc name [contract-change]

**Origin:** the rename to z-sdlc (entry below) left three names that other repositories store: two adapter fields and the improve loop's route value.

**What changed:**
- `process/adapter-lifecycle-protocol.md`, `process/knowledge-routing.md`, `sdlc-initialize`, `sdlc-migrate`: adapters mark themselves with `zsdlc_adapter` and declare `supported_zsdlc_version`. The pre-rename keys `ccsdlc_adapter` and `supported_ccsdlc_version` stay readable, and a migration that refreshes a project's adapter entry writes the new key and drops the old one.
- `sdlc-audit` improvement mode: the framework route and section are `z-sdlc`; factories and reports from before the rename call them `cc-sdlc`, and the two are the same route.
- `skeleton/contract_changes.yaml` 0018 records it.

**Adapter action:** declare `zsdlc_adapter` and `supported_zsdlc_version` (neuroloom-sdlc-plugin does as of this change). A factory that stores the route (quantile's improve loop) accepts both values in its schema and ledger.

**Rationale:** Every reader accepts both names, so an adapter or ledger written before the rename keeps working, and nothing has to change in lockstep. Release type: major, with contract 0017 in the same release.

---

## 2026-10-12: The framework is called z-sdlc everywhere

**Origin:** CD (2026-10-12): every cc-sdlc reference becomes z-sdlc. The `sdlc-*` skill and file names and "SDLC" stay.

**What changed:**
- Every skill, agent, process doc, template, knowledge file, bootstrap file and design doc names the framework z-sdlc (Z-SDLC in titles).
- The temporary clone paths are `/tmp/z-sdlc-bootstrap`, `/tmp/z-sdlc-lite-bootstrap` and `/tmp/z-sdlc-migrate`, and the source placeholder is `[z-sdlc-path]`. `sdlc-initialize` also accepts `/tmp/cc-sdlc-bootstrap` from a BOOTSTRAP.md copied before the rename, and looks for a local copy under both names.
- The framework-development skills are `zsdlc-audit`, `zsdlc-audit-adapter-installation`, `zsdlc-create-skill`, `zsdlc-ingest` and `zsdlc-research`.
- Unchanged on purpose: this changelog's past entries and the changelog archive (`archive --upstream` matches a project's copied entries by their dated headings, so those must stay as written), past `contract_changes.yaml` entries (append-only), and the old repository URL in `sdlc-migrate`'s `source_repo` rewrite. The adapter fields and the improve loop's route value are renamed in the next entry, with compatibility.

**Rationale:** One name for the framework in everything it installs. Projects get the new text at their next migration (direct copies). Release type: patch.

---

## 2026-10-12: The framework moved to endless-galaxy-studios/z-sdlc

**Origin:** CD moved the repository from `Inpacchi/cc-sdlc` into the Endless Galaxy Studios organization and renamed it `z-sdlc` for branding. The `sdlc-*` names inside stay.

**What changed:**
- `BOOTSTRAP.md`, `BOOTSTRAP-LITE.md`, `README.md` and the `.sdlc-manifest.json` template point at `https://github.com/endless-galaxy-studios/z-sdlc`, for cloning and for the raw bootstrap file.
- `skills/sdlc-initialize`: clones from the new URL, and looks for a local copy under the new name first (`~/Projects/z-sdlc`, `~/z-sdlc`, `../z-sdlc`), then the old one.
- `skills/sdlc-migrate` § 4.5 step 1a: a project whose `source_repo` names `github.com/Inpacchi/cc-sdlc` (HTTPS or SSH) gets it rewritten to the same form at the new home. Any other value, such as a fork or a local path, is left alone.

**Rationale:** GitHub redirects the old URL, but only until something takes the old name, and every install's manifest still names it. Migration fixes each project's record, so no project has to be edited by hand. A migration runs the project's installed `sdlc-migrate`, so the rewrite happens at the first migration after one installs this version; the redirect covers the time between. Release type: patch.

---

## 2026-10-11: Changelog archiving: project-only changelogs, quarterly archive files

**Origin:** CD decided the process changelog gets archived (2026-10-11) and chose all four parts of `docs/current_work/ideas/changelog-archiving_design.md`. [contract-change] (adapter exemption list; contract 0017)

**What happened:** cc-sdlc's changelog was 644 KB and nothing archived it. Every project's changelog started as a copy of it, so projects carried the framework's whole history plus their own (quantile 735 KB). CD chose: project changelogs hold only their own entries from now on; old entries move by calendar quarter once the file passes about 150 KB; a script does it; and existing installs are archived by their next migration without asking, which makes the release major. Then, seeing that quantile would keep 96 KB of copied cc-sdlc entries from July on: existing installs move every copied cc-sdlc entry out, whatever its quarter.

**Changes made:**

1. **`skills/sdlc-archive/scripts/changelog_archive.py`** (new; the first script shipped in a skill) — `archive` moves every entry dated before the previous quarter to `changelog-archive/YYYY-Qn.md` when the file is over the threshold, byte for byte and in its order, adds one pointer line, and writes nothing unless every entry is present exactly once across the files before and after. `check` fails when there's something to move and names the command. With `--upstream` (cc-sdlc's changelog and archive files), entries copied from cc-sdlc move too, whatever their date and the file's size; a copy is an entry whose `## YYYY-MM-DD: Title` line matches one upstream. `init` writes a new project's changelog: the header and one install entry. Splits on `## YYYY-MM-DD:` headings outside code fences. Tests: `tests/test_changelog_archive.py`.
2. **`process/changelog-archive/2026-Q1.md`, `2026-Q2.md`** (new) — cc-sdlc's own 203 entries from March to June, moved unedited. The live file is 171 KB with 46 entries (Q3 and Q4): over 150 KB, with nothing older than the previous quarter, so it stays until January. 15 old entries have no `---` before the next one; kept that way, so `release.yml` sees no old entry as new.
3. **`skills/sdlc-initialize/SKILL.md`** — Phase 1b writes the changelog with `init` from the source at `HEAD` instead of copying it; the archive is never installed; the changelog stays out of `installed_files`.
4. **`skills/sdlc-migrate/SKILL.md`** — §1.2 reads cc-sdlc's archive at the target tag when the project's version predates the live file; §1.3 rows for skill scripts (direct copy) and the archive (not installed, never overwritten); §2.1 copies `process/*.md` top level only and copies skill scripts; §2.1a ignores archive paths; new §4.5c runs `archive --upstream` (cc-sdlc's changelog and archive at the target tag) on the project's changelog every migration, automatically, so copied cc-sdlc entries leave and old quarters follow; back-fills skip never-overwrite files; the report lists what moved.
5. **`skills/sdlc-archive/SKILL.md`** — the inventory runs a dry run, the approval table gets a changelog row, step 8a runs it, and a red flag forbids moving entries by hand.
6. **`process/path-mappings.md`**, **`process/README.md`**, **`process/adapter-lifecycle-protocol.md`**, **`agents/sdlc-compliance-auditor.md`** — the archive is project-owned, never overwritten, never installed from cc-sdlc, and exempt from adapter transformation and the phrasing scan.
7. **`skeleton/manifest.json`** (the script listed; a not-installed note), **`skeleton/contract_changes.yaml`** (0017, `type: other`), **`CLAUDE.md`** (the consistency glob covers `skills/*/scripts/*.py`), **`.github/workflows/changelog.yml`** (new: the tests and `check`, on change and each quarter's first day; it never archives by itself), **`.claude/skills/ccsdlc-audit*`** (exempt lists; a project's changelog no longer holds cc-sdlc's entries).
8. **Paired adapter change:** `neuroloom-sdlc-plugin` `ddcc382` exempts `process/changelog-archive/*.md` in the transformer, the pattern rules, the post-operation audit and `sdlc-port`'s remapping.

**Rationale:** the framework's history belongs to cc-sdlc, where migration already reads it; a project's changelog is its own record. Moving whole quarters unedited keeps every entry findable by date, and a script that proves nothing was lost is safer than an agent copying 600 KB by hand. `release.yml` needs no change: it takes entries present now but not at the previous tag, and archiving only moves old ones. The one gap: an entry added after a tag and backdated into an already archived quarter would miss that release's notes.

---

## 2026-10-11: Migration never overwrites a project's changelog

**Origin:** sizing the changelog for archiving (CD asked for it to be archived, 2026-10-11). Every project's changelog turned out to be a full copy of cc-sdlc's history plus its own entries (quantile: all 199 cc-sdlc entries from March to May, and 54 entries of its own).

**What happened:** `sdlc-migrate` treated `process/sdlc_changelog.md` like any other process doc: a direct copy from upstream. Drift detection caught the project's edits, so on a tracked install every migration raised a hard three-way prompt over a file every project edits by design; on an install from before `installed_files`, the first migration had no drift data and would have copied over the project's own entries.

**Changes made:**

1. **`process/path-mappings.md`** — `process/sdlc_changelog.md` joins the Project-Specific Files (Never Overwrite) list.
2. **`skills/sdlc-migrate/SKILL.md`** — the changelog is excluded from direct copies (§1.3's table, §2.1's Step 0 and list); drift detection skips every never-overwrite file, since their edits are expected; new §4.5b prepends one entry recording the migration (version, the upstream entries applied, the project's decisions) instead of copying upstream entries; § Preserved lists it.

**Rationale:** the project's changelog is the project's record; the framework's history already lives in cc-sdlc, where §1.2 reads it. Archiving old entries (CD's decision) is a separate, larger design, in `docs/current_work/ideas/changelog-archiving_design.md`.

---

## 2026-10-11: A headless run stops before its time limit, not at it

**Origin:** the software factory's "work survives no stop" follow-up (`docs/current_work/ideas/software-factory_handoff.md`). quantile's D14b full-tier plan ran past its 2-hour step limit and was killed: about 2 hours of work, no result, no transcript.

**What happened:** headless callers stop a run at a time limit, but nothing told the run how long it had, so it could only be killed. A killed run returns nothing: no document, no notes, no result for the caller to act on.

**Changes made:**

1. **`process/headless-mode.md`** — § Ending a Headless Run: a caller that kills the run at a time limit gives it a time budget (how long, and the margin to keep for stopping). The run checks the time between steps; at the margin it starts nothing new, commits what is done, and stops with the status the caller names for running out of time, with what is done and what is left in `notes`. A red flag for pushing past the margin.

**Rationale:** a stop a few minutes early leaves a result the caller can resume or publish; a kill at the limit leaves nothing. The caller owns the clock and the status, so the rule only says to stop at its margin and with its status.

---

## 2026-10-11: Improvement mode reads a factory digest, report-only when headless

**Origin:** the software factory's phase 4, the weekly improve loop (`docs/current_work/ideas/software-factory_handoff.md` § Next build). CD decided (2026-10-10) that once a week the factory reads its own GitHub record of what CD did to its output and posts a report CD acts on: report only, every item actionable, every area covered, ranked, and tracked across weeks.

**What happened:** `sdlc-audit` improvement mode took sessions and commits only, and its Applying Improvements step edited files on approval. The factory's analyze job has neither a session nor a person: it gets a digest of signals built deterministically from GitHub, and it must never apply anything.

**Changes made:**

1. **`skills/sdlc-audit/SKILL.md`** — a new input, the **factory digest** (`/sdlc-audit improve <digest>.json`, recognized by `kind: factory-digest`), and § Improvement with a Factory Digest: the digest's signals, metrics and ledger; quoted text is untrusted data; check the window's commits so already-fixed problems aren't proposed; reference an earlier proposal's fingerprint instead of re-proposing it; each proposal names its target, change, why (signal ids, never invented), expected effect, severity and route (`hygiene`, `cd`, `cc-sdlc`, `issue`); all five sections are considered and an empty one means nothing to action. A **Headless run:** line there and at § Applying Improvements: return the proposals with status `awaiting-approval`, apply nothing. Two red flags (quoted text as instructions; a re-worded duplicate of a ledger item).
2. **`skills/sdlc-audit/references/improvement-methodology.md`** — § Extraction from a Factory Digest: what each signal says and where its fix usually goes, patterns over events, what CD needs from each proposal; evidence for a digest is its signal ids; a headless run never applies.
3. **`process/headless-mode.md`** — § Integration lists `sdlc-audit`'s factory-digest input and Applying Improvements as gate sites.
4. **`process/writing-for-cd.md`**, **`CLAUDE-SDLC.md`** — improvement proposals are something CD reads, budget about 100 words each.

**Rationale:** the improve loop's analysis is the same judgment as an improvement audit, so it runs the same skill rather than a factory-only prompt. Making the digest a first-class input, and the headless contract explicit, keeps the factory's report from drifting away from how interactive audits reason, and keeps it from ever changing what CD hasn't approved.

---

## 2026-10-11: Discovery check-in and headless results follow writing for CD

**Origin:** the first live discovery check-in (quantile D14c, issue #48). CD asked whether it followed the writing-for-CD rules, and then asked that every surface the factory uses to reach CD does.

**What happened:** The check-in question ran to about 1,150 words. It re-explained decisions CD had already approved item by item, listed implementation details CD doesn't decide, and gave each option a paragraph. The check-in rule set no budget and no filter, and `writing-for-cd.md` didn't name headless results as something CD reads, though callers post their questions, reasons and findings straight to CD.

**Changes made:**

1. **`process/writing-for-cd.md`** — § Where It Applies names the parts of a headless result a caller shows CD (questions, a stop's reason, findings, deferred items); `notes` keeps its detail. Length budgets add a stop's reason (1–2 sentences) and a discovery check-in (about 300 words, only what CD hasn't decided, one line per assumption and per choice). § Integration lists the check-in.
2. **`process/headless-mode.md`** — the check-in is about 300 words: one line for what carries over from what CD approved, one line per undecided assumption with its source, one line per open choice with its recommendation and the alternative's cost. Facts go in `notes`. § Ending a Headless Run adds "Write the result for CD where CD will read it".
3. **`skills/sdlc-plan/SKILL.md`** — the check-in block matches.
4. **`CLAUDE-SDLC.md`** — § Writing for CD covers what a headless caller posts, and its budgets name the check-in.
5. **`process/writing-for-cd.md`** — fixes mirror drift found by the consistency check. The Completion Report source block gets the Add-ons and Follow-ups lines that `sdlc-execute` and `sdlc-lite-execute` gained with add-ons (2026-10-09), so source and copies match again.

**Rationale:** a check-in CD can't read in a minute gets skimmed, which defeats the point of asking. Headless results are the factory's main voice to CD, so they get the same budget as everything else CD reads.

---

## 2026-10-10: Discovery check-in — a headless spec run can confirm its basis with CD before writing

**Origin:** the software factory's full-tier test (quantile D14b, issue #47), and CD's direction to have the spec stage ask its discovery questions.

**What happened:** Three D14b spec runs reached discovery. One stopped with a real question (live's late 5m bars break the parity bar under Rule C). The other two settled all of discovery from D11b's records, never asked, and wrote specs that didn't address that problem. The headless DISCOVERY-GATE counts questions the records already answer, so a run with rich history never stops. That drifts from the factory's decision (F18) that the full-tier spec stage has a discovery conversation with CD.

**Changes made:**

1. **`process/headless-mode.md`** — § The Rule adds the **discovery check-in**, a caller option and the one exception to "ask what blocks the next step, and no more". When the caller's prompt asks for one, `sdlc-plan` stops once with `needs-input`, after the DISCOVERY-GATE and FAR gate pass and before the spec is written. The stop carries one question, "is this the right basis for the spec?", listing the assumptions with their sources and the open choices with recommendations. It is not a batch, and it happens once per deliverable. The answered-question red flag names the exception, and § Integration lists the new gate site.
2. **`skills/sdlc-plan/SKILL.md`** — a **Discovery check-in** block as the last step before step 2, with its **Headless run:** line. The DISCOVERY-GATE's no-batching rule says the check-in isn't a batch. **Headless restart** gains a bullet (CD answered the check-in → apply it, start at step 2, never repeat it), and `notes` record whether it was asked and what CD answered.

**Rationale:** confirming the assumptions costs CD one reply, while a wrong assumption found later costs a whole spec run. It's opt-in, so callers that don't want the stop keep today's behavior. This is new contract surface (a caller option in the headless contract), so it's a minor bump when CD cuts a release.

---

## 2026-10-10: Production gates — fixes from the convention review

**Origin:** an `sdlc-reviewer` pass over the production-gates change (the entry below), the same day.

**What happened:** The new gate text left four gaps: lite execution still said it commits once; the review loop before a gate ended with step 2's hand-off to step 3, which would skip the rest of the plan; a plan with production work inside a phase (D11b's shape) had no stop at execution; and the interactive gate put a runbook and a question in one turn.

**Changes made:**

1. **`skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`** — the review before a gate emits its own REVIEW-GATE line and proceeds to the gate, not to step 3 (past the cap at CD's direction, with the open findings recorded); every loop's open minors and feedback go in the result doc; the gate is presented as a completed message before the question, and the report-back values are asked once it's done; a phase holding production work is triaged REVISE_PLAN and never dispatched; gate rows are never dispatched; the review after a gate starts at round 1. Lite: the per-gate commit uses step 4's format, and the "commits once" lines say so.
2. **`process/production-gates.md`** — no phase after a gate starts before it's done; approving a deploy gate authorizes deploying before Validated, and the deliverable stays In Progress; typed parameters defined; push the branch before a gate whose steps use `${head}`.
3. **`process/headless-mode.md`** — `production-gates.md` § At a Gate joins the gate-site list; the approval row says the next run receives the gate's result.
4. **`skills/sdlc-lite-plan/SKILL.md`, `skills/sdlc-plan/SKILL.md`** — reviewers check each gate in both; "catalog patterns".
5. **`templates/planning_template.md`** — the example gate sits between Step 2 and Step 3, matching its "After: Step 2".

**Rationale:** each gap would have shown up the first time a plan reached a gate: an execution ending early after the pre-gate review, or an older plan's deploy dispatched to an agent.

---

## 2026-10-10: Production gates — production work happens only in gates between phases

**Origin:** the software factory's gap 1 (`docs/current_work/ideas/software-factory_handoff.md` § Gaps). quantile D11b's plan mixed a deploy into a phase ("Phase 3: code + Deploy step 1"), so nothing running plans unattended could tell which steps needed production. CD decided the factory gets a production-capable runner with per-step approval; the framework half is the plan structure every project uses, with or without a runner. Cross-checked with a Fable advisor and Codex (`gpt-6-astra`, max effort).

**What happened:** Plans had no place for production work. It sat inside phases, where an execute run would either do it (a live-system change no headless run may make) or skip it silently. Execution's review loop also ran only after the last phase, so a deploy in the middle of a plan would have shipped unreviewed code.

**Changes made:**

1. **`process/production-gates.md`** (new) — what a gate is (production work between phases, done by CD or the project's production runner after CD approves, never by an agent); the gate section (runbook, report-back fields, rollback, optional `gate-ops` block); gates don't count toward the phase limit; the last item is a phase; a review loop and commit before every gate; interactive and headless behavior at a gate and after it; the optional operations catalog with its placeholders and two approvals.
2. **`templates/planning_template.md`, `templates/sdlc_lite_plan_template.md`** — a gate section between phases and gate rows in the Phase Dependencies table.
3. **`templates/result_template.md`, `templates/sdlc_lite_result_template.md`** — a Gates section: outcome, when, done by, report-back values.
4. **`skills/sdlc-plan/SKILL.md`, `skills/sdlc-lite-plan/SKILL.md`** — production work goes in gates; gates don't count toward the 7- or 4-phase limit; reviewers check runbook, rollback and report-back; the Approval Brief lists every gate. A red flag each.
5. **`skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`** — before a gate: the review loop over the work since the last gate, then a commit (lite commits once per gate). At a gate: interactive shows CD the gate; headless stops with `awaiting-approval`, the gate named in `stage` (and a `gate` field when the caller's schema has one). The headless restart after a gate records its result or stops with `needs-input`. The completion review covers the work after the last gate. Three red flags each.
6. **`process/headless-mode.md`** — a production gate is an approval gate whose action plan is the gate's steps; the execute skills' gate-site entries name it.
7. **`skeleton/manifest.json`, `process/README.md`** — the new process doc.

**Rationale:** Production work is the riskiest part of a plan and the one part an agent must never do on its own. Giving it a fixed place makes it visible at plan approval, approvable at the moment it happens, reversible by a stated rollback, and reviewable before it ships. The same structure serves a project where CD runs every gate by hand and one where a production runner does it after CD's approval. Release: minor (a new template structure and process convention, additive).

---

## 2026-10-09: Dependencies between deliverables, and splitting a deliverable

**Origin:** quantile D11. D11 split into D11a → D11b → D11c, but the split and the dependencies lived only in prose, so D11a dropped out of sight while D11b was planned against it (`docs/current_work/ideas/prerequisite-tracking_handoff.md`). The software factory also needed a split it could act on (`software-factory-gaps_design.md`, gap 2). CD approved building both together, cross-checked with Codex and Fable.

**What changed:**
- **Catalog:** a `Depends on` column in the deliverable catalog (`skeleton/manifest.json` template, `skills/sdlc-initialize` seed), with a Notes bullet on its format.
- **`process/deliverable_lifecycle.md`:**
  - **§ Dependencies:** where dependencies are recorded (the catalog column; a deliverable ID in a plan's Phase Dependencies row gates that phase), who fills them, and what checks them.
  - **§ Splitting a Deliverable:** split records, part rows, the parent as umbrella, one level only.
- **`templates/split_record_template.md` (new):** the document CD approves for a split. Its parts table carries name, tier, dependencies, a reused spec and scope.
- **`templates/planning_template.md`, `templates/sdlc_lite_plan_template.md`:** a phase's Depends On may name a deliverable.
- **`skills/sdlc-plan`:**
  - a § Splitting a Deliverable procedure (propose parts, write the split record, register the parts, approval; headless stops with `awaiting-approval` and the split record);
  - the Feasibility Gate and the phase limit point to it;
  - registration fills `Depends on`, and existing deliverables report unplanned prerequisites.
- **`skills/sdlc-lite-plan`:** uses an existing ID (a split part) instead of claiming one, fills `Depends on`, and reports unplanned prerequisites.
- **`skills/sdlc-execute`, `skills/sdlc-lite-execute`:** at load, run only phases no unfinished prerequisite gates. Interactive runs ask CD whether to continue; headless runs stop with `needs-input`.
- **`skills/sdlc-status`:** shows deliverables waiting on a prerequisite, split parents, and a **Forgotten Prerequisites** section.
- **`skills/sdlc-audit/references/compliance-methodology.md`, `agents/sdlc-compliance-auditor.md`:** flag missing IDs, cycles, Draft prerequisites of active work, and split parents without a split record.
- **`process/headless-mode.md`:** split approval is an approval gate, and the execute prerequisite stop is listed in § Integration.
- **`skeleton/contract_changes.yaml` and `skills/sdlc-migrate` §4.5a:** a new `catalog_column_added` entry type, and entry 0016, which back-fills `—` into existing catalogs.

**Release:** minor. New contract surface (a catalog column projects write, a new template and a new entry type), purely additive with a back-fill default.

**Rationale:** A dependency no tool reads is a dependency nobody sees. One column plus a few checks surfaces the three failures that bit D11: blocked work, execution starting before a prerequisite is done, and a prerequisite nobody is moving forward. A split record gives CD one document to approve, and gives the factory something it can act on.

---

## 2026-10-09: Add-ons finish small follow-ups; Follow-Up Items become issue-ready

**Origin:** CD, after the software factory's first executed plan (quantile D13) deferred two stale knowledge entries and left its follow-ups in the result doc. CD's direction: SDLC hygiene is part of the work, a quick follow-up is finished in the PR as an add-on, and anything else becomes its own issue and goes through triage. Cross-checked with Fable and Codex.

**What changed:**
- `skills/sdlc-lite-execute` and `skills/sdlc-execute`: an **Add-ons and follow-ups** rule.
  - **Add-ons:** small, no new decision, inside the touched area, dispatched and verified like planned work, listed in the result doc.
  - **SDLC hygiene:** knowledge entries or parking-lot notes the change makes wrong are corrected in the same deliverable.
  - **Everything else is a Follow-Up Item:** F-numbered, an issue-ready title, why not now. Nothing is dropped silently.
  - The PR body example's Scope gains Add-ons and Follow-ups lines.
- `templates/sdlc_lite_result_template.md` and `templates/result_template.md`: a new **Add-ons Beyond the Plan** section, and **Follow-Up Items** in a parseable checklist format (`- [ ] **F1: title**: what _Not now: why_`).
- `templates/pr_description_template.md`: Scope's Deferred line becomes Add-ons and Follow-ups. Follow-ups are a checklist CD can prune before merging.

**Rationale:** Follow-ups that live only in a result doc are forgotten, and tiny ones aren't worth an issue each. Finishing small ones in the PR and making the rest issue-ready lets a project (the factory does) file them automatically.

---

## 2026-10-09: Codex calls can't hang on stdin

**Origin:** A direct `codex exec` consult run from a background shell sat idle for 35 minutes. It printed "Reading additional input from stdin..." and waited for an end-of-file the open, empty pipe never sent.

**What changed:**
- `process/external-review-gate.md`: direct `codex exec` calls (no piped payload) end with `< /dev/null`, and the Task-Based Model Selection example shows it. The wrapper bullets list the new time limit and the stdin refusal.
- `templates/external-review.sh.template` and `templates/external-review-knowledge.sh.template`: refuse to run without piped stdin, and bound the codex call with `CODEX_TIMEOUT_SECS` (default 1800) through a portable `perl` alarm. A stall now skips the gate with a message instead of hanging.

**Rationale:** The wrappers always pipe a payload, so they were safe in normal use, but nothing stopped a background or ad-hoc call from waiting forever, and a stalled model call had no bound at all.

---

## 2026-10-09: Writing for CD — plain, short output in every session

**Origin:** CD, after the PR description standard landed: "I regularly find that I tune out because the agent is just so verbose and it just becomes information overload." CD wanted the PR's readability in every interactive SDLC session, and asked whether this belongs in the framework or in an installed output style.

**What happened:** Most of the overload was written into the skills themselves. Plan approval pasted the whole plan into plan mode (quantile's D13 plan is 12,020 words). The completion report's change list was required to be "exhaustive". Gate checklists and review rosters printed in full every time. An output style can't override that, and the docs confirm it doesn't reach dispatched agents. Only one style can be active, and CD already uses personal ones (Architect Mentor, and ELI5 Finance Mentor in quantile). So the fix goes in the framework, and personal styles stay a teaching layer on top. Mid-change, CD also dropped plan mode: "I generally close a session and start a new one to execute the plan."

**Changes made:**

1. **`process/writing-for-cd.md`** (new) — The standard for anything CD reads.
   - **Rules:** lead with what CD needs, plain language, say each thing once, evidence over claims, say where you're unsure, don't invent, keep to the budget.
   - **Length budgets:** status updates 1–2 sentences, end-of-turn summaries about 150 words, approval briefs about 450, completion reports about 500.
   - **Status blocks:** one line on the happy path, and a plain sentence before any findings table.
   - **Approval Briefs:** shown verbatim, then the path, in a message that ends the turn. CD's reply is the approval: the one approval asked without `AskUserQuestion`, now stated in `CLAUDE-SDLC.md` and `process/collaboration_model.md` too.
   - **Two mirrored blocks:** the Approval Brief procedure (`approval-brief`) and the Completion Report (`completion-report`). The procedure: the writing agent fills the brief's `###` headings with `Edit`, naming every decision CD approves; a fresh reader checks it; the manager counts its words. Both blocks are registered in § Mirrored Blocks and `process/project-section-markers.md`.
   - **Soft gates (a behavior change):** a FAR or FACTS gate that passes now prints one line and the run continues, where before every soft gate waited for CD. A failing one still waits (also in `process/input-quality-gates.md`). To restore the pause, revert that sentence in the two plan skills and the gates doc.
2. **`CLAUDE-SDLC.md`** — new § Writing for CD for every session. Key References lists the doc.
3. **Approval Briefs** — `templates/spec_template.md`, `planning_template.md` and `sdlc_lite_plan_template.md` gain a `## Approval Brief` section at the top.
   - `sdlc-plan` gains step 2a (spec brief) and step 5b (plan brief); `sdlc-lite-plan` gains step 4a. Each carries the `approval-brief` block; the process diagrams gain the new nodes, and the headless restart paths cover a plan change request.
   - Spec approval (step 3) shows the brief, the path and "To approve, reply approved" as a message of its own, and takes CD's reply as the answer. SPEC-REVISION re-runs step 2a after a scope change or pivot.
   - The lite plan's Definition of Done gains a seventh item for the brief.
4. **Plan mode removed** — `sdlc-plan` step 6 and `sdlc-lite-plan` step 5 are now "Present the Approval Brief".
   - The plan file is read, the brief is pasted verbatim, then the path and "start a new session and say: Execute the plan at …".
   - Approval is CD starting execution in a new session. `EnterPlanMode`/`ExitPlanMode` and the execution-prompt text are gone, from the skills and from `process/headless-mode.md` and `process/html-rendering.md` too.
   - The Read-then-paste rule against summarizing stays.
5. **Completion report** (`sdlc-execute`, `sdlc-lite-execute` step 5) — now the `completion-report` block:
   - the code variant of the PR template, with the same sections in the same order, bold labels for the terminal, What was built in place of What you're approving, What you need to do first and Commits last;
   - explicit always-present and left-out-when-empty sections;
   - critical or major findings CD directed past the cap shown under Review focus;
   - Scope integrity drawn from the deviation log and a diff of test and CI paths;
   - about 500 words, with the exhaustive file list kept in the result doc;
   - "Present the full commit" folded into the Commits line;
   - a PR opened from the report's sections in the template's PR form, after the fresh-reader check.
6. **One-line status blocks:**
   - pass lines for VERIFICATION-GATE (keeping the resolved library ID and how infrastructure was checked) and DISCOVERY-GATE;
   - FAR and FACTS pass lines (also in `process/input-quality-gates.md`);
   - REVIEW-GATE as one line, without repeating the roster;
   - review rosters and plan revision dispatches as one line instead of checkbox lists, in `process/review-fix-loop.md` Step A and both plan skills. The count-must-match rule now counts names.
7. **`process/finding-classification.md`** — one plain sentence before the Classification Table.
8. **`templates/pr_description_template.md`** — the general rules now live in the writing standard. A plan or spec PR's description is the document's Approval Brief. `process/headless-mode.md` fills a caller's PR fields from the brief.
9. **`process/collaboration_model.md`** § Completion Reports, and `sdlc-lite-execute`'s description — updated to match.
10. **`skeleton/manifest.json`** — lists `process/writing-for-cd.md`.

11. **Quality gate** — `sdlc-reviewer` ran on the four skills in two parallel passes and found 0 critical, 7 major and about 35 minor findings and nits. All majors were fixed:
   - the brief's heading level (it must stay `###`, or the word count and the shown brief break);
   - the `sdlc-plan` diagram;
   - the report's empty-section rules;
   - the PR/report shape and order;
   - open critical findings in the report;
   - the duplicated report and brief procedure, now mirrored blocks.

   Most minors were fixed too: stale "checklist" wording, restart paths, the approval exception, the FAR metric, the VERIFICATION-GATE one-liner, and the red flags. Not fixed, because they predate this change: skill size, `sdlc-plan`'s Integration labels, `sdlc-review-code`'s own dispatch checklist, and the diagrams' missing step 5 node in the execute skills.

**Rationale:** CD approves and steers from what the agent shows, and a wall of text gets skimmed: an approval CD couldn't follow isn't an approval. The documents agents work from keep their detail; only what CD reads gets shorter and plainer. Briefs come from the document's author and are checked by a fresh reader, so the manager never paraphrases, which was the reason for the old verbatim-paste rule. Release type: minor (a new cross-skill convention and new skill steps).

---

## 2026-10-09: A reviewable PR description standard

**Origin:** `docs/current_work/ideas/pr-description-standard_handoff.md`. The software factory opened its first plan PR (quantile #31, the D13 plan for issue #30). CD couldn't approve it: "It doesn't really feel right for me to read and approve something that I don't understand."

**What happened:** The plan is written for the executing agent: exact functions, file lines, test fixtures. That is the right content for the agent's contract and the wrong document for CD's approval, and the PR body inherited the same voice. Every PR that asks CD to approve agent-written work has this problem, interactive or factory-made. cc-sdlc had no PR-description guidance at all.

**Changes made:**

1. **`templates/pr_description_template.md`** (new) — The standard, with a plan/spec variant and a code variant.
   - **Fixed sections, in order:** The problem; What changes for users; What you're approving (numbered decisions, each with the alternative it rejects, plus any scope beyond the issue); Scope (tackled, not tackled, deferred); Risk (tier, top risks, undo); Review focus; How it will be verified; How it works (the approach and why it is shaped that way); Learn the change (files in reading order with their roles, and concepts); then a collapsed agent record. Each section has a word share.
   - **Code variant:** How it was verified shows results, not intent. It adds Scope integrity and Deviations from the approved plan (omitted for a direct fix). Open critical or major findings go under Review focus, in plan PRs too.
   - **Rules:** plain language, with code names only where they help CD find or check something. About 450 words above the agent record for a plan, 500 for code. Say each thing once. Evidence over claims. Don't invent: an empty list is fine. Line-level explanation stays in code comments. Headless fields are plain sentences, because the caller renders the formatting.
   - **Fresh-reader check before opening:** a reader given only the description and the plan or diff must be able to explain the change, and every statement must match its source.
   - **Risk tiers:** high, medium and low, decided by what valid use gets and whether a revert undoes it, with the highest fitting tier winning. Each project lists its always-high areas in its own `PROJECT-SECTION` block.
   - **Examples:** a complete plan PR from quantile #30 (D13), and the code-only sections for the same change.
2. **`CLAUDE-SDLC.md`** — new § Pull Request Description: every PR that asks CD to approve agent-written work follows the template, whether a person or the factory opens it. Key References names the template.
3. **`process/headless-mode.md`** § Ending a Headless Run — when a caller's schema has PR-description fields, fill them per the template, never pasted from the plan. Integration lists the template.
4. **`skills/sdlc-plan`, `skills/sdlc-lite-plan`** (Output) — when the spec or plan is approved through a PR, its description follows the plan variant. The plan file is unchanged.
5. **`skills/sdlc-execute`** step 4 item 8 and **`skills/sdlc-lite-execute`** step 4 — a PR carrying the work follows the code variant: deviations come from the result doc, and verification shows the build and test results.
6. **`skeleton/manifest.json`** — lists the template. `sdlc-migrate` §2.1 already direct-copies every manifest-listed template and preserves `PROJECT-SECTION` blocks, so it needs no change.

**Rationale:** CD approves through the PR and, as CD put it, reviewing PRs "is going to be the predominant way in which I look at the code in the first place." So the PR has to say for sure what is being approved, why, at what risk and with what proof, and leave CD understanding the codebase better. The research behind the sections is in the handoff: Google's CL descriptions and Bacchelli & Bird on the why; Willison, Osmani and Phabricator test plans on evidence; Osmani, Atlassian and Kubernetes on review focus; Spotify Honk and GitHub's agent-PR guide on scope integrity; the Rust RFC guide-level explanation and PEP "How to Teach This" on learning. CD overrode Google's "explanations belong in code comments" for the approach-level "How it works". Line-level explanation still goes in comments. A Codex cross-check (gpt-6.1-sol) before building shaped four choices: one file map rather than separate read-order and key-file lists, a fresh-reader check, "don't invent" for lists that can be empty, and risk tiers by reversibility. Release type: minor (a new cross-skill convention).

---

## 2026-10-09: Headless runs dispatch agents in the foreground

**Origin:** The software factory's first live lite-plan run (quantile #30) ended after 4 minutes. The Agent tool launched the plan writer in the background by default. The orchestrator ended its turn to wait for it, and the run closed with the plan unwritten.

**What changed:**
- `process/headless-mode.md` § Ending a Headless Run: every agent is dispatched in the foreground, and the run waits for its result. Callers switch background launches off in the runtime (`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`). Added a Red Flags row.

**Rationale:** A headless run ends with the orchestrator's turn. This was already a rule in the factory's `sdlc-implement` skill; every headless skill that dispatches agents needs it.

---

## 2026-10-08: Headless mode — the rule for running skills with no person present

**Origin:** Software-factory handoff (`docs/current_work/ideas/software-factory_handoff.md`), phase 2 prerequisite "Headless rule". Decision F13 made it a cc-sdlc framework change from the start, ahead of the opt-in `factory` bundle. Phases 0–1 now run `/sdlc-triage` unattended on a self-hosted runner in quantile, and phase 2 will run implementation skills the same way.

**What happened:** Every skill assumed CD was present. Questions went through `AskUserQuestion`, spec approval waited for CD, plan approval went through `EnterPlanMode`/`ExitPlanMode`, phase triage SKIP/REVISE_PLAN waited for confirmation, and the review-loop round cap escalated through `AskUserQuestion`. Under `claude -p` with `--permission-prompts none`, `AskUserQuestion` does not exist, and nothing said what a skill should do instead. The likely failure was guessing past a gate or approving its own work to keep going. The framework had never defined a headless run (the evaluation's Explore pass: "the framework has never run headless").

**Changes made:**

1. **`process/headless-mode.md`** (new) — The rule.
   - **Detection:** a line starting `SDLC headless mode:` in the caller's prompt or appended system prompt (primary). The phrase quoted in the rule, `CLAUDE.md` or a skill doesn't count. Fallback: no ask-the-user tool can be used — neither `AskUserQuestion` nor the harness's equivalent (OpenCode's `question`) is available or loadable, or a call to it is denied without an answer. A deferred tool counts as available.
   - **Subagents:** a dispatched subagent is never headless itself. In a headless run the orchestrator says so in every dispatch prompt, so the limits bind the subagent.
   - **The rule:** every point that needs CD stops the run, and nothing is guessed, defaulted, self-approved or skipped. Seven kinds of point:
     - a question the next step depends on → `needs-input`;
     - a bounded loop that ran out without meeting its bar (review round cap, a FIX that failed twice — not reclassified headless: the run stops and CD decides where it goes — the External Review Gate's fix-round limit, debug-incident T6, the tests-run round limit) → `escalated`;
     - an approval gate (spec, plan mode, or an action plan such as `sdlc-archive`'s archive set or `sdlc-migrate`'s change plan) → save it and stop with `awaiting-approval`. An action plan goes in the result in full, never call `EnterPlanMode`/`ExitPlanMode`, and the next run executes exactly what was approved or stops again;
     - a soft gate (FAR, FACTS) → continue on a pass, stop with `needs-input` on a fail;
     - a question the next step doesn't depend on (PRE-EXISTING findings, minor PLAN findings) → list it under `deferred` and continue. A critical or major PLAN finding stops, because deferring it needs CD (manager rule);
     - an optional offer → take the no path and list it under `skipped`;
     - confirmation of local, reversible work (committing the skill's own output, even when framed as optional) → proceed.
   - **Answered questions are not gates:** a question the prompt or thread already answers doesn't stop the run. Skill pacing rules still hold, and work done before the stop stays.
   - **Outward actions go to the caller:** no side effect outside the working tree. That rules out push, PRs, comments, labels, publishing, messages, external sends and live-system changes, and github-provenance checkpoint writes (their local half still runs, and their GitHub half becomes a rendered `outbound` entry). Reads from anywhere are fine (Context7, web search, `gh` reads, an upstream fetch), and writes to the project's configured knowledge backend count as local. The External Review Gate runs only against a local model or a durably authorized hosted provider. Each skipped action is listed under `outbound`, unless the caller's prompt names it.
   - **Ending:** a stop is a result, so the run ends its turn normally. The run can't set its own exit code, so the status carries the outcome. `failed` with a `reason` is for a precondition the caller must fix.
   - **Result format:** a skill's own closing report comes first and the result last. With `--json-schema`, the caller's schema is the contract; any field it lacks (`notes`, `deferred`, `skipped`, `outbound`) goes into the stage's saved document under `## Headless Result`. Otherwise the run ends with a `## Headless Result` block: status, stage, reason, questions, findings, documents, deferred, notes, skipped, outbound.
   - **Restart, not resume.** A skill whose restart from step 1 would repeat a side effect or lose counted state carries a **Headless restart** paragraph in its entry step. It skips work already done, never registers the deliverable twice, and keeps counting completed phases, review rounds and the frozen roster.
   - **Kept out of core:** factory specifics (labels, markers, writer jobs, approval by merging the doc PR).
2. **Every skill in `skills/`** (27) — Carries the `headless-stop-rule` mirrored block verbatim, inside `MIRROR` markers.
   - **Placement:** directly after the `**AskUserQuestion mandate:**` paragraph where a skill has one (`sdlc-plan`, `sdlc-lite-plan`, `sdlc-execute`, `sdlc-lite-execute`, `sdlc-tests-create`, `sdlc-create-reference-doc`, `sdlc-debug-incident`). Otherwise, before the first `##` section.
   - **Coverage:** every skill carries it, including skills that never ask anything, so choosing consumers takes no judgment. Project skills may carry it too.
   - **How it was done:** copied by script from the source. The audit's drift check reports no drift across all 33 mirrored copies: 27 headless and 6 review-loop.
   - This follows the 2026-05-19 lesson that a pointer alone gets skipped.
3. **Gate-site lines** (outside the mirrored block):
   - **`sdlc-plan`:**
     - step 0 **Headless restart**: skip registration and finished steps, and never mint a second D-number. Spec approval → set Ready and start at 3d, or stop again if the spec changed since. Spec feedback → the SPEC-REVISION block in step 3. A discovery answer → the DISCOVERY-GATE in step 1. DECIDE answers, a FACTS decision or an escalated review → step 5 at the recorded round with the frozen roster. `notes` carry the D-number, complexity, worktree, agent list, prior context and ADR constraints, playbook match, review round, roster and open findings.
     - DISCOVERY-GATE: answered questions count toward the minimum; on a FAIL, stop with the single most blocking question.
     - FAR and FACTS: continue on a pass, stop on a fail.
     - step 3 spec hard gate: `awaiting-approval`.
     - step 6: skip 6a–6c and stop with `awaiting-approval`. "Follow these sub-steps in exact order" is now labelled **Interactive run**, as is the step's opening line.
     - Output section and a red flag.
   - **`sdlc-lite-plan`:** step 0 **Headless restart** (never a second ID or plan file; resume at FACTS or review with the recorded round and roster), step 5 (the same as step 6), FACTS (pass = every phase meets the thresholds), the summary line, the Output section, and a red flag.
   - **`sdlc-execute` and `sdlc-lite-execute`:**
     - step 0: no plan → `failed` with the reason. A **Headless restart** paragraph reads the plan, partial result doc and notes, skips completed phases, and continues the review round count with the frozen roster.
     - PRE-GATE "Triage ≠ BUILD": stop with `needs-input`, giving the phase, SKIP or REVISE_PLAN, and the reason.
     - Completion Report: the Headless Result follows it as the last output.
     - `sdlc-execute` step 4: no push or PR, both listed under `outbound`.
   - **`sdlc-handoff`:** step 7 commits the handoff locally without asking (when the project commits SDLC docs), never pushes; the "Always ask" red flag is scoped to interactive runs.
4. **`process/review-fix-loop.md`** § Round Cap — New headless bullet:
   - at the cap with a critical or major finding open, save the partial result doc and stop with `escalated`;
   - DECIDE and unresolved INVESTIGATE findings stop with `needs-input`;
   - a FIX that fails twice is not reclassified and stops with `escalated`;
   - PRE-EXISTING and minor PLAN findings go under `deferred`, and a critical or major PLAN finding stops with `needs-input`.

   It sits outside the `MIRROR-SOURCE` blocks, so the six review-loop copies are unchanged. The Step C "FIX failure escalation" line and the § Round Cap closing line, plus **`process/finding-classification.md`** § FIX Failure Escalation, say a headless run stops with `escalated` instead of reclassifying.
5. **`process/html-rendering.md`** § Post-Skill Offer — Headless runs take the no path and list the offer under `skipped`.
6. **`process/external-review-gate.md`** § Data egress — In a headless run without durable authorization, hosted-model runs are skipped and listed under `skipped`. A local model or a durably authorized provider runs as usual. The opening list of sanctioned reasons to skip a configured reviewer now includes this one.
7. **`process/github-checkpoints.md`** — New § Headless Runs. The run never writes to GitHub itself, and each checkpoint splits in two:
   - **Local half (still done):** when the issue is known (named in the caller's prompt, or already recorded in an earlier artifact's frontmatter or the catalog's linked ID cell), CP-1 writes `github_issue:` (and `github_board:`) into the first artifact's frontmatter and the catalog ID cell as a link. The ⎘ checkpoints commit their artifact locally under § Commit Conventions, without pushing.
   - **GitHub half (handed to the caller):** each checkpoint, and `sdlc-archive`'s parked-issue closure, adds a rendered entry to `outbound` in firing order. The fields are `checkpoint`, `deliverable`, `issue` (or `new <repo>` for CP-1 or CP-12), `title`, `labels`, `type`, `parent`, `board`, `board_add`, the whole rendered `comment`, `status` (column name and rank, or `—`), `write_if` (the floor rule, or CP-S2's exact match), `close` (`completed` or `not planned`, set only when the skill's closing conditions hold), `needs_push` (the commits the links need, and the branch), and `note`. A `ranks` item travels inside `outbound`: it includes the `never_write` columns above every SDLC rank, an empty Status is rank 0, and an unmapped column means skip the write, so a caller can never move a card backward.
   - **Caller order:**
     - **Push** the linked commits unchanged. A `git bundle` keeps the SHAs; a re-applied patch breaks the links, but the comment still posts. CP-10 waits until the moved files are on the default branch, by any merge method.
     - **Find or create the issue:** search open and closed issues for the `Dnn` title prefix and link a match before creating; create with title, labels, type and the comment as body in one call, then link the parent sub-issue. Under rule 4, `issue: new` carries candidate repos in `note`, and the caller waits for CD to name one.
     - **Board add, then comment** (skipped when the comment was the new issue's body).
     - **Status:** write only if `write_if` holds, using `ranks`.
     - **Close last:** skip it if the issue is already closed or an earlier entry for the same issue failed; CP-10 waits until the moved files are on the default branch, by any merge method, and closes only after its main-branch links resolve. The `sdlc-archive` fragment's checklist executor gains a headless line: its GitHub rows are earlier entries for the same issue.
   - **Missing links are caught up:** any later headless run whose prompt names the issue writes missing links before its own work, including a restart that skips registration and a lite deliverable's first execute run. The rule lives in the six fragments' activation lines, not in core skill text, so projects without the bundle never see it.
   - A handed-off checkpoint is not a failure: no miss-log entry and no notice; reconciliation sees the gap if the caller drops it. CP-11b never fires headless. The caller may hand checkpoint writes to the run; if it does, CP-11b's offer takes the no path and repo selection rule 4 skips that one checkpoint (listed under `outbound`) rather than stopping the SDLC step, so the never-block invariant holds.
   - **`bundles/github-provenance/fragments/{sdlc-plan,sdlc-lite-plan,sdlc-execute,sdlc-lite-execute,sdlc-handoff,sdlc-archive}.md`:** the activation gate line says that in a headless run each checkpoint does only its local half and hands its GitHub half to the caller as a rendered `outbound` entry, unless the caller hands checkpoints to the run.
   - The first draft simply skipped checkpoints and listed only the CP id and D-number. CD asked for the two changes above, because the factory's writer job doesn't know the checkpoint recipes, so the provenance trail would have gone dark for every headless run. A review of the split found five majors, all fixed before landing: the `ranks` map omitted `never_write` columns (a backward write over the deploy pipeline), creation skipped the `Dnn` duplicate search, nothing wrote the CP-1 links once a caller created the issue, the entry lacked `type`, `board` and `parent`, and CP-10's main-branch links and close were unguarded. Round 2 found no majors; its seven minors were fixed and re-reviewed. Round 3 (the cap) found no critical or major findings, and its four wording minors were applied after the cap without re-review.
8. **`CLAUDE-SDLC.md`** § Use AskUserQuestion for All Questions — A self-contained headless paragraph, matching the mirrored block: detection, subagents, stop and end normally, never guess or self-approve, deferred questions, no path on offers, no actions outside the working tree unless the caller names them, answered questions aren't gates. It points at the process doc.
9. **`process/project-section-markers.md`** § MIRROR Markers — Lists the headless stop rule as a user. New rule 6: prose never spells a live marker. A source doc describes its markers with `{id}`, and a skill never writes the copy-marker form with a file name. The drift check matches marker text, and both forms produced false drift while this change was drafted:
   - `headless-mode.md`'s own Markers paragraph made all 27 copies report drift;
   - `sdlc-develop-skill`'s authoring bullet made that skill report drift.
10. **`skills/sdlc-develop-skill/SKILL.md`**, **`.claude/skills/ccsdlc-create-skill/SKILL.md`** — All-types required sections now include the headless stop-rule block: its marker label form, placement and scope, the fact that no mirror-table row is needed, when a gate gets its own **Headless run:** line (its stop needs stating at the gate: status, payload, a skipped step, or an outward action), and a **Headless restart** paragraph for skills that can be restarted. In a target project the § Integration list is upstream-owned, so `sdlc-develop-skill` proposes the entry upstream instead of editing it. `sdlc-develop-skill` also:
    - CREATE step 1.5 (item 4) and MODIFY M1.5 exempt `MIRROR` blocks from extraction. Without the exemption, its DRY audit would recommend reducing the now-universal block to a pointer.
    - M2 gains a "Inside a `MIRROR` block → source-doc change" row: propose the change upstream, never edit the copy.
    - New red flag: "never asks anything, so the headless block is noise".
11. **`process/skill-agent-review.md`** § Required Sections — Mirrored blocks: the headless stop rule in every skill, and the review-loop block in loop-bearing skills.
12. **`agents/sdlc-reviewer.md`** (`.claude/agents` is a symlink to `../agents`) — The mirrored-block drift check names `headless-mode.md` § Mirrored Stop Rule (which lists every skill) beside the review-loop table.
13. **`.claude/skills/ccsdlc-audit/references/compliance-methodology.md`** — Dimension 10 check 5 names both mirror sources and adds a one-line completeness check: `grep -L 'MIRROR-START: headless-mode.md#headless-stop-rule' skills/*/SKILL.md` must print nothing.
14. **`process/README.md`**, **`skeleton/manifest.json`** — `headless-mode.md` registered: a Shared Behavioral Protocols row, and an entry in `source_files.process`.

**Review:** round 1 ran three `sdlc-reviewer` passes (`sdlc-plan`; `sdlc-lite-plan` + `sdlc-develop-skill`; the two execute skills) and one cross-framework consistency review. There were no critical findings. All majors were fixed:
- the skip-vs-"do not skip any sub-step" contradiction;
- no restart entry in `sdlc-plan`;
- the DISCOVERY-GATE unanswerable headless;
- the lite-execute line citing a triage table lite never produces;
- OpenCode's ask tool tripping the fallback;
- an outward-action ban too narrow, missing live-system changes, egress and subagents;
- no `failed` status;
- unsaved action plans approved by question.

Round 2 (three fresh reviewers) confirmed every round-1 fix and found three new majors, now fixed: (1) a twice-failed FIX had three different outcomes across the docs, one of which let a critical finding be deferred; (2) `sdlc-lite-plan` had no restart entry, so a restarted run would mint a second D-number; (3) both execute skills had no restart entry, so a restarted run could redo finished phases and reset the review round count. Round-2 minors were fixed in the same pass: the `failed` status was added to the mirrored block, reads were allowed explicitly, schema fallback now covers every field, the commit-confirmation rule was settled, the external gate's sanctioned-skip list was updated, the gate-line criterion was stated once, and the § Integration list was completed. Round 3 (two fresh reviewers, the cap) found no critical or major findings. Its ten minors were applied after the cap and checked mechanically, not re-reviewed: twice-failed-FIX qualifiers in `review-fix-loop.md` and `finding-classification.md`; the restart-paragraph scope narrowed to skills whose restart from step 1 would repeat a side effect or lose counted state; `sdlc-plan` records the spec's content hash for the unchanged-since-approval check and splits the FAR, FACTS and review restart cases; `sdlc-lite-execute` restart notes reflect its single step-4 commit; `sdlc-handoff` step 7 commits locally headless. Known open item: the plan → execute hop has no unchanged-since-approval guard for the plan (a design question for the approval row). Pre-existing findings were left alone. These include `sdlc-plan`'s Integration structure, skill length, the `§3c` references, sibling drift between the execute skills, bare paths in `sdlc-develop-skill`, and the Manager Rule copies.

**Not changed:**
- The `code-review-mechanics` and `plan-review-mechanics` blocks still say "escalate to CD via `AskUserQuestion`". The mirrored stop rule and the § Round Cap bullet cover headless runs, and editing those blocks would mean re-copying them into six skills.
- Parking a draft PR at the review cap with `factory:review-capped`, the labels, the markers, the writer-job split and the per-stage output schemas are factory concerns. They stay in quantile until the `factory` bundle.
- No `contract_changes.yaml` entry: the new process doc is a direct copy and the rest are in-place edits, so no migration behavior is needed.
- Neuroloom: no new knowledge-layer references, so this is not a contract change.

**Versioning:** a new cross-skill process convention, so this is a **minor** bump at the next release. No tag was cut.

**Rationale:** The factory is the first caller, but the gap is general. Any unattended run (CI, a scheduled job, `claude -p`) reaches the same gates. Stopping cleanly with a structured result does three things:
- keeps CD's decisions with CD;
- lets a caller tell "needs CD" from "broke";
- gives the next cold run what it needs to continue.

The rule sits in core with a mirrored line in every skill, not only a pointer, because pointer-only guardrails have been skipped before.

---

## 2026-10-06: Unify and bound the review loops — one severity scale, mechanical re-review, critical/major exit bar, 3-round cap

**Origin:** A software-factory and cost evaluation session measured 30 days of Claude Code usage (local transcript token counts to 2026-10-06, priced at API list rates — on the Max plan this is usage limits and waiting time, not dollars). About $16.3k equivalent in total; subagents were 67% (~$10.9k) and 95% of all cost was re-reading context. Review and re-review were ~3,008 of 4,775 subagent dispatches and ~$5.1k — 47% of subagent cost. Median review checkpoint roster 7 reviewers (p90 12, max 15); rounds labelled up to 23 (469 dispatches in rounds 3–5, 224 in rounds 6–10, 183 in round 11+); 60–75% of reviewers reported findings in every round bucket, and hand-sampled late-round reports were nearly all self-described minor. Fable and Codex (GPT-6-Astra, `ultra`) ruled independently on proposed changes (consult record: `docs/current_work/ideas/review-loop-unification_consult-record.md`); CD decided D1–D14 (`docs/current_work/ideas/review-loop-unification_handoff.md`).

**What happened:** The loop had no termination guarantee. The exit bar was zero findings with minors included; the 3-strike rule only fired when the *same* finding category repeated, so a loop surfacing a different minor each round never stopped. Every fix sent the whole roster back ("not just the ones who found issues"), rosters never shrank ("do not remove agents", "When in doubt, include"), and AOP5 right-sizing was cited only by the plan skills. There was also no single severity definition: `finding-classification.md` was planning-shaped (critical = "changes the approach"), the impact × likelihood calibration and the dedup table lived only in `sdlc-review-code`, and `sdlc-create-reference-doc` used its own CRITICAL/HIGH/MEDIUM/LOW scale. History: the 2026-04-14 audit attributed 63% of token cost to review-fix; 2026-05-12 removed `team-review-fix` as underused; 2026-05-19 ("Inline Critical Guardrails Lost in Skill Consolidation") restored inline loop steps after a pointer-only consolidation let `sdlc-review-code` skip the loop and falsely claim it clean — which is why this change keeps the loop steps inline as verbatim mirrored blocks instead of reducing skills to pointers.

**Changes made:**

1. **`process/finding-classification.md`** — Now owns the shared definitions for every review loop. § Severity Levels replaced: impact × likelihood scale (critical = certain/very likely data loss, breach, or complete failure; major = significant, likely to manifest; minor = partial/workaround/cosmetic) moved from `sdlc-review-code`, with a per-context reading of "impact" (software / implementation-as-written / reader). New § Severity Calibration (calibrate before labelling; never a lever for exiting a loop). New § Scope-Change Marker — a `Scope change` yes/no column in the planning-context Classification Table (fix changes the approach, adds/removes files, or changes a phase/agent assignment); plan re-review trigger (1) reads it (D9, D12). New § Finding Deduplication — the four-row merge table moved from `sdlc-review-code` Step 4, applied before classification everywhere. New § Open Minor Findings — table shape, where it lives per context (result doc / Fix Summary / plan file / commit message), only CD closes entries. Context table: stale "Post-commit fix (review-fix)" row retitled to code review fix (`sdlc-review-code`, direct dispatch); reference-doc row added. Kept: FIX Failure Escalation (fails twice → INVESTIGATE/PLAN) and Low-Severity In-Scope Findings (Planning Context).
2. **`process/manager-rule.md`** — § No Unilateral Finding Demotion: listing open minor FIX findings at loop exit, visible to CD, is permitted and not demotion; closing them still requires CD; downgrading severity to meet the exit bar is demotion.
3. **`process/review-fix-loop.md`** — Now owns the loop for every review context. Overview rewritten. Step A: the "do not remove agents… dispatch every single one" rule replaced by the first-round roster rule (code-reviewer + software-architect plus one reviewer per touched domain; "when in doubt" covers domains, not headcount; beyond five each extra agent states what it uniquely adds, AOP5; MTS4 high-risk domains always get their specialist; lenses are never trimmed). Context-separation rule kept, plus **fresh reviewers every round — no reuse** and what re-review prompts carry (prior findings table, fix diff, read current code, look for regressions, a clean report is acceptable). Step B: "Zero means zero" replaced by § Exit Bar. Step C: dedup → calibrate → classify; fix critical and major each round, minors accumulate for one batched pass; a non-mutating **pre-fix snapshot** — a tree hash written through a throwaway copy of the index (`GIT_INDEX_FILE=<tmp> git add -A && git write-tree`), taken again after the fixes — feeds the file-set comparison and the fix diff (verified in a scratch repo: the real index and working tree are untouched, and edits to untracked files are caught; `git stash create` was tried first and rejected because it omits untracked files, so fixes to newly created code or docs would be invisible); FIX failure escalation cross-referenced. Step D: "dispatch ALL agents — not just the ones who found issues" replaced by the mechanical rule (re-run the verification gate; full roster if any applied fix was critical/major or touched files go beyond the findings' files, otherwise raisers + code-reviewer + software-architect scoped to the fix diff; new domain adds its reviewer). Step E: external findings deduplicated and calibrated with internal ones; every internal round they re-open counts toward the cap; the gate's own 2-round cap kept, whichever limit hits first. New § Exit Bar (no critical/major open, no INVESTIGATE/DECIDE unresolved, minors have had their batched pass) and § Round Cap (3 rounds, every round counts; escalate via `AskUserQuestion` with the open-findings table when critical/major remain; exit with Open Minor Findings when only minors remain) — **replaces the 3-strike rule**. New § Plan Review (no verification gate; one revision dispatch per round; re-review fires on the scope-change marker, Files-list change, or phase/agent change — exactly today's cases — and always dispatches the full step-1 roster; an unreviewable round-3 revision escalates). New § Mirrored Critical-Steps Blocks with the two source blocks (`code-review-mechanics`, `plan-review-mechanics`) and the consumer table. § Skill-Specific Variations rebuilt as a per-context table (execution, review-code — whose Step 3 dispatch is round 1 — direct dispatch, plan review, reference-doc review); the stale `sdlc-review-fix` row removed; lite and full run the identical loop.
4. **`process/project-section-markers.md`** — New § MIRROR Markers: `MIRROR-SOURCE-START/END: {id}` in the source doc, `MIRROR-START/END: {doc}.md#{id}` in skills; byte-identical content; exempt from DRY extraction; not migration markers (`sdlc-migrate` matches only the literal `PROJECT-SECTION-*` / `BUNDLE-SECTION-*` names, so mirror blocks pass through as upstream content). Validation section: `sdlc-reviewer` checks mirror blocks against their source.
5. **`skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`** — Inlined loop steps replaced by the mirrored code-review block; Step 0.5, self-applied-fix note, Triage output format, plan contract briefing, and the External Review Gate paragraph kept outside it. Exit announcement now "Review loop complete — no critical or major findings open (N open minor findings listed)"; step 3 is reached under the exit bar; open minors go to the result doc. Flow diagrams redrawn (fresh reviewers per round, dedup/calibrate/classify, cap and escalation branch). Red flags: "ALL means ALL" → "Re-review is mandatory; its roster comes from the mechanical trigger, never judgment"; "Skip re-review, the fixes were small" (lite) rewritten the same way; "One more iteration" now cites the cap; "Build passes" updated; new flags for downgrading severity to exit, claiming clean at the cap, resuming a reviewer, and skipping the verification re-run. No lite-specific rules.
6. **`skills/sdlc-review-code/SKILL.md`** — Step 3 gains the roster-size rule and states its dispatch is review round 1. Step 4's dedup and calibration tables moved to `finding-classification.md`; a short inline step keeps the critical behavior (merge same-location duplicates keeping the highest severity; calibrate before labelling). Report Framing Discipline kept. Fix gate: critical/major first, minors batched. Step 5a self-check counts the findings being fixed this round and records the pre-fix snapshot. Step 5b replaced with the mirrored code-review block (5a's manager-rule guardrails stay inline). Fix Summary shows rounds of 3 and the Open Minor Findings table. Red flags :367 (lenses) and :372 (Tier 2) kept — Tier 2 wording now says a touched-domain Tier 2 agent stays; new flags for headcount padding, judgment-scoped re-review, and claiming clean at the cap.
7. **`skills/sdlc-plan/SKILL.md`, `skills/sdlc-lite-plan/SKILL.md`** — Selection Rule: "When in doubt, include" replaced by coverage-not-headcount wording with AOP5 as a rule (beyond five, a one-sentence unique-contribution statement) and MTS4 specialists; the existing `Consult [sdlc-root]/knowledge/architecture/agent-orchestration-patterns.yaml` lines kept (phrasing contract). Plan review: mirrored plan-review block added; classification now dedups, calibrates on the shared scale, and fills the `Scope change` column; re-review trigger (1) reads `Scope change` instead of `Severity = critical` (triggers (2) and (3) unchanged, full step-1 roster unchanged, no narrow re-review, no re-review for non-scope fixes); revision checklist counts minors and scope-change findings; stopping condition is the exit bar with an Open Minor Findings table appended to the plan; external reviewer's 2-round cap sits inside the 3-round loop cap. Lite-plan flow diagram redrawn to show the trigger and cap. New red flags on severity-vs-scope triggers, the cap, reviewer reuse, and headcount padding.
8. **`skills/sdlc-create-reference-doc/SKILL.md`** — CRITICAL/HIGH/MEDIUM/LOW reviewer format and the "no CRITICAL, HIGH, or MEDIUM" exit replaced by the shared critical/major/minor scale (read as impact on a reader) and the exit bar, used as-is. § 5 Fix Loop carries the mirrored code-review block; the step 4 dispatch is round 1; the standing reviewer for narrow re-review is `code-reviewer` (on every quorum). Open minors are listed in the commit body (commit template updated). Flow diagram and red flags updated.
9. **`process/agent-selection.yaml`** — Selection Process step 7: coverage, not headcount; AOP5 beyond five; MTS4 specialists; lenses are not headcount.
10. **`knowledge/architecture/agent-orchestration-patterns.yaml`** — AOP5: note that review rosters apply it through the Step A roster rule, using the one-sentence test rather than splitting the round. No rule change.
11. **`process/external-review-gate.md`** — Severity vocabulary points at `finding-classification.md`; external findings are deduplicated and calibrated with internal ones; the 2-round gate cap is reconciled with the 3-round loop cap (both apply, whichever first; gate re-entries consume loop rounds) for execution and plan review; the plan-review rubric now defines the three severities for the external model. **`templates/external-review.sh.template`** default-format line defines them too.
12. **`CLAUDE-SDLC.md`** — Direct Dispatch "Review before committing": "dispatch ALL relevant agents… re-review until clean" replaced by a pointer to the loop plus the one-line roster / re-review / exit / cap summary (self-contained for target CLAUDE.md files). Escalation list mentions the review-loop round cap.
13. **`process/README.md`** — `review-fix-loop.md` and `finding-classification.md` rows describe what each now owns; consumer counts corrected to 7.
14. **`templates/result_template.md`, `templates/sdlc_lite_result_template.md`** — New Open Minor Findings section.
15. **`process/discipline_capture.md`, `process/collaboration_model.md`, `process/github-checkpoints.md`, `bundles/github-provenance/fragments/{sdlc-execute,sdlc-lite-execute,sdlc-plan}.md`** — Stale "review-fix" skill row retitled to `sdlc-review-code`; escalations mention the round cap; CP-7 / plan checkpoint wording "loop clean" → "meets its exit bar".
16. **`agents/sdlc-reviewer.md`** (hardlinked to `.claude/agents/sdlc-reviewer.md`) — § Cross-skill DRY: `MIRROR` blocks are exempt from extraction recommendations; new mirrored-block drift check (copy must match the source exactly; a listed consumer with no copy is major).
17. **`.claude/skills/ccsdlc-audit/references/compliance-methodology.md`** — Dimension 10 check 5: mirrored-block drift, with a BSD-safe shell check (verified against all six copies and against a deliberately drifted copy); scoping rule exempting `MIRROR` blocks from extraction recommendations.

18. **Quality gate** — `sdlc-reviewer` dispatched in three parallel passes (execute pair, review-code + reference-doc, plan pair); 0 critical, 10 major, 20 minor, 10 nit in total. The plan pass walked trigger (1)–(3) before and after and confirmed plan re-review fires in exactly the same cases. Applied: the snapshot mechanism change above (reference-doc pass: the doc is a new untracked file); `sdlc-review-code` now emits the Classification Table before fixing (FIX / INVESTIGATE / DECIDE / PRE-EXISTING), runs the full verification gate after fix rounds, and moves a parenthetical `agent-context-map.yaml` instruction into its own sentence (phrasing contract); reference-doc minors get the batched pass before being listed, classification and External-Gate-not-applicable notes added, diagram gains the cap/escalation branch; execute skills' descriptions and round-1 roster now include the standing pair, every round emits the Step A checklist, Step E paragraph carries the gate cap and never-block rule, a round-cap escalation outcome rule, CHECKER-mode re-audits follow the loop rules, Open Minor Findings wired into § 3 / result-doc lists, lite/full red flags aligned, and stale step references fixed (2c→2b, 3c→3d, 3d→3e, 3b→3c, "L143"); plan block now records the pre-revision Files list and phase/agent assignments before the revision dispatch and defines the roster as the round-1 dispatch checklist; `sdlc-plan` diagram gains the re-review/cap loop; lite-plan diagram no longer lets a minors-only round skip the writer; plan checklists say "round N of 3"; `manager-rule.md` allowed-edits list covers the Open Minor Findings table; `sdlc-lite-plan` points at `agent-selection.yaml`; `sdlc-plan` bare `playbooks/README.md` path fixed; Integration/Uses lists include the two process docs. Mirror drift check re-run after every source edit: all six copies identical. Not applied (pre-existing, out of scope): skill body length and the `sdlc-plan` Integration section shape. The gate then ran the new loop on itself. Round 2 sent the full roster, because round 1 had major fixes, and found 0 critical/major and 14 minors. Those 14 went into one batched pass: escalation-outcome wording; `review-fix-loop.md` step qualifiers; CHECKER round counting; lite description; red-flag merge and parity; the `sdlc-plan` diagram gate; AGENT-RECONFIRM limited to round 1; "round-1 roster" naming; review-code's pre-round-1 gate exemption; the Tool Rule link; the per-round checklist; and the `sdlc-reviewer` unresolvable-source rule. The batch also covered `sdlc-develop-skill` and `ccsdlc-create-skill` (item 19). Round 3 sent the narrow roster, since every touched file was named in a finding, and found 0 critical/major, 4 minors and 2 nits. The loop exited at the cap, and these were listed as **Open Minor Findings** for CD. CD then directed fixing all four before the v1.9.0 tag was redone; each row says how it was resolved:

| # | Finding | Location | Why still open |
|---|---------|----------|----------------|
| 1 | When CD directs proceeding past the round cap with majors open, the step 3 precondition and the "Review loop complete — no critical or major findings open" announcement would be false. The skills should say to skip the announcement and record the open findings and CD's direction in the result doc. | `sdlc-execute` / `sdlc-lite-execute` § 2 escalation paragraph | **Resolved:** the escalation paragraph now skips the announcement and records the open findings and CD's direction; step 3's precondition admits the CD-directed path |
| 2 | The `sdlc-plan` diagram's re-review edge loops back to node 5, whose label still says "AGENT-RECONFIRM". Prose says reconfirm is round 1 only. | `sdlc-plan` flow diagram | **Resolved:** node relabelled "AGENT-RECONFIRM (round 1 only) … re-review: frozen roster, no reconfirm" |
| 3 | `sdlc-plan` CHECKER-mode re-audit has no Classification/`Scope change` table, roster, or escalate-at-cap rule. Its trigger is not mechanically evaluable. | `sdlc-plan` CHECKER step 6 | **Resolved:** plan audits classify with the `Scope change` column and record Files/phase-agent state first; re-audits use the full round-1 roster; the cap escalates via `AskUserQuestion` |
| 4 | `sdlc-plan` does not say to re-emit the "Plan review round N of 3" checklist each round. `sdlc-lite-plan` says "copy it". | `sdlc-plan` § 5 Re-review | **Resolved:** both plan skills re-emit the checklist each round with N updated |

A narrow `sdlc-reviewer` check of these fixes found three more minors, all applied. `review-fix-loop.md` § Round Cap now owns the CD-directed-proceed rule: the still-open critical and major findings go in the Open Minor Findings table with their real severity and CD's direction, and `finding-classification.md` and both result templates say so. The plan checklist re-emit drops the external reviewer once its 2-round cap is spent. `sdlc-plan` CHECKER audits deduplicate and calibrate before classifying. Nits: the four skills that quoted a shortened Step A checklist header now quote it verbatim. The "step-1 list" sentence in `sdlc-lite-plan` is kept, because it is correct as a contrast with the dispatched set.

19. **`skills/sdlc-develop-skill/SKILL.md`, `.claude/skills/ccsdlc-create-skill/SKILL.md`** — The orchestration-skill requirement "Review-Fix Loop — reference to review-fix-loop.md" prescribed exactly the pointer-only form this change forbids; it now requires carrying the matching mirrored block verbatim and registering the skill in the mirror table.

**Deliberately kept:** "When in doubt, include" in `sdlc-develop-agent/references/enrichment-methodology.md` (external-content relevance mapping, not reviewer selection) and the other "3-strike" rules (`sdlc-tests-run` test failures, `parallel-dispatch-monitoring.md` dispatch failures, `debate-protocol.md`, `team-communication-protocol.md`, `debugging-methodology.yaml`, AOP debugging checks) are different rules about stuck hypotheses and failed dispatches, not the review loop. Not implemented (raised in the consult, not decided by CD): fixer return contract, stable finding IDs across rounds, whole-file PRE-EXISTING scope qualification, and headless parking/budgets at the cap. No manifest or `contract_changes.yaml` change — no files added, removed, or renamed. Neuroloom `pattern-mapping-rules.md` has no transformation for any changed phrase (`finding-classification`, `review-fix-loop`, severity); new knowledge references use the canonical `Read [sdlc-root]/knowledge/...` form outside parentheses — not a contract change.

**Rationale:** Termination comes from the exit bar and the cap, not from roster trimming alone: the critical/major bar plus three rounds bounds every loop, the mechanical re-review rule (Fable's version — execution reviews run on Sonnet, so no judgment-based scoping) stops whole-roster re-reviews after minor, file-local fixes, and visible Open Minor Findings keep the looser bar honest. One severity scale and one dedup step are prerequisites — a severity-keyed exit bar without shared calibration invites inflation and deflation. Reviewer reuse (D4) and a lighter lite tier (D6) were considered and rejected. Estimated effect ~$1.5–2.5k API-equivalent per month, mostly from rounds 2+ — an estimate, not a measurement. Versioning: **minor** bump (CD decision, 2026-10-06) — the mirrored-block convention and the shared loop contract are new process conventions with no forced migration behavior.

---

## 2026-09-22: sdlc-render becomes sdlc-explain — big pictures, few words `[contract-change]`

**Origin:** CD brought in Thariq Shihipar's (Claude Code team) published practice with artifacts: "use big pictures and few words" typed several times a day, inline SVG in artifacts, artifacts as explainers, "one picture + a hard limit beats three paragraphs of vibe", "show me the diff, not the essay — agents drown in prose", Claude is too verbose by default, and the `/eli5 <topic>` plugin (`anthropics/claude-plugins-community`, `eli5@claude-community`) used for "how does this module work", "why did we make this tradeoff", "what caused this incident". CD asked to fold this into `sdlc-render`, whether render / walkthru / eli5 should be combined, then clarified: the render was built as the reading aid for specs and plans, `sdlc-walkthru` has overtaken that, so the render no longer needs to be faithful — it needs to explain, the way eli5 does. Then: rename it to `sdlc-explain`, and remove any rules and documentation the change makes unnecessary.

**What happened:** A first cut kept three skills (faithful render, walkthrough, a new explainer) sharing one doctrine. CD's clarification collapsed that: with the comprehensive read owned by the walkthrough, a faithful render and an explainer of the same deliverable are the same artifact with different fidelity — and the lossy one is the one people read. So the render *is* the explainer. Merged, renamed, and everything built for the faithful-render era removed: the verbatim content rule, the four-question audience/purpose/emphasis scoping, audience-variant profiles, the per-section slide layout with review checkboxes, tab auto-generation, filter chips, the component-by-component document-type profiles, and the Content Review Deck component in the design system.

**Changes made:**

1. **`skills/sdlc-render/` → `skills/sdlc-explain/SKILL.md`** — Renamed and rewritten as the eli5 explainer. Subject resolution table (deliverable → catalog and document type; module → code; tradeoff → specs/ADRs/knowledge layer/changelog; incident → incident doc and fixing commits), verify-before-draw under the Code Verification Rule with a sources footer, the "one thing" discipline (≤12-word title), storyboard budgets (3–8 pictures, 12 for a many-phase plan; ≤40 words per picture; ≤30 × pictures total, binding; zero paragraphs), a beat → picture-type table, open decisions always get a picture, inline-SVG-only drawing rules, one picture per screen, jargon glossed inside the picture. Post-skill mode uses the document type's storyboard with no Q&A; manual mode has no scoping Q&A either — the only question is a disambiguation. Deliverable explainers still live beside their markdown (staleness conventions unchanged); question explainers go to `docs/current_work/explainers/`. Twelve Red Flags; four validation criteria. Triggers keep `/sdlc-render` and "render the spec/plan" so muscle memory still lands, and add `/eli5`, "eli5", "explain like I'm 5", and explainer-shaped questions.
2. **`process/html-rendering.md`** — Rewritten. Philosophy now says HTML explains, it does not transcribe. New § "Visual Doctrine: Big Pictures, Few Words" (seven rules, credited to Thariq's practice). "Two Categories" are now explainers and exploration artifacts, with a table relating them to the walkthrough. § Post-Skill Offer keeps the opt-in, precedes-approval, and walkthrough-as-peer rules and the skill → storyboard table. § Document-Type Storyboards replaces the component-by-component profiles: one row per type with its default beats. Removed: Layout Modes, Review Checkboxes, Tab Auto-Generation, Filter Chips, Audience Variants, Manual Render scoping, and the verbatim content rules. Staleness and sharing kept, trimmed.
3. **Ten post-write offer points** (`sdlc-plan` ×2, `sdlc-lite-plan`, `sdlc-execute`, `sdlc-lite-execute`, `sdlc-idea`, `sdlc-handoff`, `sdlc-audit`, `sdlc-create-reference-doc`, `sdlc-debug-incident`; `sdlc-review-code`'s two-line variant) — Each carried a near-verbatim paragraph re-describing how to render. Replaced with one line: offer an explainer (`sdlc-explain`, named storyboard) or a walkthrough, never unprompted, mechanics in the process doc. "Render precedes approval" wording in `sdlc-plan` / `sdlc-lite-plan` (steps and Red Flags) now says explainer.
4. **`skills/sdlc-walkthru/SKILL.md`** — Step 4 routes by shape of the question: *see* one mechanism → `sdlc-explain`; *manipulate* it → an exploration artifact. Description, Complements, Does NOT replace, and Red Flags reference the explainer instead of the render.
5. **`templates/html-design-system.html`** — Removed the Content Review Deck (section 21): its CSS, print rules, TOC entry, demo markup, and the localStorage review-state script. The presentation Slide Deck (section 20) stays — it is the explainer's optional one-picture-per-screen stepper. Footer attribution updated.
6. **`CLAUDE-SDLC.md`** — The post-write rule now offers explainer or walkthrough, and a second paragraph states the visual doctrine and `/eli5`.
7. **`process/commands.md`** — `/sdlc-render` row replaced by `/sdlc-explain <subject>` / `/eli5 <subject>`; walkthru row calls it the explainer's peer.
8. **`skeleton/manifest.json`** — `skills/sdlc-render/SKILL.md` → `skills/sdlc-explain/SKILL.md`.
9. **`skeleton/contract_changes.yaml`** — Entry `0015`, `rename_skill` `sdlc-render` → `sdlc-explain`, with notes on the offer-paragraph rewrite and the design-system removal.
10. **Quality gate** — `sdlc-reviewer` dispatched on the rewritten skill, then across the whole change set (three parallel passes on the two rendering skills, the ten lifecycle skills, and the process-doc wiring). Second round applied: a leftover "Render precedes approval" paragraph deleted from `sdlc-plan`; `sdlc-review-code` and `sdlc-audit` codebase-health mode now offer the walkthrough alongside the explainer; the stale "tabs and collapsibles only" clause in `sdlc-idea` / `sdlc-plan` exploration-artifact provisions replaced with the explainer's static, stepper-only rule; one missed "render" noun in `sdlc-walkthru`; `§ Post-Skill Offer` casing normalized across all pointers; two Key References descriptions in `CLAUDE-SDLC.md`. First round on the skill (4 minor findings, all applied): "render" as a noun replaced by "explainer" throughout the body (the `/sdlc-render` and "render the spec/plan" triggers stay, deliberately); a garbled § Sharing cross-reference fixed; the Visual Doctrine section trimmed to a pointer so it matches the DRY-notes claim; the Code Verification Rule no longer re-described inline.

**Rationale:** Prose is where the human in the loop becomes the bottleneck; a picture with a hard limit is how they stay in the loop without reading everything. Once the walkthrough owns "nothing load-bearing omitted", a second HTML view that also tries to keep everything is dead weight — and the machinery built to make a faithful render reviewable (slide decks, review checkboxes, audience scoping) is dead weight with it. The community plugin's three-line prompt is preserved as the skill's spine; cc-sdlc adds grounding (verify before draw, cite sources, always draw the open decisions) so that a lossy picture is never a false one. Versioning: a skill rename is a breaking contract change → **major** bump when CD next tags.

---

## 2026-09-02: sdlc-reviewer quality-gate fixes for the two new skills

**Origin:** `sdlc-reviewer` dispatched on both skills added today (`sdlc-manage-github`, `sdlc-walkthru`) per the new-skill quality gate. Eight findings total; six applied, two declined with rationale.

**Changes made:**

1. **`skills/sdlc-manage-github/SKILL.md`** — 8 bare `github-checkpoints.md` references expanded to `[sdlc-root]/process/github-checkpoints.md` (path-variable rule); recipe headers renamed `### Recipe N:` to disambiguate from the Steps numbering; Integration gains the board-roles-vs-catalog-statuses relationship (roles are a deliberate per-project taxonomy; the catalog stays canonical) and documents why the recipes stay inline rather than in `references/` (an extra read-hop is skippable indirection under the directive-inlining convention — declining the extraction suggestion).
2. **`skills/sdlc-walkthru/SKILL.md`** — `AskUserQuestion` gate question now cites `[sdlc-root]/process/collaboration_model.md` § Tool Rule; the Code Verification Rule citation names its home (project CLAUDE.md); the Manager Rule section names the dispatch mechanism. Declined: renaming `walkthru` → `walkthrough` — the contraction matches the trigger phrases and the originating project's installed skill name, which keeps migration continuity.

**Rationale:** The quality gate exists precisely for ported content — both declined findings are deliberate design choices now documented in place, so the next reviewer reads a decision instead of re-flagging a gap.

---

## 2026-09-02: Adopt sdlc-walkthru from paire-appetit — guided artifact walkthroughs as the render's peer

**Origin:** paire-appetit built `sdlc-walkthru` as a comprehension-first alternative to the HTML render: an SDLC artifact delivered as a paced, part-by-part guided tour — CD paces with "next", questions are answered against verified code, and feedback is classified and dispatched to revision agents mid-flight. Its first use surfaced three material spec corrections a static read had missed. Fully generic apart from two project references, so it upstreams as a core skill (not a bundle — no external dependencies).

**Changes made:**

1. **`skills/sdlc-walkthru/SKILL.md`** — New core skill, ported near-verbatim: preflight segmentation by story (4–7 parts, chaptered past ~8), the pacing contract, part-delivery rules (≤350 words, lead with the claim, one part per turn), verify-then-answer for questions, feedback classification via the invoking skill's revision protocol (SPEC-REVISION et al.), wrap-up-before-gate. Generalized: the project-specific principles reference now consults `[sdlc-root]/knowledge/agent-context-map.yaml`; paire's terminology example dropped.
2. **`process/html-rendering.md`** — § Post-skill render offer: the walkthrough is the render's peer at every offer point — skills offer both consumption modes; whichever CD picks resolves before any approval question. (This closes the follow-up paire's own Integration note recorded as not-yet-done.)
3. **`CLAUDE-SDLC.md`** — Post-write render-offer paragraph updated to offer the walkthrough alongside the render.
4. **`skeleton/manifest.json`** — `skills/sdlc-walkthru/SKILL.md` added to `source_files.skills`.
5. **`process/commands.md`** — `/sdlc-walkthru` row.

**Rationale:** A document's job is durability; a decision-maker's job is judgment. The walkthrough serves the approval gates the render already serves, with a different consumption mode — and it demonstrably surfaces corrections a static read misses. New installs get it via the normal file copy; existing installs receive it on next migration as an ordinary new framework skill.

---

## 2026-09-02: Unbuilt-Capability Rule, launch-recipe skill convention, additive-contract versioning

**Origin:** Three adoptions from reviewing paire-appetit's recent evolution alongside this session's own decisions. (1) Paire's newest CLAUDE.md rule (their commit of 2026-09-02): a session investigated only the exposed application layer, concluded a leadership-requested capability "does not exist," and cut the language unilaterally — when the underlying data actually supported building it. (2) Paire's project-local `verify` skill — a build/launch recipe with accumulated environment gotchas — is a pattern worth naming upstream even though its content is project-specific. (3) CD decision on versioning for this release.

**Changes made:**

1. **`CLAUDE-SDLC.md`** — New § Unbuilt-Capability Rule: Ask, Don't Silently Cut (generalized from paire's). "Not found in the codebase" is a reason to ask, never to unilaterally cut or soften a stakeholder's request: check the underlying data (not just the application layer), ask via `AskUserQuestion` with what exists vs. what would need building, and never present a cut as a fait accompli — doubly so for leadership requests, whose phrasing may be deliberately illustrative.
2. **`process/verify-command.md`** — New § Companion: the Project Launch-Recipe Skill: the convention of a project-local `.claude/skills/verify/` skill capturing launch commands, end-to-end drive instructions, and accumulated environment gotchas; seeded on first rediscovery, grown per gotcha. The framework defines the convention; the content stays project-specific.
3. **`CLAUDE.md`** (source repo) — Versioning refinement (CD decision, 2026-09-02): purely additive `contract_changes.yaml` entries — opt-in bundle debuts, manifest field additions with back-fill defaults — are **minor**, not major; major is reserved for entries that force behavior change on existing installs.

**Rationale:** (1) is a judgment-boundary rule that generalizes cleanly: codebase absence ≠ infeasibility, and the requester owns the call. (2) names a pattern the built-in `run` behavior already looks for, so projects stop rediscovering their own launch procedure. (3) keeps major bumps meaningful — a convention no project is forced to adopt should not signal breakage.

---

## 2026-09-02: Debut github-provenance bundle (upstreamed from paire-appetit D52)

**Origin:** paire-appetit built a full GitHub provenance convention as their D52 — every tracked deliverable narrated into a GitHub issue via lifecycle checkpoints (CP-1…CP-12 + CP-S1/S2), with Projects v2 board tracking under a forward-only floor rule, a never-block invariant, SHA-pinned artifact links, and a read-only reconciliation audit dimension. It was live-verified against real boards (their Phase 6), which among other things discovered that GitHub accepts a wrong board's option ID silently — making name-then-resolve-per-session the only guard against silent mis-writes. This entry generalizes and upstreams the whole convention as an opt-in bundle. Design cross-checked via the external review gate (Codex, 18 findings triaged): config survives migration via a PROJECT-SECTION-wrapped config block, "configured" is machine-defined (`enabled: true` set last in Enablement), issues-only mode (`board: none`) supported, label provisioning and preflight in Enablement, predecessor detection at the migrate offer.

**Changes made:**

1. **`process/github-checkpoints.md`** — New policy doc (bundle-delivered). Owns the checkpoint map, column **roles** (`registered`/`spec-approved`/`executing`/`stakeholder-blocked`/`validated`/`staged`) mapped to per-project names/ranks in a `PROJECT-SECTION`-wrapped config block, the floor rule + CP-S2 exact-match exception, never-block + miss-log, catalog-wins + reconciliation cutoff, never-reopen, repo selection (single-repo first), labels (universal + project-defined conditionals), pre-deliverable `Parked:` promotion path, SHA-pinned links, commit conventions, call budgets with two exemptions, terminology + content prohibitions (config-extensible), all comment templates, failure classes, checkpoint confirmation carve-out, and the six recipe names. § Activation defines the two-stage gate (installed + `enabled: true`); § Enablement is the guided setup (preflight, board column verification, label provisioning, miss-log gitignore, cutoff, `enabled: true` last).
2. **`skills/sdlc-manage-github/SKILL.md`** — New skill (bundle-delivered). Interactive `gh` procedures for Projects v2 boards/issues (the github MCP tools 404 on board items), plus § SDLC Checkpoint Recipes: `create-or-link` (idempotent by `Dnn` prefix, `registration`/`parked` modes, promotion path, idempotent board add), `resolve-and-write-status` (role→name→ID per session, floor rule, CP-S2 flag, NEVER-WRITE hard guard, no-op in issues-only mode), `link-sub-issue`, `commit-and-push-artifact` (pathspec-only, rebase-once, SHA re-capture), `log-miss` (atomic JSONL append), shared failure-class→action lookup, and the verified cross-board option-ID hazard note.
3. **`bundles/github-provenance/fragments/*.md`** — Eight fragments injected as `BUNDLE-SECTION` blocks: checkpoint ownership sections for `sdlc-plan` (CP-1/2/3, S-pair), `sdlc-lite-plan` (CP-1/3, S-pair — no spec gate), `sdlc-execute` (CP-4–9, S-pair), `sdlc-lite-execute` (CP-4/5/7/8, S-pair — no CP-6/9), `sdlc-handoff` (CP-11/11b), `sdlc-archive` (CP-10 two-part, CP-12, parked closure, archive-time checklist executor); a Dimension 10 dispatch hook for `sdlc-audit`; and the full § GitHub Provenance Reconciliation (10a–10j) for `sdlc-compliance-auditor`. Every fragment opens with the activation gate and inlines the DIRECTIVE-level rules (never-block, comment-before-Status, the CP-3/CP-6 trap notes) while reading DATA (templates, ranks) from the policy doc.
4. **`skeleton/manifest.json`** — `bundles.github-provenance` registered with `skills`, `process`, and `fragments`.
5. **`skeleton/contract_changes.yaml`** — Entry 0014 (`bundle_debut`) with predecessor-detection notes for hand-rolled installs (paire-appetit itself: adopt-preserving-config, retire hand-wrapped equivalents on their next migration); bundle_debut type comment updated for the extended shape.
6. **`process/commands.md`** — `/sdlc-manage-github` row (marked as bundle-delivered).
7. **`CLAUDE.md`** (source repo) — `bundles/` row in the structure table; consistency-check globs and manifest comparison extended to bundle entries.
8. **Post-D52 refinement sync** — paire evolved the convention after the initial port was drafted (their commits of 2026-08-14…24, pulled mid-session); all four refinements are folded in: closed label taxonomy with the **silent label auto-creation** hazard (the REST create never fails on an unknown label — replaces the obsolete unknown-label retry fallback), § Issue Types (`Bug`/`Feature`/`Task` set on the same REST create call, `gh issue create` has no type flag; type silently dropped without push access → audit is the detector), § Board Fields: Ownership (human-owned fields incl. the Test Verdict example, the assignees convention, and the deliberate absence of estimate fields), the follow-up-issues-start-at-`registered` rule (with the originating project's 17-misfiled-issues incident), the completion-lives-in-comments rule (policy + skill + Red Flags — bodies go stale; CP-9–12 outcomes are comments), the full-read-before-classify triage rule, audit 10h upgraded from label presence to **taxonomy parity** (extra labels are drift; untyped open issues; stale column-scoped verdicts, report-only), and paire's create-or-link step-numbering fix ("skip to step 4 — step 3 is creation-only").
9. **External implementation review fixes (Codex, second pass — on the diff, not the plan)** — bundle-detection fallback restricted to skill paths so a hand-rolled `github-checkpoints.md` routes through §4.7 predecessor detection instead of being auto-marked installed; fragment injection extended to the content-merge flow (§2.2–§2.4 — most fragment targets are content-merged skills, not direct-copied files) in both `sdlc-migrate` and the marker doc; `installed_files` drift baselines explicitly include bundle-installed files (initialize + migrate back-fill); `create-or-link` step 4 now explicitly writes the `registered` option after a fresh board add (a new item is otherwise column-less) and states the comment-before-Status ordering on the link path; mechanical cautions added for `content.repository` shape and pagination-at-the-limit (recipe + audit dimension); the audit-skill fragment states outright that "all 9 dimensions" language is superseded when the dimension is active.

**Rationale:** The provenance layer makes SDLC work legible to people who will never open the markdown vault, without the issue ever becoming a second source of truth — the catalog stays canonical, the board is a projection corrected forward-only, and a checkpoint can never stall the work it narrates. Shipping it as a fragment-carrying bundle keeps core skills clean for the majority of projects that will not enable it, while adopters get the full DIRECTIVE-inlined sections and every future policy improvement on migration. The role indirection (`registered`…`staged`) keeps the checkpoint map stable across projects whose boards name columns differently, and `board: none` gives issue-only projects the narrative without Projects v2.

---

## 2026-09-02: Bundle fragment injection (BUNDLE-SECTION) and bundle process files

**Origin:** Upstream adoption of paire-appetit's GitHub provenance convention (their D52). The convention needs ~40–50-line checkpoint sections inside six core lifecycle skills plus an auditor dimension — content that must not ship as dormant dead weight to projects that decline the bundle, and must not freeze at install time the way hand-wrapped `PROJECT-SECTION` blocks do. Design cross-checked via the external review gate (Codex), which drove the idempotency, ordering, offline-validation, and predecessor-detection requirements. This is Phase 1 (mechanism); the `github-provenance` bundle itself is Phase 2.

**Changes made:**

1. **`process/project-section-markers.md`** — New § BUNDLE-SECTION Markers: upstream-owned sibling of `PROJECT-SECTION`. Labels namespaced `bundle/fragment`; declared in `manifest.bundles.<name>.fragments` (fragment source file → target framework file); injection is strip-then-append (idempotent), alphabetical bundle order, no nesting; hand-edits inside markers are lost on migration by design; presence must match `installed_bundles`/`bundle_fragments`; injection counts as a file write for adapter `post-file-write`. Installer ordering rule: copy files → inject fragments → record in manifest last (crash under-claims, re-run repairs). Direct-copy flow and Validation sections updated to match.
2. **`skeleton/manifest.json`** — `bundles._comment` documents the extended schema: optional `process` and `fragments` fields alongside `skills`. (Also normalized a stray-indent directory entry.)
3. **`skills/sdlc-initialize/SKILL.md`** — Phase 1b bundle offer lists process docs and fragment targets; effective install set includes bundle `process` files; fragment injection step after all copies; `installed_bundles`/`bundle_fragments` written only after files + fragments land; Enablement-section offer for bundles that need per-project configuration. Manifest schema example and field docs gain `bundle_fragments`.
4. **`skills/sdlc-migrate/SKILL.md`** — §2.0a: effective process list, file-existence fallback covers bundle process paths, fragments-are-refreshed rule. §2.1 marker preservation: new step 7 injects current fragments from source at `[target_tag]` after PROJECT-SECTION re-injection. §4.5: new step 4a maintains `bundle_fragments` (add injected, drop upstream-removed). §4.7: offer lists process/fragment surface; predecessor detection for bundles whose `process` paths already exist in the project (adopt-preserving-config vs. skip); accept path copies process files, injects fragments, records manifest entries last, offers Enablement.
5. **`agents/sdlc-compliance-auditor.md`** — Dimension 7 marker validation extended: `BUNDLE-SECTION` pairing, orphaned-bundle-content check against `installed_bundles`, partial-install check against `bundle_fragments`, nesting with `PROJECT-SECTION` is critical.
6. **`skeleton/contract_changes.yaml`** — Entry 0013 (`manifest_field_added`, `bundle_fragments`, default `{}`) documenting the schema extension and the adapter posture.

**Rationale:** Bundles could previously carry only whole skills, so any bundle needing hooks inside core framework files had two bad options: dormant sections shipped to everyone (recurring context cost in every downstream invocation, forever) or project-local `PROJECT-SECTION` blocks (frozen at install, silently staling as upstream evolves — the exact failure paire's hand-wrapped Dimension 10 block exhibits). Fragment injection gives bundles a third path: core files stay clean upstream, hooks exist only where the bundle is installed, and hooks refresh from source on every migration because migration overwrites with a clean upstream copy and re-appends the current fragment — no merging, ever. The mechanism is general-purpose: any future bundle (testing infrastructure, incident extensions) rides the same rails.

---

## 2026-07-21: 6n guard check verifies effective enforcement, not presence; versioning convention recorded

**Origin:** Sleeved D121 field report (via inter-session, evidence in Sleeved ADR-15 and the D121 result doc): their `zustand-selector-missing-useshallow` guard shipped with the rule set to `off` behind a stale justification comment — both 6n's "guard exists" check and their local wiring script read it as fully wired, because presence-in-config was checked but not effective enforcement. Related sub-gap: conditional-registration wrappers (`plugin.rules["x"] ? {...} : {}`) defeat text-grep wiring checks the same way. Caught only by a completion review. Sleeved correctly declined a local patch (framework owns check design) and fed it upstream.

**Changes made:**

1. **`process/guardrail-lifecycle.md`** — Freshness check 1 renamed "Guard exists and enforces": parse effective severity (`off` = CRITICAL, same as missing; `warn` = WARNING unless `notes` documents advisory intent), evaluate conditional registration for runtime collapse, skipped tests and continue-on-error CI steps count as not enforcing, known-bad-sample fallback when static reading is inconclusive. `location` spec and new Red Flag ("presence ≠ enforcement") updated to match.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — 6n check 1 extended identically.
3. **`CLAUDE.md`** — Versioning convention recorded (CD decision, v1.7.0/v1.7.1): minor for new contract surface (new cross-skill contracts, command surface, downstream data schema); patch for iterations, fixes, and check strengthening within existing contracts.

**Rationale:** The first field deployment of 6n produced a guard that passed the freshness check while enforcing nothing — the exact failure 6n exists to catch. One fix (read effective enforcement from config semantics, not string presence) closes both the severity blind spot and the conditional-wrapper gap.

---

## 2026-07-20: Review-time mechanization-threshold trigger in sdlc-review-code

**Origin:** Sleeved D121 (CD-approved, via inter-session): per-review pattern logging and audit-cadence triage were only connected by the next audit happening to run — a cluster could cross the mechanization threshold and sit unproposed for weeks.

**Changes made:**

1. **`skills/sdlc-review-code/SKILL.md`** — Step 6d: when logging brings a `promoted: false`, non-guarded cluster to 3+ occurrences within Dimension 6l's 30-day window (6l's threshold definition reused verbatim, not redefined), emit "Pattern {slug} crossed the mechanization threshold ({N} occurrences) — run `/sdlc-audit` to triage mechanization." Skips `mechanization_assessed: excluded` clusters. Nudge only — no triage or field-writing from within the review skill.

**Rationale:** Threshold crossings now surface in the same review that causes them, while the decision itself stays at audit triage where CD gates it.

---

## 2026-07-20: Guardrail exclusion marker — "assessed, deliberately not mechanized, do not re-propose"

**Origin:** Inter-session report from Sleeved's D121 reconciliation against the just-landed `guardrail-lifecycle.md` — first downstream contact with the contract found a gap: a cluster clearing the 3+ threshold whose manifestations are heterogeneous (would need a semantic allowlist that doesn't exist). CD chose exclusion, but the contract had no way to record it, so 6l and reflect would re-propose every cycle and CD would re-dismiss forever.

**What happened:** Sleeved adopted local fields `mechanization_assessed: excluded` + `mechanization_reason`; upstream adopts the same names verbatim so the local data becomes canonical on next migration.

**Changes made:**

1. **`process/guardrail-lifecycle.md`** — New § "Assessed and Excluded — Do Not Re-Propose": field schema, semantics (set only at triage; exclude ≠ defer; guards only — knowledge promotion unaffected; reversible at triage; new occurrences accumulate info-tier but never auto-reopen). Red Flag row for the re-propose nag.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — 6l.1 validates the fields; 6l.2 skips excluded clusters from guard-candidate output, lists them info-tier with reasons; output format shows the excluded section; triage note distinguishes decline-with-exclusion from defer.
3. **`skills/sdlc-reflect/SKILL.md`** — Step 4b skips excluded clusters.
4. **`skills/sdlc-review-code/SKILL.md`** — Step 6 optional-fields note covers the exclusion fields (don't strip them when appending occurrences).

**Rationale:** A promotion pipeline that cannot record "no, and stop asking" trains CD to ignore its proposals. Exclusion keeps the decision durable, audit-visible (info-tier listing, never hidden), and reversible — without turning every dismissal into a permanent burial. Additive only; no reference-pattern changes, no `[contract-change]`.

---

## 2026-07-20: Guardrail lifecycle, KEEP-IN-SYNC lens, codebase-health audit mode, verify-command convention (Sleeved upstream contributions)

**Origin:** Cross-repo handoff from Sleeved (`docs/current_work/ideas/cc-sdlc-upstream-contributions_handoff.md`, sourced from Sleeved's 2026-07-17 repo-wide quality audit). Four framework-shaped improvements identified downstream that would be clobbered by `sdlc-migrate` if implemented there.

**What happened:** Sleeved's `recurring-patterns.yaml` accumulated ~40 pattern clusters, several recurring for months because nothing converts a recurring pattern into a mechanized guard (lint rule, drift test, CI check) — and nothing re-evaluates guards once created. Separately: the `manually-synced-parallel-copies-drift` pattern hit 5 occurrences (copies diverging in the very commit adding the "keep in sync" comment); the audit's product-substrate sweeps proved a generic recipe worth a first-class audit mode; and the top agent-ergonomics gap was the absence of a discoverable one-shot verify command.

**Changes made:**

1. **`process/guardrail-lifecycle.md`** (new) — The cross-skill guardrail contract: LOG → THRESHOLD → PROMOTE → ENFORCE → RE-EVALUATE → MODIFY/RETIRE. Defines the `mechanized_guard` field on recurring-pattern clusters, mechanizability criteria (textual/structural/behavioral signatures), guard-freshness checks, the guard-modification-in-scope rule, and enforcement floors. Framework defines the loop; projects supply the actual rules/tests.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — 6l extended: validates optional `knowledge_entry`/`mechanized_guard` fields, flags guard-promotion candidates (mechanizable patterns at threshold) alongside knowledge-promotion candidates; triage promotion note covers the guard path. New **6n Mechanized Guard Freshness**: guard-exists, recurred-despite-guard, suppression-growth, never-fired checks.
3. **`skills/sdlc-audit/SKILL.md`** — Four modes (was three): new **Codebase Health mode** auditing the product substrate via three parallel read-only sweeps (test/CI activation, agentic ergonomics, observability blind spots) with SCOPE → SWEEP → SYNTHESIZE → ROUTE workflow; report to `docs/current_work/audits/`, gaps route to handoffs/plans/parking lots, never fixed in-mode. Dimension 6 summary, triage section (guard promotions + 6n findings), Red Flags, Integration, and frontmatter triggers updated.
4. **`skills/sdlc-audit/references/codebase-health.md`** (new) — Full health-mode methodology: dispatch discipline, the three sweep prompts, report format, merged top-gap ranking (cap 10), routing rules, recurring-pattern cross-referencing.
5. **`skills/sdlc-review-code/SKILL.md`** — Step 6 documents the post-promotion `knowledge_entry`/`mechanized_guard` fields and flags "recurred despite guard" in the patterns table; Step 5a adds the two-part guard-modification-in-scope rule; Integration references the lifecycle doc.
6. **`process/review-fix-loop.md`** — Step C: FIX findings matching a guarded (or plainly guardable) recurring-pattern cluster get two-part fixes — instance + guard — consumed by all execution skills.
7. **`skills/sdlc-reflect/SKILL.md`** — New Step 4b: session-scoped recurring-pattern guard scan (reuses 6l thresholds, no redefinition) proposing guard promotions and flagging recurred-despite-guard; report section, Red Flag ("reflect proposes, triage decides"), Integration updated.
8. **`process/review-lenses.md`** — Contract Safety Lens: manually-synced parallel copies bullet — a KEEP-IN-SYNC comment is itself a defect; require single source of truth or a drift-detection test; grep-based CI floor sanctioned.
9. **`process/verify-command.md`** (new) — The one-shot root `verify` command convention: chains the gates CI runs, documented in CLAUDE.md, invoked by the review-fix loop's verification gate.
10. **`skills/sdlc-initialize/SKILL.md`** — New Phase 9b: check for the verify command, offer scaffolding (chain what exists, report gaps, don't invent tooling); Phase 10 checklist line added.
11. **`agents/sdlc-compliance-auditor.md`** — Dimension 6 summary mentions 6l recurrence and 6n guard freshness.
12. **`process/commands.md`** — `/sdlc-audit health [scope]` row.
13. **`skeleton/manifest.json`** — Added `process/guardrail-lifecycle.md`, `process/verify-command.md`, `skills/sdlc-audit/references/codebase-health.md`.

**Rationale:** Review-pattern logging existed (review-code Step 6) and knowledge promotion existed (audit 6l), but the loop dead-ended at "agents were told" — nothing made the *machine* catch a recurring pattern, and nothing watched guards after creation. This closes the loop end-to-end with explicit ownership: review-code logs, reflect and 6l propose, CD decides at triage, projects implement, 6n re-evaluates, review loops maintain. The KEEP-IN-SYNC lens and verify-command convention are the two cheapest universal wins from Sleeved's evidence; the health mode generalizes an audit recipe already validated against a real repo. No knowledge-layer reference patterns were changed — all new references use canonical phrasing, so no `[contract-change]` tag is needed.

---

## 2026-07-19: Frontier once-over made unconditional for all promotion candidates

**Origin:** CD directive — promotion candidates should never be validated by shipped-deliverable evidence alone; every candidate must be reviewed by a frontier-tier agent (Codex external wrapper at xhigh, or Fable subagent) before reaching CD.

**What happened:** The Promotion Verification Gate had a skip path: a single well-evidenced entry (direct deliverable evidence, batch < 3) bypassed the judge panel entirely and went straight to CD. That entry never received any independent model review — inconsistent with the gate's own rationale, since deliverable recurrence proves a pattern was used, not that its embedded factual claims are true, and the compounding risk of a wrongly promoted entry applies equally to skip-path entries.

**Changes made:**

1. **`process/discipline_capture.md`** — Skip path narrowed: single well-evidenced entries may skip the screening panel (steps 2–4) but not the frontier once-over (step 5); the neutral payload is built for them and the once-over verdict accompanies the CD presentation. Step 5 restated as unconditional for every promotion candidate, including screening-skip entries.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — §6c evidence-production note and step 11a gate description updated to match: the once-over is unconditional; deliverable evidence alone never carries a candidate to CD without an independent frontier-tier fact-check.

**Rationale:** The once-over machinery already exists and runs as a single batch dispatch, so extending it to skip-path entries costs almost nothing while closing the only route by which a promotion candidate could become knowledge-store precedent with zero independent model review. Frontier budget stays concentrated at promotion time, where the risk asymmetry justifies it — parking-lot triage of non-candidates remains cheap.

---

## 2026-07-18: Standard external-review wrapper templates; drop "different model family" from model-facing prompts

**Origin:** CD follow-up to the 2026-07-17 planning integration: "we don't need to say 'from a different model family'. also, we can adopt a standard template from ~/Projects/neuroloom."

**What happened:** The gate doc's example wrappers were toy inline sketches, while the Neuroloom installation had a production-hardened wrapper pair (stdin passthrough to dodge ARG_MAX, `-o` final-message capture so codex noise never reaches the findings contract, `--sandbox read-only --ephemeral`, stderr egress disclosure, mktemp/trap cleanup, and empty-output-is-failure handling in the knowledge judge). The planning payload rubrics also told the external model it was "from a different model family" — unnecessary framing in model-facing text (the cross-family rationale belongs in the docs, not the prompt).

**Changes made:**

1. **`templates/external-review.sh.template`** (new) — Codex-backed standard wrapper adopted from the Neuroloom installation, with the embedded prompt generalized to payload-neutral: it defers to the payload's rubric header for artifact, task, and output format, so the one wrapper serves diff review, plan review, and approach consults.
2. **`templates/external-review-knowledge.sh.template`** (new) — Neuroloom's knowledge-judgment wrapper adopted as-is (paths converted to `[sdlc-root]`), including its contract difference: empty stdout exits non-zero so the Promotion Verification Gate falls back to an internal subagent judge.
3. **`process/external-review-gate.md`** — "Example wrappers" replaced by "Standard template": documents the shipped template, its operational details, and enable-by-copy instructions; the local-Ollama variant stays as the sensitive-codebase alternative. Wrapper-contract bullet updated from "cc-sdlc ships no default wrapper" to the template + copy/chmod stance. Knowledge-judgment section's inline example replaced with a pointer to its template. Removed "from a different model family" from the Codex example prompt and both planning payload rubrics.
4. **`skeleton/manifest.json`** — Both templates added to `source_files.templates`; `_templates_note` updated (non-.md template files install too; `*.sh.template` files are inert until a project copies and chmods them — the gate activates on the executable copy, never the template).
5. **`skills/sdlc-migrate/SKILL.md`** — Template copy rules widened from `templates/*.md` to all manifest-listed template files, with an explicit guard: never copy a `*.sh.template` onto the executable wrapper path, and never overwrite a project's enabled `external-review*.sh` (project-authored).
6. **`process/path-mappings.md`** — `templates/*.md` row generalized to manifest-listed template files.
7. **`CLAUDE-SDLC.md`** — Gate paragraph now names the shipped templates and the copy + chmod enable path.

**Rationale:** A production-tested wrapper encodes half a dozen non-obvious operational lessons; shipping it as a template means the next project enables the gate in one copy instead of rediscovering ARG_MAX limits and codex stdout noise. Keeping templates inert (`.sh.template`, non-executable, in `templates/`) preserves the gate's activation semantics — presence of the executable wrapper remains the project's explicit egress opt-in. And prompts sent to the external model should carry task instructions, not meta-commentary about the ensemble's composition.

---

## 2026-07-17: External reviewer becomes a first-class planning participant

**Origin:** CD directive — "integrate our external reviewer into planning as well. It should be more of a first-class resident in the SDLC if it is configured… deliberation between models is much stronger when they're of different families."

**What happened:** The External Review Gate participated only at execution time (post-internal-loop diff review) and knowledge promotion. Planning — where decisions are structural and cross-family disagreement is most valuable — had no external participation. The gate was also framed as "opt-in per run," leaving configured projects under-using a capability they had already paid to set up.

**Changes made:**

1. **`process/external-review-gate.md`** — Reframed intro as a lifecycle-wide participant with a three-point integration table (planning / execution / knowledge promotion). Added a "First-class once configured" presence policy: enabling is opt-in via wrapper presence, but once configured, participation is the default at every integration point, with named skip conditions the only sanctioned skips. Added § Planning Integration defining (1) the approach deliberation consult (payload, `RECOMMEND \| <approach> \| reason` output line, advisory-only, frontier/`xhigh`) and (2) the plan review ensemble member (spec+plan payload, `SEVERITY \| artifact § section \| finding` output, same classification table, `[external:<model>]` attribution, 2-round cap, mid-tier/`high` default). Generalized the wrapper contract so the payload rubric header owns task framing and output format (wrapper is transport; old-contract wrappers keep working via the default format); updated both example wrappers to be payload-neutral. Updated "When to run it" with per-point skip conditions and the planning invocation sites.
2. **`skills/sdlc-plan/SKILL.md`** — Step 3d: added `External consult:` line to the APPROACH-DECISION block and the external deliberation consult procedure (run before selecting when approaches are compared; on disagreement present both positions to CD via AskUserQuestion). Step 5: external reviewer added to the review dispatch checklist and roster (same round as domain agents), findings attributed `[external:<model>]` in the classification table, re-review participation capped at 2 rounds, Domain Agent Reviews attribution rule extended. Two new Red Flags rows (external reviewer is not code-review-only; disagreement is signal, not authority — neither defer nor ignore). Integration section links the gate doc.
3. **`skills/sdlc-lite-plan/SKILL.md`** — Step 3: external reviewer joins the review roster when configured (plan-only payload, mid-tier/`high`, `[external:<model>]` attribution, 2-round cap, never blocks on availability). Worker Agent Reviews attribution rule extended; new Red Flags row; Integration section links the gate doc.
4. **`process/debate-protocol.md`** — § Cross-Vendor External Reviewer updated: first-class once configured; final pass at execution time, but *alongside* the internal roster at planning time (plan review is a single ensemble round, not a fix loop — independence is maximized by parallel review).
5. **`CLAUDE-SDLC.md`** — "Optional external review gate" paragraph retitled "External review gate — first-class when configured" and extended to name the planning integration points.

**Rationale:** The value of an external reviewer comes from vendor-level independence — a different training distribution fails on different edge cases. That independence pays most where decisions are structural and cheapest to change: planning. Reviewing a plan costs a fraction of reviewing a diff, and a caught phasing or approach error avoids the 10x cost of unwinding it during execution. Making participation default-on when configured (instead of per-run discretionary) converts an occasional second opinion into genuine cross-family deliberation, while the advisory-only + same-triage + 2-round-cap constraints keep the Manager Rule and anti-conformity safeguards intact.

---

## 2026-07-13: sdlc-audit Deep Verify — opt-in retroactive knowledge content verification (§6m)

**Origin:** ChronoCore handoff (`sdlc-audit-deep-verify-mode_handoff.md`), sibling to the promotion-verification-gate handoff. After two worked runs of the multi-judge pattern (18-entry promotion batch, then a 674-entry full-store retroactive sweep that found 45 real defects — ~1 in 15 entries — in content unreviewed since ingestion), CD asked where the retroactive version should live upstream. Decision: an opt-in `sdlc-audit` mode — not the default run (an order of magnitude costlier than the file-read/grep dimensions), not a standalone skill (audit already owns provenance reading, the §6c authority matrix, and the step 11 triage flow the findings feed).

**What happened:** The Promotion Verification Gate covers content entering the store, but nothing re-verified content already inside — entries predating the gate, drifted since ingestion, or contradicting the code they describe (worked example: an entry claiming all four effect classes route through a pipeline that its own `pipeline:` field showed handles two). The ChronoCore sweep also had to invent tooling mid-session (a comment-preserving YAML entry remover, because `yaml.safe_dump()` round-trips destroy hand-authored `# =====` banners) that should ship with the mode, not be re-derived per project.

**Changes made:**

1. **`skills/sdlc-audit/references/deep-verify.md`** (new) — Full mode spec: opt-in-by-name activation (mirrors the external-review-gate's disabled-by-default shape); orchestrator-run, never the `sdlc-compliance-auditor` subagent (needs `AskUserQuestion`, judge dispatches, egress disclosure); mandatory pre-flight `AskUserQuestion` with cost estimate, egress disclosure, and scope selection (full / domain / stale-only via §6h / incremental since last `audit-sweep` provenance entry); claims-vs-reference content scoping with ambiguous files flagged to CD, never silently decided; judge mechanics by reference to the Promotion Verification Gate with `KEEP|DEMOTE` verdicts (screening tier, fact-check lens, frontier tie-breaks, once-over of the keep-bound slate); embedded reusable scripts (payload extraction + comment-preserving entry removal); demotion mechanics; provenance logging; red flags.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — New §6m dimension (explicitly excluded from the default sweep and from the auditor subagent's scan; sequence note added after step 11 list). §6c authority matrix gains a demotion row: Promoted/`[READY TO PROMOTE]` → `[NEEDS VALIDATION]` is CD decision (step 11), proposed with multi-judge DEMOTE verdicts, **batch-level approval per discipline acceptable** with factual-error dissents and splits listed individually — resolving the handoff's open question on demotion authority (CD-gated, but at batch granularity; per-entry adjudication at 45-demotion scale is the same failure mode the tie-break judge exists to prevent). Step 11 intro gains Deep Verify as a third candidate source; step 11c gains the Demote path (comment-preserving removal, parking-lot restoration with judges' reasoning, `Promoted →` ledger pointer fixes, `last_updated` bump, one provenance entry per sweep).
3. **`skills/sdlc-audit/SKILL.md`** — Three-mode frontmatter with deep-verify trigger phrases ("deep audit", "deep verify", "verify the knowledge store", "full content sweep"); modes table and Input Resolution rows (`/sdlc-audit deep-verify [scope]`) with an explicit "never activates implicitly" rule; new Deep Verify Mode section (workflow summary + non-negotiable gates, details in the reference file); Integration and Reference Files updated; red-flag row against opportunistic deep-verifying during a compliance audit.
4. **`knowledge/provenance_log.md`** — `source-type` enum gains `audit-sweep`; conventions note that sweep entries record scope/judge-config/counts and serve as the incremental-scope boundary marker.
5. **`process/commands.md`** — `/sdlc-audit deep-verify [scope]` command row.
6. **`skeleton/manifest.json`** — `skills/sdlc-audit/references/deep-verify.md` added to `source_files.skills`.
7. **`agents/sdlc-compliance-auditor.md`** — Explicit exception under "Full coverage": §6m is opt-in and orchestrator-run; the auditor never executes it and reports it as "opt-in, not run" in coverage rather than as a gap.

**Rationale:** The ~1-in-15 defect rate in never-reverified content justifies the capability existing; the two-hour/dozens-of-dispatches cost profile justifies it never running by default — the handoff's own answer to "should full-store re-verification be scheduled?" is "no: available, opt-in, on the project's cadence." Routing findings through the existing step 11 triage instead of a parallel flow keeps one authority model (the §6c matrix) governing every marker transition in both directions. The judge mechanics are referenced from the gate rather than duplicated, so the two-tier/fact-check/once-over refinements land in one place. Not a `[contract-change]`: no knowledge-layer reference phrasing changed.

---

## 2026-07-13: Promotion gate — two-tier judging (screen cheap, escalate splits), mandatory fact-checking lens, frontier once-over

**Origin:** Retroactive gate run over ChronoCore's 674 already-promoted knowledge entries: 540 unanimous PROMOTE, 12 unanimous DEMOTE, **122 splits** — far too many for one-by-one CD adjudication. Sampling showed the splits were signal, not noise: Codex was fact-checking specific claims embedded in entries (PostgreSQL lock-escalation semantics, `REINDEX CONCURRENTLY` locking, OCI image-signing order, stale DORA thresholds, a 4xx-retry rule contradicting its own 429 guidance) while the Fable judge evaluated "is this a recognized general pattern?" and passed them. CD directives: run the initial external-judge pass at a low/mid tier with medium/high reasoning, elevate model and/or effort for tie-breaks, and add a final high-model once-over to verify the lower tiers got it right.

**What happened:** The gate as first shipped ran everything at the frontier tier (`xhigh`) and escalated every split to CD with full reasoning — a design that worked at prototype scale (18 entries, 5 splits) and collapses at batch scale (674 entries, 122 splits). The retro also exposed a judge-instruction gap: nothing required judges to verify embedded factual claims, so a pattern-recognition lens could PROMOTE entries containing checkable errors.

**Changes made:**

1. **`process/discipline_capture.md`** — Gate step 2 becomes the **screening tier**: external judge at a balanced/mid-tier `CODEX_MODEL` with `CODEX_REASONING_EFFORT=high`; subagent judge at `model: "opus"`. Step 4's split handling becomes **escalate model/effort, not CD**: one fresh frontier-tier tie-break judge (frontier `CODEX_MODEL` at `xhigh`, else `model: "fable"` subagent), blind to the split, same fact-checking instructions; the 2–1 majority applies with dissent recorded. New requirement in step 2: every judge's instructions must demand fact-checking of specific claims (numeric thresholds, version-sensitive benchmarks, protocol/API semantics, internal consistency) — a recognized pattern containing a false specific claim is a DEMOTE. New flag rule: a 2–1 PROMOTE overriding a factual-error dissent is flagged prominently to CD rather than buried by the majority. New step 5: **frontier once-over** — the full promote-bound slate (unanimous and tie-broken PROMOTEs) gets one final frontier-tier judgment as a single batch dispatch, blind to earlier verdicts, before CD presentation; its DEMOTEs are frontier dissents flagged to CD, never silently applied or discarded. Demote-bound entries are not re-reviewed — the risk is asymmetric (a wrong promotion compounds; a wrong hold-back waits a cycle).
2. **`process/external-review-gate.md`** — § Task-Based Model Selection effort guidance rewritten as "screen cheap, escalate splits" (frontier tier reserved for tie-breaks, the final once-over, and high-risk diffs); Knowledge-Judgment Wrapper section documents the tiers; example knowledge-judge wrapper default effort `xhigh` → `high` and its prompt gains the fact-checking instruction.
3. **`skills/sdlc-audit/references/compliance-methodology.md`** — §6c evidence-production note and step 11a updated to the tie-break flow (splits resolved by frontier-tier judge, factual-error dissents flagged to CD) plus the final frontier once-over before 11b, instead of per-split CD escalation.

**Rationale:** Two empirical lessons from the first at-scale run. (1) Split volume grows with batch size, so the human can't be the tie-breaker — but a frontier-tier judge can be, while CD keeps batch-level authority and gets the high-value splits (factual-error dissents) surfaced instead of all 122. (2) The most valuable verdicts came from fact-checking embedded claims, not recognizing patterns — so that lens is now a required judge instruction rather than an accident of which vendor's model happened to apply it. Screening at mid-tier/high is the cost floor that makes 674-entry batches feasible; the retro showed unanimity is the common case (82%), so frontier capacity is only spent where it pays: the ~18% that split, plus one batch-level once-over that backstops the screening tier on everything about to enter a knowledge store.

---

## 2026-07-13: Task-based model selection for Codex-backed external-review wrappers

**Origin:** CD directive in a cc-sdlc source session: when Codex is configured as an external reviewer, allow the orchestrator to choose model and reasoning effort per task (`codex -m <model> --config model_reasoning_effort="xhigh"`), resolving current model names at runtime from https://developers.openai.com/api/docs/models.

**What happened:** The wrapper contract gave the wrapper sole ownership of model choice, so every external review ran at the wrapper's single hardcoded configuration regardless of stakes — a docs-only diff and a knowledge-promotion verdict got the same model and effort.

**Changes made:**

1. **`process/external-review-gate.md`** — New "Task-Based Model Selection" section: Codex-backed wrappers pass through optional `CODEX_MODEL` / `CODEX_REASONING_EFFORT` env vars set by the invoking skill at the call site; wrapper defaults apply when unset. Model names must be resolved at runtime from OpenAI's model catalog (WebFetch https://developers.openai.com/api/docs/models), never recalled from training data — if the catalog can't be fetched, leave `CODEX_MODEL` unset rather than guess. Effort guidance: top-tier model at `xhigh` for high-stakes single-shot judgments (promotion verdicts, auth/payments/migrations/concurrency diffs), `medium` for routine second opinions. Wrapper-contract bullet updated (wrapper provides the *default* model, honors the passthrough); both Codex example wrappers updated — diff reviewer defaults effort to `medium`, knowledge judge to `xhigh`. Egress disclosure now names the actual model used.
2. **`CLAUDE-SDLC.md`** — External review paragraph mentions the env-var convention and the runtime model-resolution rule.

**Rationale:** External review quality should scale with task stakes, and the framework shouldn't embed model names that rot — OpenAI's catalog changes faster than this repo. Env-var passthrough keeps the wrapper contract intact (project still owns endpoint, egress policy, and defaults) while letting the orchestrator escalate a high-stakes judgment to a frontier model at maximum effort without editing the wrapper.

---

## 2026-07-13: Promotion Verification Gate — multi-judge evidence before knowledge promotion

**Origin:** ChronoCore handoff (`promotion-verification-gate_handoff.md`). In a ChronoCore session, 18 `[NEEDS VALIDATION]` parking-lot entries were bulk-promoted on the orchestrator's own judgment, violating the §6c authority matrix ("Proposed with evidence during interactive triage"). A retrofitted 3-judge review (self + Codex + Fable subagent) demoted 10 of the 18 — empirical proof that single-agent self-certification fails at exactly this transition. CD asked for the gate to be formalized upstream. Design was reviewed by two independent judges (Codex via `codex exec`, plus this session's own analysis) before implementation; both agreed with three amendments adopted below.

**What happened:** Promotion to a knowledge store had a CD-only authority rule but no defined evidence-production mechanism — step 11a said candidates need "evidence" without saying how it gets produced, so orchestrators substituted their own reasoning. Worse, `sdlc-archive` step 9c instructed applying `[READY TO PROMOTE]` as a silent "reasonable default," directly contradicting the §6c matrix.

**Changes made:**

1. **`process/discipline_capture.md`** — New "Promotion Verification Gate" section before the Promotion Workflow: neutral no-verdict evidence payload; two independent non-orchestrator judges (external `external-review-knowledge.sh` wrapper if configured, high-tier Fable/Opus subagent always, second subagent as fallback); `N | PROMOTE|DEMOTE | justification` verdict format; the orchestrator does not vote or break ties; unanimous-PROMOTE goes to CD as verified, unanimous-DEMOTE is not proposed, splits escalate to CD with each judge's full reasoning. Proportionality rule: full gate required for batches of 3+ entries or any weakly-evidenced entry; a single well-evidenced entry may present its evidence directly (lighter path replaces the judges, never the CD decision). Rules section's audit-triage carve-out now points at the gate as how CD's decision gets evidence.
2. **`process/external-review-gate.md`** — New "Knowledge-Judgment Wrapper" section: parallel convention `[sdlc-root]/external-review-knowledge.sh` (separate wrapper, not a mode flag — different artifact, different contract), stdin = neutral payload, stdout = `N | PROMOTE|DEMOTE | justification`, non-zero exit falls back to a second internal subagent, same egress rules, with a Codex example wrapper.
3. **`skills/sdlc-audit/references/compliance-methodology.md`** — §6c gains an "Evidence production" note wiring the matrix's evidence requirement to the gate; step 11a specifies when to run the gate before 11b and how verdicts map to the candidate list (unanimous-DEMOTE drops the candidate with dissent appended to the parking-lot entry).
4. **`skills/sdlc-archive/SKILL.md`** — Step 9c no longer applies `[READY TO PROMOTE]` as a silent default (that contradicted the §6c CD-only rule): validated entries are flagged as promotion candidates in the triage table for CD, or annotated `(promotion candidate — [date])` if the table is skipped. Added an explicit note that archival identifies candidates but does not adjudicate — the gate runs at promotion time (audit step 11), keeping archival fast by design.
5. **`CLAUDE-SDLC.md`** — External review gate paragraph mentions the parallel knowledge-judgment wrapper.

**Rationale:** A knowledge store entry is precedent every future agent reads, so a bad promotion compounds — and the ChronoCore data shows self-certification approves bad promotions at a >50% rate. The gate's key design points came from the prototype and the two-judge design review: judges must reason from a shared verdict-free payload (independence), the orchestrator must not tie-break (it is the actor being checked — "self + one subagent" is one independent opinion, not a majority), split votes need full reasoning surfaced (a bare tally hid the "adjacent entry ≠ corroboration" distinction that caught most bad promotions), and the gate is scoped to batches/weak evidence so it stays a followed rule rather than skipped ceremony. Not a `[contract-change]`: no knowledge-layer reference phrasing changed.

---

## 2026-07-11: sdlc-reflect prunes agent memories session-scoped

**Origin:** CD directives in a cc-sdlc source session: "sdlc-reflect should attempt to prune agent memories," followed by "part of the reflect process should be figuring out if those entries warrant being entered into the parking lots."

**What happened:** Agent memory hygiene existed only as sdlc-audit Dimension 8b — a project-wide sweep that runs at audit cadence. Between audits, memories invalidated by ongoing work (stale claims, drifted duplicate values, MEMORY.md files creeping toward the 200-line/25KB load cap) accumulated with no lighter-weight cleanup point. sdlc-reflect already closes out ad-hoc sessions and surveys the session's diff, making it the natural place for a session-scoped prune.

**Changes made:**

1. **`skills/sdlc-reflect/SKILL.md`** — Added Step 5 "Prune Agent Memories" (Report renumbered to Step 6): session-scoped prune covering agents dispatched this session and memories whose claims the session's diff invalidated. Reuses the Dimension 8b check definitions (contradicts-code, duplicate/drifted values, size-cap split, orphaned directory), gates prunes behind a confirmation prompt, requires source verification before deleting, and treats pruning as best-effort — parking lot capture remains the primary deliverable. Step 5 also runs a promotion check before any deletion: memory entries passing the Step 2 filters (reusable, non-obvious, actionable) — whether pruned or kept — are routed to discipline parking lots with context `[memory: {agent-name}]`, marked `[NEEDS VALIDATION]`. Frontmatter description, preconditions, report template, Red Flags, and Integration/DRY notes updated; added anti-trigger routing project-wide sweeps to sdlc-audit.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — Dimension 8b note: sdlc-reflect applies the same checks session-scoped between audits and opportunistically routes generalizable memory entries to parking lots (lower bar than 8a's 2+-agent recurrence, same triage cycle); the audit remains the project-wide sweep and shouldn't be skipped on the assumption that reflect kept things clean.
3. **`CLAUDE-SDLC.md`** — Extended the post-session sdlc-reflect suggestion to mention the memory prune.

**Rationale:** Stale agent memories are a correctness risk (an agent trusting an invalidated claim is worse than one with no memory), and the session that invalidated a memory is the cheapest moment to catch it — the diff is already in hand. Pruning without a promotion check would silently discard insight: a memory invalidated by a change often documents why the old approach failed, which is exactly the kind of gotcha/anti-pattern signal the parking lots exist to catch. Scoping reflect's prune to the session keeps it fast and keeps the division of labor clean: reflect handles incremental hygiene and opportunistic capture, audit handles the exhaustive sweep and recurrence-based mining.

---

## 2026-07-09: Render precedes approval — never in sequence with the approval gate

**Origin:** CD directive in a cc-sdlc source session: "render should never happen in sequence with approval — it should precursor approval if the user chooses."

**What happened:** The post-skill render offer existed as a post-write step, but nothing constrained its position relative to approval gates. In practice this allowed the render offer to be bundled into the approval question, or the render to happen after approval as a follow-up — defeating the render's purpose as a review aid for the approval read. Worse, `html-rendering.md`'s re-render-on-plan-revision rule said "the HTML should reflect the approved plan," which reads as an instruction to render *after* approval.

**Changes made:**

1. **`process/html-rendering.md`** — Added "Render precedes approval — never in sequence with it" rule to the post-skill render offer section: the render offer is its own interaction, fully resolved (declined, or accepted with HTML delivered) before approval is requested; never bundled into the approval question, never rendered post-approval. Reworded the re-render-on-plan-revision rule: re-render after the final revision and *before* presenting for approval — CD approves what they see rendered.
2. **`CLAUDE-SDLC.md`** — Appended the sequencing rule to the post-deliverable render-offer paragraph.
3. **`skills/sdlc-plan/SKILL.md`** — Spec render offer (step 2) now states it must resolve before the step-3 approval gate. Step 6 (Prompt for Execution) gained a "Render precedes approval" pre-step: re-render the final revised plan before entering plan mode. Added two Red Flags rows (post-approval render offer; bundling render offer with approval question).
4. **`skills/sdlc-lite-plan/SKILL.md`** — Step 5 (Enter Plan Mode) gained the same "Render precedes approval" pre-step. Added a Red Flags row.

**Rationale:** The HTML render exists to give CD a better reading surface for the decision they're about to make. Sequencing it with or after the approval gate makes it decorative — the decision is already made by the time the render arrives. Fixing the sequencing at the process-doc level and at each approval gate ensures CD reviews the rendered artifact (if they opt in) before being asked to approve.

---

## 2026-07-09: Agent-memory hygiene — MEMORY.md cap enforcement, topic-file protocol, archive path fixups

**Origin:** Upstream handoff from a ChronoCore session that manually pruned `.claude/agent-memory/` (16 dirs, ~50 files) after severe drift — one `MEMORY.md` had reached 2628 lines, others contained content actively contradicting current code, duplicated tuned values with drifted numbers, and an orphaned predecessor-role directory. Web research confirmed Claude Code loads only the first **200 lines / 25KB** of `MEMORY.md` into the agent's system prompt (`MAX_ENTRYPOINT_LINES`), silently truncating the rest — and since entries append at the bottom, the *newest* notes are the ones dropped. The framework already named topic files as the remedy but only as a bare one-line suggestion with no size trigger, naming convention, or index framing, and nothing enforced the cap.

**Changes made:**

1. **`templates/agent-template.md`** — rewrote the Persistent Agent Memory guidelines into a real protocol: MEMORY.md-as-index framing, the 200-line/25KB cap with the "newest entries truncated" explanation, a split trigger (~180 lines), a topic-file naming/location convention (`.claude/agent-memory/{agent-name}/{topic}.md`, kebab-case, linked with one-line pointers), and explicit "replace drifted values, don't duplicate" guidance. Removed the redundant trailing `## MEMORY.md` section (its content is now covered above).
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — split Dimension 8 into **8a Pattern mining** (promotion signal, unchanged) and **8b Hygiene** (new fix signal): size-cap violation (Major, MEMORY.md only — topic files uncapped), contradicts-current-code, internal duplication, orphaned directory. States the read-only auditor reports with file+line and the orchestrator applies fixes.
3. **`skills/sdlc-audit/SKILL.md`** — added a **Memory hygiene triage** to Step 3 folded into the existing prune `AskUserQuestion` batch (no second gate); routed fixes to Step 4's orchestrator (has Write), resolving the read-only-domain-agent limitation without needing write-capable domain agents. Updated the Dimension 8 summary line.
4. **`agents/sdlc-compliance-auditor.md`** — updated Dimension 8 summary to name 8a/8b; extended the Major severity class to include over-cap and code-contradicting `MEMORY.md`.
5. **`skills/sdlc-archive/SKILL.md`** — added **Step 9d Agent Memory Path Fixups (mechanical only)**: scoped strictly to the archived deliverable(s) and to rewriting `docs/current_work/...` → `docs/chronicle/...` paths this operation just broke. Explicitly defers all judgment-based pruning to audit Dimension 8b; folds any task-log deletions into the Step 9c triage table (with a defined fallback when 9c is skipped).
6. **`CLAUDE-SDLC.md`** — added the MEMORY.md cap + topic-file index pattern to the agent-memory bullet so target projects see the rule in their merged CLAUDE.md.

**Rationale:** Detection of agent-memory drift already existed (Dimension 8 flagged stale/contradicting memories) but there was no *fix loop* and no *prevention* — findings were flagged and nothing acted. The split here is deliberate: the template is the prevention layer (agents split before they hit the cap), archive Step 9d is the incremental mechanical cleanup (fix only what an archive itself breaks), and audit Dimension 8b is the periodic judgment-based sweep. The over-cap flag is a correctness issue, not cosmetic — an agent over 200 lines is silently running on a memory it can't fully see. Adapter phrasing contract checked: `.claude/agent-memory/` is the private scratchpad, distinct from the knowledge layer the neuroloom adapter transforms, so no `[contract-change]` and no paired plugin edit.

---

## 2026-07-09: sdlc-execute — plan size is not a confirmation trigger

**Origin:** Observed in a target-project execution session (D105, 7-phase plan). After emitting the Phase plan table, the executor paused and asked an `AskUserQuestion` about "execution scope" (full run vs. backend-only vs. Phase 1 only) — a checkpoint the skill never sanctions. The question's "Full sequential execution" wording also contradicted the parallelism the Phase plan itself declared.

**What happened:** The skill already forbids pausing for confirmation at dispatch time ("the plan is already approved") and treats post-summary stopping as a red flag, but nothing addressed the specific failure shape: plan *size* triggering an invented pre-execution scope checkpoint right after the Phase plan emission.

**Changes made:**

1. **`skills/sdlc-execute/SKILL.md`** — added an explicit rule after the Phase plan emission instructions: proceed directly to the first wave's PRE-GATE in the same response; plan size is not a confirmation trigger; a scope question re-litigates the `sdlc-plan` approval. Added a matching Red Flags row ("This plan is very large — I should confirm scope before starting").

**Rationale:** Approved plans are executed, not re-negotiated. Large plans pattern-match to a generic "confirm before a long autonomous run" instinct; the skill now names and blocks that instinct at the exact point it fired.

## 2026-07-08: Planning orchestrator is Fable OR Opus (CD's choice, not prescribed)

**Origin:** CD directive — "fable or opus should be the planning agent depending on what the user wants." The just-added cheat-sheet leaned toward Fable as the planning default; CD clarified it is a choice between the two top-tier models.

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — MTS6 reworded: run planning on a top-tier model, Fable OR Opus at CD's discretion (choose by task, quota, preference; e.g. Fable flagship vs Opus 4.8 1M-context), explicitly "the framework does not prescribe one; the load-bearing split is planning-premium vs execution-Sonnet." Checklist item updated to match.
2. **`CLAUDE-SDLC.md`** — session cheat-sheet: planning Model cell now "Fable **or** Opus (CD's choice)"; added a "Planning model is your call" note; alias block now offers both `ccplan` (Fable) and `ccplan-opus` (Opus).

**Downstream:** Documentation — propagates on next migration.

**Rationale:** Both models are premium and interchangeable for the planning seat; prescribing Fable would over-constrain a preference/quota decision. What actually matters is that planning runs premium and execution runs Sonnet — not which premium.

## 2026-07-08: Session model/effort cheat-sheet + launch-alias recipe in CLAUDE-SDLC

**Origin:** CD found switching the session model and effort by hand every time they change between planning and execution painful, and asked for an easier way. Claude Code session-config mechanics were verified against current docs via a claude-code-guide subagent.

**What happened:** MTS6 said "plan on Fable/high, execute on Sonnet/medium" but nothing told CD *how* to apply that without friction. Added a CD-facing session cheat-sheet with the lowest-friction mechanism (launch aliases that set both dials at once).

**Changes made:**

1. **`CLAUDE-SDLC.md`** — new "Session Model & Effort (your orchestrator seat)" subsection: a plan-vs-execution model/effort table, the `ccplan`/`ccexec` launch-alias recipe (`claude --model fable --effort high` / `--model sonnet --effort medium`), and the verified mechanics — both are launch flags; switching model mid-session can reset effort (re-check `/effort` after `/model`); `settings.json` persists `effortLevel` but not `model`; no named profiles; SessionStart hooks can't drive `/model`. Distinguished the session dial from the per-agent frontmatter tiers.

**Verified mechanics (Claude Code docs):** `--model` and `--effort` are launch flags (effort values low/medium/high/xhigh/max); `settings.json` supports `model` and a persisting `effortLevel` field, but `model` does not hot-reload; `/model` and `/effort` switch mid-session; no named-profile mechanism exists.

**Downstream:** Documentation — propagates on next migration. Closes the loop between the MTS6 rule and its day-to-day application.

**Rationale:** A tier rule nobody can apply frictionlessly gets ignored. The alias recipe makes the plan-wide/execute-narrow split a one-word launch choice, so the guidance actually gets followed.

## 2026-07-08: AI/ML domain provisioning rule (function coverage, not agent count)

**Origin:** CD asked whether an AI-adjacent domain always warrants a dedicated ai-architect + ai-engineer duo.

**What happened:** Refined G5. The precise requirement is that two opus-tier FUNCTIONS are covered — AI system design/judgment, and AI-aware correctness review — not that two named agents always exist. Whether to dedicate a pair depends on how central AI is to the product.

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — added an `ai_ml_provisioning` block under `assignment_rules`: principle (two functions, not two agents; a single opus ai-architect can fill both design + escalated review); a core/feature/incidental decision (dedicate the duo only when AI is the core value prop; for a feature, inject the AI review lenses into the existing opus software-architect + code-reviewer; incidental gets generic agents + a security reviewer); and a "provision by function coverage, not agent count; right-size per AOP5" rule. Added an "AI/ML architect + reviewer" row (opus/high) to `archetype_table` and cross-linked it from G5.

**Downstream:** Documentation/rule change — propagates on next migration.

**Rationale:** "Always a duo" would over-provision feature-level and incidental AI usage (roster bloat, violates AOP5/M4) while under-specifying what actually matters — the two opus functions. Framing it as function coverage lets a project satisfy G5 with existing opus reviewers when AI is peripheral, and dedicate specialists only when AI is central (avoiding generalist-masking). paire-appetit's organic llm-engineer + taste-intelligence-engineer split is the reference for the core case.

## 2026-07-08: Consolidated model/effort assignment rules + field survey of 5 installs

**Origin:** CD asked (1) what rules govern setting `model` and `effort` on agents, including AI/ML agents, and (2) to evaluate the sub-agents actually installed across sleeved, ChronoCore, paire-appetit, endlessgalaxystudios, and neuroloom to see whether real usage warrants additional rules.

**What happened:** The tier rules existed but were scattered across MTS1–MTS7 and the AGENT_SUGGESTIONS note — not a followable procedure. A survey of 113 installed agents validated the ladder and surfaced three additions: a both-axes reviewer invariant, a project-level baseline pattern, and the finding that `effort` is unset on 113/113 agents (a migration backfill, not just a go-forward default).

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — added an `assignment_rules` block: axes definition; model rules M1–M4; effort rules E1–E4; guardrails G1–G5 (G5 = AI/ML correctness is not evidence-checkable, so the correctness review escalates to opus/high regardless of implementation tier, and a passing run is never verification); `reviewer_invariant` (reviewer ≥ implementer on the model-OR-effort axis); `project_baseline` (raise the whole project's implementer model for systematically-hard domains, then differentiate reviewers by effort); `archetype_table` (keyed by role archetype, not agent name); and `survey_2026_07` recording the field evaluation and its consequences.
2. **`skills/sdlc-develop-agent/SKILL.md`** — pointed the frontmatter step at `assignment_rules` as the authoritative procedure for both `model` and `effort`, emphasizing archetype-keying.

**Survey findings (recorded in the YAML):** effort unset on all 113 agents; `code-reviewer` sonnet in 3/5 (violates the opus-reviewer default); security-review agents inconsistent (opus vs sonnet); deep-debugging split opus/sonnet; AI/ML implementers sonnet with non-escalated reviewers (confirms the G5 gap); ChronoCore runs implementers at opus wholesale (the project_baseline pattern); role names drift across projects (rules must key on archetype).

**Downstream:** Documentation/rule change — propagates to child projects on next migration. The installed agents in the five surveyed projects were NOT edited (out of scope — the ask was rules, not fixes); backfilling their model/effort per these rules is a separate migration/audit action a future session can trigger. A future sdlc-audit dimension could flag violations automatically.

**Rationale:** Real-world installs showed the rules were needed (broad inconsistency) and surfaced patterns pure theory missed — especially that when a hard-domain project runs everything at opus, effort becomes the ONLY remaining reviewer-differentiation lever, which is the strongest argument for treating effort as first-class rather than optional.

## 2026-07-08: Record tier-override decision (structural over per-call/Workflow)

**Origin:** CD follow-up in the same session — after verifying that per-dispatch model/effort override is reliable only in Workflow scripts (not interactive Task dispatch), CD asked whether the manual override was worth the effort or whether designating general-tier reviewer agents suffices, and whether Workflows could cover spec/plan reviews as well as implementation review loops.

**What happened:** Decided to keep the structural approach (MTS7 — dedicated opus review-only agents) and NOT adopt per-call override or a Workflow orchestration rewrite. Reasoning: the opus cross-cutting reviewers already carry the highest-value lenses; escalating each domain agent's own review adds only modest depth at large architectural cost; Workflows fit only the mechanical implementation review loop (spec/plan review are human-gated and cannot run headless); and interactive per-dispatch override is a tracked Claude Code feature (GitHub #62211/#64033) that could make a Workflow rewrite obsolete if it ships.

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — added a `tier_override_decision` record after MTS7 capturing the question, decision, rationale, and explicit `revisit_if` triggers (per-dispatch override becoming documented; evidence that sonnet domain review misses defects the opus reviewers don't catch).

**Downstream:** Documentation-only; propagates on next migration. No behavior change — records why the current structure was chosen so a future migration does not re-litigate it.

**Rationale:** The decision hinges on facts that will age (Claude Code's dispatch capabilities, the #62211/#64033 roadmap). Recording the triggers that would flip the decision keeps the choice auditable and cheap to revisit rather than re-deriving it from scratch later.

## 2026-07-08: Agent-tier structure decisions + External Review Gate

**Origin:** CD design session following the model-tier-strategy ingestion (below). CD asked three questions: (1A) split subagents into reviewer/implementer roles or genericize into stage-based roles (spec/plan/code reviewer)? (1B) how does a dispatching agent override a subagent's hardcoded model — is it even possible? (2) how can cc-sdlc use one LLM as planner/orchestrator and another (Codex or a local LLM) as implementer/reviewer, at minimum for an extra external review phase? Claude Code mechanics were verified via a claude-code-guide subagent against current docs before answering.

**What happened:** CD decided: (1) keep domain + reviewer hybrid — no stage-generic roles; (2) wire tiers explicitly (domain writers=sonnet, review-only agents=opus, recon=effort:low); (3) build an External Review Gate via Bash CLI. Verified mechanics that shaped the design: subagent model resolves in order `CLAUDE_CODE_SUBAGENT_MODEL` env → per-invocation param → frontmatter → inherit, but per-invocation model/effort override is only reliable in Workflow scripts, not interactive Task dispatch; `effort:` frontmatter (low|medium|high|xhigh|max) is stable and overrides session effort; external models integrate via MCP-wrapped tool, Bash CLI, or the existing OpenCode local-serving path.

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — added MTS7: realize the reviewer/implementer tier gap through the write/review agent split (reviewer-only agents at opus), NOT through stage-generic roles or unreliable interactive dispatch override. Unifies decisions 1A and 1B — the tier gap is achieved structurally because cc-sdlc already separates reviewer agents from writer agents.
2. **`agents/AGENT_SUGGESTIONS.md`** — added a "Model & effort defaults" note to the intro; added `Suggested model: opus` to code-reviewer, security-auditor, and software-architect (the cross-cutting review-only layer).
3. **`process/agent-selection.yaml`** — tier1 header comment codifying: review is a mode not a role; review-only agents carry the escalated (opus) tier; recon agents effort:low; do not add stage-generic reviewer roles.
4. **`process/external-review-gate.md`** (new) — canonical spec for the opt-in cross-vendor review gate: runs after the internal loop converges, activated by an executable `[sdlc-root]/external-review.sh` wrapper (stdin=rubric+context+diff, stdout=`SEVERITY | file:line | finding`), findings re-enter triage, external model never fixes, hard data-egress rules (never send secrets; prefer local models; state egress to CD; confirm before first hosted run), 2-round cap, anti-conformity handling. Includes local (Ollama) and hosted (Codex) example wrappers.
5. **`process/review-fix-loop.md`** — added Step E (External Review Gate) between the clean internal loop and commit.
6. **`process/debate-protocol.md`** — added "Cross-Vendor External Reviewer" section framing the external model as the most-independent ensemble member (Design Principle 1), subordinate to internal review, weighted for higher false positives.
7. **`skills/sdlc-review-code/SKILL.md`, `skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`** — added the optional External Review Gate step after each internal review loop.
8. **`CLAUDE-SDLC.md`** — Direct Dispatch Rules: added the optional external review gate with the egress caveat.
9. **`skeleton/manifest.json`** — registered `process/external-review-gate.md`.

**Downstream:** Child projects receive MTS7, the new process doc, and the skill/doc wiring on next migration (`process/*.md` glob already covers the new doc in sdlc-migrate §2.1). The gate ships disabled — projects opt in by adding an executable `external-review.sh`; cc-sdlc ships no default wrapper because model choice and egress policy are project decisions. No contract-phrase changes.

**Rationale:** CD's planner/implementer-split goal is served two ways. Within Claude Code: keep domain agents, make the existing reviewer layer the higher tier (MTS7) so reviewer≥implementer holds without depending on dispatch-override that only workflows support. Across vendors: the External Review Gate adds a genuinely independent reviewer (different vendor/architecture = different blind spots), which debate-protocol identifies as the highest-value ensemble addition — while keeping it subordinate to cc-sdlc's own review loop and the Manager Rule (external model reviews; domain agents fix). Stage-generic roles were rejected because they strip knowledge routing, duplicate the skill's own stage orchestration, and shrink ensemble diversity.

## 2026-07-08: Manager Rule — replace trivial-fix exception with Delegation Economics Exception

**Origin:** CD directive, same session as the model-tier-strategy ingestion below. The initial ingestion deliberately rejected the community "do the work directly when delegation would cost more" boundary; CD reviewed that call and reversed it: "I don't mind the manager doing changes if they're trivial or small or more cost efficient, but they should always be reviewed. The goal is to keep main context small."

**What happened:** The Manager Rule's trivial-fix exception (mechanical + single-site + self-evident) was the only permitted self-implementation. CD adopted a broader economic boundary: the manager may self-apply when delegation costs more than the change itself — monetarily (dispatch overhead re-loading context the manager already holds) or in main-context growth — with review as the non-negotiable backstop.

**Changes made:**

1. **`process/manager-rule.md`** — "The Rule" reframed from "never edits code files" to "dispatches by default; direct implementation only under the Delegation Economics Exception; never self-approves." Trivial Fix Exception replaced by the Delegation Economics Exception (4 conditions: small and bounded; no design judgment; context-neutral — no paging in code to decide HOW; reviewed). Trivial fixes always qualify. Hard boundaries kept regardless of economics: specs/plans stay agent-written (except WORDING), architectural/product decisions stay with agents/CD, high-risk domains allow only trivial-class fixes with MTS4 risk-escalated review. "No Size Exception" section removed (superseded); new "Mandatory Review of Manager-Applied Changes" section (self-applied ≠ self-approved; batch small changes into one review dispatch). "No Complexity Exception" retained. Failed-dispatch rule softened: re-dispatch with revised prompt first; a remaining gap that itself passes the economics test may be closed directly with review. Scope/completeness bullets updated to the same test (merge reconciliation still always dispatches — it's judgment). Session Scope single-file rule now applies the economics test.
2. **`skills/sdlc-plan/SKILL.md`, `skills/sdlc-lite-plan/SKILL.md`, `skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`** — inlined Manager Rule summaries updated to the economics exception + revised failed-dispatch rule; execute skills' review-loop fix triage now uses the economics test (self-applied fixes re-enter the next review round); lite-execute red flag updated.
3. **`skills/sdlc-review-code/SKILL.md`** — Step 5a fix triage rewritten around the economics test (trivial fixes always qualify); self-check wording updated; Step 5b review loop unchanged and remains mandatory for self-applied fixes.
4. **`skills/sdlc-create-reference-doc/SKILL.md`** — fix-loop triage aligned to the economics test.
4a. **`skills/sdlc-tests-run/SKILL.md`** — Manager Rule section updated: economics-qualifying fixes may be self-applied, verified by re-running tests, and reviewed; diagnosis-requiring fixes still dispatch.
5. **`CLAUDE-SDLC.md`** — Direct Dispatch Rules: "Never self-implement" → "Dispatch-first, with an economics exception" (review mandatory); "Iterate on CD feedback" allows economics-qualifying self-fixes with review.
6. **`process/overview.md`** — direct-dispatch description updated.
7. **`BOOTSTRAP-LITE.md`** — Manager Rule summary updated (complexity exception still absent; economics exception added with mandatory review).
8. **`knowledge/architecture/model-tier-strategy.yaml`** — "Relationship to the Manager Rule" preamble rewritten (exception adopted; economics never buys skipped review or absorbed design judgment); MTS1 anti-pattern retargeted at skipping review rather than at self-implementation per se.
9. **`knowledge/provenance_log.md`** — prov-2026-07-08-001 note amended to record the same-session adoption (branch not yet merged; note corrected rather than appended to avoid misleading future readers).

**Rationale:** The original rule optimized for role purity; CD optimizes for context economy. A dispatch that forces an agent to re-load context the manager already holds costs more tokens than the change, and reading the agent's handoff can grow main context more than typing the fix would. The redesigned exception keeps the two failure modes the old rule guarded against — scope creep via "small" changes and unreviewed manager output — behind explicit conditions: acquiring new context to self-implement disqualifies (that cost is the point of the rule), design judgment disqualifies, and review is unconditional. Self-applied is never self-approved.

## 2026-07-08: Framework Ingestion — Model & Effort Tier Strategy

**Origin:** Bulk ingestion via `ccsdlc-ingest` from community sources: three r/ClaudeAI thread screenshots (per-subagent `effort:` frontmatter; Fable-coordinates/Opus-verifies/Sonnet-executes/Haiku-scouts workflow splits; SDD with a top-tier coordinator), a community "fable-chief-agent" skill, and the DataCamp spec-driven development tutorial. CD specifically asked to explore Fable/Opus as the research/planning tier with Sonnet agents implementing.

**What happened:** The framework already assigned models per-agent (sonnet default, opus for design decisions, haiku for retrieval) and already enforced judgment/labor separation via the Manager Rule, but had no codified doctrine for WHY tiers map to work types, no effort-as-a-lever guidance, no risk-escalated-review rule, and no session-level guidance that planning should run on the top tier. The community sources supplied exactly that doctrine.

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — created with 6 rules (MTS1–MTS6): concentrate judgment at the top tier / delegate evidence-checkable work down; the tier ladder (top-tier orchestrator → opus hard delegated reasoning + high-risk review → sonnet default worker → haiku recon); effort as an independent per-role lever; reviewer tier ≥ implementer tier for high-risk domains; stack-difficulty tier adjustment; plan-wide-on-premium / execute-narrow-on-cheap session tiering. Includes an explicit "Relationship to the Manager Rule" preamble rejecting the community delegation-economics escape hatch.
2. **`templates/agent-template.md`** — frontmatter reference: added optional `effort:` field (low|medium|high|xhigh|max, with harness-version caveat); model guidance now covers the high-risk-review role for opus and points to the tier strategy file.
3. **`skills/sdlc-develop-agent/SKILL.md`** — frontmatter generation step: expanded `model:` guidance and added `effort:` field guidance with tier-strategy pointer.
4. **`agents/sdlc-reviewer.md`** — agent frontmatter checklist: validates optional `effort:` values.
5. **`skills/sdlc-plan/SKILL.md`** / **`skills/sdlc-lite-plan/SKILL.md`** — Agent Dispatch Protocol: read the tier strategy; planning sessions run on the highest-tier model available (MTS1/MTS6), recon goes cheap, high-risk phases get escalated reviewer tiers (MTS4).
6. **`skills/sdlc-execute/SKILL.md`** — EXECUTE dispatch protocol: MTS4 (reviewer ≥ implementer tier on high-risk) and MTS5 (escalate a thrashing worker instead of a third re-dispatch).
7. **`knowledge/agent-context-map.yaml`** — wired the new file to the architect role.
8. **`knowledge/architecture/README.md`** — structure listing updated.
9. **`CLAUDE-SDLC.md`** — Agent Conventions: new bullet on pre-assigned model/effort tiers and running planning sessions on the top tier.
10. **`disciplines/architecture.md`** — inventory table row + 3 `[NEEDS VALIDATION]` parking lot entries (effort-frontmatter support matrix, Sonnet-on-Rust thrash reports, per-phase Model/Effort column in the planning template).
11. **`knowledge/provenance_log.md`** — first provenance entry (prov-2026-07-08-001) recording sources and ingestion.
12. **`skeleton/manifest.json`** — added the new knowledge file.

**Skill candidates proposed:** none — the material is doctrine (knowledge + template/skill wiring), not a workflow warranting a new skill. The pasted fable-chief-agent skill was NOT adopted as a skill: its judgment/labor split is now knowledge, and its "do the work directly when delegation costs more" boundary conflicts with the Manager Rule, which stays authoritative.

**Downstream:** Child projects receive the new knowledge file, template fields, and skill guidance on next migration. No renames or contract-phrase changes — all new references use canonical phrasings, so no `[contract-change]` tag and no `skeleton/contract_changes.yaml` entry needed.

**Rationale:** CD's proposed split — Fable/Opus researching and planning, Sonnet implementing — is exactly the architecture the SDLC already enforces structurally (Manager Rule separates judgment from labor; agent frontmatter carries worker tiers). What was missing was the explicit doctrine making that split *deliberate*: run planning where judgment concentrates on the strongest model, keep workers cheap, and escalate only the review tier — not the implementation tier — when risk demands it. The DataCamp SDD material validated the existing spec → plan → execute gate structure without requiring changes.

## 2026-07-07: Agent-description example economy (drop `<commentary>`, tier example count, mandatory Do-NOT-use)

**Origin:** Upstream handoff from ChronoCore (`upstream-agent-description-economy_handoff.md`). ChronoCore measured that Claude Code injects every agent's full `description` frontmatter into every session's system prompt regardless of whether the agent is ever spawned — a permanent per-session tax, unlike the agent body (loaded only on spawn). ChronoCore's 16 agents, authored to the prior convention (4 `<example>` blocks each, every example with `<commentary>`), totaled ~44.5k characters (~11k tokens) of description payload per session. ChronoCore applied a local trim (~18-20k chars, ~5-6k tokens saved) and handed the convention change upstream since the framework's template/skill/reviewer — not the projects — was the driver.

**What happened:** The prior convention (agent-template.md, sdlc-develop-agent, sdlc-reviewer) mandated 2-4 `<example>` blocks per agent description, each with a `<commentary>` annotation restating why the routing is correct. Review of the trimmed ChronoCore agents found `<commentary>` blocks invariably restate the scope sentence or Do-NOT-use boundary already present in the same description (pure redundancy), and examples 3-4 invariably restate example 1's pattern with a different noun. The routing value concentrates in one typical-use example plus, for agents with a confusable sibling, one "seam" example distinguishing the two.

**Changes made:**

1. **`templates/agent-template.md`** — Description example rewritten to 1 `<example>` block (no `<commentary>`) plus a mandatory `Do NOT use for: X — use Y instead` boundary sentence. Comment-block frontmatter reference rewritten: explains the per-session token-tax mechanic, the confusability-tiering rule (1 example / 2 examples, never 3-4), the `<commentary>` drop, and the boundary sentence's promotion to mandatory.
2. **`skills/sdlc-develop-agent/SKILL.md`** — CREATE mode Step 2 (Frontmatter Generation) adds an explicit example-count-tiering procedure (detect confusable sibling via the Step 1 domain-overlap scan → 1 or 2 examples, never 3-4, no `<commentary>`, mandatory boundary sentence). Red Flags table entry on example blocks updated to the tiered rule. New Red Flags entry warns ENRICH mode against re-inflating a description's example count or reintroducing `<commentary>` when a source suggests a "great new scenario" — ENRICH enriches the body, not the description.
3. **`agents/sdlc-reviewer.md`** and **`process/skill-agent-review.md`** — Reviewer checklist updated in both: 1-2 examples tiered by confusability (3+ is Major), `<commentary>` blocks inside descriptions are Major, missing Do-NOT-use boundary sentence is Major (graduated from recommended to required — it's now the primary overlap-resolution mechanism once examples are capped at 2). "Do NOT use" section discipline broadened to cover both the body scope statement AND the description boundary sentence. Example-quality check extended: a 2nd example that isn't a genuine seam (just another typical-use case) is also Major.
4. **`agents/sdlc-reviewer.md`** and **`agents/sdlc-compliance-auditor.md`** — Dogfooded the new convention on the two framework agents installed into every target project. Both had 3 examples with `<commentary>` (pre-trim). Trimmed to 2 examples each (typical-use + a reciprocal seam example distinguishing single-file convention review from project-wide compliance auditing) with `<commentary>` dropped and a Do-NOT-use sentence naming the other agent.
5. **`skills/sdlc-migrate/SKILL.md`** — §3.1 (Identify Template-Derived Sections): added a clarifying note that the frontmatter `description` field is project/author-owned and is NEVER auto-updated by template changes — settles the handoff's open question explicitly rather than leaving it implicit. §3.4 (Downstream Impact Analysis): added an "Agent descriptions" scan row, a scan-step bullet, a findings-block example, and a gate-rule line so migration offers (but never auto-applies) a description trim to existing downstream agents that violate the new convention.

**Rationale:** The convention was the cost driver, not the individual projects — every agent scaffolded via `sdlc-develop-agent` inherited the 4-example-plus-commentary shape by default. Fixing it at the template/skill/reviewer level means future generated and migrated agents are born lean, and `sdlc-migrate` won't regress a project's already-trimmed descriptions back to the fat framework default (the field was never template-derived to begin with — §3.1 now says so explicitly instead of leaving it to be discovered by re-reading the migration code). Dogfooding the trim on `sdlc-reviewer`/`sdlc-compliance-auditor` themselves avoids the framework shipping two examples of the exact violation its own reviewer now flags in downstream agents.

---

## 2026-07-04: Route sdlc-handoff deferred work on effort, not artifact size

**Origin:** Downstream-project feedback. A session filed mechanical metadata backfill (a known, repeatable transform over ~76 production records) as "Deferred work — non-trivial" and got routed to `sdlc-lite-plan` when direct dispatch was correct. Root cause: the word "non-trivial" in the Step 3 routing table invited a *size/volume* reading, while the rest of that table keys on *approach*.

**Changes made:**

1. **`skills/sdlc-handoff/SKILL.md`** (Step 3 table) — Re-keyed the two "Deferred work" rows and the isolated-Issue row on **effort** (coordination cycles) instead of size. Added a criterion sentence above the table pointing at `collaboration_model.md` § Estimation Model: a known repeatable transform over N items is Light effort regardless of item count or production-write surface → direct dispatch. Preserved blast-radius/reversibility as an explicit plan trigger ("costly or hard to reverse") so high-volume irreversible writes still route to a plan. Encoded the escalation default in the Light-effort deferred row (default to direct dispatch; receiver escalates only if a real unknown surfaces).
2. **`skills/sdlc-handoff/SKILL.md`** (Red Flags) — Added an entry capturing the exact miscalibration: "It touches many records / writes to production, so it's non-trivial → plan it" → volume and write-surface aren't effort.

**Rationale:** Aligns the skill with the framework's existing Estimation Model, which already defines Effort as coordination cycles ("not wall-clock time") and explicitly lists cross-domain handoffs and verification depth — exactly the levers that make high-blast-radius work plan-worthy. Reusing the Effort vocabulary fixes the size-proxy miscalibration without minting a competing "approach clarity" axis, and keeps the fix from over-rotating into "scale never warrants a plan."
