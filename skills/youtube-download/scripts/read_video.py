#!/usr/bin/env python3
"""read_video.py - one video -> one text file: details, description, chapters,
transcript, and comments if asked. Part of the youtube-download skill.

usage: python3 read_video.py [options] URL [URL ...]

  -o DIR            folder for the .md files (default: the current folder)
  --lang CODE       transcript language, e.g. en, de, ru (default: the video's own)
  --translated      allow a machine-translated transcript when no original exists
  --comments N      also fetch N top-level comment threads (default 0 = none)
  --sort top|new    which comments: most liked (default) or newest
  --browser NAME    use the person's login from this browser (firefox, chrome,
                    edge, safari, brave...) - only after the person agreed
  -h, --help        this text

Prints the path of each file written. Notes (no transcript in that language,
only a machine translation exists) go to stderr. Exit codes: 0 done, 1 yt-dlp
failed (its error is printed in full), 2 wrong arguments, 3 yt-dlp not found,
4 no transcript in the language given with --lang (nothing written; the note
lists the tracks there are).
Needs yt-dlp on PATH; Python 3.8+ standard library only. Reads nothing but
what yt-dlp returns for the given links; writes only the .md files and a
temporary folder that is removed at the end.
"""
import json
import os
import re
import shutil
# yt-dlp is run with an argument list, never through a shell; links come after "--"
import subprocess  # nosec B404
import sys
import tempfile
from datetime import datetime, timezone

class NoTrack(Exception):
    pass


BASE = ["yt-dlp", "--no-playlist", "--no-warnings", "-q"]


def fail(msg, code):
    print("read_video.py: " + msg, file=sys.stderr)
    sys.exit(code)


def ytdlp(args, extra):
    p = subprocess.run(BASE + extra + args, capture_output=True, text=True)  # noqa: S603 # nosec B603
    if p.returncode:
        raise RuntimeError("yt-dlp " + " ".join(args) + "\n" + p.stderr.strip())
    return p.stdout


def hms(s):
    s = int(s or 0)
    h, m, s = s // 3600, s // 60 % 60, s % 60
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def num(x):
    return "?" if x is None else "{:,}".format(x).replace(",", " ")


def base(code):
    return code.split("-")[0].lower()


def pick_track(info, lang, translated):
    """Return (code, automatic, note). Manual subtitles beat automatic captions;
    of automatic ones only the original (the "-orig" track) unless allowed."""
    want = lang or info.get("language") or ""
    manual = [k for k in (info.get("subtitles") or {}) if k != "live_chat"]
    auto = list(info.get("automatic_captions") or {})
    orig = [k for k in auto if k.endswith("-orig")]
    if want:
        for k in manual:
            if k.lower() == want.lower():
                return k, False, ""
        for k in manual:
            if base(k) == base(want):
                return k, False, ""
        for k in orig:
            if base(k) == base(want):
                return k, True, ""
        if not orig and not manual:
            # sites other than YouTube list their tracks under automatic_captions
            for k in auto:
                if base(k) == base(want):
                    return k, True, ""
        if lang:
            have = sorted(set(manual) | set(orig))
            if want in auto or any(base(k) == base(want) for k in auto):
                if translated:
                    k = want if want in auto else [k for k in auto if base(k) == base(want)][0]
                    return k, True, "machine translation into %s" % k
                return None, False, ("no %s transcript; only a machine translation exists "
                                     "(add --translated to use it). Original tracks: %s"
                                     % (lang, ", ".join(have) or "none"))
            return None, False, "no %s transcript. Tracks: %s" % (lang, ", ".join(have) or "none")
    if manual:
        return manual[0], False, ""
    if orig:
        # auto-dubbed videos carry several "-orig" tracks; without a known
        # language the first is a guess, so say which one was taken
        return orig[0], True, ("" if len(orig) == 1 else
                               "several original tracks (%s), took %s" % (", ".join(orig), orig[0]))
    if auto and not info.get("extractor_key", "").lower().startswith("youtube"):
        return auto[0], True, ""
    return None, False, "no subtitles or captions on the site"


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s).replace("&amp;", "&").replace("&lt;", "<").replace(
        "&gt;", ">").replace("&nbsp;", " ").strip()


