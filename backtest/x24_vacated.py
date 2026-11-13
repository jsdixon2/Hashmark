"""Data test (owner "test 1 and 2"), test 2: vacated opportunity. For each team and season Y (2021-24): share of the
team's targets / carries in Y that belonged to players NOT on its week-1 depth chart in Y+1 (bt/nfl/depth, published
before games). Each Y+1 player gets his team's vacated target share (RB/WR/TE) and vacated carry share (RB), plus
"moved team" and his own share of his Y team's targets/carries.
(a) Projections: weeks 1-4 of Y+1, Sleeper's projection vs real PPR points (bt/sleeper_proj / sleeper_stats);
    residual regressed on the features per position, fit Y+1 = 2022-23, tested 2024-25 (MAE vs Sleeper alone).
(b) Value: players ranked <= 250 in FantasyPros dynasty consensus near Aug 20 of Y+1; change to early November
    (app curve, log); fitted shift vs "no change", same split."""
import csv, gzip, json, math, collections, statistics as st, datetime as dt
import numpy as np
exec(open("backtest/x9_paths.py").read().split("paths = []")[0])
g2s = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA") and r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
USE = collections.defaultdict(lambda: collections.Counter()); TEAM = {}; TT = collections.defaultdict(lambda: collections.Counter())
for y in range(2021, 2026):
    for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv", encoding="utf-8")):
        if r["season_type"] != "REG": continue
        g = r["player_id"]; t = r["team"]; tg = float(r["targets"] or 0); ca = float(r["carries"] or 0)
        USE[(y, g)]["t"] += tg; USE[(y, g)]["c"] += ca; USE[(y, g)]["team_" + t] += tg + ca + .001
        TT[(y, t)]["t"] += tg; TT[(y, t)]["c"] += ca
for (y, g), u in USE.items(): TEAM[(y, g)] = max((k for k in u if k.startswith("team_")), key=lambda k: u[k])[5:]
W1 = {}
for y in range(2022, 2026):
    best = {}
    for r in csv.DictReader(gzip.open(f"bt/nfl/depth/{y}.csv.gz", "rt")):
        if "game_type" in r:
            if r["game_type"] == "REG" and r["week"] == "1": W1[(y, r["gsis_id"])] = r["team"]
        elif f"{y}-08-01" <= r["dt"][:10] <= f"{y}-09-03" and str(r.get("season")) == str(y):   # 2025 file: dated snapshots, last one before week 1
            if r["gsis_id"] not in best or r["dt"] > best[r["gsis_id"]][0]: best[r["gsis_id"]] = (r["dt"], r["team"])
    for g_, (d_, t_) in best.items(): W1[(y, g_)] = t_
VAC = collections.defaultdict(lambda: collections.Counter())
for (y, g), u in USE.items():
    if y >= 2025: continue
    t = TEAM[(y, g)]
    if W1.get((y + 1, g)) != t: VAC[(y, t)]["t"] += u["t"]; VAC[(y, t)]["c"] += u["c"]
def feats(y1, g, pos):
    t = W1.get((y1, g))
    if not t: return None
    v = VAC[(y1 - 1, t)]; T = TT[(y1 - 1, t)]
    vt = v["t"] / T["t"] if T["t"] else 0; vc = v["c"] / T["c"] if T["c"] else 0
    old = TEAM.get((y1 - 1, g)); mv = 1.0 if old and old != t else 0.0
    u = USE.get((y1 - 1, g), {}); To = TT.get((y1 - 1, old), {}) if old else {}
    own = (u.get("t", 0) / To["t"] if To and To.get("t") else 0) if pos != "RB" else (u.get("c", 0) / To["c"] if To and To.get("c") else 0)
    return [vt, vc if pos == "RB" else 0.0, mv, own]
s2g = {v: k for k, v in g2s.items()}
P = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]; Sx = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
rows = []
for y1 in range(2022, 2026):
    for w in range(1, 5):
        pj = P.get(f"{y1}-{w}", {}); ac = Sx.get(f"{y1}-{w}", {})
        for sid, pr in pj.items():
            pos = info.get(sid, ("",))[0]
            if pos not in ("RB", "WR", "TE") or (pr.get("pts_ppr") or 0) < 3 or sid not in ac or not ac[sid].get("gp"): continue
            g = s2g.get(sid); f = feats(y1, g, pos) if g else None
            if f is None: continue
            rows.append(dict(y=y1, pos=pos, p=pr["pts_ppr"], a=ac[sid].get("pts_ppr") or 0, f=f))
