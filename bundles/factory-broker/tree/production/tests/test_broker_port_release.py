"""Release gates (z-sdlc process/factory.md D4 rule 13), the part test_broker_release_gate.py doesn't hold: the rebuild's
search for the merged release PR, the release branch's head still having the gate's content, the pre-run deadline, the
branch moving after the last step, git failures, the broker-only shape refusals, and the plan's path. Real git
repositories, a mocked GitHub, the fake host. Carried over from the third project's broker tests (test_release_gate.py:
RebuildRelease, ReleaseContent, PreRunDeadline, AfterTheLastStep, GitFailures, BrokerOnlyShapeRefusals; test_round6.py:
RebuildPlanPath)."""

import ast
import base64
import inspect
import subprocess
import unittest
from unittest import mock

import fakes
import factory_op as fo
import gates
from fakes import TOKEN
import test_broker_release_gate as rg
from test_broker_gate import GateBase

PR, ISSUE, GATE, RELEASE_PR = rg.PR, rg.ISSUE, rg.GATE, rg.RELEASE_PR
PLAN, PLAN_PATH = rg.PLAN, rg.PLAN_PATH


class Base(rg.ReleaseBase):
    """ReleaseBase, with the release branch's PR listing (`pulls`), a GitHub double for rebuild, and a way to replace the
    gate's release with another execution branch's."""

    def list_row(self, **changes):
        return rg.merged({"number": RELEASE_PR, "state": "closed", "merged_at": "2026-11-06T00:00:00Z", "user": {"id": self.app},
                          "head": {"ref": self.pin(), "repo": {"full_name": self.cfg["repo"]}},
                          "base": {"ref": "release/production"}}, **changes)

    def routes(self):
        return {**super().routes(), "pulls": [self.list_row()]}

    def swap_release(self, *commits):
        """Drop setUp's release and make the gate's release these commits of a fresh execution branch."""
        self.repo.sh("reset", "-q", "--hard", self.repo.base)
        self.E = self.exec_branch(*commits, branch="factory/9-impl")
        self.M = self.release_merge(self.E, number=60)
        self.repo.fetch()

    def github(self, pulls=None, **routes):
        """GitHub as rebuild reads it: the execution PR, its tracker, the plan on the default branch, the release PR, and the
        release branch's PR listing, which answers a `closed` query with merged rows only."""
        tracker = {"id": 1, "created_at": "2026-11-05T00:00:00Z", "user": {"type": "Bot", "id": self.app},
                   "body": gates.marker(gates.TRACKER, {"v": 1, "issue": ISSUE, "plan": PLAN_PATH, "stopped_at": ""})}
        plan = {"encoding": "base64", "content": base64.b64encode(PLAN.encode()).decode(), "sha": "b" * 40}
        table = {f"pulls/{PR}": self.execution_record(), f"pulls/{RELEASE_PR}": self.release_record(),
                 f"issues/{PR}/comments": [tracker], "pulls": [self.list_row()] if pulls is None else pulls}
        table.update(routes)

        class GH:
            def __init__(s):
                s.calls = []

            def get(s, path, params=None):
                s.calls.append((path, params))
                if path.startswith("contents/"):
                    return plan
                if path == "pulls":
                    return [p for p in table["pulls"] if not params or params.get("state") != "closed" or p.get("merged_at")]
                return table[path]
        return GH()


