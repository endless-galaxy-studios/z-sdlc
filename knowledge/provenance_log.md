# Knowledge Provenance Log

Append-only record of where knowledge entered the SDLC knowledge layer. Enables staleness tracing, audit lineage, and prepared handoffs between research and ingestion.

**Conventions:**
- Entries in reverse-chronological order (newest first)
- IDs are sequential per date: `prov-YYYY-MM-DD-NNN`
- Conditional fields (`files-created`, `files-updated`, `rule-count`, `ingested-by`) only required when `status: ingested`
- Optional fields (`tier-1-count`, `tier-2-count`) used by `sdlc-research` for research entries
- Status transitions: `pending-review` -> `approved-for-ingest` -> `ingested` (or `rejected` at any point)
- `source-type: audit-sweep` marks a Deep Verify re-verification run (sdlc-audit §6m), not a content ingestion — one entry per sweep, recording scope, judge configuration, and kept/demoted counts; the newest such entry is the boundary for the next incremental sweep

## Entry Format

```markdown
## [YYYY-MM-DD] {source name} — {discipline}

- **id:** prov-YYYY-MM-DD-NNN
- **status:** pending-review | approved-for-ingest | ingested | rejected
- **source-type:** reference-doc | file | directory | url | manual | audit-sweep
- **source:** {path or description}
- **source-url:** {URL if applicable}
- **discipline:** {target discipline}
- **files-created:** {paths, when status=ingested}
- **files-updated:** {paths, when status=ingested}
- **rule-count:** {N, when status=ingested}
- **ingested-by:** {skill name, when status=ingested}
- **notes:** {freeform}

---
```

## Log

## [2026-10-23] pstack comment rules (cursor/plugins) — coding

- **id:** prov-2026-10-23-001
- **status:** ingested
- **source-type:** url
- **source:** pstack plugin, cursor/plugins at commit 8b3326d (2026-10-22), MIT license: `pstack/skills/no-comments/SKILL.md`, `pstack/agents/comment-sicko.md`, and the Comments section of `pstack/skills/poteto-mode/SKILL.md`
- **source-url:** https://github.com/cursor/plugins/tree/main/pstack
- **discipline:** coding
- **files-created:** knowledge/coding/comment-discipline.yaml, skills/sdlc-cleanup-comments/SKILL.md, skills/sdlc-cleanup-comments/references/dispatch-prompts.md, skills/sdlc-cleanup-comments/references/machine-read-comments.md, skills/sdlc-cleanup-comments/references/report-template.md
- **files-updated:** knowledge/agent-context-map.yaml, knowledge/coding/README.md, CLAUDE-SDLC.md, process/review-lenses.md, process/commands.md, process/headless-mode.md, skeleton/manifest.json
- **rule-count:** 1
- **ingested-by:** zsdlc-create-skill
- **notes:** Rewritten in z-sdlc's own words, not copied. Taken from pstack: the keep list (outside constraints, public contracts, issue links, legal headers), checking "do not remove" comments against the code and its history before trusting them, treating a comment that explains our own surprise as a reshape candidate, offering an enforcement for comments that state a constraint, and test steps named by their assertion messages. Changed by CD's decision: unclear comments are kept and listed instead of cut, gaps are listed and never filled, and our-code surprise comments stay until the code is reshaped. Left out: the comment-sicko persona, and automatic code reshaping and lint-suppression removal (both report-only here).

---

## [2026-07-08] Community tiered-orchestration sources — architecture

- **id:** prov-2026-07-08-001
- **status:** ingested
- **source-type:** manual
- **source:** Three r/ClaudeAI thread screenshots (per-subagent effort frontmatter; Fable/Opus/Sonnet/Haiku workflow splits; SDD with top-tier coordinator), community "fable-chief-agent" skill text, DataCamp spec-driven development tutorial
- **source-url:** https://www.datacamp.com/tutorial/spec-driven-development-with-claude-code
- **discipline:** architecture
- **files-created:** knowledge/architecture/model-tier-strategy.yaml
- **files-updated:** templates/agent-template.md, skills/sdlc-develop-agent/SKILL.md, agents/sdlc-reviewer.md, skills/sdlc-plan/SKILL.md, skills/sdlc-lite-plan/SKILL.md, skills/sdlc-execute/SKILL.md, knowledge/agent-context-map.yaml, knowledge/architecture/README.md, CLAUDE-SDLC.md, disciplines/architecture.md
- **rule-count:** 6
- **ingested-by:** zsdlc-ingest
- **notes:** DataCamp SDD workflow (spec → plan → implement with human gates) validated as already fully implemented by z-sdlc — no structural change needed. The fable-chief-agent skill's delegation-economics boundary ("do work directly when delegation costs more") was initially deferred, then adopted by CD decision in the same session as the Manager Rule's Delegation Economics Exception (mandatory review retained; see changelog 2026-07-08 entries). Three unvalidated observations parked in disciplines/architecture.md.

---
