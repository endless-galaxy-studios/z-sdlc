"""Pack a stage's browser evidence for upload (process/factory.md, D6 rule 7).

Usage: python3 -I evidence.py <workspace> <evidence dir, relative> <out-dir> <title>

Runs in the agent job after the agent step and quiesce, from the frozen copy (D2 rule 4). The agent writes only the
evidence directory (.factory/evidence/ in the workspace): its files and a manifest.json. Nothing there is trusted:
- the directory is opened component by component without following a link, and only regular files directly in
  it are read, each opened without following a link;
- manifest.json lists the files to keep, at most 30: [{"file", "step", "shows", "bug"}]. A file it doesn't list,
  or one that fails a check, is dropped and said why;
- screenshots (PNG) are decoded and written again from their image data alone, which drops every text and
  metadata chunk: at most 20, each at most 5 MB and 64 MB decoded;
- one video (WebM, its header checked, its bytes as recorded), at most 50 MB: inside the report when it's at most
  20 MB, so the one link plays it on a phone too (Safari plays Playwright's WebM), else beside it;
- one Playwright trace (a zip of plain relative names, at most 2000 entries and 200 MB unpacked), written again
  entry by entry;
- 150 MB in all.
It writes <out-dir>/evidence-report.html (self-contained: the manifest, the screenshots and the video inline, no
script, and a content policy that loads nothing), evidence-video.webm for a video too big for the report,
evidence-trace.zip when there's a trace, and evidence.json (what was packed, and what was dropped and why), which the
writer job renders into the PR. Its video_in_report says where the video went. That record
also names the issue and the run, from the job's own ISSUE_NUMBER and GITHUB_RUN_ID, so the archive (host/
evidence_archive.py) files the run's evidence where the PR said it would be. It prints
a summary, and step outputs when GITHUB_OUTPUT is set: report, video and trace say which files to upload. Evidence is optional: no directory, or nothing to keep, packs
nothing and exits 0.
"""

import base64
import html
import io
import json
import os
import pathlib
import re
import stat
import struct
import sys
import zipfile
import zlib

MAX_ENTRIES = 30
MAX_PNG, MAX_PNG_COUNT, MAX_PNG_RAW = 5 << 20, 20, 64 << 20
MAX_VIDEO = 50 << 20
# The largest video the report holds: 27 MB as base64, and with 20 screenshots at their cap the report stays under the
# archive's 200 MB a file.
MAX_EMBED = 20 << 20
MAX_TRACE, MAX_TRACE_RAW, MAX_TRACE_ENTRIES = 50 << 20, 200 << 20, 2000
MAX_TOTAL = 150 << 20
MAX_SHOWS = 300
MAX_DROPPED = 20
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\.(png|webm|zip)")
ENTRY = re.compile(r"[A-Za-z0-9._@-]+(/[A-Za-z0-9._@-]+)*/?")
KINDS = {"png": "screenshot", "webm": "video", "zip": "trace"}
MAX_WHY = 200
PNG_SIG = b"\x89PNG\r\n\x1a\n"
# Bytes per pixel, by colour type, at 8 bits a sample: grey, RGB, palette, grey+alpha, RGBA.
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class Bad(Exception):
    pass


def open_dir(base, rel):
    """A descriptor for base/rel, each component opened without following a link; None if it doesn't exist."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(base, flags)
    try:
        for part in pathlib.PurePosixPath(rel).parts:
            if part in (".", "..", "/"):
                raise Bad(f"the evidence directory {rel!r} must be a plain relative path")
            nxt = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except FileNotFoundError:
        os.close(fd)
        return None
    except OSError as e:
        os.close(fd)
        raise Bad(f"the evidence directory isn't a plain directory: {e.strerror}")


def read_file(dir_fd, name, cap):
    """A regular file's bytes, opened without following a link, refused past cap."""
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    except OSError as e:
        raise Bad(f"can't open it: {e.strerror}")
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise Bad("not a regular file")
        if st.st_size > cap:
            raise Bad(f"{st.st_size} bytes, over the cap of {cap}")
        data = b""
        while len(data) <= cap:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            data += chunk
        if len(data) > cap:
            raise Bad(f"over the cap of {cap} bytes")
        return data
    finally:
        os.close(fd)


def chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def clean_png(data):
    """The PNG written again from its header, palette and image data alone, the image data decompressed and
    compressed again: every ancillary chunk (text, EXIF, ICC, time) and anything after the image is gone."""
    if not data.startswith(PNG_SIG):
        raise Bad("not a PNG")
    pos, ihdr, plte, idat, ended = 8, None, None, [], False
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        crc = data[pos + 8 + length:pos + 12 + length]
        if len(body) != length or len(crc) != 4 or struct.unpack(">I", crc)[0] != zlib.crc32(kind + body) & 0xFFFFFFFF:
            raise Bad("a PNG chunk is truncated or its checksum is wrong")
        pos += 12 + length
        if kind == b"IHDR":
            ihdr = body
        elif kind == b"PLTE":
            if not 3 <= len(body) <= 768 or len(body) % 3:
                raise Bad("a PNG palette that isn't 1 to 256 colours")
            plte = body
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            ended = True
            break
    if not ended or ihdr is None or len(ihdr) != 13 or not idat:
        raise Bad("a PNG without its header, image data or end")
    width, height, depth, colour, compression, filtering, interlace = struct.unpack(">IIBBBBB", ihdr)
    if depth != 8 or colour not in CHANNELS or compression or filtering or interlace:
        raise Bad("only 8-bit, non-interlaced PNGs are kept (as Playwright writes them)")
    if colour == 3 and plte is None:
        raise Bad("a palette PNG without its palette")
    if not 0 < width <= 16384 or not 0 < height <= 65536:
        raise Bad(f"a PNG of {width}x{height}")
    want = height * (1 + width * CHANNELS[colour])
    if want > MAX_PNG_RAW:
        raise Bad(f"a PNG of {width}x{height} decodes past {MAX_PNG_RAW} bytes")
    inflater = zlib.decompressobj()
    try:
        raw = inflater.decompress(b"".join(idat), want + 1)
    except zlib.error:
        raise Bad("the PNG's image data doesn't decompress")
    if len(raw) != want or not inflater.eof:
        raise Bad("the PNG's image data isn't the size its header says")
    if any(raw[i] > 4 for i in range(0, want, 1 + width * CHANNELS[colour])):
        raise Bad("the PNG's image data has an unknown row filter")
    out = PNG_SIG + chunk(b"IHDR", ihdr)
    if colour == 3:
        out += chunk(b"PLTE", plte)
    return out + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def check_webm(data):
    if not data.startswith(b"\x1a\x45\xdf\xa3") or b"webm" not in data[:64]:
        raise Bad("not a WebM video")
    return data


