---
name: sdlc-manage-github
description: >
  Required procedures for inspecting and updating GitHub Projects v2 boards and repo issues
  using the `gh` CLI, plus the named SDLC checkpoint recipes that the GitHub provenance
  convention ([sdlc-root]/process/github-checkpoints.md) calls from the planning, execution,
  handoff, archive, and audit skills. Covers listing/reading Projects v2 boards and their
  items, looking up and updating repo issues, and creating new issues — all via `gh`, not
  github MCP tools, since MCP issue tools cannot browse Projects v2 boards.
  Triggers on "check the project board", "what's on the [board name] board", "look up issue #N",
  "update this issue", "move this issue to [status]", "create a github issue", "close issue #N",
  "assign this issue", "gh project", "check github issues", "what issues are open",
  "/sdlc-manage-github".
  Do NOT use for reviewing PR code changes — use sdlc-review-code.
  Do NOT use for turning an issue into a tracked deliverable — use sdlc-idea, sdlc-lite-plan,
  or sdlc-plan (this skill only performs the GitHub-side lookup/update).
  Do NOT use github MCP issue tools for board work — MCP's issue tools 404 on Projects v2
  board items and cannot enumerate a board; `gh project` commands succeed where they do not.
---

# GitHub Board & Issue Management

Procedures for checking and updating GitHub project boards and issues via the `gh` CLI, when
the github MCP tools can't reach what's needed (Projects v2 boards) or a quick CLI round-trip
is faster than an MCP call chain. Also home to the § SDLC Checkpoint Recipes that implement
the GitHub provenance convention's mechanics.

**Argument:** a natural-language ask naming a board, issue number, repo, or desired change
(e.g. "what's on the launch board", "look up issue #8", "move issue #12 to In Progress",
"create an issue for the broken reset link").

<!-- MIRROR-START: headless-mode.md#headless-stop-rule -->
**Headless runs (no person present).** This run is headless if the caller's prompt or appended system prompt has a line starting `SDLC headless mode:`, or if no ask-the-user tool (`AskUserQuestion`, or the harness's equivalent such as OpenCode's `question`) can be used — none is available or loadable, or a call to it is denied without an answer. A dispatched subagent is never headless itself; in a headless run the orchestrator tells each subagent so, and the limits below bind it too. In a headless run, every point in this skill that asks CD something the next step depends on, waits for CD's approval, or escalates to CD **stops the run there**: save the work so far, return the questions, the document or action plan awaiting approval, or the open-findings table as the run's result (in the caller's output schema if it passed one), and end the turn normally — a stop is a result, not an error. A missing precondition the caller must fix ends the run with status `failed` and the reason. Never guess an answer, take a default for a decision CD owns, approve your own work, or skip the gate. List questions the next step does not depend on in the result instead of stopping. Take the no path on optional offers. Cause no side effect outside the working tree — no push, post, comment, label, publish, external send, or live-system change — unless the caller's prompt names it; list those actions in the result. Reads are fine. A question the prompt or thread already answers is not a gate. Full rule and result format: `[sdlc-root]/process/headless-mode.md`.
<!-- MIRROR-END: headless-mode.md#headless-stop-rule -->

## Preconditions

- **Read the config block first**: `[sdlc-root]/process/github-checkpoints.md`
  § Activation and Configuration. It carries the org, host, driving repos, default board,
  column role→name→rank mapping, labels, and terminology directives. If that file is absent,
  this skill still works for interactive asks — resolve org/repo from the local git remotes —
  but the § SDLC Checkpoint Recipes must not be invoked (the convention is not installed).
- `gh` CLI is installed and authenticated (`gh auth status`). If not authenticated, stop and
  tell the user to run `gh auth login` — do not attempt to authenticate on their behalf.
- Confirm org casing with `gh project list --owner <org>` rather than assuming a form.
- Resolve which repo an issue belongs to before running repo-scoped `gh issue` commands — use
  `git -C <repo> remote -v` (or `git remote -v` in a single-repo project) to confirm the
  owner/repo pair, never guess it.

## Output

