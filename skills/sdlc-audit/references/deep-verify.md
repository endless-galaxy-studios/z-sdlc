# Deep Verify — Retroactive Knowledge Content Verification (Opt-In)

An **opt-in** sdlc-audit mode that re-judges already-promoted knowledge-store content using the multi-judge mechanics of the Promotion Verification Gate (`[sdlc-root]/process/discipline_capture.md` § Promotion Verification Gate). The gate verifies content on its way *into* the store; Deep Verify catches what is already inside — entries that predate the gate, drifted since ingestion, or contradict the code they describe.

**Never part of a default audit run.** This mode activates only when the user requests it by name (`/sdlc-audit deep-verify`, "deep audit", "verify the knowledge store", "full content sweep") — the same opt-in shape as `[sdlc-root]/process/external-review-gate.md` ("disabled by default; activates only when..."). A routine `/sdlc-audit` invocation must never trigger it: the default dimensions are file reads and greps; this mode is dozens of judge dispatches and (if an external wrapper is configured) hosted-model egress.

**Orchestrator-run, not auditor-run.** The `sdlc-compliance-auditor` subagent does not execute this mode — it requires `AskUserQuestion` gates, judge dispatches, and egress disclosure, none of which a read-only subagent can do. The skill orchestrator drives it directly.

## Why this exists

The first at-scale retroactive run (674 entries) found 45 entries with real defects — roughly 1 in 15 — in content that had sat unreviewed since ingestion. Representative defect: an entry whose `description` claimed all four effect base classes "processed through EffectResolutionPipeline" while the entry's own `pipeline:` field (and the live source file) showed the pipeline handles only two — an internal contradiction uncaught since the entry was authored, predating provenance tracking. Ingestion-time review does not catch post-ingestion drift; this mode does, on whatever cadence the project chooses.

## Workflow

```
PRE-FLIGHT → SCOPE → PAYLOAD → JUDGE → TRIAGE (step 11) → APPLY → PROVENANCE
```

### 1. Pre-flight confirmation (mandatory)

Count the entries in the proposed scope, then present ONE `AskUserQuestion` covering:

- **Cost estimate:** entry count → approximate external-wrapper calls (entries ÷ batch size), subagent dispatches, expected tie-breaks (plan for ~15–20% of entries, the observed split rate at scale), plus the frontier once-over dispatches.
- **Egress disclosure:** if `[sdlc-root]/external-review-knowledge.sh` exists and calls a hosted model, state plainly that knowledge-store content will be sent to that provider (name the model per the gate's disclosure rule).
- **Scope selection:**

| Scope | What gets judged |
|-------|------------------|
| Full store | Every claim-bearing entry in `[sdlc-root]/knowledge/` |
| Domain-scoped | One or more domains (e.g., "just architecture") |
| Stale-only | Entries in files whose §6h staleness age exceeds a threshold |
| Incremental | Entries ingested/changed since the last `source-type: audit-sweep` provenance entry |

Never start judging without CD's confirmation of scope and cost.

### 2. Scope the content — claims vs. reference

Deep Verify judges **claims** (assertions about how systems behave, thresholds, patterns, gotchas). It does not judge **reference material** (pure legend/convention files, format specs, files whose content is mechanically verified against code elsewhere) or **event records** (`provenance_log.md` itself, ledgers). Exclude those categories from the payload — judging them produces noise verdicts.

**Flag, don't decide:** if a file's classification is ambiguous (part claims, part reference), surface it to CD in the pre-flight question rather than silently including or excluding it.

### 3. Build payloads

Apply the gate's payload rules (step 1: neutral, numbered, no verdicts; corroboration signals where available — at store scale the entry's own internal consistency is the primary evidence surface). Batch entries into payloads of roughly 25–30 to keep each judge call tractable. Use the extraction script below rather than hand-authoring.

### 4. Judge

Run the gate's steps 2–5 unchanged, with verdicts read as `KEEP|DEMOTE` instead of `PROMOTE|DEMOTE`:

- **Screening tier:** external wrapper (mid-tier model, `high` effort) + `opus` subagent, both with the mandatory fact-checking instructions — the defect class this mode exists for (stale thresholds, wrong protocol semantics, internal contradictions) is exactly what the fact-check lens catches and the pattern-recognition lens misses. Do not drop the external judge's effort to the project's ambient default; the at-scale run showed a low-effort screening pass under-catches real errors.
- **Splits:** frontier-tier tie-break judge, blind, 2–1 majority applies.
- **Frontier once-over:** the keep-bound slate gets the gate's step-5 once-over — in retroactive mode the asymmetric risk is identical (a wrongly-kept entry compounds as precedent; a wrongly-demoted entry goes to triage where CD sees it anyway). Include its dispatches in the pre-flight cost estimate.
- **Deep Verify never applies a demotion itself.** DEMOTE verdicts become candidates for step 11 triage.

### 5. Route findings into step 11 — no parallel triage flow

DEMOTE verdicts enter the existing interactive triage (compliance methodology step 11) as a third candidate source alongside §6c/6l promotion candidates and Dimension 8 memory patterns. Each candidate carries: the entry text, source location (`file.yaml::key` or `file.yaml::key[field=value]`), both judges' verdicts and reasoning (plus tie-break reasoning if split), and the proposed action (demote to `[NEEDS VALIDATION]`).

Present grouped by discipline per step 11b. **Batch-level approval is acceptable** (per the §6c authority matrix demotion row): CD may approve a discipline's demotions as a batch rather than one-by-one — at scale, per-entry adjudication is exactly the failure mode the tie-break judge exists to prevent. Entries whose dissent alleges a specific checkable factual error, or whose verdict was split, are listed individually with reasoning; CD may pull any entry out of a batch.

### 6. Apply approved demotions (step 11c demote path)

For each approved demotion:

1. **Remove the entry from the knowledge YAML** with the comment-preserving script below — never a `yaml.safe_load()`/`safe_dump()` round-trip, which destroys hand-authored `# =====` comment banners. Review the git diff after each removal.
   - **The script leaves a removal mark where it was:** ``# PROJECT-SECTION-REMOVED: demote-YYYY-MM-DD-<slug> `<target>` — <why, in a few words>; CD, YYYY-MM-DD``. The target is the one the payload named: its top-level key (`error_design`), or `key[field=value]` for an item in a key's list (`gotchas[id=playwright-cli-open-url]`). Without it, the next migration takes the entry back from upstream, since an entry the project removed looks exactly like one upstream added (`[sdlc-root]/process/project-section-markers.md` § The Three Kinds of Change). An entry upstream never had needs the mark too: it costs nothing, and migration drops it quietly later. In a file the project replaced as a whole, nothing is marked (the script knows).
2. **Restore a parking-lot entry** in the relevant `[sdlc-root]/disciplines/*.md` under `## Parking Lot`, marked `[NEEDS VALIDATION]`, with the demoting judges' reasoning appended inline (so the next triage pass sees why it came back).
3. **Fix ledger forward-pointers:** grep the entry's key across `[sdlc-root]/disciplines/*.md` for `Promoted →` lines referencing it; update or remove them so the ledger doesn't point at a deleted entry.
4. **Bump the knowledge file's `last_updated`** (or equivalent metadata field, if present).

### 7. Provenance

Append one entry to `[sdlc-root]/knowledge/provenance_log.md` documenting the sweep itself, using `source-type: audit-sweep`: scope, judge configuration (models and effort levels actually used), counts (entries judged / kept / demoted / tie-breaks / once-over dissents), and the commit reference for the applied demotions. This entry is also the boundary marker the "incremental" scope option keys off next time.

## Reusable Scripts

Materialize these to the session scratchpad at run time (they are not installed as executables). Both address entries by target, as a removal mark names them (`[sdlc-root]/process/project-section-markers.md` § Target Grammar): `file.yaml::top_level_key`, or `file.yaml::key[field=value]` for an item of a key's list.

**Payload extraction** — `safe_load` is fine here because the payload is disposable; it is the store file that must never round-trip:

```python
#!/usr/bin/env python3
"""Emit a numbered, verdict-free judge payload from knowledge YAML files, one entry per target: a top-level key,
or each item of a top-level key's list, named by a field whose value is unique there (file.yaml::key[field=value])."""
import sys, yaml

FILE_METADATA_KEYS = {"id", "name", "description", "pattern", "category", "spec_relevant", "project_applicability",
                      "last_updated", "version", "sources"}
ID_FIELDS = ("id", "rule_id", "key", "name")  # [sdlc-root]/process/project-section-markers.md § Target Grammar


def naming_field(items):
    """The first of ID_FIELDS, then any other scalar field, that every item has with a value only it has."""
    others = sorted({f for i in items for f, v in i.items() if isinstance(v, (str, int))} - set(ID_FIELDS))
    for f in (*ID_FIELDS, *others):
        values = [str(i.get(f)) for i in items if isinstance(i.get(f), (str, int)) and "]" not in str(i.get(f))]
        if len(values) == len(items) and len(set(values)) == len(values):
            return f
    return None


n = 0
for path in sys.argv[1:]:
    data = yaml.safe_load(open(path))
    if not isinstance(data, dict):
        print(f"skipped {path}: not a mapping at the top", file=sys.stderr)
        continue
    for key, val in data.items():
        if key in FILE_METADATA_KEYS:
            continue
        field = None
        if isinstance(val, list) and val and all(isinstance(i, dict) for i in val):
            field = naming_field(val)
        for target, body in ([(f"{key}[{field}={i[field]}]", i) for i in val] if field else [(key, {key: val})]):
            n += 1
            print(f"## {n}. {path}::{target}")
            print(yaml.safe_dump(body, sort_keys=False, width=100))
            print("---")
```

**Comment-preserving entry removal** — line-based, so `# =====` banners and inline comments survive: the comment lines just above the next entry are that entry's, and stay. It writes the removal mark in the removed entry's place, at its indent, refuses a target that names no item or more than one, and refuses one inside a marked block. In a file the project replaced as a whole (`` `*` ``) it removes the entry and writes no mark, since that file is the project's:

```python
#!/usr/bin/env python3
"""Remove one knowledge YAML entry without round-tripping the file, and leave its removal mark where it was.
Usage: remove_entry.py <file.yaml> <target> <label> <why> [<who>]
<target> is a key, as a dotted path from the top level (error_design, internal_doc_authoring.rules), optionally
naming one item of that key's list by a field whose value only it has (gotchas[id=some-id]).
Line-based, so comments survive: the comment lines and blank lines just above the next entry are that entry's, and
stay. It refuses a target inside a marked block (edit the block instead); in a file the project replaced as a whole
(`*`) it removes the entry and writes no mark, since the file is the project's. Review the git diff after each run."""
import datetime, re, sys

path, target, label, why = sys.argv[1:5]
who = sys.argv[5] if len(sys.argv) > 5 else "CD"
m = re.fullmatch(r"([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)(?:\[([A-Za-z0-9_]+)=([^\]]+)\])?", target)
if not m:
    sys.exit(f"not a target: {target}")
keys, field, value = m.group(1).split("."), m.group(2), m.group(3)
lines = open(path).readlines()
indent = lambda line: len(line) - len(line.lstrip())
content = lambda line: bool(line.strip()) and not line.lstrip().startswith("#")
is_item = lambda line: line.lstrip().startswith("-") and line.lstrip()[1:2] in (" ", "\n", "")
unquote = lambda v: re.sub(r"\s+#.*$", "", v).strip().strip("'\"")


def block_end(first, level, limit):
    """The line after the block that starts at `first`: the next content line at `level` or less (a key's own list
    may sit at its indent), less the comment and blank lines just above it, which belong to what follows."""
    key_block = not is_item(lines[first])
    stop = next((j for j in range(first + 1, limit) if content(lines[j]) and indent(lines[j]) <= level
                 and not (key_block and indent(lines[j]) == level and is_item(lines[j]))), limit)
    while stop > first + 1 and not content(lines[stop - 1]):
        stop -= 1
    return stop


# Whole-line marks ([sdlc-root]/process/project-section-markers.md rule 8): blocks the target must not sit in, and `*`.
marks = [(i, re.match(r"\s*#\s*PROJECT-SECTION-(START|END):\s*(\S+)(.*)", l)) for i, l in enumerate(lines)]
opened, blocks, whole = {}, [], False
for i, mk in marks:
    if mk and mk.group(1) == "START":
        opened[mk.group(2)] = i
        whole = whole or bool(re.search(r"replaces\s+`\*`", mk.group(3)))
    elif mk and mk.group(2) in opened:
        blocks.append((opened.pop(mk.group(2)), i))

lo, hi, level = 0, len(lines), 0
for key in keys:  # walk the dotted path, one mapping level at a time
    start = next((i for i in range(lo, hi) if content(lines[i]) and indent(lines[i]) == level and not is_item(lines[i])
                  and re.match(r"\s*" + re.escape(key) + r":(\s|$)", lines[i])), None)
    if start is None:
        sys.exit(f"no key {'.'.join(keys)} in {path}")
    end = block_end(start, level, hi)
    child = next((indent(lines[j]) for j in range(start + 1, end) if content(lines[j])), level + 2)
    lo, hi, level, at = start + 1, end, child, indent(lines[start])
if field:  # one item of the key's list: from its "- " line to the next line at its indent or less
    items = [i for i in range(lo, hi) if content(lines[i]) and is_item(lines[i])]
    dash = min((indent(lines[i]) for i in items), default=None)
    found, siblings = [], 0
    for i in (i for i in items if indent(lines[i]) == dash):
        siblings += 1
        stop = block_end(i, dash, hi)
        col = len(lines[i]) - len(lines[i].lstrip(" -"))  # where the item's own keys start
        for line in lines[i:stop]:
            hit = re.fullmatch(r"[\s-]*" + re.escape(field) + r":\s*(.+?)\s*", line.rstrip("\n"))
            if hit and len(line) - len(line.lstrip(" -")) == col and unquote(hit.group(1)) == value:
                found.append((i, stop))
                break
    if len(found) != 1:
        sys.exit(f"{target} names {len(found)} items in {path}, not one")
    (start, end), at = found[0], dash
    if siblings == 1:
        print(f"warning: {target} was the list's only item; the key is left empty", file=sys.stderr)
if any(a < start < b for a, b in blocks) and not whole:
    sys.exit(f"{target} is inside a marked block: edit the block instead")
mark = [] if whole else [" " * at + f"# PROJECT-SECTION-REMOVED: {label} `{target}` — {why}; {who}, "
                                    f"{datetime.date.today().isoformat()}\n"]
open(path, "w").writelines(lines[:start] + mark + lines[end:])
print(f"removed {target} (lines {start + 1}-{end})" + ("" if whole else " and marked it"))
```

## Cadence

Not scheduled, not automatic. Sensible triggers a project might choose: after a large ingestion, after a refactor that invalidates recorded patterns, or when §6h shows a large cohort of files older than the last `audit-sweep` provenance entry. The observed base rate (~1 defect per 15 entries in never-reverified content) is the argument for running it at all; the cost profile is the argument for not running it by default.

## Red Flags

| Thought | Reality |
|---------|---------|
| "The audit found knowledge issues, I'll deep-verify while I'm here" | Opt-in means opt-in. Report the finding; let CD invoke the sweep. |
| "The auditor subagent can run the judges" | It can't `AskUserQuestion` or disclose egress. Orchestrator only. |
| "I'll just re-dump the YAML after removing the entry" | Round-tripping destroys comment banners. Use the removal script and check the diff. |
| "This reference file looks like claims, I'll include it" | Ambiguous classification goes to CD in pre-flight, not silently decided. |
| "45 demotions — I'll ask CD about each one" | Batch approval per discipline, individual listing only for factual-error dissents and splits. |
| "The judges confirmed DEMOTE, I'll apply it now" | Verdicts are candidates. Demotions apply only after step 11 triage approval. |
