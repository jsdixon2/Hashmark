"""B4 / e26: choose the share of the fitted (OLS) blend vs the shipped rosPPG without touching held-out seasons:
leave-one-season-out inside 2021-24 (fit OLS on the other three, score the left-out season at wk 4/8/11, ROS per team game).
Then refit on 2021-24 and score 2025 / 2026 with the chosen share."""
import os, json, numpy as np, pandas as pd
from sklearn.linear_model import LinearRegression
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(B + "/e26_scored.pkl")
src = open(B + "/e26_eval.py").read(); ns = {}
exec(src.split("# fitted blend (runtime inputs only)")[1].split("FCOLS = None")[0], {"np": np, "pd": pd}, ns); feats = ns["feats"]
def fit(train):
    M = {}
    for pos in ("QB", "RB", "WR", "TE"):
        t = train[(train.pos == pos) & train.role & (train.gR >= 1)]
        m = LinearRegression().fit(feats(t), t.yR / t.gR, sample_weight=t.gR); M[pos] = (m.intercept_, m.coef_)
    return M
def pred(M, d):
    X = feats(d).values; o = np.zeros(len(d))
    for pos, (b, c) in M.items():
        s = (d.pos == pos).values; o[s] = np.maximum(0, b + X[s] @ c)
    return o
A = [0, .25, .4, .5, .6, .75, 1]
cv = {a: [] for a in A}; cvp = {(a, p): [] for a in A for p in ("QB", "RB", "WR", "TE")}
for s in (2021, 2022, 2023, 2024):
    M = fit(D[(D.s <= 2024) & (D.s != s)])
    d = D[(D.s == s) & D.role & D.w.isin([4, 8, 11]) & (D.gR >= 1)].copy(); d["f"] = pred(M, d); y = d.yR / d.gR
    for a in A:
        e = np.abs((1 - a) * d.app + a * d.f - y); cv[a].append(e.mean())
        for p in ("QB", "RB", "WR", "TE"): cvp[(a, p)].append(e[d.pos == p].mean())
print("LOSO 2021-24 ROS MAE by share of fitted blend:", {a: round(float(np.mean(v)), 3) for a, v in cv.items()})
for p in ("QB", "RB", "WR", "TE"): print(p, {a: round(float(np.mean(cvp[(a, p)])), 3) for a in A})
best = min(A, key=lambda a: (round(np.mean(cv[a]), 4), a)); print("chosen share", best)
M = fit(D[D.s <= 2024]); D["ols"] = pred(M, D); D["hm"] = (1 - best) * D.app + best * D.ols
res = {}
for tag, sel, yc, gc in [("2025 ros wk4/8/11", (D.s == 2025) & D.w.isin([4, 8, 11]), "yR", "gR"), ("2025 next4 wk4/8/11", (D.s == 2025) & D.w.isin([4, 8, 11]), "y4", "g4"),
                         ("2026 next4 wk4", (D.s == 2026) & (D.w == 4), "y4", "g4"), ("2026 wk4/8 to wk9", (D.s == 2026) & D.w.isin([4, 8]), "yP", "gP")]:
    for unit, dc in (("per team game", gc), ("per game played", {"gR": "pR", "g4": "p4", "gP": "pP"}[gc])):
        d = D[sel & D.role & (D[dc] >= 1)]; y = d[yc] / d[dc]
        row = {"n": len(d)}
        for c in ("app", "hm", "ols", "wv", "n_ppg", "n_l4", "n_proj"): row[c] = round(float(np.mean(np.abs(d[c] - y))), 3)
        for p in ("QB", "RB", "WR", "TE"):
            q = d.pos == p; row[p] = (int(q.sum()), round(float(np.mean(np.abs(d.app[q] - y[q]))), 3), round(float(np.mean(np.abs(d.hm[q] - y[q]))), 3))
        for w in (4, 8, 11):
            q = d.w == w
            if q.sum(): row[f"wk{w}"] = (int(q.sum()), round(float(np.mean(np.abs(d.app[q] - y[q]))), 3), round(float(np.mean(np.abs(d.hm[q] - y[q]))), 3))
        res[f"{tag} | {unit}"] = row; print(tag, "|", unit, row)
M5 = fit(D[D.s <= 2025])  # what ships: refit including 2025
json.dump({"share": best, "cv": {str(a): float(np.mean(v)) for a, v in cv.items()}, "F": list(feats(D.head(3)).columns),
           "M_2124": {k: [round(float(v[0]), 4)] + [round(float(x), 4) for x in v[1]] for k, v in M.items()},
           "M_2125": {k: [round(float(v[0]), 4)] + [round(float(x), 4) for x in v[1]] for k, v in M5.items()}, "res": res}, open(B + "/e26_mix.json", "w"), indent=1)
d = D[(D.s == 2026) & D.role & D.w.isin([4, 8]) & (D.gP >= 1)].copy(); d["f5"] = (1 - best) * d.app + best * pred(M5, d); y = d.yP / d.gP
print("2026 with weights refit on 2021-25:", round(float(np.mean(np.abs(d.f5 - y))), 3), "vs app", round(float(np.mean(np.abs(d.app - y))), 3))
D.to_pickle(B + "/e26_scored.pkl")
