"""Engine 5 fixes, fitted on 2024 and checked on 2025 (exact weekly rosters, e9_exact2 output).
Weaknesses found in the redraft retest: (1) suggestions hurt the lineup more often than managers' own claims, mostly when
the dropped player still had value; (2) WR and QB gains were overstated next to RB and TE; (3) dynasty suggestions were weak.
Fix: score each add/drop pair by the real lineup gain we expect, r_hat = a[add pos]*g - b*drop_value (+ per league type),
pick the best pair by r_hat, and only call it a move when r_hat clears a bar per league type."""
import pickle, sys, os, json, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__))
R, M = pickle.load(open(sys.argv[1] if len(sys.argv) > 1 else B + "/e9_exact2_rosters.pkl", "rb"))
R = pd.DataFrame(R); M = pd.DataFrame(M)
TN = {0: "redraft", 1: "keeper", 2: "dynasty", 3: "other"}
R["tn"] = R.t.map(TN)
lt = R.drop_duplicates("lg").set_index("lg").tn; M["tn"] = M.lg.map(lt)
POS = ["QB", "RB", "WR", "TE"]
def feats(d):
    X = pd.DataFrame(index=d.index)
    for p in POS: X["g_" + p] = d.g * (d.apos == p)
    X["dval"] = d.dval
    for t in ["keeper", "dynasty", "other"]: X["t_" + t] = (d.tn == t).astype(float)
    return X
tr, te = R[R.s == 2024], R[R.s == 2025]
from sklearn.linear_model import HuberRegressor
X = feats(tr); m = HuberRegressor(alpha=1.0, max_iter=2000).fit(X, tr.r3)
coef = dict(zip(X.columns, np.round(m.coef_, 4))); coef["_b"] = round(float(m.intercept_), 4)
print("fitted on 2024:", json.dumps(coef))
R["rh"] = m.predict(feats(R))
key = ["s", "w", "lg", "rid"]
old = R.loc[R.groupby(key).g.idxmax()]          # current app: best pair by modelled lineup lift
new = R.loc[R.groupby(key).rh.idxmax()]         # fixed: best pair by expected real gain
def show(d, col, bar):
    q = d[d[col] >= bar]; return dict(n=len(q), cover=round(len(q) / max(1, len(d)), 3), gain=round(q.r3.mean(), 2),
                                      helped=round((q.r3 > 0).mean(), 3), hurt=round((q.r3 < 0).mean(), 3))
# bar per league type fitted on 2024: lowest bar where shown moves hurt no more often than managers' own waiver claims
bars = {}
for t in ["redraft", "keeper", "dynasty", "other"]:
    mh = (M[(M.tn == t) & (M.s == 2024) & (M.typ == "waiver")].r3 < 0).mean()
    q = new[(new.s == 2024) & (new.tn == t)]
    if not len(q): continue
    for b in np.arange(0, 15.01, .25):
        s_ = show(q, "rh", b)
        if s_["n"] >= 30 and s_["hurt"] <= mh: bars[t] = round(float(b), 2); break
    else: bars[t] = 15.0
print("bars (2024):", bars)
out = {"coef": coef, "bars": bars, "test2025": {}}
for t in ["redraft", "keeper", "dynasty", "other"]:
    o, n = old[(old.s == 2025) & (old.tn == t)], new[(new.s == 2025) & (new.tn == t)]
    if not len(o): continue
    mw = M[(M.tn == t) & (M.s == 2025) & (M.typ == "waiver")]
    res = {"old (g>=4)": show(o, "g", 4), "old (g>=8)": show(o, "g", 8), "new (bar)": show(n, "rh", bars.get(t, 4)),
           "managers' claims": dict(n=len(mw), gain=round(mw.r3.mean(), 2), helped=round((mw.r3 > 0).mean(), 3), hurt=round((mw.r3 < 0).mean(), 3))}
    # same number of moves as the old 4+ rule, for a like-for-like check
    k = res["old (g>=4)"]["n"]; nn = n.nlargest(k, "rh")
    res["new (same count as old 4+)"] = dict(n=len(nn), gain=round(nn.r3.mean(), 2), helped=round((nn.r3 > 0).mean(), 3), hurt=round((nn.r3 < 0).mean(), 3))
    out["test2025"][t] = res
    print(f"\n2025 {t}"); [print(f"  {k_:28s}", v) for k_, v in res.items()]
q = new[(new.s == 2025) & (new.rh >= new.tn.map(bars).fillna(4))]
print("\n2025 new rule, by add position:", q.groupby("apos").r3.agg(["size", "mean", lambda x: (x < 0).mean()]).round(2).to_dict("index"))
qo = old[(old.s == 2025) & (old.g >= 4)]
print("2025 old rule, by add position:", qo.groupby("apos").r3.agg(["size", "mean", lambda x: (x < 0).mean()]).round(2).to_dict("index"))
# tiers on r_hat: what each label delivered in 2025
for t in ["redraft", "dynasty"]:
    q = new[(new.s == 2025) & (new.tn == t)]
    print(t, "2025 by r_hat:", q.groupby(pd.cut(q.rh, [-99, 0, 2, 4, 6, 8, 99])).r3.agg(["size", "mean", lambda x: (x < 0).mean()]).round(2).to_dict("index"))
json.dump(out, open(B + "/e9_fix.json", "w"), indent=1)
