---
name: sdlc-port-opencode
description: >
  Adapt an existing z-sdlc installation to work with OpenCode agents alongside Claude Code.
  OpenCode natively discovers .claude/skills/ and falls back to CLAUDE.md, so skills and the
  shared [sdlc-root] content are used as-is by both tools — no duplication. This skill ports the
  parts OpenCode does NOT auto-discover: it creates .opencode/agents/ from .claude/agents/ with
  tool-name and frontmatter mapping, generates AGENTS.md from CLAUDE.md SDLC content, and scaffolds
  opencode.json (provider, model, mcp, permission) — including wiring a local OpenAI-compatible model
  endpoint when present. Does NOT remove or replace the Claude Code setup — it adds OpenCode
  compatibility alongside it.
  Use when an existing z-sdlc project needs OpenCode compatibility alongside its Claude Code setup.
  Triggers on "port to opencode", "make this work with opencode", "opencode compatibility",
  "wire for opencode", "adapt for opencode", "opencode setup", "/sdlc-port-opencode".
  Do NOT use for full framework migration or updates — use sdlc-migrate.
  Do NOT use for initial SDLC installation — use sdlc-initialize.
  Do NOT use for Claude Code-only configuration — use sdlc-migrate.
---

# Port SDLC to OpenCode

Adapt an existing z-sdlc installation so the project's SDLC agents, skills, and process documentation work with [OpenCode](https://opencode.ai). This creates a parallel `.opencode/` structure and an `AGENTS.md` alongside the existing `.claude/` setup — it **does not remove or replace anything**.

**Argument:** `$ARGUMENTS` (optional: specific components to port, e.g., "agents only", "config only")

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## What OpenCode discovers natively (do NOT port these)

OpenCode shares more with Claude Code than people expect. Confirmed against OpenCode docs (`opencode.ai/docs/skills`, `/rules`):

- **Skills** — OpenCode reads `.claude/skills/*/SKILL.md` directly (walking from cwd up to the git root), in addition to `.opencode/skills/`. **The project's existing SDLC skills already work in OpenCode.** Copying them into `.opencode/skills/` would register the same skill name twice — a collision. So this skill does **not** fork skills.
- **Instructions fallback** — OpenCode reads `AGENTS.md` first and falls back to `CLAUDE.md`. We still generate `AGENTS.md` because it carries OpenCode-correct tool references; `AGENTS.md` takes precedence when both exist.
- **`[sdlc-root]` content** — process docs, knowledge, disciplines, templates, playbooks are plain markdown/YAML read identically by both tools. Never duplicated.

What OpenCode does **not** auto-discover from the Claude Code layer — and what this skill therefore ports — is **agents** (OpenCode reads `.opencode/agents/`, not `.claude/agents/`) and **config** (`opencode.json`).

## Preconditions

- The project must have an existing z-sdlc installation (`.claude/skills/`, `.claude/agents/`, `CLAUDE.md` with SDLC sections)
- Verify with `ls .claude/skills/ .claude/agents/` and check `CLAUDE.md` exists
- If preconditions fail, tell the user to run `/sdlc-initialize` first

## Workflow

```
SURVEY → SCAFFOLD → AGENTS.MD → ADAPT AGENTS → VERIFY SKILLS (shared) → CONFIG → GAPS → REPORT
```

### 1. Survey Existing Installation

Read the project's current Claude Code SDLC setup:

1. `ls .claude/agents/` — list installed agent definitions
2. `ls .claude/skills/` — list installed skill directories (these stay where they are)
3. Read `CLAUDE.md` — identify SDLC sections (look for `## SDLC Process` header)
4. Read `.sdlc-manifest.json` if it exists — determine `[sdlc-root]` path
5. Check for existing `.opencode/` and `AGENTS.md` — if present, ask the user whether to overwrite or skip
6. Ask the user whether they will run OpenCode against a **local model endpoint** (vLLM / llama.cpp / Ollama / LM Studio) or a hosted provider — this determines the `provider`/`model` block in Step 6. If local, get the base URL (e.g. `http://localhost:8000/v1`) and the model id the endpoint serves.

