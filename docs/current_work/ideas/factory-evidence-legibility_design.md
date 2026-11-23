---
type: design
slug: factory-evidence-legibility
created: 2026-11-23
status: built and proven on the browser host by hand (CD chose Option B as bundle code, 2026-11-23)
origin: the pilot project's session, at CD's request
related_files:
  - process/factory.md
  - skills/sdlc-reproduce/SKILL.md
  - skills/sdlc-implement/SKILL.md
  - skills/sdlc-revise/SKILL.md
  - bundles/factory/tree/with-browser
  - bundles/factory/tree/evidence.py
  - bundles/factory/tree/browser_probe.mjs
---

# Factory browser evidence CD can follow

**Decided (CD, 2026-11-23):** Option B, as bundle code, and the wiki's line fixed. Question 2's mapping as proposed.
Before the release is tagged, the probe's film checks are run by hand on the runner host against the browser host, as
on 2026-11-20, since `factory-smoke` reaches them only after a tag. The pilot's session films the real case with the
module first.

**Where the build departs from this design:**
- `page.setContent` runs `document.open()`, which erases the window's listeners and runs no init script. So the
  overlay's listeners can be registered again (`listen()`, idempotent), and the module calls that after `setContent`.
- The caption strip can sit at the top (`filmContext(context, { captionAt: "top" })`) for a layout whose bottom edge
  holds what CD needs.
- A gesture shows "Watch: <label>" in the strip while it runs.
- The press ring is a Web Animation, so it shows even when the press and release are milliseconds apart, and a paused
  `page.clock` doesn't stop it.
- The proof runs record video as before, since nothing ships from them: the last invocation's files do.
- A stage runs the filmed pass only where the project's evidence helper loads the module. Otherwise the proof's
  evidence ships and the result says the video isn't paced: a plain second run would spend a browser-host session for
  nothing.
- Under a paused `page.clock`, a canvas that paints in `requestAnimationFrame` doesn't repaint during a gesture.
  Measured: the drawn pointer swept across four squares while the canvas still showed the first one highlighted,
  until the spec advanced the clock. The rule has a spec on a paused clock say so in its gesture's label; nothing
  detects it automatically.
