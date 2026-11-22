# Plugin Dependencies

## Required

| Plugin | What It Does | Skills That Use It |
|--------|-------------|-------------------|
| **context7** | Provides live library/framework documentation lookups via MCP. Prevents use of stale or incorrect API knowledge from training data. | All SDLC skills that touch external dependencies |

**context7 must be installed for accurate external library usage.** Without it, agents will rely on training data for API signatures, parameter names, and default behaviors — which go stale and cause subtle runtime failures.

See `context7-setup.md` for installation instructions.

## Highly Recommended

| Plugin | What It Does | Skills That Use It |
|--------|-------------|-------------------|
| **LSP** (language-specific) | Type-aware code intelligence — go-to-definition, find-references, hover, diagnostics. Replaces Grep-based guesswork with precise type-system navigation. | All planning and execution skills (discovery, pattern reuse, code verification) |
| **Playwright MCP** (`@playwright/mcp`) | Browser automation — navigate, click, type, screenshot, read console. Enables automated UI verification during execution. | Execution skills (POST-GATE UI smoke check, Step 0.5 experiential verification), review subagents (interaction testing, accessibility checks) |

**Install the LSP plugin for your project's primary language(s).** Without it, agents fall back to Grep for code navigation, missing type relationships, interface implementations, and call hierarchies. See `lsp-setup.md` for the full plugin list and installation instructions.

**Install Playwright MCP for projects with user-facing UI.** Without it, POST-GATE UI smoke checks and experiential verification fall back to manual browser inspection. For UI-heavy deliverables, automated verification catches render failures immediately after each phase instead of at post-execution review. See `playwright-mcp-setup.md` for installation instructions.


## Readiness check

The one check for these plugins: `sdlc-initialize` runs it during the install (Phase 9), and `sdlc-migrate` on
every migration (§ 4.4b), so a gap that appears after setup shows up too. Tell CD about each plugin it finds
missing, with its install command. A plugin installed with `/plugin install` is listed under `enabledPlugins` in a
settings file; an MCP server can also be in `.mcp.json`.

**context7 (required):**
```bash
grep -r "context7" ~/.claude/settings.json ~/.claude/settings.local.json .claude/settings.json .claude/settings.local.json .mcp.json 2>/dev/null
```
Missing: "context7 is required for library verification. Install via `/plugin install context7` or see
`[sdlc-root]/plugins/context7-setup.md`."

**LSP (highly recommended), for each of the project's languages:** an LSP plugin is named `<language>-lsp`
(`lsp-setup.md`'s table); the language servers' own names catch one configured by hand. The surest check is that
the `LSP` tool answers in this session (`lsp-setup.md` § Verification).
```bash
grep -rE -- "-lsp|typescript-language-server|pyright|gopls|rust-analyzer|clangd|omnisharp" ~/.claude/settings.json ~/.claude/settings.local.json .claude/settings.json .claude/settings.local.json .mcp.json 2>/dev/null
```
Missing: "LSP is recommended for type-aware code navigation. Install via `/plugin install <language>-lsp` (e.g.,
`/plugin install typescript-lsp`). See `[sdlc-root]/plugins/lsp-setup.md` for the full language list."

**Playwright MCP (recommended for a project with UI):** a project has UI when it has frontend components, web
pages or templates (`*.tsx`, `*.jsx`, `*.vue`, `*.svelte`, `*.cshtml` files, say).
```bash
grep -r "playwright" ~/.claude/settings.json ~/.claude/settings.local.json .claude/settings.json .claude/settings.local.json .mcp.json 2>/dev/null
```
Missing, in a project with UI: "Playwright MCP is recommended for automated UI verification during execution.
Install via `/plugin install playwright@claude-plugins-official` or see `[sdlc-root]/plugins/playwright-mcp-setup.md`."
