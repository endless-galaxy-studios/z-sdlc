# Playwright MCP Setup (Recommended)

The `@playwright/mcp` server gives Claude Code direct browser control — navigate, click, type, screenshot, and read console output. The SDLC uses it for visual UI verification during execution: POST-GATE smoke checks after each UI-affecting phase and experiential verification during the review loop.

## What It Provides

| Capability | What It Does | Used By |
|-----------|-------------|---------|
| `browser_navigate` | Navigate to a URL in a browser | Execution skills (POST-GATE UI smoke check, Step 0.5 experiential verification) |
| `browser_take_screenshot` | Capture the current page as an image | POST-GATE visual verification, review agent findings |
| `browser_click` / `browser_type` | Interact with page elements | Review subagents (golden path walk, interaction testing) |
| `browser_wait_for` | Wait for text to appear or disappear, or for a time to pass | Smoke checks (verify page rendered), interaction verification |
| `browser_console_messages` | Read browser console messages | POST-GATE console error check |

## Why It's Recommended

The SDLC execution skills auto-detect UI-affecting phases (files matching `*.tsx`, `*.jsx`, `*.vue`, `*.svelte`, `*.cshtml`, `*.css`, `components/`, `pages/`, `views/`, `templates/`) and run inline smoke checks after each phase. Without Playwright MCP, these checks fall back to manual browser inspection — the user must open a browser, navigate, and visually confirm. With Playwright MCP, the smoke check is automated: navigate, screenshot, check console, report.

For UI-heavy deliverables (visual editors, multi-phase component work, layout overhauls), automated verification catches render failures immediately after the phase that caused them — not at post-execution review where they've compounded across phases.

## Installation

Install the official plugin in Claude Code:

```
/plugin install playwright@claude-plugins-official
```

Or add it as a project MCP server, which a `.mcp.json` records for everyone working in the repository:

```
claude mcp add playwright npx @playwright/mcp@latest
```

The tools' names carry the install's prefix: `mcp__plugin_playwright_playwright__` for the plugin,
`mcp__playwright__` for the server. An agent whose frontmatter has a `tools:` line gets only the tools it
lists, so it names each browser tool it uses in full, with that prefix; an agent without one inherits them.

## Verification

After installation, verify the tools are available by asking Claude Code:

```
What MCP tools do you have access to?
```

You should see `browser_navigate`, `browser_take_screenshot`, `browser_click`, and related tools in the list. The exact tool names may vary by server version — check the `@playwright/mcp` documentation via Context7 for the current API surface.

## How It's Used in the SDLC

### POST-GATE UI Smoke Check (Execution Skills)

After each UI-affecting phase completes, the execution skill runs an inline smoke check:

1. Navigate to the affected page (route specified in the plan's visual checkpoints)
2. Wait for the key element that proves the page loaded
3. Take a screenshot and verify it matches the phase's expected outcome
4. Read console errors — runtime errors after the implementation are defects

If the smoke check fails, the phase agent is re-dispatched with the screenshot and console errors before the next phase begins.

### Experiential Verification (Review Loop — Step 0.5)

Before dispatching review agents, the manager walks the golden path using Playwright MCP: navigate, interact with the primary user flow, screenshot at each key state, check console errors.

### Review Subagent Verification

When `sdet`, `frontend-developer`, and `accessibility-auditor` are dispatched for review, their prompts include instructions to use Playwright MCP (if available) to verify findings in the running app — testing interactions, keyboard navigation, focus management, and accessibility.

## Graceful Degradation

If Playwright MCP is not installed, the SDLC workflow still functions:

- POST-GATE UI smoke check is skipped with a note: "Playwright MCP not available — manual verification recommended"
- Step 0.5 experiential verification falls back to manual inspection
- Review subagents describe what manual checks the user should perform

The workflow is better with Playwright MCP but not broken without it.
