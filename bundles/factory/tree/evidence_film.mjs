// The factory's filmed pass (process/factory.md D6 rule 7): a run CD can follow by watching it.
//
// A stage proves a spec at full speed, as CI runs it, and then runs it once more, last, under
// `with-browser --film`, which sets FACTORY_EVIDENCE_PACE=1 and points FACTORY_EVIDENCE_FILM at this file. In that
// pass the project's evidence helper loads this module and:
//   - filmContext(context) on the recorded context, before its first page opens: a pointer drawn from the page's own
//     pointer events, a ring on each press, and a caption strip;
//   - caption(page, text) when it records a step, so the video carries the step's words;
//   - gesture(page, label, fn), which the spec wraps around the moves and presses that show the bug: inside it, each
//     step of a page.mouse move is held STEP_MS after the browser takes it, so the page sees the steps at least that
//     far apart (the module adds at most MOVE_CAP_MS to a move; a slow browser's own time per step comes on top),
//     a press, click or key waits PRESS_MS first, a typed string then goes STEP_MS a character (Playwright's own
//     delay; at most MOVE_CAP_MS added in all, as for a move, and a longer delay from the spec kept: past MAX_TYPED
//     characters in one call, a key would be held under KEY_FLOOR_MS, a frame of the video, and the string counts as
//     unpaced), and a wheel waits STEP_MS before and after. Nothing outside a gesture waits. So in the filmed pass a key is held about STEP_MS and
//     the app's handlers run between characters: a debounced search or a keyup handler can behave differently from
//     the proof. insertText puts its whole string in at once, as one action, like a paste;
//   - paceClaim(page) when it saves the video: what the video's `shows` ends with, which says the gestures (the parts
//     captioned "Watch") were filmed at a person's pace only when every input in them was paced and the pointer was
//     drawn travelling (paceCounts(page) gives the counts).
// Outside the filmed pass every function does nothing (gesture just runs fn), so the proof pass is unchanged.
// Text (a caption, a label) is measured as evidence.py measures a manifest's `shows`: in characters (code points), at
// most MAX_TEXT, printable, with no space but the plain one.
//
// What keeps it harmless (factory-smoke's browser probe checks the first three on the browser host):
//   - Everything it draws is in a closed shadow root on a <factory-film> element under <html>, outside <body>, with
//     pointer-events: none, so elementFromPoint and every hit test are unchanged. An observer outside the shadow
//     root sees one record: the element's insertion, when the document loads.
//   - It draws only what the page received: a passive, capture-phase listener reads each pointer event (including
//     pointerover and pointerout, which still say where the pointer went when it enters a frame, but not those right
//     after a pointercancel, which report (0, 0); and drag and dragover during a native drag, which stops the page's
//     pointer events until the drop) and never stops or cancels one. It uses no page timer, requestAnimationFrame or Date, which page.clock replaces: the
//     pointer moves inside the event handler, and the press ring is a Web Animation.
//   - A paced move sends the same points the unpaced move would, one at a time: from the point this module saw the
//     page.mouse last move to, as Playwright interpolates them. When the page saw the pointer elsewhere (a locator
//     action moved it, into a frame too), the move runs unpaced instead. Moves the page can't see, inside a frame, run
//     unpaced as well, so the film sends the proof's points.
//   - A top-layer element (an open <dialog>, a popover) paints above it: the pointer goes under an open modal.
//
// What paceClaim may say. Inside a gesture, these count as unpaced, so it says "a move ... ran at full speed", and
// each logs "[film] a move ran unpaced: ...":
//   - a move, press or click after something other than page.mouse moved the pointer, which this module checks before
//     each of them and once when the gesture ends;
//   - a press or key the page received that page.mouse and page.keyboard didn't send (a locator click where the
//     pointer already was, a locator key): the overlay counts the page's trusted pointerdown and keydown events, and
//     the gesture's end compares them with the most this module's calls could have caused, counted as Playwright sends
//     them (a chord's keys as Playwright splits it, and only typed characters on its US layout, which it presses: the
//     rest it inserts with no key). A foreign press or key that fits inside that slack isn't seen;
//   - a jump: a move with a step longer than MAX_STEP_PX, or a click that far from the pointer;
//   - a move whose start can't be checked (the page hasn't seen the pointer since it loaded, or it's over a frame):
//     it runs unpaced, so the proof's points aren't changed;
//   - a move with a step point on a frame, where the top page can't see the pointer, so the drawn pointer would
//     stall and then jump: it runs unpaced. Only the step points are checked; a frame narrower than a step can fall
//     between two of them, and the drawn pointer steps over it as over anything else;
//   - a paced move in which the page itself saw the pointer jump more than MAX_STEP_PX, give or take SEEN_SLACK_PX (a
//     native drag's events come in whole pixels; the overlay records the longest jump between the positions it
//     receives, and the last leg to the end point): the drawn pointer stalled where the page got no pointer events,
//     such as over a frame in a closed shadow root, which no lookup finds;
//   - a typed string of more than MAX_TYPED characters in one call, unless the spec's own delay is at least
//     KEY_FLOOR_MS;
//   - a move whose steps isn't a whole number.
// A press, a click or the gesture's end that can't be checked (the page hasn't seen the pointer since it loaded, loaded
// during the gesture, has the pointer over a frame, still has it where a paced move's end went unseen, or couldn't be
// asked), and a key sent while the focus is in a frame, log "[film] not checked: ..." and make no claim either way. A
// move that ends where the page doesn't see it (inside a frame in a closed shadow root, which the page sees the pointer
// enter, at the first point inside, and then nothing) leaves the page's view behind: until the page sees the pointer
// again, the checks there read "not checked", not "moved outside page.mouse", and a move from there runs unpaced. A
// press or key that goes into a frame is left out of the counts, since the top page never receives it, so it leaves no
// slack for a foreign one to hide in. The counts are per
// page, so one such press or key leaves the whole video with no claim about pace, and a move from inside the frame then
// runs unpaced and makes it "full speed": keep the bug's gesture out of frames where the app allows. Frames are found
// through open shadow roots too. Unpaced outweighs unchecked: one unpaced input makes the claim "full speed". So a spec places the
// pointer with page.mouse outside any gesture before it starts, uses only page.mouse and page.keyboard inside it, with
// moves in steps of at most MAX_STEP_PX and typed strings of at most MAX_TYPED characters a call, and ends it before
// the input that loads a new page. The gesture's end clears its "Watch" caption, so nothing after it sits under one.
// What this module can't see at all:
//   - a locator hover that ends within 1 px of where page.mouse left the pointer, wherever it went in between;
//   - a locator action that makes no press, key or pointer move: fill (an input event only), selectOption, focus,
//     setInputFiles, dispatchEvent;
//   - anything inside a frame: the overlay runs in the top document only;
//   - a frame inside a closed shadow root, which can't be looked into: it reads as its host. A move across or into it
//     is caught by the jump the page saw, or the page's lost view (above), but a click into it from just outside, which
//     the page sees land, and a key into it count as sent, which leaves room for one nobody sent (a locator press after
//     a move back out, say).
// It loads nothing and imports only Node's own timers. The job installs it read-only at /opt/factory.
// A test outside the project's import() reach (vitest can't import() a file outside the project) can load it with
// createRequire: that's require() of an ES module, on by default from Node 22.12, and it holds while this module has
// no top-level await.

