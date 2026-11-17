"""Release gates (z-sdlc process/factory.md D4 rule 13): the broker's own checks of a release gate's run, its wait for
production, the release-PR case of provenance, and `timed-out` receipts. Real git repositories, a mocked GitHub, the fake
host. Carried over from the third project's broker tests (test_release_gate.py: the run, release-PR refusals, request
shape, history refusals, run failures, timed-out receipts, provenance and the declarations)."""

import unittest

import fakes
import factory_op as fo
import gates
from fakes import TOKEN
from test_broker_gate import GateBase

PR, ISSUE, GATE = 7, 3, "G1"
RELEASE_PR = 41
PLAN_PATH = "docs/current_work/planning/d99_thing_plan.md"
PLAN = """# D99: Thing

### Phase 1: Code

Write it.

### Gate G1: The web service reaches production

**After:** Phase 1. **Changes production:** yes.
**Release:** the next phase needs the code live

```gate-ops
{"steps": [{"op": "health"}]}
```

### Phase 2: Records

Write the result.
"""


def merged(record, **changes):
    out = dict(record)
    for key, value in changes.items():
        out[key] = {**record[key], **value} if isinstance(value, dict) and isinstance(record.get(key), dict) else value
    return out


class ReleaseBase(GateBase):
    """main is the base commit; the execution branch factory/3-impl adds one commit (README) that is not on main; the release
    PR (#41) merged that commit into release/production with a merge commit, as GitHub's merge button does."""

    def setUp(self):
        super().setUp()
        self.append_baseline(self.state)
        self.app, self.approver = self.cfg["app_bot_id"], self.cfg["approvers"][0]
        self.E = self.exec_branch({"README": "r2"})
        self.M = self.release_merge(self.E)
        self.repo.fetch()
        self.setup_runs = len(self.env.sandbox.runs)  # GateBase's own capture of the starting state

    def ran(self):
        return [n for n, _ in self.env.sandbox.runs[self.setup_runs:]]

    # -- the repository
    def exec_branch(self, *commits, branch=None):
        self.repo.sh("checkout", "-q", "-b", branch or f"factory/{ISSUE}-impl", "main")
        for changes in commits:
            for path, text in changes.items():
                if text is None:
                    self.repo.sh("rm", "-q", path)
                else:
                    self.repo.write({path: text})
            self.repo.sh("add", "-A")
            self.repo.sh("commit", "-q", "-m", "work")
        head = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "release/production")
        return head

    def release_merge(self, sha, number=RELEASE_PR):
        self.repo.sh("checkout", "-q", "release/production")
        self.repo.sh("merge", "-q", "--no-ff", "-m", f"Merge pull request #{number} from o/pin", sha)
        return self.repo.head()

    def later_release(self, files, number=2):
        """Another release after the gate's, as the normal path ships one: a branch of main, merged into main, then into the
        release branch. Its second parent is in main, so provenance accepts it."""
        self.repo.sh("checkout", "-q", "-b", f"later{number}", "main")
        self.repo.write(files)
        self.repo.sh("add", "-A")
        self.repo.sh("commit", "-q", "-m", f"later {number}")
        self.repo.sh("checkout", "-q", "main")
        self.repo.sh("merge", "-q", "--no-ff", "-m", f"Merge pull request #{number} into main", f"later{number}")
        self.repo.sh("checkout", "-q", "release/production")
        self.repo.sh("merge", "-q", "--no-ff", "-m", f"Merge pull request #{number} from o/later", f"later{number}")
        return self.repo.head()

    def release_deleting_readme(self):
        """Make the gate's release the deletion of README: the execution branch deletes it and its release PR merged that."""
        self.repo.sh("reset", "-q", "--hard", self.repo.base)
        self.repo.sh("checkout", "-q", "-b", "factory/9-impl", "main")
        self.repo.sh("rm", "-q", "README")
        self.repo.sh("commit", "-q", "-m", "delete")
        self.E = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "release/production")
        self.M = self.release_merge(self.E, number=60)
        self.repo.fetch()

    # -- GitHub
    def pin(self, head=None):
        return gates.pin_branch(PR, GATE, head or self.E)

    def release_record(self, **changes):
        return merged({"number": RELEASE_PR, "merged": True, "merged_at": "2026-11-06T00:00:00Z", "merge_commit_sha": self.M,
                       "base": {"ref": "release/production"}, "merged_by": {"id": self.approver}, "user": {"id": self.app},
                       "head": {"ref": self.pin(), "sha": self.E, "repo": {"full_name": self.cfg["repo"]}}}, **changes)

    def execution_record(self, sha=None, **changes):
        return merged({"state": "open", "user": {"id": self.app},
                       "head": {"ref": f"factory/{ISSUE}-impl", "sha": sha or self.E, "repo": {"full_name": self.cfg["repo"]}}}, **changes)

    def routes(self):
        return {f"commits/{self.M}/pulls": [{"number": RELEASE_PR, "merge_commit_sha": self.M}],
                f"pulls/{RELEASE_PR}": self.release_record(), f"pulls/{PR}": self.execution_record()}

    def gh(self, merges=(), by=None, extra=None):
        return fakes.github_for(self.cfg, self.repo, merges, approver=by, extra={**self.routes(), **(extra or {})})

    # -- the gate
    def request(self, steps=(), **changes):
        req = {"pr": PR, "gate": GATE, "issue": ISSUE, "attempt": 1, "digest": "d" * 64, "head": self.E, "kind": "release",
               "plan_blob": "b" * 40, "rollback": [], "steps": list(steps),
               "release": {"branch": "release/production", "pr": RELEASE_PR, "merge": self.M}}
        req.update(changes)
        return req

    def health(self):
        return [{"id": "h", "op": "health", "with": {}}]

    def run_gate(self, steps=(), svc=None, req=None, cat=None):
        return fo.execute(self.cfg, gates, cat or self.env.cat, req or self.request(steps), "def", self.approver, 55,
                          fo.ledger_entries(self.cfg["ledger"]), lambda r: gates.sign_receipt(self.env.secret, r), TOKEN,
                          svc or self.services(), self.env.public, host_run="run1")

    def refuses(self, steps=(), svc=None, req=None, cat=None):
        """The refusal's message; nothing was recorded and no step (not even a capture) ran."""
        before, runs = fo.ledger_entries(self.cfg["ledger"]), len(self.env.sandbox.runs)
        with self.assertRaises((fo.Refused, fo.GitError)) as cm:
            self.run_gate(steps, svc, req, cat)
        self.assertEqual(fo.ledger_entries(self.cfg["ledger"]), before)
        self.assertEqual(len(self.env.sandbox.runs), runs)
        return str(cm.exception)

    def recorded(self):
        return fo.recorded_state(fo.ledger_entries(self.cfg["ledger"]), gates, self.env.public)


