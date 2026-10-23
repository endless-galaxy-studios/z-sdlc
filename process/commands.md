# SDLC Commands Reference

Quick reference for all SDLC skills and commands. Slash commands (`/sdlc-*`) are auto-discoverable — type `/` in Claude Code to see available skills. Natural-language triggers require knowing the phrase.

## Core SDLC Workflow

The standard deliverable lifecycle: **ideation → plan → execute**. Most work flows through these skills.

| Command | Action |
|---------|--------|
| `/sdlc-idea` or "I have an idea" | Invokes `sdlc-idea` — open-ended exploration for seeds that aren't ready to plan yet; produces an idea brief |
| "Let's build X" / "Plan deliverable DNN" | Invokes `sdlc-plan` — full planning lifecycle (spec + plan with domain-agent review) for non-trivial work |
| "Execute the plan at ..." | Invokes `sdlc-execute` — executes an approved plan; worker agents implement, review, and fix |
| "Quick plan for X" / small tweak | Invokes `sdlc-lite-plan` — lightweight plan for same-session 1–3 file changes |
| "Execute the lite plan" | Invokes `sdlc-lite-execute` — executes a lite plan with the same review-fix loop |

## Lifecycle Commands

| Command | Action |
|---------|--------|
| "Initialize SDLC in this project" | Invokes `sdlc-initialize` — detects greenfield vs retrofit, walks through full framework setup |
| "Let's organize the chronicles" | Invokes `sdlc-archive` — archive completed deliverables from `current_work/` to `chronicle/`, reconciles untracked ad hoc work first |
| "Let's update the SDLC" | Propose process improvement. See `[sdlc-root]/process/sdlc_changelog.md` |
| "Migrate my SDLC framework" | Invokes `sdlc-migrate` — apply z-sdlc upstream updates while preserving project customizations |

## Status & Navigation

| Command | Action |
|---------|--------|
| `/sdlc-status` | Show active deliverables, blocked items, and recent archives |
| `/sdlc-manage-github` or "check the project board" | *(github-provenance bundle)* Invokes `sdlc-manage-github` — inspect/update GitHub Projects v2 boards and repo issues via `gh`; also home to the SDLC checkpoint recipes |
| `/sdlc-handoff` or "create a handoff" | Invokes `sdlc-handoff` — capture the current session as a self-contained handoff doc at `docs/current_work/ideas/{slug}_handoff.md` for another session to pick up via `sdlc-idea`, `sdlc-lite-plan`, `sdlc-plan`, or `sdlc-debug-incident` |
| `/sdlc-reflect` or "capture learnings" | Invokes `sdlc-reflect` — surface session learnings into discipline parking lots after direct-dispatch or ad-hoc work sessions |

## Auditing

| Command | Action |
|---------|--------|
| `/sdlc-audit` | Compliance audit — deliverable integrity, knowledge layer health, migration correctness |
| `/sdlc-audit improve` | Improvement audit — analyze current session or past session/commits for process gaps |
| `/sdlc-audit deep-verify [scope]` | Opt-in multi-judge re-verification of promoted knowledge content — expensive, pre-flight cost/egress confirmation required; scope: full (default), a domain, `stale`, or `incremental` |
| `/sdlc-audit health [scope]` | Codebase health audit — test/CI activation, agentic ergonomics, observability blind spots via parallel read-only sweeps; scope: whole repo (default), a path, or one sweep (`tests`, `ergonomics`, `observability`) |

## Incidents & Reference Docs

| Command | Action |
|---------|--------|
| `/sdlc-debug-incident` | Two-phase incident workflow — TRIAGE during active response, CLOSEOUT to postmortem after remediation. Auto-detects mode from incident doc state. |
| `/sdlc-create-reference-doc` | Create an internal developer-facing reference doc (event schemas, API surfaces, pipeline stage inventories). Author + review quorum + code-reviewer through review-fix loop. Writes to `docs/reference/{category}/`. |

## Knowledge & Content

