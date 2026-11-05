"""Production gates (cc-sdlc design rule D4): a plan's gates, checked against the operations catalog,
turned into gate requests CD approves, and the signed results the production broker returns.

Pure functions over text and JSON, plus a CLI the workflows call. The broker on the production host
(production/factory_op.py) runs its installed copy of this module, so the workflows and the host build
the same request and the same digest.

  plan          ops/sdlc/process/production-gates.md: `### Gate G<n>: title` sections, each with an
                optional ```gate-ops block of catalog operations.
  catalog       production/ops.json.
  request       what CD approves: the gate's steps with values filled in, bound by a digest that the
                gate run's title carries. CD approves the run in environment factory-production.
  receipt       what the broker did, signed with its root-only key (production/receipt.pub verifies).
  PR comments   display records by the App, each led by one marker line:
                  <!-- factory-gate-tracker: {...} -->  the plan, issue and the gate execution stopped at
                  <!-- factory-gate-request: {...} -->  a request and its run
                  <!-- factory-gate-result: {...} -->   a signed receipt (or a CD gate's approval)
                Comments can be edited by any writer, so nothing here authorizes anything: the broker
                re-derives every request and checks CD's approval with GitHub's deployment records.
"""

import argparse
import hashlib
import json
import pathlib
import re
import sys

# python3 -I leaves this directory off the path: ed25519 and implement_guard live beside this file.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

GATE_HEAD = re.compile(r"^###\s+Gate\s+(G[1-9][0-9]?)\s*:\s*(.+?)\s*$")
ITEM_HEAD = re.compile(r"^###\s+(Phase|Step)\s+([0-9]+)\b")
SECTION_END = re.compile(r"^#{1,3}\s")
FENCE_OPEN = re.compile(r"^```gate-ops\s*$")
FENCE_CLOSE = re.compile(r"^```\s*$")
STEP_ID = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
FIELD = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
PLACEHOLDER = re.compile(r"^\$\{([^{}]+)\}$")
GATE_REF = re.compile(r"^(G[1-9][0-9]?)\.([a-z][a-z0-9-]{0,31})\.([a-z][a-z0-9_]{0,31})$")
STEP_REF = re.compile(r"^steps\.([a-z][a-z0-9-]{0,31})\.([a-z][a-z0-9_]{0,31})$")
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
GATE_ID = re.compile(r"^G[1-9][0-9]?$")
PLAN_PATH = re.compile(r"^docs/current_work/(sdlc-lite|planning)/d[0-9]+[a-z]?_[a-z0-9_]+_plan\.md$")
KINDS = ("read", "change")
MAX_STEPS = 12
MARKER = re.compile(r"\A<!-- (factory-gate-(?:tracker|request|result)): (\{.*?\}) -->\n", re.S)
TRACKER, REQUEST, RESULT = "factory-gate-tracker", "factory-gate-request", "factory-gate-result"
TITLE = re.compile(r"^factory-gate #([0-9]+) (G[1-9][0-9]?) a([0-9]+) (ops|cd) ([0-9a-f]{64})$")
# A broker receipt's status. Only done lets execution continue. refused: nothing ran.
RECEIPT_STATUSES = ("done", "failed", "rolled-back", "refused")
# A result the report job posts without a receipt: CD rejected the run, or the runner returned nothing.
UNSIGNED_STATUSES = ("rejected", "error")
# Unsigned results a PR may show: those, and a refusal the broker made before it read the request.
UNSIGNED_RESULTS = UNSIGNED_STATUSES + ("refused",)
DIGEST_FIELDS = ("repo", "issue", "pr", "gate", "attempt", "plan", "plan_blob", "head", "kind", "steps",
                 "rollback", "ops_digest")


class Invalid(ValueError):
    """A plan, catalog, request, receipt or marker that breaks the rules."""


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


# ---------------------------------------------------------------- the catalog and its digest

def load_catalog(text):
    """The operations catalog, checked: every operation has a kind, a summary, anchored parameter and
    output patterns that compile, a timeout, and `requires` naming other operations."""
    try:
        cat = json.loads(text)
    except json.JSONDecodeError as e:
        raise Invalid(f"catalog isn't JSON: {e}") from e
    if not isinstance(cat, dict) or not isinstance(cat.get("version"), int) or not isinstance(cat.get("operations"), dict):
        raise Invalid("catalog needs an integer version and an operations object")
    ops = cat["operations"]
    for name, op in ops.items():
        if not STEP_ID.match(name) or not isinstance(op, dict):
            raise Invalid(f"catalog: bad operation {name!r}")
        if op.get("kind") not in KINDS or not isinstance(op.get("summary"), str) or not op["summary"].strip():
            raise Invalid(f"catalog: {name} needs kind (read or change) and a summary")
        if not isinstance(op.get("timeout_s"), int) or not 1 <= op["timeout_s"] <= 3600:
            raise Invalid(f"catalog: {name} needs timeout_s between 1 and 3600")
        for key in ("params", "outputs"):
            fields = op.get(key, {})
            if not isinstance(fields, dict):
                raise Invalid(f"catalog: {name}.{key} must be an object")
            for field, pattern in fields.items():
                if not FIELD.match(field) or not isinstance(pattern, str) or not pattern.startswith("^") or not pattern.endswith("$"):
                    raise Invalid(f"catalog: {name}.{key}.{field} needs an anchored pattern")
                try:
                    re.compile(pattern)
                except re.error as e:
                    raise Invalid(f"catalog: {name}.{key}.{field}: {e}") from e
        requires = op.get("requires", [])
        if not isinstance(requires, list) or any(r not in ops for r in requires):
            raise Invalid(f"catalog: {name}.requires must name operations in the catalog")
        if not isinstance(op.get("rollback_only", False), bool):
            raise Invalid(f"catalog: {name}.rollback_only must be true or false")
    return cat


