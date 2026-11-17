# GitHub Checkpoints

The SDLC narrates every deliverable it tracks into a **GitHub issue** — created when a
D-number is minted, commented at each meaningful checkpoint, moved forward across the
project's GitHub Projects v2 board (when one is configured), and closed when the work is
chronicled. The catalog (`docs/_index.md`) stays canonical; the issue is a **projection** of
it, readable by people who will never open a markdown vault.

This document is the **policy**. It owns:

- the checkpoint map (what fires, when, what it says, where it moves the card),
- the board Status **column roles, their configured names, and their ordinal ranks**,
- the **floor rule** and its single documented exception,
- comment templates, terminology, and content prohibitions,
- the SHA-pinned link policy and the commit conventions,
- the failure **classes** and the never-block invariant,
- repo selection, board selection, never-reopen, and catalog-wins.

It does **not** own mechanics. No `gh` command sequences, no git command sequences, no field
IDs, no option IDs appear here — not even as examples. Those live in the
**`sdlc-manage-github`** skill, which implements the recipes named in
§ Recipes `sdlc-manage-github` Must Provide and **reads the ranks from this document's
config block** rather than restating them.

This mirrors an established precedent exactly: `[sdlc-root]/process/external-review-gate.md`
is the policy doc that skills point at, and `[sdlc-root]/external-review.sh` is the mechanism.

**Who points here.** Eight framework files carry checkpoint sections (installed as
`BUNDLE-SECTION` fragments of the `github-provenance` bundle) that point at this document:
`sdlc-plan`, `sdlc-lite-plan`, `sdlc-execute`, `sdlc-lite-execute`, `sdlc-handoff`,
`sdlc-archive`, `sdlc-audit`, and the `sdlc-compliance-auditor` agent. None of them restates
policy.

---

## Activation and Configuration

The convention is **inert until configured**. Every consumer applies the same two-stage gate:

1. This file exists (the `github-provenance` bundle is installed), **and**
2. The config block below says `enabled: true`.

If either fails, checkpoint sections in the skills are skipped entirely and the audit
dimension reports "not applicable — convention not installed/not configured." Installing
without configuring is a valid resting state.

The config block is the **project's** data — it lives inside `PROJECT-SECTION` markers so
migrations update this document's policy body while preserving the configuration verbatim.
Fill it via § Enablement; never set `enabled: true` by hand without completing that section.

<!-- PROJECT-SECTION-START: config-github-provenance -->
```yaml
enabled: false                # set true only as the LAST step of § Enablement

github:
  host: github.com            # GitHub Enterprise hosts are untested; verify gh support first
  org: ""                     # org or user that owns the repos and the board

repos:
  driving: []                 # candidate driving repos (bare names, e.g. [my-app, my-api]).
                              # Single-repo projects list exactly one entry.

board:
  default: none               # Projects v2 project number, or `none` for issues-only mode
                              # (no Status writes anywhere; comments and issue lifecycle only)
  status_field: Status        # the single-select field checkpoints write — the ONLY board
                              # field the SDLC ever writes
  human_fields: []            # board fields humans own (see § Board Fields: Ownership), e.g.
                              #   [Test Verdict, Validity, Correctness, Effort, Priority]

# Column roles → the names this project's board uses, with ordinal ranks.
# Ranks are the floor-rule join key — never option IDs. A role mapped to `null`
# makes every checkpoint targeting it comment-only.
columns:
  - { rank: 1, role: registered,          name: Backlog }
  - { rank: 2, role: spec-approved,       name: Ready }
  - { rank: 3, role: executing,           name: In progress }
  - { rank: 4, role: stakeholder-blocked, name: Review Pending }
  - { rank: 5, role: validated,           name: Ready for Staging Deploy }
  - { rank: 6, role: staged,              name: Acceptance Testing }

# NEVER-WRITE: columns owned by whoever runs the production deploy pipeline.
# No checkpoint or recipe may ever target them; ranks above every SDLC write.
never_write:
  - Ready for Production Deploy   # NEVER-WRITE:
  - Deployed                      # NEVER-WRITE:

labels:
  universal: sdlc             # applied to every SDLC-tracked issue, always
  conditional: {}             # label → plain-language condition, e.g.
                              #   design: "the deliverable has a visual or UX surface"
                              #   user-facing: "users of the product will notice the change"
  human: []                   # labels only humans apply — never a checkpoint (e.g. [copy])

issue_types: default          # `default` = Bug/Feature/Task per § Issue Types;
                              # `none` for orgs without GitHub issue types enabled

stakeholders: {}              # role → what they decide, e.g. { CEO: product, CCO: design }.
                              # CP-S1/CP-S2 fire only for decisions owed by a role listed here.

terminology: []               # binding word-choice directives for all issue text, e.g.
                              #   - "never 'users'; say 'members' (default), 'guests' (dine-in)"

sensitive_data: []            # project data categories that must never appear in issue text,
                              # on top of the universal prohibitions in § Content Prohibitions

reconciliation_cutoff: null   # first in-scope D-number (e.g. D14); set at enablement, never moved
```
<!-- PROJECT-SECTION-END: config-github-provenance -->

Checkpoints in this document target columns **by role**; `sdlc-manage-github` resolves role →
configured name → option ID on the target board, per session. Two roles must be mapped for
the convention to function at all when a board is configured: `registered` and `executing`.

---

## Enablement

**Runbook:** `github-provenance-enablement` · **When:** enable · **Record:** `docs/runbooks/github-provenance-enablement.md` § Record

Run once, with CD, to activate the convention (`sdlc-run-runbook github-provenance-enablement` runs it; it fills the
config block, and keeps its record apart). Read § Activation and Configuration first: the block this fills.

**Ask first**, each with its recommendation: board or issues-only (step 3; the board when the project already
runs a Projects v2 board, else issues-only); the conditional labels (none to start), and whether to prune
GitHub's default labels (step 4; keep them unless CD wants them gone); and the block's `stakeholders`,
`terminology`, `sensitive_data` and `labels.human` (each left at its default unless CD names entries). **Done when:** every step passed and `enabled: true`. Completing this section — filling the config
block and setting `enabled: true` — **is CD's standing authorization for the entire
checkpoint map** (see § No Per-Call Human Confirmation).

1. **Preflight.** `gh` CLI installed and authenticated for the target host; the org resolves;
   **[CD]** confirms the token's account may create issues and (if a board is used) edit the
   project. Any failure stops enablement — never enable a convention whose first checkpoint
   would fail through. **Check:** `gh auth status` succeeds for the host, and CD's confirmation is in the
   record.
2. **Fill `github` and `repos`.** Confirm each driving repo's owner/name against its actual
   git remote, never from memory, and the rest of the block from the answers asked first. **Check:** each
   driving repo's owner/name equals its `git remote -v`, and `gh api orgs/<org>` (or `users/<user>`) resolves.
3. **Board, or issues-only.** If the project runs a Projects v2 board, set `board.default`
   to its project number and map every column role to that board's real column names —
   verify each name exists by fetching the board's fields live. Roles the board has no
   column for are set to `null` (their checkpoints become comment-only). List the
   deploy-pipeline-owned columns under `never_write`. If there is no board, set
   `board.default: none` — issue narration still runs in full. **Check:** every non-null column name is
   one of the board's live Status options (`gh project field-list`).
