"""Check every workflow against the factory's binding rules (D1 stage contract, D2 credential
boundary). Run by ci.yml on every PR and push to main.

Usage: python3 workflow_policy.py <workflows-dir> [<factory-dir>]
       (factory-dir defaults to <workflows-dir>/../factory, where the *-tools.args files live)

This is a drift check, not the security boundary. It catches a workflow edit that weakens an
agent job by mistake. A workflow is a program (expressions, $GITHUB_ENV writes, other actions), so
no static check is complete against someone editing workflows on purpose. The boundary is
CODEOWNERS review of .github/ (enforced by the main ruleset), the Claude App having no `workflows`
permission, and the runtime sandbox probe (factory-smoke). The factory's design rules say what
this leaves open (z-sdlc process/factory.md, D2).

Allowlists, not blocklists:
- Runners: only exact GitHub-hosted labels count as hosted, plus the organization's own hosted
  (larger) runner labels factory.json's policy.hosted_labels lists (never a label every self-hosted
  runner carries, nor a factory runner's). A listed label counts as hosted wherever the policy asks:
  the container rule, the App key's job and the fixtures job. Any other job needs a container
  whose only options are the factory seccomp profile and systempaths=unconfined, with no volumes, no
  service containers, no docker:// steps and no docker CLI, unless policy.self_hosted_exemptions
  names it: one of the project's own CI jobs (never in a factory workflow, on the factory's runners
  or running an agent), by workflow and job, with a written reason. An exemption lifts only that
  container rule; the secret rules below hold in every job. An exemption that names no job, or a
  job that doesn't need it, is a violation, so the list stays exact.
- Actions: a local action (`uses: ./...`) is scanned: a composite action's steps are checked as the
  calling job's own, nested local actions included. One that can't be scanned (a docker or
  JavaScript action, a path with no action.yml or outside the repository, one that uses itself) is
  refused, as is an agent step inside one, any local action in an agent job, and any action naming
  claude other than `anthropics/claude-code-action@`.
- Agent steps (`anthropics/claude-code-action@`): only allowlisted inputs. claude_code_oauth_token is
  the OAuth secret, github_token the job's own token, settings a frozen settings file. claude_args
  is parsed the way the action parses it: each flag at most once, from an allowlist, with its value
  checked; printable ASCII only (the action splits words on a non-breaking space, shlex doesn't);
  exactly one ${{ env.FACTORY_TOOL_ARGS }}; --model a literal model ID or a choice input of model
  IDs; --setting-sources user or user,project, and project only with a checkout pinned to the
  default branch.
- Agent jobs: exactly one checkout, of this repository into the workspace, without persisted
  credentials, and `git remote remove origin` before the agent step (the action would write the
  job token into origin's URL).
- Bash: a tool policy that grants Bash (or sets no --tools, which grants every tool) needs the
  sandbox: a frozen --settings file also passed as the settings input, CLAUDE_CODE_SUBPROCESS_ENV_SCRUB
  set to 1, and the factory container options.
- Agent jobs: an explicit read-only permissions block; the tool policy set only by
  `tr ... < .github/factory/*-tools.args`; no env (workflow, job or agent step) that sets
  FACTORY_TOOL_ARGS, an Anthropic variable or a token, or references any secret but CONTEXT7_API_KEY.
  The services' credential slots are the exception, in an agent step whose job builds its settings with
  services.py: FACTORY_SVC_1..4 in a planning job only, FACTORY_EXEC_SVC_1..2 in an implement or
  revise job only, each exactly its own secret (process/factory.md, D2 rule 8 and D3 rule 4).
- The OAuth secret appears only as an agent step's claude_code_oauth_token, or in the step env of
  a run step in an agent job (the probes and scans that compare against it).
- The factory App's key appears only as the private-key input of actions/create-github-app-token,
  in a job on a GitHub-hosted runner that uses the writer environment and runs no agent.
- No run step starts Claude Code or the Agent SDK directly.
- Agent jobs set CLAUDE_CODE_DISABLE_BACKGROUND_TASKS: "1" (headless runs dispatch in the foreground).
- Runner tiers (design rule D3): only the planning workflows (PLANNING_WORKFLOWS) run on the
  planning runners, and their agent jobs must; only jobs there may use the planning
  environment, which holds the read-only database password. The one exception is the planning
  stages' sandbox probe (PLANNING_PROBES: factory-smoke.yml's planning-sandbox job, D2 rule 5),
  which runs in their tier and job setup, service credential slots included. Only that job may
  judge its probe by the planning tier's open internet (sandbox_check.py's `open`): every other
  sandbox probe is held to the allowlist.
- Production tier (design rule D4): only factory-gate.yml's `execute` job runs on the production
  runner. It runs on the host with no container (it only talks to the root broker's socket), so the
  container rule doesn't apply; instead it has the production environment (CD's approval), exactly
  read-only permissions, no `uses:` steps, no secrets and no agent. The production environment is
  for that job only (CD gates run through it too). factory-gate.yml has no agent job.
- CI tier (factory.json's runners.ci, host/setup.sh TIER=ci): a project's own CI jobs that must run
  self-hosted, pull requests' code included, each in a disposable runner container (ci_launcher.py).
  A job on its label runs in that container, so it names no container or service containers and no
  docker:// step (the container rule above doesn't apply to it). It is in one of the project's own
  workflows (never a factory-*.yml), runs no agent, has explicit read-only permissions, checks out
  without persisted credentials, and holds no secret and no job token.
- Fixtures (design rule D2 rule 7): a factory workflow's job named `fixtures` is in the implement or
  revise workflow and runs on a GitHub-hosted runner with no agent, container, environment or
  outputs, permissions exactly contents: read, one checkout of the default branch without persisted
  credentials, and only the checkout, cache and upload-artifact actions. Its one secret is
  ${{ secrets['NAME'] }} in a run step's FIXTURE_SECRET, and no other job or workflow env references
  that secret. factory.json's fixtures values, which render into the workflow text, hold no
  expression and no character that would break it.
- Job conditions: in a factory workflow, a job after one whose `if` has a status function (always(),
  !cancelled(): it runs past a skipped or failed job) has one in its own `if` too. Without one GitHub adds
  success(), which reads every job before it, not just those it needs, so it is skipped whenever an earlier
  job carried on (factory-revise.yml's stop-at-gate after a skipped fixtures job, 2026-10-20). Not a boundary:
  a job skipped this way leaves a stage stopped. A project's own workflows are its own.
"""