def ops_digest(files):
    """sha256 over the operation package: {canonical name: bytes}. The names are the installed layout
    (gates.py, ed25519.py, factory_op.py, ops.json, ops/<name>.sh), so main's copy and the host's
    installed copy hash the same when they match."""
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(name.encode() + b"\0" + hashlib.sha256(files[name]).hexdigest().encode() + b"\n")
    return h.hexdigest()


def repo_ops_files(factory_dir):
    """The operation package as it is in the repository (.github/factory)."""
    d = pathlib.Path(factory_dir)
    files = {"gates.py": (d / "gates.py").read_bytes(), "ed25519.py": (d / "ed25519.py").read_bytes(),
             "factory_op.py": (d / "production" / "factory_op.py").read_bytes(),
             "ops.json": (d / "production" / "ops.json").read_bytes()}
    for script in sorted((d / "production" / "ops").glob("*.sh")):
        files[f"ops/{script.name}"] = script.read_bytes()
    return files


def installed_ops_files(lib_dir):
    """The operation package as setup installs it on the host (/usr/local/lib/factory-prod)."""
    d = pathlib.Path(lib_dir)
    files = {n: (d / n).read_bytes() for n in ("gates.py", "ed25519.py", "factory_op.py", "ops.json")}
    for script in sorted((d / "ops").glob("*.sh")):
        files[f"ops/{script.name}"] = script.read_bytes()
    return files


# ---------------------------------------------------------------- the plan's gates

def parse_gates(plan):
    """The plan's gates, in order: [{id, title, block (dict or None), line}]. Also checks the shape the
    factory relies on: G1, G2, ... in order; at most one gate-ops block per gate; a phase (or step)
    before the first gate and after the last. Raises Invalid."""
    lines = plan.splitlines()
    gates, items, current, fence = [], [], None, None
    for n, line in enumerate(lines, 1):
        if fence is not None:
            if FENCE_CLOSE.match(line):
                body = "\n".join(lines[fence:n - 1])
                if current is None:
                    raise Invalid(f"line {fence}: a gate-ops block outside a gate section")
                if current["block"] is not None:
                    raise Invalid(f"{current['id']}: more than one gate-ops block")
                try:
                    current["block"] = json.loads(body)
                except json.JSONDecodeError as e:
                    raise Invalid(f"{current['id']}: the gate-ops block isn't JSON: {e}") from e
                fence = None
            continue
        if FENCE_OPEN.match(line):
            fence = n
            continue
        m = GATE_HEAD.match(line)
        if m:
            current = {"id": m.group(1), "title": m.group(2), "block": None, "line": n}
            gates.append(current)
            items.append(("gate", m.group(1)))
            continue
        m = ITEM_HEAD.match(line)
        if m:
            items.append(("phase", m.group(2)))
        if SECTION_END.match(line):
            current = None
    if fence is not None:
        raise Invalid(f"line {fence}: an unclosed gate-ops block")
    for i, g in enumerate(gates, 1):
        if g["id"] != f"G{i}":
            raise Invalid(f"gates must be numbered G1, G2, ... in order; found {g['id']} as gate {i}")
    if gates:
        if items[0][0] != "phase":
            raise Invalid("the factory needs a phase before the first gate (it has no PR to post the gate on)")
        if items[-1][0] != "phase":
            raise Invalid("the plan's last item must be a phase (it writes the records)")
    return gates


RELEASE_HEAD = re.compile(r"^###\s+Release\s*$")
RELEASE_WHY = re.compile(r"^\*\*Why:\*\*\s*(\S.*?)\s*$")