Report the inventory to the user before proceeding.

### 2. Scaffold .opencode/ Structure

Create only the directories OpenCode does not share from `.claude/`:

```
.opencode/
├── agents/        # Adapted agent definitions (OpenCode does NOT read .claude/agents/)
└── commands/      # Custom commands (empty initially; optional)
```

Use plural directory names (`agents/`, `commands/`) — these are the names in OpenCode's docs. (The engine also accepts singular `agent/`/`command/`, but follow the documented plural form.) Create with `mkdir -p`. Add a `.gitkeep` to `commands/` if left empty.

**Do NOT create `.opencode/skills/`** — OpenCode discovers `.claude/skills/` directly, and a duplicate `.opencode/skills/` would collide on skill names.

### 3. Generate AGENTS.md

Create `AGENTS.md` in the project root from the SDLC content in `CLAUDE.md`. OpenCode reads `AGENTS.md` as its instructions file (the equivalent of `CLAUDE.md`) and prefers it over `CLAUDE.md` when both exist.

**What to copy:** All SDLC sections — process rules, verification policy, commit rules, debugging escalation, agent conventions. The goal is a complete OpenCode-correct instructions file.

**Adaptation rules:**

| Pattern in CLAUDE.md | Replacement in AGENTS.md |
|---------------------|-------------------------|
| "CC (Claude Code)" | "OC (OpenCode)" |
| `.claude/agents/` | `.opencode/agents/` |
| `.claude/skills/` | `.claude/skills/` (unchanged — OpenCode reads it directly) |
| `.claude/agent-memory/` | (omit or note as unavailable) |
| `AskUserQuestion` tool references | `question` tool (OpenCode's ask-the-user tool) |
| `Agent(subagent_type='...')` | `Task` tool / `@agent-name` mention (see Tool Mapping) |
| `Skill` tool | `skill` tool (`skill({ name: "..." })`) |
| `SendMessage` tool | (no equivalent — note as a gap; subagents return results to the caller) |
| Claude Code-specific tool table | OpenCode tool equivalents (see Tool Mapping) |

**Preserve unchanged:**
- All SDLC process rules and workflow documentation
- `[sdlc-root]` references (these resolve the same way for both tools)
- Verification policy, commit rules, debugging escalation
- Role definitions (CD stays "Claude Director" — the human role is tool-agnostic)

Add a header to AGENTS.md (substitute the actual resolved path from Step 1 for `{sdlc-root-path}`):

```markdown
<!-- Generated by sdlc-port-opencode from CLAUDE.md. Shared SDLC content lives in {sdlc-root-path}/. Skills are read from .claude/skills/ by OpenCode directly. -->
```

**Note:** In the adapted body content, keep `[sdlc-root]` as a literal placeholder — it is resolved at runtime, the same way it works in CLAUDE.md. Only the header comment gets the concrete path for human orientation.

**Do NOT modify the original CLAUDE.md.**

### 4. Adapt Agent Definitions

For each `.md` file in `.claude/agents/` (skip `AGENT_SUGGESTIONS.md` if present):

1. Read the agent file
2. Create a copy in `.opencode/agents/{name}.md`
3. Apply these adaptations:

**Frontmatter** — OpenCode agent frontmatter fields: `description`, `mode`, `model`, `temperature`, `tools`, `permission`, `color`, `disable`, `hidden`.

- **`description`**: Claude Code agents use a double-quoted single line with `\n`; OpenCode accepts a `>` folded scalar. Convert to a `>` folded scalar, unescaping `\n` to real line breaks.
- **`mode`**: Add `mode: subagent`. z-sdlc framework agents are dispatched by orchestrating skills, not interacted with directly — `subagent` is correct. (Use `primary` only for an agent meant to be a top-level driver, which z-sdlc agents are not.)
- **`model`**: Claude Code uses bare tier names (`sonnet`/`opus`/`haiku`). OpenCode requires `provider/model-id` format (e.g. `anthropic/claude-sonnet-5-5`, or `local/qwen3-coder` for a local endpoint). **Prefer omitting `model` entirely** — an OpenCode subagent then inherits the invoking primary's model, which keeps the project's default (set once in `opencode.json`) authoritative and sidesteps Claude-specific tier names. Only set an explicit `model` when an agent genuinely needs a different tier than the default; resolve it to the project's configured OpenCode provider/model.
- **`tools`**: If the Claude Code agent restricts tools, translate the allowed set using the Tool Mapping table (e.g. `Read, Grep, Glob` → `read`, `grep`, `glob`). Omit if the agent had no restriction.

**Tool references in the body:** Apply the Tool Mapping table (§ Tool Mapping). Replace Claude Code tool invocation patterns with OpenCode equivalents.

**Path references:**
- `.claude/agents/` → `.opencode/agents/`
- `.claude/skills/` → `.claude/skills/` (unchanged — shared)
- `.claude/agent-memory/{name}/` → note as unavailable (OpenCode has no persistent per-agent memory)

**Preserve unchanged:**
- All domain knowledge, rules, methodologies, and behavioral instructions
- `[sdlc-root]` references
- Knowledge routing phrases (these are part of the adapter contract)

### 5. Verify Skills Are Discovered (do not copy)

Skills are **not** ported — OpenCode reads `.claude/skills/*/SKILL.md` directly. Confirm this works rather than duplicating:

1. Note in the report that skills remain in `.claude/skills/` and are shared by both tools.
2. **Tool-reference caveat:** SDLC skill *bodies* may contain Claude Code tool names (`Agent(subagent_type=...)`, `AskUserQuestion`, `Skill`). OpenCode exposes equivalents under different names (`Task`/`@mention`, `question`, `skill`). A capable model usually bridges the synonym, but a weaker/local model may not.
   - Do **NOT** fork adapted skill copies into `.opencode/skills/` — OpenCode reads both trees and would register each skill name twice (collision).
   - The correct long-term fix is to make the *source* skills use tool-agnostic action language ("ask the user", "dispatch the {agent}", "invoke the {skill}") so one copy works in both harnesses. Flag any skills with hard Claude-Code tool references in the report as candidates for that change — do not rewrite shared skills as part of this port unless the user asks.

### 6. Create opencode.json

Generate `opencode.json` (or `opencode.jsonc`) in the project root. Agents and skills are auto-discovered from the filesystem, so the config's job is provider/model/mcp/permission — **there is no `agents` map**.

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "<provider>/<model-id>",
  "permission": {
    "edit": "ask",
    "bash": "ask"
  }
}
```

**Before writing:** Confirm the current schema URL and field names from `opencode.ai/docs/config` or `opencode --help`. The schema URL is `https://opencode.ai/config.json` at time of writing.

