"""WR adds: can the rest-of-month rate for receivers on the wire be improved? Fit 2021-23, test 2024-25 on waiver pools.
Adds receiving-role features from nflverse weekly stats (air-yards share, WOPR, average depth) and scoring-over-expected
(TD luck), and tries stronger shrinkage. Writes e9_Dfit_wr.pkl (e9_Dfit with WR 'lin' replaced by the chosen variant)."""
import pandas as pd, numpy as np, os, json, sys
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
B = os.path.dirname(os.path.abspath(__file__)); DL = B + "/dl"
sys.argv = [sys.argv[0]]
D = pd.read_pickle(B + "/e9_Dfit.pkl")
ids = pd.read_csv(DL + "/ids.csv", low_memory=False).dropna(subset=["sleeper_id"]); ids["sid"] = ids.sleeper_id.astype(int).astype(str)
s2g = dict(zip(ids.sid, ids.gsis_id))
W = []
for y in range(2021, 2026):
    p = pd.read_csv(f"{DL}/pw_{y}.csv", low_memory=False); p = p[p.season_type == "REG"]
    W.append(p[["player_id", "week", "targets", "receiving_air_yards", "target_share", "air_yards_share", "wopr", "receptions", "receiving_tds"]].assign(s=y))
W = pd.concat(W).rename(columns={"player_id": "g"})
G = {k: v.sort_values("week") for k, v in W.groupby(["s", "g"])}
def roll(s, gsis, w):
    q = G.get((s, gsis))
    if q is None: return [np.nan] * 8
    q = q[q.week < w]
    if not len(q): return [np.nan] * 8
    l3 = q.tail(3); t = q.targets.sum()
    return [q.air_yards_share.mean(), l3.air_yards_share.mean(), q.wopr.mean(), l3.wopr.mean(),
            q.receiving_air_yards.sum() / t if t else np.nan, l3.targets.mean(), q.targets.mean(), q.receiving_tds.sum() / max(1, len(q))]
wr = D.pos == "WR"
F = np.array([roll(s, s2g.get(pid), w) for s, pid, w in zip(D[wr].s, D[wr].pid, D[wr].w)])
for i, c in enumerate(["as", "as3", "wopr", "wopr3", "adot", "tg3", "tg", "tdpg"]): D.loc[wr, c] = F[:, i]
q = D[wr].copy(); q["rate"] = q.y4 / q.games; q = q[q.games > 0]
def base(d):
    X = pd.DataFrame(index=d.index); ppg = d.ppg.fillna(d.proj); l3 = d.l3.fillna(ppg); lw = d.lw.fillna(ppg); x = d.xfp.fillna(ppg); x3 = d.x3.fillna(x)
    prev = d.prev.fillna(d.proj); hp = d.prev.notna().astype(float); k = d.gp / (d.gp + 3)
    X["proj"] = d.proj; X["ppg_k"] = k * ppg; X["l3_k"] = k * l3; X["x_k"] = k * x; X["x3_k"] = k * x3; X["lw_k"] = k * lw; X["prev"] = hp * prev; X["hp"] = hp
    X["snap3"] = d.snap3.fillna(0) / (100 if d.snap3.max() > 1.5 else 1); X["dsnap"] = (d.snap3 - d.snap).fillna(0) / (100 if d.snap.max() > 1.5 else 1)
    X["ts3"] = d.ts3.fillna(0); X["dts"] = (d.ts3 - d.ts).fillna(0); X["cs3"] = d.cs3.fillna(0); X["dcs"] = (d.cs3 - d.cs).fillna(0)
    X["out"] = d.inj.isin(["Out", "Doubtful"]).astype(float); X["q"] = (d.inj == "Questionable").astype(float)
    X["dc1"] = (d.dc == 1).astype(float); X["dc3"] = (d.dc >= 3).astype(float); rk = d.rk.fillna(999) if "rk" in d else pd.Series(999, index=d.index)
    X["t5"] = (rk <= 5) * 1.; X["t15"] = ((rk > 5) & (rk <= 15)) * 1.; X["t30"] = ((rk > 15) & (rk <= 30)) * 1.; X["t50"] = ((rk > 30) & (rk <= 50)) * 1.; X["t100"] = ((rk > 50) & (rk <= 100)) * 1.
    return X
def role(d, X):
    X = X.copy(); k = d.gp / (d.gp + 3)
    X["as_k"] = k * d["as"].fillna(0); X["as3_k"] = k * d.as3.fillna(0); X["wopr_k"] = k * d.wopr.fillna(0); X["wopr3_k"] = k * d.wopr3.fillna(0)
    X["adot_k"] = k * d.adot.fillna(0).clip(-5, 25); X["tg3_k"] = k * d.tg3.fillna(0)
    X["fpoe_k"] = k * (d.ppg.fillna(d.proj) - d.xfp.fillna(d.ppg.fillna(d.proj)))  # scoring above expected (TD luck) tends to fade
    return X
tr, te = q.s <= 2023, q.s >= 2024
w8 = np.where(q[tr].own < .6, 2.0, 1.0)
def ev(sc, pool):
    d = q[te & pool].assign(sc=sc[te & pool]); r = {"rho": [], "top5": [], "top10": [], "slope": []}
    for _, g in d.groupby(["s", "w"]):
        if len(g) < 15: continue
        r["rho"].append(spearmanr(g.sc, g.y4).correlation); r["top5"].append(g.nlargest(5, "sc").y4.mean()); r["top10"].append(g.nlargest(10, "sc").y4.mean())
    t = d.groupby(["s", "w"], group_keys=False).apply(lambda g: g.nlargest(10, "sc"))
    pr, ac = t.sc / t.games, t.y4 / t.games
    return dict(rho=round(np.nanmean(r["rho"]), 3), top5=round(np.mean(r["top5"]), 2), top10=round(np.mean(r["top10"]), 2),
                calib=round(float(ac.mean() / pr.mean()), 3), slope=round(float(np.polyfit(pr, ac, 1)[0]), 3))
pool = q.own < .5
res = {}; preds = {}
res["current (shipped WVC)"] = ev(q.lin.clip(lower=0) * q.games, pool); preds["current"] = q.lin
Xb, Xr = base(q), role(q, base(q))
for nm, X, a in [("refit base a=3", Xb, 3), ("base a=30", Xb, 30), ("base + role a=3", Xr, 3), ("base + role a=30", Xr, 30), ("base + role a=100", Xr, 100)]:
    m = Ridge(alpha=a).fit(X[tr], q[tr].rate, sample_weight=w8); p = pd.Series(m.predict(X), index=q.index); preds[nm] = p
    res[nm] = ev(p.clip(lower=0) * q.games, pool)
    if nm == "base + role a=30": coef = dict(zip(["_b"] + list(X.columns), np.round([m.intercept_] + list(m.coef_), 4)))
gb = HistGradientBoostingRegressor(max_iter=300, learning_rate=.04, max_leaf_nodes=15, min_samples_leaf=60).fit(Xr[tr], q[tr].rate, sample_weight=w8)
p = pd.Series(gb.predict(Xr), index=q.index); preds["boosted + role"] = p; res["boosted + role"] = ev(p.clip(lower=0) * q.games, pool)
res["Sleeper projection only"] = ev(q.proj * q.games, pool)
for k, v in res.items(): print(f"{k:28s}", v)
print("role-model coefficients (a=30):", json.dumps({k: float(v) for k, v in coef.items()}))
pd.to_pickle(preds, B + "/e9_wr_preds.pkl")
