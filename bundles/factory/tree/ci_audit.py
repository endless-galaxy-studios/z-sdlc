#!/usr/bin/env python3
"""The project's own CI, read against Enablement step 10, "The project's existing CI runs agent-written code"
(z-sdlc process/factory.md; process/factory-runbook.md § 2 item 4 and § 4.6). Report-only: it reads workflow
files and, with --repo, names on GitHub, and changes nothing.

    python3 .github/factory/ci_audit.py [<workflows-dir>] [--factory-dir DIR] [--repo OWNER/NAME] [--runs N] [--json]

    <workflows-dir>  default .github/workflows
    --factory-dir    where factory.json is (default: this script's directory): the CI tier's label, the
                     organization's hosted labels (policy.hosted_labels), the self-hosted exemptions and the
                     release branch
    --repo           read secret names, environments, the default branch and the token's default permissions on
                     GitHub, through gh; values are never read
    --runs N         (needs --repo) the gaps between each scheduled workflow's last N scheduled runs
    --json           the same data as JSON instead of tables

Why: factory branches live in the repository, so a factory PR's `pull_request` runs get the repository's secrets
and as wide a token as the workflow asks for. Before the first factory run, every job that builds, tests or lints a
PR's code is held to an agent job's rules, and reading a project's CI by eye has gone wrong before: a workflow
referenced a secret that didn't exist.

For each workflow it reports its triggers (which of them can carry agent-written code, and which branch's copy of
the workflow each runs) and, per job, its runner, container, environment, token, each checkout's
persist-credentials and ref, and every secret it references, with where.

Agent-written code reaches a job when one of these triggers reaches it and the job fetches that code:
- pull_request, pull_request_review(_comment) and merge_group, unless a branch filter excludes the bases factory
  PRs target (the default branch and factory.json's release branch); push, when its filter matches a factory
  branch (factory/...). The job fetches the code with a checkout of this repository whose ref isn't the default or
  base branch (an unset ref is the event's own commit);
- pull_request_target (it runs the base branch's copy) and workflow_run of a workflow that pull requests or factory
  pushes trigger (the default branch's): only a checkout of the PR's or the triggering run's head, or of a ref this
  audit can't read as the base, fetches it;
- workflow_call: its callers' events, through the calling job;
- `gh pr checkout` or `git fetch ... pull/...` in a run step, under any of them.
A job's own `if:` clears an event only when it is false for that event whatever the PR (it reads github.event_name,
github.ref, ref_name, head_ref, base_ref and github.event.pull_request.merged, compared with literals or by
startsWith, with && and ||; anything else counts as "may run"; a PR's code is unreviewed only while it's unmerged,
since a merged PR's closed run is the base branch's), and a job that needs a cleared job is cleared too unless its
`if:` has always(), failure() or cancelled(). A step's `if:` clears nothing: step 10 bars a secret anywhere in the
job.

Findings (exit 1). For a job that runs agent-written code, in the project's own workflows (the factory-*.yml ones
are held to workflow_policy.py's stricter rules instead):
  secret       a secret in the job, before or after the PR's code runs: a build step can write $GITHUB_ENV or
               $GITHUB_PATH and redirect every later step. A reusable workflow's job counts the secrets its callers
               pass (secrets: inherit passes all of them);
  checkout     a checkout without persist-credentials: false: the job's token stays in .git/config for the PR's code;
  token        a token that isn't read-only: a permissions block with a write scope, write-all, or none at all where
               the repository's default is read/write or wasn't read;
  runner       a self-hosted runner outside a container and off the CI tier (runners.ci), a label the policy
               doesn't list as GitHub-hosted (factory.json policy.hosted_labels adds the organization's own), one of
               the factory's own runner labels, or a runner this audit can't read (an expression, a runner group);
  remote-call  secrets passed to a reusable workflow in another repository, which this audit can't read.
In any job of the project's own workflows:
  head         pull_request_target checking out the PR's head: the PR's code with the base's secrets and token.
In the project's own workflows, with --repo:
  missing      a referenced secret that exists nowhere the job can read it: not in the repository, the organization
               secrets shared with it, or the job's own environment (one only another environment holds is missing).
               In a factory-*.yml workflow it is info: their templates reference optional slots (FACTORY_SVC_2..4,
               a planning database's password, Context7) that read as empty by design, and bootstrap.py checks
               the secrets the factory needs.
And a workflow that doesn't parse (unreadable): GitHub won't run it either, and the audit can't read it.

Info (no effect on the exit status): a secret on GitHub that no workflow references, a referenced environment that
doesn't exist (a run creates it with no protection rules and no secrets), a token left to a read-only repository
default, a self-hosted job in a container (workflow_policy.py holds the container to the factory's options) or
exempted in factory.json, artifacts a job downloads, a local action that can't be read, and the gaps of --runs.

What it doesn't see: a workflow on another branch (GitHub runs `pull_request` from the PR's own copy, so a factory
PR could change these files; CODEOWNERS review of .github/ is the boundary); a reusable workflow in another
repository; what an action does with its inputs; Dependabot's secrets; preview deploys (Enablement step 10's
next rule). A level gh couldn't read is "not checked", never an empty list.

Exit 0: no findings. 1: findings. 2: a usage or setup error. Needs PyYAML (the factory's CI has it) and, for
--repo and --runs, an authenticated gh.
"""

import argparse
import contextlib
import datetime
import json
import pathlib
import re
import statistics
import subprocess
import sys
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import yaml
    import workflow_policy as wp  # noqa: E402 (the factory directory's own module)
    IMPORT_ERROR = None
except ImportError as e:  # PyYAML is missing
    yaml = wp = None
    IMPORT_ERROR = str(e)

# Branches the factory pushes, as its workflows name them: a stage's branch and a release gate's pin. A push filter
# is matched against these, and any branch pattern naming factory/ counts as matching too.
FACTORY_BRANCHES = ("factory/1-change", "factory/release/1-G1-0123456789ab")
PR_EVENTS = ("pull_request", "pull_request_review", "pull_request_review_comment")
# Events whose own commit can be agent-written: an unset checkout ref fetches it.
OWN_COMMIT_EVENTS = PR_EVENTS + ("merge_group", "push")
# Events that run the base or default branch's copy: agent-written code only when a job fetches it.
BASE_EVENTS = ("pull_request_target", "workflow_run")
AGENT_EVENTS = OWN_COMMIT_EVENTS + BASE_EVENTS

# Which branch's copy of the workflow each event runs (GitHub's events table; runbook § 4.6).
COPY = {
    "push": "the pushed commit's",
    "pull_request": "the PR's merge commit's (the PR's own copy)",
    "pull_request_review": "the PR's merge commit's (the PR's own copy)",
    "pull_request_review_comment": "the PR's merge commit's (the PR's own copy)",
    "merge_group": "the merge queue's commit's (the PR's own copy)",
    "pull_request_target": "the PR's base branch's",
    "workflow_dispatch": "the branch or tag it's dispatched on",
    "workflow_call": "its caller's",
    "release": "the release tag's",
    "create": "the created branch's or tag's",
    "deployment": "the deployed commit's",
    "deployment_status": "the deployed commit's",
    "registry_package": "the published package's commit's",
}
for _event in ("schedule", "workflow_run", "status", "issues", "issue_comment", "repository_dispatch", "check_run",
               "check_suite", "delete", "discussion", "discussion_comment", "fork", "gollum", "label", "milestone",
               "page_build", "project", "project_card", "project_column", "public", "watch", "branch_protection_rule"):
    COPY[_event] = "the default branch's"
UNCLASSIFIED = "not classified (see GitHub's events table)"

EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.S)
# The secrets context, never a property named secrets (steps.secrets.outputs.token, needs.secrets.*, inputs.secrets).
SECRET_INDEXED = re.compile(r"(?<![\w.-])secrets\s*\[\s*'([^']*)'\s*\]", re.I)
SECRET_NAMED = re.compile(r"(?<![\w.-])secrets\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)", re.I)
STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")
# Every other use of the secrets context: secrets[<expression>], toJSON(secrets), the whole object.
SECRET_DYNAMIC = re.compile(r"(?<![\w.-])secrets\b(?!\s*\.\s*[A-Za-z_]|\s*\[\s*')", re.I)
BUILT_IN = "GITHUB_TOKEN"
DYNAMIC = "*"
# Checkout refs that are the default or the base branch whatever the PR.
SAFE_REFS = {"github.event.repository.default_branch", "github.base_ref", "github.event.pull_request.base.ref",
             "github.event.pull_request.base.sha", "github.event.merge_group.base_sha",
             "github.event.merge_group.base_ref"}
# Under pull_request_target and workflow_run, the run's own commit is the base or default branch's.
BASE_RUN_REFS = {"github.sha", "github.ref", "github.ref_name"}
HEAD_HINT = re.compile(r"pull_request\.head\b|head_ref|refs/pull/|merge_commit_sha|workflow_run\.head_|"
                       r"workflow_run\.pull_requests", re.I)
RUN_FETCHES_PR = re.compile(r"\bgh\s+pr\s+checkout\b|\bgit\s+(?:fetch|pull)\b[^\n]*\bpull/", re.I)
CONTINUES = re.compile(r"\b(?:always|failure|cancelled)\s*\(\s*\)", re.I)
REPO = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
# The workflow_policy globals configure() and main() set: the audit sets them for its run and puts them back.
POLICY_GLOBALS = ("PLANNING_LABEL", "PRODUCTION_LABEL", "WRITER_ENVIRONMENT", "PLANNING_ENVIRONMENT",
                  "PRODUCTION_ENVIRONMENT", "FACTORY_LABELS", "CI_LABEL", "HOSTED_EXTRA", "EXEMPTIONS", "REPO_ROOT")


class SetupError(Exception):
    """A usage or setup error: exit 2."""


class GhError(Exception):
    """gh couldn't answer: that level is not checked."""


def run_gh(args):
    """The one place gh runs: (exit status, stdout, stderr). Raises FileNotFoundError without gh."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def printable(text, limit=200):
    return " ".join("".join(c if 32 <= ord(c) < 127 else " " for c in str(text)).split())[:limit]


# ---------------------------------------------------------------------------------------------------------------
# GitHub's expressions: just enough to see a job that can't run for a factory PR or push.

class Unknown:
    def __repr__(self):
        return "UNKNOWN"


UNKNOWN = Unknown()
CONTEXT_KEYS = ("github.event_name", "github.ref", "github.ref_name", "github.head_ref", "github.base_ref",
                "github.event.pull_request.merged")
LITERALS = {"true": True, "false": False, "null": None}
TOKEN = re.compile(r"\s*(?:('(?:[^']|'')*')|(&&|\|\||==|!=|[(),])|([A-Za-z_][A-Za-z0-9_.-]*))")


class Unsupported(Exception):
    pass


def truth(value):
    return UNKNOWN if value is UNKNOWN else bool(value)


class Condition:
    """A tiny reader of an `if:` expression: the CONTEXT_KEYS compared with literals (== and !=, strings without
    regard to case, as GitHub compares them), startsWith, parentheses, && and ||. Anything else is Unsupported, and
    the whole condition then reads as "may run"."""

    def __init__(self, text, context):
        self.tokens, self.context, self.i = [], context, 0
        pos, text = 0, text.strip()
        while pos < len(text):
            m = TOKEN.match(text, pos)
            if not m or m.end() == pos:
                raise Unsupported(text[pos:])
            self.tokens.append(m.groups())
            pos = m.end()
            while pos < len(text) and text[pos].isspace():
                pos += 1

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else (None, None, None)

    def take(self, op):
        if self.peek()[1] != op:
            raise Unsupported(op)
        self.i += 1

    def parse(self):
        value = self.either()
        if self.i != len(self.tokens):
            raise Unsupported("trailing")
        return truth(value)

    def either(self):
        value = self.both()
        while self.peek()[1] == "||":
            self.i += 1
            right = truth(self.both())
            left = truth(value)
            value = True if True in (left, right) else UNKNOWN if UNKNOWN in (left, right) else False
        return value

    def both(self):
        value = self.compare()
        while self.peek()[1] == "&&":
            self.i += 1
            right = truth(self.compare())
            left = truth(value)
            value = False if False in (left, right) else UNKNOWN if UNKNOWN in (left, right) else True
        return value

    def compare(self):
        left = self.atom()
        op = self.peek()[1]
        if op not in ("==", "!="):
            return left
        self.i += 1
        right = self.atom()
        if UNKNOWN in (left, right):
            return UNKNOWN
        if isinstance(left, str) and isinstance(right, str):
            equal = left.lower() == right.lower()
        elif not isinstance(left, str) and not isinstance(right, str):
            equal = int(bool(left)) == int(bool(right))  # GitHub compares null, false and true as 0, 0 and 1
        else:
            return UNKNOWN
        return equal == (op == "==")

    def atom(self):
        string, op, name = self.peek()
        self.i += 1
        if string is not None:
            return string[1:-1].replace("''", "'")
        if op == "(":
            value = self.either()
            self.take(")")
            return value
        if name is not None and name.lower() == "startswith" and self.peek()[1] == "(":
            self.take("(")
            whole = self.atom()
            self.take(",")
            start = self.atom()
            self.take(")")
            if not isinstance(whole, str) or not isinstance(start, str):
                return UNKNOWN
            return whole.lower().startswith(start.lower())
        if name is not None and self.peek()[1] != "(":
            if name.lower() in LITERALS:
                return LITERALS[name.lower()]
            return self.context.get(name.lower(), UNKNOWN) if name.lower() in CONTEXT_KEYS else UNKNOWN
        raise Unsupported(name or op)


def condition(value, context):
    """An `if:` value under one event's context: True, False or UNKNOWN (may run)."""
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    text = str(value).strip()
    whole = re.fullmatch(r"\$\{\{(.*)\}\}", text, re.S)
    if whole:
        if "${{" in whole.group(1) or "}}" in whole.group(1):
            return UNKNOWN
        text = whole.group(1)
    elif "${{" in text:
        return UNKNOWN
    try:
        return Condition(text, context).parse()
    except Unsupported:
        return UNKNOWN


def contexts(event, default_branch, release_branch):
    """The github context a factory PR or push has under the event (an unknown default branch stays UNKNOWN). A PR's
    agent-written code is unreviewed only while it's unmerged: once merged, a closed PR's run is the base branch's."""
    default = default_branch if default_branch else UNKNOWN
    bases = [default] + ([release_branch] if release_branch else [])
    out = []
    for head in FACTORY_BRANCHES:
        if event in PR_EVENTS:
            out += [{"github.event_name": event, "github.ref": "refs/pull/1/merge", "github.ref_name": "1/merge",
                     "github.head_ref": head, "github.base_ref": base, "github.event.pull_request.merged": False}
                    for base in bases]
        elif event == "push":
            out.append({"github.event_name": event, "github.ref": f"refs/heads/{head}", "github.ref_name": head,
                        "github.head_ref": "", "github.base_ref": "", "github.event.pull_request.merged": None})
        elif event == "pull_request_target":
            out += [{"github.event_name": event, "github.ref": UNKNOWN if base is UNKNOWN else f"refs/heads/{base}",
                     "github.ref_name": base, "github.head_ref": head, "github.base_ref": base,
                     "github.event.pull_request.merged": False} for base in bases]
    if event == "merge_group":
        for base in bases:
            ref = UNKNOWN if base is UNKNOWN else f"gh-readonly-queue/{base}/pr-1-{'0' * 40}"
            out.append({"github.event_name": event, "github.ref": UNKNOWN if ref is UNKNOWN else f"refs/heads/{ref}",
                        "github.ref_name": ref, "github.head_ref": "", "github.base_ref": "",
                        "github.event.pull_request.merged": None})
    elif event == "workflow_run":
        out.append({"github.event_name": event, "github.ref": UNKNOWN if default is UNKNOWN else f"refs/heads/{default}",
                    "github.ref_name": default, "github.head_ref": "", "github.base_ref": "",
                    "github.event.pull_request.merged": None})
    return out


