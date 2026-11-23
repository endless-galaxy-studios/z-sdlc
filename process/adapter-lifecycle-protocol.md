# Adapter Lifecycle Protocol

## Purpose

Adapter plugins transform z-sdlc's file-based knowledge routing into alternate backends (memory graphs, vector stores, external APIs). Before this protocol, adapters achieved this by overriding `sdlc-initialize` and `sdlc-migrate` entirely — full skill replacements that forked upstream's logic, accumulated merge drift, and lagged behind upstream improvements.

The adapter lifecycle protocol separates the concerns. Upstream owns the migration algorithm (drift detection, changelog gating, marker preservation, bundle handling, file merging). Adapters own the knowledge backend and content transformation. The protocol defines extension points — phases where upstream delegates to the adapter — so adapters participate without overriding.

When no adapter is declared, upstream's skills run identically to today. The protocol is invisible to non-adapter projects.

---

## Relationship to the Phrasing Contract

The phrasing contract (`process/knowledge-routing.md` § "Adapter Plugins and the Phrasing Contract") governs **content** — what phrases z-sdlc uses when referencing the knowledge layer, so adapters can pattern-match and transform them.

The lifecycle protocol governs **execution** — when adapters run during initialize and migrate, what inputs they receive, and what outputs they must produce.

Both are required. The phrasing contract ensures transformable content. The lifecycle protocol ensures the adapter has the opportunity to transform it at the right moment.

---

## Adapter Discovery

Adapter plugins declare themselves by shipping an `adapter.json` file at their plugin root. During `sdlc-initialize`, upstream scans installed plugins for this file and automatically wires the adapter into the project manifest.

### The `adapter.json` file

Lives at the adapter plugin's root directory (e.g., `.claude/plugins/neuroloom-sdlc-plugin/adapter.json`):

```json
{
  "zsdlc_adapter": true,
  "supported_zsdlc_version": "1.4.0",
  "phase_handlers": "references/adapter-lifecycle.md"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `zsdlc_adapter` | boolean | Must be `true`. Marker that identifies this plugin as a z-sdlc adapter. Adapters written before 2026-10-12 use the pre-rename key `ccsdlc_adapter`; readers accept either. |
| `supported_zsdlc_version` | string | Highest z-sdlc version the adapter's handlers have been verified against. Gates `[contract-change]` entries during migration — entries above this version halt deterministically. Pre-rename key: `supported_ccsdlc_version`; readers accept either, and a migration that refreshes a project's adapter entry writes the new key. |
| `phase_handlers` | string | Path to the handler reference doc, relative to the plugin root. Contains instructions for each phase the adapter participates in. |

### Discovery during initialization

During Phase 1 (before writing `.sdlc-manifest.json`), upstream's init scans for adapter plugins:

```
For each directory in .claude/plugins/:
  If {plugin_dir}/adapter.json exists:
    Read and parse adapter.json
    If zsdlc_adapter == true (or the pre-rename ccsdlc_adapter == true):
      Record this as the active adapter
