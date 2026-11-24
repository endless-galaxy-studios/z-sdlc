// factory-smoke's browser-host probe (D6). The agent runs it inside the implement stage's sandbox, under
// with-browser, so it reaches the browser host only as a stage would; the job runs it once outside the sandbox
// first, as the control:
//   with-browser node browser_probe.mjs <secret hashes>
// It loads the project's own Playwright client (from $FACTORY_BROWSER_CLIENT, which with-browser sets) and prints
// what it saw, one line per check, then "end":
//   <check> <result> [detail]
// It judges nothing: browser_check.py does, for the control and the agent, and requires every check, so one this
// skips fails there too. The job copies this file out of the agent's reach before the agent runs.
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import http from "node:http";
import net from "node:net";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [hashFile] = process.argv.slice(2);
const projectDir = process.env.FACTORY_BROWSER_CLIENT || ".";
const out = (check, result, detail = "") =>
  process.stdout.write(`${check} ${result}${detail ? " " + String(detail).replace(/\s+/g, " ").slice(0, 300) : ""}\n`);
const why = (e) => (String(e && e.message).match(/net::[A-Z_]+/) || [String(e && e.message).split("\n")[0]])[0];

// The credential names D2 denies, and the hashes of the job's real secrets (the first 12 hex digits of each
// value's sha256, "<label> <hash>" a line, as sandbox_probe.py reads them).
const CREDENTIAL_NAMES = ["CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "GH_TOKEN", "GITHUB_TOKEN",
  "OVERRIDE_GITHUB_TOKEN", "DEFAULT_WORKFLOW_TOKEN", "CONTEXT7_API_KEY", "ACTIONS_RUNTIME_TOKEN",
  "ACTIONS_ID_TOKEN_REQUEST_TOKEN"];

function credentials() {
  const hashes = new Map();
  for (const line of fs.readFileSync(hashFile, "utf8").split("\n")) {
    const [label, h] = line.trim().split(/\s+/);
    if (label && /^[0-9a-f]{12}$/.test(h || "")) hashes.set(h, label);
  }
  if (!hashes.size) return out("credentials", "unchecked", "the secret hashes file is empty");
  const h12 = (v) => createHash("sha256").update(v).digest("hex").slice(0, 12);
  const names = CREDENTIAL_NAMES.filter((n) => n in process.env);
  const values = [...new Set(Object.values(process.env).map((v) => hashes.get(h12(v))).filter(Boolean))];
  for (const label of values) out("secret", "env", label);
  for (const name of names) out("env-name", "present", name);
  out("credentials", names.length || values.length ? "found" : "clean", `${hashes.size} secrets checked`);
}

