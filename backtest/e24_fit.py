"""Task B2 step 2: QB models. Fit on 2021-24, test on 2025 and 2026 separately vs Sleeper and the shipped QB formula
(PJC.QB from index.html, x .88 when questionable). Median regression (MAE); alternatives: L1-regularised quantile regression
and a monotone-constrained small gradient-boosted model. Features are the shipped prediction h0 plus QB terms."""
import os, json, re, sys, numpy as np, pandas as pd
from sklearn.linear_model import QuantileRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
B = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(B)
df = pd.read_pickle(f"{B}/e24_panel.pkl")
PJC = json.loads(re.search(r"const PJC=(\{.*?\});", open(f"{R}/index.html", encoding="utf-8").read()).group(1))
c = np.array(PJC["QB"])
def Xb(d):
    v = lambda k: d[k].fillna(d.base)
    return np.column_stack([d.base, v("ppg"), v("l3"), v("xs"), v("x3"),
                            np.where(d.rk.notna(), d.base * (16.5 - d.rk.fillna(16.5)) / 16, 0),
                            np.where(d.imp.notna(), d.base * (d.imp.fillna(22.5) - 22.5) / 22.5, 0),
                            d["ppg"].notna().astype(float), d["xs"].notna().astype(float)])
df["h0"] = np.maximum(0, c[0] + Xb(df) @ c[1:]) * np.where(df.q == 1, .88, 1)
has = df.rpg.notna()
# candidate extra terms (0 when unknown)
T = {
 "rush":  np.where(has, df.rpg.fillna(0) - 4, 0),                      # rush attempts/g above 4
 "rsh":   np.where(has, df.rsh.fillna(.15) - .15, 0),
 "epad":  np.where(has, df.epad.fillna(0) * df.n / (df.n + 4), 0),      # shrunk
 "cpoe":  np.where(has, df.cpoe.fillna(0) / 10 * df.n / (df.n + 4), 0),
 "sackr": np.where(has, (df.sackr.fillna(.07) - .07) * 10, 0),
 "dq":    df.dq.fillna(0) / 5,
 "sp":    df.sp.fillna(0) / 7,
 "tot":   (df.tot.fillna(45) - 45) / 7,
 "home":  df.home.fillna(.5) - .5,
 "dome":  df.dome.fillna(0),
 "wind":  np.maximum(0, df.wind.fillna(8) - 10) / 10,
 "cold":  np.where(df.temp.notna() & (df.temp < 40), 1, 0),
}
for k, v in T.items(): df["t_" + k] = v
tr = df[df.season <= 2024]; TE = {y: df[df.season == y] for y in (2025, 2026)}
def mae(a, p): return float(np.mean(np.abs(a - p)))
def wb(d, p, ref):  # weeks where p beats ref
    e = d.assign(e=np.abs(d.actual - p), s=np.abs(d.actual - ref)).groupby("week")[["e", "s"]].mean(); return f"{int((e.e < e.s).sum())}/{len(e)}"
def qfit(d, cols, alpha=0):
    X = d[cols].values; y = d.actual / np.where(d.q == 1, .88, 1)
    return QuantileRegressor(quantile=.5, alpha=alpha, solver="highs").fit(X, y)
def qpred(m, d, cols): return np.maximum(0, m.predict(d[cols].values)) * np.where(d.q == 1, .88, 1)
df["h0u"] = df.h0 / np.where(df.q == 1, .88, 1); tr = df[df.season <= 2024]; TE = {y: df[df.season == y] for y in (2025, 2026)}
out = {"n": {"train": len(tr), **{str(y): len(d) for y, d in TE.items()}}}
base = {}
for y, d in TE.items(): base[y] = dict(sleeper=round(mae(d.actual, d.base), 3), shipped=round(mae(d.actual, d.h0), 3), shipped_wb=wb(d, d.h0, d.base))
out["baseline"] = base; print("baseline", base)
# 1) recalibrate shipped: actual ~ a + b*h0 (sanity), then one extra term at a time; sign per training season
res = {}
for k in ["none"] + list(T):
    cols = ["h0u"] + ([] if k == "none" else ["t_" + k])
    m = qfit(tr, cols); signs = []
    for y in range(2021, 2025):
        mm = qfit(tr[tr.season == y], cols); signs.append(round(float(mm.coef_[-1]), 2))
    r = {"coef": [round(float(m.intercept_), 3)] + [round(float(x), 3) for x in m.coef_], "by_season_last": signs}
    for y, d in TE.items(): p = qpred(m, d, cols); r[y] = (round(mae(d.actual, p), 3), wb(d, p, d.h0), wb(d, p, d.base))
    res[k] = r; print(k, r)
out["one_at_a_time"] = {k: {kk: (vv if not isinstance(kk, int) else list(vv)) for kk, vv in v.items()} for k, v in res.items()}
# 2) full refit of the 10 PJC inputs + QB terms (raw features), median regression and L1
names = ["base", "ppg", "l3", "xs", "x3", "mat", "imp", "hasppg", "hasxs"]
for i, nme in enumerate(names): df["b_" + nme] = Xb(df)[:, i]
tr = df[df.season <= 2024]; TE = {y: df[df.season == y] for y in (2025, 2026)}
bcols = ["b_" + n for n in names]
def run(label, cols, alpha=0):
    m = qfit(tr, cols, alpha); r = {"coef": dict(zip(["int"] + cols, [round(float(m.intercept_), 3)] + [round(float(x), 3) for x in m.coef_]))}
    for y, d in TE.items(): p = qpred(m, d, cols); r[y] = [round(mae(d.actual, p), 3), wb(d, p, d.h0), wb(d, p, d.base)]
    print(label, {k: v for k, v in r.items() if k != "coef"}); return r
out["refit_base"] = run("refit10", bcols)
for sel in (["rush", "epad"], ["rush", "dq", "sp"], ["rush", "epad", "dq", "sp", "wind"], list(T)):
    cols = ["h0u"] + ["t_" + k for k in sel]; out["h0+" + "+".join(sel)] = run("h0+" + "+".join(sel), cols)
    out["refit10+" + "+".join(sel)] = run("refit10+" + "+".join(sel), bcols + ["t_" + k for k in sel])
for a in (.001, .003, .01, .03):
    out[f"L1_{a}_all"] = run(f"L1 a={a} refit10+all", bcols + ["t_" + k for k in T], a)
# 3) monotone small GBM on h0 + QB terms (residual-free: predicts actual directly)
gcols = ["h0u", "t_rush", "t_epad", "t_dq", "t_sp", "t_tot", "t_wind", "t_dome", "t_sackr"]
mono = [1, 0, 1, 1, 1, 1, -1, 1, -1]
g = HistGradientBoostingRegressor(loss="absolute_error", max_iter=150, learning_rate=.05, max_depth=3, min_samples_leaf=100, monotonic_cst=mono, random_state=0).fit(tr[gcols], tr.actual / np.where(tr.q == 1, .88, 1))
r = {}
for y, d in TE.items(): p = np.maximum(0, g.predict(d[gcols])) * np.where(d.q == 1, .88, 1); r[y] = [round(mae(d.actual, p), 3), wb(d, p, d.h0), wb(d, p, d.base)]
print("gbm_mono", r); out["gbm_mono"] = r
json.dump(out, open(f"{B}/e24_fit.json", "w"), indent=1, default=str)
