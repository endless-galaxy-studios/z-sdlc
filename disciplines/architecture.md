# Architecture Discipline

**Status**: Active — backend capability assessment

## Scope

System design, component boundaries, integration patterns, technology choices, cross-project patterns. Assessing what a backend currently supports and estimating the cost of adding capabilities that unlock desired feature scope.

## Backend Capability Assessment

**When to invoke:** After competitive analysis produces a scoped feature definition with open questions, and before UX modeling finalizes the design. The backend assessment bridges "what should we build?" with "what CAN we build?"

**What it produces:**
- Backend inventory summary (API surface, database, services, auth, existing patterns)
- Capability matrix mapping feature dimensions to support levels (Supported / Partial / New / Infrastructure)
- Cost estimates with T-shirt sizing and dependency chains
- Scope recommendation organized by effort tier (ship now, quick wins, significant investment, revisit later)

**How to use the output:** Map each effort tier back to the competitive analysis scoping questions. This gives the product owner cost-aware information to adjust scope decisions.

**Knowledge store:** `[sdlc-root]/knowledge/architecture/` (see inventory below)

**Pipeline position:**
```
/feature-compare → scope questions → product owner picks target scope
  ↓
/backend-assess → capability matrix, cost estimates    ← THIS
  ↓
/ux-model → IA, wireframes, specs (informed by what's feasible)
  ↓
spec → plan → implement
```

## Knowledge Store Inventory

| File | Domain | Primary Consumers |
|------|--------|-------------------|
| `backend-capability-assessment.yaml` | Capability matrix, cost estimation | [architect] |
| `technology-patterns.yaml` | Stack-specific patterns | [architect], [backend-developer], [build-engineer] |
| `pipeline-design-patterns.yaml` | ETL, data pipeline, background processing patterns | [architect], [data-engineer] |
| `api-design-methodology.yaml` | REST API design, route conventions | [architect], [backend-developer] |
| `deployment-patterns.yaml` | CI/CD, hosting deploy patterns | [architect], [backend-developer], [build-engineer] |
| `agent-communication-protocol.yaml` | Cross-agent structured output format | All agents |
| `knowledge-management-methodology.yaml` | Knowledge store organization patterns | [architect], compliance auditor |
| `debugging-methodology.yaml` | Root cause analysis, investigation workflow | [debug-specialist], [code-reviewer] |
| `investigation-report-format.yaml` | Structured investigation output format, and how to explain why code is shaped as it is | [debug-specialist], [code-reviewer], [security-engineer], [performance-engineer], [accessibility-auditor], [architect], [refactor-engineer], compliance auditor |
| `error-cascade-methodology.yaml` | Error propagation tracing, failure chains | [debug-specialist], [performance-engineer] |
| `security-review-taxonomy.yaml` | Security assessment categories, OWASP mapping | [security-engineer], [code-reviewer] |
| `payment-state-machine.yaml` | Payment flow states, gateway integration | [payment-engineer] |
| `ml-system-design.yaml` | ML inference pipelines, model lifecycle | [ml-architect] |
| `prompt-engineering-patterns.yaml` | LLM prompt design, evaluation patterns | [ml-architect] |
| `domain-boundary-gotchas.yaml` | Cross-domain work patterns, orchestrator signals | [architect], [code-reviewer] |
| `token-economics.yaml` | Context window constraints on AI-assisted workflows | [architect] |
| `model-tier-strategy.yaml` | Model/effort tier matching for agent dispatch | [architect], all orchestrating skills |
| `database-optimization-methodology.yaml` | Query optimization, index strategy | [data-engineer], [backend-developer] |

## Parking Lot

*Add architectural insights here as they emerge during work. Include date and source context.*

### Promoted

- **Layer 0 (upstream SDLC context) is an architectural function.** Promoted → `[sdlc-root]/knowledge/architecture/domain-boundary-gotchas.yaml` (architect-feeds-testing-risk-areas entry)
- **Two-tier knowledge architecture.** Promoted → `[sdlc-root]/knowledge/architecture/knowledge-management-methodology.yaml` (two_tier_architecture section)
- **Token economics as an architectural constraint.** Promoted → `[sdlc-root]/knowledge/architecture/token-economics.yaml`
- **Async concurrency: pass a session/connection factory.** Promoted → `[sdlc-root]/knowledge/architecture/domain-boundary-gotchas.yaml` (async-session-factory-concurrency entry)
- **Advisory lock + connection pooling release locks silently.** Promoted → `[sdlc-root]/knowledge/architecture/domain-boundary-gotchas.yaml` (advisory-lock-pool-release entry)
- **Lazy initialization needs a short-circuit for tests.** Promoted → `[sdlc-root]/knowledge/architecture/domain-boundary-gotchas.yaml` (lazy-init-test-shortcircuit entry)
- **"Metadata-only" flags don't gate behavior — until they do.** Promoted → `[sdlc-root]/knowledge/architecture/domain-boundary-gotchas.yaml` (metadata-only-flag-drift entry)

### Model & Effort Tiering (2026-07-08, source: r/ClaudeAI community threads + community "fable-chief-agent" skill)

*Bulk import from community tiered-orchestration discussion. Validated, generalizable rules were promoted directly to `[sdlc-root]/knowledge/architecture/model-tier-strategy.yaml` (MTS1–MTS6); the entries below need validation before promotion.*

- **Per-agent `effort:` frontmatter support matrix.** [NEEDS VALIDATION] Community reports per-subagent effort (`low` through `max`) in agent frontmatter overriding session effort, with recon roles at low effort "nearly free quality-wise." Verify which Claude Code versions support the field and confirm the accepted value set (low | medium | high | xhigh | max) before projects rely on it. (Source: r/ClaudeAI effort-frontmatter thread, 2026-07 screenshot)
- **Sonnet-tier workers thrash on Rust codebases.** [NEEDS VALIDATION] One practitioner reports Sonnet "struggles with Rust codebases then drowns in tool calls" while performing well on frontend work. If reproduced, Rust-heavy projects should default implementer agents to opus-tier or add a stack note at initialization. Recheck per model release. (Source: r/ClaudeAI tiered-workflow thread, 2026-07 screenshot)
- **Per-phase Model/Effort column in plan templates.** [NEEDS VALIDATION] Plans assign agents per phase; the agent's frontmatter carries the tier. An explicit per-phase Model/Effort override column in `planning_template.md` would let the planning agent encode MTS4 escalations in the artifact instead of relying on dispatch-time judgment — but adds template weight. Trial on a high-risk deliverable first. (Source: this ingestion's gap analysis)
