#!/usr/bin/env python3
"""Pregame record of Hashmark's projections (Engine 8): bt/proj_log/<season>-<week>.json.gz, standard library only.

Before each week's games, stores Hashmark's projection for every QB/RB/WR/TE with a Sleeper projection >= 1, using
scripts/proj_panel.py's formula (PJC, questionable multiplier and props share read from index.html) on the data available
at that moment: Sleeper's current projection, season-to-date Sleeper stats (PPG / last 3, weeks before this one only),
ffopportunity expected points and nflverse defense-vs-position (weeks before this one only), the current line from
data/sched.json, props from data/odds.json, and Sleeper's injury status. Runs in GitHub Actions (Sleeper is reachable there).

Freezing: per game. A game's players are (re)written at most once per US-Eastern day, plus one last update in the 7 hours
before its kickoff; once a game has kicked off its players are never touched again (a Thursday game freezes Thursday's
players only). Graded by scripts/rpt_snapshot.py once results exist.

File (numbers only): {"v":1,"s":season,"w":week,"g":{"AWY@HOM":[kickoff UTC, snapshot UTC]},
  "src":{"AWY@HOM":{"st":last stats week,"xfp":last xfp week,"dvp":last dvp week}},
  "p":{sleeper_id:[hashmark, sleeper base, flags, "AWY@HOM"]}}   flags: 1 questionable, 2 props used, 4 doubtful, 8 out/IR.

Test without Sleeper (replay an archived week as if it were "now", before its first kickoff):
  python3 scripts/snapshot_proj.py --test 2026 9 [--out DIR]
"""
import csv, gzip, io, json, os, re, sys, time, collections, statistics as st, urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proj_panel as PP

API = "https://api.sleeper.app/v1"
OUTDIR = os.environ.get("HM_PROJ_LOG", "bt/proj_log")
MINB = 1.0                # Sleeper projection floor
LAST_CALL_H = 7           # one more update allowed within this many hours of kickoff
FIX = {"LA": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR", "WSH": "WAS"}
OUTRX = re.compile(r"^(out|ir|pup|sus|na|dnr|cov|inactive)", re.I)


def get(u, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "hashmark-snapshot"}), timeout=90) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print("  retry", u, e); time.sleep(2 + 3 * k)
    return None


# ---------- time: schedule times are US Eastern ----------
def _us_dst(dt):   # naive local Eastern datetime -> DST? (2nd Sun Mar 2:00 .. 1st Sun Nov 2:00)
    y = dt.year
    m = datetime(y, 3, 8); start = m + timedelta(days=(6 - m.weekday()) % 7, hours=2)
    n = datetime(y, 11, 1); end = n + timedelta(days=(6 - n.weekday()) % 7, hours=2)
    return start <= dt < end

