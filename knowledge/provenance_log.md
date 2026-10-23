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

## [2026-10-23] pstack fix order and plain-writing cues (cursor/plugins) — process-improvement

- **id:** prov-2026-10-23-006
- **status:** ingested
- **source-type:** url
- **source:** pstack plugin, cursor/plugins at commit 8b3326d (2026-10-22), MIT license: `pstack/skills/correct/SKILL.md`, `pstack/skills/principle-encode-lessons-in-structure/SKILL.md`, `pstack/skills/unslop/SKILL.md`
- **source-url:** https://github.com/cursor/plugins/tree/main/pstack
- **discipline:** process-improvement
- **files-created:** none
- **files-updated:** process/guardrail-lifecycle.md, process/writing-for-cd.md, CLAUDE-SDLC.md, templates/pr_description_template.md, process/review-fix-loop.md, skills/sdlc-review-code/SKILL.md, skills/sdlc-reflect/SKILL.md, skills/sdlc-audit/references/compliance-methodology.md
- **rule-count:** 2
- **ingested-by:** manual (Claude session, after a Codex consult)
- **notes:** Rewritten in z-sdlc's own words, not copied. Taken from pstack: fixing a mistake class at the highest level that works (structure, types, a lint naming the fix, a test, written rules last), failing only on new instances of a common pattern, proving a check against a real past mistake, and a selection of its machine-written phrasing patterns. Left out: unslop's punctuation and formatting rules (em dashes, colons, sentence-case headings), which conflict with z-sdlc's conventions, and correct's rule table in the agent instruction file (z-sdlc records guards in `recurring-patterns.yaml`).

---

## [2026-10-23] pstack history-first explanations and check-before-asking (cursor/plugins) — architecture

- **id:** prov-2026-10-23-005
- **status:** ingested
- **source-type:** url
- **source:** pstack plugin, cursor/plugins at commit 8b3326d (2026-10-22), MIT license: `pstack/skills/why/SKILL.md`, `pstack/skills/why/references/epistemics.md`, `pstack/skills/why/references/sources/code-archaeology.md`, and the facts-versus-decisions line in `pstack/skills/poteto-mode/SKILL.md`
- **source-url:** https://github.com/cursor/plugins/tree/main/pstack
- **discipline:** architecture
- **files-created:** none
- **files-updated:** knowledge/architecture/investigation-report-format.yaml, knowledge/agent-context-map.yaml, knowledge/coding/comment-discipline.yaml, disciplines/architecture.md, skills/sdlc-explain/SKILL.md, CLAUDE-SDLC.md, process/collaboration_model.md
- **rule-count:** 2
- **ingested-by:** manual (Claude session, after a Codex consult)
- **notes:** Rewritten in z-sdlc's own words, not copied. Taken from pstack: starting from the code's own history, the five confidence groups and their wording, sources consulted including the empty ones, a suggested answer treated as a hypothesis, the keep/change/avoid/risk ending before a change, and checking whether an experiment answers an observable fact before asking. Left out: the parallel investigators over chat, ticket, document, observability, error-tracking and analytics tools, its model routing, and the broader rule to proceed on reversible work without asking (CD decides product and scope questions).

---

## [2026-10-23] pstack review-evidence rules (cursor/plugins) — architecture

- **id:** prov-2026-10-23-004
- **status:** ingested
- **source-type:** url
- **source:** pstack plugin, cursor/plugins at commit 8b3326d (2026-10-22), MIT license: `pstack/skills/blast-radius/SKILL.md`, `pstack/skills/principle-prove-it-works/SKILL.md`, `pstack/skills/benchmark-checklist/SKILL.md`, `pstack/skills/principle-explain-the-number/SKILL.md`, `pstack/agents/comment-sicko.md` (its suppression rule)
- **source-url:** https://github.com/cursor/plugins/tree/main/pstack
- **discipline:** architecture
- **files-created:** none
- **files-updated:** process/review-lenses.md, knowledge/architecture/performance-optimization-philosophy.yaml
- **rule-count:** 4
- **ingested-by:** manual (Claude session, after a Codex consult)
- **notes:** Rewritten in z-sdlc's own words, not copied. Taken from pstack: the one fact a change is safe because of and the ladder of how far it is proven, consumers a symbol search misses, looking up the rule a suppression silences, and the benchmark questions with their report format and ballpark exception. Left out: pstack's multi-model "arena" for wide changes (z-sdlc has its own external review gate), its decision-log format, and its rule to delete a suppression and mark the code (z-sdlc reports it as a review finding; code changes go through the fix gate).