import { setTimeout as sleep } from "node:timers/promises";

export const STEP_MS = 80; // two frames of a 25 fps video: the hold after each step of a paced move
export const MOVE_CAP_MS = 1500; // the most the module adds to one move
export const PRESS_MS = 400;
export const MAX_TEXT = 300;
export const MAX_STEP_PX = 40; // the longest step a paced move may take and still be drawn travelling
const KEY = "factory-film";
// A native drag's events come in whole pixels (Chromium truncates them), so a step the page saw can read up to a
// pixel longer on each axis than the one sent.
const SEEN_SLACK_PX = Math.SQRT2;
// A frame of a 25 fps video: the shortest a typed key may be held and still count as paced, so no two characters
// land in one frame. Under MOVE_CAP_MS, a string of more than MAX_TYPED characters in one call would go faster.
const KEY_FLOOR_MS = STEP_MS / 2;
const MAX_TYPED = Math.floor(MOVE_CAP_MS / KEY_FLOOR_MS);

/** True in the filmed pass: with-browser --film sets FACTORY_EVIDENCE_PACE=1 for a stage that records video. */
export function filming(env = process.env) {
  return env.FACTORY_EVIDENCE_PACE === "1" && env.FACTORY_EVIDENCE_VIDEO === "1";
}

// The page's side, run in each document of the recorded context before its own scripts. The caption strip sits at
// the bottom edge unless filmContext asks for the top.
function overlay(captionAt) {
  const key = Symbol.for("factory-film");
  if (window !== window.top || Object.prototype.hasOwnProperty.call(window, key)) return;
  let host = null, cursor = null, ring = null, strip = null, last = null, text = "", downs = 0, keys = 0;
  // Which document this is: a load makes a new one, page.setContent keeps it.
  const doc = Math.random().toString(36).slice(2);
  const place = () => {
    cursor.style.transform = `translate(${last.x}px, ${last.y}px)`;
    cursor.style.visibility = "visible";
  };
  const mount = () => {
    if (host && host.isConnected) return true;
    if (!document.documentElement) return false;
    host = document.createElement("factory-film");
    host.setAttribute("style", "all: initial; position: fixed; inset: 0; pointer-events: none; z-index: 2147483647; contain: strict;");
    const root = host.attachShadow({ mode: "closed" });
    const edge = captionAt === "top" ? "top: 0;" : "bottom: 0;";
    root.innerHTML = `<style>
      * { pointer-events: none; box-sizing: border-box; }
      #c { position: fixed; left: 0; top: 0; width: 22px; height: 28px; visibility: hidden; overflow: visible;
           filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.6)); }
      #r { position: fixed; left: -16px; top: -16px; width: 32px; height: 32px; border-radius: 50%;
           border: 3px solid #ffd400; opacity: 0; }
      #s { position: fixed; left: 0; right: 0; ${edge} padding: 6px 12px; max-height: 3.4em; overflow: hidden;
           font: 600 15px/1.4 system-ui, -apple-system, sans-serif; color: #fff; background: rgba(0, 0, 0, 0.7);
           white-space: pre-wrap; overflow-wrap: anywhere; }
      #s:empty { display: none; }
    </style><div id="r"></div><svg id="c" viewBox="0 0 22 28" aria-hidden="true"><path d="M1 1 L1 22 L6.5 17 L10.5 26 L14 24.5 L10 15.8 L17.5 15.8 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg><div id="s"></div>`;
    cursor = root.getElementById("c");
    ring = root.getElementById("r");
    strip = root.getElementById("s");
    strip.textContent = text;
    document.documentElement.appendChild(host);
    if (last) place();
    return true;
  };
  // While the module watches a paced move, the longest jump between two pointer positions this page saw.
  let watching = null;
  const moved = (x, y) => {
    if (watching) {
      watching.gap = Math.max(watching.gap, Math.hypot(x - watching.at.x, y - watching.at.y));
      watching.at = { x, y };
    }
    last = { x, y };
  };
  // A native drag cancels the pointer (pointercancel), and the pointerout and pointerover that follow report (0, 0),
  // not where the pointer is: boundary events after a cancel are skipped until a real pointer event comes.
  let cancelled = false;
  const seen = (e) => {
    if (!e.isPrimary) return;
    if (e.type === "pointerover" || e.type === "pointerout") {
      if (cancelled) return;
    } else {
      cancelled = false;
    }
    moved(e.clientX, e.clientY);
    if (mount()) place();
  };
  const cancel = (e) => {
    if (e.isPrimary) cancelled = true;
  };
  const pressed = (e) => {
    if (e.isTrusted) downs += 1;
    seen(e);
    if (!host || !e.isPrimary) return;
    const at = `translate(${e.clientX}px, ${e.clientY}px)`;
    ring.animate([{ opacity: 1, transform: `${at} scale(0.5)` }, { opacity: 0, transform: `${at} scale(1.6)` }],
      { duration: 500, easing: "ease-out" });
  };
  const keyed = (e) => {
    if (e.isTrusted) keys += 1;
  };
  // A native drag (draggable) stops the page's pointer events until it drops; drag (on the source) and dragover (on
  // the target) still say where the pointer is, between them at every step, so the drawn pointer keeps moving and the
  // module's checks keep the drop point. A drag event at exactly (0, 0) is a browser's "no position", skipped.
  const dragged = (e) => {
    if (!e.isTrusted || (e.clientX === 0 && e.clientY === 0)) return;
    moved(e.clientX, e.clientY);
    if (mount()) place();
  };
  // document.open() (page.setContent) erases the window's listeners and runs no init script, so the module calls
  // listen() again after it. Removing first keeps it to one of each.
  const listen = () => {
    const options = { capture: true, passive: true };
    for (const [type, fn] of [["pointermove", seen], ["pointerover", seen], ["pointerout", seen], ["pointerup", seen],
      ["pointerdown", pressed], ["pointercancel", cancel], ["keydown", keyed], ["drag", dragged], ["dragover", dragged]]) {
      removeEventListener(type, fn, options);
      addEventListener(type, fn, options);
    }
    if (!mount()) document.addEventListener("DOMContentLoaded", mount, { once: true });
  };
  listen();
  Object.defineProperty(window, key, {
    value: Object.freeze({
      listen,
      last: () => (last ? { x: last.x, y: last.y } : null),
      // A paced move's watch: from its start, then, at its end, the longest jump seen, the last leg to the end
      // point included (a move that ends where this page can't see it), with where this page last saw the pointer
      // and which document this is. null when this document didn't start it.
      watch: (x, y) => { watching = { at: { x, y }, gap: 0 }; },
      unwatch: (x, y) => {
        if (!watching) return null;
        const gap = Math.max(watching.gap, Math.hypot(x - watching.at.x, y - watching.at.y));
        watching = null;
        return { gap, last: last ? { x: last.x, y: last.y } : null, doc };
      },
      // For the module's checks: where the page last saw the pointer, the trusted presses and keys it has received,
      // which document this is, and whether (x, y) is over a frame, whose own events this document never sees.
      // Also whether any of a move's step points, or a click's target, is over a frame, and whether the focus is in one.
      // Both lookups go down through open shadow roots, where document's own stop at the host; a closed root can't be.
      check: (x, y, points = []) => {
        const frame = (el) => /^(IFRAME|FRAME|OBJECT|EMBED)$/.test(el?.tagName ?? "");
        const at = (px, py) => {
          let el = document.elementFromPoint(px, py);
          for (let inner; el?.shadowRoot && (inner = el.shadowRoot.elementFromPoint(px, py)) && inner !== el;) el = inner;
          return el;
        };
        let focused = document.activeElement;
        while (focused?.shadowRoot?.activeElement) focused = focused.shadowRoot.activeElement;
        return {
          last: last ? { x: last.x, y: last.y } : null, downs, keys, doc,
          framed: frame(at(x, y)), pathFramed: points.some(([px, py]) => frame(at(px, py))), focusFramed: frame(focused),
        };
      },
      caption: (t) => {
        text = String(t);
        if (mount()) strip.textContent = text;
      },
    }),
  });
}

