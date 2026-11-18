# PROJECT-SECTION Markers

A convention for protecting project-specific content in **process and skill files** across migrations. Only applies to framework files that get overwritten during `sdlc-migrate`.

This document defines two marker types with opposite ownership: `PROJECT-SECTION` (project-owned content, preserved verbatim across migrations) and `BUNDLE-SECTION` (upstream-owned bundle fragments, discarded and re-injected fresh on every migration — see § BUNDLE-SECTION Markers below). A third, `MIRROR`, is not a migration marker at all — it tags upstream-owned verbatim copies of a process-doc section inside skills so drift can be checked mechanically (§ MIRROR Markers).

---

## When Markers Are Needed

Markers are required when adding project-specific content to **process docs** or **skill files** — these are framework files that `sdlc-migrate` overwrites from upstream.

| File Type | Needs Markers | Reason |
|-----------|---------------|--------|
| Process docs (`[sdlc-root]/process/*.md`) | Yes | Overwritten during migration |
| Skill files (`.claude/skills/*/SKILL.md`) | Yes | Overwritten during migration |
| Knowledge YAML (`[sdlc-root]/knowledge/**/*.yaml`) | No | Project-specific, not overwritten |
| Discipline parking lots (`[sdlc-root]/disciplines/*.md`) | No | Project-specific, not overwritten |
| Agent-context-map (`[sdlc-root]/knowledge/agent-context-map.yaml`) | No | Project-specific, not overwritten |

## Skills That Produce Marked Content

- `sdlc-develop-skill` (modify mode) — adds project-specific phases to framework skills
- `sdlc-audit` (improvement mode) — applies project-specific fixes to process docs
- `sdlc-migrate` — wraps detected customizations during migration (deviation detection)

---

## The Convention

Wrap project-specific content in paired markers that `sdlc-migrate` recognizes and preserves.

### Markdown Files

```html
<!-- PROJECT-SECTION-START: descriptive-label -->
... project content preserved across migrations ...
<!-- PROJECT-SECTION-END: descriptive-label -->
```

### YAML Files

```yaml
# PROJECT-SECTION-START: descriptive-label
... project content ...
# PROJECT-SECTION-END: descriptive-label
```

### Label Format

Labels must be descriptive and unique within the file. Use this pattern:

```
{origin}-{date}-{topic}
```

| Origin | When | Example Label |
|--------|------|---------------|
| `modify` | `sdlc-develop-skill` modifies a framework skill | `modify-2026-04-07-custom-gate` |
| `audit-improve` | `sdlc-audit` improvement mode applies a project-specific fix | `audit-improve-2026-04-07-env-check` |
| `deviation` | `sdlc-migrate` wraps detected customizations during migration | `deviation-2026-04-07-build-commands` |

---

## Rules

1. **Every START must have a matching END with the same label.** Orphaned markers are flagged by `sdlc-compliance-auditor` (Dimension 7).

2. **Labels must be unique within a file.** Duplicate labels cause ambiguity during extraction and re-injection.

3. **Markers must not nest.** A `PROJECT-SECTION-START` inside another `PROJECT-SECTION` block is malformed. Use separate, sequential blocks instead.

4. **Content inside markers is preserved verbatim.** `sdlc-migrate` does not modify, reformat, or merge content within markers — it extracts the block before overwriting and re-injects it afterward.

5. **Markers use the file's native comment syntax.** HTML comments (`<!-- -->`) for Markdown, hash comments (`#`) for YAML. Do not mix formats.

6. **Skills that produce project-specific content are responsible for adding markers at creation time.** This is a producing-skill obligation, not a migration-time responsibility. If content is created without markers, it can only be protected retroactively via deviation detection (§2.1c in `sdlc-migrate`).

### What Markers Can't Hold

A marked block adds project content beside upstream's; it can't stand in for upstream text. Three kinds of project edit have no marker form:

- **A replacement of upstream text.** Migration re-injects the block at its heading, next to the new upstream text, so both versions appear.
- **YAML frontmatter.** A comment marker can't sit inside it, so a project's change to a skill's description has nowhere to go.
- **Table rows.** A marker line between two rows breaks the table.

When such an edit fixes the framework's own text (a contradiction, a wrong path, a stale rule), its durable home is upstream. `sdlc-migrate` lists it under Upstream Candidates in its report (§4.6; §2.1c decides what goes there) for CD to send to z-sdlc; until a release carries it, the project re-applies it after each migration, where it shows as drift.

---

## BUNDLE-SECTION Markers

