---
type: handoff
slug: pilot-v2-migration-upstream-issues
created: 2026-10-13
status: partly done (cross-checked 2026-11-25)
trigger: issue
recommended_next_skill: none
source_session_summary: "The pilot project migrated from z-sdlc v1.8.1 to v2.0.0 on 2026-10-12/13. The run and its compliance audit worked around 13 framework problems in the project; each is checked here against the v2.0.0 tag"
active_deliverable: null
related_files:
  - skills/sdlc-archive/scripts/changelog_archive.py
  - tests/test_changelog_archive.py
  - .github/workflows/release.yml
  - skills/sdlc-migrate/SKILL.md
  - skeleton/contract_changes.yaml
  - skeleton/manifest.json
  - skills/sdlc-ingest/SKILL.md
  - agents/sdlc-compliance-auditor.md
  - agents/sdlc-reviewer.md
  - CLAUDE-SDLC.md
  - templates/agent-template.md
  - knowledge/README.md
  - knowledge/architecture/agent-orchestration-patterns.yaml
  - process/factory.md
  - bundles/factory/tree/templates/factory-image.yml
  - bundles/factory/tree/tests/test_render.py
  - process/external-review-gate.md
  - process/adapter-lifecycle-protocol.md
  - templates/test_spec_template.md
  - playbooks/example-playbook.md
  - process/knowledge-routing.md
  - process/changelog-archive/2026-Q1.md
  - process/changelog-archive/2026-Q2.md
---

# Handoff: Framework problems found in the pilot project's migration to v2.0.0

## Progress (cross-checked 2026-11-25)

**Done:**
- **Item 3, migration ran the old sdlc-migrate:** Pre-Flight step 1c follows the target tag's own skill and process docs (v2.9.0, 758cfbd). Projects learn of it from that entry's release notes, so open question 3 is answered.
- **Item 7, additive-only merge:** it's gone. Dual-audience skills and sdlc-audit's references merge by the project's marks, so an unedited copy takes upstream in full (v2.9.0).
- **Item 8, re-render after changing `stack.profile`:** in `process/factory.md` Enablement (v2.1.0).
- **Item 10, the `[sdlc-root]/../skills/` path:** `external-review-gate.md` cites the `.claude/skills/` path (v2.6.1, 3366565e).
- **Item 13, files a project removed:** `declined_files` (contract 0022, v2.9.0). Initialize and migrate write it, and any other missing file is asked about once. That answers open question 13.

**Partly done:**
- **Item 4, a project document at an upstream path:** a missing upstream file is asked about once, and deviation detection shows the differing units. Not built: the ingest guard, §2.1b's "this is a different document" check, and the auditor's check that cited rule IDs exist.
- **Item 5, a framework agent's edited `description:`:** deviation detection asks before overwriting it (v2.9.0). Frontmatter can't hold a mark, though, so the edit is re-applied by hand and reads as drift at each migration. There's still no keep-the-project's default.
- **Item 6, the `\n` rule:** the agents follow it (v2.3.0, c198e6e), and open question 6 is answered: a single `\n` loads today. No automated check.

**Not done:**
- **Item 1:** the archive script still accepts only `## YYYY-MM-DD:`.
- **Item 2:** §4.5a still finds the catalog table by column order.
- **Item 9:** the bundle tests leave `.pyc` files, and nothing ignores them.
- **Item 11:** the auditor flags upstream's own adapter doc.
- **Item 12:** templates cite stores a project may have removed.

Open questions 1, 4 and 9 are unanswered.

## Why this is a handoff

The pilot project is a card-game project (.NET server, TypeScript web client), with a local clone (its checkout, named below by repository-relative paths). On 2026-10-12/13 it migrated from z-sdlc v1.8.1 to v2.0.0. The run hit 13 problems that belong to z-sdlc, not to the project. It worked around each one in the pilot project and finished. The fixes go here.

The source session wrote only this file. Don't take on the pilot project's own follow-ups (see Out of scope). The factory work this tree had uncommitted then (`bundles/factory/…`, `process/factory.md`, `process/sdlc_changelog.md`) belonged to another session, and is committed since.

## Context

