# Design Knowledge Store — Cross-Project

Knowledge for structured UX modeling during SDLC work. When a feature scope has been defined (often via competitive analysis), this knowledge guides an agent through understanding existing app context and producing UX artifacts that integrate coherently with what's already built.

## Structure

```
knowledge/design/
├── README.md                                    ← This file
├── ux-modeling-methodology.yaml                 ← Process an agent follows end-to-end
├── ascii-conventions.yaml                       ← Reusable ASCII diagramming conventions
├── accessibility-testability-principles.yaml    ← A11y and testability as a single concern
├── component-patterns.yaml                      ← UI component rules (icons, buttons, nav, modals, inputs, cards)
├── interaction-animation.yaml                   ← Interactive states, micro-interactions, animation easing
├── interaction-patterns.yaml                    ← Interaction design rules: states, animations, easing, gestures, feedback
├── visual-design-rules.yaml                     ← Color theory, palettes, dark mode, shadows, gradients
└── layout-principles.yaml                       ← Spacing, grid, structural layout principles
```

## How This Gets Used

1. A feature scope is defined (from `/feature-compare` output, stakeholder requirements, or spec)
2. An agent loads the methodology and examines the existing app (routes, components, IA)
3. Based on what needs modeling, the agent offers appropriate output format(s)
4. The product owner reviews the UX model before implementation begins

## Output Formats

| Format | Best For | Tool |
|--------|----------|------|
| ASCII diagrams | Navigation, page wireframes, IA sections | Inline markdown |
| D2 diagrams | IA site maps, user flows, component relationships | `d2` CLI → PNG/SVG |
| Figma prompts | Detailed UI specs for a designer to execute | Natural language |

D2 is used for structure diagrams (IA, flows) but NOT for wireframes — it lacks UI primitives. ASCII handles low-fi wireframes. Figma prompts handle high-fi specifications.

## Relationship to Other Knowledge Stores

- **`[sdlc-root]/knowledge/product-research/`** — produces the feature scope that feeds into UX modeling
- **`[sdlc-root]/knowledge/testing/`** — element catalogs and app maps provide existing-state context
- **`[sdlc-root]/knowledge/data-modeling/`** — data model shapes inform what entities the UI must represent

## Skill Trajectory

This knowledge feeds a future `/ux-model` skill that composes with `/feature-compare`:
```
/feature-compare "gantt chart"     → comparison + scoping questions
  ↓ (product owner answers)
/ux-model "gantt with [scope]"     → IA diagrams, wireframes, Figma prompts
  ↓
Normal SDLC: spec → plan → implement
```

## Maintenance

- Updated when UX modeling sessions reveal new conventions worth generalizing
- ASCII conventions grow as new component patterns are diagrammed
- D2 patterns and Figma prompt structures refined based on designer feedback