import json
import pathlib
import re
import shlex
import sys

import yaml

ACTION = "anthropics/claude-code-action@"
HOSTED = {
    "ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04", "ubuntu-24.04-arm", "ubuntu-22.04-arm",
    "windows-latest", "windows-2025", "windows-2022", "macos-latest", "macos-15", "macos-14",
}
ALLOWED_OPTIONS = {
    ("--security-opt", "seccomp=/etc/factory-runner/seccomp-bwrap.json"),
    ("--security-opt", "systempaths=unconfined"),
}
OAUTH = "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"
OAUTH_REF = re.compile(r"secrets\.CLAUDE_CODE_OAUTH_TOKEN")
APP_KEY = "${{ secrets.FACTORY_APP_PRIVATE_KEY }}"
APP_KEY_REF = re.compile(r"secrets\.FACTORY_APP_PRIVATE_KEY")
APP_TOKEN_ACTION = "actions/create-github-app-token@"
JOB_TOKENS = {"${{ github.token }}", "${{ secrets.GITHUB_TOKEN }}"}
DEFAULT_BRANCH_REFS = {"${{ github.event.repository.default_branch }}", "main"}
AGENT_INPUTS = {"claude_code_oauth_token", "github_token", "prompt", "claude_args", "settings", "allowed_bots",
                "classify_inline_comments", "bot_name", "bot_id"}
SETTINGS_INPUT = re.compile(r"^\$\{\{ env\.CHECKS \}\}/[\w.-]+\.settings\.json$")
REMOVE_REMOTE = re.compile(r"^\s*git remote remove origin\s*$", re.M)
TOOL_ARGS_SETTER = re.compile(r"FACTORY_TOOL_ARGS=\$\(tr '\\n' ' ' < \.github/factory/[\w-]+-tools\.args\)")
TOOL_ARGS_FILE = re.compile(r"\.github/factory/([\w-]+-tools\.args)")
EXPR = re.compile(r"\$\{\{.*?\}\}")
HEADLESS = "SDLC headless mode: no person is present."
# One directory level is allowed (the brief rewrite resumes from its own), never `..`.
RESUME_FILE = re.compile(r"^\$\{\{ env\.CHECKS \}\}/(?:[\w-][\w.-]*/)?[\w.-]+\.jsonl$")
PRINTABLE = re.compile(r"^[\x20-\x7e\t\n]*$")
MODEL_ID = re.compile(r"^claude-[a-z0-9.-]+$")
MODEL_INPUT = re.compile(r"^\$\{\{ inputs\.model(?: \|\| '(claude-[a-z0-9.-]+)')? \}\}$")
# claude_args flags an agent step may set, with a check for each value (None: takes no value).
# --model is checked separately (it depends on the workflow's inputs).
FLAGS = {
    "model": lambda v: True,
    "json-schema": lambda v: True,
    "mcp-config": lambda v: True,
    "strict-mcp-config": None,
    "setting-sources": lambda v: v in ("user", "user,project"),
    "permission-mode": lambda v: v == "auto",
    "permission-prompts": lambda v: v == "none",
    "max-turns": lambda v: v.isdigit(),
    "settings": lambda v: bool(SETTINGS_INPUT.match(v)),
    # The headless declaration (process/headless-mode.md), verbatim.
    "append-system-prompt": lambda v: v == HEADLESS,
    # A literal advisor, or the one the workflow chose from its choice input.
    "advisor": lambda v: v in ("opus", "fable", "${{ env.FACTORY_ADVISOR }}"),
    "effort": lambda v: v in ("low", "medium", "high", "xhigh", "max"),
    # Resume a saved session: only a file in the frozen checks directory.
    "resume": lambda v: bool(RESUME_FILE.match(v)),
}
ENV_NAME = re.compile(r"TOKEN|^ANTHROPIC_|^CLAUDE_CODE_OAUTH|^FACTORY_TOOL_ARGS$|_PAT$|PRIVATE_KEY", re.I)
DIRECT_CLAUDE = re.compile(r"@anthropic-ai/|claude-agent-sdk|(^|[\s;&|(/])claude(\s|$)", re.M)


SERVICE_SLOTS = {f"FACTORY_SVC_{n}" for n in range(1, 5)}
EXEC_SERVICE_SLOTS = {f"FACTORY_EXEC_SVC_{n}" for n in range(1, 3)}
# The execution stages' workflows (implement and execute share factory-implement.yml), on the strict tier.
EXECUTION_WORKFLOWS = {"factory-implement.yml", "factory-revise.yml"}
SERVICES_RUN = re.compile(r"python3 -I \.github/factory/services\.py \.github/factory/services\.json ")
PLANNING_WORKFLOWS = {"factory-plan.yml", "factory-spec.yml", "factory-revise-doc.yml"}
# The planning stages' sandbox probe (D2 rule 5): proven in their tier and job setup, so it runs where they run.
PLANNING_PROBES = {("factory-smoke.yml", "planning-sandbox")}
PRODUCTION_WORKFLOW = "factory-gate.yml"
PRODUCTION_JOBS = {"execute": "runner"}
PRODUCTION_PERMISSIONS = {"actions": "read", "contents": "read", "issues": "read", "pull-requests": "read"}
SECRET_REF = re.compile(r"secrets\.|secrets\[|toJSON\(\s*secrets", re.I)
FIXTURES_JOB = "fixtures"
FIXTURES_WORKFLOWS = {"factory-implement.yml", "factory-revise.yml"}
FIXTURES_ACTIONS = ("actions/checkout@", "actions/cache@", "actions/upload-artifact@")
FIXTURE_SECRET = re.compile(r"^\$\{\{ secrets\['([A-Za-z_][A-Za-z0-9_]*)?'\] \}\}$")
STATUS_FUNCTION = re.compile(r"\b(?:always|success|failure|cancelled)\(\)")
# factory.json's fixtures values render into workflow text: an expression or a quote would change it.
FIXTURE_VALUES = {
    "path": re.compile(r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._/-]*$"),
    "secret": re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*)?$"),
    "apt": re.compile(r"^[a-z0-9.+ -]*$"),
    "cache_key": re.compile(r"^[A-Za-z0-9._-]*$"),
    "key_files": re.compile(r"^[A-Za-z0-9._/*-]*$"),
    "run": re.compile(r"^(?!.*\$\{\{)[\x20-\x7e]*$"),
}

LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# Labels GitHub gives every self-hosted runner (matched without regard to case): never a hosted label.
SELF_HOSTED_DEFAULTS = {"self-hosted", "linux", "windows", "macos", "x64", "arm", "arm64"}
WORKFLOW_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml$")
JOB_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
LOCAL_ACTION_DEPTH = 8

# The project's runner labels and environment names (factory.json in the factory directory; configure()).
PLANNING_LABEL = PRODUCTION_LABEL = WRITER_ENVIRONMENT = PLANNING_ENVIRONMENT = PRODUCTION_ENVIRONMENT = None
FACTORY_LABELS = frozenset()
CI_LABEL = None
# factory.json's policy block: extra hosted labels, and {(workflow, job): reason} exemptions from the container rule.
HOSTED_EXTRA = frozenset()
EXEMPTIONS = {}
# The repository the workflows belong to, where `uses: ./...` resolves (main()).
REPO_ROOT = None


def configure(factory_dir):
    """Read the runner labels and environment names this project's workflows were rendered with, and its
    policy block. Returns the policy block's own violations."""
    global PLANNING_LABEL, PRODUCTION_LABEL, WRITER_ENVIRONMENT, PLANNING_ENVIRONMENT, PRODUCTION_ENVIRONMENT
    global FACTORY_LABELS, HOSTED_EXTRA, EXEMPTIONS, CI_LABEL
    config = json.loads((pathlib.Path(factory_dir) / "factory.json").read_text())
    PLANNING_LABEL, PRODUCTION_LABEL = config["runners"]["planning"], config["runners"]["production"]
    FACTORY_LABELS = frozenset(v for k, v in config["runners"].items() if isinstance(v, str))
    CI_LABEL = config["runners"].get("ci") if isinstance(config["runners"].get("ci"), str) else None
    environments = config["environments"]
    WRITER_ENVIRONMENT, PLANNING_ENVIRONMENT = environments["writer"], environments["planning"]
    PRODUCTION_ENVIRONMENT = environments["production"]
    failures = []
    policy = config.get("policy") or {}
    labels = policy.get("hosted_labels", [])
    if not isinstance(labels, list):
        failures.append("factory.json policy.hosted_labels: a list of runner labels")
        labels = []
    good = set()
    for label in labels:
        if (not isinstance(label, str) or not LABEL.match(label) or label.lower() in SELF_HOSTED_DEFAULTS
                or label.lower() in {f.lower() for f in FACTORY_LABELS}):
            failures.append(f"factory.json policy.hosted_labels: {label!r} isn't a GitHub-hosted runner label "
                            "(never one every self-hosted runner carries, or one of the factory's runner labels)")
        else:
            good.add(label)
    HOSTED_EXTRA = frozenset(good)
    exemptions = policy.get("self_hosted_exemptions", [])
    if not isinstance(exemptions, list):
        failures.append("factory.json policy.self_hosted_exemptions: a list of {workflow, job, reason}")
        exemptions = []
    EXEMPTIONS = {}
    for entry in exemptions:
        where = f"factory.json policy.self_hosted_exemptions: {entry!r}"
        if not isinstance(entry, dict) or set(entry) != {"workflow", "job", "reason"}:
            failures.append(f"{where}: needs exactly workflow, job and reason")
            continue
        workflow, job, reason = entry["workflow"], entry["job"], entry["reason"]
        if not isinstance(workflow, str) or not WORKFLOW_FILE.match(workflow) or workflow.startswith("factory-"):
            failures.append(f"{where}: workflow is one of the project's own workflow files, never a factory workflow")
        elif not isinstance(job, str) or not JOB_ID.match(job):
            failures.append(f"{where}: job is a job ID")
        elif not isinstance(reason, str) or len(reason.strip()) < 20:
            failures.append(f"{where}: reason says why the job can't run hosted or in the factory container")
        elif (workflow, job) in EXEMPTIONS:
            failures.append(f"{where}: listed twice")
        else:
            EXEMPTIONS[(workflow, job)] = reason.strip()
    return failures


def environment_name(job):
    environment = job.get("environment")
    return environment.get("name") if isinstance(environment, dict) else environment


def production_failures(workflow_name, name, job, is_agent_job):
    """The production tier (design rule D4): one containerless job, behind CD's approval, that can only
    hand the run to the broker."""
    labels = job.get("runs-on", [])
    labels = [labels] if isinstance(labels, str) else labels if isinstance(labels, list) else []
    on_prod = PRODUCTION_LABEL in labels
    environment = environment_name(job)
    failures = []
    if workflow_name == PRODUCTION_WORKFLOW and is_agent_job:
        failures.append(f"{name}: {PRODUCTION_WORKFLOW} may not run an agent")
    if on_prod:
        if workflow_name != PRODUCTION_WORKFLOW or PRODUCTION_JOBS.get(name) != "runner":
            failures.append(f"{name}: only {PRODUCTION_WORKFLOW}'s execute job may run on {PRODUCTION_LABEL} runners")
        if job.get("container") or job.get("services"):
            failures.append(f"{name}: the production job runs no container or service")
        if environment != PRODUCTION_ENVIRONMENT:
            failures.append(f"{name}: the production job needs the {PRODUCTION_ENVIRONMENT} environment (CD's approval)")
        if job.get("permissions") != PRODUCTION_PERMISSIONS:
            failures.append(f"{name}: the production job's permissions must be exactly {PRODUCTION_PERMISSIONS}")
        for step in job.get("steps") or []:
            if "uses" in step or set(step) - {"name", "id", "env", "run", "shell", "if", "timeout-minutes"}:
                failures.append(f"{name}: the production job runs only plain run steps")
        if SECRET_REF.search(str(job)):
            failures.append(f"{name}: the production job references a secret")
    if environment == PRODUCTION_ENVIRONMENT:
        kind = PRODUCTION_JOBS.get(name) if workflow_name == PRODUCTION_WORKFLOW else None
        if kind is None or (kind == "runner") != on_prod or (kind == "hosted" and not hosted(job.get("runs-on", []))):
            failures.append(f"{name}: the {PRODUCTION_ENVIRONMENT} environment is for {PRODUCTION_WORKFLOW}'s gate jobs only")
        if kind == "hosted" and (job.get("permissions") != {} or SECRET_REF.search(str(job))
                                 or any("uses" in s for s in job.get("steps") or [])):
            failures.append(f"{name}: the CD-gate job has no permissions, secrets or actions")
    return failures


