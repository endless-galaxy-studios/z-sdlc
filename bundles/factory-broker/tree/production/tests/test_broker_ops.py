"""The generic operations (health, release-wait, http-check, capture-state, drift-scan, host-check) on the fake host:
D4 rule 15's evidence (reports, the two-read heartbeat, the end re-read), and what the broker checks of every answer the
host module gives. Carried over from the third project's broker tests (test_ops.py), with its platform's world replaced
by fake_host. No network, no systemd."""

import datetime
import json
import re
import unittest

import fakes
from fakes import Env
import factory_op as fo
from fake_host import Resp, iso


class OpTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.w, self.clock, self.repo = self.env.world, self.env.clock, self.env.repo

    def run_op(self, name, **params):
        return self.env.run_op(name, **params)

    def total_requests(self):
        return len(self.w.requests) + len(self.w.app_calls)

    def merge(self, files):
        sha = self.repo.merge_pr(files)
        self.repo.fetch()
        return sha

    def ready(self, **override):
        base = self.w.default_ready
        self.w.ready = lambda: {**base(), **{k: (v() if callable(v) else v) for k, v in override.items()}}

    def with_module(self, extra):
        path = self.env.tmp / "host" / fo.HOST_MODULE
        path.parent.mkdir(exist_ok=True)
        path.write_text(fakes.FAKE_HOST.read_text() + "\n" + extra + "\n")
        self.env.sandbox.host_module = path


class HealthTest(OpTest):
    def test_healthy_stack_passes_with_the_serving_ids(self):
        res = self.run_op("health")
        self.assertEqual(res.status, "done", res.why)
        self.assertEqual((res.outputs["healthy"], res.outputs["services"], res.outputs["unhealthy"]), ("yes", "4", ""))
        self.assertEqual(res.outputs["web_deployment"], self.w.serving("web")["id"])
        self.assertEqual(res.outputs["jobs_deployment"], self.w.serving("jobs")["id"])
        self.assertLessEqual(self.total_requests(), fakes.fake_host.BUDGET["health"][0])

    def test_serving_deployment_found_behind_skipped_rows(self):
        for name in ("web", "jobs"):
            for _ in range(11):
                self.w.add(name, "SKIPPED", self.repo.base)
        res = self.run_op("health")
        self.assertEqual(res.status, "done", res.why)
        self.assertEqual(res.outputs["web_deployment"], self.w.serving("web")["id"])

    def test_crashed_after_success_fails(self):
        self.w.add("jobs", "CRASHED", self.repo.base)
        res = self.run_op("health")
        self.assertEqual(res.status, "failed")
        self.assertEqual((res.outputs["healthy"], res.outputs["unhealthy"]), ("no", "jobs"))
        self.assertNotIn("jobs_deployment", res.outputs)

    def test_every_declared_service_needs_a_serving_deployment(self):
        self.w.deployments["cache"].clear()
        self.assertEqual(self.run_op("health").outputs["unhealthy"], "cache")

    def test_a_service_reporting_an_old_deployment_id_fails(self):
        self.ready(deployment_id="dep-9999")
        res = self.run_op("health")
        self.assertEqual((res.status, res.outputs["unhealthy"]), ("failed", "web"))

    def test_no_usable_answer_fails_a_strict_read(self):
        self.w.ready = lambda: Resp(503, {}, b"")
        self.assertEqual(self.run_op("health").outputs["unhealthy"], "web,jobs")

    def test_heartbeat_old_id_fails(self):
        self.ready(jobs_deployment_id="dep-9999")
        self.assertEqual(self.run_op("health").outputs["unhealthy"], "jobs")

    def test_a_definitive_heartbeat_answer_fails_a_strict_read(self):
        self.ready(jobs_state="starting")
        res = self.run_op("health")
        self.assertEqual(res.outputs["unhealthy"], "jobs")
        self.assertIn("not 'ready'", res.why)

    def test_heartbeat_start_time_changing_between_reads_fails(self):
        calls = iter(range(100))
        self.ready(jobs_started_at=lambda: iso(self.clock.now() - datetime.timedelta(seconds=next(calls) + 10)))
        self.assertEqual(self.run_op("health").outputs["unhealthy"], "jobs")

    def test_heartbeat_written_at_not_advancing_fails(self):
        self.ready(jobs_written_at=iso(self.clock.now()))
        res = self.run_op("health")
        self.assertEqual(res.outputs["unhealthy"], "jobs")
        self.assertIn("isn't advancing", res.why)

    def test_heartbeat_written_before_the_deployment_fails(self):
        # advancing on every read (so "not advancing" can't be what fails it), but always older than the deployment
        self.ready(jobs_written_at=lambda: iso(self.clock.now() - datetime.timedelta(days=1)))
        self.assertEqual(self.run_op("health").outputs["unhealthy"], "jobs")

    def test_heartbeat_reads_are_more_than_one_ttl_apart(self):
        before = self.clock.t
        self.run_op("health")
        self.assertGreater(self.clock.t - before, self.env.cat["broker"]["heartbeat_ttl_s"])

    def test_a_service_crashed_by_the_end_of_the_wait_fails(self):
        dep = self.w.deployments["jobs"][0]
        n = []
        self.w.hooks.append(lambda w: (n.append(1), len(n) == 11 and w.add("jobs", "CRASHED", dep["commit"])))
        res = self.run_op("health")
        self.assertEqual(res.outputs["unhealthy"], "jobs")

    def test_serving_a_deployment_that_isnt_successful_fails_the_step(self):
        self.with_module("def serving(ctx, svc):\n    return Deployment('dep-0001', None, 'failed', None)")
        res = self.run_op("health")
        self.assertEqual(res.status, "failed")
        self.assertIn("isn't successful", res.why)