4. **Provision the taxonomy.** Create the universal label and any conditional labels in
   every driving repo (idempotent — an existing label is success). Record each conditional
   label's plain-language condition in the config block; the classification is owned here,
   not by calling skills. Optionally prune GitHub's default labels that have no consumer (a
   CD decision). If the org has GitHub issue types enabled, confirm the `default` set's
   names exist (or record custom ones); otherwise set `issue_types: none`. List any
   human-owned board fields under `board.human_fields`. **Check:** `gh label list` in each driving repo
   shows every label the config names.
5. **Gitignore the miss-log.** Ensure `[sdlc-root]/.local/` is gitignored before any
   checkpoint can write `[sdlc-root]/.local/github-checkpoint-misses.jsonl`. **Check:**
   `git check-ignore [sdlc-root]/.local/github-checkpoint-misses.jsonl` names the rule.
6. **Set the reconciliation cutoff** to the next unassigned D-number. Rows below it are
   pre-convention and permanently out of reconciliation scope. Set once; never moved. **Check:** the cutoff
   equals `docs/_index.md`'s next unassigned D-number.
7. **[CD] Set `enabled: true`** — last, after every step above verified: it is CD's standing
   authorization for the checkpoint map. Log the enablement in
   `[sdlc-root]/process/sdlc_changelog.md`. **Check:** the block reads `enabled: true` and the changelog
   entry is there.

To deliberately deactivate, set `enabled: false` — every consumer goes quiet; nothing is
deleted. Reconciliation findings that reflect config drift (a renamed board, a deleted
column) are repaired by re-running the relevant Enablement step.

---

## The Never-Block Invariant

**A checkpoint may never abort, stall, or slow the SDLC step it sits inside.**

This is the first thing to know about the whole system, because it constrains every other
rule here. A provenance log that can halt a build is worse than no provenance log. The
posture is identical to the one `external-review-gate.md` takes toward an external model,
and for the same reason.

Concretely:

- A failed GitHub or git operation gets **at most one** bounded remediation attempt per
  checkpoint (§ Failure Classes), then **fails through**.
- Failing through means: one short notice in session output, one entry in the miss-log, and
  **execution continues**. The SDLC step completes.
- Nothing in a checkpoint may wait on something slow or interactive. No sleeping for a rate
  limit, no backoff loop, no browser-based auth prompt, no binary reinstall.
- **Post the comment before the Status write.** If exactly one of the two survives, a
  narrative without a column move is far more useful than a moved column with no explanation.

The miss-log lives at `[sdlc-root]/.local/github-checkpoint-misses.jsonl` — JSONL, one
object per line, machine-local and **gitignored**. It is a *fast path* for reconciliation,
never a gate: reconciliation reads it to prioritize where to look, then runs its full live
comparison regardless, and produces **identical findings** when the file is missing, empty,
stale, or wrong. Any design where the log's contents change what reconciliation concludes
has inverted the relationship and is a defect.

---

## Checkpoint Map

Checkpoints marked **⎘** commit and push their artifact **before** commenting, then link a
SHA-pinned blob URL rather than a workspace path. Every other checkpoint links things already
on GitHub (commits, pull requests) or links nothing, and pays no git cost at all.

A blank Status target (`—`) means **comment-only**: the card does not move. In issues-only
mode (`board.default: none`), every Status target is treated as `—`.

