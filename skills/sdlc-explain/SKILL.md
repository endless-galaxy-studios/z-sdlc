---
name: sdlc-explain
description: >
  Explain a subject — an SDLC deliverable (spec, plan, result, idea brief, incident doc, audit, review),
  a module, a tradeoff, or an incident — as a self-contained HTML explainer with big pictures and few
  words: inline SVG from the design system, a hard word budget, real names and real values, every
  claim verified against the artifact or the code before it is drawn. Built for a reader who knows
  nothing about the subject to get the one load-bearing idea in one sitting. The eli5 command.
  Triggers on "/sdlc-explain", "/sdlc-render", "render this as HTML", "render the spec", "render the plan",
  "render the result", "make an HTML version", "/eli5 <topic>", "eli5", "explain like I'm 5",
  "explain like I know nothing about this", "big pictures and few words", "picture explainer",
  and explainer-shaped questions such as "how does this module work", "why did we make this
  tradeoff", "what caused this incident".
  Do NOT use for a paced, comprehensive, conversational read of an artifact before a gate — use sdlc-walkthru.
  Do NOT use for interactive tools, prototypes, or playgrounds — those are exploration artifacts, built directly.
  Do NOT use for editing markdown content — the MD file is the source of truth.
  Do NOT use for a question one paragraph settles — just answer it.
---

# Explain (eli5)

Produce a one-screen-at-a-time HTML explainer of one subject: big pictures, few words, nothing invented. The reader should be able to say the one load-bearing idea back after a single pass. Comprehension is the deliverable; the markdown, the code, and the decision record remain the sources of truth.

**Argument:** `$ARGUMENTS` — the subject. A deliverable path or reference ("the spec", "D5 plan"), a question ("how does the ranking module work", "why did we pick SSE over websockets", "what caused the 03-14 outage"), or a module path. If the invoking context just wrote the artifact, no argument is needed.

**Why this shape:** this skill began as `sdlc-render`, a faithful HTML view built as the reading aid for specs and plans. `sdlc-walkthru` now owns the comprehensive, paced read, so the HTML no longer needs to be faithful — it needs to be *understood*. Its spine is Thariq Shihipar's `eli5` plugin (`anthropics/claude-plugins-community`): "explain like I'm someone who knows nothing about this topic, using an HTML artifact with big pictures and few words." This skill adds subject resolution against the project's artifacts and code, verify-before-draw, and the framework's design system.

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## When This Applies

**Post-skill mode (opt-in):** After a skill writes a deliverable to `docs/current_work/`, it offers an explainer or a walkthrough. When CD accepts the explainer, build it with the document type's storyboard defaults — no further Q&A. This mode runs only on CD's acceptance, never unprompted.

**Manual mode (user-invoked):** CD invokes `/sdlc-explain <subject>`, `/eli5 <subject>`, or asks an explainer-shaped question. No scoping Q&A either — an explainer is one shot. The only question ever asked is a disambiguation when the subject could be two things.

Signs this skill is NOT appropriate:
- CD needs every load-bearing decision surfaced and wants to question and correct as they go → `sdlc-walkthru`
- CD needs to *manipulate* a mechanism (sliders, worked numbers, drag-to-prioritise) → an interactive exploration artifact, built directly per `sdlc-idea` / `sdlc-plan`
- The markdown itself needs changing → edit the MD file
- A paragraph answers it → answer it

## Visual Doctrine

Every explainer follows the framework's visual doctrine — **big pictures, few words** — defined once in `[sdlc-root]/process/html-rendering.md` § "Visual Doctrine: Big Pictures, Few Words". This skill is its purest application.

## Workflow

```
RESOLVE SUBJECT → VERIFY (read artifact / code) → FIND THE ONE THING
  → STORYBOARD (3–8 pictures, word budget) → DRAW (inline SVG) → WRITE → OPEN → REPORT
```

This is a direct-action skill. It does not dispatch agents — CC reads the sources and builds the explainer itself.

## Preconditions

- A subject that can be grounded in something real: a deliverable under `docs/`, code in the repository, a decision record, an incident doc, or the knowledge layer. A general concept ("how does DNS work") is allowed; ground it in the project's own stack wherever the project touches it.
- The design system at `[sdlc-root]/templates/html-design-system.html`.

## Steps

### 1. Resolve the subject

