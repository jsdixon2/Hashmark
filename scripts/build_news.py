#!/usr/bin/env python3
"""Build data/news.json from free, public NFL RSS/Atom feeds.

Every feed here is published by its owner for syndication. We store only the
headline, a short summary, the source name, the time and a link back to the
original article. Feeds that fail are skipped and reported in "sources".
"""
import json, os, re, time, html, hashlib, urllib.request
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

FEEDS = [
    ("CBS Sports", "https://www.cbssports.com/rss/headlines/nfl/"),
    ("Yahoo Sports", "https://sports.yahoo.com/nfl/rss/"),
    ("ProFootballTalk", "https://profootballtalk.nbcsports.com/feed/"),
    ("RotoWire", "https://www.rotowire.com/rss/news.php?sport=NFL"),
    ("SB Nation", "https://www.sbnation.com/rss/nfl/index.xml"),
    ("Sporting News", "https://www.sportingnews.com/us/rss/nfl"),
    ("FantasyPros", "https://www.fantasypros.com/feed/"),
    ("Fox Sports", "https://api.foxsports.com/v2/content/optimized-rss?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244mlTDK1i&size=30&tags=fs/nfl"),
    ("RotoBaller", "https://www.rotoballer.com/category/nfl/feed"),
    ("PFF", "https://www.pff.com/feed"),
    ("Google News: NFL injuries", "https://news.google.com/rss/search?q=NFL+injury+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: NFL transactions", "https://news.google.com/rss/search?q=NFL+(signs+OR+traded+OR+released+OR+waived)+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: NFL depth chart", "https://news.google.com/rss/search?q=NFL+(starter+OR+%22depth+chart%22+OR+benched)+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: ESPN NFL", "https://news.google.com/rss/search?q=site:espn.com+NFL+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: NFL.com", "https://news.google.com/rss/search?q=site:nfl.com+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: The Ringer", "https://news.google.com/rss/search?q=site:theringer.com+NFL+when:3d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: Sports Illustrated", "https://news.google.com/rss/search?q=site:si.com+NFL+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: Bleacher Report", "https://news.google.com/rss/search?q=site:bleacherreport.com+NFL+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("CBS College Football", "https://www.cbssports.com/rss/headlines/college-football/"),
    ("Yahoo College Football", "https://sports.yahoo.com/college-football/rss/"),
    ("Google News: college football", "https://news.google.com/rss/search?q=college+football+(injury+OR+transfer+OR+portal+OR+depth+chart+OR+declares)+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: NFL draft prospects", "https://news.google.com/rss/search?q=NFL+draft+prospect+OR+big+board+when:3d&hl=en-US&gl=US&ceid=US:en"),
]
KEEP_HOURS = 96
MAX_ITEMS = 500
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15 HashmarkNews/1.0"

KINDS = [
    ("injury", r"injur|questionable|doubtful|ruled out|\bout for\b|\bout (?:vs|against|sunday|monday|thursday|this week)|torn|\bacl\b|achilles|hamstring|ankle|knee|concussion|\bir\b|injured reserve|carted|\bmri\b|surgery|did not practice|\bdnp\b|limited practice"),
    ("return", r"\breturn|activated|cleared|full practice|designated to return|back at practice|off (?:the )?ir"),
    ("trade", r"\btrade[ds]?\b|acquire"),
    ("release", r"releas|waive[ds]?\b|\bcut\b"),
    ("signing", r"\bsign(?:s|ed|ing)?\b|agree[ds]? to|contract|extension|re-sign"),
    ("suspension", r"suspen"),
    ("depth", r"starter|starting|named|bench(?:ed)?|demot|promot|depth chart|workhorse|lead back|snap share|role"),
    ("coaching", r"\bfired\b|\bhire[ds]?\b|coordinator|play-?call"),
]
BREAKING = re.compile(r"breaking|season-ending|out for (?:the )?season|torn (?:acl|achilles)|\btraded\b|\bacquire[sd]?\b|suspended|\bfired\b|placed on (?:injured reserve|ir)|retir", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def text(el):
    return (el.text or "").strip() if el is not None else ""


def clean(s, n=None):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return (s[: n - 1] + "…") if n and len(s) > n else s


def when(s):
    if not s:
        return None
    try:
        return int(parsedate_to_datetime(s).timestamp() * 1000)
    except Exception:
        pass
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def parse(raw):
    root = ET.fromstring(raw)
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        g = lambda name: next((c for c in it if c.tag.split("}")[-1] == name), None)
        title = clean(text(g("title")))
        link = text(g("link"))
        if not link and g("link") is not None:
            link = g("link").get("href", "")
        desc = clean(text(g("description")) or text(g("summary")) or text(g("content")), 280)
        ts = when(text(g("pubDate")) or text(g("published")) or text(g("updated")) or text(g("date")))
        if title and link:
            out.append((title, link, desc, ts))
    return out


def classify(t):
    low = t.lower()
    return [k for k, rx in KINDS if re.search(rx, low)]


def main():
    now = int(time.time() * 1000)
    cutoff = now - KEEP_HOURS * 3600 * 1000
    items, seen, status = [], set(), []
    for name, url in FEEDS:
        try:
            got = parse(fetch(url))
            n = 0
            for title, link, desc, ts in got:
                src = name
                if name.startswith("Google News"):
                    m = re.search(r"\s+-\s+([^-]+)$", title)
                    if m:
                        src = m.group(1).strip()
                        title = title[: m.start()].strip()
                ts = ts or now
                if ts < cutoff or ts > now + 3600 * 1000:
                    continue
                key = re.sub(r"[^a-z0-9]", "", title.lower())[:70]
                if key in seen:
                    continue
                seen.add(key)
                full = title + " " + desc
                items.append({
                    "id": hashlib.sha1(link.encode()).hexdigest()[:12],
                    "t": title, "s": desc, "src": src, "url": link, "ts": ts,
                    "k": classify(full), "brk": bool(BREAKING.search(title)),
                })
                n += 1
            status.append({"name": name, "url": url, "ok": True, "items": n})
        except Exception as e:
            status.append({"name": name, "url": url, "ok": False, "err": str(e)[:120]})
    items.sort(key=lambda x: -x["ts"])
    os.makedirs("data", exist_ok=True)
    with open("data/news.json", "w", encoding="utf-8") as f:
        json.dump({"built": now, "sources": status, "items": items[:MAX_ITEMS]}, f, ensure_ascii=False, separators=(",", ":"))
    ok = sum(1 for s in status if s["ok"])
    print(f"{len(items)} items from {ok}/{len(FEEDS)} feeds")
    for s in status:
        print(("  ok  " if s["ok"] else "  ERR ") + s["name"] + " <" + s["url"] + ">" + (f" ({s.get('items')})" if s["ok"] else f": {s['err']}"))


if __name__ == "__main__":
    main()