# ---------------------------------------------------------------------------------------------------------------
# Triggers.

def as_list(value):
    return [value] if isinstance(value, str) else list(value) if isinstance(value, list) else []


def triggers_of(workflow):
    # YAML 1.1 reads a bare `on` key as the boolean True.
    on = workflow.get("on", workflow.get(True))
    if isinstance(on, str):
        return {on: {}}
    if isinstance(on, list):
        return {str(e): {} for e in on}
    if isinstance(on, dict):
        return {str(k): (v if isinstance(v, (dict, list)) else {}) for k, v in on.items()}
    return {}


def glob_regex(pattern):
    """A GitHub branch filter pattern: * within a path segment, ** across them, ? and + on the character before."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out, i = out + ".*", i + 2
            continue
        c = pattern[i]
        if c == "*":
            out += "[^/]*"
        elif c in "?+" and out:
            out += c
        elif c == "[" and "]" in pattern[i + 1:]:
            j = pattern.index("]", i + 1)
            out, i = out + pattern[i:j + 1], j + 1
            continue
        else:
            out += re.escape(c)
        i += 1
    try:
        return re.compile(out)
    except re.error:
        return None


def filter_matches(patterns, name):
    """Patterns in order: a later !pattern undoes an earlier match. A pattern that can't be read matches (fails
    closed: the trigger may run)."""
    hit = False
    for pattern in patterns:
        pattern = str(pattern)
        negated = pattern.startswith("!")
        regex = glob_regex(pattern[1:] if negated else pattern)
        if regex is None or regex.fullmatch(name):
            hit = not negated
    return hit


def branch_filter(spec, name):
    if "branches" in spec:
        return filter_matches(as_list(spec["branches"]), name)
    if "branches-ignore" in spec:
        return not filter_matches(as_list(spec["branches-ignore"]), name)
    return True


def reaches_factory_prs(spec, default_branch, release_branch):
    """Whether a PR-type trigger's branch filter (on the PR's base) lets a factory PR through."""
    if not ("branches" in spec or "branches-ignore" in spec) or not default_branch:
        return True
    return any(branch_filter(spec, base) for base in [default_branch] + ([release_branch] if release_branch else []))


def reaches_factory_pushes(spec):
    """A push trigger with only tag filters runs for no branch; otherwise its branch filter decides."""
    if ("tags" in spec or "tags-ignore" in spec) and not ("branches" in spec or "branches-ignore" in spec):
        return False
    named = any("factory/" in str(p) and not str(p).startswith("!") for p in as_list(spec.get("branches")))
    return named or any(branch_filter(spec, b) for b in FACTORY_BRANCHES)


def filters_text(spec):
    if isinstance(spec, list):  # schedule
        return "cron: " + "; ".join(str(e.get("cron")) for e in spec if isinstance(e, dict))
    parts = []
    for key in ("branches", "branches-ignore", "tags", "tags-ignore", "paths", "paths-ignore", "types", "workflows"):
        if key in spec:
            parts.append(f"{key}: {', '.join(str(v) for v in as_list(spec[key]))}")
    return "; ".join(parts)


# ---------------------------------------------------------------------------------------------------------------
# Jobs.

def expr_body(value):
    """The body of a value that is exactly one ${{ }} expression, else None."""
    m = re.fullmatch(r"\s*\$\{\{\s*(.*?)\s*\}\}\s*", str(value), re.S)
    return m.group(1) if m and "${{" not in m.group(1) else None


def step_label(step, index, chain):
    run = str(step.get("run") or "").strip().splitlines()
    label = step.get("name") or step.get("id") or step.get("uses") or (f"run: {run[0]}" if run else f"#{index + 1}")
    return printable(label, 60) + (f" (in {chain[-1]})" if chain else "")


def expand(steps, notes, chain=()):
    """The job's steps as (step, label), each local composite action's steps after the step that uses it."""
    out = []
    for index, step in enumerate(steps if isinstance(steps, list) else []):
        if not isinstance(step, dict):
            continue
        out.append((step, step_label(step, index, chain)))
        uses = str(step.get("uses", ""))
        if not uses.startswith("./"):
            continue
        if uses in chain or len(chain) >= wp.LOCAL_ACTION_DEPTH:
            notes.append(f"local action {uses} uses itself or is nested too deep to read")
            continue
        action, why = wp.load_local_action(uses)
        if why:
            notes.append(f"local action {uses} {why}")
            continue
        out += expand(action["runs"]["steps"], notes, chain + (uses,))
    return out


def references(node, where, out, bare=False):
    """Every secret a value names, as (NAME, where); DYNAMIC for secrets[<expression>] or the whole context."""
    if isinstance(node, dict):
        for key, value in node.items():
            references(value, where, out, bare=key == "if")
    elif isinstance(node, list):
        for value in node:
            references(value, where, out)
    elif isinstance(node, str):
        texts = EXPRESSION.findall(node) or ([node] if bare else [])
        for text in texts:
            out += [(m.group(1).upper(), where) for m in SECRET_INDEXED.finditer(text)]
            # What's left, without its string literals: hashFiles('config/secrets.example') names no secret.
            rest = STRING_LITERAL.sub("''", SECRET_INDEXED.sub(" ", text))
            out += [(m.group(1).upper(), where) for m in SECRET_NAMED.finditer(rest)]
            if SECRET_DYNAMIC.search(rest):
                out.append((DYNAMIC, where))


def job_secrets(workflow, job, steps):
    found = []
    if "uses" not in job:  # a reusable workflow's call gets no workflow env
        references(workflow.get("env"), "workflow env", found)
    for key, value in job.items():
        if key == "steps":
            continue
        where = {"env": "job env", "if": "job if", "secrets": "secrets: to the called workflow",
                 "with": "with: to the called workflow"}.get(key, key)
        references(value, where, found, bare=key == "if")
    for step, label in steps:
        for key, value in step.items():
            references(value, f"step '{label}' {key}", found, bare=key == "if")
    merged = {}
    for name, where in found:
        if name:
            merged.setdefault(name, [])
            if where not in merged[name]:
                merged[name].append(where)
    return merged


def runner_of(job, settings):
    """{kind, labels, text}: kind is hosted, ci-tier, factory, self-hosted, unlisted (no label the policy lists as
    GitHub-hosted, and none every self-hosted runner carries), unknown or reusable."""
    if "uses" in job:
        return {"kind": "reusable", "labels": [], "text": "the called workflow's"}
    runs_on, group = job.get("runs-on"), None
    if isinstance(runs_on, dict):
        group, runs_on = runs_on.get("group"), runs_on.get("labels")
    labels = as_list(runs_on)
    alternatives = [labels]
    body = expr_body(runs_on) if isinstance(runs_on, str) else None
    matrix_key = re.fullmatch(r"matrix\.([A-Za-z0-9_-]+)", body or "")
    if matrix_key:
        matrix = (job.get("strategy") or {}).get("matrix") if isinstance(job.get("strategy"), dict) else None
        values = []
        if isinstance(matrix, dict):
            values = list(matrix.get(matrix_key.group(1)) or []) if isinstance(matrix.get(matrix_key.group(1)), list) else []
            values += [e[matrix_key.group(1)] for e in as_list(matrix.get("include"))
                       if isinstance(e, dict) and matrix_key.group(1) in e]
        alternatives = [as_list(v) for v in values] or [labels]
    kinds = []
    for alt in alternatives:
        alt = [str(label) for label in alt]
        if not alt or any("${{" in label for label in alt):
            kinds.append("unknown")
        elif settings["ci_label"] and settings["ci_label"] in alt:
            kinds.append("ci-tier")
        elif wp.hosted(alt):
            kinds.append("hosted")
        elif set(alt) & set(settings["factory_labels"]):
            kinds.append("factory")
        elif {label.lower() for label in alt} & wp.SELF_HOSTED_DEFAULTS:
            kinds.append("self-hosted")
        else:
            kinds.append("unlisted")  # an older hosted image, a larger runner or a self-hosted one's custom label
    order = ("unknown", "factory", "self-hosted", "unlisted", "ci-tier", "hosted")
    kind = min(kinds, key=order.index)
    shown = ", ".join(", ".join(str(x) for x in alt) for alt in alternatives) or "none"
    text = f"group {group}: {shown}" if group else shown
    if group and kind == "hosted":
        kind = "unknown"  # a runner group's labels don't say who runs it
    return {"kind": kind, "labels": [str(x) for alt in alternatives for x in alt], "text": text}


def permissions_of(workflow, job):
    """(value, where it comes from); value None when the repository's default decides."""
    if "permissions" in job:
        return job["permissions"], "job"
    if "permissions" in workflow:
        return workflow["permissions"], "workflow"
    return None, "the repository's default"