| Command | Action |
|---------|--------|
| "Ingest these transcripts/articles" | Invokes `sdlc-ingest` — bulk-import external knowledge into disciplines and knowledge stores |
| "Make a playbook from this" | Invokes `sdlc-playbook-generate` — generate a structured playbook from the current session context or a past session's conversation and commits |
| `/sdlc-research` | Research external knowledge sources (blogs, talks, papers) and curate tiered reference docs |

## Skill & Agent Development

| Command | Action |
|---------|--------|
| `/sdlc-develop-skill` | Create or modify SDLC skills with convention enforcement, migration-aware wrapping, and quality gate |
| `/sdlc-develop-agent` | Create a new domain agent with frontmatter validation and knowledge wiring |
| `/sdlc-develop-agent enrich <agent> <sources>` | Extract patterns from external sources and integrate them into an existing agent definition |

## Code Review

| Command | Action |
|---------|--------|
| `/sdlc-review-code` | Review code with domain agents. No argument reviews uncommitted changes; a commit ref or range reviews that target. |
| `/sdlc-cleanup-comments` | Trim code comments down to the ones that say what the code can't: why, how it connects, outside constraints, public contracts. No argument covers the whole repo; paths or a commit range narrow it. Edits comments only, writes no new comments, and lists unclear comments, contradictions and unexplained code for your call. |

## Design (optional bundle)

Installed only when CD opts into the `design` bundle during `/sdlc-initialize`.

| Command | Action |
|---------|--------|
| `/sdlc-design-consult` | Consult domain design agents on UX, visual design, or interaction patterns |

## Software Factory (optional bundle)

Installed only when CD opts into the `factory` bundle (`[sdlc-root]/process/factory.md`). Its skills run headless inside the factory's GitHub Actions stages, started by labels and dispatches rather than commands; CD drives the factory from GitHub (`factory:triage` on an issue, reviews and replies on its PRs).

| Skill | Run by |
|-------|--------|
| `sdlc-triage` | `factory-triage.yml`: routes an issue to direct, plan, needs-input or wait. Can also run interactively on an issue number, read-only |
| `sdlc-implement` | `factory-implement.yml`: a direct-tier fix, unattended, to a draft PR |
| `sdlc-revise` | `factory-revise.yml`: a revision of a factory code PR from CD's review |

## Cross-Platform

| Command | Action |
|---------|--------|
| `/sdlc-port-opencode` | Adapt existing z-sdlc installation for OpenCode — creates `.opencode/agents/`, `AGENTS.md`, and `opencode.json` (incl. local model endpoint) alongside the Claude Code setup; skills and `[sdlc-root]` content are shared, not copied (OpenCode reads `.claude/skills/` directly) |

## Rendering

| Command | Action |
|---------|--------|
| `/sdlc-walkthru` or "walk me through the spec/plan" | Guided part-by-part interactive walkthrough of an SDLC artifact — CD paces with "next", questions answered against real code, feedback classified and dispatched mid-flight. The explainer's peer at every offer point. |
| `/sdlc-explain <subject>` or `/eli5 <subject>` | Big-pictures-few-words HTML explainer of a deliverable, module, tradeoff, decision, or incident for someone who knows nothing about it — inline SVG, hard word budget, every claim verified and cited. Lossy by design. Offered (opt-in) after skills write deliverables, as the walkthrough's peer; on demand for questions. |

## Testing

| Command | Action |
|---------|--------|
| `/sdlc-tests-create` | Generate test suites — domain experts identify gaps, SDET implements |
| `/sdlc-tests-run` | Automated test-fix loop — run tests, classify failures, dispatch agents to fix, repeat until green |
| `/sdlc-develop-verify-skill` | Create the project's verify skill (`.claude/skills/verify/`): how to launch, health-check, drive and clean up the running app, with a feature map, proven end to end before handover. `maintain` re-checks every mapped feature against the source and drives each one live; it never edits product code and reports app bugs instead. |
