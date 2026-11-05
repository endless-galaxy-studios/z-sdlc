#!/usr/bin/env bash
# python-uv-node profile: install the project's dependencies before the agent runs, outside the sandbox
# (implement's sandbox has no network at all). Run by agent_job.sh workspace from the frozen copy, in
# the workspace, after the test services start and after any secret is out of the environment: this
# runs the project's dependency manifests.
# Usage: install.sh <python-dir> <node-dir>
#   Every top-level directory holding a uv.lock beside its pyproject.toml is a uv project, and gets
#   `uv sync --locked` (its dev group included); <python-dir> must be one of them. <node-dir> gets
#   `pnpm install --frozen-lockfile`.
set -euo pipefail

python_dir=$1 node_dir=$2
# The uv projects, as verify finds them. A factory commit can't add one: uv.lock and pyproject.toml are
# code-owned at any depth (process/factory.md, § Stack Profiles).
projects=()
for lock in */uv.lock; do
  [ -f "$lock" ] && [ -f "${lock%/uv.lock}/pyproject.toml" ] && projects+=("${lock%/uv.lock}")
done
[ ${#projects[@]} -gt 0 ] || { echo "install.sh: no top-level directory has a uv.lock and a pyproject.toml" >&2; exit 1; }
printf '%s\n' "${projects[@]}" | grep -qxF "${python_dir%/}" \
  || { echo "install.sh: $python_dir (stack.python) isn't a uv project: it has no uv.lock beside a pyproject.toml" >&2; exit 1; }
[ -f "$node_dir/pnpm-lock.yaml" ] || { echo "install.sh: no pnpm-lock.yaml in $node_dir (this profile installs with pnpm)" >&2; exit 1; }

# HOME is unreadable in the sandbox and the root is read-only: the caches live in the workspace's
# .factory/, which is gitignored, so a tool's cache never leaves an untracked file that stops the publish.
# In the sandbox uv is offline (no network): it may read what this install cached, never fetch.
factory=$GITHUB_WORKSPACE/.factory
install -d "$factory/uv-cache" "$factory/pnpm-store" "$factory/mypy-cache" "$factory/ruff-cache"
settings=(
  "UV_CACHE_DIR=$factory/uv-cache"
  UV_PYTHON_DOWNLOADS=never
  UV_PYTHON=/usr/local/bin/python3
  UV_NO_PROGRESS=1
  "MYPY_CACHE_DIR=$factory/mypy-cache"
  "RUFF_CACHE_DIR=$factory/ruff-cache"
)
export "${settings[@]}"

for project in "${projects[@]}"; do
  (cd "$project" && uv sync --locked --quiet)
done
(cd "$node_dir" && pnpm install --frozen-lockfile --store-dir "$factory/pnpm-store" --reporter=append-only)

printf '%s\n' "${settings[@]}" UV_OFFLINE=1 >> "$GITHUB_ENV"
