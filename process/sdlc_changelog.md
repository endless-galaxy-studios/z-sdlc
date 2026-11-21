# SDLC Process Changelog

A living record of how the process evolves through real use. Each entry captures what changed, why, and where the change originated.

<!-- changelog-archive-pointer -->
> Older entries are in `changelog-archive/`, one file per quarter, moved there unedited once this file passed about 150 KB.

---

## Format

Each entry contains:
- **Date** — when the change was made
- **Origin** — what prompted the change (a session, audit finding, or observed friction)
- **What happened** — context leading to the change
- **Changes made** — numbered list of specific file changes
- **Rationale** — why the change improves the process

---

## Example Entry

```
## YYYY-MM-DD: [Brief Title]

**Origin:** [What prompted this — e.g., D7 planning session compliance audit, upstream sync]

**What happened:** [Context — what was observed, what problem was found]

**Changes made:**

1. **`[file path]`** — [what changed and why]
2. **`[file path]`** — [what changed and why]

**Rationale:** [Why this improves the process — the insight that led to the change]
```

---

## 2026-11-21: The factory imported from the incubator (664b097..f2af44d): z-sdlc's changes through v2.9.4 handed back

**Origin:** The incubator took z-sdlc's factory changes from v2.8.0 to v2.9.4 in two PRs, #148 (through v2.9.0) and #149 (v2.9.1 to v2.9.4). Those changes are the browser route, browser evidence, the reproduce step and the `sdlc-reproduce` skill, the `browser.stages` check, and the video and trace rules.

**Changes made:**

1. **`.claude/skills/zsdlc-import-factory/import.json`** — `last_import` moves to the incubator's merge of #149, `f2af44d`. The import reads every bundle file in sync, and the skills and process doc the incubator copies match. No bundle code or seed changed. The proof passed in the incubator and in an empty project.

---

## 2026-11-21: A run that records video traces without screenshots

**Origin:** The pilot project, measuring a real 90-second run on Playwright 1.61.1. With video on, the trace's screenshot frames are captured at the video's size (1280×720, not 800×450): the trace was 61.2 MB, 57.2 MB of it frames, and `tracing.stop` took 18 s. Without the frames it was 3.9 MB, and stop took 1.5 s. `evidence.py` keeps a trace up to 50 MB, and v2.9.2 turned video on for every browser stage, so every project's long runs would have lost their trace. CD chose the rule over raising the limit.

**Changes made:**

1. **`process/factory.md` D6 rule 5, the `factory-browser` mirror and its copies in `sdlc-implement`, `sdlc-revise` and `sdlc-reproduce`** — a run that records video takes its trace without screenshots (`tracing.start({ screenshots: false })`), since the video is the visual timeline.
2. **D6 rule 7** — says why, with the measurement.

---

## 2026-11-20: The factory's evidence folder can hold an earlier run's files

**Origin:** The pilot project, from its evidence PR's review. CD chose to state the rule, and left a mechanical check for later.

**Changes made:**

1. **`process/factory.md` D6 rule 5, the `factory-browser` mirror and its copies in `sdlc-implement`, `sdlc-revise` and `sdlc-reproduce`** — within one job, a run refused by the project's guard, or one that never started, leaves the previous run's files in `.factory/evidence/`. The rule now says so: treat the latest run as not run (reproduce reports `blocked`), and cite none of the folder's files. A mechanical check, with `with-browser` stamping each invocation and the report flagging older evidence, waits until a factory run shows the problem.

---

## 2026-11-20: The factory's video evidence: plain video, one per stage, switched on by the factory, written by the project's helper

**Origin:** The review of the pilot project's evidence and video PR. It sent four notes, and CD chose all four as recommended.

**Changes made:**

1. **Plain video (`process/factory.md` D6 rule 7, and rule 5 in the `factory-browser` mirror and its copies in `sdlc-implement`, `sdlc-revise` and `sdlc-reproduce`)** — reproduce and verify runs record plain `recordVideo`, never annotated. Playwright's annotated video (`recordVideo.showActions`, in 1.61) waits before every input on its context, 500 ms by default. That can hide a race or break a short UI window, so a factory run would disagree with CI's run of the same spec. The trace already marks each action. Before, rule 7 preferred annotated video from 1.59.
2. **One video per stage** — implement, execute and revise run the spec failing and then fixed, and keep the verifying run's video, the last. The failure shows in screenshots, and in the reproduce step's own video. Rule 7 allowed one video without saying which.
3. **The factory turns video on** — `browser.py` writes `video=1` into `browser.conf` for the stages and `video=0` for smoke. `with-browser` exports it as `FACTORY_EVIDENCE_VIDEO`, so a project's evidence helper knows when to record. `reproduce_report.py` says "No video" in the issue comment when a reproduce run (not a blocked one) kept none. Before, nothing in the bundle switched video on, and a run without it passed every check. New tests in `test_browser.py` and `test_reproduce.py`.
4. **The project's evidence helper writes the manifest** — rule 5 and `sdlc-reproduce` step 4: where the project has an evidence helper, it writes the files and the manifest, and the agent never writes a manifest by hand beside it, which would overwrite the helper's.

---

## 2026-11-20: The factory warns when browser.stages lists implement without execute; with-browser defers to a project's helper

**Origin:** The pilot project, before listing its browser stages. CD chose the warning and the comment fix.

**Changes made:**

1. **`bootstrap.py`, `tests/test_bootstrap.py`** — An implement run asks for the browser route as `execute` when it's given a plan, and as `implement` when it isn't (`templates/factory-implement.yml`). So `browser.stages` listing one without the other silently leaves half those runs without a browser. `bootstrap.py` reports that as a problem naming the stage to add, and reports both listed as ok.
2. **`process/factory.md` (Enablement, the browser's step 4) and `bundles/factory/seed/factory.json`'s `browser._doc`** — say the same at the point of listing. The seed reaches new installs only.
3. **`with-browser`** — its header said a script of the agent's own connects with `chromium.connect()`. Now: unless the project opens its browser contexts through a helper of its own, whose routes (an allowed host's `context.route`) a bare `connect()` would skip. This matches the browser block v2.9.0 already corrected.

---

## 2026-11-20: The factory's browser route: a project helper may serve an allowed host, and smoke proves that path

**Origin:** The pilot project, proving its card-art route helper through the browser host and a real sandbox. It sent four notes, and CD chose all four.

**Changes made:**

1. **`process/factory.md` (the `factory-browser` mirror and its copies in `sdlc-implement`, `sdlc-revise` and `sdlc-reproduce`; D6 rule 6)** — An allowed outside host is served by "the spec, or the project's helper its specs use". Before, the block a stage passes to its agent word for word said the spec serves it itself, which contradicted a project that routes it in one helper.
   - New rule 6 bullet: a project rule that must bind the working agent goes in a file beside the code that the agent reads for itself, not only in the orchestrator's prompt. A verbatim block reaches the agent unchanged, while a project rule may reach it only as a summary.
   - Rule 6's egress weighing now says what an exception opens: the whole of `<host>:443`, to every sandboxed command, with any method, headers and body, not only request URLs.
2. **`browser_probe.mjs`, `browser_check.py`, `templates/factory-smoke.yml`, `tests/test_browser.py`** — `factory-smoke`'s `browser-host` job checks that Node's `fetch` reaches the project's first `browser.allow` host, through the sandbox's proxy in the agent run. That's the path a `context.route` helper depends on: before, smoke proved only refusals.
   - Any HTTP status counts.
   - It sends one `HEAD` request per run, which rule 6 now says.
   - The job reads the host from `factory.json`. With none allowed, the probe must say so; a probe that reaches a host anyway, or another host, fails.
   - It's unproven against the real proxy until a project's next smoke run.
3. **`bundles/factory/seed/factory.json`** — the `browser._doc` lists `reproduce` among the stages that take the route (D6 rule 8 needs it there). Seeds are never overwritten, so this reaches new installs only; an installed project edits its own copy.

---

## 2026-11-20: Migration follows the project's marks: a deliberate change to a framework file is marked [contract-change]

**Migrating to this release from an earlier one:** the installed `sdlc-migrate` runs the migration, and an installed copy from before this release still follows the old rules: it adds back every top-level upstream knowledge key the project lacks (so an entry removed on purpose returns), and it moves `source_version` past the change, so the next migration can't see it. Tell the migrating session to follow this release's `sdlc-migrate` (its `SKILL.md` and `references/`) and process docs, read from the z-sdlc source at this release's tag, instead of the installed copy. That leaves nothing on disk for drift detection to ask about. **A session reading this at its changelog gate while following an older installed copy:** stop following that copy now (Phase 1 has written nothing to the project), and start again from Pre-Flight with this release's `sdlc-migrate` and process docs, read from the z-sdlc source at this release's tag. From this release on, migration follows the release's own rules by itself (Pre-Flight 1c).

**Origin:** CD directive: "the merge rules should be looking for project markers to see a project's deliberate change, meaning that projects making changes to framework files should be marking their changes as such."

**What happened:** The merge rules guessed a project's intent from its files instead of reading it. Knowledge YAMLs merged key by key, keeping the project's version of every existing key (so upstream's fixes never landed) and adding back every upstream key the project lacked (so an entry removed on purpose came back: the pilot's Deep Verify sweep removed 29 upstream entries, 16 of them top-level keys in files upstream still has). Dual-audience skills merged additive-only, so upstream's fixes to their existing sections never landed either. And markers could only add: a replacement of upstream text, or a removal, had no form. A diff against the last release can find a change, but it can't say the change was meant. A mark does, once, for every migration after. A dry run on the pilot's real files shaped the target grammar.

**Changes made:**

1. **`process/project-section-markers.md`** — A project marks every deliberate change, and migration follows the marks. New § The Three Kinds of Change: an addition (the `PROJECT-SECTION` block), a replacement (``PROJECT-SECTION-START: <label> replaces `<target>` ``) and a removal (``PROJECT-SECTION-REMOVED: <label> `<target>` — <why>; <who>, <date>``). New § Target Grammar:
   - Targets are quoted in backticks. A Markdown target is a heading's section, counting only headings outside code fences. A YAML target is a dotted key path, or `key[field=value]` for a list item, with any field unique in the list (writers prefer `id`, `rule_id`, `key`, `name`). `*` is the whole file.
   - Targets don't overlap.
   - What text a YAML unit holds: comments just above the next unit belong to it. Comments outside marks and Markdown separators follow upstream. Units are compared by parsed value, not order. A project's unit stays after the one it followed.
   - `last_updated` takes the later date.
   - A project's ids in an upstream list carry a project prefix.
   - Marks inside code fences are examples.
   
   Knowledge YAMLs' upstream entries and `CLAUDE.md`'s SDLC sections now need marks. Project-set values need none: filled placeholders, the project's agent names, resolved guards, the SDLC root choice and `spec_relevant`. What Markers Can't Hold shrinks to frontmatter. New labels `demote`, `fix` and `init`. New rules:
   - Rule 7: one mark per target.
   - Rule 8: a live mark is a whole line outside code fences, so prose and tables can quote marks.
   - Rule 9: inside a `*` replacement nothing more is marked.
   
   An ORPHAN is shown with its likely renamed target. A mark on a never-upstream unit is dropped quietly. The auditor's validation list follows the grammar.
2. **`skills/sdlc-migrate/SKILL.md`** — The marks decide, everything unmarked follows upstream, and nothing unmarked is replaced before CD answers.
   - Deviation detection (§2.1c) and the mark review (§2.1d) run in Phase 1, after the drift gate and before the point of no return. They cover the files Phase 2 will write. A drifted file's drift decision is its deviation decision, and a re-applied hunk is written as a mark.
   - Answers are logged with what Phase 2 needs to write each mark (`deviation_decision`, `marker_review_decision`), and the point-of-no-return checks require them. A headless run collects every question into one `needs-input` stop, with nothing written. The agent-memory gitignore step moves to Phase 2 (§2.1f).
   - Before diffing, §2.1c sets aside project-set values, `BUNDLE-SECTION` blocks, what marks cover, and an adapter's transforms.
   - The source clone keeps history (`--filter=blob:none`, not `--depth=1`), since the baseline is now read for every file. A legacy SHA install's baseline is the SHA itself (or `source_version_sha`).
   - §4.4's audit is told which differences this run's decisions expect.
   - Phase 2 writes only the files the Phase 1 pass checked: upstream changed or added them, or (a plugin guide) they differ from the release's with marks set aside. A file outside that set keeps its unmarked changes until a release changes it, and the audit reports them meanwhile. The replay found that §2.1's unfiltered copy list would otherwise overwrite them unasked.
   - Deviations are answered per section, with each proposed mark shown to confirm. Separators set aside before diffing. The headless §1.2 summary joins the one stop.
   - §2.1c covers every merged file: knowledge YAMLs, dual-audience skills and their references, and `CLAUDE.md`'s sections. It shows removals as removals and asks about each difference when there is no baseline. A knowledge file an adapter handles is left to the adapter.
   - §2.1 leaves out what a replacement or removal names. The orphan warning uses the file's own comment syntax.
   - §2.1b is a marked merge, recursive, as a text edit, with a table read top down. An upstream file the project lacks, if upstream changed it, is asked about and never copied back silently. Playbooks lose their git-blame guess.
   - §2.1d always compares a replacement or removal with its target, whatever its age, and no longer re-flags `deviation-` marks.
   - §2.2 Step 0 and §2.4: dual-audience skills, `sdlc-audit` included, merge by their marks. §2.2's preserve list is cut to project-set values.
   - The report gains Deviations, knowledge marks to review, knowledge conflicts, and which copy's rules ran.
   - New red flags against guessing intent from a diff. New log events: `marker_dropped`, and a widened `marker_preserved`.
   - New Pre-Flight 1c follows the release's own `sdlc-migrate`, and always reads the process docs it follows from the release. A file identical to the release's isn't drift.
3. **`skills/sdlc-migrate/references/marker-review-findings.md`, `red-flags.md`** — Target findings: changed upstream is `REVIEW`, gone is `ORPHAN`, and a unit both sides added is `CONFLICT`. What keep, update, remove and merge mean for a replacement and for a removal. The 7-day skip applies only to additions.
4. **`agents/sdlc-compliance-auditor.md`, `agents/sdlc-reviewer.md`, `skills/sdlc-audit/references/compliance-methodology.md`** — Validate `replaces` targets and `PROJECT-SECTION-REMOVED` lines (one target each, named once) across `[sdlc-root]/`, `.claude/skills/` and `CLAUDE.md`. 7c treats a marked target's absence as the project's choice.
5. **`skills/sdlc-audit/references/deep-verify.md`, `improvement-methodology.md`** — A Deep Verify demotion leaves a removal mark. The payload and removal scripts address items (`key[field=value]`) and dotted paths. The payload names an item only by a unique field, and skips a file whose top level isn't a mapping. The removal script:
   - writes the mark and keeps the next entry's banner;
   - handles lists at their key's indent, trailing comments and wide dashes;
   - warns when it empties a list;
   - refuses an ambiguous target, or one inside a marked block;
   - writes no mark inside a `*` replacement.
   
   Both scripts were tested on copies of two shipped knowledge files and on those edge cases. An improvement that corrects framework text marks it as a replacement until upstream has it.
6. **`skills/sdlc-ingest/SKILL.md`, `skills/sdlc-develop-skill/SKILL.md`, `skills/sdlc-initialize/SKILL.md`** — Ingest marks a rewrite or removal of an upstream entry, and prefixes its ids in a shipped file. Modify mode's M3 offers a marked replacement or removal, with snippets. The installer marks a knowledge file it customizes for the stack as a replacement of `*` (6a), and 6c's agent is told to.
7. **`process/factory.md` and its mirrors in `sdlc-implement`, `sdlc-revise` and `sdlc-reproduce`, and `bundles/factory/tree/templates/factory-implement.yml`** — A factory stage marks an existing knowledge entry it corrects or removes, unless the run added it.
8. **`CLAUDE-SDLC.md`** — New § Marking Changes to Framework Files, so a session editing one outside any skill knows the rule.
9. **`process/path-mappings.md`, `process/adapter-lifecycle-protocol.md`** — Dual-audience skills: marked merge, not additive-only. The `knowledge-update` phase's default is the marked merge.
10. **`skeleton/contract_changes.yaml`** — Entry 0021 (`other`).
11. **`.claude/skills/zsdlc-audit-adapter-installation/references/classification-framework.md`** — A section a replacement stands in for, or a removal names, is absent by the project's marked choice.

**Rationale:** Intent belongs in writing, where the project put it. Upstream's fixes now reach every unmarked entry and section. A deliberate override survives every migration and still shows upstream's later changes to what it set aside. Nothing unmarked is lost silently, because deviation detection asks first. Each unmarked change is asked about once, at the first migration whose release changes its file. On the pilot, the unmarked changes are about 34 knowledge units across all its files (50 less 16 that were only `last_updated`, which no longer needs asking), 3 `CLAUDE.md` sections, and nothing in the dual-audience skills. A migration asks only about those in files its release changed, and writes no other file. Two read-only replays of the new Phase 1 on the pilot each ended at one decision point: the second held four questions (the summary, `CLAUDE.md`'s four sections, and the two execute skills' Integration line, which this release changes).

**Then, at CD's direction:**

- **Deleted files are recorded in the manifest** (CD: "deleted files should be maintained thru the manifest field"). `.sdlc-manifest.json` → `declined_files` maps a declined file's installed path to `{why, decided}` (contract 0022, `manifest_field_added`, default `{}`); `process/project-section-markers.md` § Deleted Files defines it.
  - `sdlc-initialize` writes it when 6a removes a knowledge file.
  - `sdlc-migrate` writes it when CD keeps a deleted file deleted (§2.1c, any file type). A declined file is never drift, never copied back, never asked about and never wired into the context map. The report lists upstream's changes to one. The record moves or goes when upstream moves or deletes the file (§2.1a, §3.3, §4.5 4b, §4.6).
  - The auditor's file-completeness check treats a declined file as declined, not missing.
- **Older gaps, fixed with this change:**
  - Added table rows are an addition block inside the table (a renderer splits the table; agents read the source). The dateless `agent-wiring-<agent>` label is in the label table.
  - Discipline files' framework sections follow the marks, while their project data (parking-lot entries, `## Project Context`, `## Active Questions`, the tracker) is kept whole and set aside before diffing (§2.3, §1.3, the markers table, `sdlc-execute`, `sdlc-lite-execute`, `improvement-methodology`). Before, the markers doc said those files were never overwritten while §2.3 updated their framework sections word for word.
  - "Proceed with migration?" moves to the Phase 1 decision point, with every drift, deviation and mark question, for interactive and headless runs alike.
  - The changelog gate reads the entries this release adds by comparing headings at the two refs (changelog and archive), not by date.
  - "Never use bare `HEAD`" now holds while a release tag exists; only a source with no tags falls back to it, and says so.
- **From the second replay:**
  - Headless, the Phase 1 decision point is the approval gate `headless-mode.md` already names for migrate's change plan: `awaiting-approval`, with the plan in full, not a batched `needs-input`. `headless-mode.md` lists it.
  - The decision point's message format is defined. Phase 2's leftover "ask" steps now apply logged decisions.
  - Blank lines beside marks are set aside, and re-injection anchors count only non-blank lines.
  - `SDLC-END` goes after adapter-written lines at the end of the last SDLC section.
  - A framework file the project lacks (in `source_files`, not declined) is asked about once, whether or not the release changed it: keep it removed, recorded with CD's why (`keep_removed`), or restore it. That is also how a file CD un-declines comes back. A bundle file is copied back, since a bundle is declined whole. An absent field reads as empty. Keys are installed paths, mapped per `path-mappings.md`.
  - §2.3: the status line is project-assessed, parking-lot data is bounded per `## Parking Lot`, and a seeded entry the project removed isn't re-added.
  - Subdirectory knowledge READMEs are listed.
  - §4.5's steps are in order.
  - §1.3 gains rows for framework agents, playbooks, examples and READMEs, bundle files and declined files. Its Skills row is limited to the manifest's skills.
  - `CLAUDE.md`'s SDLC region is bounded by `SDLC-START`/`SDLC-END` lines, which the installer now writes with the content word for word. Without them, a section counts as SDLC when its `##` heading matches `CLAUDE-SDLC.md` at either ref, and Phase 2 then writes the lines.

**Adapter pairing:** neuroloom-sdlc-plugin makes the paired change:
- Its content-merge audits read the new marks, so a marked replacement or removal isn't a structural regression, and the marker audit counts removal lines.
- `knowledge-seed` and `knowledge-update` honour `declined_files`, and no longer re-seed a knowledge file a project removed from its workspace.
- Its `adapter.json` supports 2.9.0.

A seeded entry a project edits in the workspace is still protected only by the adapter's `sdlc:project-specific` tag, not by a mark.

---

## 2026-11-20: The factory:needs-repro label fits GitHub's limit

**Origin:** the pilot project's `bootstrap.py --apply` after migrating to v2.8.0. GitHub refused `factory:needs-repro` (HTTP 422): its description was 101 characters, one over the 100 GitHub allows.

**Changes made:**

1. **`bundles/factory/tree/bootstrap.py`:** the description is shorter (84 characters).
2. **`bundles/factory/tree/tests/test_bootstrap.py`:** every factory label's name, description and colour is held to GitHub's limits (50, 100, six hex digits), so a new label can't ship one bootstrap can't create.

**Rationale:** `bootstrap.py` compares descriptions, so a project can't work around a label it can't create without the check reporting drift.

---

## 2026-11-20: A verify exception for the factory too says so in its entry

**Origin:** the pilot project's v2.8.0 migration review. The verify skill's template said an exception recorded in Recorded Exceptions "doesn't carry over" to the factory's runs. That read as contradicting D6 rule 6, which says CD records a factory exception in that same section, and the pilot's CDN exception is one.

**Changes made:**

1. **`skills/sdlc-develop-verify-skill/references/generated-skill-template.md`, `process/verify-command.md` § Companion:** an exception recorded for interactive verify doesn't carry over to the factory. One CD makes for the factory too says so in its entry, and CD also records it in the factory's allowlist (`browser.allow`).

**Rationale:** the same section holds both kinds of exception. Only an entry that names the factory reaches the factory.

---

## 2026-11-20: The factory reproduces a bug the code can't confirm before planning it (D6 rule 8)

**Origin:** CD's decision (2026-11-20): triage stays code-only, flags `needs-repro`, and a short reproduce job on the strict tier writes the failing spec before a plan. In the pilot project, triage left 4 of 16 issues unreproduced, and half of its plan PRs were UI work built on unconfirmed causes. CD confirmed the shape the same day: a mode of the implement workflow, which needs no change to the runner group's selected workflows, where a workflow of its own would.

**Changes made:**

1. **`process/factory.md`:** D6 rule 8, the `factory:needs-repro` label, and `sdlc-reproduce` in the installed skills and both browser mirrors' copies.
2. **Triage:** `sdlc-triage` step 7b and a `needs_repro` flag in `triage.schema.json`, for a web-app bug headed for a plan whose cause the code didn't confirm. The apply job decides the route from the default branch's `factory.json` (a browser host and `reproduce` in `browser.stages`), never from the agent. It adds the property label `factory:needs-repro` (`bootstrap.py`, § Labels, `report.sh`'s properties), clears it when it no longer flags the issue, and warns rather than stops when the label doesn't exist yet. It then dispatches the implement workflow with `reproduce`. Without the route, it starts the plan as before, saying the cause is unconfirmed.
3. **New skill `sdlc-reproduce`** (headless, in the bundle's skills). It writes the failing spec through the route, commits nothing, and returns `reproduce.schema.json`.
4. **The implement workflow's `reproduce`, `reproduce-report` and `reproduce-failure` jobs;** the implement, publish, report and report-failure jobs step aside. `reproduce_report.py` (the writer) checks the result and posts it on the issue: the outcome, summary, what was tried and failed requests as escaped text, the spec in a fence the writer picks, and the evidence links. It refuses a spec with bidirectional or invisible control characters, and posts a spec too long for the comment by pointer. It then starts the plan, but only for an issue still waiting for one, or asks CD (`needs-input` with a `reproduce` stage marker). Resume restarts it, with a failure hint that fits a reproduce retry, and `factory:go` starts it for a held issue that carries the label.
5. **The tier readers in the plan stage and `factory:go`** take a triage marker only from a comment's leading block, as D1 rule 5 says. A review found that a marker in a reproduce spec, the first agent text posted raw in an App comment, could otherwise set the plan's tier.
6. `browser.py` takes `reproduce` as a stage, and `run_metrics.py` takes the stage and its outcomes. Tests: `tests/test_reproduce.py`.

**Rationale:** the plan starts from a failing spec rather than a guess, and the stage that can't run app code (planning reads production data) never has to.

---

## 2026-11-20: The factory's browser evidence reaches the PR, and an archive keeps it (D6 rule 7)

**Origin:** CD's decisions on evidence (2026-11-20): CD sees it through links the writer job builds; GitHub keeps it 90 days and then an archive on the runner host's redundant storage, "so it's never gone"; video for reproduce and verify runs; annotated video where Playwright has the screencast API.

**What happened:** a stage's screenshots, video and trace come back through the browser host's front end to the client (tested 2026-11-20), but the agent's files can't go to a PR as they are: an agent-chosen file or link is a way out, and D2 rule 3 refuses images and embeds in agent text.

**Changes made:**

1. **`process/factory.md`:** D6 rule 7. The agent writes only `.factory/evidence/`, with a manifest. Frozen code packs it after the agent, each file goes up unzipped, the writer builds the links, and the archive keeps it after 90 days. D2 rule 3: a writer job's own links to its run's artifacts are the one link it adds outside agent text. Enablement step 14.5 installs the archive.
2. **The bundle:**
   - `evidence.py` packs `.factory/evidence/` after the agent and quiesce. It reads only manifest-listed regular files, follows no link, and writes screenshots again from their image data alone, checking a palette's size. It keeps one video, and one trace written again entry by entry, stored or deflated only. A bzip2 entry unpacked 785 bytes to 1 GB in a reviewer's test. It enforces the caps and writes a report that runs no script. Every name and reason it prints or records is escaped, so a newline can't start a workflow command, and a crafted file costs only itself. It records the issue and run from the job's own environment.
   - The implement and revise jobs upload the report, video, trace and `evidence.json` as their own unzipped artifacts for 90 days.
   - `implement_guard.py` renders a Browser evidence section in the PR or revision comment. Its links are built from the run's URL and ASCII-digit artifact IDs, the archive path comes from `factory.json`'s new `evidence.archive`, and the manifest goes in as escaped text, capped at 12,000 bytes. A record of the wrong shape degrades to one line rather than refusing the publish.
   - `workflow_policy.py` holds an agent job's uploads to the runner's temp directory or an execution file, read case-insensitively as GitHub does. Only the packed evidence goes up unzipped, and an `archive` that isn't a literal true counts as unzipped.
   - `host/evidence_archive.py` pulls each run's evidence into `<root>/<repository>/<issue>/<run>/`, never overwriting. It takes only this repository's implement and revise runs on the default branch that were started as the factory starts them and weren't skipped. It reads every page within 90 days, keeps a list of runs it has finished with, and lets one bad run cost only itself. It takes an artifact's file bare or in a zip, since the download of an unzipped artifact isn't documented. `host/setup-archive.sh` installs it with root under a user of its own on a systemd timer: the token is read without echo, and a system directory, a link or a path with odd characters is refused.
   - `render.py` counts the `evidence` block as read at run time; the seed's `evidence` block is off by default, and `import.json` marks it optional.
   - Tests: the packer, the PR section, the upload rule and the record's issue and run in `tests/test_browser.py`, and `tests/test_evidence_archive.py` against a stand-in API.
3. **`process/verify-command.md` § Companion, `skills/sdlc-develop-verify-skill/`:** the shared evidence layout, a `manifest.json` with each file's step, what it shows and whether it shows the bug. It names a file by its path in the run's folder, since the verify skill keeps per-feature subfolders; the factory's is flat. The skill's proof, teardown and maintain checks look for it, and so do its template, worked example and review checklist. "Evidence survives cleanup" names it, so each project's verify skill picks it up on its next maintain run.

**Rationale:** evidence crosses the boundary only through frozen code that checks what it is, and only the writer makes links. So the agent can't use the PR as a way out, and CD gets the screenshots, video and trace a click away.

---

## 2026-11-20: The factory's browser route: a stage drives a real browser on the browser host (D6)

**Origin:** `docs/current_work/ideas/factory-browser-repro_handoff.md`. CD's decisions (2026-11-19/20): the browser runs on a dedicated browser host with a GPU, the strict tier gets its first network opening for it, nothing relies on it until smoke passes, offline by default, and it's built for the pilot project first. The pilot project's session reviewed the design against its own end-to-end setup. It also proved, by hand on the runner host in the same sandbox, that the pilot's own servers build, migrate and start inside it and that two of its specs pass through the route. That run is the source of the protocol's points on one spec at a time, `page.clock`, timeouts, the project's own fixtures, and a code-owned script for what its servers need before they start.

**What happened:** the code-writing stages couldn't see a web app run, so a UI bug was "fixed" from code alone. The browser host was built and proven by hand on 2026-11-19/20. The handoff left open whether a Playwright client inside the factory's real sandbox, which reaches out only through its HTTP proxy, could drive it. It can. The test ran on the runner host, in a container with the factory's seccomp profile and the sandbox runtime Claude Code's sandbox is built on (`@anthropic-ai/sandbox-runtime` 0.0.83), using implement's settings plus one `allowedDomains` entry: `<address>:<port>`, which Claude Code 2.1.316's own sandbox also honours as one port.
- The client loaded an app on the sandbox's own loopback, WebSocket included, with WebGL on the host's GPU, and got a screenshot, a trace and a video back.
- The outside world and context proxies were refused. An unsandboxed control reached the outside world through the same tunnel, which shows the refusal is the sandbox's.
- Against the pilot project's own install (pnpm's `@playwright/test` 1.61.1), `browser.py` found the client and its port, and the probe passed.

**Changes made:**

1. **`process/factory.md`:** a new design rule, **D6: Browser Host**, rules 1 to 6.
   - Where the browser runs, and the strict tier's one opening, narrowed by the sandbox to the project's Playwright version's port.
   - What the browser host must hold, and what proves it: the smoke job, and the host's own check for its outbound block and DNS, which smoke can't see.
   - Absence is reported as `UNAVAILABLE`, never guessed.
   - Offline by default, with the five kinds of outside connection, the verify skill as the one list, and no outside hosts to start. The reviewed allowlist `browser.allow` covers the exceptions: one plain hostname per entry, with why and who decided it. CD made the first exception the same day, the pilot project's card-art CDN.
   - D2 rule 2's empty `allowedDomains` gains the route as its one exception. Stack Profiles says how a stage runs the project's own Playwright, and the stages' sandbox mirror names the route.
   - A new § Reproducing in a browser holds the stage protocol: the failing spec first, kept as `repro-<issue>-<slug>.spec.ts`; the four outcomes; failed requests listed; a helper agent drives; one spec at one worker; `page.clock` over wall time; and a timeout alone isn't a reproduction.
   - Enablement step 14 and an After migrating item cover setup.
2. **`skills/sdlc-implement/SKILL.md`, `skills/sdlc-revise/SKILL.md`:** both mirrors. A bug a user sees is reproduced in the browser when the stage has the route, and `verification` names the spec, its outcome and its failed requests. "Step 0.5 has no browser here" now applies only without the route, and `sdlc-revise` Step 5 says how Step 0.5 runs.
3. **`skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`, `process/review-fix-loop.md` Step 0.5, `CLAUDE-SDLC.md` § UI Verification:** a factory run has no MCP browser. Its UI checks go through the route, or are reported as not run. `process/factory-runbook.md` § 3.5 names the new smoke job.
4. **`process/verify-command.md` § Companion and the verify skill's template:** the verify skill is the project's one list of outside connections, which the factory holds more strictly.
5. **The bundle (`bundles/factory/tree/`):**
   - `with-browser` forwards a loopback port through the sandbox's proxy to the front end and points Playwright Test at it. It composes with `with-test-services`, and says `UNAVAILABLE: browser host (<why>)` and exits 75 when there's no route, or no answer.
   - `browser.py` reads `factory.json`'s new `browser` block. It refuses a host that isn't a private or tailnet address, since only those get the firewall's say. It finds the project's installed Playwright, adds `<host>:<port>` and each allowed host to the stage's sandbox settings, and writes `/opt/factory/browser.conf`. `agent_job.sh browser` runs it, and `workspace` installs the wrapper.
   - The implement and revise workflows call it before their sandbox settings are final, and execute's prompt names the route.
   - `factory-smoke` gains a `browser-host` job: an unsandboxed control holding a canary credential, then the agent probe in implement's own sandbox. The probe is `browser_probe.mjs`, judged by `browser_check.py`. It checks:
     - the app, its WebSocket and the GPU, and that the evidence comes back;
     - the forced flags, and a hostile client's own browser and launch options replaced;
     - the outside world and context proxies refused;
     - no run-server WebSocket opens on the host's loopback, against a control showing loopback answers;
     - the browser host's next port refused by the sandbox, and no credential visible.
   - `host/setup.sh`: the strict tier's opening (`STRICT_BROWSER_HOST`, `STRICT_BROWSER_PORTS`), before the private-range rejects. It is a private or tailnet address only, never the host's own, with a strict port pattern. The loaded rule is read back, and the browser host's other ports and the ports past each end of the range are probed. Real `nft` loaded the ruleset in a throwaway network namespace on the runner host, and a widened rule failed the read-back.
   - Playwright's tunnel connects from the client without the proxy, so a spec serves an allowed host's requests itself with `context.route`, fetched through the proxy. `with-browser` exports `NODE_USE_ENV_PROXY` and the hosts for that. On the runner host an allowed host answered through the proxy, another was refused, and the client still connected.
   - `render.py` counts the `browser` block as read at run time.
   - Tests: `tests/test_browser.py` (route, wrapper, verdict, and the smoke job under the policy), and `tests/test_host_setup.py` for the opening.
6. **`bundles/factory/seed/factory.json`, `seed/host/host.conf`:** the `browser` block (off by default) and the two `host.conf` settings, commented. `zsdlc-import-factory`'s `import.json` marks the block optional, since the incubator doesn't use it yet.

An outside review found smoke claiming more than it proved: the loopback check had no control, no hostile client was tried, and D6 promised a firewall safety net for any address. Those are the checks and refusals above. No `contract_changes.yaml` entry: the block is optional and off when absent, and seeds are never rewritten. A project opts in with Enablement step 14.

**Rationale:** the route keeps D2's shape. The agent's sandbox still has no way out but its proxy, and the proxy now allows one more address and port. Everything else the browser could reach is closed on the browser host, by rules the smoke job and the host's own check prove. Absence reports `blocked`, so a stage never claims a reproduction it couldn't run.

---

## 2026-11-20: A factory feature can start where its workload is

**Origin:** planning the factory's browser-based bug reproduction (`docs/current_work/ideas/factory-browser-repro_handoff.md`). z-sdlc proposed building it in the incubator first, as the incubator rule (CD, 2026-10-12) says. CD: the incubator first "seems counterintuitive considering its workload is nothing like" the pilot project's, so build it in the pilot project "then import". The pilot project runs WebGL end-to-end suites, two browsers to a duel; the incubator has no Playwright at all.

**Changes made:**

1. **`CLAUDE.md`** (the incubator rule): a feature whose workload the incubator doesn't have is built and proven in a project that installed the bundle and has it. It then goes into `bundles/factory/tree/` the way a fix found in such a project does, and the import hands it to the incubator.
2. **`.claude/skills/zsdlc-import-factory/SKILL.md`:** the same in the skill's opening, which already describes how the import keeps a pilot fix and copies it to the incubator.

**Rationale:** a feature proven where its workload doesn't exist proves little. The import already carries a project's change into the bundle and on to the incubator, so the only change is what may start in a project: a feature now, as well as a fix.

---

## 2026-11-19: The factory's code stages prove a bug before fixing it

**Origin:** CD compared the factory with another team's agent workflow, which makes a regression test that fails on the old code a rule for every fix. z-sdlc already had that rule (`CLAUDE-SDLC.md` § Bug-Fix Rule, `sdlc-lite-plan`'s bug-fix phase), but the factory's `sdlc-implement` and `sdlc-revise` never carried it: neither dispatch told the fixer it was a bug fix, and neither asked for the failing run, so a PR could show a passing test that had never failed.

**Changes made:**
1. **`skills/sdlc-implement/SKILL.md`:** step 3 dispatches a bug with the Bug-Fix Rule (reproduce, smallest test that fails on the unfixed code, then fix, with the failing run quoted and redacted; the closest check, and why, when a test isn't practical). Step 4 confirms the report quotes the failing run before the checks, has the fixer produce it if not, and says plainly when none could fail first. The brief's `verification` carries it, and Red Flags gets a row.
2. **`skills/sdlc-revise/SKILL.md`:** the same for a request that reports a bug, in steps 3 and 4 and Red Flags.
3. No schema change: the evidence goes in the brief's existing `verification` entries.

**Rationale:** a bug-fix test that passes on the unfixed code proves nothing, and CD reviews from the PR's description. The orchestrator still never edits code, so it checks the report and sends the fixer back rather than producing the evidence itself. The incubator's copies of both skills need `zsdlc-import-factory --to-incubator` (not run).

---

## 2026-11-18: The smoke check stops looping and reads its triggers from the verify skill; review dispatch and the round cap

**Origin:** Eight notes from a project's session, from the follow-ups after its v2.7.0 migration, sent at CD's request for z-sdlc to triage.

**What happened:** Each note was checked against z-sdlc's files:
- **Already in z-sdlc:** the Recorded Exceptions section and the zsh guidance, which went in with the previous entry, and the rules against putting markers inside a Markdown table and against reusing a marker's label, already in `project-section-markers.md` (§ What Markers Can't Hold; rule 2).
- **Ported here:** these problems.
  - The UI smoke check re-dispatched a launch failure with no limit, including one the phase couldn't fix, such as a stopped container runtime.
  - Its file patterns missed UI outside them, such as a plain-TypeScript client.
  - The verify template didn't say what a local run can't prove.
  - Its port and cleanup advice let a port the browser refuses pass a curl health check, and let a reused process ID be stopped.
  - A reviewer without a shell couldn't read the diff it was given.
  - The round cap offered CD nothing between stopping and proceeding.
  - A parking-lot entry promoted to a test had no ledger format.

**Changes made:**
1. **`process/verify-command.md` § Companion** states the contract the UI smoke check reads from a project's verify skill:
   - The launch prints `UNAVAILABLE: <what>` for a missing prerequisite outside the repo. The smoke check skips on it only when the app needed that prerequisite before the phase.
   - An optional `## Smoke Trigger Paths` section adds paths to the default patterns and takes precedence over the backend-only skip. CD sets it, maintain never changes it on its own, and it isn't derived from the feature map's `Source:` lines, which also name backend files.
2. **`sdlc-execute`, `sdlc-lite-execute`, `knowledge/testing/advanced-test-patterns.yaml`:**
   - The smoke check reads both.
   - A smoke failure that survives a third attempt goes to CD with each attempt's output (the 3-strike rule). It is never turned into a skip, since the step exists to stop work building on a broken render (headless: `escalated`).
3. **`sdlc-develop-verify-skill`:**
   - The template's launch prints `UNAVAILABLE:` and picks a port browsers allow, and for a browser-driven surface the health check loads a page through the browser.
   - Each process ID is recorded with its start time (`ps -o lstart=`), and cleanup stops a process only while that time still matches. The Tally example does this.
   - New template sections: **Out of Reach** (what no local run can show, as distinct from Unproven and `unreachable`) and the optional **Smoke Trigger Paths**.
   - CREATE step 1 asks what only production shows, and step 3 fills both sections. MAINTAIN's source readers return UI paths neither the defaults nor the list match (`ui_paths_uncovered`), and MAINTAIN reports them without changing the list.
   - The review and helper prompts check `UNAVAILABLE:` and the start-time match.
   - The Safety Rule on stopping says "only while it is still the same process", so the next maintain run updates every project's copy, and its review checks the Cleanup against it.
4. **`process/review-fix-loop.md`:**
   - **Reviewers without a shell (Step A):** a reviewer whose tools don't include Bash gets its diff in a file outside the working tree, since a file inside the tree would be staged with the work. `headless-mode.md` counts such a scratch file as local work.
   - **§ Round Cap:** CD can now pick one targeted check after the open findings are fixed. A fresh reviewer reads only the diff from round 3's state to now, and its findings go to CD. It is not a fourth round, and a headless run never takes it.
   - **`process/skill-agent-review.md`:** says the same about `sdlc-reviewer`, which has no shell.
5. **`process/discipline_capture.md`:** an entry can be promoted to a fitness function, a committed test that enforces it, written ``Promoted → `path/to/test` (fitness function)``. CD still approves it. Instead of the verification panel, it must fail without the behavior it enforces and pass in CI.
6. **`process/headless-mode.md` § Integration:** the smoke check's new stop, in both execute skills.

**Policy for CD:**
- A persistent smoke failure now stops for CD rather than looping or skipping.
- A verify skill can widen the smoke check's triggers.
- The round cap gains an option CD can pick.

**Rationale:**
- **Smoke loop:** a check that can't tell "the phase broke it" from "the machine can't run it" either loops on the second case or learns to skip the first.
- **Trigger paths:** the project says where its UI is, but its feature map isn't that list.
- **Targeted check:** at the cap, the cheapest useful next step is to read exactly what changed after the last round.

Release type: minor (a new optional section and output line in the verify skill that the execute skills read).

---

## 2026-11-18: The verify skill keeps CD's exceptions to its Safety Rules, and migration checks its base first

**Origin:** Two notes from a project's session, from adopting its hand-written verify skill through `sdlc-develop-verify-skill` and from its v2.7.0 migration.

**What happened:**
- **Verify skill:** CD made one exception to the Safety Rules for that project's app: the browser reads static assets read-only from a public CDN that no local copy can stand in for. The skill had nowhere to record it. Written inside the generated skill's Safety Rules section, it would have been deleted by the next maintain run, since MAINTAIN step 1 replaces that section whenever it differs from `references/safety-rules.md`. The project's step-6 reviewer caught it.
- **zsh:** the same run found that recipes an agent runs on macOS run under zsh, which doesn't split an unquoted variable into words. Checked here: with `x="a b"`, `set -- $x` gives zsh one argument and bash two. zsh also stops on a glob that matches nothing.
- **Stale base:** the migration ran on a branch cut from a local default branch nine merges behind its remote. That branch had already landed its own framework-file edits. Drift detection and the three-way merges compared against the old tree, part of the migration repeated work, and the PR conflicted in 25 files. GitHub runs no `pull_request` workflows on a PR with merge conflicts, so CI never ran, and only `mergeStateStatus: DIRTY` showed it.

**Changes made:**
1. **`sdlc-develop-verify-skill`**:
   - § Safety Rules: exceptions are CD's alone. Each goes in the generated skill's new **Recorded Exceptions** section, naming the rule, exactly what it allows, why, and who decided it and when. Stopping, secrets and evidence take no exception.
   - Adopt and CREATE step 3 write the section; the Troubleshooting row launches against an unlocalizable target only under a recorded exception.
   - MAINTAIN step 1 keeps the section, or adds it saying none, and reports an incomplete entry to CD. Text found inside Safety Rules besides the rules is shown to CD before the replace: an exception CD confirms moves to the new section, and the rest goes. A stray edit never becomes an exception on its own.
2. **`references/generated-skill-template.md`**:
   - The Recorded Exceptions section, after Safety Rules.
   - Launch steps 3–4 and the Health Check accept a target under an exception only where its entry says.
   - Shell guidance: write commands to run alike under zsh and bash, and put anything that needs word splitting or loose globs in a bash helper script.
3. **`references/dispatch-prompts.md`:**
   - The review prompt checks each exception entry, and checks that nothing goes beyond its entry. It doesn't judge CD's decision.
   - It also checks that commands run alike under both shells.
   - The helper-script prompt reads Recorded Exceptions and asks for a bash shebang.
4. **`references/safety-rules.md`:** its header says where exceptions live.
5. **`sdlc-migrate`:**
   - Pre-Flight step 0 fetches and counts how far the branch is behind `origin/<default>`. When it is behind, it asks CD to update first or go on (headless: `needs-input`). When it can't check, the assessment says so.
   - The report's Next Steps say to check a migration PR's `mergeStateStatus`.
6. **`process/headless-mode.md` § Integration:** the two new gate sites.

**Policy for CD:** the Safety Rules had no exceptions before this. CD can now make one per app, recorded in that app's skill.

**Rationale:** A rule that has to bend for one app needs a recorded place to bend, or the bend lives where the next refresh erases it. A migration measures drift against the tree it runs on, so that tree has to be current.

Release type: minor (a new section in the generated verify skill, which projects write into their own files).

---

## 2026-11-18: The factory imported from the incubator (8f83385..664b097): the review fixes handed back

**Origin:** CD (2026-11-18): "commit and send to incubator", after the outside-review fixes below.

**What happened:** `zsdlc-import-factory --to-incubator` at the incubator's `8f83385` wrote z-sdlc's fixes to `factory-gate-request.yml`, `factory-release-pr.yml`, `factory-smoke.yml` and `tests/test_release_gates.py` into the incubator, which re-rendered its three workflows and took them in #147. Its render, workflow policy and factory tests passed there (811, 46 skipped). The import then read every bundle file in sync, and the proof passed: the incubator at `664b097` took the bundle unchanged, and an empty project rendered all 19 templates and passed the workflow policy and the tests.

**Changes made:**

1. `.claude/skills/zsdlc-import-factory/import.json`: `last_import` is the incubator's merge of #147, so z-sdlc's next change to these files no longer reads as changed on both sides.
2. No bundle code or seed changed: the range's only factory commit is the hand-back itself.

**Rationale:** Until the incubator took z-sdlc's copies and the import recorded it, the next z-sdlc change to any of them would have read as a conflict, and the proof would have installed the incubator's copies without z-sdlc's changes.

---

## 2026-11-18: An outside review of a project's v2.7.0 migration: four text fixes and four factory workflow fixes

**Origin:** The same project's v2.7.0 migration PR had a review by another vendor's model. The project's session sent the 13 findings that concern upstream text here to judge; it had checked four of them against the files.

**What happened:** Each finding was checked against z-sdlc's files. The four in core text hold. Of the nine in the factory bundle's workflows, five hold and are fixed here, three hold but need a decision CD owns, and one is a false alarm.

**Changes made:**
1. **Bug-Fix Rule** (`CLAUDE-SDLC.md`; `knowledge/architecture/debugging-methodology.yaml` § fix_discipline): the quoted failing run has secrets and personal data redacted. A failure message can carry a token, a connection string or a request's data, and a commit is permanent.
2. **`knowledge/architecture/security-review-taxonomy.yaml` § case_aliasing:** the one mitigation becomes two. Fold names to decide what to refuse, so an alias of a protected path is refused. Match as GitHub does (case-sensitive, last match wins) to decide what gets code-owner review: GitHub leaves an alias of an owned path unowned, so a folded match would call it reviewed. The factory's guard already did both (`protected` and `owner_on_github`, 2026-11-05 below); the knowledge text now says so.
3. **UI smoke skip** (`sdlc-execute`, `sdlc-lite-execute`, `knowledge/testing/advanced-test-patterns.yaml`): an occupied port is a skip only when it is the port the app used before the phase. A phase that moved the app to a port already in use caused the failure itself.
4. **`sdlc-status`:** a lite result left in `sdlc-lite/` is Complete when the catalog says Complete, which `sdlc-lite-execute` sets at its final commit and `sdlc-archive` step 2 cross-checks. Otherwise it is Executing, shown as Executing? when commits already name the ID. `sdlc-archive` takes a never-moved result, but status showed it as Executing forever. The project's suggested row repeated the Executing row's condition, so the row keys on the catalog instead.
5. **The factory bundle's workflows** (`bundles/factory/tree/templates/`), fixes found in a project that installed it:
   - **`factory-release-pr.yml`:** the open release PR is looked up with this repository's default branch as its head (`head=owner:branch`). `gh pr list --head` also matched a fork's branch of the same name, so a fork's PR into the release branch could be announced as the release PR. The release-marker check is `jq -e … contains`, not `jq | grep -q`: under `pipefail`, grep's early exit could kill jq on a long PR body and read as "doesn't release".
   - **`factory-gate-request.yml`:** a retry that finds the release PR already open runs the cleanup of stale release PRs and waiting gate runs too. Before, it returned first, so when the run that opened the PR failed during cleanup, stale release PRs stayed open, and merging one would deploy code the gate isn't at. Both listings of gate runs now paginate. New test `test_a_retry_that_finds_the_release_pr_open_still_cleans_up` fails on the old template.
   - **`factory-smoke.yml`:** the `mcp-services` job fails on a `services.json` that is missing or isn't `{"services": [...]}`, instead of reporting that it lists no MCP service. The `planning-sandbox` job already failed on such a file.
   - `import_factory.py --prove` passes in the incubator and in an empty project: every template renders, the workflow policy passes, and so does the whole factory suite. The incubator takes the changes with `--to-incubator`.

**Declined:** The finding that `factory-revise` and continued implementation run `services.py` from the PR's tree. `factory_branch.sh switch` lays main's `services.py` and `services.json` over the branch before that step (`test_factory_branch.py` covers it), and `check` refuses a branch that changes either.

**Open, for CD:**
- **Bypass actors on the pinned branches' ruleset.** The gate request checks rule types from `rules/branches`, which doesn't return bypass actors, so a ruleset with bypass actors passes there. `bootstrap.py` checks that the ruleset has none. Checking them in the workflow needs a token that can read the ruleset's bypass actors; whether the job's tokens can is unverified.
- **The smoke's left-out-tool probe** passes when the agent never tries the tool and the harness still lists it. Closing that means requiring either an attempt or the tool's absence from the init message's tool list. A real run must first show whether MCP tools always appear there.
- **`factory-release-pr`'s concurrency group** keeps one pending run, so a third merge in quick succession cancels the second's run. That PR then gets no link to the release PR, though its commits still ship in it. Per-PR groups would bring back two runs creating the same PR.

**Rationale:** An outside review sees what the authors stopped seeing, and calls some things wrong that aren't. Checking each finding against the files kept the four real core gaps and the five real workflow gaps, and left out the false alarm. Release type: patch.

---

## 2026-11-18: What a project's v2.7.0 migration carried back: fixes it had made to its copies of framework files

**Origin:** A project that installed z-sdlc migrated from v2.1.5 to v2.7.0 on 2026-11-18. Its own copies of framework files carried 44 edits in places v2.7.0 never touched, so after the migration they still differed from upstream. The edits came from a configuration audit and from the agent-format work already ported in the 2026-11-17 entry below. CD had that project's session send them here; z-sdlc decided what to adopt, generalize or decline. Each one is ported onto z-sdlc's current text, not copied.

**What happened:** Most of the edits were contradictions z-sdlc had left in its own text, and two of them were wrong when checked against the framework:
- **Four rows still said "Size is not an exception."** They contradicted the Manager Rule's Delegation Economics Exception, and two more lines had the same problem. The 2026-11-14 audit fixed four other places and missed these.
- **Two places still said "all findings must be fixed".** That contradicts the review loop's exit bar.
- **`sdlc-archive` called step 4 "the ONLY AskUserQuestion".** Step 9c and step 12 ask too, and so does step 0 when it reconciles. The project's version missed step 0.
- **The project's `sdlc-status` rows skipped `sdlc-lite/completed/`.** That is where `sdlc-lite-execute` moves a finished lite deliverable, so those rows would have hidden exactly the deliverables that are ready to archive.
- **Two descriptions were already over Claude Code's 1,536-character cap.** `sdlc-reflect` was at 1,604 and `sdlc-audit` at 1,541, so the listing cut off their anti-triggers. Claude Code's skills docs ("Skill descriptions are cut short", read 2026-11-18) say the combined `description` and `when_to_use` are capped at 1,536 characters (`skillListingMaxDescChars`). When the listing outgrows its budget (1% of the context window), it drops whole descriptions, starting with the least-used skills.

**Changes made:**

1. **Manager Rule.** These now follow the Delegation Economics Exception and its failed-dispatch rule:
   - `sdlc-execute` and `sdlc-lite-execute`: the "This phase is small" row.
   - `sdlc-tests-create`: the manager paragraph, the failed-dispatch rule and the compile-error row.
   - `sdlc-tests-run`: the one-line-fix row.

   A fix that passes the test is applied, re-tested and reviewed by SDET. Anything that needs diagnosis still goes to SDET.
2. **Exit bar.** `sdlc-plan`'s Post-Execution Review note and `templates/sdlc_lite_plan_template.md` now state `review-fix-loop.md` § Exit Bar: no critical or major finding open, no INVESTIGATE or DECIDE finding unresolved, and the minors still open after their batched pass listed for CD.
3. **`sdlc-archive`.** Step 4 is renamed the Main Approval Gate and names the other points that ask: step 0, step 9c and step 12. Step 9d and the Red Flags row agree with it.
4. **Trigger lists trimmed to one phrase per intent** in `sdlc-audit`, `sdlc-debug-incident`, `sdlc-develop-skill`, `sdlc-explain`, `sdlc-ingest` and `sdlc-playbook-generate`. This applies `sdlc-develop-skill`'s own rule. `sdlc-reflect`'s description is rewritten as a trigger, not a summary.
   - `sdlc-debug-incident` loses its "Use when…" sentence, which repeated the first sentence ("Required workflow for any production incident…").
   - `sdlc-develop-skill` loses its "Enforces…" summary.
   - `sdlc-explain` writes `/eli5 [topic]`: the skills docs say angle brackets in a description show as `&lt;`/`&gt;`.
5. **Agent names come from `agent-selection.yaml`, not a roster.** Projects name their own agents.
   - `sdlc-create-reference-doc` loses its author and quorum table and keeps the two categories with no owning domain.
   - `sdlc-debug-incident` loses its symptom-to-agent list, which its own Red Flags row ("I'll hardcode the agent matrix") already forbade. It adds the project's security-review agent if the project has one, and otherwise asks CD who assesses.
   - `sdlc-tests-run` loses its fallback example and its list of domain agents.
6. **Fixes and gaps:**
   - **`sdlc-status`** lists lite deliverables in `sdlc-lite/` (plan ready, executing) and in `sdlc-lite/completed/` (complete).
   - **`sdlc-develop-skill`:**
     - It states the 1,536-character cap and why it matters.
     - "Framework-owned" means listed under `installed_files` in `.sdlc-manifest.json`. Other skills are the project's, or come from other tools.
     - Its Exploration example is just `sdlc-idea`.
   - **Where descriptions are reviewed:** `sdlc-reviewer` checks the cap and reports a longer description as Major; `process/skill-agent-review.md` and `zsdlc-create-skill` add it to their checklists.
   - **`sdlc-research`** suggests starting points instead of requiring `site:` queries, as `zsdlc-research` does. It keeps the known gaps from step 2.
   - **`sdlc-develop-agent`:** the dismissal-defense row says what to do.
   - **`sdlc-audit`:** an empty improvement result is valid once the correction signals have been checked.
   - **`sdlc-tests-run`:** the example names `timing-paradigm.yaml`. `timing-defaults.yaml` is a template a project may never fill.
7. **`sdlc-plan`'s boundary** sends moderate-complexity work that needs no spec to `sdlc-lite-plan`, matching `commands.md`: complexity is the trigger, not file count.
8. **Policy: an unconfirmed suspicion is reported, not dropped.** `sdlc-compliance-auditor` reports a gap it has located but can't confirm as **info**, marked "unverified — check X", with what would confirm it. A suspicion it can't locate is still not reported, and minor or above still needs all four pieces of evidence. This matches the review loop's INVESTIGATE class: a finding nobody has diagnosed yet goes to diagnosis, not to the bin.
   - `compliance-methodology.md`'s Info level says the same.
   - `sdlc-audit`'s triage, and step 11 of the methodology, run each check first. A confirmed suspicion is triaged at its real severity, and a refuted one is dropped. Step 11 no longer skips while one is open.
9. **Bundle skills named conditionally.**
   - `sdlc-idea` routes visual/UI work to `sdlc-design-consult` if the design bundle is installed. Otherwise it routes to a design agent from `agent-selection.yaml`, if the project has one.
   - `sdlc-reflect` calls it "the design bundle's `sdlc-design-consult`".
   - `zsdlc-create-skill` says a core skill that routes to a bundle's skill names the bundle. Every other core reference to a bundle skill (the factory's and github-provenance's) already did.
10. **Migration (`sdlc-migrate`, `process/project-section-markers.md`):**
    - **§1.2a sizes a drifted file per hunk.** Each project hunk is subsumed (take upstream), untouched (re-apply) or combined (merge), rather than counted as conflicts. A file whose fix upstream already took reads as all conflicts but is all subsumed.
    - **The markers doc gains § What Markers Can't Hold:** a replacement of upstream text, YAML frontmatter, and table rows.
    - **§2.1c, and §1.2a's drift gate,** drop "wrap in markers" for those edits and offer to re-apply them instead.
    - **§4.6** lists the project's fixes to framework text under Upstream Candidates, since upstream is their only durable home.
    - **§3.2** compares an agent's memory and Surfacing Learnings sections with the template sentence by sentence. In the project, 6 of 15 agents had kept those headings but lost the template's routing sentences.

**Declined:**
- The whitespace-only hunks.
- The project's own knowledge file in two Integration lines. z-sdlc has no such file.
- The project's design agent in place of `sdlc-design-consult` (item 9 generalizes it instead).
- Deleting `commands.md`'s Design section. It is already marked optional, as the factory's section is.

**Open:** MIRROR-style markers for the agent template's memory and Surfacing Learnings sections, so a project's agents could be checked mechanically for drift. The MIRROR convention covers process-doc sections copied into skills, which migration overwrites. Agents belong to the project and are updated in place (§3.2), so extending it is a design question for CD. §3.2's sentence-by-sentence check covers the gap until then.

**Rationale:** A rule that an older line contradicts gets followed half the time. A project that fixes framework text in its own copy has no marker that keeps the fix, so the fix belongs upstream; otherwise every project hits the same contradiction and repairs it separately.

---

## 2026-11-18: The factory imported from the incubator (32271b0..8f83385): z-sdlc's copies handed back

**Origin:** CD (2026-11-18): "push and hand the factory changes to the incubator", after the agent-format port below.

**What happened:** `zsdlc-import-factory --to-incubator` at the incubator's `0a53446` wrote what z-sdlc was ahead on into the incubator, which took it in #146: the shellcheck fixes in `host/setup.sh` and `host/setup-ci.sh` (kept `ahead` by the last import), `process/factory.md` with Context7's plain tool names for factory runs, and the stage skills `sdlc-triage`, `sdlc-implement` and `sdlc-revise` with the narrower headless exception and final-message-only review dispatches. The factory tests passed there (810, 46 skipped). The import then read every bundle file in sync, and the proof passed: the incubator at `8f83385` took the bundle unchanged, and an empty project rendered all 19 templates and passed the workflow policy and the tests.

**Changes made:**

1. `.claude/skills/zsdlc-import-factory/import.json`: `last_import` is the incubator's merge of #146, so z-sdlc's next change to these files no longer reads as changed on both sides.
2. No bundle code or seed changed. The incubator's other factory commits in the range change only its production tier, which the bundle excludes. They also change its README's file table, which moves the production runner's request client to `host/`. The bundle's generic README seed doesn't list the production tier, so it needs no matching change, and the report's check item was accepted.

**Rationale:** Until the incubator took z-sdlc's copies and the import recorded it, the next z-sdlc change to any of them would have read as a conflict, and the proof would have installed the incubator's copies without z-sdlc's changes.

---

## 2026-11-17: Agents name their triggers in prose, send progress updates over a real channel, and are granted tools by exact name

**Origin:** A project that installed z-sdlc audited its Claude Code agent configuration on 2026-11-17 and changed its copies of the framework files. CD made each decision there: drop the example dialogues, keep the scenarios in a When to invoke section (the format Anthropic's guide uses), have progress updates reach the orchestrator, and let agents store memories as well as read them. That project's session sent the changes here to be carried upstream. Five of its commits touch framework files; they are ported onto z-sdlc's current text, not copied.

**What happened:**
- **Example dialogues.** Claude Code sends every agent's description with every request, and z-sdlc asked for one or two `<example>` dialogues in each. Anthropic's agent-writing guide (the `plugin-dev` plugin's `agent-development` skill) dropped its own dialogues on 2026-04-28 (its commit `ce721c1f1d`). It names the typical triggers in the description and keeps the worked scenarios in a "When to invoke" section of the agent body, which loads only when the agent runs. In the project, 17 descriptions totalled 24,307 characters with dialogues, 13,197 with none, and 16,047 in this format.
- **Progress updates went nowhere.** The protocol told agents to emit JSON progress updates. But text an agent writes while working stays in its own transcript, and the orchestrator receives only the final message. The project's probes in Claude Code showed:
  - an agent gets only the tools its `tools:` line names, and no agent listed SendMessage, so it had no channel;
  - `main` accepts SendMessage only from background subagents, and an update sent from one arrives mid-turn, before the completion notice;
  - a foreground dispatch has no mid-task channel;
  - SendMessage's own instructions ask for prose, not JSON.
- **Tool grants.** A tool named in a `tools:` line loads directly, with no ToolSearch. A server prefix grants every tool on the server and loads all of their definitions: one agent's prefix grant loaded about 250 tool definitions, about 240K tokens per dispatch. The project's CLAUDE.md told agents to use its memory store, Context7 and LSP, and no agent's `tools:` line granted them.

**Changes made:**

1. **`templates/agent-template.md`:**
   - The description gives a topic list in "Use this agent when…", names its scenarios in "Typical triggers include…" in body order, adds a seam sentence when a confusable sibling exists, ends its prose with `See When to invoke in the agent body.`, then the Do-NOT-use boundary. No `<example>` or `<commentary>` blocks.
   - A `## When to invoke` body section goes before every other section: 2–4 scenario bullets plus `Seam:` bullets, 5 at most, in prose with no `user:` / `assistant:` turns. New here (CD, 2026-11-18): a confusable sibling is an agent the Do-NOT-use boundary names, one seam bullet may cover several, and past 5 bullets the scenarios merge first.
   - The default tools include `SendMessage`.
   - New here, from Claude Code's tools reference ("Glob tool behavior", read 2026-11-17), which matches the project's probes: on macOS, Linux and WSL, Glob and Grep are out of the default tool set and searches go through Bash. A subagent gets them back only when it lists them without Bash, so a read-only agent lists Glob and Grep without Bash. A Bash agent keeps them for Windows. `sdlc-develop-agent` says the same.
   - The tools guidance says every tool the body tells the agent to use must be listed, an MCP server's tools are named one by one, and a project's own MCP grants belong in its CLAUDE.md.
   - The Communication Protocol sentence asks for short plain-text updates sent to the orchestrator. Its canonical "Read … and follow the canonical agent communication protocol it defines" opening is unchanged, so the phrasing contract is untouched.
   - New here: the Persistent Agent Memory guidelines say never to save a secret, credential, token or environment-variable value. `project_memory` (item 2) covers only an MCP memory store, so the rule hadn't reached `.claude/agent-memory/`, which every project without a memory store relies on. `sdlc-migrate` updates these guidelines in existing agents (§3.1), so it reaches them on the next migration.
2. **`knowledge/architecture/agent-communication-protocol.yaml`:**
   - A `delivery` section (`channel`, `no_channel`, `handoff_wins`, `dispatch_prompt_wins`, `cost`). Updates go only to the agent that dispatched you. A foreground dispatch, a harness without a messaging tool or a failed send means no channel: stop sending, don't retry another recipient, and carry the progress in the handoff. An update carries status only, so every finding must also be in the handoff. A dispatch prompt asking for the final message only overrides the section.
   - A `rendering` rule: the first line is the status sentence, then `name: value` lines. The `minimal_example` is plain text.
   - Renames: `when_to_emit` is now `when_to_send`, and `emit-during-long-tasks` is now `send-during-long-tasks`, qualified "when you have a channel". A blocked update's first line starts with `BLOCKED:`, and the BLOCKED state is returned as the handoff in every case. code-reviewer's `remaining` is now a count, which renders as a number, and security-engineer's list of uncovered domains is renamed `remaining_domains` so it doesn't clash with that count.
   - A `project_memory` section that names no memory product and covers an MCP memory store, not an agent's own `.claude/agent-memory/` directory. Never store a secret, credential, token or environment-variable value. Store only what was confirmed, once, after searching. A review dispatch stores nothing unless its prompt says to. Name each stored memory in the handoff, whose `common_elements` gain "Memories stored".
   - The headless rule is the project's (CD, 2026-11-18): a headless run stores nothing unless the caller's prompt names the memory store, and what it would have stored goes in the handoff. No one reviews what a headless run stores, and the factory's proposed memory store would make that a factory run's writes. `process/headless-mode.md` counted every write to an adapter's memory store as local work, so it now separates the two (item 15).
   - `dispatch_prompt_wins` overrides every progress-update instruction, `send-during-long-tasks` included.
3. **`knowledge/architecture/investigation-report-format.yaml`:** "progress JSON" becomes progress updates sent to the orchestrator, and multi-file reviews skip them when the dispatch prompt asks for the final message only.
4. **`process/skill-agent-review.md`:** the checklist carries the description format, the When to invoke section and the tools rule.
5. **`agents/sdlc-reviewer.md`:**
   - Grades: dialogue blocks are Major. A body scenario the description doesn't name, including a missing typical-triggers sentence, is Major, because routing reads only the description. Wrong order, a missing pointer or a named trigger with no scenario is Minor. A missing When to invoke section is Minor, and a transcript-shaped one is Major.
   - New here, from an open item of the project's review: a confusable sibling that the description names but no `Seam:` bullet covers is Minor.
   - `tools:` missing a tool the body uses is Major, a protocol agent without `SendMessage` is Major, and an MCP prefix grant is Minor. New here (CD, 2026-11-18): a tool the project's CLAUDE.md requires of agents doing this agent's work is Major when missing too; the framework's own agents are exempt. "Trigger quality" replaces "example quality".
   - A checklist item's own severity overrides the general "missing required sections" Critical, and the workflow and self-verification checklist carry the new cross-checks.
   - Its own description and When to invoke follow the format.
6. **`agents/sdlc-compliance-auditor.md`:** its description and When to invoke follow the format. Each framework agent's former second example ("did the migration…") is now a scenario, with a `Seam:` bullet routing the other reading to its sibling. Neither agent sends progress updates, so neither gets `SendMessage`, and neither names a memory store's tools.
7. **`skills/sdlc-develop-agent/SKILL.md`:** the description rules, the seam sentence, the tools rules (`SendMessage`, every tool the body uses, exact MCP names), the When to invoke section in step 3a, and two rationalization rows. New here: the tools step reads the project's CLAUDE.md for the tools its rules require of agents and grants them by exact name, and the full-engineering set includes `LSP`, as the template's does. A project that runs the factory gets Context7's plain names too (item 9), and step 3h names the no-secrets memory guideline.
8. **`skills/sdlc-migrate/SKILL.md`:**
   - The description and When to invoke are project-owned: a migration never adds or rewrites them, and §3.4 suggests a fix. A Knowledge Context section that §3.2 adds goes after When to invoke.
   - New here: §3.1 and §3.2 bring the Communication Protocol sentence to the template's wording, so an old "Emit structured JSON progress updates" sentence doesn't contradict the protocol. `tools:` stays project-owned, so an agent left without `SendMessage` is listed for §3.4.
   - New here: §3.4 flags an agent that sends progress updates without `SendMessage`, one missing a tool the project's CLAUDE.md requires of it, and an MCP server granted by prefix. Both are advisory, since `tools:` is project-owned, and its gate rule says how an approved description fix or tool grant is applied.
9. **`CLAUDE-SDLC.md`:** an "Agent tool grants name each tool" convention covering Context7, LSP, the project's memory store and `SendMessage`, by the names the session lists (a plugin-installed server's tools carry the plugin's prefix). The project's own grant list goes in a project-owned part of its CLAUDE.md, where `sdlc-develop-agent` reads it.
   - New here: a project that runs the software factory also grants Context7's plain names (`mcp__context7__resolve-library-id`, `mcp__context7__query-docs`). A factory stage that connects an MCP server connects only Context7, as a server named `context7`, under `--strict-mcp-config` (`agent_job.sh mcp`), so an agent granted only a plugin install's names would have no Context7 in factory runs. Granting both is safe: Claude Code's errors reference ("Agent would be spawned with zero tools", read 2026-11-17) refuses a subagent only when every entry in its `tools:` list fails to resolve. `process/factory.md`'s `--strict-mcp-config` rule says the same, and goes to the incubator with the factory skills (item 10).
10. **`process/review-fix-loop.md` and the skills that mirror its review blocks** (`sdlc-execute`, `sdlc-lite-execute`, `sdlc-review-code`, `sdlc-create-reference-doc`, `sdlc-plan`, `sdlc-lite-plan`, and the `factory` bundle's `sdlc-implement` and `sdlc-revise`): new here (CD, 2026-11-18), a "Final message only" rule. Each reviewer's prompt asks for its findings in its final message, with no progress updates. Both mirrored blocks carry the sentence, because the protocol's advice to do this in parallel review fan-outs reached only the agents, never the dispatching skill. The factory skills' new copies still go to the incubator with `zsdlc-import-factory --to-incubator`.
11. **`BOOTSTRAP-LITE.md`:** the lite agents' frontmatter rules and When to invoke section follow the full ones. Their Knowledge Context goes after it. Lite installs no communication protocol, so lite agents send no updates and get no `SendMessage`.
12. **`agents/AGENT_SUGGESTIONS.md`, `skills/sdlc-initialize/SKILL.md`, `process/knowledge-routing.md`:** three mentions of `<example>` blocks or emitted updates follow the new format.
13. **`.claude/skills/zsdlc-audit/references/compliance-methodology.md`** (framework development, not installed): Dimension 8 checks the description format, When to invoke and the tools rule.
14. **`plugins/context7-setup.md`:** new here. The guide installed the plugin but said to expect `mcp__context7__…` names. A plugin install's tools are `mcp__plugin_context7_context7__resolve-library-id` and `…__query-docs` (the plugin's `.mcp.json` names its server `context7`). The guide now gives both forms and a "Granting It to Agents" section with the factory's plain names (item 9).
15. **`process/headless-mode.md`:** new here. Its "local work" paragraph counted every write to an adapter's memory store as local. It now covers the framework's own knowledge-layer updates (discipline capture, knowledge-store updates), even when an adapter writes them to its store. An agent's own memory-store writes are left to the protocol's `project_memory` rule (item 2). The `headless-stop-rule` block, which binds a headless run's subagents too, says the same, and its 33 copies in the `sdlc-*` skills match it again. They include the `factory` bundle's `sdlc-triage`, `sdlc-implement` and `sdlc-revise`, whose new copies go to the incubator (item 10).

Not carried: the project's own agent scenarios, its tool lines and standard grants (the memory store's, Context7's and LSP tool names), its deployment agent's provider tools, and its own linter, which isn't part of z-sdlc.

**Rationale:** Routing keeps the same signal in the description at about two thirds of the dialogue cost, and each agent keeps its scenarios at no per-request cost. The protocol's updates now travel over a channel that exists, and fall back to the handoff when there isn't one. Grants by exact name let agents follow the project's rules without loading every tool a server has. Adapters: no standard phrase changed. The new rule that `tools:` must grant every tool the body uses also applies to an agent body an adapter rewrites to call its own tools.

---

## 2026-11-17: CI skips the jobs a change doesn't need, never the run

**Origin:** CD (2026-11-16), in a project's execution session: "for docs only commit messages, we should add this as an upstream rule in z-sdlc." That session relayed it. CD (2026-11-17), after the draft's reviews: drop the rule, keep what the experiment found, and write up gating in CI instead.

**What happened:**
- In one project, a draft pull request took about 141 pushes in 8 days. Each push re-ran a pre-merge workflow of about 19 jobs, with a median wall time of about 72 minutes, and 6 of one session's 10 pushes were docs-only commits.
- The directive asked for docs-only commits to carry GitHub's skip note. To be safe, the draft rule needed five checks:
  - the commit is docs-only by nature;
  - its branch has no pull request, or a draft one;
  - nothing the skip silences matters;
  - no other commit rides under it;
  - no merge can carry it to the default branch.
- Four adversarial review rounds found 2 critical and 4 major problems, then 1 and 5, then 0 and 3, then 0 and 1 (a merge queue can carry the note).
- The checks fail on GitHub's default merge settings, in every project with the factory bundle (its advance runs on `pull_request: closed`, which the note silences), and in the project that prompted it. So the rule would almost never apply. It was dropped before it was committed.
- Gating inside CI saves the same runs without those traps, and the incubator's CI already works that way.

**What GitHub did** (seen 2026-11-16 in a throwaway private repository, with one workflow on `push` and one on `pull_request`, over three passes and 53 runs; not in GitHub's docs unless marked):

| Case | Result |
|---|---|
| A push whose head carries the note, with or without other commits under it | no `push` run |
| A push with a note commit under a commit without one | runs |
| A note commit pushed to a draft PR whose head had none | no `push` run, no `synchronize` run |
| An empty commit without the note pushed on top of it | both run, and so do marked ready and merged |
| A PR whose head carries the note, when opened, marked ready, merged or closed unmerged | no `pull_request` run (the docs say only "the HEAD commit of a pull request") |
| The default branch after a merge commit merge | runs |
| After a squash merge with `COMMIT_MESSAGES` (a new repository's default) | no run: the squash commit's message holds the note |
| After a squash merge with `PR_BODY` | runs |
| After a rebase merge whose head was the empty commit | no run: the rebase dropped the empty commit, and the note commit became the head |
| A release-style `git merge --no-ff` of a range holding a note commit, or of a tag on one | runs |
| A lightweight tag pushed onto a note commit | no run (a tag on a commit without one runs) |

**Not tested:**
- merge queues;
- a `BLANK` squash message;
- `reopened` and `labeled` runs, and `workflow_run` chains;
- annotated tags;
- a fast-forward of a deploy branch onto a note head;
- services other than GitHub Actions that build from the repository and may honor the note too.

**Documented** (GitHub's "Troubleshooting required status checks", "Compare two commits" and "Control the concurrency of workflows and jobs", read 2026-11-17):
- a required check whose workflow is skipped by path filtering, branch filtering or a commit message stays Pending and blocks the merge;
- a job skipped by its condition reports Success;
- the compare API lists at most 300 changed files;
- by default a concurrency group holds one pending run, and a newly queued run cancels it.

**Changes made:**

1. **`knowledge/testing/test-infrastructure-patterns.yaml`** § `ci_execution`, a new `change_gating` entry:
   - **One aggregate check is required,** on `if: always()`. It reads each job's result, so a failed gate can't skip it into a pass.
   - **A detecting job, doing nothing else, sets one output per area** from the compare API. An area's patterns cover every path its jobs read, and the workflow file is in each of them.
   - **Any doubt runs everything.**
   - **`concurrency` cancels a pull request's superseded runs only.** Every other run gets a group of its own, since a group's newly queued run cancels its pending one even without `cancel-in-progress`. One group per branch would drop a default-branch run that was waiting. With change detection, no later run would check that merge's changes either, since each run checks only its own push's files. The incubator's CI had this gap, and fixed it in its own PR.
   - **The triggers:** no path filter on a required workflow, and `merge_group` with a merge queue.
   - **Never a commit-message skip,** with the findings above in short.
2. **`knowledge/provenance_log.md`:** an entry for the experiment and the two docs pages, since GitHub can change the behavior seen.

**Rationale:**
- **A skip note costs more than it saves.** A missed skip costs minutes; a wrong one can skip a deploy, a release, or the factory's advance, and leave a pull request blocked on checks that never start.
- **Gating in CI decides from the files changed,** not from what the committer believed about them. It saves the same runs on every push, draft or not, and works the same on GitHub's default settings.

**Release:** patch (guidance in an existing knowledge store).

---

## 2026-11-17: The factory imported from the incubator (6094011..32271b0): the CI tier's optional GPU

**Origin:** CD (2026-11-16/17): a pull request's code may use a GPU on a CI-only host, after the incubator's measurement of what a GPU does for the CI tier's Playwright browser suites.

**What happened:** The incubator added `CI_JOB_GPUS` (#140: one CDI device name per CI slot, checked by setup and the launcher, a library layer on the job image, an isolation probe) and took z-sdlc's review fixes (#141). It then took z-sdlc's own changes back (#142), which cleared the import's two [fix first] items, and this import followed.

**Changes made:**

1. `bundles/factory/tree/host/ci_launcher.py`, `setup.sh`, `setup-ci.sh` and the tests `test_ci_launcher.py`, `test_host_setup.py`: the incubator's versions (five files changed on both sides, the incubator's holding both sets). z-sdlc's own shellcheck fixes in `setup.sh` and `setup-ci.sh` are kept, and stay `ahead` for the incubator.
2. `process/factory.md` step 10: a GPU bullet under the CI tier's browser-suite notes (what the setting is, what setup needs and refuses, that the project's Playwright config must ask for the GPU, and that the host should do nothing else).
3. `bundles/factory/seed/host/host.conf`: a commented `CI_JOB_GPUS` after `CI_CPU_QUOTA`.

**Rationale:** The setting is off by default and changes nothing for a project that doesn't set it, so it is documented where the CI tier's other settings are.

---

## 2026-11-17: The CI tier follow-ups' review fixes

**Origin:** CD (2026-11-17), on the final review of the follow-ups below: "fix those yes, then send them over."

**What happened:** Two fresh reviewers checked what no one had reviewed: the follow-ups' last launcher fixes and their tests, and the docs and changelog against the code. Neither found anything critical or major. The code review found four minor problems, and the docs review found five things to fix before a release and a few smaller ones.

**Changes made:**

1. **`host/ci_launcher.py`:**
   - **Each slot holds a lock while its cycle, or its stop's removal of registrations, runs** (`slot-N.lock`, never removed). Slot 1's sweep of a retired slot takes it without waiting, and leaves the slot alone while it's held. A stop removes its container and JIT config before it takes the lock, so a stop waiting behind a sweep still removes them in time. Before this, the sweep could delete a record that the retired slot's live cycle had just rewritten with a new runner's ID, leaving that runner with no record. It was the third review to find a race between the sweep and a live cycle, so this closes the whole class rather than the one case.
   - **Failed cycles no longer pile up pending markers.**
     - The token comes before the marker, so a cycle that can't get one writes none.
     - A refusal from `generate-jitconfig` (a 4xx other than 409) drops the marker, since GitHub registered nothing (`Refused`).
     - A lookup that fails ends `resolve_pending`'s pass, rather than each marker waiting out a timeout in turn. The reviewer worked out that, on a network dropping packets, about eleven markers would take a slot's stop past its six minutes.
   - **The tidy-up:**
     - a cycle removes its slot's temporary files that a killed write left;
     - the sweep tidies every retired slot, including one whose stop removed every registration: its temporaries, and its failure count once it holds nothing.
   - **`retire`** reads the slot's record without a separate existence check. The sweep removing it in between made `retire` answer "not idle: FileNotFoundError".
2. **`host/setup.sh`:** the runners' archive is downloaded and checked once, the first time a runner needs it, and every runner unpacks that one. Before, each runner downloaded in turn, so a second runner's failed download left the first, already upgraded, stopped until setup ran again. Now a failed download stops setup before any runner is stopped. The archive (`$RUNNER_HOME/.actions-runner-<version>.tgz`) is removed after the runners' loop. One left by a setup that stopped partway, at any version, goes with the next download.
3. **`process/factory.md`:**
   - Enablement step 8: the upgrade sentence says every runner is as it was after a failed download, and that this applies to the strict and planning tiers only, since the CI tier's runner version is a job-image input.
   - D3 rule 2: the database address's other ports are probed only when it's private or tailnet, and only those in `PROBE_PORTS`.
   - The CI tier's step 4:
     - a reboot or a trip stops a slot mid-job; setup no longer does;
     - a refused name isn't kept;
     - the 404 rule covers leftovers and `retire`.
   - The setup notes: slot 1's sweep runs at the start of its cycles, spares a busy runner, and leaves a slot alone while its own process runs.
   - Step 12.4: regenerate the audit's workflow after a release that changes `runner_audit.py`, since the workflow carries its own copy.
4. **`process/factory-runbook.md`:** the same for the audit, in its list of what to regenerate.
5. **This changelog:**
   - the follow-ups' upgrade notes now name the `x86` refusal, the one change that can fail a project's CI after migrating;
   - the import entry no longer says the deleted handoff remains.
6. **`docs/current_work/ideas/runner-audit-reads-audit-log_handoff.md`:** its references point to names and quoted phrases, not line numbers, which had drifted (`create_app.py`'s two by about 20 lines, `factory.md`'s by about 300).
7. **Tests:**
   - `tests/test_ci_launcher.py`:
     - the sweep leaving a locked slot alone, and a cycle and a stop holding the lock (a stop waiting on it has already removed its container);
     - a cleanly retired slot tidied;
     - a retired slot found by its marker alone;
     - failed cycles leaving no markers, with a 5xx and a 409 keeping theirs;
     - a failed lookup ending the pass;
     - `retire` surviving a record removed mid-read;
     - the temporaries' tidy-up;
     - the temporary-name test now looks while the file exists.
   - `tests/test_host_setup.py`: one download shared by two runners, a failed one stopping neither and leaving no partial file, and a stale archive removed.

   Each new test failed against a copy of the code with its fix taken out.

A fresh review of this change found nothing critical or major. Its five minor findings are fixed:
- nothing tested that a cycle and a stop hold their lock;
- a cleanly retired slot was never tidied;
- a stop could wait behind a sweep before removing its container;
- an archive left at an older version was never removed, and the failed download's clean-up was untested;
- four comments still described the sweep running beside a live cycle.

**Not done:** of the code review's smaller notes, nothing. Of the docs review's, the commit messages' two slips ("five copies" for two tests, and "16" of 17 findings): rewording them would rewrite history under another session's commits.

**Rationale:** The follow-ups said their cleanups couldn't leak. These close the cases where they still could, and make the docs say what the code does.

**Upgrading:** as for the follow-ups below: a project with a CI tier runs its setup again after the migration, and the shared host's repository copies `host/` and runs the strict and planning tiers' setup again. Nothing else.

---

## 2026-11-16: The factory-broker bundle, a checks-only production broker (pilot)

**Origin:** the third project's factory install, whose broker (a checks-only one, for a host that deploys the release branch by itself) any next project would write again. CD (2026-11-16): an opt-in bundle whose fixes reach projects through migration; the bundle owns the generic broker and the project its host module; root runs no project code; the whole bundle piloted before it debuts; the request client in the factory bundle. Plan: `docs/current_work/ideas/factory-broker-bundle_plan.md`.

**What happened:** The third project's broker (about 3,100 lines, a 1,200-line setup and 587 tests) was mapped line by line into generic code, host code and project data. A scratch host module for it then proved that declared data can express every check its broker made as root, except the host's config check and its operation list, which moved into the sandboxed step and the block. The generic broker and setup were built from it, the generic tests carried over onto a fake host, and the bundle was reviewed twice (security, and correctness against D4) and fixed. It ships as a pilot: nothing has run under real systemd, and the third project's adoption on its production machine is the pilot.

**Changes made:**

1. **`bundles/factory/tree/gates.py`:** the operations digest covers a broker's own host module (`BROKER_MODULES`, `factory_op_host.py`) by exact name when present, the same in the repository and installed; a stray file can't enter it. A broker with a host module also has its `config.json` hashed (approvers, the App's id, the release branch and its start), so a change to it refuses gates until setup re-runs; a broker without one (the incubator's) hashes exactly what it did. The catalog's optional `rollbacks` (true unless false) is the broker's word that it runs rollback steps, and with false the plan guard refuses a gate's rollback (D4 rule 11: CD is never told a rollback will run that won't). `tests/test_broker_package.py` (new) covers both.
2. **`bundles/factory/tree/host/factory-op-request` (new):** the per-user request client (`/run/<calling user>/op.sock`), in the factory bundle so every tier's setup on a host installs the same bytes.
3. **`skeleton/manifest.json`, `skills/sdlc-initialize/SKILL.md`, `skills/sdlc-migrate/SKILL.md`:** a bundle may require others (`requires.bundles`), checked at install and on every migration, and may be marked `pilot`: initialize doesn't offer it, and it has no `bundle_debut` entry until its pilot passes.
4. **`process/factory-broker.md` (new), `bundles/README.md`, the `factory-broker` bundle in `skeleton/manifest.json` (`pilot`, requiring `factory`):** what the bundle installs and who owns each file, how it works (root runs no project code; the digest covers the host module; the instance from the install path; setup's trust root), the host module's contract, the `broker` block and the catalog keys the broker requires, its `enable` runbook (`factory-broker-enablement`), adopting it by hand over a broker of a project's own, and `## After migrating`.
5. **`process/factory.md` D4 rule 16:** the factory bundle still installs no production tier; the `factory-broker` bundle supplies a checks-only one for a project whose host deploys the release branch by itself.
6. **`bundles/factory-broker/tree/production/factory_op.py` (new):** the generic broker, generalized from the third project's (reviewed over four rounds there). Root's commands never import the host module; only a sandboxed step loads it, by explicit path, after its not-root check, and checks its interface. Every root check of the host is generic code over typed step outputs or the `broker` block's data. The instance comes from the install path. It refuses a rollback for every request kind, a release-kind request while `release_gates` is false, and a catalog that breaks its rules (`broker_problems`, pure, also run by the project's CI). It reads a ledger written before it, so a project adopting it keeps its release head and recorded state. Its generic operations: `release-wait`, `health`, `http-check`, `capture-state`, `drift-scan`, `host-check`.
7. **`bundles/factory-broker/tree/host/setup-production.sh` (new):** generic setup. The repository comes from a root-owned tier record written on the first run, never from the checkout; `production.conf` is parsed as text, never sourced; other tiers on the host are found, hidden from this one's steps and units, and checked unchanged after; the client is replaced only when absent or identical, or on CD's `REPLACE_CLIENT=1` after its diff; the runner's pinned version is read from the factory bundle's `setup.sh`.
8. **`bundles/factory-broker/tree/production/tests/` (new):** the broker's tests on an in-memory host reached only through the egress path (the fitness tests first: root never imports the host module, the interface check, the rollback and evidence refusals, the instance rule, the digest), setup's tests (two tiers side by side, the trust root, the client rule, every name and sandbox property tied to the broker's), and `test_broker_catalog.py`, which checks the project's own `ops.json`, `config.json` and host module against the broker's rules in its CI.
9. **`bundles/factory-broker/seed/` (new):** the host module as a stub that fails every step closed, `ops.example.json` (the catalog to start from, accepted by the broker's rules with release gates off), `config.json`, `host/production.conf`.
10. **Reviewed twice before the pilot** (security, and correctness against D4 and the doc), with no critical finding; every finding fixed with a test that fails without the fix. The sandbox became an allowlist (`/run` empty but for the egress socket and the step's directory, its own IPC namespace, no `/dev/shm`; systemd 248 or newer). No command starts a step, and `resolve` closes no run, while one of the tier's step units is still running (a broker killed mid-step leaves its step running). Setup takes the broker's lock, and a gate stops if the installed package changes under it. `host_locks` only in root's own directories. The egress proxy can't reach the production machine. A torn last ledger line refuses gates until `resolve --torn-line` moves it aside with a signed note. The approval check reads the environment's name from `config.json`, which setup ties to `factory.json`. The daily drift check accepts a release gate's pinned merge by its exact subject. A heartbeat `health` step fails rather than overrun its deadline, and the catalog's rules size its timeout.
11. **`tests/test_factory_broker_bundle.py` (new):** the shipped seeds choose nothing for a project and pass the broker's rules, the stub host module fails every step closed, there's no seeded `ops.json`, and the bundle is a pilot with no `bundle_debut` entry. The bundle's own tests run in a project, where they can't tell a shipped preset from a project's choice.
12. **An outside review (Codex, on the bundle's code and docs alone):** two of its findings fixed. An earlier gate counts only when it ran as the kind the plan gives it now (a gate since made a release gate, or no longer one, runs again: its result lacks, or had, the release's checks). `resolve --torn-line` replaces the ledger in one rename, so a crash never leaves it cut without its note. Its third, that setup's first stage runs the checkout's own script as root, is the documented limit both setups share; the enable runbook now says, as the factory's does, to run setup from a fresh clone no agent session can write.

**Upgrading:**
- `gates.py` changed, which is in the operations digest: a project with a production tier re-runs its setup after the migration, or every gate is refused (as with this release's other `gates.py` change: one re-run covers both). A broker with no host module, such as the incubator's, hashes the same files as before.
- The factory bundle now ships the per-user request client (`host/factory-op-request`). The incubator's production setup installs it too, from a PR there that CD merged (2026-11-17); its host takes the shared client at the same setup re-run the `gates.py` change calls for.
- Nothing installs the `factory-broker` bundle: it is a pilot (`process/factory-broker.md` § Adopting it by hand).

---

## 2026-11-16: The headless stop rule names its two standing exceptions

**Origin:** the dry run of the external review gate's runbook (the runbooks entry below). CD (2026-11-16): fix the copied rule.

**What happened:** The stop rule every skill copies said a headless run sends nothing outside the working tree "unless the caller's prompt names it". Its source doc's § Outward Actions allows two more: a write to the project's knowledge backend (local work), and the External Review Gate's send to a hosted provider the project has durably authorized. A skill reading its own copy would skip an authorized review, or refuse its own knowledge writes, while the full rule allowed both.

**Changes made:**

1. **`process/headless-mode.md` § Mirrored Stop Rule:** the block names both exceptions, with the gate's pointing at `external-review-gate.md` § Data egress for what durable authorization is. § Outward Actions points there too.
2. **The 33 skills under `skills/` that carry the block:** re-copied from the source. Every copy had matched the old source exactly.

**Upgrading:** nothing to do. The factory bundle's skills (`sdlc-triage`, `sdlc-implement`, `sdlc-revise`) carry the block too, so the incubator takes the new copies with the next `--to-incubator`.

**Rationale:** A copy that's shorter than its source has to say the same thing, or a skill obeys the copy and contradicts the rule it was copied from.

---

## 2026-11-16: The spec-relevance walkthrough and the plugin check, each in one place

**Origin:** the survey behind the runbooks entry below found two procedures written twice, with the copies drifting. CD (2026-11-16) had them fixed here rather than handed off.

**What happened:** `sdlc-migrate` said to run "the same walkthrough as `sdlc-initialize` Phase 6d", and `sdlc-initialize` promised CD could re-tag stores later, but `sdlc-initialize` deletes itself after the install, so in a project neither pointer led anywhere. The plugin readiness check was written in both skills, and the copies disagreed: migrate grepped for language servers' names, which miss some installed plugins (`typescript-lsp`, `csharp-lsp`), and initialize gave no command for LSP at all.

**Changes made:**

1. **`knowledge/README.md` § spec_relevant Field:** "Tagging a project's stores", the one walkthrough. `sdlc-initialize` Phase 6d and `sdlc-migrate`'s first migration with the field point at it.
2. **`plugins/README.md` § Readiness check (new):** the one check, whose LSP grep matches an installed plugin's `<language>-lsp` name as well as a server configured by hand. `sdlc-initialize` Phase 9 and `sdlc-migrate` § 4.4b run it.
3. **`skills/sdlc-migrate/SKILL.md` § 2.1:** copies `plugins/*.md`, which no migration had refreshed, so a project kept its install's plugin guides. It copies each one that differs from the release's, not only those the release changed, so a project catches up on its first migration with the rule.

**Upgrading:** a migration runs the project's installed `sdlc-migrate`, a release behind, so the plugin guides and § Readiness check arrive with the migration after this one; this one still runs its own copy of the check.

**Rationale:** A procedure written twice drifts, and a pointer into a skill a project no longer has points nowhere.

---

## 2026-11-16: Runbooks: one skill drives every one-time procedure

**Origin:** CD, on a draft `sdlc-enable-factory` skill: "i don't want skills for one time things, only for repeatable things. once you install the factory, you wont need to run the skill again." An Anthropic-docs and Day-0/1/2-operations search, and a Codex cross-check (gpt-5.6-luna, framework excerpts only), both chose a generic hook with the procedure in the bundle's own docs; Codex added a small generic runbook driver, which CD chose (2026-11-16): "i like the idea of a runbook skill; we can see what else in the initialize/migration might benefit from it, as well as using it for other bundles."

**What happened:** Enabling the factory is a long, mostly one-time procedure (about 83 hours on the third project, across many sessions), and a skill of its own would load its description on every turn of every factory project for good, after one use (Claude Code's skills docs). The procedure was already a runbook (`process/factory-runbook.md`); what it lacked was a way to resume across sessions and to keep each step's check on record. One generic skill now does that for any runbook, the github-provenance bundle's Enablement included.

**Changes made:**

1. **`process/runbooks.md` (new):** the convention. The rule, stated once: skills are for repeatable work; a one-time or rare procedure is a runbook. A runbook is a process doc or section opening with a marker line (`**Runbook:** `<id>` · **When:** enable | on-demand · **Record:** ...`); its numbered steps (a section, or a section's item: `3.3 item 6`) are its IDs and never renumber; it says the order when that isn't its numbering; each step says who does it (**[CD]**) and has a **Check:**; a definition-of-done item a decision can make inapplicable says so; a decision the runbook itself records isn't asked again. Its record (in the project, or `docs/runbooks/<id>.md` when it has no natural home; never the configuration it fills, which can't say where the run stands) keeps Status, Next, Decisions (sessions' ground rules included), State (each step `passed`, `done`, `skipped` with the decision, or `failed`) and Deferred. A bundle's `## After migrating` section is not a runbook: `sdlc-migrate` follows it.
2. **`skills/sdlc-run-runbook/SKILL.md` (new, core):** lists the runbooks and where each stands; runs one: loads its record (adding missing parts without rewriting what's there, and carrying in what an older record kept elsewhere), resumes at the first step with no passed check, confirms relayed decisions, asks up-front questions four at a time, takes each step (dispatching, or handing CD a **[CD]** step), writes each check to the record, and commits a handoff at each phase's end. Headless, it takes read-only steps only. `process/headless-mode.md` § Integration and `process/commands.md` list it.
3. **`process/factory-runbook.md`, `bundles/factory/seed/README.md`, `process/factory.md`:** the runbook's marker (`factory-enablement`) and its order (§ 2's inventory before § 1's form); § 3.3 item 6, the rulesets, marked **[CD]**; § 3.8's production-tier items conditional on § 1 C3; the seed's record gains Status and Next; `factory.md` says to read the runbook's opening and § 0 first.
4. **`process/github-checkpoints.md` § Enablement:** a runbook (`github-provenance-enablement`), recording in `docs/runbooks/github-provenance-enablement.md`, with its questions asked first (board, labels, and the config fields no step filled: stakeholders, terminology, sensitive data, human labels), a definition of done, a **Check:** on every step (the org's check moved after step 2 confirms the org), and **[CD]** on CD's two (the token's account, `enabled: true`).
5. **`process/factory.md` § After migrating (new):** what a release can make due (re-run production setup when the digest's files change, smoke after new action pins, tier setup within 30 days of a runner version bump, the CI tier after its files change, seed changes to copy by hand, the runner audit after label changes), which migrate reports and CD does. The rest of the upkeep stays in the runbook's § 7.
6. **`skills/sdlc-status/SKILL.md`:** lists open runbooks.
7. **`.claude/skills/zsdlc-create-skill/SKILL.md`, `skills/sdlc-develop-skill/SKILL.md`:** step 1 asks first whether the skill is repeatable, and points a one-time procedure to `runbooks.md`.
8. **Tried before release:** a fresh agent ran the skill, dry, on both runbooks with half-filled records (the factory's in its older shape, without Status or Next). It found a config-block record left nowhere to write a check or Next, steps without a check that could never read as passed, ambiguous IDs where a runbook item cites another doc's step number, the factory's survey-before-form order unstated, an unreachable done when the production tier is deferred, and github-provenance's unfilled config fields and checks out of order. Each is fixed above. A second dry run on the fixed docs listed both runbooks and resumed github-provenance correctly on a literal reading; its findings (every recorded decision re-confirmed each session, Next guessed while loading, "first session" undefined, ground rules read as a step, older State lines without an outcome, one check over eight items, questions without recommendations) are fixed too: a decision in the record stands unless reopened, and a reopened one fails the steps built on it; Status and Next are set only at a phase's end; each numbered item of a step records its own outcome.
9. **`skills/sdlc-initialize/SKILL.md`, `skills/sdlc-migrate/SKILL.md`:** generic hooks in place of the factory's name. Initialize offers each accepted bundle's `enable` runbook at the end (Phase 12), which it had promised but no phase did. Migrate offers it with a newly debuted bundle (§ 4.7); after the render, follows each installed bundle's `## After migrating` section, comparing the bundle's files at `source_version` with the release's; and reports what's due and the open runbooks under a new **Bundles** heading, with CD's steps as next steps.
10. **`tests/test_runbooks.py` (new):** every marker well formed and unique, its doc shipped, both bundles' enablement runbooks found, and `## After migrating` headings exact. A bare `**Runbook:**` label, a gate's checklist in `production-gates.md`, isn't a marker.
11. **Removed before release:** the draft `sdlc-enable-factory` bundle skill, and its mentions. It was never committed or tagged, so no contract entry is needed: had it shipped, removing it would have taken one, since `sdlc-migrate` never removes an installed bundle's skill.

12. **A third kind, `setup`** (`process/runbooks.md`, `sdlc-run-runbook`, `sdlc-status`, `sdlc-initialize` Phase 12, `sdlc-migrate` § 4.6 and § 4.7, `tests/test_runbooks.py`): a core feature every project gets but not every project uses. CD (2026-11-16) had these built here rather than handed off. Initialize offers each at the end of the install, and migrate each one the project has no record of: the test is the record, not the release that shipped it, so the one-release lag only delays the offer. Each offer has three answers: now; later, which writes nothing, so it's offered again; or not for this project, which writes the record as `declined`, and nothing offers it again. A test holds `enable` runbooks to a bundle's docs and `setup` ones to the core's.
13. **`process/external-review-gate.md` § Enabling the gate:** a `setup` runbook (`external-review-gate`): find the wrappers already there, CD's destination for payloads (a local model, a hosted provider, or nowhere, and the same for promotion judgments), write or align the wrapper, and a dry run with no project code. § Data egress now says what "durable authorization" is: the destination (provider and model) CD decided at step 2, while the wrapper still sends there, with how to tell a Codex wrapper's provider. Until step 2 has passed, an authorization written down before still counts, and declining the runbook leaves a wrapper running. Nothing said where authorization was kept before, so a headless run couldn't tell.
14. **`process/verify-command.md` § Setting it up:** a `setup` runbook (`verify-command`): the inventory, CD's decision, scaffolding or extending the command, a check that it fails naming a broken gate, its line in `CLAUDE.md`, and the gaps under Deferred. `sdlc-initialize` Phase 9b offers it (now, later, or not for this project) instead of scaffolding inline, so the gaps outlast the install skill, and a project that never had the command is offered it on a migration. § Scaffolding Guidance now says a gate CI runs is chained with CI's command, and its missing configuration is a gap.
15. **`skills/sdlc-run-runbook/SKILL.md`:** a run sets its record's Status to `in progress` when it starts (step 2), moving a prior `done` or `declined` into Decisions, so a run that stops early isn't hidden. A run that finishes in its session needs no handoff (step 6, as `runbooks.md` § The record already said), and a run inside an install or a migration commits with it.
16. **`skills/sdlc-initialize/references/retrofit-mode.md`:** a retrofit install runs Phases 9 and 9b and ends with Phase 12, as a fresh one does. It ran neither, so it never checked plugins, and its install never offered a runbook.
17. **Tried before release:** a fresh agent dry-ran both runbooks on an installed project with a hosted wrapper and an old `CLAUDE.md` authorization: kept as it is, turned off, re-run after a decline, and a headless run's authorization read in three states. It found the gaps items 13 to 16 now close: an unconfirmed carried decision read as authorization, an "endpoint" a Codex wrapper never names, a Status left `declined` during a run, a "not now" at install that meant never, a `CLAUDE.md` note left contradicting the record, and a verify check that couldn't fail.

**Upgrading:**
- **The setup runbooks are offered from the migration after this one:** a migration runs the project's installed `sdlc-migrate`, a release behind. Meanwhile `sdlc-status` lists them as "no record yet", and `sdlc-run-runbook <id>` runs one any time.
- **A project whose external review gate sends to a hosted provider:** the authorization now lives in the gate's runbook record. Until that runbook runs, one written down before (in the project's `CLAUDE.md`, say) still counts; with none, a session confirms before its first hosted run and a headless run skips hosted models, as before.

**Rationale:** A skill earns its context cost by being used again and again; an install is used once. One driver for every runbook is repeatable work, and keeps each procedure in one place, its bundle's own doc.

---

## 2026-11-16: What the third project's factory install found worth building upstream

**Origin:** `docs/current_work/ideas/factory-enablement-upstream_handoff.md`, written with the runbook (2026-11-08) from the third project's install. CD (2026-11-16): "do all except 6", the production drill checklist.

**What happened:** The third project's install built several pieces any next install would build again, or found missing: a broker for a host that deploys a branch, a planning reader generator that doesn't need an ORM, a CI audit for Enablement step 10, gate-plan checks its broker made only after a release's deploy, review rules for its stack, and a copied CODEOWNERS list that drifted.

**Upgrading:**
- **A project with a production tier:** `gates.py` changed, which is in the operations digest: re-run the production tier's setup after the migration, or every gate is refused. To have the plan guard budget gates, declare the broker's own time in `production/ops.json` (`gate_overhead_s`, `step_margin_s`, `release_wait`; D4 rule 3), which is in the digest too.
- **A project with a bundle that gains a file:** the migration runs the project's installed `sdlc-migrate`, whose rule for a skill or process doc a bundle gains is this release's (§ 2.0a): check that the bundle's new files arrived, and copy any it left out from the release.
- **A project on FastAPI or SQLAlchemy:** the seed is the project's, so copy the new packs from the bundle's seed `factory.json` into its own `review.focus` if it has none of its own.
- **Every project:** the seeded `tests/test_codeowners.py` is the project's and doesn't update. Replace its `PROFILE_FILES`, `NODE_FILES` and `PACKAGE_MANAGER_FILES` with `guard.profile_build_files(stack)` (the new seed's `test_the_profiles_build_files`). The guard's lists hold samples the old copies lacked (`eslint.config.mjs`, `.eslintrc*`, `vitest.workspace.*`, `.postcssrc.json`, `.babelrc.json`, F# and VB project files, and `requirements*.txt` for `python-uv-node`), which factory.md's list already named: CODEOWNERS must own them.

**Changes made:**

1. **`bundles/factory/tree/host/setup.sh`, `host/setup-ci.sh`:** shellcheck's warnings at its default level are gone: an empty `local` assignment written `token_copy=''` (SC1007); `setup-ci.sh`, which `setup.sh` sources, says its shell (SC2148) and that `targets` and `ports` come from `setup.sh` (SC2154). Nothing they do changes.
2. **`bundles/factory/tree/gates.py`:** the plan guard's checks of what the third project's broker refused only at a gate run:
   - **A time budget:** `budget_errors` refuses a gate whose worst case is over its run's job (`GATE_JOB_S`, `factory-gate.yml`'s `execute`, 300 minutes): the broker's own time, then every step it may run, to its timeout plus its stop margin, a release gate's own wait and the rollback included. The catalog declares the broker's time (`gate_overhead_s`, `step_margin_s`, `release_wait`), all optional, so every existing catalog still loads; without them the check counts the steps' timeouts alone.
   - **`release_gates` before the block:** `check_plan` checked it only for a release gate with a `gate-ops` block, so one without a block passed the plan guard and was refused only at the gate request.
   - **A gate with no steps** was already refused (`check_block`); a test pins it.
3. **`bundles/factory/tree/tests/test_gate_budget.py`:** new: the budget, the declarations, the gate shapes, and `GATE_JOB_S` tied to the template's `timeout-minutes`.
4. **`bundles/factory/tree/implement_guard.py`, `bundles/factory/seed/tests/test_codeowners.py`:** each profile's build files (what its tools load just because they exist) move from the seeded test into the guard (`PROFILE_BUILD_FILES`, `profile_build_files`), as the governing knowledge list already had. A seed never updates, so the third project's copy drifted at the first release that changed it; the seed's own copy lagged factory.md's list. `tests/test_implement_guard.py` ties the lists to the shipped profiles and to factory.md's globs.
5. **`knowledge/architecture/deployment-patterns.yaml`:** `concurrent_service_deploys`: services deployed concurrently from one merge keep their contracts (schemas, background-job arguments, payloads) add-only for a release, with the consuming side's startup wait and the producing side's two releases.
6. **`process/factory.md`:** D4 rule 3 names the catalog's time declarations and the budget; Enablement step 9 and § Stack Profiles say the guard keeps the profile's list and how an older seed's test takes it.
7. **`process/production-gates.md`:** a gate must fit its run; a release gate needs a broker that takes it with or without a block.
8. **`process/factory-runbook.md`:** § 4.3's catalog step declares the broker's time.
9. **`bundles/factory/seed/factory.json`:** review rule packs for FastAPI and SQLAlchemy beside the Django and ASP.NET Core ones (each line regex is near its 500-character cap, so they are rules of their own): Raw SQL (SQLAlchemy), with `text()`, a driver's own connection and SQL in a string, quoted or on a line of its own; Bulk write (SQLAlchemy); Access check (FastAPI); and Auth code, a paths rule. The configuration-read rule knows pydantic-settings. Every new regex was run on sample lines that must and mustn't match.
10. **`bundles/factory/tree/tests/test_implement_guard.py`:** the project's own line regexes are timed on long lines in a child process the test can stop, so one that backtracks fails CI with its rule's name instead of hanging a publish job (`implement_guard` has no regex timeout). A rule that never finished was caught and named.
11. **`process/factory.md` § Where to look:** the seed's packs, and the timing test.
12. **The factory's enablement runs from the runbook, not a skill of its own:** the entry above this one (runbooks).
13. **`bundles/factory/tree/ci_audit.py`, `tests/test_ci_audit.py` (41 tests):** new: Enablement step 10's procedure, report only. It reads every workflow (PyYAML, reusing `workflow_policy.py`'s runner and local-action readers): triggers and which branch's copy each runs, each job's runners, container, environment, token and checkouts, and every secret it references. A job that runs agent-written code is held to step 10's rules: no secret, `persist-credentials: false`, a read-only token, a hosted runner or the CI tier; `pull_request_target` checking out the PR's head is a finding anywhere. With `--repo` it asks `gh` for secret names at each level, so a referenced secret that exists nowhere is a finding (the third project's first reading missed one), and a level it can't read is "not checked", never empty; `--runs N` shows scheduled workflows' real gaps. Exit 0 clean, 1 findings, 2 usage. Run live, read-only, on the third project: it read every level's secret names and the scheduled runs' gaps. A missing secret in a `factory-*.yml` workflow is info, not a finding: the templates reference optional slots (`FACTORY_SVC_2..4`, a planning database's password, Context7) that read as empty by design, and `bootstrap.py` checks the ones the factory needs. Without that, every factory project's audit failed on them.
14. **`bundles/factory/tree/planning_reader.py`, `tests/test_planning_reader.py` (39 tests):** new: D3 rule 3's read-only login, generated from PostgreSQL's own catalog instead of an ORM's models, so it works for any stack (the incubator's walks Django models; the third project wrote its own for SQLAlchemy, and review found its first version allowed unknown short text and `_id` names by default). Standard library only. `catalog-query` prints the query; `update` classifies every column (CD's overrides with reasons, then credential, payment and personal names, foreign keys capped at their target's class, integer or uuid keys, types that can hold anything, id-like names without a foreign key, and only then safe types and enum-like labels) and writes the listing, `create_role.sql` (column grants, the PUBLIC revokes of large-object writes, `TEMPORARY` and `CONNECT` elsewhere, role limits) and `verify_role.sql` (a superset of `planning-services.sh`'s reader check, which a test ties to the script); `check` fails a project's CI when a migration adds a column the listing lacks. Proven on a throwaway PostgreSQL 17 cluster: the role SQL runs and reruns, verify passes, the reader check finds nothing, allowed columns read and excluded ones are refused (in a `WHERE` too), writes are refused by privilege inside an explicit read-write transaction, temporary tables, large objects and other databases are refused while the app role keeps them, and `check` fails on a migration's new column, which stays unreadable.
15. **`process/factory.md` (D3 rule 3, Enablement step 10), `process/factory-runbook.md` (§ 2 item 4, § 4.2):** name the reader generator and the CI audit.
16. **`skills/sdlc-migrate/SKILL.md` § 2.0a:** a skill or process doc an installed bundle gained since `source_version` is new, not declined, and is installed; "the project chose its subset" covers only a file the bundle listed then. Without it, a migration could read a bundle's new file (this release's `process/runbooks.md` is core, but a bundle's next process doc won't be) as one the project chose not to take.

17. **`docs/current_work/ideas/factory-enablement-upstream_handoff.md` (removed), `factory-broker-bundle_plan.md` (new):** the list's items are built, dropped (the provenance alarm, CD 2026-11-13) or declined (the drill checklist), so the list is gone. The broker (item 1) is not built. CD chose an opt-in bundle whose fixes flow downstream through migration, then answered the design's four questions: the bundle tree's contract (the bundle owns the generic broker, the project its host module), root running no project code, the whole bundle piloted on the third project before it debuts, and the request client moved into the factory bundle. A read-only map of the third project's broker found it a redesign more than an extraction (about 2,100 generic broker lines, a 1,100-line setup script, 350 to 390 of 587 tests to port), and found that its live broker accepts an ops gate's rollback and never runs it. The new plan holds the map's findings, the layout, CD's answers and the build's phases; it's committed with the broker's build.

**Rationale:** Each was built once by hand in the third project, or found missing there. A refusal that comes only at a release gate's run comes after the deploy, so the plan guard has to make it first; and a list a seed copies drifts silently, where one the bundle code holds migrates.

---

## 2026-11-16: The factory imported from the incubator (cccad04..6094011): z-sdlc's follow-ups, handed back

**Origin:** The entry below, handed to the incubator with `--to-incubator` and merged there (CD, 2026-11-16).

**What happened:** The incubator took z-sdlc's 10 changed bundle files, and its copies of `factory.md`, the runbook and `sdlc-revise`, as they were. Its factory tests passed (681, 46 skipped), and so did its render check and workflow policy. The report against the merge shows the bundle code in sync and nothing needing a person.

**Changes made:**
1. **`.claude/skills/zsdlc-import-factory/import.json`:** `last_import` is `6094011`. Nothing was copied.
2. **`docs/current_work/ideas/factory-ci-tier-follow-ups_handoff.md`:** the hand-off is done, and was removed afterwards.

**Rationale:** Until the merge was recorded, the next z-sdlc change to one of these files would have read as a conflict, as if both sides had changed it.

---

## 2026-11-16: The CI tier's and the runner audit's follow-ups from v2.1.0's review

**Origin:** `docs/current_work/ideas/factory-ci-tier-follow-ups_handoff.md`. The pilot project's three release reviews of v2.1.0 (2026-10-15), and the incubator's review of that import, passed 17 findings as minor, to follow the tag. They stayed pending for a month. CD (2026-11-16): "lets address them all now". Item 15, reading the organization's audit log, had already moved to its own handoff (`runner-audit-reads-audit-log_handoff.md`), and stays there.

**Upgrading:**
- **A project with a CI tier:** run its setup again after the migration that brings this (`sudo TIER=ci bash .github/factory/host/setup.sh`). It writes the slot count into the launcher's settings and the slots' new unit.
- **The shared host's own repository:** copy the bundle's `host/` at the release's tag, then run the strict and planning tiers' setup again. Nothing changes on the host until then.
- **The runner audit:** regenerate its workflow (`runner_audit.py workflow expected.json`, Enablement step 12) to get the rename and malformed-answer handling. The expected state doesn't change.
- **`policy.hosted_labels`:** `x86` is now refused there as one of GitHub's default labels (item 8). A project whose `factory.json` names it fails its workflow policy check, and every PR's CI with it, until `x86` is removed.

**What happened, and the changes made** (by the handoff's numbers):
1. **A registration could leak when SIGTERM landed inside `generate-jitconfig`.** GitHub had registered the runner, but the cycle never heard its ID. `host/ci_launcher.py` now writes the runner's name to `slot-N.pending-<suffix>` before it asks. A later cycle and the slot's stop look that name up (`GET orgs/<org>/actions/runners?name=`, matched exactly) and turn a registration they find into a leftover record, which is then removed. A marker with no registration behind it is dropped once it's `PENDING_SETTLE` (300 s) old, since the request may still have been in flight. `retire` counts a marker's registration as one of the slot's but leaves the marker, since its cycle may still be running. A slot beyond the count (item 2) never runs another cycle, so slot 1's cycles remove what such a slot left: a registration made after its stop looked, or one GitHub wouldn't remove then (`retired_slots`). Only slot 1 does this, so two cycles never do it at once. It asks GitHub first, as `retire` does, and leaves a registration GitHub calls busy as it is, record and all, since the retired slot's last cycle may still be running its job. The handoff's start, a sweep by the slot's name prefix, could remove the slot's own live runner. An exact name can't.
2. **Lowering `CI_RUNNERS` killed a job on an excess slot.** `host/setup-ci.sh` now writes `slots` into `launcher.json` and disables an excess slot without stopping it. It stops the slot only when `retire` answers idle. A busy one finishes its job, and its next cycle exits 12 (`RETIRED`), which the slot unit's `SuccessExitStatus=`/`RestartPreventExitStatus=` keep from restarting. A disable alone wouldn't have held it, since `Restart=always` starts the next cycle as soon as the job ends.
3. **The image build directory could leak, and old images went first.** `setup.sh`'s one exit trap now also removes `CI_BUILD`. A trap of `setup-ci.sh`'s own would have replaced it, since that file is sourced. Directories an earlier run left are removed before a new one is made. Earlier job images are pruned only after the check passes on the new one. That happens on every run whose check passes, the image kept or not, since a run whose check failed pruned nothing.
4. **and 6. The pre-release migration code is gone:** the `/run/factory-runner/<unit>` reads in `record_files()`, the `legacy_state_dir` setting, and `setup-ci.sh`'s tmpfiles removal and carry-over loop. Item 4, the loose old-state directory read silently, goes with them. The handoff's condition held: the only host with a pre-release CI tier, the pilot project's runner host, ran v2.1.0's setup on the evening of 2026-10-15, as the pilot project's runbook records.
5. **A 404 from the wrong organization read as "gone".** `retire` and the leftover removal now take a 404 on a runner as gone only once the organization's runner list has answered 200 in the same call (`org_answers`, at most once per call). The check is never made in `runner_state`, which every normal cycle ends on with a 404.
7. **A strict- or planning-tier runner could be left stopped by a failed download.** `setup.sh`'s new `runner_install` downloads and checks the archive first. It looks at `Runner.Worker` again after the download, then stops the runner and unpacks. A failed download dies with the runner as it was.
8. **The default runner labels were in five places, not four.** `workflow_policy.py` had a copy too, without `x86`. It now has `x86`, so `x86` can no longer be named in `policy.hosted_labels`. The handoff's start was one file the scripts all read. None can: the audit is written whole into a workflow, the launcher is installed alone, and the bootstrap stages only named files from the tier owner's repository. So each script keeps its copy, and a new `bundles/factory/tree/tests/test_runner_labels.py` holds `ci_launcher.py`, `runner_audit.py`, `workflow_policy.py` and `setup.sh` to one set. `tests/test_factory_runner_labels.py` (z-sdlc's own) holds the docs to it.
9. **`process/factory.md`**, Enablement step 8: a Runner labels paragraph names GitHub's default labels and says what the factory does with them.
10. **The planning database's address in two places.** Since the shared tiers moved to the host's own repository (2026-11-06), the firewall's address (`host.conf`) and each project's (`planning.json`) are in different repositories, and setup never sees `planning.json`. The handoff's start, a check in setup, would never run. So D3 rule 2 says the two must agree and nothing compares them, and `planning-services.sh`'s can't-reach error, on a private or tailnet address, names both settings.
11. **`setup.sh`'s header** says a planning database port is on this host's own addresses or on `PLANNING_DB_HOST`'s.
12. **An `nftables` upgrade can change the firewall's fingerprint.** The handoff's start offered a narrower fingerprint or a note. A narrower one would trip every CI tier on upgrade, since the minute timer runs the installed launcher until setup replaces it. So: Enablement step 10's checks say to check the table and run setup again after an `nftables` upgrade, and the trip's message names that cause.
13. **`PLANNING_DB_HOST`'s other ports were never probed.** The planning tier's isolation test now probes every `PROBE_PORTS` port but the database's on `PLANNING_DB_HOST`, when that address is in the firewall's blocked set. `db_host_other_ports` reads the set from the firewall file setup has just written, so there's one list. An address outside it is reached as the internet is, so it's not probed, and setup says so.
14. **A malformed answer could raise `TypeError` in the audit's `check`,** and exit 1 (drift). `runner_audit.py`'s `current()` checks each field's type where it's read (the group's settings, `selected_workflows`, repositories, runner labels) and raises `Unreadable`, exit 2, with the reason on stdout, which the alarm's issue carries. `main()` takes `TypeError`, `KeyError` and `AttributeError` as exit 2 too, as a backstop.
16. **A renamed group read as one gone and one new.** `drift()` matches them by ID and reports one line, `renamed <new name>`. It compares the group's settings, lists and runners with the expected entry, and its runners' factory labels keep their home.
17. **The real-Docker smoke test pulled from Docker Hub.** `test_a_real_daemon_takes_the_job_flags` now imports an image made of nothing but a hand-built static program that exits 0 (x86-64 or arm64, by the daemon's architecture). So it pulls nothing, and a flag the daemon refuses still fails it. Tried on a local daemon, on both architectures, with `compress=false` taken out (exit 125).

An independent review of the change found nothing critical or major. Its three minor findings are fixed: old images left after a failed check, a retired slot's late registration, and a SIGTERM test that depended on timing (the fake's answer now waits for an event). A last look found that the fix for the second, slot 1's sweep, could send a DELETE at a retired slot's busy runner, so the sweep now asks first. The reviewer's second look at the sweep and the pruning found three narrow races, all fixed:
- a removal GitHub refused under the sweep moved a live cycle's record to a leftover, which could let `retire` answer idle; such a record now stays where it is;
- the sweep used the slot count from its cycle's start, up to a backoff's ten minutes old, so it now reads the settings' file again;
- two processes writing one record shared a temporary name, so each now writes through one of its own (`.<record>.<pid>.new`), hidden from the records' globs.

The `missing_ok` on a cycle's own marker got its test too. `planning-services.sh`'s new message (item 10) is untested here: reaching it needs pgbouncer in the job container, which `factory-smoke` runs.

Tests: `tests/test_ci_launcher.py` (pending markers through a SIGTERM inside the call, the in-flight case included, and one dropped once old; a wrong organization's 404; a slot beyond the count, and slot 1 removing what it left), `tests/test_host_setup.py` (`runner_install`'s order, `db_host_other_ports`, the units and the trap) and `tests/test_runner_audit.py` (malformed answers, a rename). The handoff is removed (CD, 2026-11-16): every item is done but 15, which has its own handoff, now pointing here.

**Rationale:** Each of these passed review as minor, so none was ever a breach. Most were a cleanup that could leak, or an error that misnamed its cause. Three of the handoff's starts no longer fit the code: the host's own repository has no `planning.json`, a prefix sweep can catch a live runner, and no file reaches every script that needs the labels. Where a start didn't fit, the fix went where the problem actually shows. Release type: patch.

---

## 2026-11-14: The installed framework catches up with itself and with current models [contract-change]

**Origin:** A prompt audit of everything `skeleton/manifest.json` installs, plus `CLAUDE-SDLC.md`, the installer and both bootstraps, against Claude Opus 5.5, Sonnet 5.5 for the execution skills and `model: sonnet` agents, and Fable 5.2 too for the planning skills. [contract-change] for the knowledge-store glob in item 1: the adapter's mapping table already transforms the new form (`pattern-mapping-rules.md`, the `([sdlc-root]/knowledge/**/*.yaml)` parenthetical and the table-cell rule), so the plugin needs no paired edit.

**What happened:** Most of what the audit found was stale cross-references and rules that had come to contradict newer ones, not old-model prompting. A fresh project's catalog had no `Next ID` line, which `sdlc-plan` stops on. `sdlc-archive` never looked in `sdlc-lite/completed/`. The compliance auditor's exemptions named statuses that don't exist. Four places still said "agent-first, always" or "no size exceptions" against the Manager Rule's Delegation Economics Exception. The commit template pinned `Claude Opus 4.6 (1M context)`, the planning advice named Fable 5 and Opus 4.8, and the OpenCode example named `claude-sonnet-4-5`, which retires on 2026-11-30. Knowledge recommended "think step by step", keep-tail compaction, and treating low effort on a top model as waste.

**Changes made:**
1. **Knowledge-store glob:** `CLAUDE-SDLC.md` (commit-completeness table), `sdlc-execute` and `sdlc-lite-execute` scan `[sdlc-root]/knowledge/**/*.yaml`; `knowledge/*.md` matched only the READMEs, so every store change was missed. The framework-dev `defect-catalog.md` idiom list follows.
2. **`CLAUDE-SDLC.md`:** the ID threshold is "more than one human–AI coordination cycle", not 30 minutes (§ Estimation forbids cardinal time). The "Agent-first, always" paragraph and the "default to asking" bullet under the STOP list go: § Manager Rule and the tier question already cover them. The changelog rule is said once, with its reason. "Assumptions are forbidden" becomes "Verify before you rely on it", scoped to external behavior. The Unbuilt-Capability Rule is one paragraph under the same heading. The planning-model example and the two settings sentences current Claude Code contradicts (`model` is a settings key; `/model` saves the default) are removed. The `\\n` frontmatter rule keeps its reason and loses its history.
3. **Commit templates** in `sdlc-execute`, `sdlc-lite-execute` and `sdlc-tests-run`: `{Co-Authored-By trailer, if your harness specifies one}` in place of a pinned model. **`sdlc-port-opencode`:** `anthropic/claude-sonnet-5-5`.
4. **Lifecycle skills:** `sdlc-walkthru` ends on the Approval Brief instead of `AskUserQuestion`. `sdlc-plan` and `sdlc-lite-plan` no longer assume lite plans execute in the same session, and `sdlc-plan` loses "the plan is already approved" and its dangling labels (Iron Law 2, §3c, a Pre-Dispatch block). `sdlc-execute` and `sdlc-lite-execute` glob `*_idea-brief.md`, point to `agent-selection.yaml` for agent tables, say where status goes instead of forbidding narration, and keep each rule without its incident history; `db-architect` becomes `data-architect`. `sdlc-archive` covers `sdlc-lite/completed/`. `sdlc-handoff` no longer says `sdlc-status` surfaces handoffs. `sdlc-explain` keeps its credit and drops its rename history. The github-provenance `sdlc-lite-execute` fragment says lite runs the full review loop.
5. **Specialist and authoring skills:** `sdlc-develop-skill`'s activation rule says write a trigger, not a summary, with no capitals, and trigger phrases cover distinct intents rather than synonyms; `sdlc-migrate` and `context-engineering-patterns.yaml` follow. `sdlc-debug-incident` points to C9 and states its return shape instead of a word cap. `sdlc-manage-github` labels go through the REST call Recipe 1 uses. `sdlc-ingest` drops `/feature-compare`. `sdlc-research` writes the curated doc itself. `sdlc-design-consult` drops the removed design-for-ai skill. `sdlc-tests-run` routes test writing to `sdlc-tests-create`. `local-model-serving.md` dates its external-tool facts.
6. **Installer, migration, audit, agents:** `sdlc-initialize` seeds `Next ID: **D1**` (so does `skeleton/manifest.json`'s `deliverable_catalog_template`), seeds and assesses every discipline file (dx and observability were missing), counts the audit's dimensions correctly, and states the Manager Rule with its exception. `lite-graduation.md` names `CLAUDE-SDLC.md`. `sdlc-migrate` cites §2.0 and `.claude/agents/`, says "say when the skill applies" for trigger framing, names `sdlc-develop-skill`'s counterpart, and drops its red-flag count and migration-relative phrasing; its `red-flags.md` uses an explicit ref instead of `HEAD:` and cites `[sdlc-root]/process/source-repo-safety.md`; `recovery-procedures.md` uses `[target_tag]`. `sdlc-compliance-auditor` uses real statuses. `compliance-methodology.md` lists dx, observability, `dx/` and `search/` and uses the auditor's four-level scale; it and `sdlc-audit` call it the auditor's source of truth instead of "migrated from" the agent. `sdlc-reviewer` checks MEMORY.md at 200 lines or 25KB and loses the parser history, as do `sdlc-develop-agent` and `agent-template.md`. `AGENT_SUGGESTIONS.md`'s prompt-engineer puts native thinking, effort and structured outputs first, and its defaults line matches the entries.
7. **Process docs, templates, bootstraps:** `process/README.md`, `ad_hoc_reconciliation.md` and `parallel-dispatch-monitoring.md` agree with `manager-rule.md` (no revert by the orchestrator). `commands.md` sizes lite by complexity, not file count. `finding-classification.md` heads six classifications and drops the team-skill metadata. `compliance_audit.md` checks the templates and CLAUDE.md sections that exist. `external-review-gate.md`'s path resolves. `disciplines/README.md` names `sdlc-design-consult` and skills that exist. `playbooks/README.md` quotes nothing no skill says. `production-gates.md`'s example keeps the 7-phase limit. `collaboration_model.md` and `ad_hoc_reconciliation.md` ask their example questions through `AskUserQuestion`. `review-fix-loop.md` keeps the rule and drops the fixed false-positive statistic and migration-relative phrasing; `security-review-taxonomy.yaml` dates and scopes the same statistic. `skill-agent-review.md` gives the `<example>` limit its reason. `agent-template.md`'s opus line no longer says "most capable". `BOOTSTRAP-LITE.md` asks for 1-2 examples without commentary and the boundary sentence, drops `/sdlc-review-fix`, updates its knowledge count, and names the steps that wait for user input (2, 3 and 9) in place of "do not narrate".
8. **Knowledge:** `prompt-engineering-patterns.yaml` notes that current Claude models take effort settings instead of a request for visible reasoning, and server-side compaction, context editing or a whole-history summary instead of keep-tail; "JSON only" and sentence caps become structured outputs and length by reader need. `model-tier-strategy.yaml` drops the pinned planning model, "low effort wastes a top model", and `high (→ xhigh/max)`; low-effort mechanical edits run a real check before reporting done. `skill-quality-rubrics.yaml` SQR-03 exempts Orchestration skills from the routing ban. `token-economics.yaml` sizes knowledge files by topic, not "< 200 lines". The `knowledge/`, `architecture/`, `business-analysis/`, `coding/` and `design/` READMEs list the files that exist.
9. **Factory bundle:** `factory-runbook.md` drops the step count, `process/factory.md` says implement sets `factory:review-capped` too, and `sdlc-revise` says its narrowed roster holds against the mirrored mechanics.

**Rationale:** A rule an older line contradicts gets followed half the time, and a pointer to a status, path or skill that doesn't exist sends the next session looking for it. Current models follow instructions literally, so stale model names, word caps and incident stories read as standing orders.

---

## 2026-11-13: The import tooling names no project; research dispatches suggest; skills here stop routing to skills that don't load here

**Origin:** CD's decisions on the open items of the prompt audit in the entry below.

**What happened:** `zsdlc-import-factory`'s skill, script and `import.json` named the incubator, against § z-sdlc is public in `CLAUDE.md`. `zsdlc-research` required the dispatch to prescribe search queries and entry points, and also said search method is the agent's. Anti-triggers in the framework-development skills sent work to installed-project skills (`sdlc-idea`, `sdlc-plan`, `sdlc-lite-plan`, `sdlc-playbook-generate`, `sdlc-develop-agent`) that never load in z-sdlc source. `zsdlc-audit-adapter-installation` hard-coded a home path for z-sdlc's clone, and one of its sentences was garbled.

**Changes made:**
1. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`:** the incubator's clone is the argument, or else the path in the untracked `.claude/incubator-clone.txt`; with neither, it exits 2. Every name in `.claude/private-names.txt` is checked like a `specific` pattern and kept out of the rules `--apply` writes back. A missing or empty names file is a [fix first] item, so `--apply` refuses. The report and the changelog hint say "the incubator".
2. **`.claude/skills/zsdlc-import-factory/import.json`:** no `incubator` key and no name among `specific`; `_doc` says where both come from now.
3. **`.claude/skills/zsdlc-import-factory/SKILL.md`:** "the incubator" throughout, so the trigger that named it is now "import from the incubator". The commands take no path, and the argument, preconditions, exit codes and Integration name the two untracked files.
4. **`tests/test_import_factory.py`:** a name from the names file is flagged and never written to `import.json`; a missing names file blocks `--apply`; the clone defaults to the local file; no clone and no file is exit 2.
5. **`CLAUDE.md`** § z-sdlc is public: the import checks for the names in check 6's file too.
6. **`.claude/skills/zsdlc-research/SKILL.md`:** a dispatch carries suggested queries and entry points the agent may change, in place of required ones, which matches its rule that search method is the agent's.
7. **`.claude/skills/zsdlc-research/`, `zsdlc-ingest/`, `zsdlc-audit/` and `zsdlc-create-skill/` `SKILL.md`:** anti-triggers, agent-creation lines and `zsdlc-audit`'s playbook-proposal line keep their boundary and no longer name a skill that doesn't load here.
8. **`.claude/skills/zsdlc-audit-adapter-installation/SKILL.md`**, **`references/exempt-file-list.md`** and **`references/classification-framework.md`:** source paths are relative to the z-sdlc root the skill runs from. Step 2a's count reads "recent runs against the target".

**Rationale:** Tooling in a public repo that carries a private name publishes it with every commit that touches it; it now reads the name where check 6 does. A pointer to a skill that can't load sends a session nowhere.

---

## 2026-11-13: The framework subagents are told they're in the source repo; the framework-development skills catch up with the consolidations

**Origin:** A prompt audit of the Claude Code configuration that loads in this repo.

**What happened:** `.claude/agents` has been a symlink to `agents/` since 2026-04-22, so `sdlc-compliance-auditor` and `sdlc-reviewer` load here with their installed-project brief (`.claude/skills/sdlc-*`, `docs/_index.md`, `[sdlc-root]` as `ops/sdlc`), while `CLAUDE.md`'s location table said neither runs in z-sdlc source. `zsdlc-audit` and `zsdlc-create-skill` dispatched them without saying where they were. The framework-development skills also still named `setup.sh` (removed), `enrich-agent`, `sdlc-reconcile`, `design-consult` and `sdlc-review` (consolidated), `sdlc-create-skill` (folded into `sdlc-develop-skill`), the installed-project `sdlc-ingest` where `zsdlc-ingest` is meant, and an `audit` skill that doesn't exist.

**Changes made:**
1. **`CLAUDE.md`** § Skill/Agent Location Convention: `agents/` gets its own row. Its subagents load here too, through the symlink, and a z-sdlc skill that dispatches one tells it it's in the source repo.
2. **`.claude/skills/zsdlc-audit/SKILL.md`:** the dispatch prompt names this skill's methodology and its 10 dimensions, and says `[sdlc-root]` is the repo root. Dimension 9 is installer correctness (`sdlc-initialize`, `sdlc-migrate`). The bulk-import anti-trigger names `zsdlc-ingest`, and the reference list says 10 dimensions. The improvement mode's "looks fine" red flag allows a clean result.
3. **`.claude/skills/zsdlc-audit/references/compliance-methodology.md`:** 10 dimensions. Dimension 9 checks `process/path-mappings.md`, `sdlc-initialize` Phase 1 and `sdlc-migrate` §2.1 instead of `setup.sh`, in the sequence, the report format and the severity levels. **`session-reading.md`** and **`improvement-methodology.md`:** their `setup.sh` lines name the installers, and the example proposal names `zsdlc-create-skill`.
4. **`.claude/skills/zsdlc-create-skill/SKILL.md`:** the quality gate tells `sdlc-reviewer` it's in the source repo, that `skills/{name}/SKILL.md` is a skill and that `[sdlc-root]` is the repo root. The type examples drop `sdlc-reconcile` and name `sdlc-design-consult`. Integration names the installers and `sdlc-reviewer`. The frontmatter rule is stated plainly, with its reason.
5. **`.claude/skills/zsdlc-ingest/SKILL.md`:** skills go to `zsdlc-create-skill`, and child projects receive changes through `sdlc-migrate`.
6. **`.claude/skills/zsdlc-research/SKILL.md`:** `zsdlc-ingest` throughout.
7. **`.claude/skills/zsdlc-audit-adapter-installation/SKILL.md`:** z-sdlc source is audited with `zsdlc-audit`, and a bare install goes to the target's own `sdlc-audit`. Scans 3b and 3c keep the reason they exist and lose the story of the migration that prompted them. The report template's instruction loses its capitals.
8. **`process/path-mappings.md`:** `zsdlc-audit`'s row says installer correctness, not `setup.sh`.

**Rationale:** A subagent follows its own brief unless the dispatch says otherwise, and a skill that names something removed sends the next session looking for it.

---

## 2026-11-12: The factory imported from the incubator (cbfcde0..cccad04): the CI launcher's cycle test

**Origin:** The fix for the test the last import's proof failed (the entry below), merged in the incubator.

**What happened:** One bundle file changed and nothing needed a person.

**Changes made:**
1. **`bundles/factory/tree/tests/test_ci_launcher.py`:** `test_a_cycle` checks the token and the registration exactly, then one or more polls of the runner and nothing else. How many polls fit before the fake container exits depends on how fast the machine starts a process.
2. **`.claude/skills/zsdlc-import-factory/import.json`:** `last_import` is `cccad04`.

**Rationale:** A proof that fails on a machine's speed hides a real failure behind a known one.

---

## 2026-11-12: The factory imported from the incubator (7c07be1..cbfcde0): the sessions App's helper, one review standard

**Origin:** CD merged the incubator's two PRs for the three entries below. The first handed back z-sdlc's changes since the last import. The second, the sessions App and the review standard, was stacked on it and merged into it before it reached the default branch.

**What happened:** The report found `bootstrap.py` and its tests changed on both sides. The hand-back had made the incubator's copies identical to z-sdlc's (checked at its head before the second PR merged into it), and the review standard was built on them, so `--apply --accept` takes the incubator's, z-sdlc's change included. The incubator's own CODEOWNERS test changed too: it's the bundle's seed with the incubator's paths filled in, so the seed needs nothing. Nothing was flagged as incubator-specific, and the skills and process docs were already in sync.

The proof passed in the incubator. In the empty project one test failed, `tests/test_ci_launcher.py`'s `test_a_cycle`, which counts the launcher's polls of its runner while a fake container runs. The launcher polls every 0.1 seconds, and the fake `docker wait` is a Python script that exits as soon as it starts. On CD's Mac, starting it took longer than that, so the launcher polled two to four times where the test expects one. Run alone, it failed five times out of five on this import's bundle and twice out of three on the bundle before it; the import changes neither the launcher nor its test, and the incubator's CI passed it. CD had the import committed anyway and the test fixed in the incubator first, to come with the next import.

**Changes made:**
1. **`bundles/factory/tree/`:**
   - `session_identity.py` and `tests/test_session_identity.py` (new): the sessions App's helper, Enablement step 13.
   - `create_app.py`: `--sessions`.
   - `bootstrap.py` and its tests: every default branch needs one approving review, dismissed by a new push, no last-push approval and merge commits only.
2. **`.claude/skills/zsdlc-import-factory/import.json`:** `last_import` is `cbfcde0`.

**Installed projects:** a migration brings the files. The review standard's and the sessions App's entries below say what each asks of a project: `bootstrap.py` reports a default branch that differs from the standard, and the helper does nothing until CD runs its `install`.

**Rationale:** The factory's code comes only from its incubator, and an import that takes a file changed on both sides has to find z-sdlc's side already there.

---

## 2026-11-12: The sessions App's name, description and logo, and what renaming it does

**Origin:** CD renamed the organization's sessions App the same day, gave it a description and a logo, and said "document it".

**What happened:** The rename changed the App's slug and its bot's login, but not its ID, key, client ID or installation. The helper's recorded login, and so the commit author of every new session, stayed the old one until `session_identity.py install` ran again. A commit made under the old name still showed as the bot, since GitHub matches the bot's noreply address by its ID. The first name CD wanted was already another account's: App names are unique across GitHub.

**Changes made:**
1. **`process/factory.md`:** Enablement step 13, setup item 1: the App's default name, a description and a logo that pairs with the factory App's, and running `install` again after a rename.
2. **`process/factory-runbook.md`:** § 5: a pitfall, a renamed sessions App whose new sessions still commit under the old login.

**Rationale:** The App's name and logo are what a reviewer sees on every PR a session opens, and a rename is the one change to the App that the machine running the sessions doesn't pick up by itself.

---

## 2026-11-12: Sessions on CD's machine work as the sessions App in the product's repositories

**Origin:** The App trial of 2026-11-11 (the entry below that one) wired one scratch session to an App by hand. CD (2026-11-12): "create the token helper and yes, i want sessions on product repos authoring as the app instaed of me. as far as permissions, I would say that app sessions should deal with app code, and use my login for anything dealing with infra/setup changes."

**On migrating:** Nothing changes for a project until CD sets it up (Enablement step 13): the sessions App, created once per organization with `create_app.py --sessions` and installed on the product's repositories only, then `session_identity.py install` on CD's machine. After that, CD's new sessions in those repositories commit, push and open PRs as the App, which CD approves and merges like any PR. Infra and setup PRs stay CD's, merged with the bypass. `session_identity.py` and `create_app.py --sessions` are written in the incubator first and reach the bundle with its next import; until then, a project takes them from the incubator.

**What happened:** The trial's helper was a scratch script that made a whole clone the App: its remote, credential helper and commit author. That made CD's own terminal in the clone the App too, and left no way to do infra work as CD in the same session. Its one session commit carried CD's signature under the App's name, which GitHub shows as unverified (CD signs every commit). And when no token could be had, `GH_TOKEN` was empty, so `gh` would quietly fall back to CD's login.

**Changes made:**
1. **`process/factory.md`:**
   - Enablement step 13, sessions' identity: what is the App's (the product's code) and what is CD's own login (a path CODEOWNERS gives an owner, and anything outside the repository's files). It covers how `session_identity.py` sets a session up and what that contains (nothing, while CD's login is in reach), and the setup.
   - D2 rule 6: the sessions App has no `workflows` permission, and a session's token is narrowed to one repository and the session's permissions.
2. **`process/factory-runbook.md`:**
   - § 1 A3: the sessions App is the usual answer, with infra and setup on CD's login.
   - § 3.3 item 8: step 13 in sitting 1.
   - § 4.5: the sessions App among the organization's pieces.
   - § 5: two pitfalls, an App installed on every repository and a session's commits signed with CD's key.
3. **The incubator's `.github/factory/` (code, imported next):**
   - `session_identity.py`, with its tests. Its SessionStart hook, in CD's user settings only, puts the App's identity in the session's environment (`CLAUDE_ENV_FILE`), never the clone's git config: `GH_TOKEN`, the bot as commit author, and git's credential helper, HTTPS for SSH remotes and signing off, through `GIT_CONFIG_*`. A token is minted for one repository with the session's permissions, whatever else the App holds, and cached until ten minutes before it expires. Without one, `gh` and git fail, and the session is told why. `as-owner -- <command>` runs one command as CD's login. `install` records the App and adds the hook once.
   - `create_app.py --sessions`.

**Rationale:** The App's PRs carry a person's approval, CD's, while CD's own PRs show as bypasses, so the record says who wrote what. Putting the identity in the session's environment, not the clone, lets the session work as both the App and CD, and leaves CD's own terminal alone. Infra and setup stay with CD's login because GitHub refuses the App workflow changes, and settings, rulesets and secrets are beyond a product change's reach. It contains nothing: a session can still reach CD's login, and the docs say so.

---

## 2026-11-12: Every factory project's default branch takes the same review

**Origin:** After the bypasses were standardized, the four factory repositories' default-branch rulesets still differed. CD (2026-11-12): "standardize the remaining ruleset differences too - 1 approving review, disallow squashing/rebase merges (i'll handle that via driving sessions), no last approval push and the runner audit should require code owner review".

**On migrating:** `bootstrap.py` reports a default branch that:
- requires no approving review;
- doesn't dismiss approvals on push;
- requires last-push approval;
- allows squash or rebase merges, now on every project, not only on the fallback with a production tier.

Set each in the default branch's ruleset, and allow merge commits only in the repository's settings too. A linear-history rule refuses merge commits, so drop it. A repository with no CODEOWNERS file gets one, or code-owner review asks nothing. After that, every PR merges with a merge commit: a session squashes a PR's commits before review when they should be one.

**What happened:**
- One project required no approving review, which the team rule from 2026-11-11 covered in practice.
- Two allowed squash and rebase merges and required last-push approval, and one of those also required linear history with merge commits turned off.
- The runner audit's repository didn't require code-owner review, and had no CODEOWNERS file for it to read.
- `bootstrap.py` checked merge methods only on the fallback with a production tier, and checked neither the approval count, stale-approval dismissal nor last-push approval.

**Changes made:**
1. **`process/factory.md`:**
   - Enablement step 9: the same review on every project's `main`. That is one approving review, which a push dismisses; no last-push approval; and merge commits only, with no linear-history rule.
   - Step 9's fallback bullet keeps the production reason for merge commits, now as a second reason.
2. **`process/factory-runbook.md`:**
   - § 3.3 item 6: the standard. A repository without a CODEOWNERS file gets `* @<CD>`.
   - § 5: three pitfalls: last-push approval, linear history with merge commits only, and code-owner review without a CODEOWNERS file.
3. **The incubator's `bootstrap.py` and its tests (imported next):** `check_branch_rules` reads the approval count, stale-approval dismissal and last-push approval, from rulesets and classic protection alike, and checks merge methods on every project. The ruleset's allowed methods settle the merge check when the repository's settings can't be read.

**Rationale:**
- Without the dismissal, a push after CD's approval keeps it, and an App could merge what CD never saw.
- With the dismissal, last-push approval adds nothing but stopping CD from approving a PR CD last pushed to.
- Merge commits keep a PR's commits and their authors as reviewed, and CD wants squashing done in the session that drives a PR.
- One standard, checked by `bootstrap.py`, keeps the projects from drifting apart again.

---

## 2026-11-12: Every bypass of the factory's default branch is in pull-request mode

**Origin:** Adding the required-reviewers team showed two of the three factory projects with their default branch's bypass in mode "always". CD (2026-11-12): "switch the bypasses to pr mode - we should be standardized across all projects utilizing the software factory".

**On migrating:** `bootstrap.py` reports a default-branch ruleset whose bypass actor is in mode `always`, `exempt` or no mode (which means always). Switch each to pull requests only. After that, nothing reaches the default branch but a PR: an admin's direct push is refused. A project whose sessions or people pushed docs or migrations straight to it opens a PR for them instead, and an admin merges it with the bypass, which the ruleset's history records.

**What happened:** The runbook's § 3.3 step 6 already asked for `pull_request` bypass mode on the default branch, but `process/factory.md` step 9 didn't, and `bootstrap.py` checked bypass modes only on the release branch. So two of the three projects kept "always", which skips every rule, review and checks included, for a direct push. One of them took about 29 direct commits on its default branch in 30 days. The third project's ruleset, the runner host's and the runner audit's were already in pull-request mode. Step 3 and Enablement's opening also said to push to `main`, which pull-request mode refuses.

**Changes made:**
1. **`process/factory.md`:**
   - Enablement step 9: every bypass of `main`'s rulesets in pull-request mode, for every project the factory runs in. A tag ruleset is outside it.
   - Enablement's opening and step 3: settings and workflows are merged into `main` through a PR, not pushed to it.
2. **`process/factory-runbook.md`** § 5: the bypass pitfall's row says `bootstrap.py` checks the default branch too.
3. **`bundles/factory/tree/bootstrap.py`:** `check_branch_rules` reports each bypass actor of a default-branch ruleset that isn't in `pull_request` mode, reading a missing mode as always, as the release branch's check does. It checks the mode only, not who may bypass.
4. **`bundles/factory/tree/tests/test_bootstrap.py`:** the fake's default ruleset has a pull-request-mode bypass. A new test covers always, exempt and a missing mode, and a tag ruleset's always bypass being ignored.

**Rationale:** Code-owner review, the team and the required check guard what reaches `main` (D2 rule 6), and an "always" bypass skips all three without leaving a PR to read. In pull-request mode, a bypass still merges what an admin chooses, but always through a PR, and it's recorded as a bypass. Holding every project to it, and having `bootstrap.py` check it, keeps them from drifting apart again.

---

## 2026-11-11: A team of people must approve every file on the factory's default branch

**Origin:** CD asked what an identity of their own for agent sessions would take, short of a paid second account. A GitHub App of their own was tried on a scratch repository, and the trial found that an App's approval merges a PR CD opened. CD had the fix added to the third project's ruleset the same day, then said "go" to making it part of the factory's setup.

**On migrating:** `bootstrap.py` reports a new problem until the default branch's ruleset requires a team to approve every file. Add a team that only people CD trusts as reviewers are on (CD alone, usually) and give it write access to the repository. Then, in the ruleset's pull-request rule, add it as a required reviewer: file pattern `*`, one approval. After that, CD's own PRs merge only with the bypass, since CD can't approve their own. With one approval or more already required, that is no change. With none, it is a change: those PRs merged without a review before, and an App could merge them too.

**What happened:** On the scratch repository, with code-owner review and one approval required on `main`:
- an App can't approve its own PR, so its PRs needed CD's approval as code owner;
- GitHub asked no code-owner review of a PR CD opened, since CD was the only code owner of what it changed. The App's approval counted toward the one required, and the App, with contents write, merged it. The ruleset's history recorded a pass, not a bypass, on an owned path as on an unowned one;
- with a team holding only CD added as a required reviewer of `*`, the same App approval no longer satisfied the rule. It was tried on an `owned/` file, which CD then merged with the bypass, recorded as a bypass, and on `.github/` and `.claude/` files two and three directories deep, a PR closed unmerged. With 0 approvals required, the team still blocked the App's merge, with or without the App's approval;
- a PR the App opened, approved by CD, merged with a pass.

The factory's own App could approve PRs the same way, as could any App the organization installs with pull-request write. A session working as CD's login could merge with CD's bypass all along; the team only makes the record honest about it.

**Changes made:**
1. **`process/factory.md`:**
   - D2 rule 6: the team is part of the boundary against a malicious change, with why.
   - Enablement step 9: the team, its pattern and approval count, and that it must be a ruleset (branch protection has nothing like it).
2. **`process/factory-runbook.md`:**
   - § 1 A3: a GitHub App of the sessions' own is an option, no seat needed (its token helper isn't in the bundle yet). An identity of their own names who acted, but contains nothing while a session can reach CD's login. The team is needed whichever answer is chosen.
   - § 3.3 step 6: the team in the default branch's ruleset.
   - § 5: a pitfalls row.
3. **`bundles/factory/tree/bootstrap.py`:** `check_branch_rules` reports the default branch's rulesets lacking a team that approves every file. It reads a required reviewer only as a team, with at least one approval (0 only adds it for visibility), and exactly `*` among its patterns with no `!` line. A narrower or unproven pattern is reported, not guessed at (a leading space is part of a pattern in `.gitignore` syntax, so `" *"` is not `*`), and classic protection never counts. The fix was found in an installed project, so it goes straight into the bundle's tree; the incubator gets it with the next `--to-incubator`.
4. **`bundles/factory/tree/tests/test_bootstrap.py`:** the fake's default ruleset has the team. A new test covers a missing team, zero approvals, a reviewer that isn't a team, narrower patterns, `**`, `" *"`, a `!` line in either order, an extra narrower team beside the right one, and classic protection alone.

**Rationale:** Code-owner review is the factory's control on what reaches `main` (D2 rule 6). But GitHub doesn't ask it of a PR whose author is the only code owner, and that author is CD on every PR CD opens. Any App's approval then stood in for a person's. A team can't hold an App, so requiring one on every file means a merge into `main` carries a person's approval or shows as a bypass.

---

## 2026-11-11: The factory's templates take Dependabot's action pins; the bundle's pins move up

**Origin:** The third project's install session reported two problems from a week of Dependabot PRs. It relayed CD's choice to fix both upstream first; the project changes nothing locally until the bundle ships.

**On migrating:** this release moves the agent action to v1.0.266 and factory-smoke's Claude Code to 2.1.316. Run `factory-smoke` after the migration (D2 rule 5). A project that already copied these pins by hand still gets asked about those templates: take the release's copy, which matches.

**What happened:**
- **Dependabot breaks `render.py --check`.** Dependabot's `github-actions` updates edit only the rendered `.github/workflows/factory-*.yml`, because it scans `.github/workflows/` and a root `action.yml` and nothing else. So every actions bump touching a factory workflow failed `render.py --check` until someone copied the pins into the templates by hand. On one update the project did that across 15 templates. It also moved factory-smoke's `CLAUDE_CODE_VERSION` to the version the new agent action installs, and factory-smoke then passed on its default branch.
- **Re-rendering isn't the answer.** Re-rendering goes from template to workflow, so it would throw the bump away.
- **The project's templates had drifted from the bundle.** The 15 hand-edited templates no longer matched the bundle's copies. `sdlc-migrate` asks about each one either way, since it compares a file with its installed hash, but the release's copy is now the same content.

**Changes made:**
1. **`bundles/factory/tree/templates/`:** `actions/create-github-app-token` v3.2.0 → v3.3.0 and `anthropics/claude-code-action` v1.0.244 → v1.0.266, by commit, in all 15 templates that use them. `factory-smoke.yml`'s `CLAUDE_CODE_VERSION` 2.1.292 → 2.1.316, the version v1.0.266's `base-action/action.yml` installs. The templates now match the project's byte for byte.
2. **`bundles/factory/tree/render.py`:** `--adopt-pins` copies the workflows' changed action pins into the templates. It takes a line only where:
   - a `uses:` line differs only in its commit and version comment;
   - the action's path and the line's indentation are unchanged;
   - both pins are full 40-character commits;
   - the template's line has no setting in it.

   It also requires every pin of the adopted action to end at one commit. It refuses anything else and writes nothing. It prints each pin it adopted and a reminder to run factory-smoke after the merge. When the agent action changed, it also reminds you to move `CLAUDE_CODE_VERSION`. An unknown flag, or `--check` with `--adopt-pins`, is a usage error (exit 2).
3. **`bundles/factory/tree/tests/test_render.py`:** `AdoptPins` tests the bump, `--check` passing after it, the agent action's reminder, nothing to adopt, and each refusal, with the templates unchanged after every refusal. A mutant of each guard was run: the action, indentation, settings, one-commit and set checks and the agent action's reminder each fail a test when removed. The line-count check and the final render check back each other: removing both fails a test.
4. **`process/factory.md`** Enablement step 10: Dependabot's actions updates, with `--adopt-pins`, `CLAUDE_CODE_VERSION`, factory-smoke after the merge, and what `sdlc-migrate` reports until a release carries the same pins.
5. **`process/factory-runbook.md`** § 7: the same as an upkeep line.

**Rationale:** The templates are code-owned and generated workflows are policy-checked, so a Dependabot bump has to land in the templates under CD's review. A copy that takes only a commit pin's change keeps that review meaningful. Replayed on the project's real Dependabot commit, `--adopt-pins` wrote exactly the templates the project had fixed by hand. The new pins have passed factory-smoke on one project's default branch and stack profile so far, so each project runs smoke after it migrates.

---

## 2026-11-10: Restricted updates on the default branch come out of the runbook

**Origin:** The third project's install session asked z-sdlc whether the factory needed restricted updates and last-push approval on its default branch's ruleset. With restricted updates, every Dependabot PR needed the bypass to merge, even approved and green. CD (2026-11-10): "yes, fix the runbook line".

**What happened:** `process/factory-runbook.md` § 3.3 step 6 listed "updates restricted" for the default branch's ruleset. Nothing else asks for it:
- `process/factory.md` Enablement step 9 asks the default branch for code-owner review only;
- `bootstrap.py`'s `check_branch_rules` checks code-owner review and a required status check;
- the incubator's own default-branch ruleset has no restricted updates.

The factory never merges a PR itself, and its release gates rely on the release branch's and the pinned branches' rulesets, not the default branch's.

**Changes made:**
1. **`process/factory-runbook.md`:**
   - § 3.3 step 6: the default branch's ruleset drops restricted updates and gains stale approvals dismissed on push. Of the project's branches, restricted updates belong on the release branch and the pinned branches only, since on the default branch every merge needs the bypass. The runner host's repository keeps them on its default branch (factory.md step 8), and the step says so.
   - § 5: a pitfall row for it.

**Rationale:** Restricted updates on the default branch make the bypass the routine way to merge, when it's meant for the exception: agent PRs under CD's login, which CD can't approve. Dismissing stale approvals is what keeps an approval from carrying over to commits pushed after it.

---

## 2026-11-09: ADRs may record status facts and CD's answers in place

**Origin:** CD's decision of 2026-11-09, from a project that installed the framework, whose ADRs recorded status facts and CD's answers in place under a rule that named neither.

**What happened:** `adr-practice.md` allowed two in-place ADR edits, placeholder corrections and rendering updates, and sent everything else to a superseding ADR. The project made a third kind of edit that changes no constraint, and each one read as a violation:
- status facts: a Status line saying CD approves the ADR by merging its PR, after the PR merged; an Implementation Notes item marked "Proposed" after CD dropped it and its PR closed unmerged;
- answers to the ADR's own open questions: a Revisit line or a Consequences item that left a question for CD, after CD answered it.

**Changes made:**

1. **`process/adr-practice.md`**:
   - § Amendments vs. Supersessions has three exceptions, not two. The section's opening says every trailer entry names the exception it uses (`Exception: placeholder correction`, `rendering update`, `status fact` or `answer to an open question`), stands on its own and never declares that it wins over the ADR's body, and that a dated `## Amendment log` is the same trailer. The trailer's name is unchanged.
   - The third exception, status facts and answers to open questions, has three sub-items. **Status fact:** a proposal (an item the ADR itself marks undecided: Proposed, pending CD) was dropped; something the ADR already required has landed; or a proposal was adopted without adding, removing or changing a requirement or prohibition. Adding a proposal to an Active (or Accepted) ADR is never a status fact: a proposed change, or an adopted proposal that adds a requirement or prohibition, is drafted as a superseding ADR. Retiring the ADR is outside the exception; until the framework defines retirement, it is a supersession. **Answer to an open question:** written where the question was, and it qualifies only when it defers, declines or keeps the current state; one that picks a new requirement or prohibition is a supersession. It is written as a dated fact with its reopening trigger, never as an instruction ("CD declined X on YYYY-MM-DD; revisit when …", not "X is not allowed"), and neither it nor the trigger is a requirement or prohibition: work that wants X goes back to CD. **Trailer:** what happened, the text it replaced (if any), where the decision or event is recorded, and that no constraint changed.
   - The closing paragraph names tightening and loosening alongside adding and removing, and gains a test: does the edit add, remove or change anything the ADR requires or forbids, in any section (e.g., Decision, Consequences, What This ADR Forbids, Revisit)? Then supersede. It decides only whether a status-fact or answer edit qualifies (placeholder corrections and rendering updates keep their own conditions), and an edit that is none of the three exceptions is a supersession whatever the test says. "When in doubt, supersede" stays.
   - § Immutability gains a sentence: the only in-place edits are the three exceptions, plus the Status line and frontmatter a supersession sets on the ADR it replaces, and none changes what the ADR requires or forbids. § Contradiction Handling's "Never edit the prior ADR in place" becomes "… in place to reflect the new choice", with the same pointer.
2. **`docs/current_work/ideas/adr-amendment-vs-supersession-gate_handoff.md`** — dated notes: the first open question and candidates 2 (the decision test, its scope, and that adding a proposal to an Active (or Accepted) ADR is not a status fact) and 5 (what "Amendment trailer" means) are partly answered; three mentions of "two exceptions" (candidates 2 and 5, and Evidence) note there are three since 2026-11-09; the retrofit question notes that amendment entries written before the `Exception:` label carry none; a new open question records that `adr-practice.md` lists two different status vocabularies and doesn't say how an ADR is retired, left for a later patch. Another new open question asks whether replacing an estimate with a measured figure needs its own form; today it supersedes. The handoff stays pending and its gate work is untouched.

**Rationale:** The rule exists to keep the reasoning chain intact, and these edits don't break it: what the ADR requires and forbids stays as written, and the trailer records what changed and where. The test asks about what the ADR requires or forbids in any section, so it catches a tightened value or a rule added under Consequences as surely as an edit to the Decision. It doesn't lean on the drift review in § Three Functions, because that review checks only the ADR's decision. Naming the form, with that hard boundary, stops normal upkeep from reading as a violation without opening a path for the constraint-adding amendments the pending handoff is about.

---

## 2026-11-09: A runbook for installing the factory, from the third project's install

**Origin:** CD (2026-11-09): "analyze all the work that it took getting neuroloom integrated with the software factory and make repeatable procedures for next time so we dont have the same pains". The third project's install session wrote a retrospective from its transcripts, transaction log and PR history: 25 pain areas, 40 decisions made mid-stream, 15 assumptions that held only because the first two projects were alike. z-sdlc's own record of the same install was read alongside it.

**What happened:** On the third project, the twelve Enablement steps took about 2.5 hours of an 83-hour install. The rest went to three things the steps don't cover:
- a stack no profile fit, built upstream mid-install;
- credential debt the factory's threat model surfaced: secrets in history, a "read-only" route running as a superuser, a public database without TLS;
- a production tier for a host unlike the incubator's.

The first two projects had hidden this, because each fit a profile and the incubator's production host was one its broker deploys to. Decisions were also asked one at a time, relayed between sessions, some reversed and one never built.

**Changes made:**
1. **`process/factory-runbook.md`** (new, a `factory` bundle process doc):
   - **§ 0, how an install runs:** one owning session in the project, migrations included; framework fixes batched per phase and never re-tagged; every decision recorded when made, with its source session; recommendations with alternatives; no credential ever handled by the agent.
   - **§ 1, the day-one form:** every question, with options, the usual answer, its cost to reverse and who decides.
   - **§ 2, a read-only inventory:** stack fit, bare tools against CI, a CI audit, every host that deploys from git, the production host's profile, credential reach, an architecture map.
   - **§ 3, the critical path:** each step's Enablement step and its check; CD's steps batched into three sittings (GitHub and secrets, hosts, dashboards). The definition of done is one real issue through the factory, the first release and a production tier's first `baseline`, not a passing smoke run.
   - **§ 4, when no template exists:** a stack profile, a planning data route, a production tier for a new kind of host, a new host serving production, the first project in an organization, a scheduled alarm.
   - **§ 5, the pitfalls,** each with where it's handled.
   - **§ 6, what varies between projects:** each dimension, what the first two projects had, what the third brought, the rule now, and what a new value means.
   - **§ 7, upkeep.**
   - **Reviewed:** the third project's install session read it against what happened. Its nine findings are in: the two credential forms, three more day-one questions, scheduled alarms (§ 4.6), the rollback drill's revert path, a contract check's known false failure, and the host repository's clone command.
2. **`process/factory.md`:**
   - Enablement opens with a pointer to the runbook.
   - Step 8: `smoke.host_probes` holds the runner host's own addresses, never another project's planning exception.
   - Step 12: GitHub starts scheduled runs late or not at all (an hourly schedule was measured starting in about one slot in five), so pair the audit with an outside heartbeat.
3. **`bundles/factory/seed/README.md`:** an Enablement record skeleton (decisions with their source, inventory, state, deferred). Seeds aren't overwritten, so this reaches new installs only.
4. **`skeleton/manifest.json`:** the runbook is in `bundles.factory.process`.
5. **`docs/current_work/ideas/factory-enablement-upstream_handoff.md`:** what the install found worth building upstream, none of it built:
   - a checks-only broker skeleton;
   - a catalog-based planning reader generator;
   - a CI audit script;
   - a release provenance alarm;
   - a seeded CODEOWNERS test importing the guard's lists;
   - per-stack review rules;
   - a drill checklist;
   - gate-plan checks;
   - shellcheck fixes.

**Installed projects:** the runbook arrives with the next migration of any project with the `factory` bundle. Nothing else changes for an installed project.

**Rationale:** The steps say what must be true. What cost the time was what to ask, and what to build when a project doesn't fit, and both were being decided live. Writing them down once, against what actually happened, turns the next install's discoveries into checks.

---

## 2026-11-06: A release gate pins only for a broker that takes it, under its ruleset

**Origin:** Neuroloom's review of its own v2.4.0 migration, passed upstream by its enablement session. CD (2026-11-06): "yes, build v2.4.1".

**What happened:** Four gaps around release gates:
1. Nothing asked whether the project's broker runs release gates' gate runs, which Neuroloom's doesn't yet. A plan with a release gate would still pin its commit and open the release PR. CD's merge would then deploy, the broker would refuse the gate run, and provenance would block later gates until a `baseline`.
2. `factory-gate-request.yml` pinned without checking that the pinned branches' ruleset existed. Without it, the branch could move after CD reviewed it.
3. The pin's contents token was minted on every gate request, release gate or not, and sat in the environment of the step that parses the PR, its comments and the plan.
4. `factory-gate-stop.yml` puts the next gate's ID into JSON unchecked. It wasn't reachable: the ID comes from a reviewed plan's parsed gates.

**Changes made:**
1. **`bundles/factory/tree/gates.py`:** the catalog takes `release_gates`, true or false, which is the broker's own word that it runs kind `release`.
   - `check_plan` refuses a release gate without it.
   - The `release-gate` command refuses to name a pin for one, so nothing is pinned.
2. **`bundles/factory/tree/implement_guard.py`:** a release gate without a release branch is still refused first, before the broker's support is checked.
3. **`bundles/factory/tree/templates/factory-gate-request.yml`:** three steps before the request.
   - **"Find a release gate's pinned branch"** holds only the read token and says nothing. It makes the request step's checks again: the requester's permission, and a head that hasn't moved.
   - **The contents token** is minted only when there's a pin.
   - **"Pin the release gate's commit"** holds only that token and the read token. It pins only where GitHub lists `update`, `non_fast_forward` and `deletion` covering the pin's name. It writes its outcome for the request step, which says it on the PR.
   - **The request step** no longer holds the contents token, and refuses unless the pin exists at the gate's commit.
4. **`bundles/factory/tree/revise_gate.sh`:** it outputs a gate ID matching `^G[1-9][0-9]?$`, or stops.
5. **Tests:**
   - `tests/test_release_gates.py` runs the job's three steps in order against the fake gh, which now records a created ref. New tests cover:
     - no pin without the ruleset, or when GitHub doesn't answer;
     - no pin for a broker that doesn't take release gates;
     - the contents token used for the pin alone.
   - `check_plan` refuses an undeclared or false `release_gates`, and `load_catalog` refuses a value that isn't true or false.
   - `tests/test_revise_gate.py` checks the gate-ID guard comes before the output.
   - The ruleset check and the declaration were each removed on purpose, and their tests failed.
   - All 554 tests pass in a fresh install.
6. **`process/factory.md`** D4 rules 3 and 13, and **`process/production-gates.md`** § With a Release Branch, say both refusals and the token's scope.

**Installed projects:**
- A broker that runs release gates adds `"release_gates": true` to its `production/ops.json`. Until it does, plans with release gates are refused, while a Release section at the end still releases.
- The pinned branches' ruleset (`factory/release/**`) must exist before the first release gate. `bootstrap.py` already checks it.
- `ops.json` is in the operations digest, so a production host re-runs its setup after adding the field.

**Rationale:** A release gate deploys on CD's merge, so everything that has to hold afterwards is checked before the pin: that the broker can run the check, and that nothing can move the pinned commit.

---

## 2026-11-06: The shared runner host's setup lives in a repository of its own

**Origin:** CD (2026-11-06): "we should have a small repo for the host setup and settings". CD had asked why the shared runner tiers need an owner at all. Since v2.3.4 the runner setup runs the tier owner's own default branch, so a project that owns a shared tier holds back the host's upgrades for every project. The incubator, owner of the strict and planning tiers, was parked with the runner upgrade due.

**What happened:** The runners are shared by every project, but the host's setup script and settings were only in project repositories, so one project per tier was designated as their source (v2.1.0). That was bookkeeping until v2.3.4 made setup run the owner's default branch.

**Changes made:**
1. **`process/factory.md`** Enablement step 8, the shared host's own repository:
   - **What it holds:** `.github/factory/host/`, a minimal `factory.json` with the runner labels and groups setup reads, and the host's committed `host.conf`.
   - **What it owns:** the strict and planning tiers. A project never owns a shared tier. The CI tier stays its project's, because its job image is built from that project's toolchain.
   - **What it runs:** nothing. It's in no runner group, with Actions off.
   - **Its protection:** the organization's strongest on its default branch, since a merge there is root on the runner host at the next setup run.
   - **How it takes a release:** by copying the bundle's `host/` files at each release's tag, never `host.conf`.
   - **Moving a tier:** remove its record, then claim it again with `TIER_OWNER` from a fresh clone of the new owner.
   - The runner-upgrade paragraph says each tier's setup runs again once the release reaches its owner.
2. **`bundles/factory/tree/host/setup.sh`** (its header) and **`bundles/factory/seed/host/host.conf`** (its header): say the same in a line each.

**Installed projects:** nothing changes until a host's operator moves its shared tiers to the host's repository: remove each tier's record, then run setup once with `TIER_OWNER` from a fresh clone of it. Its first run prints that repository's deploy key to add.

**Rationale:** The shared tiers belong to the organization, not to any project. Their setup should move at the framework's pace, not wait for whichever product happened to set them up first.

---

## 2026-11-06: Production deploys from a release branch by default

**Origin:** CD (2026-11-06): "release/production deploys should be the primary way of deployments", then "yes all 3": the rules lead with it, new projects get it, and a Compose host's broker follows the branch (designed now, built when the incubator is un-parked).

**What happened:** Since 2026-11-05 each project chose its own release model. The default, with `release.branch` empty, was execution-PR gates: the broker deploys an execution PR's head at a gate, before CD merges it. A project on Railway took the release branch, and release gates let a plan deploy partway through there too, so choosing it gave nothing up.

**Changes made:**
1. **`process/factory.md`:**
   - **D4 rule 13** leads with the release branch as the model. Execution-PR gates become the fallback, for a production host that can't follow a branch yet. A `factory.json` with no `release` block is on the fallback, and migrating changes nothing for it.
   - **A host that can't deploy a branch by itself** (a Compose host) follows it through its broker. This is designed, not built.
     - **Trigger:** `factory-advance`, on a PR merged into the branch, dispatches `factory-follow.yml` on `main`. A `push` trigger would run the release branch's own copy of the workflow. CD can also dispatch it by hand, and it does nothing when the head is already deployed.
     - **Approval:** no environment approval. CD's merge is the approval, and the broker reads it from GitHub.
     - **What the broker checks:** the run, the release branch's provenance, that the head descends from the deployed commit, the ledger, and that no nightly backup is running.
     - **What stays CD's:** the fallback's infrastructure refusal, since a Compose restart doesn't rebuild.
     - **The deploy itself** follows rule 14's settings check and rule 15's evidence. It rolls back by itself to the recorded commit, never past a migration, and then blocks until CD reverts in the branch or records a `baseline`.
     - **The record:** a ledger entry and a signed receipt posted on the merged PR.
     - **Release gates** wait for the follow deploy under the broker's lock.
     - **A missed dispatch** shows at the next gate.
   - **Rule 2:** a deploy is a release PR, and gates hold what isn't a deploy, or the deploys too on the fallback.
   - **Rules 10, 14 and Forbids 4** allow for `factory-follow.yml`.
   - **Rule 16:** a release-branch project without a tier releases through a Release section, and its plans can have no gates, release gates included.
   - **Enablement step 2** gains the release model. Create the branch at `main`'s tip, add its rulesets and point every production host at it, all before the first plan that releases. It also names the three cases: a host that follows a branch, nothing in production yet, and a Compose host, which sets `release.branch` to `""`.
   - **Step 9** lists the two release rulesets first. Merge-commits-only on `main` becomes the fallback's requirement.
2. **`bundles/factory/seed/factory.json`:** `release.branch` is `release/production`, and its note says why and how. Only that value and its `_doc` changed, and the file's layout is untouched.
3. **`process/production-gates.md`, `skills/sdlc-plan`, `skills/sdlc-lite-plan` and both plan templates:** a factory project's production follows a release branch by default, and empty is the fallback. Without a production tier, a Release section still releases.
4. **`bundles/factory/tree/bootstrap.py`:** a missing release branch's problem says how to fix it.
5. **Tests:**
   - `tests/test_bootstrap.py` starts from a project with no release block, whatever the project's own model is.
   - `tests/test_release_model.py` (new) checks that a `factory.json` with no `release` block is the fallback for the guard, the rendered workflows and the release refusals. It also covers what a release-branch project without a production tier can do.
   - The bundle's suite passes in an empty project with the new default (549 tests), and again with its `release` block removed, as an older project has it.

**Installed projects:** nothing changes on migrating. A seed is never rewritten, and every reader of `release.branch` treats a missing block as the fallback. A project already on a release branch keeps it. A project on the fallback switches by setting `release.branch` and following Enablement step 2. A project on a Compose host stays on the fallback until its broker follows the branch.

**Versioning:** a new default for new installs is a minor release under this repository's rules (v2.4.0). CD has chosen patches before, so it's CD's call.

**Rationale:** CD's merge as the deploy is the simplest approval there is, and release gates already cover mid-plan deploys. So the model where no agent and no broker decides what deploys becomes the one every new project starts on. The broker deploying stays only where a host can't follow a branch, until its broker can.

---

## 2026-11-06: Testing knowledge: run the mutant for every claimed protection

**Origin:** Neuroloom's production broker reviews, passed upstream by its enablement session as knowledge feedback. Round 2 of its security audit found a test whose fixture made a moved check indistinguishable from the check in place. CD (2026-11-05): "do 1, 3, 4 and 7".

**What happened:** `two_edit_check` asks for a test to be judged by imagining a breaking edit. For a protection, such as a check, a refusal, a guard or an isolation, imagining the edit wasn't enough. The test passed with the protection moved, and nothing showed it.

**Changes made:**
1. **`knowledge/testing/testing-paradigm.yaml`:** a new entry, `protection_mutants`, beside `two_edit_check`.
   - For every protection a test claims, make the mutant (removed, weakened, moved too late) and run it, and the test must fail.
   - The fixture must be an input the unprotected code mishandles, and the test asserts that property too.
   - Keep the mutant in the test when it's cheap; otherwise run it once by hand and say so in the commit.
   - Its example is the root setup's replace-ref test from this release.

**Rationale:** A missing protection fails silently, so the test is the only evidence it exists, and it's evidence only when the test fails without it. The other three fixes in this batch apply it: `test_host_setup.py`, `test_gate_values.py` and `test_ed25519.py` each run the broken copy and show it fails.

---

## 2026-11-06: Receipts are signed in constant time, by OpenSSL

**Origin:** Neuroloom's production broker reviews, passed upstream by its enablement session. CD (2026-11-05): "do 1, 3, 4 and 7".

**What happened:** `ed25519.py` signed the broker's receipts in plain Python. Its scalar multiplication branches on the secret's bits, and its loop runs as long as the nonce is long. Its docstring accepted that "on a host where the signer is root", but an unprivileged local user can make the broker sign, since a refusal is signed too. Timing many signatures leaks nonce bits, and enough of those recover the key.

**Changes made:**
1. **`bundles/factory/tree/ed25519.py`:**
   - `sign` and `public_key` run OpenSSL 3's Ed25519, which is constant-time. The key goes to OpenSSL as PKCS #8 DER on a pipe (`/dev/fd/<n>`), never in a file. The message, which is public, goes in a temp file, since a one-shot signature needs its input's size.
   - Each signature must verify under the key's public half, which catches a key-format mistake. An empty message is refused: OpenSSL 3.0 to 3.5 can't sign one, and a receipt never is one.
   - A host whose OpenSSL can't sign gets an error, such as an older OpenSSL or LibreSSL, which has no `-rawin`. Nothing falls back to plain Python.
   - `verify` stays plain Python: it handles only public values, and it runs on GitHub's runners. The plain-Python signer stays as `_reference_sign`, for the tests.
2. **`bundles/factory/tree/tests/test_ed25519.py`** (new):
   - OpenSSL's output equals RFC 8032's test vectors and the reference signer's, byte for byte.
   - With the secret's plain-Python expansion made to fail, signing still works, so it never runs.
   - The secret is never written to a file.
   - Without OpenSSL 3, or with LibreSSL's refusal, nothing is signed.
   - A signature from another key is refused.

   With the plain-Python signer put back, 4 of its tests fail. It passes against OpenSSL 3.0.2 (Ubuntu 22.04), 3.0.13 (Ubuntu 24.04), 3.0.22 (Debian 12), 3.5.7 (python:3.12-slim) and 4.0.3.

**Installed projects:** each production host's broker signs with the host's `openssl`, so the host needs OpenSSL 3 (Debian 12 and Ubuntu 22.04 or later ship it), reachable on the broker's `PATH`. The broker's sandbox must let it run `openssl` and write a temp file. `ed25519.py` is in the operations digest, so the host re-runs its setup before its next gate. A developer machine that runs the projects' gate tests needs an OpenSSL 3 as well; macOS's own `/usr/bin/openssl` is LibreSSL, so install OpenSSL 3 (Homebrew's `openssl@3`), which the module also looks for.

**Rationale:** The signer's time mustn't depend on the secret when someone who isn't root can ask for signatures. OpenSSL is on every Debian and Ubuntu host already, so no new dependency comes with the fix.

---

## 2026-11-06: Gate values match whole, and a step that times out says so

**Origin:** Neuroloom's production broker reviews, passed upstream by its enablement session. CD (2026-11-05): "do 1, 3, 4 and 7".

**What happened:** `gates.py` checked values with `re.match` and with compiled patterns' `.match`, all ending in `$`. `$` also matches just before a trailing newline, so `"<sha>\n"` passed as a commit, a digest, a plan path, a run title, a release branch, a plan's catalog parameter and a receipt's output, and the newline went on to whatever read the value next. The release gates' new branch check had the same flaw. Separately, a receipt's status had no `timed-out`, so a broker reported a step stopped at its catalog `timeout_s` as `failed`.

**Changes made:**
1. **`bundles/factory/tree/gates.py`:**
   - Every value check uses `fullmatch`. Plan lines, which come from `splitlines`, keep their prefix patterns, and so does the comment marker, matched from `\A` to its own newline.
   - `RECEIPT_STATUSES` takes `timed-out`. The tracker shows it as "timed out", and its result comment says what the step changed is unknown, so inspect production before `factory:gate-retry`. It isn't done, so execution doesn't continue, and later gates get no outputs from it.
2. **`bundles/factory/tree/tests/test_gate_values.py`** (new): a trailing newline is refused in each value. Every fixture is one `.match` accepts and `.fullmatch` doesn't, so the test tells the fix from the flaw: with `.match` put back, 8 of its checks fail. A test also finds any value check left on `.match`. A timed-out receipt is checked, shown and not continued.

**Installed projects:** `gates.py` changed, so a production host re-runs its setup before its next gate, as v2.3.3 already requires. A broker may now report `timed-out` for a step its catalog timeout stopped. One that doesn't still reports `failed`, as before.

**Rationale:** A check that passes the value plus a newline isn't checking the value that gets used.

---

## 2026-11-05: Runner setup runs root's own copy of the default branch, never the checkout

**Origin:** Neuroloom's production broker reviews (its security audit, round 2), passed upstream by its enablement session. CD (2026-11-05): "do 1, 3, 4 and 7; use the deploy key".

**What happened:** The audit found that a root setup script trusting a user-owned checkout gives that user root. The user is also the agent sessions' login. A replace ref (`git replace <blob> <evil>`) leaves `git status`, `ls-files -v` and the tip comparison clean while `git show` returns the evil bytes, and `url.insteadOf` and `objects/info/alternates` are other routes. The bundle's runner setup was worse than the script the audit read. Run as root from the tier owner's checkout, it sourced the checkout's `host.conf` and ran its helpers, `setup-ci.sh` included, with no check at all. It also took the tier's repository from the checkout's `origin` remote, and copied the CI tier's build context from the working tree.

**Changes made:**
1. **`bundles/factory/tree/host/setup.sh`:** two stages, after Neuroloom's fix.
   - **The bootstrap** runs from the checkout and reads nothing there but `host.conf`'s `RUNNER_INSTANCE`, as text, and the registration token. It:
     - takes the tier's repository from its root-owned record, or from `TIER_OWNER` on the first run;
     - fetches that repository's default branch, as GitHub names it, into a root-owned clone. The fetch uses root's own read-only deploy key, one per repository at `/etc/factory-runner/deploy-keys/<owner>/<repository>`, GitHub's host keys from its API, and a git with no system or global config, no replace objects and literal pathspecs. The first run prints the key and stops.
     - stages every file setup reads from that clone, each checked against the blob id its tree names;
     - refuses a checkout whose `setup.sh` or `host.conf` isn't the default branch's;
     - takes the host's setup lock before the fetch;
     - copies the token after checking it on one open file: no link, owned by root or the sudo user, mode 0600, only a token;
     - re-executes the staged copy with a clean environment and the operator's settings by name.
   - **The staged copy** checks it is the bootstrap's (a root-only stage, root's clone at the tip it names, the lock held). It checks the default branch's `host.conf` sets the instance the bootstrap read. It claims the tier for the repository root fetched, never the checkout's remote.
   - `--print-settings` is refused as root, since it would source the checkout's `host.conf`. The header states the residual: the bootstrap is still the checkout's script, so run setup from a checkout no agent session can write.
2. **`bundles/factory/tree/host/setup-ci.sh`:** the CI job image's context and Dockerfile are staged from root's clone at the same tip, with links kept as links, not copied from the checkout.
3. **`bundles/factory/tree/tests/test_host_setup.py`:** the claim reads the fetched repository, and a new `RootsOwnCopy` class covers:
   - the default branch;
   - the fetch;
   - a replace ref;
   - a loose object whose bytes don't hash to its id;
   - file and directory staging;
   - the token file;
   - reading the instance;
   - the tier's repository;
   - the bootstrap's order.

   Each protection is also broken on purpose and the broken copy shown to fail the same check: `clean_git` without `env -i`, the stager without `GIT_NO_REPLACE_OBJECTS`, and the stager without the hash check. The bootstrap also ran as root in an Ubuntu 24.04 container against a local stand-in for GitHub: all 24 checks passed, including a replace ref plus an assume-unchanged working file in the agent's checkout, which the staged run ignored.
4. **`bundles/factory/seed/host/host.conf`:** its header says setup runs the default branch's copy, and to write `RUNNER_INSTANCE` plainly.
5. **`process/factory.md`** Enablement step 8: commit `host.conf` to `main`. Root never runs the checkout's files. Add the printed deploy key, then run again. The residual. Each tier has a designated repository rather than a checkout.

**Installed projects:** the next setup run on each runner host prints a deploy key per repository that owns a tier. Add it to that repository (Settings, Deploy keys, write access off) and run setup again. A `host.conf` with uncommitted settings is refused until they are committed to the default branch. The incubator's own production setup (`setup-production.sh`, the incubator's code, not the bundle's) has the same flaw and is parked with the rest of the incubator work (CD, 2026-11-05).

**Rationale:** Root can't learn from the checkout what the checkout's owner can change, so it gets the code itself: from GitHub, with its own key, through a git that ignores everyone's config. What it can't get that way, the bootstrap script, is kept short and named as the residual it is.

---

## 2026-11-05: A plan can deploy partway through, in a release gate

**Origin:** CD (2026-11-05): "i need any project able to execute deploys mid-work as part of plans. gating to release/production shouldn't stop work that needs to execute that way". The release-branch model in v2.3.3 forbade it: "A plan never deploys mid-execution", and work that needed production between its own phases had to be split into two deliverables. Neuroloom's enablement and broker sessions reviewed the design; their security audit's provenance rule and ruleset checks are folded in.

**What happened:** A release-branch project could deploy only when a plan was done. The broker can't deploy there, since every host deploys the release branch by itself and CD's merge into it is the deploy. So a plan whose later phases need the earlier ones live had no way to say so.

**Changes made:**
1. **`process/factory.md`:**
   - D4 rule 13: a release gate (a gate with a `**Release:**` line) pins the stopped commit on `factory/release/<pr>-<gate>-<commit>`, opens a release PR from it, and CD's merge is the deploy. Its gate run, of kind `release`, binds the release PR and its merge. The broker checks the release PR is the App's from the pin at the request's head, merged by an approver, its merge on the release branch's first-parent history, and the head still holding the gate's content. Then it waits for rule 15's evidence and runs the gate's read steps.
   - Provenance accepts a merge whose second parent is on the default branch or is a release gate's pinned commit: who merged proves who clicked, not what came in.
   - The release branch's ruleset restricts updates to admin bypass actors in pull-request mode, merges with merge commits only, and no `exclude` matches it. The pinned branches' ruleset lets nothing move them.
   - Rule 2 and Enablement step 9 say so.
2. **`process/production-gates.md`** § With a Release Branch: a plan deploys partway through, in a release gate (its template: read steps only, no rollback; merging deploys everything behind the gate's commit), or when done, in a Release section, or both. The two-deliverables rule is gone.
3. **`bundles/factory/tree/`:**
   - `gates.py`: the gate's Release line, the `release` kind, its title, digest field (only for that kind, so `ops` and `cd` digests are unchanged), `pin_branch`, `release_binding`, the release PR's description, and the `release-gate` and `release-pr` commands.
   - `factory-gate-request.yml`: pins the commit with a contents-only App token, refuses a pinned name at another commit, trusts only the App's own release PRs from it, closes the gate's stale ones, and opens the release PR. Once it's merged, it asks for the gate run.
   - `factory-advance.yml`: asks for it when CD merges a release gate's PR.
   - `factory-gate.yml`: takes the `release` kind and rebuilds the request from GitHub's record of the release PR.
   - `implement_guard.py`: shows release gates on the plan PR and refuses one without a release branch.
   - `bootstrap.py`: checks both rulesets, with GitHub's include and exclude patterns.
   - Tests: `tests/test_release_gates.py` (new; it runs the request step, the advance job and the gate run's check against a fake `gh`) and `tests/test_bootstrap.py`. Review agents read it in two rounds (code, security, then the fixes); their findings are fixed:
     - someone else's PR from a pin is refused rather than blocking silently, and a refused pin or PR is said;
     - a release PR merged at an older commit is reported, once GitHub confirms it's the App's from that PR's pin;
     - the release PR lists every commit by author from GitHub's totals, leaving out ones an earlier release gate shipped;
     - stale gate runs are cancelled, and the release PR is announced before that cleanup;
     - `bootstrap.py` matches ruleset patterns as GitHub does (`File.fnmatch` with `FNM_PATHNAME`: `**` crosses a slash only as `**/`), refuses any exclude that can leave pinned branches out, and checks the pinned ruleset even before the release branch exists;
     - the recovery after a failed release gate is stated as git and rule 11 allow it (a revert needs a `baseline`; a migration fixes forward), and its result comment says so.
4. **`skills/sdlc-plan`, `skills/sdlc-lite-plan` and both plan templates:** a deploy partway through is a release gate.

**Installed projects:**
- **Every project with a production tier re-runs its host's setup (`setup-production.sh`) after migrating, before its next gate.** `gates.py` changed, and the operations digest every request carries hashes it, so until the host installs the new copy every gate is refused, `ops` and `cd` included. Gates without a release branch otherwise behave as before: their request and digest fields are unchanged.
- **A release-branch project** runs `bootstrap.py`, adds the pinned branches' ruleset, and tightens the release branch's. Its broker takes the `release` kind: it checks the binding, the merge, the head's content and rule 15's evidence, and applies the new provenance rule.
- **The incubator** takes it with the next `--to-incubator`, and CD re-runs its production setup on the production machine with it.

**Rationale:** CD's merge into the release branch already is the deploy and its approval, so a mid-plan deploy is a release PR at the gate's commit. The pin and its ruleset make the commit CD reviews the commit CD merges. The gate run after it lets the broker check that production serves it before the next phase builds on it.

---

## 2026-11-05: The factory imported from the incubator (9e56842..7c07be1): Where to look, a revision's gate stop

**Origin:** The incubator merged the factory code for the entry below, its own fix of 2026-10-20 for a revision's gate stop, and a larger patch cap.

**What happened:** The first report found z-sdlc ahead on 24 bundle files, the implement and revise skills and `process/factory.md`, none of them in the incubator since the last import. Six bundle files had changed on both sides: `implement_guard.py` and its tests, the implement and revise templates, `workflow_policy.py` and `tests/test_revise_gate.py`. `--apply --accept` takes the incubator's file, so it would have dropped z-sdlc's side. `--to-incubator` handed z-sdlc's changes over first, the six were merged by hand in the incubator, and its CI passed before this import took them. In `implement_guard.py`, z-sdlc's case-folded CODEOWNERS form is now built with the `path_regex` Where to look added, not a second copy of the pattern compiler. The seed README needs nothing: its generic version has none of the sections the incubator changed.

**Changes made:**
1. **`bundles/factory/tree/`:** `implement_guard.py` (Where to look, and the patch cap raised from 400,000 to 550,000 bytes), the implement and revise templates and `render.py` (Where to look), `templates/factory-gate-stop.yml` (new) and `revise_gate.sh stopped` (CD dispatches it for a PR whose last revision stopped before a gate without its gate stop, and it does that job's work with no agent and no revision counted), `factory-revise.yml`'s stop-at-gate running after a skipped fixtures job, and `workflow_policy.py` (a factory job after one that carries on past a skipped job has a status function in its own `if`), with their tests.
2. **`.claude/skills/zsdlc-import-factory/import.json`:** `last_import` is `7c07be1`.

**Rationale:** The factory's code comes only from its incubator, and an import that takes a file changed on both sides has to find z-sdlc's side already there.

---

## 2026-11-05: Where to look: factory PRs list the files CD always looks at

**Origin:** CD chose it from an "AI That Works" episode on software factories (2026-10-23). The episode treated code review as risk management: rules over the diff, not the author, decide what a person must look at.

**What happened:** A factory PR's Risk line and Review focus were the agent's own judgment, and the publish guard checked only that they were filled in. The factory already refused agent changes to code-owned paths, but a migration, a money file or a dropped permission check could reach CD rated Low with nothing pointing at it. Built in the incubator first, as the factory's changes are, and reviewed by code, architecture and security reviewers over two rounds. Round 1 found lines hidden past a length cap or behind a NUL byte, decoy files pushing the real one out of a capped list, flags lost at a continued execution's gate stop, files changed and changed back vanishing, moves counted as new code, seed rules raising PRs to High over docs and tests, and a broken rule costing the agent's run. Round 2 found that rewriting a continued execution's description after every segment (round 1's fix for its gate stops) re-checked follow-ups CD had unchecked; that the move handling could read another file's lines or hide code moved across a rule's scope; and that nothing capped the description's length.

**Changes made:**

1. **`bundles/factory/tree/`** (imported): `implement_guard.py` reads `factory.json`'s `review.focus` from the default branch. It lists every changed file the rules flag at the top of a code PR's Review focus (over the whole PR) and in a revision's comment, and a continued execution that stops short of done lists its segment's own. When a rule flagging the final diff has a tier above the agent's rating, the Risk line leads with it. Changed paths that aren't plain render as escaped text everywhere the guard names them. A file name that isn't UTF-8, a description or comment over 60,000 bytes, and a segment's list over 30,000, are refused before any push. `render.py` treats the `review` block as read at run time. The implement workflow carries the segment's list to the gate stop's comment, and the revise workflow's publish checkout names the default branch. Tests cover each case.
2. **`process/factory.md`** — new § Where to look (rule shape, what CD sees, what it holds against, not a gate, deterministic only, the always-high areas, the seed), and Enablement step 2.
3. **`bundles/factory/seed/factory.json`** — a `review` block with four rules: migrations (`migrations/`, `Migrations/`, `alembic/`), bulk writes and raw SQL, access checks and configuration reads. They're scoped to source files and leave out test directories. The bulk-write and access-check rules know Django's and ASP.NET Core's names; a project on another framework, such as one on `python-uv-node`, adds its own.
4. **`templates/pr_description_template.md`** — Code PR: the factory adds Where to look above the author's Review focus, and the author's own focus and rating don't change. Risk Tiers: a factory project checks its always-high areas as `high` rules, and its block says so.

**Installed projects:** migrations never touch seeds. To turn it on, copy the seed's `review` block into `.github/factory/factory.json`, add the project's own always-high areas as rules with paths, and let CI (the factory's tests load the rules) pass. Without the block, PRs are unchanged.

**Rationale:** CD approves every merge, and what to look at first shouldn't depend on the agent that wrote the change. Rules from the default branch, applied by the writer job, can't be changed by the agent. A file can't hide from a path rule by its name, though logic copied elsewhere isn't followed; line rules catch mistakes, not a hostile agent. It points CD at files and blocks nothing. Release type: patch (CD, 2026-11-05: v2.3.3; the bump rule reads a new setting as minor, and CD chose a patch).

---

## 2026-11-05: The runners move to actions/runner v2.338.2

**Origin:** A third project enabling the factory noticed `setup.sh` still pinned v2.338.0 (released 2026-10-06), while v2.338.2 came out on 2026-10-26. GitHub stops sending jobs to a self-hosted runner more than 30 days behind the latest release, and the factory's runners never update themselves (`--disableupdate`).

**Changes made:**

1. **`bundles/factory/tree/host/setup.sh`**: `RUNNER_VERSION=2.338.2`, with `RUNNER_SHA256` set to the linux-x64 archive's published checksum. GitHub's asset digest and the release notes agree on it, and setup verifies the download against it.

**Upgrading:** after the migration that brings this, run each tier's setup again from its checkout (`sudo TIER=<tier> bash .github/factory/host/setup.sh`, the strict tier with no `TIER`): it upgrades each idle runner in place. Do it before 2026-11-25, 30 days after v2.338.2. The CI tier's image is rebuilt on its next setup run. A project's own `setup-production.sh` that copies the pin bumps its own copy.

**Rationale:** The pin is a supply-chain control (a checksum, no self-update), so keeping it current is z-sdlc's job, within the 30 days. Release type: patch.

---

## 2026-11-05: A release-branch production model, beside the execution-PR gates

**Origin:** CD's release model for a third project (2026-11-05): "branch release/production; when i make changes i'll merge into release/production to get them to deploy. when the factory wants to deploy to prod, it'll make a PR to release/production."
- CD chose that the branch deploys itself, so CD's merge is the approval, rather than a merge that triggers a broker gate.
- The factory opens a release PR only when a plan calls for one.
- A plan never deploys mid-execution.

**What happened:** D4 had one release model: a deploy gate deploys the execution PR's head through the broker, before CD merges it. Rules 2, 13 and 14 and the plan skills assumed it. The project wanted every deploy, CD's own included, to be a merge into one protected branch that its hosts deploy by themselves.

**Changes made:**

1. **`bundles/factory/seed/factory.json`**: a `release` block, `branch` empty by default (today's model). **`.claude/skills/zsdlc-import-factory/import.json`**: the incubator may leave it out.
2. **`bundles/factory/tree/gates.py`**: `parse_release()`, a plan's `### Release` section and its `**Why:**` line.
3. **`bundles/factory/tree/implement_guard.py`**:
   - `read_release_branch()` and `release_line()`;
   - a plan with a Release section is refused without a release branch;
   - the plan PR's body shows the release;
   - the execution PR's body carries `<!-- factory-release v1 -->` and says merging it releases.
   **`tests/test_implement_guard.py`** covers it.
4. **`bundles/factory/tree/templates/factory-advance.yml`**: a `release` job. A merged factory code PR carrying the marker, in a project with a release branch, dispatches **`factory-release-pr.yml`** (new). That workflow, as the factory App in the writer environment:
   - checks the PR merged into the default branch, is the App's, and carries the marker;
   - opens a release PR from the default branch into the release branch, or comments on the one already open;
   - says so on the merged PR, or that there's nothing to release.
   **`tests/test_render.py`**: the workflow counts.
5. **`bundles/factory/tree/bootstrap.py`**: with a release branch, it checks that the branch exists and that its ruleset requires a PR with code-owner review and forbids force pushes and deletion. It also checks that no bypass actor may bypass it always: in that mode an admin credential skips every rule, which the project's security review found and fixed live. The default branch's merge-method check then doesn't apply. **`tests/test_bootstrap.py`** covers it.
6. **`process/factory.md`**:
   - D4 rule 13 now names two models:
     - **execution-PR gates,** unchanged;
     - **a release branch:** every host serving production deploys it by itself; CD's merge is the deploy and its approval; plans release through a Release section and never deploy mid-execution; the broker keeps non-deploy operations; a rollback is CD's, followed by a revert PR; rule 7's expected commit is the branch's head, with a provenance check that every first-parent commit since the last record is the merge commit of a PR an approver merged (from the project's broker design); no infrastructure refusal; the default branch's merge method doesn't matter.
   - Rules 2 and 14 note the model.
   - Enablement step 9's merge-commit line is scoped to execution-PR gates.
7. **`process/production-gates.md`**: § With a Release Branch, with the Release section's format. Work that needs production between its own phases is two deliverables.
8. **`skills/sdlc-plan/SKILL.md`**, **`skills/sdlc-lite-plan/SKILL.md`**, **`templates/planning_template.md`**, **`templates/sdlc_lite_plan_template.md`**: with a release branch, a deploy never goes in a gate, and a plan that must reach production ends with a Release section.

**Upgrading:**
- Nothing changes without `release.branch`.
- To use it:
  - create the branch at what production runs;
  - give it a ruleset (a PR with code-owner review, no force push, no deletion, merges by CD);
  - point every host that serves production at it, with auto-deploy on and every other branch off;
  - set `release.branch` and render.

**Rationale:**
- A project that wants every deploy to be one reviewed merge into one branch gets it, with the factory's part kept to opening the PR.
- The broker keeps what it's for: operations that aren't deploys.
- The execution-PR model stays as it was for projects that run it.

Release type: patch (CD, 2026-11-05: v2.3.3; the bump rule reads a new setting and workflow as minor, and CD chose a patch).

---

## 2026-11-05: With a production tier, the default branch merges with merge commits only

**Origin:** Designing a third project's production tier (2026-11-05). Its repository allows squash and rebase merges.

**What happened:** D4 rule 13 says an execution PR merges with a merge commit: the broker deploys the PR's head, and production may run ahead of the default branch until then. Nothing set or checked a repository's merge settings. A squash or rebase of an execution PR would leave production on a commit the default branch doesn't contain, and rule 7's deployed-commit check would refuse every later gate until a `baseline`.

**Changes made:**

1. **`bundles/factory/tree/bootstrap.py`**: with a production tier (`production/ops.json`), it reads the repository's merge settings and the default branch's ruleset's allowed merge methods. It reports a problem when merge commits aren't allowed, or when squash or rebase also is, and unchecked without admin access. **`tests/test_bootstrap.py`** covers squash allowed, a ruleset restricted to merge, no merge commit, and no check without a production tier.
2. **`process/factory.md`** Enablement step 9: with a production tier, the default branch allows merge commits only.

**Upgrading:** a project with a production tier restricts its default branch to merge commits (repository settings, or the ruleset's allowed merge methods).

**Rationale:** Rule 13 needed a check that holds it, not a habit. Release type: patch.

---

## 2026-11-05: smoke's mcp-services job keeps the planning probe's transcript

**Origin:** The `mcp-services` job's first run, in a third project (2026-11-05, dispatched with `mcp_probe`). It passed the execution entry: the credential arrived, Bash saw a placeholder, and the left-out tool was tried and refused. It failed the planning entry, which reported the execution entry's header digest.

**What happened:** claude-code-action writes every run's execution output to one fixed path (`/__w/_temp/claude-execution-output.json`). The job's second agent step overwrote the first's transcript before the upload and the verdict read it. So the planning check read the execution probe's transcript. Its refusal and masking verdicts passed only because both transcripts behave the same there.

**Changes made:**

1. **`bundles/factory/tree/templates/factory-smoke.yml`** `mcp-services`: a step right after the planning probe copies its execution file to `$RUNNER_TEMP/mcp-plan-execution.json`. The planning transcript's upload and the verdict read the copy.
2. **`bundles/factory/tree/tests/test_planning_probe.py`** (`McpServicesProbe`): the policy admits the job, the copy sits between the two agent steps, and the verdict reads it.
3. **`process/factory.md`** D2 rule 10: what the first run observed (the execution entry end to end, the refusal under auto mode included). After v2.3.2, the next run observed the planning entry too: every check passed for both entries, the left-out tool tried and refused.

**Rationale:** Two agent steps in one job share the action's output path. A verdict must read what each step wrote before the next step runs. Release type: patch.

---

## 2026-11-05: Enablement step 3: a first image publish GHCR refuses is re-run

**Origin:** A third project's first `factory-image` run (2026-11-05): GHCR created the package and took every layer, then refused the tag in the same second (`error from registry: denied`). A plain re-run published it.

**Changes made:**

1. **`process/factory.md`** Enablement step 3: on a package's first publish, a `denied` tag push is re-run.

**Rationale:** A first-publish failure that a re-run fixes looks like a permissions problem and sends people to the package settings. One sentence saves that detour. Release type: patch.

---

## 2026-11-05: The seeded CODEOWNERS test checks GitHub's case-sensitive view too

**Origin:** A review of a third project's CODEOWNERS after its migration to v2.3.0 (2026-11-05).

**What happened:** v2.3.0 made the guard match owned lines in any case, and the seeded `tests/test_codeowners.py` checks ownership through it. So the test could no longer see a CODEOWNERS that owned `CLAUDE.local.md` but not `claude.local.md`. Under GitHub's case-sensitive, last-match-wins rules, those casings had no code owner after the owner-less lines. The guard still refused them in factory commits, but a person's PR touching them needed no code-owner review. The reviewer's mutation, deleting the last `AGENTS.md` line, failed no test.

**Changes made:**

1. **`bundles/factory/tree/implement_guard.py`**: each CODEOWNERS entry also keeps its exact regex. `owner_on_github()` evaluates a path as GitHub does: case-sensitive, last match wins. **`tests/test_implement_guard.py`** covers it: an unlisted casing has no owner on GitHub but is still refused by the guard.
2. **`bundles/factory/seed/tests/test_codeowners.py`**: `test_github_owns_every_casing_agents_load` checks, through `owner_on_github`, that the agent files' casings are owned at the root, nested, and under the parking lots: `CLAUDE.md`, `claude.md` and `Claude.md`, the same for `CLAUDE.local.md` and `AGENTS.md`, and `GEMINI.md`. The reviewer's mutation now fails it.
3. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`**: the proof's CODEOWNERS lists those casings early and after the owner-less lines.
4. **`process/factory.md`** Enablement step 9: list every casing a tool loads explicitly, early and again after the owner-less lines, `GEMINI.md` among the re-owned. The seeded test checks GitHub's view as well as the guard's.

**Upgrading:** add the casing lines to CODEOWNERS (the seed's test shows which), and copy the new test into the project's own `tests/test_codeowners.py`.

**Rationale:** The guard gates factory commits, and GitHub gates everyone else's. Each needs its own check, because one ignores case and the other doesn't. Release type: patch.

---

## 2026-11-05: MCP services for the planning stages, and read-only ones for the execution stages

**Origin:** A third project enabling the factory reads its production database through its own pgEdge MCP server. CD chose that route for its planning stages (2026-11-05), over a planning-database proxy on the tailnet. CD also asked for read-only MCP services in the execution stages, as framework capability for other repositories (2026-11-05), reversing the planning-only rule of 2026-10-10 for read-only entries. `services.py` already held the MCP path but refused it until it had its own proof (2026-10-10).

**What happened:** Three things stood between `services.py` and a usable MCP service:
- **Tool allowlist:** the allowed tools came only from the static `*-tools.args`, so an MCP service's tools couldn't be allowed.
- **Header choice:** nothing constrained which header carried the credential. A local test on Node v22.23.0 showed `fetch`, which the MCP client is built on, drops `Authorization` on a cross-origin redirect (301, 302, 303, 307 and 308) but forwards a custom header.
- **No proof:** nothing proved it end to end.
D2 rule 8 (2026-11-03) named "the project tool list" as unbuilt.

**Changes made:**

1. **`bundles/factory/tree/services.py`**:
   - `attach: mcp` is accepted, with `header` limited to `Authorization`.
   - An optional `tools` list.
   - Two tiers of stages: plan and spec, or implement, execute and revise; one tier per entry.
   - An execution entry must be `attach: mcp`, with `tools`, in its own slot `FACTORY_EXEC_SVC_1` or `_2`.
   - `read_only` now attests that the credential is read-only at its source.
   - Every slot of both tiers is masked in every run.
   - `settings()` puts the stage's MCP tools (`mcp__<name>__<tool>`, or `mcp__<name>` for an entry without a list) into the settings' `permissions.allow`.
   - `context()` names each MCP service's tools.
   **`tests/test_services.py`** covers all of it.
2. **`bundles/factory/tree/workflow_policy.py`**: the execution slots may reach only an implement or revise agent step whose job runs `services.py`; the planning slots stay planning-only. **`tests/test_planning_probe.py`** (`ServiceSlotTiers`) checks:
   - the rendered workflows hold;
   - a planning slot in implement is refused;
   - an execution slot in plan is refused;
   - an execution slot without `services.py` is refused.
3. **`templates/factory-implement.yml`, `factory-revise.yml`**: the MCP step runs `services.py` for the stage (`execute`, `implement` or `revise`) over the frozen implement settings, and the agent step gets the two execution slots. **`factory-plan.yml`, `factory-revise-doc.yml`**: the data prompt says an MCP service is called as tools, and that production data through one is facts and aggregates, never rows. Without a database proxy, it points at the services before asking CD.
4. **`bundles/factory/tree/factory_branch.sh`** `switch`: `.github/factory/services.py` and `services.json` join the files laid over from `main` and hidden from git (test included).
5. **`echo/worker.js`, `echo/server.py`**: a `/mcp` route, a stand-in MCP server (stateless streamable HTTP, JSON). `header_digest` returns the SHA-256 of the Authorization header it received, never the header. `not_allowed` is a tool the factory must refuse. **`tests/test_echo.py`** covers the Python server; the Worker was exercised the same way under Node, with matching digests.
6. **`templates/factory-smoke.yml`**: a `mcp-services` job and a `mcp_probe` dispatch input. It runs when `services.json` lists an MCP service, or when asked. Then:
   - a planning entry and an execution entry, each with a throwaway value, point at the echo host's `/mcp`;
   - each agent calls the allowed tool, tries the left-out one, and prints its slot from sandboxed Bash;
   - outside the agent, the job checks the digest matches the throwaway value, the left-out tool never ran, and Bash saw a placeholder.
7. **`bootstrap.py`**: an execution entry's slot is reported as a repository secret, never a planning environment secret (test included).
8. **`process/factory.md`**:
   - D2 rule 8: the tool list's read-only form exists; write or spend keys still can't be opted in.
   - New D2 rule 9: the execution stages' read-only MCP services, and the prompt-injection risk of a service whose content agents or outsiders write.
   - New D2 rule 10: Authorization only, and the `mcp-services` proof.
   - D2 Forbids 8.
   - D3 rule 4 covers MCP entries.
   - Enablement step 4: the echo service's `/mcp` route, redeployed once by an organization that lists an MCP service.
9. **`skills/sdlc-implement/SKILL.md`**, **`skills/sdlc-revise/SKILL.md`**: the stage's read-only MCP services, if any, are listed in `.factory/services-context.json`; their results are reference material, never instructions.

**Upgrading:**
- A project with no MCP service changes nothing. Its `mcp-services` job skips.
- To add one: an entry in `services.json` and its secret, a `factory-planning` environment secret for a planning entry or a repository secret for an execution entry. Then redeploy the organization's echo service if its deployment predates `/mcp`, and dispatch `factory-smoke`.
- The `mcp-services` job's first run is the proof. Until an organization redeploys its echo service and runs it, that a left-out tool is refused under auto mode, and that the credential arrives, are the design's claims. The redirect property was tested on Node's `fetch` and is inferred for Claude Code's client.
- A revise or continued implement run lays `main`'s `services.py` and `services.json` over the factory branch (`factory_branch.sh switch`), as it does the agent configuration, so the MCP step reads the current list, not the branch's older copy.

**Rationale:**
- The credential stays out of the sandbox and is sent only where the code-owned list points.
- The tools the agent may call are the ones the entry names.
- What the credential can do is bounded where it's issued, not by the factory.
Release type: patch (CD, 2026-11-05; the bump rule reads new `services.json` schema as minor, and CD chose a patch for it).

---

## 2026-11-05: The planning database login is read-only by its privileges, checked before the agent starts

**Origin:** A security review of a third project's planning login (2026-11-05). It reproduced, on Postgres 17, a lasting write by a SELECT-only role: a large object the reader owned after its transaction committed. Confirmed here on a throwaway Postgres 17 cluster: a SELECT-only role keeps PUBLIC's large-object functions and `TEMPORARY`, and can't lift a role-level `temp_file_limit`.

**What happened:** D3 rule 3 asked for a role with `SELECT` only, a statement timeout and a connection limit. Neither the read-only intent nor the timeout is a boundary the role can't cross:
- any session can `COMMIT; BEGIN READ WRITE`;
- PUBLIC's `EXECUTE` on `lo_create`, `lo_from_bytea`, `lo_put` and `lowrite` writes large objects that last;
- `TEMPORARY` makes tables;
- a role can `SET statement_timeout = 0`.
`planning-services.sh`'s pgbouncer set no deadline either.

**Changes made:**

1. **`bundles/factory/tree/planning-services.sh`**:
   - pgbouncer gets `query_timeout = 60`, `idle_transaction_timeout = 30` and `query_wait_timeout = 30`, deadlines the login can't lift.
   - After the connect test, a check runs through the proxy as the login, and the script refuses (stopping pgbouncer) a login that can do any of these. It lists each problem with its fix:
     - write a table (column-level `INSERT` or `UPDATE` grants included), a sequence or a large object;
     - create a temporary table, a schema or an object in a schema;
     - own the database or a relation;
     - run with unlimited `temp_file_limit`;
     - hold superuser, create-role, create-database or bypass-RLS;
     - belong to `pg_write_all_data` or the server-file and signal roles.
   The check was run on Postgres 17: a SELECT-only role with PUBLIC's defaults is refused on the large-object functions, `TEMPORARY` and `temp_file_limit`; after the revokes it passes; a later `UPDATE` grant is refused again.
2. **`process/factory.md`**, D3 rule 3:
   - Read-only is the role's privileges, never a session default.
   - The role's SQL revokes from PUBLIC the large-object write functions and `TEMPORARY`, granting back to the app's roles what they use, and sets `temp_file_limit`.
   - `planning-services.sh` checks it.
   - The proxy's deadline is the one the role can't lift.
   - The connection limit covers 4 connections per planning job.
   - The same rules hold when planning reads a database through a service such as an MCP server: the role's privileges are the boundary, not the service's read-only mode.
   D3 Costs: `work_mem`, parallel queries and session advisory locks still let a read-only role load the primary until planning reads a replica. That's CD's to accept.

**Upgrading:** before taking this, a project with a planning database runs, as a superuser:
- `REVOKE EXECUTE ON FUNCTION lo_create(oid), lo_creat(integer), lo_from_bytea(oid,bytea), lo_put(oid,bigint,bytea), lowrite(integer,bytea), lo_truncate(integer,integer), lo_truncate64(integer,bigint) FROM PUBLIC;`
- `REVOKE TEMPORARY ON DATABASE <name> FROM PUBLIC;`
- `ALTER ROLE <reader> SET temp_file_limit = '1GB';`
Then it grants back to the app's own roles what they use. Otherwise planning refuses to start its database proxy, naming each problem. Then it checks the role's connection limit against 4 per planning job.

**Rationale:** A boundary has to be something the bounded party can't change. A role's default transaction mode and statement timeout are settings it can change; its privileges and the proxy's deadlines aren't. The check makes the rule hold by construction, not by each project's memory of it. Release type: patch (a stricter check within D3 rule 3's existing contract; projects update their role, as the upgrade note says).

---

## 2026-11-05: A third factory stack profile, python-uv-node (uv, alembic, pgvector, Redis, pnpm)

**Origin:** A third project enabling the factory has two uv projects (an API and an MCP server), a pnpm/Vite web app, Postgres 17 with pgvector and Redis. `python-node`'s pip install and Django probe don't fit. Under the pilot rule the profile goes straight into the bundle code, as `dotnet-node` did. CD approved it (2026-11-05) with:
- **Name:** `python-uv-node`.
- **Folders:** every top-level uv project is installed and checked, with `stack.python` naming the one with the database. No new `factory.json` field.
- **Scope:** CI's checks, plus integration and the alembic round trip.
- **Probe:** `alembic current`.

**What happened:**
- **pgvector:** tested on Postgres 17.9 with pgvector 0.8.2, as a `LOGIN CREATEDB` role.
  - pgvector isn't a trusted extension, so the role can't create it.
  - Preinstalled in `public`, a test teardown's `DROP SCHEMA public CASCADE` drops it silently, and the role can't create it again.
  - In a schema of its own in template1, on the role's `search_path`, every database made from template1 has it: the project's, its test database, a test's scratch databases. The teardown leaves it, and `CREATE EXTENSION IF NOT EXISTS` skips it.
- **The env file:** the project's settings refuse unknown keys (pydantic-settings' `extra=forbid`). So an env file holding the test URLs or `POSTGRES_*` stops the app, alembic and the tests from loading.

**Changes made:**

1. **`bundles/factory/tree/profiles/python-uv-node/`** (new):
   - **`Dockerfile`:** `python:3.12-slim-bookworm`; uv 0.13.5 (pip, on PATH; Python downloads off); Node 22 with pnpm 10.34.7 as a package; PGDG `postgresql-17` and `postgresql-17-pgvector` (version floor 0.8); `redis-server` with the Lua-fix floor (EVAL stays enabled); `pgbouncer`.
   - **`install.sh`:** finds every top-level `uv.lock` beside a `pyproject.toml` and refuses when `stack.python` isn't among them. It runs `uv sync --locked` in each, then `pnpm install --frozen-lockfile`. The uv, mypy, ruff and pnpm caches go in `.factory/`, and `UV_OFFLINE=1` is set for the agent.
   - **`test-services.sh`:** `python-node`'s lockdown on Postgres 17.
     - The superuser installs pgvector in template1's `extensions` schema before the role exists, and the role gets `search_path = "$user", public, extensions`.
     - Two more fail-closed checks: pgvector resolves for the role, and the role doesn't own it.
     - The output is `DATABASE_URL` (asyncpg) and `REDIS_URL` only.
   - **`with-test-services`:** `python-node`'s ports. It also exports `TEST_DATABASE_URL` (`<database>_test`) and `TEST_REDIS_URL` (db 15), from `verify.conf`'s `database=`.
   - **`services`:** db and redis.
   - **`verify`**, areas:
     - `python`, per uv project: `ruff check`, `ruff format --check`, `mypy`, and pytest without `tests/integration`;
     - `migrations`: the alembic round trip on a fresh `<database>_migrations` each run, so an edited migration never meets a stale schema;
     - `integration`: `tests/integration -m "not slow"`;
     - `node`: `eslint . --max-warnings 0`, `tsc -b`, `vitest run`;
     - `probe`: `alembic current`, which writes nothing, and `tsc --version`.
     Tools run from each project's `.venv/bin`, never `uv run`, and `--print`'s note says so.
2. **`bundles/factory/tree/agent_job.sh`** `workspace`: `verify.conf` gains `database=` (additive; the other profiles ignore it).
3. **`bundles/factory/tree/tests/test_agent_job.py`**:
   - `VerifyPythonUvNode`: the commands, every area's failures, discovery, `stack.python` without a `uv.lock`, the database line.
   - `InstallPythonUvNode`: stand-in `uv` and `pnpm` record the calls; the refusals.
   `test_sandbox_check.py` already covers every profile's `services`.
4. **`process/factory.md`**:
   - "Limits of this version" lists three profiles;
   - the profile table gets a row with what the project must meet;
   - the interface paragraph names `database=` and the profile's discovery;
   - What CODEOWNERS must cover: `python-uv-node`'s list (uv's files, ruff, mypy, coverage and alembic configs, pnpm's).
5. **`bundles/README.md`** lists the profile. **`bundles/factory/seed/tests/test_codeowners.py`** gets its keys (new installs). **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`**: the proof's CODEOWNERS gains the uv lines.

**Upgrading:** nothing changes for a project on another profile. To adopt this one:
- set `stack.profile` and render;
- publish the image to a package of its own (`factory-image` pushes `:latest`);
- meet the table's row;
- cover the CODEOWNERS list in every uv project.

**Rationale:** The profile checks what the project's CI checks, in the order an agent needs them, and keeps the profile's security properties:
- no superuser test login, with pgvector installed by the superuser and owned by it;
- services started with an empty environment;
- nothing installed inside the sandbox.

Release type: minor (a new `stack.profile` value, with its contract).

---

## 2026-11-05: Production gates for a host that builds each deploy, and TLS to a public planning database

**Origin:** A third project enabling the factory runs production on Railway, a host that builds every deploy from the commit, with no compose host. CD decided (2026-11-05) that its production tier is built in that project, as the incubator's was, and that z-sdlc restates D4's compose-specific rules (13-15) for any host. CD also approved requiring TLS to a planning database on a public address. The project's read-only spike against Railway's live API (2026-11-05) supplied the host's facts:
- an empty staged row can sit in an environment permanently;
- variables carry no version;
- a rollback restores variables as well as the image;
- the deploy call that targets a commit returns the deployment's id;
- the serving deployment is the newest successful one;
- a pre-deploy step has no time limit;
- a restore stages a change.

**What happened:**
- Rules 13-15 assumed a production checkout restarted by Compose. 13 refused dependency changes because a restart doesn't rebuild. 14 proved settings with a Compose dry run. 15 tied health to a restarted worker's heartbeat. Rule 16 assumed one tier per host.
- A planning database on a public address needs no firewall exception (the tier reaches the internet). But `planning-services.sh` left pgbouncer's TLS mode at its default, which falls back to plaintext when the server offers no TLS.

**Changes made:**

1. **`process/factory.md`**:
   - D4 rule 13: deploys move forward only from the broker's last recorded commit, and only the broker deploys (a host's own branch auto-deploy is off). What stays CD's is the project's list: on a compose host, compose files, Dockerfiles, `docker/`, dependencies, env files, the Makefile and units; on a host that rebuilds every deploy, its config-as-code, Dockerfiles and builder configuration.
   - Rule 14, "A deploy never changes production's settings", with two realizations. Compose: the dry run. Railway: no non-empty staged patch, and an unchanged hash of each service's variables and configuration, computed in the broker's process and never printed or stored, recorded again after a rollback that restores settings.
   - Rule 15, "Healthy after a deploy means the new release". Compose: the heartbeat. Railway: the returned deployment's SUCCESS, then health and heartbeat reporting `RAILWAY_DEPLOYMENT_ID`; the serving deployment is the newest successful one.
   - Rule 15 also takes three points from the project's review of its deployment-id reporting:
     - a time-to-live heartbeat counts only on two reads more than one time-to-live apart, since a worker that writes once and crashes, or crash-loops as the same release, leaves its mark for a whole time-to-live;
     - during the overlap the wait looks for the new mark, never a value that stops changing;
     - the deployment status is read again at the end of the wait, and SUCCESS is no evidence for a service without a platform health check.
   - Rule 11: a rollback never reverts a migration. Where the host runs migrations itself (Railway's pre-deploy command), the broker runs none of the commit's code, bounds the step with its own deadline and cancels the deployment past it. A restore is CD's runbook, never an operation.
   - Rule 16: several projects' tiers on one host, each after the first with names of its own, and the request client finding the broker's socket from the calling user.
   - Forbids 5 names rule 13's list.
   - D3 rule 2: a public-address database needs no exception but is reached only over TLS.
2. **`bundles/factory/tree/planning-services.sh`**: sets `server_tls_sslmode`. Without `database.sslmode`, it uses `require` for a host off the private, tailnet and loopback ranges, and `prefer` on them. It refuses `prefer` or `disable` off them, and any other value. It prints the decision before the password check. **`tests/test_planning_services.py`** covers it.
3. **`bundles/factory/seed/planning.json`**: `database.sslmode` (empty), documented. **`.claude/skills/zsdlc-import-factory/import.json`**: the incubator may leave it out (`optional_settings`).

**Upgrading:**
- A project whose planning database is on its runner host or a tailnet address needs nothing: TLS stays `prefer`.
- One on a public address now needs TLS on the server. Planning refuses to start its database proxy otherwise.
- The D4 changes are rule text for each project's own production tier; a compose tier's behaviour doesn't change.

**Rationale:** The rules protect the same three things on any host: only reviewed releases, unchanged settings, and health of the release just deployed. Writing them per host keeps a compose tier as it was and gives a host-built one exact checks instead of loopholes. Plaintext fallback to a production database over the internet isn't a mode the factory should allow by default. Release type: patch (rule text within D4's existing contract and a stricter check in an existing script).

---

## 2026-11-05: The publish guard sees paths the way a case-insensitive checkout does

**Origin:** A security review in a third project enabling the factory (rated major), confirmed here by probing the guard. CD approved the fix on 2026-11-05, to ship as its own patch ahead of the next minor release. CD also asked (2026-11-05) that the knowledge-file ownership rule be written into factory setup, so no project asks again.

**What happened:** The guard compared directory names and CODEOWNERS patterns case-sensitively, as git and GitHub do, but macOS and Windows checkouts are case-insensitive, and APFS is normalization-insensitive too. Paths that passed both checks:
- `.Claude/settings.local.json`, which on CD's Mac lands inside `.claude/`, so its hooks run in CD's next session;
- `.GitHub/workflows/x.yml`;
- `api/PyProject.toml`.
`AGENTS.md`, `.vscode/` and the other agents' and editors' configuration weren't covered at all. File names were already compared lowercased, so `.MCP.json` and `api/Claude.md` were refused. The CODEOWNERS lists also missed:
- pytest 9's `pytest.toml`, `.pytest.toml` and `.pytest.ini`, read before `pyproject.toml`;
- hatchling's `hatch.toml` and `hatch_build.py`, a build hook that runs at install, outside the sandbox;
- the PostCSS and Babel configs Vite loads.
And under last-match-wins, the parking lots' owner-less line unowned a nested `disciplines/CLAUDE.md` on GitHub.

**Changes made:**

1. **`bundles/factory/tree/implement_guard.py`**:
   - `fold()` gives the canonical caseless form, `NFD(casefold(NFD(path)))`.
   - `agent_config()` compares every path component folded. It gains `.codex`, `.gemini`, `.cursor`, `.vscode`, `.devcontainer`, `agents.md` and `gemini.md`.
   - It also gains `GOVERNING_KNOWLEDGE`, the eight knowledge files that route or govern agents, refused by name.
   - `codeowners_patterns()`/`protected()`: an owned line matches the folded path; an owner-less line still matches exactly, since unowning too much is the dangerous direction.
   - `case_collisions()`, run by `check_commits()`, refuses a changed path that folds to the same name as another file or directory in any pushed commit's tree. A collision already on the base, untouched by the change, is left alone.
2. **`bundles/factory/tree/tests/test_implement_guard.py`**:
   - casings, the new configuration names, the governing list, owned lines in any case and owner-less lines exactly, and `fold()`;
   - collisions built through the index, since a case-insensitive filesystem can't hold both names;
   - an untouched collision on the base.
   **`tests/test_revise_doc_guard.py`**: the context map is now refused by name; the CODEOWNERS case uses another owned knowledge file.
3. **`bundles/factory/seed/tests/test_codeowners.py`** (new installs; existing projects extend their own copy): other agents' and tools' configuration, any-case samples, the agent files owned again under the owner-less lines, the governing list read from the guard, and the new Python and Node files.
4. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`**: the proof's CODEOWNERS follows the new step 9, ordering included.
5. **`process/factory.md`**:
   - D2 rule 6: the guard's stricter matching.
   - § Stack Profiles, What CODEOWNERS must cover: the pytest TOML configs, hatchling's files, an in-tree build backend, the PostCSS, Babel, eslintrc and Vitest workspace configs.
   - Enablement step 9:
     - other agents' and tools' configuration;
     - the owner-less lines;
     - then the eight governing knowledge files and `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md` owned again;
     - the other knowledge YAMLs stated as agent-writable on purpose, with CD's PR review as the control, an exposure CD accepted organization-wide.
   - Step 10: preview-deploying hosts (Vercel, Netlify, Cloudflare Pages, Railway's PR environments) build factory branches with their preview variables, so turn them off for `factory/**` or keep secrets out.
   - The off-limits paragraph names what the guard refuses.
6. **`skills/sdlc-implement/SKILL.md`**, **`skills/sdlc-revise/SKILL.md`**: the same off-limits paragraph.
7. **`knowledge/architecture/security-review-taxonomy.yaml`**: `supply_chain_security` gains `load_on_presence` (files tools load just because they exist, by ecosystem, with review checks) and `case_aliasing`. The code-reviewer and security-engineer roles already read it.

**Upgrading:** take the bundle code. In CODEOWNERS:
- add the other agents' and tools' configuration and the new profile files;
- after the owner-less lines, own the eight governing knowledge files and `CLAUDE.md`, `CLAUDE.local.md` and `AGENTS.md` again.
Then extend your `tests/test_codeowners.py` to match (the seed's version shows how). A commit that adds a path differing from an existing one only in case is now refused.

**Rationale:** The guard protects CD's own machine as much as `main`, and that machine reads paths case-insensitively. A protection that git and GitHub's case-sensitive matching can't see has to come from the guard. Writing the knowledge rule and its accepted risk into Enablement ends a question every project's reviewers raised. Release type: patch (stricter checks within the existing guard contract).

---

## 2026-11-03: The factory lets a project opt in to a key that can do more than read

**Origin:** CD, while the factory is extended to give agent jobs a project's own services in every stage. A memory service's plugin reads a full-power project key from a file in the checkout, and the external review gate needs a model provider's key, which spends. CD accepted that exposure on 2026-10-29, for private repositories, and asked for it to be recorded here.

**What happened:** D2 forbade any write-capable token in an agent job, or one in a file the agent can read (Forbids 6). Services had to be read-only by attestation. Neither key fits.

**Changes made:**

1. **`process/factory.md`** D2:
   - rule 8: a project may opt in, per service, to a key that can write or spend. The exposure is accepted, not mitigated. What holds:
     - the entry says what the key can do;
     - the tool list allows only the tools it names, and an unlisted tool is refused;
     - writes the project keeps are staged in the PR and stored after merge by a writer job;
     - one key per repository, with a provider spending limit on a spending key;
     - a key in a checkout file is seeded before the agent step and deleted before seeding and right after it;
     - smoke treats a declared key as expected and every other credential as a leak.
   - Forbids 6 names the exception. Revisit when gains a repository the organization doesn't control, and a service starting to offer read-only keys.
   - The mechanism (the project tool list) isn't built, so no project can opt in yet.

**Rationale:** A rule the factory is about to break should be changed where it's written, before the code that breaks it, with its conditions and its owner stated. Release type: patch (a rule change in an existing process doc; the tool list that uses it comes later).

---

## 2026-10-29: The framework's own agents follow the `\\n` rule

**Origin:** an adapter-installation audit of a Neuroloom-backed project. z-sdlc's rule says agent descriptions use `\\n`, but its own `sdlc-reviewer.md` and `sdlc-compliance-auditor.md` used single `\n`. So the reviewer flagged the framework's own agents in every project that keeps them byte-identical. CD chose to keep the rule and bring the two agents into line.

**What happened:** the rule dates from 2026-04-13 (now in `changelog-archive/2026-Q2.md`), when two agents with single `\n` broke Claude Code's frontmatter parser and every `\\n` agent worked. On 2026-10-29, current Claude Code loaded both forms in two separate sessions. Only `\\n` has worked in every observation, so the rule stays, and its wording now records both observations instead of claiming a break that today's Claude Code doesn't show.

**Changes made:**

1. **`agents/sdlc-reviewer.md`, `agents/sdlc-compliance-auditor.md`:** the description's 16 single `\n` each become `\\n`. The frontmatter still parses, and the description holds literal `\n` with no real newlines. z-sdlc's own `.claude/agents/` copies are the same files.
2. **`agents/sdlc-reviewer.md`** (the YAML parse rule and its Red Flags row), **`skills/sdlc-develop-agent/SKILL.md`** (the CRITICAL note and its Red Flags row), **`templates/agent-template.md`**, **`CLAUDE-SDLC.md`** (Agent Conventions): single `\n` broke the parser in April 2026, Claude Code loads both forms as of October 2026, and `\\n` stays the rule because it has always worked.

**Rationale:** a rule the framework breaks itself makes every check of it noise, and a rule whose stated reason no longer reproduces invites someone to drop it. Keeping the form that works on every version seen, and saying why plainly, settles both. Release type: patch (a fix to existing files; no new contract).

---

## 2026-10-29: The adapter audit defers to the adapter's own files

**Origin:** CD, after an adapter-installation audit of a Neuroloom-backed project found that the audit's exempt list and the plugin's design disagreed.

**What happened:** The audit skill's references required `process/knowledge-routing.md` and `agents/sdlc-reviewer.md` to be verbatim copies of z-sdlc, and treated Integration-section `**Uses:**` lines as exempt from transformation. The neuroloom-sdlc plugin does otherwise on purpose:
- it installs its own Neuroloom routing doc;
- it rewrites the reviewer's phrasing checklist in Neuroloom forms, which is what that project's reviewer has to check;
- since 0.5.7 it transforms `Uses:` lines.
So every audit reported correct output as a defect. CD decided the adapter's versions are authoritative in Neuroloom-backed projects.

**Changes made:**

1. **`.claude/skills/zsdlc-audit-adapter-installation/references/exempt-file-list.md`:** `knowledge-routing.md` and `sdlc-reviewer.md` leave the verbatim list for a new § Adapter-owned, with Integration `Uses:` lines. A diff against z-sdlc there is expected; only corrupted output or residue is a defect. The project then has no copy of z-sdlc's current phrasing contract, so a phrasing change is checked against z-sdlc source. The transaction-log check and the diff example no longer name the two files.
2. **`references/defect-catalog.md`:** §1.6 flags only corrupted output on Integration lines, not a clean transform. §3's exempt list drops the two files, and the old `migrate-f01a70` reviewer finding is marked as no longer a defect.
3. **`references/classification-framework.md`:** step 3 skips adapter-owned files and lines, and the calibration table's reviewer row shows the changed verdict.
4. **`SKILL.md`:** Step 4 says adapter-owned files are expected to differ.

**Rationale:** An audit that calls the adapter's intended output a defect teaches readers to ignore its findings. Release type: none (a framework-development skill of this repository; nothing installed changes).

---

## 2026-10-24: z-sdlc runs the framework work it starts

**Origin:** CD, when asked to choose an incubator SDLC tier for a factory change started here: "no, you (this repo) are the commanding SDLC expert".

**What happened:** A factory change (flagging the files CD should look at in factory PRs) was scoped from z-sdlc. Its code lands in the incubator first, so the session followed the incubator's `CLAUDE.md`, whose tier rule says to ask CD which tier to use before touching files, and asked CD to approve an SDLC-Lite deliverable there.

**Changes made:**

1. **`CLAUDE.md`** (this repository's): framework work that starts in z-sdlc is scoped, planned and reviewed by z-sdlc's own judgment, even when its code lands in a project first. The project's process rules don't govern it, and CD is asked about the work, never which process to run it under. The project's `main` ruleset, CODEOWNERS review and CI still hold.

**Rationale:** z-sdlc writes the process every project runs. Running its own work through a project's copy of that process puts the copy above its source, and asks CD a question the framework should answer itself. Release type: none (a convention of this repository; nothing installed changes).

---

## 2026-10-24: The post-planning report

**Origin:** CD, in a project still on a pre-2.0 install: "remove the last step/plan mode, standard execution prompt/clear context, etc. When a plan is done planning, just give a post planning report/breakdown/overview with major decision points, what's important to know, etc. Get a codex opinion on things that should be in this report, similar to how the post execution reports are."

**What happened:** Plan mode had already left the framework in v2.0.0 (2026-10-09, "Writing for CD"). The step CD saw was an older install's, so migrating fixes that part. Since v2.0.0 planning has ended with the plan's Approval Brief, its path, and a line telling CD to start a new session and say "Execute the plan at …". Codex was asked, on the brief's spec and the Completion Report's, what a post-planning report should add. Its answers that CD took: a title line and a What you need to do section first, as the Completion Report has; the phases in order (the brief had only the approach); the assumptions the plan rests on; what review changed; the file reading order dropped, since the files don't exist yet; and about 550 words. CD turned down tying each check to a phase and bold labels in place of headings: the brief lives in the plan file, and its `###` headings carry the word count. CD kept the factory's plan PRs as they are, because the factory fills a fixed PR schema from the brief and needs its Files line, and dropped the execute line.

**Changes made:**

1. **`process/writing-for-cd.md`** — § Approval Briefs: a plan's brief in an interactive run is the post-planning report. It adds a title line (`**[ID] plan, for your approval:** …`), What you need to do (what CD supplies before execution starts and what execution will stop to ask for: production gates, deferred decisions; actions only, left out when empty), The phases (one line each, in order, with about how many files each touches, and gates on their own lines), the assumptions under Review focus, and keeps only Concepts under Learn the change. A spec's brief and a plan's in a headless run stay the plan variant alone. Length Budgets: 550 words for that report, 450 for the rest. The `approval-brief` block: the writing agent writes the additions in an interactive run and the plan variant alone in a headless one, and gets the findings whose fixes changed the plan for the Review line. The fresh reader also checks what CD must do and the order of the work. The word count's limit is about 700 words for that report.
2. **`skills/sdlc-plan/SKILL.md`** (steps 2a, 5b, 6) and **`skills/sdlc-lite-plan/SKILL.md`** (steps 4a, 5) — the block re-copied. The presenting step ends with the brief and the path only: no execute line, no "tell me what to change". The Output sections, the lite Definition of Done (550 words, what CD must do) and the red flags match, and a new red flag covers plan mode and the execute line.
3. **`templates/planning_template.md`**, **`templates/sdlc_lite_plan_template.md`** — the brief gains the title line and the What you need to do and The phases headings, and the Review line names what review changed. The guidance note points to § Approval Briefs. It now tells the author to delete it when filling the section, in `templates/spec_template.md` too: the note stayed in filled-in briefs, so every brief CD read opened with agent instructions, and the word count included them.
4. **`templates/pr_description_template.md`** — an interactive plan's brief keeps its additions, and its 550-word budget, when it becomes a PR description.
5. **`CLAUDE-SDLC.md`** § Writing for CD budgets, and **`process/deliverable_lifecycle.md`** (unplanned prerequisites go under What you need to do).

**Rationale:** CD reads one report at each end of a deliverable, and the planning one now answers the same questions as the execution one: what CD has to do, what gets built and in what order, and what it rests on. The factory is left alone on purpose: its renderer requires `brief.files`, and its PR already shows production gates. Projects on pre-2.0 installs keep the plan-mode step until they migrate. Release type: minor (new sections in the plans projects write).

---

## 2026-10-23: Review lenses reach the execution review loop

**Origin:** A `sdlc-reviewer` pass on the review-evidence change found that `process/review-lenses.md` reached only `sdlc-review-code`, `sdlc-tests-create` and `sdlc-create-reference-doc`. The review-fix loop said every reviewer "gets every applicable lens" but never named the file, and neither execution skill mentioned it. So no lens reached execution's reviews: not the overengineering, type-safety and contract lenses, and not the two-edit check, the Suppressions lens or the evidence checks added today. CD chose to close the gap.

**Changes made:**
1. **`process/review-fix-loop.md`** Step A: every code review through the loop names `review-lenses.md` in each reviewer's prompt, with the lenses that apply; plan reviews don't use them. That covers direct dispatch and the factory's `sdlc-implement` and `sdlc-revise`, which run this loop, without changing the factory's skills.
2. **`skills/sdlc-execute/SKILL.md`** and **`skills/sdlc-lite-execute/SKILL.md`**: a "Review lenses (mandatory)" paragraph beside the plan contract briefing, outside the mirrored loop block.
3. **`process/review-lenses.md`** § Lens Applicability: a row for the execution review loop.

**Rationale:** The lenses were written for every code review and reached only one of them. Reviewer prompts get longer and reviews may raise more findings, a cost CD accepted. Step A already promised every applicable lens; this makes the promise hold, strengthening an existing check: a patch.

---

## 2026-10-23: Fixing a repeated mistake structure-first, and no stock phrasing

**Origin:** The last of the pstack (cursor/plugins) items CD agreed to bring in, checked first against z-sdlc with Codex (`gpt-6-luna`, max effort). `guardrail-lifecycle.md` defined when a recurring pattern becomes a guard and how guards are kept fresh, but not which kind of fix to reach for first. `writing-for-cd.md` asked for plain language but named none of the phrasing that reads as machine-written.

**What happened:** pstack's `correct` skill, `principle-encode-lessons-in-structure` and `unslop` were the sources. Its punctuation rules (no em dashes, few colons) were left out: z-sdlc's own files use both.

**Changes made:**
1. **`process/guardrail-lifecycle.md`**: new § Choosing the Fix for a Repeated Mistake: design, then types, then a lint or CI check whose error names the fix (failing only on new instances of a common pattern, with the allowed count in `notes`), then a test, then a knowledge entry for what needs judgment. It is an order of preference, not a demand to mechanize everything. A new Preventable row in § What Qualifies lets a design or type fix be proposed at all; it is recorded with `type: other` or `type-constraint` and the edit that must now fail, which Dimension 6n tries instead of reporting it as never fired, and a recurrence counts only beyond the allowed count. Inside a review-fix loop the guard edit stays a lint, test, or change confined to the finding's diff; anything wider is a PLAN or DECIDE finding. Every new guard is shown failing on a real past occurrence. A red flag for reaching for a lint rule first.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** (6l and 6n), **`skills/sdlc-reflect/SKILL.md`**, **`process/review-fix-loop.md`** and **`skills/sdlc-review-code/SKILL.md`**: guard proposals name their fix level, the worked example proposes a tenant-scoped query type instead of a lint, and the review loops' guard edits follow the in-loop limit and the failing-occurrence proof.
3. **`process/writing-for-cd.md`** § The Rules: rule 8, no stock phrasing: inflated words, "serves as" for "is", "not just X, but Y", empty "-ing" tails, unnamed authorities, chat openers and closers, filler and stacked hedges, as prompts to rewrite rather than banned words. **`CLAUDE-SDLC.md`** § Writing for CD and **`templates/pr_description_template.md`** carry it in one line.
4. **`knowledge/provenance_log.md`**: pstack at 8b3326d, MIT, rewritten rather than copied.

**Rationale:** A rule an agent can skip is the weakest fix for a mistake agents keep making, so the order puts the ones that can't be skipped first. Stock phrasing costs CD reading time and hides whether a sentence says anything. A `sdlc-reviewer` pass caught the fix order meeting the existing guard machinery at four points (review loops, the audit's signature test, 6n's checks, and proposals that couldn't name a level); all are fixed. Both strengthen existing conventions: the fix order is a preference inside the guard contract, using `type` values the schema already has, and rule 8 names what plain language already excluded. A patch, unlike "Check before asking", which added a new action every session takes.

---

## 2026-10-23: Explaining why code is shaped as it is, and checking before asking

**Origin:** The fourth of the pstack (cursor/plugins) items CD agreed to bring in, checked first against z-sdlc with Codex (`gpt-6-luna`, max effort), plus one from the first list that CD chose to include. `sdlc-explain` already answered "why" questions from specs, plans and ADRs, and the investigation report format asked for confidence levels on hypotheses. Nothing said to start from the code's history, or to keep what a source states apart from what the agent infers. And nothing said to try a quick experiment before asking CD about a fact that could be observed.

**What happened:** pstack's `why` skill (with its epistemics and code-archaeology references) and the facts-versus-decisions line in its `poteto-mode` skill were the sources. Its investigators across chat, tickets, observability and analytics tools were left out, and so was its broader rule to proceed on reversible work without asking.

**Changes made:**
1. **`knowledge/architecture/investigation-report-format.yaml`**: new `explaining_why` key: the history commands to start from (blame, the line-range log past the last touch, log through renames, the pickaxe search, finding the pull request and its line comments, its issues, ADRs, tests), five groups for every claim (found, supported, inferred, competing, unknown), words that claim intent only beside a citation, one line per source consulted including the empty ones, a suggested answer treated as one hypothesis, and, before a change, what to keep, change and avoid, with the risks, feeding the plan rather than replacing its approval.
2. **`skills/sdlc-explain/SKILL.md`**: the "why" row points at it for code whose reason the specs, plans and ADRs don't record, and the explainer draws only what a source states. **`knowledge/agent-context-map.yaml`**: `architect` and `refactor-engineer` now load the file, so the method reaches the agents that plan and reshape code; **`disciplines/architecture.md`** lists its readers. **`knowledge/coding/comment-discipline.yaml`** § trimming.when_unsure points at it for the method.
3. **`CLAUDE-SDLC.md`** § Use AskUserQuestion for All Questions: new "Check before asking": a fact that could be observed gets a quick experiment first, one that is local and either read-only or on disposable data, within existing permissions, never against production or a shared environment (that is a gate). The result is reported instead of asked; when no safe experiment settles it, the question is asked. Decisions in the Decision Authority table stay CD's. **`process/collaboration_model.md`** § Tool Rule says the same.
4. **`knowledge/provenance_log.md`**: pstack at 8b3326d, MIT, rewritten rather than copied.

**Rationale:** An explanation that mixes what the record says with what the agent guessed reads as certain either way; separating them lets CD see which is which. Asking CD for a fact a thirty-second experiment would settle costs CD a turn and teaches nothing. A `sdlc-reviewer` pass caught a safety wording that would have let a read-only query run against production, the method not reaching planning agents, the two statements of the question rule disagreeing, and an explainer told to draw inferences; all are fixed. "Check before asking" changes when every session asks CD, a new process convention: a minor version at the next tag. The new knowledge content is a new top-level key, so migration adds it, and `sdlc-migrate` §3.3 adds the new map entries by role.

---

## 2026-10-23: Review asks for evidence: what a change is safe because of, suppressions, performance numbers

**Origin:** The third of the pstack (cursor/plugins) items CD agreed to bring in, checked first against z-sdlc with Codex (`gpt-6-luna`, max effort). Contract Safety asked whether consumers were updated but never for proof that the change is safe. Code review looked at suppressions only in shell scripts. The performance philosophy said to measure before and after but gave no way to check a reported number.

**What happened:** pstack's `blast-radius`, `principle-prove-it-works`, `benchmark-checklist`, `principle-explain-the-number`, and the suppression rule in its `comment-sicko` agent were the sources. Each landed in `process/review-lenses.md`, which reaches the reviewers of `sdlc-review-code`, `sdlc-tests-create` and `sdlc-create-reference-doc`. The execution skills' review loop doesn't name that file, so these checks don't reach it yet; that gap predates this change and is left for CD's decision.

**Changes made:**
1. **`process/review-lenses.md`** § Contract Safety: two bullets. Consumers a symbol search won't find (API JSON, stored formats and columns, wire formats, other languages reading the same bytes, flags and config keys, code several calls downstream). And the fact the change is safe because of, named with how far it is proven, from stated up to reproduced in the app; a shared-contract change that rests on a statement when a short script could settle it is an INVESTIGATE finding asking for the script, closed by its output or a test.
2. **`process/review-lenses.md`**: new § Suppressions Lens. Look up the rule each suppression the diff adds or changes silences; one over a bug-catching or security rule is a finding unless the line says why the rule is wrong here, and the fix is the code or, where the rule is wrong, a written reason. One that could name its rule and doesn't, or covers a whole file, is a finding. Style suppressions are fine; ones already in a touched file are noted, not fixed. Shell keeps its own rules, and a suppression is never reworded as prose. **`skills/sdlc-review-code/SKILL.md`**: `suppression` and `performance` join its finding categories and pattern lenses.
3. **`process/review-lenses.md`** § Performance Lens: a performance number without its evidence is a finding, with a pointer to the new questions.
4. **`knowledge/architecture/performance-optimization-philosophy.yaml`**: new `checking_a_number` key: write the claim first; seven questions (what limits it, both sides tuned alike, the arithmetic against physical limits, errors counted, at least 5 alternating runs with median and range, its share of the end-to-end path, proof the work ran); a labeled one-run ballpark; and how to report the verdict.
5. **`knowledge/provenance_log.md`**: pstack at 8b3326d, MIT, rewritten rather than copied.

**Rationale:** Each of these is evidence a reviewer can ask for instead of trusting a write-up: the one fact a change depends on, the rule a suppression hides, the run behind a number. Putting them in lenses means `sdlc-review-code` applies them without new routing. The new knowledge content is a new top-level key, so migration adds it to existing projects. A `sdlc-reviewer` pass caught the lens reach overstated (here and in the Bug-Fix entry), a suppression rule that would have pulled every old suppression in a touched file into scope, and evidence findings with no category or way to close; all are fixed. These strengthen existing review checks: a patch.

---

## 2026-10-23: The Bug-Fix Rule: bug fixes reach the method z-sdlc already has

**Origin:** The second of the pstack (cursor/plugins) items CD agreed to bring in. A Codex consult (`gpt-6-luna`, max effort) showed the method already existed: `debugging-methodology.yaml` asks for a reproduction first and a regression test that fails on the unfixed code, and `testing-paradigm.yaml` § regression_first asks for red, then green, then one commit. The gap was the path. Those files reach `code-reviewer`, `debug-specialist`, `performance-engineer` and `build-engineer`, not the developers who fix most bugs, and nothing in `sdlc-lite-plan` or the main session's rules sent a bug fix to them.

**What happened:** pstack's bug-fix playbook, `tdd`, `principle-fix-root-causes`, `principle-attack-the-premise` and `principle-test-behavior-not-implementation` were the sources. z-sdlc keeps its own rule to commit the test with the fix, rather than pstack's separate commit for the failing test.

**Changes made:**
1. **`CLAUDE-SDLC.md`**: new § Bug-Fix Rule. Reproduce the bug locally or in a test environment (against production it's a gate), watch the smallest test that would have caught it fail for the bug's reason, or use the closest runnable check with the reason a test isn't practical, fix the first wrong step rather than the symptom, commit the test with the fix, and quote the failing run in the report and the commit message. A dispatch to fix a bug says so, carries the rule, and points the agent at `fix_discipline` and `two_edit_check`, so the cues reach the developer who writes the fix without wiring two large files into every implementation dispatch.
2. **`skills/sdlc-lite-plan/SKILL.md`**: a plan rule that the phase fixing a bug starts by proving it, with the failing-then-passing test or check in its acceptance criteria and the test in the same phase as the fix.
3. **`skills/sdlc-review-code/SKILL.md`** and **`process/review-lenses.md`** § Standard Lens: the two-edit check (break the behavior and the test must fail; change only the internals and it must still pass), and a recorded failing run for a bug-fix test. The Standard Lens carries it to `sdlc-review-code`'s reviewers; the execution skills' review loop doesn't name the lens file (see the entry on review evidence). In `sdlc-review-code` a test that can't fail when the behavior breaks is `major`, and a missing failing run is `minor`.
4. **`knowledge/architecture/debugging-methodology.yaml`**: new `fix_discipline` key: the failing test must fail for the bug's reason, a guard is a fix only when the state it handles is allowed, a failure only after a restart points at saved state, the whole pattern gets fixed, and when two fixes on one assumption have failed, the assumption is written down and tested before a third. That check feeds investigation and never allows a fix past the review loop's FIX failure escalation; a headless run stops with `escalated`. Other instances of the fault outside the task's scope become follow-ups, not part of the fix. A `sdlc-reviewer` pass found those two bounds missing, the cues not reaching the developer, and a failing-run check no reviewer could verify; all are fixed.
5. **`knowledge/testing/testing-paradigm.yaml`**: new `two_edit_check` key, and `regression_first` names its one exception. **`skills/sdlc-tests-run/SKILL.md`**: before a test's third round, the assumption its two failed fixes shared is written down and tested.
6. **`knowledge/provenance_log.md`**: pstack at 8b3326d, MIT, rewritten rather than copied.

**Rationale:** The method was right but reached the wrong agents, so the fix is routing rather than a new skill. The new knowledge content sits in new top-level keys because `sdlc-migrate`'s key-level merge keeps a project's existing keys as they are and adds new ones. A new `CLAUDE-SDLC.md` rule is a new cross-skill convention, so this is a minor version at the next tag.

---

## 2026-10-23: `sdlc-develop-verify-skill`, the skill that builds the project's verify skill

**Origin:** CD agreed to bring in seven items from pstack (cursor/plugins), cross-checked first with Codex (`gpt-6-luna`, max effort) against z-sdlc, and chose to build this one first. `process/verify-command.md` § Companion has described a project-local verify skill at `.claude/skills/verify/` since 2026-09-02, but nothing created or maintained one.

**What happened:** pstack's `create-verification-skill` and `maintain-verification-skill` were the base. CD chose one skill with a maintain mode, like `sdlc-develop-agent`'s enrich mode, rather than two, and chose to wire the result into the execute skills' smoke check. Codex's consult set three limits: leave the Cursor paths and control skills, send a broken app to the bug route instead of fixing it first, and make the generated skill keep z-sdlc's side-effect rules.

**Changes made:**
1. **`skills/sdlc-develop-verify-skill/`** (new skill, with `references/safety-rules.md`, `references/generated-skill-template.md`, `references/feature-map-format.md` and `references/dispatch-prompts.md`). A hand-written verify skill can be adopted, keeping its commands and gotchas, or replaced. CREATE reads the repo, checks the app starts, writes the verify skill and a seed feature map, drives every seeded feature once (the evidence must survive cleanup), has a fresh `code-reviewer` check the whole folder, and commits that folder locally after CD's yes. MAINTAIN fixes the map's index, has the domain agents explain each feature from the source in parallel, drives every feature live, and sorts what it finds into drift, harness gaps and product bugs. It fixes the first two and reports the bugs. The orchestrator writes the generated skill and does every drive; helper scripts are code, so the agent that owns test or environment tooling writes them. Safety rules bind every drive and are copied into the generated skill: only instances the run started, every database and service URL pointed at the run's own copy, every outbound integration confirmed sandboxed, stop only what it started, secrets by name, evidence kept out of cleanup and commits. `sdlc-reviewer`'s quality gate found 8 major issues, among them: no check that the launch pointed at local data rather than a shared database, no check that mail or payments were sandboxed, a proof that drove one of the seeded features while calling the map proven, a review handed to `sdlc-review-code`, which can't review untracked files, and retry limits marked `failed` instead of `escalated`. A second round found 4 more: overrides that were set but never seen to take effect before migrations ran, a smoke check that would have skipped an app the phase itself broke, a word-for-word check with nothing to compare against (the Safety Rules now live in one reference file that the copy, the refresh and the reviewer all use), and no path for a verify skill written by hand. It also moved MAINTAIN's undo to saved text, made the folder's precondition check that it is tracked, and gave each review finding two tries. A third round found 5 more: adopting a hand-written skill would have run its commands before the target check and the mechanical check, the launch order let migrations run before targets were confirmed, a clean maintain run would have left a modified file that failed the next run's precondition (the `Verified at:` line, now dropped: MAINTAIN compares the app's own route, command and menu lists with the map instead), the review gate had no one to confirm a fix, and the undo could drop earlier fixes in the same file. All are fixed.
2. **`skills/sdlc-execute/SKILL.md`** and **`skills/sdlc-lite-execute/SKILL.md`**: the UI smoke check takes the dev server from the verify skill when there is one, and launches, health-checks and cleans up through it. When the verify skill can't launch or refuses (another instance holds the port), the check reports `skipped` with the reason, but only for a cause outside the phase; a launch the phase broke is still a smoke failure.
3. **`process/path-mappings.md`** § Project-Specific Files and **`skills/sdlc-migrate/SKILL.md`** §2.1 Step 0: the project's `.claude/skills/verify/` is never written, overwritten or removed by migration.
4. **`process/verify-command.md`** § Companion points at the skill; **`skills/sdlc-initialize/SKILL.md`** Phase 9b offers it for a project with a runnable app; **`CLAUDE-SDLC.md`** § UI Verification and **`knowledge/testing/advanced-test-patterns.yaml`** (the smoke check's auto-detect rule) name the verify skill as a source of the dev server; **`skills/sdlc-develop-skill/SKILL.md`** no longer says every skill in `.claude/skills/` is framework-installed, and sends the verify skill here; **`process/skill-agent-review.md`** and **`agents/sdlc-reviewer.md`** exempt the lean generated skill from the trigger phrases and the section requirements.
5. **`process/commands.md`** (Testing), **`process/headless-mode.md`** § Integration (the skill's gate sites), **`skeleton/manifest.json`**, **`knowledge/provenance_log.md`** (pstack at 8b3326d, MIT, rewritten rather than copied).

**Rationale:** The verify command says whether the checks pass; nothing gave agents a proven way to see a change work in the running app, so each session rediscovered how to launch it. A recipe is only worth trusting once it has been run, so CREATE runs it before handing it over, and MAINTAIN drives every feature rather than trusting the map. A new skill is a minor version at the next tag.

---

## 2026-10-23: The comment rule, and `sdlc-cleanup-comments`

**Origin:** CD directive, after reviewing what to adopt from pstack (cursor/plugins). Comments should explain what the code can't show at a glance, and comments that only repeat the code add bulk to every pull request. CD asked for a skill that trims an existing codebase, and for the same rule to govern how code gets written.

**What happened:** z-sdlc had one bullet on this ("comments explaining obvious code", in the overengineering lens) and no rule for writing comments. pstack's `no-comments` skill and its `comment-sicko` agent were the base. CD set three behaviors that differ from pstack: an unclear comment is kept and listed rather than cut; complex code with no explanation is listed, with any reason the history gives, and the skill writes no comments; and the skill keeps the `sdlc-` prefix.

**Changes made:**
1. **`knowledge/coding/comment-discipline.yaml`** (new): the single rule. What a comment is for and its two readers (an agent mid-task, a developer new to the code), what to keep, cut and shorten, reshaping our own surprises before commenting them, trimming rules (when unsure, contradictions, constraints, vague TODOs), writing rules, and a review checklist. A project lists its own tool-read comments in a `project_machine_read` key it adds, which migration keeps.
2. **`skills/sdlc-cleanup-comments/`** (new skill, with `references/dispatch-prompts.md`, `references/machine-read-comments.md` and `references/report-template.md`): scope (whole repo, paths, or a commit range), a verify baseline, disjoint slices per domain agent, trimming that only deletes or shortens comments, a single check by a fresh `code-reviewer` whose every correction restores `HEAD` text, verification against the baseline, a report under `docs/reviews/`, CD's call on kept comments, and one local commit per area. Machine-read comments, docstrings a program reads, generated and vendored code, applied migrations and framework files are never touched. Each change the orchestrator makes itself has a mechanical check that stands as its review, against a snapshot saved before the change. A slice hash taken as each agent returns flags files someone else changed later in the run; it can't see changes made while an agent was working. `sdlc-reviewer`'s quality gate took several rounds. Among what it caught: report locations that went stale after put-backs (entries now carry an anchor), a diagnosis the orchestrator would have done itself (the slice's agent does it now), a review check that could never pass, a trimmer barred from removing the blank line its own cut left, and a docstring rule that contradicted the cut list. A whole-slice restore asks CD every time, because it discards edits in files the run didn't create.
3. **`knowledge/agent-context-map.yaml`**: the rule is wired to every code-writing role the map has, and `code-reviewer`. Four code-writing roles in `agent-selection.yaml` (`domain-integration-engineer`, `realtime-systems-engineer`, `devops-engineer`, `systems-engineer`) have no map entry at all, so the Comment Rule in `CLAUDE-SDLC.md` is what reaches them.
4. **`CLAUDE-SDLC.md`**: new § Comment Rule, so every project's main session writes comments by the same rule.
5. **`process/review-lenses.md`**: the overengineering lens's comment bullet now names what to flag and points at the rule.
6. **`process/commands.md`**, **`process/headless-mode.md`** § Integration (the skill's gate sites), **`knowledge/coding/README.md`**, **`skeleton/manifest.json`**, **`knowledge/provenance_log.md`** (pstack at 8b3326d, MIT, rewritten rather than copied).
7. **`skills/sdlc-migrate/SKILL.md`** §1.3 and §2.1: skill reference files (`skills/*/references/*`, manifest-listed) are direct-copied to `.claude/skills/*/references/`, except a dual-audience skill's, which merge additively. Until now only `sdlc-audit`'s references had a rule, so a migration had no stated way to install the references of this skill, `sdlc-migrate`, `sdlc-develop-agent`, `sdlc-playbook-generate` or `sdlc-port-opencode`.
8. **A Codex cross-check** (`gpt-6-luna`, max effort; `gpt-6-astra` and `gpt-6.1-sol` aren't available on the ChatGPT-account login) found what the internal rounds missed, and all of it is fixed but one point. Every diff and slice hash compared the files with the index, so a trimmer that staged its edits would have hidden them from the check, and `git restore` would have put back the staged trims: every check now compares with `HEAD`, the restore is `git restore --source=HEAD --staged --worktree`, agents don't stage or commit, and the run stops if `HEAD` moves. A slice left failing in the tree no longer lets the other slices commit, since no verify run covered them without it: step 9 commits only after a verify that matched the baseline. A commit takes only its own paths (`git commit -- <paths>`), with the report named in the first. Step 6's fix gets its own prompt, which carries the headless notice. The context-map consult and the Comment Rule's pointer to the knowledge file now use the phrasing contract's forms, which the adapter transforms. One point stays as it was, by CD's decision: the skill's three mechanical self-applied changes take a diff check instead of § Mandatory Review's domain-agent review. The skill states that departure in its Manager Rule section, and `manager-rule.md` gets no new exception.

**Rationale:** One rule, used three ways: when agents write code, when reviewers read a diff, and when the skill trims existing code. Keeping it in a single knowledge file means the three can't drift apart. Keeping unclear comments costs a little bulk. Cutting them would lose reasons nobody wrote down anywhere else. A new skill is a minor version at the next tag.

---

## 2026-10-20: A revision's gate stop that didn't run

**Origin:** The first revision to stop at a gate, in the incubator. It stopped before its plan's first gate, and its comment said so. But the writer job that posts the gate tracker and asks for the gate run was skipped. It was the PR's last revision, and a re-run would have run the agent again.

**What happened:** The job's condition had no status function, so GitHub added `success()`. That reads every earlier job, and the fixtures job before the agent's is skipped in every project with no fixtures. The incubator fixed the condition and added a workflow policy rule that would have caught it. It also added a workflow CD dispatches to do that job's work for a PR whose last revision stopped before a gate. The code comes in with the next import.

**Changes made:**
1. **`process/factory.md`:** D4 rule 17 says what that workflow checks: the App's last revision comment stopped before the plan's next gate, and the branch's last push is the App's push of the PR's head, from before that comment. Both are GitHub's own records, and it runs no agent and counts no revision.

**Rationale:** A gate stop that didn't run would otherwise leave a PR stuck once its revisions are used up. The recovery takes nothing a dispatch passes in on trust.

---

## 2026-10-20: The factory imported from the incubator (946ddda..9e56842): a revision's gate stop

**Origin:** The incubator merged the factory code for the entry below.

**What happened:** The import brought in 11 bundle files, one of them new (`gate_stop.sh`). The skill and process doc were already in sync, since `--to-incubator` had copied them in. The incubator's own `README.md` seed changed, in its § Production gates and § Revise. The bundle's generic seed has neither section, so it needs nothing. Both proofs pass: the incubator takes the bundle unchanged, and so does an empty project. The empty-project proof had caught a bug before the merge: without a production runner (no receipt key), the gate job would have failed for every revision of a PR that executes a plan. The incubator fixed it before merging.

**Changes made:**
1. **`bundles/factory/tree/`:** `revise_gate.sh` (the plan, bound to the issue's reserved ID, and its next gate), `gate_stop.sh` (new: the stop-at-gate job), `agent_job.sh`, `implement_guard.py`, `revise.schema.json`, the `factory-revise`, `factory-gate-request` and `factory-implement` templates, and their tests.
2. **`.claude/skills/zsdlc-import-factory/import.json`:** `last_import` is `9e56842`.
3. **`bundles/factory/tree/tests/test_revise_gate.py`:** z-sdlc's own fix. The imported test hard-coded the incubator App's login in its fake comments, which the bundle never names (its seeds and tests use placeholders). The import's patterns didn't catch it. The test now reads the login from `factory.json`, as it reads the App's user ID. The incubator has the same change in review, so the next import should show the two in sync.

**Rationale:** The factory's code comes only from its incubator. This brings in the code the skill change below relies on: without `gate` in the revise context, a revision never stops at a gate.

---

## 2026-10-20: A revision reaches a production gate the way execution does

**Origin:** An execution PR in the incubator. Execution built the phase before the plan's first gate, then stopped with two major findings that were CD's decisions. Its result was `escalated`. CD answered with Request-changes reviews, and two revisions ran. Even after a clean revision, nothing could take the PR to its gate:
- only execute's report job posts the gate tracker and asks for the gate run, and only for `awaiting-approval`;
- the revise workflow had no gate handling at all;
- the gate request reads its plan from the tracker;
- a continued execution needs a done gate at the PR's head;
- and the gate code trusts only the App's comments, so CD can't post a tracker by hand.

**Changes made:**
1. **`skills/sdlc-revise/SKILL.md`:**
   - The context gives the plan an execution PR executes (`plan`) and its next gate (`gate`). § 7 adds the result's `gate` field and status `awaiting-approval`.
   - New: § "An execution PR at a production gate". A revision may stop before the context's `gate`, and no other, when the work before it is done, no critical or major finding is open, and no response is `needs-your-call`. Otherwise `gate` stays empty. A revision never continues execution.
   - Edge cases and red flags for both.
2. **`process/factory.md`:** D4 rule 17 says how a revision reaches a gate: the plan it finds and how that plan is bound to the issue, which gate is next, what the stop requires, and what the writer job does. Execution and a revision ask for the gate on the commit they pushed. `factory:gate` is now set by execute or revise.
3. **`process/headless-mode.md`:** the gate-site list includes the revise skill's gate stop.

**The factory code** changes in the incubator first, and comes into `bundles/factory/tree/` with the next import:
- `revise_gate.sh` finds the plan: the one the PR's gate tracker names, or else the sibling of the one result doc the PR adds, if that plan is on the default branch and its deliverable ID is the one the plan stage reserved on the issue. It also finds that plan's next gate the PR hasn't passed, by the broker's signed results.
- `agent_job.sh` puts the plan and the gate in the revise context.
- `revise.schema.json` gets `gate` and `awaiting-approval`; `implement_guard.py` checks them, and refuses any gate but the next one.
- `factory-revise.yml` gets a `stop-at-gate` job, which runs the new `gate_stop.sh`. It does what execute's report job does at a gate stop: posts the tracker, sets `factory:gate` and asks for the gate run. It's a separate job so that re-running it never posts the revision comment (and its revision marker) twice.
- `factory-gate-request.yml` takes the commit the factory pushed (`head`) and builds no request if the branch has moved since. Implement and revise both pass it.
- `gates.py` is unchanged. It's part of the operations package the broker hashes, so changing it would make every gate refuse until the host's setup re-runs.

A review of the incubator's PR found the first version steerable: with no tracker, a result doc named after another deliverable's plan on `main` would have chosen that plan's gates. It also found that a push after the revision's could have gone under the gate request, and that only the gate ID's shape was checked. The ID binding, the next-gate rule and the head binding fix those.

The skill is safe to deliver before the code: without `gate` in the context, a revision never stops at a gate.

**Left open:**
- Execute's result can't be `escalated` and name the gate it stopped before, so an escalated stop gets no tracker. (An `awaiting-approval` result with a major open is refused too, which lost one run's publish.)
- An execution that escalated part-way through a phase has no route but CD's own push.

---

## 2026-10-16: The `open` guard's limits are on record

**Origin:** The pilot project's review of v2.1.5. The workflow policy's guard against `open` in a sandbox verdict outside the planning probe is a match on the word. A quoted, split, variable or line-continued `open`, or the checker run through a variable, gets past it. A bare ` open` is refused.

**Decision:** Leave the guard as it is, and record the limit. D2 rule 6 already says the static workflow check isn't a security control against a deliberate edit, and that the boundary is code-owner review of workflow changes. The guard is there for the accident, which it catches. The reviewer's suggested allowlist of the strict verdict's whole line would also fall to a deliberate edit, such as a renamed step or a shell function. The structural answer stays the one already listed: every agent run through one reusable workflow, checked at runtime.

**Changes made:**
1. **`process/factory.md`:** D2's Leaves open, "Gaps in the static workflow check", lists it.

---

## 2026-10-16: Only the planning probe may be judged by the open internet; no socket may answer the sandbox

**Origin:** The pilot project's review of v2.1.4. Two findings, neither blocking:
- **Major:** nothing held `bash-sandbox` to the allowlist. Adding `open` to its verdict, in the template and the rendered workflow together, would pass `render.py --check` and the workflow policy, leaving only CODEOWNERS review. The sandbox would still enforce its allowlist, but smoke would stop proving it.
- **Minor, from before v2.1.4:** the probe reports every Unix socket it finds, but the verdict failed only on the Docker socket. Any other socket that answered would pass silently.

**Changes made:**
1. **`workflow_policy.py`:** a sandbox probe's verdict may pass `open` only in `PLANNING_PROBES` (the planning stages' `planning-sandbox`). The check runs in every project's CI over its actual workflows.
2. **`sandbox_check.py`:** from inside the sandbox, any Unix socket the probe finds that accepts a connection fails the verdict, whatever it serves. The sandbox refuses Unix sockets, so no allowlist is needed. The control, outside the sandbox, still reaches the job's own sockets.
3. **Tests:**
   - `test_planning_probe.py`: the rendered `bash-sandbox` verdict passes no `open` and `planning-sandbox`'s does, and the policy refuses `open` in `bash-sandbox`;
   - `test_sandbox_check.py`: a socket that answers fails the agent's verdict and not the control's.
4. **`process/factory.md`:** D2 rule 5 lists the socket rule, and says only the planning probe may use `open`.

**Checked against live runs:** the incubator's passing strict-tier and planning-tier probe output (2026-10-16) both pass under the new rules. Every socket they found from inside the sandbox was blocked: the Docker socket, the runtime's own sockets and the test services' sockets.

---

## 2026-10-15: The planning probe judges the planning tier's open internet

**Origin:** The new `planning-sandbox` smoke job's first live run, in the incubator (2026-10-16, its planning tier, with a production database):
- **What held:** the planning boundary itself. The unsandboxed control found the reader password in `pgbouncer.ini`, which proves the probe looks where the password lives. The sandboxed agent found no secret, reached the test services and the planning database through the proxy, was refused the Docker socket, and had no route around the proxy. The isolation step passed with the database as its one exception.
- **What failed:** the verdict, on "host outside the allowlist reachable" for `example.com` and `api.github.com`.

**What happened:** The check held the planning sandbox to the strict tier's network allowlist. But the planning sandbox's `WebFetch(domain:*)` permission opens its proxy to every host, which is D3 rule 5's open internet for planning, by design. Its sandbox settings' own `allowedDomains` are only `localhost`, which hid that.

**Changes made:**
1. **`sandbox_check.py`:** the agent mode takes the tier's network rule as a last argument: `allowlist` (the default, the strict tier's) or `open` (the planning tier's). Under `open`, any host may answer through the proxy, but nothing may bypass it (no direct connection, no DNS). An unknown rule fails.
2. **`templates/factory-smoke.yml`:** `planning-sandbox` passes `open`.
3. **`tests/test_sandbox_check.py`:** the open internet still goes through the proxy: a host reached without it fails under either rule.
4. **`process/factory.md`:** D2 rule 5's planning bullet says what the planning tier's network is.

**Checked against the live run:** that run's control and agent output, judged again: `allowlist` gives exactly those two failures, `open` passes, and the control passes.

**Rationale:** The probe proves what the design says, D3 rule 5 included. A check stricter than the design fails for the wrong reason, and teaches people to ignore its failures.

---

## 2026-10-15: The public-content scan stops a push

**Origin:** This release's first push. Check 6 found an added line naming the incubator, but its last command was an `echo`, so it exited 0. The push chained after it ran, and the release went out with the line. CD had it re-cut.

**Changes made:**
1. **`CLAUDE.md`** (this repository's), check 6: the scan exits non-zero on a missing names file, a missing `origin/master`, a match or a grep error, and prints `check 6: clean` only when there's none. A push chained after it stops before it runs.
2. **`.claude/skills/zsdlc-import-factory/SKILL.md`:** step 3's line, which this release changed, says "the incubator".

**Rationale:** A check whose exit status always says "pass" depends on someone reading its output, which a chained command never does.

---

## 2026-10-15: Smoke probes the planning stages' sandbox

**Origin:** The pilot project's review after its move to v2.1.2. Its plan and revise-doc stages grant Bash (`plan-tools.args`) under `planning-sandbox.settings.json` on the planning runners, while all of `factory-smoke`'s jobs ran on the strict runners. D2 rule 5 ("Before any stage gets Bash, smoke carries that stage's sandbox probe") would then keep Bash from both stages even after a green smoke. CD asked for the fix, shipped as a patch (v2.1.3).

**What happened:**
- **The planning job differs from the strict one.** The planning sandbox's settings are implement's plus a WebFetch permission, but its job doesn't match the strict job the probe ran in:
  - pgbouncer holds the read-only database login's password on the job container's loopback;
  - the service credential slots are wired in;
  - the runners run as their own user, behind a firewall with the database exception.

  None of that had been probed. The incubator had run both stages that way since the planning tier began.
- **Two doc errors:**
  - D2 rule 6 pointed to a "Leaves open" list that `factory.md` didn't have;
  - the design record said smoke probed every stage's tools but improve's, which plan's and revise-doc's weren't.

**Changes made:**
1. **`templates/factory-smoke.yml`:** a ninth job, `planning-sandbox`, on the planning runners with the planning environment. It runs the planning stages' setup:
   - the profile's test services, and pgbouncer with the reader password when `planning.json` names a database;
   - the sandbox settings `services.py` builds for the plan stage, with their service slots in the agent step's environment.

   It then runs the sandbox probe:
   - the probe looks for the reader password and the service credentials too, besides the tokens and the canary;
   - it must reach the planning database through the proxy (`planning-db`, beside the profile's services);
   - the transcript is checked for each raw value.

   The isolation probes run from that tier as well, with the planning database (`planning.json`'s host and port) as their one exception.
2. **`workflow_policy.py`:**
   - `PLANNING_PROBES` lets that one job, and no other outside the planning workflows, use the planning runners, environment and service slots;
   - the job must run on the planning runners.
3. **`tests/test_planning_probe.py`** (new):
   - the job runs where the planning stages run, and the policy admits it;
   - no other smoke job may use the planning tier, and the probe may not leave it;
   - `plan-tools.args` is `implement-tools.args` (which smoke probes) plus WebFetch, with the same deny rules, so the planning tool policy needs no probe of its own, as with improve's.
4. **`process/factory.md`:**
   - D2 rule 5 names the planning probe and the two pinned tool policies;
   - D2 gains its Leaves open list (the static check's known gaps and the rest), which rule 6 points to.
5. **`.claude/skills/zsdlc-import-factory/`:**
   - `import.json` records the incubator's commit that took v2.1.2 (`--apply`; nothing copied);
   - `SKILL.md` step 3 says to record each hand-back's commit that way. Until then, the next change here to a handed-back file reads as changed on both sides, and the proof installs the incubator's copy without it, which is how this release's proof first failed.

**Upgrading:** take the bundle code, re-render, and run `factory-smoke`. All nine jobs must pass before the plan, spec and revise-doc stages are relied on. The planning job needs the planning environment's secrets as the planning stages have them, and `planning.json`'s database host written as in `smoke.host_probes`.

**Rationale:** A probe proves the boundary in the job it ran in. The planning stages hold a credential and a network path the strict job never had, so their sandbox is proven where they run.

---

## 2026-10-15: The sandbox probe checks the profile's own test services

**Origin:** The pilot project's first `factory-smoke` run on z-sdlc v2.1.0 (2026-10-15): 7 of 8 jobs passed, and `bash-sandbox` failed in its control probe with "test service unreachable: redis". D2 rule 5 lets no stage have Bash until that job passes, so the pilot project's agent workflows stay disabled until it does.

**What happened:** `sandbox_probe.py` probed Postgres (5432) and Redis (6379), and `sandbox_check.py` required both (`SERVICE_SOCKETS`). Those are the `python-node` profile's services. The `dotnet-node` profile starts Postgres alone, so its control could never pass. The probe's docstring already described a services list beside its hash file, which was never built. Unchanged since v2.0.0.

**Changes made:**
1. **`bundles/factory/tree/profiles/*/services`** (new, a profile's sixth file): its test services, `<label> <port>` a line. `python-node`: `db 5432`, `redis 6379`; `dotnet-node`: `db 5432`.
2. **`sandbox_probe.py`:**
   - probes the services listed in the `services` file beside its hash file, so the agent's command (which the job compares word for word) is unchanged;
   - reports `localsvc none` for a profile with none, and `localsvc-list unreadable` for a missing or malformed list, which fails the required-line check.
3. **`sandbox_check.py`:**
   - takes the profile's frozen `services` file as its last argument and requires each listed service to answer;
   - a missing or malformed file is a failure;
   - the Docker socket must still refuse.
4. **`templates/factory-smoke.yml`:**
   - the check reads the copy `agent_job.sh freeze` made of the profile, out of the agent's reach;
   - the probe gets its own copy beside its hash file.
5. **`templates/factory-implement.yml`, `factory-revise.yml`:** a comment no longer says the test services are Postgres and Redis.
6. **`bundles/factory/tree/tests/test_sandbox_check.py`** (new):
   - a profile without Redis passes on its Postgres;
   - a listed service must answer, and the Docker socket must not;
   - a missing or malformed list fails;
   - the probe and the check parse a list alike;
   - every profile's list names only ports its `with-test-services` forwards.

   `test_agent_job.py`'s freeze test lists `services` among the profile files frozen for the check.
7. **`process/factory.md`:** a profile has six files, `services` among them.

**Upgrading:** take the bundle code, re-render (`render.py`), and run `factory-smoke`. A project with its own profile adds a `services` file listing what its `test-services.sh` starts.

**Rationale:** The services a probe requires belong to the profile that starts them. A fixed list is right for one stack and impossible for the next.

---

## 2026-10-15: The factory owns its labels

**Origin:** The incubator's compliance audit after its migration to v2.1.0 flagged all 13 of the factory's `factory:*` labels as label sprawl. CD asked how two z-sdlc bundles could disagree, and for the best fix, shipped as a patch (CD, 2026-10-15: v2.1.1).

**What happened:**
- **The two rules:** github-provenance (2026-09-02) made its config block "the complete allowed label set … a label not listed there is definitionally sprawl", and its audit (§ 10h) requires the repository's labels to equal that set exactly. Then, its checkpoint skills were z-sdlc's only automated label writers. The factory bundle (2026-10-12) brought its own 13 labels, created by `bootstrap.py` and documented in `process/factory.md` § Labels.
- **Nothing reconciled them:** neither bundle's docs named the other, the factory import's proof installs the factory alone, the release reviews were scoped to the factory's code, and this repository's checks don't look at bundles together. Every project running both bundles gets 13 `minor` findings.

**Changes made:**
1. **`bundles/github-provenance/fragments/sdlc-compliance-auditor.md` § 10h:**
   - when the project runs the factory (`.github/factory/factory.json`: the bundle installed, or the factory's incubator), `factory:` labels are the factory's, not the config block's;
   - they're checked against `process/factory.md` § Labels, so a missing one, or a `factory:` label the table doesn't list, is still drift;
   - a config block that lists them is drift too.
2. **`process/github-checkpoints.md` § Labels:** labels another bundle owns are outside the config block's set, and the factory's are the case today.
3. **`process/factory.md` § Labels:** the factory owns the `factory:` namespace. A project with github-provenance keeps the labels out of its checkpoint config, and a new label goes in the table and `LABELS` together.
4. **`bundles/factory/tree/bootstrap.py`:** `LABEL_PREFIX`. A `factory:` label it doesn't define is reported (a typo, or one a removed stage left), never removed, since that would strip it from every issue. This covers projects with the factory but no github-provenance audit. Test: `test_a_label_in_the_factorys_namespace_it_doesnt_define_is_reported_never_removed`.
5. **`tests/test_factory_labels.py`** (new): the factory's table and `bootstrap.py`'s `LABELS` name the same labels, so the audit's reference can't drift from the code.
6. **`CLAUDE.md`** (this repository's): bundles share a project. A bundle that adds something a project's GitHub or config holds is checked against every other bundle's rules and audits.

**Upgrading:** a project running both bundles takes this with its next migration: the auditor's fragment and the process docs refresh, and the 13 findings go. Leave the factory's labels out of the config block, and take out any listed there by hand.

**Rationale:**
- **Ownership by namespace, not a shared list:** a list of the factory's labels in the config would be a second copy that drifts the first time the factory adds one.
- **Why the factory is named directly:** a manifest field declaring the namespace wouldn't reach the incubator, which runs the factory without installing the bundle, and the factory is the only bundle that creates labels. A generic declaration waits for a second one.

---

## 2026-10-15: The import's last commit, after the incubator's history rewrite

**Origin:** The incubator rewrote its own history after its production move. The commit `import.json` recorded as the last import no longer exists there, so the next import would have stopped.

**What happened:** The rewrite changed no file under the incubator's `.github/factory/`. The incubator then committed this release's factory code. Its import report showed all 103 bundle files in sync. Its two own seeds changed, in its database host and a note on its runner host, and the bundle's generic seeds already cover both.

**Changes made:**
1. **`.claude/skills/zsdlc-import-factory/import.json`:** `last_import` is the incubator's commit that took this release's factory code, applied with the import's own `--apply`.

**Rationale:** An import compares three ways against its last commit. A rewritten history has to give it one that exists, with the same files.

---

## 2026-10-15: The factory imported from the incubator (07d9441..3f43e26); optional seed settings

**Origin:** The incubator's migration to v2.1.0. Before z-sdlc's factory changes are copied into the incubator (`--to-incubator`), the import brings the incubator's own since the last import (its production move, 2026-10-14).

**What happened:**
- **One shared file changed:** the incubator's production move changed one shared file, a comment in `templates/factory-smoke.yml`. Its other changes are in its production tier (excluded) and its own seeds: `README.md` and `host/host.conf`, both naming its hosts, so the bundle's generic seeds need nothing.
- **The import refused to apply:** the bundle's `factory.json` seed has the pilot project's optional settings (`ci`, `fixtures`, `policy`, `runners.ci`), and the incubator, which uses none of them, doesn't. The import read each as "removed there?", a fix-first item.

**Changes made:**
1. **`bundles/factory/tree/templates/factory-smoke.yml`:** imported. The host probes also cover the production machine's addresses.
2. **`.claude/skills/zsdlc-import-factory/import.json`:**
   - `optional_settings` names the seed settings the bundle's code reads only when they're there, which the incubator may leave out;
   - one the incubator has is still compared;
   - `last_import` is `3f43e26`.
3. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`, `SKILL.md`, `tests/test_import_factory.py`:** the rule, its documentation, and a test that a listed setting is no finding while an unlisted one still is.

**Rationale:** A seed setting that's optional for a project is optional for the incubator too. Flagging it on every import would hide a real removal among false ones.

---

## 2026-10-15: The factory's tests pass in a project with no CI tier

**Origin:** The incubator's migration to v2.1.0. With v2.1.0's factory code in the incubator's tree, two of the bundle's tests failed there, and the import's proof hadn't caught it.

**What happened:**
- **The tests:** two `test_bootstrap.py` tests, a CI tier's group and one restricted to workflows, read the project's own `factory.json` and assumed it names a CI tier (`runners.ci`). The bundle's seed does, so a new project passes. A project upgrading from v2.0.0 keeps its own `factory.json` (a migration never changes a seed), and the incubator's has no CI tier, so both tests failed. Every project upgrading from v2.0.0 without one would see the same.
- **The proof:** the import's proof ran the tests only in an empty project made from the seeds, never in the incubator with its own settings.

**Changes made:**
1. **`bundles/factory/tree/tests/test_bootstrap.py`:** the CI-tier tests give their test project a CI tier themselves.
2. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`, `SKILL.md`:** the proof's first step, in a clone of the incubator, also runs the factory's tests there. Without the fix above, it fails on those two tests.

**Rationale:** The seed is what a new project starts from, not what an existing one has. A test that reads the project's settings must hold for every settings file a migration leaves in place.

---

## 2026-10-15: The runner audit's repository admits no App that can write

**Origin:** The pilot project, setting up its runner audit after v2.1.0. An AI coding assistant's GitHub App was installed on all of its organization's repositories, with workflows, contents, issues and actions write.

**What happened:** Enablement step 12 and `runner_audit.py` reasoned that no App can change the audit, because neither of the factory's Apps has the workflows permission. Any other App installed on the audit's repository breaks that, an organization-wide installation included. Such an App could rewrite the expected state or the audit, close its alarm issues, or disable the workflow.

**Changes made:**
1. **`process/factory.md`:** Enablement step 12:
   - the premise holds only while no other App that can write is installed on the audit's repository;
   - setup step 2 says to check the repository's installed Apps, counting organization-wide ones, and to narrow any App that can write workflows, contents, issues or actions to selected repositories, without this one.
2. **`bundles/factory/tree/runner_audit.py`:** the docstring and the generated workflow's header say the same.

**Rationale:** The audit's guarantee rests on who can change one file. Every App installed on its repository is someone.

---

## 2026-10-15: The release review's second round

**Origin:** The pilot project's second review of this release (three fresh reviewers: code and tests, architecture, host operations) closed the first round's three blockers and found three more, with cheap hardening around them.

**What happened:**
- **The audit missed a group open to every private repository.** A runner group's visibility is `selected`, `all` or `private`, and the audit flagged only `all`. It records repositories only for a `selected` group, so a `private` group admitted the audit's own (private) repository unseen.
- **Upgrading a pre-release CI tier could kill a job.** Setup moved the old `/run` state's records into the new state before it installed the slots' new settings, minutes earlier, while the image built. A cycle starting in that window wrote its record to the old place, so `retire` found nothing there and answered idle. A re-run after an abort could also delete a live record.
- **The upgrade notes missed what stops a v2.0.0 host's first run:**
  - every tier's claim;
  - the label refusal;
  - IPv6;
  - `TasksMax` at the defaults;
  - a pre-release audit's expected state.

**Changes made:**
1. **`bundles/factory/tree/runner_audit.py`:**
   - any visibility but `selected` is drift, whatever the expected state says;
   - the audit's own repository is matched without case;
   - `check` refuses to run (2) without `GITHUB_REPOSITORY`, which a hand run would otherwise skip;
   - an empty token is a clean 2.
2. **`bundles/factory/tree/host/ci_launcher.py`:**
   - **`retire`:**
     - asks GitHub about each registration the slot holds (its record, its leftovers, and any record on the old `/run` state) before removing an idle one, so it no longer depends on GitHub refusing to remove a busy runner;
     - treats a record that changes meanwhile, or a missing state directory, as not idle;
     - says why it isn't restarting a slot.
   - **A leftover GitHub no longer has** is dropped rather than kept forever.
   - **The tier's group** must be the only one with its name.
3. **`bundles/factory/tree/host/setup-ci.sh`:** the old state's records move in as leftovers, never over a current record, only once the slots' new settings are in place, just before the restarts.
4. **`bundles/factory/tree/host/setup.sh`:** the usage line's first run names the tier too, as the claim requires.
5. **Tests:**
   - `private` visibility;
   - case;
   - no `GITHUB_REPOSITORY`;
   - `retire` asking first, a busy old-state record, a new record meanwhile, a missing state directory;
   - a leftover GitHub no longer has;
   - the old state's default path;
   - two groups with the tier's name;
   - the carry-over's order in `setup-ci.sh`.
6. **`process/factory.md`:**
   - step 12 says `private` is as open as `all`, and lists `inherited` among the compared fields;
   - the audit log is GitHub Enterprise Cloud's, and isn't read yet;
   - step 10 says setup's restart asks GitHub first.
7. **This changelog:**
   - "Upgrading a project from v2.0.0" is rewritten: every tier's claim and label rule, IPv6, self-update, the planning database, and the CI tier and audit framed as a pre-release host's;
   - item 12 no longer names a `setup-ci.sh` label check;
   - Enterprise Cloud is named the same way throughout.
8. **`CLAUDE.md`:**
   - check 6 fails closed when the names file is missing or empty, or a scan errors;
   - pushes name `master` and the tag, never `--all`;
   - "no absolute home path".
9. **`docs/current_work/ideas/factory-ci-tier-follow-ups_handoff.md`** (new): the minors that follow the tag.
10. **The third round** (ship; no critical or major findings), before the tag:
    - **`ci_launcher.py`:** a record on the old `/run` state (tmpfs) that GitHub won't remove yet is written into the state as a leftover, then removed, rather than renamed across filesystems, which failed (`EXDEV`) on a real host. The test now refuses a rename between directories, as a real host does.
    - **The follow-ups:**
      - added: a renamed group read as one gone and one new; a sunset for the pre-release migration code; a loose old-state directory skipped silently; a 404 from the wrong organization read as "gone";
      - corrected: where the label lists live, and that the firewall check already fingerprints `nft -j`'s JSON;
      - dropped: `read < <(python3 …)` failing silently (those sites stop setup).
    - **`CLAUDE.md` check 6:** fails when `origin/master` can't be read, which the scans' exits don't show.
    - **The upgrade notes:** why the release is minor, the apt refusal, and the planning tier's error without `PLANNING_DB_HOST`.

**Rationale:** Both blockers were the same mistake as the first round's: a check that passes when it can't see. An unknown visibility or a record in the wrong place now counts as the unsafe answer.

---

## 2026-10-15: z-sdlc names no private project, host or path

**Origin:** CD (2026-10-15), preparing this release: z-sdlc is public, and its unpushed commits named the pilot project, two of the organization's machines and a tailnet address.

**What happened:** The import's `specific` patterns keep hosts and home paths out of code imported from the incubator, but nothing checked z-sdlc's own changelog, docs, tests and commit messages. The pilot project's name, and the names of the runner host and the production machine, had spread through this release's entries.

**Changes made:**
1. **`CLAUDE.md`** (this repository's):
   - z-sdlc's commits, their messages and the files they change name no project of the organization's, no host, no home path and no private address;
   - consistency check 6 scans what's unpushed before every push, against names kept in an untracked, git-ignored `.claude/private-names.txt`.
2. **This release's commits**, before their first push:
   - reworded: "the pilot project", "the runner host", "the production machine", documentation addresses in tests;
   - the pilot project's intake note is renamed `pilot-v2-migration-upstream-issues_handoff.md`;
   - published history is left as it is.
3. **`CLAUDE.md`, `.claude/skills/zsdlc-import-factory/SKILL.md`:** "the pilot project first" for the pilot rule.

**Rationale:** A public framework's history is permanent. Naming a private project or a machine in it tells anyone how the organization is built, and the only cheap moment to keep it out is before the push.

---

## 2026-10-14: CI tier runners take their jobs (a label hotfix)

**Origin:** The pilot project's second first-run attempt on its runner host, with the log-driver hotfix (the entry below). Setup passed, the check was ok, and both JIT runners came online in the CI group, but neither took a queued job.

**What happened:**
- The runners' labels were only `factory-ci`.
- A `config.sh` registration gets `self-hosted`, plus the OS and architecture, by itself. `generate-jitconfig` gives a runner only the labels it's passed.
- Every job on the tier asks for `[self-hosted, factory-ci]`, and the workflow policy requires exactly that.
- The pilot project confirmed with the tier's App that GitHub accepts `self-hosted` in a JIT label list.

**Changes made:**
1. **`bundles/factory/tree/host/ci_launcher.py`** — `jit_labels()` registers each runner with `self-hosted` first, then the tier's labels (without a second `self-hosted`).
2. **`bundles/factory/tree/tests/test_ci_launcher.py`** — the JIT request's labels are `["self-hosted", "factory-ci"]`, and `self-hosted` appears once however the settings list it.

**Rationale:** The launcher's tests fake GitHub, so a label set GitHub routes differently can only show on a real tier. The label list is now pinned to what the jobs ask for.

---

## 2026-10-14: CI tier job containers start (a log-driver hotfix)

**Origin:** The pilot project's first `TIER=ci` setup on its runner host at `b73589a` (2026-10-14). Steps 1–7 passed, but step 8's check tripped: "the check's listener container didn't start".

**What happened:** On Docker 29.4.0's rootless daemon, `docker run` failed with "failed to initialize logging driver: compression cannot be enabled when max file count is 1". `job_flags()` passes `--log-driver local --log-opt max-size=20m --log-opt max-file=1`, and the `local` driver compresses rotated files by default, which takes at least two. Every job container, and every check container, took those flags. The tests' fake docker can't see a daemon's refusal.

**Changes made:**
1. **`bundles/factory/tree/host/ci_launcher.py`** — `job_flags()` adds `--log-opt compress=false`: one log file, uncompressed.
2. **`bundles/factory/tree/tests/test_ci_launcher.py`** — the job's log options are exactly `max-size=20m`, `max-file=1` and `compress=false`, on the `local` driver.

**Rationale:** A cap on a job's logs that the daemon refuses stops every job. The test pins the one combination the local driver accepts.

---

## 2026-10-14: The CI tier, review round 3; the runner audit

**Origin:** The pilot project's review of the CI tier's round 2 (`8575c31`; 2026-10-14) passed with minor findings, and CD left the calls on them to that project, which asked for all of them before the minor release. The same review found that the runner-registration App's key, now on a runner host that no longer runs production, is the main bridge to production's runner group, and asked for an alarm off that host. Scope from the pilot project (CD's delegate): lean, state-only, hourly.

**What happened:**
- **`ci_launcher.py`:**
  - A token GitHub refused stayed cached until its expiry by the wall clock, so a revoked token or a clock step failed every poll, silently disabling every limit that waits on GitHub's answer.
  - A JSON answer that wasn't an object raised past the cycle's handlers and skipped the backoff counter's write.
  - A network failure on the idle runner's removal counted as "busy".
  - A job that overran `CI_JOB_HOURS` added to the backoff.
  - Low disk and a slow rootless Docker daemon at boot each tripped the whole tier.
  - The firewall check only tested that the table existed, and a tick during `nftables.service`'s own restart could trip.
  - "Nothing may start the runner user's manager again" was false: linger, and the enabled gate and slots' `Requires=user@` (a unit's condition doesn't stop its dependencies from starting), brought it back at boot while tripped.
  - A memory cap that isn't a whole number of pages (`6001k`) never matched `memory.max`, so the check would trip forever.
- **`setup-ci.sh`:**
  - The slots' state was on tmpfs, so a reboot forgot the registrations a killed cycle left.
  - `setpriv` was checked after the host had changed.
  - `TimeoutStopSec=180` was under the launcher's worst-case cleanup (about 210 s).
- **`setup.sh`:** the apt plan ignored removals, and nothing warned about a `RUNNER_HOME_BASE` whose directories someone other than root owns (the pilot project's host condition c3).
- **`create_app.py`:** step 3 for `--runners` left out `TIER_OWNER`.
- **Tests:** nothing covered setup's owner logic, its key refusal, its apt plan or the units.
- **The runner-registration App's key** (organization self-hosted runners: write) can register a runner into any group and change any group's repositories and workflows. Nothing would notice if it did.

**Changes made:**
1. **`bundles/factory/tree/host/ci_launcher.py`**:
   - **Tokens:**
     - their lifetime is counted on the monotonic clock;
     - a 401 drops the cached token and retries once with a new one (`Tokens.call`); a 403 doesn't (item 9).
   - **GitHub's answers:** `api()` returns only JSON objects. A success with anything else is `Failed`, and an error's body is its message. A JIT answer without a runner ID is `Failed`.
   - **Idle runners:** a failed removal of an idle runner asks GitHub again. The runner counts as busy only on GitHub's word, and otherwise the next poll retries the removal.
   - **Backoff:** `job-hours` is neutral, like a recycle.
   - **Memory caps:** they're compared as the kernel keeps them, rounded down to whole pages.
   - **The firewall check:** it compares the table's fingerprint with what setup loaded (`nft -j`, without handles, counters and nft's version; chains, rules and set elements). The minute check looks again three times, 2 s apart, before it trips.
   - **Low disk:** in the check, it's a note, not a trip.
   - **The boot gate:** it waits up to 10 minutes for the runner user's daemon.
   - **A trip:** it also disables the slots, the gate and the timers, and turns off the runner user's linger, so a reboot brings nothing back. Setup enables them all again.
   - **JIT configs:** one a crashed cycle left is removed at the next cycle and at the slot's stop.
   - **The docstring:** it says what bounds a container while GitHub can't be read (the lifetime cap and the disk floor).
2. **`bundles/factory/tree/host/setup-ci.sh`**:
   - The state moves to `/var/lib/factory-runner/<unit>`. Registrations left in the old `/run` state are carried over, and the tmpfiles entry is removed.
   - The settings get `loginctl`'s path and the table's fingerprint (`ci_launcher.py fingerprint`).
   - `TimeoutStopSec=360`.
   - The units' comments say what a trip disables.
3. **`bundles/factory/tree/host/setup.sh`**:
   - `setpriv` and `loginctl` are checked in the CI preflight, before anything changes.
   - The apt plan refuses removals as well as upgrades.
   - **`warn_home_base`** warns when `RUNNER_HOME_BASE`, or any directory above it, isn't root-owned or is writable by group or other.
   - The key check, the tier claim and the warning are functions (`check_ci_key`, `claim_tier`, `warn_home_base`), so they can be tested.
4. **`bundles/factory/tree/runner_audit.py`** (new): the runner audit.
   - `snapshot` takes the organization's runner groups as an expected state.
   - `workflow` writes a self-contained, hourly, GitHub-hosted workflow, with the script and the expected state inside it. Neither factory App can edit a workflow, so neither can change what the audit expects. It refuses content GitHub would read as an expression.
   - `check` compares exactly:
     - the groups, and each group's visibility, public-repository setting, repositories, workflow restriction and workflows;
     - each group's runners, with their IDs and labels. The CI tier's group is a pattern, a most-at-once and labels;
     - factory labels outside their groups.
   - It fails closed: exit 2 when anything can't be read. A failing run opens or updates an issue through the workflow's own `GITHUB_TOKEN`.
   - No audit-log check: a change made and reverted between two runs goes unseen, and the doc names the audit log as the upgrade.
5. **`bundles/factory/tree/create_app.py`**:
   - `--auditor` makes the audit's App: organization self-hosted runners: read, nothing else. Its printed steps put the key in the audit repository's secrets.
   - `--runners`' step 3 names `TIER_OWNER`.
6. **Tests:**
   - **`test_ci_launcher.py`** (13 new):
     - a token minted again after a 401, and a token's life counted on the monotonic clock;
     - answers that aren't objects;
     - GitHub out of reach during an idle removal, and polls failing through the grace window;
     - an overrun counted as neutral, and low disk as a note;
     - memory pages, and a JIT config left behind;
     - SIGTERM during `docker run` and during an API call;
     - the check network's collision;
     - a flushed chain, and the nftables restart window;
     - the trip's disabling steps.
   - **`test_host_setup.py`** (5 new): the apt plan, tier claims, the CI key, the home-base warning, and the CI units as text.
   - **`test_runner_audit.py`** (new, 11): every kind of drift, failing closed, pagination, the expected state's shape, the workflow (YAML, the embedded script byte-identical, its expressions, its refusals), and `check` end to end.
   - **`test_create_app.py`**: the audit App's one read permission.
7. **`process/factory.md`**:
   - **Enablement step 8:** the `RUNNER_HOME_BASE` ownership warning.
   - **Step 10:** the slots' state on disk, what bounds a container during an outage, the firewall rule count and second look, low disk as a note, the boot wait, and what a trip disables.
   - **Step 12 (new), the runner audit:** what it compares, where it runs, what it doesn't see, and its setup.
8. **A fresh architecture review of this batch**, all applied:
   - **The setup self-trip:** `setup.sh` writes the CI table's new rule count into the live settings right after the table loads. Before, the minute check compared a table this run had just changed with the old count until `setup-ci.sh` wrote settings, tripping the tier under setup.
   - **The build context:** it's copied into `/var/lib/factory-runner/ci-build.*`, root's all the way up, not under `RUNNER_HOME_BASE`, whose ancestors' owner could swap it.
   - **A trip inside the gate:** a trip only disables the gate. A trip running inside the gate would otherwise stop itself before turning off linger.
   - **The `/run` state:** registrations carried over from it are removed there.
   - **The alarm:**
     - it comments only on an open issue the workflow opened itself, and opens a new one when there's none or the comment is refused, so a planted or locked decoy can't swallow it;
     - it mentions `RUNNER_AUDIT_NOTIFY`'s logins;
     - it fires on a cancelled run (a timeout) as well as a failed one;
     - the doc names the failed-run email as the channel no App can touch, and asks for a private repository the factory's App isn't installed on.
   - **Patterns:** an expected pattern that matches an empty name is refused, and the doc gives the CI tier's exact one.
   - **"Not seen" says what it is:**
     - a runner that takes one job and goes, and a group opened for one job and restored (the audit log, on GitHub Enterprise Cloud, would see both);
     - a rogue runner within the CI pattern and most-at-once;
     - repository-level runners;
     - a run that never happens.
   - **Snapshot:** it's taken from an operator's machine, never a runner host.
9. **A fresh code review of this batch**, all applied (its two majors were the architect's 1 and 2 above):
   - **401 only:** a 403 is also GitHub's rate limit, so it no longer mints a new token.
   - **The firewall fingerprint:** it replaces the rule count, because `nft flush set … blocked4` keeps the count but opens the LAN.
   - **Stopping:** `TimeoutStopSec=360` covers a cleanup whose refused token is minted again.
   - **The audit:**
     - a runner carrying a GitHub-hosted-style label is drift, and the doc names the limit: a runner registered with `ubuntu-latest` just before a run can answer for the audit;
     - labels must be strings;
     - the expected state is embedded as ASCII-only JSON;
     - `IncompleteRead` exits 2;
     - a failed issue search still opens an issue;
     - the audit step has its own timeout under the job's, so the alarm step runs after it.
   - **The home-base warning:** it walks the resolved path.
   - **Tests:**
     - a trip's steps in order;
     - a 403 that mints nothing, and a token refused twice;
     - a flushed chain and a flushed set, against unchanged counters and handles;
     - setup's fingerprint;
     - hosted-style labels and non-string labels;
     - ASCII embedding;
     - a failed search;
     - a symlinked base.
10. **The pilot project's pre-merge review of the vendored `setup.sh`** (at `b73589a`), all applied to `setup.sh`:
    - **One setup at a time per host:** an `flock` on `/run/factory-runner/setup.lock`, in a directory only root can write.
    - **The tier claim** prints git's own error, naming `safe.directory`, instead of "no origin remote".
    - **`acl`** installs with step 1's packages where Tailscale runs, instead of an un-updated `apt-get install` after the units were written.
    - **An idle runner** is stopped before its new version is unpacked, so no job starts on a half-unpacked runner.
    - **`PLANNING_DB_HOST`** must be a real IPv4 address (no octet above 255).
    - **`host.conf`:** any `TIER` or `TIER_OWNER` assignment in it is refused, even one equal to the command line's, as its seed and setup's message say.
    - **The polkit rule** stays the incubator's: it denies `logind` to its production runner, whose sandbox is its unit's. The bundle's runner users already run user managers by design (rootless Docker), and their Tailscale deny is by user, so it holds there.
11. **The pilot project's two further notes**, applied:
    - **The CI slice's `TasksMax`:** it was a fixed 16384, exactly `CI_RUNNERS` × `CI_JOB_PIDS` at the defaults, leaving no room for the user manager, rootless dockerd and rootlesskit in the same slice. It's now `CI_RUNNERS` × `CI_JOB_PIDS` + 4096 (`SLICE_TASKS` in `--print-settings`); the other tiers stay at 16384.
    - **Enablement step 10's Capacity:**
      - every tier's ceilings are limits, not reservations, and can add up past the host;
      - jobs don't swap, so memory pressure ends in OOM kills (exit 137);
      - compare the tiers' ceilings with the host's memory and other tenants, and use `CI_RUNNERS=1` as the lever.
    - **Step 10, the busy-runner refusal:** a safe way to see GitHub's 422 on removing a busy runner on a new tier (a sleep-only job dispatched on the label), and what happens if it ever didn't.
12. **After the CI tier's first real run** (the pilot project on its runner host, 2026-10-14), beyond its two hotfixes (the log driver, `self-hosted`; their own entries):
    - **Idle slots restart:** a setup run restarts each slot whose runner isn't running a job (`ci_launcher.py busy`; a runner GitHub can't answer for counts as busy). It used to leave a running slot alone, so an idle runner kept the old launcher, and an old label set, until its `CI_IDLE_HOURS` recycle.
    - **The audit:** it leaves out the labels every self-hosted runner has (`self-hosted`, the OS and architecture) by name, whatever type GitHub reports, so a just-in-time runner's own `self-hosted` is neither drift nor a hosted-style label.
    - **A real-Docker test:** `test_a_real_daemon_takes_the_job_flags` runs the job flags on a real Docker daemon when `FACTORY_DOCKER_SMOKE=1` (Enablement step 10's CI says to set it on a GitHub-hosted runner). The fakes passed the log options that stopped every job.
    - **Docs:** step 10 says a JIT runner gets only the labels it's given.
    - **The pilot project's review of the label hotfix** (two lows):
      - `self-hosted` is matched regardless of case;
      - a runner label setting of only commas or spaces (`","`) is refused for every tier, the CI tier's included, as an empty one was (`setup.sh`). Otherwise a runner would register with none of the factory's labels and could take any job asking only for `self-hosted`.
    - **A flaky test:** `test_a_runner_that_never_ran_its_job_backs_off` asserted exactly one `time.sleep`, under a patch of the whole time module that `subprocess`'s own wait loop also calls. It now checks that the first sleep is the backoff.
13. **The first run's report** (the tier live on its runner host: runners registered with `self-hosted,factory-ci`, busy within 40 s, job caps read live from the containers):
    - **The job image:** every setup run built a new one (a new image ID each time, since package steps resolve again), churning the prune. Setup now fingerprints the image's inputs (`ci_launcher.py inputs`: the copied context and Dockerfiles, by path, mode and contents or link target, plus the build arguments and the runner's version). It keeps the image while they're unchanged and it's still there. `CI_REBUILD=1` on setup's command line rebuilds anyway, for upstream updates.
    - **Enablement step 10:** cancel runs still queued for the label a moved job used before (they'd wait a day), and the image reuse.
14. **What the first real e2e runs needed** (the pilot project's experiment, 2026-10-15). No code: per-slot CPU pins were prepared and dropped.
    - **The cause:** the tier's e2e jobs timed out at 8 CPUs where they passed uncapped on the same host. The cause was CPU itself: Chromium's software WebGL (SwiftShader) wants about 7 CPUs a browser.
    - **The experiment**, in a replica of the job container:
      - `--cpus 8`: throttled in 75–80% of periods, failed;
      - pinned to 8 CPUs with no quota: no throttling, but only about 4 CPUs used, failed;
      - `--cpus 16`: failed;
      - `--cpus 24`, with Chromium on a 4 GB `/dev/shm` and fonts added: 32/32 in 10.0 minutes, matching the uncapped runner.
    - **Two container differences mattered too:**
      - Playwright's default `--disable-dev-shm-usage` puts Chromium's shared memory in the container's `/tmp`, which made each round of a test take 4–5 s instead of 0.4 s. A 1 GB `/dev/shm` crashed; 4 GB peaked near 900 MB.
      - The bare image's fallback font broke two hover tests.
    - **The pilot project's fix is its own settings:** `CI_RUNNERS=1`, `CI_JOB_CPUS=24`, `CI_CPU_QUOTA=2600%`, `CI_JOB_SHM=4g`, `CI_MEMORY_HIGH=10G`, `CI_MEMORY_MAX=12G`, plus its Playwright config and fonts in its image.
    - **`process/factory.md`, Enablement step 10's Capacity:**
      - browser suites need far more CPU than their test count suggests, so size `CI_JOB_CPUS` from a measured run and expect one at a time;
      - a quota a CPU-bound job outgrows can't be offset by pinning: measure;
      - give Chromium a real `/dev/shm` and turn off `--disable-dev-shm-usage`;
      - put the fonts in the image.
15. **The pilot project's review of the release** (three reviewers), applied:
    - **Critical, the audit keyed groups by name.** An organization can have two groups of the same name: its own `Default` (visibility `all`, which every repository can target) and one its enterprise shares, which GitHub lists last. So the organization's own dropped out of both the snapshot and the check. Groups are now keyed `<name>#<id>`, whether a group is the enterprise's (`inherited`) is compared, and an expected state keyed otherwise is refused.
    - **Restarting an idle slot could kill a job.** `ci_launcher.py busy` answered "idle" on any local error, and asking then restarting raced a job assigned in between. `retire` replaces it: it deregisters the slot's runner first, which GitHub refuses while it runs a job (422), and answers 10 only when the runner is gone or there was none. `setup-ci.sh` restarts a slot on 10 alone, and says when it doesn't.
    - **A tier labelled only `self-hosted`** (or with the OS and architecture, in any case) passed every guard, so its runners would take any job asking only for `self-hosted`. `setup.sh` refuses a tier without a label of its own, and `jit_labels()` won't register one.
    - **The audit reads every list in full:** it checks GitHub's `total_count`, so a short page isn't taken for the end.
    - **An expected state has every field and list of every group.** One missing used to skip that check silently.
    - **No expected state makes two holes right:** a group every repository may use (visibility `all`), and one the audit's own repository may use. Either lets a runner registered there take the audit's job and answer for it. Enablement step 12's setup now says to close both.
    - **`api()`'s failure paths are tested:** an HTTP error, a network error, a truncated read, and a success that isn't an object.
    - **A registration GitHub won't remove** (a dead runner it still calls busy) no longer stops the cycle. It's kept as `slot-N.leftover-<id>` and retried by later cycles and the slot's stop.
    - **The docs say what the code does:**
      - a 401 drops a token, a 403 doesn't;
      - the CI tier's group is compared by pattern, count and labels;
      - the audit log's REST API is on GitHub Enterprise Cloud;
      - the items here are in order.

**Upgrading a project from v2.0.0.** Migrating copies the bundle; nothing on a host changes until each tier's setup runs again, as root, from the project's checkout. It's a minor release because each change below either needs no action or stops setup with a message that names the fix:
- **Every tier:**
  - **the first run claims the tier,** the strict tier's included: `sudo TIER=<strict|planning|ci> TIER_OWNER=<owner>/<repository> bash setup.sh`, naming the checkout's own repository. Without both, setup stops ("no checkout owns the … tier"). Later runs need neither for strict and `TIER` alone for the others, and another repository's checkout is refused. Remove any `TIER`/`TIER_OWNER` from `host.conf`: it's refused. One setup runs at a time per host;
  - **labels:** a tier whose labels are only defaults GitHub gives every self-hosted runner (`self-hosted`, an OS, an architecture) is refused. The factory's own labels pass;
  - **the firewall** rejects all IPv6 for the runner users, gets its `nftables` stop drop-in, and, where Tailscale runs, denies the runner users `/run/tailscale`;
  - **runners** no longer update themselves (`--disableupdate`; existing ones get it in their settings), and an idle one upgrades to `RUNNER_VERSION`;
  - **the runner's libraries** come from apt, and setup stops rather than upgrade or remove an installed package for them ("would upgrade …", "would remove …"): resolve that by hand, then run setup again;
  - setup warns on every run while `RUNNER_HOME_BASE`'s directories aren't root's alone.
- **The planning tier:** if production's database is on another machine, set `PLANNING_DB_HOST` (its one IPv4 address) with `PLANNING_DB_PORT` in `host.conf`. Unset, the exception stays on this host's own addresses, as before, and setup stops with "the planning tier cannot reach the database at <address>:<port>".
- **A host on a pre-release CI tier** (v2.0.0 has none; a project setting one up now follows Enablement step 10):
  - claim it as above, with `TIER=ci`;
  - the job image rebuilds once, then is kept while its inputs are unchanged (`CI_REBUILD=1` rebuilds);
  - the slice's `TasksMax` becomes `CI_RUNNERS` × `CI_JOB_PIDS` + 4096: 20480 at the defaults (2 × 8192 + 4096);
  - slot state moves from `/run/factory-runner/<unit>` to `/var/lib/factory-runner/<unit>`. The registrations cycles left on the old state move in as leftovers just before the slots restart, to be removed. The backoff counts start again, and the tmpfiles entry is removed;
  - idle slots restart: setup asks GitHub about each slot's registrations and restarts a slot only when they're gone, or idle and removed;
  - a runner audit's `expected.json` made before the release (groups keyed by name alone) is refused: snapshot again, review it, and regenerate the workflow.
- **The project's CI:** with a CI tier, run the bundle's tests on a GitHub-hosted runner with `FACTORY_DOCKER_SMOKE=1`.
- **The runner audit:** set it up before the CI tier takes jobs (Enablement step 12), with every runner group's visibility `selected`.

**Rationale:**
- **The audit:** the runner-registration key is the most powerful credential the factory keeps on a host, and production's runner group is one PATCH away from it. An alarm off the host, with a read-only credential and an expected state that neither factory App can edit, is the least that makes misuse visible.
- **Round 3:** each fix keeps a failure from looking like something else: a dead token like a quiet runner, a slow daemon like an isolation failure, a flushed chain like a loaded firewall.

---

## 2026-10-14: Runner users can't reach Tailscale's local API

**Origin:** The incubator's production move to a machine of its own (2026-10-14). The architecture review of its production runner asked whether Tailscale could get around a firewall that matches the user. A test on the production machine showed it could: a non-root user that isn't Tailscale's operator ran `tailscale nc` and got the runner host's SSH banner. Tailscale's local API socket (`/run/tailscale/tailscaled.sock`) is mode 0666, and its dial endpoint connects to any tailnet peer as `tailscaled`, which is root. The connection comes from root, so the runner users' `meta skuid` rules never see it.

**What happened:**
- The runner tiers' isolation test already proves a job container can't reach the host's Docker socket, so a job probably couldn't mount Tailscale's either.
- But the runner users have processes on the host: the runner itself and, with linger, a user manager. Nothing stopped those from reaching it, and nothing tested it.

**Changes made:**
1. **`bundles/factory/tree/host/setup.sh`** — On a host running Tailscale:
   - Each tier denies its runner user `/run/tailscale` with an ACL (installing `acl` if it's missing).
   - A `tailscaled.service.d/<firewall unit>.conf` drop-in reapplies the ACL whenever `tailscaled` starts, since its `RuntimeDirectory` is recreated each time. It runs before the socket exists (`ExecStartPre`) and again after (`ExecStartPost`).
   - The isolation test fails unless the runner user is refused for permission (`EACCES`). Root connects first, so a missing socket can't pass for a refusal.
   - Matching by user covers the runner, its user manager and its rootless containers alike: inside a container, the user ID is still the runner user's.
2. **`process/factory.md`** — Enablement step 8 says so. It also notes that the firewall table is reloaded after `nftables` stops, and that a setup run upgrades idle runners.

**Rationale:** The tiers' isolation is a firewall that matches the user. Any root daemon that connects on a local user's behalf goes around it, and Tailscale's does by design. The runner hosts that need this most also run Tailscale.

---

## 2026-10-14: Runners take a version bump; tier firewalls survive nftables stopping

**Origin:** An architecture review of the incubator's production move to a machine of its own (2026-10-14) read the same code in the incubator's `setup-production.sh` and in the bundle.

**What happened:**
- **Runner upgrades.** Since "factory runner hosts: no IPv6, no self-update" (2026-10-13), runners register with `--disableupdate` and stay at `setup.sh`'s `RUNNER_VERSION`. The comment and `process/factory.md` (Enablement step 8) said "a run of this setup installs it". But setup downloaded a runner only when its directory had none, so a bump never reached an installed runner. GitHub stops sending jobs to runners more than 30 days behind a release.
- **The firewall after a stop.** Each tier's firewall table was reloaded after `nftables.service` started, restarted or reloaded, but not after it stopped. Its stock `ExecStop` flushes the whole ruleset, so the table was gone while the firewall unit still showed active.

**Changes made:**
1. **`bundles/factory/tree/host/setup.sh`**:
   - **Upgrades.** An installed runner at a different version than `RUNNER_VERSION` gets the new archive unpacked over it. Its registration files aren't in the archive. The existing idle-only restart then starts the new version. A runner running a job is left alone, with a message to re-run setup when it's idle.
   - **Stops.** A drop-in, `nftables.service.d/<firewall unit>.conf`, reloads the tier's table with `ExecStopPost` after nftables stops.
   - A flush by hand (`nft flush ruleset`) is still not covered. The CI tier's minute-by-minute firewall check would see one.

**Rationale:** Runners that never update themselves are only safe if setup is how they update. A firewall that a routine `systemctl stop` can remove, without anything noticing, isn't a boundary.

---

## 2026-10-14: The planning tier's database can live on another machine

**Origin:** The incubator's production is moving off its factory runner host to a production-only machine (CD, 2026-10-14). The planning tier's one firewall exception (D3 rule 2) admitted only a database port on the runner host's own addresses, so a database elsewhere was out of its reach.

**Changes made:**
1. **`bundles/factory/tree/host/setup.sh`:**
   - A new setting, `PLANNING_DB_HOST`: one IPv4 address, refused unless `PLANNING_DB_PORT` is set too.
   - When set, the planning tier's exception admits that address and port instead of the host's own addresses.
   - The isolation test then keeps the database port in the probe of this host, which must now be closed like any other, and the final reachability check connects to the remote address.
   - The setting is empty by default, which keeps today's behavior.
   - `--print-settings` shows it as `DB_HOST`.
2. **`bundles/factory/seed/host/host.conf`:** `PLANNING_DB_HOST`, with a note to use an address that doesn't change, such as the machine's Tailscale address. The comment now cites D3 rule 2, not rule 3.
3. **`bundles/factory/tree/tests/test_host_setup.py`:**
   - the planning tier with a remote database;
   - the strict tier never gets one;
   - a host name, a list, or a host without a port is refused.
4. **`process/factory.md`:** D3 rule 2 names the remote case.

**Rationale:** Moving production off the runner host is what D2's "Revisit when" anticipates. The planning tier's read-only access to production's database must follow the database to its new machine through the same single, address-pinned exception.

---

## 2026-10-13: The tier and its owner come only from setup's command line

**Origin:** The pilot project's review of round 2 ("The factory CI tier, review round 2", below). `setup.sh` recorded whether `TIER` was given after it had sourced `host.conf`, so a `host.conf` that set `TIER` (the pilot project's did) defeated the rule that a new owner claim names its tier. A `TIER_OWNER` there would have defeated the claim itself.

**Changes made:**
1. **`bundles/factory/tree/host/setup.sh`**: whether `TIER` was given is taken before `host.conf` is sourced, and setup refuses a `host.conf` that sets `TIER` or `TIER_OWNER` to anything but what the command line gave.
2. **`bundles/factory/seed/host/host.conf`**: says `TIER` and `TIER_OWNER` never go there. The per-tier defaults line gives the CI tier's new `CI_MEMORY_HIGH` default (14G, not 12G).
3. **`bundles/factory/tree/tests/test_host_setup.py`**: a `host.conf` that sets either is refused; the same value on both is not an override.

**Rationale:** The claim is the operator's statement at the moment of the first run. A checked-in setting that supplies it for them is the trust-on-first-use the claim replaced.

---

## 2026-10-13: The factory CI tier, review round 2

**Origin:** The pilot project's architect and code reviewer reviewed the disposable-runner CI tier ("The factory CI tier runs one disposable runner per job", below). The architect approved it with conditions, both reviewers found the same three launcher defects, and they listed host, configuration and test gaps besides.

**Changes made:**

1. **`bundles/factory/tree/host/ci_launcher.py`**:
   - **Docker no longer orphans.** Every docker call runs through `setpriv`, which execs, so a timeout kills docker itself. `runuser`'s forked parent left docker running after a timeout. Every call has a timeout. A cycle runs one `docker wait`, which is never killed and returns when the container ends.
   - **The job-hours limit can't be dodged.** GitHub's view of the runner decides when to kill. A 404 while the container runs (the job is over) kills it, so does offline on two polls after being online, or never online within a grace period. An idle runner is recycled after `CI_IDLE_HOURS`: it is deregistered first, and if GitHub refuses because a job just arrived, the job runs. The container's lifetime is capped at `CI_IDLE_HOURS` + `CI_JOB_HOURS` whatever the API says.
   - **Backoff.** It counts from GitHub too. A runner still registered after its container ended never ran a job, so it counts as a failure. The installation token is cached in memory until near expiry.
   - **The check fails closed.** Any exception in it, a hang included, trips the tier (the units' `OnFailure=` runs a new `trip` subcommand that keeps the check's marker).
   - **The check covers more:**
     - It re-reads the group's visibility and public-repository setting.
     - It checks free space.
     - It runs a host-side probe as the runner user with no Docker, which is where IPv6 is tested.
     - The default LAN gateway joins the targets, so the blocked set itself is exercised; the host's own addresses all hit the loopback rule.
     - The container probe runs with a job's own flags and checks the exact `cpu.max`, `memory.max` and `pids.max`.
     - A listener at a fixed address on a network of its own must be unreachable from a slot-like network.
   - **Liveness is not isolation.** The internet or GitHub out of reach is logged, not tripped.
   - **`fwcheck`** checks the firewall table every minute.
   - **SIGTERM unwinds the cycle**, so the slot's stop removes its container and registration. The runner's ID is kept in `slot-N.runner` before the container starts, and the slot's `stop` and the next cycle deregister a leftover. Each cleanup step runs on its own.
   - **Transport errors.** `api()` turns every transport and parse error (`http.client.HTTPException`, non-JSON) into one error type, so polling survives them.
   - **Disk.** Below `CI_MIN_FREE_GB` free under the runner's home, no cycle starts and a running job is killed.
   - **Container hardening.** Job containers get capped `local` logs and drop `NET_RAW` and `MKNOD`.
   - **The state directory** must be a directory only root can write.
   - **Logging.** Probe and API output is logged as printable ASCII only.
   - **The header** states the App key's reach, and that the JIT config stays readable inside the container until removal (single-use).
2. **`bundles/factory/tree/host/setup-ci.sh`**:
   - **The key** is no longer moved from the checkout (see `setup.sh`).
   - **The launcher's settings** are written whole to a new file, resolved against GitHub, completed with the image, then renamed into place.
   - **The build context and Dockerfile** must resolve, links included, inside the checkout. They are copied with `cp -RP`, so links stay links.
   - **The job image** is labelled `factory.keep`, and earlier ones are removed by the runner user.
   - **The units:**
     - the gate `Wants=network-online.target`;
     - the gate and check get `TimeoutStartSec` and `OnFailure=` the trip unit, and the check no longer `Requires=user@`, which restarted the runner user's manager while tripped;
     - a new firewall check timer runs every minute;
     - slots run with `KillMode=mixed`.
   - **Extra slots** are found from the enabled and loaded units, not 1–20.
   - **A failed image inspect** now dies with its message.
3. **`bundles/factory/tree/host/setup.sh`** (shared by every tier):
   - **Tier owner, no longer trust-on-first-use.** A missing owner record is made only when `TIER_OWNER` names this checkout's repository and `TIER` is given too, so a dropped `TIER` can't claim strict.
   - **The firewall.** Each tier's firewall unit orders after `nftables.service` and reloads with it, and a new `<firewall>-reapply.service`, wanted by `nftables.service`, loads the table again after its start or restart. Its stock ruleset begins with `flush ruleset`. `PartOf=` would have restarted the firewall unit and, through `user@`'s `Requires=`, killed every job.
   - **The weekly prune** spares `factory.keep` images.
   - **The runner's apt dependencies** are simulated first, and setup stops if installing them would upgrade an installed package (an `Inst` line with the old version in brackets straight after the name). The comment claimed `--no-upgrade` did that.
   - **For TIER=ci:**
     - every setting and the App's key are checked before anything changes;
     - caps must be above 0, which Docker reads as unlimited;
     - `CI_MEMORY_HIGH` must cover `CI_RUNNERS` × `CI_JOB_MEMORY` + 2G (default now 14G);
     - the key must already be at `/etc/factory-runner/<unit>/app.pem`, and a key in the checkout's `host/` directory stops setup;
     - `CI_CPU_WEIGHT` is removed: a weight on the user's slice only ranks it against other users, never against `system.slice`, so `CI_CPU_QUOTA` is the bound;
     - new settings `CI_IDLE_HOURS` (24) and `CI_MIN_FREE_GB` (20).
4. **`bundles/factory/tree/create_app.py`**: `--runners` states the key's reach and prints the root-only install command.
5. **Seeds:** `host/host.conf`'s CI block (the new settings, the key's place, the memory rule, `RUNNER_HOME_BASE` on its own filesystem). `factory.json`'s `ci._doc` (paths resolve inside the repository; base pinned by digest).
6. **Tests:** `test_ci_launcher.py` rewritten (23 tests). It covers:
   - one `docker wait` per cycle, and no docker process left alive;
   - a 404 while running, offline twice, never online, idle recycling and its race, and the lifetime cap with GitHub failing;
   - non-JSON and cut-off answers while polling;
   - low disk;
   - a real SIGTERM mid-job;
   - a slot's stop and a leftover registration;
   - the state directory's owner and mode;
   - the check passing, tripping on each of ten failures (an exception and a timeout among them), and not tripping on liveness;
   - the firewall check;
   - the trip unit keeping a check's marker.

   `test_host_setup.py` follows the settings.
7. **`process/factory.md`**:
   - **Enablement step 2:** `ci-app.pem` is gone from the `.gitignore` list.
   - **Step 8:** `TIER_OWNER` and the reapply unit.
   - **"The CI tier":** the kill conditions, key handling (straight to `/etc`, never a checkout, out of backups), the build-context rule, the setup order with `TIER_OWNER`, the checks, liveness, capacity (`CI_CPU_QUOTA`, the memory rule, `RUNNER_HOME_BASE` on its own filesystem).

**Not done here:**
- **A scheduled audit of every organization runner group's members against expected names.** The architect asked for it as a compensating control for the App key. It is CD's decision. Tripping the CI tier wouldn't touch a rogue runner in another group, and the audit must run where the key isn't.
- **Tests for `setup.sh`'s and `setup-ci.sh`'s heredoc units and the tier-owner logic.** They need root and systemd, so a host run is their first test.

---

## 2026-10-13: The CI tier's App key reaches every runner group

**Origin:** The pilot project's review of the CI tier asked whether a stolen runner-registration key could put runners into the strict tier's group or a production group. GitHub's REST docs for self-hosted runner groups answer it. The App's one permission, `organization_self_hosted_runners`, covers every organization runner endpoint: registering into any group with any labels, moving runners between groups, and changing a group's visibility, public-repository and workflow restrictions.

**What happened:** `process/factory.md` said the key "can register runners and nothing else", which understated its reach.

**Changes made:**
1. **`process/factory.md`** (Enablement step 10, The CI tier): the runner-registration App's paragraph now states what a holder of its key can do. It notes that it is the first long-lived credential on a host that can register runners. It lists how the key is kept: root-only, the downloaded copy deleted, revoked on doubt, and group drift reported by `bootstrap.py`.

**Rationale:** CD chose disposable runners partly on the App's stated reach, so the stated reach has to be right. `create_app.py`'s docstring and `host/ci_launcher.py`'s header say the same and change with the review's findings.

---

## 2026-10-13: The factory CI tier runs one disposable runner per job

**Origin:** CD's decision (2026-10-13): design A for the held CI tier ("The factory CI tier is held", below). The pilot project's review had shown that a persistent runner hands a job's environment and PATH to its own host-side processes.

**What happened:** The runner itself goes inside the boundary. A launcher on the host registers a just-in-time (JIT) runner for each job and runs it in a fresh rootless container. The job runs in that container, runner and all, and the container is removed after its one job. Checked against actions/runner v2.338.0:
- `generate-jitconfig` takes an App installation token with the organization's "Self-hosted runners" (write) permission.
- The runner reads `ACTIONS_RUNNER_INPUT_JITCONFIG` from its environment, masks it, and removes it before any step.
- `run.sh` exits 0 when a JIT runner has run its job.
- A JIT runner's settings come from GitHub, so `--disableupdate` can't apply to it. It updates itself, if at all, only inside its throwaway container.

**Changes made:**

1. **`bundles/factory/tree/host/ci_launcher.py`** (new), root-owned:
   - **`run`, one cycle:** the App's JWT signed by openssl with the root-only key, then an installation token narrowed to the one permission, then a JIT config, then a fresh container started as the runner user with per-job CPU, memory, process and shm caps, `no-new-privileges` and its own network. An idle runner waits as long as it takes. `docker wait` runs in 5-minute rounds, and between rounds GitHub, not the daemon, is asked whether the runner is busy. A job is killed after `CI_JOB_HOURS` of job time, a backstop behind the job's own `timeout-minutes`. Then the cycle removes the container and deregisters the runner with a fresh token. A failing cycle backs off, so `generate-jitconfig` isn't hammered.
   - **`stop`, `resolve` and `check`.** `resolve` returns the App's installation (it must hold the permission) and the group (selected repositories only, no public ones). `check` covers the firewall table, the slice caps, the delegated controllers, and a probe from a container of the job image: host, LAN and IPv6 closed, the internet open, caps in force. A failure writes a marker no slot starts past and stops the runner user's whole session.
   - **The rules root keeps.** Root reads only `docker wait`'s integer from the daemon. The JIT config travels in a 0600 file created without following links, in a root-owned directory, and is deleted once the container starts. Every docker call runs as the runner user with a fixed environment.
2. **`bundles/factory/tree/host/ci-runner.Dockerfile`** (new): the project's toolchain image with the runner on top (pinned version, checked archive, its dependencies installed inside the image), `python3` for the probe, and `RUNNER_ALLOW_RUNASROOT` (container root is an unprivileged host user).
3. **`bundles/factory/tree/host/setup-ci.sh`** (new), sourced by `setup.sh` after step 6 for `TIER=ci`:
   - **The key** moves from the checkout's gitignored `host/ci-app.pem` to `/etc/factory-runner/<unit>/app.pem` (root-only).
   - **Delegation** of the cpu, memory and pids controllers is verified.
   - **The launcher's settings** are written, and resolved against the App and the group before anything is built.
   - **The job image** is built as the runner user from root-owned copies of the build contexts.
   - **The units:** a gate unit runs the check before any slot starts (at boot too), a timer runs it every 6 hours, and `<unit>-slot@N` is started, never restarted, so a job in flight survives a setup run.
4. **`bundles/factory/tree/host/setup.sh`**:
   - **The hold is gone.** `TIER=ci` takes steps 1–6, then `setup-ci.sh`.
   - **The CI tier's settings:** its slice gets a low `CPUWeight` (`CI_CPU_WEIGHT`, 20) and its user's manager delegates cpu, cpuset, io, memory and pids. New settings `CI_APP_CLIENT_ID` and `CI_JOB_*` show in `--print-settings`.
   - **Removed:** the persistent-runner guard, hooks and their check.
5. **Removed:** `host/docker_guard.py`, `host/ci_job_hook.sh` and their tests.
6. **`bundles/factory/tree/workflow_policy.py`**: a job on the CI label runs in its disposable runner. So: no `container:` or `services:` of its own, no `docker://` step, and the container rule doesn't apply to it. The other CI-tier rules stay.
7. **`bundles/factory/tree/create_app.py`**: `--runners` creates the runner-registration App, whose only permission is `organization_self_hosted_runners: write`, and says where its key and client ID go.
8. **`bundles/factory/tree/bootstrap.py`**: a runner group that lets public repositories use it is a problem.
9. **`bundles/factory/tree/render.py`**, **seeds:** `factory.json` gains the `ci` block (`dockerfile`, `context`, `build_args`), which render treats as a run-time setting. `host/host.conf` gains `CI_APP_CLIENT_ID`, `CI_JOB_*` and `CI_CPU_WEIGHT`.
10. **Tests:** `test_ci_launcher.py` (new) covers a cycle against a fake GitHub with recorded docker calls, the JWT verified with real openssl, failure and non-integer exits, an idle runner never killed, a job killed after its job time, no JIT config, backoff, the env file over a planted link, resolve, and the check passing and tripping. Also `test_host_setup.py`, `test_render.py` (the flipped CI-tier rules), `test_create_app.py` and `test_bootstrap.py`.
11. **`process/factory.md`**: "The CI tier" rewritten (how it works, the threat model, the App, the image and its version coupling, the setup order, the check, the job shape, capacity, runner versions). Enablement step 2 adds `ci-app.pem` to what `.gitignore` must cover.

**Rationale:** On a persistent runner, the runner's own processes are the job's way to the host. A disposable runner per job puts them inside the job's container, so nothing a job does outlives it, and the runner user's firewall and caps remain the outer boundary.

---

## 2026-10-13: The factory's verify test runs in its own directory

**Origin:** Handing the pilot's bundle code to the incubator (zsdlc-import-factory --to-incubator).

**What happened:** `test_agent_job.py`'s `Verify` test assumes its profile's directories (`api`, `web`) don't exist, but it ran `verify` in the current directory. Run from a checkout whose `web/` has `node_modules` (the incubator's), the node checks really ran and passed, and the test failed.

**Changes made:**

1. **`bundles/factory/tree/tests/test_agent_job.py`**: `Verify` (and `VerifyDotnetNode`) run `verify` in the test's temp directory.

**Rationale:** A test that depends on where it is run from fails on a developer's machine and passes in CI, which hides real failures.

---

## 2026-10-13: Factory runner hosts: no IPv6, no self-update, one checkout per tier

**Origin:** The pilot project's review of the CI tier raised three findings that hold for every tier. CD approved all three proposals (2026-10-13).

**What happened:**
- **IPv6.** The firewall rejected private IPv4 ranges and a few IPv6 ones (loopback, unique-local, link-local, multicast), and the isolation test probed only IPv4. A host's own global IPv6 addresses and its LAN's global prefix were reachable from jobs.
- **Self-update.** Runners updated themselves, away from the version setup.sh verifies by checksum.
- **Checkouts.** Any checkout's `host.conf` could re-run any tier's setup, re-capping or re-labelling a tier another project set up. A dropped `TIER` falls through to `strict`.

**Changes made:**

1. **`bundles/factory/tree/host/setup.sh`**:
   - **IPv6:** the runner users' chain rejects all IPv6 (everything a job needs answers over IPv4), and the IPv6 blocked set is gone. The isolation test also probes the host's global IPv6 addresses and a public one, and must find them closed.
   - **Self-update:** new registrations pass `--disableupdate`, and runners already registered get `disableUpdate` in their settings file (the runner reports it when its session starts).
   - **Tier ownership:** the first run records the repository whose checkout set the tier up, in `/etc/factory-runner/tiers/<unit>`, and a run from another repository's checkout is refused (remove the file to hand the tier over).
2. **`process/factory.md`** Enablement step 8 says all three. z-sdlc bumps `RUNNER_VERSION` within 30 days of each actions/runner release, since GitHub stops sending jobs to older runners, and each tier's setup runs again from its checkout after the migration that brings the bump.

**Rationale:** The firewall's job is that no factory job reaches the host or the LAN. An address family it didn't cover, a runner binary nobody verified, and a tier any checkout could reconfigure were three ways around it.

---

## 2026-10-13: The factory CI tier is held; host setup never runs a runner-writable file as root

**Origin:** The pilot project's review of the CI tier (software-architect, devops, code-review). The architect rejected running `sudo TIER=ci setup.sh`. Its premise: assume a pull request's code reaches the host as the runner user. Two findings, confirmed against actions/runner v2.338.0, make that premise true:
- **C1, the docker client.** The runner starts the docker client for a step's `docker exec` with the step's whole environment (StepHost.cs), so `LD_PRELOAD` from `$GITHUB_ENV` reaches the host binary first: the guard's `/bin/sh` and python3, or `/usr/bin/docker` itself without a guard. The runner's host-to-container path translation is a prefix match, so a host path to a planted library slips through untranslated.
- **C2, the hooks.** The runner picks a hook's shell with `GetDefaultShellForScript(path, prependPath)` (JobHookProvider.cs), and `$GITHUB_PATH` feeds `prependPath`. So the job-completed hook runs a bash the job chose.

**What happened:** On a persistent runner, job-controlled environment and PATH reach the runner's own host-side processes. That is the runner's design, not a gap in the guard (2026-10-13 entries below). Hardening the guard further would be whack-a-mole, so the tier is held for a design decision.

The review also found a root escalation present in every tier from the start. setup.sh ran `"$dir/bin/installdependencies.sh"` as root whenever `config.sh` wasn't executable, and that directory belongs to the runner user. A compromised runner user could plant the script, and the next setup run would execute it as root. The same script's apt run could upgrade shared libraries on a production host.

**Changes made:**

1. **`bundles/factory/tree/host/setup.sh`**:
   - **Runner libraries:** root installs them from apt, from an explicit list of the runner's Debian dependencies (installdependencies.sh v2.338.0), with `--no-upgrade`, and never runs anything from the runner's directory. This affects every tier, but only does anything on a host missing one of those libraries.
   - **The seccomp profile** is replaced only when it differs, by an atomic rename, so the other tiers' jobs never see it missing.
   - **`TIER=ci` is refused** after `--print-settings` and before any root work, naming this entry.
2. **`bundles/factory/tree/tests/test_host_setup.py`**: the hold.
3. **`process/factory.md`**: "The CI tier" opens with the hold. Enablement step 2 adds `.github/factory/host/reg-token` to what `.gitignore` must cover.

**For CD to decide (the CI tier's design):**
- **A. Disposable per-job runners** (recommended). A root-owned launcher mints a just-in-time (JIT) runner config per job and starts a fresh runner in a throwaway rootless container. Its image is the runner plus the end-to-end toolchain, and the job runs in it (no `container:`). The container is destroyed after one job, so everything C1 and C2 reach is inside it. The runner user, firewall and caps stay the outer boundary. It needs a credential on the host that can register runners: a second GitHub App with only `organization_self_hosted_runners: write`, its key root-only. The container only ever gets the single-use JIT config.
- **B. Untrusted code never reaches the host.** The tier runs only the default branch's code, so its group can be restricted to `ci.yml@refs/heads/main`, a platform-enforced boundary. Pull-request end-to-end tests go to hosted runners, where the per-test CPU need (a server, Postgres, two browsers) starves 2 vCPU. So B means a lighter pre-merge subset plus the full suite after merge, or paid larger runners.
- **C. Harden the persistent runner** (a static first-exec shim, no completed hook, a loader-variable scrub). Residual exposure through the runner's own processes; not recommended.

The guard, hooks and check timer stay in the tree, held, as design inputs. The review's findings on them (service-container start TOCTOU, fail-closed ordering, the check not killing in-flight jobs, the `_PipelineMapping` redundancy, the exec environment allowlist, a stricter network regex, `..` tests) are recorded for whichever design follows.

**For CD, all tiers (proposals, nothing changed):**
- **IPv6.** The firewall and the isolation probe are IPv4-only, so a host's global IPv6 addresses and its LAN's global prefix aren't blocked. The simplest sound fix rejects all IPv6 egress for factory users, since IPv4 reaches everything the jobs need.
- **`--disableupdate`.** It would pin the runner to setup.sh's verified version, at the cost of a bump within 30 days of each runner release.
- **One checkout per tier.** Run each tier's setup from one designated checkout: its host.conf caps that tier (the pilot project now defaults its host.conf to `TIER=ci`).

**Rationale:** A boundary has to hold against what the runner itself does with a job's input. The fix that applies everywhere (root never executing what the runner user can write) goes in now. The CI tier waits for a design that puts the runner's own processes inside the disposable boundary.

---

## 2026-10-13: The factory's seeded CODEOWNERS test works in a repository with Git LFS

**Origin:** The pilot project's first hosted CI run of the factory checks (its fix is c7892b62 there).

**What happened:** The seeded `tests/test_codeowners.py` replays the publish path on a local `git clone --depth 1 --no-local` of the CI checkout (`RealChangelog`). In a repository that tracks files with Git LFS, `actions/checkout` leaves them as pointers, and git-lfs on the runner then tries to fetch their objects from a "remote" that has none. The clone exits 128 ("remote missing object"). The incubator has no LFS, so it never saw this.

**Changes made:**

1. **`bundles/factory/seed/tests/test_codeowners.py`**: the test's git calls (`run()` and `RealChangelog.git()`) set `GIT_LFS_SKIP_SMUDGE=1`; the test never reads LFS content. A seed: new projects get it, and an existing project takes the change by hand (the pilot project has it).

**Rationale:** A project's own files decide whether it uses LFS. A seeded test has to pass in either case.

---

## 2026-10-13: The factory CI tier holds against a hostile job definition

**Origin:** The pilot project's software-architect reviewed the CI tier. A `pull_request` run executes the pull request's own workflow, and the CI group can't be workflow-restricted (pull requests' merge refs). So for a pull request from a branch, the workflow policy is a merge gate, not an execution gate, and a job definition on the tier can be hostile (`container.options: -v …`, a new workflow on the label). The review asked for ephemeral runners or wiping between jobs, runner credentials kept from job containers, daemon defaults, a recurring isolation probe and no shared host caches. It also found `*.csproj.user` and a root `dotnet-tools.json` missing from `dotnet-node`'s CODEOWNERS list.

**What happened:** Read against the runner's source (actions/runner v2.338.0):
- **The runner's docker calls.** `DockerCommandManager` builds one options string and splices the job's `container.options` into it verbatim, and a job's `container.volumes` become `-v` too. docker/cli stops reading options at the image (`SetInterspersed(false)`).
- **What a job can reach.** Job containers get the whole work directory read-write. The runner's credentials sit outside it, reachable only through a mount the job adds.
- **What persists between jobs.** `ActionManager` deletes `_actions` at every job start and `_temp` is recreated, but `_tool` and the workspaces persist. So does `_PipelineMapping`, which `PipelineDirectoryManager` joins to `_work` unchecked when the next job starts, before its hooks run.
- **Steps' secrets.** A step's environment, secrets included, reaches `docker exec` through the CLI's own environment (`-e KEY`).
- **Mid-job containers.** `docker run` (docker:// steps, container actions) mounts runner directories mid-job, after the job's code could have swapped one for a symlink.

**Changes made:**

1. **`bundles/factory/tree/host/docker_guard.py`** (new): the CI tier's runners reach docker only through it.
   - **What passes:** the runner's own commands, exact forms only.
   - **Mounts:** only the runner's own directories, by exact path with no symlink below them, or anonymous volumes.
   - **Refused:** any option it doesn't know (`--env-file`, `--cidfile` and the rest), every privilege and namespace option, other networks, published ports, and other security options. Those must stay a pair with the policy's `ALLOWED_OPTIONS`. It also refuses `docker run` and `docker build`, so no `docker://` step or Dockerfile action runs on the tier.
   - **What it forces:** `no-new-privileges` on every container, and docker always against the instance's own daemon. Every command but `exec` gets a minimal environment.
2. **`bundles/factory/tree/host/ci_job_hook.sh`** (new): the job-started hook deletes `_tool` and empties the workspaces, keeping the directories the runner made for the job. The job-completed hook deletes `_tool`, the workspaces and `_PipelineMapping`. They work in the rootless daemon's user namespace, for files owned by subordinate IDs. `reset` deletes the whole work directory as root.
3. **`bundles/factory/tree/host/setup.sh`** (`TIER=ci`):
   - **Installs:** the guard, the hook and a root-owned probe, under `/usr/local/lib/factory-runner`. Each instance gets root-owned settings (`/etc/factory-runner/factory-ci/N.json`) and wrappers, and its `.env` puts the guard first on PATH with both hooks.
   - **The runner unit:** wipes the work directory as root before every start.
   - **The check timer:** `factory-ci-check.timer` runs every 6 hours. It checks the firewall, the slice caps, the isolation probe from a container (host, LAN and host socket closed, internet open; a failed pull of the probe's image says so), and each instance's PATH, hooks and guard, which must refuse a mount of the runner's own directory. A failure stops `factory-ci@*`, which stays stopped until someone starts it again. Setup's last step is the check's first run, so a misconfigured tier never takes a job.
4. **`bundles/factory/tree/tests/test_docker_guard.py`, `test_ci_job_hook.py`** (new): the runner's own argv (job container, exec, `--config` pull and login, networks) passes; every hostile variant is refused; the guard's environment and host are checked. The hooks' modes are tested on a temp tree, and bad paths and a missing pid file are refused.
5. **`process/factory.md`**: "The CI tier" gains the threat model (merge gate against execution gate), the guard, hooks and check, the docker:// and Dockerfile-action ban, no host paths, and ephemeral runners as CD's call. They need a credential on the host that can register runners, and the factory App lacks that permission. `dotnet-node`'s CODEOWNERS list gains the project files' `.user` files and a root `dotnet-tools.json` (with the seeded test and the proof's CODEOWNERS).

**Rationale:** The factory's own pool keeps hostile workflows out by its workflow restriction. The CI tier can't, so it enforces at the one place every job definition passes through, the runner's docker commands. It also leaves nothing on disk for the next job.

---

## 2026-10-13: A factory CI tier: isolated self-hosted runners for a project's own CI jobs

**Origin:** The pilot project. CD's decision for its pull-request end-to-end jobs (Playwright, against the real server and Postgres) was a dedicated, isolated CI runner tier on the runner host, built the factory's way, with no paid larger runners, and with pre-merge end-to-end tests kept for factory PRs. They had moved off 2-vCPU GitHub-hosted runners because two browsers starved the CPU, and ran on an unisolated self-hosted runner, which the workflow policy refuses.

**What happened:** CD asked for the tier's runner group to be restricted to the project's CI workflow. GitHub's runner groups pin each selected workflow to a branch, with no wildcard ([docs](https://docs.github.com/en/enterprise-cloud@latest/actions/hosting-your-own-runners/managing-self-hosted-runners/managing-access-to-self-hosted-runners-using-groups)). A `pull_request` run comes from the PR's merge ref, so a `ci.yml@refs/heads/main` entry never matches it and its jobs would wait forever. That restriction can't coexist with pre-merge tests, so the CI group is restricted to the repositories that use it. The isolation lives in the runners (their own user, firewall and caps, a job container required) and in the policy's hold on the label. `factory-pool` keeps its workflow restriction: agent workflows run from events on the default branch. This, and the Chromium point in item 4, are decisions for CD to confirm.

**Changes made:**

1. **`bundles/factory/tree/host/setup.sh`**: `TIER=ci`. User `factory-ci`, nft table `factory_ci`, firewall unit and file, runner unit `factory-ci@N`, names `<prefix>-ci-N`, all suffixed for a second organization. Label `runners.ci`; group `runners.groups.ci` (default `factory-ci`), computed per tier now. Caps from host.conf's `CI_RUNNERS` (2), `CI_MEMORY_HIGH` (12G), `CI_MEMORY_MAX` (16G) and `CI_CPU_QUOTA` (800%), for the tier's runners together. Otherwise the strict tier's setup: firewall (internet, no host or LAN), rootless Docker, isolation self-check from inside a container, job container required. A `factory.json` without `runners.ci` is refused with the reason.
2. **`bundles/factory/tree/bootstrap.py`**: once a workflow runs on `runners.ci`, the CI group, created with the repository and without a workflow restriction. An existing CI group restricted to workflows is reported with why it would strand pull requests, and left to CD.
3. **`bundles/factory/tree/workflow_policy.py`**: CI-tier rules for any job on the label. It must be in one of the project's own workflows (never a factory one), run no agent, and run in a container (the existing rule: no service containers). It needs explicit read-only permissions and checkouts with `persist-credentials: false`. It holds no secret and no job token, except the job token as the container's pull credentials. `systempaths=unconfined` comes only with the factory seccomp profile. The label counts as a factory label, so it is never a hosted label or exemptible.
4. **`process/factory.md`**: Enablement step 8 runs `TIER=ci`. Step 10's "The CI tier" covers the setup order (bootstrap creates the group before setup registers into it), why the group isn't workflow-restricted, the job rules, the seccomp profile as allowed but not required, and capacity. Docker's default seccomp is stricter, and enough for a browser run without its own sandbox, which is Playwright's default. Chromium's sandbox under `seccomp-bwrap.json` wasn't tested.
5. **`render.py`** treats `runners.ci` and `runners.groups` as run-time settings. **Seeds:** `factory.json` gains `runners.ci: factory-ci`, and `host/host.conf` the `CI_*` settings. **Tests:** `test_host_setup.py` (the tier's names, caps, group, second organization, an old `factory.json`), `test_bootstrap.py` (the group made only once a workflow uses the label, without a workflow restriction; a restricted one left to CD), `test_render.py` (a compliant CI-tier job, each rule broken, a factory workflow on the label).

**Rationale:** End-to-end suites need more machine than GitHub's standard runners, and pre-merge they run a pull request's code, agent-written for factory PRs. The factory already knows how to run untrusted code on its own hardware: a firewalled user, rootless Docker, a container per job, and nothing in the job worth taking. The CI tier is that, for the project's CI, without the agent machinery.

---

## 2026-10-13: The factory's workflow policy scans local actions, and names its exceptions in factory.json

**Origin:** The pilot project (CD: "fix the checker upstream"). The policy, which Enablement step 10 makes required CI over every workflow in a repository, refused 6 jobs in the project's own `ci.yml`. Two refusals were for a local composite action the policy refused rather than read. Four were for the end-to-end jobs on a self-hosted runner outside a container. CD's runner choice for those jobs (GitHub-hosted, possibly larger runners, or an isolated self-hosted runner) is still open, so the checker had to support either without loosening anything.

**What happened:** A blanket rescoping (checking only the factory's own workflows) would have stopped the policy from catching a newly added self-hosted PR job, so each exception is named instead. The new settings live in a `policy` block in `factory.json`, which CODEOWNERS covers through `/.github/` and only `workflow_policy.py` reads.

**Changes made:**

1. **`bundles/factory/tree/workflow_policy.py`**:
   - **Local actions** (`uses: ./…`) resolve in the repository and are scanned. A composite action's steps join the calling job's, nested ones too, so every step rule reads them: docker, direct Claude Code, the agent jobs' checks, and the OAuth, App-key and fixture-secret confinement. Refused: a docker or JavaScript action, a path with no `action.yml` or outside the repository, a ref, an action that uses itself, nesting deeper than 8, and an agent step inside one. An agent job still runs no local action at all, as before.
   - **`policy.hosted_labels`**: the organization's own GitHub-hosted runner labels count as hosted, wherever the policy asks (the container rule, the App key's job, the fixtures job). Refused, regardless of case: a label GitHub gives every self-hosted runner (`self-hosted`, `linux`, `windows`, `macos`, `x64`, `arm`, `arm64`), a factory runner label, and anything that isn't a label.
   - **`policy.self_hosted_exemptions`**: exact `{workflow, job, reason}` entries. They lift only the container rule, and only for one of the project's own jobs. Never a factory workflow, a job on the factory's runners or an agent job, and never with a reason under 20 characters. An entry that names no job, or a job that runs hosted, is a violation, so the list stays exactly what it lets through. Each use prints a CI notice.
2. **`bundles/factory/tree/render.py`**: the `policy` block, like `stack`, is read at run time, not by a template.
3. **`bundles/factory/seed/factory.json`**: the empty `policy` block, with its `_doc`.
4. **`bundles/factory/tree/tests/test_render.py`**: `ProjectWorkflows`, run in a repository laid out as GitHub's: nested composite actions scanned, each unscannable kind refused, a local action in an agent job refused, the factory's secrets refused inside a local action, the organization's labels, an exemption lifting one named job and not a new one, an exemption never reaching the secret rules, and each exemption that can't hold.
5. **`process/factory.md`**: Enablement step 10 says the policy scans local actions, and when a project's own CI needs `policy.hosted_labels` or an exemption.

**Rationale:** The policy reads every workflow so that a job someone adds later falls under the factory's rules by default. Exceptions now live in a reviewed file with reasons, and the checker refuses any that stop being true. The secret rules have no exceptions at all.

---

## 2026-10-13: Factory Enablement: what CODEOWNERS must cover per profile, and the project's own CI

**Origin:** The pilot project's Enablement review. That project's session found that none of the files .NET and pnpm load just because they exist were code-owned, and that its existing CI would run factory PRs' code next to a secret.

**What happened:** Two of the factory's protections rest on CODEOWNERS covering every file a stack's tools load by existing. A revise or continued run installs a factory branch's dependencies outside the sandbox (`install.sh`: `dotnet restore`, `pnpm install`). The only guard there is `factory_branch.sh check` refusing any change to a CODEOWNERS path. The same files decide what the project's CI does with a factory PR. Enablement step 9 said "the test and build configuration" and nothing more specific. For .NET that set is wide: a project file can hook a target into restore, and any `.props`/`.targets` it imports can too. And factory branches live in the repository, so `pull_request` CI on a factory PR gets the repository's secrets. In the pilot project, the build step (PR code) ran before the step holding `SLEEVED_API_KEY`, and the end-to-end jobs ran on a self-hosted runner outside any container. Running the workflow policy on that repository found 6 violations in its own `ci.yml`, which Enablement step 10's required check would have hit on the first PR.

**Changes made:**

1. **`process/factory.md`** § Stack Profiles: "What CODEOWNERS must cover, per profile", the files each profile's tools load just because they exist, at any depth and in every casing a tool accepts. python-node: requirements, pyproject, setup, pytest and tox config, conftest, sitecustomize. dotnet-node: `*.csproj`, `*.props`, `*.targets`, `*.rsp`, the solution files, `global.json`, `nuget.config` in its three casings, the tool manifest, runsettings, `xunit.runner.json`, `.editorconfig`, `.globalconfig`. Node in both: `package.json`, `.npmrc`, and each package manager's own lockfile and files. Enablement step 9 points at it. Step 10 says to run the policy (which reads every workflow) before making it required, and warns that the project's existing CI runs agent-written code. Every job that builds, tests or lints a PR's code therefore holds no secret before or after it, uses `persist-credentials: false` and a read-only token, and runs on a hosted runner or in a container. A job that needs a secret runs the default branch's code.
2. **`bundles/factory/seed/tests/test_codeowners.py`**: `test_the_profiles_build_files` checks sample paths from the profile's list in the project's two directories (`factory.json`'s stack). New projects get it; existing projects keep their own copy.
3. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`**: the proof's Enablement-shaped CODEOWNERS covers both profiles' lists (and names Enablement step 9, not 7).

**Rationale:** "The test and build configuration" left each project to rediscover which files a toolchain executes by convention. The factory's own install step and the project's CI both depend on that list, so the profile that brings the toolchain now names it, and the seeded test holds a new project to it.

---

## 2026-10-13: Factory fixtures: a hosted job hands secret-sourced test fixtures to the agent job

**Origin:** The pilot project. Four of the pilot project's tests need card-art fixtures that CI fetches with a secret (`SLEEVED_API_KEY`), and the implement sandbox has neither the network nor the secret, so the `dotnet-node` profile left them out (`Category=External`). CD asked whether the factory could fetch the art itself ("can we wire this in as a service?"), chose option 3 of five (CD, 2026-10-13: a hosted fixtures job that hands an artifact to the agent job), and approved D2 rule 7 for it.

**What happened:** A service (`services.json`) was the wrong tool. It would have put a masked credential and two egress hosts into the code-writing stages, against the planning-only services rule (CD 2026-10-10) and D2 rule 2's empty network for implement. The chosen shape keeps the secret off the self-hosted host entirely. It is CI's own three steps (restore the cache, fetch on a miss, upload) in a job on a GitHub-hosted runner, and the agent job only downloads the result. Two GitHub Actions details shaped the templates. A job whose upstream job is skipped may be skipped too unless its condition says otherwise, so `publish` now states its own condition, as `report` already did. And an expression like `secrets.` with an empty name breaks the whole workflow, so the secret is read as `secrets['NAME']`, which stays valid when a project has no fixtures.

**Changes made:**

1. **`bundles/factory/tree/templates/factory-implement.yml`, `factory-revise.yml`**: a `fixtures` job, skipped when `fixtures.path` is empty. It checks out the default branch, restores `path` with `actions/cache` (v6.1.0) under `cache_key-<hashFiles(key_files)>`, and on a miss installs `apt` and runs `run` with the secret exported under its own name. Then it refuses fixtures that contain the secret (plain or base64) and uploads them as `factory-fixtures`. The agent job `needs` it, runs unless it failed, and downloads the artifact into `path` before the agent starts. `publish` states its condition explicitly. `report-failure` names a failed fixtures job.
2. **`bundles/factory/tree/render.py`**: `%{key?}` is an optional setting, which renders empty when `factory.json` doesn't have it. A project installed before the `fixtures` block keeps rendering without editing its settings.
3. **`bundles/factory/tree/workflow_policy.py`**: the fixtures job kind (a factory workflow's job named `fixtures`; a project's own `ci.yml` may use the name). It must be in the implement or revise workflow, on a GitHub-hosted runner, with no agent, container, environment or outputs. Its permissions are exactly `contents: read`, it checks out the default branch once without persisted credentials, and it uses only the checkout, cache and upload-artifact actions. Its one secret appears only as `${{ secrets['NAME'] }}` in a run step's `FIXTURE_SECRET`. No other job, and no workflow env, may reference that secret. `factory.json`'s fixtures values are checked for anything that would change the workflow text they render into: an expression, a quote, `..`, or a path without its command and cache key.
4. **`bundles/factory/seed/factory.json`**: the `fixtures` block, empty (path, run, secret, apt, cache_key, key_files), with its `_doc`.
5. **`bundles/factory/tree/tests/test_render.py`**: optional placeholders; a project without the block renders skipped fixtures jobs; a project with one renders them, names the secret only in the fixtures job, and passes the policy. The policy refuses the secret in an agent job, a factory-branch checkout, a self-hosted runner, outputs, another action, another secret, and settings that would change the workflow.
6. **`process/factory.md`**: D2 rule 7 (CD's sentence, with how the job does it). Enablement step 2 points at the `fixtures` block, and step 7 lists its secret as a read-only repository secret.

**Rationale:** The factory's boundary is that an agent job holds no credential beyond its own read-only token. Test fixtures that need a secret were the first thing that boundary kept out of a factory run, and the answer keeps the boundary: the privileged fetch happens in a trusted job, and only its non-secret result crosses over, as D1 already does for writes.

---

## 2026-10-13: A second factory stack profile, dotnet-node (.NET 10 and pnpm/Vite)

**Origin:** The pilot project (its session, at CD's request), which is .NET 10 with a pnpm/Vite web client, is installing the `factory` bundle, and its only profile was `python-node`. Under the pilot rule (CD, 2026-10-12) the fix goes straight into the bundle code.

**What happened:** A profile was written from `python-node` and proven against a clean archive of the pilot project in a local stand-in for the implement sandbox (the job image with no network, a read-only root, no HOME and a seccomp filter refusing `socket(AF_UNIX)`). That run found what the sandbox does to .NET. MSBuild's worker nodes talk over Unix sockets, so a solution's build fails in under a second with "Build FAILED, 0 errors" and leaves orphaned workers. No environment variable, SDK `MSBuild.rsp` or root `Directory.Build.rsp` overrides the `-maxcpucount` the dotnet CLI passes; only an explicit `-m:1` works, and `dotnet run` and `dotnet ef` ignore it. With `-m:1`, 5,565 of the pilot project's 5,573 tests pass there (4 are skipped, and the 4 that fail are card-art cases that need a secret), and tsc, vitest, the Vite build and both of its bundle gates pass too. `eslint .` fails on `scripts/*.mjs` and `perf/*.mjs` alone, which the pilot project's own lint never covers. With no HOME, `dotnet restore` writes NuGet's data into the working directory (`.local/share/NuGet/`), an untracked file that would stop the run's publish; `XDG_DATA_HOME` moves it. A second run started from a git repository and applied the asks to the pilot project (the card-art cases tagged `External`, eslint without `scripts/` and `perf/`, `.factory/` ignored). In it install, `verify probe` and `verify` all pass, `git status` stays empty, and no process outlives a command. It also showed a gap that predates the profile. Every job writes `.factory/` into the workspace, and the publish step refuses untracked files. The incubator gitignores `.factory/`, but Enablement never said to.

**Changes made:**

1. **`bundles/factory/tree/profiles/dotnet-node/`** (new): `Dockerfile` (python:3.12-slim-bookworm, because the plan and smoke templates call `/usr/local/bin/python3` by path; the .NET 10 SDK copied from `mcr.microsoft.com/dotnet/sdk:10.0` with `libicu72`; Node 22; pnpm 10.33.0 as a package, not corepack; Postgres 16 and pgbouncer). `install.sh` (`dotnet restore`, `dotnet tool restore` when there is a tool manifest, `pnpm install --frozen-lockfile`; .NET's home, the NuGet packages, the data directory (`XDG_DATA_HOME`) and the pnpm store go in `.factory/`; it sets no-node-reuse, no shared compilation, no telemetry or first-run certificate, and NuGet audit off in the sandbox). `test-services.sh` (Postgres only, the same lockdown checks, and a `ConnectionStrings__DefaultConnection` line). `with-test-services` (ports 5432 and 6432). `verify` (areas `dotnet` and `node`, plus `probe`; `-m:1` on every build; tests in the categories `Nightly` and `External` left out; `--print` tells the agent the `-m:1` rule).
2. **`bundles/factory/tree/tests/test_agent_job.py`**: `VerifyDotnetNode` covers the new profile's commands, areas and failures. The `Freeze` test reads the project's profile from `factory.json` instead of naming `python-node`; before this, it failed in any project on another profile, and these tests are required CI (Enablement step 10). All 269 tests pass in a project on `dotnet-node`.
3. **`process/factory.md`**: "Limits of this version" names both profiles. § Stack Profiles gains a table of the two profiles and what each needs of a project, says why `verify` leaves a build script's own gates to CI, and covers the sandbox's `-m:1` rule and end-to-end suites. The `stack.python`/`stack.node` slots stay, renamed only when a stack doesn't fit two directories, because renaming them changes every project's `factory.json`. Enablement step 2 requires `.gitignore` to cover the env file and `.factory/`, and says to render after choosing the profile: `factory-image` builds the chosen profile's `Dockerfile`, so the pilot project's render check failed until it re-rendered.

**Rationale:** The second stack is where the factory learns what "one kind of project" really varies in. The sandbox's Unix-socket block is invisible to Python and npm but breaks MSBuild silently, and only a run that imitates the sandbox finds it before a paid agent run does. Proof on a real runner is still `factory-smoke`, in the pilot project's Enablement.

---

## 2026-10-13: The factory import's patterns name no host

**Origin:** the import tool's rules, public in z-sdlc, listed the incubator's runner host by name as a pattern to flag; CD asked for it to go.

**Changes made:**

1. **`.claude/skills/zsdlc-import-factory/import.json`** — the host name is out of `specific`; private and VPN address ranges and home directories still catch host-specific text an import would add.

**Rationale:** a public file shouldn't name a private machine, even as a pattern. Release type: patch.

---

## 2026-10-12: One factory runner host serves several organizations

**Origin:** a second organization's factory will share an existing runner host rather than need its own machine (CD: "change setup.sh").

**What happened:** `host/setup.sh` used fixed names for its users, firewall tables and services, so a host ran one organization's runners; setting it up for a second would have reused the first's users and runner directories. Imported from quantile 6251b8c..07d9441.

**Changes made:**

1. **`bundles/factory/tree/host/setup.sh`** — `RUNNER_INSTANCE` (in `host.conf`) names a second organization's runners: users `factory-runner-<instance>` and `factory-planner-<instance>`, their own nft tables, firewall units and runner services, each isolated from the others as from the host. Without it the names are as before. Setup refuses, before changing anything, a runner directory registered to another organization; new runner users get subordinate IDs above every range already given out, not a fixed block that could collide on a fresh host; replacing the shared seccomp profile says so.
2. **`bundles/factory/seed/host/host.conf`** — documents `RUNNER_INSTANCE` and that each organization's limits come out of the same host.
3. **`bundles/factory/tree/tests/test_host_setup.py`** — the instance names, refused names, and the ownership guard.
4. **`process/factory.md`** — Enablement step 8: a host can serve several organizations; a planning database port is only ever the organization's own.
5. **`.claude/skills/zsdlc-import-factory/scripts/import_factory.py`** — a copy of `process/factory.md` or a skill that the incubator committed from z-sdlc (`--to-incubator`) is recognized by z-sdlc's history, not reported as an edit made in the incubator; with a test.

**Rationale:** runner hosts are the costly part of the factory; letting organizations share one, each confined as strictly as from the host itself, removes the need for a machine per organization. Release type: minor (a new host setting).

---

## 2026-10-12: factory.md's Enablement starts from zero, and says what a stack profile is

**Origin:** with the bundle carrying everything an organization needs (the entry below), its Enablement still assumed Endless Galaxy's App, image, echo service and runners already existed (CD: the factory is an abstraction for anyone). Checking GitHub's documentation for the plan the factory needs corrected an earlier answer: a free organization isn't enough.

**Changes made:**

1. **`process/factory.md`** — Enablement starts from an organization (the runners are an organization runner group's), on GitHub Team or above for a private repository (environment secrets, `main`-only environments and rulesets), and says the production tier's required reviewer on a private repository needs Enterprise. New steps for the job image, the echo service, the App (`create_app.py`) and the runner host (`host/setup.sh`, `host.conf`); `bootstrap.py --apply` becomes its own step, after the placeholders are filled. The planning tier's database is optional. A new Stack Profiles section says what a profile's five files do, and that the interface keeps `python-node`'s shape until the first other profile generalizes it. The install table and limits match the bundle.
2. **`bundles/factory/`** — imported from quantile c6520ae..6251b8c: `create_app.py` and the tests cite the new step numbers; `create_app.py` writes the App's private key to the home directory by default, outside any checkout; `bootstrap.py` compares with the seed's exact placeholders, so an organization named like one isn't locked out. The seeded `planning.json` says its database is optional, and the seeded `tests/test_codeowners.py` cites step 9.

**Rationale:** Enablement is the one path a new organization follows, so it has to cover everything that path needs, in an order where each step has what it uses. Release type: patch.

---

## 2026-10-12: The factory bundle sets up from zero: host setup, the App, the echo service, placeholders

**Origin:** the factory is meant to be usable by anyone who installs z-sdlc, not only by CD's organization (CD). The bundle assumed Endless Galaxy's App, job image, echo service and runner host, and the host setup wasn't in it at all.

**What happened:** imported from endless-galaxy-studios/quantile ec4b0d9..c6520ae. Quantile's commits made each piece of the factory read the project's own settings, and the import proof (an empty project with the seed's placeholders) found that the host setup stopped outside a checkout with an `origin`; fixed in quantile and imported.

**Changes made:**

1. **`bundles/factory/seed/factory.json`** — `app`, `image` and `smoke.echo_host` are placeholders (`your-factory-app[bot]`, `ghcr.io/your-org/factory-job`, an all-zero digest, `echo.example.invalid`) instead of Endless Galaxy's values; the runner labels and environment names stay as shared defaults.
2. **`bundles/factory/tree/bootstrap.py`** — checks first that `factory.json` names the project's own App, image and echo service, and applies nothing until it does, naming the Enablement step that fills each.
3. **`bundles/factory/tree/create_app.py`** (new) — creates the factory's GitHub App in an organization through GitHub's manifest flow, with exactly the four permissions `bootstrap.py` checks and no webhook; writes its bot user into `factory.json` and its private key to a new mode-600 file.
4. **`bundles/factory/tree/echo/`** (new) — the echo service smoke calls: `worker.js` for Cloudflare Workers, `server.py` for any container host behind HTTPS.
5. **`bundles/factory/tree/host/setup.sh`**, **`seccomp-bwrap.json`** and **`bundles/factory/seed/host/host.conf`** (new to the bundle) — the runner host setup: runner labels and group from `factory.json`, the host's own settings (organization, home directory, LAN resolver, probe ports, a planning database port, runner counts and limits) from `host.conf`, each with a default; `--print-settings` resolves them without root. The production tier's host scripts stay per project.
6. **`bundles/factory/tree/planning-services.sh`**, **`templates/factory-plan.yml`**, **`templates/factory-revise-doc.yml`** — the planning database is optional (D3): with none in `planning.json`, the plan and revise-doc stages run without one.
7. **`bundles/factory/tree/templates/factory-smoke.yml`**, **`implement_tools_check.py`** — smoke's write probe uses directories it creates, not one project's layout.
8. **`bundles/factory/tree/tests/`** — the tests read the project's own `factory.json` instead of Endless Galaxy's App and values, so every adopter's CI runs them unchanged; new tests for the App creation, the echo server, the host settings and the optional planning database.
9. **`.claude/skills/zsdlc-import-factory/`** — `host/` is bundle code except the production tier's two scripts, and `host/host.conf` is a seed. A file z-sdlc's history never had (excluded at the last import, bundle code under today's rules) is reported as added, not as z-sdlc's removal; with a test. The home-directory pattern no longer matches `api.github.com/users/`.

**Rationale:** an adopter now fills four placeholders with its own App, image and echo service, each made by a script or file in the bundle, and sets up its runner host from the same checkout; nothing in the bundle presumes Endless Galaxy. Release type: minor (new command surface: `create_app.py`, the host setup).

---

## 2026-10-12: Public and generic: project-internal material leaves z-sdlc

**Origin:** z-sdlc is public and for anyone, and the factory is meant to be an abstraction every adopter can use (CD). A review of what z-sdlc publishes found no credentials, but it did find CD's own projects' internals: a runner host's network addresses in the factory's smoke template, the factory's design record (one project's hosts, operations, costs and history), another project's product material, and private projects named as examples in files every project installs.

**Changes made:**

1. **`process/factory.md`** — each of D1-D5 gains a Why section (the context and the options considered), written for any adopter. The factory's design record and rollout plan, which held one project's operations, leave `docs/current_work/ideas/` for CD's private documentation.
2. **`bundles/factory/`** — smoke's isolation probe takes the runner host's own addresses from `factory.json`'s new `smoke.host_probes` (empty in the seed) and always adds the default Docker bridge and rootless gateways; the template no longer carries one host's addresses. Comments and test fixtures that named a host or project are generic, and code cites `process/factory.md` instead of the design record.
3. **Installed files** — `knowledge/architecture/model-tier-strategy.yaml`'s survey, two design knowledge files' sources, the examples in `process/production-gates.md` and `process/deliverable_lifecycle.md`, `skills/sdlc-migrate`, `skills/sdlc-audit/references/session-reading.md`, and `templates/pr_description_template.md` (its worked example is now an orders API) no longer name private projects or people.
4. **`docs/current_work/ideas/`** — the two pending handoffs (an ADR supersession gate, and option previews for `sdlc-explain`) keep their proposals without the source projects' details; the 155 KB reference page from another project is removed. `changelog-archiving_design.md` cites its numbers without naming projects.
5. **Framework-development tooling** — the adapter-installation audit says "the target" for the project it audits; the import tool flags private and VPN address ranges and home directories instead of names.
6. **`skeleton/contract_changes.yaml`** — 0019 and 0020's `changelog_ref` match the factory debut's heading; descriptions don't name projects.

**Rationale:** what a public framework ships, and what its examples teach, should hold for any project; CD's own projects belong in CD's private records. Release type: patch.

---

## 2026-10-12: zsdlc-import-factory: importing the factory from quantile is a command

**Origin:** CD decided (2026-10-12) that quantile incubates the software factory and z-sdlc imports it, and asked for the import tool proposed then.

**What happened:** the session that built the `factory` bundle imported it from quantile by hand five times. Each time, new files had to be remembered and new seed settings added by hand. Quantile's copy of `process/factory.md` fell a clause behind z-sdlc's, and the guard tests carried quantile's own CODEOWNERS into the bundle. The proof that an import installs and works lived in a throwaway script.

**Changes made:**

1. **`.claude/skills/zsdlc-import-factory/`** (new, source-only) — `SKILL.md` (report, apply, prove, record), `import.json` (which of quantile's `.github/factory/` files are seeds, which are excluded, settings whose keys are project data, patterns of quantile-specific text, the last imported commit), and `scripts/import_factory.py`. The script reads quantile at a commit, never its working tree. It reports bundle code added, changed and removed; JSON seed settings the bundle's seeds lack; text seeds quantile changed; quantile-specific text an import would add; and whether quantile's copies of the bundle's skills and process doc still match. `--apply` writes the bundle code and records the commit. Since later reports compare against that commit, it refuses while a [fix first] item is open (a missing seed setting, a quantile edit to z-sdlc's text). An added or removed file, quantile-specific text or a changed text seed needs `--accept`. `--prove` installs into a clone of quantile and into an empty project, then renders every template, checks the policy and runs the tests. `sdlc-reviewer` found that applying could hide open items. That's fixed in the script, and its other findings are fixed in the skill.
2. **`tests/test_import_factory.py`** (new) — 19 tests against fixture repositories, including a z-sdlc fix kept and handed to quantile, a file z-sdlc added, a conflict merged in quantile, and a file quantile deleted.
3. **`CLAUDE.md`** — the `factory` bundle is imported from quantile. Edited here instead: the skills, `process/factory.md`, the seeds, and a fix found in a project that installed the bundle, which goes straight into the bundle code (CD, 2026-10-12, for the ChronoCore pilot).

Because of that last rule, the script compares each bundle code file three ways: quantile now, the bundle now, and quantile at the last import. Quantile's changes are imported. z-sdlc's own changes are kept, listed as `ahead`, and `--to-incubator` writes them (and newer skills and process docs) into quantile's working tree to commit there. A file changed on both sides is a conflict: merge in quantile, then `--apply --accept`. The proof installs the bundle with z-sdlc's own changes kept.

**Proof:** against quantile `3b1ba7d` the report finds the bundle in sync and the proof passes (17 workflows, policy, every test). `import.json` records `3b1ba7d` as the last import.

**Rationale:** the pilot will bring changes from two directions; every import now sorts, checks and proves the same way. Release type: patch (framework-development tooling; nothing installs into projects).

---

## 2026-10-12: Debut the factory bundle: the software factory, promoted from quantile

**Origin:** the factory's rollout (`docs/current_work/ideas/software-factory_rollout-design.md`). The software factory incubated in quantile (F13): issue-driven agent stages from triage to a draft PR, on self-hosted runners, with CD approving every plan, merge and production step. Steps 1-3 made it installable: shared scripts, workflows rendered from a per-repository `factory.json`, and the `python-node` stack profile. Step 4 moves it into z-sdlc as an opt-in bundle, with its design rules promoted to a process doc (F22); step 5 adds the GitHub setup. CD decided (2026-10-12) that quantile keeps incubating it and z-sdlc imports it, and that a fix found in a project that installed the bundle goes straight into z-sdlc.

**What happened:** before the release, the bundle met quantile's live runs. D17, the first live rollback gate, found that the deploy check refused the factory's own job image under `.github/`. Moving the guard tests upstream found that a project without a production tier could publish no plan. Renaming the org's runner groups showed that a runner-group API update can empty a group's repository list. Smoke's stand-in service, httpbin.org, failed it for an afternoon. Each is fixed here.

**Changes made:**

1. **`bundles/factory/tree/`** — the factory's code as quantile has it (83 files): the scripts, guards, schemas, tool policies, sandbox settings, workflow templates, `render.py`, `workflow_policy.py`, the `python-node` profile, `bootstrap.py` and the tests. Installed at `.github/factory/` and refreshed on every migration. The guard tests use a sample CODEOWNERS and operations catalog, so they ship upstream; the publish guards treat a missing catalog as no production tier. `bootstrap.py` checks a repository's GitHub setup against Enablement and, with `--apply`, creates the labels, environments and runner-group entries (secrets, the App, CODEOWNERS and the ruleset stay report-only). Smoke's injection probes call `factory.json`'s `smoke.echo_host` instead of httpbin.org.
2. **`bundles/factory/seed/`** — what becomes the project's, written once where absent: `factory.json` (Endless Galaxy's shared defaults, including `smoke.echo_host`; the `stack` block is set per project), `planning.json`, `services.json`, `triage-policy.md`, a short `README.md`, and `tests/test_codeowners.py` (the project's CODEOWNERS against the guard). Not in the bundle: quantile's production tier (the broker, its operations and their tests), its host setup and its Django-specific database access list.
3. **`skills/sdlc-triage`, `skills/sdlc-implement`, `skills/sdlc-revise`** — the stage skills, made generic. Project specifics moved to the project's `.github/factory/triage-policy.md`; the App's login comes from `factory.json`, and commands and test services from the stack profile. An `sdlc-reviewer` pass found 7 major and 15 minor findings; two minors are left as follow-ups (the thread-reading rules repeated across the three skills, and where the sandbox paragraphs sit).
4. **`process/factory.md`** — D1-D5's rules, forbids, costs and revisit-when, the label set and Enablement. D4 rule 13: no infrastructure pattern applies under `.github/`, whatever a file there is called. D4 rule 16: without a production tier a plan has no gates, CD's included. Enablement names the shared runner group `factory-pool` and the per-project `factory-pool-<project>-prod`, gives the runner-group API's rule, and points steps 2 to 8 at `bootstrap.py`.
5. **`skeleton/manifest.json`** — `bundles.factory`; bundles may now carry `tree`, `seed`, `render` and `requires` (`skeleton/contract_changes.yaml` 0019; the debut is 0020). `sdlc-initialize` and `sdlc-migrate` install trees and absent seeds, run the render, hash tree files (never seeds) and offer an adopt path to a project that already has the tree. `process/path-mappings.md`, `process/commands.md`, `review-fix-loop.md`'s mirror table and `headless-mode.md`'s gate sites cover them.

**Proof:** installed into quantile, the bundle changes nothing and the workflow policy passes. Installed into an empty project with an Enablement-shaped CODEOWNERS, all 17 workflows render, the policy passes and every test passes (`zsdlc-import-factory --prove`). Quantile's live runs exercised the rest: smoke (all eight jobs, on the new echo host), a rollback gate that ended `rolled-back` as designed, and the generic triage and implement skills on a throwaway issue.

**Adapter action:** none; the bundle's files are code and settings, not knowledge-layer references (treat `bundles/factory/` like scripts).

**Rationale:** the factory is meant for every project (F22). Steps 1-3 left its project-specific values in a settings file and a stack profile, so the rest ships as one upstream copy. Release type: minor on its own (an opt-in bundle debut and additive manifest fields).

---

## 2026-10-12: Adapter fields and the improve route take the z-sdlc name [contract-change]

**Origin:** the rename to z-sdlc (entry below) left three names that other repositories store: two adapter fields and the improve loop's route value.

**What changed:**
- `process/adapter-lifecycle-protocol.md`, `process/knowledge-routing.md`, `sdlc-initialize`, `sdlc-migrate`: adapters mark themselves with `zsdlc_adapter` and declare `supported_zsdlc_version`. The pre-rename keys `ccsdlc_adapter` and `supported_ccsdlc_version` stay readable, and a migration that refreshes a project's adapter entry writes the new key and drops the old one.
- `sdlc-audit` improvement mode: the framework route and section are `z-sdlc`; factories and reports from before the rename call them `cc-sdlc`, and the two are the same route.
- `skeleton/contract_changes.yaml` 0018 records it.

**Adapter action:** declare `zsdlc_adapter` and `supported_zsdlc_version` (neuroloom-sdlc-plugin does as of this change). A factory that stores the route (quantile's improve loop) accepts both values in its schema and ledger.

**Rationale:** Every reader accepts both names, so an adapter or ledger written before the rename keeps working, and nothing has to change in lockstep. Release type: major, with contract 0017 in the same release.

---

## 2026-10-12: The framework is called z-sdlc everywhere

**Origin:** CD (2026-10-12): every cc-sdlc reference becomes z-sdlc. The `sdlc-*` skill and file names and "SDLC" stay.

**What changed:**
- Every skill, agent, process doc, template, knowledge file, bootstrap file and design doc names the framework z-sdlc (Z-SDLC in titles).
- The temporary clone paths are `/tmp/z-sdlc-bootstrap`, `/tmp/z-sdlc-lite-bootstrap` and `/tmp/z-sdlc-migrate`, and the source placeholder is `[z-sdlc-path]`. `sdlc-initialize` also accepts `/tmp/cc-sdlc-bootstrap` from a BOOTSTRAP.md copied before the rename, and looks for a local copy under both names.
- The framework-development skills are `zsdlc-audit`, `zsdlc-audit-adapter-installation`, `zsdlc-create-skill`, `zsdlc-ingest` and `zsdlc-research`.
- Unchanged on purpose: this changelog's past entries and the changelog archive (`archive --upstream` matches a project's copied entries by their dated headings, so those must stay as written), past `contract_changes.yaml` entries (append-only), and the old repository URL in `sdlc-migrate`'s `source_repo` rewrite. The adapter fields and the improve loop's route value are renamed in the next entry, with compatibility.

**Rationale:** One name for the framework in everything it installs. Projects get the new text at their next migration (direct copies). Release type: patch.

---

## 2026-10-12: The framework moved to endless-galaxy-studios/z-sdlc

**Origin:** CD moved the repository from `Inpacchi/cc-sdlc` into the Endless Galaxy Studios organization and renamed it `z-sdlc` for branding. The `sdlc-*` names inside stay.

**What changed:**
- `BOOTSTRAP.md`, `BOOTSTRAP-LITE.md`, `README.md` and the `.sdlc-manifest.json` template point at `https://github.com/endless-galaxy-studios/z-sdlc`, for cloning and for the raw bootstrap file.
- `skills/sdlc-initialize`: clones from the new URL, and looks for a local copy under the new name first (`~/Projects/z-sdlc`, `~/z-sdlc`, `../z-sdlc`), then the old one.
- `skills/sdlc-migrate` § 4.5 step 1a: a project whose `source_repo` names `github.com/Inpacchi/cc-sdlc` (HTTPS or SSH) gets it rewritten to the same form at the new home. Any other value, such as a fork or a local path, is left alone.

**Rationale:** GitHub redirects the old URL, but only until something takes the old name, and every install's manifest still names it. Migration fixes each project's record, so no project has to be edited by hand. A migration runs the project's installed `sdlc-migrate`, so the rewrite happens at the first migration after one installs this version; the redirect covers the time between. Release type: patch.

---

## 2026-10-11: Changelog archiving: project-only changelogs, quarterly archive files

**Origin:** CD decided the process changelog gets archived (2026-10-11) and chose all four parts of `docs/current_work/ideas/changelog-archiving_design.md`. [contract-change] (adapter exemption list; contract 0017)

**What happened:** cc-sdlc's changelog was 644 KB and nothing archived it. Every project's changelog started as a copy of it, so projects carried the framework's whole history plus their own (quantile 735 KB). CD chose: project changelogs hold only their own entries from now on; old entries move by calendar quarter once the file passes about 150 KB; a script does it; and existing installs are archived by their next migration without asking, which makes the release major. Then, seeing that quantile would keep 96 KB of copied cc-sdlc entries from July on: existing installs move every copied cc-sdlc entry out, whatever its quarter.

**Changes made:**

1. **`skills/sdlc-archive/scripts/changelog_archive.py`** (new; the first script shipped in a skill) — `archive` moves every entry dated before the previous quarter to `changelog-archive/YYYY-Qn.md` when the file is over the threshold, byte for byte and in its order, adds one pointer line, and writes nothing unless every entry is present exactly once across the files before and after. `check` fails when there's something to move and names the command. With `--upstream` (cc-sdlc's changelog and archive files), entries copied from cc-sdlc move too, whatever their date and the file's size; a copy is an entry whose `## YYYY-MM-DD: Title` line matches one upstream. `init` writes a new project's changelog: the header and one install entry. Splits on `## YYYY-MM-DD:` headings outside code fences. Tests: `tests/test_changelog_archive.py`.
2. **`process/changelog-archive/2026-Q1.md`, `2026-Q2.md`** (new) — cc-sdlc's own 203 entries from March to June, moved unedited. The live file is 171 KB with 46 entries (Q3 and Q4): over 150 KB, with nothing older than the previous quarter, so it stays until January. 15 old entries have no `---` before the next one; kept that way, so `release.yml` sees no old entry as new.
3. **`skills/sdlc-initialize/SKILL.md`** — Phase 1b writes the changelog with `init` from the source at `HEAD` instead of copying it; the archive is never installed; the changelog stays out of `installed_files`.
4. **`skills/sdlc-migrate/SKILL.md`** — §1.2 reads cc-sdlc's archive at the target tag when the project's version predates the live file; §1.3 rows for skill scripts (direct copy) and the archive (not installed, never overwritten); §2.1 copies `process/*.md` top level only and copies skill scripts; §2.1a ignores archive paths; new §4.5c runs `archive --upstream` (cc-sdlc's changelog and archive at the target tag) on the project's changelog every migration, automatically, so copied cc-sdlc entries leave and old quarters follow; back-fills skip never-overwrite files; the report lists what moved.
5. **`skills/sdlc-archive/SKILL.md`** — the inventory runs a dry run, the approval table gets a changelog row, step 8a runs it, and a red flag forbids moving entries by hand.
6. **`process/path-mappings.md`**, **`process/README.md`**, **`process/adapter-lifecycle-protocol.md`**, **`agents/sdlc-compliance-auditor.md`** — the archive is project-owned, never overwritten, never installed from cc-sdlc, and exempt from adapter transformation and the phrasing scan.
7. **`skeleton/manifest.json`** (the script listed; a not-installed note), **`skeleton/contract_changes.yaml`** (0017, `type: other`), **`CLAUDE.md`** (the consistency glob covers `skills/*/scripts/*.py`), **`.github/workflows/changelog.yml`** (new: the tests and `check`, on change and each quarter's first day; it never archives by itself), **`.claude/skills/ccsdlc-audit*`** (exempt lists; a project's changelog no longer holds cc-sdlc's entries).
8. **Paired adapter change:** `neuroloom-sdlc-plugin` `ddcc382` exempts `process/changelog-archive/*.md` in the transformer, the pattern rules, the post-operation audit and `sdlc-port`'s remapping.

**Rationale:** the framework's history belongs to cc-sdlc, where migration already reads it; a project's changelog is its own record. Moving whole quarters unedited keeps every entry findable by date, and a script that proves nothing was lost is safer than an agent copying 600 KB by hand. `release.yml` needs no change: it takes entries present now but not at the previous tag, and archiving only moves old ones. The one gap: an entry added after a tag and backdated into an already archived quarter would miss that release's notes.

---

## 2026-10-11: Migration never overwrites a project's changelog

**Origin:** sizing the changelog for archiving (CD asked for it to be archived, 2026-10-11). Every project's changelog turned out to be a full copy of cc-sdlc's history plus its own entries (quantile: all 199 cc-sdlc entries from March to May, and 54 entries of its own).

**What happened:** `sdlc-migrate` treated `process/sdlc_changelog.md` like any other process doc: a direct copy from upstream. Drift detection caught the project's edits, so on a tracked install every migration raised a hard three-way prompt over a file every project edits by design; on an install from before `installed_files`, the first migration had no drift data and would have copied over the project's own entries.

**Changes made:**

1. **`process/path-mappings.md`** — `process/sdlc_changelog.md` joins the Project-Specific Files (Never Overwrite) list.
2. **`skills/sdlc-migrate/SKILL.md`** — the changelog is excluded from direct copies (§1.3's table, §2.1's Step 0 and list); drift detection skips every never-overwrite file, since their edits are expected; new §4.5b prepends one entry recording the migration (version, the upstream entries applied, the project's decisions) instead of copying upstream entries; § Preserved lists it.

**Rationale:** the project's changelog is the project's record; the framework's history already lives in cc-sdlc, where §1.2 reads it. Archiving old entries (CD's decision) is a separate, larger design, in `docs/current_work/ideas/changelog-archiving_design.md`.

---

## 2026-10-11: A headless run stops before its time limit, not at it

**Origin:** the software factory's "work survives no stop" follow-up (`docs/current_work/ideas/software-factory_handoff.md`). quantile's D14b full-tier plan ran past its 2-hour step limit and was killed: about 2 hours of work, no result, no transcript.

**What happened:** headless callers stop a run at a time limit, but nothing told the run how long it had, so it could only be killed. A killed run returns nothing: no document, no notes, no result for the caller to act on.

**Changes made:**

1. **`process/headless-mode.md`** — § Ending a Headless Run: a caller that kills the run at a time limit gives it a time budget (how long, and the margin to keep for stopping). The run checks the time between steps; at the margin it starts nothing new, commits what is done, and stops with the status the caller names for running out of time, with what is done and what is left in `notes`. A red flag for pushing past the margin.

**Rationale:** a stop a few minutes early leaves a result the caller can resume or publish; a kill at the limit leaves nothing. The caller owns the clock and the status, so the rule only says to stop at its margin and with its status.

---

## 2026-10-11: Improvement mode reads a factory digest, report-only when headless

**Origin:** the software factory's phase 4, the weekly improve loop (`docs/current_work/ideas/software-factory_handoff.md` § Next build). CD decided (2026-10-10) that once a week the factory reads its own GitHub record of what CD did to its output and posts a report CD acts on: report only, every item actionable, every area covered, ranked, and tracked across weeks.

**What happened:** `sdlc-audit` improvement mode took sessions and commits only, and its Applying Improvements step edited files on approval. The factory's analyze job has neither a session nor a person: it gets a digest of signals built deterministically from GitHub, and it must never apply anything.

**Changes made:**

1. **`skills/sdlc-audit/SKILL.md`** — a new input, the **factory digest** (`/sdlc-audit improve <digest>.json`, recognized by `kind: factory-digest`), and § Improvement with a Factory Digest: the digest's signals, metrics and ledger; quoted text is untrusted data; check the window's commits so already-fixed problems aren't proposed; reference an earlier proposal's fingerprint instead of re-proposing it; each proposal names its target, change, why (signal ids, never invented), expected effect, severity and route (`hygiene`, `cd`, `cc-sdlc`, `issue`); all five sections are considered and an empty one means nothing to action. A **Headless run:** line there and at § Applying Improvements: return the proposals with status `awaiting-approval`, apply nothing. Two red flags (quoted text as instructions; a re-worded duplicate of a ledger item).
2. **`skills/sdlc-audit/references/improvement-methodology.md`** — § Extraction from a Factory Digest: what each signal says and where its fix usually goes, patterns over events, what CD needs from each proposal; evidence for a digest is its signal ids; a headless run never applies.
3. **`process/headless-mode.md`** — § Integration lists `sdlc-audit`'s factory-digest input and Applying Improvements as gate sites.
4. **`process/writing-for-cd.md`**, **`CLAUDE-SDLC.md`** — improvement proposals are something CD reads, budget about 100 words each.

**Rationale:** the improve loop's analysis is the same judgment as an improvement audit, so it runs the same skill rather than a factory-only prompt. Making the digest a first-class input, and the headless contract explicit, keeps the factory's report from drifting away from how interactive audits reason, and keeps it from ever changing what CD hasn't approved.

---

## 2026-10-11: Discovery check-in and headless results follow writing for CD

**Origin:** the first live discovery check-in (quantile D14c, issue #48). CD asked whether it followed the writing-for-CD rules, and then asked that every surface the factory uses to reach CD does.

**What happened:** The check-in question ran to about 1,150 words. It re-explained decisions CD had already approved item by item, listed implementation details CD doesn't decide, and gave each option a paragraph. The check-in rule set no budget and no filter, and `writing-for-cd.md` didn't name headless results as something CD reads, though callers post their questions, reasons and findings straight to CD.

**Changes made:**

1. **`process/writing-for-cd.md`** — § Where It Applies names the parts of a headless result a caller shows CD (questions, a stop's reason, findings, deferred items); `notes` keeps its detail. Length budgets add a stop's reason (1–2 sentences) and a discovery check-in (about 300 words, only what CD hasn't decided, one line per assumption and per choice). § Integration lists the check-in.
2. **`process/headless-mode.md`** — the check-in is about 300 words: one line for what carries over from what CD approved, one line per undecided assumption with its source, one line per open choice with its recommendation and the alternative's cost. Facts go in `notes`. § Ending a Headless Run adds "Write the result for CD where CD will read it".
3. **`skills/sdlc-plan/SKILL.md`** — the check-in block matches.
4. **`CLAUDE-SDLC.md`** — § Writing for CD covers what a headless caller posts, and its budgets name the check-in.
5. **`process/writing-for-cd.md`** — fixes mirror drift found by the consistency check. The Completion Report source block gets the Add-ons and Follow-ups lines that `sdlc-execute` and `sdlc-lite-execute` gained with add-ons (2026-10-09), so source and copies match again.

**Rationale:** a check-in CD can't read in a minute gets skimmed, which defeats the point of asking. Headless results are the factory's main voice to CD, so they get the same budget as everything else CD reads.

---

## 2026-10-10: Discovery check-in — a headless spec run can confirm its basis with CD before writing

**Origin:** the software factory's full-tier test (quantile D14b, issue #47), and CD's direction to have the spec stage ask its discovery questions.

**What happened:** Three D14b spec runs reached discovery. One stopped with a real question (live's late 5m bars break the parity bar under Rule C). The other two settled all of discovery from D11b's records, never asked, and wrote specs that didn't address that problem. The headless DISCOVERY-GATE counts questions the records already answer, so a run with rich history never stops. That drifts from the factory's decision (F18) that the full-tier spec stage has a discovery conversation with CD.

**Changes made:**

1. **`process/headless-mode.md`** — § The Rule adds the **discovery check-in**, a caller option and the one exception to "ask what blocks the next step, and no more". When the caller's prompt asks for one, `sdlc-plan` stops once with `needs-input`, after the DISCOVERY-GATE and FAR gate pass and before the spec is written. The stop carries one question, "is this the right basis for the spec?", listing the assumptions with their sources and the open choices with recommendations. It is not a batch, and it happens once per deliverable. The answered-question red flag names the exception, and § Integration lists the new gate site.
2. **`skills/sdlc-plan/SKILL.md`** — a **Discovery check-in** block as the last step before step 2, with its **Headless run:** line. The DISCOVERY-GATE's no-batching rule says the check-in isn't a batch. **Headless restart** gains a bullet (CD answered the check-in → apply it, start at step 2, never repeat it), and `notes` record whether it was asked and what CD answered.

**Rationale:** confirming the assumptions costs CD one reply, while a wrong assumption found later costs a whole spec run. It's opt-in, so callers that don't want the stop keep today's behavior. This is new contract surface (a caller option in the headless contract), so it's a minor bump when CD cuts a release.

---

## 2026-10-10: Production gates — fixes from the convention review

**Origin:** an `sdlc-reviewer` pass over the production-gates change (the entry below), the same day.

**What happened:** The new gate text left four gaps: lite execution still said it commits once; the review loop before a gate ended with step 2's hand-off to step 3, which would skip the rest of the plan; a plan with production work inside a phase (D11b's shape) had no stop at execution; and the interactive gate put a runbook and a question in one turn.

**Changes made:**

1. **`skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`** — the review before a gate emits its own REVIEW-GATE line and proceeds to the gate, not to step 3 (past the cap at CD's direction, with the open findings recorded); every loop's open minors and feedback go in the result doc; the gate is presented as a completed message before the question, and the report-back values are asked once it's done; a phase holding production work is triaged REVISE_PLAN and never dispatched; gate rows are never dispatched; the review after a gate starts at round 1. Lite: the per-gate commit uses step 4's format, and the "commits once" lines say so.
2. **`process/production-gates.md`** — no phase after a gate starts before it's done; approving a deploy gate authorizes deploying before Validated, and the deliverable stays In Progress; typed parameters defined; push the branch before a gate whose steps use `${head}`.
3. **`process/headless-mode.md`** — `production-gates.md` § At a Gate joins the gate-site list; the approval row says the next run receives the gate's result.
4. **`skills/sdlc-lite-plan/SKILL.md`, `skills/sdlc-plan/SKILL.md`** — reviewers check each gate in both; "catalog patterns".
5. **`templates/planning_template.md`** — the example gate sits between Step 2 and Step 3, matching its "After: Step 2".

**Rationale:** each gap would have shown up the first time a plan reached a gate: an execution ending early after the pre-gate review, or an older plan's deploy dispatched to an agent.

---

## 2026-10-10: Production gates — production work happens only in gates between phases

**Origin:** the software factory's gap 1 (`docs/current_work/ideas/software-factory_handoff.md` § Gaps). quantile D11b's plan mixed a deploy into a phase ("Phase 3: code + Deploy step 1"), so nothing running plans unattended could tell which steps needed production. CD decided the factory gets a production-capable runner with per-step approval; the framework half is the plan structure every project uses, with or without a runner. Cross-checked with a Fable advisor and Codex (`gpt-6-astra`, max effort).

**What happened:** Plans had no place for production work. It sat inside phases, where an execute run would either do it (a live-system change no headless run may make) or skip it silently. Execution's review loop also ran only after the last phase, so a deploy in the middle of a plan would have shipped unreviewed code.

**Changes made:**

1. **`process/production-gates.md`** (new) — what a gate is (production work between phases, done by CD or the project's production runner after CD approves, never by an agent); the gate section (runbook, report-back fields, rollback, optional `gate-ops` block); gates don't count toward the phase limit; the last item is a phase; a review loop and commit before every gate; interactive and headless behavior at a gate and after it; the optional operations catalog with its placeholders and two approvals.
2. **`templates/planning_template.md`, `templates/sdlc_lite_plan_template.md`** — a gate section between phases and gate rows in the Phase Dependencies table.
3. **`templates/result_template.md`, `templates/sdlc_lite_result_template.md`** — a Gates section: outcome, when, done by, report-back values.
4. **`skills/sdlc-plan/SKILL.md`, `skills/sdlc-lite-plan/SKILL.md`** — production work goes in gates; gates don't count toward the 7- or 4-phase limit; reviewers check runbook, rollback and report-back; the Approval Brief lists every gate. A red flag each.
5. **`skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`** — before a gate: the review loop over the work since the last gate, then a commit (lite commits once per gate). At a gate: interactive shows CD the gate; headless stops with `awaiting-approval`, the gate named in `stage` (and a `gate` field when the caller's schema has one). The headless restart after a gate records its result or stops with `needs-input`. The completion review covers the work after the last gate. Three red flags each.
6. **`process/headless-mode.md`** — a production gate is an approval gate whose action plan is the gate's steps; the execute skills' gate-site entries name it.
7. **`skeleton/manifest.json`, `process/README.md`** — the new process doc.

**Rationale:** Production work is the riskiest part of a plan and the one part an agent must never do on its own. Giving it a fixed place makes it visible at plan approval, approvable at the moment it happens, reversible by a stated rollback, and reviewable before it ships. The same structure serves a project where CD runs every gate by hand and one where a production runner does it after CD's approval. Release: minor (a new template structure and process convention, additive).

---

## 2026-10-09: Dependencies between deliverables, and splitting a deliverable

**Origin:** quantile D11. D11 split into D11a → D11b → D11c, but the split and the dependencies lived only in prose, so D11a dropped out of sight while D11b was planned against it (`docs/current_work/ideas/prerequisite-tracking_handoff.md`). The software factory also needed a split it could act on (`software-factory-gaps_design.md`, gap 2). CD approved building both together, cross-checked with Codex and Fable.

**What changed:**
- **Catalog:** a `Depends on` column in the deliverable catalog (`skeleton/manifest.json` template, `skills/sdlc-initialize` seed), with a Notes bullet on its format.
- **`process/deliverable_lifecycle.md`:**
  - **§ Dependencies:** where dependencies are recorded (the catalog column; a deliverable ID in a plan's Phase Dependencies row gates that phase), who fills them, and what checks them.
  - **§ Splitting a Deliverable:** split records, part rows, the parent as umbrella, one level only.
- **`templates/split_record_template.md` (new):** the document CD approves for a split. Its parts table carries name, tier, dependencies, a reused spec and scope.
- **`templates/planning_template.md`, `templates/sdlc_lite_plan_template.md`:** a phase's Depends On may name a deliverable.
- **`skills/sdlc-plan`:**
  - a § Splitting a Deliverable procedure (propose parts, write the split record, register the parts, approval; headless stops with `awaiting-approval` and the split record);
  - the Feasibility Gate and the phase limit point to it;
  - registration fills `Depends on`, and existing deliverables report unplanned prerequisites.
- **`skills/sdlc-lite-plan`:** uses an existing ID (a split part) instead of claiming one, fills `Depends on`, and reports unplanned prerequisites.
- **`skills/sdlc-execute`, `skills/sdlc-lite-execute`:** at load, run only phases no unfinished prerequisite gates. Interactive runs ask CD whether to continue; headless runs stop with `needs-input`.
- **`skills/sdlc-status`:** shows deliverables waiting on a prerequisite, split parents, and a **Forgotten Prerequisites** section.
- **`skills/sdlc-audit/references/compliance-methodology.md`, `agents/sdlc-compliance-auditor.md`:** flag missing IDs, cycles, Draft prerequisites of active work, and split parents without a split record.
- **`process/headless-mode.md`:** split approval is an approval gate, and the execute prerequisite stop is listed in § Integration.
- **`skeleton/contract_changes.yaml` and `skills/sdlc-migrate` §4.5a:** a new `catalog_column_added` entry type, and entry 0016, which back-fills `—` into existing catalogs.

**Release:** minor. New contract surface (a catalog column projects write, a new template and a new entry type), purely additive with a back-fill default.

**Rationale:** A dependency no tool reads is a dependency nobody sees. One column plus a few checks surfaces the three failures that bit D11: blocked work, execution starting before a prerequisite is done, and a prerequisite nobody is moving forward. A split record gives CD one document to approve, and gives the factory something it can act on.

---

## 2026-10-09: Add-ons finish small follow-ups; Follow-Up Items become issue-ready

**Origin:** CD, after the software factory's first executed plan (quantile D13) deferred two stale knowledge entries and left its follow-ups in the result doc. CD's direction: SDLC hygiene is part of the work, a quick follow-up is finished in the PR as an add-on, and anything else becomes its own issue and goes through triage. Cross-checked with Fable and Codex.

**What changed:**
- `skills/sdlc-lite-execute` and `skills/sdlc-execute`: an **Add-ons and follow-ups** rule.
  - **Add-ons:** small, no new decision, inside the touched area, dispatched and verified like planned work, listed in the result doc.
  - **SDLC hygiene:** knowledge entries or parking-lot notes the change makes wrong are corrected in the same deliverable.
  - **Everything else is a Follow-Up Item:** F-numbered, an issue-ready title, why not now. Nothing is dropped silently.
  - The PR body example's Scope gains Add-ons and Follow-ups lines.
- `templates/sdlc_lite_result_template.md` and `templates/result_template.md`: a new **Add-ons Beyond the Plan** section, and **Follow-Up Items** in a parseable checklist format (`- [ ] **F1: title**: what _Not now: why_`).
- `templates/pr_description_template.md`: Scope's Deferred line becomes Add-ons and Follow-ups. Follow-ups are a checklist CD can prune before merging.

**Rationale:** Follow-ups that live only in a result doc are forgotten, and tiny ones aren't worth an issue each. Finishing small ones in the PR and making the rest issue-ready lets a project (the factory does) file them automatically.

---

## 2026-10-09: Codex calls can't hang on stdin

**Origin:** A direct `codex exec` consult run from a background shell sat idle for 35 minutes. It printed "Reading additional input from stdin..." and waited for an end-of-file the open, empty pipe never sent.

**What changed:**
- `process/external-review-gate.md`: direct `codex exec` calls (no piped payload) end with `< /dev/null`, and the Task-Based Model Selection example shows it. The wrapper bullets list the new time limit and the stdin refusal.
- `templates/external-review.sh.template` and `templates/external-review-knowledge.sh.template`: refuse to run without piped stdin, and bound the codex call with `CODEX_TIMEOUT_SECS` (default 1800) through a portable `perl` alarm. A stall now skips the gate with a message instead of hanging.

**Rationale:** The wrappers always pipe a payload, so they were safe in normal use, but nothing stopped a background or ad-hoc call from waiting forever, and a stalled model call had no bound at all.

---

## 2026-10-09: Writing for CD — plain, short output in every session

**Origin:** CD, after the PR description standard landed: "I regularly find that I tune out because the agent is just so verbose and it just becomes information overload." CD wanted the PR's readability in every interactive SDLC session, and asked whether this belongs in the framework or in an installed output style.

**What happened:** Most of the overload was written into the skills themselves. Plan approval pasted the whole plan into plan mode (quantile's D13 plan is 12,020 words). The completion report's change list was required to be "exhaustive". Gate checklists and review rosters printed in full every time. An output style can't override that, and the docs confirm it doesn't reach dispatched agents. Only one style can be active, and CD already uses personal ones (Architect Mentor, and ELI5 Finance Mentor in quantile). So the fix goes in the framework, and personal styles stay a teaching layer on top. Mid-change, CD also dropped plan mode: "I generally close a session and start a new one to execute the plan."

**Changes made:**

1. **`process/writing-for-cd.md`** (new) — The standard for anything CD reads.
   - **Rules:** lead with what CD needs, plain language, say each thing once, evidence over claims, say where you're unsure, don't invent, keep to the budget.
   - **Length budgets:** status updates 1–2 sentences, end-of-turn summaries about 150 words, approval briefs about 450, completion reports about 500.
   - **Status blocks:** one line on the happy path, and a plain sentence before any findings table.
   - **Approval Briefs:** shown verbatim, then the path, in a message that ends the turn. CD's reply is the approval: the one approval asked without `AskUserQuestion`, now stated in `CLAUDE-SDLC.md` and `process/collaboration_model.md` too.
   - **Two mirrored blocks:** the Approval Brief procedure (`approval-brief`) and the Completion Report (`completion-report`). The procedure: the writing agent fills the brief's `###` headings with `Edit`, naming every decision CD approves; a fresh reader checks it; the manager counts its words. Both blocks are registered in § Mirrored Blocks and `process/project-section-markers.md`.
   - **Soft gates (a behavior change):** a FAR or FACTS gate that passes now prints one line and the run continues, where before every soft gate waited for CD. A failing one still waits (also in `process/input-quality-gates.md`). To restore the pause, revert that sentence in the two plan skills and the gates doc.
2. **`CLAUDE-SDLC.md`** — new § Writing for CD for every session. Key References lists the doc.
3. **Approval Briefs** — `templates/spec_template.md`, `planning_template.md` and `sdlc_lite_plan_template.md` gain a `## Approval Brief` section at the top.
   - `sdlc-plan` gains step 2a (spec brief) and step 5b (plan brief); `sdlc-lite-plan` gains step 4a. Each carries the `approval-brief` block; the process diagrams gain the new nodes, and the headless restart paths cover a plan change request.
   - Spec approval (step 3) shows the brief, the path and "To approve, reply approved" as a message of its own, and takes CD's reply as the answer. SPEC-REVISION re-runs step 2a after a scope change or pivot.
   - The lite plan's Definition of Done gains a seventh item for the brief.
4. **Plan mode removed** — `sdlc-plan` step 6 and `sdlc-lite-plan` step 5 are now "Present the Approval Brief".
   - The plan file is read, the brief is pasted verbatim, then the path and "start a new session and say: Execute the plan at …".
   - Approval is CD starting execution in a new session. `EnterPlanMode`/`ExitPlanMode` and the execution-prompt text are gone, from the skills and from `process/headless-mode.md` and `process/html-rendering.md` too.
   - The Read-then-paste rule against summarizing stays.
5. **Completion report** (`sdlc-execute`, `sdlc-lite-execute` step 5) — now the `completion-report` block:
   - the code variant of the PR template, with the same sections in the same order, bold labels for the terminal, What was built in place of What you're approving, What you need to do first and Commits last;
   - explicit always-present and left-out-when-empty sections;
   - critical or major findings CD directed past the cap shown under Review focus;
   - Scope integrity drawn from the deviation log and a diff of test and CI paths;
   - about 500 words, with the exhaustive file list kept in the result doc;
   - "Present the full commit" folded into the Commits line;
   - a PR opened from the report's sections in the template's PR form, after the fresh-reader check.
6. **One-line status blocks:**
   - pass lines for VERIFICATION-GATE (keeping the resolved library ID and how infrastructure was checked) and DISCOVERY-GATE;
   - FAR and FACTS pass lines (also in `process/input-quality-gates.md`);
   - REVIEW-GATE as one line, without repeating the roster;
   - review rosters and plan revision dispatches as one line instead of checkbox lists, in `process/review-fix-loop.md` Step A and both plan skills. The count-must-match rule now counts names.
7. **`process/finding-classification.md`** — one plain sentence before the Classification Table.
8. **`templates/pr_description_template.md`** — the general rules now live in the writing standard. A plan or spec PR's description is the document's Approval Brief. `process/headless-mode.md` fills a caller's PR fields from the brief.
9. **`process/collaboration_model.md`** § Completion Reports, and `sdlc-lite-execute`'s description — updated to match.
10. **`skeleton/manifest.json`** — lists `process/writing-for-cd.md`.

11. **Quality gate** — `sdlc-reviewer` ran on the four skills in two parallel passes and found 0 critical, 7 major and about 35 minor findings and nits. All majors were fixed:
   - the brief's heading level (it must stay `###`, or the word count and the shown brief break);
   - the `sdlc-plan` diagram;
   - the report's empty-section rules;
   - the PR/report shape and order;
   - open critical findings in the report;
   - the duplicated report and brief procedure, now mirrored blocks.

   Most minors were fixed too: stale "checklist" wording, restart paths, the approval exception, the FAR metric, the VERIFICATION-GATE one-liner, and the red flags. Not fixed, because they predate this change: skill size, `sdlc-plan`'s Integration labels, `sdlc-review-code`'s own dispatch checklist, and the diagrams' missing step 5 node in the execute skills.

**Rationale:** CD approves and steers from what the agent shows, and a wall of text gets skimmed: an approval CD couldn't follow isn't an approval. The documents agents work from keep their detail; only what CD reads gets shorter and plainer. Briefs come from the document's author and are checked by a fresh reader, so the manager never paraphrases, which was the reason for the old verbatim-paste rule. Release type: minor (a new cross-skill convention and new skill steps).

---

## 2026-10-09: A reviewable PR description standard

**Origin:** `docs/current_work/ideas/pr-description-standard_handoff.md`. The software factory opened its first plan PR (quantile #31, the D13 plan for issue #30). CD couldn't approve it: "It doesn't really feel right for me to read and approve something that I don't understand."

**What happened:** The plan is written for the executing agent: exact functions, file lines, test fixtures. That is the right content for the agent's contract and the wrong document for CD's approval, and the PR body inherited the same voice. Every PR that asks CD to approve agent-written work has this problem, interactive or factory-made. cc-sdlc had no PR-description guidance at all.

**Changes made:**

1. **`templates/pr_description_template.md`** (new) — The standard, with a plan/spec variant and a code variant.
   - **Fixed sections, in order:** The problem; What changes for users; What you're approving (numbered decisions, each with the alternative it rejects, plus any scope beyond the issue); Scope (tackled, not tackled, deferred); Risk (tier, top risks, undo); Review focus; How it will be verified; How it works (the approach and why it is shaped that way); Learn the change (files in reading order with their roles, and concepts); then a collapsed agent record. Each section has a word share.
   - **Code variant:** How it was verified shows results, not intent. It adds Scope integrity and Deviations from the approved plan (omitted for a direct fix). Open critical or major findings go under Review focus, in plan PRs too.
   - **Rules:** plain language, with code names only where they help CD find or check something. About 450 words above the agent record for a plan, 500 for code. Say each thing once. Evidence over claims. Don't invent: an empty list is fine. Line-level explanation stays in code comments. Headless fields are plain sentences, because the caller renders the formatting.
   - **Fresh-reader check before opening:** a reader given only the description and the plan or diff must be able to explain the change, and every statement must match its source.
   - **Risk tiers:** high, medium and low, decided by what valid use gets and whether a revert undoes it, with the highest fitting tier winning. Each project lists its always-high areas in its own `PROJECT-SECTION` block.
   - **Examples:** a complete plan PR from quantile #30 (D13), and the code-only sections for the same change.
2. **`CLAUDE-SDLC.md`** — new § Pull Request Description: every PR that asks CD to approve agent-written work follows the template, whether a person or the factory opens it. Key References names the template.
3. **`process/headless-mode.md`** § Ending a Headless Run — when a caller's schema has PR-description fields, fill them per the template, never pasted from the plan. Integration lists the template.
4. **`skills/sdlc-plan`, `skills/sdlc-lite-plan`** (Output) — when the spec or plan is approved through a PR, its description follows the plan variant. The plan file is unchanged.
5. **`skills/sdlc-execute`** step 4 item 8 and **`skills/sdlc-lite-execute`** step 4 — a PR carrying the work follows the code variant: deviations come from the result doc, and verification shows the build and test results.
6. **`skeleton/manifest.json`** — lists the template. `sdlc-migrate` §2.1 already direct-copies every manifest-listed template and preserves `PROJECT-SECTION` blocks, so it needs no change.

**Rationale:** CD approves through the PR and, as CD put it, reviewing PRs "is going to be the predominant way in which I look at the code in the first place." So the PR has to say for sure what is being approved, why, at what risk and with what proof, and leave CD understanding the codebase better. The research behind the sections is in the handoff: Google's CL descriptions and Bacchelli & Bird on the why; Willison, Osmani and Phabricator test plans on evidence; Osmani, Atlassian and Kubernetes on review focus; Spotify Honk and GitHub's agent-PR guide on scope integrity; the Rust RFC guide-level explanation and PEP "How to Teach This" on learning. CD overrode Google's "explanations belong in code comments" for the approach-level "How it works". Line-level explanation still goes in comments. A Codex cross-check (gpt-6.1-sol) before building shaped four choices: one file map rather than separate read-order and key-file lists, a fresh-reader check, "don't invent" for lists that can be empty, and risk tiers by reversibility. Release type: minor (a new cross-skill convention).

---

## 2026-10-09: Headless runs dispatch agents in the foreground

**Origin:** The software factory's first live lite-plan run (quantile #30) ended after 4 minutes. The Agent tool launched the plan writer in the background by default. The orchestrator ended its turn to wait for it, and the run closed with the plan unwritten.

**What changed:**
- `process/headless-mode.md` § Ending a Headless Run: every agent is dispatched in the foreground, and the run waits for its result. Callers switch background launches off in the runtime (`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`). Added a Red Flags row.

**Rationale:** A headless run ends with the orchestrator's turn. This was already a rule in the factory's `sdlc-implement` skill; every headless skill that dispatches agents needs it.

---

## 2026-10-08: Headless mode — the rule for running skills with no person present

**Origin:** Software-factory handoff (`docs/current_work/ideas/software-factory_handoff.md`), phase 2 prerequisite "Headless rule". Decision F13 made it a cc-sdlc framework change from the start, ahead of the opt-in `factory` bundle. Phases 0–1 now run `/sdlc-triage` unattended on a self-hosted runner in quantile, and phase 2 will run implementation skills the same way.

**What happened:** Every skill assumed CD was present. Questions went through `AskUserQuestion`, spec approval waited for CD, plan approval went through `EnterPlanMode`/`ExitPlanMode`, phase triage SKIP/REVISE_PLAN waited for confirmation, and the review-loop round cap escalated through `AskUserQuestion`. Under `claude -p` with `--permission-prompts none`, `AskUserQuestion` does not exist, and nothing said what a skill should do instead. The likely failure was guessing past a gate or approving its own work to keep going. The framework had never defined a headless run (the evaluation's Explore pass: "the framework has never run headless").

**Changes made:**

1. **`process/headless-mode.md`** (new) — The rule.
   - **Detection:** a line starting `SDLC headless mode:` in the caller's prompt or appended system prompt (primary). The phrase quoted in the rule, `CLAUDE.md` or a skill doesn't count. Fallback: no ask-the-user tool can be used — neither `AskUserQuestion` nor the harness's equivalent (OpenCode's `question`) is available or loadable, or a call to it is denied without an answer. A deferred tool counts as available.
   - **Subagents:** a dispatched subagent is never headless itself. In a headless run the orchestrator says so in every dispatch prompt, so the limits bind the subagent.
   - **The rule:** every point that needs CD stops the run, and nothing is guessed, defaulted, self-approved or skipped. Seven kinds of point:
     - a question the next step depends on → `needs-input`;
     - a bounded loop that ran out without meeting its bar (review round cap, a FIX that failed twice — not reclassified headless: the run stops and CD decides where it goes — the External Review Gate's fix-round limit, debug-incident T6, the tests-run round limit) → `escalated`;
     - an approval gate (spec, plan mode, or an action plan such as `sdlc-archive`'s archive set or `sdlc-migrate`'s change plan) → save it and stop with `awaiting-approval`. An action plan goes in the result in full, never call `EnterPlanMode`/`ExitPlanMode`, and the next run executes exactly what was approved or stops again;
     - a soft gate (FAR, FACTS) → continue on a pass, stop with `needs-input` on a fail;
     - a question the next step doesn't depend on (PRE-EXISTING findings, minor PLAN findings) → list it under `deferred` and continue. A critical or major PLAN finding stops, because deferring it needs CD (manager rule);
     - an optional offer → take the no path and list it under `skipped`;
     - confirmation of local, reversible work (committing the skill's own output, even when framed as optional) → proceed.
   - **Answered questions are not gates:** a question the prompt or thread already answers doesn't stop the run. Skill pacing rules still hold, and work done before the stop stays.
   - **Outward actions go to the caller:** no side effect outside the working tree. That rules out push, PRs, comments, labels, publishing, messages, external sends and live-system changes, and github-provenance checkpoint writes (their local half still runs, and their GitHub half becomes a rendered `outbound` entry). Reads from anywhere are fine (Context7, web search, `gh` reads, an upstream fetch), and writes to the project's configured knowledge backend count as local. The External Review Gate runs only against a local model or a durably authorized hosted provider. Each skipped action is listed under `outbound`, unless the caller's prompt names it.
   - **Ending:** a stop is a result, so the run ends its turn normally. The run can't set its own exit code, so the status carries the outcome. `failed` with a `reason` is for a precondition the caller must fix.
   - **Result format:** a skill's own closing report comes first and the result last. With `--json-schema`, the caller's schema is the contract; any field it lacks (`notes`, `deferred`, `skipped`, `outbound`) goes into the stage's saved document under `## Headless Result`. Otherwise the run ends with a `## Headless Result` block: status, stage, reason, questions, findings, documents, deferred, notes, skipped, outbound.
   - **Restart, not resume.** A skill whose restart from step 1 would repeat a side effect or lose counted state carries a **Headless restart** paragraph in its entry step. It skips work already done, never registers the deliverable twice, and keeps counting completed phases, review rounds and the frozen roster.
   - **Kept out of core:** factory specifics (labels, markers, writer jobs, approval by merging the doc PR).
2. **Every skill in `skills/`** (27) — Carries the `headless-stop-rule` mirrored block verbatim, inside `MIRROR` markers.
   - **Placement:** directly after the `**AskUserQuestion mandate:**` paragraph where a skill has one (`sdlc-plan`, `sdlc-lite-plan`, `sdlc-execute`, `sdlc-lite-execute`, `sdlc-tests-create`, `sdlc-create-reference-doc`, `sdlc-debug-incident`). Otherwise, before the first `##` section.
   - **Coverage:** every skill carries it, including skills that never ask anything, so choosing consumers takes no judgment. Project skills may carry it too.
   - **How it was done:** copied by script from the source. The audit's drift check reports no drift across all 33 mirrored copies: 27 headless and 6 review-loop.
   - This follows the 2026-05-19 lesson that a pointer alone gets skipped.
3. **Gate-site lines** (outside the mirrored block):
   - **`sdlc-plan`:**
     - step 0 **Headless restart**: skip registration and finished steps, and never mint a second D-number. Spec approval → set Ready and start at 3d, or stop again if the spec changed since. Spec feedback → the SPEC-REVISION block in step 3. A discovery answer → the DISCOVERY-GATE in step 1. DECIDE answers, a FACTS decision or an escalated review → step 5 at the recorded round with the frozen roster. `notes` carry the D-number, complexity, worktree, agent list, prior context and ADR constraints, playbook match, review round, roster and open findings.
     - DISCOVERY-GATE: answered questions count toward the minimum; on a FAIL, stop with the single most blocking question.
     - FAR and FACTS: continue on a pass, stop on a fail.
     - step 3 spec hard gate: `awaiting-approval`.
     - step 6: skip 6a–6c and stop with `awaiting-approval`. "Follow these sub-steps in exact order" is now labelled **Interactive run**, as is the step's opening line.
     - Output section and a red flag.
   - **`sdlc-lite-plan`:** step 0 **Headless restart** (never a second ID or plan file; resume at FACTS or review with the recorded round and roster), step 5 (the same as step 6), FACTS (pass = every phase meets the thresholds), the summary line, the Output section, and a red flag.
   - **`sdlc-execute` and `sdlc-lite-execute`:**
     - step 0: no plan → `failed` with the reason. A **Headless restart** paragraph reads the plan, partial result doc and notes, skips completed phases, and continues the review round count with the frozen roster.
     - PRE-GATE "Triage ≠ BUILD": stop with `needs-input`, giving the phase, SKIP or REVISE_PLAN, and the reason.
     - Completion Report: the Headless Result follows it as the last output.
     - `sdlc-execute` step 4: no push or PR, both listed under `outbound`.
   - **`sdlc-handoff`:** step 7 commits the handoff locally without asking (when the project commits SDLC docs), never pushes; the "Always ask" red flag is scoped to interactive runs.
4. **`process/review-fix-loop.md`** § Round Cap — New headless bullet:
   - at the cap with a critical or major finding open, save the partial result doc and stop with `escalated`;
   - DECIDE and unresolved INVESTIGATE findings stop with `needs-input`;
   - a FIX that fails twice is not reclassified and stops with `escalated`;
   - PRE-EXISTING and minor PLAN findings go under `deferred`, and a critical or major PLAN finding stops with `needs-input`.

   It sits outside the `MIRROR-SOURCE` blocks, so the six review-loop copies are unchanged. The Step C "FIX failure escalation" line and the § Round Cap closing line, plus **`process/finding-classification.md`** § FIX Failure Escalation, say a headless run stops with `escalated` instead of reclassifying.
5. **`process/html-rendering.md`** § Post-Skill Offer — Headless runs take the no path and list the offer under `skipped`.
6. **`process/external-review-gate.md`** § Data egress — In a headless run without durable authorization, hosted-model runs are skipped and listed under `skipped`. A local model or a durably authorized provider runs as usual. The opening list of sanctioned reasons to skip a configured reviewer now includes this one.
7. **`process/github-checkpoints.md`** — New § Headless Runs. The run never writes to GitHub itself, and each checkpoint splits in two:
   - **Local half (still done):** when the issue is known (named in the caller's prompt, or already recorded in an earlier artifact's frontmatter or the catalog's linked ID cell), CP-1 writes `github_issue:` (and `github_board:`) into the first artifact's frontmatter and the catalog ID cell as a link. The ⎘ checkpoints commit their artifact locally under § Commit Conventions, without pushing.
   - **GitHub half (handed to the caller):** each checkpoint, and `sdlc-archive`'s parked-issue closure, adds a rendered entry to `outbound` in firing order. The fields are `checkpoint`, `deliverable`, `issue` (or `new <repo>` for CP-1 or CP-12), `title`, `labels`, `type`, `parent`, `board`, `board_add`, the whole rendered `comment`, `status` (column name and rank, or `—`), `write_if` (the floor rule, or CP-S2's exact match), `close` (`completed` or `not planned`, set only when the skill's closing conditions hold), `needs_push` (the commits the links need, and the branch), and `note`. A `ranks` item travels inside `outbound`: it includes the `never_write` columns above every SDLC rank, an empty Status is rank 0, and an unmapped column means skip the write, so a caller can never move a card backward.
   - **Caller order:**
     - **Push** the linked commits unchanged. A `git bundle` keeps the SHAs; a re-applied patch breaks the links, but the comment still posts. CP-10 waits until the moved files are on the default branch, by any merge method.
     - **Find or create the issue:** search open and closed issues for the `Dnn` title prefix and link a match before creating; create with title, labels, type and the comment as body in one call, then link the parent sub-issue. Under rule 4, `issue: new` carries candidate repos in `note`, and the caller waits for CD to name one.
     - **Board add, then comment** (skipped when the comment was the new issue's body).
     - **Status:** write only if `write_if` holds, using `ranks`.
     - **Close last:** skip it if the issue is already closed or an earlier entry for the same issue failed; CP-10 waits until the moved files are on the default branch, by any merge method, and closes only after its main-branch links resolve. The `sdlc-archive` fragment's checklist executor gains a headless line: its GitHub rows are earlier entries for the same issue.
   - **Missing links are caught up:** any later headless run whose prompt names the issue writes missing links before its own work, including a restart that skips registration and a lite deliverable's first execute run. The rule lives in the six fragments' activation lines, not in core skill text, so projects without the bundle never see it.
   - A handed-off checkpoint is not a failure: no miss-log entry and no notice; reconciliation sees the gap if the caller drops it. CP-11b never fires headless. The caller may hand checkpoint writes to the run; if it does, CP-11b's offer takes the no path and repo selection rule 4 skips that one checkpoint (listed under `outbound`) rather than stopping the SDLC step, so the never-block invariant holds.
   - **`bundles/github-provenance/fragments/{sdlc-plan,sdlc-lite-plan,sdlc-execute,sdlc-lite-execute,sdlc-handoff,sdlc-archive}.md`:** the activation gate line says that in a headless run each checkpoint does only its local half and hands its GitHub half to the caller as a rendered `outbound` entry, unless the caller hands checkpoints to the run.
   - The first draft simply skipped checkpoints and listed only the CP id and D-number. CD asked for the two changes above, because the factory's writer job doesn't know the checkpoint recipes, so the provenance trail would have gone dark for every headless run. A review of the split found five majors, all fixed before landing: the `ranks` map omitted `never_write` columns (a backward write over the deploy pipeline), creation skipped the `Dnn` duplicate search, nothing wrote the CP-1 links once a caller created the issue, the entry lacked `type`, `board` and `parent`, and CP-10's main-branch links and close were unguarded. Round 2 found no majors; its seven minors were fixed and re-reviewed. Round 3 (the cap) found no critical or major findings, and its four wording minors were applied after the cap without re-review.
8. **`CLAUDE-SDLC.md`** § Use AskUserQuestion for All Questions — A self-contained headless paragraph, matching the mirrored block: detection, subagents, stop and end normally, never guess or self-approve, deferred questions, no path on offers, no actions outside the working tree unless the caller names them, answered questions aren't gates. It points at the process doc.
9. **`process/project-section-markers.md`** § MIRROR Markers — Lists the headless stop rule as a user. New rule 6: prose never spells a live marker. A source doc describes its markers with `{id}`, and a skill never writes the copy-marker form with a file name. The drift check matches marker text, and both forms produced false drift while this change was drafted:
   - `headless-mode.md`'s own Markers paragraph made all 27 copies report drift;
   - `sdlc-develop-skill`'s authoring bullet made that skill report drift.
10. **`skills/sdlc-develop-skill/SKILL.md`**, **`.claude/skills/ccsdlc-create-skill/SKILL.md`** — All-types required sections now include the headless stop-rule block: its marker label form, placement and scope, the fact that no mirror-table row is needed, when a gate gets its own **Headless run:** line (its stop needs stating at the gate: status, payload, a skipped step, or an outward action), and a **Headless restart** paragraph for skills that can be restarted. In a target project the § Integration list is upstream-owned, so `sdlc-develop-skill` proposes the entry upstream instead of editing it. `sdlc-develop-skill` also:
    - CREATE step 1.5 (item 4) and MODIFY M1.5 exempt `MIRROR` blocks from extraction. Without the exemption, its DRY audit would recommend reducing the now-universal block to a pointer.
    - M2 gains a "Inside a `MIRROR` block → source-doc change" row: propose the change upstream, never edit the copy.
    - New red flag: "never asks anything, so the headless block is noise".
11. **`process/skill-agent-review.md`** § Required Sections — Mirrored blocks: the headless stop rule in every skill, and the review-loop block in loop-bearing skills.
12. **`agents/sdlc-reviewer.md`** (`.claude/agents` is a symlink to `../agents`) — The mirrored-block drift check names `headless-mode.md` § Mirrored Stop Rule (which lists every skill) beside the review-loop table.
13. **`.claude/skills/ccsdlc-audit/references/compliance-methodology.md`** — Dimension 10 check 5 names both mirror sources and adds a one-line completeness check: `grep -L 'MIRROR-START: headless-mode.md#headless-stop-rule' skills/*/SKILL.md` must print nothing.
14. **`process/README.md`**, **`skeleton/manifest.json`** — `headless-mode.md` registered: a Shared Behavioral Protocols row, and an entry in `source_files.process`.

**Review:** round 1 ran three `sdlc-reviewer` passes (`sdlc-plan`; `sdlc-lite-plan` + `sdlc-develop-skill`; the two execute skills) and one cross-framework consistency review. There were no critical findings. All majors were fixed:
- the skip-vs-"do not skip any sub-step" contradiction;
- no restart entry in `sdlc-plan`;
- the DISCOVERY-GATE unanswerable headless;
- the lite-execute line citing a triage table lite never produces;
- OpenCode's ask tool tripping the fallback;
- an outward-action ban too narrow, missing live-system changes, egress and subagents;
- no `failed` status;
- unsaved action plans approved by question.

Round 2 (three fresh reviewers) confirmed every round-1 fix and found three new majors, now fixed: (1) a twice-failed FIX had three different outcomes across the docs, one of which let a critical finding be deferred; (2) `sdlc-lite-plan` had no restart entry, so a restarted run would mint a second D-number; (3) both execute skills had no restart entry, so a restarted run could redo finished phases and reset the review round count. Round-2 minors were fixed in the same pass: the `failed` status was added to the mirrored block, reads were allowed explicitly, schema fallback now covers every field, the commit-confirmation rule was settled, the external gate's sanctioned-skip list was updated, the gate-line criterion was stated once, and the § Integration list was completed. Round 3 (two fresh reviewers, the cap) found no critical or major findings. Its ten minors were applied after the cap and checked mechanically, not re-reviewed: twice-failed-FIX qualifiers in `review-fix-loop.md` and `finding-classification.md`; the restart-paragraph scope narrowed to skills whose restart from step 1 would repeat a side effect or lose counted state; `sdlc-plan` records the spec's content hash for the unchanged-since-approval check and splits the FAR, FACTS and review restart cases; `sdlc-lite-execute` restart notes reflect its single step-4 commit; `sdlc-handoff` step 7 commits locally headless. Known open item: the plan → execute hop has no unchanged-since-approval guard for the plan (a design question for the approval row). Pre-existing findings were left alone. These include `sdlc-plan`'s Integration structure, skill length, the `§3c` references, sibling drift between the execute skills, bare paths in `sdlc-develop-skill`, and the Manager Rule copies.

**Not changed:**
- The `code-review-mechanics` and `plan-review-mechanics` blocks still say "escalate to CD via `AskUserQuestion`". The mirrored stop rule and the § Round Cap bullet cover headless runs, and editing those blocks would mean re-copying them into six skills.
- Parking a draft PR at the review cap with `factory:review-capped`, the labels, the markers, the writer-job split and the per-stage output schemas are factory concerns. They stay in quantile until the `factory` bundle.
- No `contract_changes.yaml` entry: the new process doc is a direct copy and the rest are in-place edits, so no migration behavior is needed.
- Neuroloom: no new knowledge-layer references, so this is not a contract change.

**Versioning:** a new cross-skill process convention, so this is a **minor** bump at the next release. No tag was cut.

**Rationale:** The factory is the first caller, but the gap is general. Any unattended run (CI, a scheduled job, `claude -p`) reaches the same gates. Stopping cleanly with a structured result does three things:
- keeps CD's decisions with CD;
- lets a caller tell "needs CD" from "broke";
- gives the next cold run what it needs to continue.

The rule sits in core with a mirrored line in every skill, not only a pointer, because pointer-only guardrails have been skipped before.

---

## 2026-10-06: Unify and bound the review loops — one severity scale, mechanical re-review, critical/major exit bar, 3-round cap

**Origin:** A software-factory and cost evaluation session measured 30 days of Claude Code usage (local transcript token counts to 2026-10-06, priced at API list rates — on the Max plan this is usage limits and waiting time, not dollars). About $16.3k equivalent in total; subagents were 67% (~$10.9k) and 95% of all cost was re-reading context. Review and re-review were ~3,008 of 4,775 subagent dispatches and ~$5.1k — 47% of subagent cost. Median review checkpoint roster 7 reviewers (p90 12, max 15); rounds labelled up to 23 (469 dispatches in rounds 3–5, 224 in rounds 6–10, 183 in round 11+); 60–75% of reviewers reported findings in every round bucket, and hand-sampled late-round reports were nearly all self-described minor. Fable and Codex (GPT-6-Astra, `ultra`) ruled independently on proposed changes (consult record: `docs/current_work/ideas/review-loop-unification_consult-record.md`); CD decided D1–D14 (`docs/current_work/ideas/review-loop-unification_handoff.md`).

**What happened:** The loop had no termination guarantee. The exit bar was zero findings with minors included; the 3-strike rule only fired when the *same* finding category repeated, so a loop surfacing a different minor each round never stopped. Every fix sent the whole roster back ("not just the ones who found issues"), rosters never shrank ("do not remove agents", "When in doubt, include"), and AOP5 right-sizing was cited only by the plan skills. There was also no single severity definition: `finding-classification.md` was planning-shaped (critical = "changes the approach"), the impact × likelihood calibration and the dedup table lived only in `sdlc-review-code`, and `sdlc-create-reference-doc` used its own CRITICAL/HIGH/MEDIUM/LOW scale. History: the 2026-04-14 audit attributed 63% of token cost to review-fix; 2026-05-12 removed `team-review-fix` as underused; 2026-05-19 ("Inline Critical Guardrails Lost in Skill Consolidation") restored inline loop steps after a pointer-only consolidation let `sdlc-review-code` skip the loop and falsely claim it clean — which is why this change keeps the loop steps inline as verbatim mirrored blocks instead of reducing skills to pointers.

**Changes made:**

1. **`process/finding-classification.md`** — Now owns the shared definitions for every review loop. § Severity Levels replaced: impact × likelihood scale (critical = certain/very likely data loss, breach, or complete failure; major = significant, likely to manifest; minor = partial/workaround/cosmetic) moved from `sdlc-review-code`, with a per-context reading of "impact" (software / implementation-as-written / reader). New § Severity Calibration (calibrate before labelling; never a lever for exiting a loop). New § Scope-Change Marker — a `Scope change` yes/no column in the planning-context Classification Table (fix changes the approach, adds/removes files, or changes a phase/agent assignment); plan re-review trigger (1) reads it (D9, D12). New § Finding Deduplication — the four-row merge table moved from `sdlc-review-code` Step 4, applied before classification everywhere. New § Open Minor Findings — table shape, where it lives per context (result doc / Fix Summary / plan file / commit message), only CD closes entries. Context table: stale "Post-commit fix (review-fix)" row retitled to code review fix (`sdlc-review-code`, direct dispatch); reference-doc row added. Kept: FIX Failure Escalation (fails twice → INVESTIGATE/PLAN) and Low-Severity In-Scope Findings (Planning Context).
2. **`process/manager-rule.md`** — § No Unilateral Finding Demotion: listing open minor FIX findings at loop exit, visible to CD, is permitted and not demotion; closing them still requires CD; downgrading severity to meet the exit bar is demotion.
3. **`process/review-fix-loop.md`** — Now owns the loop for every review context. Overview rewritten. Step A: the "do not remove agents… dispatch every single one" rule replaced by the first-round roster rule (code-reviewer + software-architect plus one reviewer per touched domain; "when in doubt" covers domains, not headcount; beyond five each extra agent states what it uniquely adds, AOP5; MTS4 high-risk domains always get their specialist; lenses are never trimmed). Context-separation rule kept, plus **fresh reviewers every round — no reuse** and what re-review prompts carry (prior findings table, fix diff, read current code, look for regressions, a clean report is acceptable). Step B: "Zero means zero" replaced by § Exit Bar. Step C: dedup → calibrate → classify; fix critical and major each round, minors accumulate for one batched pass; a non-mutating **pre-fix snapshot** — a tree hash written through a throwaway copy of the index (`GIT_INDEX_FILE=<tmp> git add -A && git write-tree`), taken again after the fixes — feeds the file-set comparison and the fix diff (verified in a scratch repo: the real index and working tree are untouched, and edits to untracked files are caught; `git stash create` was tried first and rejected because it omits untracked files, so fixes to newly created code or docs would be invisible); FIX failure escalation cross-referenced. Step D: "dispatch ALL agents — not just the ones who found issues" replaced by the mechanical rule (re-run the verification gate; full roster if any applied fix was critical/major or touched files go beyond the findings' files, otherwise raisers + code-reviewer + software-architect scoped to the fix diff; new domain adds its reviewer). Step E: external findings deduplicated and calibrated with internal ones; every internal round they re-open counts toward the cap; the gate's own 2-round cap kept, whichever limit hits first. New § Exit Bar (no critical/major open, no INVESTIGATE/DECIDE unresolved, minors have had their batched pass) and § Round Cap (3 rounds, every round counts; escalate via `AskUserQuestion` with the open-findings table when critical/major remain; exit with Open Minor Findings when only minors remain) — **replaces the 3-strike rule**. New § Plan Review (no verification gate; one revision dispatch per round; re-review fires on the scope-change marker, Files-list change, or phase/agent change — exactly today's cases — and always dispatches the full step-1 roster; an unreviewable round-3 revision escalates). New § Mirrored Critical-Steps Blocks with the two source blocks (`code-review-mechanics`, `plan-review-mechanics`) and the consumer table. § Skill-Specific Variations rebuilt as a per-context table (execution, review-code — whose Step 3 dispatch is round 1 — direct dispatch, plan review, reference-doc review); the stale `sdlc-review-fix` row removed; lite and full run the identical loop.
4. **`process/project-section-markers.md`** — New § MIRROR Markers: `MIRROR-SOURCE-START/END: {id}` in the source doc, `MIRROR-START/END: {doc}.md#{id}` in skills; byte-identical content; exempt from DRY extraction; not migration markers (`sdlc-migrate` matches only the literal `PROJECT-SECTION-*` / `BUNDLE-SECTION-*` names, so mirror blocks pass through as upstream content). Validation section: `sdlc-reviewer` checks mirror blocks against their source.
5. **`skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`** — Inlined loop steps replaced by the mirrored code-review block; Step 0.5, self-applied-fix note, Triage output format, plan contract briefing, and the External Review Gate paragraph kept outside it. Exit announcement now "Review loop complete — no critical or major findings open (N open minor findings listed)"; step 3 is reached under the exit bar; open minors go to the result doc. Flow diagrams redrawn (fresh reviewers per round, dedup/calibrate/classify, cap and escalation branch). Red flags: "ALL means ALL" → "Re-review is mandatory; its roster comes from the mechanical trigger, never judgment"; "Skip re-review, the fixes were small" (lite) rewritten the same way; "One more iteration" now cites the cap; "Build passes" updated; new flags for downgrading severity to exit, claiming clean at the cap, resuming a reviewer, and skipping the verification re-run. No lite-specific rules.
6. **`skills/sdlc-review-code/SKILL.md`** — Step 3 gains the roster-size rule and states its dispatch is review round 1. Step 4's dedup and calibration tables moved to `finding-classification.md`; a short inline step keeps the critical behavior (merge same-location duplicates keeping the highest severity; calibrate before labelling). Report Framing Discipline kept. Fix gate: critical/major first, minors batched. Step 5a self-check counts the findings being fixed this round and records the pre-fix snapshot. Step 5b replaced with the mirrored code-review block (5a's manager-rule guardrails stay inline). Fix Summary shows rounds of 3 and the Open Minor Findings table. Red flags :367 (lenses) and :372 (Tier 2) kept — Tier 2 wording now says a touched-domain Tier 2 agent stays; new flags for headcount padding, judgment-scoped re-review, and claiming clean at the cap.
7. **`skills/sdlc-plan/SKILL.md`, `skills/sdlc-lite-plan/SKILL.md`** — Selection Rule: "When in doubt, include" replaced by coverage-not-headcount wording with AOP5 as a rule (beyond five, a one-sentence unique-contribution statement) and MTS4 specialists; the existing `Consult [sdlc-root]/knowledge/architecture/agent-orchestration-patterns.yaml` lines kept (phrasing contract). Plan review: mirrored plan-review block added; classification now dedups, calibrates on the shared scale, and fills the `Scope change` column; re-review trigger (1) reads `Scope change` instead of `Severity = critical` (triggers (2) and (3) unchanged, full step-1 roster unchanged, no narrow re-review, no re-review for non-scope fixes); revision checklist counts minors and scope-change findings; stopping condition is the exit bar with an Open Minor Findings table appended to the plan; external reviewer's 2-round cap sits inside the 3-round loop cap. Lite-plan flow diagram redrawn to show the trigger and cap. New red flags on severity-vs-scope triggers, the cap, reviewer reuse, and headcount padding.
8. **`skills/sdlc-create-reference-doc/SKILL.md`** — CRITICAL/HIGH/MEDIUM/LOW reviewer format and the "no CRITICAL, HIGH, or MEDIUM" exit replaced by the shared critical/major/minor scale (read as impact on a reader) and the exit bar, used as-is. § 5 Fix Loop carries the mirrored code-review block; the step 4 dispatch is round 1; the standing reviewer for narrow re-review is `code-reviewer` (on every quorum). Open minors are listed in the commit body (commit template updated). Flow diagram and red flags updated.
9. **`process/agent-selection.yaml`** — Selection Process step 7: coverage, not headcount; AOP5 beyond five; MTS4 specialists; lenses are not headcount.
10. **`knowledge/architecture/agent-orchestration-patterns.yaml`** — AOP5: note that review rosters apply it through the Step A roster rule, using the one-sentence test rather than splitting the round. No rule change.
11. **`process/external-review-gate.md`** — Severity vocabulary points at `finding-classification.md`; external findings are deduplicated and calibrated with internal ones; the 2-round gate cap is reconciled with the 3-round loop cap (both apply, whichever first; gate re-entries consume loop rounds) for execution and plan review; the plan-review rubric now defines the three severities for the external model. **`templates/external-review.sh.template`** default-format line defines them too.
12. **`CLAUDE-SDLC.md`** — Direct Dispatch "Review before committing": "dispatch ALL relevant agents… re-review until clean" replaced by a pointer to the loop plus the one-line roster / re-review / exit / cap summary (self-contained for target CLAUDE.md files). Escalation list mentions the review-loop round cap.
13. **`process/README.md`** — `review-fix-loop.md` and `finding-classification.md` rows describe what each now owns; consumer counts corrected to 7.
14. **`templates/result_template.md`, `templates/sdlc_lite_result_template.md`** — New Open Minor Findings section.
15. **`process/discipline_capture.md`, `process/collaboration_model.md`, `process/github-checkpoints.md`, `bundles/github-provenance/fragments/{sdlc-execute,sdlc-lite-execute,sdlc-plan}.md`** — Stale "review-fix" skill row retitled to `sdlc-review-code`; escalations mention the round cap; CP-7 / plan checkpoint wording "loop clean" → "meets its exit bar".
16. **`agents/sdlc-reviewer.md`** (hardlinked to `.claude/agents/sdlc-reviewer.md`) — § Cross-skill DRY: `MIRROR` blocks are exempt from extraction recommendations; new mirrored-block drift check (copy must match the source exactly; a listed consumer with no copy is major).
17. **`.claude/skills/ccsdlc-audit/references/compliance-methodology.md`** — Dimension 10 check 5: mirrored-block drift, with a BSD-safe shell check (verified against all six copies and against a deliberately drifted copy); scoping rule exempting `MIRROR` blocks from extraction recommendations.

18. **Quality gate** — `sdlc-reviewer` dispatched in three parallel passes (execute pair, review-code + reference-doc, plan pair); 0 critical, 10 major, 20 minor, 10 nit in total. The plan pass walked trigger (1)–(3) before and after and confirmed plan re-review fires in exactly the same cases. Applied: the snapshot mechanism change above (reference-doc pass: the doc is a new untracked file); `sdlc-review-code` now emits the Classification Table before fixing (FIX / INVESTIGATE / DECIDE / PRE-EXISTING), runs the full verification gate after fix rounds, and moves a parenthetical `agent-context-map.yaml` instruction into its own sentence (phrasing contract); reference-doc minors get the batched pass before being listed, classification and External-Gate-not-applicable notes added, diagram gains the cap/escalation branch; execute skills' descriptions and round-1 roster now include the standing pair, every round emits the Step A checklist, Step E paragraph carries the gate cap and never-block rule, a round-cap escalation outcome rule, CHECKER-mode re-audits follow the loop rules, Open Minor Findings wired into § 3 / result-doc lists, lite/full red flags aligned, and stale step references fixed (2c→2b, 3c→3d, 3d→3e, 3b→3c, "L143"); plan block now records the pre-revision Files list and phase/agent assignments before the revision dispatch and defines the roster as the round-1 dispatch checklist; `sdlc-plan` diagram gains the re-review/cap loop; lite-plan diagram no longer lets a minors-only round skip the writer; plan checklists say "round N of 3"; `manager-rule.md` allowed-edits list covers the Open Minor Findings table; `sdlc-lite-plan` points at `agent-selection.yaml`; `sdlc-plan` bare `playbooks/README.md` path fixed; Integration/Uses lists include the two process docs. Mirror drift check re-run after every source edit: all six copies identical. Not applied (pre-existing, out of scope): skill body length and the `sdlc-plan` Integration section shape. The gate then ran the new loop on itself. Round 2 sent the full roster, because round 1 had major fixes, and found 0 critical/major and 14 minors. Those 14 went into one batched pass: escalation-outcome wording; `review-fix-loop.md` step qualifiers; CHECKER round counting; lite description; red-flag merge and parity; the `sdlc-plan` diagram gate; AGENT-RECONFIRM limited to round 1; "round-1 roster" naming; review-code's pre-round-1 gate exemption; the Tool Rule link; the per-round checklist; and the `sdlc-reviewer` unresolvable-source rule. The batch also covered `sdlc-develop-skill` and `ccsdlc-create-skill` (item 19). Round 3 sent the narrow roster, since every touched file was named in a finding, and found 0 critical/major, 4 minors and 2 nits. The loop exited at the cap, and these were listed as **Open Minor Findings** for CD. CD then directed fixing all four before the v1.9.0 tag was redone; each row says how it was resolved:

| # | Finding | Location | Why still open |
|---|---------|----------|----------------|
| 1 | When CD directs proceeding past the round cap with majors open, the step 3 precondition and the "Review loop complete — no critical or major findings open" announcement would be false. The skills should say to skip the announcement and record the open findings and CD's direction in the result doc. | `sdlc-execute` / `sdlc-lite-execute` § 2 escalation paragraph | **Resolved:** the escalation paragraph now skips the announcement and records the open findings and CD's direction; step 3's precondition admits the CD-directed path |
| 2 | The `sdlc-plan` diagram's re-review edge loops back to node 5, whose label still says "AGENT-RECONFIRM". Prose says reconfirm is round 1 only. | `sdlc-plan` flow diagram | **Resolved:** node relabelled "AGENT-RECONFIRM (round 1 only) … re-review: frozen roster, no reconfirm" |
| 3 | `sdlc-plan` CHECKER-mode re-audit has no Classification/`Scope change` table, roster, or escalate-at-cap rule. Its trigger is not mechanically evaluable. | `sdlc-plan` CHECKER step 6 | **Resolved:** plan audits classify with the `Scope change` column and record Files/phase-agent state first; re-audits use the full round-1 roster; the cap escalates via `AskUserQuestion` |
| 4 | `sdlc-plan` does not say to re-emit the "Plan review round N of 3" checklist each round. `sdlc-lite-plan` says "copy it". | `sdlc-plan` § 5 Re-review | **Resolved:** both plan skills re-emit the checklist each round with N updated |

A narrow `sdlc-reviewer` check of these fixes found three more minors, all applied. `review-fix-loop.md` § Round Cap now owns the CD-directed-proceed rule: the still-open critical and major findings go in the Open Minor Findings table with their real severity and CD's direction, and `finding-classification.md` and both result templates say so. The plan checklist re-emit drops the external reviewer once its 2-round cap is spent. `sdlc-plan` CHECKER audits deduplicate and calibrate before classifying. Nits: the four skills that quoted a shortened Step A checklist header now quote it verbatim. The "step-1 list" sentence in `sdlc-lite-plan` is kept, because it is correct as a contrast with the dispatched set.

19. **`skills/sdlc-develop-skill/SKILL.md`, `.claude/skills/ccsdlc-create-skill/SKILL.md`** — The orchestration-skill requirement "Review-Fix Loop — reference to review-fix-loop.md" prescribed exactly the pointer-only form this change forbids; it now requires carrying the matching mirrored block verbatim and registering the skill in the mirror table.

**Deliberately kept:** "When in doubt, include" in `sdlc-develop-agent/references/enrichment-methodology.md` (external-content relevance mapping, not reviewer selection) and the other "3-strike" rules (`sdlc-tests-run` test failures, `parallel-dispatch-monitoring.md` dispatch failures, `debate-protocol.md`, `team-communication-protocol.md`, `debugging-methodology.yaml`, AOP debugging checks) are different rules about stuck hypotheses and failed dispatches, not the review loop. Not implemented (raised in the consult, not decided by CD): fixer return contract, stable finding IDs across rounds, whole-file PRE-EXISTING scope qualification, and headless parking/budgets at the cap. No manifest or `contract_changes.yaml` change — no files added, removed, or renamed. Neuroloom `pattern-mapping-rules.md` has no transformation for any changed phrase (`finding-classification`, `review-fix-loop`, severity); new knowledge references use the canonical `Read [sdlc-root]/knowledge/...` form outside parentheses — not a contract change.

**Rationale:** Termination comes from the exit bar and the cap, not from roster trimming alone: the critical/major bar plus three rounds bounds every loop, the mechanical re-review rule (Fable's version — execution reviews run on Sonnet, so no judgment-based scoping) stops whole-roster re-reviews after minor, file-local fixes, and visible Open Minor Findings keep the looser bar honest. One severity scale and one dedup step are prerequisites — a severity-keyed exit bar without shared calibration invites inflation and deflation. Reviewer reuse (D4) and a lighter lite tier (D6) were considered and rejected. Estimated effect ~$1.5–2.5k API-equivalent per month, mostly from rounds 2+ — an estimate, not a measurement. Versioning: **minor** bump (CD decision, 2026-10-06) — the mirrored-block convention and the shared loop contract are new process conventions with no forced migration behavior.

---

## 2026-09-22: sdlc-render becomes sdlc-explain — big pictures, few words `[contract-change]`

**Origin:** CD brought in Thariq Shihipar's (Claude Code team) published practice with artifacts: "use big pictures and few words" typed several times a day, inline SVG in artifacts, artifacts as explainers, "one picture + a hard limit beats three paragraphs of vibe", "show me the diff, not the essay — agents drown in prose", Claude is too verbose by default, and the `/eli5 <topic>` plugin (`anthropics/claude-plugins-community`, `eli5@claude-community`) used for "how does this module work", "why did we make this tradeoff", "what caused this incident". CD asked to fold this into `sdlc-render`, whether render / walkthru / eli5 should be combined, then clarified: the render was built as the reading aid for specs and plans, `sdlc-walkthru` has overtaken that, so the render no longer needs to be faithful — it needs to explain, the way eli5 does. Then: rename it to `sdlc-explain`, and remove any rules and documentation the change makes unnecessary.

**What happened:** A first cut kept three skills (faithful render, walkthrough, a new explainer) sharing one doctrine. CD's clarification collapsed that: with the comprehensive read owned by the walkthrough, a faithful render and an explainer of the same deliverable are the same artifact with different fidelity — and the lossy one is the one people read. So the render *is* the explainer. Merged, renamed, and everything built for the faithful-render era removed: the verbatim content rule, the four-question audience/purpose/emphasis scoping, audience-variant profiles, the per-section slide layout with review checkboxes, tab auto-generation, filter chips, the component-by-component document-type profiles, and the Content Review Deck component in the design system.

**Changes made:**

1. **`skills/sdlc-render/` → `skills/sdlc-explain/SKILL.md`** — Renamed and rewritten as the eli5 explainer. Subject resolution table (deliverable → catalog and document type; module → code; tradeoff → specs/ADRs/knowledge layer/changelog; incident → incident doc and fixing commits), verify-before-draw under the Code Verification Rule with a sources footer, the "one thing" discipline (≤12-word title), storyboard budgets (3–8 pictures, 12 for a many-phase plan; ≤40 words per picture; ≤30 × pictures total, binding; zero paragraphs), a beat → picture-type table, open decisions always get a picture, inline-SVG-only drawing rules, one picture per screen, jargon glossed inside the picture. Post-skill mode uses the document type's storyboard with no Q&A; manual mode has no scoping Q&A either — the only question is a disambiguation. Deliverable explainers still live beside their markdown (staleness conventions unchanged); question explainers go to `docs/current_work/explainers/`. Twelve Red Flags; four validation criteria. Triggers keep `/sdlc-render` and "render the spec/plan" so muscle memory still lands, and add `/eli5`, "eli5", "explain like I'm 5", and explainer-shaped questions.
2. **`process/html-rendering.md`** — Rewritten. Philosophy now says HTML explains, it does not transcribe. New § "Visual Doctrine: Big Pictures, Few Words" (seven rules, credited to Thariq's practice). "Two Categories" are now explainers and exploration artifacts, with a table relating them to the walkthrough. § Post-Skill Offer keeps the opt-in, precedes-approval, and walkthrough-as-peer rules and the skill → storyboard table. § Document-Type Storyboards replaces the component-by-component profiles: one row per type with its default beats. Removed: Layout Modes, Review Checkboxes, Tab Auto-Generation, Filter Chips, Audience Variants, Manual Render scoping, and the verbatim content rules. Staleness and sharing kept, trimmed.
3. **Ten post-write offer points** (`sdlc-plan` ×2, `sdlc-lite-plan`, `sdlc-execute`, `sdlc-lite-execute`, `sdlc-idea`, `sdlc-handoff`, `sdlc-audit`, `sdlc-create-reference-doc`, `sdlc-debug-incident`; `sdlc-review-code`'s two-line variant) — Each carried a near-verbatim paragraph re-describing how to render. Replaced with one line: offer an explainer (`sdlc-explain`, named storyboard) or a walkthrough, never unprompted, mechanics in the process doc. "Render precedes approval" wording in `sdlc-plan` / `sdlc-lite-plan` (steps and Red Flags) now says explainer.
4. **`skills/sdlc-walkthru/SKILL.md`** — Step 4 routes by shape of the question: *see* one mechanism → `sdlc-explain`; *manipulate* it → an exploration artifact. Description, Complements, Does NOT replace, and Red Flags reference the explainer instead of the render.
5. **`templates/html-design-system.html`** — Removed the Content Review Deck (section 21): its CSS, print rules, TOC entry, demo markup, and the localStorage review-state script. The presentation Slide Deck (section 20) stays — it is the explainer's optional one-picture-per-screen stepper. Footer attribution updated.
6. **`CLAUDE-SDLC.md`** — The post-write rule now offers explainer or walkthrough, and a second paragraph states the visual doctrine and `/eli5`.
7. **`process/commands.md`** — `/sdlc-render` row replaced by `/sdlc-explain <subject>` / `/eli5 <subject>`; walkthru row calls it the explainer's peer.
8. **`skeleton/manifest.json`** — `skills/sdlc-render/SKILL.md` → `skills/sdlc-explain/SKILL.md`.
9. **`skeleton/contract_changes.yaml`** — Entry `0015`, `rename_skill` `sdlc-render` → `sdlc-explain`, with notes on the offer-paragraph rewrite and the design-system removal.
10. **Quality gate** — `sdlc-reviewer` dispatched on the rewritten skill, then across the whole change set (three parallel passes on the two rendering skills, the ten lifecycle skills, and the process-doc wiring). Second round applied: a leftover "Render precedes approval" paragraph deleted from `sdlc-plan`; `sdlc-review-code` and `sdlc-audit` codebase-health mode now offer the walkthrough alongside the explainer; the stale "tabs and collapsibles only" clause in `sdlc-idea` / `sdlc-plan` exploration-artifact provisions replaced with the explainer's static, stepper-only rule; one missed "render" noun in `sdlc-walkthru`; `§ Post-Skill Offer` casing normalized across all pointers; two Key References descriptions in `CLAUDE-SDLC.md`. First round on the skill (4 minor findings, all applied): "render" as a noun replaced by "explainer" throughout the body (the `/sdlc-render` and "render the spec/plan" triggers stay, deliberately); a garbled § Sharing cross-reference fixed; the Visual Doctrine section trimmed to a pointer so it matches the DRY-notes claim; the Code Verification Rule no longer re-described inline.

**Rationale:** Prose is where the human in the loop becomes the bottleneck; a picture with a hard limit is how they stay in the loop without reading everything. Once the walkthrough owns "nothing load-bearing omitted", a second HTML view that also tries to keep everything is dead weight — and the machinery built to make a faithful render reviewable (slide decks, review checkboxes, audience scoping) is dead weight with it. The community plugin's three-line prompt is preserved as the skill's spine; cc-sdlc adds grounding (verify before draw, cite sources, always draw the open decisions) so that a lossy picture is never a false one. Versioning: a skill rename is a breaking contract change → **major** bump when CD next tags.

---

## 2026-09-02: sdlc-reviewer quality-gate fixes for the two new skills

**Origin:** `sdlc-reviewer` dispatched on both skills added today (`sdlc-manage-github`, `sdlc-walkthru`) per the new-skill quality gate. Eight findings total; six applied, two declined with rationale.

**Changes made:**

1. **`skills/sdlc-manage-github/SKILL.md`** — 8 bare `github-checkpoints.md` references expanded to `[sdlc-root]/process/github-checkpoints.md` (path-variable rule); recipe headers renamed `### Recipe N:` to disambiguate from the Steps numbering; Integration gains the board-roles-vs-catalog-statuses relationship (roles are a deliberate per-project taxonomy; the catalog stays canonical) and documents why the recipes stay inline rather than in `references/` (an extra read-hop is skippable indirection under the directive-inlining convention — declining the extraction suggestion).
2. **`skills/sdlc-walkthru/SKILL.md`** — `AskUserQuestion` gate question now cites `[sdlc-root]/process/collaboration_model.md` § Tool Rule; the Code Verification Rule citation names its home (project CLAUDE.md); the Manager Rule section names the dispatch mechanism. Declined: renaming `walkthru` → `walkthrough` — the contraction matches the trigger phrases and the originating project's installed skill name, which keeps migration continuity.

**Rationale:** The quality gate exists precisely for ported content — both declined findings are deliberate design choices now documented in place, so the next reviewer reads a decision instead of re-flagging a gap.

---

## 2026-09-02: Adopt sdlc-walkthru from paire-appetit — guided artifact walkthroughs as the render's peer

**Origin:** paire-appetit built `sdlc-walkthru` as a comprehension-first alternative to the HTML render: an SDLC artifact delivered as a paced, part-by-part guided tour — CD paces with "next", questions are answered against verified code, and feedback is classified and dispatched to revision agents mid-flight. Its first use surfaced three material spec corrections a static read had missed. Fully generic apart from two project references, so it upstreams as a core skill (not a bundle — no external dependencies).

**Changes made:**

1. **`skills/sdlc-walkthru/SKILL.md`** — New core skill, ported near-verbatim: preflight segmentation by story (4–7 parts, chaptered past ~8), the pacing contract, part-delivery rules (≤350 words, lead with the claim, one part per turn), verify-then-answer for questions, feedback classification via the invoking skill's revision protocol (SPEC-REVISION et al.), wrap-up-before-gate. Generalized: the project-specific principles reference now consults `[sdlc-root]/knowledge/agent-context-map.yaml`; paire's terminology example dropped.
2. **`process/html-rendering.md`** — § Post-skill render offer: the walkthrough is the render's peer at every offer point — skills offer both consumption modes; whichever CD picks resolves before any approval question. (This closes the follow-up paire's own Integration note recorded as not-yet-done.)
3. **`CLAUDE-SDLC.md`** — Post-write render-offer paragraph updated to offer the walkthrough alongside the render.
4. **`skeleton/manifest.json`** — `skills/sdlc-walkthru/SKILL.md` added to `source_files.skills`.
5. **`process/commands.md`** — `/sdlc-walkthru` row.

**Rationale:** A document's job is durability; a decision-maker's job is judgment. The walkthrough serves the approval gates the render already serves, with a different consumption mode — and it demonstrably surfaces corrections a static read misses. New installs get it via the normal file copy; existing installs receive it on next migration as an ordinary new framework skill.

---

## 2026-09-02: Unbuilt-Capability Rule, launch-recipe skill convention, additive-contract versioning

**Origin:** Three adoptions from reviewing paire-appetit's recent evolution alongside this session's own decisions. (1) Paire's newest CLAUDE.md rule (their commit of 2026-09-02): a session investigated only the exposed application layer, concluded a leadership-requested capability "does not exist," and cut the language unilaterally — when the underlying data actually supported building it. (2) Paire's project-local `verify` skill — a build/launch recipe with accumulated environment gotchas — is a pattern worth naming upstream even though its content is project-specific. (3) CD decision on versioning for this release.

**Changes made:**

1. **`CLAUDE-SDLC.md`** — New § Unbuilt-Capability Rule: Ask, Don't Silently Cut (generalized from paire's). "Not found in the codebase" is a reason to ask, never to unilaterally cut or soften a stakeholder's request: check the underlying data (not just the application layer), ask via `AskUserQuestion` with what exists vs. what would need building, and never present a cut as a fait accompli — doubly so for leadership requests, whose phrasing may be deliberately illustrative.
2. **`process/verify-command.md`** — New § Companion: the Project Launch-Recipe Skill: the convention of a project-local `.claude/skills/verify/` skill capturing launch commands, end-to-end drive instructions, and accumulated environment gotchas; seeded on first rediscovery, grown per gotcha. The framework defines the convention; the content stays project-specific.
3. **`CLAUDE.md`** (source repo) — Versioning refinement (CD decision, 2026-09-02): purely additive `contract_changes.yaml` entries — opt-in bundle debuts, manifest field additions with back-fill defaults — are **minor**, not major; major is reserved for entries that force behavior change on existing installs.

**Rationale:** (1) is a judgment-boundary rule that generalizes cleanly: codebase absence ≠ infeasibility, and the requester owns the call. (2) names a pattern the built-in `run` behavior already looks for, so projects stop rediscovering their own launch procedure. (3) keeps major bumps meaningful — a convention no project is forced to adopt should not signal breakage.

---

## 2026-09-02: Debut github-provenance bundle (upstreamed from paire-appetit D52)

**Origin:** paire-appetit built a full GitHub provenance convention as their D52 — every tracked deliverable narrated into a GitHub issue via lifecycle checkpoints (CP-1…CP-12 + CP-S1/S2), with Projects v2 board tracking under a forward-only floor rule, a never-block invariant, SHA-pinned artifact links, and a read-only reconciliation audit dimension. It was live-verified against real boards (their Phase 6), which among other things discovered that GitHub accepts a wrong board's option ID silently — making name-then-resolve-per-session the only guard against silent mis-writes. This entry generalizes and upstreams the whole convention as an opt-in bundle. Design cross-checked via the external review gate (Codex, 18 findings triaged): config survives migration via a PROJECT-SECTION-wrapped config block, "configured" is machine-defined (`enabled: true` set last in Enablement), issues-only mode (`board: none`) supported, label provisioning and preflight in Enablement, predecessor detection at the migrate offer.

**Changes made:**

1. **`process/github-checkpoints.md`** — New policy doc (bundle-delivered). Owns the checkpoint map, column **roles** (`registered`/`spec-approved`/`executing`/`stakeholder-blocked`/`validated`/`staged`) mapped to per-project names/ranks in a `PROJECT-SECTION`-wrapped config block, the floor rule + CP-S2 exact-match exception, never-block + miss-log, catalog-wins + reconciliation cutoff, never-reopen, repo selection (single-repo first), labels (universal + project-defined conditionals), pre-deliverable `Parked:` promotion path, SHA-pinned links, commit conventions, call budgets with two exemptions, terminology + content prohibitions (config-extensible), all comment templates, failure classes, checkpoint confirmation carve-out, and the six recipe names. § Activation defines the two-stage gate (installed + `enabled: true`); § Enablement is the guided setup (preflight, board column verification, label provisioning, miss-log gitignore, cutoff, `enabled: true` last).
2. **`skills/sdlc-manage-github/SKILL.md`** — New skill (bundle-delivered). Interactive `gh` procedures for Projects v2 boards/issues (the github MCP tools 404 on board items), plus § SDLC Checkpoint Recipes: `create-or-link` (idempotent by `Dnn` prefix, `registration`/`parked` modes, promotion path, idempotent board add), `resolve-and-write-status` (role→name→ID per session, floor rule, CP-S2 flag, NEVER-WRITE hard guard, no-op in issues-only mode), `link-sub-issue`, `commit-and-push-artifact` (pathspec-only, rebase-once, SHA re-capture), `log-miss` (atomic JSONL append), shared failure-class→action lookup, and the verified cross-board option-ID hazard note.
3. **`bundles/github-provenance/fragments/*.md`** — Eight fragments injected as `BUNDLE-SECTION` blocks: checkpoint ownership sections for `sdlc-plan` (CP-1/2/3, S-pair), `sdlc-lite-plan` (CP-1/3, S-pair — no spec gate), `sdlc-execute` (CP-4–9, S-pair), `sdlc-lite-execute` (CP-4/5/7/8, S-pair — no CP-6/9), `sdlc-handoff` (CP-11/11b), `sdlc-archive` (CP-10 two-part, CP-12, parked closure, archive-time checklist executor); a Dimension 10 dispatch hook for `sdlc-audit`; and the full § GitHub Provenance Reconciliation (10a–10j) for `sdlc-compliance-auditor`. Every fragment opens with the activation gate and inlines the DIRECTIVE-level rules (never-block, comment-before-Status, the CP-3/CP-6 trap notes) while reading DATA (templates, ranks) from the policy doc.
4. **`skeleton/manifest.json`** — `bundles.github-provenance` registered with `skills`, `process`, and `fragments`.
5. **`skeleton/contract_changes.yaml`** — Entry 0014 (`bundle_debut`) with predecessor-detection notes for hand-rolled installs (paire-appetit itself: adopt-preserving-config, retire hand-wrapped equivalents on their next migration); bundle_debut type comment updated for the extended shape.
6. **`process/commands.md`** — `/sdlc-manage-github` row (marked as bundle-delivered).
7. **`CLAUDE.md`** (source repo) — `bundles/` row in the structure table; consistency-check globs and manifest comparison extended to bundle entries.
8. **Post-D52 refinement sync** — paire evolved the convention after the initial port was drafted (their commits of 2026-08-14…24, pulled mid-session); all four refinements are folded in: closed label taxonomy with the **silent label auto-creation** hazard (the REST create never fails on an unknown label — replaces the obsolete unknown-label retry fallback), § Issue Types (`Bug`/`Feature`/`Task` set on the same REST create call, `gh issue create` has no type flag; type silently dropped without push access → audit is the detector), § Board Fields: Ownership (human-owned fields incl. the Test Verdict example, the assignees convention, and the deliberate absence of estimate fields), the follow-up-issues-start-at-`registered` rule (with the originating project's 17-misfiled-issues incident), the completion-lives-in-comments rule (policy + skill + Red Flags — bodies go stale; CP-9–12 outcomes are comments), the full-read-before-classify triage rule, audit 10h upgraded from label presence to **taxonomy parity** (extra labels are drift; untyped open issues; stale column-scoped verdicts, report-only), and paire's create-or-link step-numbering fix ("skip to step 4 — step 3 is creation-only").
9. **External implementation review fixes (Codex, second pass — on the diff, not the plan)** — bundle-detection fallback restricted to skill paths so a hand-rolled `github-checkpoints.md` routes through §4.7 predecessor detection instead of being auto-marked installed; fragment injection extended to the content-merge flow (§2.2–§2.4 — most fragment targets are content-merged skills, not direct-copied files) in both `sdlc-migrate` and the marker doc; `installed_files` drift baselines explicitly include bundle-installed files (initialize + migrate back-fill); `create-or-link` step 4 now explicitly writes the `registered` option after a fresh board add (a new item is otherwise column-less) and states the comment-before-Status ordering on the link path; mechanical cautions added for `content.repository` shape and pagination-at-the-limit (recipe + audit dimension); the audit-skill fragment states outright that "all 9 dimensions" language is superseded when the dimension is active.

**Rationale:** The provenance layer makes SDLC work legible to people who will never open the markdown vault, without the issue ever becoming a second source of truth — the catalog stays canonical, the board is a projection corrected forward-only, and a checkpoint can never stall the work it narrates. Shipping it as a fragment-carrying bundle keeps core skills clean for the majority of projects that will not enable it, while adopters get the full DIRECTIVE-inlined sections and every future policy improvement on migration. The role indirection (`registered`…`staged`) keeps the checkpoint map stable across projects whose boards name columns differently, and `board: none` gives issue-only projects the narrative without Projects v2.

---

## 2026-09-02: Bundle fragment injection (BUNDLE-SECTION) and bundle process files

**Origin:** Upstream adoption of paire-appetit's GitHub provenance convention (their D52). The convention needs ~40–50-line checkpoint sections inside six core lifecycle skills plus an auditor dimension — content that must not ship as dormant dead weight to projects that decline the bundle, and must not freeze at install time the way hand-wrapped `PROJECT-SECTION` blocks do. Design cross-checked via the external review gate (Codex), which drove the idempotency, ordering, offline-validation, and predecessor-detection requirements. This is Phase 1 (mechanism); the `github-provenance` bundle itself is Phase 2.

**Changes made:**

1. **`process/project-section-markers.md`** — New § BUNDLE-SECTION Markers: upstream-owned sibling of `PROJECT-SECTION`. Labels namespaced `bundle/fragment`; declared in `manifest.bundles.<name>.fragments` (fragment source file → target framework file); injection is strip-then-append (idempotent), alphabetical bundle order, no nesting; hand-edits inside markers are lost on migration by design; presence must match `installed_bundles`/`bundle_fragments`; injection counts as a file write for adapter `post-file-write`. Installer ordering rule: copy files → inject fragments → record in manifest last (crash under-claims, re-run repairs). Direct-copy flow and Validation sections updated to match.
2. **`skeleton/manifest.json`** — `bundles._comment` documents the extended schema: optional `process` and `fragments` fields alongside `skills`. (Also normalized a stray-indent directory entry.)
3. **`skills/sdlc-initialize/SKILL.md`** — Phase 1b bundle offer lists process docs and fragment targets; effective install set includes bundle `process` files; fragment injection step after all copies; `installed_bundles`/`bundle_fragments` written only after files + fragments land; Enablement-section offer for bundles that need per-project configuration. Manifest schema example and field docs gain `bundle_fragments`.
4. **`skills/sdlc-migrate/SKILL.md`** — §2.0a: effective process list, file-existence fallback covers bundle process paths, fragments-are-refreshed rule. §2.1 marker preservation: new step 7 injects current fragments from source at `[target_tag]` after PROJECT-SECTION re-injection. §4.5: new step 4a maintains `bundle_fragments` (add injected, drop upstream-removed). §4.7: offer lists process/fragment surface; predecessor detection for bundles whose `process` paths already exist in the project (adopt-preserving-config vs. skip); accept path copies process files, injects fragments, records manifest entries last, offers Enablement.
5. **`agents/sdlc-compliance-auditor.md`** — Dimension 7 marker validation extended: `BUNDLE-SECTION` pairing, orphaned-bundle-content check against `installed_bundles`, partial-install check against `bundle_fragments`, nesting with `PROJECT-SECTION` is critical.
6. **`skeleton/contract_changes.yaml`** — Entry 0013 (`manifest_field_added`, `bundle_fragments`, default `{}`) documenting the schema extension and the adapter posture.

**Rationale:** Bundles could previously carry only whole skills, so any bundle needing hooks inside core framework files had two bad options: dormant sections shipped to everyone (recurring context cost in every downstream invocation, forever) or project-local `PROJECT-SECTION` blocks (frozen at install, silently staling as upstream evolves — the exact failure paire's hand-wrapped Dimension 10 block exhibits). Fragment injection gives bundles a third path: core files stay clean upstream, hooks exist only where the bundle is installed, and hooks refresh from source on every migration because migration overwrites with a clean upstream copy and re-appends the current fragment — no merging, ever. The mechanism is general-purpose: any future bundle (testing infrastructure, incident extensions) rides the same rails.

---

## 2026-07-21: 6n guard check verifies effective enforcement, not presence; versioning convention recorded

**Origin:** Sleeved D121 field report (via inter-session, evidence in Sleeved ADR-15 and the D121 result doc): their `zustand-selector-missing-useshallow` guard shipped with the rule set to `off` behind a stale justification comment — both 6n's "guard exists" check and their local wiring script read it as fully wired, because presence-in-config was checked but not effective enforcement. Related sub-gap: conditional-registration wrappers (`plugin.rules["x"] ? {...} : {}`) defeat text-grep wiring checks the same way. Caught only by a completion review. Sleeved correctly declined a local patch (framework owns check design) and fed it upstream.

**Changes made:**

1. **`process/guardrail-lifecycle.md`** — Freshness check 1 renamed "Guard exists and enforces": parse effective severity (`off` = CRITICAL, same as missing; `warn` = WARNING unless `notes` documents advisory intent), evaluate conditional registration for runtime collapse, skipped tests and continue-on-error CI steps count as not enforcing, known-bad-sample fallback when static reading is inconclusive. `location` spec and new Red Flag ("presence ≠ enforcement") updated to match.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — 6n check 1 extended identically.
3. **`CLAUDE.md`** — Versioning convention recorded (CD decision, v1.7.0/v1.7.1): minor for new contract surface (new cross-skill contracts, command surface, downstream data schema); patch for iterations, fixes, and check strengthening within existing contracts.

**Rationale:** The first field deployment of 6n produced a guard that passed the freshness check while enforcing nothing — the exact failure 6n exists to catch. One fix (read effective enforcement from config semantics, not string presence) closes both the severity blind spot and the conditional-wrapper gap.

---

## 2026-07-20: Review-time mechanization-threshold trigger in sdlc-review-code

**Origin:** Sleeved D121 (CD-approved, via inter-session): per-review pattern logging and audit-cadence triage were only connected by the next audit happening to run — a cluster could cross the mechanization threshold and sit unproposed for weeks.

**Changes made:**

1. **`skills/sdlc-review-code/SKILL.md`** — Step 6d: when logging brings a `promoted: false`, non-guarded cluster to 3+ occurrences within Dimension 6l's 30-day window (6l's threshold definition reused verbatim, not redefined), emit "Pattern {slug} crossed the mechanization threshold ({N} occurrences) — run `/sdlc-audit` to triage mechanization." Skips `mechanization_assessed: excluded` clusters. Nudge only — no triage or field-writing from within the review skill.

**Rationale:** Threshold crossings now surface in the same review that causes them, while the decision itself stays at audit triage where CD gates it.

---

## 2026-07-20: Guardrail exclusion marker — "assessed, deliberately not mechanized, do not re-propose"

**Origin:** Inter-session report from Sleeved's D121 reconciliation against the just-landed `guardrail-lifecycle.md` — first downstream contact with the contract found a gap: a cluster clearing the 3+ threshold whose manifestations are heterogeneous (would need a semantic allowlist that doesn't exist). CD chose exclusion, but the contract had no way to record it, so 6l and reflect would re-propose every cycle and CD would re-dismiss forever.

**What happened:** Sleeved adopted local fields `mechanization_assessed: excluded` + `mechanization_reason`; upstream adopts the same names verbatim so the local data becomes canonical on next migration.

**Changes made:**

1. **`process/guardrail-lifecycle.md`** — New § "Assessed and Excluded — Do Not Re-Propose": field schema, semantics (set only at triage; exclude ≠ defer; guards only — knowledge promotion unaffected; reversible at triage; new occurrences accumulate info-tier but never auto-reopen). Red Flag row for the re-propose nag.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — 6l.1 validates the fields; 6l.2 skips excluded clusters from guard-candidate output, lists them info-tier with reasons; output format shows the excluded section; triage note distinguishes decline-with-exclusion from defer.
3. **`skills/sdlc-reflect/SKILL.md`** — Step 4b skips excluded clusters.
4. **`skills/sdlc-review-code/SKILL.md`** — Step 6 optional-fields note covers the exclusion fields (don't strip them when appending occurrences).

**Rationale:** A promotion pipeline that cannot record "no, and stop asking" trains CD to ignore its proposals. Exclusion keeps the decision durable, audit-visible (info-tier listing, never hidden), and reversible — without turning every dismissal into a permanent burial. Additive only; no reference-pattern changes, no `[contract-change]`.

---

## 2026-07-20: Guardrail lifecycle, KEEP-IN-SYNC lens, codebase-health audit mode, verify-command convention (Sleeved upstream contributions)

**Origin:** Cross-repo handoff from Sleeved (`docs/current_work/ideas/cc-sdlc-upstream-contributions_handoff.md`, sourced from Sleeved's 2026-07-17 repo-wide quality audit). Four framework-shaped improvements identified downstream that would be clobbered by `sdlc-migrate` if implemented there.

**What happened:** Sleeved's `recurring-patterns.yaml` accumulated ~40 pattern clusters, several recurring for months because nothing converts a recurring pattern into a mechanized guard (lint rule, drift test, CI check) — and nothing re-evaluates guards once created. Separately: the `manually-synced-parallel-copies-drift` pattern hit 5 occurrences (copies diverging in the very commit adding the "keep in sync" comment); the audit's product-substrate sweeps proved a generic recipe worth a first-class audit mode; and the top agent-ergonomics gap was the absence of a discoverable one-shot verify command.

**Changes made:**

1. **`process/guardrail-lifecycle.md`** (new) — The cross-skill guardrail contract: LOG → THRESHOLD → PROMOTE → ENFORCE → RE-EVALUATE → MODIFY/RETIRE. Defines the `mechanized_guard` field on recurring-pattern clusters, mechanizability criteria (textual/structural/behavioral signatures), guard-freshness checks, the guard-modification-in-scope rule, and enforcement floors. Framework defines the loop; projects supply the actual rules/tests.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — 6l extended: validates optional `knowledge_entry`/`mechanized_guard` fields, flags guard-promotion candidates (mechanizable patterns at threshold) alongside knowledge-promotion candidates; triage promotion note covers the guard path. New **6n Mechanized Guard Freshness**: guard-exists, recurred-despite-guard, suppression-growth, never-fired checks.
3. **`skills/sdlc-audit/SKILL.md`** — Four modes (was three): new **Codebase Health mode** auditing the product substrate via three parallel read-only sweeps (test/CI activation, agentic ergonomics, observability blind spots) with SCOPE → SWEEP → SYNTHESIZE → ROUTE workflow; report to `docs/current_work/audits/`, gaps route to handoffs/plans/parking lots, never fixed in-mode. Dimension 6 summary, triage section (guard promotions + 6n findings), Red Flags, Integration, and frontmatter triggers updated.
4. **`skills/sdlc-audit/references/codebase-health.md`** (new) — Full health-mode methodology: dispatch discipline, the three sweep prompts, report format, merged top-gap ranking (cap 10), routing rules, recurring-pattern cross-referencing.
5. **`skills/sdlc-review-code/SKILL.md`** — Step 6 documents the post-promotion `knowledge_entry`/`mechanized_guard` fields and flags "recurred despite guard" in the patterns table; Step 5a adds the two-part guard-modification-in-scope rule; Integration references the lifecycle doc.
6. **`process/review-fix-loop.md`** — Step C: FIX findings matching a guarded (or plainly guardable) recurring-pattern cluster get two-part fixes — instance + guard — consumed by all execution skills.
7. **`skills/sdlc-reflect/SKILL.md`** — New Step 4b: session-scoped recurring-pattern guard scan (reuses 6l thresholds, no redefinition) proposing guard promotions and flagging recurred-despite-guard; report section, Red Flag ("reflect proposes, triage decides"), Integration updated.
8. **`process/review-lenses.md`** — Contract Safety Lens: manually-synced parallel copies bullet — a KEEP-IN-SYNC comment is itself a defect; require single source of truth or a drift-detection test; grep-based CI floor sanctioned.
9. **`process/verify-command.md`** (new) — The one-shot root `verify` command convention: chains the gates CI runs, documented in CLAUDE.md, invoked by the review-fix loop's verification gate.
10. **`skills/sdlc-initialize/SKILL.md`** — New Phase 9b: check for the verify command, offer scaffolding (chain what exists, report gaps, don't invent tooling); Phase 10 checklist line added.
11. **`agents/sdlc-compliance-auditor.md`** — Dimension 6 summary mentions 6l recurrence and 6n guard freshness.
12. **`process/commands.md`** — `/sdlc-audit health [scope]` row.
13. **`skeleton/manifest.json`** — Added `process/guardrail-lifecycle.md`, `process/verify-command.md`, `skills/sdlc-audit/references/codebase-health.md`.

**Rationale:** Review-pattern logging existed (review-code Step 6) and knowledge promotion existed (audit 6l), but the loop dead-ended at "agents were told" — nothing made the *machine* catch a recurring pattern, and nothing watched guards after creation. This closes the loop end-to-end with explicit ownership: review-code logs, reflect and 6l propose, CD decides at triage, projects implement, 6n re-evaluates, review loops maintain. The KEEP-IN-SYNC lens and verify-command convention are the two cheapest universal wins from Sleeved's evidence; the health mode generalizes an audit recipe already validated against a real repo. No knowledge-layer reference patterns were changed — all new references use canonical phrasing, so no `[contract-change]` tag is needed.

---

## 2026-07-19: Frontier once-over made unconditional for all promotion candidates

**Origin:** CD directive — promotion candidates should never be validated by shipped-deliverable evidence alone; every candidate must be reviewed by a frontier-tier agent (Codex external wrapper at xhigh, or Fable subagent) before reaching CD.

**What happened:** The Promotion Verification Gate had a skip path: a single well-evidenced entry (direct deliverable evidence, batch < 3) bypassed the judge panel entirely and went straight to CD. That entry never received any independent model review — inconsistent with the gate's own rationale, since deliverable recurrence proves a pattern was used, not that its embedded factual claims are true, and the compounding risk of a wrongly promoted entry applies equally to skip-path entries.

**Changes made:**

1. **`process/discipline_capture.md`** — Skip path narrowed: single well-evidenced entries may skip the screening panel (steps 2–4) but not the frontier once-over (step 5); the neutral payload is built for them and the once-over verdict accompanies the CD presentation. Step 5 restated as unconditional for every promotion candidate, including screening-skip entries.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — §6c evidence-production note and step 11a gate description updated to match: the once-over is unconditional; deliverable evidence alone never carries a candidate to CD without an independent frontier-tier fact-check.

**Rationale:** The once-over machinery already exists and runs as a single batch dispatch, so extending it to skip-path entries costs almost nothing while closing the only route by which a promotion candidate could become knowledge-store precedent with zero independent model review. Frontier budget stays concentrated at promotion time, where the risk asymmetry justifies it — parking-lot triage of non-candidates remains cheap.

---

## 2026-07-18: Standard external-review wrapper templates; drop "different model family" from model-facing prompts

**Origin:** CD follow-up to the 2026-07-17 planning integration: "we don't need to say 'from a different model family'. also, we can adopt a standard template from ~/Projects/neuroloom."

**What happened:** The gate doc's example wrappers were toy inline sketches, while the Neuroloom installation had a production-hardened wrapper pair (stdin passthrough to dodge ARG_MAX, `-o` final-message capture so codex noise never reaches the findings contract, `--sandbox read-only --ephemeral`, stderr egress disclosure, mktemp/trap cleanup, and empty-output-is-failure handling in the knowledge judge). The planning payload rubrics also told the external model it was "from a different model family" — unnecessary framing in model-facing text (the cross-family rationale belongs in the docs, not the prompt).

**Changes made:**

1. **`templates/external-review.sh.template`** (new) — Codex-backed standard wrapper adopted from the Neuroloom installation, with the embedded prompt generalized to payload-neutral: it defers to the payload's rubric header for artifact, task, and output format, so the one wrapper serves diff review, plan review, and approach consults.
2. **`templates/external-review-knowledge.sh.template`** (new) — Neuroloom's knowledge-judgment wrapper adopted as-is (paths converted to `[sdlc-root]`), including its contract difference: empty stdout exits non-zero so the Promotion Verification Gate falls back to an internal subagent judge.
3. **`process/external-review-gate.md`** — "Example wrappers" replaced by "Standard template": documents the shipped template, its operational details, and enable-by-copy instructions; the local-Ollama variant stays as the sensitive-codebase alternative. Wrapper-contract bullet updated from "cc-sdlc ships no default wrapper" to the template + copy/chmod stance. Knowledge-judgment section's inline example replaced with a pointer to its template. Removed "from a different model family" from the Codex example prompt and both planning payload rubrics.
4. **`skeleton/manifest.json`** — Both templates added to `source_files.templates`; `_templates_note` updated (non-.md template files install too; `*.sh.template` files are inert until a project copies and chmods them — the gate activates on the executable copy, never the template).
5. **`skills/sdlc-migrate/SKILL.md`** — Template copy rules widened from `templates/*.md` to all manifest-listed template files, with an explicit guard: never copy a `*.sh.template` onto the executable wrapper path, and never overwrite a project's enabled `external-review*.sh` (project-authored).
6. **`process/path-mappings.md`** — `templates/*.md` row generalized to manifest-listed template files.
7. **`CLAUDE-SDLC.md`** — Gate paragraph now names the shipped templates and the copy + chmod enable path.

**Rationale:** A production-tested wrapper encodes half a dozen non-obvious operational lessons; shipping it as a template means the next project enables the gate in one copy instead of rediscovering ARG_MAX limits and codex stdout noise. Keeping templates inert (`.sh.template`, non-executable, in `templates/`) preserves the gate's activation semantics — presence of the executable wrapper remains the project's explicit egress opt-in. And prompts sent to the external model should carry task instructions, not meta-commentary about the ensemble's composition.

---

## 2026-07-17: External reviewer becomes a first-class planning participant

**Origin:** CD directive — "integrate our external reviewer into planning as well. It should be more of a first-class resident in the SDLC if it is configured… deliberation between models is much stronger when they're of different families."

**What happened:** The External Review Gate participated only at execution time (post-internal-loop diff review) and knowledge promotion. Planning — where decisions are structural and cross-family disagreement is most valuable — had no external participation. The gate was also framed as "opt-in per run," leaving configured projects under-using a capability they had already paid to set up.

**Changes made:**

1. **`process/external-review-gate.md`** — Reframed intro as a lifecycle-wide participant with a three-point integration table (planning / execution / knowledge promotion). Added a "First-class once configured" presence policy: enabling is opt-in via wrapper presence, but once configured, participation is the default at every integration point, with named skip conditions the only sanctioned skips. Added § Planning Integration defining (1) the approach deliberation consult (payload, `RECOMMEND \| <approach> \| reason` output line, advisory-only, frontier/`xhigh`) and (2) the plan review ensemble member (spec+plan payload, `SEVERITY \| artifact § section \| finding` output, same classification table, `[external:<model>]` attribution, 2-round cap, mid-tier/`high` default). Generalized the wrapper contract so the payload rubric header owns task framing and output format (wrapper is transport; old-contract wrappers keep working via the default format); updated both example wrappers to be payload-neutral. Updated "When to run it" with per-point skip conditions and the planning invocation sites.
2. **`skills/sdlc-plan/SKILL.md`** — Step 3d: added `External consult:` line to the APPROACH-DECISION block and the external deliberation consult procedure (run before selecting when approaches are compared; on disagreement present both positions to CD via AskUserQuestion). Step 5: external reviewer added to the review dispatch checklist and roster (same round as domain agents), findings attributed `[external:<model>]` in the classification table, re-review participation capped at 2 rounds, Domain Agent Reviews attribution rule extended. Two new Red Flags rows (external reviewer is not code-review-only; disagreement is signal, not authority — neither defer nor ignore). Integration section links the gate doc.
3. **`skills/sdlc-lite-plan/SKILL.md`** — Step 3: external reviewer joins the review roster when configured (plan-only payload, mid-tier/`high`, `[external:<model>]` attribution, 2-round cap, never blocks on availability). Worker Agent Reviews attribution rule extended; new Red Flags row; Integration section links the gate doc.
4. **`process/debate-protocol.md`** — § Cross-Vendor External Reviewer updated: first-class once configured; final pass at execution time, but *alongside* the internal roster at planning time (plan review is a single ensemble round, not a fix loop — independence is maximized by parallel review).
5. **`CLAUDE-SDLC.md`** — "Optional external review gate" paragraph retitled "External review gate — first-class when configured" and extended to name the planning integration points.

**Rationale:** The value of an external reviewer comes from vendor-level independence — a different training distribution fails on different edge cases. That independence pays most where decisions are structural and cheapest to change: planning. Reviewing a plan costs a fraction of reviewing a diff, and a caught phasing or approach error avoids the 10x cost of unwinding it during execution. Making participation default-on when configured (instead of per-run discretionary) converts an occasional second opinion into genuine cross-family deliberation, while the advisory-only + same-triage + 2-round-cap constraints keep the Manager Rule and anti-conformity safeguards intact.

---

## 2026-07-13: sdlc-audit Deep Verify — opt-in retroactive knowledge content verification (§6m)

**Origin:** ChronoCore handoff (`sdlc-audit-deep-verify-mode_handoff.md`), sibling to the promotion-verification-gate handoff. After two worked runs of the multi-judge pattern (18-entry promotion batch, then a 674-entry full-store retroactive sweep that found 45 real defects — ~1 in 15 entries — in content unreviewed since ingestion), CD asked where the retroactive version should live upstream. Decision: an opt-in `sdlc-audit` mode — not the default run (an order of magnitude costlier than the file-read/grep dimensions), not a standalone skill (audit already owns provenance reading, the §6c authority matrix, and the step 11 triage flow the findings feed).

**What happened:** The Promotion Verification Gate covers content entering the store, but nothing re-verified content already inside — entries predating the gate, drifted since ingestion, or contradicting the code they describe (worked example: an entry claiming all four effect classes route through a pipeline that its own `pipeline:` field showed handles two). The ChronoCore sweep also had to invent tooling mid-session (a comment-preserving YAML entry remover, because `yaml.safe_dump()` round-trips destroy hand-authored `# =====` banners) that should ship with the mode, not be re-derived per project.

**Changes made:**

1. **`skills/sdlc-audit/references/deep-verify.md`** (new) — Full mode spec: opt-in-by-name activation (mirrors the external-review-gate's disabled-by-default shape); orchestrator-run, never the `sdlc-compliance-auditor` subagent (needs `AskUserQuestion`, judge dispatches, egress disclosure); mandatory pre-flight `AskUserQuestion` with cost estimate, egress disclosure, and scope selection (full / domain / stale-only via §6h / incremental since last `audit-sweep` provenance entry); claims-vs-reference content scoping with ambiguous files flagged to CD, never silently decided; judge mechanics by reference to the Promotion Verification Gate with `KEEP|DEMOTE` verdicts (screening tier, fact-check lens, frontier tie-breaks, once-over of the keep-bound slate); embedded reusable scripts (payload extraction + comment-preserving entry removal); demotion mechanics; provenance logging; red flags.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — New §6m dimension (explicitly excluded from the default sweep and from the auditor subagent's scan; sequence note added after step 11 list). §6c authority matrix gains a demotion row: Promoted/`[READY TO PROMOTE]` → `[NEEDS VALIDATION]` is CD decision (step 11), proposed with multi-judge DEMOTE verdicts, **batch-level approval per discipline acceptable** with factual-error dissents and splits listed individually — resolving the handoff's open question on demotion authority (CD-gated, but at batch granularity; per-entry adjudication at 45-demotion scale is the same failure mode the tie-break judge exists to prevent). Step 11 intro gains Deep Verify as a third candidate source; step 11c gains the Demote path (comment-preserving removal, parking-lot restoration with judges' reasoning, `Promoted →` ledger pointer fixes, `last_updated` bump, one provenance entry per sweep).
3. **`skills/sdlc-audit/SKILL.md`** — Three-mode frontmatter with deep-verify trigger phrases ("deep audit", "deep verify", "verify the knowledge store", "full content sweep"); modes table and Input Resolution rows (`/sdlc-audit deep-verify [scope]`) with an explicit "never activates implicitly" rule; new Deep Verify Mode section (workflow summary + non-negotiable gates, details in the reference file); Integration and Reference Files updated; red-flag row against opportunistic deep-verifying during a compliance audit.
4. **`knowledge/provenance_log.md`** — `source-type` enum gains `audit-sweep`; conventions note that sweep entries record scope/judge-config/counts and serve as the incremental-scope boundary marker.
5. **`process/commands.md`** — `/sdlc-audit deep-verify [scope]` command row.
6. **`skeleton/manifest.json`** — `skills/sdlc-audit/references/deep-verify.md` added to `source_files.skills`.
7. **`agents/sdlc-compliance-auditor.md`** — Explicit exception under "Full coverage": §6m is opt-in and orchestrator-run; the auditor never executes it and reports it as "opt-in, not run" in coverage rather than as a gap.

**Rationale:** The ~1-in-15 defect rate in never-reverified content justifies the capability existing; the two-hour/dozens-of-dispatches cost profile justifies it never running by default — the handoff's own answer to "should full-store re-verification be scheduled?" is "no: available, opt-in, on the project's cadence." Routing findings through the existing step 11 triage instead of a parallel flow keeps one authority model (the §6c matrix) governing every marker transition in both directions. The judge mechanics are referenced from the gate rather than duplicated, so the two-tier/fact-check/once-over refinements land in one place. Not a `[contract-change]`: no knowledge-layer reference phrasing changed.

---

## 2026-07-13: Promotion gate — two-tier judging (screen cheap, escalate splits), mandatory fact-checking lens, frontier once-over

**Origin:** Retroactive gate run over ChronoCore's 674 already-promoted knowledge entries: 540 unanimous PROMOTE, 12 unanimous DEMOTE, **122 splits** — far too many for one-by-one CD adjudication. Sampling showed the splits were signal, not noise: Codex was fact-checking specific claims embedded in entries (PostgreSQL lock-escalation semantics, `REINDEX CONCURRENTLY` locking, OCI image-signing order, stale DORA thresholds, a 4xx-retry rule contradicting its own 429 guidance) while the Fable judge evaluated "is this a recognized general pattern?" and passed them. CD directives: run the initial external-judge pass at a low/mid tier with medium/high reasoning, elevate model and/or effort for tie-breaks, and add a final high-model once-over to verify the lower tiers got it right.

**What happened:** The gate as first shipped ran everything at the frontier tier (`xhigh`) and escalated every split to CD with full reasoning — a design that worked at prototype scale (18 entries, 5 splits) and collapses at batch scale (674 entries, 122 splits). The retro also exposed a judge-instruction gap: nothing required judges to verify embedded factual claims, so a pattern-recognition lens could PROMOTE entries containing checkable errors.

**Changes made:**

1. **`process/discipline_capture.md`** — Gate step 2 becomes the **screening tier**: external judge at a balanced/mid-tier `CODEX_MODEL` with `CODEX_REASONING_EFFORT=high`; subagent judge at `model: "opus"`. Step 4's split handling becomes **escalate model/effort, not CD**: one fresh frontier-tier tie-break judge (frontier `CODEX_MODEL` at `xhigh`, else `model: "fable"` subagent), blind to the split, same fact-checking instructions; the 2–1 majority applies with dissent recorded. New requirement in step 2: every judge's instructions must demand fact-checking of specific claims (numeric thresholds, version-sensitive benchmarks, protocol/API semantics, internal consistency) — a recognized pattern containing a false specific claim is a DEMOTE. New flag rule: a 2–1 PROMOTE overriding a factual-error dissent is flagged prominently to CD rather than buried by the majority. New step 5: **frontier once-over** — the full promote-bound slate (unanimous and tie-broken PROMOTEs) gets one final frontier-tier judgment as a single batch dispatch, blind to earlier verdicts, before CD presentation; its DEMOTEs are frontier dissents flagged to CD, never silently applied or discarded. Demote-bound entries are not re-reviewed — the risk is asymmetric (a wrong promotion compounds; a wrong hold-back waits a cycle).
2. **`process/external-review-gate.md`** — § Task-Based Model Selection effort guidance rewritten as "screen cheap, escalate splits" (frontier tier reserved for tie-breaks, the final once-over, and high-risk diffs); Knowledge-Judgment Wrapper section documents the tiers; example knowledge-judge wrapper default effort `xhigh` → `high` and its prompt gains the fact-checking instruction.
3. **`skills/sdlc-audit/references/compliance-methodology.md`** — §6c evidence-production note and step 11a updated to the tie-break flow (splits resolved by frontier-tier judge, factual-error dissents flagged to CD) plus the final frontier once-over before 11b, instead of per-split CD escalation.

**Rationale:** Two empirical lessons from the first at-scale run. (1) Split volume grows with batch size, so the human can't be the tie-breaker — but a frontier-tier judge can be, while CD keeps batch-level authority and gets the high-value splits (factual-error dissents) surfaced instead of all 122. (2) The most valuable verdicts came from fact-checking embedded claims, not recognizing patterns — so that lens is now a required judge instruction rather than an accident of which vendor's model happened to apply it. Screening at mid-tier/high is the cost floor that makes 674-entry batches feasible; the retro showed unanimity is the common case (82%), so frontier capacity is only spent where it pays: the ~18% that split, plus one batch-level once-over that backstops the screening tier on everything about to enter a knowledge store.

---

## 2026-07-13: Task-based model selection for Codex-backed external-review wrappers

**Origin:** CD directive in a cc-sdlc source session: when Codex is configured as an external reviewer, allow the orchestrator to choose model and reasoning effort per task (`codex -m <model> --config model_reasoning_effort="xhigh"`), resolving current model names at runtime from https://developers.openai.com/api/docs/models.

**What happened:** The wrapper contract gave the wrapper sole ownership of model choice, so every external review ran at the wrapper's single hardcoded configuration regardless of stakes — a docs-only diff and a knowledge-promotion verdict got the same model and effort.

**Changes made:**

1. **`process/external-review-gate.md`** — New "Task-Based Model Selection" section: Codex-backed wrappers pass through optional `CODEX_MODEL` / `CODEX_REASONING_EFFORT` env vars set by the invoking skill at the call site; wrapper defaults apply when unset. Model names must be resolved at runtime from OpenAI's model catalog (WebFetch https://developers.openai.com/api/docs/models), never recalled from training data — if the catalog can't be fetched, leave `CODEX_MODEL` unset rather than guess. Effort guidance: top-tier model at `xhigh` for high-stakes single-shot judgments (promotion verdicts, auth/payments/migrations/concurrency diffs), `medium` for routine second opinions. Wrapper-contract bullet updated (wrapper provides the *default* model, honors the passthrough); both Codex example wrappers updated — diff reviewer defaults effort to `medium`, knowledge judge to `xhigh`. Egress disclosure now names the actual model used.
2. **`CLAUDE-SDLC.md`** — External review paragraph mentions the env-var convention and the runtime model-resolution rule.

**Rationale:** External review quality should scale with task stakes, and the framework shouldn't embed model names that rot — OpenAI's catalog changes faster than this repo. Env-var passthrough keeps the wrapper contract intact (project still owns endpoint, egress policy, and defaults) while letting the orchestrator escalate a high-stakes judgment to a frontier model at maximum effort without editing the wrapper.

---

## 2026-07-13: Promotion Verification Gate — multi-judge evidence before knowledge promotion

**Origin:** ChronoCore handoff (`promotion-verification-gate_handoff.md`). In a ChronoCore session, 18 `[NEEDS VALIDATION]` parking-lot entries were bulk-promoted on the orchestrator's own judgment, violating the §6c authority matrix ("Proposed with evidence during interactive triage"). A retrofitted 3-judge review (self + Codex + Fable subagent) demoted 10 of the 18 — empirical proof that single-agent self-certification fails at exactly this transition. CD asked for the gate to be formalized upstream. Design was reviewed by two independent judges (Codex via `codex exec`, plus this session's own analysis) before implementation; both agreed with three amendments adopted below.

**What happened:** Promotion to a knowledge store had a CD-only authority rule but no defined evidence-production mechanism — step 11a said candidates need "evidence" without saying how it gets produced, so orchestrators substituted their own reasoning. Worse, `sdlc-archive` step 9c instructed applying `[READY TO PROMOTE]` as a silent "reasonable default," directly contradicting the §6c matrix.

**Changes made:**

1. **`process/discipline_capture.md`** — New "Promotion Verification Gate" section before the Promotion Workflow: neutral no-verdict evidence payload; two independent non-orchestrator judges (external `external-review-knowledge.sh` wrapper if configured, high-tier Fable/Opus subagent always, second subagent as fallback); `N | PROMOTE|DEMOTE | justification` verdict format; the orchestrator does not vote or break ties; unanimous-PROMOTE goes to CD as verified, unanimous-DEMOTE is not proposed, splits escalate to CD with each judge's full reasoning. Proportionality rule: full gate required for batches of 3+ entries or any weakly-evidenced entry; a single well-evidenced entry may present its evidence directly (lighter path replaces the judges, never the CD decision). Rules section's audit-triage carve-out now points at the gate as how CD's decision gets evidence.
2. **`process/external-review-gate.md`** — New "Knowledge-Judgment Wrapper" section: parallel convention `[sdlc-root]/external-review-knowledge.sh` (separate wrapper, not a mode flag — different artifact, different contract), stdin = neutral payload, stdout = `N | PROMOTE|DEMOTE | justification`, non-zero exit falls back to a second internal subagent, same egress rules, with a Codex example wrapper.
3. **`skills/sdlc-audit/references/compliance-methodology.md`** — §6c gains an "Evidence production" note wiring the matrix's evidence requirement to the gate; step 11a specifies when to run the gate before 11b and how verdicts map to the candidate list (unanimous-DEMOTE drops the candidate with dissent appended to the parking-lot entry).
4. **`skills/sdlc-archive/SKILL.md`** — Step 9c no longer applies `[READY TO PROMOTE]` as a silent default (that contradicted the §6c CD-only rule): validated entries are flagged as promotion candidates in the triage table for CD, or annotated `(promotion candidate — [date])` if the table is skipped. Added an explicit note that archival identifies candidates but does not adjudicate — the gate runs at promotion time (audit step 11), keeping archival fast by design.
5. **`CLAUDE-SDLC.md`** — External review gate paragraph mentions the parallel knowledge-judgment wrapper.

**Rationale:** A knowledge store entry is precedent every future agent reads, so a bad promotion compounds — and the ChronoCore data shows self-certification approves bad promotions at a >50% rate. The gate's key design points came from the prototype and the two-judge design review: judges must reason from a shared verdict-free payload (independence), the orchestrator must not tie-break (it is the actor being checked — "self + one subagent" is one independent opinion, not a majority), split votes need full reasoning surfaced (a bare tally hid the "adjacent entry ≠ corroboration" distinction that caught most bad promotions), and the gate is scoped to batches/weak evidence so it stays a followed rule rather than skipped ceremony. Not a `[contract-change]`: no knowledge-layer reference phrasing changed.

---

## 2026-07-11: sdlc-reflect prunes agent memories session-scoped

**Origin:** CD directives in a cc-sdlc source session: "sdlc-reflect should attempt to prune agent memories," followed by "part of the reflect process should be figuring out if those entries warrant being entered into the parking lots."

**What happened:** Agent memory hygiene existed only as sdlc-audit Dimension 8b — a project-wide sweep that runs at audit cadence. Between audits, memories invalidated by ongoing work (stale claims, drifted duplicate values, MEMORY.md files creeping toward the 200-line/25KB load cap) accumulated with no lighter-weight cleanup point. sdlc-reflect already closes out ad-hoc sessions and surveys the session's diff, making it the natural place for a session-scoped prune.

**Changes made:**

1. **`skills/sdlc-reflect/SKILL.md`** — Added Step 5 "Prune Agent Memories" (Report renumbered to Step 6): session-scoped prune covering agents dispatched this session and memories whose claims the session's diff invalidated. Reuses the Dimension 8b check definitions (contradicts-code, duplicate/drifted values, size-cap split, orphaned directory), gates prunes behind a confirmation prompt, requires source verification before deleting, and treats pruning as best-effort — parking lot capture remains the primary deliverable. Step 5 also runs a promotion check before any deletion: memory entries passing the Step 2 filters (reusable, non-obvious, actionable) — whether pruned or kept — are routed to discipline parking lots with context `[memory: {agent-name}]`, marked `[NEEDS VALIDATION]`. Frontmatter description, preconditions, report template, Red Flags, and Integration/DRY notes updated; added anti-trigger routing project-wide sweeps to sdlc-audit.
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — Dimension 8b note: sdlc-reflect applies the same checks session-scoped between audits and opportunistically routes generalizable memory entries to parking lots (lower bar than 8a's 2+-agent recurrence, same triage cycle); the audit remains the project-wide sweep and shouldn't be skipped on the assumption that reflect kept things clean.
3. **`CLAUDE-SDLC.md`** — Extended the post-session sdlc-reflect suggestion to mention the memory prune.

**Rationale:** Stale agent memories are a correctness risk (an agent trusting an invalidated claim is worse than one with no memory), and the session that invalidated a memory is the cheapest moment to catch it — the diff is already in hand. Pruning without a promotion check would silently discard insight: a memory invalidated by a change often documents why the old approach failed, which is exactly the kind of gotcha/anti-pattern signal the parking lots exist to catch. Scoping reflect's prune to the session keeps it fast and keeps the division of labor clean: reflect handles incremental hygiene and opportunistic capture, audit handles the exhaustive sweep and recurrence-based mining.

---

## 2026-07-09: Render precedes approval — never in sequence with the approval gate

**Origin:** CD directive in a cc-sdlc source session: "render should never happen in sequence with approval — it should precursor approval if the user chooses."

**What happened:** The post-skill render offer existed as a post-write step, but nothing constrained its position relative to approval gates. In practice this allowed the render offer to be bundled into the approval question, or the render to happen after approval as a follow-up — defeating the render's purpose as a review aid for the approval read. Worse, `html-rendering.md`'s re-render-on-plan-revision rule said "the HTML should reflect the approved plan," which reads as an instruction to render *after* approval.

**Changes made:**

1. **`process/html-rendering.md`** — Added "Render precedes approval — never in sequence with it" rule to the post-skill render offer section: the render offer is its own interaction, fully resolved (declined, or accepted with HTML delivered) before approval is requested; never bundled into the approval question, never rendered post-approval. Reworded the re-render-on-plan-revision rule: re-render after the final revision and *before* presenting for approval — CD approves what they see rendered.
2. **`CLAUDE-SDLC.md`** — Appended the sequencing rule to the post-deliverable render-offer paragraph.
3. **`skills/sdlc-plan/SKILL.md`** — Spec render offer (step 2) now states it must resolve before the step-3 approval gate. Step 6 (Prompt for Execution) gained a "Render precedes approval" pre-step: re-render the final revised plan before entering plan mode. Added two Red Flags rows (post-approval render offer; bundling render offer with approval question).
4. **`skills/sdlc-lite-plan/SKILL.md`** — Step 5 (Enter Plan Mode) gained the same "Render precedes approval" pre-step. Added a Red Flags row.

**Rationale:** The HTML render exists to give CD a better reading surface for the decision they're about to make. Sequencing it with or after the approval gate makes it decorative — the decision is already made by the time the render arrives. Fixing the sequencing at the process-doc level and at each approval gate ensures CD reviews the rendered artifact (if they opt in) before being asked to approve.

---

## 2026-07-09: Agent-memory hygiene — MEMORY.md cap enforcement, topic-file protocol, archive path fixups

**Origin:** Upstream handoff from a ChronoCore session that manually pruned `.claude/agent-memory/` (16 dirs, ~50 files) after severe drift — one `MEMORY.md` had reached 2628 lines, others contained content actively contradicting current code, duplicated tuned values with drifted numbers, and an orphaned predecessor-role directory. Web research confirmed Claude Code loads only the first **200 lines / 25KB** of `MEMORY.md` into the agent's system prompt (`MAX_ENTRYPOINT_LINES`), silently truncating the rest — and since entries append at the bottom, the *newest* notes are the ones dropped. The framework already named topic files as the remedy but only as a bare one-line suggestion with no size trigger, naming convention, or index framing, and nothing enforced the cap.

**Changes made:**

1. **`templates/agent-template.md`** — rewrote the Persistent Agent Memory guidelines into a real protocol: MEMORY.md-as-index framing, the 200-line/25KB cap with the "newest entries truncated" explanation, a split trigger (~180 lines), a topic-file naming/location convention (`.claude/agent-memory/{agent-name}/{topic}.md`, kebab-case, linked with one-line pointers), and explicit "replace drifted values, don't duplicate" guidance. Removed the redundant trailing `## MEMORY.md` section (its content is now covered above).
2. **`skills/sdlc-audit/references/compliance-methodology.md`** — split Dimension 8 into **8a Pattern mining** (promotion signal, unchanged) and **8b Hygiene** (new fix signal): size-cap violation (Major, MEMORY.md only — topic files uncapped), contradicts-current-code, internal duplication, orphaned directory. States the read-only auditor reports with file+line and the orchestrator applies fixes.
3. **`skills/sdlc-audit/SKILL.md`** — added a **Memory hygiene triage** to Step 3 folded into the existing prune `AskUserQuestion` batch (no second gate); routed fixes to Step 4's orchestrator (has Write), resolving the read-only-domain-agent limitation without needing write-capable domain agents. Updated the Dimension 8 summary line.
4. **`agents/sdlc-compliance-auditor.md`** — updated Dimension 8 summary to name 8a/8b; extended the Major severity class to include over-cap and code-contradicting `MEMORY.md`.
5. **`skills/sdlc-archive/SKILL.md`** — added **Step 9d Agent Memory Path Fixups (mechanical only)**: scoped strictly to the archived deliverable(s) and to rewriting `docs/current_work/...` → `docs/chronicle/...` paths this operation just broke. Explicitly defers all judgment-based pruning to audit Dimension 8b; folds any task-log deletions into the Step 9c triage table (with a defined fallback when 9c is skipped).
6. **`CLAUDE-SDLC.md`** — added the MEMORY.md cap + topic-file index pattern to the agent-memory bullet so target projects see the rule in their merged CLAUDE.md.

**Rationale:** Detection of agent-memory drift already existed (Dimension 8 flagged stale/contradicting memories) but there was no *fix loop* and no *prevention* — findings were flagged and nothing acted. The split here is deliberate: the template is the prevention layer (agents split before they hit the cap), archive Step 9d is the incremental mechanical cleanup (fix only what an archive itself breaks), and audit Dimension 8b is the periodic judgment-based sweep. The over-cap flag is a correctness issue, not cosmetic — an agent over 200 lines is silently running on a memory it can't fully see. Adapter phrasing contract checked: `.claude/agent-memory/` is the private scratchpad, distinct from the knowledge layer the neuroloom adapter transforms, so no `[contract-change]` and no paired plugin edit.

---

## 2026-07-09: sdlc-execute — plan size is not a confirmation trigger

**Origin:** Observed in a target-project execution session (D105, 7-phase plan). After emitting the Phase plan table, the executor paused and asked an `AskUserQuestion` about "execution scope" (full run vs. backend-only vs. Phase 1 only) — a checkpoint the skill never sanctions. The question's "Full sequential execution" wording also contradicted the parallelism the Phase plan itself declared.

**What happened:** The skill already forbids pausing for confirmation at dispatch time ("the plan is already approved") and treats post-summary stopping as a red flag, but nothing addressed the specific failure shape: plan *size* triggering an invented pre-execution scope checkpoint right after the Phase plan emission.

**Changes made:**

1. **`skills/sdlc-execute/SKILL.md`** — added an explicit rule after the Phase plan emission instructions: proceed directly to the first wave's PRE-GATE in the same response; plan size is not a confirmation trigger; a scope question re-litigates the `sdlc-plan` approval. Added a matching Red Flags row ("This plan is very large — I should confirm scope before starting").

**Rationale:** Approved plans are executed, not re-negotiated. Large plans pattern-match to a generic "confirm before a long autonomous run" instinct; the skill now names and blocks that instinct at the exact point it fired.

## 2026-07-08: Planning orchestrator is Fable OR Opus (CD's choice, not prescribed)

**Origin:** CD directive — "fable or opus should be the planning agent depending on what the user wants." The just-added cheat-sheet leaned toward Fable as the planning default; CD clarified it is a choice between the two top-tier models.

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — MTS6 reworded: run planning on a top-tier model, Fable OR Opus at CD's discretion (choose by task, quota, preference; e.g. Fable flagship vs Opus 4.8 1M-context), explicitly "the framework does not prescribe one; the load-bearing split is planning-premium vs execution-Sonnet." Checklist item updated to match.
2. **`CLAUDE-SDLC.md`** — session cheat-sheet: planning Model cell now "Fable **or** Opus (CD's choice)"; added a "Planning model is your call" note; alias block now offers both `ccplan` (Fable) and `ccplan-opus` (Opus).

**Downstream:** Documentation — propagates on next migration.

**Rationale:** Both models are premium and interchangeable for the planning seat; prescribing Fable would over-constrain a preference/quota decision. What actually matters is that planning runs premium and execution runs Sonnet — not which premium.

## 2026-07-08: Session model/effort cheat-sheet + launch-alias recipe in CLAUDE-SDLC

**Origin:** CD found switching the session model and effort by hand every time they change between planning and execution painful, and asked for an easier way. Claude Code session-config mechanics were verified against current docs via a claude-code-guide subagent.

**What happened:** MTS6 said "plan on Fable/high, execute on Sonnet/medium" but nothing told CD *how* to apply that without friction. Added a CD-facing session cheat-sheet with the lowest-friction mechanism (launch aliases that set both dials at once).

**Changes made:**

1. **`CLAUDE-SDLC.md`** — new "Session Model & Effort (your orchestrator seat)" subsection: a plan-vs-execution model/effort table, the `ccplan`/`ccexec` launch-alias recipe (`claude --model fable --effort high` / `--model sonnet --effort medium`), and the verified mechanics — both are launch flags; switching model mid-session can reset effort (re-check `/effort` after `/model`); `settings.json` persists `effortLevel` but not `model`; no named profiles; SessionStart hooks can't drive `/model`. Distinguished the session dial from the per-agent frontmatter tiers.

**Verified mechanics (Claude Code docs):** `--model` and `--effort` are launch flags (effort values low/medium/high/xhigh/max); `settings.json` supports `model` and a persisting `effortLevel` field, but `model` does not hot-reload; `/model` and `/effort` switch mid-session; no named-profile mechanism exists.

**Downstream:** Documentation — propagates on next migration. Closes the loop between the MTS6 rule and its day-to-day application.

**Rationale:** A tier rule nobody can apply frictionlessly gets ignored. The alias recipe makes the plan-wide/execute-narrow split a one-word launch choice, so the guidance actually gets followed.

## 2026-07-08: AI/ML domain provisioning rule (function coverage, not agent count)

**Origin:** CD asked whether an AI-adjacent domain always warrants a dedicated ai-architect + ai-engineer duo.

**What happened:** Refined G5. The precise requirement is that two opus-tier FUNCTIONS are covered — AI system design/judgment, and AI-aware correctness review — not that two named agents always exist. Whether to dedicate a pair depends on how central AI is to the product.

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — added an `ai_ml_provisioning` block under `assignment_rules`: principle (two functions, not two agents; a single opus ai-architect can fill both design + escalated review); a core/feature/incidental decision (dedicate the duo only when AI is the core value prop; for a feature, inject the AI review lenses into the existing opus software-architect + code-reviewer; incidental gets generic agents + a security reviewer); and a "provision by function coverage, not agent count; right-size per AOP5" rule. Added an "AI/ML architect + reviewer" row (opus/high) to `archetype_table` and cross-linked it from G5.

**Downstream:** Documentation/rule change — propagates on next migration.

**Rationale:** "Always a duo" would over-provision feature-level and incidental AI usage (roster bloat, violates AOP5/M4) while under-specifying what actually matters — the two opus functions. Framing it as function coverage lets a project satisfy G5 with existing opus reviewers when AI is peripheral, and dedicate specialists only when AI is central (avoiding generalist-masking). paire-appetit's organic llm-engineer + taste-intelligence-engineer split is the reference for the core case.

## 2026-07-08: Consolidated model/effort assignment rules + field survey of 5 installs

**Origin:** CD asked (1) what rules govern setting `model` and `effort` on agents, including AI/ML agents, and (2) to evaluate the sub-agents actually installed across sleeved, ChronoCore, paire-appetit, endlessgalaxystudios, and neuroloom to see whether real usage warrants additional rules.

**What happened:** The tier rules existed but were scattered across MTS1–MTS7 and the AGENT_SUGGESTIONS note — not a followable procedure. A survey of 113 installed agents validated the ladder and surfaced three additions: a both-axes reviewer invariant, a project-level baseline pattern, and the finding that `effort` is unset on 113/113 agents (a migration backfill, not just a go-forward default).

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — added an `assignment_rules` block: axes definition; model rules M1–M4; effort rules E1–E4; guardrails G1–G5 (G5 = AI/ML correctness is not evidence-checkable, so the correctness review escalates to opus/high regardless of implementation tier, and a passing run is never verification); `reviewer_invariant` (reviewer ≥ implementer on the model-OR-effort axis); `project_baseline` (raise the whole project's implementer model for systematically-hard domains, then differentiate reviewers by effort); `archetype_table` (keyed by role archetype, not agent name); and `survey_2026_07` recording the field evaluation and its consequences.
2. **`skills/sdlc-develop-agent/SKILL.md`** — pointed the frontmatter step at `assignment_rules` as the authoritative procedure for both `model` and `effort`, emphasizing archetype-keying.

**Survey findings (recorded in the YAML):** effort unset on all 113 agents; `code-reviewer` sonnet in 3/5 (violates the opus-reviewer default); security-review agents inconsistent (opus vs sonnet); deep-debugging split opus/sonnet; AI/ML implementers sonnet with non-escalated reviewers (confirms the G5 gap); ChronoCore runs implementers at opus wholesale (the project_baseline pattern); role names drift across projects (rules must key on archetype).

**Downstream:** Documentation/rule change — propagates to child projects on next migration. The installed agents in the five surveyed projects were NOT edited (out of scope — the ask was rules, not fixes); backfilling their model/effort per these rules is a separate migration/audit action a future session can trigger. A future sdlc-audit dimension could flag violations automatically.

**Rationale:** Real-world installs showed the rules were needed (broad inconsistency) and surfaced patterns pure theory missed — especially that when a hard-domain project runs everything at opus, effort becomes the ONLY remaining reviewer-differentiation lever, which is the strongest argument for treating effort as first-class rather than optional.

## 2026-07-08: Record tier-override decision (structural over per-call/Workflow)

**Origin:** CD follow-up in the same session — after verifying that per-dispatch model/effort override is reliable only in Workflow scripts (not interactive Task dispatch), CD asked whether the manual override was worth the effort or whether designating general-tier reviewer agents suffices, and whether Workflows could cover spec/plan reviews as well as implementation review loops.

**What happened:** Decided to keep the structural approach (MTS7 — dedicated opus review-only agents) and NOT adopt per-call override or a Workflow orchestration rewrite. Reasoning: the opus cross-cutting reviewers already carry the highest-value lenses; escalating each domain agent's own review adds only modest depth at large architectural cost; Workflows fit only the mechanical implementation review loop (spec/plan review are human-gated and cannot run headless); and interactive per-dispatch override is a tracked Claude Code feature (GitHub #62211/#64033) that could make a Workflow rewrite obsolete if it ships.

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — added a `tier_override_decision` record after MTS7 capturing the question, decision, rationale, and explicit `revisit_if` triggers (per-dispatch override becoming documented; evidence that sonnet domain review misses defects the opus reviewers don't catch).

**Downstream:** Documentation-only; propagates on next migration. No behavior change — records why the current structure was chosen so a future migration does not re-litigate it.

**Rationale:** The decision hinges on facts that will age (Claude Code's dispatch capabilities, the #62211/#64033 roadmap). Recording the triggers that would flip the decision keeps the choice auditable and cheap to revisit rather than re-deriving it from scratch later.

## 2026-07-08: Agent-tier structure decisions + External Review Gate

**Origin:** CD design session following the model-tier-strategy ingestion (below). CD asked three questions: (1A) split subagents into reviewer/implementer roles or genericize into stage-based roles (spec/plan/code reviewer)? (1B) how does a dispatching agent override a subagent's hardcoded model — is it even possible? (2) how can cc-sdlc use one LLM as planner/orchestrator and another (Codex or a local LLM) as implementer/reviewer, at minimum for an extra external review phase? Claude Code mechanics were verified via a claude-code-guide subagent against current docs before answering.

**What happened:** CD decided: (1) keep domain + reviewer hybrid — no stage-generic roles; (2) wire tiers explicitly (domain writers=sonnet, review-only agents=opus, recon=effort:low); (3) build an External Review Gate via Bash CLI. Verified mechanics that shaped the design: subagent model resolves in order `CLAUDE_CODE_SUBAGENT_MODEL` env → per-invocation param → frontmatter → inherit, but per-invocation model/effort override is only reliable in Workflow scripts, not interactive Task dispatch; `effort:` frontmatter (low|medium|high|xhigh|max) is stable and overrides session effort; external models integrate via MCP-wrapped tool, Bash CLI, or the existing OpenCode local-serving path.

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — added MTS7: realize the reviewer/implementer tier gap through the write/review agent split (reviewer-only agents at opus), NOT through stage-generic roles or unreliable interactive dispatch override. Unifies decisions 1A and 1B — the tier gap is achieved structurally because cc-sdlc already separates reviewer agents from writer agents.
2. **`agents/AGENT_SUGGESTIONS.md`** — added a "Model & effort defaults" note to the intro; added `Suggested model: opus` to code-reviewer, security-auditor, and software-architect (the cross-cutting review-only layer).
3. **`process/agent-selection.yaml`** — tier1 header comment codifying: review is a mode not a role; review-only agents carry the escalated (opus) tier; recon agents effort:low; do not add stage-generic reviewer roles.
4. **`process/external-review-gate.md`** (new) — canonical spec for the opt-in cross-vendor review gate: runs after the internal loop converges, activated by an executable `[sdlc-root]/external-review.sh` wrapper (stdin=rubric+context+diff, stdout=`SEVERITY | file:line | finding`), findings re-enter triage, external model never fixes, hard data-egress rules (never send secrets; prefer local models; state egress to CD; confirm before first hosted run), 2-round cap, anti-conformity handling. Includes local (Ollama) and hosted (Codex) example wrappers.
5. **`process/review-fix-loop.md`** — added Step E (External Review Gate) between the clean internal loop and commit.
6. **`process/debate-protocol.md`** — added "Cross-Vendor External Reviewer" section framing the external model as the most-independent ensemble member (Design Principle 1), subordinate to internal review, weighted for higher false positives.
7. **`skills/sdlc-review-code/SKILL.md`, `skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`** — added the optional External Review Gate step after each internal review loop.
8. **`CLAUDE-SDLC.md`** — Direct Dispatch Rules: added the optional external review gate with the egress caveat.
9. **`skeleton/manifest.json`** — registered `process/external-review-gate.md`.

**Downstream:** Child projects receive MTS7, the new process doc, and the skill/doc wiring on next migration (`process/*.md` glob already covers the new doc in sdlc-migrate §2.1). The gate ships disabled — projects opt in by adding an executable `external-review.sh`; cc-sdlc ships no default wrapper because model choice and egress policy are project decisions. No contract-phrase changes.

**Rationale:** CD's planner/implementer-split goal is served two ways. Within Claude Code: keep domain agents, make the existing reviewer layer the higher tier (MTS7) so reviewer≥implementer holds without depending on dispatch-override that only workflows support. Across vendors: the External Review Gate adds a genuinely independent reviewer (different vendor/architecture = different blind spots), which debate-protocol identifies as the highest-value ensemble addition — while keeping it subordinate to cc-sdlc's own review loop and the Manager Rule (external model reviews; domain agents fix). Stage-generic roles were rejected because they strip knowledge routing, duplicate the skill's own stage orchestration, and shrink ensemble diversity.

## 2026-07-08: Manager Rule — replace trivial-fix exception with Delegation Economics Exception

**Origin:** CD directive, same session as the model-tier-strategy ingestion below. The initial ingestion deliberately rejected the community "do the work directly when delegation would cost more" boundary; CD reviewed that call and reversed it: "I don't mind the manager doing changes if they're trivial or small or more cost efficient, but they should always be reviewed. The goal is to keep main context small."

**What happened:** The Manager Rule's trivial-fix exception (mechanical + single-site + self-evident) was the only permitted self-implementation. CD adopted a broader economic boundary: the manager may self-apply when delegation costs more than the change itself — monetarily (dispatch overhead re-loading context the manager already holds) or in main-context growth — with review as the non-negotiable backstop.

**Changes made:**

1. **`process/manager-rule.md`** — "The Rule" reframed from "never edits code files" to "dispatches by default; direct implementation only under the Delegation Economics Exception; never self-approves." Trivial Fix Exception replaced by the Delegation Economics Exception (4 conditions: small and bounded; no design judgment; context-neutral — no paging in code to decide HOW; reviewed). Trivial fixes always qualify. Hard boundaries kept regardless of economics: specs/plans stay agent-written (except WORDING), architectural/product decisions stay with agents/CD, high-risk domains allow only trivial-class fixes with MTS4 risk-escalated review. "No Size Exception" section removed (superseded); new "Mandatory Review of Manager-Applied Changes" section (self-applied ≠ self-approved; batch small changes into one review dispatch). "No Complexity Exception" retained. Failed-dispatch rule softened: re-dispatch with revised prompt first; a remaining gap that itself passes the economics test may be closed directly with review. Scope/completeness bullets updated to the same test (merge reconciliation still always dispatches — it's judgment). Session Scope single-file rule now applies the economics test.
2. **`skills/sdlc-plan/SKILL.md`, `skills/sdlc-lite-plan/SKILL.md`, `skills/sdlc-execute/SKILL.md`, `skills/sdlc-lite-execute/SKILL.md`** — inlined Manager Rule summaries updated to the economics exception + revised failed-dispatch rule; execute skills' review-loop fix triage now uses the economics test (self-applied fixes re-enter the next review round); lite-execute red flag updated.
3. **`skills/sdlc-review-code/SKILL.md`** — Step 5a fix triage rewritten around the economics test (trivial fixes always qualify); self-check wording updated; Step 5b review loop unchanged and remains mandatory for self-applied fixes.
4. **`skills/sdlc-create-reference-doc/SKILL.md`** — fix-loop triage aligned to the economics test.
4a. **`skills/sdlc-tests-run/SKILL.md`** — Manager Rule section updated: economics-qualifying fixes may be self-applied, verified by re-running tests, and reviewed; diagnosis-requiring fixes still dispatch.
5. **`CLAUDE-SDLC.md`** — Direct Dispatch Rules: "Never self-implement" → "Dispatch-first, with an economics exception" (review mandatory); "Iterate on CD feedback" allows economics-qualifying self-fixes with review.
6. **`process/overview.md`** — direct-dispatch description updated.
7. **`BOOTSTRAP-LITE.md`** — Manager Rule summary updated (complexity exception still absent; economics exception added with mandatory review).
8. **`knowledge/architecture/model-tier-strategy.yaml`** — "Relationship to the Manager Rule" preamble rewritten (exception adopted; economics never buys skipped review or absorbed design judgment); MTS1 anti-pattern retargeted at skipping review rather than at self-implementation per se.
9. **`knowledge/provenance_log.md`** — prov-2026-07-08-001 note amended to record the same-session adoption (branch not yet merged; note corrected rather than appended to avoid misleading future readers).

**Rationale:** The original rule optimized for role purity; CD optimizes for context economy. A dispatch that forces an agent to re-load context the manager already holds costs more tokens than the change, and reading the agent's handoff can grow main context more than typing the fix would. The redesigned exception keeps the two failure modes the old rule guarded against — scope creep via "small" changes and unreviewed manager output — behind explicit conditions: acquiring new context to self-implement disqualifies (that cost is the point of the rule), design judgment disqualifies, and review is unconditional. Self-applied is never self-approved.

## 2026-07-08: Framework Ingestion — Model & Effort Tier Strategy

**Origin:** Bulk ingestion via `ccsdlc-ingest` from community sources: three r/ClaudeAI thread screenshots (per-subagent `effort:` frontmatter; Fable-coordinates/Opus-verifies/Sonnet-executes/Haiku-scouts workflow splits; SDD with a top-tier coordinator), a community "fable-chief-agent" skill, and the DataCamp spec-driven development tutorial. CD specifically asked to explore Fable/Opus as the research/planning tier with Sonnet agents implementing.

**What happened:** The framework already assigned models per-agent (sonnet default, opus for design decisions, haiku for retrieval) and already enforced judgment/labor separation via the Manager Rule, but had no codified doctrine for WHY tiers map to work types, no effort-as-a-lever guidance, no risk-escalated-review rule, and no session-level guidance that planning should run on the top tier. The community sources supplied exactly that doctrine.

**Changes made:**

1. **`knowledge/architecture/model-tier-strategy.yaml`** — created with 6 rules (MTS1–MTS6): concentrate judgment at the top tier / delegate evidence-checkable work down; the tier ladder (top-tier orchestrator → opus hard delegated reasoning + high-risk review → sonnet default worker → haiku recon); effort as an independent per-role lever; reviewer tier ≥ implementer tier for high-risk domains; stack-difficulty tier adjustment; plan-wide-on-premium / execute-narrow-on-cheap session tiering. Includes an explicit "Relationship to the Manager Rule" preamble rejecting the community delegation-economics escape hatch.
2. **`templates/agent-template.md`** — frontmatter reference: added optional `effort:` field (low|medium|high|xhigh|max, with harness-version caveat); model guidance now covers the high-risk-review role for opus and points to the tier strategy file.
3. **`skills/sdlc-develop-agent/SKILL.md`** — frontmatter generation step: expanded `model:` guidance and added `effort:` field guidance with tier-strategy pointer.
4. **`agents/sdlc-reviewer.md`** — agent frontmatter checklist: validates optional `effort:` values.
5. **`skills/sdlc-plan/SKILL.md`** / **`skills/sdlc-lite-plan/SKILL.md`** — Agent Dispatch Protocol: read the tier strategy; planning sessions run on the highest-tier model available (MTS1/MTS6), recon goes cheap, high-risk phases get escalated reviewer tiers (MTS4).
6. **`skills/sdlc-execute/SKILL.md`** — EXECUTE dispatch protocol: MTS4 (reviewer ≥ implementer tier on high-risk) and MTS5 (escalate a thrashing worker instead of a third re-dispatch).
7. **`knowledge/agent-context-map.yaml`** — wired the new file to the architect role.
8. **`knowledge/architecture/README.md`** — structure listing updated.
9. **`CLAUDE-SDLC.md`** — Agent Conventions: new bullet on pre-assigned model/effort tiers and running planning sessions on the top tier.
10. **`disciplines/architecture.md`** — inventory table row + 3 `[NEEDS VALIDATION]` parking lot entries (effort-frontmatter support matrix, Sonnet-on-Rust thrash reports, per-phase Model/Effort column in the planning template).
11. **`knowledge/provenance_log.md`** — first provenance entry (prov-2026-07-08-001) recording sources and ingestion.
12. **`skeleton/manifest.json`** — added the new knowledge file.

**Skill candidates proposed:** none — the material is doctrine (knowledge + template/skill wiring), not a workflow warranting a new skill. The pasted fable-chief-agent skill was NOT adopted as a skill: its judgment/labor split is now knowledge, and its "do the work directly when delegation costs more" boundary conflicts with the Manager Rule, which stays authoritative.

**Downstream:** Child projects receive the new knowledge file, template fields, and skill guidance on next migration. No renames or contract-phrase changes — all new references use canonical phrasings, so no `[contract-change]` tag and no `skeleton/contract_changes.yaml` entry needed.

**Rationale:** CD's proposed split — Fable/Opus researching and planning, Sonnet implementing — is exactly the architecture the SDLC already enforces structurally (Manager Rule separates judgment from labor; agent frontmatter carries worker tiers). What was missing was the explicit doctrine making that split *deliberate*: run planning where judgment concentrates on the strongest model, keep workers cheap, and escalate only the review tier — not the implementation tier — when risk demands it. The DataCamp SDD material validated the existing spec → plan → execute gate structure without requiring changes.

## 2026-07-07: Agent-description example economy (drop `<commentary>`, tier example count, mandatory Do-NOT-use)

**Origin:** Upstream handoff from ChronoCore (`upstream-agent-description-economy_handoff.md`). ChronoCore measured that Claude Code injects every agent's full `description` frontmatter into every session's system prompt regardless of whether the agent is ever spawned — a permanent per-session tax, unlike the agent body (loaded only on spawn). ChronoCore's 16 agents, authored to the prior convention (4 `<example>` blocks each, every example with `<commentary>`), totaled ~44.5k characters (~11k tokens) of description payload per session. ChronoCore applied a local trim (~18-20k chars, ~5-6k tokens saved) and handed the convention change upstream since the framework's template/skill/reviewer — not the projects — was the driver.

**What happened:** The prior convention (agent-template.md, sdlc-develop-agent, sdlc-reviewer) mandated 2-4 `<example>` blocks per agent description, each with a `<commentary>` annotation restating why the routing is correct. Review of the trimmed ChronoCore agents found `<commentary>` blocks invariably restate the scope sentence or Do-NOT-use boundary already present in the same description (pure redundancy), and examples 3-4 invariably restate example 1's pattern with a different noun. The routing value concentrates in one typical-use example plus, for agents with a confusable sibling, one "seam" example distinguishing the two.

**Changes made:**

1. **`templates/agent-template.md`** — Description example rewritten to 1 `<example>` block (no `<commentary>`) plus a mandatory `Do NOT use for: X — use Y instead` boundary sentence. Comment-block frontmatter reference rewritten: explains the per-session token-tax mechanic, the confusability-tiering rule (1 example / 2 examples, never 3-4), the `<commentary>` drop, and the boundary sentence's promotion to mandatory.
2. **`skills/sdlc-develop-agent/SKILL.md`** — CREATE mode Step 2 (Frontmatter Generation) adds an explicit example-count-tiering procedure (detect confusable sibling via the Step 1 domain-overlap scan → 1 or 2 examples, never 3-4, no `<commentary>`, mandatory boundary sentence). Red Flags table entry on example blocks updated to the tiered rule. New Red Flags entry warns ENRICH mode against re-inflating a description's example count or reintroducing `<commentary>` when a source suggests a "great new scenario" — ENRICH enriches the body, not the description.
3. **`agents/sdlc-reviewer.md`** and **`process/skill-agent-review.md`** — Reviewer checklist updated in both: 1-2 examples tiered by confusability (3+ is Major), `<commentary>` blocks inside descriptions are Major, missing Do-NOT-use boundary sentence is Major (graduated from recommended to required — it's now the primary overlap-resolution mechanism once examples are capped at 2). "Do NOT use" section discipline broadened to cover both the body scope statement AND the description boundary sentence. Example-quality check extended: a 2nd example that isn't a genuine seam (just another typical-use case) is also Major.
4. **`agents/sdlc-reviewer.md`** and **`agents/sdlc-compliance-auditor.md`** — Dogfooded the new convention on the two framework agents installed into every target project. Both had 3 examples with `<commentary>` (pre-trim). Trimmed to 2 examples each (typical-use + a reciprocal seam example distinguishing single-file convention review from project-wide compliance auditing) with `<commentary>` dropped and a Do-NOT-use sentence naming the other agent.
5. **`skills/sdlc-migrate/SKILL.md`** — §3.1 (Identify Template-Derived Sections): added a clarifying note that the frontmatter `description` field is project/author-owned and is NEVER auto-updated by template changes — settles the handoff's open question explicitly rather than leaving it implicit. §3.4 (Downstream Impact Analysis): added an "Agent descriptions" scan row, a scan-step bullet, a findings-block example, and a gate-rule line so migration offers (but never auto-applies) a description trim to existing downstream agents that violate the new convention.

**Rationale:** The convention was the cost driver, not the individual projects — every agent scaffolded via `sdlc-develop-agent` inherited the 4-example-plus-commentary shape by default. Fixing it at the template/skill/reviewer level means future generated and migrated agents are born lean, and `sdlc-migrate` won't regress a project's already-trimmed descriptions back to the fat framework default (the field was never template-derived to begin with — §3.1 now says so explicitly instead of leaving it to be discovered by re-reading the migration code). Dogfooding the trim on `sdlc-reviewer`/`sdlc-compliance-auditor` themselves avoids the framework shipping two examples of the exact violation its own reviewer now flags in downstream agents.

---

## 2026-07-04: Route sdlc-handoff deferred work on effort, not artifact size

**Origin:** Downstream-project feedback. A session filed mechanical metadata backfill (a known, repeatable transform over ~76 production records) as "Deferred work — non-trivial" and got routed to `sdlc-lite-plan` when direct dispatch was correct. Root cause: the word "non-trivial" in the Step 3 routing table invited a *size/volume* reading, while the rest of that table keys on *approach*.

**Changes made:**

1. **`skills/sdlc-handoff/SKILL.md`** (Step 3 table) — Re-keyed the two "Deferred work" rows and the isolated-Issue row on **effort** (coordination cycles) instead of size. Added a criterion sentence above the table pointing at `collaboration_model.md` § Estimation Model: a known repeatable transform over N items is Light effort regardless of item count or production-write surface → direct dispatch. Preserved blast-radius/reversibility as an explicit plan trigger ("costly or hard to reverse") so high-volume irreversible writes still route to a plan. Encoded the escalation default in the Light-effort deferred row (default to direct dispatch; receiver escalates only if a real unknown surfaces).
2. **`skills/sdlc-handoff/SKILL.md`** (Red Flags) — Added an entry capturing the exact miscalibration: "It touches many records / writes to production, so it's non-trivial → plan it" → volume and write-surface aren't effort.

**Rationale:** Aligns the skill with the framework's existing Estimation Model, which already defines Effort as coordination cycles ("not wall-clock time") and explicitly lists cross-domain handoffs and verification depth — exactly the levers that make high-blast-radius work plan-worthy. Reusing the Effort vocabulary fixes the size-proxy miscalibration without minting a competing "approach clarity" axis, and keeps the fix from over-rotating into "scale never warrants a plan."
