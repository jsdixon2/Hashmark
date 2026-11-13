"""Value test A (owner: "follow your suggestions"): should today's value already include the predictable drift?
For each test November Y (2022, 2023): players ranked <= 250 in FantasyPros dynasty consensus (1QB and SF lists).
  V0  = today's market value (app curve of the rank)                         [what the app shows now, market part]
  Va  = V0 x exp(a x expected 1-year log change)  for a in 0..1, the change from x9 cells fitted ONLY on value paths that
        ended before November Y (no look-ahead).
Targets: (1) market value one year later (same list, app curve); (2) real PPR points over the next two seasons (nflverse).
Scores: Spearman rank correlation with each target, and mean absolute error vs next year's value."""
import math, statistics as st, csv, datetime as dt, collections, sys
src = open("backtest/x9_paths.py").read().split("paths = []")[0]; exec(src)   # loaders, curve, RK, val, near, cellkey, FM, info, D
QS = [.05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95]
# all value paths (start, 365 days) once
paths = []
for f in FM:
    for i in range(len(D)):
        R = RK[f][i]
        if not R: continue
        j = near(D[i] + dt.timedelta(days=365))
        if j is None or j <= i or not RK[f][j]: continue
        for pid, rank in R.items():
            if rank > 250 or pid not in info or info[pid][0] not in ("QB", "RB", "WR", "TE"): continue
            paths.append((cellkey(f, pid, i, rank), D[j], math.log(val(f, j, pid) / curve(rank, FM[f][1]))))
def fitcells(cut):
    G = collections.defaultdict(list)
    for ck, end, lr in paths:
        if end >= cut: continue
        for lvl, key in enumerate((ck, ck[:4], ck[:3], (ck[0], ck[1]), (ck[0],))): G[(lvl,) + key].append(lr)
    return {k: st.median(v) for k, v in G.items() if len(v) >= 30}
def look(M, ck):
    for lvl, key in enumerate((ck, ck[:4], ck[:3], (ck[0], ck[1]), (ck[0],))):
        if (lvl,) + key in M: return M[(lvl,) + key]
    return 0.0
# production: PPR points by season
pts = collections.Counter(); g2s = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA") and r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
for y in range(2021, 2027):
    try:
        for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv", encoding="utf-8")):
            if r["season_type"] == "REG" and r["player_id"] in g2s: pts[(y, g2s[r["player_id"]])] += float(r.get("fantasy_points_ppr") or 0)
    except FileNotFoundError: pass
def spear(a, b):
    n = len(a); ra = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: a[i]))}; rb = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: b[i]))}
    return 1 - 6 * sum((ra[i] - rb[i]) ** 2 for i in range(n)) / (n * (n * n - 1))
A = [0, .25, .5, .75, 1.0, 1.25]
for Y in (2022, 2023):
    i = near(dt.date(Y, 11, 12)); M = fitcells(D[i])
    j = near(D[i] + dt.timedelta(days=365))
    for f in FM:
        R, R1 = RK[f][i], RK[f][j]
        if not R or not R1: continue
        rows = []
        for pid, rank in R.items():
            if rank > 250 or pid not in info or info[pid][0] not in ("QB", "RB", "WR", "TE"): continue
            v0 = curve(rank, FM[f][1]); d = look(M, cellkey(f, pid, i, rank))
            rows.append((v0, d, val(f, j, pid), pts[(Y + 1, pid)] + pts[(Y + 2, pid)]))
        print(f"\nNovember {Y} · {f} · {len(rows)} players (cells fit on paths ending before {D[i]})")
        for a in A:
            v = [x[0] * math.exp(a * x[1]) for x in rows]
            print("  shade %.2f: vs value 1 yr later  rank corr %.3f  error %5.0f  |  vs points next 2 seasons  rank corr %.3f" % (
                a, spear(v, [x[2] for x in rows]), st.mean(abs(p - x[2]) for p, x in zip(v, rows)), spear(v, [x[3] for x in rows])))
