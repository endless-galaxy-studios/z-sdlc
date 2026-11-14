---
name: sdlc-debug-incident
description: >
  Required workflow for any production incident (OOM, service down, elevated error rate,
  data issue, security event) — creates a live investigation doc during active response and
  transforms it into the canonical postmortem after remediation is scoped. Two phases
  auto-detected by doc state: TRIAGE captures hypotheses, timestamped findings, and
  dispatched domain agents in real time; CLOSEOUT restructures the messy doc into the
  project's postmortem template (timeline, root cause, action items) once remediation
  deliverables exist.
  Use when a production incident occurs — service down, OOM, elevated error rate, data issue, or security event.
  Triggers on "incident", "production incident", "OOM", "service is down", "we had an outage",
  "production issue", "investigate the outage", "postmortem", "incident report",
  "document the incident", "/sdlc-debug-incident".
  Do NOT use for pure debugging without user-visible service impact — dispatch the
  debug-specialist agent directly.
  Do NOT use for writing the remediation plan itself — use sdlc-plan or sdlc-lite-plan once
  TRIAGE identifies candidate deliverables.
  Do NOT use for proactive systemic audits without a triggering incident — use sdlc-audit.
  Do NOT use for generating playbooks from a resolved incident — use sdlc-playbook-generate.
---

# SDLC Debug Incident

Orchestrates the full incident lifecycle: live investigation during active response, then structured postmortem closeout after remediation is scoped. The investigation doc is the single source of truth the whole way through — it starts messy and gets cleaned up, rather than being rewritten from scratch. One skill, two phases, auto-detected.

**Argument:** `$ARGUMENTS` (optional — `triage`, `closeout`, or empty for auto-detect; see Mode Resolution below)

## Modes

| Mode | Purpose | Output |
|------|---------|--------|
| **TRIAGE** | Active investigation — capture hypotheses, findings, dispatched agents, emerging remediation | Live doc at `docs/current_work/incidents/incident_YYYY-MM-DD_slug.md` |
| **CLOSEOUT** | Transform the triage doc into the canonical postmortem; link action items to deliverables | Same file, restructured to match `[sdlc-root]/templates/postmortem_template.md`; candidate for eventual archival |

## Mode Resolution

Parse `$ARGUMENTS` and the working tree to pick a mode:

| Invocation | Condition | Mode |
|------------|-----------|------|
| `/sdlc-debug-incident triage` | Explicit | TRIAGE |
| `/sdlc-debug-incident closeout` | Explicit | CLOSEOUT |
| `/sdlc-debug-incident` (no args) | No incident doc exists for today, or most recent incident doc has `status: triage-active` | TRIAGE |
| `/sdlc-debug-incident` (no args) | Most recent incident doc has `status: remediation-scoped` and all linked deliverables are `Complete` | CLOSEOUT |
| `/sdlc-debug-incident` (no args) | Most recent incident doc has `status: remediation-scoped` but linked deliverables are still in-flight | Ask the user: "Remediation deliverables are still in flight. Run CLOSEOUT now (partial) or wait until all deliverables complete?" |

When the user asks for a specific incident ("close out last week's OOM"), accept either a date (`2026-04-20`) or a slug (`api_oom`) as a second argument and resolve the matching file under `docs/current_work/incidents/`.

---

## Manager Rule and Collaboration

**You are the manager — you orchestrate, domain agents investigate.** The canonical rule is in `[sdlc-root]/process/manager-rule.md`. Never self-investigate past a single layer of code reading — if the root cause isn't obvious after one read of the suspected file, dispatch a domain agent. The incident doc is *your* artifact; the investigation work is the agents'.

- **Default: dispatch domain agents** for all investigation, debugging, and code analysis. You read one file to orient, then dispatch.
- **Failed dispatch:** if an agent returns without useful findings, re-dispatch with refined context — do not investigate yourself.
- **No semantic revert:** fixing a bug by removing the feature is not a fix — preserve the user's requested behavior.
- **Session scope:** this rule stays active for the entire session. There is no post-incident wind-down mode.

**AskUserQuestion mandate:** every question directed at the user MUST use the `AskUserQuestion` tool — do not type questions as conversational text. This applies to: the Mode Resolution ambiguity prompt, the T6 escalation after three unconverging dispatch rounds, and the C1 partial-closeout choice. The full collaboration model is in `[sdlc-root]/process/collaboration_model.md`.

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

**Anti-patterns to avoid:** (1) code assertion without verification — never answer "how does X work" from memory; grep/read the code first; (2) trajectory poisoning — if the agent is off track after 2-3 corrections, clear context and start fresh.

Status transitions on the incident doc (`triage-active` → `remediation-scoped` → `complete` / `partial`) and on linked deliverables follow the state machine in `[sdlc-root]/process/deliverable_lifecycle.md`. Do not invent custom states.

## Agent Dispatch Protocol

Every agent dispatched during TRIAGE must receive:

1. **The symptom** — what the user sees or what the monitoring reported. Exact error messages, latency numbers, service IDs, timestamps.
2. **The classification so far** — what's been ruled in and what's been ruled out.
3. **The domain lens** — what this specific agent should look at (not the whole system).
4. **Output format** — a structured finding using the evidence report format below. The report format is what makes arbitration tractable when multiple agents return simultaneously.
5. **Return shape** — the evidence report below and nothing around it: verdict, cited evidence and causal chain, no narrative. Several reports arrive at once during an incident, and they have to be compared quickly.

Dispatch prompts describe *what to investigate and why*. Agents decide *how*. Do not tell an agent what the root cause is — let them find it independently and converge. Parallel independent investigations are more valuable than one agent being given the answer.

