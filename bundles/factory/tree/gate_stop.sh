#!/usr/bin/env bash
# A revision that stopped before a production gate (design rule D4), as execute's report job does at a gate
# stop: the gate tracker on the PR (created on the first stop, updated after), the issue's factory:gate
# label, and the gate run, asked of factory-gate-request.yml for the commit the revision pushed. Run by the
# stop-at-gate job of factory-revise.yml, from the default branch, after the revision comment. Every step
# can run again.
# Environment: PR, ISSUE_NUMBER, GH_REPO, RUN_URL, DEFAULT_BRANCH, RUNNER_TEMP; RESULT (the agent's result),
# PLAN and NEXT_GATE (from the gate job), PUBLISHED_HEAD (the commit the publish job pushed); GH_TOKEN (the
# App's issues token) and READ_TOKEN (the job's token: the reads and the dispatch).
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
app_id=$(jq -r .app.user_id "$here/factory.json")
[[ $app_id =~ ^[0-9]+$ ]] || { echo "::error::factory.json has no app.user_id"; exit 1; }
# The publish job's guard held the result to the plan's next gate; so does this.
gate=$(printf '%s' "$RESULT" | jq -r .gate)
if [ -z "$PLAN" ] || [ -z "$NEXT_GATE" ] || [ "$gate" != "$NEXT_GATE" ]; then
  echo "::error::the revision stopped before '$gate', not the plan's next gate (${NEXT_GATE:-none left})"; exit 1
fi
[[ $PUBLISHED_HEAD =~ ^[0-9a-f]{40}$ ]] || { echo "::error::no pushed commit to ask for the gate on"; exit 1; }

t=$RUNNER_TEMP
GH_TOKEN="$READ_TOKEN" gh api "repos/$GH_REPO/pulls/$PR" > "$t/pr.json"
GH_TOKEN="$READ_TOKEN" gh api "repos/$GH_REPO/issues/$PR/comments" --paginate --jq '.[]' > "$t/comments.ndjson"
GH_TOKEN="$READ_TOKEN" gh api "repos/$GH_REPO/contents/$PLAN?ref=$DEFAULT_BRANCH" > "$t/plan.json"
python3 -I "$here/gates.py" tracker --repo "$GH_REPO" --app-id "$app_id" --factory-dir "$here" --pr-json "$t/pr.json" \
  --comments "$t/comments.ndjson" --plan-meta "$t/plan.json" --plan "$PLAN" --stopped-at "$gate" --out "$t/tracker.md"
tracker=$(jq -r 'select(.user.id == '"$app_id"' and (.body | startswith("<!-- factory-gate-tracker: "))) | .id' "$t/comments.ndjson" | head -1)
if [ -n "$tracker" ]; then
  gh api -X PATCH "repos/$GH_REPO/issues/comments/$tracker" -F body=@"$t/tracker.md" > /dev/null
else
  gh api "repos/$GH_REPO/issues/$PR/comments" -F body=@"$t/tracker.md" > /dev/null
fi
# The issue's state: stopped at a gate (no longer review-capped).
"$here/report.sh" labels factory:gate

# The gate run only for the commit this revision pushed, which the publish job checked: a push since then is
# code the factory didn't check. The tracker stays, so factory:gate-retry can ask for the gate once CD has
# looked at it. factory-gate-request.yml checks the head again when it builds the request.
head=$(jq -r .head.sha "$t/pr.json")
if [ "$head" != "$PUBLISHED_HEAD" ]; then
  gh api "repos/$GH_REPO/issues/$PR/comments" -f body="**No gate run requested:** the branch moved after this revision was pushed (\`${PUBLISHED_HEAD:0:7}\` to \`${head:0:7}\`), and the factory asks for $gate only on code it checked. Review the new commits, then add \`factory:gate-retry\` to ask for $gate on them. <sub>factory revise · [run]($RUN_URL)</sub>" > /dev/null
  echo "PR #$PR: revision stopped before $gate; the branch moved, so no gate run was requested" >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi
# A run still waiting on an older request is cancelled there as stale.
GH_TOKEN="$READ_TOKEN" gh workflow run factory-gate-request.yml --ref "$DEFAULT_BRANCH" -f pr="$PR" -f head="$PUBLISHED_HEAD"
echo "PR #$PR: revision stopped before $gate; gate run requested" >> "$GITHUB_STEP_SUMMARY"
