"""A release gate's merge is the deploy, so a refusal the broker makes only afterwards can't be recovered by editing the
plan. The plan guard (gates.check_plan) is what a plan PR's CI runs, so for each refusal the broker makes from a plan's
gate the guard must make it too, and on the same terms:

- the worst-case time budget: the guard's gates.budget_errors, from the catalog's gate_overhead_s, step_margin_s and
  release_wait, against the broker's budget_problem, on every catalog the broker accepts (a catalog that claims less
  than the broker's own time is one it refuses outright), and over the project's own plans;
- release gates at all: the guard and the broker each take one exactly when the catalog's release_gates is true.

Changed on purpose from the third project's broker tests (test_release_plans_fit.py, test_release_gates_declared.py):
there the guard lacked the budget, so a test ran the broker's own over the repository's plans; and its broker took
release gates exactly when its kinds named them. Here the guard has the budget, and the broker always knows the kind and
goes by release_gates, which stays false while a project enables the broker. The project's own catalog and plans are
checked when they exist (production/ops.json, docs/current_work/), and skipped before the enable runbook writes them."""

import pathlib
import tempfile
import unittest

import fakes
from fakes import Env, TOKEN
import factory_op as fo
import gates
from test_broker_release_gate import PLAN

REPO_ROOT = fakes.PROD.parents[2]
OPS = fakes.PROD / "ops.json"
PLAN_DIRS = ("docs/current_work/sdlc-lite", "docs/current_work/planning")


def plan_files(root):
    """The files gates.py would treat as a plan: the paths its PLAN_PATH accepts, under the directories it names."""
    root = pathlib.Path(root)
    found = []
    for d in PLAN_DIRS:
        for path in sorted((root / d).glob("*.md")) if (root / d).is_dir() else []:
            rel = path.relative_to(root).as_posix()
            if gates.PLAN_PATH.fullmatch(rel):
                found.append((rel, path))
    return found


def as_request(g):
    """What the broker would be asked for a plan's gate, as far as its budget reads it."""
    steps = [{"id": s.get("id", s["op"]), "op": s["op"], "with": s.get("with", {})} for s in (g["block"] or {}).get("steps", [])]
    return {"kind": "release" if g["release"] else "ops", "steps": steps, "rollback": []}


def release_gate_problems(root, catalog):
    """[(plan path, gate id, problem)] for every release gate in the plans under root that the plan guard or the broker would
    refuse for its time: the guard's budget (gates.budget_errors) and the broker's (fo.budget_problem), so a gate the guard
    passes and the broker refuses after the merge shows up here."""
    problems = []
    for rel, path in plan_files(root):
        text = path.read_text()
        try:
            parsed = gates.parse_gates(text)
        except gates.Invalid as e:
            if "**Release:**" in text:  # a plan the guard can't read holds a release gate the broker can't be shown to accept
                problems.append((rel, "-", f"can't parse the plan's gates: {e}"))
            continue
        for g in parsed:
            if not g["release"]:
                continue
            steps = (g["block"] or {}).get("steps") or []
            unknown = [s.get("op") if isinstance(s, dict) else s for s in steps
                       if not isinstance(s, dict) or s.get("op") not in catalog["operations"]]
            if unknown:
                problems.append((rel, g["id"], f"unknown operation {unknown[0]!r}"))
                continue
            found = gates.budget_errors(g, catalog) + [p for p in [fo.budget_problem(catalog, as_request(g))] if p]
            if found:
                problems.append((rel, g["id"], found[0]))
    return problems


def plan_text(steps):
    return f"""# D9: Thing

### Phase 1: Code

Write it.

### Gate G1: The web service reaches production

**After:** Phase 1. **Changes production:** yes.
**Release:** the next phase needs the code live

```gate-ops
{{"steps": [{", ".join(steps)}]}}
```

### Phase 2: Records

Write the result.
"""


def slow_catalog(wait_s=None, **changes):
    cat = fakes.catalog_dict(**changes)
    cat["operations"]["health"]["timeout_s"] = 2900  # four health steps fit a gate's run, five don't
    if wait_s:
        cat["operations"]["release-wait"]["timeout_s"] = wait_s
    return fakes.load(cat)


