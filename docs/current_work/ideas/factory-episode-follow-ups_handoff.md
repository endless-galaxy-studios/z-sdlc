---
type: handoff
slug: factory-episode-follow-ups
created: 2026-11-05
status: pending
trigger: idea
recommended_next_skill: sdlc-lite-plan
source_session_summary: "z-sdlc's review of an AI That Works episode on software factories found four ideas worth taking; CD had Where to look built (f436be2) and parked the other three, plus a doc gap the review found"
active_deliverable: null
related_files:
  - bundles/factory/tree/improve_report.py
  - bundles/factory/tree/improve_harvest.py
  - bundles/factory/tree/improve.schema.json
  - bundles/factory/tree/templates/factory-implement.yml
  - bundles/factory/tree/templates/factory-revise.yml
  - bundles/factory/tree/bootstrap.py
  - bundles/factory/tree/workflow_policy.py
  - skills/sdlc-plan/SKILL.md
  - process/factory.md
---

# Handoff: follow-ups from the software factory episode

## Why this is a handoff

z-sdlc reviewed "How to Build an AI Software Factory That Ships Faster" (AI That Works, 2026-10-23, with Warp's CEO: https://www.youtube.com/watch?v=XUEfIxkdT2Q) against the `factory` bundle. Most of what the episode describes the bundle already does, under stricter rules:
- the factory as versioned code (`bundles/factory/tree/` and `factory.json`);
- agents improving it from failed runs (D5);
- metrics recorded at the source (`run_metrics.py`);
- trying variants on the same work (`compare` runs);
- a person reviewing risky changes (the risk tiers, and the publish guard's refusals);
- checking code against its spec (Deviations, Scope integrity and the review loop).

Four ideas were worth taking. CD had the first built, Where to look (z-sdlc `f436be2`, imported in `4555684`), and parked the other three on 2026-11-05 "for now". Those three are below, with a documentation gap the review found. They're independent of each other, so any one can be picked up alone.

## What needs to happen

### 1. Yield numbers in the weekly report (factory code)

`facts()` in `improve_report.py` (line 148 as of `4555684`) reports the week's runs and cost, nothing more. The digest the harvest builds already carries each factory PR's revisions, changes requested, hours open, cost and models, so these need no new collection:

- the share of merged PRs that needed no revision;
- how often CD had to step in per merged PR (reviews, answered questions, revisions). This is the episode's "how automated are you" measure, which can improve gradually instead of being yes or no;
- cost per merged PR, and cost by stage;
- outcomes by advisor. A `compare` run varies only the advisor (`none`, `opus`, `fable`), and the report counts comparison PRs (`improve_harvest.py`, the outcome function at line 421) but never says which variant won or what each cost. This gives compare runs a number instead of an impression;
- trends in turns and denials. The episode used AI-judged checks for agents hitting dead ends or relearning how to run tests. These counts are the stand-in that needs no transcripts, which D5 forbids.

It's factory code, so it's built in the incubator's `.github/factory/` first and imported with `zsdlc-import-factory`. `process/factory.md` D5 lists what the report holds; add the new figures there.

### 2. Plan detail in proportion to how hard a change is to undo (skill text)

This is one rule in `skills/sdlc-plan/SKILL.md`: put the spec's detail into what's costly to change later (schema, saved state, external contracts) and leave cheap details, like a button's colour, to execution. The PR template's risk tiers already use "a revert fully undoes it" to judge a change for review; this applies the same test when planning one. It's a z-sdlc edit, made directly with its changelog entry. Check `sdlc-lite-plan` and `sdlc-plan`'s reviewers for a place it belongs as well.

### 3. Benchmarks replayed from real issues (a design, then factory code)

**What it is.** It re-runs an issue the factory already finished and CD merged, starting from the commit before the fix, with a changed model, advisor or skill. A `compare` run works on a live issue whose answer nobody knows yet, so CD judges every PR. A replay has a known answer, so most scoring is automatic:
- whether the merged PR's own tests pass on the replay's code (applied afterwards, never shown to the agent);
- cost, turns and time;
- files touched outside the merged PR's set, and findings still open at the end.

The same dozen or so tasks run before and after a change, each two or three times to show how much results vary, and CD reads one table.

**What it's for:**
- choosing defaults: the implement model, and whether the advisor is worth its cost;
- testing z-sdlc skill changes on known tasks before a release, instead of weeks of live improve reports;
- measuring an accepted improve proposal's `effect` field (`improve.schema.json`), which nothing measures today.

It's a regression check on a few tasks, not a model ranking: the episode's A/B tests need far more runs than a small organization's factory produces.

**Why it's big.** It touches nearly every rule the stages run by:
- **A different starting point.** Implement always checks out the default branch. A replay starts from the commit before the fix, with today's agent configuration laid over it. Revise already does this over a PR's older checkout (`factory-revise.yml`, lines 218–222). What gets laid over is open: skills and `CLAUDE.md`, yes. Knowledge YAMLs and discipline entries, no: a lesson written in the PR being replayed would hand the agent the answer. But skills can encode lessons too.
- **Hiding the answer:**
  - the issue's context is cut off at the original dispatch, so the agent never sees the "Draft PR opened" comment or CD's review thread;
  - the merged PR's tests stay out of the checkout until scoring;
  - D2 rule 5 tests a boundary before anything relies on it, so smoke needs a probe proving a replay can't see the future: a canary planted in the fix commit that the agent must not find.
- **Nothing written to the live record:** no PR, push, comment or label on the original issue, and nothing the harvest could mistake for CD's reviews and replies. Results go to a run summary, or to one report a writer job posts.
- **New plumbing:**
  - a new workflow, added to the runner group's selected workflows (`bootstrap.py`);
  - `workflow_policy.py` rules for it;
  - a code-owned task list (issue, starting commit, merged PR, its test files);
  - tests;
  - a new design rule, D6, in `process/factory.md`.

  It's built in the incubator first and imported, and it's a minor release.
- **Old tasks stop building.** The job image is pinned to today's toolchain, so a task from months ago may no longer build, and the list needs pruning.
- **Cost.** Every replay is a full implement run on the same plan usage as live work, multiplied by tasks, variants and repeats.

**Testing z-sdlc skills needs no new trust path** if they're tested after they reach the incubator's default branch and before a release. A replay then compares the skills at one default-branch commit with the skills at a later one: both reviewed, both from the default branch, and the runner groups still take only the default branch's workflows. Testing a skill before it's merged anywhere would need a new trust path. Don't build that version.

### 4. Compare runs are undocumented (doc gap)

`process/factory.md` doesn't mention `compare` runs. The only documentation is the input's description in `factory-implement.yml` (line 40). A section should say:
- how to start one: dispatch `factory-implement.yml` by hand with `compare=true` and an `advisor`, once per variant;
- that each variant gets its own branch (`factory/<n>-impl-<advisor>`) and queue, and opens a draft PR titled `[advisor: …]`;
- that a comparison run reports and stops, with no label changes;
- that the harvest counts a closed sibling as `comparison`, not `rejected`;
- its limits: implement only, the advisor is the only thing that varies, one run per variant, and several PRs for CD to read.

It's a z-sdlc doc edit with a changelog entry, and it pairs with item 1's advisor outcomes.

## Recommended next step

They're independent, so pick by value:
- **Item 2** is the smallest: one rule in `sdlc-plan`, directly here.
- **Item 4** is a short doc section, directly here.
- **Item 1** is a planned change to `improve_report.py` and its tests in the incubator, with `sdlc-lite-plan`.
- **Item 3** needs a design first (`sdlc-idea`, then `sdlc-plan`), and CD's decisions on the open questions below.

## Open questions

- **Item 3:** which configuration a replay lays over the old commit (skills and `CLAUDE.md` only, or more), and how to keep skills that encode a replayed task's lesson from leaking the answer.
- **Item 3:** the starting task list: which merged issues, and who curates and prunes it.
- **Item 3:** the budget per replay round, since it draws on the same plan usage as live work.
- **Item 1:** whether the advisor outcomes need a minimum number of runs before the report shows a split.

## Out of scope (do NOT pursue)

The episode's other ideas each run into a factory rule:
- **AI-judged checks over transcripts** (redundant tests, dead ends): D5 forbids transcripts as a data source. Item 1's turn and denial trends are the version that fits.
- **Merging small PRs without review:** the bundle is built on CD approving every merge.
- **Screenshots or recordings in PR bodies:** writer jobs refuse images (D2 rule 3), and no stack profile has a browser. At most, a link to a CI-tier artifact.
- **Build it, rewrite the spec from what was learned, build it again:** it doubles the cost, revise runs are capped, and `sdlc-plan` prefers checking the real code first to throwaway prototypes.
- **Yield as customer or business results:** outside what the bundle covers.
