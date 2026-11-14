## GitHub Checkpoints

**Activation gate:** skip this entire section unless `[sdlc-root]/process/github-checkpoints.md` exists and its config block says `enabled: true`. In a headless run, unless the caller's prompt hands checkpoints to the run, each checkpoint below does only its local half (issue links when the issue is known, the local artifact commit) and puts its GitHub half under the result's `outbound` as a rendered entry for the caller. A headless run whose prompt names the deliverable's issue also writes any missing issue links (`github_issue:` frontmatter, the catalog link) before its own work, even when it skips registration (`[sdlc-root]/process/github-checkpoints.md` § Headless Runs).

This skill owns **CP-4, CP-5, CP-7, CP-8**, and the conditional **CP-S1/CP-S2** pair. It owns **neither CP-6 nor CP-9** — the checkpoint map assigns CP-6 to `sdlc-execute` only, and lite deliverables stop at the `validated` column.

**Read `[sdlc-root]/process/github-checkpoints.md` before firing any of them.** That document is the policy: what each checkpoint says, where it moves the card, the comment templates, the column roles/names/ranks, the floor rule, the never-block invariant, SHA-pinned link policy, commit conventions, terminology, content prohibitions, and the failure classes. None of it is restated here. The mechanics — the exact `gh`/`git` calls — are the named recipes in `sdlc-manage-github` § SDLC Checkpoint Recipes; call them by name rather than assembling commands.

Two operating rules govern every checkpoint below: a checkpoint **never** blocks, stalls, or aborts the step it sits inside (on failure: `log-miss`, one-line notice, continue), and the **comment posts before any Status write**. Only **CP-8** pays git cost in this skill — every other checkpoint here links commits that are already pushed, or links nothing.

### CP-4 — execution begins

Fires once the phase plan is emitted and before the first phase dispatches. Comment what is starting, in what order, and which agents are dispatched. Status → `executing` via `resolve-and-write-status`.

### CP-5 — a phase completes

Fires when a phase's POST-GATE clears. Comment-only — no Status write; the card stays at `executing`. Comment what that phase produced, in plain language, plus anything that changed relative to the plan.

**Threshold:** CP-5 is **required only when the deliverable has three or more phases**, and optional below that. Lite plans cap at four phases and most run two, so the common outcome here is legitimately "not required" — a two-phase lite deliverable that skips CP-5 has not missed a checkpoint.

### CP-S1 / CP-S2 — conditional, position-independent

These are **not** sequential steps. They are a branch available at **any** point during execution — a decision owed by any configured stakeholder role can block between two phases just as easily as during the review loop.

- **CP-S1** fires when the deliverable becomes blocked on a decision owed by a stakeholder role listed in the policy doc's config block — because CD did not resolve it or explicitly deferred it. Status → `stakeholder-blocked`.
- **CP-S2** fires when that stakeholder answers and work resumes. Status → `executing`. This is the system's only backward write, guarded by an exact-match precondition — `resolve-and-write-status` implements the guard, so pass its `is_cp_s2` flag and let the recipe decide rather than checking the current column yourself.

The `stakeholder-blocked` column means **awaiting stakeholder feedback**, and nothing else. The internal review loop never writes it — the card stays at `executing` throughout. (That distinction is CP-6's job in the full-SDLC flow; lite deliverables have no CP-6, so the rule shows up here instead: the review loop moves no column.)

### CP-7 — review loop exited, work committed

Fires after the review loop meets its exit bar (no critical or major findings open) and the work is committed. Comment-only — no Status write. Comment what shipped in plain language, the commit SHAs and any pull-request links, and any deviation from the plan and why. The commits are already pushed, so this checkpoint pays no git cost.

### CP-8 — result doc written, catalog moves to Validated

Fires once the result doc is written and the catalog row moves to Validated. Commit and push the result doc (and the catalog row) via `commit-and-push-artifact`, comment the outcome, the verification evidence, the deviations, and the known follow-ups with a SHA-pinned link to the result doc, then Status → `validated` via `resolve-and-write-status`.

**CP-8 is the ceiling of SDLC board tracking for a lite deliverable.** There is no CP-9 here; nothing in this skill writes a Status past the `validated` column.