class ReleaseGateRunsTest(ReleaseBase):
    def test_a_release_gate_checks_waits_and_runs_its_read_steps(self):
        receipt = self.run_gate(self.health())["receipt"]
        self.assertEqual(receipt["status"], "done", receipt)
        self.assertEqual([s["id"] for s in receipt["steps"]], ["h"])  # the broker's own wait is not one of the request's steps
        self.assertEqual(receipt["release_head"], self.M)
        self.assertEqual(receipt["release_gate"]["merge"], self.M)
        self.assertEqual(self.ran(), ["capture-state", "release-wait", "health", "capture-state"])
        self.assertEqual(self.recorded()["release_head"], self.M)

    def test_a_release_gate_without_a_block_only_checks_production(self):
        receipt = self.run_gate()["receipt"]
        self.assertEqual((receipt["status"], receipt["steps"]), ("done", []))
        self.assertEqual(self.ran(), ["capture-state", "release-wait", "capture-state"])

    def test_the_receipt_answers_the_request_the_way_the_hosted_report_job_checks_it(self):
        request = gates.build_request(repo=self.cfg["repo"], issue=ISSUE, pr=PR, plan=PLAN_PATH, plan_blob="b" * 40, plan_text=PLAN,
                                      gate_id=GATE, attempt=1, head=self.E, catalog=self.env.cat, gate_outputs={},
                                      ops_digest="c" * 64, release={"branch": "release/production", "pr": RELEASE_PR, "merge": self.M})
        self.assertEqual(request["kind"], "release")
        signed = self.run_gate(req=request)
        _payload, status = gates.report_result(signed, request, self.env.cat, self.env.public)
        self.assertEqual(status, "done")

    def test_the_wait_sees_the_deployment_of_the_release_heads_code(self):
        later = self.later_release({"web/app.txt": "w2"})
        self.w.add("jobs", "SKIPPED", later)
        dep = self.w.add("web", "BUILDING", later)
        self.w.hooks.append(lambda _w: dep.update(status="SUCCESS") if self.clock.t > 90 else None)
        receipt = self.run_gate(self.health(), svc=self.services([(later, 2, None)]))["receipt"]
        self.assertEqual(receipt["status"], "done", receipt)
        self.assertEqual(receipt["release_gate"]["wait"]["deployed"], "web")
        self.assertEqual(receipt["release_head"], later)

    def test_a_later_release_that_followed_it_is_allowed(self):
        later = self.later_release({"docs/note.md": "n"})
        receipt = self.run_gate(svc=self.services([(later, 2, None)]))["receipt"]
        self.assertEqual(receipt["status"], "done", receipt)
        self.assertEqual(receipt["release_head"], later)

    def test_a_path_the_gate_deleted_that_stays_absent_passes(self):
        self.release_deleting_readme()
        self.assertEqual(self.run_gate()["receipt"]["status"], "done")


