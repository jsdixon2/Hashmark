"""Report card: rest-of-season points per week (key ros). Standard library only.
The app's rest-of-season estimate (rosPPG in index.html: .62 PPG + .38 Sleeper's projection for the week, depth/injury
cuts, xFP nudge, recent-absence cut; v114 blends 75% of a fitted model from backtest/e26_*, read here from ROS114) is
rebuilt for this season at weeks 4, 8 and 11 from what was known before that week's games, then graded on what players
scored from that week through week 17 (or the last finished week): points per team game, bye weeks out, missed games 0.
Benchmarks: season PPG, last-4 PPG, Sleeper's projection for the week carried forward; "naive" = the best of the three.
Not replayed: the news multiplier. Population: QB/RB/WR/TE with (2+ games and PPG >= 5) or a projection >= 5. PPR."""
import csv, gzip, io, json, os, re, statistics as st, collections, datetime

CHECK = (4, 8, 11)
def _nt(t): return {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}.get(t, t)
def _f(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def load_ros114(path="index.html"):
    s = open(path, encoding="utf-8").read(); m = re.search(r"const ROS114=\{A:([\d.]+),M:(\{.*?\]\})\};", s)
    if not m: return 0.0, {}
    return float(m.group(1)), json.loads(re.sub(r"([A-Z]{2}):", r'"\1":', m.group(2)))

def app_old(r):
    ppg, pj = r["ppg"], (None if r["bye"] else r["proj"])
    v = .62 * ppg + .38 * pj if ppg is not None and pj is not None else ppg * .94 if ppg is not None else pj if pj is not None else 0.0
    dc, inj = r["dc"], r["inj"] or ""
    if dc and r["pos"] != "QB" and dc > 1: v *= .92 if dc == 2 else .8
    if re.search(r"\bout\b|\bir\b|doubt", inj, re.I): v *= .8
    if r["ag"] >= 4 and r["xfp"] is not None and r["fp"] and r["fp"] >= 2 and v > 0:
        x = r["xfp"] * .65 + r["x3"] * .35 if r["ag"] >= 5 else r["xfp"]
        sc = max(.6, min(1.6, (ppg or r["fp"]) / r["fp"])); t = x * sc
        v *= 1 + max(-.2, min(.2, (t - v) / max(4, v))) * .35
    a = 1.0
    if r["pos"] == "QB" and dc and dc >= 2: a = .12 if dc == 2 else .04
    elif dc and dc >= 4 and r["pos"] != "QB": a = .5
    if (r["gp"] or r["ag"]) and r["w"] > 2 and not re.search(r"\bout\b|\bir\b|\bpup\b|\bsus|doubt", inj, re.I) and r["nrec"] >= 3:
        if r["prec"] == 0: a *= .25
        elif r["prec"] == 1: a *= .6
    return v * a

def fit(r, c):
    gp = r["gp"]; k = gp / (gp + 3)
    pg = r["ppg"] if r["ppg"] is not None else (r["proj"] or 0.0)
    pj = r["proj"] if (r["proj"] is not None and not r["bye"]) else pg
    l3 = r["l3"] if r["l3"] is not None else pg
    x = r["xfp"] if r["xfp"] is not None else pg; x3 = r["x3"] if r["x3"] is not None else x
    inj = r["inj"] or ""; out = 1 if re.search("out|doubt", inj, re.I) else 0; q = 1 if re.search("quest", inj, re.I) else 0
    dc = r["dc"] or 1; miss = 1 - r["prec"] / r["nrec"] if r["nrec"] else 0
    age = max(20, min(40, r["age"] if r["age"] is not None else 26)); pv = r["prev"]
    f = [pj, k * pg, k * l3, k * x, k * x3, (1 - k) * (pv if pv is not None else pg), 1 if pv is not None else 0, k, out, out * pj, q,
         pj if dc == 2 else 0, pj if dc >= 3 else 0, miss * pj, (age - 26) * pj / 10, r["w"] * pj / 10]
    return max(0.0, c[0] + sum(a * b for a, b in zip(c[1:], f)))

def build_rows(season, ST, SP, PP, checks=CHECK, root="."):
    J = lambda *p: os.path.join(root, *p)
    s2g, s2b, POS = {}, {}, {}
    for w in SP.values():
        for pid, s in w.items():
            if s.get("pos"): POS[pid] = s["pos"]
    for r in csv.DictReader(open(PP._get("ids.csv", PP.IDS), encoding="utf-8")):
        s = str(r.get("sleeper_id") or "").split(".")[0]
        if s in ("", "NA"): continue
        if r.get("gsis_id") not in ("", "NA", None): s2g[s] = r["gsis_id"]
        s2b[s] = r.get("birthdate")
        if s not in POS and r.get("position") in ("QB", "RB", "WR", "TE"): POS[s] = r["position"]
    TW = collections.defaultdict(set); KICK = {}
    for r in csv.DictReader(gzip.open(J("bt", "nfl", "schedules.csv.gz"), "rt")):
        if r["game_type"] != "REG" or int(r["season"]) != season: continue
        w = int(r["week"]); TW[w] |= {_nt(r["home_team"]), _nt(r["away_team"])}; KICK[w] = min(KICK.get(w, "9999"), r["gameday"])
    TEAM = collections.defaultdict(dict)
    for r in csv.DictReader(open(PP._get(f"pw_{season}.csv", PP.NV + f"stats_player/stats_player_week_{season}.csv"), encoding="utf-8")):
        if r.get("season_type") == "REG": TEAM[r["player_id"]][int(r["week"])] = _nt(r["team"])
    EP = collections.defaultdict(dict)
    try:
        for r in csv.DictReader(open(PP._get(f"ep_{season}.csv", PP.FF + f"ep_weekly_{season}.csv"), encoding="utf-8")):
            try: EP[r["player_id"]][int(float(r["week"]))] = (_f(r.get("total_fantasy_points")), _f(r.get("total_fantasy_points_exp")))
            except (KeyError, ValueError): pass
    except Exception: pass
    INJ = {}
    try:
        for r in csv.DictReader(gzip.open(J("bt", "nfl", "injuries", f"{season}.csv.gz"), "rt")):
            if r.get("game_type", "REG") == "REG" and r.get("report_status"): INJ[(r["gsis_id"], int(float(r["week"])))] = r["report_status"]
    except Exception: pass
    DC = {}
    try:
        rows = list(csv.DictReader(gzip.open(J("bt", "nfl", "depth", f"{season}.csv.gz"), "rt")))
        if rows and "dt" in rows[0]:
            by = collections.defaultdict(list)
            for r in rows:
                if r.get("position") in ("QB", "RB", "WR", "TE"): by[r["dt"]].append(r)
            dts = sorted(by)
            for w, k in KICK.items():
                prior = [d for d in dts if d[:10] < k]
                if not prior: continue
                for r in by[prior[-1]]:
                    try: DC[(r["gsis_id"], w)] = min(DC.get((r["gsis_id"], w), 9), int(float(r["depth"])))
                    except (TypeError, ValueError): pass
        else:
            for r in rows:
                if r.get("game_type") != "REG" or r.get("depth_position") not in ("QB", "RB", "WR", "TE") or not r.get("week"): continue
                try: DC[(r["gsis_id"], int(float(r["week"])))] = min(DC.get((r["gsis_id"], int(float(r["week"]))), 9), int(float(r["depth"])))
                except (TypeError, ValueError): pass
    except Exception: pass
    prev = collections.defaultdict(list)
    for w in range(1, 19):
        for pid, s in (ST.get(f"{season-1}-{w}") or {}).items():
            if s.get("gp"): prev[pid].append(s.get("pts_ppr") or 0.0)
    PTS = collections.defaultdict(dict)
    for w in range(1, 18):
        for pid, s in (ST.get(f"{season}-{w}") or {}).items():
            if s.get("gp"): PTS[pid][w] = s.get("pts_ppr") or 0.0
    LW = min(17, max([int(k.split("-")[1]) for k in ST if k.startswith(f"{season}-")] or [0]))
    out = []
    for w in checks:
        if w > LW: continue
        pj = SP.get(f"{season}-{w}") or {}
        cand = {pid for pid, s in pj.items() if (s.get("pts_ppr") or 0) >= .3} | {pid for pid in PTS if any(k < w for k in PTS[pid])}
        for pid in sorted(cand):
            pos = POS.get(pid)
            if pos not in ("QB", "RB", "WR", "TE"): continue
            g = s2g.get(pid); tm = TEAM.get(g, {})
            past = [PTS[pid][k] for k in sorted(PTS[pid]) if k < w]
            if not tm and not past: continue
            def team_at(k):
                b = [x for x in tm if x <= k]
                if b: return tm[max(b)]
                a = [x for x in tm if x > k]
                return tm[min(a)] if a else None
            e = EP.get(g, {}); ew = [k for k in sorted(e) if k < w]
            fpv = [e[k][0] for k in ew if e[k][0] is not None]; xfv = [e[k][1] for k in ew if e[k][1] is not None]
            rec = [w - k for k in (1, 2, 3, 4) if w - k >= 1]; played = set(k for k in PTS[pid] if k < w) | set(ew)
            age = None; bd = s2b.get(pid)
            if bd and bd not in ("NA", "") and KICK.get(w):
                try: age = (datetime.date.fromisoformat(KICK[w]) - datetime.date.fromisoformat(bd[:10])).days / 365.25
                except ValueError: pass
            pr = (pj.get(pid) or {}).get("pts_ppr")
            def outc(lo, hi):
                tg = [k for k in range(lo, hi + 1) if team_at(k) in TW[k]]; pl = [k for k in tg if k in PTS[pid]]
                return len(tg), sum(PTS[pid][k] for k in pl)
            gR, yR = outc(w, LW); g4, y4 = outc(w, w + 3) if w + 3 <= LW else (0, 0)
            ppg = st.mean(past) if past else None
            r = dict(w=w, pid=pid, pos=pos, proj=pr, bye=team_at(w) not in TW[w], gp=len(past), ppg=ppg,
                     l3=st.mean(past[-3:]) if past else None, l4=st.mean(past[-4:]) if past else None,
                     prev=st.mean(prev[pid]) if len(prev[pid]) >= 4 else None, ag=len(ew), fp=st.mean(fpv) if fpv else None,
                     xfp=st.mean(xfv) if xfv else None, x3=st.mean(xfv[-3:]) if xfv else None, inj=INJ.get((g, w)), dc=DC.get((g, w)),
                     age=age, nrec=len(rec), prec=sum(1 for k in rec if k in played), gR=gR, yR=yR, g4=g4, y4=y4, LW=LW)
            if not ((r["gp"] >= 2 and (ppg or 0) >= 5) or (pr or 0) >= 5): continue
            out.append(r)
    return out

def grade(rows, A, M):
    res = {}
    for r in rows:
        old = app_old(r); c = M.get(r["pos"])
        r["hm"] = (1 - A) * old + A * fit(r, c) if c else old
        base = r["ppg"] if r["ppg"] is not None else (r["proj"] or 0.0)
        r["ppg_"] = base; r["l4_"] = r["l4"] if r["l4"] is not None else base
        r["sl_"] = r["proj"] if (r["proj"] is not None and not r["bye"]) else base
    NAMES = {"ppg_": "season PPG", "l4_": "last-4 PPG", "sl_": "Sleeper projection carried forward"}
    for w in CHECK:
        for hz, yk, gk in (("", "yR", "gR"), ("_next4", "y4", "g4")):
            xs = [r for r in rows if r["w"] == w and r[gk] >= 1]
            if len(xs) < 40: continue
            mae = lambda k: sum(abs(r[k] - r[yk] / r[gk]) for r in xs) / len(xs)
            nv = {k: mae(k) for k in NAMES}; best = min(sorted(nv), key=lambda k: nv[k])
            d = {"n": len(xs), "hm": round(mae("hm"), 3), "naive": round(nv[best], 3), "naive_is": NAMES[best],
                 "through": 17 if hz == "" and xs[0]["LW"] >= 17 else (w + 3 if hz else xs[0]["LW"]),
                 "pos": {p: round(sum(abs(r["hm"] - r[yk] / r[gk]) for r in xs if r["pos"] == p) / max(1, sum(1 for r in xs if r["pos"] == p)), 3) for p in ("QB", "RB", "WR", "TE")}}
            res[f"wk{w}{hz}"] = d
    return res

def section(ctx):
    season = ctx["season"]; A, M = load_ros114()
    rows = build_rows(season, ctx["ST"], ctx["SP"], ctx["PP"])
    res = grade(rows, A, M)
    return {"ros": dict(season=season, unit="points per team game, missed games count 0 (PPR)", blend=A,
                        tested="held out 2025: 3.50 vs 3.82 shipped before v114 (naive best 4.51); 2026 wk 4/8: 3.94 vs 4.24", **res)}

if __name__ == "__main__":
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("pp", "scripts/proj_panel.py"); PP = importlib.util.module_from_spec(spec); spec.loader.exec_module(PP)
    ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]; SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]
    season = int(sys.argv[1]) if len(sys.argv) > 1 else max(int(k.split("-")[0]) for k in ST)
    A, M = load_ros114(sys.argv[2] if len(sys.argv) > 2 else "index.html")
    print(json.dumps(grade(build_rows(season, ST, SP, PP), A, M), indent=1))
