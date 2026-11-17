"""The plan guard's checks of a gate's shape that a broker would otherwise refuse only at its gate run (z-sdlc
process/factory.md, D4 rules 3 and 13): a worst case that outruns the gate run's job, a gate with no steps, and a
release gate the broker doesn't take, with or without a gate-ops block. A release gate's merge is the deploy, so a
refusal that comes only at its gate run comes after production has changed.
Run by CI: python -m unittest discover -s .github/factory/tests"""

import json
import pathlib
import re
import sys
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
import gates  # noqa: E402

OPERATIONS = {
    "health": {"kind": "read", "summary": "Production's health", "timeout_s": 600},
    "release-wait": {"kind": "read", "summary": "Wait for production to serve a commit", "timeout_s": 3600,
                     "params": {"sha": "^[0-9a-f]{40}$"}},
    "backup-now": {"kind": "change", "summary": "Back up the database", "timeout_s": 2400,
                   "outputs": {"backup": "^[a-z0-9-]{1,64}$"}},
    "drop-backup": {"kind": "change", "summary": "Remove a backup", "timeout_s": 300, "rollback_only": True,
                    "params": {"backup": "^[a-z0-9-]{1,64}$"}},
}


def catalog(**fields):
    return gates.load_catalog(json.dumps({"version": 1, "release_gates": True, "operations": OPERATIONS, **fields}))


def plan(gate_body):
    return f"""# D9: Thing

### Phase 1: Code

Write it.

### Gate G1: Production

**After:** Phase 1. **Changes production:** yes.
{gate_body}

### Phase 2: Records

Write the result.
"""


def block(steps, rollback=None):
    body = {"steps": steps, **({"rollback": rollback} if rollback is not None else {})}
    return f"\n```gate-ops\n{json.dumps(body)}\n```"


def healths(n):
    return [{"id": f"h{i}", "op": "health"} for i in range(n)]


RELEASE = "**Release:** the next phase needs the code live"


class TheGateRunsJob(unittest.TestCase):
    def test_the_limit_is_factory_gate_yml_s_execute_job(self):
        text = (FACTORY / "templates" / "factory-gate.yml").read_text()
        job = re.search(r"^  execute:\n(.*?)(?=^  [a-z-]+:\n)", text, re.M | re.S)
        self.assertIsNotNone(job, "factory-gate.yml has no execute job")
        minutes = re.search(r"^    timeout-minutes: ([0-9]+)$", job.group(1), re.M)
        self.assertEqual(int(minutes.group(1)) * 60, gates.GATE_JOB_S,
                         "the execute job's timeout-minutes and gates.GATE_JOB_S must change together")


class Budget(unittest.TestCase):
    def test_a_catalog_that_declares_nothing_still_counts_every_timeout(self):
        backups = [{"id": f"b{i}", "op": "backup-now"} for i in range(8)]
        self.assertEqual(gates.check_plan(plan(block(backups[:7])), catalog()), [])  # 7 x 2400 = 16800 s
        [error] = gates.check_plan(plan(block(backups)), catalog())  # 8 x 2400 = 19200 s
        self.assertIn("G1: its steps could take 19200 s with the broker's own 0 s", error)

    def test_the_broker_s_own_time_and_margins_count(self):
        cat = catalog(gate_overhead_s=5400, step_margin_s=90)
        # 11000 + 12 x (600 + 90) = 19280 s: over.
        [error] = gates.check_plan(plan(block(healths(12))), catalog(gate_overhead_s=11000, step_margin_s=90))
        self.assertTrue(error.startswith("G1: its steps could take 19280 s"), error)
        self.assertIn("more than the gate run's 18000 s", error)
        self.assertEqual(gates.check_plan(plan(block(healths(12))), cat), [])  # 5400 + 12 x 690 = 13680 s

    def test_the_rollback_counts_since_it_runs_after_a_failed_step(self):
        steps = [{"id": "backup", "op": "backup-now"}] + healths(4)
        rollback = [{"op": "drop-backup", "with": {"backup": "${steps.backup.backup}"}}]
        # 2400 + 4 x 600 + 300 = 5100, plus 12900 of the broker's own: 18000, then 18001.
        self.assertEqual(gates.check_plan(plan(block(steps, rollback)), catalog(gate_overhead_s=12900)), [])
        [error] = gates.check_plan(plan(block(steps, rollback)), catalog(gate_overhead_s=12901))
        self.assertIn("G1: its steps could take 18001 s", error)

    def test_a_release_gate_counts_the_broker_s_own_wait_unless_the_block_starts_with_it(self):
        cat = catalog(release_wait="release-wait", gate_overhead_s=8400)
        # The broker's wait (3600) + 10 x 600 + 8400 = 18000: fits. One more health step doesn't.
        self.assertEqual(gates.check_plan(plan(RELEASE + block(healths(10))), cat), [])
        [error] = gates.check_plan(plan(RELEASE + block(healths(11))), cat)
        self.assertIn("G1: its steps could take 18600 s", error)
        # The block's own release-wait is the gate's wait: the broker adds none, so it isn't counted twice.
        own_wait = [{"op": "release-wait", "with": {"sha": "${head}"}}] + healths(10)
        self.assertEqual(gates.check_plan(plan(RELEASE + block(own_wait)), cat), [])

    def test_a_release_gate_with_no_block_still_has_the_broker_s_wait(self):
        self.assertEqual(gates.check_plan(plan(RELEASE), catalog(release_wait="release-wait", gate_overhead_s=14400)), [])
        [error] = gates.check_plan(plan(RELEASE), catalog(release_wait="release-wait", gate_overhead_s=14401))
        self.assertIn("G1: its steps could take 18001 s", error)

    def test_a_cd_gate_runs_nothing_so_it_has_no_budget(self):
        self.assertEqual(gates.check_plan(plan("**Runbook:**\n- [ ] by hand"), catalog(gate_overhead_s=18000)), [])

    def test_a_broken_block_reports_its_own_errors_not_a_budget(self):
        errors = gates.check_plan(plan(block([{"op": "nope"}])), catalog(gate_overhead_s=18000))
        self.assertEqual(errors, ["G1.steps[1]: 'nope' isn't in the operations catalog"])