def read_only(value):
    if value == "read-all":
        return True
    if isinstance(value, dict):
        return all(str(v) in ("read", "none") for v in value.values())
    return False


def permissions_text(value):
    if isinstance(value, dict):
        return "{}" if not value else ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def checkout_fetch(step, event, repo):
    """(fetches agent-written code under the event, why)."""
    with_ = step.get("with") if isinstance(step.get("with"), dict) else {}
    ref, repository = with_.get("ref"), with_.get("repository")
    if repository not in (None, ""):
        body = expr_body(repository)
        if body is not None and HEAD_HINT.search(body):
            return True, f"repository {repository}: the PR's head"
        if not ((body or "").lower() == "github.repository" or (repo and str(repository).strip().lower() == repo.lower())):
            return False, f"another repository ({repository})"
    if ref in (None, ""):
        if event in BASE_EVENTS:
            return False, "ref unset: the base or default branch's commit"
        return True, "ref unset: the event's own commit"
    text = str(ref).strip()
    if "${{" not in text:
        branch = text[len("refs/heads/"):] if text.startswith("refs/heads/") else text
        return (True, f"ref {text}: a factory branch") if branch.startswith("factory/") else (False, f"ref {text}")
    body = expr_body(text)
    if body is not None:
        normal = body.lower().replace(" ", "")
        if normal in SAFE_REFS or (event in BASE_EVENTS and normal in BASE_RUN_REFS):
            return False, f"ref {text}"
        if HEAD_HINT.search(body):
            return True, f"ref {text}: the PR's head"
    return True, f"ref {text}: not provably the default or base branch"


def persist_false(step):
    with_ = step.get("with") if isinstance(step.get("with"), dict) else {}
    value = with_.get("persist-credentials")
    return value is False or str(value).strip().lower() == "false"


def checkout_record(step, label):
    with_ = step.get("with") if isinstance(step.get("with"), dict) else {}
    persist = "false" if persist_false(step) else printable(with_.get("persist-credentials", "unset (true)"), 80)
    return {"step": label, "repository": with_.get("repository"), "ref": with_.get("ref"),
            "persist_credentials": persist, "_step": step}


def environment_of(job):
    environment = job.get("environment")
    name = environment.get("name") if isinstance(environment, dict) else environment
    return None if name in (None, "") else str(name)


def container_of(job):
    container = job.get("container")
    if isinstance(container, dict):
        return str(container.get("image", "")) or "(no image)"
    return str(container) if container else None


def read_job(workflow, job_id, job, settings, notes):
    steps = expand(job.get("steps"), notes)
    value, source = permissions_of(workflow, job)
    uses = str(job.get("uses", "")) if "uses" in job else None
    secrets_in = job.get("secrets")
    return {
        "id": job_id,
        "name": printable(job.get("name") or job_id, 80),
        "uses": uses,
        "if": job.get("if"),
        "needs": [str(n) for n in as_list(job.get("needs"))],
        "runner": runner_of(job, settings),
        "container": container_of(job),
        "services": sorted(str(s) for s in (job.get("services") or {})) if isinstance(job.get("services"), dict) else [],
        "environment": environment_of(job),
        "permissions": {"value": value, "from": source, "text": "unset" if value is None and source != "job"
                        else permissions_text(value)},
        "checkouts": [checkout_record(step, label) for step, label in steps
                      if str(step.get("uses", "")).startswith("actions/checkout@")],
        "runs_fetch_pr": [label for step, label in steps if RUN_FETCHES_PR.search(str(step.get("run", "")))],
        "downloads": [label for step, label in steps if "/download-artifact@" in str(step.get("uses", ""))],
        "secret_refs": job_secrets(workflow, job, steps),
        "inherit": secrets_in == "inherit",
        "passes": sorted(str(k).upper() for k in secrets_in) if isinstance(secrets_in, dict) else [],
    }


# ---------------------------------------------------------------------------------------------------------------
# GitHub, through gh: names only.

def gh_names(gh, path, key):
    status, out, err = gh(["api", "--paginate", path, "--jq", f".{key}[].name"])
    if status != 0:
        raise GhError(printable((err or "").strip().splitlines()[0] if (err or "").strip() else f"gh exited {status}"))
    return sorted({line.strip() for line in out.splitlines() if line.strip()})


def gh_value(gh, path, jq):
    status, out, err = gh(["api", path, "--jq", jq])
    if status != 0:
        raise GhError(printable((err or "").strip().splitlines()[0] if (err or "").strip() else f"gh exited {status}"))
    return out.strip() or None


def read_github(repo, gh, environments):
    """What GitHub says, by name. A level gh couldn't read has an error, never an empty list."""
    out = {"checked": False, "why": None, "default_branch": None, "token_default": None, "levels": {},
           "environments": {}}
    if not repo:
        out["why"] = "no --repo"
        return out
    base = f"repos/{repo}"

    def level(path, key):
        try:
            return {"names": [n.upper() for n in gh_names(gh, path, key)]}
        except GhError as e:
            return {"error": str(e)}

    try:
        try:
            out["default_branch"] = gh_value(gh, base, ".default_branch")
        except GhError as e:
            out["why"] = f"gh couldn't read {repo}: {e}"
            return out
        out["checked"] = True
        try:
            out["token_default"] = gh_value(gh, f"{base}/actions/permissions/workflow", ".default_workflow_permissions")
        except GhError as e:
            out["token_default_error"] = str(e)
        out["levels"]["repository"] = level(f"{base}/actions/secrets", "secrets")
        out["levels"]["organization"] = level(f"{base}/actions/organization-secrets", "secrets")
        try:
            existing = {n.lower(): n for n in gh_names(gh, f"{base}/environments", "environments")}
        except GhError as e:
            existing = None
            out["environments_error"] = str(e)
        for name in sorted(environments):
            if existing is None:
                out["environments"][name] = {"exists": None, "error": out["environments_error"]}
            elif name.lower() not in existing:
                out["environments"][name] = {"exists": False, "names": []}
            else:
                quoted = urllib.parse.quote(existing[name.lower()], safe="")
                out["environments"][name] = {"exists": True, **level(f"{base}/environments/{quoted}/secrets", "secrets")}
        if existing:
            for lower, name in sorted(existing.items()):
                if not any(e.lower() == lower for e in out["environments"]):
                    quoted = urllib.parse.quote(name, safe="")
                    out["environments"][name] = {"exists": True, "referenced": False,
                                                 **level(f"{base}/environments/{quoted}/secrets", "secrets")}
    except FileNotFoundError:
        out.update(checked=False, why="gh isn't installed", levels={}, environments={})
    except subprocess.TimeoutExpired:
        out.update(checked=False, why="gh timed out", levels={}, environments={})
    return out


