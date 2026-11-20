#!/usr/bin/env bash
# What the report jobs do around posting an agent's result as the factory App: factory-implement.yml's
# and factory-plan.yml's report jobs and factory-triage.yml's apply job, on a GitHub-hosted runner, from
# the default branch. The text filters are in report.jq.
# Usage: report.sh <command> [args]
#
#   check <stage> <result.json> <fields>
#                  refuse to post (exit 1) when any of <fields>, a jq expression giving the strings the
#                  job posts (for example '[.reason, .questions[]]'), holds a credential-like string, an
#                  image or an embed
#   labels <new> [fable|none]
#                  make <new> (a factory:* state label, or empty for none) the issue's only state label;
#                  factory:advisor, factory:follow-up, factory:go and factory:needs-repro are properties and stay. fable adds
#                  factory:advisor, none removes it.
# Environment: ISSUE_NUMBER; GH_TOKEN and GH_REPO for labels.
# Tested in CI by tests/test_report.py.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
cmd=${1:-}
if [ $# -gt 0 ]; then shift; fi

case "$cmd" in
  check)
    stage=$1 result=$2 fields=$3
    if jq -L "$here" -e "include \"report\"; $fields | any(credential_like)" "$result" > /dev/null; then
      echo "::error::$stage output contains a credential-like string; not posting"; exit 1
    fi
    if jq -L "$here" -e "include \"report\"; $fields | any(embed)" "$result" > /dev/null; then
      echo "::error::$stage output contains an image or embed; not posting"; exit 1
    fi
    ;;

  labels)
    new=$1 advisor=${2:-}
    old=$(gh issue view "$ISSUE_NUMBER" --json labels \
          -q "[.labels[].name | select(startswith(\"factory:\") and . != \"$new\" and (IN(\"factory:advisor\", \"factory:follow-up\", \"factory:go\", \"factory:needs-repro\") | not))] | join(\",\")")
    add=$new
    case "$advisor" in
      "") ;;
      fable) add="${add:+$add,}factory:advisor" ;;
      none)
        if [ "$(gh issue view "$ISSUE_NUMBER" --json labels -q '[.labels[].name] | index("factory:advisor") != null')" = true ]; then
          old="${old:+$old,}factory:advisor"
        fi ;;
      *) echo "::error::unknown advisor $advisor"; exit 1 ;;
    esac
    if [ -n "$add$old" ]; then
      gh issue edit "$ISSUE_NUMBER" ${add:+--add-label "$add"} ${old:+--remove-label "$old"}
    fi
    ;;

  *)
    echo "usage: report.sh check|labels ..." >&2
    exit 2
    ;;
esac