class ReleasePrRefusalsTest(ReleaseBase):
    def refuses_record(self, **changes):
        return self.refuses(svc=self.services(gh=self.gh(extra={f"pulls/{RELEASE_PR}": self.release_record(**changes)})))

    def test_a_release_pr_that_isnt_the_apps_refuses(self):
        self.assertIn("isn't the factory App's", self.refuses_record(user={"id": 5}))

    def test_a_release_pr_from_another_branch_refuses(self):
        self.assertIn("isn't from the gate's pinned branch", self.refuses_record(head={"ref": self.pin().replace("G1", "G2")}))

    def test_a_release_pr_from_the_pinned_branch_at_another_commit_refuses(self):
        self.assertIn("not PR #7's head", self.refuses_record(head={"sha": "9" * 40}))

    def test_a_release_pr_from_a_fork_refuses(self):
        self.assertIn("isn't from this repository", self.refuses_record(head={"repo": {"full_name": "evil/fork"}}))

    def test_a_release_pr_into_another_branch_refuses(self):
        self.assertIn("isn't into release/production", self.refuses_record(base={"ref": "main"}))

    def test_an_unmerged_release_pr_refuses(self):
        self.assertIn("isn't merged", self.refuses_record(merged=False))

    def test_a_release_pr_merged_by_a_non_approver_refuses(self):
        self.assertIn("release PR #41 was merged by someone who isn't an approver", self.refuses_record(merged_by={"id": 424242}))

    def test_a_merge_commit_other_than_the_bound_one_refuses(self):
        self.assertIn("isn't the one the request binds", self.refuses_record(merge_commit_sha="8" * 40))

    def test_a_head_that_moved_since_the_request_refuses(self):
        gh = self.gh(extra={f"pulls/{PR}": self.execution_record(sha="7" * 40)})
        self.assertIn("head moved since the request", self.refuses(svc=self.services(gh=gh)))

    def test_a_merged_execution_pr_refuses(self):
        gh = self.gh(extra={f"pulls/{PR}": self.execution_record(merged=True)})
        self.assertIn("isn't open and unmerged", self.refuses(svc=self.services(gh=gh)))

    def test_a_stale_release_pr_is_reported_as_what_it_is(self):
        old = "6" * 40
        stale = self.release_record(head={"ref": gates.pin_branch(PR, GATE, old), "sha": old})
        msg = self.refuses(svc=self.services(gh=self.gh(extra={f"pulls/{RELEASE_PR}": stale})))
        self.assertIn("older commit", msg)
        self.assertIn("production runs that commit", msg)