def et_to_utc(day, hhmm):
    try:
        loc = datetime.strptime(f"{day} {hhmm or '13:00'}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    try:
        from zoneinfo import ZoneInfo
        return loc.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
    except Exception:
        return (loc + timedelta(hours=4 if _us_dst(loc) else 5)).replace(tzinfo=timezone.utc)

def et_date(t):
    return (t - timedelta(hours=4 if _us_dst(t.replace(tzinfo=None) - timedelta(hours=5)) else 5)).date().isoformat()

iso = lambda t: t.strftime("%Y-%m-%dT%H:%MZ")
parse = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


# ---------- schedule: {game key: {wk, a, h, kick, sp, tot}} ----------
def schedule(season=None):
    G = {}
    if season is None and os.path.exists("data/sched.json"):
        s = json.load(open("data/sched.json")); season = int(s["season"])
        for g in s["games"]:
            a, h = FIX.get(g["a"], g["a"]), FIX.get(g["h"], g["h"])
            G[f"{a}@{h}"] = dict(wk=int(g["wk"]), a=a, h=h, kick=et_to_utc(g.get("day"), g.get("time")), sp=g.get("sp"), tot=g.get("tot"))
        return season, G
    for r in csv.DictReader(gzip.open("bt/nfl/schedules.csv.gz", "rt")):
        if r["game_type"] != "REG" or (season and int(r["season"]) != season): continue
        a, h = FIX.get(r["away_team"], r["away_team"]), FIX.get(r["home_team"], r["home_team"])
        num = lambda x: float(x) if x not in ("", "NA", None) else None
        G[f"{a}@{h}"] = dict(wk=int(r["week"]), a=a, h=h, kick=et_to_utc(r["gameday"], r["gametime"]), sp=num(r["spread_line"]), tot=num(r["total_line"]))
    return season, G


# ---------- season-to-date inputs, strictly from weeks before `week` ----------
def history(season, week, STw):
    """STw: {week: {sid: stats}} (Sleeper stat lines). Returns log, xfp, dvp_rank(opp, pos) and the last week of each source."""
    ids = {}; g2s = {}
    for r in csv.DictReader(open(PP._get("ids.csv", PP.IDS), encoding="utf-8")):
        s = str(r.get("sleeper_id") or "").split(".")[0]
        if s in ("", "NA"): continue
        ids[s] = r
        if r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
    log = collections.defaultdict(list); xfp = {}; allowed = collections.defaultdict(float); dgames = collections.defaultdict(set)
    tm_last = {}; src = {"st": 0, "xfp": 0, "dvp": 0}
    try:
        f = PP._get(f"pw_{season}.csv", PP.NV + f"stats_player/stats_player_week_{season}.csv")
        for r in csv.DictReader(open(f, encoding="utf-8")):
            if r.get("season_type") != "REG": continue
            w = int(r["week"])
            if w >= week: continue
            s = g2s.get(r["player_id"])
            if s: tm_last[s] = (w, FIX.get(r["team"], r["team"]))
            if r.get("position") in ("QB", "RB", "WR", "TE"):
                o = FIX.get(r["opponent_team"], r["opponent_team"])
                allowed[(o, r["position"], w)] += float(r.get("fantasy_points_ppr") or 0); dgames[o].add(w)
                src["dvp"] = max(src["dvp"], w)
    except Exception as e:
        print("  no nflverse weekly stats:", e)
    try:
        f = PP._get(f"ep_{season}.csv", PP.FF + f"ep_weekly_{season}.csv")
        for r in csv.DictReader(open(f, encoding="utf-8")):
            s = g2s.get(r.get("player_id"))
            try: w = int(float(r["week"]))
            except (ValueError, KeyError): continue
            if not s or w >= week: continue
            try: xfp[(w, s)] = float(r["total_fantasy_points_exp"] or 0); src["xfp"] = max(src["xfp"], w)
            except (ValueError, KeyError): pass
    except Exception as e:
        print("  no ffopportunity:", e)
    for w in sorted(STw):
        if w >= week: continue
        for pid, stt in STw[w].items():
            if stt.get("gp"): log[pid].append((w, stt.get("pts_ppr") or 0, xfp.get((w, pid)))); src["st"] = max(src["st"], w)
    DV = {}
    def dvp_rank(opp, pos):   # proj_panel.dvp_rank: needs every defense to have >= 2 games before this week
        k = (opp, pos)
        if k in DV: return DV[k]
        per = {}
        for t, ws in dgames.items():
            if len(ws) < 2: DV[k] = None; return None
            per[t] = sum(allowed.get((t, pos, x), 0) for x in ws) / len(ws)
        DV[k] = (sorted(per, key=lambda t: -per[t]).index(opp) + 1) if opp in per else None
        return DV[k]
    return dict(ids=ids, g2s=g2s, log=log, dvp=dvp_rank, tm_last=tm_last, src=src)


def project(pos, base, L, rk, imp, quest, mk, C, PW, QM):
    """proj_panel.build's per-row formula."""
    ppg = st.mean(x[1] for x in L) if len(L) >= 2 else None; l3 = st.mean(x[1] for x in L[-3:]) if len(L) >= 3 else None
    xs_ = [x[2] for x in L if x[2] is not None]; xs = st.mean(xs_) if len(xs_) >= 2 else None; x3 = st.mean(xs_[-3:]) if len(xs_) >= 3 else None
    hm = PP.proj(C[pos], base, ppg, l3, xs, x3, rk, imp) * (QM if quest else 1)
    if mk is not None: pw = PW.get(pos, .2); hm = hm * (1 - pw) + mk * pw
    return hm


def build_rows(season, week, games, players, H):
    """players: {sid: dict(pos, base, team, quest, doubt, out, mk)}; games: this week's {key: g}. -> {sid: [hm, base, flags, key]}"""
    C, PW = PP.load_app(); QM = PP.QMULT
    side = {}
    for k, g in games.items():
        side[g["a"]] = (k, g["h"], g["tot"] / 2 - g["sp"] / 2 if g["sp"] is not None and g["tot"] is not None else None)
        side[g["h"]] = (k, g["a"], g["tot"] / 2 + g["sp"] / 2 if g["sp"] is not None and g["tot"] is not None else None)
    out = {}
    for sid in sorted(players):
        p = players[sid]
        if p["pos"] not in C or p["base"] < MINB or p["team"] not in side: continue
        k, opp, imp = side[p["team"]]
        hm = project(p["pos"], p["base"], H["log"].get(sid, []), H["dvp"](opp, p["pos"]), imp, p["quest"], p["mk"], C, PW, QM)
        fl = (1 if p["quest"] else 0) | (2 if p["mk"] is not None else 0) | (4 if p.get("doubt") else 0) | (8 if p.get("out") else 0)
        out[sid] = [round(hm, 2), round(p["base"], 2), fl, k]
    return out


# ---------- freezing + writing ----------
def merge_write(season, week, games, rows, now, src, outdir=OUTDIR):
    """Re-snapshot only games that have not kicked off and were not already snapshotted today (ET), except one last
    update within LAST_CALL_H hours of kickoff. Returns the list of games written."""
    os.makedirs(outdir, exist_ok=True); fn = os.path.join(outdir, f"{season}-{week}.json.gz")
    old = json.load(gzip.open(fn, "rt")) if os.path.exists(fn) else {"v": 1, "s": season, "w": week, "g": {}, "src": {}, "p": {}}
    upd = []
    for k, g in sorted(games.items()):
        if g["kick"] is None or now >= g["kick"]: continue            # kicked off: frozen for good
        prev = old["g"].get(k)
        if prev:
            at = parse(prev[1]); left = (g["kick"] - now).total_seconds() / 3600
            last_call = left <= LAST_CALL_H and (g["kick"] - at).total_seconds() / 3600 > LAST_CALL_H
            if et_date(at) == et_date(now) and not last_call: continue
        upd.append(k)
    if not upd: return []
    U = set(upd)
    p = {sid: v for sid, v in old["p"].items() if v[3] not in U and not (sid in rows and rows[sid][3] in U)}
    for sid, v in rows.items():
        if v[3] in U: p[sid] = v
    for k in upd:
        old["g"][k] = [iso(games[k]["kick"]), iso(now)]; old["src"][k] = src
    old["p"] = dict(sorted(p.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0))
    raw = json.dumps(old, separators=(",", ":"), sort_keys=True).encode()
    with open(fn, "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as z: z.write(raw)
    return upd


# ---------- live run (GitHub Actions) ----------
def live():
    now = datetime.now(timezone.utc) if not os.environ.get("SNAP_NOW") else parse(os.environ["SNAP_NOW"])
    season, G = schedule()
    up = [g for g in G.values() if g["kick"] and g["kick"] > now]
    if not up: print("no upcoming games"); return
    week = min(g["wk"] for g in up)
    games = {k: g for k, g in G.items() if g["wk"] == week}
    if all(g["kick"] <= now for g in games.values()): print("week", week, "frozen"); return
    SPj = get(f"{API}/projections/nfl/regular/{season}/{week}")
    PL = get(f"{API}/players/nfl")
    if not SPj or not PL: print("Sleeper unavailable; nothing written"); return
    rows_ = SPj if isinstance(SPj, list) else [dict(player_id=k, stats=v) for k, v in SPj.items()]
    # season-to-date Sleeper stat lines: archive, plus any finished week the archive lacks
    STw = {}
    if os.path.exists("bt/sleeper_stats.json.gz"):
        for k, v in json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"].items():
            y, w = map(int, k.split("-"))
            if y == season and w < week: STw[w] = v
    for w in range(1, week):
        if w in STw and w < week - 1: continue
        j = get(f"{API}/stats/nfl/regular/{season}/{w}")
        if j:
            rr = j if isinstance(j, list) else [dict(player_id=k, stats=v) for k, v in j.items()]
            STw[w] = {str(r.get("player_id")): (r.get("stats") or r) for r in rr if (r.get("stats") or r).get("gp")}
    H = history(season, week, STw)
    props = {}; O = json.load(open("data/odds.json")) if os.path.exists("data/odds.json") else {}
    try:
        if O.get("props") and now - datetime.strptime(O["props_asof"][:16], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc) < timedelta(days=8):
            for sid, pr in O["props"].items():
                props[sid] = PP.props_pts({"recyd": pr.get("rec"), "rushyd": pr.get("rush"), "passyd": pr.get("pass"), "td": pr.get("atd")}, 1)
    except Exception as e:
        print("  props skipped:", e)
    players = {}
    for r in rows_:
        sid = str(r.get("player_id") or ""); stt = r.get("stats") or r; meta = PL.get(sid) or {}
        pos = meta.get("position") or (r.get("player") or {}).get("position")
        if not sid or pos not in ("QB", "RB", "WR", "TE"): continue
        inj = str(meta.get("injury_status") or "")
        team = FIX.get(meta.get("team") or "", meta.get("team"))
        players[sid] = dict(pos=pos, base=float(stt.get("pts_ppr") or 0), team=team, quest=bool(re.search("quest", inj, re.I)),
                            doubt=bool(re.search("doubt", inj, re.I)), out=bool(OUTRX.match(inj)), mk=props.get(sid))
    rows = build_rows(season, week, games, players, H)
    done = merge_write(season, week, games, rows, now, H["src"])
    print(f"{season} week {week}: {len(rows)} players projected; games written: {', '.join(done) or 'none (frozen or already today)'}; inputs to week {H['src']}")


# ---------- test: replay an archived week as if before its first kickoff ----------
def test(season, week, outdir):
    _, G = schedule(season); games = {k: g for k, g in G.items() if g["wk"] == week}
    now = min(g["kick"] for g in games.values()) - timedelta(minutes=30)
    SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"][f"{season}-{week}"]
    STa = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
    STw = {int(k.split("-")[1]): v for k, v in STa.items() if int(k.split("-")[0]) == season and int(k.split("-")[1]) < week}
    H = history(season, week, STw)
    # team this week: the week's nflverse row (stands in for Sleeper's team field), else last team seen
    team = dict((s, t) for s, (w, t) in H["tm_last"].items())
    f = PP._get(f"pw_{season}.csv", "")
    for r in csv.DictReader(open(f, encoding="utf-8")):
        if r.get("season_type") == "REG" and int(r["week"]) == week and r["player_id"] in H["g2s"]: team[H["g2s"][r["player_id"]]] = r["team"]
    q = set()
    for r in csv.DictReader(gzip.open(f"bt/nfl/injuries/{season}.csv.gz", "rt")):
        if r.get("report_status") == "Questionable" and int(r["week"]) == week and r["gsis_id"] in H["g2s"]: q.add(H["g2s"][r["gsis_id"]])
    panel = {r["pid"]: r for r in PP.build([season], feats=True) if r["w"] == week}   # props input only (+ comparison)
    players = {}
    for sid, pr in SP.items():
        pos = (H["ids"].get(sid) or {}).get("position")
        if pos not in ("QB", "RB", "WR", "TE"): continue
        players[sid] = dict(pos=pos, base=pr.get("pts_ppr") or 0, team=FIX.get(team.get(sid), team.get(sid)), quest=sid in q, mk=(panel.get(sid) or {}).get("mk"))
    rows = build_rows(season, week, games, players, H)
    if os.path.exists(os.path.join(outdir, f"{season}-{week}.json.gz")): os.remove(os.path.join(outdir, f"{season}-{week}.json.gz"))
    merge_write(season, week, games, rows, now, H["src"], outdir)
    # a second run the same day must not rewrite; a run after kickoff must not either
    assert merge_write(season, week, games, rows, now + timedelta(minutes=5), H["src"], outdir) == []
    assert merge_write(season, week, games, {}, now + timedelta(days=6), H["src"], outdir) == []
    both = [s for s in rows if s in panel]
    d = [abs(rows[s][0] - panel[s]["hm"]) for s in both]
    big = sorted(both, key=lambda s: -abs(rows[s][0] - panel[s]["hm"]))[:5]
    print(f"{season} wk {week}: snapshot {len(rows)} (Sleeper >= {MINB}), panel graded {len(panel)}, both {len(both)}; "
          f"|snapshot - panel| mean {st.mean(d):.4f} max {max(d):.3f}; identical (<.01) {sum(1 for x in d if x < .01)}/{len(d)}; inputs to week {H['src']}")
    for s in big:
        if abs(rows[s][0] - panel[s]["hm"]) >= .01: print("   ", s, rows[s], round(panel[s]["hm"], 2), "team", players[s]["team"])
    return rows, panel


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--test":
        od = a[a.index("--out") + 1] if "--out" in a else ".build/proj_log_test"
        test(int(a[1]), int(a[2]), od)
    else:
        live()
