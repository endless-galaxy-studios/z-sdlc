# Recovery / Emergency Restore

If `/sdlc-migrate` crashes, is interrupted, or leaves the workspace in an inconsistent state, use this section to diagnose and recover. Migration is designed to be resumable — most scenarios resolve via re-running the skill.

## Step 1: Diagnose

**Transaction log** (authoritative timeline):
```bash
tail -n 200 .sdlc-transaction-log | jq -c 'select(.run_id | startswith("migrate-"))'
# Last `run_start` marks the crashed migration run
# Last `mutation` event shows what was last committed
# Presence of `checkpoint: point_of_no_return` tells you whether mutations were attempted
```

**Manifest version:**
```bash
jq -r '.source_version' .sdlc-manifest.json
```
Authoritative post-migration version. If this matches the intended `[target_tag]`, migration completed. If it still shows the old version, Phase 4.5 didn't run.

**Source clone state:**
```bash
ls /tmp/z-sdlc-migrate/ 2>/dev/null
```
If present, the temp clone wasn't cleaned up — may indicate crash during or before Phase 4.6. Safe to delete manually if the migration is resolved.

**Drift decisions** (if §1.2a detected any):
```bash
grep -c '"event":"drift_decision"' .sdlc-transaction-log
# If drift was detected but fewer drift_decision events than drift_detected events,
# some files have unresolved drift — they weren't handled before the crash
```

## Step 2: Match state to recovery action

| State | Recovery Action |
|-------|-----------------|
| Crash before point_of_no_return (Phase 0–1 events, no `checkpoint: point_of_no_return` in log) | **Safe — no recovery needed.** Re-run `/sdlc-migrate` from the top. Phase 0 and Phase 1 are idempotent. |
| Crash after point_of_no_return, manifest updated to `[target_tag]` | **Migration completed.** Any remaining issues are audit-level. Dispatch `sdlc-compliance-auditor` to identify. |
| Crash after point_of_no_return, manifest still at old version | **Operational writes partial.** Re-run `/sdlc-migrate` — it detects the version skew and completes from the first unwritten file. PROJECT-SECTION marker re-extraction handles already-written files correctly. |
| Crash during §2.1 direct copy | **File-level idempotency saves you.** Re-run — each direct copy is idempotent (same git show → same content). Previously copied files will simply re-copy with the same result. |
| Crash during §2.1b knowledge YAML merge | **Knowledge files at intermediate state.** Re-run — key-level merge is idempotent when re-applied against its own output. Use git diff to verify files look correct after re-run. |
| Drift decisions lost to crash (drift_detected without matching drift_decision) | **Re-run `/sdlc-migrate`.** Drift re-detected at §1.2a; CD re-prompted with same options. Prior decisions not preserved across crashes. |
| Temp clone at `/tmp/z-sdlc-migrate/` from prior run | **Clean up manually:** `rm -rf /tmp/z-sdlc-migrate/` before re-running. Phase 0 would have cloned fresh. |

## Step 3: Never do these things

- **Do not edit `.sdlc-manifest.json` to match what you think the state should be.** If the manifest is wrong, re-run migrate; don't synthesize state.
- **Do not delete `[sdlc-root]/` and re-run `/sdlc-initialize`.** That loses drift-detection history and treats the workspace as greenfield. Always prefer re-running migrate for mid-migration recovery.
- **Do not ignore drift warnings from §1.2a.** They signal files where manual edits will be silently overwritten if you proceed without deciding.

## Step 4: Absolute last resort

If the workspace is so corrupted that re-running migrate cannot resolve it:

1. Back up: `cp -r [sdlc-root] [sdlc-root].backup-{date}` and `cp .sdlc-manifest.json .sdlc-manifest.backup-{date}.json`
2. Run `/sdlc-initialize` in repair mode to rebuild the skeleton.
3. Manually re-apply project customizations from the backup (PROJECT-SECTION blocks, agent-context-map additions, discipline parking lot entries).

This path loses `installed_files` hash history and resets drift-detection baselines — use only when no other recovery works.