- **Migration commit:** The pilot project's `4342bd24` (`sdlc(migrate): upgrade z-sdlc from v1.8.1 to v2.0.0`).
- **Post-migration compliance audit:** 8/10, with Dimension 7 (migration integrity) compliant.
- **Full record:** the 2026-10-12 entry "Migrated to z-sdlc v2.0.0 (from v1.8.1)" in the pilot project's `ops/sdlc/process/sdlc_changelog.md` (line 40 at `4342bd24`). Its items 3, 4, 6, 8, 10 and 11 are the pilot project's side of several issues below.
- **How the items were checked:** every z-sdlc `file:line` is at tag `v2.0.0` (`git -C <z-sdlc> show v2.0.0:<path>`) unless another tag is named. The pilot project's paths are relative to its checkout, or given with a commit.
- **Result:** all 13 issues hold at v2.0.0, and none failed to reproduce. Four differ from the first report, and those differences are written into the items: item 4's file was never installed, so nothing was displaced; item 7 didn't affect the pilot project; item 8 is fixed since (`5da9dd8`); item 13 is a rule that contradicts itself, not a missing rule.

## Summary

| # | Issue | Area | Priority | Route |
|---|---|---|---|---|
| 1 | Archive script misfiles entries whose date heading isn't `## YYYY-MM-DD:` | Changelog archiving | high | plan |
| 2 | §4.5a looks for the catalog table by a fixed column order | sdlc-migrate | medium | direct |
| 3 | A migration runs the installed (old) sdlc-migrate | sdlc-migrate | high | plan |
| 4 | A project document at an upstream path goes unnoticed | Knowledge layer | medium | plan |
| 5 | Framework agents' edited `description:` gets replaced | sdlc-migrate | medium | plan or direct |
| 6 | Upstream's own agents break the `\\n` frontmatter rule | Framework agents | low | direct |
| 7 | Additive-only merge applies to unedited copies too | sdlc-migrate | low | plan or direct |
| 8 | Re-render after changing `stack.profile` | Factory bundle | medium (fixed: `5da9dd8`) | confirm only |
| 9 | Bundle tests leave `.pyc` files to commit | Factory bundle | low | direct |
| 10 | Broken `[sdlc-root]/../skills/…` path | Process docs | low | direct |
| 11 | Upstream's auditor flags upstream's own adapter doc | Process docs | low | direct |
| 12 | Templates cite stores a project may have removed | Knowledge layer | low | direct |
| 13 | Migrate would reinstall files the project removed | sdlc-migrate | low | plan |

## What needs to happen

### Changelog archiving

#### 1. The archive script misfiles entries with other heading forms (high)

**What happens.** `changelog_archive.py` starts a new entry only at a `## YYYY-MM-DD:` line outside a code fence (`skills/sdlc-archive/scripts/changelog_archive.py:42`, the `HEADING` regex, used at :86). A heading that starts with a date in any other form doesn't start an entry. Two examples are `## 2026-07-08 — Title` and `## 2026-04-22 (follow-on): Title`. The script adds that entry's text to the entry above it and moves it with that entry, into that entry's quarter. `check` and `archive` report nothing wrong. The script's own check (:274-280) passes because no text is lost, only filed in the wrong place. The migration runs this script automatically (§4.5c, `skills/sdlc-migrate/SKILL.md:1018`: "don't ask CD").

**Evidence.**
- The pilot project before the migration (`git show 4342bd24^:ops/sdlc/process/sdlc_changelog.md`) had six headings in the em-dash form at lines 4688-4742: 07-08, 07-10, 07-12, 07-11, 07-21 and 07-21. They came right after `## 2026-06-25: Knowledge-store promotion…` at line 4670. The archive run would have filed those six Q3 entries inside a June entry in `2026-Q2.md`. The migration changed the six headings to the colon form first (changelog entry item 8).
- Reproduced with the v2.0.0 script on a test file (`--today 2026-10-13 --threshold-kb 0`): a `## 2026-07-08 — …` entry placed after a `## 2026-06-25:` entry was moved into `changelog-archive/2026-Q2.md`. `check` exited 1 ("2026-Q2 (2)") and gave no warning.
- z-sdlc's own history has the `(follow-on)` form: `process/changelog-archive/2026-Q2.md:1643`. The pilot project's copy was at line 2278. It's in the same quarter as the entry above it, so nothing was misfiled. But the `--upstream` matching (:209-211, :221) can't see it as a heading of its own.
- `.github/workflows/release.yml:99` also recognizes only the colon form.
- `tests/test_changelog_archive.py` has no case for a heading in another form.