**Cross-domain knowledge injection:** When an agent investigates outside its primary domain (e.g., `debug-specialist` tracing into payment logic, `performance-engineer` examining data-layer queries), consult `[sdlc-root]/knowledge/agent-context-map.yaml` for the other domain's agent and include those knowledge files in the dispatch prompt.

### Hypothesis Investigation Dispatch Template

When dispatching an agent to investigate a specific hypothesis, structure the prompt to include **what counts as confirming evidence and what counts as falsifying evidence** before the agent begins. Spelling out falsification criteria before dispatch prevents agents from treating absence-of-disconfirmation as confirmation.

Include these fields in every hypothesis-targeted dispatch prompt:

```
Hypothesis: {clear, falsifiable statement}
Failure mode category: {Logic Error | Data Issue | State Problem | Integration Failure | Resource Issue | Environment}
Files / services to examine: {specific paths or services, not "the whole codebase"}

Confirming evidence — if you find any of these, the hypothesis is supported:
1. {observable condition with a specific code path or metric}
2. {observable condition}

Falsifying evidence — if you find any of these, the hypothesis is wrong:
1. {observable condition that would rule it out}
2. {observable condition}

Return your findings in this format, each field holding only what the evidence supports:
- Verdict: Confirmed | Falsified | Inconclusive
- Confidence: High (>80%) | Medium (50-80%) | Low (<50%)
- Confirming evidence: list each with file:line citation
- Contradicting evidence: list each with file:line citation (include even if verdict is Confirmed — contradicting evidence on a confirmed hypothesis means the causal chain is incomplete)
- Causal chain: numbered steps from root cause to observed symptom
- Additional observations: anything discovered that may be relevant to other hypotheses — do not discard it
- Recommended fix: only if Confirmed; otherwise leave blank
```

**Why file:line citations are mandatory:** Evidence without a code location is testimonial evidence — weak and unverifiable. "The connection pool can exhaust" is a hypothesis, not evidence. "`src/db/session.py:47` creates a new engine per request rather than using the module-level singleton" is evidence.

### Evidence Strength Reference

Not all evidence carries equal weight. When logging findings and comparing across parallel investigations, classify each piece:

| Evidence type | Strength | Example |
|---------------|----------|---------|
| **Direct** | Strong | Code at `file.py:line` shows the bug; query plan output shows sequential scan where index should be used |
| **Correlational** | Medium | Error rate spiked after commit `abc123`; latency climbed when worker count increased |
| **Testimonial** | Weak | "It works on my machine"; "this endpoint has always been slow" |
| **Absence** | Variable | No tenant filter found in the query — strong when the absence is the entire causal chain; weak when the code path is complex |

A high-confidence verdict requires multiple pieces of direct evidence and a clear causal chain. Medium-confidence (correlational + some direct) warrants continued investigation, not declaration of root cause.

---

## Agent Selection

Pick 3–5 agents per incident based on the symptom. Over-dispatch (10 agents for a small bug) wastes cycles; under-dispatch (1 agent for a multi-domain issue) misses cross-cutting causes.

**Use `[sdlc-root]/process/agent-selection.yaml` as the source of truth for which agent covers which domain.** That file lists the project's actual agents, their dispatch triggers, and their domain coverage — incident triage uses the same role-to-domain mapping as planning and review.

**Default starting point:** `debug-specialist` is the universal entry point when the root cause is unclear — it does structured root cause analysis and narrows the domain. Once the domain is clearer, dispatch the specialist.

**Selection process:**

1. Identify the symptom domain(s) from `agent-selection.yaml`'s `dispatch_when` triggers (e.g., latency → performance-engineer; auth → security-engineer; DB → data-architect; deploy/container → devops-engineer; frontend render → frontend-developer; build/CI → build-engineer; data pipeline → data-engineer; ML/inference → ml-engineer; cross-service → systems-engineer).
2. Always include `debug-specialist` for ambiguous cases.
3. Always include `code-reviewer` if you suspect a recent change introduced the issue.
4. Add `security-auditor` (not `security-engineer`) if the incident is a suspected breach, IDOR, or data exposure — the auditor assesses, the engineer fixes.
5. For ML/retrieval quality regressions, pair `ml-engineer` with whichever evaluation specialist your project has (often `sdet`).

---

## TRIAGE Mode

### Workflow

```
CAPTURE SYMPTOM → CLASSIFY SEVERITY → CREATE/OPEN DOC → FIRST RESPONSE → GENERATE HYPOTHESES → SELECT AGENTS → DISPATCH IN PARALLEL → LOG FINDINGS → ARBITRATE RESULTS → IDENTIFY CAUSE → RECOMMEND DELIVERABLES → HANDOFF
```

### Steps

### T1. Capture the Symptom

Ask the user (or accept from the invocation context):

- What is observed? (error message, behavior, metric)
- What is the scope? (one user, one tenant, all users, one service)
- When did it start? (if known)
- What changed recently? (last deploy, config change, env var update)

Follow `[sdlc-root]/process/incident_response.md` for severity classification (SEV-1 to SEV-4). Err higher when uncertain — downgrading is cheaper than under-responding.

### T2. Create or Open the Incident Doc

Path: `docs/current_work/incidents/incident_YYYY-MM-DD_{slug}.md`. If the directory does not exist, create it. The `{slug}` is a 2–4 word identifier of the incident (e.g., `api_oom`, `auth_session_leak`, `search_quality_drop`).

If a doc for today already exists for the same slug, open it and continue — do not create duplicates. If the symptom is distinct from an existing doc for today (different service, different symptom), use a disambiguating slug.

