#!/usr/bin/env python3
"""x26 data (owner 2026-11-16, test only): head coach, offensive and defensive coordinator for every NFL team-season
2016-2026 from Wikipedia's team-season pages (infobox fields; Wikipedia text is CC BY-SA, read through the public API).
Writes bt/nfl/coaches.json: {"YYYY|TM": {"hc": [...], "oc": [...], "dc": [...], "raw": {field: text}}}.
Names are public staff names (no user data). Runs in Actions (Wikipedia is not reachable from the cloud sessions).
Run: python3 scripts/fetch_coaches.py [first] [last]"""
import json, re, sys, time, urllib.parse, urllib.request

first = int(sys.argv[1]) if len(sys.argv) > 1 else 2016
last = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
UA = {"User-Agent": "HashmarkResearch/1.0 (sports analytics research; python-urllib)", "Api-User-Agent": "HashmarkResearch/1.0"}
NAMES = {"ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
         "CAR": "Carolina Panthers", "CHI": "Chicago Bears", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
         "DAL": "Dallas Cowboys", "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
         "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs",
         "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings", "NE": "New England Patriots", "NO": "New Orleans Saints",
         "NYG": "New York Giants", "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
         "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans",
         "LA": "Los Angeles Rams"}


def tname(tm, y):
    if tm == "LV": return "Oakland Raiders" if y < 2020 else "Las Vegas Raiders"
    if tm == "LAC": return "San Diego Chargers" if y < 2017 else "Los Angeles Chargers"
    if tm == "WAS": return "Washington Redskins" if y < 2020 else ("Washington Football Team" if y < 2022 else "Washington Commanders")
    return NAMES[tm]


def fetch_batch(titles):
    """up to 40 pages per request (query + revisions); returns {requested title: wikitext}"""
    u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": "|".join(titles),
         "format": "json", "redirects": 1, "formatversion": 2})
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
                j = json.loads(r.read().decode())
            q = j.get("query") or {}; back = {}
            for m in (q.get("normalized") or []) + (q.get("redirects") or []): back[m["to"]] = back.get(m["from"], m["from"])
            out = {}
            for pg in q.get("pages") or []:
                t = pg.get("title"); orig = back.get(t, t)
                while orig in back and back[orig] != orig: orig = back[orig]
                revs = pg.get("revisions") or []
                out[orig] = revs[0]["slots"]["main"]["content"] if revs else ""
            return out
        except Exception as e:
            print("  error", getattr(e, "code", ""), str(e)[:200], flush=True); time.sleep(3 + 5 * k)
    return {}


def clean(v):
    v = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", v, flags=re.S)
    v = re.sub(r"\{\{(?:nowrap|small)\|([^{}]*)\}\}", r"\1", v)
    v = re.sub(r"\{\{[^{}]*\}\}", "", v)
    v = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"<br\s*/?>|<hr\s*/?>|\n|;|/", ",", v)
    v = re.sub(r"'''?|<[^>]+>", "", v)
    return v.strip()


def names(v):
    out = []
    for part in re.split(r",|\band\b", v):
        part = re.sub(r"\([^)]*\)", "", part).strip(" .*")
        part = re.sub(r"^(interim|acting)\s+", "", part, flags=re.I)
        if part and len(part.split()) >= 2 and not re.search(r"\d", part): out.append(part)
    return out


out, seen = {}, set()
todo = [(y, tm, f"{y} {tname(tm, y)} season") for y in range(first, last + 1) for tm in list(NAMES) + ["LV", "LAC", "WAS"]]
texts = {}
for i in range(0, len(todo), 40):
    texts.update(fetch_batch([x[2] for x in todo[i:i + 40]])); print("fetched", min(i + 40, len(todo)), "of", len(todo), flush=True); time.sleep(1)
for y, tm, title in todo:
    if True:
        wt = texts.get(title, "")
        m = re.search(r"\{\{\s*Infobox NFL (?:team )?season(.*?)\n\}\}", wt, flags=re.S | re.I)
        box = m.group(1) if m else wt[:20000]
        raw = {}
        for fm in re.finditer(r"\n\s*\|\s*([a-z_ ]*coach[a-z_ ]*|[a-z_ ]*coordinator[a-z_ ]*)\s*=\s*(.*?)(?=\n\s*\||\Z)", box, flags=re.S | re.I):
            k = fm.group(1).strip().lower(); seen.add(k); raw[k] = clean(fm.group(2))
        pick = lambda *ks: next((raw[k] for k in ks if raw.get(k)), "")
        rec = {"hc": names(pick("head_coach", "coach")), "oc": names(pick("off_coach", "offensive_coordinator", "oc")),
               "dc": names(pick("def_coach", "defensive_coordinator", "dc")), "raw": raw}
        out[f"{y}|{tm}"] = rec
        print(f"{y} {tm}: HC {rec['hc']} | OC {rec['oc']} | DC {rec['dc']}{'' if wt else '  (no page)'}", flush=True)
print("infobox fields seen:", sorted(seen))
miss = [k for k, v in out.items() if not v["oc"] or not v["dc"]]
print(f"{len(out)} team-seasons, missing OC or DC: {len(miss)}", miss[:40])
json.dump(out, open("bt/nfl/coaches.json", "w"), indent=0, ensure_ascii=False)
