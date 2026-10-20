#!/usr/bin/env bash
# The revise stages' gate (F15/F16): is this an open factory PR the requester may have revised, and is
# it under its revision limit? Run by the gate job of factory-revise.yml (code) and
# factory-revise-doc.yml (doc), on a GitHub-hosted runner, from the default branch.
# Usage: revise_gate.sh <code|doc>
# Environment: PR, REQUESTER, REVISION_LIMIT, RUN_URL, GH_REPO; GH_TOKEN (the job's read-only token)
# and APP_TOKEN (the App's issues token: the requester notice, the limit comment and the labels).
# Writes proceed=true and the PR's facts to $GITHUB_OUTPUT when the revision may run (for a code PR, the
# plan it executes and that plan's next gate, if any); proceed=false otherwise. Exits 1 when the PR isn't
# one this stage revises.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
# The factory App's bot user (factory.json, beside this script).
app_id=$(jq -r .app.user_id "$here/factory.json")
[[ $app_id =~ ^[0-9]+$ ]] || { echo "::error::factory.json has no app.user_id"; exit 1; }
kind=${1:-}
case "$kind" in
  code) pattern='^factory/([0-9]+)-impl$'; what="factory code PR" ;;
  doc) pattern='^factory/([0-9]+)-(spec|plan)$'; what="factory spec or plan PR" ;;
  *) echo "usage: revise_gate.sh code|doc" >&2; exit 2 ;;
esac

# REST issue endpoints: the App token is issues-only, and gh pr uses GraphQL, which needs more.
say() { GH_TOKEN="$APP_TOKEN" gh api "repos/$GH_REPO/issues/$PR/comments" -f body="$1 <sub>factory revise · [run]($RUN_URL)</sub>" > /dev/null; }
unlabel() { GH_TOKEN="$APP_TOKEN" gh api -X DELETE "repos/$GH_REPO/issues/$PR/labels/factory:revise" > /dev/null 2>&1 || true; }
echo "proceed=false" >> "$GITHUB_OUTPUT"
pr="$RUNNER_TEMP/pr.json"
gh api "repos/$GH_REPO/pulls/$PR" > "$pr"
head=$(jq -r .head.ref "$pr")
if [[ ! $head =~ $pattern ]] || [ "$(jq -r .state "$pr")" != open ] \
   || [ "$(jq -r .head.repo.full_name "$pr")" != "$GH_REPO" ] || [ "$(jq -r .user.id "$pr")" != "$app_id" ]; then
  echo "::error::PR #$PR isn't an open $what"; exit 1
fi
issue=${BASH_REMATCH[1]}
stage=${BASH_REMATCH[2]:-code}
perm=$(gh api "repos/$GH_REPO/collaborators/$REQUESTER/permission" --jq .permission 2> /dev/null || echo none)
case "$perm" in admin|maintain|write) ;; *) unlabel; say "Revisions need a reviewer with write access."; exit 0 ;; esac

if [ "$kind" = doc ]; then
  # The PR's document, and the planning skill that wrote it.
  # Doubled backslashes: the pattern lands inside a jq string literal.
  if [ "$stage" = spec ]; then docpattern='^docs/current_work/specs/d[0-9]+[a-z]?_[a-z0-9_]+_spec\\.md$'
  else docpattern='^docs/current_work/(sdlc-lite|planning)/d[0-9]+[a-z]?_[a-z0-9_]+_plan\\.md$'; fi
  docs=$(gh api "repos/$GH_REPO/pulls/$PR/files" --paginate --jq ".[] | select(.status != \"removed\") | .filename | select(test(\"$docpattern\"))")
  [ "$(grep -c . <<< "$docs")" = 1 ] || { echo "::error::PR #$PR doesn't add or change exactly one $stage document"; exit 1; }
  case "$docs" in
    docs/current_work/sdlc-lite/*) skill=sdlc-lite-plan ;;
    *) skill=sdlc-plan ;;
  esac
  deliverable=$(basename "$docs" | sed -E 's/^d([0-9]+[a-z]?)_.*/D\1/')