Scaffold the doc with the TRIAGE template:

```markdown
---
type: incident
severity: SEV-{N}  # or SEV-?  if still assessing
date: YYYY-MM-DD
service: {service-name}  # e.g., "api", "worker", "frontend"
status: triage-active
started_at: YYYY-MM-DDTHH:MM:SSZ  # best-available estimate of incident start
detected_at: YYYY-MM-DDTHH:MM:SSZ  # when someone noticed
author: CC
related_deliverables: []  # filled in as deliverables get created
---

# Incident — {Title}

## Symptom
- Observed: {what}
- Scope: {who is affected}
- First seen: {time, if known}
- Recent changes: {deploys, env vars, merges in the last N hours}

## Hypotheses (live — add, don't delete)
- [ ] H1: {description}  — proposed {timestamp}
- [ ] H2: {description}  — proposed {timestamp}

## Ruled Out (preserve, don't delete)
- {hypothesis}  — ruled out by {evidence}, {timestamp}

## Findings Log (timestamped, append-only)
- {timestamp} — {finding from agent/investigation}

## Dispatched Agents
| Agent | Dispatched | Returned | Key finding |
|-------|------------|----------|-------------|

## Candidate Remediation
- {item}  — likely deliverable: D{NN} or backlog

## Open Questions
- {question}
```

**Post-write: offer an explainer or a walkthrough.** Ask CD whether they want an HTML explainer (`sdlc-explain`, **incident** storyboard) or a guided walkthrough (`sdlc-walkthru`) of the incident doc — never unprompted. Mechanics and the precedes-approval rule: `[sdlc-root]/process/html-rendering.md` § Post-Skill Offer.

### T2a. First Response Checklist

Before selecting agents or generating hypotheses, run the first-response checklist for the incident class. These steps take 3-5 minutes and accomplish two things: they preserve evidence before any mitigation disturbs the system state, and they often narrow the hypothesis space enough that one or two agents can handle what would otherwise need five.

**Why run this before T3/T3a?** Hypothesis generation without first-response evidence is speculation. These diagnostic reads are non-destructive — they produce data, they don't change state. Running them first means agents receive a richer dispatch prompt with observed data rather than inferring from symptom description alone.

**Evidence before mitigation.** Before restarting any service or rolling back any deployment, snapshot: current logs, active connection counts, container memory / process stats, pending job queue depth. Take 90 seconds to capture them — once you restart, the evidence is gone and RCA depends entirely on what was already logged.

#### Runbook lookup

Match the symptom to the right playbook in `[sdlc-root]/playbooks/`. Each incident-class playbook (files matching `incident-*.md`) contains the non-destructive first-response steps, agent dispatch list, escalation triggers, and rollback path for that incident class. See `[sdlc-root]/templates/incident-runbook-template.md` for the format when creating new runbooks.

If no playbook matches: skip T2a and proceed directly to T3 (Select Agents). After the incident closes, open an idea brief proposing a new playbook for the unmatched failure class — recurring patterns deserve their own runbook.

---

### T2b. Severity Classification Quick-Reference

The skill references `[sdlc-root]/process/incident_response.md` for the full SEV-1 to SEV-4 definitions. These quick-reference triggers let you classify in the first 5 minutes without looking up the process doc:

| Severity | Trigger | Response posture |
|----------|---------|-----------------|
| **SEV-1** | Service fully down for all users; data loss or corruption actively occurring; authentication broken; container restart-looping with no recovery window | Immediate response regardless of time of day. Incident commander designated within 5 minutes. Status page updated within 15 minutes. |
| **SEV-2** | Core feature path broken for all users; significant latency degradation (p95 > 3x baseline); critical background workers completely down | Within-hour response. Hourly updates to stakeholders. Status page updated if externally visible. |
| **SEV-3** | Single endpoint degraded; isolated tenant affected; non-critical feature broken; performance regression not yet user-impacting | Business-hours response. Document in incident doc, no status page update required. |
| **SEV-4** | Cosmetic, logging noise, non-blocking developer friction, single test flake | Next business-day response. Optional incident doc if learnings exist. |

**When uncertain, classify higher.** The cost of over-classifying a SEV-2 as SEV-1 is 30 minutes of heightened attention. The cost of under-classifying a SEV-1 as SEV-2 is a slow response while users experience an outage.

**Incident command structure for SEV-1 and SEV-2:** At these severities, separate three roles: Incident Commander (owns decisions and external communication), Technical Lead (drives diagnosis and fixes), Communications Lead (owns status page and stakeholder cadence). A single person filling all three roles will drop comms at the worst moment.

### T2c. On-Call Handoff Bullets

When the incident crosses a context boundary (shift change, handoff to a domain specialist, or escalation), include these bullets in the handoff message so the incoming responder has full orientation without reading the full doc:

```
Incident: {slug} ({date})
Severity: SEV-{N}
Service: {service-name}
Started: {timestamp} | Detected: {timestamp}
Status: {triage-active | remediation-scoped}

Current best hypothesis: {H? — description} [{confirmed | plausible | inconclusive}]
Ruled out: {H? — one line each}

Evidence snapshot taken: {yes/no — what was captured}
Last action: {what was done and when}
Next action: {what is in flight or waiting}

Rollback path available: {yes/no — description}
Outstanding questions: {one per line}

Incident doc: docs/current_work/incidents/incident_{date}_{slug}.md
```

This is not a summary of the doc — it's the minimum orientation payload for a responder who hasn't read the doc yet. Every field matters. Empty fields are answered by "unknown — check the doc," not omitted.

### T3. Select Agents