**Suggested fix.** Choose one:
- Treat every `## YYYY-MM-DD` heading outside a fence as an entry boundary: the date comes from the heading, and the title follows any separator.
- Make `archive` and `check` exit 2 and list each `## YYYY-MM-DD` heading that isn't in the colon form, so the person fixes them first.

A refusal would also fail on upstream's own `2026-Q2.md:1643`, so fix that heading in the same change. Either way, add both forms to `tests/test_changelog_archive.py`.

### sdlc-migrate

#### 2. §4.5a finds the catalog table by a fixed column order (medium)

**What happens.** §4.5a picks "the first table whose header row starts `| ID | Name | Status`" (`skills/sdlc-migrate/SKILL.md:985`). In a catalog with any column between Name and Status, no table matches, and step 2 (:986) has nowhere to insert the column.

**Evidence.**
- The pilot project's header was `| ID | Name | Concept | Status |`, under `## Active Deliverables` (`docs/_index.md:9` at `4342bd24^`).
- Contract 0016 (`skeleton/contract_changes.yaml:332-347`) adds `Depends on` after `Status`. Its notes say "Tools that parse catalog rows by position must find columns by header name" (:344-345), but the migrate step itself doesn't do that.
- The pilot project's run placed the column by hand (changelog entry item 6).
- The same file has `## Cancelled / Dropped Deliverables` with `| ID | Name | Concept | Status | Reason |` (line 96). A looser match must still pick the right table.

**Suggested fix.** Find the table under the `## Active Deliverables` heading. If there's no such heading, fall back to the first table whose header contains ID, Name and Status in any order. Find each column by its name, and insert after the column the contract names in `after`. If no table or no `after` column is found, stop and show CD the problem rather than guess.

#### 3. A migration runs the old version of sdlc-migrate (high)

**What happens.** A migration follows the copy of sdlc-migrate the project has installed, which is the old release's procedure. Any rule the new release adds to the migrate skill only arrives as part of the migration, too late to apply to it.

For v1.8.1 → v2.0.0 that included the rule that protects the project's changelog:
- v1.8.1's §2.1 direct-copies `process/*.md` and excludes only `agent-selection.yaml` (v1.8.1 `skills/sdlc-migrate/SKILL.md:328`, :332).
- v1.8.1's `process/path-mappings.md:22-30` doesn't list the changelog either.
- v2.0.0 adds `sdlc_changelog.md` and `process/changelog-archive/` to the exclusions (:343, :347, :249), along with §4.5b and §4.5c (:990-1018).

**Evidence.**
- The pilot project's changelog had 247 entries. The installed v1.8.1 procedure would have overwritten it with upstream's. The run noticed this and followed the v2.0.0 procedure instead (the pilot project changelog entry, line 42).
- The root cause is in z-sdlc's history. The 2026-03-22 entry that turned `MIGRATE.md` into this skill (`process/changelog-archive/2026-Q1.md:549-557`) removed MIGRATE.md's "Phase 0 (self-update)", reasoning that "skills are always installed from the source repo". That doesn't hold for sdlc-migrate: the copy that runs is the one the project has installed.
- v2.0.0's Pre-Flight (:50-139) doesn't check the version of the skill itself.

**Suggested fix.** In Pre-Flight, after resolving `[target_tag]` (:67-84), compare the installed `.claude/skills/sdlc-migrate/SKILL.md` with `git show [target_tag]:skills/sdlc-migrate/SKILL.md`. When they differ, do one of these:
- (a) Read the target tag's procedure with `git show` and follow that.
- (b) Install the target's sdlc-migrate and its scripts first, then tell the person to run the migration again.

At minimum, print a warning in Pre-Flight that names the gap. Any of these helps only from the release that ships it, because a project still runs its old Pre-Flight. The release notes should therefore tell projects to take the new migrate first.

#### 5. A framework agent's edited `description:` gets replaced (medium)

**What happens.** §2.1 direct-copies `agents/sdlc-reviewer.md` and `agents/sdlc-compliance-auditor.md` (`skills/sdlc-migrate/SKILL.md:353`). §3.1 says an agent's frontmatter `description` belongs to the project and is never updated automatically (:691). But Phase 3 covers only the project's own agents, and §3.4's check skips these two by name (:759). §1.2a flags both files as drifted (:199-226), but the three-way decision has no default for this field. Twice, the migrator took upstream's description.