const contexts = new WeakSet();
// page -> { at: {x, y}, moved, pacing (gestures running), sentDowns and sentKeys (the most pointerdown and keydown
// events this module's calls can cause), and the counts paceCounts gives }
const pages = new WeakMap();

// Python's str.isprintable, which evidence.py applies to `shows`: no control, format, unassigned or private-use
// character, no lone surrogate, and no separator but the plain space.
const UNPRINTABLE = /(?! )[\p{C}\p{Z}]/u;

function checkText(what, text, { shorten = false } = {}) {
  const chars = typeof text === "string" ? [...text] : null;
  if (chars === null || (!shorten && chars.length > MAX_TEXT) || UNPRINTABLE.test(text)) {
    throw new TypeError(`[film] ${what} must be one printable line of at most ${MAX_TEXT} characters`);
  }
  return chars.length > MAX_TEXT ? `${chars.slice(0, MAX_TEXT - 1).join("")}\u2026` : text;
}

const log = (message) => process.stderr.write(`[film] ${message}\n`);
const OUTSIDE = "a move ran unpaced: the pointer was moved outside page.mouse (a locator action?), so its start isn't known: place it with page.mouse outside a gesture before it starts, and use only page.mouse inside it";
const JUMP = `a move ran unpaced: the pointer jumped (a step longer than ${MAX_STEP_PX} px, or a click that far from it): move there in more steps first`;
const AFTER = "a move ran unpaced: the pointer was moved outside page.mouse during the gesture (a locator action?)";
const AROUND = "a move ran unpaced: the page received a press or key that page.mouse and page.keyboard didn't send (a locator action?)";
const UNCHECKED_MOVE = "a move ran unpaced: the page hasn't seen the pointer (since it loaded, or it's over a frame, or the page didn't see where a move left it), so its start can't be checked: place it with page.mouse outside a gesture first, and end a gesture before the input that loads a new page";
const UNCHECKED = "not checked: the page hasn't seen the pointer since it loaded, loaded during the gesture, has the pointer or the focus in a frame, didn't see where a move left the pointer, or couldn't be asked, so this makes no claim about pace";
const TYPED_FAST = `a move ran unpaced: a string of more than ${MAX_TYPED} characters typed in one call would go faster than a key a video frame (${KEY_FLOOR_MS} ms) within the cap: type at most ${MAX_TYPED} a call inside a gesture`;
const CROSSES = "a move ran unpaced: a step point lands on a frame, where this page can't see the pointer, so the drawn pointer would stall and then jump: go around the frame";
const far = (at, x, y) => Math.abs(x - at.x) > 1 || Math.abs(y - at.y) > 1;
// Playwright's own split of a chord ("Shift+A", "Control++"): a "+" with nothing before it is the key itself.
function chord(key) {
  const keys = [];
  let building = "";
  for (const ch of key) {
    if (ch === "+" && building) {
      keys.push(building);
      building = "";
    } else {
      building += ch;
    }
  }
  keys.push(building);
  return keys;
}
const jumps = (at, x, y, steps = 1) => Math.hypot(x - at.x, y - at.y) / steps > MAX_STEP_PX;

