---
name: sdlc-idea
description: >
  Open-ended exploration and iterative concept development for ideas that aren't ready to plan yet.
  Focuses on Socratic questioning, codebase-aware research, and sketching multiple conceptual
  approaches before committing to any direction. Produces an idea brief, not a spec or plan.
  Use when an idea needs open-ended exploration before it's ready for formal planning.
  Triggers on "I have an idea", "let's explore", "what if we", "brainstorm", "how should we approach",
  "I'm thinking about", "explore this concept", "idea for", "could we", "what would it take to",
  "kick around an idea", "spitball", "before we plan anything", "I want to think through".
  Do NOT use for work that already has clear requirements — use sdlc-plan or sdlc-lite-plan.
  Do NOT use for visual/UI exploration — use sdlc-design-consult (design bundle) or the project's design agent.
  Do NOT use for active bug investigation — use sdlc-review-code or direct dispatch.
---

# Idea Exploration

Structured but open-ended exploration for ideas that aren't ready for planning. The goal is to deepen understanding of the problem space, surface constraints and possibilities, and sketch conceptual approaches — without committing to any single direction.

**This skill produces an idea brief. It does NOT produce a spec, plan, or design.** When the user is ready to commit, hand off to the appropriate next skill.

**Argument:** `$ARGUMENTS` (the seed idea — however vague or specific)

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Two exceptions stand: the skill's own knowledge-layer updates count as local work, even when an adapter writes them to its memory store (a subagent's own memory-store writes don't), and the External Review Gate may send to a hosted provider the project has durably authorized (`[sdlc-root]/process/external-review-gate.md` § Data egress). Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## When This Applies

Use this when the user has a thought, question, or direction they want to explore before writing requirements. The hallmark is uncertainty — the user doesn't yet know what they want to build, or they know the problem but not the shape of the solution.

Signs this skill is appropriate:
- "What if we..." / "Could we..." / "I'm wondering about..."
- The user describes a problem without proposing a solution
- The user has a solution idea but hasn't thought through implications
- Multiple viable approaches exist and the user hasn't chosen
- The idea crosses domain boundaries and the right framing isn't obvious

Signs this skill is NOT appropriate:
- Clear requirements already exist → `sdlc-plan` or `sdlc-lite-plan`
- The question is purely visual/UI → `sdlc-design-consult` if the design bundle is installed; otherwise a design agent from `[sdlc-root]/process/agent-selection.yaml`, if the project has one
- The user says "build this" with specifics → planning skill, not exploration

## Core Principles

**No premature convergence.** The instinct to propose solutions immediately is the enemy of good exploration. Stay in the question space longer than feels comfortable.

**Codebase-first.** Before asking the user anything, search the codebase. The idea may already be partially implemented, previously attempted, or constrained by existing architecture. Discovery that ignores existing reality wastes the user's time.

**One question at a time.** Batched questions get shallow answers. Ask the most important question, let the answer inform the next one.

**Sketch, don't spec.** Conceptual approaches are rough shapes — "we could use a queue" not "implement a RabbitMQ consumer with retry policy X". Keep the altitude high enough that pivoting is cheap.

**The user decides when to stop.** There is no gate, no minimum question count, no mandatory output. The user may explore for 2 minutes or 2 hours. Follow their energy.

## Workflow

```
SEED → GROUND → QUESTION → RESEARCH → SKETCH → ITERATE → (optional) CRYSTALLIZE
```

The flow is non-linear. Any step can loop back to any earlier step. New information from research may reframe the seed entirely. A sketch may reveal that the wrong question was asked. This is expected.

## Steps

### 1. Receive the Seed

Acknowledge what the user brought. Restate the idea in your own words to confirm understanding. If the idea is vague, that's fine — name the vagueness explicitly:

> "So the seed is: [restatement]. What I'm not clear on yet is [the fuzzy parts]. Let me look at the codebase before I ask questions."

Do NOT immediately propose solutions or ask a list of questions. Ground first.

### 2. Ground in the Codebase

Before asking the user anything, search for relevant context:

1. **Existing implementations** — Is anything like this already built? Partially built? Previously attempted and removed?
2. **Architectural constraints** — What patterns exist that this idea must work within? What boundaries exist (API layers, module boundaries, data flow)?
3. **Related systems** — What adjacent code would this idea touch or depend on?
4. **Chronicle context** — Scan `docs/chronicle/` for related concepts. Read `_index.md` for any that match. Prior deliverables may have explored adjacent territory.
5. **Knowledge layer** — Read relevant files under `[sdlc-root]/knowledge/` and `[sdlc-root]/disciplines/` for domain knowledge, especially methodology files that define how the project approaches this domain.
6. **Active work** — Check `docs/current_work/` for in-flight deliverables that might overlap or conflict.