def parse_release(plan):
    """A plan's release declaration, for a project whose production follows a release branch (D4 rule 13,
    factory.json's release.branch): a `### Release` section whose `**Why:**` line says what production needs
    from this deliverable. When CD merges the plan's execution PR, the factory opens a release PR into the
    branch. Returns the reason, or None without the section. Raises Invalid for a section with no reason, or
    more than one."""
    found, why, section = 0, None, False
    for line in plan.splitlines():
        if RELEASE_HEAD.match(line):
            found += 1
            section = True
            continue
        if section and SECTION_END.match(line):
            section = False
        if section and why is None and (m := RELEASE_WHY.match(line)):
            why = m.group(1)
    if found > 1:
        raise Invalid("the plan has more than one Release section")
    if found and why is None:
        raise Invalid("the plan's Release section needs a **Why:** line (what production needs from it)")
    return why


def gate(plan, gate_id):
    for g in parse_gates(plan):
        if g["id"] == gate_id:
            return g
    raise Invalid(f"the plan has no gate {gate_id}")


def _value_errors(where, value, pattern, outputs_of, step_ids, in_rollback):
    """Errors for one parameter value: a literal matching its pattern, or exactly one placeholder."""
    if not isinstance(value, str):
        return [f"{where}: values are strings"]
    m = PLACEHOLDER.match(value)
    if not m:
        if "${" in value:
            return [f"{where}: a placeholder must be the whole value"]
        return [] if re.match(pattern, value) else [f"{where}: {value!r} doesn't match {pattern}"]
    ref = m.group(1)
    if ref == "head":
        return []
    g = GATE_REF.match(ref)
    if g:
        gate_id, step, field = g.groups()
        known = outputs_of.get(gate_id)
        if known is None:
            return [f"{where}: ${{{ref}}} names a gate that doesn't come earlier"]
        if field not in known.get(step, ()):
            return [f"{where}: ${{{ref}}}: {gate_id} has no step {step} with output {field}"]
        return []
    s = STEP_REF.match(ref)
    if s:
        if not in_rollback:
            return [f"{where}: ${{steps...}} is for rollback steps only"]
        step, field = s.groups()
        if field not in step_ids.get(step, ()):
            return [f"{where}: ${{{ref}}}: no step {step} with output {field} in this gate"]
        return []
    return [f"{where}: unknown placeholder ${{{ref}}}"]


def check_block(gate_id, block, catalog, outputs_of):
    """Errors in one gate's gate-ops block. outputs_of: {earlier gate ID: {step id: [output fields]}}."""
    ops = catalog["operations"]
    if not isinstance(block, dict) or set(block) - {"steps", "rollback"} or not isinstance(block.get("steps"), list):
        return [f"{gate_id}: the block is {{\"steps\": [...], \"rollback\": [...]}}"]
    errors, step_ids, seen_ops = [], {}, []
    for key in ("steps", "rollback"):
        items = block.get(key, [])
        if not isinstance(items, list) or (key == "steps" and not items) or len(items) > MAX_STEPS:
            errors.append(f"{gate_id}.{key}: 1 to {MAX_STEPS} steps" if key == "steps" else f"{gate_id}.rollback: at most {MAX_STEPS} steps")
            continue
        for i, step in enumerate(items, 1):
            where = f"{gate_id}.{key}[{i}]"
            if not isinstance(step, dict) or set(step) - {"id", "op", "with"}:
                errors.append(f"{where}: a step is {{\"id\", \"op\", \"with\"}}")
                continue
            name = step.get("op")
            op = ops.get(name)
            if op is None:
                errors.append(f"{where}: {name!r} isn't in the operations catalog")
                continue
            if op.get("rollback_only") and key == "steps":
                errors.append(f"{where}: {name} may only run as a rollback step")
            sid = step.get("id", name)
            if not isinstance(sid, str) or not STEP_ID.match(sid):
                errors.append(f"{where}: bad step id {sid!r}")
            elif key == "steps":
                if sid in step_ids:
                    errors.append(f"{where}: step id {sid} is used twice; give the step an id")
                step_ids[sid] = list(op.get("outputs", {}))
            for req in op.get("requires", []):
                if key == "steps" and req not in seen_ops:
                    errors.append(f"{where}: {name} needs a {req} step earlier in the same gate")
            if key == "steps":
                seen_ops.append(name)
            params, given = op.get("params", {}), step.get("with", {})
            if not isinstance(given, dict) or set(given) != set(params):
                errors.append(f"{where}: {name} takes exactly {sorted(params) or 'no parameters'}")
                continue
            for field, pattern in params.items():
                errors += _value_errors(f"{where}.{field}", given[field], pattern, outputs_of, step_ids, key == "rollback")
            if key == "rollback" and not any(STEP_REF.match((PLACEHOLDER.match(v) or [None, ""])[1] or "")
                                             for v in given.values() if isinstance(v, str)):
                # A rollback step runs only when the step it undoes was reached: it must name that
                # step's output, which exists only once the step got that far.
                errors.append(f"{where}: a rollback step must use an output of the step it undoes (${{steps.<id>.<field>}})")
    return errors