def tier_failures(workflow_name, name, job, is_agent_job):
    """Planning runners and their environment belong to the planning workflows only (D3 rule 1)."""
    labels = job.get("runs-on", [])
    labels = [labels] if isinstance(labels, str) else labels if isinstance(labels, list) else []
    on_planning = PLANNING_LABEL in labels
    environment = job.get("environment")
    environment = environment.get("name") if isinstance(environment, dict) else environment
    failures = []
    if on_planning and workflow_name not in PLANNING_WORKFLOWS and (workflow_name, name) not in PLANNING_PROBES:
        failures.append(f"{name}: only the planning workflows may run on {PLANNING_LABEL} runners")
    if (workflow_name, name) in PLANNING_PROBES and not on_planning:
        failures.append(f"{name}: the planning stages' sandbox probe must run on {PLANNING_LABEL} runners")
    if workflow_name in PLANNING_WORKFLOWS and is_agent_job and not on_planning:
        failures.append(f"{name}: a planning agent job must run on {PLANNING_LABEL} runners")
    if environment == PLANNING_ENVIRONMENT and not on_planning:
        failures.append(f"{name}: the {PLANNING_ENVIRONMENT} environment is for planning-tier jobs only")
    return failures


OPEN_VERDICT = re.compile(r'sandbox_check\.py"?\s+agent\b[^\n|]*\sopen\b')


def probe_network_failures(workflow_name, name, job):
    """Only the planning stages' probe is judged by the planning tier's open internet (D3 rule 5)."""
    if (workflow_name, name) in PLANNING_PROBES:
        return []
    return [f"{name}: only the planning stages' sandbox probe may be judged by the open internet (`open`)"
            for step in job.get("steps") or [] if OPEN_VERDICT.search(str(step.get("run", "")))]


def hosted(runs_on):
    labels = [runs_on] if isinstance(runs_on, str) else runs_on
    return isinstance(labels, list) and bool(labels) and all(l in HOSTED or l in HOSTED_EXTRA for l in labels)


def load_local_action(uses):
    """A local composite action's definition, or why it can't be scanned."""
    if REPO_ROOT is None:
        return None, "can't be resolved (the workflows aren't in a repository's .github/workflows)"
    if "@" in uses:
        return None, "names a ref, which a local action can't"
    root = REPO_ROOT.resolve()
    path = (root / uses[2:]).resolve()
    if path != root and root not in path.parents:
        return None, "is outside the repository"
    file = next((path / n for n in ("action.yml", "action.yaml") if (path / n).is_file()), None)
    if file is None:
        return None, "has no action.yml or action.yaml, so it can't be scanned"
    try:
        action = yaml.safe_load(file.read_text())
    except yaml.YAMLError:
        return None, "doesn't parse"
    runs = action.get("runs") if isinstance(action, dict) else None
    using = str((runs or {}).get("using", "")) if isinstance(runs, dict) else ""
    if using != "composite":
        return None, f"runs {using or 'nothing'}, not composite steps, so it can't be scanned"
    if not isinstance(runs.get("steps"), list):
        return None, "has no steps list"
    return action, None


def expand_steps(name, steps, chain=()):
    """The job's steps with each local composite action's steps after the step that calls it, nested
    ones included, and why any local action can't be scanned. Every step-level rule reads this list."""
    out, failures = [], []
    for step in steps:
        if not isinstance(step, dict):
            continue
        out.append(step)
        uses = str(step.get("uses", ""))
        if chain and uses.startswith(ACTION):
            failures.append(f"{name}: agent step inside local action {chain[-1]}: the policy checks agent steps "
                            "only in the workflow")
        if not uses.startswith("./"):
            continue
        if uses in chain:
            failures.append(f"{name}: local action {uses} uses itself")
            continue
        if len(chain) >= LOCAL_ACTION_DEPTH:
            failures.append(f"{name}: local action {uses} is nested too deep to scan")
            continue
        action, why = load_local_action(uses)
        if why:
            failures.append(f"{name}: local action {uses} {why}")
            continue
        inner, more = expand_steps(name, action["runs"]["steps"], chain + (uses,))
        out += inner
        failures += more
    return out, failures


def container_failures(name, job):
    """(job: its steps expanded, expand_steps)"""
    failures = []
    if not job.get("container"):
        failures.append(f"{name}: runs off GitHub-hosted runners without a container")
    if job.get("services"):
        failures.append(f"{name}: runs service containers off GitHub-hosted runners")
    container = job.get("container")
    if isinstance(container, dict):
        if container.get("volumes"):
            failures.append(f"{name}: container mounts volumes")
        try:
            tokens = shlex.split(str(container.get("options", "")))
        except ValueError:
            tokens = []
            failures.append(f"{name}: container options don't parse")
        while tokens:
            if tuple(tokens[:2]) in ALLOWED_OPTIONS:
                tokens = tokens[2:]
            else:
                failures.append(f"{name}: container option not allowed: {tokens[0]}")
                tokens = tokens[1:]
    for step in job.get("steps") or []:
        if str(step.get("uses", "")).startswith("docker://"):
            failures.append(f"{name}: docker:// step off GitHub-hosted runners")
        if re.search(r"(^|[\s;&|(])docker\s", str(step.get("run", "")), re.M):
            failures.append(f"{name}: runs the docker CLI off GitHub-hosted runners")
    return failures


def claude_words(args):
    """claude_args as shell words, with each ${{ }} expression kept whole (raises ValueError)."""
    exprs = EXPR.findall(args)
    placeholder = {f"__expr{i}__": e for i, e in enumerate(exprs)}
    text = args
    for key, expr in placeholder.items():
        text = text.replace(expr, key, 1)
    words = shlex.split(text)
    for key, expr in placeholder.items():
        words = [w.replace(key, expr) for w in words]
    return words