---

## [2026-10-23] pstack bug-fix and test-quality rules (cursor/plugins) — testing

- **id:** prov-2026-10-23-003
- **status:** ingested
- **source-type:** url
- **source:** pstack plugin, cursor/plugins at commit 8b3326d (2026-10-22), MIT license: `pstack/skills/poteto-mode/playbooks/bug-fix.md`, `pstack/skills/tdd/SKILL.md`, `pstack/skills/principle-fix-root-causes/SKILL.md`, `pstack/skills/principle-attack-the-premise/SKILL.md`, `pstack/skills/principle-test-behavior-not-implementation/SKILL.md`
- **source-url:** https://github.com/cursor/plugins/tree/main/pstack
- **discipline:** testing
- **files-created:** none
- **files-updated:** CLAUDE-SDLC.md, skills/sdlc-lite-plan/SKILL.md, skills/sdlc-review-code/SKILL.md, skills/sdlc-tests-run/SKILL.md, process/review-lenses.md, knowledge/architecture/debugging-methodology.yaml, knowledge/testing/testing-paradigm.yaml
- **rule-count:** 8
- **ingested-by:** manual (Claude session, after a Codex consult)
- **notes:** Rewritten in z-sdlc's own words, not copied. Taken from pstack: watching the failing test fail for the bug's reason, the closest runnable check when a test is impractical, "prefer no new test to a bad one", the legitimacy test for guards, saved state after a restart, fixing the whole pattern, writing down and testing the shared assumption after two failed fixes, and the two-edit check for tests. Left out: pstack's separate commit for the failing test (z-sdlc commits the test with the fix), its model routing and Cursor commands, and binary-search and instrumentation guidance z-sdlc's debugging methodology already has.

---

## [2026-10-23] pstack verification skills (cursor/plugins) — testing

- **id:** prov-2026-10-23-002
- **status:** ingested
- **source-type:** url
- **source:** pstack plugin, cursor/plugins at commit 8b3326d (2026-10-22), MIT license: `pstack/skills/create-verification-skill/SKILL.md` (and its `references/feature-map-example/`), `pstack/skills/maintain-verification-skill/SKILL.md`
- **source-url:** https://github.com/cursor/plugins/tree/main/pstack
- **discipline:** testing
- **files-created:** skills/sdlc-develop-verify-skill/SKILL.md, skills/sdlc-develop-verify-skill/references/safety-rules.md, skills/sdlc-develop-verify-skill/references/generated-skill-template.md, skills/sdlc-develop-verify-skill/references/feature-map-format.md, skills/sdlc-develop-verify-skill/references/dispatch-prompts.md
- **files-updated:** process/verify-command.md, process/path-mappings.md, process/commands.md, process/headless-mode.md, skills/sdlc-execute/SKILL.md, skills/sdlc-lite-execute/SKILL.md, skills/sdlc-migrate/SKILL.md, skills/sdlc-initialize/SKILL.md, skills/sdlc-develop-skill/SKILL.md, process/skill-agent-review.md, agents/sdlc-reviewer.md, CLAUDE-SDLC.md, knowledge/testing/advanced-test-patterns.yaml, skeleton/manifest.json
- **rule-count:** 1
- **ingested-by:** zsdlc-create-skill
- **notes:** Rewritten in z-sdlc's own words, not copied; the example app (Tally) is our own. Taken from pstack: reading the repo before asking (surface, launch, drive, evidence, isolation), the six sections of the generated skill, "ready means usable", the proof standards, the feature map's fixed four-section shape, proving the generated skill before handover with evidence that survives cleanup (z-sdlc drives every seeded feature, where pstack drives one), the unproven-on-a-stand-in list, and the maintain pass (read-only source readers per feature, a live drive of every feature with health checks after anything surprising, and triage into drift, harness gap and product bug). Changed by CD's decisions: one skill with a maintain mode instead of two, and the execute skills' smoke check uses the result. Left out: `.cursor/` paths and Cursor control skills, "fix the app first" (a broken app goes to the bug route), scaffolding a missing asset to get the app to start, and the pull request (z-sdlc commits locally after CD's yes).

---

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
