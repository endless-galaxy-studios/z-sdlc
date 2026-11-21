# PROJECT-SECTION Marker Review: Finding Types and Detection

This reference defines the classification scheme and detection rules for PROJECT-SECTION content review during migration (§2.1d).

## Finding Type Classification

| Upstream Change | Project Marker Status | Finding Type | Recommendation |
|-----------------|----------------------|--------------|----------------|
| Section unchanged | Any | `OK` | Re-inject as-is |
| Section updated (minor) | Content still valid | `OK` | Re-inject as-is |
| Section updated (significant) | Content may be stale | `REVIEW` | Present to user — content may need updating |
| Section restructured | Block position unclear | `REVIEW` | Present to user — may need repositioning |
| Section removed | Block orphaned | `ORPHAN` | Present to user — content has no home |
| New patterns added nearby | Could benefit project | `OPPORTUNITY` | Present to user — may want to adopt |
| Project content contradicts upstream | Conflict detected | `CONFLICT` | Present to user — resolve contradiction |
| A replaced or removed target changed upstream | The project set aside a version upstream has since improved | `REVIEW` | Present to user — show upstream's change to the target; keep the mark, update the replacement, or drop the mark to take upstream's |
| A replaced or removed target is gone upstream | The mark names nothing | `ORPHAN` | Present to user — the mark can go |
| A replaced or removed target is unchanged upstream | — | `OK` | Keep the mark |

## User Decision Prompt

For each extracted `PROJECT-SECTION` block or `PROJECT-SECTION-REMOVED` line with a non-`OK` finding, present:

```
PROJECT-SECTION CONTENT REVIEW
══════════════════════════════

Found [N] marked blocks that may need attention:

┌─ [file path] ─────────────────────────────────────
│ Label: [marker label]
│ Section: [heading]
│ Finding: [REVIEW | ORPHAN | OPPORTUNITY | CONFLICT]
│
│ Upstream change:
│   [brief description of what changed in upstream]
│
│ Project content:
│   [first 3-5 lines of marked block, truncated if long]
│
│ Recommendation:
│   [specific suggestion based on finding type]
└────────────────────────────────────────────────────

[Repeat for each finding]

For each finding, choose:
1. Keep as-is — re-inject project content unchanged
2. Update — [opens content for manual edit, then re-inject]
3. Remove — discard this marked block, adopt upstream
4. Merge — combine project additions with upstream changes

Enter choices (e.g., "1:keep, 2:update, 3:remove" or "all:keep"):
```

## User Decision Application

- `keep` — re-inject block verbatim after upstream copy
- `update` — user edits the block content, then re-inject
- `remove` — do not re-inject; block is discarded
- `merge` — combine project content with upstream changes (present merged result for confirmation)

**For a replacement or a removal**, the choices mean:

| Choice | Replacement (`replaces`) | Removal (`PROJECT-SECTION-REMOVED`) |
|---|---|---|
| `keep` | Keep the block, and leave upstream's target out | Keep the line, and leave the target out |
| `update` | Edit the block (to take upstream's change into it), then keep it | Edit the reason or re-point the target (an ORPHAN's renamed heading or key) |
| `remove` | Drop the mark: upstream's target comes back in its place | Drop the line: upstream's target comes back |
| `merge` | Combine the block with upstream's changed target, shown for confirmation | Not offered: a removal holds no content |

In the prompt, a removal shows its line and upstream's current target in place of "Project content".

## Decision Logging

```
PROJECT-SECTION review decisions:
- [file]#[label]: kept (upstream section unchanged)
- [file]#[label]: kept (user chose to preserve despite upstream changes)
- [file]#[label]: updated (user modified content to align with upstream)
- [file]#[label]: removed (user adopted upstream version)
- [file]#[label]: merged (combined project + upstream)
```

## Finding Type Detection Rules

| Type | Detection | User Prompt |
|------|-----------|-------------|
| `REVIEW` | Upstream section diff > 20% changed lines, or key patterns added/removed | "Upstream significantly updated this section. Your marked content may reference outdated patterns or miss improvements." |
| `ORPHAN` | Upstream removed the heading entirely | "The section this content lived under no longer exists. Consider: moving to a new location, removing if obsolete, or keeping at file end." |
| `OPPORTUNITY` | Upstream added new content within 10 lines of marker position | "Upstream added new guidance near your marked content. Review whether to incorporate or reference it." |
| `CONFLICT` | Project content contains patterns explicitly superseded in upstream changelog | "Your marked content uses [pattern] which upstream replaced with [new pattern]. Consider updating." |
| `REVIEW` (target) | A replacement's or removal's target differs between `source_version` and `[target_tag]`, by any amount | "Upstream changed `[target]`, which you [replaced \| removed]. Here is its change: keep your mark, update it, or take upstream's." |
| `ORPHAN` (target) | `[target_tag]` no longer has the target | "Upstream no longer has `[target]`. Its likely new name is `[heading or key]`: re-point the mark, or drop it." |
| `CONFLICT` (unit) | Upstream and the project each added a knowledge unit of the same name since `source_version` (§2.1b) | "Upstream added `[unit]`, and so did you. Keep yours (marked as a replacement), take upstream's, or rename yours." |

## When to Skip Review

- If `source_version` is unknown (first migration after legacy install), skip review — no baseline to compare against
- If an addition is < 7 days old (parse date from label), skip its review — too recent to be stale. A replacement or removal is always compared with its target, whatever its age.
