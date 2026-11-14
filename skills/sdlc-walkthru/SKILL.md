---
name: sdlc-walkthru
description: >
  Required procedure for presenting an SDLC artifact (spec, plan, result doc, review-findings doc)
  as a guided, part-by-part interactive walkthrough in lieu of an HTML explainer — CD paces with
  "next", asks questions answered against real code, and raises changes that are classified and
  routed to revision agents mid-walkthrough without losing the thread. Built for comprehension
  without reading the whole document: comprehensive in content, small in bites.
  Use when a finished or draft SDLC artifact needs a paced, comprehension-first read instead of
  a static one — especially before an approval gate.
  Triggers on "walk me through the spec", "walk me through the plan", "walkthrough the doc",
  "walkthru the spec/plan", "guide me through the doc", "explain it part by part",
  "go through the doc with me", "/sdlc-walkthru".
  Do NOT use for producing an HTML picture explainer — use sdlc-explain.
  Do NOT use for agent/technical review of artifact content — use sdlc-review-code or the
  invoking skill's review roster; this skill is for the human decision-maker's read.
  Do NOT use for open-ended exploration of an idea with no artifact yet — use sdlc-idea.
---

# SDLC Artifact Walkthrough

Present a finished (or draft) SDLC artifact as a guided tour: segmented into story-sized parts, delivered one part per turn at the reader's pace, with questions answered from verified code and change requests routed to agents mid-flight. The walkthrough replaces the wall-of-text read — the reader ends up understanding every load-bearing decision without having consumed the document linearly.

**Argument:** path to the artifact to walk through (spec, plan, result doc, findings doc), or an artifact reference the catalog can resolve ("the D41 spec"). If the invoking context just wrote the artifact, no argument is needed.

**Why this exists:** a document's job is durability; a decision-maker's job is judgment. Those need different formats. Reading a 400-line spec front-to-back is monotonous and low-retention; a paced walkthrough of the same content surfaces sharper questions and better decisions. The document remains the source of truth; the walkthrough is how a human actually absorbs it.

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## Workflow

```
PREFLIGHT (read + segment) → OPENING (map + pacing contract)
  → PART LOOP: deliver part → [questions → verify-then-answer]
                            → [feedback → classify → dispatch → keep walking]
                            → "next"
  → WRAP-UP (recap + changes made) → hand back to the invoking gate
```

## Manager Rule

Read and follow `[sdlc-root]/process/manager-rule.md`. The walkthrough narration is yours; artifact revisions triggered by feedback are dispatched to the artifact's writing agent (a background agent dispatch, per the invoking skill's dispatch protocol, while the walkthrough continues). Dispatch prompts describe WHAT changed and WHY — implementation of the revision is the agent's domain.

## Steps

### 1. Preflight — read and segment

1. **Read the entire artifact.** You cannot walk through what you have not fully read. If the artifact cites a feasibility doc, decision log, or prior-decision records, read those too — questions will reach them.
2. **Segment into as many parts as the content needs — by story, not by section headers.** Target 4–7 parts for a typical artifact; never cram to hit a count. The document's structure serves completeness; the walkthrough's structure serves comprehension. Good part boundaries: "what this is", "the core mechanism", "what users see", "the guardrails / what we won't do", "the data / evidence", "the open decisions". A part may span three document sections or a third of one.
   **Past ~8 parts, group them into 2–4 chapters** (e.g. "Chapter 2 — the backend, parts 4–8"). The map stays one glance, progress stays visible, and each chapter boundary is an exit ramp: offer "full detail or the short version?" per chapter, so a long artifact never forces a long walkthrough. The ≤350-word budget applies per part, never stretched to absorb an under-segmented artifact.
3. **For each part, identify the one load-bearing claim** — the sentence the reader must retain even if they forget everything else in the part. The part is built around it.
4. **Note every open decision and `USER DECISION NEEDED` marker** — these must surface during the walkthrough, never be skipped past.

### 2. Opening — map and pacing contract

One message containing:
- What the document is and where it sits in the process (e.g., "this is the spec — the *what and why*; approving it starts planning").
- The one-sentence story of the whole artifact.
- A part map: numbered parts with 3–6-word titles (a table if ≥5 parts), so the reader always knows where they are and how much remains.
- The pacing contract, verbatim in spirit: **"Say 'next' when ready, stop me anywhere, ask anything."**
- Then deliver Part 1 or wait — match the reader's energy; when in doubt, deliver Part 1 in the same message.

