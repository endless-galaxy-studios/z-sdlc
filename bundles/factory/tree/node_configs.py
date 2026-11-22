"""The config file each Node tool in a profile's verify loads by name (process/factory.md, Stack Profiles).

Usage:
  python3 -I node_configs.py record <node dir>
  python3 -I node_configs.py check <node dir> <verify.conf> <tool>...     tools: eslint, vite, vitest
  python3 -I node_configs.py load <node dir> <verify.conf>

Each tool finds its config by name, in its own order, and the first name there wins: an added vite.config.js
replaces a project's vite.config.ts, and an added vitest.config.ts replaces the test settings a project keeps in
vite.config.ts. agent_job.sh workspace runs `record` in the checkout before the agent starts and appends its lines
to verify.conf: <tool>_config=, the file each tool loads, relative to the node directory (empty when it loads
none), and vitest_workspace=, the workspace or projects file beside Vitest's config. The checkout holds only what
was published, and the publish guard refuses an agent's change to a code-owned path, which these names are
(factory.md, Stack Profiles), so a name can't be planted there by an earlier run. A profile's verify passes the
recorded files to the tools (--config) and runs `check` first, which fails, naming the file, when a tool would now
load another: a file added since replaces the project's wherever nothing pins it, CI included.

The search orders, as measured in the pilot project's installed tools (2026-11):
- ESLint 9.39: eslint.config.{js,mjs,cjs,ts,mts,cts}, from the working directory up. Given --config, it reads the
  config's paths relative to the working directory rather than the config's own, so verify pins it only when the
  file is in the node directory itself.
- Vite 6.4: vite.config.{js,mjs,ts,cjs,mts,cts}, in the root only.
- Vitest 3.2: vitest.config.*, then vite.config.*, each .ts, .mts, .cts, .js, .mjs, .cjs, from the root up; then
  vitest.workspace.* or vitest.projects.* (those six, and .json) beside the config it loaded, which choose the tests
  it runs unless the config sets test.projects. The command line can't pin that file, so it is checked only.
The upward searches stop at the working directory, the checkout's root: what's above it isn't the run's to change.

`load`, in a profile's `verify probe` (which factory-smoke runs as sandboxed agent Bash), loads each recorded Vite and
Vitest config with the project's own Vite (loadConfigFromFile, which bundles it with esbuild, as both tools do), so a
config that can't load in the sandbox fails smoke rather than a stage. Claude Code's env scrub, on in every agent job,
write-protects package.json in the working directory and, when there's none, leaves an empty one, which esbuild,
reading each package.json up the tree, fails on (process/factory.md, D2 rule 2).
"""

import os
import pathlib
import subprocess
import sys

ESLINT = tuple(f"eslint.config.{e}" for e in ("js", "mjs", "cjs", "ts", "mts", "cts"))
VITE = tuple(f"vite.config.{e}" for e in ("js", "mjs", "ts", "cjs", "mts", "cts"))
_VITEST_EXT = ("ts", "mts", "cts", "js", "mjs", "cjs")
VITEST = tuple(f"{n}.{e}" for n in ("vitest.config", "vite.config") for e in _VITEST_EXT)
VITEST_WORKSPACE = tuple(f"{n}.{e}" for n in ("vitest.workspace", "vitest.projects") for e in _VITEST_EXT + ("json",))
TOOLS = {"eslint": ("eslint_config", ESLINT, True), "vite": ("vite_config", VITE, False),
         "vitest": ("vitest_config", VITEST, True)}
KEYS = ("eslint_config", "vite_config", "vitest_config", "vitest_workspace")


class Invalid(Exception):
    pass


def node_dir(value):
    """The node directory as a relative path below the working directory."""
    p = pathlib.PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts:
        raise Invalid(f"the node directory must be below the checkout's root: got {value!r}")
    return pathlib.Path(p)


def first(directory, names):
    """The first of names that is a file in directory, or None."""
    for name in names:
        if (directory / name).is_file():
            return directory / name
    return None


def find(root, names, upward):
    """The file a tool loads, relative to root (the node directory), or "": names in root, then each parent up to
    the working directory when the tool searches upward."""
    directories = [root]
    if upward:
        directories += [d for d in root.parents if d != pathlib.Path("/")]
    for directory in directories:
        found = first(directory, names)
        if found:
            return os.path.relpath(found, root)
    return ""