**Local model endpoint (from Step 1).** If the user runs a local OpenAI-compatible endpoint, add a `provider` block and point `model` at it. Use `@ai-sdk/openai-compatible` for any vLLM / llama.cpp / LM Studio / custom endpoint; the model ids under `models` must match what the endpoint's `GET /v1/models` returns:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "local": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Local (vLLM/llama.cpp)",
      "options": { "baseURL": "http://localhost:8000/v1" },
      "models": { "qwen3-coder": { "name": "Qwen3-Coder" } }
    }
  },
  "model": "local/qwen3-coder",
  "small_model": "local/qwen3-coder"
}
```

For **Ollama**, use `"baseURL": "http://localhost:11434/v1"`. If tool-calls fail on a local model, raise the served context window (Ollama: `num_ctx` ~16k–32k) — the SDLC skills are long and tool-call-heavy.

**For a concrete, model-specific serving guide** — recommended models (Qwen3.6 family), GGUF quant selection for ~48 GB, the **llama.cpp** tool-call chat-template fixes (without which tool calls break under long SDLC prompts), `llama-server` launch flags for dual-GPU, and OpenCode wiring — see `references/local-model-serving.md`. The block above is the general pattern; that doc is the battle-tested specifics for the llama.cpp path.

**MCP.** If the project uses Context7 (check CLAUDE.md / `.mcp.json` for `context7` or `mcp__context7`), wire it under `mcp`:

```jsonc
{
  "mcp": {
    "context7": { "type": "local", "command": ["npx", "-y", "@upstash/context7-mcp"], "enabled": true }
  }
}
```

(Confirm the project's actual context7 launch command from its existing `.mcp.json` / `.claude/settings.json` rather than assuming the example above.)

### 7. Document Compatibility Gaps

Create `.opencode/COMPAT_GAPS.md`. Statuses below reflect OpenCode's documented feature set; re-confirm against the user's installed OpenCode version (`opencode --version`).

```markdown
# OpenCode Compatibility Notes

