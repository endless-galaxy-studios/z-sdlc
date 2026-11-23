#!/usr/bin/env bash
# dotnet-node profile: install the project's dependencies before the agent runs, outside the sandbox
# (implement's sandbox has no network at all). Run by agent_job.sh workspace from the frozen copy, in
# the workspace, after the test services start and after any secret is out of the environment: this
# runs the project's dependency manifests.
# Usage: install.sh <dotnet-dir> <node-dir>
#   <dotnet-dir> (its solution or project, and its local tools) gets `dotnet restore`; <node-dir>
#   gets `pnpm install --frozen-lockfile`.
set -euo pipefail

dotnet_dir=$1 node_dir=$2
[ -f "$node_dir/pnpm-lock.yaml" ] || { echo "install.sh: no pnpm-lock.yaml in $node_dir (this profile installs with pnpm)" >&2; exit 1; }
# HOME is unreadable in the sandbox and the root is read-only: .NET's home, the NuGet packages and
# the data directory (NuGet writes there, and with no HOME into the working directory, where the
# untracked file would stop the run's publish) live in the workspace's .factory/. No build or
# compiler server may outlive a command, and nothing on first run writes outside the workspace
# (telemetry, the HTTPS development certificate). NuGet's audit needs the network: it runs here,
# and is off in the sandbox, where a restore can only work from these packages. ASP.NET Core keeps its
# data protection keys under $LOCALAPPDATA/ASP.NET when it's set, before it tries HOME (its
# DefaultKeyStorageDirectories): with a relative HOME in the sandbox it made .aspnet/ in the server's
# working directory, which stopped the pilot project's first implement run's publish (reproduced with
# HOME=.; an empty or unset HOME gives in-memory keys and no folder).
factory=$GITHUB_WORKSPACE/.factory
install -d "$factory/dotnet-home" "$factory/nuget" "$factory/xdg-data" "$factory/local-app-data" "$factory/pnpm-store"
settings=(
  "DOTNET_CLI_HOME=$factory/dotnet-home"
  "NUGET_PACKAGES=$factory/nuget"
  "XDG_DATA_HOME=$factory/xdg-data"
  "LOCALAPPDATA=$factory/local-app-data"
  DOTNET_NOLOGO=1
  DOTNET_CLI_TELEMETRY_OPTOUT=1
  DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
  DOTNET_GENERATE_ASPNET_CERTIFICATE=false
  MSBUILDDISABLENODEREUSE=1
  UseSharedCompilation=false
)
export "${settings[@]}"

(cd "$dotnet_dir" && dotnet restore --verbosity quiet)
if [ -f "$dotnet_dir/.config/dotnet-tools.json" ] || [ -f "$dotnet_dir/dotnet-tools.json" ]; then
  (cd "$dotnet_dir" && dotnet tool restore)
fi
(cd "$node_dir" && pnpm install --frozen-lockfile --store-dir "$factory/pnpm-store" --reporter=append-only)

printf '%s\n' "${settings[@]}" NuGetAudit=false >> "$GITHUB_ENV"