// Track where page.mouse last sent the pointer, and pace its calls inside a gesture.
function track(page) {
  if (pages.has(page)) return;
  // lost: where the page last saw the pointer, and in which document, when a paced move ended where the page didn't
  // see it (in a frame no lookup finds): while the page still has the pointer there, the checks can't say where it is.
  const state = { at: { x: 0, y: 0 }, moved: false, pacing: 0, sentDowns: 0, sentKeys: 0, text: "", passthrough: 0,
    lost: null, gestures: 0, paced: 0, unpaced: 0, unchecked: 0 };
  pages.set(page, state);
  const mouse = page.mouse, keyboard = page.keyboard;
  const m = { move: mouse.move.bind(mouse), click: mouse.click.bind(mouse), dblclick: mouse.dblclick.bind(mouse),
    down: mouse.down.bind(mouse), up: mouse.up.bind(mouse), wheel: mouse.wheel.bind(mouse) };
  // A key or wheel inside a gesture is paced: it waits before it goes.
  const pause = (ms, first = false) => {
    if (state.pacing === 0) return undefined;
    if (first) state.paced += 1;
    return sleep(ms);
  };
  // A press or click inside a gesture checks the pointer first: something other than page.mouse may have moved it,
  // and a click aimed more than MAX_STEP_PX from it (x, y given) jumps there, into a frame too. Returns whether the
  // press reaches the top page, which one that lands over a frame doesn't: a click by its target, a bare down by where
  // the pointer is (over a frame, or where the page didn't see a move leave it). The caller counts it as sent only then.
  const pressCounts = async (x, y) => {
    if (state.pacing === 0) return true;
    const c = await pointerCheck(page, state, x === undefined ? [] : [[x, y]]);
    const intoFrame = x === undefined ? c.why === "framed" || c.why === "lost" : c.pathFramed;
    if (c.where === "outside") {
      state.unpaced += 1;
      log(OUTSIDE);
    } else if (c.where === "known" && x !== undefined && jumps(state.at, x, y)) {
      state.unpaced += 1;
      log(JUMP);
    } else if (c.where === "unchecked" || intoFrame) {
      state.unchecked += 1;
      log(UNCHECKED);
    } else {
      state.paced += 1;
    }
    return !intoFrame;
  };
  const setContent = page.setContent.bind(page);
  page.setContent = async (...args) => {
    const result = await setContent(...args);
    await page.evaluate((k) => window[Symbol.for(k)]?.listen(), KEY).catch(() => {});
    return result;
  };

  mouse.move = async (x, y, options = {}) => {
    const steps = options.steps ?? 1;
    const wholeSteps = Number.isInteger(steps) && steps >= 1;
    if (state.pacing > 0 && !wholeSteps) log("a move ran unpaced: its steps option isn't a whole number of at least 1");
    // The step points a paced move would send, for the check: any over a frame, and the move runs unpaced.
    const from0 = state.at;
    const points = state.pacing > 0 && wholeSteps ? Array.from({ length: steps }, (_, k) => (k + 1 === steps ? [x, y]
      : [from0.x + (x - from0.x) * ((k + 1) / steps), from0.y + (y - from0.y) * ((k + 1) / steps)])) : [];
    const c = state.pacing > 0 && wholeSteps ? await pointerCheck(page, state, points) : null;
    let where = c ? c.where : null;
    if (where === "outside") log(OUTSIDE);
    if (where === "unchecked") log(UNCHECKED_MOVE);
    if (where === "known" && c.pathFramed) {
      log(CROSSES);
      where = "crosses";
    }
    if (where === "known") {
      const from = state.at, hold = Math.min(STEP_MS, MOVE_CAP_MS / steps);
      // A step longer than MAX_STEP_PX is a jump: held, but the pointer is drawn at points, not travelling.
      const jumped = jumps(from, x, y, steps);
      if (jumped) log(JUMP);
      await page.evaluate(([k, sx, sy]) => window[Symbol.for(k)]?.watch(sx, sy), [KEY, from.x, from.y]).catch(() => {});
      for (let i = 1; i <= steps; i++) {
        // Playwright's own interpolation (server Mouse.move), one step a call; the last lands exactly on (x, y).
        const px = i === steps ? x : from.x + (x - from.x) * (i / steps);
        const py = i === steps ? y : from.y + (y - from.y) * (i / steps);
        await m.move(px, py);
        state.at = { x: px, y: py };
        // The whole hold, after the browser has taken the step. Holding only what the round trip didn't take let two
        // steps reach the page 7 ms apart on the browser host: part of a round trip's delay can come after the page
        // already has the event.
        await sleep(hold);
      }
      // And a jump the page itself saw: the drawn pointer stalled where the page got no pointer events (a frame in a
      // closed shadow root, which no lookup finds), then jumped.
      const watched = await page.evaluate(([k, ex, ey]) => window[Symbol.for(k)]?.unwatch(ex, ey) ?? null, [KEY, x, y])
        .catch(() => null);
      const gap = watched?.gap ?? null;
      const unseen = !jumped && gap !== null && gap > MAX_STEP_PX + SEEN_SLACK_PX;
      if (unseen) log(`a move ran unpaced: the page saw the pointer jump ${Math.round(gap)} px within a paced move (a frame it can't see into, such as one in a closed shadow root?): go around it`);
      if (jumped || unseen) state.unpaced += 1;
      else state.paced += 1;
      // A move that ends where the page didn't see it (inside such a frame: the page sees the pointer enter, then
      // nothing) leaves the page with the pointer where it lost it, which isn't a locator action.
      state.lost = watched?.last && far({ x, y }, watched.last.x, watched.last.y) ? { ...watched.last, doc: watched.doc } : null;
    } else {
      if (state.pacing > 0) state.unpaced += 1;
      await m.move(x, y, options);
    }
    state.at = { x, y };
    state.moved = true;
  };
  mouse.click = async (x, y, options) => {
    // Playwright's own dblclick calls this click: the dblclick below counted and paced it already.
    if (state.passthrough > 0) return m.click(x, y, options);
    if (await pressCounts(x, y)) state.sentDowns += Math.max(1, options?.clickCount ?? 1);
    await pause(PRESS_MS);
    await m.click(x, y, options);
    state.at = { x, y };
    state.moved = true;
    await pause(STEP_MS);
  };
  mouse.dblclick = async (x, y, options) => {
    if (await pressCounts(x, y)) state.sentDowns += 2;
    await pause(PRESS_MS);
    state.passthrough += 1;
    try {
      await m.dblclick(x, y, options);
    } finally {
      state.passthrough -= 1;
    }
    state.at = { x, y };
    state.moved = true;
    await pause(STEP_MS);
  };
  mouse.down = async (options) => {
    if (await pressCounts()) state.sentDowns += 1;
    await pause(PRESS_MS);
    await m.down(options);
  };
  mouse.up = async (options) => { await m.up(options); await pause(STEP_MS); };
  mouse.wheel = async (dx, dy) => { await pause(STEP_MS, true); await m.wheel(dx, dy); await pause(STEP_MS); };
  // The keydown events each call causes, as Playwright sends them: one per key of a chord (split as Playwright splits
  // it, so "+" alone is one key), and one per typed character on its US layout (printable ASCII, and \n or \r for
  // Enter); it inserts any other character with no key.
  const keydowns = { press: (key) => chord(String(key)).length,
    type: (text) => [...String(text)].filter((ch) => (ch >= " " && ch <= "~") || ch === "\n" || ch === "\r").length,
    down: () => 1, up: () => 0, insertText: () => 0 };
  for (const name of ["press", "type", "down", "up", "insertText"]) {
    const original = keyboard[name].bind(keyboard);
    keyboard[name] = async (...args) => {
      const n = keydowns[name](args[0]);
      // A typed string goes a character at a time, each held STEP_MS (Playwright's own delay, between a key's down and
      // its up), so the film shows it typed rather than appearing at once. Capped as a move is, but a key held less
      // than a video frame isn't paced: such a string runs at the cap and counts as unpaced.
      let tooFast = false;
      if (name === "type" && state.pacing > 0) {
        const hold = Math.min(STEP_MS, MOVE_CAP_MS / Math.max(1, [...String(args[0])].length));
        const delay = Math.max(args[1]?.delay ?? 0, hold);
        args[1] = { ...args[1], delay };
        tooFast = delay < KEY_FLOOR_MS;
      }
      // Keys go where the focus is: into a frame, the top page never receives them, so they're left out of the count
      // (no slack for a foreign key) and can't be checked.
      if (state.pacing > 0 && n > 0 && (await pointerCheck(page, state)).focusFramed) {
        state.unchecked += 1;
        log(UNCHECKED);
      } else {
        state.sentKeys += n;
      }
      if (tooFast) {
        state.unpaced += 1;
        log(TYPED_FAST);
      }
      await pause(PRESS_MS, !tooFast);
      return original(...args);
    };
  }
}