class ReleaseRequestShapeTest(ReleaseBase):
    def test_a_block_with_a_change_operation_refuses(self):
        self.assertIn("only read operations", self.refuses([{"id": "b", "op": "snapshot-now", "with": {}}]))

    def test_a_block_with_an_unknown_operation_refuses(self):
        self.assertIn("isn't in the installed catalog", self.refuses([{"id": "x", "op": "deploy", "with": {}}]))

    def test_a_block_with_a_rollback_refuses(self):
        req = self.request(self.health(), rollback=[{"id": "r", "op": "health", "with": {}}])
        self.assertIn("runs no rollback", self.refuses(req=req))

    def test_a_binding_for_another_branch_refuses(self):
        req = self.request()
        req["release"]["branch"] = "main"
        self.assertIn("needs its merged release PR", self.refuses(req=req))

    def test_a_request_without_a_binding_refuses(self):
        req = self.request()
        del req["release"]
        self.assertIn("needs its merged release PR", self.refuses(req=req))

    def wait_step(self, step_id="w", sha=None):
        return {"id": step_id, "op": "release-wait", "with": {"sha": sha or self.E}}

    def test_a_block_that_opens_with_release_wait_uses_it_as_the_gates_wait(self):
        receipt = self.run_gate([self.wait_step(), *self.health()])["receipt"]
        self.assertEqual(receipt["status"], "done", receipt)
        self.assertEqual([x["id"] for x in receipt["steps"]], ["w", "h"])
        self.assertEqual(self.ran(), ["capture-state", "release-wait", "health", "capture-state"])  # one wait, not two
        self.assertEqual(receipt["release_gate"]["wait"], receipt["steps"][0]["outputs"])

    def test_a_release_wait_later_in_the_block_runs_after_the_brokers_own(self):
        receipt = self.run_gate([*self.health(), self.wait_step("late")])["receipt"]
        self.assertEqual(receipt["status"], "done", receipt)
        self.assertEqual(self.ran(), ["capture-state", "release-wait", "health", "release-wait", "capture-state"])

    def test_a_block_step_named_release_wait_does_not_collide_with_the_brokers_wait(self):
        receipt = self.run_gate([{"id": "release-wait", "op": "health", "with": {}}])["receipt"]
        self.assertEqual((receipt["status"], [x["id"] for x in receipt["steps"]]), ("done", ["release-wait"]))
        started = [e["step"] for e in fo.ledger_entries(self.cfg["ledger"]) if e["event"] == "step-start"]
        self.assertEqual(started, ["release_wait", "release-wait"])  # the broker's id can't be a plan's: step ids have no underscore

    def test_a_first_release_wait_whose_commit_is_in_the_history_still_waits_for_the_branch_head(self):
        later = self.later_release({"docs/note.md": "n"})
        receipt = self.run_gate([self.wait_step(sha=self.repo.base)], svc=self.services([(later, 2, None)]))["receipt"]
        self.assertEqual(receipt["status"], "done", receipt)
        self.assertEqual(receipt["steps"][0]["outputs"]["head"], later)  # not the base it was given, not the gate's commit

    def test_a_first_release_wait_cannot_wait_for_anything_but_the_branch_head(self):
        receipt = self.run_gate([self.wait_step(sha="1" * 40)])["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("release PR not merged yet", receipt["steps"][0]["why"])

    def slow_catalog(self):
        cat = fakes.catalog_dict()
        cat["operations"]["health"]["timeout_s"] = 2900
        return fakes.load(cat)

    def test_the_budget_counts_one_wait_when_the_block_opens_with_its_own(self):
        cat, h = self.slow_catalog(), {"id": "h", "op": "health", "with": {}}
        self.assertIsNone(fo.budget_problem(cat, self.request([self.wait_step()] + [h] * 4)))
        self.assertIsNotNone(fo.budget_problem(cat, self.request([h] * 4 + [self.wait_step()])))

    def test_the_worst_case_has_to_fit_the_gate_runs_job(self):
        cat, h = self.slow_catalog(), {"id": "h", "op": "health", "with": {}}
        self.assertIsNone(fo.budget_problem(cat, self.request([h] * 4)))
        self.assertIn("more than the gate run's", fo.budget_problem(cat, self.request([h] * 5)))
        steps = [{**h, "id": f"h{i}"} for i in range(5)]
        self.assertIn("more than the gate run's", self.refuses(steps, cat=cat))

    def test_the_broker_never_counts_less_than_its_own_overhead(self):
        cat = fakes.load(fakes.catalog_dict(gate_overhead_s=0))
        self.assertEqual(fo.budget_problem(cat, self.request([{"id": "h", "op": "health", "with": {}}])),
                         fo.budget_problem(self.env.cat, self.request([{"id": "h", "op": "health", "with": {}}])))


class ReleaseHistoryRefusalsTest(ReleaseBase):
    def exec_other(self, changes):
        self.repo.sh("checkout", "-q", "-b", "other", "main")
        self.repo.write(changes)
        self.repo.sh("add", "-A")
        self.repo.sh("commit", "-q", "-m", "other")
        head = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "release/production")
        return head

    def test_a_merge_whose_second_parent_is_not_the_gates_commit_refuses(self):
        merge = self.release_merge(self.exec_other({"docs/other.md": "o"}), number=50)
        self.repo.fetch()
        req = self.request()
        req["release"]["merge"] = merge
        gh = self.gh(extra={f"pulls/{RELEASE_PR}": self.release_record(merge_commit_sha=merge)})
        self.assertIn("as its second parent", self.refuses(svc=self.services(gh=gh), req=req))

    def test_a_merge_that_is_not_in_the_branchs_history_refuses(self):
        self.repo.sh("checkout", "-q", "-b", "elsewhere", "main")
        self.repo.sh("merge", "-q", "--no-ff", "-m", "Merge pull request #43 from o/elsewhere", self.E)
        elsewhere = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "release/production")
        self.repo.git.fetch("x", "+refs/heads/elsewhere:refs/factory/elsewhere")
        req = self.request()
        req["release"]["merge"] = elsewhere
        gh = self.gh(extra={f"pulls/{RELEASE_PR}": self.release_record(merge_commit_sha=elsewhere)})
        self.assertIn("isn't in release/production's history", self.refuses(svc=self.services(gh=gh), req=req))

    def test_a_merge_that_came_in_through_another_merges_second_parent_refuses(self):
        self.repo.sh("reset", "-q", "--hard", self.repo.base)
        self.repo.sh("checkout", "-q", "-b", "side", self.repo.base)
        self.repo.sh("merge", "-q", "--no-ff", "-m", "Merge pull request #41 from o/pin", self.E)
        m = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "release/production")
        self.repo.sh("merge", "-q", "--no-ff", "-m", "Merge pull request #42 from o/side", "side")
        self.M = m
        self.repo.fetch()
        gh = self.gh(extra={f"pulls/{RELEASE_PR}": self.release_record(merge_commit_sha=m)})
        self.assertIn("first-parent history", self.refuses(svc=self.services(gh=gh), req=self.request()))

    def test_a_later_release_that_changed_a_path_refuses_naming_it(self):
        later = self.repo.merge_pr({"README": "r3"}, via_main=False)
        self.assertIn("no longer has this gate's content: README", self.refuses(svc=self.services([(later, 2, None)])))

    def test_a_revert_since_refuses_naming_the_path(self):
        self.repo.sh("revert", "--no-edit", "-m", "1", self.M)
        self.assertIn("no longer has this gate's content: README", self.refuses())

    def test_a_deleted_path_that_a_later_release_brought_back_refuses(self):
        self.release_deleting_readme()
        later = self.repo.merge_pr({"README": "back"}, via_main=False)
        self.assertIn("no longer has this gate's content: README", self.refuses(svc=self.services([(later, 2, None)])))

    def test_content_the_execution_pr_never_touched_may_change(self):
        later = self.later_release({"docs/note.md": "n"})
        self.assertEqual(self.run_gate(svc=self.services([(later, 2, None)]))["receipt"]["status"], "done")