How the Claude Code SDLC setup maps onto OpenCode. Re-confirm against your OpenCode version.

| Claude Code Feature | OpenCode Status | Mapping / Workaround |
|--------------------|-----------------|----------------------|
| `Agent` tool (typed subagent dispatch) | Available | `Task` tool (model-invoked) + `@agent-name` mention (user-invoked); gate with `permission.task` |
| `AskUserQuestion` (structured prompts) | Available | `question` tool |
| `Skill` tool | Available | `skill` tool — `skill({ name: "..." })`; gate with `permission.skill` |
| `WebFetch` / `WebSearch` | Available | `webfetch` / `websearch` |
| Skills auto-discovery | Available | OpenCode reads `.claude/skills/` directly — no port needed |
| `CLAUDE.md` instructions | Available | `AGENTS.md` (preferred) with `CLAUDE.md` fallback |
| Context7 / LSP MCP | Available | Configure under `mcp` / `lsp` in opencode.json |
| `SendMessage` (inter-agent messaging) | Not available | Subagents return results to the caller; no peer-to-peer messaging |
| `.claude/agent-memory/` (session state) | Not available | No persistent per-agent memory across sessions |
| `EnterWorktree` / `ExitWorktree` | Not available | Manual `git worktree` commands |
| `TaskCreate` / `TaskUpdate` (task tracking) | Partial | `todowrite` for in-session task lists; external tracking otherwise |
| `Monitor` (background streaming) | Not available | Bash polling loops |
| `CronCreate` / `ScheduleWakeup` | Not available | External scheduling (cron, systemd timer) |
| `PushNotification` | Verify | Terminal/desktop notification per OpenCode version |
```

### 8. Report

Output a summary:

```markdown
## OpenCode Port Summary

| Component | Source | Target | Notes |
|-----------|--------|--------|-------|
| Agents | .claude/agents/ | .opencode/agents/ | N adapted |
| Skills | .claude/skills/ | (shared) | Read directly by OpenCode — not copied |
| Instructions | CLAUDE.md | AGENTS.md | 1 generated |
| Configuration | — | opencode.json | provider/model/mcp/permission |
| Gaps doc | — | .opencode/COMPAT_GAPS.md | 1 |