class ReleaseWaitTest(OpTest):
    def wait(self, sha):
        return self.env.sandbox.run("release-wait", self.env.cat["operations"]["release-wait"], {"sha": sha}, "t",
                                    self.env.tmp / "logs" / "rw.log", self.repo.head())

    def test_sha_not_in_heads_history_fails_with_release_pr_not_merged_yet(self):
        res = self.wait("1" * 40)
        self.assertEqual(res.status, "failed")
        self.assertIn("release PR not merged yet", res.why)
        self.assertEqual(self.w.requests, [("GET", "/v1/whoami")])  # preflight, then nothing: it fails before waiting

    def test_unmerged_branch_commit_is_not_in_history(self):
        self.repo.sh("checkout", "-q", "-b", "unmerged")
        self.repo.direct_commit({"web/app.txt": "side"})
        side = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "release/production")
        # The commit is in the clone, so only the ancestry test (not mere presence) can say it isn't in the head's history.
        self.repo.git.fetch("x", "+refs/heads/unmerged:refs/factory/unmerged")
        self.assertTrue(self.repo.git.has(side))
        self.assertIn("not merged yet", self.wait(side).why)

    def test_head_already_serving_still_needs_the_evidence(self):
        res = self.wait(self.repo.base)
        self.assertEqual((res.status, res.outputs["deployed"]), ("done", "web,jobs"), res.why)
        self.assertEqual(res.outputs["web_deployment"], self.w.serving("web")["id"])
        self.assertTrue(self.w.app_calls)

    def test_content_equal_service_with_no_deployment_row_is_done(self):
        head = self.merge({"README": "r2"})  # touches no service's files
        res = self.wait(head)
        self.assertEqual((res.status, res.outputs["deployed"]), ("done", ""), res.why)
        self.assertEqual(res.outputs["jobs_deployment"], self.w.serving("jobs")["id"])

    def release_web(self, status="BUILDING"):
        head = self.merge({"web/app.txt": "w2"})
        self.w.add("jobs", "SKIPPED", head)  # the host skips jobs (its files didn't change) and builds web
        return head, self.w.add("web", status, head)

    def test_deployment_for_head_is_found_by_commit_among_skipped_rows(self):
        head, dep = self.release_web()
        self.w.hooks.append(lambda w: dep.update(status="SUCCESS") if self.clock.t > 90 else None)
        res = self.wait(head)
        self.assertEqual((res.status, res.outputs["deployed"]), ("done", "web"), res.why)
        self.assertEqual(res.outputs["web_deployment"], dep["id"])
        self.assertEqual(res.outputs["jobs_deployment"], self.w.serving("jobs")["id"])  # skipped for unchanged content

    def test_the_hosts_order_isnt_trusted(self):
        head, dep = self.release_web("SUCCESS")
        real = self.w.api

        def oldest_first(method, path, body, headers):
            resp = real(method, path, body, headers)
            if path == "/v1/services/web/deployments":
                resp = Resp(200, {}, json.dumps(list(reversed(json.loads(resp.read())))).encode())
            return resp
        self.w.api = oldest_first
        res = self.wait(head)
        self.assertEqual((res.status, res.outputs["web_deployment"]), ("done", dep["id"]), res.why)

    def test_waits_for_success_at_the_head(self):
        head, dep = self.release_web()
        self.w.hooks.append(lambda w: dep.update(status="SUCCESS") if self.clock.t > 200 else None)
        before = self.clock.t
        self.assertEqual(self.wait(head).status, "done")
        self.assertGreater(self.clock.t - before, 200)

    def test_no_deployment_within_the_grace_fails(self):
        head = self.merge({"web/app.txt": "w2"})
        res = self.wait(head)
        self.assertEqual(res.status, "failed")
        self.assertIn("no deployment created", res.why)
        self.assertGreater(self.clock.t, self.env.cat["broker"]["release_wait_phases"]["grace_s"])

    def test_failed_or_crashed_at_the_head_fails_at_once(self):
        for status, word in (("FAILED", "failed"), ("CRASHED", "crashed"), ("REMOVED", "failed"), ("UNHEARD-OF", "failed")):
            with self.subTest(status):
                self.setUp()
                head, dep = self.release_web(status)
                res = self.wait(head)
                self.assertEqual(res.status, "failed")
                self.assertIn(word, res.why)
                self.assertLess(self.clock.t, 60)

    def test_a_crashed_newest_deployment_with_none_for_the_head_fails(self):
        head = self.merge({"web/app.txt": "w2"})
        self.w.add("web", "CRASHED", self.repo.base)
        res = self.wait(head)
        self.assertEqual(res.status, "failed")
        self.assertIn("crashed", res.why)

    def test_skipped_while_content_differs_fails(self):
        head = self.merge({"web/app.txt": "w2"})
        self.w.add("web", "SKIPPED", head)
        res = self.wait(head)
        self.assertEqual(res.status, "failed")
        self.assertIn("skipped", res.why.lower())

    def release_both(self):
        head = self.merge({"shared/lib.txt": "s2"})
        return head, {n: self.w.add(n, "SUCCESS", head) for n in ("web", "jobs")}

    def test_a_late_first_heartbeat_still_passes(self):
        head, deps = self.release_both()
        old = {"jobs_deployment_id": "dep-0002", "jobs_started_at": iso(self.clock.now()), "jobs_written_at": iso(self.clock.now())}

        def ready():
            if self.clock.t < 400:  # jobs is still starting: no heartbeat of its own yet
                return {**self.w.default_ready(), **old}
            return {**self.w.default_ready(), "jobs_started_at": iso(self.clock.base + datetime.timedelta(seconds=300))}
        self.w.ready = ready
        res = self.wait(head)
        self.assertEqual((res.status, res.outputs["deployed"]), ("done", "web,jobs"), res.why)
        self.assertGreater(self.clock.t, 400)
        self.assertLess(self.clock.t, self.env.cat["operations"]["release-wait"]["timeout_s"] / fo.DEADLINE_MARGIN)

    def test_not_yet_from_a_patient_heartbeat_is_waited_out(self):
        head, deps = self.release_both()
        self.ready(jobs_state=lambda: "starting" if self.clock.t < 200 else "ready")
        res = self.wait(head)
        self.assertEqual(res.status, "done", res.why)
        self.assertGreater(self.clock.t, 200)

    def test_a_definitive_answer_fails_even_a_patient_wait(self):
        head, deps = self.release_both()
        self.ready(jobs_state="failed")
        res = self.wait(head)
        self.assertEqual(res.status, "failed")
        self.assertIn("startup failed", res.why)

    def test_alternating_old_and_new_passes_only_on_the_new_one_twice(self):
        head, deps = self.release_both()
        reads, new_times = [], []

        def ready():
            n = len(reads)
            reads.append(self.clock.t)
            new = n % 2 == 0
            if new:
                new_times.append(self.clock.t)
            base = {**self.w.default_ready(), "jobs_started_at": iso(self.clock.base + datetime.timedelta(seconds=300))}
            return base if new else {**base, "jobs_deployment_id": "dep-0002"}
        self.w.ready = ready
        res = self.wait(head)
        self.assertEqual(res.status, "done", res.why)
        self.assertGreaterEqual(len(new_times), 3)  # the reports read, then the new id seen on two heartbeat reads
        self.assertGreater(new_times[-1] - new_times[1], self.env.cat["broker"]["heartbeat_ttl_s"])
        self.assertGreater(len(reads) - len(new_times), 0)  # old-id reads came between them without failing the wait

    def test_an_old_heartbeat_forever_times_out(self):
        head, deps = self.release_both()
        self.ready(jobs_deployment_id="dep-0002")
        res = self.wait(head)
        self.assertEqual(res.status, "failed")
        self.assertIn("deadline", res.why)
        self.assertGreater(self.clock.t, 700)

    def test_unavailable_answers_are_waited_out_while_patient(self):
        head, deps = self.release_both()
        real = self.w.default_ready
        self.w.ready = lambda: Resp(502, {}, b"") if self.clock.t < 150 else real()
        self.assertEqual(self.wait(head).status, "done")

    def test_superseded_deployment_at_the_end_fails(self):
        head, dep = self.release_web("SUCCESS")
        newer = []
        # A newer deployment is serving by the time the end-of-wait re-read happens.
        self.w.hooks.append(lambda w: newer or newer.append(w.add("web", "SUCCESS", head)) if len(w.app_calls) >= 1 else None)
        res = self.wait(head)
        self.assertEqual(res.status, "failed")
        self.assertIn("at the end of the wait", res.why)

    def test_a_deployment_with_no_usable_time_cant_be_the_heartbeats(self):
        head, deps = self.release_both()
        deps["jobs"]["created"] = "not a time"
        res = self.wait(head)
        self.assertEqual(res.status, "failed")
        self.assertIn("no usable time", res.why)


