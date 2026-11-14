# External Review Gate

An **optional, configuration-gated** cross-vendor reviewer that sends SDLC
artifacts to a **non-Claude model** — OpenAI Codex, or a local LLM (llama.cpp /
Ollama / vLLM) — for an independent second opinion. It participates at three
points in the lifecycle:

| SDLC point | Artifact reviewed | Where defined |
|------------|-------------------|---------------|
| **Planning** | Approach comparison (deliberation consult); spec + plan (review ensemble member) | § Planning Integration below |
| **Execution** | The converged diff, after the internal review-fix loop meets its exit bar, before commit | § Where it sits in the loop |
| **Knowledge promotion** | Parking-lot promotion candidates | § Knowledge-Judgment Wrapper |

In every case its findings re-enter the normal triage; they never auto-apply.

This gate is disabled by default. It activates only when the project provides the
wrapper described under "Enabling the gate."

**First-class once configured.** Enabling is opt-in (the project must provide the
wrapper), but once the wrapper exists, participation is **not** discretionary
per-invocation: the external reviewer is a standing member of the planning
review roster and the execution gate, invoked by default at each integration
point below. Deliberation between models is strongest when the models come from
different families — cross-vendor disagreement is signal, not noise — so when
the capability is configured, the SDLC uses it as much as possible rather than
reserving it for special occasions. The per-point skip conditions (trivial
diffs, docs-only changes, precedent-following approach decisions) and a headless
run without durable egress authorization (§ Data egress) are the only sanctioned
reasons to skip a configured reviewer.

---

## Why a cross-vendor gate

`[sdlc-root]/process/debate-protocol.md` establishes that the primary value of
multi-agent review is **ensembling** — independent reviewers with different blind
spots — not debate itself. Every internal reviewer is still a Claude model, so
they share systematic blind spots: the same training distribution fails on the
same edge cases. A reviewer from a different vendor (Codex) or a different
architecture (a local Qwen) is the most independent reviewer available — it
catches the class of issue Claude reviewers miss *together*. This gate is one
more ensemble member, deliberately chosen to maximize independence.

It is **not** a replacement for internal review. At execution time the internal
loop still runs to completion first — the external model reviews an
already-converged change, so its signal is "what did an entire vendor's-worth of
independent judgment still catch?" At planning time it instead reviews
*alongside* the internal roster (§ Planning Integration) — plan review is a
single ensemble round, not a fix loop, so there is no converged state to wait
for and independence is maximized by reviewing in parallel.

## Where it sits in the loop

```
internal review-fix loop → EXIT BAR MET (no critical/major open)
   ↓
External Review Gate (if enabled)
   ├─ no findings → proceed to commit
   └─ findings → dedup + calibrate with internal findings → triage (Step C of review-fix-loop.md)
                   ├─ FIX → dispatch domain agent → re-run INTERNAL loop (counts toward the 3-round cap) → re-run gate
                   ├─ INVESTIGATE / DECIDE → surface to CD
                   └─ PRE-EXISTING → record, no action
```

The gate is a source of findings, not a fixer. External findings flow through the
exact same classification (`[sdlc-root]/process/finding-classification.md`) and
the exact same fix path as any agent finding: **the external model never edits
files; domain agents fix, and the internal loop re-verifies.** This keeps the
Manager Rule intact — an external model's output is input to triage, subordinate
to z-sdlc's own review.

A FIX from the external gate re-opens the internal loop: after the fix, dispatch
the internal reviewers again (fixes can introduce new problems), and only once
the internal loop meets its exit bar again does the gate re-run. External
findings are **deduplicated against and calibrated alongside** the internal
findings, on the one severity scale in
`[sdlc-root]/process/finding-classification.md`. **Every internal round a gate
finding re-opens counts toward the review loop's three-round cap**
(`[sdlc-root]/process/review-fix-loop.md` § Round Cap). The gate also keeps its
own cap of 2 fix rounds. Both limits apply — whichever is reached first stops
the loop, and the remainder goes to CD via `AskUserQuestion` rather than looping
(external models can generate an unbounded stream of low-value style opinions).

## Data egress — read before enabling

Sending a diff to an external model **publishes that code to that service.** For
a hosted model (Codex / OpenAI), the code leaves the machine and may be retained
or logged by the provider. This is an outward-facing action:

