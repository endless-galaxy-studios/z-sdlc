"""The planning stages' sandbox probe (factory-smoke's planning-sandbox job, D2 rule 5, D3): it runs on the
planning tier in the planning stages' job setup, and the workflow policy lets that one job, and no other smoke
job, use the planning runners, environment and service slots. The planning tool policy is implement's, which
smoke probes, plus WebFetch (D3 rule 5)."""

import pathlib
import shlex
import sys
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))

import render  # noqa: E402

try:
    import yaml  # noqa: F401
    import workflow_policy as policy  # noqa: E402
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@unittest.skipUnless(HAS_YAML, "needs PyYAML")
class PlanningProbe(unittest.TestCase):
    def setUp(self):
        self.assertEqual(policy.configure(FACTORY), [])
        smoke = yaml.safe_load(render.render_all(FACTORY, FACTORY / "templates")["factory-smoke.yml"])
        self.workflow_env = smoke.get("env") or {}
        self.jobs = smoke["jobs"]
        self.probe = self.jobs["planning-sandbox"]

    def failures(self, name, job):
        return policy.job_failures(name, job, self.workflow_env, None, FACTORY, "factory-smoke.yml", set())

    def test_it_runs_where_the_planning_stages_run(self):
        self.assertIn(policy.PLANNING_LABEL, self.probe["runs-on"])
        self.assertEqual(self.probe["environment"], policy.PLANNING_ENVIRONMENT)
        run = "\n".join(str(s.get("run", "")) for s in self.probe["steps"])
        self.assertIn("planning-services.sh", run)  # the reader password, held by pgbouncer
        self.assertIn("python3 -I .github/factory/services.py .github/factory/services.json plan", run)
        agent = next(s for s in self.probe["steps"] if str(s.get("uses", "")).startswith(policy.ACTION))
        self.assertIn("planning-sandbox.settings.json", agent["with"]["settings"])
        self.assertEqual(set(agent["env"]), policy.SERVICE_SLOTS)

    def test_the_policy_admits_it(self):
        self.assertEqual(self.failures("planning-sandbox", self.probe), [])

    def test_no_other_smoke_job_may_use_the_planning_tier(self):
        failures = self.failures("bash-sandbox-on-planning", self.probe)
        self.assertTrue(any("only the planning workflows may run on" in f for f in failures), failures)
        self.assertTrue(any("FACTORY_SVC_1 reaches the agent" in f for f in failures), failures)

    def test_only_the_planning_probe_is_judged_by_the_open_internet(self):
        verdict = lambda job: next(str(s.get("run")) for s in job["steps"]  # noqa: E731
                                   if 'sandbox_check.py" agent' in str(s.get("run", "")))
        self.assertRegex(verdict(self.probe), r"planning-probe\.services\" open \|\|")
        self.assertNotRegex(verdict(self.jobs["bash-sandbox"]), r"\sopen\b")
        # The policy refuses `open` anywhere else, the strict tier's probe included.
        opened = {**self.jobs["bash-sandbox"], "steps": [
            {**s, "run": str(s.get("run", "")).replace('/services" || bad=1', '/services" open || bad=1')}
            for s in self.jobs["bash-sandbox"]["steps"]]}
        self.assertRegex(verdict(opened), r"\sopen \|\|")
        failures = self.failures("bash-sandbox", opened)
        self.assertTrue(any("may be judged by the open internet" in f for f in failures), failures)

    def test_the_probe_must_run_on_the_planning_tier(self):
        moved = {**self.probe, "runs-on": ["self-hosted", self.jobs["bash-sandbox"]["runs-on"][1]]}
        failures = self.failures("planning-sandbox", moved)
        self.assertTrue(any("sandbox probe must run on" in f for f in failures), failures)


