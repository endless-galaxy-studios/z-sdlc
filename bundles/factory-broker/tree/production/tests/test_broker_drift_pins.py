"""The daily drift check during a mid-plan release gate (z-sdlc process/factory.md D4 rule 13). A release gate's release PR
merges its pinned commit, on the execution PR's branch and not in main until CD merges that PR, into the release branch.
That is the state rule 13 allows, so the check accepts a first-parent merge whose second parent is a pinned commit when the
broker's ledger holds a verified release-gate finish for that merge commit (the gate checked it against GitHub) and its
subject names factory/release/<pr>-G<n>-<first 12 of it> in this repository, and doesn't count the code that commit brought
as code main lacks. A subject alone proves nothing (a branch can be named after its commit), and a pin still not in main
14 days after its gate is named as such and no longer counts. Anything else stays an alarm."""

import datetime
import unittest

import fakes
import factory_op as fo
import gates
from test_broker_gate import GateBase

RECENT, OLD = "2026-11-05T11:30:00Z", "2026-10-20T12:00:00Z"  # an hour before the drift check, and 16 days


class PinnedReleaseDriftTest(GateBase):
    def setUp(self):
        super().setUp()
        self.append_baseline(self.state)

    def drift(self):
        svc = fo.Services(self.gh(), self.repo.git, lambda run: self.env.sandbox)
        return fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret, lambda c, t: svc, now_dt=self.clock.now())

    def record_gate(self, merge, at=RECENT, secret=None, kind="release"):
        """The finish line execute() writes for a release gate whose release PR's merge commit is `merge`."""
        base = {"repo": self.cfg["repo"], "pr": 7, "issue": 3, "gate": "G1", "kind": kind, "attempt": 1, "digest": "d" * 64,
                "head": "a" * 40, "run": f"run-{merge[:8]}", "github_run": 55}
        receipt = {**base, "v": 1, "status": "done", "steps": [], "rollback": [], "at": at, "release_head": merge,
                   "release_gate": {"release_pr": 41, "merge": merge, "wait": {}}}
        fo.ledger_append(self.cfg["ledger"], {**base, "event": "finish", "at": at, "status": "done", "outputs": {},
                                              "state_signed": None, "plan_blob": "b" * 40, "gate_def": "def",
                                              "signed": gates.sign_receipt(secret or self.env.secret, receipt)})

    def execution_commit(self, files, branch="factory/3-impl"):
        """The execution PR's branch, from main, with one commit: the gate's pinned commit."""
        self.repo.sh("checkout", "-q", "-B", branch, "main")
        self.repo.write(files)
        self.repo.sh("add", "-A")
        self.repo.sh("commit", "-q", "-m", "execution work up to G1")
        return self.repo.sh("rev-parse", "HEAD")

    def release_merge(self, pin, owner="example", sha12=None, extra=None, branch="factory/3-impl"):
        """The release PR's merge into the release branch, with GitHub's subject for it. `extra` changes files in the merge
        commit itself."""
        name = gates.pin_branch(7, "G1", pin) if sha12 is None else f"factory/release/7-G1-{sha12}"
        self.repo.sh("checkout", "-q", "release/production")
        message = f"Merge pull request #41 from {owner}/{name}"
        if extra:
            self.repo.sh("merge", "-q", "--no-ff", "--no-commit", branch)
            self.repo.write(extra)
            self.repo.sh("add", "-A")
            self.repo.sh("commit", "-q", "-m", message)
        else:
            self.repo.sh("merge", "-q", "--no-ff", "-m", message, branch)
        return self.repo.head()

    def test_a_release_gates_pinned_merge_raises_no_alarm(self):
        pin = self.execution_commit({"docs/plan-result.md": "done up to G1"})
        self.record_gate(self.release_merge(pin))
        self.assertEqual(self.drift(), ([], "drift: ok"))

    def test_a_look_alike_merge_the_broker_never_checked_is_an_alarm(self):
        """A branch named after its own commit, merged by CD: no release gate of this broker's checked it."""
        pin = self.execution_commit({"docs/plan-result.md": "looks like a release gate's"})
        merge = self.release_merge(pin)
        line = self.drift()[1]
        self.assertIn(f"release {merge[:12]} merged a branch that is not in main", line)
        self.assertIn("production carries code main lacks", line)

    def test_a_record_that_doesnt_verify_or_isnt_a_release_gates_doesnt_count(self):
        pin = self.execution_commit({"docs/plan-result.md": "x"})
        merge = self.release_merge(pin)
        self.record_gate(merge, secret=bytes(range(60, 92)))  # signed by another key
        self.record_gate(merge, kind="ops")
        self.record_gate("f" * 40)  # another merge's
        self.assertIn(f"release {merge[:12]} merged a branch that is not in main", self.drift()[1])

    def test_a_pin_still_not_in_main_after_the_bound_is_named_and_no_longer_counts(self):
        pin = self.execution_commit({"docs/plan-result.md": "abandoned"})
        merge = self.release_merge(pin)
        self.record_gate(merge, at=OLD)
        issues, line = self.drift()
        self.assertIn(f"release gate's pinned commit {pin[:12]} (merged as {merge[:12]} on 2026-10-20) is still not in main "
                      f"after 14 days", line)
        self.assertIn("production carries code main lacks", line)
        self.assertEqual(fo.PIN_BOUND_S, 14 * 24 * 3600)

    def test_it_stays_explained_after_a_later_record_and_a_later_release(self):
        pin = self.execution_commit({"docs/plan-result.md": "done up to G1"})
        merge = self.release_merge(pin)
        self.record_gate(merge)
        state = self.copy(self.state)
        state["release_head"] = merge  # the gate's own record, after it checked the release
        self.append_baseline(state, at="2026-11-05T11:30:00Z")
        self.merge({"README": "r2"})  # an ordinary release from main after it
        self.assertEqual(self.drift(), ([], "drift: ok"))

    def test_once_main_has_it_nothing_changes(self):
        pin = self.execution_commit({"docs/plan-result.md": "done up to G1"})
        self.release_merge(pin)  # with no record at all, and older than the bound: main has it, so nothing is asked
        self.repo.sh("checkout", "-q", "main")
        self.repo.sh("merge", "-q", "--no-ff", "-m", "Merge pull request #7 from example/factory/3-impl", "factory/3-impl")
        self.repo.sh("checkout", "-q", "release/production")
        self.assertEqual(self.drift(), ([], "drift: ok"))

    def test_a_name_that_isnt_the_commits_or_this_repositorys_is_an_alarm(self):
        for n, kwargs in enumerate(({"sha12": "0" * 12}, {"owner": "someone-else"})):
            with self.subTest(**kwargs):
                pin = self.execution_commit({f"docs/result-{n}.md": "work"}, branch=f"factory/{n + 3}-impl")
                merge = self.release_merge(pin, branch=f"factory/{n + 3}-impl", **kwargs)
                self.record_gate(merge)  # even a recorded gate's merge must carry its own pin name
                line = self.drift()[1]
                self.assertIn(f"release {merge[:12]} merged a branch that is not in main", line)
                self.assertIn("production carries code main lacks", line)

    def test_a_branch_that_isnt_a_pin_is_an_alarm(self):
        self.execution_commit({"docs/plan-result.md": "x"})
        self.repo.sh("checkout", "-q", "release/production")
        self.repo.sh("merge", "-q", "--no-ff", "-m", "Merge pull request #41 from example/factory/3-impl", "factory/3-impl")
        line = self.drift()[1]
        self.assertIn("merged a branch that is not in main", line)
        self.assertIn("main lacks", line)

    def test_code_the_pin_didnt_bring_is_still_code_main_lacks(self):
        pin = self.execution_commit({"docs/plan-result.md": "done up to G1"})
        self.record_gate(self.release_merge(pin, extra={"docs/smuggled.md": "not in the pinned commit"}))
        line = self.drift()[1]
        self.assertNotIn("merged a branch that is not in main", line)
        self.assertIn("production carries code main lacks (1 files, e.g. docs/smuggled.md)", line)

    def test_a_pinned_path_the_branch_changed_since_is_still_code_main_lacks(self):
        pin = self.execution_commit({"docs/plan-result.md": "done up to G1"})
        self.record_gate(self.release_merge(pin))
        self.repo.sh("checkout", "-q", "-b", "hotfix", "release/production")
        self.repo.write({"docs/plan-result.md": "changed on the release branch alone"})
        self.repo.sh("add", "-A")
        self.repo.sh("commit", "-q", "-m", "hotfix")
        self.repo.sh("checkout", "-q", "release/production")
        self.repo.sh("merge", "-q", "--no-ff", "-m", "Merge pull request #42 from example/hotfix", "hotfix")
        line = self.drift()[1]
        self.assertIn("docs/plan-result.md", line)
        self.assertIn("main lacks", line)

    def test_the_pin_name_is_the_brokers_and_gates(self):
        pin = "ab" * 20
        self.assertTrue(fo.PIN_MERGE.fullmatch(f"Merge pull request #41 from example/{gates.pin_branch(7, 'G1', pin)}"))
        self.assertFalse(fo.PIN_MERGE.fullmatch(f"Merge pull request #41 from example/{gates.pin_branch(7, 'G1', pin)} extra"))


if __name__ == "__main__":
    unittest.main()
