---
name: sdlc-design-consult
description: >
  Design consultation that synthesizes screenshots, references, and codebase context into 2-3 distinct
  design options backed by design theory. Uses the ui-ux-designer agent with design principles
  mandatory. Supports iterative refinement until a final direction is chosen.
  Use when a UI component, page layout, or interaction flow needs visual design exploration before implementation.
  Triggers on "design consult", "consult on the design", "design options", "give me design ideas",
  "help me design", "design this", "I need design help", "design consultation", "layout ideas",
  "UI concepts for".
  Do NOT use for implementation — this produces design direction only. Hand off to planning/execution skills.
  Do NOT use for code review — use sdlc-review-code.
---

# Design Consultation

Structured design consultation that produces 2-3 distinct design options for the user to evaluate, compare, and iterate on. Combines codebase-aware UI/UX expertise with design theory principles.

**This skill produces design direction. It does NOT produce code or implementation plans.** When the user selects a final direction, hand off to `sdlc-lite-plan` or `sdlc-plan` for implementation.

**Argument:** `$ARGUMENTS` (what to design — component, page, layout, feature area)

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## Workflow

```
GATHER → RESEARCH → DISPATCH DESIGNER → PRESENT OPTIONS → ITERATE → FINALIZE
```

The user stays in the loop at PRESENT and ITERATE. You present options, they react, you refine.

## Agent Dispatch Protocol

Dispatch prompts must describe WHAT/WHY — implementation HOW is the agent's domain. Every dispatch must include sufficient context for the agent to work autonomously.

**Critical:** The `ui-ux-designer` agent starts fresh each dispatch — it has no context from prior dispatches. Everything the agent needs must be in the dispatch prompt. The richer the context brief, the better the options.

## Steps

### 1. Gather Context

Collect everything the user has provided:
- Read any screenshots or images with the Read tool
- Read any reference files or directories mentioned
- Note verbal requirements, constraints, and preferences
- Identify what specifically needs design work (component, page, layout, etc.)

If the user hasn't provided enough context, ask:
- What is the UI surface? (page, component, modal, widget, etc.)
- What's wrong with the current version? (or is this net new?)
- Any references or inspiration?
- Any hard constraints? (must fit in X pixels, must work at specific resolutions, etc.)

**Output:** A context brief (10-15 lines max) summarizing: what exists, what the user wants, key constraints, and whether this is a specialized surface (e.g., broadcast overlay, mobile).

**Gate:** Present the context brief to the user before proceeding. Confirm understanding is correct — wrong context produces wrong concepts. If the user corrects anything, update the brief before moving on.

### 2. Research

Before dispatching the designer, YOU gather all relevant context from multiple sources. The designer agent starts fresh — it only knows what you pass in.

#### 2a. Codebase Research

1. Read the current component code if redesigning existing UI
2. Read design token files for the project's visual language
3. Read the relevant domain adapter or module if the design is domain-specific
4. Read related components that the design must integrate with
5. Check `.claude/agent-memory/ui-ux-designer/` for prior design decisions

#### 2b. Design Theory Research

Include general design principles in the context brief from your knowledge. Pick the 2-3 most relevant design theory areas based on the user's request:

| Design concern | Theory to include |
|---------------|-------------------|
| General audit / "what's wrong?" | Visual hierarchy checklist, gestalt principles |
| Layout feels off | Visual hierarchy, proximity, alignment |
| Color questions | Color theory, contrast ratios, color harmony |
| Typography questions | Type scale, font pairing, readability |
| Composition / eye flow | Composition rules, visual weight, focal points |
| Proportions | Golden ratio, modular scale, spacing systems |
| Motion / interaction | Easing curves, feedback patterns, transition timing |
| Responsive behavior | Breakpoint strategy, fluid typography, layout shifts |
| Design feels generic | Intentional character, brand voice in UI |
| Foundational direction | Design purpose, audience analysis, aesthetic direction |

**Pre-extract key principles, checklists, and decision trees** and include them in the context brief. The designer needs the actual content.

#### 2c. Web Research

Use WebSearch to research UI/UX patterns relevant to the design task. Frame the search around:

- How comparable products solve this design problem
- Current UI/UX best practices for this type of component/layout
- Accessibility patterns for the interaction type

Research comparable products in your domain area for reference patterns. For specialized surfaces (broadcast overlays, dashboards, data-heavy views), identify the industry-standard reference products for that context.

#### 2d. SDLC Context

Check the SDLC knowledge layer for context that should inform the design:

1. **Active deliverables**: Read `docs/current_work/` — related specs or plans that set constraints?
2. **SDLC-Lite work**: Check `docs/current_work/sdlc-lite/` for plans touching the same UI surface
3. **Archived decisions**: Check `docs/chronicle/` for past design decisions
4. **Design discipline**: Read `[sdlc-root]/disciplines/design.md` — UX modeling pipeline, parking lot items, trajectory
5. **Design knowledge** — Read the full design knowledge store for principles to include in the context brief:
   - Read `[sdlc-root]/knowledge/design/ux-modeling-methodology.yaml` for the UX modeling pipeline
   - Read `[sdlc-root]/knowledge/design/ascii-conventions.yaml` for wireframe notation rules
   - Read `[sdlc-root]/knowledge/design/accessibility-testability-principles.yaml` for accessibility and testability criteria
   - Read `[sdlc-root]/knowledge/design/component-patterns.yaml` for component structure and composition rules
   - Read `[sdlc-root]/knowledge/design/interaction-animation.yaml` for motion and transition principles
   - Read `[sdlc-root]/knowledge/design/interaction-patterns.yaml` for interaction state and micro-interaction patterns
   - Read `[sdlc-root]/knowledge/design/visual-design-rules.yaml` for color, typography, and visual hierarchy rules
   - Read `[sdlc-root]/knowledge/design/layout-principles.yaml` for layout grid and spacing systems

#### 2e. Compile the Context Brief

Synthesize all research into a structured brief for the designer. This brief IS the designer's world — anything not in it doesn't exist for the agent. Include:
- User requirements + screenshots described
- Codebase context (code, design tokens, domain constraints, agent memory)
- Design theory content (actual principles and checklists, not just file names)
- Web research findings (layout patterns, interaction patterns observed)
- SDLC context (prior decisions, constraints, established patterns)

### 3. Dispatch the Designer

Consult `[sdlc-root]/knowledge/agent-context-map.yaml` for the `ui-ux-designer` entry and include the mapped knowledge files in the dispatch prompt. The design knowledge files read in Step 2d supply the theory content; the context-map ensures the agent receives its full knowledge context.

Dispatch the `ui-ux-designer` agent with this structure:

```
DESIGN CONSULTATION REQUEST

## Context Brief
[Full compiled brief from step 2e]

## Design Theory Requirement (MANDATORY)
- For EXISTING UI: Audit current design first. Cite specific principles.
- For NEW UI: Establish design foundations, then apply design theory systematically.
- For ALL options: Ground every major decision in a named principle.
- Design theory context is provided below — use it.

[Paste pre-extracted theory content from step 2b]

## Output: 2-3 DISTINCT Options

Each option must have:
1. **Name** — 2-3 words capturing the philosophy (e.g., "Data-First Compact")
2. **Design philosophy** — 1-2 sentences on what this option optimizes for
3. **ASCII layout diagram** — spatial arrangement
4. **Key design decisions** — with theory justification for each
5. **Visual treatment** — colors, typography hierarchy, spacing, motion
6. **Tradeoffs** — what this option sacrifices vs. the others
7. **What's needed** — new assets, data, or components required

Options must differ in PHILOSOPHY, not minor details:
- One can prioritize visual impact (art-heavy, immersive)
- Another can prioritize information density (data-first, compact)
- Another can prioritize simplicity (minimal, focused)

Do NOT converge on a single recommendation. Present all options as viable with honest tradeoffs.
```

**Enforcement — theory:** If the agent's output reads like generic UI feedback without design theory references (named principles, cited rationale), re-dispatch: "Your output must include specific design theory references. Cite specific design principles explicitly."

**Enforcement — count:** If fewer than 2 concepts, re-dispatch: "You returned N concept(s). Produce 2-3 distinct concepts with different design philosophies."

### 4. Present Options

Present the options in a structured comparison format:

For each option show:
- Name and philosophy
- ASCII diagram
- Key decisions with theory justification
- Tradeoffs
- What's needed

Then add a comparison table:

```
| Dimension            | Option A | Option B | Option C |
|----------------------|----------|----------|----------|
| Visual impact        | ...      | ...      | ...      |
| Information density  | ...      | ...      | ...      |
| Implementation effort| ...      | ...      | ...      |
| Accessibility        | ...      | ...      | ...      |
| Mobile adaptability  | ...      | ...      | ...      |
```

Then ask: **"What speaks to you? You can pick one, combine elements from multiple, or tell me what to adjust."**

### 4b. Visual Mockups (optional, on request or when ASCII isn't enough)

Generate HTML mockups that use the actual project design tokens, rendered via Playwright and screenshotted for visual evaluation. This bridges the gap between ASCII wireframes and implemented code — the user sees what the design would actually look like without writing production code.

**When to offer mockups:**
- After presenting ASCII options, if the user asks "what would that look like?" or "can I see it?"
- When the design involves color, typography, or spacing decisions that ASCII can't communicate
- When comparing options where the difference is visual treatment, not layout structure

**How to generate a mockup:**

1. Write a self-contained HTML file to `/tmp/design-mockup-{option}.html` that:
   - Uses the actual project design tokens as inline CSS variables
   - Renders the design option at the appropriate viewport for the target surface
   - Uses system fonts (no external dependencies)
   - Is fully self-contained (inline CSS, no external resources)
   - Uses placeholder boxes/gradients for images

2. Use Playwright MCP to navigate to the HTML file, resize to the target viewport, and take a screenshot.

