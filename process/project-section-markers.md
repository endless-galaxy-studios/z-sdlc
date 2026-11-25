# PROJECT-SECTION Markers

A convention for protecting project-specific content in **framework files** across migrations: process docs, skills and their references, knowledge YAMLs, and the SDLC sections of `CLAUDE.md`.

**A project marks every deliberate change it makes to a framework file, and migration follows the marks** (CD, 2026-11-20). An addition, a replacement of upstream text and a removal each have a mark (§ The Three Kinds of Change). Everything unmarked follows upstream: before upstream replaces an unmarked difference, `sdlc-migrate` shows it and asks whether to mark it (§2.1c deviation detection), so nothing is lost silently. Migration never guesses intent from a diff: a diff against the project's last release finds a change but can't say it was meant (and without that baseline, a key the project deleted looks exactly like one upstream added). A mark says so once, for every migration after.

This document defines two marker types with opposite ownership: `PROJECT-SECTION` (project-owned content, preserved verbatim across migrations) and `BUNDLE-SECTION` (upstream-owned bundle fragments, discarded and re-injected fresh on every migration — see § BUNDLE-SECTION Markers below). A third, `MIRROR`, is not a migration marker at all — it tags upstream-owned verbatim copies of a process-doc section inside skills so drift can be checked mechanically (§ MIRROR Markers).

---

## When Markers Are Needed

Markers are required for any deliberate change to a file `sdlc-migrate` updates from upstream:

| File Type | Needs Markers | Reason |
|-----------|---------------|--------|
| Process docs (`[sdlc-root]/process/*.md`) | Yes | Overwritten during migration |
| Skill files and their references (`.claude/skills/*/`) | Yes | Overwritten or content-merged during migration, dual-audience skills included |
| Knowledge YAML (`[sdlc-root]/knowledge/**/*.yaml`, except the agent-context-map) | Yes, for upstream entries | Upstream's entries merge from upstream (§2.1b): a project's edit or removal of one is marked. A key or list item upstream never had is the project's, marked or not |
| `CLAUDE.md`'s SDLC sections | Yes | Merged from `CLAUDE-SDLC.md` (§2.1e) |
| Disciplines (`[sdlc-root]/disciplines/*.md`) | Yes, for framework sections | Their framework sections merge from upstream (§2.3), so a change to one is marked. Their project data needs none: the `## Parking Lot` entries and triage markers, `## Project Context`, `## Active Questions`, and the Process Maturity Tracker block |
| Agent-context-map (`[sdlc-root]/knowledge/agent-context-map.yaml`) | No | Project-specific, not overwritten |

A value a framework file leaves for the project to set is the project's by design and needs no mark: a filled `[build command]`-style placeholder (a build, test or start command, a health-check URL), the project's agent name where the framework names a canonical one, a resolved `[PLUGIN: ...]` guard, a knowledge file's `spec_relevant`. Text an adapter plugin writes is the adapter's, under its phrasing contract. Every other difference from upstream is a change, and is marked.

## Skills That Produce Marked Content

- `sdlc-initialize` — marks the knowledge files it customizes for the project's stack (a replacement of `` `*` ``) and the dispatcher table entries it adds
- `sdlc-develop-skill` (modify mode) — adds project-specific phases to framework skills
- `sdlc-audit` (improvement mode) — applies project-specific fixes to process docs; its Deep Verify demotion removes knowledge entries, each with a removal mark
- `sdlc-ingest` — adds knowledge entries, and marks any upstream entry it rewrites
- The factory's code stages (`sdlc-implement`, `sdlc-revise`) — correct knowledge entries a change makes wrong, marking an upstream entry they change or remove
- `sdlc-migrate` — wraps detected customizations during migration (deviation detection)

Anyone editing a framework file by hand does the same.

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

## The Three Kinds of Change

| Kind | Mark | What migration does |
|---|---|---|
| **Addition** | A `PROJECT-SECTION-START: <label>` … `PROJECT-SECTION-END: <label>` block | Keeps the block beside upstream's text, at its heading |
| **Replacement** | The same block, its start line naming what it replaces: ``PROJECT-SECTION-START: <label> replaces `<target>` `` | Leaves the target out of upstream's text and keeps the block in its place |
| **Removal** | One line: ``PROJECT-SECTION-REMOVED: <label> `<target>` — <why>; <who>, <date>`` | Leaves the target out of upstream's text, and keeps the line |

For a replacement or a removal, migration also shows what upstream changed in the target since the project's last migration (§2.1d), so an upstream fix to something the project set aside is never missed. A target that upstream no longer has is an ORPHAN: migration shows it beside the heading or key upstream most likely renamed it to, and CD re-points the mark or drops it. One upstream never had (a mark on the project's own entry) is dropped quietly and logged.

