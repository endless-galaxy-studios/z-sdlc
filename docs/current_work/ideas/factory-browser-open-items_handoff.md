---
type: handoff
slug: factory-browser-open-items
created: 2026-11-25
status: pending
trigger: deferred-work
recommended_next_skill: none
source_session_summary: "The factory's browser reproduction (v2.8.0) and its filmed pass (v2.10.0 to v2.12.8) are built, released and rolled out to the pilot project. Their handoffs and design notes were removed once handled (2026-11-25, CD: 'consolidate and remove any handoffs that we've handled'). This is what they left open."
active_deliverable: null
related_files:
  - process/factory.md
  - bundles/factory/tree/evidence_film.mjs
  - bundles/factory/tree/browser_probe.mjs
  - bundles/factory/tree/with-browser
---

# Handoff: what the browser reproduction and the filmed pass left open

## Why this is a handoff

These notes were consolidated here and removed once handled:
- the browser-reproduction handoff;
- the filmed pass's design note;
- its follow-ups and nine review rounds;
- three of the pilot's migration notes.

Their outcomes are in `process/sdlc_changelog.md`, one entry per release, and in the organization's wiki (Factory Browser Design), which is the place of record for the hosts and the rollout. What's below is what nobody has decided or done yet.

## Waiting on something

1. **The pilot's first `factory-smoke` run on the full filmed pass.** It comes once CD merges the pilot's PR #124, which carries v2.12.8. It's the first run of `film-claims`, `film-frames`, `film-typed` and `film-caption` in the pilot's own smoke job. Anything it finds comes back as a new round.
2. **The incubator hasn't taken z-sdlc's bundle changes since several releases** (`zsdlc-import-factory --to-incubator`): every import report lists them under "for the incubator". CD's call when.
3. **The other projects take the browser route one at a time.** The wiki's project table says what each needs first.

## Open questions

- **Which Playwright versions the browser host serves** (one port each), and who adds one when a project upgrades. The wiki's project table names versions some projects need.
- **Whether a spec that fails only on the browser host counts as reproduced** when it passes on the CI host. One timing-sensitive spec flaked there.
- **Offsite copies of the evidence archive.** The wiki states the limit: one machine, no offsite copy.

## Left as they are, by choice

They're stated in `evidence_film.mjs`'s header and D6 rule 7, and none can make a video over-claim beyond what's stated:
- **A click at a point inside a frame in a closed shadow root** that the page saw the pointer reach, and a key into one, still count as sent, so one foreign press can hide in that slack. Closing it would take finding frames no lookup can reach, or checking each press after it's sent.
- **A far click out of a frame reads "not checked" rather than a jump.** It's safe either way.
- **Typing past 37 characters a call counts as unpaced,** though keys still arrive about 40 ms apart. It only under-claims.
