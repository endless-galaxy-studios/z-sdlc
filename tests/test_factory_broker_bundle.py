"""The factory-broker bundle as z-sdlc ships it (process/factory-broker.md). Its own tests run inside a project,
where the seeds are the project's to fill in, so they can't tell a shipped seed that presets a project's choice from
a project that made it. These check the shipped files: the seeds choose nothing for the project and pass the
broker's own rules, the stub host module fails every step closed, and the bundle is still a pilot (no
bundle_debut entry) that requires the factory bundle."""

import importlib.util
import json
import pathlib
import re
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundles" / "factory-broker"
SEED = BUNDLE / "seed"
sys.path.insert(0, str(ROOT / "bundles" / "factory" / "tree"))
sys.path.insert(0, str(BUNDLE / "tree" / "production"))
import factory_op as fo  # noqa: E402
import gates  # noqa: E402


def conf_settings(text):
    """production.conf's KEY=value lines (comments and blanks aside), as setup reads them."""
    out = {}
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip().strip('"')
    return out


class Seeds(unittest.TestCase):
    def test_production_conf_presets_nothing_a_project_must_choose(self):
        settings = conf_settings((SEED / "host" / "production.conf").read_text())
        self.assertEqual(settings, {"PROD_INSTANCE": ""}, "the seed may set only the first tier's empty instance")

    def test_the_example_catalog_passes_the_broker_s_rules_with_release_gates_off(self):
        cat = gates.load_catalog((SEED / "production" / "ops.example.json").read_text())
        self.assertEqual(fo.broker_problems(cat), [])
        self.assertIs(cat["release_gates"], False)
        self.assertIs(cat["rollbacks"], False)

    def test_the_catalog_is_seeded_as_an_example_only_so_the_install_is_inert(self):
        # A project has a production tier once production/ops.json exists (D4 rule 16): installing the bundle must not
        # create one before the enable runbook does.
        self.assertFalse((SEED / "production" / "ops.json").exists())
        self.assertFalse((BUNDLE / "tree" / "production" / "ops.json").exists())

    def test_the_config_seed_is_the_first_tier_s(self):
        cfg = json.loads((SEED / "production" / "config.json").read_text())
        self.assertEqual(fo.config_problems(cfg, fo.tier_names("factory-prod")), [])

    def test_the_stub_host_module_fails_every_primitive_closed(self):
        sys.modules.setdefault("factory_op", fo)
        spec = importlib.util.spec_from_file_location("stub_host", SEED / "production" / "factory_op_host.py")
        stub = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stub)
        cat = gates.load_catalog((SEED / "production" / "ops.example.json").read_text())
        self.assertEqual(fo.host_interface_problems(stub, cat["broker"]), [])
        ctx = types.SimpleNamespace()
        calls = {"client": (ctx,), "preflight": (ctx,), "latest": (ctx,), "deployments": (ctx, "web"),
                 "serving": (ctx, "web"), "reports": (ctx, "web", "d"), "heartbeat": (ctx, "web", "d", True),
                 "capture": (ctx,)}
        self.assertEqual(set(calls), set(fo.PRIMITIVES))
        for name, args in calls.items():
            with self.subTest(primitive=name), self.assertRaises(fo.StepFailed):
                getattr(stub, name)(*args)


class Shape(unittest.TestCase):
    def test_the_bundle_holds_only_its_tree_and_seeds(self):
        self.assertEqual(sorted(p.name for p in BUNDLE.iterdir()), ["seed", "tree"])

    def test_it_is_a_pilot_that_requires_the_factory_bundle_and_has_no_debut_yet(self):
        manifest = json.loads((ROOT / "skeleton" / "manifest.json").read_text())
        entry = manifest["bundles"]["factory-broker"]
        self.assertEqual(entry["requires"]["bundles"], ["factory"])
        self.assertEqual(entry["process"], ["process/factory-broker.md"])
        changes = (ROOT / "skeleton" / "contract_changes.yaml").read_text()
        debuted = re.search(r"type: bundle_debut\s*\n\s*bundle:\s*\n\s*name: factory-broker\b", changes)
        self.assertEqual(entry.get("pilot") is True, debuted is None,
                         "a pilot bundle has no bundle_debut entry, and a debuted one is no longer a pilot")


if __name__ == "__main__":
    unittest.main()