// Where the page last saw the pointer, against where this module last sent it. "known": the same point. "outside":
// somewhere else, so something other than page.mouse moved it (a locator action), and a paced move would start from the
// wrong point. "unchecked": the page can't say, since it hasn't seen the pointer (since it loaded: Playwright's pointer
// may be anywhere), the pointer is over a frame, the page still has it where a move left it unseen (state.lost: the
// page's view hasn't changed since, so nothing else moved it where the page could see), or the page couldn't be asked.
// With the page's tally of presses, keys and document (null when it couldn't be asked). The caller logs.
async function pointerCheck(page, state, points = []) {
  let seen;
  try {
    seen = await page.evaluate(([k, x, y, pts]) => window[Symbol.for(k)]?.check(x, y, pts) ?? null,
      [KEY, state.at.x, state.at.y, points]);
  } catch {
    seen = null;
  }
  if (seen == null) return { where: "unchecked", why: "unasked", tally: null, pathFramed: false, focusFramed: false };
  const tally = { downs: seen.downs, keys: seen.keys, doc: seen.doc };
  const more = { tally, pathFramed: !!seen.pathFramed, focusFramed: !!seen.focusFramed };
  if (seen.framed) return { where: "unchecked", why: "framed", ...more };
  if (seen.last === null) return { where: "unchecked", why: "unseen", ...more };
  // The page has seen the pointer somewhere else since it lost it, or loaded: what it sees now counts again.
  const lost = state.lost;
  if (lost && (lost.doc !== seen.doc || far(lost, seen.last.x, seen.last.y))) state.lost = null;
  if (!far(state.at, seen.last.x, seen.last.y)) return { where: "known", why: null, ...more };
  if (state.lost) return { where: "unchecked", why: "lost", ...more };
  return { where: "outside", why: null, ...more };
}

