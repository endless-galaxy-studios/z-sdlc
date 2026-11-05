# Factory job image: the container every factory job runs in (F4), for the python-uv-node profile.
# Tooling only; project dependencies are installed by the jobs that need them.
# Python 3.12 with uv (one or more uv projects, each with its own uv.lock), Node 22 with pnpm 10, and the
# test services such a stack's suites use: Postgres 17 with pgvector, and Redis 7.
# Built and pushed to GHCR by .github/workflows/factory-image.yml.
FROM node:22-bookworm-slim AS node

# The factory's own steps are Python, and some call /usr/local/bin/python3 by path.
FROM python:3.12-slim-bookworm

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
# pnpm as a plain package, not corepack (which keeps its downloads under HOME). A project's
# packageManager pin may name another version: install.sh runs pnpm with network, so pnpm fetches it.
RUN npm install -g --no-audit --no-fund --loglevel=error pnpm@10.34.7
# uv, at /usr/local/bin/uv, on PATH in the sandbox too (a project's tests may call it offline). Python
# downloads stay off: every uv project uses this image's 3.12.
RUN pip install --no-cache-dir --root-user-action=ignore uv==0.13.5
ENV UV_PYTHON_DOWNLOADS=never

# curl/unzip: the action installs Claude Code (install.sh) and Bun (zip) each run.
# bubblewrap/socat: Claude Code's Bash sandbox (process namespace and network proxy).
# postgresql-17 with postgresql-17-pgvector (PGDG; bookworm ships 15 without pgvector) and redis-server
# (7.0): throwaway test services for stages that run the test suite. test-services.sh starts them on the
# job container's loopback; their apt postinstall clusters and init scripts are never used.
# pgbouncer: the planning tier's database proxy (design rule D3). It holds the read-only login's
# password where the agent can't read it and serves the agent's connections on loopback.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash bubblewrap ca-certificates curl git gnupg jq netcat-openbsd openssh-client procps socat unzip \
 && install -d -m 755 /etc/apt/keyrings \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      | gpg --dearmor -o /etc/apt/keyrings/postgresql.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends gh postgresql-17 postgresql-17-pgvector redis-server pgbouncer \
 && rm -rf /var/lib/apt/lists/*

# Redis must carry the 2025 Lua fixes (CVE-2025-49844, -46817, -46818, -46819; DSA-6020-1): EVAL stays
# enabled for projects that script Redis. Debian backports them without changing 7.0.15, so compare the package.
RUN dpkg --compare-versions "$(dpkg-query -W -f '${Version}' redis-server)" ge '5:7.0.15-1~deb12u6' \
 || { echo "redis-server predates the Lua CVE fixes (DSA-6020-1)" >&2; exit 1; }
# pgvector 0.8 (halfvec, sparsevec, iterative index scans), as the pgvector/pgvector:pg17 images CI uses.
RUN dpkg --compare-versions "$(dpkg-query -W -f '${Version}' postgresql-17-pgvector)" ge '0.8.0' \
 || { echo "postgresql-17-pgvector predates 0.8" >&2; exit 1; }

RUN node --version && npm --version && pnpm --version && python3 --version && uv --version \
 && gh --version && jq --version && bwrap --version && socat -V | head -2 \
 && /usr/lib/postgresql/17/bin/postgres --version && redis-server --version && pgbouncer --version