class PlanningToolPolicy(unittest.TestCase):
    def words(self, name):
        return shlex.split((FACTORY / name).read_text())

    def test_plan_is_implement_plus_webfetch(self):
        """plan-tools.args has no probe of its own in factory-smoke: implement's (probed by implement-tools)
        plus WebFetch, D3 rule 5's open internet, which runs outside the Bash sandbox, and the same denies."""
        plan, implement = self.words("plan-tools.args"), self.words("implement-tools.args")
        tools = lambda w: set(w[w.index("--tools") + 1].split(","))  # noqa: E731
        allowed = lambda w: set(w[w.index("--allowedTools") + 1:w.index("--disallowedTools")])  # noqa: E731
        denies = lambda w: w[w.index("--disallowedTools"):]  # noqa: E731 - every deny rule, in order
        self.assertEqual(tools(plan) - tools(implement), {"WebFetch"})
        self.assertLessEqual(tools(implement), tools(plan))
        self.assertEqual(allowed(plan) - allowed(implement), {"WebFetch"})
        self.assertEqual(denies(plan), denies(implement))


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAS_YAML, "needs PyYAML")
class ServiceSlotTiers(unittest.TestCase):
    """Each tier's service credentials stay in their tier: FACTORY_SVC_n (planning) only in planning agent
    jobs, FACTORY_EXEC_SVC_n (execution) only in implement and revise agent jobs, and either only where the
    job builds its settings with services.py, which masks every slot (process/factory.md, D2 rule 8, D3)."""

    def setUp(self):
        self.assertEqual(policy.configure(FACTORY), [])
        rendered = render.render_all(FACTORY, FACTORY / "templates")
        self.flows = {name: yaml.safe_load(rendered[name]) for name in ("factory-implement.yml", "factory-plan.yml")}

    def agent_job(self, workflow):
        jobs = self.flows[workflow]["jobs"]
        name = next(n for n, j in jobs.items() if any(str(s.get("uses", "")).startswith(policy.ACTION)
                                                      for s in j.get("steps", [])))
        return name, jobs[name]

    def failures(self, workflow, name, job):
        flow = self.flows[workflow]
        triggers = flow.get("on", flow.get(True)) or {}  # YAML 1.1 reads a bare `on:` as True
        dispatch = triggers.get("workflow_dispatch") if isinstance(triggers, dict) else None
        model_input = ((dispatch or {}).get("inputs") or {}).get("model")
        return policy.job_failures(name, job, flow.get("env") or {}, model_input, FACTORY, workflow, set())

    def with_agent_env(self, job, env):
        steps = [dict(s, env={**(s.get("env") or {}), **env}) if str(s.get("uses", "")).startswith(policy.ACTION) else s
                 for s in job["steps"]]
        return dict(job, steps=steps)

    def test_the_rendered_workflows_hold(self):
        for workflow in self.flows:
            name, job = self.agent_job(workflow)
            self.assertEqual(self.failures(workflow, name, job), [], workflow)
            agent = next(s for s in job["steps"] if str(s.get("uses", "")).startswith(policy.ACTION))
            want = policy.EXEC_SERVICE_SLOTS if workflow == "factory-implement.yml" else policy.SERVICE_SLOTS
            self.assertEqual(set(agent["env"]), want, workflow)

    def test_a_planning_slot_never_reaches_an_execution_job(self):
        name, job = self.agent_job("factory-implement.yml")
        moved = self.with_agent_env(job, {"FACTORY_SVC_1": "${{ secrets.FACTORY_SVC_1 }}"})
        self.assertIn(f"{name}: Implement env FACTORY_SVC_1 reaches the agent", self.failures("factory-implement.yml", name, moved))

    def test_an_execution_slot_never_reaches_a_planning_job(self):
        name, job = self.agent_job("factory-plan.yml")
        moved = self.with_agent_env(job, {"FACTORY_EXEC_SVC_1": "${{ secrets.FACTORY_EXEC_SVC_1 }}"})
        self.assertTrue(any("FACTORY_EXEC_SVC_1 reaches the agent" in f for f in self.failures("factory-plan.yml", name, moved)))

    def test_an_execution_slot_needs_services_py(self):
        name, job = self.agent_job("factory-implement.yml")
        unbuilt = dict(job, steps=[dict(s, run=str(s["run"]).replace("python3 -I .github/factory/services.py", "true"))
                                   if "services.py" in str(s.get("run", "")) else s for s in job["steps"]])
        self.assertTrue(any("FACTORY_EXEC_SVC_1 reaches the agent" in f
                            for f in self.failures("factory-implement.yml", name, unbuilt)))



@unittest.skipUnless(HAS_YAML, "needs PyYAML")
class McpServicesProbe(unittest.TestCase):
    """factory-smoke's mcp-services job runs two agent steps, and claude-code-action writes every run's execution
    output to one fixed path: the verdict must read a copy of the first, never the second's file twice."""

    def setUp(self):
        self.assertEqual(policy.configure(FACTORY), [])
        smoke = yaml.safe_load(render.render_all(FACTORY, FACTORY / "templates")["factory-smoke.yml"])
        self.workflow_env = smoke.get("env") or {}
        self.job = smoke["jobs"]["mcp-services"]

    def test_the_policy_admits_it(self):
        failures = policy.job_failures("mcp-services", self.job, self.workflow_env, None, FACTORY, "factory-smoke.yml", set())
        self.assertEqual(failures, [])

    def test_the_planning_transcript_is_copied_before_the_next_agent_step(self):
        steps = self.job["steps"]
        ids = [s.get("id") for s in steps]
        copy = next(i for i, s in enumerate(steps) if "mcp-plan-execution.json" in str(s.get("run", "")))
        self.assertLess(ids.index("plan"), copy)
        self.assertLess(copy, ids.index("exec"))
        verdict = next(s for s in steps if "authorization-sha256" in str(s.get("run", "")))
        self.assertIn("$RUNNER_TEMP/mcp-plan-execution.json", verdict["run"])
        self.assertNotIn("steps.plan.outputs.execution_file", str(verdict.get("env", {})))
