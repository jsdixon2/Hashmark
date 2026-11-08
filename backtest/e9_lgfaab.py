"""Does a league's own past bidding predict what claims cost there later in the season?"""
import pandas as pd, numpy as np, json, os
B = os.path.dirname(os.path.abspath(__file__))
src = open(B + "/e9_faab.py").read().split('out = {"n_bids"')[0].replace("os.path.dirname(os.path.abspath(__file__))", repr(B))
exec(src)
W = W.dropna(subset=["tier"]).copy()
tr = W[W.s <= 2023]; te = W[W.s >= 2024].copy()
QS = np.linspace(0, 1, 41)
tab = {k: g.pct.quantile(QS).values for k, g in tr.groupby(["tier", "phase"], observed=True)}
def q_at(k, p): return float(np.interp(p, QS, tab[k]))
def cdf(k, x):
    v = tab[k]; lo = np.searchsorted(v, x, side="left"); hi = np.searchsorted(v, x, side="right")
    return float(QS[min(len(QS) - 1, max(0, (lo + hi) // 2))])
te["F"] = [cdf((t, p), x) for t, p, x in zip(te.tier, te.phase, te.pct)]
# league factor from its own first-half claims: average position in the global distribution (0.5 = typical)
te["half"] = np.where(te.w <= 8, "early", "late")
f = te[te.half == "early"].groupby(["lg", "s"]).agg(Fm=("F", "mean"), nh=("F", "size")).reset_index()
L2 = te[te.half == "late"].merge(f, on=["lg", "s"], how="inner")
out = {"late claims with early history": len(L2), "leagues": int(L2[["lg", "s"]].drop_duplicates().shape[0])}
out["corr: league's early position vs late claims' position"] = round(float(np.corrcoef(L2.Fm, L2.F)[0, 1]), 3)
for target in (.5, .7, .85):
    g = np.array([q_at((t, p), target) for t, p in zip(L2.tier, L2.phase)])
    # shift the target percentile by how far the league runs from typical, shrunk by sample size
    k = L2.nh / (L2.nh + 8); adj_t = np.clip(target + k * (L2.Fm - .5), .02, .99)
    a = np.array([q_at((t, p), tt) for t, p, tt in zip(L2.tier, L2.phase, adj_t)])
    hi = L2.Fm > .58; lo = L2.Fm < .42
    out[f"target {int(target*100)}%: share of real winning bids at/below the suggested bid"] = {
        "global table, all": round(float((L2.pct <= g).mean()), 3), "league-adjusted, all": round(float((L2.pct <= a).mean()), 3),
        "global, pricey leagues": round(float((L2.pct[hi] <= g[hi]).mean()), 3), "adjusted, pricey leagues": round(float((L2.pct[hi] <= a[hi]).mean()), 3),
        "global, cheap leagues": round(float((L2.pct[lo] <= g[lo]).mean()), 3), "adjusted, cheap leagues": round(float((L2.pct[lo] <= a[lo]).mean()), 3),
        "avg bid global %": round(float(g.mean() * 100), 2), "avg bid adjusted %": round(float(a.mean() * 100), 2)}
out["pricey/cheap league counts"] = [int((f.Fm > .58).sum()), int((f.Fm < .42).sum()), len(f)]
print(json.dumps(out, indent=1)); json.dump(out, open(B + "/e9_lgfaab.json", "w"), indent=1)
