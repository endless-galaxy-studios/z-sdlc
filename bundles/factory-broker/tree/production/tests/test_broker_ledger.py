"""The ledger's records (z-sdlc process/factory.md D4 rules 8-9): signed baselines and gate states in either shape. A ledger
written before the generic broker records {fingerprints, fp_key_id, seen}; the reader maps it to {release_head, recorded}
with no host code, so a project adopting the bundle keeps its release head and recorded state without a re-baseline. A
record that doesn't match the block stops gates and drift, and still gives baseline its release head."""

import json
import unittest

import fakes
import factory_op as fo
import gates
from test_broker_gate import GateBase, request


def legacy(state, seen=None):
    """The legacy shape of a {release_head, recorded} state: recorded's fp_<name> as fingerprints.<name>."""
    rec = dict(state["recorded"])
    key_id = rec.pop("fp_key_id")
    return {"fingerprints": {n[len("fp_"):]: v for n, v in rec.items()}, "fp_key_id": key_id,
            "seen": {"release_head": state["release_head"], "web": state["release_head"], "jobs": None, **(seen or {})}}


class LegacyShapeTest(unittest.TestCase):
    STATE = {"release_head": "a" * 40, "recorded": {"fp_web": "1" * 64, "fp_shared": "2" * 64, "fp_key_id": "3" * 8}}

    def test_the_legacy_shape_maps_to_the_new_one(self):
        self.assertEqual(fo.to_state(legacy(self.STATE)), self.STATE)
        self.assertEqual(fo.to_state(self.STATE), self.STATE)

    def test_anything_else_doesnt_count(self):
        bad = [None, [], {}, {"release_head": "a" * 40}, {**self.STATE, "extra": 1},
               {"fingerprints": {}, "fp_key_id": "3" * 8},  # no seen
               legacy(self.STATE, seen={"web": "not a commit"}),
               {**legacy(self.STATE), "seen": {"web": "a" * 40}},  # no release head
               {**legacy(self.STATE), "fingerprints": {"key_id": "4" * 64}},  # fp_ + key_id collides with fp_key_id
               {**legacy(self.STATE), "fingerprints": {"Web": "1" * 64}},  # not a field name once prefixed
               {**legacy(self.STATE), "fp_key_id": 5},
               {"release_head": "a" * 40, "recorded": {"fp_web": 1}}, {"release_head": "short", "recorded": {}}]
        for state in bad:
            with self.subTest(state=state):
                self.assertIsNone(fo.to_state(state))


