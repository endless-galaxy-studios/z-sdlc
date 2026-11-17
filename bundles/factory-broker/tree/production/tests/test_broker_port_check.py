"""`check`'s rules about the install (z-sdlc process/factory.md D4 rule 16, process/factory-broker.md), the part the other
broker tests don't hold: root ownership and modes, exact for secrets and sockets and widest-allowed for the rest; the
sockets' groups; the receipt key; every path a tier owns, for the first tier and a later one; the clone as setup creates
it; and Sandbox.install_secret agreeing with check. Carried over from the third project's broker tests (test_review.py:
CheckAdditions; test_round2.py: CheckV2; test_round4.py: CloneMode)."""

import re
import stat
import types
import unittest

import fakes
from fakes import Env
import factory_op as fo
from test_broker_sandbox import SandboxHelper

SETUP = (fakes.FACTORY / "host" / "setup-production.sh").read_text()
TIERS = ("factory-prod", "factory-prod-two")


def fake_stat(uid=0, gid=0, mode=0o600, directory=False):
    return types.SimpleNamespace(st_uid=uid, st_gid=gid, st_mode=(stat.S_IFDIR if directory else stat.S_IFREG) | mode)


def missing(path):
    raise FileNotFoundError(path)


def tier_cfg(tier):
    names = fo.tier_names(tier)
    return {"operator_user": names["operator_user"], "clone_dir": names["clone_base"] + "/app.git"}, names


class OwnerProblemsTest(unittest.TestCase):
    def test_root_owned_with_no_bit_beyond_the_mode(self):
        self.assertEqual(fo.owner_problems([("/etc/x/key", 0o600)], stat_fn=lambda p: fake_stat()), [])
        self.assertTrue(fo.owner_problems([("/etc/x/key", 0o600)], stat_fn=lambda p: fake_stat(mode=0o640)))
        self.assertTrue(fo.owner_problems([("/etc/x/key", 0o600)], stat_fn=lambda p: fake_stat(uid=1000)))
        self.assertTrue(fo.owner_problems([("/etc/x/key", 0o600)], stat_fn=lambda p: fake_stat(gid=1000)))
        self.assertEqual(fo.owner_problems([("/etc/x/key", 0o600)], stat_fn=missing), ["no /etc/x/key"])
        self.assertEqual(fo.owner_problems([("/etc/dir", 0o755)], stat_fn=lambda p: fake_stat(mode=0o755, directory=True)), [])
        self.assertTrue(fo.owner_problems([("/etc/dir", 0o755)], stat_fn=lambda p: fake_stat(mode=0o775, directory=True)))

    def test_exact_modes_for_secrets_and_widest_modes_for_the_rest(self):
        exact = [("/etc/x/key", 0o600, None, True)]
        self.assertEqual(fo.owner_problems(exact, stat_fn=lambda p: fake_stat()), [])
        self.assertTrue(fo.owner_problems(exact, stat_fn=lambda p: fake_stat(mode=0o400)))  # install_secret refuses 0400 too
        self.assertTrue(fo.owner_problems(exact, stat_fn=lambda p: fake_stat(mode=0o640)))
        wide = [("/x/dir", 0o755, None, False)]
        self.assertEqual(fo.owner_problems(wide, stat_fn=lambda p: fake_stat(mode=0o700, directory=True)), [])
        self.assertTrue(fo.owner_problems(wide, stat_fn=lambda p: fake_stat(mode=0o757, directory=True)))

    def test_group_owned_sockets(self):
        item = [("/run/x/op.sock", 0o660, "grp", True)]

        def gid_of(name):
            return {"grp": 4321}[name]
        self.assertEqual(fo.owner_problems(item, stat_fn=lambda p: fake_stat(gid=4321, mode=0o660), gid_of=gid_of), [])
        self.assertTrue(fo.owner_problems(item, stat_fn=lambda p: fake_stat(gid=0, mode=0o660), gid_of=gid_of))
        self.assertTrue(fo.owner_problems(item, stat_fn=lambda p: fake_stat(gid=4321, mode=0o600), gid_of=gid_of))
        self.assertEqual(fo.owner_problems([("/run/x/op.sock", 0o660, "nogroup", True)], stat_fn=lambda p: fake_stat(),
                                           gid_of=gid_of), ["no group nogroup for /run/x/op.sock"])


class CheckedPathsTest(unittest.TestCase):
    def test_every_path_a_tier_owns_is_checked_with_its_rule(self):
        block = fakes.catalog()["broker"]
        for tier in TIERS:
            with self.subTest(tier):
                cfg, names = tier_cfg(tier)
                items = {str(i[0]): tuple(i[1:]) for i in fo.checked_modes(cfg, block, names)}
                for path in (names["etc_dir"], names["config"], names["known_hosts"], names["state_dir"], names["log_dir"],
                             names["run_dir"], names["steps_dir"], names["clone_base"], cfg["clone_dir"], names["socket"],
                             names["egress_socket"], names["sudoers"], names["command_path"], "/usr/local/bin/factory-op-request"):
                    self.assertIn(path, items)
                self.assertEqual(items[names["sudoers"]], (0o440, None, True))
                self.assertEqual(items[names["socket"]], (0o660, names["runner_user"], True))
                self.assertEqual(items[names["egress_socket"]], (0o660, names["operator_user"], True))
                secrets = [names["key"], names["deploy_key"], *(f"{names['etc_dir']}/{s['file']}" for s in block["secrets"].values())]
                for secret in secrets:
                    self.assertEqual(items[secret], (0o600, None, True), secret)
                self.assertEqual(items[cfg["clone_dir"]], (0o750, names["operator_user"], True))
                self.assertEqual(items[names["clone_base"]], (0o755, None, False))

    def test_a_later_tiers_paths_are_its_own(self):
        block = fakes.catalog()["broker"]

        def paths(tier):
            cfg, names = tier_cfg(tier)
            return {str(i[0]) for i in fo.checked_modes(cfg, block, names)}
        first, later = paths("factory-prod"), paths("factory-prod-two")
        self.assertEqual(first & later, {"/usr/local/bin/factory-op-request"})  # the request client is one per host