class CatalogDeclarations(unittest.TestCase):
    def test_absent_declarations_are_none(self):
        cat = catalog()
        self.assertNotIn("gate_overhead_s", cat)
        self.assertEqual(gates.check_plan(plan(block(healths(1))), cat), [])

    def test_bad_declarations_are_refused(self):
        for fields, message in (
                ({"gate_overhead_s": -1}, "gate_overhead_s must be a whole number of seconds from 0 to 18000"),
                ({"gate_overhead_s": 18001}, "gate_overhead_s must be"),
                ({"gate_overhead_s": True}, "gate_overhead_s must be"),
                ({"gate_overhead_s": 60.0}, "gate_overhead_s must be"),
                ({"step_margin_s": 3601}, "step_margin_s must be a whole number of seconds from 0 to 3600"),
                ({"release_wait": "nope"}, "release_wait must name a read operation"),
                ({"release_wait": "backup-now"}, "release_wait must name a read operation"),
                ({"release_wait": ["release-wait"]}, "release_wait must name a read operation")):
            with self.subTest(fields=fields), self.assertRaisesRegex(gates.Invalid, re.escape(message)):
                catalog(**fields)

    def test_a_rollback_only_operation_can_t_be_the_wait(self):
        ops = {**OPERATIONS, "undo-wait": {"kind": "read", "summary": "x", "timeout_s": 60, "rollback_only": True}}
        with self.assertRaisesRegex(gates.Invalid, "release_wait must name a read operation"):
            gates.load_catalog(json.dumps({"version": 1, "operations": ops, "release_wait": "undo-wait"}))


class GateShapes(unittest.TestCase):
    def test_a_gate_with_no_steps_is_refused(self):
        for body in ({"steps": []}, {"rollback": [{"op": "health"}]}, {}):
            with self.subTest(body=body):
                errors = gates.check_plan(plan(f"\n```gate-ops\n{json.dumps(body)}\n```"), catalog())
                self.assertEqual(len(errors), 1)
                self.assertTrue(errors[0].startswith("G1"), errors[0])

    def test_a_release_gate_with_no_block_needs_a_broker_that_takes_release_gates(self):
        # Before, check_plan skipped a gate with no block, so this passed the plan guard and was refused only at
        # the gate request.
        self.assertEqual(gates.check_plan(plan(RELEASE), catalog()), [])
        for declared in (None, False):
            with self.subTest(release_gates=declared):
                text = {"version": 1, "operations": OPERATIONS}
                if declared is not None:
                    text["release_gates"] = declared
                errors = gates.check_plan(plan(RELEASE), gates.load_catalog(json.dumps(text)))
                self.assertEqual(len(errors), 1)
                self.assertIn("G1: a release gate, but the production broker doesn't take release gates", errors[0])


if __name__ == "__main__":
    unittest.main()