def resolve(name, environment, github):
    """(status, where): exists, missing, unknown or not checked, for a secret a job with this environment reads."""
    if not github["checked"]:
        return "not checked", github["why"]
    found, unread = [], []
    for level in ("repository", "organization"):
        entry = github["levels"].get(level, {"error": "not read"})
        if "error" in entry:
            unread.append(level)
        elif name in entry["names"]:
            found.append(level)
    if environment is not None:
        entry = next((v for k, v in github["environments"].items() if k.lower() == environment.lower()), None)
        if "${{" in environment or entry is None or "error" in entry:
            unread.append(f"environment {environment}")
        elif name in entry.get("names", []):
            found.append(f"environment {environment}")
    if found:
        return "exists", ", ".join(found)
    if unread:
        return "unknown", f"not in what was read; {', '.join(unread)} not checked"
    elsewhere = sorted(k for k, v in github["environments"].items() if name in v.get("names", []))
    if elsewhere:
        return "missing", f"only in environment {', '.join(elsewhere)}, which this job doesn't use"
    return "missing", "in none of: the repository's secrets, the organization secrets shared with it" + (
        f", environment {environment}" if environment else "")


# ---------------------------------------------------------------------------------------------------------------
# The audit.

def load_settings(factory_dir):
    """factory.json's runner labels, hosted labels, exemptions and release branch (workflow_policy.configure)."""
    path = pathlib.Path(factory_dir) / "factory.json"
    settings = {"factory_json": str(path), "found": path.is_file(), "ci_label": None, "factory_labels": [],
                "hosted_labels": [], "exemptions": {}, "release_branch": None, "policy_notes": []}
    if not settings["found"]:
        wp.HOSTED_EXTRA, wp.EXEMPTIONS, wp.CI_LABEL, wp.FACTORY_LABELS = frozenset(), {}, None, frozenset()
        return settings
    try:
        config = json.loads(path.read_text())
        settings["policy_notes"] = wp.configure(factory_dir)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise SetupError(f"{path}: {type(e).__name__}: {printable(e)}") from None
    settings.update(ci_label=wp.CI_LABEL, factory_labels=sorted(wp.FACTORY_LABELS), hosted_labels=sorted(wp.HOSTED_EXTRA),
                    exemptions={f"{w}/{j}": r for (w, j), r in wp.EXEMPTIONS.items()})
    release = (config.get("release") or {}).get("branch") if isinstance(config.get("release"), dict) else None
    settings["release_branch"] = release if isinstance(release, str) and release else None
    return settings


@contextlib.contextmanager
def policy_state():
    saved = {name: getattr(wp, name) for name in POLICY_GLOBALS}
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(wp, name, value)


def finding(report, level, rule, workflow, job, message):
    report["findings" if level == "finding" else "info"].append(
        {"rule": rule, "workflow": workflow, "job": job, "message": message})


def audit(workflows_dir, factory_dir=HERE, repo=None, runs=None, gh=run_gh, now=None):
    """The whole report as data. Raises SetupError."""
    if IMPORT_ERROR:
        raise SetupError(f"needs PyYAML ({IMPORT_ERROR})")
    root = pathlib.Path(workflows_dir)
    if not root.is_dir():
        raise SetupError(f"{root}: no such directory")
    with policy_state():
        resolved = root.resolve()
        wp.REPO_ROOT = resolved.parent.parent if resolved.parent.name == ".github" else None
        settings = load_settings(factory_dir)
        return _audit(root, settings, repo, runs, gh, now)