| ID | Trigger | Status → (role) | Comment content |
|----|---------|-----------------|-----------------|
| **CP-1 ⎘** | `sdlc-plan` / `sdlc-lite-plan` — D-number registered in the catalog | `registered` | Create-or-link the issue. Body carries the problem in plain language, the tier, the driving repo, a link to the idea brief if one exists, and a link to the catalog row. |
| **CP-2 ⎘** | `sdlc-plan` — spec approved by CD | `spec-approved` | What is being built and why; what is explicitly out of scope; link to the spec as approved at this checkpoint. |
| **CP-3 ⎘** | `sdlc-plan` / `sdlc-lite-plan` — plan approved after agent review | — | The approach, the phase list, the key risks and trade-offs review surfaced, and whether the external-review gate participated. Link the plan (and the plan-review findings doc when one exists). |
| **CP-4** | `sdlc-execute` / `sdlc-lite-execute` — execution begins | `executing` | What is starting, in what order, which agents are dispatched. |
| **CP-5** | a phase completes | — | What that phase produced, in plain language. **Required** when the deliverable has three or more phases; optional below that. |
| **CP-6** | `sdlc-execute` — internal review-fix loop begins | — | What is under review, the reviewer roster, and external-review-gate participation when it runs. **No Status write** — the card stays at `executing`. Internal agent review is the SDLC doing its own work, not waiting on anyone. |
| **CP-S1** | *(conditional, any stage)* — the deliverable is blocked on a decision owed by a configured stakeholder role, because CD did not resolve it or explicitly deferred it | `stakeholder-blocked` | Names **what is awaited and from whom**, what the options are, and what stays blocked until it lands. |
| **CP-S2** | *(conditional)* — the stakeholder answers and work resumes | `executing` | The decision that was made, by whom, and what resumes. **The one backward write in the system**, guarded by an exact-match precondition (§ The Floor Rule). |
| **CP-7** | review loop exited (no critical/major open), work committed | — | What shipped, commit SHAs and pull-request links, any deviation from the plan and why. |
| **CP-8 ⎘** | result doc written, catalog moves to Validated | `validated` | Outcome, verification evidence, deviations, known follow-ups. The column reads as "validated and queued for deploy." |
| **CP-9** | the **staging** (pre-production) deploy lands | `staged` | What is now testable, what reviewers should look at, what end users will notice if it goes further. **SDLC board tracking ends here.** Projects with no staging stage leave `staged: null` and CP-9 never fires live (see `sdlc-archive`'s archive-time checklist for the simulated variant). |
| **CP-10 ⎘** | `sdlc-archive` — deliverable chronicled | — | Final summary. Commits the archive move, then links the **final chronicle locations as main-branch URLs** — the one checkpoint that does not pin. **Closes the issue as completed** (last, after any archive-time checklist verification that needs the thread open). |
| **CP-11 ⎘** | `sdlc-handoff` — an existing deliverable's session is parked (an issue already exists) | — | Why the session stopped, where the handoff doc is, what remains. No Status write, no new issue. |
| **CP-11b ⎘** | `sdlc-handoff` — work is parked and **no** issue exists | `registered` *(on accept only)* | **Offers** issue creation via `AskUserQuestion`. On accept: creates `Parked: <short description>`, labelled with the universal label, adds it to the board at `registered`, body carrying what was found or attempted, the handoff doc link, and what remains; writes the issue number back into the handoff doc's `github_issue:` frontmatter. On decline: nothing happens, and nothing is recorded as a miss — a declined offer is a decision, not a failure. |
| **CP-12 ⎘** | `sdlc-archive` reconciliation — retroactive D-number assigned to direct-dispatch work | `staged` (terminal only) | One consolidated comment: what the work was, which commits carried it, what it changed. Checkpoint history is **never** replayed or fabricated. Close if the work is complete. |
| *(no checkpoint)* | production deploy pipeline / human | — | NEVER-WRITE: the columns listed under `never_write` belong to whoever runs the production deploy pipeline; no checkpoint in this map may target them. |

**On the `CP-S1` / `CP-S2` naming.** The stakeholder-wait pair is deliberately not numbered
`CP-6b`. It is not a sub-step of CP-6 and holds no fixed position in the sequence — a design
decision can block at CP-2 just as easily as a product decision can block mid-execution.
`CP-S` reads as "the stakeholder pair, position-independent." `CP-11b`, by contrast, *is*
correctly a letter suffix: it fires at exactly the same point as CP-11, inside
`sdlc-handoff`, and is simply the other branch of the same decision — an issue exists, or it
does not.

**On the `stakeholder-blocked` column.** It means **awaiting stakeholder feedback** —
someone outside the session owes us a decision. It does **not** mean "under internal
review." CP-6 exists precisely to make that distinction visible: the internal agent
review-fix loop leaves the card at `executing`. If a card sits at `stakeholder-blocked` and
nobody outside the session owes a decision, the column has been misused and its signal is
dead.

---

## Board Status: Roles, Names, and Ordinal Ranks

Status is written by **column name** (looked up from the config block's role mapping),
resolved to whatever the target board calls that option at the moment of the write. **Ranks
are the join key for the floor rule — never option IDs.** The shipped default mapping (in
the config template above) is the set proven in production by the originating project; remap
names freely, keep the rank ordering's meaning.

### The Never-Write Columns

NEVER-WRITE: this document names the `never_write` column list (defaults: `Ready for Production Deploy` and `Deployed`) only to state
that no checkpoint, recipe, or skill may ever target them as a Status write. This is an
ownership boundary, not a preference — the SDLC does not run the production deploy pipeline
and does not get to narrate it. SDLC board tracking ends at the `staged` role's column. The
catalog still tracks production status
(NEVER-WRITE: the catalog statuses `Deployed`, `Complete`, `Archived` exist — tagged only because one shares a column's name); the
board does not receive it from the SDLC — those catalog statuses get **no board write at
all**, and the issue is simply closed at CP-10.

This prohibition is mechanically checkable. Every legitimate mention of a `never_write`
column name in this document, in `sdlc-manage-github`, and in the checkpoint fragments sits
on a line containing the literal token `NEVER-WRITE:`. A grep that finds a configured
never-write column name on a line without that token has found a defect.

**`NEVER-WRITE:` is a mechanical line-tag, not a prohibition statement in itself.** Its only
job is to keep that grep free of false positives, so it marks *any* line naming a
never-write column for *any* reason — including lines that merely mention one in passing,
and mentions of a **catalog status** that happens to share a column's name (a different
thing entirely, which gets no board write at all). One token per line is sufficient and
correct, because the grep is line-based. Read what the line actually says rather than
inferring a prohibition from the presence of the tag.

The enforcement is not policy-only: `resolve-and-write-status` itself refuses to write any
configured `never_write` column before the floor-rule comparison ever runs, regardless of
which checkpoint or caller invoked it — so a regression that tried to write one would have
to remove that guard from the recipe itself, not merely mis-route a checkpoint.

**Policy context, informational.** A card manually moved by a human into a never-write
column may trigger board-native automation (e.g. GitHub's own "Auto-close issue" Projects v2
workflow) that closes the underlying issue as a side effect — independent of anything the
SDLC does, since the SDLC never originates a transition into those columns. If a close
appears to have already happened when CP-10 goes to act, treat it as expected, not a failure.

### Why Names, Not IDs

Field and option IDs are **per-project**. Two boards with identically-named columns have
entirely different IDs, and — worse — the same ID string can carry different meanings on
different boards. GitHub validates only that an option ID belongs to the field being
written, **not** that the caller resolved it against this board: a stale or cross-board ID
can land a card in an arbitrary column, silently, exit 0. This was verified live by the
originating project, not inferred from documentation. The discipline that makes writes safe:

1. Map the checkpoint's Status target role to a column **name** (config block).
2. Resolve that name to an option ID **on the target board, in the current session**.
3. If the target board has no column with that name, **fail through** (§ Failure Classes).
   Never closest-match, never substitute a similar column, never fall back to a default.

Resolved IDs may be cached in process memory keyed by project number for the life of a
session. They are **never written to disk and never reused across sessions or boards**.

---

## The Floor Rule

**Before any transition to target Status `T`, read the item's current Status `C`. Write only
if `rank(T) > rank(C)`. Otherwise skip the write; still post the comment.**

That is the whole rule. It exists because the board has two writers — the SDLC and the humans
who run deploys — and the mitigation for two writers on one field is a read-before-write
ordinal comparison, not a locking scheme. The SDLC never moves a card backward and never
"corrects" a human's manual move. An SDLC that overrides a human's board move will be turned
off within a week.

### The CP-S2 Exception — the only backward transition in the system

**CP-S2 may write `stakeholder-blocked` (4) → `executing` (3), backward, but only via an
exact-match precondition: the write fires if and only if the item's current Status is
*exactly* the `stakeholder-blocked` column.** If a human has moved the card anywhere else,
CP-S2 writes nothing and posts its comment.

This is the SDLC unwinding **its own** write of a column it exclusively owns (CP-S1 is the
only writer of `stakeholder-blocked`) — not overwriting a human's move, which is what the
floor rule exists to prevent. Without it, a card would sit at "awaiting feedback" for the
entire remaining execution until CP-8 advanced it, showing a stale block while three phases
ship.

**No other backward transition is permitted anywhere in the system.** Any proposal for a
second one is a change to this document first, not an implementation detail.

### Worked Examples (default column names)

- A stakeholder block at CP-S1 left the card at `Review Pending` (4) and CP-S2 never ran.
  CP-8 fires targeting `Ready for Staging Deploy` (5). `5 > 4` → **write executes.** A stale
  block clears itself at the next forward checkpoint.
- CP-S2 fires targeting `In progress` (3) from `Review Pending` (4). Backward, so the floor
  rule alone would refuse — it executes only under the exception, and only because the
  current Status matches the `stakeholder-blocked` column exactly.
- The same CP-S2 fires when a human has already advanced the card to rank 5. The exact-match
  guard fails → **CP-S2 writes nothing**, and comments anyway.
- NEVER-WRITE: a human moved the card to `Ready for Production Deploy` (7) or `Deployed` (8)
  because staging and production went through back to back. CP-9 then fires targeting
  `Acceptance Testing` (6). `6 ≤ 7` and `6 ≤ 8` → **Status write skipped, comment still
  posted.** Nothing moves backward.

---

## Catalog Wins

Board Status is a **projection** of the catalog, and `docs/_index.md` is the single source of
truth. Where the two disagree, **the catalog wins and the board is the thing that gets
corrected** — forward only, under the floor rule, with the CP-S2 exception as the sole
backward move.

GitHub never writes back into the catalog. Drift is *detected* and reported by
reconciliation; a human decides what to do about it. The issue must not become a second
source of truth that can drift.

**Reconciliation cutoff.** The convention applies to deliverables registered **after**
enablement. The cutoff D-number lives in the config block. Catalog rows with an ID below the
cutoff are pre-convention and out of reconciliation scope entirely; rows at or above it are
in scope **regardless of cell format**, so a deliverable whose CP-1 failed (leaving a
plain-text ID cell) is still detected as missing an issue. Set once; never moved.

---

## Never Reopen

**A closed issue is a closed chapter.**

Once CP-10 closes a deliverable's issue, that thread is the historical record of that
deliverable and is never reopened — not for a follow-up, not for a regression, not for
"one more small thing."

Genuinely new work earns a **new D-number and a new issue**, related to the old one in
whichever way fits: a **linked issue** that cross-references the closed one inline, when the
new work is a peer or a follow-on; or a **GitHub sub-issue under the same parent**, when the
new work is a sub-deliverable of the same family.

This matches the standing rule that sub-deliverables never share a thread. A reopened issue
would have two lifecycles, two sets of checkpoints, and two catalog rows claiming it — which
is exactly the drift the catalog-wins rule exists to prevent.

### Follow-Up Issues Always Start at `registered` — Never Inherit the Parent's Column

A follow-up issue's Status is **never** copied from the card it is linked under, sub-issue or
not. It is unstarted work, so it starts at the `registered` column (rank 1), exactly like any
other new issue created via `create-or-link` — full stop, regardless of what column the
parent deliverable currently occupies.

This needs stating explicitly because it has already been gotten wrong once, in the
originating project: a reconciliation session sweeping a batch of result docs' "Follow-Up
Items" checklists into real GitHub issues hand-rolled the `gh` calls instead of calling
`create-or-link`, and in the improvised Status-write step set every new follow-up issue to
whatever column its parent occupied at that moment — in that case the `staged` column,
because the parent had already reached staging. The result: 17 issues describing work that
had never been started — several explicitly marked "decision needed" or "deferred" in their
own body text — sitting in a column that is supposed to mean "testable right now." Nobody
could tell, from the board alone, that these were unstarted backlog items rather than shipped
work awaiting a tester.

The fix is procedural, not just corrective: **any session creating a follow-up issue —
whether by hand, by script, or by re-deriving one from a result doc's checklist — must call
`create-or-link` (or otherwise land the new item at `registered`) exactly as it would for a
brand-new deliverable's CP-1.** A sub-issue relationship (via `link-sub-issue`) records
lineage, not status inheritance. If a session is tempted to write a different Status at
creation time because "the parent is already further along," that impulse is the bug this
section exists to catch.

---

## Repo Selection

Every deliverable files its issue in exactly one **driving repo**. Apply these rules in order
and stop at the first that resolves:

1. **One repo in `repos.driving` → that is the driving repo.** Most projects stop here.
2. **Multi-repo: the repo holding the majority of changed files**, taken from the spec's
   Components Affected section or the plan's file scope. A repo that receives the SDLC's own
   process/docs commits drives process deliverables — that is this rule applied to the repo
   that receives the work.
3. **Tie-break by where the change's outward-facing surface lives** — the repo whose users
   would notice.
4. **Still ambiguous → `AskUserQuestion` at registration. Never guess.**

**Cross-repo work files ONE issue, in the driving repo.** Issues living in other repos are
cross-referenced inline in the comments (`other-repo#21`) and recorded in the artifact's
`related_issues:` frontmatter — never duplicated into a second deliverable thread. A second
issue is created only if scope genuinely grows to need independent tracking, and the plan
for that deliverable must say so explicitly.

---

## Board Selection

The default board is `board.default` in the config block (or `none` — issues-only mode).

Board choice is a per-deliverable input captured at CP-1. When a deliverable lives on any
board other than the default, that is recorded in the artifact's `github_board:` frontmatter
and honored by every subsequent checkpoint for that deliverable.

Field and option IDs are **per-project** and must be resolved **by name on the target board,
every session**. A board whose columns do not match the configured role names is
**unconfigured** for SDLC tracking: deliverables pointed at it get their comments, and their
Status writes fail through. That is correct behavior, and it is a silent degradation worth
knowing about before pointing a deliverable at a new board.

---

## Labels

**The config block owns the complete allowed label set for all driving repos — universal +
conditional + human. A label not listed there is definitionally sprawl.** Projects may also
prune GitHub's nine default labels (`bug`, `enhancement`, `duplicate`, …) at enablement when
they have no consumer — a CD decision, recorded when made.

The universal label (default `sdlc`) plus the project's conditional labels exist in all
driving repos — § Enablement provisions them. The automation labels are applied on
**`create-or-link`'s own create call**, never as a follow-up edit — that is what keeps
registration inside its call budget, and it is why repo labels were chosen over a board field
(labels travel with the issue across boards; a board field would need a fetch/edit pair per
board). There is no separate label recipe. Labels in `labels.human` are applied by humans
only — never by a checkpoint.

**Which label applies when — this classification is owned by the config block's
`labels.conditional` conditions, not by the calling skills.** The universal label is applied
**always**: it marks the issue as an SDLC-tracked deliverable with a full artifact trail,
distinguishing it from ad hoc issues. Conditional labels are independent of one another —
apply every one whose condition holds.

**A label never blocks issue creation — and the REST create call cannot fail on one: it
silently auto-creates any label that does not exist in the repo** (verified live by the
originating project). The hazard is therefore not a blocked create but **silent sprawl**: the
recipe may only ever pass labels from the config block, spelled exactly, because a typo
becomes a new repo label nobody decided to create. The audit's taxonomy parity check
(`sdlc-compliance-auditor` § 10h) is the designated detector — extra labels are drift, not
just missing ones. A new label is a CD decision recorded in the config block, not an agent's
judgment in the moment.

**Labels another bundle owns are outside that set.** A project that runs the software factory (`.github/factory/factory.json`) also has the factory's `factory:*` labels. The factory's App and CD apply them, under the factory's rules (`[sdlc-root]/process/factory.md` § Labels), never a checkpoint. So the config block doesn't list them, which would make it a second copy of the factory's list. The audit checks them against the factory's table instead (`sdlc-compliance-auditor` § 10h), and the factory's own `bootstrap.py` reports one it doesn't define.

**Close reasons, not labels.** "This is a duplicate," "this won't be done," and "this isn't
valid" are expressed with GitHub's native close reasons (close as *duplicate* / *not
planned*, with a one-line comment when the reason needs a word of explanation) — never with
labels.

---

## Issue Types

Applies when `issue_types` is not `none` (GitHub issue types are an org-level feature). With
the `default` set, every issue carries one of three types — the classification is owned here,
not by the calling skills:

| Type | Applied when |
|---|---|
| `Bug` | The work fixes wrong behavior — a defect, a regression, a correctness gap. |
| `Feature` | The work adds a new capability — user-visible or a genuinely new subsystem. |
| `Task` | Everything else — process, infra, refactors, content, docs, measurements, decisions. The default. |

**Precedence:** when a deliverable both fixes a defect and adds capability, `Bug` wins. CD
may override any assignment; the override stands.

**Where types are set.** `create-or-link` sets the type **on the same create call as the
labels** (`mode: parked` is always `Task`), and on the promotion path when it retitles an
existing parked issue — the retitle edit carries the type, correcting the parked placeholder.
The one intake path that deliberately leaves type untouched is the link-to-existing-issue
path — an already-typed issue keeps whatever it has. Type-setting never blocks creation: per
GitHub's REST docs, a caller without push access has its `type` silently dropped on a 200
response, so no failure surfaces to the miss-log — the audit's untyped-issue check
(`sdlc-compliance-auditor` § 10h) is the detector. Manually created issues should pick a type
at creation.

Do not add a type without a CD decision — types are org-wide, so their blast radius is every
repo at once.

---

## Board Fields: Ownership

**The status field is the only board field the SDLC ever writes.** The fields listed in
`board.human_fields` — and any other field on the board — are human-owned: no checkpoint,
recipe, or skill may write them, the same ownership boundary as the never-write columns.

The originating project's worked example: a `Test Verdict` single-select
(`Approved` / `Needs work` / `Not applicable`) for cards sitting in the `staged` column —
one verdict at a time, each with a short comment saying what was tested; a new staging deploy
resets it; it is cleared when the card leaves the column; `Needs work` never moves the card
by itself (humans may move cards backward; only the SDLC is forbidden). Plus
`Validity`/`Correctness`/`Effort` projecting the estimation model's three dimensions, and an
optional `Priority` for backlog ordering. There is deliberately **no** `Estimate`, `Size`, or
`Iteration` field — a numeric estimate field invites cardinal-time estimation, which the
estimation model forbids.

**Assignees convention.** The issue's assignee is **the human who owes the next action**.
During agent-driven development nobody is assigned; when a card reaches the `staged` column,
CD assigns the tester (so they get a native GitHub notification and an `assignee:@me`
queue). **Checkpoints never write assignees.**

---

## Pre-Deliverable Issue Lifecycle

Work can enter GitHub **before** it has a D-number. That means the `Dnn` join key cannot
exist at creation time, and the lifecycle closes that gap without ever producing two issues
for one body of work.

```
CP-11b   sdlc-handoff parks work; CD accepts the offer
         → "Parked: <short description>"     board: registered, universal label
         → handoff doc frontmatter gains  github_issue: repo#N
                                │
                 (work sits parked — visible to the team)
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
        crystallized                          abandoned
              │                                   │
CP-1   create-or-link reads the handoff      sdlc-archive closes the issue
       doc's github_issue:, LINKS that       as "not planned" with a comment
       issue (never creates a second),       saying the work was never
       and RETITLES it                       crystallized
       → "Dnn — <Deliverable Name>"
       → board: registered (unchanged, rank 1)
       → the Dnn join key now exists
```

Three properties make this work:

- **Pre-deliverable issues carry no `Dnn` prefix, and that absence is the signal.** Parked
  work has no catalog row to join against, so it is deliberately outside reconciliation's
  join until crystallized. Reconciliation keys on the *presence or absence* of a `Dnn`
  prefix, never on the specific wording that precedes it — so hand-created `Idea: …` issues
  are correctly classified with no renaming pass.
- **Promotion is a link, not a second create.** The retitle at CP-1 is the moment the issue
  joins the catalog. Everything downstream then behaves exactly as if the issue had been
  created at CP-1 in the first place.
- **Parked issues get a closure path.** Without it, the `registered` column slowly fills
  with parked items nobody will ever pick up and the column stops meaning anything.

---

## Artifact Links: SHA-Pinned, With One Exception

**Every artifact link a checkpoint posts is a SHA-pinned blob URL:**

```
https://<host>/<owner>/<repo>/blob/<sha>/<path>
```

**A workspace path is not a link.** `docs/current_work/specs/d12_..._spec.md` is a dead
reference to anyone reading the issue on GitHub — and specs and plans routinely sit
uncommitted for long stretches, so a checkpoint that links one without committing it
publishes a broken reference by default. That is why the ⎘ checkpoints commit and push
**before** they comment.

Two reasons pinning wins over a main-branch URL:

| Shape | Behavior |
|---|---|
| `blob/main/docs/current_work/specs/…` | Always shows the current version — **and 404s the moment `sdlc-archive` moves the file to `chronicle/`.** |
| `blob/<sha>/docs/current_work/specs/…` | Resolves forever. Shows the file exactly as it stood at that checkpoint. |

The first reason is survival: CP-10 *moves* every artifact from `current_work/` to
`chronicle/`, so a main-branch scheme breaks every link posted earlier in the thread
precisely when the thread stops being a live feed and becomes the historical record people
actually read.

The second reason is semantics, and it matters more. **A comment is an immutable statement
about a moment.** CP-2 says "the spec was approved"; it should link the spec *as approved*,
not as amended three revisions later. Comments linking pinned artifacts say so in one clause
("the spec as approved at this checkpoint") so a reader knows they are looking at a snapshot.

**The one exception: CP-10's closing comment uses main-branch links to the final chronicle
locations.** That is the "where does this live now" pointer. Between the pinned history and
the main-branch closing links, a reader gets both the frozen record and the current home. The
catalog's linked ID cell and the artifact's `github_issue:` frontmatter remain the live
pointers in the other direction.

---

## Commit Conventions

The ⎘ checkpoints write to shared git history in a workspace where another session may push
at any moment. Three rules are absolute.

**1. Stage by explicit path, and commit with a matching pathspec.** The commit is limited to
the same paths that were staged — belt-and-braces, because a pathspec-limited commit cannot
pick up whatever a concurrent session happened to stage in between. **Bulk staging is
forbidden**: not `-A`, not `.`, not `-u`. A checkpoint must never sweep another session's
in-flight work into its commit.

A checkpoint stages **the artifact file(s) it produced**, plus `docs/_index.md` only when the
checkpoint itself changed the catalog row. A pathspec does not isolate concurrent edits
*within* a shared file, so before committing the catalog the checkpoint verifies that the
only delta against HEAD is the intended row. If other deltas are present it commits the
artifact alone, skips the catalog, logs a miss, and surfaces a one-line notice.

**2. Never force-push, in any form.** Not `--force`, not `--force-with-lease`. Under
concurrent sessions both can discard another session's commits, and no provenance link is
worth that. A push that one rebase cannot resolve fails through with a degraded link; it
never escalates.

**3. Conventional Commits, with the deliverable tag.** Messages follow the project's standard
format with the `[D<N>]` tag attached to the type:

```
docs[D12]: spec
docs[D12]: plan
docs[D12]: result doc
docs[D12]: archive to chronicle
```

**Pre-deliverable handoff commits (CP-11b) carry no `[D<N>]` tag**, because no D-number
exists yet: `docs: park <slug> handoff`.

**Idempotence.** If the artifact has no unstaged changes, the commit is **skipped** and the
checkpoint resolves HEAD's existing SHA instead. Re-running a checkpoint must never produce
an empty commit and must never fail because there was nothing to commit.

**Interaction with the Commit Completeness Rule.** This moves artifact commits *earlier* — to
checkpoint time, rather than deferred to the execution commit. That is a strengthening, not a
conflict. The execution commit at CP-7 will find the spec and the plan already committed;
that is correct and must not be read as a completeness violation. The rule requires that no
artifact goes *uncommitted*, not that every artifact lands in one commit.

---

## Call Budgets

A checkpoint's cost is bounded on **two separate axes**, because a network API call and a
local git command cost very different things:

| | Happy path | Worst case |
|---|---|---|
| `gh` API calls | **≤ 4** (including the floor-rule Status read) | **≤ 6** |
| git operations | **≤ 4** (`add`, `commit`, `push`, `rev-parse`) — **only on the ⎘ checkpoints**; zero elsewhere | **≤ 6** (adds `pull --rebase` plus one retry push) |

The worst case sits at +2 rather than unbounded because of the hard cap in § Failure
Classes — at most one remediation attempt plus one retry, once per checkpoint, however many
operations fail. The majority of checkpoints (CP-4 through CP-7, CP-9, CP-S1, CP-S2) pay
**no** git cost at all: they link commits and pull requests that are already pushed, or link
nothing.

### The Two Documented Exemptions

The ≤4 caps defend against **accumulation** — many checkpoints across a multi-phase
deliverable, each paying a toll. A checkpoint that fires **exactly once** per deliverable
does not accumulate, and that is the entire basis of both exemptions. Each is exempt on
**one axis only**; the other axis stays at ≤4 / ≤6.

| Checkpoint | Exempt axis | Budget | Why it does not accumulate |
|---|---|---|---|
| **CP-1** — deliverable registration | `gh` API calls | **≤ 8 happy path, ≤ 10 worst case** | Fires exactly once per deliverable. Covers create-with-labels, the idempotent board add, the sub-issue link, and the frontmatter and catalog writes. Three collapses keep it near the floor: labels ride on the create call; the sub-issue link fires **only** for sub-deliverables; and the floor read is **skipped on a freshly created item**, whose Status is known-empty. |
| **CP-11b** — parked work, on accept | git operations | **≤ 8 happy path, ≤ 10 worst case** | Fires exactly once for a given body of parked work, and needs **two** `commit-and-push-artifact` cycles for an ordering constraint that cannot be collapsed: the issue body links the handoff doc SHA-pinned, so the doc must be pushed *before* the issue is created — and the `github_issue:` frontmatter cannot be written until the issue number comes back from that create. |

**No other checkpoint may claim either exemption.** A third one is a change to this document
first, not an implementation detail.

---

## Terminology

Issue titles, bodies, and comments are human-facing and visible to every collaborator, so
any word-choice directives the project's leadership has issued apply to all of them without
exception. The config block's `terminology` list is where those directives live — the
classification is owned here, not re-derived by calling skills.

**Technical identifiers are the one carve-out, and they must be backticked.** When a comment
needs to quote an identifier that collides with a directive (a `user_id` column, a `users`
table), it appears **inside backticks** so it reads as a quoted identifier rather than as
prose. An unbackticked occurrence is a violation regardless of intent; the check is
mechanical, run after stripping backticked spans.

This rule is stated here **and** in `sdlc-manage-github` so the two documents cannot drift
apart on it.

---

## Content Prohibitions

Issues are visible to every collaborator on the repo — and on public repos, to everyone.
**A checkpoint comment must never contain:**

- **personal data about the product's users** — names, email addresses, phone numbers,
  precise locations, account identifiers tied to a real person, or anything derived from an
  individual's behavior or profile;
- **credentials, tokens, API keys, or connection strings** — in any form, including inside a
  quoted error message or a pasted log line;
- **pasted artifact bodies** — link the artifact instead (§ Artifact Links);
- **anything in the config block's `sensitive_data` list** — the project's own categories,
  on top of the universal three above.

This is an active hazard, not a theoretical one: result docs and prototypes routinely carry
real data extracts, and a careless comment could quote one into a visible thread. When a
checkpoint needs to describe data, it describes the **shape** of the data, not an instance
of it. When in doubt, link the artifact and say nothing more.

---

## Comment Templates

Every checkpoint posts a comment. **Comment count is uncapped** — this is a narrative log,
not a status ticker. **Individual comment length is bounded**: a few short paragraphs. If a
checkpoint's comment is growing past that, the excess belongs in the artifact it links.

**Accepted trade-off:** re-running a checkpoint (after a crash or a resumed session) may
post a duplicate comment. That is tolerated — deduplicating would spend API calls on every
run to prevent a rare cosmetic artifact a human can delete. Commits are idempotent; comments
are append-only narrative.

Two quality bars apply to every template below:

- **Plain language a non-technical reader can follow** — the audience includes people who
  will never read the code.
- **Substantive, not a summary of a summary.** Each comment answers *what is happening* and
  *why*. **A comment a reader could have written from the issue title alone is a failed
  comment.**

The templates are shapes, not scripts. Fill them with the actual specifics; do not post the
scaffolding.

**Completion lives in comments, not the body.** The issue body is written once, near the top
of a deliverable's life, and is frequently never touched again; CP-9 through CP-12 all post
their outcome as a *comment*. A backfilled deliverable (CP-12) in particular almost always
has a body that still reads as a pre-implementation ask. **Fetching only the body is not a
completion check** — any check of whether a deliverable is done, live, or still blocked must
pull the comments too and read to the end of the thread. The originating project verified
this the hard way: three separate deliverables were misread as unresolved purely because
their "Outcome: Complete" note was three-plus comments deep under a body that still described
the original, superseded ask.

### CP-1 — issue body at registration

> **What this is.** `<one or two plain-language sentences: the problem, stated as a problem
> someone actually has — not as a task>`
>
> **Why now.** `<what makes this worth doing at this point>`
>
> **How it will be tracked.** `<tier: full SDLC or SDLC-Lite>`, driving repo
> `<repo>`. Progress is narrated in this thread at each stage.
>
> **Background:** `<link to the idea brief or handoff doc, if one exists>`
> **Catalog row:** `<link to docs/_index.md>`

### CP-2 — spec approved

> **The spec is approved.** `<what is being built, in two or three sentences a non-engineer
> can follow>`
>
> **Explicitly out of scope:** `<the two or three things people would otherwise assume are
> included>`
>
> **Spec, as approved at this checkpoint:** `<SHA-pinned link>`

### CP-3 — plan approved

> **The plan is approved and reviewed.** The approach: `<one paragraph — what we chose and
> what we chose against>`
>
> **Phases:** `<short list, one line each>`
>
> **What review surfaced:** `<the key risks and trade-offs, and how the plan handles them>`
> `<state whether the external review gate participated>`
>
> **Plan:** `<SHA-pinned link>` `<plan-review findings doc link, when one exists>`

### CP-4 — execution begins

> **Execution has started.** `<what is being built first and why that order>`
>
> `<which specialist agents are doing which phases>`

### CP-5 — phase complete

> **Phase `<n>` is done: `<phase name>`.** `<what it produced, in plain language — what is
> now possible that was not before>`
>
> `<anything that changed relative to the plan, and why>`

### CP-6 — internal review begins

> **The work is now under internal review.** `<what is being reviewed>`
>
> **Reviewers:** `<roster>` `<and whether the external review gate is running>`
>
> This is the SDLC checking its own work — nothing is blocked and nobody is waiting on a
> decision.

### CP-S1 — blocked on a stakeholder

> **Waiting on a decision.** We need `<what>` from `<who — the configured stakeholder role
> that owns this kind of decision>`.
>
> **The options as we see them:** `<the real choices, stated so a non-engineer can pick>`
>
> **Blocked until it lands:** `<what cannot proceed>`. `<what continues in the meantime, if
> anything>`

### CP-S2 — stakeholder answered

> **Decision made.** `<who>` chose `<what>`. `<one line on the reasoning, if it was given>`
>
> **Resuming:** `<what starts moving again>`

### CP-7 — work committed

> **The work is committed.** `<what shipped, in plain language>`
>
> **Commits:** `<SHA links>` `<pull-request links, if any>`
>
> **Deviations from the plan:** `<what changed and why — or "none">`

### CP-8 — result doc written

> **Validated.** `<the outcome — what now works>`
>
> **How we know:** `<the verification evidence, concretely>`
>
> **Known follow-ups:** `<what was deliberately left, and where it is tracked>`
>
> **Result doc:** `<SHA-pinned link>`
>
> This is queued for deploy.

### CP-9 — staging deploy landed

> **This is deployed to staging and ready to look at.** `<what to try, and where>`
>
> **What reviewers should focus on:** `<the specific surfaces>`
>
> **What users will notice** if it goes further: `<the visible change, or "nothing — this is
> internal">`
>
> SDLC tracking of this deliverable ends here.

### CP-10 — chronicled and closed

> **Complete.** `<a short closing summary: what was built, and what changed as a result>`
>
> **Where it lives now:** `<main-branch links to the chronicle locations of the spec, plan,
> and result doc>`
>
> Earlier links in this thread are pinned to the commits they described, so they still
> resolve. Closing this issue — any follow-on work will get its own D-number and its own
> thread.

### CP-11 — session parked, issue exists

> **Parked for now.** `<why the session stopped — finished a natural unit, ran out of scope,
> blocked on something else>`
>
> **What remains:** `<concretely, what the next session picks up>`
>
> **Handoff doc:** `<SHA-pinned link>`

### CP-11b — issue body for parked pre-deliverable work

> **Parked before it became a deliverable.** `<what was found or attempted, in plain
> language>`
>
> **Why it stopped:** `<the reason>`
>
> **What picking this up would involve:** `<enough that a teammate reading only this issue
> understands the shape of the work>`
>
> **Handoff doc:** `<SHA-pinned link>`
>
> This has no D-number yet. If it is crystallized into a deliverable, this same issue is
> retitled rather than replaced.

### CP-12 — retroactive, at reconciliation

> **Recorded retroactively.** This work was done by direct dispatch and earned a D-number
> during reconciliation, so it has one consolidated entry rather than a checkpoint history.
>
> **What it was:** `<plain language>`
> **What changed:** `<the surfaces affected>`
> **Commits:** `<SHA links>`
>
> `<result doc link, when one exists>`

---

## Failure Classes

A failed operation gets **one** shot at cheap self-healing, then fails through. The classes
below are policy; the actions that implement them — and the exact commands — live in
`sdlc-manage-github`.

| Failure class | Remediation rationale |
|---|---|
| **Stale cached field/option ID** (the write is rejected as unresolvable) | Highest-value rung. The session-scoped ID cache is the most likely thing to go stale, and re-fetching the board's fields is exactly the "never fabricate, always fetch" fix. One re-fetch, one retry. |
| **Transient network / API 5xx / timeout** | Single flaky calls are common; a second failure means something real. One immediate retry, no meaningful pause. |
| **404 / wrong repo** | Cheap to re-resolve from the repo's own remote, and it catches the most common misconfiguration. One re-resolve, one retry. |
| **Auth failure** (unauthenticated, no token) | Nothing safe can fix this in-session. Confirm the diagnosis once, then fail through. |
| **Push rejected, non-fast-forward** | A concurrent session pushed first — expected steady state, not an anomaly. One rebase-on-pull, one retry push. The SHA is **re-captured after the rebase** — the pre-rebase SHA is not the pushed SHA. |
| **Rebase hits a conflict** | Abort and fail through. A checkpoint auto-resolving another session's conflict is exactly the failure the commit conventions exist to prevent. Never resolve, never force. |
| **Rate limit** | **No remediation** — fail through immediately. Reset windows can be an hour; waiting is indistinguishable from blocking. |
| **Target board has no column with the required name** | **No remediation** — fail through. Never closest-match. A column named `Done` on some other board is not the `staged` column. |
| **Anything else** | **No remediation** — fail through. Unknown failures do not get speculative fixes. |

**Hard cap: at most one remediation attempt per checkpoint, ever.** If a second operation in
the same checkpoint also fails, it fails through immediately with no remediation. Implement
this as a failure-class → single-action lookup, never as a loop with a counter — a counter
invites someone to raise the bound later.

**Explicitly excluded, and why:**

- **Force-push in any form is forbidden outright** — not `--force`, not `--force-with-lease`.
  Under concurrent sessions both can discard another session's commits.
- **No interactive auth.** Neither a login nor a token-refresh flow may be invoked; both can
  block indefinitely on a browser prompt, which is the exact failure the never-block
  invariant exists to prevent.
- **No reinstalling or upgrading the CLI binary.** It mutates the developer's machine
  mid-checkpoint, takes minutes, and needs network access that a failing call already
  suggests is unavailable.
- **No rate-limit sleep. No exponential backoff. No retry loops of any kind.**

**Failure detection is mechanical, not linguistic.** Classify on exit codes and HTTP status.
Never match on stderr prose — it changes between tool releases and a broken classifier fails
silently.

### Fail-Through Behavior

A failure that survives remediation does three things and no more:

1. **Surfaces a one-line notice** in session output — what failed, which checkpoint, which
   deliverable.
2. **Appends one entry to the miss-log** (`[sdlc-root]/.local/github-checkpoint-misses.jsonl`)
   — a single atomic append of one JSONL line, recording timestamp, deliverable, checkpoint,
   operation, target, and the error. Never a read-modify-write, which loses entries under
   concurrency.
3. **Execution continues.** The SDLC step completes.

**For a failed push specifically, the comment still posts** — carrying the workspace path
plus a note that the file reaches GitHub at the next push. A comment with a degraded
reference is far better than a silent checkpoint, and the miss-log entry records which
comment needs its link upgraded. Nothing automatically edits that comment later; a human may.

A **declined CP-11b offer is not a failure** and must leave no trace anywhere: not in the
session notice, not in the miss-log, not in the drift report.

---

## No Per-Call Human Confirmation

`sdlc-manage-github` normally requires confirming a visible state change before executing it.
**SDLC checkpoints are exempt from that confirmation.** They execute without asking.

Three things make the exemption safe:

- **The target is unambiguous.** The issue is identified by its D-number, not by
  interpretation of a request.
- **The transition is determined, not chosen.** The Status target comes from the checkpoint
  map in this document, and the floor rule decides whether it is written. There is no
  judgment call at the moment of the write.
- **Enablement is the standing authorization.** CD completed § Enablement and set
  `enabled: true`; that act authorizes the entire checkpoint map.

The exemption is **scoped to SDLC checkpoints only**. It does not extend to
`sdlc-manage-github`'s own interactive use, where a human is steering and confirmation is
the whole point.

`sdlc-manage-github` carries this same exemption note, so the two documents cannot
contradict each other. Two exceptions to the "no asking" posture survive by design and are
part of the map, not violations of it: **CP-11b offers** issue creation rather than assuming
it, and **repo selection rule 4** asks rather than guessing.

---

## Headless Runs

A run with no person present (`[sdlc-root]/process/headless-mode.md`) **never writes to
GitHub itself.** Whatever runs skills unattended owns GitHub, often through a token the run
does not hold. Each checkpoint splits in two: the **local half**, which the run still does,
and the **GitHub half**, which it hands to the caller as a rendered entry the caller can
apply without this document or `sdlc-manage-github`'s recipes.

### The local half

When a checkpoint fires in a headless run, the run still does every part that does not write
to GitHub:

- **Issue links, when the issue is known.** The issue is known when the caller's prompt
  names it, when an earlier artifact's `github_issue:` frontmatter or the catalog's linked
  ID cell already records it, or when the originating handoff doc's `github_issue:` names a
  `Parked:` issue (the promotion path: the entry retitles that issue rather than creating
  one). CP-1 then writes the two local parts of its persistence set:
  `github_issue: <repo>#N` (and `github_board:` when it differs from the default) into the
  first artifact's frontmatter, and the catalog ID cell as a link. When no issue is known,
  repo selection rules 1–3 pick the repo for the new issue as usual. If they leave it
  ambiguous (rule 4), the entry's `issue` is `new` with no repo, its `note` lists the
  candidate repos, and the caller applies it only after CD names the repo. When no issue
  exists yet, the links wait: the caller creates the issue and passes its number to the
  next run. **Any later headless run whose prompt names the deliverable's issue writes
  missing links before its own work**, including a restarted run that skips registration
  and the first execute run of a lite deliverable.
- **Artifact commits.** The ⎘ checkpoints commit their artifact locally under § Commit
  Conventions: explicit-path staging, the `[D<N>]` tag, and idempotence. They do not push.
  The commit's SHA is what the rendered comment links.
- **Everything else is computed, not applied.** The run renders the comment, picks the
  Status target and works out the labels, then puts them in the entry.

### The GitHub half: rendered entries in `outbound`

Each checkpoint that fires adds one entry to the result's `outbound`, in firing order. So
does `sdlc-archive`'s closure of a never-crystallized `Parked:` issue, which has no CP id.

| Field | Content |
|---|---|
| `checkpoint` | The CP id, or `parked-closure` |
| `deliverable` | The D-number; omitted for `parked-closure` |
| `issue` | `<owner>/<repo>#N`, or `new <owner>/<repo>` when the caller must create it (CP-1 with no issue known; CP-12), or `new` alone when repo selection reached rule 4 |
| `title` | `Dnn — <Deliverable Name>`, for a new issue or CP-1's retitle of an existing one; otherwise omitted |
| `labels` | For a new issue only: the config block's labels that apply (the universal label plus every conditional whose condition holds), spelled exactly |
| `type` | The issue type per § Issue Types, for a new issue or CP-1's retitle; omitted when `issue_types` is `none` |
| `parent` | For a sub-deliverable (`D41a`), the parent deliverable's issue, linked as a native sub-issue after creation; otherwise omitted |
| `board` | The board's owner and project number, on every entry that adds the issue to a board or writes Status: the deliverable's `github_board:`, or the configured default. Omitted in issues-only mode |
| `board_add` | `yes` when the issue must be added to the board first (CP-1, CP-12) |
| `comment` | The whole comment, rendered from § Comment Templates with the real specifics; for a new issue, its body. Artifact links are SHA-pinned to the run's local commits, except CP-10's main-branch links |
| `status` | The target column's configured name and rank, or `—` for comment-only |
| `write_if` | The condition the caller checks at write time: `current rank < N` (§ The Floor Rule), or for CP-S2 `current column is exactly <name>` |
| `close` | `completed` (CP-10 part 2; CP-12 when the work is complete) or `not planned` (`parked-closure`); otherwise omitted. Set only when the skill's own conditions for closing hold. For CP-10, the archive-time checklist's local rows passed; its GitHub rows are earlier entries for the same issue, so the caller's skip-on-failure (step 6) covers them |
| `needs_push` | The commits the comment's links need on GitHub, and where: any branch for SHA-pinned links. For CP-10's main-branch links, what matters is the moved files reaching the default branch, by whatever merge |
| `note` | Anything the caller must know that has no field, such as "repo ambiguous under rule 4; candidates: app, api" |

Once per result, `outbound` also carries a `ranks` item: the config block's columns with
their ranks, plus every `never_write` column ranked above all of them. It travels inside
`outbound` so it is never separated from the entries that need it. An empty Status
(a card in no column) is rank 0. A column missing from the map means **skip the write**:
the caller never guesses a rank, so it can never move a card backward.

**The caller applies each entry in this order:**

1. **Push** the `needs_push` commits unchanged, never force-pushing. A `git bundle` keeps
   their SHAs; a re-applied patch does not, and its links would 404. If SHA-pinned commits
   cannot go up unchanged, still post the comment: a narrative with a degraded link beats
   none. CP-10 is different: hold the entry until its main-branch links resolve, meaning the
   moved files are on the default branch (for example, once the pull request merges, by any
   merge method), then apply it.
2. **Find or create the issue.** For `new`, first search the repo's open and closed issues
   for a title starting with `Dnn` followed by a space, em dash or colon. If one matches,
   link it instead of creating a second thread. Otherwise create it with its title, labels,
   type and `comment` as the body, in one call. Then link `parent` as a sub-issue. For a
   retitle, set the title and type together.
3. **Add it to the board** when `board_add` says so.
4. **Post the comment**, unless step 2 just created the issue with it as the body.
5. **Write Status:** read the current column, look up its rank in `ranks`, and write the
   target only if `write_if` holds.
6. **Close** last, with the reason in `close`. Skip the close if the issue is already
   closed, or if any earlier entry for the same issue failed. For CP-10, close only after
   the comment's main-branch links resolve.

Comment before Status, as everywhere in this document. Rendering an entry never stops the run.

### Other rules

- A checkpoint handed to the caller is **not a failure**. It writes no miss-log entry and no
  session notice; the `outbound` entry is its record. Reconciliation still sees the gap (the
  issue or Status lags the catalog) if the caller drops it.
- CP-11b never fires: its offer takes the no path.
- The caller's prompt may hand checkpoint writes to the run by name ("you may fire
  checkpoints"). The run then fires them under this document as usual, except at the two
  interactive points: CP-11b's offer takes the no path, and when repo selection reaches
  rule 4 the run skips that checkpoint, lists it under `outbound`, and continues. It never
  guesses a repo, and never stops the SDLC step (§ The Never-Block Invariant).

---

## Recipes `sdlc-manage-github` Must Provide

The mechanics live in `sdlc-manage-github` as named recipes. These names are the interface
between this document and that one; skills call them by name and this document refers to
them by name.

1. **`create-or-link`** — idempotent by `Dnn` title prefix: search the driving repo for an
   open or closed issue carrying the same prefix and **link** a match rather than creating a
   duplicate. Implements the promotion path — read the originating handoff doc's
   `github_issue:` frontmatter first and, when it names an issue, **link and retitle** that
   issue instead of creating a second one. Adds the issue to the board at `registered`,
   itself idempotent (skipped in issues-only mode). Labels **and the issue type**
   (§ Issue Types) ride on this recipe's underlying create call; there is no separate label
   or type recipe.
2. **`resolve-and-write-status`** — role→name→option-ID resolution on the **target** board in
   the current session, the floor-rule read-then-write, and the CP-S2 exact-match exception.
   Reads roles, names, and ranks from this document's config block; it does not carry its
   own copy. A no-op in issues-only mode.
3. **`link-sub-issue`** — parent/sub linking for sub-deliverables, via GitHub's native
   parent/sub-issue relationship. Fires only when the deliverable being registered is a
   sub-deliverable.
4. *(deliberately empty — there is no separate label recipe. Labels are applied on
   `create-or-link`'s own create call, which is what keeps registration inside its call
   budget and is the reason repo labels were chosen over a board field in the first place.)*
5. **`commit-and-push-artifact`** — pathspec-scoped commit, push, and SHA capture, per
   § Commit Conventions. SHA capture happens only after a push that succeeded, and is
   re-captured after any rebase-retry.
6. **`log-miss`** — atomic single-line append to the miss-log.

Phases and skills depend on these exact names. Renaming one is a change to this document
first.

---

## Related

- `[sdlc-root]/process/external-review-gate.md` — the precedent this document follows:
  policy in a process doc, mechanism in a separate file, never block on external
  availability.
- `.claude/skills/sdlc-manage-github/SKILL.md` — the mechanics: the recipes above, the
  failure-class→action lookup, and the same terminology and no-confirmation notes.
- `docs/_index.md` — the catalog. Canonical; the board is its projection.
- `[sdlc-root]/process/project-section-markers.md` — why the config block survives
  migration while this policy body updates.
