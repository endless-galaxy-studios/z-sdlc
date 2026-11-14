# SDLC Disciplines

## North Star: Toolbox, Not Recipe

This framework is a toolbox of available capabilities, not a prescribed sequence that must be followed end to end. The first activity is always **tailor to the pursuit**.

Both RUP and SAFe included "tailor the methodology" as a core principle, but their ecosystems made the full prescription the path of least resistance. We learn from that mistake. Nothing here is mandatory overhead. Disciplines, knowledge stores, spec formats, knowledge layers — they exist *when you need them* and stay out of the way when you don't.

**Guidelines:**
- Vibe coding is valid. Exploratory and creative work benefits from minimal process. The ad hoc accommodations in `[sdlc-root]/process/overview.md` exist for exactly this reason.
- Use the discipline that helps. Ignore the ones that don't. A quick prototype doesn't need Layer 0 risk analysis.
- Add process only when its absence caused a problem. "We should have written a spec" is the right trigger, not "the process says we must write a spec."
- Each discipline should deliver value immediately when invoked, not require setup, ceremony, or prerequisite steps.
- If the process feels heavy, it's wrong — simplify it or skip it.

## The Key Distinction: Disciplines vs Phases

Our SDLC process (`[sdlc-root]/process/overview.md`) describes **phases** — the temporal stages work moves through:

```
Idea → Spec → Planning → Implementation → Result → Chronicle
```

But the real work is done by **disciplines** — capabilities that persist across the entire lifecycle, with varying intensity at each phase:

```
                    Inception  Spec  Planning  Impl  Validation  Deploy  Evolution
                    ─────────  ────  ────────  ────  ──────────  ──────  ─────────
Product Research    ████████   ███   ██        █                         ██
Business Analysis   ████████   ████████  ███   ██    █                   ██
Design              ███        ████████  ████████  ██████  ██            ███
Architecture        ██████     ████████  ████████  ████    ██   █        ██
Coding                                  ███   ████████████  ██  ██       ████
Testing             █          ██        ███   ████  ████████████  ██    ████
Deployment                                    █     ██      █████████   ██
```

This is the RUP "hump chart" insight: disciplines don't live in phases — they *cross* phases. Testing doesn't happen in a "testing phase." It's a lens that's always available, with peak intensity during validation but present during spec review, planning, and even product research ("is this testable?").

## Why This Matters

1. **Ideas don't respect phase boundaries.** During a test run, you discover a product research question. During coding, you realize a design assumption was wrong. During business analysis, you identify a testing risk. These insights need a place to land *immediately*, not "when we get to that phase."

2. **Each discipline is a future skill.** The testing discipline already has `sdlc-tests-create` and `sdlc-tests-run`. The same pattern applies to every discipline. A mature SDLC is a suite of discipline skills orchestrated across phases.

3. **Cross-discipline knowledge compounds.** What testing learns about UI fragility feeds into design. What architecture learns about performance constraints feeds into business analysis. The knowledge store concept from testing (Layers 0-6) generalizes to all disciplines.

## Structure

Each discipline has a file in this directory. Each file serves as a **parking lot** — a place to capture ideas, patterns, questions, and learning as they emerge during work in *any* discipline. The files are not formal specs. They're scratch pads that accumulate raw material for when the discipline gets deeper attention.

```
disciplines/
├── README.md                  ← This file (mental model + structure)
├── testing.md                 ← Most developed (active knowledge stores in knowledge/testing/)
├── design.md                  ← UI/UX, visual design, interaction patterns
├── coding.md                  ← Implementation patterns, conventions, tech debt
├── architecture.md            ← System design, component boundaries, integration
├── business-analysis.md       ← Requirements, domain modeling, stakeholder needs
├── product-research.md        ← Market, users, competitive landscape, feature ideas
├── deployment.md              ← CI/CD, infrastructure, release management
└── process-improvement.md     ← Meta: improving the SDLC itself
```

## How to Use

**During any work session**, if you encounter an insight that belongs to a discipline other than your current focus:

1. Open the discipline's parking lot file
2. Add the insight under the appropriate heading (with date and source context)
3. Continue your current work

**SDLC skills automatically prompt for discipline capture** at key points:
- After execution completes (sdlc-execute, sdlc-lite-execute) — before committing
- After planning completes (sdlc-plan, sdlc-lite-plan) — after agent review
- During idea exploration (sdlc-idea) — insights from research
- During design consultation (`sdlc-design-consult`, design bundle) — design insights
- During bulk knowledge import (sdlc-ingest) — external content → knowledge files and parking lots

**Triage markers** — when adding parking lot entries, optionally mark their readiness for promotion:

| Marker | Meaning | Action |
|--------|---------|--------|
| `[READY TO PROMOTE]` | Validated through real use, reusable, stable | Auditor surfaces to CD for promotion to knowledge/skill/process |
| `[NEEDS VALIDATION]` | Promising but not yet confirmed through use | Leave in parking lot until validated |
| `[DEFERRED]` | Acknowledged but not a priority (include reason) | Revisit at next planning boundary |
| *(no marker)* | Newly captured, not yet triaged | Auditor flags after 2 audit cycles without triage |

**At planning boundaries** (deliverable kickoff, quarterly review, new project):

1. Read the relevant discipline parking lots
2. Scan for `[READY TO PROMOTE]` items — promote directly to knowledge YAML, skill update, or process change
3. Triage unmarked items: mark as `[NEEDS VALIDATION]`, `[DEFERRED]`, or `[READY TO PROMOTE]`

**When a discipline matures** (enough patterns to formalize):

1. Promote `[READY TO PROMOTE]` items directly to structured knowledge (knowledge/ YAML files)
2. Design skill definitions from the validated patterns
3. Move promoted entries from the active parking lot to the `### Promoted` section at the bottom — mark them `Promoted → [target file]`. See `[sdlc-root]/process/discipline_capture.md` § Promotion Workflow.

## Creating a New Discipline

Disciplines are not created speculatively. They emerge from real work when a recurring capability doesn't fit any existing discipline.

### When to create

A new discipline is warranted when **all three** conditions are met:

1. **Recurring capability.** You've done this type of work on 2+ deliverables and expect to do it again.
2. **No existing home.** The insights don't naturally fit in any current discipline's parking lot. If they do fit (even loosely), add them to the existing discipline instead of creating a new one.
3. **Distinct agent role.** The work would be dispatched to a different type of agent than any existing discipline's agents. If the same architect or developer handles it, it's probably a sub-concern of an existing discipline, not a new one.

**Anti-pattern: premature discipline creation.** Creating a discipline for a one-time concern (e.g., "migration discipline" for a single database migration) adds overhead without value. If it turns out to be recurring, you can always create it later. The parking lot for the closest existing discipline is the right interim home.

### Minimum viable discipline

A new discipline starts at Level 1 (Initial) and requires exactly:

1. **Discipline file** — `[sdlc-root]/disciplines/<name>.md` with:
   - Status line (`Parking lot — [brief description]`)
   - Scope section (what capability this discipline covers)
   - Parking lot section (empty, ready for entries)

2. **Tracker entry** — add a row to the Process Maturity Tracker in `[sdlc-root]/disciplines/process-improvement.md` at Level 1

3. **Manifest entry** — *(z-sdlc framework developers only)* add the file path to `skeleton/manifest.json` under `source_files.disciplines`

4. **Hump chart row** — add the discipline to the intensity chart in this README (estimate where it peaks across phases)

That's it. No knowledge store directory, no agent-context-map entry, no skill. Those come when the discipline reaches Level 2.

### Lifecycle

```
Recurring capability observed
  ↓
Check: does it fit an existing discipline? → yes → add to that parking lot
  ↓ no
Create discipline file (Level 1)
  ↓
Capture insights during work (parking lot fills)
  ↓
Triage entries → some marked [READY TO PROMOTE]
  ↓
Promote to knowledge store → create knowledge/<name>/ (Level 2)
  ↓
Wire agents via agent-context-map
  ↓
Package as skill (optional, when patterns are stable enough)
```

### What NOT to do

- Don't create a discipline and a knowledge store at the same time. The parking lot must accumulate and be triaged first. Jumping to structured YAML without validated insights produces speculative knowledge.
- Don't create a discipline to "own" work that's currently handled fine by existing disciplines. The question is not "could this have its own discipline?" but "is the current home insufficient?"
- Don't add a discipline to the hump chart at high intensity across all phases. New disciplines start narrow — they peak in 1-2 phases and are silent elsewhere. Intensity grows with maturity.

## Relationship to Existing SDLC

| Existing | Discipline view |
|----------|-----------------|
| `process/` | Phase definitions — *when* work happens |
| `disciplines/` | Capability definitions — *what* capabilities are applied, plus parking lot entries with triage markers |
| `templates/` | Phase-oriented artifacts (spec, plan, result) |
| `knowledge/` | Discipline-specific knowledge stores (testing, data-modeling, etc.) |

The phase and discipline views are complementary, not competing. A deliverable still flows through phases (Spec → Plan → Implement → Result). But at each phase, multiple disciplines contribute — and each discipline accumulates knowledge that persists beyond any single deliverable.