def model_failures(label, value, model_input):
    """--model: a literal model ID, or the workflow's model input when it's a choice of model IDs."""
    if MODEL_ID.match(value):
        return []
    match = MODEL_INPUT.match(value)
    if not match:
        return [f"{label}: --model must be a model ID or ${{{{ inputs.model }}}}: {value}"]
    options = (model_input or {}).get("options") if isinstance(model_input, dict) else None
    if (model_input or {}).get("type") != "choice" or not options or not all(MODEL_ID.match(str(o)) for o in options):
        return [f"{label}: --model takes inputs.model, which must be a choice input of model IDs"]
    return []


def claude_args_failures(label, args, pinned, model_input):
    """Parse claude_args like the action does (shell words, '--flag value'), refuse anything off the list."""
    failures = []
    if not PRINTABLE.match(args):
        return [f"{label}: claude_args has a character outside printable ASCII"]
    if "#" in args:
        return [f"{label}: '#' in claude_args (the action parses it as a shell comment)"]
    if EXPR.findall(args).count("${{ env.FACTORY_TOOL_ARGS }}") != 1:
        failures.append(f"{label}: claude_args needs exactly one ${{{{ env.FACTORY_TOOL_ARGS }}}}")
    try:
        words = claude_words(args)
    except ValueError:
        return failures + [f"{label}: claude_args don't parse"]
    seen = set()
    i = 0
    while i < len(words):
        word = words[i]
        i += 1
        if word == "${{ env.FACTORY_TOOL_ARGS }}":
            continue
        if not word.startswith("--") or "=" in word:
            failures.append(f"{label}: unexpected claude_args word: {word}")
            continue
        flag = word[2:]
        if flag not in FLAGS:
            failures.append(f"{label}: claude_args flag not allowed: --{flag}")
            continue
        if flag in seen:
            failures.append(f"{label}: --{flag} given twice")
        seen.add(flag)
        check = FLAGS[flag]
        if check is None:
            continue
        if i >= len(words) or words[i].startswith("--"):
            failures.append(f"{label}: --{flag} has no value")
            continue
        value = words[i]
        i += 1
        if flag == "model":
            failures += model_failures(label, value, model_input)
        elif not check(value):
            failures.append(f"{label}: --{flag} value not allowed: {value}")
        if flag == "setting-sources" and "project" in value.split(",") and not pinned:
            failures.append(f"{label}: loads project settings without a checkout pinned to the default branch")
    for flag in ("strict-mcp-config", "setting-sources"):
        if flag not in seen:
            failures.append(f"{label}: no --{flag}")
    return failures


def grants_bash(text):
    """Whether a tool policy grants Bash: named in --tools or --allowedTools, or no --tools at all."""
    words = shlex.split(text)
    if "--tools" not in words:
        return True
    current = None
    for word in words:
        if word.startswith("--"):
            current = word
        elif current in ("--tools", "--allowedTools"):
            if any(t == "Bash" or t.startswith("Bash(") for t in re.split(r"[,\s]+", word)):
                return True
    return False


def tool_args_failures(name, setters, factory_dir):
    """Read the *-tools.args files the job's setters name. Returns (failures, grants Bash)."""
    failures, bash = [], False
    for file in sorted({f for s in setters for f in TOOL_ARGS_FILE.findall(str(s["run"]))}):
        path = factory_dir / file
        try:
            text = path.read_text()
        except OSError:
            failures.append(f"{name}: tool policy {file} not found in {factory_dir}")
            continue
        if not PRINTABLE.match(text):
            failures.append(f"{name}: tool policy {file} has a character outside printable ASCII")
            continue
        try:
            bash = grants_bash(text) or bash
        except ValueError:
            failures.append(f"{name}: tool policy {file} doesn't parse")
    return failures, bash


