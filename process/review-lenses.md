# Review Lenses

Analytical perspectives that agents apply when reviewing code. Each consuming skill specifies which lenses are relevant to its context.

## Lens Applicability by Skill

| Skill Context | Applicable Lenses |
|--------------|-------------------|
| Code review (`sdlc-review-code`) | All lenses |
| Execution review loop (`sdlc-execute`, `sdlc-lite-execute`, direct dispatch, the factory's `sdlc-implement` and `sdlc-revise`) | All lenses |
| Test gap analysis (`sdlc-tests-create`) | Coverage, security at boundaries, contract safety, performance, data integrity, standard |
| Agent/skill creation (`sdlc-develop-agent`, `sdlc-initialize`) | Standard only |

**Frontend-conditional lenses:** UX Regression, Accessibility, and State Completeness apply only when the diff touches user-facing code (components, pages, styles, templates). API Ergonomics applies when the diff introduces new public interfaces (endpoints, exported functions, component props). Agents should skip these lenses entirely for backend-only or infrastructure changes.

---

## Primary Lens — Overengineering and Unnecessary Code (review only)

- Abstractions that serve only one call site
- Helper functions or utilities for one-time operations
- Configuration or options that could just be hardcoded
- Error handling for scenarios that can't happen in context
- Feature flags, backward-compatibility shims, or future-proofing for hypothetical requirements
- Added types, interfaces, or enums that aren't needed yet
- Comments that repeat the code, a name or the types, narrate the change, or keep commented-out code (the rule: `[sdlc-root]/knowledge/coding/comment-discipline.yaml`)
- Defensive checks that duplicate what the framework already guarantees
- Replacement of a working component with a new, larger implementation when extending the existing component would suffice — a 15-line component that works correctly replaced by a 170-line component that introduces bugs is not an improvement. Every replacement must justify what the existing code cannot do that requires starting over rather than adding to it

## Type Safety Lens (review only)

- `as` type casts that bypass the compiler instead of fixing the underlying type
- `any` types that erase safety (especially in function parameters or return types)
- `!` non-null assertions that hide potential undefined values
- Optional chaining (`?.`) that silently swallows undefined instead of failing at a clear boundary — particularly in data paths where undefined means a real bug, not an expected absence

## Suppressions Lens (review only)

- A lint, type or security suppression the diff adds, or one on a line the diff changes (such as `eslint-disable`, `@ts-ignore`, `# noqa`, `# type: ignore`, `# nosec`, `//nolint`): look up the rule it silences. If the rule catches bugs or guards security, the suppression is a finding unless the line says why the rule is wrong here. The fix is the code the rule objects to; where the rule really is wrong here, the fix is a reason written beside the suppression, which stays as it is. Category `suppression`; `major` when the rule guards security, otherwise `minor`.
- A suppression of a style or formatting rule is fine.
- A suppression that could name its rule and doesn't (a bare `# noqa`, `# type: ignore`, `//nolint` or `eslint-disable`), or one covering a whole file (`@ts-nocheck`, a top-of-file `eslint-disable`), hides every later instance too: a finding. `@ts-ignore` and `@ts-expect-error` take no rule: ask for a reason, and prefer `@ts-expect-error`, which fails once the error is gone.
- Suppressions already in a touched file that the diff doesn't add or change are out of this change's scope: note them once, and fix none. `sdlc-audit` health mode counts them across the codebase.
- A tool reads every suppression, so it is never reworded as prose (`[sdlc-root]/knowledge/coding/comment-discipline.yaml`, Machine-read). For shell scripts, read `[sdlc-root]/knowledge/coding/shell-patterns.yaml` § fixing_vs_suppressing.

## Security at Boundaries Lens

- User-supplied strings rendered without sanitization
- Raw HTML injection via escape hatches in components that render external data
- Database writes that accept user input without validating shape or size
- URL construction from user input without encoding
- Parser inputs that could contain injection payloads

## Contract Safety Lens

- Changes to shared types in shared packages — did all consumers get updated?
- State store shape changes — are all selectors and subscribers still reading valid paths?
- Enum additions or removals — are switch/case handlers and maps exhaustive?
- Function signature changes in shared utilities — are all call sites passing the right arguments?
- Consumers a symbol search won't find (review only) — the JSON an API returns, stored formats and database columns, wire formats, another service or language reading the same bytes, feature flags and config keys, code several calls downstream. Check those, not only the callers grep lists.
- The fact the change is safe because of (review only) — most risky-looking changes are safe because of one fact ("this only drops cache entries that are already dead"). Name it, and how far it is proven: stated, pointed at a `file:line`, walked through the failure, run against the real code by a script or test, or reproduced in the running app. When a shared-contract change rests only on a statement or a cited line and a short script against the real code could settle it, raise an INVESTIGATE finding (category `contract`) asking for the script: `minor`, or `major` when the unproven fact guards data, auth or money. It closes with the script's command and output in the finding's rationale and the re-review prompt, or with a test added to the diff. Say what stays unproven; not every change needs a reproduction in the app.
- Manually-synced parallel copies — a "KEEP IN SYNC" / "must match X" / "kept in sync manually" comment is itself a defect, not a mitigation. The duplication must be replaced by a single source of truth (one copy derives from the other, or both derive from shared code/config) or covered by a drift-detection test that fails when the copies diverge. Flag the comment even when the copies currently match — the observed failure mode is copies diverging in the very commit that adds the comment. A grep-based CI check on these comment markers is a legitimate enforcement floor (`[sdlc-root]/process/guardrail-lifecycle.md` § Enforcement Floors).

## Performance Lens

- N+1 queries — loading related objects in a loop instead of eager loading or joining
- Missing pagination on list endpoints — unbounded result sets that grow with data
- Unnecessary re-renders from unstable references, inline object literals in props, or missing memoization
- Database queries missing indexes on filtered/sorted columns, especially in hot paths
- Unbounded loops or recursive calls without depth limits
- Large payloads returned when only a subset of fields is needed
- A performance number in the change or its description (review only) — a before and after, a benchmark, a regression — that doesn't answer the questions in `checking_a_number`. A labeled one-run ballpark passes, and the runs can sit in a linked file. Read `[sdlc-root]/knowledge/architecture/performance-optimization-philosophy.yaml` § checking_a_number for the questions, when the project has that file.

## Data Integrity Lens

- Missing database constraints that allow invalid state (e.g., nullable FK that should be required, missing unique constraint on a business key)
- Race conditions in concurrent writes — two requests modifying the same row without optimistic locking or serializable isolation
- Transaction boundary violations — work split across multiple commits where partial failure leaves inconsistent state
- Orphaned records — deletes or status changes that leave related rows pointing to nothing
- Enum/status values stored as strings without validation — any string can be written, not just valid states

## Coverage Lens (test gap analysis)

- End-to-end workflows that cross function boundaries — is the full chain tested, or just individual pieces?
- State machine transitions — are all valid status changes exercised, including edge cases (recovery, reactivation, out-of-order events)?
- Error handling paths that affect user-visible behavior — do tests cover what happens when external services fail, input is invalid, or preconditions aren't met?
- Integration points — are external API calls, DB transactions, and job queue interactions tested with realistic mocks or real systems?
- Auth and permission boundaries — are role guards, JWT-only requirements, and IDOR prevention tested at the endpoint level?

## UX Regression Lens (review only)

- Existing user affordances removed without replacement (visible labels replaced by icons, text buttons replaced by unlabeled icon buttons)
- Interactive elements relocated without maintaining discoverability (filters moved but old location not cleaned up, nav items hidden behind new interaction patterns)
- Scroll-accessible controls that lose accessibility on scroll (non-sticky sidebars, toolbars, or filter panels that scroll away with content)
- Contrast or visibility regressions (new elements with insufficient contrast against their background, ghost-variant buttons on dark surfaces)
- Phased work that adds a replacement without removing the original (duplicated filters, duplicated nav items, parallel controls for the same function)

## Accessibility Lens (review only)

- Focus management — modals, drawers, and dynamic content trap focus correctly; focus returns to trigger on close; no focus lost to `<body>` after interaction
- Keyboard navigation — all interactive elements reachable via Tab; logical tab order; custom widgets implement expected key patterns (Arrow keys for menus, Escape to close)
- ARIA semantics — roles, states, and properties match the widget's actual behavior; live regions announce dynamic content changes; labels are descriptive, not implementation-derived
- Screen reader flow — content order in DOM matches visual order; headings create a navigable hierarchy; decorative elements are hidden from assistive tech
- Color and contrast — text meets WCAG AA (4.5:1 for normal, 3:1 for large); interactive element boundaries distinguishable without relying solely on color; focus indicators visible against all backgrounds

## State Completeness Lens (review only)

- Loading states — does every async operation show loading feedback? Can the user tell something is happening?
- Error states — when a request fails, what does the user see? Is there a recovery path (retry, go back, clear and restart)?
- Empty states — what renders when the data set is empty? Is there guidance on what to do next, or just a blank void?
- Partial/stale data — after optimistic updates, what happens on rollback? After cache expiration, does the UI show stale data without indication?
- Scroll and overflow states — do panels, lists, and content areas behave correctly when content exceeds the viewport? Do sticky elements stay accessible? Do scroll containers clip content or controls?
- Concurrent interaction — what happens on double-click, rapid navigation, or interaction during pending state transitions?

## API Ergonomics Lens (review only)

- Naming — do new function names, component props, endpoint paths, and parameters communicate intent? Would a consumer unfamiliar with the implementation guess correctly what they do?
- Consistency — do new interfaces follow the same patterns as existing ones in the codebase? (e.g., if existing list endpoints use `?page=&limit=`, a new one shouldn't use `?offset=&count=`)
- Pit of success — is it hard to misuse the API? Required parameters before optional ones; invalid states unrepresentable in the type system; sensible defaults that don't surprise
- Surface area — does the interface expose only what consumers need? Internal implementation details leaking into public props, return types, or endpoint responses indicate a missing abstraction boundary

## Architecture Guardrail Lens (review only)

- Module boundary health — are responsibilities bleeding across module or package boundaries? A utility importing from a feature module, a component reaching into another feature's store, or a shared package depending on an app-specific one are all boundary violations
- Dependency direction — imports should flow downward (features → shared → core). Upward or lateral dependencies between peer features create hidden coupling that makes changes cascade unpredictably
- Pattern consistency — when the codebase has an established way to do something (state management, API calls, data fetching, error handling), new code should follow it or explicitly justify the divergence. Silent pattern drift creates two ways to do the same thing, confusing future contributors
- Extraction signals — a file, function, or component that has grown to handle multiple concerns is due for extraction. Watch for: functions with multiple unrelated branches, components with 3+ responsibilities, files that are the "go-to dumping ground" for new logic in their area
- Abstraction fitness — every abstraction (wrapper, provider, adapter, base class) must justify its existence by serving 2+ consumers or encapsulating genuine complexity. Abstractions that pass through without transforming, or that serve exactly one call site, are premature and add navigation cost without value
- Scope creep in changes — does the diff stay within its stated intent? A bug fix that also reorganizes imports, adds a utility, and refactors an adjacent function has expanded beyond its scope. Each concern should be a separate change

## ADR Drift Lens (review only, skip-if-absent)

Skip this lens entirely if `docs/architecture/decisions/` does not exist in the project. When the directory exists:

- For each active ADR relevant to the changed files, verify the change does not violate the ADR's decision. Flag violations as `major` with category `adr-drift`.
- Intentional supersessions require a matching supersession ADR staged in the same diff. A code change that contradicts an active ADR without a co-committed supersession ADR is itself an `adr-drift` finding.
- ADRs are immutable — edits to a prior ADR's Decision or Rationale sections (rather than writing a new superseding ADR) are `major` with category `adr-drift`.

See `[sdlc-root]/process/adr-practice.md` for conventions and contradiction handling.

## Standard Lens — Always Applied

- DRY violations (duplicated logic that should be shared)
- Architecture adherence (domain adapter pattern, state management conventions, import rules, file conventions per CLAUDE.md)
- Correctness (logic errors, off-by-one, missing edge cases)
- Naming and consistency with codebase conventions
- Test quality: each new or changed test passes the two-edit check (it fails when the behavior breaks and survives a change to the internals), and a bug-fix test has a recorded failing run on the unfixed code (`[sdlc-root]/knowledge/testing/testing-paradigm.yaml` § two_edit_check)