Use LSP (`goToDefinition`, `findReferences`, `hover`) for type-system questions. Use Grep for text patterns. Do NOT ask the user what you can discover by reading code.

**Present a grounding summary** before asking questions:

```
GROUNDING
Existing relevant code: [what exists and where]
Architectural context: [patterns, boundaries, constraints discovered]
Related chronicle entries: [prior decisions that inform this space]
Active work that may intersect: [in-flight deliverables, or "none"]
```

This summary serves two purposes: it shows the user you've done homework, and it often reframes the idea based on what actually exists.

### 3. Socratic Questioning

Ask questions that deepen understanding of the problem space. The goal is NOT to gather requirements (that's planning) — it's to help the user think through what they actually want and why.

**Question categories** (use as a menu, not a checklist):

| Category | Purpose | Example |
|----------|---------|---------|
| **Problem** | Understand the pain | "What's the actual friction today? Walk me through a concrete scenario where this hurts." |
| **Audience** | Who benefits and how | "Who encounters this problem? Is it every user or a specific workflow?" |
| **Constraints** | Surface hidden limits | "Are there performance/cost/timeline constraints that would shape the solution?" |
| **Tradeoffs** | Explore the tension | "If you had to choose between X and Y, which matters more?" |
| **Prior art** | Learn from the past | "Have you seen this solved well somewhere else? What did you like about their approach?" |
| **Scope** | Understand boundaries | "What's explicitly NOT part of this idea?" |
| **Risk** | Identify the scary parts | "What's the part of this that makes you most nervous?" |
| **Value** | Clarify motivation | "If this existed and worked perfectly, what changes for the user/team/product?" |

**Deep interview technique:** Don't ask obvious questions — dig into the hard parts the user might not have considered. Probe specifically for:
- **Edge cases** — "What happens when [unusual but plausible scenario]?"
- **Failure modes** — "If this breaks, what's the blast radius? How would you know it broke?"
- **Hidden dependencies** — "Does this assume [X] will always be true? What if it isn't?"
- **Scale implications** — "Does this need to work for 10 items or 10,000? Does that change the approach?"
- **Second-order effects** — "If we build this, what else changes? What becomes possible or impossible?"

The goal is to surface the things the user hasn't thought about yet — not to validate what they already know.

**Questioning discipline:**
- Ask ONE question per turn
- Let the answer land before pivoting to a new category
- Follow threads — if the user says something surprising, go deeper on that
- Share your reasoning: "I'm asking because [context from grounding] suggests..."
- If the user gives a short answer, that's a signal — don't push. Move to a different angle.
- When you learn something that changes the picture, say so: "That reframes this — now I'm thinking about it as [new framing]."

There is no minimum question count. The user may answer two questions and have full clarity. They may explore for twenty questions and still be uncertain. Both are valid.

### 4. Research (as needed)

Research is **demand-driven, not default**. Trigger research only when a specific unknown emerges from questioning — never run a research sweep up front, and never fan out multiple research agents "just to be thorough." Premature research is a convergence trap: it produces findings that feel like answers before the real question has been sharpened.

When an unknown does emerge, pick the lightest tool that can resolve it:

**Codebase deep-dives** — Trace specific code paths, read specific modules, verify what the architecture actually supports vs. what seems possible. Use directly (Read, Grep, LSP).

**Library/API verification** — If the idea involves external libraries or services, verify capabilities via Context7 (`mcp__context7__resolve-library-id` → `mcp__context7__query-docs`). Do NOT assume library capabilities from training data.

**Knowledge store consultation** — Consult `[sdlc-root]/knowledge/agent-context-map.yaml` to identify which methodology files are relevant to the domain being explored, then read those files. They define how the project approaches this domain (e.g., testing paradigm for test-related ideas, data modeling patterns for schema ideas).

**Project specialist agents** — Before reaching for WebSearch yourself, scan `[sdlc-root]/process/agent-selection.yaml` (`tier1:` and `tier2:` only) for any project-installed agent whose domain matches the unknown.

A project-tier agent fits the unknown when its `dispatch_when` triggers, `covers` list, or domain framing maps to what you're trying to learn. Examples (illustrative — actual roster is project-specific):

| Unknown shape | Project-tier agent that fits (if installed) |
|---|---|
| "What's the right retrieval strategy / ranking model / embedding approach?" | An IR specialist (e.g., `ir-analyst`) |
| "How should this schema/index/migration be shaped?" | `data-architect` |
| "Which auth/input-validation pattern applies here?" | `security-engineer` |
| "How should this real-time/WebSocket flow be structured?" | `realtime-systems-engineer` |

If no project-tier agent's domain matches the unknown, fall back to direct tools — WebSearch for narrow facts, Context7 for library/API verification. Do not synthesize a personal-tier dispatch; if the project lacks a specialist for this domain, that's a signal to either keep the research narrow or surface the gap to the user (they may want to add an agent via `sdlc-develop-agent`).

Dispatch rules when a project-tier agent fits:
- One agent per emerged unknown. If you can't articulate which specific question the agent is answering, you're not ready to dispatch.
- Brief the agent with the seed, the grounding summary, and the specific unknown — not the entire conversation.
- Wait for findings before continuing to question or sketch — research that arrives after a sketch is locked in is wasted.

Share research findings with the user as they come in. New information often shifts the conversation, sometimes back to step 2 or 3.

### 5. Sketch Conceptual Approaches

When enough understanding exists (the user will signal this, or you'll notice the conversation naturally shifting from "what's the problem" to "how might we solve it"), sketch 2-3 conceptual approaches.

**This step is expected but not mandatory.** If the exploration converges quickly on a single obvious direction (e.g., the codebase architecture makes one approach clearly natural), it's fine to skip straight to Crystallize with a single Direction. But when multiple viable approaches exist and the user hasn't explicitly chosen, present sketches — don't collapse the option space on their behalf.

**Sketches are NOT specs.** They are rough shapes — each one a different way to think about the solution:

For each approach:
- **Name** — 2-4 words capturing the philosophy
- **Core idea** — 2-3 sentences: what this approach bets on
- **How it works** — High-level description (a paragraph, not implementation steps)
- **What it gets right** — Strengths relative to the problem as understood
- **What it gives up** — Honest tradeoffs
- **Open questions** — What would need to be figured out to pursue this approach
- **Feasibility signal** — Based on grounding: how much existing code supports vs. works against this approach

Present sketches side by side. Do NOT rank them or recommend one. The user chooses the direction.

**Interactive exploration artifacts:** When sketches involve visual concepts (UI layouts, interaction flows, data visualizations, component variants), create self-contained HTML files as exploration tools. These are NOT explainers — they're throwaway working artifacts that help CD evaluate options:

- **Side-by-side comparisons** — Render 2-4 visual approaches in a single HTML file so CD can compare them at a glance
- **Interaction prototypes** — Clickable flows, animation sandboxes, hover states — things that can't be described, only felt
- **Parameter tuning** — Sliders, knobs, and controls to adjust spacing, timing, thresholds, colors. Include a "copy settings" button so CD can paste chosen values back into the conversation
- **Architecture diagrams** — Interactive SVG with clickable nodes that reveal module details, data flows, dependency paths
- **Drag-and-drop prioritization** — When sketching multiple options or requirements, let CD drag to reorder priorities

Write exploration artifacts to `/tmp/` or `docs/current_work/ideas/` with descriptive names (e.g., `{slug}_comparison.html`, `{slug}_prototype.html`). Read the design system from `[sdlc-root]/templates/html-design-system.html` for visual tokens but use whatever JavaScript and interactivity the exploration requires — the static, stepper-only rule applies to explainers, not exploration artifacts.

After presenting: **"Any of these resonate? We can go deeper on one, combine elements, or throw them all out and come at this differently."**

### 6. Iterate

The user may:
- **Go deeper** on one approach → refine the sketch, explore its implications
- **Combine** elements from multiple approaches → sketch the hybrid
- **Pivot** entirely → new seed, back to questioning
- **Ask new questions** → follow the thread
- **Bring new constraints** → re-evaluate approaches against them
- **Request research** on a specific unknown → investigate and report back
- **Decide they're done** → move to crystallize or just stop

There is no iteration limit. After 3-4 rounds of refinement on the same approach, offer a soft prompt: "This is getting pretty shaped. Want to crystallize it into a brief, or keep exploring?"

### 7. Crystallize (optional)

When the user signals readiness (or when the conversation has naturally converged), produce an **idea brief** — a lightweight document that captures the exploration:

```markdown
---
type: idea-brief
title: "[Title]"
status: active
explored: YYYY-MM-DD
seed: "[original idea — use the user's actual words, not a cleaned-up restatement]"
tags: []
---

# Idea Brief: [Title]

### Problem Understanding
[2-3 sentences: the problem as understood after exploration]

### Key Insights from Exploration
- [Insight from questioning or research that shaped thinking]
- [Constraint discovered that wasn't obvious at the start]
- [Pattern from codebase that informs the approach]

### Direction
[The approach the user gravitated toward — name and 3-4 sentence description]

### Open Questions
- [What still needs answering before this can be planned]
- [Technical unknowns that require prototyping or deeper research]

### Codebase Context
[Key files, modules, and patterns discovered during grounding that inform the direction — name specific paths]

### Feasibility Notes
[What the codebase grounding revealed about effort and risk]

### Recommended Next Step
- [Specific skill to use next and why]
```

Save to: `docs/current_work/ideas/{slug}_idea-brief.md`

If the `docs/current_work/ideas/` directory doesn't exist, create it.

**Post-write: offer an explainer or a walkthrough.** Ask CD whether they want an HTML explainer (`sdlc-explain`, **exploration** storyboard) or a guided walkthrough (`sdlc-walkthru`) of the idea brief — never unprompted. Mechanics and the precedes-approval rule: `[sdlc-root]/process/html-rendering.md` § Post-Skill Offer.

**Recommend next step based on what emerged:**
- Clear requirements, bounded scope → `sdlc-lite-plan`
- Complex feature, needs spec → `sdlc-plan`
- Visual/UI direction needed → `sdlc-design-consult` if the design bundle is installed; otherwise a design agent from `[sdlc-root]/process/agent-selection.yaml`, if the project has one
- Technical unknown needs prototyping → suggest a spike (direct dispatch)
- Still too vague → keep exploring (this skill isn't done yet)

**Discipline capture:** Run the protocol per `[sdlc-root]/process/discipline_capture.md`. Context format: `[idea: {slug}]`. Structured gap detection: comparison #2 (cross-domain friction) only — comparisons #1 and #3 are not applicable without a review-fix loop.

Do NOT start planning or implementing. The idea exploration ends with a direction and a handoff.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I already know the right approach, skip to sketching" | The user came to explore, not to receive a recommendation. Ask questions first. |
| "The user's idea is obviously X, let me reframe it better" | Confirm understanding, don't overwrite. The user knows their context better than you. |
| "I should ask all the question categories" | The categories are a menu, not a checklist. Ask what's relevant. |
| "The user only answered two questions, that's not enough" | The user decides when enough is enough. There is no minimum. |
| "This approach is clearly better, I should recommend it" | Present options without ranking. The user chooses. |
| "We've explored enough, time to write a spec" | This skill produces an idea brief, not a spec. Hand off to planning when the user is ready. |
| "The user said 'build this' — I should start planning" | If they said it during exploration, ask: "Ready to move to planning, or still exploring?" |
| "I'll skip codebase grounding, the idea is conceptual" | Every idea lives in a codebase context. Ground first, always. |
| "The user seems to know what they want — skip questioning" | Even confident users benefit from one or two probing questions. The question may not change the direction, but it often sharpens it. |
| "Let me batch 5 questions to save time" | One question at a time. Batched questions get shallow answers. |
| "Let me fan out a few research agents in parallel before questioning" | Research is demand-driven. Dispatch a specialist only after a specific unknown has emerged — running a menu up front locks in convergence before the real question is even sharp. |
| "I'll WebSearch this myself, faster than dispatching" | For a narrow factual lookup, yes. But scan `agent-selection.yaml` (`tier1`/`tier2`) first — if a project-installed specialist's domain matches the unknown, dispatch them; their depth beats your generic search. |
| "I'll dispatch a personal-tier agent like research-analyst since it's listed in agent-selection.yaml" | Don't. Personal-tier agents live at `~/.claude/agents/` and aren't guaranteed to exist for every contributor. Only dispatch project-tier agents (`tier1`/`tier2`); fall back to direct WebSearch/Context7 otherwise. |

## Integration

- **Feeds into:** `sdlc-plan` (full planning), `sdlc-lite-plan` (lightweight planning), `sdlc-design-consult` (design bundle: visual design exploration)
- **Uses:** LSP, Grep, Context7, WebSearch, chronicle and knowledge layer; consults `[sdlc-root]/process/agent-selection.yaml` (`tier1`/`tier2` only — never `personal:`) to dispatch a project-installed specialist when an emerged unknown maps to its domain
- **Complements:** `sdlc-design-consult` (design bundle), or the project's design agent, explores visual direction; `idea` explores conceptual direction. They can feed into each other.
- **Does NOT replace:** DISCOVERY-GATE in `sdlc-plan` (that gate validates minimum discovery before spec writing; this skill is unbounded exploration before any commitment)
