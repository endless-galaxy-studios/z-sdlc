"""evidence_film.mjs, the filmed pass's overlay and pacing (process/factory.md D6 rule 7), against a stand-in page.

What it must never do is change the proof: outside the filmed pass and outside a gesture it waits for nothing, and a
paced move sends the points Playwright's own interpolation would. factory-smoke's browser probe checks the overlay in
a real browser on the browser host (browser_probe.mjs, film-*)."""

import json
import pathlib
import shutil
import subprocess
import unittest

FACTORY = pathlib.Path(__file__).resolve().parent.parent
MODULE = FACTORY / "evidence_film.mjs"

# Runs in Node: a stand-in context and page that record each call with its time, then every case, as JSON.
HARNESS = r"""
const [modulePath] = process.argv.slice(1);
const now = () => Number(process.hrtime.bigint() / 1000000n);
const errors = [];
process.stderr.write = ((write) => (chunk, ...rest) => { errors.push(String(chunk)); return true; })(process.stderr.write.bind(process.stderr));

function stand(seen, moveMs = 0) {
  // seen stands for the page's overlay: where it last saw the pointer (value), the trusted presses and keys it has
  // received, which document it is, and whether the pointer is over a frame. The page sees what Playwright's mouse and
  // keyboard send; a test changes seen itself to stand for a locator action, or a load.
  // framed: the pointer is over a frame; pathFramed: the points asked about are (a click's target); focusFramed: the
  // focus is in a frame. A click whose target is over a frame, a down where the pointer is over one, and a key into one
  // never reach this page's counts.
  // closed: [left, right], a frame in a closed shadow root across the page, which no lookup finds. The page sees it as
  // Chromium shows it: entering, the body's pointerout and the host's pointerover, both at the first point inside;
  // inside, nothing; leaving, the host's pointerout, then the body's pointerover and pointermove, all at the first
  // point outside. A press inside it goes to the frame. A move call lands at its end point (an unpaced move's own steps
  // aren't played out).
  Object.assign(seen, { downs: 0, keys: 0, doc: "first", framed: false, pathFramed: false, focusFramed: false, closed: null, ...seen });
  const calls = [];
  const rec = (name) => async (...args) => { calls.push([name, ...args.map((a) => (typeof a === "function" ? "fn" : a)), now()]); };
  const inClosed = (p) => !!(p && seen.closed && p.x >= seen.closed[0] && p.x <= seen.closed[1]);
  // A paced move's watch, as the overlay keeps it: the longest jump between the positions the page saw.
  let watching = null;
  const sees = (x, y) => {
    if (inClosed({ x, y }) && inClosed(seen.value)) return;
    if (watching) {
      watching.gap = Math.max(watching.gap, Math.hypot(x - watching.at.x, y - watching.at.y));
      watching.at = { x, y };
    }
    seen.value = { x, y };
  };
  const lands = (name, downs = () => 0) => async (x, y, ...rest) => {
    await rec(name)(x, y, ...rest);
    sees(x, y);
    if (!seen.pathFramed && !inClosed({ x, y })) seen.downs += downs(rest[0]);
  };
  const slowMove = async (...args) => { if (moveMs) await new Promise((ok) => setTimeout(ok, moveMs)); return lands("move")(...args); };
  const keyed = (name, keys) => async (...args) => { await rec(name)(...args); if (!seen.focusFramed) seen.keys += keys(args[0]); };
  // The keydowns Playwright really sends: a chord's keys as it splits them, and one per typed character on its US
  // layout (printable ASCII, \n, \r); any other character is inserted with no key.
  const chord = (k) => k.split(/(?<=[^+])\+/).length;
  const onLayout = (t) => [...t].filter((ch) => (ch >= " " && ch <= "~") || ch === "\n" || ch === "\r").length;
  return {
    calls, seen,
    // Playwright's client dblclick is this mouse's click with clickCount 2.
    mouse: { move: slowMove, click: lands("click", (o) => o?.clickCount ?? 1),
      dblclick(x, y, o) { return this.click(x, y, { ...o, clickCount: 2 }); },
      down: async (...a) => { await rec("down")(...a); if (!seen.framed && !inClosed(seen.value)) seen.downs += 1; },
      up: rec("up"), wheel: rec("wheel") },
    keyboard: { press: keyed("press", chord), type: keyed("type", onLayout),
      down: keyed("kdown", () => 1), up: rec("kup"), insertText: rec("insertText") },
    async evaluate(fn, arg) {
      // A paced move's watch: the longest jump this page saw (or seen.gap, which a test sets to stand for one), where
      // it last saw the pointer, and which document it is.
      if (typeof fn === "function" && String(fn).includes("unwatch(")) {
        const [, ex, ey] = arg;
        const gap = watching ? Math.max(watching.gap, Math.hypot(ex - watching.at.x, ey - watching.at.y)) : 0;
        watching = null;
        return { gap: this.seen.gap ?? gap, last: this.seen.value, doc: this.seen.doc };
      }
      if (typeof fn === "function" && String(fn).includes("watch(")) {
        watching = { at: { x: arg[1], y: arg[2] }, gap: 0 };
        return undefined;
      }
      if (typeof fn === "function" && String(fn).includes("check(")) {
        if (this.seen.fail) throw new Error("Execution context was destroyed");
        const { value, downs, keys, doc, framed, pathFramed, focusFramed } = this.seen;
        return { last: value, downs, keys, doc, framed, pathFramed: arg[3].length > 0 && pathFramed, focusFramed };
      }
      calls.push(["evaluate", typeof fn === "string" ? "script" : arg, now()]);
    },
    async setContent() { calls.push(["setContent", now()]); },
  };
}
function context() {
  return { scripts: [], handler: null, pages: () => [], on(event, fn) { this.handler = fn; },
    async addInitScript(s) { this.scripts.push(s); } };
}
const env = (pace, video) => { process.env.FACTORY_EVIDENCE_PACE = pace; process.env.FACTORY_EVIDENCE_VIDEO = video; };
const out = {};

env("0", "1");
let film = await import(modulePath);
out.filming = [["1", "1"], ["1", "0"], ["0", "1"], ["", ""]].map(([p, v]) => film.filming({ FACTORY_EVIDENCE_PACE: p, FACTORY_EVIDENCE_VIDEO: v }));
{
  const c = context();
  out.unfilmedContext = { filmed: await film.filmContext(c), scripts: c.scripts.length, listening: c.handler !== null };
  const page = stand({ value: null });
  const t0 = now();
  out.untrackedGesture = await film.gesture(page, "a gesture on a page nobody filmed", async () => { await page.mouse.move(10, 10, { steps: 12 }); return "ran"; });
  out.untrackedCalls = page.calls.map((c) => c.slice(0, 4));
  out.untrackedMs = now() - t0;
}

env("1", "1");
const c = context();
out.filmedContext = await film.filmContext(c);
const script = c.scripts[0] && c.scripts[0].content;
try { new Function(script); out.scriptParses = true; } catch (e) { out.scriptParses = String(e); }
const page = stand({ value: null });
c.handler(page);

// Outside a gesture: one call, as given, no wait and no page round trip.
let t0 = now();
await page.mouse.move(100, 50, { steps: 12 });
await page.keyboard.press("Enter");
out.outside = { calls: page.calls.map((x) => x.slice(0, -1)), ms: now() - t0 };
page.calls.length = 0;

// Inside: one call a step, Playwright's interpolation from where page.mouse last went, each held STEP_MS.
page.seen.value = { x: 100, y: 50 };
t0 = now();
const result = await film.gesture(page, "cross the button to the card", async () => { await page.mouse.move(400, 290, { steps: 12 }); return 7; });
out.inside = { result, ms: now() - t0, moves: page.calls.filter((x) => x[0] === "move"), captions: page.calls.filter((x) => x[0] === "evaluate").map((x) => x[1]) };
page.calls.length = 0;

// A press inside a gesture waits PRESS_MS first; a key too.
page.seen.value = { x: 400, y: 290 };
t0 = now();
await film.gesture(page, "press and type", async () => { await page.mouse.down(); await page.mouse.up(); await page.keyboard.press("Escape"); });
out.presses = page.calls.filter((x) => x[0] !== "evaluate").map((x) => [x[0], x[x.length - 1] - t0]);
page.calls.length = 0;

// The start isn't known (the page saw the pointer elsewhere): the move runs as given, unpaced, and says so.
page.seen.value = { x: 5, y: 5 };
errors.length = 0;
await film.gesture(page, "after a locator moved the pointer", async () => { await page.mouse.move(10, 10, { steps: 6 }); });
out.unknownStart = { moves: page.calls.filter((x) => x[0] === "move").map((x) => x.slice(0, 4)), said: errors.join("") };
page.calls.length = 0;

// A long move is capped at MOVE_CAP_MS.
page.seen.value = { x: 10, y: 10 };
t0 = now();
await film.gesture(page, "a long move", async () => { await page.mouse.move(300, 10, { steps: 60 }); });
out.capped = { ms: now() - t0, moves: page.calls.filter((x) => x[0] === "move").length };
page.calls.length = 0;

// A step whose own round trip is slower than STEP_MS gets no hold on top.
const slow = stand({ value: null }, 120);
c.handler(slow);
await slow.mouse.move(0, 0);
slow.seen.value = { x: 0, y: 0 };
slow.calls.length = 0;
await film.gesture(slow, "a slow browser", async () => { await slow.mouse.move(60, 0, { steps: 4 }); });
const slowMoves = slow.calls.filter((x) => x[0] === "move");
out.slowGaps = slowMoves.slice(1).map((m, i) => m[m.length - 1] - slowMoves[i][slowMoves[i].length - 1]);

// A gesture that throws stops pacing.
page.seen.value = { x: 300, y: 10 };
try { await film.gesture(page, "throws", async () => { throw new Error("boom"); }); } catch (e) { out.thrown = e.message; }
t0 = now();
await page.mouse.move(20, 20, { steps: 5 });
out.afterThrow = { calls: page.calls.filter((x) => x[0] === "move").length, ms: now() - t0 };

// Bad text is a bad call everywhere, filmed or not.
out.bad = [];
for (const [what, call] of [["label", () => film.gesture(stand({ value: null }), "two\nlines", async () => {})],
                            ["caption", () => film.caption(page, "two\nlines")],
                            ["number", () => film.caption(page, 5)]]) {
  try { await call(); out.bad.push([what, "accepted"]); } catch (e) { out.bad.push([what, e.constructor.name]); }
}
// A caption past MAX_TEXT is cut with an ellipsis, so "Step n: " plus a full shows fits.
page.calls.length = 0;
await film.caption(page, "Step 2: " + "x".repeat(300));
const long = page.calls.find((x) => x[0] === "evaluate")[1][1];
out.longCaption = [long.length, long.endsWith("\u2026")];
// setContent erases the page's listeners: the module asks the overlay to listen again.
page.calls.length = 0;
await page.setContent("<p>x</p>");
out.setContent = page.calls.map((x) => x[0]);
// Text is measured in characters (code points), as evidence.py measures `shows`, and printable as Python means it.
const face = "\u{1F600}";
out.astral = [];
for (const [what, call] of [["300 faces", () => film.gesture(stand({ value: null }), face.repeat(300), async () => {})],
                            ["301 faces", () => film.gesture(stand({ value: null }), face.repeat(301), async () => {})],
                            ["a no-break space", () => film.gesture(stand({ value: null }), "a\u00a0b", async () => {})],
                            ["a lone surrogate", () => film.gesture(stand({ value: null }), "a\ud83d", async () => {})],
                            ["plain spaces", () => film.gesture(stand({ value: null }), "a b  c", async () => {})]]) {
  try { await call(); out.astral.push([what, "accepted"]); } catch (e) { out.astral.push([what, e.constructor.name]); }
}
page.calls.length = 0;
await film.caption(page, face.repeat(301));
const cut = page.calls.find((x) => x[0] === "evaluate")[1][1];
out.astralCaption = [[...cut].length, cut.endsWith("\u2026"), /\p{Cs}/u.test(cut), [...cut].slice(0, -1).every((ch) => ch === face)];

// paceCounts: what the gestures on a page paced, and which moves ran unpaced.
const counted = stand({ value: null });
c.handler(counted);
const counts = () => ({ ...film.paceCounts(counted) });
out.counts = { untracked: { ...film.paceCounts(stand({ value: null })) } };
await counted.mouse.move(30, 30, { steps: 3 });
await counted.keyboard.press("a");
out.counts.outside = counts();
counted.seen.value = { x: 30, y: 30 };
await film.gesture(counted, "a paced move", async () => { await counted.mouse.move(40, 40, { steps: 2 }); });
out.counts.paced = counts();
counted.seen.value = { x: 40, y: 40 };
await film.gesture(counted, "a press and a key", async () => { await counted.mouse.down(); await counted.mouse.up(); await counted.keyboard.press("b"); });
out.counts.presses = counts();
counted.seen.value = { x: 1, y: 1 };
await film.gesture(counted, "a move from where a locator left the pointer", async () => { await counted.mouse.move(50, 50, { steps: 2 }); });
out.counts.unknownStart = counts();
counted.seen.value = { x: 50, y: 50 };
errors.length = 0;
await film.gesture(counted, "a move with a fractional steps option", async () => { await counted.mouse.move(60, 60, { steps: 2.5 }); });
out.counts.fractional = counts();
out.counts.fractionalSaid = errors.join("");

// What can't be called paced, and what paceClaim says. Each case on a page of its own, the pointer placed at (0, 0)
// with page.mouse first unless the case says not.
async function claimed(steps, { place = true } = {}) {
  const pg = stand({ value: null });
  c.handler(pg);
  if (place) await pg.mouse.move(0, 0);
  errors.length = 0;
  await film.gesture(pg, "a case", () => steps(pg));
  return { counts: { ...film.paceCounts(pg) }, claim: film.paceClaim(pg), said: errors.join("") };
}
const locator = (pg, at, { downs = 0, keys = 0 } = {}) => {
  if (at) pg.seen.value = at;
  pg.seen.downs += downs;
  pg.seen.keys += keys;
};
const load = (pg) => Object.assign(pg.seen, { value: null, doc: "second", downs: 0, keys: 0 });
out.claims = {
  stepped: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); }),
  steppedThenClickThere: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); await pg.mouse.click(50, 50); }),
  clickNear: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); await pg.mouse.click(70, 70); }),
  oneStepShort: await claimed(async (pg) => { await pg.mouse.move(30, 0); }),
  keysOnly: await claimed(async (pg) => { await pg.keyboard.press("a"); }),
  chordAndTyping: await claimed(async (pg) => { await pg.keyboard.press("Shift+A"); await pg.keyboard.type("bc"); }),
  hoverThenClick: await claimed(async (pg) => { locator(pg, { x: 5, y: 5 }); await pg.mouse.click(100, 100); }),
  hoverThenDown: await claimed(async (pg) => { locator(pg, { x: 5, y: 5 }); await pg.mouse.down(); await pg.mouse.up(); }),
  steppedThenLocatorHover: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); locator(pg, { x: 300, y: 300 }); }),
  steppedThenLocatorClickThere: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); locator(pg, null, { downs: 1 }); }),
  locatorKey: await claimed(async (pg) => { await pg.keyboard.press("a"); locator(pg, null, { keys: 1 }); }),
  oneStepAcross: await claimed(async (pg) => { await pg.mouse.move(400, 300); }),
  twoStepsAcross: await claimed(async (pg) => { await pg.mouse.move(780, 580, { steps: 2 }); }),
  clickAway: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); await pg.mouse.click(200, 200); }),
  unplaced: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); }, { place: false }),
  clickThatLoads: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); await pg.mouse.click(50, 50); load(pg); }),
  clickWhileLoading: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); await pg.mouse.click(50, 50); pg.seen.fail = true; }),
  moveAfterLoad: await claimed(async (pg) => { load(pg); await pg.mouse.move(80, 80, { steps: 4 }); }),
  overAFrame: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); Object.assign(pg.seen, { framed: true, pathFramed: true }); await pg.mouse.click(50, 50); }),
  nothing: await claimed(async () => {}),
  // Counted as Playwright sends them, so no slack hides a locator key.
  plusKeyThenLocatorKey: await claimed(async (pg) => { await pg.keyboard.press("+"); locator(pg, null, { keys: 1 }); }),
  typedOffLayoutThenLocatorKeys: await claimed(async (pg) => { await pg.keyboard.type("a\u00e9\t"); locator(pg, null, { keys: 2 }); }),
  controlPlus: await claimed(async (pg) => { await pg.keyboard.press("Control++"); }),
  // A double-click goes through Playwright's click once, counted once.
  dblclick: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); await pg.mouse.dblclick(50, 50); }),
  dblclickThenLocatorClicks: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); await pg.mouse.dblclick(50, 50); locator(pg, null, { downs: 2 }); }),
  // Frames: a path across one runs unpaced; a press or key into one is left out of the counts, and not checked.
  pathCrossesAFrame: await claimed(async (pg) => { pg.seen.pathFramed = true; await pg.mouse.move(50, 50, { steps: 4 }); }),
  clickIntoAFrame: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); pg.seen.pathFramed = true; await pg.mouse.click(70, 70); }),
  typedIntoAFrame: await claimed(async (pg) => { pg.seen.focusFramed = true; await pg.keyboard.type("ab"); }),
  typedIntoAFrameThenLocatorKeys: await claimed(async (pg) => { pg.seen.focusFramed = true; await pg.keyboard.type("ab"); locator(pg, null, { keys: 2 }); }),
  // A click is judged by its target: out of a frame it reaches the page and counts as sent; far into one it jumped.
  clickOutOfAFrame: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); pg.seen.framed = true; await pg.mouse.click(60, 60); }),
  farClickIntoAFrame: await claimed(async (pg) => { await pg.mouse.move(50, 50, { steps: 4 }); pg.seen.pathFramed = true; await pg.mouse.click(450, 50); }),
  // The page saw the pointer jump within a paced move (a frame no lookup finds): unpaced.
  pageSawAJump: await claimed(async (pg) => { pg.seen.gap = 204; await pg.mouse.move(50, 50, { steps: 4 }); }),
  pageSawStepsOnly: await claimed(async (pg) => { pg.seen.gap = 18; await pg.mouse.move(50, 50, { steps: 4 }); }),
  // A native drag's whole pixels can make a 40 px step read up to SEEN_SLACK_PX longer: within it, still paced.
  pageSawADragsRounding: await claimed(async (pg) => { pg.seen.gap = 41.2; await pg.mouse.move(50, 50, { steps: 4 }); }),
  pageSawPastTheSlack: await claimed(async (pg) => { pg.seen.gap = 41.5; await pg.mouse.move(50, 50, { steps: 4 }); }),
  // A frame in a closed shadow root at x 150 to 400, which no lookup finds. A move that ends inside it: unpaced, by
  // the jump the page saw, and the page's view is left at the first point inside, which isn't a locator action.
  closedInto: await claimed(async (pg) => { pg.seen.closed = [150, 400]; await pg.mouse.move(300, 0, { steps: 12 }); }),
  // One step into it: the page saw every step but the last, so the move is paced, but where it ended isn't checked.
  closedOneStepIn: await claimed(async (pg) => { pg.seen.closed = [150, 400]; await pg.mouse.move(175, 0, { steps: 7 }); }),
  // The page then sees where the move ended (its last event came late): checked again.
  closedThenSeen: await claimed(async (pg) => { pg.seen.closed = [150, 400]; await pg.mouse.move(175, 0, { steps: 7 }); pg.seen.value = { x: 175, y: 0 }; }),
  // In and back out: the move out can't start from a point the page saw, so it runs unpaced, as one from a frame does.
  closedInAndOut: await claimed(async (pg) => { pg.seen.closed = [150, 400]; await pg.mouse.move(300, 0, { steps: 12 }); await pg.mouse.move(100, 0, { steps: 8 }); }),
  // A locator that moves the pointer where the page sees it still reads as one.
  closedThenLocatorHover: await claimed(async (pg) => { pg.seen.closed = [150, 400]; await pg.mouse.move(175, 0, { steps: 7 }); locator(pg, { x: 30, y: 30 }); }),
  // A bare down there goes to the frame: left out of the sent count, so a locator click then reads as foreign.
  closedDown: await claimed(async (pg) => { pg.seen.closed = [150, 400]; await pg.mouse.move(175, 0, { steps: 7 }); await pg.mouse.down(); await pg.mouse.up(); }),
  closedDownThenLocatorClick: await claimed(async (pg) => { pg.seen.closed = [150, 400]; await pg.mouse.move(175, 0, { steps: 7 }); await pg.mouse.down(); await pg.mouse.up(); locator(pg, null, { downs: 1 }); }),
  // KNOWN LIMIT (the header's): a click just inside it from its edge, which the page sees land, counts as sent, so
  // after a paced move back out a locator click hides in that slack.
  knownLimitClosedClickThenLocatorClick: await claimed(async (pg) => { pg.seen.closed = [150, 400]; await pg.mouse.move(140, 0, { steps: 4 }); await pg.mouse.click(160, 0); await pg.mouse.move(125, 0); locator(pg, null, { downs: 1 }); }),
};
{
  // Typing inside a gesture goes a character at a time: Playwright's own delay, STEP_MS; outside, as given.
  const pg = stand({ value: null });
  c.handler(pg);
  await pg.mouse.move(0, 0);
  await pg.keyboard.type("ab");
  errors.length = 0;
  await film.gesture(pg, "typing", async () => {
    await pg.keyboard.type("cd");
    await pg.keyboard.type("ef", { delay: 200 });
    await pg.keyboard.type("x".repeat(37));
  });
  out.typed = { calls: pg.calls.filter((x) => x[0] === "type").map((x) => x.slice(1, -1)), counts: { ...film.paceCounts(pg) }, said: errors.join("") };
}
{
  // Past MAX_TYPED characters in one call, a key would go under a video frame: it runs at the cap and counts as
  // unpaced. A spec's own delay of a frame or more keeps it paced.
  const pg = stand({ value: null });
  c.handler(pg);
  await pg.mouse.move(0, 0);
  errors.length = 0;
  await film.gesture(pg, "long typing", async () => {
    await pg.keyboard.type("x".repeat(38));
    await pg.keyboard.type("y".repeat(60), { delay: 40 });
  });
  out.longTyped = { calls: pg.calls.filter((x) => x[0] === "type").map((x) => x.slice(1, -1)), counts: { ...film.paceCounts(pg) }, said: errors.join("") };
}
{
  // The double-click's wait comes once: PRESS_MS, not twice.
  const pg = stand({ value: null });
  c.handler(pg);
  await pg.mouse.move(0, 0);
  const t0 = now();
  await film.gesture(pg, "a double-click", () => pg.mouse.dblclick(0, 0));
  out.dblclickMs = now() - t0;
  out.dblclickCalls = pg.calls.filter((x) => x[0] === "click").map((x) => x[3]);
}

// The gesture's "Watch" caption: cleared when it ends, kept when a step inside it replaced it, and an enclosing
// gesture's given back.
async function captionsOf(steps) {
  const pg = stand({ value: null });
  c.handler(pg);
  await pg.mouse.move(0, 0);
  pg.calls.length = 0;
  await steps(pg);
  return pg.calls.filter((x) => x[0] === "evaluate" && Array.isArray(x[1])).map((x) => x[1][1]);
}
out.captions = {
  cleared: await captionsOf((pg) => film.gesture(pg, "a gesture", async () => {})),
  stepInside: await captionsOf((pg) => film.gesture(pg, "a gesture", () => film.caption(pg, "Step 3: the popup open"))),
  nested: await captionsOf((pg) => film.gesture(pg, "outer", () => film.gesture(pg, "inner", async () => {}))),
};
out.claims.untracked = film.paceClaim(stand({ value: null }));
out.constants = { STEP_MS: film.STEP_MS, MOVE_CAP_MS: film.MOVE_CAP_MS, PRESS_MS: film.PRESS_MS };
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "needs node")
class Film(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["node", "--input-type=module", "-e", HARNESS, str(MODULE)], capture_output=True, text=True,
                           timeout=60)
        if r.returncode != 0:
            raise AssertionError(r.stderr)
        cls.r = json.loads(r.stdout)
        cls.step, cls.cap, cls.press = (cls.r["constants"][k] for k in ("STEP_MS", "MOVE_CAP_MS", "PRESS_MS"))

    def test_only_the_filmed_pass_films(self):
        self.assertEqual(self.r["filming"], [True, False, False, False])
        self.assertEqual(self.r["unfilmedContext"], {"filmed": False, "scripts": 0, "listening": False})
        self.assertTrue(self.r["filmedContext"])

    def test_a_gesture_on_a_page_nobody_filmed_just_runs(self):
        self.assertEqual(self.r["untrackedGesture"], "ran")
        self.assertEqual(self.r["untrackedCalls"], [["move", 10, 10, {"steps": 12}]])
        self.assertLess(self.r["untrackedMs"], 12 * self.step - 100)  # a paced 12-step move

    def test_the_page_script_parses(self):
        self.assertIs(self.r["scriptParses"], True)

    def test_outside_a_gesture_nothing_waits(self):
        self.assertEqual(self.r["outside"]["calls"], [["move", 100, 50, {"steps": 12}], ["press", "Enter"]])
        self.assertLess(self.r["outside"]["ms"], self.press - 100)  # a paced press

    def test_a_paced_move_sends_playwrights_own_points_one_at_a_time(self):
        inside = self.r["inside"]
        self.assertEqual(inside["result"], 7)
        moves = inside["moves"]
        self.assertEqual(len(moves), 12)
        for i, m in enumerate(moves, start=1):
            # Playwright's server Mouse.move: from + (to - from) * (i / steps); the last lands exactly on the target.
            want = (400, 290) if i == 12 else (100 + (400 - 100) * (i / 12), 50 + (290 - 50) * (i / 12))
            self.assertEqual((m[1], m[2]), want)
            self.assertEqual(len(m), 4, "one step a call, with no steps option")
        gaps = [b[-1] - a[-1] for a, b in zip(moves, moves[1:])]
        self.assertGreaterEqual(min(gaps), self.step - 5)
        # The gesture's caption, then the strip cleared when it ends.
        self.assertEqual(inside["captions"], [["factory-film", "Watch: cross the button to the card"], ["factory-film", ""]])

    def test_a_press_waits_first(self):
        down, up, key = self.r["presses"]
        self.assertEqual([down[0], up[0], key[0]], ["down", "up", "press"])
        self.assertGreaterEqual(down[1], self.press - 5)
        self.assertGreaterEqual(key[1] - up[1], self.press - 5)

    def test_an_unknown_start_runs_unpaced_and_says_so(self):
        self.assertEqual(self.r["unknownStart"]["moves"], [["move", 10, 10, {"steps": 6}]])
        self.assertIn("ran unpaced", self.r["unknownStart"]["said"])

    def test_a_long_move_is_capped(self):
        self.assertEqual(self.r["capped"]["moves"], 60)
        self.assertLess(self.r["capped"]["ms"], 60 * self.step - 1000)  # uncapped
        self.assertGreaterEqual(self.r["capped"]["ms"], self.cap - 100)

    def test_a_gesture_that_throws_stops_pacing(self):
        self.assertEqual(self.r["thrown"], "boom")
        self.assertEqual(self.r["afterThrow"]["calls"], 1)
        self.assertLess(self.r["afterThrow"]["ms"], 5 * self.step - 100)  # a paced 5-step move

    def test_bad_text_is_refused_everywhere(self):
        self.assertEqual(self.r["bad"], [["label", "TypeError"], ["caption", "TypeError"], ["number", "TypeError"]])

    def test_each_step_is_held_after_the_browser_takes_it(self):
        # A step's own round trip (120 ms here) doesn't shorten the hold: part of that delay can come after the page
        # already has the event, so only a hold after it keeps the page's steps STEP_MS apart.
        gaps = self.r["slowGaps"]
        self.assertEqual(len(gaps), 3)
        self.assertGreaterEqual(min(gaps), 120 + self.step - 10)

    def test_a_long_caption_is_cut(self):
        self.assertEqual(self.r["longCaption"], [300, True])

    def test_set_content_listens_again(self):
        self.assertEqual(self.r["setContent"], ["setContent", "evaluate"])


    def test_text_is_measured_in_characters_and_printable_as_the_manifest_means_it(self):
        self.assertEqual(self.r["astral"], [["300 faces", "accepted"], ["301 faces", "TypeError"],
                                            ["a no-break space", "TypeError"], ["a lone surrogate", "TypeError"],
                                            ["plain spaces", "accepted"]])
        # 299 whole faces and the ellipsis: the cut never splits a surrogate pair.
        self.assertEqual(self.r["astralCaption"], [300, True, False, True])

    def test_pace_counts_say_what_the_gestures_paced(self):
        counts = self.r["counts"]
        zero = {"gestures": 0, "paced": 0, "unpaced": 0, "unchecked": 0}
        self.assertEqual(counts["untracked"], zero)
        self.assertEqual(counts["outside"], zero, "nothing outside a gesture counts")
        self.assertEqual(counts["paced"], {"gestures": 1, "paced": 1, "unpaced": 0, "unchecked": 0})
        self.assertEqual(counts["presses"], {"gestures": 2, "paced": 3, "unpaced": 0, "unchecked": 0})
        self.assertEqual(counts["unknownStart"], {"gestures": 3, "paced": 3, "unpaced": 1, "unchecked": 0})
        self.assertEqual(counts["fractional"], {"gestures": 4, "paced": 3, "unpaced": 2, "unchecked": 0})
        self.assertIn("isn't a whole number", counts["fractionalSaid"])


    def test_pace_claim_says_paced_only_when_every_pointer_input_travelled_at_a_persons_pace(self):
        claims = self.r["claims"]
        paced = "; filmed at a person's pace where captioned \"Watch\""
        unpaced = "; filmed, but a move captioned \"Watch\" ran at full speed"
        def n(paced=0, unpaced=0, unchecked=0):
            return {"gestures": 1, "paced": paced, "unpaced": unpaced, "unchecked": unchecked}
        want = {
            "stepped": (n(1), paced, None),
            "steppedThenClickThere": (n(2), paced, None),
            "clickNear": (n(2), paced, None),  # 28 px away: within a step
            "oneStepShort": (n(1), paced, None),  # 30 px: within a step
            "keysOnly": (n(1), paced, None),
            "chordAndTyping": (n(2), paced, None),  # Shift+A is two keydowns, "bc" two more: none extra
            # Something other than page.mouse moved the pointer: checked before a press, and when the gesture ends.
            "hoverThenClick": (n(0, 1), unpaced, "moved outside page.mouse"),
            "hoverThenDown": (n(0, 2), unpaced, "moved outside page.mouse"),
            "steppedThenLocatorHover": (n(1, 1), unpaced, "during the gesture"),
            # A press or key the module didn't send, even where the pointer already was.
            "steppedThenLocatorClickThere": (n(1, 1), unpaced, "didn't send"),
            "locatorKey": (n(1, 1), unpaced, "didn't send"),
            # Jumps: a step longer than MAX_STEP_PX.
            "oneStepAcross": (n(0, 1), unpaced, "jumped"),
            "twoStepsAcross": (n(0, 1), unpaced, "jumped"),
            "clickAway": (n(1, 1), unpaced, "jumped"),
            # A start the page hasn't seen runs unpaced, so the film sends the proof's points.
            "unplaced": (n(0, 1), unpaced, "place it with page.mouse"),
            "moveAfterLoad": (n(0, 1, 1), unpaced, "place it with page.mouse"),
            # What can't be checked makes no claim either way.
            "clickThatLoads": (n(2, 0, 1), "", "not checked"),
            "clickWhileLoading": (n(2, 0, 1), "", "not checked"),
            "overAFrame": (n(1, 0, 2), "", "not checked"),
            "nothing": (n(), "", None),
            "plusKeyThenLocatorKey": (n(1, 1), unpaced, "didn't send"),
            "typedOffLayoutThenLocatorKeys": (n(1, 1), unpaced, "didn't send"),
            "controlPlus": (n(1), paced, None),
            "dblclick": (n(2), paced, None),
            "dblclickThenLocatorClicks": (n(2, 1), unpaced, "didn't send"),
            "pathCrossesAFrame": (n(0, 1), unpaced, "lands on a frame"),
            "clickIntoAFrame": (n(1, 0, 1), "", "not checked"),
            "typedIntoAFrame": (n(1, 0, 1), "", "not checked"),
            "typedIntoAFrameThenLocatorKeys": (n(1, 1, 1), unpaced, "didn't send"),
            "clickOutOfAFrame": (n(1, 0, 2), "", "not checked"),
            "farClickIntoAFrame": (n(1, 1), unpaced, "jumped"),
            "pageSawAJump": (n(0, 1), unpaced, "saw the pointer jump 204 px"),
            "pageSawStepsOnly": (n(1), paced, None),
            "pageSawADragsRounding": (n(1), paced, None),
            "pageSawPastTheSlack": (n(0, 1), unpaced, "saw the pointer jump 42 px"),
            # A frame in a closed shadow root: the page's view left behind where a move ended unseen is "not checked".
            "closedInto": (n(0, 1, 1), unpaced, "saw the pointer jump 150 px"),
            "closedOneStepIn": (n(1, 0, 1), "", "not checked"),
            "closedThenSeen": (n(1), paced, None),
            "closedInAndOut": (n(0, 2), unpaced, "can't be checked"),
            "closedThenLocatorHover": (n(1, 1), unpaced, "during the gesture"),
            "closedDown": (n(1, 0, 2), "", "not checked"),
            "closedDownThenLocatorClick": (n(1, 1, 1), unpaced, "didn't send"),
            "knownLimitClosedClickThenLocatorClick": (n(3), paced, None),
        }
        # A click back out of a frame reaches the page and is counted as sent: no press reads as foreign.
        self.assertNotIn("didn't send", claims["clickOutOfAFrame"]["said"])
        # Where the page lost the pointer in a frame, the module's own move doesn't read as a locator's.
        for case in ("closedInto", "closedOneStepIn", "closedInAndOut", "closedDown"):
            with self.subTest(case=case):
                self.assertNotIn("moved outside page.mouse", claims[case]["said"])
        self.assertEqual(sorted(want), sorted(k for k in claims if k != "untracked"))
        for case, (counts, claim, said) in want.items():
            with self.subTest(case=case):
                self.assertEqual(claims[case]["counts"], counts)
                self.assertEqual(claims[case]["claim"], claim)
                if said:
                    self.assertIn(said, claims[case]["said"])
                else:
                    self.assertEqual(claims[case]["said"], "")
        self.assertEqual(claims["untracked"], "")


    def test_the_gestures_caption_ends_with_it(self):
        captions = self.r["captions"]
        self.assertEqual(captions["cleared"], ["Watch: a gesture", ""])
        self.assertEqual(captions["stepInside"], ["Watch: a gesture", "Step 3: the popup open"])
        self.assertEqual(captions["nested"], ["Watch: outer", "Watch: inner", "Watch: outer", ""])


    def test_a_double_click_goes_through_playwrights_click_once(self):
        self.assertEqual(self.r["dblclickCalls"], [{"clickCount": 2}])
        self.assertLess(self.r["dblclickMs"], 2 * self.press, "waited once, not twice")


    def test_typing_inside_a_gesture_goes_a_character_at_a_time(self):
        # Capped like a move: 37 characters share MOVE_CAP_MS, each still held a video frame (STEP_MS / 2); a longer
        # delay from the spec is kept.
        typed = self.r["typed"]
        self.assertEqual(typed["calls"], [["ab"], ["cd", {"delay": self.step}], ["ef", {"delay": 200}],
                                          ["x" * 37, {"delay": self.cap / 37}]])
        self.assertGreaterEqual(self.cap / 37, self.step / 2)
        self.assertEqual(typed["counts"], {"gestures": 1, "paced": 3, "unpaced": 0, "unchecked": 0})
        self.assertEqual(typed["said"], "")

    def test_typing_too_long_for_the_cap_counts_as_unpaced(self):
        # 38 characters would go under a frame a key: run at the cap, unpaced. The spec's own 40 ms keeps 60 paced.
        long = self.r["longTyped"]
        self.assertEqual(long["calls"], [["x" * 38, {"delay": self.cap / 38}], ["y" * 60, {"delay": 40}]])
        self.assertEqual(long["counts"], {"gestures": 1, "paced": 1, "unpaced": 1, "unchecked": 0})
        self.assertIn("more than 37 characters", long["said"])


if __name__ == "__main__":
    unittest.main()