Use `[sdlc-root]/process/agent-selection.yaml` to map symptom → specialist. Start with `debug-specialist` + 2–4 domain specialists from the matching `dispatch_when` triggers. State the selection explicitly in the doc under "Dispatched Agents" before dispatching.

### T3a. Generate Hypotheses Before Dispatching

Before dispatching agents, draft the initial hypothesis list in the doc. Dispatching without hypotheses sends agents on open-ended explorations; dispatching with hypotheses sends agents to test specific falsifiable claims.

Use these six failure-mode categories as a brainstorm scaffold. Not every category will produce a hypothesis for every incident — that is fine. Work through each one and ask: given the symptom, is a plausible cause in this category possible?

| Category | What to ask for this incident |
|----------|-------------------------------|
| **Logic Error** | Is there a conditional, loop, or algorithm that could produce this symptom with the observed inputs? |
| **Data Issue** | Could the data shape, type, encoding, or null/absent field cause this? Is a tenant-isolation filter missing? |
| **State Problem** | Could a race condition, stale cache, or shared-state mutation produce this? Is a sync primitive wrong? |
| **Integration Failure** | Could an API contract mismatch, env var absence, or version incompatibility between services cause this? |
| **Resource Issue** | Could connection pool exhaustion, fd leak, memory growth, or cache eviction cause this? |
| **Environment** | Could a deploy, config change, dependency version, or platform difference cause this? |

Write each hypothesis as a **falsifiable statement**, not a description: "the worker engine is being created at module-load time rather than in the startup hook, causing it to be invalid after the event loop restarts" is falsifiable; "something is wrong with the worker" is not.

Aim for 3-5 hypotheses before dispatching. Each agent in T4 will be assigned one or two hypotheses to test. Hypotheses across agents should be *independent* — if H1 and H2 both point at the same code path, merge them into one.

### T4. Dispatch in Parallel

Dispatch all selected agents in a single message with multiple tool calls so they run concurrently. Each prompt must follow the Agent Dispatch Protocol. Wait for all to return before synthesis.

### T5. Log Findings

As each agent returns, append a timestamped entry to the Findings Log. Update the Hypotheses section: move anything confirmed to a "leading hypothesis" position, move anything falsified to Ruled Out with the evidence that falsified it.

**Do not delete hypotheses**, even wrong ones. The ruled-out list is future-you's context for the next similar incident.

### T5a. Arbitrate Parallel Results

When two or more agents have returned findings on the same incident, don't just log them sequentially and pick the most recent — arbitrate systematically.

**Step 1: Categorize each verdict**

For each hypothesis under investigation, classify the combined evidence from all relevant agents:

| Category | Meaning |
|----------|---------|
| **Confirmed** | High confidence (>80%), multiple direct evidence pieces, clear causal chain, no material contradicting evidence |
| **Plausible** | Medium confidence (50-80%), some direct evidence, reasonable causal chain, minor ambiguities or one contradicting piece |
| **Falsified** | Direct evidence contradicts the hypothesis; move to Ruled Out with the evidence that falsified it |
| **Inconclusive** | Insufficient direct evidence; neither confirmed nor falsified — warrants targeted follow-up, not declaration |

**Step 2: Rank confirmed and plausible hypotheses**

If multiple hypotheses reach Confirmed or Plausible status, rank them by:

1. Confidence level (high beats medium)
2. Number of direct-evidence pieces with file:line citations
3. Completeness of causal chain (can you trace the path step-by-step from cause to observed symptom?)
4. Absence of contradicting evidence

**Step 3: Determine root cause classification**

| Situation | What to do |
|-----------|-----------|
| One hypothesis is Confirmed, high confidence | Declare as proximate cause. Check Contributing Factors separately. |
| One hypothesis is Plausible, none Confirmed | Flag as leading candidate, not confirmed. Dispatch targeted follow-up (see T6). |
| Two or more hypotheses Confirmed | Check whether they are causally related (one enabling the other) or independent. Related: compound cause. Independent: usually a sign that one confirmation is actually medium-confidence. |
| No hypotheses Confirmed or Plausible | All inconclusive or falsified. Generate new hypotheses (loop back to T3a) or escalate per T6. |

**Step 4: Log the arbitration decision** in the Findings Log:

```
{timestamp} — Arbitration: H{N} Confirmed (high confidence, direct evidence at {file:line}); H{M} Falsified (contradicted by {evidence}); H{P} Inconclusive (insufficient evidence — follow-up needed on {specific question})
```

**Cross-hypothesis spillover:** When an agent's "Additional observations" field contains something relevant to another hypothesis, add it to the Findings Log immediately. Don't defer — these observations are often the thread that unravels the actual cause.

### T6. Converge or Re-Dispatch

Ask: has at least one hypothesis been confirmed to the point we can scope remediation?

- **Yes** — proceed to T7.
- **No, but we have a narrower domain** — dispatch additional specialists focused on the narrowed area. Loop T4-T6.
- **No, and we've looped 3+ times without convergence** — STOP. Escalate to the user: "Triage has run three rounds without a converging hypothesis. I recommend pausing to add telemetry or log a larger observation window, then resuming." Do not accumulate agents indefinitely.

### T7. Identify Root Cause + Contributing Factors

Write the `Root Cause` section inline in the doc. Distinguish:

- **Proximate cause** — the single thing that broke. Example: "Memory allocator grew to 15 GB under concurrent fan-out."
- **Contributing factors** — conditions that made the proximate cause possible, harder to detect, or harder to fix. Example: "no concurrency cap on the worker, no RSS watchdog, upstream dependency slowness extended request duration."

Root cause is rarely a single event. Be thorough on contributing factors — they drive the action items.

