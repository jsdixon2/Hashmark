#!/usr/bin/env python3
"""Build data/cfb.json: college (devy) scouting data for QB/RB/WR/TE.

Free sources:
  cfbfastR-data (sportsdataverse, GitHub)  play-level player stats and rosters, updated daily (data from CollegeFootballData)
  nflverse                                draft picks and combine results (to tie prospects to NFL outcomes and teams)
  nflverse games                          NFL standings, used for the projected draft order
  Google News RSS                         recent headlines for the top prospects
  CollegeFootballData API (optional)      recruiting stars/ratings and transfer portal, if CFBD_API_KEY is set
Every number is computed here from play-level data; scores, projected rounds and landing spots are Hashmark model estimates.
"""
import csv, gzip, html, io, json, math, os, re, sys, time, urllib.parse, urllib.request
from collections import Counter, defaultdict
import xml.etree.ElementTree as ET

CF = "https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/"
NV = "https://github.com/nflverse/nflverse-data/releases/download/"
GAMES = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
FBS = {"SEC", "Big Ten", "Big 12", "ACC", "Pac-12", "American Athletic", "Mountain West", "Sun Belt", "Mid-American", "Conference USA", "FBS Independents"}
P5 = {"SEC", "Big Ten", "Big 12", "ACC"}
POS = {"QB", "RB", "WR", "TE"}
KEY = os.environ.get("CFBD_API_KEY", "").strip()


def get(url, tries=3, headers=None):
    for k in range(tries):
        try:
            h = {"User-Agent": "hashmark-build"}
            h.update(headers or {})
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=180) as r:
                b = r.read()
            return gzip.decompress(b).decode("utf-8", "replace") if url.endswith(".gz") else b.decode("utf-8", "replace")
        except Exception as e:
            if k == tries - 1:
                print("  skip", url[:120], e)
                return None
            time.sleep(3)


def rows(url):
    t = get(url)
    return list(csv.DictReader(io.StringIO(t))) if t else []


def f(x):
    try:
        v = float(x)
        return v if v == v else None
    except Exception:
        return None


def nid(x):
    return None if x in (None, "", "NA") else x


def norm(n):
    n = (n or "").lower().replace(".", "").replace("'", "").replace("’", "")
    n = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n.strip())
    return re.sub(r"[^a-z ]", "", n).strip()


def r2(x, n=3):
    return None if x is None else round(x, n)


def season_now():
    t = time.gmtime()
    return t.tm_year if t.tm_mon >= 8 else t.tm_year - 1


def parse_season(y):
    """Aggregate play-level rows into per-player and per-team season totals."""
    P = defaultdict(lambda: defaultdict(float))
    G = defaultdict(set)
    TM = defaultdict(Counter)
    T = defaultdict(lambda: defaultdict(float))
    conf = {}
    txt = get(CF + f"player_stats/csv/player_stats_{y}.csv")
    if not txt:
        return None
    for r in csv.DictReader(io.StringIO(txt)):
        team = r.get("team"); conf[team] = r.get("conference")
        gid = r.get("game_id"); ytg = f(r.get("yards_to_goal")) or 99; rz = ytg <= 20
        rec, tgt, cmp_, inc, itp, rus, td, sk = (nid(r.get(k)) for k in ("reception_player_id", "target_player_id", "completion_player_id", "incompletion_player_id",
                                                                       "interception_thrown_player_id", "rush_player_id", "touchdown_player_id", "sack_taken_player_id"))
        tt = T[team]
        if rec or tgt or cmp_ or inc or itp:
            tt["pa"] += 1
        if rec:
            yd = f(r.get("reception_yds")) or 0; p = P[rec]
            p["tgt"] += 1; p["rec"] += 1; p["ryd"] += yd; p["r20"] += 1 if yd >= 20 else 0; p["rz"] += 1 if rz else 0
            tt["tgt"] += 1; tt["ryd"] += yd; G[rec].add(gid); TM[rec][team] += 1
            if td:
                p["rtd"] += 1; tt["rtd"] += 1
                if cmp_: P[cmp_]["ptd"] += 1
        if tgt and not rec:
            P[tgt]["tgt"] += 1; P[tgt]["rz"] += 1 if rz else 0; tt["tgt"] += 1; G[tgt].add(gid); TM[tgt][team] += 1
        if cmp_:
            p = P[cmp_]; p["cmp"] += 1; p["att"] += 1; p["pyd"] += f(r.get("completion_yds")) or 0; G[cmp_].add(gid); TM[cmp_][team] += 1
            if td == cmp_ and not rec:
                p["ptd"] += 1
        if inc:
            P[inc]["att"] += 1; G[inc].add(gid); TM[inc][team] += 1
        if itp:
            P[itp]["att"] += 1; P[itp]["int"] += 1; G[itp].add(gid); TM[itp][team] += 1
        if sk:
            P[sk]["sk"] += 1
        if rus:
            yd = f(r.get("rush_yds")) or 0; p = P[rus]
            p["car"] += 1; p["ruyd"] += yd; p["r15"] += 1 if yd >= 15 else 0; p["rz"] += 1 if rz else 0
            tt["car"] += 1; tt["ruyd"] += yd; G[rus].add(gid); TM[rus][team] += 1
            if td == rus:
                p["rutd"] += 1; tt["rutd"] += 1
        tt["g_" + str(gid)] = 1
    for team, tt in T.items():
        tt["games"] = sum(1 for k in tt if k.startswith("g_"))
    return P, G, TM, T, conf


