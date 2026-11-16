"""The labels GitHub gives every self-hosted runner: process/factory.md (Enablement step 8, Runner labels) names
exactly the set the factory's code treats as GitHub's own. The bundle's tests/test_runner_labels.py holds the code's
copies to one another; this holds the docs to them."""
import ast
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def launcher_labels():
    tree = ast.parse((ROOT / "bundles/factory/tree/host/ci_launcher.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "SELF_HOSTED_DEFAULTS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("ci_launcher.py has no SELF_HOSTED_DEFAULTS")


def documented_labels():
    text = (ROOT / "process/factory.md").read_text()
    m = re.search(r"\*\*Runner labels\.\*\* GitHub gives every self-hosted runner its own default labels \(([^)]*)\)",
                  text)
    assert m, "process/factory.md has no Runner labels paragraph naming the labels"
    return set(re.findall(r"`([^`]+)`", m.group(1)))


class RunnerLabels(unittest.TestCase):
    def test_the_docs_name_the_labels_the_code_treats_as_githubs(self):
        self.assertTrue(launcher_labels())
        self.assertEqual(documented_labels(), launcher_labels())


if __name__ == "__main__":
    unittest.main()