class RebuildReleaseTest(Base):
    """The broker has only the run's title: it finds the merged release PR itself, and the digest ties it to what CD approved."""

    def request_for(self, merge=None):
        return gates.build_request(repo=self.cfg["repo"], issue=ISSUE, pr=PR, plan=PLAN_PATH, plan_blob="b" * 40, plan_text=PLAN,
                                   gate_id=GATE, attempt=1, head=self.E, catalog=self.env.cat, gate_outputs={},
                                   ops_digest=fo.installed_digest(gates, self.cfg["lib_dir"]),
                                   release={"branch": "release/production", "pr": RELEASE_PR, "merge": merge or self.M})

    def rebuild(self, gh, request=None):
        request = request or self.request_for()
        title = {"gate": GATE, "attempt": 1, "kind": "release", "digest": request["digest"]}
        return fo.rebuild(self.cfg, gates, self.env.cat, gh, PR, title, [])

    def refusal(self, gh, request=None):
        with self.assertRaises(fo.Refused) as cm:
            self.rebuild(gh, request)
        return str(cm.exception)

    def test_the_merged_release_pr_is_found_and_its_digest_matches(self):
        request, _ = self.rebuild(self.github())
        self.assertEqual(request["kind"], "release")
        self.assertEqual(request["release"], {"branch": "release/production", "pr": RELEASE_PR, "merge": self.M})

    def test_a_merge_commit_other_than_the_approved_one_changes_the_digest_and_refuses(self):
        self.assertIn("something changed since approval", self.refusal(self.github(), self.request_for(merge="3" * 40)))

    def test_a_stale_install_is_named_when_the_digest_differs(self):
        self.assertIn("CD re-runs setup on the production host", self.refusal(self.github(), self.request_for(merge="3" * 40)))

    def test_no_release_pr_refuses_saying_so(self):
        self.assertIn("no release PR from", self.refusal(self.github(pulls=[])))

    def test_an_unmerged_release_pr_refuses_saying_so(self):
        msg = self.refusal(self.github(pulls=[self.list_row(state="open", merged_at=None)]))
        self.assertIn("isn't merged into release/production yet", msg)
        self.assertIn("CD merges it", msg)

    def test_a_release_pr_closed_without_merging_says_to_reopen_or_retry_not_to_merge(self):
        msg = self.refusal(self.github(pulls=[self.list_row(merged_at=None)]))
        self.assertIn("closed without merging", msg)
        self.assertIn("factory opens a new one", msg)
        self.assertNotIn("CD merges it", msg)

    def test_a_release_pr_merged_at_an_older_head_is_reported_as_stale(self):
        old = gates.pin_branch(PR, GATE, "2" * 40)
        pulls = [{"number": 39, "merged_at": "2026-11-05T00:00:00Z", "head": {"ref": old}, "base": {"ref": "release/production"}}]
        msg = self.refusal(self.github(pulls=pulls))
        self.assertIn("merged at an older commit", msg)
        self.assertIn("#39", msg)

    def test_a_pr_from_another_gate_or_pr_is_not_the_gates(self):
        for other in (gates.pin_branch(PR + 1, GATE, "2" * 40), gates.pin_branch(PR, "G2", "2" * 40)):
            with self.subTest(other=other):
                pulls = [{"number": 39, "merged_at": "2026-11-05T00:00:00Z", "head": {"ref": other},
                          "base": {"ref": "release/production"}}]
                self.assertIn("no release PR from", self.refusal(self.github(pulls=pulls)))

    def test_a_release_pr_record_without_a_number_is_a_refusal_not_a_crash(self):
        record = self.release_record()
        del record["number"]
        self.assertIn("isn't merged", self.refusal(self.github(**{f"pulls/{RELEASE_PR}": record})))

    def test_someone_elses_pr_from_the_pin_does_not_stand_in_for_the_apps(self):
        theirs = [self.list_row(state="open", merged_at=None, user={"id": 5})]
        self.assertIn("no release PR from", self.refusal(self.github(pulls=theirs)))

    def test_two_merged_release_prs_from_the_pin_refuse(self):
        row = self.list_row()
        self.assertIn("more than one merged release PR", self.refusal(self.github(pulls=[row, {**row, "number": 77}])))

    def test_an_ops_gate_never_looks_for_a_release_pr(self):
        gh = self.github()
        title = {"gate": GATE, "attempt": 1, "kind": "ops", "digest": "0" * 64}
        with self.assertRaises(fo.Refused):
            fo.rebuild(self.cfg, gates, self.env.cat, gh, PR, title, [])
        self.assertNotIn("pulls", [path for path, _ in gh.calls])