def check_plan(plan, catalog):
    """Every error in the plan's gates against the catalog. A gate without a block is a CD gate."""
    try:
        gates = parse_gates(plan)
    except Invalid as e:
        return [str(e)]
    errors, outputs_of = [], {}
    for g in gates:
        if g["block"] is None:
            outputs_of[g["id"]] = {}
            continue
        errors += check_block(g["id"], g["block"], catalog, outputs_of)
        steps = g["block"].get("steps") if isinstance(g["block"], dict) else None
        outputs_of[g["id"]] = {
            s.get("id", s.get("op")): list(catalog["operations"].get(s.get("op"), {}).get("outputs", {}))
            for s in (steps or []) if isinstance(s, dict)
        }
    return errors


# ---------------------------------------------------------------- requests

def resolve(block, catalog, head, gate_outputs):
    """The block's steps and rollback with ${head} and ${G<n>.<step>.<field>} filled in.
    gate_outputs: {gate ID: {step id: {field: value}}} from earlier gates' results. ${steps...} stays
    for the broker to fill at run time. Every filled value must match its pattern."""
    if not SHA.match(head or ""):
        raise Invalid(f"head isn't a commit SHA: {head!r}")
    ops = catalog["operations"]

    def fill(step, in_rollback):
        op = ops[step["op"]]
        out = {"id": step.get("id", step["op"]), "op": step["op"], "with": {}}
        for field, value in step.get("with", {}).items():
            m = PLACEHOLDER.match(value)
            ref = m.group(1) if m else None
            if ref == "head":
                value = head
            elif ref and GATE_REF.match(ref):
                gate_id, sid, f = GATE_REF.match(ref).groups()
                try:
                    value = gate_outputs[gate_id][sid][f]
                except KeyError:
                    raise Invalid(f"{step['op']}.{field}: no result for ${{{ref}}}") from None
            elif ref and STEP_REF.match(ref) and in_rollback:
                out["with"][field] = value
                continue
            elif ref:
                raise Invalid(f"{step['op']}.{field}: unknown placeholder ${{{ref}}}")
            if not isinstance(value, str) or not re.match(op["params"][field], value):
                raise Invalid(f"{step['op']}.{field}: {value!r} doesn't match {op['params'][field]}")
            out["with"][field] = value
        return out

    return ([fill(s, False) for s in block["steps"]], [fill(s, True) for s in block.get("rollback", [])])


def digest(request):
    """sha256 over the request's binding fields: what CD approves is exactly what the broker runs."""
    return hashlib.sha256(canonical({k: request[k] for k in DIGEST_FIELDS}).encode()).hexdigest()


def build_request(*, repo, issue, pr, plan, plan_blob, plan_text, gate_id, attempt, head, catalog,
                  gate_outputs, ops_digest):
    """A gate request: the binding fields and their digest. kind is `ops` (the broker runs the block)
    or `cd` (no block: CD does the runbook, then approves to continue)."""
    if not PLAN_PATH.match(plan or ""):
        raise Invalid(f"not a plan path: {plan!r}")
    if not SHA.match(plan_blob or ""):
        raise Invalid(f"plan_blob isn't a SHA: {plan_blob!r}")
    if not DIGEST.match(ops_digest or ""):
        raise Invalid("ops_digest isn't a sha256")
    if not isinstance(attempt, int) or not 1 <= attempt <= 99:
        raise Invalid(f"attempt must be 1-99: {attempt!r}")
    g = gate(plan_text, gate_id)
    if g["block"] is None:
        steps, rollback, kind = [], [], "cd"
        if not SHA.match(head or ""):
            raise Invalid(f"head isn't a commit SHA: {head!r}")
    else:
        errors = check_plan(plan_text, catalog)
        if errors:
            raise Invalid("; ".join(errors))
        steps, rollback = resolve(g["block"], catalog, head, gate_outputs)
        kind = "ops"
    request = {"v": 1, "repo": repo, "issue": int(issue), "pr": int(pr), "gate": gate_id, "attempt": attempt,
               "title": g["title"], "plan": plan, "plan_blob": plan_blob, "head": head, "kind": kind,
               "steps": steps, "rollback": rollback, "ops_digest": ops_digest}
    request["digest"] = digest(request)
    return request


def run_title(request):
    """The gate run's title, fixed at dispatch: the broker reads the digest from it."""
    return f"factory-gate #{request['pr']} {request['gate']} a{request['attempt']} {request['kind']} {request['digest']}"


def parse_title(title):
    m = TITLE.match(title or "")
    if not m:
        raise Invalid(f"not a gate run title: {title!r}")
    pr, gate_id, attempt, kind, dig = m.groups()
    return {"pr": int(pr), "gate": gate_id, "attempt": int(attempt), "kind": kind, "digest": dig}


# ---------------------------------------------------------------- receipts

def sign_receipt(secret, receipt):
    import ed25519
    return {"receipt": receipt, "sig": ed25519.sign(secret, canonical(receipt).encode()).hex()}