class ReleaseRunFailuresTest(ReleaseBase):
    def test_the_branch_head_moving_during_the_wait_fails_the_gate(self):
        later = self.later_release({"docs/note.md": "n"})
        moved = fakes.Seq([{"name": "release/production", "commit": {"sha": self.M}},
                           {"name": "release/production", "commit": {"sha": later}}])
        receipt = self.run_gate(svc=self.services(gh=self.gh(extra={"branches/release%2Fproduction": moved})))["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("the release wait failed: head moved", receipt["reason"])
        self.assertEqual(receipt["steps"], [])

    def test_the_execution_prs_head_moving_during_the_gate_fails_it(self):
        # The execution PR is read three times: before the checks, by provenance's pinned-branch case, and after the last step.
        moved = fakes.Seq([self.execution_record(), self.execution_record(), self.execution_record(sha="5" * 40)])
        receipt = self.run_gate(svc=self.services(gh=self.gh(extra={f"pulls/{PR}": moved})))["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("head moved during the gate", receipt["reason"])
        self.assertTrue(receipt["reason"].startswith("PRODUCTION NEEDS CD:"))

    def test_a_failed_read_step_says_the_release_is_live_and_nothing_was_changed(self):
        self.w.add("cache", "CRASHED", None)
        receipt = self.run_gate(self.health())["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["rollback"], [])
        self.assertIn("h failed", receipt["reason"])
        self.assertIn("live from CD's merge", receipt["reason"])

    def test_a_release_the_host_never_deploys_fails_the_wait(self):
        later = self.later_release({"web/app.txt": "w2"})
        self.w.add("jobs", "SKIPPED", later)
        self.w.add("web", "FAILED", later)
        receipt = self.run_gate(svc=self.services([(later, 2, None)]))["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("the release wait failed", receipt["reason"])


class TimedOutReceiptTest(ReleaseBase):
    def slow_on(self, op):
        inner = self.env.sandbox

        class Slow:
            def run(s, name, *a, **kw):
                return fo.StepResult("timed-out", why="timed out") if name == op else inner.run(name, *a, **kw)
        return fo.Services(self.gh(), self.repo.git, lambda run: Slow())

    def test_a_timed_out_read_step_signs_timed_out_and_blocks_until_resolved(self):
        receipt = self.run_gate(self.health(), svc=self.slow_on("health"))["receipt"]
        self.assertEqual(receipt["status"], "timed-out")
        self.assertIn(receipt["status"], gates.RECEIPT_STATUSES)
        self.assertEqual(receipt["rollback"], [])
        self.assertTrue(receipt["reason"].startswith("PRODUCTION NEEDS CD:"))
        self.assertIn("resolve run1", receipt["reason"])
        self.assertIn("live from CD's merge", receipt["reason"])
        self.assertEqual(receipt["release_head"], self.M)
        self.assertEqual(receipt["release_gate"]["release_pr"], RELEASE_PR)
        self.assertIn("deployed", receipt["release_gate"]["wait"])  # the wait had finished before the step timed out
        self.assertEqual(fo.unfinished(fo.ledger_entries(self.cfg["ledger"])), ["run1"])

    def test_a_timed_out_wait_signs_timed_out_with_no_request_steps(self):
        receipt = self.run_gate(self.health(), svc=self.slow_on("release-wait"))["receipt"]
        self.assertEqual((receipt["status"], receipt["steps"]), ("timed-out", []))
        self.assertEqual((receipt["release_head"], receipt["release_gate"]["merge"]), (self.M, self.M))
        self.assertEqual(fo.unfinished(fo.ledger_entries(self.cfg["ledger"])), ["run1"])


class ReleaseProvenanceTest(ReleaseBase):
    def failures(self, **routes):
        return fo.provenance_failures(self.cfg, self.gh(extra=routes), self.repo.git, self.repo.base, self.repo.head())

    def reason(self, **routes):
        fails = self.failures(**routes)
        self.assertEqual(len(fails), 1, fails)
        return fails[0][1]

    def test_a_release_prs_merge_of_a_pinned_commit_that_isnt_in_main_passes(self):
        self.assertFalse(self.repo.git.is_ancestor(self.E, self.repo.git.main_sha()))
        self.assertEqual(self.failures(), [])

    def test_a_pr_that_isnt_the_apps_refuses(self):
        self.assertIn("not the factory App's", self.reason(**{f"pulls/{RELEASE_PR}": self.release_record(user={"id": 5})}))

    def test_a_pin_name_that_doesnt_match_the_commit_refuses(self):
        wrong = gates.pin_branch(PR, GATE, "1" * 40)
        self.assertIn("name and head are not the commit", self.reason(**{f"pulls/{RELEASE_PR}": self.release_record(head={"ref": wrong})}))

    def test_a_pr_whose_head_is_not_the_commit_it_brought_in_refuses(self):
        self.assertIn("name and head are not the commit",
                      self.reason(**{f"pulls/{RELEASE_PR}": self.release_record(head={"sha": "4" * 40})}))

    def test_a_pin_from_a_fork_refuses(self):
        self.assertIn("not from this repository",
                      self.reason(**{f"pulls/{RELEASE_PR}": self.release_record(head={"repo": {"full_name": "evil/fork"}})}))

    def test_a_pin_that_names_no_execution_pr_refuses(self):
        self.assertIn("not a factory execution PR", self.reason(**{f"pulls/{PR}": self.execution_record(head={"ref": "feature/x"})}))
        self.assertIn("not a factory execution PR", self.reason(**{f"pulls/{PR}": self.execution_record(user={"id": 5})}))

    def test_a_branch_that_only_looks_like_a_pin_refuses(self):
        for ref in ("factory/release/7-G1-abc", f"factory/release/7-G0-{self.E[:12]}", f"factory/release/x-G1-{self.E[:12]}",
                    f"factory/releases/7-G1-{self.E[:12]}", f"release/7-G1-{self.E[:12]}"):
            with self.subTest(ref=ref):
                self.assertIn("not in main", self.reason(**{f"pulls/{RELEASE_PR}": self.release_record(head={"ref": ref})}))

    def test_a_pr_merged_by_a_non_approver_refuses_even_from_a_pin(self):
        self.assertIn("approver", self.reason(**{f"pulls/{RELEASE_PR}": self.release_record(merged_by={"id": 424242})}))

    def test_a_branch_outside_main_that_isnt_a_pin_keeps_its_old_reason(self):
        self.assertEqual(self.reason(**{f"pulls/{RELEASE_PR}": self.release_record(head={"ref": "feature/x"})}),
                         "it merged a branch that is not in main")


class DeclarationTest(unittest.TestCase):
    def test_the_pin_pattern_and_field_patterns_are_the_ones_gates_py_uses(self):
        self.assertEqual(fo.PIN.pattern, gates.PIN.pattern)
        self.assertEqual(fo.FIELD.pattern, gates.FIELD.pattern)
        self.assertEqual(fo.STEP_ID.pattern, gates.STEP_ID.pattern)
        self.assertEqual(fo.GIT_BRANCH.pattern, gates.BRANCH.pattern)
        self.assertEqual(fo.GATE_JOB_S, gates.GATE_JOB_S)

    def test_a_release_gate_is_declared_and_accepted_together(self):
        self.assertIn("release", fo.REQUEST_KINDS)
        self.assertTrue(gates.takes_release_gates(fakes.catalog()))
        self.assertFalse(gates.takes_rollbacks(fakes.catalog()))

    def test_the_sample_plan_passes_the_plan_guard_and_a_rollback_doesnt(self):
        self.assertEqual(gates.check_plan(PLAN, fakes.catalog()), [])
        ops_plan = fakes.OPS_PLAN.replace('{"steps": [{"op": "health"}]}',
                                          '{"steps": [{"id": "s", "op": "snapshot-now"}], "rollback": '
                                          '[{"op": "health", "with": {}}]}')
        self.assertTrue(any("runs no rollback steps" in e for e in gates.check_plan(ops_plan, fakes.catalog())))


if __name__ == "__main__":
    unittest.main()
