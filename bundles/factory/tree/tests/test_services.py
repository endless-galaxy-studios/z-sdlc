"""Tests for services.py: validation, every slot masked in every run, wiring only for listed stages,
nothing secret in the agent's context, and MCP servers by slot."""

import json
import pathlib
import sys
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))

import services as svc  # noqa: E402

ENV = {"name": "sentry", "stages": ["plan", "spec"], "slot": "FACTORY_SVC_1", "attach": "env", "read_only": True,
       "domains": ["sentry.io", "*.sentry.io"], "auth": "Authorization: Bearer $FACTORY_SVC_1"}
MCP = {"name": "linear", "stages": ["plan"], "slot": "FACTORY_SVC_2", "attach": "mcp", "read_only": True,
       "url": "https://mcp.linear.app/mcp", "header": "Authorization", "prefix": "Bearer "}
EXEC = {"name": "memory", "stages": ["implement", "execute", "revise"], "slot": "FACTORY_EXEC_SVC_1", "attach": "mcp",
        "read_only": True, "url": "https://memory.example/mcp", "header": "Authorization", "prefix": "Bearer ",
        "tools": ["memory_search", "memory_get"]}
BASE = {"sandbox": {"network": {"allowedDomains": ["localhost"]}, "credentials": {"envVars": []}}}


def load(services):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"services": services}, f)
    return svc.load(f.name)


class Validation(unittest.TestCase):
    def test_accepts(self):
        self.assertEqual(len(load([ENV])), 1)
        self.assertEqual(load([]), [])
        self.assertEqual(len(load([ENV, MCP, EXEC])), 3)
        self.assertEqual(len(load([dict(MCP, tools=["list_issues"])])), 1)

    def test_read_only_required(self):
        for bad in [[{k: v for k, v in ENV.items() if k != "read_only"}], [dict(ENV, read_only=False)],
                    [dict(MCP, read_only=False)], [dict(EXEC, read_only=False)]]:
            with self.assertRaises(svc.Invalid, msg=bad):
                load(bad)

    def test_mcp_credentials_go_only_in_authorization(self):
        # fetch drops Authorization on a cross-origin redirect and keeps any other header.
        for header in ("X-Api-Key", "authorization", None):
            with self.assertRaisesRegex(svc.Invalid, "Authorization", msg=header):
                load([dict(MCP, header=header)])
        with self.assertRaises(svc.Invalid):
            load([dict(MCP, url="http://mcp.linear.app/mcp")])

    def test_one_tier_per_entry(self):
        for bad in [[dict(MCP, stages=["plan", "implement"])], [dict(EXEC, stages=["revise", "spec"])]]:
            with self.assertRaisesRegex(svc.Invalid, "never both", msg=bad):
                load(bad)

    def test_execution_entries(self):
        with self.assertRaisesRegex(svc.Invalid, "must be attach mcp"):
            load([dict(ENV, stages=["implement"], slot="FACTORY_EXEC_SVC_1")])
        with self.assertRaisesRegex(svc.Invalid, "required for an execution stage"):
            load([{k: v for k, v in EXEC.items() if k != "tools"}])
        # Each tier has its own slots: a planning secret never reaches a strict-tier job.
        with self.assertRaisesRegex(svc.Invalid, "slot must be one of"):
            load([dict(EXEC, slot="FACTORY_SVC_1")])
        with self.assertRaisesRegex(svc.Invalid, "slot must be one of"):
            load([dict(MCP, slot="FACTORY_EXEC_SVC_1")])

    def test_tools_lists(self):
        for tools in ([], ["ok", "ok"], ["bad tool"], ["../x"], [1], "memory_search"):
            with self.assertRaises(svc.Invalid, msg=tools):
                load([dict(EXEC, tools=tools)])

    def test_refuses(self):
        for bad in [[dict(ENV, domains=["*"])], [dict(ENV, domains=["*.com"])], [dict(ENV, domains=[])],
                    [dict(ENV, stages=["implement"])], [dict(ENV, stages=[])], [dict(ENV, slot="FACTORY_SVC_9")],
                    [ENV, dict(ENV, name="other")], [ENV, dict(ENV, slot="FACTORY_SVC_3")],
                    [dict(ENV, name="Bad Name")], [dict(ENV, attach="file")],
                    [dict(ENV, extra=1)], [dict(ENV, domains=["e.com/path"])]]:
            with self.assertRaises(svc.Invalid, msg=bad):
                load(bad)


