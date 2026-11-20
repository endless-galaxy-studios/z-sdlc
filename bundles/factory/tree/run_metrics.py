"""Write one agent run's metrics record for the weekly improve loop (factory-improve.yml reads them).

Usage: python3 -I run_metrics.py <stage> <issue> <out.json>
       (inputs in the environment, each optional: EXEC, the agent step's execution file; RESULT, its
       structured output; LOST, session_log.sh's reason when the step returned nothing; INPUTS, a JSON
       object of the dispatch inputs; RUN_ID, RUN_ATTEMPT and WORKFLOW, from the job)

Every agent job runs this last, whatever happened, and uploads the record as the `factory-metrics`
artifact (35 days), so the improve loop never races the 7-day transcripts (CD, 2026-10-10: metrics are
recorded at the source). The record is an allowlist: enums, numbers, model IDs and step-free facts,
never agent text. A value it can't read is null, which the loop reads as unknown, not zero.
"""

import json
import os
import re
import sys

STAGES = {"triage", "reproduce", "implement", "execute", "plan", "spec", "revise", "improve"}
# Every stage's outcome values (triage returns `state`; the others `status`).
STATUSES = {"ready-for-dispatch", "ready-to-plan", "needs-input", "wait", "done", "escalated", "rescope",
            "failed", "awaiting-approval", "split", "reproduced", "partially-reproduced", "not-reproduced", "blocked"}
INPUT_KEYS = {"tier", "advisor", "model", "compare"}
INPUT_VALUE = re.compile(r"^[a-z0-9.-]{0,40}$")
MODEL = re.compile(r"^claude-[a-z0-9.-]{1,60}$")
SUBTYPE = re.compile(r"^[a-z_]{1,40}$")
RUN_ID = re.compile(r"^[0-9]{1,20}$")


def number(value, integer=False):
    """A non-negative number (an integer when asked), or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    if integer:
        return int(value) if float(value).is_integer() else None
    return value


def last_result(exec_text):
    """The runtime's closing `result` record, or {}."""
    try:
        events = json.loads(exec_text)
    except ValueError:
        return {}
    results = [e for e in events if isinstance(e, dict) and e.get("type") == "result"] if isinstance(events, list) else []
    return results[-1] if results else {}


def outcome(result_text):
    """The stage's status from its structured output, if it's one the factory knows."""
    try:
        result = json.loads(result_text)
    except ValueError:
        return None
    if not isinstance(result, dict):
        return None
    value = result.get("status", result.get("state"))
    return value if value in STATUSES else None


def lost(why):
    """session_log.sh's phrase, reduced to a kind."""
    if not why:
        return None
    if "error_max_turns" in why:
        return "turn-limit"
    if "limit after" in why:
        return "time-limit"
    return "no-result"


def inputs(text):
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(v).lower() for k, v in data.items()
            if k in INPUT_KEYS and isinstance(v, (str, bool)) and INPUT_VALUE.match(str(v).lower())}


def record(stage, issue, env):
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}")
    exec_text = ""
    if env.get("EXEC") and os.path.isfile(env["EXEC"]):
        with open(env["EXEC"], encoding="utf-8", errors="replace") as f:
            exec_text = f.read()
    final = last_result(exec_text) if exec_text else {}
    models = final.get("modelUsage") if isinstance(final.get("modelUsage"), dict) else {}
    denials = final.get("permission_denials")
    subtype = final.get("subtype")
    return {
        "v": 1,
        "stage": stage,
        "issue": int(issue) if str(issue).isdigit() and int(issue) > 0 else None,
        "workflow": env.get("WORKFLOW") if re.match(r"^factory-[a-z-]{1,30}$", env.get("WORKFLOW") or "") else None,
        "run_id": int(env["RUN_ID"]) if RUN_ID.match(env.get("RUN_ID") or "") else None,
        "run_attempt": int(env["RUN_ATTEMPT"]) if RUN_ID.match(env.get("RUN_ATTEMPT") or "") else None,
        "status": outcome(env.get("RESULT") or ""),
        "end": subtype if isinstance(subtype, str) and SUBTYPE.match(subtype) else None,
        "lost": lost(env.get("LOST") or ""),
        "cost": number(final.get("total_cost_usd")),
        "turns": number(final.get("num_turns"), True),
        "duration_ms": number(final.get("duration_ms"), True),
        "models": sorted(m for m in models if isinstance(m, str) and MODEL.match(m)),
        "denials": len(denials) if isinstance(denials, list) else None,
        "inputs": inputs(env.get("INPUTS") or ""),
    }


def main():
    stage, issue, out = sys.argv[1:4]
    with open(out, "w") as f:
        json.dump(record(stage, issue, os.environ), f, separators=(",", ":"))
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