class BudgetAgreementTest(unittest.TestCase):
    def gate(self, steps, release):
        return {"id": "G1", "title": "t", "release": "the next phase needs the code live" if release else None,
                "block": {"steps": steps}, "line": 1}

    def test_the_plan_guard_and_the_broker_agree_on_every_block_for_every_catalog_the_broker_accepts(self):
        catalogs = {"the test catalog": fakes.catalog(), "a slow health": slow_catalog(),
                    "more overhead and margin": slow_catalog(gate_overhead_s=9000, step_margin_s=300),
                    "a long release wait": slow_catalog(wait_s=3600)}
        wait = {"id": "w", "op": "release-wait", "with": {"sha": "${head}"}}
        for label, cat in catalogs.items():
            self.assertEqual(fo.broker_problems(cat), [], label)
            refused = set()
            for n in range(gates.MAX_STEPS + 1):
                for release in (True, False):
                    for wait_first in (False, True):
                        steps = ([wait] if wait_first else []) + [{"id": f"h{i}", "op": "health"} for i in range(n)]
                        g = self.gate(steps, release)
                        guard = bool(gates.budget_errors(g, cat))
                        broker = fo.budget_problem(cat, as_request(g)) is not None
                        with self.subTest(label, n=n, release=release, wait_first=wait_first):
                            self.assertEqual(guard, broker, "the plan guard and the broker disagree about this gate's time")
                        refused.add(broker)
            if label != "the test catalog":
                self.assertEqual(refused, {True, False}, f"{label}: the cases never crossed the limit")

    def test_a_catalog_claiming_less_than_the_brokers_own_time_is_refused_outright(self):
        floor = fo.min_gate_overhead_s(fakes.catalog())
        for changes, needle in (({"gate_overhead_s": floor - 1}, "gate_overhead_s"), ({"gate_overhead_s": 0}, "gate_overhead_s"),
                                ({"step_margin_s": fo.STEP_KILL_MARGIN_S - 1}, "step_margin_s"), ({"step_margin_s": 0}, "step_margin_s")):
            with self.subTest(changes):
                problems = fo.broker_problems(fakes.load(fakes.catalog_dict(**changes)))
                self.assertTrue(any(needle in p for p in problems), problems)
        self.assertEqual(fo.broker_problems(fakes.load(fakes.catalog_dict(gate_overhead_s=floor,
                                                                          step_margin_s=fo.STEP_KILL_MARGIN_S))), [])

    def test_the_guard_counts_the_brokers_wait_once_from_the_catalog(self):
        self.assertEqual(fakes.catalog()["release_wait"], "release-wait")
        health = [{"id": f"h{i}", "op": "health"} for i in range(5)]
        wait = [{"id": "w", "op": "release-wait"}]
        slow = slow_catalog()
        # A release gate's steps cost the broker's wait too; opening with it costs it once, not twice.
        over = gates.budget_errors(self.gate(health, True), slow)
        self.assertTrue(over)
        self.assertEqual(gates.budget_errors(self.gate(wait + health, True), slow), over)
        self.assertEqual(gates.budget_errors(self.gate(wait + health, False), slow), over)
        self.assertEqual(gates.budget_errors(self.gate(health[:4], True), slow), [])
        # The wait's own timeout is the catalog's: a longer one tips the same four steps over.
        self.assertTrue(gates.budget_errors(self.gate(health[:4], True), slow_catalog(wait_s=3600)))
        self.assertEqual(gates.budget_errors(self.gate(health[:4], False), slow_catalog(wait_s=3600)), [])


class ReleasePlansFitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "docs/current_work/planning").mkdir(parents=True)

    def write(self, name, steps):
        (self.root / "docs/current_work/planning" / name).write_text(plan_text(steps))

    @unittest.skipUnless(OPS.exists(), "no production/ops.json: the project has no production tier yet")
    def test_every_release_gate_in_the_projects_plans_fits_the_gate_runs_budget(self):
        self.assertEqual(release_gate_problems(REPO_ROOT, gates.load_catalog(OPS.read_text())), [])

    def test_an_over_budget_release_gate_is_caught_with_its_plan_and_gate(self):
        self.write("d9_big_plan.md", [f'{{"id": "h{i}", "op": "health"}}' for i in range(5)])
        [(rel, gate, problem)] = release_gate_problems(self.root, slow_catalog())
        self.assertEqual((rel, gate), ("docs/current_work/planning/d9_big_plan.md", "G1"))
        self.assertIn("more than the gate run's", problem)
        self.assertTrue(any("more than the gate run's" in e for e in gates.check_plan(plan_text(
            [f'{{"id": "h{i}", "op": "health"}}' for i in range(5)]), slow_catalog())))

    def test_a_release_gate_that_fits_passes(self):
        self.write("d9_ok_plan.md", ['{"op": "health"}',
                                     '{"op": "http-check", "with": {"target": "web", "path": "/status", "expect_status": "200"}}'])
        self.assertEqual(release_gate_problems(self.root, fakes.catalog()), [])
        self.assertEqual(gates.check_plan((self.root / "docs/current_work/planning/d9_ok_plan.md").read_text(), fakes.catalog()), [])

    def test_files_gates_py_would_not_take_as_plans_are_not_looked_at(self):
        self.write("d9_big_notes.md", [f'{{"id": "h{i}", "op": "health"}}' for i in range(5)])
        (self.root / "docs/current_work/planning/D9_big_plan.md").write_text(plan_text(['{"op": "health"}'] * 5))
        self.assertEqual(plan_files(self.root), [])

    def test_an_unreadable_plan_with_a_release_line_is_reported(self):
        (self.root / "docs/current_work/planning/d9_bad_plan.md").write_text("# D9\n\n### Gate G2: wrong order\n\n**Release:** x\n")
        [(rel, gate, _)] = release_gate_problems(self.root, fakes.catalog())
        self.assertEqual((rel, gate), ("docs/current_work/planning/d9_bad_plan.md", "-"))

    def test_an_unknown_operation_in_a_release_gate_is_reported(self):
        self.write("d9_odd_plan.md", ['{"op": "deploy"}'])
        [(_, _, problem)] = release_gate_problems(self.root, fakes.catalog())
        self.assertIn("unknown operation", problem)


class ReleaseGatesDeclaredTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)

    def broker_takes(self, cat):
        """Whether execute gets past the release_gates check for a release request: with an empty ledger, the next thing it
        says is that there is no recorded state."""
        req = {"pr": 7, "gate": "G1", "issue": 3, "attempt": 1, "digest": "d" * 64, "head": "a" * 40, "kind": "release",
               "plan_blob": "b" * 40, "rollback": [], "steps": [{"id": "h", "op": "health", "with": {}}],
               "release": {"branch": "release/production", "pr": 41, "merge": "c" * 40}}
        with self.assertRaises(fo.Refused) as cm:
            fo.execute(self.env.cfg, gates, cat, req, "def", fakes.APPROVER, 55, [], lambda r: r, TOKEN,
                       self.env.services(fakes.github_for(self.env.cfg, self.env.repo, [])), self.env.public, host_run="run1")
        if str(cm.exception) == fo.RELEASE_GATES_OFF:
            return False
        self.assertIn("no recorded state", str(cm.exception))
        return True

    def guard_takes(self, cat):
        return not any(gates.RELEASE_GATES_REFUSED in e for e in gates.check_plan(PLAN, cat))

    def test_the_plan_guard_and_the_broker_take_release_gates_exactly_when_the_catalog_declares_them(self):
        self.assertIn("release", fo.REQUEST_KINDS)  # the broker always knows the kind; the catalog says whether it takes it
        for declared in (True, False):
            with self.subTest(release_gates=declared):
                cat = fakes.load(fakes.catalog_dict(release_gates=declared))
                self.assertEqual(fo.broker_problems(cat), [])
                self.assertEqual(self.guard_takes(cat), declared)
                self.assertEqual(self.broker_takes(cat), declared)
        self.assertEqual(self.env.sandbox.runs, [])

    @unittest.skipUnless(OPS.exists(), "no production/ops.json: the project has no production tier yet")
    def test_the_projects_catalog_says_it_once_for_both(self):
        cat = gates.load_catalog(OPS.read_text())
        self.assertIs(type(cat.get("release_gates")), bool, "production/ops.json must say release_gates true or false")
        self.assertEqual(self.guard_takes(cat), cat["release_gates"])
        self.assertEqual(self.broker_takes(cat), cat["release_gates"])


if __name__ == "__main__":
    unittest.main()
