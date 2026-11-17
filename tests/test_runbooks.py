"""Runbooks (process/runbooks.md): every **Runbook:** marker line is well formed, its id is unique, it names a
record, and its doc ships, as a source process doc or a bundle's, so sdlc-run-runbook and sdlc-status find it in a
project. An `enable` runbook is a bundle's and a `setup` one the core's, since that's what decides who offers it. A
bundle's `## After migrating` section is followed by sdlc-migrate, so its heading must be exact."""
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = re.compile(r"^\*\*Runbook:\*\* `([a-z0-9]+(?:-[a-z0-9]+)*)` · \*\*When:\*\* (enable|setup|on-demand) · "
                    r"\*\*Record:\*\* `([^`]+)` § (\S.*)$")


# A marker starts this way; a bare `**Runbook:**` label is a gate's checklist (production-gates.md), not a runbook.
START = re.compile(r"^\*\*Runbook:\*\* `")


def markers():
    """(doc, line number, line) for every marker outside a code fence in a process doc."""
    found = []
    for path in sorted((ROOT / "process").glob("*.md")):
        fenced = False
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if line.startswith("```"):
                fenced = not fenced
            elif not fenced and START.match(line):
                found.append((path.relative_to(ROOT).as_posix(), n, line))
    return found


def shipped():
    manifest = json.loads((ROOT / "skeleton/manifest.json").read_text())
    docs = set(manifest["source_files"]["process"])
    for bundle in manifest["bundles"].values():
        if isinstance(bundle, dict):
            docs |= set(bundle.get("process", []))
    return docs


class Runbooks(unittest.TestCase):
    def test_every_marker_is_well_formed_and_unique(self):
        found = markers()
        self.assertTrue(found, "no runbooks found")
        ids = []
        for doc, n, line in found:
            with self.subTest(doc=doc, line=n):
                m = MARKER.match(line)
                self.assertIsNotNone(m, f"{doc}:{n}: {line}")
                ids.append(m.group(1))
        self.assertEqual(len(ids), len(set(ids)), f"duplicate runbook ids: {sorted(ids)}")

    def test_every_runbook_ships_to_projects(self):
        docs = shipped()
        for doc, n, _ in markers():
            self.assertIn(doc, docs, f"{doc} has a runbook but isn't in the manifest's process docs")

    def test_the_known_runbooks(self):
        ids = {MARKER.match(line).group(1): (doc, MARKER.match(line).group(2)) for doc, _, line in markers()}
        self.assertEqual(ids.get("factory-enablement"), ("process/factory-runbook.md", "enable"))
        self.assertEqual(ids.get("github-provenance-enablement"), ("process/github-checkpoints.md", "enable"))
        self.assertEqual(ids.get("external-review-gate"), ("process/external-review-gate.md", "setup"))
        self.assertEqual(ids.get("verify-command"), ("process/verify-command.md", "setup"))

    def test_enable_is_a_bundles_and_setup_the_cores(self):
        manifest = json.loads((ROOT / "skeleton/manifest.json").read_text())
        core = set(manifest["source_files"]["process"])
        for doc, n, line in markers():
            kind = MARKER.match(line).group(2)
            with self.subTest(doc=doc, line=n):
                if kind == "enable":
                    self.assertNotIn(doc, core, f"{doc}: an enable runbook is offered with its bundle; this doc isn't one")
                elif kind == "setup":
                    self.assertIn(doc, core, f"{doc}: a setup runbook is offered to every project; this doc is a bundle's")

    def test_after_migrating_sections_are_exact_and_in_bundle_docs(self):
        manifest = json.loads((ROOT / "skeleton/manifest.json").read_text())
        bundle_docs = {d for b in manifest["bundles"].values() if isinstance(b, dict) for d in b.get("process", [])}
        for path in sorted((ROOT / "process").glob("*.md")):
            text = path.read_text()
            near = re.findall(r"(?im)^#+\s*after\s+migrat.*$", text)
            for heading in near:
                with self.subTest(doc=path.name, heading=heading):
                    self.assertEqual(heading, "## After migrating")
                    self.assertIn(path.relative_to(ROOT).as_posix(), bundle_docs | {"process/runbooks.md"})
        self.assertIn("\n## After migrating\n", (ROOT / "process/factory.md").read_text())


if __name__ == "__main__":
    unittest.main()