def season_line(pid, y, S, ro):
    P, G, TM, T, conf = S
    p = P.get(pid)
    if not p:
        return None
    if not TM[pid]:
        return None
    team = TM[pid].most_common(1)[0][0]
    t = T[team]; g = len(G[pid])
    sh = lambda a, b: (a / b) if b else None
    ln = {"y": y, "team": team, "conf": conf.get(team), "g": g, "cls": f(ro.get("year")),
          "tgt": int(p["tgt"]), "rec": int(p["rec"]), "ryd": int(p["ryd"]), "rtd": int(p["rtd"]),
          "car": int(p["car"]), "ruyd": int(p["ruyd"]), "rutd": int(p["rutd"]),
          "att": int(p["att"]), "cmp": int(p["cmp"]), "pyd": int(p["pyd"]), "ptd": int(p["ptd"]), "int": int(p["int"]), "sk": int(p["sk"]),
          "ts": r2(sh(p["tgt"], t["tgt"])), "ys": r2(sh(p["ryd"], t["ryd"])), "tds": r2(sh(p["rtd"], t["rtd"])),
          "yptpa": r2(sh(p["ryd"], t["pa"]), 2), "rs": r2(sh(p["car"], t["car"])),
          "scrim": r2(sh(p["ryd"] + p["ruyd"], t["ryd"] + t["ruyd"])), "x20": int(p["r20"]), "x15": int(p["r15"]), "rz": int(p["rz"])}
    ys, tds = ln["ys"] or 0, ln["tds"] or 0
    ln["dom"] = r2((ys + tds) / 2) if ln["tgt"] else None
    return {k: v for k, v in ln.items() if v not in (None, 0) or k in ("y", "team", "g")}


def pct_rank(vals, v):
    if v is None or not vals:
        return None
    lo = sum(1 for x in vals if x < v); eq = sum(1 for x in vals if x == v)
    return (lo + eq / 2) / len(vals)


