"""Render the factory's workflows from templates/ and this repository's settings (rollout step 2).

Usage: python3 render.py [--check | --adopt-pins] [<factory-dir> <templates-dir> <workflows-dir>]
       (defaults: this directory, its templates/, and ../workflows)

Every .github/workflows/factory-*.yml is rendered from templates/<same name>, under a header line that
says so: edit the template (or factory.json), then run this. --check renders in memory and fails on any workflow that differs, any
factory workflow without a template and any template without a workflow; CI runs it before
workflow_policy.py, which checks the rendered files (D2 rule 6).

--adopt-pins copies action pins from the workflows back into the templates, for a Dependabot actions
update: Dependabot edits only .github/workflows/, so its bump fails --check until the templates have it.
It takes a line only where the workflow and the rendered template differ by a `uses:` line's commit and
its version comment, the action's path and the line's indentation unchanged, both pins full 40-character
commits, and every pin of that action in the templates ends at one commit. Anything else is refused
and nothing is written. After it, --check passes. Run factory-smoke once the update merges (D2 rule 5).

A placeholder is %{key}, a dotted path into factory.json, or into planning.json under `planning.`
(the planning tier's database). %{key+N} adds N to a number; a list renders as `a, b`. %{key?} is an
optional setting: it renders empty when factory.json doesn't have it (a project installed before the
setting existed keeps rendering; the fixtures block). Plain text substitution, so a template is the
workflow byte for byte outside its placeholders. Refused: an unknown key, a %{ left unresolved, and a
factory.json setting no template uses (keys starting with _ are notes; the stack block is read at run
time, by agent_job.sh, the policy block by workflow_policy.py, the review block by implement_guard.py, and the ci
block, runners.ci and runners.groups by host/setup.sh and bootstrap.py).
"""

import json
import pathlib
import re
import sys

HEADER = ("# Rendered from .github/factory/templates/{name} and factory.json by render.py:"
          " edit those and re-render, not this file.\n")
PLACEHOLDER = re.compile(r"%\{([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*)(?:\+(\d+)|(\?))?\}")
# A step's action pinned to a commit: indentation and `- `, the action's path, the commit, a version comment.
PIN = re.compile(r"(?P<lead>[ ]*(?:- )?uses: )(?P<action>[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9_./-]+)"
                 r"@(?P<ref>[0-9a-f]{40})(?P<comment>[ ]+#[^\n]*)?(?P<end>\n?)")
# The agent action installs its own Claude Code; factory-smoke checks the run used the version it names.
AGENT_ACTION = "anthropics/claude-code-action"


class Invalid(Exception):
    pass


def settings(factory_dir):
    """factory.json, with planning.json's settings under `planning`."""
    factory_dir = pathlib.Path(factory_dir)
    values = json.loads((factory_dir / "factory.json").read_text())
    planning = factory_dir / "planning.json"
    if planning.exists():
        values["planning"] = json.loads(planning.read_text())
    return values


def leaves(values, prefix=""):
    """Every setting's dotted key (lists are values, not branches); notes (_ keys) skipped."""
    for key, value in values.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            yield from leaves(value, f"{prefix}{key}.")
        else:
            yield f"{prefix}{key}"


def lookup(values, key, optional=False):
    value = values
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            if optional:
                return ""
            raise Invalid(f"unknown setting %{{{key}}}")
        value = value[part]
    if isinstance(value, dict):
        raise Invalid(f"%{{{key}}} names a group of settings, not one")
    return value


def text(value, key):
    if isinstance(value, bool) or value is None:
        raise Invalid(f"%{{{key}}} is {json.dumps(value)}, which doesn't render")
    if isinstance(value, list):
        return ", ".join(text(v, key) for v in value)
    return str(value)


def render(template, values, used=None):
    def substitute(match):
        key, add, optional = match.group(1), match.group(2), match.group(3)
        value = lookup(values, key, optional=bool(optional))
        if used is not None:
            used.add(key)
        if add is not None:
            if not isinstance(value, int) or isinstance(value, bool):
                raise Invalid(f"%{{{key}+{add}}} adds to a setting that isn't a whole number")
            value += int(add)
        return text(value, key)

    out = PLACEHOLDER.sub(substitute, template)
    if "%{" in out:
        line = out[:out.index("%{")].count("\n") + 1
        raise Invalid(f"line {line}: a %{{ that isn't a placeholder")
    return out


def render_all(factory_dir, templates_dir):
    """{workflow name: rendered text}, checking that every factory.json setting is used."""
    values = settings(factory_dir)
    used = set()
    out = {}
    for template in sorted(pathlib.Path(templates_dir).glob("factory-*.yml")):
        try:
            out[template.name] = HEADER.format(name=template.name) + render(template.read_text(), values, used)
        except Invalid as e:
            raise Invalid(f"{template}: {e}")
    # planning.json and the stack block are read at run time too (planning-services.sh, agent_job.sh), the policy
    # block by workflow_policy.py, the review block by implement_guard.py, and the CI tier's label and the runner
    # groups by host/setup.sh and bootstrap.py, so a setting there no template names isn't dead.
    run_time = ("planning.", "stack.", "policy.", "review.", "ci.", "runners.groups.")
    unused = sorted(k for k in leaves(values) if not k.startswith(run_time) and k != "runners.ci" and k not in used)
    if unused:
        raise Invalid(f"factory.json settings no template uses: {', '.join(unused)}")
    return out


