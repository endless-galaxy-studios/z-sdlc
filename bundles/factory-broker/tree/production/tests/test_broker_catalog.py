"""The project's own production catalog and settings, against the broker's rules (z-sdlc process/factory-broker.md):
production/ops.json and its broker block, production/config.json, and the host module's interface. The broker
refuses every gate while any of these is wrong; this test says so on the PR that breaks it, not on the host.

A seed is never rewritten by a migration, so when a release of the bundle tightens a rule, this test is how a
project learns its ops.json needs a change: it fails in CI with the broker's own message.

Skipped while the project has no production/ops.json: it has no production tier yet (the enable runbook writes it).
Run by CI: python -I -m unittest discover -s .github/factory/production/tests"""

import importlib.util
import json
import pathlib
import sys
import unittest

PRODUCTION = pathlib.Path(__file__).resolve().parents[1]
FACTORY = PRODUCTION.parent
sys.path.insert(0, str(FACTORY))
sys.path.insert(0, str(PRODUCTION))
import factory_op as fo  # noqa: E402
import gates  # noqa: E402

OPS = PRODUCTION / "ops.json"
EXAMPLE = PRODUCTION / "ops.example.json"


def catalog_of(path):
    return gates.load_catalog(path.read_text())


class TheExample(unittest.TestCase):
    """The seeded example a project starts from is one the broker accepts, while the enable runbook's release gates
    are still off."""

    def test_the_example_catalog_passes_the_broker_s_rules(self):
        if not EXAMPLE.exists():
            self.skipTest("no production/ops.example.json (the project removed the example)")
        cat = catalog_of(EXAMPLE)
        self.assertEqual(fo.broker_problems(cat), [])
        self.assertIs(cat["release_gates"], False)


@unittest.skipUnless(OPS.exists(), "no production/ops.json: the project has no production tier yet")
class TheProjectsCatalog(unittest.TestCase):
    def test_ops_json_passes_the_broker_s_rules(self):
        cat = catalog_of(OPS)
        problems = fo.broker_problems(cat, fo.lib_scripts(PRODUCTION))
        self.assertEqual(problems, [], "the broker refuses every gate until these are fixed:\n- " + "\n- ".join(problems))

    def test_config_json_passes_the_broker_s_rules(self):
        cfg = json.loads((PRODUCTION / "config.json").read_text())
        problems = fo.config_problems(cfg)
        self.assertEqual(problems, [], "the broker refuses every command until these are fixed:\n- " + "\n- ".join(problems))

    def test_the_host_module_has_the_broker_s_interface(self):
        path = PRODUCTION / fo.HOST_MODULE
        self.assertTrue(path.is_file(), f"production/{fo.HOST_MODULE} is missing: every step fails without it")
        sys.modules.setdefault("factory_op", fo)
        spec = importlib.util.spec_from_file_location("factory_op_host_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        problems = fo.host_interface_problems(module, catalog_of(OPS)["broker"])
        self.assertEqual(problems, [], "every step fails until these are fixed:\n- " + "\n- ".join(problems))


if __name__ == "__main__":
    unittest.main()