// The test app, on this command's own loopback: a page that opens a WebSocket back to it and reports WebGL's
// renderer. A minimal WebSocket server, so the probe needs nothing but the project's Playwright.
function startApp() {
  const page = `<!doctype html><title>factory browser probe</title><canvas id=c width=64 height=64></canvas><script>
window.result = new Promise((resolve) => {
  const gl = document.getElementById("c").getContext("webgl");
  const dbg = gl && gl.getExtension("WEBGL_debug_renderer_info");
  const renderer = gl ? (dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) : "no webgl";
  const ws = new WebSocket("ws://" + location.host + "/ws");
  const t = setTimeout(() => resolve({ renderer, ws: "timeout" }), 10000);
  ws.onopen = () => ws.send("ping");
  ws.onmessage = (e) => { clearTimeout(t); resolve({ renderer, ws: e.data }); };
  ws.onerror = () => { clearTimeout(t); resolve({ renderer, ws: "error" }); };
});
</script>`;
  const server = http.createServer((req, res) => {
    res.writeHead(200, { "content-type": "text/html" });
    res.end(req.url === "/film" ? FILM_PAGE : req.url === "/film-claims" ? CLAIMS_PAGE : page);
  });
  server.on("upgrade", (req, sock) => {
    const accept = createHash("sha1").update(req.headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest("base64");
    sock.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
    sock.once("data", (b) => {
      // One short masked text frame from the page: answer "pong:<text>", unmasked.
      const len = b[1] & 0x7f, mask = b.subarray(2, 6), data = b.subarray(6, 6 + len);
      const reply = Buffer.from("pong:" + Buffer.from(data.map((x, i) => x ^ mask[i % 4])).toString());
      sock.write(Buffer.concat([Buffer.from([0x81, reply.length]), reply]));
    });
    sock.on("error", () => {});
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

// A navigation's outcome: reached (any response at all) or refused.
async function navigate(check, context, url) {
  const page = await context.newPage();
  try {
    const res = await page.goto(url, { timeout: 15000 });
    out(check, "reached", `${url} ${res ? res.status() : "no response"}`);
  } catch (e) {
    out(check, "refused", `${url} ${why(e)}`);
  } finally {
    await page.close().catch(() => {});
  }
}

const magic = (buf, bytes) => buf.length > 100 && buf.subarray(0, bytes.length).equals(Buffer.from(bytes));

// The flags the front end forces on every browser (process/factory.md D6 rule 3), as chrome://version shows them.
const FORCED = ["--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1",
  "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"];
// What a hostile client asks for: none of it may take effect.
const HOSTILE_ADDRESS = "203.0.113.7";
const HOSTILE = JSON.stringify({
  headless: false, executablePath: "/bin/false", proxy: { server: `http://${HOSTILE_ADDRESS}:3128` },
  args: [`--host-resolver-rules=MAP * ${HOSTILE_ADDRESS}`, "--remote-debugging-port=9333"],
});

async function commandLine(browser) {
  const c = await browser.newContext();
  try {
    const p = await c.newPage();
    await p.goto("chrome://version", { timeout: 15000 });
    return await p.locator("#command_line").innerText();
  } finally {
    await c.close().catch(() => {});
  }
}

const count = (text, part) => text.split(part).length - 1;

// The sandbox's proxy, asked for another port on the browser host: it must refuse (the stage's allowedDomains names
// one port). Without a proxy (the control) there's nothing to ask.
function otherPort() {
  const proxy = process.env.HTTP_PROXY || process.env.http_proxy;
  const host = process.env.FACTORY_BROWSER_HOST, port = Number(process.env.FACTORY_BROWSER_PORT);
  if (!proxy) return Promise.resolve(out("narrow", "unchecked", "no proxy: outside the sandbox"));
  const u = new URL(proxy);
  return new Promise((resolve) => {
    const sock = net.connect(Number(u.port || 80), u.hostname, () => {
      const auth = u.username ? `Proxy-Authorization: Basic ${Buffer.from(`${u.username}:${u.password}`).toString("base64")}\r\n` : "";
      sock.write(`CONNECT ${host}:${port + 1} HTTP/1.1\r\nHost: ${host}:${port + 1}\r\n${auth}\r\n`);
    });
    let head = "";
    const done = (result, detail) => { sock.destroy(); resolve(out("narrow", result, detail)); };
    sock.setTimeout(10000, () => done("unchecked", "the proxy didn't answer"));
    sock.on("data", (b) => {
      head += b;
      const m = head.match(/^HTTP\/1\.[01] (\d{3})/);
      if (m) done(m[1] === "403" ? "refused" : m[1] === "200" ? "allowed" : "unchecked", `${host}:${port + 1} ${m[1]}`);
    });
    sock.on("error", (e) => done("unchecked", e.message));
  });
}

// The first outside host CD allowed (factory.json browser.allow), fetched the way a project's route helper fetches
// it: Node's fetch, through the sandbox's proxy when there is one (with-browser sets NODE_USE_ENV_PROXY). One request
// per run, and factory-smoke runs this twice (the control and the agent). With the entry's probe path
// (FACTORY_BROWSER_PROBE), a GET of it, which must answer 2xx: the host serves what the specs fetch. Without one, a
// HEAD of the root, where any HTTP status proves only the path through the proxy (a CDN with nothing at its root
// answers 522), so the line says so.
async function allowedHost() {
  const host = (process.env.FACTORY_BROWSER_ALLOW || "").split(/\s+/).filter(Boolean)[0];
  if (!host) return out("allowed", "none", "browser.allow is empty");
  const probe = process.env.FACTORY_BROWSER_PROBE || "";
  try {
    const r = await fetch(`https://${host}${probe || "/"}`,
      { method: probe ? "GET" : "HEAD", redirect: "manual", signal: AbortSignal.timeout(15000) });
    if (!probe) return out("allowed", "reached", `${host} ${r.status} HEAD /: any answer counts; browser.allow's probe checks content`);
    await r.body?.cancel().catch(() => {});
    out("allowed", r.status >= 200 && r.status < 300 ? "reached" : "answered", `${host} ${r.status} GET ${probe}`);
  } catch (e) {
    const cause = e && e.cause && (e.cause.code || e.cause.message);
    out("allowed", "unreached", `${host} ${cause || why(e)}`);
  }
}

// The filmed pass's overlay (evidence_film.mjs, D6 rule 7), which the job copies beside this file: the same stepped
// move on a page with a canvas under a DOM button, in a plain context and a filmed one. The overlay must change no hit
// test, no pointer coordinate and nothing an observer of <body> sees; it must draw the pointer; and a gesture must
// hold each step. Timing is checked only from below: the remote browser makes everything slower, never faster.
const FILM_PAGE = `<!doctype html><title>factory film probe</title><style>body{margin:0}canvas{position:absolute;left:0;top:0}
#b{position:absolute;left:200px;top:200px;width:90px;height:32px}</style><canvas id=c width=640 height=480></canvas>
<button id=b>Undo</button><script>
window.__moves = []; window.__body = 0;
addEventListener("pointermove", (e) => __moves.push([e.clientX, e.clientY, (document.elementFromPoint(e.clientX, e.clientY) || {}).id || "none", performance.now()]), { capture: true });
new MutationObserver((r) => { __body += r.length; }).observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
</script>`;
// The pace claim's checks (paceCounts and the reasons the module logs), on a page with a button, an input, a frame with
// an input of its own, and a second frame inside an open shadow root. Each case below says what it must count and the
// reason it must log (or not): film-claims holds the cases without a frame, film-frames the ones with, and
// film-caption checks by the strip's pixels that a gesture's "Watch" caption is gone after it.
const CLAIMS_PAGE = `<!doctype html><title>factory film claims</title><style>body{margin:0}
#b{position:absolute;left:200px;top:200px;width:90px;height:32px}#i{position:absolute;left:200px;top:300px;width:150px;height:24px}
#f{position:absolute;left:400px;top:100px;width:200px;height:150px;border:0}#w{position:absolute;left:20px;top:340px;display:block}
</style><button id=b>Undo</button><input id=i>
<iframe id=f srcdoc="<input id=fi style='width:180px'><button style='width:100%;height:110px'>in a frame</button>"></iframe>
<x-w id=w></x-w><script>
// A frame inside an open shadow root, where document's own lookups stop at the host.
customElements.define("x-w", class extends HTMLElement { constructor() { super(); const f = document.createElement("iframe");
  f.srcdoc = "<input id=si>"; f.style.cssText = "display:block;width:160px;height:120px;border:0";
  this.attachShadow({ mode: "open" }).append(f); } });
</script>`;
// Checked after the gesture, with the pointer and the caption strip drawn: the pointer's tip, the button, and a point
// under the strip at the bottom edge.
const FILM_POINTS = [[400, 240], [245, 216], [10, 10], [300, 470], [630, 476]];

async function filmChecks(browser, appUrl) {
  let film;
  try {
    film = await import(new URL("./evidence_film.mjs", import.meta.url).href);
  } catch (e) {
    return out("film", "unchecked", `evidence_film.mjs didn't load beside the probe: ${e.message}`);
  }
  const pass = async (filmed) => {
    const saved = [process.env.FACTORY_EVIDENCE_PACE, process.env.FACTORY_EVIDENCE_VIDEO];
    [process.env.FACTORY_EVIDENCE_PACE, process.env.FACTORY_EVIDENCE_VIDEO] = filmed ? ["1", "1"] : ["0", "0"];
    const context = await browser.newContext({ viewport: { width: 640, height: 480 } });
    try {
      const on = await film.filmContext(context);
      const page = await context.newPage();
      await page.goto(`${appUrl}film`, { timeout: 30000 });
      await page.mouse.move(100, 210);
      await page.evaluate(() => { window.__moves = []; window.__body = 0; });
      await film.gesture(page, "the probe's stepped move", () => page.mouse.move(400, 240, { steps: 8 }));
      const hits = await page.evaluate((pts) => pts.map(([x, y]) => (document.elementFromPoint(x, y) || {}).id || "none"), FILM_POINTS);
      const r = await page.evaluate(() => ({ moves: window.__moves, body: window.__body,
        host: document.documentElement.querySelectorAll(":scope > factory-film").length }));
      let drawn = null;
      if (on) {
        const clip = { x: 398, y: 238, width: 12, height: 14 };
        const shot = await page.screenshot({ clip });
        await page.evaluate(() => { document.querySelector("factory-film").style.display = "none"; });
        drawn = !shot.equals(await page.screenshot({ clip }));
      }
      return { on, hits, ...r, drawn };
    } finally {
      await context.close().catch(() => {});
      [process.env.FACTORY_EVIDENCE_PACE, process.env.FACTORY_EVIDENCE_VIDEO] = saved;
    }
  };
  try {
    const plain = await pass(false), filmed = await pass(true);
    if (plain.on || !filmed.on) return out("film", "unchecked", `filmContext filmed ${plain.on}/${filmed.on}, expected false/true`);
    // Each step's own hit test, made in the page as the pointer arrived (the pointer drawn there in the filmed pass),
    // and the points above once the gesture's caption is showing.
    const targets = (r) => r.moves.map((m) => m[2]).concat(r.hits).join(",");
    out("film-hits", targets(plain) === targets(filmed) ? "same" : "changed", `plain ${targets(plain)} filmed ${targets(filmed)}`);
    const path = (r) => r.moves.map(([x, y]) => `${x},${y}`).join(" ");
    out("film-path", path(plain) === path(filmed) && plain.moves.length === 8 ? "same" : "changed",
      `${filmed.moves.length} moves: ${path(filmed)}`);
    out("film-observed", filmed.body === 0 && plain.body === 0 && filmed.host === 1 ? "none" : "seen",
      `body records plain ${plain.body} filmed ${filmed.body}; overlay elements under <html> ${filmed.host}`);
    out("film-drawn", filmed.drawn ? "drawn" : "missing", "the pointer at the move's end");
    const gaps = filmed.moves.slice(1).map((m, i) => m[3] - filmed.moves[i][3]);
    const least = gaps.length ? Math.round(Math.min(...gaps)) : 0;
    // Each step is held STEP_MS after the browser takes it, so the page sees them at least that far apart; half of it
    // still tells paced from unpaced (a few ms), with room for the timers' slack.
    const floor = film.STEP_MS / 2;
    out("film-paced", gaps.length === 7 && least >= floor ? "paced" : "unpaced",
      `shortest gap between steps ${least} ms (want at least ${floor})`);
  } catch (e) {
    out("film", "unchecked", e.message);
  }
  await claimChecks(browser, appUrl, film);
}

async function claimChecks(browser, appUrl, film) {
  const saved = [process.env.FACTORY_EVIDENCE_PACE, process.env.FACTORY_EVIDENCE_VIDEO];
  [process.env.FACTORY_EVIDENCE_PACE, process.env.FACTORY_EVIDENCE_VIDEO] = ["1", "1"];
  const write = process.stderr.write;
  // One filmed gesture on its own page, with the module's counts and the reasons it logged.
  const run = async (steps, after) => {
    const context = await browser.newContext({ viewport: { width: 640, height: 480 } });
    const said = [];
    try {
      await film.filmContext(context);
      const page = await context.newPage();
      await page.goto(`${appUrl}film-claims`, { timeout: 30000 });
      await page.mouse.move(100, 100);
      process.stderr.write = (chunk) => { said.push(String(chunk)); return true; };
      try {
        await film.gesture(page, "a probe case", () => steps(page));
      } finally {
        process.stderr.write = write;
      }
      return { ...film.paceCounts(page), said: said.join(""), extra: after ? await after(page) : null };
    } finally {
      process.stderr.write = write;
      await context.close().catch(() => {});
    }
  };
  // The caption strip's pixels at the bottom edge, with the overlay shown and then hidden.
  const strip = { x: 0, y: 440, width: 640, height: 40 };
  const hidden = async (page) => {
    await page.evaluate(() => { document.querySelector("factory-film").style.display = "none"; });
    const shot = await page.screenshot({ clip: strip });
    await page.evaluate(() => { document.querySelector("factory-film").style.display = ""; });
    return shot;
  };
  try {
    // Steps of about 30 px, under MAX_STEP_PX. Each case: [name, steps, what it must count, the reason it must log].
    let during = null;
    const cases = [
      ["mouse+keys", async (page) => {
        during = await page.screenshot({ clip: strip });
        await page.mouse.move(245, 216, { steps: 6 });
        await page.mouse.click(245, 216);
        await page.mouse.dblclick(245, 216);
        await page.mouse.down();
        await page.mouse.up();
        await page.mouse.move(275, 312, { steps: 4 });
        await page.mouse.click(275, 312);
        await page.keyboard.type("ab");
        await page.keyboard.press("Shift+C");
      }, (c) => c.paced > 0 && c.unpaced === 0 && c.unchecked === 0, null],
      ["locator-click", async (page) => {
        await page.mouse.move(245, 216, { steps: 6 });
        await page.locator("#b").click();
      }, (c) => c.unpaced > 0, "didn't send"],
      ["dblclick+locator", async (page) => {
        await page.mouse.move(245, 216, { steps: 6 });
        await page.mouse.dblclick(245, 216);
        await page.locator("#b").click();
      }, (c) => c.unpaced > 0, "didn't send"],
    ];
    // A frame's cases. Up to the frame's edge (x 400), then a click just inside it: a move into the frame would cross it.
    const frameCases = [
      ["click", async (page) => {
        await page.mouse.move(390, 175, { steps: 10 });
        await page.mouse.click(410, 175);
      }, (c) => c.unpaced === 0 && c.unchecked > 0, "not checked"],
      ["locator+move", async (page) => {
        await page.frameLocator("#f").locator("button").click();
        await page.mouse.move(100, 300, { steps: 16 });
      }, (c) => c.unpaced > 0, "moved outside page.mouse"],
      ["across", async (page) => {
        await page.mouse.move(380, 175, { steps: 10 });
        await page.mouse.move(620, 175, { steps: 8 });
      }, (c) => c.unpaced > 0, "lands on a frame"],
      // A frame takes these, so they're left out of the sent counts: the locator's press or key then reads as foreign.
      ["key+locator", async (page) => {
        await page.frameLocator("#f").locator("#fi").focus();
        await page.keyboard.type("ab");
        await page.locator("#i").press("x");
      }, (c) => c.unpaced > 0, "didn't send"],
      ["click+locator", async (page) => {
        await page.mouse.move(390, 175, { steps: 10 });
        await page.mouse.click(410, 175);
        await page.locator("#b").click();
      }, (c) => c.unpaced > 0, "didn't send"],
      // The frame inside an open shadow root: found by its point and by the focus.
      ["shadow-across", async (page) => {
        await page.mouse.move(10, 300, { steps: 8 });
        await page.mouse.move(10, 400, { steps: 4 });
        await page.mouse.move(200, 400, { steps: 8 });
      }, (c) => c.unpaced > 0, "lands on a frame"],
      ["shadow-key+locator", async (page) => {
        await page.frameLocator("#w iframe").locator("#si").focus();
        await page.keyboard.type("ab");
        await page.locator("#i").press("x");
      }, (c) => c.unpaced > 0, "didn't send"],
      // A click far into a frame jumped there: the jump is checked before the frame.
      ["far-click", async (page) => {
        await page.mouse.click(500, 175);
      }, (c) => c.unpaced > 0, "jumped"],
      // A click back out of the frame reaches the page and is counted as sent: no press reads as a locator's.
      ["click-out", async (page) => {
        await page.mouse.move(390, 175, { steps: 10 });
        await page.mouse.click(410, 175);
        await page.mouse.click(385, 175);
      }, (c) => c.unpaced === 0 && c.unchecked > 0, ["not checked", "didn't send"]],
      // A bare down is judged by where the pointer is: over the frame it's left out of the sent count, so the
      // locator's click then reads as foreign.
      ["down+locator", async (page) => {
        await page.mouse.move(390, 175, { steps: 10 });
        await page.mouse.click(410, 175);
        await page.mouse.down();
        await page.mouse.up();
        await page.locator("#b").click();
      }, (c) => c.unpaced > 0, "didn't send"],
    ];
    let captionShown = null, captionAfter = null;
    // reason: a string the log must hold, null for a silent log, or [a string it must hold, one it mustn't].
    const judge = async (group, list) => {
      const results = [];
      for (const [name, steps, want, reason] of list) {
        const c = await run(steps, name === "mouse+keys"
          ? async (page) => {
            const after = await page.screenshot({ clip: strip });
            const bare = await hidden(page);
            return { shown: !during.equals(bare), cleared: after.equals(bare) };
          } : null);
        if (c.extra) [captionShown, captionAfter] = [c.extra.shown, c.extra.cleared];
        const [must, mustNot] = Array.isArray(reason) ? reason : [reason, null];
        const ok = want(c) && (must === null ? c.said === "" : c.said.includes(must)) && !(mustNot && c.said.includes(mustNot));
        results.push({ name, ok, text: `${name} ${c.paced}/${c.unpaced}/${c.unchecked}${ok ? "" : ` WRONG (${c.said.trim().split("\n").map((l) => l.slice(7, 40)).join("; ") || "logged nothing"})`}` });
      }
      // Failing cases first, so the 300-character line keeps them.
      results.sort((a, b) => Number(a.ok) - Number(b.ok));
      out(group, results.every((r) => r.ok) ? "checked" : "wrong", `paced/unpaced/not checked: ${results.map((r) => r.text).join(", ")}`);
    };
    await judge("film-claims", cases);
    await judge("film-frames", frameCases);
    out("film-caption", captionShown && captionAfter ? "cleared" : "left",
      `the "Watch" caption ${captionShown ? "showed during the gesture" : "didn't show during the gesture"} and ${captionAfter ? "was gone after it" : "was still there after it"}`);
  } catch (e) {
    out("film-claims", "unchecked", e.message);
    out("film-frames", "unchecked", e.message);
  } finally {
    process.stderr.write = write;
    [process.env.FACTORY_EVIDENCE_PACE, process.env.FACTORY_EVIDENCE_VIDEO] = saved;
  }
}

async function main() {
  const endpoint = process.env.FACTORY_BROWSER_WS_ENDPOINT;
  if (!endpoint) return out("connect", "failed", "FACTORY_BROWSER_WS_ENDPOINT is unset: run under with-browser");
  credentials();
  const require = createRequire(path.join(path.resolve(projectDir), "package.json"));
  let pw;
  for (const name of ["@playwright/test", "playwright", "playwright-core"]) {
    try { pw = require(name); break; } catch { /* try the next */ }
  }
  if (!pw) return out("connect", "failed", `no Playwright client in ${projectDir}`);
  const server = await startApp();
  const appUrl = `http://localhost:${server.address().port}/`;
  let browser;
  try {
    // The client asks for everything ("*", which the front end forces anyway), so only the sandbox stands
    // between the browser and the outside world: the control, which has network, reaches it, and the agent
    // must not.
    browser = await pw.chromium.connect(endpoint, { exposeNetwork: "*", timeout: 120000 });
    out("connect", "ok", `Chromium ${browser.version()}`);
  } catch (e) {
    server.close();
    return out("connect", "failed", e.message);
  }
  fs.mkdirSync(os.tmpdir(), { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "browser-probe-"));
  try {
    // The app on this command's loopback, its WebSocket, and the GPU, recording what a stage would keep.
    const context = await browser.newContext({ viewport: { width: 640, height: 480 }, recordVideo: { dir: tmp, size: { width: 640, height: 480 } } });
    await context.tracing.start({ screenshots: true, snapshots: true });
    const page = await context.newPage();
    try {
      await page.goto(appUrl, { timeout: 30000 });
      out("app", "loaded", appUrl);
      const r = await page.evaluate(() => window.result);
      out("websocket", r.ws === "pong:ping" ? "echoed" : "failed", r.ws);
      out("gpu", /swiftshader|llvmpipe|software|no webgl/i.test(r.renderer) ? "software" : "hardware", r.renderer);
    } catch (e) {
      out("app", "failed", e.message);
    }
    // The evidence comes back through the front end: a screenshot, the trace and the video.
    try {
      const png = await page.screenshot();
      out("screenshot", magic(png, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]) ? "png" : "bad", `${png.length} bytes`);
      await context.tracing.stop({ path: path.join(tmp, "trace.zip") });
      const trace = fs.readFileSync(path.join(tmp, "trace.zip"));
      out("trace", magic(trace, [0x50, 0x4b, 0x03, 0x04]) ? "zip" : "bad", `${trace.length} bytes`);
      const video = page.video();
      await context.close();
      await video.saveAs(path.join(tmp, "video.webm"));
      const webm = fs.readFileSync(path.join(tmp, "video.webm"));
      out("video", magic(webm, [0x1a, 0x45, 0xdf, 0xa3]) ? "webm" : "bad", `${webm.length} bytes`);
    } catch (e) {
      out("evidence", "failed", e.message);
    }
    await filmChecks(browser, appUrl);

    // The forced launch flags, from the browser's own command line. The resolver rule keeps every name the
    // browser would look up itself (a context proxy's, a STUN server's) off the host's resolver; the host's own
    // check proves no lookup leaves it (D6).
    try {
      const cmd = await commandLine(browser);
      const missing = FORCED.filter((w) => !cmd.includes(w));
      const resolverRules = count(cmd, "--host-resolver-rules=");
      out("flags", missing.length ? "missing" : resolverRules !== 1 ? "doubled" : "present",
        missing.join(" ") || `${resolverRules} resolver rules`);
    } catch (e) {
      out("flags", "unread", e.message);
    }

    // The outside world through the tunnel, by name and by address.
    const plain = await browser.newContext();
    await navigate("outside-name", plain, "http://example.com/");
    await navigate("outside-ip", plain, "http://1.1.1.1/");
    await plain.close();
    // A context's own proxy, which skips the tunnel: by address (the host's outbound block) and by name (the
    // resolver rule). Refused for the control too: the host's own boundary, not the sandbox's.
    for (const [check, proxy] of [["proxy-ip", "http://1.1.1.1:80"], ["proxy-name", "http://one.one.one.one:80"]]) {
      const c = await browser.newContext({ proxy: { server: proxy } });
      await navigate(check, c, "http://example.com/");
      await c.close();
    }
    // A page that reaches the host's loopback directly (a proxy whose bypass names it) must open no WebSocket to a
    // run-server, which listens on a secret path. Which ports answered plain HTTP is shown, not judged.
    try {
      const c = await browser.newContext({ proxy: { server: "http://203.0.113.1:9", bypass: "127.0.0.1,localhost" } });
      const p = await c.newPage();
      await p.setContent("<title>loopback</title>");
      // The run-servers listen on the host's loopback at port_base + 100 + minor (D6 rule 3).
      const first = Number(process.env.FACTORY_BROWSER_PORT_BASE || 3100) + 100;
      const r = await p.evaluate(async (first) => {
        const ports = Array.from({ length: 100 }, (_, i) => first + i);
        const opened = [];
        await Promise.all(ports.map((port) => new Promise((done) => {
          const ws = new WebSocket(`ws://127.0.0.1:${port}/`);
          const t = setTimeout(() => { ws.close(); done(); }, 5000);
          ws.onopen = () => { opened.push(port); clearTimeout(t); ws.close(); done(); };
          ws.onerror = () => { clearTimeout(t); done(); };
        })));
        const answered = await Promise.all(ports.map((port) => fetch(`http://127.0.0.1:${port}/`, { mode: "no-cors" })
          .then(() => port, () => null)));
        return { opened, answered: answered.filter(Boolean) };
      }, first);
      // The control for the check below: the page did reach the run-servers' ports, so a WebSocket refused there was
      // refused by them, not unreachable.
      out("loopback", r.answered.length ? "reached" : "unreached", `plain HTTP answered on ${r.answered.join(",") || "no port"} of ${first}-${first + 99}`);
      out("runserver-ws", r.opened.length ? "opened" : "none", r.opened.join(","));
      await c.close();
    } catch (e) {
      out("runserver-ws", "unchecked", e.message);
    }
  } finally {
    await browser.close().catch(() => {});
    server.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  // A client asking for another browser, its own launch options (a program, headed, a proxy, its own resolver rule
  // and a debugging port) and loopback only, in the headers and the query: the front end must replace all of it.
  // Sent after the first browser closed, since the host holds two at once.
  try {
    const q = new URLSearchParams({ "launch-options": HOSTILE, browser: "firefox", proxy: "<loopback>" });
    const hostile = await pw.chromium.connect(`${endpoint}?${q}`, {
      timeout: 120000,
      headers: { "x-playwright-launch-options": HOSTILE, "x-playwright-browser": "firefox", "x-playwright-proxy": "<loopback>" },
    });
    try {
      const cmd = await commandLine(hostile);
      const name = hostile.browserType().name();
      const honored = [cmd.includes(HOSTILE_ADDRESS) && "its address", cmd.includes("9333") && "its debugging port",
        !cmd.includes("--headless") && "headed", FORCED.some((f) => !cmd.includes(f)) && "without the forced flags",
        name !== "chromium" && name].filter(Boolean);
      out("hostile", honored.length ? "honored" : "replaced", honored.join(", ") || `Chromium ${hostile.version()}`);
    } finally {
      await hostile.close().catch(() => {});
    }
  } catch (e) {
    // A program of the client's, if it had run, would have failed the launch.
    out("hostile", "failed", e.message);
  }
  await allowedHost();
  await otherPort();
}

try {
  await main();
} catch (e) {
  out("probe", "crashed", e.message);
}
process.stdout.write("end\n");
process.exit(0);