class Settings(unittest.TestCase):
    def masks(self, out):
        return {v["name"]: v for v in out["sandbox"]["credentials"]["envVars"]}

    def test_every_slot_masked_even_with_no_services(self):
        out = svc.settings(BASE, [], "plan")
        masks = self.masks(out)
        self.assertEqual(set(masks), set(svc.SLOTS + svc.EXEC_SLOTS))
        self.assertTrue(all(m["mode"] == "mask" and m["injectHosts"] == [] for m in masks.values()))
        self.assertEqual(out["sandbox"]["network"]["allowedDomains"], ["localhost"])
        self.assertNotIn("tlsTerminate", out["sandbox"]["network"])

    def test_env_service_wired_for_its_stages_only(self):
        services = load([ENV, MCP])
        out = svc.settings(BASE, services, "plan")
        self.assertEqual(self.masks(out)["FACTORY_SVC_1"]["injectHosts"], ["sentry.io", "*.sentry.io"])
        self.assertEqual(self.masks(out)["FACTORY_SVC_2"]["injectHosts"], [])  # mcp: never in the sandbox
        self.assertEqual(out["sandbox"]["network"]["allowedDomains"], ["localhost", "sentry.io", "*.sentry.io"])
        self.assertEqual(out["sandbox"]["network"]["tlsTerminate"], {})
        other = svc.settings(BASE, services, "implement")
        self.assertTrue(all(m["injectHosts"] == [] for m in self.masks(other).values()))
        self.assertEqual(other["sandbox"]["network"]["allowedDomains"], ["localhost"])
        self.assertNotIn("permissions", other)

    def test_mcp_tools_allowed_for_their_stages_only(self):
        services = load([ENV, MCP, EXEC])
        self.assertEqual(svc.settings(BASE, services, "plan")["permissions"]["allow"], ["mcp__linear"])
        self.assertEqual(svc.settings(BASE, services, "execute")["permissions"]["allow"],
                         ["mcp__memory__memory_search", "mcp__memory__memory_get"])
        self.assertNotIn("permissions", svc.settings(BASE, services, "spec"))
        # An execution slot is masked with nothing injected, like every mcp slot.
        masks = self.masks(svc.settings(BASE, services, "implement"))
        self.assertEqual(masks["FACTORY_EXEC_SVC_1"]["injectHosts"], [])
        base = {"permissions": {"allow": ["mcp__context7", "mcp__memory__memory_get"]}}
        self.assertEqual(svc.settings(base, services, "revise")["permissions"]["allow"],
                         ["mcp__context7", "mcp__memory__memory_get", "mcp__memory__memory_search"])

    def test_base_is_not_mutated_and_slots_not_duplicated(self):
        base = {"sandbox": {"credentials": {"envVars": [{"name": "FACTORY_SVC_1", "mode": "mask", "injectHosts": ["x.io"]},
                                                        {"name": "OTHER", "mode": "mask", "injectHosts": []}]}}}
        snapshot = json.dumps(base)
        out = svc.settings(base, [], "plan")
        self.assertEqual(json.dumps(base), snapshot)
        names = [v["name"] for v in out["sandbox"]["credentials"]["envVars"]]
        self.assertEqual(sorted(names), sorted(svc.SLOTS + svc.EXEC_SLOTS + ["OTHER"]))


class ContextAndMcp(unittest.TestCase):
    def test_context_has_no_values(self):
        ctx = svc.context(load([ENV, MCP, EXEC]), "plan")
        self.assertEqual([e["name"] for e in ctx["services"]], ["sentry", "linear"])
        self.assertEqual(ctx["services"][0]["variable"], "FACTORY_SVC_1")
        self.assertEqual(svc.context(load([ENV]), "implement"), {"services": []})
        exec_ctx = svc.context(load([EXEC]), "revise")["services"][0]
        self.assertEqual((exec_ctx["mcp_server"], exec_ctx["tools"]), ("memory", ["memory_search", "memory_get"]))
        self.assertNotIn("variable", exec_ctx)

    def test_mcp_server_by_slot(self):
        self.assertEqual(svc.mcp_servers(load([EXEC]), "implement")["memory"]["headers"],
                         {"Authorization": "Bearer ${FACTORY_EXEC_SVC_1}"})
        servers = svc.mcp_servers(load([ENV, MCP]), "plan")
        self.assertEqual(servers, {"linear": {"type": "http", "url": "https://mcp.linear.app/mcp",
                                              "headers": {"Authorization": "Bearer ${FACTORY_SVC_2}"}}})
        self.assertEqual(svc.mcp_servers([MCP], "spec"), {})


if __name__ == "__main__":
    unittest.main()
