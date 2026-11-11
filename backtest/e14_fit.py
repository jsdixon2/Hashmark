"""Engine 1 refit, step 2: fit on 2021-24, test on 2025 and 2026 (to date). Metric: MAE in PPR points, players Sleeper
projected 3+ who played (same population as data/report.json). Compares Sleeper, the app's current PJC formula, a refit
of the same formula (median regression = minimises MAE), and a gradient-boosted model as a ceiling."""
import os, json, re, numpy as np, pandas as pd
from sklearn.linear_model import QuantileRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
B = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(B)
df = pd.read_pickle(f"{B}/e14_panel.pkl"); df = df[df.base >= 3].copy()
PJC = json.loads(re.search(r"const PJC=(\{.*?\});", open(f"{R}/index.html", encoding="utf-8").read()).group(1))
def X(d):
    v = lambda c: d[c].fillna(d.base)
    return np.column_stack([d.base, v("ppg"), v("l3"), v("xs"), v("x3"),
                            np.where(d.rk.notna(), d.base * (16.5 - d.rk.fillna(16.5)) / 16, 0),
                            np.where(d.imp.notna(), d.base * (d.imp.fillna(22.5) - 22.5) / 22.5, 0),
                            d["ppg"].notna().astype(float), d["xs"].notna().astype(float)])
def app(d, C=None):
    out = np.zeros(len(d))
    for pos, c in (C or PJC).items():
        m = (d.pos == pos).values
        if m.any(): out[m] = np.maximum(0, c[0] + X(d[m]) @ np.array(c[1:]))
    return np.where(d.q == 1, out * .88, out)
tr = df[df.season <= 2024]; te = {y: df[df.season == y] for y in (2025, 2026)}
newC = {}; gb = {}
for pos in ("QB", "RB", "WR", "TE"):
    d = tr[tr.pos == pos]; y = d.actual / np.where(d.q == 1, .88, 1)
    qr = QuantileRegressor(quantile=.5, alpha=0, solver="highs").fit(X(d), y)
    newC[pos] = [round(float(qr.intercept_), 3)] + [round(float(x), 3) for x in qr.coef_]
    F = np.column_stack([X(d), d.q, d.week, d.n]); gb[pos] = HistGradientBoostingRegressor(loss="absolute_error", max_iter=300, learning_rate=.05, max_leaf_nodes=15, min_samples_leaf=80).fit(F, d.actual)
def gbp(d):
    out = np.zeros(len(d))
    for pos, g in gb.items():
        m = (d.pos == pos).values
        if m.any(): dd = d[m]; out[m] = g.predict(np.column_stack([X(dd), dd.q, dd.week, dd.n]))
    return out
res = {"new_PJC": newC}
for y, d in te.items():
    a = d.actual.values; r = {}
    for name, p in (("sleeper", d.base.values), ("app_now", app(d)), ("refit", app(d, newC)), ("gbm_ceiling", gbp(d))):
        r[name] = round(float(np.mean(np.abs(a - p))), 3)
        wk = d.assign(e=np.abs(a - p), s=np.abs(a - d.base.values)).groupby("week")[["e", "s"]].mean()
        r[name + "_weeks_beat"] = f"{int((wk.e < wk.s).sum())}/{len(wk)}"
        r[name + "_by_pos"] = {pos: round(float(np.mean(np.abs(a[(d.pos == pos).values] - p[(d.pos == pos).values]))), 3) for pos in ("QB", "RB", "WR", "TE")}
    res[y] = r
    print(y, len(d), {k: v for k, v in r.items() if not k.endswith("by_pos")})
    for k in ("sleeper", "app_now", "refit", "gbm_ceiling"): print("   ", k, r[k + "_by_pos"])
print("new PJC", newC)
json.dump(res, open(f"{B}/e14_fit.json", "w"), indent=1)
# ---- shipping fit: 2021-25, checked on 2026 (QB keeps the current PJC: the refit was worse for QBs in both test years)
tr2 = df[df.season <= 2025]; ship = {"QB": PJC["QB"]}
for pos in ("RB", "WR", "TE"):
    d = tr2[tr2.pos == pos]; y = d.actual / np.where(d.q == 1, .88, 1)
    qr = QuantileRegressor(quantile=.5, alpha=0, solver="highs").fit(X(d), y)
    ship[pos] = [round(float(qr.intercept_), 3)] + [round(float(x), 3) for x in qr.coef_]
d = te[2026]; a = d.actual.values
print("ship (2021-25 fit) on 2026:", round(float(np.mean(np.abs(a - app(d, ship)))), 3), "| 2021-24 fit + old QB:", round(float(np.mean(np.abs(a - app(d, {**newC, "QB": PJC["QB"]})))), 3), "| sleeper", round(float(np.mean(np.abs(a - d.base))), 3))
res["ship_PJC"] = ship; print("ship", ship); json.dump(res, open(f"{B}/e14_fit.json", "w"), indent=1)
