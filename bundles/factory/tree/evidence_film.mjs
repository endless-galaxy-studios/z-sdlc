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
//     and a press, click, key or wheel waits PRESS_MS first. Nothing outside a gesture waits;
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
//   - It draws only what the page received: a passive, capture-phase listener reads each pointer event (and dragover
//     during a native drag, which stops the page's pointer events until the drop) and never stops or cancels one. It uses no page timer, requestAnimationFrame or Date, which page.clock replaces: the
//     pointer moves inside the event handler, and the press ring is a Web Animation.
//   - A paced move sends the same points the unpaced move would, one at a time: from the point this module saw the
//     page.mouse last move to, as Playwright interpolates them. When that point isn't certain (a locator action has
//     moved the pointer since, which this module can't see), the move runs unpaced instead.
//   - A top-layer element (an open <dialog>, a popover) paints above it: the pointer goes under an open modal.
//
// What paceClaim may say. Inside a gesture, these count as unpaced, so it says "a move ... ran at full speed", and
// each logs "[film] a move ran unpaced: ...":
//   - a move, press or click after something other than page.mouse moved the pointer, which this module checks before
//     each of them and once when the gesture ends;
//   - a press or key the page received that page.mouse and page.keyboard didn't send (a locator click where the
//     pointer already was, a locator key): the overlay counts the page's trusted pointerdown and keydown events, and
//     the gesture's end compares them with what this module sent;
//   - a jump: a move with a step longer than MAX_STEP_PX, or a click that far from the pointer;
//   - a move whose start can't be checked (the page hasn't seen the pointer since it loaded, or it's over a frame):
//     it runs unpaced, so the proof's points aren't changed;
//   - a move whose steps isn't a whole number.
// A press, a click or the gesture's end that can't be checked (the page loaded during the gesture, the pointer is over
// a frame, or the page couldn't be asked) logs "[film] not checked: ..." and makes no claim either way. So a spec
// places the pointer with page.mouse outside any gesture before it starts, uses only page.mouse and page.keyboard
// inside it, with moves in steps of at most MAX_STEP_PX, and ends it before the input that loads a new page. The
// overlay runs in the top document only, so nothing inside a frame is seen.
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
  const seen = (e) => {
    if (!e.isPrimary) return;
    last = { x: e.clientX, y: e.clientY };
    if (mount()) place();
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
  // A native drag (draggable) stops the page's pointer events until it drops; dragover still says where the pointer
  // is, so the drawn pointer keeps moving and the module's checks keep the drop point.
  const dragged = (e) => {
    if (!e.isTrusted) return;
    last = { x: e.clientX, y: e.clientY };
    if (mount()) place();
  };
  // document.open() (page.setContent) erases the window's listeners and runs no init script, so the module calls
  // listen() again after it. Removing first keeps it to one of each.
  const listen = () => {
    const options = { capture: true, passive: true };
    for (const [type, fn] of [["pointermove", seen], ["pointerup", seen], ["pointerdown", pressed], ["keydown", keyed], ["dragover", dragged]]) {
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
      // For the module's checks: where the page last saw the pointer, the trusted presses and keys it has received,
      // which document this is, and whether (x, y) is over a frame, whose own events this document never sees.
      check: (x, y) => ({
        last: last ? { x: last.x, y: last.y } : null, downs, keys, doc,
        framed: /^(IFRAME|FRAME|OBJECT|EMBED)$/.test(document.elementFromPoint(x, y)?.tagName ?? ""),
      }),
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
const UNCHECKED_MOVE = "a move ran unpaced: the page hasn't seen the pointer (since it loaded, or it's over a frame), so its start can't be checked: place it with page.mouse outside a gesture first, and end a gesture before the input that loads a new page";
const UNCHECKED = "not checked: the page loaded during the gesture, the pointer is over a frame, or the page couldn't be asked, so this makes no claim about pace";
const far = (at, x, y) => Math.abs(x - at.x) > 1 || Math.abs(y - at.y) > 1;
const jumps = (at, x, y, steps = 1) => Math.hypot(x - at.x, y - at.y) / steps > MAX_STEP_PX;

// Track where page.mouse last sent the pointer, and pace its calls inside a gesture.
function track(page) {
  if (pages.has(page)) return;
  const state = { at: { x: 0, y: 0 }, moved: false, pacing: 0, sentDowns: 0, sentKeys: 0,
    gestures: 0, paced: 0, unpaced: 0, unchecked: 0 };
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
  // and a click aimed more than MAX_STEP_PX from it (x, y given) jumps there.
  const pressCounts = async (x, y) => {
    if (state.pacing === 0) return;
    const { where } = await pointerCheck(page, state);
    if (where === "outside") {
      state.unpaced += 1;
      log(OUTSIDE);
    } else if (where === "unchecked") {
      state.unchecked += 1;
      log(UNCHECKED);
    } else if (x !== undefined && jumps(state.at, x, y)) {
      state.unpaced += 1;
      log(JUMP);
    } else {
      state.paced += 1;
    }
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
    const where = state.pacing > 0 && wholeSteps ? (await pointerCheck(page, state)).where : null;
    if (where === "outside") log(OUTSIDE);
    if (where === "unchecked") log(UNCHECKED_MOVE);
    if (where === "known") {
      const from = state.at, hold = Math.min(STEP_MS, MOVE_CAP_MS / steps);
      // A step longer than MAX_STEP_PX is a jump: held, but the pointer is drawn at points, not travelling.
      if (jumps(from, x, y, steps)) {
        state.unpaced += 1;
        log(JUMP);
      } else {
        state.paced += 1;
      }
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
    } else {
      if (state.pacing > 0) state.unpaced += 1;
      await m.move(x, y, options);
    }
    state.at = { x, y };
    state.moved = true;
  };
  mouse.click = async (x, y, options) => {
    state.sentDowns += Math.max(1, options?.clickCount ?? 1);
    await pressCounts(x, y);
    await pause(PRESS_MS);
    await m.click(x, y, options);
    state.at = { x, y };
    state.moved = true;
    await pause(STEP_MS);
  };
  mouse.dblclick = async (x, y, options) => {
    state.sentDowns += 2;
    await pressCounts(x, y);
    await pause(PRESS_MS);
    await m.dblclick(x, y, options);
    state.at = { x, y };
    state.moved = true;
    await pause(STEP_MS);
  };
  mouse.down = async (options) => { state.sentDowns += 1; await pressCounts(); await pause(PRESS_MS); await m.down(options); };
  mouse.up = async (options) => { await m.up(options); await pause(STEP_MS); };
  mouse.wheel = async (dx, dy) => { await pause(STEP_MS, true); await m.wheel(dx, dy); await pause(STEP_MS); };
  // The most keydown events each call can cause: one per key of a chord, one per character typed.
  const keydowns = { press: (key) => String(key).split("+").length, type: (text) => [...String(text)].length,
    down: () => 1, up: () => 0, insertText: () => 0 };
  for (const name of ["press", "type", "down", "up", "insertText"]) {
    const original = keyboard[name].bind(keyboard);
    keyboard[name] = async (...args) => {
      state.sentKeys += keydowns[name](args[0]);
      await pause(PRESS_MS, true);
      return original(...args);
    };
  }
}

// Where the page last saw the pointer, against where this module last sent it. "known": the same point. "outside":
// somewhere else, so something other than page.mouse moved it (a locator action), and a paced move would start from the
// wrong point. "unchecked": the page can't say, since it hasn't seen the pointer (since it loaded: Playwright's pointer
// may be anywhere), the pointer is over a frame, or the page couldn't be asked. With the page's tally of presses, keys
// and document (null when it couldn't be asked). The caller logs.
async function pointerCheck(page, state) {
  let seen;
  try {
    seen = await page.evaluate(([k, x, y]) => window[Symbol.for(k)]?.check(x, y) ?? null, [KEY, state.at.x, state.at.y]);
  } catch {
    seen = null;
  }
  if (seen == null) return { where: "unchecked", why: "unasked", tally: null };
  const tally = { downs: seen.downs, keys: seen.keys, doc: seen.doc };
  if (seen.framed) return { where: "unchecked", why: "framed", tally };
  if (seen.last === null) return { where: "unchecked", why: "unseen", tally };
  return { where: far(state.at, seen.last.x, seen.last.y) ? "outside" : "known", why: null, tally };
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
  if (!pages.has(page)) return;
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
  await caption(page, `Watch: ${label}`);
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
    } else if (end.why === "framed") {
      // Over a frame, whose events this document doesn't see. (No pointer seen at all in the same document means
      // nothing moved it there, which is fine.)
      state.unchecked += 1;
      log(UNCHECKED);
    }
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
