# Runbooks

A **runbook** is a procedure a project runs once, or now and then, rather than as everyday work: enabling a
bundle, setting up a host, rotating a credential. It is a process doc, or a section of one, that `sdlc-run-runbook`
drives in a session with CD present: it finds where the procedure stands, takes it one step at a time, runs each
step's check, and writes what was decided and what passed to the runbook's record, so a later session picks up
where this one stopped.

## A skill or a runbook (CD, 2026-11-16)

**Skills are for repeatable work; a one-time or rare procedure is a runbook.** Every installed skill's description
is loaded on every turn of every session, whether or not it's used (Claude Code's skills docs), so a skill that
runs once per project costs context for the rest of the project's life. One generic skill, `sdlc-run-runbook`, drives
every runbook instead. Before creating a skill (`zsdlc-create-skill`, `sdlc-develop-skill`), ask whether it would
run more than a few times in a project: if not, write a runbook.

## What makes a doc a runbook

**The marker line.** A runbook opens (the doc's first lines, or its section's first line) with exactly one line in
this form, which is how `sdlc-run-runbook` and `sdlc-status` find it in `[sdlc-root]/process/`:

```
**Runbook:** `<id>` · **When:** <enable | setup | on-demand> · **Record:** `<project path>` § <section>
```

A line is a marker only in this full form, outside a code fence, with a real id (the template above isn't
one): a gate's `**Runbook:**` checklist in a plan
(`[sdlc-root]/process/production-gates.md`) is something else, CD's steps for one gate, and has no id.

- **id:** lowercase words joined by hyphens, unique across the framework (a repository test checks it).
- **When:**
  - `enable`: once per project, after its bundle is installed. `sdlc-initialize` and `sdlc-migrate` offer to
    start it when the bundle is installed.
  - `setup`: once per project, for a core feature every project gets but not every project uses (the external
    review gate, the verify command). `sdlc-initialize` offers it during the install, and `sdlc-migrate`
    offers each one the project has no record of, so a project installed before it existed is offered it too.
    The offer has three answers: now; later, which writes nothing, so the next migration offers it again; or not
    for this project, for which whoever made the offer writes the record with **Status** `declined` and the date,
    and nothing offers it again (`sdlc-run-runbook <id>` still runs it). Its first step finds what the project already has
    (a wrapper, a command) and records it, so a project that set the feature up by hand finishes quickly.
  - `on-demand`: when its trigger happens; the runbook's first paragraph names the trigger.
- **Record:** the project file and section where the run is written down. A runbook with no natural home
  for one records in `docs/runbooks/<id>.md`. The configuration a runbook fills is not its record: a config
  block can't say which checks passed or where the run stands.

**Its body:**
- **Numbered steps.** The doc's own numbers are the step IDs: its sections' (`3.3`), or for a numbered item
  inside a section, the section and the item (`3.3 item 6`). Never another doc's numbers: a runbook item that
  cites "factory.md step 9" is still `3.3 item 6`. Records, handoffs and other docs cite the IDs, so a
  published runbook never renumbers: a new step takes a new number, and a dropped one stays, marked dropped.
- **The order to take them in,** when it isn't the numbering (the factory's runs § 2's survey before § 1's
  questions), said at the top.
- **Each step says what is done, who does it, and how to tell it worked.** A step only CD can do (a credential, a
  dashboard, a root shell, a decision) is marked **[CD]**. A step's **Check:** is something that can be run or
  read, not "looks right".
- **A definition of done**, and, when the run starts with decisions, the questions to ask up front, each with its
  recommended answer and its alternatives. An item a decision makes inapplicable says so ("if § 1 C3 chose a
  production tier").
- **A decision the runbook itself records** ("decided org-wide", "CD, 2026-11-12") isn't asked again: the run
  writes it to its Decisions as decided, with its source.

## The record

`sdlc-run-runbook` keeps these parts, and adds any that are missing (a record written before this convention, or
by hand) on its first run, without rewriting what's there:

- **Status:** `not started`, `in progress` or `done` (with the date); for a `setup` runbook CD turned down when
  it was offered, `declined` (with the date).
- **Next:** the step ID the next session starts at, and what it does first.
- **Decisions:** each question, the answer in CD's words, the date, the session (its date and the branch or
  handoff it worked from), and later whether it was built, deferred or dropped. A decision relayed from another
  session is confirmed in this one before anything acts on it. A session's ground rules (what may be pushed
  while it runs) are decisions too, written with that session.
- **State:** each step's ID, the date, and how it ended: `passed` (its check, and what the check showed),
  `done` (a step with no check, such as questions answered), `skipped` (a step a decision made inapplicable, and
  which decision), or `failed` (the check, and what it showed). The run resumes at the first step that isn't
  passed, done or skipped.
- **Deferred:** what was left for later, and who owns it.

A runbook that runs across several sessions also ends each of its phases with a committed handoff
(`sdlc-handoff`): what's done, what's next and what's decided, in the repository rather than a session's memory.

## After migrating

A bundle's process doc may have a section headed exactly `## After migrating`: the checks a release can make
due (re-running a host's setup when a file it installs changed, say). It is not a runbook: it has no record and
no resume. `sdlc-migrate` follows it itself, after copying the bundle's files, and puts what it found in the
migration report.

## Integration

- **Driven by:** `sdlc-run-runbook`
- **Listed by:** `sdlc-status`
- **Offered by:** `sdlc-initialize` and `sdlc-migrate` (a bundle's `enable` runbooks, and each `setup` runbook a
  project has no record of; `## After migrating`)
- **The rule against one-time skills, pointed to from:** `zsdlc-create-skill`, `sdlc-develop-skill`
- **Checked by:** `tests/test_runbooks.py` (markers, unique IDs, records named, `enable` in a bundle's docs and
  `setup` in the core's)
