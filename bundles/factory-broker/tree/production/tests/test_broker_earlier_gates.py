"""Every gate before the requested one must be done on this host as the plan defines it now (z-sdlc process/factory.md
D4 rule 7): its title and block, and its kind. A gate the plan has since made a release gate (or stopped making one)
runs again, rather than count a result that lacks (or had) the release's own checks."""

import json
import unittest

import fakes  # noqa: F401  (puts the broker and gates.py on the path, as every test here)
import factory_op as fo
import gates

BLOCK = {"steps": [{"id": "h", "op": "health"}]}


def plan(g1_release=False, g1_block=True):
    g1 = ("**Release:** the next phase needs the code live\n" if g1_release else "") + \
         (f"\n```gate-ops\n{json.dumps(BLOCK)}\n```\n" if g1_block else "")
    return f"""# D9: Thing

### Phase 1: Code

Write it.

### Gate G1: Production

**After:** Phase 1. **Changes production:** yes.
{g1}
### Phase 2: More

Write more.

### Gate G2: Check

**After:** Phase 2. **Changes production:** no.

### Phase 3: Records

Write the result.
"""


def done_as(text, kind, gate_id="G1"):
    g = next(g for g in gates.parse_gates(text) if g["id"] == gate_id)
    return {gate_id: {"gate_def": fo.gate_def(gates, g), "kind": kind}}


class EarlierGatesTest(unittest.TestCase):
    def test_an_earlier_gate_done_as_the_plan_defines_it_counts(self):
        for text, kind in ((plan(), "ops"), (plan(g1_release=True), "release"), (plan(g1_block=False), "cd")):
            with self.subTest(kind=kind):
                self.assertTrue(fo.earlier_gates(gates, text, "G2", done_as(text, kind)))

    def test_a_gate_since_made_a_release_gate_must_run_again(self):
        before, now = plan(), plan(g1_release=True)
        done = done_as(before, "ops")
        self.assertEqual(done["G1"]["gate_def"], done_as(now, "ops")["G1"]["gate_def"], "the title and block are the same")
        with self.assertRaises(fo.Refused) as cm:
            fo.earlier_gates(gates, now, "G2", done)
        self.assertIn("ran as a ops gate, and the plan now makes it a release gate", str(cm.exception))

    def test_a_release_gate_the_plan_no_longer_marks_must_run_again(self):
        with self.assertRaises(fo.Refused) as cm:
            fo.earlier_gates(gates, plan(), "G2", done_as(plan(g1_release=True), "release"))
        self.assertIn("ran as a release gate, and the plan now makes it a ops gate", str(cm.exception))

    def test_a_record_without_a_kind_doesnt_count(self):
        done = done_as(plan(), "ops")
        del done["G1"]["kind"]
        with self.assertRaises(fo.Refused):
            fo.earlier_gates(gates, plan(), "G2", done)

    def test_the_kind_is_the_one_gates_builds_requests_with(self):
        for text, kind in ((plan(), "ops"), (plan(g1_release=True), "release"), (plan(g1_block=False), "cd")):
            with self.subTest(kind=kind):
                self.assertEqual(fo.gate_kind(gates.parse_gates(text)[0]), kind)


if __name__ == "__main__":
    unittest.main()
