"""The operations package a production broker is bound to (z-sdlc process/factory.md, D4 rules 6 and 11): the digest
covers a broker's own host module when there is one, by exact name, and then the config.json that broker reads from
beside it, the same in the repository and installed on the host; a broker without a host module hashes what it always
has; and a catalog whose broker runs no rollback steps makes the plan guard refuse a rollback, so CD is never told
one will run.
Run by CI: python -m unittest discover -s .github/factory/tests"""

import json
import pathlib
import sys
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
import gates  # noqa: E402

OPERATIONS = {
    "health": {"kind": "read", "summary": "Production's health", "timeout_s": 600,
               "outputs": {"healthy": "^(yes|no)$"}},
    "backup-now": {"kind": "change", "summary": "Back up the database", "timeout_s": 600,
                   "outputs": {"backup": "^[a-z0-9-]{1,64}$"}},
    "drop-backup": {"kind": "change", "summary": "Remove a backup", "timeout_s": 300, "rollback_only": True,
                    "params": {"backup": "^[a-z0-9-]{1,64}$"}},
}


def catalog(**fields):
    return gates.load_catalog(json.dumps({"version": 1, "operations": OPERATIONS, **fields}))


def layouts(root, host_module):
    """A repository's .github/factory and the lib dir setup would install from it, with or without a host module."""
    repo, lib = root / "repo", root / "lib"
    prod = repo / "production"
    (prod / "ops").mkdir(parents=True)
    (lib / "ops").mkdir(parents=True)
    files = {"gates.py": b"gates\n", "ed25519.py": b"ed\n", "factory_op.py": b"broker\n", "ops.json": b"{}\n",
             "ops/health.sh": b"#!/bin/sh\n", "config.json": b'{"repo": "octo-org/example"}\n'}
    if host_module:
        files["factory_op_host.py"] = b"host\n"
    for name, data in files.items():
        (repo / name if name in ("gates.py", "ed25519.py") else prod / name).write_bytes(data)
        (lib / name).write_bytes(data)
    return repo, lib


class Digest(unittest.TestCase):
    def test_the_repository_and_the_installed_copy_hash_the_same_with_and_without_a_host_module(self):
        for host_module in (False, True):
            with self.subTest(host_module=host_module), tempfile.TemporaryDirectory() as tmp:
                repo, lib = layouts(pathlib.Path(tmp), host_module)
                in_repo, installed = gates.repo_ops_files(repo), gates.installed_ops_files(lib)
                self.assertEqual(in_repo, installed)
                self.assertEqual("factory_op_host.py" in in_repo, host_module)
                self.assertEqual("config.json" in in_repo, host_module)
                self.assertEqual(gates.ops_digest(in_repo), gates.ops_digest(installed))

    def test_the_host_module_is_in_the_digest_and_one_sided_presence_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, lib = layouts(pathlib.Path(tmp), True)
            before = gates.ops_digest(gates.repo_ops_files(repo))
            (repo / "production" / "factory_op_host.py").write_bytes(b"edited\n")
            self.assertNotEqual(gates.ops_digest(gates.repo_ops_files(repo)), before)
            (repo / "production" / "factory_op_host.py").unlink()
            self.assertNotEqual(gates.ops_digest(gates.repo_ops_files(repo)), gates.ops_digest(gates.installed_ops_files(lib)))

    def test_a_bundle_brokers_config_is_in_the_digest(self):
        """What root checks (approvers, the App's id, the release branch) is in config.json: a change to it is a change to
        the package, in the repository and installed alike."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, lib = layouts(pathlib.Path(tmp), True)
            before = gates.ops_digest(gates.repo_ops_files(repo))
            (repo / "production" / "config.json").write_bytes(b'{"repo": "octo-org/example", "approvers": [9]}\n')
            self.assertNotEqual(gates.ops_digest(gates.repo_ops_files(repo)), before)
            (lib / "config.json").write_bytes(b'{"repo": "octo-org/example", "approvers": [9]}\n')
            self.assertEqual(gates.ops_digest(gates.installed_ops_files(lib)), gates.ops_digest(gates.repo_ops_files(repo)))
            (lib / "config.json").unlink()
            with self.assertRaises(OSError):  # a bundle broker's package without its config is no package
                gates.installed_ops_files(lib)

    def test_a_broker_without_a_host_module_hashes_exactly_what_it_did(self):
        """A project's own broker (no host module) keeps its digest: config.json, which it reads from /etc, isn't in it."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, lib = layouts(pathlib.Path(tmp), False)
            self.assertEqual(sorted(gates.repo_ops_files(repo)),
                             ["ed25519.py", "factory_op.py", "gates.py", "ops.json", "ops/health.sh"])
            before = gates.ops_digest(gates.installed_ops_files(lib))
            (lib / "config.json").write_bytes(b"changed\n")
            (repo / "production" / "config.json").write_bytes(b"changed\n")
            self.assertEqual(gates.ops_digest(gates.installed_ops_files(lib)), before)
            self.assertEqual(gates.ops_digest(gates.repo_ops_files(repo)), before)

    def test_only_named_modules_enter_the_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, lib = layouts(pathlib.Path(tmp), True)
            before = gates.ops_digest(gates.installed_ops_files(lib))
            (lib / "stray.py").write_bytes(b"x\n")
            (repo / "production" / "helper.py").write_bytes(b"x\n")
            self.assertEqual(gates.ops_digest(gates.installed_ops_files(lib)), before)
            self.assertNotIn("helper.py", gates.repo_ops_files(repo))
        self.assertEqual(gates.BROKER_MODULES, ("factory_op_host.py",))
        self.assertEqual(gates.BROKER_CONFIG, "config.json")


class Rollbacks(unittest.TestCase):
    BLOCK = {"steps": [{"id": "b", "op": "backup-now"}],
             "rollback": [{"op": "drop-backup", "with": {"backup": "${steps.b.backup}"}}]}

    def test_a_broker_that_runs_no_rollbacks_refuses_a_rollback_at_plan_time(self):
        errors = gates.check_block("G1", self.BLOCK, catalog(rollbacks=False), {})
        self.assertTrue(any("runs no rollback steps" in e for e in errors), errors)
        self.assertEqual(gates.check_block("G1", {"steps": self.BLOCK["steps"]}, catalog(rollbacks=False), {}), [])

    def test_rollbacks_default_to_allowed(self):
        self.assertEqual(gates.check_block("G1", self.BLOCK, catalog(), {}), [])
        self.assertTrue(gates.takes_rollbacks(catalog()))
        self.assertFalse(gates.takes_rollbacks(catalog(rollbacks=False)))

    def test_rollbacks_must_be_a_boolean(self):
        for value in ("false", 0, None):
            with self.subTest(value=value), self.assertRaises(gates.Invalid):
                catalog(rollbacks=value)


if __name__ == "__main__":
    unittest.main()