Return a plain-language answer to the ask — board status, issue detail, or confirmation that
an update ran — not a raw `gh` JSON dump. When a `--json` call was used, surface only the
fields relevant to what was asked, and quote the issue/item's title and number so the user
can immediately recognize which one you mean. For updates, state what changed (e.g. "closed
my-app#8 as completed") rather than only echoing the command's exit status.

## Steps

### 1. Scope the request

Determine what's being asked:
- **Board-level** ("what's on the board", "what's in progress") → step 2.
- **Specific issue** (a number, a title fragment) → step 3.
- **Update** (status change, field edit, comment, close/reopen) → step 4.
- **New issue** → step 5.

If the user names a board or issue ambiguously (e.g. an issue number with no repo, and more
than one repo has that number), list the candidates and ask which one they mean before
acting — do not guess. Project board item numbers and repo issue numbers are independent:
the same number frequently exists in multiple repos on the same board.

### 2. Discover and read project boards

```bash
gh project list --owner <org>
gh project item-list <project-number> --owner <org> --format json --limit 100
```

The JSON response nests issue data under `content` (title, body, number, repository, url) and
carries board-specific fields (`status`, `labels`, `assignees`) at the top level of each
item — `status` is the board's column value and is independent of the underlying issue's
open/closed state. When cross-referencing an item against its repo issue, use
`content.number` and `content.repository`, not the item's own `id`.

Do not paginate past what's needed — request the field subset the user needs when the board
is large, and say so if you're limiting results.

### 3. Look up a specific issue

Once the repo is confirmed (see Preconditions):

```bash
gh issue view <number> --repo <org>/<repo> --json title,body,state,labels,assignees,comments
```

Use `--json` with an explicit field list rather than the default human-readable output when
the result will be parsed or quoted back. If the issue can't be found by repo issue number,
it may only exist as a project board item — fall back to step 2 and filter the item list by
title or `content.number` (draft items exist only on the board).

**When the question is "is this actually done" — not just "what does this issue say" —
`comments` is not optional.** Per `[sdlc-root]/process/github-checkpoints.md` § Comment Templates,
completion/outcome is posted as a *comment* (CP-9 through CP-12), while the body is written
once early and often never updated — a backfilled deliverable's body routinely still
describes the original, since-superseded ask. Pulling the body alone and treating an
unresolved-sounding body as proof the work isn't done is the exact mistake this note exists
to prevent; always fetch and read `comments` to the end of the thread before concluding an
issue is stale, blocked, or unstarted.

**Classifying an issue (decision-needed vs. agent-ready, stakeholder-approval-needed, or any
other judgment call) requires the same full read — body AND comments, for that specific
issue — before asserting a classification.** A title, a label, or an earlier agent's summary
of a *different* question is not a substitute. Two failure modes observed in practice: (1)
treating an issue as still needing a decision when the issue body itself says the decision
was already made and only implementation remains (or vice versa); (2) missing that the
"unknown" the issue is blocked on is already answered elsewhere — check the project's
canonical domain-knowledge source and any linked spec/plan/handoff doc before concluding a
decision is genuinely outstanding. When classifying more than a handful of issues, hand the
read-heavy work to parallel general-purpose agents (one batch per repo or theme) — but each
batch's prompt must require the full body+comments read and the cross-check, not a title
skim; do this proactively, without waiting for the user to ask "did you read the
descriptions?"

### 4. Update an issue or board item

Repo-level issue fields (state, labels, assignees, comments):

```bash
gh issue edit <number> --repo <org>/<repo> --add-label "bug" --add-assignee <user>
gh issue close <number> --repo <org>/<repo> --reason completed
gh issue comment <number> --repo <org>/<repo> --body "..."
```

Board-only fields (status/column, custom Projects v2 fields):

```bash
gh project item-edit --project-id <PVT_...> --id <PVTI_...> --field-id <field-id> --single-select-option-id <option-id>
```

Board-field edits need the project's field and option IDs, not their display names — fetch
them first with `gh project field-list <project-number> --owner <org> --format json` and
match the id to the human-readable name. Never fabricate an ID.

**Before any update that changes visible state (closing an issue, moving a board column,
removing an assignee):** confirm the exact issue/repo/board item with the user if there was
any ambiguity in step 1, and state what you're about to run before running it. These changes
are visible to every collaborator watching the repo or board.

### 5. Create a new issue

```bash
gh issue create --repo <org>/<repo> --title "..." --body "..." --label "..."
```

Confirm the target repo with the user first if it wasn't explicitly named.

### 6. Hand off resulting work

If the lookup surfaces something that should become tracked work, this skill's job ends at
the GitHub-side read/update. Route the follow-up through `sdlc-idea` (exploration),
`sdlc-lite-plan`/`sdlc-plan` (concrete scope), or `sdlc-handoff` (park it) — do not expand
this skill's scope to cover planning the work itself.

## SDLC Checkpoint Recipes

These named recipes are what `[sdlc-root]/process/github-checkpoints.md` calls by name from
inside `sdlc-plan`, `sdlc-lite-plan`, `sdlc-execute`, `sdlc-lite-execute`, `sdlc-handoff`,
and `sdlc-archive`. **That document owns the policy** — the checkpoint map, the column
role→name→rank config, the floor rule, comment templates, terminology, and the failure-class
table. This section owns only the mechanics: the exact `gh`/`git` calls, in what order, with
what error handling. If a rank, a column name, or a comment template is needed, read it from
that document at call time — never restate it here, so the two cannot drift apart.

**Activation gate.** Recipes may only be invoked when the policy doc exists and its config
block says `enabled: true`. **Issues-only mode** (`board.default: none`): every board
operation in every recipe is a silent no-op — `create-or-link` skips its board add,
`resolve-and-write-status` returns without writing — while issue creation, comments,
commits, and the miss-log run in full.

**Scope note.** These recipes exist to be called *by* SDLC checkpoints, not to be invoked
directly from a natural-language ask. A human asking "move issue #12 to In Progress" still
goes through Steps 1–6 above, with normal confirmation. An SDLC checkpoint calling
`resolve-and-write-status` goes through this section, under the carve-out below.

### Checkpoint carve-out — no per-call confirmation for SDLC checkpoints

**Step 4's confirmation requirement above does not apply when a recipe in this section is
invoked by an SDLC checkpoint.** Three things make that safe, stated in both this file and
`[sdlc-root]/process/github-checkpoints.md` so neither can contradict the other: the target is unambiguous (the
issue is identified by its `Dnn` join key), the transition is determined by the checkpoint
map rather than chosen in the moment, and CD's completion of the policy doc's § Enablement is
the standing authorization for the entire checkpoint map. The exemption is scoped to these
recipes when called from an SDLC checkpoint — it does **not** extend to this skill's own
interactive use, where a human is steering and confirmation is the whole point. Two
exceptions inside the checkpoint map itself still ask rather than assume: CP-11b *offers*
issue creation via `AskUserQuestion`, and driving-repo selection rule 4 asks rather than
guessing when the repo is genuinely ambiguous.

### Shared discipline across all recipes

- **Name-then-resolve, never ID-then-assume.** Every board field/option is resolved by
  **name** (from the config block's role mapping) on the **target board**, in the **current
  session**, via `gh project field-list <project-number> --owner <org> --format json`.
  Resolved IDs may be cached in process memory, keyed by project number, for the life of the
  session — **never written to disk, never reused across sessions, never reused across
  boards.** A cached ID from one board is meaningless on another even when both boards have
  a field or option with the identical name.
- **No fabricated IDs, ever.** `PVT_...`, `PVTSSF_...`, `PVTI_...`, and single-select option
  IDs are always the output of a `gh project field-list` / `gh project item-list` call made
  in this session, never a literal written into this file or a comment. Repo ownership is
  confirmed via `git remote -v`, never guessed.
- **Column-not-found is fail-through, never fallback.** If the target board has no Status
  option by the required name, that is the "target board has no column with the required
  name" failure class: log the miss, post the comment, write nothing to Status. Never
  closest-match, never substitute a visually similar column.
- **Post the comment before the Status write, in every recipe and every caller pattern.**
  If only one of the two survives a failure, a narrative with no column move is far more
  useful than a moved column with no explanation.
- **Failure detection is mechanical.** Classify on exit codes and HTTP status — `gh`
  subcommands surface these in their exit code and, for `--json` output, in the response
  shape. Never match on stderr prose; it changes between `gh` releases and a classifier
  keyed on wording fails silently the day the wording changes.
- **Remediation is a lookup, not a loop.** Implement the table below as failure-class →
  single-action. At most **one** remediation attempt per checkpoint, full stop — if a second
  operation in the same checkpoint also fails, it fails through immediately with no
  remediation. A counter-based loop invites someone to raise the bound later; a lookup table
  has no bound to raise.

  | Failure class | Detection | Remediation |
  |---|---|---|
  | Stale cached field/option ID | write rejected as unresolvable | re-run `gh project field-list`, invalidate the session cache entry for that project number, retry the write once |
  | Transient network / API 5xx / timeout | non-2xx / timeout exit | retry once, immediately, no backoff |
  | 404 / wrong repo | 404 exit | re-resolve via `git remote -v`, retry once |
  | Auth failure | 401/unauthenticated | run `gh auth status` once to confirm, then fail through — never `gh auth login`/`gh auth refresh` |
  | Push rejected, non-fast-forward | non-zero exit on `git push` | one `git pull --rebase`, retry push once; **re-capture the SHA after the rebase** |
  | Rebase hits a conflict | non-zero exit on `git rebase` | `git rebase --abort`, fail through — never auto-resolve, never force |
  | Rate limit | 403 with rate-limit headers | none — fail through immediately |
  | Target board lacks the named column | option name absent from `field-list` output | none — fail through immediately |
  | Anything else | — | none — fail through immediately |

  **Forbidden in every code path, with no exceptions:** `git push --force`, `git push
  --force-with-lease`, interactive `gh auth login`/`gh auth refresh`, reinstalling or
  upgrading the `gh` binary, any sleep/backoff/retry-loop for a rate limit.
- **Fail-through does three things, no more:** surface a one-line notice in session output,
  append one entry via `log-miss`, let the calling SDLC step continue. Never abort the step
  that called the recipe.

### Recipe 1: `create-or-link`

Idempotent-by-`Dnn`-prefix issue creation, with the pre-deliverable promotion path and an
idempotent board add. Labels ride on the create call — there is no separate label recipe
(see recipe 4).

**Takes a `mode` parameter — `registration` or `parked` — set by the caller, never
inferred.** The two SDLC checkpoints that call this recipe need genuinely different titles,
bodies, and label sets:

| | `mode: registration` (called by CP-1) | `mode: parked` (called by CP-11b) |
|---|---|---|
| Title | `Dnn — <Deliverable Name>` | `Parked: <short description>` — **no `Dnn` prefix** |
| Body | CP-1 body, `[sdlc-root]/process/github-checkpoints.md` § Comment Templates | CP-11b body, `[sdlc-root]/process/github-checkpoints.md` § Comment Templates |
| Labels | universal label [+ conditional labels], classified per the policy doc's § Labels | universal label only — parked work has no scoped file set yet to classify conditionals against |
| Issue type (when `issue_types` is not `none`) | Classified per the policy doc's § Issue Types | `Task`, always — parked work has no settled shape to classify |
| Steps 1–2 (`Dnn`-prefix search, promotion) | Run | **Skipped** — see below |
| Step 5 (`link-sub-issue`) | Run when the deliverable is a sub-deliverable | **Skipped** — parked work has no D-number, so it cannot be a sub-deliverable yet |

1. **[`mode: registration` only] Search for an existing issue carrying the `Dnn` prefix**,
   open and closed, in the driving repo resolved per `[sdlc-root]/process/github-checkpoints.md` § Repo
   Selection:
   ```bash
   gh issue list --repo <org>/<repo> --state all --search "\"Dnn\" in:title" \
     --json number,title,state,url --limit 30
   ```
   Filter results in-memory for a title that starts with `Dnn` followed by a space, em dash,
   or colon — a substring match on `Dnn` alone is not sufficient (it would also match `D4`
   inside `D40`). If a match is found, **link, do not create** — skip to step 4 with that
   issue's number (step 3 is creation-only). An already-typed linked issue keeps whatever
   type it has.

   **`mode: parked` skips this step entirely.** `Parked: …` titles are deliberately
   prefix-less, so a `Dnn`-prefix search can never match one — running it would spend a `gh`
   call to guarantee a miss.
2. **[`mode: registration` only] Promotion path — check before creating.** If the caller
   passed an originating handoff doc path, read its `github_issue:` frontmatter first. If it
   names `repo#N`, that issue is the target: **link and retitle** it — the same call carries
   the deliverable's issue type when `issue_types` is configured (the `gh issue edit` command
   has no type flag, so the promotion edit goes through the REST endpoint):
   ```bash
   gh api -X PATCH repos/<org>/<repo>/issues/<N> \
     -f title="Dnn — <Deliverable Name>" -f type="<Bug|Feature|Task>"
   ```
   — rather than creating a second issue. This is also where a parked issue's placeholder
   `Task` type is corrected to the deliverable's real classification, and it keeps step 1's
   idempotency guarantee intact across the pre-deliverable boundary (the handoff issue and
   the deliverable issue are the same issue). Skip to step 4 (step 3 is creation-only).
3. **No match anywhere — create.** Labels **and the issue type** ride on the create call
   itself, never a follow-up edit. The create goes through the REST endpoint rather than
   `gh issue create` because the CLI command has no type flag and the REST create accepts
   `type` alongside `labels` — one call sets everything:
   ```bash
   gh api -X POST repos/<org>/<repo>/issues \
     -f title="<mode-specific title>" -f body="<mode-specific body>" \
     -f type="<mode-specific type>" \
     -f "labels[]=<universal>" [-f "labels[]=<conditional>"...]   # conditionals: mode: registration only
   ```
   Title, body, labels, and type come from the mode table above. Omit `type` when
   `issue_types: none`.

   **The REST create silently auto-creates any label that does not exist in the repo**
   (verified live by the originating project) — it never fails on an unknown label. The
   hazard is not a blocked create, it is **silent label sprawl**: this call may only ever
   pass labels from the policy doc's config block, exactly as spelled there — a typo becomes
   a new repo label nobody decided to create. The audit's taxonomy parity check (§ 10h) is
   the detector. Similarly, the REST docs note `type` is silently dropped for callers
   without push access (the response is still 200) — no failure surfaces to `log-miss`, and
   the audit's untyped-issue check is the only detector. Neither hazard blocks creation,
   which is the posture the never-block invariant wants.
4. **Add to the board at the `registered` column, idempotently.** Skipped entirely in
   issues-only mode. Before adding, check whether the issue is already an item on the target
   board:
   ```bash
   gh project item-list <project-number> --owner <org> --format json --limit 200 \
     | jq --arg n "<issue-number>" --arg r "<repo>" \
       '.items[] | select(.content.number == ($n|tonumber) and .content.repository == $r)'
   ```
   If no item matches, add it, **then explicitly write the `registered` column to the new
   item's status field** (resolve field and option ID by name as in `resolve-and-write-status`
   steps 1–2; the floor read is skipped because a freshly added item's Status is known-empty
   — GitHub does not place it in any column by default, so without this write the card sits
   column-less on the board):
   ```bash
   gh project item-add <project-number> --owner <org> --url <issue-url>
   gh project item-edit --project-id <PVT_...> --id <PVTI_...> \
     --field-id <PVTSSF_... for the status field> --single-select-option-id <option-id for registered>
   ```
   If an item already matches, do nothing — adding an already-present item must never
   duplicate it. Call `resolve-and-write-status` normally (floor read included) when this
   recipe took the link-existing path in step 1 or 2, since a human may already have moved
   that card — and on that path the caller's checkpoint comment must already be posted
   before the Status write (comment-before-Status applies; on the fresh-create path the
   issue body created in step 3 *is* the checkpoint content, so the ordering is already
   satisfied).

   Two mechanical cautions on the item-list matching: confirm the actual shape of
   `content.repository` from the JSON before matching (bare name vs. `owner/name` varies by
   `gh` version — match against what the call actually returns, never assume); and **when a
   listing returns exactly its `--limit`, page to completion before concluding the item is
   absent** — a truncated listing that misses an existing item causes a duplicate board add.