### T8. Recommend Deliverables

Translate the root cause + contributing factors into remediation candidates. For each, state:

- What the deliverable would address
- Estimated tier (lite, full, housekeeping)
- Which existing in-flight deliverables already cover it (if any)

Update the doc frontmatter:

```yaml
status: remediation-scoped
related_deliverables: [D{NN}, D{NN+1}]  # use placeholders if not yet created
```

### T9. Handoff

STOP. The incident doc now has enough to drive remediation, but **this skill does not write plans**.

Output to the user:

1. Summary of root cause and contributing factors
2. Recommended deliverables with tier
3. Explicit handoff: "Run `sdlc-lite-plan` for D{NN} and `sdlc-plan` for D{NN+1} when you're ready. Re-run `/sdlc-debug-incident closeout` once remediation is merged."

Do not invoke `sdlc-plan` or `sdlc-lite-plan` from inside this skill. Keep the boundary sharp — planning is a separate skill with its own dispatch and review loop.

---

## CLOSEOUT Mode

### Workflow

```
DETECT DELIVERABLES → EXTRACT TIMELINE → RESTRUCTURE TO POSTMORTEM → FILL WHAT-WENT-WELL/POORLY → MAP ACTION ITEMS → PRESERVE HYPOTHESIS LOG → REVIEW → (OPTIONAL) ARCHIVE
```

### Steps

### C1. Detect Remediation Deliverables

Read the incident doc's `related_deliverables` frontmatter. Verify each in `docs/_index.md`:

- All `Complete` — proceed.
- Some `In Progress` or `Planning` — ask the user whether to proceed with a partial closeout (valid — "what we know so far") or wait for all to complete. Partial closeout is allowed; label the postmortem's `status` as `partial` in that case.

### C2. Extract Timeline

Walk the Findings Log. Each timestamped entry is a timeline row. Map to the postmortem template's Timeline section:

| Time | Event |
|------|-------|
| HH:MM UTC | {Finding log entry → event} |

Enrich with:

- The `started_at` and `detected_at` from frontmatter as the first two rows
- Deployment / config-change events (cross-reference `git log` against the window)
- Resolution timestamp (when the remediation was deployed or the mitigation was applied)

**Timeline content discipline — what belongs in the timeline vs. the appendix:**

The timeline is the **public-facing chronological narrative** — it answers "what happened and when?" for anyone reading the postmortem cold. The appendix is the **investigator's scratch pad** preserved for future engineers. Keep them distinct:

| Belongs in timeline | Belongs in appendix |
|---------------------|---------------------|
| Deployment events, rollbacks, config changes | Full agent dispatch prompts and responses |
| First detection of symptom (alert, user report) | Ruled-out hypotheses with falsification evidence |
| Incident declaration and severity transitions | Raw diagnostic output (query plans, connection snapshots) |
| Key diagnostic findings (e.g., "identified missing tenant filter") | Metrics graph links and data exports |
| Mitigation applied and its effect | Intermediate investigation logs |
| Resolution confirmed | Supporting queries used during investigation |

A timeline row is a *state transition* (the system or the response changed), not a *task* (what someone did). "14:45 — @alice checked the job queue" is a task; "14:45 — Job queue depth confirmed at 847 queued jobs; worker service running normally" is a state transition. State transitions belong; tasks do not.

**Detection Gap subsection:** After the timeline table, add a `### Detection Gap` paragraph: how long between incident start (`started_at`) and first detection (`detected_at`), and whether that gap was avoidable. This is the metric that drives alerting improvements.

### C3. Restructure to Postmortem

Load `[sdlc-root]/templates/postmortem_template.md`. Keep the incident doc in place; restructure its body to match the template sections:

- **Summary** — one paragraph synthesizing what happened and how it was resolved.
- **Timeline** — from C2.
- **Impact** — users affected, duration, data loss (none / specific), revenue (usually none pre-launch).
- **Root Cause** — lifted from the TRIAGE doc's Root Cause section, cleaned up.
- **Contributing Factors** — lifted from TRIAGE, numbered.
- **Detection** — how detected, time to detect, could it have been faster.
- **Response** — what worked (as paragraphs) + what could be improved (as paragraphs).
- **Action Items** — table mapping each item to its Deliverable ID. Every row must have a `Deliverable ID` column value — either `D{NN}`, `housekeeping`, or `backlog`.
- **Lessons Learned** — systemic insights, not "don't do the bad thing again." 5-8 items.

#### Blameless Framing Discipline

**This is not optional.** A postmortem written with blame framing will be hidden and never referenced again. A blameless postmortem will be read, cited, and prevent the next incident.

The test is simple: replace "the engineer" with "the system." If the sentence still makes sense and describes a real problem, it's a system problem. If it falls apart, you were blaming a person.

**Language patterns to reject → patterns to use instead:**

| Reject | Use instead |
|--------|-------------|
| "X failed to check Y before deploying" | "Y was unchecked at deploy time; the deploy pipeline had no gate requiring Y" |
| "The on-call engineer missed the alert" | "The alert fired at 02:30 UTC; the alert routing policy did not escalate until 03:00; the gap was 30 minutes" |
| "Nobody noticed the filter was missing" | "The filter was absent in the query; no isolation audit existed for this code path" |
| "The worker was misconfigured" | "The registration used a data structure that silently dropped the second entry" |
| "The developer didn't understand the async lifecycle" | "The async session was closed before relationship traversal; the error was not caught in staging because the test fixture used synchronous sessions" |

