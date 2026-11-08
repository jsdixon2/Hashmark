import pickle, numpy as np, json, os, collections
B = os.path.dirname(os.path.abspath(__file__))
exec(open(B + "/e7_keeper.py").read().split("rows = []")[0].split("K = json.load")[0])  # imports only
import gzip
HV = json.load(gzip.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bt") + "/hv.json.gz", "rt"))
R = pickle.load(open(B + "/e7_rows.pkl", "rb"))
A1 = np.array([[1, 10000], [2, 9713], [3, 9455], [6, 8778], [12, 7677], [18, 6782], [24, 6028], [36, 4819], [50, 3762], [75, 2476], [100, 1664], [150, 782], [200, 381], [300, 98], [450, 14], [600, 5]], float)
AS = np.array([[1, 10000], [2, 9766], [3, 9548], [6, 8960], [12, 7959], [18, 7114], [24, 6382], [36, 5178], [50, 4093], [75, 2732], [100, 1849], [150, 870], [200, 421], [300, 103], [450, 14], [600, 5]], float)
cv = lambda A, r: float(np.exp(np.interp(np.log(max(1, r)), np.log(A[:, 0]), np.log(A[:, 1]))))
def rk(t, di, pid):
    m = HV.setdefault("_m", {}).get((t, di))
    if m is None: m = {HV["ids"][ix]: i + 1 for i, ix in enumerate(HV["t"][t][di])}; HV["_m"][(t, di)] = m
    return m.get(pid)
PVT = [[0, .5], [.05, .54], [.12, .58], [.2, .605], [.3, .63], [.45, .65], [.6, .675], [.75, .7], [.9, .765], [1, .78]]
def pv(p):
    a = min(1, abs(p)); xs = [x for x, _ in PVT]; ys = [y for _, y in PVT]; v = float(np.interp(a, xs, ys)); return v if p >= 0 else 1 - v
lg = lambda p: np.log(p / (1 - p))
def keep_val(r, ids, mode):
    A = AS if r["sf"] else A1; n = r["n"]; K = r["kmax"] or 0
    if K <= 0: return 0.0, 1.0
    lastr = r["lastr"] or 16
    def val(p): return .7 * cv(A, rk("dsf" if r["sf"] else "do", r["di"], p) or 400) + .3 * cv(A, rk("rsf" if r["sf"] else "ro", r["di"], p) or 400)
    def cost(p):
        if mode == "line": return cv(A, n * K + 1)
        if mode == "none" or r["style"] == "none" or not r["od"].get(p): return cv(A, n * K + (lastr - .5) * n)
        return cv(A, n * K + (max(1, r["od"][p]) - .5) * n)
    s = sorted([max(0.0, val(p) - cost(p)) for p in ids], reverse=True)[:K]; return sum(s), max([val(p) for p in ids] + [1])
out = {}; rows = []
for r in R:
    a, b = r["a"], r["b"]; sa, sb = r["side"][a], r["side"][b]
    Ta, Tb = sa["now"] + sa["fut"], sb["now"] + sb["fut"]
    if Ta == Tb: continue
    feat = {"d": sa["pnow"] - sb["pnow"], "won": Ta > Tb, "won_now": sa["now"] > sb["now"], "season": r["season"], "kshare": r["kshare"], "style": r["style"], "futmat": abs(sa["fut"] - sb["fut"]) > 1}
    for mode in ("cost", "none", "line"):
        ka = keep_val(r, r["post"][a], mode)[0] - keep_val(r, r["pre"][a], mode)[0]; kb = keep_val(r, r["post"][b], mode)[0] - keep_val(r, r["pre"][b], mode)[0]
        sc = max(1.0, max(keep_val(r, r["pre"][a], mode)[1], keep_val(r, r["pre"][b], mode)[1]) * .5)
        feat["pk_" + mode] = max(-1, min(1, (ka - kb) / sc))
    rows.append(feat)
print(len(rows), "keeper trades with a winner;", sum(x["futmat"] for x in rows), "where next season mattered")
def acc(rs, c, mode="cost", tau=.35):
    h = 0
    for x in rs:
        wf = max(0, min(.95, c * 1.15 * x["kshare"])); z = (1 - wf) * .878 * np.tanh(x["d"] / tau) + wf * lg(pv(x["pk_" + mode]))
        if z == 0: z = 1e-9 * x["d"]
        h += (z > 0) == x["won"]
    return round(h / max(1, len(rs)), 4)
tr = [x for x in rows if x["season"] <= 2023]; te = [x for x in rows if x["season"] >= 2024]
out["n"] = dict(all=len(rows), train=len(tr), test=len(te))
for c in (0, .25, .5, .75, 1.0, 1.5, 2.0, 3.0):
    out[f"c={c}"] = dict(train=acc(tr, c), test=acc(te, c), all=acc(rows, c), next_season_mattered=acc([x for x in rows if x["futmat"]], c))
best = max((acc(tr, c), c) for c in np.arange(0, 3.01, .25)); out["fit_c"] = best[1]; out["test_at_fit"] = acc(te, best[1])
for mode in ("cost", "none", "line"): out["mode_" + mode] = acc(rows, best[1], mode)
out["by_style"] = {s: dict(n=len([x for x in rows if x["style"] == s]), acc=acc([x for x in rows if x["style"] == s], best[1])) for s in ("none", "round")}
out["by_keepers"] = {k: acc([x for x in rows if lo <= x["kshare"] < hi], best[1]) for k, (lo, hi) in {"<15%": (0, .15), "15-30%": (.15, .3), "30%+": (.3, 2)}.items()}
out["n_by_keepers"] = {k: len([x for x in rows if lo <= x["kshare"] < hi]) for k, (lo, hi) in {"<15%": (0, .15), "15-30%": (.15, .3), "30%+": (.3, 2)}.items()}
print(json.dumps(out, indent=1)); json.dump(out, open(B + "/e7.json", "w"), indent=1)
