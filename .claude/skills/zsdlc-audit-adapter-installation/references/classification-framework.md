# Classification Framework

For each differing hunk between target installation and z-sdlc source, assign one verdict. This framework exists so two auditors running the skill on the same installation reach the same classification.

## The four verdicts

| Verdict | Meaning | Fix destination |
|---|---|---|
| **upstream** | z-sdlc source has a bug the adapter-installed version corrected, OR z-sdlc source uses non-canonical phrasing | z-sdlc source (this repo) — edit the source file, add changelog entry |
| **plugin** | Adapter transformation is wrong (bug, gap, or exemption violation) | `~/Projects/neuroloom/neuroloom-sdlc-plugin/` — edit Pattern Mapping, add guard, or fix transformer rule |
| **both** | A single finding requires coordinated fixes in both repos | Both |
| **neither** | Correct as-is: legitimate transformation, legitimate customization, or no-op | No action |

## Decision tree

For each hunk, walk this in order and stop at the first match:

### 1. Is the hunk inside a PROJECT-SECTION marker pair?

```
<!-- PROJECT-SECTION-START: <label> -->
...hunk content...
<!-- PROJECT-SECTION-END: <label> -->
```

If yes → **neither** (project-specific customization preserved by design). Don't look further.

### 2. Is the hunk inside a preserved MCP section (project-authored MCP)?

Signal: the section contains `memory_search(query="<domain-specific>", tags=[...])` with query terms that reference project-specific domain vocabulary not found in the plugin's Pattern Mapping output.

Example — a domain-specific query like `memory_search(query="Tailwind v4 migration patterns color tokens", tags=[...])` is clearly project-authored. A generic query like `memory_search(query="agent communication protocol structured progress handoff format", tags=[...])` matches what the plugin's Pattern Mapping emits and would also appear in any Neuroloom installation.

If the hunk is inside a project-authored MCP section preserved by the plugin's §4.2.0 gate → **neither**.

### 3. Is the hunk in a known-exempt file (adapter transforming what it shouldn't)?

Check against `exempt-file-list.md`. If the file is exempt and the hunk shows any transformation shape (i.e., any MCP call, any metadata replacement, any orphan debris) → **plugin** (exempt-file violation).

Exception: `agents/sdlc-compliance-auditor.md` has a documented adapter customization around the methodology path reference in line ~13. If the hunk is only that documented path correction, it's **neither**. Anything else in that file → **plugin**.

Adapter-owned files and lines (`exempt-file-list.md` § Adapter-owned: `knowledge-routing.md`, the `sdlc-reviewer.md` checklist, Integration `**Uses:**` lines) aren't exempt. Skip this step for them and go on to step 4.

### 4. Is the hunk a known malformed transformer output?

If the target side contains any of:
- `((discipline memories`, `((memory graph`, `((the agent knowledge graph`, `((via memory_store`
- `*.md\`)` or `) *.md)` (orphan debris)
- `Read memory_store` or `Read memory_search` (malformed API verb)
- Greedy-swallow in query string (e.g., `query="...(e"` followed by leaked text)

→ **plugin** (transformer bug). See `defect-catalog.md` §1 for root causes.

### 5. Does the target side contain an untransformed canonical phrase?

If the hunk shows the target has `[sdlc-root]/knowledge/...` or `[sdlc-root]/disciplines/...` text that the plugin's Pattern Mapping should have transformed, and the file is not on the exempt list, and the context is not a fenced code block / Integration section / audit-description-by-design:

- **Pattern Mapping gap** (no rule covers this phrasing) → **plugin**
- **Match failure** (rule exists but didn't fire, e.g., mid-sentence verb or backtick-wrapped path) → **plugin**
- **Preservation boundary** (section was kept verbatim and contained untransformed content) → **plugin** (plugin should re-transform inside preserved sections)

All three collapse to **plugin** for fix routing, but in the findings detail note which subcategory so the plugin maintainer knows what kind of fix to apply.

### 6. Does the hunk show structural content loss?

Compare heading counts / table row counts / numbered step counts between the target and z-sdlc source.

If the target has fewer of any structural element than source, and the delta doesn't match a PROJECT-SECTION or documented customization → **plugin** (content-merge content-loss).

### 7. Does z-sdlc source have a bug the target corrected?

If the target's version is MORE correct than source — e.g., a path reference in source points at a non-existent location and the target's version points at the real one — → **upstream**.

Verify by checking the file system: does the path in the source version resolve? If not and the target's does, source is buggy.

Canonical example: `agents/sdlc-compliance-auditor.md:13` — z-sdlc source had `[sdlc-root]/knowledge/compliance-methodology.md` (broken path); the target had `.claude/skills/sdlc-audit/references/compliance-methodology.md` (correct path). Upstream finding.

### 8. Does z-sdlc source use non-canonical phrasing?

If source uses a phrasing the plugin's Pattern Mapping wouldn't recognize (per the plugin's reviewer checklist), and the adapter had to emit a TRANSFORMATION_WARNING or leave it untransformed → **upstream** (z-sdlc needs to use canonical phrasing).

These findings are rare — the z-sdlc `sdlc-reviewer` agent should have caught them at authoring time. Any that slip through indicate the reviewer's canonical-phrase list is out of sync with the phrasing contract.

### 9. Does the hunk indicate a defect that needs BOTH fixes?

Rare. Typically:
- A z-sdlc source phrase uses non-canonical wording (upstream fix) AND the plugin would silently mis-transform if upstream used the canonical form (plugin fix).

Default to picking one primary classification and note the secondary in the findings detail.

### 10. Everything else

If the hunk is a clean canonical transformation (z-sdlc source uses a canonical phrase and the target side shows the expected Pattern Mapping output) → **neither**.

If the hunk represents a no-op migration (files identical) → **neither**.

## Specific examples from `migrate-f01a70`

To calibrate your intuition, these are real findings from the 2026-04-22 audit:

| Hunk site | Walk-through | Verdict |
|---|---|---|
| `AGENT_TEMPLATE.md:68` shows `memory_search(query="[agent-name] domain-specific patterns anti-patterns guidance", tags=[...])` where source has `consult [sdlc-root]/knowledge/agent-context-map.yaml` | Step 10 — clean canonical transformation | **neither** |
| `AGENT_TEMPLATE.md:133` shows `Read memory_store with tags [...]` | Step 4 — malformed API verb | **plugin** |
| `AGENT_TEMPLATE.md:134` shows untransformed `knowledge stores (\`[sdlc-root]/knowledge/\`)` | Step 5 — Pattern Mapping rule exists but didn't fire mid-sentence | **plugin** |
| `sdlc-reviewer.md:82-86` shows forbidden-phrases checklist transformed into Neuroloom forms | Step 3 — exempt-file violation at the time. Since 2026-10-29 the file is adapter-owned (`exempt-file-list.md` § Adapter-owned), so a clean transform is **neither** | **plugin** then, **neither** now |
| `sdlc-compliance-auditor.md:13` shows `.claude/skills/sdlc-audit/references/compliance-methodology.md` where source has `[sdlc-root]/knowledge/compliance-methodology.md` | Step 7 — source path is broken, the target corrected it | **upstream** |
| `sdlc-plan.md:240-254` shows 3-step stub where source has 5-step "Library verification (MANDATORY)" procedure | Step 6 — structural content loss | **plugin** |
| `sdlc-execute.md:257` shows `Discipline parking lot entries ((discipline memories, tagged sdlc:discipline:*) *.md\`)` | Step 4 — double-paren corruption | **plugin** |
| `sdlc-compliance-auditor.md:116` shows `(resolve via .sdlc-manifest.json's sdlc_root field, or fall back to .claude/sdlc/)` instead of source's `(detected in methodology section above)` | Step 3 exception — documented customization in sdlc-compliance-auditor | **neither** |

## Bias check

When in doubt between two verdicts, bias toward **plugin**. The adapter's job is to produce correct output; if the output is wrong, the adapter owns it until proven otherwise. Upstream findings should have evidence that z-sdlc source is itself broken (verify the path doesn't exist, the phrasing is on the forbidden list, etc.) — not just "the adapter transformation produced something unexpected."
