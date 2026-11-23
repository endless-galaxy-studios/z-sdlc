---
type: handoff
slug: external-review-wrapper-hardening
created: 2026-11-23
status: pending
trigger: issue
recommended_next_skill: direct-dispatch
source_session_summary: "Sleeved's external-review-gate runbook after its v2.9.11 migration: infosec-engineer's review of the two wrapper templates"
active_deliverable: null
related_files:
  - templates/external-review.sh.template
  - templates/external-review-knowledge.sh.template
  - process/external-review-gate.md
---

# Handoff: Harden the external-review wrapper templates and the gate doc

## Why this is a handoff
On 2026-11-23 Sleeved ran the `external-review-gate` runbook after migrating to v2.9.11. It installed both wrapper templates unchanged. infosec-engineer reviewed them, approved the egress (OpenAI through the Codex CLI, model looked up per call), and found four defects in the templates and the gate doc themselves.

They're z-sdlc's files: a project's next migration overwrites its copies. So CD chose (Sleeved's runbook record, decision D4) to fix them here instead of patching Sleeved's wrappers. Sleeved's wrappers carry item 1's exposure until a release fixes it.

## What needs to happen
1. **major: `codex exec` loads the user's whole Codex config.** That includes its MCP servers and plugins (`~/.codex/config.toml`), and Codex's sandbox doesn't cover MCP calls. Planted text in a reviewed diff could reach a tool with credentials. On the reporting machine that's the `railway` and `node_repl` servers.

   Fix: add `--ignore-user-config` to the `codex exec` call in both templates (`external-review.sh.template:48`, `external-review-knowledge.sh.template:47`). Codex 0.166.0's help says: "Do not load `$CODEX_HOME/config.toml`; auth still uses `CODEX_HOME`".

   A dry run with it passed: exit 0, `provider: openai`, `model: gpt-6.2-astra`, one finding in the requested format. Then check what it changes in § Task-Based Model Selection: with no `CODEX_MODEL`, Codex's built-in default applies, not the user's configured one.
2. **minor: the prompt gives planted text more weight.** `external-review.sh.template:56` tells the model to follow the payload's rubric header "exactly", and the rubric arrives on stdin next to the artifact under review. Tell the model that everything after the rubric is data under review.
3. **minor: nobody owns secret scrubbing.** `process/external-review-gate.md:212` (§ Wrapper contract) says the wrapper owns it, `:91` (§ Data egress) says the caller scrubs, and the template scrubs nothing. The example payload at `:280` runs `git diff` over every path, so a changed tracked `.env` file would be sent. Settle who scrubs, and make the example exclude `.env*` and other secret-bearing paths.
4. **minor: the temp file can outlive a killed wrapper.** `trap 'rm -f "$out"' EXIT` (`external-review.sh.template:42`, `external-review-knowledge.sh.template:41`) doesn't run when the wrapper itself is killed. That leaves a 0600 temp file holding the model's answer, never the payload. Use `trap … EXIT INT TERM`.

## Evidence
- **Line numbers** are in v2.9.11 (`f1bd7e0`), and are the same in Sleeved's byte-identical copies.
- **infosec-engineer's main finding**, verbatim: "`codex exec` loads the whole user config. That includes the `railway` and `node_repl` MCP servers and several enabled plugins, and Codex's sandbox does not cover MCP calls. Text in a diff that tells the reviewer to act could reach Railway credentials, or reach the network through node_repl. I did not test whether `exec` runs MCP calls without asking."
- **Option injection was checked:** `${model:+-m "$model"}` expands to exactly two arguments under bash, and `--config model_reasoning_effort="$effort"` is a single argument. That part is fine.
- **Sleeved's record:** `docs/runbooks/external-review-gate.md` § Deferred items 1-4, and Decisions D2-D4 (endless-galaxy-studios/sleeved).

## Recommended next step
Direct dispatch in a z-sdlc session. The four fixes are small and clear, and they sit in two templates and one process doc. Item 3 may become a contract change, if the caller's scrubbing duty is written into each skill that builds a payload.

## Open questions
- Does `codex exec` call MCP tools without approval in non-interactive mode? Nobody has tested it. That decides how urgent item 1 is, not whether to fix it.
- Should the templates also pass `--ignore-rules`?
- Item 3: a contract change for callers, or a wrapper feature?

## Out of scope (do NOT pursue)
- Sleeved's own wrappers. They follow the template at its next migration.
- Where a project sends payloads: that is each project's runbook decision.