class HttpCheckTest(OpTest):
    def check(self, **p):
        params = {"target": "web", "path": "/status", "expect_status": "200", **p}
        return self.env.sandbox.run("http-check", self.env.cat["operations"]["http-check"], params, "t",
                                    self.env.tmp / "logs" / "hc.log")

    def test_get_returns_status_latency_and_body_hash(self):
        res = self.check()
        self.assertEqual(res.status, "done", res.why)
        self.assertEqual(res.outputs["status"], "200")
        self.assertRegex(res.outputs["body_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual({c[:3] for c in self.w.app_calls}, {("web.example.com", "GET", "/status")})

    def test_sends_no_credentials_or_cookies(self):
        self.check()
        headers = {k.lower() for k in self.w.app_calls[0][3]}
        self.assertFalse(headers & {"authorization", "cookie"})

    def test_pattern_refusals_including_dot_dot(self):
        for bad in ({"path": "/a/../b"}, {"path": "no-slash"}, {"path": "/UPPER"}, {"path": "/a?x=1"}, {"target": "api"},
                    {"expect_status": "99"}, {"expect_status": "600"}, {"path": "/ready\n"}):
            with self.subTest(bad):
                self.assertEqual(self.check(**bad).status, "failed")
        self.assertEqual(self.w.app_calls, [])

    def test_catalog_patterns_also_refuse_them(self):
        pats = self.env.cat["operations"]["http-check"]["params"]
        self.assertIsNone(re.fullmatch(pats["path"], "/a/../b"))
        self.assertIsNone(re.fullmatch(pats["path"], "/.."))
        self.assertTrue(re.fullmatch(pats["path"], "/status"))

    def test_status_mismatch_fails_but_reports_the_status(self):
        res = self.check(expect_status="204")
        self.assertEqual((res.status, res.outputs["status"]), ("failed", "200"))

    def test_only_the_declared_hosts(self):
        with self.assertRaises(fo.HostError):
            fo.http_exchange(self.w.connect, frozenset(self.env.cat["broker"]["egress"]), "evil.example", "GET", "/", {}, None, 5, 1000)
        self.assertEqual(self.w.app_calls, [])

    def test_body_over_1_mib_fails_and_exactly_1_mib_is_allowed(self):
        self.w.page = lambda path: Resp(200, {}, b"x" * ((1 << 20) + 1))
        self.assertEqual(self.check().status, "failed")
        self.w.page = lambda path: Resp(200, {}, b"x" * (1 << 20))
        self.assertEqual(self.check().status, "done")

    def test_a_redirect_is_refused_not_followed(self):
        self.w.page = lambda path: Resp(301, {"location": "https://evil.example/"}, b"")
        self.assertEqual(self.check(expect_status="301").status, "failed")
        self.assertEqual(len(self.w.app_calls), 1)


class CaptureStateTest(OpTest):
    def test_capture_gives_every_output_root_needs(self):
        res = self.run_op("capture-state")
        self.assertEqual(res.status, "done", res.why)
        self.assertEqual(set(res.outputs), set(self.env.cat["operations"]["capture-state"]["outputs"]))
        self.assertEqual(res.outputs["proxy_commit"], self.repo.base)
        self.assertTrue(any(n.startswith("web: builds from") for n in res.detail["notes"]))
        self.assertLessEqual(self.total_requests(), fakes.fake_host.BUDGET["capture-state"][0])

    def test_a_missing_required_output_fails_the_step(self):
        self.with_module("_capture = capture\ndef capture(ctx):\n    out = _capture(ctx)\n    del out['jobs_settled']\n    return out")
        res = self.run_op("capture-state")
        self.assertEqual(res.status, "failed")
        self.assertIn("jobs_settled", res.why)

    def test_an_output_with_a_line_break_fails_the_step_and_cant_forge_another(self):
        self.with_module("_capture = capture\ndef capture(ctx):\n    out = _capture(ctx)\n"
                         "    out['mode_source'] = 'x\\nfp_web=' + '0' * 64\n    return out")
        res = self.run_op("capture-state")
        self.assertEqual(res.status, "failed")
        self.assertNotEqual(res.outputs.get("fp_web"), "0" * 64)

    def test_an_empty_commit_is_allowed_only_for_a_service_that_isnt_a_release_service(self):
        self.w.deployments["proxy"][0]["commit"] = None
        self.assertEqual(self.run_op("capture-state").outputs["proxy_commit"], "")
        self.w.deployments["proxy"][0]["commit"] = self.repo.base
        self.w.deployments["web"][0]["commit"] = None
        self.assertEqual(self.run_op("capture-state").status, "failed")

    def test_capture_fails_when_the_host_builds_from_other_patterns(self):
        self.w.patterns["jobs"] = ["jobs/**"]
        res = self.run_op("capture-state")
        self.assertEqual(res.status, "failed")
        self.assertIn("patterns", res.why)

    def test_capture_needs_the_branch_head(self):
        res = self.run_op("capture-state", release_head="")
        self.assertEqual(res.status, "failed")
        self.assertIn("head", res.why)

    def test_the_step_reaches_only_the_declared_hosts(self):
        self.with_module("def capture(ctx):\n    ctx.https('evil.example', 'GET', '/', {}, max_bytes=10)")
        res = self.run_op("capture-state")
        self.assertEqual(res.status, "failed")
        self.assertIn("HostError", res.why)
        self.assertEqual(self.w.app_calls, [])


class DriftScanAndHostCheckTest(OpTest):
    def test_drift_scan_writes_rows_for_every_declared_service(self):
        self.w.add("cache", "SUCCESS", None, age=40 * 3600)
        res = self.run_op("drift-scan")
        self.assertEqual(res.status, "done", res.why)
        self.assertEqual(set(res.detail["rows"]), set(fakes.SERVICES))
        self.assertEqual(len(res.detail["rows"]["cache"]), 1)  # the 40-hour-old row is outside the window
        row = res.detail["rows"]["web"][0]
        self.assertEqual((row["commit"], row["branch"]), (self.repo.base, "release/production"))

    def test_host_check_runs_preflight(self):
        self.assertEqual(self.run_op("host-check", release_head="").status, "done")
        self.env.cfg["host"]["services"].pop("cache")
        res = self.run_op("host-check", release_head="")
        self.assertEqual(res.status, "failed")
        self.assertIn("host block", res.why)

    def test_a_diagnostic_runs_without_preflight_and_fails_its_own_step(self):
        self.env.cfg["host"]["services"].pop("cache")  # preflight would refuse this
        res = self.run_op("check-token", release_head="")
        self.assertEqual(res.status, "done", res.why)
        self.assertIn("the token's project: proj-1", res.detail["notes"])
        self.w.project = "proj-2"
        self.assertEqual(self.run_op("check-token", release_head="").status, "failed")

    def test_a_host_op_returns_typed_outputs(self):
        res = self.run_op("snapshot-status")
        self.assertEqual((res.status, res.outputs["fresh"]), ("done", "yes"), res.why)
        res = self.run_op("snapshot-now")
        self.assertEqual(res.outputs["snapshot_id"], "snap-0002")
        self.assertEqual(self.w.created, [{"name": "factory r1"}])

    def test_a_wrong_token_fails_preflight(self):
        self.env.sandbox.token_for_step = "another-token-0123456789abcdef"
        res = self.run_op("health")
        self.assertEqual(res.status, "failed")
        self.assertIn("HostError", res.why)

    def test_a_step_gets_only_its_declared_secrets(self):
        self.with_module("_status = op_snapshot_status\ndef op_snapshot_status(ctx):\n    ctx.secret('key')\n    return _status(ctx)\n"
                         "OPS = {**OPS, 'snapshot-status': op_snapshot_status}")
        res = self.run_op("snapshot-status")
        self.assertEqual(res.status, "failed")
        self.assertIn("isn't given the secret key", res.why)


class BudgetTest(unittest.TestCase):
    def test_every_operations_timeout_covers_its_worst_case(self):
        cat = fakes.catalog()
        for name, (requests, waits) in fakes.fake_host.BUDGET.items():
            with self.subTest(name):
                timeout = fo.op_of(cat, name)["timeout_s"]
                self.assertGreaterEqual(timeout, fo.DEADLINE_MARGIN * (requests * fo.REQUEST_TIMEOUT_S + waits))

    def test_a_healthy_run_makes_no_more_requests_than_it_declares(self):
        env = Env()
        self.addCleanup(env.close)
        for name in ("health", "capture-state", "snapshot-status", "drift-scan", "host-check", "check-token"):
            env.world.requests.clear()
            env.world.app_calls.clear()
            res = env.run_op(name, release_head="" if name in ("health", "host-check", "check-token") else None)
            self.assertEqual(res.status, "done", (name, res.why))
            self.assertLessEqual(len(env.world.requests) + len(env.world.app_calls), fakes.fake_host.BUDGET[name][0], name)

    def test_the_deadline_is_below_the_brokers_kill(self):
        clock = fakes.FakeClock()
        d = fo.Deadline(600 / fo.DEADLINE_MARGIN, clock)
        clock.t = 600 / fo.DEADLINE_MARGIN + 1
        with self.assertRaises(fo.StepFailed):
            d.check()


if __name__ == "__main__":
    unittest.main()