### Target Grammar

A target is quoted in backticks, in both forms; one that itself holds a backtick is quoted in double backticks, as Markdown does.

- **Markdown:** a heading, written as upstream writes it, hashes included (`` `### 3. Find how the project runs its specs` ``). The target is that heading's section: the heading and everything up to the next heading at its level or above, counting only headings outside code fences. A heading upstream's file has more than once can't be named alone: mark the section around it instead.
- **YAML:** a key, as a dotted path from the top level (`` `error_design` ``, `` `assignment_rules.ai_ml_provisioning` ``), or one item of a key's list of mappings, named by a field whose value only that item has (`` `gotchas[id=playwright-cli-open-url]` ``, `` `internal_doc_authoring.rules[rule_id=WGX7]` ``). Any such field names it; a writer uses the first of `id`, `rule_id`, `key`, `name` that's unique in the list, else another field that is (`` `anti_patterns[pattern=sleep-for-sync]` ``). A list with no unique field is named by its key.
- **The whole file:** `` `*` ``. A replacement of `` `*` `` wraps the whole file, after its frontmatter if it has one (frontmatter stays upstream's), and the project's file stands in for upstream's; migration still shows upstream's changes to the file for review. A file the project deleted can't hold its own mark: its removal is recorded in the manifest instead (§ Deleted Files).

Targets don't overlap: a mark inside a section another mark replaces or removes is malformed, since the outer mark already covers it. Name the smallest target the change needs: a sentence's section, a nested key, one item, so upstream's later changes reach the rest.

**What a target holds, and what's upstream's around it:**
- A YAML target runs from its key or `- ` line to the next one at its level or above, less the comment and blank lines just above that next one: those belong to what follows. Comment lines outside marks, and separators between Markdown sections (`---`, blank lines), are upstream's text and follow upstream.
- YAML units are compared by their parsed values, not their comments or their order. The merged file keeps upstream's order; a project's own unit, or a marked block, stays after the unit it followed in the project's file. A removal line sits where its target's first line was.
- A knowledge file's `last_updated` takes the later of the project's and upstream's dates, and needs no mark.
- A project's own entry in an upstream list takes an id upstream won't reach, with a project prefix (`P-VD1`, not upstream's next `VD23`): an id both sides add is a conflict migration has to ask about.

### Deleted Files

A framework file the project doesn't want is deleted and recorded, never just deleted. `.sdlc-manifest.json` → `declined_files` maps its installed path to why, and who decided when:

```json
"declined_files": {
  "ops/sdlc/knowledge/architecture/payment-state-machine.yaml": { "why": "no payment features", "decided": "CD, 2026-11-20" }
}
```

- **Who writes it:** `sdlc-initialize` when CD removes a knowledge file that doesn't apply (6a), `sdlc-migrate` when CD keeps a deleted file deleted (its §2.1c), and anyone who deletes a framework file by hand, in the same change. A framework file missing without a record is asked about at the next migration, once: keep it removed (recorded) or restore it. The exception is a file an adapter took into its backend when the knowledge layer is the adapter's (`sdlc-migrate` Pre-Flight Check, Step 2): it is never asked about or recorded.
- **What migration does:** never copies a declined file back, never asks about it, and never wires it into the agent-context-map. When upstream changes one, the report lists it. CD takes one back by removing its entry: the next migration then asks, and restores it. Keys are installed paths; the release's paths map to them per `[sdlc-root]/process/path-mappings.md`. When upstream moves it, the record moves to the new path; when upstream deletes it, the record goes, logged.
- **Scope:** the files `skeleton/manifest.json` lists in `source_files` (skills and their files, agents, process docs, templates, knowledge, disciplines, plugin guides, playbooks). A bundle is declined whole, by not being in `installed_bundles`.
- A declined path that exists on disk again is a finding (Dimension 7), and migration asks whether to take it back.

**Marks inside code fences are examples.** Migration's extraction, `sdlc-compliance-auditor` and `sdlc-reviewer` skip every mark between a pair of ```` ``` ```` fence lines, so a document can show marks, as this one does. Only a whole-line mark is live (rule 8).

```html
<!-- PROJECT-SECTION-START: modify-2026-11-20-our-launch replaces `### 3. Launch` -->
### 3. Launch
... the project's own version ...
<!-- PROJECT-SECTION-END: modify-2026-11-20-our-launch -->
<!-- PROJECT-SECTION-REMOVED: audit-improve-2026-11-20-no-mobile `## Mobile Checks` — this project has no mobile client; CD, 2026-11-20 -->
```

```yaml
# PROJECT-SECTION-REMOVED: demote-2026-07-13-error-design `error_design` — factual errors (Deep Verify sweep); CD, 2026-07-13
# PROJECT-SECTION-REMOVED: demote-2026-07-13-pw-open `gotchas[id=playwright-cli-open-url]` — not reproducible; CD, 2026-07-13
# PROJECT-SECTION-START: modify-2026-11-20-pagination replaces `pagination`
pagination:
  ... the project's version ...
# PROJECT-SECTION-END: modify-2026-11-20-pagination
```

A YAML mark is a comment, so only a text edit keeps it: never round-trip a knowledge file through a YAML parser and dumper (`.claude/skills/sdlc-audit/references/deep-verify.md` has a comment-preserving removal script).

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
| `demote` | `sdlc-audit`'s Deep Verify removes a knowledge entry | `demote-2026-07-13-error-design` |
| `fix` | A factory stage or a person corrects or removes an upstream knowledge entry | `fix-2026-11-20-gotcha-port` |
| `init` | `sdlc-initialize` customizes a knowledge file for the project's stack | `init-2026-11-20-vitest` |
| `agent-wiring` | `sdlc-develop-agent` or `sdlc-initialize` adds a project agent's rows to a dispatcher table. One block per agent, so the label names the agent and carries no date | `agent-wiring-payments-engineer` |

---

## Rules

1. **Every START must have a matching END with the same label.** A `PROJECT-SECTION-REMOVED` line stands alone. Orphaned markers are flagged by `sdlc-compliance-auditor` (Dimension 7).

2. **Labels must be unique within a file.** Duplicate labels cause ambiguity during extraction and re-injection.

3. **Markers must not nest.** A `PROJECT-SECTION-START` inside another `PROJECT-SECTION` block is malformed. Use separate, sequential blocks instead.

4. **Content inside markers is preserved verbatim.** `sdlc-migrate` does not modify, reformat, or merge content within markers — it extracts the block before overwriting and re-injects it afterward.

5. **Markers use the file's native comment syntax.** HTML comments (`<!-- -->`) for Markdown, hash comments (`#`) for YAML. Do not mix formats.

6. **Skills that produce project-specific content are responsible for adding markers at creation time.** This is a producing-skill obligation, not a migration-time responsibility. If content is created without markers, it can only be protected retroactively via deviation detection (§2.1c in `sdlc-migrate`).

7. **One mark per target.** A target is replaced or removed once in a file. A replacement's block holds the whole of what it replaces; a removal names one target (§ Target Grammar).

8. **A live mark is a whole line.** A mark is a line holding only its comment: `<!-- PROJECT-SECTION-… -->` in Markdown, or `# PROJECT-SECTION-…` in YAML, indented or not. Migration, `sdlc-compliance-auditor` and `sdlc-reviewer` read only those lines, outside code fences. A mark quoted inline in prose, or in a table cell, is text, so a document can describe the marks, as this one does.

9. **Inside a whole-file replacement, nothing more is marked.** A file replaced as `` `*` `` is the project's: an entry added, changed or removed in it needs no mark of its own, and a mark inside it is malformed.

### What Markers Can't Hold

One kind of project edit has no marker form:

- **YAML frontmatter.** A comment marker can't sit inside it, so a project's change to a skill's description has nowhere to go.

**Table rows** the project adds are an addition block inside the table, its start and end lines between rows. Agents read the source, where the rows hold; a Markdown renderer shows the table split at the marks, which framework files accept. Migration puts the block back after the same upstream row it followed, else at the end of the table. Changing or removing an upstream row is marked by replacing the section the table is in.

```markdown
| `frontend-developer` | UI components |
<!-- PROJECT-SECTION-START: agent-wiring-payments-engineer -->
| `payments-engineer` | Billing and refunds |
<!-- PROJECT-SECTION-END: agent-wiring-payments-engineer -->
```

A change smaller than a section (a sentence, a line in a list) is marked by replacing its section.

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

Upstream-owned **verbatim copies** of a process-doc section, carried inline in skills so a critical step is never reduced to a skippable pointer. The users are the two review-loop critical-steps blocks defined in `[sdlc-root]/process/review-fix-loop.md` § Mirrored Critical-Steps Blocks, the headless stop rule in `[sdlc-root]/process/headless-mode.md` § Mirrored Stop Rule, which every skill carries, and the Approval Brief procedure and Completion Report in `[sdlc-root]/process/writing-for-cd.md` § Mirrored Blocks, which the planning and execution skills carry, and the SDLC root check in `[sdlc-root]/process/path-mappings.md` § The SDLC Root, which `sdlc-migrate` and `sdlc-initialize` carry.

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

1. **Identical content.** The lines between `MIRROR-START`/`MIRROR-END` must be byte-identical to the lines between the matching `MIRROR-SOURCE-START`/`MIRROR-SOURCE-END`. A skill may carry a block more than once (`sdlc-plan` carries the Approval Brief procedure twice), and each copy must match on its own. Any difference is a drift finding — `sdlc-reviewer` (§ Cross-skill DRY) and the framework's cross-skill DRY audit check it.
2. **Edit the source, then re-copy.** Never edit a copy in place. Context-specific wording goes outside the markers.
3. **Exempt from DRY extraction.** Mirrored blocks are deliberate duplication; DRY checks do not recommend extracting them — they check that they match.
4. **Not migration markers.** `sdlc-migrate` matches only the literal `PROJECT-SECTION-*` and `BUNDLE-SECTION-*` names, so `MIRROR` blocks pass through as ordinary upstream content: the upstream skill copy (with its current block) overwrites the old one. A project must not hand-edit a mirrored block; project additions go in a `PROJECT-SECTION` outside it.
5. **No nesting.** A `MIRROR` block may not contain or intersect a `PROJECT-SECTION` or `BUNDLE-SECTION`.
6. **Prose never spells a live marker.** The drift check finds blocks by matching marker text, so marker-shaped prose is read as a marker. In a source doc, describe its markers with `{id}` (`MIRROR-SOURCE-START: {id}`), never the literal id: a prose line carrying the literal marker starts the range early and reports false drift. In a skill, do not write the copy-marker form with a file name at all (`MIRROR-START:` followed by `file.md#`); name the markers and give the file and id separately.

---

## How Migration Uses Markers

### Direct Copy Files (§2.1)

1. Before overwriting, extract all `PROJECT-SECTION` blocks and `PROJECT-SECTION-REMOVED` lines with their labels and heading context
2. **Review each block against upstream changes (§2.1d):**
   - Compare the upstream section at `source_version` vs `[target_tag]` (for a replacement or removal, its target)
   - Classify: OK, REVIEW (significant changes), ORPHAN (section removed), OPPORTUNITY (new patterns), CONFLICT (contradicts upstream)
   - Present non-OK findings to user with options: keep, update, remove, merge
3. Copy the upstream file (overwriting the project's version)
4. Leave out of the new copy every target a replacement or removal names; re-inject each block at its original heading position, a replacement in its target's place (unless user chose to update/remove), and each removal line where its target was
5. If the heading no longer exists upstream, append at end with a warning comment, in the file's own comment syntax
6. Inject `BUNDLE-SECTION` fragments for installed bundles targeting this file (strip-then-append from the z-sdlc source at the target release — no content review; these blocks are upstream-owned)

### Content-Merge Files (§2.2–2.4)

1. **Review marked blocks against upstream changes (§2.1d)** — same classification and user presentation
2. Framework sections outside markers are updated to match upstream, dual-audience skills' included; a replaced or removed target is left out
3. Markers are never moved, split, or merged automatically — but user can choose to update content during review
4. Inject `BUNDLE-SECTION` fragments for installed bundles targeting this file, exactly as in the direct-copy flow — most fragment targets are content-merged skills, so this path must run the injection pass too

### Knowledge YAMLs (§2.1b)

Key by key, and item by item in a key's list: upstream's version, unless a mark says otherwise. A key or item upstream never had is the project's and stays. A key upstream dropped since the project's last migration goes, unless the project marked it.

### Deviation Detection (§2.1c)

1. Before any file is updated, diff the project's version against the previous upstream version
2. If the project changed content outside existing marks (an edit, a replacement or a removal), present the customizations
3. User can choose to: mark them (as an addition, a replacement or a removal), take upstream's (discard), or skip the file

---

## Validation

The `sdlc-compliance-auditor` validates marker integrity as part of Dimension 7 (Migration Integrity):

- Every `START` has a matching `END` with the same label
- No orphaned `END` without a `START`
- A `replaces` target and a `PROJECT-SECTION-REMOVED` line name one target in § Target Grammar (a heading, a key path, `key[field=value]`, or `*`), quoted in backticks, each target once and none inside another's
- Labels unique within the file; no `PROJECT-SECTION` inside another; no mark inside a `*` replacement
- Only whole-line marks outside code fences count (rule 8)
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

- **Not a way to opt out of upstream changes silently.** Framework sections outside markers are still updated by migration. A replacement or removal is how a project overrides upstream, on purpose and in writing; migration still shows upstream's later changes to what it replaced or removed (§2.1d).
- **Not version control.** Markers don't track history — they mark boundaries. Use git for history.
- **Not a substitute for upstream contribution.** If a project-specific change would benefit all projects, propose it upstream rather than wrapping it in markers permanently.
- **Not a guarantee of permanent preservation.** Migration reviews marked content against upstream changes (§2.1d). If upstream significantly changed the surrounding context, the user is prompted to review — they may choose to update, merge, or remove the marked content. Markers protect from silent overwriting, not from becoming stale.