**Evidence.**
- The pilot project shortened both descriptions on 2026-07-07 (`3d762195`). sdlc-reviewer's went from 1,241 to 481 characters. CD ruled on 2026-07-09 that they stay short.
- The v1.6.0 migration's first pass replaced them; the `8e93cfd6` commit message calls this "a deliberate project trim the initial migration pass mistakenly reverted".
- This migration's first pass did the same, and the post-migration audit caught it before commit (changelog entry item 3).

**Suggested fix.** For these two files, if the project's `description:` differs from the previous release's, keep the project's. Apply only upstream's mechanical renames (for example `cc-sdlc` → `z-sdlc`), and list upstream's new description in the report as a suggestion. Changes to the rest of the file still come from upstream.

#### 7. Additive-only merge also applies to copies the project never edited (low)

**What happens.** §2.2 Step 0 (`skills/sdlc-migrate/SKILL.md:593-595`) puts `sdlc-audit`, `sdlc-ingest`, `sdlc-develop-skill` and `sdlc-research` on an additive-only merge: new sections are added, and existing sections are never changed. §2.4 (:641-647) applies the same rule to sdlc-audit's reference docs. The rule applies whether or not the project ever edited the skill. When the copy is unedited, a full update is safe, and additive-only leaves old text behind.

**Evidence.**
- v1.8.1 → v2.0.0 changed all four skills: 7 files, +103/−13 (`git diff --stat v1.8.1 v2.0.0 -- skills/sdlc-{audit,ingest,develop-skill,research}`).
- In `skills/sdlc-audit/SKILL.md`, the new `### Improvement with a Factory Digest` section (:201) would be added. But two lines that lead to it sit inside `## Input Resolution`, a section that existed at v1.8.1: the input-table row `/sdlc-audit improve <digest>.json` (:57) and the input format (:68). Additive-only skips them, so nothing in the arguments would reach the new mode. Renames inside existing sections would be skipped the same way.
- The pilot project wasn't affected. Its run updated these skills in full, and its copies carry :57, :68 and :201. The rule as written would have left them out.

**Suggested fix.** Use additive-only only when the project changed the skill after installing it, meaning `installed_files[path].sha256` no longer matches the file on disk. §1.2a already computes this (:203-214). Direct-copy an unchanged skill from upstream.

#### 13. Migrate's rules would reinstall files the project removed (low)

**What happens.** The skill can't tell a file that is new upstream from one the project removed or never installed, and read literally, its rules reinstall both:
- §2.1 direct-copies `README.md` to `[sdlc-root]/` (`skills/sdlc-migrate/SKILL.md:351`) and every `knowledge/**/*.yaml` (:349).
- §2.1b step 1 says "New file (doesn't exist in project): Copy from upstream as-is" (:493).

Meanwhile, §1.2a only looks at paths listed in `installed_files` (:203), so it can't see absent files. The project manifest has no field for files the project chose not to have. Legitimate removals do happen: `sdlc-initialize` deletes a store marked `remove` when CD agrees (`knowledge/README.md:208`, :210).

**Evidence.**
- 31 upstream paths were never installed in the pilot project, or were removed (changelog entry item 10). They include `ops/sdlc/README.md` (`top_level` in `skeleton/manifest.json`), `token-economics.yaml`, `component-catalog.yaml` and `timing-defaults.yaml`.
- The retrofit install removed 20 stores that didn't apply (`e5705499` message: "45 YAML files retained after removing 20 inapplicable stores").
- This migration chose not to install any of the 31, as earlier migrations had, but there was no rule to point to.
- The pilot project's `.sdlc-manifest.json` has 264 `installed_files` entries and no record of the declined paths.

**Suggested fix.** State the rule. If a path existed at the project's `source_version` and is absent from the project, that was the project's choice: don't reinstall it, and list it in the report. Install only paths that are new upstream since `source_version`.

Record the choice in the manifest (for example a `declined_files` list), written by `sdlc-initialize` Phase 6a and by each migration, so later runs don't have to work it out again.

Item 4 is the exception that rule has to allow for. `agent-orchestration-patterns.yaml` is marked `keep` and was still missing in the pilot project, and a blanket "never reinstall" would have hidden that. Show CD any absent `keep` file instead of skipping it silently.