```

If exactly one adapter is found, upstream populates the `adapter` block in the manifest automatically. If multiple adapters are found, halt with an error — only one adapter per project is supported.

### Manifest `adapter` block

The discovered adapter is persisted in `.sdlc-manifest.json` so `sdlc-migrate` can detect it without re-scanning plugins:

```json
{
  "version": "1.0.0",
  "source_repo": "...",
  "adapter": {
    "plugin": "neuroloom-sdlc-plugin",
    "plugin_root": ".claude/plugins/neuroloom-sdlc-plugin",
    "supported_zsdlc_version": "1.4.0",
    "phase_handlers": "references/adapter-lifecycle.md"
  },
  "installed_files": { "..." }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `plugin` | string | Adapter plugin name (read from the plugin's `plugin.json` → `name`) |
| `plugin_root` | string | Path to the adapter plugin root, relative to project root |
| `supported_zsdlc_version` | string | Copied from `adapter.json` at install time; updated during migration if the adapter's `adapter.json` has been bumped |
| `phase_handlers` | string | Copied from `adapter.json` — path to the handler doc, relative to `plugin_root` |

### Detection during migration

`sdlc-migrate` reads the manifest's `adapter` block directly (no plugin scan needed):

1. Read `.sdlc-manifest.json`.
2. If `manifest.adapter` exists and is not `null` → adapter mode.
3. Resolve handler doc: `{project_root}/{adapter.plugin_root}/{adapter.phase_handlers}`.
4. Load phase handler instructions from that doc.
5. Which phases the adapter participates in is determined by which H2 sections exist in the handler doc.
6. Refresh `supported_zsdlc_version` from the live `adapter.json` (the adapter may have been updated between migrations).

If the handler doc is missing or unreadable, halt with a clear error (adapter declared but handlers not found).

---

## Lifecycle Phases

Each phase corresponds to a natural seam in upstream's skill structure. The adapter declares participation by including the corresponding H2 section in its handler doc — if a section is absent, upstream runs its default behavior for that phase.

### Phase: `knowledge-seed` (initialize only)

| | |
|---|---|
| **Fires when** | Where upstream would install knowledge YAML files to `[sdlc-root]/knowledge/` |
| **Default (no adapter)** | Copy knowledge YAMLs from source to `[sdlc-root]/knowledge/` as flat files |
| **Purpose** | Ingest knowledge into the adapter's backend instead of (or in addition to) writing flat files |

The adapter's backend owns knowledge storage. During initialization, upstream provides the full set of knowledge YAML content; the adapter ingests it into its backend using whatever mechanism it supports (batch API, individual writes, etc.).

The adapter is responsible for:
- Assigning stable identifiers to each knowledge entry (for idempotent upsert during future migrations)
- Distinguishing upstream-originated entries from project-originated entries so project additions are never overwritten during future updates

### Phase: `knowledge-update` (migrate only)

| | |
|---|---|
| **Fires when** | Where upstream would run §2.1b key-level merge on knowledge YAML files |
| **Default (no adapter)** | Marked merge, key by key and item by item: upstream's version of an unmarked upstream entry, the project's marked replacements and removals kept, project-only entries kept (`sdlc-migrate` §2.1b) |
| **Purpose** | Let the adapter update its backend directly using its native diff/upsert semantics |

When an adapter declares this phase, upstream skips §2.1b entirely for knowledge YAML files. The adapter handles the update using its backend's native capabilities.

**Expected strategy:**

1. **Diff by identifier** — compare upstream knowledge entries (by stable ID) against what's already stored in the backend. Categorize as: new, updated, unchanged, deprecated.
2. **Upsert new and changed entries** — send only the delta to the backend. The backend handles idempotent write (create-or-update by ID).
3. **Protect project entries** — entries originated by the project (different origin tag) are invisible to this operation. They are never overwritten, removed, or re-tagged.
4. **Deprecate removed entries** — entries present in the backend but absent from upstream get marked deprecated (never hard-deleted — projects may still reference them).
5. **Update manifest** — the project's `source_version` in `.sdlc-manifest.json` reflects the new z-sdlc version after the full migration completes (handled by upstream, not the adapter).

This eliminates the materialization round-trip. No flat files are created, diffed, or cleaned up. The backend's own storage semantics handle what upstream's key-level merge does for flat-file projects.

**What upstream still handles:** `agent-context-map.yaml` structural updates (new agent entries, wiring changes) remain upstream's responsibility unless the adapter also transforms these during `post-file-write`. A project whose adapter declares this phase and that has no map (the adapter routes knowledge through its backend) has nothing to update: `sdlc-migrate` §3.3 skips, and never creates the map.

### Phase: `post-file-write`

| | |
|---|---|
| **Fires when** | After each operational file is written or merged by upstream |
| **Default (no adapter)** | No-op |
| **Purpose** | Apply the adapter's Pattern Mapping transformation rules to each file as it's installed |

**Granularity:** Per-file. Upstream calls the adapter once per written file.

**Two-pass pipeline (based on the Neuroloom model):**

1. **Pass 1 — Instruction and metadata rules:** Transform phrasing-contract anchors (file-path references) into backend-native calls. Example: `consult [sdlc-root]/knowledge/agent-context-map.yaml` → `memory_search(query="[agent-name] domain patterns", tags=["sdlc:knowledge"])`.

2. **Pass 2 — Concept-terminology rules:** Transform prose references to flat-file concepts into backend-native vocabulary. Example: "knowledge YAML files" → "memory entries tagged sdlc:knowledge". Applied to prose regions only — not paths, code blocks, or Integration sections.

**MCP preservation gate (for migrations):** When transforming a file that already contains backend-native calls (from a previous migration), the adapter must preserve existing calls. The gate:
1. Count backend-native calls in the project's current version (`COUNT_BEFORE`)
2. Apply transformation to upstream content
3. For files with existing calls: extract project-section calls, merge with transformed upstream, verify `COUNT_AFTER >= COUNT_BEFORE`
4. If count decreases → halt (backend call loss detected)

**File-type filter:** The adapter's handler doc declares which file patterns it transforms and which it skips:

```markdown
## post-file-write
Applies to: `[sdlc-root]/**/*.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`
Skip: `[sdlc-root]/knowledge/**/*.yaml` (handled by knowledge-update)
Hard exclusions: process/knowledge-routing.md, process/sdlc_changelog.md, process/changelog-archive/*.md, agents/sdlc-reviewer.md, agents/sdlc-compliance-auditor.md
```

Files not matching the filter are written by upstream with no adapter callout.

### Phase: `post-operation`

| | |
|---|---|
| **Fires when** | After all files written, before final manifest update |
| **Default (no adapter)** | No-op |
| **Purpose** | Run adapter-specific integrity verification |

The adapter runs its own verification gates after the file writes and knowledge updates are complete. In `sdlc-migrate` the manifest is not: §4.5 writes it after this phase, so `.sdlc-manifest.json` still holds the previous version's values, and an adapter checking it compares against what §4.5 will write (the run's `[target_tag]`, the new hashes of the files the run wrote), as §4.4's audit does. Based on the Neuroloom model, this includes:

- **Contract residue scan** — grep all written files for untransformed phrasing-contract anchors (e.g., residual `[sdlc-root]/knowledge/` references that should have been transformed)
- **Backend call retention** — verify aggregate backend-native call count across all files hasn't decreased from pre-migration baseline
- **Backend consistency** — verify the backend reflects the expected state (correct version tags, no orphaned entries, no duplicates)
- **Stale agent reference scan** — verify agent files reference valid backend queries, not dead file paths

The adapter reports pass/fail with details. Upstream includes the result in the migration report (§4.6).

---

## Phase Failure Semantics

Each phase declares its failure behavior in the adapter's handler doc via an `**On failure:**` line. Options:

| Failure Mode | Behavior |
|--------------|----------|
| `halt` | Upstream stops the migration/initialization, logs a `failure` event to the transaction log, reports to user. **This is the default if not declared.** |
| `warn-continue` | Upstream logs a `warning` event, continues with remaining phases. The final report includes the warning. |

Recommended defaults:

| Phase | Recommended | Rationale |
|-------|-------------|-----------|
| `knowledge-seed` | `halt` | Failed ingestion means the backend has no knowledge — project is non-functional |
| `knowledge-update` | `halt` | Failed update leaves knowledge in an inconsistent state between backend and framework version |
| `post-file-write` | `halt` | A failed transformation means backend-native calls are missing — agents won't retrieve knowledge. The MCP preservation gate makes partial success dangerous. |
| `post-operation` | `warn-continue` | Verification failure is informational — files are already written, halting doesn't undo them |

---

## Handler Doc Structure

The adapter's handler doc (referenced by `phase_handlers` in the manifest) is a markdown file with one H2 section per phase the adapter participates in. Absent sections mean "use upstream default."

```markdown
# Adapter Lifecycle Handlers — [Plugin Name]

## knowledge-seed
**On failure:** halt

[Instructions for ingesting knowledge into the backend during initialization...]

## knowledge-update
**On failure:** halt

[Instructions for diffing and upserting knowledge during migration...]

## post-file-write
**On failure:** halt
**Applies to:** `[sdlc-root]/**/*.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`
**Skip:** `[sdlc-root]/knowledge/**/*.yaml`
**Hard exclusions:** [list of files copied verbatim]

[Instructions for applying Pattern Mapping transformations...]
[May reference external docs, e.g., "See references/pattern-mapping-rules.md for the full rule table"]

## post-operation
**On failure:** warn-continue

[Instructions for running integrity gates...]
```

The instructions are prose that upstream's skill reads and follows — same pattern as existing reference docs in the framework. They may reference other files in the adapter plugin for detailed transformation tables or audit procedures.

---

## Upstream Skill Integration

### In `sdlc-migrate`

```
§ Pre-Flight (existing)
  ... existing pre-flight checks ...
  → Read .sdlc-manifest.json
  → If manifest.adapter exists:
      Resolve handler doc path
      Read handler doc
      Note which phases are declared (by H2 section presence)

§ Phase 1: Detect Changes (unchanged)
  ... changelog review, drift detection, categorization ...

§ Phase 2: Apply Updates
  § 2.1b Knowledge Files:
    → If adapter declares knowledge-update:
        Execute adapter's knowledge-update instructions
    → Else:
        Run upstream's key-level merge (unchanged)

  § 2.1 Operational Files (for each file in change set):
    → Write/merge file (unchanged upstream logic)
    → If adapter declares post-file-write AND file matches filter:
        Execute adapter's post-file-write instructions on this file

§ Phase 4: Verification
  ... existing verification (4.1–4.4) ...
  → If adapter declares post-operation:
      Execute adapter's post-operation instructions
  → 4.5: Update manifest (unchanged)
  → 4.6: Report to user (include adapter phase results)
```

### In `sdlc-initialize`

```
§ Phase 1: Install Skeleton
  → Install operational files (unchanged)
  → If adapter declares post-file-write AND file matches filter:
      Execute adapter's post-file-write instructions on each installed file

§ Phase 5–6: Knowledge Seeding
  → If adapter declares knowledge-seed:
      Execute adapter's knowledge-seed instructions
  → Else:
      Copy knowledge YAMLs to [sdlc-root]/knowledge/ (unchanged)

§ Phase 10: Final Verification
  → If adapter declares post-operation:
      Execute adapter's post-operation instructions
  → Continue with existing verification
```

---

## Transaction Log Integration

Adapter phase execution is logged using existing transaction log event types:

```json
{"ts": "...", "run_id": "migrate-abc123", "skill": "sdlc-migrate", "event": "phase_start", "phase": "2.1b", "details": {"phase_name": "knowledge-update", "adapter": "neuroloom-sdlc-plugin", "mode": "adapter-delegated"}}
{"ts": "...", "run_id": "migrate-abc123", "skill": "sdlc-migrate", "event": "phase_end", "phase": "2.1b", "details": {"duration_ms": 12000, "result": "pass", "adapter": "neuroloom-sdlc-plugin"}}
```

When an adapter phase fails:

```json
{"ts": "...", "run_id": "migrate-abc123", "skill": "sdlc-migrate", "event": "failure", "phase": "2.1b", "details": {"adapter": "neuroloom-sdlc-plugin", "phase_name": "knowledge-update", "failure_mode": "halt", "error": "MCP connection refused — memory_search unavailable"}}
```

---

## What This Does NOT Change

- **The phrasing contract** — remains exactly as-is. Content-level using Pattern Mapping.
- **`contract_changes.yaml`** — remains the versioning mechanism for breaking changes.
- **`supported_zsdlc_version`** — remains required (now lives in the manifest's `adapter` block).
- **Upstream's non-adapter behavior** — when no adapter is declared, skills run identically to today. No conditional branches in the main flow.
- **`sdlc-port`** — remains a standalone one-time migration tool. Not part of the lifecycle protocol.
- **The reviewer/auditor contracts** — `sdlc-reviewer` still flags inline adapter conditionals. `sdlc-compliance-auditor` still validates phrasing contract compliance. Neither needs changes.

---

## Migration Path for Existing Adapters

For adapters currently using full skill overrides (e.g., `neuroloom-sdlc-plugin` at 0.4.x):

1. **Write the handler doc** — extract adapter-specific logic from the full skill overrides into `references/adapter-lifecycle.md` phase sections. The Neuroloom plugin's existing `references/pattern-mapping-rules.md` and `references/post-operation-audit.md` can be referenced from the handler doc rather than inlined.

2. **Add the `adapter` block** — update the adapter's initialization to write the `adapter` block into `.sdlc-manifest.json`.

3. **Remove skill overrides** — once upstream ships lifecycle-aware skills, the adapter removes its `/sdlc-initialize` and `/sdlc-migrate` overrides. The handler doc plus existing reference docs become the entire adapter surface for these skills.

4. **Version gate** — the adapter sets `supported_zsdlc_version` to the first upstream release with lifecycle support. Projects initialized before this version continue using the adapter's override until re-initialized.

---

## Versioning and Compatibility

The lifecycle protocol is versioned implicitly by the `supported_zsdlc_version` field. If upstream adds a new phase or changes phase semantics, it will be gated behind a `[contract-change]` entry in the changelog. Adapters that haven't verified against the new version will halt at their version gate.

New phases are always additive — existing phases never have their semantics changed without a `contract_changes.yaml` entry.