- **Never** send secrets, `.env` files, credentials, or key material. The wrapper
  payload is the diff plus spec/plan context — scrub or exclude secret-bearing
  files before they reach the wrapper.
- For proprietary or sensitive codebases, prefer a **local** model (llama.cpp /
  Ollama) so nothing leaves the machine. The OpenCode local-serving reference
  (`.claude/skills/sdlc-port-opencode/references/local-model-serving.md`)
  documents a suitable local setup.
- The gate must state, each time it runs, **where the code is going** (which
  model / endpoint) so CD sees the egress. If the project has not durably
  authorized egress to a hosted provider, confirm with CD before the first
  hosted-model run of a session.
- **In a headless run** (no person present) nobody can confirm. Without durable
  authorization, skip hosted-model runs and list the gate under the result's
  `skipped` (`[sdlc-root]/process/headless-mode.md`). A local model, or a hosted
  provider the project has durably authorized, runs as usual.

If the codebase's sensitivity is unknown, default to local-only or skip the gate.

## Enabling the gate

The gate is convention-driven — no manifest schema change. It activates when an
executable wrapper exists at:

```
[sdlc-root]/external-review.sh
```

If the file is absent or not executable, the gate is **skipped silently** (it is
optional). If present, the skill runs it as the gate.

### Wrapper contract

- **stdin** — the review payload: a rubric header, context, and the artifact
  under review. Plain text. **The rubric header owns the task framing and the
  output format** — the invoking skill writes it per integration point (diff
  review, plan review, approach consult), and the wrapper passes it through.
  For diff review the artifact is spec/plan context plus the unified diff; for
  planning payloads it is the spec and plan text (see § Planning Integration).
- **stdout** — findings in the format the rubric header requested. The default
  review format, used when the rubric does not specify otherwise: one finding
  per line or as a markdown list, each in the form
  `SEVERITY | location | finding` where SEVERITY ∈ {critical, major, minor} —
  defined in `[sdlc-root]/process/finding-classification.md` § Severity Levels — and
  location is `file:line` for diffs or `artifact § section` for planning
  artifacts. Empty stdout means "no findings."
- **exit code** — `0` on success (including zero findings). Non-zero means the
  gate could not run; the skill records "external gate errored — skipped" and
  proceeds to commit. **Never block a commit on external availability.**
- The wrapper owns endpoint, secret scrubbing, and prompt shaping, and provides
  the default model choice. z-sdlc ships a **standard template** at
  `[sdlc-root]/templates/external-review.sh.template` — enabling is copy +
  `chmod +x` + adjusting the defaults, because the right model and the egress
  policy remain project decisions. Codex-backed wrappers SHOULD honor the
  optional `CODEX_MODEL` / `CODEX_REASONING_EFFORT` environment variables (see
  § Task-Based Model Selection below) so the invoking skill can match model and
  reasoning effort to the task; the wrapper's own defaults apply when they are
  unset.

### Standard template

z-sdlc ships a Codex-backed standard template, adopted from a
production installation, at:

```
[sdlc-root]/templates/external-review.sh.template
```

To enable the gate, copy it to `[sdlc-root]/external-review.sh`, `chmod +x`
it, and adjust the defaults to the project's egress policy. The template
implements the contract's operational details so hand-written wrappers don't
have to rediscover them:

- **stdin passthrough** — the payload flows through stdin (the codex CLI
  appends it as a `<stdin>` block), avoiding ARG_MAX limits on large diffs.
- **`-o` output capture** — only the model's final message reaches stdout;
  codex progress/echo noise never contaminates the findings contract.
- **`--sandbox read-only --ephemeral`** — the external model can execute
  nothing and persists nothing.
- **Time limit** — `CODEX_TIMEOUT_SECS` (default 1800) bounds the codex call
  with a portable `perl` alarm (macOS has no `timeout`), so a stalled call
  skips the gate instead of hanging the session.
- **No payload, no wait** — the wrapper refuses to run without piped stdin.
  The codex CLI reads stdin whenever it isn't a terminal and waits for
  end-of-file, so a background call with an open, empty stdin hangs forever.