**The framing test in practice:** After writing each sentence in Root Cause, Contributing Factors, and Lessons Learned, ask: *Does this sentence lead to "fire/retrain/blame the person" or "fix/add/improve the system"?* If the former, rewrite it.

**Blameless does not mean consequences-free.** Identifying that a system allowed a mistake does not prevent human accountability for decisions made in that system. Blamelessness is about the *postmortem document* — its job is to improve systems. Personnel decisions are separate and made elsewhere.

#### Root Cause vs. Contributing Factor Discipline

The distinction matters because they drive different action items.

- **Root cause (proximate):** The single condition whose absence would have prevented the incident from occurring. There is exactly one, even if it is uncomfortable to name it.

- **Contributing factors:** Conditions that allowed the root cause to exist or to persist undetected. There can be many. Each one should be distinct — if two contributing factors trace to the same underlying condition, merge them.

**5 Whys applied carefully:** Ask "why?" for each contributing factor until you reach a system-level answer. Stop before you reach a person-level answer. The stopping criterion is: *"Would this cause have existed regardless of which individual was involved?"*

| Depth | Question | Acceptable stopping point? |
|-------|----------|---------------------------|
| 1 | Why did the incident occur? | No — this is the symptom |
| 2 | Why did [root cause] exist? | Sometimes — if the answer is a missing system check |
| 3 | Why did [system check] not exist? | Usually — this is the system-level finding |
| 4 | Why was [system check] not built? | Edge cases — if it reveals a missing process |
| 5+ | Why did [person] not build it? | Stop here — you've reached a person, not a system |

#### Action Item SMART Discipline

Every action item in the postmortem table must be usable as-is for writing a deliverable description in `sdlc-plan` or `sdlc-lite-plan`. A vague action item produces a vague plan.

**SMART criteria for postmortem action items:**

| Criterion | What it means | Bad example | Good example |
|-----------|---------------|-------------|--------------|
| **Specific** | Names the exact thing to build or fix | "Improve isolation" | "Add tenant filter assertion to all query call sites in the affected service files" |
| **Measurable** | Defines done — a test, a metric, an audit result | "Better monitoring" | "Alert fires within 2 minutes when queue depth exceeds threshold; verified by load test" |
| **Assigned** | Names the deliverable tier and which agent owns implementation | "Engineering to fix" | "D{NN} — `sdlc-lite` — `backend-developer` + `data-architect`" |
| **Realistic** | Can be scoped as a single deliverable | "Rewrite the entire service" | "Add warm-up check to service startup; block requests until ready" |
| **Time-bound** | Has a relative deadline or blocking condition | (no date) | "Before next production deploy; blocks D{NN+1}" |

In the action items table, include columns: `Priority | Action | Deliverable ID | Tier | Owner Agent | Blocking`. The `Blocking` column captures whether this action blocks another deliverable — this is what sdlc-plan needs to sequence work.

**Orphan action items are failures.** An action item without a Deliverable ID means it will never be done. Assign `housekeeping` if it is too small for a deliverable, `backlog` if it is real but deliberately deferred, or `D{NN}` if it maps to a specific deliverable. There is no fourth option.

#### "Where We Got Lucky" Section

Add this as a subsection within Lessons Learned. It documents conditions that were favorable during this incident but cannot be relied upon next time. This is not the same as "What Went Well" — "went well" means the team did something right; "got lucky" means the environment was merciful.

Examples:
- "The incident occurred during business hours; an identical incident overnight would have required a paged response with a smaller team."
- "The data leak returned data from only one other tenant, which happened to be a test account. If the order had been reversed, a real tenant's data would have been exposed."
- "The queue had no in-flight jobs at the time of failure, so no work was lost. A failure during active processing would have required manual recovery."

Naming lucky conditions is blameless — it acknowledges that the outcome could have been worse *without* implying the team was negligent. It also drives the most concrete action items: reduce exposure to the luck condition.

#### Postmortem Reusability Discipline

Three things make a postmortem reusable:

**1. Cross-reference related incidents.** At the end of the Appendix (A5), reference any prior incident with a similar symptom or root cause. If the current incident is a recurrence, note what action items from the prior incident were not completed — those are the direct cause of the recurrence.

**2. Searchable terminology.** The Summary and Root Cause sections should use canonical terminology for the failure class (e.g., "connection pool exhaustion" not "db issues", "tenant isolation violation" not "data bleed"). Consistent terminology means searching the incident archive finds the full history of each failure class.

**3. Periodic cross-incident pattern review.** After 4+ postmortems exist, the incident archive should be reviewed periodically: which root cause categories recur, which action items were never closed, which lucky conditions are still present. Note this in C9 (Handoff to Archival): when archiving, check for pattern recurrence across the archive.

### C4. Preserve Hypothesis Log as Appendix

Do NOT delete the Hypotheses, Ruled Out, or Dispatched Agents sections from TRIAGE. Move them to an `## Appendix: Investigation Log` at the end. That content is the reusable learning — future you on a similar incident will mine it.

Structure the appendix with these subsections:

```markdown
## Appendix: Investigation Log

### A1. Hypotheses Investigated
{Original H1, H2, ... list with final status per hypothesis}

### A2. Ruled Out
{Each ruled-out hypothesis with the evidence that falsified it and timestamp}

### A3. Dispatched Agents
{The Dispatched Agents table from TRIAGE, with key findings preserved}

### A4. Supporting Data
{Links or inline snippets of:
- Metrics graphs at time of incident
- Query plan output if the investigation included query analysis
- Connection/process state snapshots taken during incident
- Any other raw diagnostic data captured during T2a first-response checklists}

### A5. Related Incidents
{Links to prior postmortems with similar symptom or root cause class}
```

