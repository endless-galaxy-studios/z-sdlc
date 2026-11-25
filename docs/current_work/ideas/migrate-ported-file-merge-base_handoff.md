---
type: handoff
slug: migrate-ported-file-merge-base
created: 2026-10-15
status: pending: nothing built (cross-checked 2026-11-25)
trigger: issue
recommended_next_skill: direct-dispatch
source_session_summary: "The incubator's migration from v1.9.0 to v2.1.0 (2026-10-15) found four files it had ported from z-sdlc before the release. sdlc-migrate had no common base to merge them from, so each was compared by hand"
active_deliverable: null
related_files:
  - skills/sdlc-migrate/SKILL.md
---

# sdlc-migrate has no merge base for a file a project ported before the release

## Progress (cross-checked 2026-11-25)

Nothing here has been built, and the open questions are unanswered. Since 2026-11-20 migration follows the project's marks, so a fix now goes into §1.2a's drift check and §2.1c's deviation detection rather than a plain three-way merge. Drift checks only the paths in `installed_files`, so a hand-ported file that was never hashed is skipped there (unconfirmed against porting practice).

## Why this is a handoff

The incubator migrated from v1.9.0 to v2.1.0 on 2026-10-15 (its migration session, reported to the z-sdlc session). Some of v2.1.0's files had already reached it earlier, ported from z-sdlc commits ahead of any release and recorded in its `.sdlc-manifest.json` under `ported_commits`. sdlc-migrate's merge compares the project's file with upstream as of the project's `source_version`. Those files didn't exist upstream at v1.9.0, so there was no base: four had to be compared by hand. That session was about the release and the incubator's migration, so this wasn't fixed there.

## What needs to happen

Give sdlc-migrate a base for files a project ported early:
- **The base:** a file a `ported_commits` entry brought in should be merged against upstream as of that commit, not as of `source_version`, where it may not exist.
  - unchanged since the port: take the new release's version as a clean update;
  - edited since the port: a three-way merge like any other drifted file.
- **Where the base comes from:** the manifest already says which commit was ported (`sha`), and sometimes what it was consolidated from (`consolidated_from`). It doesn't say which files each commit brought in. The fix can read that from the commit itself (`git show --name-only <sha>` in the source clone), or the porting step can record the files.
- **After a migration:** the ported entries the target release now contains should be cleared or marked, so the next migration doesn't use them again.

## Evidence

- **`skills/sdlc-migrate/SKILL.md:205-223`:**
  - drift is classified against `installed_files` hashes (`DRIFTED-CLEAN`, `DRIFTED-CONFLICT`, `DRIFTED-ORPHAN`);
  - nothing in the skill reads `ported_commits`: a search for "ported" finds only the adapter lines.
- **The incubator's `.sdlc-manifest.json`:**
  - 11 `ported_commits` entries;
  - the first (`2df932e`, "headless mode", 2026-10-08) carries the note "Applied on top of source_version v1.9.0 without a migration; the next migration should find these changes already present";
  - another (`0810c37`, consolidated from `86b6bd5`) brought the PR description template.
- **The four files compared by hand,** as the incubator's migration session reported them:
  - `process/headless-mode.md`;
  - `process/writing-for-cd.md`;
  - `process/production-gates.md`;
  - `templates/pr_description_template.md`.

## Recommended next step

Open a new session in z-sdlc and run this as **direct dispatch**, with this file as the seed.

Reasoning: the change is to one skill's merge step, and its input (`ported_commits`) already exists. A plan is worth it only if recording the files at port time turns out to be needed.

## Open questions

- **The porting step:** where does it live, and does it update `installed_files` hashes for the files it ports? If it does, a ported file the project hasn't edited already shows as clean. Then the fix is only for edited ones.
- **Partial ports:** how should a ported commit that the release later changed again be handled? The base is the ported version, and upstream's newer one is the theirs side of the merge.

## Out of scope (do NOT pursue)

- **The dual-audience detection.** The incubator's session also saw sdlc-migrate look for `.claude/skills/ccsdlc-{name}`. That was its installed v1.9.0 copy: v2.0.0 renamed the counterparts, and v2.1.0's skill already looks for `zsdlc-{name}`.