- **Egress disclosure on stderr** — each run announces where the payload is
  going and at what model/effort, satisfying the disclosure rule above.
- **Payload-neutral prompt** — the embedded prompt defers to the payload's
  rubric header for artifact, task, and output format, so the one wrapper
  serves diff review, plan review, and approach consults.

For sensitive codebases, replace the codex call with a local model so nothing
leaves the machine (nothing else changes):

```bash
#!/usr/bin/env bash
# [sdlc-root]/external-review.sh — local Qwen reviewer
set -euo pipefail
payload="$(cat)"
printf '%s\n\nFollow the rubric at the top of the payload — it defines the task and output format.\nDefault if unspecified: SEVERITY | location | finding. Empty if none.\n' \
  "$payload" | ollama run qwen3.6-27b
```

The invoking skill builds the payload like:

```bash
{
  echo "Independent review. Report only real defects: correctness, security,"
  echo "data integrity, contract breaks. Skip style. Severity + file:line + why."
  echo
  echo "=== SPEC/PLAN CONTEXT ==="; cat "$plan_or_spec" 2>/dev/null || echo "(none)"
  echo; echo "=== DIFF ==="; git diff --staged 2>/dev/null || git diff
} | "[sdlc-root]/external-review.sh"
```

## Task-Based Model Selection

When the wrapper is Codex-backed, the invoking skill may choose the model and
reasoning effort per task instead of accepting the wrapper's defaults. The
Codex CLI accepts both on the command line:

```bash
codex exec -m <model> --config model_reasoning_effort="<minimal|low|medium|high|xhigh>" "<prompt>" < /dev/null
```

**Direct calls close stdin.** Any `codex exec` without a piped payload, such as an ad-hoc consult or a
call from a background shell, ends with `< /dev/null`. Otherwise codex prints "Reading additional input
from stdin..." and waits indefinitely for end-of-file that never comes.

The convention: wrappers pass these through from environment variables, and
the invoking skill sets them at the call site —

```bash
CODEX_MODEL="gpt-5.6-luna" CODEX_REASONING_EFFORT="xhigh" \
  { ...payload... } | "[sdlc-root]/external-review.sh"
```

- **Resolve model names at runtime, not from memory.** OpenAI's model catalog
  changes; a model name recalled from training data may be retired or
  superseded. Before choosing a model, fetch the current catalog from
  <https://developers.openai.com/api/docs/models> (WebFetch) and pick from
  what is actually listed. If the catalog cannot be fetched, leave
  `CODEX_MODEL` unset and let the wrapper's default stand — never guess a
  model name.
- **Match effort to the task — screen cheap, escalate splits.** High-volume
  screening passes (initial promotion-gate verdicts over a batch) run on a
  balanced/mid-tier model at `high`; reserve the frontier tier at `xhigh` for
  tie-break judgments on split verdicts, the final once-over of promote-bound
  entries, and high-risk single diffs (auth, payments, migrations,
  concurrency). Routine second opinions on ordinary diffs run fine at
  `medium`; don't pay frontier-model latency for a docs-only change.
- **Both variables are optional, independently.** Setting only
  `CODEX_REASONING_EFFORT` while leaving the wrapper's default model is a
  normal configuration.
- Model selection does not change the egress picture — the payload goes to the
  same provider either way — but the "state where the code is going"
  disclosure should name the actual model used.

## Planning Integration

Planning is where cross-family deliberation pays the most: the artifacts are
cheap to review (text, not code), the decisions are structural (wrong ones cost
10x to unwind during execution), and a model from another family disagrees for
*different reasons* than another Claude would. When `external-review.sh` is
configured, the external reviewer participates in planning at two points. Both
use the **same wrapper** as diff review — only the payload differs.

Egress note: spec, plan, and approach text are project knowledge. The same
egress rules apply — state where the content is going before running a hosted
model, and never include secrets in the payload.

### 1. Approach deliberation consult (sdlc-plan step 3d)

When the APPROACH-DECISION block compares 2–3 candidate approaches (i.e., no
clean precedent exists), send the comparison to the external model **before
selecting**, and weigh its recommendation as one more independent opinion.
Skip when a precedent is being followed — there is nothing to deliberate.

Payload:

```bash
{
  echo "Independent architecture consult."
  echo "Below are candidate approaches for a planned change. Critique each"
  echo "(risks, hidden costs, failure modes the authors may have missed),"
  echo "then end with exactly one line:"
  echo "RECOMMEND | <approach letter> | one-sentence reason"
  echo
  echo "=== TASK ==="; echo "$task_summary"
  echo; echo "=== CONSTRAINTS ==="; echo "$constraints"
  echo; echo "=== APPROACHES ==="; echo "$approaches_with_tradeoffs"
} | "[sdlc-root]/external-review.sh"
```

Record the outcome in the APPROACH-DECISION block (`External consult:` line —
see `sdlc-plan`). The consult is advisory: the orchestrator and CD still select.
If the external model recommends against the internally preferred approach, that
disagreement is exactly the signal the consult exists to surface — present both
positions to CD via `AskUserQuestion` rather than silently overriding either
side. If the wrapper errors, record "external consult errored — skipped" and
proceed; never block planning on external availability.

Model tier: this is wide-solution-space judgment work — run the frontier tier
at `xhigh` (§ Task-Based Model Selection).

### 2. Plan review ensemble member (sdlc-plan step 5, sdlc-lite-plan step 3)

When the planning skills dispatch domain agents to review the plan, the external
reviewer joins the roster as one more ensemble member — dispatched in the same
review round, not as an afterthought pass. This is the planning analogue of
Design Principle 1 in `[sdlc-root]/process/debate-protocol.md`: independent
review is the value driver, and the most independent reviewer available is one
from another vendor.

Payload (the spec section is omitted for lite plans, which have none):

```bash
{
  echo "Independent plan review. You are reviewing a PLAN, not code."
  echo "Report real problems: infeasible phasing,"
  echo "missing dependencies or sequencing errors, scope gaps vs. the spec,"
  echo "unstated risks, untestable acceptance criteria, missing failure"
  echo "handling. Skip style and formatting."
  echo "Format: SEVERITY | artifact § section | finding   (SEVERITY: critical|major|minor)"
  echo "Severity = impact x likelihood if the plan is executed as written: critical = certain or very likely data loss, breach, or complete failure; major = significant impact, likely to manifest; minor = partial, workaround exists, or cosmetic."
  echo
  echo "=== SPEC ==="; cat "$spec_file" 2>/dev/null || echo "(no spec — lite plan)"
  echo; echo "=== PLAN ==="; cat "$plan_file"
} | "[sdlc-root]/external-review.sh"
```

Because the payload includes the spec, spec-level gaps (requirements the plan
silently dropped, success criteria nothing verifies) surface here too — no
separate spec gate is needed.

Handling findings:

- External findings enter the **same classification table** as domain agent
  findings (`[sdlc-root]/process/finding-classification.md`; planning context
  uses FIX / DECIDE / PRE-EXISTING). Attribute them as `[external:<model>]`.
- The external model never revises the plan — the writing agent incorporates
  FIX findings, exactly as with internal findings.
- External findings are deduplicated and calibrated alongside the domain agents'
  findings before classification (`[sdlc-root]/process/finding-classification.md`).
- When re-review is triggered, the external reviewer re-reviews with the rest
  of the roster. Cap its participation at **2 rounds**, inside the plan review
  loop's three-round cap (`[sdlc-root]/process/review-fix-loop.md` § Plan
  Review) — after that, classify
  any remaining new external findings as DECIDE and surface to CD rather than
  looping (same unbounded-style-opinion risk as the execution gate).
- Apply § Anti-conformity below unchanged: the external reviewer lacks
  chronicle/ADR context, so uncorroborated architectural objections that
  contradict a recorded decision lean DECIDE, not FIX.
- If the wrapper errors, record "external plan review errored — skipped" and
  continue with the internal roster. Never block planning on external
  availability.

Model tier: plan review runs a balanced/mid-tier model at `high` by default;
escalate to the frontier tier at `xhigh` for high-risk deliverables (auth,
payments, migrations, concurrency, public APIs — MTS4 risk escalation).

## Knowledge-Judgment Wrapper

The diff-review wrapper above is shaped for code review — its output contract
(`SEVERITY | file:line | finding`) does not fit judging whether a discipline
parking-lot entry deserves promotion to a knowledge store. That task gets its
**own, parallel wrapper convention** rather than a mode flag on the same
script — different artifact, different contract:

```
[sdlc-root]/external-review-knowledge.sh
```

It serves as the external judge in the Promotion Verification Gate
(`[sdlc-root]/process/discipline_capture.md` § Promotion Verification Gate).
Same activation rule as the diff wrapper: if the file is absent or not
executable, the gate substitutes a second internal high-tier subagent judge —
never block a promotion pass on external availability.

### Knowledge-judgment wrapper contract

- **stdin** — a neutral evidence payload: numbered candidate entries, each with
  its full parking-lot text and corroboration signals (recurrence count,
  independent-reviewer citations, same-claim vs. adjacent-claim knowledge-store
  overlap, external validity). **No verdicts** — the judge reasons from raw
  evidence.
- **stdout** — one line per entry: `N | PROMOTE|DEMOTE | one-sentence justification`.
  Empty stdout means the wrapper failed to produce verdicts; treat as an error.
- **exit code** — `0` on success. Non-zero means the judge could not run; the
  gate records "external judge errored — substituted internal subagent" and
  falls back.
- The wrapper owns endpoint and prompt shaping, exactly like the diff-review
  wrapper, and honors the same `CODEX_MODEL` / `CODEX_REASONING_EFFORT`
  passthrough (§ Task-Based Model Selection). The gate runs it at two tiers:
  a balanced/mid-tier model at `high` for the initial screening pass over the
  batch, and a frontier model at `xhigh` for tie-break judgments on split
  verdicts and the final once-over of the promote-bound slate (see
  `[sdlc-root]/process/discipline_capture.md` § Promotion Verification Gate,
  steps 4–5). The **data egress rules above apply unchanged**
  — parking-lot text is project knowledge; state where it is going before
  running a hosted model.

z-sdlc ships a standard template for this wrapper too, at
`[sdlc-root]/templates/external-review-knowledge.sh.template` — enable it the
same way (copy to `[sdlc-root]/external-review-knowledge.sh`, `chmod +x`,
adjust defaults). It carries the same operational details as the diff-review
template (stdin passthrough, `-o` output capture, read-only ephemeral sandbox,
stderr egress disclosure), plus one contract difference: **empty stdout is a
judge failure** here (unlike the review wrapper, where empty means "no
findings"), so the template exits non-zero on empty output and the gate falls
back to an internal subagent judge.

## Anti-conformity for external findings

The external model is an outsider — it lacks the internal reviewers' context,
which is exactly its value, but also means it will produce more false positives
(it does not know the codebase conventions or the plan's deliberate trade-offs).
Apply the debate-protocol safeguards:

- **Do not defer to it.** An external finding is not more authoritative because it
  came from another vendor. Classify on evidence, like any finding.
- **Scrutinize before FIX.** External findings uncorroborated by tests or the
  internal reviewers lean toward INVESTIGATE, not FIX — verify before spending a
  fix cycle. (Same discipline as the security-finding calibration in
  `[sdlc-root]/process/review-fix-loop.md` Step C.)
- **Watch for conformity.** If an internal reviewer flips to agree with the
  external model on re-review without new evidence, treat the flip as suspect
  (debate-protocol § Anti-Conformity Safeguard).

## When to run it

When the wrapper is configured, running it is the default (§ First-class once
configured). The skip conditions per integration point:

- **Planning — plan review:** runs whenever plan review runs. No skip
  condition — plans are cheap to review and structural mistakes are the most
  expensive kind.
- **Planning — approach consult:** skip when a precedent is being followed
  (nothing to deliberate); run whenever approaches are actually compared.
- **Execution — diff review:** skip for trivial changes, docs-only diffs, or
  sensitive code with no local model available. Highest value in high-risk
  domains (auth, payments, migrations, concurrency, public APIs) — pairs
  naturally with MTS4 risk escalation.

The gate is invoked from `[sdlc-root]/process/review-fix-loop.md` (Step E) and
surfaced in `sdlc-review-code`, `sdlc-execute`, and `sdlc-lite-execute`
(execution diff review — always after the internal loop), and in `sdlc-plan`
(steps 3d and 5) and `sdlc-lite-plan` (step 3) per § Planning Integration.