The appendix is read by two audiences: (1) the engineer investigating *the next* incident with a similar symptom, who will scan A2 to skip ruled-out hypotheses and A1 to find the confirmed cause; (2) the future engineer doing a periodic pattern review, who will scan A5 cross-references across incidents. Write each section for those readers, not as a dump of the raw triage log.

### C5. Update Frontmatter

```yaml
status: complete  # or 'partial' if some deliverables are still in-flight
resolved_at: YYYY-MM-DDTHH:MM:SSZ
peak_impact: {concise description — e.g., "~20 GB RSS, 14-minute eval blockage"}
```

### C6. Self-Review

Dispatch `code-reviewer` on the final postmortem with the following lens:

- Every action item has an owner and a deliverable ID
- Root cause is specific, not vague ("a bug" is not a root cause per `[sdlc-root]/process/incident_response.md`)
- Contributing factors are distinct from root cause and from each other
- No blame assignment — focus is on systems, not people (apply the framing test: does the sentence lead to "fix the system" or "fix the person"?)
- Lessons learned are generalizable — they would help on *a different* incident
- Action items are SMART: specific (names the code path or system), measurable (defines done), assigned (deliverable tier + agent), realistic (single deliverable scope), time-bound (has a deadline or blocking condition)
- "Where We Got Lucky" is present and distinct from "What Went Well"
- Timeline rows are state transitions, not task logs; Detection Gap subsection is present
- Appendix A5 cross-references prior incidents with similar symptom class
- No rejected blameless-framing patterns: scan for "failed to", "didn't check", "missed the", "nobody noticed" — each instance should be rewritten as a system condition

Apply findings before marking closeout complete.

### C6a. Architecture Decision Crystallization Check (skip-if-absent)

If `docs/architecture/decisions/` does not exist, skip. If it does and the remediation changed architecture (new service boundary, dependency direction change, safety default, defensive pattern — see `[sdlc-root]/process/adr-practice.md` § Crystallization Signals), dispatch the architect agent to draft an ADR with `triggered_by` citing this postmortem. Pure bugfixes skip the ADR; the check runs either way.

### C7. Link from Catalog and Deliverables

For each deliverable in `related_deliverables`:

- Add a line to the deliverable's result doc: `**Triggered by:** [incident YYYY-MM-DD](../../current_work/incidents/incident_YYYY-MM-DD_{slug}.md)`
- Optionally add a row for the incident in `docs/_index.md` under a new `## Incidents` section if the project adopts that convention (propose to user — this is a project-level choice).

### C8. Session Learning Capture

Incident investigation and closeout surface cross-discipline insights — architecture anti-patterns that enabled the failure, testing gaps that delayed detection, observability blind spots, deployment friction. The postmortem's Lessons Learned section captures incident-specific takeaways, but discipline-level patterns belong in parking lots where they feed the triage cycle.

If this CLOSEOUT surfaced non-obvious learnings beyond the postmortem itself, suggest:

> This incident may have surfaced cross-discipline insights worth capturing (architecture patterns, testing gaps, observability blind spots). Consider running `/sdlc-reflect` to surface them to discipline parking lots.

Skip the suggestion if the postmortem's Lessons Learned already covers everything and no broader discipline patterns emerged.

### C9. Handoff to Archival

STOP. Do not auto-archive. Archival to `docs/chronicle/{concept}/` happens later, when the user invokes `sdlc-archive` and the incident's related deliverables have all completed and themselves been archived.

