---
name: agent-name
description: "Use this agent when [triggering conditions — be specific about what files, domains, or user requests should activate this agent]. Typical triggers include [2-4 trigger scenarios as short noun phrases]. [Seam sentence, only if a confusable sibling exists: a look-alike request and the agent it belongs to.] See When to invoke in the agent body.\\n\\nDo NOT use for: [adjacent domain] — use [other-agent] instead."
model: sonnet
tools: Read, Write, Edit, Bash, Glob, Grep, SendMessage
color: blue
memory: project
---

<!-- Remove this comment block before using the template.

FRONTMATTER REFERENCE:

  name:
    Format: lowercase-with-hyphens, 3-50 characters
    Pattern: must start and end with alphanumeric
    Good: code-reviewer, test-generator, api-docs-writer
    Bad: helper (too generic), -agent- (starts with hyphen), my_agent (underscores)

  description:
    The most critical field — determines when Claude triggers this agent. Claude Code injects
    EVERY agent's full description into EVERY session's system prompt, regardless of whether
    that agent is ever spawned — it is a permanent per-session tax, unlike the agent body (which
    only costs tokens once spawned). Keep it lean: triggers, a few named trigger scenarios, one seam sentence and the boundary, with no example dialogues. The worked scenarios go in the body's ## When to invoke section, which costs nothing until the agent runs.
    Format: single-line YAML double-quoted string using \\n (double-backslash n) for newlines, never a block scalar (|, >)
    WARNING: In YAML double-quoted strings, \n = real newline; \\n = literal \n, the form every Claude Code version parses (use it)
    Must include:
    - Triggering conditions ("Use this agent when..."), naming the files, domains and kinds of
      request that should route here.
    - "Typical triggers include ..." naming 2-4 trigger scenarios as short noun phrases, so routing
      sees them (routing reads only the description, never the body).
    - When a confusable sibling agent exists, one seam sentence naming the look-alike request and
      the agent it belongs to. The Do-NOT-use boundary counts as the seam sentence when it names both.
    - The pointer "See When to invoke in the agent body." Write it without quote marks: a double
      quote inside the double-quoted string would need escaping.
    - NO <example> dialogue blocks and NO <commentary>. The description is read on every dispatch
      decision; the worked scenarios go in the body's ## When to invoke section instead.
    - A mandatory "Do NOT use for: X — use Y instead" boundary sentence. It is the primary mechanism
      for resolving overlap with adjacent agents.
    See the frontmatter above for the exact format. This follows Anthropic's agent-writing guide
    (the plugin-dev plugin's agent-development skill), which replaced its own <example> dialogues
    with this format on 2026-04-28.

  model:
    Options: sonnet (default, balanced) | opus (for architectural decisions and high-risk review) | haiku (fast, for retrieval/search tasks)
    Use opus for agents that make design decisions or evaluate trade-offs — and for
    agents that review high-risk work implemented by cheaper tiers.
    Use haiku for agents that primarily search and retrieve.
    Read [sdlc-root]/knowledge/architecture/model-tier-strategy.yaml for the full
    tier ladder and risk-escalation rules.

  effort:
    Optional. Overrides the session reasoning effort for this agent's role.
    Options: low | medium | high | xhigh | max
    Use low for recon/mechanical roles (discovery, summaries, checklist verification) —
    nearly free quality-wise. Use high+ for review agents on high-risk domains.
    Omit when the session default fits. Requires a Claude Code version that supports
    per-agent effort frontmatter — verify before relying on it.

  tools:
    List only what the agent actually needs — fewer tools = less latitude to diverge.
    Common sets:
    - Read-only analysis: Read, Glob, Grep
    - Code generation: Read, Write, Edit, Glob, Grep
    - Full engineering: Read, Write, Edit, Bash, Glob, Grep, LSP
    - Research: Read, Glob, Grep, WebFetch, WebSearch
    Search tools in Claude Code are platform-dependent. On macOS, Linux and WSL, Glob and Grep are
    left out of the default tool set and Claude searches with find and grep through Bash (embedded
    bfs and ugrep, seen by hooks and permission rules as Bash calls). A subagent that lists Glob or
    Grep and leaves out Bash gets them back; one that also lists Bash doesn't, and searches through
    Bash. So a read-only agent lists Glob and Grep without Bash. Keep them in a Bash agent's line
    too: Windows keeps both tools.
    In Claude Code, add SendMessage to any set when the agent's Communication Protocol section tells
    it to send progress updates (this template's does): without it the agent has no channel for its progress updates (background and team dispatches
    only). Every tool the body tells the agent to use (an MCP server's tools by exact name) must be
    listed here; a tool the list leaves out is simply unavailable to the agent. Name an MCP server's
    tools one by one: a server prefix (mcp__server) grants every tool the server has, and each
    definition loads into the agent's context on every dispatch, which for a large server is a
    six-figure token cost. Which tools a project's rules require of its agents (the project's memory
    store, the docs tool, LSP) is the project's choice: its CLAUDE.md lists them, and they go in this
    line by exact name.

  color:
    Options: green | cyan | orange | red | yellow | blue | purple | pink
    Pick the color matching the agent's semantic category. Multiple agents CAN share
    a color if they belong to the same group — color indicates category, not uniqueness.
    Semantic groups:
    - green: core product
    - cyan: architecture + domain
    - orange: infrastructure
    - red: quality + debugging
    - yellow: SDLC process
    - blue: business intelligence
    - purple: product + design
    - pink: creative / external

  memory:
    Set to "project" if the agent has a persistent memory directory.
    Omit if the agent is stateless across conversations.

WHEN TO INVOKE (body section):
  Goes right after the opening scope paragraphs, before every other section. 2-4 scenario bullets,
  plus seam bullets for the confusable siblings, 5 bullets at most; past 5, merge scenarios first,
  and one seam bullet may cover several siblings. A confusable sibling is an agent a look-alike
  request could route to instead: an agent the Do-NOT-use boundary names. Each bullet starts with a bold short scenario name (a seam bullet's
  name starts with "Seam:"), then the situation in third person (what just happened, or what the
  user asks for in any phrasing) and what this agent should do. Cover an explicit request and,
  where it applies, a proactive trigger. No quoted utterances and no user:/assistant: turn markers.
  Collapse phrasings of one intent into one bullet.
  Name every scenario bullet (not the seam bullets) in the description's typical triggers, in the
  same order: routing reads only the description. A seam bullet is covered by the seam sentence or
  the Do-NOT-use boundary.
-->

You own [scope — what directories, packages, or domains this agent is responsible for]. You do not touch [explicit boundaries — what belongs to other agents]. [When cross-domain work is needed, describe the handoff pattern.]

Your domain expertise covers [technologies, frameworks, and patterns this agent is deeply familiar with].

## When to invoke

- **[Short scenario name].** [The situation in third person: what just happened, or what the user is asking for in any phrasing. Then what this agent should do.]
- **[Short scenario name].** [Another trigger: an explicit request, or a proactive one where the assistant should call this agent without being asked.]
- **Seam: [the look-alike request the Do-NOT-use boundary sends to a sibling].** [The situation, and the agent it belongs to instead.]

## Knowledge Context

Before starting substantive work, consult `[sdlc-root]/knowledge/agent-context-map.yaml` and find your entry. Read the mapped knowledge files — they contain reusable patterns, anti-patterns, and domain-specific guidance relevant to your work.

## [Core Mission / Your Domain]

[Project-specific context that grounds this agent. What does this agent's domain look like in this specific project? Key abstractions, patterns, file locations, and architectural decisions the agent needs to internalize.]

## Communication Protocol

Read `[sdlc-root]/knowledge/architecture/agent-communication-protocol.yaml` and follow the canonical agent communication protocol it defines. Send short plain-text progress updates to the orchestrator during longer tasks (the protocol's `delivery` section says how) and complete every task with a structured handoff.

[Domain]-specific handoff fields (in addition to the canonical modified files and follow-up):
- **[Field]**: [What to include and why]
- **[Field]**: [What to include and why]

## Core Principles

### [Concern Area 1]
- [Concrete principle with rationale]
- [Concrete principle with rationale]

### [Concern Area 2]
- [Concrete principle with rationale]
- [Concrete principle with rationale]

## Workflow

1. **[First step]**: [What to do and why — e.g., check existing patterns before inventing new ones]
2. **[Second step]**: [What to do and why]
3. **[Third step]**: [What to do and why]

## Anti-Rationalization Table

| Thought | Reality |
|---------|---------|
| "[Common shortcut this agent might take]" | [Why it's wrong and what to do instead] |
| "[Another rationalization]" | [The correct approach] |

## Self-Verification Checklist

Before presenting any implementation:
- [ ] [Domain-specific quality check]
- [ ] [Domain-specific quality check]
- [ ] [Domain-specific quality check]
- [ ] No changes outside this agent's owned scope
- [ ] Structured handoff emitted with modified files and follow-up items

# Persistent Agent Memory

You have a persistent memory directory at `{project_root}/.claude/agent-memory/{agent-name}/`. Its contents persist across conversations.

Guidelines:
- **`MEMORY.md` is an index, not a logbook.** Claude Code loads only the first **200 lines or 25KB, whichever comes first** — anything past that is silently truncated and invisible to you in future sessions. Because entries are appended at the bottom, it's your *newest* notes that get dropped. Keep MEMORY.md lean: short summaries and pointers, with detail pushed to topic files.
- **Split before you hit the cap.** When MEMORY.md approaches ~180 lines (or any single topic outgrows a handful of lines), move that topic's detail into a topic file and leave a one-line pointer behind. Don't wait for truncation to start eating your notes.
- **Topic files live beside MEMORY.md and are uncapped.** Create them at `.claude/agent-memory/{agent-name}/{topic}.md` (kebab-case, e.g. `flip-timing-rules.md`) and link each from MEMORY.md: `- [Flip timing rules](flip-timing-rules.md) — <one-line summary>`. Topic files are read on demand, so they have no size limit.
- **Update or remove memories that turn out to be wrong or outdated** — in both MEMORY.md and topic files. A memory that contradicts current code is worse than no memory. When you restate a tuned value, replace the old line; don't leave two copies with drifted numbers.
- **Never save a secret, credential, token or environment-variable value.** Memory files are plain text: git-ignored, but readable by anything that reads the project directory.
- Organize memory semantically by topic, not chronologically.

What to save: [domain-specific examples — e.g., "stable patterns, key decisions, recurring problems"].
What NOT to save: session-specific context, incomplete info, CLAUDE.md duplicates.

**Update your agent memory** as you discover [domain-specific patterns] in this codebase.

## Surfacing Learnings to the SDLC

Agent memory is your private scratchpad — it is **not git-tracked**. If you discover something that would benefit the team or future sessions beyond your own, surface it through the proper SDLC channels:

- **Include a `knowledge_feedback` section in your handoff** when you notice knowledge gaps, find loaded files unhelpful, or wish a pattern had been documented. The orchestrator uses this during discipline capture. Read `[sdlc-root]/knowledge/architecture/agent-communication-protocol.yaml` for the handoff schema.
- **Reusable patterns, anti-patterns, and domain gotchas** belong in knowledge stores (`[sdlc-root]/knowledge/`), not agent memory. If you discover something general enough to help other agents or future deliverables, flag it in your handoff so the orchestrator can route it to discipline capture or a knowledge store update.
- **Your memory is for you; knowledge stores are for everyone.** Save codebase-specific shortcuts and session-to-session continuity here. Save transferable domain knowledge through the SDLC pipeline.
