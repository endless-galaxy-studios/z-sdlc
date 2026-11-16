---
type: handoff
slug: factory-ci-tier-follow-ups
created: 2026-10-15
status: done (2026-11-16), not released
trigger: issue
recommended_next_skill: none
source_session_summary: "The pilot project's reviews of the v2.1.0 release (the CI tier, the runner audit) found minor issues that can follow the tag. None is a blocker; each is recorded here so it isn't lost"
active_deliverable: null
related_files:
  - bundles/factory/tree/host/ci_launcher.py
  - bundles/factory/tree/host/setup.sh
  - bundles/factory/tree/host/setup-ci.sh
  - bundles/factory/tree/runner_audit.py
  - bundles/factory/tree/tests/test_ci_launcher.py
  - process/factory.md
---

# The factory CI tier and runner audit: follow-ups after v2.1.0

The pilot project's release reviews (rounds 1 to 3, 2026-10-15) passed these as minor, to follow the tag. Each says what's wrong, what it costs, and where to start. Fixes go in the bundle (`bundles/factory/tree/`) and then to the incubator with `zsdlc-import-factory --to-incubator`.

**Done (2026-11-16):** every item but 15, which has its own handoff. Where each fix went, and where it departs from the start written here (items 1, 8, 10 and 12), is in `process/sdlc_changelog.md`, "The CI tier's and the runner audit's follow-ups from v2.1.0's review". Still to do: hand the fixes to the incubator (`--to-incubator`). `sdlc-archive` removes this file once they're released.

## The CI launcher (`host/ci_launcher.py`)

1. **A registration can leak when SIGTERM lands inside `generate-jitconfig`.** GitHub has registered the runner, but the cycle hasn't recorded its ID yet, so neither the cycle's cleanup nor the slot's stop knows to remove it. It stays registered and offline until GitHub ages it out, and the audit counts it against the CI group's most-at-once in the meantime. Start: record a pending marker before the call, and on stop, list the group's runners by the slot's name prefix to find one with no record.
2. **Excess slots are removed without asking whether they're busy.** Lowering `CI_RUNNERS` makes setup `disable --now` every slot above the new count, which kills a job one of them is running. Start: `retire` each one first, and leave a busy one running until its job ends, then disable it.
3. **The image build directory can leak, and old images are removed in the wrong order.** A build that fails leaves its root-only build directory behind. Setup also removes old images before it knows the new one works. Start: clean the build directory in a trap, and remove old images only after the gate's check passes on the new one.
4. **`record_files()` skips a loose old-state directory silently.** It reads `/run/factory-runner/<unit>` only when that directory passes the root-only check, and swallows the check's failure. So `retire` can answer idle while a record there goes unread. Only root can loosen it. Start: in `retire`, an old-state directory that exists but fails the check answers not idle; the cycle can keep skipping it.
5. **A 404 from the wrong organization reads as "gone".** `retire` and the leftover sweep take a 404 on a runner to mean it's already removed. GitHub also answers 404 for an organization the App can't see, so a misconfigured `org` makes `retire` answer idle. Start: trust a 404 only after the organization's runner list has answered 200 in the same call.
6. **The pre-release migration code has no sunset.** `record_files()`'s old `/run` path and `setup-ci.sh`'s carry-over loop serve only hosts upgrading from a pre-release CI tier. Remove both in the release after v2.1.0, once every such host has run v2.1.0's setup and `CI_IDLE_HOURS` + `CI_JOB_HOURS` have passed since, or the host has rebooted (`/run` is tmpfs).

## Host setup (`host/setup.sh`, `host/setup-ci.sh`)

7. **A strict-tier runner can be left stopped when an upgrade's download fails.** Setup stops an idle runner before unpacking a `RUNNER_VERSION` bump. If the download then fails, setup dies and the runner stays stopped until the next run. Start: download and verify first, then stop and unpack.
8. **The label rules live in four places:**
   - `setup.sh`'s refusal of a tier without a label of its own;
   - `ci_launcher.py`'s `SELF_HOSTED_DEFAULTS`, which `jit_labels()` uses;
   - `runner_audit.py`'s `DEFAULT_LABELS_OF_RUNNERS`;
   - the docs.

   They agree today. Start: one list in a file the scripts all read, with a test that the docs name the same labels.
9. **Enablement doesn't say the factory drops GitHub's default labels.** GitHub adds `self-hosted`, the OS and the architecture to every self-hosted runner, and the launcher and the audit both drop them by name. Enablement doesn't say so, so an operator reading a runner's labels in GitHub's UI can't tell which ones the factory set. Start: a line in step 10.

10. **The planning database's address is set in two places.** `planning.json`'s `database.host`/`port` (what the planning job connects to) and `host.conf`'s `PLANNING_DB_HOST`/`PLANNING_DB_PORT` (what its firewall admits) can disagree. Nothing widens when they do: the firewall refuses, and `planning-services.sh` fails with a confusing error. Start: setup's planning branch reads `planning.json` and stops when the two differ, naming both; `host.conf` stays what the firewall is built from.
11. **`setup.sh`'s header still says the planning tier's database port is "on this host's own addresses".** That's no longer true once `PLANNING_DB_HOST` is set. Start: one line in the header.

## The firewall check

12. **An `nftables` upgrade can change the table's fingerprint.** The check already fingerprints `nft -j`'s JSON (chains, rules, set elements), not the printed text. The risk left is that JSON's shape changing across `nft` versions: new fields, or a different order, would read as drift and trip the tier. That fails safe, but it looks like an attack. Start: a note in Enablement step 10's recovery steps (run setup again after an `nftables` upgrade, which records a new fingerprint), or a fingerprint of only the fields that matter.

13. **Nothing tests that `PLANNING_DB_HOST`'s other ports stay closed.** The isolation test proves the planning tier reaches `PLANNING_DB_HOST:PLANNING_DB_PORT`, but not that the host's other probe ports are refused. The rule refuses them by construction, and the smoke run probes only from the strict tier. Start: the planning branch of the isolation test probes `PROBE_PORTS` on `PLANNING_DB_HOST`, the database port excepted.

## The runner audit (`runner_audit.py`)

14. **A malformed answer from GitHub can raise `TypeError` in `check`.** It isn't in `main()`'s handled exceptions, so it prints a traceback and exits 1 (drift) rather than 2 (couldn't read). The run still fails and alerts, but under the wrong name. Start: validate each field's type where it's read, or add `TypeError` and `KeyError` to the tuple.
15. **The audit doesn't read the organization's audit log.** Parked by CD on 2026-10-15. CD un-parked it on 2026-10-16, and it moved, with everything known here, to its own handoff: `runner-audit-reads-audit-log_handoff.md`.
16. **A renamed group reads as one gone and one new.** Groups are keyed `<name>#<id>`, so a rename reports two drifts that look worse than what happened. Start: match an unexpected key to a missing one by ID, and report a rename.

## Tests

17. **The real-Docker smoke test pulls from Docker Hub.** `FACTORY_DOCKER_SMOKE=1` pulls a base image on each run, which is slow and can hit Docker Hub's rate limit, and the test then fails for a reason unrelated to the job flags. Start: build the smoke image `FROM scratch` with a static binary, or skip with a clear message when the pull fails.
