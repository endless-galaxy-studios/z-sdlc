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

Lives at the adapter plugin's root directory: the directory Claude Code installed the plugin to (`claude plugin list --json` → `installPath`), or a copy vendored in the project:

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

During Phase 1 (before writing `.sdlc-manifest.json`), upstream's init looks for an adapter among the plugins installed and enabled for this project, and among plugins vendored in it:

```bash
# The project root, as Claude Code records a project-scope install's projectPath
ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)
command -v claude >/dev/null || echo "NO CLAUDE CLI: only a vendored adapter can be found"
# Installed for this project (project or local scope) or for the user. "enabled" alone isn't enough:
# it follows this directory's settings, so it reads true for another project's install of the plugin too
claude plugin list --json 2>/dev/null | jq -r --arg root "$ROOT_DIR" '
  .[] | select(.enabled == true) | select(.scope == "user" or .projectPath == $root)
      | "\(.id)\t\(.installPath)"' |
  while IFS="$(printf '\t')" read -r id dir; do
    jq -e '.zsdlc_adapter == true or .ccsdlc_adapter == true' "$dir/adapter.json" >/dev/null 2>&1 && echo "$id"
  done | sort -u
# Vendored in the project
find .claude/plugins -mindepth 2 -maxdepth 2 -name adapter.json 2>/dev/null | while read -r f; do
  jq -e '.zsdlc_adapter == true or .ccsdlc_adapter == true' "$f" >/dev/null 2>&1 && echo "vendored $(dirname "$f")"
done
```

If exactly one adapter is found, upstream populates the `adapter` block in the manifest automatically, and finds its directory with § Finding the plugin, `PLUGIN` set to the id found. If multiple adapters are found, halt with an error — only one adapter per project is supported. A headless run ends with status `failed`, naming them. A worktree is its own project here: an install for the main checkout doesn't count for it.

### Manifest `adapter` block

The discovered adapter is persisted in `.sdlc-manifest.json` so `sdlc-migrate` needn't discover it again; it looks up the plugin's directory by id (§ Finding the plugin). The block records which plugin the adapter is, never where one machine installed it:

```json
{
  "version": "1.0.0",
  "source_repo": "...",
  "adapter": {
    "plugin": "neuroloom-sdlc@endless-galaxy-studios",
    "supported_zsdlc_version": "1.4.0",
    "phase_handlers": "references/adapter-lifecycle.md"
  },
  "installed_files": { "..." }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `plugin` | string | The plugin's id as Claude Code lists it: `<name>@<marketplace>`; for a vendored plugin, its `.claude-plugin/plugin.json` → `name`. A manifest written before contract 0025 may hold the bare name; readers match it against the id's name part, and `sdlc-migrate` writes the full id. |
| `plugin_root` | string | Only for a plugin vendored in the project: its path relative to the project root. Never an absolute path or one outside the project. An install's location differs by machine and by version, so it is looked up on every run (§ Finding the plugin), not recorded. |
| `supported_zsdlc_version` | string | Copied from `adapter.json` at install time; updated during migration if the adapter's `adapter.json` has been bumped |
| `phase_handlers` | string | Copied from `adapter.json` — path to the handler doc, relative to the plugin's directory |

### Finding the plugin

`sdlc-initialize` and `sdlc-migrate` find the adapter's directory the same way on every run:

```bash
# The manifest's plugin (initialize sets PLUGIN to the id discovery found, and PLUGIN_ROOT for a vendored one)
PLUGIN=${PLUGIN:-$(jq -r '.adapter.plugin // empty' .sdlc-manifest.json 2>/dev/null)}
ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)
# 1. The enabled install whose id (or, for a bare name, whose id's name part) matches: the one for
#    this project (project scope, then local), else the user's. Never another project's install.
PLUGIN_DIR=$(claude plugin list --json 2>/dev/null | jq -r --arg p "$PLUGIN" --arg root "$ROOT_DIR" '
  [ .[] | select(.enabled == true) | select(.id == $p or (.id | split("@")[0]) == $p) ]
  | [ (.[] | select(.scope == "project" and .projectPath == $root)),
      (.[] | select(.scope == "local" and .projectPath == $root)),
      (.[] | select(.scope == "user")) ] | .[0].installPath // empty')
# 2. Otherwise a copy vendored in the project
if [ -z "$PLUGIN_DIR" ]; then
  ROOT=${PLUGIN_ROOT:-$(jq -r '.adapter.plugin_root // empty' .sdlc-manifest.json 2>/dev/null)}
  case "$ROOT" in ""|/*|"~"*|..|../*|*/../*|*/..) ;; *) [ -f "$ROOT/adapter.json" ] && PLUGIN_DIR="$ROOT" ;; esac
