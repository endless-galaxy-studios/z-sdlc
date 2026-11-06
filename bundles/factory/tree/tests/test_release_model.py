"""The release model (z-sdlc process/factory.md, D4 rule 13). Production deploys from a release branch by default
(the seed's release.branch is release/production). A factory.json with no release block, written before the release
branch existed, is on the fallback, execution-PR gates, and every reader of the setting agrees: migrating, which
never rewrites a seed, changes nothing for it. A release-branch project without a production tier releases through
a Release section, and its plans can have no gates, release gates included (D4 rule 16).
Run by CI: python -m unittest discover -s .github/factory/tests"""

import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
import implement_guard as guard  # noqa: E402
import render  # noqa: E402

RELEASE_GATE_PLAN = """# D99: Thing

### Phase 1: Code

Write it.

### Gate G1: The API reaches production

**After:** Phase 1. **Changes production:** yes.
**Release:** the web app needs the new endpoint before Phase 2 builds on it

### Phase 2: Records

Write the result.
"""
RELEASE_SECTION_PLAN = """# D99: Thing

### Phase 1: Code

Write it.

### Release

**Why:** the web app needs the new endpoint
"""


def settings(release):
    """This project's factory.json with the release block replaced: None for none at all."""
    values = copy.deepcopy(render.settings(FACTORY))
    values.pop("release", None)
    if release is not None:
        values["release"] = release
    return values


class ReleaseSetting(unittest.TestCase):
    def read(self, values):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "factory.json"
            path.write_text(json.dumps(values))
            with mock.patch.object(guard, "FOCUS_SETTINGS", path):
                return guard.read_release_branch()

    def test_no_release_block_is_the_fallback(self):
        self.assertEqual(self.read(settings(None)), "")
        self.assertEqual(self.read(settings({"branch": ""})), "")
        self.assertEqual(self.read(settings({"branch": "release/production"})), "release/production")

    def test_the_workflows_render_the_fallback_without_a_release_block(self):
        advance = (FACTORY / "templates" / "factory-advance.yml").read_text()
        request = (FACTORY / "templates" / "factory-gate-request.yml").read_text()
        release_pr = (FACTORY / "templates" / "factory-release-pr.yml").read_text()
        for values, branch in ((settings(None), ""), (settings({"branch": ""}), ""),
                               (settings({"branch": "release/production"}), "release/production")):
            with self.subTest(branch=branch, block="release" in values):
                out = render.render(advance, values)
                # The release jobs' conditions: false on the fallback, so no release PR and no release gate run.
                self.assertIn(f"'{branch}' != ''", out)
                self.assertEqual("'release/production'" in out, bool(branch))
                self.assertIn(f'RELEASE_BRANCH: "{branch}"', render.render(request, values))
                self.assertIn(f'RELEASE: "{branch}"', render.render(release_pr, values))

    def test_the_fallback_refuses_a_release(self):
        with self.assertRaisesRegex(guard.Refused, "doesn't follow a release branch"):
            guard.release_line(RELEASE_SECTION_PLAN, self.read(settings(None)))
        catalog = json.dumps({"version": 1, "operations": {
            "health": {"kind": "read", "summary": "Production's health", "timeout_s": 60,
                       "outputs": {"status": "^(ok|down)$"}}}})
        with self.assertRaisesRegex(guard.Refused, "G1 is a release gate, but this project's production doesn't follow"):
            guard.plan_gate_lines(RELEASE_GATE_PLAN, catalog, self.read(settings(None)))


class WithoutAProductionTier(unittest.TestCase):
    def test_a_release_section_still_releases(self):
        self.assertEqual(guard.release_line(RELEASE_SECTION_PLAN, "release/production"),
                         ("release/production", "the web app needs the new endpoint"))

    def test_no_gate_at_all_release_gates_included(self):
        # No catalog: no production tier, so no broker to check a release gate's deploy either.
        with self.assertRaisesRegex(guard.Refused, "has no production tier"):
            guard.plan_gate_lines(RELEASE_GATE_PLAN, None, "release/production")


if __name__ == "__main__":
    unittest.main()