### Knowledge layer

#### 4. A project document at an upstream path goes unnoticed (medium)

**What happens.** Nothing stops a project from writing a different document at a path that belongs to upstream. Once that happens, nothing reports that upstream's content is missing, while skills keep citing it.

**Evidence (the pilot project).**
- Upstream lists `knowledge/architecture/agent-orchestration-patterns.yaml` in `skeleton/manifest.json` (v1.5.8:158; v2.0.0:171) and marks it `action_if_irrelevant: keep`. Even so, the pilot project's retrofit install at v1.5.8 (`e5705499`, 2026-05-26) didn't include it. Nobody knows why (see Out of scope).
- On 2026-06-03 an `sdlc-ingest` run (`72199722`) created a new file at that empty path. It held the pilot project's game-studio patterns AO01–AO06 (`pattern: entries`), not upstream's rules AOP1–AOP10 (`pattern: rules`, `rules:` at :25-389) or its `dispatch_prompt_templates` (:390). Upstream's content was never in the project, so nothing was overwritten. Upstream's name was taken.
- Seven installed skills cite AOP rules: sdlc-plan, sdlc-lite-plan, sdlc-execute, sdlc-lite-execute, sdlc-review-code, sdlc-tests-create and sdlc-tests-run. They did so at every release the pilot project ran, v1.5.8 through v1.8.1 (`git grep -l 'AOP[0-9]' <tag> -- skills`). v2.0.0 adds `process/review-fix-loop.md`'s AOP5 roster rule, and `process/agent-selection.yaml` cites them too. For four months none of the skills' citations pointed to anything in the pilot project.
- The path wasn't in the pilot project's `installed_files` until `4342bd24`, so §1.2a's drift check (`skills/sdlc-migrate/SKILL.md:199-235`) never looked at it.
- The 2026-07-09 audit (`7176c3b7`) restored only `dispatch_prompt_templates`. v2.0.0's §2.1b key-level merge (:476-525) added `rules` and `maintenance`, because those key names didn't clash with the project's.
- What remains is two documents under one header. The pilot project's file keeps its own `id`, `description` and `pattern: entries`, with upstream's `rules:` added at line 291 (§2.1b keeps project keys, :487). Tidying it is the pilot project's job. It shows that a key-level merge can't tell "the project extended upstream's file" from "the project's file has upstream's name".