def checkout_failures(name, steps):
    """Exactly one checkout, of this repository into the workspace, credentials not persisted.
    Returns (failures, pinned to the default branch)."""
    checkouts = [s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@")]
    if len(checkouts) != 1:
        return [f"{name}: agent job needs exactly one checkout (has {len(checkouts)})"], False
    with_ = checkouts[0].get("with") or {}
    failures = [f"{name}: agent job checkout sets {k}" for k in ("repository", "path") if k in with_]
    if str(with_.get("persist-credentials", "")).strip().lower() != "false":
        failures.append(f"{name}: agent job checkout must set persist-credentials: false")
    return failures, str(with_.get("ref", "")).strip() in DEFAULT_BRANCH_REFS


def sandbox_failures(name, job, workflow_env, agent_steps):
    """A Bash-granting tool policy runs only inside the factory's proven sandbox setup."""
    failures = []
    scrub = {**workflow_env, **(job.get("env") or {})}.get("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB")
    if str(scrub) != "1":
        failures.append(f"{name}: grants Bash without CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: \"1\"")
    container = job.get("container")
    options = []
    if isinstance(container, dict):
        try:
            words = shlex.split(str(container.get("options", "")))
            options = list(zip(words[::2], words[1::2]))
        except ValueError:
            pass
    if not ALLOWED_OPTIONS <= set(options):
        failures.append(f"{name}: grants Bash outside a container with the factory seccomp and systempaths options")
    for step in agent_steps:
        label = f"{name} / {step.get('name', step.get('id', 'claude-code-action'))}"
        with_ = step.get("with") or {}
        settings = str(with_.get("settings", "")).strip()
        try:
            words = claude_words(str(with_.get("claude_args", "")))
        except ValueError:
            words = []
        flag = words[words.index("--settings") + 1] if "--settings" in words[:-1] else None
        if not settings or flag != settings:
            failures.append(f"{label}: grants Bash without the same frozen file as --settings and the settings input")
    return failures


def agent_failures(name, job, workflow_env, model_input, factory_dir, workflow_name=""):
    failures = []
    steps = job.get("steps") or []
    perms = job.get("permissions")
    if not isinstance(perms, dict):
        failures.append(f"{name}: agent job needs an explicit permissions block")
    elif any(v not in ("read", "none") for v in perms.values()):
        failures.append(f"{name}: agent job grants a write permission")
    checkout, pinned = checkout_failures(name, steps)
    failures += checkout

    setters = [s for s in steps if "FACTORY_TOOL_ARGS=" in str(s.get("run", ""))]
    if not setters or any(len(re.findall(r"FACTORY_TOOL_ARGS=", str(s["run"])))
                          != len(TOOL_ARGS_SETTER.findall(str(s["run"]))) for s in setters):
        failures.append(f"{name}: FACTORY_TOOL_ARGS must be set only from .github/factory/*-tools.args")
    policy, bash = tool_args_failures(name, setters, factory_dir)
    failures += policy
    agent_steps = [s for s in steps if str(s.get("uses", "")).startswith(ACTION)]
    # The action writes the job token into origin's URL, where the agent can read it.
    first_agent = next(i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith(ACTION))
    if not any(REMOVE_REMOTE.search(str(s.get("run", ""))) for s in steps[:first_agent]):
        failures.append(f"{name}: agent job must run `git remote remove origin` before the agent step")
    if bash:
        failures += sandbox_failures(name, job, workflow_env, agent_steps)

    envs = [("workflow", workflow_env), ("job", job.get("env") or {})]
    envs += [(s.get("name", "agent step"), s.get("env") or {}) for s in steps if str(s.get("uses", "")).startswith(ACTION)]
    # Service credential slots (README § Services) may reach an agent step, each exactly its own secret,
    # when the job builds its sandbox settings with services.py, which masks every slot: a planning job its
    # own four, an execution job (strict tier) its own two. A planning slot never reaches a strict-tier job.
    builds_services = any(SERVICES_RUN.search(str(s.get("run", ""))) for s in steps[:first_agent])
    for where, env in envs:
        for key, value in env.items():
            planning = workflow_name in PLANNING_WORKFLOWS or (workflow_name, name) in PLANNING_PROBES
            execution = workflow_name in EXECUTION_WORKFLOWS and not planning
            own_secret = str(value).strip() == f"${{{{ secrets.{key} }}}}" and where not in ("workflow", "job")
            if own_secret and builds_services and ((key in SERVICE_SLOTS and planning)
                                                   or (key in EXEC_SERVICE_SLOTS and execution)):
                continue
            refs = set(re.findall(r"secrets\.(\w+)", str(value)))
            if ENV_NAME.search(key) or refs - {"CONTEXT7_API_KEY"}:
                failures.append(f"{name}: {where} env {key} reaches the agent")

    for step in steps:
        if not str(step.get("uses", "")).startswith(ACTION):
            continue
        label = f"{name} / {step.get('name', step.get('id', 'claude-code-action'))}"
        with_ = step.get("with") or {}
        failures += [f"{label}: input not allowed: {k}" for k in sorted(set(with_) - AGENT_INPUTS)]
        if str(with_.get("claude_code_oauth_token", "")).strip() != OAUTH:
            failures.append(f"{label}: claude_code_oauth_token must be {OAUTH}")
        if str(with_.get("github_token", "")).strip() not in JOB_TOKENS:
            failures.append(f"{label}: github_token must be the job's own read-only token")
        if "settings" in with_ and not SETTINGS_INPUT.match(str(with_["settings"]).strip()):
            failures.append(f"{label}: settings must be a frozen file under ${{{{ env.CHECKS }}}}")
        failures += claude_args_failures(label, str(with_.get("claude_args", "")), pinned, model_input)
    return failures


def oauth_failures(name, job, workflow_env, is_agent_job):
    """The OAuth secret: an agent step's input, or a run step's env inside an agent job. Nowhere else."""
    failures = []
    if OAUTH_REF.search(str(workflow_env)) or OAUTH_REF.search(str(job.get("env") or "")):
        failures.append(f"{name}: OAuth token in workflow or job env")
    for step in job.get("steps") or []:
        label = f"{name} / {step.get('name', step.get('uses', 'step'))}"
        rest = {k: v for k, v in step.items() if k not in ("with", "env")}
        if OAUTH_REF.search(str(rest)):
            failures.append(f"{label}: OAuth token outside an input or env")
        is_agent = str(step.get("uses", "")).startswith(ACTION)
        with_ = dict(step.get("with") or {})
        if is_agent:
            with_.pop("claude_code_oauth_token", None)
        if OAUTH_REF.search(str(with_)):
            failures.append(f"{label}: OAuth token passed as an input")
        if OAUTH_REF.search(str(step.get("env") or "")) and not (is_agent_job and "run" in step):
            failures.append(f"{label}: OAuth token in env outside an agent job's run step")
    return failures


def app_key_failures(name, job, workflow_env, is_agent_job):
    """The App key: create-github-app-token's private-key, in a hosted writer-environment job with no agent."""
    failures = []
    if APP_KEY_REF.search(str(workflow_env)) or APP_KEY_REF.search(str(job.get("env") or "")):
        failures.append(f"{name}: App key in workflow or job env")
    users = []
    for step in job.get("steps") or []:
        label = f"{name} / {step.get('name', step.get('uses', 'step'))}"
        with_ = dict(step.get("with") or {})
        is_minter = str(step.get("uses", "")).startswith(APP_TOKEN_ACTION)
        if is_minter and str(with_.get("private-key", "")).strip() == APP_KEY:
            with_.pop("private-key")
            users.append(label)
        rest = {k: v for k, v in step.items() if k != "with"}
        if APP_KEY_REF.search(str(rest)) or APP_KEY_REF.search(str(with_)):
            failures.append(f"{label}: App key outside create-github-app-token's private-key")
    if users:
        environment = job.get("environment")
        if isinstance(environment, dict):
            environment = environment.get("name")
        if environment != WRITER_ENVIRONMENT:
            failures.append(f"{name}: App key in a job outside the {WRITER_ENVIRONMENT} environment")
        if not hosted(job.get("runs-on", [])):
            failures.append(f"{name}: App key on a self-hosted runner")
        if is_agent_job:
            failures.append(f"{name}: App key in an agent job")
    return failures


JOB_TOKEN_REF = re.compile(r"github\.token|secrets\.GITHUB_TOKEN|secrets\[\s*['\"]GITHUB_TOKEN", re.I)


def ci_tier_failures(workflow_name, name, job, is_agent_job):
    """The CI tier: a project's own CI jobs, pull requests' code included, each in a disposable runner container.
    The job runs in that container: no container or services of its own (the runner image has no Docker), and
    nothing for a pull request's code to take: no secret, no job token, read-only permissions, checkouts that keep
    no credentials. (job: its steps expanded.)"""
    if not on_ci_tier(job):
        return []
    failures = []
    if workflow_name.startswith("factory-"):
        failures.append(f"{name}: only a project's own workflows run on the CI tier ({CI_LABEL})")
    if is_agent_job:
        failures.append(f"{name}: no agent job runs on the CI tier ({CI_LABEL})")
    for key, what in (("container", "container"), ("services", "service containers")):
        if job.get(key):
            failures.append(f"{name}: a CI-tier job runs in its disposable runner, with no {what} of its own")
    perms = job.get("permissions")
    if not isinstance(perms, dict) or any(v not in ("read", "none") for v in perms.values()):
        failures.append(f"{name}: a CI-tier job needs explicit read-only permissions")
    for step in job.get("steps") or []:
        uses = str(step.get("uses", ""))
        if uses.startswith("actions/checkout@") and (step.get("with") or {}).get("persist-credentials") is not False:
            failures.append(f"{name}: a CI-tier job's checkout sets persist-credentials: false")
        if uses.startswith("docker://"):
            failures.append(f"{name}: a CI-tier job runs no docker:// step (its runner has no Docker)")
    if SECRET_REF.search(str(job)) or JOB_TOKEN_REF.search(str(job)):
        failures.append(f"{name}: a CI-tier job runs pull requests' code, so it holds no secret and no job token")
    return failures


def on_ci_tier(job):
    runs_on = job.get("runs-on", [])
    labels = [runs_on] if isinstance(runs_on, str) else runs_on if isinstance(runs_on, list) else []
    return bool(CI_LABEL) and CI_LABEL in labels


def fixture_secrets(job):
    """The secret names a fixtures job's FIXTURE_SECRET steps name ('' for none)."""
    names = set()
    for step in job.get("steps") or []:
        for key, value in (step.get("env") or {}).items():
            match = FIXTURE_SECRET.match(str(value).strip())
            if key == "FIXTURE_SECRET" and match:
                names.add(match.group(1) or "")
    return names


def fixtures_failures(workflow_name, name, job, is_agent_job):
    """Fixtures from a secret-holding source (D2 rule 7): made on a hosted runner from the default branch,
    handed over as an artifact; the secret reaches only this job's own steps. A project's own workflows
    (ci.yml) may have a job of that name: only the factory's are checked."""
    if name != FIXTURES_JOB or not workflow_name.startswith("factory-"):
        return []
    failures = []
    if workflow_name not in FIXTURES_WORKFLOWS:
        failures.append(f"{name}: a fixtures job belongs to {', '.join(sorted(FIXTURES_WORKFLOWS))} only")
    if not hosted(job.get("runs-on", [])):
        failures.append(f"{name}: the fixtures job runs on a GitHub-hosted runner")
    if is_agent_job:
        failures.append(f"{name}: the fixtures job runs no agent")
    for key in ("container", "services", "environment", "outputs"):
        if job.get(key):
            failures.append(f"{name}: the fixtures job has no {key}")
    if job.get("permissions") != {"contents": "read"}:
        failures.append(f"{name}: the fixtures job's permissions must be exactly contents: read")
    steps = job.get("steps") or []
    checkouts = [s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@")]
    with_ = (checkouts[0].get("with") or {}) if len(checkouts) == 1 else {}
    if len(checkouts) != 1 or with_.get("ref") not in DEFAULT_BRANCH_REFS or with_.get("persist-credentials") is not False:
        failures.append(f"{name}: the fixtures job checks out the default branch once, without persisted credentials")
    for step in steps:
        uses = str(step.get("uses", ""))
        if uses and not uses.startswith(FIXTURES_ACTIONS):
            failures.append(f"{name}: action not allowed in the fixtures job: {uses}")
        if SECRET_REF.search(str({k: v for k, v in step.items() if k != "env"})):
            failures.append(f"{name} / {step.get('name', uses or 'step')}: secret outside a step's env")
        for key, value in (step.get("env") or {}).items():
            if SECRET_REF.search(str(value)) and not (key == "FIXTURE_SECRET" and "run" in step
                                                       and FIXTURE_SECRET.match(str(value).strip())):
                failures.append(f"{name} / {step.get('name', 'step')}: env {key}: a fixtures job's secret is "
                                "${{ secrets['NAME'] }} in a run step's FIXTURE_SECRET")
    if SECRET_REF.search(str({k: v for k, v in job.items() if k != "steps"})):
        failures.append(f"{name}: secret in the fixtures job's own settings")
    if len(fixture_secrets(job) - {""}) > 1:
        failures.append(f"{name}: the fixtures job uses one secret")
    return failures


def fixture_secret_failures(path, workflow):
    """A fixtures job's secret reaches no other job, nor the workflow env; factory.json's fixtures values
    can't change the workflow text they render into."""
    failures = []
    if not path.name.startswith("factory-"):
        return failures
    jobs = workflow.get("jobs") or {}
    names = fixture_secrets(jobs.get(FIXTURES_JOB) or {}) - {""}
    for secret in sorted(names):
        ref = re.compile(rf"secrets(?:\.{secret}\b|\[\s*['\"]{secret}['\"]\s*\])", re.I)
        if ref.search(str(workflow.get("env") or {})):
            failures.append(f"{path}: the fixtures secret {secret} is in the workflow env")
        for name, job in jobs.items():
            steps, _ = expand_steps(name, job.get("steps") or [])
            if name != FIXTURES_JOB and ref.search(str({**job, "steps": steps})):
                failures.append(f"{path}: {name}: references the fixtures secret {secret}")
    return failures


def condition_failures(path, workflow):
    """A factory job after one that carries on past a skipped or failed job (a status function in its `if`)
    has a status function in its own `if`: GitHub's implicit success() reads every earlier job."""
    if not path.name.startswith("factory-"):
        return []
    jobs = workflow.get("jobs") or {}

    def needs(name):
        n = (jobs.get(name) or {}).get("needs") or []
        return [n] if isinstance(n, str) else list(n)

    def carries_on(name):
        return bool(STATUS_FUNCTION.search(str((jobs.get(name) or {}).get("if", ""))))

    failures = []
    for name in jobs:
        if carries_on(name):
            continue
        earlier, todo = set(), needs(name)
        while todo:
            n = todo.pop()
            if n not in earlier:
                earlier.add(n)
                todo += needs(n)
        past = sorted(n for n in earlier if carries_on(n))
        if past:
            failures.append(f"{path}: {name}: runs after {', '.join(past)}, which carry on past a skipped or "
                            "failed job, so its `if` needs a status function too (!cancelled() or always())")
    return failures


def fixture_value_failures(factory_dir):
    config = json.loads((pathlib.Path(factory_dir) / "factory.json").read_text())
    fixtures = config.get("fixtures") or {}
    failures = []
    for key, pattern in FIXTURE_VALUES.items():
        value = fixtures.get(key, "")
        if not isinstance(value, str) or not pattern.match(value):
            failures.append(f"factory.json fixtures.{key}: {value!r} would change the workflow text it renders into")
    if fixtures.get("path") and not all(fixtures.get(k) for k in ("run", "cache_key", "key_files")):
        failures.append("factory.json fixtures: a path needs run, cache_key and key_files")
    return failures


def job_failures(name, job, workflow_env, model_input, factory_dir, workflow_name="", used_exemptions=None):
    # Every rule below reads the job with its local composite actions' steps in place.
    steps, failures = expand_steps(name, job.get("steps") or [])
    is_agent_job = any(str(s.get("uses", "")).startswith(ACTION) for s in job.get("steps") or [])
    if is_agent_job and any(str(s.get("uses", "")).startswith("./") for s in job.get("steps") or []):
        failures.append(f"{name}: an agent job runs no local action")
    job = {**job, "steps": steps}
    runs_on = job.get("runs-on", [])
    labels = [runs_on] if isinstance(runs_on, str) else runs_on if isinstance(runs_on, list) else []
    on_prod = PRODUCTION_LABEL in labels
    reason = EXEMPTIONS.get((workflow_name, name))
    if reason is not None and used_exemptions is not None:
        used_exemptions.add((workflow_name, name))
    if not hosted(runs_on) and not on_prod and not on_ci_tier(job):
        if reason is None:
            failures += container_failures(name, job)
        elif is_agent_job or FACTORY_LABELS & set(labels):
            failures.append(f"{name}: exempt from the container rule, but an agent job or one on the factory's "
                            "runners never is")
            failures += container_failures(name, job)
        else:
            print(f"::notice::{workflow_name}: {name}: runs on a self-hosted runner without the factory "
                  f"container (factory.json policy.self_hosted_exemptions: {reason})")
    elif reason is not None:
        where = "on the CI tier's disposable runners" if on_ci_tier(job) else "hosted"
        failures.append(f"{name}: has an exemption from the container rule it doesn't need (it runs {where})")
    for step in steps:
        uses = str(step.get("uses", ""))
        if "claude" in uses.lower() and not uses.startswith(ACTION):
            failures.append(f"{name}: Claude action other than {ACTION}: {uses}")
        if DIRECT_CLAUDE.search(str(step.get("run", ""))):
            failures.append(f"{name} / {step.get('name', 'run')}: runs Claude Code outside the action")
    failures += tier_failures(workflow_name, name, job, is_agent_job)
    failures += probe_network_failures(workflow_name, name, job)
    failures += production_failures(workflow_name, name, job, is_agent_job)
    failures += fixtures_failures(workflow_name, name, job, is_agent_job)
    failures += ci_tier_failures(workflow_name, name, job, is_agent_job)
    if is_agent_job and str({**workflow_env, **(job.get("env") or {})}.get("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS")) != "1":
        # Headless mode: the run ends with the orchestrator's turn, so a background agent's work is lost.
        failures.append(f"{name}: agent job without CLAUDE_CODE_DISABLE_BACKGROUND_TASKS: \"1\"")
    if is_agent_job:
        failures += agent_failures(name, job, workflow_env, model_input, factory_dir, workflow_name)
    failures += oauth_failures(name, job, workflow_env, is_agent_job)
    failures += app_key_failures(name, job, workflow_env, is_agent_job)
    return failures


def main():
    global REPO_ROOT
    root = pathlib.Path(sys.argv[1])
    factory_dir = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else root.parent / "factory"
    failures = configure(factory_dir)
    # `uses: ./...` resolves in the repository whose .github/workflows these are.
    resolved = root.resolve()
    REPO_ROOT = resolved.parent.parent if resolved.parent.name == ".github" else None
    paths = sorted([*root.glob("*.yml"), *root.glob("*.yaml")])
    used = set()
    for path in paths:
        workflow = yaml.safe_load(path.read_text()) or {}
        workflow_env = workflow.get("env") or {}
        # YAML 1.1 reads a bare `on` key as the boolean True.
        triggers = workflow.get("on") or workflow.get(True) or {}
        dispatch = triggers.get("workflow_dispatch") if isinstance(triggers, dict) else None
        model_input = ((dispatch or {}).get("inputs") or {}).get("model")
        for name, job in (workflow.get("jobs") or {}).items():
            failures += [f"{path}: {f}" for f in job_failures(name, job, workflow_env, model_input, factory_dir,
                                                               path.name, used)]
        failures += fixture_secret_failures(path, workflow)
        failures += condition_failures(path, workflow)
    failures += fixture_value_failures(factory_dir)
    # An exemption names a job that exists: the list stays exactly what it lets through.
    for workflow, job in sorted(set(EXEMPTIONS) - used):
        failures.append(f"factory.json policy.self_hosted_exemptions: {workflow} has no job {job}")
    # claude_args wraps each result schema in single quotes: one apostrophe breaks every run of that stage.
    for schema in sorted(factory_dir.glob("*.schema.json")):
        if "'" in schema.read_text():
            failures.append(f"{schema}: contains a single quote (claude_args wraps schemas in single quotes)")
    # The services the planning stages may use: a malformed entry would fail every planning run.
    services_file = factory_dir / "services.json"
    if services_file.exists():
        sys.path.insert(0, str(factory_dir))
        import services  # noqa: E402 (the factory directory's own module)
        try:
            services.load(services_file)
        except services.Invalid as e:
            failures.append(f"{services_file}: {e}")
    for f in failures:
        print(f"::error::{f}")
    print(f"workflow policy: {len(paths)} workflows, {len(failures)} violations")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
