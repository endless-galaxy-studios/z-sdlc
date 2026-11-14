# Parallel Dispatch Monitoring

Protocol for detecting and resolving stuck, blocked, or imbalanced agents during parallel dispatch. Referenced by orchestration skills that fan out to multiple agents in a single round.

## When This Applies

Any skill step that dispatches 2+ agents in parallel. Single-agent dispatches and sequential dispatch chains do not need this protocol — their completion is self-evident.

## Detection Signals

| Signal | How to detect | Action |
|--------|---------------|--------|
| **Stuck agent** | Agent returns no file changes and no structured findings after a reasonable execution window | Re-dispatch with tighter scope, or dispatch `debug-specialist` to diagnose the blocker |
| **BLOCKED signal** | Agent explicitly reports it cannot proceed (missing dependency, permission denied, ambiguous requirement) | Resolve the blocker before dispatching any work that depends on this agent's output |
| **Workload imbalance** | One agent's dispatch covers 3x+ the files or findings of its peers | Split the overloaded agent's work into two dispatches, or accept the imbalance if the work is indivisible |
| **File conflict** | Two agents report changes to the same file (detected via `git status` post-dispatch) | Revert nothing: re-dispatch the overwritten agent with the current file state and instructions to re-apply its changes (`[sdlc-root]/process/manager-rule.md` § No Exceptions for Scope or Completeness) |
| **Idle agent** | Agent completes while peers are still running | Stand the agent down — do not invent busywork. Note completion in the dispatch log. |

## Monitoring Protocol

### Before parallel dispatch

1. **Log the dispatch set.** Record which agents are dispatched, what each is expected to produce, and the expected completion signal (file changes, structured report, or both).
2. **Identify the critical path.** If any agent's output feeds another's input, that dependency must be sequential — do not parallelize it.

### After parallel dispatch returns

3. **Read every agent's output before deciding next steps.** Do not act on the first agent's result while others are still pending. The full picture may change the interpretation of early results.
4. **Check for file conflicts.** Run `git diff --stat` after all agents return. If two agents modified the same file, the second write silently overwrote the first — verify the merge is correct or re-dispatch.
5. **Check for BLOCKED signals.** If any agent reported it could not complete, resolve the blocker before dispatching dependent work.

### Stuck-agent recovery

6. **3-strike rule.** If the same agent fails to produce expected output 3 times (across re-dispatches with revised prompts), escalate to the user rather than continuing to re-dispatch. Document what was tried.
7. **Prompt revision, not repetition.** Re-dispatching with the identical prompt is not recovery — it is hoping for a different outcome. Change the prompt: add more context, tighten scope, or decompose the task further.

### Rebalancing

8. **Split, don't redistribute.** When one agent has disproportionate work, split its task into independent subtasks rather than reassigning to an agent with a different specialization. The overloaded agent's domain knowledge is the reason it was assigned — a different agent would produce lower-quality output.
9. **Stand down idle agents explicitly.** An agent that finishes early does not need new work unless there is genuinely independent work remaining. Do not create tasks to keep agents busy.

## Integration with POST-GATE

For skills that use PRE-GATE / POST-GATE discipline (sdlc-execute, sdlc-lite-execute), the monitoring protocol runs between EXECUTE and POST-GATE:

```
PRE-GATE → EXECUTE (parallel dispatch) → MONITOR (this protocol) → POST-GATE
```

POST-GATE verifies the output quality. This protocol verifies the dispatch health.

## Anti-Patterns

| Anti-pattern | Why it fails |
|--------------|-------------|
| Acting on the first agent's result without waiting for peers | Partial information leads to premature decisions that the remaining results may contradict |
| Re-dispatching with the same prompt after failure | The prompt is the variable — if it didn't work, change it |
| Serializing planned-parallel work to "avoid conflicts" | This hides the decomposition defect rather than fixing it; the same conflict will recur |
| Inventing work for idle agents | Busywork wastes tokens and produces low-quality output that must be reviewed and potentially reverted |
| Ignoring BLOCKED signals and dispatching downstream work | The downstream work will fail or produce incorrect results because its input is missing |