class ReleaseContentTest(Base):
    """The release branch's head must still have the gate's commit's content (the contract's check), not just the merge's: a
    revert that predates the merge would otherwise pass."""

    BIG = "".join(f"{i}\n" for i in range(1, 11))

    def release_ahead_on_a_touched_path(self):
        """P1 puts docs/big.md on main and the release branch; the execution branch (from main then) edits its last line; R, a
        release made meanwhile, edits its first line; the gate's release merges the execution branch into R, cleanly."""
        self.repo.sh("reset", "-q", "--hard", self.repo.base)
        p1 = self.later_release({"docs/big.md": self.BIG}, number=2)
        self.E = self.exec_branch({"docs/big.md": self.BIG.replace("10\n", "ten\n")}, branch="factory/9-impl")
        r = self.later_release({"docs/big.md": self.BIG.replace("1\n", "one\n", 1)}, number=3)
        self.M = self.release_merge(self.E, number=60)
        self.repo.fetch()
        return [(p1, 2, None), (r, 3, None)]

    def second_release_after_a_revert(self, revert_the_revert=False):
        """E1 changes README; CD merged M1; then M1 was reverted (and, for the recovery, the revert reverted); E2 adds only
        docs/q.md on the same execution branch, and M2 merges it cleanly. Returns the commit the revert work ended at."""
        self.repo.sh("revert", "--no-edit", "-m", "1", self.M)
        if revert_the_revert:
            self.repo.sh("revert", "--no-edit", self.repo.head())
        ended = self.repo.head()
        self.repo.sh("checkout", "-q", f"factory/{ISSUE}-impl")
        self.repo.write({"docs/q.md": "q"})
        self.repo.sh("add", "-A")
        self.repo.sh("commit", "-q", "-m", "fix q")
        self.E = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "release/production")
        self.M = self.release_merge(self.E, number=61)
        self.repo.fetch()
        return ended

    def test_a_release_branch_that_was_ahead_on_a_touched_path_is_refused_with_the_recovery(self):
        merges = self.release_ahead_on_a_touched_path()
        msg = self.refuses(svc=self.services(merges))
        self.assertIn("docs/big.md", msg)
        self.assertIn("bring main into the execution branch, push, and add factory:gate-retry", msg)

    def test_a_revert_that_predates_a_later_clean_merge_is_refused(self):
        self.second_release_after_a_revert()
        self.assertEqual(self.repo.git.diff_paths(self.M, self.repo.head()), set())  # the comparison with M2 would pass
        self.assertIn("README", self.refuses())

    def test_reverting_the_revert_and_recording_a_baseline_lets_the_gate_pass(self):
        """factory.md rule 13's recovery after a failed release gate: revert the revert, record a baseline, then the retry."""
        restored = self.second_release_after_a_revert(revert_the_revert=True)
        self.append_baseline(self.capture_state(restored), at="2026-11-05T11:30:00Z")  # the revert commits came in by hand
        receipt = self.run_gate()["receipt"]
        self.assertEqual(receipt["status"], "done", receipt)

    def test_a_gate_whose_commits_changed_nothing_has_nothing_to_compare_and_passes(self):
        self.swap_release({"docs/t.md": "t"}, {"docs/t.md": None})
        self.assertEqual(self.repo.git.diff_paths(self.repo.base, self.E), set())
        self.assertEqual(self.run_gate()["receipt"]["status"], "done")

    def test_an_execution_pr_that_is_not_open_and_unmerged_refuses(self):
        for change in ({"state": "closed"}, {"merged": True}, {"merged_at": "2026-11-06T00:00:00Z"}):
            with self.subTest(change=change):
                gh = self.gh(extra={f"pulls/{PR}": self.execution_record(**change)})
                self.assertIn("isn't open and unmerged", self.refuses(svc=self.services(gh=gh)))

    def test_a_path_changed_and_changed_back_within_the_pr_is_not_part_of_its_content(self):
        self.swap_release({"README": "r2", "docs/t.md": "t"}, {"docs/t.md": None})
        later = self.later_release({"docs/t.md": "someone else's"})
        self.assertEqual(self.run_gate(svc=self.services([(later, 2, None)]))["receipt"]["status"], "done")

    def test_a_rename_counts_both_names(self):
        self.swap_release({"README": None, "README2": "r"})
        later = self.repo.merge_pr({"README": "back"}, via_main=False)
        self.assertIn("README", self.refuses(svc=self.services([(later, 2, None)])))

    def test_main_merged_into_the_execution_branch_is_not_the_prs_content(self):
        self.repo.sh("reset", "-q", "--hard", self.repo.base)
        self.repo.sh("checkout", "-q", "-b", "factory/9-impl", "main")
        self.repo.write({"README": "r2"})
        self.repo.sh("add", "-A")
        self.repo.sh("commit", "-q", "-m", "work")
        self.repo.sh("checkout", "-q", "main")
        self.repo.write({"docs/m.md": "from main"})
        self.repo.sh("add", "-A")
        self.repo.sh("commit", "-q", "-m", "main moves on")
        self.repo.sh("checkout", "-q", "factory/9-impl")
        self.repo.sh("merge", "-q", "--no-ff", "-m", "Merge main", "main")
        self.E = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "release/production")
        self.M = self.release_merge(self.E, number=60)
        self.repo.fetch()
        self.assertEqual(self.repo.git.diff_paths(self.repo.git.merge_base(self.E, self.repo.git.main_sha()), self.E), {"README"})
        self.assertEqual(self.run_gate()["receipt"]["status"], "done")


