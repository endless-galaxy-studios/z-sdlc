#!/usr/bin/env bash
# A factory branch, read in an agent job and written in a writer job. Run in the repository.
# Usage: factory_branch.sh <command> [args]
#
#   fetch <branch>        fetch refs/heads/<branch> with READ_TOKEN (sent as a header, never stored)
#                         and print its commit
#   check <branch> <head> <code|doc>
#                         fetch <branch>, refuse it unless it is still at <head>, and refuse any path
#                         it changes since its merge base with HEAD (the default branch) that main's
#                         CODEOWNERS owns or that is agent or gate configuration; doc also refuses
#                         anything outside the document stages' paths. Anyone with write access can
#                         push to a factory branch, and the job loads its agent configuration and runs
#                         its dependency manifests (the publish guard refused those paths in every
#                         factory commit, so a factory branch has none). Prints nothing on success.
#   switch <head>         detach at <head> with HEAD's agent configuration, CODEOWNERS and services list
#                         (services.py and services.json, which the stage's MCP step runs from the
#                         working tree) laid over the branch's older copy and hidden from git: the run
#                         has current skills, path rules and services, and nothing of them can be
#                         committed (tracked copies are skip-worktree, new files excluded)
#   push <branch> <base>  (writer job) fast-forward <branch> from <base> to $RUNNER_TEMP/out/head
#                         with GH_TOKEN, refusing if the branch moved since the run started
# check and switch run in an agent job before its agent, from the frozen copy in $CHECKS; check reads
# CODEOWNERS from the workspace, so it runs before switch.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
cmd=${1:-}
if [ $# -gt 0 ]; then shift; fi

fetch() {
  local auth
  auth="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$READ_TOKEN" | base64 -w0)"
  GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.extraheader GIT_CONFIG_VALUE_0="$auth" git fetch -q origin "refs/heads/$1"
  git rev-parse FETCH_HEAD
  rm -f .git/FETCH_HEAD
}

case "$cmd" in
  fetch)
    fetch "$1"
    ;;

  check)
    branch=$1 head=$2 kind=$3
    case "$kind" in code|doc) ;; *) echo "::error::unknown branch kind $kind"; exit 1 ;; esac
    fetched=$(fetch "$branch")
    [ "$fetched" = "$head" ] || { echo "::error::$branch is at $fetched, not $head (pushed to since this run started); re-run"; exit 1; }
    merge_base=$(git merge-base HEAD "$head")
    if git diff --name-only "$merge_base" "$head" | python3 -I -c '
import sys; sys.path.insert(0, sys.argv[1]); import implement_guard as g
patterns = g.codeowners_patterns(open(".github/CODEOWNERS").read())
bad = [p for p in sys.stdin.read().split() if g.agent_config(p) or g.protected(p, patterns)
       or (sys.argv[2] == "doc" and not p.startswith(g.DOC_STAGE_PATHS))]
if bad:
    print("\n".join(bad))
sys.exit(1 if bad else 0)' "$here" "$kind"; then :; else
      echo "::error::$branch changes paths this stage may not (above); not using it"; exit 1
    fi
    ;;

  switch)
    head=$1
    main=$(git rev-parse HEAD)
    git checkout -q --detach "$head"
    cfg=(.claude CLAUDE.md CLAUDE.local.md .mcp.json .github/CODEOWNERS .github/factory/services.py .github/factory/services.json)
    git ls-files -z -- "${cfg[@]}" | xargs -0 -r git update-index --skip-worktree
    git archive "$main" -- $(git ls-tree --name-only "$main" -- "${cfg[@]}") | tar -x
    git ls-files --others --exclude-standard -- "${cfg[@]}" >> .git/info/exclude
    ;;

  push)
    branch=$1 base=$2
    remote="https://x-access-token:${GH_TOKEN}@github.com/${GH_REPO}.git"
    now=$(git ls-remote "$remote" "refs/heads/$branch" | cut -f1)
    [ "$now" = "$base" ] || { echo "::error::$branch moved since this run started ($base -> $now); not pushing"; exit 1; }
    git -c core.hooksPath=/dev/null push --quiet "$remote" "$(cat "$RUNNER_TEMP/out/head"):refs/heads/$branch"
    ;;

  *)
    echo "usage: factory_branch.sh fetch|check|switch|push ..." >&2
    exit 2
    ;;
esac
