"""B1 step 2: do the PPR projection weights (index.html PJC) work in half-PPR and standard leagues?
Population per format: Sleeper projected >= 3 in that scoring, player played. MAE in that format's points.
Candidates: Sleeper; PJC as-is; PJC's 2021-24 PPR fit as-is (fully held out in 2025); PJC with its additive terms (intercept, has-PPG, has-xFP) scaled by the format's points
per PPR point (one number per position, from 2021-24 projections); a format-specific median-regression refit (2021-24).
Test 2025 and 2026 (to date). Then the shipping refit on 2021-25, checked on 2026. Output backtest/e15_fit.json."""
import os, json, re, numpy as np, pandas as pd
from sklearn.linear_model import QuantileRegressor
B = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(B)
P = pd.read_pickle(f"{B}/e15_panel.pkl")
src = open(f"{R}/index.html", encoding="utf-8").read()
PJC = json.loads(re.search(r"const PJC=(\{.*?\});", src).group(1))
PW = {"QB": .1, "RB": .3, "WR": .3, "TE": .3}
POS = ("QB", "RB", "WR", "TE")
ppr = P[P.fmt == "ppr"].set_index(["s", "w", "pid"]).base
def X(d):
    v = lambda c: d[c].astype(float).fillna(d.base)
    return np.column_stack([d.base, v("ppg"), v("l3"), v("xs"), v("x3"),
                            np.where(d.rk.notna(), d.base * (16.5 - d.rk.astype(float).fillna(16.5)) / 16, 0),
                            np.where(d.imp.notna(), d.base * (d.imp.astype(float).fillna(22.5) - 22.5) / 22.5, 0),
                            d["ppg"].notna().astype(float), d["xs"].notna().astype(float)])
def app(d, C):
    out = np.zeros(len(d))
    for pos in POS:
        m = (d.pos == pos).values
        if m.any(): c = C[pos]; out[m] = np.maximum(0, c[0] + X(d[m]) @ np.array(c[1:]))
    out = np.where(d.q, out * .88, out)
    mk = d.mk.astype(float).values; pw = d.pos.map(PW).values
    return np.where(np.isnan(mk), out, out * (1 - pw) + np.nan_to_num(mk) * pw)
def scaled(C, k):   # additive terms x k (format points per PPR point)
    return {p: [c[0] * k[p]] + c[1:8] + [c[8] * k[p], c[9] * k[p]] for p, c in C.items()}
def fit(tr, keepQB=True):
    C = {}
    for pos in POS:
        if keepQB and pos == "QB": C[pos] = PJC["QB"]; continue
        d = tr[tr.pos == pos]; y = d.actual / np.where(d.q, .88, 1)
        qr = QuantileRegressor(quantile=.5, alpha=0, solver="highs").fit(X(d), y)
        C[pos] = [round(float(qr.intercept_), 3)] + [round(float(x), 3) for x in qr.coef_]
    return C
def mae(d, p): return round(float(np.mean(np.abs(d.actual.values - p))), 3)
def report(d, preds):
    r = {"n": int(len(d))}
    for name, p in preds.items():
        r[name] = mae(d, p); r[name + "_pos"] = {pos: mae(d[(d.pos == pos).values], p[(d.pos == pos).values]) for pos in POS}
        wk = d.assign(e=np.abs(d.actual.values - p), s=np.abs(d.actual.values - d.base.values)).groupby("w")[["e", "s"]].mean()
        r[name + "_weeks_beat"] = f"{int((wk.e < wk.s).sum())}/{len(wk)}"
    return r
# PJC's 2021-24 PPR fit (backtest/e14_fit.json, QB as shipped): the PPR weights on seasons they never saw, incl. 2025
C14 = {**json.load(open(f"{B}/e14_fit.json"))["new_PJC"], "QB": PJC["QB"]}
res = {}
for f in ("ppr", "half", "std"):
    D = P[(P.fmt == f) & (P.base >= 3)].rename(columns={"a": "actual"}).copy()
    tr = D[D.s <= 2024]
    if f == "ppr": k = {p: 1.0 for p in POS}
    else:
        T = P[(P.fmt == f) & (P.s <= 2024)].copy(); T["bp"] = [ppr.get((a, b, c), np.nan) for a, b, c in zip(T.s, T.w, T.pid)]
        T = T[T.bp >= 3]; k = {p: round(float(T[T.pos == p].base.sum() / T[T.pos == p].bp.sum()), 3) for p in POS}
    Cf = fit(tr); Cfq = fit(tr, keepQB=False)
    res[f] = {"k": k, "refit_2124": Cfq}
    for y in (2025, 2026):
        d = D[D.s == y]
        preds = {"sleeper": d.base.values.astype(float), "pjc_now": app(d, PJC), "pjc_scaled": app(d, scaled(PJC, k)),
                 "refit": app(d, Cf), "refit_incl_qb": app(d, Cfq), "ppr_fit_2124": app(d, C14)}
        res[f][y] = report(d, preds)
        print(f, y, {kk: v for kk, v in res[f][y].items() if not kk.endswith("_pos")})
        for nm in preds: print("    ", nm, res[f][y][nm + "_pos"])
    ship = fit(D[D.s <= 2025]); ship_q = fit(D[D.s <= 2025], keepQB=False); d = D[D.s == 2026]
    res[f]["ship_2125"] = ship; res[f]["ship_2125_incl_qb"] = ship_q
    res[f]["ship_on_2026"] = report(d, {"sleeper": d.base.values.astype(float), "pjc_now": app(d, PJC), "ship": app(d, ship), "ship_incl_qb": app(d, ship_q)})
    print(f, "k", k, "ship 2021-25 on 2026", {kk: v for kk, v in res[f]["ship_on_2026"].items() if not kk.endswith("_pos")})
json.dump(res, open(f"{B}/e15_fit.json", "w"), indent=1)