**Suggested fixes** (choose when planning):
1. **sdlc-ingest:** before creating a knowledge file, check the target path against upstream's names (`skeleton/manifest.json` source_files, or `installed_files` in the project manifest). If the name belongs to upstream, refuse and suggest a different filename. Today the skill reads existing files only to remove duplicates (`skills/sdlc-ingest/SKILL.md:57`, :107-109, :163-166, :219-222), so an empty upstream path looks free.
2. **sdlc-migrate §2.1b:** when the project's file and upstream's share few top-level keys besides the metadata (`id`, `name`, `description`, `pattern`, `category`, …), or their `pattern` values differ, treat it as probably a different document. Ask CD whether to rename the project's file and install upstream's, instead of merging.
3. **Compliance auditor:** check that every rule ID cited in skills and process docs (`AOP<n>` and the other stores' prefixes) matches a `rule_id` in the installed knowledge files. Today it checks only that mapped file paths exist (`skills/sdlc-audit/references/compliance-methodology.md:143`, :153).

#### 12. Templates cite stores a project may have removed (low)

**What happens.** Three upstream files point at knowledge stores that `sdlc-initialize` may delete (`knowledge/README.md:204-210`) or that a project removes later. In those projects the references point to nothing.

**Evidence** (the marking is `action_if_irrelevant`; "absent" means missing in the pilot project):

| File | Store cited | Marked | In the pilot |
|---|---|---|---|
| `templates/test_spec_template.md:165` | `testing/component-catalog.yaml` | `customize` | absent |
| `templates/test_spec_template.md:166` | `testing/timing-defaults.yaml` | `customize` | absent |
| `templates/test_spec_template.md:167` | `testing/tool-patterns.yaml` | `customize` | absent |
| `playbooks/example-playbook.md:41` | `data-modeling/patterns/meta-framework.yaml` | `remove` | absent |
| `playbooks/example-playbook.md:42` | `testing/tool-patterns.yaml` | `customize` | absent |
| `process/knowledge-routing.md:54` | `architecture/pipeline-design-patterns.yaml` | `remove` | absent |

`templates/test_spec_template.md:164` (`gotchas.yaml`) is fine. The knowledge-routing line is in a fenced example of the context map, and the prose at :57 describes it.

**Suggested fix.** Mark the template and playbook lines "if installed", or point them at `[sdlc-root]/knowledge/README.md` for the current list. In `knowledge-routing.md`, build the example from stores marked `keep`.

### Framework agents

#### 6. Upstream's own agents break the `\\n` frontmatter rule (low)

**What happens.** The framework's two agents don't follow the framework's own frontmatter rule.

**Evidence.**
- `CLAUDE-SDLC.md:296` requires `\\n` (double backslash) for line breaks in an agent's `description`. It says a single `\n` "silently breaks Claude Code's frontmatter parser".
- `agents/sdlc-reviewer.md:43` checks for the same rule.
- `templates/agent-template.md:3` follows it: 10 double, no single.
- But `agents/sdlc-reviewer.md:3` and `agents/sdlc-compliance-auditor.md:3` each have 16 single `\n` and no `\\n`, so sdlc-reviewer would flag its own file.
- The pilot project's copies use `\\n`, because its 2026-07-07 trim converted them. So they differ from upstream's in every line break, and any upstream change to either file becomes a merge.
- Not checked: whether the parser claim is still true in current Claude Code.

**Suggested fix.** Find out which side is right. If the rule holds, change both agents to `\\n` and check the other agent files z-sdlc ships. If Claude Code now reads single `\n` correctly, change the rule in `CLAUDE-SDLC.md:296`, `templates/agent-template.md` and `agents/sdlc-reviewer.md:43` instead. Then add a check (test or lint) that runs upstream's agents against the rule.

### Factory bundle

#### 8. Re-render after changing `stack.profile` (medium; fixed by `5da9dd8`, `process/factory.md` Enablement step 2)

**What happens.** `factory-image.yml` is rendered from `factory.json`'s `stack.profile` (`bundles/factory/tree/templates/factory-image.yml:9`, `paths: [".github/factory/profiles/%{stack.profile}/Dockerfile"]`, and :41). If the profile changes and nobody re-renders, the workflow keeps watching the old profile's Dockerfile.

**Evidence.** The pilot project changed `python-node` to `dotnet-node`. `factory-image.yml` kept watching `profiles/python-node/Dockerfile` until `render.py` ran, and `render.py --check` caught it. At v2.0.0, `process/factory.md:353-355` says "after each settings change, run render.py". But step 2 (:367-372), where the profile is chosen, and § Stack Profiles (:326-346) don't say that the workflows depend on it.

**Status.** Covered in this tree's uncommitted work as of 2026-10-13. In `git diff -- process/factory.md`, step 2 now reads: "The profile is rendered into `factory-image` (it builds that profile's `Dockerfile`), so render after choosing it, or CI's render check fails."

**Suggested fix.** None. Confirm that the sentence ships in the next tag.

#### 9. The bundle's tests leave Python bytecode to commit (low)

**What happens.** Running the bundle's tests writes `__pycache__/*.pyc` under `.github/factory/`. Enablement step 10's CI command is `python -m unittest discover -s .github/factory/tests` (`process/factory.md:425-427`). The pilot project's migration also ran these tests before committing (changelog entry item 7: "268 passed, 2 skipped"). The bundle doesn't ship a `.gitignore` for these files: there is none in `bundles/factory/tree/` at v2.0.0, nor in this release. A project's root `.gitignore` may not cover Python.

**Evidence.**
- The pilot project is a .NET/TypeScript repository, and it had 36 `.pyc` files about to be committed. The migration audit caught them, and `4342bd24` added `__pycache__/` and `*.pyc` to the root `.gitignore` (changelog entry item 11).
- Upstream already expects the folder to appear: `bundles/factory/tree/tests/test_render.py:99` skips `__pycache__` when it copies the tree.
- Enablement's step 2 (since `5da9dd8`) adds `.factory/` to the ignores it asks for, but not bytecode.

**Suggested fix.** Ship `bundles/factory/tree/.gitignore` containing `__pycache__/` and `*.pyc`, installed as `.github/factory/.gitignore`, and mention it next to the `.factory/` line in Enablement. Check that the code that installs and migrates the `tree` files copies dotfiles.