---

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll investigate this myself — no need to dispatch" | Manager Rule applies here exactly as in planning. Dispatch `debug-specialist` + specialists. |
| "I'll skip the incident doc — the incident is small" | Even small incidents have reusable lessons. Small incidents → small docs, but there's no floor at which the doc becomes pointless. |
| "I'll name the root cause during T1 from the symptom alone" | Root cause is a conclusion, not a hypothesis. Log it as H1, verify, then move to Root Cause. Premature convergence ends investigation. |
| "I'll delete ruled-out hypotheses to keep the doc clean" | Preserve them. The next engineer investigating a similar symptom wants to see what you checked and why it wasn't that. Ruled-out is signal, not noise. |
| "I'll write the remediation plan inside the closeout" | Out of scope. Hand off to `sdlc-plan` or `sdlc-lite-plan`. Incident skill identifies deliverables; planning skills write them. |
| "I'll auto-run closeout as soon as triage identifies a cause" | No. Closeout requires remediation deliverables to exist. Without them, "Action Items" is empty, which is the useless part of a postmortem. Wait. |
| "I'll merge the triage log into the timeline and delete it" | The hypothesis log becomes the Appendix. Timeline is distinct — it's the ordered public-facing narrative, the appendix is the investigator's scratch pad preserved. |
| "I'll dispatch 8 agents to be thorough" | Over-dispatch dilutes signal. 3-5 with clear domain lenses outperforms 8 with overlapping scope. |
| "I'll use a different template — the project's is too long" | Use `[sdlc-root]/templates/postmortem_template.md` verbatim. Consistency across incidents makes the chronicle searchable. |
| "The kernel OOM-killed us, so there's nothing to investigate — just restart" | SIGKILL leaves no trace, but the conditions that led to the kill are everywhere else: traffic patterns, resource curves, config state. Run TRIAGE. |
| "This is the same as last month's incident, copy-paste the old doc" | New doc, reference the old one. A fresh investigation might find that the cause is different even if the symptom matches. Copying hides regressions in root-cause understanding. |
| "Agent H1 returned first and it looks right — close investigation" | Wait for all dispatched agents to return before arbitrating (T5a). A parallel investigation that returns second with contradicting evidence is the whole value of parallel dispatch. |
| "Two agents confirmed different hypotheses — pick the one I find more intuitive" | Apply the arbitration protocol (T5a). Confidence level, evidence count, causal chain completeness, and absence of contradicting evidence are the ranking criteria — not intuition. |
| "I'll skip the first-response checklist and go straight to hypothesis generation" | The runbook checklists (T2a) are non-destructive reads that take 3-5 minutes and produce evidence that makes hypothesis generation faster and more accurate. Skipping them means agents get symptom descriptions instead of observed data. |
| "I need to run this mitigation immediately — the incident is active" | Every destructive command (kill connections, rollback, scale-down) requires a dry-run count check first. Running it wrong during an incident adds a secondary incident on top of the first. Verify count, then execute. |
| "I'll figure out the on-call handoff later once things settle" | The handoff bullets (T2c) should be ready before they're needed, not after. A handoff written under pressure with no template is how critical context gets dropped between responders. |
| "The postmortem says 'the team failed to add a filter' — that's just what happened" | That is blame framing. Rewrite: "The filter was absent; no audit existed in the CI pipeline or review checklist for this code path." The system allowed the omission — name the system gap, not the omission. |
| "I have a root cause and three contributing factors — one action item will fix everything" | Root cause and contributing factors drive distinct action items. A contributing factor that was not addressed directly will be the root cause of the next incident. Each contributing factor needs its own SMART action item or an explicit decision to accept the risk. |
| "The action item is 'improve monitoring' — that's good enough" | That is not a SMART action item. It names no specific code path, no measurable done-state, no deliverable tier, no assigned agent. Be specific about what to build, how to verify it works, and who owns it. |
| "We got lucky, but that's fine — the incident resolved cleanly" | Lucky conditions that remain unaddressed are incidents waiting to happen. Document the lucky condition in "Where We Got Lucky" and create a SMART action item to eliminate reliance on that luck, or a documented risk-acceptance decision. |
| "The 5 Whys led me to 'the developer was unfamiliar with the pattern' — that's the root cause" | You went one level too deep. A person is not a root cause. Back up one level to the system-level finding: "The pattern was not documented in the codebase; tests used a fixture that masked the violation." |
| "I'll skip the 'Related Incidents' appendix section — this is a one-off" | Every incident feels like a one-off until you search the archive and find three prior incidents with the same root cause class. Write the cross-reference, even if it says "no prior incidents found." |
| "The timeline has a row for every action the on-call engineer took — this is thorough" | Timeline rows should be state transitions (system state changed, incident state changed), not task logs (person did a thing). Move task logs to the appendix. |
| "I'll hardcode the agent matrix in this skill" | No — the matrix lives in `agent-selection.yaml` so it stays consistent with planning and review. If a project adds a new domain agent, it shows up in incident triage automatically. |

---

## Integration

- **Depends on:** An observable incident signal — user report, alert, or visible service degradation. Does not run speculatively.
- **Feeds into:** `sdlc-lite-plan` and `sdlc-plan` for remediation deliverables. `sdlc-reflect` (CLOSEOUT suggests it for cross-discipline insights beyond the postmortem). `sdlc-archive` eventually, when all related deliverables complete.
- **Uses:** `debug-specialist` agent (primary diagnostic during TRIAGE), domain specialists per `[sdlc-root]/process/agent-selection.yaml`, `code-reviewer` for CLOSEOUT review, and project observability tooling (whatever your stack uses) via the corresponding MCPs or CLI access.
- **Complements:** `sdlc-audit` (proactive systemic review — different trigger, different purpose), `sdlc-review-code` (code-level review), `sdlc-playbook-generate` (turns a resolved incident + its remediation into a reusable playbook — runs AFTER CLOSEOUT).
- **Does NOT replace:**
  - The `debug-specialist` agent itself, which can still be dispatched directly for non-incident debugging (e.g., a failing test).
  - `sdlc-plan` / `sdlc-lite-plan`, which own remediation planning. This skill hands off to them.
  - `sdlc-audit` (proactive, curiosity-driven, no triggering incident).
- **DRY notes:** This skill does not duplicate `[sdlc-root]/process/incident_response.md` — it references the process doc for severity classification, triage workflow principles, and postmortem timeline conventions. This skill is the *executable orchestration* of that process. The postmortem template at `[sdlc-root]/templates/postmortem_template.md` is also referenced rather than reinvented; CLOSEOUT's output conforms to it.

---

## Additional Resources

- `[sdlc-root]/process/incident_response.md` — severity classification (SEV-1 to SEV-4), triage workflow, postmortem principles, deliverable lifecycle connection. Read before TRIAGE if you haven't recently.
- `[sdlc-root]/templates/postmortem_template.md` — the canonical postmortem structure. CLOSEOUT output conforms to this template.
- `[sdlc-root]/process/agent-selection.yaml` — domain-to-agent mapping used during T3. Single source of truth shared with planning and review skills.
- `[sdlc-root]/knowledge/architecture/debugging-methodology.yaml` — structured investigation methodology used by `debug-specialist`. Injected into TRIAGE dispatch prompts per the knowledge injection protocol above.
- `[sdlc-root]/process/manager-rule.md` — required reading. You orchestrate; agents investigate.
- `[sdlc-root]/process/collaboration_model.md` — ask-user gates in this skill follow this doc.
- `[sdlc-root]/process/deliverable_lifecycle.md` — canonical state transitions for deliverables and the incident doc itself.
- `[sdlc-root]/process/finding-classification.md` — when incident TRIAGE produces findings, classify them per this doc (FIX / DECIDE / PRE-EXISTING).