fi
if [ -n "$PLUGIN_DIR" ]; then echo "PLUGIN_DIR=$PLUGIN_DIR"
elif ! command -v claude >/dev/null; then echo "ADAPTER NOT FOUND: $PLUGIN (no claude CLI on PATH)"
else echo "ADAPTER NOT FOUND: $PLUGIN"; fi
```

If it prints `ADAPTER NOT FOUND`, stop before any change: tell CD the adapter isn't installed for this project, and to install it here (`claude plugin install <plugin> --scope project`, or `claude plugin enable <plugin>`) and restart Claude Code, then run again. With no `claude` CLI on `PATH`, say that instead: only a vendored copy can be found without it. **Headless run:** end with status `failed`. Never fall back to an absolute `plugin_root` an older manifest holds: it names one machine's install, often an older version's, whose handlers no longer match the plugin the session loaded.

The handler doc is `{PLUGIN_DIR}/{adapter.phase_handlers}`, and `${CLAUDE_PLUGIN_ROOT}` in it means `{PLUGIN_DIR}`.

### Detection during migration

`sdlc-migrate` reads the manifest's `adapter` block directly (no discovery needed):

1. Read `.sdlc-manifest.json`.
2. If `manifest.adapter` exists and is not `null` → adapter mode.
3. Find the plugin (§ Finding the plugin), before the version gate: the gate reads the live `adapter.json` from that directory.
4. Load phase handler instructions from `{PLUGIN_DIR}/{adapter.phase_handlers}`.
5. Which phases the adapter participates in is determined by which H2 sections exist in the handler doc.
6. Refresh the block in the manifest §4.5 writes (never earlier, so a run the version gate halts leaves it as it was): `supported_zsdlc_version` from the live `adapter.json` (the adapter may have been updated between migrations), `plugin` as the full id the lookup matched, and no `plugin_root` that is absolute or outside the project.

If the handler doc is missing or unreadable, halt with a clear error (adapter declared but handlers not found). A headless run ends with status `failed` and that error (`[sdlc-root]/process/headless-mode.md`).

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

**The knowledge layer is the adapter's** when the adapter routes knowledge through its backend and keeps no agent-context map: upstream knows it by the map's absence, as `sdlc-migrate` §3.3 does. Such an adapter, in this phase, removes the map and records it in `declined_files` (below). It also removes the copies `sdlc-initialize`'s Phase 1 made under `[sdlc-root]/knowledge/` and `[sdlc-root]/disciplines/`, dropping their `installed_files` entries without recording them as declined: the adapter seeds them from the z-sdlc source and keeps them up to date. From then on, `sdlc-migrate` copies, removes, merges, asks about and checks none of those files, and records none as declined. A file the adapter handles has no copy on disk to go missing, so a "keep it removed" record would only stop the adapter updating it. An adapter that keeps the map keeps the files too, and stays on the ordinary path.

**The agent-context map.** An adapter that routes knowledge through its backend and keeps no map removes `[sdlc-root]/knowledge/agent-context-map.yaml` in this phase and records it in `.sdlc-manifest.json` → `declined_files` (`[sdlc-root]/process/project-section-markers.md` § Deleted Files). Upstream reads that the same way `sdlc-migrate` §3.3 does: the adapter declares its knowledge phase, and the project has no map. In adapter mode, `sdlc-initialize` wires the map (Phase 5) after this phase, and skips the wiring when the map is gone. Its later checks (Phase 9a's maturity levels, Phase 10's checklist, Phase 11's audit) then treat the project's knowledge as reaching agents through the adapter.

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

### Phase: `project-knowledge` (initialize only)

| | |
|---|---|
| **Fires when** | `sdlc-initialize` writes the project's own content into the knowledge layer: each discipline's Project Context (Phase 7), the project's knowledge entries (Phase 8's testing gotchas) and the Process Maturity Tracker (Phase 9a). A lite install graduates without the adapter (`sdlc-initialize` § Lite Graduation Mode), so there is no lite content to hand over |
| **Input** | One item per write: its kind (`discipline-context`, `knowledge-entry`, `maturity-tracker`), the file and section it would have gone to, and its content |
| **Default (no adapter, or an adapter that doesn't declare it)** | Write it to that file, copied from the z-sdlc source first when the project doesn't keep it on disk |
| **Purpose** | Keep the project's content where its agents look, the adapter's backend, marked as the project's so `knowledge-update` never overwrites it |

These run after `knowledge-seed`, so without this phase their content lands on disk beside a backend the project's agents search instead. An adapter that doesn't declare the phase gets the files, which stay visible.

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
| `halt` | Upstream stops the migration/initialization, logs a `failure` event to the transaction log, reports to user (a headless run ends with status `failed` and the error). **This is the default if not declared.** |
| `warn-continue` | Upstream logs a `warning` event, continues with remaining phases. The final report includes the warning. |

Recommended defaults:

| Phase | Recommended | Rationale |
|-------|-------------|-----------|
| `knowledge-seed` | `halt` | Failed ingestion means the backend has no knowledge — project is non-functional |
| `knowledge-update` | `halt` | Failed update leaves knowledge in an inconsistent state between backend and framework version |
| `project-knowledge` | `halt` | Project content that doesn't reach the backend is invisible to the project's agents |
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

## project-knowledge
**On failure:** halt

[Instructions for storing the project's own discipline context, knowledge entries and maturity tracker during initialization...]

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
      Find the plugin by id (§ Finding the plugin); stop if it isn't enabled here
      Resolve handler doc path: {plugin dir}/{phase_handlers}
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
      Execute adapter's knowledge-seed instructions, then Phase 5 (map wiring),
      skipped when the adapter declined the map
  → Else:
      Phase 5, then copy knowledge YAMLs to [sdlc-root]/knowledge/ (unchanged)

§ Phases 7, 8, 9a: the project's own knowledge-layer content
  → If adapter declares project-knowledge:
      Hand each item to the adapter's project-knowledge instructions
  → Else:
      Write it to its file (unchanged)

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
