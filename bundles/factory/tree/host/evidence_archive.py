#!/usr/bin/env python3
"""Pull the factory's browser evidence into a long-term archive before GitHub's 90 days run out (process/factory.md
D6 rule 7). Run by a systemd timer on the host that keeps the archive, as its own user (setup-archive.sh installs
both), never as a runner user.

Usage: python3 -I evidence_archive.py <config.json> [--dry-run]

config.json (root-owned, readable by the archive's user):
  {"root": "/srv/factory-evidence", "token_file": "/etc/factory-evidence/token",
   "repos": ["owner/repository", ...], "days": 14}
The token is read-only: Actions read on those repositories, nothing else.

For each repository it lists the completed runs of factory-implement.yml and factory-revise.yml on the default branch
from the last `days` days (90 by default, GitHub's retention), every page, and takes only their evidence artifacts:
evidence.json, evidence-report.html (which holds the run's video, unless it was too big) and evidence-video.webm, the
video when it wasn't inside the report. The Playwright trace, a desktop debugging tool, isn't kept past GitHub's 90
days (CD, 2026-11-22). Any workflow can upload a file by
those names, so a run of another workflow, on another branch, from another repository (a fork) or started by another
event is skipped. A run it has finished with, archived or holding no evidence, is listed in <root>/.seen-runs, so a
later pull asks nothing more about it. The run's evidence.json names its issue (evidence.py writes it from the
job's own environment), and the files go to <root>/<repository name>/<issue>/<run id>/, the path the PR names.

Never overwrites: a run already archived (its evidence.json is there) is skipped, and a file is written to a
temporary name, then renamed. Every name and number it writes under is checked first. A file that fails to download
is retried on the next run, and any failure exits 1, so the timer's unit shows as failed. A re-run's later attempt
isn't archived apart from the first one pulled.
"""

import io
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile

API = "https://api.github.com"
WORKFLOWS = ("factory-implement.yml", "factory-revise.yml")
# How each is started: implement by dispatch or a person's label, revise only by dispatch.
EVENTS = {"factory-implement.yml": {"workflow_dispatch", "issues"}, "factory-revise.yml": {"workflow_dispatch"}}
MAX_PAGES = 30
EVIDENCE = ("evidence.json", "evidence-report.html", "evidence-video.webm")
REPO = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")
MAX_FILE = 200 << 20


class Skip(Exception):
    pass