3. Show the screenshot to the user inline.

**Generate mockups for multiple options in parallel** when comparing.

**Mockup scope:** Keep mockups focused on layout, color, and typography — not interaction. These are static visual proofs. Do not add JavaScript, hover states, or animations.

**After showing mockups**, return to the normal iteration flow.

### 5. Iterate

The user may:
- **Pick one** → re-dispatch designer to deepen with full detail (all states, responsive, accessibility)
- **Combine** → re-dispatch with "Take [element] from A and [element] from B, synthesize"
- **Adjust** → re-dispatch with specific feedback
- **Reject all** → return to step 3 with new direction
- **Deep dive** → re-dispatch designer with focused brief on specific aspect (color, typography, motion)
- **Approve** → move to step 6

For each iteration, dispatch the designer again with the user's feedback AND all prior options as context.

There is no hard iteration limit — the user controls the loop. After 3 refinement rounds, add a soft prompt: "We've refined 3 times. Want to finalize this direction, or keep iterating?"

### 6. Finalize

When the user confirms a final direction:

1. Produce a clean design spec:

```markdown
## Design Spec: [Title]

**Produced by:** sdlc-design-consult skill
**Date:** [date]
**Target:** [component/page/feature]

### Design Direction
[Name of selected concept + philosophy]

### Layout
[Final ASCII wireframe]

### Component Specifications
[Per component: purpose, states, responsive behavior, accessibility]

### Design Tokens
[New tokens or modifications needed]

### Design Theory Backing
[Principles supporting this design]

### Scope Assessment
[Files that would need to change, packages affected]
[Whether this warrants SDLC tracking or can proceed ad hoc]
```

2. Save the spec to `docs/current_work/design/{slug}_design-spec.md`

3. Recommend next step based on scope:
   - Single file → just implement it
   - 2-3 files → suggest `sdlc-lite-plan`
   - 4+ files or new abstractions → suggest `sdlc-plan`

**Discipline capture:** Run the protocol per `[sdlc-root]/process/discipline_capture.md`. Context format: `[sdlc-design-consult: {slug}]`. Structured gap detection: comparison #2 (cross-domain friction) only — comparisons #1 and #3 are not applicable without a review-fix loop.

Do NOT start implementing. The design consultation ends with a direction and a handoff.

## Red Flags

| Thought | Reality |
|---------|---------|
| "The agent produced good output without citing theory" | Check for theory references. Good-sounding output without theory backing is the failure mode this skill exists to prevent. |
| "One concept is obviously right, skip the others" | The user decides. Present 2-3 options even when one seems dominant. |
| "Skip the audit, we're designing from scratch" | If existing implementation exists, audit it. Understanding what's wrong informs what to build. |
| "Skip web research, I know what looks good" | Research grounds concepts in real-world patterns. Without it, designs are invented from training data. |
| "The user just wants a quick opinion" | Give a quick opinion AND offer the full consultation. Quick opinions miss what structured analysis catches. |
| "I'll skip reading the codebase, the designer knows it" | The designer starts fresh each dispatch. YOU gather context and pass it in. |
| "I'll skip the design theory section, the designer knows theory" | The brief tells the designer which principles this request turns on. Without it, options come back as generic UI feedback and fail the theory enforcement check. |
| "I'll skip SDLC context" | Prior deliverables may have established constraints or patterns. A 30-second scan prevents contradicting past decisions. |
| "I'll present the designer's raw output" | Restructure into the comparison format. The user needs side-by-side evaluation, not an agent dump. |
| "The user provided a screenshot that makes the problem obvious — skip research" | Screenshots show what IS, not what COULD BE. Research surfaces patterns the screenshot can't. |
| "The agent cited theory on the first dispatch, no need to verify" | Trust but verify. Check for theory references. Agents skip theory grounding more often than expected. |
| "The user picked one, let me start coding" | This skill produces direction, not code. Hand off to planning. |
| "The mockup needs to be interactive/animated" | Mockups are static visual proofs — layout, color, typography only. |

## Integration

- **Feeds into:** `sdlc-lite-plan` or `sdlc-plan` (for implementation)
- **Uses:** `ui-ux-designer` agent, WebSearch (for design research), Playwright MCP (for visual mockups)
- **Knowledge routing:** `[sdlc-root]/knowledge/agent-context-map.yaml` (dispatch-time injection), all 8 files under `[sdlc-root]/knowledge/design/`, `[sdlc-root]/disciplines/design.md`
- **Complements:** `sdlc-idea` (conceptual exploration) — `sdlc-design-consult` explores visual direction, `sdlc-idea` explores conceptual direction. An idea brief from `sdlc-idea` can feed into `sdlc-design-consult` when the concept needs visual exploration.
- **Does NOT replace:** `sdlc-review-code` (code review), `accessibility-auditor` (WCAG compliance on implemented code)
- **Installed via:** The `design` bundle (opt-in during `/sdlc-initialize`). Not part of the default install.