def stamp(t):
    p = t.replace(",", ".").split(":")
    p = [float(x) for x in p]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def words_json3(path):
    out = []
    for e in json.load(open(path, encoding="utf-8")).get("events", []):
        t = e.get("tStartMs", 0) / 1000
        for i, s in enumerate(e.get("segs") or []):
            # each event starts on a word boundary: manual subtitles have one cue
            # per event without a leading space, and words would glue together
            w = (" " if i == 0 else "") + s.get("utf8", "").replace("\n", " ")
            if w.strip():
                out.append((t + s.get("tOffsetMs", 0) / 1000, w))
    return out


def words_cues(path):
    # WebVTT and SRT. Automatic captions repeat the previous line at the top of
    # every cue (rolling captions): a line equal to the last one kept is dropped.
    out, last, t = [], None, None
    for line in open(path, encoding="utf-8", errors="replace").read().splitlines():
        m = re.match(r"\s*([\d:.,]+)\s+-->\s+([\d:.,]+)", line)
        if m:
            t = stamp(m.group(1))
            continue
        if t is None or not line.strip() or line.strip().isdigit():
            continue
        txt = strip_tags(line)
        if txt and txt != last:
            out.append((t, " " + txt))
            last = txt
    return out


def transcript(path, chapters):
    words = words_json3(path) if path.endswith(".json3") else words_cues(path)
    marks = sorted((c["start_time"], c.get("title") or "") for c in chapters or [])
    out, block, ci, start = [], [], 0, None

    def flush():
        if block:
            out.append("[%s] %s" % (hms(start), re.sub(r"\s+", " ", "".join(block)).strip()))
        del block[:]

    for t, w in words:
        while ci < len(marks) and t >= marks[ci][0]:
            flush()
            start = None
            out.append("\n## %s %s\n" % (hms(marks[ci][0]), marks[ci][1]))
            ci += 1
        # paragraphs of about 30 seconds, ended at a sentence end when there is one
        if start is None or (t - start >= 30 and block and block[-1].rstrip()[-1:] in ".?!…") \
                or t - start >= 45:
            flush()
            start = t
        block.append(w)
    flush()
    return "\n".join(out).strip()


def comments_text(comments):
    comments = [c for c in comments if c.get("id")]  # yt-dlp sometimes yields stubs
    replies = {}
    for c in comments:
        if (c.get("parent") or "root") != "root":
            replies.setdefault(c["parent"], []).append(c)

    def head(c):
        h = "%s · %s · %s likes" % (c.get("author"), c.get("_time_text") or "", num(c.get("like_count") or 0))
        flags = [n for n, k in (("pinned", "is_pinned"), ("liked by the author", "is_favorited"),
                                ("the author", "author_is_uploader")) if c.get(k)]
        return h + (" · " + ", ".join(flags) if flags else "")

    blocks = []
    for c in comments:
        if (c.get("parent") or "root") != "root":
            continue
        b = ["- " + head(c), "  " + (c.get("text") or "").strip().replace("\n", "\n  ")]
        for r in replies.get(c["id"], []):
            b.append("    > " + head(r))
            b.append("      " + (r.get("text") or "").strip().replace("\n", "\n      "))
        blocks.append("\n".join(b))
    return "\n\n".join(blocks)


def safe_name(title):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", title or "video")
    name = re.sub(r"\s+", " ", name).strip(" .")[:150] or "video"
    return name