def _audit(root, settings, repo, runs, gh, now):
    report = {"workflows_dir": str(root), "repo": repo, "settings": settings, "workflows": [], "findings": [],
              "info": [], "secrets": [], "schedules": []}
    files = sorted([*root.glob("*.yml"), *root.glob("*.yaml")])
    workflows = {}
    for path in files:
        entry = {"file": path.name, "name": None, "factory": path.name.startswith("factory-"), "error": None,
                 "triggers": [], "jobs": [], "cron": []}
        report["workflows"].append(entry)
        try:
            data = yaml.safe_load(path.read_text())
        except (yaml.YAMLError, OSError, UnicodeDecodeError) as e:
            entry["error"] = printable(e, 300)
        else:
            if not isinstance(data, dict) or not isinstance(data.get("jobs"), dict):
                entry["error"] = "not a workflow: no jobs mapping"
            else:
                workflows[path.name] = (entry, data)
        if entry["error"]:
            finding(report, "finding", "unreadable", path.name, None,
                    f"doesn't parse ({entry['error']}): GitHub won't run it, and this audit can't read it")

    # Static reading: triggers and jobs.
    for file, (entry, data) in workflows.items():
        entry["name"] = printable(data.get("name"), 80) if data.get("name") else None
        entry["_triggers"] = triggers_of(data)
        entry["cron"] = [str(e.get("cron")) for e in as_list(entry["_triggers"].get("schedule"))
                         if isinstance(e, dict) and e.get("cron")]
        call = entry["_triggers"].get("workflow_call")
        declared = (call or {}).get("secrets") if isinstance(call, dict) else None
        entry["declared_secrets"] = sorted(str(k).upper() for k in declared) if isinstance(declared, dict) else []
        for job_id, job in data["jobs"].items():
            if not isinstance(job, dict):
                continue
            notes = []
            record = read_job(data, str(job_id), job, settings, notes)
            entry["jobs"].append(record)
            for note in notes:
                finding(report, "info", "local-action", file, record["id"], note)

    environments = {j["environment"] for e, _ in workflows.values() for j in e["jobs"]
                    if j["environment"] and "${{" not in j["environment"]}
    github = read_github(repo, gh, environments)
    report["github"] = github
    default_branch, release = github["default_branch"], settings["release_branch"]

    # Which events can carry agent-written code into each workflow.
    by_name = {}
    for file, (entry, data) in workflows.items():
        by_name.setdefault(data.get("name") or f".github/workflows/{file}", file)
    direct, carries = {}, {}
    for file, (entry, data) in workflows.items():
        direct[file] = set()
        for event, spec in entry["_triggers"].items():
            spec_d = spec if isinstance(spec, dict) else {}
            if event in PR_EVENTS + ("merge_group",) and reaches_factory_prs(spec_d, default_branch, release):
                direct[file].add(event)
            elif event == "push" and reaches_factory_pushes(spec_d):
                direct[file].add(event)
        carries[file] = bool(direct[file])
    events = {file: set(direct[file]) for file in workflows}
    for file, (entry, data) in workflows.items():
        for event, spec in entry["_triggers"].items():
            spec_d = spec if isinstance(spec, dict) else {}
            if event == "pull_request_target":
                events[file].add(event)
            elif event == "workflow_run":
                targets = [str(w) for w in as_list(spec_d.get("workflows"))]
                known = [by_name[t] for t in targets if t in by_name]
                if any(carries.get(t) for t in known):
                    events[file].add(event)
                for t in targets:
                    if t not in by_name:
                        finding(report, "info", "workflow-run", file, None,
                                f"workflow_run names {t!r}, which no workflow here is called")

    own = {file: set(events[file]) for file in workflows}
    for file, (entry, data) in workflows.items():
        entry["own_events"] = sorted(own[file])

    # Reusable workflows run under their callers' events, through the calling job: to a fixed point.
    callers = {file: [] for file in workflows}
    for _ in range(len(workflows) + 2):
        changed = False
        for file, (entry, data) in workflows.items():
            cleared = clearing(entry, events[file], default_branch, release)
            for job in entry["jobs"]:
                callee = local_callee(job)
                if callee not in workflows:
                    continue
                run_under = events[file] - set(cleared.get(job["id"], {}))
                if (file, job["id"]) not in [(c["workflow"], c["job"]) for c in callers[callee]]:
                    callers[callee].append({"workflow": file, "job": job["id"], "inherit": job["inherit"],
                                            "passes": job["passes"], "token": job["permissions"]})
                if run_under - events[callee]:
                    events[callee] |= run_under
                    changed = True
        if not changed:
            break

    # Each workflow's triggers, as reported.
    for file, (entry, data) in workflows.items():
        for event, spec in entry["_triggers"].items():
            spec_d = spec if isinstance(spec, dict) else {}
            if event in direct[file]:
                agent = "factory pushes" if event == "push" else "yes"
            elif event in PR_EVENTS + ("merge_group",):
                agent = "no: its branch filter excludes factory PRs' bases"
            elif event == "pull_request_target":
                agent = "if a job checks out the PR's head"
            elif event == "workflow_run":
                agent = ("if a job checks out the triggering run's head" if "workflow_run" in events[file]
                         else "no: the workflows it follows don't run for factory PRs or pushes")
            elif event == "workflow_call":
                via = sorted((events[file] - own[file]) & set(AGENT_EVENTS))
                agent = (f"through its callers ({', '.join(via)})" if via else
                         "no: its callers here don't run for factory PRs or pushes" if callers[file] else
                         "no caller here (one in another repository isn't read)")
            else:
                agent = "no"
            entry["triggers"].append({"event": event, "agent_code": agent, "copy": COPY.get(event, UNCLASSIFIED),
                                      "filters": filters_text(spec)})

    # Per job: the events that reach it, whether it fetches agent-written code, and its secrets.
    secret_uses = {}
    for file, (entry, data) in workflows.items():
        cleared = clearing(entry, events[file], default_branch, release)
        call_secrets = passed_secrets(entry, callers[file])
        for job in entry["jobs"]:
            job["cleared"] = cleared.get(job["id"], {})
            job["agent_events"] = sorted(events[file] - set(job["cleared"]))
            job["agent_code"], job["agent_code_why"] = fetches(job, job["agent_events"], repo)
            job["token"] = token_of(job, entry, callers[file], github)
            job["secrets"] = []
            for name, where in sorted(job["secret_refs"].items()):
                status, detail = secret_status(name, job, entry, call_secrets, github)
                job["secrets"].append({"name": name, "where": where, "status": status, "detail": detail})
                if status not in ("built in", "dynamic"):
                    secret_uses.setdefault(name, []).append((f"{file}/{job['id']}", job["environment"]))
                if status == "missing" and entry["factory"]:
                    # The factory's templates reference optional slots (FACTORY_SVC_2..4, a planning database's
                    # password, Context7) that read as empty by design; bootstrap.py checks the ones it needs.
                    finding(report, "info", "missing", file, job["id"],
                            f"references secret {name} ({'; '.join(where)}), which is {detail}: it reads as empty, "
                            "which a factory workflow allows for an optional slot (bootstrap.py checks the ones the "
                            "factory needs)")
                elif status == "missing":
                    finding(report, "finding", "missing", file, job["id"],
                            f"references secret {name} ({'; '.join(where)}), which is {detail}: it reads as empty")
    for _ in range(len(workflows) + 2):
        changed = False
        for file, (entry, data) in workflows.items():
            for job in entry["jobs"]:
                callee = local_callee(job)
                if job["agent_code"] or callee not in workflows or not job["agent_events"]:
                    continue
                if any(j["agent_code"] for j in workflows[callee][0]["jobs"]):
                    job["agent_code"], changed = True, True
                    job["agent_code_why"].append(f"its called workflow {callee} fetches agent-written code")
        if not changed:
            break
    for file, (entry, data) in workflows.items():
        for job in entry["jobs"]:
            rules(report, file, entry, job, callers[file], settings, github)

    # Secrets on GitHub that nothing references.
    report["secrets"] = secrets_table(github, secret_uses)
    dynamic = any(s["name"] == DYNAMIC for e, _ in workflows.values() for j in e["jobs"] for s in j["secrets"]) or any(
        j["inherit"] and j["uses"] and not j["uses"].startswith("./") for e, _ in workflows.values() for j in e["jobs"])
    for row in report["secrets"]:
        if not row["referenced_by"]:
            caveat = " (a job here reads secrets by a name this audit can't see, so it may)" if dynamic else ""
            finding(report, "info", "unused-secret", None, None,
                    f"{row['level']} secret {row['name']} exists, but no workflow here references it{caveat}")
    for name, entry in sorted(github["environments"].items()):
        if entry.get("exists") is False:
            finding(report, "info", "environment", None, None,
                    f"environment {name} is referenced but doesn't exist: the first run creates it, with no protection "
                    "rules and no secrets")
    for note in settings["policy_notes"]:
        finding(report, "info", "factory-json", None, None, note)
    factory_files = sorted(f for f in workflows if workflows[f][0]["factory"])
    if factory_files:
        finding(report, "info", "factory-workflows", None, None,
                f"{len(factory_files)} factory workflows ({', '.join(factory_files)}): workflow_policy.py holds them to "
                "an agent job's rules, so step 10's findings here skip them (their secrets are still checked)")

    if runs:
        report["schedules"] = schedules(workflows, repo, runs, gh, now)
    for entry in report["workflows"]:
        entry.pop("_triggers", None)
        for job in entry["jobs"]:
            for checkout in job["checkouts"]:
                checkout.pop("_step", None)
            job.pop("secret_refs", None)
    report["findings"].sort(key=lambda f: (f["workflow"] or "", f["job"] or "", f["rule"]))
    report["summary"] = summary(report)
    return report


def local_callee(job):
    uses = job.get("uses") or ""
    m = re.fullmatch(r"\./\.github/workflows/([^/@]+\.ya?ml)", uses)
    return m.group(1) if m else None


def clearing(entry, events, default_branch, release):
    """{job id: {event: why it can't run under that event}} for the agent events."""
    jobs = {j["id"]: j for j in entry["jobs"]}
    memo = {}

    def cleared(job_id, event, seen):
        if (job_id, event) in memo:
            return memo[(job_id, event)]
        job = jobs[job_id]
        why = None
        ctxs = contexts(event, default_branch, release)
        if ctxs and job["if"] is not None and all(condition(job["if"], c) is False for c in ctxs):
            why = f"its if: {printable(job['if'], 160)}"
        elif not CONTINUES.search(str(job["if"] or "")):
            for need in job["needs"]:
                if need in jobs and need not in seen and cleared(need, event, seen | {job_id}):
                    why = f"it needs {need}, which doesn't run"
                    break
        memo[(job_id, event)] = why
        return why

    out = {}
    for job_id in jobs:
        for event in sorted(set(events) & set(AGENT_EVENTS)):
            why = cleared(job_id, event, frozenset())
            if why:
                out.setdefault(job_id, {})[event] = why
    return out


def fetches(job, agent_events, repo):
    """(whether the job fetches agent-written code under any event that reaches it, why)."""
    why = []
    for event in agent_events:
        for checkout in job["checkouts"]:
            fetched, reason = checkout_fetch(checkout["_step"], event, repo)
            if fetched:
                why.append(f"{event}: step '{checkout['step']}' {reason}")
        for label in job["runs_fetch_pr"]:
            why.append(f"{event}: step '{label}' fetches a PR")
    return bool(why), why


def passed_secrets(entry, callers):
    """For a reusable workflow: "inherit" if a local caller passes every secret, else the names they pass."""
    if any(c["inherit"] for c in callers):
        return "inherit"
    return sorted({name for c in callers for name in c["passes"]})


def secret_status(name, job, entry, call_secrets, github):
    if name == BUILT_IN:
        return "built in", "the job's own token"
    if name == DYNAMIC:
        return "dynamic", "a secret by a name this audit can't read, or every secret"
    if "workflow_call" in [t["event"] for t in entry["triggers"]] and name in entry["declared_secrets"] \
            and call_secrets != "inherit":
        return "passed", "a workflow_call secret: its caller passes it"
    return resolve(name, job["environment"], github)


