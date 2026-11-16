"""The labels GitHub gives every self-hosted runner (self-hosted, its OS, its architecture), which the factory treats as
GitHub's own: setup refuses a tier with no label beyond them, the CI launcher refuses one too, the workflow policy never
takes one for a hosted label, and the runner audit leaves them out of its comparison. Each of those runs where no shared
file reaches it (the launcher installed alone on the runner host, the audit written whole into a workflow, setup staged
from root's own clone), so each keeps its own copy, and this test holds the copies to one set."""
import ast
import pathlib
import re
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]


def python_set(path, name):
    """A module-level set literal, as written in the file."""
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{path.name} has no {name}")


def setup_set():
    """setup.sh's refusal of a tier without a label of its own: its inline Python's defaults."""
    m = re.search(r"^defaults = (\{[^}\n]*\})$", (FACTORY / "host" / "setup.sh").read_text(), re.M)
    assert m, "setup.sh has no defaults = {...} in its label check"
    return ast.literal_eval(m.group(1))


class RunnerLabels(unittest.TestCase):
    def test_every_copy_names_the_same_labels(self):
        launcher = python_set(FACTORY / "host" / "ci_launcher.py", "SELF_HOSTED_DEFAULTS")
        self.assertEqual(launcher, {"self-hosted", "linux", "windows", "macos", "x64", "x86", "arm", "arm64"})
        self.assertEqual(python_set(FACTORY / "runner_audit.py", "DEFAULT_LABELS_OF_RUNNERS"), launcher)
        self.assertEqual(python_set(FACTORY / "workflow_policy.py", "SELF_HOSTED_DEFAULTS"), launcher)
        self.assertEqual(setup_set(), launcher)

    def test_the_labels_are_lowercase(self):
        # Every copy compares a label's lower case with them.
        labels = python_set(FACTORY / "host" / "ci_launcher.py", "SELF_HOSTED_DEFAULTS")
        self.assertEqual({label.lower() for label in labels}, labels)


if __name__ == "__main__":
    unittest.main()