The inverse of `PROJECT-SECTION`: **upstream-owned** content injected into framework files only when an opt-in bundle is installed. Where `PROJECT-SECTION` protects project content from upstream overwrites, `BUNDLE-SECTION` lets a bundle hook into core framework files without those hooks shipping to projects that declined the bundle — and without the hooks freezing at whatever version was current at install time.

| | `PROJECT-SECTION` | `BUNDLE-SECTION` |
|---|---|---|
| Owner | The project | Upstream (the bundle's fragment file) |
| Present when | The project added it | The owning bundle is in `installed_bundles` |
| On migration | Extracted before overwrite, re-injected **verbatim** (after content review) | **Discarded and re-injected fresh** from the bundle's current fragment file |
| Hand-edits inside | Preserved | **Lost on next migration** — by design |

### Markers

```html
<!-- BUNDLE-SECTION-START: bundle-name/fragment-name -->
... injected verbatim from the bundle's fragment file ...
<!-- BUNDLE-SECTION-END: bundle-name/fragment-name -->
```

The label is `{bundle}/{fragment}` — the bundle's manifest name plus the fragment file's basename without extension (e.g., `github-provenance/sdlc-plan`). The slash-namespaced label is what distinguishes a `BUNDLE-SECTION` label from a `PROJECT-SECTION` label mechanically.

### Source of Truth

A bundle declares fragments in `skeleton/manifest.json` → `bundles.<name>.fragments`, a map of fragment source file → target framework file:

```json
"fragments": {
  "bundles/github-provenance/fragments/sdlc-plan.md": "skills/sdlc-plan/SKILL.md"
}
```

The fragment file in the z-sdlc source IS the content; the injected block in the target file is a projection of it. To change what installed projects see, change the fragment file upstream — the next migration propagates it. Installers record every injected fragment in `.sdlc-manifest.json` → `bundle_fragments` (label → target path) so the compliance auditor can verify presence without reaching the z-sdlc source.

### Rules

1. **One fragment per (bundle, target file).** A bundle that needs two additions to the same file puts them in one fragment.
2. **Injection is strip-then-append.** Remove any existing block carrying the same label — the markers, the content between them, **and any blank lines immediately preceding the start marker** (the separator blank line the previous injection added; leaving it behind accretes whitespace on every re-run) — then normalize the file to end with a single newline and append one blank line, the start marker, the fragment content, and the end marker. Re-running injection is idempotent — byte-identical output.
3. **Deterministic order.** When multiple bundles target the same file, blocks are appended in alphabetical bundle-name order.
4. **No nesting or overlap.** A `BUNDLE-SECTION` may not contain or intersect a `PROJECT-SECTION` or another `BUNDLE-SECTION`. Fragments are self-contained end-of-file sections.
5. **Never hand-edit inside the markers.** Project customizations to bundle behavior go in a separate `PROJECT-SECTION` block (or upstream, as a fragment change). Anything written inside a `BUNDLE-SECTION` is silently replaced at the next migration.
6. **Presence must match `installed_bundles`.** A `BUNDLE-SECTION` block in a project without the owning bundle installed — or an installed bundle with declared fragments missing from their targets — is a Dimension 7 finding (partial install; re-running the bundle install or migration repairs it).
7. **Fragment injection counts as a file write.** When an adapter plugin declares `post-file-write`, the adapter's transformation runs on the target file **after** injection (or re-runs, if the file was already transformed this pass) — fragment content may contain knowledge-layer references that the adapter must transform like any other framework content.

### Installer Ordering

Copy the bundle's files → inject its fragments → record the bundle in `installed_bundles` and its fragments in `bundle_fragments` **last**. A crash mid-install then under-claims rather than over-claims: the manifest never lists a bundle whose hooks are missing, and a re-run (or the next migration) completes the injection idempotently.

---

## MIRROR Markers

Upstream-owned **verbatim copies** of a process-doc section, carried inline in skills so a critical step is never reduced to a skippable pointer. The users are the two review-loop critical-steps blocks defined in `[sdlc-root]/process/review-fix-loop.md` § Mirrored Critical-Steps Blocks, the headless stop rule in `[sdlc-root]/process/headless-mode.md` § Mirrored Stop Rule, which every skill carries, and the Approval Brief procedure and Completion Report in `[sdlc-root]/process/writing-for-cd.md` § Mirrored Blocks, which the planning and execution skills carry.

```html
<!-- In the source process doc -->
<!-- MIRROR-SOURCE-START: section-id -->
... the canonical block ...
<!-- MIRROR-SOURCE-END: section-id -->

<!-- In each skill that carries a copy -->
<!-- MIRROR-START: source-file.md#section-id -->
... identical lines ...
<!-- MIRROR-END: source-file.md#section-id -->
```

The label names its source: `{process-file}#{section-id}`, where `{process-file}` resolves to `[sdlc-root]/process/{process-file}`.

### Rules

1. **Identical content.** The lines between `MIRROR-START`/`MIRROR-END` must be byte-identical to the lines between the matching `MIRROR-SOURCE-START`/`MIRROR-SOURCE-END`. Any difference is a drift finding — `sdlc-reviewer` (§ Cross-skill DRY) and the framework's cross-skill DRY audit check it.
2. **Edit the source, then re-copy.** Never edit a copy in place. Context-specific wording goes outside the markers.
3. **Exempt from DRY extraction.** Mirrored blocks are deliberate duplication; DRY checks do not recommend extracting them — they check that they match.
4. **Not migration markers.** `sdlc-migrate` matches only the literal `PROJECT-SECTION-*` and `BUNDLE-SECTION-*` names, so `MIRROR` blocks pass through as ordinary upstream content: the upstream skill copy (with its current block) overwrites the old one. A project must not hand-edit a mirrored block; project additions go in a `PROJECT-SECTION` outside it.
5. **No nesting.** A `MIRROR` block may not contain or intersect a `PROJECT-SECTION` or `BUNDLE-SECTION`.
6. **Prose never spells a live marker.** The drift check finds blocks by matching marker text, so marker-shaped prose is read as a marker. In a source doc, describe its markers with `{id}` (`MIRROR-SOURCE-START: {id}`), never the literal id: a prose line carrying the literal marker starts the range early and reports false drift. In a skill, do not write the copy-marker form with a file name at all (`MIRROR-START:` followed by `file.md#`); name the markers and give the file and id separately.

---

## How Migration Uses Markers

### Direct Copy Files (§2.1)

1. Before overwriting, extract all `PROJECT-SECTION` blocks with their labels and heading context
2. **Review each block against upstream changes (§2.1d):**
   - Compare the upstream section at `source_version` vs `HEAD`
   - Classify: OK, REVIEW (significant changes), ORPHAN (section removed), OPPORTUNITY (new patterns), CONFLICT (contradicts upstream)
   - Present non-OK findings to user with options: keep, update, remove, merge
3. Copy the upstream file (overwriting the project's version)
4. Re-inject each block at its original heading position (unless user chose to update/remove)
5. If the heading no longer exists upstream, append at end with a warning comment
6. Inject `BUNDLE-SECTION` fragments for installed bundles targeting this file (strip-then-append from the z-sdlc source at the target release — no content review; these blocks are upstream-owned)

### Content-Merge Files (§2.2–2.4)

1. **Review marked blocks against upstream changes (§2.1d)** — same classification and user presentation
2. Framework sections outside markers are updated to match upstream
3. Markers are never moved, split, or merged automatically — but user can choose to update content during review
4. Inject `BUNDLE-SECTION` fragments for installed bundles targeting this file, exactly as in the direct-copy flow — most fragment targets are content-merged skills, so this path must run the injection pass too

### Deviation Detection (§2.1c)

1. Before direct-copying, diff the project's version against the previous upstream version
2. If the project modified content outside existing markers, present the customizations
3. User can choose to: wrap in markers (preserve), overwrite (discard), or skip the file

---

## Validation

The `sdlc-compliance-auditor` validates marker integrity as part of Dimension 7 (Migration Integrity):

- Every `START` has a matching `END` with the same label
- No orphaned `END` without a `START`
- No mismatched labels between paired markers
- Correct comment syntax for the file type
- `BUNDLE-SECTION` blocks only where the owning bundle is in `installed_bundles`, and every fragment recorded in `bundle_fragments` present in its target file (both directions of the presence rule)
- No nesting between `BUNDLE-SECTION` and `PROJECT-SECTION` blocks

The `sdlc-reviewer` recognizes markers when reviewing skills and agents:

- Does not flag content inside `PROJECT-SECTION` / `BUNDLE-SECTION` markers as convention violations
- Checks every `MIRROR` block is identical to its source section (§ MIRROR Markers)
- Verifies markers are well-formed if present
- Flags malformed markers as minor findings

---

## What Markers Are NOT

- **Not a way to opt out of upstream changes.** Framework sections outside markers are still updated by migration. Markers protect additions, not overrides.
- **Not version control.** Markers don't track history — they mark boundaries. Use git for history.
- **Not a substitute for upstream contribution.** If a project-specific change would benefit all projects, propose it upstream rather than wrapping it in markers permanently.
- **Not a guarantee of permanent preservation.** Migration reviews marked content against upstream changes (§2.1d). If upstream significantly changed the surrounding context, the user is prompted to review — they may choose to update, merge, or remove the marked content. Markers protect from silent overwriting, not from becoming stale.