class LegacyLedgerTest(GateBase):
    def sign_baseline(self, state, at="2026-11-05T11:00:00Z"):
        self.append_baseline(state, at=at)

    def entries(self):
        return fo.ledger_entries(self.cfg["ledger"])

    def recorded(self):
        return fo.recorded_state(self.entries(), gates, self.env.public)

    def run_gate(self, steps=None):
        return fo.execute(self.cfg, gates, self.env.cat, request(steps), "def", fakes.APPROVER, 55, self.entries(),
                          lambda r: gates.sign_receipt(self.env.secret, r), fakes.TOKEN, self.services(), self.env.public,
                          host_run="run1")

    def test_a_legacy_baseline_counts_and_matches_so_the_next_gate_needs_no_baseline(self):
        self.sign_baseline(legacy(self.state))
        self.assertEqual(self.recorded(), self.state)
        self.assertIsNone(fo.state_problem(self.recorded(), self.env.cat))
        receipt = self.run_gate()["receipt"]
        self.assertEqual(receipt["status"], "done", receipt)
        self.assertEqual(self.recorded(), self.state)  # the gate's own state, in the new shape, is now the record
        finish = self.entries()[-1]
        self.assertEqual(set(gates.verify_receipt(self.env.public, finish["state_signed"])["deployed_state"]),
                         {"release_head", "recorded"})

    def test_a_legacy_gate_state_counts_only_on_its_own_run(self):
        signed = gates.sign_receipt(self.env.secret, {"v": 1, "kind": "state", "run": "run-A", "deployed_state": legacy(self.state)})
        fo.ledger_append(self.cfg["ledger"], {"event": "finish", "run": "run-B", "state_signed": signed})
        self.assertIsNone(self.recorded())
        fo.ledger_append(self.cfg["ledger"], {"event": "finish", "run": "run-A", "state_signed": signed})
        self.assertEqual(self.recorded(), self.state)

    def test_a_later_record_in_either_shape_wins(self):
        self.sign_baseline(legacy(self.state))
        newer = {**self.state, "release_head": "5" * 40}
        self.sign_baseline(newer)
        self.assertEqual(self.recorded(), newer)
        self.sign_baseline(legacy({**self.state, "release_head": "6" * 40}))
        self.assertEqual(self.recorded()["release_head"], "6" * 40)

    def test_a_record_that_doesnt_match_the_block_refuses_gates_and_names_the_difference(self):
        old = legacy(self.state)
        del old["fingerprints"]["cache"]
        old["fingerprints"]["retired"] = "7" * 64
        self.sign_baseline(old)
        problem = fo.state_problem(self.recorded(), self.env.cat)
        self.assertIn("added fp_cache", problem)
        self.assertIn("dropped fp_retired", problem)
        with self.assertRaises(fo.Refused) as cm:
            self.run_gate()
        self.assertIn("recorded outputs changed", str(cm.exception))
        issues, line = fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret,
                                      lambda c, t: self.services(), now_dt=self.clock.now())
        self.assertIn("recorded outputs changed", line)

    def test_a_value_outside_its_pattern_doesnt_match(self):
        bad = {**self.state, "recorded": {**self.state["recorded"], "fp_web": "not-hex"}}
        self.sign_baseline(bad)
        self.assertIn("don't match capture-state's patterns", fo.state_problem(self.recorded(), self.env.cat))

    def test_baseline_keeps_a_mismatched_records_release_head(self):
        later = self.merge({"README": "r2"})
        old = legacy({**self.state, "release_head": later})
        del old["fingerprints"]["cache"]  # the catalog changed since: it doesn't match, but it still counts
        self.sign_baseline(old)
        console = fakes.Console()
        self.assertEqual(fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "catalog changed", False,
                                         lambda c, t: self.services(), console), 0)
        self.assertEqual(self.recorded()["release_head"], later)  # not release_head_start: accepted hotfixes stay accepted
        self.assertIsNone(fo.state_problem(self.recorded(), self.env.cat))
        self.assertIn("fp_cache", console.lines[0])

    def test_drift_counts_a_legacy_baselines_time(self):
        self.sign_baseline(legacy(self.state), at="2026-11-05T12:30:00Z")
        self.w.add("cache", "SUCCESS", None, age=300)
        issues, line = fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret,
                                      lambda c, t: self.services(), now_dt=self.clock.now())
        self.assertEqual(issues, [], line)

    def test_unverified_records_are_listed_in_either_shape(self):
        self.sign_baseline(legacy(self.state))
        entries = self.entries()
        entries[0]["signed"]["receipt"]["deployed_state"]["seen"]["release_head"] = "9" * 40
        self.assertEqual(fo.unverified_records(entries, gates, self.env.public), [("baseline", "b")])
        self.assertIsNone(fo.recorded_state(entries, gates, self.env.public))

    def test_the_line_shapes_other_readers_use_are_unchanged(self):
        self.sign_baseline(self.state)
        self.run_gate()
        start, finish = [e for e in self.entries() if e["event"] in ("start", "finish")]
        base = {"repo", "pr", "issue", "gate", "kind", "attempt", "digest", "head", "run", "github_run"}
        self.assertEqual(set(start), base | {"event", "at", "approver"})
        self.assertEqual(set(finish), base | {"event", "at", "status", "outputs", "state_signed", "plan_blob", "gate_def", "signed"})
        self.assertEqual(fo.done_outputs(self.entries(), self.cfg["repo"], 7), {"G1": finish["outputs"]})
        self.assertEqual(fo.stored_receipt(self.entries(), "d" * 64), finish["signed"])
        json.dumps(self.entries())


if __name__ == "__main__":
    unittest.main()
