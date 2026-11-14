# Red Flags

| Thought | Reality |
|---------|---------|
| "I'll just copy all files from z-sdlc" | Content-merge exists for a reason — direct copy overwrites project customizations |
| "The project's agent names match z-sdlc's" | They almost never do. Always read the project's context-map, not the source's |
| "I'll copy agent-selection.yaml with the other process files" | `agent-selection.yaml` is project-specific — it contains the project's agent roster, not the framework's. Never overwrite it. |
| "I'll skip the changelog review" | Breaking changes and new capabilities need user input before applying |
| "The tracker levels look right, I'll overwrite them" | The source repo's tracker reflects the source repo's levels, not this project's |
| "I'll rephrase the framework sections to be clearer" | Verbatim rule. Copy exactly from z-sdlc. Do not rephrase. |
| "I'll remove this agent mapping that z-sdlc doesn't have" | Project-specific mappings are intentional. Never remove them. |
| "No files were deleted, so §2.1a doesn't apply" | Always check. Moved files appear as add+delete pairs, not renames. |
| "I'll just read the file from the z-sdlc directory" | Use `git -C [path] show [target_tag]:file` — never raw filesystem reads or bare `HEAD`. The repo may have uncommitted WIP or unreleased commits. |
| "I'll use `git show HEAD:path > file` to extract" | UNSAFE. Shell redirect truncates the target before git show runs. If git show fails, the target becomes an empty file. See `[sdlc-root]/process/source-repo-safety.md`. |
| "New knowledge files are installed, so the project benefits automatically" | Knowledge in [sdlc-root]/ is available but not applied until skills and agents are updated to use it. §3.4 closes this gap. |
| "This file has no PROJECT-SECTION markers, so I'll just overwrite it" | Run deviation detection (§2.1c) first — the project may have customized framework content that should be wrapped in markers before overwriting. |
| "I'll rename all skill references to match upstream" | Guarded renames (§4.3a) — only rename if the target skill exists in the project. Renaming to a nonexistent skill causes silent process failures. |
| "I'll rename agent names in skills to match upstream" | Guarded renames (§4.3a) — only rename if the target agent exists in the project. Projects use different agent names (`frontend-engineer` vs `frontend-developer`). Renaming to a nonexistent agent causes silent dispatch failures. |
| "I'll auto-fix all the downstream impact findings" | Present findings to the user. They choose what to apply — some findings may not suit the project's context. |
| "The SDLC is in `ops/sdlc/`" | Not always. Some projects use `.claude/sdlc/`. Detect the actual structure in pre-flight and use `[sdlc-root]` throughout. |
| "PROJECT-SECTION markers mean this content is protected, just re-inject it" | Markers preserve content from being overwritten, but they don't prevent staleness. Review marked content against upstream changes (§2.1d) — a 6-month-old custom skill phase may reference outdated patterns. |
| "I'll skip the marker review for old blocks" | Old blocks are the most likely to be stale. The skip threshold is for recent blocks (< 7 days) that can't have drifted yet. |
| "The user chose 'keep' last time, so keep all markers this time" | Each migration is a fresh review. Upstream may have changed differently this time. Don't cache decisions across migrations. |