def main():
    cur = int(sys.argv[1]) if len(sys.argv) > 1 else season_now()
    yrs = list(range(cur - 4, cur + 1))
    seasons, rosters = {}, {}
    for y in yrs:
        S = parse_season(y)
        if S:
            seasons[y] = S
        rosters[y] = {r["athlete_id"]: r for r in rows(CF + f"rosters/csv/cfb_rosters_{y}.csv")}
        print(f"  {y}: {len(S[0]) if S else 0} players with plays, {len(rosters[y])} on rosters")
    if cur not in seasons:
        cur -= 1
    # every skill-position player on an FBS roster (current or last season), plus anyone with real FBS production
    # roster positions are sometimes '?' / 'NA' / 'ATH': fall back to the player's position in any other roster year
    # of the window (backtest/e23 found this dropped real prospects, e.g. older rosters listing Chubb and Michel as '?')
    UNK = {"?", "NA", "", "ATH", None}
    PS = {}
    for y in sorted(rosters, reverse=True):
        for aid, r in rosters[y].items():
            if r.get("position") in POS:
                PS.setdefault(aid, r["position"])
    ids = set()
    for y in (cur, cur - 1):
        for aid, r in rosters.get(y, {}).items():
            if r.get("position") in POS or (r.get("position") in UNK and aid in PS):
                ids.add(aid)
    out = {}
    for aid in ids:
        ro = rosters.get(cur, {}).get(aid) or rosters.get(cur - 1, {}).get(aid)
        if not ro:
            continue
        lines, teams = [], []
        for y in yrs:
            if y in seasons:
                rr = rosters.get(y, {}).get(aid, {})
                ln = season_line(aid, y, seasons[y], rr)
                if ln:
                    lines.append(ln)
            rr = rosters.get(y, {}).get(aid)
            if rr and (not teams or teams[-1][1] != rr.get("team")):
                teams.append([y, rr.get("team")])
        if not lines:
            continue
        last = lines[-1]
        if last.get("conf") not in FBS and not any(l.get("conf") in FBS for l in lines):
            continue
        pos = ro.get("position") if ro.get("position") in POS else PS.get(aid)
        if pos not in POS:
            continue
        vol = sum(l.get("tgt", 0) + l.get("car", 0) + l.get("att", 0) for l in lines)
        if vol < 25:
            continue
        cur_ro = rosters.get(cur, {}).get(aid)
        out[aid] = {"id": aid, "n": f'{ro.get("first_name","")} {ro.get("last_name","")}'.strip(), "pos": pos, "school": (cur_ro or ro).get("team"),
                    "conf": last.get("conf"), "cls": f((cur_ro or {}).get("year")), "active": bool(cur_ro), "ht": f(ro.get("height")), "wt": f(ro.get("weight")),
                    "home": ", ".join(x for x in (ro.get("home_city"), ro.get("home_state")) if x and x != "NA") or None,
                    "rid": [x for x in re.split(r"[;,\s]+", ro.get("recruit_ids") or "") if x and x != "NA"],
                    "seasons": lines, "teams": teams}
    print(f"  {len(out)} FBS skill players with college production")
    # metrics and breakout year
    CF_ = lambda l: 1.0 if l.get("conf") in P5 else .88 if l.get("conf") in FBS else .65
    for p in out.values():
        L = p["seasons"]; pos = p["pos"]
        Lq = [l for l in L if l.get("g", 0) >= 4] or L
        def best(k):  # blend of best season and latest season, discounted for lower levels of play
            vals = [(l.get(k) or 0) * CF_(l) for l in Lq]
            return (.55 * max(vals) + .45 * vals[-1]) if vals else 0
        p["m"] = m = {}
        if pos in ("WR", "TE"):
            m.update(dom=best("dom"), yptpa=best("yptpa"), ts=best("ts"), ypr=max(((l.get("ryd", 0) / l["rec"]) if l.get("rec") else 0) for l in L),
                     x20=max((l.get("x20", 0) / max(1, l.get("g", 1))) for l in L))
            thr = .2 if pos == "WR" else .15
            bo = next((l for l in L if (l.get("dom") or 0) >= thr and l.get("g", 0) >= 6 and l.get("conf") in FBS), None)
        elif pos == "RB":
            m.update(scrim=best("scrim"), rs=best("rs"), ypc=max(((l.get("ruyd", 0) / l["car"]) if l.get("car", 0) >= 50 else 0) for l in L),
                     ts=best("ts"), x15=max((l.get("x15", 0) / max(1, l.get("g", 1))) for l in L), rtd=max(l.get("rutd", 0) for l in L))
            bo = next((l for l in L if (l.get("scrim") or 0) >= .25 and l.get("g", 0) >= 6 and l.get("conf") in FBS), None)
        else:
            def ypa(l): return (l.get("pyd", 0) / l["att"]) if l.get("att", 0) >= 100 else 0
            m.update(ypa=max(ypa(l) for l in L), cmp=max(((l.get("cmp", 0) / l["att"]) if l.get("att", 0) >= 100 else 0) for l in L),
                     tdint=max(((l.get("ptd", 0) + 1) / (l.get("int", 0) + 1)) if l.get("att", 0) >= 100 else 0 for l in L),
                     rush=max(l.get("ruyd", 0) / max(1, l.get("g", 1)) for l in L), att=sum(l.get("att", 0) for l in L))
            bo = next((l for l in L if l.get("att", 0) >= 200 and ypa(l) >= 8), None)
        p["bo"] = {"y": bo["y"], "cls": max(1, (p.get("cls") or len(L)) - (cur - bo["y"]))} if bo else None
        # trend: latest vs previous season on the key share metric
        key = {"WR": "dom", "TE": "dom", "RB": "scrim", "QB": "pyd"}[pos]
        floor = {"dom": .08, "scrim": .08, "pyd": 800}[key]
        if len(L) >= 2 and L[-1].get(key) is not None and (L[-2].get(key) or 0) >= floor and L[-2].get("g", 0) >= 5:
            p["trend"] = r2(min(3, L[-1].get(key, 0) / L[-2][key] - 1), 2)
    # devy score: weighted percentiles within position (FBS, meaningful volume)
    W = {"WR": [("dom", .3), ("yptpa", .25), ("ts", .15), ("x20", .1), ("bo", .2)], "TE": [("dom", .3), ("yptpa", .25), ("ts", .15), ("x20", .1), ("bo", .2)],
         "RB": [("scrim", .3), ("ts", .15), ("ypc", .15), ("x15", .15), ("bo", .15), ("rtd", .1)], "QB": [("ypa", .3), ("tdint", .15), ("cmp", .15), ("rush", .15), ("att", .1), ("bo", .15)]}
    for pos, ws in W.items():
        group = [p for p in out.values() if p["pos"] == pos]
        dist = {k: sorted(p["m"].get(k, 0) for p in group) for k, _ in ws if k != "bo"}
        for p in group:
            sc = 0
            for k, w in ws:
                if k == "bo":
                    c = (p["bo"] or {}).get("cls")
                    v = 1.0 if c and c <= 1 else .8 if c == 2 else .55 if c == 3 else .3 if p["bo"] else 0
                else:
                    v = pct_rank(dist[k], p["m"].get(k, 0)) or 0
                sc += v * w
            conf = p.get("conf"); sc *= 1.0 if conf in P5 else .9 if conf in FBS else .8
            if pos in ("WR", "RB", "TE") and p.get("wt"):
                ideal = {"WR": 200, "RB": 210, "TE": 245}[pos]
                sc *= 1 - min(.08, abs(p["wt"] - ideal) / 400)
            p["score"] = round(sc * 100)
    # CollegeFootballData (optional key, free tier 1,000 calls a month): cached so twice-daily runs stay ~150 calls a month
    if KEY:
        H = {"Authorization": "Bearer " + KEY, "Accept": "application/json"}
        cpath = "data/cfbd_cache.json"
        try:
            cache = json.load(open(cpath))
        except Exception:
            cache = {}
        now = time.time()
        SK = {"QB", "RB", "WR", "TE", "ATH", "APB", "DUAL", "PRO"}

        def cached(name, max_h, fetch):
            c = cache.get(name)
            if c and now - c.get("t", 0) < max_h * 3600:
                return c["d"]
            d = fetch()
            if d is not None:
                cache[name] = {"t": now, "d": d}
                return d
            return c["d"] if c else None

        def jl(url):
            t = get(url, headers=H)
            try:
                return json.loads(t) if t else None
            except Exception:
                return None

        def f_rec():
            rec = {}
            for y in range(cur - 7, cur + 1):   # e23: older seniors / 5th-years need HS classes back to cur-7
                xs = jl(f"https://api.collegefootballdata.com/recruiting/players?year={y}&classification=HighSchool")
                if xs is None:
                    return None
                for x in xs:
                    if (x.get("position") or "") in SK:
                        rec[str(x.get("id"))] = {"stars": x.get("stars"), "rating": x.get("rating"), "rank": x.get("ranking"), "cls": y, "from": x.get("committedTo"), "aid": str(x.get("athleteId") or "")}
            return rec

        def f_portal():
            pt = {}
            for y in (cur, cur + 1):
                for x in jl(f"https://api.collegefootballdata.com/player/portal?year={y}") or []:
                    if (x.get("position") or "") in SK:
                        pt[norm(f'{x.get("firstName","")} {x.get("lastName","")}')] = {"from": x.get("origin"), "to": x.get("destination"), "y": y, "stars": x.get("stars")}
            return pt

        def f_usage(yr=None):
            xs = jl(f"https://api.collegefootballdata.com/player/usage?year={yr or cur}&excludeGarbageTime=true")
            if xs is None:
                return None
            return {str(x["id"]): {k: round(v, 3) for k, v in (x.get("usage") or {}).items() if isinstance(v, (int, float))} for x in xs if x.get("position") in POS and x.get("id")}

        def f_ppa(yr=None):
            xs = jl(f"https://api.collegefootballdata.com/ppa/players/season?year={yr or cur}&excludeGarbageTime=true")
            if xs is None:
                return None
            return {str(x["id"]): {"avg": {k: round(v, 3) for k, v in (x.get("averagePPA") or {}).items() if isinstance(v, (int, float))},
                                   "tot": round((x.get("totalPPA") or {}).get("all") or 0, 1)} for x in xs if x.get("position") in POS and x.get("id")}

        rec = cached("rec", 24 * 7, f_rec) or {}
        portal = cached("portal", 24, f_portal) or {}
        usage = cached("usage", 20, f_usage) or {}
        ppa = cached("ppa", 20, f_ppa) or {}
        # x20 / v153 devy odds: last season's usage + PPA too, used while this season is short (< 6 games)
        usage1 = cached("usage1", 24 * 7, lambda: f_usage(cur - 1)) or {}
        ppa1 = cached("ppa1", 24 * 7, lambda: f_ppa(cur - 1)) or {}
        recA = {v["aid"]: v for v in rec.values() if v.get("aid")}
        for k, p in out.items():
            r0 = recA.get(str(k))
            if not r0:
                for r_ in p["rid"]:
                    if r_ in rec:
                        r0 = rec[r_]; break
            if r0:
                p["rec"] = {kk: vv for kk, vv in r0.items() if kk != "aid"}
            if norm(p["n"]) in portal:
                p["portal"] = portal[norm(p["n"])]
            u = usage.get(str(k))
            if u:
                p["use"] = u
            q = ppa.get(str(k))
            if q:
                p["ppa"] = q
            u1, q1 = usage1.get(str(k)), ppa1.get(str(k))
            if u1 and q1:
                p["use1"] = {"overall": u1.get("overall")}; p["ppa1"] = {"avg": {"all": (q1.get("avg") or {}).get("all")}, "tot": q1.get("tot")}
        json.dump(cache, open(cpath, "w"), separators=(",", ":"))
        print(f"  CFBD: recruiting {sum(1 for p in out.values() if 'rec' in p)} matched; portal {sum(1 for p in out.values() if 'portal' in p)}; "
              f"usage {sum(1 for p in out.values() if 'use' in p)}; EPA {sum(1 for p in out.values() if 'ppa' in p)}")
    else:
        print("  CFBD_API_KEY not set; skipping recruiting, portal, usage and EPA")
    # NFL draft results: tie drafted prospects to their NFL team
    picks = rows(NV + "draft_picks/draft_picks.csv")
    byname = {}
    for r in picks:
        if int(r["season"]) >= cur - 4:
            byname[(norm(r.get("pfr_player_name")), (r.get("college") or "").lower())] = r
            byname.setdefault((norm(r.get("pfr_player_name")), ""), r)
    for p in out.values():
        r = byname.get((norm(p["n"]), (p["school"] or "").lower())) or byname.get((norm(p["n"]), ""))
        if r and int(r["season"]) >= p["seasons"][-1]["y"]:
            p["drafted"] = {"y": int(r["season"]), "r": int(r["round"]), "p": int(r["pick"]), "t": r.get("team"), "gsis": r.get("gsis_id")}
    # draft class + projected round and landing spot (model)
    nfl = rows(GAMES); rec_ = defaultdict(lambda: [0, 0])
    for g in nfl:
        if g.get("season") == str(cur) and g.get("game_type") == "REG" and g.get("result") not in ("", "NA"):
            res = f(g["result"])
            for tm, won in ((g["home_team"], res > 0), (g["away_team"], res < 0)):
                rec_[tm][0] += 1 if won else 0; rec_[tm][1] += 1
    order = sorted(rec_, key=lambda t: (rec_[t][0] / max(1, rec_[t][1]), t))
    for k in [k for k, p in out.items() if not p.get("drafted") and not p["active"] and p["seasons"][-1]["y"] < cur]:
        del out[k]  # left college without being drafted
    for p in out.values():
        c = p.get("cls") or 0
        last_y = p["seasons"][-1]["y"]
        p["dclass"] = (cur + 1) if (c >= 3 or not p["active"]) else cur + (4 - int(c))
    PV = {"QB": 1.0, "WR": .96, "RB": .86, "TE": .82}  # positional draft value
    for dc in sorted({p["dclass"] for p in out.values()}):
        grp = sorted((p for p in out.values() if p["dclass"] == dc and not p.get("drafted")), key=lambda p: -p["score"] * PV[p["pos"]])
        prank = Counter()
        for i, p in enumerate(grp):
            pick = int((i + 1) / .33)  # skill positions are about a third of all picks
            rnd = min(8, (pick - 1) // 32 + 1); prank[p["pos"]] += 1
            p["proj"] = {"rank": prank[p["pos"]], "pick": pick, "rd": rnd if rnd <= 7 else None}
            if dc == cur + 1 and pick <= 64 and order:
                p["proj"]["team"] = order[(pick - 1) % 32]
    # profile comps: drafted players with similar college profiles
    comps = [p for p in out.values() if p.get("drafted")]
    keys = {"WR": ["dom", "yptpa", "ts"], "TE": ["dom", "yptpa", "ts"], "RB": ["scrim", "ypc", "ts"], "QB": ["ypa", "cmp", "rush"]}
    for p in out.values():
        if p.get("drafted"):
            continue
        ks = keys[p["pos"]]; pool = [c for c in comps if c["pos"] == p["pos"]]
        def d(c):
            s_ = sum(((p["m"].get(k) or 0) - (c["m"].get(k) or 0)) ** 2 / max(1e-6, (p["m"].get(k) or .01) ** 2 + .0001) for k in ks)
            if p.get("wt") and c.get("wt"):
                s_ += ((p["wt"] - c["wt"]) / 25) ** 2
            return s_
        best = sorted(pool, key=d)[:3]
        if best:
            p["comps"] = [{"id": c["id"], "n": c["n"], "y": c["drafted"]["y"], "r": c["drafted"]["r"], "t": c["drafted"]["t"]} for c in best]
    # headlines for the top prospects (Google News RSS)
    top = sorted((p for p in out.values() if not p.get("drafted")), key=lambda p: -p["score"])[:45]
    for p in top:
        q = urllib.parse.quote(f'"{p["n"]}" {p["school"]} football')
        t = get(f"https://news.google.com/rss/search?q={q}+when:14d&hl=en-US&gl=US&ceid=US:en", tries=1)
        if not t:
            continue
        try:
            items = []
            for it in ET.fromstring(t).iter("item"):
                ti = html.unescape(it.findtext("title") or ""); src = ""
                mm = re.search(r"\s+-\s+([^-]+)$", ti)
                if mm:
                    src = mm.group(1).strip(); ti = ti[: mm.start()].strip()
                items.append({"t": ti, "src": src, "url": it.findtext("link"), "d": it.findtext("pubDate")})
                if len(items) >= 4:
                    break
            if items:
                p["news"] = items
        except Exception:
            pass
        time.sleep(.4)
    # keep the board focused: everyone drafted in the last two classes plus the top prospects by position
    keep = {}
    for pos, n in (("QB", 120), ("RB", 220), ("WR", 320), ("TE", 120)):
        for p in sorted((p for p in out.values() if p["pos"] == pos and not p.get("drafted")), key=lambda p: -p["score"])[:n]:
            keep[p["id"]] = p
    for dc in (cur + 2, cur + 3, cur + 4):
        for pos, n in (("QB", 25), ("RB", 40), ("WR", 60), ("TE", 25)):
            for p in sorted((p for p in out.values() if p["pos"] == pos and p["dclass"] == dc and not p.get("drafted")), key=lambda p: -p["score"])[:n]:
                keep[p["id"]] = p
    for p in out.values():
        if p.get("drafted") and p["drafted"]["y"] >= cur:
            keep[p["id"]] = p
    for p in keep.values():
        p.pop("rid", None)
    os.makedirs("data", exist_ok=True)
    with open("data/cfb.json", "w") as fh:
        json.dump({"asof": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "season": cur, "order": order, "recruiting": bool(KEY), "p": keep}, fh, separators=(",", ":"))
    print(f"{len(keep)} prospects; file {os.path.getsize('data/cfb.json')//1024} KB")


if __name__ == "__main__":
    main()
