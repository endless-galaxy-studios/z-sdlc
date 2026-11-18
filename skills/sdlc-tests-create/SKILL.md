---
name: sdlc-tests-create
description: >
  Generate integration and E2E test suites for completed work by dispatching domain experts
  for coverage gap analysis and the SDET agent for implementation. Two-phase approach: domain
  agents audit what needs testing, SDET builds the tests. Prioritizes integration and E2E
  tests that exercise real application behavior over isolated unit tests.
  Use when completed work needs test coverage — after a deliverable, execution phase, or significant code change.
  Trigger when someone says "create tests", "write tests", "generate test suite",
  "create test suite", "test this work", "write tests for this", or after completing
  a deliverable or SDLC-Lite execution.
  Do NOT use for running or fixing existing tests — use sdlc-tests-run for that.
  Do NOT use for trivial single-file changes with no branching logic — direct SDET dispatch
  is sufficient when the scope is one pure function with obvious test cases.
---

# Create Test Suite

Two-phase test creation: domain experts identify what needs testing, SDET implements the tests. You are the manager — you gather scope, run the coverage inventory, dispatch domain experts for gap analysis, synthesize their findings into a test brief, then dispatch SDET to implement. Hand off to `sdlc-tests-run` when done.

## Testing Philosophy

**Integration and E2E tests are the standard.** These test real application behavior — actual HTTP requests, real database queries, genuine service interactions. Unit tests are appropriate only for pure functions with complex logic (validators, parsers, state machines). Do not create unit tests for simple getters, trivial wrappers, or code that's already exercised by integration tests.

**No useless tests.** Every test must verify behavior a user or operator cares about. "Does this function return the right type" is not a useful test. "Does completing checkout result in an active subscription" is.

**Test the workflow, not the pieces.** Testing individual functions in isolation and the orchestrator in isolation can leave the entire end-to-end chain (the actual business logic) untested. Integration tests should exercise the full chain — from entry point to final state change.

## Collaboration Model

The full model is in `[sdlc-root]/process/collaboration_model.md` (role definitions, decision authority table, autonomy spectrum). The critical directives:

**AskUserQuestion mandate:** every question directed at the user MUST use the `AskUserQuestion` tool — do not type questions as conversational text. Status updates and completion reports that need no response use normal text.

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Two exceptions stand: the skill's own knowledge-layer updates count as local work, even when an adapter writes them to its memory store (a subagent's own memory-store writes don't), and the External Review Gate may send to a hosted provider the project has durably authorized (`[sdlc-root]/process/external-review-gate.md` § Data egress). Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

**Anti-patterns to avoid:** (1) code assertion without verification — never answer "how does X work" from memory; grep/read the code first; (2) trajectory poisoning — if the agent is off track after 2-3 corrections, clear context and start fresh rather than continuing to correct in a poisoned trajectory.

## Manager Rule

**You are the manager — you orchestrate, you do not implement.** The canonical rule is in `[sdlc-root]/process/manager-rule.md`. **You never write test code.** The SDET agent designs test cases, implements tests, and fixes test compilation issues. If you notice a gap in test coverage, dispatch SDET to address it. Do not write test files, fixtures, or helpers yourself.

- **Failed dispatch:** if SDET returns without applying its work, re-dispatch — do not write the tests yourself.
- **Session scope:** this rule stays active for the entire session. There is no post-commit wind-down mode.

## Step 0: Identify Scope

Determine what work needs tests. If the user didn't specify, ask:

```
What work should I create tests for?

1. The current SDLC deliverable plan (docs/current_work/planning/)
2. The current SDLC-Lite plan (docs/current_work/sdlc-lite/)
3. A specific commit (provide SHA or "HEAD")
4. Unstaged changes in the working tree
```

Use `AskUserQuestion` — do not type this as conversational text.

If the user already specified scope or passed arguments, skip the question. User-requested test cases are passed as skill arguments — do not ask separately.

### Scope Resolution

| Source | How to gather context |
|--------|----------------------|
| SDLC plan | Read `docs/current_work/planning/dNN_name_plan.md` — extract phases, files, acceptance criteria |
| SDLC-Lite plan | Read `docs/current_work/sdlc-lite/dNN_{slug}_plan.md` — extract phases, files, acceptance criteria |
| Specific commit | Run `git show --stat {sha}` + `git diff {sha}~1 {sha}` — extract changed files and diff |
| Unstaged changes | Run `git diff` + `git diff --cached` — extract changed files and diff |

Extract from the scope:
1. **Changed files** — what was created or modified
2. **Packages affected** — which packages or layers
3. **User-facing behavior** — what a user would interact with
4. **Acceptance criteria** — from plan if available, otherwise infer from the diff

## Step 1: Coverage Inventory (Mandatory)

**Do not skip this step.** File-level scoping ("17 integration tests exist") masks function-level gaps ("none of the webhook handlers are tested end-to-end"). This step builds the actual inventory.

### 1a. Build the Implementation Inventory

For each implementation file in scope, list every public function/method/endpoint:

```
Implementation Inventory:

| File | Function/Endpoint | Type | Description |
|------|------------------|------|-------------|
| services/billing_service.py | create_checkout_session | async | Creates checkout, returns URL |
| jobs/processor.py | process_event | job | Dispatches to event handlers |
| jobs/processor.py | _handle_completed | handler | Full completion→activation flow |
| routers/billing.py | POST /checkout-session | endpoint | Auth + service + response |
...
```

Include private functions that contain significant business logic (like `_handle_*` or `_classify_*`). Skip trivial helpers.

### 1b. Map Existing Test Coverage

For each function in the inventory, check if existing tests cover it:

```
Coverage Map — {N} functions inventoried, {M} gaps identified ({K} critical)

| Function | Tested By | Coverage Level | Gap |
|----------|-----------|---------------|-----|
| create_checkout_session | test_integration:TestCheckout | Integration (isolated) | Not tested as part of full chain |
| _handle_completed | NOT TESTED | None | Full handler chain untested |
| POST /checkout-session | test_endpoints:TestCreate | Endpoint (mocked service) | Happy path + auth covered |
...
```

**Coverage levels:**
- **None** — no test touches this function
- **Unit (isolated)** — tested in isolation with mocks
- **Integration (isolated)** — tested with real DB but not as part of a workflow
- **Integration (chain)** — tested as part of a realistic workflow end-to-end
- **Endpoint** — tested via HTTP request through the full stack

**The goal is "Integration (chain)" or "Endpoint" for every function that contains business logic.** Unit (isolated) and Integration (isolated) are insufficient for workflow functions — they prove the piece works alone but not that the pieces work together.

## Step 2: Domain Expert Gap Analysis

**Dispatch ALL relevant domain agents to audit the coverage map.** The SDET knows testing patterns but doesn't have deep domain knowledge of (for example) webhook lifecycle, subscription state machines, or recovery flows. Domain experts catch gaps the SDET would miss. Each agent's perspective matters — do not subset. Read `[sdlc-root]/knowledge/architecture/agent-orchestration-patterns.yaml` for AOP2 (decompose by concern for review work) and AOP5 (group sizing).

### Which agents to dispatch

Use `[sdlc-root]/process/agent-selection.yaml` to identify which agents to dispatch. For lenses, see `[sdlc-root]/process/review-lenses.md` — test gap analysis uses the **coverage**, **security at boundaries**, **contract safety**, **performance**, **data integrity**, and **standard** lenses (not overengineering or type safety — those are review-only).

- If a plan exists: read the `agents:` frontmatter list as the starting set
- If no plan exists (commit or unstaged scope): match changed files against the Tier 1 agent selection rules in `agent-selection.yaml`
- Add agents if the Coverage Map reveals domains not in the initial set

**Dispatch every agent identified — not a subset.** Each agent reviews the coverage map and reports gaps from their domain perspective. Output a checklist before dispatching:

```
Gap analysis — dispatching:
- [ ] agent-name-1
- [ ] agent-name-2
- [ ] agent-name-3
```

Every checkbox must have a corresponding dispatch. Each agent receives:

```
Review the implementation code and the existing test coverage map below.
Identify workflows, edge cases, and critical paths that are NOT covered
by existing tests. Focus on:

1. End-to-end workflows that cross function boundaries
2. State machine transitions and their edge cases
3. Error handling paths that affect user-visible behavior
4. Integration points (external APIs, DB transactions, job queues)

Do NOT suggest unit tests for simple functions already covered by
integration tests. Focus on gaps where real behavior is untested.

IMPLEMENTATION FILES:
[list all implementation files]

EXISTING COVERAGE MAP:
[paste the coverage map from Step 1b]

Output a prioritized gap list:
| Gap | What's Untested | Suggested Test Type | Priority |
```

### Synthesize findings

Collect all domain agent findings. Deduplicate (multiple agents may flag the same gap). Produce the **Test Brief** — the definitive list of what the SDET should implement:

```
Test Brief:

COVERAGE GAPS (from domain expert analysis):
[deduplicated, prioritized list]

EXISTING TESTS (do not duplicate):
[list of existing test files and what they cover]

USER-REQUESTED TEST CASES:
[from skill arguments, or "None specified"]
```
## Step 3: Dispatch SDET to Implement

Dispatch `sdet` with the Test Brief and full implementation context.

**Cross-domain knowledge injection:** Consult `[sdlc-root]/knowledge/agent-context-map.yaml` for the agents who built the feature being tested and include their domain knowledge files in the SDET's dispatch prompt.

The dispatch prompt must include:
- The Test Brief from Step 2 (coverage gaps, existing tests, user requests)
- The Implementation Inventory from Step 1a (every function to consider)
- Cross-domain knowledge file paths from the feature's domain agents
- **Library verification instructions** (when tests involve external library APIs): verify API usage via Context7 before writing tests
- These instructions:

```
Implement tests based on the Test Brief below. Domain experts have
identified the coverage gaps — your job is to implement tests that
close them.

TEST BRIEF:
[paste from Step 2]

IMPLEMENTATION INVENTORY:
[paste from Step 1a]

GUIDELINES:
- Read `[sdlc-root]/knowledge/testing/testing-paradigm.yaml` and apply the testing paradigm it defines
- Consult `[sdlc-root]/knowledge/testing/advanced-test-patterns.yaml` for Playwright CI config, custom fixture patterns, waiting strategies, and property-based testing when applicable
- PRIORITIZE integration and E2E tests that exercise real workflows end-to-end
- Unit tests ONLY for pure functions with complex branching logic (state machines,
  classifiers, validators with multiple edge cases)
- Do NOT create unit tests for functions already covered by integration tests
- Do NOT create trivial tests (type checks, simple getter verification)
- Test the chain, not the piece: if a workflow goes A → B → C, test A → C,
  not A alone and B alone and C alone
- Read the source files under test before writing assertions
- Check for existing tests and avoid duplication
- Use existing fixtures and helpers where applicable
- Verify the tests compile by running the test list command for your framework
```

**Do not pre-filter the Test Brief.** Pass the domain expert findings directly to SDET. The SDET decides how to organize tests — you decide what needs coverage (via domain experts).
## Step 4: Verify and Hand Off

After SDET returns:

1. **Check that test files were created** — verify via `git diff --stat` or agent report
2. **Run a compilation check** — run the test list command for your framework on the new test files to confirm they parse
3. **Quick coverage spot-check** — verify at least the critical gaps from the Test Brief have corresponding tests. If a critical gap has no test, re-dispatch SDET with the specific gap.
4. **Invoke `sdlc-tests-run`** — hand off to the sdlc-tests-run skill targeting the newly created test files

```
Test suite created. Handing off to sdlc-tests-run to run and fix.
Target: tests/{path-to-new-tests}
```

If compilation check fails, re-dispatch SDET with the error output. Do not fix test code yourself.

## Step 5: Session Learning Capture

Coverage gap analysis reveals discipline-level blind spots — entire domains without test coverage, testing paradigm gaps, knowledge store deficiencies that left agents unaware of testable behavior, and architecture patterns that resist testing.

If this test creation session surfaced non-obvious learnings (coverage gaps that reveal missing domain knowledge, architecture patterns that make testing difficult, cross-domain friction between test infrastructure and application structure), suggest:

> This test creation session surfaced insights that may be worth capturing to discipline parking lots. Consider running `/sdlc-reflect` to surface them.

Skip the suggestion if the gaps were straightforward with no broader patterns.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll write a quick test myself" | SDET writes all test code. Manager Rule. |
| "I'll tell SDET exactly which test cases to write" | Provide the Test Brief (what needs coverage). SDET decides how to implement. |
| "Skip the domain expert analysis, SDET can figure it out" | SDET knows testing patterns but not domain logic. Domain experts catch gaps the SDET would miss — they know which handlers exist and which workflows matter. |
| "The coverage map shows tests exist, so skip Step 2" | Tests existing ≠ workflows covered. Integration tests can exist for a module but zero tests cover the actual handler chain. File-level coverage ≠ function-level coverage ≠ workflow coverage. |
| "I know what's missing, skip the domain expert" | The manager can identify "endpoint tests missing" and miss that the entire handler chain is untested. Domain experts see gaps the manager doesn't. |
| "Unit tests for every function" | Integration tests that exercise the workflow are worth 10x more than unit tests of individual functions. Only add unit tests for complex pure logic. |
| "More tests = better coverage" | Useless tests are worse than no tests — they create maintenance burden and false confidence. Every test must verify behavior someone cares about. |
| "Skip sdlc-tests-run, the tests already pass" | sdlc-tests-run catches what a single run misses. Always hand off. |
| "The scope is obvious, skip step 0" | Ask if not specified. Wrong scope = wrong tests. |
| "I'll fix the compilation error, it's one line" | Re-dispatch SDET. Size is not an exception. |
| "This is a small change, skip the domain expert phase" | The description has an anti-trigger for trivial single-file changes. But if the scope has any workflow logic, branching, or integration points, run the full two-phase flow. When in doubt, run it. |

## Integration

- **Depends on:** `[sdlc-root]/process/agent-selection.yaml` (agent identification), `[sdlc-root]/process/review-lenses.md` (lens definitions), `[sdlc-root]/knowledge/agent-context-map.yaml` (cross-domain knowledge injection), `[sdlc-root]/knowledge/testing/testing-paradigm.yaml` (SDET dispatch guidelines)
- **Feeds into:** `sdlc-tests-run` (receives the created tests and runs the red-green fix cycle), `sdlc-reflect` (suggests it when coverage gaps reveal discipline-level blind spots)
- **Uses:** Domain agents (Step 2 gap analysis), SDET agent (Step 3 implementation), `[sdlc-root]/process/manager-rule.md`, `[sdlc-root]/process/collaboration_model.md`
- **Complements:** `sdlc-execute` / `sdlc-lite-execute` (invoke after execution to generate tests for the deliverable)
- **Does NOT replace:** `sdlc-tests-run` (this creates tests; that runs and fixes them). Direct SDET dispatch (appropriate for trivial scope where two-phase is overkill).
