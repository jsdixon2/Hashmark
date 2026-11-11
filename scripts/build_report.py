#!/usr/bin/env python3
"""Engine 8: report card + projection ranges -> data/report.json.

Report card (graded on real results, current season, week by week):
- projections: Hashmark (Sleeper projection through the fitted PJC weights, as in build_calib) vs Sleeper's own,
  mean absolute error per player-week (players projected 3+ who played), PPR.
- win odds: every archived league matchup (bt/leagues.json.gz), pregame team projections from the starters through
  PJC, the app's fitted winProb (WP k .16, c 5, b 1.01); Brier vs a coin flip (.25) and 10-bucket calibration.
- NFL game picks: the e12 rating (no line) vs the closing line, Brier and accuracy for this season's finished games;
  plus the live prediction log in data/teams.json once it has graded games.
- waivers / trades: tested numbers from backtests (season-level), labelled as such.
Projection ranges (fitted on 2021-2023, checked on 2024-2025): actual/projection ratio quantiles (10th, 90th) per
position x projection tier x volatility tier (player's CV over prior games; "new" under 4 games) x questionable flag.
Labels: interval width relative to projection; HIGH / MEDIUM / LOW cut at the 1/3 and 2/3 points per position.
Tested 2024-25 (7,898 player-weeks): 80% range held 82.7%; relative miss HIGH .44 / MEDIUM .53 / LOW .72, coverage
79% / 82% / 87%."""
import gzip, json, math, os, csv, io, statistics, collections, datetime, urllib.request
OUT = "data/report.json"
WP = {"k": .16, "c": 5, "b": 1.01}

def load_pjc():
    import re
    return json.loads(re.search(r"const PJC=(\{.*?\});", open("index.html", encoding="utf-8").read()).group(1))

def positions():
    try:
        txt = urllib.request.urlopen(urllib.request.Request("https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv", headers={"User-Agent": "hashmark-build"}), timeout=60).read().decode()
        rows = csv.DictReader(io.StringIO(txt))
    except Exception:
        rows = csv.DictReader(open("backtest/dl/ids.csv"))
    return {str(r["sleeper_id"]).split(".")[0]: r["position"] for r in rows if r.get("sleeper_id") not in ("", "NA", None)}

def pts(st, sc=None):
    sc = sc or {}; rec = sc.get("rec", 1)
    b = st.get("pts_ppr") if rec >= .75 else st.get("pts_half_ppr") if rec >= .25 else st.get("pts_std")
    if b is None: b = st.get("pts_ppr", 0) or 0
    if sc.get("pass_td") is not None and st.get("pass_td") is not None: b += (sc["pass_td"] - 4) * st["pass_td"]
    if sc.get("pass_int") is not None and st.get("pass_int") is not None: b += (sc["pass_int"] + 1) * st["pass_int"]
    return b

def hm(v, c, w):
    return max(0.0, c[0] + sum(c[1:6]) * v + (0 if w <= 2 else c[8] + c[9])) if c else v

def win_prob(pa, pb):
    sd = math.sqrt((pa * WP["k"] + WP["c"]) ** 2 + (pb * WP["k"] + WP["c"]) ** 2) or 1
    return 1 / (1 + math.exp(-1.7 * WP["b"] * (pa - pb) / sd))

def phi(x): return .5 * (1 + math.erf(x / math.sqrt(2)))