def token_of(job, entry, callers, github):
    """{read_only: True/False, text}: the job's token, a reusable workflow's capped by its callers'."""
    value, source = job["permissions"]["value"], job["permissions"]["from"]
    if source == "the repository's default" and callers:
        caller_tokens = [c["token"] for c in callers]
        if all(t["from"] != "the repository's default" for t in caller_tokens):
            ok = all(read_only(t["value"]) for t in caller_tokens)
            return {"read_only": ok, "text": "the caller's: " + "; ".join(t["text"] for t in caller_tokens),
                    "default": False}
    if source == "the repository's default":
        default = github.get("token_default")
        if default == "read":
            return {"read_only": True, "text": "the repository's default (read)", "default": True}
        if default == "write":
            return {"read_only": False, "text": "the repository's default (read and write)", "default": True}
        return {"read_only": False, "text": "the repository's default (not read)", "default": True}
    return {"read_only": read_only(value), "text": f"{permissions_text(value)} ({source})", "default": False}


def rules(report, file, entry, job, callers, settings, github):
    """Step 10's rules for a job that runs agent-written code, and pull_request_target's head checkout."""
    if entry["factory"]:
        return
    job_id = job["id"]
    if "pull_request_target" in job["agent_events"]:
        for checkout in job["checkouts"]:
            fetched, reason = checkout_fetch(checkout["_step"], "pull_request_target", report["repo"])
            if fetched:
                finding(report, "finding", "head", file, job_id,
                        f"pull_request_target runs with the base's secrets and token, and step '{checkout['step']}' "
                        f"checks out the PR's head ({reason}): run the PR's code under pull_request instead")
        for label in job["runs_fetch_pr"]:
            finding(report, "finding", "head", file, job_id,
                    f"pull_request_target runs with the base's secrets and token, and step '{label}' fetches the PR")
    if job["downloads"] and job["agent_events"]:
        finding(report, "info", "artifacts", file, job_id,
                f"downloads artifacts ({', '.join(job['downloads'])}) under {', '.join(job['agent_events'])}: they may "
                "be built from a PR's code, so a job that runs them is held to step 10 too")
    if job["uses"] and not job["uses"].startswith("./") and job["agent_events"]:
        passes = "every secret (secrets: inherit)" if job["inherit"] else ", ".join(job["passes"])
        level = "finding" if passes and set(job["agent_events"]) & set(OWN_COMMIT_EVENTS) else "info"
        finding(report, level, "remote-call", file, job_id,
                f"calls {job['uses']} under {', '.join(job['agent_events'])}"
                + (f" and passes it {passes}" if passes else "") + ": this audit can't read another repository's "
                "workflow, so check it doesn't build the PR's code" + (" with them" if passes else ""))
    if not job["agent_code"]:
        return
    events = ", ".join(job["agent_events"])
    # Only through its callers: the secrets they pass are all it has.
    in_callee = bool(callers) and not set(job["agent_events"]) & set(entry["own_events"])
    call_secrets = passed_secrets(entry, callers) if in_callee else None
    # A call job's secrets are judged in the workflow it calls (or by remote-call).
    for secret in [] if job["uses"] else job["secrets"]:
        name = secret["name"]
        if secret["status"] == "built in":
            continue
        if in_callee and call_secrets != "inherit" and name != DYNAMIC and name not in call_secrets:
            continue  # its callers don't pass it: it reads as empty
        what = "every secret, or one by a name this audit can't read" if name == DYNAMIC else f"secret {name}"
        finding(report, "finding", "secret", file, job_id,
                f"{what} ({'; '.join(secret['where'])}) in a job that runs agent-written code ({events}): no secret "
                "belongs in it, before or after the PR's code runs. A job that needs one runs the default branch's "
                "code, as the fixtures job does")
    if job["uses"] and job["inherit"] and local_callee(job):
        finding(report, "finding", "secret", file, job_id,
                f"passes every secret (secrets: inherit) to {job['uses']}, which runs agent-written code ({events})")
    for checkout in job["checkouts"]:
        if checkout["persist_credentials"] != "false":
            finding(report, "finding", "checkout", file, job_id,
                    f"step '{checkout['step']}' checks out without persist-credentials: false "
                    f"({checkout['persist_credentials']}): the job's token stays in .git/config for the PR's code")
    token = job["token"]
    if not job["uses"]:
        if token["read_only"] and token["default"]:
            finding(report, "info", "token", file, job_id,
                    "its token is read-only by the repository's default: a permissions block keeps it so if the "
                    "setting changes")
        elif not token["read_only"]:
            finding(report, "finding", "token", file, job_id,
                    f"its token isn't read-only ({token['text']}) in a job that runs agent-written code ({events}): "
                    "set permissions with read scopes only (contents: read)")
    kind = job["runner"]["kind"]
    exemption = settings["exemptions"].get(f"{file}/{job_id}")
    if kind in ("self-hosted", "unlisted") and exemption:
        finding(report, "info", "runner", file, job_id,
                f"self-hosted without the factory container, exempted in factory.json: {exemption}")
    elif kind in ("self-hosted", "unlisted") and job["container"]:
        finding(report, "info", "runner", file, job_id,
                f"self-hosted in container {job['container']}: workflow_policy.py holds it to the factory's options")
    elif kind == "unlisted":
        finding(report, "finding", "runner", file, job_id,
                f"runs agent-written code on {job['runner']['text']}, which the policy doesn't list as GitHub-hosted: "
                "if it's the organization's own hosted (larger) runner, add it to factory.json policy.hosted_labels; "
                f"if it's self-hosted, it needs a container or the CI tier ({settings['ci_label'] or 'runners.ci'})")
    elif kind == "self-hosted":
        finding(report, "finding", "runner", file, job_id,
                f"runs agent-written code on a self-hosted runner ({job['runner']['text']}) outside a container and "
                f"off the CI tier ({settings['ci_label'] or 'runners.ci: no factory.json read'})")
    elif kind == "factory":
        finding(report, "finding", "runner", file, job_id,
                f"runs on the factory's own runners ({job['runner']['text']}): a project's CI job runs hosted or on "
                f"the CI tier ({settings['ci_label']})")
    elif kind == "unknown":
        finding(report, "finding", "runner", file, job_id,
                f"its runner can't be read here ({job['runner']['text']}): check it's GitHub-hosted or the CI tier")


def secrets_table(github, uses):
    """Each secret on GitHub and the jobs that reference it: an environment's, only jobs that use the environment."""
    rows = []
    for level in ("repository", "organization"):
        for name in github["levels"].get(level, {}).get("names", []):
            rows.append({"level": level, "name": name, "referenced_by": sorted({j for j, _ in uses.get(name, [])})})
    for env, entry in sorted(github["environments"].items()):
        for name in entry.get("names", []):
            jobs = sorted({j for j, e in uses.get(name, []) if e and e.lower() == env.lower()})
            rows.append({"level": f"environment {env}", "name": name, "referenced_by": jobs})
    return rows


def parse_time(text):
    return datetime.datetime.fromisoformat(str(text).replace("Z", "+00:00"))


def duration(minutes):
    days, rest = divmod(int(round(minutes)), 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days}d{hours}h{mins:02d}m"
    return f"{hours}h{mins:02d}m" if hours else f"{mins}m"