5. **[`mode: registration` only] Sub-deliverable linking**, when the deliverable being
   registered is a sub-deliverable (`D41a`, not `D41`): call `link-sub-issue` (recipe 3)
   with the parent's issue and this new issue.

Call budget note: CP-1 carries `[sdlc-root]/process/github-checkpoints.md`'s documented exemption (≤8 happy
path / ≤10 worst case) — the only checkpoint permitted to exceed the ordinary ≤4 `gh`-call
cap, because it fires exactly once per deliverable rather than accumulating across a
multi-phase deliverable.

### Recipe 2: `resolve-and-write-status`

Role→name→option-ID resolution on the **target** board, the floor-rule read-then-write, and
the CP-S2 exact-match exception. Roles, names, and ranks are read from
`[sdlc-root]/process/github-checkpoints.md`'s config block — this recipe carries no copy of its own. **A silent
no-op in issues-only mode.** A target role mapped to `null` in the config is likewise a
no-op (the caller still posts its comment).

**Hard guard, checked first, unconditionally:** NEVER-WRITE: if the caller's resolved target
column name appears in the config block's `never_write` list, refuse the call outright — no
recipe may write those columns regardless of caller. This is not a floor-rule case; it is a
refusal before the floor rule is even evaluated.

**Informational — board-native automations are out of band.** A board may have GitHub's
native "Auto-close issue" Projects v2 workflow enabled: a human moving a card into a
terminal column can close the underlying issue as a side effect, entirely outside this
recipe. `gh project field-list` cannot surface board-level workflow configuration, so this
recipe cannot detect it, and does not need to — the NEVER-WRITE guard already prevents *this
recipe* from originating such a transition. If a close appears to have already happened when
this recipe or CP-10 goes to act, treat it as expected rather than a failure to diagnose.

