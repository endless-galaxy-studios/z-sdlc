# Context7 MCP Setup

The `context7` MCP server provides up-to-date library and framework documentation lookups via the Context7 API.

## What It Provides

| Tool | What It Does | Used By |
|------|-------------|---------|
| `resolve-library-id` | Resolves a library name to a Context7 library ID | All skills that touch external dependencies |
| `query-docs` | Queries library documentation by resolved ID | All skills that touch external dependencies |

A tool's full name depends on how Context7 is installed. The plugin's tools are `mcp__plugin_context7_context7__resolve-library-id` and `mcp__plugin_context7_context7__query-docs`. A server you add yourself, in `.mcp.json` or with `claude mcp add`, under the name `context7`, gives `mcp__context7__resolve-library-id` and `mcp__context7__query-docs`.

## Why It's Required

Claude's training data goes stale. API signatures change, parameters get renamed, defaults shift between versions. Without live documentation lookup, Claude will confidently use outdated or incorrect library APIs — and the code will look plausible but break at runtime.

Context7 closes this gap by providing real-time documentation for the libraries your project actually uses. Every SDLC skill that dispatches agents to write or review code must have access to accurate library documentation.

## Installation

Install via Claude Code:

```
/plugin install context7
```

This installs Context7 as a managed plugin with automatic updates.

## Verification

After installation, verify the tools are available by asking Claude Code:

```
What MCP tools do you have access to?
```

You should see `mcp__plugin_context7_context7__resolve-library-id` and `mcp__plugin_context7_context7__query-docs` in the list, or the `mcp__context7__` names for a server you added yourself.

## Granting It to Agents

An agent with a `tools:` line gets only the tools it lists, so an agent that writes or reviews code against external libraries lists both Context7 tools by the full names your session shows. A project that runs the software factory also lists `mcp__context7__resolve-library-id` and `mcp__context7__query-docs`, because the factory's jobs connect Context7 as a server named `context7`. A listed tool the session doesn't have is skipped, as long as another entry in the list resolves. See "Agent tool grants name each tool" in the project's CLAUDE.md.

## How It's Used in the SDLC

The CLAUDE-SDLC.md file includes a **Verification Policy** that requires:

1. Before using any external library API → resolve via Context7, then query docs
2. Before asserting version-specific behavior → check the version in use, then query Context7 for that version's docs
3. If Context7 doesn't have docs for a library → disclose the gap and ask the user for a documentation source

This policy applies to all domain agents dispatched by SDLC skills. Agent dispatch prompts should include verification instructions when the phase involves external library integration.
