"""The broker's checks before every gate, provenance, executing a gate and its records, baseline, the daily drift check and
the sandbox (z-sdlc process/factory.md D4 rules 7-9, 14). Real git repositories, a mocked GitHub, the fake host.
Carried over from the third project's broker tests (test_gate.py), with its platform's world replaced by fake_host."""

import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import fakes
from fakes import Env, TOKEN
import factory_op as fo
import gates

BASELINE_AT = "2026-11-05T11:00:00Z"


class GateBase(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.cfg, self.repo, self.w, self.clock = self.env.cfg, self.env.repo, self.env.world, self.env.clock
        self.block = self.env.cat["broker"]
        for name, value in (("LOCK", self.env.tmp / "run" / "broker.lock"), ("STEPS_DIR", self.env.tmp / "steps")):
            patcher = mock.patch.object(fo, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        fakes.no_live_steps(self)
        self.state = self.capture_state(self.repo.base)

    def capture_state(self, release_head):
        return self.env.capture_state(release_head)

    def gh(self, merges=(), by=None, extra=None):
        return fakes.github_for(self.cfg, self.repo, merges, approver=by, extra=extra)

    def pregate(self, merges=(), ops=("health",), state=None, by=None, extra=None):
        run_capture = fo.capture_runner(self.cfg, self.env.cat, self.env.sandbox, self.env.tmp / "logs", "pre")
        return fo.pregate(self.cfg, self.block, self.gh(merges, by, extra), self.repo.git, state or self.state, run_capture,
                          list(ops), TOKEN)

    def merge(self, files):
        return self.repo.merge_pr(files)

    def append_baseline(self, state, secret=None, at=BASELINE_AT):
        self.env.append_baseline(state, secret=secret, at=at)

    def services(self, merges=(), gh=None):
        return fo.Services(gh or self.gh(merges), self.repo.git, lambda run: self.env.sandbox)

    def refused(self, **kw):
        with self.assertRaises(fo.Refused) as cm:
            self.pregate(**kw)
        return str(cm.exception)

    def copy(self, state):
        return json.loads(json.dumps(state))


class PregateTest(GateBase):
    def test_head_is_read_from_github_and_the_clean_state_passes(self):
        head, out, _ = self.pregate()
        self.assertEqual(head, self.repo.base)
        self.assertEqual(out["staged"], "none")

    def test_a_service_serving_an_older_content_equal_commit_passes(self):
        sha = self.merge({"README": "r2"})  # no service's files change
        head, _, _ = self.pregate(merges=[(sha, 1, None)])
        self.assertEqual(head, sha)

    def test_a_service_whose_content_differs_refuses_naming_it(self):
        sha = self.merge({"jobs/work.txt": "j2"})
        msg = self.refused(merges=[(sha, 1, None)])
        self.assertIn("jobs", msg)
        self.assertIn("isn't serving", msg)

    def test_content_check_uses_the_declared_glob_patterns(self):
        sha = self.merge({"web/deep/dir/x.txt": "new", "docs/other.txt": "d"})
        self.assertIn("web", self.refused(merges=[(sha, 1, None)]))
        self.assertTrue(self.repo.git.content_equal(self.repo.base, sha, ["/jobs/**"]))
        self.assertFalse(self.repo.git.content_equal(self.repo.base, sha, ["/web/**"]))
        self.assertTrue(self.repo.git.content_equal(self.repo.base, sha, ["/web-not/**"]))

    def test_a_shared_path_counts_for_every_service_that_declares_it(self):
        sha = self.merge({"shared/lib.txt": "s2"})
        msg = self.refused(merges=[(sha, 1, None)])
        self.assertTrue(msg.startswith("web:"), msg)

    def test_a_serving_commit_that_is_not_an_ancestor_refuses(self):
        self.w.deployments["web"][0]["commit"] = "2" * 40
        self.assertIn("isn't on release/production", self.refused())

    def test_a_deploying_latest_deployment_refuses_except_for_release_wait(self):
        self.w.add("web", "BUILDING", self.repo.base)
        self.assertIn("a release is deploying", self.refused())
        head, _, _ = self.pregate(ops=("release-wait", "health"))
        self.assertEqual(head, self.repo.base)

    def test_release_wait_lifts_the_serving_check_for_release_services_only(self):
        self.w.add("proxy", "BUILDING", self.repo.base)
        self.assertIn("proxy: a release is deploying", self.refused(ops=("release-wait", "health")))

    def test_release_wait_must_be_the_first_step(self):
        self.assertIn("first step", self.refused(ops=("health", "release-wait")))

    def test_release_wait_still_gets_the_settings_and_provenance_checks(self):
        self.w.settings["web"]["replicas"] = 2
        self.assertIn("settings changed", self.refused(ops=("release-wait",)))
        self.setUp()
        self.w.mode = "manual"
        self.assertIn("mode is 'manual'", self.refused(ops=("release-wait",)))
        self.setUp()
        sha = self.repo.direct_commit({"README": "x"})
        self.assertIn("release without a PR", self.refused(ops=("release-wait",), extra={f"commits/{sha}/pulls": []}))

    def test_a_moved_recorded_output_refuses_and_names_it(self):
        self.w.settings["jobs"]["replicas"] = 3
        self.assertIn("settings changed outside a release (fp_jobs)", self.refused())

    def test_shared_settings_drift_refuses(self):
        self.w.shared["X"] = "1"
        self.assertIn("fp_shared", self.refused())

    def test_a_key_id_change_refuses(self):
        bad = self.copy(self.state)
        bad["recorded"]["fp_key_id"] = "00000000"
        self.assertIn("fp_key_id", self.refused(state=bad))

    def test_each_invariant_refuses_with_what_it_found_what_it_needs_and_why(self):
        self.w.staged = "pending"
        msg = self.refused()
        self.assertIn("staged is 'pending', not 'none'", msg)
        self.assertIn(self.block["invariants"]["staged"]["why"], msg)
        self.setUp()
        self.w.mode, self.w.mode_source = "manual", "a hand edit"
        msg = self.refused()
        self.assertIn("mode is 'manual', not one of 'auto', 'locked' (mode_source: 'a hand edit')", msg)

    def test_every_problem_found_is_named_in_one_refusal(self):
        self.w.staged, self.w.mode = "pending", "manual"
        self.w.settings["cache"]["replicas"] = 4
        msg = self.refused()
        for needle in ("staged is", "mode is", "fp_cache"):
            self.assertIn(needle, msg)

    def test_a_checked_service_that_isnt_a_release_service_joins_the_content_check(self):
        sha = self.merge({"proxy/p.txt": "p2"})
        self.assertIn("proxy", self.refused(merges=[(sha, 1, None)]))

    def test_a_service_that_isnt_checked_is_never_content_checked(self):
        sha = self.merge({"cache/c.txt": "c2"})
        head, _, _ = self.pregate(merges=[(sha, 1, None)])
        self.assertEqual(head, sha)

    def test_a_failed_capture_refuses(self):
        self.w.patterns["web"] = ["web/**"]  # the host builds web from other patterns than the block's
        self.assertIn("capture-state didn't complete", self.refused())


class ProvenanceTest(GateBase):
    def test_a_direct_push_refuses(self):
        sha = self.repo.direct_commit({"README": "pushed"})
        self.assertIn(f"release without a PR: {sha}", self.refused(extra={f"commits/{sha}/pulls": []}))

    def test_provenance_refuses_a_first_parent_commit_that_is_not_a_merged_prs_merge_commit(self):
        merge = self.merge({"README": "r2"})
        other = {"number": 9, "merge_commit_sha": "3" * 40}
        extra = {f"commits/{merge}/pulls": [other], "pulls/9": {"merged": True, "merge_commit_sha": "3" * 40,
                                                                 "base": {"ref": "release/production"},
                                                                 "merged_by": {"id": fakes.APPROVER}}}
        self.assertIn(f"release without a PR: {merge}", self.refused(extra=extra))

    def test_a_merge_commit_of_a_pr_merged_by_a_non_approver_refuses(self):
        sha = self.merge({"README": "r2"})
        msg = self.refused(merges=[(sha, 1, 424242)])
        self.assertIn("release without a PR", msg)
        self.assertIn("approver", msg)

    def test_a_pr_into_another_branch_does_not_count(self):
        sha = self.merge({"README": "r2"})
        routes = {f"commits/{sha}/pulls": [{"number": 1, "merge_commit_sha": sha}],
                  "pulls/1": {"merged": True, "merge_commit_sha": sha, "base": {"ref": "main"}, "merged_by": {"id": fakes.APPROVER}}}
        self.assertIn("release without a PR", self.refused(extra=routes))

    def test_an_unmerged_pr_does_not_count(self):
        sha = self.merge({"README": "r2"})
        routes = {f"commits/{sha}/pulls": [{"number": 1, "merge_commit_sha": sha}],
                  "pulls/1": {"merged": False, "merge_commit_sha": sha, "base": {"ref": "release/production"}, "merged_by": None}}
        self.assertIn("release without a PR", self.refused(extra=routes))

    def test_every_merge_since_the_record_is_checked_not_just_the_last(self):
        first = self.merge({"README": "r2"})
        second = self.merge({"README": "r3"})
        msg = self.refused(merges=[(second, 2, None)], extra={f"commits/{first}/pulls": []})
        self.assertIn(first, msg)
        head, _, _ = self.pregate(merges=[(first, 1, None), (second, 2, None)])
        self.assertEqual(head, second)

    def test_a_hotfix_branch_main_never_saw_refuses(self):
        sha = self.repo.merge_pr({"README": "hot"}, via_main=False)
        self.assertIn("merged a branch that is not in main", self.refused(merges=[(sha, 1, None)]))

    def test_a_force_pushed_branch_refuses_when_the_recorded_head_is_not_an_ancestor(self):
        self.repo.sh("checkout", "-q", "--orphan", "other")
        self.repo.sh("commit", "-q", "--allow-empty", "-m", "rewritten history")
        orphan = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "-f", "release/production")
        self.repo.git.fetch("x", "+refs/heads/other:refs/factory/other")
        state = self.copy(self.state)
        state["release_head"] = orphan
        self.assertIn("rewritten", self.refused(state=state))

    def test_a_head_missing_from_the_clone_refuses(self):
        routes = {"branches/release%2Fproduction": {"name": "release/production", "commit": {"sha": "4" * 40}}}
        self.assertIn("doesn't have", self.refused(extra=routes))

    def test_a_branch_answer_for_another_name_refuses(self):
        routes = {"branches/release%2Fproduction": {"name": "main", "commit": {"sha": self.repo.base}}}
        self.assertIn("can't read", self.refused(extra=routes))

    def test_a_token_never_reaches_a_git_argv(self):
        calls = []
        real = subprocess.run

        def spy(argv, **kw):
            calls.append((argv, kw.get("env", {})))
            return real(argv, **kw)
        git = fo.Git(self.repo.clone, runner=spy, remote=lambda repo: str(self.repo.work))
        git.fetch("x", f"+refs/heads/release/production:{fo.RELEASE_REF}", token=TOKEN)
        git.content_equal(self.repo.base, self.repo.base, ["/web/**"])
        for argv, env in calls:
            self.assertFalse(any(TOKEN in a for a in argv))
            self.assertNotIn(TOKEN, " ".join(env.values()))  # only its base64 form, in GIT_CONFIG_VALUE_1
        self.assertTrue(any("GIT_CONFIG_VALUE_1" in env for _, env in calls))

    def test_fetch_uses_https_with_a_token_header_or_ssh_with_the_deploy_key(self):
        calls = []
        git = fo.Git(self.repo.clone, runner=lambda argv, **kw: (calls.append((argv, kw["env"])), subprocess.CompletedProcess(argv, 0, "", ""))[1])
        git.fetch("o/r", "+refs/heads/x:refs/y", token=TOKEN)
        git.fetch("o/r", "+refs/heads/x:refs/y", ssh_key="/etc/factory-prod/github-deploy-key")
        (https_argv, https_env), (ssh_argv, ssh_env) = calls
        self.assertIn("https://github.com/o/r.git", https_argv)
        self.assertIn("GIT_CONFIG_VALUE_1", https_env)
        self.assertNotIn("GIT_SSH_COMMAND", https_env)
        self.assertIn("git@github.com:o/r.git", ssh_argv)
        self.assertIn("-i /etc/factory-prod/github-deploy-key", ssh_env["GIT_SSH_COMMAND"])
        self.assertIn("StrictHostKeyChecking=yes", ssh_env["GIT_SSH_COMMAND"])
        self.assertNotIn("GIT_CONFIG_VALUE_1", ssh_env)

    def test_git_diff_is_always_called_without_renames_external_diff_and_textconv(self):
        calls = []
        real = subprocess.run
        git = fo.Git(self.repo.clone, runner=lambda argv, **kw: (calls.append(argv), real(argv, **kw))[1])
        git.content_equal(self.repo.base, self.repo.base, ["/web/**"])
        git.run("diff", "--name-only", self.repo.base, self.repo.base)
        diffs = [c for c in calls if "diff" in c]
        self.assertEqual(len(diffs), 2)
        for argv in diffs:
            for flag in fo.DIFF_FLAGS:
                self.assertIn(flag, argv)

    def test_git_ignores_user_config_and_never_prompts(self):
        seen = []
        git = fo.Git(self.repo.clone, runner=lambda argv, **kw: (seen.append(kw["env"]), subprocess.CompletedProcess(argv, 0, "", ""))[1])
        git.run("rev-parse", "HEAD")
        env = seen[0]
        self.assertEqual((env["GIT_CONFIG_GLOBAL"], env["GIT_CONFIG_NOSYSTEM"], env["GIT_TERMINAL_PROMPT"]), ("/dev/null", "1", "0"))

    def test_content_equal_refuses_anything_but_commit_ids_and_globs(self):
        for a, b, pats in (("HEAD", self.repo.base, ["/web/**"]), (self.repo.base, self.repo.base, ["../x"]),
                           (self.repo.base, self.repo.base, [])):
            with self.subTest(a=a, pats=pats), self.assertRaises(fo.GitError):
                self.repo.git.content_equal(a, b, pats)


def request(steps=None, **changes):
    req = {"pr": 7, "gate": "G1", "issue": 3, "attempt": 1, "digest": "d" * 64, "head": "a" * 40, "kind": "ops",
           "plan_blob": "b" * 40, "rollback": [], "steps": steps if steps is not None else [{"id": "h", "op": "health", "with": {}}]}
    req.update(changes)
    return req


class ExecuteAndRecordsTest(GateBase):
    def sign(self, receipt):
        return gates.sign_receipt(self.env.secret, receipt)

    def run_gate(self, steps=None, svc=None, entries=None, req=None):
        entries = entries if entries is not None else fo.ledger_entries(self.cfg["ledger"])
        return fo.execute(self.cfg, gates, self.env.cat, req or request(steps), "def", fakes.APPROVER, 55, entries, self.sign,
                          TOKEN, svc or self.services(), self.env.public, host_run="run1")

    def recorded(self):
        return fo.recorded_state(fo.ledger_entries(self.cfg["ledger"]), gates, self.env.public)

    def test_a_done_gate_records_the_new_state_with_the_head_it_checked(self):
        self.append_baseline(self.state)
        sha = self.merge({"README": "r2"})
        receipt = self.run_gate(svc=self.services([(sha, 1, None)]))["receipt"]
        self.assertEqual(receipt["status"], "done", receipt)
        self.assertEqual(receipt["release_head"], sha)
        self.assertEqual(self.recorded(), {"release_head": sha, "recorded": self.state["recorded"]})

    def test_the_receipt_answers_the_request_and_the_ledger_shows_every_step(self):
        self.append_baseline(self.state)
        receipt = self.run_gate()["receipt"]
        self.assertEqual([s["id"] for s in receipt["steps"]], ["h"])
        self.assertEqual(receipt["steps"][0]["outputs"]["healthy"], "yes")
        events = [e["event"] for e in fo.ledger_entries(self.cfg["ledger"])]
        self.assertEqual(events, ["baseline", "start", "step-start", "step-finish", "finish"])
        finish = fo.ledger_entries(self.cfg["ledger"])[-1]
        self.assertEqual((finish["status"], finish["gate_def"], finish["plan_blob"]), ("done", "def", "b" * 40))
        self.assertEqual(finish["outputs"], {"h": receipt["steps"][0]["outputs"]})

    def test_a_moved_recorded_output_during_the_gate_records_no_state(self):
        self.append_baseline(self.state)
        n0 = len(self.env.sandbox.runs)  # the pre-gate capture is the next run; the hook fires once it has finished
        self.w.hooks.append(lambda w: w.settings["web"].update(replicas=5) if len(self.env.sandbox.runs) > n0 else None)
        receipt = self.run_gate()["receipt"]
        self.assertEqual(receipt["status"], "done")
        self.assertEqual(self.recorded()["release_head"], self.repo.base)  # still the baseline's record
        self.w.hooks.clear()
        self.assertIn("settings changed", self.refused(state=self.recorded()))  # so the next gate refuses

    def test_a_failed_step_gives_a_loud_receipt_and_still_records(self):
        self.append_baseline(self.state)
        self.w.add("jobs", "CRASHED", self.repo.base)
        receipt = self.run_gate()["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertTrue(receipt["reason"].startswith("PRODUCTION NEEDS CD:"))
        self.assertIn("only read", receipt["reason"])
        self.assertIsNotNone(self.recorded())

    def test_a_change_operations_failure_names_what_it_may_have_changed(self):
        self.append_baseline(self.state)
        real = self.w.api
        self.w.api = lambda method, path, body, headers: (fakes.fake_host.Resp(500, {}, b"{}") if method == "POST"
                                                          else real(method, path, body, headers))
        receipt = self.run_gate([{"id": "s", "op": "snapshot-now", "with": {}}])["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("except by this gate's change operations (snapshot-now)", receipt["reason"])

    def test_a_timed_out_step_blocks_with_a_loud_receipt_and_no_finish(self):
        self.append_baseline(self.state)
        inner = self.env.sandbox

        class Slow:
            def run(s, name, *a, **kw):
                return fo.StepResult("timed-out", why="timed out") if name == "health" else inner.run(name, *a, **kw)
        svc = fo.Services(self.gh(), self.repo.git, lambda run: Slow())
        receipt = self.run_gate(svc=svc)["receipt"]
        self.assertEqual(receipt["status"], "timed-out")  # gates.RECEIPT_STATUSES: what the step changed is unknown
        self.assertEqual(receipt["rollback"], [])
        self.assertTrue(receipt["reason"].startswith("PRODUCTION NEEDS CD:"))
        self.assertIn("resolve run1 failed", receipt["reason"])
        self.assertEqual(fo.unfinished(fo.ledger_entries(self.cfg["ledger"])), ["run1"])

    def test_release_wait_fails_with_head_moved_when_the_branch_advanced_during_the_wait(self):
        self.append_baseline(self.state)
        moved = self.merge({"README": "r2"})
        routes_head = fakes.Seq([{"name": "release/production", "commit": {"sha": self.repo.base}},
                                 {"name": "release/production", "commit": {"sha": moved}}])
        gh = self.gh(extra={"branches/release%2Fproduction": routes_head})
        steps = [{"id": "w", "op": "release-wait", "with": {"sha": self.repo.base}}]
        receipt = self.run_gate(steps, svc=self.services(gh=gh))["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("head moved", receipt["steps"][0]["why"])

    def test_release_wait_with_an_unmerged_sha_fails_with_release_pr_not_merged_yet(self):
        self.append_baseline(self.state)
        steps = [{"id": "w", "op": "release-wait", "with": {"sha": "1" * 40}}]
        receipt = self.run_gate(steps)["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("release PR not merged yet", receipt["steps"][0]["why"])
        self.assertIn("PRODUCTION NEEDS CD", receipt["reason"])

    def test_refused_gate_writes_nothing_to_the_ledger(self):
        self.append_baseline(self.state)
        self.w.settings["web"]["replicas"] = 9
        before = fo.ledger_entries(self.cfg["ledger"])
        with self.assertRaises(fo.Refused):
            self.run_gate()
        self.assertEqual(fo.ledger_entries(self.cfg["ledger"]), before)

    def test_no_recorded_state_refuses_the_gate(self):
        with self.assertRaises(fo.Refused) as cm:
            self.run_gate(entries=[])
        self.assertIn("baseline", str(cm.exception))

    def test_a_cd_gate_runs_nothing_and_records_the_approval(self):
        receipt = self.run_gate(req=request([], kind="cd"))["receipt"]
        self.assertEqual((receipt["status"], receipt["steps"]), ("done", []))
        self.assertEqual(self.env.sandbox.runs[-1][0], "capture-state")  # setUp's, not the gate's
        with self.assertRaises(fo.Refused):
            self.run_gate(req=request(kind="cd"))

    def test_an_unknown_kind_or_operation_is_refused(self):
        for req, needle in ((request(kind="deploy"), "unknown request kind"),
                            (request([{"id": "d", "op": "deploy-now", "with": {}}]), "isn't in the installed catalog")):
            with self.subTest(needle), self.assertRaises(fo.Refused) as cm:
                self.run_gate(req=req)
            self.assertIn(needle, str(cm.exception))

    def test_a_request_over_the_job_limit_is_refused_before_anything_runs(self):
        self.append_baseline(self.state)
        runs = len(self.env.sandbox.runs)
        cat = fakes.catalog_dict()
        cat["operations"]["snapshot-now"]["timeout_s"] = 3600
        steps = [{"id": f"s{i}", "op": "snapshot-now", "with": {}} for i in range(4)]
        with self.assertRaises(fo.Refused) as cm:
            fo.execute(self.cfg, gates, fakes.load(cat), request(steps), "def", fakes.APPROVER, 55,
                       fo.ledger_entries(self.cfg["ledger"]), self.sign, TOKEN, self.services(), self.env.public, host_run="run1")
        self.assertIn("could take", str(cm.exception))
        self.assertEqual(len(self.env.sandbox.runs), runs)

    def test_an_unsigned_baseline_is_ignored(self):
        fo.ledger_append(self.cfg["ledger"], {"event": "baseline", "run": "b", "repo": self.cfg["repo"], "deployed_state": self.state})
        self.assertIsNone(self.recorded())

    def test_a_baseline_with_a_forged_signature_is_ignored(self):
        receipt = {"v": 1, "kind": "baseline", "deployed_state": self.state}
        fo.ledger_append(self.cfg["ledger"], {"event": "baseline", "run": "b", "repo": self.cfg["repo"],
                                              "signed": {"receipt": receipt, "sig": "00" * 64}})
        self.assertIsNone(self.recorded())

    def test_a_baseline_signed_by_another_key_is_ignored(self):
        self.append_baseline(self.state, secret=bytes(range(50, 82)))
        self.assertIsNone(self.recorded())

    def test_a_tampered_baseline_is_ignored(self):
        self.append_baseline(self.state)
        entries = fo.ledger_entries(self.cfg["ledger"])
        entries[0]["signed"]["receipt"]["deployed_state"]["release_head"] = "9" * 40
        self.assertIsNone(fo.recorded_state(entries, gates, self.env.public))

    def test_the_latest_signed_baseline_wins_and_malformed_state_is_ignored(self):
        self.append_baseline(self.state)
        later = self.copy(self.state)
        later["release_head"] = "5" * 40
        self.append_baseline(later)
        self.assertEqual(self.recorded()["release_head"], "5" * 40)
        self.append_baseline({"recorded": {}})
        self.append_baseline({"release_head": "6" * 40, "recorded": {"Bad Name": "x"}})
        self.assertEqual(self.recorded()["release_head"], "5" * 40)

    def test_a_state_signed_for_another_run_doesnt_count(self):
        self.append_baseline(self.state)
        other = gates.sign_receipt(self.env.secret, {"v": 1, "kind": "state", "run": "elsewhere",
                                                     "deployed_state": {**self.state, "release_head": "7" * 40}})
        fo.ledger_append(self.cfg["ledger"], {"event": "finish", "run": "mine", "state_signed": other})
        self.assertEqual(self.recorded()["release_head"], self.repo.base)

    def test_serve_one_refuses_malformed_requests_and_an_unusable_config(self):
        bad = {**self.cfg, "approvers": []}
        for line, why in (("garbage", "malformed"), (json.dumps({"run_id": 1, "pr": 2, "token": "short"}), "token"),
                          (json.dumps({"run_id": 1, "pr": 2, "token": TOKEN}), "approvers")):
            with self.subTest(why):
                signed = fo.serve_one(bad, gates, self.env.cat, line, self.env.secret)
                receipt = gates.verify_receipt(self.env.public, signed)
                self.assertEqual(receipt["status"], "refused")
                self.assertIn(why, receipt["reason"])

    def test_the_test_config_has_no_problems(self):
        self.assertEqual(fo.config_problems(self.cfg), [])


class BaselineTest(GateBase):
    def baseline(self, console, advance=False, merges=(), extra=None):
        def factory(cfg, token):
            return fo.Services(self.gh(merges, extra=extra), self.repo.git, lambda run: self.env.sandbox)
        return fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "note", advance, factory, console)

    def recorded(self):
        return fo.recorded_state(fo.ledger_entries(self.cfg["ledger"]), gates, self.env.public)

    def test_the_first_baseline_sets_release_head_to_the_configured_start(self):
        self.assertEqual(self.baseline(fakes.Console(["yes"])), 0)
        self.assertEqual(self.recorded(), {"release_head": self.repo.base, "recorded": self.state["recorded"]})

    def test_baseline_captures_at_the_fetched_branch_head(self):
        merged = self.merge({"README": "r2"})
        self.baseline(fakes.Console(["yes"]))
        self.assertEqual(self.env.sandbox.envs[-1]["FACTORY_RELEASE_HEAD"], merged)

    def test_baseline_keeps_release_head_unless_advance_release_head(self):
        self.baseline(fakes.Console(["yes"]))
        merged = self.merge({"README": "r2"})
        self.repo.fetch()
        self.assertEqual(self.repo.git.run("rev-parse", fo.RELEASE_REF).stdout.strip(), merged)
        self.w.settings["web"]["replicas"] = 2
        c = fakes.Console(["yes"])
        self.baseline(c)
        self.assertEqual(self.recorded()["release_head"], self.repo.base)  # kept: the new merge is still checked later
        self.assertIn("would change: fp_web", c.lines[0])
        self.assertNotEqual(self.recorded()["recorded"]["fp_web"], self.state["recorded"]["fp_web"])

    def test_baseline_shows_the_outputs_it_doesnt_record_and_the_notes(self):
        c = fakes.Console(["yes"])
        self.baseline(c)
        self.assertIn("mode=auto", c.lines)
        self.assertIn("mode_source=the service settings", c.lines)
        self.assertTrue(any(line.startswith("web: builds from") for line in c.lines), c.lines)
        self.assertFalse(any(line.startswith("fp_web=") for line in c.lines))

    def test_advance_release_head_runs_provenance_and_moves_the_head(self):
        self.baseline(fakes.Console(["yes"]))
        sha = self.merge({"README": "r2"})
        self.baseline(fakes.Console(["yes"]), advance=True, merges=[(sha, 1, None)])
        self.assertEqual(self.recorded()["release_head"], sha)

    def test_a_failing_commit_needs_its_own_accept_and_a_general_yes_is_not_enough(self):
        self.baseline(fakes.Console(["yes"]))
        sha = self.repo.direct_commit({"README": "pushed"})
        extra = {f"commits/{sha}/pulls": []}
        with self.assertRaises(fo.Refused):
            self.baseline(fakes.Console(["yes", "yes"]), advance=True, extra=extra)
        self.assertEqual(self.recorded()["release_head"], self.repo.base)
        self.baseline(fakes.Console([f"accept {sha}", "yes"]), advance=True, extra=extra)
        self.assertEqual(self.recorded()["release_head"], sha)
        accepted = [json.loads(line)["signed"]["receipt"]["accepted"] for line in pathlib.Path(self.cfg["ledger"]).read_text().splitlines()]
        self.assertEqual(accepted[-1], [sha])

    def test_accepting_one_commit_does_not_accept_another(self):
        self.baseline(fakes.Console(["yes"]))
        a = self.repo.direct_commit({"README": "a"})
        b = self.repo.direct_commit({"README": "b"})
        extra = {f"commits/{a}/pulls": [], f"commits/{b}/pulls": []}
        with self.assertRaises(fo.Refused):
            self.baseline(fakes.Console([f"accept {a}", f"accept {a}"]), advance=True, extra=extra)

    def test_baseline_refuses_a_broken_invariant_and_mid_deploy(self):
        self.w.staged = "pending"
        with self.assertRaises(fo.Refused) as cm:
            self.baseline(fakes.Console(["yes"]))
        self.assertIn(self.block["invariants"]["staged"]["why"], str(cm.exception))
        self.w.staged = "none"
        self.w.mode = "manual"
        with self.assertRaises(fo.Refused):
            self.baseline(fakes.Console(["yes"]))
        self.w.mode = "auto"
        self.w.add("jobs", "BUILDING", self.repo.base)
        with self.assertRaises(fo.Refused) as cm:
            self.baseline(fakes.Console(["yes"]))
        self.assertIn("mid-deploy (jobs)", str(cm.exception))
        self.assertIsNone(self.recorded())

    def test_declining_records_nothing(self):
        with self.assertRaises(fo.Refused):
            self.baseline(fakes.Console(["no"]))
        self.assertIsNone(self.recorded())

    def test_refuses_while_a_gate_run_is_unfinished(self):
        fo.ledger_append(self.cfg["ledger"], {"event": "start", "run": "r9", "repo": self.cfg["repo"]})
        with self.assertRaises(fo.Refused):
            self.baseline(fakes.Console(["yes"]))


class DriftTest(GateBase):
    def setUp(self):
        super().setUp()
        self.append_baseline(self.state)

    def drift(self):
        svc = fo.Services(self.gh(), self.repo.git, lambda run: self.env.sandbox)
        return fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret, lambda cfg, token: svc, now_dt=self.clock.now())

    def test_quiet_production_is_ok(self):
        self.assertEqual(self.drift(), ([], "drift: ok"))

    def test_moved_recorded_outputs_are_named(self):
        self.w.settings["cache"]["X"] = "1"
        self.assertIn("settings moved: fp_cache", self.drift()[1])

    def test_a_broken_invariant_is_named(self):
        self.w.staged = "pending"
        self.assertIn("staged is 'pending'", self.drift()[1])

    def test_a_deployment_from_outside_the_release_branch_is_flagged(self):
        self.w.add("web", "SUCCESS", self.repo.base, age=600, branch="main")
        self.assertIn("web: deployment", self.drift()[1])

    def test_an_unexplained_deployment_of_an_unchecked_service_is_flagged_and_a_later_baseline_explains_it(self):
        self.w.add("cache", "SUCCESS", None, age=300)
        self.assertIn("cache: deployment", self.drift()[1])
        self.append_baseline(self.state, at="2026-11-05T12:30:00Z")
        self.assertEqual(self.drift()[0], [])

    def test_a_deployment_older_than_the_window_is_ignored(self):
        self.w.add("cache", "SUCCESS", None, age=30 * 3600)
        self.assertEqual(self.drift()[0], [])

    def test_a_deployment_with_no_usable_time_is_flagged(self):
        self.w.add("cache", "SUCCESS", None)["created"] = "yesterday"
        self.assertIn("cache: a deployment has no usable time", self.drift()[1])

    def test_a_scan_that_leaves_a_service_out_is_flagged(self):
        real = fo.read_step_files

        def drop_cache(name, *a, **kw):
            outputs, detail = real(name, *a, **kw)
            if name == "drift-scan":
                detail["rows"].pop("cache")
            return outputs, detail
        with mock.patch.object(fo, "read_step_files", drop_cache):
            self.assertIn("cache: the deployment scan gave no rows", self.drift()[1])

    def test_the_weak_git_provenance_alarm_flags_a_direct_push(self):
        self.repo.direct_commit({"README": "pushed"})
        self.assertIn("release without a PR", self.drift()[1])

    def test_a_merge_commit_with_the_right_message_passes_the_weak_check_only(self):
        self.repo.merge_pr({"README": "r2"}, via_main=False)
        line = self.drift()[1]
        self.assertNotIn("release without a PR", line)
        self.assertIn("main lacks", line)
        self.assertIn("merged a branch that is not in main", line)

    def test_a_rewritten_branch_is_reported_as_an_issue_and_fails(self):
        self.repo.sh("checkout", "-q", "--orphan", "other")
        self.repo.sh("commit", "-q", "--allow-empty", "-m", "rewritten history")
        orphan = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "-f", "release/production")
        self.repo.git.fetch("x", "+refs/heads/other:refs/factory/other")
        state = self.copy(self.state)
        state["release_head"] = orphan
        self.append_baseline(state)
        issues, line = self.drift()
        self.assertIn(f"recorded release head {orphan[:12]} isn't an ancestor of the branch head: rewritten", line)
        self.assertTrue(issues)

    def test_unfetchable_remote_or_missing_record_is_reported_not_raised(self):
        git = fo.Git(self.repo.clone, remote=lambda repo: "/nonexistent/path", ssh_remote=lambda repo: "/nonexistent/path")
        svc = fo.Services(self.gh(), git, lambda run: self.env.sandbox)
        issues, line = fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret, lambda c, t: svc)
        self.assertIsNone(issues)
        self.assertIn("can't fetch", line)
        pathlib.Path(self.cfg["ledger"]).unlink()
        self.assertEqual(self.drift(), (None, "drift: no recorded state"))

    def test_a_content_comparison_is_skipped_while_a_release_is_mid_deploy(self):
        sha = self.merge({"jobs/work.txt": "j2"})
        self.w.add("jobs", "BUILDING", sha)
        self.assertNotIn("jobs isn't content-equal", self.drift()[1])

    def test_a_settled_service_off_the_branch_head_is_flagged(self):
        self.merge({"jobs/work.txt": "j2"})
        self.assertIn("jobs isn't content-equal", self.drift()[1])


class SandboxTest(unittest.TestCase):
    """The real Sandbox, with systemd-run replaced by a process double that writes the step's outputs."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cfg = fakes.make_config(self.tmp, self.tmp / "lib")
        (self.tmp / "lib").mkdir()
        self.etc = self.tmp / "etc"
        self.etc.mkdir()
        for name, text in (("host.token", fakes.SENTINEL_TOKEN), ("fingerprint.key", fakes.FP_KEY.hex())):
            (self.etc / name).write_text(text)
            (self.etc / name).chmod(0o600)
        self.cat = fakes.catalog()
        self.seen, self.argvs, self.stops = [], [], []

    def sandbox(self, wait=lambda p, timeout=None: 0, outputs=None, detail=None):
        outer = self
        outputs = outputs if outputs is not None else "healthy=yes\nservices=4\nunhealthy=\nweb_deployment=dep-0001\njobs_deployment=dep-0002\n"

        class Proc:
            def __init__(s, argv, **kw):
                outer.argvs.append(argv)
                d = pathlib.Path(next(a for a in argv if a.startswith("--working-directory=")).split("=", 1)[1])
                outer.seen.append({**{p.name: oct(p.stat().st_mode & 0o777) for p in d.iterdir()}, "_dir": oct(d.stat().st_mode & 0o777)})
                env = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in argv if "=" in a and a.split("=", 1)[0].isupper()}
                pathlib.Path(env["OP_OUT"]).write_text(outputs)
                if detail is not None:
                    pathlib.Path(env["OP_DETAIL"]).write_text(detail)

            def wait(s, timeout=None):
                return wait(s, timeout)

            def kill(s):
                outer.stops.append("kill")
        def runner(argv, **kw):  # systemd says a stopped unit is gone (Sandbox.stop_and_confirm asks)
            if argv[1] == "show":
                return subprocess.CompletedProcess(argv, 0, "inactive\n", "")
            self.stops.append(argv)
        return fo.Sandbox(self.cfg, self.cat, "r1", steps_dir=self.tmp / "steps", popen=Proc,
                          runner=runner, chown=False, secret_dir=self.etc,
                          secret_owner=(os.getuid(), os.getgid()), root=self.tmp / "root")

    def run_health(self, sb):
        return sb.run("health", self.cat["operations"]["health"], {}, "1", self.tmp / "log")

    def test_the_unit_is_sandboxed_without_an_ip_network(self):
        res = self.run_health(self.sandbox())
        self.assertEqual(res.status, "done", res.why)
        argv = " ".join(self.argvs[0])
        for flag in (*fo.STEP_PROPS, "--collect", "--pipe", "--wait"):
            self.assertIn(flag, argv)
        self.assertIn(f"--unit={fo.UNIT_PREFIX}r1-1", argv)
        self.assertIn("--uid=factory-prod-op", argv)
        self.assertIn(f"RuntimeMaxSec={self.cat['operations']['health']['timeout_s'] + 60}", argv)
        self.assertIn("/run/dbus/system_bus_socket", argv)
        self.assertIn(f"/usr/bin/python3 -I {self.cfg['lib_dir']}/factory_op.py op health", argv)

    def test_secrets_are_the_declared_ones_in_a_private_step_dir_and_never_in_argv(self):
        sb = self.sandbox()
        self.run_health(sb)
        files = self.seen[0]
        self.assertEqual((files["secret-token"], files["_dir"]), ("0o600", "0o700"))
        self.assertNotIn("secret-key", files)  # op_secrets: health has no use for it
        for argv in self.argvs:
            self.assertFalse(any(fakes.SENTINEL_TOKEN in a for a in argv))
            self.assertFalse(any(fakes.FP_KEY.hex() in a for a in argv))
        self.assertFalse(any(p.exists() for p in (self.tmp / "steps").iterdir()), "the step dir is deleted afterwards")

    def test_a_secret_file_with_the_wrong_mode_fails_the_step_before_it_starts(self):
        (self.etc / "host.token").chmod(0o644)
        res = self.run_health(self.sandbox())
        self.assertEqual(res.status, "failed")
        self.assertIn("0600", res.why)
        self.assertEqual(self.argvs, [])

    def test_environment_is_explicit_and_has_no_proxy_variables_or_github_token(self):
        self.run_health(self.sandbox())
        envs = [self.argvs[0][i + 1] for i, a in enumerate(self.argvs[0]) if a == "-E"]
        keys = {e.split("=", 1)[0] for e in envs}
        self.assertTrue({"PATH", "OP_OUT", "FACTORY_RUN", "FACTORY_RELEASE_HEAD", "FACTORY_STEP_DIR"} <= keys)
        self.assertFalse({k for k in keys if "PROXY" in k.upper() or "TOKEN" in k.upper()})

    def test_timeout_stops_the_unit_and_reports_timed_out(self):
        state = {"n": 0}

        def wait(proc, timeout=None):
            state["n"] += 1
            if state["n"] == 1:
                raise subprocess.TimeoutExpired("x", timeout)
            return -15
        res = self.run_health(self.sandbox(wait=wait))
        self.assertEqual(res.status, "timed-out")
        self.assertEqual(self.stops[0], ["/usr/bin/systemctl", "stop", f"{fo.UNIT_PREFIX}r1-1"])

    def test_nonzero_exit_fails_but_keeps_valid_outputs(self):
        res = self.run_health(self.sandbox(wait=lambda p, timeout=None: 1, outputs="healthy=no\nservices=4\nunhealthy=web\nrogue=1\n"))
        self.assertEqual((res.status, res.outputs), ("failed", {"healthy": "no", "services": "4", "unhealthy": "web"}))

    def test_outputs_that_break_their_pattern_are_dropped_and_missing_ones_fail(self):
        res = self.run_health(self.sandbox(outputs="healthy=maybe\nservices=4\nunhealthy=\n"))
        self.assertEqual(res.status, "failed")
        self.assertIn("healthy", res.why)

    def test_an_output_written_twice_is_refused(self):
        res = self.run_health(self.sandbox(outputs="healthy=yes\nhealthy=no\nservices=4\nunhealthy=\n"
                                                   "web_deployment=dep-0001\njobs_deployment=dep-0002\n"))
        self.assertEqual(res.status, "failed")
        self.assertNotIn("healthy", res.outputs)

    def test_a_parameter_that_breaks_its_pattern_at_run_time_fails_before_starting(self):
        sb = self.sandbox()
        res = sb.run("release-wait", self.cat["operations"]["release-wait"], {"sha": "not-a-sha"}, "1", self.tmp / "log")
        self.assertEqual(res.status, "failed")
        self.assertEqual(self.argvs, [])
        for params in ({"sha": "a" * 40, "extra": "x"}, {}):
            res = sb.run("release-wait", self.cat["operations"]["release-wait"], params, "2", self.tmp / "log")
            self.assertEqual(res.status, "failed")
        self.assertEqual(self.argvs, [])

    def test_a_project_script_runs_only_for_its_own_operation(self):
        cat = fakes.catalog_dict()
        cat["operations"]["warm-cache"] = {"kind": "read", "summary": "x", "timeout_s": 60, "outputs": {}}
        cat["broker"]["op_secrets"]["warm-cache"] = []
        self.cat = fakes.load(cat)
        (self.tmp / "lib" / "ops").mkdir()
        for name in ("warm-cache", "health"):
            (self.tmp / "lib" / "ops" / f"{name}.sh").write_text("exit 0\n")
        sb = self.sandbox(outputs="")
        sb.run("warm-cache", self.cat["operations"]["warm-cache"], {}, "1", self.tmp / "log")
        self.assertEqual(self.argvs[-1][-2:], ["/bin/bash", str(self.tmp / "lib" / "ops" / "warm-cache.sh")])
        sb.run("health", self.cat["operations"]["health"], {}, "2", self.tmp / "log")
        self.assertEqual(self.argvs[-1][-3:], [f"{self.cfg['lib_dir']}/factory_op.py", "op", "health"])

    def test_root_keeps_only_clean_notes_and_drift_rows_for_declared_services(self):
        detail = json.dumps({"notes": ["ok \x1b[31mred", 5, "secret " + fakes.SENTINEL_TOKEN] + ["n"] * 100,
                             "rows": {"web": [{"id": "dep-1", "commit": "x", "created": "2026-11-05T09:00:00Z", "branch": 3}],
                                      "rogue": [{"id": "z"}]}})
        res = self.run_health(self.sandbox(detail=detail))
        self.assertEqual(res.detail["rows"], None)  # rows are drift-scan's alone
        self.assertEqual(len(res.detail["notes"]), fo.MAX_NOTES - 1)
        self.assertEqual(res.detail["notes"][0], "ok ?[31mred")
        self.assertNotIn(fakes.SENTINEL_TOKEN, " ".join(res.detail["notes"]))
        sb = self.sandbox(outputs="", detail=detail)
        scan = sb.run("drift-scan", fo.op_of(self.cat, "drift-scan"), {}, "3", self.tmp / "log", "a" * 40)
        self.assertEqual(scan.detail["rows"], {"web": [{"id": "dep-1", "commit": None, "created": "2026-11-05T09:00:00Z", "branch": None}]})

    def test_a_nested_or_unparsable_detail_file_is_dropped_not_a_crash(self):
        for detail in ("[" * 100000, "not json", '"a string"'):
            with self.subTest(detail[:10]):
                res = self.run_health(self.sandbox(detail=detail))
                self.assertEqual(res.status, "done")
                self.assertEqual(res.detail, {"notes": [], "rows": None})


class HiddenPathsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cfg = fakes.make_config(self.tmp, self.tmp / "lib")

    def tier(self, name, cfg):
        d = self.tmp / "etc" / name
        d.mkdir(parents=True)
        (d / "config.json").write_text(cfg if isinstance(cfg, str) else json.dumps(cfg))

    def test_other_tiers_directories_and_deploy_dirs_are_hidden(self):
        self.tier("factory-prod-two", {"deploy_dir": "/srv/two"})
        hidden = fo.hidden_paths(self.cfg, own="factory-prod", root=self.tmp).split()
        for path in ("/run/factory-prod-two", "/var/lib/factory-prod-two", "/var/log/factory-prod-two", "/etc/factory-prod-two",
                     "/var/lib/factory-prod-two-clone", "/srv/two", self.cfg["log_dir"]):
            self.assertIn("-" + path, hidden)
        self.assertFalse(any("factory-prod-op" in p or p == "-/run/factory-prod" for p in hidden))

    def test_a_path_that_cant_be_one_property_value_is_refused(self):
        for cfg in ({"deploy_dir": "/srv/with space"}, {"deploy_dir": "/srv/../etc"}, "not json"):
            with self.subTest(cfg=cfg):
                shutil.rmtree(self.tmp / "etc", ignore_errors=True)
                self.tier("factory-prod-two", cfg)
                with self.assertRaises(fo.Refused):
                    fo.hidden_paths(self.cfg, own="factory-prod", root=self.tmp)


if __name__ == "__main__":
    unittest.main()
