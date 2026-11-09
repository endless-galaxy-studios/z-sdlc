# Factory

This project runs the z-sdlc software factory: issue-driven agent stages on self-hosted runners, as
the `factory` bundle installs them. The rules are `[sdlc-root]/process/factory.md` (D1 stage contract,
D2 credential boundary, D3 planning tier, D4 production tier, D5 improve loop); what to set up before
the first run is its Enablement section.

**The factory workflows are rendered.** Each `.github/workflows/factory-*.yml` is `.github/factory/templates/<same
name>` with this project's settings (`factory.json`, and `planning.json`'s database) put in by
`render.py`. Edit the settings and run `python3 .github/factory/render.py`; CI's
`render.py --check` refuses a workflow edited by hand. Templates, scripts, guards and the stack
profile come from z-sdlc and are refreshed by `sdlc-migrate`; change them there.

## Operating notes

This file is the project's: record its runners, hosts, environments and anything else an operator
needs here. `sdlc-migrate` never overwrites it.

## Enablement record

The install's decisions and state (`[sdlc-root]/process/factory-runbook.md` § 0 and § 1). Write each
decision when it's made, in CD's words, with the date and the session it was made in, and say later
whether it was built or dropped.

| # | Question | Answer (CD's words) | Date | Session | Built, deferred or dropped |
|---|---|---|---|---|---|

**Inventory** (runbook § 2): the stack-fit table, the hosts that deploy from git, the production
host's profile, credential reach, and the "New" items.

**State** (runbook § 3): each step's check, with its date and result.

**Deferred:** what was left for later, and who owns it.