print("(a) projections, weeks 1-4: rows", len(rows))
for pos in ("RB", "WR", "TE"):
    tr = [r for r in rows if r["pos"] == pos and r["y"] <= 2023]; te = [r for r in rows if r["pos"] == pos and r["y"] >= 2024]
    A = np.array([[1] + r["f"] for r in tr]); b = np.array([r["a"] - r["p"] for r in tr]); lam = np.eye(A.shape[1]) * 5; lam[0, 0] = 0
    wgt = np.linalg.solve(A.T @ A + lam, A.T @ b)
    base = st.mean(abs(r["a"] - r["p"]) for r in te); adj = st.mean(abs(r["a"] - r["p"] - float(np.dot(wgt, [1] + r["f"]))) for r in te)
    hi = [r for r in te if r["f"][0] >= .35]
    print("  %-2s test n %5d: Sleeper MAE %.3f -> with vacated %.3f | teams with 35%%+ targets vacated: n %d, Sleeper miss (actual - proj) %+.2f | coef [1, vac tgt, vac car, moved, own share] %s" % (
        pos, len(te), base, adj, len(hi), st.mean(r["a"] - r["p"] for r in hi) if hi else float("nan"), [round(x, 2) for x in wgt]))
print("(b) value, Aug 20 -> early Nov")
for f in FM:
    vr = []
    for y1 in range(2022, 2026):
        i = near(dt.date(y1, 8, 20)); j = near(dt.date(y1, 11, 5))
        if i is None or j is None or not RK[f][i] or not RK[f][j]: continue
        for sid, rk in RK[f][i].items():
            pos = info.get(sid, ("",))[0]; g = s2g.get(sid)
            if rk > 250 or pos not in ("RB", "WR", "TE") or not g: continue
            ft = feats(y1, g, pos)
            if ft is None: continue
            v0 = curve(rk, FM[f][1]); vr.append(dict(y=y1, pos=pos, v0=v0, v1=val(f, j, sid), lr=math.log(val(f, j, sid) / v0), f=ft))
    for pos in ("RB", "WR", "TE"):
        tr = [r for r in vr if r["pos"] == pos and r["y"] <= 2023]; te = [r for r in vr if r["pos"] == pos and r["y"] >= 2024]
        if len(tr) < 50 or not te: continue
        A0 = np.array([[1] for r in tr]); A = np.array([[1] + r["f"] for r in tr]); b = np.array([r["lr"] for r in tr])
        w0 = np.linalg.lstsq(A0, b, rcond=None)[0]; lam = np.eye(A.shape[1]) * 2; lam[0, 0] = 0; w = np.linalg.solve(A.T @ A + lam, A.T @ b)
        e = lambda fn: st.mean(abs(r["v0"] * math.exp(fn(r)) - r["v1"]) for r in te)
        sp = lambda fn: float(np.corrcoef(np.argsort(np.argsort([r["v0"] * math.exp(fn(r)) for r in te])), np.argsort(np.argsort([r["v1"] for r in te])))[0, 1])
        print("  %-3s %-2s test n %4d: value error flat %4.0f | avg shift %4.0f | + vacated %4.0f   rank corr flat %.3f / + vacated %.3f" % (
            f, pos, len(te), e(lambda r: 0), e(lambda r: w0[0]), e(lambda r: float(np.dot(w, [1] + r["f"]))), sp(lambda r: 0), sp(lambda r: float(np.dot(w, [1] + r["f"])))))
# is the TE gain from vacated opportunity or just Sleeper running high on TEs early (an intercept)?
for pos in ("RB", "WR", "TE"):
    tr = [r for r in rows if r["pos"] == pos and r["y"] <= 2023]; te = [r for r in rows if r["pos"] == pos and r["y"] >= 2024]
    c0 = st.median(r["a"] - r["p"] for r in tr)
    print("  %s intercept only (median miss fit 2022-23 %+.2f): test MAE %.3f vs Sleeper %.3f" % (pos, c0, st.mean(abs(r["a"] - r["p"] - c0) for r in te), st.mean(abs(r["a"] - r["p"]) for r in te)))