### 3. Part delivery rules

Each part is one message, and each message obeys:

- **Lead with the claim, not the structure.** "The ranking must be honest before it is advertised" — then the supporting detail. Never "Section 4 covers the design approach."
- **Target ≤350 words of prose per part.** Comprehensive means *nothing load-bearing omitted*, not *everything transcribed*. Detail that doesn't change the reader's understanding or decision stays in the document.
- **Number and title every part** ("Part 3 of 6 — what users see") so progress is always visible.
- **Tables only for genuinely enumerable content** (sub-deliverables, options, measured results) — explanation lives in prose around them, never inside cells.
- **Bold the load-bearing decisions** and any sentence the reader will be asked to approve later.
- **Translate jargon at the point of use.** One clause, inline: "a sentinel — a special 'no data' signal hiding inside the normal number range."
- **Connect to the governing principle where one applies.** Consult `[sdlc-root]/knowledge/agent-context-map.yaml` for where the project's standing principles live, and honor any terminology directives the project records (in its CLAUDE.md or a configured convention).
- **End with a hook**: "Say 'next' for Part 4 — the two defects users can see."
- **Never deliver two parts in one message**, even if the reader seems fast. Pace is the product.

### 4. Questions mid-walkthrough

- **Verify before answering.** Follow the Code Verification Rule (in the project's CLAUDE.md): if the question touches how code behaves ("how did that 40 get computed?"), read the actual code first, then step through it with real values. An answer sourced from the artifact's own claims is only acceptable when the artifact itself verified them — say which it is.
- **Escalate depth on demand.** A "explain step 3 further" gets a deeper, slower pass on that one point — not a repeat of the summary.
- **Reach for a picture when a picture beats prose.** Two tools, by shape of the question: when the reader is circling one mechanism and needs to *see* it, invoke `sdlc-explain` for a big-pictures-few-words explainer of that mechanism (static, inline SVG, verified against code); when they need to *manipulate* it — sliders, worked numbers, a step-through with real values — build an interactive exploration artifact in `docs/current_work/ideas/` and open it in the browser. Don't build either for a question a paragraph answers. If asked whether an artifact is faithful, verify every claim in it against source and say what was corrected. Both follow `[sdlc-root]/process/html-rendering.md` § "Visual Doctrine: Big Pictures, Few Words".
- **Wrong-premise corrections flow back.** If the reader corrects a fact, the correction is load-bearing: restate it, verify its implications, and treat it as feedback (step 5).

### 5. Feedback mid-walkthrough — classify, dispatch, keep walking

Reader feedback during a walkthrough is the point, not an interruption.

1. **Classify** using the invoking skill's revision protocol. For specs, that is `sdlc-plan`'s SPEC-REVISION block (WORDING / SCOPE_CHANGE / PIVOT). For plans, use `sdlc-plan` step 5's finding-incorporation flow: FIX-level content changes re-dispatch to the plan's writing agent; product decisions route to CD. If the invoking context defines no protocol, apply the SPEC-REVISION classification by analogy and say so. Do not re-define classification here — use the owning skill's.
2. **WORDING-level**: the orchestrator may edit directly. **SCOPE_CHANGE / PIVOT**: dispatch the artifact's writing agent with a focused delta, in the background.
3. **Keep walking while revisions run.** Announce briefly ("the spec author is revising those sections now"), then continue to the next part — the walkthrough does not block on the revision unless the next part depends on the changed content.
4. **Record decisions where they live**: product decisions into the artifact and its decision record (feasibility doc, provenance log); standing principles into the knowledge layer per `[sdlc-root]/process/discipline_capture.md`. A decision made mid-walkthrough that only lives in the conversation is a decision lost.
5. **Report revisions when they land**, in one or two sentences, and correct anything already walked through that the revision changed.

### 6. Wrap-up and hand-back

After the final part:

- **Recap in one short paragraph** what the reader would be approving/accepting — the whole artifact compressed to its decisions.
- **List changes made during the walkthrough** (classification, what changed, where recorded) so the reader knows the document they heard is the document that now exists.
- **Surface any open decisions** that remain unmade.
- **Hand back to the invoking gate.** If the walkthrough served an approval gate (spec approval, plan approval), the gate comes *after* the walkthrough fully resolves, in its own turn and in the form the invoking skill defines (for spec and plan approval, the Approval Brief message that ends the turn — `[sdlc-root]/process/writing-for-cd.md` § Approval Briefs), never bundled into the final part. The walkthrough is the alternative to the HTML explainer at that gate: like the explainer, it must complete *before* the approval question, never after.

## Output

Usually none — the walkthrough is an interaction, not an artifact. Two exceptions:
- **Exploration artifacts** built for questions (step 4) persist in `docs/current_work/ideas/`.
- **Revisions and decision records** produced by feedback (step 5) land in their normal homes (the artifact file, feasibility doc, knowledge layer, changelog as applicable).

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll deliver all the parts in one message to save time" | Pacing is the mechanism. A wall of parts is the wall of text this skill exists to replace. One part per turn, reader-paced. |
| "I'll summarize aggressively so it's easy to consume" | Easy ≠ shallow. Every load-bearing decision, constraint, and open question must surface. Cut transcription, never substance — "spares no detail" and "≤350 words" coexist by selecting, not by omitting. |
| "The document's section order is the natural walkthrough order" | Segment by story. Document structure serves completeness; walkthrough structure serves comprehension. |
| "I remember how that code works — I'll just explain it" | Verify-then-answer. Read the code, step through real values. A confident wrong answer in a walkthrough poisons the approval it feeds. |
| "The reader's question is a detour; I'll defer it to keep momentum" | Questions are the highest-value moments — they're where corrections surface. Answer fully, then re-offer the thread ("say 'next' to continue"). |
| "Feedback means the walkthrough failed; restart after the revision" | Feedback means it worked. Classify, dispatch in background, keep walking. |
| "I'll fold the approval question into the last part" | Never. Wrap-up resolves first (recap + changes made), then the gate question in its own turn. Same rule as explainer-precedes-approval. |
| "The reader seems impatient — I'll skip parts 4 and 5" | Ask, don't skip silently: offer "want the short version of the remaining parts, or stop here?" Skipped parts hide open decisions. |
| "A decision was made in conversation; the artifact can catch up later" | Record it now — artifact, decision record, knowledge layer as appropriate. Conversations get cleared; documents survive. |
| "This 1,000-line plan is too big to walk through" | Size is why the walkthrough exists. Use as many parts as it needs, grouped into chapters with per-chapter depth choices — never cram a big artifact into 7 oversized parts. |
| "More parts = more thorough, I'll make 20 flat parts" | Flat part counts past ~8 kill the map's scannability and the reader's stamina. Chapters + exit ramps, not an endless corridor. |

## Integration

- **Depends on:** an existing artifact to walk through; the invoking skill's revision protocol for classifying feedback (e.g., `sdlc-plan`'s SPEC-REVISION); `[sdlc-root]/process/manager-rule.md` for dispatched revisions.
- **Feeds into:** the invoking skill's gate (spec approval in `sdlc-plan`, plan approval, result acceptance). Decisions recorded during the walkthrough feed the feasibility/decision record and, for standing principles, the knowledge layer via `[sdlc-root]/process/discipline_capture.md`.
- **Uses:** the artifact's writing agent (for SCOPE_CHANGE/PIVOT revisions), `AskUserQuestion` (questions after wrap-up), `sdlc-explain` (a picture explainer of one mechanism mid-walkthrough), exploration HTML artifacts (optional, per `sdlc-plan`'s interactive-exploration-artifacts provision).
- **Complements:** `sdlc-explain` — same offer point, different consumption mode. The explainer is a lossy picture artifact; the walkthrough is comprehensive and conversational and produces decisions. Whichever CD picks must fully resolve before the approval question (`[sdlc-root]/process/html-rendering.md` § Post-Skill Offer).
- **Does NOT replace:** `sdlc-explain` (a lossy picture explainer — the walkthrough is comprehensive and conversational), `sdlc-review-code` and domain-agent plan review (technical correctness review — this skill serves the *human* read), `sdlc-idea` (no artifact yet).
- **DRY notes:** revision classification is deliberately NOT defined here — it belongs to the owning skill (`sdlc-plan` SPEC-REVISION et al.) and is referenced. Code verification, terminology, and manager-rule content are referenced from their canonical homes. The only novel content here is the walkthrough method itself (segmentation, pacing, part-delivery rules).