1. **Resolve the item** on the target board: locate the project item ID (`PVTI_...`) for
   this issue via `gh project item-list <project-number> --owner <org> --format json --limit
   200`, matching on `content.number` + `content.repository`. The same query's `status`
   field on that item is the current Status column name `C` — no separate read is needed.
2. **Resolve the field and target option ID** on this board, this session:
   ```bash
   gh project field-list <project-number> --owner <org> --format json
   ```
   Find the configured status field, and within its `options`, the option whose `name`
   exactly matches the target role's configured column name `T`. **If no option by that name
   exists**, this is the "target board has no column with the required name" failure class:
   `log-miss`, return without writing (the caller is responsible for the comment; this
   recipe only handles the Status write).
3. **Rank comparison.** Look up `rank(T)` and `rank(C)` from the config block's `columns`
   table.
   - If `rank(T) > rank(C)`: proceed to step 4.
   - If `rank(T) <= rank(C)` **and** this is not a CP-S2 call: skip the write. The caller
     still posts its comment — this recipe does not decide comment behavior.
   - If this **is** a CP-S2 call (the caller passes an explicit `is_cp_s2` flag — never
     inferred from the target name alone): apply the exact-match exception — step 3a.
3a. **CP-S2 exact-match exception.** The write fires **if and only if** the item's current
    Status `C`, read in step 1, is *exactly* the `stakeholder-blocked` role's configured
    column name. If a human has moved the card anywhere else, this recipe writes nothing —
    the caller still posts its comment. This is the one recipe-level backward transition in
    the whole system; no other caller may pass `is_cp_s2: true`.