class GroupProblemsTest(unittest.TestCase):
    def groups(self, extra=(), missing_group=None):
        def getgrnam(name):
            if name == missing_group:
                raise KeyError(name)
            return types.SimpleNamespace(gr_mem=[name, *extra])
        return getgrnam

    def test_each_sockets_group_holds_only_its_own_account(self):
        for tier in TIERS:
            with self.subTest(tier):
                names = fo.tier_names(tier)
                self.assertEqual(fo.group_problems(names, getgrnam=self.groups()), [])
                self.assertEqual(fo.group_problems(names, getgrnam=lambda name: types.SimpleNamespace(gr_mem=[])), [])
                bad = fo.group_problems(names, getgrnam=self.groups(extra=("someone",)))
                self.assertEqual(len(bad), 2, bad)
                self.assertTrue(all("someone" in p for p in bad), bad)
                self.assertEqual(fo.group_problems(names, getgrnam=self.groups(missing_group=names["operator_user"])),
                                 [f"no group {names['operator_user']}"])


class KeyProblemsTest(unittest.TestCase):
    def test_a_missing_unreadable_or_mismatched_receipt_key_is_a_problem_not_a_crash(self):
        env = Env()
        self.addCleanup(env.close)
        key = env.tmp / "receipt.key"
        self.assertEqual(fo.key_problems(env.cfg, key=key), [f"no usable receipt.key at {key}"])
        key.write_text("not hex\n")
        self.assertEqual(fo.key_problems(env.cfg, key=key), [f"no usable receipt.key at {key}"])
        key.write_text(bytes(range(40, 72)).hex() + "\n")
        self.assertEqual(fo.key_problems(env.cfg, key=key), ["receipt.pub doesn't match the signing key"])
        key.write_text(env.secret.hex() + "\n")
        self.assertEqual(fo.key_problems(env.cfg, key=key), [])
        (env.lib / "receipt.pub").unlink()
        self.assertEqual(fo.key_problems(env.cfg, key=key), ["receipt.pub doesn't match the signing key"])


class InstallSecretAgreesWithCheckTest(SandboxHelper):
    def test_a_secret_check_would_refuse_is_never_installed(self):
        for mode in (0o400, 0o640, 0o644, 0o660):
            with self.subTest(mode=oct(mode)):
                (self.etc / "host.token").chmod(mode)
                res = self.run_op(self.sandbox())
                self.assertEqual(res.status, "failed")
                self.assertIn("mode 0600", res.why)
                self.assertTrue(fo.owner_problems([(self.etc / "host.token", 0o600, None, True)],
                                                  stat_fn=lambda p: fake_stat(mode=mode)))
        self.assertEqual(self.argvs, [])
        (self.etc / "host.token").chmod(0o600)
        self.assertEqual(self.run_op(self.sandbox(lambda d: (d / "out").write_text(
            "healthy=yes\nservices=4\nunhealthy=\nweb_deployment=dep-0001\njobs_deployment=dep-0002\n"))).status, "done")


class CloneModeTest(unittest.TestCase):
    def test_check_expects_the_clone_as_setup_creates_it(self):
        self.assertRegex(SETUP, r'chown -R "root:\$OP_USER" "\$CLONE"')
        self.assertRegex(SETUP, r'chmod 750 "\$CLONE"')
        self.assertRegex(SETUP, r'chmod 755 "\$CLONE_BASE"')
        # setup derives the names from the tier as the broker does
        self.assertRegex(SETUP, r"\bOP_USER=\$TIER_NAME-op\b")
        self.assertRegex(SETUP, r"\bCLONE_BASE=/var/lib/\$TIER_NAME-clone\b")
        self.assertRegex(SETUP, re.escape("CLONE=$CLONE_BASE/${REPO#*/}.git"))
        for tier in TIERS:
            with self.subTest(tier):
                cfg, names = tier_cfg(tier)
                self.assertEqual((names["operator_user"], names["clone_base"]), (f"{tier}-op", f"/var/lib/{tier}-clone"))
                items = {str(i[0]): tuple(i[1:]) for i in fo.checked_modes(cfg, fakes.catalog()["broker"], names)}
                self.assertEqual(items[cfg["clone_dir"]], (0o750, names["operator_user"], True))
                self.assertEqual(items[names["clone_base"]], (0o755, None, False))

    def test_a_correct_install_reports_no_problem_for_the_clone_and_its_parent(self):
        cfg, names = tier_cfg("factory-prod-two")

        def st(path):
            if str(path) == cfg["clone_dir"]:
                return fake_stat(gid=4242, mode=0o750, directory=True)
            return fake_stat(mode=0o755, directory=True)
        items = [i for i in fo.checked_modes(cfg, fakes.catalog()["broker"], names) if "clone" in str(i[0])]
        self.assertEqual(len(items), 2)
        self.assertEqual(fo.owner_problems(items, stat_fn=st, gid_of=lambda g: {names["operator_user"]: 4242}[g]), [])
        self.assertTrue(fo.owner_problems(items, stat_fn=lambda p: fake_stat(gid=4242, mode=0o755, directory=True),
                                          gid_of=lambda g: 4242))  # a world-readable clone is refused


if __name__ == "__main__":
    unittest.main()