| Subject shape | Where the truth lives |
|---------------|------------------------|
| A deliverable path or reference | Resolve via `docs/_index.md` and `docs/current_work/`; read the whole artifact plus anything it cites (feasibility doc, decision log). Detect the document type from the path (`specs/` → spec, `planning/` → plan, `results/` → result, `ideas/*_idea-brief` → exploration, `ideas/*_handoff` → handoff, `audits/` → report, `incidents/` → incident, `docs/reference/` → reference, `docs/reviews/` → review; `sdlc-lite/` by `_plan` / `_result` suffix). |
| "how does this module / feature work" | The code itself — entry points, the main data path, the boundaries. Use LSP go-to-definition and find-references where available. |
| "why did we make this tradeoff / decision" | Specs and plans in `docs/current_work/` (Prior context tables, feasibility docs, decision logs), ADRs per `[sdlc-root]/process/adr-practice.md`, standing principles — consult `[sdlc-root]/knowledge/agent-context-map.yaml` for where they live — and `[sdlc-root]/process/sdlc_changelog.md`. For code whose reason none of those record, read `[sdlc-root]/knowledge/architecture/investigation-report-format.yaml` § explaining_why: start from the commits and pull requests behind the lines, and keep what a source states apart from what you infer. Draw only what a source states: show competing explanations as a decision card and an unrecorded reason as "not recorded", leave inferences and the before-a-change ending out of the pictures, and list the sources searched, empty ones included, in the footer. |
| "what caused this incident" | The incident doc in `docs/current_work/incidents/`, the fixing commits, and the code paths the timeline names. |

If the subject is ambiguous (two modules match, the "tradeoff" could be one of three), ask one question with `AskUserQuestion` per `[sdlc-root]/process/collaboration_model.md` § Tool Rule — never guess a subject and draw the wrong thing well.

### 2. Verify before drawing

Follow the Code Verification Rule in the project's CLAUDE.md for anything that touches code behaviour, and note where each claim comes from. For a deliverable, the artifact is the source for *what was decided*; the code is the source for *what is true today* — if they disagree, draw today's truth and flag the drift in the report. Never silently fix either. Keep a running list of sources (file paths, artifact sections, commits); it goes in the footer.

A picture that is wrong is worse than a paragraph that is right — pictures are believed.

### 3. Find the one thing

Write the single sentence the reader must retain even if they forget everything else. Twelve words or fewer. It becomes the title, and every picture must serve it. For a deliverable, it is usually the decision the artifact exists to make. If you cannot write it, you do not understand the subject yet — go back to step 2.

### 4. Storyboard

Plan before drawing. Budgets are the design, not a constraint on it:

| Budget | Limit |
|--------|-------|
| Pictures | 3 minimum, 8 maximum (a many-phase plan may go to 12, grouped into chapters with a one-line chapter title each) |
| Words per picture (caption + labels outside the SVG) | ≤ 40 |
| Words in the whole explainer, excluding the footer | ≤ 30 × picture count — the binding limit |
| Paragraphs | 0 — captions only |

The total is what binds; the per-picture figure is a ceiling. If the content does not fit, add a picture or a real value; never add words. If it needs more than the maximum, the subject is two subjects — split it and say so.

Order pictures the way a newcomer's questions arrive, not the way the document is laid out: **what is it → what goes in and comes out → what happens inside → what breaks, or what we chose instead → so what.** In post-skill mode, start from the document type's storyboard defaults in `[sdlc-root]/process/html-rendering.md` § Document-Type Storyboards, then bend them to the artifact's actual story. Pick a picture type per beat:

| Beat | Picture |
|------|---------|
| What is it / where it sits | Anatomy — one labelled box inside its neighbours |
| What flows through it | Flow — nodes and arrows, solid for sync, dashed for async |
| What happens inside | Zoom — the overview with one node opened up |
| What we chose instead | Tradeoff — options side by side, the chosen one accented, one gain and one cost each |
| What went wrong (incidents) | Timeline — discovery → cause → fix, the failing edge in danger colour |
| Before and after (results) | Two-column pair with the delta named |
| What is still open | Decision card — the question, the options, who decides |

Use real names from the artifact or code and real numbers from the logs or results. "The `score` column, 0–100" teaches; "a value" does not. **Open decisions and `USER DECISION NEEDED` markers always get a picture** — an explainer that hides an open decision is worse than no explainer.

### 5. Draw

