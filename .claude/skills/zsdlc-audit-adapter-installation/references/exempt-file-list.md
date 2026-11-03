# Exempt File List (Neuroloom)

Files the adapter must copy verbatim from z-sdlc source — zero transformation applied. Any hunk in these files that shows transformation shape (MCP calls, metadata replacements, orphan debris, etc.) is a plugin defect.

This list mirrors the plugin's own "Transformation-Exempt Files" table in `neuroloom-sdlc-plugin/skills/sdlc-migrate/SKILL.md`. If the two lists drift, the plugin's list is authoritative for what the plugin *should* enforce; this list is what the audit *checks* was enforced. Drift between them is itself a finding.

## The list

| File | Install path | Why exempt | Permitted deviations |
|---|---|---|---|
| `process/sdlc_changelog.md` | `.claude/sdlc/process/sdlc_changelog.md` | Historical record — entries quote canonical phrases as context. Transforming corrupts history. | None in the project's own entries. Since contract 0017 the file is project-only: z-sdlc's entries are expected to be absent (they live in z-sdlc), so compare only entries the project wrote; a changed or missing one of those = defect. |
| `process/changelog-archive/*.md` | `.claude/sdlc/process/changelog-archive/*.md` | The project's archived changelog entries, moved unedited by `changelog_archive.py`. Same reason as the changelog. | None. Any hunk = defect. z-sdlc's own archive files are never installed; one in a project = defect. |
| `agents/sdlc-compliance-auditor.md` | `.claude/agents/sdlc-compliance-auditor.md` | Auditor's validation section lists canonical phrases as scan targets. | **Documented exception:** line ~116 section about PROJECT-SECTION scan may have `(resolve via .sdlc-manifest.json's sdlc_root field, or fall back to .claude/sdlc/)` in place of source's `(detected in methodology section above)` — this is a post-2026-04-22 adapter customization since the `**Path detection:**` block was dropped from the adapter version. Content outside that line must be verbatim. |
| `CLAUDE-SDLC.md` | (merged into target's `CLAUDE.md`, not a standalone file) | Framework documentation inserted into project's CLAUDE.md; contains canonical phrases as examples. | The adapter merges this into the project's existing CLAUDE.md rather than overwriting, so the section's content should be verbatim within the merged file. |
| `knowledge/provenance_log.md` | `.claude/sdlc/knowledge/provenance_log.md` | Project-specific append-only file; treated like changelog. The adapter should NEVER overwrite this. | None — should be completely absent from the diff (never touched by migration). |

## Adapter-owned (not verbatim)

In a Neuroloom-backed project, the adapter's versions of these are authoritative, not z-sdlc's (CD, 2026-10-29). A diff against z-sdlc source is expected and is never a defect by itself. Audit them like any transformed file: the Step 2 defect scans, the Step 3 residue scans and the classification framework. A defect is corrupted output (`defect-catalog.md` §1) or residue, not the transformation.

| File or lines | Install path | What the adapter does |
|---|---|---|
| `process/knowledge-routing.md` | `.claude/sdlc/process/knowledge-routing.md` | Installs its own Neuroloom routing doc in place of z-sdlc's phrasing contract. So the project has no copy of z-sdlc's current contract: check a phrasing change against z-sdlc source, not the project's copy. |
| `agents/sdlc-reviewer.md` | `.claude/agents/sdlc-reviewer.md` | Rewrites the reviewer's phrasing checklist in Neuroloom canonical forms, since the reviewer checks the project's own Neuroloom-form files. The frontmatter and everything else stays verbatim. |
| Integration-section `**Uses:**` lines (any skill) | `.claude/skills/*/SKILL.md` | Transforms knowledge-layer references there like any other line (plugin 0.5.7+). |

Earlier audits (`migrate-f01a70`, 2026-04-22) treated a transformed `knowledge-routing.md` or `sdlc-reviewer.md` checklist as an exempt-file violation. That verdict no longer applies to Neuroloom.

## How to verify exempt-ness during audit

For each file in the list:

1. **Locate both copies:**
   - Source: `~/Projects/z-sdlc/<source-path>`
   - Target: `<target-path>/<install-path>`

2. **Diff them:**
   ```bash
   diff -u ~/Projects/z-sdlc/agents/sdlc-compliance-auditor.md <target>/.claude/agents/sdlc-compliance-auditor.md
   ```

3. **Evaluate the diff:**
   - **No diff** → exempt-ness enforced correctly. ✓
   - **Only permitted-deviation hunks per the table above** → exempt-ness enforced correctly. ✓
   - **Any other diff** → exempt-file violation (plugin defect). Report per-hunk with what shape of transformation shows.

## Transaction log cross-check

The plugin emits `file_merged` events during stage 4.2. For each file on this exempt list, the event should have `subtype: "exempt_verbatim"` and `rules_fired: []`. Subtypes of `mcp_preserved`, `mcp_backfilled`, or `mcp_new_file` on an exempt file are telemetry evidence of exempt-ness NOT being enforced — even before diffing the content.

```bash
grep '"event":"file_merged"' <target>/.sdlc-transaction-log \
  | grep -E 'sdlc_changelog\.md|changelog-archive/|sdlc-compliance-auditor\.md|CLAUDE-SDLC\.md|provenance_log\.md' \
  | grep -v '"subtype":"exempt_verbatim"'
```

Any output is a finding — the plugin ran non-verbatim transformation on an exempt file.

## When the target's version is MORE correct than source

Sometimes the adapter's verbatim copy would propagate an upstream bug. The `agents/sdlc-compliance-auditor.md:13` case (broken methodology path) is an example. In these cases:

1. Classify the diff as **upstream** (source has a bug)
2. Note that the adapter is currently violating exempt-ness in a way that happens to produce the correct outcome
3. After the upstream fix lands, the adapter should return to verbatim copying — the correction is no longer needed

Don't punish the adapter for the workaround, but track it — once source is fixed, the plugin should drop any special-case handling.

## Future adapters

Different adapters may have different exempt lists. When adding a new adapter, create `references/exempt-file-list-<adapter>.md` and update `SKILL.md` Step 1 to select the right file based on `<adapter-name>` parameter.