### Manual Follow-up
- [ ] Run `opencode` and confirm SDLC skills appear (discovered from .claude/skills/)
- [ ] Dispatch one ported agent (via `@agent-name`) to confirm wiring works
- [ ] If using a local model, confirm tool-calls succeed; raise served context if they fail
- [ ] Review AGENTS.md for any remaining Claude Code-specific language
- [ ] Review flagged skills with hard Claude-Code tool references (Step 5 caveat)
```

## Tool Mapping

Use this table when adapting agent files and AGENTS.md. OpenCode's built-in tool identifiers are lowercase. Confirmed against `opencode.ai/docs/tools`.

| Claude Code | OpenCode | Adaptation |
|-------------|----------|------------|
| `Read` | `read` | Lowercase identifier |
| `Write` | `write` | Lowercase; gated by `edit` permission |
| `Edit` | `edit` | Lowercase identifier |
| `Bash` | `bash` | Lowercase identifier |
| `Glob` | `glob` | Lowercase identifier |
| `Grep` | `grep` | Lowercase identifier |
| `LSP` | `lsp` | Experimental in OpenCode; same concept |
| (patch / apply) | `apply_patch` | OpenCode names it `apply_patch`, not `patch` |
| `Agent(subagent_type=...)` | `Task` tool + `@agent-name` | Model dispatches via `Task`; users via `@mention`; restrict with `permission.task` |
| `Skill` tool | `skill` | `skill({ name: "..." })`; restrict with `permission.skill` |
| `AskUserQuestion` | `question` | OpenCode's ask-the-user tool |
| `WebFetch` | `webfetch` | Confirmed available |
| `WebSearch` | `websearch` | Confirmed available |
| `SendMessage` | (none) | No inter-agent messaging — flag as gap |
| `TaskCreate` / `TaskUpdate` | `todowrite` | In-session todos only; no harness-level tasks |
| `EnterWorktree` / `ExitWorktree` | (none) | Manual `git worktree` |
| `Monitor` | (none) | Bash polling |
| `CronCreate` / `ScheduleWakeup` | (none) | External scheduler |
| Context7 MCP | Context7 MCP | Same server; configure under `mcp` in opencode.json |

**No-equivalent strategy:** where OpenCode has no tool (SendMessage, Monitor, worktree, cron), write the adapted file with generic action language and add `<!-- opencode: no direct equivalent — see COMPAT_GAPS.md -->` so the user can see what degraded.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll copy the skills into `.opencode/skills/` too" | OpenCode reads `.claude/skills/` directly. A duplicate copy registers each skill name twice — a collision. Skills are shared, not forked. |
| "I'll just copy the agent files without adapting tool references" | OpenCode tool names are lowercase and orchestration tools differ (`Task`, `question`, `skill`). Every agent must go through the mapping. |
| "I'll remove the .claude/ directory to avoid confusion" | This skill creates PARALLEL compatibility. Never remove the Claude Code setup. |
| "opencode.json needs an `agents` map listing every agent" | Agents auto-discover from `.opencode/agents/`. The config is for provider/model/mcp/permission, not an agent registry. |
| "Set each agent's `model` to its old Claude tier name" | OpenCode needs `provider/model-id`. Prefer omitting `model` so subagents inherit the project default — especially for local models with no Claude tiers. |
| "The SDLC process content needs rewriting for OpenCode" | Process rules are tool-agnostic. Only tool interface references change. |
| "I'll modify CLAUDE.md to also work with OpenCode" | CLAUDE.md stays untouched. AGENTS.md is the parallel OpenCode instructions file and takes precedence. |
| "Agent domain knowledge needs adaptation" | Domain knowledge (rules, patterns, methodologies) is tool-agnostic. Only adapt the tooling interface. |
| "I'll skip the compatibility gaps document" | Users need to know what doesn't map (SendMessage, agent-memory, worktrees). The gaps doc prevents trial-and-error frustration. |
| "I should duplicate [sdlc-root] content for OpenCode" | `[sdlc-root]` content is shared. Both tools read the same process docs, knowledge stores, and disciplines. Never duplicate. |
| "I'll skip the changelog update" | Changelog entries happen in the same step as the work. Not later. |

## Integration

- **Depends on:** Existing z-sdlc installation (`sdlc-initialize` must have run first)
- **Feeds into:** OpenCode-based development using the same SDLC process and knowledge layer, including against a local model endpoint
- **Uses:** `.claude/agents/`, `.claude/skills/` (read in place), `CLAUDE.md`, `.sdlc-manifest.json`, `[sdlc-root]` content
- **Complements:** `sdlc-initialize` (creates the Claude Code installation this skill reads from), `sdlc-migrate` (updates the Claude Code installation — re-run this skill after migration if OpenCode agent files or config need updating)
- **Does NOT replace:** `sdlc-initialize` (this adapts, doesn't install), `sdlc-migrate` (this is a one-time port, not ongoing sync)
- **DRY notes:** `[sdlc-root]` content AND `.claude/skills/` are shared between both tools and are NOT duplicated — OpenCode discovers skills natively. Only the agent layer (`.claude/agents/` → `.opencode/agents/`) and instructions (`CLAUDE.md` → `AGENTS.md`) are ported, plus a new `opencode.json`. After running `sdlc-migrate` to update the Claude Code layer, re-run this skill to sync `.opencode/agents/` and `AGENTS.md`.