### Process docs

#### 10. `process/external-review-gate.md` has a broken path (low)

**What happens.** `process/external-review-gate.md:95` (v1.8.1: :90) points at `[sdlc-root]/../skills/sdlc-port-opencode/references/local-model-serving.md`. That path is right only in a `.claude/sdlc` install, where `.claude/sdlc/../skills` is `.claude/skills`. With `ops/sdlc` it becomes `ops/skills/…`, which doesn't exist, and in the z-sdlc source it points outside the repository. The file is installed at `.claude/skills/sdlc-port-opencode/references/local-model-serving.md` (`skeleton/manifest.json:259`).

**Suggested fix.** Cite the installed path, `.claude/skills/sdlc-port-opencode/references/local-model-serving.md`, which is how other docs cite skill files (for example §4.5c's `.claude/skills/sdlc-archive/scripts/changelog_archive.py`).

#### 11. Upstream's auditor flags upstream's adapter doc (low)

**What happens.** The compliance auditor's phrasing-contract check treats any `memory_search(` in skills, agents or process docs as a **critical** finding (`agents/sdlc-compliance-auditor.md:173-180`). `process/adapter-lifecycle-protocol.md:151` uses that string in inline backticks, as an example of what an adapter produces. The exceptions (:182-187) cover only fenced code blocks and four named files, so upstream's own doc fails upstream's own check.

**Evidence.** The pilot project's post-migration compliance audit raised it.

**Suggested fix.** Add `process/adapter-lifecycle-protocol.md` to the exceptions, since it documents adapter output. Alternatively, put the example in a fenced block, which the existing exception already covers.

## Recommended next step

Work it the way z-sdlc changes itself (`CLAUDE.md` § When Editing This Repo), not through the SDLC planning skills, which this repository doesn't use for its own work (CD, 2026-10-13):
- Settle the open questions below with CD first for the behavior changes: items 1, 3, 4 and 13, with 5 and 7 alongside since they also edit `skills/sdlc-migrate/SKILL.md`. Item 3 decides how every later fix reaches projects; 4 and 13 both turn on how an absent upstream file is handled; 1 changes a script every migration runs without asking.
- Make each fix as a direct framework edit, with its `process/sdlc_changelog.md` entry in the same step, and tests where a script changes (`tests/test_changelog_archive.py` for item 1).
- Run `sdlc-reviewer` on each changed skill or agent, and the consistency checks (§ Consistency Checks) after each batch.
- Commit with the conventional types and scopes in § Commit Convention. The release type follows § Versioning (item 3 changes migration behavior); tags only on CD's request.

The rest are small local edits, each with its own changelog entry: 2, 6, 9, 10, 11 and 12. Item 8 needs only a check that the working-tree text ships. The receiving session may split this file into separate handoffs if that's easier to track.

## Open questions

- **Item 1:** should the script accept the other heading forms or refuse them? Accepting is kinder to projects. Refusing keeps one documented format, and `release.yml:99` already assumes that format.
- **Item 3:** which fix: follow the target tag's procedure through `git show`, or install the new skill first and run again? And how do projects on v2.0.0 or earlier find out (release notes, README)?
- **Item 4:** do other upstream paths, in the pilot project or others, hold a project's document under upstream's name? A one-time scan comparing top-level keys with upstream's would show it.
- **Item 6:** does Claude Code's frontmatter parser still break on a single `\n`?
- **Item 9:** factory jobs also run Python from `.github/factory/`. The working-tree Enablement text says "a run that leaves an untracked file isn't published". Can bytecode written during a run trip that?
- **Item 13:** what should the manifest field be called, who writes it, and how should an absent `keep` file be handled?

## Out of scope

- **The pilot project's own follow-ups:** the hosted fixtures job, filling in `Depends on` for each deliverable, splitting its merged `agent-orchestration-patterns.yaml`, and the CODEOWNERS step of Enablement.
- **Why the pilot project's 2026-05 retrofit install lacked the `keep`-marked `agent-orchestration-patterns.yaml`.** It was a one-off, and items 4 and 13 cover the general case.
- **This tree's uncommitted factory work:** the `dotnet-node` profile, `render.py`, `workflow_policy.py`, the templates and tests, and `process/factory.md`. Another session owns it.