4. **Write.**
   ```bash
   gh project item-edit --project-id <PVT_...> --id <PVTI_...> \
     --field-id <PVTSSF_... for the status field> --single-select-option-id <option-id for T>
   ```
   On a rejection classified as the "stale cached ID" failure class, re-run step 2's
   field-list fetch (invalidating the in-memory cache entry for this project number) and
   retry this write once. Any other failure class follows the shared remediation table.

### Recipe 3: `link-sub-issue`

Parent/sub linking via GitHub's **native** parent/sub-issue relationship — not a label, not
a comment convention. Boards' Parent issue / Sub-issues progress fields populate
automatically once the relationship exists; there is no separate board-field write.

1. Resolve both issues' GraphQL node IDs:
   ```bash
   gh api graphql -f query='
     query($owner:String!,$repo:String!,$number:Int!){
       repository(owner:$owner,name:$repo){ issue(number:$number){ id } }
     }' -f owner=<org> -f repo=<repo> -F number=<issue-number>
   ```
2. Create the relationship:
   ```bash
   gh api graphql -f query='
     mutation($issueId:ID!,$subIssueId:ID!){
       addSubIssue(input:{issueId:$issueId, subIssueId:$subIssueId}){
         issue { number } subIssue { number }
       }
     }' -f issueId=<parent node ID> -f subIssueId=<sub node ID>
   ```
   `replaceParent` is left at its default (`false`) — a sub-issue that already has a
   different parent is a data problem for a human to resolve, not something this recipe
   silently overwrites.