def verify_receipt(public_hex, signed):
    """The receipt, if its signature verifies with the committed public key. Raises Invalid."""
    import ed25519
    try:
        receipt, sig = signed["receipt"], bytes.fromhex(signed["sig"])
        ok = isinstance(receipt, dict) and ed25519.verify(bytes.fromhex(public_hex.strip()), canonical(receipt).encode(), sig)
    except (KeyError, TypeError, ValueError):
        ok = False
    if not ok:
        raise Invalid("the receipt's signature doesn't verify")
    return receipt


def check_receipt(receipt, request, catalog):
    """A verified receipt that answers this request: same digest, a known status, the request's steps
    in order (a prefix, when it stopped early), and outputs the catalog allows."""
    if receipt.get("digest") != request["digest"] or receipt.get("status") not in RECEIPT_STATUSES \
            or receipt.get("pr") != request["pr"] or receipt.get("gate") != request["gate"]:
        raise Invalid("the receipt doesn't answer this request")
    ops = catalog["operations"]
    for key in ("steps", "rollback"):
        ran, asked = receipt.get(key) or [], request[key]
        if len(ran) > len(asked) or any(r.get("id") != a["id"] or r.get("op") != a["op"] for r, a in zip(ran, asked)):
            raise Invalid(f"the receipt's {key} aren't the request's")
        for r in ran:
            allowed = ops[r["op"]].get("outputs", {})
            for field, value in (r.get("outputs") or {}).items():
                if field not in allowed or not isinstance(value, str) or not re.match(allowed[field], value):
                    raise Invalid(f"the receipt's {r['op']}.{field} isn't an allowed output")
    if receipt["status"] == "done" and len(receipt.get("steps") or []) != len(request["steps"]):
        raise Invalid("a done receipt must cover every step")
    return receipt


def unbound_refusal(receipt):
    """A refusal the broker made before it could read the request (a malformed request, no usable token,
    the production lock, a run it couldn't check): signed, but bound to no digest, PR or gate."""
    return receipt.get("status") == "refused" and not receipt.get("digest") and receipt.get("pr") is None \
        and receipt.get("gate") is None and not receipt.get("steps") and not receipt.get("rollback")


def report_result(payload, request, catalog, public_hex):
    """(the result to post, its status) for the runner's signed receipt. Raises Invalid. An unbound refusal
    can't be this request's result, so it's posted unsigned, with the broker's reason: display only, like a
    rejected run, never done."""
    receipt = verify_receipt(public_hex, payload)
    if unbound_refusal(receipt):
        reason = receipt.get("reason") or "no reason given"
        return ({"unsigned": True, "digest": request["digest"], "gate": request["gate"], "status": "refused",
                 "kind": request["kind"], "reason": f"the production broker refused before reading the request: {reason}"},
                "refused")
    return payload, check_receipt(receipt, request, catalog)["status"]


# ---------------------------------------------------------------- PR comments

def marker(name, payload):
    text = canonical(payload)
    if "-->" in text:
        raise Invalid("a marker payload can't contain -->")
    return f"<!-- {name}: {text} -->\n"


def parse_marker(body):
    """(name, payload) of a comment's leading gate marker, or None."""
    m = MARKER.match(body or "")
    if not m:
        return None
    try:
        payload = json.loads(m.group(2))
    except json.JSONDecodeError:
        return None
    return (m.group(1), payload) if isinstance(payload, dict) else None


def pr_state(comments, app_id, public_hex, pr=None):
    """What the PR's App comments say: the tracker (and its comment id), requests in order, and results
    by digest. A result counts only if the broker's signature verifies and it names this PR; an unsigned
    result (a rejected run, or one that returned nothing) is display only and never counts as done.
    Comments by anyone but the App are ignored."""
    state = {"tracker": None, "tracker_comment": None, "requests": [], "results": {}}
    for c in sorted(comments, key=lambda c: (c["created_at"], c["id"])):
        user = c.get("user") or {}
        if user.get("type") != "Bot" or user.get("id") != app_id:
            continue
        parsed = parse_marker(c.get("body"))
        if not parsed:
            continue
        name, payload = parsed
        if name == TRACKER and state["tracker"] is None:
            state["tracker"], state["tracker_comment"] = payload, c["id"]
        elif name == REQUEST and isinstance(payload.get("request"), dict):
            state["requests"].append({**payload, "comment": c["id"]})
        elif name == RESULT:
            if payload.get("unsigned"):
                if payload.get("status") in UNSIGNED_RESULTS:
                    state["results"].setdefault(payload.get("digest"), payload)
                continue
            try:
                receipt = verify_receipt(public_hex, payload)
            except Invalid:
                continue
            if pr is not None and receipt.get("pr") != pr:
                continue
            state["results"][receipt.get("digest")] = receipt
    return state


