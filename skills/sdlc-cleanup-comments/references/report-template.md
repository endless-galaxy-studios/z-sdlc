# Report Template

The report `sdlc-cleanup-comments` writes in step 7, at `docs/reviews/comment-cleanup-{YYYY-MM-DD}.md`.

```markdown
# Comment Cleanup: {scope}

{N} comment lines cut in {M} files. For your call: {K} kept comments, {C} comments that contradict the code (possible bugs), {G} spots with no explanation.
Verification: {same as baseline | same as baseline; not trimmed: {slices} | fails ({check}), so nothing is committed | unverified, by CD's choice}

## Cut, by Area
| Area | Agent | Files changed | Lines cut | Shortened | Restored after check |
|---|---|---|---|---|---|

## Kept for Your Call
| # | Location | Comment | Why it was unclear |
|---|---|---|---|

## Comments That Contradict the Code
| # | Location | The comment says | The code does |
|---|---|---|---|

## Code With No Explanation
| # | Location | What a reader can't tell | Reason found (source) |
|---|---|---|---|

## Code That Should Explain Itself
| # | Location | Symbol | Comment it would replace | Suggested change |
|---|---|---|---|---|

## Constraints Worth Enforcing
| # | Location | Constraint | Check that could enforce it |
|---|---|---|---|

## Suppressions Worth a Look
| # | Location | Suppression | What the rule protects |
|---|---|---|---|

## Put Back for a Tool
| Location | The cut | What failed |
|---|---|---|

## Not Trimmed
| Slice | Why |
|---|---|
```