def adopt_pins(factory_dir, templates_dir, workflows_dir):
    """{template name: new text} taking the workflows' changed action pins, and what changed; Invalid when a
    workflow differs from its rendered template by anything else, or when an action would end at two commits."""
    values = settings(factory_dir)
    rendered = render_all(factory_dir, templates_dir)
    on_disk = {p.name for p in pathlib.Path(workflows_dir).glob("factory-*.yml")}
    if on_disk != set(rendered):
        raise Invalid("the workflows and the templates aren't the same set: "
                      + ", ".join(sorted(on_disk ^ set(rendered))))
    texts = {name: (pathlib.Path(templates_dir) / name).read_text() for name in rendered}
    new, changes = {}, []
    for name, expected in rendered.items():
        actual = (pathlib.Path(workflows_dir) / name).read_text()
        if actual == expected:
            continue
        want, have = expected.splitlines(keepends=True), actual.splitlines(keepends=True)
        lines = texts[name].splitlines(keepends=True)
        if len(want) != len(have):
            raise Invalid(f"{name}: lines added or removed, not only pins changed")
        if len(want) != len(lines) + 1:
            raise Invalid(f"{name}: its template doesn't line up with the workflow (a setting renders on several lines)")
        for i, (w, h) in enumerate(zip(want, have)):
            if w == h:
                continue
            was, now = PIN.fullmatch(w), PIN.fullmatch(h)
            if not was or not now or (was["lead"], was["action"], was["end"]) != (now["lead"], now["action"], now["end"]):
                raise Invalid(f"{name}: line {i}: not only an action's commit changed: {h.strip()[:120]}")
            if lines[i - 1] != w:
                raise Invalid(f"{name}: line {i}: the template's line has a setting in it")
            lines[i - 1] = h
            changes.append((name, i, now["action"], (was["comment"] or "").strip("# ") or was["ref"][:12],
                            (now["comment"] or "").strip("# ") or now["ref"][:12]))
        new[name] = "".join(lines)
        if HEADER.format(name=name) + render(new[name], values) != actual:
            raise Invalid(f"{name}: the template still doesn't render to the workflow")
    adopted = {action for _, _, action, _, _ in changes}
    refs = {}
    for name in rendered:
        for m in PIN.finditer(new.get(name, texts[name])):
            if m["action"] in adopted:
                refs.setdefault(m["action"], set()).add(m["ref"])
    split = sorted(action for action, found in refs.items() if len(found) > 1)
    if split:
        raise Invalid(f"the templates would pin {', '.join(split)} at more than one commit: update every workflow that uses it")
    return new, changes


def main(argv):
    flags = [a for a in argv if a.startswith("--")]
    args = [a for a in argv if not a.startswith("--")]
    if set(flags) - {"--check", "--adopt-pins"} or len(flags) > 1 or len(args) not in (0, 3):
        print("::error::usage: render.py [--check | --adopt-pins] [<factory-dir> <templates-dir> <workflows-dir>]")
        return 2
    check = "--check" in flags
    here = pathlib.Path(__file__).resolve().parent
    factory_dir, templates_dir, workflows_dir = (
        [pathlib.Path(a) for a in args] if args else [here, here / "templates", here.parent / "workflows"])
    if "--adopt-pins" in flags:
        try:
            new, changes = adopt_pins(factory_dir, templates_dir, workflows_dir)
        except (Invalid, OSError, ValueError) as e:
            print(f"::error::render --adopt-pins: {e}; nothing written")
            return 1
        for name, text in new.items():
            (templates_dir / name).write_text(text)
        for name, line, action, was, now in changes:
            print(f"{templates_dir / name}:{line}: {action} {was} -> {now}")
        print(f"render: {len(changes)} pins adopted into {len(new)} templates")
        if changes:
            print("Run factory-smoke once this merges (D2 rule 5).")
        if any(action == AGENT_ACTION for _, _, action, _, _ in changes):
            print(f"{AGENT_ACTION} changed: set CLAUDE_CODE_VERSION in templates/factory-smoke.yml to the Claude Code "
                  "version the action installs at its new commit (base-action/action.yml), then run render.py.")
        return 0
    try:
        rendered = render_all(factory_dir, templates_dir)
    except (Invalid, OSError, ValueError) as e:
        print(f"::error::render: {e}")
        return 1
    problems = []
    existing = {p.name for p in workflows_dir.glob("factory-*.yml")}
    for name, body in rendered.items():
        path = workflows_dir / name
        if check:
            if not path.exists():
                problems.append(f"{path}: rendered from templates/{name}, but missing")
            elif path.read_text() != body:
                problems.append(f"{path}: differs from templates/{name} rendered; edit the template, then run render.py")
        else:
            path.write_text(body)
    for name in sorted(existing - set(rendered)):
        problems.append(f"{workflows_dir / name}: no template in {templates_dir}")
    for p in problems:
        print(f"::error::{p}")
    print(f"render: {len(rendered)} workflows{' checked' if check else ' written'}, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
