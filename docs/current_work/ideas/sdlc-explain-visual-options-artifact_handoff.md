---
type: handoff
slug: sdlc-explain-visual-options-artifact
created: 2026-10-03
status: pending: nothing built (cross-checked 2026-11-25)
trigger: idea
recommended_next_skill: sdlc-develop-skill
source_session_summary: "Choosing between two UI designs in a project; CD asked for both shown side by side and liked how the generated preview page turned out"
active_deliverable: null
related_files:
  - skills/sdlc-explain/SKILL.md
  - skills/sdlc-render/SKILL.md
  - skills/sdlc-walkthru/SKILL.md
  - process/html-rendering.md
---

# Handoff: Teach `sdlc-explain` to produce side-by-side option previews

## Progress (cross-checked 2026-11-25)

Nothing here has been built, and the open questions are undecided.
- **A related file is gone:** `skills/sdlc-render/SKILL.md` became `sdlc-explain` on 2026-09-22.
- **The nearest existing feature:** `sdlc-design-consult`, which makes one mockup per option, at the target surface's viewport, from placeholder content. It's the obvious candidate home for the "new mode or separate skill?" question.
- **What's missing everywhere:**
  - real project material;
  - a caveats list;
  - dark mode (the HTML design system has no `prefers-color-scheme`);
  - private publishing.

## Why this is a handoff

A session in a project running z-sdlc was deciding between two designs for a small piece of UI. CD asked to see both, liked how the generated preview page turned out, and asked for `sdlc-explain` to produce pages like it. The source session couldn't read `sdlc-explain` (it wasn't installed there), so everything below describes what the preview page did, not what the skill does today. Read `skills/sdlc-explain/SKILL.md` first and compare.

## What needs to happen

When CD is choosing between visual or UI options, `sdlc-explain` produces a preview page instead of describing the options in text. The qualities CD liked:

- **Both options on one page, side by side,** each with a plain name and a one-line "what you give up, what you get" subtitle, so they compare without scrolling between messages.
- **Real project material, not placeholders:** the project's own images (resized and embedded, so the page stands alone) and the product's real wording. Nothing invented.
- **Real size and real context:** each option at the true width of the component it would appear in, on a stand-in background, so "too long for a small screen" is visible instead of argued.
- **A short caveats list under the options,** naming what the mockup leaves out or approximates, so the page stays honest.
- **Plain, specific copy:** short sentences, no jargon, no code names.
- **Light and dark, and phone width:** colors from tokens, an explicit page background, one column when narrow.
- **Published as a private page with a link,** with no product code changed to produce it, and a short chat reply: what's being decided, the options, things to know, then the decision needed.

Open design choice: is this the default for every explanation, or only for visual and UI decisions? Recommended: only when two or more concrete visual options exist and the choice is CD's.

## Evidence

- **Closest existing skills:** `skills/sdlc-explain/SKILL.md` (the target), `skills/sdlc-render/SKILL.md` (renders finished Markdown deliverables to HTML) and `skills/sdlc-walkthru/SKILL.md` (a paced read of an artifact). Neither produces option comparisons from real project assets.
- **Closest existing convention:** `process/html-rendering.md` § Two Categories of HTML already describes exploration artifacts, such as side-by-side comparisons, as throwaway working tools. The preview page is a concrete example of that category.
- **How such a page can be built:** images resized (to about 72px tall there) and base64-embedded into one HTML file from a template with `{{asset}}` placeholders, then published as a private page following the host's page-design guidance (tokens on `:root`, dark-mode blocks, no external assets).

## Recommended next step

Open a session in this repo and run **`/sdlc-develop-skill`** (MODIFY mode) on `sdlc-explain`, with this file as the seed. It's a change to an existing skill, and the modify mode handles the framework and project section markers and the DRY check against `sdlc-render` and `sdlc-walkthru`.

## Open questions

- What does `sdlc-explain` do today? Its description covers single-subject explainers with a word budget. Is option comparison a new mode, or a separate skill?
- Or should it hook into `sdlc-idea`'s exploration artifacts, which `html-rendering.md` already covers?
- Should the skill require real assets when they exist, and say what to do when they don't (label placeholders clearly)?
- Hosting: should the skill fall back to a local HTML file in `docs/current_work/` when no page-publishing tool is available?
- Where does the caveats list come from, so it stays honest and is never left empty out of habit?

## Out of scope

- Rewriting `sdlc-render`'s design system or document-type profiles.
- Changing any output style.
