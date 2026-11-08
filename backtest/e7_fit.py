"""Which way of judging a keeper-league trade best predicts who came out ahead (this season's lineup points + next season's keeper value)?"""
import pickle, json, os, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
B = os.path.dirname(os.path.abspath(__file__))
src = open(B + "/e7_eval.py").read().split("out = {}; rows = []")[0]
exec(src)
def effV(vs):
    vs = sorted(vs, reverse=True); return sum(.75 ** i * v ** 1.3 for i, v in enumerate(vs)) ** (1 / 1.3) if vs else 0.0
rows = []
for r in R:
    a, b = r["a"], r["b"]; sa, sb = r["side"][a], r["side"][b]
    T = sa["now"] + sa["fut"] - sb["now"] - sb["fut"]
    if T == 0: continue
    A = AS if r["sf"] else A1
    dv = lambda p: cv(A, rk("dsf" if r["sf"] else "do", r["di"], p) or 400)
    rv = lambda p: cv(A, rk("rsf" if r["sf"] else "ro", r["di"], p) or 400)
    dyn = effV([dv(p) for p in sa["got"]]) - effV([dv(p) for p in sb["got"]])
    red = effV([rv(p) for p in sa["got"]]) - effV([rv(p) for p in sb["got"]])
    ka = keep_val(r, r["post"][a], "cost")[0] - keep_val(r, r["pre"][a], "cost")[0]
    kb = keep_val(r, r["post"][b], "cost")[0] - keep_val(r, r["pre"][b], "cost")[0]
    rows.append(dict(y=T > 0, ynow=sa["now"] > sb["now"], yfut=np.sign(sa["fut"] - sb["fut"]), now=(sa["pnow"] - sb["pnow"]) * r["rem"], dyn=dyn / 1000, red=red / 1000, keep=(ka - kb) / 1000,
                     ks=r["kshare"], season=r["season"], key=r["key"], style=r["style"]))
import pandas as pd
D = pd.DataFrame(rows); print(len(D), "trades")
D["now_s"] = np.tanh(D.now / 60); D["keep_s"] = np.tanh(D.keep / 2); D["dyn_s"] = np.tanh(D.dyn / 2); D["red_s"] = np.tanh(D.red / 2)
D["keep_ks"] = D.keep_s * D.ks; D["dyn_ks"] = D.dyn_s * D.ks
M = {"pure redraft (this-season lineup gain)": ["now_s"], "pure dynasty (long-term value)": ["dyn_s"], "redraft value (season ranks)": ["red_s"],
     "lineup gain + keeper surplus": ["now_s", "keep_s"], "lineup gain + keeper surplus x keepers/roster": ["now_s", "keep_s", "keep_ks"],
     "lineup gain + dynasty x keepers/roster": ["now_s", "dyn_s", "dyn_ks"], "all": ["now_s", "keep_s", "keep_ks", "dyn_s", "dyn_ks", "red_s"]}
out = {}; g = GroupKFold(5)
def cvacc(cols, d):
    X = d[cols].values; y = d.y.values; h = 0; ll = 0
    for tr, te in g.split(X, y, d.key):
        m = LogisticRegression(fit_intercept=False, C=10).fit(X[tr], y[tr]); p = m.predict_proba(X[te])[:, 1]
        h += ((p > .5) == y[te]).sum(); ll += -np.sum(y[te] * np.log(p) + (1 - y[te]) * np.log(1 - p))
    return round(h / len(d), 4), round(ll / len(d), 4)
for k, cols in M.items():
    out[k] = cvacc(cols, D)
    m = LogisticRegression(fit_intercept=False, C=10).fit(D[cols].values, D.y.values); out[k + " coef"] = dict(zip(cols, np.round(m.coef_[0], 3)))
for lo, hi in ((0, .15), (.15, .3), (.3, 2)):
    d = D[(D.ks >= lo) & (D.ks < hi)]
    out[f"keepers/roster {lo}-{hi} (n={len(d)})"] = {k: cvacc(c, d)[0] for k, c in M.items() if "x keepers" not in k and k != "all"}
    m = LogisticRegression(fit_intercept=False, C=10).fit(d[["now_s", "keep_s"]].values, d.y.values); out[f"coef {lo}-{hi}"] = np.round(m.coef_[0], 3).tolist()
# future-only check: when next season decided something, does keeper surplus call it?
f = D[D.yfut != 0]; out["future-only: keeper surplus picks next-season winner"] = round(float(np.mean(np.sign(f.keep) == f.yfut)), 4)
out["future-only: dynasty value picks next-season winner"] = round(float(np.mean(np.sign(f.dyn) == f.yfut)), 4)
out["future-only n"] = len(f)
print(json.dumps(out, indent=1, default=str)); json.dump(out, open(B + "/e7_fit.json", "w"), indent=1, default=str)
D.to_pickle(B + "/e7_D.pkl")