def result_for(state, req):
    """The result answering a request: same digest and, for a signed receipt, the same gate."""
    res = state["results"].get(req.get("digest"))
    if res and not res.get("unsigned") and res.get("gate") != req.get("gate"):
        return None
    return res


def gate_status(state, gate_id):
    """(status, latest request entry) of one gate on this PR: done, failed, rolled-back, refused,
    rejected, error, waiting (a request without a result), or not-started."""
    latest = None
    for entry in state["requests"]:
        req = entry["request"]
        if req.get("gate") != gate_id:
            continue
        res = result_for(state, req)
        if res and res.get("status") == "done" and not res.get("unsigned"):
            return "done", entry
        latest = entry
    if latest is None:
        return "not-started", None
    res = result_for(state, latest["request"])
    return (res.get("status") if res else "waiting"), latest


def gate_outputs(state):
    """{gate ID: {step id: {field: value}}} from each gate's done result (CD gates have none)."""
    out = {}
    for entry in state["requests"]:
        req = entry["request"]
        res = result_for(state, req)
        if res and res.get("status") == "done" and not res.get("unsigned"):
            out[req["gate"]] = {s["id"]: s.get("outputs") or {} for s in res.get("steps") or []}
    return out


def next_attempt(state, gate_id):
    return 1 + max([e["request"].get("attempt", 0) for e in state["requests"] if e["request"].get("gate") == gate_id] or [0])


# ---------------------------------------------------------------- rendering (display only)

def _literal(text):
    from implement_guard import literal  # noqa: E402 (the guard's escaping for agent-written text)
    return literal(text)


def render_tracker(tracker, plan_text, state):
    lines = [marker(TRACKER, tracker).rstrip("\n"), "", "### Production gates", "",
             f"Plan: `{tracker['plan']}`. Each gate runs only after you approve its gate run in the "
             "`factory-production` environment (**Review deployments** on the run).", "",
             "| Gate | What | Kind | Status |", "|---|---|---|---|"]
    labels = {"done": "done", "waiting": "**awaiting your approval**", "not-started": "not reached",
              "failed": "failed", "rolled-back": "failed, rolled back", "refused": "refused (nothing ran)",
              "rejected": "rejected"}
    for g in parse_gates(plan_text):
        status, entry = gate_status(state, g["id"])
        if status == "not-started" and tracker.get("stopped_at") == g["id"]:
            status = "requesting"
        cell = labels.get(status, status)
        if entry and entry.get("run_url"):
            cell += f" ([run]({entry['run_url']}))"
        kind = "CD runs the runbook" if g["block"] is None else "production runner"
        lines.append(f"| {g['id']} | {_literal(g['title'])} | {kind} | {cell} |")
    lines += ["", "<sub>factory gates · updated by the factory</sub>"]
    return "\n".join(lines) + "\n"


def render_request(request, run_url, catalog, plan_text):
    g = gate(plan_text, request["gate"])
    lines = [marker(REQUEST, {"request": request, "run_url": run_url}).rstrip("\n"), "",
             f"### Gate {request['gate']}: {_literal(g['title'])} (attempt {request['attempt']})", ""]
    if request["kind"] == "cd":
        lines += ["**You run this gate.** Do the runbook in the plan, post the report-back values as a comment "
                  "on this PR, then approve the run: the production runner records your approval (it runs nothing) "
                  "and execution continues.", ""]
    else:
        lines += ["**The production runner runs these steps, in order, once you approve the run:**", ""]
        for i, s in enumerate(request["steps"], 1):
            op = catalog["operations"][s["op"]]
            args = ", ".join(f"`{k}={v}`" for k, v in s["with"].items())
            lines.append(f"{i}. `{s['op']}`{' (' + args + ')' if args else ''} ({op['kind']}): {op['summary']}")
        lines += ["", "**If a step fails:** " + ("these rollback steps run, for the steps that were reached:" if request["rollback"]
                                                 else "nothing is rolled back; the gate stops.")]
        for s in request["rollback"]:
            args = ", ".join(f"`{k}={v}`" for k, v in s["with"].items())
            lines.append(f"- `{s['op']}` ({args})")
        lines.append("")
    lines += [f"**Code at this gate:** `{request['head']}`. **Plan:** `{request['plan']}` (blob `{request['plan_blob'][:12]}`).",
              f"**Approve:** [the gate run]({run_url}) → Review deployments → `factory-production`. "
              f"Digest `{request['digest'][:16]}`, also in the run's title.", "",
              "<sub>factory gate request · comments are display only; the runner re-checks everything</sub>"]
    return "\n".join(lines) + "\n"