def make_api(token):
    """GET <path> on the GitHub API as the token: (status, body bytes). Redirects (artifact downloads) are followed
    without the token, which belongs to GitHub's API and never goes to the storage host."""

    class NoAuthOnRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            new = super().redirect_request(req, fp, code, msg, headers, newurl)
            if new is not None:
                new.remove_header("Authorization")
            return new

    opener = urllib.request.build_opener(NoAuthOnRedirect)

    def api(path):
        req = urllib.request.Request(path if path.startswith("https://") else API + path, headers={
            "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "factory-evidence-archive"})
        try:
            with opener.open(req, timeout=60) as r:
                return r.status, r.read(MAX_FILE + 1)
        except urllib.error.HTTPError as e:
            return e.code, b""
        except (urllib.error.URLError, OSError):
            return 0, b""
    return api


def get_json(api, path):
    status, body = api(path)
    if status != 200:
        raise Skip(f"GET {path}: {status}")
    return json.loads(body)


def unwrap(name, body):
    """An artifact's file. An unzipped artifact downloads as the file itself; a zipped one as a zip holding it."""
    if body[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                names = z.namelist()
                if names == [name]:
                    info = z.getinfo(name)
                    if info.file_size > MAX_FILE:
                        raise Skip(f"{name} is over {MAX_FILE} bytes")
                    return z.read(name)
        except zipfile.BadZipFile:
            pass
    return body


def write_new(path, data):
    tmp = path.with_name(f".{path.name}.part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def pull_run(api, repo, run, root, dry_run=False):
    """One run's evidence into root: the files written, or [] when there's nothing (more) to pull."""
    arts = get_json(api, f"/repos/{repo}/actions/runs/{run['id']}/artifacts?per_page=100").get("artifacts") or []
    found = {a["name"]: a for a in arts if a.get("name") in EVIDENCE and not a.get("expired")}
    if "evidence.json" not in found:
        return []
    status, body = api(f"/repos/{repo}/actions/artifacts/{found['evidence.json']['id']}/zip")
    if status != 200:
        raise Skip(f"evidence.json of run {run['id']}: {status}")
    record = json.loads(unwrap("evidence.json", body))
    if not isinstance(record, dict):
        raise Skip(f"run {run['id']}'s evidence.json isn't a record")
    issue, run_id = record.get("issue"), record.get("run")
    if not isinstance(issue, int) or isinstance(issue, bool) or issue <= 0 or run_id != run["id"]:
        raise Skip(f"run {run['id']}'s evidence.json doesn't name its issue and this run")
    where = root / repo.split("/")[1] / str(issue) / str(run["id"])
    if (where / "evidence.json").exists():
        return []
    if dry_run:
        return [str(where / n) for n in found]
    where.mkdir(parents=True, exist_ok=True)
    written = []
    for name in EVIDENCE[1:]:
        if name not in found:
            continue
        status, body = api(f"/repos/{repo}/actions/artifacts/{found[name]['id']}/zip")
        if status != 200 or len(body) > MAX_FILE:
            raise Skip(f"{name} of run {run['id']}: {status or 'unreachable'}")
        write_new(where / name, unwrap(name, body))
        written.append(str(where / name))
    # The record last: its presence says the run is archived.
    write_new(where / "evidence.json", json.dumps(record, indent=2).encode() + b"\n")
    return written + [str(where / "evidence.json")]


def runs(api, repo, days, now=None):
    """The completed implement and revise runs on the default branch from the last `days` days, the factory's own:
    this repository's, started the way the factory starts them, and not skipped (a label event that ran nothing)."""
    default = get_json(api, f"/repos/{repo}")["default_branch"]
    since = time.strftime("%Y-%m-%d", time.gmtime((now or time.time()) - days * 86400))
    for wf in WORKFLOWS:
        for n in range(1, MAX_PAGES + 1):
            page = get_json(api, f"/repos/{repo}/actions/workflows/{wf}/runs?branch={default}&status=completed"
                                 f"&created=%3E%3D{since}&per_page=100&page={n}")
            listed = page.get("workflow_runs") or []
            for run in listed:
                if (run.get("path", "").split("@")[0] == f".github/workflows/{wf}" and run.get("head_branch") == default
                        and (run.get("head_repository") or {}).get("full_name") == repo
                        and run.get("event") in EVENTS[wf] and run.get("conclusion") != "skipped"):
                    yield run
            if len(listed) < 100:
                break


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv[1:]
    config = json.loads(pathlib.Path(args[0]).read_text())
    root = pathlib.Path(config["root"])
    repos = config["repos"]
    if not root.is_absolute() or not isinstance(repos, list) or not all(isinstance(r, str) and REPO.fullmatch(r) for r in repos):
        print("config: root must be absolute and repos a list of owner/repository", file=sys.stderr)
        return 2
    api = make_api(pathlib.Path(config["token_file"]).read_text().strip())
    seen_file = root / ".seen-runs"
    seen = set(seen_file.read_text().split()) if seen_file.exists() else set()
    failed = 0
    for repo in repos:
        try:
            for run in runs(api, repo, int(config.get("days", 90))):
                key = f"{repo}#{run['id']}"
                if key in seen:
                    continue
                try:
                    for path in pull_run(api, repo, run, root, dry_run):
                        print(("would write " if dry_run else "wrote ") + path)
                    seen.add(key)
                except Exception as e:  # noqa: BLE001 - one bad run must never stop the rest
                    failed += 1
                    print(f"{repo}: run {run.get('id')}: {type(e).__name__}: {e}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"{repo}: {type(e).__name__}: {e}", file=sys.stderr)
    if not dry_run:
        write_new(seen_file, ("\n".join(sorted(seen)) + "\n").encode())
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