- The video's `shows` ends "; filmed at a person's pace", so it still opens with what the video shows.
- **The pilot's real case, filmed locally:** the bug and the fix, each as a proof and then a filmed pass. The verdicts,
  points and hit targets agreed, and the drawn pointer and captions read in order. Each paced step is its own call,
  and the pilot's trace snapshots each one (about 130 to 160 ms on that board), so its 12-step move took 2.3 to 2.5 s.
  Holding only what a step's round trip didn't take would shorten that, but on the browser host it let two steps reach
  the page 7 ms apart, so each step keeps the whole 80 ms hold. It changed two things:
  - `caption` cuts text past 300 characters instead of refusing it;
  - the module may be loaded from a fixture, because the pilot's import guard refuses it in the helper.

  The bottom caption strip covers about 30 px of the board (a life bar, the hand's bottom edge); the top would cover
  turn controls instead.
- Local proof (Playwright 1.61.1, through `connect`): identical pointer coordinates filmed and unfilmed, steps about
  83 ms apart instead of 5 to 18 ms, and the pointer visibly walking across the board in the filmed video.

## The problem

CD (2026-11-23): "i want to be able to read this report, watch the video and understand what's happening. things
move fast (expected since it's just code running) but it's not human-like, and thus somewhat unverifiable for me
looking at the change". Earlier: "i dont think the screenshots & annotations line up with what's actually happening".

In the case that raised it, a popup on a canvas board stuck open after the pointer crossed a DOM button. The pilot's
session measured both runs' evidence, frame by frame at 25 fps:

1. **The pointer is never drawn.** Plain `recordVideo` and `page.screenshot` don't render the mouse, so a caption like
   "pointer settled 4000 ms on the Support cell" can't be checked against the picture.
2. **The gesture is invisible.** It is one `page.mouse.move` with 12 steps. In the fix run's video nothing changes
   after 15 s, yet the spec's precondition passed, so the popup opened and closed between two frames. The bug run
   shows one event: the popup appearing and staying.
3. **Repeats triple the screenshots.** The fix run used `--repeat-each=3`: 12 screenshots, three identical sets
   numbered 1 to 4.
4. **Captions describe the test's intent and its internal measurements** (`elementFromPoint`, a MutationObserver), not
   what the picture shows.

## What Playwright 1.61.1 does

Read from its source (`playwright-core` 1.61.1). Nothing here has been filmed.

1. **A stepped `mouse.move` sends its steps back to back.** `Mouse.move` loops over the steps with no wait between
   them, so a step takes only as long as the browser takes the input. Measured later: 5 to 18 ms on a light page and
   about 50 ms on the pilot's board, so a state that lasts one step shows for a frame or two at most. A drawn pointer
   alone doesn't fix that: it would jump.
2. **`showActions` waits before every input call, and its cursor goes ahead of the real pointer.** The pre-input hook
   awaits `duration` (500 ms by default) before each input API call. For a stepped move it fires once, with the end
   point: the drawn cursor glides to the end during the wait, and then the real steps run, undrawn, in one burst. So
   the 2026-11-21 review was right about timing, and the cursor wouldn't show the path either.
3. **`showChapter` blocks and covers the page.** It awaits its duration (2000 ms by default) and then a 300 ms fade.
   It blurs the whole page behind a box up to 560 px wide in the centre, which hides what CD is meant to watch.
4. **`showOverlay(html)` with no duration returns once the overlay is in**, but with a duration it awaits it. Its
   overlays sit in Playwright's pane, which has `pointer-events: none` (so `elementFromPoint` is unchanged), with
   scripts and `on*` attributes removed.
5. **`page.clock` replaces `requestAnimationFrame`.** Under a paused clock a canvas doesn't redraw, so a wall-clock
   pause shows a still board until the spec advances the clock. The case's spec uses no fake clock (the popup has no
   close timer).

## Part 1: fixes that need no choice

These fix rules that are wrong or missing today, whichever option below is chosen. They change the rule text in
`process/factory.md` D6 rule 7 and § Reproducing in a browser rule 5, and in that section's mirrors in
`sdlc-reproduce`, `sdlc-implement` and `sdlc-revise`. They change no code.

1. **The stated reason for plain video is half wrong.** "The trace already marks each action" is false where it
   matters: on a canvas app the trace's DOM snapshots don't show the board. Its screenshots are also off whenever
   video is on (rule 5), and the trace doesn't open on a phone or reach the archive. The timing reason stands on its
   own (fact 2).
2. **A caption says what its picture shows.** `shows` already opens with what the file shows. The rule adds that a
   measurement the picture can't show (a hit test, an observer's record) never stands in for it. A measurement may
   follow, marked, in the same 300 characters: "pointer on the Support cell, popup open on the far Core; checked: the
   path crossed the Undo button".
3. **A repeated run films and photographs its first repeat only.** A stage that runs a spec more than once
   (`--repeat-each`, or a retry) records evidence from repeat 0 alone (`testInfo.repeatEachIndex`), and its result
   says how many repeats passed. Today the pilot's helper takes every repeat's screenshots and renames the repeats
   `-2` and `-3`, so the report shows three copies of each step.

Also: the organization wiki's Factory Browser Design page still says "Annotated video wherever the project's
Playwright is 1.59 or later". The code changed on 2026-11-21 and the wiki didn't. So does the earlier handoff
`factory-browser-repro_handoff.md`, which belongs to another session and is left alone here.

## Part 2: making the gesture watchable

### Option A: Part 1 only

The captions and screenshots get honest, but a fast gesture stays invisible in the video. That's the failure CD
described.

### Option B (recommended): a filmed pass at a person's pace, after the proof

- **The proof pass is unchanged.** It runs as CI runs it, unpaced, with every repeat the stage wants. It records no
  video, and only its screenshots go in the report. Its outcome is the stage's outcome.
- **A filmed pass runs last, once.** It's the same spec, under `FACTORY_EVIDENCE_PACE=1`, and it asserts as the proof
  does. The helper clears the evidence folder on each invocation, so the last invocation's files are the ones that
  ship. In it:
  - **The pointer is drawn from the page's own pointer events.** A passive, capture-phase listener reads each
    `pointermove`, `pointerdown` and `pointerup` and moves a cursor, with a ring on a press. It draws only what the
    page received, so it can't run ahead of the real pointer (unlike fact 2). It shows in the video and in
    screenshots.
  - **Only the gesture is paced, never setup.** The spec marks the gesture: one call that wraps the moves and presses
    that show the bug. Inside it, each step of a move is held for at least 80 ms (two frames at 25 fps), capped at
    1.5 s per move, and a press waits 400 ms first. Lobby, sign-in and board setup run at full speed, so the video
    stays short: a measured run was 90 s, and the report embeds at most 20 MB. A spec's own waits (a 4000 ms hold)
    are untouched.
  - **Each step's caption is on the picture.** A strip at the bottom edge shows "Step n: <shows>", set when the helper
    records the step, without waiting. Any player, on any phone, shows it. A WebVTT track in the report would keep
    the picture clean, but it would need timestamps in the manifest. It's also unproven on CD's iPhone under the
    report's `media-src data:` policy.
