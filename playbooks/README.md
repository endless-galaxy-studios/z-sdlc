# Playbooks

Playbooks capture recurring task patterns so that planning doesn't start from scratch every time. They pre-seed agent selection, knowledge context, typical phases, and reference implementations for common categories of work.

## When to consult

Playbooks are a **reference, not a mandatory gate**. The planning agent decides whether a playbook is relevant — the same way templates work today. Consult a playbook when the task clearly matches a known pattern. Skip it when the task is novel or doesn't fit.

Planning skills (`sdlc-plan`, `sdlc-lite-plan`) read this README after their own agent selection, check each playbook in the Available playbooks table for task-type overlap, and report every candidate with its match or no-match reason.

## Format

Each playbook includes:

- **Last validated** — date the playbook was last confirmed accurate against the codebase
- **Validation triggers** — conditions that should prompt re-validation (e.g., "domain adapter interface changes")
- **When to use** — 1-2 sentence trigger description
- **Recommended agents** — who leads, who contributes
- **Knowledge context** — which `[sdlc-root]/knowledge/` files to include when dispatching
- **Typical phases** — the usual phase structure for this task type
- **Reference implementation** — existing code to study
- **Key decisions to surface** — decision points that always come up

## Freshness

Playbooks go stale. Each playbook declares its `validation_triggers` — when any of those conditions occur, the playbook should be re-validated. The `sdlc-audit` skill checks playbook freshness as part of knowledge layer health audits.

## Available playbooks

| Playbook | Task type |
|----------|-----------|
| [example-playbook.md](example-playbook.md) | Generic example — copy and customize |

Add your own playbooks as recurring task patterns emerge in your project.