def schedules(workflows, repo, n, gh, now):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    out = []
    for file, (entry, data) in workflows.items():
        if not entry["cron"]:
            continue
        row = {"workflow": file, "cron": entry["cron"], "checked": False, "runs": [], "gaps_minutes": []}
        try:
            status, stdout, err = gh(["run", "list", "--repo", repo, "--workflow", file, "--event", "schedule",
                                      "--limit", str(n), "--json", "createdAt"])
            if status != 0:
                raise GhError(printable((err or "").strip() or f"gh exited {status}"))
            times = sorted(parse_time(r["createdAt"]) for r in json.loads(stdout or "[]"))
        except FileNotFoundError:
            row["why"] = "gh isn't installed"
        except (GhError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as e:
            row["why"] = f"gh couldn't list its runs: {printable(e)}"
        else:
            row["checked"] = True
            row["runs"] = [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in times]
            row["gaps_minutes"] = [round((b - a).total_seconds() / 60, 1) for a, b in zip(times, times[1:])]
            if times:
                row["since_last_minutes"] = round((now - times[-1]).total_seconds() / 60, 1)
        out.append(row)
    return out


def summary(report):
    jobs = [j for w in report["workflows"] for j in w["jobs"]]
    agent = [j for j in jobs if j.get("agent_code")]
    github = report.get("github") or {}
    if github.get("checked"):
        unread = [k for k, v in github["levels"].items() if "error" in v]
        existence = f"checked on {report['repo']}" + (f" ({', '.join(unread)} not readable)" if unread else "")
    else:
        existence = f"not checked ({github.get('why') or 'no --repo'})"
    return (f"ci audit: {len(report['workflows'])} workflows, {len(jobs)} jobs ({len(agent)} run agent-written code), "
            f"{len(report['findings'])} findings, {len(report['info'])} info; secrets' existence {existence}")


# ---------------------------------------------------------------------------------------------------------------
# Output.

def table(headers, rows, indent="    "):
    rows = [[printable(c, 200) for c in r] for r in rows]
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]
    line = lambda cells: (indent + "  ".join(c.ljust(w) for c, w in zip(cells, widths))).rstrip()  # noqa: E731
    return [line(headers)] + [line(r) for r in rows]


def job_agent_text(job):
    if job.get("agent_code"):
        return "yes (" + ", ".join(job["agent_events"]) + ")"
    if job.get("cleared") and not job["agent_events"]:
        return "no, by " + "; ".join(sorted(set(job["cleared"].values())))
    if job["agent_events"]:
        return "no checkout of it (" + ", ".join(job["agent_events"]) + ")"
    return "no"


def render(report):
    s = report["settings"]
    github = report["github"]
    out = [f"CI audit of {report['workflows_dir']}: {len(report['workflows'])} workflows (Enablement step 10)"]
    if github["checked"]:
        out.append(f"  repository {report['repo']}: default branch {github['default_branch']}, token default "
                   f"{github['token_default'] or 'not readable'}")
    else:
        out.append(f"  secrets' existence, the default branch and the token's default: not checked "
                   f"({github['why']})")
    if s["found"]:
        out.append(f"  factory.json: CI tier label {s['ci_label'] or 'none'}, hosted labels "
                   f"{', '.join(s['hosted_labels']) or 'none'}, release branch {s['release_branch'] or 'none'}")
    else:
        out.append(f"  factory.json not found ({s['factory_json']}): CI tier label unknown, no extra hosted labels")
    for w in report["workflows"]:
        out.append("")
        out.append(f"== {w['file']}" + (f" ({w['name']})" if w["name"] else "")
                   + ("  [factory workflow: workflow_policy.py]" if w["factory"] else ""))
        if w["error"]:
            out.append(f"    doesn't parse: {w['error']}")
            continue
        out.append("  triggers")
        out += table(["EVENT", "AGENT-WRITTEN CODE", "RUNS THE WORKFLOW FROM", "FILTERS"],
                     [[t["event"], t["agent_code"], t["copy"], t["filters"]] for t in w["triggers"]])
        out.append("  jobs")
        out += table(["JOB", "AGENT-WRITTEN CODE", "RUNNER", "CONTAINER", "ENVIRONMENT", "TOKEN"],
                     [[j["id"], job_agent_text(j),
                       f"{j['runner']['kind']}: {j['runner']['text']}" if not j["uses"] else f"calls {j['uses']}",
                       j["container"] or "-", j["environment"] or "-", j["token"]["text"]] for j in w["jobs"]])
        checkouts = [[j["id"], c["step"], c["persist_credentials"], c["ref"] if c["ref"] is not None else "unset",
                      c["repository"] or "-"] for j in w["jobs"] for c in j["checkouts"]]
        if checkouts:
            out.append("  checkouts")
            out += table(["JOB", "STEP", "PERSIST-CREDENTIALS", "REF", "REPOSITORY"], checkouts)
        secrets = [[j["id"], x["name"], "; ".join(x["where"]), f"{x['status']}: {x['detail']}"]
                   for j in w["jobs"] for x in j["secrets"]]
        inherit = [[j["id"], "(all)", "secrets: inherit", "passes every secret"] for j in w["jobs"] if j["inherit"]]
        if secrets or inherit:
            out.append("  secrets")
            out += table(["JOB", "SECRET", "WHERE", "EXISTS"], secrets + inherit)
    if report["secrets"]:
        out.append("")
        out.append(f"== secrets on GitHub ({report['repo']}), names only")
        out += table(["LEVEL", "NAME", "REFERENCED BY"],
                     [[r["level"], r["name"], ", ".join(r["referenced_by"]) or "nothing"] for r in report["secrets"]])
    if github["checked"]:
        unread = [f"{k}: {v['error']}" for k, v in github["levels"].items() if "error" in v]
        unread += [f"environment {k}: {v['error']}" for k, v in github["environments"].items() if "error" in v]
        for line in unread:
            out.append(f"    not checked: {line}")
    if report["schedules"]:
        out.append("")
        out.append("== scheduled runs (GitHub starts them late or not at all: design an alarm on the gaps)")
        rows = []
        for r in report["schedules"]:
            gaps = r["gaps_minutes"]
            if not r["checked"]:
                rows.append([r["workflow"], "; ".join(r["cron"]), "-", f"not checked: {r['why']}", "-"])
            elif len(gaps) < 1:
                rows.append([r["workflow"], "; ".join(r["cron"]), str(len(r["runs"])), "too few runs for a gap",
                             duration(r["since_last_minutes"]) if "since_last_minutes" in r else "never"])
            else:
                rows.append([r["workflow"], "; ".join(r["cron"]), str(len(r["runs"])),
                             f"{duration(min(gaps))} / {duration(statistics.median(gaps))} / {duration(max(gaps))}",
                             duration(r["since_last_minutes"])])
        out += table(["WORKFLOW", "CRON", "RUNS", "GAP MIN / MEDIAN / MAX", "SINCE THE LAST"], rows)
    for title, items in (("findings", report["findings"]), ("info", report["info"])):
        out.append("")
        out.append(f"== {title} ({len(items)})")
        for f in items:
            where = " / ".join(x for x in (f["workflow"], f["job"]) if x)
            out.append(f"  [{f['rule']}] " + (f"{where}: " if where else "") + f["message"])
    out.append("")
    out.append(report["summary"])
    return "\n".join(out)


def main(argv=None, gh=run_gh):
    parser = argparse.ArgumentParser(prog="ci_audit.py", description="Read the project's CI against Enablement "
                                     "step 10 (report only).")
    parser.add_argument("workflows", nargs="?", default=".github/workflows")
    parser.add_argument("--factory-dir", default=str(HERE))
    parser.add_argument("--repo")
    parser.add_argument("--runs", type=int)
    parser.add_argument("--json", action="store_true")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if args.repo is not None and not REPO.match(args.repo):
        print(f"ci_audit: --repo {args.repo!r} isn't owner/name", file=sys.stderr)
        return 2
    if args.runs is not None and (args.runs < 2 or not args.repo):
        print("ci_audit: --runs N takes 2 or more runs and needs --repo", file=sys.stderr)
        return 2
    try:
        report = audit(args.workflows, args.factory_dir, args.repo, args.runs, gh)
    except SetupError as e:
        print(f"ci_audit: {e}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, default=str) if args.json else render(report))
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
