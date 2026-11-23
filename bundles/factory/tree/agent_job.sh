#!/usr/bin/env bash
# The scaffolding every agent job shares, around the steps that stay in the workflow (the checkout,
# `git remote remove origin`, the tool policy and the agent step, which workflow_policy.py checks).
# Usage: agent_job.sh <command> [args]
#
# Before the agent:
#   freeze [file ...]   copy the factory's scripts, guards, schemas and factory.json, plus the named
#                       files (a stage's sandbox settings), to $CHECKS. Run from .github/factory/
#                       before anything can switch the workspace away from the default branch; every
#                       later call runs the frozen copy in $CHECKS.
#   mcp                 write the MCP config (Context7), set FACTORY_MCP_CONFIG for the next steps and
#                       print its path (a stage that adds servers to it does so in the same step)
#   services [file]     start the stack profile's test services; their settings go into the project's
#                       env file (factory.json stack.env_file), or into the file named
#   workspace           install the profile's test-services wrapper and verify at /opt/factory, with
#                       verify.conf (the stack's directories, and the config file each Node tool loads,
#                       which verify pins), run its install.sh (the dependencies), point the project's
#                       paths (stack.env) into the workspace, set the factory's git identity, exclude
#                       what's never the run's work (excludes) and record the hooks' hashes. Run
#                       after services, and after any secret is out of the environment.
#   excludes <profile>  exclude what's never the run's work from git status: each name the sandbox mounts
#                       over at the workspace's root that doesn't exist there, and the tool state the
#                       profile names (profiles/<profile>/excludes). In .git/info/exclude, for the agent's
#                       git status, and in $CHECKS/excludes, for bundle's check (workspace runs it)
#   browser <stage> <settings>
#                       the browser route (D6): when factory.json's browser block lists the stage (smoke
#                       always counts), add the browser host's front end for the project's Playwright to
#                       the frozen sandbox settings and write /opt/factory/browser.conf for with-browser,
#                       which workspace installed. Run after workspace (it reads the installed client).
#   issue-context <base> [deliverable]
#                       the issue and its comments as .factory/issue-context.json (and $RUNNER_TEMP/issue.json)
#   schema <name>       check <name>.schema.json and set FACTORY_<NAME>_SCHEMA for --json-schema
#   advisor <none|opus|fable>
#                       set FACTORY_ADVISOR for --advisor; none switches the advisor tool off
#   revise-context <merge base> [<stage> <document> <deliverable>]
#                       (revise stages) CD's review since the last revision, as .factory/revise-context.json
#                       for the agent; fails when there is none. The document stage names its document;
#                       a code PR that executes a plan names the plan and its next gate (PLAN and
#                       NEXT_GATE, from the gate job).
# After the agent (D2 rule 4: run only from $CHECKS):
#   quiesce             no sandbox process may outlive the agent step, and git_guard.sh must pass
#                       before the job runs git in the agent's repository again
#   bundle <base> <bundle> <status> <publishing status> ...
#                       count the commits since <base>; when <status> is one that publishes, require a
#                       commit, write <bundle>, remove the sandbox's empty placeholders at the root and
#                       refuse uncommitted changes, but for $CHECKS/excludes. It first prints what the
#                       sandbox left at the root.
#   stats               the run's cost, turns and models (from EXEC, the execution file) as the step
#                       output stats, for the agent record the publish guard checks
#   lost <who>          an agent step that ended with no result: keep its session log (session_log.sh,
#                       with OAUTH and GHTOKEN to refuse) and say why, as "the <who> agent ..."
#   metrics <stage>     the run's metrics record for the improve loop (run_metrics.py, inputs in the
#                       environment) at $RUNNER_TEMP/metrics/metrics.json
# Tested in CI by tests/test_agent_job.py.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
# The factory App's bot user (factory.json, frozen beside this script).
app() {
  app_id=$(jq -r .app.user_id "$here/factory.json")
  app_login=$(jq -r .app.login "$here/factory.json")
  [[ $app_id =~ ^[0-9]+$ ]] || { echo "::error::factory.json has no app.user_id"; exit 1; }
}
# The stack profile and this project's layout (factory.json's stack).
stack() {
  profile=$(jq -r .stack.profile "$here/factory.json")
  [[ $profile =~ ^[a-z0-9-]+$ ]] && [ -d "$here/profiles/$profile" ] \
    || { echo "::error::factory.json's stack.profile names no profile in $here/profiles"; exit 1; }
  python_dir=$(jq -r .stack.python "$here/factory.json")
  node_dir=$(jq -r .stack.node "$here/factory.json")
  env_file=$(jq -r .stack.env_file "$here/factory.json")
  database=$(jq -r .stack.database "$here/factory.json")
}
# The names the sandbox mounts over at the workspace's root (Claude Code 2.1.330's sandbox). Where none exists it
# makes an empty file there to mount on, which sandboxed `git status` lists as untracked while a command runs, and
# removes it when the command ends, unless the sandbox is killed: both seen in the pilot project's first implement
# run, whose agent saw all nine in every `git status` and whose bundle step found none.
ROOT_MOUNTS=".bash_profile .bashrc .gitconfig .profile .ripgreprc .zprofile .zshrc .idea .vscode"
# Excluded where none exists, so the agent never stages one, or spends turns on a file it can't remove. No trailing
# slash: the placeholder is a file, which /.vscode/ wouldn't match. Only where none exists: a project's own stays seen.
# Then the profile's tool state, which its tools write in the checkout (ASP.NET Core's .aspnet/, say). The same
# patterns go in $CHECKS/excludes, which the sandbox can't write, since whether Claude Code keeps the job's lines in
# .git/info/exclude when it writes its own isn't seen yet: bundle's check reads that copy.
excludes() {
  local profile=$1 p patterns=()
  for p in $ROOT_MOUNTS; do
    if [ ! -e "$p" ] && [ ! -L "$p" ]; then patterns+=("/$p"); fi
  done
  if [ -f "$here/profiles/$profile/excludes" ]; then
    while IFS= read -r p; do
      case $p in ''|'#'*) continue ;; esac
      [[ $p =~ ^[A-Za-z0-9._/*-]+$ ]] || { echo "::error::profiles/$profile/excludes: not a plain pattern: $p"; exit 1; }
      patterns+=("$p")
    done < "$here/profiles/$profile/excludes"
  fi
  mkdir -p .git/info
  # A last line without its newline would take the first pattern onto it.
  if [ -s .git/info/exclude ] && [ -n "$(tail -c 1 .git/info/exclude)" ]; then echo >> .git/info/exclude; fi
  : > "$CHECKS/excludes"
  for p in ${patterns[@]+"${patterns[@]}"}; do
    grep -qxF -- "$p" .git/info/exclude 2> /dev/null || echo "$p" >> .git/info/exclude
    echo "$p" >> "$CHECKS/excludes"
  done
  chmod 644 "$CHECKS/excludes"
}
cmd=${1:-}
if [ $# -gt 0 ]; then shift; fi

case "$cmd" in
  freeze)
    install -d -m 700 "$CHECKS"
    install -m 644 "$here"/*.py "$here"/*.schema.json "$CHECKS/"
    install -m 755 "$here"/*.sh "$CHECKS/"
    install -m 644 "$here/factory.json" "$CHECKS/"
    # The browser route's wrapper and smoke probe (D6).
    install -m 755 "$here/with-browser" "$CHECKS/"
    install -m 644 "$here"/*.mjs "$CHECKS/"
    # The stack profile's scripts, at the same path below $CHECKS.
    stack
    install -d -m 700 "$CHECKS/profiles/$profile"
    find "$here/profiles/$profile" -maxdepth 1 -type f -exec install -m 755 {} "$CHECKS/profiles/$profile/" \;
    for f in "$@"; do install -m 644 "$here/$f" "$CHECKS/"; done
    ;;

  services)
    # The profile's throwaway test services, their settings into the project's env file (gitignored;
    # the env scrub strips credential-named variables from sandboxed Bash, so they go in a file), or
    # into the file named.
    stack
    out=${1:-$GITHUB_WORKSPACE/$env_file}
    "$here/profiles/$profile/test-services.sh" "$GITHUB_WORKSPACE/.factory/db" "$database" > "$out"
    ;;

  mcp)
    cfg="$RUNNER_TEMP/factory-mcp.json"
    if [ -n "${CONTEXT7_API_KEY:-}" ]; then
      jq -n '{mcpServers:{context7:{type:"http",url:"https://mcp.context7.com/mcp",headers:{CONTEXT7_API_KEY:"${CONTEXT7_API_KEY}"}}}}' > "$cfg"
    else
      jq -n '{mcpServers:{context7:{type:"http",url:"https://mcp.context7.com/mcp"}}}' > "$cfg"
    fi
    echo "FACTORY_MCP_CONFIG=$cfg" >> "$GITHUB_ENV"
    echo "$cfg"
    ;;

  workspace)
    stack
    # Sandboxed Bash reaches the test services (started outside the sandbox) only through this wrapper,
    # and runs the project's checks with verify (the factory's skills name it, not the commands).
    install -D -m 755 "$here/profiles/$profile/with-test-services" /opt/factory/with-test-services
    install -D -m 755 "$here/profiles/$profile/verify" /opt/factory/verify
    # Every stage has the wrapper; without browser.conf (agent_job.sh browser) it reports the browser host
    # unavailable, so a run without the route says `blocked` rather than guessing.
    install -D -m 755 "$here/with-browser" /opt/factory/with-browser
    printf 'python=%s\nnode=%s\ndatabase=%s\n' "$python_dir" "$node_dir" "$database" > /opt/factory/verify.conf
    # The config file each Node tool loads in the checkout, recorded before the agent starts: verify pins
    # them, and fails when a file added since would replace one (node_configs.py).
    install -D -m 644 "$here/node_configs.py" /opt/factory/node_configs.py
    /usr/local/bin/python3 -I "$here/node_configs.py" record "$node_dir" >> /opt/factory/verify.conf \
      || { echo "::error::node_configs.py couldn't record the Node tools' config files in $node_dir"; exit 1; }
    chmod 644 /opt/factory/verify.conf
    "$here/profiles/$profile/install.sh" "$python_dir" "$node_dir"
    # Paths this project's code reads, moved into the workspace: the sandbox's root is read-only (the
    # model directory, /app/ml_models by default).
    jq -r '.stack.env // {} | to_entries[] | "\(.key)=\(env.GITHUB_WORKSPACE)/\(.value)"' "$here/factory.json" >> "$GITHUB_ENV"
    # The agent commits locally as the factory; the publish job pushes the commits unchanged.
    app
    git config user.name "$app_login"
    git config user.email "$app_id+$app_login@users.noreply.github.com"
    excludes "$profile"
    # quiesce compares the hooks after the agent (the sandbox can't write them; this proves it).
    find .git/hooks -type f -exec sha256sum {} + | sort > "$CHECKS/git-hooks.sha256"
    ;;

  excludes)
    [[ ${1:-} =~ ^[a-z0-9-]+$ ]] && [ -d "$here/profiles/$1" ] || { echo "::error::excludes: no profile ${1:-}"; exit 2; }
    excludes "$1"
    ;;

  browser)
    stage=$1 settings=$2
    /usr/local/bin/python3 -I "$here/browser.py" "$here/factory.json" "$stage" "$GITHUB_WORKSPACE" "$settings" \
      /opt/factory/browser.conf
    ;;

  issue-context)
    base=$1 id=${2:-}
    # The agent gets the issue as a file, so it needs no GitHub access of its own.
    gh issue view "$ISSUE_NUMBER" -R "$GITHUB_REPOSITORY" \
      --json number,title,body,author,labels,state,url,comments > "$RUNNER_TEMP/issue.json"
    install -d "$GITHUB_WORKSPACE/.factory"
    jq --arg base "$base" --arg id "$id" '{repo: env.GITHUB_REPOSITORY, base: $base}
        + (if $id == "" then {} else {deliverable: $id} end)
        + {issue: {number, title, body, author: .author.login, labels: [.labels[].name], state, url},
           comments: [.comments[] | {author: .author.login, author_association: .authorAssociation,
                                     created_at: .createdAt, body}]}' \
      "$RUNNER_TEMP/issue.json" > "$GITHUB_WORKSPACE/.factory/issue-context.json"
    ;;

  schema)
    name=$1
    [[ $name =~ ^[a-z][a-z-]*$ ]] || { echo "::error::bad schema name $name"; exit 1; }
    # claude_args wraps the schema in single quotes.
    if grep -q "'" "$here/$name.schema.json"; then
      echo "::error::$name.schema.json must not contain single quotes"; exit 1
    fi
    var=FACTORY_$(tr 'a-z-' 'A-Z_' <<< "$name")_SCHEMA
    echo "$var=$(jq -c . "$here/$name.schema.json")" >> "$GITHUB_ENV"
    ;;

  advisor)
    # --advisor needs a model; for none it is passed but the tool is switched off.
    case "$1" in
      none) { echo "FACTORY_ADVISOR=opus"; echo "CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1"; } >> "$GITHUB_ENV" ;;
      opus|fable) echo "FACTORY_ADVISOR=$1" >> "$GITHUB_ENV" ;;
      *) echo "::error::unknown advisor $1" >&2; exit 1 ;;
    esac
    ;;

  revise-context)
    merge_base=$1 stage=${2:-} document=${3:-} deliverable=${4:-}
    app
    # CD's review since the last revision: maintainers only, never bots, oldest first.
    since=$(gh api "repos/$GITHUB_REPOSITORY/issues/$PR/comments" --paginate \
            --jq '.[] | select(.user.type == "Bot" and .user.id == '"$app_id"' and (.body | test("\\A<!-- factory-revise: "))) | .created_at' \
            | sort | tail -1)
    since=${since:-1970-01-01T00:00:00Z}
    trusted='(.user.type != "Bot") and (.author_association | IN("OWNER", "MEMBER", "COLLABORATOR"))'
    {
      gh api "repos/$GITHUB_REPOSITORY/pulls/$PR/reviews" --paginate \
        --jq ".[] | select($trusted and (.submitted_at // \"\") > \"$since\" and (.body // \"\") != \"\")
              | {kind: \"review\", state, author: .user.login, created_at: .submitted_at, body}"
      gh api "repos/$GITHUB_REPOSITORY/pulls/$PR/comments" --paginate \
        --jq ".[] | select($trusted and .created_at > \"$since\")
              | {kind: \"inline\", author: .user.login, created_at, path, line: (.line // .original_line), body}"
      gh api "repos/$GITHUB_REPOSITORY/issues/$PR/comments" --paginate \
        --jq ".[] | select($trusted and .created_at > \"$since\")
              | {kind: \"comment\", author: .user.login, created_at, body}"
    } | jq -s 'sort_by(.created_at)' > "$RUNNER_TEMP/requests.json"
    n=$(jq length "$RUNNER_TEMP/requests.json")
    echo "Requests since the last revision: $n" >> "$GITHUB_STEP_SUMMARY"
    [ "$n" -gt 0 ] || { echo "::error::no review comments since the last revision"; exit 1; }
    install -d "$GITHUB_WORKSPACE/.factory"
    gh api "repos/$GITHUB_REPOSITORY/pulls/$PR" --jq .body > "$RUNNER_TEMP/body.md"
    jq -n --arg pr "$PR" --arg issue "$ISSUE_NUMBER" --arg branch "$BRANCH" --arg base "$BASE" \
          --arg merge_base "$merge_base" --arg revision "$REVISION" --arg limit "$REVISION_LIMIT" \
          --arg stage "$stage" --arg document "$document" --arg deliverable "$deliverable" --arg plan "${PLAN:-}" \
          --arg gate "${NEXT_GATE:-}" --rawfile body "$RUNNER_TEMP/body.md" --slurpfile requests "$RUNNER_TEMP/requests.json" \
      '{pr: ($pr | tonumber), issue: ($issue | tonumber)}
       + (if $plan == "" then {} else {plan: $plan} end) + (if $gate == "" then {} else {gate: $gate} end)
       + (if $stage == "" then {} else {stage: $stage, document: $document, deliverable: $deliverable} end)
       + {branch: $branch, base: $base, merge_base: $merge_base,
          revision: ($revision | tonumber), limit: ($limit | tonumber), body: $body, requests: $requests[0]}' \
      > "$GITHUB_WORKSPACE/.factory/revise-context.json"
    ;;

  quiesce)
    # Killed sandboxes become zombies (the container's init never reaps them); only live ones count.
    pkill -9 -x bwrap || true
    sleep 1
    if ps -eo stat=,comm= | awk '$2 == "bwrap" && $1 !~ /^Z/ { found = 1 } END { exit !found }'; then
      echo "::error::sandbox processes survived the agent step"; exit 1
    fi
    # Before any git: refuse a repository the agent could have booby-trapped.
    "$here/git_guard.sh" "$CHECKS/git-hooks.sha256"
    ;;

  bundle)
    base=$1 bundle=$2 status=$3
    shift 3
    # Hooks and fsmonitor off, and never into a nested repository (git_guard.sh ran first). The status check reads the
    # frozen copy of the job's excludes, whatever .git/info/exclude now holds.
    g() { git -c core.hooksPath=/dev/null -c core.fsmonitor=false -c diff.ignoreSubmodules=all "$@"; }
    gx() { g -c core.excludesFile="$CHECKS/excludes" "$@"; }
    # For the job log, in every run: what the sandbox left at the root, and the exclude's patterns, which show whether
    # Claude Code keeps the job's lines (not seen yet: D2 rule 4), and whether a placeholder outlives its command.
    # Only the fixed names, and patterns of plain characters, are printed: the log reads workflow commands.
    seen=""
    for p in $ROOT_MOUNTS; do
      if [ -L "$p" ]; then st=symlink
      elif [ -f "$p" ]; then st="file of $(wc -c < "$p" | tr -d ' ') bytes"
      elif [ -d "$p" ]; then st=directory
      elif [ -e "$p" ]; then st=other
      else st=absent; fi
      seen="$seen $p: $st;"
    done
    echo "At the root after the agent:${seen%;}"
    if [ -f .git/info/exclude ] && [ ! -L .git/info/exclude ]; then
      echo ".git/info/exclude: $(wc -l < .git/info/exclude | tr -d ' ') lines, $(grep -c '^#' .git/info/exclude || true) of them comments. Its patterns:"
      grep -v '^#' .git/info/exclude | grep -xE '[A-Za-z0-9._/*!-]{1,100}' | head -40 | sed 's/^/  /' || true
    else
      echo ".git/info/exclude: none"
    fi
    n=$(g rev-list --count "$base..HEAD")
    echo "Commits since the base: $n" >> "$GITHUB_STEP_SUMMARY"
    publishes=no
    for s in "$@"; do
      if [ "$s" = "$status" ]; then publishes=yes; fi
    done
    [ "$publishes" = yes ] || exit 0
    [ "$n" -gt 0 ] || { echo "::error::status $status but the agent made no commit"; exit 1; }
    install -d -m 700 "$(dirname "$bundle")"
    g bundle create -q "$bundle" "$base..HEAD"
    # The bundle is uploaded either way, so the commits survive for CD; publish won't run.
    echo "bundle=yes" >> "$GITHUB_OUTPUT"
    # The sandbox's mount points at the root (ROOT_MOUNTS): one a killed sandbox left (quiesce kills one that outlived
    # the agent) is an empty, untracked placeholder, so remove it. A tracked one is the check's below; any other
    # untracked one fails it too, named here when only the job's excludes hide it, and not when the project ignores it.
    left=""
    for p in $ROOT_MOUNTS; do
      if g ls-files --error-unmatch -- "$p" > /dev/null 2>&1; then continue
      elif [ ! -L "$p" ] && [ -f "$p" ] && [ ! -s "$p" ]; then rm -f -- "$p"; echo "removed the sandbox's empty placeholder $p"
      elif [ ! -L "$p" ] && [ -d "$p" ] && [ -z "$(ls -A -- "$p")" ]; then
        rmdir -- "$p"; echo "removed the sandbox's empty placeholder $p/"
      elif [ -e "$p" ] || [ -L "$p" ]; then
        case $(gx check-ignore -v -- "$p" 2> /dev/null || true) in .git/info/exclude:*|"$CHECKS/excludes":*) left="$left $p" ;; esac
      fi
    done
    # Every untracked file, not only its directory, so a failure names what wrote it.
    changes=$(gx status --porcelain --untracked-files=all --ignore-submodules=all; for p in $left; do echo "?? $p"; done)
    if [ -n "$changes" ]; then
      echo "incomplete=yes" >> "$GITHUB_OUTPUT"
      echo "::error::status $status but the agent left uncommitted changes:"; printf '%s\n' "$changes" | head -20 || true
      exit 1
    fi
    ;;

  stats)
    echo "stats=$(jq -c '[.[] | select(.type == "result")] | last | {cost: .total_cost_usd, turns: .num_turns, models: (.modelUsage // {} | keys)}' "$EXEC")" >> "$GITHUB_OUTPUT"
    ;;

  lost)
    who=$1
    # The time limit, the turn limit or a crash leaves no execution file: the session files are all there is.
    out=$("$here/session_log.sh" "$RUNNER_TEMP/agent-start" "$RUNNER_TEMP/session-log" "$AGENT_MINUTES" "${EXEC:-}")
    printf '%s\n' "$out" >> "$GITHUB_OUTPUT"
    why=$(sed -n 's/^why=//p' <<< "$out")
    echo "::error::The $who agent $why."
    echo "The $who agent $why. Session log kept: $(sed -n 's/^saved=//p' <<< "$out")" >> "$GITHUB_STEP_SUMMARY"
    ;;

  metrics)
    install -d "$RUNNER_TEMP/metrics"
    /usr/local/bin/python3 -I "$here/run_metrics.py" "$1" "${ISSUE_NUMBER:-0}" "$RUNNER_TEMP/metrics/metrics.json"
    ;;

  *)
    echo "usage: agent_job.sh freeze|mcp|services|workspace|excludes|browser|issue-context|schema|advisor|revise-context|quiesce|bundle|stats|lost|metrics ..." >&2
    exit 2
    ;;
esac
