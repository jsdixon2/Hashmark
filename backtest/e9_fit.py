"""Fit the waiver/rest-of-month score: points over the next 4 weeks, judged on players actually available on waivers."""
import pandas as pd, numpy as np, json, os
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(B + "/e9_D.pkl")
D = D[D.games > 0].copy()
A_ = pd.read_pickle(B + "/e9_adds.pkl"); c_ = A_.groupby(["s", "w", "pid"]).size().rename("c").reset_index()
c_["rk"] = c_.groupby(["s", "w"]).c.rank(ascending=False, method="first")
D = D.merge(c_[["s", "w", "pid", "rk"]], on=["s", "w", "pid"], how="left")
D["rate"] = D.y4 / D.games
def feats(d):
    X = pd.DataFrame(index=d.index)
    has = (d.gp > 0).astype(float)
    ppg = d.ppg.fillna(d.proj); l3 = d.l3.fillna(ppg); lw = d.lw.fillna(ppg)
    x = d.xfp.fillna(ppg); x3 = d.x3.fillna(x)
    prev = d.prev.fillna(d.proj); hp = d.prev.notna().astype(float)
    k = d.gp / (d.gp + 3)  # how much to trust this season's sample
    X["proj"] = d.proj  # next week's projection left out: archived ones were made after this week's games (would leak)
    X["ppg_k"] = k * ppg; X["l3_k"] = k * l3; X["x_k"] = k * x; X["x3_k"] = k * x3; X["lw_k"] = k * lw
    X["prev"] = hp * prev; X["hp"] = hp
    X["snap3"] = d.snap3.fillna(0) / 100 if d.snap3.max() > 1.5 else d.snap3.fillna(0)
    X["dsnap"] = (d.snap3 - d.snap).fillna(0) / (100 if d.snap.max() > 1.5 else 1)
    X["ts3"] = d.ts3.fillna(0); X["dts"] = (d.ts3 - d.ts).fillna(0); X["cs3"] = d.cs3.fillna(0); X["dcs"] = (d.cs3 - d.cs).fillna(0)
    X["out"] = d.inj.isin(["Out", "Doubtful"]).astype(float); X["q"] = (d.inj == "Questionable").astype(float)
    X["dc1"] = (d.dc == 1).astype(float); X["dc3"] = (d.dc >= 3).astype(float)
    rk = d.rk.fillna(999)
    if os.environ.get("DEM", "1") == "1":
        X["t5"] = (rk <= 5).astype(float); X["t15"] = ((rk > 5) & (rk <= 15)).astype(float); X["t30"] = ((rk > 15) & (rk <= 30)).astype(float); X["t50"] = ((rk > 30) & (rk <= 50)).astype(float)
        if os.environ.get("T100", "1") == "1": X["t100"] = ((rk > 50) & (rk <= 100)).astype(float)
    for p in ("QB", "RB", "WR", "TE"): X["is" + p] = (d.pos == p).astype(float)
    return X
X = feats(D)
tr = D.s <= 2023; te = D.s >= 2024
def evals(score, d, pool):
    m = pool
    sp, t5, t10 = [], [], []
    for (s, w), q in d[m].assign(sc=score[m]).groupby(["s", "w"]):
        if len(q) < 20: continue
        sp.append(spearmanr(q.sc, q.y4).correlation); t5.append(q.nlargest(5, "sc").y4.mean()); t10.append(q.nlargest(10, "sc").y4.mean())
    return dict(rho=round(float(np.nanmean(sp)), 3), top5=round(float(np.mean(t5)), 1), top10=round(float(np.mean(t10)), 1))
out = {}
Dt = D[te]; Xt = X[te]
pools = {"waiver pool (rostered in <50% of leagues)": Dt.own < .5, "deep wire (<20%)": Dt.own < .2, "everyone": Dt.own >= 0}
cands = {}
cands["Sleeper projection"] = Dt.proj * Dt.games
ppg = Dt.ppg.fillna(Dt.proj)
app = (.62 * ppg + .38 * Dt.proj).where(Dt.gp > 0, Dt.proj)
app = app * np.where((Dt.dc == 2) & (Dt.pos != "QB"), .92, np.where((Dt.dc > 2) & (Dt.pos != "QB"), .8, 1)) * np.where(Dt.inj.isin(["Out", "Doubtful"]), .8, 1)
cands["Hashmark now (season PPG + projection)"] = app * Dt.games
cands["Crowd: most-rostered"] = Dt.own
# fitted linear, per position interactions via separate fits
lin = pd.Series(0.0, index=D.index); coefs = {}
cols = [c for c in X.columns if not c.startswith("is")]
for p in ("QB", "RB", "WR", "TE"):
    m = D.pos == p
    r = Ridge(alpha=3.0).fit(X[m & tr][cols], D[m & tr].rate, sample_weight=np.where(D[m & tr].own < .6, 2.0, 1.0))
    lin[m] = r.predict(X[m][cols]); coefs[p] = dict(zip(["_b"] + cols, np.round([r.intercept_] + list(r.coef_), 4)))
cands["Fitted linear (per position)"] = lin[te].clip(lower=0) * Dt.games
gb = HistGradientBoostingRegressor(max_iter=300, learning_rate=.05, max_leaf_nodes=15, min_samples_leaf=40).fit(X[tr], D[tr].rate)
cands["Gradient boosting (reference)"] = pd.Series(gb.predict(Xt), index=Dt.index).clip(lower=0) * Dt.games
for pn, pm in pools.items():
    out[pn] = {k: evals(v, Dt, pm) for k, v in cands.items()}
out["coef"] = coefs
out["n_test"] = int(te.sum()); out["n_train"] = int(tr.sum())
print(json.dumps(out, indent=1)); json.dump(out, open(B + "/e9" + os.environ.get("DEM", "1") + ".json", "w"), indent=1)
D.assign(lin=lin).to_pickle(B + "/e9_Dfit" + ("" if os.environ.get("DEM", "1") == "1" else "0") + ".pkl")
# per-position view on the waiver pool: rank within position, top-3 each week
pp = {}
for p in ("QB", "RB", "WR", "TE"):
    m = (Dt.pos == p) & (Dt.own < .5)
    r = {}
    for k, v in cands.items():
        sp, t3 = [], []
        for (s, w), q in Dt[m].assign(sc=v[m]).groupby(["s", "w"]):
            if len(q) < 8: continue
            sp.append(spearmanr(q.sc, q.y4).correlation); t3.append(q.nlargest(3, "sc").y4.mean())
        r[k] = (round(float(np.nanmean(sp)), 3), round(float(np.mean(t3)), 1))
    pp[p] = r
print(json.dumps(pp, indent=1)); out["by_pos"] = pp; json.dump(out, open(B + "/e9" + os.environ.get("DEM", "1") + ".json", "w"), indent=1)