def main():
    C = load_pjc(); POS = positions()
    SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]; ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
    season = max(int(k.split("-")[0]) for k in ST)
    weeks = sorted({int(k.split("-")[1]) for k in ST if k.startswith(f"{season}-")})
    # ---------- projections ----------
    proj_wk = {}
    rows_all = collections.defaultdict(list)   # for ranges: (season, week, pid, pos, hm_proj, actual)
    for key, P in SP.items():
        s, w = map(int, key.split("-"))
        S = ST.get(key) or {}
        for pid, pr in P.items():
            pos = POS.get(pid)
            if pos not in ("QB", "RB", "WR", "TE"): continue
            st = S.get(pid)
            if not st or not st.get("gp"): continue
            sp = pts(pr); a = pts(st)
            if sp < 3: continue
            h = hm(sp, C.get(pos), w)
            rows_all[(s, w)].append((pid, pos, h, sp, a))
    for w in weeks:
        r = rows_all.get((season, w)) or []
        if len(r) < 50: continue
        proj_wk[w] = {"n": len(r), "hm": round(sum(abs(a - h) for _, _, h, _, a in r) / len(r), 3), "sl": round(sum(abs(a - sp) for _, _, _, sp, a in r) / len(r), 3)}
    pw = list(proj_wk.values())
    proj = {"weeks": proj_wk, "mae_hm": round(sum(x["hm"] * x["n"] for x in pw) / max(1, sum(x["n"] for x in pw)), 3) if pw else None,
            "mae_sleeper": round(sum(x["sl"] * x["n"] for x in pw) / max(1, sum(x["n"] for x in pw)), 3) if pw else None,
            "weeks_beat": sum(1 for x in pw if x["hm"] < x["sl"]), "weeks": proj_wk, "n_weeks": len(pw)}
    # ---------- win odds ----------
    L = json.load(gzip.open("bt/leagues.json.gz", "rt"))["leagues"]
    wo = []
    for lg in L.values():
        if lg.get("guillotine") or int(lg["season"]) != season: continue
        sc = lg.get("sc") or {}; pws = lg.get("pws") or 15
        for wk, rows in lg["weeks"].items():
            w = int(wk); P = SP.get(f"{season}-{w}")
            if not P or w >= pws: continue
            tot = {}
            for rid, mid, pt, st in rows:
                hit = [x for x in st if x in P]
                if not st or len(hit) / len(st) < .9: continue
                tot[rid] = (sum(hm(pts(P[x], sc), C.get(POS.get(x)), w) for x in hit), mid, pt)
            by = collections.defaultdict(list)
            for rid, (t, mid, pt) in tot.items():
                if mid is not None: by[mid].append((t, pt))
            for pair in by.values():
                if len(pair) != 2 or pair[0][1] == pair[1][1] or min(pair[0][1], pair[1][1]) <= 0: continue
                (ta, pa), (tb, pb) = pair; wo.append((w, win_prob(ta, tb), 1 if pa > pb else 0))
    def brier(xs): return round(sum((p - y) ** 2 for _, p, y in xs) / len(xs), 4) if xs else None
    buckets = []
    for i in range(10):
        xs = [x for x in wo if i / 10 <= x[1] < (i + 1) / 10 or (i == 9 and x[1] == 1)]
        if len(xs) >= 20: buckets.append({"said": round(sum(p for _, p, _ in xs) / len(xs), 3), "won": round(sum(y for *_, y in xs) / len(xs), 3), "n": len(xs)})
    odds = {"n": len(wo), "brier": brier(wo), "coin": .25, "acc": round(sum((p > .5) == (y == 1) for _, p, y in wo) / len(wo), 3) if wo else None,
            "calib": buckets, "weeks": {w: brier([x for x in wo if x[0] == w]) for w in sorted({x[0] for x in wo})}}
    # ---------- NFL game picks ----------
    games = {}
    try:
        T = json.load(open("data/teams.json")); card = T.get("card") or {}
    except Exception: card = {}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("bt", "scripts/build_teams.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        rows = [r for r in m.load() if int(r["season"]) >= 2002]; rows.sort(key=lambda r: (int(r["season"]), int(r["week"]), r.get("gameday") or ""))
        rat, last = {}, None; out = []
        for g in rows:
            s = int(g["season"])
            if s != last: rat = {t: m.PRIOR * v for t, v in rat.items()}; last = s
            hs, as_ = m.num(g["home_score"]), m.num(g["away_score"])
            if hs is None or as_ is None: continue
            h, a = rat.get(g["home_team"], 0.0), rat.get(g["away_team"], 0.0); hfa = 0 if g.get("location") == "Neutral" else m.HFA
            mu = h - a + hfa
            if s == season and g["game_type"] == "REG" and hs != as_:
                sp = m.num(g.get("spread_line")); y = 1 if hs > as_ else 0
                out.append((int(g["week"]), phi(mu / m.SIG), phi(sp / m.SIG) if sp is not None else None, y))
            err = max(-m.CAP, min(m.CAP, hs - as_)) - mu
            rat[g["home_team"]] = h + m.K * err; rat[g["away_team"]] = a - m.K * err
        rr = [(w, p, y) for w, p, l, y in out]; ll = [(w, l, y) for w, p, l, y in out if l is not None]
        games = {"n": len(out), "rating_brier": brier(rr), "line_brier": brier(ll), "rating_acc": round(sum((p > .5) == (y == 1) for _, p, y in rr) / len(rr), 3) if rr else None,
                 "line_acc": round(sum((p > .5) == (y == 1) for _, p, y in ll) / len(ll), 3) if ll else None, "live_log": card}
    except Exception as e:
        games = {"error": str(e)[:120], "live_log": card}
    # ---------- projection ranges ----------
    hist = collections.defaultdict(list)    # pid -> [(s,w,actual)]
    for (s, w), rs in sorted(rows_all.items()):
        for pid, pos, h, sp, a in rs: hist[pid].append((s, w, a))
    injq = set()
    for y in range(2021, 2026):
        f = f"backtest/dl/inj_{y}.csv"
        if not os.path.exists(f): continue
        for r in csv.DictReader(open(f)):
            if (r.get("report_status") or "") == "Questionable" and r.get("game_type", "REG") == "REG":
                injq.add((int(r["season"]), int(r["week"]), r.get("gsis_id")))
    g2s = {}
    if os.path.exists("backtest/dl/ids.csv"):
        for r in csv.DictReader(open("backtest/dl/ids.csv")):
            if r.get("sleeper_id") not in ("", "NA"): g2s[r["gsis_id"]] = str(r["sleeper_id"]).split(".")[0]
    q = {(s, w, g2s[g]) for s, w, g in injq if g in g2s}
    def tier(h): return 0 if h < 8 else 1 if h < 14 else 2
    def vol(pid, s, w):
        past = [a for ss, ww, a in hist.get(pid, []) if ss == s and ww < w]
        if len(past) < 4: return "new"
        m_ = statistics.mean(past); return "lo" if m_ <= 0 or statistics.pstdev(past) / m_ < .45 else ("mid" if statistics.pstdev(past) / m_ < .7 else "hi")
    cells = collections.defaultdict(list); test = []
    for (s, w), rs in rows_all.items():
        if s < 2021 or s > 2025: continue
        for pid, pos, h, sp, a in rs:
            if h < 4: continue
            k = (pos, tier(h), vol(pid, s, w), 1 if (s, w, pid) in q else 0)
            (cells[k] if s <= 2023 else test).append((k, h, a) if s > 2023 else a / h)
    def qt(xs, p):
        xs = sorted(xs); i = (len(xs) - 1) * p; lo = int(i); hi = min(len(xs) - 1, lo + 1); return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)
    table = {}
    for k, xs in cells.items():
        if len(xs) < 60:   # small cell: fall back to the cell without the injury split, then without volatility
            continue
        table["|".join(map(str, k))] = [round(qt(xs, .1), 3), round(qt(xs, .9), 3), len(xs)]
    def look(k):
        for kk in (k, (k[0], k[1], k[2], 0), (k[0], k[1], "mid", 0)):
            v = table.get("|".join(map(str, kk)))
            if v: return v
        return None
    widths = collections.defaultdict(list)
    for kk, v in table.items(): widths[kk.split("|")[0]].append(v[1] - v[0])
    cuts = {p: [round(qt(ws, 1 / 3), 3), round(qt(ws, 2 / 3), 3)] for p, ws in widths.items()}
    inside = n = 0; lab = collections.defaultdict(lambda: [0, 0, 0.0])
    for k, h, a in test:
        v = look(k)
        if not v: continue
        n += 1; ok = v[0] * h <= a <= v[1] * h; inside += ok
        wdt = v[1] - v[0]; c = cuts.get(k[0]); L_ = "HIGH" if wdt <= c[0] else "MEDIUM" if wdt <= c[1] else "LOW"
        lab[L_][0] += 1; lab[L_][1] += ok; lab[L_][2] += abs(a - h) / h
    labels = {L_: {"n": v[0], "inside": round(v[1] / v[0], 3), "rel_err": round(v[2] / v[0], 3)} for L_, v in lab.items() if v[0]}
    if not injq:  # injury reports live in backtest/dl (local only): keep the ranges fitted with them
        try:
            old = json.load(open(OUT)).get("ranges")
            if old and old.get("table"): table, cuts = old["table"], old["cuts"]; n = old.get("test_n") or n; inside = (old.get("test_coverage_80") or 0) * n; labels = old.get("labels") or labels
        except Exception: pass
    ranges = {"table": table, "cuts": cuts, "test_coverage_80": round(inside / n, 3) if n else None, "test_n": n, "labels": labels,
              "tiers": [8, 14], "vol_cv": [.45, .7], "new_games": 4}
    # ---------- tested numbers from the backtests ----------
    tested = {"waivers": {"helped": .73, "pts": 8.8, "managers_pts": 7.6, "src": "redraft 2024-25, 516 leagues (e9)"},
              "trades": {"fit_lineup_up": .80, "baseline": .44, "src": "3,413 dynasty/keeper trades 2022-25 (e11)"}}
    out = {"built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "season": season, "projections": proj, "win_odds": odds,
           "games": games, "ranges": ranges, "tested": tested}
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print(json.dumps({"proj": {k: proj[k] for k in ("mae_hm", "mae_sleeper", "weeks_beat", "n_weeks")}, "odds": {k: odds[k] for k in ("n", "brier", "acc")}, "calib": odds["calib"],
                      "games": {k: v for k, v in games.items() if k != "live_log"}, "ranges": {k: ranges[k] for k in ("test_coverage_80", "test_n", "labels", "cuts")}}, indent=1))

if __name__ == "__main__":
    main()