- **Inline SVG only.** Follow the design system's diagram conventions (`.diagram-container`, node classes, rx=10, 1.5px neutral / 2px emphasized strokes, semantic colours: clay = focus, olive = success, danger = failure, info = external). No `<img>`, no Mermaid, no external CSS or JS.
- **Big.** One picture per screen: each picture spans the content width, and the picture plus its caption fill a laptop viewport without scrolling. Labels inside nodes at 16px or larger; the one-thing title at display size.
- **Gloss jargon inside the picture.** Any term a newcomer would not know gets a three-to-six-word annotation beside it. No glossary section, no footnotes.
- **Sequence.** Pictures stack vertically in storyboard order. An optional prev/next stepper (the design system's Slide Deck component and its `navigateDeck` script, no more) is the only JavaScript permitted.
- **Audience is not "dumb", it is new to this.** Engineers get the same explainer as anyone else; eli5 removes jargon, not rigour. If CD names an audience ("explain this for leadership"), it changes which beat leads and what the *so what* picture shows — not the budget, not the doctrine.

### 6. Write, open, report

- **Path.** For a deliverable subject, alongside the markdown with the same base name: `d01_feature_spec.md` → `d01_feature_spec.html` (a named audience appends a suffix: `_leadership`). For a question or module subject, `docs/current_work/explainers/{slug}.html`, creating the directory if needed, where the slug is a short form of the one thing.
- **Staleness.** If an HTML already exists at the target path, this is a regeneration: the footer shows "Updated" alongside the original generation date. See `[sdlc-root]/process/html-rendering.md` § Output Conventions for when a regeneration is owed.
- **Footer.** Generation timestamp, "Generated by sdlc-explain", and the sources consulted (file paths, artifact sections, commit SHAs). The footer is exempt from the word budget.
- **Open it:** `open <path>`.
- **Report in two lines:** the path, and the one thing. Add a third line only if verification found drift between a record and the code. In post-skill mode, one line confirming the HTML was written is enough.

## Output

One self-contained HTML file per explainer, inline SVG only, with a footer listing every source consulted. Deliverable explainers live beside their markdown; question explainers live in `docs/current_work/explainers/`. Explainers are working artifacts, not deliverables — never catalogued in `docs/_index.md`. An explainer informs an approval gate but is never approved *against*: the markdown is what gets approved.

## Validation Criteria

Before reporting, check all four:

1. Every claim in every picture traces to a source listed in the footer.
2. Word counts are within budget — count them, do not estimate; the total binds.
3. Every picture is inline SVG using design-system classes; the file has no external references.
4. Read it cold: a reader with no context could say the one thing back after one pass, and every open decision in the source has a picture.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I know how this works — I'll draw it from memory" | Verify-then-draw. Pictures are believed more than prose, so a wrong picture does more damage. Read the code, step through real values. |
| "It needs more words to be accurate" | Add a picture or a real value. The word budget is the design; if the idea does not fit, the storyboard is wrong, not the budget. |
| "I'll transcribe the spec's sections so nothing is lost" | Nothing-lost is the walkthrough's job and the markdown's job. An explainer that mirrors the document is the wall of text it exists to replace. |
| "A bulleted list is basically a picture" | It is prose in a costume. Draw the structure the list describes. |
| "I'll add a glossary at the end" | Gloss inside the picture, at the point of use. A glossary is a second document. |
| "Mermaid or a PNG would be faster" | Inline SVG only — self-contained, themeable through design-system tokens, editable by the next person. |
| "The reader is an engineer, so jargon is fine" | eli5 removes jargon regardless of audience. New to *this* is not the same as new to engineering. |
| "The source has no diagram, so this section gets none" | Picture-first is the explainer's job, not the author's. The markdown stays agent-clean; the explainer carries the pictures. |
| "This section has no shape — I'll add a picture anyway" | Decorative pictures are noise. If it cannot be drawn honestly, it does not get a picture; it gets a caption or nothing. |
| "The record says X, the code does Y — I'll draw the record" | Draw what the code does today, flag the drift in the report. Never silently fix either. |
| "The open decision is awkward to draw, I'll leave it to the markdown" | Open decisions always get a picture. Hiding one behind a lossy explainer is how it gets approved unseen. |
| "I'll add a custom colour that looks better here" | Design-system tokens only. Consistency across every explainer matters more than per-file aesthetics. |

## Integration

- **Depends on:** `[sdlc-root]/templates/html-design-system.html` (SVG diagram vocabulary and tokens), `[sdlc-root]/process/html-rendering.md` (visual doctrine, document-type storyboards, staleness and sharing conventions), the project's Code Verification Rule (in CLAUDE.md), `docs/_index.md` and `[sdlc-root]/knowledge/agent-context-map.yaml` (subject resolution).
- **Called by:** skills that write deliverables to `docs/current_work/`, when CD accepts their post-write offer (post-skill mode); CD directly (manual mode); `sdlc-walkthru` step 4 when a reader is circling one mechanism.
- **Feeds into:** the invoking skill's approval gate (the explainer resolves before the approval question, per `[sdlc-root]/process/html-rendering.md` § Post-Skill Offer), the sharing workflows in that doc's § Sharing; also onboarding and incident review.
- **Uses:** design-system tokens and diagram components, `AskUserQuestion` (ambiguous subject only), LSP where installed, `open`.
- **Complements:** `sdlc-walkthru` — same offer point, different consumption mode: the walkthrough is comprehensive and conversational; the explainer is a lossy picture artifact.
- **Does NOT replace:** `sdlc-walkthru` (nothing load-bearing omitted; feeds decisions at the gate), exploration artifacts built in `sdlc-idea` / `sdlc-plan` (interactive tools), `sdlc-debug-incident` (produces the incident record; this explains it), `sdlc-create-reference-doc` (durable reference).
- **DRY notes:** the visual doctrine and the document-type storyboards are defined once in `[sdlc-root]/process/html-rendering.md` and referenced here; SVG conventions live in the design system; verification lives in the Code Verification Rule. The only novel content here is subject resolution, the one-thing discipline, the storyboard budgets, and the beat → picture table.