/**
 * Film the recorded context: call it before the context's first page opens (open pages are filmed too). Only in the
 * filmed pass; returns whether it filmed. options.captionAt: "bottom" (default) or "top", for a layout whose bottom
 * edge holds what CD needs to see.
 */
export async function filmContext(context, options = {}) {
  if (!filming()) return false;
  if (contexts.has(context)) return true;
  const captionAt = options.captionAt === "top" ? "top" : "bottom";
  contexts.add(context);
  const script = `(${overlay.toString()})(${JSON.stringify(captionAt)});`;
  await context.addInitScript({ content: script });
  for (const page of context.pages()) {
    track(page);
    await page.evaluate(script).catch((e) => log(`an open page wasn't filmed: ${e.message.split("\n")[0]}`));
  }
  context.on("page", track);
  return true;
}

/**
 * Show text in the caption strip of a filmed page, at once: "Step 2: ...". Text past MAX_TEXT characters is cut, with
 * an ellipsis, so a step's full `shows` fits behind "Step n: ". Does nothing on any other page.
 */
export async function caption(page, text) {
  const shown = checkText("a caption", text, { shorten: true });
  const state = pages.get(page);
  if (!state) return;
  state.text = shown;
  await page.evaluate(([k, t]) => window[Symbol.for(k)]?.caption(t), [KEY, shown])
    .catch((e) => log(`caption not shown: ${e.message.split("\n")[0]}`));
}