class PreRunDeadlineTest(Base):
    """The checks before a release gate runs anything stop at a deadline (fo.PRE_RUN_BUDGET_S), checked between calls, in two
    windows: up to the fetch of the release branch, and from the fetch to the end of provenance."""

    class Slow:
        """Wraps GitHub or git: every call costs `cost` seconds of the clock the broker's deadline reads."""

        def __init__(self, inner, clock, cost):
            self._inner, self._clock, self._cost = inner, clock, cost

        def __getattr__(self, name):
            attr = getattr(self._inner, name)
            if not callable(attr):
                return attr

            def call(*a, **kw):
                self._clock.t += self._cost
                return attr(*a, **kw)
            return call

    def test_slow_github_reads_refuse_the_gate_before_anything_runs(self):
        clock = fakes.FakeClock()
        svc = fo.Services(self.Slow(self.gh(), clock, 700), self.repo.git, lambda run: self.env.sandbox, clock=clock)
        msg = self.refuses(svc=svc)
        self.assertIn("reading the execution PR", msg)
        self.assertIn(f"ran past {fo.PRE_RUN_BUDGET_S} s", msg)
        self.assertIn("nothing has run", msg)

    def test_slow_git_calls_refuse_the_gate_before_anything_runs(self):
        clock = fakes.FakeClock()
        svc = fo.Services(self.gh(), self.Slow(self.repo.git, clock, 400), lambda run: self.env.sandbox, clock=clock)
        # The fetch and the clone's has() spend the first window; the release history's calls trip the second.
        self.assertIn("reading the merge commit", self.refuses(svc=svc))

    def test_provenance_stops_between_commits_when_the_deadline_has_passed(self):
        clock = fakes.FakeClock()
        budget = fo.PreRunBudget(60, clock)
        first = self.later_release({"docs/a.md": "a"}, number=2)
        second = self.later_release({"docs/b.md": "b"}, number=3)
        self.repo.fetch()
        gh = self.Slow(self.gh([(first, 2, None), (second, 3, None)]), clock, 50)
        with self.assertRaises(fo.Refused) as cm:
            fo.provenance_failures(self.cfg, gh, self.repo.git, self.M, second, budget=budget)
        self.assertIn(f"provenance of {second[:12]}", str(cm.exception))

    def test_a_slow_read_of_the_release_branch_trips_the_first_window(self):
        clock = fakes.FakeClock()
        inner = self.gh()

        class SlowBranch:
            def get(s, path, params=None):
                if path.startswith("branches/"):
                    clock.t += fo.PRE_RUN_BUDGET_S + 10
                return inner.get(path, params)
        svc = fo.Services(SlowBranch(), self.repo.git, lambda run: self.env.sandbox, clock=clock)
        self.assertIn("reading the release branch", self.refuses(svc=svc))

    def test_a_slow_fetch_does_not_spend_the_checks_after_it(self):
        clock = fakes.FakeClock()
        inner = self.repo.git

        class SlowFetch:
            def __getattr__(s, name):
                attr = getattr(inner, name)
                if name != "fetch":
                    return attr

                def fetch(*a, **kw):
                    clock.t += fo.PRE_RUN_BUDGET_S + 100  # a cold fetch, bounded by its own timeout
                    return attr(*a, **kw)
                return fetch
        svc = fo.Services(self.gh(), SlowFetch(), lambda run: self.env.sandbox, clock=clock)
        self.assertEqual(self.run_gate(svc=svc)["receipt"]["status"], "done")

    def test_the_rebuilds_release_pr_reads_are_inside_the_deadline_too(self):
        clock = fakes.FakeClock()
        budget = fo.PreRunBudget(60, clock)
        gh = self.Slow(self.github(), clock, 100)
        with self.assertRaises(fo.Refused) as cm:
            fo.release_binding_for(self.cfg, gates, gh, PR, GATE, self.E, budget)
        self.assertIn("listing the gate's release PRs", str(cm.exception))

    def test_serve_one_starts_one_deadline_and_hands_it_to_rebuild_and_execute(self):
        seen = {}
        title = {"pr": PR, "gate": GATE, "attempt": 1, "kind": "release", "digest": "d" * 64}

        def fake_rebuild(cfg, g, cat, gh, pr, t, entries, budget=None):
            seen["rebuild"] = budget
            return self.request(), "def"

        def fake_execute(*a, budget=None, **kw):
            seen["execute"] = budget
            return {"receipt": {"status": "done"}}
        line = '{"run_id": 1, "pr": %d, "token": "%s"}' % (PR, TOKEN)
        with mock.patch.object(fo, "check_run", return_value=(title, 1)), mock.patch.object(fo, "rebuild", fake_rebuild), \
                mock.patch.object(fo, "execute", fake_execute):
            fo.serve_one(self.cfg, gates, self.env.cat, line, self.env.secret, svc_factory=lambda cfg, token: self.services())
        self.assertIsInstance(seen["rebuild"], fo.PreRunBudget)
        self.assertIs(seen["rebuild"], seen["execute"])

    def test_the_deadline_is_the_slack_with_room_for_the_call_in_flight(self):
        self.assertLessEqual(2 * fo.PRE_RUN_BUDGET_S + fo.GIT_TIMEOUT_S, fo.RELEASE_SLACK_S)  # two windows, one call in flight


