"""B4 / e26: bias, RMSE, rank correlation; OLS (mean) blend vs median blend; pooled held-out summaries."""
import os, json, numpy as np, pandas as pd
from sklearn.linear_model import LinearRegression
import importlib.util
B = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ev", B + "/e26_eval.py")
D = pd.read_pickle(B + "/e26_scored.pkl")
# reuse feats() from e26_eval without rerunning it
src = open(B + "/e26_eval.py").read(); ns = {}
exec(src.split("# fitted blend (runtime inputs only)")[1].split("FCOLS = None")[0], {"np": np, "pd": pd}, ns)
feats = ns["feats"]
def fit_ols(train, ycol, gcol):
    M = {}
    for pos in ("QB", "RB", "WR", "TE"):
        t = train[(train.pos == pos) & train.role & (train[gcol] >= 1)]
        X = feats(t); y = t[ycol] / t[gcol]
        m = LinearRegression().fit(X, y, sample_weight=t[gcol]); M[pos] = (m.intercept_, m.coef_)
    return M, list(X.columns)
def pred(M, d):
    X = feats(d); o = np.zeros(len(d))
    for pos, (b, c) in M.items():
        s = (d.pos == pos).values; o[s] = np.maximum(0, b + X.values[s] @ c)
    return o
TR = D[D.s <= 2024]
MO, F = fit_ols(TR, "yR", "gR"); D["olsR"] = pred(MO, D)
json.dump({"F": F, "M": {k: [float(v[0])] + [float(x) for x in v[1]] for k, v in MO.items()}}, open(B + "/e26_ols.json", "w"))
EST = ["app", "wv", "n_ppg", "n_l4", "n_proj", "neutral", "fitR", "olsR"]
def stats(d, y):
    o = {}
    for e in EST:
        err = d[e] - y
        rc = np.mean([d[d.pos == p][e].rank().corr(y[d.pos == p].rank()) for p in ("QB", "RB", "WR", "TE")])
        o[e] = (round(float(np.mean(np.abs(err))), 3), round(float(np.mean(err)), 2), round(float(np.sqrt(np.mean(err ** 2))), 2), round(float(rc), 3))
    return o
out = {}
def show(tag, d, ycol, gcol):
    d = d[d[gcol] >= 1]; y = d[ycol] / d[gcol]; st = stats(d, y); out[tag] = dict(n=len(d), **{e: st[e] for e in EST})
    print(f"{tag:28s} n={len(d):4d} " + "  ".join(f"{e}:{st[e][0]:.3f}/{st[e][1]:+.2f}/{st[e][3]:.2f}" for e in EST))
R = D[D.role]
print("MAE/bias/spearman per week incl zeros")
for s in (2021, 2022, 2023, 2024, 2025):
    show(f"{s} ros wk4-8-11", R[(R.s == s) & R.w.isin([4, 8, 11])], "yR", "gR")
    show(f"{s} next4 wk4-8-11", R[(R.s == s) & R.w.isin([4, 8, 11])], "y4", "g4")
show("2026 next4 wk4", R[(R.s == 2026) & (R.w == 4)], "y4", "g4")
show("2026 todate wk4-8", R[(R.s == 2026) & R.w.isin([4, 8])], "yP", "gP")
print("per game played")
def showp(tag, d, ycol, pcol):
    d = d[d[pcol] >= 1]; y = d[ycol] / d[pcol]; st = stats(d, y); out[tag + " gp"] = dict(n=len(d), **{e: st[e] for e in EST})
    print(f"{tag:28s} n={len(d):4d} " + "  ".join(f"{e}:{st[e][0]:.3f}/{st[e][1]:+.2f}" for e in EST))
showp("2025 ros wk4-8-11", R[(R.s == 2025) & R.w.isin([4, 8, 11])], "yR", "pR")
showp("2025 next4 wk4-8-11", R[(R.s == 2025) & R.w.isin([4, 8, 11])], "y4", "p4")
showp("2026 next4 wk4", R[(R.s == 2026) & (R.w == 4)], "y4", "p4")
showp("2026 todate wk4-8", R[(R.s == 2026) & R.w.isin([4, 8])], "yP", "pP")
print("per position 2025 ros per week, 2026 todate per week")
for pos in ("QB", "RB", "WR", "TE"):
    show(f"2025 ros {pos}", R[(R.s == 2025) & R.w.isin([4, 8, 11]) & (R.pos == pos)], "yR", "gR")
    show(f"2026 todate {pos}", R[(R.s == 2026) & R.w.isin([4, 8]) & (R.pos == pos)], "yP", "gP")
json.dump(out, open(B + "/e26_more.json", "w"), indent=0)
D.to_pickle(B + "/e26_scored.pkl")