/**
 * Run fn, the moves and presses that show the bug, at a person's pace on a filmed page, with label in the caption
 * strip while it runs ("Watch: ..."). Elsewhere it just runs fn. A locator action inside it runs unpaced: use
 * page.mouse and page.keyboard for the gesture.
 */
export async function gesture(page, label, fn) {
  checkText("a gesture's label", label);
  const state = pages.get(page);
  if (!state) return fn();
  const replaced = state.text;
  await caption(page, `Watch: ${label}`);
  const ours = state.text;
  state.gestures += 1;
  state.pacing += 1;
  const before = (await pointerCheck(page, state)).tally;
  const sent = { downs: state.sentDowns, keys: state.sentKeys };
  try {
    return await fn();
  } finally {
    const end = await pointerCheck(page, state);
    if (before === null || end.tally === null || end.tally.doc !== before.doc) {
      // The page loaded during the gesture, or couldn't be asked: nothing here can be checked.
      state.unchecked += 1;
      log(UNCHECKED);
    } else if (end.tally.downs - before.downs > state.sentDowns - sent.downs
               || end.tally.keys - before.keys > state.sentKeys - sent.keys) {
      state.unpaced += 1;
      log(AROUND);
    } else if (end.where === "outside") {
      // A locator action after the gesture's last page.mouse call left the pointer where this module didn't send it.
      state.unpaced += 1;
      log(AFTER);
    } else if (end.why === "framed" || end.why === "lost") {
      // Over a frame, whose events this document doesn't see, or where the page didn't see a move leave it. (No
      // pointer seen at all in the same document means nothing moved it there, which is fine.)
      state.unchecked += 1;
      log(UNCHECKED);
    }
    // Nothing after the gesture sits under its "Watch": clear it (or give an enclosing gesture's back), unless a step
    // recorded inside it already replaced it.
    if (state.text === ours) await caption(page, state.pacing > 1 ? replaced : "");
    state.pacing -= 1;
  }
}

