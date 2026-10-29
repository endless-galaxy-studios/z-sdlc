# z-sdlc

**An architect-driven software development lifecycle for agentic development (primarily with Claude Code), taking work from ideation to completion.**

## Key Features
- Domain-expert agents that build and review
- A knowledge layer that learns from your & agent's work
- A process you can bend to fit as you need

With z-sdlc, you are the architect, or **CD (Claude Director)**. You set direction, review & approve specs & plans, and make the product & design calls. Agents, collectively **CC (Claude Code)**, implement, review each other, and report back.

This is a toolbox, not a recipe. Nothing in it is mandatory overhead, and the framework is built to be reshaped by the people using it.

- [Why this exists](#why-this-exists)
- [How it works](#how-it-works)
- [The thinking behind it](#the-thinking-behind-it)
- [How it compares](#how-it-compares)
- [Why you might like it](#why-you-might-like-it)
- [Bundles](#bundles)
- [Quick start](#quick-start)
- [Core concepts](#core-concepts)
- [What's in the repo](#whats-in-the-repo)

---

## Why this exists

z-sdlc was forged from the fires of early LLM-assisted programming. It started with no framework at all, and then at some point I started pasting the same prompt everywhere: `make this change/do this work, then review the changes with the relevant domain subagents, fix the findings, and continue until no more issues are found.` It was naive, but it was mine, and it worked. It was the early days of a skill, and it grew into a habit of using subagents for two main reasons.

### 1. Subagents keep the main context light.
Subagents do all the reading, searching and grinding in their own windows, so none of it clogs the main context. They hand back a final report, which keeps the main session small so large pieces of work don't force you to compact.

### 2. Domain scoping helps, as long as the agent is given knowledge.
A common claim is that domain-scoped subagents add little, since the model already knows everything. Half of that is right: a bare persona ("you are the database specialist") adds very little, because the label carries no information the model didn't already have. What helps is what you put in the window next to it.

An agent briefed as the database specialist, with the project's actual data-modeling rules, known gotchas and conventions injected into its context, is working from information the model could never have guessed, and every token it produces is conditioned on it. Scoping is how that knowledge gets to the right agent: a reviewer with a narrow brief and a specific rule set catches what a generalist skims past, several of them reviewing independently act as an ensemble, and each one reads only what it needs, which keeps the main context light.

### How do we stop repeating ourselves?
Humans learn by doing: we try something, it works or it doesn't and we carry the lesson into the next attempt. A model does the same thing inside a session. You correct it, it adjusts, and for the rest of that conversation it does better. But we aren't retraining models or training LoRAs, so when the session ends, the lesson ends with it.

z-sdlc's answer is a portable brain: a layer of plain files (patterns, gotchas, review rules, decisions) that agents read before they work and that the process feeds as work happens. People and models share it, it can be diffed and reviewed like code, and it goes with the project instead of living in a model or a vendor.

The same design made the SDLC easy to extend. Need a new stage, a new reviewer, a new rule? It's a file. That turned out to matter more than anything else. I never meant it to be the base for a software factory, but it is: the [factory bundle](#bundles) runs on the same skills, agents, review rules and knowledge layer, and it is what keeps the unattended pieces consistent with each other.

## How it works

**Work moves through a lifecycle, scaled to the work.**

```
Idea (optional) → Spec (you approve) → Plan (agents review) → Execute → Review → Result → Chronicle
```

The project has three tiers, with an optional ideation step before them:

- **Ideation** (`sdlc-idea`) is always optional. It's a precursor for truly undefined work: things are murky, you don't know what you want yet or how you want it, and you want to explore the possibilities before deciding between lite and full, or whether to write a spec at all.
1. **Direct dispatch:** no documents are generated (unless you ask for one retroactively). Best for real-time steering while still using everything the SDLC offers.
2. **SDLC-Lite (`sdlc-lite-plan`):** subagents review a plan, and that's it. Best for short pieces of work that benefit from varying perspectives, or from making sure the SDLC's stored gotchas don't let anything unintended through.
3. **Full SDLC (`sdlc-plan`):** a spec and a plan are generated, and subagents review both documents over a series of review rounds. Best for new features, architectural changes, and anything that should be clearly designed and thought through before code is written.

Every tracked piece of work gets a sequential deliverable ID (D1, D2, ...) and an entry in a catalog.

**A manager dispatches domain agents.** The session you talk to is the manager, and it delegates by default. Agents do the implementation, other agents review it, and the manager doesn't approve its own work ([`process/manager-rule.md`](process/manager-rule.md)). The rule is economic, not ceremonial: the manager's context is the scarcest resource, and delegation protects it.

**Agents get knowledge, not just a role.** A map ([`knowledge/agent-context-map.yaml`](knowledge/agent-context-map.yaml)) names the structured YAML knowledge files each agent role should read before it works: architecture patterns, testing gotchas, data-modeling anti-patterns, design methodology, and so on. The skills do the injection at dispatch time.

**Review is a loop with named lenses.** Work is reviewed by domain agents through a set of lenses (overengineering, type safety, security at boundaries, data integrity, accessibility, and more; see [`process/review-lenses.md`](process/review-lenses.md)). Findings are classified and fixed in a loop that has an exit bar. Conflicts between reviewers go through a defined debate protocol, and an optional external gate can send a diff to a non-Claude model for an independent second opinion.

**The knowledge layer learns.** This is the part that makes it more than a set of prompts:

```
Work → Discipline parking lots (insights, triaged) → Knowledge YAMLs and skills (validated patterns) → Agents read them next time
```

Planning and execution skills prompt for discipline capture at natural checkpoints, and `sdlc-reflect` does it after any session. Entries are triaged (`[READY TO PROMOTE]`, `[NEEDS VALIDATION]`, `[DEFERRED]`) and promoted when validated. Recurring review findings can graduate into mechanized guards such as lint rules and CI checks ([`process/guardrail-lifecycle.md`](process/guardrail-lifecycle.md)), which are re-evaluated later and retired when they stop earning their place. The framework audits itself too (`/sdlc-audit`), in a compliance mode and in an improvement mode that reads sessions and commits for gaps.

**It stays alive across projects.** `sdlc-migrate` updates an installed project to a newer framework version by reading its content, keeping what the project owns (its knowledge, its configuration, its customizations) and refreshing what the framework owns.

## The thinking behind it

- **Toolbox, not recipe.** The first move is always to tailor the process to the work. Vibe coding is valid, and a quick prototype doesn't need a spec. Process is added when its absence caused a problem, not because a document says to. Heavy process is a bug. ([`disciplines/README.md`](disciplines/README.md))
- **Memory belongs to the project.** What the team learns should live in files that humans can read, diff and correct, not in an opaque model state. If a pattern is wrong, you fix a YAML file.
- **Context is the scarce resource.** Delegate to subagents, inject only the knowledge a role needs, and write documents that survive a context clear.
- **Independent review beats agreement.** Multi-agent research suggests most of the gain from "debate" comes from ensembling independent reviewers. Reviewers work independently, and debate exists only to resolve real conflicts, with a tiebreaker.
- **Humans decide; agents do.** CD is the human who sets direction and approves specs, plans and merges. Anything that needs CD stops the run instead of being guessed past, which is what makes headless operation safe ([`process/headless-mode.md`](process/headless-mode.md)).
- **Write for the reader.** Output addressed to CD is short and scannable, because an approval nobody could follow isn't a real approval ([`process/writing-for-cd.md`](process/writing-for-cd.md)).
- **Estimate in dimensions, not hours.** AI-assisted work makes calendar estimates misleading, so deliverables are rated on validity, correctness and effort instead.
- **Make it extensible and let it evolve.** Skills, agents, knowledge and process docs are all plain files with conventions and a skill for creating each one. A directive like "from now on do X" is meant to change the framework, not one session.

## How it compares

There are other good ways to structure AI-assisted development, made by people who thought hard about the same problems. z-sdlc is one opinionated take, not a claim that the others are wrong or missing things. These summaries come from each project's public README and docs as of October 2026. All of them are moving fast, so read their docs for the current picture.

| | What it is | How z-sdlc differs |
|---|---|---|
| **BMAD Method** | A skills-based delivery loop (Clarify, Plan, Build and verify, Learn and adjust) with a ready-made set of roles and optional modules for things like test architecture and game dev. | z-sdlc ships no fixed cast. You define agents from your own stack, because your project's rules matter more than a generic role, and its learning loop keeps those agents current. |
| **GSD ("Get Shit Done")** | A spec-driven, context-engineering system, now continued as [GSD Core](https://github.com/open-gsd/gsd-core): one Discuss, Plan, Execute, Verify, Ship loop per phase, run in fresh-context subagents. | z-sdlc has no single mandatory loop. Its tiers scale from a one-line steer to a full spec, since most work isn't a milestone, and its edge is what carries over between sessions: lessons become knowledge. |
| **GitHub Spec Kit** | An extensible toolkit for spec-driven development that works across many coding agents, with a catalog of extensions and presets. | z-sdlc trades breadth for depth: it is Claude Code-first (with an OpenCode port) so it can use subagents and skills fully, and it extends through plain files you edit, not a catalog. |
| **Superpowers** | A library of composable skills for Claude Code and many other tools, including habits like brainstorming first and test-driven development. | z-sdlc doesn't prescribe how you write code. It governs how work is tracked, reviewed and learned from, and leaves the coding method to you. |
| **Plain Claude Code** | Your own `CLAUDE.md`, skills and subagents.                                                                                                                                                                                                                                                                                                     | This is where z-sdlc started. If your own setup already works, you may not need it, and much of z-sdlc is worth borrowing piecemeal. |

Where z-sdlc puts its emphasis overall:

- **A learning loop you can read.** What a session teaches lands in plain files, gets triaged, and is promoted into knowledge, skills and guardrails that agents read next time.
- **Domain agents with injected knowledge**, built around your project's rules and domains.
- **Proportional ceremony.** A typo fix and a new subsystem shouldn't cost the same.
- **It audits and migrates itself.** Installs carry a manifest, and updates are content-aware.

Take what's useful. I didn't care for the whole of several of these, but I liked specific ideas in each, and z-sdlc is the result of keeping the parts that worked for me. If you know what you want from a workflow, building your own is a good idea, and the point of z-sdlc being a set of plain, documented files is that you can fork, delete and rewrite it. Skills like `sdlc-ingest` and `zsdlc-research` exist so you can pull other people's ideas into it.

## Why you might like it

- You work in Claude Code every day and keep re-explaining the same conventions to it, or find that it isn't adhering to your `CLAUDE.md` or the other conventions you've laid out.
- You have rules about how your project should be coded and managed, and you want reviews done with those rules in mind.
- Your sessions run long and context pressure is a daily cost.
- You want the lessons from one deliverable to improve the next, and a team-readable record of what was built and why.
- You want process that is optional at every level, and that you can inspect and change.
- You're building toward unattended agent work and want guardrails, approval gates and an audit trail underneath it.

You may not want it if you prefer to keep a project almost entirely ad hoc, if you need a different primary tool (OpenCode compatibility exists via `sdlc-port-opencode`, but Claude Code is the home), or if a lighter spec workflow already covers your needs.

## Bundles

Beyond the core, z-sdlc ships **opt-in bundles**: self-contained capabilities that are installed only if you accept them, and are inert until configured.

| Bundle | What it adds |
|---|---|
| **design** | `sdlc-design-consult`: turns references and codebase context into distinct design options backed by design theory. |
| **github-provenance** | Narrates every tracked deliverable into a GitHub issue through lifecycle checkpoints, with optional Projects v2 board tracking and audit reconciliation. |
| **factory** | An issue-driven software factory: agent stages (triage, implement, plan and spec, revise, execute with production gates, a weekly improve loop) on self-hosted runners, with CD approving every plan, every merge and every production step. |

See [`bundles/README.md`](bundles/README.md) for what each one does, how bundles are installed and kept up to date, and how they share a project.

## Quick start

### 1. Initialize a project

```bash
# One command: downloads the bootstrap file
curl -fsSL https://raw.githubusercontent.com/endless-galaxy-studios/z-sdlc/master/BOOTSTRAP.md -o .claude/BOOTSTRAP.md
```

Open your project in Claude Code and say:

> "Bootstrap SDLC"

Claude Code reads the bootstrap file, clones the framework, installs everything, and walks you through setup. The `sdlc-initialize` skill detects whether the project is greenfield or a retrofit, then handles file installation, `CLAUDE.md` authoring, agent creation, knowledge wiring, optional bundles and verification.

### 2. Use the process

| Trigger | What happens |
|---|---|
| "Let's build X" / "New feature" | `sdlc-plan`: spec and plan |
| "Execute the plan" | `sdlc-execute`: implement, review, result |
| "Let's organize the chronicles" | `sdlc-archive`: moves completed work to the archive |
| `/sdlc-audit` | Compliance audit: deliverable integrity, knowledge health, migration correctness |
| `/sdlc-audit improve <session>` | Improvement audit: analyze sessions and commits for process improvements |
| `/sdlc-reflect` | Capture what a session taught into the discipline parking lots |
| "Make a playbook from that session" | `sdlc-playbook-generate`: session-to-playbook extraction |

### 3. Keep it current

Ask Claude Code to migrate. `sdlc-migrate` brings an installed project up to the latest version without clobbering what the project owns.

## Core concepts

- **Deliverable IDs:** Sequential identifiers (D1, D2, ...) that track work for the life of the project. Never reused, even if work is abandoned.
- **Current work vs chronicles:** `docs/current_work/` holds active deliverables; `docs/chronicle/` holds completed work organized by concept.
- **Roles:** **CD (Claude Director)** is the human. **CC (Claude Code)** is the whole agent system.
- **Disciplines:** Persistent per-domain parking lots where insights land before they're promoted to knowledge or skills.
- **Playbooks:** Recipes for recurring task types, extracted from real sessions.

## What's in the repo

| Directory | Contents |
|---|---|
| `skills/` | Claude Code skills for planning, execution, review, audit, migration and more |
| `agents/` | `AGENT_SUGGESTIONS.md` (a catalog of proven domain roles) and the framework's own subagents |
| `knowledge/` | Structured YAML knowledge stores and the agent-to-knowledge map |
| `disciplines/` | Discipline parking lots for capturing insights |
| `process/` | The workflow rules: lifecycle, manager rule, review lenses, headless mode, guardrails, and more |
| `templates/` | Document templates for specs, plans, results and PR descriptions |
| `examples/` | Filled-out examples of spec, plan and result documents |
| `playbooks/` | Recipes for recurring task types |
| `plugins/` | Plugin setup guides (context7 required; LSP and Playwright recommended) |
| `bundles/` | Opt-in bundle sources ([overview](bundles/README.md)) |
| `skeleton/` | The manifest of what gets installed, and the structured record of changes that need active migration |

**Plugins.** `context7` is required: it gives agents live library documentation instead of stale training data (`plugins/context7-setup.md`). A language-server plugin for your main language is highly recommended.

**Adapters.** z-sdlc is the stable core; adapter plugins live in separate repos and swap its file-based knowledge routing for another backend (for example a memory graph) at install time, through a fixed phrasing contract ([`process/knowledge-routing.md`](process/knowledge-routing.md)).

## Upstream

Maintained at [github.com/endless-galaxy-studios/z-sdlc](https://github.com/endless-galaxy-studios/z-sdlc). Release notes are generated from [`process/sdlc_changelog.md`](process/sdlc_changelog.md).

The knowledge YAMLs and discipline files were seeded from a cross-project reference implementation. They are intentionally generic: project-specific content belongs in your project's `docs/` and `CLAUDE.md`.