def render_result(payload, request, run_url):
    """A result comment: the signed receipt as its marker, and what happened in words."""
    rec = payload if payload.get("unsigned") else payload["receipt"]
    status = rec["status"]
    words = {"done": "done", "failed": "**failed**", "rolled-back": "**failed and rolled back**",
             "refused": "**refused: nothing ran**", "rejected": "**rejected**"}.get(status, status)
    lines = [marker(RESULT, payload).rstrip("\n"), "",
             f"### Gate {request['gate']} (attempt {request['attempt']}): {words}", ""]
    if rec.get("reason"):
        lines += [f"**Why:** {_literal(rec['reason'])}", ""]
    for key, heading in (("steps", "Steps"), ("rollback", "Rollback")):
        rows = rec.get(key) or []
        if rows:
            lines += [f"**{heading}:**", "", "| Step | Status | Outputs |", "|---|---|---|"]
            for r in rows:
                outs = ", ".join(f"`{k}={v}`" for k, v in (r.get("outputs") or {}).items()) or "—"
                why = f" ({_literal(r['why'])})" if r.get("why") else ""
                lines.append(f"| `{r['id']}` | {r.get('status')}{why} | {outs} |")
            lines.append("")
    if status == "done":
        lines.append("Execution continues on this PR.")
    elif status == "error":
        lines.append("Re-run this run's failed jobs and approve again: if the gate finished on the host, its recorded "
                     "result comes back without running anything; if it was interrupted, the broker says how to resolve it.")
    elif status == "refused" and "interrupted" in (rec.get("reason") or ""):
        lines.append("An earlier gate run was interrupted, so its outcome is unknown. Inspect production, then "
                     "resolve it on the host (`sudo factory-op resolve`), and add `factory:gate-retry` here.")
    else:
        lines.append("To try again, add `factory:gate-retry` to this PR (a fresh request, approved again). "
                     "To fix the code first, request changes; to stop, close the PR.")
    lines += ["", f"<sub>factory gate · [run]({run_url})" + (f" · host run `{rec['run']}`" if rec.get("run") else "") + "</sub>"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- CLI for the workflows

def _ndjson(path):
    return [json.loads(line) for line in pathlib.Path(path).read_text().splitlines() if line.strip()]


def _context(args):
    """Everything a workflow fetched with `gh api`, as files: the PR, its comments (NDJSON), and the
    plan's contents-API record on the default branch (or none, before the tracker names a plan)."""
    factory = pathlib.Path(args.factory_dir)
    catalog = load_catalog((factory / "production" / "ops.json").read_text())
    public = (factory / "production" / "receipt.pub").read_text().strip()
    pr = json.loads(pathlib.Path(args.pr_json).read_text())
    m = re.match(r"^factory/([0-9]+)-impl$", (pr.get("head") or {}).get("ref", ""))
    if not m or pr.get("state") != "open" or (pr.get("user") or {}).get("id") != args.app_id \
            or (pr.get("head") or {}).get("repo", {}).get("full_name") != args.repo:
        raise Invalid(f"PR #{pr.get('number')} isn't an open factory execution PR")
    state = pr_state(_ndjson(args.comments), args.app_id, public, pr["number"])
    return factory, catalog, pr, int(m.group(1)), state


def _plan(args):
    meta = json.loads(pathlib.Path(args.plan_meta).read_text())
    import base64
    return meta["sha"], base64.b64decode(meta["content"]).decode()


def cli(argv):
    p = argparse.ArgumentParser(prog="gates.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check-plan", help="errors in a plan's gates (exit 1 if any)")
    c.add_argument("plan")
    c.add_argument("--catalog", default=str(pathlib.Path(__file__).resolve().parent / "production" / "ops.json"))
    pp = sub.add_parser("plan-path", help="the plan the PR's tracker names")
    pp.add_argument("--comments", required=True)
    pp.add_argument("--app-id", type=int, required=True)
    sp = sub.add_parser("stopped-at", help="the gate the PR's tracker says execution is stopped at (empty if none)")
    sp.add_argument("--comments", required=True)
    sp.add_argument("--app-id", type=int, required=True)
    for name in ("request", "verify-request", "tracker", "report", "results"):
        s = sub.add_parser(name)
        s.add_argument("--repo", required=True)
        s.add_argument("--app-id", type=int, required=True)
        s.add_argument("--factory-dir", required=True)
        s.add_argument("--pr-json", required=True)
        s.add_argument("--comments", required=True)
        s.add_argument("--plan-meta")
        s.add_argument("--out", required=True)
        if name == "verify-request":
            s.add_argument("--request-b64", required=True)
            s.add_argument("--run-url", required=True)
        if name == "tracker":
            s.add_argument("--plan")
            s.add_argument("--stopped-at", default=None, help="the gate execution stopped at; empty clears it")
        if name == "report":
            s.add_argument("--request-b64", required=True)
            s.add_argument("--receipt", help="the broker's signed receipt")
            s.add_argument("--cd-approved", choices=UNSIGNED_STATUSES,
                           help="no receipt: rejected (CD rejected the run) or error (the runner returned nothing)")
            s.add_argument("--run-url", required=True)
    args = p.parse_args(argv)
    out = lambda text: pathlib.Path(args.out).write_text(text)  # noqa: E731

    if args.cmd == "check-plan":
        errors = check_plan(pathlib.Path(args.plan).read_text(), load_catalog(pathlib.Path(args.catalog).read_text()))
        for e in errors:
            print(f"::error::{args.plan}: {e}")
        return 1 if errors else 0

    if args.cmd == "stopped-at":
        for c in _ndjson(args.comments):
            parsed = parse_marker(c.get("body"))
            if (c.get("user") or {}).get("id") == args.app_id and parsed and parsed[0] == TRACKER:
                gate_id = parsed[1].get("stopped_at") or ""
                print(gate_id if GATE_ID.match(gate_id) else "")
                return 0
        print("")
        return 0

    if args.cmd == "plan-path":
        for c in _ndjson(args.comments):
            parsed = parse_marker(c.get("body"))
            if (c.get("user") or {}).get("id") == args.app_id and parsed and parsed[0] == TRACKER:
                plan = parsed[1].get("plan", "")
                if PLAN_PATH.match(plan):
                    print(plan)
                    return 0
        raise Invalid("no gate tracker naming a plan on this PR")

    factory, catalog, pr, issue, state = _context(args)
    if args.cmd == "tracker":
        tracker = dict(state["tracker"] or {"v": 1, "issue": issue})
        if args.plan:
            tracker["plan"] = args.plan
        if args.stopped_at is not None:
            tracker["stopped_at"] = args.stopped_at
        tracker.setdefault("stopped_at", "")
        if not PLAN_PATH.match(tracker.get("plan", "")) or (tracker["stopped_at"] and not GATE_ID.match(tracker["stopped_at"])):
            raise Invalid("the tracker needs a plan path and, if stopped, a gate ID")
        _, plan_text = _plan(args)
        out(render_tracker(tracker, plan_text, state))
        return 0

    tracker = state["tracker"] or {}
    if args.cmd in ("request", "verify-request"):
        plan_blob, plan_text = _plan(args)
        if args.cmd == "request":
            gate_id = tracker.get("stopped_at")
            if not gate_id:
                raise Invalid("execution isn't stopped at a gate on this PR")
            status, _ = gate_status(state, gate_id)
            if status == "done":
                raise Invalid(f"{gate_id} is already done")
            attempt = next_attempt(state, gate_id)
        else:
            asked = json.loads(__import__("base64").b64decode(args.request_b64))
            gate_id, attempt = asked.get("gate"), asked.get("attempt")
        if tracker.get("plan") is None:
            raise Invalid("no gate tracker on this PR")
        request = build_request(repo=args.repo, issue=issue, pr=pr["number"], plan=tracker["plan"], plan_blob=plan_blob,
                                plan_text=plan_text, gate_id=gate_id, attempt=attempt, head=pr["head"]["sha"],
                                catalog=catalog, gate_outputs=gate_outputs(state),
                                ops_digest=ops_digest(repo_ops_files(factory)))
        if args.cmd == "request":
            out(canonical(request))
            return 0
        if asked != request:
            raise Invalid("the dispatched request isn't what the plan, the PR and the earlier results give now")
        out(render_request(request, args.run_url, catalog, plan_text))
        return 0

    if args.cmd == "report":
        request = json.loads(__import__("base64").b64decode(args.request_b64))
        if args.cd_approved in UNSIGNED_STATUSES:
            # No receipt: CD rejected the run, or the runner returned nothing (the host ledger has the truth).
            status = args.cd_approved
            payload = {"unsigned": True, "digest": request["digest"], "gate": request["gate"], "status": status,
                       "kind": request["kind"],
                       "reason": "you rejected the run" if status == "rejected" else
                                 "the runner job returned no receipt (cancelled, timed out or failed)"}
        else:
            text = pathlib.Path(args.receipt).read_text().strip() if args.receipt else ""
            try:
                payload = json.loads(text.splitlines()[-1]) if text else None
                payload, status = report_result(payload, request, catalog,
                                                (factory / "production" / "receipt.pub").read_text())
            except (Invalid, ValueError, IndexError, KeyError, TypeError) as e:
                print(f"::error::no verified receipt: {e}")
                return 2
        out(render_result(payload, request, args.run_url))
        print(status)
        return 0

    if args.cmd == "results":
        results = []
        for entry in state["requests"]:
            req = entry["request"]
            res = result_for(state, req)
            if res and not res.get("unsigned"):
                results.append({"gate": req["gate"], "attempt": req["attempt"], "kind": res.get("kind", req["kind"]),
                                "status": res.get("status"), "head": res.get("head"), "steps": res.get("steps", []),
                                "rollback": res.get("rollback", [])})
        out(json.dumps({"plan": tracker.get("plan"), "gates": results}, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    try:
        sys.exit(cli(sys.argv[1:]))
    except Invalid as e:
        print(f"::error::{e}")
        sys.exit(1)