/**
 * What the filmed pass did on a page: gestures run, inputs paced inside them (a move, press, click, key or wheel),
 * checks inside them that failed (unpaced: see the header's list), and checks that couldn't be made (unchecked). One
 * action the module didn't make can fail two checks: a press's, and the gesture's end. A page nobody filmed has every
 * count 0. paceClaim turns these into the video's words.
 */
export function paceCounts(page) {
  const state = pages.get(page);
  return Object.freeze(state ? { gestures: state.gestures, paced: state.paced, unpaced: state.unpaced, unchecked: state.unchecked }
    : { gestures: 0, paced: 0, unpaced: 0, unchecked: 0 });
}

/**
 * What the video's `shows` ends with, from paceCounts(page) on the recorded page. It speaks for the gestures only,
 * which the video captions "Watch: ...": '; filmed at a person's pace where captioned "Watch"' when they paced an input
 * and every check passed, '; filmed, but a move captioned "Watch" ran at full speed' when one ran unpaced, and "" when
 * a check couldn't be made or nothing was paced (no gesture, or a page nobody filmed). A helper appends it as it is,
 * shortening the rest of `shows` by its length.
 */
export function paceClaim(page) {
  const { paced, unpaced, unchecked } = paceCounts(page);
  if (unpaced > 0) return '; filmed, but a move captioned "Watch" ran at full speed';
  return unchecked === 0 && paced > 0 ? '; filmed at a person\'s pace where captioned "Watch"' : "";
}