else
  # An execution PR's plan, which a revision may stop at a production gate of: the one its gate tracker
  # names, or else the sibling of the one result doc the PR adds, if that plan is on the default branch and
  # is for the issue's own deliverable (the ID the plan stage reserved on the issue, as the App). Empty for
  # a direct fix.
  gh api "repos/$GH_REPO/issues/$PR/comments" --paginate --jq '.[]' > "$RUNNER_TEMP/comments.ndjson"
  plan=$(python3 -I "$here/gates.py" plan-path --comments "$RUNNER_TEMP/comments.ndjson" --app-id "$app_id") || plan=""
  if [ -z "$plan" ]; then
    results=$(gh api "repos/$GH_REPO/pulls/$PR/files" --paginate \
              --jq '.[] | select(.status == "added") | .filename | select(test("^docs/current_work/(sdlc-lite|results)/d[0-9]+[a-z]?_[a-z0-9_]+_result\\.md$"))')
    if [ "$(grep -c . <<< "$results")" = 1 ]; then
      plan=$(sed -E -e 's#^docs/current_work/results/#docs/current_work/planning/#' -e 's/_result\.md$/_plan.md/' <<< "$results")
      # The reservation as the plan stage reads it: the latest by the App or, before 2026-10-09, github-actions.
      reserved=$(gh api "repos/$GH_REPO/issues/$issue/comments" --paginate \
                 --jq '.[] | select(.user.type == "Bot" and (.user.id == '"$app_id"' or .user.login == "github-actions[bot]")) | .body | capture("\\A<!-- factory-id: (?<id>D[0-9]+[a-z]?) -->")? | .id' | tail -1)
      ours=$(basename "$plan" | sed -E 's/^d([0-9]+[a-z]?)_.*/D\1/')
      if [ "$ours" != "$reserved" ]; then
        echo "::warning::$results is for $ours, but issue #$issue reserved ${reserved:-no ID}: no production gate for this revision"
        plan=""
      fi
    fi
  fi
  # The plan as it is on the default branch, and its next gate this PR hasn't passed (by the broker's signed
  # results): the one gate a revision may stop before. Empty when the plan has none left, and in a project
  # with no production runner (no receipt key), where no gate can run.
  next_gate=""
  if [ -n "$plan" ]; then
    if ! gh api "repos/$GH_REPO/contents/$plan" -H "Accept: application/vnd.github.raw" > "$RUNNER_TEMP/plan.md" 2> /dev/null; then
      plan=""
    elif [ -f "$here/production/receipt.pub" ]; then
      next_gate=$(python3 -I - "$here" "$RUNNER_TEMP/plan.md" "$RUNNER_TEMP/comments.ndjson" "$app_id" "$PR" <<'PY'
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
import gates  # noqa: E402
factory, plan, comments, app_id, pr = sys.argv[1:]
public = (pathlib.Path(factory) / "production" / "receipt.pub").read_text().strip()
state = gates.pr_state([json.loads(line) for line in pathlib.Path(comments).read_text().splitlines() if line.strip()],
                       int(app_id), public, int(pr))
try:
    print(next((g["id"] for g in gates.parse_gates(pathlib.Path(plan).read_text())
                if gates.gate_status(state, g["id"])[0] != "done"), ""))
except gates.Invalid:
    print("")
PY
) || { echo "::warning::couldn't read the gates of $plan: no production gate for this revision"; next_gate=""; }
    fi
  fi
fi

# Earlier revisions: the App's factory-revise markers on the PR (matched by the App's user ID).
done_=$(gh api "repos/$GH_REPO/issues/$PR/comments" --paginate \
        --jq '[.[] | select(.user.type == "Bot" and .user.id == '"$app_id"' and (.body | test("\\A<!-- factory-revise: [0-9]+ -->")))] | length' \
        | awk '{s += $1} END {print s + 0}')
revision=$((done_ + 1))
if [ "$revision" -gt "$REVISION_LIMIT" ]; then
  unlabel
  if [ "$kind" = code ]; then
    say "**Revision limit reached** ($REVISION_LIMIT for a code PR): no more automatic revisions. Push the changes yourself, or close the PR and re-triage the issue."
  else
    say "**Revision limit reached** ($REVISION_LIMIT for a $stage PR): no more automatic revisions. A document that needs another round usually needs a conversation: continue in an interactive \`sdlc-plan\` session on \`$head\` (it can read this review), push the changes yourself, or close the PR to stop."
  fi
  GH_TOKEN="$APP_TOKEN" gh issue edit "$issue" --add-label factory:escalated > /dev/null
  exit 0
fi
{
  echo "issue=$issue"; echo "branch=$head"; echo "base=$(jq -r .head.sha "$pr")"; echo "revision=$revision"
  if [ "$kind" = doc ]; then
    echo "stage=$stage"; echo "document=$docs"; echo "deliverable=$deliverable"; echo "skill=$skill"
  else
    echo "plan=$plan"; echo "next_gate=$next_gate"
  fi
  echo "proceed=true"
} >> "$GITHUB_OUTPUT"
if [ "$kind" = code ]; then
  echo "Revision $revision of $REVISION_LIMIT for PR #$PR (issue #$issue${plan:+, executing $plan}${next_gate:+, next gate $next_gate})" >> "$GITHUB_STEP_SUMMARY"
else
  echo "Revision $revision of $REVISION_LIMIT for $stage PR #$PR (issue #$issue, $docs, /$skill)" >> "$GITHUB_STEP_SUMMARY"
fi