3. No board write follows this.

Fires only when the deliverable being registered is a sub-deliverable (called from
`create-or-link` step 5); it is never invoked standalone by a checkpoint.

### Recipe 4: *(no separate label recipe)*

Deliberately absent. Labels are applied on `create-or-link`'s own create call (recipe 1,
step 3: the REST create's `labels[]` fields) — this is what keeps CP-1 near the floor of its call-budget
exemption, and labels travel with the issue across boards where a board field would need a
fetch/edit pair per board. There is no follow-up label-edit call anywhere in the checkpoint
recipes.

### Recipe 5: `commit-and-push-artifact`

Pathspec-scoped commit, push, and SHA capture. Never bulk-staged, never force-pushed.

1. **Stage by explicit path only:**
   ```bash
   git add <artifact-path> [docs/_index.md]
   ```
   `docs/_index.md` is staged **only** when this checkpoint itself changed the catalog row,
   and only after confirming the only delta against HEAD in that file is the intended row —
   `git diff HEAD -- docs/_index.md` and inspect it. If other deltas are present (a
   concurrent session's edit), stage and commit the artifact **alone**, skip the catalog
   from this commit, call `log-miss`, and surface a one-line notice that the catalog row
   needs a follow-up commit. `git add -A` / `.` / `-u` are forbidden outright, no exception.
2. **Idempotence check.** If `git diff --cached --quiet` reports no staged changes (the
   artifact was already committed, e.g. a re-run), skip the commit entirely and resolve
   `git rev-parse HEAD` as the SHA — never produce an empty commit, never fail because there
   was nothing to commit.
3. **Commit with a matching pathspec** — the same paths just staged, repeated on the commit
   command as belt-and-braces against a concurrent `git add` landing between steps 1 and 3:
   ```bash
   git commit <same paths as step 1> -m "docs[D<N>]: <artifact kind>"
   ```
   Pre-deliverable handoff commits (CP-11b) carry no `[D<N>]` tag: `docs: park <slug>
   handoff`.
4. **Push.**
   ```bash
   git push
   ```
   On a non-fast-forward rejection: `git pull --rebase`, then retry the push once. If the
   rebase itself hits a conflict: `git rebase --abort`, fail through (comment posts with the
   workspace path plus a note that the file reaches GitHub at the next push; `log-miss`
   records it). Never `--force`, never `--force-with-lease`, in any path.
5. **Capture the SHA — only after a push that succeeded:**
   ```bash
   git rev-parse HEAD
   ```
   If step 4 required a rebase-retry, this SHA is captured **again**, after the rebase — the
   pre-rebase SHA is not the SHA that was actually pushed, and linking it would point to a
   commit that exists only in a discarded local state.

### Recipe 6: `log-miss`

Atomic single-line JSONL append to `[sdlc-root]/.local/github-checkpoint-misses.jsonl`. This
path must already be gitignored (§ Enablement step 5) before any recipe writes to it.

1. **Append, never read-modify-write:**
   ```bash
   mkdir -p <sdlc-root>/.local
   printf '%s\n' "$(jq -nc \
     --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     --arg deliverable "<Dnn>" --arg checkpoint "<CP-n>" --arg op "<operation>" \
     --arg target "<repo#N or board item>" --arg detail "<what was being written>" \
     --arg error "<the failure>" --arg remediation "<what was attempted, or 'none — <class>'>" \
     '{ts:$ts,deliverable:$deliverable,checkpoint:$checkpoint,op:$op,target:$target,detail:$detail,error:$error,remediation:$remediation}' \
   )" >> <sdlc-root>/.local/github-checkpoint-misses.jsonl
   ```
   A single `>>` redirect is an atomic append at the OS level for a line this short — never
   open the file for read-modify-write, which loses entries under concurrent sessions.
2. **Compaction** (clearing entries reconciliation has healed) writes a temp file and renames
   it over the original — never truncates and rewrites in place, which is not atomic:
   ```bash
   jq -c 'select(.healed != true)' <miss-log> > <miss-log>.tmp && mv <miss-log>.tmp <miss-log>
   ```

### Cross-board option-ID validation — verified behavior

`updateProjectV2ItemFieldValue` (what `gh project item-edit --single-select-option-id`
wraps) validates that the **option ID belongs to the field** it is being written to — it
does **not** validate that the caller resolved that ID against this project, this session,
or any particular board. This was live-tested against real boards by the originating
project, not inferred from documentation: one board's option ID was also a live, valid
option ID on a second board's `Status` field, mapping to an entirely different column — a
write using the second board's correct field ID paired with the first board's option-ID
string **succeeded silently, exit 0**, and landed the card on `Done` with no error at all.

The practical consequence: **the name-then-resolve discipline (fetch by name, every session,
never cache to disk, never reuse across boards) is the only thing preventing a silent
wrong-column write.** There is no server-side check standing behind it. Treat every
deviation from name-then-resolve as a live risk of a silent mis-write, not a theoretical one
caught by a second layer of validation.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll use the github MCP issue tools to browse the project board" | Those tools only resolve repo issues by number/query and 404 on Projects v2 board items; there is no MCP tool that enumerates a board. Use `gh project item-list` instead. |
| "I know the org's casing" | Confirm with `gh project list --owner <org>` rather than assuming — GitHub resolves multiple casings, but don't guess when scripting calls that matter. |
| "Issue #8 is issue #8 everywhere" | Item/issue numbers are per-repo. The same number frequently exists in multiple repos on the same board with unrelated content — disambiguate before touching anything. |
| "I can update the board status with the field's display name" | Projects v2 field edits require the field ID and option ID, fetched via `gh project field-list`, not the human-readable label. |
| "This item's `status` tells me if the underlying issue is closed" | Board `status` and the repo issue's open/closed `state` are independent — check both if it matters. |
| "I'll just close/reopen/create without confirming — it's just a CLI command" | Closing, reopening, editing, or creating issues is a visible action every collaborator sees. Confirm scope first (interactive use). |
| "No repo was named, I'll guess from context" | Confirm the owner/repo pair via `git remote -v` before running any `gh issue` command. |
| "This SDLC checkpoint should confirm before writing Status, like Step 4 says" | Step 4's confirmation requirement is the interactive-use posture. SDLC checkpoints calling § SDLC Checkpoint Recipes are exempt under the checkpoint carve-out — the target and transition are already determined by the checkpoint map. |
| "I can cache this board's field/option IDs and reuse them next session, or on another board" | Never. IDs are resolved by name every session, per project number, in process memory only. The same ID string means something different on a different board — and GitHub will accept the wrong one silently. |
| "The write failed, let me retry until it works" | Remediation is a one-shot lookup table, not a loop — at most one attempt per checkpoint, then fail through. |
| "The push was rejected, I'll force it through" | Force-push (`--force` or `--force-with-lease`) is forbidden outright in every checkpoint recipe. A push that one `pull --rebase` cannot resolve fails through with a degraded link. |
| "I'll `git add -A` to make sure the artifact and the catalog both get committed" | Forbidden outright. Stage by explicit path, commit with a matching pathspec — concurrent sessions share this working tree. |
| "There's no board configured, so the convention is broken" | `board.default: none` is issues-only mode, a fully supported configuration: comments and issue lifecycle run; Status writes are silent no-ops. |
| "The title/label tells me enough to classify this issue" | For any judgment call (decision-needed vs. agent-ready, approval-needed, done vs. stale), read the full body AND comments for that specific issue, and check linked specs/plans for whether the "open question" is already answered — before asserting. Do this proactively. |
| "The create call will fail if I pass a wrong label, so any label is safe to try" | The REST create silently auto-creates unknown labels — a typo becomes a new repo label nobody decided on. Pass only labels from the policy doc's config block, spelled exactly. |
| "The issue body says this is still open, so the work isn't done" | Completion is posted as a comment (CP-9–CP-12); the body is written once and rarely updated. Fetch and read `comments` to the end of the thread before concluding anything about state. |

## Integration

- **Depends on:** `gh` CLI installed and authenticated; git remotes configured;
  `[sdlc-root]/process/github-checkpoints.md` config block for org/repos/board/roles (the
  checkpoint recipes require it; interactive use degrades gracefully without it).
- **Feeds into:** `sdlc-idea`, `sdlc-lite-plan`, `sdlc-plan`, `sdlc-handoff` — once a lookup
  surfaces work that needs tracking, those skills take over.
- **Called by (SDLC checkpoints):** `sdlc-plan`, `sdlc-lite-plan`, `sdlc-execute`,
  `sdlc-lite-execute`, `sdlc-handoff`, `sdlc-archive` — each calls § SDLC Checkpoint Recipes
  by name at the checkpoints it owns, per `[sdlc-root]/process/github-checkpoints.md`. That
  document is the policy source; this skill is the mechanism. Neither restates the other.
- **Uses:** `gh` CLI (`gh project`, `gh issue`, `gh api graphql`); `git`
  (`add`/`commit`/`push`/`pull --rebase`/`rev-parse`) for the checkpoint recipes that commit
  artifacts.
- **Complements:** the `github` MCP server tools, for the subset they cover well (PR
  reviews, repo file operations, commit/branch operations, repo-scoped issue search).
- **Does NOT replace:** the github MCP tools for PR review workflows or repo file
  operations — this skill exists for the Projects v2 board gap and quick CLI round-trips.
- **Relationship to the deliverable lifecycle:** the board column roles
  (`registered`…`staged`) are a deliberately separate, per-project-configurable taxonomy —
  not a rename of `[sdlc-root]/process/deliverable_lifecycle.md`'s catalog statuses. The
  catalog remains canonical; the policy doc's config block maps roles to board column names,
  and the audit dimension's § 10e table maps catalog statuses onto role floors. This skill
  transitions board cards, never catalog state.
- **DRY notes:** § SDLC Checkpoint Recipes is the single place the checkpoint `gh`/`git`
  call sequences exist — `[sdlc-root]/process/github-checkpoints.md` and the calling skills' fragments all point
  here rather than carrying their own copies. The recipes stay **inline in this file, not in
  `references/`, deliberately**: checkpoints call them by name under the never-block
  invariant, and an extra "read the reference file first" hop is exactly the kind of
  skippable indirection the framework's directive-inlining convention exists to avoid.