def clean_trace(data):
    """The trace zip written again entry by entry, with plain relative names only."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except (zipfile.BadZipFile, ValueError):
        raise Bad("not a zip")
    if len(infos) > MAX_TRACE_ENTRIES:
        raise Bad(f"{len(infos)} entries, over {MAX_TRACE_ENTRIES}")
    if sum(i.file_size for i in infos) > MAX_TRACE_RAW:
        raise Bad(f"unpacks past {MAX_TRACE_RAW} bytes")
    # Playwright writes stored and deflated entries. Others (bzip2, lzma) decompress a whole block at once, past any
    # size cap: an entry of a few kilobytes can claim ten bytes and unpack to gigabytes.
    if any(i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) for i in infos):
        raise Bad("an entry compressed other than stored or deflated")
    names = [i.filename for i in infos]
    if len(set(names)) != len(names) or not any(n.endswith(".trace") for n in names):
        raise Bad("not a Playwright trace (no .trace entry, or a repeated name)")
    out = io.BytesIO()
    total = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as w:
        for info in infos:
            name = info.filename
            if not ENTRY.fullmatch(name) or ".." in name.split("/"):
                raise Bad(f"an entry with a name that isn't plain: {plain(name, 60)}")
            if name.endswith("/"):
                continue
            with zf.open(info) as f:
                body = f.read(info.file_size + 1)
            if len(body) != info.file_size:
                raise Bad(f"an entry that isn't the size it says: {name[:60]}")
            total += len(body)
            if total > MAX_TRACE_RAW:
                raise Bad(f"unpacks past {MAX_TRACE_RAW} bytes")
            w.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), body)
    return out.getvalue()


def plain(text, cap=80):
    """Text that's safe anywhere: printable ASCII, everything else escaped (a name that isn't UTF-8, which os.listdir
    hands over with surrogates, a control character or a newline that would start a workflow command), capped."""
    return "".join(c if " " <= c <= "~" else c.encode("unicode_escape", "backslashreplace").decode("ascii")
                   for c in text)[:cap]


def manifest_entries(raw):
    try:
        entries = json.loads(raw)
    except ValueError:
        raise Bad("manifest.json isn't JSON")
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise Bad(f"manifest.json must be a list of at most {MAX_ENTRIES} entries")
    out, seen = [], set()
    for e in entries:
        if not isinstance(e, dict) or set(e) != {"file", "step", "shows", "bug"}:
            raise Bad('each manifest entry is exactly {"file", "step", "shows", "bug"}')
        f, step, shows, bug = e["file"], e["step"], e["shows"], e["bug"]
        if not isinstance(f, str) or not NAME.fullmatch(f) or f in seen:
            raise Bad(f"a manifest file name that isn't plain, or is listed twice: {str(f)[:60]!r}")
        if not isinstance(step, int) or isinstance(step, bool) or not 1 <= step <= 999:
            raise Bad(f"{f}: step must be a whole number from 1 to 999")
        if not isinstance(shows, str) or not shows.strip() or len(shows) > MAX_SHOWS or not shows.isprintable():
            raise Bad(f"{f}: shows must be one printable line of at most {MAX_SHOWS} characters")
        if not isinstance(bug, bool):
            raise Bad(f"{f}: bug must be true or false")
        seen.add(f)
        out.append({"file": f, "step": step, "shows": " ".join(shows.split()), "bug": bug})
    return out


def report(title, packed, images, dropped, video=None):
    """The report page. video is (its manifest entry, its bytes, or None when it's too big to go inside)."""
    rows = "".join(
        f"<tr><td>{p['step']}</td><td><code>{html.escape(p['file'])}</code></td><td>{html.escape(p['shows'])}</td>"
        f"<td>{'yes' if p['bug'] else 'no'}</td></tr>" for p in sorted(packed, key=lambda p: (p["step"], p["file"])))
    shots = "".join(
        f"<figure><img alt=\"{html.escape(p['file'])}\" src=\"data:image/png;base64,{base64.b64encode(images[p['file']]).decode()}\">"
        f"<figcaption>Step {p['step']}: {html.escape(p['shows'])}{' (shows the bug)' if p['bug'] else ''}</figcaption></figure>"
        for p in sorted(packed, key=lambda p: (p["step"], p["file"])) if p["file"] in images)
    gone = "".join(f"<li><code>{html.escape(d['file'])}</code>: {html.escape(d['why'])}</li>" for d in dropped)
    film = ""
    if video:
        entry, body = video
        caption = f"Step {entry['step']}: {html.escape(entry['shows'])}{' (shows the bug)' if entry['bug'] else ''}"
        # No script, and no blob: URL: Safari on a phone plays a data: source in a video element, as measured. After
        # the table: a page shows nothing past a data: URL until all of it has arrived.
        film = (f'<figure><video controls playsinline preload="metadata" src="data:video/webm;base64,'
                f'{base64.b64encode(body).decode()}"></video><figcaption>{caption}</figcaption></figure>' if body else
                f"<p>The video, <code>{html.escape(entry['file'])}</code>, is over the {MAX_EMBED >> 20} MB this page "
                f"holds: it's the run's separate video artifact.</p>")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; media-src data:; style-src 'unsafe-inline'">
<title>{html.escape(title)}: browser evidence</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}}
.wide{{overflow-x:auto}}table{{border-collapse:collapse}}
td,th{{border:1px solid #ccc;padding:.3rem .6rem;text-align:left;vertical-align:top}}
figure{{margin:1.5rem 0}}img,video{{max-width:100%;border:1px solid #ccc}}video{{width:100%}}</style></head><body>
<h1>{html.escape(title)}: browser evidence</h1>
<p>Written by the factory's frozen code from what the agent left. Each screenshot is written again from its image data
alone, which drops its metadata; the video's header is checked, and its bytes are as recorded. The text is the agent's
own description, shown as text.</p>
<div class="wide"><table><tr><th>Step</th><th>File</th><th>What it shows</th><th>Shows the bug</th></tr>{rows}</table></div>
{film}
{shots}
{f'<h2>Dropped</h2><ul>{gone}</ul>' if gone else ''}
</body></html>
"""


def pack(workspace, rel, out, title):
    """Pack the evidence; returns evidence.json's content."""
    result = {"files": [], "dropped": [], "report": False, "video": False, "video_in_report": False, "trace": False}
    fd = open_dir(workspace, rel)
    if fd is None:
        return result
    try:
        names = sorted(os.listdir(fd))
        try:
            entries = manifest_entries(read_file(fd, "manifest.json", 1 << 20)) if "manifest.json" in names else []
        except Bad as e:
            result["dropped"].append({"file": "manifest.json", "why": plain(str(e), MAX_WHY)})
            entries = []
        except RecursionError:
            result["dropped"].append({"file": "manifest.json", "why": "nested too deep to read"})
            entries = []
        if "manifest.json" not in names and names:
            result["dropped"].append({"file": "manifest.json", "why": "missing: every file is dropped without it"})
        listed = {e["file"] for e in entries}
        result["dropped"] += [{"file": plain(n), "why": "not in the manifest"} for n in names
                              if n != "manifest.json" and n not in listed]
        images, total, pngs, video = {}, 0, 0, None
        out.mkdir(parents=True, exist_ok=True)
        for e in entries:
            f = e["file"]
            try:
                kind = f.rsplit(".", 1)[1]
                if kind not in KINDS:
                    raise Bad("not a PNG, WebM or zip")
                if f not in names:
                    raise Bad("listed in the manifest but not there")
                if kind == "png":
                    if pngs >= MAX_PNG_COUNT:
                        raise Bad(f"more than {MAX_PNG_COUNT} screenshots")
                    body = clean_png(read_file(fd, f, MAX_PNG))
                elif kind == "webm":
                    if result["video"]:
                        raise Bad("only one video is kept")
                    body = check_webm(read_file(fd, f, MAX_VIDEO))
                else:
                    if result["trace"]:
                        raise Bad("only one trace is kept")
                    body = clean_trace(read_file(fd, f, MAX_TRACE))
                if total + len(body) > MAX_TOTAL:
                    raise Bad(f"over the {MAX_TOTAL} bytes all the evidence may take")
            except Bad as err:
                result["dropped"].append({"file": f, "why": plain(str(err), MAX_WHY)})
                continue
            except Exception as err:  # noqa: BLE001 - a crafted file must cost only itself, never the rest
                result["dropped"].append({"file": f, "why": f"couldn't be read: {type(err).__name__}"})
                continue
            total += len(body)
            if kind == "png":
                pngs += 1
                images[f] = body
            elif kind == "webm":
                video = (dict(e), body)
                result["video"] = True
            else:
                (out / "evidence-trace.zip").write_bytes(body)
                result["trace"] = True
            result["files"].append(dict(e, kind=KINDS[kind]))
    finally:
        os.close(fd)
    if len(result["dropped"]) > MAX_DROPPED:
        n = len(result["dropped"]) - MAX_DROPPED
        result["dropped"] = result["dropped"][:MAX_DROPPED] + [{"file": "...", "why": f"and {n} more files dropped"}]
    if video and len(video[1]) <= MAX_EMBED:
        result["video_in_report"] = True
    elif video:
        (out / "evidence-video.webm").write_bytes(video[1])
        video = (video[0], None)
    if result["files"]:
        (out / "evidence-report.html").write_text(report(title, result["files"], images, result["dropped"], video))
        result["report"] = True
    return result


def uploads(result):
    """Which files the job uploads: the video only when it isn't inside the report."""
    return {"report": result["report"], "video": result["video"] and not result["video_in_report"],
            "trace": result["trace"]}


def main():
    workspace, rel, out_dir, title = sys.argv[1:5]
    out = pathlib.Path(out_dir)
    try:
        result = pack(workspace, rel, out, " ".join(title.split())[:120])
    except Exception as e:  # noqa: BLE001 - the packer never fails the job: no evidence is a result
        result = {"files": [], "dropped": [{"file": plain(rel), "why": plain(str(e)) or type(e).__name__}],
                  "report": False, "video": False, "video_in_report": False, "trace": False}
    out.mkdir(parents=True, exist_ok=True)
    for key, var in (("issue", "ISSUE_NUMBER"), ("run", "GITHUB_RUN_ID")):
        value = os.environ.get(var, "")
        if value.isascii() and value.isdigit():
            result[key] = int(value)
    text = json.dumps(result, separators=(",", ":"))
    (out / "evidence.json").write_text(text + "\n")
    print(f"evidence: {len(result['files'])} kept, {len(result['dropped'])} dropped")
    for d in result["dropped"]:
        print(f"  dropped {plain(d['file'])}: {plain(d['why'], MAX_WHY)}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as o:
            for k, up in uploads(result).items():
                o.write(f"{k}={'yes' if up else 'no'}\n")
            o.write(f"manifest={text}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