def resolve(root):
    """{key: file} for every tool, as verify.conf records it."""
    found = {key: find(root, names, upward) for key, names, upward in TOOLS.values()}
    beside = (root / found["vitest_config"]).parent if found["vitest_config"] else root
    workspace = first(beside, VITEST_WORKSPACE)
    found["vitest_workspace"] = os.path.relpath(workspace, root) if workspace else ""
    return found


def recorded(conf_text):
    """verify.conf's recorded files; a missing key raises Invalid (agent_job.sh workspace writes every one)."""
    lines = dict(line.split("=", 1) for line in conf_text.splitlines() if "=" in line)
    missing = [k for k in KEYS if k not in lines]
    if missing:
        raise Invalid(f"verify.conf has no {', '.join(k + '=' for k in missing)} line: agent_job.sh workspace records "
                      "them before the agent starts")
    return {k: lines[k] for k in KEYS}


def check(root, before, tools):
    """The problems, one line each: a tool that would now load a file other than the one recorded."""
    now = resolve(root)
    problems = []
    for tool in tools:
        key = TOOLS[tool][0]
        if now[key] != before[key]:
            was = f"not {before[key]}, the file it loaded" if before[key] else "and loaded none"
            problems.append(f"{tool} would load {now[key] or 'no config file'} in {root}, {was} when the job began")
    if "vitest" in tools:
        # Beside the recorded config, where the pinned run looks.
        beside = (root / before["vitest_config"]).parent if before["vitest_config"] else root
        workspace = first(beside, VITEST_WORKSPACE)
        workspace = os.path.relpath(workspace, root) if workspace else ""
        if workspace != before["vitest_workspace"]:
            problems.append(f"vitest would read {workspace or 'no workspace file'} in {root} to choose its tests, "
                            f"{'not ' + before['vitest_workspace'] if before['vitest_workspace'] else 'and read none'}"
                            " when the job began")
    return problems


# Run in the node directory by node: loadConfigFromFile resolves the file from there, as the tools do.
LOAD = r"""
const file = process.argv[1];
try {
  const { loadConfigFromFile } = await import("vite");
  const loaded = await loadConfigFromFile({ command: "build", mode: "production" }, file, process.cwd(), "silent");
  if (!loaded) throw new Error(`Vite found no config at ${file}`);
} catch (e) {
  console.error(String((e && e.message) || e).split("\n").filter(Boolean).slice(0, 4).join(" | "));
  process.exit(1);
}
"""


def load(root, before):
    """The problems, one line each: a recorded Vite or Vitest config that Vite can't load from the node directory."""
    problems = []
    for name in sorted({before[k] for k in ("vite_config", "vitest_config") if before[k]}):
        try:
            r = subprocess.run(["node", "--input-type=module", "-e", LOAD, name], cwd=root, capture_output=True,
                               text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            problems.append(f"couldn't load {name} in {root}: {e}")
            continue
        if r.returncode != 0:
            # The script's own line is the last: esbuild writes its diagnostics to stderr first.
            why = ((r.stderr or r.stdout).strip().splitlines() or ["no output"])[-1][:1000]
            if "package.json" in why and "Unexpected end of file" in why:
                why += (" (an empty package.json above it is the placeholder Claude Code's env scrub leaves where there's "
                        "none: give the repository a code-owned root package.json, such as {\"private\": true}; "
                        "process/factory.md, D2 rule 2)")
            problems.append(f"Vite couldn't load {name} in {root}: {why}")
    return problems


def main(argv):
    try:
        if len(argv) == 2 and argv[0] == "record":
            for key, value in resolve(node_dir(argv[1])).items():
                print(f"{key}={value}")
            return 0
        if len(argv) >= 4 and argv[0] == "check" and set(argv[3:]) <= set(TOOLS):
            root = node_dir(argv[1])
            problems = check(root, recorded(pathlib.Path(argv[2]).read_text()), argv[3:])
            for p in problems:
                print(f"verify: {p}: a config file added since replaces the project's wherever nothing pins it, CI "
                      "included. Remove it, or leave the change to CD.")
            return 1 if problems else 0
        if len(argv) == 3 and argv[0] == "load":
            root = node_dir(argv[1])
            before = recorded(pathlib.Path(argv[2]).read_text())
            problems = load(root, before)
            for p in problems:
                print(f"verify: {p}")
            loaded = [before[k] for k in ("vite_config", "vitest_config") if before[k]]
            if not problems:
                print(f"configs-ok {' '.join(sorted(set(loaded))) or '(no Vite or Vitest config)'}")
            return 1 if problems else 0
    except (Invalid, OSError) as e:
        print(f"verify: {e}", file=sys.stderr)
        return 2
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
