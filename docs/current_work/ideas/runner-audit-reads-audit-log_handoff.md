---
type: handoff
slug: runner-audit-reads-audit-log
created: 2026-10-16
status: pending
trigger: idea
recommended_next_skill: sdlc-lite-plan
source_session_summary: "The pilot project's operator session, after its v2.1.5 migration, found GitHub had dropped most of the runner audit's hourly runs; CD un-parked reading the organization's audit log"
active_deliverable: null
related_files:
  - bundles/factory/tree/runner_audit.py
  - bundles/factory/tree/create_app.py
  - bundles/factory/tree/tests/test_runner_audit.py
  - process/factory.md
  - docs/current_work/ideas/factory-ci-tier-follow-ups_handoff.md
---

# Handoff: the runner audit reads the organization's audit log

## Why this is a handoff

The runner audit (`runner_audit.py`, Enablement step 12) compares the organization's runner groups with an expected state on a schedule. Each run sees only the state at that moment. Two things go unseen, and `factory.md` lists both: anything done and undone between two runs, and everything during a run GitHub never starts.

In the pilot organization, GitHub started only 2 of the audit's first 11 hourly runs. The two that ran started about 8 minutes late and passed in about 10 seconds. None failed: GitHub dropped the rest, which its docs allow for scheduled workflows under load. So the audit went 5 hours without a check. A shorter schedule would only shorten each gap. CD kept the hourly cron (2026-10-16) and asked for this instead.

This was item 15 of `factory-ci-tier-follow-ups_handoff.md`, parked by CD on 2026-10-15. CD un-parked it on 2026-10-16, and item 15 now points here. The source session was the pilot project's migration to v2.1.5 and its CI runs. None of that is part of this work.

## What needs to happen

Each audit run reads the organization's audit log since the last run and alarms on runner changes the expected state wouldn't allow. With a cursor (a record of the last event already read), a dropped run only delays the alarm, because the next run reads what it missed.

- **The shape CD chose (2026-10-15):** alarm when the CI tier's runner-registration App registers or removes a runner outside the CI tier's group, or changes any runner group, read from the audit log since the last run.
- **Recommended in the source session, not yet decided by CD:**
  - Add the log next to the state comparison, not in place of it. The state check catches what's wrong now, including what the log doesn't record or what happened before the cursor began. The log catches what came and went between runs. The two checks are level-triggered and edge-triggered: each covers the other's misses.
  - Keep it in the scheduled workflow, hourly, rather than an always-on service. With a cursor, a dropped run loses nothing. An always-on watcher couldn't run on the runner host, which holds the key it guards against, so it would need another host and a liveness check of its own.
- **Touches:**
  - `create_app.py`: `AUDITOR_PERMISSIONS` (line 46) adds the organization's Administration permission, read. The manifest key is presumably `organization_administration`; check it. `auditor_done()` (line 195) checks the granted set equals it.
  - `runner_audit.py`: a log step in `check`, the cursor, the docstring's "What it doesn't see" (line 22), and the `CRON` comments (lines 70–71 and 372).
  - `process/factory.md` Enablement step 12: drop "The audit doesn't read it yet" (line 720). Say what Administration read also lets the auditor read: the organization's settings, and its whole audit log, not just runners.
  - `tests/test_runner_audit.py`.
  - As with the other follow-ups, fixes go in the bundle and then to the incubator with `zsdlc-import-factory --to-incubator`.

## Evidence

- **The permission (checked 2026-10-16):** GitHub's "Permissions required for GitHub Apps" page lists `GET /orgs/{org}/audit-log` under Organization permissions for "Administration", read, for user access tokens and installation access tokens. The endpoint's own page names only OAuth app tokens and classic personal access tokens with `read:audit_log`, and says the authenticated user must be an organization owner. That reads as the user-token case. It hasn't been tried with the auditor's installation token.
- **Seen working (2026-10-15, from item 15):** an organization owner's token answers 200 and records `org.register_self_hosted_runner`.
- **The endpoint's limits (its page):** 1,750 queries an hour per user and IP address. By default it returns up to 30 events from the past three months; older events need `phrase` with a `created` qualifier.
- **The dropped runs:** the pilot organization's audit, from 2026-10-15T19:48Z to 2026-10-16T06:31Z. After two manual runs at setup, scheduled runs started only at 22:25Z and 01:26Z, against a `17 * * * *` schedule. The workflow was active throughout.
- **Code:** `runner_audit.py:25` and `:71`, and `process/factory.md:719–720`, say the log would close the gap and isn't read yet.

## Recommended next step

Open a new session and run **`/sdlc-lite-plan`** with this file as the seed.

Reasoning: CD has already chosen what to alarm on, so the shape is clear. But the work spans several files and widens a security credential's reach, so a reviewed plan is worth having before any code.

## Open questions

- **The test that settles the permission.** Grant the auditor App Administration read, then call `GET orgs/<org>/audit-log?phrase=action:org.register_self_hosted_runner&per_page=1` with its installation token. A 200 means the design holds. A 403 means it needs an owner's classic token with `read:audit_log`, which is tied to one person; bring that back to CD before going on.
- **Where the cursor lives.** The workflow file is regenerated and holds the expected state. Neither factory App can write workflows, and the workflow's own token has only `issues: write`. The cursor has to survive dropped runs, and the key the audit guards against must not be able to write it. Options:
  - the start time of the last successful run, read from the Actions API (adds `actions: read` to the workflow);
  - a fixed, overlapping window, de-duplicated through the alarm issue;
  - something else.
- **The first run:** with no cursor, how far back it reads.
- **Which `action:` names cover a group change.** Not just `org.register_self_hosted_runner`: a group created, deleted or renamed, its visibility, repositories added or removed, its workflow restriction, a runner moved in or out. List them and confirm each one appears in the log.
- **Telling the CI App's normal work apart.** The CI App registers and removes just-in-time runners in its own group all day. Each registration event has to say which group (and which actor), or the alarm can't tell normal from outside. Check what the event carries.
- **Log delay.** If events reach the log minutes after they happen, a cutoff at the last run's start can miss one. Overlap the window and de-duplicate.
- **Paging across a busy CI hour:** many just-in-time registrations, at 30 events a page by default.

## Out of scope (do NOT pursue)

- **The schedule.** CD kept it hourly at :17 (2026-10-16).
- **Streaming the audit log to an outside store** (push instead of poll). It moves the scheduled job somewhere else rather than removing it.
- **The other items in `factory-ci-tier-follow-ups_handoff.md`.**
