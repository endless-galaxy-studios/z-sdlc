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
  const calls = [];
  const rec = (name) => async (...args) => { calls.push([name, ...args.map((a) => (typeof a === "function" ? "fn" : a)), now()]); };
  const slowMove = async (...args) => { if (moveMs) await new Promise((ok) => setTimeout(ok, moveMs)); return rec("move")(...args); };
  return {
    calls, seen,
    mouse: { move: slowMove, click: rec("click"), dblclick: rec("dblclick"), down: rec("down"), up: rec("up"), wheel: rec("wheel") },
    keyboard: { press: rec("press"), type: rec("type"), down: rec("kdown"), up: rec("kup"), insertText: rec("insertText") },
    async evaluate(fn, arg) {
      if (typeof fn === "function" && String(fn).includes("last()")) return this.seen.value;
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
        self.assertEqual(inside["captions"], [["factory-film", "Watch: cross the button to the card"]])

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
        zero = {"gestures": 0, "paced": 0, "unpaced": 0}
        self.assertEqual(counts["untracked"], zero)
        self.assertEqual(counts["outside"], zero, "nothing outside a gesture counts")
        self.assertEqual(counts["paced"], {"gestures": 1, "paced": 1, "unpaced": 0})
        self.assertEqual(counts["presses"], {"gestures": 2, "paced": 3, "unpaced": 0})
        self.assertEqual(counts["unknownStart"], {"gestures": 3, "paced": 3, "unpaced": 1})
        self.assertEqual(counts["fractional"], {"gestures": 4, "paced": 3, "unpaced": 2})
        self.assertIn("isn't a whole number", counts["fractionalSaid"])


if __name__ == "__main__":
    unittest.main()