class AfterTheLastStepTest(Base):
    def test_the_release_branch_moving_after_the_last_step_fails_the_gate(self):
        later = self.later_release({"docs/note.md": "n"})
        head = {"name": "release/production", "commit": {"sha": self.M}}
        # Read before the checks, at the end of the wait, and after the last step.
        moved = fakes.Seq([head, head, {"name": "release/production", "commit": {"sha": later}}])
        svc = self.services(gh=self.gh(extra={"branches/release%2Fproduction": moved}))
        receipt = self.run_gate(self.health(), svc=svc)["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("release/production's head moved during the gate", receipt["reason"])
        self.assertTrue(receipt["reason"].startswith("PRODUCTION NEEDS CD:"))
        self.assertEqual(receipt["release_head"], self.M)
        self.assertEqual([s["status"] for s in receipt["steps"]], ["done"])  # the steps ran; what they vouch for moved


class GitFailuresTest(Base):
    def test_a_git_failure_in_the_release_checks_is_a_refusal_with_context(self):
        with mock.patch.object(self.repo.git, "merge_base", side_effect=fo.GitError("git merge-base found no common ancestor")):
            msg = self.refuses()
        self.assertIn("can't check the release against release/production", msg)
        self.assertIn("no common ancestor", msg)

    def git_with(self, stdout="", returncode=0, error=None):
        def runner(argv, **kw):
            if error:
                raise error
            return subprocess.CompletedProcess(argv, returncode, stdout, "")
        return fo.Git(self.repo.clone, runner=runner)

    def test_merge_base_without_an_answer_raises(self):
        with self.assertRaises(fo.GitError):
            self.git_with(returncode=1).merge_base("a" * 40, "b" * 40)
        with self.assertRaises(fo.GitError):
            self.git_with(stdout="not a commit\n").merge_base("a" * 40, "b" * 40)
        with self.assertRaises(fo.GitError):
            self.git_with(stdout="c" * 40).merge_base("HEAD", "b" * 40)

    def test_a_path_that_is_not_utf8_fails_closed(self):
        err = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        with self.assertRaisesRegex(fo.GitError, "valid UTF-8"):
            self.git_with(error=err).diff_paths("a" * 40, "b" * 40)

    def test_diff_paths_reads_well_formed_records_and_nothing_else(self):
        hdr = ":100644 100644 " + "a" * 40 + " " + "b" * 40 + " M"
        self.assertEqual(self.git_with(f"{hdr}\0x y\0{hdr}\0:odd\0").diff_paths("a" * 40, "b" * 40), {"x y", ":odd"})
        self.assertEqual(self.git_with("").diff_paths("a" * 40, "b" * 40), set())
        for bad in (f"{hdr}\0x", f"{hdr}\0x\0stray\0", "junk\0x\0", f"{hdr.replace(' M', ' R')}\0x\0", f"{hdr}\0\0", ":1 2 3\0x\0"):
            with self.subTest(bad=bad), self.assertRaises(fo.GitError):
                self.git_with(bad).diff_paths("a" * 40, "b" * 40)


class BrokerOnlyShapeRefusalsTest(Base):
    """Every refusal the broker makes from a release request's shape, and whether gates.check_plan catches the same plan
    before its release PR is merged (the merge is the deploy, so a refusal only the broker makes comes after it).

    Changed on purpose from the third project's broker, where all four refusals were one function's and the plan guard
    lacked the budget: here a rollback is refused by execute for every kind (NO_ROLLBACK), the budget is budget_problem's,
    and the plan guard has the budget too (gates.budget_errors, from the catalog's gate_overhead_s, step_margin_s and
    release_wait). Only the binding, which no plan holds, is the broker's alone. When a refusal is added, this table is
    extended and says whether the plan guard mirrors it."""

    def plan_with(self, block):
        return PLAN.replace('{"steps": [{"op": "health"}]}', block)

    def slow(self):
        cat = fakes.catalog_dict()
        cat["operations"]["health"]["timeout_s"] = 2900  # four health steps fit a release gate's run, five don't
        return fakes.load(cat)

    def test_each_shape_refusal_and_whether_the_plan_guard_mirrors_it(self):
        five = ", ".join(f'{{"id": "h{i}", "op": "health"}}' for i in range(5))
        cases = {
            "rollback": (self.plan_with('{"steps": [{"op": "health"}], "rollback": [{"op": "health"}]}'), self.env.cat,
                         self.request(self.health(), rollback=[{"id": "u", "op": "health", "with": {}}]),
                         "a release gate has no rollback", "runs no rollback"),
            "not a read operation": (self.plan_with('{"steps": [{"op": "snapshot-now"}]}'), self.env.cat,
                                     self.request([{"id": "s", "op": "snapshot-now", "with": {}}]),
                                     "a release gate runs only read operations", "only read operations"),
            "worst case over the job's limit": (self.plan_with('{"steps": [' + five + ']}'), self.slow(),
                                                self.request([{"id": f"h{i}", "op": "health", "with": {}} for i in range(5)]),
                                                "more than the gate run's", "more than the gate run's"),
        }
        for name, (plan, cat, request, guard, broker) in cases.items():
            with self.subTest(name):
                errors = gates.check_plan(plan, cat)
                self.assertTrue(any(guard in e for e in errors), f"the plan guard doesn't refuse it for that: {errors}")
                self.assertIn(broker, self.refuses(req=request, cat=cat))
        # The binding is about the request itself, which no plan holds.
        self.assertIn("needs its merged release PR", fo.release_shape_problem(self.cfg, self.env.cat, {**self.request(), "release": None}))

    def test_the_table_lists_every_refusal_the_functions_can_make(self):
        def refusals(fn):
            tree = ast.parse(inspect.getsource(fn))
            return [n for n in ast.walk(tree) if isinstance(n, ast.Return) and n.value is not None
                    and not (isinstance(n.value, ast.Constant) and n.value.value is None)]
        self.assertEqual(len(refusals(fo.release_shape_problem)), 2, "release_shape_problem gained or lost a refusal: update "
                                                                     "the table above, and say whether gates.check_plan mirrors it")
        self.assertEqual(len(refusals(fo.budget_problem)), 1, "budget_problem gained or lost a refusal: update the table above")


class RebuildPlanPathTest(GateBase):
    """rebuild() reads the plan a PR's tracker names; gates.PLAN_PATH must match the whole path (a trailing newline is not a plan)."""

    def refusal(self, plan):
        cfg = self.cfg
        pr = {"head": {"ref": "factory/7-impl", "sha": "a" * 40, "repo": {"full_name": cfg["repo"]}}, "state": "open",
              "user": {"id": cfg["app_bot_id"]}}
        tracker = {"id": 1, "created_at": "2026-11-05T00:00:00Z", "user": {"type": "Bot", "id": cfg["app_bot_id"]},
                   "body": gates.marker(gates.TRACKER, {"v": 1, "issue": 7, "plan": plan, "stopped_at": ""})}

        class GH:
            def get(self, path, params=None):
                if path.startswith("pulls/"):
                    return pr
                if path.startswith("issues/"):
                    return [tracker]
                return {}  # the plan's contents: reached only if the path was accepted

        with self.assertRaises(fo.Refused) as cm:
            fo.rebuild(cfg, gates, self.env.cat, GH(), 7, {}, [])
        return str(cm.exception)

    def test_a_plan_path_with_a_trailing_newline_names_no_plan(self):
        self.assertEqual(self.refusal("docs/current_work/sdlc-lite/d1_x_plan.md\n"), "the PR names no plan")

    def test_a_valid_plan_path_is_read(self):
        self.assertEqual(self.refusal("docs/current_work/sdlc-lite/d1_x_plan.md"), "can't read the plan")


if __name__ == "__main__":
    unittest.main()
