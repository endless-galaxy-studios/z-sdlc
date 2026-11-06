"""What gates.py accepts as a value matches the whole value (z-sdlc process/factory.md, D4): `$` also matches just
before a trailing newline, so a check with `.match` passes "<sha>\n", and the newline goes on to whatever reads the
value next. And a step that ran past its catalog timeout has a status of its own, timed-out, rather than failed.
Each fixture is one `.match` accepts and `.fullmatch` doesn't, so it tells the fixed check from the old one.
Run by CI: python -m unittest discover -s .github/factory/tests"""

import json
import pathlib
import re
import sys
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
import gates  # noqa: E402

CATALOG = gates.load_catalog(json.dumps({"version": 1, "operations": {
    "health": {"kind": "read", "summary": "Production's health", "timeout_s": 60, "outputs": {"status": "^(ok|down)$"}},
    "deploy": {"kind": "change", "summary": "Deploy a commit", "timeout_s": 600, "params": {"sha": "^[0-9a-f]{40}$"},
               "outputs": {"previous_sha": "^[0-9a-f]{40}$"}},
}}))
HEAD, PLAN_PATH = "a" * 40, "docs/current_work/planning/d99_thing_plan.md"


def plan(with_sha="${head}"):
    block = {"steps": [{"id": "deploy", "op": "deploy", "with": {"sha": with_sha}}],
             "rollback": [{"op": "deploy", "with": {"sha": "${steps.deploy.previous_sha}"}}]}
    return f"""# D99: Thing

### Phase 1: Code

Write it.

### Gate G1: Deploy it

**After:** Phase 1. **Changes production:** yes.

```gate-ops
{json.dumps(block)}
```

### Phase 2: Records

Write the result.
"""


def request(**changes):
    args = dict(repo="o/r", issue=7, pr=8, plan=PLAN_PATH, plan_blob="b" * 40, plan_text=plan(), gate_id="G1",
                attempt=1, head=HEAD, catalog=CATALOG, gate_outputs={}, ops_digest="c" * 64)
    return gates.build_request(**{**args, **changes})


class WholeValues(unittest.TestCase):
    def old_check_passes(self, pattern, value):
        """The fixture is one the old `.match` accepted: otherwise this test couldn't tell the two apart."""
        self.assertTrue(re.match(pattern, value), (pattern, value))
        self.assertFalse(re.fullmatch(pattern, value), (pattern, value))

    def test_a_request_s_shas_digest_and_plan_path(self):
        request()  # the fixture itself is accepted
        for field, value in (("head", HEAD + "\n"), ("plan_blob", "b" * 40 + "\n"), ("ops_digest", "c" * 64 + "\n"),
                             ("plan", PLAN_PATH + "\n")):
            with self.subTest(field=field):
                pattern = {"head": gates.SHA, "plan_blob": gates.SHA, "ops_digest": gates.DIGEST,
                           "plan": gates.PLAN_PATH}[field].pattern
                self.old_check_passes(pattern, value)
                with self.assertRaises(gates.Invalid):
                    request(**{field: value})

    def test_a_plan_s_parameter_matches_its_catalog_pattern_whole(self):
        self.assertEqual(gates.check_plan(plan(HEAD), CATALOG), [])
        self.old_check_passes(CATALOG["operations"]["deploy"]["params"]["sha"], HEAD + "\n")
        errors = gates.check_plan(plan(HEAD + "\n"), CATALOG)
        self.assertTrue(any("doesn't match" in e for e in errors), errors)

    def test_a_receipt_s_outputs_match_the_catalog_whole(self):
        req = request()
        receipt = {"digest": req["digest"], "status": "done", "pr": 8, "gate": "G1",
                   "steps": [{"id": "deploy", "op": "deploy", "outputs": {"previous_sha": "e" * 40}}]}
        gates.check_receipt(receipt, req, CATALOG)
        self.old_check_passes(CATALOG["operations"]["deploy"]["outputs"]["previous_sha"], "e" * 40 + "\n")
        receipt["steps"][0]["outputs"]["previous_sha"] = "e" * 40 + "\n"
        with self.assertRaisesRegex(gates.Invalid, "isn't an allowed output"):
            gates.check_receipt(receipt, req, CATALOG)

    def test_a_run_title_a_pin_and_a_release_branch(self):
        title = gates.run_title(request())
        self.assertEqual(gates.parse_title(title)["gate"], "G1")
        self.old_check_passes(gates.TITLE.pattern, title + "\n")
        with self.assertRaises(gates.Invalid):
            gates.parse_title(title + "\n")
        self.old_check_passes(gates.GATE_ID.pattern, "G3\n")
        with self.assertRaises(gates.Invalid):
            gates.pin_branch(8, "G3\n", HEAD)
        self.old_check_passes(gates.BRANCH.pattern, "release/production\n")
        with self.assertRaisesRegex(gates.Invalid, "not a release branch"):
            gates.release_binding({}, repo="o/r", app_id=1, branch="release/production\n", pr=8, gate_id="G3",
                                  head=HEAD)

    def test_no_value_check_is_left_on_match(self):
        # Plan lines come from splitlines (no newline left to match) and keep their prefix patterns; a marker is
        # matched from \A up to its own newline. Every other check matches the whole value.
        text = (FACTORY / "gates.py").read_text()
        line_patterns = {"FENCE_CLOSE", "FENCE_OPEN", "GATE_HEAD", "ITEM_HEAD", "SECTION_END", "GATE_RELEASE",
                         "RELEASE_HEAD", "RELEASE_WHY", "MARKER"}
        left = {name for name in re.findall(r"\b([A-Z_]+)\.match\(", text)} - line_patterns
        self.assertEqual(left, set())
        self.assertNotIn("re.match(", text)


class TimedOut(unittest.TestCase):
    def test_a_timed_out_receipt_is_its_own_status(self):
        req = request()
        receipt = {"digest": req["digest"], "status": "timed-out", "pr": 8, "gate": "G1",
                   "steps": [{"id": "deploy", "op": "deploy", "status": "timed-out"}]}
        gates.check_receipt(receipt, req, CATALOG)
        text = gates.render_result({"receipt": receipt}, req, "https://example.com/run")
        self.assertIn("### Gate G1 (attempt 1): **timed out**", text)
        self.assertIn("what it changed is unknown. Inspect production first", text)
        self.assertNotIn("Execution continues", text)
        state = {"requests": [{"request": req}], "results": {req["digest"]: receipt}}
        self.assertEqual(gates.gate_status(state, "G1")[0], "timed-out")
        self.assertIn("| timed out |", gates.render_tracker({"plan": PLAN_PATH, "stopped_at": "G1"}, plan(), state))
        self.assertEqual(gates.gate_outputs(state), {})  # not done: nothing for later gates to use

    def test_an_unknown_status_is_still_refused(self):
        req = request()
        with self.assertRaisesRegex(gates.Invalid, "doesn't answer this request"):
            gates.check_receipt({"digest": req["digest"], "status": "timedout", "pr": 8, "gate": "G1"}, req, CATALOG)


if __name__ == "__main__":
    unittest.main()