- **The two passes are compared.** Agreement is the normal case. A disagreement is itself a finding (the behaviour
  depends on speed), and what it means for each stage is CD's call (question 2).
- **How the overlay stays harmless.**
  - The cursor and strip live in a closed shadow root, on a host appended to `<html>`, outside `body`.
  - Everything in it has `pointer-events: none`, so hit tests are unchanged.
  - Its listeners are passive and never stop or cancel an event.
  - It updates styles only inside the shadow root, which an observer outside can't see. The one record anything
    outside sees is the host's insertion, at start.
  - It goes only into the recorded context, and only in the filmed pass.
  - `factory-smoke`'s browser probe proves all of this on the browser host. It loads the same page with and without
    the overlay and compares `elementFromPoint` at each drawn point, the MutationObserver records on `body` and on a
    watched element, and how long an unpaced stepped move takes.
  - Known limit: a top-layer element (an open `<dialog>`, a popover) paints above it, so the pointer goes under an
    open modal.
- **Cost.** One more run of the spec per filmed stage, and about 80 ms per paced step. Today's 34.5 s video would
  gain about one second for the 12-step move.
- **Fake clocks.** Pacing doesn't advance a fake clock. The film shows what the app drew, so an app on a paused clock
  looks paused until the spec advances it (fact 5), and the caption says so.

### Rejected

- **`recordVideo.showActions` or `screencast.showActions`:** it adds waits to every input, and its cursor shows the
  end point ahead of the real events (fact 2).
- **`showChapter`:** it blocks for 2.3 s and blurs the page (fact 3).
- **One paced run and no fast proof:** the factory would disagree with CI's run of the same spec, which is the
  2026-11-21 concern.
- **Drawing the pointer onto the video afterwards, from logged positions:** it touches nothing in the page, but it
  needs a video encoder in frozen code and in the job image. A burst that spans two frames is still two frames,
  however slowly it's played.

## Part 3: where Option B lives

- **Bundle code (recommended, a minor release: new contract surface).**
  - `bundles/factory/tree/` gains the page script: the cursor and the strip. It also gains the pacing wrapper, a
    Node module a project's evidence helper imports.
  - `with-browser` exports `FACTORY_EVIDENCE_PACE`, and the stages' skills run the filmed pass last.
  - `factory-smoke` proves the overlay, and a seed note tells a project's helper what to call.
  - One reviewed copy is proven where it runs. The page script goes into the app's page, so it's near the boundary.
  - The pilot's helper changes go back to its session, which offered.
- **The rule alone (a patch):** `factory.md` says what the filmed pass does, and each project's helper builds it.
  It's cheaper now, but every project writes its own overlay and pacing, and smoke can't prove a helper it doesn't
  ship.

No manifest change either way. `evidence.py` takes exactly four keys and drops every file when an entry has another
one. The captions use `shows`, and whether the video came from a paced pass goes in the video entry's `shows`
("filmed at a person's pace: …"). If a new field is ever needed, the packer must accept it in a release before any
helper writes it.

## Questions for CD

1. Option B, a filmed pass at a person's pace after the proof, or Part 1 alone?
2. When the passes disagree, what does each stage report? Proposed:
   - **reproduce:** the bug only in the paced pass → `partially reproduced`, "only at a person's pace": a failing
     check of the mechanism at another speed, which D6's "only a failing check counts" allows. The bug only in the
     fast pass → `reproduced`, and the report says the film doesn't show it.
   - **implement and revise:** the fix holds fast and fails paced → not done: it doesn't hold at the speed a person
     moves.
3. Bundle code (a minor release) or the rule alone?
4. Fix the wiki's "Annotated video" line now? It's wrong today, whatever is chosen.

## First build step

**A sample clip, before anything ships.** Film this case's gesture with the overlay and the pacing on the browser
host, beside today's plain video, and put both in front of CD. CD's test is whether the video can be followed, so the
clip is the evidence the design works. The pilot's session offered to run it.