def read(url, a, extra):
    tmp = tempfile.mkdtemp(prefix="read_video-")
    try:
        # details first, without comments: fetching comments replaces
        # comment_count with the number fetched
        info = json.loads(ytdlp(["-J", "--flat-playlist", "--", url], extra))
        if info.get("_type") == "playlist":
            raise RuntimeError("this link is a playlist or channel; give one video link at a time "
                               "(list them with: yt-dlp --flat-playlist --print url LINK)")
        ij = os.path.join(tmp, "info.json")
        with open(ij, "w", encoding="utf-8") as f:
            json.dump(info, f)
        code, auto, note = pick_track(info, a["lang"], a["translated"])
        if a["lang"] and not code:
            raise NoTrack(note)
        text = ""
        if code:
            ytdlp(["--load-info-json", ij, "--skip-download",
                   "--write-auto-subs" if auto else "--write-subs", "--sub-langs", code,
                   "--sub-format", "json3/vtt/srt/best", "-o", os.path.join(tmp, "sub")], extra)
            subs = [os.path.join(tmp, f) for f in os.listdir(tmp)
                    if f.startswith("sub.") and f.rsplit(".", 1)[-1] in ("json3", "vtt", "srt")]
            if subs:
                text = transcript(subs[0], info.get("chapters"))
            else:
                note = "the %s track came in a format this script does not read" % code
        if note:
            print("note: %s: %s" % (info.get("title") or url, note), file=sys.stderr)
        comments = []
        if a["comments"]:
            n = a["comments"]
            got = json.loads(ytdlp(["-J", "--write-comments", "--extractor-args",
                                    "youtube:max_comments=%d,%d,%d,3;comment_sort=%s"
                                    % (n + n // 2, n, n // 2, a["sort"]), "--", url], extra))
            comments = got.get("comments") or []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    up = info.get("timestamp")
    date = (datetime.fromtimestamp(up, timezone.utc).strftime("%Y-%m-%d") if up
            else re.sub(r"(\d{4})(\d\d)(\d\d)", r"\1-\2-\3", info.get("upload_date") or "?"))
    L = ["# " + (info.get("title") or "?"), "",
         "link: " + (info.get("webpage_url") or url),
         "channel: %s · %s subscribers" % (info.get("channel") or info.get("uploader") or "?",
                                           num(info.get("channel_follower_count"))),
         "published: %s · length %s" % (date, hms(info.get("duration"))),
         "views %s · likes %s · comments %s" % (num(info.get("view_count")), num(info.get("like_count")),
                                                 num(info.get("comment_count"))),
         "language: %s · license: %s" % (info.get("language") or "?", info.get("license") or "?"),
         "read: " + datetime.now().strftime("%Y-%m-%d %H:%M") + " (comment ages count from here)"]
    if info.get("tags"):
        L.append("tags: " + ", ".join(info["tags"]))
    L += ["", "## Description", "", (info.get("description") or "").strip() or "(empty)"]
    if info.get("chapters"):
        L += ["", "## Chapters", ""] + ["%s %s" % (hms(c["start_time"]), c.get("title") or "")
                                        for c in info["chapters"]]
    kind = ("automatic captions" if auto else "subtitles") if code else ""
    L += ["", "# Transcript" + (" (%s, %s)" % (code, kind) if code else ""), "",
          text or "(no transcript: %s)" % (note or "the track was empty")]
    if a["comments"]:
        L += ["", "# Comments (%s, %d threads fetched)" % (a["sort"], sum(
            1 for c in comments if (c.get("parent") or "root") == "root")), "",
            comments_text(comments) or "(none)"]
    path = os.path.join(a["out"], safe_name(info.get("title")) + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


def main():
    args = sys.argv[1:]
    a = {"out": ".", "lang": None, "translated": False, "comments": 0, "sort": "top", "browser": None}
    urls = []
    while args:
        x = args.pop(0)
        if x in ("-h", "--help"):
            print(__doc__.strip())
            return 0
        if x in ("-o", "--lang", "--comments", "--sort", "--browser"):
            if not args:
                fail("%s needs a value" % x, 2)
            v = args.pop(0)
            if x == "-o":
                a["out"] = os.path.expanduser(v)
            elif x == "--lang":
                a["lang"] = v
            elif x == "--comments":
                if not v.isdigit():
                    fail("--comments takes a number, e.g. --comments 100", 2)
                a["comments"] = int(v)
            elif x == "--sort":
                if v not in ("top", "new"):
                    fail("--sort takes top or new", 2)
                a["sort"] = v
            else:
                a["browser"] = v
        elif x == "--translated":
            a["translated"] = True
        elif x.startswith("-") and "/" not in x:
            fail("unknown option %s (see --help)" % x, 2)
        else:
            urls.append(x)
    if not urls:
        fail("give at least one video link (see --help)", 2)
    if not shutil.which("yt-dlp"):
        fail("yt-dlp not found; install it first", 3)
    os.makedirs(a["out"], exist_ok=True)
    extra = ["--cookies-from-browser", a["browser"]] if a["browser"] else []
    code = 0
    for u in urls:
        try:
            print(read(u, a, extra), flush=True)
        except NoTrack as e:
            code = code or 4
            print("read_video.py: %s: %s" % (u, e), file=sys.stderr)
        except RuntimeError as e:
            code = 1
            print("read_video.py: %s\n%s" % (u, e), file=sys.stderr)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
